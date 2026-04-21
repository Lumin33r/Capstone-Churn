#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/recycle_notready_nodes.sh [options]

Safely replaces Kubernetes nodes that are NotReady by:
  1. Attempting to cordon and drain the node
  2. Deleting the stale Kubernetes Node object
  3. Terminating the backing EC2 instance through its Auto Scaling Group
     without decrementing desired capacity, so the nodegroup replaces it

Options:
  --cluster-name NAME       EKS cluster name for display only
  --nodegroup NAME          Only target nodes in this EKS nodegroup label
  --node NAME               Target a specific node; repeatable
  --min-ready N             Refuse execution if fewer than N nodes are Ready (default: 2)
  --wait-seconds N          Drain timeout in seconds (default: 60)
  --execute                 Perform the replacement actions
  --help                    Show this help text

Examples:
  ./scripts/recycle_notready_nodes.sh --nodegroup retention-ng
  ./scripts/recycle_notready_nodes.sh --node ip-10-0-1-112.ec2.internal --execute
  ./scripts/recycle_notready_nodes.sh --nodegroup retention-ng --execute
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

get_ready_count() {
  kubectl get nodes --no-headers 2>/dev/null | awk '$2 == "Ready" {count++} END {print count+0}'
}

jsonpath_field() {
  local node_name=$1
  local path=$2
  kubectl get node "$node_name" -o "jsonpath=${path}" 2>/dev/null || true
}

drain_node() {
  local node_name=$1
  local timeout_seconds=$2

  kubectl cordon "$node_name" >/dev/null 2>&1 || true
  kubectl drain "$node_name" \
    --ignore-daemonsets \
    --delete-emptydir-data \
    --force \
    --grace-period=30 \
    --timeout="${timeout_seconds}s" >/dev/null 2>&1 || true
}

CLUSTER_NAME="${EKS_CLUSTER_NAME:-}"
NODEGROUP_FILTER=""
MIN_READY_NODES=2
DRAIN_TIMEOUT_SECONDS=60
EXECUTE=false
declare -a REQUESTED_NODES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-name)
      CLUSTER_NAME=${2:?Missing value for --cluster-name}
      shift 2
      ;;
    --nodegroup)
      NODEGROUP_FILTER=${2:?Missing value for --nodegroup}
      shift 2
      ;;
    --node)
      REQUESTED_NODES+=("${2:?Missing value for --node}")
      shift 2
      ;;
    --min-ready)
      MIN_READY_NODES=${2:?Missing value for --min-ready}
      shift 2
      ;;
    --wait-seconds)
      DRAIN_TIMEOUT_SECONDS=${2:?Missing value for --wait-seconds}
      shift 2
      ;;
    --execute)
      EXECUTE=true
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

require_cmd kubectl
require_cmd aws

if [[ -z "$CLUSTER_NAME" ]]; then
  raw_cluster=$(kubectl config view --minify -o jsonpath='{.contexts[0].context.cluster}' 2>/dev/null || true)
  CLUSTER_NAME=${raw_cluster##*/}
fi

if [[ -z "$CLUSTER_NAME" ]]; then
  echo "Unable to determine cluster name from kubeconfig; pass --cluster-name" >&2
  exit 1
fi

READY_COUNT=$(get_ready_count)
echo "Cluster: $CLUSTER_NAME"
echo "Current Ready nodes: $READY_COUNT"
echo "Execution mode: $([[ "$EXECUTE" == true ]] && echo EXECUTE || echo DRY-RUN)"

if [[ "$EXECUTE" == true && "$READY_COUNT" -lt "$MIN_READY_NODES" ]]; then
  echo "Refusing to proceed: only $READY_COUNT Ready nodes, below --min-ready=$MIN_READY_NODES" >&2
  exit 1
fi

declare -a TARGET_NODES=()

if [[ ${#REQUESTED_NODES[@]} -gt 0 ]]; then
  TARGET_NODES=("${REQUESTED_NODES[@]}")
else
  while IFS='|' read -r node_name nodegroup ready_status; do
    [[ -z "$node_name" ]] && continue
    [[ "$ready_status" == "True" ]] && continue
    if [[ -n "$NODEGROUP_FILTER" && "$nodegroup" != "$NODEGROUP_FILTER" ]]; then
      continue
    fi
    TARGET_NODES+=("$node_name")
  done < <(kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{.metadata.labels.eks\.amazonaws\.com/nodegroup}{"|"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}')
fi

if [[ ${#TARGET_NODES[@]} -eq 0 ]]; then
  echo "No matching NotReady nodes found"
  exit 0
fi

echo "Target nodes:"
printf '  - %s\n' "${TARGET_NODES[@]}"

for node_name in "${TARGET_NODES[@]}"; do
  nodegroup=$(jsonpath_field "$node_name" '{.metadata.labels.eks\.amazonaws\.com/nodegroup}')
  provider_id=$(jsonpath_field "$node_name" '{.spec.providerID}')
  ready_status=$(jsonpath_field "$node_name" '{.status.conditions[?(@.type=="Ready")].status}')
  instance_id=${provider_id##*/}

  if [[ -z "$provider_id" || "$instance_id" == "$provider_id" ]]; then
    echo "Skipping $node_name: unable to determine provider ID" >&2
    continue
  fi

  asg_name=$(aws --no-cli-pager autoscaling describe-auto-scaling-instances \
    --instance-ids "$instance_id" \
    --query 'AutoScalingInstances[0].AutoScalingGroupName' \
    --output text 2>/dev/null || true)

  if [[ -z "$asg_name" || "$asg_name" == "None" ]]; then
    echo "Skipping $node_name: instance $instance_id is not attached to an Auto Scaling Group" >&2
    continue
  fi

  echo
  echo "Node: $node_name"
  echo "  nodegroup: ${nodegroup:-unknown}"
  echo "  ready: ${ready_status:-Unknown}"
  echo "  instance: $instance_id"
  echo "  asg: $asg_name"

  echo "  workloads:"
  kubectl get pods -A --field-selector "spec.nodeName=$node_name" -o wide 2>/dev/null || true

  if [[ "$EXECUTE" != true ]]; then
    echo "  dry-run actions: cordon/drain -> delete node -> terminate instance in ASG without decrementing desired capacity"
    continue
  fi

  echo "  draining node..."
  drain_node "$node_name" "$DRAIN_TIMEOUT_SECONDS"

  echo "  deleting Kubernetes node object..."
  kubectl delete node "$node_name" --ignore-not-found

  echo "  terminating EC2 instance via ASG replacement..."
  aws --no-cli-pager autoscaling terminate-instance-in-auto-scaling-group \
    --instance-id "$instance_id" \
    --no-should-decrement-desired-capacity >/dev/null

  echo "  replacement requested for $instance_id"
done

if [[ "$EXECUTE" == true ]]; then
  echo
  echo "Replacement requests submitted. Monitor with:"
  echo "  kubectl get nodes -o wide"
  echo "  aws --no-cli-pager eks describe-nodegroup --cluster-name $CLUSTER_NAME --nodegroup-name ${NODEGROUP_FILTER:-<nodegroup>}"
else
  echo
  echo "Dry run complete. Re-run with --execute to perform replacement."
fi
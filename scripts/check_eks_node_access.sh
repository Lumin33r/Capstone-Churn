#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/check_eks_node_access.sh [options]

Validate that an EKS nodegroup's IAM role is authorized in aws-auth and that
the cluster has enough Ready nodes in the target nodegroup for a safe rollout.

Options:
  --cluster-name NAME       EKS cluster name
  --nodegroup NAME          EKS nodegroup name
  --min-ready N             Minimum Ready nodes required in the target nodegroup (default: 1)
  --help                    Show this help text
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

CLUSTER_NAME=""
NODEGROUP_NAME=""
MIN_READY_NODES=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-name)
      CLUSTER_NAME=${2:?Missing value for --cluster-name}
      shift 2
      ;;
    --nodegroup)
      NODEGROUP_NAME=${2:?Missing value for --nodegroup}
      shift 2
      ;;
    --min-ready)
      MIN_READY_NODES=${2:?Missing value for --min-ready}
      shift 2
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

require_cmd aws
require_cmd kubectl

if [[ -z "$CLUSTER_NAME" || -z "$NODEGROUP_NAME" ]]; then
  echo "Both --cluster-name and --nodegroup are required" >&2
  exit 1
fi

NODE_ROLE_ARN=$(aws --no-cli-pager eks describe-nodegroup \
  --cluster-name "$CLUSTER_NAME" \
  --nodegroup-name "$NODEGROUP_NAME" \
  --query 'nodegroup.nodeRole' \
  --output text)

if [[ -z "$NODE_ROLE_ARN" || "$NODE_ROLE_ARN" == "None" ]]; then
  echo "Unable to determine node role for nodegroup $NODEGROUP_NAME" >&2
  exit 1
fi

AWS_AUTH_ROLES=$(kubectl get configmap aws-auth -n kube-system -o jsonpath='{.data.mapRoles}')

if ! grep -Fq "$NODE_ROLE_ARN" <<<"$AWS_AUTH_ROLES"; then
  echo "❌ EKS node authorization drift detected" >&2
  echo "Expected node role: $NODE_ROLE_ARN" >&2
  kubectl get configmap aws-auth -n kube-system -o yaml >&2
  exit 1
fi

READY_NODES=$(kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.labels.eks\.amazonaws\.com/nodegroup}{"|"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' \
  | awk -F'|' -v nodegroup="$NODEGROUP_NAME" '$1 == nodegroup && $2 == "True" {count++} END {print count+0}')

TOTAL_NODES=$(kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.labels.eks\.amazonaws\.com/nodegroup}{"\n"}{end}' \
  | awk -v nodegroup="$NODEGROUP_NAME" '$1 == nodegroup {count++} END {print count+0}')

echo "Target nodegroup: $NODEGROUP_NAME"
echo "Expected node role: $NODE_ROLE_ARN"
echo "Registered nodes in nodegroup: $TOTAL_NODES"
echo "Ready nodes in nodegroup: $READY_NODES"

if [[ "$READY_NODES" -lt "$MIN_READY_NODES" ]]; then
  echo "❌ Insufficient Ready nodes in nodegroup $NODEGROUP_NAME. Need at least $MIN_READY_NODES before rollout." >&2
  kubectl get nodes -o wide >&2
  exit 1
fi

echo "✅ EKS node authorization and nodegroup capacity look healthy"
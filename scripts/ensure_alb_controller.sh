#!/usr/bin/env bash

set -euo pipefail

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [[ -z "$REGION" ]]; then
  echo "AWS_REGION or AWS_DEFAULT_REGION must be set"
  exit 1
fi

RAW_CLUSTER=$(kubectl config view --minify -o jsonpath='{.contexts[0].context.cluster}')
CLUSTER_NAME="${EKS_CLUSTER_NAME:-${RAW_CLUSTER##*/}}"
ROLE_NAME="${ALB_CONTROLLER_ROLE_NAME:-retention-engine-alb-controller-role}"
ROLE_ARN="${ALB_CONTROLLER_ROLE_ARN:-}"

if [[ -z "$ROLE_ARN" ]]; then
  ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
fi

if [[ -z "$ROLE_ARN" || "$ROLE_ARN" == "None" ]]; then
  echo "Unable to determine ALB controller IAM role ARN"
  exit 1
fi

VPC_ID=$(aws eks describe-cluster --name "$CLUSTER_NAME" --query 'cluster.resourcesVpcConfig.vpcId' --output text)

echo "Ensuring AWS Load Balancer Controller for cluster: $CLUSTER_NAME"
echo "Using IAM role: $ROLE_ARN"

if ! helm repo list | awk '{print $1}' | grep -qx eks; then
  helm repo add eks https://aws.github.io/eks-charts
fi
helm repo update eks

kubectl create serviceaccount aws-load-balancer-controller \
  -n kube-system \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl annotate serviceaccount aws-load-balancer-controller \
  -n kube-system \
  eks.amazonaws.com/role-arn="$ROLE_ARN" \
  --overwrite

helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  --namespace kube-system \
  --set clusterName="$CLUSTER_NAME" \
  --set region="$REGION" \
  --set vpcId="$VPC_ID" \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --wait

kubectl rollout status deployment/aws-load-balancer-controller \
  -n kube-system \
  --timeout="${ALB_CONTROLLER_TIMEOUT:-180s}"

echo "✅ AWS Load Balancer Controller is ready"
#!/usr/bin/env bash
# scripts/install-alb-controller.sh
# One-time setup: installs the AWS Load Balancer Controller into EKS via Helm.
# Run AFTER terraform apply has created the IAM role.
#
# Prerequisites:
#   - kubectl configured for the target cluster
#   - helm v3 installed
#   - terraform apply completed (for the IAM role ARN)
#
# Usage:
#   ./scripts/install-alb-controller.sh

set -euo pipefail

CLUSTER_NAME="eks-ezvrmopo-okl"
NAMESPACE="kube-system"
REGION="us-east-1"

# Get the IAM role ARN from Terraform output
echo "Reading ALB controller role ARN from Terraform..."
ROLE_ARN=$(cd terraform && terraform output -raw alb_controller_role_arn)
echo "Role ARN: $ROLE_ARN"

# Add the EKS Helm chart repo
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Install the controller
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  --namespace "$NAMESPACE" \
  --set clusterName="$CLUSTER_NAME" \
  --set region="$REGION" \
  --set vpcId="$(aws eks describe-cluster --name "$CLUSTER_NAME" --query 'cluster.resourcesVpcConfig.vpcId' --output text)" \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"="$ROLE_ARN"

echo ""
echo "Waiting for controller to be ready..."
kubectl rollout status deployment/aws-load-balancer-controller -n "$NAMESPACE" --timeout=120s

echo ""
echo "✅ AWS Load Balancer Controller installed successfully"
echo "You can now apply k8s/ingress.yaml and it will create an ALB."

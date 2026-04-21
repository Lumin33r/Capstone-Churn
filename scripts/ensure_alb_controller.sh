#!/usr/bin/env bash

set -euo pipefail

wait_for_webhook() {
  local attempts=${1:-24}
  local sleep_seconds=${2:-5}
  local secret_ca=""
  local mutating_webhook_ca=""
  local validating_webhook_ca=""

  echo "Waiting for ALB webhook TLS and admission readiness..."

  for ((i=1; i<=attempts; i++)); do
    secret_ca=$(kubectl get secret aws-load-balancer-tls -n kube-system -o jsonpath='{.data.ca\.crt}' 2>/dev/null || true)
    mutating_webhook_ca=$(kubectl get mutatingwebhookconfiguration aws-load-balancer-webhook -o jsonpath='{.webhooks[2].clientConfig.caBundle}' 2>/dev/null || true)
    validating_webhook_ca=$(kubectl get validatingwebhookconfiguration aws-load-balancer-webhook -o jsonpath='{.webhooks[2].clientConfig.caBundle}' 2>/dev/null || true)

    if [[ -n "$secret_ca" && -n "$mutating_webhook_ca" && -n "$validating_webhook_ca" && "$secret_ca" == "$mutating_webhook_ca" && "$secret_ca" == "$validating_webhook_ca" ]]; then
      if cat <<'EOF' | kubectl apply --dry-run=server -f - >/dev/null 2>&1
apiVersion: v1
kind: Service
metadata:
  name: alb-webhook-probe
  namespace: default
spec:
  selector:
    app: does-not-matter
  ports:
    - port: 80
      targetPort: 80
  type: ClusterIP
EOF
      && kubectl apply --dry-run=server -f k8s/ingress.yaml >/dev/null 2>&1
      then
        echo "✅ ALB webhook is ready"
        return 0
      fi
    fi

    echo "[$i/$attempts] Webhook not ready yet; waiting ${sleep_seconds}s..."
    sleep "$sleep_seconds"
  done

  echo "ALB webhook did not become ready in time"
  kubectl get secret aws-load-balancer-tls -n kube-system -o yaml || true
  kubectl get mutatingwebhookconfiguration aws-load-balancer-webhook -o yaml || true
  kubectl get validatingwebhookconfiguration aws-load-balancer-webhook -o yaml || true
  kubectl get deployment aws-load-balancer-controller -n kube-system -o yaml | sed -n '1,220p' || true
  exit 1
}

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

wait_for_webhook

echo "✅ AWS Load Balancer Controller is ready"
# Retention Engine — Setup & Deployment Guide

**Author:** George (gvill0576) — Infrastructure and Agentic Layer
**Team:** George, Kathleen, Okino, Troy
**Repository:** https://github.com/Lumin33r/Capstone-Churn
**Last updated:** April 2026

This document explains how to reproduce the full Retention Engine platform
from scratch. It covers prerequisites, environment setup, Terraform
infrastructure lifecycle, local development with Docker Compose, and
Kubernetes deployment to EKS. Follow the sections in order.

---

## Table of Contents

1. Prerequisites
2. Clone the Repository
3. Environment Variables
4. Terraform Infrastructure Lifecycle
5. Local Development with Docker Compose
6. Kubernetes EKS Deployment
7. Troubleshooting
8. Architecture Overview
9. Team Ownership Reference

---

## 1. Prerequisites

Before starting, confirm every tool below is installed on your machine.
Run each command in your terminal and verify it returns a version number.

    terraform --version      # Must be 1.0 or higher
    kubectl version --client # Kubernetes command line tool
    aws --version            # AWS CLI
    docker --version         # Must be running (check Docker Desktop is open)
    python3 --version        # Must be 3.9 or higher
    node --version           # Must be 18 or higher
    git --version

Confirm your AWS credentials are working. This command returns your
account ID, user ID, and ARN. If it fails your credentials are not set.

    aws sts get-caller-identity

Expected output:

    {
        "UserId": "AIDAXXXXXXXXXXXXXXXXX",
        "Account": "388691194728",
        "Arn": "arn:aws:iam::388691194728:user/your-username"
    }

---

## 2. Clone the Repository

Run these commands to clone the project to your local machine:

    cd ~/codeplatoon
    git clone https://github.com/Lumin33r/Capstone-Churn.git
    cd Capstone-Churn
    git checkout main
    git pull origin main
    ls

You should see these folders: terraform/, k8s/, services/, frontend/,
sagemaker/, docs/, and files like docker-compose.yml and README.md.

---

## 3. Environment Variables

The application needs AWS credentials and service URLs configured as
environment variables. These are stored in a .env file that is never
committed to GitHub. It is already listed in .gitignore.

Copy the example file to create your own:

    cp .env.example .env

Open .env and replace every placeholder with your real values:

    AWS_REGION=us-east-1
    AWS_ACCESS_KEY_ID=INSERT_KEY_HERE
    AWS_SECRET_ACCESS_KEY=INSERT_KEY_HERE
    S3_BUCKET=BUCKET_NAME
    SAGEMAKER_ENDPOINT=ENDPOINT_NAME
    SENTIMENT_ENDPOINT_NAME=ENDPOINT_NAME
    MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
    QA_EVALUATOR_URL=http://localhost:8000
    CHURN_PREDICTOR_URL=http://localhost:8001

To find your AWS credentials run:

    cat ~/.aws/credentials

Save the .env file. Never commit it to GitHub.

---

## 4. Terraform Infrastructure Lifecycle

Terraform creates and manages AWS resources automatically using
configuration files. All Terraform commands run from the terraform/ directory.

    cd ~/codeplatoon/capstone/Capstone-Churn/terraform

### What Terraform manages for this project

- S3 bucket (retention-engine-bucket) — stores customer data and model artifacts
- IAM roles — controls what AWS services can access Bedrock and SageMaker
- IAM policies — defines the specific permissions attached to each role
- S3 encryption and versioning — secures stored data

### Remote State Backend

This project uses S3 remote state storage so all teammates share the same
Terraform state file. A DynamoDB table acts as a lock to prevent two people
from running terraform apply at the same time.

The S3 bucket and DynamoDB table must exist before running terraform init.
If they do not exist, create them once with these commands:

    aws s3 mb s3://retention-engine-tf-state --region us-east-1

    aws s3api put-bucket-versioning \
      --bucket retention-engine-tf-state \
      --versioning-configuration Status=Enabled

    aws dynamodb create-table \
      --table-name retention-engine-tf-lock \
      --attribute-definitions AttributeName=LockID,AttributeType=S \
      --key-schema AttributeName=LockID,KeyType=HASH \
      --billing-mode PAY_PER_REQUEST \
      --region us-east-1

    aws dynamodb describe-table \
      --table-name retention-engine-tf-lock \
      --query "Table.TableStatus"

Wait until the output shows "ACTIVE" before continuing.

### 4a. terraform init

Downloads the AWS provider plugin and connects to the remote S3 backend.
Run this once after cloning and again any time backend.tf changes.

    terraform init

Expected output: Terraform has been successfully initialized!

### 4b. terraform validate

Checks configuration files for syntax errors without making any AWS changes.
Run this any time you edit a .tf file.

    terraform validate

Expected output: Success! The configuration is valid.

### 4c. terraform plan

Shows a preview of exactly what Terraform will create, modify, or delete.
No AWS resources are created — this command is completely safe to run.

    terraform plan

Expected output ends with: Plan: 7 to add, 0 to change, 0 to destroy.

### 4d. terraform apply

Creates the actual AWS resources. Type yes when prompted.

    terraform apply

Expected output after completion:

    Apply complete! Resources: 7 added, 0 changed, 0 destroyed.

    Outputs:
    bedrock_role_arn          = "arn:aws:iam::388691194728:role/retention-engine-bedrock-role"
    s3_bucket_arn             = "arn:aws:s3:::retention-engine-bucket"
    s3_bucket_name            = "retention-engine-bucket"
    sagemaker_invoke_role_arn = "arn:aws:iam::388691194728:role/retention-engine-sagemaker-invoke-role"

Share these output values with teammates. They need the ARNs to configure
SageMaker and S3 access.

### 4e. terraform output

Shows output values from the last apply without re-running apply.

    terraform output

### 4f. terraform destroy

Deletes all AWS resources managed by Terraform. This is irreversible.
Confirm with your team before running.

    terraform destroy

Type yes when prompted. Expected output: Destroy complete! Resources: 7 destroyed.

The S3 remote state bucket and DynamoDB lock table are not managed by
Terraform and will not be destroyed automatically. Delete them manually
only when permanently decommissioning the platform:

    aws s3 rb s3://retention-engine-tf-state --force
    aws dynamodb delete-table --table-name retention-engine-tf-lock

---

## 5. Local Development with Docker Compose

Docker Compose runs all four services locally so you can test the full
stack before deploying to EKS. Make sure Docker Desktop is open first.

Return to the project root:

    cd ~/codeplatoon/capstone/Capstone-Churn

Build and start all services:

    docker-compose up --build

The --build flag rebuilds all images from source. Use this after any
code changes. The first run takes several minutes to download base images.

Once running, services are available at:

    Agent Service    http://localhost:8080   LangChain orchestration
    QA Evaluator     http://localhost:8000   Sentiment analysis
    Churn Predictor  http://localhost:8001   Churn probability
    Frontend         http://localhost:3000   React chat interface

Test the agent service health:

    curl http://localhost:8080/health

Expected response: {"status": "healthy", "service": "agent-service"}

Test the chat endpoint:

    curl -X POST http://localhost:8080/chat \
      -H "Content-Type: application/json" \
      -d '{"message": "Analyze this call: Customer is frustrated with billing.", "customer_id": "C00077940"}'

Stop all services when done:

    docker-compose down

---

## 6. Kubernetes EKS Deployment

Kubernetes runs containers in the cloud and keeps them alive automatically.
The class EKS cluster k8s-training-cluster hosts the deployed platform.

### 6a. Connect kubectl to the EKS Cluster

    aws eks update-kubeconfig --region us-east-1 --name k8s-training-cluster

Verify the connection:

    kubectl get nodes

You should see six nodes all showing Ready status.

### 6b. Create the Namespace

A namespace is an isolated space inside the cluster for your team's services.

    kubectl apply -f k8s/namespace.yaml

Expected output: namespace/retention-engine created

### 6c. Apply Resource Quotas

ResourceQuota limits total CPU and memory in the namespace.
LimitRange sets default limits per container.

    kubectl apply -f k8s/namespace-quota.yaml

Expected output:
    resourcequota/retention-engine-quota created
    limitrange/retention-engine-limits created

### 6d. Create AWS Credentials Secret

Services need AWS credentials to call Bedrock and SageMaker from inside
the cluster. Never put credentials in ConfigMaps or YAML files.

    kubectl create secret generic aws-secrets \
      --from-literal=AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id) \
      --from-literal=AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key) \
      --from-literal=AWS_REGION=us-east-1 \
      -n retention-engine

Expected output: secret/aws-secrets created

### 6e. Apply ConfigMaps

    kubectl apply -f k8s/configmaps/

Expected output: configmap/agent-config created

### 6f. Apply Deployments and Services

    kubectl apply -f k8s/deployments/
    kubectl apply -f k8s/services/

### 6g. Verify All Pods are Running

    kubectl get pods -n retention-engine

Allow 1 to 2 minutes for pods to start. Expected healthy pods:

    agent-service       1/1 Running
    frontend            1/1 Running
    qa-evaluator        1/1 Running
    churn-predictor     1/1 Running

### 6h. Get the Public Agent Service URL

    kubectl get service agent-service -n retention-engine

The EXTERNAL-IP column shows the AWS Load Balancer URL.
The agent service is accessible publicly at that URL on port 8080.

Current deployment URL:
    k8s-retentio-agentser-2be767f401-df6dab165e224a2f.elb.us-east-1.amazonaws.com:8080

### 6i. Test a Running Service from Inside the Cluster

    kubectl exec -it deployment/agent-service \
      -n retention-engine -- curl localhost:8080/health

Expected: {"status":"healthy","service":"agent-service"}

### 6j. View Service Logs

    kubectl logs deployment/agent-service -n retention-engine --tail=50
    kubectl logs deployment/churn-predictor -n retention-engine --tail=50
    kubectl logs deployment/qa-evaluator -n retention-engine --tail=50

### 6k. Tear Down the Kubernetes Deployment

Deletes all resources in the namespace. Run only when decommissioning.

    kubectl delete namespace retention-engine

---

## 7. Troubleshooting

### ImagePullBackOff

The cluster cannot pull the Docker image from the registry.

Cause: The CI/CD pipeline has not built and pushed the image yet.

Fix: Ask Troy to trigger the GitHub Actions build pipeline. Check the
Actions tab on GitHub to confirm the workflow ran successfully.

### CrashLoopBackOff

The container starts but Kubernetes keeps restarting it.

Cause: Health probe checking the wrong port, missing environment variable,
or the application crashes on startup.

Fix: Check logs for the exact error:

    kubectl logs deployment/service-name -n retention-engine --tail=50

Check which port the health probe is using:

    kubectl describe deployment service-name -n retention-engine | grep -A 5 "Liveness\|Readiness"

Confirm the port matches what the application actually listens on.

### Terraform State Conflict

Error message: Error acquiring the state lock

Cause: Another teammate is running terraform apply at the same time.

Fix: Wait for the lock to release and retry. If the lock is stuck from
a failed run, manually release it:

    aws dynamodb delete-item \
      --table-name retention-engine-tf-lock \
      --key '{"LockID": {"S": "retention-engine-tf-state/terraform.tfstate"}}'

### Bedrock Access Denied

Error message: AccessDeniedException: User is not authorized to perform bedrock:InvokeModel

Fix: Go to the AWS Bedrock console, navigate to Model access, and confirm
access is granted for Claude Haiku. Verify the IAM role
retention-engine-bedrock-role has the bedrock_invoke_policy attached.

### Pod Stuck in Pending

    kubectl describe resourcequota -n retention-engine

If the namespace quota is exceeded, scale down other deployments first.

---

## 8. Architecture Overview

![System Architecture](architecture_final.png)

    Frontend (React) — port 3000
         |
         | HTTP
         v
    Agent Service (FastAPI + LangChain + Bedrock/Claude) — port 8080
         |                        |
         | HTTP                   | HTTP
         v                        v
    QA Evaluator             Churn Predictor
    Sentiment model          XGBoost model
    SageMaker                SageMaker
    port 8000                port 8001
         |                        |
         +----------+-------------+
                    |
                    v
         S3: retention-engine-bucket
         Customer data, model artifacts

    Infrastructure: Terraform (IAM roles, S3, remote state backend)
    Orchestration:  Kubernetes on k8s-training-cluster EKS
    CI/CD:          GitHub Actions in .github/workflows/
    Namespace:      retention-engine

All services run in the retention-engine namespace on the shared EKS
cluster k8s-training-cluster in us-east-1.

Terraform state is stored in S3 bucket retention-engine-tf-state with
DynamoDB locking via retention-engine-tf-lock.

---

## 9. Team Ownership Reference

| Area                       | Owner    | Key Files                                          |
|----------------------------|----------|----------------------------------------------------|
| Infrastructure (Terraform) | George   | terraform/                                         |
| Kubernetes manifests       | George   | k8s/                                               |
| LangGraph agent            | Kathleen | services/agent-service/                            |
| CI/CD pipelines            | Troy     | .github/workflows/                                 |
| Churn predictor ML         | Kathleen | sagemaker/churn/, services/churn-predictor-api/    |
| Sentiment analysis ML      | Okino    | sagemaker/sentiment/, services/sentiment-analysis-api/ |
| Frontend                   | Kathleen | frontend/                                          |
| Documentation              | All      | docs/                                              |
# 📘 **Capstone‑Churn**

_A cloud‑native, end‑to‑end churn prediction and call‑center analytics platform._

`https://img.shields.io/badge/build-passing-brightgreen`
`https://img.shields.io/badge/python-3.10%2B-blue`
`https://img.shields.io/badge/AWS-SageMaker%20%7C%20EKS-orange`
`https://img.shields.io/badge/Kubernetes-Production--Ready-blue`
`https://img.shields.io/badge/Terraform-IaC-623CE4`
`https://img.shields.io/badge/Docker-Containerized-2496ED`
`https://img.shields.io/badge/license-AGPL--3.0-lightgrey`

---

# 🧠 Overview

**Capstone‑Churn** is a full‑stack, cloud‑native machine learning system designed to:

- Predict customer churn
- Analyze call‑center transcripts
- Detect sentiment, frustration, escalation, and agent behavior
- Provide real‑time insights through a modern frontend
- Deploy ML models to AWS SageMaker
- Run microservices on Kubernetes
- Automate infrastructure with Terraform

This project integrates **ML**, **NLP**, **MLOps**, **DevOps**, and **cloud infrastructure** into a cohesive, production‑ready platform.

---

# 🌟 Features

### 🔍 ML & NLP

- XGBoost churn prediction model
- Transformer‑based sentiment + emotion classifier
- Transcript ingestion + processing pipeline
- Real‑time inference APIs
- Feature engineering + schema validation
- MLflow experiment tracking

### ☁️ Cloud Infrastructure

- AWS SageMaker model deployment
- EKS Kubernetes cluster
- ALB ingress controller
- Terraform‑managed infrastructure
- Lambda‑based transcription pipeline

### 🧩 Microservices

- **agent‑service** (LLM‑powered retention agent)
- **churn‑predictor‑api**
- **sentiment‑analysis‑api**
- **transcribe‑pipeline** (Lambda)
- Backend routing + frontend service

### 🖥️ Frontend

- React + TypeScript + Vite
- Real‑time transcript viewer
- Churn prediction dashboard
- Agent‑assist tools

### 🛠️ Developer Experience

- Dockerized services
- Local development via `docker-compose`
- Kubernetes manifests for all services
- Automated deployment scripts
- Clear IaC separation

---

# 🏗️ Architecture Overview

![System Architecture](docs/architecture_final.png)

```
                        ┌──────────────────────────────┐
                        │          Frontend             │
                        │     (TypeScript + Vite)       │
                        └──────────────┬───────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────────┐
                        │        API Gateway            │
                        │ (K8s Ingress + AWS ALB)       │
                        └──────────────┬───────────────┘
                                       │
       ┌───────────────────────────────┼───────────────────────────────┐
       ▼                               ▼                               ▼
┌──────────────┐              ┌────────────────┐              ┌────────────────┐
│ agent-service│              │ sentiment-api  │              │ churn-api       │
│ (LLM tools)  │              │ (Transformer)  │              │ (XGBoost)       │
└──────────────┘              └────────────────┘              └────────────────┘
       │                               │                               │
       └──────────────┬────────────────┴───────────────┬──────────────┘
                      ▼                                ▼
            ┌────────────────┐                ┌────────────────────┐
            │ transcribe svc │                │  S3 / DynamoDB      │
            │  (Lambda)      │                │  (data storage)     │
            └────────────────┘                └────────────────────┘
```

---

# 🧰 Tech Stack

### **Languages**

- Python
- TypeScript
- Shell
- HCL (Terraform)

### **ML / NLP**

- XGBoost
- PyTorch
- Hugging Face Transformers
- MLflow
- SageMaker SDK

### **Infrastructure**

- AWS (SageMaker, Lambda, S3, EKS, IAM, ALB)
- Kubernetes
- Terraform
- Docker

### **Frontend**

- React + TypeScript
- Vite
- TailwindCSS

---

# 🤖 Model Details

## **1. Churn Prediction Model**

**Location:** `sagemaker/churn/`

### Model Type

- XGBoost classifier
- Trained on customer metadata + behavioral features

### Features

Loaded from `feature_columns.json`:

- Tenure
- Contract type
- Monthly charges
- Payment method
- Support call frequency
- Account flags
- Encoded categorical fields

### Artifacts

- `churn_model.joblib`
- `label_encoders.json`
- `feature_columns.json`

### Deployment

- Packaged via `setup.py`
- Deployed to SageMaker using `deploy.py`
- Served via `churn-predictor-api` microservice

---

## **2. Sentiment + Emotion Model**

**Location:** `sagemaker/sentiment/`

### Model Type

- Fine‑tuned transformer
- Multi‑class classification for:
  - Sentiment
  - Emotion
  - Frustration
  - Escalation
  - Toxicity

### Artifacts

- `sentiment_model.joblib`
- `sentiment_schema.json`
- `sentiment_columns.json`
- `label_encoders.json`
- Tokenized dataset (HF `DatasetDict`)

### Training

- Notebook: `sentiment_training.ipynb`
- Script: `sentiment_training.py`
- MLflow tracking: `mlflow.db`

### Deployment

- Packaged via `requirements.txt`
- Deployed to SageMaker using `deploy.py`
- Served via `sentiment-analysis-api`

---

# ⚡ Quick Start

## 1. Clone the repository

```bash
git clone https://github.com/Lumin33r/Capstone-Churn
cd Capstone-Churn
```

## 2. Local development (Docker Compose)

```bash
docker-compose up --build
```

## 3. Frontend development

```bash
cd frontend
npm install
npm run dev
```

---

# ☁️ Deployment

## 1. Provision AWS Infrastructure (Terraform)

```bash
cd terraform
terraform init
terraform apply
```

Creates:

- EKS cluster
- ALB ingress
- IAM roles
- S3 buckets
- SageMaker endpoints
- Lambda transcription pipeline

---

## 2. Deploy ML Models to SageMaker

```bash
cd sagemaker/churn
python deploy.py

cd ../sentiment
python deploy.py
```

---

## 3. Deploy Microservices to Kubernetes

```bash
kubectl apply -f k8s/
```

---

# 🧪 Testing

### Unit Tests

```bash
pytest
```

### Integration Tests

- API endpoint tests
- Model inference tests
- Lambda local tests (`transcribe-pipeline/test_local.py`)

### Load Testing

- Optional: Locust or K6

---

# 📦 Project Structure

```
Capstone-Churn/
├── frontend/               # UI
├── services/               # Microservices
├── sagemaker/              # ML models + training + deployment
├── k8s/                    # Kubernetes manifests
├── terraform/              # Infrastructure as code
├── scripts/                # Utility scripts
├── docs/                   # Documentation
└── docker-compose.yml      # Local dev
```

---

# 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Follow Conventional Commits
4. Run tests + linting
5. Submit a PR

---

# 🏷️ Versioning

This project uses **Semantic Versioning (SemVer)**:

```
MAJOR.MINOR.PATCH
```

Example:

```
1.3.2
```

---

# 🔐 Security

- Secrets stored in AWS Secrets Manager or Kubernetes Secrets
- IAM least‑privilege roles
- No credentials committed to Git
- Container image scanning recommended

---

# 📄 License

This project is licensed under the **AGPL‑3.0** license.

---

If you'd like, I can also generate:

- A **CONTRIBUTING.md**
- A **CHANGELOG.md**
- A **model card** for each ML model
- A **system architecture diagram (SVG/PNG)**
- A **frontend screenshot section**

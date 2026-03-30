# Capstone Roadmap: Agentic Multi-Service Pipeline

**Team:** Troy, Kathleen, Okino, George

---

## Platform Architecture

```
                            ┌──────────────────────┐
                            │     USER / BROWSER    │
                            └──────────┬───────────┘
                                       │
                            ┌──────────▼───────────┐
                            │   Frontend (React /   │
                            │   Streamlit)          │
                            │   Chat Interface      │
                            └──────────┬───────────┘
                                       │ HTTP
┌──────────────────────────────────────▼────────────────────────────────────┐
│                         EKS Cluster (team namespace)                      │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Backend Service (FastAPI)                                       │    │
│  │  ┌────────────────────────────────────────────────────────┐     │    │
│  │  │  LangChain Agent (Router / Orchestrator)               │     │    │
│  │  │                                                        │     │    │
│  │  │  Tools:                                                │     │    │
│  │  │   • invoke_churn_model  ──▶ Churn Prediction Endpoint  │     │    │
│  │  │   • invoke_transcript   ──▶ Transcript Analysis Endpt  │     │    │
│  │  │   • bedrock_chat        ──▶ Bedrock (Claude)           │     │    │
│  │  └────────────────────────────────────────────────────────┘     │    │
│  │                                                                  │    │
│  │  Routes:                                                         │    │
│  │   POST /chat         ← frontend sends user message              │    │
│  │   GET  /health       ← K8s liveness probe                       │    │
│  │   GET  /ready        ← K8s readiness probe                      │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌─────────────────────┐  ┌─────────────────────┐                       │
│  │ Churn Prediction    │  │ Transcript Analysis  │                       │
│  │ FastAPI Wrapper     │  │ FastAPI Wrapper      │                       │
│  │  /predict  /health  │  │  /predict  /health   │                       │
│  └────────┬────────────┘  └────────┬─────────────┘                       │
│           │                        │                                      │
│  ConfigMaps ─ Secrets ─ Namespaces ─ ResourceQuotas                      │
└───────────┼────────────────────────┼──────────────────────────────────────┘
            │                        │
   ┌────────▼────────┐    ┌─────────▼────────┐    ┌──────────────────┐
   │ SageMaker       │    │ SageMaker        │    │ Amazon Bedrock   │
   │ Endpoint #1     │    │ Endpoint #2      │    │ Claude 3         │
   │ Customer Churn  │    │ Transcript       │    │ (Foundation LLM) │
   │ (XGBoost)       │    │ Classification   │    └──────────────────┘
   └─────────────────┘    └──────────────────┘

INFRA: Terraform (S3, IAM, SageMaker, EKS references)
CI/CD: GitHub Actions → Build → Push GHCR → Deploy to EKS
```

---

## Repo Structure

```
capstone/
├── .github/
│   └── workflows/
│       ├── ci-backend.yml          # Build + push backend image
│       ├── ci-frontend.yml         # Build + push frontend image
│       ├── ci-ml-wrappers.yml      # Build + push ML wrapper images
│       ├── deploy.yml              # kubectl apply to EKS
│       └── terraform.yml           # (bonus) tf plan/apply
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── providers.tf
│   └── modules/                    # (bonus) networking, iam, sagemaker
├── k8s/
│   ├── namespace.yml
│   ├── configmap.yml
│   ├── secrets.yml                 # (template — real values via GH Secrets)
│   ├── backend-deployment.yml
│   ├── backend-service.yml
│   ├── churn-wrapper-deployment.yml
│   ├── churn-wrapper-service.yml
│   ├── transcript-wrapper-deployment.yml
│   ├── transcript-wrapper-service.yml
│   ├── frontend-deployment.yml
│   └── frontend-service.yml
├── backend/
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py                 # FastAPI app, /chat, /health, /ready
│   │   ├── agent.py                # LangChain agent + tool definitions
│   │   ├── tools/
│   │   │   ├── churn_tool.py       # Calls churn-wrapper /predict
│   │   │   ├── transcript_tool.py  # Calls transcript-wrapper /predict
│   │   │   └── bedrock_tool.py     # Bedrock invoke for general chat
│   │   └── config.py               # Env var config
│   └── requirements.txt
├── ml-wrappers/
│   ├── churn/
│   │   ├── Dockerfile
│   │   ├── app.py                  # FastAPI /predict + /health
│   │   └── requirements.txt
│   └── transcript/
│       ├── Dockerfile
│       ├── app.py                  # FastAPI /predict + /health
│       └── requirements.txt
├── sagemaker/
│   ├── churn/
│   │   ├── train.py                # Training script or notebook
│   │   ├── deploy.py               # Endpoint creation script
│   │   └── data/                   # Sample data / data prep scripts
│   └── transcript/
│       ├── train.py
│       ├── deploy.py
│       └── data/
├── frontend/
│   ├── Dockerfile
│   ├── src/                        # React or Streamlit app
│   └── ...
├── docker-compose.yml              # Local dev: all services together
├── docs/
│   ├── architecture.md
│   ├── setup.md
│   ├── deployment.md
│   ├── teardown.md
│   └── llm-usage.md               # How LLMs were used in development
└── README.md
```

---

## Owner Matrix

| Component                   | Primary Owner        | Support                         | Key Deliverables                                    |
| --------------------------- | -------------------- | ------------------------------- | --------------------------------------------------- |
| GitHub Projects / Kanban    | **Troy**             | All                             | Board setup, task cards, sprint tracking            |
| GitHub Actions CI/CD        | **Troy**             | George                          | All `.yml` workflows, secrets config                |
| Dataset identification      | **Kathleen + Okino** | —                               | Churn dataset, transcript dataset                   |
| SageMaker training + deploy | **Kathleen + Okino** | —                               | `sagemaker/` training scripts, live endpoints       |
| ML FastAPI wrappers         | **Kathleen + Okino** | Troy (CI)                       | `ml-wrappers/` services with `/predict` + `/health` |
| Terraform infra             | **George**           | Troy (CI)                       | `terraform/` — IAM, S3, SageMaker resources         |
| Kubernetes manifests        | **George**           | Troy (deploy wf)                | `k8s/` — all manifests                              |
| LangChain agent + Bedrock   | **George**           | Kathleen/Okino (tool contracts) | `backend/app/agent.py`, tool definitions            |
| Backend FastAPI service     | **George**           | All                             | `backend/` — routes, agent wiring                   |
| Frontend chat UI            | **All**              | —                               | `frontend/` — chat interface                        |
| Documentation + diagrams    | **All**              | —                               | `docs/`, `README.md`                                |

---

## Phased Roadmap

### Phase 1: Foundation (Days 1–2)

> Goal: Repo structure, one vertical slice working end-to-end locally.

```
Troy                    Kathleen/Okino              George
─────                   ──────────────              ──────
Set up GitHub repo      Find + validate churn       Write Terraform for
  with branch rules       dataset (CSV)               S3 bucket + IAM role

Create GitHub Projects  Find + validate transcript  Scaffold k8s/ namespace
  Kanban board            dataset                     + configmap templates

Scaffold .github/       Scaffold sagemaker/churn/   Scaffold backend/ with
  workflows/ stubs        with train.py notebook      FastAPI hello world

Create docker-compose   Set up local dev env        Write first Dockerfile
  .yml skeleton                                       for backend

ALL: Agree on API contracts between services
     ─────────────────────────────────────────
     Churn wrapper:    POST /predict  { features: [...] } → { churn_prob: 0.82 }
     Transcript wrapper: POST /predict  { text: "..." }   → { category: "...", sentiment: "..." }
     Backend:          POST /chat     { message: "..." }  → { response: "..." }
```

**Milestone:** Every team member can run `docker-compose up` and hit the backend `/health` endpoint.

---

### Phase 2: Core Services (Days 3–5)

> Goal: ML endpoints live, agent wired, CI green.

```
Troy                        Kathleen/Okino                George
─────                       ──────────────                ──────
CI workflow: build +        Train churn model in          Terraform apply:
  push backend image          SageMaker, deploy             provision cloud
  to GHCR                    endpoint                      resources

CI workflow: build +        Train transcript model,       Write LangChain agent
  push ML wrapper             deploy endpoint               with tool definitions:
  images                                                    • churn_tool
                                                            • transcript_tool
CI workflow: build +        Build FastAPI wrappers          • bedrock_tool
  push frontend image         for both endpoints
                              (churn/ + transcript/)      Wire agent into
Add verification step                                       backend /chat route
  (health check) to        Write Dockerfiles for
  each workflow               each wrapper                Write k8s deployments
                                                            + services for all
                                                            containers
```

**Milestone:** From local, you can POST to `/chat` with "Will this customer churn?" and the agent calls the churn endpoint and returns a response.

---

### Phase 3: Infrastructure + Deploy (Days 5–7)

> Goal: Everything running on Kubernetes, CI/CD deploys automatically.

```
Troy                        Kathleen/Okino                George
─────                       ──────────────                ──────
Deploy workflow:            Harden ML wrappers:           Deploy to Minikube/EKS:
  kubectl apply               retry logic,                 kubectl apply -f k8s/
  triggered on merge           error handling
  to main                                                Add ConfigMaps +
                            Test endpoints under            Secrets for env vars
Add rollback step             load, verify                  (endpoint URLs,
  to deploy workflow          CloudWatch logs                AWS creds)

Set up branch-based                                      Add health probes to
  targeting (staging                                        all deployments
  vs prod)                                                 (liveness + readiness)

                                                         Verify Bedrock access
                                                           from inside cluster
```

**Milestone:** Push to `main` triggers build → push → deploy. All pods healthy in cluster. Chat works via LoadBalancer URL.

---

### Phase 4: Frontend + Polish (Days 7–9)

> Goal: Chat UI live, full pipeline working, docs complete.

```
Troy                        Kathleen/Okino                George
─────                       ──────────────                ──────
Wire frontend CI/CD         Help build chat UI            Help build chat UI

Ensure all workflows        Add model versioning          (Bonus) Add
  pass on main                or 3rd endpoint               conversation memory

Final Kanban cleanup:       Write docs:                   Write docs:
  all cards resolved          ML approach,                  architecture diagram,
                              data decisions,               infra setup,
Write docs:                   LLM usage log                 deployment steps
  CI/CD setup guide,
  teardown steps                                          Write teardown docs
                                                            (terraform destroy,
                                                             kubectl delete)
```

**Milestone:** Demo-ready. Clone → follow docs → full deployment reproducible.

---

## Interface Contracts

Define these early so everyone can work in parallel.

### Churn Wrapper → SageMaker Endpoint

```
POST /predict
Request:  { "features": [0.5, 1.0, 3, 45.2, ...] }
Response: { "churn_probability": 0.82, "prediction": "churn" }

GET /health
Response: { "status": "healthy", "endpoint": "churn-endpoint-v1" }
```

### Transcript Wrapper → SageMaker Endpoint

```
POST /predict
Request:  { "text": "I've been waiting for 30 minutes and nobody..." }
Response: { "category": "complaint", "sentiment": "negative", "confidence": 0.91 }

GET /health
Response: { "status": "healthy", "endpoint": "transcript-endpoint-v1" }
```

### Backend /chat → Frontend

```
POST /chat
Request:  { "message": "What's the churn risk for customer 4521?" }
Response: { "response": "Based on the model prediction, customer 4521 has a 82% churn probability..." }

GET /health
Response: { "status": "healthy", "agent": "ready", "tools": ["churn", "transcript", "bedrock"] }
```

---

## LangChain Agent Design

```python
# Simplified agent structure — George owns, Kathleen/Okino define tool I/O

tools = [
    # Tool 1: Churn prediction
    #   Input: customer feature vector
    #   Action: POST to churn-wrapper-service:8000/predict
    #   Output: churn probability + label

    # Tool 2: Transcript analysis
    #   Input: raw text from service call
    #   Action: POST to transcript-wrapper-service:8000/predict
    #   Output: category + sentiment + confidence

    # Tool 3: Bedrock general chat
    #   Input: user message (when no tool needed)
    #   Action: bedrock invoke_model (Claude 3)
    #   Output: conversational response
]

# Agent routes based on user intent:
#   "Will customer X churn?"     → churn tool
#   "Analyze this transcript..." → transcript tool
#   "What can you help with?"    → bedrock general chat
#   Complex queries              → chain multiple tools
```

---

## CI/CD Pipeline Overview

```
Feature Branch Push          Merge to Main
────────────────────         ─────────────────────────────

  ┌──────────────┐             ┌──────────────┐
  │ Lint + Test  │             │ Build Images │
  └──────┬───────┘             └──────┬───────┘
         │                            │
         ▼                     ┌──────▼───────┐
    PR Status Check            │ Push to GHCR │
                               └──────┬───────┘
                                      │
                               ┌──────▼───────┐
                               │ kubectl apply│
                               │ -f k8s/      │
                               └──────┬───────┘
                                      │
                               ┌──────▼───────┐
                               │ Health Check │
                               │ (verify pods)│
                               └──────────────┘
```

**Workflows (Troy owns):**

| File                 | Trigger                  | What It Does                           |
| -------------------- | ------------------------ | -------------------------------------- |
| `ci-backend.yml`     | push to `backend/**`     | Build + push backend image             |
| `ci-ml-wrappers.yml` | push to `ml-wrappers/**` | Build + push both wrapper images       |
| `ci-frontend.yml`    | push to `frontend/**`    | Build + push frontend image            |
| `deploy.yml`         | merge to `main`          | `kubectl apply -f k8s/` + health check |
| `terraform.yml`      | (bonus) manual trigger   | `tf plan` on PR, `tf apply` on merge   |

---

## Kubernetes Layout

```
Namespace: team-<name>
│
├── backend-deployment        (2 replicas)
│   └── backend-service       (ClusterIP or LoadBalancer)
│
├── churn-wrapper-deployment  (1 replica)
│   └── churn-wrapper-service (ClusterIP)
│
├── transcript-wrapper-deployment (1 replica)
│   └── transcript-wrapper-service (ClusterIP)
│
├── frontend-deployment       (1 replica)
│   └── frontend-service      (LoadBalancer → public)
│
├── configmap                 (endpoint URLs, region, model names)
└── secret                    (AWS creds — injected via GH Actions)
```

All inter-service calls stay **inside the cluster** (ClusterIP). Only the frontend service gets a LoadBalancer for public access. The backend talks to ML wrappers via K8s DNS (`churn-wrapper-service.team-<name>.svc.cluster.local:8000`).

---

## Scoring Checklist

| Area (10% each)         | Key Requirements                                                         | Owner            |
| ----------------------- | ------------------------------------------------------------------------ | ---------------- |
| **Containers**          | Multi-stage Dockerfiles, GHCR push, docker-compose, no hardcoded secrets | Troy + All       |
| **Terraform**           | Provision resources, variables/outputs, documented lifecycle             | George           |
| **CI/CD**               | Build→push→deploy workflow, GH Secrets, health check verification        | Troy             |
| **LangChain Agent**     | Route requests, invoke tools, multi-step reasoning                       | George           |
| **Bedrock + Frontend**  | Chat UI, Bedrock as LLM, agent invokes ML endpoints                      | All              |
| **SageMaker Endpoints** | 2 endpoints, FastAPI wrappers, /health + /predict                        | Kathleen + Okino |
| **Kubernetes**          | Namespace, ConfigMaps, Secrets, health probes                            | George           |
| **Collaboration**       | Kanban board, feature branches, PRs, task ownership                      | Troy + All       |
| **Presentation + Docs** | Architecture diagram, setup/deploy/teardown docs                         | All              |
| **LLM Usage**           | Document where/how LLMs used, critical evaluation                        | All              |

---

## Parallel Work Strategy

The key to speed: **everyone works simultaneously from Day 1**.

```
                    Troy         Kathleen/Okino       George
                    ────         ──────────────       ──────
Week 1 Focus:       CI/CD        ML Models            Infra + Agent
                    Repo         Datasets             Terraform
                    Workflows    SageMaker Train      K8s Manifests
                                 FastAPI Wrappers     LangChain

Week 2 Focus:       Frontend     Frontend             Frontend
                    Final CI     Hardening             Deploy to EKS
                    Docs         Docs                  Docs
```

**Integration points** (where people need to sync):

1. **API contracts** — agree on request/response shapes before coding (Day 1)
2. **Docker image names** — Troy needs image paths for CI, George needs them for K8s
3. **Endpoint URLs** — Kathleen/Okino provide SageMaker endpoint names, George puts them in ConfigMaps
4. **Secrets** — Troy sets up GH Secrets, George references them in K8s Secrets

---

## Quick Wins for Bonus Points

| Bonus                                  | Effort | Who                    |
| -------------------------------------- | ------ | ---------------------- |
| Alpine/slim Docker images              | Low    | Troy                   |
| Remote Terraform state (S3 + DynamoDB) | Low    | George                 |
| Separate CI workflows per service      | Low    | Troy (already in plan) |
| LangSmith tracing                      | Medium | George                 |
| Conversation memory                    | Medium | George + Frontend dev  |
| 3rd SageMaker endpoint                 | Medium | Kathleen/Okino         |
| Polished UI (Tailwind/MUI)             | Medium | Frontend dev           |
| HPA (auto-scaling)                     | Low    | George                 |
| Polly/Transcribe integration           | Medium | Anyone                 |
| LLM usage comparison doc               | Low    | All                    |

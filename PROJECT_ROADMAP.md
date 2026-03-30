# The Retention Engine — Project Roadmap

## Team Roles

Each team member owns a primary lane. Everyone contributes across lanes, but ownership prevents gaps.

| Person | Primary Ownership | Responsibilities |
|--------|------------------|-----------------|
| **Troy** | Git & CI/CD | GitHub Projects Kanban board, GitHub Actions workflows (`.github/workflows/`), branch protection, repo setup |
| **Okino** | ML/Data Science (Endpoint 1) | Dataset identification (transcripts/sentiment), SageMaker QA Evaluator training & deployment, FastAPI wrapper |
| **Kathleen** | ML/Data Science (Endpoint 2) | Dataset identification (churn), SageMaker Churn Predictor training & deployment, FastAPI wrapper |
| **George** | Infrastructure & Agentic | Terraform configs, K8s manifests, LangChain/Bedrock integration, agentic harness |

| Shared | Owner |
|--------|-------|
| **Frontend Development** | All (TBD who wires final integration) |
| **Documentation** | All (end of project) |
| **LLM Usage Docs** | Each member individually |

---

## Graded Areas → Lane Mapping

| # | Graded Area (10% each) | Primary Owner | Supporting |
|---|----------------------|--------------|------------|
| 1 | Containers & Dockerfiles | George (writes Dockerfiles for infra), Kathleen/Okino (write Dockerfiles for their services) | Troy (CI builds) |
| 2 | Terraform Provisioning | George | — |
| 3 | CI/CD with GitHub Actions | Troy | All contribute workflows |
| 4 | LangChain Agentic Harness | George | Kathleen, Okino (endpoint integration) |
| 5 | Bedrock Chat Agent & Frontend | George (Bedrock/agent), All (frontend) | — |
| 6 | SageMaker ML Endpoints | Okino (Endpoint 1: QA Evaluator), Kathleen (Endpoint 2: Churn Predictor) | George (integration) |
| 7 | Kubernetes Orchestration | George | Troy (CI/CD deploy steps) |
| 8 | Team Collaboration & Agile | Troy (board setup), All (participation) | — |
| 9 | Presentation & Documentation | All | — |
| 10 | Leveraging LLMs as Dev Tools | All (individual docs) | — |

---

## Phase Overview

```
Phase 0: Setup & Planning          ██░░░░░░░░░░░░░░  (Days 1-2)
Phase 1: Vertical Slice            ████░░░░░░░░░░░░  (Days 3-6)
Phase 2: Full Build-Out            ████████░░░░░░░░  (Days 7-12)
Phase 3: Integration & Hardening   ██████████░░░░░░  (Days 13-16)
Phase 4: Polish & Present          ████████████████  (Days 17-20)
```

---

## Phase 0 — Setup & Planning (Days 1–2)

**Goal:** Repo structure, tooling, Kanban board, and team alignment. Nothing is built yet — everything is scaffolded.

### Troy — Git & CI/CD Setup
- [ ] Set up GitHub Projects Kanban board with columns: `Backlog`, `In Progress`, `In Review`, `Done`
- [ ] Create all tasks from this roadmap as GitHub Issues and assign owners
- [ ] Set branch protection on `main` (require PR + 1 approval)
- [ ] Agree on branch naming convention with team (e.g., `feat/<owner>-<description>`, `fix/...`)
- [ ] Scaffold `.github/workflows/` with placeholder workflow files

### All Team Members
- [ ] Each member documents their LLM setup (which tools, how they're using them) in `docs/llm-usage/`

### George — Infrastructure & Agentic
- [ ] Scaffold `terraform/` directory structure:
  ```
  terraform/
  ├── main.tf
  ├── variables.tf
  ├── outputs.tf
  ├── providers.tf
  ├── backend.tf          # S3 remote state (bonus)
  └── modules/            # (bonus) networking, compute, sagemaker
  ```
- [ ] Identify which AWS resources are pre-existing (shared VPC, EKS cluster, IAM roles) vs. need provisioning
- [ ] Scaffold `k8s/` directory structure:
  ```
  k8s/
  ├── namespace.yaml
  ├── configmaps/
  ├── secrets/
  ├── deployments/
  └── services/
  ```
- [ ] Create initial `docker-compose.yml` for local dev
- [ ] Scaffold `services/agent-service/`:
  ```
  services/
  └── agent-service/
      ├── app.py           # FastAPI + LangChain
      ├── chains/
      ├── tools/
      ├── Dockerfile
      └── requirements.txt
  ```
- [ ] Verify Bedrock model access in `us-east-1`
- [ ] Decide: Minikube for local dev → EKS for production? Or EKS only?

### Okino — ML Endpoint 1 (QA Evaluator)
- [ ] Download sentiment dataset from Kaggle ("Customer Support on Twitter" or "Amazon Reviews")
- [ ] Scaffold `sagemaker/endpoint1-qa-evaluator/`:
  ```
  sagemaker/endpoint1-qa-evaluator/
  ├── train.py (or notebook)
  └── deploy.py
  services/qa-evaluator-api/
  ├── app.py           # FastAPI
  ├── Dockerfile
  └── requirements.txt
  ```
- [ ] Begin data exploration and preprocessing

### Kathleen — ML Endpoint 2 (Churn Predictor)
- [ ] Download "Telco Customer Churn" (IBM) dataset from Kaggle
- [ ] Scaffold `sagemaker/endpoint2-churn-predictor/`:
  ```
  sagemaker/endpoint2-churn-predictor/
  ├── train.py (or notebook)
  └── deploy.py
  services/churn-predictor-api/
  ├── app.py           # FastAPI
  ├── Dockerfile
  └── requirements.txt
  ```
- [ ] Begin data exploration and preprocessing

### Kathleen & Okino (Together)
- [ ] Create synthetic Customer ID mapping between the two datasets
- [ ] Decide frontend framework: React (more polished, bonus points) or Streamlit (faster to build)
- [ ] Scaffold `frontend/` directory

### Repo Structure After Phase 0
```
Capstone-Churn/
├── .github/
│   └── workflows/           # CI/CD pipelines
├── terraform/               # IaC
├── k8s/                     # Kubernetes manifests
├── sagemaker/               # Training notebooks & deploy scripts
├── services/
│   ├── qa-evaluator-api/    # FastAPI wrapper for Endpoint 1
│   ├── churn-predictor-api/ # FastAPI wrapper for Endpoint 2
│   └── agent-service/       # LangChain orchestration service
├── frontend/                # Chat UI
├── docs/
│   ├── architecture/        # Diagrams
│   ├── llm-usage/           # LLM documentation per member
│   └── setup.md             # Reproduction steps
├── docker-compose.yml
├── PROJECT_ROADMAP.md
└── README.md
```

---

## Phase 1 — Vertical Slice (Days 3–6)

**Goal:** One end-to-end path working: a single ML endpoint → FastAPI wrapper → LangChain agent can call it → basic chat UI can trigger it. This proves the architecture before building everything out.

### George — Terraform & K8s Foundation
- [ ] Write Terraform for core resources:
  - S3 bucket (audio/data storage)
  - IAM roles for SageMaker execution and Bedrock access
  - Reference existing VPC/EKS (use `data` sources or `terraform import`)
- [ ] `terraform init` + `plan` + `apply` — document the lifecycle in `docs/setup.md`
- [ ] Set up remote state with S3 + DynamoDB locking (bonus)
- [ ] Write initial K8s manifests for the QA evaluator service:
  - `namespace.yaml` (use team name, e.g., `retention-engine`)
  - `deployment.yaml` with health probes (readiness + liveness)
  - `service.yaml`
  - `configmap.yaml` for env vars
- [ ] Deploy to Minikube, verify `/health` responds

### George — LangChain Agent (First Tool)
- [ ] Create a LangChain `Tool` that calls the QA Evaluator `/predict` endpoint
- [ ] Wire it into a basic agent with Bedrock as the LLM backbone
- [ ] Test: agent receives "Analyze this call transcript: ..." → invokes QA tool → returns result

### Okino — QA Evaluator Endpoint
- [ ] **Train and deploy Endpoint 1:**
  - Preprocess sentiment dataset (tokenize, label encode)
  - Train DistilBERT/RoBERTa text classifier in SageMaker notebook
  - Deploy to SageMaker endpoint
  - Verify: `aws sagemaker describe-endpoint --endpoint-name qa-evaluator`
- [ ] **FastAPI wrapper for Endpoint 1:**
  - `POST /predict` — accepts `{"text": "..."}`, returns `{"qa_score": 7, "sentiment": "Frustrated"}`
  - `GET /health` — returns `{"status": "healthy"}`
  - Invoke SageMaker endpoint from FastAPI using `boto3`
- [ ] Write Dockerfile for `qa-evaluator-api` (multi-stage build, slim base)
  - `.dockerignore` for optimization, health check in Dockerfile
- [ ] Test end-to-end: `curl localhost:8000/predict -d '{"text": "I am very upset"}'`

### Kathleen — Churn Predictor Endpoint (Parallel with Okino)
- [ ] **Begin training Endpoint 2** (will complete in Phase 2, but start data prep and initial training now)
  - Preprocess Telco Churn dataset (encode categoricals, scale numerics)
  - Begin XGBoost/LightGBM model training in SageMaker notebook

### Troy — First CI/CD Pipeline
- [ ] **First GitHub Actions workflow:**
  - On push to `main`: build Docker image → push to GHCR or DockerHub
  - Use `docker/build-push-action`
  - Use GitHub Secrets for registry credentials
  - Add a health check step (curl the built container)

### Frontend — Basic Chat (All, TBD wiring)
- [ ] Minimal Streamlit or React app with a text input and response display
- [ ] Connects to the agent service API
- [ ] Verify: type a message → get a response that includes QA analysis

### Milestone Check ✓
> Can a user type a call transcript into the chat UI, have the LangChain agent analyze it via the QA Evaluator endpoint, and return a sentiment score? If yes, Phase 1 is complete.

---

## Phase 2 — Full Build-Out (Days 7–12)

**Goal:** All services built, all endpoints live, full agentic pipeline working. This is the heavy lifting phase.

### George — Infrastructure Expansion
- [ ] Add Terraform resources for:
  - SageMaker endpoint configurations (if not manually deployed)
  - Any additional S3 buckets, IAM policies
  - ECR repositories (if using ECR instead of GHCR)
- [ ] Modularize Terraform (bonus): separate `modules/networking`, `modules/compute`, `modules/sagemaker`
- [ ] Document all outputs: endpoint URLs, bucket names, role ARNs
- [ ] Write `terraform destroy` teardown instructions

### George — K8s Full Stack & Dockerfiles
- [ ] Write Dockerfiles for `agent-service` and `frontend` (multi-stage builds + slim bases + health checks)
- [ ] Update `docker-compose.yml` for full local stack (all 4 services)
- [ ] Write K8s manifests for all services:
  - Deployments with health probes for each service
  - Services (ClusterIP for internal, LoadBalancer for frontend)
  - ConfigMaps for non-sensitive config
  - Secrets for AWS credentials, API keys
- [ ] Add resource management (bonus):
  - `ResourceQuota` and `LimitRange` per namespace
  - Rolling update strategy in deployments
- [ ] Deploy full stack to Minikube, test service-to-service communication

### Kathleen — Churn Predictor Endpoint (Complete)
- [ ] **Finish Endpoint 2 (Churn Predictor) — train and deploy:**
  - Complete XGBoost/LightGBM model training in SageMaker
  - Deploy to SageMaker endpoint
- [ ] **FastAPI wrapper for Endpoint 2:**
  - `POST /predict` — accepts `{"qa_score": 7, "contract_length": 12, "monthly_bill": 89.50, "support_calls": 4}`
  - Returns `{"churn_probability": 0.82, "risk_level": "HIGH"}`
  - `GET /health`
- [ ] Write Dockerfile for `churn-predictor-api` (multi-stage build, slim base)

### Kathleen & Okino — Cross-Model Integration
- [ ] Create the Customer ID mapping logic
- [ ] Test pipeline: transcript → QA score → combine with account data → churn probability
- [ ] Add production hardening (bonus):
  - Retry logic on SageMaker invocations
  - Error handling and fallback responses
  - Model versioning

### George — Full Agentic Pipeline
- [ ] **Full LangChain agent with multiple tools:**
  - Tool 1: `analyze_call` → calls QA Evaluator endpoint (Okino's service)
  - Tool 2: `predict_churn` → calls Churn Predictor endpoint (Kathleen's service)
  - Tool 3: `get_customer_info` → retrieves account metadata (can be mocked or from a simple DB)
  - Implement conditional routing: if churn risk > 0.7, trigger retention recommendation
- [ ] **Multi-step agentic workflow:**
  - Agent receives transcript → calls QA tool → gets score → calls churn tool with score + account data → if high risk, asks Bedrock to generate retention offer
  - This satisfies: "non-trivial agentic behavior" + "multi-step reasoning" + "tool use"
- [ ] **LangGraph workflow (bonus):**
  - Model the above as a state graph with conditional edges
- [ ] **LangSmith integration (bonus):**
  - Enable `LANGCHAIN_TRACING_V2=true`
  - Document trace examples in `docs/`

### Frontend — Manager's Command Center (All, TBD wiring)
- [ ] Chat interface for interacting with the agent
- [ ] Display: QA Score, Sentiment, Churn Probability, Retention Recommendation
- [ ] "High Risk" leaderboard or dashboard panel
- [ ] Conversation memory / context persistence (bonus)
- [ ] Polish with Tailwind/MUI (bonus)

### Troy — CI/CD Expansion
- [ ] **Expand GitHub Actions:**
  - Workflow per service: build → test → push to registry
  - Infrastructure workflow: `terraform plan` on PR, `terraform apply` on merge to main (bonus)
  - Deployment workflow: `kubectl apply` to EKS after image push
  - Branch-based targeting (bonus): deploy to staging on `develop`, production on `main`
- [ ] Add verification steps:
  - Health check after deployment
  - Rollout status check: `kubectl rollout status deployment/<name>`
  - Smoke test: curl the `/health` endpoints

---

## Phase 3 — Integration & Hardening (Days 13–16)

**Goal:** Everything deployed to EKS, CI/CD fully automated, cross-service communication verified, edge cases handled.

### All — Integration Testing
- [ ] Deploy full stack to EKS cluster
- [ ] Test end-to-end flow from frontend through all services
- [ ] Verify all health probes are passing: `kubectl get pods -n retention-engine`
- [ ] Test CI/CD: push a change → watch it build → deploy → verify
- [ ] Fix any networking/CORS/DNS issues between services

### George — Infrastructure Hardening
- [ ] Verify all Terraform state is clean and reproducible
- [ ] Test full lifecycle: `destroy` → `init` → `plan` → `apply`
- [ ] Ensure no hardcoded credentials anywhere
- [ ] Add HPA (Horizontal Pod Autoscaler) for high-traffic services (bonus)
- [ ] Add persistent storage if needed (bonus)
- [ ] Verify all containers use env vars, not hardcoded secrets
- [ ] Test: `kubectl exec <pod> -- curl localhost:8000/health` for each service

### Kathleen & Okino — ML Endpoint Validation
- [ ] Verify both SageMaker endpoints are stable and responding
- [ ] Load test the FastAPI wrappers
- [ ] Ensure model invocations work from inside K8s pods

### George — Agentic & Frontend Validation
- [ ] Verify Bedrock access from inside the cluster
- [ ] Test full agent workflow from the deployed frontend
- [ ] Verify conversation memory works across sessions

### Bonus Integrations
- [ ] Amazon Transcribe pipeline: S3 audio upload → Transcribe → feed transcript to agent (bonus)
- [ ] Amazon Polly: text-to-speech for agent responses (bonus)

---

## Phase 4 — Polish & Present (Days 17–20)

**Goal:** Documentation complete, presentation rehearsed, everything demo-ready.

### Documentation (All Members)
- [ ] **README.md** — project overview, team members, quick start
- [ ] **docs/setup.md** — full reproduction steps (clone → provision → deploy → test → teardown)
- [ ] **docs/architecture/** — at least one architecture diagram:
  - System-level diagram showing all services and data flow
  - Deployment pipeline diagram
  - (Bonus) C4 diagrams, sequence diagrams
- [ ] **docs/llm-usage/** — each member documents:
  - Which LLM tools they used
  - Specific examples of code generation, debugging, architecture planning
  - Critical evaluation: what they accepted, rejected, or modified
  - (Bonus) comparison of LLM-generated vs hand-written code

### Presentation Prep
- [ ] Assign presentation sections — each member covers their area
- [ ] Suggested structure:
  1. **Business Problem & Architecture Overview** — any member (2 min)
  2. **Infrastructure & Terraform** — George (3 min)
  3. **CI/CD & Git Workflow** — Troy (3 min)
  4. **ML Endpoints & Data Pipeline** — Kathleen & Okino (3 min)
  5. **Agentic Layer, Bedrock, K8s & Frontend** — George (3 min)
  6. **Live Demo** — all (3 min)
  7. **LLM Usage & Lessons Learned** — all (2 min)
- [ ] Rehearse at least once as a team
- [ ] Prepare for Q&A on any section

### Final Checks
- [ ] GitHub Projects board is up to date with task history
- [ ] All PRs have descriptions and at least one review
- [ ] Commit history shows contributions from all members
- [ ] No AWS credentials in the repo (scan with `git log --all -p | grep -i "AKIA"`)
- [ ] All services healthy on EKS
- [ ] CI/CD pipelines green

---

## Bonus Points Checklist

Quick reference for all bonus opportunities across the rubric:

| Area | Bonus Item | Difficulty |
|------|-----------|------------|
| Containers | Alpine/slim bases, health checks, `.dockerignore` | Low |
| Terraform | Remote state with S3/DynamoDB | Medium |
| Terraform | Modular structure (separate modules) | Medium |
| CI/CD | Separate infra vs app workflows | Medium |
| CI/CD | Branch targeting, rollback, multi-workflow chaining | Medium |
| LangChain | LangGraph workflows | Medium |
| LangChain | LangSmith observability | Low |
| Bedrock/Chat | Conversation memory persistence | Medium |
| Bedrock/Chat | Polished UI (Tailwind/MUI) | Medium |
| SageMaker | Third endpoint or model versioning | High |
| SageMaker | Retry logic, error handling, fallback | Medium |
| K8s | ResourceQuota + LimitRange | Low |
| K8s | HPA, persistent storage, rolling updates | Medium |
| Collaboration | Sprint artifacts, retro notes, standup docs | Low |
| Collaboration | Code review comments on PRs | Low |
| Presentation | C4/sequence diagrams | Medium |
| Presentation | Present early | Low |
| LLM Usage | Compare LLM vs hand-written code | Medium |
| LLM Usage | Document prompt engineering techniques | Low |
| Extra | AWS Transcribe/Polly integration | High |
| Extra | Blog articles, MkDocs, video series | High |
| Extra | Portfolio page integration | High |

---

## Daily Standup Template

Use this in your team channel or standup meetings:

```
**Name:**
**Yesterday:** What I completed
**Today:** What I'm working on
**Blockers:** Anything stopping progress
**LLM Note:** How I used LLM tools today (for documentation)
```

---

## Key Principles

1. **Vertical slice first** — get one path working end-to-end before expanding
2. **Parallel lanes** — infrastructure and application work happen simultaneously
3. **Feature branches always** — never commit directly to `main`
4. **Document as you go** — don't leave it all for Phase 4
5. **Log your LLM usage** — it's 10% of the grade, treat it seriously
6. **Test locally before deploying** — Docker Compose and Minikube first, EKS second
7. **Reuse prior work** — FastAPI services, K8s manifests, Terraform configs from earlier modules are fair game

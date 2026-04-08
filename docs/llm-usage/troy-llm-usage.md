# LLM Usage Log — Troy

**Tool:** GitHub Copilot (Claude Opus 4.6, VS Code Chat)
**Period:** April 7, 2026

---

## Summary

Used GitHub Copilot as a pair programming partner for CI/CD pipeline design, workflow implementation, documentation updates, observability research, and codebase analysis. All output was reviewed and adapted to fit the project's actual architecture — not blindly accepted.

---

## Task Log

### 1. Codebase Deep-Dive — Agent Memory & LangGraph

**What I asked:** Explain how memory works in `retention_agent.py`.

**LLM output:** Walked through `InMemoryChatMessageHistory`, `get_session_history()`, `RunnableWithMessageHistory`, and per-request flow. Explained how session IDs map to isolated conversation histories and how the callback chain wires it together.

**My evaluation:** Accurate explanation of the codebase. Helped me understand the agent layer I don't own so I can write CI/CD that tests it properly.

---

### 2. CAPSTONE-CHURN-WALKTHROUGH.md Update

**What I asked:** Update the walkthrough doc to reflect LangGraph migration, LangSmith observability, and K8s cluster structure.

**LLM output:**

- Read `retention_graph.py`, `app.py`, `requirements.txt`, `.env.example`, and all K8s manifests via subagent
- Applied 5 edits: updated architecture diagram with LangSmith, rewrote Section 1 for LangGraph, added K8s cluster ASCII diagram + manifest inventory table, updated technology summary, updated quick start

**My evaluation:** Good structural changes. The K8s diagram accurately reflected our 7 deployments, 3 services, and resource quotas. Accepted as-is.

---

### 3. CI/CD Strategy Design — 6 Design Documents

**What I asked:** Design a CI/CD strategy with manual triggers, correct ordering (infra before app), post-merge E2E testing, and SageMaker endpoint validation.

**LLM output:** Created 6 design docs in `CAPSTONE/docs/`:

- `cicd-overview.md` — Master pipeline map, execution order, required secrets
- `cicd-terraform.md` — Terraform workflow spec with YAML skeleton
- `cicd-sagemaker-deploy.md` — SageMaker deploy with health checks + inference validation
- `cicd-deploy.md` — Docker build → GHCR → EKS rollout
- `cicd-post-merge.md` — Automatic post-merge validation pipeline
- `cicd-test-strategy.md` — Test pyramid with unit test examples per service

**My evaluation:** The design docs gave me a clear reference before implementation. The execution ordering (terraform → sagemaker → deploy) was correct. The workflow_dispatch approach for infra was the right call — you don't want infra changes running automatically on every push.

---

### 4. GitHub Actions Workflow Implementation

**What I asked:** Implement the 6 workflows from the design docs into `.github/workflows/`.

**LLM output:**

- Deleted 3 empty placeholder files: `ci-backend.yml`, `ci-frontend.yml`, `ci-ml-wrappers.yml`
- Created/overwrote 4 workflow files following the design doc skeletons
- Left `slack-pr-events.yml` untouched

**Final workflows:**

| File                   | Trigger             | Key Features                                                                                  |
| ---------------------- | ------------------- | --------------------------------------------------------------------------------------------- |
| `terraform.yml`        | `workflow_dispatch` | plan/apply input, environment selection (dev/staging/prod)                                    |
| `sagemaker-deploy.yml` | `workflow_dispatch` | endpoint selection, deploy/delete, health polling, inference validation                       |
| `deploy.yml`           | `workflow_dispatch` | service selection, matrix Docker build, GHCR push, kubectl apply, rollout restart, smoke test |
| `ci-post-merge.yml`    | `push` to `main`    | Unit tests (matrix), Docker build check, SageMaker health, E2E smoke test via docker-compose  |
| `slack-pr-events.yml`  | PR open/close       | Slack webhook notification                                                                    |

**My evaluation:** The workflows matched the design docs. Matrix strategy for Docker builds was efficient. The E2E smoke test job in `ci-post-merge.yml` (spins up docker-compose, hits `/chat` and `/high-risk`) was a strong addition.

**Issue encountered:** First run of `ci-post-merge.yml` failed with `Error: Input required and not supplied: aws-region` — the `AWS_REGION` secret wasn't set in GitHub. Fixed by running `gh secret set AWS_REGION --body "us-east-1"`.

---

### 5. LangSmith Observability — Teaching Session

**What I asked:** Teach me how LangSmith creates observability and how it differs from OpenTelemetry. Use code examples from Capstone-Churn.

**LLM output:**

- Explained zero-code instrumentation via env vars (`LANGCHAIN_TRACING_V2=true`)
- Showed the callback protocol: `Runnable` → `LangChainTracer` → HTTPS to smith.langchain.com
- Mapped our `retention_graph.py` nodes to the nested trace tree LangSmith generates automatically
- Compared to OTel's manual span creation approach
- Identified the gap: LangSmith can't trace across HTTP boundaries (e.g., into churn-predictor-api)

**My evaluation:** Clear explanation with good code examples from our actual codebase. The key insight — LangSmith traces inside LangChain, OTel traces across services — was valuable for understanding our observability gaps.

---

### 6. Grafana Observability Stack Research

**What I asked:** How would you export LangSmith data into a Grafana observability stack?

**LLM output:** Presented 3 options:

1. **Replace LangSmith with OTel** — `OpenTelemetryCallbackHandler` → OTel Collector → Tempo
2. **Dual-write** — Keep LangSmith + add OTel callback side-by-side
3. **LangSmith API → Prometheus** — Poll LangSmith API, export metrics only

Included docker-compose additions for OTel Collector, Tempo, Prometheus, and Grafana.

**My evaluation:** Recommended Option 2 (dual-write) for the capstone — shows understanding of both paradigms. Didn't implement; this was research for potential future work.

---

### 7. SageMaker Inference Code Analysis

**What I asked:** What is `sagemaker/churn/inference.py` doing? What overlaps with the service layer?

**LLM output:**

- Identified `inference.py` as the SageMaker serving script (model_fn, input_fn, predict_fn, output_fn)
- Found that `churn-predictor-api/app.py` sends `text/csv` to SageMaker, which uses the container's built-in CSV handler — **bypassing inference.py entirely**
- Found duplicated label encoders and feature columns in 3 locations (all identical)
- Recommended keeping `inference.py` (required by deploy.py packaging) but noted `app.py` should load from JSON files instead of hardcoding

**My evaluation:** Thorough analysis. The finding that `inference.py` is effectively dead code in our current architecture was surprising and accurate. The duplication across 3 locations (`sagemaker/churn/`, `services/churn-predictor-api/model/`, hardcoded in `app.py`) is a real maintenance risk. Flagged for team discussion.

---

### 8. PROJECT_ROADMAP.md Update

**What I asked:** Update PROJECT_ROADMAP.md to reflect the implemented workflows and delete the PDF version.

**LLM output:**

- Updated 5 sections: repo structure (new workflow filenames), CI/CD pipeline diagram (split manual/automatic view with workflow table), Phase 1 Troy status (marked complete), Phase 2 Troy status (marked complete with per-workflow descriptions), Bonus Points CI/CD rows (marked done)
- Deleted `PROJECT_ROADMAP.pdf`

**My evaluation:** Accurate updates. The new CI/CD diagram clearly shows the manual dispatch pipeline vs automatic post-merge pipeline. Accepted all changes.

---

### 9. Terraform Remote State & Fixes

**What I asked:** Debug `terraform apply` failures (EntityAlreadyExists on all IAM roles + S3 bucket, invalid ECR repo policy). Then set up remote state.

**LLM analysis:**
- Identified root cause: Terraform was using **local state** (no `backend` block in `providers.tf`), so GitHub Actions runners had no memory of previous applies. Resources created manually or by prior runs weren't tracked.
- Identified the `aws_ecr_repository_policy` targeting `763104351884/*` (AWS's public SageMaker registry) as invalid — you can't set policies on repos you don't own.

**Changes made:**
1. Added S3 backend + DynamoDB lock table to `providers.tf`:
   ```hcl
   backend "s3" {
     bucket         = "retention-engine-tf-state"
     key            = "terraform.tfstate"
     region         = "us-east-1"
     dynamodb_table = "retention-engine-tf-lock"
     encrypt        = true
   }
   ```
2. Bootstrapped backend: `aws s3api create-bucket --bucket retention-engine-tf-state` (DynamoDB table already existed)
3. Ran `terraform init` to migrate local state to S3 — all existing resources carried over
4. Removed invalid `aws_ecr_repository_policy` from `sagemaker.tf`

**My evaluation:** The local state problem perfectly explained why CI kept trying to recreate existing resources. The S3 backend is now shared across local and CI runs.

---

### 10. Terraform SageMaker Definition Alignment

**What I asked:** The `terraform plan` showed 2 destroy/recreate for SageMaker resources. Why?

**LLM analysis:** Found 5 mismatches between `sagemaker.tf` definitions and the actual deployed resources (created by `sagemaker/sentiment/deploy.py`):

| Setting | Terraform had | Actually deployed |
|---|---|---|
| Execution role | `sagemaker-execution-role` | `retention/retention-sagemaker-execution-role` |
| Container image | `pytorch-inference:2.0.0-cpu-py310` | `huggingface-pytorch-inference:2.6.0-transformers4.49.0-cpu-py312-ubuntu22.04` |
| Model data | *(none)* | `s3://retention-engine-bucket/models/sentiment/model.tar.gz` |
| Environment vars | `HF_MODEL_ID` + `HF_TASK` | `SAGEMAKER_PROGRAM=inference.py` |
| Variant name | `AllTraffic` | `primary` |

**Changes made:** Updated `sagemaker.tf` to match the actual deployed state — execution role ARN, container image, model data URL, environment variables, and variant name.

**My guidance:** Told the LLM to look up the actual names from `deploy.py` rather than guessing. The sentiment endpoint name was `retention-sentiment-analysis-endpoint`, not `sentiment-analysis-endpoint` as originally assumed.

**Result:** `terraform plan` now shows **0 changes** — Terraform's definitions match live AWS resources exactly.

**Key learning:** When Terraform is adopted after resources are already manually created, the hardest part is aligning the `.tf` definitions with reality. The `terraform import` gets the state right, but the config still needs to match or Terraform will try to "fix" the drift by destroying and recreating.

---

### 11. Terraform Environment Variable Analysis

**What I asked:** The `terraform.yml` workflow has dev/staging/prod environment options — what are the actual differences?

**LLM analysis:** Found that `var.environment` is only used as an AWS resource **tag** (`Environment = var.environment`). No resource names, instance types, bucket names, or configs change between environments. All three options produce identical infrastructure.

**My evaluation:** Accurate. This is cosmetic multi-environment support — fine for a capstone demo, but worth knowing the limitation.

---

## Instances Where I Provided Guidance or Changed LLM Recommendations

### 1. Workflow Trigger Strategy

**LLM initial approach:** Could have used `push` triggers with path filters for per-service CI.
**My choice:** Went with `workflow_dispatch` for all infra/deploy workflows so nothing runs automatically on push except post-merge validation. This prevents accidental Terraform applies or SageMaker endpoint changes.

### 2. Keeping inference.py

**LLM analysis:** Identified it as dead code in our architecture.
**My decision:** Keep it — it's bundled by `deploy.py` into `model.tar.gz` and serves as a fallback for direct endpoint invocation.

### 3. Secret Management

**LLM used:** `${{ secrets.AWS_REGION }}` in workflows.
**Issue:** `AWS_REGION` wasn't set as a GitHub secret, causing the first CI run to fail.
**Resolution:** Added it via `gh secret set`. Could also have hardcoded `us-east-1` since it's not sensitive, but keeping it as a secret maintains consistency with the other AWS vars.

### 4. Terraform SageMaker — Don't Guess, Look It Up

**LLM initial output:** Updated `sagemaker.tf` with names it assumed were correct (`sentiment-analysis-model`, `sentiment-endpoint-config`).
**My guidance:** Told it to look at the actual `deploy.py` files for the real names. The real names were prefixed with `retention-` (e.g., `retention-sentiment-analysis-endpoint`).
**Impact:** Without this correction, `terraform apply` would have created duplicate endpoints at double the cost.

### 5. Preventing Destructive Terraform Applies

**LLM flagged:** The plan showed `destroy and then create replacement` for the sentiment model and endpoint config.
**My decision:** Did not apply. Waited for the LLM to align the `.tf` definitions with the actual deployed state before running any apply.
**Key learning:** Always review `terraform plan` output before applying — the LLM correctly warned against applying the destructive plan.

---

## LLM Tools Used

| Tool                             | Usage                               |
| -------------------------------- | ----------------------------------- |
| GitHub Copilot (Claude Opus 4.6) | Primary — all tasks in this session |
| VS Code Chat                     | Interface for all interactions      |

---

## Key Takeaways

1. **Design docs before implementation** — having the CI/CD design docs written first made the workflow YAML implementation straightforward. The LLM followed its own specs accurately.
2. **Codebase analysis is a strength** — the LLM accurately traced data flow across multiple files (inference.py → deploy.py → app.py) and identified the dead code + duplication issues.
3. **Teaching with real code** — the LangSmith/OTel comparison was more useful because it referenced our actual `retention_graph.py` and tool files rather than generic examples.
4. **First-run failures are normal** — the `AWS_REGION` secret issue was a simple miss that the LLM couldn't have known about (it doesn't have access to GitHub Secrets state). Quick fix once identified.

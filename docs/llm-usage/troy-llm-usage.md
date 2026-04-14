# LLM Usage Log — Troy

**Tool:** GitHub Copilot (Claude Opus 4.6, VS Code Chat)
**Period:** April 7–11, 2026

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

| Setting          | Terraform had                       | Actually deployed                                                              |
| ---------------- | ----------------------------------- | ------------------------------------------------------------------------------ |
| Execution role   | `sagemaker-execution-role`          | `retention/retention-sagemaker-execution-role`                                 |
| Container image  | `pytorch-inference:2.0.0-cpu-py310` | `huggingface-pytorch-inference:2.6.0-transformers4.49.0-cpu-py312-ubuntu22.04` |
| Model data       | _(none)_                            | `s3://retention-engine-bucket/models/sentiment/model.tar.gz`                   |
| Environment vars | `HF_MODEL_ID` + `HF_TASK`           | `SAGEMAKER_PROGRAM=inference.py`                                               |
| Variant name     | `AllTraffic`                        | `primary`                                                                      |

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

### 12. Workflow Debugging — Missing GitHub Secrets

**What I asked:** Debug failing `sagemaker-deploy.yml` workflow runs.

**LLM analysis:** Two consecutive failures, same root cause pattern:

1. **Run 1:** `S3_BUCKET` secret not set → `botocore.exceptions.ParamValidationError: Invalid bucket name ""`. The workflow passes `S3_BUCKET: ${{ secrets.S3_BUCKET }}` as an env var, but when the secret is empty, Python's `os.environ.get("S3_BUCKET", "default")` receives an empty string (not `None`), so the fallback never triggers.
2. **Run 2:** `SAGEMAKER_ROLE_ARN` secret not set → `ParamValidationError: Invalid length for parameter ExecutionRoleArn, value: 0, valid min length: 20`. Same empty-string-override pattern.

**Fixes applied:**

```bash
gh secret set S3_BUCKET --body "retention-engine-bucket"
gh secret set SAGEMAKER_ROLE_ARN --body "arn:aws:iam::388691194728:role/retention/retention-sagemaker-execution-role"
```

**My evaluation:** Straightforward diagnosis — the error messages pointed exactly to the problem. Key lesson: GitHub Actions sets env vars to empty strings when secrets are missing, which defeats Python's default-value fallback. All required secrets should be set before first workflow run.

---

### 13. SageMaker Deploy Script Optimization — Skip Healthy Endpoints

**What I asked:** The `sagemaker-deploy.yml` run was taking 6+ minutes on "Deploy Churn Endpoint" even though the endpoints already exist and are healthy. Add early-exit logic.

**LLM output:** Added a `describe_endpoint` check at the top of `create_endpoint()` in both `sagemaker/churn/deploy.py` and `sagemaker/sentiment/deploy.py`:

- If endpoint status is `InService` → print skip message and return immediately
- If endpoint exists but unhealthy → proceed with redeployment
- If endpoint doesn't exist → proceed with full creation

**My evaluation:** Clean optimization. Avoids the 5-10 minute `update_endpoint` + waiter cycle when nothing has changed. The sentiment script also skips `get_iam_role()` and `select_best_container()` calls in the early-exit path, saving additional API calls.

---

### 14. Endpoint Update Loop — Handling In-Progress States

**What I asked:** Workflow kept failing with `WaiterError: Max attempts exceeded` on Deploy Churn Endpoint (14m 54s). The skip check wasn't catching it.

**LLM analysis:** The endpoint was stuck in `Updating` from a previous failed run. The initial skip logic only handled `InService` — when it saw `Updating`, it fell through and tried to `update_endpoint` on an already-updating endpoint, which SageMaker rejects.

**LLM fix:** Updated both `deploy.py` scripts to handle three states:

- `InService` → skip immediately
- `Updating` / `Creating` → wait for the in-progress operation to finish, then return
- `Failed` / other → proceed with full redeployment

**My evaluation:** Good defensive coding. The `Updating` state is a real edge case that surfaces when CI runs overlap or retry after failures.

---

### 15. CloudWatch Log Diagnosis — Missing setup.py in Model Tar

**What I asked:** The churn endpoint was stuck failing health checks despite the model tar having the right files. Why?

**LLM analysis:** Pulled CloudWatch logs for the endpoint and found the root cause:

```
sagemaker_containers._errors.ImportModuleError: No module named 'inference'
```

The XGBoost container uses `SAGEMAKER_PROGRAM=inference.py` and needs `setup.py` to install `inference` as an importable module. `deploy.py` defined `SETUP_SCRIPT` but never added it to the tar.

**LLM fix:** Added `tar.add(SETUP_SCRIPT, arcname="setup.py")` to `package_model()`.

**Additional actions:** Since the endpoint was stuck in an `Updating` loop with the bad model, the LLM waited for it to settle back to `InService` (SageMaker rolled back to previous config), then deleted the endpoint/config/model to allow a clean fresh deploy.

**My evaluation:** Good root cause analysis. The CloudWatch log pull was the right move — the Python traceback on the CI runner only showed the waiter timeout, not _why_ the container failed. The `setup.py` was defined but unused — a bug in the original `deploy.py` that was masked because the previous manually-deployed model tar already had it.

---

### 16. Sentiment Deploy — Missing `packaging` Module

**What I asked:** After churn passed, sentiment deploy failed with `ModuleNotFoundError: No module named 'packaging'`.

**LLM fix:** Added `packaging` to the workflow's pip install step: `pip install boto3 python-dotenv packaging`.

**My evaluation:** Fast fix. The sentiment `deploy.py` imports `validator.py` which uses `from packaging import version`. The workflow's dependency list was incomplete.

---

### 17. Skip Logic Placement Bug — Packaging Before Checking

**What I asked:** Workflow runs were uploading a new (broken) model tar and deleting the working one, even when the endpoint was already InService.

**LLM analysis:** The skip check was inside `create_endpoint()`, but `package_model()` and `upload_to_s3()` ran _before_ it in `__main__`. This meant every CI run:

1. Rebuilt the tar (potentially with bugs)
2. Uploaded it to S3 (overwriting the working model)
3. _Then_ checked if the endpoint was healthy

**LLM fix:** Moved the `describe_endpoint` skip logic to the top of `__main__`, before any packaging or upload calls. Both `churn/deploy.py` and `sentiment/deploy.py` updated.

**My evaluation:** Critical fix. The ordering bug meant that even "successful" skip runs were silently replacing good model artifacts with potentially bad ones. This was the root cause of the 500 errors — a working endpoint got its model tar overwritten, then SageMaker rolled back to the overwritten (broken) version on the next update.

---

### 18. invoke-endpoint CLI Fixes — /dev/stdout and Base64

**What I asked:** Inference validation step failing with exit code 255 on GitHub runners.

**LLM analysis:** Two issues:

1. **`/dev/stdout` as output file:** AWS CLI v2 on GitHub runners rejects `/dev/stdout` as an output path. Fixed by writing to temp files (`/tmp/churn-response.json`, `/tmp/sentiment-response.json`) then `cat`-ing the result.
2. **Base64 body encoding:** AWS CLI v2 treats `--body` as base64-encoded by default. Passing raw CSV like `--body "2,100,78.0,..."` caused garbled input. Fixed by writing payload to a temp file and using `fileb://` prefix (`--body fileb:///tmp/churn-payload.csv`).

**My evaluation:** Both are AWS CLI v2 behavioral differences that don't surface locally (v1 handles both differently). The `fileb://` fix is documented in AWS docs but easy to miss.

---

### 19. Clean Slate Redeploy — Stale Model Tar

**What I asked:** Churn endpoint was InService but returning 500 on every invoke. CloudWatch showed `No module named 'inference'`.

**LLM analysis:** The endpoint was InService with an **old** model tar (pre-`setup.py` fix). Previous failed `update_endpoint` calls caused SageMaker to roll back to the last working config — which pointed to the old S3 model tar without `setup.py`. The endpoint appeared healthy (passed `/ping`) but couldn't serve predictions.

**LLM fix:** Deleted the endpoint, endpoint config, and model to force a completely fresh deploy:

```bash
aws sagemaker delete-endpoint --endpoint-name churn-predictor-endpoint
aws sagemaker delete-endpoint-config --endpoint-config-name churn-predictor-config
aws sagemaker delete-model --model-name churn-predictor-model
```

**My evaluation:** Right call. SageMaker's rollback behavior is designed for safety but creates a trap: the endpoint looks healthy while serving a stale model. The only way to guarantee the new tar is loaded is a full teardown + recreate.

---

### 20. SAGEMAKER_PROGRAM vs Algorithm Mode — CSV Support in inference.py

**What I asked:** After redeploying, the churn endpoint still failed with a 500 on CSV payloads.

**LLM first attempt:** Removed `SAGEMAKER_PROGRAM` and `SAGEMAKER_SUBMIT_DIRECTORY` from the model environment so the built-in XGBoost container would handle CSV natively.

**Result:** Container crashed on startup — without `SAGEMAKER_PROGRAM`, the XGBoost container runs in "algorithm mode" and tries to load _every_ file in the tar as a model. It choked on `feature_columns.json`:

```
RuntimeError: Model /opt/ml/model/feature_columns.json cannot be loaded
```

**Corrected fix (two changes):**

1. **Restored `SAGEMAKER_PROGRAM=inference.py`** in `deploy.py` — the container needs the custom script because the tar contains non-model files
2. **Added `text/csv` support to `inference.py`** — `input_fn` now parses CSV as a list of floats, and `predict_fn` handles both list (CSV, pre-encoded) and dict (JSON, needs label encoding) inputs

**My evaluation:** The first attempt (removing SAGEMAKER*PROGRAM) was a reasonable hypothesis — the app does send CSV — but missed that our tar layout forces "framework mode" with a custom script. The corrected two-part fix addresses the real constraint: we need SAGEMAKER_PROGRAM \_and* CSV support in `inference.py`. This also validates the Task 7 finding — `inference.py` was always needed, just needed to support the content type the app actually sends.

---

### 21. deploy.yml — qa-evaluator-api Docker Build Failure

**What I asked:** `deploy.yml` failed on `docker/build-push-action@v5` for `qa-evaluator-api` — `COPY requirements.txt .` failed because the file doesn't exist.

**LLM analysis:** The `services/qa-evaluator-api/` directory only contained a `Dockerfile` (written by George). No `requirements.txt`, no `app.py` — the service was never implemented. The Dockerfile references both files but neither existed, so the matrix Docker build failed.

**LLM fix:** Created two stub files:

- `requirements.txt` — fastapi, uvicorn, httpx (matching the Dockerfile's uvicorn CMD and httpx health check)
- `app.py` — minimal FastAPI app with a `/health` endpoint, marked as stub for George/Okino to implement

**My evaluation:** Right approach — stub it out so the CI pipeline isn't blocked by an unfinished teammate service. The stubs match the Dockerfile's expectations (uvicorn entrypoint, httpx health check) so the image builds and runs correctly. George can replace with the real implementation later.

---

### 22. agent-service boto3 Dependency Conflict

**What I asked:** `deploy.yml` Docker build for `agent-service` failed with `ResolutionImpossible` — pip can't resolve dependencies.

**LLM analysis:** `requirements.txt` pinned `boto3==1.35.0`, but `langchain-aws==0.2.0` requires `boto3<1.35.0,>=1.34.131`. The exact pin conflicted with the upper bound.

**LLM fix:** Changed `boto3==1.35.0` to `boto3>=1.34.131,<1.35.0` to satisfy both constraints.

**My evaluation:** Straightforward version conflict. The original pin was probably set before `langchain-aws` was added. This is a common pattern when teams add packages without checking transitive dependency constraints.

---

### 23. EKS Cluster Access Setup for deploy.yml

**What I asked:** `deploy.yml` failed on `kubectl apply` with `connection refused` — the GitHub runner had no kubeconfig.

**LLM analysis:** The workflow expects a `KUBE_CONFIG` secret (base64-encoded kubeconfig) but it wasn't set. The runner had no way to reach the EKS cluster.

**LLM actions:**

1. Listed EKS clusters — found `eks-ezvrmopo-okl` (v1.30) and `k8s-training-cluster` (v1.33)
2. I selected `eks-ezvrmopo-okl` as the target cluster
3. Found that IAM user `Troy` wasn't in the cluster's access entries (only `Okino` had access)
4. Added `Troy` as an access entry with `AmazonEKSClusterAdminPolicy`
5. Generated kubeconfig via `aws eks update-kubeconfig`
6. Base64-encoded and set as `KUBE_CONFIG` GitHub secret

**My evaluation:** Correct sequence. The LLM asked me which cluster to target rather than guessing. The access entry addition was necessary — without it, even a valid kubeconfig would fail auth.

---

### 24. Kubeconfig AWS_PROFILE Reference — CI Environment Mismatch

**What I asked:** `deploy.yml` still failed on `kubectl apply` with `The config profile (lumineer) could not be found`.

**LLM analysis:** The kubeconfig generated by `aws eks update-kubeconfig` included `AWS_PROFILE: lumineer` in the exec env block — a local-only AWS CLI profile that doesn't exist on the GitHub runner. The runner uses env var credentials (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`), not named profiles.

**LLM fix:** Generated a fresh kubeconfig to `/tmp/ci-kubeconfig`, stripped the `AWS_PROFILE` env blocks with `sed`, verified no `lumineer` references remained, then re-uploaded as the `KUBE_CONFIG` secret.

**My evaluation:** Another local-vs-CI environment gap. The `aws eks update-kubeconfig` command inherits whatever profile is active locally and bakes it into the kubeconfig. For CI, the profile reference must be removed so the runner falls back to environment variable credentials.

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

### 6. Iterative Secret Debugging

**Situation:** The `sagemaker-deploy.yml` workflow failed twice in a row due to missing secrets (`S3_BUCKET`, then `SAGEMAKER_ROLE_ARN`).
**My process:** Ran the workflow, read the error, set the secret, re-ran. Each failure revealed the next missing secret. The LLM correctly diagnosed each one from the traceback but couldn't preemptively check which secrets are set (no access to GitHub Secrets API).
**Takeaway:** Before first workflow run, audit the workflow YAML for all `${{ secrets.* }}` references and ensure every one is set. Would have saved two failed runs.

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
5. **CloudWatch logs are essential for SageMaker debugging** — CI runner output only shows waiter timeouts. The actual container failure reason (`No module named 'inference'`) was only in CloudWatch. The LLM pulled the right log stream and identified the root cause (missing `setup.py` in tar) in one step.
6. **Iterative workflow debugging** — 6 consecutive workflow runs to get `sagemaker-deploy.yml` passing: missing S3_BUCKET → missing SAGEMAKER_ROLE_ARN → update loop → waiter timeout → missing setup.py → missing packaging module. Each failure taught something new about the gap between local assumptions and CI reality.
7. **Execution order matters in CI scripts** — the skip logic placement bug (Task 17) showed that checking endpoint health _after_ uploading a new model tar defeats the purpose of the check. The order must be: check → skip OR package → upload → deploy.
8. **SageMaker rollback creates stale-model traps** — when `update_endpoint` fails, SageMaker rolls back to the previous config. The endpoint returns to InService but serves the old model. A full delete → recreate is the only reliable way to force a new model tar.
9. **LLM missteps are recoverable** — the SAGEMAKER_PROGRAM removal (Task 20) was wrong, but the error was diagnosable from CloudWatch logs in one iteration. The corrected fix (restore SAGEMAKER_PROGRAM + add CSV to inference.py) addressed the real constraint.

---

### 25. Merge Main into troy/test-workflows — Branch Sync & Conflict Resolution

**What I asked:** `troy/test-workflows` fell behind main after the team merged several PRs (#52, #53, #55). What are the differences, and how do I get current?

**LLM output:**

- Compared branches: main had 10 new commits (George's infra-agent PR #55, Kathleen's drift-roadmap PR #53, Troy's terraform-workflow PR #52)
- Key changes on main: K8s port fixes (agent 8000→8080, churn 8000→8001), ConfigMap URL rename (qa-evaluator→sentiment-analysis), SageMaker deploy.py switch to native XGBoost, new `terraform/backend.tf` with S3 remote state
- Explained merge vs rebase tradeoffs; recommended merge since it's a shared branch
- Guided through conflict resolution in `sagemaker/churn/deploy.py` (2 conflicts — both resolved by accepting main's native XGBoost changes)

**My evaluation:** Clear branch comparison and conflict walkthrough. The merge approach was correct for a shared branch. Both conflicts were straightforward — main's version was the right one since Kathleen's XGBoost fix was intentional.

---

### 26. Fix Duplicate Terraform Backend Block

**What I asked:** `terraform init` failed with "Duplicate backend configuration" — S3 backend defined in both `backend.tf` and `providers.tf`.

**LLM analysis:** The merge brought in George's `backend.tf` (PR #55) while `providers.tf` already had the same block. Both were identical.

**LLM fix:** Removed the backend block from `providers.tf`, keeping it in `backend.tf` which has the documentation comments.

**My evaluation:** Obvious merge artifact. Quick fix.

---

### 27. Remove SageMaker Resources from Terraform

**What I asked:** Terraform `apply` failed with "Cannot create already existing model" because both `sagemaker.tf` and `sagemaker-deploy.yml` (Python boto3) managed the same SageMaker resources. Which should own them?

**LLM analysis:**

- Two systems creating the same resources (model, endpoint config, endpoint) for both churn and sentiment
- `deploy.py` handles packaging, upload, health checks, inference validation, and deploy/delete — purpose-built for ML endpoints
- Terraform is better suited for foundational infra (IAM, S3, networking, EKS)
- Recommended removing SageMaker resources from Terraform

**LLM fix:** Replaced all SageMaker resource blocks in `sagemaker.tf` with a comment pointing to `sagemaker-deploy.yml`. Removed orphaned `sentiment_endpoint_name` variable from `variables.tf`.

**My evaluation:** Right call. ML endpoints change frequently (retrained models, new artifacts) — that's operational, not infrastructure. Clean separation of concerns.

---

### 28. Fix K8s `secrets.yaml` — `Secrets` vs `Secret`

**What I asked:** `kubectl apply -f k8s/secrets.yaml` failed with "resource mapping not found for kind `Secrets` in version `v1`".

**LLM fix:** Changed `kind: Secrets` → `kind: Secret` (singular) on both resources. Kubernetes resource kinds are always singular.

**My evaluation:** Typo fix. Quick catch.

---

### 29. Number Workflow Names for Run Order

**What I asked:** Add numbers to workflow names so they sort in order in the Actions tab.

**LLM fix:** Renamed:

- `Terraform — Infrastructure` → `1 — Terraform Infrastructure`
- `SageMaker — Deploy Endpoints` → `2 — SageMaker Endpoints`
- `Deploy — Build & Roll Out to EKS` → `3 — Build & Roll Out to EKS`

**My evaluation:** Simple UX improvement. Shows the team the execution order at a glance.

---

### 30. Add Deployment Summary to deploy.yml

**What I asked:** `deploy.yml` doesn't show endpoint URLs after completion. Add a summary.

**LLM fix:** Added a `Deployment Summary` step using `$GITHUB_STEP_SUMMARY` that queries `kubectl get svc` for each service and outputs a markdown table with endpoint URLs, ports, and status.

**My evaluation:** Good addition. The summary shows up in the Actions run page so the team can grab URLs without digging through logs.

---

### 31. Fix K8s Secrets — GitHub Secrets Instead of Static YAML

**What I asked:** `deploy.yml` was applying `k8s/secrets.yaml` which had literal `${AWS_ACCESS_KEY_ID}` placeholders. The pods would get the string `${AWS_ACCESS_KEY_ID}` as their credentials.

**LLM fix:**

- Removed `kubectl apply -f k8s/secrets.yaml` from the workflow
- Added a step that creates secrets from GitHub repo secrets using `kubectl create secret generic --dry-run=client -o yaml | kubectl apply -f -`
- `kube-secrets` required a `kubectl delete --ignore-not-found` first because the existing secret had `type: kubernetes.io/basic-auth` and Kubernetes won't allow changing a Secret's type via apply

**My evaluation:** Critical fix. Without this, every pod referencing `aws-secrets` would have empty/broken AWS credentials. The `--dry-run | apply` pattern is idempotent — safe for reruns.

---

### 32. deploy.yml Rollout Timeout Analysis

**What I asked:** `agent-service` deployment timed out with "0 out of 1 new replicas have been updated". What other errors will it hit?

**LLM analysis:** Identified 3 additional issues beyond the timeout:

1. **`k8s/secrets.yaml` placeholders** — already fixed in Task 31
2. **Build matrix vs deployment mismatch** — `deploy.yml` builds 4 images but applies 7 deployment manifests. `backend-deployment`, `churn-wrapper-deployment`, `transcript-wrapper-deployment` have no built images → will sit in `ImagePullBackoff`
3. **Rollout wait only checks 3 of 7 deployments** — unbuilt ones fail silently

**My evaluation:** Good audit. The build-vs-deploy mismatch is the next thing to address with the team.

---

### 33. Quota Exhaustion — Delete Broken Deployments & Clean Up Manifests

**What I asked:** `agent-service` rollout kept timing out. `kubectl get pods` showed 6 pods in `ImagePullBackOff` consuming 10/10 pod quota, 4/4 CPU, 4Gi/4Gi memory — leaving zero room for `agent-service`.

**LLM analysis:** 5 deployments (`backend-deployment`, `churn-wrapper-deployment`, `sentiment-predictor`, `sentiment-wrapper-deployment`, `transcript-wrapper-deployment`) had no Docker images in GHCR — the build matrix only builds 4 services. These dead pods consumed the entire namespace quota.

**LLM fix:**

1. Deleted the 5 broken deployments from the cluster: `kubectl delete deployment ... --ignore-not-found`
2. Removed 3 deployment YAML files from `k8s/deployments/` (`backend-deployment.yaml`, `churn-wrapper-deployment.yaml`, `transcript-wrapper-deployment.yaml`) so they won't be recreated on the next `kubectl apply`
3. Also identified `TooManyLoadBalancers` AWS account limit as a secondary blocker

**My evaluation:** Right call. The remaining 4 deployment manifests (`agent`, `churn-predictor`, `frontend`, `qa-evaluator`) now match the build matrix exactly. Quota freed up for `agent-service` to schedule.

---

## Running List of Changes (This Session — April 9, 2026)

| Commit    | File(s)                                                                                                          | Change                                                                                        |
| --------- | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `72079ee` | multiple                                                                                                         | Merged `origin/main` into `troy/test-workflows` (PRs #52, #53, #55)                           |
| `5da84ed` | `terraform/providers.tf`                                                                                         | Removed duplicate S3 backend block (kept in `backend.tf`)                                     |
| `cf63e10` | `terraform/sagemaker.tf`, `terraform/variables.tf`                                                               | Removed all SageMaker model/endpoint/config resources; managed by `sagemaker-deploy.yml`      |
| `8bf16b2` | `.github/workflows/deploy.yml`                                                                                   | Added Deployment Summary step with service URLs table via `$GITHUB_STEP_SUMMARY`              |
| `d2d26d7` | `k8s/secrets.yaml`                                                                                               | Fixed `kind: Secrets` → `kind: Secret` (singular)                                             |
| `3cd6c35` | `.github/workflows/terraform.yml`, `sagemaker-deploy.yml`, `deploy.yml`                                          | Numbered workflow names: 1 — Terraform, 2 — SageMaker, 3 — Build & Roll Out                   |
| `2a21d56` | `.github/workflows/deploy.yml`                                                                                   | Replaced `kubectl apply -f k8s/secrets.yaml` with `kubectl create secret` from GitHub secrets |
| `70c2dcb` | `.github/workflows/deploy.yml`                                                                                   | Added `kubectl delete kube-secrets --ignore-not-found` before recreate to handle type change  |
| `9bea5b6` | `k8s/deployments/backend-deployment.yaml`, `churn-wrapper-deployment.yaml`, `transcript-wrapper-deployment.yaml` | Removed deployment manifests for services with no Docker images                               |

---

## Session 2 — April 11, 2026

### 34. ALB Ingress Architecture — Replace Per-Service LoadBalancers

**What I asked:** Replace individual LoadBalancer services with a single ALB Ingress to consolidate all traffic through one DNS endpoint.

**LLM output:**

- Created `terraform/alb-controller.tf` — OIDC provider, IAM policy, IAM role with IRSA trust for the ALB controller service account
- Created `k8s/ingress.yaml` — ALB Ingress with path-based routing (`/` → frontend, `/agent-api/` → agent-service, `/churn-api/` → churn-predictor)
- Created `k8s/services/frontend-service.yaml` — ClusterIP service for frontend (previously had none)
- Created `scripts/install-alb-controller.sh` — Helm install script for the AWS Load Balancer Controller
- Converted existing LoadBalancer services to ClusterIP

**My evaluation:** Correct architecture. Single ALB reduces cost and gives one DNS endpoint for all traffic instead of 3+ separate ELB hostnames.

---

### 35. Five Configuration Bugs Fixed (PR #62)

**What I asked:** Frontend can't reach backend services through the ALB. Debug and fix everything.

**LLM analysis and fixes:**

1. **Nginx reverse proxy** — Frontend's `nginx.conf` had no proxy rules. Added `location /agent-api/` and `/churn-api/` blocks proxying to backend ClusterIP services. Updated Dockerfile with `VITE_API_BASE_URL` build arg so React builds with the correct API prefix.

2. **Ingress routing** — Simplified path annotations. The ALB routes `/agent-api/*` to agent-service, nginx handles the rest.

3. **ConfigMap fix** — `agent-config.yaml` had `QA_EVALUATOR_URL` pointing to wrong hostname. Fixed to match the actual service name.

4. **SageMaker endpoint name** — Hardcoded endpoint name in agent-service didn't match the actual deployed endpoint (`churn-predictor-endpoint`).

5. **ChatBedrock source code bug** — `chains/churn_analysis.py` used `ChatBedrock(model=..., region=...)` but the LangChain API requires `model_id=` and `region_name=`. Also pinned `pydantic<2.0` to fix a separate import error.

**My evaluation:** All 5 were real bugs preventing end-to-end functionality. The ChatBedrock parameter names were the most subtle — the old parameter names silently fell back to defaults.

---

### 36. Terraform State Cleanup — 19 Orphaned Resources

**What I asked:** `terraform plan` showed 11 destroys. The state had resources that no longer existed in `.tf` files.

**LLM analysis:** After removing SageMaker resources from Terraform (Task 27), the state file still tracked them. Additionally, old resource names from before the refactor cluttered the state.

**LLM actions:**

- Removed 19 orphaned resources from state using `terraform state rm`
- Re-imported S3 resources that had provider schema mismatches
- Achieved clean plan: **9 to add, 0 to change, 0 to destroy**

**My evaluation:** Careful state surgery. The LLM checked each resource before removing and verified the final plan was clean.

---

### 37. Teardown Workflow (PR #64) — Safe Infrastructure Teardown

**What I asked:** Create a teardown workflow for full CI/CD pipeline testing — tear everything down, then rebuild from scratch using the 3 dispatch workflows.

**LLM output:** Created `.github/workflows/teardown.yml` with:

- **Safety gate** — must type `TEARDOWN` to confirm
- **Scope selection** — all, terraform-only, kubernetes-only, or alb-controller-only
- **4 phases** — delete ingress → delete namespace → uninstall Helm chart → terraform destroy
- **Preserves** — EKS cluster, SageMaker endpoints, S3 buckets, sagemaker-execution-role (all pre-existing, not managed by TF)
- **Rebuild instructions** in summary — terraform apply → sagemaker deploy → k8s deploy (3 clicks)

Also automated ALB controller Helm install as a post-apply step in `terraform.yml`, so the rebuild pipeline is fully automated.

**My evaluation:** Well-designed safety gates. The scope options let you tear down just K8s without touching Terraform, which is useful for testing deploy.yml in isolation.

---

### 38. Teardown Execution — Finalizer Stuck on Ingress

**What I asked:** Ran the teardown workflow. The ingress deletion hung for 5+ minutes.

**LLM analysis:** The ALB Ingress had a `ingress.k8s.aws/resources` finalizer that blocks deletion until the ALB controller confirms the AWS resources (ALB, target groups, listeners) are cleaned up. Since the controller was being deleted in the same teardown, nothing was there to clear the finalizer.

**LLM fix:** Updated `teardown.yml` to:
1. Delete ingress with `--timeout=120s`
2. If timeout, force-remove the finalizer with `kubectl patch --type=json -p='[{"op": "remove", "path": "/metadata/finalizers"}]'`
3. Capture ALB hostname before deletion, then poll AWS until the actual ALB is gone

**My evaluation:** Right fix. The ordering issue (deleting the controller before the ingress finalizer resolves) is a common Kubernetes teardown trap. The fallback patch is safe because we're tearing down everything anyway.

---

### 39. Terraform Import Marathon — Pre-Existing AWS Resources

**What I asked:** After teardown, `terraform apply` in CI kept failing with "already exists" errors for resources that existed in AWS but not in Terraform state.

**LLM actions:** Imported 7 resources across multiple CI runs:

| Resource | Import ID | Why Missing |
|----------|-----------|-------------|
| `aws_iam_openid_connect_provider.eks` | Full ARN | Created by teammate's script, never in TF |
| `aws_iam_policy.alb_controller` | Policy ARN | Created by previous apply, state lost |
| `aws_iam_role.alb_controller` | Role name | Same — partial apply |
| `aws_iam_role.transcribe_lambda_role` | Role name | Created by Kathleen's PR, never in TF |
| `aws_lambda_function.transcribe_pipeline` | Function name | Partial apply created it, then errored on `AWS_REGION` |
| `aws_lambda_permission.allow_s3_invoke` | `function/statement_id` | Partial apply created it, next run couldn't |
| `aws_s3_bucket_notification.audio_upload_trigger` | Bucket name | Same pattern |

**My evaluation:** Each import was necessary — the resources genuinely existed in AWS. The root cause was partial applies: Terraform creates resource A, then fails on resource B, but only records A in state if the apply step completes. Since CI uses `tfplan` files and the apply step fails, nothing gets recorded.

**Key learning:** After a failed `terraform apply`, always check what was partially created in AWS before re-running. Import first, then re-apply.

---

### 40. Transcribe Lambda Role — Description Drift

**What I asked:** `terraform plan` showed a change on `transcribe_lambda_role` — trying to null the description.

**LLM analysis:** The imported role had `description = "Lambda role for Transcribe pipeline"` in AWS, but `transcribe.tf` had no description field. Terraform treated this as drift and wanted to remove it, which requires `iam:UpdateRoleDescription` — a permission Troy's IAM user didn't have.

**LLM fix:** Added `description = "Lambda role for Transcribe pipeline"` to `transcribe.tf` to match AWS.

**My evaluation:** Correct. Aligning the config with reality (rather than trying to change AWS) avoids the permission issue entirely.

---

### 41. Reserved Lambda Environment Variable — `AWS_REGION`

**What I asked:** Lambda creation failed with `InvalidParameterValueException: contains reserved keys: AWS_REGION`.

**LLM fix:** Removed `AWS_REGION = "us-east-1"` from the Lambda's environment variables in `transcribe.tf`. Lambda sets `AWS_REGION` automatically from the function's configured region — you can't override it.

**My evaluation:** Fast fix. AWS Lambda reserves several environment variable names (`AWS_REGION`, `AWS_ACCESS_KEY_ID`, etc.) — they're injected by the runtime.

---

### 42. ALB Controller Helm Install — Cluster Name ARN Issue

**What I asked:** `terraform.yml` ALB controller install step failed with `InvalidParameterException: The parameter name contains invalid characters`.

**LLM analysis:** `kubectl config view --minify -o jsonpath='{.contexts[0].context.cluster}'` returned the full ARN (`arn:aws:eks:us-east-1:388691194728:cluster/eks-ezvrmopo-okl`) instead of just the cluster name. The Helm `--set clusterName=` flag and `aws eks describe-cluster --name` both expect the short name.

**LLM fix:** Added `CLUSTER_NAME="${RAW_CLUSTER##*/}"` to strip the ARN prefix using bash parameter expansion.

**My evaluation:** Clean fix. The kubeconfig stores clusters by ARN when created via `aws eks update-kubeconfig`. This is a local-vs-CI divergence — locally you might have the short name, CI gets the ARN.

---

### 43. Deploy Smoke Test — DNS Resolution Timeout

**What I asked:** `deploy.yml` smoke test failed with curl exit code 6 (DNS resolution failure) on the new ALB hostname.

**LLM analysis:** New ALBs take 1-3 minutes for DNS to propagate. The existing `curl --retry 5 --retry-delay 10` only retries on HTTP errors, not DNS failures.

**LLM fix:** Added a DNS resolution wait loop (up to 3 min with `nslookup`) before the curl, and added `--retry-all-errors` to curl so it retries on DNS failures too. Gracefully skips the smoke test if DNS doesn't resolve.

**My evaluation:** Good resilience improvement. The smoke test is informational — it shouldn't fail the whole deploy just because DNS hasn't propagated yet.

---

### 44. GitHub Actions Secret Masking — `AWS_REGION` Breaks ALB URLs

**What I asked:** The deployment summary showed `k8s-retentio-retentio-08beda03dc-1707420489.***.elb.amazonaws.com` — the region was masked with `***`.

**LLM analysis:** `AWS_REGION` was stored as a GitHub **secret**, so GitHub Actions masked every occurrence of `us-east-1` in all logs and summaries — including inside the ALB hostname. A region is not sensitive data.

**LLM fix:** Changed all 5 workflow files from `${{ secrets.AWS_REGION }}` to `${{ vars.AWS_REGION }}`. Variables are not masked in output.

**Post-fix steps (manual):** Added `AWS_REGION` as a repository variable (`us-east-1`) and deleted the `AWS_REGION` secret.

**My evaluation:** Root cause correctly identified. The `vars` vs `secrets` distinction is important: secrets get masked everywhere (even inside unrelated strings like hostnames), variables don't. Region, account ID, and cluster names should be variables, not secrets.

---

### 45. Full Pipeline Rebuild — End-to-End Validation

**What I did:** After all fixes, executed the full 3-step rebuild:

1. **Terraform Apply** (Workflow #1) — Created remaining resources (ALB controller policy attachment, transcribe policy, Lambda, Lambda permission, S3 notification), installed ALB controller via Helm
2. **SageMaker Deploy** (Workflow #2) — Validated existing endpoints (churn-predictor, retention-sentiment-analysis) — both InService, skipped redeployment
3. **Build & Roll Out to EKS** (Workflow #3) — Built 4 Docker images, pushed to GHCR, deployed to EKS, applied ingress, ALB provisioned

**Result:** All 3 workflows completed successfully. Frontend accessible at `http://k8s-retentio-retentio-08beda03dc-1707420489.us-east-1.elb.amazonaws.com`.

**Key insight:** The full teardown → rebuild cycle exposed 7 issues (Tasks 39–44) that would never surface in normal incremental deploys. This is exactly why teardown testing is valuable.

---

## Instances Where I Provided Guidance (Session 2)

### 6. Cherry-Pick vs Branch Workflow

**Situation:** Two commits (transcribe description fix + finalizer fix) were pushed to `troy/teardown-workflow` after PR #64 was already merged. They were orphaned — not on main.
**LLM action:** Cherry-picked both commits onto main and pushed directly (bypassing branch protection as repo admin).
**My evaluation:** Right approach for hotfixes during active pipeline testing. Would use a PR for non-urgent changes.

### 7. Direct-to-Main for CI Iteration

**Situation:** Every workflow fix required a commit to main before CI could pick it up. Creating PRs for each iteration would have been 10+ PRs in one session.
**My decision:** Pushed directly to main using admin bypass for all Session 2 fixes. This was a conscious choice for iteration speed during pipeline testing — not a permanent workflow change.

---

## Running List of Changes (Session 2 — April 11, 2026)

| Commit | File(s) | Change |
|--------|---------|--------|
| `447a007` | `terraform/alb-controller.tf`, `k8s/ingress.yaml`, `k8s/services/frontend-service.yaml`, `scripts/install-alb-controller.sh` | ALB Ingress architecture — single ALB replaces per-service LoadBalancers |
| `232ab88` | `frontend/nginx.conf`, `frontend/Dockerfile`, `k8s/configmaps/agent-config.yaml`, `k8s/deployments/qa-evaluator-deployment.yaml` | Nginx reverse proxy, correct service URLs, SageMaker endpoint name |
| `71667b2` | `services/agent-service/chains/churn_analysis.py`, `requirements.txt` | ChatBedrock `model=` → `model_id=`, `region=` → `region_name=`, pin pydantic<2.0 |
| `f083df9` | `terraform/alb-controller.tf` | Add DescribeListenerAttributes IAM permission |
| `6492fe0` | `.github/workflows/deploy.yml`, `.github/workflows/terraform.yml` | Correct deploy summary URLs, default terraform env to dev on PR |
| `577fb7e` | `terraform/alb-controller.tf`, `k8s/ingress.yaml` | Revert Copilot review suggestions that broke working config |
| `a5fc0fb` | `.github/workflows/teardown.yml` | Safe teardown workflow with scope options and safety gate |
| `9c4be1e` | `.github/workflows/terraform.yml` | Automate ALB controller Helm install as post-apply step |
| `e87d2df` | `.github/workflows/teardown.yml` | Remove OIDC provider from teardown targets to preserve IRSA |
| `0d0ac6a` | `.github/workflows/terraform.yml` | Gate ALB install to dev env, derive cluster name from kubeconfig |
| `9ba54f3` | `terraform/transcribe.tf` | Add description to transcribe_lambda_role to match AWS |
| `3e802da` | `.github/workflows/teardown.yml` | Handle stuck ingress finalizer with timeout + force-remove |
| `bd4269c` | `terraform/transcribe.tf` | Remove reserved `AWS_REGION` env var from Lambda config |
| `a26a02e` | `.github/workflows/terraform.yml` | Extract short cluster name from ARN for Helm install |
| `36e1c7b` | `.github/workflows/deploy.yml` | Add DNS resolution wait before ALB smoke test |
| `6ff4bcb` | All 5 workflow files | Move `AWS_REGION` from secrets to vars to prevent URL masking |

---

## Session 3 — April 13, 2026

### 46. CI Post-Merge Path Fix — `sentiment-predictor-api` → `sentiment-analysis-api`

**What I asked:** `ci-post-merge.yml` failed with `cd services/sentiment-predictor-api: No such file or directory`. Fix it.

**LLM analysis:** The workflow matrix referenced `services/sentiment-predictor-api` in two places (unit-tests and docker-build-check jobs), but the actual directory is `services/sentiment-analysis-api`.

**LLM fix:** Updated both matrix entries in `ci-post-merge.yml` from `sentiment-predictor-api` to `sentiment-analysis-api`.

**My evaluation:** Straightforward path mismatch. The directory was likely renamed at some point and the workflow wasn't updated.

---

### 47. Terraform State Imports — 6 Pre-Existing AWS Resources

**What I asked:** `terraform apply` failed with "already exists" errors on multiple resources. Import them.

**LLM actions:**

1. Ran `terraform init -upgrade` to update provider lock (5.100.0 → 6.40.0)
2. Imported 6 resources into Terraform state:

| Resource | Import ID | Notes |
|----------|-----------|-------|
| `aws_bedrockagent_agent.bedrock_agent` | `GOKJIPPKQW` | Bedrock Agent |
| `aws_bedrock_guardrail.sentiment_guardrail` | `p5vveaor3pg2,DRAFT` | Required `guardrail_id,DRAFT` format |
| `aws_bedrockagent_agent_alias.bedrock_endpoint` | `S9NJTXGPP1,GOKJIPPKQW` | Required `alias_id,agent_id` (not `agent_id,alias_id`) |
| `aws_eks_cluster.main` | `eks-ezvrmopo-okl` | EKS cluster |
| `aws_eks_node_group.main` | `eks-ezvrmopo-okl:retention-ng` | EKS node group |
| `aws_iam_role.eks_cluster_role` | `eks-cluster-role` | IAM role |
| `aws_iam_role.eks_node_role` | `eks-node-role` | IAM role |

3. Fixed Bedrock Agent role replacement: the associated IAM role had been deleted from AWS, causing the agent to force-replace (blocked by active aliases). Fixed by doing a targeted apply of just the role first.
4. Force-unlocked a stale state lock: `terraform force-unlock -force b9b8377b-...`

**Result:** `terraform plan` returned **No changes** — state fully in sync.

**My evaluation:** Tedious but necessary. The Bedrock alias import format (`alias_id,agent_id`) was counterintuitive — had to reverse the order after the first attempt failed. The targeted role apply to prevent agent replacement was a good strategy.

---

### 48. SageMaker Sentiment Endpoint — git-lfs Pointer File in Model Tar

**What I asked:** The sentiment endpoint was failing. Investigate and fix.

**LLM analysis:** `pytorch_model.bin` was 134 bytes — a git-lfs pointer file instead of the real 256MB model weights. The `model.tar.gz` uploaded to S3 contained the pointer, so SageMaker was loading garbage.

**LLM fix (multi-step):**

1. Installed `git-lfs` and ran `git lfs pull` to download the real 256MB weights
2. Repackaged `model.tar.gz` with the correct binary
3. Re-uploaded to `s3://retention-engine-bucket/models/sentiment/model.tar.gz`
4. Deleted and recreated the SageMaker model + endpoint config to force the new tar
5. Triggered endpoint update

**My evaluation:** Root cause correctly identified. The LFS pointer issue is a common CI trap — any checkout without `lfs: true` produces broken model files.

---

### 49. Prevent Future LFS Pointer Deployments

**What I asked:** The workflow kept re-deploying the broken model because `sagemaker-deploy.yml` didn't pull LFS files. Harden the pipeline.

**LLM fixes (3 changes):**

1. **`sagemaker-deploy.yml`** — Added `lfs: true` to the `actions/checkout@v4` step so CI pulls real LFS files
2. **`sagemaker/sentiment/deploy.py` — LFS guard** — Added a check in `package_model()`: if `pytorch_model.bin` is < 1024 bytes and contains "git-lfs", raise `RuntimeError` immediately instead of packaging a broken tar
3. **`sagemaker/sentiment/deploy.py` — InService skip** — Added `describe_endpoint` check at the top of `__main__` (matching churn's pattern): InService → exit, Updating/Creating → wait, Failed → redeploy, Not found → create

**My evaluation:** Defense in depth. The LFS checkout prevents the issue at the source, the guard catches it if checkout fails, and the InService skip avoids unnecessary redeployments.

---

### 50. deploy.yml Docker Build Path Fix — Same `sentiment-predictor-api` Bug

**What I asked:** `docker/build-push-action@v5` failed with `path "services/sentiment-predictor-api" not found` in `deploy.yml`.

**LLM fix:** Updated `deploy.yml` matrix `context` from `services/sentiment-predictor-api` to `services/sentiment-analysis-api`. Same root cause as Task 46 — the path was wrong in a different workflow file.

**My evaluation:** Consistent fix across all workflows. This was the last occurrence of the old directory name.

---

## Instances Where I Provided Guidance (Session 3)

### 8. Terraform Import Order

**Situation:** The Bedrock Agent kept showing force-replacement because its IAM role was deleted from AWS.
**My process:** The LLM identified the missing role as the root cause and proposed a targeted `terraform apply -target` to recreate just the role before the full apply. I confirmed this approach rather than deleting the agent alias (which would have caused downtime).

### 9. InService Skip Pattern

**Situation:** The sentiment `deploy.py` lacked the InService skip that churn's deploy.py already had.
**My decision:** Told the LLM to match the churn pattern exactly — same status checks, same waiter config, same exit behavior. Consistency across both deploy scripts makes maintenance easier.

---

## Running List of Changes (Session 3 — April 13, 2026)

| Commit | File(s) | Change |
|--------|---------|--------|
| `93fb460` | `.github/workflows/ci-post-merge.yml` | Fix `sentiment-predictor-api` → `sentiment-analysis-api` in unit-tests and docker-build matrices |
| `25c4758` | `.github/workflows/sagemaker-deploy.yml`, `sagemaker/sentiment/deploy.py` | Add `lfs: true` to checkout; add LFS guard + InService skip to sentiment deploy.py |
| `86e44e6` | `sagemaker/sentiment/deploy.py` | Refine InService skip logic and LFS guard in sentiment deploy |
| `c9f0cdc` | `.github/workflows/deploy.yml` | Fix Docker build context path `sentiment-predictor-api` → `sentiment-analysis-api` |

**Terraform state changes (not committed — remote S3 state):**
- Imported 6 resources: Bedrock Agent, Bedrock Guardrail, Bedrock Agent Alias, EKS Cluster, EKS Node Group, 2 IAM Roles
- Targeted apply to recreate deleted Bedrock IAM role
- Force-unlocked stale state lock
- Final state: fully in sync, `terraform plan` shows no changes

**SageMaker manual operations:**
- Re-uploaded correct `model.tar.gz` (256MB real weights) to S3
- Deleted and recreated SageMaker model + endpoint config
- Triggered endpoint update with correct model artifacts

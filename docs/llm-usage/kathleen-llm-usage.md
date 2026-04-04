# LLM Usage Log — Kathleen

**Tool:** Claude Code (Claude Opus 4.6, CLI + VS Code extension)
**Period:** March 30 – April 4, 2026

---

## Summary

Used Claude Code as a pair programming partner throughout the capstone project. The LLM assisted with architecture planning, model training, API development, frontend design, SageMaker deployment, and debugging. In every case, output was reviewed, tested, and adapted — not blindly accepted.

---

## Issues & Debugging Log

### Issue 1: Git Repository Setup — Empty Repo Default Branch
**Problem:** Cloned an empty repo, pushed `feat/project-roadmap` as the first branch. GitHub set it as the default branch instead of `main`, causing PRs to target the wrong base.
**LLM Recommendation:** Create an empty `main` branch with `git checkout --orphan main`.
**Resolution:** Worked, but required `--allow-unrelated-histories` to merge. Later, team fixed the default branch in GitHub Settings.

### Issue 2: Jupyter Kernel Not Found in VS Code
**Problem:** VS Code kernel picker kept spinning, no kernels listed. Tried `sklearn-env` conda environment — missing `ipykernel`.
**LLM Recommendation:** Install `ipykernel` into the conda env via `conda install -n sklearn-env ipykernel`.
**My Guidance:** Conda env didn't actually exist. I directed Claude to try a different approach.
**Resolution:** Installed packages into `.venv`, registered as `churn-venv` kernel, ran notebook in browser via `jupyter notebook` instead of VS Code.

### Issue 3: XGBoost Import Error — Missing libomp
**Problem:** `XGBoostError: libxgboost.dylib could not be loaded. OpenMP runtime is not installed.`
**LLM Recommendation:** `brew install libomp`
**Resolution:** Worked after kernel restart.

### Issue 4: Team Stepping on Each Other's Files
**Problem:** Multiple team members editing the same files (Terraform, K8s manifests, agent service code), causing merge conflicts.
**My Guidance:** I asked Claude to help establish lane ownership rules.
**Resolution:** Created clear directory ownership table — each person only touches their own directories. Communicated to team.

### Issue 5: PR Workflow Confusion — Merging and Pulling
**Problem:** Team didn't understand that merging a PR on GitHub doesn't update local repos. Changes not appearing locally after merge.
**LLM Recommendation:** Explained `git pull origin main` workflow and fast-forward merges.
**My Guidance:** Asked Claude to explain what a fast-forward is in simple terms.

### Issue 6: SageMaker Deploy — Wrong S3 Bucket
**Problem:** `NoSuchBucket` error when uploading model.tar.gz. Deploy script used `retention-engine-transcript-dev`.
**LLM Recommendation:** Updated to correct bucket name.
**Resolution:** Found actual bucket `retention-engine-bucket` via `aws s3 ls`. Later changed to `sagemaker-us-east-1-388691194728` for IAM compatibility.

### Issue 7: SageMaker Deploy — IAM Role S3 Permissions
**Problem:** `Could not access model data at s3://...` — SageMaker execution role didn't have S3 access to `retention-engine-bucket`.
**LLM Recommendation:** Switch to `AmazonSageMaker-ExecutionRole-20260224T095369` which has broader permissions.
**Resolution:** Worked — this role's policy covers `sagemaker-*` buckets.

### Issue 8: SageMaker Deploy — "No module named 'inference'" (5 attempts)
**Problem:** The sklearn container kept failing with `ModuleNotFoundError: No module named 'inference'` even though `pip install .` succeeded.
**LLM Recommendations (in order):**
1. Put inference.py in `code/` directory → Failed
2. Add `setup.py` with `py_modules=["inference"]` → Failed
3. Add `requirements.txt` in `code/` → Failed (container only runs `pip install .`)
4. Remove pandas dependency from inference.py → Failed (same error)
5. Add `SAGEMAKER_SUBMIT_DIRECTORY` env var → Failed

**My Guidance:** After 5 failures, I asked Claude to "evaluate every possible issue that could be causing this, along with solutions and probability of success" instead of trying one fix at a time.

**LLM Analysis:** Identified 4 root causes with probability rankings. Recommended switching to XGBoost container + native model format as highest probability fix.

**Resolution path:**
- Switched to `sagemaker-xgboost:1.7-1` container → Still got `No module named 'inference'`
- Removed inference.py entirely, used native XGBoost serving → Got `invalid load key` because container tried to load `feature_columns.json` as a model
- **Final fix:** Only include `xgboost-model` in tar.gz, move JSON files to FastAPI wrapper → **SUCCESS**

**Key Learning:** The SageMaker container module loading mechanism is poorly documented. The fix required understanding that (a) the container tries to load ALL files as models, and (b) native serving doesn't need a custom inference script. This was the most frustrating debugging session — 6 deploy attempts, each taking 10-15 minutes.

### Issue 9: Frontend Unicode Escape Sequences
**Problem:** Emojis rendered as raw text like `\uD83D\uDCCA` instead of actual icons.
**LLM Recommendation:** Replace with actual emoji characters.
**My Guidance:** Asked to use professional SVG icons from a library instead of emojis — more appropriate for an internal corporate tool.
**Resolution:** Installed `lucide-react` for clean SVG icons.

### Issue 10: Frontend Dropdown Not Working — CORS
**Problem:** Customer dropdown wouldn't populate. Browser console showed CORS errors.
**LLM Recommendation:** Add CORS middleware to churn-predictor-api.
**Resolution:** Added `CORSMiddleware` with `allow_origins=["*"]`.

### Issue 11: Frontend Missing Files After Cherry-Pick
**Problem:** After messy branch operations, `index.html`, `vite.config.ts`, `tsconfig.json`, `main.tsx`, `index.css` were missing from the frontend directory.
**My Guidance:** Asked if we needed to revert.
**Resolution:** No revert needed — recreated the missing files.

### Issue 12: Customer Combobox — Can't Change After First Selection
**Problem:** After running analysis, clicking the customer field didn't reset — couldn't select a new customer.
**LLM Recommendation:** Clear query state on focus.
**Resolution:** Added `onFocus={() => { setQuery(""); setOpen(true); }}`.

### Issue 13: Agent 1 Data Not Loading — S3 Upload Missing
**Problem:** All customers showing "Neutral" sentiment with 0.00 frustration/anger, even customers with call data.
**Resolution:** Agent 1 synthetic CSV wasn't uploaded to S3. Uploaded it and restarted API.

---

## Instances Where I Provided Guidance or Changed LLM Recommendations

### 1. Team Role Assignments
**LLM Default:** Assigned Kathleen to QA Evaluator (Endpoint 1), Okino to Churn Predictor (Endpoint 2).
**My Change:** Swapped — I took Churn Predictor, Okino took QA Evaluator. Claude updated all roadmap references.

### 2. Orchestration Ownership
**LLM Default:** Roadmap assigned LangChain orchestration to George.
**My Change:** Told Claude that Okino and I own the orchestration, not George. Claude updated project memory and all related files.

### 3. Agent 1 Feature Selection
**LLM Recommendation:** Use 3 features from Agent 1 (qa_score, sentiment, frustration_level).
**My Guidance:** Reviewed Okino's example_output.json, identified additional useful fields. Suggested replacing `frustration_level` with `emotion_scores.frustration` and adding `emotion_scores.anger`.
**Outcome:** Model retrained with 7 Agent 1 features instead of 3. AUC improved 0.9808 → 0.9861.

### 4. Frontend — Hardcoded Customer IDs
**My Feedback:** "Why are you listing customer IDs and not accessing an API? Can we make an API?"
**Outcome:** Added `/customers` endpoint to churn-predictor-api, frontend now loads from API.

### 5. Frontend — Emojis vs Professional Icons
**My Feedback:** Asked to use Flaticon or similar instead of emojis for a corporate tool.
**Outcome:** Installed lucide-react for clean SVG icons.

### 6. Customer Dropdown vs Text Input
**LLM Recommendation:** Searchable text input where user types customer ID.
**My Feedback:** "I don't know the nomenclature to type that in, I think a dropdown with search would be better."
**Outcome:** Changed to dropdown that loads on page load, filters as you type.

### 7. Agent Guardrails — Product Catalog
**My Suggestion:** "Should Agent 3 have a specific set of concrete actions so it doesn't offer upgrades that don't exist?"
**Outcome:** Added TriLink product catalog (real plan tiers and pricing) and approved retention actions per risk level to the system prompt. Added output validation guardrail.

### 8. SageMaker Debugging Approach
**My Feedback:** After 5 failed deploy attempts, instead of letting Claude try another single fix, I said "evaluate every possible issue that could be causing this, along with solutions and probability of success."
**Outcome:** Claude provided a structured analysis with 4 root causes ranked by probability. This led directly to the working solution (XGBoost container + native model format).

### 9. No Co-Author Tags
**My Feedback:** Rejected a commit that included `Co-Authored-By: Claude` line.
**Outcome:** Claude saved this as a persistent memory and never added it again.

### 10. PR Workflow — New Branch Every Time
**My Feedback:** "You keep trying to let old PRs capture new pushes. Make a feature branch and a PR every time!"
**Outcome:** Claude adopted the pattern of creating a new feature branch and PR for each set of changes.

### 11. Chat Interface Requirement
**My Observation:** Identified from the rubric that we need "a user-facing chat agent powered by AWS Bedrock with a frontend interface" — not just an analysis dashboard.
**Outcome:** Added Chat tab to the frontend with conversational interface.

### 12. High-Risk Customer Tool
**My Suggestion:** "We would also have questions like: show me my high risk customers, is this another tool to add?"
**Outcome:** Added `get_high_risk_customers` LangChain tool, `/high-risk` API endpoint, and smart chat fallback handling.

---

## Critical Evaluation

### What I Accepted
- Project roadmap structure and phased approach
- XGBoost model training pipeline (standard ML workflow)
- FastAPI wrapper architecture with internal data lookup
- React + Vite + Tailwind stack (familiar from prior coursework)
- LangChain tool-calling agent pattern

### What I Rejected or Modified
- Hardcoded customer lists → API-driven dropdown
- Emoji icons → Professional Lucide SVG icons
- Text input for customer ID → Searchable dropdown
- Generic retention actions → TriLink-specific product catalog with guardrails
- Single-fix debugging → Systematic root cause analysis
- Reusing old PRs → New branch + PR every time
- Co-author attribution → Removed

### What I Would Do Differently
- Start with the XGBoost container from the beginning instead of sklearn (would have saved 6 deploy attempts)
- Upload Agent 1 synthetic data to S3 immediately instead of relying on local file paths
- Set up docker-compose for local development earlier in the project
- Establish stricter PR review process — too many files were modified outside lane ownership

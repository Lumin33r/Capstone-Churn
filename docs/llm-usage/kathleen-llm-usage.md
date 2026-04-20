# LLM Usage Log — Kathleen

**Tool:** Claude Code (Claude Opus 4.6, CLI + VS Code extension)
**Period:** March 30 – April 19, 2026

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

### Issue 14: Repeated File Loss During Branch Operations
**Problem:** Frontend files (index.html, vite.config.ts, tsconfig.json, main.tsx, index.css, Dockerfile, nginx.conf) kept getting lost across branch switches, cherry-picks, and stash pops. Files would exist on one branch but not carry over to new branches created from main. This happened at least 3 times, requiring full recreation of the frontend scaffold each time.
**Root Cause:** A combination of: (1) cherry-picking commits that created files not tracked on main, (2) stash conflicts on files that existed locally but not in the branch, (3) pushing to PRs that got merged, then creating new branches from main that didn't have the latest frontend code.
**My Guidance:** After the third occurrence, I told Claude to stop trying complex git operations and just recreate the files directly.
**Resolution:** Recreated missing files each time. The core issue was that our PR workflow kept branching from main, but main didn't always have the latest frontend code merged yet. Files committed on feature branches would disappear when switching back to main.
**Key Learning:** When multiple feature branches are in flight and PRs merge asynchronously, always verify that your files exist on the current branch before starting work. Don't assume a file from a previous branch carried over.

### Issue 15: Stale PRs Capturing Unrelated Commits
**Problem:** Claude kept pushing new commits to existing open PRs instead of creating new feature branches. This meant PRs accumulated unrelated changes — a deploy fix PR would end up with frontend code, orchestration changes, and roadmap updates bundled together.
**My Guidance:** "You keep trying to let old PRs capture new pushes. Make a feature branch and a PR every time!"
**Resolution:** Established the rule: every new set of changes gets a fresh `git checkout main && git pull && git checkout -b feat/kathleen-<description>` and a new PR.
**Key Learning:** Each PR should be a clean, focused unit of work. Reusing branches across multiple tasks makes reviews harder and increases conflict risk.

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

---

## Session 2 Work (April 7, 2026)

### LangSmith Integration
- Set up free tier account at smith.langchain.com
- Created `retention-engine` project for trace collection
- Configured via `.env` file (LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT)
- API key stored in GitHub Secrets (`gh secret set LANGCHAIN_API_KEY`)
- Verified traces visible in LangSmith dashboard showing tool calls, latency, token usage
- **My guidance:** Asked about embedding in our UI vs separate dashboard. Claude recommended separate dashboard — sufficient for rubric.

### LangGraph Implementation
- Replaced AgentExecutor with explicit LangGraph state graph
- Nodes: classify → model → tools → respond
- Conditional edges based on whether tools are needed
- Added MemorySaver checkpointer for conversation memory across messages
- **Issue:** Initial implementation lost conversation context between messages — LLM forgot which customer was being discussed
- **Fix:** Added `MemorySaver` checkpointer with `thread_id` for session-based persistence
- **Issue:** System prompt was too short — agent freely chose actions instead of being constrained to approved list
- **My guidance:** Noticed in LangSmith traces that the agent wasn't selecting from the approved retention actions. Asked Claude to update the system prompt with explicit action selection rules.

### Batch Prediction Optimization
- `/high-risk` endpoint was calling SageMaker individually for 20,571 customers (~34 min)
- Implemented batch CSV prediction: 500 rows per SageMaker call
- Added in-memory cache: first call ~30 seconds, subsequent calls <100ms
- **My guidance:** Identified the performance problem during demo testing ("this is taking forever"). Asked Claude to evaluate optimization approaches.

### Frontend Tab Memory Fix
- **Bug I found:** Switching between Analyze and Chat tabs wiped the state in both
- **Fix:** Changed from conditional rendering (`{tab === "analyze" ? <A/> : <B/>}`) to CSS hidden (`<div className={tab === "analyze" ? "" : "hidden"}>`) so both tabs stay mounted

### PR #46 Review — Cross-Service File Conflicts
- Identified that the PR included changes to `services/churn-predictor-api/` along with the sentiment service rename
- Renames `qa_tool.py` → `sentiment_tool.py` and restructures `services/` → `backend/`
- **My guidance:** Requested changes on the PR — coordinated to avoid overwriting each other's services
- Created `.backup/` directory to protect critical files from branch conflicts
- Tested the live SageMaker sentiment endpoint — identified that the output format needed additional enrichment fields for the churn predictor integration

### Rubric Audit
- Conducted full audit of all 10 rubric areas against current implementation
- Identified CI/CD (0%) and Documentation (20%) as highest risk areas
- **My guidance:** Recommended Troy proceed with CI/CD immediately despite ongoing code changes — workflows are in an isolated directory

---

## Instances Where I Provided Guidance — Session 2

### 13. Tab Memory Persistence
**Bug I found:** Switching between Analyze and Chat tabs reset all state.
**Outcome:** Changed rendering approach to keep both tabs mounted.

### 14. LangSmith vs Embedded Observability
**My question:** "Should we put it in our interface as another tab?"
**Outcome:** Separate dashboard is sufficient — no need to embed.

### 15. LangGraph Action Selection
**My observation:** Noticed in LangSmith traces that the agent wasn't choosing from the approved action list.
**Outcome:** Updated system prompt with explicit action codes and selection rules.

### 16. High-Risk Performance
**My observation:** "The show me high risk customers question is taking forever."
**Outcome:** Batch prediction + caching implemented.

### 17. Protecting Code from PR Deletions
**My guidance:** After discovering file conflicts across PRs, created `.backup/` and established the rule: always verify files exist on current branch before starting work.

### 18. Not Making Assumptions About Teammate's Code
**My guidance:** When Claude offered to rewrite the sentiment tool to call the SageMaker endpoint directly, I said "No, I don't want to make those assumptions. We will work it through this evening."

### 19. Frankenstein PR — Cherry-Picking Across Branches
**Situation:** PR #46 had useful new sentiment files alongside directory restructuring. PR #47 had our LangGraph/LangSmith work. Neither could merge cleanly due to overlapping file changes.
**My guidance:** Asked Claude to cherry-pick the sentiment files from one branch, combine with our code from backups, and create a single consolidated PR #48. Closed both #46 and #47.
**Outcome:** Clean PR with all components working together. Required manual verification that every file from both PRs was included.

### 20. Defending Working Code
**Situation:** Troy and Okino suggested uploading label encoders to S3 and restructuring the endpoint invocation pattern.
**My guidance:** "The label encoders are already hardcoded in app.py and the endpoint is live and tested. Don't restructure something that's working."
**Outcome:** Kept the working implementation. Avoided unnecessary complexity before presentation.

### 21. Model Drift as Stretch Goal
**My question:** "Is there SageMaker model drift tracking we can implement?"
**Claude's options:** Full SageMaker Model Monitor (4+ hours) vs lightweight `/drift` endpoint (30 min).
**My decision:** Added to roadmap as stretch goal rather than implementing now — presentation prep is higher priority.

---

### What I Would Do Differently
- Start with the XGBoost container from the beginning instead of sklearn (would have saved 6 deploy attempts)
- Upload Agent 1 synthetic data to S3 immediately instead of relying on local file paths
- Set up docker-compose for local development earlier in the project
- Establish stricter PR review process — too many files were modified outside lane ownership
- Use LangGraph from the start instead of AgentExecutor — the explicit state graph is easier to reason about and debug
- Set up LangSmith from Day 1 — would have caught the action selection issue much earlier

---

## Session 3 Work (April 9–11, 2026)

### Churn Endpoint Recovery
- Troy redeployed SageMaker endpoints via Terraform, which broke the churn predictor
- **Root cause:** Terraform `sagemaker.tf` defined the endpoints, but our `deploy.py` also managed them. When Troy ran `terraform apply`, it destroyed and recreated the churn endpoint with an `inference.py` that garbled CSV input
- **My analysis:** Asked Claude to check CloudWatch logs. Identified `ValueError: could not convert string to float` — the inference.py was corrupting raw bytes
- Redeployed using our original `deploy.py` (native XGBoost, no inference.py) — endpoint restored
- **Resolution:** Added churn endpoint to `sagemaker.tf` initially, then agreed with Troy to remove ALL SageMaker resources from Terraform. Endpoints now managed exclusively by `sagemaker-deploy.yml` GitHub Actions workflow. Single owner per resource prevents conflicts.

### Systematic PR Review Process
- Reviewed a large PR (132k additions) across k8s, Terraform, sentiment service, model artifacts
- **My approach:** Organized review into categories: Blocking (will break), Merge Conflicts, Structural (won't break immediately but creates problems), and Positive (acknowledge good work)
- Led with positives (guardrails, EKS, k8s services), then blocking items with specific file/line references
- **Key findings:**
  - Env var naming inconsistency across configmap, docker-compose, and code — three names for one value
  - Cross-service imports that won't resolve in Docker containers
  - API output format needed alignment with downstream consumers
  - Directory restructuring would break existing docker-compose and CI/CD references
- **My guidance:** Asked Claude to walk through each issue with multiple solution options, then compiled into a single structured review comment on the PR

### Amazon Transcribe Pipeline (Stretch Goal)
- Built as an independent workstream while the sentiment endpoint integration was in progress
- **Lambda function:** S3 audio upload → Amazon Transcribe job with speaker diarization (2 speakers) → transcript saved to S3
- **Deploy script:** Standalone `deploy_lambda.py` using boto3 (not Terraform) — cleaner for Lambda-specific logic
- **API endpoints:** Added `/transcribe`, `/transcripts`, `/transcripts/{name}` to churn predictor API
- **Frontend:** New Transcribe tab (third tab) — file upload, transcript list, speaker-segmented viewer
- **Bug found:** Transcribe outputs speaker labels differently than expected. The `speaker_labels.segments.items` array only has timestamps — the actual text content is in the top-level `results.items` array with `speaker_label` on each item. Fixed the parser to read from the correct location.
- **Speaker label logic:** Initially defaulted single-speaker transcripts to "Agent". I caught this — a single speaker saying "I'm experiencing an issue with your product" is clearly a customer. Changed to: two speakers = Agent/Customer, one speaker = "Speaker".

### LangGraph Strategist Node
- **Troy's concern:** Questioned whether our LangGraph flow was truly "agentic" vs just a pipeline
- **My analysis:** The flow IS agentic — Claude selects tools based on the question, can skip tools, can chain multiple tools, can loop. But it's predictable in practice because inputs are structured.
- **My question:** "Should we add another agent responsible for evaluating the churn risk and determining the best recommendation?"
- **Outcome:** Added a Retention Strategist node to the graph — a second LLM call with a different system prompt focused on action selection. No new service needed, just a new node in the existing graph.
- **Design decision:** Strategist uses base LLM without tools (reasoning only). Creates two distinct LLM calls visible in LangSmith: Gatherer (collects data) → Strategist (recommends action).
- **Rubric alignment:** Re-read the assessment requirements. The rubric says "orchestration layer" and "chains or agents" — not "multiple agents." SageMaker endpoints are endpoints, not agents. The single LangGraph orchestrator with multi-step reasoning IS the agentic behavior the rubric asks for.

### Version Conflicts — LangChain/LangGraph
- Troy's CI/CD workflow was failing on `pip install` due to version conflicts
- **Root cause:** `requirements.txt` had `langchain==0.3.0` but `langgraph>=0.2.0` — these version-lock `langchain-core` and conflicted
- Updated to match our working local versions: `langchain>=1.2.0`, `langchain-aws>=1.2.0`, `langgraph>=1.0.0`, `langsmith>=0.6.0`

---

## Instances Where I Provided Guidance — Session 3

### 22. Terraform vs deploy.py Ownership
**Situation:** Troy removed all SageMaker resources from `sagemaker.tf`. I initially wanted Terraform to manage them for the rubric.
**My realization:** The roadmap already documents `sagemaker-deploy.yml` as the endpoint manager. Having both caused the exact conflict that broke the endpoint. One owner per resource is correct.
**Outcome:** Approved Troy's change.

### 23. Systematic PR Review
**My approach:** Instead of commenting on individual lines, organized the review into prioritized categories (Blocking → Conflicts → Structural → Positive). Asked Claude to compile multiple solution options for each issue.
**Outcome:** Posted comprehensive review with actionable steps for each issue.

### 24. Transcribe Speaker Labels
**My observation:** Single-speaker transcript was labeled "Agent" — wrong assumption. A person saying "I have an issue with your product" is a customer.
**Outcome:** Changed logic: two speakers = Agent/Customer (first speaker is agent), one speaker = neutral "Speaker" label.

### 25. Questioning "Agentic" Architecture
**My concern:** "I just don't think agents 1 and 2 are agents. They are just endpoints."
**Outcome:** Re-read the rubric requirements carefully. Confirmed the rubric uses "agent" only for the orchestration layer, calls SageMaker components "endpoints." Correct framing matters for the presentation.

### 26. Strategist vs New Service
**My question:** Should the strategist be a separate service (true multi-agent) or a node in the existing graph?
**Claude's recommendation:** Node in the existing graph — 30 minutes vs a full new service, less risk before demo.
**My decision:** Agreed. One graph with two reasoning phases is architecturally cleaner and still shows multi-step reasoning in LangSmith.

---

### What I Would Do Differently
- Start with the XGBoost container from the beginning instead of sklearn (would have saved 6 deploy attempts)
- Upload Agent 1 synthetic data to S3 immediately instead of relying on local file paths
- Set up docker-compose for local development earlier in the project
- Establish stricter PR review process — too many files were modified outside lane ownership
- Use LangGraph from the start instead of AgentExecutor — the explicit state graph is easier to reason about and debug
- Set up LangSmith from Day 1 — would have caught the action selection issue much earlier
- Establish single-owner-per-resource rule for infrastructure from Day 1 — would have prevented the Terraform/deploy.py endpoint conflict
- Build the Transcribe pipeline earlier — it's independent of other work and adds AWS service breadth for the rubric

---

## Session 4 Work (April 12–19, 2026)

### Bedrock Guardrail Tuning
- Initially attached the existing `sentiment-analysis-guardrail` to the LangGraph Bedrock calls
- Found it blocked legitimate retention output — words like "cancel," "frustrated," and "churn" triggered the MISCONDUCT and INSULTS filters
- **My analysis:** The guardrail was tuned for transcript input filtering, not agent output. A retention engine MUST discuss frustrated customers and cancellation threats — that's the entire use case.
- **Decision:** Created a new `retention-engine-guardrail` with tuned filters: HATE/SEXUAL kept HIGH, MISCONDUCT and INSULTS lowered to NONE on output, PII switched from BLOCK to ANONYMIZE for email/phone (BLOCK kept for SSN/cards)
- **Architectural decision:** Attached the guardrail only to the Gatherer LLM (input protection), not the Strategist LLM (which generates retention recommendations). Created a second `llm_strategist` instance without the guardrail.
- **Rubric framing for presentation:** "We deployed a Bedrock Guardrail, tested it, and made an informed decision about placement based on the use case." Stronger answer than just "we added a guardrail."

### Sentiment Service Enrichment Layer
- The upstream sentiment SageMaker endpoint returned inconsistent classifications and `qa_score = 0` for all transcripts
- **My decision:** Build an enriched FastAPI wrapper (`app_enriched.py`) that calls the SageMaker endpoint for base sentiment, then computes the remaining 6 fields via NLP post-processing
- **Approach:** Keyword-based emotion scoring (frustration, anger, joy), sentiment_shift via first-half vs second-half text comparison, escalation/resolution detection via phrase matching, composite qa_score formula
- **My guidance:** Asked Claude to make the qa_score start at a baseline of 5.0 and adjust up/down rather than start at 0 and only add — this avoids the trap where every transcript scores 0 because positive contributions are rare
- **Outcome:** Returns all 7 fields the churn predictor needs, in the correct ranges (qa_score 0-10, emotions 0-1, flags as bool)

### Sentiment Model Retraining (Stretch)
- Created `sentiment_revision.ipynb` to retrain DistilBERT as a 3-class classifier (Negative/Neutral/Positive) instead of the original 6-class model
- Trained on Google Colab with T4 GPU
- Improved metrics: accuracy 43.8% → 58.4%, F1 macro 25.2% → 52.3%
- **My decision:** Use this revised model for the demo path while the main team continued iterating on their version
- **Critical evaluation:** The model is still weak (58% accuracy) because the dataset is only 2,500 samples. Hyperparameter tuning would yield diminishing returns — the data size is the bottleneck, not the model configuration. Pushed back when Claude suggested a 20-trial Optuna search.

### Transcript-Aware Workflow
- Built end-to-end transcript flow: Transcribe tab uploads audio with customer ID → S3 stores under `audio/{customer_id}/` → Lambda triggers Transcribe job → output saved to `transcripts/{customer_id}/`
- Added `get_transcripts` LangChain tool so the agent can pull historical transcripts for any customer
- Added saved-transcript dropdown to the Analyze tab — selecting a customer auto-fetches their transcripts from S3, eliminating copy/paste
- **My observation:** The Chat tab's "default" session_id meant all conversations shared MemorySaver state. Identified the issue when customer IDs from prior conversations leaked into general questions. Removed hardcoded customer IDs from tool docstrings to prevent the LLM from referencing specific examples.

### LangGraph Strategist Routing
- Initially the Gatherer was generating both summaries AND recommendations, making the Strategist redundant
- **My guidance:** Strengthened the Gatherer prompt to be strictly factual — "DO NOT recommend actions, DO NOT suggest retention strategies. The Retention Strategist will handle recommendations."
- **Bug found:** The Strategist node wasn't returning content even though it ran. Traced it to the guardrail blocking the Strategist's output. Fixed by giving the Strategist its own LLM instance without the guardrail.
- Added explicit `run_name` parameters to LLM invocations so LangSmith traces clearly label "DataGatherer", "DataGatherer-ReviewTools", and "RetentionStrategist" as distinct runs

### Architecture Diagram for Presentation
- Iteratively refined an architecture diagram for the team presentation
- Used color-coded edges (HTTP, boto3, Bedrock API, S3 events) to reduce visual clutter from labeling every arrow
- Distinguished what runs in K8s (our containerized services) vs managed AWS services (SageMaker, Bedrock, S3, Lambda)
- **My judgment call:** Showed SageMaker endpoints OUTSIDE the K8s boundary because they're AWS-managed. The FastAPI wrappers go inside the boundary because we deploy them as containers. Helped clarify the distinction between "our code" and "managed services."

### Coordinating Multiple Concurrent PRs
- Repeatedly hit conflicts where teammates' PRs deleted or overwrote each other's code
- **My guidance:** Established the pattern of always pulling main before starting work, using fresh feature branches, and writing PR descriptions that listed exactly which files were touched and why
- **Defensive backups:** Continued using `.backup/` to preserve critical files before any branch operation
- **Tactical PR reviews:** When reviewing teammates' PRs, organized feedback into Blocking / Conflicts / Structural / Positive categories. Avoided line-by-line nitpicks; focused on what would break in production.

### Switching to Fallback for End-to-End Demo
- With days remaining and the upstream sentiment endpoint still inconsistent, made the decision to ship our enriched wrapper for the presentation
- **My guidance:** Wrote the PR with explicit reversal instructions — if/when the upstream endpoint produces correct fields, switch the Dockerfile CMD back. This frames our wrapper as a fallback rather than a replacement.
- Verified end-to-end: agent → 5 tools → strategist → recommendation, with all services running locally

---

## Instances Where I Provided Guidance — Session 4

### 27. Tuning the Guardrail vs Removing It
**Initial Claude suggestion:** Disable the guardrail because it blocks retention output.
**My pushback:** "Can we adjust the guardrail for our use case?" — better than just removing it for the rubric.
**Outcome:** Created a tuned guardrail with appropriate filter levels for our domain. Better presentation story.

### 28. Strategist Output Was Empty
**My observation:** Strategist node was firing per logs but returning no content.
**Diagnosis:** The guardrail attached to the Strategist LLM was silently blocking the output containing retention terminology.
**Outcome:** Created `llm_strategist` without guardrail, kept `llm` with guardrail for the Gatherer. Two LLM instances, different protection levels per role.

### 29. Hyperparameter Tuning When Data Is the Bottleneck
**Claude's suggestion:** 20-trial Optuna search across learning rate, batch size, weight decay, warmup ratio.
**My pushback:** "How long would this take? With 2,500 samples, isn't tuning diminishing returns?"
**Outcome:** Skipped the search. Used standard fine-tuning hyperparameters (lr=3e-5, batch=16, 8 epochs, warmup_ratio=0.1). Saved hours of training time.

### 30. Architecture Diagram Boundaries
**My question:** Should SageMaker endpoints be inside the K8s box or outside?
**Claude's explanation:** Outside — SageMaker is AWS-managed, our FastAPI wrappers (which we deploy as containers) are inside K8s. The wrapper is the waiter, the SageMaker endpoint is the kitchen.
**Outcome:** Diagram now correctly shows the deployment topology, which makes the architecture much clearer for non-technical reviewers.

### 31. Sanitizing LLM Usage Docs
**My guidance:** When updating docs, sanitize anything that reads as critical of teammates. Frame issues as "cross-PR conflicts" or "alignment issues" rather than naming individuals.
**Outcome:** Maintained professional tone in docs that will be reviewed by the instructor and potentially shared.

### 32. Demo Resilience
**My decision:** When the upstream sentiment endpoint was still inconsistent days before the demo, I chose to switch to our enriched wrapper rather than wait. Better to demo a working pipeline than risk a broken live demo.
**Framing:** Wrote the PR description with explicit revert instructions so this is positioned as a fallback, not a replacement.

---

### What I Would Do Differently (Session 4 additions)
- Tune the guardrail filters during initial setup, not after discovering they block legitimate output
- Build the enriched wrapper from the start instead of waiting for the upstream endpoint
- Establish role-specific LLM instances earlier — having one `llm` shared across all nodes made it harder to attach different guardrails or configurations per role
- Color-code architecture diagrams from the first draft — much easier to read than text-labeled arrows

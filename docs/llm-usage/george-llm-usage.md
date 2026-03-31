# George (gvill0576) — LLM Usage Documentation
# Capstone-Churn | Assessment V

## Tools Used
- Claude (claude.ai) — primary tool for code generation, debugging, architecture planning
- Used throughout Phase 0 and Phase 1 development

## Documented Examples

### 1. Terraform IAM Policy Structure
**What I asked Claude:** How to write a least-privilege IAM policy for a service
that needs Bedrock InvokeModel and S3 read/write access to a specific bucket.

**What Claude generated:** The jsonencode() block structure with the correct
Action and Resource fields for both Bedrock and S3.

**What I accepted:** The overall structure and the bedrock:InvokeModel action list.

**What I modified:** Changed the S3 Resource from a hardcoded ARN string to
reference the Terraform resource: aws_s3_bucket.data.arn
This makes it dynamic — if the bucket name changes, the policy updates automatically.

**Why:** Hardcoded ARNs break when resource names change. Terraform references
are always in sync with the actual resource.

### 2. LangChain Tool Error Handling
**What I asked Claude:** Show me how to handle httpx timeouts and HTTP errors
separately in a LangChain tool so the agent gets a structured fallback response.

**What Claude generated:** A try/except block with TimeoutException and
HTTPStatusError as separate cases.

**What I accepted:** The exception type separation — TimeoutException vs
HTTPStatusError is the right distinction for network tool calls.

**What I modified:** The error return format. Claude returned a plain string.
I changed it to return a JSON string so the agent can parse it consistently
whether the call succeeded or failed.

**Why:** The agent prompt expects JSON from tool calls. If the tool returns
a plain error string, the agent might hallucinate a response instead of
correctly reporting the failure.

### 3. Kubernetes Health Probe Timing
**What I asked Claude:** What initialDelaySeconds should I use for a FastAPI
service that imports LangChain and boto3 on startup?

**What Claude suggested:** 10 seconds for readiness, 20 seconds for liveness.

**What I accepted:** Both values after verifying against the K8s docs.
LangChain import plus boto3 client initialization typically takes 5-8 seconds.
The 10 second buffer is appropriate.

**What I modified:** Added failureThreshold: 3 explicitly, which Claude omitted.
Without it K8s uses the default of 3 but being explicit is better documentation.

## Critical Evaluation Note
All LLM-generated code was tested locally before committing. Terraform files
were validated with terraform validate. Python imports were verified with
pip install. No code was merged without understanding what each line does.
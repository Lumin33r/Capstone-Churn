# The Retention Engine — Architecture

## System Architecture

```
                                 ┌──────────────────────┐
                                 │    USER / BROWSER     │
                                 └──────────┬───────────┘
                                            │ HTTPS
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│                          Frontend (React + Vite + Tailwind)                             │
│                          Port 3000 / nginx · Lucide React icons                        │
│                                                                                        │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────────────┐  │
│  │   ANALYZE TAB        │  │     CHAT TAB         │  │      TRANSCRIBE TAB          │  │
│  │                      │  │                      │  │                              │  │
│  │  CustomerCombobox    │  │  Conversational AI   │  │  CustomerCombobox            │  │
│  │  (searchable         │  │  interface           │  │  (associate with customer)   │  │
│  │   dropdown)          │  │                      │  │  Audio Upload (.wav/.mp3)    │  │
│  │  Transcript input    │  │  Session memory      │  │  Transcript List (from S3)   │  │
│  │                      │  │  (per session_id)    │  │  Speaker-segmented viewer    │  │
│  │  If transcript:      │  │                      │  │  (Agent / Customer bubbles)  │  │
│  │  1. Sentiment API    │  │  Tries Agent Service │  │                              │  │
│  │  2. Save to S3       │  │  first, falls back   │  │                              │  │
│  │  3. Churn predict    │  │  to direct churn     │  │                              │  │
│  │     (with enriched   │  │  predictor API       │  │                              │  │
│  │      sentiment data) │  │                      │  │                              │  │
│  │  No transcript:      │  │                      │  │                              │  │
│  │  → Churn predict     │  │                      │  │                              │  │
│  │    (account data     │  │                      │  │                              │  │
│  │     only)            │  │                      │  │                              │  │
│  │                      │  │                      │  │                              │  │
│  │  Results:            │  │                      │  │                              │  │
│  │  • RiskCard          │  │                      │  │                              │  │
│  │  • SentimentCard     │  │                      │  │                              │  │
│  │  • ActionCard        │  │                      │  │                              │  │
│  └──────────┬───────────┘  └──────────┬───────────┘  └──────────────┬───────────────┘  │
│             │                         │                              │                  │
│  Data flow: │              Data flow: │                   Data flow: │                  │
│  Sentiment API →           Agent-first with              File upload + S3 list         │
│  save transcript →         fallback                      by customer ID                │
│  churn predict                                           (no agent)                    │
└──────┬──────┼─────────────────────────┼──────────────────────────────┼──────────────────┘
       │      │                         │                              │
       │      │              ┌──────────┴──────────┐                   │
       │      │              │ tries :8080 first   │                   │
       │      │              │ catches network err │                   │
       │      │              │ falls back to :8001 │                   │
       │      │              └──┬───────────────┬──┘                   │
       │      │                 │               │                      │
       │      │          Agent reachable   Agent down                  │
       │      │                 │               │                      │
       │      │                 ▼               │                      │
       │      │                                                        │
       │      │  Analyze tab (if transcript provided):                 │
       │      │  ① POST sentiment-api:8002/predict ──────────────────────────►(Sentiment API)
       │      │  ② POST churn-api:8001/save-transcript (background)   │
       │      │  ③ POST churn-api:8001/predict (with enriched fields)──►(Churn API)
       │      │                                                        │
              │    ┌────────────────────────┐   │                      │
              │    │   Agent Service        │   │                      │
              │    │   (FastAPI :8080)      │   │                      │
              │    │                        │   │                      │
              │    │   POST /chat           │   │                      │
              │    │   GET  /health         │   │                      │
              │    │                        │   │                      │
              │    │   ┌─────────────────────────────────┐   │         │
              │    │   │       LangGraph Orchestrator    │   │         │
              │    │   │                                 │   │         │
              │    │   │  ┌───────────────────────────┐  │   │         │
              │    │   │  │  DataGatherer             │  │   │         │
              │    │   │  │  (Bedrock + Guardrail)    │  │   │         │
              │    │   │  │                           │  │   │         │
              │    │   │  │  Guardrail:               │  │   │         │
              │    │   │  │  retention-engine-        │  │   │         │
              │    │   │  │  guardrail (nvruz8wx5q83) │  │   │         │
              │    │   │  │  • Hate/Sexual: HIGH      │  │   │         │
              │    │   │  │  • Violence: HIGH/MED     │  │   │         │
              │    │   │  │  • Misconduct: HIGH/LOW   │  │   │         │
              │    │   │  │  • Insults: MED/LOW       │  │   │         │
              │    │   │  │  • PII: ANONYMIZE/BLOCK   │  │   │         │
              │    │   │  └─────────────┬─────────────┘  │   │         │
              │    │   │                │                 │   │         │
              │    │   │  ┌─────────────▼─────────────┐  │   │         │
              │    │   │  │  RetentionStrategist      │  │   │         │
              │    │   │  │  (Bedrock, NO guardrail)  │  │   │         │
              │    │   │  │                           │  │   │         │
              │    │   │  │  Uses clean LLM to avoid  │  │   │         │
              │    │   │  │  blocking retention terms │  │   │         │
              │    │   │  │  (cancel, churn, etc.)    │  │   │         │
              │    │   │  └───────────────────────────┘  │   │         │
              │    │   └────────────────┬────────────────┘   │         │
              │    │                    │                     │         │
              │    │   Tools (5 HTTP calls):                  │         │
              │    │   • get_customer_details ───────────────►│         │
              │    │   • predict_churn ─────────────────────►│         │
              │    │   • analyze_call ──────────────────────►Sent. API │
              │    │   • get_high_risk_customers ───────────►│         │
              │    │   • get_transcripts ───────────────────►│         │
              │    └───────────────┬────────────┘             │         │
              │                    │                          │         │
              │    ┌───────────────▼───────────────┐          │         │
              │    │      Amazon Bedrock            │          │         │
              │    │      Claude Haiku 4.5          │          │         │
              │    │                                │          │         │
              │    │  2 LLM instances:              │          │         │
              │    │  • llm (guardrail attached)    │          │         │
              │    │    → used by DataGatherer      │          │         │
              │    │  • llm_strategist (no guard)   │          │         │
              │    │    → used by RetentionStrat.   │          │         │
              │    └────────────────────────────────┘          │         │
              │                                 │                      │
              ▼                                 ▼                      ▼

┌──────────────────────────────────────────────────────────────────────────────────────┐
│                    Churn Predictor Service (FastAPI :8001)                            │
│                                                                                      │
│  Routes:                                    Internal:                                │
│  GET  /customers                            Loads account data + Agent 1 data from S3│
│  GET  /customer-details/{id}                Label encoders + 31 features from train  │
│  POST /predict                              Batch prediction: 500 rows/batch + cache │
│  GET  /high-risk                                                                     │
│  POST /transcribe (+ customer_id)           ┌──────────────────────────────────────┐ │
│  GET  /transcripts (filter by customer_id)  │  SageMaker Endpoint #1               │ │
│  GET  /transcripts/{name}                   │  churn-predictor-endpoint             │ │
│  POST /save-transcript                      │                                      │ │
│  GET  /health                               │  XGBoost v3 · 31 features            │ │
│                                             │  95% accuracy · 0.9861 AUC           │ │
│  /predict encodes features → CSV →          │  Native XGBoost container            │ │
│  invokes SageMaker → returns probability    │  (no inference.py)                   │ │
│                                             └──────────────────────────────────────┘ │
└──────────────────────────────┬───────────────────────────────────────────────────────┘
                               │ boto3
                               ▼
                    ┌──────────────────┐
                    │ S3: retention-   │
                    │ engine-bucket    │
                    │                  │
                    │ /data/           │
                    │  internet_data   │
                    │  trilink_cust    │
                    │  agent1_synth    │
                    │                  │
                    │ /audio/          │
                    │  /{cust_id}/     │
                    │ /transcripts/    │
                    │  /{cust_id}/     │
                    │                  │
                    │ /models/         │
                    │  churn/          │
                    │  sentiment/      │
                    │  sentiment-rev/  │
                    └────────┬─────────┘
                             │
                             ▼
              ┌────────────────────────────────────────┐
              │ Amazon Transcribe                      │
              │                                        │
              │  ┌──────────┐    ┌──────────────────┐  │
              │  │ S3 audio/│───►│ Lambda:          │  │
              │  │ {cust_id}│    │ retention-       │  │
              │  │ upload   │    │ transcribe-      │  │
              │  └──────────┘    │ pipeline         │  │
              │                  └────────┬─────────┘  │
              │                           │             │
              │  ┌────────────────────────▼──────────┐ │
              │  │ Amazon Transcribe Job             │ │
              │  │ Speaker diarization (2 speakers) │ │
              │  │ Output → S3 transcripts/{cid}/   │ │
              │  └──────────────────────────────────┘ │
              └────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────┐
│                  Sentiment Analysis Service (FastAPI :8002)                           │
│                                                                                      │
│  Routes:                                                                             │
│  POST /predict                                                                       │
│  GET  /health                                                                        │
│                                                                                      │
│  Enrichment Pipeline:                       ┌──────────────────────────────────────┐ │
│                                             │  SageMaker Endpoint #2               │ │
│  1. Call SageMaker ─────────────────────────►│  retention-sentiment-revised-endpoint│ │
│     (base sentiment classification)         │                                      │ │
│             │                               │  DistilBERT 3-class revised          │ │
│  2. Decode label (Neg/Neu/Pos)              │  (Negative / Neutral / Positive)     │ │
│             │                               │                                      │ │
│  3. Emotion scores (keyword NLP:            │  HuggingFace PyTorch container       │ │
│     frustration, anger, joy, sadness, fear) └──────────────────────────────────────┘ │
│             │                                                                        │
│  4. Sentiment shift (1st half vs 2nd half)                                           │
│             │                                                                        │
│  5. Escalation + resolution detection (phrase matching)                              │
│             │                                                                        │
│  6. QA score (composite: sentiment + emotions + flags)                               │
│             │                                                                        │
│  7. Return all 7 fields ─────────────────────────────► Agent 2 (Churn Predictor)    │
│     qa_score · sentiment · emotion_frustration                                       │
│     emotion_anger · sentiment_shift                                                  │
│     escalation_flag · resolution_flag                                                │
└──────────────────────────────────────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────────────────────────────────────────

INFRASTRUCTURE LAYER

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              EKS Cluster: eks-ezvrmopo-okl                         │
│                              Namespace: retention-engine                            │
│                                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                  │
│  │ agent-service    │  │ churn-predictor  │  │ sentiment-       │                  │
│  │ Deployment       │  │ Deployment       │  │ predictor        │                  │
│  │ Port: 8080       │  │ Port: 8001       │  │ Deployment       │                  │
│  │ LoadBalancer     │  │ ClusterIP        │  │ Port: 8001       │                  │
│  └──────────────────┘  └──────────────────┘  │ ClusterIP        │                  │
│                                               └──────────────────┘                  │
│  ┌──────────────────┐                                                               │
│  │ frontend         │  ConfigMaps ─ Secrets ─ ResourceQuota ─ LimitRange           │
│  │ Deployment       │                                                               │
│  │ Port: 3000       │                                                               │
│  │ LoadBalancer     │                                                               │
│  └──────────────────┘                                                               │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   Terraform                                         │
│                                                                                     │
│  iam.tf          s3.tf           eks.tf          guardrail.tf    transcribe.tf      │
│  • SageMaker     • retention-    • EKS cluster   • Bedrock       • Lambda function  │
│    execution       engine-       • Node group      content        • IAM role         │
│    roles           bucket        • VPC subnets     moderation     • S3 event trigger │
│  • Lambda role   • TF state     • IRSA                                              │
│                    bucket                                                            │
│                                                                                     │
│  State: s3://retention-engine-tf-state + DynamoDB lock                              │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                             CI/CD — GitHub Actions                                  │
│                                                                                     │
│  1. terraform.yml          Triggered on PR to terraform/**                          │
│     plan / apply           Provisions IAM, S3, EKS, guardrails                     │
│                                                                                     │
│  2. sagemaker-deploy.yml   Triggered on push to main, sagemaker/**                 │
│     deploy / delete        Runs deploy.py, polls InService, validates inference     │
│                                                                                     │
│  3. deploy.yml             Triggered on push to main, services/** frontend/**      │
│     Docker → GHCR → EKS   Matrix build per service, kubectl rollout               │
│                                                                                     │
│  4. ci-post-merge.yml      Triggered on push to main                               │
│     Unit tests → Docker    build → endpoint health → E2E smoke test                │
│                                                                                     │
│  5. teardown.yml           Manual dispatch — safe cleanup for testing               │
│                                                                                     │
│  Observability: LangSmith (project: retention-engine)                              │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## LangGraph Orchestrator Flow

```
                              User Message
                                  │
                                  ▼
                        ┌─────────────────┐
                        │    CLASSIFY      │
                        │                  │
                        │ • Extract        │
                        │   customer_id    │
                        │   (regex C\d{8}) │
                        │                  │
                        │ • Detect type:   │
                        │   customer_query │
                        │   high_risk      │
                        │   transcript     │
                        │   general        │
                        │                  │
                        │ • Enrich state   │
                        └────────┬─────────┘
                                 │
                                 │ always
                                 ▼
                  ┌──────────────────────────────┐
                  │     MODEL (Data Gatherer)     │
                  │                                │
                  │  System: GATHERER_PROMPT        │
                  │  LLM: Claude Haiku 4.5          │
                  │  + Bedrock Guardrail            │
                  │  Tools: 5 tools bound           │
                  │                                │
                  │  "Collect all relevant data.    │
                  │   Do not recommend yet."         │
                  │                                │
                  │  Claude decides which tools     │
                  │  to call based on the question  │
                  └──────────┬───────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
              has tool calls    no tool calls
                    │                 │
                    ▼                 │
          ┌─────────────────┐        │
          │     TOOLS       │        │
          │  (ToolNode)     │        │
          │                 │        │
          │  Executes:      │        │
          │  ┌────────────┐ │        │
          │  │get_customer│ │        │
          │  │_details    │ │        │
          │  └────────────┘ │        │
          │  ┌────────────┐ │        │
          │  │predict_    │ │        │
          │  │churn       │ │        │
          │  └────────────┘ │        │
          │  ┌────────────┐ │        │
          │  │analyze_    │ │        │
          │  │call        │ │        │
          │  └────────────┘ │        │
          │  ┌────────────┐ │        │
          │  │get_high_   │ │        │
          │  │risk_       │ │        │
          │  │customers   │ │        │
          │  └────────────┘ │        │
          │  ┌────────────┐ │        │
          │  │get_        │ │        │
          │  │transcripts │ │        │
          │  └────────────┘ │        │
          └────────┬────────┘        │
                   │                 │
                   │ always          │
                   ▼                 │
        ┌────────────────────┐       │
        │  RESPOND           │       │
        │  (Gatherer Review) │       │
        │                    │       │
        │  Reviews tool      │       │
        │  results.          │       │
        │  May request       │       │
        │  more tools.       │       │
        └────────┬───────────┘       │
                 │                   │
        ┌────────┴────────┐          │
        │                 │          │
  has tool calls    no tool calls    │
        │                 │          │
        ▼                 │          │
   (back to TOOLS)        │          │
                          │          │
                          ▼          ▼
                ┌─────────────────────────────┐
                │      STRATEGIST             │
                │  (Retention Strategist)      │
                │                              │
                │  System: STRATEGIST_PROMPT    │
                │  LLM: Claude Haiku 4.5        │
                │  NO guardrail (uses           │
                │  llm_strategist to avoid      │
                │  blocking retention terms)    │
                │  Tools: NONE (reasoning only) │
                │                              │
                │  Receives all gathered data   │
                │  and produces:                │
                │                              │
                │  1. Customer Summary          │
                │  2. Churn Risk: HIGH/MED/LOW  │
                │  3. Sentiment (if available)  │
                │  4. Action: [ACTION_CODE]     │
                │  5. Recommendation            │
                │                              │
                │  APPROVED ACTIONS:            │
                │  HIGH:   PLAN_UPGRADE         │
                │          LOYALTY_DISCOUNT     │
                │          SERVICE_CREDIT       │
                │          TECH_VISIT           │
                │          DEDICATED_SUPPORT    │
                │          CONTRACT_FLEX        │
                │  MEDIUM: FOLLOWUP_48H         │
                │          GOODWILL_CREDIT      │
                │          SPEED_BOOST          │
                │  LOW:    MONITOR              │
                └──────────────┬───────────────┘
                               │
                               ▼
                             END
                     (return AI response)


─────────────────────────────────────────────────────────────

TOOL DETAIL

┌─────────────────────────────────────────────────────────┐
│ get_customer_details                                     │
│ GET churn-predictor:8001/customer-details/{customer_id}  │
│ Returns: plan_tier, speed_mbps, monthly_cost,            │
│   contract_type, tenure, complaints, outage_count,       │
│   age, income_bracket, has_call_data, qa_score,          │
│   sentiment, emotion_frustration, emotion_anger          │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ predict_churn                                            │
│ POST churn-predictor:8001/predict                        │
│ Sends: customer_id + 7 Agent 1 fields                   │
│ Returns: churn_probability, prediction, risk_level,      │
│   has_call_data, qa_score, sentiment, emotion scores     │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ analyze_call                                             │
│ POST sentiment-api:8002/predict                          │
│ Sends: transcript text                                   │
│ Returns: qa_score, sentiment, emotion_frustration,       │
│   emotion_anger, sentiment_shift, escalation_flag,       │
│   resolution_flag (enriched via NLP post-processing)     │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ get_high_risk_customers                                  │
│ GET churn-predictor:8001/high-risk?limit=N               │
│ Returns: ranked list of at-risk customers with           │
│   churn_probability, plan, cost, sentiment, qa_score     │
│ Uses batch SageMaker prediction (500 rows/batch)         │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ get_transcripts                                          │
│ GET churn-predictor:8001/transcripts?customer_id={id}    │
│ Returns: list of transcripts for a customer (up to 5)    │
│   with full text and speaker segments                    │
│ Fetches from S3 transcripts/{customer_id}/               │
└─────────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────────

CONVERSATION MEMORY

  Session A ──┐    Session B ──┐
              │                │
     ┌────────▼──────┐  ┌─────▼────────┐
     │ MemorySaver   │  │ MemorySaver  │
     │ thread_id: A  │  │ thread_id: B │
     │               │  │              │
     │ msg1: human   │  │ msg1: human  │
     │ msg2: ai      │  │ msg2: ai     │
     │ msg3: tool    │  │ ...          │
     │ msg4: ai      │  └──────────────┘
     │ ...           │
     └───────────────┘

  In-memory checkpointer per session.
  Resets on service restart.
  Each session_id gets isolated conversation history.
```

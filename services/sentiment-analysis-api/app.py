import os
import json
import logging
import pandas as pd
from typing import Any


import boto3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from io import StringIO


# Initialization
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name=__name__)

app = FastAPI(title="Sentiment Analysis API")

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SENTIMENT_ENDPOINT_NAME = os.getenv(key="SENTIMENT_ENDPOINT_NAME", default="retention-sentiment-analysis-endpoint")
GUARDRAIL_NAME = os.getenv(key="GUARDRAIL_NAME", default="sentiment-analysis-guardrail")
S3_BUCKET = os.getenv(key="S3_BUCKET", default="retention-engine-bucket")
AWS_REGION = os.getenv(key="AWS_REGION", default="us-east-1")

sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=AWS_REGION)

FEATURE_COLUMNS = [
    "call_id",
    "customer_id",
    "call_date",
    "call_time",
    "agent_id",
    "agent_name",
    "primary_scenario",
    "call_transcript",
    "overall_rating",
    "call_successful",
    "customer_monthly_spend",
    "customer_service_count",
    "customer_issue_history",
]

_customer_data: pd.DataFrame | None = None

def download_csv_from_s3() -> pd.DataFrame:
    """Download a CSV file from S3 with full error handling and validation."""
    global _customer_data
    s3 = boto3.client("s3")
    KEY = "data/call_transcripts.csv"

    # Download file 
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=KEY)
        csv_str = obj["Body"].read().decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"Failed to download file from S3: {e}")

    # Parse CSV into DataFrame 
    try:
        _customer_data = pd.read_csv(filepath_or_buffer=StringIO(initial_value=csv_str))
    except Exception as e:
        raise ValueError(f"Failed to parse CSV into DataFrame: {e}")

    return _customer_data


def find_record(df: pd.DataFrame | None, id: str) -> pd.DataFrame:
    """
    Search the DataFrame for either call_id or customer_id.
    Priority: call_id > customer_id.
    """
    if df is None:
        df = download_csv_from_s3()
    
    if id and id[0:3] == "CALL":
        match = df[df["call_id"] == id]
        if match.empty:
            raise LookupError(f"No record found for call_id={id}")
        return match.iloc[0]

    else:
        match = df[df["customer_id"] == id]
        if match.empty:
            raise LookupError(f"No record found for customer_id={id}")
        return match.iloc[0]

    raise ValueError("You must provide either call_id or customer_id")


# File Loaders
def load_model_files() -> dict[str, Any]:
    """Load model metadata files dynamically at request time."""
    with open(file=os.path.join(os.path.dirname(__file__), "model/label_encoder.json"), mode="r") as f:
        RESULTS = json.load(fp=f)

    with open(file=os.path.join(os.path.dirname(__file__), "model/example_output.json"), mode="r") as f:
        EXAMPLE = json.load(fp=f)

    return {"results": RESULTS, "example": EXAMPLE}


def load_notebook() -> Any:
    """Load notebook content dynamically."""
    notebook_path = os.path.abspath(
        path=os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "sagemaker",
            "sentiment",
            "sentiment_training.ipynb",
        )
    )

    with open(file=notebook_path, mode="r", encoding="utf-8") as f:
        return json.load(fp=f)



def encode_features(raw: dict, label_encoders: dict) -> str:
    """Encode a raw feature dict to a CSV string for SageMaker."""
    LABEL_ENCODERS = label_encoders
    for col, mapping in LABEL_ENCODERS.items():
        raw[col] = mapping.get(str(object=raw.get(col, "")), 0)

    return ",".join(str(object=float(raw.get(col, 0))) for col in FEATURE_COLUMNS)

# Sagemaker Invocation
def invoke_sagemaker(customer: Any) -> dict[str, Any]:
    if isinstance(customer, pd.Series):
        customer = customer.to_dict()
        
    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SENTIMENT_ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps(obj=customer)
    )

    return json.loads(s=response["Body"].read().decode())

def extract_customer_fields(customer: pd.Series) -> dict:
    """Extract only the fields required for feature building."""
    return {
        "call_id": customer["call_id"],
        "customer_id": customer["customer_id"],
        "call_date": customer["call_date"],
        "call_time": customer["call_time"],
        "agent_id": customer["agent_id"],
        "agent_name": customer["agent_name"],
        "primary_scenario": customer["primary_scenario"],
        "call_transcript": customer["call_transcript"],
        "overall_rating": int(customer["overall_rating"]),
        "call_successful": int(customer["call_successful"]),
        "customer_monthly_spend": float(customer["customer_monthly_spend"]),
        "customer_service_count": int(customer["customer_service_count"]),
        "customer_issue_history": customer["customer_issue_history"]
    }

# Data Models
class CallRecord(BaseModel):
    call_id: str
    customer_id: str
    call_date: str
    call_time: str
    agent_id: str
    agent_name: str
    primary_scenario: str
    call_transcript: str
    overall_rating: int
    call_successful: int
    customer_monthly_spend: float
    customer_service_count: int
    customer_issue_history: str
    
class CallResponse(BaseModel):
    customer_id: str
    qa_score: float 
    sentiment: str 
    emotion_frustration: float 
    emotion_anger: float 
    sentiment_shift: float 
    escalation_flag: int 
    resolution_flag: int 


# API Endpoints
@app.get(path="/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "endpoint": SENTIMENT_ENDPOINT_NAME}


@app.post(path="/sentiment", response_model=CallResponse)
def analyze_sentiment(req: CallRecord | dict, input: str | None = None) -> dict[str, Any] | dict[str, Any] | dict[str, str]:

    customer_data = download_csv_from_s3()
    
    # if req.customer_id not in customer_data.index:
        # raise HTTPException(status_code=404, detail=f"Customer {req.customer_id} not found")
    
    customer = find_record(customer_data, req["customer_id"])
    # Validate transcript length
    char_count = len(customer.call_transcript.encode(encoding="utf-8"))
    if char_count < 0:
        return {"error": "Insufficient data for analysis.", "char_count": char_count}
    if char_count > 20000:
        return {"error": "Transcript exceeds maximum processing limit.", "char_count": char_count}

    # Load dynamic files
    files = load_model_files()
    notebook = load_notebook()
    

    # Invoke Sagemaker
    try:
        return invoke_sagemaker(customer=req)
    except Exception as e:
        logger.exception(msg="Sagemaker invocation failed")
        return {"error": str(object=e), "status": "failure"}






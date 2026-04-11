"""
Churn Predictor API — FastAPI wrapper that looks up account data
by customer_id, combines with Agent 1 output, and calls SageMaker.

Routes: /predict, /customers, /high-risk, /customer-details, /health
"""

import io
import json
import os
import logging
import time

import boto3
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Churn Predictor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Config ---
REGION = os.environ.get("AWS_REGION", "us-east-1")
ENDPOINT_NAME = os.environ.get("SAGEMAKER_ENDPOINT", "churn-predictor-endpoint")
S3_BUCKET = os.environ.get("S3_BUCKET", "retention-engine-bucket")

sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)

# --- Label encoders (must match training) ---
LABEL_ENCODERS = {
    "plan_tier": {"Basic_25": 0, "Premium_Gig": 1, "Standard_100": 2},
    "contract_type": {"12_Month": 0, "24_Month": 1, "Month_to_Month": 2},
    "income_bracket": {"High": 0, "Low": 1, "Middle": 2, "Upper_Middle": 3},
    "home_ownership": {"Other": 0, "Own": 1, "Rent": 2},
    "work_from_home_flag": {"False": 0, "True": 1},
    "education_level": {"College": 0, "Graduate": 1, "HS": 2, "Professional": 3},
    "life_stage": {"Empty_Nest": 0, "Established_Family": 1, "Senior": 2, "Single": 3, "Young_Family": 4},
    "home_type": {"Apartment": 0, "Condo": 1, "Single_Family": 2, "Townhouse": 3},
    "fiber_availability": {"False": 0, "True": 1},
    "sentiment": {"Negative": 0, "Neutral": 1, "Positive": 2},
}

FEATURE_COLUMNS = [
    "plan_tier", "speed_mbps", "monthly_cost", "data_usage_gb", "connected_devices",
    "contract_type", "speed_complaints", "outage_count", "internet_tenure_days",
    "contract_completed_percent", "age", "household_income", "income_bracket",
    "family_size", "home_ownership", "work_from_home_flag", "education_level",
    "life_stage", "home_type", "home_square_footage", "property_value",
    "neighborhood_crime_rate", "neighborhood_income_median", "fiber_availability",
    "qa_score", "sentiment", "emotion_frustration", "emotion_anger",
    "sentiment_shift", "escalation_flag", "resolution_flag",
]

# --- Cached data ---
_account_data: pd.DataFrame | None = None
_agent1_data: pd.DataFrame | None = None
_risk_cache: list[dict] | None = None  # pre-computed high-risk customers


def load_account_data() -> pd.DataFrame:
    global _account_data
    if _account_data is not None:
        return _account_data

    obj = s3.get_object(Bucket=S3_BUCKET, Key="data/internet_data.csv")
    internet_df = pd.read_csv(io.BytesIO(obj["Body"].read()))

    obj = s3.get_object(Bucket=S3_BUCKET, Key="data/trilink_customers_data.csv")
    customers_df = pd.read_csv(io.BytesIO(obj["Body"].read()))

    merged = internet_df.merge(customers_df, on="customer_id", how="inner")
    _account_data = merged.set_index("customer_id")
    return _account_data


def load_agent1_data() -> pd.DataFrame:
    global _agent1_data
    if _agent1_data is not None:
        return _agent1_data
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key="data/agent1_synthetic_output.csv")
        _agent1_data = pd.read_csv(io.BytesIO(obj["Body"].read())).set_index("customer_id")
    except Exception:
        local_path = os.path.join(os.path.dirname(__file__), "../../sagemaker/churn/data/agent1_synthetic_output.csv")
        if os.path.exists(local_path):
            _agent1_data = pd.read_csv(local_path).set_index("customer_id")
        else:
            _agent1_data = pd.DataFrame()
    return _agent1_data


def encode_row(raw: dict) -> str:
    """Encode a raw feature dict to CSV string for SageMaker."""
    for col, mapping in LABEL_ENCODERS.items():
        raw[col] = mapping.get(str(raw.get(col, "")), 0)
    return ",".join(str(float(raw.get(col, 0))) for col in FEATURE_COLUMNS)


def build_raw_features(customer: pd.Series, qa_score: float, sentiment: str,
                       emotion_frustration: float, emotion_anger: float,
                       sentiment_shift: float, escalation_flag: int,
                       resolution_flag: int) -> dict:
    """Build raw feature dict from account data + Agent 1 fields."""
    return {
        "plan_tier": customer["plan_tier"],
        "speed_mbps": int(customer["speed_mbps"]),
        "monthly_cost": float(customer["monthly_cost"]),
        "data_usage_gb": float(customer["data_usage_gb"]),
        "connected_devices": int(customer["connected_devices"]),
        "contract_type": customer["contract_type"],
        "speed_complaints": int(customer["speed_complaints"]),
        "outage_count": int(customer["outage_count"]),
        "internet_tenure_days": float(customer.get("internet_tenure_days", 0) or 0),
        "contract_completed_percent": float(customer.get("contract_completed_percent", 0) or 0),
        "age": int(customer["age"]),
        "household_income": int(customer["household_income"]),
        "income_bracket": customer["income_bracket"],
        "family_size": int(customer["family_size"]),
        "home_ownership": customer["home_ownership"],
        "work_from_home_flag": str(customer["work_from_home_flag"]),
        "education_level": customer["education_level"],
        "life_stage": customer["life_stage"],
        "home_type": customer["home_type"],
        "home_square_footage": int(customer["home_square_footage"]),
        "property_value": int(customer["property_value"]),
        "neighborhood_crime_rate": float(customer["neighborhood_crime_rate"]),
        "neighborhood_income_median": int(customer["neighborhood_income_median"]),
        "fiber_availability": str(customer["fiber_availability"]),
        "qa_score": qa_score,
        "sentiment": sentiment,
        "emotion_frustration": emotion_frustration,
        "emotion_anger": emotion_anger,
        "sentiment_shift": sentiment_shift,
        "escalation_flag": escalation_flag,
        "resolution_flag": resolution_flag,
    }


def compute_risk_cache() -> list[dict]:
    """Batch-predict churn for all customers with call data.
    Sends rows in batches to SageMaker (multi-row CSV) for speed."""
    global _risk_cache
    if _risk_cache is not None:
        return _risk_cache

    logger.info("Computing high-risk cache (batch prediction)...")
    account_data = load_account_data()
    agent1_data = load_agent1_data()

    if agent1_data.empty:
        _risk_cache = []
        return _risk_cache

    # Build all rows
    customer_ids = []
    csv_rows = []
    metadata = []

    for cid in agent1_data.index:
        if cid not in account_data.index:
            continue
        customer = account_data.loc[cid]
        call = agent1_data.loc[cid]

        raw = build_raw_features(
            customer,
            float(call["qa_score"]), str(call["sentiment"]),
            float(call["emotion_frustration"]), float(call["emotion_anger"]),
            float(call["sentiment_shift"]), int(call["escalation_flag"]),
            int(call["resolution_flag"]),
        )
        csv_rows.append(encode_row(raw))
        customer_ids.append(cid)
        metadata.append({
            "plan": customer["plan_tier"],
            "monthly_cost": int(customer["monthly_cost"]),
            "contract_type": customer["contract_type"],
            "sentiment": str(call["sentiment"]),
            "qa_score": float(call["qa_score"]),
            "emotion_frustration": float(call["emotion_frustration"]),
            "emotion_anger": float(call["emotion_anger"]),
        })

    # Send in batches of 500 rows
    BATCH_SIZE = 500
    all_probas = []

    for i in range(0, len(csv_rows), BATCH_SIZE):
        batch = "\n".join(csv_rows[i:i + BATCH_SIZE])
        try:
            resp = sagemaker_runtime.invoke_endpoint(
                EndpointName=ENDPOINT_NAME,
                ContentType="text/csv",
                Body=batch,
            )
            result = resp["Body"].read().decode().strip()
            probas = [float(p) for p in result.split("\n")]
            all_probas.extend(probas)
        except Exception as e:
            logger.error(f"Batch {i}-{i+BATCH_SIZE} failed: {e}")
            all_probas.extend([0.0] * min(BATCH_SIZE, len(csv_rows) - i))

    logger.info(f"Batch prediction complete: {len(all_probas)} customers scored")

    # Build results
    results = []
    for j, proba in enumerate(all_probas):
        if proba >= 0.4:  # only cache MEDIUM and HIGH risk
            results.append({
                "customer_id": customer_ids[j],
                "churn_probability": round(proba, 4),
                "risk_level": "HIGH" if proba >= 0.7 else "MEDIUM",
                **metadata[j],
            })

    results.sort(key=lambda x: x["churn_probability"], reverse=True)
    _risk_cache = results
    logger.info(f"Risk cache built: {len(results)} at-risk customers")
    return _risk_cache


# --- Request / Response schemas ---
class PredictRequest(BaseModel):
    customer_id: str
    qa_score: float | None = None
    sentiment: str | None = None
    emotion_frustration: float | None = None
    emotion_anger: float | None = None
    sentiment_shift: float | None = None
    escalation_flag: int | None = None
    resolution_flag: int | None = None


class PredictResponse(BaseModel):
    churn_probability: float
    prediction: str
    risk_level: str
    customer_id: str
    has_call_data: bool
    qa_score: float
    sentiment: str
    emotion_frustration: float
    emotion_anger: float
    sentiment_shift: float
    escalation_flag: int
    resolution_flag: int


# --- Routes ---
@app.get("/health")
def health():
    return {"status": "healthy", "model": "churn-xgboost", "endpoint": ENDPOINT_NAME}


@app.get("/customers")
def list_customers(q: str = "", limit: int = 20):
    """Search customers for the frontend dropdown."""
    account_data = load_account_data()
    agent1_data = load_agent1_data()
    matches = account_data.index[account_data.index.str.contains(q, case=False)][:limit]
    results = []
    for cid in matches:
        row = account_data.loc[cid]
        has_call = cid in agent1_data.index
        results.append({
            "id": cid,
            "label": f"{cid} — {row['plan_tier']}, {row['contract_type']}, ${int(row['monthly_cost'])}/mo"
                     + (" (has call)" if has_call else ""),
            "has_call": has_call,
        })
    return results


@app.get("/customer-details/{customer_id}")
def customer_details(customer_id: str):
    """Return full account details for a customer. Used by the agent."""
    account_data = load_account_data()
    agent1_data = load_agent1_data()

    if customer_id not in account_data.index:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    c = account_data.loc[customer_id]
    result = {
        "customer_id": customer_id,
        "plan_tier": c["plan_tier"],
        "speed_mbps": int(c["speed_mbps"]),
        "monthly_cost": float(c["monthly_cost"]),
        "contract_type": c["contract_type"],
        "internet_tenure_days": float(c.get("internet_tenure_days", 0) or 0),
        "speed_complaints": int(c["speed_complaints"]),
        "outage_count": int(c["outage_count"]),
        "age": int(c["age"]),
        "income_bracket": c["income_bracket"],
        "home_ownership": c["home_ownership"],
        "has_call_data": customer_id in agent1_data.index,
    }
    if customer_id in agent1_data.index:
        call = agent1_data.loc[customer_id]
        result.update({
            "qa_score": float(call["qa_score"]),
            "sentiment": str(call["sentiment"]),
            "emotion_frustration": float(call["emotion_frustration"]),
            "emotion_anger": float(call["emotion_anger"]),
        })
    return result


@app.get("/high-risk")
def high_risk_customers(limit: int = 10):
    """Return top N highest-risk customers from pre-computed cache."""
    results = compute_risk_cache()
    return results[:limit]


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    try:
        account_data = load_account_data()
        agent1_data = load_agent1_data()

        if req.customer_id not in account_data.index:
            raise HTTPException(status_code=404, detail=f"Customer {req.customer_id} not found")

        customer = account_data.loc[req.customer_id]

        # Determine Agent 1 values: request > stored call data > neutral defaults
        has_call = req.customer_id in agent1_data.index
        call = agent1_data.loc[req.customer_id] if has_call else None

        qa_score = req.qa_score if req.qa_score is not None else (float(call["qa_score"]) if call is not None else 5.0)
        sentiment = req.sentiment if req.sentiment is not None else (str(call["sentiment"]) if call is not None else "Neutral")
        emotion_frustration = req.emotion_frustration if req.emotion_frustration is not None else (float(call["emotion_frustration"]) if call is not None else 0.0)
        emotion_anger = req.emotion_anger if req.emotion_anger is not None else (float(call["emotion_anger"]) if call is not None else 0.0)
        sentiment_shift = req.sentiment_shift if req.sentiment_shift is not None else (float(call["sentiment_shift"]) if call is not None else 0.0)
        escalation_flag = req.escalation_flag if req.escalation_flag is not None else (int(call["escalation_flag"]) if call is not None else 0)
        resolution_flag = req.resolution_flag if req.resolution_flag is not None else (int(call["resolution_flag"]) if call is not None else 1)

        raw = build_raw_features(customer, qa_score, sentiment, emotion_frustration,
                                 emotion_anger, sentiment_shift, escalation_flag, resolution_flag)
        csv_row = encode_row(raw)

        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType="text/csv",
            Body=csv_row,
        )

        proba = float(response["Body"].read().decode())
        prediction = "churn" if proba >= 0.5 else "no_churn"
        risk_level = "HIGH" if proba >= 0.7 else "MEDIUM" if proba >= 0.4 else "LOW"

        return PredictResponse(
            customer_id=req.customer_id,
            churn_probability=round(proba, 4),
            prediction=prediction,
            risk_level=risk_level,
            has_call_data=has_call or req.qa_score is not None,
            qa_score=qa_score,
            sentiment=sentiment,
            emotion_frustration=emotion_frustration,
            emotion_anger=emotion_anger,
            sentiment_shift=sentiment_shift,
            escalation_flag=escalation_flag,
            resolution_flag=resolution_flag,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Transcribe Pipeline Routes ---
transcribe_client = boto3.client("transcribe", region_name=REGION)


@app.post("/transcribe")
async def upload_audio(file: UploadFile = File(...)):
    """Upload an audio file to S3 audio/ prefix.
    The Lambda trigger will automatically start a Transcribe job."""
    allowed_ext = {".wav", ".mp3", ".mp4", ".flac"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}. Use: {', '.join(allowed_ext)}")

    s3_key = f"audio/{file.filename}"
    logger.info(f"Uploading audio: {s3_key}")

    contents = await file.read()
    s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=contents)

    return {
        "status": "uploaded",
        "s3_key": s3_key,
        "filename": file.filename,
        "message": "Transcription job will start automatically via Lambda trigger.",
    }


@app.get("/transcripts")
def list_transcripts():
    """List all completed transcripts in S3 transcripts/ prefix."""
    try:
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="transcripts/")
        transcripts = []
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".json"):
                name = os.path.basename(key).replace(".json", "")
                transcripts.append({
                    "name": name,
                    "key": key,
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                })
        transcripts.sort(key=lambda x: x["last_modified"], reverse=True)
        return transcripts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcripts/{filename}")
def get_transcript(filename: str):
    """Retrieve a specific transcript and return the text + speaker segments."""
    s3_key = f"transcripts/{filename}.json"
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        result = json.loads(obj["Body"].read().decode())

        full_text = result["results"]["transcripts"][0]["transcript"]

        # Extract speaker segments if available
        segments = []
        if "speaker_labels" in result["results"]:
            for seg in result["results"]["speaker_labels"]["segments"]:
                speaker = seg["speaker_label"]
                text = " ".join(
                    item["alternatives"][0]["content"]
                    for item in seg["items"]
                    if item.get("alternatives")
                )
                segments.append({"speaker": speaker, "text": text})

        return {
            "filename": filename,
            "transcript": full_text,
            "segments": segments,
            "job_name": result.get("jobName", ""),
        }
    except s3.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail=f"Transcript '{filename}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

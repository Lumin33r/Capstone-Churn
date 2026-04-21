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
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name=__name__)

app = FastAPI(
    title="Churn Predictor API",
    root_path=os.getenv("FASTAPI_ROOT_PATH", ""),
)

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Config ---
REGION = os.environ.get(key="AWS_REGION", default="us-east-1")
ENDPOINT_NAME = os.environ.get(key="SAGEMAKER_ENDPOINT", default="churn-predictor-endpoint")
S3_BUCKET = os.environ.get(key="S3_BUCKET", default="retention-engine-bucket")

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
    internet_df = pd.read_csv(filepath_or_buffer=io.BytesIO(initial_bytes=obj["Body"].read()))

    obj = s3.get_object(Bucket=S3_BUCKET, Key="data/trilink_customers_data.csv")
    customers_df = pd.read_csv(filepath_or_buffer=io.BytesIO(initial_bytes=obj["Body"].read()))

    merged = internet_df.merge(right=customers_df, on="customer_id", how="inner")
    _account_data = merged.set_index(keys="customer_id")
    return _account_data


def load_agent1_data() -> pd.DataFrame:
    global _agent1_data
    if _agent1_data is not None:
        return _agent1_data
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key="data/agent1_synthetic_output.csv")
        _agent1_data = pd.read_csv(filepath_or_buffer=io.BytesIO(initial_bytes=obj["Body"].read())).set_index(keys="customer_id")
    except Exception:
        local_path = os.path.join(os.path.dirname(p=__file__), "../../sagemaker/churn/data/agent1_synthetic_output.csv")
        if os.path.exists(path=local_path):
            _agent1_data = pd.read_csv(filepath_or_buffer=local_path).set_index(keys="customer_id")
        else:
            _agent1_data = pd.DataFrame()
    return _agent1_data


def encode_row(raw: dict) -> str:
    """Encode a raw feature dict to CSV string for SageMaker."""
    for col, mapping in LABEL_ENCODERS.items():
        raw[col] = mapping.get(str(object=raw.get(col, "")), 0)
    return ",".join(str(object=float(raw.get(col, 0))) for col in FEATURE_COLUMNS)


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

    logger.info(msg="Computing high-risk cache (batch prediction)...")
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
            customer=customer,
            qa_score=float(call["qa_score"]), sentiment=str(object=call["sentiment"]),
            emotion_frustration=float(call["emotion_frustration"]), emotion_anger=float(call["emotion_anger"]),
            sentiment_shift=float(call["sentiment_shift"]), escalation_flag=int(call["escalation_flag"]),
            resolution_flag=int(call["resolution_flag"]),
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
    for j, proba in enumerate(iterable=all_probas):
        if proba >= 0.4:  # only cache MEDIUM and HIGH risk
            results.append({
                "customer_id": customer_ids[j],
                "churn_probability": round(number=proba, ndigits=4),
                "risk_level": "HIGH" if proba >= 0.7 else "MEDIUM",
                **metadata[j],
            })

    results.sort(key=lambda x: x["churn_probability"], reverse=True)
    _risk_cache = results
    logger.info(msg=f"Risk cache built: {len(results)} at-risk customers")
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
@app.get(path="/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "model": "churn-xgboost", "endpoint": ENDPOINT_NAME}


@app.get(path="/customers")
def list_customers(q: str = "", limit: int = 20) -> list[Any]:
    """Search customers for the frontend dropdown."""
    account_data = load_account_data()
    agent1_data = load_agent1_data()
    matches = account_data.index[account_data.index.str.contains(pat=q, case=False)][:limit]
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


@app.get(path="/customer-details/{customer_id}")
def customer_details(customer_id: str) -> dict[str, Any]:
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


@app.get(path="/high-risk")
def high_risk_customers(limit: int = 10) -> list[dict[Any, Any]]:
    """Return top N highest-risk customers from pre-computed cache."""
    results = compute_risk_cache()
    return results[:limit]


@app.post(path="/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
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

        raw = build_raw_features(customer=customer, qa_score=qa_score, sentiment=sentiment, emotion_frustration=emotion_frustration,
                                 emotion_anger=emotion_anger, sentiment_shift=sentiment_shift, escalation_flag=escalation_flag, resolution_flag=resolution_flag)
        csv_row = encode_row(raw=raw)

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
            churn_probability=round(number=proba, ndigits=4),
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
        raise HTTPException(status_code=500, detail=str(object=e))


# --- Transcribe Pipeline Routes ---

@app.post("/transcribe")
async def upload_audio(file: UploadFile = File(...), customer_id: str | None = None):
    """Upload an audio file to S3 audio/ prefix.
    The Lambda trigger will automatically start a Transcribe job.
    If customer_id is provided, the file is stored under audio/{customer_id}/."""
    allowed_ext = {".wav", ".mp3", ".mp4", ".flac"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}. Use: {', '.join(allowed_ext)}")

    if customer_id:
        s3_key = f"audio/{customer_id}/{file.filename}"
    else:
        s3_key = f"audio/{file.filename}"
    logger.info(f"Uploading audio: {s3_key}")

    contents = await file.read()
    s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=contents)

    return {
        "status": "uploaded",
        "s3_key": s3_key,
        "filename": file.filename,
        "customer_id": customer_id,
        "message": "Transcription job will start automatically via Lambda trigger.",
    }


@app.get("/transcripts")
def list_transcripts(customer_id: str | None = None):
    """List completed transcripts. Optionally filter by customer_id."""
    try:
        prefix = f"transcripts/{customer_id}/" if customer_id else "transcripts/"
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
        transcripts = []
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".json"):
                name = os.path.basename(key).replace(".json", "")
                parts = key.replace("transcripts/", "").split("/")
                cid = parts[0] if len(parts) > 1 else None
                transcripts.append({
                    "name": name,
                    "key": key,
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "customer_id": cid,
                })
        transcripts.sort(key=lambda x: x["last_modified"], reverse=True)
        return transcripts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcripts/{filename}")
def get_transcript(filename: str, customer_id: str | None = None):
    """Retrieve a specific transcript and return the text + speaker segments.
    If customer_id is provided, looks up transcripts/{customer_id}/{filename}.json.
    Otherwise falls back to transcripts/{filename}.json (legacy path)."""
    if customer_id:
        s3_key = f"transcripts/{customer_id}/{filename}.json"
    else:
        s3_key = f"transcripts/{filename}.json"
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        result = json.loads(obj["Body"].read().decode())

        # Handle two formats:
        #   Transcribe output: {"results": {"transcripts": [...], "items": [...]}}
        #   Manually saved:    {"transcript": "...", "customer_id": "...", ...}
        if "results" in result:
            full_text = result["results"]["transcripts"][0]["transcript"]
            items = result["results"].get("items", [])
        else:
            full_text = result.get("transcript", "")
            items = []

        segments = []
        if items and items[0].get("speaker_label"):
            current_speaker = None
            current_words = []
            for item in items:
                speaker = item.get("speaker_label", current_speaker)
                word = item["alternatives"][0]["content"] if item.get("alternatives") else ""
                if speaker != current_speaker and current_words:
                    segments.append({"speaker": current_speaker, "text": " ".join(current_words)})
                    current_words = []
                current_speaker = speaker
                if word:
                    if item.get("type") == "punctuation" and current_words:
                        current_words[-1] += word
                    else:
                        current_words.append(word)
            if current_words:
                segments.append({"speaker": current_speaker, "text": " ".join(current_words)})

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


@app.post("/save-transcript")
def save_transcript(customer_id: str, transcript: str, source: str = "manual"):
    """Save a text transcript to S3 for a customer."""
    ts = int(time.time())
    s3_key = f"transcripts/{customer_id}/{source}_{ts}.json"
    payload = json.dumps({
        "customer_id": customer_id,
        "source": source,
        "timestamp": ts,
        "transcript": transcript,
    })
    s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=payload)
    return {"status": "saved", "key": s3_key, "customer_id": customer_id}

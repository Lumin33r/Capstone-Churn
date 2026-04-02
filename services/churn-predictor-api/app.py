"""
Churn Predictor API — FastAPI wrapper that looks up account data
by customer_id, combines with Agent 1 output, and calls SageMaker.

Routes: /predict and /health
"""

import io
import json
import os

import boto3
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Churn Predictor API")

# --- Config ---
REGION = os.environ.get("AWS_REGION", "us-east-1")
ENDPOINT_NAME = os.environ.get("SAGEMAKER_ENDPOINT", "churn-predictor-endpoint")
S3_BUCKET = os.environ.get("S3_BUCKET", "retention-engine-bucket")

sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)

# --- Load account data at startup ---
# Cache the joined customer + internet data in memory so we don't hit S3 every request
_account_data: pd.DataFrame | None = None


def load_account_data() -> pd.DataFrame:
    """Load and join internet + customer data from S3, cache in memory."""
    global _account_data
    if _account_data is not None:
        return _account_data

    # Load internet data
    obj = s3.get_object(Bucket=S3_BUCKET, Key="data/internet_data.csv")
    internet_df = pd.read_csv(io.BytesIO(obj["Body"].read()))

    # Load customer data
    obj = s3.get_object(Bucket=S3_BUCKET, Key="data/trilink_customers_data.csv")
    customers_df = pd.read_csv(io.BytesIO(obj["Body"].read()))

    # Join and index by customer_id
    merged = internet_df.merge(customers_df, on="customer_id", how="inner")
    _account_data = merged.set_index("customer_id")
    return _account_data


# --- Request / Response schemas ---
class PredictRequest(BaseModel):
    """Agent 1 output + customer_id. The wrapper looks up account data internally."""
    customer_id: str
    qa_score: float = 5.0
    sentiment: str = "Neutral"
    frustration_level: float = 5.0


class PredictResponse(BaseModel):
    churn_probability: float
    prediction: str
    risk_level: str
    customer_id: str


# --- Routes ---
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model": "churn-xgboost",
        "endpoint": ENDPOINT_NAME,
    }


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    try:
        # 1. Load account data
        account_data = load_account_data()

        # 2. Look up this customer
        if req.customer_id not in account_data.index:
            raise HTTPException(
                status_code=404,
                detail=f"Customer {req.customer_id} not found",
            )

        customer = account_data.loc[req.customer_id]

        # 3. Build the full feature payload for SageMaker
        payload = {
            # Service features (from account lookup)
            "plan_tier": customer["plan_tier"],
            "speed_mbps": int(customer["speed_mbps"]),
            "monthly_cost": float(customer["monthly_cost"]),
            "data_usage_gb": float(customer["data_usage_gb"]),
            "connected_devices": int(customer["connected_devices"]),
            "contract_type": customer["contract_type"],
            "speed_complaints": int(customer["speed_complaints"]),
            "outage_count": int(customer["outage_count"]),
            "internet_tenure_days": float(customer.get("internet_tenure_days", 0)),
            "contract_completed_percent": float(customer.get("contract_completed_percent", 0)),
            # Demographic features (from account lookup)
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
            # Agent 1 features (from request)
            "qa_score": req.qa_score,
            "sentiment": req.sentiment,
            "frustration_level": req.frustration_level,
        }

        # 4. Call SageMaker
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType="application/json",
            Body=json.dumps(payload),
        )

        result = json.loads(response["Body"].read().decode())
        return PredictResponse(
            customer_id=req.customer_id,
            **result,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

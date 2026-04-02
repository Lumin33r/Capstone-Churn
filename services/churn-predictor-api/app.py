"""
Churn Predictor API — FastAPI wrapper that calls the SageMaker endpoint.
Routes: /predict and /health
"""

import json
import os

import boto3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Churn Predictor API")

# --- Config ---
REGION = os.environ.get("AWS_REGION", "us-east-1")
ENDPOINT_NAME = os.environ.get("SAGEMAKER_ENDPOINT", "churn-predictor-endpoint")

sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=REGION)


# --- Request / Response schemas ---
class PredictRequest(BaseModel):
    plan_tier: str = "Standard_100"
    speed_mbps: float = 100
    monthly_cost: float = 75.0
    data_usage_gb: float = 200.0
    connected_devices: int = 5
    contract_type: str = "Month_to_Month"
    speed_complaints: int = 0
    outage_count: int = 0
    internet_tenure_days: float = 365.0
    contract_completed_percent: float = 0.5
    age: int = 35
    household_income: int = 60000
    income_bracket: str = "Middle"
    family_size: int = 3
    home_ownership: str = "Own"
    work_from_home_flag: bool = False
    education_level: str = "College"
    life_stage: str = "Established_Family"
    home_type: str = "Single_Family"
    home_square_footage: int = 1500
    property_value: int = 300000
    neighborhood_crime_rate: float = 3.0
    neighborhood_income_median: int = 55000
    fiber_availability: bool = True


class PredictResponse(BaseModel):
    churn_probability: float
    prediction: str
    risk_level: str


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
        payload = req.model_dump()

        # Convert bools to strings for the label encoder on the SageMaker side
        for key in ["work_from_home_flag", "fiber_availability"]:
            payload[key] = str(payload[key])

        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType="application/json",
            Body=json.dumps(payload),
        )

        result = json.loads(response["Body"].read().decode())
        return PredictResponse(**result)

    except sagemaker_runtime.exceptions.ModelError as e:
        raise HTTPException(status_code=502, detail=f"SageMaker model error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

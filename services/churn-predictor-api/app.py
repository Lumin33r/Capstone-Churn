"""
Churn Predictor API — FastAPI wrapper for the XGBoost churn model.
Loads the trained model and serves predictions via /predict and /health routes.
"""

import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Churn Predictor API")

# --- Load model artifacts at startup ---
MODEL_DIR = os.environ.get("MODEL_DIR", "/app/model")

model = joblib.load(Path(MODEL_DIR) / "churn_model.joblib")

with open(Path(MODEL_DIR) / "feature_columns.json") as f:
    FEATURE_COLUMNS = json.load(f)

with open(Path(MODEL_DIR) / "label_encoders.json") as f:
    LABEL_ENCODERS = json.load(f)


# --- Request / Response schemas ---
class PredictRequest(BaseModel):
    """Accepts customer + service features as key-value pairs."""
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
        "features": len(FEATURE_COLUMNS),
    }


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    try:
        row = req.model_dump()

        # Encode categorical / boolean fields using the saved label encoders
        for col, mapping in LABEL_ENCODERS.items():
            val = str(row.get(col, ""))
            if val not in mapping:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown value '{val}' for '{col}'. Valid: {list(mapping.keys())}",
                )
            row[col] = mapping[val]

        # Build a single-row DataFrame in the exact column order the model expects
        df = pd.DataFrame([row], columns=FEATURE_COLUMNS)

        # Predict
        proba = float(model.predict_proba(df)[0, 1])
        prediction = "churn" if proba >= 0.5 else "no_churn"
        risk_level = "HIGH" if proba >= 0.7 else "MEDIUM" if proba >= 0.4 else "LOW"

        return PredictResponse(
            churn_probability=round(proba, 4),
            prediction=prediction,
            risk_level=risk_level,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

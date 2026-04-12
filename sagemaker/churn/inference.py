"""
SageMaker inference script for the XGBoost churn prediction model.
Used with the SageMaker XGBoost container.

SageMaker calls these functions:
- model_fn: load the model from disk
- input_fn: parse the incoming request
- predict_fn: run the prediction
- output_fn: format the response
"""

import json
import os
import pickle

import numpy as np
import xgboost as xgb


def model_fn(model_dir):
    """Load the XGBoost model and supporting artifacts."""
    booster = xgb.Booster()
    booster.load_model(os.path.join(model_dir, "xgboost-model"))

    with open(os.path.join(model_dir, "feature_columns.json")) as f:
        feature_columns = json.load(f)

    with open(os.path.join(model_dir, "label_encoders.json")) as f:
        label_encoders = json.load(f)

    return {
        "booster": booster,
        "feature_columns": feature_columns,
        "label_encoders": label_encoders,
    }


def input_fn(request_body, request_content_type):
    """Parse the incoming request (JSON or CSV)."""
    if request_content_type == "application/json":
        return json.loads(request_body)
    if request_content_type == "text/csv":
        return [float(x) for x in request_body.strip().split(",")]
    raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(input_data, model_artifacts):
    """Run prediction using the loaded model."""
    booster = model_artifacts["booster"]
    feature_columns = model_artifacts["feature_columns"]

    if isinstance(input_data, list):
        # CSV input: already numeric values in feature-column order
        row = input_data
    else:
        # JSON input: needs label encoding
        label_encoders = model_artifacts["label_encoders"]
        for col, mapping in label_encoders.items():
            val = str(input_data.get(col, ""))
            if val in mapping:
                input_data[col] = mapping[val]
            else:
                input_data[col] = 0
        row = [float(input_data.get(col, 0)) for col in feature_columns]
    dmatrix = xgb.DMatrix(np.array([row]), feature_names=feature_columns)

    # Predict probability
    proba = float(booster.predict(dmatrix)[0])
    prediction = "churn" if proba >= 0.5 else "no_churn"
    risk_level = "HIGH" if proba >= 0.7 else "MEDIUM" if proba >= 0.4 else "LOW"

    return {
        "churn_probability": round(proba, 4),
        "prediction": prediction,
        "risk_level": risk_level,
    }


def output_fn(prediction, response_content_type):
    """Format the prediction as JSON."""
    return json.dumps(prediction)

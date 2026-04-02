"""
SageMaker inference script for the churn prediction model.

SageMaker calls these four functions:
- model_fn: load the model from disk
- input_fn: parse the incoming request
- predict_fn: run the prediction
- output_fn: format the response
"""

import json
import os

import joblib
import numpy as np
import pandas as pd


def model_fn(model_dir):
    """Load the model and supporting artifacts from the SageMaker model directory."""
    model = joblib.load(os.path.join(model_dir, "churn_model.joblib"))

    with open(os.path.join(model_dir, "feature_columns.json")) as f:
        feature_columns = json.load(f)

    with open(os.path.join(model_dir, "label_encoders.json")) as f:
        label_encoders = json.load(f)

    return {
        "model": model,
        "feature_columns": feature_columns,
        "label_encoders": label_encoders,
    }


def input_fn(request_body, request_content_type):
    """Parse the incoming JSON request."""
    if request_content_type == "application/json":
        return json.loads(request_body)
    raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(input_data, model_artifacts):
    """Run prediction using the loaded model."""
    model = model_artifacts["model"]
    feature_columns = model_artifacts["feature_columns"]
    label_encoders = model_artifacts["label_encoders"]

    # Encode categorical / boolean fields
    for col, mapping in label_encoders.items():
        val = str(input_data.get(col, ""))
        if val in mapping:
            input_data[col] = mapping[val]
        else:
            input_data[col] = 0  # fallback for unknown values

    # Build DataFrame in the correct column order
    df = pd.DataFrame([input_data], columns=feature_columns)

    # Predict
    proba = float(model.predict_proba(df)[0, 1])
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

"""
Deploy the churn prediction model to a SageMaker endpoint.

Usage:
    python deploy.py          # deploy new endpoint
    python deploy.py --delete # tear down endpoint

This script:
1. Packages the trained model as model.tar.gz
2. Uploads it to S3
3. Creates a SageMaker model, endpoint config, and endpoint
"""

import argparse
import json
import os
import tarfile
import time

import boto3

# ── Configuration ─────────────────────────────────────────────────────
REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ.get("S3_BUCKET", "sagemaker-us-east-1-388691194728")
MODEL_PREFIX = "models/churn"
ENDPOINT_NAME = "churn-predictor-endpoint"
MODEL_NAME = "churn-predictor-model"
ENDPOINT_CONFIG_NAME = "churn-predictor-config"
EXECUTION_ROLE_ARN = os.environ.get(
    "SAGEMAKER_ROLE_ARN",
    "arn:aws:iam::388691194728:role/service-role/AmazonSageMaker-ExecutionRole-20260224T095369",
)
INSTANCE_TYPE = "ml.m5.large"

# Model artifact paths (relative to this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILES = [
    os.path.join(SCRIPT_DIR, "churn_model.joblib"),
    os.path.join(SCRIPT_DIR, "label_encoders.json"),
    os.path.join(SCRIPT_DIR, "feature_columns.json"),
]
INFERENCE_SCRIPT = os.path.join(SCRIPT_DIR, "inference.py")
SETUP_SCRIPT = os.path.join(SCRIPT_DIR, "setup.py")


def package_model(tar_path: str) -> str:
    """Package model artifacts into a tar.gz for SageMaker."""
    print(f"Packaging model to {tar_path}...")
    with tarfile.open(tar_path, "w:gz") as tar:
        for filepath in MODEL_FILES:
            tar.add(filepath, arcname=os.path.basename(filepath))
        # SageMaker sklearn container needs inference.py + setup.py in code/
        tar.add(INFERENCE_SCRIPT, arcname="code/inference.py")
        tar.add(SETUP_SCRIPT, arcname="code/setup.py")
    print(f"  Created {tar_path}")
    return tar_path


def upload_to_s3(tar_path: str) -> str:
    """Upload model.tar.gz to S3 and return the S3 URI."""
    s3 = boto3.client("s3", region_name=REGION)
    s3_key = f"{MODEL_PREFIX}/model.tar.gz"
    print(f"Uploading to s3://{S3_BUCKET}/{s3_key}...")
    s3.upload_file(tar_path, S3_BUCKET, s3_key)
    s3_uri = f"s3://{S3_BUCKET}/{s3_key}"
    print(f"  Uploaded to {s3_uri}")
    return s3_uri


def create_endpoint(s3_uri: str) -> None:
    """Create SageMaker model, endpoint config, and endpoint."""
    sm = boto3.client("sagemaker", region_name=REGION)

    # 1. Create SageMaker Model
    print(f"Creating SageMaker model: {MODEL_NAME}...")
    try:
        sm.create_model(
            ModelName=MODEL_NAME,
            PrimaryContainer={
                "Image": f"683313688378.dkr.ecr.{REGION}.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3",
                "ModelDataUrl": s3_uri,
                "Environment": {
                    "SAGEMAKER_PROGRAM": "inference.py",
                },
            },
            ExecutionRoleArn=EXECUTION_ROLE_ARN,
        )
    except sm.exceptions.ClientError as e:
        if "Cannot create already existing model" in str(e):
            print("  Model already exists, deleting and recreating...")
            sm.delete_model(ModelName=MODEL_NAME)
            sm.create_model(
                ModelName=MODEL_NAME,
                PrimaryContainer={
                    "Image": f"683313688378.dkr.ecr.{REGION}.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3",
                    "ModelDataUrl": s3_uri,
                    "Environment": {
                        "SAGEMAKER_PROGRAM": "inference.py",
                    },
                },
                ExecutionRoleArn=EXECUTION_ROLE_ARN,
            )
        else:
            raise

    # 2. Create Endpoint Configuration
    print(f"Creating endpoint config: {ENDPOINT_CONFIG_NAME}...")
    try:
        sm.create_endpoint_config(
            EndpointConfigName=ENDPOINT_CONFIG_NAME,
            ProductionVariants=[
                {
                    "VariantName": "primary",
                    "ModelName": MODEL_NAME,
                    "InstanceType": INSTANCE_TYPE,
                    "InitialInstanceCount": 1,
                },
            ],
        )
    except sm.exceptions.ClientError as e:
        if "Cannot create already existing" in str(e):
            print("  Config already exists, deleting and recreating...")
            sm.delete_endpoint_config(EndpointConfigName=ENDPOINT_CONFIG_NAME)
            sm.create_endpoint_config(
                EndpointConfigName=ENDPOINT_CONFIG_NAME,
                ProductionVariants=[
                    {
                        "VariantName": "primary",
                        "ModelName": MODEL_NAME,
                        "InstanceType": INSTANCE_TYPE,
                        "InitialInstanceCount": 1,
                    },
                ],
            )
        else:
            raise

    # 3. Create Endpoint
    print(f"Creating endpoint: {ENDPOINT_NAME}...")
    try:
        sm.create_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=ENDPOINT_CONFIG_NAME,
        )
    except sm.exceptions.ClientError as e:
        if "Cannot create already existing" in str(e):
            print("  Endpoint already exists, updating...")
            sm.update_endpoint(
                EndpointName=ENDPOINT_NAME,
                EndpointConfigName=ENDPOINT_CONFIG_NAME,
            )
        else:
            raise

    # 4. Wait for endpoint to be in service
    print("Waiting for endpoint to be InService (this can take 5-10 minutes)...")
    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(
        EndpointName=ENDPOINT_NAME,
        WaiterConfig={"Delay": 30, "MaxAttempts": 30},
    )
    print(f"Endpoint {ENDPOINT_NAME} is InService!")


def delete_endpoint() -> None:
    """Tear down the endpoint, config, and model."""
    sm = boto3.client("sagemaker", region_name=REGION)

    try:
        print(f"Deleting endpoint: {ENDPOINT_NAME}...")
        sm.delete_endpoint(EndpointName=ENDPOINT_NAME)
    except Exception as e:
        print(f"  {e}")

    try:
        print(f"Deleting endpoint config: {ENDPOINT_CONFIG_NAME}...")
        sm.delete_endpoint_config(EndpointConfigName=ENDPOINT_CONFIG_NAME)
    except Exception as e:
        print(f"  {e}")

    try:
        print(f"Deleting model: {MODEL_NAME}...")
        sm.delete_model(ModelName=MODEL_NAME)
    except Exception as e:
        print(f"  {e}")


def test_endpoint() -> None:
    """Send a test prediction to the live endpoint."""
    runtime = boto3.client("sagemaker-runtime", region_name=REGION)

    test_payload = {
        "plan_tier": "Standard_100",
        "speed_mbps": 100,
        "monthly_cost": 74.0,
        "data_usage_gb": 300.0,
        "connected_devices": 5,
        "contract_type": "Month_to_Month",
        "speed_complaints": 4,
        "outage_count": 3,
        "internet_tenure_days": 200.0,
        "contract_completed_percent": 0.0,
        "age": 29,
        "household_income": 55000,
        "income_bracket": "Middle",
        "family_size": 2,
        "home_ownership": "Rent",
        "work_from_home_flag": False,
        "education_level": "College",
        "life_stage": "Single",
        "home_type": "Apartment",
        "home_square_footage": 800,
        "property_value": 200000,
        "neighborhood_crime_rate": 6.0,
        "neighborhood_income_median": 45000,
        "fiber_availability": True,
    }

    print("Sending test prediction...")
    response = runtime.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps(test_payload),
    )
    result = json.loads(response["Body"].read().decode())
    print(f"Result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy churn model to SageMaker")
    parser.add_argument("--delete", action="store_true", help="Delete the endpoint")
    parser.add_argument("--test", action="store_true", help="Test the live endpoint")
    args = parser.parse_args()

    if args.delete:
        delete_endpoint()
    elif args.test:
        test_endpoint()
    else:
        tar_path = os.path.join(SCRIPT_DIR, "model.tar.gz")
        package_model(tar_path)
        s3_uri = upload_to_s3(tar_path)
        create_endpoint(s3_uri)
        print("\nDone! Test with: python deploy.py --test")

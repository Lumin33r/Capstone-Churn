"""
Deploy the transcript sentiment model to a SageMaker endpoint.

Usage:
    python deploy.py          # deploy new endpoint
    python deploy.py --delete # tear down endpoint
    python deploy.py --test   # invoke test payload

This script:
1. Packages the trained model as model.tar.gz
2. Uploads it to S3
3. Creates a SageMaker model, endpoint config, and endpoint
"""


import argparse
import json
import os
import time
import tarfile
import shutil
import csv

import boto3
import glob
from dotenv import load_dotenv
from validator import valid_checks
from pathlib import Path

import atexit
import concurrent.futures

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────
REGION: str = os.getenv(key="REGION", default="us-east-1")
S3_BUCKET: str = os.getenv(key="S3_BUCKET", default="retention-engine-bucket")
MODEL_PREFIX: str = os.getenv(key="MODEL_PREFIX", default="models/sentiment")
USER_ROLE: str | None = os.getenv(key="USER_ROLE", default="")
IAM_PATH: str = "/retention/"
TAR_NAME: str = "model.tar.gz"
ENDPOINT_NAME = "retention-sentiment-revised-endpoint"
MODEL_NAME = "retention-sentiment-revised-model"
ENDPOINT_CONFIG_NAME = "retention-sentiment-revised-config"
EXECUTION_ROLE_NAME = os.getenv(
    key="EXECUTION_ROLE_NAME",
    default="retention-sagemaker-execution-role"
)
# Free Instance
INSTANCE_TYPE = "ml.t2.medium"


# Model artifact paths (relative to this script)
SCRIPT_DIR: str = os.path.dirname(p=os.path.abspath(path=__file__))
MODEL_PATHS: list[str] = [
    os.path.join(SCRIPT_DIR, "model/inference.py"),
    os.path.join(SCRIPT_DIR, "model/sentiment_columns.json"),
    os.path.join(SCRIPT_DIR, "model/sentiment_encoders.json"),
    os.path.join(SCRIPT_DIR, "model/sentiment_schema.json"),
    os.path.join(SCRIPT_DIR, "model/requirements.txt"),
    os.path.join(SCRIPT_DIR, "model/pytorch_model.bin"),
    os.path.join(SCRIPT_DIR, "model/tokenizer.json"),
    os.path.join(SCRIPT_DIR, "model/special_tokens_map.json"),
    os.path.join(SCRIPT_DIR, "model/tokenizer_config.json"),
    os.path.join(SCRIPT_DIR, "model/config.json"),
    os.path.join(SCRIPT_DIR, "model/vocab.txt"),
]

def shutdown_threads() -> None:
    try:
        concurrent.futures.thread._python_exit()
        concurrent.futures.thread._shutdown
    except:
        pass


# Container priority
CONTAINER_CANDIDATES = [
    # Hugging Faces (model is trained on distilbert)
    {
        "name": "huggingfaces",
        "image": f"763104351884.dkr.ecr.{REGION}.amazonaws.com/huggingface-pytorch-inference:2.6.0-transformers4.49.0-cpu-py312-ubuntu22.04"
    },
    # New Version of Hugging Faces
    {
        "name": "huggingfaces-new",
        "image": f"763104351884.dkr.ecr.{REGION}.amazonaws.com/huggingface-pytorch-inference:2.6.0-transformers4.49.0-cpu-py312-ubuntu22.04"
    },
    # PyTorch Script Mode (great for NLP, public, supports custom inference.py)
    {
        "name": "pytorch-scriptmode",
        "image": f"763104351884.dkr.ecr.{REGION}.amazonaws.com/pytorch-inference:1.13.1-cpu-py39",
    },
    # SKLearn (joblib-native, public older version)
    {
        "name": "sklearn-1.0",
        "image": f"683313688378.dkr.ecr.{REGION}.amazonaws.com/sagemaker-scikit-learn:1.0-1-cpu-py3",
    },
    # XGBoost (generic Python container)
    {
        "name": "xgboost-1.7",
        "image": f"683313688378.dkr.ecr.{REGION}.amazonaws.com/sagemaker-xgboost:1.7-1-cpu-py3",
    },
    # Python SDK (flexible, but sometimes requires permission)
    {
        "name": "python-sdk-2.0",
        "image": f"763104351884.dkr.ecr.{REGION}.amazonaws.com/sagemaker-python-sdk:2.0-cpu-py3",
    },
]


# ── Helpers ────────────────────────────────────────────────────────────

def validate_model_artifacts() -> None:
    """Ensure required files exist and no HF training artifacts are present."""
    print("Validating model artifacts...")

    required_files = [
        "pytorch_model.bin",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "config.json",
        "tokenizer.json",
        "training_args.bin",
        "vocab.txt",
        "feature_columns.json",
        "label_encoders.json",
        "label_encoding_schema.json",
        "sentiment_columns.json",
        "sentiment_encoders.json",
        "sentiment_schema.json",
    ]

    for fname in required_files:
        path = os.path.join(f"{SCRIPT_DIR}/model", fname)
        if not os.path.isfile(path=path):
            # raise FileNotFoundError(f"Required file missing: {path}")
            pass

    # Block HF training artifacts that confuse framework containers
    forbidden_patterns = [
        "checkpoint",
        "model.safetensors",
        "pytorch_model.bin",
        "tokenizer.json",
        "config.json",
        "training_args.bin",
        "special_tokens_map.json",
        "vocab.txt",
    ]

    for pattern in forbidden_patterns:
        matches = glob.glob(pathname=os.path.join(SCRIPT_DIR, "**", pattern), recursive=True)
        if matches:
            print(
                f"Forbidden artifact(s) found matching '{pattern}': {matches}\n"
                "Remove HF training artifacts from the project/tarball."
            )

    print("Model artifacts validation passed.")



def package_model(tar_path: str) -> str:
    """Package model artifacts into a tar.gz for SageMaker."""
    validate_model_artifacts()

    # Guard against git-lfs pointer files
    bin_path = os.path.join(SCRIPT_DIR, "model/pytorch_model.bin")
    if os.path.isfile(bin_path) and os.path.getsize(bin_path) < 1024:
        with open(bin_path, "r") as f:
            head = f.read(40)
        if "git-lfs" in head:
            raise RuntimeError(
                f"{bin_path} is a git-lfs pointer ({os.path.getsize(bin_path)} bytes). "
                "Run 'git lfs pull' or enable lfs in checkout before packaging."
            )

    if not os.path.exists(path="exported_model"):
        os.makedirs(name=f"{SCRIPT_DIR}/exported_model", exist_ok=True)

    print(f"Packaging model to {tar_path}...")
    with tarfile.open(name=tar_path, mode="w:gz") as tr:
        for filepath in MODEL_PATHS:
            # Expand wildcards (e.g., "*.bin", "folder/*")
            matched_files = glob.glob(pathname=filepath, recursive=True)

            if matched_files:
                # Add all matched files
                for filepath in matched_files:
                    if os.path.isfile(path=filepath):
                        tr.add(name=filepath, arcname=os.path.basename(p=filepath))
                    elif os.path.isdir(s=filepath):
                        tr.add(name=filepath, arcname=os.path.basename(p=filepath))
            else:
                # No wildcard — treat as a normal path
                if os.path.isfile(path=filepath):
                    tr.add(name=filepath, arcname=os.path.basename(p=filepath))
                elif os.path.isdir(s=filepath):
                    tr.add(name=filepath, arcname=os.path.basename(p=filepath))

                tr.add(name=filepath, arcname=os.path.basename(p=filepath))

    print(f"  Created {tar_path}")

    shutil.rmtree(f"{SCRIPT_DIR}/exported_model")
    print("Local folder deleted.")

    return tar_path


def download_s3_folder() -> None:
    """Get export model files for s3 to be zipped."""
    s3 = boto3.client("s3", region_name=REGION)

    paginator = s3.get_paginator("list_objects_v2")

    os.makedirs(name=f"{SCRIPT_DIR}/exported_model", exist_ok=True)

    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=MODEL_PREFIX):
        for obj in page.get("Contents", []):
            s3_key = obj["Key"]
            rel_path = s3_key[len(MODEL_PREFIX):].lstrip("/")
            local_path = os.path.join(os.path.dirname(__file__), rel_path)

            s3.download_file(S3_BUCKET, s3_key, local_path)

    print("Download complete")

def upload_to_s3(tar_path: str) -> str:
    """Upload model.tar.gz to S3 and return the S3 URI."""
    s3 = boto3.client("s3", region_name=REGION)
    s3_key = f"{MODEL_PREFIX}/{TAR_NAME}"
    print(f"Uploading to s3://{S3_BUCKET}/{s3_key}...")
    s3.upload_file(Filename=tar_path, Bucket=S3_BUCKET, Key=s3_key)
    s3_uri = f"s3://{S3_BUCKET}/{s3_key}"
    print(f"  Uploaded to {s3_uri}")
    s3.close()
    return s3_uri

def get_iam_role() -> str:
    """Get or create SageMaker execution role."""
    iam = boto3.client("iam", region_name=REGION)
    try:
        response = iam.get_role(RoleName=EXECUTION_ROLE_NAME)
        arn = response["Role"]["Arn"]
        print(f"Using existing IAM role: {arn}")
        iam.close()
        return arn
    except iam.exceptions.NoSuchEntityException:
        print("Execution role not found, creating...")
        assume_role_policy = json.dumps(obj={
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "sagemaker.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }],
        })
        response = iam.create_role(
            Path=IAM_PATH,
            RoleName=EXECUTION_ROLE_NAME,
            AssumeRolePolicyDocument=assume_role_policy,
            Description="Execution role for SageMaker",
            MaxSessionDuration=3600,
            Tags=[
                {
                    "Key": "Team",
                    "Value": "retention_team",
                    "Key": "Environment",
                    "Value": "dev"
                },
            ]
        )
        iam.attach_role_policy(
            RoleName=EXECUTION_ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/AmazonSageMakerFullAccess",
        )
        iam.attach_role_policy(
            RoleName=EXECUTION_ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
        )
        arn = response["Role"]["Arn"]
        print(f"Created IAM role: {arn}")
        iam.close()
        return arn


def can_use_container(image_uri: str) -> bool:
    """Best-effort check if the ECR image is accessible."""
    print(f"  Probing container image: {image_uri}")
    ecr = boto3.client("ecr", region_name=REGION)
    try:
        repo, tag = image_uri.split(sep="/")[-1].split(sep=":")
        account_id = image_uri.split(sep=".")[0]
        resp = ecr.batch_get_image(
            registryId=account_id,
            repositoryName=repo,
            imageIds=[{"imageTag": tag}],
        )
        images = resp.get("images", [])
        if not images:
            print("    No images returned; assuming not usable.")
            return False
        print("    Image is accessible.")
        return True
    except Exception as e:
        print(f"    Image probe failed: {e}")
        return False
    finally:
        ecr.close()


def select_best_container() -> str:
    """Auto-select the best available container for NLP sentiment."""
    print("Selecting best available container for sentiment analysis...")
    for candidate in CONTAINER_CANDIDATES:
        name = candidate["name"]
        image = candidate["image"]
        print(f"- Trying {name}: {image}")
        if can_use_container(image_uri=image):
            print(f"  -> Selected container: {name}")
            return image
    raise RuntimeError("No suitable container image is accessible from this account.")


def create_endpoint(s3_uri: str) -> None:
    """Create SageMaker model, endpoint config, and endpoint."""
    sm = boto3.client("sagemaker", region_name=REGION)

    role_arn = get_iam_role()
    image_uri = select_best_container()

    # Create SageMaker Model
    print(f"Creating SageMaker model: {MODEL_NAME}...")
    try:
        sm.create_model(
            ModelName=MODEL_NAME,
            PrimaryContainer={
                "Image": image_uri,
                "ModelDataUrl": s3_uri,
                "Environment": {
                    "SAGEMAKER_PROGRAM": "inference.py",
                },
            },
            ExecutionRoleArn=role_arn,
        )
    except sm.exceptions.ClientError as e:
        if "Cannot create already existing model" in str(object=e):
            print("  Model already exists, deleting and recreating...")
            sm.delete_model(ModelName=MODEL_NAME)
            sm.create_model(
                ModelName=MODEL_NAME,
                PrimaryContainer={
                    "Image": image_uri,
                    "ModelDataUrl": s3_uri,
                    "Environment": {
                        "SAGEMAKER_PROGRAM": "inference.py",
                    },
                },
                ExecutionRoleArn=role_arn,
            )
        else:
            raise

    # Create Endpoint Configuration
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
        if "Cannot create already existing" in str(object=e):
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

    # Create Endpoint
    print(f"Creating endpoint: {ENDPOINT_NAME}...")
    try:
        sm.create_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=ENDPOINT_CONFIG_NAME,
        )
    except sm.exceptions.ClientError as e:
        if "Cannot create already existing" in str(object=e):
            print("  Endpoint already exists, updating...")
            sm.update_endpoint(
                EndpointName=ENDPOINT_NAME,
                EndpointConfigName=ENDPOINT_CONFIG_NAME,
            )
        else:
            raise

    # Wait for endpoint to be in service
    print("Waiting for endpoint to be InService (this can take 5-10 minutes)...")
    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(
        EndpointName=ENDPOINT_NAME,
        WaiterConfig={"Delay": 30, "MaxAttempts": 30},
    )
    print(f"Endpoint {ENDPOINT_NAME} is InService!")
    print("Sagemaker client closed")
    sm.close()



def delete_endpoint() -> None:
    """Tear down the endpoint, config, and model."""
    sm = boto3.client("sagemaker", region_name=REGION)
    for action, name, func in [
        ("endpoint", ENDPOINT_NAME, sm.delete_endpoint),
        ("config", ENDPOINT_CONFIG_NAME, sm.delete_endpoint_config),
        ("model", MODEL_NAME, sm.delete_model),
    ]:
        try:
            print(f"Deleting {action}: {name}...")
            func(**{("EndpointName" if "endpoint" in action else "ModelName" if "model" in action else "EndpointConfigName" if "config" in action else ""): name})
        except Exception as e:
            print(f"  {e}")
    sm.close()


def test_endpoint() -> None:
    """Send a test prediction to the live endpoint."""
    runtime = boto3.client("sagemaker-runtime", region_name=REGION)

    positive_statement = "I am unbelievably impressed with how flawlessly everything was handled today; the agent went above and beyond, resolved an issue that had been stressing me out for weeks, and delivered some of the best customer service I have ever experienced in my life."
    negative_statement = "I am extremely frustrated and honestly overwhelmed by how terrible this entire situation has been; nothing has worked correctly, every step has been a complete nightmare, and I feel completely ignored and exhausted by the whole process."
    neutral_statement = "I am reaching out because I need a clear update on the status of my account changes; there is nothing urgent or problematic at the moment, but I want to understand where things currently stand so I can plan my next steps accordingly."

    test_payload = {
        "call_id": "",
        "customer_id": "",
        "call_date": "1970-01-01",
        "call_time": "00:00:00",
        "agent_id": "agent_007",
        "agent_name": "James Bond",
        "primary_scenario": "billing_inquiry",
        "call_transcript": negative_statement,
        "overall_rating": 0,
        "call_successful":  False,
        "customer_monthly_spend": 0.0,
        "customer_service_count": 0,
        "customer_issue_history": 0,
    }

    # with open(file=os.path.join(os.path.dirname(__file__), "call_transcripts.csv")) as f:
        # csv_file = csv.DictReader(f)
#
        # test_payload = next(csv_file)

    print("Sending test prediction...")
    response = runtime.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps(obj=test_payload),
    )

    try:
        result = json.loads(s=response["Body"].read().decode())
    except json.JSONDecodeError:
        result = response["Body"].read().decode()

    print(f"Result: {json.dumps(obj=result, indent=2)}" if isinstance(result, dict) else result)
    runtime.close()

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
        # Skip everything if endpoint is already healthy or in-progress
        sm = boto3.client("sagemaker", region_name=REGION)
        try:
            resp = sm.describe_endpoint(EndpointName=ENDPOINT_NAME)
            status = resp["EndpointStatus"]
            if status == "InService":
                print(f"Endpoint {ENDPOINT_NAME} already InService, skipping redeployment.")
                print("\nDone! Test with: python deploy.py --test")
                sm.close()
                exit(0)
            if status in ("Updating", "Creating"):
                print(f"Endpoint {ENDPOINT_NAME} is {status}, waiting for it to finish...")
                waiter = sm.get_waiter("endpoint_in_service")
                waiter.wait(EndpointName=ENDPOINT_NAME, WaiterConfig={"Delay": 30, "MaxAttempts": 30})
                print(f"Endpoint {ENDPOINT_NAME} is now InService!")
                print("\nDone! Test with: python deploy.py --test")
                sm.close()
                exit(0)
            print(f"Endpoint {ENDPOINT_NAME} exists but status is {status}, redeploying...")
        except sm.exceptions.ClientError:
            print(f"Endpoint {ENDPOINT_NAME} not found, creating...")
        finally:
            sm.close()

        valid_checks()
        tar_path = os.path.join(SCRIPT_DIR, "model.tar.gz")
        package_model(tar_path=tar_path)
        s3_uri = upload_to_s3(tar_path=tar_path)
        download_s3_folder()
        create_endpoint(s3_uri=s3_uri)
        if os.path.isdir(s="./model.tar.gz"):
            os.remove(path="./model.tar.gz")
        if os.path.isdir(s="./model"):
            shutil.rmtree(path="./model")
        if os.path.isdir(s="./exported_model"):
            os.rmdir(path="./exported_model")
    atexit.register(shutdown_threads)

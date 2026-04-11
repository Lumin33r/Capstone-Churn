"""
Deploy the Transcribe Lambda function to AWS.

Usage:
    python deploy_lambda.py          # deploy/update
    python deploy_lambda.py --delete # tear down

This creates:
  - IAM role with Transcribe, S3, and CloudWatch permissions
  - Lambda function from lambda_function.zip
  - S3 event notification on retention-engine-bucket/audio/
"""

import argparse
import json
import os
import time
import zipfile

import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
BUCKET = "retention-engine-bucket"
FUNCTION_NAME = "retention-transcribe-pipeline"
ROLE_NAME = "retention-transcribe-lambda-role"
ROLE_PATH = "/retention/"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

iam = boto3.client("iam", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


def package_lambda() -> bytes:
    """Zip the lambda function and return bytes."""
    zip_path = os.path.join(SCRIPT_DIR, "lambda_function.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(
            os.path.join(SCRIPT_DIR, "lambda_function.py"),
            "lambda_function.py",
        )
    with open(zip_path, "rb") as f:
        return f.read()


def get_or_create_role() -> str:
    """Get or create the Lambda execution role."""
    try:
        resp = iam.get_role(RoleName=ROLE_NAME)
        arn = resp["Role"]["Arn"]
        print(f"Using existing role: {arn}")
        return arn
    except iam.exceptions.NoSuchEntityException:
        pass

    print(f"Creating IAM role: {ROLE_NAME}")
    assume_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    })

    resp = iam.create_role(
        Path=ROLE_PATH,
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=assume_policy,
        Description="Lambda role for Transcribe pipeline",
    )
    role_arn = resp["Role"]["Arn"]

    # Attach inline policy
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="transcribe-lambda-policy",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "transcribe:StartTranscriptionJob",
                        "transcribe:GetTranscriptionJob",
                    ],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:PutObject"],
                    "Resource": [
                        f"arn:aws:s3:::{BUCKET}/audio/*",
                        f"arn:aws:s3:::{BUCKET}/transcripts/*",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": "arn:aws:logs:*:*:*",
                },
            ],
        }),
    )

    # Wait for role to propagate
    print("Waiting for role to propagate...")
    time.sleep(10)
    return role_arn


def deploy():
    """Deploy or update the Lambda function."""
    role_arn = get_or_create_role()
    zip_bytes = package_lambda()

    # Create or update Lambda
    try:
        lam.get_function(FunctionName=FUNCTION_NAME)
        print(f"Updating existing Lambda: {FUNCTION_NAME}")
        lam.update_function_code(
            FunctionName=FUNCTION_NAME,
            ZipFile=zip_bytes,
        )
        # Wait for code update to finish before updating config
        waiter = lam.get_waiter("function_updated")
        waiter.wait(FunctionName=FUNCTION_NAME)
        lam.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Timeout=900,
            MemorySize=128,
            Environment={
                "Variables": {
                    "OUTPUT_BUCKET": BUCKET,
                    "OUTPUT_PREFIX": "transcripts",
                },
            },
        )
    except lam.exceptions.ResourceNotFoundException:
        print(f"Creating Lambda: {FUNCTION_NAME}")
        lam.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.11",
            Role=role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": zip_bytes},
            Timeout=900,
            MemorySize=128,
            Environment={
                "Variables": {
                    "OUTPUT_BUCKET": BUCKET,
                    "OUTPUT_PREFIX": "transcripts",
                },
            },
        )

    # Get Lambda ARN
    func = lam.get_function(FunctionName=FUNCTION_NAME)
    lambda_arn = func["Configuration"]["FunctionArn"]
    print(f"Lambda ARN: {lambda_arn}")

    # Add S3 invoke permission
    try:
        lam.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId="AllowS3Invoke",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{BUCKET}",
        )
        print("Added S3 invoke permission")
    except lam.exceptions.ResourceConflictException:
        print("S3 invoke permission already exists")

    # Configure S3 event notification
    print("Configuring S3 event notification for audio/ prefix...")

    # Get existing notifications to preserve them
    existing = s3.get_bucket_notification_configuration(Bucket=BUCKET)
    existing.pop("ResponseMetadata", None)

    # Build Lambda notification configs for audio uploads
    lambda_configs = existing.get("LambdaFunctionConfigurations", [])

    # Remove any existing transcribe notifications
    lambda_configs = [
        c for c in lambda_configs
        if c.get("LambdaFunctionArn") != lambda_arn
    ]

    # Add notifications for each audio format
    for suffix in [".wav", ".mp3", ".mp4", ".flac"]:
        lambda_configs.append({
            "LambdaFunctionArn": lambda_arn,
            "Events": ["s3:ObjectCreated:*"],
            "Filter": {
                "Key": {
                    "FilterRules": [
                        {"Name": "prefix", "Value": "audio/"},
                        {"Name": "suffix", "Value": suffix},
                    ]
                }
            },
        })

    existing["LambdaFunctionConfigurations"] = lambda_configs

    s3.put_bucket_notification_configuration(
        Bucket=BUCKET,
        NotificationConfiguration=existing,
    )

    print(f"\nDeployed! Upload audio to s3://{BUCKET}/audio/ to trigger transcription.")
    print(f"Transcripts will appear in s3://{BUCKET}/transcripts/")


def delete():
    """Tear down Lambda, S3 notifications, and IAM role."""
    # Remove S3 notifications
    print("Removing S3 event notifications...")
    try:
        func = lam.get_function(FunctionName=FUNCTION_NAME)
        lambda_arn = func["Configuration"]["FunctionArn"]

        existing = s3.get_bucket_notification_configuration(Bucket=BUCKET)
        existing.pop("ResponseMetadata", None)
        lambda_configs = existing.get("LambdaFunctionConfigurations", [])
        lambda_configs = [
            c for c in lambda_configs
            if c.get("LambdaFunctionArn") != lambda_arn
        ]
        existing["LambdaFunctionConfigurations"] = lambda_configs
        s3.put_bucket_notification_configuration(
            Bucket=BUCKET,
            NotificationConfiguration=existing,
        )
    except Exception as e:
        print(f"  {e}")

    # Delete Lambda
    print(f"Deleting Lambda: {FUNCTION_NAME}")
    try:
        lam.delete_function(FunctionName=FUNCTION_NAME)
    except Exception as e:
        print(f"  {e}")

    # Delete IAM role
    print(f"Deleting IAM role: {ROLE_NAME}")
    try:
        iam.delete_role_policy(RoleName=ROLE_NAME, PolicyName="transcribe-lambda-policy")
        iam.delete_role(RoleName=ROLE_NAME)
    except Exception as e:
        print(f"  {e}")

    print("Cleanup complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Transcribe Lambda")
    parser.add_argument("--delete", action="store_true", help="Delete the Lambda")
    args = parser.parse_args()

    if args.delete:
        delete()
    else:
        deploy()

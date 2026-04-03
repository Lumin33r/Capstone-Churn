from typing import Any
from dotenv import load_dotenv
import boto3, os

load_dotenv()

BUCKET_NAME = os.getenv(key="BUCKET_NAME")

s3_client = boto3.client('s3')


def get_s3_file(bucket_name: str, key: str | None = None) -> dict[str, Any]:
    """
    Retrieves the object from the specified S3 bucket.
    """
    try:
        return s3_client.get_object(Bucket=bucket_name)
    except Exception as e:
        raise Exception(f"Error finding S3 bucket/object: {str(object=e)}")


def extract_data_as_string(s3_object: dict[str, Any]) -> str:
    """
    Reads the streaming body of an S3 object and returns the decoded string.
    """
    return s3_object['Body'].read().decode('utf-8')
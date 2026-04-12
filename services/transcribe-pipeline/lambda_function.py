"""
AWS Lambda: S3 audio upload → Amazon Transcribe → transcript saved to S3.

Trigger: S3 PUT event on retention-engine-bucket/audio/
Output:  JSON transcript written to retention-engine-bucket/transcripts/

The transcript is then available for the sentiment analysis tool
and the LangGraph agent to consume via the analyze_call tool.
"""

import json
import os
import time
import logging
import boto3
from urllib.parse import unquote_plus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-east-1")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", "retention-engine-bucket")
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "transcripts")

transcribe = boto3.client("transcribe", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


def lambda_handler(event, context):
    """Handle S3 PUT event — start a Transcribe job for the uploaded audio."""

    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])

    logger.info(f"New audio file: s3://{bucket}/{key}")

    # Extract filename without extension for job naming
    filename = os.path.splitext(os.path.basename(key))[0]
    job_name = f"retention-{filename}-{int(time.time())}"

    # Determine media format from extension
    ext = os.path.splitext(key)[1].lower().lstrip(".")
    media_format = ext if ext in ("mp3", "mp4", "wav", "flac", "ogg", "webm") else "wav"

    # Start transcription job
    logger.info(f"Starting Transcribe job: {job_name}")
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": f"s3://{bucket}/{key}"},
        MediaFormat=media_format,
        LanguageCode="en-US",
        OutputBucketName=OUTPUT_BUCKET,
        OutputKey=f"{OUTPUT_PREFIX}/{filename}.json",
        Settings={
            "ShowSpeakerLabels": True,
            "MaxSpeakerLabels": 2,  # agent + customer
        },
    )

    # Wait for job completion (Lambda has up to 15 min timeout)
    while True:
        status = transcribe.get_transcription_job(
            TranscriptionJobName=job_name
        )
        job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]
        logger.info(f"Job {job_name} status: {job_status}")

        if job_status == "COMPLETED":
            transcript_uri = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
            logger.info(f"Transcript saved: {transcript_uri}")

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "job_name": job_name,
                    "status": "COMPLETED",
                    "transcript_key": f"{OUTPUT_PREFIX}/{filename}.json",
                    "source_audio": f"s3://{bucket}/{key}",
                }),
            }

        if job_status == "FAILED":
            reason = status["TranscriptionJob"].get("FailureReason", "Unknown")
            logger.error(f"Transcription failed: {reason}")
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "job_name": job_name,
                    "status": "FAILED",
                    "reason": reason,
                }),
            }

        time.sleep(5)

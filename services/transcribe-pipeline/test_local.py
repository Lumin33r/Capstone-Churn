"""
Test the Transcribe pipeline locally (without Lambda).

Usage:
    python test_local.py <audio_file>
    python test_local.py sample_call.wav

This uploads the audio to S3 audio/ prefix and starts a Transcribe job
directly, then polls for completion and prints the transcript.
"""

import sys
import json
import time
import boto3

REGION = "us-east-1"
BUCKET = "retention-engine-bucket"

s3 = boto3.client("s3", region_name=REGION)
transcribe = boto3.client("transcribe", region_name=REGION)


def test_transcribe(audio_path: str):
    filename = audio_path.rsplit("/", 1)[-1]
    s3_key = f"audio/{filename}"

    # 1. Upload audio to S3
    print(f"Uploading {audio_path} → s3://{BUCKET}/{s3_key}")
    s3.upload_file(audio_path, BUCKET, s3_key)

    # 2. Start transcription job
    job_name = f"retention-test-{int(time.time())}"
    ext = filename.rsplit(".", 1)[-1].lower()
    print(f"Starting Transcribe job: {job_name}")

    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": f"s3://{BUCKET}/{s3_key}"},
        MediaFormat=ext if ext in ("mp3", "mp4", "wav", "flac") else "wav",
        LanguageCode="en-US",
        OutputBucketName=BUCKET,
        OutputKey=f"transcripts/{filename.rsplit('.', 1)[0]}.json",
        Settings={
            "ShowSpeakerLabels": True,
            "MaxSpeakerLabels": 2,
        },
    )

    # 3. Poll for completion
    while True:
        resp = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        status = resp["TranscriptionJob"]["TranscriptionJobStatus"]
        print(f"  Status: {status}")

        if status == "COMPLETED":
            break
        if status == "FAILED":
            print(f"  Failed: {resp['TranscriptionJob'].get('FailureReason')}")
            return

        time.sleep(5)

    # 4. Fetch and display the transcript
    transcript_key = f"transcripts/{filename.rsplit('.', 1)[0]}.json"
    obj = s3.get_object(Bucket=BUCKET, Key=transcript_key)
    result = json.loads(obj["Body"].read().decode())

    full_text = result["results"]["transcripts"][0]["transcript"]
    print(f"\n--- Transcript ---\n{full_text}\n")

    # Show speaker segments if available
    if "speaker_labels" in result["results"]:
        print("--- Speaker Segments ---")
        for seg in result["results"]["speaker_labels"]["segments"]:
            speaker = seg["speaker_label"]
            text = " ".join(item["alternatives"][0]["content"] for item in seg["items"])
            print(f"  {speaker}: {text}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_local.py <audio_file>")
        sys.exit(1)
    test_transcribe(sys.argv[1])

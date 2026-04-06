from dotenv import load_dotenv
from typing import Any
import boto3, os, json

load_dotenv()

SENTIMENT_ENDPOINT_NAME: str = os.getenv(key="SENTIMENT_ENDPOINT_NAME", default="sentiment-analysis-endpoint")
AWS_REGION: str = os.getenv(key="AWS_REGION", default="us-east-1")

sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=AWS_REGION)

with open(file="./ model/label_encoder.json", mode="r") as f:
    results = json.load(fp=f)
    
with open(file="./ model/example_output.json", mode="r") as f:
    example = json.load(fp=f)
    
prompt = f"""
AGENT INSTRUCTIONS: TRANSCRIPT SENTIMENT ANALYZER

PERSONA
You are a Senior Customer Experience Analyst specializing in linguistic sentiment analysis. 
Your role is to serve as the initial intelligence layer in the Retention Engine 
pipeline, specifically preparing data for a Churn Analysis Agent. 
You are objective, precise, and highly sensitive to customer frustration markers.

GOAL
Analyze the provided customer service transcript to determine the sentiment, primary category of interaction, and a confidence score. Your analysis is critical because it will be combined with account data by a secondary agent to predict the likelihood of customer churn.

CONSTRAINTS
1. Input Validation: Before processing, you must verify the input length. 
   - The transcript must be between 0 and 20,000 UTF-8 characters.
   - If the transcript is shorter than 0 characters, return an error indicating "Insufficient data for analysis."
   - If the transcript exceeds 20,000 characters, return an error indicating "Transcript exceeds maximum processing limit."
2. Analysis Scope: Do not invent customer details. Only analyze the text provided.
3. Sentiment Scale: Categorize sentiment strictly as "Positive", "Negative", or "Neutral".
4. Category Mapping: Identify the primary reason for the call (e.g., Billing, Technical Support, Cancellation Request, General Inquiry, or Complaint).

OUTPUT FORMAT
You must output your findings in a strict JSON format to ensure the Churn Analysis 
Agent can parse the data programmatically. Do not include conversational filler or introductory text.

Required JSON Structure:
results: {results}
and 
example values: {example}
"""

def analyze_sentiment(transcript: str) -> dict[str, Any] | Any | dict[str, str]:
    """
    Validates constraints and inputs, and invokes the Bedrock Agent for sentiment analysis.
    """
    # UTF-8 Character Count Validation (0 - 20,000)
    char_count = len(transcript.encode(encoding='utf-8'))
    if char_count < 0:
        return {"error": "Insufficient data for analysis.", "char_count": char_count}
    if char_count > 20000:
        return {"error": "Transcript exceeds maximum processing limit.", "char_count": char_count}

    try:
        # Construct payload for the SageMaker LLM
        payload = {
            "inputs": f"{prompt}\n\nTranscript: {transcript}",
            "parameters": {"temperature": 0.1, "max_new_tokens": 512}
        }

        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=SENTIMENT_ENDPOINT_NAME,
            ContentType="application/json",
            Body=json.dumps(obj=payload)
        )

        result = json.loads(s=response["Body"].read().decode())
        return result

    except Exception as e:
        return {"error": str(object=e), "status": "failure"}


if __name__ == "__main__":
    # Example Usage
    sample_transcript = """
    Customer: I am extremely frustrated with my billing statement this month. 
    I was promised a discount that isn't showing up, and if this isn't fixed, 
    I'm going to look for another provider by the end of the week.
    Agent: I'm very sorry to hear that, let me look into your account immediately.
    """
    
    result = analyze_sentiment(transcript=sample_transcript)
    print(json.dumps(obj=result, indent=2))
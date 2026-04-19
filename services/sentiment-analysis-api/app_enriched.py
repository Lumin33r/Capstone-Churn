"""
Sentiment Analysis API — Enriched FastAPI wrapper.

Calls Okino's SageMaker DistilBERT endpoint for base sentiment classification,
then enriches with emotion scores, qa_score, and behavioral flags using
lightweight NLP post-processing.

Returns all 7 fields Agent 2 (churn predictor) needs:
  qa_score, sentiment, emotion_frustration, emotion_anger,
  sentiment_shift, escalation_flag, resolution_flag
"""

import json
import logging
import os
import re
from typing import Any

import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sentiment Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Config ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SENTIMENT_ENDPOINT = os.getenv(
    "SENTIMENT_ENDPOINT_NAME", "retention-sentiment-revised-endpoint"
)

sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=AWS_REGION)

# Sentiment label decoder (from Okino's label_encoder.json)
SENTIMENT_LABELS = {0: "Negative", 1: "Neutral", 2: "Positive"}

# Escalation keywords
ESCALATION_KEYWORDS = [
    "speak to a manager", "supervisor", "escalate", "cancel my",
    "cancellation", "close my account", "switch provider", "lawsuit",
    "attorney", "legal action", "BBB", "better business bureau",
    "complaint", "unacceptable", "ridiculous", "worst service",
]

# Resolution keywords
RESOLUTION_KEYWORDS = [
    "thank you", "that helps", "sounds good", "i appreciate",
    "resolved", "fixed", "taken care of", "great", "perfect",
    "that works", "satisfied", "happy with",
]

# Negative emotion words
NEGATIVE_WORDS = [
    "frustrated", "angry", "upset", "disappointed", "annoyed",
    "furious", "terrible", "horrible", "awful", "hate",
    "disgusted", "outraged", "fed up", "sick of", "tired of",
    "unacceptable", "ridiculous", "absurd", "pathetic", "useless",
    "broken", "failed", "worst", "never", "waste",
]

# Positive emotion words
POSITIVE_WORDS = [
    "happy", "pleased", "satisfied", "great", "excellent",
    "wonderful", "fantastic", "perfect", "thank", "appreciate",
    "helpful", "resolved", "fixed", "love", "good",
    "amazing", "outstanding", "impressed", "recommend",
]


# --- NLP Processing Functions ---

def compute_text_features(transcript: str) -> dict[str, Any]:
    """Extract text-level features from the transcript."""
    words = transcript.split()
    word_count = len(words)
    avg_word_length = sum(len(w) for w in words) / max(word_count, 1)
    num_exclamation = transcript.count("!")
    lower = transcript.lower()

    num_negative = sum(1 for w in NEGATIVE_WORDS if w in lower)
    num_positive = sum(1 for w in POSITIVE_WORDS if w in lower)

    return {
        "word_count": word_count,
        "avg_word_length": round(avg_word_length, 2),
        "num_exclamation_marks": num_exclamation,
        "num_negative_words": num_negative,
        "num_positive_words": num_positive,
    }


def compute_emotion_scores(transcript: str, text_features: dict) -> dict[str, float]:
    """Compute emotion scores from transcript text analysis.

    Uses keyword density, punctuation patterns, and negative/positive word
    ratios to estimate emotion intensities. Not a neural model — a
    rule-based approximation that's deterministic and fast.
    """
    lower = transcript.lower()
    word_count = max(text_features["word_count"], 1)
    neg_ratio = text_features["num_negative_words"] / max(word_count / 50, 1)
    pos_ratio = text_features["num_positive_words"] / max(word_count / 50, 1)
    excl_ratio = text_features["num_exclamation_marks"] / max(word_count / 100, 1)

    # Frustration: driven by negative words + exclamation marks + specific phrases
    frustration_phrases = ["waiting", "hold", "again", "already told", "how many times",
                           "still not", "nothing has", "keeps happening"]
    frustration_hits = sum(1 for p in frustration_phrases if p in lower)
    frustration = min(1.0, round(neg_ratio * 0.4 + excl_ratio * 0.2 +
                                  frustration_hits * 0.15, 2))

    # Anger: driven by strong negative words + capitalization + exclamation
    anger_phrases = ["furious", "outraged", "angry", "unacceptable", "ridiculous",
                     "disgusted", "hate", "worst"]
    anger_hits = sum(1 for p in anger_phrases if p in lower)
    caps_ratio = sum(1 for c in transcript if c.isupper()) / max(len(transcript), 1)
    anger = min(1.0, round(anger_hits * 0.25 + excl_ratio * 0.15 +
                            caps_ratio * 0.3, 2))

    # Joy: driven by positive words
    joy = min(1.0, round(pos_ratio * 0.5, 2))

    # Sadness: "disappointed", "let down", "unfortunate"
    sad_phrases = ["disappointed", "let down", "unfortunate", "sad", "unhappy",
                   "depressing", "heartbroken"]
    sad_hits = sum(1 for p in sad_phrases if p in lower)
    sadness = min(1.0, round(sad_hits * 0.3 + neg_ratio * 0.1, 2))

    # Fear: "worried", "concerned", "afraid"
    fear_phrases = ["worried", "concerned", "afraid", "scared", "anxious",
                    "nervous", "panic"]
    fear_hits = sum(1 for p in fear_phrases if p in lower)
    fear = min(1.0, round(fear_hits * 0.3, 2))

    return {
        "anger": anger,
        "frustration": frustration,
        "joy": joy,
        "sadness": sadness,
        "fear": fear,
    }


def compute_sentiment_shift(transcript: str) -> float:
    """Compute sentiment shift by comparing first half vs second half.

    Returns a value from -1 (worsening) to +1 (improving).
    """
    mid = len(transcript) // 2
    first_half = transcript[:mid].lower()
    second_half = transcript[mid:].lower()

    def score_half(text: str) -> float:
        pos = sum(1 for w in POSITIVE_WORDS if w in text)
        neg = sum(1 for w in NEGATIVE_WORDS if w in text)
        total = max(pos + neg, 1)
        return (pos - neg) / total

    first_score = score_half(first_half)
    second_score = score_half(second_half)

    return round(second_score - first_score, 2)


def detect_escalation(transcript: str) -> bool:
    """Detect if the customer escalated or threatened to leave."""
    lower = transcript.lower()
    return any(kw in lower for kw in ESCALATION_KEYWORDS)


def detect_resolution(transcript: str) -> bool:
    """Detect if the call was resolved positively."""
    lower = transcript.lower()
    # Check the last 30% of the transcript for resolution indicators
    tail = lower[int(len(lower) * 0.7):]
    return any(kw in tail for kw in RESOLUTION_KEYWORDS)


def compute_qa_score(
    sentiment_label: str,
    confidence: float,
    emotions: dict,
    text_features: dict,
    escalated: bool,
    resolved: bool,
) -> float:
    """Compute a QA score (0-10) from all available signals.

    Higher score = better call quality from the agent's perspective.
    """
    score = 5.0  # baseline

    # Sentiment contribution
    if sentiment_label == "Positive":
        score += 2.0
    elif sentiment_label == "Negative":
        score -= 2.0

    # Confidence adjusts magnitude
    score += (confidence - 0.5) * 1.0

    # Emotion penalties
    score -= emotions.get("frustration", 0) * 1.5
    score -= emotions.get("anger", 0) * 2.0
    score += emotions.get("joy", 0) * 1.0

    # Resolution bonus, escalation penalty
    if resolved:
        score += 1.5
    if escalated:
        score -= 1.5

    return round(max(0.0, min(10.0, score)), 1)


# --- SageMaker Endpoint Call ---

def call_sagemaker_sentiment(transcript: str) -> dict:
    """Call Okino's DistilBERT endpoint for base sentiment classification."""
    try:
        payload = json.dumps({"call_transcript": transcript})
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=SENTIMENT_ENDPOINT,
            ContentType="application/json",
            Body=payload,
        )
        result = json.loads(response["Body"].read().decode())

        # Parse the nested response format
        if isinstance(result, list) and len(result) > 0:
            inner = result[0]
            if isinstance(inner, str):
                inner = json.loads(inner)
                if isinstance(inner, list):
                    inner = inner[0]

            sentiment_int = inner.get("sentiment", 1)
            confidence = inner.get("confidence", 0.5)
        else:
            sentiment_int = 1
            confidence = 0.5

        label = SENTIMENT_LABELS.get(sentiment_int, "Neutral")
        return {"sentiment": label, "confidence": confidence}

    except Exception as e:
        logger.error(f"SageMaker call failed: {e}")
        return {"sentiment": "Neutral", "confidence": 0.5}


# --- Request/Response Models ---

class PredictRequest(BaseModel):
    transcript: str
    customer_id: str | None = None
    call_id: str | None = None


class PredictResponse(BaseModel):
    # The 7 fields Agent 2 needs
    qa_score: float
    sentiment: str
    emotion_frustration: float
    emotion_anger: float
    sentiment_shift: float
    escalation_flag: bool
    resolution_flag: bool
    # Additional context
    confidence: float
    customer_id: str | None = None
    call_id: str | None = None
    emotion_joy: float
    emotion_sadness: float
    emotion_fear: float
    word_count: int
    num_negative_words: int
    num_positive_words: int


# --- Routes ---

@app.get("/health")
def health():
    return {"status": "healthy", "service": "sentiment-analysis", "endpoint": SENTIMENT_ENDPOINT}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    """Analyze a transcript and return enriched sentiment features."""
    if not req.transcript or len(req.transcript.strip()) < 10:
        raise HTTPException(status_code=400, detail="Transcript too short for analysis")

    transcript = req.transcript.strip()

    # 1. Call SageMaker for base sentiment classification
    sagemaker_result = call_sagemaker_sentiment(transcript)
    sentiment_label = sagemaker_result["sentiment"]
    confidence = sagemaker_result["confidence"]

    # 2. Compute text features
    text_features = compute_text_features(transcript)

    # 3. Compute emotion scores
    emotions = compute_emotion_scores(transcript, text_features)

    # 4. Compute sentiment shift
    shift = compute_sentiment_shift(transcript)

    # 5. Detect escalation and resolution
    escalated = detect_escalation(transcript)
    resolved = detect_resolution(transcript)

    # 6. Compute composite QA score
    qa_score = compute_qa_score(
        sentiment_label, confidence, emotions, text_features, escalated, resolved
    )

    return PredictResponse(
        qa_score=qa_score,
        sentiment=sentiment_label,
        emotion_frustration=emotions["frustration"],
        emotion_anger=emotions["anger"],
        sentiment_shift=shift,
        escalation_flag=escalated,
        resolution_flag=resolved,
        confidence=confidence,
        customer_id=req.customer_id,
        call_id=req.call_id,
        emotion_joy=emotions["joy"],
        emotion_sadness=emotions["sadness"],
        emotion_fear=emotions["fear"],
        word_count=text_features["word_count"],
        num_negative_words=text_features["num_negative_words"],
        num_positive_words=text_features["num_positive_words"],
    )

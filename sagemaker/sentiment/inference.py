import sys
print("[FORCE LOG] inference script imported")
sys.stdout.flush()

import logging
import torch
import os
import re
import json
import traceback
import subprocess
import sys
import csv

from typing import Any, Dict, Tuple, Literal
import torch.nn.functional as F
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification
# from happytransformer import HappyTextClassification 

logger = logging.getLogger(name=__name__)
logger.setLevel(level=logging.INFO)

DEVICE = torch.device(device="cuda" if torch.cuda.is_available() else "cpu")

tokenizer = None
model = None


# Emotion / Frustration Helpers
FRUSTRATION_WORDS = [
    # direct frustration
    "frustrated", "frustrating", "fed up", "annoyed", "upset", "angry",
    "mad", "irritated", "ridiculous", "unacceptable", "insane", "absurd",


    # service issues
    "slow", "slowing down", "cutting out", "dropping", "intermittent",
    "not working", "never works", "always failing", "constant issues",
    "persistent issues", "ongoing issues", "keeps happening",
    "same problem", "nothing helps", "nothing works",


    # billing frustration
    "high bill", "massive bill", "wrong bill", "unexpected charges",
    "overage charges", "late fee", "charged extra", "bill is wrong",
    "bill is too high", "can't afford", "feels like a lot",


    # escalation-level frustration
    "really fed up", "close to switching", "thinking of switching",
    "might cancel", "i'm done", "tired of this", "called multiple times",
    "keeps happening", "nobody told me", "nobody informed me",
    "shouldn't have to", "don't have time for this", "wasn't handled well",


    # emotional intensity
    "nightmare", "hassle", "mess", "terrible", "awful", "stressful",
    "confusing", "overwhelmed", "exhausted", "sick of this", "broken"


    # reliability complaints
    "completely unreliable", "keeps cutting out", "nowhere near",
    "video calls drop", "downloads fail", "signal degradation",
    "keeps going out", "angry", "upset", "frustrated", "ridiculous", "unacceptable",
    "this is crazy", "i'm tired of", "why do i have to", "absurd", "problem"
]



ANGRY_WORDS = [
    "rage", "fury", "irritation", "annoyance", "resentment", "outrage", "wrath",
    "frustration", "displeasure", "indignation", "hostility", "aggravation", "exasperation",
    "mad", "furious", "irritated", "annoyed", "upset", "enraged", "livid", "outraged",
    "frustrated", "aggravated", "hostile", "irate", "incensed", "cross", "heated", "angry",
    "infuriated", "resentful", "bitter", "fed up", "pissed", "fuming", "displeased",
    "boiling", "seething", "exasperated",
]


EMPATHY_PHRASES = [
    "i understand", "i completely understand", "i hear your frustration", "i hear you",
    "i hear your concern", "i understand your frustration", "i understand how disruptive",
    "i know how frustrating", "i see why you're upset", "i can see why", "i understand why",

    "i apologize", "i sincerely apologize", "i'm sorry", "i truly apologize", "i apologize for the inconvenience",
    "i apologize if", "i see a high number", "i can see your service history", "i understand this has been going on",
    "i know you've called", "i see this has been a recurring issue", "i can definitely help",
    "i can certainly look into", "i'll make sure", "i'll take care of that", "i want to help resolve this",

    "let me check", "let me take a look", "let me see what i can do", "let me review your account",
    "thank you for your patience", "thank you for checking", "i appreciate you explaining", "i appreciate your time",

    "i understand this feels like a lot", "i know this unexpected increase is frustrating", "i understand you're having a tough time",

    "i know how important reliable service is", "i completely understand how that affects your work",
]



SADNESS_WORDS = [
    "sad", "unhappy", "depressed", "miserable", "heartbroken", "down",
    "disappointed", "discouraged", "hopeless", "gloomy", "melancholy",
    "sorrowful", "devastated", "let down", "blue", "downcast", "forlorn",
    "dejected", "woeful", "dismayed"
]

FEAR_WORDS = [
    "afraid", "scared", "terrified", "anxious", "worried", "concerned",
    "panicked", "fearful", "nervous", "uneasy", "alarmed", "shaken",
    "distressed", "intimidated", "threatened"
]


DISGUST_WORDS = [
    "disgusted", "gross", "nasty", "repulsive", "revolting", "sickening",
    "horrible", "awful", "terrible", "vile", "filthy", "offensive",
    "abhorrent", "detestable", "loathsome"
]


BILLING_NEGATIVE_WORDS = [
    "overcharged", "wrong bill", "high bill", "unexpected charges",
    "late fee", "charged extra", "billing issue", "credit", "refund",
    "fee", "expensive", "can't afford", "too much", "unfair charge"
]

SERVICE_NEGATIVE_WORDS = [
    "bad service", "poor service", "terrible service", "unreliable",
    "slow", "down", "outage", "no signal", "disconnect", "dropped call",
    "failure", "broken", "bug", "glitch", "problem", "issue", "faulty"
]

TOXIC_WORDS = [
    "stupid", "idiot", "moron", "useless", "worthless", "garbage",
    "trash", "hate", "shut up", "pathetic", "incompetent", "terrible",
    "awful", "worst", "disgrace", "joke", "scam", "fraud"
]

ESCALATION_WORDS = [
    "cancel", "switch providers", "i'm done", "i'm leaving",
    "close my account", "terminate", "refund me now", "this is unacceptable",
    "let me speak to a supervisor", "i want a manager", "escalate this",
    "i'll report this", "legal action", "complaint", "lawsuit"
]

NEGATIVE_WORDS = (
    ANGRY_WORDS +
    SADNESS_WORDS +
    FEAR_WORDS +
    DISGUST_WORDS +
    FRUSTRATION_WORDS +
    BILLING_NEGATIVE_WORDS +
    SERVICE_NEGATIVE_WORDS +
    TOXIC_WORDS +
    ESCALATION_WORDS
)

POSITIVE_WORDS = [
    "resolved", "fixed", "corrected", "adjusted", "updated",
    "credited", "refunded", "waived", "removed", "taken care of",
    "no longer an issue", "issue closed", "all set", "sorted out",
    "clear now", "explained clearly", "makes sense now",
    "billing corrected", "charges corrected", "charges removed",
    "fee waived", "balance updated", "account updated",
    "problem resolved", "everything looks good",
    "thank you for fixing this", "appreciate the clarification",
    "billing is accurate now", "that helps a lot",
    "this clears things up", "glad this is resolved",
    "happy with the outcome", "satisfied with the resolution",

    "helpful", "supportive", "professional", "friendly", "kind",
    "patient", "polite", "courteous", "understanding",
    "knowledgeable", "informative", "clear", "responsive",
    "quick", "efficient", "effective", "reliable",
    "great service", "excellent service", "amazing help",
    "fantastic support", "appreciate your help",
    "thank you", "thanks so much", "very helpful",
    "you explained it well", "you made it easy",
    "you solved my issue", "you were very patient",
    "you were very clear", "you handled this well",
    "you took care of everything", "you made this simple",
    "great job", "awesome support", "wonderful assistance",
    "really appreciate it", "that was fast", "that was easy",

    "great", "good", "excellent", "amazing", "wonderful", "fantastic",
    "positive", "satisfied", "happy", "pleased", "delighted", "awesome",
    "love", "loved", "loving", "like", "liked",
    "appreciate", "appreciated", "appreciation", "thankful", "grateful",
    "smooth", "easy", "working", "perfect",
    "outstanding", "brilliant", "superb", "impressive", "nice",
    "trustworthy", "much better", "improved", "improvement",
    "helped", "helping", "fantastic service"
]

def sanitize_transcript(text) -> str | Literal['']:
    # Remove everything before the first '---'
    if "---" in text:
        text = text.split("---", 1)[1]
    # Remove **bold markdown**
    text = re.sub(pattern=r"\*\*(.*?)\*\*", repl="", string=text)
    # Remove (parentheses content)
    text = re.sub(pattern=r"\([^)]*\)", repl="", string=text)
    # Remove [bracket content]
    text = re.sub(pattern=r"\[[^\] ]*\]", repl="", string=text)
    # Normalize whitespace
    text = re.sub(pattern=r"\s+", repl=" ", string=text).strip()

    return text

def empathy_score(text: str) -> int:
    text = text.lower()
    return sum(text.count(p.lower()) for p in EMPATHY_PHRASES)


def emotion_frustration(text: str) -> int:
    text = text.lower()
    return sum(text.count(w) for w in FRUSTRATION_WORDS)


def emotion_anger(text: str) -> int:
    text = text.lower()
    return sum(text.count(w) for w in ANGRY_WORDS)

# Escalation / Resolution Flags
def escalation_flag(text: str) -> bool:
    text = text.lower()
    return any(
        phrase in text
        for phrase in [
            "supervisor", "manager", "escalation", "transfer me",
            "speak to a manager", "supervisor", "escalate", "cancel my",
            "cancellation", "close my account", "switch provider", "lawsuit",
            "attorney", "legal action", "BBB", "better business bureau",
            "complaint", "unacceptable", "ridiculous", "worst service",
        ]
    )

def resolution_flag(text: str) -> bool:  
    text = text.lower()
    return any(
        phrase in text
        for phrase in [
            "resolved", "fixed", "taken care of", "issue closed",
            "that helps", "sounds good", "i appreciate",
            "fixed", "taken care of", "great", "perfect", "that works", 
            "satisfied", "happy with" 
        ]
    )


# Sentiment Shift Helpers
TURN_SPLIT_RE = re.compile(pattern=r"(Agent:|Customer:)")

def split_turns(text: str) -> list[Any] | list[str | Any]:
    if not text:
        return []
    text = re.sub(pattern=r"\s+", repl=" ", string=text).strip()
    if "Agent" in text or "Customer" in text:
        parts = TURN_SPLIT_RE.split(string=text)
        merged = []
        for i in range(1, len(parts), 2):
            speaker = parts[i].strip()
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if content:
                merged.append(f"{speaker} {content}")
        return merged
    return re.split(pattern=r"(?<=[.!?])\s+", string=text)


def predict_sentiment_batch(texts: list[str], model, tokenizer) -> np.ndarray[tuple[int, int], np.dtype[np.floating[Any]]] | np.ndarray[Tuple[Any, ...], np.dtype[Any]]:
    if not texts:
        return np.empty((0, model.num_labels), dtype=np.float32)

    encoded = tokenizer(
        texts,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512
    ).to(DEVICE)

    with torch.no_grad():
        logits = model(**encoded).logits
        probs = F.softmax(input=logits, dim=-1).cpu().numpy()

    return probs


def sentiment_trajectory(turns, model, tokenizer) -> list[Any]:
    probs_batch = predict_sentiment_batch(texts=turns, model=model, tokenizer=tokenizer)
    preds = np.argmax(probs_batch, axis=1)

    trajectory = []
    for idx, (t, probs, pred) in enumerate(iterable=zip(turns, probs_batch, preds)):
        trajectory.append({
            "turn_index": idx,
            "text": t,
            "sentiment_probs": probs.tolist(),
            "sentiment_label": int(pred),
            "confidence": float(probs[pred])
        })
    return trajectory


def compute_sentiment_shift(trajectory) -> float:
    if len(trajectory) < 3:
        return 0.0

    probs = np.array(object=[t["sentiment_probs"] for t in trajectory])
    n = probs.shape[0]
    third = n // 3
    if third == 0:
        return 0.0

    start = probs[:third].mean(axis=0)
    end = probs[2*third:].mean(axis=0)
    shift_vector = end - start
    return float(np.linalg.norm(shift_vector))

# QA Score Helper
def compute_text_features(text: str) -> dict[str, Any]:
    words = text.split()
    word_count = len(text.split())
    avg_word_length = sum(len(w) for w in words) / max(word_count, 1)
    num_exclamation = text.count("!")
    lower = text.lower()


    num_negative = sum(1 for w in NEGATIVE_WORDS if w in lower)
    num_positive = sum(1 for w in POSITIVE_WORDS if w in lower)


    return {
        "word_count": word_count,
        "avg_word_length": round(number=avg_word_length, ndigits=2),
        "num_exclamation_marks": num_exclamation,
        "num_negative_words": num_negative,
        "num_positive_words": num_positive,
    }


def compute_emotion_scores(text: str, text_features: dict) -> dict[str, float]:
    lower = text.lower()
    word_count = max(text_features["word_count"], 1)
    neg_ratio = text_features["num_negative_words"] / max(word_count / 50, 1)
    pos_ratio = text_features["num_positive_words"] / max(word_count / 50, 1)
    excl_ratio = text_features["num_exclamation_marks"] / max(word_count / 100, 1)

    frustration_hits = sum(1 for p in FRUSTRATION_WORDS if p in lower)
    frustration = min(1.0, round(number=neg_ratio * 0.4 + excl_ratio * 0.2 +
                                  frustration_hits * 0.15, ndigits=2))

    # Anger: driven by strong negative words + capitalization + exclamation
    anger_hits = sum(1 for p in ANGRY_WORDS if p in lower)
    anger = min(1.0, round(number=anger_hits * 0.25 + excl_ratio * 0.15, ndigits=2))

    # Joy: driven by positive words
    joy = min(1.0, round(number=pos_ratio * 0.5, ndigits=2))


    return {
        "anger": anger,
        "frustration": frustration,
        "joy": joy,
    }


def compute_qa_score(
    emotions: dict,
    text_features: dict,
    escalated: bool,
    resolved: bool,
    sentiment_label: str,
    confidence: float ,
) -> float:
    score = 5.0  # baseline

    # Sentiment contribution
    if sentiment_label.lower() == "positive":
        score += 2.0
    elif sentiment_label.lower() == "negative":
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

    return round(number=max(0.0, min(10.0, score)), ndigits=1)

# MODEL LOADING
def model_fn(model_dir: str) -> Any:
    
    global tokenizer, model
    logger.info(msg=f"[DEBUG] model_dir = {model_dir}")
    logger.info(msg=f"[DEBUG] Files in model_dir: {os.listdir(path=model_dir)}")
    
    
    try:
        logger.info(msg=f"[model_fn] Loading tokenizer from: {model_dir}")
        tokenizer = AutoTokenizer.from_pretrained(pretrained_model_name_or_path="ProsusAI/finbert")

        logger.info(msg=f"[model_fn] Loading model from: {model_dir}")
        model = AutoModelForSequenceClassification.from_pretrained(pretrained_model_name_or_path="ProsusAI/finbert")
        model.to(DEVICE)
        model.eval()
    

        logger.info(msg=f"[DEBUG] model.config.num_labels = {model.config.num_labels}")
        logger.info(msg=f"[DEBUG] model.config.id2label = {model.config.id2label}")
        logger.info(msg=f"[DEBUG] classifier head = {model.classifier}")


        logger.info(msg="[model_fn] Model + tokenizer loaded successfully.")
        return model

    except Exception as e:
        logger.error(msg=f"[model_fn] FAILED to load model: {e}")
        logger.error(msg=traceback.format_exc())
        raise RuntimeError(f"Model loading failed: {e}")



# INPUT PARSING
def input_fn(request_body: str, content_type: str) -> Dict[str, Any]:
    logger.info(msg=f"[input_fn] RequestBody={request_body}")
    try:
        logger.info(msg=f"[input_fn] Received content_type={content_type}")

        if content_type == "application/json":
            data = json.loads(s=request_body)

            # Single record
            if isinstance(data, dict):
                texts = [data.get("call_transcript", "")]
                meta = [data]
                logger.info(msg=f"[input_fn] Texts={texts}")
            # Batch of records
            elif isinstance(data, list):
                texts = [d.get("call_transcript", "") for d in data]
                meta = data
                logger.info(msg=f"[input_fn] TextsBatch={texts}")
            else:
                raise ValueError("JSON payload must be dict or list.")

            logger.info(msg=f"[input_fn] Parsed {len(texts)} text entries.")
            return {"texts": texts, "meta": meta}

        # Allow raw text as fallback
        elif content_type == "text/plain":
            logger.warning(msg="[input_fn] Received raw text input.")
            return {"texts": [request_body], "meta": [{"raw_text": request_body}]}

        else:
            raise ValueError(f"Unsupported content type: {content_type}")

    except Exception as e:
        logger.error(msg=f"[input_fn] FAILED to parse input: {e}")
        logger.error(msg=traceback.format_exc())
        raise RuntimeError(f"Input parsing failed: {e}")


# PREDICTION
def predict_fn(inputs: Dict[str, Any], model) -> Dict[str, Any]:
    logger.info(msg=f"[DEBUG] Model: {model}")

    
    logger.info(msg=f"[DEBUG] P model.config.num_labels = {model.config.num_labels}")
    logger.info(msg=f"[DEBUG] P model.config.id2label = {model.config.id2label}")
    logger.info(msg=f"[DEBUG] P classifier head = {model.classifier}")
    try:
        texts = inputs["texts"]
        meta = inputs["meta"]
        
        logger.info(msg=f"[DEBUG] Predict Text: {texts}")
        logger.info(msg=f"[DEBUG] Predict Meta: {meta}")

        results = []
        for text, m in zip(texts, meta): 
            # MODEL SENTIMENT
            enc = tokenizer(
                text,
                padding="max_length",
                truncation=True,
                max_length=512,
                return_tensors="pt"
            ).to(DEVICE)
            
    
            with torch.no_grad():
                logits = model(**enc).logits
                print("[DEBUG] Raw logits:", logits.cpu().numpy())
                probs = torch.softmax(input=logits, dim=-1)[0].cpu().numpy()
                
            logger.info(msg=f"[DEBUG] Raw logits: {logits.cpu().numpy().tolist()}")
            logger.info(msg=f"[DEBUG] Probs1: {probs}")

     
            sentiment_map = {
              "0": "positive",
              "1": "negative",
              "2": "neutral"
            }

            pred_idx = int(np.argmax(probs))
            confidence = float(probs[pred_idx])
            sentiment_label = sentiment_map[str(pred_idx)]
            
            logger.info(f"[DEBUG] Pred_Idx: {pred_idx}")
            logger.info(f"[DEBUG] Probs2: {probs}")
            
            text = sanitize_transcript(text)
            
            duration = m.get("call_duration_seconds")
            cd = (
               "short" if duration and duration < 180 else
               "medium" if duration and duration < 600 else
               "long" if duration else None
            )

            # FEATURE EXTRACTION
            fr = emotion_frustration(text=text)
            ang = emotion_anger(text=text)
            esc = escalation_flag(text=text)
            res = resolution_flag(text=text)

            turns = split_turns(text=text)
            trajectory = sentiment_trajectory(turns=turns, model=model, tokenizer=tokenizer)
            shift = compute_sentiment_shift(trajectory=trajectory)
            
            text_features = compute_text_features(text=text)
            
            emo = compute_emotion_scores(text=text, text_features=text_features)

            qa = compute_qa_score(
                sentiment_label=sentiment_label, 
                confidence=confidence, 
                emotions=emo, 
                text_features=text_features, 
                escalated=esc, resolved=res
            )
            # happy_tc = HappyTextClassification("BERT", "ProsusAI/finbert", num_labels=3)
            # FINAL RESULT
            results.append({
                "call_id": m.get("call_id"),
                "customer_id": m.get("customer_id"),
                "category": m.get("primary_scenario"),

                "sentiment": pred_idx,
                "sentiment_label": sentiment_label,
                "confidence": confidence,
                "call_duration_indicator": cd,

                "qa_score": qa,
                "emotion_frustration": fr,
                "emotion_anger": ang,
                "sentiment_shift": shift,
                "escalation_flag": esc,
                "resolution_flag": res,
            })
        return {"results": results}

    except Exception as e:
        logger.error(msg=f"[predict_fn] FAILED: {e}")
        logger.error(msg=traceback.format_exc())
        raise RuntimeError(f"Inference failed: {e}")



# OUTPUT SERIALIZATION
def output_fn(prediction: Dict[str, Any], accept: str) -> Tuple[str, Literal["application/json"]]:
    try:
        if accept != "application/json":
            raise ValueError(f"Unsupported accept type: {accept}")
        
            
        logger.info(msg="[output_fn] Serializing output.")
        logger.info(msg=f"[output_fn] Prediction: {prediction}.")
        return json.dumps(obj=prediction["results"]), "application/json"

    except Exception as e:
        logger.error(msg=f"[output_fn] FAILED to serialize output: {e}")
        logger.error(msg=traceback.format_exc())
        raise RuntimeError(f"Output serialization failed: {e}")


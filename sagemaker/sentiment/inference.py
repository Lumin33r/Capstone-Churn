import logging
import torch
import os
import re
import json
import traceback
import subprocess
import sys

from typing import Any, Dict, Tuple, Literal
import torch.nn.functional as F
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger(name=__name__)
logger.setLevel(level=logging.INFO)

DEVICE = torch.device(device="cuda" if torch.cuda.is_available() else "cpu")

tokenizer = None
model = None
sentiment_schema = None

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
    "confusing", "overwhelmed", "exhausted", "sick of this",


    # reliability complaints
    "completely unreliable", "keeps cutting out", "nowhere near",
    "video calls drop", "downloads fail", "signal degradation",
    "keeps going out", "angry", "upset", "frustrated", "ridiculous", "unacceptable",
    "this is crazy", "i'm tired of", "why do i have to"
]

ANGRY_WORDS = [
    "rage", "fury", "irritation", "annoyance", "resentment", "outrage", "wrath",
    "frustration", "displeasure", "indignation", "hostility", "aggravation", "exasperation",
    "mad", "furious", "irritated", "annoyed", "upset", "enraged", "livid", "outraged",
    "frustrated", "aggravated", "hostile", "irate", "incensed", "cross", "heated", "angry",
    "furious", "mad"
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


def empathy_score(text) -> int:
    text = text.lower()
    return sum(text.count(p.lower()) for p in EMPATHY_PHRASES)

def emotion_frustration(text: str) -> int:
    text = text.lower()
    return sum(text.count(w) for w in FRUSTRATION_WORDS)

def emotion_anger(text: str) -> int:
    text = text.lower()
    return sum(text.count(w) for w in ANGRY_WORDS)

ANGER_WORDS = [
    "angry", "furious", "mad", "irritated", "annoyed", "outraged", "livid",
    "enraged", "hostile", "aggravated", "infuriated", "resentful", "bitter",
    "fed up", "pissed", "upset", "fuming", "displeased", "irate", "cross",
    "heated", "frustrated", "exasperated", "boiling", "seething"
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

FRUSTRATION_WORDS = [
    "frustrated", "frustrating", "fed up", "tired of this", "sick of this",
    "ridiculous", "unacceptable", "absurd", "insane", "hassle", "nightmare",
    "mess", "problem", "issue", "keeps happening", "nothing works",
    "never works", "always failing", "constant issues", "ongoing issues",
    "same problem", "not working", "broken", "slow", "slowing down",
    "cutting out", "dropping", "intermittent"
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
    ANGER_WORDS +
    SADNESS_WORDS +
    FEAR_WORDS +
    DISGUST_WORDS +
    FRUSTRATION_WORDS +
    BILLING_NEGATIVE_WORDS +
    SERVICE_NEGATIVE_WORDS +
    TOXIC_WORDS +
    ESCALATION_WORDS
)


def toxicity_score(text) -> float | Literal[0]:
    if not isinstance(text, str):
        return 0
    count = sum(1 for w in NEGATIVE_WORDS if w in text.lower())
    # Toxicity proxy = negative sentiment intensity
    return count


def agent_turns(text) -> int:
    if not isinstance(text, str):
        return 0
    prefix = "Agent:" if "Agent:" in text else "Agent"
    return text.count(prefix)


# Escalation / Resolution Flags
def escalation_flag(text: str) -> bool:
    text = text.lower()
    return any(
        phrase in text
        for phrase in [
            "let me speak to a supervisor",
            "i want a manager",
            "this needs escalation",
            "transfer me",
        ]
    )

def resolution_flag(text: str) -> bool:
    
    text = text.lower()
    return any(
        phrase in text
        for phrase in ["resolved", "fixed", "taken care of", "issue closed"]
    )



# Sentiment Shift Helpers
TURN_SPLIT_RE = re.compile(pattern=r"(Agent:|Customer:)")

def split_turns(transcript: str) -> list[Any] | list[str | Any]:
    if not transcript:
        return []
    text = re.sub(pattern=r"\s+", repl=" ", string=transcript).strip()
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


def predict_sentiment_batch(texts: list[str], model, tokenizer, device) -> np.ndarray[tuple[int, int], np.dtype[np.floating[Any]]] | np.ndarray[Tuple[Any, ...], np.dtype[Any]]:
    if not texts:
        return np.empty((0, model.num_labels), dtype=np.float32)

    encoded = tokenizer(
        texts,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=256
    ).to(device)

    with torch.no_grad():
        logits = model(**encoded).logits
        probs = F.softmax(input=logits, dim=-1).cpu().numpy()

    return probs


def sentiment_trajectory(turns, model, tokenizer, device) -> list[Any]:
    probs_batch = predict_sentiment_batch(texts=turns, model=model, tokenizer=tokenizer, device=device)
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
def qa_score(text: str) -> float:
    empathy = empathy_score(text=text)
    frustration = emotion_frustration(text=text)
    toxicity = toxicity_score(text=text)
    agent_turn= agent_turns(text=text)
    
    def compute_escalation_probability(text: str, frustration: int, toxicity: float) -> float:
        score = 0
        t = text.lower()

        if "cancel" in t or "switch providers" in t:
            score += 4
        if frustration >= 3:
            score += 3
        if toxicity > 0.3:
            score += 2
        if "billing" in t:
            score += 1
        if "outage" in t:
            score += 1

        return min(1.0, score / 10)
    
    escalation = compute_escalation_probability(text=text, frustration=frustration, toxicity=toxicity)


    # Weighted QA score (0–100)
    score = (
        empathy * 4
        - frustration * 3
        - toxicity * 20
        - escalation * 30
        + (agent_turn > 0) * 10
    )

    score = max(0, min(100, score))

    return score



# MODEL LOADING
def model_fn(model_dir: str) -> Any:
    # subprocess.check_call(args=["pip", "install", "-r", "/opt/ml/model/requirements.txt"])
    
    global tokenizer, model, sentiment_schema
    logger.info(msg=f"[DEBUG] model_dir = {model_dir}")
    logger.info(msg=f"[DEBUG] Files in model_dir: {os.listdir(path=model_dir)}")
    
    
    try:
        logger.info(msg=f"[model_fn] Loading tokenizer from: {model_dir}")
        tokenizer = AutoTokenizer.from_pretrained(pretrained_model_name_or_path=model_dir)

        logger.info(msg=f"[model_fn] Loading model from: {model_dir}")
        model = AutoModelForSequenceClassification.from_pretrained(pretrained_model_name_or_path=model_dir)
        model.to(DEVICE)
        model.eval()
    

        # Load schema
        schema_path = os.path.join(model_dir, "sentiment_schema.json")
        with open(file=schema_path, mode="r") as f:
            sentiment_schema = json.load(fp=f)
            
        logger.info(f"[DEBUG] model.config.num_labels = {model.config.num_labels}")
        logger.info(f"[DEBUG] model.config.id2label = {model.config.id2label}")
        logger.info(f"[DEBUG] classifier head = {model.classifier}")


        logger.info(msg="[model_fn] Model + tokenizer loaded successfully.")
        return model

    except Exception as e:
        logger.error(msg=f"[model_fn] FAILED to load model: {e}")
        logger.error(msg=traceback.format_exc())
        raise RuntimeError(f"Model loading failed: {e}")



# INPUT PARSING
def input_fn(request_body: str, content_type: str) -> Dict[str, Any]:
    try:
        logger.info(msg=f"[input_fn] Received content_type={content_type}")

        if content_type == "application/json":
            data = json.loads(s=request_body)

            # Single record
            if isinstance(data, dict):
                texts = [data.get("call_transcript", "")]
                meta = [data]

            # Batch of records
            elif isinstance(data, list):
                texts = [d.get("call_transcript", "") for d in data]
                meta = data

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
    try:
        texts = inputs["texts"]
        meta = inputs["meta"]

        results = []
        for text, m in zip(texts, meta): 
            # MODEL SENTIMENT
            enc = tokenizer(
                text,
                padding="max_length",
                truncation=True,
                max_length=256,
                return_tensors="pt"
            ).to(DEVICE)
            
    
            with torch.no_grad():
                logits = model(**enc).logits
                print("[DEBUG] Raw logits:", logits.cpu().numpy())
                probs = torch.softmax(input=logits, dim=-1)[0].cpu().numpy()
                
            logger.info(f"[DEBUG] Raw logits: {logits.cpu().numpy().tolist()}")

            # inputs = tokenizer(
                #  text,
                #  return_tensors="pt",
                #  truncation=True,
                #  padding="max_length",
                #  max_length=256
            #  )
            #  
            # with torch.no_grad():
                #  outputs = model(**{k: v for k, v in inputs.items()})
                #  probs = torch.softmax(input=outputs.logits, dim=-1)[0].cpu().numpy()
                #  pred_idx = int(np.argmax(a=probs))
                #  confidence = float(probs[pred_idx])
     
            sentiment_map = {
              "0": "negative",
              "1": "neutral",
              "2": "positive",
            }

            pred_idx = int(np.argmax(probs))
            confidence = float(probs[pred_idx])
            sentiment_label = sentiment_map[str(pred_idx)]

            # FEATURE EXTRACTION
            fr = emotion_frustration(text=text)
            ang = emotion_anger(text=text)
            esc = escalation_flag(text=text)
            res = resolution_flag(text=text)

            turns = split_turns(transcript=text)
            trajectory = sentiment_trajectory(turns=turns, model=model, tokenizer=tokenizer, device=DEVICE)
            shift = compute_sentiment_shift(trajectory=trajectory)

            qa = qa_score(text=text)

            
            # FINAL RESULT
            results.append({
                "call_id": m.get("call_id"),
                "customer_id": m.get("customer_id"),
                "primary_scenario": m.get("primary_scenario"),

                "sentiment": pred_idx,
                "sentiment_label": sentiment_label,
                "confidence": confidence,

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
        return json.dumps(obj=prediction["results"]), "application/json"

    except Exception as e:
        logger.error(msg=f"[output_fn] FAILED to serialize output: {e}")
        logger.error(msg=traceback.format_exc())
        raise RuntimeError(f"Output serialization failed: {e}")


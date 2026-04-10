import json
import logging
import traceback
import torch
import os
from typing import Any, Dict, Tuple, Literal
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger(name=__name__)
logger.setLevel(level=logging.INFO)

DEVICE = torch.device(device="cuda" if torch.cuda.is_available() else "cpu")

tokenizer = None
model = None
sentiment_schema = None


# MODEL LOADING
def model_fn(model_dir: str) -> Any:
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
        logger.info(msg=f"[predict_fn] Running inference on {len(texts)} texts.")

        if tokenizer is None:
            raise RuntimeError("Tokenizer not initialized. model_fn must be called first.")

        encodings = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        ).to(DEVICE)

        with torch.no_grad():
            outputs = model(**encodings)
            logits = outputs.logits
            probs = torch.softmax(input=logits, dim=-1)

        preds = torch.argmax(input=probs, dim=-1).cpu().tolist()
        confidences = probs.max(dim=-1).values.cpu().tolist()

        logger.info(msg="[predict_fn] Inference completed successfully.")

        return {
            "preds": preds,
            "confidences": confidences,
            "meta": inputs["meta"],
        }

    except Exception as e:
        logger.error(msg=f"[predict_fn] FAILED during inference: {e}")
        logger.error(msg=traceback.format_exc())
        raise RuntimeError(f"Inference failed: {e}")



# OUTPUT SERIALIZATION
def output_fn(prediction: Dict[str, Any], accept: str) -> Tuple[str, Literal["application/json"]]:
    try:
        if accept != "application/json":
            raise ValueError(f"Unsupported accept type: {accept}")
        
        preds = prediction["preds"]
        confidences = prediction["confidences"]
        meta = prediction["meta"]
    
        results = []
        for m, p, c in zip(meta, preds, confidences):
            result = {
                "call_id": m.get("call_id"),
                "customer_id": m.get("customer_id"),
                "primary_scenario": m.get("primary_scenario"),
                "sentiment": int(p),
                "confidence": float(c),
            }

            # Attach full schema
            # if sentiment_schema is not None:
                # result.update(sentiment_schema) 
            # results.append(result)
            
        logger.info(msg="[output_fn] Serializing output.")
        return json.dumps(obj=results), "application/json"

    except Exception as e:
        logger.error(msg=f"[output_fn] FAILED to serialize output: {e}")
        logger.error(msg=traceback.format_exc())
        raise RuntimeError(f"Output serialization failed: {e}")


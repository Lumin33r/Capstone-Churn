# import json
# import os
# import torch
# from transformers import AutoTokenizer, AutoModelForSequenceClassification
# from typing import Literal, Any, Dict

# DEVICE = torch.device(device="cuda" if torch.cuda.is_available() else "cpu")

# tokenizer = None
# model = None
# sentiment_schema = None


# def model_fn(model_dir: str) -> Any:
#     global tokenizer, model, sentiment_schema

#     # Load HF model + tokenizer
#     tokenizer = AutoTokenizer.from_pretrained(model_dir)
#     model = AutoModelForSequenceClassification.from_pretrained(model_dir)
#     model.to(DEVICE)
#     model.eval()

#     # Load schema
#     schema_path = os.path.join(model_dir, "sentiment_schema.json")
#     with open(file=schema_path, mode="r") as f:
#         sentiment_schema = json.load(fp=f)

#     return model



# def input_fn(request_body, content_type: str) -> Dict[str, Any]:
#     if content_type == "application/json":
#         data = json.loads(request_body)
#         # single record
#         if isinstance(data, dict):
#             texts = [data["call_transcript"]]
#             meta = [data]
#         # batch
#         elif isinstance(data, list):
#             texts = [d["call_transcript"] for d in data]
#             meta = data
#         else:
#             raise ValueError("Invalid JSON payload format.")
#         return {"texts": texts, "meta": meta}
#     else:
#         raise ValueError(f"Unsupported content type: {content_type}")


# def predict_fn(inputs, model) -> Dict[str, Any]:
#     texts = inputs["texts"]

#     encodings = tokenizer( 
#         texts,
#         padding=True,
#         truncation=True,
#         max_length=256,
#         return_tensors="pt",
#     ).to(DEVICE) 

#     with torch.no_grad():
#         outputs = model(**encodings)
#         logits = outputs.logits
#         probs = torch.softmax(logits, dim=-1)

#     preds = torch.argmax(probs, dim=-1).cpu().tolist()
#     confidences = probs.max(dim=-1).values.cpu().tolist()

#     return {
#         "preds": preds,
#         "confidences": confidences,
#         "meta": inputs["meta"],
#     }



# def output_fn(prediction, accept) -> tuple[str, Literal['application/json']]:
#     if accept != "application/json":
#         raise ValueError(f"Unsupported accept type: {accept}")

#     preds = prediction["preds"]
#     confidences = prediction["confidences"]
#     meta = prediction["meta"]

#     results = []
#     for m, p, c in zip(meta, preds, confidences):
#         result = {
#             "call_id": m.get("call_id"),
#             "customer_id": m.get("customer_id"),
#             "primary_scenario": m.get("primary_scenario"),
#             "sentiment": int(p),
#             "confidence": float(c),
#         }

#         # Attach full schema
#         result["schema"] = sentiment_schema

#         results.append(result)

#     return json.dumps(obj=results), "application/json"


import json
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = None
model = None

def model_fn(model_dir):
    global tokenizer, model
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.to(DEVICE)
    model.eval()
    return model

def input_fn(request_body, content_type):
    data = json.loads(request_body)
    if isinstance(data, dict):
        texts = [data["call_transcript"]]
        meta = [data]
    elif isinstance(data, list):
        texts = [d["call_transcript"] for d in data]
        meta = data
    else:
        raise ValueError("Invalid JSON payload format.")
    return {"texts": texts, "meta": meta}

def predict_fn(inputs, model):
    encodings = tokenizer(
        inputs["texts"],
        padding=True,
        truncation=True,
        max_length=256,
        return_tensors="pt",
    ).to(DEVICE)

    with torch.no_grad():
        outputs = model(**encodings)
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)

    preds = torch.argmax(probs, dim=-1).cpu().tolist()
    confidences = probs.max(dim=-1).values.cpu().tolist()

    return {
        "preds": preds,
        "confidences": confidences,
        "meta": inputs["meta"],
    }

def output_fn(prediction, accept):
    if accept != "application/json":
        raise ValueError(f"Unsupported accept type: {accept}")
    return json.dumps(prediction), "application/json"

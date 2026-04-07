# %%
%pip install boto3
# %pip install s3fs
# %pip install sagemaker
# %pip install "transformers==4.26.0" "accelerate==0.17.1"
# %pip install datasets


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import torch
import os
import boto3
import json
from typing import Any, NoReturn, Literal
from transformers import (AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments)
from datasets import Dataset, DatasetDict


import warnings
warnings.filterwarnings(action='ignore')

# %% [markdown]
# ### 1. Load & Explore Dataset

# %%
import s3fs
fs = s3fs.S3FileSystem()
df = pd.read_csv(filepath_or_buffer="s3://retention-engine-bucket/data/call_transcripts.csv", storage_options={"anon": False}, sep=",", engine="python", encoding="utf-8", encoding_errors="strict")
df

# %%
# Explore data
print(f'Customer data: {df.shape[0]} rows, {df.shape[1]} columns')

# %%
print('--- Customer Data ---')
df.head(n=10)

# %%
print('--- Customer Data ---')
df.sample(n=10, random_state=3)

# %%
print('--- Customer Data Info ---')
df.info()

# %%
print('--- Customer Data Unique Types Count---')
df.select_dtypes(include="object").nunique()

# %%
print('---- Customer Data Unique Values')
unique_value = df.copy().drop(labels=['call_id', 'customer_id', 'call_date', 'agent_id', 'call_transcript', 'call_successful'], axis=1)
unique_value

# %%
# Check for null values
print('--- Customer Data Null ---')
print(df.isnull().sum())
print()
print('--- Customer Data Sum Non Null ---')
print(df.notnull().value_counts().sum())

# %%
print('--- Customer Data Statistics---')
df.describe()

# %%
numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()

df["call_successful"] = df["call_successful"].astype(dtype=int)

corr = df[numeric_cols].corr()
corr

# %%

plt.figure(figsize=(8, 6))
sns.heatmap(data=corr, annot=True, cmap="coolwarm", fmt=".2f")
plt.title(label="Correlation Matrix")
plt.show()


# %%
# Save the feature order for the FastAPI wrapper
with open(file='feature_columns.json', mode='w') as f:
    json.dump(obj=df.columns.tolist(), fp=f)
print('Feature columns saved to feature_columns.json')

# %% [markdown]
# ### 2. Feature Engineering & Preprocessing

# %%
import re

def sanitize_transcript(text) -> str | None | Literal['']:
    if pd.isna(text):
        return ""
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

df["clean_transcript"] = df["call_transcript"].apply(func=sanitize_transcript)
df["clean_transcript"].iloc[0][:100]

# %%
def engineer_features(df) -> Any:
    df = df.copy()
    df["word_count"] = df["call_transcript"].str.split().str.len()
    df["avg_word_length"] = (
        df["call_transcript"]
        .str.split()
        .apply(lambda words: sum(len(w) for w in words) / len(words) if words else 0)
    )
    df["num_exclamation_marks"] = df["call_transcript"].str.count("!")
    return df

df = engineer_features(df=df)
df.head()


# %%

# Drop null/na value -- if exists
df = df.dropna(subset=["call_transcript", "overall_rating"])
df.head()

# %%
from sklearn.preprocessing import LabelEncoder

class CallRecordLabelEncoders:
    def __init__(self) -> None:
        self.encoders = {
            "call_id": LabelEncoder(),
            "customer_id": LabelEncoder(),
            "call_date": LabelEncoder(),
            "call_time": LabelEncoder(),
            "agent_id": LabelEncoder(),
            "agent_name": LabelEncoder(),
            "primary_scenario": LabelEncoder(),
            "call_transcript": LabelEncoder()
        }

    def fit(self, df) -> Any:
        # Columns are required based on self.encoders schema
        # Conditional confirms if column is present
        for col, encoder in list(self.encoders.items()):
            if col not in df.columns:
                del self.encoders[col]
                continue
            encoder.fit(y=df[col].astype(str))
        return self


    def transform(self, df) -> Any:
        df_encoded = df.copy()
        for col, encoder in self.encoders.items():
            df_encoded[col] = encoder.transform(y=df[col].astype(str))
        return df_encoded

    def fit_transform(self, df) -> Any:
        self.fit(df=df)
        return self.transform(df=df)
    

    def inverse_transform(self, df) -> Any:
        df_decoded = df.copy()
        for col, encoder in self.encoders.items():
            df_decoded[col] = encoder.inverse_transform(y=df[col])
        return df_decoded
    
# Instantiate
enc = CallRecordLabelEncoders()
# Fit and Transform Data
label_encoders = enc.fit_transform(df=df)
label_encoders.head(3)


# %% [markdown]
# ### 3. Train/Test Split

# %%
from sklearn.model_selection import train_test_split

# Normalize before splitting
df["overall_rating"] -= df["overall_rating"].min()

train_df, test_df = train_test_split(
    df, stratify=df["overall_rating"], test_size=0.2, random_state=42
)

dataset = DatasetDict({
    "train": Dataset.from_pandas(df=train_df.reset_index(drop=True)),
    "test": Dataset.from_pandas(df=test_df.reset_index(drop=True)),
})


# %% [markdown]
# ### 4. Train Model

# %%
###### Transformer Based Approach to Training Model ######

# Tokenize the dataset
model_name = "distilbert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(pretrained_model_name_or_path=model_name)

def tokenize_batch(batch) -> Any:
    return tokenizer(
        batch["call_transcript"],
        padding="max_length",
        truncation=True,
        max_length=256
    )

tokenized = dataset.map(function=tokenize_batch, batched=True)
tokenized = tokenized.remove_columns(
    column_names=[c for c in tokenized["train"].column_names if c not in ["input_ids", "attention_mask", "overall_rating"]]
)
tokenized = tokenized.rename_column(original_column_name="overall_rating", new_column_name="labels")
tokenized.set_format(type="torch")

# %%
# Load the model
num_labels = int(df["overall_rating"].nunique())

model = AutoModelForSequenceClassification.from_pretrained(
    pretrained_model_name_or_path=model_name,
    num_labels=num_labels
)

# %%
# Define Training arguments
training_args = TrainingArguments(
    output_dir="./sentiment_model",
    logging_dir='./sentiment_logs',
    evaluation_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=None,
    save_safetensors=False,
    save_only_model=True,
    learning_rate=2e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    num_train_epochs=2,
    weight_decay=0.01,
    logging_steps=50,
    load_best_model_at_end=True,
    warmup_steps=500,
    no_cuda=True
)


# %% [markdown]
# ### 5. Evaluate Performance

# %%

# Define compute metrics function
from sklearn.metrics import accuracy_score, f1_score, recall_score, precision_recall_fscore_support

def compute_metrics(eval_pred) -> dict[str, Any]:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(y_true=labels, y_pred=preds),
        "f1_macro": f1_score(y_true=labels, y_pred=preds, average="macro"),
        "recall": recall_score(y_true=labels, y_pred=preds, average="macro")  
    }


def compare_compute_metrics(pred) -> dict[str, Any]:
    labels = pred.label_ids
    preds = np.argmax(a=pred.predictions, axis=1)
    precision, recall, f1, _ = precision_recall_fscore_support(y_true=labels, y_pred=preds, average='weighted')
    acc = accuracy_score(y_true=labels, y_pred=preds)
    return {'accuracy': acc, 'f1': f1, 'precision': precision, 'recall': recall}


# %%
# Disable Weights & Biases (W&B)
os.environ["WANDB_DISABLED"] = "true"

# %%
# def model_init() -> Any:
    # return model

# Parameters in consideration for hyperparameter
# def hp_space(trial) -> dict[str, Any]:
    # return {
        # "learning_rate": trial.suggest_float("learning_rate", 1e-5, 5e-5),
        # "num_train_epochs": trial.suggest_int("num_train_epochs", 2, 5),
        # "per_device_train_batch_size": trial.suggest_categorical("batch_size", [8, 16, 32]),
        # "weight_decay": trial.suggest_float("weight_decay", 0.0, 0.1),
        # "warmup_steps": trial.suggest_int("warmup_steps", 0, 500),
    # }


# %%
# Initialize Model Training 
# trainer = Trainer(
    # model_init=model_init,
    # args=training_args,
    # train_dataset=tokenized["train"], # type: ignore
    # eval_dataset=tokenized["test"],   # type: ignore
    # tokenizer=tokenizer,
    # compute_metrics=compute_metrics,
# )

# %%
# %pip install optuna

# Comment out for presentation: runtime is 105min for 5 trails
# best_run = trainer.hyperparameter_search(
    # direction="maximize",
    # backend="optuna",
    # hp_space=hp_space,
    # n_trials=20
# )

# Apply parameters to trainer arguments
# for n, v in best_run.hyperparameters.items():
    # setattr(trainer.args, n, v)


# %% [markdown]
# ### 6. Invoke Model

# %%
import mlflow # type: ignore imported in previous cell
mlflow.autolog(disable=True)

# End and Start a new session
mlflow.end_run()
mlflow.start_run()
# Initialize trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized["train"],   # type: ignore
    eval_dataset=tokenized["test"],     # type: ignore
    tokenizer=tokenizer,
    compute_metrics=compute_metrics,
)

# Train the model on the larger subset
trainer.train()
trainer.evaluate()

# %%
id2label = {i: str(object=i) for i in range(num_labels)}

def predict_call(row) -> dict[str, Any]:
    text = row["call_transcript"]
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding="max_length",
        max_length=256
    )

    with torch.no_grad():
        outputs = model(**{k: v for k, v in inputs.items()})
        probs = torch.softmax(input=outputs.logits, dim=-1)[0].cpu().numpy()
        pred_idx = int(np.argmax(a=probs))
        confidence = float(probs[pred_idx])

    return {
        "call_id": row.get("call_id"),
        "customer_id": row.get("customer_id"),
        "primary_scenario": row.get("primary_scenario"),

        "qa_score": None,
        "sentiment": id2label[pred_idx],
        "category": row.get("primary_scenario"),
        "confidence": confidence,
        "frustration_level": None,
        "call_duration_indicator": None,
        "escalation_flag": None,

        "word_count": len(text.split()),
        "avg_word_length": (
            round(number=sum(len(w) for w in text.split()) / max(1, len(text.split())), ndigits=3)
        ),

        "emotion_scores": {
            "anger": None,
            "sadness": None,
            "frustration": None,
        },

        "billing_dispute_flag": None,
        "outage_history_flag": None,
        "overage_amount_last_cycle": None,

        "agent_experience": None,
        "transfer_count": None,
        "resolution_flag": row.get("call_successful"),
    }


# %%
sample = df.iloc[0]
predict_call(row=sample)


# %%

import torch.nn.functional as F # type: ignore imported in previous cell
device = torch.device(device="cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

def predict_row(row) -> dict[str, Any]:
    text = row["call_transcript"]

    # --- Tokenize ---
    inputs = tokenizer(
        text,
        truncation=True,
        padding="max_length",
        max_length=256,
        return_tensors="pt"
    ).to(device)

    # --- Forward pass ---
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        probs = F.softmax(input=logits, dim=-1)

    # --- Prediction ---
    pred = torch.argmax(input=probs, dim=-1).item()
    confidence = probs[0][pred].item() # type: ignore

    # --- Basic text stats ---
    word_count = len(text.split())
    avg_word_length = sum(len(w) for w in text.split()) / max(word_count, 1)
    num_exclamation_marks = text.count("!")

    # --- Frustration heuristic ---
    frustration_keywords = [
        "angry", "upset", "frustrated", "ridiculous", "unacceptable",
        "this is crazy", "i'm tired of", "why do i have to"
    ]
    frustration_level = sum(1 for kw in frustration_keywords if kw in text.lower())

    # --- Emotion scores ---
    emotion_scores = {
        "anger": sum(1 for w in ["angry", "furious", "mad"] if w in text.lower()),
        "sadness": sum(1 for w in ["sad", "disappointed", "unhappy"] if w in text.lower()),
        "frustration": frustration_level
    }

    # --- Call duration indicator ---
    duration = row.get("call_duration_seconds")
    call_duration_indicator = (
        "short" if duration and duration < 180 else
        "medium" if duration and duration < 600 else
        "long" if duration else None
    )

    # --- Escalation flag ---
    escalation_flag = any(
        phrase in text.lower()
        for phrase in [
            "let me speak to a supervisor",
            "i want a manager",
            "this needs escalation",
            "transfer me"
        ]
    )

    # --- Billing / service flags ---
    billing_dispute_flag = any(
        phrase in text.lower()
        for phrase in ["charge", "billing", "refund", "overcharged", "invoice"]
    )

    outage_history_flag = any(
        phrase in text.lower()
        for phrase in ["outage", "service down", "no signal", "network issue"]
    )

    return {
        "call_id": row["call_id"],
        "customer_id": row["customer_id"],
        "primary_scenario": row["primary_scenario"],

        # model outputs
        "sentiment": int(pred),
        "confidence": float(confidence),

        # engineered features
        "word_count": word_count,
        "avg_word_length": avg_word_length,
        "num_exclamation_marks": num_exclamation_marks,
        "frustration_level": frustration_level,
        "emotion_scores": emotion_scores,
        "call_duration_indicator": call_duration_indicator,
        "escalation_flag": escalation_flag,

        # billing / service
        "billing_dispute_flag": billing_dispute_flag,
        "outage_history_flag": outage_history_flag,
        "overage_amount_last_cycle": row.get("overage_amount_last_cycle"),

        # agent behavior
        "agent_experience": row.get("agent_experience"),
        "transfer_count": row.get("transfer_count"),
        "resolution_flag": any(
            phrase in text.lower()
            for phrase in ["resolved", "fixed", "taken care of", "issue closed"]
        ),

        # passthrough fields
        "qa_score": row.get("qa_score"),
        "category": row.get("category")
    }
    
results = df.apply(predict_row, axis=1)
results.iloc[0]

# %%
pred_df = pd.DataFrame(data=results.tolist())
pred_df.head()

# %%
# %pip install emoji==1.7.0

emotion_model = AutoModelForSequenceClassification.from_pretrained(pretrained_model_name_or_path="j-hartmann/emotion-english-distilroberta-base")

device = "cuda" if torch.cuda.is_available() else "cpu"
emotion_model.to(device)

batch_size = 128

# Diverges from function template
# Implement to increase performance
def extract_emotions(texts) -> list[Any]:
    results = []

    for i in range(0, len(texts), batch_size):
        # Implement as batch process to increase performance
        batch = texts[i:i+batch_size]
        inputs = tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        ).to(device)

        with torch.no_grad():
            logits = emotion_model(**inputs).logits
            probs = F.softmax(input=logits, dim=-1)

        for p in probs:
            results.append({
                emotion_model.config.id2label[j]: float(p[j])
                for j in range(len(p))
            })

    return results

texts = df["clean_transcript"].tolist()
emotion_results = extract_emotions(texts=texts)
df["emotion_scores"] = emotion_results

df.head()

# %%
# %pip install vaderSentiment

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer # type: ignore imported in previous cell
analyzer = SentimentIntensityAnalyzer()

def toxicity_score(text) -> float | Literal[0]:
    if not isinstance(text, str):
        return 0
    scores = analyzer.polarity_scores(text=text)
    # Toxicity proxy = negative sentiment intensity
    return scores["neg"]

df["toxicity_score"] = df["clean_transcript"].apply(func=toxicity_score)



# %%

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
    "keeps going out"
]


def frustration_level(text) -> int:
    if not isinstance(text, str):
        return 0
    text_lower = text.lower()
    count = sum(text_lower.count(w) for w in FRUSTRATION_WORDS)
    # scale to 0–10
    return min(10, count * 2)

df["frustration_level"] = df["clean_transcript"].apply(func=frustration_level)


# %%
def escalation_probability(row) -> float:
    score = 0
    text = row["clean_transcript"].lower()
    if "cancel" in text or "switch providers" in text:
        score += 4
    if row["frustration_level"] >= 6:
        score += 3
    if row["toxicity_score"] > 0.3:
        score += 2
    if "billing" in text or "overage" in text:
        score += 1
    if "outage" in text or "slow" in text:
        score += 1
    return min(1.0, score / 10)

df["escalation_probability"] = df.apply(func=escalation_probability, axis=1)


# %%
def agent_turns(text) -> int:
    if not isinstance(text, str):
        return 0
    prefix = "Agent:" if "Agent:" in text else "Agent"
    return text.count(prefix)

def customer_turns(text) -> int:
    if not isinstance(text, str):
        return 0
    prefix = "Customer:" if "Customer:" in text else "Customer"
    return text.count(prefix)

df["agent_turns"] = df["call_transcript"].apply(func=agent_turns)
df["customer_turns"] = df["call_transcript"].apply(func=customer_turns)

# %%
EMPATHY_PHRASES = [
    "i understand",
    "i completely understand",
    "i hear your frustration",
    "i hear you",
    "i hear your concern",
    "i understand your frustration",
    "i understand how disruptive",
    "i know how frustrating",
    "i see why you're upset",
    "i can see why",
    "i understand why",

    "i apologize",
    "i sincerely apologize",
    "i'm sorry",
    "i truly apologize",
    "i apologize for the inconvenience",
    "i apologize if",

    "i see a high number",
    "i can see your service history",
    "i understand this has been going on",
    "i know you've called",
    "i see this has been a recurring issue",

    "i can definitely help",
    "i can certainly look into",
    "i'll make sure",
    "i'll take care of that",
    "i want to help resolve this",

    "let me check",
    "let me take a look",
    "let me see what i can do",
    "let me review your account",

    "thank you for your patience",
    "thank you for checking",
    "i appreciate you explaining",
    "i appreciate your time",

    "i understand this feels like a lot",
    "i know this unexpected increase is frustrating",
    "i understand you're having a tough time",

    "i know how important reliable service is",
    "i completely understand how that affects your work",
]


def empathy_score(text) -> int:
    text = text.lower()
    return sum(text.count(p.lower()) for p in EMPATHY_PHRASES)

df["agent_empathy_score"] = df["clean_transcript"].apply(func=empathy_score)


# %%
def billing_dispute_flag(text) -> bool:
    text = text.lower()
    return any(word in text for word in ["bill", "charge", "overage", "credit", "fee"])

def outage_history_flag(text) -> bool:
    text = text.lower()
    return any(word in text for word in ["outage", "slow", "disconnect", "no service"])

df["billing_dispute_flag"] = df["clean_transcript"].apply(func=billing_dispute_flag)
df["outage_history_flag"] = df["clean_transcript"].apply(func=outage_history_flag)


# %%
def build_features(df) -> Any:
    df = df.copy()
    # Emotion
    texts = df["clean_transcript"].tolist()
    emotion_results = extract_emotions(texts=texts)
    emotion_df = pd.DataFrame(data=emotion_results)
    df = pd.concat(objs=[df, emotion_df], axis=1)
    # Toxicity
    df["toxicity_score"] = df["clean_transcript"].apply(func=toxicity_score)
    # Frustration
    df["frustration_level"] = df["clean_transcript"].apply(func=frustration_level)
    # Escalation
    df["escalation_probability"] = df.apply(escalation_probability, axis=1)
    # Agent behavior
    df["agent_turns"] = df["call_transcript"].apply(func=agent_turns)
    df["customer_turns"] = df["clean_transcript"].apply(func=customer_turns)
    df["agent_talk_ratio"] = df["agent_turns"] / (df["agent_turns"] + df["customer_turns"] + 1e-6)
    df["customer_talk_ratio"] = df["customer_turns"] / (df["agent_turns"] + df["customer_turns"] + 1e-6)
    df["agent_empathy_score"] = df["clean_transcript"].apply(func=empathy_score)
    # Billing flags
    df["billing_dispute_flag"] = df["clean_transcript"].apply(func=billing_dispute_flag)
    df["outage_history_flag"] = df["clean_transcript"].apply(func=outage_history_flag)

    return df


# %%
df_features = build_features(df=df)
df_features.head()

# %%

from dotenv import load_dotenv

load_dotenv()

S3_BUCKET: str = os.getenv(key="S3_BUCKET", default="retention-engine-bucket")
MODEL_PREFIX: str = os.getenv(key="MODEL_PREFIX", default="models/sentiment")

export_dir = "exported_model"

model.save_pretrained(export_dir, safe_serialization=False)
tokenizer.save_pretrained(export_dir)

s3 = boto3.client("s3")


for root, dirs, files in os.walk(top=export_dir):
    for file in files:
        local_path = os.path.join(root, file)
        s3_path = f"{MODEL_PREFIX}/{export_dir}/{file}"
        s3.upload_file(local_path, S3_BUCKET, s3_path)

print("Upload complete.")


# %%

model = AutoModelForSequenceClassification.from_pretrained(pretrained_model_name_or_path="./exported_model")
print("Model loaded successfully!")

# %%
label_encoding_schema = {
    "call_id": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Unique call identifier; high-cardinality; typically excluded from modeling."
    },
    "customer_id": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Unique customer identifier; high-cardinality; often excluded to avoid leakage."
    },
    "call_date": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Raw date string; useful only if engineered into day/month/week features."
    },
    "call_time": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Raw time string; useful only if converted into hour-of-day or time bucket."
    },
    "agent_id": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Identifier for the agent; categorical feature; moderate cardinality."
    },
    "agent_name": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Human-readable agent name; redundant with agent_id; usually dropped."
    },
    "primary_scenario": {
        "type": "categorical",
        "encoding": "one_hot",
        "notes": "High-level scenario category (billing, outage, cancellation, etc.). Strong categorical signal."
    },
    "call_transcript": {
        "type": "text",
        "encoding": "passthrough",
        "notes": "Raw transcript text; not used directly in tabular models; used to generate NLP features."
    },
    "overall_rating": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Customer satisfaction rating (0-5). Numeric predictor."
    },
    "call_successful": {
        "type": "boolean",
        "encoding": "binary",
        "notes": "Binary success flag; may cause target leakage depending on prediction task."
    },
    "customer_monthly_spend": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Customer's monthly spend; numeric predictor."
    },
    "customer_service_count": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Number of customer service interactions in the last 12 months."
    },
    "customer_issue_history": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Count of past issues or complaints; numeric predictor."
    }
}


# %%
sentiment_feature_schema = {
    "call_id": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Unique identifier; usually dropped for modeling."
    },
    "customer_id": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Customer identifier; high-cardinality; often dropped."
    },
    "call_date": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Raw date string; useful only if engineered into day/month/week."
    },
    "call_time": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Raw time string; useful only if engineered into hour-of-day."
    },
    "agent_id": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Agent identifier; categorical feature."
    },
    "agent_name": {
        "type": "categorical",
        "encoding": "label_encode",
        "notes": "Human-readable agent name; redundant with agent_id."
    },
    "primary_scenario": {
        "type": "categorical",
        "encoding": "one_hot",
        "notes": "High-level call scenario category."
    },
    "call_transcript": {
        "type": "text",
        "encoding": "passthrough",
        "notes": "Raw transcript; not used directly for tabular models."
    },
    "overall_rating": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Customer rating (0-5)."
    },
    "call_successful": {
        "type": "boolean",
        "encoding": "binary",
        "notes": "Binary success flag; may cause leakage depending on target."
    },
    "customer_monthly_spend": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Customer's monthly spend."
    },
    "customer_service_count": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Number of service interactions in the last year."
    },
    "customer_issue_history": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Count of past issues or complaints."
    },
    "clean_transcript": {
        "type": "text",
        "encoding": "passthrough",
        "notes": "Preprocessed transcript; used to generate engineered features."
    },
    "word_count": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Total number of words in the transcript."
    },
    "avg_word_length": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Average word length across the transcript."
    },
    "num_exclamation_marks": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Count of exclamation marks; proxy for emotional intensity."
    },
    "emotion_scores": {
        "type": "nested",
        "encoding": "expand",
        "nested_schema": {
            "anger": {"type": "numeric", "encoding": "normalize"},
            "joy": {"type": "numeric", "encoding": "normalize"},
            "sadness": {"type": "numeric", "encoding": "normalize"},
            "surprise": {"type": "numeric", "encoding": "normalize"},
            "fear": {"type": "numeric", "encoding": "normalize"}
        },
        "notes": "Emotion intensity scores extracted from transcript."
    },
    "toxicity_score": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Probability of toxic language."
    },
    "frustration_level": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Discrete frustration level (0–3)."
    },
    "escalation_probability": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Probability that the call escalates."
    },
    "agent_turns": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Number of times the agent speaks."
    },
    "customer_turns": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Number of times the customer speaks."
    },
    "agent_empathy_score": {
        "type": "numeric",
        "encoding": "normalize",
        "notes": "Empathy score for agent responses."
    },
    "billing_dispute_flag": {
        "type": "boolean",
        "encoding": "binary",
        "notes": "Whether the call involves a billing dispute."
    },
    "outage_history_flag": {
        "type": "boolean",
        "encoding": "binary",
        "notes": "Whether the customer recently experienced an outage."
    }
}


# %%
# Drop columns not useful for prediction
drop_cols = [
    'call_id',                  # ID: not relevant, introduces random noise, no predictive value, causes overfitting
    'customer_id',              # ID: creates leakage, introduces random noise, no predictive value, causes overfitting
    'call_date',                # Raw date is useless
    'call_time',                # Raw date is useless
    'call_transcript',          # primary data target, high‑dimensional, Label‑encoding is meaningless
]

schema_col = df.drop(columns=[c for c in drop_cols if c in df.columns])

# %%
import joblib

enc = CallRecordLabelEncoders()
enc.schema = label_encoding_schema # type: ignore


# Save or Overwrite label schema
with open(file='label_encoding_schema.json', mode='w') as f:
    json.dump(obj=label_encoding_schema, fp=f, indent=2)

enc.fit(df=schema_col)
label_encoders = enc.encoders

# Save the label encoders so the FastAPI wrapper can decode inputs
encoder_mapping = {}
for col, le in label_encoders.items():
    encoder_mapping[col] = dict(zip(le.classes_.tolist(), le.transform(le.classes_).tolist())) # type: ignore

with open(file='label_encoders.json', mode='w') as f:
    json.dump(obj=encoder_mapping, fp=f, indent=2)
print('Label encoders saved to label_encoders.json')


# %%
# Define final feature set (drop noisy/leaky columns)
sentiment_columns = [
    "primary_scenario",
    "agent_id",
    "agent_name",
    "overall_rating",
    "customer_monthly_spend",
    "customer_service_count",
    "customer_issue_history",
    "word_count",
    "avg_word_length",
    "num_exclamation_marks",
    "toxicity_score",
    "frustration_level",
    "escalation_probability",
    "agent_turns",
    "customer_turns",
    "agent_empathy_score",
    "billing_dispute_flag",
    "outage_history_flag"
]

# Filter dataframe
sentiment_df = df[sentiment_columns].copy()

# Save model
joblib.dump(value=model, filename="sentiment_model.joblib")
print("Model saved to sentiment_model.joblib")

# Save schema
with open(file="sentiment_schema.json", mode="w") as f:
    json.dump(obj=sentiment_feature_schema, fp=f, indent=2)

# Fit encoder on categorical columns only
categorical_cols = ["primary_scenario", "agent_id"]

enc = CallRecordLabelEncoders()
enc.fit(df=sentiment_df[categorical_cols])
sentiment_encoders = enc.encoders

# Save encoder mapping
sentiment_encoder_mapping = {
    col: dict(zip(le.classes_.tolist(), le.transform(le.classes_).tolist())) # type: ignore
    for col, le in sentiment_encoders.items()
}

with open(file="sentiment_encoders.json", mode="w") as f:
    json.dump(obj=sentiment_encoder_mapping, fp=f, indent=2)

print("Sentiment encoder saved to sentiment_encoders.json")

# Save feature order
with open(file="sentiment_columns.json", mode="w") as f:
    json.dump(obj=df.columns.tolist(), fp=f, indent=2)

print("Sentiment columns saved to sentiment_columns.json")


# %%
# Load the schema for inclusion in predictions
with open(file="sentiment_schema.json", mode="r") as f:
    full_schema = json.load(f)

# Modify predict_row to include the schema
def predict_row_with_schema(row) -> dict[str, Any]:
    # Call the original predict_row
    result = predict_row(row=row)
    # Add the schema
    result["schema"] = full_schema
    return result

# Test with schema
sample_with_schema = predict_row_with_schema(row=df.iloc[0])
print("Prediction with schema included:")
print(json.dumps(obj=sample_with_schema, indent=2)[:500] + "...")  # Truncate for display



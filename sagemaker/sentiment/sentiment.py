import pandas as pd
import numpy as np
import os
from datasets import Dataset
from sklearn.model_selection import train_test_split
from transformers import (
    DistilBertTokenizerFast,
    DistilBertForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
    get_linear_schedule_with_warmup
)
from typing import Any
import torch
import evaluate


# 1. Load dataset

filepath = os.path.join(os.path.dirname(p=__file__), "call_transcripts_sentiment.csv")
df = pd.read_csv(filepath_or_buffer=filepath)

# EXPECTED COLUMNS:
# - transcript (string)
# - sentiment (int: 0=neg, 1=neutral, 2=pos)

df = df.dropna(subset=["call_transcript", "sentiment"])

df = df[["call_transcript", "sentiment"]]

# Stratified split
train_df, val_df = train_test_split(
    df,
    test_size=0.2,
    random_state=42,
    stratify=df["sentiment"]
)

train_ds = Dataset.from_pandas(df=train_df)
val_ds = Dataset.from_pandas(df=val_df)


# Tokenizer
model_name = "distilbert-base-uncased"
tokenizer = DistilBertTokenizerFast.from_pretrained(pretrained_model_name_or_path=model_name)

def tokenize(batch) -> Any:
    return tokenizer(
        batch["call_transcript"],
        truncation=True,
        padding="max_length",
        max_length=256  # longer for call transcripts
    )

train_ds = train_ds.map(function=tokenize, batched=True)
val_ds = val_ds.map(function=tokenize, batched=True)

train_ds = train_ds.remove_columns(column_names=["call_transcript"])
val_ds = val_ds.remove_columns(column_names=["call_transcript"])

train_ds = train_ds.rename_column(original_column_name="sentiment", new_column_name="labels")
val_ds = val_ds.rename_column(original_column_name="sentiment", new_column_name="labels")

train_ds.set_format(type="torch")
val_ds.set_format(type="torch")


# Class weights (important for imbalance)
class_counts = train_df["sentiment"].value_counts().sort_index()
weights = torch.tensor(data=1.0 / class_counts, dtype=torch.float)
weights = weights / weights.sum()  # normalize


# Model
num_labels = 3
model = DistilBertForSequenceClassification.from_pretrained(
    pretrained_model_name_or_path=model_name,
    num_labels=num_labels,
    id2label={
       0: "negative",
       1: "neutral",
       2: "positive",
    }
    ,
    label2id={
       "negative": 0,
       "neutral": 1,
       "positive": 2,
    }
)

# Inject class weights into loss function
model.classifier = torch.nn.Linear(in_features=model.config.dim, out_features=num_labels)
loss_fn = torch.nn.CrossEntropyLoss(weight=weights)


# Metrics
accuracy = evaluate.load(path="accuracy")
f1 = evaluate.load(path="f1")

def compute_metrics(eval_pred) -> dict[str, Any]:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    return {
        "accuracy": accuracy.compute(predictions=preds, references=labels)["accuracy"],
        "f1": f1.compute(predictions=preds, references=labels, average="weighted")["f1"]
    }


# Training configuration (improved)
training_args = TrainingArguments(
    output_dir="./sentiment_model",
    evaluation_strategy="epoch",
    save_strategy="epoch",
    learning_rate=3e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=16,
    gradient_accumulation_steps=4,  # effective batch size = 32
    num_train_epochs=6,
    weight_decay=0.01,
    warmup_ratio=0.1,
    load_best_model_at_end=True,
    fp16=False,
    bf16=False,
    logging_steps=50,
    report_to="none"
)


# Trainer with custom loss
class WeightedTrainer(Trainer):
    def compute_loss(self, model, inputs, num_items_in_batch=None, return_outputs=False) -> tuple[Any, Any] | Any:
        labels = inputs.get("labels")

        # Forward pass
        outputs = model(**inputs)
        logits = outputs.get("logits")

        # Ensure labels and class weights are on the same device as logits
        device = logits.device
        labels = labels.to(device)
        loss_fn_device = loss_fn.to(device=device)

        loss = loss_fn_device(logits, labels)
        return (loss, outputs) if return_outputs else loss

trainer = WeightedTrainer(
    model=model,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    tokenizer=tokenizer,
    data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
    compute_metrics=compute_metrics
)


# Train
trainer.train()


# Save model
path = os.path.join(os.path.dirname(__file__), "training_model")
trainer.save_model(output_dir=path)
tokenizer.save_pretrained(path)

print("Training complete. Model saved to ./training_model")

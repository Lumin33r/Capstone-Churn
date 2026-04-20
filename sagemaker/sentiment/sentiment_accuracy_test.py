"""Compare Okino's finbert endpoint vs our revised endpoint on REAL labeled transcripts.

Samples 30 transcripts from the training CSV (stratified by rating) and maps
overall_rating to sentiment: 3-4=Negative, 5-6=Neutral, 7-8=Positive.
"""

import json
import boto3
import pandas as pd

runtime = boto3.client("sagemaker-runtime", region_name="us-east-1")

OKINO = "retention-sentiment-analysis-endpoint"
OURS = "retention-sentiment-revised-endpoint"

# Sample stratified by rating
df = pd.read_csv("sagemaker/sentiment/data/call_transcripts.csv")

def rating_to_sentiment(r):
    if r <= 4: return "Negative"
    elif r <= 6: return "Neutral"
    else: return "Positive"

df["sentiment"] = df["overall_rating"].apply(rating_to_sentiment)

# Stratified sample: 10 per class
samples = []
for sent in ["Negative", "Neutral", "Positive"]:
    subset = df[df["sentiment"] == sent].sample(n=10, random_state=42)
    samples.append(subset)
test_df = pd.concat(samples).reset_index(drop=True)

print(f"Testing {len(test_df)} transcripts (10 per class)")
print()


def parse_response(resp_body):
    raw = json.loads(resp_body)
    if isinstance(raw, list):
        inner = raw[0]
        if isinstance(inner, str):
            inner = json.loads(inner)
            if isinstance(inner, list):
                inner = inner[0]
        label = inner.get("sentiment_label") or inner.get("sentiment")
        if isinstance(label, int):
            label = {0: "negative", 1: "neutral", 2: "positive"}.get(label, "unknown")
        return str(label).capitalize()
    return "Unknown"


def test_endpoint(endpoint_name, display_name):
    print(f"{'='*70}")
    print(f"  {display_name}")
    print(f"  Endpoint: {endpoint_name}")
    print(f"{'='*70}")

    correct = 0
    confusion = {"Negative": {}, "Neutral": {}, "Positive": {}}
    per_class = {"Negative": [0, 0], "Neutral": [0, 0], "Positive": [0, 0]}

    for _, row in test_df.iterrows():
        expected = row["sentiment"]
        transcript = row["call_transcript"][:15000]
        try:
            resp = runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="application/json",
                Body=json.dumps({"call_transcript": transcript}),
            )
            predicted = parse_response(resp["Body"].read().decode())
            match = predicted == expected
            if match: correct += 1
            confusion[expected][predicted] = confusion[expected].get(predicted, 0) + 1
            per_class[expected][1] += 1
            if match: per_class[expected][0] += 1
        except Exception as e:
            print(f"  ERROR: {e}")

    total = len(test_df)
    accuracy = correct / total * 100
    print(f"\n  Overall Accuracy: {correct}/{total} = {accuracy:.1f}%")
    print()
    print(f"  Per-class accuracy:")
    for cls in ["Negative", "Neutral", "Positive"]:
        c, t = per_class[cls]
        pct = (c/t*100) if t > 0 else 0
        print(f"    {cls:<10}: {c}/{t} = {pct:.0f}%")
    print()
    print(f"  Confusion Matrix:")
    print(f"                  Predicted")
    print(f"                  Neg  Neu  Pos")
    for exp in ["Negative", "Neutral", "Positive"]:
        n = confusion[exp].get("Negative", 0)
        u = confusion[exp].get("Neutral", 0)
        p = confusion[exp].get("Positive", 0)
        print(f"    Actual {exp:<6} {n:>4} {u:>4} {p:>4}")
    return accuracy


acc_okino = test_endpoint(OKINO, "Okino (FinBERT pretrained)")
print()
acc_ours = test_endpoint(OURS, "Ours (DistilBERT retrained 3-class)")

print()
print("="*70)
print(f"  SUMMARY")
print("="*70)
print(f"  Okino (FinBERT):             {acc_okino:.1f}%")
print(f"  Ours (DistilBERT retrained): {acc_ours:.1f}%")
print(f"  Random baseline:             33.3%")
print(f"  Majority class baseline:     33.3% (balanced sample)")

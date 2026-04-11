"""QA Evaluator API — stub service (George/Okino to implement)."""

from fastapi import FastAPI

app = FastAPI(title="QA Evaluator API")


@app.get("/health")
def health():
    return {"status": "ok"}

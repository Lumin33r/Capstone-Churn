# services/sentiment-analysis-api/Dockerfile
# Runs the enriched sentiment analysis wrapper:
#   - Calls SageMaker endpoint for base classification
#   - Enriches with NLP post-processing (emotions, qa_score, escalation, resolution)
# Returns all 7 fields the churn predictor needs.

FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8002/health')" || exit 1

EXPOSE 8002
CMD ["uvicorn", "app_enriched:app", "--host", "0.0.0.0", "--port", "8002"]

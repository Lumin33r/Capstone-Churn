# ── Churn Predictor Endpoint ───────────────────────────────────────────
# Native XGBoost serving — no inference.py, no SAGEMAKER_PROGRAM.
# The model.tar.gz must contain ONLY the xgboost-model binary file.
# S3 path: s3://sagemaker-us-east-1-388691194728/models/churn/model.tar.gz

resource "aws_sagemaker_model" "churn_model" {
  name               = "churn-predictor-model"
  execution_role_arn = "arn:aws:iam::388691194728:role/service-role/AmazonSageMaker-ExecutionRole-20260224T095369"

  primary_container {
    image          = "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-xgboost:1.7-1"
    model_data_url = "s3://sagemaker-us-east-1-388691194728/models/churn/model.tar.gz"
  }
}

resource "aws_sagemaker_endpoint_configuration" "churn_endpoint_config" {
  name = "churn-predictor-config"

  production_variants {
    variant_name           = "primary"
    model_name             = aws_sagemaker_model.churn_model.name
    initial_instance_count = 1
    instance_type          = "ml.m5.large"
  }
}

resource "aws_sagemaker_endpoint" "churn_endpoint" {
  name                 = "churn-predictor-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.churn_endpoint_config.name
}

# ── Sentiment Analysis Endpoint ───────────────────────────────────────

resource "aws_sagemaker_model" "sentiment_model" {
  name               = "retention-sentiment-analysis-model"
  execution_role_arn = "arn:aws:iam::388691194728:role/retention/retention-sagemaker-execution-role"

  primary_container {
    image          = "763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-inference:2.6.0-transformers4.49.0-cpu-py312-ubuntu22.04"
    model_data_url = "s3://retention-engine-bucket/models/sentiment/model.tar.gz"

    environment = {
      SAGEMAKER_PROGRAM = "inference.py"
    }
  }
}


resource "aws_sagemaker_endpoint_configuration" "sentiment_endpoint_config" {
  name = "retention-sentiment-analysis-config"

  production_variants {
    variant_name           = "primary"
    model_name             = aws_sagemaker_model.sentiment_model.name
    initial_instance_count = 1
    instance_type          = "ml.t2.medium"
  }
}

resource "aws_sagemaker_endpoint" "sentiment_endpoint" {
  name                 = "retention-sentiment-analysis-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.sentiment_endpoint_config.name
}

##### Note: Sagemaker, Sagemaker Endpoint, and Sagemaker Configuration
##### will be created programmatically 


# resource "aws_ecr_repository_policy" "allow_sagemaker" {
#   repository = "763104351884/*"

#   policy = <<EOF
# {
#   "Version": "2008-10-17",
#   "Statement": [
#     {
#       "Sid": "AllowSageMakerPull",
#       "Effect": "Allow",
#       "Principal": {
#         "Service": "sagemaker.amazonaws.com"
#       },
#       "Action": [
#         "ecr:GetDownloadUrlForLayer",
#         "ecr:BatchGetImage",
#         "ecr:BatchCheckLayerAvailability"
#       ]
#     }
#   ]
# }
# EOF
# }


# resource "aws_sagemaker_model" "sentiment_model" {
  # name               = "sentiment-analysis-model"
  # execution_role_arn = aws_iam_role.sagemaker_execution_role.arn
# 
  # primary_container { 
    # image = "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.0.0-cpu-py310"
# 
    # environment = {
      # HF_MODEL_ID = "distilbert-base-uncased-finetuned-sst-2-english"
      # HF_TASK     = "text-classification"
    # }
  # }
# }
# 
# 
# resource "aws_sagemaker_endpoint_configuration" "sentiment_endpoint_config" {
  # name = "sentiment-endpoint-config"
# 
  # production_variants {
    # variant_name           = "AllTraffic"
    # model_name             = aws_sagemaker_model.sentiment_model.name
    # initial_instance_count = 1
    # instance_type          = "ml.t2.medium"
  # }
# }
# 
# resource "aws_sagemaker_endpoint" "sentiment_endpoint" {
  # name                 = "sentiment-endpoint"
  # endpoint_config_name = aws_sagemaker_endpoint_configuration.sentiment_endpoint_config.name
# }

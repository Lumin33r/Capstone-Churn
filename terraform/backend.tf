# terraform/backend.tf
# Remote state backend — stores terraform.tfstate in S3 so all teammates
# share the same infrastructure state instead of having separate local copies.
#
# DynamoDB table acts as a lock — prevents two people from running
# terraform apply at the same time which would corrupt the state file.
#
# IMPORTANT: The S3 bucket and DynamoDB table must be created MANUALLY
# in AWS before running terraform init with this backend configured.
# They cannot be created by Terraform itself because Terraform needs
# the backend to exist before it can store any state.
#
# To create them manually run these AWS CLI commands once:
#   aws s3 mb s3://retention-engine-tf-state --region us-east-1
#   aws dynamodb create-table \
#     --table-name retention-engine-tf-lock \
#     --attribute-definitions AttributeName=LockID,AttributeType=S \
#     --key-schema AttributeName=LockID,KeyType=HASH \
#     --billing-mode PAY_PER_REQUEST \
#     --region us-east-1

terraform {
  backend "s3" {
    bucket         = "retention-engine-tf-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "retention-engine-tf-lock"
    encrypt        = true
  }
}
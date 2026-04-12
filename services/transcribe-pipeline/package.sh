#!/bin/bash
# Package the Lambda function for deployment
# Usage: ./package.sh
# Output: lambda_function.zip (referenced by terraform/transcribe.tf)

cd "$(dirname "$0")"
zip lambda_function.zip lambda_function.py
echo "Created lambda_function.zip"
echo "To deploy: run 'terraform apply' from the terraform/ directory"

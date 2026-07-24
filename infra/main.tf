# Terraform configuration
terraform {
  required_version = ">= 1.7"
  required_providers { 
    aws = { source = "hashicorp/aws", version = "~> 5.60" } 
  }

  backend "s3" {
    bucket         = "cloud-rag-engine-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

# Provider config
provider "aws" { 
  region = var.region   
  default_tags {
    tags = {
      project     = "cloud-rag-engine"
      environment = "dev"
      managed_by  = "terraform"
    }
  }
}

variable "region"        { default = "us-east-1" }
variable "project"       { default = "cloud-rag-engine" }
variable "image_uri"     { type = string }   # passed by CI
variable "anthropic_api_key" { 
  type = string
  sensitive = true 
}

# Container registry config
resource "aws_ecr_repository" "app" {
  name                 = var.project
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_ecr_repository_policy" "lambda_pull" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowLambdaPull"
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
        Condition = {
          StringEquals = {
            "aws:sourceArn" = "arn:aws:lambda:us-east-1:058264351864:function:cloud-rag-engine"
          }
        }
      }
    ]
  })
}

# Lambda iam role
resource "aws_iam_role" "lambda" {
  name = "${var.project}-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ 
      Effect = "Allow", 
      Principal = { Service = "lambda.amazonaws.com" }, 
      Action = "sts:AssumeRole" 
    }]
  })
}


resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}


resource "aws_lambda_function" "app" {
  function_name = var.project
  package_type  = "Image"
  image_uri     = var.image_uri
  role          = aws_iam_role.lambda.arn
  memory_size   = 1024
  timeout       = 30
  environment {
    variables = { ANTHROPIC_API_KEY = var.anthropic_api_key }
  }

  depends_on = [
    aws_ecr_repository_policy.lambda_pull,
    aws_iam_role_policy_attachment.basic
  ]
}

resource "aws_apigatewayv2_api" "http" {
  name          = var.project
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.app.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "any" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

output "public_url"   { value = aws_apigatewayv2_api.http.api_endpoint }
output "ecr_repo_url" { value = aws_ecr_repository.app.repository_url }

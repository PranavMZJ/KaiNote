# ------------------------------------------------------------------------------
# Outputs
# ------------------------------------------------------------------------------

# Cognito outputs
output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_app_client_id" {
  description = "Cognito App Client ID"
  value       = aws_cognito_user_pool_client.main.id
}

output "cognito_jwks_endpoint" {
  description = "Cognito JWKS endpoint for JWT verification"
  value       = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/jwks.json"
}

# REST API Gateway outputs
output "rest_api_id" {
  description = "REST API Gateway ID"
  value       = aws_api_gateway_rest_api.main.id
}

output "rest_api_endpoint" {
  description = "REST API Gateway invoke URL"
  value       = aws_api_gateway_stage.main.invoke_url
}

# WebSocket API Gateway outputs
output "ws_api_id" {
  description = "WebSocket API Gateway ID"
  value       = aws_apigatewayv2_api.ws.id
}

output "ws_api_endpoint" {
  description = "WebSocket API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.ws.invoke_url
}

# S3 bucket outputs
output "s3_data_bucket_name" {
  description = "S3 data bucket name (transcripts and reports)"
  value       = aws_s3_bucket.data.id
}

output "s3_data_bucket_arn" {
  description = "S3 data bucket ARN"
  value       = aws_s3_bucket.data.arn
}

output "s3_prompts_bucket_name" {
  description = "S3 prompts bucket name (prompt templates and schemas)"
  value       = aws_s3_bucket.prompts.id
}

output "s3_prompts_bucket_arn" {
  description = "S3 prompts bucket ARN"
  value       = aws_s3_bucket.prompts.arn
}

# DynamoDB outputs
output "dynamodb_connections_table_name" {
  description = "DynamoDB connections table name"
  value       = aws_dynamodb_table.connections.name
}

output "dynamodb_connections_table_arn" {
  description = "DynamoDB connections table ARN"
  value       = aws_dynamodb_table.connections.arn
}

output "dynamodb_meetings_table_name" {
  description = "DynamoDB meetings metadata table name"
  value       = aws_dynamodb_table.meetings.name
}

output "dynamodb_meetings_table_arn" {
  description = "DynamoDB meetings metadata table ARN"
  value       = aws_dynamodb_table.meetings.arn
}

output "dynamodb_audio_buffer_table_name" {
  description = "DynamoDB audio buffer table name"
  value       = aws_dynamodb_table.audio_buffer.name
}

output "dynamodb_audio_buffer_table_arn" {
  description = "DynamoDB audio buffer table ARN"
  value       = aws_dynamodb_table.audio_buffer.arn
}

# Step Functions outputs
output "sfn_state_machine_arn" {
  description = "Step Functions state machine ARN"
  value       = aws_sfn_state_machine.workflow.arn
}

output "sfn_state_machine_name" {
  description = "Step Functions state machine name"
  value       = aws_sfn_state_machine.workflow.name
}

# Bedrock Guardrail outputs
output "bedrock_guardrail_id" {
  description = "Bedrock Guardrail ID"
  value       = aws_bedrock_guardrail.main.guardrail_id
}

output "bedrock_guardrail_version" {
  description = "Bedrock Guardrail version"
  value       = aws_bedrock_guardrail.main.version
}

output "bedrock_guardrail_arn" {
  description = "Bedrock Guardrail ARN"
  value       = aws_bedrock_guardrail.main.guardrail_arn
}

# Frontend hosting outputs
output "cloudfront_distribution_domain_name" {
  description = "CloudFront distribution domain name for the frontend"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for the frontend"
  value       = aws_cloudfront_distribution.frontend.id
}

output "s3_frontend_bucket_name" {
  description = "S3 frontend bucket name (static site assets)"
  value       = aws_s3_bucket.frontend.id
}

# ECS Fargate outputs
output "ecr_repository_url" {
  description = "ECR repository URL for the transcription service (used for docker push)"
  value       = aws_ecr_repository.transcription.repository_url
}

output "alb_dns_name" {
  description = "ALB DNS name (WebSocket endpoint for the frontend)"
  value       = aws_lb.transcription.dns_name
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.transcription.name
}

output "ecs_instance_id" {
  description = "ECS EC2 host instance ID"
  value       = aws_instance.ecs_host.id
}

# SNS outputs
output "sns_notifications_topic_arn" {
  description = "SNS topic ARN for post-meeting notifications"
  value       = aws_sns_topic.notifications.arn
}

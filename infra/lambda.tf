# ------------------------------------------------------------------------------
# Lambda Functions and CloudWatch Log Groups
# Requirements: 14.1, 14.2, 14.3, 16.1, 16.2
# ------------------------------------------------------------------------------

# ==============================================================================
# Placeholder deployment package
# ==============================================================================

data "archive_file" "lambda_placeholder" {
  type        = "zip"
  source_file = "${path.module}/../backend/placeholder/handler.py"
  output_path = "${path.module}/.build/placeholder.zip"
}

# ==============================================================================
# CloudWatch Log Groups (30-day retention)
# ==============================================================================

resource "aws_cloudwatch_log_group" "ws_authorizer" {
  name              = "/aws/lambda/${local.name_prefix}-ws-authorizer"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "ws_handler" {
  name              = "/aws/lambda/${local.name_prefix}-ws-handler"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "stream_bridge" {
  name              = "/aws/lambda/${local.name_prefix}-stream-bridge"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "cleanup" {
  name              = "/aws/lambda/${local.name_prefix}-cleanup"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "chunker" {
  name              = "/aws/lambda/${local.name_prefix}-chunker"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "generator" {
  name              = "/aws/lambda/${local.name_prefix}-generator"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "validator" {
  name              = "/aws/lambda/${local.name_prefix}-validator"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "store" {
  name              = "/aws/lambda/${local.name_prefix}-store"
  retention_in_days = 30
  tags              = local.common_tags
}

# ==============================================================================
# 1. WebSocket Authorizer Lambda — 256 MB / 30 s
# ==============================================================================

resource "aws_lambda_function" "ws_authorizer" {
  function_name = "${local.name_prefix}-ws-authorizer"
  role          = aws_iam_role.ws_auth.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  memory_size   = 256
  timeout       = 30

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.main.id
      COGNITO_JWKS_URL     = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/jwks.json"
    }
  }

  depends_on = [aws_cloudwatch_log_group.ws_authorizer]

  tags = local.common_tags
}

# ==============================================================================
# 2. WebSocket Handler Lambda — 256 MB / 30 s
# ==============================================================================

resource "aws_lambda_function" "ws_handler" {
  function_name = "${local.name_prefix}-ws-handler"
  role          = aws_iam_role.ws_handler.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  memory_size   = 256
  timeout       = 30

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      CONNECTIONS_TABLE = aws_dynamodb_table.connections.name
      WS_API_ENDPOINT   = "${aws_apigatewayv2_api.ws.api_endpoint}/${aws_apigatewayv2_stage.ws.name}"
    }
  }

  depends_on = [aws_cloudwatch_log_group.ws_handler]

  tags = local.common_tags
}

# ==============================================================================
# 3. Streaming Bridge Lambda — 512 MB / 900 s
# ==============================================================================

resource "aws_lambda_function" "stream_bridge" {
  function_name = "${local.name_prefix}-stream-bridge"
  role          = aws_iam_role.stream_bridge.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  memory_size   = 512
  timeout       = 900

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      TRANSCRIPT_BUCKET  = aws_s3_bucket.data.id
      STEP_FUNCTION_ARN  = "arn:aws:states:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:stateMachine:${local.name_prefix}-workflow"
      CONNECTIONS_TABLE   = aws_dynamodb_table.connections.name
      WS_API_ENDPOINT    = "${aws_apigatewayv2_api.ws.api_endpoint}/${aws_apigatewayv2_stage.ws.name}"
    }
  }

  depends_on = [aws_cloudwatch_log_group.stream_bridge]

  tags = local.common_tags
}

# ==============================================================================
# 4. REST API Lambda — 256 MB / 30 s
# ==============================================================================

resource "aws_lambda_function" "api" {
  function_name = "${local.name_prefix}-api"
  role          = aws_iam_role.api.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  memory_size   = 256
  timeout       = 30

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      DATA_BUCKET       = aws_s3_bucket.data.id
      STEP_FUNCTION_ARN = "arn:aws:states:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:stateMachine:${local.name_prefix}-workflow"
    }
  }

  depends_on = [aws_cloudwatch_log_group.api]

  tags = local.common_tags
}

# ==============================================================================
# 5. Transcript Cleanup Lambda — 256 MB / 30 s
# ==============================================================================

resource "aws_lambda_function" "cleanup" {
  function_name = "${local.name_prefix}-cleanup"
  role          = aws_iam_role.cleanup.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  memory_size   = 256
  timeout       = 30

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      DATA_BUCKET = aws_s3_bucket.data.id
    }
  }

  depends_on = [aws_cloudwatch_log_group.cleanup]

  tags = local.common_tags
}

# ==============================================================================
# 6. Transcript Chunker Lambda — 256 MB / 30 s
# ==============================================================================

resource "aws_lambda_function" "chunker" {
  function_name = "${local.name_prefix}-chunker"
  role          = aws_iam_role.chunker.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  memory_size   = 256
  timeout       = 30

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      DATA_BUCKET = aws_s3_bucket.data.id
    }
  }

  depends_on = [aws_cloudwatch_log_group.chunker]

  tags = local.common_tags
}

# ==============================================================================
# 7. Minutes Generator Lambda — 1024 MB / 120 s
# ==============================================================================

resource "aws_lambda_function" "generator" {
  function_name = "${local.name_prefix}-generator"
  role          = aws_iam_role.generator.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  memory_size   = 1024
  timeout       = 120

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      PROMPT_BUCKET     = aws_s3_bucket.prompts.id
      PROMPT_VERSION    = "v1"
      GUARDRAIL_ID      = ""
      GUARDRAIL_VERSION = ""
      MODEL_ID          = "anthropic.claude-3-haiku-20240307-v1:0"
    }
  }

  depends_on = [aws_cloudwatch_log_group.generator]

  tags = local.common_tags
}

# ==============================================================================
# 8. Schema Validator Lambda — 256 MB / 30 s
# ==============================================================================

resource "aws_lambda_function" "validator" {
  function_name = "${local.name_prefix}-validator"
  role          = aws_iam_role.validator.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  memory_size   = 256
  timeout       = 30

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      PROMPT_BUCKET = aws_s3_bucket.prompts.id
    }
  }

  depends_on = [aws_cloudwatch_log_group.validator]

  tags = local.common_tags
}

# ==============================================================================
# 9. Report Storage Lambda — 256 MB / 30 s
# ==============================================================================

resource "aws_lambda_function" "store" {
  function_name = "${local.name_prefix}-store"
  role          = aws_iam_role.store.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  memory_size   = 256
  timeout       = 30

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      DATA_BUCKET = aws_s3_bucket.data.id
    }
  }

  depends_on = [aws_cloudwatch_log_group.store]

  tags = local.common_tags
}

# ==============================================================================
# Lambda Permissions — API Gateway invocation
# ==============================================================================

# --- REST API Gateway → api Lambda ---
resource "aws_lambda_permission" "api_gw_rest" {
  statement_id  = "AllowRESTAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# --- WebSocket API Gateway → ws-authorizer Lambda ---
resource "aws_lambda_permission" "api_gw_ws_authorizer" {
  statement_id  = "AllowWSAPIGatewayInvokeAuthorizer"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ws_authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ws.execution_arn}/*"
}

# --- WebSocket API Gateway → ws-handler Lambda ---
resource "aws_lambda_permission" "api_gw_ws_handler" {
  statement_id  = "AllowWSAPIGatewayInvokeHandler"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ws_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ws.execution_arn}/*"
}

# --- WebSocket API Gateway → stream-bridge Lambda ---
resource "aws_lambda_permission" "api_gw_ws_stream_bridge" {
  statement_id  = "AllowWSAPIGatewayInvokeStreamBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stream_bridge.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ws.execution_arn}/*"
}

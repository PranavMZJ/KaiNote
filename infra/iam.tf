# ------------------------------------------------------------------------------
# IAM Roles and Policies for Lambda Functions and Step Functions
# Requirements: 13.4, 13.5, 16.1, 16.2
# ------------------------------------------------------------------------------

# --- Data sources for dynamic ARN construction ---
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# --- Common Lambda assume-role policy ---
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# --- Common Step Functions assume-role policy ---
data "aws_iam_policy_document" "sfn_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

# ==============================================================================
# 1. WebSocket Authorizer Lambda Role — CloudWatch Logs only
# ==============================================================================

resource "aws_iam_role" "ws_auth" {
  name                 = "${local.name_prefix}-ws-auth-role"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy" "ws_auth" {
  name = "${local.name_prefix}-ws-auth-policy"
  role = aws_iam_role.ws_auth.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.name_prefix}-ws-authorizer:*"
      }
    ]
  })
}

# ==============================================================================
# 2. WebSocket Handler Lambda Role — DynamoDB, CloudWatch Logs, API GW Mgmt
# ==============================================================================

resource "aws_iam_role" "ws_handler" {
  name                 = "${local.name_prefix}-ws-handler-role"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy" "ws_handler" {
  name = "${local.name_prefix}-ws-handler-policy"
  role = aws_iam_role.ws_handler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBConnections"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.connections.arn,
          "${aws_dynamodb_table.connections.arn}/index/*"
        ]
      },
      {
        Sid    = "ApiGatewayManagement"
        Effect = "Allow"
        Action = [
          "execute-api:ManageConnections"
        ]
        Resource = "arn:aws:execute-api:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${aws_apigatewayv2_api.ws.id}/*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.name_prefix}-ws-handler:*"
      }
    ]
  })
}

# ==============================================================================
# 3. Streaming Bridge Lambda Role — Transcribe, S3, Step Functions, DynamoDB,
#    API GW Mgmt, CloudWatch Logs
# ==============================================================================

resource "aws_iam_role" "stream_bridge" {
  name                 = "${local.name_prefix}-stream-role"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy" "stream_bridge" {
  name = "${local.name_prefix}-stream-policy"
  role = aws_iam_role.stream_bridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TranscribeStreaming"
        Effect = "Allow"
        Action = [
          "transcribe:StartStreamTranscriptionWebSocket",
          "transcribe:StartStreamTranscription"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3DataBucketWrite"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.data.arn}/*"
      },
      {
        Sid    = "StepFunctionsStart"
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = "arn:aws:states:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:stateMachine:${local.name_prefix}-workflow"
      },
      {
        Sid    = "DynamoDBConnectionsRead"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.connections.arn,
          "${aws_dynamodb_table.connections.arn}/index/*"
        ]
      },
      {
        Sid    = "ApiGatewayManagement"
        Effect = "Allow"
        Action = [
          "execute-api:ManageConnections"
        ]
        Resource = "arn:aws:execute-api:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${aws_apigatewayv2_api.ws.id}/*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.name_prefix}-stream-bridge:*"
      }
    ]
  })
}

# ==============================================================================
# 4. REST API Lambda Role — S3 read/write, Step Functions, CloudWatch Logs
# ==============================================================================

resource "aws_iam_role" "api" {
  name                 = "${local.name_prefix}-api-role"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy" "api" {
  name = "${local.name_prefix}-api-policy"
  role = aws_iam_role.api.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3DataBucketReadWrite"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*"
        ]
      },
      {
        Sid    = "StepFunctionsStart"
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = "arn:aws:states:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:stateMachine:${local.name_prefix}-workflow"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.name_prefix}-api:*"
      }
    ]
  })
}

# ==============================================================================
# 5. Transcript Cleanup Lambda Role — S3 read/write, CloudWatch Logs
# ==============================================================================

resource "aws_iam_role" "cleanup" {
  name                 = "${local.name_prefix}-cleanup-role"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy" "cleanup" {
  name = "${local.name_prefix}-cleanup-policy"
  role = aws_iam_role.cleanup.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3DataBucketReadWrite"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.data.arn}/*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.name_prefix}-cleanup:*"
      }
    ]
  })
}

# ==============================================================================
# 6. Transcript Chunker Lambda Role — S3 read, CloudWatch Logs
# ==============================================================================

resource "aws_iam_role" "chunker" {
  name                 = "${local.name_prefix}-chunker-role"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy" "chunker" {
  name = "${local.name_prefix}-chunker-policy"
  role = aws_iam_role.chunker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3DataBucketRead"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.data.arn}/*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.name_prefix}-chunker:*"
      }
    ]
  })
}

# ==============================================================================
# 7. Minutes Generator Lambda Role — S3 prompts read, Bedrock, CloudWatch Logs
# ==============================================================================

resource "aws_iam_role" "generator" {
  name                 = "${local.name_prefix}-generator-role"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy" "generator" {
  name = "${local.name_prefix}-generator-policy"
  role = aws_iam_role.generator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3PromptsBucketRead"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.prompts.arn}/*"
      },
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ApplyGuardrail"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:guardrail/*"
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.name_prefix}-generator:*"
      }
    ]
  })
}

# ==============================================================================
# 8. Schema Validator Lambda Role — S3 prompts read, CloudWatch Logs
# ==============================================================================

resource "aws_iam_role" "validator" {
  name                 = "${local.name_prefix}-validator-role"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy" "validator" {
  name = "${local.name_prefix}-validator-policy"
  role = aws_iam_role.validator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3PromptsBucketRead"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.prompts.arn}/*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.name_prefix}-validator:*"
      }
    ]
  })
}

# ==============================================================================
# 9. Report Storage Lambda Role — S3 data write, CloudWatch Logs
# ==============================================================================

resource "aws_iam_role" "store" {
  name                 = "${local.name_prefix}-store-role"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy" "store" {
  name = "${local.name_prefix}-store-policy"
  role = aws_iam_role.store.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3DataBucketWrite"
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.data.arn}/*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.name_prefix}-store:*"
      }
    ]
  })
}

# ==============================================================================
# 10. Step Functions Role — Invoke all workflow Lambdas, CloudWatch Logs
# ==============================================================================

resource "aws_iam_role" "sfn" {
  name                 = "${local.name_prefix}-sfn-role"
  assume_role_policy   = data.aws_iam_policy_document.sfn_assume_role.json
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy" "sfn" {
  name = "${local.name_prefix}-sfn-policy"
  role = aws_iam_role.sfn.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeWorkflowLambdas"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-cleanup",
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-chunker",
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-generator",
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-validator",
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-store"
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:CreateLogStream",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutLogEvents",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

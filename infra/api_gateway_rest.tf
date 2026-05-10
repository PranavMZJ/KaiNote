# ------------------------------------------------------------------------------
# REST API Gateway with Cognito Authorizer
# Requirements: 1.3, 1.4, 13.2, 16.1, 16.2
# ------------------------------------------------------------------------------

# --- REST API ---
resource "aws_api_gateway_rest_api" "main" {
  name        = "${local.name_prefix}-rest-api"
  description = "REST API for Meeting Minutes application"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = local.common_tags
}

# --- Cognito Authorizer ---
resource "aws_api_gateway_authorizer" "cognito" {
  name            = "${local.name_prefix}-cognito-auth"
  rest_api_id     = aws_api_gateway_rest_api.main.id
  type            = "COGNITO_USER_POOLS"
  identity_source = "method.request.header.Authorization"

  provider_arns = [
    aws_cognito_user_pool.main.arn,
  ]
}

# ==============================================================================
# Resource Paths
# ==============================================================================

# /meetings
resource "aws_api_gateway_resource" "meetings" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "meetings"
}

# /meetings/{meetingId}
resource "aws_api_gateway_resource" "meeting" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.meetings.id
  path_part   = "{meetingId}"
}

# /meetings/{meetingId}/report
resource "aws_api_gateway_resource" "report" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.meeting.id
  path_part   = "report"
}

# /meetings/{meetingId}/report/download
resource "aws_api_gateway_resource" "report_download" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.report.id
  path_part   = "download"
}

# /meetings/{meetingId}/retry
resource "aws_api_gateway_resource" "retry" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.meeting.id
  path_part   = "retry"
}

# /meetings/{meetingId}/agent-report
resource "aws_api_gateway_resource" "agent_report" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.meeting.id
  path_part   = "agent-report"
}

# ==============================================================================
# Methods — MOCK integration placeholders (Lambda wired in Task 4.2)
# ==============================================================================

# --- GET /meetings ---
resource "aws_api_gateway_method" "get_meetings" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.meetings.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_meetings" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.meetings.id
  http_method             = aws_api_gateway_method.get_meetings.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.api.invoke_arn
}

# --- GET /meetings/{meetingId} ---
resource "aws_api_gateway_method" "get_meeting" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.meeting.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_meeting" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.meeting.id
  http_method             = aws_api_gateway_method.get_meeting.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.api.invoke_arn
}

# --- GET /meetings/{meetingId}/report ---
resource "aws_api_gateway_method" "get_report" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.report.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_report" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.report.id
  http_method             = aws_api_gateway_method.get_report.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.api.invoke_arn
}

# --- PUT /meetings/{meetingId}/report ---
resource "aws_api_gateway_method" "put_report" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.report.id
  http_method   = "PUT"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "put_report" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.report.id
  http_method             = aws_api_gateway_method.put_report.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.api.invoke_arn
}

# --- GET /meetings/{meetingId}/report/download ---
resource "aws_api_gateway_method" "get_report_download" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.report_download.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_report_download" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.report_download.id
  http_method             = aws_api_gateway_method.get_report_download.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.api.invoke_arn
}

# --- POST /meetings/{meetingId}/retry ---
resource "aws_api_gateway_method" "post_retry" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.retry.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_retry" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.retry.id
  http_method             = aws_api_gateway_method.post_retry.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.api.invoke_arn
}

# --- GET /meetings/{meetingId}/agent-report ---
resource "aws_api_gateway_method" "get_agent_report" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.agent_report.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_agent_report" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.agent_report.id
  http_method             = aws_api_gateway_method.get_agent_report.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.api.invoke_arn
}

# --- DELETE /meetings/{meetingId} ---
resource "aws_api_gateway_method" "delete_meeting" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.meeting.id
  http_method   = "DELETE"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "delete_meeting" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.meeting.id
  http_method             = aws_api_gateway_method.delete_meeting.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.api.invoke_arn
}

# ==============================================================================
# CORS — OPTIONS preflight on every resource
# ==============================================================================

# --- OPTIONS /meetings ---
resource "aws_api_gateway_method" "options_meetings" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.meetings.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_meetings" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.meetings.id
  http_method = aws_api_gateway_method.options_meetings.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "options_meetings_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.meetings.id
  http_method = aws_api_gateway_method.options_meetings.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_meetings_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.meetings.id
  http_method = aws_api_gateway_method.options_meetings.http_method
  status_code = aws_api_gateway_method_response.options_meetings_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# --- OPTIONS /meetings/{meetingId} ---
resource "aws_api_gateway_method" "options_meeting" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.meeting.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_meeting" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.meeting.id
  http_method = aws_api_gateway_method.options_meeting.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "options_meeting_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.meeting.id
  http_method = aws_api_gateway_method.options_meeting.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_meeting_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.meeting.id
  http_method = aws_api_gateway_method.options_meeting.http_method
  status_code = aws_api_gateway_method_response.options_meeting_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# --- OPTIONS /meetings/{meetingId}/report ---
resource "aws_api_gateway_method" "options_report" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.report.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_report" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.report.id
  http_method = aws_api_gateway_method.options_report.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "options_report_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.report.id
  http_method = aws_api_gateway_method.options_report.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_report_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.report.id
  http_method = aws_api_gateway_method.options_report.http_method
  status_code = aws_api_gateway_method_response.options_report_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,PUT,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# --- OPTIONS /meetings/{meetingId}/report/download ---
resource "aws_api_gateway_method" "options_report_download" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.report_download.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_report_download" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.report_download.id
  http_method = aws_api_gateway_method.options_report_download.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "options_report_download_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.report_download.id
  http_method = aws_api_gateway_method.options_report_download.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_report_download_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.report_download.id
  http_method = aws_api_gateway_method.options_report_download.http_method
  status_code = aws_api_gateway_method_response.options_report_download_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# --- OPTIONS /meetings/{meetingId}/retry ---
resource "aws_api_gateway_method" "options_retry" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.retry.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_retry" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.retry.id
  http_method = aws_api_gateway_method.options_retry.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "options_retry_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.retry.id
  http_method = aws_api_gateway_method.options_retry.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_retry_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.retry.id
  http_method = aws_api_gateway_method.options_retry.http_method
  status_code = aws_api_gateway_method_response.options_retry_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# --- OPTIONS /meetings/{meetingId}/agent-report ---
resource "aws_api_gateway_method" "options_agent_report" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.agent_report.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_agent_report" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.agent_report.id
  http_method = aws_api_gateway_method.options_agent_report.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "options_agent_report_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.agent_report.id
  http_method = aws_api_gateway_method.options_agent_report.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_agent_report_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.agent_report.id
  http_method = aws_api_gateway_method.options_agent_report.http_method
  status_code = aws_api_gateway_method_response.options_agent_report_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ==============================================================================
# Gateway Responses — Add CORS headers to error responses (401, 403, 500)
# Without these, the Cognito authorizer's 401 response blocks CORS in browsers.
# ==============================================================================

resource "aws_api_gateway_gateway_response" "unauthorized" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "UNAUTHORIZED"
  status_code   = "401"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,PUT,POST,OPTIONS'"
  }

  response_templates = {
    "application/json" = "{\"error\": \"Unauthorized\"}"
  }
}

resource "aws_api_gateway_gateway_response" "access_denied" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "ACCESS_DENIED"
  status_code   = "403"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,PUT,POST,OPTIONS'"
  }

  response_templates = {
    "application/json" = "{\"error\": \"Access denied\"}"
  }
}

resource "aws_api_gateway_gateway_response" "default_5xx" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "DEFAULT_5XX"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,PUT,POST,OPTIONS'"
  }
}

# ==============================================================================
# Deployment and Stage
# ==============================================================================

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  # Redeploy when any method or integration changes
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.meetings,
      aws_api_gateway_resource.meeting,
      aws_api_gateway_resource.report,
      aws_api_gateway_resource.report_download,
      aws_api_gateway_resource.retry,
      aws_api_gateway_resource.agent_report,
      aws_api_gateway_method.get_meetings,
      aws_api_gateway_method.get_meeting,
      aws_api_gateway_method.delete_meeting,
      aws_api_gateway_method.get_report,
      aws_api_gateway_method.put_report,
      aws_api_gateway_method.get_report_download,
      aws_api_gateway_method.post_retry,
      aws_api_gateway_method.get_agent_report,
      aws_api_gateway_method.options_meetings,
      aws_api_gateway_method.options_meeting,
      aws_api_gateway_method.options_report,
      aws_api_gateway_method.options_report_download,
      aws_api_gateway_method.options_retry,
      aws_api_gateway_method.options_agent_report,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.get_meetings,
    aws_api_gateway_integration.get_meeting,
    aws_api_gateway_integration.delete_meeting,
    aws_api_gateway_integration.get_report,
    aws_api_gateway_integration.put_report,
    aws_api_gateway_integration.get_report_download,
    aws_api_gateway_integration.post_retry,
    aws_api_gateway_integration.get_agent_report,
    aws_api_gateway_integration.options_meetings,
    aws_api_gateway_integration.options_meeting,
    aws_api_gateway_integration.options_report,
    aws_api_gateway_integration.options_report_download,
    aws_api_gateway_integration.options_retry,
    aws_api_gateway_integration.options_agent_report,
  ]
}

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "v1"

  tags = local.common_tags
}

# --- Throttling settings: 1000 burst, 500 sustained ---
resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.main.stage_name
  method_path = "*/*"

  settings {
    throttling_burst_limit = 1000
    throttling_rate_limit  = 500
  }
}

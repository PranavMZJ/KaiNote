# ------------------------------------------------------------------------------
# WebSocket API Gateway
# Requirements: 2.5, 3.1, 16.1, 16.2
# ------------------------------------------------------------------------------

# --- WebSocket API ---
resource "aws_apigatewayv2_api" "ws" {
  name                       = "${local.name_prefix}-ws-api"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"

  tags = local.common_tags
}

# --- Stage ---
resource "aws_apigatewayv2_stage" "ws" {
  api_id      = aws_apigatewayv2_api.ws.id
  name        = "v1"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 1000
    throttling_rate_limit  = 500
  }

  tags = local.common_tags
}

# ==============================================================================
# Lambda Authorizer
# ==============================================================================

resource "aws_apigatewayv2_authorizer" "ws_lambda" {
  api_id           = aws_apigatewayv2_api.ws.id
  authorizer_type  = "REQUEST"
  authorizer_uri   = aws_lambda_function.ws_authorizer.invoke_arn
  identity_sources = ["route.request.querystring.token"]
  name             = "${local.name_prefix}-ws-authorizer"
}

# ==============================================================================
# Lambda Integrations
# ==============================================================================

# --- ws-handler integration (for $connect, $disconnect) ---
resource "aws_apigatewayv2_integration" "ws_handler" {
  api_id                 = aws_apigatewayv2_api.ws.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.ws_handler.invoke_arn
  content_handling_strategy = "CONVERT_TO_TEXT"
}

# --- stream-bridge integration (for audio_chunk, stop_capture) ---
resource "aws_apigatewayv2_integration" "ws_stream_bridge" {
  api_id                 = aws_apigatewayv2_api.ws.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.stream_bridge.invoke_arn
  content_handling_strategy = "CONVERT_TO_TEXT"
}

# ==============================================================================
# Routes
# ==============================================================================

# --- $connect (with Lambda authorizer) ---
resource "aws_apigatewayv2_route" "ws_connect" {
  api_id             = aws_apigatewayv2_api.ws.id
  route_key          = "$connect"
  target             = "integrations/${aws_apigatewayv2_integration.ws_handler.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.ws_lambda.id
}

resource "aws_apigatewayv2_route_response" "ws_connect" {
  api_id             = aws_apigatewayv2_api.ws.id
  route_id           = aws_apigatewayv2_route.ws_connect.id
  route_response_key = "$default"
}

# --- $disconnect ---
resource "aws_apigatewayv2_route" "ws_disconnect" {
  api_id    = aws_apigatewayv2_api.ws.id
  route_key = "$disconnect"
  target    = "integrations/${aws_apigatewayv2_integration.ws_handler.id}"
}

resource "aws_apigatewayv2_route_response" "ws_disconnect" {
  api_id             = aws_apigatewayv2_api.ws.id
  route_id           = aws_apigatewayv2_route.ws_disconnect.id
  route_response_key = "$default"
}

# --- audio_chunk ---
resource "aws_apigatewayv2_route" "ws_audio_chunk" {
  api_id    = aws_apigatewayv2_api.ws.id
  route_key = "audio_chunk"
  target    = "integrations/${aws_apigatewayv2_integration.ws_stream_bridge.id}"
}

resource "aws_apigatewayv2_route_response" "ws_audio_chunk" {
  api_id             = aws_apigatewayv2_api.ws.id
  route_id           = aws_apigatewayv2_route.ws_audio_chunk.id
  route_response_key = "$default"
}

# --- stop_capture ---
resource "aws_apigatewayv2_route" "ws_stop_capture" {
  api_id    = aws_apigatewayv2_api.ws.id
  route_key = "stop_capture"
  target    = "integrations/${aws_apigatewayv2_integration.ws_stream_bridge.id}"
}

resource "aws_apigatewayv2_route_response" "ws_stop_capture" {
  api_id             = aws_apigatewayv2_api.ws.id
  route_id           = aws_apigatewayv2_route.ws_stop_capture.id
  route_response_key = "$default"
}

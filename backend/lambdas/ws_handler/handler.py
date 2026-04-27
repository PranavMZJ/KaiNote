"""WebSocket handler Lambda for the Meeting Minutes application.

Routes WebSocket messages ($connect, $disconnect, audio_chunk, stop_capture)
and manages connection state in DynamoDB.

Resource name: Pranav-meeting-minutes-ws-handler

Environment variables:
    CONNECTIONS_TABLE          – DynamoDB table for WebSocket connections
    WS_API_ENDPOINT            – WebSocket API Management endpoint
    STREAM_BRIDGE_FUNCTION_NAME – Name/ARN of the streaming bridge Lambda

Requirements: 2.5, 2.6, 5.1, 5.2, 15.1
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_TTL_SECONDS = 24 * 60 * 60  # 24 hours


def _get_connections_table() -> str:
    return os.environ.get("CONNECTIONS_TABLE", "")


def _get_stream_bridge_function() -> str:
    return os.environ.get("STREAM_BRIDGE_FUNCTION_NAME", "")


def _get_ws_api_endpoint() -> str:
    return os.environ.get("WS_API_ENDPOINT", "")


# -------------------------------------------------------------------
# Route handlers
# -------------------------------------------------------------------


def handle_connect(
    connection_id: str,
    user_id: str,
    *,
    dynamodb_client: Any = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """Handle $connect: store connection metadata in DynamoDB.

    Stores connectionId, userId, a newly generated meetingId, connectedAt
    timestamp, and a TTL set to 24 hours from now.

    Args:
        connection_id: The WebSocket connection ID.
        user_id: The authenticated user's Cognito sub (from authorizer context).
        dynamodb_client: Optional boto3 DynamoDB client (for testing).
        table_name: Optional table name override (for testing).

    Returns:
        A dict with statusCode 200 and the meetingId.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_connections_table()

    meeting_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    connected_at = now.isoformat()
    ttl = int(now.timestamp()) + _TTL_SECONDS

    logger.info(
        "Storing connection: connectionId=%s userId=%s meetingId=%s",
        connection_id,
        user_id,
        meeting_id,
    )

    dynamodb_client.put_item(
        TableName=table_name,
        Item={
            "connectionId": {"S": connection_id},
            "userId": {"S": user_id},
            "meetingId": {"S": meeting_id},
            "connectedAt": {"S": connected_at},
            "ttl": {"N": str(ttl)},
        },
    )

    return {"statusCode": 200, "body": json.dumps({"meetingId": meeting_id})}


def handle_disconnect(
    connection_id: str,
    *,
    dynamodb_client: Any = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """Handle $disconnect: remove connection from DynamoDB.

    Args:
        connection_id: The WebSocket connection ID.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).
        table_name: Optional table name override (for testing).

    Returns:
        A dict with statusCode 200.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_connections_table()

    logger.info("Removing connection: connectionId=%s", connection_id)

    dynamodb_client.delete_item(
        TableName=table_name,
        Key={"connectionId": {"S": connection_id}},
    )

    return {"statusCode": 200, "body": "Disconnected"}


def handle_audio_chunk(
    connection_id: str,
    body: dict[str, Any],
    *,
    dynamodb_client: Any = None,
    lambda_client: Any = None,
    table_name: str | None = None,
    stream_bridge_function: str | None = None,
) -> dict[str, Any]:
    """Handle audio_chunk: forward audio data to the streaming bridge Lambda.

    Looks up the connection in DynamoDB to get userId and meetingId, then
    invokes the streaming bridge Lambda asynchronously with the audio payload.

    Args:
        connection_id: The WebSocket connection ID.
        body: The parsed message body containing audio data.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).
        lambda_client: Optional boto3 Lambda client (for testing).
        table_name: Optional table name override (for testing).
        stream_bridge_function: Optional function name override (for testing).

    Returns:
        A dict with statusCode 200.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if lambda_client is None:
        lambda_client = boto3.client("lambda", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_connections_table()
    if stream_bridge_function is None:
        stream_bridge_function = _get_stream_bridge_function()

    # Look up connection metadata
    response = dynamodb_client.get_item(
        TableName=table_name,
        Key={"connectionId": {"S": connection_id}},
    )
    item = response.get("Item")
    if not item:
        logger.warning("Connection not found: connectionId=%s", connection_id)
        return {"statusCode": 410, "body": "Connection not found"}

    user_id = item["userId"]["S"]
    meeting_id = item["meetingId"]["S"]

    payload = {
        "action": "audio_chunk",
        "connectionId": connection_id,
        "userId": user_id,
        "meetingId": meeting_id,
        "data": body.get("data", ""),
        "wsEndpoint": _get_ws_api_endpoint(),
    }

    logger.info(
        "Forwarding audio chunk: connectionId=%s meetingId=%s",
        connection_id,
        meeting_id,
    )

    lambda_client.invoke(
        FunctionName=stream_bridge_function,
        InvocationType="Event",  # async invocation
        Payload=json.dumps(payload).encode("utf-8"),
    )

    return {"statusCode": 200, "body": "Audio chunk forwarded"}


def handle_stop_capture(
    connection_id: str,
    *,
    dynamodb_client: Any = None,
    lambda_client: Any = None,
    table_name: str | None = None,
    stream_bridge_function: str | None = None,
) -> dict[str, Any]:
    """Handle stop_capture: signal the streaming bridge Lambda to stop.

    Looks up the connection in DynamoDB to get userId and meetingId, then
    invokes the streaming bridge Lambda asynchronously with a stop signal.

    Args:
        connection_id: The WebSocket connection ID.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).
        lambda_client: Optional boto3 Lambda client (for testing).
        table_name: Optional table name override (for testing).
        stream_bridge_function: Optional function name override (for testing).

    Returns:
        A dict with statusCode 200.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if lambda_client is None:
        lambda_client = boto3.client("lambda", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_connections_table()
    if stream_bridge_function is None:
        stream_bridge_function = _get_stream_bridge_function()

    # Look up connection metadata
    response = dynamodb_client.get_item(
        TableName=table_name,
        Key={"connectionId": {"S": connection_id}},
    )
    item = response.get("Item")
    if not item:
        logger.warning("Connection not found: connectionId=%s", connection_id)
        return {"statusCode": 410, "body": "Connection not found"}

    user_id = item["userId"]["S"]
    meeting_id = item["meetingId"]["S"]

    payload = {
        "action": "stop_capture",
        "connectionId": connection_id,
        "userId": user_id,
        "meetingId": meeting_id,
        "wsEndpoint": _get_ws_api_endpoint(),
    }

    logger.info(
        "Sending stop signal: connectionId=%s meetingId=%s",
        connection_id,
        meeting_id,
    )

    lambda_client.invoke(
        FunctionName=stream_bridge_function,
        InvocationType="Event",  # async invocation
        Payload=json.dumps(payload).encode("utf-8"),
    )

    return {"statusCode": 200, "body": "Stop signal sent"}


# -------------------------------------------------------------------
# Lambda entry point
# -------------------------------------------------------------------


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for WebSocket message routing.

    Routes messages based on ``event["requestContext"]["routeKey"]``:
    - ``$connect``: Store connection in DynamoDB
    - ``$disconnect``: Remove connection from DynamoDB
    - ``audio_chunk``: Forward audio data to streaming bridge Lambda
    - ``stop_capture``: Signal streaming bridge to stop

    Args:
        event: API Gateway WebSocket event.
        context: Lambda context (unused).

    Returns:
        A dict with statusCode and body.
    """
    request_context = event.get("requestContext", {})
    route_key = request_context.get("routeKey", "")
    connection_id = request_context.get("connectionId", "")

    logger.info(
        "WebSocket handler invoked: route=%s connectionId=%s",
        route_key,
        connection_id,
    )

    try:
        if route_key == "$connect":
            # userId is set by the Lambda authorizer in the context
            authorizer = request_context.get("authorizer", {})
            user_id = authorizer.get("userId", "")
            if not user_id:
                logger.warning("No userId in authorizer context")
                return {"statusCode": 401, "body": "Unauthorized"}
            return handle_connect(connection_id, user_id)

        if route_key == "$disconnect":
            return handle_disconnect(connection_id)

        if route_key == "audio_chunk":
            body = json.loads(event.get("body", "{}"))
            return handle_audio_chunk(connection_id, body)

        if route_key == "stop_capture":
            return handle_stop_capture(connection_id)

        logger.warning("Unknown route: %s", route_key)
        return {"statusCode": 400, "body": f"Unknown route: {route_key}"}

    except Exception:
        logger.exception(
            "WebSocket handler error: route=%s connectionId=%s",
            route_key,
            connection_id,
        )
        return {"statusCode": 500, "body": "Internal server error"}

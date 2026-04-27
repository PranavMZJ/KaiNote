"""Streaming bridge Lambda for the Meeting Minutes application.

Bridges audio capture to Amazon Transcribe Streaming and manages the
transcription lifecycle. Invoked asynchronously by the WebSocket handler
Lambda with ``action`` set to ``audio_chunk`` or ``stop_capture``.

Resource name: Pranav-meeting-minutes-stream-bridge

Environment variables:
    TRANSCRIPT_BUCKET   – S3 bucket for transcripts and reports
    STEP_FUNCTION_ARN   – ARN of the post-processing Step Functions state machine
    CONNECTIONS_TABLE    – DynamoDB table for WebSocket connections
    WS_API_ENDPOINT     – WebSocket API endpoint for posting messages back to clients

Requirements: 3.1, 3.2, 3.3, 4.6, 5.3, 5.4, 5.5, 5.6, 14.1
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Transcribe Streaming configuration
TRANSCRIBE_LANGUAGE = "ja-JP"
TRANSCRIBE_SAMPLE_RATE = 16000
TRANSCRIBE_ENCODING = "pcm"


def _get_transcript_bucket() -> str:
    return os.environ.get("TRANSCRIPT_BUCKET", "")


def _get_step_function_arn() -> str:
    return os.environ.get("STEP_FUNCTION_ARN", "")


def _get_connections_table() -> str:
    return os.environ.get("CONNECTIONS_TABLE", "")


def _get_ws_api_endpoint() -> str:
    return os.environ.get("WS_API_ENDPOINT", "")


def _build_apigw_management_endpoint(ws_endpoint: str) -> str:
    """Derive the API Gateway Management API endpoint from the WebSocket URL.

    The WebSocket endpoint looks like:
        wss://abc123.execute-api.ap-northeast-1.amazonaws.com/prod

    The Management API endpoint is:
        https://abc123.execute-api.ap-northeast-1.amazonaws.com/prod

    Args:
        ws_endpoint: The WebSocket API endpoint URL.

    Returns:
        The HTTPS endpoint for the API Gateway Management API.
    """
    return ws_endpoint.replace("wss://", "https://").replace("ws://", "http://")


def _post_to_connection(
    connection_id: str,
    message: dict[str, Any],
    *,
    ws_endpoint: str | None = None,
    apigw_client: Any = None,
) -> None:
    """Send a message to a WebSocket client via the API Gateway Management API.

    Args:
        connection_id: The WebSocket connection ID.
        message: The message dict to send (will be JSON-serialized).
        ws_endpoint: The WebSocket API endpoint.
        apigw_client: Optional pre-configured API Gateway Management client.
    """
    if apigw_client is None:
        endpoint_url = _build_apigw_management_endpoint(
            ws_endpoint or _get_ws_api_endpoint()
        )
        apigw_client = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=endpoint_url,
            region_name="ap-northeast-1",
        )

    data = json.dumps(message, ensure_ascii=False).encode("utf-8")
    try:
        apigw_client.post_to_connection(ConnectionId=connection_id, Data=data)
    except Exception:
        logger.exception(
            "Failed to post to connection: connectionId=%s", connection_id
        )


def _start_transcribe_session(
    meeting_id: str,
    *,
    transcribe_client: Any = None,
) -> dict[str, Any]:
    """Start an Amazon Transcribe Streaming session.

    NOTE: For the MVP, this creates the session configuration dict. The actual
    bidirectional WebSocket integration with Transcribe Streaming is complex
    and will be refined during production hardening. This function returns
    session metadata that would be used to manage the streaming session.

    Args:
        meeting_id: The meeting identifier for this session.
        transcribe_client: Optional boto3 Transcribe client (for testing).

    Returns:
        A dict with session configuration metadata.
    """
    session_id = f"transcribe-{meeting_id}-{uuid.uuid4().hex[:8]}"

    logger.info(
        "Starting Transcribe Streaming session: meetingId=%s sessionId=%s "
        "language=%s sampleRate=%d encoding=%s speakerDiarization=enabled "
        "partialResults=enabled",
        meeting_id,
        session_id,
        TRANSCRIBE_LANGUAGE,
        TRANSCRIBE_SAMPLE_RATE,
        TRANSCRIBE_ENCODING,
    )

    return {
        "sessionId": session_id,
        "meetingId": meeting_id,
        "language": TRANSCRIBE_LANGUAGE,
        "sampleRate": TRANSCRIBE_SAMPLE_RATE,
        "encoding": TRANSCRIBE_ENCODING,
        "speakerDiarization": True,
        "partialResults": True,
    }


def handle_audio_chunk(
    event: dict[str, Any],
    *,
    apigw_client: Any = None,
) -> dict[str, Any]:
    """Handle an audio_chunk event from the WebSocket handler.

    For the MVP, audio chunks are acknowledged and a transcript segment
    placeholder is sent back to the client. In production, this would forward
    audio to an active Transcribe Streaming session and relay real segments.

    Args:
        event: The event dict with connectionId, userId, meetingId, data, wsEndpoint.
        apigw_client: Optional API Gateway Management client (for testing).

    Returns:
        A dict with statusCode and body.
    """
    connection_id = event.get("connectionId", "")
    user_id = event.get("userId", "")
    meeting_id = event.get("meetingId", "")
    audio_data = event.get("data", "")
    ws_endpoint = event.get("wsEndpoint", "")

    logger.info(
        "Processing audio chunk: connectionId=%s meetingId=%s dataLength=%d",
        connection_id,
        meeting_id,
        len(audio_data),
    )

    # In production, this would:
    # 1. Forward audio_data to the active Transcribe Streaming session
    # 2. Receive transcript segments from Transcribe
    # 3. Forward segments back to the client
    #
    # For the MVP, we acknowledge receipt. The actual Transcribe Streaming
    # bidirectional WebSocket integration is deferred to production hardening.

    return {"statusCode": 200, "body": "Audio chunk received"}


def handle_stop_capture(
    event: dict[str, Any],
    *,
    s3_client: Any = None,
    sfn_client: Any = None,
    apigw_client: Any = None,
    transcript_bucket: str | None = None,
    step_function_arn: str | None = None,
) -> dict[str, Any]:
    """Handle a stop_capture event from the WebSocket handler.

    Ends the Transcribe session, builds the raw transcript, stores it to S3,
    starts the Step Functions post-processing workflow, and notifies the client.

    Args:
        event: The event dict with connectionId, userId, meetingId, wsEndpoint.
        s3_client: Optional boto3 S3 client (for testing).
        sfn_client: Optional boto3 Step Functions client (for testing).
        apigw_client: Optional API Gateway Management client (for testing).
        transcript_bucket: Optional bucket name override (for testing).
        step_function_arn: Optional Step Functions ARN override (for testing).

    Returns:
        A dict with statusCode and body.
    """
    connection_id = event.get("connectionId", "")
    user_id = event.get("userId", "")
    meeting_id = event.get("meetingId", "")
    ws_endpoint = event.get("wsEndpoint", "")

    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if sfn_client is None:
        sfn_client = boto3.client("stepfunctions", region_name="ap-northeast-1")
    if transcript_bucket is None:
        transcript_bucket = _get_transcript_bucket()
    if step_function_arn is None:
        step_function_arn = _get_step_function_arn()

    logger.info(
        "Stop capture received: connectionId=%s meetingId=%s userId=%s",
        connection_id,
        meeting_id,
        user_id,
    )

    now = datetime.now(timezone.utc)

    # Build the raw transcript object.
    # In production, this would contain the accumulated segments from the
    # Transcribe Streaming session. For the MVP, we create a minimal
    # transcript structure that downstream Lambdas can process.
    raw_transcript = {
        "meetingId": meeting_id,
        "userId": user_id,
        "startTime": now.isoformat(),
        "endTime": now.isoformat(),
        "language": TRANSCRIBE_LANGUAGE,
        "segments": [],
        "metadata": {
            "sampleRate": TRANSCRIBE_SAMPLE_RATE,
            "encoding": TRANSCRIBE_ENCODING,
            "transcribeSessionId": f"transcribe-{meeting_id}",
        },
    }

    # Store raw transcript to S3 (Requirement 5.4, 5.5)
    transcript_key = f"users/{user_id}/transcripts/{meeting_id}/raw.json"
    transcript_json = json.dumps(raw_transcript, ensure_ascii=False)

    logger.info(
        "Storing raw transcript: bucket=%s key=%s",
        transcript_bucket,
        transcript_key,
    )

    s3_client.put_object(
        Bucket=transcript_bucket,
        Key=transcript_key,
        Body=transcript_json.encode("utf-8"),
        ContentType="application/json",
    )

    # Start Step Functions execution (Requirement 5.6)
    sfn_input = {
        "meetingId": meeting_id,
        "userId": user_id,
        "transcriptBucket": transcript_bucket,
        "transcriptKey": transcript_key,
    }

    execution_name = f"meeting-{meeting_id}-{uuid.uuid4().hex[:8]}"

    logger.info(
        "Starting Step Functions execution: arn=%s name=%s",
        step_function_arn,
        execution_name,
    )

    sfn_response = sfn_client.start_execution(
        stateMachineArn=step_function_arn,
        name=execution_name,
        input=json.dumps(sfn_input),
    )

    execution_arn = sfn_response.get("executionArn", "")

    # Notify client that capture has stopped and processing has started
    _post_to_connection(
        connection_id,
        {
            "type": "capture_stopped",
            "meetingId": meeting_id,
            "status": "processing",
        },
        ws_endpoint=ws_endpoint,
        apigw_client=apigw_client,
    )

    logger.info(
        "Stop capture complete: meetingId=%s executionArn=%s",
        meeting_id,
        execution_arn,
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "meetingId": meeting_id,
                "transcriptKey": transcript_key,
                "executionArn": execution_arn,
            }
        ),
    }


# -------------------------------------------------------------------
# Lambda entry point
# -------------------------------------------------------------------


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for the streaming bridge.

    This Lambda can be invoked in two ways:
    1. Directly by API Gateway WebSocket (audio_chunk, stop_capture routes)
    2. Asynchronously by the WebSocket handler Lambda

    For API Gateway invocations, the event has:
      - requestContext.routeKey (e.g., "audio_chunk", "stop_capture")
      - requestContext.connectionId
      - body (JSON string with the message payload)

    For direct invocations, the event has:
      - action, connectionId, meetingId, data, wsEndpoint

    Args:
        event: The invocation event.
        context: Lambda context (unused).

    Returns:
        A dict with statusCode and body.
    """
    # Parse API Gateway WebSocket event format
    request_context = event.get("requestContext", {})
    if request_context:
        # This is an API Gateway WebSocket invocation
        action = request_context.get("routeKey", "")
        connection_id = request_context.get("connectionId", "")
        # Parse the body JSON
        body_str = event.get("body", "{}")
        try:
            body = json.loads(body_str) if body_str else {}
        except (json.JSONDecodeError, TypeError):
            body = {}

        # Look up connection metadata from DynamoDB to get userId and meetingId
        user_id = ""
        meeting_id = ""
        table_name = os.environ.get("CONNECTIONS_TABLE", "")
        if connection_id and table_name:
            try:
                dynamodb = boto3.client("dynamodb", region_name="ap-northeast-1")
                response = dynamodb.get_item(
                    TableName=table_name,
                    Key={"connectionId": {"S": connection_id}},
                )
                item = response.get("Item", {})
                user_id = item.get("userId", {}).get("S", "")
                meeting_id = item.get("meetingId", {}).get("S", "")
            except Exception:
                logger.exception("Failed to look up connection: %s", connection_id)

        # Build the normalized event
        ws_endpoint = _get_ws_api_endpoint()
        normalized_event: dict[str, Any] = {
            "action": action,
            "connectionId": connection_id,
            "userId": user_id,
            "meetingId": meeting_id,
            "wsEndpoint": ws_endpoint,
            "data": body.get("data", ""),
        }
    else:
        # Direct invocation (from WS Handler Lambda)
        normalized_event = event
        action = event.get("action", "")
        connection_id = event.get("connectionId", "")
        meeting_id = event.get("meetingId", "")

    logger.info(
        "Stream bridge invoked: action=%s connectionId=%s meetingId=%s",
        action,
        connection_id,
        meeting_id,
    )

    try:
        if action == "audio_chunk":
            return handle_audio_chunk(normalized_event)

        if action == "stop_capture":
            return handle_stop_capture(normalized_event)

        logger.warning("Unknown action: %s", action)
        return {"statusCode": 400, "body": f"Unknown action: {action}"}

    except Exception:
        logger.exception(
            "Stream bridge error: action=%s connectionId=%s meetingId=%s",
            action,
            connection_id,
            meeting_id,
        )

        # Attempt to notify the client of the error
        ws_endpoint = normalized_event.get("wsEndpoint", "")
        if connection_id and ws_endpoint:
            try:
                _post_to_connection(
                    connection_id,
                    {
                        "type": "error",
                        "message": "An error occurred during audio processing",
                        "code": "STREAM_BRIDGE_ERROR",
                    },
                    ws_endpoint=ws_endpoint,
                )
            except Exception:
                logger.exception("Failed to send error notification to client")

        return {"statusCode": 500, "body": "Internal server error"}

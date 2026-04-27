"""Unit tests for the streaming bridge Lambda.

Tests cover:
- audio_chunk action acknowledges receipt
- stop_capture stores raw transcript to S3
- stop_capture starts Step Functions execution with correct input
- stop_capture notifies client via WebSocket Management API
- Unknown action returns 400
- Error handling sends error notification to client
- Transcribe session configuration is correct
- API Gateway Management endpoint derivation

Requirements: 3.1, 3.2, 3.3, 4.6, 5.3, 5.4, 5.5, 5.6, 14.1
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from backend.lambdas.stream_bridge.handler import (
    _build_apigw_management_endpoint,
    _post_to_connection,
    _start_transcribe_session,
    handle_audio_chunk,
    handle_stop_capture,
    handler,
)

TRANSCRIPT_BUCKET = "pranav-meeting-minutes-data"
STEP_FUNCTION_ARN = (
    "arn:aws:states:ap-northeast-1:681561127010:"
    "stateMachine:Pranav-meeting-minutes-workflow"
)
CONNECTIONS_TABLE = "Pranav-meeting-minutes-connections"
WS_ENDPOINT = "wss://abc123.execute-api.ap-northeast-1.amazonaws.com/prod"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("TRANSCRIPT_BUCKET", TRANSCRIPT_BUCKET)
    monkeypatch.setenv("STEP_FUNCTION_ARN", STEP_FUNCTION_ARN)
    monkeypatch.setenv("CONNECTIONS_TABLE", CONNECTIONS_TABLE)
    monkeypatch.setenv("WS_API_ENDPOINT", WS_ENDPOINT)


# -------------------------------------------------------------------
# Helper to build stream bridge events
# -------------------------------------------------------------------


def _stream_event(
    action: str,
    connection_id: str = "conn-sb-001",
    user_id: str = "user-sb-001",
    meeting_id: str = "meeting-sb-001",
    data: str = "",
    ws_endpoint: str = WS_ENDPOINT,
) -> dict[str, Any]:
    """Build a minimal streaming bridge invocation event."""
    event: dict[str, Any] = {
        "action": action,
        "connectionId": connection_id,
        "userId": user_id,
        "meetingId": meeting_id,
        "wsEndpoint": ws_endpoint,
    }
    if data:
        event["data"] = data
    return event


# -------------------------------------------------------------------
# _build_apigw_management_endpoint tests
# -------------------------------------------------------------------


class TestBuildApigwManagementEndpoint:
    def test_converts_wss_to_https(self):
        result = _build_apigw_management_endpoint(
            "wss://abc123.execute-api.ap-northeast-1.amazonaws.com/prod"
        )
        assert result == "https://abc123.execute-api.ap-northeast-1.amazonaws.com/prod"

    def test_converts_ws_to_http(self):
        result = _build_apigw_management_endpoint(
            "ws://localhost:3001/local"
        )
        assert result == "http://localhost:3001/local"


# -------------------------------------------------------------------
# _start_transcribe_session tests
# -------------------------------------------------------------------


class TestStartTranscribeSession:
    def test_returns_session_config(self):
        session = _start_transcribe_session("meeting-123")
        assert session["meetingId"] == "meeting-123"
        assert session["language"] == "ja-JP"
        assert session["sampleRate"] == 16000
        assert session["encoding"] == "pcm"
        assert session["speakerDiarization"] is True
        assert session["partialResults"] is True
        assert session["sessionId"].startswith("transcribe-meeting-123-")

    def test_generates_unique_session_ids(self):
        s1 = _start_transcribe_session("meeting-a")
        s2 = _start_transcribe_session("meeting-a")
        assert s1["sessionId"] != s2["sessionId"]


# -------------------------------------------------------------------
# handle_audio_chunk tests
# -------------------------------------------------------------------


class TestHandleAudioChunk:
    def test_acknowledges_audio_chunk(self):
        event = _stream_event("audio_chunk", data="base64audiodata==")
        result = handle_audio_chunk(event)
        assert result["statusCode"] == 200

    def test_handles_empty_audio_data(self):
        event = _stream_event("audio_chunk", data="")
        result = handle_audio_chunk(event)
        assert result["statusCode"] == 200


# -------------------------------------------------------------------
# handle_stop_capture tests
# -------------------------------------------------------------------


class TestHandleStopCapture:
    def test_stores_transcript_to_s3(self):
        mock_s3 = MagicMock()
        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:ap-northeast-1:123:execution:test"
        }
        mock_apigw = MagicMock()

        event = _stream_event("stop_capture")
        result = handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
        )

        assert result["statusCode"] == 200

        # Verify S3 put_object was called with correct params
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == TRANSCRIPT_BUCKET
        assert call_kwargs["Key"] == "users/user-sb-001/transcripts/meeting-sb-001/raw.json"
        assert call_kwargs["ContentType"] == "application/json"

        # Verify the stored transcript structure
        stored_body = call_kwargs["Body"].decode("utf-8")
        transcript = json.loads(stored_body)
        assert transcript["meetingId"] == "meeting-sb-001"
        assert transcript["userId"] == "user-sb-001"
        assert transcript["language"] == "ja-JP"
        assert isinstance(transcript["segments"], list)
        assert transcript["metadata"]["sampleRate"] == 16000
        assert transcript["metadata"]["encoding"] == "pcm"

    def test_starts_step_functions_execution(self):
        mock_s3 = MagicMock()
        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:ap-northeast-1:123:execution:test"
        }
        mock_apigw = MagicMock()

        event = _stream_event("stop_capture")
        handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
        )

        # Verify Step Functions was started
        mock_sfn.start_execution.assert_called_once()
        call_kwargs = mock_sfn.start_execution.call_args[1]
        assert call_kwargs["stateMachineArn"] == STEP_FUNCTION_ARN
        assert call_kwargs["name"].startswith("meeting-meeting-sb-001-")

        sfn_input = json.loads(call_kwargs["input"])
        assert sfn_input["meetingId"] == "meeting-sb-001"
        assert sfn_input["userId"] == "user-sb-001"
        assert sfn_input["transcriptBucket"] == TRANSCRIPT_BUCKET
        assert sfn_input["transcriptKey"] == "users/user-sb-001/transcripts/meeting-sb-001/raw.json"

    def test_notifies_client_via_websocket(self):
        mock_s3 = MagicMock()
        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:ap-northeast-1:123:execution:test"
        }
        mock_apigw = MagicMock()

        event = _stream_event("stop_capture")
        handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
        )

        # Verify client was notified
        mock_apigw.post_to_connection.assert_called_once()
        call_kwargs = mock_apigw.post_to_connection.call_args[1]
        assert call_kwargs["ConnectionId"] == "conn-sb-001"

        message = json.loads(call_kwargs["Data"].decode("utf-8"))
        assert message["type"] == "capture_stopped"
        assert message["meetingId"] == "meeting-sb-001"
        assert message["status"] == "processing"

    def test_returns_transcript_key_and_execution_arn(self):
        mock_s3 = MagicMock()
        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:ap-northeast-1:123:execution:my-exec"
        }
        mock_apigw = MagicMock()

        event = _stream_event("stop_capture")
        result = handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
        )

        body = json.loads(result["body"])
        assert body["meetingId"] == "meeting-sb-001"
        assert body["transcriptKey"] == "users/user-sb-001/transcripts/meeting-sb-001/raw.json"
        assert body["executionArn"] == "arn:aws:states:ap-northeast-1:123:execution:my-exec"

    def test_stores_transcript_before_starting_workflow(self):
        """Verify S3 put happens before Step Functions start (Req 5.5)."""
        call_order = []

        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = lambda **kw: call_order.append("s3_put")

        mock_sfn = MagicMock()
        mock_sfn.start_execution.side_effect = lambda **kw: (
            call_order.append("sfn_start"),
            {"executionArn": "arn:test"},
        )[1]

        mock_apigw = MagicMock()

        event = _stream_event("stop_capture")
        handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
        )

        assert call_order == ["s3_put", "sfn_start"]


# -------------------------------------------------------------------
# handler (routing) tests
# -------------------------------------------------------------------


class TestHandler:
    def test_routes_audio_chunk(self):
        event = _stream_event("audio_chunk", data="base64data==")
        result = handler(event, None)
        assert result["statusCode"] == 200

    def test_routes_stop_capture(self):
        mock_s3 = MagicMock()
        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:ap-northeast-1:123:execution:test"
        }
        mock_apigw = MagicMock()

        event = _stream_event("stop_capture")

        with patch("backend.lambdas.stream_bridge.handler.boto3.client") as mock_boto:
            # Return different mocks for different service calls
            def client_factory(service, **kwargs):
                if service == "s3":
                    return mock_s3
                if service == "stepfunctions":
                    return mock_sfn
                if service == "apigatewaymanagementapi":
                    return mock_apigw
                return MagicMock()

            mock_boto.side_effect = client_factory
            result = handler(event, None)

        assert result["statusCode"] == 200

    def test_unknown_action_returns_400(self):
        event = _stream_event("unknown_action")
        result = handler(event, None)
        assert result["statusCode"] == 400

    def test_error_sends_notification_to_client(self):
        """When an exception occurs, the handler should attempt to notify the client."""
        mock_apigw = MagicMock()

        event = _stream_event("stop_capture")

        with patch("backend.lambdas.stream_bridge.handler.boto3.client") as mock_boto:
            # Make S3 client raise an exception
            mock_s3 = MagicMock()
            mock_s3.put_object.side_effect = Exception("S3 error")

            def client_factory(service, **kwargs):
                if service == "s3":
                    return mock_s3
                if service == "apigatewaymanagementapi":
                    return mock_apigw
                return MagicMock()

            mock_boto.side_effect = client_factory
            result = handler(event, None)

        assert result["statusCode"] == 500

        # Verify error notification was attempted
        mock_apigw.post_to_connection.assert_called_once()
        call_kwargs = mock_apigw.post_to_connection.call_args[1]
        message = json.loads(call_kwargs["Data"].decode("utf-8"))
        assert message["type"] == "error"
        assert message["code"] == "STREAM_BRIDGE_ERROR"

    def test_missing_action_returns_400(self):
        event = {"connectionId": "conn-1", "meetingId": "m-1", "wsEndpoint": WS_ENDPOINT}
        result = handler(event, None)
        assert result["statusCode"] == 400

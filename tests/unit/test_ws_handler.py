"""Unit tests for the WebSocket handler Lambda.

Tests cover:
- $connect stores connection in DynamoDB with correct attributes
- $disconnect removes connection from DynamoDB
- audio_chunk looks up connection and invokes stream bridge Lambda async
- stop_capture looks up connection and invokes stream bridge Lambda async
- Unknown route returns 400
- Missing userId in authorizer context returns 401

Requirements: 2.5, 2.6, 5.1, 5.2, 15.1
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from backend.lambdas.ws_handler.handler import (
    handle_audio_chunk,
    handle_connect,
    handle_disconnect,
    handle_stop_capture,
    handler,
)

TABLE_NAME = "Pranav-meeting-minutes-connections"
STREAM_BRIDGE_FUNCTION = "Pranav-meeting-minutes-stream-bridge"
WS_ENDPOINT = "https://abc123.execute-api.ap-northeast-1.amazonaws.com/prod"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("CONNECTIONS_TABLE", TABLE_NAME)
    monkeypatch.setenv("STREAM_BRIDGE_FUNCTION_NAME", STREAM_BRIDGE_FUNCTION)
    monkeypatch.setenv("WS_API_ENDPOINT", WS_ENDPOINT)


@pytest.fixture()
def dynamodb_table():
    """Create a mocked DynamoDB connections table."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="ap-northeast-1")
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "connectionId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "connectionId", "AttributeType": "S"},
                {"AttributeName": "userId", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "userId-index",
                    "KeySchema": [{"AttributeName": "userId", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield client


# -------------------------------------------------------------------
# Helper to build WebSocket events
# -------------------------------------------------------------------


def _ws_event(
    route_key: str,
    connection_id: str = "conn-abc-123",
    user_id: str | None = None,
    body: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a minimal API Gateway WebSocket event."""
    request_context: Dict[str, Any] = {
        "routeKey": route_key,
        "connectionId": connection_id,
    }
    if user_id is not None:
        request_context["authorizer"] = {"userId": user_id}

    event: Dict[str, Any] = {"requestContext": request_context}
    if body is not None:
        event["body"] = json.dumps(body)
    return event


# -------------------------------------------------------------------
# $connect tests
# -------------------------------------------------------------------


class TestHandleConnect:
    def test_stores_connection_in_dynamodb(self, dynamodb_table):
        result = handle_connect(
            "conn-001",
            "user-xyz",
            dynamodb_client=dynamodb_table,
            table_name=TABLE_NAME,
        )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "meetingId" in body

        # Verify item was stored
        response = dynamodb_table.get_item(
            TableName=TABLE_NAME,
            Key={"connectionId": {"S": "conn-001"}},
        )
        item = response["Item"]
        assert item["connectionId"]["S"] == "conn-001"
        assert item["userId"]["S"] == "user-xyz"
        assert "meetingId" in item
        assert "connectedAt" in item
        assert "ttl" in item

    def test_ttl_is_24_hours_from_now(self, dynamodb_table):
        import time

        before = int(time.time())
        handle_connect(
            "conn-002",
            "user-abc",
            dynamodb_client=dynamodb_table,
            table_name=TABLE_NAME,
        )
        after = int(time.time())

        response = dynamodb_table.get_item(
            TableName=TABLE_NAME,
            Key={"connectionId": {"S": "conn-002"}},
        )
        ttl = int(response["Item"]["ttl"]["N"])
        expected_min = before + 24 * 60 * 60
        expected_max = after + 24 * 60 * 60
        assert expected_min <= ttl <= expected_max

    def test_generates_unique_meeting_ids(self, dynamodb_table):
        r1 = handle_connect("conn-a", "user-1", dynamodb_client=dynamodb_table, table_name=TABLE_NAME)
        r2 = handle_connect("conn-b", "user-1", dynamodb_client=dynamodb_table, table_name=TABLE_NAME)
        m1 = json.loads(r1["body"])["meetingId"]
        m2 = json.loads(r2["body"])["meetingId"]
        assert m1 != m2


# -------------------------------------------------------------------
# $disconnect tests
# -------------------------------------------------------------------


class TestHandleDisconnect:
    def test_removes_connection_from_dynamodb(self, dynamodb_table):
        # First store a connection
        handle_connect("conn-del", "user-1", dynamodb_client=dynamodb_table, table_name=TABLE_NAME)

        # Verify it exists
        resp = dynamodb_table.get_item(
            TableName=TABLE_NAME,
            Key={"connectionId": {"S": "conn-del"}},
        )
        assert "Item" in resp

        # Disconnect
        result = handle_disconnect("conn-del", dynamodb_client=dynamodb_table, table_name=TABLE_NAME)
        assert result["statusCode"] == 200

        # Verify it's gone
        resp = dynamodb_table.get_item(
            TableName=TABLE_NAME,
            Key={"connectionId": {"S": "conn-del"}},
        )
        assert "Item" not in resp

    def test_disconnect_nonexistent_connection_succeeds(self, dynamodb_table):
        """Disconnecting a connection that doesn't exist should not error."""
        result = handle_disconnect("conn-ghost", dynamodb_client=dynamodb_table, table_name=TABLE_NAME)
        assert result["statusCode"] == 200


# -------------------------------------------------------------------
# audio_chunk tests
# -------------------------------------------------------------------


class TestHandleAudioChunk:
    def test_forwards_audio_to_stream_bridge(self, dynamodb_table):
        # Store a connection first
        handle_connect("conn-audio", "user-a", dynamodb_client=dynamodb_table, table_name=TABLE_NAME)

        mock_lambda = MagicMock()
        result = handle_audio_chunk(
            "conn-audio",
            {"data": "base64audiodata=="},
            dynamodb_client=dynamodb_table,
            lambda_client=mock_lambda,
            table_name=TABLE_NAME,
            stream_bridge_function=STREAM_BRIDGE_FUNCTION,
        )

        assert result["statusCode"] == 200
        mock_lambda.invoke.assert_called_once()
        call_kwargs = mock_lambda.invoke.call_args[1]
        assert call_kwargs["FunctionName"] == STREAM_BRIDGE_FUNCTION
        assert call_kwargs["InvocationType"] == "Event"

        payload = json.loads(call_kwargs["Payload"])
        assert payload["action"] == "audio_chunk"
        assert payload["connectionId"] == "conn-audio"
        assert payload["userId"] == "user-a"
        assert payload["data"] == "base64audiodata=="

    def test_returns_410_for_missing_connection(self, dynamodb_table):
        mock_lambda = MagicMock()
        result = handle_audio_chunk(
            "conn-missing",
            {"data": "abc"},
            dynamodb_client=dynamodb_table,
            lambda_client=mock_lambda,
            table_name=TABLE_NAME,
            stream_bridge_function=STREAM_BRIDGE_FUNCTION,
        )
        assert result["statusCode"] == 410
        mock_lambda.invoke.assert_not_called()


# -------------------------------------------------------------------
# stop_capture tests
# -------------------------------------------------------------------


class TestHandleStopCapture:
    def test_sends_stop_signal_to_stream_bridge(self, dynamodb_table):
        handle_connect("conn-stop", "user-b", dynamodb_client=dynamodb_table, table_name=TABLE_NAME)

        mock_lambda = MagicMock()
        result = handle_stop_capture(
            "conn-stop",
            dynamodb_client=dynamodb_table,
            lambda_client=mock_lambda,
            table_name=TABLE_NAME,
            stream_bridge_function=STREAM_BRIDGE_FUNCTION,
        )

        assert result["statusCode"] == 200
        mock_lambda.invoke.assert_called_once()
        call_kwargs = mock_lambda.invoke.call_args[1]
        assert call_kwargs["FunctionName"] == STREAM_BRIDGE_FUNCTION
        assert call_kwargs["InvocationType"] == "Event"

        payload = json.loads(call_kwargs["Payload"])
        assert payload["action"] == "stop_capture"
        assert payload["connectionId"] == "conn-stop"
        assert payload["userId"] == "user-b"

    def test_returns_410_for_missing_connection(self, dynamodb_table):
        mock_lambda = MagicMock()
        result = handle_stop_capture(
            "conn-missing",
            dynamodb_client=dynamodb_table,
            lambda_client=mock_lambda,
            table_name=TABLE_NAME,
            stream_bridge_function=STREAM_BRIDGE_FUNCTION,
        )
        assert result["statusCode"] == 410
        mock_lambda.invoke.assert_not_called()


# -------------------------------------------------------------------
# handler (routing) tests
# -------------------------------------------------------------------


class TestHandler:
    def test_connect_route(self, dynamodb_table):
        event = _ws_event("$connect", connection_id="conn-h1", user_id="user-h1")
        with patch(
            "backend.lambdas.ws_handler.handler.boto3.client",
            return_value=dynamodb_table,
        ):
            result = handler(event, None)
        assert result["statusCode"] == 200

    def test_connect_without_user_id_returns_401(self):
        event = _ws_event("$connect", connection_id="conn-h2")
        # No authorizer context → no userId
        result = handler(event, None)
        assert result["statusCode"] == 401

    def test_disconnect_route(self, dynamodb_table):
        # Store a connection first
        handle_connect("conn-h3", "user-h3", dynamodb_client=dynamodb_table, table_name=TABLE_NAME)

        event = _ws_event("$disconnect", connection_id="conn-h3")
        with patch(
            "backend.lambdas.ws_handler.handler.boto3.client",
            return_value=dynamodb_table,
        ):
            result = handler(event, None)
        assert result["statusCode"] == 200

    def test_unknown_route_returns_400(self):
        event = _ws_event("unknown_action", connection_id="conn-h4")
        result = handler(event, None)
        assert result["statusCode"] == 400

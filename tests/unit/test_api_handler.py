"""Unit tests for the REST API Lambda handler.

Tests cover all six endpoints with moto-mocked S3 and stubbed Step Functions.

Requirements: 9.1, 10.4, 11.2, 12.4, 13.1, 13.3
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from backend.lambdas.api.handler import (
    get_meeting,
    get_report,
    get_report_download,
    handler,
    list_meetings,
    put_report,
    retry_meeting,
)
from backend.utils.s3_keys import report_key, status_key

DATA_BUCKET = "test-data-bucket"
REGION = "ap-northeast-1"
STEP_FUNCTION_ARN = "arn:aws:states:ap-northeast-1:123456789012:stateMachine:test-workflow"


def _create_bucket(s3_client) -> None:
    s3_client.create_bucket(
        Bucket=DATA_BUCKET,
        CreateBucketConfiguration={"LocationConstraint": REGION},
    )


def _put_s3_json(s3_client, key: str, data: dict[str, Any]) -> None:
    s3_client.put_object(
        Bucket=DATA_BUCKET,
        Key=key,
        Body=json.dumps(data).encode("utf-8"),
        ContentType="application/json",
    )


def _read_s3_json(s3_client, key: str) -> dict[str, Any]:
    response = s3_client.get_object(Bucket=DATA_BUCKET, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def _status_obj(meeting_id: str, user_id: str, status: str = "completed", **kwargs) -> dict[str, Any]:
    base = {
        "meetingId": meeting_id,
        "userId": user_id,
        "status": status,
        "createdAt": "2024-01-15T10:00:00Z",
        "updatedAt": "2024-01-15T11:00:00Z",
    }
    base.update(kwargs)
    return base


def _sample_report() -> dict[str, Any]:
    return {
        "schema_version": "v1",
        "meeting_title": "Sprint Planning",
        "meeting_datetime": "2024-01-15T10:00:00Z",
        "participants": ["Alice", "Bob"],
        "summary": "Discussed sprint goals.",
        "agenda_items": ["Sprint backlog review"],
        "key_discussion_points": ["Velocity trends"],
        "decisions": [],
        "action_items": [],
        "risks_blockers": [],
        "open_questions": [],
        "follow_up_needed": True,
    }


def _api_event(
    method: str,
    resource: str,
    user_id: str = "user-1",
    meeting_id: str | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    """Build a minimal API Gateway proxy event."""
    event: dict[str, Any] = {
        "httpMethod": method,
        "resource": resource,
        "requestContext": {
            "authorizer": {
                "claims": {"sub": user_id},
            },
        },
        "pathParameters": {},
        "body": body,
    }
    if meeting_id:
        event["pathParameters"] = {"meetingId": meeting_id}
    return event


# ---------------------------------------------------------------------------
# GET /meetings
# ---------------------------------------------------------------------------


class TestListMeetings:
    @mock_aws
    def test_returns_only_user_meetings(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        # Two meetings for user-1, one for user-2
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))
        _put_s3_json(s3, status_key("m-2"), _status_obj("m-2", "user-1"))
        _put_s3_json(s3, status_key("m-3"), _status_obj("m-3", "user-2"))

        result = list_meetings("user-1", s3_client=s3, bucket=DATA_BUCKET)
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert len(body["meetings"]) == 2
        meeting_ids = {m["meetingId"] for m in body["meetings"]}
        assert meeting_ids == {"m-1", "m-2"}

    @mock_aws
    def test_returns_empty_list_when_no_meetings(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        result = list_meetings("user-1", s3_client=s3, bucket=DATA_BUCKET)
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert body["meetings"] == []


# ---------------------------------------------------------------------------
# GET /meetings/{meetingId}
# ---------------------------------------------------------------------------


class TestGetMeeting:
    @mock_aws
    def test_returns_meeting_status(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1", status="processing"))

        result = get_meeting("user-1", "m-1", s3_client=s3, bucket=DATA_BUCKET)
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert body["meetingId"] == "m-1"
        assert body["status"] == "processing"

    @mock_aws
    def test_returns_404_for_missing_meeting(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        result = get_meeting("user-1", "nonexistent", s3_client=s3, bucket=DATA_BUCKET)
        assert result["statusCode"] == 404

    @mock_aws
    def test_returns_403_for_other_users_meeting(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-2"))

        result = get_meeting("user-1", "m-1", s3_client=s3, bucket=DATA_BUCKET)
        assert result["statusCode"] == 403


# ---------------------------------------------------------------------------
# GET /meetings/{meetingId}/report
# ---------------------------------------------------------------------------


class TestGetReport:
    @mock_aws
    def test_returns_original_report(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))
        _put_s3_json(s3, report_key("user-1", "m-1"), _sample_report())

        result = get_report("user-1", "m-1", s3_client=s3, bucket=DATA_BUCKET)
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert body["version"] == "original"
        assert body["report"]["meeting_title"] == "Sprint Planning"

    @mock_aws
    def test_returns_edited_report_when_available(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))
        _put_s3_json(s3, report_key("user-1", "m-1"), _sample_report())

        edited = _sample_report()
        edited["meeting_title"] = "Edited Sprint Planning"
        _put_s3_json(s3, report_key("user-1", "m-1", edited=True), edited)

        result = get_report("user-1", "m-1", s3_client=s3, bucket=DATA_BUCKET)
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert body["version"] == "edited"
        assert body["report"]["meeting_title"] == "Edited Sprint Planning"

    @mock_aws
    def test_returns_404_when_no_report(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))

        result = get_report("user-1", "m-1", s3_client=s3, bucket=DATA_BUCKET)
        assert result["statusCode"] == 404

    @mock_aws
    def test_returns_403_for_other_users_report(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-2"))

        result = get_report("user-1", "m-1", s3_client=s3, bucket=DATA_BUCKET)
        assert result["statusCode"] == 403


# ---------------------------------------------------------------------------
# PUT /meetings/{meetingId}/report
# ---------------------------------------------------------------------------


class TestPutReport:
    @mock_aws
    def test_saves_edited_report(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))

        edited = _sample_report()
        edited["meeting_title"] = "Updated Title"
        body = json.dumps(edited)

        result = put_report("user-1", "m-1", body, s3_client=s3, bucket=DATA_BUCKET)
        resp_body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert resp_body["message"] == "Report saved"

        # Verify stored as minutes_edited.json
        stored = _read_s3_json(s3, report_key("user-1", "m-1", edited=True))
        assert stored["meeting_title"] == "Updated Title"

    @mock_aws
    def test_preserves_original_report(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))
        _put_s3_json(s3, report_key("user-1", "m-1"), _sample_report())

        edited = _sample_report()
        edited["meeting_title"] = "Edited"
        put_report("user-1", "m-1", json.dumps(edited), s3_client=s3, bucket=DATA_BUCKET)

        # Original is untouched
        original = _read_s3_json(s3, report_key("user-1", "m-1"))
        assert original["meeting_title"] == "Sprint Planning"

    @mock_aws
    def test_returns_400_for_empty_body(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))

        result = put_report("user-1", "m-1", None, s3_client=s3, bucket=DATA_BUCKET)
        assert result["statusCode"] == 400

    @mock_aws
    def test_returns_400_for_invalid_json(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))

        result = put_report("user-1", "m-1", "not-json{", s3_client=s3, bucket=DATA_BUCKET)
        assert result["statusCode"] == 400


# ---------------------------------------------------------------------------
# GET /meetings/{meetingId}/report/download
# ---------------------------------------------------------------------------


class TestGetReportDownload:
    @mock_aws
    def test_returns_presigned_url_for_original(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))
        _put_s3_json(s3, report_key("user-1", "m-1"), _sample_report())

        result = get_report_download("user-1", "m-1", s3_client=s3, bucket=DATA_BUCKET)
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert "downloadUrl" in body
        assert body["key"] == report_key("user-1", "m-1")

    @mock_aws
    def test_prefers_edited_version(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))
        _put_s3_json(s3, report_key("user-1", "m-1"), _sample_report())
        _put_s3_json(s3, report_key("user-1", "m-1", edited=True), _sample_report())

        result = get_report_download("user-1", "m-1", s3_client=s3, bucket=DATA_BUCKET)
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert body["key"] == report_key("user-1", "m-1", edited=True)

    @mock_aws
    def test_returns_404_when_no_report(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))

        result = get_report_download("user-1", "m-1", s3_client=s3, bucket=DATA_BUCKET)
        assert result["statusCode"] == 404


# ---------------------------------------------------------------------------
# POST /meetings/{meetingId}/retry
# ---------------------------------------------------------------------------


class TestRetryMeeting:
    @mock_aws
    def test_starts_retry_for_failed_meeting(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(
            s3,
            status_key("m-1"),
            _status_obj(
                "m-1", "user-1", status="failed",
                transcriptKey="users/user-1/transcripts/m-1/raw.json",
            ),
        )

        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:ap-northeast-1:123:execution:test:m-1-retry-123",
        }

        result = retry_meeting(
            "user-1", "m-1",
            s3_client=s3, sfn_client=mock_sfn,
            bucket=DATA_BUCKET, step_function_arn=STEP_FUNCTION_ARN,
        )
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert body["message"] == "Retry started"
        mock_sfn.start_execution.assert_called_once()

        # Status should be updated to processing
        status = _read_s3_json(s3, status_key("m-1"))
        assert status["status"] == "processing"

    @mock_aws
    def test_rejects_retry_for_non_failed_meeting(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1", status="completed"))

        result = retry_meeting(
            "user-1", "m-1",
            s3_client=s3, sfn_client=MagicMock(),
            bucket=DATA_BUCKET, step_function_arn=STEP_FUNCTION_ARN,
        )
        assert result["statusCode"] == 409

    @mock_aws
    def test_rejects_retry_without_transcript(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)
        _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1", status="failed"))

        result = retry_meeting(
            "user-1", "m-1",
            s3_client=s3, sfn_client=MagicMock(),
            bucket=DATA_BUCKET, step_function_arn=STEP_FUNCTION_ARN,
        )
        assert result["statusCode"] == 400


# ---------------------------------------------------------------------------
# handler (router integration)
# ---------------------------------------------------------------------------


class TestHandler:
    @mock_aws
    def test_routes_get_meetings(self):
        os.environ["DATA_BUCKET"] = DATA_BUCKET
        try:
            s3 = boto3.client("s3", region_name=REGION)
            _create_bucket(s3)
            _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))

            event = _api_event("GET", "/meetings", user_id="user-1")

            with patch("backend.lambdas.api.handler.boto3.client", return_value=s3):
                result = handler(event, None)

            body = json.loads(result["body"])
            assert result["statusCode"] == 200
            assert len(body["meetings"]) == 1
        finally:
            os.environ.pop("DATA_BUCKET", None)

    @mock_aws
    def test_routes_get_meeting(self):
        os.environ["DATA_BUCKET"] = DATA_BUCKET
        try:
            s3 = boto3.client("s3", region_name=REGION)
            _create_bucket(s3)
            _put_s3_json(s3, status_key("m-1"), _status_obj("m-1", "user-1"))

            event = _api_event("GET", "/meetings/{meetingId}", user_id="user-1", meeting_id="m-1")

            with patch("backend.lambdas.api.handler.boto3.client", return_value=s3):
                result = handler(event, None)

            assert result["statusCode"] == 200
        finally:
            os.environ.pop("DATA_BUCKET", None)

    def test_returns_401_without_user_id(self):
        event = {
            "httpMethod": "GET",
            "resource": "/meetings",
            "requestContext": {},
            "pathParameters": {},
            "body": None,
        }
        result = handler(event, None)
        assert result["statusCode"] == 401

    def test_returns_404_for_unknown_route(self):
        event = _api_event("DELETE", "/meetings", user_id="user-1")
        result = handler(event, None)
        assert result["statusCode"] == 404

    def test_cors_headers_present(self):
        event = _api_event("DELETE", "/unknown", user_id="user-1")
        result = handler(event, None)
        assert result["headers"]["Access-Control-Allow-Origin"] == "*"

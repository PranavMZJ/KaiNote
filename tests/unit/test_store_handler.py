"""Unit tests for the report storage Lambda handler.

Tests cover:
- Storing a validated report to S3 and updating status to completed
- Marking a meeting as failed with error details
- Updating terminal status (preserving existing status)
- Handler dispatch for all three actions
- Behaviour when no prior status object exists

Requirements: 6.7, 14.5
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
import pytest
from moto import mock_aws

from backend.lambdas.store.handler import (
    handler,
    mark_failed,
    store_report,
    update_status,
)
from backend.models.meeting_status import MeetingStatusEnum
from backend.utils.s3_keys import report_key, status_key


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

DATA_BUCKET = "test-data-bucket"
REGION = "ap-northeast-1"


def _sample_report(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid report dict."""
    base: dict[str, Any] = {
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
    base.update(overrides)
    return base


def _create_bucket(s3_client) -> None:
    s3_client.create_bucket(
        Bucket=DATA_BUCKET,
        CreateBucketConfiguration={"LocationConstraint": REGION},
    )


def _read_s3_json(s3_client, key: str) -> dict[str, Any]:
    response = s3_client.get_object(Bucket=DATA_BUCKET, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def _put_status(s3_client, meeting_id: str, status_data: dict[str, Any]) -> None:
    key = status_key(meeting_id)
    s3_client.put_object(
        Bucket=DATA_BUCKET,
        Key=key,
        Body=json.dumps(status_data).encode("utf-8"),
    )


# ---------------------------------------------------------------------------
# store_report
# ---------------------------------------------------------------------------


class TestStoreReport:
    @mock_aws
    def test_stores_report_and_creates_status(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        result = store_report("m-1", "u-1", _sample_report(), s3_client=s3, bucket=DATA_BUCKET)

        # Report stored at correct key
        rpt_key = report_key("u-1", "m-1")
        assert result["reportKey"] == rpt_key
        stored_report = _read_s3_json(s3, rpt_key)
        assert stored_report["meeting_title"] == "Sprint Planning"

        # Status created with completed
        sts_key = status_key("m-1")
        assert result["statusKey"] == sts_key
        status = _read_s3_json(s3, sts_key)
        assert status["status"] == "completed"
        assert status["meetingId"] == "m-1"
        assert status["userId"] == "u-1"
        assert status["reportKey"] == rpt_key

    @mock_aws
    def test_updates_existing_status_to_completed(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        # Pre-existing processing status
        _put_status(s3, "m-2", {
            "meetingId": "m-2",
            "userId": "u-2",
            "status": "processing",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "currentStep": "GenerateMinutes",
        })

        store_report("m-2", "u-2", _sample_report(), s3_client=s3, bucket=DATA_BUCKET)

        status = _read_s3_json(s3, status_key("m-2"))
        assert status["status"] == "completed"
        assert status["createdAt"] == "2024-01-01T00:00:00Z"  # preserved
        assert status["currentStep"] == "StoreReport"


# ---------------------------------------------------------------------------
# mark_failed
# ---------------------------------------------------------------------------


class TestMarkFailed:
    @mock_aws
    def test_creates_failed_status_with_error(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        error = {"Error": "SchemaValidation", "Cause": "Missing required field"}
        result = mark_failed("m-3", "u-3", error, s3_client=s3, bucket=DATA_BUCKET)

        sts_key = status_key("m-3")
        assert result["statusKey"] == sts_key
        status = _read_s3_json(s3, sts_key)
        assert status["status"] == "failed"
        assert status["meetingId"] == "m-3"
        assert "SchemaValidation" in status["error"]

    @mock_aws
    def test_updates_existing_status_to_failed(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        _put_status(s3, "m-4", {
            "meetingId": "m-4",
            "userId": "u-4",
            "status": "processing",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
        })

        mark_failed("m-4", "u-4", "Lambda timeout", s3_client=s3, bucket=DATA_BUCKET)

        status = _read_s3_json(s3, status_key("m-4"))
        assert status["status"] == "failed"
        assert status["error"] == "Lambda timeout"
        assert status["currentStep"] == "MarkFailed"

    @mock_aws
    def test_handles_dict_error(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        error = {"Error": "States.TaskFailed", "Cause": "Something broke"}
        mark_failed("m-5", "u-5", error, s3_client=s3, bucket=DATA_BUCKET)

        status = _read_s3_json(s3, status_key("m-5"))
        assert "States.TaskFailed" in status["error"]


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------


class TestUpdateStatus:
    @mock_aws
    def test_preserves_existing_status(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        _put_status(s3, "m-6", {
            "meetingId": "m-6",
            "userId": "u-6",
            "status": "completed",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
        })

        result = update_status("m-6", "u-6", s3_client=s3, bucket=DATA_BUCKET)

        assert result["status"] == "completed"
        status = _read_s3_json(s3, status_key("m-6"))
        assert status["status"] == "completed"
        # updatedAt should be refreshed
        assert status["updatedAt"] != "2024-01-01T00:00:00Z"

    @mock_aws
    def test_creates_status_when_none_exists(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        result = update_status("m-7", "u-7", s3_client=s3, bucket=DATA_BUCKET)

        assert result["status"] == "completed"
        status = _read_s3_json(s3, status_key("m-7"))
        assert status["meetingId"] == "m-7"
        assert status["userId"] == "u-7"

    @mock_aws
    def test_preserves_failed_status(self):
        s3 = boto3.client("s3", region_name=REGION)
        _create_bucket(s3)

        _put_status(s3, "m-8", {
            "meetingId": "m-8",
            "userId": "u-8",
            "status": "failed",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "error": "Some error",
        })

        result = update_status("m-8", "u-8", s3_client=s3, bucket=DATA_BUCKET)

        assert result["status"] == "failed"
        status = _read_s3_json(s3, status_key("m-8"))
        assert status["error"] == "Some error"


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------


class TestHandler:
    @mock_aws
    def test_default_action_stores_report(self):
        os.environ["DATA_BUCKET"] = DATA_BUCKET
        try:
            s3 = boto3.client("s3", region_name=REGION)
            _create_bucket(s3)

            event = {
                "meetingId": "m-10",
                "userId": "u-10",
                "report": _sample_report(),
            }

            from unittest.mock import patch

            with patch("backend.lambdas.store.handler.boto3.client", return_value=s3):
                result = handler(event, None)

            assert result["action"] == "store"
            assert result["meetingId"] == "m-10"
            assert "reportKey" in result
            assert "statusKey" in result

            # Verify report was stored
            stored = _read_s3_json(s3, report_key("u-10", "m-10"))
            assert stored["meeting_title"] == "Sprint Planning"
        finally:
            os.environ.pop("DATA_BUCKET", None)

    @mock_aws
    def test_mark_failed_action(self):
        os.environ["DATA_BUCKET"] = DATA_BUCKET
        try:
            s3 = boto3.client("s3", region_name=REGION)
            _create_bucket(s3)

            event = {
                "action": "mark_failed",
                "meetingId": "m-11",
                "userId": "u-11",
                "error": {"Error": "Bedrock", "Cause": "Guardrail blocked"},
            }

            from unittest.mock import patch

            with patch("backend.lambdas.store.handler.boto3.client", return_value=s3):
                result = handler(event, None)

            assert result["action"] == "mark_failed"
            assert result["meetingId"] == "m-11"
            assert "statusKey" in result

            status = _read_s3_json(s3, status_key("m-11"))
            assert status["status"] == "failed"
        finally:
            os.environ.pop("DATA_BUCKET", None)

    @mock_aws
    def test_update_status_action(self):
        os.environ["DATA_BUCKET"] = DATA_BUCKET
        try:
            s3 = boto3.client("s3", region_name=REGION)
            _create_bucket(s3)

            # Pre-create a completed status
            _put_status(s3, "m-12", {
                "meetingId": "m-12",
                "userId": "u-12",
                "status": "completed",
                "createdAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-01-01T00:00:00Z",
            })

            event = {
                "action": "update_status",
                "meetingId": "m-12",
                "userId": "u-12",
            }

            from unittest.mock import patch

            with patch("backend.lambdas.store.handler.boto3.client", return_value=s3):
                result = handler(event, None)

            assert result["action"] == "update_status"
            assert result["status"] == "completed"
        finally:
            os.environ.pop("DATA_BUCKET", None)

    @mock_aws
    def test_handler_raises_on_s3_error(self):
        os.environ["DATA_BUCKET"] = "nonexistent-bucket"
        try:
            event = {
                "meetingId": "m-13",
                "userId": "u-13",
                "report": _sample_report(),
            }

            with pytest.raises(Exception):
                handler(event, None)
        finally:
            os.environ.pop("DATA_BUCKET", None)

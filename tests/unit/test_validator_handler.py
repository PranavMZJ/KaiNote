"""Unit tests for the schema validator Lambda handler.

Tests cover:
- Schema loading from S3
- Validation of valid reports (all required fields, correct types)
- Validation of invalid reports (missing fields, wrong types, invalid enums,
  confidence out of range)
- Handler dispatch with pass-through of attemptCount
- Error handling when schema cannot be loaded

Requirements: 6.5, 8.3
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
import pytest
from moto import mock_aws

from backend.lambdas.validator.handler import (
    handler,
    load_schema,
    validate_report,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

PROMPT_BUCKET = "test-prompts-bucket"

MINUTES_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "schema_version", "meeting_title", "meeting_datetime",
        "participants", "summary", "agenda_items",
        "key_discussion_points", "decisions", "action_items",
        "risks_blockers", "open_questions", "follow_up_needed",
    ],
    "properties": {
        "schema_version": {"type": "string", "pattern": "^v\\d+$"},
        "meeting_title": {"type": "string"},
        "meeting_datetime": {"type": "string", "format": "date-time"},
        "participants": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "agenda_items": {"type": "array", "items": {"type": "string"}},
        "key_discussion_points": {"type": "array", "items": {"type": "string"}},
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["decision", "rationale", "evidence"],
                "properties": {
                    "decision": {"type": "string"},
                    "rationale": {"type": "string"},
                    "owner": {"type": ["string", "null"]},
                    "evidence": {"type": "string"},
                    "timestamp": {"type": ["string", "null"], "format": "date-time"},
                },
            },
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["task", "priority", "evidence", "confidence", "needs_human_review"],
                "properties": {
                    "task": {"type": "string"},
                    "owner": {"type": ["string", "null"]},
                    "due_date": {"type": ["string", "null"], "format": "date"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "evidence": {"type": "string"},
                    "timestamp": {"type": ["string", "null"], "format": "date-time"},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "needs_human_review": {"type": "boolean"},
                },
            },
        },
        "risks_blockers": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "follow_up_needed": {"type": "boolean"},
    },
}


def _valid_report(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid report dict."""
    base: dict[str, Any] = {
        "schema_version": "v1",
        "meeting_title": "Sprint Planning",
        "meeting_datetime": "2024-01-15T10:00:00Z",
        "participants": ["Alice", "Bob"],
        "summary": "Discussed sprint goals.",
        "agenda_items": ["Sprint backlog review"],
        "key_discussion_points": ["Velocity trends"],
        "decisions": [
            {
                "decision": "Adopt new framework",
                "rationale": "Better performance",
                "evidence": "Alice showed benchmarks",
                "owner": "Alice",
                "timestamp": None,
            }
        ],
        "action_items": [
            {
                "task": "Write migration plan",
                "owner": "Bob",
                "due_date": "2024-02-01",
                "priority": "high",
                "evidence": "Bob volunteered",
                "timestamp": None,
                "confidence": 0.85,
                "needs_human_review": False,
            }
        ],
        "risks_blockers": ["Tight deadline"],
        "open_questions": ["Who handles QA?"],
        "follow_up_needed": True,
    }
    base.update(overrides)
    return base


def _setup_s3_schema(s3_client, version: str = "v1") -> None:
    """Create the prompts bucket and upload the schema."""
    s3_client.create_bucket(
        Bucket=PROMPT_BUCKET,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3_client.put_object(
        Bucket=PROMPT_BUCKET,
        Key=f"schemas/{version}/minutes_schema.json",
        Body=json.dumps(MINUTES_SCHEMA).encode("utf-8"),
    )


# ---------------------------------------------------------------------------
# load_schema
# ---------------------------------------------------------------------------


class TestLoadSchema:
    @mock_aws
    def test_loads_schema_from_s3(self):
        os.environ["PROMPT_BUCKET"] = PROMPT_BUCKET
        try:
            s3 = boto3.client("s3", region_name="ap-northeast-1")
            _setup_s3_schema(s3)
            schema = load_schema(version="v1", s3_client=s3)
            assert schema["type"] == "object"
            assert "schema_version" in schema["properties"]
        finally:
            os.environ.pop("PROMPT_BUCKET", None)

    @mock_aws
    def test_missing_schema_raises(self):
        os.environ["PROMPT_BUCKET"] = PROMPT_BUCKET
        try:
            s3 = boto3.client("s3", region_name="ap-northeast-1")
            s3.create_bucket(
                Bucket=PROMPT_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
            )
            with pytest.raises(Exception):
                load_schema(version="v99", s3_client=s3)
        finally:
            os.environ.pop("PROMPT_BUCKET", None)


# ---------------------------------------------------------------------------
# validate_report — valid inputs
# ---------------------------------------------------------------------------


class TestValidateReportValid:
    def test_valid_report_passes(self):
        result = validate_report(_valid_report(), MINUTES_SCHEMA)
        assert result["isValid"] is True
        assert result["errors"] == []

    def test_valid_report_with_null_owner(self):
        report = _valid_report()
        report["action_items"][0]["owner"] = None
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is True

    def test_valid_report_with_null_due_date(self):
        report = _valid_report()
        report["action_items"][0]["due_date"] = None
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is True

    def test_valid_report_confidence_at_zero(self):
        report = _valid_report()
        report["action_items"][0]["confidence"] = 0.0
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is True

    def test_valid_report_confidence_at_one(self):
        report = _valid_report()
        report["action_items"][0]["confidence"] = 1.0
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is True

    def test_valid_report_all_priorities(self):
        for priority in ("low", "medium", "high"):
            report = _valid_report()
            report["action_items"][0]["priority"] = priority
            result = validate_report(report, MINUTES_SCHEMA)
            assert result["isValid"] is True, f"priority={priority} should be valid"

    def test_valid_report_empty_arrays(self):
        report = _valid_report(
            participants=[],
            agenda_items=[],
            key_discussion_points=[],
            decisions=[],
            action_items=[],
            risks_blockers=[],
            open_questions=[],
        )
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is True


# ---------------------------------------------------------------------------
# validate_report — invalid inputs
# ---------------------------------------------------------------------------


class TestValidateReportInvalid:
    def test_missing_required_field(self):
        report = _valid_report()
        del report["meeting_title"]
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is False
        assert any("meeting_title" in e for e in result["errors"])

    def test_wrong_type_for_participants(self):
        report = _valid_report(participants="not an array")
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is False
        assert any("participants" in e for e in result["errors"])

    def test_invalid_priority_enum(self):
        report = _valid_report()
        report["action_items"][0]["priority"] = "critical"
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is False
        assert any("priority" in e or "critical" in e for e in result["errors"])

    def test_confidence_above_one(self):
        report = _valid_report()
        report["action_items"][0]["confidence"] = 1.5
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is False
        assert any("confidence" in e or "1.5" in e for e in result["errors"])

    def test_confidence_below_zero(self):
        report = _valid_report()
        report["action_items"][0]["confidence"] = -0.1
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is False

    def test_follow_up_needed_wrong_type(self):
        report = _valid_report(follow_up_needed="yes")
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is False
        assert any("follow_up_needed" in e for e in result["errors"])

    def test_invalid_schema_version_pattern(self):
        report = _valid_report(schema_version="1.0")
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is False

    def test_action_item_missing_required_field(self):
        report = _valid_report()
        del report["action_items"][0]["confidence"]
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is False
        assert any("confidence" in e for e in result["errors"])

    def test_decision_missing_required_field(self):
        report = _valid_report()
        del report["decisions"][0]["evidence"]
        result = validate_report(report, MINUTES_SCHEMA)
        assert result["isValid"] is False
        assert any("evidence" in e for e in result["errors"])

    def test_empty_object_fails(self):
        result = validate_report({}, MINUTES_SCHEMA)
        assert result["isValid"] is False
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------


class TestHandler:
    @mock_aws
    def test_valid_report_returns_is_valid_true(self):
        os.environ["PROMPT_BUCKET"] = PROMPT_BUCKET
        try:
            s3 = boto3.client("s3", region_name="ap-northeast-1")
            _setup_s3_schema(s3)

            event = {
                "meetingId": "m-1",
                "userId": "u-1",
                "report": _valid_report(),
                "schemaVersion": "v1",
                "attemptCount": 2,
            }

            from unittest.mock import patch

            with patch("backend.lambdas.validator.handler.boto3.client", return_value=s3):
                result = handler(event, None)

            assert result["isValid"] is True
            assert result["errors"] == []
            assert result["meetingId"] == "m-1"
            assert result["userId"] == "u-1"
            assert result["attemptCount"] == 2
            assert result["report"] == event["report"]
        finally:
            os.environ.pop("PROMPT_BUCKET", None)

    @mock_aws
    def test_invalid_report_returns_is_valid_false(self):
        os.environ["PROMPT_BUCKET"] = PROMPT_BUCKET
        try:
            s3 = boto3.client("s3", region_name="ap-northeast-1")
            _setup_s3_schema(s3)

            bad_report = _valid_report()
            del bad_report["summary"]

            event = {
                "meetingId": "m-2",
                "userId": "u-2",
                "report": bad_report,
            }

            from unittest.mock import patch

            with patch("backend.lambdas.validator.handler.boto3.client", return_value=s3):
                result = handler(event, None)

            assert result["isValid"] is False
            assert any("summary" in e for e in result["errors"])
            assert result["attemptCount"] == 1  # default
        finally:
            os.environ.pop("PROMPT_BUCKET", None)

    @mock_aws
    def test_schema_load_failure_returns_error(self):
        os.environ["PROMPT_BUCKET"] = PROMPT_BUCKET
        try:
            s3 = boto3.client("s3", region_name="ap-northeast-1")
            # Create bucket but do NOT upload schema
            s3.create_bucket(
                Bucket=PROMPT_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
            )

            event = {
                "meetingId": "m-3",
                "userId": "u-3",
                "report": _valid_report(),
                "schemaVersion": "v99",
            }

            from unittest.mock import patch

            with patch("backend.lambdas.validator.handler.boto3.client", return_value=s3):
                result = handler(event, None)

            assert result["isValid"] is False
            assert any("Failed to load schema" in e for e in result["errors"])
        finally:
            os.environ.pop("PROMPT_BUCKET", None)

    @mock_aws
    def test_default_attempt_count(self):
        os.environ["PROMPT_BUCKET"] = PROMPT_BUCKET
        try:
            s3 = boto3.client("s3", region_name="ap-northeast-1")
            _setup_s3_schema(s3)

            event = {
                "meetingId": "m-4",
                "userId": "u-4",
                "report": _valid_report(),
            }

            from unittest.mock import patch

            with patch("backend.lambdas.validator.handler.boto3.client", return_value=s3):
                result = handler(event, None)

            assert result["attemptCount"] == 1
        finally:
            os.environ.pop("PROMPT_BUCKET", None)

    @mock_aws
    def test_attempt_count_passed_through(self):
        os.environ["PROMPT_BUCKET"] = PROMPT_BUCKET
        try:
            s3 = boto3.client("s3", region_name="ap-northeast-1")
            _setup_s3_schema(s3)

            event = {
                "meetingId": "m-5",
                "userId": "u-5",
                "report": _valid_report(),
                "attemptCount": 3,
            }

            from unittest.mock import patch

            with patch("backend.lambdas.validator.handler.boto3.client", return_value=s3):
                result = handler(event, None)

            assert result["attemptCount"] == 3
        finally:
            os.environ.pop("PROMPT_BUCKET", None)

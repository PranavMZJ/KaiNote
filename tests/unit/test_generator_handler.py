"""Unit tests for the minutes generator Lambda handler.

Tests cover:
- Prompt template loading and variable substitution
- Bedrock response parsing (valid JSON, markdown-fenced JSON, malformed JSON)
- Confidence-based human review flagging
- Null handling for owner and due_date fields
- Transcript formatting for prompt
- Merge logic for chunked generation
- Handler dispatch for generate and merge actions
- Unknown action error handling

Requirements: 7.1, 7.4, 7.5, 7.6, 7.7, 8.1, 14.4
"""

from __future__ import annotations

import io
import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from backend.lambdas.generator.handler import (
    build_prompt,
    enforce_confidence_review,
    extract_json_from_response,
    format_transcript_for_prompt,
    handler,
    invoke_bedrock,
    load_prompt_template,
    merge_chunk_results,
)
from backend.models.minutes import ActionItem, Decision, MinutesReport


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

PROMPT_BUCKET = "test-prompts-bucket"
PROMPT_VERSION = "v1"
PROMPT_TEMPLATE = (
    "Generate meeting minutes in {language} for schema {schema_version}.\n"
    "Transcript:\n{transcript}"
)


def _sample_report_dict(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid MinutesReport dict."""
    base: dict[str, Any] = {
        "schema_version": "v1",
        "meeting_title": "Test Meeting",
        "meeting_datetime": "2024-01-15T10:00:00Z",
        "participants": ["Alice", "Bob"],
        "summary": "Discussed project status.",
        "agenda_items": ["Status update"],
        "key_discussion_points": ["Timeline review"],
        "decisions": [
            {
                "decision": "Approve budget",
                "rationale": "Within limits",
                "evidence": "Alice said budget is fine",
                "owner": "Alice",
                "timestamp": None,
            }
        ],
        "action_items": [
            {
                "task": "Send report",
                "owner": "Bob",
                "due_date": "2024-02-01",
                "priority": "high",
                "evidence": "Bob volunteered",
                "timestamp": None,
                "confidence": 0.9,
                "needs_human_review": False,
            },
            {
                "task": "Review docs",
                "owner": None,
                "due_date": None,
                "priority": "medium",
                "evidence": "Someone mentioned it",
                "timestamp": None,
                "confidence": 0.5,
                "needs_human_review": True,
            },
        ],
        "risks_blockers": ["Tight deadline"],
        "open_questions": ["Who handles QA?"],
        "follow_up_needed": True,
    }
    base.update(overrides)
    return base


def _bedrock_response(report_dict: dict[str, Any]) -> dict[str, Any]:
    """Wrap a report dict in a Bedrock-style response body."""
    return {
        "content": [{"type": "text", "text": json.dumps(report_dict)}],
        "usage": {"input_tokens": 100, "output_tokens": 200},
    }


def _cleaned_transcript_dict() -> dict[str, Any]:
    return {
        "meetingId": "m-1",
        "userId": "u-1",
        "startTime": "2024-01-15T10:00:00Z",
        "endTime": "2024-01-15T11:00:00Z",
        "language": "ja-JP",
        "totalTokenCount": 500,
        "speakers": ["spk_0", "spk_1"],
        "segments": [
            {"speaker": "spk_0", "startTime": 0.0, "endTime": 1.0, "text": "Hello everyone"},
            {"speaker": "spk_1", "startTime": 1.0, "endTime": 2.0, "text": "Hi there"},
        ],
    }


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_substitutes_all_variables(self):
        template = "Lang: {language}, Schema: {schema_version}, Text: {transcript}"
        result = build_prompt(template, "my transcript", "v1", "ja-JP")
        assert result == "Lang: ja-JP, Schema: v1, Text: my transcript"

    def test_no_variables_unchanged(self):
        template = "No variables here."
        result = build_prompt(template, "text", "v1", "en")
        assert result == "No variables here."


# ---------------------------------------------------------------------------
# format_transcript_for_prompt
# ---------------------------------------------------------------------------


class TestFormatTranscript:
    def test_formats_segments(self):
        transcript = _cleaned_transcript_dict()
        result = format_transcript_for_prompt(transcript)
        assert "[spk_0]: Hello everyone" in result
        assert "[spk_1]: Hi there" in result

    def test_empty_segments(self):
        transcript = {"segments": []}
        result = format_transcript_for_prompt(transcript)
        assert result == ""

    def test_missing_segments_key(self):
        result = format_transcript_for_prompt({})
        assert result == ""


# ---------------------------------------------------------------------------
# extract_json_from_response
# ---------------------------------------------------------------------------


class TestExtractJsonFromResponse:
    def test_plain_json(self):
        report = _sample_report_dict()
        body = _bedrock_response(report)
        result = extract_json_from_response(body)
        assert result["meeting_title"] == "Test Meeting"

    def test_markdown_fenced_json(self):
        report = _sample_report_dict()
        fenced = f"```json\n{json.dumps(report)}\n```"
        body = {"content": [{"type": "text", "text": fenced}]}
        result = extract_json_from_response(body)
        assert result["meeting_title"] == "Test Meeting"

    def test_markdown_fenced_no_language(self):
        report = _sample_report_dict()
        fenced = f"```\n{json.dumps(report)}\n```"
        body = {"content": [{"type": "text", "text": fenced}]}
        result = extract_json_from_response(body)
        assert result["meeting_title"] == "Test Meeting"

    def test_malformed_json_raises(self):
        body = {"content": [{"type": "text", "text": "not valid json"}]}
        with pytest.raises(ValueError, match="not valid JSON"):
            extract_json_from_response(body)

    def test_empty_content_blocks_raises(self):
        body = {"content": []}
        with pytest.raises(ValueError, match="no content blocks"):
            extract_json_from_response(body)

    def test_missing_content_key_raises(self):
        body = {}
        with pytest.raises(ValueError, match="no content blocks"):
            extract_json_from_response(body)


# ---------------------------------------------------------------------------
# enforce_confidence_review
# ---------------------------------------------------------------------------


class TestEnforceConfidenceReview:
    def test_low_confidence_flagged(self):
        report = MinutesReport.from_dict(_sample_report_dict())
        # Set all confidences below 0.7
        for item in report.action_items:
            item.confidence = 0.3
        result = enforce_confidence_review(report)
        for item in result.action_items:
            assert item.needs_human_review is True

    def test_high_confidence_not_flagged(self):
        report = MinutesReport.from_dict(_sample_report_dict())
        for item in report.action_items:
            item.confidence = 0.9
        result = enforce_confidence_review(report)
        for item in result.action_items:
            assert item.needs_human_review is False

    def test_boundary_0_7_not_flagged(self):
        report = MinutesReport.from_dict(_sample_report_dict())
        for item in report.action_items:
            item.confidence = 0.7
        result = enforce_confidence_review(report)
        for item in result.action_items:
            assert item.needs_human_review is False

    def test_just_below_boundary_flagged(self):
        report = MinutesReport.from_dict(_sample_report_dict())
        for item in report.action_items:
            item.confidence = 0.69
        result = enforce_confidence_review(report)
        for item in result.action_items:
            assert item.needs_human_review is True

    def test_empty_owner_normalized_to_none(self):
        data = _sample_report_dict()
        data["action_items"][0]["owner"] = ""
        report = MinutesReport.from_dict(data)
        result = enforce_confidence_review(report)
        assert result.action_items[0].owner is None

    def test_empty_due_date_normalized_to_none(self):
        data = _sample_report_dict()
        data["action_items"][0]["due_date"] = "  "
        report = MinutesReport.from_dict(data)
        result = enforce_confidence_review(report)
        assert result.action_items[0].due_date is None

    def test_null_owner_stays_none(self):
        data = _sample_report_dict()
        data["action_items"][0]["owner"] = None
        report = MinutesReport.from_dict(data)
        result = enforce_confidence_review(report)
        assert result.action_items[0].owner is None


# ---------------------------------------------------------------------------
# load_prompt_template (moto S3)
# ---------------------------------------------------------------------------


class TestLoadPromptTemplate:
    @mock_aws
    def test_loads_template_from_s3(self):
        os.environ["PROMPT_BUCKET"] = PROMPT_BUCKET
        os.environ["PROMPT_VERSION"] = PROMPT_VERSION
        try:
            s3 = boto3.client("s3", region_name="ap-northeast-1")
            s3.create_bucket(
                Bucket=PROMPT_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
            )
            s3.put_object(
                Bucket=PROMPT_BUCKET,
                Key="prompts/v1/minutes_prompt.txt",
                Body=PROMPT_TEMPLATE.encode("utf-8"),
            )
            result = load_prompt_template(s3_client=s3)
            assert "{transcript}" in result
            assert "{language}" in result
        finally:
            os.environ.pop("PROMPT_BUCKET", None)
            os.environ.pop("PROMPT_VERSION", None)

    @mock_aws
    def test_missing_template_raises(self):
        os.environ["PROMPT_BUCKET"] = PROMPT_BUCKET
        os.environ["PROMPT_VERSION"] = "v99"
        try:
            s3 = boto3.client("s3", region_name="ap-northeast-1")
            s3.create_bucket(
                Bucket=PROMPT_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
            )
            with pytest.raises(Exception):
                load_prompt_template(s3_client=s3)
        finally:
            os.environ.pop("PROMPT_BUCKET", None)
            os.environ.pop("PROMPT_VERSION", None)


# ---------------------------------------------------------------------------
# invoke_bedrock (mocked)
# ---------------------------------------------------------------------------


class TestInvokeBedrock:
    def test_invokes_with_guardrails(self):
        os.environ["GUARDRAIL_ID"] = "gr-123"
        os.environ["GUARDRAIL_VERSION"] = "1"
        os.environ["MODEL_ID"] = "anthropic.claude-3-haiku-20240307-v1:0"
        try:
            report = _sample_report_dict()
            response_payload = _bedrock_response(report)

            mock_client = MagicMock()
            mock_client.invoke_model.return_value = {
                "body": io.BytesIO(json.dumps(response_payload).encode("utf-8")),
            }

            result = invoke_bedrock("test prompt", bedrock_client=mock_client)

            call_kwargs = mock_client.invoke_model.call_args[1]
            assert call_kwargs["guardrailIdentifier"] == "gr-123"
            assert call_kwargs["guardrailVersion"] == "1"
            assert result["usage"]["input_tokens"] == 100
        finally:
            os.environ.pop("GUARDRAIL_ID", None)
            os.environ.pop("GUARDRAIL_VERSION", None)
            os.environ.pop("MODEL_ID", None)

    def test_invokes_without_guardrails_when_empty(self):
        os.environ["GUARDRAIL_ID"] = ""
        os.environ["GUARDRAIL_VERSION"] = ""
        try:
            report = _sample_report_dict()
            response_payload = _bedrock_response(report)

            mock_client = MagicMock()
            mock_client.invoke_model.return_value = {
                "body": io.BytesIO(json.dumps(response_payload).encode("utf-8")),
            }

            invoke_bedrock("test prompt", bedrock_client=mock_client)

            call_kwargs = mock_client.invoke_model.call_args[1]
            assert "guardrailIdentifier" not in call_kwargs
            assert "guardrailVersion" not in call_kwargs
        finally:
            os.environ.pop("GUARDRAIL_ID", None)
            os.environ.pop("GUARDRAIL_VERSION", None)

    def test_logs_error_on_failure(self):
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = RuntimeError("Bedrock down")

        with pytest.raises(RuntimeError, match="Bedrock down"):
            invoke_bedrock("test prompt", bedrock_client=mock_client)


# ---------------------------------------------------------------------------
# merge_chunk_results
# ---------------------------------------------------------------------------


class TestMergeChunkResults:
    def test_single_chunk_returned_as_is(self):
        chunk = _sample_report_dict()
        result = merge_chunk_results([chunk])
        assert result is chunk

    def test_merges_participants_deduplicates(self):
        c1 = _sample_report_dict(participants=["Alice", "Bob"])
        c2 = _sample_report_dict(participants=["Bob", "Charlie"])
        result = merge_chunk_results([c1, c2])
        assert result["participants"] == ["Alice", "Bob", "Charlie"]

    def test_merges_action_items(self):
        c1 = _sample_report_dict()
        c2 = _sample_report_dict()
        total_items = len(c1["action_items"]) + len(c2["action_items"])
        result = merge_chunk_results([c1, c2])
        assert len(result["action_items"]) == total_items

    def test_merges_decisions(self):
        c1 = _sample_report_dict()
        c2 = _sample_report_dict()
        total = len(c1["decisions"]) + len(c2["decisions"])
        result = merge_chunk_results([c1, c2])
        assert len(result["decisions"]) == total

    def test_follow_up_true_if_any_chunk(self):
        c1 = _sample_report_dict(follow_up_needed=False)
        c2 = _sample_report_dict(follow_up_needed=True)
        result = merge_chunk_results([c1, c2])
        assert result["follow_up_needed"] is True

    def test_summary_concatenated(self):
        c1 = _sample_report_dict(summary="Part one.")
        c2 = _sample_report_dict(summary="Part two.")
        result = merge_chunk_results([c1, c2])
        assert "Part one." in result["summary"]
        assert "Part two." in result["summary"]

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="No chunk results"):
            merge_chunk_results([])


# ---------------------------------------------------------------------------
# handler dispatch
# ---------------------------------------------------------------------------


class TestHandlerDispatch:
    def test_unknown_action_raises(self):
        with pytest.raises(ValueError, match="Unknown action"):
            handler({"action": "invalid"}, None)

    @mock_aws
    def test_generate_action_end_to_end(self):
        """Test the generate action with mocked S3 and Bedrock."""
        os.environ["PROMPT_BUCKET"] = PROMPT_BUCKET
        os.environ["PROMPT_VERSION"] = PROMPT_VERSION
        os.environ["GUARDRAIL_ID"] = ""
        os.environ["GUARDRAIL_VERSION"] = ""
        try:
            # Set up S3 with prompt template.
            s3 = boto3.client("s3", region_name="ap-northeast-1")
            s3.create_bucket(
                Bucket=PROMPT_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
            )
            s3.put_object(
                Bucket=PROMPT_BUCKET,
                Key="prompts/v1/minutes_prompt.txt",
                Body=PROMPT_TEMPLATE.encode("utf-8"),
            )

            # Mock Bedrock response.
            report = _sample_report_dict()
            response_payload = _bedrock_response(report)
            mock_bedrock = MagicMock()
            mock_bedrock.invoke_model.return_value = {
                "body": io.BytesIO(json.dumps(response_payload).encode("utf-8")),
            }

            event = {
                "action": "generate",
                "meetingId": "m-1",
                "userId": "u-1",
                "cleanedTranscript": _cleaned_transcript_dict(),
            }

            with patch(
                "backend.lambdas.generator.handler.boto3.client"
            ) as mock_boto_client:
                # Return the real moto S3 client for S3, mock for bedrock-runtime.
                def client_factory(service, **kwargs):
                    if service == "s3":
                        return s3
                    return mock_bedrock

                mock_boto_client.side_effect = client_factory
                result = handler(event, None)

            assert result["meeting_title"] == "Test Meeting"
            assert result["schema_version"] == "v1"
            # Verify confidence review was enforced.
            for item in result["action_items"]:
                if item["confidence"] < 0.7:
                    assert item["needs_human_review"] is True
                else:
                    assert item["needs_human_review"] is False
        finally:
            os.environ.pop("PROMPT_BUCKET", None)
            os.environ.pop("PROMPT_VERSION", None)
            os.environ.pop("GUARDRAIL_ID", None)
            os.environ.pop("GUARDRAIL_VERSION", None)

    def test_merge_action(self):
        c1 = _sample_report_dict()
        c2 = _sample_report_dict(participants=["Charlie"])
        event = {
            "action": "merge",
            "meetingId": "m-1",
            "userId": "u-1",
            "chunkResults": [c1, c2],
        }
        result = handler(event, None)
        assert "Charlie" in result["participants"]
        # Confidence review enforced on merged result.
        for item in result["action_items"]:
            if item["confidence"] < 0.7:
                assert item["needs_human_review"] is True
            else:
                assert item["needs_human_review"] is False

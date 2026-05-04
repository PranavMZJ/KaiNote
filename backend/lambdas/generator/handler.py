"""Minutes generator Lambda handler for Pranav-meeting-minutes-generator.

Handles two actions dispatched by the Step Functions workflow:
- "generate": Generate meeting minutes from a single cleaned transcript using
  Amazon Bedrock with Guardrails.
- "merge": Merge results from multiple chunked generations into a single
  MinutesReport.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 8.1, 8.2, 14.3, 14.4
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import boto3

from backend.models.minutes import ActionItem, Decision, MinutesReport

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _get_prompt_bucket() -> str:
    return os.environ.get("PROMPT_BUCKET", "")


def _get_prompt_version() -> str:
    return os.environ.get("PROMPT_VERSION", "v1")


def _get_guardrail_id() -> str:
    return os.environ.get("GUARDRAIL_ID", "")


def _get_guardrail_version() -> str:
    return os.environ.get("GUARDRAIL_VERSION", "")


def _get_model_id() -> str:
    return os.environ.get(
        "MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
    )


# ---------------------------------------------------------------------------
# Prompt template loading
# ---------------------------------------------------------------------------


def load_prompt_template(s3_client: Any = None) -> str:
    """Load the prompt template from S3.

    Path: ``prompts/v{version}/minutes_prompt.txt`` in the PROMPT_BUCKET.
    """
    bucket = _get_prompt_bucket()
    version = _get_prompt_version()
    key = f"prompts/{version}/minutes_prompt.txt"

    if s3_client is None:
        s3_client = boto3.client("s3")

    logger.info("Loading prompt template: bucket=%s key=%s", bucket, key)
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except Exception:
        logger.exception(
            "Failed to load prompt template: bucket=%s key=%s", bucket, key
        )
        raise


def build_prompt(
    template: str,
    transcript_text: str,
    schema_version: str,
    language: str,
) -> str:
    """Substitute template variables into the prompt template."""
    return (
        template.replace("{transcript}", transcript_text)
        .replace("{schema_version}", schema_version)
        .replace("{language}", language)
    )


# ---------------------------------------------------------------------------
# Bedrock invocation
# ---------------------------------------------------------------------------


def invoke_bedrock(
    prompt: str,
    bedrock_client: Any = None,
) -> dict[str, Any]:
    """Invoke Amazon Bedrock with the given prompt and guardrail parameters.

    Returns the parsed response body dict and logs latency / token usage.
    """
    model_id = _get_model_id()
    guardrail_id = _get_guardrail_id()
    guardrail_version = _get_guardrail_version()

    if bedrock_client is None:
        bedrock_client = boto3.client("bedrock-runtime")

    request_body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    invoke_kwargs: dict[str, Any] = {
        "modelId": model_id,
        "contentType": "application/json",
        "accept": "application/json",
        "body": request_body,
    }

    if guardrail_id:
        invoke_kwargs["guardrailIdentifier"] = guardrail_id
    if guardrail_version:
        invoke_kwargs["guardrailVersion"] = guardrail_version

    logger.info(
        "Invoking Bedrock: model=%s guardrailId=%s guardrailVersion=%s",
        model_id,
        guardrail_id,
        guardrail_version,
    )

    start_time = time.time()
    try:
        response = bedrock_client.invoke_model(**invoke_kwargs)
    except Exception:
        latency_ms = (time.time() - start_time) * 1000
        logger.exception(
            "Bedrock invocation failed: model=%s latency_ms=%.1f",
            model_id,
            latency_ms,
        )
        raise

    latency_ms = (time.time() - start_time) * 1000
    response_body = json.loads(response["body"].read())

    # Log token usage from the Bedrock response.
    usage = response_body.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    logger.info(
        "Bedrock invocation complete: model=%s latency_ms=%.1f "
        "input_tokens=%d output_tokens=%d",
        model_id,
        latency_ms,
        input_tokens,
        output_tokens,
    )

    return response_body


# ---------------------------------------------------------------------------
# Response parsing and post-processing
# ---------------------------------------------------------------------------


def extract_json_from_response(response_body: dict[str, Any]) -> dict[str, Any]:
    """Extract the JSON minutes report from the Bedrock response body.

    The model returns content in ``content[0].text``.  The text may contain
    the JSON wrapped in markdown code fences — we strip those if present.
    """
    content_blocks = response_body.get("content", [])
    if not content_blocks:
        raise ValueError("Bedrock response contains no content blocks")

    text = content_blocks[0].get("text", "")

    # Strip optional markdown code fences.
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove opening fence (possibly ```json)
        first_newline = stripped.index("\n") if "\n" in stripped else len(stripped)
        stripped = stripped[first_newline + 1 :]
    if stripped.endswith("```"):
        stripped = stripped[: -3]
    stripped = stripped.strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Bedrock response as JSON: %s", exc)
        raise ValueError(f"Bedrock response is not valid JSON: {exc}") from exc


def enforce_confidence_review(report: MinutesReport) -> MinutesReport:
    """Enforce confidence-based human review flagging on action items.

    For each action item:
    - confidence < 0.7 → needs_human_review = True
    - confidence >= 0.7 → needs_human_review = False

    Also ensures owner and due_date are None (not guessed) when not provided.
    """
    for item in report.action_items:
        item.needs_human_review = item.confidence < 0.7
        # Ensure empty-string owner/due_date are normalised to None.
        if item.owner is not None and item.owner.strip() == "":
            item.owner = None
        if item.due_date is not None and item.due_date.strip() == "":
            item.due_date = None
    return report


# ---------------------------------------------------------------------------
# Transcript formatting
# ---------------------------------------------------------------------------


def format_transcript_for_prompt(cleaned_transcript: dict[str, Any]) -> str:
    """Format a cleaned transcript dict into a text block for the prompt."""
    segments = cleaned_transcript.get("segments", [])
    lines: list[str] = []
    for seg in segments:
        speaker = seg.get("speaker", "unknown")
        text = seg.get("text", "")
        lines.append(f"[{speaker}]: {text}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Merge logic (for chunked generation)
# ---------------------------------------------------------------------------


def merge_chunk_results(chunk_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple MinutesReport dicts from chunked generation.

    Takes the metadata (title, datetime, schema_version) from the first chunk
    and unions the list fields across all chunks.
    """
    if not chunk_results:
        raise ValueError("No chunk results to merge")

    if len(chunk_results) == 1:
        return chunk_results[0]

    base = chunk_results[0]
    merged: dict[str, Any] = {
        "schema_version": base.get("schema_version", "v1"),
        "meeting_title": base.get("meeting_title", ""),
        "meeting_datetime": base.get("meeting_datetime", ""),
        "participants": list(base.get("participants", [])),
        "summary": base.get("summary", ""),
        "agenda_items": list(base.get("agenda_items", [])),
        "key_discussion_points": list(base.get("key_discussion_points", [])),
        "decisions": list(base.get("decisions", [])),
        "action_items": list(base.get("action_items", [])),
        "risks_blockers": list(base.get("risks_blockers", [])),
        "open_questions": list(base.get("open_questions", [])),
        "follow_up_needed": base.get("follow_up_needed", False),
    }

    seen_participants: set[str] = set(merged["participants"])

    for chunk in chunk_results[1:]:
        # Merge participants (deduplicate).
        for p in chunk.get("participants", []):
            if p not in seen_participants:
                seen_participants.add(p)
                merged["participants"].append(p)

        # Append summary text.
        chunk_summary = chunk.get("summary", "")
        if chunk_summary:
            merged["summary"] = f"{merged['summary']} {chunk_summary}".strip()

        # Extend list fields.
        merged["agenda_items"].extend(chunk.get("agenda_items", []))
        merged["key_discussion_points"].extend(
            chunk.get("key_discussion_points", [])
        )
        merged["decisions"].extend(chunk.get("decisions", []))
        merged["action_items"].extend(chunk.get("action_items", []))
        merged["risks_blockers"].extend(chunk.get("risks_blockers", []))
        merged["open_questions"].extend(chunk.get("open_questions", []))

        # follow_up_needed is true if any chunk says so.
        if chunk.get("follow_up_needed", False):
            merged["follow_up_needed"] = True

    return merged


# ---------------------------------------------------------------------------
# Action implementations
# ---------------------------------------------------------------------------


def _generate(event: dict[str, Any]) -> dict[str, Any]:
    """Generate minutes from a single cleaned transcript."""
    meeting_id: str = event["meetingId"]
    user_id: str = event["userId"]
    cleaned_transcript: dict[str, Any] = event["cleanedTranscript"]

    logger.info(
        "Generate action: meetingId=%s userId=%s", meeting_id, user_id
    )

    # 1. Load prompt template from S3.
    template = load_prompt_template()

    # 2. Format transcript text for the prompt.
    transcript_text = format_transcript_for_prompt(cleaned_transcript)
    language = cleaned_transcript.get("language", "ja-JP")
    schema_version = _get_prompt_version()

    # 3. Build the full prompt.
    prompt = build_prompt(template, transcript_text, schema_version, language)

    # 4. Invoke Bedrock.
    response_body = invoke_bedrock(prompt)

    # 5. Parse the structured JSON response.
    report_data = extract_json_from_response(response_body)

    # 5b. Fix null values for required string fields that Bedrock may return as null.
    if not report_data.get("meeting_datetime"):
        report_data["meeting_datetime"] = cleaned_transcript.get("startTime", datetime.now(timezone.utc).isoformat())
    if not report_data.get("meeting_title"):
        report_data["meeting_title"] = "Untitled Meeting"
    if not report_data.get("schema_version"):
        report_data["schema_version"] = schema_version
    # Ensure list fields are never null
    for list_field in ["participants", "agenda_items", "key_discussion_points", "decisions", "action_items", "risks_blockers", "open_questions"]:
        if report_data.get(list_field) is None:
            report_data[list_field] = []
    if report_data.get("follow_up_needed") is None:
        report_data["follow_up_needed"] = False
    if not report_data.get("summary"):
        report_data["summary"] = ""

    # 6. Parse into MinutesReport model and enforce confidence review.
    report = MinutesReport.from_dict(report_data)
    report = enforce_confidence_review(report)

    logger.info(
        "Generation complete: meetingId=%s decisions=%d action_items=%d",
        meeting_id,
        len(report.decisions),
        len(report.action_items),
    )

    return report.to_dict()


def _merge(event: dict[str, Any]) -> dict[str, Any]:
    """Merge results from multiple chunked generations."""
    meeting_id: str = event["meetingId"]
    user_id: str = event["userId"]
    chunk_results: list[dict[str, Any]] = event["chunkResults"]

    logger.info(
        "Merge action: meetingId=%s userId=%s chunks=%d",
        meeting_id,
        user_id,
        len(chunk_results),
    )

    merged_data = merge_chunk_results(chunk_results)

    # Parse and enforce confidence review on the merged result.
    report = MinutesReport.from_dict(merged_data)
    report = enforce_confidence_review(report)

    logger.info(
        "Merge complete: meetingId=%s decisions=%d action_items=%d",
        meeting_id,
        len(report.decisions),
        len(report.action_items),
    )

    return report.to_dict()


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler dispatching on the ``action`` field.

    Actions:
        generate – Generate minutes from a cleaned transcript via Bedrock.
        merge    – Merge results from multiple chunked generations.
    """
    action = event.get("action")
    logger.info("Generator handler invoked: action=%s", action)

    if action == "generate":
        return _generate(event)
    elif action == "merge":
        return _merge(event)
    else:
        logger.error("Unknown action: %s", action)
        raise ValueError(f"Unknown action: {action}")

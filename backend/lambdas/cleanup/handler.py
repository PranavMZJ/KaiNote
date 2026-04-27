"""Transcript cleanup Lambda handler for Pranav-meeting-minutes-cleanup.

Handles two actions dispatched by the Step Functions workflow:
- "load": Load raw transcript JSON from S3 and parse into RawTranscript.
- "clean": Remove filler words, normalize formatting, merge adjacent segments
           from the same speaker, calculate token count, store cleaned transcript
           to S3, and return the CleanedTranscript.

Requirements: 6.2, 14.1, 17.1, 17.4
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import boto3
import tiktoken

from backend.models.transcript import (
    CleanedTranscript,
    CleanedTranscriptSegment,
    RawTranscript,
    TranscriptSegment,
)
from backend.utils.s3_keys import transcript_key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_data_bucket() -> str:
    """Return the DATA_BUCKET environment variable (read at call time for testability)."""
    return os.environ.get("DATA_BUCKET", "")

# Filler words to remove (Japanese + English).
# Patterns are compiled as whole-word regexes so partial matches inside real
# words are not affected.
FILLER_WORDS_JA = ["えーと", "あの", "えー", "うーん", "まあ"]
FILLER_WORDS_EN = ["um", "uh", "like", "you know", "basically", "actually", "I mean"]
FILLER_WORDS = FILLER_WORDS_JA + FILLER_WORDS_EN

# Build a single compiled regex that matches any filler word as a whole token.
# For English multi-word fillers (e.g. "you know") we match them first (longer
# patterns before shorter ones).  Japanese fillers don't need word-boundary
# anchors because they are standalone particles.


def _build_filler_pattern() -> re.Pattern[str]:
    """Build a compiled regex that matches filler words/phrases."""
    patterns: list[str] = []
    # Sort by length descending so multi-word fillers match before their parts.
    for filler in sorted(FILLER_WORDS, key=len, reverse=True):
        # Japanese fillers: match the exact string.
        # English fillers: use word boundaries for single words, or flexible
        # whitespace matching for multi-word phrases.
        if any("\u3000" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u309f" or "\u30a0" <= ch <= "\u30ff" for ch in filler):
            patterns.append(re.escape(filler))
        else:
            escaped = re.escape(filler)
            patterns.append(r"\b" + escaped + r"\b")
    return re.compile("|".join(patterns), re.IGNORECASE)


_FILLER_RE = _build_filler_pattern()


# ---------------------------------------------------------------------------
# Core cleanup helpers
# ---------------------------------------------------------------------------


def remove_filler_words(text: str) -> str:
    """Remove filler words from *text* and normalize whitespace."""
    cleaned = _FILLER_RE.sub("", text)
    # Collapse multiple spaces / leading/trailing whitespace.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Remove orphaned punctuation that may result from filler removal
    # (e.g. ", , " → ", ").
    cleaned = re.sub(r"(,\s*)+,", ",", cleaned)
    return cleaned


def normalize_text(text: str) -> str:
    """Normalize formatting: collapse whitespace, strip edges."""
    text = re.sub(r"\s+", " ", text).strip()
    return text


def merge_adjacent_segments(
    segments: list[CleanedTranscriptSegment],
) -> list[CleanedTranscriptSegment]:
    """Merge consecutive segments from the same speaker into one."""
    if not segments:
        return []

    merged: list[CleanedTranscriptSegment] = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        if seg.speaker == prev.speaker:
            merged[-1] = CleanedTranscriptSegment(
                speaker=prev.speaker,
                start_time=prev.start_time,
                end_time=seg.end_time,
                text=f"{prev.text} {seg.text}",
            )
        else:
            merged.append(seg)
    return merged


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken (cl100k_base encoding)."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


# ---------------------------------------------------------------------------
# Action implementations
# ---------------------------------------------------------------------------


def _load_transcript(event: dict[str, Any]) -> dict[str, Any]:
    """Load raw transcript JSON from S3 and return parsed dict."""
    s3_key: str = event["s3Key"]
    meeting_id: str = event["meetingId"]
    user_id: str = event["userId"]

    logger.info(
        "Loading raw transcript",
        extra={"meetingId": meeting_id, "userId": user_id, "s3Key": s3_key},
    )

    bucket = _get_data_bucket()
    s3 = boto3.client("s3")
    try:
        response = s3.get_object(Bucket=bucket, Key=s3_key)
        body = response["Body"].read().decode("utf-8")
    except Exception:
        logger.exception("Failed to load transcript from S3: bucket=%s key=%s", bucket, s3_key)
        raise

    try:
        raw = RawTranscript.from_json(body)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.error(
            "Malformed transcript JSON: %s — bucket=%s key=%s",
            exc,
            bucket,
            s3_key,
        )
        raise ValueError(f"Malformed transcript JSON at s3://{bucket}/{s3_key}: {exc}") from exc

    logger.info(
        "Loaded raw transcript: %d segments",
        len(raw.segments),
        extra={"meetingId": meeting_id},
    )
    return raw.to_dict()


def _clean_transcript(event: dict[str, Any]) -> dict[str, Any]:
    """Clean transcript: remove fillers, normalize, merge, count tokens, store."""
    meeting_id: str = event["meetingId"]
    user_id: str = event["userId"]
    transcript_data: dict[str, Any] = event["transcript"]

    try:
        raw = RawTranscript.from_dict(transcript_data)
    except (KeyError, TypeError) as exc:
        logger.error("Malformed transcript data in clean action: %s", exc)
        raise ValueError(f"Malformed transcript data: {exc}") from exc

    segments_before = len(raw.segments)

    # 1. Remove filler words and normalize each segment.
    cleaned_segments: list[CleanedTranscriptSegment] = []
    for seg in raw.segments:
        text = remove_filler_words(seg.text)
        text = normalize_text(text)
        if text:  # Drop segments that become empty after filler removal.
            cleaned_segments.append(
                CleanedTranscriptSegment(
                    speaker=seg.speaker,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    text=text,
                )
            )

    # 2. Merge adjacent segments from the same speaker.
    merged_segments = merge_adjacent_segments(cleaned_segments)

    # 3. Calculate total token count across all segments.
    all_text = " ".join(seg.text for seg in merged_segments)
    total_tokens = count_tokens(all_text) if all_text else 0

    # 4. Collect unique speakers (preserving order of first appearance).
    seen_speakers: set[str] = set()
    speakers: list[str] = []
    for seg in merged_segments:
        if seg.speaker not in seen_speakers:
            seen_speakers.add(seg.speaker)
            speakers.append(seg.speaker)

    cleaned = CleanedTranscript(
        meeting_id=raw.meeting_id,
        user_id=raw.user_id,
        start_time=raw.start_time,
        end_time=raw.end_time,
        language=raw.language,
        total_token_count=total_tokens,
        speakers=speakers,
        segments=merged_segments,
    )

    # 5. Store cleaned transcript to S3.
    bucket = _get_data_bucket()
    s3 = boto3.client("s3")
    cleaned_key = transcript_key(user_id, meeting_id, variant="cleaned")
    try:
        s3.put_object(
            Bucket=bucket,
            Key=cleaned_key,
            Body=cleaned.to_json().encode("utf-8"),
            ContentType="application/json",
        )
    except Exception:
        logger.exception(
            "Failed to store cleaned transcript: bucket=%s key=%s",
            bucket,
            cleaned_key,
        )
        raise

    # 6. Log cleanup metrics.
    segments_after = len(merged_segments)
    logger.info(
        "Cleanup complete: segments_before=%d segments_after=%d token_count=%d",
        segments_before,
        segments_after,
        total_tokens,
        extra={
            "meetingId": meeting_id,
            "segmentsBefore": segments_before,
            "segmentsAfter": segments_after,
            "tokenCount": total_tokens,
        },
    )

    return cleaned.to_dict()


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler dispatching on the ``action`` field.

    Actions:
        load  – Load raw transcript from S3.
        clean – Clean transcript and store result to S3.
    """
    action = event.get("action")
    logger.info("Cleanup handler invoked: action=%s", action)

    if action == "load":
        return _load_transcript(event)
    elif action == "clean":
        return _clean_transcript(event)
    else:
        logger.error("Unknown action: %s", action)
        raise ValueError(f"Unknown action: {action}")

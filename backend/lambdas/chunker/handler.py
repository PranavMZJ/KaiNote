"""Transcript chunker Lambda handler for Pranav-meeting-minutes-chunker.

Accepts a cleaned transcript from Step Functions, checks the totalTokenCount
against a 10,000-token threshold, and splits segments into chunks that each
fit within a configurable token limit while preserving segment boundaries.

Requirements: 6.3
"""

from __future__ import annotations

import logging
import os
from typing import Any

import tiktoken

from backend.models.transcript import CleanedTranscript, CleanedTranscriptSegment

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configurable maximum tokens per chunk.  The Bedrock context window for
# Claude 3 Haiku is ~180,000 tokens, but we leave room for the prompt
# template (~2,000 tokens) and keep chunks manageable.
DEFAULT_MAX_CHUNK_TOKENS = 8000

# Token threshold below which the transcript is returned as a single chunk.
TOKEN_THRESHOLD = 10_000


def _get_max_chunk_tokens() -> int:
    """Return the max chunk token limit from env or default."""
    return int(os.environ.get("MAX_CHUNK_TOKENS", str(DEFAULT_MAX_CHUNK_TOKENS)))


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken (cl100k_base encoding)."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _segment_token_count(segment: CleanedTranscriptSegment) -> int:
    """Return the token count for a single segment's text."""
    return count_tokens(segment.text)


def chunk_segments(
    segments: list[CleanedTranscriptSegment],
    max_chunk_tokens: int,
) -> list[dict[str, Any]]:
    """Split *segments* into chunks respecting *max_chunk_tokens*.

    Each chunk is a dict with:
      - ``segments``: list of segment dicts
      - ``tokenCount``: total token count for the chunk

    Segment boundaries are never broken — a segment is always placed in
    exactly one chunk.  If a single segment exceeds *max_chunk_tokens* it
    is placed alone in its own chunk (we cannot split it further without
    breaking the boundary rule).
    """
    if not segments:
        return []

    chunks: list[dict[str, Any]] = []
    current_segments: list[CleanedTranscriptSegment] = []
    current_tokens = 0

    for segment in segments:
        seg_tokens = _segment_token_count(segment)

        # If adding this segment would exceed the limit, flush the current
        # chunk first (unless the current chunk is empty — that means the
        # single segment itself exceeds the limit and must go alone).
        if current_segments and current_tokens + seg_tokens > max_chunk_tokens:
            chunks.append({
                "segments": [s.to_dict() for s in current_segments],
                "tokenCount": current_tokens,
            })
            current_segments = []
            current_tokens = 0

        current_segments.append(segment)
        current_tokens += seg_tokens

    # Flush remaining segments.
    if current_segments:
        chunks.append({
            "segments": [s.to_dict() for s in current_segments],
            "tokenCount": current_tokens,
        })

    return chunks


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler invoked by Step Functions.

    Expected event keys:
      - ``meetingId`` (str)
      - ``userId`` (str)
      - ``cleanedTranscript`` (dict): serialised CleanedTranscript

    Returns a dict with:
      - ``meetingId``
      - ``userId``
      - ``chunks``: list of chunk objects (each with segments + tokenCount)
      - ``totalChunks``: number of chunks produced
    """
    meeting_id: str = event["meetingId"]
    user_id: str = event["userId"]
    transcript_data: dict[str, Any] = event["cleanedTranscript"]

    logger.info("Chunker invoked: meetingId=%s userId=%s", meeting_id, user_id)

    cleaned = CleanedTranscript.from_dict(transcript_data)
    total_tokens = cleaned.total_token_count
    max_chunk_tokens = _get_max_chunk_tokens()

    logger.info(
        "Transcript stats: totalTokenCount=%d threshold=%d maxChunkTokens=%d segments=%d",
        total_tokens,
        TOKEN_THRESHOLD,
        max_chunk_tokens,
        len(cleaned.segments),
    )

    # If under the threshold, return the entire transcript as a single chunk.
    if total_tokens <= TOKEN_THRESHOLD:
        chunks = [{
            "segments": [s.to_dict() for s in cleaned.segments],
            "tokenCount": total_tokens,
        }]
    else:
        chunks = chunk_segments(cleaned.segments, max_chunk_tokens)

    logger.info(
        "Chunking complete: totalChunks=%d meetingId=%s",
        len(chunks),
        meeting_id,
    )

    return {
        "meetingId": meeting_id,
        "userId": user_id,
        "chunks": chunks,
        "totalChunks": len(chunks),
    }

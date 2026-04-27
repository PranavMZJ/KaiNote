"""Unit tests for the transcript chunker Lambda handler.

Tests cover:
- Single-chunk path (totalTokenCount ≤ threshold)
- Multi-chunk path (totalTokenCount > threshold)
- Segment boundary preservation
- Empty transcript handling
- Oversized single segment handling
- Handler dispatch and return shape

Requirements: 6.3
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from backend.lambdas.chunker.handler import (
    DEFAULT_MAX_CHUNK_TOKENS,
    TOKEN_THRESHOLD,
    chunk_segments,
    count_tokens,
    handler,
)
from backend.models.transcript import CleanedTranscript, CleanedTranscriptSegment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seg(speaker: str, text: str, start: float = 0.0, end: float = 1.0) -> CleanedTranscriptSegment:
    return CleanedTranscriptSegment(speaker=speaker, start_time=start, end_time=end, text=text)


def _make_cleaned_transcript(
    segments: list[CleanedTranscriptSegment] | None = None,
    total_token_count: int = 500,
) -> CleanedTranscript:
    if segments is None:
        segments = [_seg("spk_0", "Hello world")]
    return CleanedTranscript(
        meeting_id="m-1",
        user_id="u-1",
        start_time="2024-01-15T10:00:00Z",
        end_time="2024-01-15T11:00:00Z",
        language="ja-JP",
        total_token_count=total_token_count,
        speakers=["spk_0"],
        segments=segments,
    )


def _build_event(cleaned: CleanedTranscript) -> dict[str, Any]:
    return {
        "meetingId": cleaned.meeting_id,
        "userId": cleaned.user_id,
        "cleanedTranscript": cleaned.to_dict(),
    }


# ---------------------------------------------------------------------------
# count_tokens
# ---------------------------------------------------------------------------


class TestCountTokens:
    def test_non_empty(self):
        assert count_tokens("Hello world") > 0

    def test_empty(self):
        assert count_tokens("") == 0


# ---------------------------------------------------------------------------
# chunk_segments — unit tests
# ---------------------------------------------------------------------------


class TestChunkSegments:
    def test_empty_segments(self):
        assert chunk_segments([], 8000) == []

    def test_single_segment_fits(self):
        segs = [_seg("spk_0", "Hello")]
        chunks = chunk_segments(segs, 8000)
        assert len(chunks) == 1
        assert len(chunks[0]["segments"]) == 1
        assert chunks[0]["tokenCount"] > 0

    def test_multiple_segments_fit_in_one_chunk(self):
        segs = [_seg("spk_0", "Hello"), _seg("spk_1", "World")]
        chunks = chunk_segments(segs, 8000)
        assert len(chunks) == 1
        assert len(chunks[0]["segments"]) == 2

    def test_segments_split_across_chunks(self):
        # Use a very small limit so each segment gets its own chunk.
        segs = [
            _seg("spk_0", "This is a reasonably long sentence for testing purposes"),
            _seg("spk_1", "Another reasonably long sentence for testing purposes"),
        ]
        # Set limit to the token count of a single segment so the second
        # segment forces a new chunk.
        single_tokens = count_tokens(segs[0].text)
        chunks = chunk_segments(segs, single_tokens)
        assert len(chunks) == 2
        assert len(chunks[0]["segments"]) == 1
        assert len(chunks[1]["segments"]) == 1

    def test_preserves_segment_order(self):
        segs = [_seg("spk_0", f"Segment {i}") for i in range(5)]
        # Tiny limit to force many chunks.
        chunks = chunk_segments(segs, 1)
        all_texts = [
            s["text"] for chunk in chunks for s in chunk["segments"]
        ]
        assert all_texts == [f"Segment {i}" for i in range(5)]

    def test_oversized_single_segment(self):
        """A segment larger than max_chunk_tokens still gets its own chunk."""
        big_text = "word " * 500  # many tokens
        segs = [_seg("spk_0", big_text.strip())]
        chunks = chunk_segments(segs, 5)  # very small limit
        assert len(chunks) == 1
        assert chunks[0]["tokenCount"] > 5

    def test_token_count_per_chunk_within_limit(self):
        segs = [_seg("spk_0", f"Segment number {i} with some text") for i in range(20)]
        limit = 30
        chunks = chunk_segments(segs, limit)
        # Every chunk except those with a single oversized segment should
        # respect the limit.
        for chunk in chunks:
            if len(chunk["segments"]) > 1:
                assert chunk["tokenCount"] <= limit


# ---------------------------------------------------------------------------
# handler — below threshold (single chunk)
# ---------------------------------------------------------------------------


class TestHandlerBelowThreshold:
    def test_returns_single_chunk(self):
        segs = [_seg("spk_0", "Hello world")]
        cleaned = _make_cleaned_transcript(segments=segs, total_token_count=500)
        result = handler(_build_event(cleaned), None)

        assert result["meetingId"] == "m-1"
        assert result["userId"] == "u-1"
        assert result["totalChunks"] == 1
        assert len(result["chunks"]) == 1
        assert result["chunks"][0]["tokenCount"] == 500

    def test_at_threshold_returns_single_chunk(self):
        segs = [_seg("spk_0", "Hello")]
        cleaned = _make_cleaned_transcript(segments=segs, total_token_count=TOKEN_THRESHOLD)
        result = handler(_build_event(cleaned), None)
        assert result["totalChunks"] == 1

    def test_empty_transcript(self):
        cleaned = _make_cleaned_transcript(segments=[], total_token_count=0)
        result = handler(_build_event(cleaned), None)
        assert result["totalChunks"] == 1
        assert result["chunks"][0]["segments"] == []
        assert result["chunks"][0]["tokenCount"] == 0


# ---------------------------------------------------------------------------
# handler — above threshold (multiple chunks)
# ---------------------------------------------------------------------------


class TestHandlerAboveThreshold:
    def test_chunks_created_above_threshold(self):
        # Create segments whose actual token counts will exceed the default
        # max chunk size when combined.
        segs = [_seg("spk_0", f"Segment {i} with some filler text") for i in range(10)]
        cleaned = _make_cleaned_transcript(
            segments=segs,
            total_token_count=TOKEN_THRESHOLD + 1,
        )
        result = handler(_build_event(cleaned), None)
        assert result["totalChunks"] >= 1
        # All original segments should be present across chunks.
        all_seg_texts = [
            s["text"] for chunk in result["chunks"] for s in chunk["segments"]
        ]
        assert len(all_seg_texts) == 10

    def test_respects_max_chunk_tokens_env(self):
        os.environ["MAX_CHUNK_TOKENS"] = "5"
        try:
            segs = [_seg("spk_0", f"Segment {i} with some text") for i in range(5)]
            cleaned = _make_cleaned_transcript(
                segments=segs,
                total_token_count=TOKEN_THRESHOLD + 1,
            )
            result = handler(_build_event(cleaned), None)
            # With a 5-token limit, each segment should be its own chunk.
            assert result["totalChunks"] == 5
        finally:
            del os.environ["MAX_CHUNK_TOKENS"]

    def test_segment_order_preserved(self):
        segs = [_seg("spk_0", f"Segment {i}") for i in range(6)]
        cleaned = _make_cleaned_transcript(
            segments=segs,
            total_token_count=TOKEN_THRESHOLD + 1,
        )
        os.environ["MAX_CHUNK_TOKENS"] = "5"
        try:
            result = handler(_build_event(cleaned), None)
            all_texts = [
                s["text"] for chunk in result["chunks"] for s in chunk["segments"]
            ]
            assert all_texts == [f"Segment {i}" for i in range(6)]
        finally:
            del os.environ["MAX_CHUNK_TOKENS"]

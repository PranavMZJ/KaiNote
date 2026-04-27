"""Unit tests for the transcript cleanup Lambda handler.

Tests cover:
- Filler word removal (English and Japanese)
- Text normalization
- Adjacent segment merging
- Token counting
- Load action (S3 integration via moto)
- Clean action (S3 integration via moto)
- Malformed JSON error handling
- Handler dispatch

Requirements: 6.2, 14.1, 17.1, 17.4
"""

from __future__ import annotations

import json
import os

import boto3
import pytest
from moto import mock_aws

from backend.lambdas.cleanup.handler import (
    count_tokens,
    handler,
    merge_adjacent_segments,
    normalize_text,
    remove_filler_words,
)
from backend.models.transcript import (
    CleanedTranscriptSegment,
    RawTranscript,
    TranscriptMetadata,
    TranscriptSegment,
)

TEST_BUCKET = "pranav-meeting-minutes-data"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_transcript(**overrides) -> RawTranscript:
    defaults = dict(
        meeting_id="m-1",
        user_id="u-1",
        start_time="2024-01-15T10:00:00Z",
        end_time="2024-01-15T11:00:00Z",
        language="ja-JP",
        segments=[
            TranscriptSegment("seg-001", "spk_0", 0.5, 3.2, "Hello world", False, 0.95),
        ],
        metadata=TranscriptMetadata(16000, "pcm", "sess-1"),
    )
    defaults.update(overrides)
    return RawTranscript(**defaults)


# ---------------------------------------------------------------------------
# remove_filler_words
# ---------------------------------------------------------------------------


class TestRemoveFillerWords:
    def test_removes_english_fillers(self):
        assert remove_filler_words("um I think uh we should") == "I think we should"

    def test_removes_multi_word_english_fillers(self):
        result = remove_filler_words("you know the project is basically done")
        assert "you know" not in result
        assert "basically" not in result
        assert "the project is" in result
        assert "done" in result

    def test_removes_japanese_fillers(self):
        result = remove_filler_words("えーと会議を始めましょう")
        assert "えーと" not in result
        assert "会議を始めましょう" in result

    def test_removes_mixed_fillers(self):
        result = remove_filler_words("えー um let's start あの the meeting")
        assert "えー" not in result
        assert "um" not in result
        assert "あの" not in result
        assert "start" in result
        assert "the meeting" in result

    def test_preserves_text_without_fillers(self):
        text = "The project deadline is next Friday"
        assert remove_filler_words(text) == text

    def test_empty_string(self):
        assert remove_filler_words("") == ""

    def test_all_fillers_returns_empty(self):
        result = remove_filler_words("um uh like")
        assert result == ""

    def test_case_insensitive_english(self):
        result = remove_filler_words("Um I think UH we should")
        assert "Um" not in result
        assert "UH" not in result

    def test_does_not_remove_partial_word_match(self):
        # "like" should not remove "likely"
        result = remove_filler_words("This is likely correct")
        assert "likely" in result


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------


class TestNormalizeText:
    def test_collapses_whitespace(self):
        assert normalize_text("hello   world") == "hello world"

    def test_strips_edges(self):
        assert normalize_text("  hello  ") == "hello"

    def test_handles_tabs_and_newlines(self):
        assert normalize_text("hello\t\nworld") == "hello world"


# ---------------------------------------------------------------------------
# merge_adjacent_segments
# ---------------------------------------------------------------------------


class TestMergeAdjacentSegments:
    def test_merges_same_speaker(self):
        segs = [
            CleanedTranscriptSegment("spk_0", 0.0, 1.0, "Hello"),
            CleanedTranscriptSegment("spk_0", 1.0, 2.0, "world"),
        ]
        merged = merge_adjacent_segments(segs)
        assert len(merged) == 1
        assert merged[0].text == "Hello world"
        assert merged[0].start_time == 0.0
        assert merged[0].end_time == 2.0

    def test_does_not_merge_different_speakers(self):
        segs = [
            CleanedTranscriptSegment("spk_0", 0.0, 1.0, "Hello"),
            CleanedTranscriptSegment("spk_1", 1.0, 2.0, "Hi"),
        ]
        merged = merge_adjacent_segments(segs)
        assert len(merged) == 2

    def test_empty_list(self):
        assert merge_adjacent_segments([]) == []

    def test_single_segment(self):
        segs = [CleanedTranscriptSegment("spk_0", 0.0, 1.0, "Hello")]
        merged = merge_adjacent_segments(segs)
        assert len(merged) == 1
        assert merged[0].text == "Hello"

    def test_alternating_speakers(self):
        segs = [
            CleanedTranscriptSegment("spk_0", 0.0, 1.0, "A"),
            CleanedTranscriptSegment("spk_1", 1.0, 2.0, "B"),
            CleanedTranscriptSegment("spk_0", 2.0, 3.0, "C"),
        ]
        merged = merge_adjacent_segments(segs)
        assert len(merged) == 3


# ---------------------------------------------------------------------------
# count_tokens
# ---------------------------------------------------------------------------


class TestCountTokens:
    def test_non_empty_text(self):
        tokens = count_tokens("Hello world")
        assert tokens > 0

    def test_empty_text(self):
        assert count_tokens("") == 0


# ---------------------------------------------------------------------------
# handler — load action (with moto S3)
# ---------------------------------------------------------------------------


class TestHandlerLoad:
    @mock_aws
    def test_load_returns_parsed_transcript(self):
        os.environ["DATA_BUCKET"] = TEST_BUCKET
        s3 = boto3.client("s3", region_name="ap-northeast-1")
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
        )

        raw = _make_raw_transcript()
        s3.put_object(Bucket=TEST_BUCKET, Key="users/u-1/transcripts/m-1/raw.json", Body=raw.to_json())

        result = handler(
            {"action": "load", "meetingId": "m-1", "userId": "u-1", "s3Key": "users/u-1/transcripts/m-1/raw.json"},
            None,
        )
        assert result["meetingId"] == "m-1"
        assert len(result["segments"]) == 1

    @mock_aws
    def test_load_malformed_json_raises(self):
        os.environ["DATA_BUCKET"] = TEST_BUCKET
        s3 = boto3.client("s3", region_name="ap-northeast-1")
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
        )
        s3.put_object(Bucket=TEST_BUCKET, Key="bad.json", Body="not json{{{")

        with pytest.raises(ValueError, match="Malformed transcript JSON"):
            handler(
                {"action": "load", "meetingId": "m-1", "userId": "u-1", "s3Key": "bad.json"},
                None,
            )


# ---------------------------------------------------------------------------
# handler — clean action (with moto S3)
# ---------------------------------------------------------------------------


class TestHandlerClean:
    @mock_aws
    def test_clean_stores_and_returns_cleaned_transcript(self):
        os.environ["DATA_BUCKET"] = TEST_BUCKET
        s3 = boto3.client("s3", region_name="ap-northeast-1")
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
        )

        raw = _make_raw_transcript(
            segments=[
                TranscriptSegment("seg-001", "spk_0", 0.0, 1.0, "um Hello world", False, 0.95),
                TranscriptSegment("seg-002", "spk_0", 1.0, 2.0, "uh how are you", False, 0.90),
                TranscriptSegment("seg-003", "spk_1", 2.0, 3.0, "I'm fine", False, 0.92),
            ],
        )

        result = handler(
            {
                "action": "clean",
                "meetingId": "m-1",
                "userId": "u-1",
                "transcript": raw.to_dict(),
            },
            None,
        )

        # Segments from spk_0 should be merged.
        assert result["meetingId"] == "m-1"
        assert len(result["segments"]) == 2  # spk_0 merged, spk_1 separate
        assert result["totalTokenCount"] > 0
        assert "spk_0" in result["speakers"]
        assert "spk_1" in result["speakers"]

        # Verify filler words removed.
        for seg in result["segments"]:
            text_lower = seg["text"].lower()
            assert "um " not in f" {text_lower} " or "um" not in text_lower.split()
            assert "uh " not in f" {text_lower} " or "uh" not in text_lower.split()

        # Verify stored in S3.
        stored = s3.get_object(
            Bucket=TEST_BUCKET,
            Key="users/u-1/transcripts/m-1/cleaned.json",
        )
        stored_data = json.loads(stored["Body"].read())
        assert stored_data["meetingId"] == "m-1"

    @mock_aws
    def test_clean_empty_transcript(self):
        os.environ["DATA_BUCKET"] = TEST_BUCKET
        s3 = boto3.client("s3", region_name="ap-northeast-1")
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
        )

        raw = _make_raw_transcript(segments=[])
        result = handler(
            {
                "action": "clean",
                "meetingId": "m-1",
                "userId": "u-1",
                "transcript": raw.to_dict(),
            },
            None,
        )
        assert result["segments"] == []
        assert result["totalTokenCount"] == 0
        assert result["speakers"] == []

    @mock_aws
    def test_clean_all_filler_segments_dropped(self):
        os.environ["DATA_BUCKET"] = TEST_BUCKET
        s3 = boto3.client("s3", region_name="ap-northeast-1")
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
        )

        raw = _make_raw_transcript(
            segments=[
                TranscriptSegment("seg-001", "spk_0", 0.0, 1.0, "um uh like", False, 0.5),
            ],
        )
        result = handler(
            {
                "action": "clean",
                "meetingId": "m-1",
                "userId": "u-1",
                "transcript": raw.to_dict(),
            },
            None,
        )
        assert result["segments"] == []
        assert result["totalTokenCount"] == 0


# ---------------------------------------------------------------------------
# handler — unknown action
# ---------------------------------------------------------------------------


class TestHandlerDispatch:
    def test_unknown_action_raises(self):
        with pytest.raises(ValueError, match="Unknown action"):
            handler({"action": "invalid"}, None)

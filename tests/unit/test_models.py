"""Unit tests for data models: transcript, minutes, and meeting status."""

import json
import pytest

from backend.models.transcript import (
    RawTranscript,
    CleanedTranscript,
    TranscriptSegment,
    CleanedTranscriptSegment,
    TranscriptMetadata,
)
from backend.models.minutes import MinutesReport, Decision, ActionItem
from backend.models.meeting_status import MeetingStatus, MeetingStatusEnum


# ---------------------------------------------------------------------------
# TranscriptSegment
# ---------------------------------------------------------------------------

class TestTranscriptSegment:
    def test_round_trip(self):
        seg = TranscriptSegment(
            segment_id="seg-001", speaker="spk_0",
            start_time=0.5, end_time=3.2,
            text="Hello", is_partial=False, confidence=0.95,
        )
        assert TranscriptSegment.from_dict(seg.to_dict()) == seg

    def test_to_dict_uses_camel_case_keys(self):
        seg = TranscriptSegment(
            segment_id="seg-001", speaker="spk_0",
            start_time=0.5, end_time=3.2,
            text="Hello", is_partial=False, confidence=0.95,
        )
        d = seg.to_dict()
        assert "segmentId" in d
        assert "startTime" in d
        assert "endTime" in d
        assert "isPartial" in d


# ---------------------------------------------------------------------------
# RawTranscript
# ---------------------------------------------------------------------------

class TestRawTranscript:
    def _make_raw(self) -> RawTranscript:
        return RawTranscript(
            meeting_id="m-1", user_id="u-1",
            start_time="2024-01-15T10:00:00Z",
            end_time="2024-01-15T11:00:00Z",
            language="ja-JP",
            segments=[
                TranscriptSegment("seg-001", "spk_0", 0.5, 3.2, "Hello", False, 0.95),
            ],
            metadata=TranscriptMetadata(16000, "pcm", "sess-1"),
        )

    def test_json_round_trip(self):
        raw = self._make_raw()
        assert RawTranscript.from_json(raw.to_json()) == raw

    def test_from_dict_without_metadata(self):
        data = {
            "meetingId": "m-1", "userId": "u-1",
            "startTime": "2024-01-15T10:00:00Z",
            "endTime": "2024-01-15T11:00:00Z",
            "language": "en-US", "segments": [],
        }
        raw = RawTranscript.from_dict(data)
        assert raw.metadata is None
        assert raw.segments == []

    def test_to_dict_omits_metadata_when_none(self):
        raw = RawTranscript(
            meeting_id="m-1", user_id="u-1",
            start_time="t0", end_time="t1",
            language="en-US",
        )
        d = raw.to_dict()
        assert "metadata" not in d


# ---------------------------------------------------------------------------
# CleanedTranscript
# ---------------------------------------------------------------------------

class TestCleanedTranscript:
    def test_json_round_trip(self):
        cleaned = CleanedTranscript(
            meeting_id="m-1", user_id="u-1",
            start_time="2024-01-15T10:00:00Z",
            end_time="2024-01-15T11:00:00Z",
            language="ja-JP", total_token_count=8500,
            speakers=["spk_0", "spk_1"],
            segments=[
                CleanedTranscriptSegment("spk_0", 0.5, 3.2, "Hello"),
            ],
        )
        assert CleanedTranscript.from_json(cleaned.to_json()) == cleaned

    def test_empty_segments(self):
        cleaned = CleanedTranscript(
            meeting_id="m-1", user_id="u-1",
            start_time="t0", end_time="t1",
            language="en-US", total_token_count=0,
        )
        d = cleaned.to_dict()
        assert d["segments"] == []
        assert d["speakers"] == []


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

class TestDecision:
    def test_round_trip_with_optional_fields(self):
        dec = Decision(
            decision="Use React", rationale="Team knows it",
            evidence="Alice said so", owner="Alice",
            timestamp="2024-01-15T10:30:00Z",
        )
        assert Decision.from_dict(dec.to_dict()) == dec

    def test_round_trip_without_optional_fields(self):
        dec = Decision(decision="Use React", rationale="Team knows it", evidence="Alice said so")
        d = dec.to_dict()
        assert d["owner"] is None
        assert d["timestamp"] is None
        assert Decision.from_dict(d) == dec


# ---------------------------------------------------------------------------
# ActionItem
# ---------------------------------------------------------------------------

class TestActionItem:
    def test_round_trip_full(self):
        item = ActionItem(
            task="Set up repo", priority="high", evidence="Bob volunteered",
            confidence=0.9, needs_human_review=False,
            owner="Bob", due_date="2024-01-20",
            timestamp="2024-01-15T10:35:00Z",
        )
        assert ActionItem.from_dict(item.to_dict()) == item

    def test_round_trip_nullable_fields(self):
        item = ActionItem(
            task="TBD", priority="low", evidence="mentioned briefly",
            confidence=0.4, needs_human_review=True,
        )
        d = item.to_dict()
        assert d["owner"] is None
        assert d["due_date"] is None
        assert ActionItem.from_dict(d) == item

    def test_priority_values(self):
        for p in ("low", "medium", "high"):
            item = ActionItem(task="t", priority=p, evidence="e", confidence=0.5, needs_human_review=True)
            assert item.to_dict()["priority"] == p


# ---------------------------------------------------------------------------
# MinutesReport
# ---------------------------------------------------------------------------

class TestMinutesReport:
    def _make_report(self) -> MinutesReport:
        return MinutesReport(
            schema_version="v1",
            meeting_title="Sprint Planning",
            meeting_datetime="2024-01-15T10:00:00Z",
            participants=["Alice", "Bob"],
            summary="Discussed sprint goals.",
            agenda_items=["Review backlog"],
            key_discussion_points=["Velocity target"],
            decisions=[Decision("Use React", "Team expertise", "Alice said...", "Alice", "2024-01-15T10:30:00Z")],
            action_items=[ActionItem("Set up repo", "high", "Bob volunteered", 0.9, False, "Bob", "2024-01-20")],
            risks_blockers=["Tight deadline"],
            open_questions=["Who handles deployment?"],
            follow_up_needed=True,
        )

    def test_json_round_trip(self):
        report = self._make_report()
        assert MinutesReport.from_json(report.to_json()) == report

    def test_empty_lists(self):
        report = MinutesReport(
            schema_version="v1", meeting_title="Empty",
            meeting_datetime="2024-01-15T10:00:00Z",
            participants=[], summary="Nothing happened.",
            agenda_items=[], key_discussion_points=[],
            decisions=[], action_items=[],
            risks_blockers=[], open_questions=[],
            follow_up_needed=False,
        )
        assert MinutesReport.from_json(report.to_json()) == report

    def test_unicode_content(self):
        report = MinutesReport(
            schema_version="v1",
            meeting_title="スプリント計画",
            meeting_datetime="2024-01-15T10:00:00Z",
            participants=["田中", "鈴木"],
            summary="スプリントの目標を議論しました。",
            agenda_items=["バックログレビュー"],
            key_discussion_points=["ベロシティ目標"],
            decisions=[], action_items=[],
            risks_blockers=[], open_questions=[],
            follow_up_needed=False,
        )
        restored = MinutesReport.from_json(report.to_json())
        assert restored.meeting_title == "スプリント計画"
        assert restored == report


# ---------------------------------------------------------------------------
# MeetingStatus
# ---------------------------------------------------------------------------

class TestMeetingStatus:
    def test_json_round_trip(self):
        status = MeetingStatus(
            meeting_id="m-1", user_id="u-1",
            status=MeetingStatusEnum.PROCESSING,
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:05:00Z",
            step_function_execution_arn="arn:aws:states:ap-northeast-1:123:execution:wf:exec-1",
            current_step="GenerateMinutes",
            transcript_key="users/u-1/transcripts/m-1/raw.json",
            report_key="users/u-1/reports/m-1/minutes.json",
        )
        assert MeetingStatus.from_json(status.to_json()) == status

    def test_status_enum_values(self):
        for val in ("pending", "processing", "completed", "failed"):
            assert MeetingStatusEnum(val).value == val

    def test_optional_fields_default_to_none(self):
        status = MeetingStatus(
            meeting_id="m-1", user_id="u-1",
            status=MeetingStatusEnum.PENDING,
            created_at="t0", updated_at="t0",
        )
        d = status.to_dict()
        assert d["stepFunctionExecutionArn"] is None
        assert d["currentStep"] is None
        assert d["error"] is None
        assert d["transcriptKey"] is None
        assert d["reportKey"] is None
        assert MeetingStatus.from_dict(d) == status

    def test_failed_status_with_error(self):
        status = MeetingStatus(
            meeting_id="m-1", user_id="u-1",
            status=MeetingStatusEnum.FAILED,
            created_at="t0", updated_at="t1",
            error="Schema validation failed after 3 attempts",
        )
        d = status.to_dict()
        assert d["status"] == "failed"
        assert d["error"] == "Schema validation failed after 3 attempts"

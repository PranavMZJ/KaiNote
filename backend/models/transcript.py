"""Data models for raw and cleaned transcripts.

Matches the design document's Raw Transcript and Cleaned Transcript schemas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TranscriptMetadata:
    """Metadata about the transcription session."""

    sample_rate: int
    encoding: str
    transcribe_session_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sampleRate": self.sample_rate,
            "encoding": self.encoding,
            "transcribeSessionId": self.transcribe_session_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptMetadata:
        return cls(
            sample_rate=data["sampleRate"],
            encoding=data["encoding"],
            transcribe_session_id=data["transcribeSessionId"],
        )


@dataclass
class TranscriptSegment:
    """A single segment from the raw transcript."""

    segment_id: str
    speaker: str
    start_time: float
    end_time: float
    text: str
    is_partial: bool
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "segmentId": self.segment_id,
            "speaker": self.speaker,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "text": self.text,
            "isPartial": self.is_partial,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptSegment:
        return cls(
            segment_id=data["segmentId"],
            speaker=data["speaker"],
            start_time=data["startTime"],
            end_time=data["endTime"],
            text=data["text"],
            is_partial=data["isPartial"],
            confidence=data["confidence"],
        )


@dataclass
class CleanedTranscriptSegment:
    """A single segment from the cleaned transcript (no segmentId, isPartial, or confidence)."""

    speaker: str
    start_time: float
    end_time: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CleanedTranscriptSegment:
        return cls(
            speaker=data["speaker"],
            start_time=data["startTime"],
            end_time=data["endTime"],
            text=data["text"],
        )


@dataclass
class RawTranscript:
    """Raw transcript from Amazon Transcribe Streaming."""

    meeting_id: str
    user_id: str
    start_time: str
    end_time: str
    language: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    metadata: Optional[TranscriptMetadata] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "meetingId": self.meeting_id,
            "userId": self.user_id,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "language": self.language,
            "segments": [seg.to_dict() for seg in self.segments],
        }
        if self.metadata is not None:
            result["metadata"] = self.metadata.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RawTranscript:
        metadata = None
        if "metadata" in data and data["metadata"] is not None:
            metadata = TranscriptMetadata.from_dict(data["metadata"])
        return cls(
            meeting_id=data["meetingId"],
            user_id=data["userId"],
            start_time=data["startTime"],
            end_time=data["endTime"],
            language=data["language"],
            segments=[TranscriptSegment.from_dict(s) for s in data.get("segments", [])],
            metadata=metadata,
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> RawTranscript:
        return cls.from_dict(json.loads(json_str))


@dataclass
class CleanedTranscript:
    """Normalized transcript after cleanup processing."""

    meeting_id: str
    user_id: str
    start_time: str
    end_time: str
    language: str
    total_token_count: int
    speakers: list[str] = field(default_factory=list)
    segments: list[CleanedTranscriptSegment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "meetingId": self.meeting_id,
            "userId": self.user_id,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "language": self.language,
            "totalTokenCount": self.total_token_count,
            "speakers": list(self.speakers),
            "segments": [seg.to_dict() for seg in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CleanedTranscript:
        return cls(
            meeting_id=data["meetingId"],
            user_id=data["userId"],
            start_time=data["startTime"],
            end_time=data["endTime"],
            language=data["language"],
            total_token_count=data["totalTokenCount"],
            speakers=list(data.get("speakers", [])),
            segments=[CleanedTranscriptSegment.from_dict(s) for s in data.get("segments", [])],
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> CleanedTranscript:
        return cls.from_dict(json.loads(json_str))

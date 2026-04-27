"""Data models for the Minutes Schema (v1).

Matches the design document's Minutes Schema JSON structure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Decision:
    """A decision extracted from the meeting transcript."""

    decision: str
    rationale: str
    evidence: str
    owner: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "rationale": self.rationale,
            "owner": self.owner,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Decision:
        return cls(
            decision=data["decision"],
            rationale=data["rationale"],
            evidence=data["evidence"],
            owner=data.get("owner"),
            timestamp=data.get("timestamp"),
        )


@dataclass
class ActionItem:
    """An action item extracted from the meeting transcript."""

    task: str
    priority: str  # "low", "medium", or "high"
    evidence: str
    confidence: float  # 0.0 to 1.0
    needs_human_review: bool
    owner: Optional[str] = None
    due_date: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "owner": self.owner,
            "due_date": self.due_date,
            "priority": self.priority,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "needs_human_review": self.needs_human_review,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionItem:
        return cls(
            task=data["task"],
            priority=data["priority"],
            evidence=data["evidence"],
            confidence=data["confidence"],
            needs_human_review=data["needs_human_review"],
            owner=data.get("owner"),
            due_date=data.get("due_date"),
            timestamp=data.get("timestamp"),
        )


@dataclass
class MinutesReport:
    """Complete meeting minutes report conforming to the Minutes Schema."""

    schema_version: str
    meeting_title: str
    meeting_datetime: str
    participants: list[str]
    summary: str
    agenda_items: list[str]
    key_discussion_points: list[str]
    decisions: list[Decision]
    action_items: list[ActionItem]
    risks_blockers: list[str]
    open_questions: list[str]
    follow_up_needed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "meeting_title": self.meeting_title,
            "meeting_datetime": self.meeting_datetime,
            "participants": list(self.participants),
            "summary": self.summary,
            "agenda_items": list(self.agenda_items),
            "key_discussion_points": list(self.key_discussion_points),
            "decisions": [d.to_dict() for d in self.decisions],
            "action_items": [a.to_dict() for a in self.action_items],
            "risks_blockers": list(self.risks_blockers),
            "open_questions": list(self.open_questions),
            "follow_up_needed": self.follow_up_needed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MinutesReport:
        return cls(
            schema_version=data["schema_version"],
            meeting_title=data["meeting_title"],
            meeting_datetime=data["meeting_datetime"],
            participants=list(data["participants"]),
            summary=data["summary"],
            agenda_items=list(data["agenda_items"]),
            key_discussion_points=list(data["key_discussion_points"]),
            decisions=[Decision.from_dict(d) for d in data.get("decisions", [])],
            action_items=[ActionItem.from_dict(a) for a in data.get("action_items", [])],
            risks_blockers=list(data["risks_blockers"]),
            open_questions=list(data["open_questions"]),
            follow_up_needed=data["follow_up_needed"],
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> MinutesReport:
        return cls.from_dict(json.loads(json_str))

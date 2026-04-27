"""Data model for meeting processing status.

Tracks the state of a meeting through the post-processing workflow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class MeetingStatusEnum(str, Enum):
    """Possible states for a meeting's processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MeetingStatus:
    """Status of a meeting's processing workflow."""

    meeting_id: str
    user_id: str
    status: MeetingStatusEnum
    created_at: str
    updated_at: str
    step_function_execution_arn: Optional[str] = None
    current_step: Optional[str] = None
    error: Optional[str] = None
    transcript_key: Optional[str] = None
    report_key: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "meetingId": self.meeting_id,
            "userId": self.user_id,
            "status": self.status.value,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "stepFunctionExecutionArn": self.step_function_execution_arn,
            "currentStep": self.current_step,
            "error": self.error,
            "transcriptKey": self.transcript_key,
            "reportKey": self.report_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MeetingStatus:
        return cls(
            meeting_id=data["meetingId"],
            user_id=data["userId"],
            status=MeetingStatusEnum(data["status"]),
            created_at=data["createdAt"],
            updated_at=data["updatedAt"],
            step_function_execution_arn=data.get("stepFunctionExecutionArn"),
            current_step=data.get("currentStep"),
            error=data.get("error"),
            transcript_key=data.get("transcriptKey"),
            report_key=data.get("reportKey"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> MeetingStatus:
        return cls.from_dict(json.loads(json_str))

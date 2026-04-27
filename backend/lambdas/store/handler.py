"""Report Storage Lambda handler for the Meeting Minutes application.

Stores validated meeting-minutes reports to S3 and manages meeting status
objects. Handles three actions dispatched by Step Functions:

- Default (no action): Store the validated report to S3 and update status
  to "completed".
- "mark_failed": Update the meeting status to "failed" with error details.
- "update_status": Write the current status object (terminal state).

Resource name: Pranav-meeting-minutes-store
Requirements: 6.7, 14.5
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

from backend.models.meeting_status import MeetingStatus, MeetingStatusEnum
from backend.utils.s3_keys import report_key, status_key

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _get_data_bucket() -> str:
    return os.environ.get("DATA_BUCKET", "")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_status(
    meeting_id: str,
    s3_client: Any,
    bucket: str,
) -> dict[str, Any] | None:
    """Load an existing status object from S3, returning None if not found."""
    key = status_key(meeting_id)
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except s3_client.exceptions.NoSuchKey:
        return None
    except Exception:
        logger.warning("Could not load existing status for meeting=%s", meeting_id)
        return None


def store_report(
    meeting_id: str,
    user_id: str,
    report: dict[str, Any],
    s3_client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """Store the validated report JSON to S3.

    Writes the report to ``users/{user_id}/reports/{meeting_id}/minutes.json``
    and updates the meeting status to ``completed``.

    Args:
        meeting_id: The meeting UUID.
        user_id: The Cognito user sub identifier.
        report: The validated minutes report dictionary.
        s3_client: Optional boto3 S3 client (for testing).
        bucket: Optional bucket name override (for testing).

    Returns:
        A dict with ``reportKey`` and ``statusKey``.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()

    rpt_key = report_key(user_id, meeting_id)
    sts_key = status_key(meeting_id)
    now = _now_iso()

    # Store the report
    logger.info("Storing report to s3://%s/%s", bucket, rpt_key)
    s3_client.put_object(
        Bucket=bucket,
        Key=rpt_key,
        Body=json.dumps(report, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    # Load existing status or create a new one
    existing = _load_status(meeting_id, s3_client, bucket)
    if existing:
        existing["status"] = MeetingStatusEnum.COMPLETED.value
        existing["updatedAt"] = now
        existing["reportKey"] = rpt_key
        existing["currentStep"] = "StoreReport"
        status_data = existing
    else:
        status_obj = MeetingStatus(
            meeting_id=meeting_id,
            user_id=user_id,
            status=MeetingStatusEnum.COMPLETED,
            created_at=now,
            updated_at=now,
            report_key=rpt_key,
            current_step="StoreReport",
        )
        status_data = status_obj.to_dict()

    logger.info("Updating status to completed at s3://%s/%s", bucket, sts_key)
    s3_client.put_object(
        Bucket=bucket,
        Key=sts_key,
        Body=json.dumps(status_data, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    return {"reportKey": rpt_key, "statusKey": sts_key}


def mark_failed(
    meeting_id: str,
    user_id: str,
    error: Any,
    s3_client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """Update the meeting status to failed with error details.

    Args:
        meeting_id: The meeting UUID.
        user_id: The Cognito user sub identifier.
        error: Error details (dict or string) from the failed step.
        s3_client: Optional boto3 S3 client (for testing).
        bucket: Optional bucket name override (for testing).

    Returns:
        A dict with ``statusKey``.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()

    sts_key = status_key(meeting_id)
    now = _now_iso()

    error_message = json.dumps(error) if isinstance(error, dict) else str(error)

    existing = _load_status(meeting_id, s3_client, bucket)
    if existing:
        existing["status"] = MeetingStatusEnum.FAILED.value
        existing["updatedAt"] = now
        existing["error"] = error_message
        existing["currentStep"] = "MarkFailed"
        status_data = existing
    else:
        status_obj = MeetingStatus(
            meeting_id=meeting_id,
            user_id=user_id,
            status=MeetingStatusEnum.FAILED,
            created_at=now,
            updated_at=now,
            error=error_message,
            current_step="MarkFailed",
        )
        status_data = status_obj.to_dict()

    logger.info("Marking meeting=%s as failed at s3://%s/%s", meeting_id, bucket, sts_key)
    s3_client.put_object(
        Bucket=bucket,
        Key=sts_key,
        Body=json.dumps(status_data, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    return {"statusKey": sts_key}


def update_status(
    meeting_id: str,
    user_id: str,
    s3_client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """Write the current status object as the terminal state.

    If a status object already exists, updates ``updatedAt``. Otherwise
    creates a minimal status object with ``completed`` status.

    Args:
        meeting_id: The meeting UUID.
        user_id: The Cognito user sub identifier.
        s3_client: Optional boto3 S3 client (for testing).
        bucket: Optional bucket name override (for testing).

    Returns:
        A dict with ``statusKey`` and the final ``status`` value.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()

    sts_key = status_key(meeting_id)
    now = _now_iso()

    existing = _load_status(meeting_id, s3_client, bucket)
    if existing:
        existing["updatedAt"] = now
        status_data = existing
    else:
        status_obj = MeetingStatus(
            meeting_id=meeting_id,
            user_id=user_id,
            status=MeetingStatusEnum.COMPLETED,
            created_at=now,
            updated_at=now,
        )
        status_data = status_obj.to_dict()

    logger.info(
        "Updating terminal status for meeting=%s status=%s",
        meeting_id,
        status_data.get("status", "unknown"),
    )
    s3_client.put_object(
        Bucket=bucket,
        Key=sts_key,
        Body=json.dumps(status_data, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    return {"statusKey": sts_key, "status": status_data.get("status", "unknown")}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for report storage and status management.

    Expected event shapes (from Step Functions):

    **Store report (default action)**::

        {
            "meetingId": "...",
            "userId": "...",
            "report": { ... }
        }

    **Mark failed**::

        {
            "action": "mark_failed",
            "meetingId": "...",
            "userId": "...",
            "error": { ... }
        }

    **Update status (terminal)**::

        {
            "action": "update_status",
            "meetingId": "...",
            "userId": "..."
        }
    """
    action = event.get("action", "store")
    meeting_id = event.get("meetingId", "")
    user_id = event.get("userId", "")

    logger.info(
        "Store handler invoked: action=%s meeting=%s user=%s",
        action,
        meeting_id,
        user_id,
    )

    try:
        if action == "mark_failed":
            error_details = event.get("error", {})
            result = mark_failed(meeting_id, user_id, error_details)
            return {
                "action": "mark_failed",
                "meetingId": meeting_id,
                "userId": user_id,
                **result,
            }

        if action == "update_status":
            result = update_status(meeting_id, user_id)
            return {
                "action": "update_status",
                "meetingId": meeting_id,
                "userId": user_id,
                **result,
            }

        # Default: store report
        report = event.get("report", {})
        result = store_report(meeting_id, user_id, report)
        return {
            "action": "store",
            "meetingId": meeting_id,
            "userId": user_id,
            **result,
        }

    except Exception:
        logger.exception(
            "Store handler failed: action=%s meeting=%s", action, meeting_id
        )
        raise

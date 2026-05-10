"""Report Storage Lambda handler for the Meeting Minutes application.

Stores validated meeting-minutes reports to S3 and manages meeting status
in DynamoDB. Handles three actions dispatched by Step Functions:

- Default (no action): Store the validated report to S3 and update status
  to "completed" in DynamoDB.
- "mark_failed": Update the meeting status to "failed" in DynamoDB with error details.
- "update_status": Update the updatedAt timestamp in DynamoDB.

Resource name: Pranav-meeting-minutes-store
Requirements: 6.7, 14.5

Environment variables:
    DATA_BUCKET    – S3 bucket for transcripts and reports
    MEETINGS_TABLE – DynamoDB table for meeting metadata
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

from backend.models.meeting_status import MeetingStatusEnum
from backend.utils.s3_keys import report_key

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _get_data_bucket() -> str:
    return os.environ.get("DATA_BUCKET", "")


def _get_meetings_table() -> str:
    return os.environ.get("MEETINGS_TABLE", "")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def store_report(
    meeting_id: str,
    user_id: str,
    report: dict[str, Any],
    s3_client: Any = None,
    dynamodb_client: Any = None,
    bucket: str | None = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """Store the validated report JSON to S3.

    Writes the report to ``users/{user_id}/reports/{meeting_id}/minutes.json``
    and updates the meeting status to ``completed`` in DynamoDB.

    Args:
        meeting_id: The meeting UUID.
        user_id: The Cognito user sub identifier.
        report: The validated minutes report dictionary.
        s3_client: Optional boto3 S3 client (for testing).
        dynamodb_client: Optional boto3 DynamoDB client (for testing).
        bucket: Optional bucket name override (for testing).
        table_name: Optional DynamoDB table name override (for testing).

    Returns:
        A dict with ``reportKey``.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()
    if table_name is None:
        table_name = _get_meetings_table()

    rpt_key = report_key(user_id, meeting_id)
    now = _now_iso()

    # Store the report to S3
    logger.info("Storing report to s3://%s/%s", bucket, rpt_key)
    s3_client.put_object(
        Bucket=bucket,
        Key=rpt_key,
        Body=json.dumps(report, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    # Update meeting status to completed in DynamoDB
    logger.info("Updating meeting=%s status to completed in DynamoDB", meeting_id)
    dynamodb_client.update_item(
        TableName=table_name,
        Key={
            "userId": {"S": user_id},
            "meetingId": {"S": meeting_id},
        },
        UpdateExpression="SET #s = :status, updatedAt = :now, reportKey = :rk, currentStep = :step",
        ExpressionAttributeNames={
            "#s": "status",
        },
        ExpressionAttributeValues={
            ":status": {"S": MeetingStatusEnum.COMPLETED.value},
            ":now": {"S": now},
            ":rk": {"S": rpt_key},
            ":step": {"S": "StoreReport"},
        },
    )

    return {"reportKey": rpt_key, "bucket": bucket}


def mark_failed(
    meeting_id: str,
    user_id: str,
    error: Any,
    dynamodb_client: Any = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """Update the meeting status to failed with error details in DynamoDB.

    Args:
        meeting_id: The meeting UUID.
        user_id: The Cognito user sub identifier.
        error: Error details (dict or string) from the failed step.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).
        table_name: Optional DynamoDB table name override (for testing).

    Returns:
        A dict with ``meetingId``.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_meetings_table()

    now = _now_iso()
    error_message = json.dumps(error) if isinstance(error, dict) else str(error)

    logger.info("Marking meeting=%s as failed in DynamoDB", meeting_id)
    dynamodb_client.update_item(
        TableName=table_name,
        Key={
            "userId": {"S": user_id},
            "meetingId": {"S": meeting_id},
        },
        UpdateExpression="SET #s = :status, updatedAt = :now, #err = :error, currentStep = :step",
        ExpressionAttributeNames={
            "#s": "status",
            "#err": "error",
        },
        ExpressionAttributeValues={
            ":status": {"S": MeetingStatusEnum.FAILED.value},
            ":now": {"S": now},
            ":error": {"S": error_message},
            ":step": {"S": "MarkFailed"},
        },
    )

    return {"meetingId": meeting_id}


def update_status(
    meeting_id: str,
    user_id: str,
    dynamodb_client: Any = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """Update the updatedAt timestamp in DynamoDB.

    Args:
        meeting_id: The meeting UUID.
        user_id: The Cognito user sub identifier.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).
        table_name: Optional DynamoDB table name override (for testing).

    Returns:
        A dict with ``meetingId`` and ``status``.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_meetings_table()

    now = _now_iso()

    logger.info("Updating terminal status timestamp for meeting=%s", meeting_id)
    response = dynamodb_client.update_item(
        TableName=table_name,
        Key={
            "userId": {"S": user_id},
            "meetingId": {"S": meeting_id},
        },
        UpdateExpression="SET updatedAt = :now",
        ExpressionAttributeValues={
            ":now": {"S": now},
        },
        ReturnValues="ALL_NEW",
    )

    updated_item = response.get("Attributes", {})
    status = updated_item.get("status", {}).get("S", "unknown")

    return {"meetingId": meeting_id, "status": status}


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

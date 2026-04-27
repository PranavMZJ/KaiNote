"""REST API Lambda handler for the Meeting Minutes application.

Implements the Pranav-meeting-minutes-api Lambda as an API Gateway proxy
integration. Routes requests based on httpMethod and resource path.

Endpoints:
- GET  /meetings                          — list user's meetings
- GET  /meetings/{meetingId}              — get meeting details/status
- GET  /meetings/{meetingId}/report       — get generated report JSON
- PUT  /meetings/{meetingId}/report       — save edited report
- GET  /meetings/{meetingId}/report/download — pre-signed URL for download
- POST /meetings/{meetingId}/retry        — retry failed meeting processing

Requirements: 9.1, 10.4, 11.2, 12.4, 13.1, 13.3
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

from backend.models.meeting_status import MeetingStatus, MeetingStatusEnum
from backend.utils.s3_keys import report_key, status_key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,PUT,POST,OPTIONS",
    "Content-Type": "application/json",
}

PRESIGNED_URL_EXPIRY = 3600  # 1 hour


def _get_data_bucket() -> str:
    return os.environ.get("DATA_BUCKET", "")


def _get_step_function_arn() -> str:
    return os.environ.get("STEP_FUNCTION_ARN", "")


def _response(status_code: int, body: Any) -> dict[str, Any]:
    """Build an API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, ensure_ascii=False),
    }


def _get_user_id(event: dict[str, Any]) -> str:
    """Extract user ID from JWT claims in the request context."""
    try:
        return event["requestContext"]["authorizer"]["claims"]["sub"]
    except (KeyError, TypeError):
        return ""


def _get_meeting_id(event: dict[str, Any]) -> str:
    """Extract meetingId from path parameters."""
    params = event.get("pathParameters") or {}
    return params.get("meetingId", "")


def _load_s3_json(
    s3_client: Any, bucket: str, key: str
) -> dict[str, Any] | None:
    """Load a JSON object from S3, returning None if not found."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except s3_client.exceptions.NoSuchKey:
        return None
    except Exception:
        logger.exception("Failed to load s3://%s/%s", bucket, key)
        return None


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def list_meetings(
    user_id: str,
    s3_client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """GET /meetings — list all meetings for the authenticated user.

    Scans S3 objects under the ``meetings/`` prefix and filters by userId
    in each status object.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()

    meetings: list[dict[str, Any]] = []
    prefix = "meetings/"

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.endswith("/status.json"):
                    continue
                status_data = _load_s3_json(s3_client, bucket, key)
                if status_data and status_data.get("userId") == user_id:
                    meetings.append(status_data)
    except Exception:
        logger.exception("Failed to list meetings for user=%s", user_id)
        return _response(500, {"error": "Failed to list meetings"})

    return _response(200, {"meetings": meetings})


def get_meeting(
    user_id: str,
    meeting_id: str,
    s3_client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """GET /meetings/{meetingId} — get meeting details and status."""
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()

    sts_key = status_key(meeting_id)
    status_data = _load_s3_json(s3_client, bucket, sts_key)

    if status_data is None:
        return _response(404, {"error": "Meeting not found"})

    if status_data.get("userId") != user_id:
        return _response(403, {"error": "Access denied"})

    return _response(200, status_data)


def get_report(
    user_id: str,
    meeting_id: str,
    s3_client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """GET /meetings/{meetingId}/report — get the generated report JSON.

    Returns the edited version if it exists, otherwise the original.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()

    # Verify ownership
    sts_key = status_key(meeting_id)
    status_data = _load_s3_json(s3_client, bucket, sts_key)
    if status_data is None:
        return _response(404, {"error": "Meeting not found"})
    if status_data.get("userId") != user_id:
        return _response(403, {"error": "Access denied"})

    # Try edited version first, then original
    edited_key = report_key(user_id, meeting_id, edited=True)
    report_data = _load_s3_json(s3_client, bucket, edited_key)
    if report_data is not None:
        return _response(200, {"report": report_data, "version": "edited"})

    original_key = report_key(user_id, meeting_id, edited=False)
    report_data = _load_s3_json(s3_client, bucket, original_key)
    if report_data is not None:
        return _response(200, {"report": report_data, "version": "original"})

    return _response(404, {"error": "Report not found"})


def put_report(
    user_id: str,
    meeting_id: str,
    body: str | None,
    s3_client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """PUT /meetings/{meetingId}/report — save edited report.

    Stores the edited report as ``minutes_edited.json``, preserving the
    original ``minutes.json``.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()

    # Verify ownership
    sts_key = status_key(meeting_id)
    status_data = _load_s3_json(s3_client, bucket, sts_key)
    if status_data is None:
        return _response(404, {"error": "Meeting not found"})
    if status_data.get("userId") != user_id:
        return _response(403, {"error": "Access denied"})

    if not body:
        return _response(400, {"error": "Request body is required"})

    try:
        report_data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"error": "Invalid JSON in request body"})

    edited_key = report_key(user_id, meeting_id, edited=True)

    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=edited_key,
            Body=json.dumps(report_data, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception:
        logger.exception("Failed to save edited report for meeting=%s", meeting_id)
        return _response(500, {"error": "Failed to save report"})

    return _response(200, {"message": "Report saved", "key": edited_key})


def get_report_download(
    user_id: str,
    meeting_id: str,
    s3_client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """GET /meetings/{meetingId}/report/download — pre-signed URL for download.

    Returns a pre-signed S3 URL with 1-hour expiry. Prefers the edited
    version if it exists.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()

    # Verify ownership
    sts_key = status_key(meeting_id)
    status_data = _load_s3_json(s3_client, bucket, sts_key)
    if status_data is None:
        return _response(404, {"error": "Meeting not found"})
    if status_data.get("userId") != user_id:
        return _response(403, {"error": "Access denied"})

    # Determine which report file to serve
    edited_key = report_key(user_id, meeting_id, edited=True)
    original_key = report_key(user_id, meeting_id, edited=False)

    # Check if edited version exists
    target_key = original_key
    try:
        s3_client.head_object(Bucket=bucket, Key=edited_key)
        target_key = edited_key
    except Exception:
        pass

    # Verify the target file exists
    try:
        s3_client.head_object(Bucket=bucket, Key=target_key)
    except Exception:
        return _response(404, {"error": "Report not found"})

    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": target_key},
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )
    except Exception:
        logger.exception("Failed to generate pre-signed URL for meeting=%s", meeting_id)
        return _response(500, {"error": "Failed to generate download URL"})

    return _response(200, {"downloadUrl": url, "key": target_key})


def retry_meeting(
    user_id: str,
    meeting_id: str,
    s3_client: Any = None,
    sfn_client: Any = None,
    bucket: str | None = None,
    step_function_arn: str | None = None,
) -> dict[str, Any]:
    """POST /meetings/{meetingId}/retry — restart processing for failed meetings.

    Only allows retry when the meeting status is "failed".
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if sfn_client is None:
        sfn_client = boto3.client("stepfunctions", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()
    if step_function_arn is None:
        step_function_arn = _get_step_function_arn()

    # Load and verify status
    sts_key = status_key(meeting_id)
    status_data = _load_s3_json(s3_client, bucket, sts_key)
    if status_data is None:
        return _response(404, {"error": "Meeting not found"})
    if status_data.get("userId") != user_id:
        return _response(403, {"error": "Access denied"})
    if status_data.get("status") != MeetingStatusEnum.FAILED.value:
        return _response(409, {"error": "Only failed meetings can be retried"})

    # Get transcript key from status
    transcript_key = status_data.get("transcriptKey")
    if not transcript_key:
        return _response(400, {"error": "No transcript available for retry"})

    # Start new Step Functions execution
    import time

    execution_name = f"{meeting_id}-retry-{int(time.time())}"
    sfn_input = json.dumps({
        "meetingId": meeting_id,
        "userId": user_id,
        "transcriptKey": transcript_key,
    })

    try:
        sfn_response = sfn_client.start_execution(
            stateMachineArn=step_function_arn,
            name=execution_name,
            input=sfn_input,
        )
        execution_arn = sfn_response.get("executionArn", "")
    except Exception:
        logger.exception("Failed to start retry execution for meeting=%s", meeting_id)
        return _response(500, {"error": "Failed to start retry"})

    # Update status to processing
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    status_data["status"] = MeetingStatusEnum.PROCESSING.value
    status_data["updatedAt"] = now
    status_data["error"] = None
    status_data["stepFunctionExecutionArn"] = execution_arn
    status_data["currentStep"] = "Retry"

    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=sts_key,
            Body=json.dumps(status_data, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception:
        logger.warning("Failed to update status after retry start for meeting=%s", meeting_id)

    return _response(200, {
        "message": "Retry started",
        "meetingId": meeting_id,
        "executionArn": execution_arn,
    })


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

# Map (httpMethod, resource) to handler functions
_ROUTES = {
    ("GET", "/meetings"): "list_meetings",
    ("GET", "/meetings/{meetingId}"): "get_meeting",
    ("GET", "/meetings/{meetingId}/report"): "get_report",
    ("PUT", "/meetings/{meetingId}/report"): "put_report",
    ("GET", "/meetings/{meetingId}/report/download"): "get_report_download",
    ("POST", "/meetings/{meetingId}/retry"): "retry_meeting",
}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for the REST API.

    This is an API Gateway Lambda Proxy integration. The event contains
    ``httpMethod``, ``resource``, ``pathParameters``, ``body``, and
    ``requestContext``.
    """
    http_method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    user_id = _get_user_id(event)

    logger.info(
        "API handler invoked: method=%s resource=%s user=%s",
        http_method,
        resource,
        user_id,
    )

    if not user_id:
        return _response(401, {"error": "Unauthorized"})

    route_key = (http_method, resource)
    route_name = _ROUTES.get(route_key)

    if route_name is None:
        return _response(404, {"error": "Not found"})

    meeting_id = _get_meeting_id(event)

    try:
        if route_name == "list_meetings":
            return list_meetings(user_id)
        elif route_name == "get_meeting":
            return get_meeting(user_id, meeting_id)
        elif route_name == "get_report":
            return get_report(user_id, meeting_id)
        elif route_name == "put_report":
            return put_report(user_id, meeting_id, event.get("body"))
        elif route_name == "get_report_download":
            return get_report_download(user_id, meeting_id)
        elif route_name == "retry_meeting":
            return retry_meeting(user_id, meeting_id)
        else:
            return _response(404, {"error": "Not found"})
    except Exception:
        logger.exception(
            "Unhandled error: method=%s resource=%s meeting=%s",
            http_method,
            resource,
            meeting_id,
        )
        return _response(500, {"error": "Internal server error"})

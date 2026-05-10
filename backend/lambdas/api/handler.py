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

Environment variables:
    DATA_BUCKET       – S3 bucket for transcripts and reports
    STEP_FUNCTION_ARN – ARN of the post-processing Step Functions state machine
    MEETINGS_TABLE    – DynamoDB table for meeting metadata
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import boto3

from backend.models.meeting_status import MeetingStatusEnum
from backend.utils.s3_keys import report_key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,PUT,POST,DELETE,OPTIONS",
    "Content-Type": "application/json",
}

PRESIGNED_URL_EXPIRY = 3600  # 1 hour


def _get_data_bucket() -> str:
    return os.environ.get("DATA_BUCKET", "")


def _get_step_function_arn() -> str:
    return os.environ.get("STEP_FUNCTION_ARN", "")


def _get_meetings_table() -> str:
    return os.environ.get("MEETINGS_TABLE", "")


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


def _dynamo_item_to_dict(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a DynamoDB item (with type descriptors) to a plain dict."""
    result: dict[str, Any] = {}
    for key, value in item.items():
        if "S" in value:
            result[key] = value["S"]
        elif "N" in value:
            result[key] = value["N"]
        elif "NULL" in value:
            result[key] = None
        elif "BOOL" in value:
            result[key] = value["BOOL"]
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def list_meetings(
    user_id: str,
    dynamodb_client: Any = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """GET /meetings — list all meetings for the authenticated user.

    Queries DynamoDB meetings table with userId partition key.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_meetings_table()

    meetings: list[dict[str, Any]] = []

    try:
        response = dynamodb_client.query(
            TableName=table_name,
            KeyConditionExpression="userId = :uid",
            ExpressionAttributeValues={":uid": {"S": user_id}},
            ScanIndexForward=False,
        )
        for item in response.get("Items", []):
            meetings.append(_dynamo_item_to_dict(item))

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = dynamodb_client.query(
                TableName=table_name,
                KeyConditionExpression="userId = :uid",
                ExpressionAttributeValues={":uid": {"S": user_id}},
                ScanIndexForward=False,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            for item in response.get("Items", []):
                meetings.append(_dynamo_item_to_dict(item))

    except Exception:
        logger.exception("Failed to list meetings for user=%s", user_id)
        return _response(500, {"error": "Failed to list meetings"})

    return _response(200, {"meetings": meetings})


def get_meeting(
    user_id: str,
    meeting_id: str,
    dynamodb_client: Any = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """GET /meetings/{meetingId} — get meeting details and status."""
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_meetings_table()

    try:
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={
                "userId": {"S": user_id},
                "meetingId": {"S": meeting_id},
            },
        )
    except Exception:
        logger.exception("Failed to get meeting=%s for user=%s", meeting_id, user_id)
        return _response(500, {"error": "Failed to get meeting"})

    item = response.get("Item")
    if item is None:
        return _response(404, {"error": "Meeting not found"})

    return _response(200, _dynamo_item_to_dict(item))


def get_report(
    user_id: str,
    meeting_id: str,
    s3_client: Any = None,
    bucket: str | None = None,
    dynamodb_client: Any = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """GET /meetings/{meetingId}/report — get the generated report JSON.

    Returns the edited version if it exists, otherwise the original.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_meetings_table()

    # Verify ownership via DynamoDB
    try:
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={
                "userId": {"S": user_id},
                "meetingId": {"S": meeting_id},
            },
        )
    except Exception:
        logger.exception("Failed to verify meeting ownership: meeting=%s", meeting_id)
        return _response(500, {"error": "Internal server error"})

    if not response.get("Item"):
        return _response(404, {"error": "Meeting not found"})

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
    dynamodb_client: Any = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """PUT /meetings/{meetingId}/report — save edited report.

    Stores the edited report as ``minutes_edited.json``, preserving the
    original ``minutes.json``.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_meetings_table()

    # Verify ownership via DynamoDB
    try:
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={
                "userId": {"S": user_id},
                "meetingId": {"S": meeting_id},
            },
        )
    except Exception:
        logger.exception("Failed to verify meeting ownership: meeting=%s", meeting_id)
        return _response(500, {"error": "Internal server error"})

    if not response.get("Item"):
        return _response(404, {"error": "Meeting not found"})

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
    dynamodb_client: Any = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """GET /meetings/{meetingId}/report/download — pre-signed URL for download.

    Returns a pre-signed S3 URL with 1-hour expiry. Prefers the edited
    version if it exists.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_meetings_table()

    # Verify ownership via DynamoDB
    try:
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={
                "userId": {"S": user_id},
                "meetingId": {"S": meeting_id},
            },
        )
    except Exception:
        logger.exception("Failed to verify meeting ownership: meeting=%s", meeting_id)
        return _response(500, {"error": "Internal server error"})

    if not response.get("Item"):
        return _response(404, {"error": "Meeting not found"})

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


def get_agent_report(
    user_id: str,
    meeting_id: str,
    s3_client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """GET /meetings/{meetingId}/agent-report — get the agent actions report.

    Returns the agent_actions.json if it exists, or an empty object if the
    agent hasn't run yet or failed.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()

    agent_key = f"users/{user_id}/reports/{meeting_id}/agent_actions.json"
    report_data = _load_s3_json(s3_client, bucket, agent_key)

    if report_data is not None:
        return _response(200, {"agentReport": report_data})

    return _response(200, {"agentReport": None})


def delete_meeting(
    user_id: str,
    meeting_id: str,
    s3_client: Any = None,
    dynamodb_client: Any = None,
    bucket: str | None = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """DELETE /meetings/{meetingId} — delete a meeting and all its data.

    Removes the DynamoDB record and all S3 objects (transcript, report,
    agent_actions) for the meeting.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if bucket is None:
        bucket = _get_data_bucket()
    if table_name is None:
        table_name = _get_meetings_table()

    # Verify ownership via DynamoDB
    try:
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={
                "userId": {"S": user_id},
                "meetingId": {"S": meeting_id},
            },
        )
    except Exception:
        logger.exception("Failed to verify meeting ownership: meeting=%s", meeting_id)
        return _response(500, {"error": "Internal server error"})

    if not response.get("Item"):
        return _response(404, {"error": "Meeting not found"})

    # Delete all S3 objects for this meeting
    s3_prefixes = [
        f"users/{user_id}/transcripts/{meeting_id}/",
        f"users/{user_id}/reports/{meeting_id}/",
    ]

    for prefix in s3_prefixes:
        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
            for page in pages:
                objects = page.get("Contents", [])
                if objects:
                    delete_keys = [{"Key": obj["Key"]} for obj in objects]
                    s3_client.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": delete_keys},
                    )
                    logger.info("Deleted %d S3 objects under %s", len(delete_keys), prefix)
        except Exception:
            logger.warning("Failed to delete S3 objects under %s", prefix, exc_info=True)

    # Delete DynamoDB record
    try:
        dynamodb_client.delete_item(
            TableName=table_name,
            Key={
                "userId": {"S": user_id},
                "meetingId": {"S": meeting_id},
            },
        )
        logger.info("Deleted meeting record: meeting=%s user=%s", meeting_id, user_id)
    except Exception:
        logger.exception("Failed to delete DynamoDB record: meeting=%s", meeting_id)
        return _response(500, {"error": "Failed to delete meeting"})

    return _response(200, {"message": "Meeting deleted", "meetingId": meeting_id})


def retry_meeting(
    user_id: str,
    meeting_id: str,
    s3_client: Any = None,
    sfn_client: Any = None,
    bucket: str | None = None,
    step_function_arn: str | None = None,
    dynamodb_client: Any = None,
    table_name: str | None = None,
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
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if table_name is None:
        table_name = _get_meetings_table()

    # Load meeting from DynamoDB
    try:
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={
                "userId": {"S": user_id},
                "meetingId": {"S": meeting_id},
            },
        )
    except Exception:
        logger.exception("Failed to get meeting for retry: meeting=%s", meeting_id)
        return _response(500, {"error": "Internal server error"})

    item = response.get("Item")
    if item is None:
        return _response(404, {"error": "Meeting not found"})

    meeting_data = _dynamo_item_to_dict(item)

    if meeting_data.get("status") != MeetingStatusEnum.FAILED.value:
        return _response(409, {"error": "Only failed meetings can be retried"})

    # Get transcript key from meeting record
    transcript_key = meeting_data.get("transcriptKey")
    if not transcript_key:
        return _response(400, {"error": "No transcript available for retry"})

    # Start new Step Functions execution
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

    # Update status to processing in DynamoDB
    now = datetime.now(timezone.utc).isoformat()
    try:
        dynamodb_client.update_item(
            TableName=table_name,
            Key={
                "userId": {"S": user_id},
                "meetingId": {"S": meeting_id},
            },
            UpdateExpression="SET #s = :status, updatedAt = :now, #err = :null, stepFunctionExecutionArn = :arn, currentStep = :step",
            ExpressionAttributeNames={
                "#s": "status",
                "#err": "error",
            },
            ExpressionAttributeValues={
                ":status": {"S": MeetingStatusEnum.PROCESSING.value},
                ":now": {"S": now},
                ":null": {"NULL": True},
                ":arn": {"S": execution_arn},
                ":step": {"S": "Retry"},
            },
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
    ("GET", "/meetings/{meetingId}/agent-report"): "get_agent_report",
    ("DELETE", "/meetings/{meetingId}"): "delete_meeting",
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
        elif route_name == "get_agent_report":
            return get_agent_report(user_id, meeting_id)
        elif route_name == "delete_meeting":
            return delete_meeting(user_id, meeting_id)
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

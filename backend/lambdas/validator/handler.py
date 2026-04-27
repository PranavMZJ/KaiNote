"""Schema Validator Lambda handler for the Meeting Minutes application.

Validates generated meeting-minutes report JSON against the Minutes Schema
stored in S3. Returns validation results with specific error messages.

Resource name: Pranav-meeting-minutes-validator
Requirements: 6.5, 8.3
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
import jsonschema

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _get_prompt_bucket() -> str:
    return os.environ.get("PROMPT_BUCKET", "")


def load_schema(version: str = "v1", s3_client: Any = None) -> dict[str, Any]:
    """Load the Minutes Schema JSON from S3.

    Args:
        version: Schema version string (e.g. "v1").
        s3_client: Optional boto3 S3 client (for testing).

    Returns:
        Parsed JSON schema as a dictionary.
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")

    bucket = _get_prompt_bucket()
    key = f"schemas/{version}/minutes_schema.json"

    logger.info("Loading schema from s3://%s/%s", bucket, key)

    response = s3_client.get_object(Bucket=bucket, Key=key)
    schema_str = response["Body"].read().decode("utf-8")
    return json.loads(schema_str)


def validate_report(
    report: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Validate a report dict against the Minutes Schema.

    Performs JSON Schema validation and returns a result dict with
    ``isValid``, ``errors``, and any additional context.

    Args:
        report: The generated meeting-minutes report as a dictionary.
        schema: The JSON Schema to validate against.

    Returns:
        A dict with ``isValid`` (bool) and ``errors`` (list of str).
    """
    errors: list[str] = []

    validator = jsonschema.Draft7Validator(schema)
    for error in sorted(validator.iter_errors(report), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
        errors.append(f"{path}: {error.message}")

    return {
        "isValid": len(errors) == 0,
        "errors": errors,
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for schema validation.

    Expected event shape (from Step Functions)::

        {
            "meetingId": "...",
            "userId": "...",
            "report": { ... },          # The generated report dict
            "schemaVersion": "v1",       # Optional, defaults to "v1"
            "attemptCount": 1            # Optional, defaults to 1
        }

    Returns::

        {
            "isValid": true/false,
            "errors": [...],
            "meetingId": "...",
            "userId": "...",
            "report": { ... },
            "attemptCount": N
        }
    """
    meeting_id = event.get("meetingId", "")
    user_id = event.get("userId", "")
    report = event.get("report", {})
    schema_version = event.get("schemaVersion", "v1")
    attempt_count = event.get("attemptCount", 1)

    logger.info(
        "Validating report for meeting=%s user=%s schema=%s attempt=%d",
        meeting_id,
        user_id,
        schema_version,
        attempt_count,
    )

    try:
        schema = load_schema(version=schema_version)
    except Exception:
        logger.exception("Failed to load schema %s from S3", schema_version)
        return {
            "isValid": False,
            "errors": [f"Failed to load schema version {schema_version} from S3"],
            "meetingId": meeting_id,
            "userId": user_id,
            "report": report,
            "attemptCount": attempt_count,
        }

    result = validate_report(report, schema)

    if result["isValid"]:
        logger.info("Report validation passed for meeting=%s", meeting_id)
    else:
        logger.warning(
            "Report validation failed for meeting=%s with %d errors: %s",
            meeting_id,
            len(result["errors"]),
            result["errors"],
        )

    return {
        "isValid": result["isValid"],
        "errors": result["errors"],
        "meetingId": meeting_id,
        "userId": user_id,
        "report": report,
        "attemptCount": attempt_count,
    }

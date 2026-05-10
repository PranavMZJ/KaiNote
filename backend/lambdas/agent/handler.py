"""Post-Meeting Agent Lambda handler for KaiNote.

Analyzes generated meeting minutes, sends notifications to action item owners,
detects overdue items from prior meetings, and suggests follow-up meetings.

Triggered by Step Functions after StoreReport completes. Agent failure is
non-blocking — the meeting report remains valid regardless.

Resource name: Pranav-meeting-minutes-agent

Environment variables:
    DATA_BUCKET    – S3 bucket for transcripts and reports
    PROMPT_BUCKET  – S3 bucket for prompt templates
    MODEL_ID       – Bedrock model ID (inference profile)
    SNS_TOPIC_ARN  – SNS topic ARN for notifications
    MEETINGS_TABLE – DynamoDB table for meeting metadata
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _get_data_bucket() -> str:
    return os.environ.get("DATA_BUCKET", "")


def _get_prompt_bucket() -> str:
    return os.environ.get("PROMPT_BUCKET", "")


def _get_model_id() -> str:
    return os.environ.get("MODEL_ID", "jp.anthropic.claude-haiku-4-5-20251001-v1:0")


def _get_sns_topic_arn() -> str:
    return os.environ.get("SNS_TOPIC_ARN", "")


# ---------------------------------------------------------------------------
# AWS Clients
# ---------------------------------------------------------------------------

s3_client = boto3.client("s3", region_name="ap-northeast-1")
bedrock_client = boto3.client("bedrock-runtime", region_name="ap-northeast-1")
sns_client = boto3.client("sns", region_name="ap-northeast-1")


# ---------------------------------------------------------------------------
# Load report from S3
# ---------------------------------------------------------------------------

def load_report(bucket: str, report_key: str) -> dict[str, Any]:
    """Load the generated meeting report from S3."""
    logger.info("Loading report: s3://%s/%s", bucket, report_key)
    response = s3_client.get_object(Bucket=bucket, Key=report_key)
    return json.loads(response["Body"].read().decode("utf-8"))


# ---------------------------------------------------------------------------
# RAG — Prior meeting context (same pattern as generator)
# ---------------------------------------------------------------------------

_MAX_PRIOR_REPORTS = 3


def get_prior_meeting_context(user_id: str, meeting_id: str) -> str:
    """Retrieve context from recent prior meeting reports in S3."""
    data_bucket = _get_data_bucket()
    if not data_bucket:
        return "No prior meeting context available."

    prefix = f"users/{user_id}/reports/"

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=data_bucket, Prefix=prefix)

        report_keys: list[dict[str, Any]] = []
        for page in pages:
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/minutes.json") and meeting_id not in key:
                    report_keys.append(
                        {"key": key, "last_modified": obj["LastModified"]}
                    )

        if not report_keys:
            return "No prior meeting context available."

        report_keys.sort(key=lambda x: x["last_modified"], reverse=True)
        recent_keys = report_keys[:_MAX_PRIOR_REPORTS]

        context_parts: list[str] = []
        for item in recent_keys:
            try:
                resp = s3_client.get_object(Bucket=data_bucket, Key=item["key"])
                report_data = json.loads(resp["Body"].read().decode("utf-8"))

                title = report_data.get("meeting_title", "Untitled Meeting")
                meeting_dt = report_data.get("meeting_datetime", "Unknown date")
                summary = report_data.get("summary", "")
                decisions = report_data.get("decisions", [])
                action_items = report_data.get("action_items", [])

                part = f"### {title} ({meeting_dt})\n"
                if summary:
                    part += f"Summary: {summary}\n"
                if decisions:
                    part += "Decisions:\n"
                    for d in decisions:
                        decision_text = (
                            d.get("decision", "") if isinstance(d, dict) else str(d)
                        )
                        part += f"  - {decision_text}\n"
                if action_items:
                    part += "Action Items:\n"
                    for ai in action_items:
                        task = ai.get("task", "") if isinstance(ai, dict) else str(ai)
                        owner = (
                            ai.get("owner", "unassigned")
                            if isinstance(ai, dict)
                            else "unassigned"
                        )
                        due = (
                            ai.get("due_date", "no deadline")
                            if isinstance(ai, dict)
                            else "no deadline"
                        )
                        part += f"  - {task} (owner: {owner}, due: {due})\n"

                context_parts.append(part)
            except Exception:
                logger.warning("Failed to read prior report: key=%s", item["key"], exc_info=True)
                continue

        if not context_parts:
            return "No prior meeting context available."

        return "\n".join(context_parts)

    except Exception:
        logger.warning("Failed to retrieve prior meeting context", exc_info=True)
        return "No prior meeting context available."


# ---------------------------------------------------------------------------
# Load agent prompt template
# ---------------------------------------------------------------------------

def load_agent_prompt_template() -> str:
    """Load the agent prompt template from S3."""
    bucket = _get_prompt_bucket()
    key = "prompts/v1/agent_prompt.txt"

    logger.info("Loading agent prompt: s3://%s/%s", bucket, key)
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")


# ---------------------------------------------------------------------------
# Bedrock invocation for agent analysis
# ---------------------------------------------------------------------------

def analyze_with_bedrock(
    report: dict[str, Any],
    prior_context: str,
) -> dict[str, Any]:
    """Invoke Bedrock to analyze the report and prior context.

    Returns parsed JSON with overdue_items, follow_up_suggestion,
    and notification_enhancements.
    """
    model_id = _get_model_id()

    # Load and fill prompt template
    template = load_agent_prompt_template()
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = (
        template
        .replace("{report_json}", json.dumps(report, ensure_ascii=False, indent=2))
        .replace("{prior_context}", prior_context)
        .replace("{today_date}", today_date)
    )

    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}],
    })

    logger.info("Invoking Bedrock for agent analysis: model=%s", model_id)
    start_time = time.time()

    response = bedrock_client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=request_body,
    )

    latency_ms = (time.time() - start_time) * 1000
    response_body = json.loads(response["body"].read())

    usage = response_body.get("usage", {})
    logger.info(
        "Bedrock agent analysis complete: latency_ms=%.1f input_tokens=%d output_tokens=%d",
        latency_ms,
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
    )

    # Parse the response
    content_blocks = response_body.get("content", [])
    if not content_blocks:
        return {"overdue_items": [], "follow_up_suggestion": None, "notification_enhancements": []}

    text = content_blocks[0].get("text", "")

    # Strip markdown code fences if present
    stripped = text.strip()
    if stripped.startswith("```"):
        first_nl = stripped.index("\n") if "\n" in stripped else len(stripped)
        stripped = stripped[first_nl + 1:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    stripped = stripped.strip()

    try:
        result = json.loads(stripped)
        return result
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Bedrock agent response: %s", e)
        return {"overdue_items": [], "follow_up_suggestion": None, "notification_enhancements": []}


# ---------------------------------------------------------------------------
# SNS Notification sending
# ---------------------------------------------------------------------------

def send_action_notifications(
    report: dict[str, Any],
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """Send SNS notifications for each action item with a non-null owner.

    Returns a list of notification records for the agent report.
    """
    topic_arn = _get_sns_topic_arn()
    if not topic_arn:
        logger.warning("SNS_TOPIC_ARN not configured; skipping notifications.")
        return []

    action_items = report.get("action_items", [])
    meeting_title = report.get("meeting_title", "Untitled Meeting")
    meeting_datetime = report.get("meeting_datetime", "")

    # Build enhancement lookup
    enhancements = {}
    for enh in analysis.get("notification_enhancements", []):
        owner = enh.get("owner", "")
        if owner:
            enhancements[owner] = enh.get("additional_context", "")

    notifications_sent: list[dict[str, Any]] = []

    for item in action_items:
        owner = item.get("owner")
        if not owner:
            continue  # Skip items without an owner

        task = item.get("task", "")
        due_date = item.get("due_date", "Not specified")
        priority = item.get("priority", "medium")
        evidence = item.get("evidence", "")

        # Build subject
        priority_prefix = "[HIGH PRIORITY] " if priority == "high" else ""
        subject = f"[KaiNote] {priority_prefix}Action Item: {task[:80]}"
        # SNS subject max is 100 chars
        if len(subject) > 100:
            subject = subject[:97] + "..."

        # Build message body
        body_parts = [
            f"Meeting: {meeting_title}",
            f"Date: {meeting_datetime}",
            "",
            f"Task: {task}",
            f"Owner: {owner}",
            f"Due Date: {due_date or 'Not specified'}",
            f"Priority: {priority.upper()}",
            "",
            "Context from meeting:",
            f'"{evidence}"' if evidence else "(no context available)",
        ]

        # Add enhancement context if available
        additional = enhancements.get(owner, "")
        if additional:
            body_parts.extend(["", f"Additional context: {additional}"])

        body_parts.extend([
            "",
            "---",
            "This notification was automatically generated by KaiNote.",
        ])

        message = "\n".join(body_parts)

        try:
            response = sns_client.publish(
                TopicArn=topic_arn,
                Subject=subject,
                Message=message,
            )
            message_id = response.get("MessageId", "")
            logger.info("Notification sent: owner=%s task=%s msgId=%s", owner, task[:50], message_id)

            notifications_sent.append({
                "recipient": owner,
                "task": task,
                "due_date": due_date,
                "priority": priority,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "message_id": message_id,
            })
        except Exception:
            logger.error("Failed to send notification: owner=%s task=%s", owner, task[:50], exc_info=True)
            notifications_sent.append({
                "recipient": owner,
                "task": task,
                "due_date": due_date,
                "priority": priority,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "message_id": None,
                "error": "Failed to send",
            })

    return notifications_sent


def send_overdue_notification(
    overdue_items: list[dict[str, Any]],
    report: dict[str, Any],
) -> None:
    """Send a summary notification about overdue items."""
    topic_arn = _get_sns_topic_arn()
    if not topic_arn or not overdue_items:
        return

    meeting_title = report.get("meeting_title", "Untitled Meeting")

    subject = f"[KaiNote] ⚠️ Overdue Items Detected — {meeting_title}"
    if len(subject) > 100:
        subject = subject[:97] + "..."

    body_parts = [
        f"Meeting: {meeting_title}",
        f"Date: {report.get('meeting_datetime', '')}",
        "",
        "The following action items from prior meetings appear overdue or unresolved:",
        "",
    ]

    for item in overdue_items:
        body_parts.append(f"• Task: {item.get('original_task', 'Unknown')}")
        body_parts.append(f"  Owner: {item.get('original_owner', 'Unknown')}")
        body_parts.append(f"  Original Due Date: {item.get('original_due_date', 'Unknown')}")
        body_parts.append(f"  Status: {item.get('status', 'overdue')}")
        body_parts.append(f"  Current Reference: {item.get('current_meeting_reference', '')}")
        body_parts.append("")

    body_parts.extend([
        "---",
        "This notification was automatically generated by KaiNote.",
    ])

    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message="\n".join(body_parts),
        )
        logger.info("Overdue notification sent: %d items", len(overdue_items))
    except Exception:
        logger.error("Failed to send overdue notification", exc_info=True)


def send_follow_up_notification(
    follow_up: dict[str, Any],
    report: dict[str, Any],
) -> None:
    """Send a notification suggesting a follow-up meeting."""
    topic_arn = _get_sns_topic_arn()
    if not topic_arn or not follow_up:
        return

    meeting_title = report.get("meeting_title", "Untitled Meeting")

    subject = f"[KaiNote] 📅 Follow-Up Meeting Suggested — {meeting_title}"
    if len(subject) > 100:
        subject = subject[:97] + "..."

    body_parts = [
        f"Meeting: {meeting_title}",
        f"Date: {report.get('meeting_datetime', '')}",
        "",
        f"Reason: {follow_up.get('reason', 'Multiple open items require discussion')}",
        "",
        "Suggested Topics:",
    ]

    for topic in follow_up.get("suggested_topics", []):
        body_parts.append(f"  • {topic}")

    body_parts.append("")
    body_parts.append("Suggested Participants:")
    for participant in follow_up.get("suggested_participants", []):
        body_parts.append(f"  • {participant}")

    timeframe = follow_up.get("recommended_timeframe", "within 1 week")
    body_parts.extend([
        "",
        f"Recommended Timeframe: {timeframe}",
        "",
        "---",
        "This notification was automatically generated by KaiNote.",
    ])

    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message="\n".join(body_parts),
        )
        logger.info("Follow-up notification sent")
    except Exception:
        logger.error("Failed to send follow-up notification", exc_info=True)


# ---------------------------------------------------------------------------
# Store agent report to S3
# ---------------------------------------------------------------------------

def store_agent_report(
    user_id: str,
    meeting_id: str,
    agent_report: dict[str, Any],
) -> str:
    """Store the agent actions report to S3."""
    data_bucket = _get_data_bucket()
    key = f"users/{user_id}/reports/{meeting_id}/agent_actions.json"

    logger.info("Storing agent report: s3://%s/%s", data_bucket, key)
    s3_client.put_object(
        Bucket=data_bucket,
        Key=key,
        Body=json.dumps(agent_report, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    return key


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for the post-meeting agent.

    Expected event (from Step Functions):
        {
            "action": "run_agent",
            "meetingId": "...",
            "userId": "...",
            "bucket": "...",
            "reportKey": "..."
        }
    """
    action = event.get("action")
    meeting_id = event.get("meetingId", "")
    user_id = event.get("userId", "")
    bucket = event.get("bucket", _get_data_bucket())
    report_key = event.get("reportKey", "")

    logger.info(
        "Agent handler invoked: action=%s meeting=%s user=%s",
        action,
        meeting_id,
        user_id,
    )

    if action != "run_agent":
        raise ValueError(f"Unknown action: {action}")

    if not meeting_id or not user_id or not report_key:
        raise ValueError("meetingId, userId, and reportKey are required")

    # 1. Load the generated meeting report
    report = load_report(bucket, report_key)
    logger.info("Report loaded: title=%s", report.get("meeting_title", ""))

    # 2. Load prior meeting context (RAG)
    prior_context = get_prior_meeting_context(user_id, meeting_id)

    # 3. Invoke Bedrock to analyze
    analysis = analyze_with_bedrock(report, prior_context)
    logger.info(
        "Analysis complete: overdue=%d follow_up=%s enhancements=%d",
        len(analysis.get("overdue_items", [])),
        "yes" if analysis.get("follow_up_suggestion") else "no",
        len(analysis.get("notification_enhancements", [])),
    )

    # 4. Send action item notifications
    notifications_sent = send_action_notifications(report, analysis)
    logger.info("Notifications sent: %d", len(notifications_sent))

    # 5. Send overdue notification if applicable
    overdue_items = analysis.get("overdue_items", [])
    if overdue_items:
        send_overdue_notification(overdue_items, report)

    # 6. Send follow-up suggestion if applicable
    follow_up = analysis.get("follow_up_suggestion")
    if follow_up and follow_up.get("recommended"):
        send_follow_up_notification(follow_up, report)

    # 7. Build and store agent report
    agent_report = {
        "agent_execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "meeting_id": meeting_id,
        "meeting_title": report.get("meeting_title", ""),
        "notifications_sent": notifications_sent,
        "overdue_items": overdue_items,
        "follow_up_suggestion": follow_up,
    }

    agent_report_key = store_agent_report(user_id, meeting_id, agent_report)

    logger.info("Agent completed successfully: meeting=%s", meeting_id)

    return {
        "status": "success",
        "agentReportKey": agent_report_key,
        "notificationsSent": len(notifications_sent),
        "overdueItemsDetected": len(overdue_items),
        "followUpRecommended": bool(follow_up and follow_up.get("recommended")),
    }

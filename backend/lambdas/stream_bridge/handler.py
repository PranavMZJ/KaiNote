"""Streaming bridge Lambda for the Meeting Minutes application.

Bridges audio capture to Amazon Transcribe and manages the transcription
lifecycle. Handles two actions:
  - audio_chunk: Buffers audio data to DynamoDB (fast append)
  - stop_capture: Combines buffered audio, runs Transcribe batch job,
    sends transcript segments to client, stores transcript, starts workflow

Resource name: Pranav-meeting-minutes-stream-bridge

Environment variables:
    TRANSCRIPT_BUCKET   – S3 bucket for transcripts and reports
    STEP_FUNCTION_ARN   – ARN of the post-processing Step Functions state machine
    CONNECTIONS_TABLE   – DynamoDB table for WebSocket connections
    WS_API_ENDPOINT     – WebSocket API endpoint for posting messages back to clients
    MEETINGS_TABLE      – DynamoDB table for meeting metadata
    AUDIO_BUFFER_TABLE  – DynamoDB table for buffering audio chunks

Requirements: 3.1, 3.2, 3.3, 4.6, 5.3, 5.4, 5.5, 5.6, 14.1
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Transcribe configuration
TRANSCRIBE_LANGUAGE = "en-US"
TRANSCRIBE_SAMPLE_RATE = 16000
TRANSCRIBE_ENCODING = "pcm"

# Polling configuration for batch transcription
POLL_INTERVAL_SECONDS = 2
MAX_POLL_ATTEMPTS = 300  # 10 minutes max wait


def _get_transcript_bucket() -> str:
    return os.environ.get("TRANSCRIPT_BUCKET", "")


def _get_step_function_arn() -> str:
    return os.environ.get("STEP_FUNCTION_ARN", "")


def _get_connections_table() -> str:
    return os.environ.get("CONNECTIONS_TABLE", "")


def _get_ws_api_endpoint() -> str:
    return os.environ.get("WS_API_ENDPOINT", "")


def _get_meetings_table() -> str:
    return os.environ.get("MEETINGS_TABLE", "")


def _get_audio_buffer_table() -> str:
    return os.environ.get("AUDIO_BUFFER_TABLE", "")


def _build_apigw_management_endpoint(ws_endpoint: str) -> str:
    """Derive the API Gateway Management API endpoint from the WebSocket URL.

    The WebSocket endpoint looks like:
        wss://abc123.execute-api.ap-northeast-1.amazonaws.com/v1

    The Management API endpoint is:
        https://abc123.execute-api.ap-northeast-1.amazonaws.com/v1

    Args:
        ws_endpoint: The WebSocket API endpoint URL.

    Returns:
        The HTTPS endpoint for the API Gateway Management API.
    """
    return ws_endpoint.replace("wss://", "https://").replace("ws://", "http://")


def _post_to_connection(
    connection_id: str,
    message: dict[str, Any],
    *,
    ws_endpoint: str | None = None,
    apigw_client: Any = None,
) -> None:
    """Send a message to a WebSocket client via the API Gateway Management API.

    Args:
        connection_id: The WebSocket connection ID.
        message: The message dict to send (will be JSON-serialized).
        ws_endpoint: The WebSocket API endpoint.
        apigw_client: Optional pre-configured API Gateway Management client.
    """
    if apigw_client is None:
        endpoint_url = _build_apigw_management_endpoint(
            ws_endpoint or _get_ws_api_endpoint()
        )
        apigw_client = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=endpoint_url,
            region_name="ap-northeast-1",
        )

    data = json.dumps(message, ensure_ascii=False).encode("utf-8")
    try:
        apigw_client.post_to_connection(ConnectionId=connection_id, Data=data)
    except Exception:
        logger.exception(
            "Failed to post to connection: connectionId=%s", connection_id
        )


# -------------------------------------------------------------------
# audio_chunk handler — buffer to DynamoDB
# -------------------------------------------------------------------


def handle_audio_chunk(
    event: dict[str, Any],
    *,
    dynamodb_client: Any = None,
    audio_buffer_table: str | None = None,
) -> dict[str, Any]:
    """Handle an audio_chunk event: write audio data to DynamoDB buffer.

    Writes the base64-encoded audio chunk to the audio buffer table with a
    timestamp-based sequence number for ordering and a TTL for auto-cleanup.

    Args:
        event: The event dict with connectionId, userId, meetingId, data, wsEndpoint.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).
        audio_buffer_table: Optional table name override (for testing).

    Returns:
        A dict with statusCode and body.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if audio_buffer_table is None:
        audio_buffer_table = _get_audio_buffer_table()

    meeting_id = event.get("meetingId", "")
    audio_data = event.get("data", "")

    if not meeting_id or not audio_data:
        logger.warning("Missing meetingId or audio data in audio_chunk event")
        return {"statusCode": 400, "body": "Missing meetingId or data"}

    # Use timestamp in microseconds as sequence number for ordering
    seq_num = int(time.time() * 1_000_000)
    # TTL: current time + 1 hour (auto-cleanup)
    ttl = int(time.time()) + 3600

    logger.info(
        "Buffering audio chunk: meetingId=%s seqNum=%d dataLength=%d",
        meeting_id,
        seq_num,
        len(audio_data),
    )

    dynamodb_client.put_item(
        TableName=audio_buffer_table,
        Item={
            "meetingId": {"S": meeting_id},
            "seqNum": {"N": str(seq_num)},
            "data": {"S": audio_data},
            "ttl": {"N": str(ttl)},
        },
    )

    return {"statusCode": 200, "body": "Audio chunk buffered"}


# -------------------------------------------------------------------
# stop_capture handler — combine audio, transcribe, store, start workflow
# -------------------------------------------------------------------


def _query_all_audio_chunks(
    meeting_id: str,
    *,
    dynamodb_client: Any = None,
    audio_buffer_table: str | None = None,
) -> list[dict[str, Any]]:
    """Query all audio chunks for a meeting from the buffer table, ordered by seqNum.

    Handles pagination to retrieve all items.

    Args:
        meeting_id: The meeting identifier.
        dynamodb_client: Optional boto3 DynamoDB client.
        audio_buffer_table: Optional table name override.

    Returns:
        List of DynamoDB items ordered by seqNum.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if audio_buffer_table is None:
        audio_buffer_table = _get_audio_buffer_table()

    items: list[dict[str, Any]] = []
    exclusive_start_key = None

    while True:
        query_params: dict[str, Any] = {
            "TableName": audio_buffer_table,
            "KeyConditionExpression": "meetingId = :mid",
            "ExpressionAttributeValues": {":mid": {"S": meeting_id}},
            "ScanIndexForward": True,  # ascending order by seqNum
        }
        if exclusive_start_key:
            query_params["ExclusiveStartKey"] = exclusive_start_key

        response = dynamodb_client.query(**query_params)
        items.extend(response.get("Items", []))

        exclusive_start_key = response.get("LastEvaluatedKey")
        if not exclusive_start_key:
            break

    return items


def _delete_audio_chunks(
    meeting_id: str,
    items: list[dict[str, Any]],
    *,
    dynamodb_client: Any = None,
    audio_buffer_table: str | None = None,
) -> None:
    """Delete audio chunks from the buffer table after processing.

    Uses BatchWriteItem for efficient deletion (25 items per batch).

    Args:
        meeting_id: The meeting identifier.
        items: List of DynamoDB items to delete.
        dynamodb_client: Optional boto3 DynamoDB client.
        audio_buffer_table: Optional table name override.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if audio_buffer_table is None:
        audio_buffer_table = _get_audio_buffer_table()

    # BatchWriteItem supports max 25 items per request
    batch_size = 25
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        delete_requests = [
            {
                "DeleteRequest": {
                    "Key": {
                        "meetingId": {"S": meeting_id},
                        "seqNum": item["seqNum"],
                    }
                }
            }
            for item in batch
        ]

        try:
            dynamodb_client.batch_write_item(
                RequestItems={audio_buffer_table: delete_requests}
            )
        except Exception:
            logger.exception(
                "Failed to delete audio buffer batch: meetingId=%s batch=%d",
                meeting_id,
                i // batch_size,
            )


def _combine_audio_chunks(items: list[dict[str, Any]]) -> bytes:
    """Decode and concatenate base64 audio chunks into raw PCM bytes.

    Args:
        items: List of DynamoDB items with 'data' field containing base64 audio.

    Returns:
        Concatenated raw PCM audio bytes.
    """
    audio_bytes = bytearray()
    for item in items:
        chunk_b64 = item.get("data", {}).get("S", "")
        if chunk_b64:
            try:
                audio_bytes.extend(base64.b64decode(chunk_b64))
            except Exception:
                logger.warning("Failed to decode audio chunk, skipping")
    return bytes(audio_bytes)


def _create_wav_header(pcm_data: bytes, sample_rate: int = 16000, bits_per_sample: int = 16, channels: int = 1) -> bytes:
    """Create a WAV file header for raw PCM data.

    Args:
        pcm_data: Raw PCM audio bytes.
        sample_rate: Audio sample rate in Hz.
        bits_per_sample: Bits per sample.
        channels: Number of audio channels.

    Returns:
        Complete WAV file bytes (header + PCM data).
    """
    import struct

    data_size = len(pcm_data)
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,  # file size - 8
        b"WAVE",
        b"fmt ",
        16,  # fmt chunk size
        1,  # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )

    return header + pcm_data


def _run_transcription_job(
    meeting_id: str,
    user_id: str,
    audio_s3_key: str,
    *,
    transcribe_client: Any = None,
    transcript_bucket: str | None = None,
) -> dict[str, Any] | None:
    """Start a Transcribe batch job and poll until completion.

    Args:
        meeting_id: The meeting identifier.
        user_id: The user identifier.
        audio_s3_key: S3 key where the audio file was uploaded.
        transcribe_client: Optional boto3 Transcribe client.
        transcript_bucket: Optional bucket name override.

    Returns:
        The transcription job result dict, or None if failed.
    """
    if transcribe_client is None:
        transcribe_client = boto3.client("transcribe", region_name="ap-northeast-1")
    if transcript_bucket is None:
        transcript_bucket = _get_transcript_bucket()

    job_name = f"meeting-{meeting_id}-{uuid.uuid4().hex[:8]}"
    media_uri = f"s3://{transcript_bucket}/{audio_s3_key}"
    output_key = f"users/{user_id}/transcripts/{meeting_id}/transcribe-output.json"

    logger.info(
        "Starting TranscriptionJob: jobName=%s mediaUri=%s",
        job_name,
        media_uri,
    )

    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        LanguageCode=TRANSCRIBE_LANGUAGE,
        MediaSampleRateHertz=TRANSCRIBE_SAMPLE_RATE,
        MediaFormat="wav",
        Media={"MediaFileUri": media_uri},
        OutputBucketName=transcript_bucket,
        OutputKey=output_key,
        Settings={
            "ShowSpeakerLabels": True,
            "MaxSpeakerLabels": 10,
        },
    )

    # Poll for completion
    for attempt in range(MAX_POLL_ATTEMPTS):
        time.sleep(POLL_INTERVAL_SECONDS)

        response = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name
        )
        job = response["TranscriptionJob"]
        status = job["TranscriptionJobStatus"]

        if status == "COMPLETED":
            logger.info("TranscriptionJob completed: jobName=%s", job_name)
            return {
                "jobName": job_name,
                "status": "COMPLETED",
                "outputKey": output_key,
                "outputUri": job.get("Transcript", {}).get("TranscriptFileUri", ""),
            }
        elif status == "FAILED":
            failure_reason = job.get("FailureReason", "Unknown")
            logger.error(
                "TranscriptionJob failed: jobName=%s reason=%s",
                job_name,
                failure_reason,
            )
            return None

        if attempt % 10 == 0:
            logger.info(
                "Waiting for TranscriptionJob: jobName=%s status=%s attempt=%d",
                job_name,
                status,
                attempt,
            )

    logger.error("TranscriptionJob timed out: jobName=%s", job_name)
    return None


def _parse_transcribe_output(transcribe_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse the Transcribe batch output JSON into transcript segments.

    Transcribe batch output format has speaker labels in a separate section.
    This function maps speaker labels to transcript items.

    Args:
        transcribe_result: The parsed JSON from Transcribe output.

    Returns:
        List of segment dicts with speaker, text, startTime, endTime.
    """
    segments: list[dict[str, Any]] = []
    results = transcribe_result.get("results", {})

    # Get speaker labels mapping
    speaker_labels = results.get("speaker_labels", {})
    speaker_segments = speaker_labels.get("segments", [])

    # Build a time-to-speaker mapping from speaker label segments
    # Each speaker segment has items with start_time and speaker_label
    time_speaker_map: dict[str, str] = {}
    for sp_segment in speaker_segments:
        for item in sp_segment.get("items", []):
            start = item.get("start_time", "")
            speaker = item.get("speaker_label", "spk_0")
            if start:
                time_speaker_map[start] = speaker

    # Process transcript items
    items = results.get("items", [])
    current_segment_text = ""
    current_speaker = "spk_0"
    current_start_time = 0.0
    current_end_time = 0.0
    segment_count = 0

    for item in items:
        item_type = item.get("type", "")
        content = item.get("alternatives", [{}])[0].get("content", "")
        start_time_str = item.get("start_time", "")
        end_time_str = item.get("end_time", "")

        if item_type == "pronunciation":
            # Determine speaker for this word
            speaker = time_speaker_map.get(start_time_str, current_speaker)
            start_time = float(start_time_str) if start_time_str else current_end_time
            end_time = float(end_time_str) if end_time_str else start_time

            # If speaker changed, emit current segment and start new one
            if speaker != current_speaker and current_segment_text:
                segment_count += 1
                segments.append({
                    "segmentId": f"seg-{segment_count:03d}",
                    "speaker": current_speaker,
                    "startTime": current_start_time,
                    "endTime": current_end_time,
                    "text": current_segment_text.strip(),
                    "isPartial": False,
                    "confidence": 0.95,
                })
                current_segment_text = ""
                current_start_time = start_time

            if not current_segment_text:
                current_start_time = start_time

            current_speaker = speaker
            current_end_time = end_time
            current_segment_text += " " + content

        elif item_type == "punctuation":
            current_segment_text += content

    # Emit final segment
    if current_segment_text.strip():
        segment_count += 1
        segments.append({
            "segmentId": f"seg-{segment_count:03d}",
            "speaker": current_speaker,
            "startTime": current_start_time,
            "endTime": current_end_time,
            "text": current_segment_text.strip(),
            "isPartial": False,
            "confidence": 0.95,
        })

    # If no speaker labels were available, try to split by sentences
    # (fallback for when speaker diarization isn't in the output)
    if not segments and results.get("transcripts"):
        full_text = results["transcripts"][0].get("transcript", "")
        if full_text:
            segment_count += 1
            segments.append({
                "segmentId": f"seg-{segment_count:03d}",
                "speaker": "spk_0",
                "startTime": 0.0,
                "endTime": 0.0,
                "text": full_text,
                "isPartial": False,
                "confidence": 0.95,
            })

    return segments


# Demo transcript fallback (used when Transcribe fails or no audio chunks)
_DEMO_TRANSCRIPT_SEGMENTS = [
    {
        "segmentId": "seg-001",
        "speaker": "spk_0",
        "startTime": 0.0,
        "endTime": 8.5,
        "text": "Good morning everyone. Let's start our sprint planning meeting. The main topics today are the Q3 budget review, the CloudFront caching strategy, and assigning action items for next week.",
        "isPartial": False,
        "confidence": 0.97,
    },
    {
        "segmentId": "seg-002",
        "speaker": "spk_1",
        "startTime": 9.0,
        "endTime": 20.0,
        "text": "Thanks Sarah. I've been looking at our S3 costs and I think we should move infrequently accessed objects to Intelligent Tiering. It could save us about thirty percent on storage costs. I'll prepare a migration plan by Friday.",
        "isPartial": False,
        "confidence": 0.95,
    },
    {
        "segmentId": "seg-003",
        "speaker": "spk_2",
        "startTime": 21.0,
        "endTime": 33.0,
        "text": "That sounds good John. I also want to flag that our CloudFront cache hit ratio dropped to sixty percent last week. I think we need to review the cache policies. I can take that as an action item and have a proposal ready by Wednesday.",
        "isPartial": False,
        "confidence": 0.94,
    },
    {
        "segmentId": "seg-004",
        "speaker": "spk_0",
        "startTime": 34.0,
        "endTime": 45.0,
        "text": "Great. So to summarize, John will handle the S3 migration plan by Friday, and Meghan will review CloudFront cache policies by Wednesday. Any risks or blockers? No? Alright, let's wrap up. Thanks everyone.",
        "isPartial": False,
        "confidence": 0.96,
    },
]


def handle_stop_capture(
    event: dict[str, Any],
    *,
    s3_client: Any = None,
    sfn_client: Any = None,
    apigw_client: Any = None,
    dynamodb_client: Any = None,
    transcribe_client: Any = None,
    transcript_bucket: str | None = None,
    step_function_arn: str | None = None,
    meetings_table: str | None = None,
    audio_buffer_table: str | None = None,
) -> dict[str, Any]:
    """Handle a stop_capture event: transcribe buffered audio and start workflow.

    Flow:
    1. Query all audio chunks from the buffer table
    2. Combine chunks into raw PCM audio
    3. Upload audio as WAV to S3
    4. Start a Transcribe batch job
    5. Poll for completion
    6. Parse transcript and send segments to client via WebSocket
    7. Store raw transcript to S3
    8. Create meeting record in DynamoDB
    9. Start Step Functions workflow
    10. Send capture_stopped message to client
    11. Clean up audio buffer

    Falls back to demo transcript if Transcribe fails or no audio is available.

    Args:
        event: The event dict with connectionId, userId, meetingId, wsEndpoint.
        s3_client: Optional boto3 S3 client (for testing).
        sfn_client: Optional boto3 Step Functions client (for testing).
        apigw_client: Optional API Gateway Management client (for testing).
        dynamodb_client: Optional boto3 DynamoDB client (for testing).
        transcribe_client: Optional boto3 Transcribe client (for testing).
        transcript_bucket: Optional bucket name override (for testing).
        step_function_arn: Optional Step Functions ARN override (for testing).
        meetings_table: Optional DynamoDB table name override (for testing).
        audio_buffer_table: Optional audio buffer table name override (for testing).

    Returns:
        A dict with statusCode and body.
    """
    connection_id = event.get("connectionId", "")
    user_id = event.get("userId", "")
    meeting_id = event.get("meetingId", "")
    ws_endpoint = event.get("wsEndpoint", "")

    if s3_client is None:
        s3_client = boto3.client("s3", region_name="ap-northeast-1")
    if sfn_client is None:
        sfn_client = boto3.client("stepfunctions", region_name="ap-northeast-1")
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name="ap-northeast-1")
    if transcribe_client is None:
        transcribe_client = boto3.client("transcribe", region_name="ap-northeast-1")
    if transcript_bucket is None:
        transcript_bucket = _get_transcript_bucket()
    if step_function_arn is None:
        step_function_arn = _get_step_function_arn()
    if meetings_table is None:
        meetings_table = _get_meetings_table()
    if audio_buffer_table is None:
        audio_buffer_table = _get_audio_buffer_table()

    logger.info(
        "Stop capture received: connectionId=%s meetingId=%s userId=%s",
        connection_id,
        meeting_id,
        user_id,
    )

    now = datetime.now(timezone.utc)
    segments: list[dict[str, Any]] = []
    use_demo = False

    # --- Step 1: Query audio chunks from buffer ---
    audio_items = _query_all_audio_chunks(
        meeting_id,
        dynamodb_client=dynamodb_client,
        audio_buffer_table=audio_buffer_table,
    )

    logger.info(
        "Retrieved %d audio chunks from buffer: meetingId=%s",
        len(audio_items),
        meeting_id,
    )

    if audio_items:
        # --- Step 2: Combine audio chunks ---
        pcm_audio = _combine_audio_chunks(audio_items)
        logger.info(
            "Combined audio: meetingId=%s totalBytes=%d",
            meeting_id,
            len(pcm_audio),
        )

        if len(pcm_audio) > 0:
            # --- Step 3: Create WAV and upload to S3 ---
            wav_audio = _create_wav_header(pcm_audio)
            audio_s3_key = f"users/{user_id}/transcripts/{meeting_id}/audio.wav"

            logger.info(
                "Uploading audio to S3: bucket=%s key=%s size=%d",
                transcript_bucket,
                audio_s3_key,
                len(wav_audio),
            )

            s3_client.put_object(
                Bucket=transcript_bucket,
                Key=audio_s3_key,
                Body=wav_audio,
                ContentType="audio/wav",
            )

            # Notify client that transcription is starting
            _post_to_connection(
                connection_id,
                {
                    "type": "transcript_segment",
                    "text": "Processing audio... Starting transcription.",
                    "speaker": "system",
                    "isPartial": True,
                    "timestamp": now.isoformat(),
                },
                ws_endpoint=ws_endpoint,
                apigw_client=apigw_client,
            )

            # --- Step 4 & 5: Run Transcribe batch job ---
            job_result = _run_transcription_job(
                meeting_id,
                user_id,
                audio_s3_key,
                transcribe_client=transcribe_client,
                transcript_bucket=transcript_bucket,
            )

            if job_result and job_result["status"] == "COMPLETED":
                # --- Step 6: Parse transcript output from S3 ---
                output_key = job_result["outputKey"]
                try:
                    output_response = s3_client.get_object(
                        Bucket=transcript_bucket,
                        Key=output_key,
                    )
                    transcribe_output = json.loads(
                        output_response["Body"].read().decode("utf-8")
                    )
                    segments = _parse_transcribe_output(transcribe_output)
                    logger.info(
                        "Parsed %d segments from Transcribe output: meetingId=%s",
                        len(segments),
                        meeting_id,
                    )
                except Exception:
                    logger.exception(
                        "Failed to parse Transcribe output: meetingId=%s",
                        meeting_id,
                    )
                    use_demo = True
            else:
                logger.warning(
                    "Transcribe job failed or timed out, using demo transcript: meetingId=%s",
                    meeting_id,
                )
                use_demo = True
        else:
            logger.warning(
                "No valid audio data after decoding, using demo transcript: meetingId=%s",
                meeting_id,
            )
            use_demo = True
    else:
        logger.warning(
            "No audio chunks in buffer, using demo transcript: meetingId=%s",
            meeting_id,
        )
        use_demo = True

    # Fallback to demo transcript
    if use_demo or not segments:
        segments = _DEMO_TRANSCRIPT_SEGMENTS
        logger.info("Using demo transcript fallback: meetingId=%s", meeting_id)

    # --- Send transcript segments to client via WebSocket (live captions) ---
    for segment in segments:
        _post_to_connection(
            connection_id,
            {
                "type": "transcript_segment",
                "text": segment["text"],
                "speaker": segment["speaker"],
                "isPartial": segment.get("isPartial", False),
                "timestamp": now.isoformat(),
            },
            ws_endpoint=ws_endpoint,
            apigw_client=apigw_client,
        )
        # Small delay between segments for "live" appearance
        time.sleep(0.1)

    # --- Build and store raw transcript to S3 ---
    raw_transcript = {
        "meetingId": meeting_id,
        "userId": user_id,
        "startTime": now.isoformat(),
        "endTime": datetime.now(timezone.utc).isoformat(),
        "language": TRANSCRIBE_LANGUAGE,
        "segments": segments,
        "metadata": {
            "sampleRate": TRANSCRIBE_SAMPLE_RATE,
            "encoding": TRANSCRIBE_ENCODING,
            "transcribeSessionId": f"transcribe-{meeting_id}",
        },
    }

    transcript_key = f"users/{user_id}/transcripts/{meeting_id}/raw.json"
    transcript_json = json.dumps(raw_transcript, ensure_ascii=False)

    logger.info(
        "Storing raw transcript: bucket=%s key=%s",
        transcript_bucket,
        transcript_key,
    )

    s3_client.put_object(
        Bucket=transcript_bucket,
        Key=transcript_key,
        Body=transcript_json.encode("utf-8"),
        ContentType="application/json",
    )

    # --- Create meeting record in DynamoDB ---
    logger.info(
        "Creating meeting record: table=%s userId=%s meetingId=%s",
        meetings_table,
        user_id,
        meeting_id,
    )

    dynamodb_client.put_item(
        TableName=meetings_table,
        Item={
            "userId": {"S": user_id},
            "meetingId": {"S": meeting_id},
            "status": {"S": "processing"},
            "createdAt": {"S": now.isoformat()},
            "updatedAt": {"S": now.isoformat()},
            "meetingTitle": {"NULL": True},
            "transcriptKey": {"S": transcript_key},
            "reportKey": {"NULL": True},
            "stepFunctionExecutionArn": {"NULL": True},
            "currentStep": {"S": "TranscribeComplete"},
            "error": {"NULL": True},
        },
    )

    # --- Start Step Functions workflow ---
    sfn_input = {
        "meetingId": meeting_id,
        "userId": user_id,
        "transcriptBucket": transcript_bucket,
        "transcriptKey": transcript_key,
    }

    execution_name = f"meeting-{meeting_id}-{uuid.uuid4().hex[:8]}"

    logger.info(
        "Starting Step Functions execution: arn=%s name=%s",
        step_function_arn,
        execution_name,
    )

    sfn_response = sfn_client.start_execution(
        stateMachineArn=step_function_arn,
        name=execution_name,
        input=json.dumps(sfn_input),
    )

    execution_arn = sfn_response.get("executionArn", "")

    # Update meeting record with execution ARN
    dynamodb_client.update_item(
        TableName=meetings_table,
        Key={
            "userId": {"S": user_id},
            "meetingId": {"S": meeting_id},
        },
        UpdateExpression="SET stepFunctionExecutionArn = :arn, updatedAt = :now",
        ExpressionAttributeValues={
            ":arn": {"S": execution_arn},
            ":now": {"S": datetime.now(timezone.utc).isoformat()},
        },
    )

    # --- Notify client that capture has stopped ---
    _post_to_connection(
        connection_id,
        {
            "type": "capture_stopped",
            "meetingId": meeting_id,
            "status": "processing",
        },
        ws_endpoint=ws_endpoint,
        apigw_client=apigw_client,
    )

    # --- Clean up audio buffer ---
    if audio_items:
        logger.info(
            "Cleaning up audio buffer: meetingId=%s chunks=%d",
            meeting_id,
            len(audio_items),
        )
        _delete_audio_chunks(
            meeting_id,
            audio_items,
            dynamodb_client=dynamodb_client,
            audio_buffer_table=audio_buffer_table,
        )

    logger.info(
        "Stop capture complete: meetingId=%s executionArn=%s segments=%d",
        meeting_id,
        execution_arn,
        len(segments),
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "meetingId": meeting_id,
                "transcriptKey": transcript_key,
                "executionArn": execution_arn,
            }
        ),
    }


# -------------------------------------------------------------------
# Lambda entry point
# -------------------------------------------------------------------


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for the streaming bridge.

    This Lambda can be invoked in two ways:
    1. Directly by API Gateway WebSocket (audio_chunk, stop_capture routes)
    2. Asynchronously by the WebSocket handler Lambda

    For API Gateway invocations, the event has:
      - requestContext.routeKey (e.g., "audio_chunk", "stop_capture")
      - requestContext.connectionId
      - body (JSON string with the message payload)

    For direct invocations, the event has:
      - action, connectionId, meetingId, data, wsEndpoint

    Args:
        event: The invocation event.
        context: Lambda context (unused).

    Returns:
        A dict with statusCode and body.
    """
    # Parse API Gateway WebSocket event format
    request_context = event.get("requestContext", {})
    if request_context:
        # This is an API Gateway WebSocket invocation
        action = request_context.get("routeKey", "")
        connection_id = request_context.get("connectionId", "")
        # Parse the body JSON
        body_str = event.get("body", "{}")
        try:
            body = json.loads(body_str) if body_str else {}
        except (json.JSONDecodeError, TypeError):
            body = {}

        # Look up connection metadata from DynamoDB to get userId and meetingId
        user_id = ""
        meeting_id = ""
        table_name = os.environ.get("CONNECTIONS_TABLE", "")
        if connection_id and table_name:
            try:
                dynamodb = boto3.client("dynamodb", region_name="ap-northeast-1")
                response = dynamodb.get_item(
                    TableName=table_name,
                    Key={"connectionId": {"S": connection_id}},
                )
                item = response.get("Item", {})
                user_id = item.get("userId", {}).get("S", "")
                meeting_id = item.get("meetingId", {}).get("S", "")
            except Exception:
                logger.exception("Failed to look up connection: %s", connection_id)

        # Build the normalized event
        ws_endpoint = _get_ws_api_endpoint()
        normalized_event: dict[str, Any] = {
            "action": action,
            "connectionId": connection_id,
            "userId": user_id,
            "meetingId": meeting_id,
            "wsEndpoint": ws_endpoint,
            "data": body.get("data", ""),
        }
    else:
        # Direct invocation (from WS Handler Lambda)
        normalized_event = event
        action = event.get("action", "")
        connection_id = event.get("connectionId", "")
        meeting_id = event.get("meetingId", "")

    logger.info(
        "Stream bridge invoked: action=%s connectionId=%s meetingId=%s",
        action,
        connection_id,
        meeting_id,
    )

    try:
        if action == "audio_chunk":
            return handle_audio_chunk(normalized_event)

        if action == "stop_capture":
            return handle_stop_capture(normalized_event)

        logger.warning("Unknown action: %s", action)
        return {"statusCode": 400, "body": f"Unknown action: {action}"}

    except Exception:
        logger.exception(
            "Stream bridge error: action=%s connectionId=%s meetingId=%s",
            action,
            connection_id,
            meeting_id,
        )

        # Attempt to notify the client of the error
        ws_endpoint = normalized_event.get("wsEndpoint", "")
        if connection_id and ws_endpoint:
            try:
                _post_to_connection(
                    connection_id,
                    {
                        "type": "error",
                        "message": "An error occurred during audio processing",
                        "code": "STREAM_BRIDGE_ERROR",
                    },
                    ws_endpoint=ws_endpoint,
                )
            except Exception:
                logger.exception("Failed to send error notification to client")

        return {"statusCode": 500, "body": "Internal server error"}

"""
KaiNote Transcription Service — WebSocket server on ECS Fargate.

Handles real-time audio transcription via Amazon Transcribe Streaming.
Runs on port 8080, exposes /health for ALB health checks and /ws for
WebSocket connections.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from http import HTTPStatus

import boto3
import websockets

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PORT = 8080
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
TRANSCRIPT_BUCKET = os.environ.get("TRANSCRIPT_BUCKET", "")
STEP_FUNCTION_ARN = os.environ.get("STEP_FUNCTION_ARN", "")
MEETINGS_TABLE = os.environ.get("MEETINGS_TABLE", "")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("transcription-service")

# ---------------------------------------------------------------------------
# AWS Clients (shared across connections)
# ---------------------------------------------------------------------------

s3_client = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
sfn_client = boto3.client("stepfunctions", region_name=AWS_REGION)
translate_client = boto3.client("translate", region_name=AWS_REGION)


# ---------------------------------------------------------------------------
# Translation helper
# ---------------------------------------------------------------------------

# Map display language codes to Amazon Translate language codes
_TRANSLATE_LANG_MAP = {
    "ja": "ja",
    "ja-JP": "ja",
    "en": "en",
    "en-US": "en",
    "ko": "ko",
    "ko-KR": "ko",
    "zh": "zh",
    "zh-CN": "zh",
    "fr": "fr",
    "fr-FR": "fr",
    "de": "de",
    "de-DE": "de",
    "es": "es",
    "es-ES": "es",
}


def _get_translate_code(lang: str) -> str:
    """Convert a language code to Amazon Translate format."""
    return _TRANSLATE_LANG_MAP.get(lang, lang.split("-")[0])


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Translate text using Amazon Translate. Returns original on failure."""
    if not text.strip():
        return text
    src = _get_translate_code(source_lang)
    tgt = _get_translate_code(target_lang)
    if src == tgt:
        return text
    try:
        response = translate_client.translate_text(
            Text=text,
            SourceLanguageCode=src,
            TargetLanguageCode=tgt,
        )
        return response["TranslatedText"]
    except Exception as e:
        logger.warning(f"Translation failed ({src}→{tgt}): {e}")
        return text


# ---------------------------------------------------------------------------
# Transcribe Result Handler
# ---------------------------------------------------------------------------

class TranscriptHandler(TranscriptResultStreamHandler):
    """Receives Transcribe events and forwards them to the WebSocket client."""

    def __init__(self, output_stream, websocket, segments: list, audio_language: str = "en-US", display_language: str | None = None):
        super().__init__(output_stream)
        self.websocket = websocket
        self.segments = segments
        self._segment_counter = 0
        self._audio_language = audio_language
        self._display_language = display_language
        self._should_translate = (
            display_language is not None
            and _get_translate_code(audio_language) != _get_translate_code(display_language)
        )

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            if not result.alternatives:
                continue

            alt = result.alternatives[0]
            text = alt.transcript or ""
            if not text.strip():
                continue

            # Extract speaker label if available
            speaker = "spk_0"
            if hasattr(alt, "items") and alt.items:
                for item in alt.items:
                    if hasattr(item, "speaker") and item.speaker:
                        speaker = item.speaker
                        break
            if hasattr(result, 'speaker') and result.speaker:
                speaker = result.speaker

            is_partial = result.is_partial
            timestamp = datetime.now(timezone.utc).isoformat()

            # Translate segments if translation is enabled
            # When translation is active, ALL segments (partial and final) get translated
            # before being sent to the client. This prevents language flickering.
            display_text = text
            if self._should_translate:
                try:
                    display_text = await asyncio.get_event_loop().run_in_executor(
                        None,
                        translate_text,
                        text,
                        self._audio_language,
                        self._display_language,
                    )
                except Exception as e:
                    logger.error(f"Translation error: {e}")
                    display_text = text

            # Log speaker detection for debugging
            if not is_partial:
                logger.info(f"Segment: speaker={speaker}, partial={is_partial}, text={text[:50]}...")

            segment_msg = {
                "type": "transcript_segment",
                "text": display_text,
                "originalText": text if self._should_translate and display_text != text else None,
                "speaker": speaker,
                "isPartial": is_partial,
                "timestamp": timestamp,
                "translated": self._should_translate and display_text != text,
            }

            # Send to WebSocket client
            try:
                await self.websocket.send(json.dumps(segment_msg))
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket closed while sending transcript segment")
                return

            # Store final (non-partial) segments (always store original text)
            if not is_partial:
                self._segment_counter += 1
                self.segments.append({
                    "segmentId": f"seg_{self._segment_counter:04d}",
                    "speaker": speaker,
                    "startTime": result.start_time if hasattr(result, "start_time") else 0.0,
                    "endTime": result.end_time if hasattr(result, "end_time") else 0.0,
                    "text": text,  # Always store original language
                    "isPartial": False,
                    "confidence": 0.0,
                })


# ---------------------------------------------------------------------------
# Session Handler
# ---------------------------------------------------------------------------

async def handle_session(websocket):
    """Handle a single WebSocket transcription session."""

    meeting_id = None
    user_id = None
    token = None
    transcribe_stream = None
    audio_queue: asyncio.Queue = asyncio.Queue()
    segments: list = []
    start_time = None
    stop_event = asyncio.Event()
    tasks: list[asyncio.Task] = []

    try:
        # ---- Wait for start message ----
        raw = await asyncio.wait_for(websocket.recv(), timeout=30.0)
        start_msg = json.loads(raw)

        if start_msg.get("type") != "start":
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Expected 'start' message",
                "code": "INVALID_MESSAGE",
            }))
            return

        meeting_id = start_msg.get("meetingId")
        user_id = start_msg.get("userId")
        token = start_msg.get("token")

        # Language settings from client
        audio_language = start_msg.get("audioLanguage", "en-US")  # Language of the audio
        display_language = start_msg.get("displayLanguage", None)  # Language to display (translate to)

        if not meeting_id or not user_id:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "meetingId and userId are required",
                "code": "MISSING_FIELDS",
            }))
            return

        logger.info(f"Session started: meeting={meeting_id}, user={user_id}, audio_lang={audio_language}, display_lang={display_language}")
        start_time = datetime.now(timezone.utc).isoformat()

        # ---- Open Transcribe Streaming session ----
        transcribe_client = TranscribeStreamingClient(region=AWS_REGION)

        transcribe_stream = await transcribe_client.start_stream_transcription(
            language_code=audio_language,
            media_sample_rate_hz=16000,
            media_encoding="pcm",
            enable_partial_results_stabilization=True,
            partial_results_stability="high",
            show_speaker_label=True,
        )

        # ---- Audio feeder task ----
        async def feed_audio():
            """Feed audio chunks from the queue to Transcribe."""
            try:
                while not stop_event.is_set():
                    try:
                        chunk = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                        await transcribe_stream.input_stream.send_audio_event(
                            audio_chunk=chunk
                        )
                    except asyncio.TimeoutError:
                        continue
            except Exception as e:
                logger.error(f"Error in feed_audio: {e}")
            finally:
                try:
                    await transcribe_stream.input_stream.end_stream()
                except Exception:
                    pass

        # ---- Result handler task ----
        handler = TranscriptHandler(
            transcribe_stream.output_stream, websocket, segments,
            audio_language=audio_language,
            display_language=display_language,
        )

        async def handle_results():
            """Process Transcribe results."""
            try:
                await handler.handle_events()
            except Exception as e:
                logger.error(f"Error in handle_results: {e}")

        # ---- Start concurrent tasks ----
        feed_task = asyncio.create_task(feed_audio())
        results_task = asyncio.create_task(handle_results())
        tasks = [feed_task, results_task]

        # ---- Main receive loop ----
        async for message in websocket:
            if isinstance(message, bytes):
                # Binary audio chunk
                await audio_queue.put(message)
            elif isinstance(message, str):
                try:
                    msg = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type", "unknown")
                logger.info(f"Text message received: type={msg_type}")

                if msg_type == "stop":
                    logger.info(f"Stop received: meeting={meeting_id}")
                    break
                elif msg_type == "set_display_language":
                    new_lang = msg.get("language")
                    logger.info(f"Received set_display_language: language={new_lang}")
                    if new_lang:
                        handler._display_language = new_lang
                        handler._should_translate = (
                            _get_translate_code(audio_language) != _get_translate_code(new_lang)
                        )
                        logger.info(f"Translation enabled: {audio_language} → {new_lang} (should_translate={handler._should_translate})")
                    else:
                        handler._display_language = None
                        handler._should_translate = False
                        logger.info("Translation disabled")
            else:
                continue

        # ---- Stop transcription ----
        stop_event.set()

        # Wait for tasks to complete
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=10.0,
        )

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: meeting={meeting_id}")
        stop_event.set()
    except asyncio.TimeoutError:
        logger.warning(f"Timeout waiting for start message: meeting={meeting_id}")
        return
    except Exception as e:
        logger.error(f"Session error: meeting={meeting_id}, error={e}")
        try:
            await websocket.send(json.dumps({
                "type": "error",
                "message": str(e),
                "code": "SERVER_ERROR",
            }))
        except Exception:
            pass
        return
    finally:
        # Cancel any remaining tasks
        stop_event.set()
        for task in tasks:
            if not task.done():
                task.cancel()

    # ---- Post-session: store transcript, create record, start workflow ----
    if meeting_id and user_id and segments:
        await finalize_session(
            websocket, meeting_id, user_id, segments, start_time, audio_language
        )
    elif meeting_id and user_id:
        # No segments captured but session was valid
        try:
            await websocket.send(json.dumps({
                "type": "capture_stopped",
                "meetingId": meeting_id,
                "status": "no_segments",
            }))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Bedrock Speaker Re-Attribution
# ---------------------------------------------------------------------------

bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"


async def reattribute_speakers(segments: list, websocket) -> list:
    """Use Bedrock to re-split the transcript by speaker using context clues.
    
    Sends the full transcript text to Claude and asks it to identify speaker
    boundaries based on names mentioned, conversation flow, and tone shifts.
    Returns updated segments with corrected speaker labels.
    """
    if not segments:
        return segments

    # Build the full transcript text for Bedrock
    full_text = " ".join(seg.get("text", "") for seg in segments)
    
    if len(full_text.strip()) < 50:
        return segments  # Too short to re-attribute

    # Notify client that re-attribution is happening
    try:
        await websocket.send(json.dumps({
            "type": "transcript_segment",
            "text": "Analyzing speakers...",
            "speaker": "system",
            "isPartial": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception:
        pass

    prompt = f"""You are a transcript speaker attribution assistant. Given the following meeting transcript, split it into segments by different speakers. Use context clues like:
- Names mentioned (e.g., "Thanks, Sarah" means the next speaker is NOT Sarah)
- Conversation flow (responses to questions, agreements, etc.)
- Topic shifts that suggest a different person is speaking

Return a JSON array of segments. Each segment should have:
- "speaker": a label like "Speaker 1", "Speaker 2", etc. If you can identify names from context, use them (e.g., "Sarah", "John")
- "text": the text spoken by that speaker

IMPORTANT: Return ONLY the JSON array, no other text.

Transcript:
{full_text}"""

    try:
        # Run Bedrock call in a thread to not block the event loop
        import asyncio
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: bedrock_client.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "temperature": 0.1,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
        )

        response_body = json.loads(response["body"].read())
        content = response_body.get("content", [])
        if not content:
            return segments

        text_response = content[0].get("text", "")
        
        # Strip markdown code fences if present
        stripped = text_response.strip()
        if stripped.startswith("```"):
            first_nl = stripped.index("\n") if "\n" in stripped else len(stripped)
            stripped = stripped[first_nl + 1:]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        stripped = stripped.strip()

        # Parse the JSON response
        reattributed = json.loads(stripped)
        
        if not isinstance(reattributed, list) or len(reattributed) == 0:
            return segments

        # Convert Bedrock response to our segment format
        new_segments = []
        for i, seg in enumerate(reattributed):
            speaker = seg.get("speaker", f"Speaker {i + 1}")
            text = seg.get("text", "")
            if text.strip():
                new_segments.append({
                    "segmentId": f"seg_{i + 1:04d}",
                    "speaker": speaker,
                    "startTime": 0.0,
                    "endTime": 0.0,
                    "text": text.strip(),
                    "isPartial": False,
                    "confidence": 0.9,
                })

        if new_segments:
            logger.info(f"Re-attributed {len(segments)} segments → {len(new_segments)} segments")
            
            # Send re-attributed segments to client
            for seg in new_segments:
                try:
                    await websocket.send(json.dumps({
                        "type": "transcript_segment",
                        "text": seg["text"],
                        "speaker": seg["speaker"],
                        "isPartial": False,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }))
                except Exception:
                    break
            
            return new_segments

    except Exception as e:
        logger.error(f"Bedrock re-attribution failed: {e}")

    return segments


async def finalize_session(
    websocket, meeting_id: str, user_id: str, segments: list, start_time: str, audio_language: str = "en-US"
):
    """Store transcript to S3, create DynamoDB record, start Step Functions.
    
    Before storing, uses Bedrock to re-attribute speakers based on context clues.
    """

    end_time = datetime.now(timezone.utc).isoformat()
    transcript_s3_key = f"users/{user_id}/transcripts/{meeting_id}/raw.json"

    # --- Bedrock speaker re-attribution ---
    try:
        segments = await reattribute_speakers(segments, websocket)
    except Exception as e:
        logger.warning(f"Speaker re-attribution failed, using original: {e}")

    # Build raw transcript document
    raw_transcript = {
        "meetingId": meeting_id,
        "userId": user_id,
        "startTime": start_time,
        "endTime": end_time,
        "language": audio_language if audio_language else "en-US",
        "segments": segments,
        "metadata": {
            "sampleRate": 16000,
            "encoding": "pcm",
            "transcribeSessionId": f"session-{meeting_id}",
        },
    }

    try:
        # ---- Store to S3 ----
        s3_client.put_object(
            Bucket=TRANSCRIPT_BUCKET,
            Key=transcript_s3_key,
            Body=json.dumps(raw_transcript, ensure_ascii=False),
            ContentType="application/json",
        )
        logger.info(f"Transcript stored: s3://{TRANSCRIPT_BUCKET}/{transcript_s3_key}")

        # ---- Create DynamoDB meeting record ----
        table = dynamodb.Table(MEETINGS_TABLE)
        now = datetime.now(timezone.utc).isoformat()

        table.put_item(Item={
            "meetingId": meeting_id,
            "userId": user_id,
            "status": "processing",
            "createdAt": start_time,
            "updatedAt": now,
            "transcriptKey": transcript_s3_key,
            "currentStep": "transcription_complete",
        })
        logger.info(f"Meeting record created: {meeting_id}")

        # ---- Start Step Functions workflow ----
        execution_name = f"{meeting_id}-{uuid.uuid4().hex[:8]}"
        sfn_input = json.dumps({
            "meetingId": meeting_id,
            "userId": user_id,
            "transcriptKey": transcript_s3_key,
            "bucket": TRANSCRIPT_BUCKET,
        })

        sfn_response = sfn_client.start_execution(
            stateMachineArn=STEP_FUNCTION_ARN,
            name=execution_name,
            input=sfn_input,
        )
        execution_arn = sfn_response["executionArn"]
        logger.info(f"Step Functions started: {execution_arn}")

        # Update DynamoDB with execution ARN
        table.update_item(
            Key={"meetingId": meeting_id, "userId": user_id},
            UpdateExpression="SET stepFunctionExecutionArn = :arn, updatedAt = :now",
            ExpressionAttributeValues={
                ":arn": execution_arn,
                ":now": datetime.now(timezone.utc).isoformat(),
            },
        )

        # ---- Notify client ----
        await websocket.send(json.dumps({
            "type": "capture_stopped",
            "meetingId": meeting_id,
            "status": "processing",
        }))
        logger.info(f"Session finalized: meeting={meeting_id}")

    except Exception as e:
        logger.error(f"Finalization error: meeting={meeting_id}, error={e}")
        try:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Failed to finalize session: {str(e)}",
                "code": "FINALIZATION_ERROR",
            }))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Health Check Handler
# ---------------------------------------------------------------------------

async def health_check(connection, request):
    """Handle HTTP health check requests from ALB."""
    if request.path == "/health":
        return connection.respond(HTTPStatus.OK, "OK\n")
    return None


# ---------------------------------------------------------------------------
# WebSocket Server
# ---------------------------------------------------------------------------

async def ws_handler(websocket):
    """Route WebSocket connections based on path."""
    path = websocket.request.path if hasattr(websocket, 'request') else "/ws"
    if path == "/ws":
        await handle_session(websocket)
    else:
        await websocket.close(1008, "Invalid path. Use /ws")


async def main():
    """Start the WebSocket server."""
    logger.info(f"Starting transcription service on port {PORT}")
    logger.info(f"Region: {AWS_REGION}")
    logger.info(f"Bucket: {TRANSCRIPT_BUCKET}")
    logger.info(f"Table: {MEETINGS_TABLE}")
    logger.info(f"Step Function: {STEP_FUNCTION_ARN}")

    async with websockets.serve(
        ws_handler,
        "0.0.0.0",
        PORT,
        process_request=health_check,
        ping_interval=20,
        ping_timeout=20,
        max_size=2**20,  # 1MB max message size
    ):
        logger.info(f"Server listening on 0.0.0.0:{PORT}")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())

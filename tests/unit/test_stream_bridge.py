"""Unit tests for the streaming bridge Lambda.

Tests cover:
- audio_chunk action buffers audio to DynamoDB
- stop_capture with no audio falls back to demo transcript
- stop_capture stores raw transcript to S3
- stop_capture starts Step Functions execution with correct input
- stop_capture notifies client via WebSocket Management API
- stop_capture with real audio runs Transcribe batch job
- Unknown action returns 400
- Error handling sends error notification to client
- API Gateway Management endpoint derivation
- Audio chunk combining and WAV header creation
- Transcribe output parsing

Requirements: 3.1, 3.2, 3.3, 4.6, 5.3, 5.4, 5.5, 5.6, 14.1
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from backend.lambdas.stream_bridge.handler import (
    _build_apigw_management_endpoint,
    _combine_audio_chunks,
    _create_wav_header,
    _parse_transcribe_output,
    _post_to_connection,
    handle_audio_chunk,
    handle_stop_capture,
    handler,
)

TRANSCRIPT_BUCKET = "pranav-meeting-minutes-data"
STEP_FUNCTION_ARN = (
    "arn:aws:states:ap-northeast-1:681561127010:"
    "stateMachine:Pranav-meeting-minutes-workflow"
)
CONNECTIONS_TABLE = "Pranav-meeting-minutes-connections"
MEETINGS_TABLE = "Pranav-meeting-minutes-meetings"
AUDIO_BUFFER_TABLE = "Pranav-meeting-minutes-audio-buffer"
WS_ENDPOINT = "wss://abc123.execute-api.ap-northeast-1.amazonaws.com/v1"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("TRANSCRIPT_BUCKET", TRANSCRIPT_BUCKET)
    monkeypatch.setenv("STEP_FUNCTION_ARN", STEP_FUNCTION_ARN)
    monkeypatch.setenv("CONNECTIONS_TABLE", CONNECTIONS_TABLE)
    monkeypatch.setenv("WS_API_ENDPOINT", WS_ENDPOINT)
    monkeypatch.setenv("MEETINGS_TABLE", MEETINGS_TABLE)
    monkeypatch.setenv("AUDIO_BUFFER_TABLE", AUDIO_BUFFER_TABLE)


# -------------------------------------------------------------------
# Helper to build stream bridge events
# -------------------------------------------------------------------


def _stream_event(
    action: str,
    connection_id: str = "conn-sb-001",
    user_id: str = "user-sb-001",
    meeting_id: str = "meeting-sb-001",
    data: str = "",
    ws_endpoint: str = WS_ENDPOINT,
) -> dict[str, Any]:
    """Build a minimal streaming bridge invocation event."""
    event: dict[str, Any] = {
        "action": action,
        "connectionId": connection_id,
        "userId": user_id,
        "meetingId": meeting_id,
        "wsEndpoint": ws_endpoint,
    }
    if data:
        event["data"] = data
    return event


# -------------------------------------------------------------------
# _build_apigw_management_endpoint tests
# -------------------------------------------------------------------


class TestBuildApigwManagementEndpoint:
    def test_converts_wss_to_https(self):
        result = _build_apigw_management_endpoint(
            "wss://abc123.execute-api.ap-northeast-1.amazonaws.com/v1"
        )
        assert result == "https://abc123.execute-api.ap-northeast-1.amazonaws.com/v1"

    def test_converts_ws_to_http(self):
        result = _build_apigw_management_endpoint(
            "ws://localhost:3001/local"
        )
        assert result == "http://localhost:3001/local"


# -------------------------------------------------------------------
# _combine_audio_chunks tests
# -------------------------------------------------------------------


class TestCombineAudioChunks:
    def test_combines_multiple_chunks(self):
        chunk1 = base64.b64encode(b"\x01\x02\x03").decode()
        chunk2 = base64.b64encode(b"\x04\x05\x06").decode()
        items = [
            {"data": {"S": chunk1}},
            {"data": {"S": chunk2}},
        ]
        result = _combine_audio_chunks(items)
        assert result == b"\x01\x02\x03\x04\x05\x06"

    def test_handles_empty_items(self):
        result = _combine_audio_chunks([])
        assert result == b""

    def test_skips_invalid_base64(self):
        valid = base64.b64encode(b"\x01\x02").decode()
        items = [
            {"data": {"S": valid}},
            {"data": {"S": "!!!invalid!!!"}},
        ]
        result = _combine_audio_chunks(items)
        assert result == b"\x01\x02"


# -------------------------------------------------------------------
# _create_wav_header tests
# -------------------------------------------------------------------


class TestCreateWavHeader:
    def test_creates_valid_wav(self):
        pcm = b"\x00" * 100
        wav = _create_wav_header(pcm)
        # WAV header is 44 bytes
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"
        assert len(wav) == 44 + 100

    def test_correct_data_size_in_header(self):
        import struct
        pcm = b"\x00" * 256
        wav = _create_wav_header(pcm)
        # Bytes 40-44 contain the data chunk size
        data_size = struct.unpack_from("<I", wav, 40)[0]
        assert data_size == 256


# -------------------------------------------------------------------
# _parse_transcribe_output tests
# -------------------------------------------------------------------


class TestParseTranscribeOutput:
    def test_parses_speaker_labeled_output(self):
        transcribe_output = {
            "results": {
                "speaker_labels": {
                    "segments": [
                        {
                            "items": [
                                {"start_time": "0.0", "speaker_label": "spk_0"},
                                {"start_time": "0.5", "speaker_label": "spk_0"},
                            ]
                        },
                        {
                            "items": [
                                {"start_time": "2.0", "speaker_label": "spk_1"},
                            ]
                        },
                    ]
                },
                "items": [
                    {
                        "type": "pronunciation",
                        "start_time": "0.0",
                        "end_time": "0.4",
                        "alternatives": [{"content": "Hello"}],
                    },
                    {
                        "type": "pronunciation",
                        "start_time": "0.5",
                        "end_time": "0.9",
                        "alternatives": [{"content": "world"}],
                    },
                    {
                        "type": "punctuation",
                        "alternatives": [{"content": "."}],
                    },
                    {
                        "type": "pronunciation",
                        "start_time": "2.0",
                        "end_time": "2.5",
                        "alternatives": [{"content": "Hi"}],
                    },
                    {
                        "type": "punctuation",
                        "alternatives": [{"content": "!"}],
                    },
                ],
            }
        }

        segments = _parse_transcribe_output(transcribe_output)
        assert len(segments) == 2
        assert segments[0]["speaker"] == "spk_0"
        assert "Hello" in segments[0]["text"]
        assert "world" in segments[0]["text"]
        assert segments[1]["speaker"] == "spk_1"
        assert "Hi" in segments[1]["text"]

    def test_fallback_to_full_transcript(self):
        transcribe_output = {
            "results": {
                "transcripts": [{"transcript": "This is a test."}],
                "items": [],
            }
        }

        segments = _parse_transcribe_output(transcribe_output)
        assert len(segments) == 1
        assert segments[0]["text"] == "This is a test."

    def test_empty_output(self):
        transcribe_output = {"results": {"items": []}}
        segments = _parse_transcribe_output(transcribe_output)
        assert segments == []


# -------------------------------------------------------------------
# handle_audio_chunk tests
# -------------------------------------------------------------------


class TestHandleAudioChunk:
    def test_buffers_audio_to_dynamodb(self):
        mock_dynamodb = MagicMock()
        event = _stream_event("audio_chunk", data="base64audiodata==")

        result = handle_audio_chunk(
            event,
            dynamodb_client=mock_dynamodb,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        assert result["statusCode"] == 200
        assert result["body"] == "Audio chunk buffered"

        # Verify DynamoDB put_item was called
        mock_dynamodb.put_item.assert_called_once()
        call_kwargs = mock_dynamodb.put_item.call_args[1]
        assert call_kwargs["TableName"] == AUDIO_BUFFER_TABLE
        item = call_kwargs["Item"]
        assert item["meetingId"]["S"] == "meeting-sb-001"
        assert item["data"]["S"] == "base64audiodata=="
        assert "seqNum" in item
        assert "ttl" in item

    def test_rejects_missing_meeting_id(self):
        mock_dynamodb = MagicMock()
        event = {
            "action": "audio_chunk",
            "connectionId": "conn-1",
            "userId": "user-1",
            "meetingId": "",
            "data": "base64data",
            "wsEndpoint": WS_ENDPOINT,
        }

        result = handle_audio_chunk(
            event,
            dynamodb_client=mock_dynamodb,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        assert result["statusCode"] == 400
        mock_dynamodb.put_item.assert_not_called()

    def test_rejects_missing_data(self):
        mock_dynamodb = MagicMock()
        event = _stream_event("audio_chunk", data="")

        result = handle_audio_chunk(
            event,
            dynamodb_client=mock_dynamodb,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        assert result["statusCode"] == 400
        mock_dynamodb.put_item.assert_not_called()


# -------------------------------------------------------------------
# handle_stop_capture tests
# -------------------------------------------------------------------


class TestHandleStopCapture:
    def _make_mocks(self):
        """Create standard mocks for stop_capture tests."""
        mock_s3 = MagicMock()
        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:ap-northeast-1:123:execution:test"
        }
        mock_apigw = MagicMock()
        mock_dynamodb = MagicMock()
        # Default: no audio chunks in buffer (triggers demo fallback)
        mock_dynamodb.query.return_value = {"Items": []}
        mock_transcribe = MagicMock()
        return mock_s3, mock_sfn, mock_apigw, mock_dynamodb, mock_transcribe

    def test_uses_demo_transcript_when_no_audio(self):
        mock_s3, mock_sfn, mock_apigw, mock_dynamodb, mock_transcribe = self._make_mocks()

        event = _stream_event("stop_capture")
        result = handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            dynamodb_client=mock_dynamodb,
            transcribe_client=mock_transcribe,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
            meetings_table=MEETINGS_TABLE,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        assert result["statusCode"] == 200

        # Verify S3 put_object was called with transcript
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == TRANSCRIPT_BUCKET
        assert call_kwargs["Key"] == "users/user-sb-001/transcripts/meeting-sb-001/raw.json"

        # Verify demo transcript was used
        stored_body = call_kwargs["Body"].decode("utf-8")
        transcript = json.loads(stored_body)
        assert transcript["meetingId"] == "meeting-sb-001"
        assert transcript["language"] == "en-US"
        assert len(transcript["segments"]) == 4  # demo has 4 segments

    def test_stores_transcript_to_s3(self):
        mock_s3, mock_sfn, mock_apigw, mock_dynamodb, mock_transcribe = self._make_mocks()

        event = _stream_event("stop_capture")
        result = handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            dynamodb_client=mock_dynamodb,
            transcribe_client=mock_transcribe,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
            meetings_table=MEETINGS_TABLE,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        assert result["statusCode"] == 200
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["ContentType"] == "application/json"

    def test_starts_step_functions_execution(self):
        mock_s3, mock_sfn, mock_apigw, mock_dynamodb, mock_transcribe = self._make_mocks()

        event = _stream_event("stop_capture")
        handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            dynamodb_client=mock_dynamodb,
            transcribe_client=mock_transcribe,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
            meetings_table=MEETINGS_TABLE,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        mock_sfn.start_execution.assert_called_once()
        call_kwargs = mock_sfn.start_execution.call_args[1]
        assert call_kwargs["stateMachineArn"] == STEP_FUNCTION_ARN
        assert call_kwargs["name"].startswith("meeting-meeting-sb-001-")

        sfn_input = json.loads(call_kwargs["input"])
        assert sfn_input["meetingId"] == "meeting-sb-001"
        assert sfn_input["userId"] == "user-sb-001"
        assert sfn_input["transcriptBucket"] == TRANSCRIPT_BUCKET

    def test_notifies_client_capture_stopped(self):
        mock_s3, mock_sfn, mock_apigw, mock_dynamodb, mock_transcribe = self._make_mocks()

        event = _stream_event("stop_capture")
        handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            dynamodb_client=mock_dynamodb,
            transcribe_client=mock_transcribe,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
            meetings_table=MEETINGS_TABLE,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        # Find the capture_stopped message among all post_to_connection calls
        found_capture_stopped = False
        for c in mock_apigw.post_to_connection.call_args_list:
            data = json.loads(c[1]["Data"].decode("utf-8"))
            if data.get("type") == "capture_stopped":
                found_capture_stopped = True
                assert data["meetingId"] == "meeting-sb-001"
                assert data["status"] == "processing"
                break
        assert found_capture_stopped

    def test_sends_transcript_segments_to_client(self):
        mock_s3, mock_sfn, mock_apigw, mock_dynamodb, mock_transcribe = self._make_mocks()

        event = _stream_event("stop_capture")
        handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            dynamodb_client=mock_dynamodb,
            transcribe_client=mock_transcribe,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
            meetings_table=MEETINGS_TABLE,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        # Should have sent transcript_segment messages (4 demo segments + capture_stopped)
        assert mock_apigw.post_to_connection.call_count >= 5

        # Check first segment message
        first_call = mock_apigw.post_to_connection.call_args_list[0]
        data = json.loads(first_call[1]["Data"].decode("utf-8"))
        assert data["type"] == "transcript_segment"
        assert data["speaker"] in ["spk_0", "spk_1", "spk_2"]

    def test_creates_meeting_record_in_dynamodb(self):
        mock_s3, mock_sfn, mock_apigw, mock_dynamodb, mock_transcribe = self._make_mocks()

        event = _stream_event("stop_capture")
        handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            dynamodb_client=mock_dynamodb,
            transcribe_client=mock_transcribe,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
            meetings_table=MEETINGS_TABLE,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        mock_dynamodb.put_item.assert_called_once()
        call_kwargs = mock_dynamodb.put_item.call_args[1]
        assert call_kwargs["TableName"] == MEETINGS_TABLE
        item = call_kwargs["Item"]
        assert item["userId"]["S"] == "user-sb-001"
        assert item["meetingId"]["S"] == "meeting-sb-001"
        assert item["status"]["S"] == "processing"

    def test_returns_transcript_key_and_execution_arn(self):
        mock_s3, mock_sfn, mock_apigw, mock_dynamodb, mock_transcribe = self._make_mocks()

        event = _stream_event("stop_capture")
        result = handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            dynamodb_client=mock_dynamodb,
            transcribe_client=mock_transcribe,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
            meetings_table=MEETINGS_TABLE,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        body = json.loads(result["body"])
        assert body["meetingId"] == "meeting-sb-001"
        assert body["transcriptKey"] == "users/user-sb-001/transcripts/meeting-sb-001/raw.json"
        assert body["executionArn"] == "arn:aws:states:ap-northeast-1:123:execution:test"

    def test_with_audio_chunks_runs_transcribe(self):
        """When audio chunks exist, should upload to S3 and run Transcribe."""
        mock_s3, mock_sfn, mock_apigw, mock_dynamodb, mock_transcribe = self._make_mocks()

        # Simulate audio chunks in buffer
        chunk_data = base64.b64encode(b"\x00" * 1600).decode()
        mock_dynamodb.query.return_value = {
            "Items": [
                {
                    "meetingId": {"S": "meeting-sb-001"},
                    "seqNum": {"N": "1000000"},
                    "data": {"S": chunk_data},
                },
                {
                    "meetingId": {"S": "meeting-sb-001"},
                    "seqNum": {"N": "2000000"},
                    "data": {"S": chunk_data},
                },
            ]
        }

        # Simulate successful Transcribe job
        mock_transcribe.start_transcription_job.return_value = {}
        mock_transcribe.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobStatus": "COMPLETED",
                "Transcript": {"TranscriptFileUri": "s3://bucket/output.json"},
            }
        }

        # Simulate Transcribe output from S3
        transcribe_output = {
            "results": {
                "transcripts": [{"transcript": "Hello from Transcribe."}],
                "items": [
                    {
                        "type": "pronunciation",
                        "start_time": "0.0",
                        "end_time": "0.5",
                        "alternatives": [{"content": "Hello"}],
                    },
                    {
                        "type": "pronunciation",
                        "start_time": "0.6",
                        "end_time": "1.0",
                        "alternatives": [{"content": "from"}],
                    },
                    {
                        "type": "pronunciation",
                        "start_time": "1.1",
                        "end_time": "1.8",
                        "alternatives": [{"content": "Transcribe"}],
                    },
                    {
                        "type": "punctuation",
                        "alternatives": [{"content": "."}],
                    },
                ],
                "speaker_labels": {
                    "segments": [
                        {
                            "items": [
                                {"start_time": "0.0", "speaker_label": "spk_0"},
                                {"start_time": "0.6", "speaker_label": "spk_0"},
                                {"start_time": "1.1", "speaker_label": "spk_0"},
                            ]
                        }
                    ]
                },
            }
        }

        mock_s3_get_response = MagicMock()
        mock_s3_get_response.__getitem__ = lambda self, key: {
            "Body": MagicMock(read=lambda: json.dumps(transcribe_output).encode())
        }[key]

        # Make get_object return the transcribe output
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(transcribe_output).encode())
        }

        event = _stream_event("stop_capture")
        result = handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            dynamodb_client=mock_dynamodb,
            transcribe_client=mock_transcribe,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
            meetings_table=MEETINGS_TABLE,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        assert result["statusCode"] == 200

        # Verify audio was uploaded to S3 (first put_object call is audio)
        s3_calls = mock_s3.put_object.call_args_list
        assert len(s3_calls) == 2  # audio.wav + raw.json

        # First call: audio upload
        audio_call = s3_calls[0][1]
        assert audio_call["Key"].endswith("audio.wav")
        assert audio_call["ContentType"] == "audio/wav"

        # Second call: transcript
        transcript_call = s3_calls[1][1]
        assert transcript_call["Key"].endswith("raw.json")

        # Verify Transcribe was called
        mock_transcribe.start_transcription_job.assert_called_once()

        # Verify audio buffer cleanup
        mock_dynamodb.batch_write_item.assert_called()

    def test_transcribe_failure_falls_back_to_demo(self):
        """When Transcribe fails, should fall back to demo transcript."""
        mock_s3, mock_sfn, mock_apigw, mock_dynamodb, mock_transcribe = self._make_mocks()

        # Simulate audio chunks in buffer
        chunk_data = base64.b64encode(b"\x00" * 1600).decode()
        mock_dynamodb.query.return_value = {
            "Items": [
                {
                    "meetingId": {"S": "meeting-sb-001"},
                    "seqNum": {"N": "1000000"},
                    "data": {"S": chunk_data},
                },
            ]
        }

        # Simulate failed Transcribe job
        mock_transcribe.start_transcription_job.return_value = {}
        mock_transcribe.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobStatus": "FAILED",
                "FailureReason": "Audio too short",
            }
        }

        event = _stream_event("stop_capture")
        result = handle_stop_capture(
            event,
            s3_client=mock_s3,
            sfn_client=mock_sfn,
            apigw_client=mock_apigw,
            dynamodb_client=mock_dynamodb,
            transcribe_client=mock_transcribe,
            transcript_bucket=TRANSCRIPT_BUCKET,
            step_function_arn=STEP_FUNCTION_ARN,
            meetings_table=MEETINGS_TABLE,
            audio_buffer_table=AUDIO_BUFFER_TABLE,
        )

        assert result["statusCode"] == 200

        # Verify demo transcript was stored (4 segments)
        transcript_call = None
        for c in mock_s3.put_object.call_args_list:
            if c[1]["Key"].endswith("raw.json"):
                transcript_call = c
                break
        assert transcript_call is not None
        transcript = json.loads(transcript_call[1]["Body"].decode("utf-8"))
        assert len(transcript["segments"]) == 4  # demo segments


# -------------------------------------------------------------------
# handler (routing) tests
# -------------------------------------------------------------------


class TestHandler:
    def test_routes_audio_chunk(self):
        mock_dynamodb = MagicMock()
        event = _stream_event("audio_chunk", data="base64data==")

        with patch("backend.lambdas.stream_bridge.handler.boto3.client") as mock_boto:
            mock_boto.return_value = mock_dynamodb
            result = handler(event, None)

        assert result["statusCode"] == 200

    def test_routes_stop_capture(self):
        mock_s3 = MagicMock()
        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:ap-northeast-1:123:execution:test"
        }
        mock_apigw = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.query.return_value = {"Items": []}
        mock_transcribe = MagicMock()

        event = _stream_event("stop_capture")

        with patch("backend.lambdas.stream_bridge.handler.boto3.client") as mock_boto:
            def client_factory(service, **kwargs):
                if service == "s3":
                    return mock_s3
                if service == "stepfunctions":
                    return mock_sfn
                if service == "apigatewaymanagementapi":
                    return mock_apigw
                if service == "dynamodb":
                    return mock_dynamodb
                if service == "transcribe":
                    return mock_transcribe
                return MagicMock()

            mock_boto.side_effect = client_factory
            result = handler(event, None)

        assert result["statusCode"] == 200

    def test_unknown_action_returns_400(self):
        event = _stream_event("unknown_action")
        result = handler(event, None)
        assert result["statusCode"] == 400

    def test_error_sends_notification_to_client(self):
        """When an exception occurs, the handler should attempt to notify the client."""
        mock_apigw = MagicMock()

        event = _stream_event("stop_capture")

        with patch("backend.lambdas.stream_bridge.handler.boto3.client") as mock_boto:
            mock_dynamodb = MagicMock()
            # Make query raise to trigger error path
            mock_dynamodb.query.side_effect = Exception("DynamoDB error")

            def client_factory(service, **kwargs):
                if service == "dynamodb":
                    return mock_dynamodb
                if service == "apigatewaymanagementapi":
                    return mock_apigw
                if service == "s3":
                    return MagicMock()
                if service == "stepfunctions":
                    return MagicMock()
                if service == "transcribe":
                    return MagicMock()
                return MagicMock()

            mock_boto.side_effect = client_factory
            result = handler(event, None)

        assert result["statusCode"] == 500

        # Verify error notification was attempted
        mock_apigw.post_to_connection.assert_called_once()
        call_kwargs = mock_apigw.post_to_connection.call_args[1]
        message = json.loads(call_kwargs["Data"].decode("utf-8"))
        assert message["type"] == "error"
        assert message["code"] == "STREAM_BRIDGE_ERROR"

    def test_missing_action_returns_400(self):
        event = {"connectionId": "conn-1", "meetingId": "m-1", "wsEndpoint": WS_ENDPOINT}
        result = handler(event, None)
        assert result["statusCode"] == 400

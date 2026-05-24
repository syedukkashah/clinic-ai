from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


FIXTURE_AUDIO = Path(__file__).parent / "fixtures" / "test_audio_en.webm"


class TestVoiceChatEndpointPreprod:
    def test_voice_fixture_exists_and_is_webm(self):
        data = FIXTURE_AUDIO.read_bytes()
        assert data[:4] == bytes.fromhex("1A45DFA3")
        assert b"webm" in data[:64]
        assert b"A_OPUS" in data

    def test_voice_chat_returns_expected_fields(self, client):
        payload = {
            "transcript": "I need a doctor",
            "text_response": "I can help",
            "audio_url": "/static/audio/out_voice-test-1.mp3",
            "detected_lang": "en",
            "appointment": None,
        }
        with patch("api.routes.voice.handle_voice_request", AsyncMock(return_value=payload)) as mock_handler:
            with FIXTURE_AUDIO.open("rb") as audio:
                response = client.post(
                    "/api/voice/chat",
                    files={"audio": ("test_audio_en.webm", audio, "audio/webm")},
                    data={"session_id": "voice-test-1"},
                )

        assert response.status_code == 200
        body = response.json()
        assert {"transcript", "text_response", "audio_url", "detected_lang", "appointment"} <= set(body)
        assert body["transcript"] == "I need a doctor"
        mock_handler.assert_awaited_once()
        assert mock_handler.call_args.args[0].startswith(bytes.fromhex("1A45DFA3"))

    def test_voice_chat_audio_url_accessible(self, client):
        out_file = Path("static/audio/out_voice-test-2.mp3")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(b"ID3 test mp3")
        payload = {
            "transcript": "I need a doctor",
            "text_response": "I can help",
            "audio_url": "/static/audio/out_voice-test-2.mp3",
            "detected_lang": "en",
            "appointment": None,
        }
        with patch("api.routes.voice.handle_voice_request", AsyncMock(return_value=payload)):
            with FIXTURE_AUDIO.open("rb") as audio:
                response = client.post(
                    "/api/voice/chat",
                    files={"audio": ("test_audio_en.webm", audio, "audio/webm")},
                    data={"session_id": "voice-test-2"},
                )
        assert response.status_code == 200
        audio_response = client.get(response.json()["audio_url"])
        assert audio_response.status_code == 200
        assert audio_response.content.startswith(b"ID3")

    def test_voice_chat_missing_session_id(self, client):
        with FIXTURE_AUDIO.open("rb") as audio:
            response = client.post(
                "/api/voice/chat",
                files={"audio": ("test_audio_en.webm", audio, "audio/webm")},
            )
        assert response.status_code == 422

    def test_voice_chat_no_audio_file(self, client):
        response = client.post("/api/voice/chat", data={"session_id": "voice-test-missing-audio"})
        assert response.status_code == 422

    def test_voice_chat_cors_headers_present(self, client):
        with patch("api.routes.voice.handle_voice_request", AsyncMock(return_value={
            "transcript": "I need a doctor",
            "text_response": "I can help",
            "audio_url": "/static/audio/out_voice-cors.mp3",
            "detected_lang": "en",
            "appointment": None,
        })):
            with FIXTURE_AUDIO.open("rb") as audio:
                response = client.post(
                    "/api/voice/chat",
                    files={"audio": ("test_audio_en.webm", audio, "audio/webm")},
                    data={"session_id": "voice-cors"},
                    headers={"Origin": "http://localhost:3000"},
                )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


class TestWebRTCWebSocketPreprod:
    def test_websocket_accepts_connection(self, client):
        class FakeStream:
            async def send(self, _data):
                return None

            async def finish(self):
                return None

        with patch("api.routes.webrtc.stt_service.create_deepgram_stream", AsyncMock(return_value=FakeStream())):
            with client.websocket_connect("/ws/voice/test-ws-1") as ws:
                message = ws.receive_json()
                assert message == {"type": "status", "text": "connected"}

    def test_websocket_sends_transcript_json_and_audio_bytes(self, client):
        callback_holder = {}

        class FakeStream:
            async def send(self, _data):
                await callback_holder["callback"]("I need a doctor", "en", True)

            async def finish(self):
                return None

        async def fake_create_stream(callback):
            callback_holder["callback"] = callback
            return FakeStream()

        agent_response = MagicMock(
            message="I can help",
            appointment_data=None,
            tool_calls=[],
            suggested_slots=[],
        )

        async def fake_tts(_text, _lang, out_path):
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_bytes(b"mp3-bytes")

        with patch("api.routes.webrtc.stt_service.create_deepgram_stream", AsyncMock(side_effect=fake_create_stream)):
            with patch("api.routes.webrtc.orchestrator.handle_booking", AsyncMock(return_value=agent_response)):
                with patch("api.routes.webrtc.tts_service.synthesize", AsyncMock(side_effect=fake_tts)):
                    with client.websocket_connect("/ws/voice/test-ws-2") as ws:
                        assert ws.receive_json()["type"] == "status"
                        ws.send_bytes(b"0" * 1200)
                        partial = ws.receive_json()
                        final = ws.receive_json()
                        audio = ws.receive_bytes()

        assert partial["type"] == "partial"
        assert final["type"] == "final"
        assert final["transcript"] == "I need a doctor"
        assert final["text"] == "I can help"
        assert final["detected_lang"] == "en"
        assert audio == b"mp3-bytes"

    def test_websocket_disconnect_handled_gracefully(self, client):
        class FakeStream:
            finished = False

            async def send(self, _data):
                return None

            async def finish(self):
                self.finished = True

        stream = FakeStream()
        with patch("api.routes.webrtc.stt_service.create_deepgram_stream", AsyncMock(return_value=stream)):
            with client.websocket_connect("/ws/voice/test-ws-3") as ws:
                assert ws.receive_json()["type"] == "status"
        assert stream.finished is True

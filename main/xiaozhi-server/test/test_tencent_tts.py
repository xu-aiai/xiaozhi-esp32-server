import asyncio
import base64
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


fake_requests = types.ModuleType("requests")
fake_requests.post = None
sys.modules.setdefault("requests", fake_requests)
fake_base_module = types.ModuleType("core.providers.tts.base")


class _FakeBaseProvider:
    def __init__(self, config, delete_audio_file):
        self.conn = None
        self.delete_audio_file = delete_audio_file
        self.audio_file_type = "wav"
        self.output_file = config.get("output_dir", "tmp/")

    def _apply_percentage_params(self, config):
        return None


fake_base_module.TTSProviderBase = _FakeBaseProvider
sys.modules["core.providers.tts.base"] = fake_base_module

from core.providers.tts.tencent import TTSProvider


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.content = str(payload).encode("utf-8")

    def json(self):
        return self._payload


class TencentTTSTest(unittest.TestCase):
    def setUp(self):
        self.provider = TTSProvider(
            {
                "appid": "test-appid",
                "secret_id": "test-secret-id",
                "secret_key": "test-secret-key",
                "voice": "101001",
                "region": "ap-guangzhou",
                "output_dir": "tmp/",
            },
            delete_audio_file=True,
        )
        self.provider.conn = SimpleNamespace(sample_rate=24000)

    def test_fallback_to_16000_when_voice_does_not_support_24000(self):
        audio_bytes = b"fake-wav-audio"
        responses = [
            FakeResponse(
                200,
                {
                    "Response": {
                        "Error": {
                            "Code": "InvalidParameterValue.SampleRate",
                            "Message": "The current VoiceType does not support the SampleRate",
                        }
                    }
                },
            ),
            FakeResponse(
                200,
                {"Response": {"Audio": base64.b64encode(audio_bytes).decode("utf-8")}},
            ),
        ]
        request_payloads = []

        def fake_post(url, body, headers):
            request_payloads.append(body)
            return responses.pop(0)

        with patch.object(self.provider, "_get_auth_headers", return_value={}), patch(
            "core.providers.tts.tencent.requests.post", side_effect=fake_post
        ):
            result = asyncio.run(self.provider.text_to_speak("Hey there~", None))

        self.assertEqual(result, audio_bytes)
        self.assertIn('"SampleRate": 24000', request_payloads[0])
        self.assertIn('"SampleRate": 16000', request_payloads[1])


if __name__ == "__main__":
    unittest.main()

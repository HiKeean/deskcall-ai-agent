import base64
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from deskcall.speech import (GoogleCloudSTT, GoogleCloudTTS, GroqWhisperSTT, SpeechError, pcm_to_wav,
                             stt_from_env, tts_from_env, wav_to_pcm)

PCM = b"\x01\x00\x02\x00" * 100


class _Handler(BaseHTTPRequestHandler):
    seen = []
    status = 200
    reply = {}

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        _Handler.seen.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                              "body": body})
        out = json.dumps(_Handler.reply).encode()
        self.send_response(_Handler.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.server.server_port
        _Handler.status, _Handler.seen = 200, []

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()


class WavTest(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(wav_to_pcm(pcm_to_wav(PCM, 16000)), (PCM, 16000))


class GoogleCloudTTSTest(ServerTest):
    def test_synthesizes_strips_wav_header_and_caches(self):
        _Handler.reply = {"audioContent": base64.b64encode(pcm_to_wav(PCM, 24000)).decode()}
        tts = GoogleCloudTTS("t-key", voice="id-ID-Wavenet-B", base_url=self.base, timeout=2)

        self.assertEqual(tts.synthesize("Selamat siang"), PCM)
        self.assertEqual(tts.synthesize("Selamat siang"), PCM)

        self.assertEqual(len(_Handler.seen), 1)  # kalimat yang sama tidak disintesis ulang
        seen = _Handler.seen[0]
        body = json.loads(seen["body"])
        self.assertEqual(seen["path"], "/v1/text:synthesize")
        self.assertEqual(seen["headers"]["x-goog-api-key"], "t-key")
        self.assertEqual(body["voice"], {"languageCode": "id-ID", "name": "id-ID-Wavenet-B"})
        self.assertEqual(body["audioConfig"]["audioEncoding"], "LINEAR16")
        self.assertEqual(body["audioConfig"]["sampleRateHertz"], 24000)

    def test_errors_raise_speech_error(self):
        tts = GoogleCloudTTS("k", base_url=self.base, timeout=2)
        _Handler.reply = {}
        with self.assertRaises(SpeechError):
            tts.synthesize("a")
        _Handler.status, _Handler.reply = 403, {"error": {"message": "API not enabled"}}
        with self.assertRaisesRegex(SpeechError, "403"):
            tts.synthesize("b")
        _Handler.status, _Handler.reply = 200, {"audioContent": base64.b64encode(pcm_to_wav(PCM, 8000)).decode()}
        with self.assertRaisesRegex(SpeechError, "8000"):
            tts.synthesize("c")


class GroqWhisperSTTTest(ServerTest):
    def test_sends_wav_multipart_in_indonesian(self):
        _Handler.reply = {"text": " iya betul \n"}
        stt = GroqWhisperSTT("g-key", base_url=self.base + "/openai/v1", timeout=2)

        self.assertEqual(stt.transcribe(PCM, 16000), "iya betul")

        seen = _Handler.seen[0]
        self.assertEqual(seen["path"], "/openai/v1/audio/transcriptions")
        self.assertEqual(seen["headers"]["authorization"], "Bearer g-key")
        self.assertIn("multipart/form-data; boundary=", seen["headers"]["content-type"])
        self.assertIn(b'name="language"\r\n\r\nid\r\n', seen["body"])
        self.assertIn(b'name="model"\r\n\r\nwhisper-large-v3-turbo\r\n', seen["body"])
        self.assertIn(pcm_to_wav(PCM, 16000), seen["body"])

    def test_drops_segments_whisper_marks_as_non_speech(self):
        _Handler.reply = {"text": "Terima kasih. Betul.", "segments": [
            {"text": " Terima kasih.", "no_speech_prob": 0.92}, {"text": " Betul.", "no_speech_prob": 0.05}]}
        stt = GroqWhisperSTT("k", base_url=self.base, timeout=2)

        self.assertEqual(stt.transcribe(PCM, 16000), "Betul.")
        self.assertIn(b'name="response_format"\r\n\r\nverbose_json\r\n', _Handler.seen[0]["body"])

        _Handler.reply = {"text": "Terima kasih.", "segments": [{"text": "Terima kasih.", "no_speech_prob": 0.8}]}
        self.assertEqual(stt.transcribe(PCM, 16000), "")

    def test_missing_text_raises(self):
        _Handler.reply = {"error": "x"}
        with self.assertRaises(SpeechError):
            GroqWhisperSTT("k", base_url=self.base, timeout=2).transcribe(PCM, 16000)


class GoogleCloudSTTTest(ServerTest):
    def test_joins_results_and_handles_no_speech(self):
        _Handler.reply = {"results": [{"alternatives": [{"transcript": "iya "}]},
                                      {"alternatives": [{"transcript": "betul"}]}]}
        stt = GoogleCloudSTT("s-key", base_url=self.base, timeout=2)

        self.assertEqual(stt.transcribe(PCM, 16000), "iya betul")
        body = json.loads(_Handler.seen[0]["body"])
        self.assertEqual(body["config"]["languageCode"], "id-ID")
        self.assertEqual(body["config"]["sampleRateHertz"], 16000)
        self.assertEqual(base64.b64decode(body["audio"]["content"]), PCM)

        _Handler.reply = {}
        self.assertEqual(stt.transcribe(PCM, 16000), "")


class FromEnvTest(unittest.TestCase):
    KEYS = ("GOOGLE_CLOUD_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "STT_PROVIDER", "GOOGLE_TTS_VOICE")

    def env(self, **values):
        clean = {k: v for k, v in os.environ.items() if k not in self.KEYS}
        clean.update(values)
        return mock.patch.dict(os.environ, clean, clear=True)

    def test_selection(self):
        with self.env():
            self.assertIsNone(tts_from_env())
            self.assertIsNone(stt_from_env())
        with self.env(GEMINI_API_KEY="g"):
            self.assertIsInstance(tts_from_env(), GoogleCloudTTS)  # key AI Studio dipakai kalau tidak ada key Cloud
            self.assertIsInstance(stt_from_env(), GoogleCloudSTT)
        with self.env(GOOGLE_CLOUD_API_KEY="c", GROQ_API_KEY="q"):
            self.assertIsInstance(stt_from_env(), GroqWhisperSTT)
        with self.env(GOOGLE_CLOUD_API_KEY="c", GROQ_API_KEY="q", STT_PROVIDER="google"):
            self.assertIsInstance(stt_from_env(), GoogleCloudSTT)
        with self.env(STT_PROVIDER="azure"):
            with self.assertRaises(ValueError):
                stt_from_env()


if __name__ == "__main__":
    unittest.main()

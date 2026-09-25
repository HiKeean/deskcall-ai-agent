"""Adapter TTS/STT lewat REST (stdlib saja, bisa di-mock). Audio = PCM 16-bit mono little-endian.

TTS: Google Cloud Text-to-Speech (tier gratis: 4 juta karakter/bulan suara Standard, 1 juta WaveNet).
STT: Groq Whisper (gratis, sudah teruji untuk Bahasa Indonesia) atau Google Cloud Speech-to-Text (60 menit/bulan).

Env:
  GOOGLE_CLOUD_API_KEY   key project Google Cloud dengan "Cloud Text-to-Speech API" (dan opsional
                         "Cloud Speech-to-Text API") aktif; kalau kosong dipakai GEMINI_API_KEY
  GOOGLE_TTS_VOICE       default id-ID-Wavenet-A (lainnya: id-ID-Wavenet-B/C/D, id-ID-Standard-A..D)
  GOOGLE_TTS_SPEAKING_RATE  default 1.0
  STT_PROVIDER           groq | google (default: groq kalau GROQ_API_KEY ada, selain itu google)
  GROQ_API_KEY, GROQ_STT_MODEL (default whisper-large-v3-turbo)
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import urllib.error
import urllib.request
import uuid
import wave
from typing import Dict, Optional, Protocol, Tuple

log = logging.getLogger(__name__)

USER_AGENT = "deskcall-agent/0.1"  # User-Agent bawaan urllib diblok Cloudflare (Groq)


class SpeechError(Exception):
    pass


class TextToSpeech(Protocol):
    sample_rate: int

    def synthesize(self, text: str) -> bytes:
        """PCM16 mono pada `sample_rate`. Raise SpeechError kalau gagal."""
        ...


class SpeechToText(Protocol):
    def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        """Teks dari satu potongan ucapan (boleh kosong). Raise SpeechError kalau gagal."""
        ...


def pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_to_pcm(data: bytes) -> Tuple[bytes, int]:
    with wave.open(io.BytesIO(data), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise SpeechError("unexpected WAV format")
        return w.readframes(w.getnframes()), w.getframerate()


def _post(request: urllib.request.Request, timeout: float) -> Dict:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # isi body error aman dicatat (pesan provider), tidak memuat audio/teks nasabah
        detail = exc.read()[:300].decode("utf-8", "replace")
        raise SpeechError("HTTP %d: %s" % (exc.code, detail)) from exc
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise SpeechError("request failed: %s" % type(exc).__name__) from exc


class GoogleCloudTTS:
    """Cloud Text-to-Speech v1 `text:synthesize` dengan API key. Hasil di-cache per kalimat
    (kalimat script banyak berulang: pengulangan pertanyaan, penutup)."""

    def __init__(self, api_key: str, voice: str = "id-ID-Wavenet-A", sample_rate: int = 24000,
                 speaking_rate: float = 1.0, timeout: float = 10.0,
                 base_url: str = "https://texttospeech.googleapis.com") -> None:
        self._api_key = api_key
        self._voice = voice
        self.sample_rate = sample_rate
        self._speaking_rate = speaking_rate
        self._timeout = timeout
        self._url = base_url.rstrip("/") + "/v1/text:synthesize"
        self._cache: Dict[str, bytes] = {}

    def synthesize(self, text: str) -> bytes:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        body = json.dumps({
            "input": {"text": text},
            "voice": {"languageCode": "-".join(self._voice.split("-")[:2]), "name": self._voice},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": self.sample_rate,
                            "speakingRate": self._speaking_rate},
        }).encode("utf-8")
        request = urllib.request.Request(self._url, data=body, method="POST", headers={
            "x-goog-api-key": self._api_key, "content-type": "application/json", "user-agent": USER_AGENT})
        payload = _post(request, self._timeout)
        try:
            audio = base64.b64decode(payload["audioContent"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SpeechError("TTS returned no audio") from exc
        # LINEAR16 dari Google sudah berupa WAV (ada header); buang header supaya jadi PCM mentah
        pcm, rate = wav_to_pcm(audio) if audio[:4] == b"RIFF" else (audio, self.sample_rate)
        if rate != self.sample_rate:
            raise SpeechError("TTS returned %d Hz, expected %d" % (rate, self.sample_rate))
        self._cache[text] = pcm
        return pcm


class GroqWhisperSTT:
    """OpenAI-compatible `audio/transcriptions` (Groq Whisper), bahasa dipaksa Indonesia."""

    def __init__(self, api_key: str, model: str = "whisper-large-v3-turbo", language: str = "id",
                 timeout: float = 10.0, base_url: str = "https://api.groq.com/openai/v1",
                 max_no_speech_prob: float = 0.6) -> None:
        self._api_key = api_key
        # Whisper suka "berhalusinasi" (mis. "Terima kasih.") pada audio tanpa ucapan: segmen yang
        # menurut model sendiri kemungkinan besar bukan ucapan dibuang
        self._max_no_speech_prob = max_no_speech_prob
        self._model = model
        self._language = language
        self._timeout = timeout
        self._url = base_url.rstrip("/") + "/audio/transcriptions"

    def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        boundary = uuid.uuid4().hex
        fields = {"model": self._model, "language": self._language, "response_format": "verbose_json",
                  "temperature": "0"}
        parts = []
        for name, value in fields.items():
            parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                          % (boundary, name, value)).encode("utf-8"))
        parts.append(('--%s\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\n'
                      'Content-Type: audio/wav\r\n\r\n' % boundary).encode("utf-8"))
        parts.append(pcm_to_wav(pcm, sample_rate))
        parts.append(("\r\n--%s--\r\n" % boundary).encode("utf-8"))
        request = urllib.request.Request(self._url, data=b"".join(parts), method="POST", headers={
            "authorization": "Bearer " + self._api_key, "user-agent": USER_AGENT,
            "content-type": "multipart/form-data; boundary=" + boundary})
        payload = _post(request, self._timeout)
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str):
            raise SpeechError("STT returned no text")
        segments = payload.get("segments")
        if isinstance(segments, list) and segments:
            kept = [str(seg.get("text") or "").strip() for seg in segments if isinstance(seg, dict)
                    and float(seg.get("no_speech_prob") or 0.0) < self._max_no_speech_prob]
            if len(kept) < len(segments):
                log.info("STT: %d/%d segmen dibuang (kemungkinan bukan ucapan)", len(segments) - len(kept), len(segments))
            return " ".join(t for t in kept if t)
        return text.strip()


class GoogleCloudSTT:
    """Cloud Speech-to-Text v1 `speech:recognize` (sinkron, cocok untuk ucapan pendek < 1 menit)."""

    def __init__(self, api_key: str, language: str = "id-ID", timeout: float = 10.0,
                 base_url: str = "https://speech.googleapis.com") -> None:
        self._api_key = api_key
        self._language = language
        self._timeout = timeout
        self._url = base_url.rstrip("/") + "/v1/speech:recognize"

    def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        body = json.dumps({
            "config": {"encoding": "LINEAR16", "sampleRateHertz": sample_rate, "languageCode": self._language,
                       "enableAutomaticPunctuation": True},
            "audio": {"content": base64.b64encode(pcm).decode("ascii")},
        }).encode("utf-8")
        request = urllib.request.Request(self._url, data=body, method="POST", headers={
            "x-goog-api-key": self._api_key, "content-type": "application/json", "user-agent": USER_AGENT})
        payload = _post(request, self._timeout)
        texts = []
        for result in payload.get("results") or []:
            alternatives = result.get("alternatives") or []
            if alternatives and isinstance(alternatives[0].get("transcript"), str):
                texts.append(alternatives[0]["transcript"].strip())
        return " ".join(t for t in texts if t)


def _google_key() -> Optional[str]:
    return os.environ.get("GOOGLE_CLOUD_API_KEY") or os.environ.get("GEMINI_API_KEY") or None


def tts_from_env() -> Optional[TextToSpeech]:
    key = _google_key()
    if not key:
        return None
    return GoogleCloudTTS(key, voice=os.environ.get("GOOGLE_TTS_VOICE") or "id-ID-Wavenet-A",
                          speaking_rate=float(os.environ.get("GOOGLE_TTS_SPEAKING_RATE") or "1.0"))


def stt_from_env() -> Optional[SpeechToText]:
    provider = (os.environ.get("STT_PROVIDER") or ("groq" if os.environ.get("GROQ_API_KEY") else "google")).lower()
    if provider == "groq":
        key = os.environ.get("GROQ_API_KEY")
        return GroqWhisperSTT(key, model=os.environ.get("GROQ_STT_MODEL") or "whisper-large-v3-turbo") if key else None
    if provider == "google":
        key = _google_key()
        return GoogleCloudSTT(key) if key else None
    raise ValueError("STT_PROVIDER harus groq atau google, bukan %r" % provider)

"""Worker LiveKit: menerima dispatch dari deskcall-api, menjalankan CallRunner di dalam room.

Mode I/O (`DESKCALL_IO_MODE`):
- `text` (default): LiveKit chat stream (topic `lk.chat`), untuk uji jalur tanpa STT/TTS.
- `voice`: audio nasabah -> VAD (silero lokal) -> STT; kalimat script -> TTS -> track audio agent.
  Provider lihat `speech.py` (Google Cloud TTS; STT Groq Whisper atau Google). Belum ada barge-in.

    ~/.venvs/deskcall/bin/python -m deskcall.worker start     (butuh Python >= 3.10 + livekit-agents)

Env: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, DESKCALL_API_URL (default http://localhost:8090),
DESKCALL_API_KEYS (key pertama dipakai) atau DESKCALL_API_KEY; opsional classifier LLM: ANTHROPIC_API_KEY
GEMINI_API_KEY (+ GEMINI_MODEL), atau LLM_BASE_URL + LLM_MODEL (+ LLM_API_KEY) untuk API kompatibel OpenAI.
Nilai yang belum ada di environment dibaca dari .env di root project.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Set

from .api_client import DeskcallApi
from .classifier import IntentClassifier, RuleBasedClassifier
from .engine import DialogueEngine
from .models import call_context_from_metadata
from .runner import CallIO, CallRunner, CustomerLeft
from .speech import SpeechError, SpeechToText, TextToSpeech, stt_from_env, tts_from_env

log = logging.getLogger("deskcall.worker")

AGENT_NAME = "deskcall-agent"
CUSTOMER_IDENTITY = "customer"
CHAT_TOPIC = "lk.chat"
_LEFT = object()


def load_dotenv(path: Path) -> None:
    """Isi os.environ dari file .env untuk key yang belum diset (tidak menimpa)."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if value != "":
            os.environ.setdefault(key.strip(), value)


def build_classifier() -> IntentClassifier:
    from .llm_classifier import LlmIntentClassifier, client_from_env
    client = client_from_env()
    if client is not None:
        log.info("classifier: LLM %s (dengan fallback rule-based)", type(client).__name__)
        return LlmIntentClassifier(client)
    log.info("classifier: rule-based (tidak ada ANTHROPIC_API_KEY / GEMINI_API_KEY / LLM_BASE_URL)")
    return RuleBasedClassifier()


def build_api() -> DeskcallApi:
    key = os.environ.get("DESKCALL_API_KEY") or os.environ.get("DESKCALL_API_KEYS", "").split(",")[0].strip()
    if not key:
        raise RuntimeError("DESKCALL_API_KEY / DESKCALL_API_KEYS belum diset")
    return DeskcallApi(os.environ.get("DESKCALL_API_URL", "http://localhost:8090"), key)


class LiveKitTextIO:
    """CallIO lewat LiveKit chat stream. Hanya menerima teks dari peserta `customer`."""

    def __init__(self, room, customer_identity: str = CUSTOMER_IDENTITY) -> None:
        self._room = room
        self._customer = customer_identity
        self._inbox: "asyncio.Queue[object]" = asyncio.Queue()
        room.register_text_stream_handler(CHAT_TOPIC, self._on_stream)
        room.on("participant_disconnected", self._on_disconnected)

    def _on_stream(self, reader, participant_identity: str) -> None:
        if participant_identity != self._customer:
            return
        # antrekan future sesuai urutan stream dimulai, supaya urutan ucapan terjaga walau selesai dibaca tidak berurutan
        self._inbox.put_nowait(asyncio.ensure_future(self._read(reader)))

    async def _read(self, reader) -> Optional[str]:
        try:
            text = await reader.read_all()
        except Exception:  # noqa: BLE001
            log.exception("failed reading customer text stream")
            return None
        log.info("customer text received (%d chars)", len(text))  # isi tidak di-log (bisa memuat data pribadi)
        return text

    def _on_disconnected(self, participant) -> None:
        if participant.identity == self._customer:
            self._inbox.put_nowait(_LEFT)

    async def say(self, lines: List[str]) -> None:
        for line in lines:
            await self._room.local_participant.send_text(
                line, topic=CHAT_TOPIC, destination_identities=[self._customer])

    async def listen(self, timeout: float) -> Optional[str]:
        try:
            item = await asyncio.wait_for(self._inbox.get(), timeout)
        except asyncio.TimeoutError:
            return None
        if item is _LEFT:
            raise CustomerLeft()
        return await item  # type: ignore[misc]


STT_SAMPLE_RATE = 16000
FRAME_MS = 20
AI_ECHO_TAIL_SECONDS = 0.3


class LiveKitVoiceIO:
    """CallIO suara. Setiap potongan ucapan nasabah (dibatasi VAD) ditranskripsi di thread terpisah; hasilnya
    diantre sebagai future sesuai urutan ucapan. Half-duplex sederhana: AI menyelesaikan kalimatnya (belum barge-in),
    ucapan nasabah selama AI bicara tetap diantre sebagai jawaban."""

    def __init__(self, room, tts: TextToSpeech, stt: SpeechToText, vad,
                 customer_identity: str = CUSTOMER_IDENTITY) -> None:
        from livekit import rtc
        self._rtc = rtc
        self._room = room
        self._tts = tts
        self._stt = stt
        self._vad = vad
        self._customer = customer_identity
        self._inbox: "asyncio.Queue[object]" = asyncio.Queue()
        self._source = rtc.AudioSource(tts.sample_rate, 1)
        self._user_speaking = False
        self._ai_audio_until = 0.0  # loop.time() sampai kapan audio AI dianggap masih terdengar
        self._consumer: Optional[asyncio.Task] = None
        self._tasks: Set[asyncio.Task] = set()
        room.on("track_subscribed", self._on_track_subscribed)
        room.on("participant_disconnected", self._on_disconnected)
        for participant in room.remote_participants.values():  # track yang sudah ada sebelum handler terpasang
            for publication in participant.track_publications.values():
                if publication.track is not None:
                    self._on_track_subscribed(publication.track, publication, participant)

    async def start(self) -> None:
        rtc = self._rtc
        track = rtc.LocalAudioTrack.create_audio_track("deskcall-agent-voice", self._source)
        await self._room.local_participant.publish_track(
            track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE))

    def _on_track_subscribed(self, track, publication, participant) -> None:
        if (participant.identity == self._customer and track.kind == self._rtc.TrackKind.KIND_AUDIO
                and self._consumer is None):
            self._consumer = asyncio.ensure_future(self._consume(track))

    def _on_disconnected(self, participant) -> None:
        if participant.identity == self._customer:
            self._inbox.put_nowait(_LEFT)

    async def _consume(self, track) -> None:
        stream = self._rtc.AudioStream(track, sample_rate=STT_SAMPLE_RATE, num_channels=1)
        vad_stream = self._vad.stream()

        async def pump() -> None:
            async for event in stream:
                vad_stream.push_frame(event.frame)

        pump_task = asyncio.ensure_future(pump())
        try:
            from livekit.agents.vad import VADEventType
            started_over_ai = False
            async for event in vad_stream:
                if event.type == VADEventType.START_OF_SPEECH:
                    self._user_speaking = True
                    started_over_ai = self._ai_audio_active()
                elif event.type == VADEventType.END_OF_SPEECH:
                    self._user_speaking = False
                    if started_over_ai:
                        # dimulai saat AI bicara: biasanya pantulan suara AI sendiri (STT lalu "berhalusinasi",
                        # mis. "Terima kasih.") atau menyela; tanpa barge-in, jawaban dihitung setelah AI selesai
                        log.info("customer speech dropped: started while AI was speaking (%.1fs)", event.speech_duration)
                        continue
                    self._inbox.put_nowait(asyncio.ensure_future(self._transcribe(event.frames)))
        except Exception:  # noqa: BLE001
            log.exception("customer audio pipeline stopped")
        finally:
            pump_task.cancel()
            await vad_stream.aclose()
            await stream.aclose()

    async def _transcribe(self, frames) -> str:
        if not frames:
            return ""
        frame = self._rtc.combine_audio_frames(frames)
        try:
            text = await asyncio.to_thread(self._stt.transcribe, bytes(frame.data), frame.sample_rate)
        except SpeechError as exc:
            log.warning("STT failed, segment dropped: %s", exc)
            return ""
        log.info("customer speech transcribed (%.1fs audio, %d chars)", frame.duration, len(text))  # isi tidak di-log
        return text

    async def say(self, lines: List[str]) -> None:
        # sintesis semua kalimat paralel, putar berurutan: kalimat berikutnya siap saat kalimat sebelumnya diputar
        jobs = [asyncio.ensure_future(asyncio.to_thread(self._tts.synthesize, line)) for line in lines]
        loop = asyncio.get_running_loop()
        self._ai_audio_until = float("inf")
        try:
            for job in jobs:
                await self._play(await job)
            await self._source.wait_for_playout()
        finally:
            # sisa gema di HP nasabah bisa terdengar sesaat setelah playout selesai
            self._ai_audio_until = loop.time() + AI_ECHO_TAIL_SECONDS
            for job in jobs:
                job.cancel()

    def _ai_audio_active(self) -> bool:
        return asyncio.get_running_loop().time() < self._ai_audio_until

    async def _play(self, pcm: bytes) -> None:
        rate = self._tts.sample_rate
        chunk = rate * FRAME_MS // 1000 * 2
        for i in range(0, len(pcm), chunk):
            data = pcm[i:i + chunk]
            if len(data) < chunk:
                data = data + b"\x00" * (chunk - len(data))
            await self._source.capture_frame(self._rtc.AudioFrame(
                data=data, sample_rate=rate, num_channels=1, samples_per_channel=len(data) // 2))

    async def listen(self, timeout: float) -> Optional[str]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            try:
                item = await asyncio.wait_for(self._inbox.get(), max(deadline - loop.time(), 0.05))
            except asyncio.TimeoutError:
                if self._user_speaking:  # nasabah masih bicara: tunggu sampai selesai, jangan dianggap diam
                    deadline = loop.time() + 0.5
                    continue
                return None
            if item is _LEFT:
                raise CustomerLeft()
            text = await item  # type: ignore[misc]
            if text.strip():
                return text
            # potongan kosong (batuk, noise, STT gagal): tetap menunggu dalam batas waktu yang sama

    async def aclose(self) -> None:
        if self._consumer is not None:
            self._consumer.cancel()


def io_mode() -> str:
    mode = (os.environ.get("DESKCALL_IO_MODE") or "text").lower()
    if mode not in ("text", "voice"):
        raise RuntimeError("DESKCALL_IO_MODE harus text atau voice, bukan %r" % mode)
    return mode


def build_voice_speech():
    tts, stt = tts_from_env(), stt_from_env()
    if tts is None or stt is None:
        raise RuntimeError("mode voice butuh TTS (GOOGLE_CLOUD_API_KEY/GEMINI_API_KEY) dan STT "
                           "(GROQ_API_KEY, atau STT_PROVIDER=google)")
    log.info("voice: TTS %s, STT %s", type(tts).__name__, type(stt).__name__)
    return tts, stt


def prewarm(proc) -> None:
    if io_mode() == "voice":
        from livekit.agents.inference import VAD
        # jeda 0.6 dtk dianggap akhir ucapan (default 0.25 memotong kalimat orang yang berpikir sejenak)
        proc.userdata["vad"] = VAD(min_silence_duration=float(os.environ.get("DESKCALL_VAD_MIN_SILENCE", "0.6")))


async def entrypoint(ctx) -> None:
    api = build_api()
    try:
        call_ctx = call_context_from_metadata(ctx.job.metadata)
    except (ValueError, KeyError, TypeError):
        log.exception("invalid dispatch metadata; job dropped")
        ctx.shutdown("invalid metadata")
        return
    call_id = call_ctx.call_id
    log.info("call %s: dispatched", call_id)

    await ctx.connect()
    io: CallIO
    if io_mode() == "voice":
        tts, stt = build_voice_speech()
        vad = ctx.proc.userdata.get("vad")
        if vad is None:
            from livekit.agents.inference import VAD
            vad = VAD(min_silence_duration=0.6)
        io = LiveKitVoiceIO(ctx.room, tts, stt, vad)
        await io.start()
    else:
        io = LiveKitTextIO(ctx.room)  # daftar handler sebelum nasabah bisa mengirim apa pun
    await api.apost_event(call_id, "AGENT_JOINED")
    try:
        await asyncio.wait_for(ctx.wait_for_participant(identity=CUSTOMER_IDENTITY),
                               float(os.environ.get("DESKCALL_WAIT_FOR_CUSTOMER_SECONDS", "120")))
    except asyncio.TimeoutError:
        log.info("call %s: customer never joined; sweeper in API will tag NSTD", call_id)
        ctx.shutdown("customer did not join")
        return
    await api.apost_event(call_id, "CUSTOMER_JOINED")

    runner = CallRunner(DialogueEngine(call_ctx), build_classifier(), io, api, call_id,
                        silence_timeout=float(os.environ.get("DESKCALL_SILENCE_TIMEOUT_SECONDS", "8")))
    result = await runner.run()
    if isinstance(io, LiveKitVoiceIO):
        await io.aclose()
    log.info("call %s: finished tag=%s", call_id, result.tag.value if result.tag else None)
    ctx.shutdown("call finished")


def main() -> None:
    from livekit.agents import WorkerOptions, cli
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    logging.basicConfig(level=logging.INFO)
    opts = {}
    if os.environ.get("DESKCALL_NUM_IDLE_PROCESSES"):
        # default livekit (prod) = jumlah CPU; tiap proses idle ~130 MB
        opts["num_idle_processes"] = int(os.environ["DESKCALL_NUM_IDLE_PROCESSES"])
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm, agent_name=AGENT_NAME, **opts))


if __name__ == "__main__":
    main()

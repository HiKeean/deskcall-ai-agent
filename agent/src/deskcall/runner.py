"""CallRunner: loop percakapan (dengar -> klasifikasi -> engine -> ucapkan) yang tidak tahu soal LiveKit.

I/O (`CallIO`) diganti sesuai mode: teks lewat LiveKit chat (verifikasi/test) atau suara (STT/TTS).
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Protocol

from .classifier import IntentClassifier
from .engine import DialogueEngine
from .models import CallResult, Intent, Tag, Understanding

log = logging.getLogger(__name__)


class CustomerLeft(Exception):
    """Nasabah keluar dari room."""


class CallIO(Protocol):
    async def say(self, lines: List[str]) -> None: ...

    async def listen(self, timeout: float) -> Optional[str]:
        """Ucapan/teks nasabah berikutnya; None kalau diam sampai timeout. Raise CustomerLeft kalau keluar."""
        ...


class ResultSink(Protocol):
    async def apost_result(self, call_id: str, result: CallResult) -> None: ...


class CallRunner:
    def __init__(self, engine: DialogueEngine, classifier: IntentClassifier, io: CallIO, sink: ResultSink,
                 call_id: str, silence_timeout: float = 8.0, max_turns: int = 60) -> None:
        self._engine = engine
        self._classifier = classifier
        self._io = io
        self._sink = sink
        self._call_id = call_id
        self._silence_timeout = silence_timeout
        self._max_turns = max_turns

    async def run(self) -> CallResult:
        """Jalankan sampai selesai lalu kirim hasil. Selalu mengirim hasil (walau nasabah keluar / error)."""
        left = False
        try:
            await self._io.say(self._engine.start())
            for _ in range(self._max_turns):
                if self._engine.finished:
                    break
                text = await self._io.listen(self._silence_timeout)
                state = self._engine.state.value
                if text is None or not text.strip():
                    understanding = Understanding(Intent.SILENCE, {}, "")
                else:
                    # classifier LLM = HTTP sinkron; di thread supaya loop audio tidak tersendat
                    understanding = await asyncio.to_thread(
                        self._classifier.classify, text, self._engine.allowed_intents(), state)
                    understanding.text = text
                await self._io.say(self._engine.handle(understanding))
        except CustomerLeft:
            left = True
        except Exception:  # noqa: BLE001 - hasil harus tetap terkirim apa pun yang terjadi
            log.exception("call %s aborted by error", self._call_id)
        result = self._engine.result()
        if result.tag is None:
            result.tag = Tag.OTHERS
            result.note = "nasabah keluar sebelum percakapan selesai" if left else "percakapan berhenti tidak wajar"
        await self._sink.apost_result(self._call_id, result)
        return result

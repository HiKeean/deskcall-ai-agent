"""Dialogue engine: state machine deterministik untuk script DAS (docs/SCRIPT.md).

Tidak ada I/O suara maupun LLM di sini. Input = Understanding (hasil klasifikasi ucapan nasabah ke
enum tertutup), output = daftar kalimat AI dari template script.
"""
from __future__ import annotations

import math
import re
from datetime import date, timedelta, datetime
from enum import Enum
from typing import Callable, Dict, FrozenSet, List, Optional

from . import script as S
from .models import CallContext, CallResult, Intent, Tag, Turn, Understanding

MAX_STRIKES = 2  # tidak jelas / diam berturut-turut di satu state
MAX_OFF_SCRIPT = 3  # pertanyaan di luar script dalam satu panggilan
MAX_PUSHES = 2  # putaran negosiasi (Skenario B dihitung sebagai push 1)
MAX_VERIFY_ATTEMPTS = 2


class State(str, Enum):
    AWAIT_IDENTITY = "AWAIT_IDENTITY"
    AWAIT_VERIFICATION = "AWAIT_VERIFICATION"
    AWAIT_EMPATHY = "AWAIT_EMPATHY"
    AWAIT_PROMISE = "AWAIT_PROMISE"
    AWAIT_ATAS_NAMA_ACK = "AWAIT_ATAS_NAMA_ACK"
    AWAIT_ACCIDENT_REPORT = "AWAIT_ACCIDENT_REPORT"
    ENDED = "ENDED"


_ANYTIME = frozenset({Intent.OFF_SCRIPT, Intent.UNCLEAR, Intent.SILENCE, Intent.ASKS_IF_AI})
_SPECIAL = frozenset({Intent.CLAIMS_PAID, Intent.ATAS_NAMA, Intent.UNIT_LOST, Intent.UNIT_ACCIDENT})
_ALLOWED: Dict[State, FrozenSet[Intent]] = {
    State.AWAIT_IDENTITY: frozenset({Intent.YES, Intent.NO_THIRD_PARTY, Intent.WRONG_NUMBER,
                                     Intent.BUSY_CALLBACK, Intent.DEBTOR_DECEASED}),
    State.AWAIT_VERIFICATION: frozenset({Intent.PROVIDES_VERIFICATION, Intent.DECLINES_VERIFICATION,
                                         Intent.NO_THIRD_PARTY, Intent.DEBTOR_DECEASED}),
    State.AWAIT_EMPATHY: frozenset({Intent.FORGOT_OR_WILL_PAY, Intent.ANGRY_OR_HARDSHIP,
                                    Intent.PROMISE_PAY, Intent.REFUSE_PAY}) | _SPECIAL,
    State.AWAIT_PROMISE: frozenset({Intent.PROMISE_PAY, Intent.REFUSE_PAY,
                                    Intent.ANGRY_OR_HARDSHIP}) | _SPECIAL,
    State.AWAIT_ATAS_NAMA_ACK: frozenset({Intent.YES, Intent.NO}),
    State.AWAIT_ACCIDENT_REPORT: frozenset({Intent.REPORTED_YES, Intent.REPORTED_NO}),
    State.ENDED: frozenset(),
}


def allowed_intents_for(state: State) -> FrozenSet[Intent]:
    """Intent yang boleh dikeluarkan classifier di sebuah state (dipakai classifier LLM & eval)."""
    allowed = _ALLOWED[state]
    return allowed | _ANYTIME if allowed else allowed


def _tokens(text: str) -> FrozenSet[str]:
    return frozenset(t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3)


def _address_match(reference: str, spoken: str) -> bool:
    ref = _tokens(reference)
    if not ref:
        return False
    need = min(len(ref), max(2, math.ceil(len(ref) / 2)))
    return len(ref & _tokens(spoken)) >= need


class DialogueEngine:
    def __init__(self, ctx: CallContext) -> None:
        if ctx.birth_date is None and not ctx.address:
            raise ValueError("CallContext needs birth_date or address for identity verification")
        self._ctx = ctx
        self._now: datetime = ctx.now or datetime.now()
        self._vars = {
            "salam": S.salam(self._now.hour),
            "ai_name": ctx.ai_name,
            "company": ctx.company_name,
            "name": ctx.customer_name,
            "installment": S.rupiah(ctx.installment_amount),
            "penalty": S.rupiah(ctx.penalty_amount),
            "due_date": S.date_id(ctx.due_date),
            "autodebet": ctx.autodebet_cutoff,
            "magic": ctx.closing_magic_words,
        }
        self._state = State.AWAIT_IDENTITY
        self._started = False
        self._reask: List[str] = []
        self._strikes = 0
        self._off_script = 0
        self._verify_attempts = 0
        self._verified = False
        self._pushes = 0
        self._b_played = False
        self._tag: Optional[Tag] = None
        self._ptp_date: Optional[date] = None
        self._notes: List[str] = []
        self._transcript: List[Turn] = []
        self._visited: List[str] = []

    # --- API publik ---

    @property
    def state(self) -> State:
        return self._state

    @property
    def finished(self) -> bool:
        return self._state == State.ENDED

    def allowed_intents(self) -> FrozenSet[Intent]:
        return allowed_intents_for(self._state)

    def start(self) -> List[str]:
        if self._started:
            raise RuntimeError("call already started")
        self._started = True
        self._visited.append(State.AWAIT_IDENTITY.value)
        greeting = S.OPEN_GREETING if self._ctx.disclose_ai else S.OPEN_GREETING_UNDISCLOSED
        return self._ask([greeting, S.OPEN_CONFIRM], reask=[S.OPEN_CONFIRM])

    def handle(self, u: Understanding) -> List[str]:
        if not self._started:
            raise RuntimeError("call not started")
        if self.finished:
            return []
        if u.text:
            self._transcript.append(Turn("customer", u.text, self._state.value))
        if u.intent == Intent.ASKS_IF_AI:
            # jujur soal identitas, tidak dihitung sebagai pertanyaan di luar script / tidak jelas
            return self._say([S.AI_IDENTITY] + self._reask)
        if self._state == State.AWAIT_ATAS_NAMA_ACK:
            return self._close(Tag.CBC_ATAS_NAMA, [])
        intent = u.intent if u.intent in self.allowed_intents() else Intent.UNCLEAR
        handler = {
            State.AWAIT_IDENTITY: self._on_identity,
            State.AWAIT_VERIFICATION: self._on_verification,
            State.AWAIT_EMPATHY: self._on_empathy,
            State.AWAIT_PROMISE: self._on_promise,
            State.AWAIT_ACCIDENT_REPORT: self._on_accident,
        }[self._state]
        return handler(u, intent)

    def result(self) -> CallResult:
        return CallResult(
            call_id=self._ctx.call_id,
            tag=self._tag,
            verified=self._verified,
            ptp_date=self._ptp_date,
            note="; ".join(self._notes) or None,
            transcript=list(self._transcript),
            states_visited=list(self._visited),
            external_customer_id=self._ctx.external_customer_id,
            external_loan_id=self._ctx.external_loan_id,
        )

    # --- helper output ---

    def _say(self, lines: List[str], **fmt: str) -> List[str]:
        out = [line.format(**{**self._vars, **fmt}) for line in lines]
        for text in out:
            self._transcript.append(Turn("ai", text, self._state.value))
        return out

    def _ask(self, lines: List[str], reask: Optional[List[str]] = None) -> List[str]:
        self._reask = reask if reask is not None else [lines[-1]]
        return self._say(lines)

    def _goto(self, state: State) -> None:
        self._state = state
        self._strikes = 0
        self._visited.append(state.value)

    def _end(self, tag: Tag, lines: List[str], note: Optional[str] = None,
             ptp_date: Optional[date] = None, **fmt: str) -> List[str]:
        out = self._say(lines, **fmt)
        self._tag = tag
        self._ptp_date = ptp_date
        if note:
            self._notes.append(note)
        self._state = State.ENDED
        self._visited.append(State.ENDED.value)
        return out

    def _close(self, tag: Tag, lines: List[str], note: Optional[str] = None,
               ptp_date: Optional[date] = None, **fmt: str) -> List[str]:
        """Akhiri lewat Fase 4 (closing)."""
        self._visited.append("CLOSING")
        return self._end(tag, lines + [S.CLOSING], note, ptp_date, **fmt)

    def _noise(self, intent: Intent, give_up: Callable[[], List[str]]) -> List[str]:
        """OFF_SCRIPT / UNCLEAR / SILENCE: jawaban aman + ulang pertanyaan, atau menyerah."""
        if intent == Intent.OFF_SCRIPT:
            self._off_script += 1
            if self._off_script >= MAX_OFF_SCRIPT:
                return self._end(Tag.CBC_NO_DEAL, [S.OFF_SCRIPT_CLOSE], note="pertanyaan di luar script")
            return self._say([S.FALLBACK_OFF_SCRIPT] + self._reask)
        self._strikes += 1
        if self._strikes >= MAX_STRIKES:
            return give_up()
        return self._say(self._reask)

    # --- Fase 1 ---

    def _on_identity(self, u: Understanding, intent: Intent) -> List[str]:
        if intent == Intent.YES:
            self._goto(State.AWAIT_VERIFICATION)
            return self._ask([S.VERIFY_Q])
        if intent == Intent.NO_THIRD_PARTY:
            return self._end(Tag.CBC_TITIP_PESAN, [S.TITIP_PESAN])
        if intent == Intent.DEBTOR_DECEASED:
            return self._end(Tag.CBC_TITIP_PESAN, [S.DECEASED], note="debitur meninggal")
        if intent == Intent.WRONG_NUMBER:
            return self._end(Tag.DSS, [S.DSS_CLOSE])
        if intent == Intent.BUSY_CALLBACK:
            tomorrow = u.slots.get("callback_day") == "tomorrow"
            if u.slots.get("callback_time"):
                self._notes.append("callback jam %s" % u.slots["callback_time"])
            return self._end(Tag.LONG_TERM_CALLBACK if tomorrow else Tag.SHORT_TERM_CALLBACK,
                             [S.CALLBACK], when="besok" if tomorrow else "nanti")
        return self._noise(intent, give_up=lambda: self._end(Tag.OTHERS, [S.DSS_CLOSE]))

    # --- Fase 2 ---

    def _on_verification(self, u: Understanding, intent: Intent) -> List[str]:
        if intent == Intent.NO_THIRD_PARTY:
            return self._end(Tag.CBC_TITIP_PESAN, [S.TITIP_PESAN])
        if intent == Intent.DEBTOR_DECEASED:
            return self._end(Tag.CBC_TITIP_PESAN, [S.DECEASED], note="debitur meninggal")
        if intent == Intent.OFF_SCRIPT:
            return self._noise(intent, give_up=lambda: [])
        if intent == Intent.PROVIDES_VERIFICATION and self._verify(u.slots):
            self._verified = True
            self._goto(State.AWAIT_EMPATHY)
            return self._ask([S.DISCLOSURE, S.EMPATHY_Q])
        self._verify_attempts += 1
        if self._verify_attempts >= MAX_VERIFY_ATTEMPTS:
            return self._end(Tag.CBC_NO_DEAL, [S.VERIFY_FAILED_CLOSE], note="verifikasi gagal")
        return self._say([S.VERIFY_Q])

    def _verify(self, slots: Dict[str, object]) -> bool:
        birth = slots.get("birth_date")
        if isinstance(birth, str):
            try:
                birth = date.fromisoformat(birth)
            except ValueError:
                birth = None
        if self._ctx.birth_date is not None and birth == self._ctx.birth_date:
            return True
        address = slots.get("address")
        return bool(self._ctx.address and isinstance(address, str)
                    and _address_match(self._ctx.address, address))

    def _on_empathy(self, u: Understanding, intent: Intent) -> List[str]:
        if intent in (Intent.FORGOT_OR_WILL_PAY, Intent.PROMISE_PAY):
            return self._scenario_a()
        if intent in (Intent.ANGRY_OR_HARDSHIP, Intent.REFUSE_PAY):
            return self._scenario_b()
        special = self._special(u, intent)
        if special is not None:
            return special
        return self._noise(intent, give_up=self._scenario_a)

    # --- Fase 3 ---

    def _scenario_a(self) -> List[str]:
        self._goto(State.AWAIT_PROMISE)
        return self._ask(S.A_LINES)

    def _scenario_b(self) -> List[str]:
        self._goto(State.AWAIT_PROMISE)
        self._b_played = True
        self._pushes = max(self._pushes, 1)
        return self._ask(S.B_LINES)

    def _on_promise(self, u: Understanding, intent: Intent) -> List[str]:
        if intent == Intent.PROMISE_PAY:
            try:
                days = int(u.slots.get("promise_days", 0))
            except (TypeError, ValueError):
                days = -1
            if days < 0:
                return self._noise(Intent.UNCLEAR, give_up=self._no_deal)
            if days < self._ctx.max_promise_days:
                return self._ptp(days)
            return self._push()
        if intent in (Intent.REFUSE_PAY, Intent.ANGRY_OR_HARDSHIP):
            return self._push()
        special = self._special(u, intent)
        if special is not None:
            return special
        return self._noise(intent, give_up=self._no_deal)

    def _ptp(self, days: int) -> List[str]:
        ptp_date = self._now.date() + timedelta(days=days)
        when = "hari ini" if days == 0 else "tanggal " + S.date_id(ptp_date)
        return self._close(Tag.PTP, [S.PTP], ptp_date=ptp_date, when=when)

    def _push(self) -> List[str]:
        """Janji terlalu jauh / menolak bayar: negosiasi, bukan menerima."""
        if self._pushes >= MAX_PUSHES:
            return self._no_deal()
        self._pushes += 1
        self._strikes = 0
        if not self._b_played:
            self._b_played = True
            return self._ask(S.B_LINES)
        return self._ask([S.B_ILUSI])

    def _no_deal(self) -> List[str]:
        return self._close(Tag.CBC_NO_DEAL, [S.NO_DEAL], note="tidak ada janji bayar dalam batas")

    # --- Kasus khusus ---

    def _special(self, u: Understanding, intent: Intent) -> Optional[List[str]]:
        if intent == Intent.CLAIMS_PAID:
            return self._close(Tag.UNK, [S.UNK])
        if intent == Intent.ATAS_NAMA:
            self._goto(State.AWAIT_ATAS_NAMA_ACK)
            return self._ask([S.ATAS_NAMA])
        if intent == Intent.UNIT_LOST:
            return self._close(Tag.CBC_NO_DEAL, [S.UNIT_LOST], note="unit hilang")
        if intent == Intent.UNIT_ACCIDENT:
            self._notes.append("unit kecelakaan")
            self._goto(State.AWAIT_ACCIDENT_REPORT)
            return self._ask([S.ACCIDENT_Q])
        return None

    def _on_accident(self, u: Understanding, intent: Intent) -> List[str]:
        accident_date = u.slots.get("accident_date")
        if accident_date:
            self._notes.append("tanggal kejadian %s" % accident_date)
        if intent == Intent.REPORTED_YES:
            return self._close(Tag.CBC_NO_DEAL, [S.ACCIDENT_REPORTED])
        if intent == Intent.REPORTED_NO:
            return self._close(Tag.CBC_NO_DEAL, [S.ACCIDENT_NOT_REPORTED])
        return self._noise(intent, give_up=lambda: self._close(Tag.CBC_NO_DEAL, [S.ACCIDENT_NOT_REPORTED]))

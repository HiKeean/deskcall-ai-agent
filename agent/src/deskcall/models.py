"""Payload panggilan: CallContext (masuk), Understanding (hasil klasifikasi), CallResult (keluar).

CallContext/CallResult adalah bahan kontrak API tahap B.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Tag(str, Enum):
    NSTD = "NSTD"
    CBR = "CBR"
    PTP = "PTP"
    UNK = "UNK"
    CBC_NO_DEAL = "CBC_NO_DEAL"
    CBC_TITIP_PESAN = "CBC_TITIP_PESAN"
    CBC_ATAS_NAMA = "CBC_ATAS_NAMA"
    DSS = "DSS"
    OTHERS = "OTHERS"
    SHORT_TERM_CALLBACK = "SHORT_TERM_CALLBACK"
    LONG_TERM_CALLBACK = "LONG_TERM_CALLBACK"


class Intent(str, Enum):
    """Enum tertutup: satu-satunya hal yang boleh dikeluarkan classifier (LLM)."""

    YES = "YES"
    NO = "NO"
    NO_THIRD_PARTY = "NO_THIRD_PARTY"  # bukan nasabah / keluarga / orang lain yang angkat
    WRONG_NUMBER = "WRONG_NUMBER"
    BUSY_CALLBACK = "BUSY_CALLBACK"  # slots: callback_day (today|tomorrow), callback_time
    DEBTOR_DECEASED = "DEBTOR_DECEASED"
    PROVIDES_VERIFICATION = "PROVIDES_VERIFICATION"  # slots: birth_date (date) / address (str)
    DECLINES_VERIFICATION = "DECLINES_VERIFICATION"
    FORGOT_OR_WILL_PAY = "FORGOT_OR_WILL_PAY"  # lupa / sibuk / akan bayar / tidak ada kendala
    ANGRY_OR_HARDSHIP = "ANGRY_OR_HARDSHIP"  # marah / keberatan finansial berat
    CLAIMS_PAID = "CLAIMS_PAID"
    ATAS_NAMA = "ATAS_NAMA"
    UNIT_LOST = "UNIT_LOST"
    UNIT_ACCIDENT = "UNIT_ACCIDENT"  # slots: accident_date (date, opsional)
    REPORTED_YES = "REPORTED_YES"
    REPORTED_NO = "REPORTED_NO"
    PROMISE_PAY = "PROMISE_PAY"  # slots: promise_days (int, 0 = hari ini)
    REFUSE_PAY = "REFUSE_PAY"
    ASKS_IF_AI = "ASKS_IF_AI"  # nasabah menanyakan apakah ini robot/AI/manusia -> dijawab jujur
    OFF_SCRIPT = "OFF_SCRIPT"
    UNCLEAR = "UNCLEAR"
    SILENCE = "SILENCE"


@dataclass
class Understanding:
    intent: Intent
    slots: Dict[str, Any] = field(default_factory=dict)
    text: str = ""  # ucapan asli nasabah, untuk transkrip


@dataclass
class CallContext:
    call_id: str
    customer_name: str
    ai_name: str
    company_name: str
    installment_amount: int
    penalty_amount: int
    due_date: date
    autodebet_cutoff: str = "21.00"
    closing_magic_words: str = "Selamat beraktivitas kembali"
    birth_date: Optional[date] = None
    address: Optional[str] = None
    max_promise_days: int = 9  # janji bayar harus < max_promise_days hari
    disclose_ai: bool = True  # False hanya untuk demo (pembuka tanpa "asisten digital"); tetap jujur kalau ditanya langsung
    now: Optional[datetime] = None
    external_customer_id: Optional[str] = None
    external_loan_id: Optional[str] = None


def call_context_from_metadata(raw: str) -> "CallContext":
    """Bangun CallContext dari JSON snake_case dispatch metadata (kontrak: docs/API.md)."""
    import json
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("dispatch metadata must be a JSON object")
    fields = {
        "call_id": str(data["call_id"]),
        "customer_name": str(data["customer_name"]),
        "ai_name": str(data["ai_name"]),
        "company_name": str(data["company_name"]),
        "installment_amount": int(data["installment_amount"]),
        "penalty_amount": int(data["penalty_amount"]),
        "due_date": date.fromisoformat(data["due_date"]),
    }
    if data.get("autodebet_cutoff"):
        fields["autodebet_cutoff"] = str(data["autodebet_cutoff"])
    if data.get("closing_magic_words"):
        fields["closing_magic_words"] = str(data["closing_magic_words"])
    if data.get("birth_date"):
        fields["birth_date"] = date.fromisoformat(data["birth_date"])
    if data.get("address"):
        fields["address"] = str(data["address"])
    if data.get("max_promise_days") is not None:
        fields["max_promise_days"] = int(data["max_promise_days"])
    if data.get("disclose_ai") is False:
        fields["disclose_ai"] = False
    for key in ("external_customer_id", "external_loan_id"):
        if data.get(key):
            fields[key] = str(data[key])
    return CallContext(**fields)


@dataclass
class Turn:
    speaker: str  # "ai" | "customer"
    text: str
    state: str


@dataclass
class CallResult:
    call_id: str
    tag: Optional[Tag]
    verified: bool
    ptp_date: Optional[date]
    note: Optional[str]
    transcript: List[Turn]
    states_visited: List[str]
    external_customer_id: Optional[str] = None
    external_loan_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tag": self.tag.value if self.tag else None,
            "verified": self.verified,
            "ptp_date": self.ptp_date.isoformat() if self.ptp_date else None,
            "note": self.note,
            "transcript": [{"speaker": t.speaker, "text": t.text, "state": t.state} for t in self.transcript],
            "states_visited": self.states_visited,
            "external_customer_id": self.external_customer_id,
            "external_loan_id": self.external_loan_id,
        }

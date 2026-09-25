"""Classifier ucapan nasabah -> Understanding.

RuleBasedClassifier = regex sederhana untuk simulator & test (M1). Classifier LLM (M2) mengimplementasikan
Protocol yang sama dan wajib mengeluarkan Intent dari `allowed` saja.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Pattern, Protocol, Tuple

from .models import Intent, Understanding

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7, "agu": 8, "agt": 8,
           "sep": 9, "okt": 10, "nov": 11, "des": 12}


class IntentClassifier(Protocol):
    def classify(self, text: str, allowed: Iterable[Intent], state: Optional[str] = None) -> Understanding: ...


def parse_date_id(text: str) -> Optional[date]:
    """Tanggal lahir/kejadian dari ucapan: '17 agustus 1990', '17-08-1990', '17/8/1990', '1990-08-17'."""
    t = text.lower()
    try:
        m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.search(r"\b(\d{1,2})[\s/.\-](\d{1,2})[\s/.\-](\d{4})\b", t)
        if m:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = re.search(r"\b(\d{1,2})\s+([a-z]{3,})\s+(\d{4})\b", t)
        if m and m.group(2)[:3] in _MONTHS:
            return date(int(m.group(3)), _MONTHS[m.group(2)[:3]], int(m.group(1)))
    except ValueError:
        return None
    return None


def parse_promise_days(text: str) -> int:
    """Berapa hari dari sekarang nasabah berjanji bayar. Default 0 (hari ini)."""
    t = text.lower()
    m = re.search(r"(\d+)\s*hari", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*minggu", t)
    if m:
        return 7 * int(m.group(1))
    m = re.search(r"(\d+)\s*bulan", t)
    if m:
        return 30 * int(m.group(1))
    if re.search(r"seminggu|minggu depan", t):
        return 7
    if re.search(r"sebulan|bulan depan", t):
        return 30
    if "lusa" in t:
        return 2
    if "besok" in t:
        return 1
    return 0


def _r(pattern: str) -> Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Urutan = prioritas. Hanya intent yang ada di `allowed` yang dipertimbangkan.
_RULES: List[Tuple[Intent, Pattern[str]]] = [
    (Intent.ASKS_IF_AI, _r(r"\b(robot|bot|ai|a\.i\.?|manusia|mesin)\b|orang (beneran|asli|sungguhan)|suara (komputer|mesin)")),
    (Intent.DEBTOR_DECEASED, _r(r"meninggal|wafat|almarhum|\balm\b|sudah tiada|berpulang")),
    (Intent.WRONG_NUMBER, _r(r"salah sambung|salah nomor|tidak kenal|nggak kenal|gak kenal|ga kenal")),
    (Intent.BUSY_CALLBACK, _r(r"(telepon|telpon|hubungi|call).{0,25}(nanti|lagi|besok|jam)"
                              r"|(sedang|lagi) (meeting|rapat|sibuk|nyetir|di jalan)")),
    (Intent.NO_THIRD_PARTY, _r(r"(saya|ini) (istri|suami|anak|ibu|bapak|ayah|kakak|adik|saudara|keluarga|"
                               r"teman|orang tua)|bukan (orangnya|dia|beliau)|(dia|beliau).{0,12}(tidak|gak|nggak) ada"
                               r"|^\s*bukan\b")),
    (Intent.UNIT_LOST, _r(r"hilang|dicuri|raib|kemalingan")),
    (Intent.UNIT_ACCIDENT, _r(r"kecelakaan|ditabrak|menabrak|tabrakan|hancur")),
    (Intent.ATAS_NAMA, _r(r"dipinjam|pinjam nama|cuma nama|nama saja|dipakai (sama )?(si |teman|saudara|orang)")),
    (Intent.CLAIMS_PAID, _r(r"(sudah|udah|telah|dah)\b.{0,10}\b(bayar|transfer|lunas)")),
    (Intent.REPORTED_NO, _r(r"\b(belum|blm)\b")),
    (Intent.REPORTED_YES, _r(r"(sudah|udah|dah).{0,15}lapor|^\s*(sudah|udah|dah)\b")),
    (Intent.DECLINES_VERIFICATION, _r(r"tidak mau|nggak mau|gak mau|ga mau|tidak bisa|kenapa harus|untuk apa")),
    (Intent.REFUSE_PAY, _r(r"(tidak|nggak|gak|ga|belum) (bisa|sanggup|mampu|mau)( bayar)?")),
    (Intent.ANGRY_OR_HARDSHIP, _r(r"marah|kesel|kesal|apaan sih|jangan (telepon|telpon|ganggu)|ganggu|"
                                  r"(tidak|nggak|gak|ga|belum) (punya|ada) uang|bangkrut|\bphk\b|lagi sulit|"
                                  r"susah banget|dipecat|usaha (sepi|bangkrut)")),
    (Intent.FORGOT_OR_WILL_PAY, _r(r"lupa|kelupaan|sibuk|akan bayar|mau bayar|(tidak|nggak|gak|ga) ada kendala")),
    (Intent.PROMISE_PAY, _r(r"\b(bayar|transfer|lunasi|setor)\b|hari ini|besok|lusa|minggu depan|bulan depan|"
                            r"\d+ (hari|minggu|bulan)|^\s*(ya|iya|ok|oke|siap|bisa|baik)\b")),
    (Intent.YES, _r(r"\b(ya|iya|yaa|betul|benar|bener|yup|ok|oke|baik|dengan saya|saya sendiri|speaking)\b")),
    (Intent.NO, _r(r"^\s*(tidak|nggak|gak|ga|bukan)\b")),
]

_TIME_CUE = _r(r"\b(besok|lusa|minggu depan|bulan depan|seminggu|sebulan)\b|\d+ (hari|minggu|bulan)")

_OFF_SCRIPT = _r(r"\?|kenapa|bagaimana|gimana|berapa|\bkok\b|apa itu|bunga|keringanan|diskon|restruktur|"
                 r"dispute|tidak sesuai|salah hitung")


class RuleBasedClassifier:
    def classify(self, text: str, allowed: Iterable[Intent], state: Optional[str] = None) -> Understanding:
        allowed_set = set(allowed)
        clean = text.strip()
        if not clean:
            return Understanding(Intent.SILENCE, {}, text)

        if Intent.PROVIDES_VERIFICATION in allowed_set:
            picked = self._first_match(clean, allowed_set - {Intent.PROVIDES_VERIFICATION})
            if picked is not None:
                return Understanding(picked, {}, text)
            birth = parse_date_id(clean)
            slots: Dict[str, Any] = {"birth_date": birth} if birth else {"address": clean}
            return Understanding(Intent.PROVIDES_VERIFICATION, slots, text)

        picked = self._first_match(clean, allowed_set)
        if picked == Intent.REFUSE_PAY and Intent.PROMISE_PAY in allowed_set and _TIME_CUE.search(clean):
            picked = Intent.PROMISE_PAY  # "gak bisa hari ini, besok bisa" = janji besok
        if picked is not None:
            return Understanding(picked, self._slots(picked, clean), text)
        if _OFF_SCRIPT.search(clean):
            return Understanding(Intent.OFF_SCRIPT, {}, text)
        return Understanding(Intent.UNCLEAR, {}, text)

    @staticmethod
    def _first_match(text: str, allowed: set) -> Optional[Intent]:
        for intent, pattern in _RULES:
            if intent in allowed and pattern.search(text):
                return intent
        return None

    @staticmethod
    def _slots(intent: Intent, text: str) -> Dict[str, Any]:
        if intent == Intent.PROMISE_PAY:
            return {"promise_days": parse_promise_days(text)}
        if intent == Intent.BUSY_CALLBACK:
            slots: Dict[str, Any] = {"callback_day": "tomorrow" if re.search(r"besok", text, re.I) else "today"}
            m = re.search(r"jam\s*(\d{1,2})([.:](\d{2}))?", text, re.I)
            if m:
                slots["callback_time"] = "%02d:%s" % (int(m.group(1)), m.group(3) or "00")
            return slots
        if intent == Intent.UNIT_ACCIDENT:
            found = parse_date_id(text)
            return {"accident_date": found.isoformat()} if found else {}
        return {}

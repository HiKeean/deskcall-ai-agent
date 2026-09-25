"""Simulator teks: ngobrol dengan dialogue engine tanpa suara/LiveKit.

    PYTHONPATH=src python3 -m deskcall.simulator [--hour 14] [--json]

Ketik ucapan nasabah biasa (diklasifikasi rule-based), atau paksa intent:
    !PROMISE_PAY promise_days=3        !BUSY_CALLBACK callback_day=tomorrow
Perintah: /intents (intent yang boleh sekarang), /quit
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from typing import List, Optional

from .classifier import RuleBasedClassifier
from .engine import DialogueEngine
from .models import CallContext, Intent, Understanding


def demo_context(hour: Optional[int] = None, disclose_ai: bool = True) -> CallContext:
    now = datetime.now()
    if hour is not None:
        now = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return CallContext(
        call_id="demo-1",
        customer_name="Budi Santoso",
        ai_name="Albert",
        company_name="KlarFinance",
        installment_amount=1_500_000,
        penalty_amount=90_000,
        due_date=now.date() - timedelta(days=3),
        birth_date=date(1990, 8, 17),
        address="Jl. Merdeka No. 10 Bandung",
        now=now,
        disclose_ai=disclose_ai,
    )


def parse_override(line: str) -> Understanding:
    parts = line[1:].split()
    intent = Intent[parts[0].upper()]
    slots = {}
    for kv in parts[1:]:
        key, _, value = kv.partition("=")
        slots[key] = int(value) if value.lstrip("-").isdigit() else value
    return Understanding(intent, slots, line)


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="deskcall text simulator")
    parser.add_argument("--hour", type=int, help="paksa jam panggilan (untuk salam)")
    parser.add_argument("--json", action="store_true", help="cetak CallResult sebagai JSON di akhir")
    parser.add_argument("--demo", action="store_true", help="pembuka tanpa \"asisten digital\" (hanya demo)")
    args = parser.parse_args(argv)

    engine = DialogueEngine(demo_context(args.hour, disclose_ai=not args.demo))
    classifier = RuleBasedClassifier()
    for line in engine.start():
        print("AI   : " + line)

    while not engine.finished:
        try:
            text = input("Anda : ").strip()
        except EOFError:
            break
        if text in ("/quit", "/q"):
            break
        if text == "/intents":
            print("       " + ", ".join(sorted(i.value for i in engine.allowed_intents())))
            continue
        try:
            u = (parse_override(text) if text.startswith("!")
                 else classifier.classify(text, engine.allowed_intents()))
        except (KeyError, IndexError):
            print("       intent tidak dikenal; lihat /intents")
            continue
        print("       [%s %s]" % (u.intent.value, u.slots or ""))
        for line in engine.handle(u):
            print("AI   : " + line)

    result = engine.result()
    print("\n== TAG: %s | PTP: %s | note: %s" % (result.tag.value if result.tag else "-",
                                               result.ptp_date or "-", result.note or "-"))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Bandingkan classifier pada eval set.

    PYTHONPATH=src python3 -m deskcall.evaluate            # rule-based (offline)
    ANTHROPIC_API_KEY=... PYTHONPATH=src python3 -m deskcall.evaluate --llm
    GEMINI_API_KEY=... PYTHONPATH=src python3 -m deskcall.evaluate --llm
    LLM_BASE_URL=https://api.groq.com/openai/v1 LLM_MODEL=... LLM_API_KEY=... PYTHONPATH=src python3 -m deskcall.evaluate --llm
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from .classifier import IntentClassifier, RuleBasedClassifier
from .engine import State, allowed_intents_for
from .evalset import CASES, CRITICAL
from .llm_classifier import LlmError
from .models import Intent


def run(classifier: IntentClassifier) -> Tuple[float, float, List[Tuple[str, str, Intent, Intent]]]:
    wrong: List[Tuple[str, str, Intent, Intent]] = []
    critical_total = critical_ok = 0
    for state, text, expected in CASES:
        got = classifier.classify(text, allowed_intents_for(State(state)), state).intent
        if expected in CRITICAL:
            critical_total += 1
            critical_ok += got == expected
        if got != expected:
            wrong.append((state, text, expected, got))
    accuracy = 1 - len(wrong) / len(CASES)
    return accuracy, critical_ok / critical_total if critical_total else 1.0, wrong


class _PacedClient:
    """Bungkus klien LLM: beri jeda antar panggilan (free tier punya batas token/menit) dan hitung kegagalan,
    karena LlmIntentClassifier diam-diam fallback ke rule-based dan itu membuat akurasi tampak lebih bagus."""

    def __init__(self, inner, delay: float) -> None:
        self._inner = inner
        self._delay = delay
        self._calls = 0
        self.failures = 0

    def complete_tool(self, system: str, user: str, tool: Dict[str, Any]) -> Dict[str, Any]:
        if self._calls and self._delay:
            time.sleep(self._delay)
        self._calls += 1
        try:
            return self._inner.complete_tool(system, user, tool)
        except LlmError:
            self.failures += 1
            raise


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true",
                        help="pakai LLM dari environment (ANTHROPIC_API_KEY, GEMINI_API_KEY, atau LLM_BASE_URL + LLM_MODEL [+ LLM_API_KEY])")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="jeda detik antar panggilan LLM (free tier: coba 6)")
    args = parser.parse_args(argv)
    paced = None
    if args.llm:
        from .llm_classifier import LlmIntentClassifier, client_from_env
        client = client_from_env(timeout=15)
        if client is None:
            print("Set ANTHROPIC_API_KEY, GEMINI_API_KEY, atau LLM_BASE_URL + LLM_MODEL", file=sys.stderr)
            return 2
        paced = _PacedClient(client, args.delay)
        classifier: IntentClassifier = LlmIntentClassifier(paced)
        name = "LLM (%s, %s)" % (type(client).__name__, os.environ.get("GEMINI_MODEL") or os.environ.get("LLM_MODEL", "default"))
    else:
        classifier = RuleBasedClassifier()
        name = "rule-based"
    accuracy, critical, wrong = run(classifier)
    print("%s: akurasi %.1f%% (%d/%d), intent kritis %.0f%%" % (
        name, accuracy * 100, len(CASES) - len(wrong), len(CASES), critical * 100))
    for state, text, expected, got in wrong:
        print("  [%s] %r -> %s (harusnya %s)" % (state, text, got.value, expected.value))
    if paced and paced.failures:
        print("PERINGATAN: LLM gagal %d kali (fallback ke rule-based) -> angka di atas TIDAK valid untuk LLM. "
              "Coba --delay 6." % paced.failures, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

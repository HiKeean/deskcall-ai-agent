import asyncio
import json
import threading
import unittest
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from deskcall.api_client import ApiError, DeskcallApi
from deskcall.classifier import RuleBasedClassifier
from deskcall.engine import DialogueEngine
from deskcall.models import CallContext, CallResult, Intent, Tag, call_context_from_metadata
from deskcall.runner import CallRunner, CustomerLeft


def make_ctx():
    return CallContext(
        call_id="c1", customer_name="Budi Santoso", ai_name="Sinta", company_name="PT Demo Finance",
        installment_amount=1_500_000, penalty_amount=90_000, due_date=date(2026, 9, 18),
        birth_date=date(1990, 8, 17), now=datetime(2026, 9, 21, 9, 30))


class ScriptedIO:
    """Nasabah palsu: inputs berisi teks / None (diam) / CustomerLeft (keluar)."""

    def __init__(self, inputs):
        self.inputs = list(inputs)
        self.said = []

    async def say(self, lines):
        self.said.extend(lines)

    async def listen(self, timeout):
        if not self.inputs:
            raise CustomerLeft()
        item = self.inputs.pop(0)
        if item is CustomerLeft:
            raise CustomerLeft()
        return item


class Sink:
    def __init__(self):
        self.results = []

    async def apost_result(self, call_id, result):
        self.results.append((call_id, result))


class ExplodingClassifier:
    def classify(self, text, allowed, state=None):
        raise RuntimeError("boom")


class RunnerTest(unittest.IsolatedAsyncioTestCase):
    async def run_call(self, inputs, classifier=None, **kw):
        io, sink = ScriptedIO(inputs), Sink()
        runner = CallRunner(DialogueEngine(make_ctx()), classifier or RuleBasedClassifier(), io, sink, "c1", **kw)
        result = await runner.run()
        return io, sink, result

    async def test_full_conversation_ends_with_ptp_and_posts_result_once(self):
        io, sink, result = await self.run_call(["iya betul", "17 agustus 1990", "lupa pak, maaf", "iya saya bayar besok"])

        self.assertEqual(result.tag, Tag.PTP)
        self.assertEqual(result.ptp_date, date(2026, 9, 22))
        self.assertTrue(result.verified)
        self.assertEqual(len(sink.results), 1)
        self.assertEqual(sink.results[0][0], "c1")
        self.assertIn("Selamat pagi, saya Sinta, asisten digital dari PT Demo Finance.", io.said[0])
        self.assertIn("Tetap jaga kesehatan", io.said[-1])
        self.assertEqual([t.speaker for t in result.transcript if t.speaker == "customer"].__len__(), 4)

    async def test_classifier_receives_current_state(self):
        seen = []

        class Spy(RuleBasedClassifier):
            def classify(self, text, allowed, state=None):
                seen.append(state)
                return super().classify(text, allowed, state)

        await self.run_call(["iya betul", "17 agustus 1990"], classifier=Spy())
        self.assertEqual(seen[:2], ["AWAIT_IDENTITY", "AWAIT_VERIFICATION"])

    async def test_silence_twice_at_start_is_others(self):
        _, sink, result = await self.run_call([None, ""])

        self.assertEqual(result.tag, Tag.OTHERS)
        self.assertEqual(len(sink.results), 1)

    async def test_customer_leaving_midway_still_posts_result_with_transcript(self):
        io, sink, result = await self.run_call(["iya betul", CustomerLeft])

        self.assertEqual(result.tag, Tag.OTHERS)
        self.assertEqual(result.note, "nasabah keluar sebelum percakapan selesai")
        self.assertEqual(len(sink.results), 1)
        self.assertGreaterEqual(len(result.transcript), 3)

    async def test_customer_leaving_after_engine_finished_keeps_engine_tag(self):
        _, _, result = await self.run_call(["salah sambung pak", CustomerLeft])
        self.assertEqual(result.tag, Tag.DSS)

    async def test_error_inside_call_still_posts_result(self):
        _, sink, result = await self.run_call(["iya betul"], classifier=ExplodingClassifier())

        self.assertEqual(result.tag, Tag.OTHERS)
        self.assertEqual(result.note, "percakapan berhenti tidak wajar")
        self.assertEqual(len(sink.results), 1)

    async def test_max_turns_guard(self):
        _, sink, result = await self.run_call(["hmm"] * 100, max_turns=5)
        self.assertEqual(len(sink.results), 1)


class MetadataTest(unittest.TestCase):
    JAVA_STYLE = json.dumps({
        "call_id": "abc", "customer_name": "Budi Santoso", "ai_name": "Sinta", "company_name": "PT Demo",
        "installment_amount": 1500000, "penalty_amount": 90000, "due_date": "2026-09-18",
        "autodebet_cutoff": "21.00", "birth_date": "1990-08-17", "address": "Jl. Merdeka 10",
        "max_promise_days": 7, "external_customer_id": "C-1", "external_loan_id": "L-1"})

    def test_parses_dispatch_metadata_from_api(self):
        ctx = call_context_from_metadata(self.JAVA_STYLE)
        self.assertEqual((ctx.call_id, ctx.installment_amount, ctx.due_date), ("abc", 1500000, date(2026, 9, 18)))
        self.assertEqual((ctx.birth_date, ctx.address, ctx.max_promise_days), (date(1990, 8, 17), "Jl. Merdeka 10", 7))
        self.assertEqual((ctx.external_customer_id, ctx.external_loan_id), ("C-1", "L-1"))
        DialogueEngine(ctx).start()  # konteks valid untuk engine

    def test_disclose_ai_flag_from_metadata(self):
        base = json.loads(self.JAVA_STYLE)
        self.assertTrue(call_context_from_metadata(json.dumps(base)).disclose_ai)
        self.assertFalse(call_context_from_metadata(json.dumps(dict(base, disclose_ai=False))).disclose_ai)
        self.assertTrue(call_context_from_metadata(json.dumps(dict(base, disclose_ai=True))).disclose_ai)

    def test_optional_fields_use_defaults(self):
        minimal = json.dumps({"call_id": "abc", "customer_name": "B", "ai_name": "S", "company_name": "P",
                              "installment_amount": 1, "penalty_amount": 0, "due_date": "2026-09-18",
                              "birth_date": "1990-08-17"})
        ctx = call_context_from_metadata(minimal)
        self.assertEqual((ctx.autodebet_cutoff, ctx.max_promise_days, ctx.address), ("21.00", 9, None))

    def test_invalid_metadata_is_rejected(self):
        for bad in ("[]", "{}", "not json", json.dumps({"call_id": "x"})):
            with self.assertRaises((ValueError, KeyError)):
                call_context_from_metadata(bad)


class _Handler(BaseHTTPRequestHandler):
    seen = []
    status = 200

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.seen.append({"path": self.path, "key": self.headers.get("X-API-Key"), "body": body})
        out = b"{}"
        self.send_response(_Handler.status)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


class ApiClientTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _Handler.seen, _Handler.status = [], 200
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.api = DeskcallApi("http://127.0.0.1:%d/" % self.server.server_port, "k-123", timeout=2)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def result(self, tag=Tag.PTP, ptp=date(2026, 9, 24)):
        from deskcall.models import Turn
        return CallResult("c1", tag, True, ptp, "catatan", [Turn("ai", "Halo", "AWAIT_IDENTITY")],
                          ["AWAIT_IDENTITY", "CLOSING"])

    def test_post_event(self):
        self.api.post_event("abc", "CUSTOMER_JOINED")
        self.api.post_event("abc", "UNREACHABLE", "tidak ada token")
        self.assertEqual(_Handler.seen[0], {"path": "/api/v1/calls/abc/events", "key": "k-123",
                                            "body": {"type": "CUSTOMER_JOINED"}})
        self.assertEqual(_Handler.seen[1]["body"], {"type": "UNREACHABLE", "detail": "tidak ada token"})

    def test_post_result_matches_api_contract(self):
        self.api.post_result("abc", self.result())
        seen = _Handler.seen[0]
        self.assertEqual(seen["path"], "/api/v1/calls/abc/result")
        self.assertEqual(seen["body"], {
            "tag": "PTP", "verified": True, "ptpDate": "2026-09-24", "note": "catatan",
            "transcript": [{"speaker": "ai", "text": "Halo", "state": "AWAIT_IDENTITY"}],
            "statesVisited": ["AWAIT_IDENTITY", "CLOSING"]})

    def test_result_without_tag_is_refused_locally(self):
        with self.assertRaises(ApiError):
            self.api.post_result("abc", self.result(tag=None, ptp=None))
        self.assertEqual(_Handler.seen, [])

    def test_http_errors_and_unreachable_raise_api_error(self):
        _Handler.status = 409
        with self.assertRaises(ApiError):
            self.api.post_result("abc", self.result())
        with self.assertRaises(ApiError):
            DeskcallApi("http://127.0.0.1:1", "k", timeout=1).post_event("abc", "CUSTOMER_JOINED")

    async def test_async_event_never_raises_but_result_does(self):
        dead = DeskcallApi("http://127.0.0.1:1", "k", timeout=1)
        await dead.apost_event("abc", "CUSTOMER_JOINED")  # ditelan, hanya di-log
        with self.assertRaises(ApiError):
            await dead.apost_result("abc", self.result())


if __name__ == "__main__":
    unittest.main()

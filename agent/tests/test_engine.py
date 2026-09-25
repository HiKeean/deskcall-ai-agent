import unittest
from datetime import date, datetime

from deskcall import script as S
from deskcall.classifier import RuleBasedClassifier, parse_date_id, parse_promise_days
from deskcall.engine import DialogueEngine, State
from deskcall.models import CallContext, Intent, Tag, Understanding

BIRTH = date(1990, 8, 17)


def make_ctx(**overrides):
    base = dict(
        call_id="c1", customer_name="Budi Santoso", ai_name="Sinta", company_name="PT Demo Finance",
        installment_amount=1_500_000, penalty_amount=90_000, due_date=date(2026, 9, 18),
        birth_date=BIRTH, address="Jl. Merdeka No. 10 Bandung", now=datetime(2026, 9, 21, 9, 30),
    )
    base.update(overrides)
    return CallContext(**base)


def U(intent, text="", **slots):
    return Understanding(intent, slots, text)


YES = U(Intent.YES)
VERIFIED = U(Intent.PROVIDES_VERIFICATION, birth_date=BIRTH)
FORGOT = U(Intent.FORGOT_OR_WILL_PAY)
ANGRY = U(Intent.ANGRY_OR_HARDSHIP)
REFUSE = U(Intent.REFUSE_PAY)


def promise(days):
    return U(Intent.PROMISE_PAY, promise_days=days)


def run(*steps, **ctx_overrides):
    engine = DialogueEngine(make_ctx(**ctx_overrides))
    spoken = list(engine.start())
    for step in steps:
        spoken += engine.handle(step)
    return engine, spoken


def to_promise(*more, scenario=FORGOT, **ctx_overrides):
    return run(YES, VERIFIED, scenario, *more, **ctx_overrides)


class OpeningTest(unittest.TestCase):
    def test_opening_lines(self):
        engine, spoken = run()
        self.assertEqual(spoken[0], "Selamat pagi, saya Sinta, asisten digital dari PT Demo Finance.")
        self.assertEqual(spoken[1], "Apakah benar saya terhubung dengan Bapak/Ibu Budi Santoso?")
        self.assertEqual(engine.state, State.AWAIT_IDENTITY)

    def test_greeting_by_hour(self):
        for hour, word in [(8, "pagi"), (12, "siang"), (16, "sore"), (19, "malam")]:
            _, spoken = run(now=datetime(2026, 9, 21, hour, 0))
            self.assertIn("Selamat %s," % word, spoken[0])

    def test_context_needs_verification_data(self):
        with self.assertRaises(ValueError):
            DialogueEngine(make_ctx(birth_date=None, address=None))

    def test_handle_before_start_fails(self):
        with self.assertRaises(RuntimeError):
            DialogueEngine(make_ctx()).handle(YES)


class Phase1Test(unittest.TestCase):
    def test_wrong_number_is_dss(self):
        engine, spoken = run(U(Intent.WRONG_NUMBER))
        self.assertEqual(engine.result().tag, Tag.DSS)
        self.assertEqual(spoken[-1], S.DSS_CLOSE)
        self.assertTrue(engine.finished)

    def test_busy_today_is_short_term_callback(self):
        engine, spoken = run(U(Intent.BUSY_CALLBACK, callback_day="today", callback_time="14:00"))
        self.assertEqual(engine.result().tag, Tag.SHORT_TERM_CALLBACK)
        self.assertEqual(spoken[-1], "Baik, kami akan hubungi kembali nanti. Terima kasih.")
        self.assertIn("14:00", engine.result().note)

    def test_busy_tomorrow_is_long_term_callback(self):
        engine, spoken = run(U(Intent.BUSY_CALLBACK, callback_day="tomorrow"))
        self.assertEqual(engine.result().tag, Tag.LONG_TERM_CALLBACK)
        self.assertEqual(spoken[-1], "Baik, kami akan hubungi kembali besok. Terima kasih.")

    def test_third_party_gets_message_without_debt_details(self):
        engine, spoken = run(U(Intent.NO_THIRD_PARTY))
        self.assertEqual(engine.result().tag, Tag.CBC_TITIP_PESAN)
        self.assertEqual(spoken[-1], S.TITIP_PESAN.format(name="Budi Santoso"))
        self.assertNotIn("Rp", " ".join(spoken))

    def test_deceased_debtor(self):
        engine, spoken = run(U(Intent.DEBTOR_DECEASED))
        result = engine.result()
        self.assertEqual(result.tag, Tag.CBC_TITIP_PESAN)
        self.assertEqual(result.note, "debitur meninggal")
        self.assertIn("Customer Service cabang kami secepatnya", spoken[-1])
        self.assertNotIn("Rp", " ".join(spoken))

    def test_unclear_twice_at_identity_is_others(self):
        engine, spoken = run(U(Intent.UNCLEAR), U(Intent.SILENCE))
        self.assertEqual(engine.result().tag, Tag.OTHERS)
        self.assertEqual(spoken.count(S.OPEN_CONFIRM.format(name="Budi Santoso")), 2)

    def test_intent_not_allowed_in_state_is_treated_as_unclear(self):
        engine, _ = run(promise(0))  # PROMISE_PAY tidak valid di AWAIT_IDENTITY
        self.assertEqual(engine.state, State.AWAIT_IDENTITY)
        self.assertFalse(engine.finished)


class Phase2Test(unittest.TestCase):
    def test_verification_by_birth_date_then_disclosure(self):
        engine, spoken = run(YES, VERIFIED)
        self.assertTrue(engine.result().verified)
        self.assertEqual(engine.state, State.AWAIT_EMPATHY)
        self.assertIn("angsuran Bapak/Ibu sebesar Rp 1.500.000 dengan denda berjalan sebesar Rp 90.000, "
                      "yang telah jatuh tempo pada tanggal 18 September 2026", spoken[-2])
        self.assertEqual(spoken[-1], S.EMPATHY_Q)

    def test_verification_by_address(self):
        engine, _ = run(YES, U(Intent.PROVIDES_VERIFICATION, address="Jalan Merdeka nomor 10 Bandung"))
        self.assertTrue(engine.result().verified)

    def test_wrong_then_right_verification(self):
        engine, spoken = run(YES, U(Intent.PROVIDES_VERIFICATION, birth_date=date(1985, 1, 1)), VERIFIED)
        self.assertTrue(engine.result().verified)
        self.assertEqual(spoken.count(S.VERIFY_Q), 2)

    def test_verification_fails_twice_never_discloses_debt(self):
        wrong = U(Intent.PROVIDES_VERIFICATION, birth_date=date(1985, 1, 1))
        engine, spoken = run(YES, wrong, U(Intent.DECLINES_VERIFICATION))
        result = engine.result()
        self.assertEqual(result.tag, Tag.CBC_NO_DEAL)
        self.assertFalse(result.verified)
        self.assertEqual(spoken[-1], S.VERIFY_FAILED_CLOSE)
        self.assertNotIn("Rp", " ".join(spoken))

    def test_family_answering_during_verification_never_discloses(self):
        engine, spoken = run(YES, U(Intent.NO_THIRD_PARTY))
        self.assertEqual(engine.result().tag, Tag.CBC_TITIP_PESAN)
        self.assertNotIn("Rp", " ".join(spoken))

    def test_empathy_silence_twice_proceeds_to_scenario_a(self):
        engine, spoken = run(YES, VERIFIED, U(Intent.SILENCE), U(Intent.UNCLEAR))
        self.assertEqual(engine.state, State.AWAIT_PROMISE)
        self.assertEqual(spoken[-3:], S.A_LINES)


class Phase3Test(unittest.TestCase):
    def test_scenario_a_lines(self):
        engine, spoken = to_promise()
        self.assertEqual(spoken[-3:], S.A_LINES)
        self.assertEqual(engine.state, State.AWAIT_PROMISE)

    def test_scenario_b_lines(self):
        engine, spoken = to_promise(scenario=ANGRY)
        self.assertEqual(spoken[-3:], S.B_LINES)

    def test_ptp_today_exact_line_then_closing(self):
        engine, spoken = to_promise(promise(0))
        result = engine.result()
        self.assertEqual(result.tag, Tag.PTP)
        self.assertEqual(result.ptp_date, date(2026, 9, 21))
        self.assertEqual(
            spoken[-2],
            "Baik, kami catat janji bayarnya hari ini. Sebagai pengingat, jika menggunakan sistem autodebet, "
            "mohon pastikan dana sudah tersedia beserta sisa saldo mengendap di rekening sebelum jam maksimal "
            "autodebet yaitu pukul 21.00. Jika melalui transfer VA atau minimarket, mohon simpan bukti "
            "pembayarannya.")
        self.assertEqual(
            spoken[-1],
            "Informasi Bapak/Ibu sudah kami perbarui di sistem. Terima kasih atas waktunya. "
            "Tetap jaga kesehatan, dan selamat pagi. Selamat beraktivitas kembali.")

    def test_ptp_within_limit_confirms_date(self):
        engine, spoken = to_promise(promise(8))
        self.assertEqual(engine.result().tag, Tag.PTP)
        self.assertEqual(engine.result().ptp_date, date(2026, 9, 29))
        self.assertIn("janji bayarnya tanggal 29 September 2026", spoken[-2])

    def test_promise_at_or_beyond_limit_is_not_accepted_and_negotiates(self):
        for days in (9, 14):
            engine, spoken = to_promise(promise(days))
            self.assertFalse(engine.finished, days)
            self.assertNotEqual(engine.result().tag, Tag.PTP)
            self.assertEqual(spoken[-3:], S.B_LINES)

    def test_negotiation_then_accepts_shorter_promise(self):
        engine, _ = to_promise(promise(20), promise(2))
        self.assertEqual(engine.result().tag, Tag.PTP)
        self.assertEqual(engine.result().ptp_date, date(2026, 9, 23))

    def test_scenario_a_refusals_push_twice_then_no_deal(self):
        engine, spoken = to_promise(REFUSE)
        self.assertEqual(spoken[-3:], S.B_LINES)  # push 1: Skenario B
        spoken = engine.handle(REFUSE)
        self.assertEqual(spoken, [S.B_ILUSI])  # push 2: Ilusi Kontrol saja
        spoken = engine.handle(REFUSE)
        self.assertEqual(engine.result().tag, Tag.CBC_NO_DEAL)
        self.assertEqual(spoken[0], S.NO_DEAL)

    def test_scenario_b_gets_one_more_push_then_no_deal(self):
        engine, _ = to_promise(scenario=ANGRY)
        self.assertEqual(engine.handle(REFUSE), [S.B_ILUSI])
        engine.handle(promise(30))
        self.assertEqual(engine.result().tag, Tag.CBC_NO_DEAL)

    def test_promise_state_silence_twice_is_no_deal(self):
        engine, _ = to_promise(U(Intent.SILENCE), U(Intent.SILENCE))
        self.assertEqual(engine.result().tag, Tag.CBC_NO_DEAL)

    def test_claims_already_paid_is_unk(self):
        engine, spoken = to_promise(U(Intent.CLAIMS_PAID))
        self.assertEqual(engine.result().tag, Tag.UNK)
        self.assertEqual(spoken[-2], S.UNK)

    def test_claims_already_paid_from_empathy(self):
        engine, _ = run(YES, VERIFIED, U(Intent.CLAIMS_PAID))
        self.assertEqual(engine.result().tag, Tag.UNK)


class SpecialCasesTest(unittest.TestCase):
    def test_atas_nama_then_closing(self):
        engine, spoken = run(YES, VERIFIED, U(Intent.ATAS_NAMA))
        self.assertEqual(spoken[-1], S.ATAS_NAMA.format(name="Budi Santoso"))
        self.assertEqual(engine.state, State.AWAIT_ATAS_NAMA_ACK)
        closing = engine.handle(YES)
        self.assertEqual(engine.result().tag, Tag.CBC_ATAS_NAMA)
        self.assertEqual(len(closing), 1)
        self.assertIn("Informasi Bapak/Ibu sudah kami perbarui", closing[0])

    def test_unit_lost(self):
        engine, spoken = run(YES, VERIFIED, U(Intent.UNIT_LOST))
        self.assertEqual(spoken[-2], S.UNIT_LOST)
        self.assertEqual(engine.result().tag, Tag.CBC_NO_DEAL)
        self.assertEqual(engine.result().note, "unit hilang")

    def test_accident_not_reported(self):
        engine, spoken = run(YES, VERIFIED, U(Intent.UNIT_ACCIDENT),
                             U(Intent.REPORTED_NO, accident_date="2026-09-15"))
        self.assertIn(S.ACCIDENT_Q, spoken)
        self.assertEqual(spoken[-2], S.ACCIDENT_NOT_REPORTED)
        self.assertEqual(engine.result().tag, Tag.CBC_NO_DEAL)
        self.assertIn("2026-09-15", engine.result().note)

    def test_accident_reported(self):
        engine, spoken = run(YES, VERIFIED, U(Intent.UNIT_ACCIDENT), U(Intent.REPORTED_YES))
        self.assertEqual(spoken[-2], S.ACCIDENT_REPORTED)

    def test_accident_unclear_defaults_to_not_reported(self):
        engine, spoken = run(YES, VERIFIED, U(Intent.UNIT_ACCIDENT), U(Intent.UNCLEAR), U(Intent.SILENCE))
        self.assertEqual(spoken[-2], S.ACCIDENT_NOT_REPORTED)

    def test_special_case_also_recognised_in_phase_3(self):
        engine, _ = to_promise(U(Intent.UNIT_LOST))
        self.assertEqual(engine.result().tag, Tag.CBC_NO_DEAL)


class DemoOpeningTest(unittest.TestCase):
    def test_default_discloses_digital_assistant(self):
        _, spoken = run()
        self.assertEqual(spoken[0], "Selamat pagi, saya Sinta, asisten digital dari PT Demo Finance.")

    def test_demo_opening_is_short_but_direct_question_is_still_answered_honestly(self):
        engine, spoken = run(disclose_ai=False)
        self.assertEqual(spoken[0], "Selamat pagi, saya Sinta dari PT Demo Finance.")
        self.assertNotIn("asisten digital", " ".join(spoken))
        answer = engine.handle(U(Intent.ASKS_IF_AI, "ini robot ya?"))
        self.assertEqual(answer[0], "Benar, saya Sinta, asisten digital dari PT Demo Finance.")


class AiIdentityTest(unittest.TestCase):
    ANSWER = "Benar, saya Sinta, asisten digital dari PT Demo Finance."

    def test_honest_answer_then_repeat_pending_question(self):
        engine, spoken = run(U(Intent.ASKS_IF_AI, "ini robot ya?"))
        self.assertEqual(spoken[-2:], [self.ANSWER, S.OPEN_CONFIRM.format(name="Budi Santoso")])
        self.assertEqual(engine.state, State.AWAIT_IDENTITY)
        self.assertFalse(engine.finished)

    def test_not_counted_as_off_script_or_unclear(self):
        engine, _ = run(YES, VERIFIED, *[U(Intent.ASKS_IF_AI)] * 5)
        self.assertEqual(engine.state, State.AWAIT_EMPATHY)
        self.assertFalse(engine.finished)

    def test_not_counted_as_failed_verification(self):
        engine, spoken = run(YES, U(Intent.ASKS_IF_AI), U(Intent.ASKS_IF_AI), VERIFIED)
        self.assertTrue(engine.result().verified)
        self.assertEqual(spoken.count(self.ANSWER), 2)

    def test_answer_does_not_leak_debt_before_verification(self):
        _, spoken = run(YES, U(Intent.ASKS_IF_AI))
        self.assertNotIn("Rp", " ".join(spoken))

    def test_allowed_in_every_waiting_state(self):
        engine, _ = run(YES, VERIFIED, FORGOT)
        self.assertEqual(engine.state, State.AWAIT_PROMISE)
        self.assertIn(Intent.ASKS_IF_AI, engine.allowed_intents())
        spoken = engine.handle(U(Intent.ASKS_IF_AI))
        self.assertEqual(spoken, [self.ANSWER, S.A_LINES[-1]])
        atas_nama, _ = run(YES, VERIFIED, U(Intent.ATAS_NAMA))
        self.assertEqual(atas_nama.handle(U(Intent.ASKS_IF_AI))[0], self.ANSWER)
        self.assertFalse(atas_nama.finished)

    def test_classifier_detects_question(self):
        clf = RuleBasedClassifier()
        engine = DialogueEngine(make_ctx())
        engine.start()
        for text in ["ini robot ya?", "kamu manusia atau bukan", "ini orang beneran?", "suara komputer ya", "ini AI?"]:
            self.assertEqual(clf.classify(text, engine.allowed_intents()).intent, Intent.ASKS_IF_AI, text)
        self.assertEqual(clf.classify("iya betul", engine.allowed_intents()).intent, Intent.YES)


class OffScriptTest(unittest.TestCase):
    def test_safe_answer_then_repeat_question(self):
        engine, spoken = run(YES, VERIFIED, U(Intent.OFF_SCRIPT, "minta keringanan dong"))
        self.assertEqual(spoken[-2:], [S.FALLBACK_OFF_SCRIPT, S.EMPATHY_Q])
        self.assertEqual(engine.state, State.AWAIT_EMPATHY)

    def test_three_off_script_closes_politely(self):
        engine, spoken = to_promise(U(Intent.OFF_SCRIPT), U(Intent.OFF_SCRIPT), U(Intent.OFF_SCRIPT))
        self.assertEqual(spoken[-1], S.OFF_SCRIPT_CLOSE)
        self.assertEqual(engine.result().tag, Tag.CBC_NO_DEAL)

    def test_engine_ignores_input_after_end(self):
        engine, _ = run(U(Intent.WRONG_NUMBER))
        self.assertEqual(engine.handle(YES), [])


class ResultTest(unittest.TestCase):
    def test_transcript_and_states(self):
        engine, _ = run(YES, VERIFIED, FORGOT, U(Intent.PROMISE_PAY, "saya bayar hari ini", promise_days=0))
        result = engine.result()
        self.assertEqual([t.speaker for t in result.transcript if t.speaker == "customer"], ["customer"])
        self.assertEqual(result.states_visited[:4], ["AWAIT_IDENTITY", "AWAIT_VERIFICATION",
                                                      "AWAIT_EMPATHY", "AWAIT_PROMISE"])
        self.assertIn("CLOSING", result.states_visited)
        data = result.to_dict()
        self.assertEqual(data["tag"], "PTP")
        self.assertEqual(data["ptp_date"], "2026-09-21")

    def test_external_ids_are_echoed(self):
        engine, _ = run(U(Intent.WRONG_NUMBER), external_customer_id="C-1", external_loan_id="L-9")
        self.assertEqual(engine.result().external_loan_id, "L-9")


class ClassifierTest(unittest.TestCase):
    def setUp(self):
        self.clf = RuleBasedClassifier()

    def classify(self, engine, text):
        return self.clf.classify(text, engine.allowed_intents())

    def test_identity_answers(self):
        engine = DialogueEngine(make_ctx())
        engine.start()
        cases = [("iya betul pak", Intent.YES), ("bukan pak", Intent.NO_THIRD_PARTY),
                 ("saya istrinya, dia lagi keluar", Intent.NO_THIRD_PARTY),
                 ("salah sambung pak", Intent.WRONG_NUMBER), ("bapaknya sudah meninggal", Intent.DEBTOR_DECEASED),
                 ("saya lagi meeting, telepon lagi besok jam 10 ya", Intent.BUSY_CALLBACK),
                 ("", Intent.SILENCE), ("hmm", Intent.UNCLEAR)]
        for text, expected in cases:
            self.assertEqual(self.classify(engine, text).intent, expected, text)

    def test_callback_slots(self):
        engine = DialogueEngine(make_ctx())
        engine.start()
        u = self.classify(engine, "telepon lagi besok jam 10 ya")
        self.assertEqual(u.slots, {"callback_day": "tomorrow", "callback_time": "10:00"})

    def test_full_conversation_through_classifier(self):
        engine = DialogueEngine(make_ctx())
        engine.start()
        for text in ["iya betul", "17 agustus 1990", "lupa pak, maaf", "iya saya bayar besok"]:
            engine.handle(self.classify(engine, text))
        result = engine.result()
        self.assertEqual(result.tag, Tag.PTP)
        self.assertEqual(result.ptp_date, date(2026, 9, 22))
        self.assertTrue(result.verified)

    def test_off_script_question_detected(self):
        engine = DialogueEngine(make_ctx())
        engine.start()
        engine.handle(self.classify(engine, "iya"))
        engine.handle(self.classify(engine, "17/08/1990"))
        u = self.classify(engine, "kok dendanya segitu?")
        self.assertEqual(u.intent, Intent.OFF_SCRIPT)

    def test_parsers(self):
        self.assertEqual(parse_date_id("17 Agustus 1990"), BIRTH)
        self.assertEqual(parse_date_id("17-08-1990"), BIRTH)
        self.assertEqual(parse_date_id("1990-08-17"), BIRTH)
        self.assertIsNone(parse_date_id("Jl. Merdeka 10"))
        self.assertIsNone(parse_date_id("31 februari 1990"))
        self.assertEqual(parse_promise_days("hari ini"), 0)
        self.assertEqual(parse_promise_days("besok"), 1)
        self.assertEqual(parse_promise_days("lusa"), 2)
        self.assertEqual(parse_promise_days("5 hari lagi"), 5)
        self.assertEqual(parse_promise_days("minggu depan"), 7)
        self.assertEqual(parse_promise_days("bulan depan"), 30)


if __name__ == "__main__":
    unittest.main()

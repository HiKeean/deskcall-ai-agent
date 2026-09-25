"""Eval set klasifikasi intent: ucapan nasabah (Indonesia, formal & slang) per state -> intent yang diharapkan.

Dipakai untuk membandingkan classifier (rule-based vs LLM) sebelum dipercaya di panggilan sungguhan.
Tambah kasus dari transkrip nyata (tanpa data pribadi) seiring waktu.
"""
from __future__ import annotations

from typing import List, Tuple

from .models import Intent as I

# (state, ucapan, intent yang diharapkan)
CASES: List[Tuple[str, str, I]] = [
    # --- AWAIT_IDENTITY ---
    ("AWAIT_IDENTITY", "iya betul", I.YES),
    ("AWAIT_IDENTITY", "halo, iya dengan saya sendiri", I.YES),
    ("AWAIT_IDENTITY", "ya benar pak, ada apa ya", I.YES),
    ("AWAIT_IDENTITY", "bukan pak, ini istrinya", I.NO_THIRD_PARTY),
    ("AWAIT_IDENTITY", "saya anaknya, bapak lagi keluar", I.NO_THIRD_PARTY),
    ("AWAIT_IDENTITY", "ini ibunya, orangnya lagi gak ada", I.NO_THIRD_PARTY),
    ("AWAIT_IDENTITY", "bukan", I.NO_THIRD_PARTY),
    ("AWAIT_IDENTITY", "salah sambung pak", I.WRONG_NUMBER),
    ("AWAIT_IDENTITY", "maaf ini salah nomor", I.WRONG_NUMBER),
    ("AWAIT_IDENTITY", "gak kenal saya sama nama itu", I.WRONG_NUMBER),
    ("AWAIT_IDENTITY", "bapaknya sudah meninggal bulan lalu", I.DEBTOR_DECEASED),
    ("AWAIT_IDENTITY", "almarhum sudah tiada mbak", I.DEBTOR_DECEASED),
    ("AWAIT_IDENTITY", "saya lagi meeting nih, telpon lagi nanti siang ya", I.BUSY_CALLBACK),
    ("AWAIT_IDENTITY", "lagi nyetir pak, besok aja hubungi lagi", I.BUSY_CALLBACK),
    ("AWAIT_IDENTITY", "ini robot ya?", I.ASKS_IF_AI),
    ("AWAIT_IDENTITY", "ini orang beneran atau mesin?", I.ASKS_IF_AI),
    ("AWAIT_IDENTITY", "hmm", I.UNCLEAR),
    ("AWAIT_IDENTITY", "", I.SILENCE),
    # --- AWAIT_VERIFICATION ---
    ("AWAIT_VERIFICATION", "17 agustus 1990", I.PROVIDES_VERIFICATION),
    ("AWAIT_VERIFICATION", "tanggal lahir saya 5 mei 1985", I.PROVIDES_VERIFICATION),
    ("AWAIT_VERIFICATION", "jalan merdeka nomor 10 bandung", I.PROVIDES_VERIFICATION),
    ("AWAIT_VERIFICATION", "gak mau kasih tau, buat apa sih", I.DECLINES_VERIFICATION),
    ("AWAIT_VERIFICATION", "kenapa harus disebutin?", I.DECLINES_VERIFICATION),
    ("AWAIT_VERIFICATION", "saya suaminya pak", I.NO_THIRD_PARTY),
    ("AWAIT_VERIFICATION", "beliau sudah meninggal", I.DEBTOR_DECEASED),
    ("AWAIT_VERIFICATION", "kamu robot ya", I.ASKS_IF_AI),
    # --- AWAIT_EMPATHY ---
    ("AWAIT_EMPATHY", "lupa pak, maaf ya", I.FORGOT_OR_WILL_PAY),
    ("AWAIT_EMPATHY", "kemarin lagi sibuk banget jadi kelewat", I.FORGOT_OR_WILL_PAY),
    ("AWAIT_EMPATHY", "gak ada kendala kok, nanti saya bayar", I.FORGOT_OR_WILL_PAY),
    ("AWAIT_EMPATHY", "saya lagi susah pak, usaha sepi, gak punya uang", I.ANGRY_OR_HARDSHIP),
    ("AWAIT_EMPATHY", "kalian nelpon terus ganggu banget", I.ANGRY_OR_HARDSHIP),
    ("AWAIT_EMPATHY", "udah dibilangin belum ada uang, kesel saya", I.ANGRY_OR_HARDSHIP),
    ("AWAIT_EMPATHY", "motor saya dicuri minggu lalu", I.UNIT_LOST),
    ("AWAIT_EMPATHY", "mobilnya raib pak, hilang", I.UNIT_LOST),
    ("AWAIT_EMPATHY", "mobil saya kecelakaan tanggal 10 september", I.UNIT_ACCIDENT),
    ("AWAIT_EMPATHY", "motornya hancur ditabrak truk", I.UNIT_ACCIDENT),
    ("AWAIT_EMPATHY", "sebenarnya saya cuma dipinjam nama, mobilnya dipakai teman", I.ATAS_NAMA),
    ("AWAIT_EMPATHY", "sudah saya bayar kemarin lewat transfer", I.CLAIMS_PAID),
    ("AWAIT_EMPATHY", "udah lunas kok pak", I.CLAIMS_PAID),
    ("AWAIT_EMPATHY", "gimana kalau dapat keringanan?", I.OFF_SCRIPT),
    ("AWAIT_EMPATHY", "kok dendanya segitu besar?", I.OFF_SCRIPT),
    ("AWAIT_EMPATHY", "ini rekaman atau orang asli?", I.ASKS_IF_AI),
    # --- AWAIT_PROMISE ---
    ("AWAIT_PROMISE", "iya hari ini saya transfer", I.PROMISE_PAY),
    ("AWAIT_PROMISE", "bisa, lewat indomaret aja", I.PROMISE_PAY),
    ("AWAIT_PROMISE", "besok pagi ya pak", I.PROMISE_PAY),
    ("AWAIT_PROMISE", "3 hari lagi setelah gajian", I.PROMISE_PAY),
    ("AWAIT_PROMISE", "minggu depan baru bisa", I.PROMISE_PAY),
    ("AWAIT_PROMISE", "gak bisa hari ini, besok saya bayar", I.PROMISE_PAY),
    ("AWAIT_PROMISE", "belum bisa bayar pak", I.REFUSE_PAY),
    ("AWAIT_PROMISE", "gak mampu saya sekarang", I.REFUSE_PAY),
    ("AWAIT_PROMISE", "tidak sanggup pak, maaf", I.REFUSE_PAY),
    ("AWAIT_PROMISE", "jangan telepon terus, saya kesel", I.ANGRY_OR_HARDSHIP),
    ("AWAIT_PROMISE", "nanti ya", I.UNCLEAR),
    ("AWAIT_PROMISE", "sudah saya transfer tadi pagi", I.CLAIMS_PAID),
    ("AWAIT_PROMISE", "hah? ulangi dong", I.UNCLEAR),
    ("AWAIT_PROMISE", "berapa sih bunganya?", I.OFF_SCRIPT),
    ("AWAIT_PROMISE", "ini AI ya?", I.ASKS_IF_AI),
    # --- AWAIT_ATAS_NAMA_ACK ---
    ("AWAIT_ATAS_NAMA_ACK", "iya nanti saya sampaikan", I.YES),
    ("AWAIT_ATAS_NAMA_ACK", "gak bisa pak, dia susah dihubungi", I.NO),
    # --- AWAIT_ACCIDENT_REPORT ---
    ("AWAIT_ACCIDENT_REPORT", "belum lapor pak", I.REPORTED_NO),
    ("AWAIT_ACCIDENT_REPORT", "sudah kemarin ke cabang", I.REPORTED_YES),
    ("AWAIT_ACCIDENT_REPORT", "sudah", I.REPORTED_YES),
    ("AWAIT_ACCIDENT_REPORT", "belum sempat", I.REPORTED_NO),
]

# Kesalahan di intent ini berbahaya (salah tag / salah sikap ke nasabah): targetnya 100%.
CRITICAL = {I.DEBTOR_DECEASED, I.WRONG_NUMBER, I.NO_THIRD_PARTY, I.ASKS_IF_AI}

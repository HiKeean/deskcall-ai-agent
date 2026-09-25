"""Semua ucapan AI. Sumber: docs/SCRIPT.md. Jangan ubah wording tanpa persetujuan owner.

Kalimat bertanda DRAFT tidak ada di script asli dan belum disetujui owner.
"""
from __future__ import annotations

from datetime import date
from typing import List

_MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
           "September", "Oktober", "November", "Desember"]


def rupiah(amount: int) -> str:
    return "Rp " + f"{amount:,}".replace(",", ".")


def date_id(d: date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def salam(hour: int) -> str:
    if hour < 11:
        return "pagi"
    if hour < 15:
        return "siang"
    if hour < 18:
        return "sore"
    return "malam"  # DRAFT: script hanya Pagi/Siang/Sore


# --- Fase 1 ---
OPEN_GREETING = "Selamat {salam}, saya {ai_name}, asisten digital dari {company}."
# Hanya untuk panggilan demo (CallContext.disclose_ai=False). Jika nasabah bertanya "ini robot?", AI_IDENTITY tetap menjawab jujur.
OPEN_GREETING_UNDISCLOSED = "Selamat {salam}, saya {ai_name} dari {company}."
OPEN_CONFIRM = "Apakah benar saya terhubung dengan Bapak/Ibu {name}?"
DSS_CLOSE = "Mohon maaf mengganggu waktunya, terima kasih."
CALLBACK = "Baik, kami akan hubungi kembali {when}. Terima kasih."
TITIP_PESAN = ("Mohon sampaikan pesan kepada Bapak/Ibu {name} untuk segera mengecek aplikasi "
               "atau menghubungi kami terkait info penting kontraknya.")

# --- Fase 2 ---
VERIFY_Q = ("Baik. Untuk keamanan data, boleh dibantu konfirmasi tanggal lahir atau alamat "
            "domisili Bapak/Ibu saat ini?")
DISCLOSURE = ("Terima kasih. Kami menginformasikan bahwa di sistem kami tercatat angsuran Bapak/Ibu "
              "sebesar {installment} dengan denda berjalan sebesar {penalty}, yang telah jatuh tempo "
              "pada tanggal {due_date}, saat ini belum kami terima.")
EMPATHY_Q = ("Bolehkah kami tahu, apakah ada kendala yang Bapak/Ibu alami terkait pembayaran "
             "angsuran bulan ini?")

# --- Fase 3 ---
A_LINES: List[str] = [
    "Kami memahami situasinya. Namun, sebagai informasi, ini adalah penanganan terakhir oleh tim DAS "
    "sebelum dialihkan ke penanganan lapangan atau FAC (Field Agency Collection).",
    "Agar skor kredit Bapak/Ibu di SLIK OJK tetap berstatus lancar dan denda tidak terus bertambah, "
    "kami sarankan untuk melakukan pembayaran hari ini.",
    "Apakah Bapak/Ibu bisa memprioritaskan pembayaran hari ini via transfer Virtual Account, "
    "atau melalui minimarket terdekat?",
]
B_ILUSI = ("Untuk meringankan, apakah Bapak/Ibu ingin kami bantu jadwalkan pembayarannya sore ini "
           "melalui transfer, atau akan diusahakan besok pagi di jam kerja?")
B_LINES: List[str] = [
    "Saya mengerti situasi yang sedang Bapak/Ibu hadapi saat ini tidak mudah. Tujuan kami menghubungi "
    "justru untuk membantu Bapak/Ibu menghentikan denda yang terus berjalan di sistem kami.",
    "Kami juga ingin menjaga agar nama baik Bapak/Ibu di SLIK OJK tidak memburuk, mengingat ini adalah "
    "penanganan terakhir sebelum data dialihkan ke tim penagihan lapangan.",
    B_ILUSI,
]
# {when}: "hari ini" atau "tanggal <tgl>" (DRAFT untuk selain hari ini)
PTP = ("Baik, kami catat janji bayarnya {when}. Sebagai pengingat, jika menggunakan sistem autodebet, "
       "mohon pastikan dana sudah tersedia beserta sisa saldo mengendap di rekening sebelum jam maksimal "
       "autodebet yaitu pukul {autodebet}. Jika melalui transfer VA atau minimarket, mohon simpan bukti "
       "pembayarannya.")
NO_DEAL = ("Baik, informasi ini akan kami catat di sistem. Namun kami ingatkan kembali, keterlambatan ini "
           "akan berdampak pada SLIK OJK Bapak/Ibu dan kemungkinan penyerahan ke tim lapangan. Kami harap "
           "Bapak/Ibu dapat segera mengusahakan dananya.")
UNK = "Baik, jika sudah dibayar mohon abaikan panggilan ini atau kirimkan bukti bayar ke nomor WA resmi kami."

# --- Fase 4 ---
CLOSING = ("Informasi Bapak/Ibu sudah kami perbarui di sistem. Terima kasih atas waktunya. "
           "Tetap jaga kesehatan, dan selamat {salam}. {magic}.")

# --- Kasus khusus ---
ATAS_NAMA = ("Baik, kami catat informasinya. Namun, karena kontrak terdaftar atas nama Bapak/Ibu {name}, "
             "maka secara hukum tanggung jawab tagihan dan dampak SLIK OJK tetap berada di Bapak/Ibu. "
             "Kami sarankan Bapak/Ibu segera berkoordinasi dengan pihak pemakai kendaraan agar pembayaran "
             "segera diselesaikan. Apakah bisa dibantu komunikasikan hari ini?")
UNIT_LOST = ("Kami turut prihatin atas kejadian tersebut. Terkait unit hilang, kami perlu melakukan "
             "pengecekan produk asuransi Bapak/Ibu. Kami arahkan Bapak/Ibu untuk segera menghubungi atau "
             "datang ke Customer Service cabang terdaftar paling lambat 3x24 jam sejak kejadian untuk "
             "konfirmasi apakah klaim asuransi dapat di-cover, karena kehilangan akibat kelalaian biasanya "
             "tidak ter-cover. Untuk sementara, kewajiban angsuran tetap berjalan sampai ada keputusan dari "
             "pihak asuransi.")
ACCIDENT_Q = ("Kami turut prihatin atas musibah yang terjadi. Untuk proses asuransinya, boleh kami tahu "
              "tanggal berapa kejadiannya? Dan apakah Bapak/Ibu sudah melapor ke kantor cabang kami?")
ACCIDENT_NOT_REPORTED = ("Kami arahkan untuk segera melapor ke Customer Service cabang membawa bukti "
                         "kepolisian dan dokumentasi agar bisa dicek coverage asuransinya.")
ACCIDENT_REPORTED = ("Baik, mohon tunggu konfirmasi dari cabang terkait hasilnya. Sambil menunggu, kami "
                     "informasikan bahwa tagihan saat ini masih tercatat aktif di sistem.")
DECEASED = ("Kami mewakili perusahaan mengucapkan turut berdukacita yang sedalam-dalamnya. Terkait kontrak "
            "pembiayaan ini, kami arahkan pihak ahli waris untuk segera mengurus Surat Akta Kematian (AKM) "
            "dan membawanya ke Customer Service cabang kami secepatnya. Hal ini penting untuk proses "
            "konfirmasi asuransi jiwa debitur. Informasi ini akan kami catat di sistem kami.")

# --- DRAFT: tidak ada di script asli, butuh approval owner ---
FALLBACK_OFF_SCRIPT = ("Mohon maaf, untuk hal tersebut Bapak/Ibu dapat menghubungi Customer Service "
                       "cabang terdaftar kami.")
VERIFY_FAILED_CLOSE = ("Mohon maaf, data yang disebutkan belum sesuai dengan data kami, sehingga kami "
                       "belum dapat melanjutkan. Terima kasih atas waktunya.")
OFF_SCRIPT_CLOSE = ("Baik, terima kasih atas waktunya. Silakan menghubungi Customer Service cabang kami "
                    "untuk informasi lebih lanjut.")
AI_IDENTITY = "Benar, saya {ai_name}, asisten digital dari {company}."

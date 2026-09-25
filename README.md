# deskcall

AI voice agent untuk **desk collection** nasabah menunggak awal (bucket 0–10 hari). Pipeline **STT → LLM → TTS** di atas LiveKit, dengan dialog yang dibatasi ketat oleh script penagihan.

- Dialog berjalan sebagai **state machine deterministik**. LLM hanya dipakai untuk klasifikasi intent ke enum tertutup, ekstraksi slot, dan fallback terbatas. Nominal, tanggal, dan nama selalu diambil dari data sistem, tidak pernah dikarang.
- AI **tidak menyamar jadi manusia**: pembukanya menyebut "asisten digital", dan kalau nasabah bertanya apakah ini AI, jawabannya jujur.
- Hasil panggilan di-*tag* otomatis (PTP, CBR, NSTD, UNK, CBC, DSS, dll.).

## Struktur

| Folder | Isi | Stack |
|---|---|---|
| `agent/` | Dialogue engine, classifier (rule-based + LLM), simulator teks, worker LiveKit | Python |
| `api/` | Call API + schema DB `deskcall` (Flyway) | Spring Boot 3.5, Java 21, Maven |
| `report/` | Halaman laporan hasil panggilan | Next.js 16 |

## Setup

```bash
cp .env.example .env   # isi kredensial LiveKit, DB, API key, provider LLM/STT/TTS
```

Semua kredensial dibaca dari env var. `.env` dan `.env.*` (kecuali `.env.example`) sudah ada di `.gitignore`.

### agent (Python)

Kode inti hanya memakai stdlib dan kompatibel dengan Python 3.9. Worker LiveKit butuh Python 3.12. Taruh venv-nya di luar repo:

```bash
uv venv ~/.venvs/deskcall --python 3.12
uv pip install --python ~/.venvs/deskcall/bin/python -e "agent[worker]"
```

```bash
cd agent
PYTHONPATH=src python3 -m unittest discover -s tests       # test
PYTHONPATH=src python3 -m deskcall.simulator [--hour 14]    # simulasi dialog lewat teks
PYTHONPATH=src python3 -m deskcall.evaluate [--llm]         # evaluasi classifier
```

Worker LiveKit (butuh API sudah jalan):

```bash
PYTHONPATH=agent/src ~/.venvs/deskcall/bin/python -m deskcall.worker start
```

Mode I/O diatur lewat `DESKCALL_IO_MODE` (`text` untuk uji lewat chat pakai `agent/tools/text_client.py`, `voice` untuk suara).

### api (Spring Boot)

```bash
cd api
mvn test               # H2 mode SQL Server, LiveKit di-mock
mvn spring-boot:run    # butuh .env terisi
```

Semua objek DB berada di schema `deskcall`. Autentikasi pakai header `X-API-Key`. Swagger UI hanya aktif kalau `DESKCALL_SWAGGER_ENABLED=true`, dan jangan dinyalakan di produksi.

### report (Next.js)

```bash
cd report
npm install
npm run dev    # http://127.0.0.1:3100
```

Isi `report/.env.local` dengan `DESKCALL_API_URL` dan `DESKCALL_API_KEY`. Halaman ini tidak punya login, jadi sengaja hanya bind ke localhost.

## Catatan keamanan

- Jangan commit `.env` atau `report/.env.local`.
- `DESKCALL_ALLOW_DEMO_OPENING=true` (pembuka tanpa disclosure AI) hanya untuk environment demo, jangan dipakai di produksi.

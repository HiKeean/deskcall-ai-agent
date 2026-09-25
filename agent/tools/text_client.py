"""Nasabah simulasi via teks: join room dengan token dari API lalu ngobrol dengan agent lewat LiveKit chat.

    ~/.venvs/deskcall/bin/python agent/tools/text_client.py --url wss://... --token <jwt> "iya betul" "17 agustus 1990" ...

Tiap ucapan dikirim setelah agent selesai bicara (hening 2 detik). Berhenti kalau agent mengucapkan penutup
atau sampai --max-wait detik. Transkrip dicetak ke stdout.
"""
import argparse
import asyncio

from livekit import rtc

CHAT_TOPIC = "lk.chat"
# kalimat terakhir agent di tiap jalur (penutup Fase 4, DSS, titip pesan, kasus khusus tanpa penutup)
END_PREFIXES = ("Informasi Bapak/Ibu sudah kami perbarui", "Mohon maaf mengganggu", "Mohon sampaikan pesan",
                "Kami mewakili perusahaan", "Mohon maaf, data yang disebutkan", "Baik, kami akan hubungi kembali")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--max-wait", type=float, default=60.0)
    parser.add_argument("utterances", nargs="*")
    args = parser.parse_args()

    room = rtc.Room()
    inbox: "asyncio.Queue[asyncio.Future]" = asyncio.Queue()

    def on_stream(reader, identity):
        inbox.put_nowait(asyncio.ensure_future(reader.read_all()))  # future antre sesuai urutan stream

    room.register_text_stream_handler(CHAT_TOPIC, on_stream)
    await room.connect(args.url, args.token)
    print("[client] connected as", room.local_participant.identity)

    pending = list(args.utterances)
    loop = asyncio.get_event_loop()
    deadline = loop.time() + args.max_wait
    closing = False

    async def drain(first_timeout: float) -> bool:
        """Cetak balasan agent sampai hening 1.5 detik; True kalau agent sudah menutup."""
        nonlocal closing
        timeout = first_timeout
        while True:
            try:
                line = await (await asyncio.wait_for(inbox.get(), timeout))
            except asyncio.TimeoutError:
                return closing
            print("AI      :", line)
            closing = closing or line.startswith(END_PREFIXES)
            timeout = 1.5

    await drain(15.0)  # kalimat pembuka
    while pending and not closing and loop.time() < deadline:
        text = pending.pop(0)
        print("CUSTOMER:", text)
        await room.local_participant.send_text(text, topic=CHAT_TOPIC)
        await drain(10.0)
    await asyncio.sleep(1)
    await room.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

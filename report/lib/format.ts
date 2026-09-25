import type { CallStatus, CallTag } from "./deskcall";

// Definisi tag mengikuti docs/SCRIPT.md
export const TAG_LABELS: Record<CallTag, string> = {
  PTP: "Janji bayar (PTP)",
  NSTD: "Tidak diangkat",
  CBR: "Tidak terjangkau",
  UNK: "Mengaku sudah bayar",
  CBC_NO_DEAL: "Terhubung, tanpa janji",
  CBC_TITIP_PESAN: "Titip pesan",
  CBC_ATAS_NAMA: "Nama dipinjam",
  DSS: "Salah sambung",
  OTHERS: "Lainnya (tutup/diam)",
  SHORT_TERM_CALLBACK: "Telepon lagi hari ini",
  LONG_TERM_CALLBACK: "Telepon lagi besok",
};

export const STATUS_LABELS: Record<CallStatus, string> = {
  CREATED: "Berdering",
  ANSWERED: "Sedang berlangsung",
  ENDED: "Selesai",
  FAILED: "Gagal",
};

/** Warna badge: hijau = hasil baik, kuning = perlu tindak lanjut, merah = tidak tersambung. */
export function tagTone(tag: CallTag | null): "good" | "warn" | "bad" | "muted" {
  if (!tag) return "muted";
  if (tag === "PTP") return "good";
  if (tag === "NSTD" || tag === "CBR" || tag === "DSS") return "bad";
  if (tag === "OTHERS") return "muted";
  return "warn";
}

const dateTime = new Intl.DateTimeFormat("id-ID", {
  timeZone: "Asia/Jakarta",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

const time = new Intl.DateTimeFormat("id-ID", {
  timeZone: "Asia/Jakarta",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export function formatDateTime(iso: string | null): string {
  return iso ? `${dateTime.format(new Date(iso))} WIB` : "—";
}

export function formatTime(iso: string | null): string {
  return iso ? time.format(new Date(iso)) : "—";
}

export function formatDate(isoDate: string | null): string {
  if (!isoDate) return "—";
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Intl.DateTimeFormat("id-ID", { day: "2-digit", month: "long", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(y, m - 1, d)));
}

/** Durasi ngobrol = diangkat sampai selesai. */
export function formatDuration(answeredAt: string | null, endedAt: string | null): string {
  if (!answeredAt || !endedAt) return "—";
  const seconds = Math.max(0, Math.round((Date.parse(endedAt) - Date.parse(answeredAt)) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

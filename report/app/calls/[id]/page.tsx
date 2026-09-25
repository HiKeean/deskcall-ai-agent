import Link from "next/link";
import { AutoRefresh } from "../../auto-refresh";
import { TagBadge } from "../../tag-badge";
import { DeskcallError, getCall } from "@/lib/deskcall";
import { STATUS_LABELS, formatDate, formatDateTime, formatDuration, formatTime } from "@/lib/format";

export const dynamic = "force-dynamic";

// Event dari API (lihat EventType + event sistem CREATED/DISPATCHED/RESULT_RECEIVED/sweeper)
const EVENT_LABELS: Record<string, string> = {
  CREATED: "Panggilan dibuat",
  DISPATCHED: "AI agent dikirim ke room",
  AGENT_JOINED: "AI agent masuk room",
  CUSTOMER_JOINED: "Nasabah mengangkat",
  CUSTOMER_DECLINED: "Nasabah menolak",
  UNREACHABLE: "Nasabah tidak terjangkau",
  CUSTOMER_LEFT: "Nasabah menutup",
  RESULT_RECEIVED: "Hasil panggilan diterima",
};

// Fase percakapan (state dialogue engine) untuk konteks tiap ucapan
const STATE_LABELS: Record<string, string> = {
  AWAIT_IDENTITY: "Konfirmasi identitas",
  AWAIT_VERIFICATION: "Verifikasi data",
  AWAIT_EMPATHY: "Empati",
  AWAIT_PROMISE: "Negosiasi janji bayar",
  AWAIT_ATAS_NAMA_ACK: "Nama dipinjam",
  AWAIT_ACCIDENT_REPORT: "Laporan kecelakaan",
  ENDED: "Penutup",
};

export default async function CallDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let call;
  try {
    call = await getCall(id);
  } catch (error) {
    return (
      <>
        <Link href="/" className="back">&larr; Kembali ke laporan</Link>
        <div className="error-box">{error instanceof DeskcallError ? error.message : "Gagal memuat panggilan"}</div>
      </>
    );
  }

  const inProgress = call.status === "CREATED" || call.status === "ANSWERED";
  const transcript = call.transcript ?? [];

  return (
    <>
      <Link href="/" className="back">&larr; Kembali ke laporan</Link>
      <div className="page-heading">
        <div>
          <h1>{call.customerName}</h1>
          <p>{formatDateTime(call.createdAt)} · Loan {call.externalLoanId ?? "—"}</p>
        </div>
        <TagBadge tag={call.tag} />
      </div>

      <div className="detail-grid">
        <div>
          <section className="card">
            <h2 className="card-title">Ringkasan</h2>
            <dl className="facts">
              <div><dt>Status</dt><dd>{STATUS_LABELS[call.status]}</dd></div>
              <div><dt>Hasil</dt><dd><TagBadge tag={call.tag} /></dd></div>
              <div><dt>Tgl janji bayar</dt><dd>{formatDate(call.ptpDate)}</dd></div>
              <div><dt>Identitas terverifikasi</dt><dd>{call.verified ? "Ya" : "Tidak"}</dd></div>
              <div><dt>Durasi bicara</dt><dd>{formatDuration(call.answeredAt, call.endedAt)}</dd></div>
              <div><dt>ID nasabah</dt><dd>{call.externalCustomerId ?? "—"}</dd></div>
              {call.note && <div><dt>Catatan</dt><dd>{call.note}</dd></div>}
            </dl>
          </section>

          <section className="card">
            <h2 className="card-title">Kronologi</h2>
            <ol className="timeline">
              {(call.events ?? []).map((event, index) => (
                <li key={index}>
                  <time>{formatTime(event.occurredAt)}</time>
                  <span>{EVENT_LABELS[event.type] ?? event.type}</span>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <section className="card">
          <h2 className="card-title">Transkrip</h2>
          <div className="transcript">
            {transcript.length === 0 ? (
              <p className="empty">{inProgress ? "Panggilan masih berlangsung…" : "Tidak ada percakapan."}</p>
            ) : (
              transcript.map((turn) => (
                <div key={turn.seq} className={`bubble bubble-${turn.speaker}`}>
                  <span className="bubble-meta">
                    {turn.speaker === "ai" ? "AI agent" : "Nasabah"}
                    {turn.state ? ` · ${STATE_LABELS[turn.state] ?? turn.state}` : ""}
                  </span>
                  {turn.text}
                </div>
              ))
            )}
          </div>
        </section>
      </div>
      {inProgress && <AutoRefresh seconds={5} />}
    </>
  );
}

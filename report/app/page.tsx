import Link from "next/link";
import { AutoRefresh } from "./auto-refresh";
import { TagBadge } from "./tag-badge";
import { type Call, type CallTag, DeskcallError, listCalls } from "@/lib/deskcall";
import { STATUS_LABELS, TAG_LABELS, formatDateTime, formatDate, formatDuration } from "@/lib/format";

export const dynamic = "force-dynamic";

const LOADED = 100;

export default async function ReportPage({ searchParams }: { searchParams: Promise<{ tag?: string }> }) {
  const { tag } = await searchParams;

  let calls: Call[];
  let total: number;
  try {
    const page = await listCalls({ size: LOADED });
    calls = page.items;
    total = page.totalElements;
  } catch (error) {
    const message = error instanceof DeskcallError ? error.message : "Gagal memuat data panggilan";
    return (
      <>
        <Heading />
        <div className="error-box">{message}</div>
        <AutoRefresh seconds={10} />
      </>
    );
  }

  const tagsPresent = Array.from(new Set(calls.map((c) => c.tag).filter((t): t is CallTag => t !== null)));
  const activeTag = tag && tag in TAG_LABELS ? (tag as CallTag) : null;
  const rows = activeTag ? calls.filter((c) => c.tag === activeTag) : calls;

  const answered = calls.filter((c) => c.answeredAt !== null).length;
  const ptp = calls.filter((c) => c.tag === "PTP").length;
  const notAnswered = calls.filter((c) => c.tag === "NSTD").length;

  return (
    <>
      <Heading />

      <section className="stats">
        <Stat value={total} label="Total panggilan" />
        <Stat value={answered} label={`Diangkat${total > LOADED ? ` (${LOADED} terakhir)` : ""}`} />
        <Stat value={ptp} label="Janji bayar (PTP)" />
        <Stat value={notAnswered} label="Tidak diangkat" />
      </section>

      <section className="card">
        <nav className="filters" aria-label="Filter hasil">
          <Link href="/" className={`filter${activeTag ? "" : " active"}`}>Semua</Link>
          {tagsPresent.map((t) => (
            <Link key={t} href={`/?tag=${t}`} className={`filter${activeTag === t ? " active" : ""}`}>
              {TAG_LABELS[t]}
            </Link>
          ))}
        </nav>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Waktu</th>
                <th>Nasabah</th>
                <th>Loan</th>
                <th>Status</th>
                <th>Hasil</th>
                <th>Tgl janji bayar</th>
                <th>Terverifikasi</th>
                <th>Durasi</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="empty">Belum ada panggilan.</td>
                </tr>
              ) : (
                rows.map((c) => (
                  <tr key={c.callId}>
                    <td><Link href={`/calls/${c.callId}`}>{formatDateTime(c.createdAt)}</Link></td>
                    <td>{c.customerName}</td>
                    <td>{c.externalLoanId ?? <span className="dash">—</span>}</td>
                    <td>{STATUS_LABELS[c.status]}</td>
                    <td><TagBadge tag={c.tag} /></td>
                    <td>{formatDate(c.ptpDate)}</td>
                    <td>{c.verified ? <span className="check">✓</span> : <span className="dash">—</span>}</td>
                    <td>{formatDuration(c.answeredAt, c.endedAt)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
      <AutoRefresh seconds={10} />
    </>
  );
}

function Heading() {
  return (
    <div className="page-heading">
      <div>
        <h1>Laporan Panggilan</h1>
        <p>Hasil panggilan penagihan oleh AI agent. Klik waktu panggilan untuk melihat transkrip.</p>
      </div>
      <span className="refresh-note">Diperbarui otomatis tiap 10 detik</span>
    </div>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

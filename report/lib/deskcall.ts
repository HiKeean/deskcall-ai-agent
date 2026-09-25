import "server-only";

// Klien deskcall API untuk server component saja: X-API-Key tidak pernah dikirim ke browser.
// Kontrak: docs/API.md

export type CallStatus = "CREATED" | "ANSWERED" | "ENDED" | "FAILED";
export type CallTag =
  | "NSTD" | "CBR" | "PTP" | "UNK" | "CBC_NO_DEAL" | "CBC_TITIP_PESAN" | "CBC_ATAS_NAMA"
  | "DSS" | "OTHERS" | "SHORT_TERM_CALLBACK" | "LONG_TERM_CALLBACK";

export interface CallEvent {
  type: string;
  detail: string | null;
  occurredAt: string;
}

export interface CallTurn {
  seq: number;
  speaker: "ai" | "customer";
  text: string;
  state: string | null;
}

export interface Call {
  callId: string;
  externalCustomerId: string | null;
  externalLoanId: string | null;
  customerName: string;
  status: CallStatus;
  tag: CallTag | null;
  verified: boolean;
  ptpDate: string | null;
  note: string | null;
  roomName: string;
  createdAt: string;
  answeredAt: string | null;
  endedAt: string | null;
  events: CallEvent[] | null;
  transcript: CallTurn[] | null;
}

export interface CallPage {
  items: Call[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
}

export class DeskcallError extends Error {}

async function get<T>(path: string): Promise<T> {
  const baseUrl = process.env.DESKCALL_API_URL ?? "http://localhost:8990";
  const apiKey = process.env.DESKCALL_API_KEY;
  if (!apiKey) throw new DeskcallError("DESKCALL_API_KEY belum diset di report/.env.local");

  let response: Response;
  try {
    response = await fetch(`${baseUrl.replace(/\/+$/, "")}/api/v1${path}`, {
      headers: { "X-API-Key": apiKey },
      cache: "no-store",
    });
  } catch {
    throw new DeskcallError(`deskcall API tidak bisa dihubungi di ${baseUrl}`);
  }
  if (response.status === 404) throw new DeskcallError("Panggilan tidak ditemukan");
  if (!response.ok) throw new DeskcallError(`deskcall API menjawab HTTP ${response.status}`);
  return (await response.json()) as T;
}

export function listCalls(params: { tag?: string; status?: string; size?: number }): Promise<CallPage> {
  const query = new URLSearchParams({ page: "0", size: String(params.size ?? 100) });
  if (params.tag) query.set("tag", params.tag);
  if (params.status) query.set("status", params.status);
  return get<CallPage>(`/calls?${query}`);
}

export function getCall(callId: string): Promise<Call> {
  return get<Call>(`/calls/${encodeURIComponent(callId)}?includeTranscript=true`);
}

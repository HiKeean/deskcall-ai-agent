import type { CallTag } from "@/lib/deskcall";
import { TAG_LABELS, tagTone } from "@/lib/format";

export function TagBadge({ tag }: { tag: CallTag | null }) {
  if (!tag) return <span className="badge tone-muted">Belum ada</span>;
  return <span className={`badge tone-${tagTone(tag)}`}>{TAG_LABELS[tag]}</span>;
}

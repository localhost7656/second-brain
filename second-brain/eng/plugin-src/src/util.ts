// Little things.: russian, date, summary, number-sampling.
import type { UiContainer, UiSnapshot } from "./types";

const STAT_NAMES: [string, string][] = [
  ["files", "files received"], ["items_classified", "files analyzed"], ["placed", "entries placed"],
  ["quarantined", "for review"], ["unsorted", "unassigned"], ["containers_created", "new containers"],
  ["compacted", "entries compacted"], ["aspects", "aspects extracted"], ["composites", "composites assembled"],
  ["duplicates", "duplicates linked"], ["bases", "synthesis bases assembled"], ["products", "documents written"],
  ["answers", "responses"],
];

export function statsLine(stats?: Record<string, number>): string {
  if (!stats) return "";
  return STAT_NAMES.filter(([k]) => stats[k]).map(([k, label]) => `${label}: ${stats[k]}`).join("; ");
}

export function callsLine(calls?: Record<string, number>): string {
  if (!calls) return "";
  const total = Object.values(calls).reduce((a, b) => a + b, 0);
  if (!total) return "";
  return `Model requests: ${total} (` + Object.entries(calls).map(([k, v]) => `${k} — ${v}`).join(", ") + ")";
}

export function plural(n: number, forms: [string, string, string]): string {
  return Math.abs(n) === 1 ? forms[0] : forms[2];
}

export const nQuestions = (n: number) => `${n} ${plural(n, ["question", "questions", "questions"])}`;
export const nRecords = (n: number) => `${n} ${plural(n, ["entry", "entries", "entries"])}`;
export const nCalls = (n: number) => `${n} ${plural(n, ["request", "requests", "requests"])}`;

export function duration(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h} h ${String(m).padStart(2, "0")} min`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

const pad = (n: number) => String(n).padStart(2, "0");

export function ruDateTime(iso?: string | null): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(iso);
  if (!m) return iso;
  return `${m[3]}.${m[2]}.${m[1]}` + (m[4] ? ` ${m[4]}:${m[5]}` : "");
}

export function clock(t: number): string {
  const d = new Date(t);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function nowHm(): string {
  const d = new Date();
  return `${pad(d.getHours())}-${pad(d.getMinutes())}`;
}

/** Number from the input field: «0,85» and «80%» Its good, too.; scale-wise 0–1 «86%» — it 0,86. undefined — empty, null — mistake. */
export function parseNumber(s: string, kind: string, min?: number, max?: number): number | null | undefined {
  const raw = s.trim().replace(",", ".");
  const pct = raw.endsWith("%");
  const t = raw.replace(/%$/, "").trim();
  if (!t) return undefined;
  let v = Number(t);
  if (!Number.isFinite(v)) return null;
  if (pct && kind !== "int" && max !== undefined && max <= 1) v = v / 100;
  if (kind === "int" && !Number.isInteger(v)) return null;
  if (min !== undefined && v < min) return null;
  if (max !== undefined && v > max) return null;
  return v;
}

export function rangeText(kind: string, min?: number, max?: number): string {
  const what = kind === "int" ? "integer" : "number";
  if (min !== undefined && max !== undefined) return `${what} from ${min} to ${max}`;
  return what;
}

/** Container Parent Chain: root-to-mortar. */
export function parentsOf(ui: UiSnapshot, c: UiContainer): UiContainer[] {
  const out: UiContainer[] = [];
  const seen = new Set<string>();
  let cur = c.parent_id ? ui.containers.find((x) => x.id === c.parent_id) : undefined;
  while (cur && !seen.has(cur.id)) {
    seen.add(cur.id);
    out.unshift(cur);
    cur = cur.parent_id ? ui.containers.find((x) => x.id === cur!.parent_id) : undefined;
  }
  return out;
}

export function containerLabel(ui: UiSnapshot, c: UiContainer): string {
  return [...parentsOf(ui, c).map((x) => x.title), c.title].join(" › ");
}

/** Container, file-holder: deepest folder of the container, inside. */
export function containerOfPath(ui: UiSnapshot | null, path: string): UiContainer | null {
  if (!ui) return null;
  let best: UiContainer | null = null;
  for (const c of ui.containers) {
    if (path === c.path || (c.folder && path.startsWith(c.folder + "/"))) {
      if (!best || c.folder.length > best.folder.length) best = c;
    }
  }
  return best;
}

export function baseName(p: string): string {
  const s = p.split("/").pop() || p;
  return s.replace(/\.md$/i, "");
}

/** Starting a Thought for a File Name: symbolless, which are not in file names. */
export function fileSlug(text: string, max = 40): string {
  const words = text.replace(/[\\/:*?"<>|#^[\]\r\n\t]+/g, " ").trim().split(/\s+/);
  let out = "";
  for (const w of words) {
    if ((out + " " + w).trim().length > max) break;
    out = (out + " " + w).trim();
  }
  return (out || words[0]?.slice(0, max) || "thought").replace(/[. ]+$/, "");
}

/** Local time in the form 2026-11-04T01:54:00 (non-translational UTC). */
export function localIso(d = new Date()): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// ---------- expense (v2.5) ----------
/** Money in dollars — programmatically: less — four-sign. */
export function money(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (v && Math.abs(v) < 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

/** Share of budget: «84%», huge — shorthand. */
export function pctText(p: number): string {
  return p > 999 ? "more 999%" : `${Math.round(p)}%`;
}

/** Whole with gaps between ranks: 1 234 567. */
export function num(x: number | null | undefined): string {
  return String(Math.round(x || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0");
}

/** Shortly.: 950, 12,3 thousand., 1,25 million. */
export function compact(x: number | null | undefined): string {
  const n = Math.round(x || 0);
  if (Math.abs(n) < 10000) return num(n);
  if (Math.abs(n) < 1e6) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}\u00a0thousand`;
  return `${(n / 1e6).toFixed(2).replace(/\.?0+$/, "")}\u00a0million`;
}

/** Duration of words, program-book: «42 s», «3 min 12 s», «1 h 05 min». */
export function durationText(sec: number | null | undefined): string {
  const s = Math.max(0, Math.round(sec || 0));
  if (s < 60) return `${s} s`;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h) return `${h} h ${String(m).padStart(2, "0")} min`;
  return `${m} min ${String(s % 60).padStart(2, "0")} s`;
}

/** How much is left? — crudely: «less», «≈ 12 min», «≈ 1,5 smack». */
export function etaText(ms: number): string {
  const m = ms / 60000;
  if (m < 1) return "less than a minute";
  if (m < 90) return `≈ ${Math.round(m)} min`;
  return `≈ ${(m / 60).toFixed(1)} h`;
}

export const PTYPE_RU: Record<string, string> = {
  cloud: "cloud", local: "local", webchat: "web chat", fake: "test",
};

/** Flow line: «14 conversion · token 12,3 thousand. → 2 thousand. · $0.03». */
export function usageLine(t: { calls: number; in: number; out: number; cached?: number; cost: number; unpriced?: number; sec?: number }, o: { cost?: boolean; time?: boolean } = {}): string {
  if (!t || !t.calls) return "No requests.";
  const parts = [nCalls(t.calls)];
  if (t.in || t.out) parts.push(`tokens ${compact(t.in)} → ${compact(t.out)}` + (t.cached ? ` (cached ${compact(t.cached)})` : ""));
  if (o.cost !== false && (t.cost || (o.cost && !t.unpriced))) parts.push(money(t.cost) + (t.unpriced ? "*" : ""));
  if (o.time && t.sec) parts.push(`model time ${durationText(t.sec)}`);
  return parts.join(" · ");
}

/** File size: «6,9 GB», «25 MB» (programmatically — decimal, like Hugging Face). */
export function sizeText(bytes: number | null | undefined): string {
  const b = Math.max(0, bytes || 0);
  if (b >= 1e9) return `${(b / 1e9).toFixed(1)} GB`;
  return `${Math.max(1, Math.round(b / 1e6))} MB`;
}

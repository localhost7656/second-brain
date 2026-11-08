// Мелочи: русские числительные, даты, сводка итогов, разбор чисел.
import type { UiContainer, UiSnapshot } from "./types";

const STAT_NAMES: [string, string][] = [
  ["files", "принято файлов"], ["items_classified", "разобрано файлов"], ["placed", "записей разложено"],
  ["quarantined", "на проверку"], ["unsorted", "без контейнера"], ["containers_created", "новых контейнеров"],
  ["compacted", "уплотнено"], ["aspects", "аспектов извлечено"], ["composites", "составных собрано"],
  ["duplicates", "дублей связано"], ["bases", "баз синтеза собрано"], ["products", "документов написано"],
  ["answers", "ответов принято"],
];

export function statsLine(stats?: Record<string, number>): string {
  if (!stats) return "";
  return STAT_NAMES.filter(([k]) => stats[k]).map(([k, label]) => `${label}: ${stats[k]}`).join("; ");
}

export function callsLine(calls?: Record<string, number>): string {
  if (!calls) return "";
  const total = Object.values(calls).reduce((a, b) => a + b, 0);
  if (!total) return "";
  return `Обращений к модели: ${total} (` + Object.entries(calls).map(([k, v]) => `${k} — ${v}`).join(", ") + ")";
}

export function plural(n: number, forms: [string, string, string]): string {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return forms[2];
  if (b > 1 && b < 5) return forms[1];
  if (b === 1) return forms[0];
  return forms[2];
}

export const nQuestions = (n: number) => `${n} ${plural(n, ["вопрос", "вопроса", "вопросов"])}`;
export const nRecords = (n: number) => `${n} ${plural(n, ["запись", "записи", "записей"])}`;
export const nCalls = (n: number) => `${n} ${plural(n, ["обращение", "обращения", "обращений"])}`;

export function duration(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h} ч ${String(m).padStart(2, "0")} мин`;
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

/** Число из поля ввода: «0,85» и «80%» тоже годятся; для шкалы 0–1 «86%» — это 0,86. undefined — пусто, null — ошибка. */
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
  const what = kind === "int" ? "целое число" : "число";
  if (min !== undefined && max !== undefined) return `${what} от ${min} до ${max}`;
  return what;
}

/** Цепочка родителей контейнера: от корня к ближайшему. */
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

/** Контейнер, которому принадлежит файл: самая глубокая папка контейнера, внутри которой он лежит. */
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

/** Начало мысли для имени файла: без символов, которые нельзя в именах файлов. */
export function fileSlug(text: string, max = 40): string {
  const words = text.replace(/[\\/:*?"<>|#^[\]\r\n\t]+/g, " ").trim().split(/\s+/);
  let out = "";
  for (const w of words) {
    if ((out + " " + w).trim().length > max) break;
    out = (out + " " + w).trim();
  }
  return (out || words[0]?.slice(0, max) || "мысль").replace(/[. ]+$/, "");
}

/** Местное время в виде 2026-11-04T01:54:00 (без перевода в UTC). */
export function localIso(d = new Date()): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// ---------- расходы и время (v2.5) ----------
/** Деньги в долларах — как в программе: меньше цента — четыре знака. */
export function money(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (v && Math.abs(v) < 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

/** Доля бюджета: «84%», огромные — коротко. */
export function pctText(p: number): string {
  return p > 999 ? "больше 999%" : `${Math.round(p)}%`;
}

/** Целое с пробелами между разрядами: 1 234 567. */
export function num(x: number | null | undefined): string {
  return String(Math.round(x || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0");
}

/** Коротко: 950, 12,3 тыс., 1,25 млн. */
export function compact(x: number | null | undefined): string {
  const n = Math.round(x || 0);
  if (Math.abs(n) < 10000) return num(n);
  if (Math.abs(n) < 1e6) return `${(n / 1000).toFixed(1).replace(".", ",").replace(/,0$/, "")}\u00a0тыс.`;
  return `${(n / 1e6).toFixed(2).replace(".", ",").replace(/,?0+$/, "")}\u00a0млн`;
}

/** Длительность словами, как в журнале программы: «42 с», «3 мин 12 с», «1 ч 05 мин». */
export function durationText(sec: number | null | undefined): string {
  const s = Math.max(0, Math.round(sec || 0));
  if (s < 60) return `${s} с`;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h) return `${h} ч ${String(m).padStart(2, "0")} мин`;
  return `${m} мин ${String(s % 60).padStart(2, "0")} с`;
}

/** Сколько осталось — грубо: «меньше минуты», «≈ 12 мин», «≈ 1,5 ч». */
export function etaText(ms: number): string {
  const m = ms / 60000;
  if (m < 1) return "меньше минуты";
  if (m < 90) return `≈ ${Math.round(m)} мин`;
  return `≈ ${(m / 60).toFixed(1).replace(".", ",")} ч`;
}

export const PTYPE_RU: Record<string, string> = {
  cloud: "облачная", local: "локальная", webchat: "веб-чат", fake: "тестовая",
};

/** Строка расхода: «14 обращений · токенов 12,3 тыс. → 2 тыс. · $0.03». */
export function usageLine(t: { calls: number; in: number; out: number; cached?: number; cost: number; unpriced?: number; sec?: number }, o: { cost?: boolean; time?: boolean } = {}): string {
  if (!t || !t.calls) return "обращений не было";
  const parts = [nCalls(t.calls)];
  if (t.in || t.out) parts.push(`токенов ${compact(t.in)} → ${compact(t.out)}` + (t.cached ? ` (из кэша ${compact(t.cached)})` : ""));
  if (o.cost !== false && (t.cost || (o.cost && !t.unpriced))) parts.push(money(t.cost) + (t.unpriced ? "*" : ""));
  if (o.time && t.sec) parts.push(`модель работала ${durationText(t.sec)}`);
  return parts.join(" · ");
}

/** Размер файла: «6,9 ГБ», «25 МБ» (как в программе — десятичные гигабайты, как на Hugging Face). */
export function sizeText(bytes: number | null | undefined): string {
  const b = Math.max(0, bytes || 0);
  if (b >= 1e9) return `${(b / 1e9).toFixed(1).replace(".", ",")} ГБ`;
  return `${Math.max(1, Math.round(b / 1e6))} МБ`;
}

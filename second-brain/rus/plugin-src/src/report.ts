// Ошибки самого плагина: показать на месте («Скопировать отчёт»), записать в _логи/плагин.log
// и собрать «Отчёт для разработчика» — всё, что нужно, чтобы разобраться без доступа к компьютеру.
import { Notice, Platform, TFile, apiVersion } from "obsidian";
import * as os from "os";
import type BrainPlugin from "./main";

export interface PluginErrorRec {
  at: string;
  where: string;
  message: string;
  stack: string;
}

const KEEP = 30;
const LOG_MAX = 512 * 1024;

/** Текст ошибки. Ошибка из другого окна Obsidian (окно настроек) — не instanceof Error этого окна: смотрим поля. */
export function errParts(e: unknown): { message: string; stack: string } {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const x = e as any;
  if (x && typeof x === "object" && ("message" in x || "stack" in x)) {
    return { message: String(x.message || x.name || "ошибка"), stack: String(x.stack || "") };
  }
  return { message: String(e), stack: "" };
}

const pad = (n: number) => String(n).padStart(2, "0");
const stamp = (d = new Date()) =>
  `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

export const LOG_FILE = "_логи/плагин.log";

export class ErrorLog {
  items: PluginErrorRec[] = [];
  private chain: Promise<void> = Promise.resolve();
  constructor(private plugin: BrainPlugin) {}

  /** quiet — ошибку уже вывел в консоль сам Obsidian (неперехваченная). */
  add(where: string, e: unknown, quiet = false): PluginErrorRec {
    const { message, stack } = errParts(e);
    const rec = { at: stamp(), where, message, stack };
    // одна и та же ошибка подряд (перерисовка раз в секунду) — не размножать
    const last = this.items[0];
    if (last && last.where === where && last.message === message) return last;
    this.items.unshift(rec);
    if (this.items.length > KEEP) this.items.pop();
    if (!quiet) console.error(`Второй мозг (${where}):`, e);
    const entry = `\n===== ${rec.at} · ${where} · плагин ${this.plugin.manifest.version}\n${message}\n${stack}\n`;
    this.chain = this.chain.then(() => this.write(entry)).catch(() => undefined); // журнал — не главное
    return rec;
  }

  /** Запись в _логи/плагин.log хранилища (больше 512 КБ — прежний журнал становится плагин.log.old). */
  private async write(entry: string) {
    const a = this.plugin.app.vault.adapter;
    if (!(await a.exists("_логи"))) await a.mkdir("_логи");
    const st = await a.stat(LOG_FILE);
    if (st && st.size > LOG_MAX) {
      const old = LOG_FILE + ".old";
      if (await a.exists(old)) await a.remove(old);
      await a.rename(LOG_FILE, old);
    }
    if (await a.exists(LOG_FILE)) await a.append(LOG_FILE, entry);
    else await a.write(LOG_FILE, entry);
  }
}

export function versionLines(plugin: BrainPlugin): string[] {
  return [
    `Плагин: ${plugin.manifest.version}`,
    `Программа: ${plugin.ui?.program || "?"}`,
    `Obsidian: ${apiVersion}`,
    `Система: ${Platform.isWin ? "Windows" : Platform.isMacOS ? "macOS" : "Linux"} ${os.release()} (${process.arch})`,
  ];
}

/** В буфер обмена: через Electron (работает, даже если окно не в фокусе), иначе — через браузерный API. */
export async function copyText(text: string): Promise<boolean> {
  // сначала обычный буфер обмена браузера; Electron — запасной путь (его clipboard из окна Obsidian устаревает)
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    /* окно не в фокусе или нет доступа */
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { clipboard } = require("electron");
    if (clipboard?.writeText) {
      clipboard.writeText(text);
      return true;
    }
  } catch {
    /* не настольный Obsidian */
  }
  return false;
}

function recText(r: PluginErrorRec): string {
  return `[${r.at}] ${r.where}: ${r.message}\n${r.stack}`.trim();
}

/** Короткий отчёт об одной ошибке — для кнопки «Скопировать отчёт». */
export function errorReport(plugin: BrainPlugin, rec: PluginErrorRec): string {
  return ["Второй мозг — ошибка плагина", ...versionLines(plugin), "", recText(rec)].join("\n");
}

/** Ошибка вместо содержимого: что сломалось и кнопка «Скопировать отчёт». */
export function renderError(el: HTMLElement, plugin: BrainPlugin, where: string, e: unknown) {
  const rec = plugin.errors.add(where, e);
  const box = el.createDiv({ cls: "vm-callout is-bad vm-error-box" });
  box.createDiv({ cls: "vm-callout-title", text: `Ошибка в плагине (${where})` });
  box.createDiv({ text: rec.message });
  box.createDiv({
    cls: "vm-small-text vm-muted",
    text: `Остальное работает. Подробности записаны в ${LOG_FILE} — нажмите «Скопировать отчёт» и пришлите его разработчику.`,
  });
  const row = box.createDiv({ cls: "vm-buttons" });
  const b = row.createEl("button", { text: "Скопировать отчёт" });
  b.addEventListener("click", async () => {
    const ok = await copyText(errorReport(plugin, rec));
    new Notice(ok ? "Отчёт скопирован — вставьте его в сообщение разработчику." : `Не удалось скопировать — отчёт есть в файле ${LOG_FILE}.`);
  });
}

/** Конец файла хранилища (журнала программы). */
async function tail(plugin: BrainPlugin, rel: string, max: number): Promise<string> {
  try {
    const a = plugin.app.vault.adapter;
    if (!(await a.exists(rel))) return "";
    const text = await a.read(rel);
    return text.length > max ? text.slice(text.length - max) : text;
  } catch {
    return "";
  }
}

/** «Отчёт для разработчика»: версии, ошибки плагина и программы, вывод последних запусков. Ключей и текстов заметок в нём нет. */
export async function developerReport(plugin: BrainPlugin): Promise<string> {
  const out: string[] = ["# Второй мозг — отчёт для разработчика", "", `Собран: ${stamp()}`, "", ...versionLines(plugin).map((x) => `- ${x}`)];
  const problem = plugin.engine.problem();
  out.push(`- Папка программы: ${plugin.engine.programDir() || "не указана"}${problem ? ` — ${problem}` : ""}`);
  out.push("", "## Ошибки плагина (последние)", "");
  if (plugin.errors.items.length) out.push("```", ...plugin.errors.items.slice(0, 10).map(recText), "```");
  else out.push("Нет.");
  const progErr = await tail(plugin, "_логи/ошибки.log", 6000);
  out.push("", "## Ошибки программы (конец _логи/ошибки.log)", "", progErr ? "```\n" + progErr.trim() + "\n```" : "Нет.");
  out.push("", "## Последние запуски", "");
  const jobs = plugin.engine.history.slice(0, 3);
  if (!jobs.length) out.push("В этом сеансе Obsidian запусков не было.");
  for (const j of jobs) {
    out.push(`### ${j.label} — ${j.status}`, "", "```", ...j.lines.slice(-40), ...(j.stderr ? ["--- stderr ---", j.stderr.slice(-3000)] : []), "```", "");
  }
  return out.join("\n");
}

/** Собрать отчёт: файл _логи/отчёт для разработчика.md (открывается) и копия в буфере обмена. */
export async function saveDeveloperReport(plugin: BrainPlugin): Promise<void> {
  const text = await developerReport(plugin);
  const copied = await copyText(text);
  const rel = "_логи/отчёт для разработчика.md";
  const vault = plugin.app.vault;
  try {
    if (!vault.getAbstractFileByPath("_логи") && !(await vault.adapter.exists("_логи"))) await vault.createFolder("_логи");
    const cur = vault.getAbstractFileByPath(rel);
    let file: TFile | null = null;
    if (cur instanceof TFile) {
      await vault.modify(cur, text);
      file = cur;
    } else {
      try {
        file = await vault.create(rel, text);
      } catch {
        await vault.adapter.write(rel, text); // файл уже на диске, Obsidian его ещё не увидел
      }
    }
    if (file) await plugin.app.workspace.getLeaf(true).openFile(file);
  } catch (e) {
    plugin.errors.add("отчёт для разработчика", e);
  }
  new Notice(copied ? "Отчёт собран и скопирован — вставьте его в сообщение разработчику." : `Отчёт собран: ${rel}`, 8000);
}

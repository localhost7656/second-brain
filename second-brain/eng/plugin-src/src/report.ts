// Errors of the plugin itself: point out («Copy the report.»), write down _logs/plugin.log
// collect «Developer report» — everything, need, to sort out without access to a computer.
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

/** Text error. The mistake from the other window Obsidian (settings-box) — not instanceof Error window: gaze. */
export function errParts(e: unknown): { message: string; stack: string } {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const x = e as any;
  if (x && typeof x === "object" && ("message" in x || "stack" in x)) {
    return { message: String(x.message || x.name || "mistake"), stack: String(x.stack || "") };
  }
  return { message: String(e), stack: "" };
}

const pad = (n: number) => String(n).padStart(2, "0");
const stamp = (d = new Date()) =>
  `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

export const LOG_FILE = "_logs/plugin.log";

export class ErrorLog {
  items: PluginErrorRec[] = [];
  private chain: Promise<void> = Promise.resolve();
  constructor(private plugin: BrainPlugin) {}

  /** quiet — The error has already been brought to the console itself. Obsidian (intercepted). */
  add(where: string, e: unknown, quiet = false): PluginErrorRec {
    const { message, stack } = errParts(e);
    const rec = { at: stamp(), where, message, stack };
    // same mistake in a row (per-second) — breed out
    const last = this.items[0];
    if (last && last.where === where && last.message === message) return last;
    this.items.unshift(rec);
    if (this.items.length > KEEP) this.items.pop();
    if (!quiet) console.error(`Second Brain (${where}):`, e);
    const entry = `\n===== ${rec.at} · ${where} · plugin ${this.plugin.manifest.version}\n${message}\n${stack}\n`;
    this.chain = this.chain.then(() => this.write(entry)).catch(() => undefined); // journal — primary
    return rec;
  }

  /** Record in _logs/plugin.log storage (more 512 CBB — The old journal becomes a plugin.log.old). */
  private async write(entry: string) {
    const a = this.plugin.app.vault.adapter;
    if (!(await a.exists("_logs"))) await a.mkdir("_logs");
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
    `Plugin: ${plugin.manifest.version}`,
    `Program: ${plugin.ui?.program || "?"}`,
    `Obsidian: ${apiVersion}`,
    `System: ${Platform.isWin ? "Windows" : Platform.isMacOS ? "macOS" : "Linux"} ${os.release()} (${process.arch})`,
  ];
}

/** In the exchange buffer: through Electron (work, even if the window is out of focus), otherwise — browser-based API. */
export async function copyText(text: string): Promise<boolean> {
  // First, the usual browser clipboard; Electron — escape (his clipboard window Obsidian obsolete)
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    /* window is out of focus or no access */
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { clipboard } = require("electron");
    if (clipboard?.writeText) {
      clipboard.writeText(text);
      return true;
    }
  } catch {
    /* non-desktop Obsidian */
  }
  return false;
}

function recText(r: PluginErrorRec): string {
  return `[${r.at}] ${r.where}: ${r.message}\n${r.stack}`.trim();
}

/** A brief report of one mistake — button «Copy the report.». */
export function errorReport(plugin: BrainPlugin, rec: PluginErrorRec): string {
  return ["Second Brain — plugin error", ...versionLines(plugin), "", recText(rec)].join("\n");
}

/** Error instead of content: Whats broken and the button? «Copy the report.». */
export function renderError(el: HTMLElement, plugin: BrainPlugin, where: string, e: unknown) {
  const rec = plugin.errors.add(where, e);
  const box = el.createDiv({ cls: "vm-callout is-bad vm-error-box" });
  box.createDiv({ cls: "vm-callout-title", text: `Error in the plugin (${where})` });
  box.createDiv({ text: rec.message });
  box.createDiv({
    cls: "vm-small-text vm-muted",
    text: `The rest of the plugin is still working. Details are saved in ${LOG_FILE}. Copy the report and share it with the developer.`,
  });
  const row = box.createDiv({ cls: "vm-buttons" });
  const b = row.createEl("button", { text: "Copy report" });
  b.addEventListener("click", async () => {
    const ok = await copyText(errorReport(plugin, rec));
    new Notice(ok ? "Report copied. Paste it into a message to the developer." : `Could not copy the report. Details are in ${LOG_FILE}.`);
  });
}

/** End of the storage file (journal). */
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

/** «Developer report»: version, plugin and program errors, finalization. There are no keys or notes in it.. */
export async function developerReport(plugin: BrainPlugin): Promise<string> {
  const out: string[] = ["# Second Brain — developer report", "", `Created: ${stamp()}`, "", ...versionLines(plugin).map((x) => `- ${x}`)];
  const problem = plugin.engine.problem();
  out.push(`- Program folder: ${plugin.engine.programDir() || "not listed"}${problem ? ` — ${problem}` : ""}`);
  out.push("", "## Plugin errors (last)", "");
  if (plugin.errors.items.length) out.push("```", ...plugin.errors.items.slice(0, 10).map(recText), "```");
  else out.push("None.");
  const progErr = await tail(plugin, "_logs/mistake.log", 6000);
  out.push("", "## Program errors (ending _logs/mistake.log)", "", progErr ? "```\n" + progErr.trim() + "\n```" : "None.");
  out.push("", "## Latest launches", "");
  const jobs = plugin.engine.history.slice(0, 3);
  if (!jobs.length) out.push("No runs in this Obsidian session.");
  for (const j of jobs) {
    out.push(`### ${j.label} — ${j.status}`, "", "```", ...j.lines.slice(-40), ...(j.stderr ? ["--- stderr ---", j.stderr.slice(-3000)] : []), "```", "");
  }
  return out.join("\n");
}

/** Collect a report: file _logs/developer-report.md (open) and a clipboard. */
export async function saveDeveloperReport(plugin: BrainPlugin): Promise<void> {
  const text = await developerReport(plugin);
  const copied = await copyText(text);
  const rel = "_logs/developer-report.md";
  const vault = plugin.app.vault;
  try {
    if (!vault.getAbstractFileByPath("_logs") && !(await vault.adapter.exists("_logs"))) await vault.createFolder("_logs");
    const cur = vault.getAbstractFileByPath(rel);
    let file: TFile | null = null;
    if (cur instanceof TFile) {
      await vault.modify(cur, text);
      file = cur;
    } else {
      try {
        file = await vault.create(rel, text);
      } catch {
        await vault.adapter.write(rel, text); // files already on disk, Obsidian I havent seen him yet.
      }
    }
    if (file) await plugin.app.workspace.getLeaf(true).openFile(file);
  } catch (e) {
    plugin.errors.add("developer-report", e);
  }
  new Notice(copied ? "Report collected and copied. Paste it into a message to the developer." : `Report collected: ${rel}`, 8000);
}

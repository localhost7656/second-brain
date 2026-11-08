// Plugin «Second Brain»: panel, commands and settings on top of the program Python.
import { MarkdownView, Notice, Plugin, TFile } from "obsidian";
import * as fs from "fs";
import * as path from "path";
import { Engine, Job, liveInfo, manualMode } from "./engine";
import { AdviceModal, CheckModal, ContainerPicker, NewThoughtModal, TextModal, askOptions, choiceModal, confirmModal, thoughtFile } from "./modals";
import { ErrorLog, errParts, saveDeveloperReport } from "./report";
import { BrainSettingTab } from "./settings";
import type { Advice, AskEvent, LlamaParams, LlamaStatus, RunResult, UiContainer, UiQuestion, UiSnapshot, UpdateInfo } from "./types";
import { baseName, containerOfPath, duration, durationText, localIso, money, nQuestions, statsLine } from "./util";
import { BrainView, Tab, VIEW_TYPE } from "./view";

export interface PluginData {
  programDir: string;
  pythonPath: string;
  welcomed: boolean;
  /** notice Windows */
  notify: boolean;
  notifyMinutes: number; // «long-run» — longer
  notifyAsk: boolean; // program awaits a response
  notifyUnfocused: boolean; // only when the window Obsidian out-of-focus
  /** version, Which the user decided to miss */
  skipVersion: string;
}

const DEFAULTS: PluginData = {
  programDir: "", pythonPath: "", welcomed: false,
  notify: true, notifyMinutes: 2, notifyAsk: true, notifyUnfocused: true, skipVersion: "",
};
/** team, Who can ask in the middle of a launch? (budget, big-start) */
const INTERACTIVE = new Set(["run", "synth", "revalidate", "patterns", "advise", "answer"]);

/** a new b? Comparison of numbers: 2.10.0 > 2.9.1. */
export function newerVersion(a?: string | null, b?: string | null): boolean {
  const ta = String(a || "").match(/\d+/g)?.slice(0, 4).map(Number) || [0];
  const tb = String(b || "").match(/\d+/g)?.slice(0, 4).map(Number) || [0];
  for (let i = 0; i < Math.max(ta.length, tb.length); i++) {
    const x = ta[i] || 0;
    const y = tb[i] || 0;
    if (x !== y) return x > y;
  }
  return false;
}
const UI_FILE = ".system/ui.json";
const APPROVE = "Structure approved";

export default class BrainPlugin extends Plugin {
  data: PluginData = { ...DEFAULTS };
  engine!: Engine;
  /** Errors of the plugin itself: _logs/plugin.log and «Developer report» */
  errors!: ErrorLog;
  ui: UiSnapshot | null = null;
  snapshotError: string | null = null;
  views = new Set<BrainView>();
  advice = new Map<string, { advice: Advice; at: string }>();
  lastWebchat: { label: string; args: string[] } | null = null;
  private uiMtime = 0;
  private statusEl: HTMLElement | null = null;
  // not settingTab: name Obsidian inside Plugin
  private brainTab!: BrainSettingTab;

  async onload() {
    this.errors = new ErrorLog(this);
    this.catchErrors();
    this.data = Object.assign({}, DEFAULTS, await this.loadData());
    this.engine = new Engine(this);
    this.engine.onChange = () => this.refresh();
    this.engine.onLine = () => {
      for (const v of this.views) v.progress();
    };
    this.engine.onLive = () => {
      for (const v of this.views) v.progress();
      this.updateStatus();
    };
    this.engine.onNotice = (job, text) => {
      new Notice(`${job.label}: ${text}`, 12000);
      this.osNotify("Second Brain", text, "notice");
    };
    this.engine.onAsk = (job, ask) => this.askUser(job, ask);
    this.registerView(VIEW_TYPE, (leaf) => new BrainView(leaf, this));
    this.addRibbonIcon("brain", "Second Brain", () => this.openView());
    this.statusEl = this.addStatusBarItem();
    this.statusEl.addClass("vm-statusbar", "mod-clickable");
    this.registerDomEvent(this.statusEl, "click", () => this.openView());
    this.addCommands();
    this.brainTab = new BrainSettingTab(this.app, this);
    this.addSettingTab(this.brainTab);
    this.app.workspace.onLayoutReady(() => this.start());
  }

  onunload() {
    this.engine.dispose();
  }

  /** Unintercepted errors of the plugin code (Obsidian sign it as «plugin:<id>») — into _logs/plugin.log. */
  private catchErrors() {
    const mark = "plugin:" + encodeURIComponent(this.manifest.id);
    const mine = (e: unknown, file?: string) => errParts(e).stack.includes(mark) || String(file || "").includes(mark);
    this.registerDomEvent(window, "error", (ev: ErrorEvent) => {
      if (mine(ev.error, ev.filename)) this.errors.add("Unhandled error", ev.error || ev.message, true);
    });
    this.registerDomEvent(window, "unhandledrejection", (ev: PromiseRejectionEvent) => {
      if (mine(ev.reason)) this.errors.add("Unhandled error", ev.reason, true);
    });
  }

  private async start() {
    await this.readSnapshot(true);
    this.refresh();
    if (!this.data.welcomed) {
      this.data.welcomed = true;
      await this.saveData(this.data);
      this.openView();
    }
    if (!this.engine.problem()) await this.refreshState(true);
    this.registerInterval(window.setInterval(() => this.readSnapshot(false), 3000));
    this.registerInterval(window.setInterval(() => this.updateStatus(), 1000));
    window.setTimeout(() => this.startupChecks(), 3000);
  }

  // ---------- update ----------
  /** At launch. Obsidian: new version of the plugin in the program folder? new version of the program GitHub? */
  private async startupChecks() {
    if (this.engine.problem()) return;
    try {
      if (await this.offerPluginFromProgram()) return;
      const u = this.ui?.updates;
      if (u?.repo && u.check_on_start) await this.checkUpdates(false);
    } catch (e) {
      console.warn("Second Brain: checking for updates", e);
    }
  }

  /** Plugin version, file (It is placed there by updating or unpacking a new archive.). */
  async programPluginVersion(): Promise<string | null> {
    const dir = this.engine.programDir();
    if (!dir) return null;
    try {
      const raw = await fs.promises.readFile(path.join(dir, "plugin", "manifest.json"), "utf8");
      return String(JSON.parse(String(raw)).version || "") || null;
    } catch {
      return null;
    }
  }

  /** In the program folder, the plugin is newer than the installed — offer to put it in storage. */
  private async offerPluginFromProgram(): Promise<boolean> {
    const v = await this.programPluginVersion();
    if (!v || !newerVersion(v, this.manifest.version)) return false;
    const ch = await choiceModal(this.app, {
      title: "New version of the plugin",
      text: `The program folder contains plugin version ${v}; Obsidian is running ${this.manifest.version}. Install the new version? Plugin settings will be preserved. Obsidian must be restarted afterward.`,
      options: [{ label: "Install", kind: "cta" }, { label: "Later" }],
    }).result;
    if (ch !== 0) return true;
    const r = await this.engine.run(["install-plugin", this.engine.vaultPath()], { label: "Installing plugin" });
    if (!r.ok) {
      new Notice(`Plugin not installed: ${r.error || "error"}`, 15000);
      return true;
    }
    await this.offerRestart(`Plugin ${v} installed.`);
    return true;
  }

  /** Check the new version of the program on GitHub; manual — button-button (report «last»). */
  async checkUpdates(manual: boolean): Promise<void> {
    const prob = this.engine.problem();
    if (prob) {
      if (manual) new Notice(prob, 10000);
      return;
    }
    const r = await this.engine.run(["update", "--check"], { label: "Checking for updates", exclusive: false, quiet: true });
    if (!r.ok || !r.update) {
      if (manual) new Notice(`Verification of updates: ${r.error || "program did not respond"}`, 12000);
      else console.warn("Second Brain: checking for updates —", r.error);
      return;
    }
    const u = r.update;
    if (!u.newer) {
      if (manual) new Notice(`The latest version has been installed: ${u.current} (repository ${u.repo} — ${u.version || "?"}).`, 8000);
      return;
    }
    if (!manual && this.data.skipVersion && this.data.skipVersion === u.version) return;
    const notes = (u.notes || "").split("\n").slice(0, 40).join("\n").trim();
    const from = u.source === "release" ? `release ${u.tag || u.version}` : `branch ${u.branch || "main"}`;
    const ch = await choiceModal(this.app, {
      title: `New version available: ${u.version}`,
      sub: `${u.repo} · ${from}`,
      text: `Currently installed: ${u.current}. The update replaces program and plugin files; settings, keys, and the vault are unchanged. If modified prompts differ from the new version, your copies will be saved in prompts/_former.`,
      pre: notes || undefined,
      options: [{ label: "Install", kind: "cta" }, { label: "Later" }, { label: "Skip this version" }],
    }).result;
    if (ch === 2) {
      this.data.skipVersion = u.version || "";
      await this.saveData(this.data);
      new Notice(`Version ${u.version} skipped. To check manually, open Settings → Second Brain → Updates.`, 8000);
    } else if (ch === 0) await this.installUpdate(u);
  }

  async installUpdate(u: UpdateInfo) {
    if (this.engine.busy()) new Notice("The update will start after the current run.", 6000);
    const r = await this.engine.run(["update", "--yes"], { label: `Update to ${u.version}` });
    if (!r.ok) {
      new Notice(`Update not installed: ${r.error || "error"}`, 15000);
      return;
    }
    const inst = r.installed;
    if (!inst) {
      new Notice(r.title || "Nothing to update.", 8000);
      return;
    }
    await this.refreshState(true);
    const lines = [`Files updated: ${inst.updated}, added: ${inst.added}` + (inst.removed.length ? `, obsolete: ${inst.removed.length}` : "") + "."];
    for (const n of inst.notes || []) lines.push(n);
    if (r.restart) await this.offerRestart(`Version ${inst.version} installed.`, lines);
    else
      await choiceModal(this.app, {
        title: `Version ${inst.version} installed`, lines,
        text: "The plugin was not found in this vault. If it is installed in another vault, run Install.bat and select this one.",
        options: [{ label: "Done", kind: "cta" }],
      }).result;
  }

  /** Window. «restart Obsidian» — The new plugin will work after restarting. */
  async offerRestart(title: string, lines?: string[]) {
    const ch = await choiceModal(this.app, {
      title, lines,
      text: "Restart Obsidian to use the new plugin. Open notes have been saved.",
      options: [{ label: "Restart Obsidian", kind: "cta" }, { label: "Later" }],
    }).result;
    if (ch === 0) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const cmds = (this.app as any).commands;
      if (!cmds?.executeCommandById?.("app:reload")) window.location.reload();
    }
  }

  // ---------- Questions in the midst of launch and notification Windows ----------
  private askUser(job: Job, ask: AskEvent): Promise<number | null> {
    this.osNotify("Second Brain is waiting for an answer", `${job.label}: ${ask.title}`, "ask");
    const m = choiceModal(this.app, { ...askOptions(ask), sub: job.label });
    job.askCancel = m.close;
    this.refresh();
    return m.result;
  }

  /** What?-window Obsidian now in focus: principal, tab-window, settings-box (Obsidian 1.15+). */
  obsidianFocused(): boolean {
    const docs = new Set<Document>([document]);
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const ad = (window as any).activeDocument as Document | undefined;
      if (ad) docs.add(ad);
      const sd = this.brainTab?.containerEl?.ownerDocument;
      if (sd) docs.add(sd);
      this.app.workspace.iterateAllLeaves((leaf) => {
        const d = leaf.view?.containerEl?.ownerDocument;
        if (d) docs.add(d);
      });
    } catch {
      /* old-fashioned Obsidian — main window */
    }
    for (const d of docs) {
      try {
        if (d.hasFocus()) return true;
      } catch {
        /* window is already closed */
      }
    }
    return false;
  }

  /** Notification Windows (systemic). force — check-up: conditionally. */
  osNotify(title: string, body: string, kind: "done" | "ask" | "notice", force = false): boolean {
    const d = this.data;
    if (!force) {
      if (!d.notify) return false;
      if (kind === "ask" && !d.notifyAsk) return false;
      if (d.notifyUnfocused && this.obsidianFocused()) return false;
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const N = (window as any).Notification;
    if (typeof N !== "function") return false;
    try {
      const n = new N(title, { body, silent: kind === "notice" });
      n.onclick = () => {
        try {
          window.focus();
        } catch {
          /* window ahead */
        }
        this.openView();
      };
      return true;
    } catch (e) {
      console.warn("Second Brain: notification not shown", e);
      return false;
    }
  }

  /** Long launch over — notify (window Obsidian could have been rolled up). */
  private doneNotify(label: string, r: RunResult, sec: number) {
    if (r.cancelled) return; // cancel out, question-window, — nothing
    if (sec < Math.max(0, this.data.notifyMinutes) * 60) return;
    let body: string;
    if (r.webchat) body = "Waiting for a web chat response; see the panel.";
    else if (r.budget_stop) body = "Stopped.: budget exhausted.";
    else if (r.stopped) body = "Stopped. All processed items are saved.";
    else if (!r.ok) body = `Mistake.: ${r.error || "see panel"}`;
    else {
      const sl = statsLine(r.stats);
      body = `${r.title || "Done"} after ${durationText(sec)}` + (sl ? `: ${sl}` : "") + (r.run_usage?.cost ? ` · ${money(r.run_usage.cost)}` : "") + ".";
      if (r.questions) body += ` Questions: ${r.questions}.`;
    }
    this.osNotify(`Second Brain · ${label}`, body, "done");
  }

  // ---------- condition ----------
  async readSnapshot(force: boolean) {
    const a = this.app.vault.adapter;
    try {
      const st = await a.stat(UI_FILE);
      if (!st) {
        if (this.ui) {
          this.ui = null;
          this.refresh();
        }
        return;
      }
      if (!force && st.mtime === this.uiMtime) return;
      const raw = await a.read(UI_FILE);
      this.ui = JSON.parse(raw) as UiSnapshot;
      this.uiMtime = st.mtime;
      this.refresh();
    } catch (e) {
      console.warn("Second Brain: failed to read .system/ui.json", e);
    }
  }

  /** Ask the program to recalculate the state picture (modelless). */
  async refreshState(force = false) {
    const r = await this.engine.snapshot();
    this.snapshotError = r.ok ? null : r.error || "program did not respond";
    await this.readSnapshot(force);
    this.refresh();
  }

  refresh() {
    this.updateStatus();
    for (const v of this.views) v.render();
  }

  private updateStatus() {
    const el = this.statusEl;
    if (!el) return;
    const prob = this.engine.problem();
    const job = this.engine.active();
    if (prob) {
      el.setText("Second Brain: program not found");
      el.setAttr("title", prob);
    } else if (job) {
      const manual = manualMode(this.ui); // web-based-chat: timelessly «left»
      const t = job.startedAt && !manual ? duration(Date.now() - job.startedAt) : "";
      const q = this.engine.pending().length;
      const info = liveInfo(job);
      const parts = [`Second Brain · ${job.label}`];
      const s0 = job.live.stages[0];
      if (s0) parts.push(s0.unit === "%" ? `${s0.n}%` : s0.total > 0 ? `${s0.n} from ${s0.total}` : s0.stage);
      if (job.live.ask) parts.push("awaiting your answer");
      else if (info.wait !== null && info.wait >= 3000) parts.push(`waiting for an answer ${duration(info.wait)}`);
      else if (info.eta && !manual) parts.push(info.eta);
      if (t) parts.push(t);
      el.setText(parts.join(" · ") + (q ? ` (+${q})` : ""));
      el.setAttr("title", [info.stage, info.sub, job.lastLine].filter(Boolean).join("\n") || job.label);
    } else {
      const n = this.ui?.status.questions || 0;
      el.setText(n ? `Second Brain · ${nQuestions(n)}` : "Second Brain");
      el.setAttr("title", "Open Second Brain panel");
    }
  }

  async openView(tab?: Tab, containerId?: string | null) {
    const ws = this.app.workspace;
    let leaf = ws.getLeavesOfType(VIEW_TYPE)[0];
    if (!leaf) {
      const l = ws.getRightLeaf(false);
      if (!l) return;
      await l.setViewState({ type: VIEW_TYPE, active: true });
      leaf = l;
    }
    ws.revealLeaf(leaf);
    const v = leaf.view;
    if (v instanceof BrainView && tab) v.show(tab, containerId);
  }

  /** Open the plugin settings (tab — tab: main, models, thresholds, input, docs, costs, advanced). */
  openSettings(tab?: string) {
    if (tab) this.brainTab.openTab(tab);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const s = (this.app as any).setting;
    if (s) {
      s.open();
      s.openTabById(this.manifest.id);
    }
  }

  confirm(o: { title: string; text: string; ok: string; cancel?: string; warning?: boolean }): Promise<boolean> {
    return confirmModal(this.app, o);
  }

  // ---------- launches ----------
  async job(args: string[], label: string, notify = true): Promise<RunResult> {
    const t0 = Date.now();
    const r = await this.engine.run(args, { label, interactive: INTERACTIVE.has(args[0]) });
    this.doneNotify(label, r, r.elapsed ?? (Date.now() - t0) / 1000);
    await this.readSnapshot(true);
    if (r.webchat) this.lastWebchat = { label, args };
    else if (r.ok && this.lastWebchat && this.lastWebchat.args.join("\u0000") === args.join("\u0000")) this.lastWebchat = null;
    if (notify) this.notify(label, r);
    this.refresh();
    return r;
  }

  notify(label: string, r: RunResult) {
    if (r.webchat) new Notice(`${label}: waiting for a web chat response — see the Second Brain panel.`, 10000);
    else if (r.cancelled) new Notice(`${label}: cancelled — nothing changed.`, 6000);
    else if (r.budget_stop) {
      const why = (r.notices || []).find((n) => n.startsWith("Stopped:")) || "Stopped: budget exhausted. All processed items are saved.";
      new Notice(`${label}: ${lcFirst(why)}`, 20000);
    } else if (r.ok) {
      const sl = statsLine(r.stats);
      let msg = `${label}: ${lcFirst(r.title || "ready")}${sl ? " — " + sl : ""}.`;
      const u = r.run_usage;
      if (u && u.calls) msg += ` Requests: ${u.calls}${u.cost ? `, ${money(u.cost)}` : ""}${r.elapsed ? `, ${durationText(r.elapsed)}` : ""}.`;
      if (r.questions) msg += ` Open questions: ${r.questions}.`;
      if (r.warnings?.length) msg += ` Warnings: ${r.warnings.length} — see panel.`;
      new Notice(msg, 8000);
    } else if (r.stopped) new Notice(`${label}: stopped. Processed items are saved; the next run will continue.`, 8000);
    else new Notice(`${label}: ${r.error || "error"}`, 15000);
  }

  runPhase1() {
    return this.job(["run"], "Phase 1");
  }

  async runSynth(c: UiContainer, force = false): Promise<RunResult> {
    const label = `Phase 2 · ${c.title}`;
    const r = await this.job(["synth", c.id, ...(force ? ["--force"] : [])], label, false);
    if (r.ok && r.unchanged && !force) {
      const ok = await this.confirm({
        title: "Documents are up to date",
        text: `The synthesis base for ${c.title} has not changed since the last document run.\n\nRewrite the documents anyway? This requires model requests.`,
        ok: "Rewrite",
      });
      return ok ? this.runSynth(c, true) : r;
    }
    this.notify(label, r);
    return r;
  }

  /** Revalidation: The program will count the records and ask for confirmation. (time- and cost-estimated). */
  async runRevalidate(c: UiContainer | null) {
    const r = await this.job(["revalidate", ...(c ? [c.id] : [])], c ? `Revalidation · ${c.title}` : "Revalidate all entries", false);
    if (r.ok && !r.cancelled && !r.count) new Notice(c ? `There are no processed entries to recheck in “${c.title}”.` : "There are no processed entries to recheck.");
    else this.notify(c ? `Revalidation · ${c.title}` : "Revalidation", r);
  }

  /** Adjust program settings from the panel (price, budget): program settings.yaml. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async patchSettings(patch: Record<string, any>): Promise<RunResult> {
    const r = await this.engine.run(["settings", "--set-json", "-"], { label: "Saving settings", stdin: JSON.stringify(patch), exclusive: false, quiet: true });
    if (r.ok) await this.refreshState(true);
    return r;
  }

  /** Calculate the cost of past profile calls at current prices (expense-book — common-line). */
  async reprice(key: string): Promise<RunResult> {
    const r = await this.engine.run(["usage", "--reprice", key], { label: "Recalculate costs" });
    await this.refreshState(true);
    return r;
  }

  async runPatterns() {
    const ok = await this.confirm({
      title: "Find patterns",
      text: "The program will look in each container for groups of related aspects of different types not covered by an existing composite type, and suggest new types. It makes one model request for all groups found; if none are found, no request is made.",
      ok: "Find",
    });
    if (ok) await this.job(["patterns"], "Patterns");
  }

  runCheck() {
    new CheckModal(this).open();
  }

  // ---------- jelly-fish (llama.cpp) ----------
  /** Is the model downloaded?, assemblies llama.cpp eat, Is the server working?; hw — computer hardware. */
  async llamaStatus(hw = false): Promise<LlamaStatus | null> {
    if (this.engine.problem()) return null;
    const r = await this.engine.run(["llama", "status", ...(hw ? ["--hw"] : [])], { label: "Embedding model", exclusive: false, quiet: true });
    return r.ok && r.llama ? r.llama : null;
  }

  /** Run the model with parameters from the window «Run the model…»: need — leap (move — panel, «Stop.» —
   *  interrupt: The download will continue next time.), The server address will be entered into the settings itself. */
  async runLlamaStart(params: LlamaParams): Promise<RunResult> {
    const label = "Starting embedding model";
    const t0 = Date.now();
    const r = await this.engine.run(["llama", "start", "--params-json", "-"], { label, stdin: JSON.stringify(params) });
    this.doneNotify(label, r, (Date.now() - t0) / 1000);
    const s = r.server;
    if (r.ok && s) {
      if (s.already) new Notice(`The model is already running with these settings: ${s.url}`, 8000);
      else if (s.foreign) new Notice(`A server for this model is already running on port ${s.port}; the program will use it.`, 10000);
      else new Notice(`Model running: ${s.url}${s.load_sec ? ` (loaded ${durationText(s.load_sec)})` : ""}. Address saved in settings.`, 10000);
    } else if (r.stopped) new Notice("Model startup stopped. An interrupted download will resume on the next run.", 10000);
    else new Notice(`Model not started: ${r.error || "error"}`, 20000);
    await this.refreshState(true);
    this.brainTab.reload();
    return r;
  }

  /** Stop the model server (memory). The program will run it again on its own., whenever you need it. */
  async runLlamaStop(): Promise<RunResult> {
    const r = await this.engine.run(["llama", "stop"], { label: "Stopping embedding model", exclusive: false, quiet: true });
    if (!r.ok) new Notice(`Model not stopped: ${r.error || "error"}`, 12000);
    else new Notice(r.title === "Server stopped" ? "Embedding model stopped; memory released." : "The embedding model is not running.", 8000);
    return r;
  }

  continueWebchat() {
    const w = this.lastWebchat;
    return w ? this.job(w.args, w.label) : this.runPhase1();
  }

  answer(q: UiQuestion, option: number | null, text: string | null): Promise<RunResult> {
    const args = ["answer", q.id, option !== null ? `--option=${option}` : `--text=${text || ""}`];
    return this.job(args, `Answer. ${q.id}`, false);
  }

  async approveStructure() {
    const draft = this.ui?.status.draft || "_structure (draft).md";
    const ok = await this.confirm({
      title: "Approve structure?",
      text: "The program will create containers from the draft, including your edits, and place entries in them. This requires model requests for each entry.",
      ok: "Approve and continue",
    });
    if (!ok) return;
    for (const leaf of this.app.workspace.getLeavesOfType("markdown")) {
      const v = leaf.view; // draft — disk-first, Otherwise, the program wont see them.
      if (v instanceof MarkdownView && v.file?.path === draft) await v.save();
    }
    const r = await this.engine.local("Approving structure", async () => {
      const f = this.app.vault.getAbstractFileByPath(draft);
      if (!(f instanceof TFile)) throw new Error(`no draft file «${draft}»`);
      await this.app.vault.process(f, (text) => markApproved(text));
    });
    if (!r.ok) {
      new Notice(`Could not mark the draft as approved: ${r.error}`, 10000);
      return;
    }
    new Notice("Structure approved; creating containers and placing entries…");
    await this.runPhase1();
  }

  // ---------- AI ----------
  openAdvice(c: UiContainer, ready?: Advice) {
    new AdviceModal(this, c, ready).open();
  }

  async adviseNow(c: UiContainer): Promise<RunResult> {
    const label = `Threshold Council · ${c.title}`;
    const r = await this.job(["advise", c.id], label, false);
    if (r.ok && r.advice) {
      this.advice.set(c.id, { advice: r.advice, at: localIso() });
      this.refresh();
    } else this.notify(label, r);
    return r;
  }

  forgetAdvice(cid: string) {
    this.advice.delete(cid);
    this.refresh();
  }

  // ---------- editing YAML container (common-line, off-road) ----------
  private async editFrontmatter(c: UiContainer, label: string, fn: (fm: Record<string, unknown>) => void): Promise<boolean> {
    if (this.engine.busy()) new Notice("The program is running. The change will be saved immediately after the current run.");
    const r = await this.engine.local(label, async () => {
      const f = this.app.vault.getAbstractFileByPath(c.path);
      if (!(f instanceof TFile)) throw new Error(`No container file found «${c.path}»`);
      await this.app.fileManager.processFrontMatter(f, fn);
    });
    if (!r.ok) {
      new Notice(`Could not save: ${r.error}`, 10000);
      return false;
    }
    this.refreshState(true);
    return true;
  }

  saveThresholds(c: UiContainer, changes: Record<string, number | null>): Promise<boolean> {
    const aliases = this.ui?.threshold_aliases || {};
    return this.editFrontmatter(c, `Thresholds · ${c.title}`, (fm) => {
      const old = fm.thresholds;
      const t: Record<string, unknown> = old && typeof old === "object" && !Array.isArray(old) ? { ...(old as Record<string, unknown>) } : {};
      for (const [name, v] of Object.entries(changes)) {
        for (const k of Object.keys(t)) {
          const norm = k.trim().toLowerCase().replace(/ /g, "_");
          if (k !== name && (norm === name || aliases[norm] === name)) delete t[k]; // same threshold under the Russian name
        }
        if (v === null) delete t[name];
        else t[name] = v;
      }
      if (Object.keys(t).length) fm.thresholds = t;
      else delete fm.thresholds;
    });
  }

  saveStyle(c: UiContainer, text: string): Promise<boolean> {
    return this.editFrontmatter(c, `Style. · ${c.title}`, (fm) => {
      if (text) fm.style = text;
      else delete fm.style;
    });
  }

  async setContainerField(c: UiContainer, key: string, value: string, what: string) {
    const ok = await this.editFrontmatter(c, `${c.title}: ${what}`, (fm) => {
      fm[key] = value;
    });
    if (ok) new Notice(`${what} in “${c.title}”. The program will apply this on the next Phase 1 run.`);
  }

  // ---------- thought ----------
  newThought(hint = "") {
    new NewThoughtModal(this, hint).open();
  }

  async saveThought(text: string, hint: string, dateIso: string, source: string): Promise<string> {
    const { name, body } = thoughtFile(text, hint, dateIso);
    const folder = source && source !== "note" ? `_staging/${source}` : "_staging";
    const a = this.app.vault.adapter;
    if (!(await a.exists(folder))) await a.mkdir(folder);
    let p = `${folder}/${name}`;
    for (let i = 2; await a.exists(p); i++) p = `${folder}/${name.replace(/\.txt$/, ` (${i}).txt`)}`;
    await a.write(p, body);
    this.refreshState();
    return p;
  }

  // ---------- file ----------
  async open(rel: string) {
    const f = this.app.vault.getAbstractFileByPath(rel);
    if (f instanceof TFile && f.extension === "md") {
      await this.app.workspace.getLeaf(false).openFile(f);
      return;
    }
    try {
      const text = await this.app.vault.adapter.read(rel);
      new TextModal(this.app, baseName(rel), text).open();
    } catch {
      new Notice(`File not found: ${rel}`);
    }
  }

  async revealFolder(rel: string) {
    const a = this.app.vault.adapter;
    if (!(await a.exists(rel))) await a.mkdir(rel);
    this.revealPath(path.join(this.engine.vaultPath(), rel));
  }

  revealPath(abs: string, isFile = false) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const { shell } = require("electron");
      if (isFile) shell.showItemInFolder(abs);
      else shell.openPath(abs);
    } catch {
      new Notice(`Open it manually: ${abs}`, 10000);
    }
  }

  pickContainer(cb: (c: UiContainer | null) => void, allLabel?: string) {
    if (!this.ui?.containers.length) {
      new Notice("No containers yet; approve the structure first.");
      return;
    }
    new ContainerPicker(this, allLabel || null, cb).open();
  }

  containerOfActive(): UiContainer | null {
    const f = this.app.workspace.getActiveFile();
    return f ? containerOfPath(this.ui, f.path) : null;
  }

  // ---------- team ----------
  private addCommands() {
    this.addCommand({ id: "open-panel", name: "Open panel", callback: () => this.openView() });
    this.addCommand({ id: "run", name: "Phase 1: process new entries", callback: () => this.runPhase1() });
    this.addCommand({ id: "new-thought", name: "New thought", callback: () => this.newThought() });
    this.addCommand({ id: "questions", name: "Answer questions", callback: () => this.openView("questions") });
    this.addCommand({ id: "synth", name: "Phase 2: write documents…", callback: () => this.pickContainer((c) => c && this.runSynth(c)) });
    this.addCommand({
      id: "synth-current",
      name: "Phase 2 for the open note's container",
      checkCallback: (checking) => {
        const c = this.containerOfActive();
        if (!c) return false;
        if (!checking) this.runSynth(c);
        return true;
      },
    });
    this.addCommand({
      id: "container-current",
      name: "Show the open note's container",
      checkCallback: (checking) => {
        const c = this.containerOfActive();
        if (!c) return false;
        if (!checking) this.openView("container", c.id);
        return true;
      },
    });
    this.addCommand({ id: "advise", name: "AI advice on container thresholds…", callback: () => this.pickContainer((c) => c && this.openAdvice(c)) });
    this.addCommand({ id: "revalidate", name: "Revalidation…", callback: () => this.pickContainer((c) => this.runRevalidate(c), "All containers") });
    this.addCommand({ id: "patterns", name: "Patterns: find new composite types", callback: () => this.runPatterns() });
    this.addCommand({ id: "check", name: "Check model connection", callback: () => this.runCheck() });
    this.addCommand({ id: "usage", name: "Model expenses", callback: () => this.openView("usage") });
    this.addCommand({ id: "update", name: "Check for program updates", callback: () => this.checkUpdates(true) });
    this.addCommand({ id: "refresh", name: "Refresh status", callback: () => this.refreshState(true) });
    this.addCommand({ id: "report", name: "Developer report", callback: () => saveDeveloperReport(this) });
    this.addCommand({
      id: "stop",
      name: "Stop",
      checkCallback: (checking) => {
        if (!this.engine.busy()) return false;
        if (!checking) this.engine.stop();
        return true;
      },
    });
  }
}

/** «Ready.» → «ready» colon; franchising («API …») unmoved. */
function lcFirst(s: string): string {
  return s.length > 1 && s[1] === s[1].toLowerCase() ? s[0].toLowerCase() + s.slice(1) : s;
}

/** Mark in the draft «- [x] Structure approved» (line, if it was erased). */
export function markApproved(text: string): string {
  const re = new RegExp(`^(\\s*[-*]\\s*)\\[ \\](\\s*${APPROVE})`, "m");
  if (re.test(text)) return text.replace(re, "$1[x]$2");
  if (new RegExp(`^\\s*[-*]\\s*\\[[xXxx✓vV]\\]\\s*${APPROVE}`, "m").test(text)) return text;
  const fm = /^---\r?\n[\s\S]*?\r?\n---\r?\n/.exec(text);
  const at = fm ? fm[0].length : 0;
  return text.slice(0, at) + `- [x] ${APPROVE}\n\n` + text.slice(at);
}
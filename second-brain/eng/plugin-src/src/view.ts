// Panel «Second Brain» side-column: survey, questions, container, expense, journal.
import { ItemView, MarkdownRenderer, Notice, TFile, WorkspaceLeaf, setIcon } from "obsidian";
import type BrainPlugin from "./main";
import { Job, liveInfo, manualMode } from "./engine";
import { renderError } from "./report";
import type { Period, UiContainer, UiQuestion, UiSnapshot, UsageProfile, UsageSummary, UsageTotals } from "./types";
import {
  PTYPE_RU, callsLine, clock, compact, containerOfPath, duration, durationText, money, nCalls, nQuestions, nRecords, num,
  parentsOf, parseNumber, pctText, plural, rangeText, ruDateTime, statsLine, usageLine,
} from "./util";

export const VIEW_TYPE = "vtoroy-mozg-panel";
export type Tab = "overview" | "questions" | "container" | "usage" | "log";

const RUN_NAMES: Record<string, string> = {
  run: "Phase 1", synth: "Phase 2", revalidate: "Revalidation", patterns: "Patterns", advise: "Threshold advice",
  answer: "Answer question", check: "Check connection",
};
const TAB_TITLES: Record<Tab, string> = { overview: "Overview", questions: "Questions", container: "Container", usage: "Expenses", log: "Log" };
const PERIODS: [Period, string][] = [["today", "Today"], ["month", "This month"], ["prev_month", "Last month"], ["all", "All time"]];
const PERIOD_IN: Record<Period, string> = { today: "today", month: "this month", prev_month: "last month", all: "all time" };

interface RunEls {
  job: Job;
  time: HTMLElement;
  spin: HTMLElement;
  stage: HTMLElement;
  barBox: HTMLElement;
  bar: HTMLElement;
  sub: HTMLElement;
  wait: HTMLElement;
  usage: HTMLElement;
  ask: HTMLElement;
  line: HTMLElement;
  kill: HTMLElement | null;
}

const FILE_WAIT: Record<string, string> = {
  await_structure: "pending approval of the structure",
  await_mode: "waiting for a decision on file mode",
  ready: "waiting to be processed",
  new: "waiting for the structure draft",
};

export class BrainView extends ItemView {
  tab: Tab = "overview";
  selectedId: string | null = null;
  follow = true;
  qFilter: string | null = null;
  private freeText = new Map<string, string>();
  private answerError = new Map<string, string>();
  private thrDraft = new Map<string, Record<string, string>>();
  private styleDraft = new Map<string, string>();
  private openJobs = new Set<number>();
  private renderPending = false;
  private headEl!: HTMLElement;
  private runEl!: HTMLElement;
  private tabsEl!: HTMLElement;
  private bodyEl!: HTMLElement;
  private runEls: RunEls | null = null;
  private usagePeriod: Period = "month";
  private priceDraft = new Map<string, Record<string, string>>();
  private budgetDraft: string | null = null;

  constructor(leaf: WorkspaceLeaf, private plugin: BrainPlugin) {
    super(leaf);
  }
  getViewType() {
    return VIEW_TYPE;
  }
  getDisplayText() {
    return "Second Brain";
  }
  getIcon() {
    return "brain";
  }

  async onOpen() {
    const root = this.contentEl;
    root.empty();
    root.addClass("vm-view");
    this.headEl = root.createDiv({ cls: "vm-head" });
    this.runEl = root.createDiv({ cls: "vm-run" });
    this.tabsEl = root.createDiv({ cls: "vm-tabs" });
    this.bodyEl = root.createDiv({ cls: "vm-body" });
    this.plugin.views.add(this);
    this.registerEvent(this.app.workspace.on("file-open", (f: TFile | null) => this.onFileOpen(f)));
    this.registerDomEvent(root, "focusout", () =>
      window.setTimeout(() => {
        if (this.renderPending && !this.editing()) this.render();
      }, 150),
    );
    this.registerInterval(window.setInterval(() => this.tick(), 1000));
    this.onFileOpen(this.app.workspace.getActiveFile());
    this.render();
  }

  async onClose() {
    this.plugin.views.delete(this);
  }

  // ---------- general ----------
  show(tab: Tab, containerId?: string | null) {
    this.tab = tab;
    if (containerId !== undefined) {
      this.selectedId = containerId;
      if (containerId) this.follow = false;
    }
    this.renderPending = false;
    this.render(true);
  }

  private editing(): boolean {
    // The panel may be in a separate window Obsidian: Look at the focus of her paper.
    const a = (this.contentEl.ownerDocument || document).activeElement as HTMLElement | null;
    if (!a || !this.contentEl.contains(a)) return false;
    if (a.tagName === "TEXTAREA") return true;
    return a.tagName === "INPUT" && !["checkbox", "radio", "button"].includes((a as HTMLInputElement).type);
  }

  /** Re-drawing. While a person is typing in the panel field, postponed until out of the field. */
  render(force = false) {
    if (!this.bodyEl) return;
    if (!force && this.editing()) {
      this.renderPending = true;
      this.renderRun();
      return;
    }
    this.renderPending = false;
    const scroll = this.contentEl.scrollTop;
    try {
      this.renderHead();
      this.renderRun();
      this.renderTabs();
    } catch (e) {
      this.plugin.errors.add("panel, cap", e);
    }
    this.bodyEl.empty();
    const ui = this.plugin.ui;
    try {
      if (this.tab === "overview") this.renderOverview(this.bodyEl);
      else if (this.tab === "questions") this.renderQuestions(this.bodyEl, ui);
      else if (this.tab === "container") this.renderContainerTab(this.bodyEl, ui);
      else if (this.tab === "usage") this.renderUsageTab(this.bodyEl, ui);
      else this.renderLog(this.bodyEl, ui);
    } catch (e) {
      // one-stick broke — show off the button error «Copy the report.», the rest of the panel is working
      renderError(this.bodyEl, this.plugin, `panel, tab «${TAB_TITLES[this.tab]}»`, e);
    }
    this.contentEl.scrollTop = scroll;
  }

  private onFileOpen(f: TFile | null) {
    if (!this.follow || !f) return;
    const c = containerOfPath(this.plugin.ui, f.path);
    if (c && c.id !== this.selectedId) {
      this.selectedId = c.id;
      if (this.tab === "container") this.render();
    }
  }

  private byId(id: string | null | undefined): UiContainer | null {
    if (!id) return null;
    return this.plugin.ui?.containers.find((c) => c.id === id) || null;
  }

  private button(parent: HTMLElement, text: string, onClick: () => void, kind?: "cta" | "warning", disabled = false): HTMLButtonElement {
    const b = parent.createEl("button", { text, cls: kind === "cta" ? "mod-cta" : kind === "warning" ? "mod-warning" : "" });
    b.disabled = disabled;
    b.addEventListener("click", (ev) => {
      ev.preventDefault();
      onClick();
    });
    return b;
  }

  private section(parent: HTMLElement, title: string, extra?: string): HTMLElement {
    const s = parent.createDiv({ cls: "vm-section" });
    const h = s.createDiv({ cls: "vm-section-title", text: title });
    if (extra) h.createSpan({ cls: "vm-muted vm-section-extra", text: extra });
    return s;
  }

  private callout(parent: HTMLElement, kind: "ok" | "warning" | "info" | "accent", title: string | null, text?: string | null): HTMLElement {
    const c = parent.createDiv({ cls: `vm-callout is-${kind}` });
    if (title) c.createDiv({ cls: "vm-callout-title", text: title });
    if (text) c.createDiv({ text });
    return c;
  }

  private dot(parent: HTMLElement, color: string | null) {
    const d = parent.createSpan({ cls: "vm-dot" });
    if (color) d.style.backgroundColor = color;
    return d;
  }

  private hookLinks(el: HTMLElement) {
    el.querySelectorAll("a.internal-link").forEach((a) =>
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        const href = a.getAttribute("data-href") || a.getAttribute("href") || "";
        if (href) this.app.workspace.openLinkText(href, "", false);
      }),
    );
  }

  // ---------- cap and current launch ----------
  private renderHead() {
    const h = this.headEl;
    h.empty();
    // name and condition — block-by-block: in a narrow column, the state is transferred under the name, not circumcised
    const main = h.createDiv({ cls: "vm-head-main" });
    const t = main.createDiv({ cls: "vm-title" });
    setIcon(t.createSpan({ cls: "vm-logo" }), "brain");
    t.createSpan({ text: "Second Brain" });
    const p = this.plugin;
    const state = main.createDiv({ cls: "vm-state" });
    if (p.engine.problem()) state.setText("No connection to the program");
    else if (p.engine.busy()) state.setText("Running");
    else if (p.ui) state.setText(p.ui.status.questions ? `${nQuestions(p.ui.status.questions)} waiting` : "ready");
    const tools = h.createDiv({ cls: "vm-head-tools" });
    const r = tools.createDiv({ cls: "clickable-icon vm-icon-btn", attr: { "aria-label": "Refresh status" } });
    setIcon(r, "refresh-cw");
    r.addEventListener("click", () => p.refreshState(true));
    const s = tools.createDiv({ cls: "clickable-icon vm-icon-btn", attr: { "aria-label": "Plugin settings" } });
    setIcon(s, "settings");
    s.addEventListener("click", () => p.openSettings());
  }

  renderRun() {
    if (!this.runEl) return;
    const el = this.runEl;
    el.empty();
    this.runEls = null;
    const eng = this.plugin.engine;
    const job = eng.active();
    const queued = eng.pending();
    if (!job && !queued.length) {
      el.removeClass("is-on");
      return;
    }
    el.addClass("is-on");
    const spin = el.createDiv({ cls: "vm-progress" });
    if (job) {
      const h = el.createDiv({ cls: "vm-run-head" });
      h.createSpan({ cls: "vm-run-label", text: job.label });
      const time = h.createSpan({ cls: "vm-run-time", attr: { title: "Run duration" } });
      const stage = el.createDiv({ cls: "vm-run-stage" });
      const barBox = el.createDiv({ cls: "vm-bar" });
      const bar = barBox.createDiv({ cls: "vm-bar-fill" });
      const sub = el.createDiv({ cls: "vm-run-sub" });
      const wait = el.createDiv({ cls: "vm-run-wait" });
      const ask = el.createDiv({ cls: "vm-run-ask" });
      const usage = el.createDiv({ cls: "vm-run-usage" });
      const line = el.createDiv({ cls: "vm-run-line" });
      this.runEls = { job, time, spin, stage, barBox, bar, sub, wait, usage, ask, line, kill: null };
      if (job.stopAt) {
        el.createDiv({
          cls: "vm-run-note",
          text: "Stopping: the program will finish the current step and save everything. If the model is slow to respond, this can take a few minutes.",
        });
      }
    }
    if (queued.length) el.createDiv({ cls: "vm-run-queue", text: "Queued: " + queued.map((j) => j.label).join(", ") });
    const b = el.createDiv({ cls: "vm-buttons" });
    if (!job?.stopAt) this.button(b, "Stop", () => eng.stop());
    if (job) {
      const kill = this.button(b, "Stop immediately", async () => {
        const ok = await this.plugin.confirm({
          title: "Stop immediately?",
          text: "The program will stop immediately. The current model response will be lost, but everything saved before it will remain intact.",
          ok: "Stop",
          warning: true,
        });
        if (ok) eng.kill();
      }, "warning");
      if (this.runEls) this.runEls.kill = kill;
      this.button(b, "Program output", () => {
        this.openJobs.add(job.id);
        this.show("log");
      });
    }
    this.tick();
  }

  /** Once a second and for every live line of the program: time, stage, «left ≈», wait, expense. */
  private tick() {
    const r = this.runEls;
    const job = this.plugin.engine.active();
    if (!r || !job || r.job !== job) return;
    const now = Date.now();
    const info = liveInfo(job, now);
    const show = (e: HTMLElement, text: string) => {
      e.setText(text);
      e.toggleClass("vm-hidden", !text);
    };
    const manual = manualMode(this.plugin.ui); // web-based-chat: time «left» non-showable — You write the answer. (waiting
    // answer, only if-This step goes through the model.)
    r.time.setText(job.startedAt && !manual ? duration(now - job.startedAt) : "");
    show(r.stage, info.stage ? info.stage + (info.eta && !manual ? ` · ${info.eta}` : "") : "");
    r.barBox.toggleClass("vm-hidden", info.frac === null);
    r.spin.toggleClass("vm-hidden", info.frac !== null);
    if (info.frac !== null) r.bar.style.width = `${Math.round(info.frac * 1000) / 10}%`;
    show(r.sub, info.sub);
    const ask = job.live.ask;
    show(r.ask, ask ? `The program is waiting for your answer.: «${ask.title}» — window open Obsidian.` : "");
    show(r.wait, !ask && info.wait !== null && info.wait >= 1500 ? `Were waiting for the model to respond.: ${duration(info.wait)}${info.waitWhat ? ` · ${info.waitWhat}` : ""}` : "");
    const u = job.live.usage;
    const local = job.live.last?.ptype === "local";
    show(r.usage, u && u.calls ? `This launch: ${usageLine(u, { time: local })}` : "");
    r.line.setText(job.lastLine || "Starting the program…");
    if (r.kill) r.kill.toggleClass("vm-hidden", !(job.stopAt && now - job.stopAt > 20000));
  }

  /** New line of output — update only the progress line, panelless. */
  progress() {
    this.tick();
  }

  private renderTabs() {
    const el = this.tabsEl;
    el.empty();
    const q = this.plugin.ui?.status.questions || 0;
    const tabs: [Tab, string, number][] = [["overview", "Overview", 0], ["questions", "Questions", q], ["container", "Container", 0], ["usage", "Expenses", 0], ["log", "Log", 0]];
    for (const [id, label, n] of tabs) {
      const t = el.createEl("button", { cls: "vm-tab" + (this.tab === id ? " is-active" : "") });
      t.createSpan({ text: label });
      if (n) t.createSpan({ cls: "vm-badge is-accent", text: String(n) });
      t.addEventListener("click", () => this.show(id));
    }
  }

  // ---------- Review ----------
  private renderOverview(el: HTMLElement) {
    const p = this.plugin;
    const prob = p.engine.problem();
    if (prob) {
      const c = this.callout(el, "warning", "The plugin cannot find the program", prob);
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, "Open settings", () => p.openSettings(), "cta");
      return;
    }
    const ui = p.ui;
    if (!ui) {
      const c = this.callout(el, "info", "Loading vault status…", "On first opening, the program creates its working folders.");
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, "Update", () => p.refreshState(true));
      return;
    }
    const wizard = !ui.status.approved_once;
    if (wizard) this.renderWizard(el, ui);
    else this.renderAttention(el, ui);
    this.renderActions(el, ui, wizard);
    this.renderCounts(el, ui, wizard);
    this.renderCurrent(el, ui);
    this.renderWarnings(el, ui);
    if (ui.containers.length) this.renderTree(el, ui);
  }

  private renderWizard(el: HTMLElement, ui: UiSnapshot) {
    const p = this.plugin;
    const s = ui.status;
    const busy = p.engine.busy();
    const box = el.createDiv({ cls: "vm-card vm-wizard" });
    box.createDiv({ cls: "vm-card-title", text: "First import" });
    const waiting = Object.values(s.files).reduce((a, b) => a + b, 0);
    const hasFiles = s.staging_new > 0 || waiting > 0 || s.structure_pending;
    const draft = s.structure_pending && !!s.draft;
    const steps: { title: string; done: boolean; body: (d: HTMLElement) => void }[] = [
      {
        title: "Put your notes in _staging",
        done: hasFiles,
        body: (d) => {
          d.createDiv({ text: "Place old notes in _staging/archive and new notes directly in _staging. Both .txt and .md files are supported; filenames can be anything." });
          d.createDiv({ cls: "vm-muted", text: s.staging_new ? `Files in _staging: ${s.staging_new}.` : "_staging is currently empty." });
          const b = d.createDiv({ cls: "vm-buttons" });
          this.button(b, "Open _staging", () => p.revealFolder("_staging"));
          this.button(b, "New thought", () => p.newThought());
          if (s.staging_new) this.button(b, "Next.: Phase 1", () => p.runPhase1(), "cta", busy);
        },
      },
      {
        title: "Phase 1 — structure draft",
        done: draft,
        body: (d) => {
          d.createDiv({ text: "The program will read the files and propose a tree of containers: projects, sprouts, and questions." });
          if (waiting) d.createDiv({ cls: "vm-muted", text: `Files read: ${waiting}.` });
          const b = d.createDiv({ cls: "vm-buttons" });
          this.button(b, "Start Phase 1", () => p.runPhase1(), "cta", busy);
        },
      },
      {
        title: "Review and approve the draft",
        done: false,
        body: (d) => {
          d.createDiv({ text: "Rename, merge, or remove containers directly in the draft. Once approved, the program will create folders and place entries in them as the next part of Phase 1." });
          const b = d.createDiv({ cls: "vm-buttons" });
          if (s.draft) this.button(b, "Open draft", () => p.open(s.draft!));
          this.button(b, "Approve structure", () => p.approveStructure(), "cta", busy);
        },
      },
    ];
    const cur = steps.findIndex((x) => !x.done);
    steps.forEach((st, i) => {
      const row = box.createDiv({ cls: "vm-step " + (st.done ? "is-done" : i === cur ? "is-current" : "is-future") });
      row.createDiv({ cls: "vm-step-num", text: st.done ? "✓" : String(i + 1) });
      const body = row.createDiv({ cls: "vm-step-body" });
      body.createDiv({ cls: "vm-step-title", text: st.title });
      if (i === cur) st.body(body);
    });
    if (s.questions) {
      const q = this.callout(el, "accent", `Waiting for an answer: ${nQuestions(s.questions)}`, "For example, whether a file is a bulk import or a single entry.");
      this.button(q.createDiv({ cls: "vm-buttons" }), "Reply", () => this.show("questions"), "cta");
    }
  }

  private renderAttention(el: HTMLElement, ui: UiSnapshot) {
    const p = this.plugin;
    const s = ui.status;
    const busy = p.engine.busy();
    let n = 0;
    if (s.structure_pending && s.draft) {
      n++;
      const c = this.callout(el, "accent", "Draft structure awaits approval", "The program proposed changes to the structure. Open, edit, and approve the draft.");
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, "Open draft", () => p.open(s.draft!));
      this.button(b, "Approve structure", () => p.approveStructure(), "cta", busy);
    }
    if (s.webchat_pending.length) {
      n++;
      const c = this.callout(el, "accent", "Waiting for a web chat response", null);
      for (const w of s.webchat_pending) {
        const row = c.createDiv({ cls: "vm-webchat" });
        row.createDiv({ text: `Step “${w.prompt}”: copy the entire request to the web chat, then paste the complete response into the answer file and save it.` });
        const b = row.createDiv({ cls: "vm-buttons" });
        this.button(b, "Open the request", () => p.open(w.req));
        this.button(b, "Open answer file", () => p.open(w.ans));
      }
      const last = p.lastWebchat;
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, last ? `Continue: ${last.label}` : "Continue (Phase 1)", () => p.continueWebchat(), "cta", busy);
    }
    if (s.questions) {
      n++;
      const c = this.callout(el, "accent", `Waiting for an answer: ${nQuestions(s.questions)}`, "Answers are applied immediately.");
      this.button(c.createDiv({ cls: "vm-buttons" }), "Reply", () => this.show("questions"), "cta");
    }
    if (s.staging_new) {
      n++;
      const c = this.callout(el, "info", `New files in _staging: ${s.staging_new}`, null);
      this.button(c.createDiv({ cls: "vm-buttons" }), "Process (Phase 1)", () => p.runPhase1(), "cta", busy);
    } else if (s.pending_work) {
      n++;
      const text = s.dirty.length ? `Synthesis bases for reassembly: ${s.dirty.map((d) => d.title).join(", ")}.` : "Some entries are still queued.";
      const c = this.callout(el, "info", "Processing is incomplete", text);
      this.button(c.createDiv({ cls: "vm-buttons" }), "Continue (Phase 1)", () => p.runPhase1(), "cta", busy);
    }
    if (!n) this.callout(el, "ok", "Everything has been processed.", "Add new thoughts using the New thought button or files in _staging.");
  }

  private renderActions(el: HTMLElement, ui: UiSnapshot, wizard: boolean) {
    const p = this.plugin;
    const box = el.createDiv({ cls: "vm-actions" + (wizard ? " is-wizard" : "") });
    const has = ui.containers.length > 0;
    const s = ui.status;
    const running = !!p.engine.find((j: Job) => j.args[0] === "run");
    if (!wizard)
      this.button(box, running ? "Phase 1 in progress…" : "Phase 1: process new entries", () => p.runPhase1(), s.staging_new || s.pending_work ? "cta" : undefined, running);
    this.button(box, "New thought", () => p.newThought());
    this.button(box, "Phase 2: documents…", () => p.pickContainer((c) => c && p.runSynth(c)), undefined, !has);
    this.button(box, "Revalidation…", () => p.pickContainer((c) => p.runRevalidate(c), "All the containers."), undefined, !has);
    this.button(box, "Patterns", () => p.runPatterns(), undefined, !has);
    this.button(box, "Check connection", () => p.runCheck());
  }

  private renderCounts(el: HTMLElement, ui: UiSnapshot, wizard: boolean) {
    const s = ui.status;
    const files = Object.entries(s.files).filter(([k, v]) => v && FILE_WAIT[k]);
    const filesLine = () => {
      if (files.length) el.createDiv({ cls: "vm-muted vm-line", text: "Files: " + files.map(([k, v]) => `${FILE_WAIT[k]} — ${v}`).join(" · ") });
    };
    if (wizard) {
      filesLine();
      return;
    }
    const g = el.createDiv({ cls: "vm-stats" });
    const tile = (n: number, forms: [string, string, string], onClick?: () => void) => {
      const t = g.createDiv({ cls: "vm-stat" + (onClick ? " is-link" : "") });
      t.createDiv({ cls: "vm-stat-n", text: String(n) });
      t.createDiv({ cls: "vm-stat-l", text: plural(n, forms) });
      if (onClick) t.addEventListener("click", onClick);
    };
    tile(s.containers, ["container", "containers", "containers"]);
    tile(s.entities, ["entry", "entries", "entries"]);
    tile(s.products, ["document", "documents", "documents"]);
    tile(s.questions, ["question", "questions", "questions"], () => this.show("questions"));
    const parts = [`processed ${s.stages.done}`];
    if (s.stages.quarantine) parts.push(`wait ${s.stages.quarantine}`);
    if (s.stages.queue) parts.push(`line up ${s.stages.queue}`);
    if (s.entities || s.stages.queue || s.stages.quarantine) el.createDiv({ cls: "vm-muted vm-line", text: "Entries: " + parts.join(" · ") });
    filesLine();
  }

  private renderWarnings(el: HTMLElement, ui: UiSnapshot) {
    const list = [...new Set(ui.warnings || [])];
    if (!list.length) return;
    const s = this.section(el, "Warnings");
    for (const w of list) {
      const row = s.createDiv({ cls: "vm-warn" });
      row.createSpan({ cls: "vm-warn-mark", text: "!" });
      const t = row.createDiv({ cls: "vm-warn-text" });
      MarkdownRenderer.render(this.app, w, t, "", this).then(() => this.hookLinks(t));
    }
  }

  private renderTree(el: HTMLElement, ui: UiSnapshot) {
    const s = this.section(el, "Containers", "entries");
    for (const c of ui.containers) {
      const row = s.createDiv({ cls: "vm-tree-row" + (c.status !== "active" ? " is-muted" : "") + (c.id === this.selectedId ? " is-selected" : "") });
      row.style.paddingLeft = `${6 + c.depth * 16}px`;
      this.dot(row, c.color);
      row.createSpan({ cls: "vm-tree-title", text: c.title });
      if (c.type !== "project") row.createSpan({ cls: "vm-chip", text: c.type_ru });
      if (c.status !== "active") row.createSpan({ cls: "vm-chip is-muted", text: c.status_ru });
      const right = row.createSpan({ cls: "vm-tree-right" });
      if (c.dirty) right.createSpan({ cls: "vm-mark", text: "↻", attr: { title: "Synthesis base needs to be rebuilt" } });
      if (c.questions) right.createSpan({ cls: "vm-badge is-accent", text: String(c.questions), attr: { title: nQuestions(c.questions) } });
      right.createSpan({ cls: "vm-tree-n", text: String(c.entities + c.shared) });
      row.addEventListener("click", () => this.show("container", c.id));
    }
  }

  /** Review: What model does the program work on and how much it cost this month?. */
  private renderCurrent(el: HTMLElement, ui: UiSnapshot) {
    const u = ui.usage;
    if (!u) return;
    const cur = u.current;
    const box = el.createDiv({ cls: "vm-card vm-current" });
    const head = box.createDiv({ cls: "vm-current-head" });
    const webchat = cur.mode === "webchat";
    head.createSpan({ cls: "vm-current-k", text: "Model:" });
    head.createSpan({ cls: "vm-current-name", text: webchat ? "manual web chat" : cur.name || "no profile selected" });
    if (cur.ptype && !webchat) head.createSpan({ cls: "vm-chip", text: PTYPE_RU[cur.ptype] || cur.ptype });
    const link = head.createEl("a", { cls: "vm-link vm-small-text vm-current-link", text: "Expenses →" });
    link.addEventListener("click", () => this.show("usage"));
    if (!webchat && !cur.name) {
      const a = box.createEl("a", { cls: "vm-link vm-small-text", text: "Select a profile in settings" });
      a.addEventListener("click", () => this.plugin.openSettings("models"));
    }
    const t = cur.totals?.month;
    box.createDiv({
      cls: "vm-muted vm-small-text",
      text: t && t.calls ? `This month: ${usageLine(t, { time: cur.ptype === "local" })}${t.unpriced ? " (* some calls have no prices)" : ""}` : "This model has not been used this month.",
    });
    const all = u.totals.month;
    if (all.calls && t && all.calls !== t.calls) box.createDiv({ cls: "vm-muted vm-small-text", text: `All models this month: ${usageLine(all)}` });
    if (u.budget.monthly_usd) this.budgetBar(box, u, false);
  }

  /** Budget band of the month: green, s 80% — yellow, scoot 100% — red. */
  private budgetBar(parent: HTMLElement, u: UsageSummary, big: boolean) {
    const b = u.budget;
    if (!b.monthly_usd) return;
    const pct = b.pct ?? 0;
    const wrap = parent.createDiv({ cls: "vm-budget" + (big ? " is-big" : "") + (b.state ? ` is-${b.state}` : "") });
    const t = wrap.createDiv({ cls: "vm-budget-text" });
    t.createSpan({ text: `Monthly budget: ${money(b.spent)} of ${money(b.monthly_usd)}` });
    t.createSpan({ cls: "vm-budget-pct", text: ` · ${pctText(pct)}` });
    const bar = wrap.createDiv({ cls: "vm-bar" });
    bar.createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.min(100, pct)}%`;
    if (b.state === "over") wrap.createDiv({ cls: "vm-small-text", text: "Budget exhausted: before the next paid request, the program will stop and ask whether to continue." });
    else if (b.state === "warn") wrap.createDiv({ cls: "vm-small-text", text: `More than ${b.warn_pct}% of the budget has been spent.` });
  }

  // ---------- Expenses ----------
  private renderUsageTab(el: HTMLElement, ui: UiSnapshot | null) {
    const p = this.plugin;
    const u = ui?.usage;
    if (!ui || !u) {
      this.callout(el, "info", "No expenses yet", "A summary will appear after the first model request.");
      return;
    }
    const job = p.engine.active();
    if (job?.live.usage?.calls) {
      const local = job.live.last?.ptype === "local";
      this.callout(el, "info", `In progress: ${job.label}`, usageLine(job.live.usage, { time: local }) + ". The summary below will update when the run finishes.");
    }
    const seg = el.createDiv({ cls: "vm-seg" });
    for (const [k, label] of PERIODS) {
      const b = seg.createEl("button", { cls: "vm-seg-btn" + (this.usagePeriod === k ? " is-active" : ""), text: label });
      b.addEventListener("click", () => {
        this.usagePeriod = k;
        this.render(true);
      });
    }
    const per = this.usagePeriod;
    const T = u.totals[per];
    const card = el.createDiv({ cls: "vm-card vm-usage-total" });
    const big = card.createDiv({ cls: "vm-usage-big" });
    const hasCloud = u.profiles.some((x) => x.ptype === "cloud" && x.totals[per].calls);
    big.createSpan({ cls: "vm-usage-money", text: hasCloud || T.cost ? money(T.cost) + (T.unpriced ? "*" : "") : "$0" });
    big.createSpan({ cls: "vm-muted", text: ` ${PERIOD_IN[per]}` });
    const g = card.createDiv({ cls: "vm-usage-grid" });
    const cell = (k: string, v: string, title?: string) => {
      const c = g.createDiv({ cls: "vm-usage-cell", attr: title ? { title } : {} });
      c.createDiv({ cls: "vm-usage-v", text: v });
      c.createDiv({ cls: "vm-usage-k", text: k });
    };
    cell(plural(T.calls, ["request", "requests", "requests"]), num(T.calls));
    cell("input tokens", compact(T.in), T.cached ? `cached: ${num(T.cached)}` : undefined);
    cell("output tokens", compact(T.out));
    cell("model time", T.sec ? durationText(T.sec) : "—", "Total time models spent generating responses across all requests");
    if (T.cached) card.createDiv({ cls: "vm-muted vm-small-text", text: `From the provider’s cache: ${num(T.cached)} input tokens (lower cost).` });
    if (T.unpriced)
      card.createDiv({ cls: "vm-small-text vm-warn-line", text: `* ${nCalls(T.unpriced)} to cloud models have no cost because profile prices are missing. Enter prices below to recalculate past requests.` });
    if (T.est) card.createDiv({ cls: "vm-muted vm-small-text", text: `For ${nCalls(T.est)}, the server did not report token counts; they were estimated from the number of characters.` });
    if (!T.calls) card.createDiv({ cls: "vm-muted", text: `No requests ${PERIOD_IN[per]}.` });
    this.renderBudgetEdit(el, u);
    this.renderProfiles(el, u, per);
    this.renderSteps(el, u, per);
    this.renderDays(el, u);
    this.renderRuns(el, u);
    el.createDiv({
      cls: "vm-muted vm-small-text",
      text: "Costs use profile prices at the time of each request and are stored in .system/usage.jsonl. Local models are free; their tokens and time are still recorded.",
    });
  }

  private renderBudgetEdit(el: HTMLElement, u: UsageSummary) {
    const p = this.plugin;
    const s = this.section(el, "Cloud model budget", "per month");
    if (u.budget.monthly_usd) this.budgetBar(s, u, true);
    else s.createDiv({ cls: "vm-muted vm-small-text", text: `No budget set. Spent this month: ${money(u.budget.spent)}.` });
    const row = s.createDiv({ cls: "vm-inline-form" });
    row.createSpan({ text: "Budget, $" });
    const inp = row.createEl("input", { type: "text", cls: "vm-num", attr: { inputmode: "decimal", placeholder: "No budget limit" } });
    inp.value = this.budgetDraft ?? (u.budget.monthly_usd != null ? String(u.budget.monthly_usd) : "");
    const save = this.button(row, "Save", async () => {
      const v = parseNumber(inp.value, "float", 0, 100000);
      if (v === null) {
        inp.addClass("vm-invalid");
        new Notice("Enter a budget from 0 to 100000, or leave empty for no budget.");
        return;
      }
      save.disabled = true;
      const r = await p.patchSettings({ budget: { monthly_usd: v === undefined || v === 0 ? null : v } });
      this.budgetDraft = null;
      if (r.ok) new Notice(v ? `Monthly budget: ${money(v)}. A warning appears at ${u.budget.warn_pct}%; at 100%, the program stops and asks whether to continue.` : "Budget removed.");
      else new Notice(r.error || "Budget not saved.", 12000);
      this.render(true);
    });
    inp.addEventListener("input", () => {
      this.budgetDraft = inp.value;
      inp.removeClass("vm-invalid");
    });
    inp.addEventListener("keydown", (ev: KeyboardEvent) => {
      if (ev.key === "Enter") save.click();
    });
    const note = s.createDiv({ cls: "vm-muted vm-small-text", text: `A warning appears at ${u.budget.warn_pct}%. At 100%, the program stops before the next paid request and asks whether to continue. Configure warning thresholds, large-run estimates, and profile limits ` });
    const a = note.createEl("a", { cls: "vm-link", text: "in settings" });
    a.addEventListener("click", () => this.plugin.openSettings("costs"));
    note.appendText(".");
  }

  private renderProfiles(el: HTMLElement, u: UsageSummary, per: Period) {
    const s = this.section(el, "Models", PERIOD_IN[per]);
    const list = u.profiles.filter((x) => x.exists || x.totals.all.calls);
    if (!list.length) s.createDiv({ cls: "vm-muted", text: "No profiles." });
    for (const pr of list) this.renderProfileCard(s, pr, per);
  }

  private renderProfileCard(el: HTMLElement, pr: UsageProfile, per: Period) {
    const p = this.plugin;
    const emb = pr.kind === "emb";
    const card = el.createDiv({ cls: "vm-card vm-prof" + (pr.exists ? "" : " is-muted") + (pr.active ? " is-active" : "") });
    const h = card.createDiv({ cls: "vm-prof-head" });
    h.createSpan({ cls: "vm-prof-name", text: emb ? `Embeddings · ${pr.model || pr.name}` : pr.name });
    if (pr.ptype) h.createSpan({ cls: "vm-chip", text: PTYPE_RU[pr.ptype] || pr.ptype });
    if (pr.active) h.createSpan({ cls: "vm-chip is-accent", text: "main" });
    if (!pr.exists) h.createSpan({ cls: "vm-chip is-muted", text: emb ? "previous model" : "profile removed" });
    const meta: string[] = [];
    if (pr.model && !emb) meta.push(pr.model);
    if (pr.steps.length) meta.push("steps: " + pr.steps.join(", "));
    if (meta.length) card.createDiv({ cls: "vm-muted vm-small-text", text: meta.join(" · ") });
    const t: UsageTotals = pr.totals[per];
    card.createDiv({ cls: "vm-prof-usage", text: t.calls ? usageLine(t, { time: pr.ptype === "local", cost: pr.ptype === "cloud" }) : `No requests ${PERIOD_IN[per]}` });
    if (pr.budget_month) {
      const pct = pr.budget_pct ?? 0;
      const w = card.createDiv({ cls: "vm-budget" + (pr.budget_state ? ` is-${pr.budget_state}` : "") });
      w.createDiv({ cls: "vm-budget-text vm-small-text", text: `Profile limit: ${money(pr.totals.month.cost)} of ${money(pr.budget_month)} this month · ${pctText(pct)}` });
      w.createDiv({ cls: "vm-bar" }).createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.min(100, pct)}%`;
    }
    if (pr.ptype !== "cloud" || !pr.exists) return;
    // cloud-model prices
    const id = emb ? "emb" : pr.id!;
    const draft = this.priceDraft.get(id) || {};
    const prices = pr.prices || { input: null, cached_input: null, output: null };
    const box = card.createDiv({ cls: "vm-prices" });
    box.createDiv({ cls: "vm-small-text vm-prices-title", text: "Prices, $ per million tokens" + (pr.priced ? "" : " — not set; cost is not calculated") });
    if (!pr.priced) box.addClass("is-unpriced");
    const fields: [string, string, number | null][] = emb
      ? [["input", "input", prices.input]]
      : [["input", "input", prices.input], ["cached_input", "cached input", prices.cached_input], ["output", "output", prices.output]];
    const inputs: Record<string, HTMLInputElement> = {};
    const row = box.createDiv({ cls: "vm-prices-row" });
    for (const [k, label, v] of fields) {
      const f = row.createDiv({ cls: "vm-price" });
      f.createDiv({ cls: "vm-muted vm-small-text", text: label });
      const inp = f.createEl("input", { type: "text", cls: "vm-num", attr: { inputmode: "decimal", placeholder: k === "cached_input" ? "same as input" : "—" } });
      inp.value = k in draft ? draft[k] : v != null ? String(v) : "";
      inp.addEventListener("input", () => {
        const d = this.priceDraft.get(id) || {};
        d[k] = inp.value;
        this.priceDraft.set(id, d);
        inp.removeClass("vm-invalid");
      });
      inputs[k] = inp;
    }
    const b = row.createDiv({ cls: "vm-price vm-price-btn" });
    const save = this.button(b, "Save", async () => {
      const out: Record<string, number | null> = {};
      for (const [k] of fields) {
        const v = parseNumber(inputs[k].value, "float", 0, 1000);
        if (v === null) {
          inputs[k].addClass("vm-invalid");
          new Notice("Enter a price from 0 to 1000 dollars per million tokens.");
          return;
        }
        out[k] = v === undefined ? null : v;
      }
      save.disabled = true;
      const patch = emb ? { embeddings: { price_input: out.input } } : { llm: { profiles: { [id]: { prices: out } } } };
      const r = await p.patchSettings(patch);
      if (!r.ok) {
        new Notice(r.error || "Prices not saved.", 12000);
        save.disabled = false;
        return;
      }
      this.priceDraft.delete(id);
      new Notice(`Prices saved for ${emb ? "embeddings" : pr.name}.`);
      if (pr.totals.all.calls) {
        const ok = await p.confirm({
          title: "Recalculate past requests?",
          text: `${emb ? "Embeddings" : pr.name} already has ${nCalls(pr.totals.all.calls)}. Recalculate their cost using the new prices?\n\nOtherwise, the new prices will apply from now on and past requests will retain their original calculated costs.`,
          ok: "Recalculate",
          cancel: "No",
        });
        if (ok) {
          const rr = await p.reprice(id);
          if (rr.ok) new Notice(rr.repriced ? `Cost recalculated for ${rr.repriced} requests.` : "There is nothing to recalculate; the cost has not changed.");
          else new Notice(rr.error || "Not recalculated.", 12000);
        }
      }
      this.render(true);
    }, "cta");
  }

  private renderSteps(el: HTMLElement, u: UsageSummary, per: Period) {
    const rows = u.steps.filter((x) => x.totals[per].calls);
    if (!rows.length) return;
    const s = this.section(el, "By step", PERIOD_IN[per]);
    const tb = s.createDiv({ cls: "vm-table" });
    const hr = tb.createDiv({ cls: "vm-tr is-head" });
    for (const h of ["Step", "Requests", "Tokens", "Cost"]) hr.createDiv({ cls: "vm-td", text: h });
    for (const st of rows) {
      const t = st.totals[per];
      const r = tb.createDiv({ cls: "vm-tr" });
      r.createDiv({ cls: "vm-td", text: st.name });
      r.createDiv({ cls: "vm-td is-num", text: num(t.calls) });
      r.createDiv({ cls: "vm-td is-num", text: compact(t.in + t.out), attr: { title: `input ${num(t.in)}, output ${num(t.out)}` } });
      r.createDiv({ cls: "vm-td is-num", text: t.cost || t.unpriced ? money(t.cost) + (t.unpriced ? "*" : "") : "—" });
    }
  }

  private renderDays(el: HTMLElement, u: UsageSummary) {
    const days = u.days || [];
    if (!days.some((d) => d.calls)) return;
    const byCost = days.some((d) => d.cost > 0);
    const s = this.section(el, "By day", byCost ? "cost, last 31 days" : "requests, last 31 days");
    const max = Math.max(...days.map((d) => (byCost ? d.cost : d.calls)), byCost ? 0.0001 : 1);
    const chart = s.createDiv({ cls: "vm-chart" });
    for (const d of days) {
      const v = byCost ? d.cost : d.calls;
      const col = chart.createDiv({ cls: "vm-chart-col" + (d.date === u.today ? " is-today" : ""), attr: { title: `${ruDateTime(d.date)}: ${d.calls ? usageLine(d) : "No requests"}` } });
      const bar = col.createDiv({ cls: "vm-chart-bar" });
      bar.style.height = v ? `${Math.max(3, Math.round((v / max) * 100))}%` : "0";
    }
    const lab = s.createDiv({ cls: "vm-chart-labels vm-muted vm-small-text" });
    lab.createSpan({ text: ruDateTime(days[0].date).slice(0, 5) });
    lab.createSpan({ text: `maximum: ${byCost ? money(max) : num(max)} per day` });
    lab.createSpan({ text: "today" });
  }

  private renderRuns(el: HTMLElement, u: UsageSummary) {
    if (!u.runs?.length) return;
    const s = this.section(el, "Recent runs");
    for (const r of u.runs.slice(0, 12)) {
      const row = s.createDiv({ cls: "vm-urun" });
      row.createSpan({ cls: "vm-muted vm-small-text vm-urun-when", text: ruDateTime(r.started) });
      row.createSpan({ cls: "vm-urun-what", text: RUN_NAMES[r.cmd || ""] || r.cmd || "launch" });
      row.createSpan({ cls: "vm-small-text vm-urun-usage", text: usageLine(r, { time: !r.cost && r.sec > 0 }) });
    }
  }

  // ---------- Questions ----------
  private renderQuestions(el: HTMLElement, ui: UiSnapshot | null) {
    if (!ui) {
      this.callout(el, "info", "Status not loaded yet", null);
      return;
    }
    const p = this.plugin;
    let qs = ui.questions;
    const fc = this.byId(this.qFilter);
    if (fc) {
      const bar = el.createDiv({ cls: "vm-filter" });
      bar.createSpan({ text: "Questions only for " });
      const chip = bar.createSpan({ cls: "vm-chip is-link" });
      this.dot(chip, fc.color);
      chip.appendText(`«${fc.title}» ×`);
      chip.addEventListener("click", () => {
        this.qFilter = null;
        this.render(true);
      });
      qs = qs.filter((q) => q.container === fc.id);
    }
    if (!qs.length) {
      this.callout(el, "ok", "There are no open questions", fc ? "There are no questions for this container." : null);
      if (ui.status.pending_work) {
        const c = this.callout(el, "info", "Processing is incomplete", "Some entries were waiting for answers. Continue processing.");
        this.button(c.createDiv({ cls: "vm-buttons" }), "Continue processing (Phase 1)", () => p.runPhase1(), "cta", p.engine.busy());
      }
      return;
    }
    if (p.engine.busy()) this.callout(el, "info", null, "The program is running. Your answer will be queued and applied immediately after the current run.");
    for (const q of qs) this.renderQuestion(el, q);
    if (ui.status.pending_work) {
      const c = this.callout(el, "info", null, "After answering, continue processing to place entries that were waiting for answers.");
      this.button(c.createDiv({ cls: "vm-buttons" }), "Continue processing (Phase 1)", () => p.runPhase1(), "cta", p.engine.busy());
    }
  }

  private renderQuestion(el: HTMLElement, q: UiQuestion) {
    const p = this.plugin;
    const job = p.engine.find((j: Job) => j.args[0] === "answer" && j.args[1] === q.id);
    const card = el.createDiv({ cls: "vm-card vm-q" + (job ? " is-pending" : "") });
    const head = card.createDiv({ cls: "vm-q-head" });
    head.createDiv({ cls: "vm-q-title", text: q.title });
    head.createDiv({ cls: "vm-q-meta", text: q.id + (q.created ? ` · ${ruDateTime(q.created)}` : "") });
    const c = this.byId(q.container);
    if (c || q.entity_path) {
      const links = card.createDiv({ cls: "vm-q-links" });
      if (c) {
        const chip = links.createSpan({ cls: "vm-chip is-link", attr: { title: "Open container in the panel" } });
        this.dot(chip, c.color);
        chip.appendText(c.title);
        chip.addEventListener("click", () => this.show("container", c.id));
      }
      if (q.entity_path) {
        const a = links.createEl("a", { cls: "vm-link", text: "Open entry" });
        a.addEventListener("click", () => p.open(q.entity_path!));
      }
    }
    const text = card.createDiv({ cls: "vm-q-text markdown-rendered" });
    MarkdownRenderer.render(this.app, q.text, text, q.entity_path || "", this).then(() => this.hookLinks(text));
    if (q.note) card.createDiv({ cls: "vm-q-note", text: q.note });
    const err = this.answerError.get(q.id);
    if (err && err !== q.note) card.createDiv({ cls: "vm-q-note", text: err });
    if (job) card.createDiv({ cls: "vm-q-state", text: job.status === "queued" ? "Queued; will be applied after the current run…" : "Applying answer…" });
    if (q.options.length) {
      const opts = card.createDiv({ cls: "vm-q-options" });
      for (const o of q.options) {
        const b = opts.createEl("button", { cls: "vm-q-option", text: o.label });
        b.disabled = !!job;
        b.addEventListener("click", () => this.answer(q, o.index, null));
      }
    }
    if (q.free_text) {
      const box = card.createDiv({ cls: "vm-q-free" });
      const ta = box.createEl("textarea", { attr: { rows: "2", placeholder: q.free_hint || "Your answer." } });
      ta.value = this.freeText.get(q.id) || "";
      ta.addEventListener("input", () => this.freeText.set(q.id, ta.value));
      const b = box.createEl("button", { text: "Reply", cls: "mod-cta" });
      b.disabled = !!job;
      b.addEventListener("click", () => {
        const t = ta.value.trim();
        if (!t) {
          new Notice("Enter an answer.");
          ta.focus();
          return;
        }
        this.answer(q, null, t);
      });
    }
  }

  private async answer(q: UiQuestion, option: number | null, text: string | null) {
    this.answerError.delete(q.id);
    const pr = this.plugin.answer(q, option, text);
    this.render(true);
    const r = await pr;
    if (r.ok && r.accepted) {
      this.freeText.delete(q.id);
      new Notice(`Answer ${q.id} accepted.`);
    } else this.answerError.set(q.id, r.note || r.error || "Answer not accepted.");
    this.render();
  }

  // ---------- Container ----------
  private renderContainerTab(el: HTMLElement, ui: UiSnapshot | null) {
    if (!ui || !ui.containers.length) {
      this.callout(el, "info", "No containers yet", "They will appear after the structure is approved.");
      return;
    }
    const bar = el.createDiv({ cls: "vm-cbar" });
    const sel = bar.createEl("select", { cls: "dropdown" });
    sel.createEl("option", { text: "— select a container —", attr: { value: "" } });
    for (const c of ui.containers) sel.createEl("option", { text: "\u00a0\u00a0\u00a0".repeat(c.depth) + c.title, attr: { value: c.id } });
    sel.value = this.selectedId || "";
    sel.addEventListener("change", () => {
      this.follow = false;
      this.selectedId = sel.value || null;
      this.render(true);
    });
    const fb = bar.createEl("button", {
      cls: "vm-small" + (this.follow ? " is-active" : ""),
      text: this.follow ? "✓ follow open note" : "follow open note",
      attr: { title: "Show the container of the note open in the editor" },
    });
    fb.addEventListener("click", () => {
      this.follow = true;
      const f = this.app.workspace.getActiveFile();
      const c = f ? containerOfPath(ui, f.path) : null;
      if (c) this.selectedId = c.id;
      this.render(true);
    });
    const c = this.byId(this.selectedId);
    if (!c) {
      el.createDiv({ cls: "vm-empty", text: "Open a note from the container folder or select the container in the list." });
      return;
    }
    this.renderContainerHead(el, ui, c);
    this.renderDocs(el, c);
    this.renderThresholds(el, ui, c);
    this.renderStyle(el, c);
  }

  private renderContainerHead(el: HTMLElement, ui: UiSnapshot, c: UiContainer) {
    const p = this.plugin;
    const head = el.createDiv({ cls: "vm-card vm-chead" });
    head.style.borderLeftColor = c.color || "var(--interactive-accent)";
    const chain = parentsOf(ui, c);
    if (chain.length) head.createDiv({ cls: "vm-muted vm-small-text", text: chain.map((x) => x.title).join(" › ") + " ›" });
    const t = head.createDiv({ cls: "vm-chead-title" });
    const a = t.createEl("a", { cls: "vm-link", text: c.title, attr: { title: "Open container note" } });
    a.addEventListener("click", () => p.open(c.path));
    if (c.description) head.createDiv({ cls: "vm-cdesc", text: c.description });

    const meta = head.createDiv({ cls: "vm-cmeta" });
    const typeSel = meta.createEl("select", { cls: "dropdown", attr: { title: "Type of container" } });
    for (const [k, v] of Object.entries(ui.types || {})) typeSel.createEl("option", { text: v, attr: { value: k } });
    typeSel.value = c.type;
    typeSel.addEventListener("change", () => p.setContainerField(c, "type", typeSel.value, `type: ${ui.types[typeSel.value]}`));
    const stSel = meta.createEl("select", { cls: "dropdown", attr: { title: "Container status" } });
    for (const [k, v] of Object.entries(ui.statuses || {})) stSel.createEl("option", { text: v, attr: { value: k } });
    stSel.value = c.status;
    stSel.addEventListener("change", () => p.setContainerField(c, "container_status", stSel.value, `status: ${ui.statuses[stSel.value]}`));

    const facts = head.createDiv({ cls: "vm-facts" });
    const fact = (k: string, v: string, onClick?: () => void) => {
      const r = facts.createDiv({ cls: "vm-fact" });
      r.createSpan({ cls: "vm-fact-k", text: k });
      const val = r.createSpan({ cls: "vm-fact-v" + (onClick ? " vm-link" : ""), text: v });
      if (onClick) val.addEventListener("click", onClick);
    };
    fact("Records.", nRecords(c.entities) + (c.shared ? `, common: ${c.shared}` : ""));
    if (c.questions)
      fact("Questions", nQuestions(c.questions), () => {
        this.qFilter = c.id;
        this.show("questions");
      });
    if (c.base) {
      fact("Synthesis base", `${c.base.items} aspects, primary ${c.base.primary}` + (c.base.conflicts ? `, contradiction ${c.base.conflicts}` : ""));
      if (c.base.excluded) fact("Below the Value Threshold", String(c.base.excluded));
    } else fact("Synthesis base", "not yet assembled");
    if (c.dirty) fact("Reassembly", "the base will be rebuilt during Phase 1" + (c.dirty_reasons.length ? ` (${c.dirty_reasons.join(", ")})` : ""));
    if (c.last_modified) fact("Changed.", ruDateTime(c.last_modified));
    const views = head.createDiv({ cls: "vm-links-row" });
    if (c.views.pool) views.createEl("a", { cls: "vm-link", text: "pool" }).addEventListener("click", () => p.open(c.views.pool!));
    if (c.views.base) views.createEl("a", { cls: "vm-link", text: "synthesis" }).addEventListener("click", () => p.open(c.views.base!));
  }

  private renderDocs(el: HTMLElement, c: UiContainer) {
    const p = this.plugin;
    const s = this.section(el, "Documents");
    if (!c.products.length) s.createDiv({ cls: "vm-muted", text: "No documents yet." });
    for (const d of c.products) {
      const row = s.createDiv({ cls: "vm-doc" });
      row.createEl("a", { cls: "vm-link", text: d.title }).addEventListener("click", () => p.open(d.path));
      if (d.needs_review) row.createSpan({ cls: "vm-chip is-warning", text: "Under review", attr: { title: "Review requested: the document contains annotations" } });
    }
    const b = s.createDiv({ cls: "vm-buttons" });
    this.button(b, c.products.length ? "Update documents (Phase 2)" : "Write documents (Phase 2)", () => p.runSynth(c), "cta");
    this.button(b, "Recheck placement", () => p.runRevalidate(c));
  }

  private renderThresholds(el: HTMLElement, ui: UiSnapshot, c: UiContainer) {
    const p = this.plugin;
    const s = this.section(el, "Container thresholds");
    s.createDiv({
      cls: "vm-muted vm-small-text",
      text: "Custom values apply to this container and its children. Leave a field empty to inherit from the parent or use the global setting, shown in gray. Use ↺ to remove a custom value.",
    });
    const draft = this.thrDraft.get(c.id) || {};
    const names = Object.keys(ui.threshold_info).filter((k) => ui.threshold_info[k].per_container && (k !== "seed_dormancy_days" || c.type === "seed"));
    const table = s.createDiv({ cls: "vm-thr" });
    const inputs: Record<string, HTMLInputElement> = {};
    let save: HTMLButtonElement;
    let reset: HTMLButtonElement;
    const collect = (): { changes: Record<string, number | null>; bad: string[] } => {
      const changes: Record<string, number | null> = {};
      const bad: string[] = [];
      for (const k of names) {
        const inp = inputs[k];
        const info = ui.threshold_info[k];
        const v = parseNumber(inp.value, info.kind, info.min, info.max);
        const own = c.overrides[k];
        inp.toggleClass("vm-invalid", v === null);
        if (v === null) bad.push(info.label);
        else if (v === undefined) {
          if (own !== undefined) changes[k] = null;
        } else if (v !== own) changes[k] = v;
      }
      return { changes, bad };
    };
    const upd = () => {
      const { changes, bad } = collect();
      const n = Object.keys(changes).length;
      save.disabled = !n || bad.length > 0;
      reset.disabled = !n && !bad.length;
      save.setText(n ? `Save (${n})` : "Save");
    };
    for (const k of names) {
      const info = ui.threshold_info[k];
      const tv = c.thresholds[k];
      const own = c.overrides[k];
      // what will happen without meaning: The parent with the parent or the parent with the parent.
      let inherited = ui.thresholds[k];
      let inhFrom: string | null = null;
      const chain = parentsOf(ui, c);
      for (let i = chain.length - 1; i >= 0; i--) {
        const o = chain[i].overrides[k];
        if (o !== undefined) {
          inherited = o;
          inhFrom = chain[i].title;
          break;
        }
      }
      const row = table.createDiv({ cls: "vm-thr-row" + (own !== undefined ? " is-own" : "") });
      const top = row.createDiv({ cls: "vm-thr-top" });
      const lab = top.createDiv({ cls: "vm-thr-label", attr: { title: info.help } });
      lab.createSpan({ text: info.label });
      const src = top.createDiv({ cls: "vm-thr-src" });
      const help = row.createDiv({ cls: "vm-thr-help vm-hidden", text: `${info.help} Allowed: ${rangeText(info.kind, info.min, info.max)}.` });
      lab.addEventListener("click", () => help.toggleClass("vm-hidden", !help.hasClass("vm-hidden")));
      const ctl = row.createDiv({ cls: "vm-thr-ctl" });
      const rng = ctl.createEl("input", { type: "range", cls: "slider vm-thr-range" });
      rng.min = String(info.min);
      rng.max = String(info.max);
      rng.step = String(info.step || (info.kind === "int" ? 1 : 0.01));
      const inp = ctl.createEl("input", { type: "text", cls: "vm-thr-input", attr: { inputmode: "decimal" } });
      inp.value = k in draft ? draft[k] : own !== undefined ? String(own) : "";
      inp.placeholder = inherited != null ? String(inherited) : tv ? String(tv.value) : "";
      const resetTip = `Remove the custom threshold; use ${inhFrom ? `the value from “${inhFrom}”` : "the global value"} (${inherited})`;
      const rs = ctl.createEl("button", { cls: "vm-thr-reset", text: "↺", attr: { title: resetTip } });
      inputs[k] = inp;
      const decimals = (String(rng.step).split(".")[1] || "").length;
      const sync = () => {
        const v = parseNumber(inp.value, info.kind, info.min, info.max);
        const empty = !inp.value.trim();
        rng.value = String(typeof v === "number" ? v : inherited ?? info.min);
        rng.toggleClass("is-inherited", empty);
        // ↺ always visible (slidefield «leaper»); doorless — dull and unpressed
        rs.disabled = empty;
        rs.toggleClass("vm-reset-off", empty);
        rs.setAttr("title", empty ? `No custom threshold; using ${inhFrom ? `the value from “${inhFrom}”` : "the global value"} (${inherited})` : resetTip);
        src.setText(!empty ? (v === own ? "custom" : "custom, unsaved") : inhFrom ? `from “${inhFrom}”` : "global");
        row.toggleClass("is-own", !empty);
      };
      const changed = () => {
        const d = this.thrDraft.get(c.id) || {};
        d[k] = inp.value;
        this.thrDraft.set(c.id, d);
        sync();
        upd();
      };
      rng.addEventListener("input", () => {
        inp.value = Number(rng.value).toFixed(decimals);
        changed();
      });
      inp.addEventListener("input", changed);
      rs.addEventListener("click", (ev) => {
        ev.preventDefault();
        inp.value = "";
        changed();
      });
      inp.addEventListener("keydown", (ev: KeyboardEvent) => {
        if (ev.key === "Enter" && !save.disabled) save.click();
      });
      sync();
    }
    const b = s.createDiv({ cls: "vm-buttons" });
    save = this.button(b, "Save", async () => {
      const { changes, bad } = collect();
      if (bad.length) return;
      save.disabled = true;
      const ok = await p.saveThresholds(c, changes);
      if (ok) {
        this.thrDraft.delete(c.id);
        new Notice(`Thresholds saved for “${c.title}”; they apply from the next Phase 1 run.`);
      }
      this.render(true);
    }, "cta");
    reset = this.button(b, "Cancel edit", () => {
      this.thrDraft.delete(c.id);
      this.render(true);
    });
    this.button(b, "Consult AI", () => p.openAdvice(c));
    upd();
    const last = p.advice.get(c.id);
    if (last) {
      const a = this.callout(s, "accent", "AI advice is available.", `${ruDateTime(last.at)}: ${last.advice.summary}`);
      this.button(a.createDiv({ cls: "vm-buttons" }), "Show advice", () => p.openAdvice(c, last.advice));
    }
    s.createDiv({
      cls: "vm-muted vm-small-text",
      text: "Placement and compaction thresholds apply to new entries. Value thresholds rebuild the synthesis base on the next Phase 1 run without model requests.",
    });
  }

  private renderStyle(el: HTMLElement, c: UiContainer) {
    const p = this.plugin;
    const s = this.section(el, "Document style");
    const inherited = !c.style && c.style_effective
      ? `Inherited style from “${c.style_from}”: ${c.style_effective}`
      : "For example: Write in English as a business plan, with figures and deadlines.";
    const ta = s.createEl("textarea", { cls: "vm-style", attr: { rows: "3", placeholder: inherited } });
    ta.value = this.styleDraft.get(c.id) ?? c.style;
    const b = s.createDiv({ cls: "vm-buttons" });
    const save = this.button(b, "Save style", async () => {
      save.disabled = true;
      const ok = await p.saveStyle(c, ta.value.trim());
      if (ok) {
        this.styleDraft.delete(c.id);
        new Notice(`Style saved for “${c.title}”; it applies to the next Phase 2 run.`);
      }
      this.render(true);
    }, "cta");
    const upd = () => {
      save.disabled = ta.value.trim() === (c.style || "").trim();
    };
    ta.addEventListener("input", () => {
      this.styleDraft.set(c.id, ta.value);
      upd();
    });
    upd();
    s.createDiv({
      cls: "vm-muted vm-small-text",
      text: "Added to and takes precedence over the global style in settings. Also applies to child containers unless they have their own style.",
    });
  }

  // ---------- Journal ----------
  private renderLog(el: HTMLElement, ui: UiSnapshot | null) {
    const p = this.plugin;
    const eng = p.engine;
    const logs = this.section(el, "Logs of the program");
    const lb = logs.createDiv({ cls: "vm-buttons" });
    const L = ui?.logs || {};
    if (L.changes) this.button(lb, "Change log", () => p.open(L.changes!));
    if (L.reasoning) this.button(lb, "Model reasoning", () => p.open(L.reasoning!));
    if (L.archive) this.button(lb, "Archive of questions", () => p.open(L.archive!));
    if (L.errors) this.button(lb, "Errors", () => p.open(L.errors!));
    this.button(lb, "open-questions.md", () => p.open("open-questions.md"));

    const s = this.section(el, "Runs in this session");
    const jobs: Job[] = [];
    if (eng.current && !eng.current.quiet) jobs.push(eng.current);
    jobs.push(...eng.pending(), ...eng.history);
    if (!jobs.length) {
      s.createDiv({ cls: "vm-muted", text: "No runs yet." });
      return;
    }
    const icon: Record<string, string> = { queued: "⧗", running: "▶", done: "✓", failed: "✗", stopped: "■", cancelled: "–" };
    for (const j of jobs) {
      const card = s.createDiv({ cls: `vm-job is-${j.status}` });
      const h = card.createDiv({ cls: "vm-job-head" });
      h.createSpan({ cls: "vm-job-icon", text: icon[j.status] || "" });
      h.createSpan({ cls: "vm-job-label", text: j.label });
      const when = j.startedAt ? clock(j.startedAt) : clock(j.queuedAt);
      const dur = j.startedAt ? duration((j.finishedAt || Date.now()) - j.startedAt) : "queued";
      h.createSpan({ cls: "vm-muted vm-job-time", text: `${when} · ${dur}` });
      const r = j.result;
      if (r) {
        const sl = statsLine(r.stats);
        if (r.unchanged) card.createDiv({ text: "Documents are up to date; nothing was rewritten." });
        else if (r.title && r.ok) card.createDiv({ text: r.title + (sl ? ` — ${sl}` : "") });
        if (r.error) card.createDiv({ cls: "vm-job-error", text: r.error });
        const cl = callsLine(r.calls);
        if (cl) card.createDiv({ cls: "vm-muted vm-small-text", text: cl });
        const ru = r.run_usage;
        if (ru && ru.calls) {
          const extra = [ru.cost ? money(ru.cost) + (ru.unpriced ? "*" : "") : "", ru.sec ? `model time ${durationText(ru.sec)}` : "", r.elapsed ? `run ${durationText(r.elapsed)}` : ""].filter(Boolean);
          card.createDiv({ cls: "vm-muted vm-small-text", text: `Tokens ${compact(ru.in)} → ${compact(ru.out)}` + (extra.length ? " · " + extra.join(" · ") : "") });
        }
        for (const w of r.warnings || []) card.createDiv({ cls: "vm-small-text vm-warn-line", text: "! " + w });
        for (const n of r.notices || []) card.createDiv({ cls: "vm-small-text vm-muted", text: "• " + n });
      }
      if (j.lines.length || j.args.length) {
        const open = this.openJobs.has(j.id);
        const t = card.createEl("a", { cls: "vm-link vm-small-text", text: open ? "hide program output" : "program output" });
        t.addEventListener("click", () => {
          if (open) this.openJobs.delete(j.id);
          else this.openJobs.add(j.id);
          this.render(true);
        });
        if (open) {
          const text = [`$ brain ${j.args.join(" ")}`, ...j.lines.slice(-400)].join("\n") + (j.stderr ? `\n--- stderr ---\n${j.stderr.slice(-4000)}` : "");
          card.createEl("pre", { cls: "vm-pre", text });
        }
      }
    }
  }
}

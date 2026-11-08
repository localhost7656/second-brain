// Plugin windows: confirmation, choice (programme, update), containerization, «New thought»,
// AI Threshold Council, check-in, text, launch of his embedding model.
import { App, FuzzySuggestModal, Modal, Notice, Setting } from "obsidian";
import type BrainPlugin from "./main";
import type { Advice, AdviceRec, AskEvent, CheckItem, LlamaHardware, LlamaParams, LlamaStatus, RunResult, UiContainer } from "./types";
import { copyText } from "./report";
import { containerLabel, fileSlug, nowHm, plural, sizeText, todayIso } from "./util";

// ---------- confirmation ----------
interface ConfirmOpts {
  title: string;
  text: string;
  ok: string;
  cancel?: string;
  warning?: boolean;
}

class ConfirmModal extends Modal {
  private answered = false;
  constructor(app: App, private o: ConfirmOpts, private done: (v: boolean) => void) {
    super(app);
  }
  onOpen() {
    this.setTitle(this.o.title);
    this.contentEl.addClass("vm-modal");
    for (const p of this.o.text.split("\n\n")) this.contentEl.createEl("p", { text: p });
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    const ok = b.createEl("button", { text: this.o.ok, cls: this.o.warning ? "mod-warning" : "mod-cta" });
    ok.addEventListener("click", () => this.answer(true));
    b.createEl("button", { text: this.o.cancel || "Cancel" }).addEventListener("click", () => this.answer(false));
    window.setTimeout(() => ok.focus(), 0);
  }
  private answer(v: boolean) {
    this.answered = true;
    this.done(v);
    this.close();
  }
  onClose() {
    this.contentEl.empty();
    if (!this.answered) this.done(false);
  }
}

export function confirmModal(app: App, o: ConfirmOpts): Promise<boolean> {
  return new Promise((resolve) => new ConfirmModal(app, o, resolve).open());
}

// ---------- choice ----------
export interface ChoiceOpts {
  title: string;
  /** subtitle */
  sub?: string;
  /** paragraph-by-line */
  text?: string;
  /** line (launcher, changed) */
  lines?: string[];
  /** long text as it is (description) */
  pre?: string;
  options: { label: string; kind?: "cta" | "warning" }[];
  note?: string;
  cls?: string;
}

export class ChoiceModal extends Modal {
  private answered = false;
  constructor(app: App, private o: ChoiceOpts, private done: (choice: number | null) => void) {
    super(app);
  }
  onOpen() {
    const o = this.o;
    this.setTitle(o.title);
    const el = this.contentEl;
    el.addClass("vm-modal", "vm-choice");
    if (o.cls) this.modalEl.addClass(o.cls);
    if (o.sub) el.createDiv({ cls: "vm-muted vm-small-text vm-choice-sub", text: o.sub });
    for (const p of (o.text || "").split("\n\n").filter((x) => x.trim())) el.createEl("p", { text: p });
    if (o.lines?.length) {
      const ul = el.createEl("ul", { cls: "vm-choice-lines" });
      for (const ln of o.lines) ul.createEl("li", { text: ln });
    }
    if (o.pre) el.createEl("pre", { cls: "vm-pre vm-choice-pre", text: o.pre });
    const b = el.createDiv({ cls: "vm-modal-buttons" });
    let first: HTMLButtonElement | null = null;
    o.options.forEach((opt, i) => {
      const btn = b.createEl("button", { text: opt.label, cls: opt.kind === "cta" ? "mod-cta" : opt.kind === "warning" ? "mod-warning" : "" });
      btn.addEventListener("click", () => this.choose(i));
      if (opt.kind === "cta" && !first) first = btn;
    });
    if (o.note) el.createDiv({ cls: "vm-muted vm-small-text", text: o.note });
    window.setTimeout(() => (first as HTMLButtonElement | null)?.focus(), 0);
  }
  choose(i: number | null) {
    if (this.answered) return;
    this.answered = true;
    this.done(i);
    this.close();
  }
  onClose() {
    this.contentEl.empty();
    if (!this.answered) {
      this.answered = true;
      this.done(null);
    }
  }
}

/** Open the selection window. close() — lock up (reply — null). */
export function choiceModal(app: App, o: ChoiceOpts): { result: Promise<number | null>; close: () => void } {
  let m: ChoiceModal | null = null;
  const result = new Promise<number | null>((resolve) => {
    m = new ChoiceModal(app, o, resolve);
    m.open();
  });
  return { result, close: () => m?.close() };
}

/** The program in the middle of the launch (@@ASK): budget exhausted, launch, validation. */
export function askOptions(ask: AskEvent): ChoiceOpts {
  const opts = ask.options.map((label, i) => {
    let kind: "cta" | "warning" | undefined;
    if (ask.id === "budget") kind = i === 0 ? "warning" : i === 1 ? "cta" : undefined;
    else if (i === 0) kind = "cta";
    return { label, kind };
  });
  const note = ask.id === "budget"
    ? "Stopping is safe: processed items are saved and the next run will continue. Set the budget under Settings > Expenses."
    : ask.id === "estimate"
      ? "Set the confirmation threshold under Settings > Expenses. Closing this window is the same as Cancel."
      : "Closing this window is the same as declining.";
  return { title: ask.title, text: ask.text, lines: ask.lines, options: opts, note, cls: "vm-ask" };
}

// ---------- simple (error-log, output) ----------
export class TextModal extends Modal {
  constructor(app: App, private title: string, private text: string) {
    super(app);
  }
  onOpen() {
    this.setTitle(this.title);
    this.modalEl.addClass("vm-wide");
    this.contentEl.createEl("pre", { cls: "vm-pre", text: this.text || "(empty)" });
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "Copy" }).addEventListener("click", async () => {
      new Notice((await copyText(this.text)) ? "Copied" : "Could not copy. Select the text and press Ctrl+C.");
    });
    b.createEl("button", { text: "Close" }).addEventListener("click", () => this.close());
  }
  onClose() {
    this.contentEl.empty();
  }
}

// ---------- containerization ----------
export interface PickItem {
  c: UiContainer | null; // null — «container-wise»
  label: string;
}

export class ContainerPicker extends FuzzySuggestModal<PickItem> {
  constructor(private plugin: BrainPlugin, private allLabel: string | null, private onPick: (c: UiContainer | null) => void) {
    super(plugin.app);
    this.setPlaceholder("Start typing a container name");
  }
  getItems(): PickItem[] {
    const ui = this.plugin.ui;
    const out: PickItem[] = [];
    if (this.allLabel) out.push({ c: null, label: this.allLabel });
    for (const c of ui?.containers || []) out.push({ c, label: ui ? containerLabel(ui, c) : c.title });
    return out;
  }
  getItemText(it: PickItem): string {
    return it.label;
  }
  onChooseItem(it: PickItem): void {
    this.onPick(it.c);
  }
}

// ---------- thought ----------
export class NewThoughtModal extends Modal {
  constructor(private plugin: BrainPlugin, private hint = "") {
    super(plugin.app);
  }
  onOpen() {
    const ui = this.plugin.ui;
    this.setTitle("New thought");
    const el = this.contentEl;
    el.addClass("vm-modal", "vm-thought");
    const ta = el.createEl("textarea", { cls: "vm-thought-text", attr: { rows: "7", placeholder: "What is on your mind? Write it as it comes." } });
    const grid = el.createDiv({ cls: "vm-form" });

    const f1 = grid.createDiv({ cls: "vm-form-row" });
    f1.createEl("label", { text: "Destination", attr: { for: "vm-hint" } });
    const hint = f1.createEl("input", { type: "text", attr: { id: "vm-hint", list: "vm-hint-list", placeholder: "Optional; the program can decide" } });
    hint.value = this.hint;
    const dl = f1.createEl("datalist", { attr: { id: "vm-hint-list" } });
    for (const c of ui?.containers || []) dl.createEl("option", { attr: { value: c.title } });

    const f2 = grid.createDiv({ cls: "vm-form-row" });
    f2.createEl("label", { text: "Date", attr: { for: "vm-date" } });
    const date = f2.createEl("input", { type: "date", attr: { id: "vm-date" } });
    date.value = todayIso();

    const sources = (ui?.sources || []).map((s) => s.name).filter((n) => n && n.toLowerCase() !== "archive");
    const f3 = grid.createDiv({ cls: "vm-form-row" });
    f3.createEl("label", { text: "Source", attr: { for: "vm-src" } });
    const src = f3.createEl("select", { cls: "dropdown", attr: { id: "vm-src" } });
    if (!sources.includes("note")) src.createEl("option", { text: "note", attr: { value: "note" } });
    for (const s of sources) src.createEl("option", { text: s, attr: { value: s } });
    src.value = "note";

    const f4 = el.createDiv({ cls: "vm-check-row" });
    const now = f4.createEl("input", { type: "checkbox", attr: { id: "vm-now" } });
    now.checked = false; // The default thought is waiting for the next phase 1 (sketch out)
    f4.createEl("label", { text: "Process immediately (Phase 1)", attr: { for: "vm-now" } });

    const b = el.createDiv({ cls: "vm-modal-buttons" });
    const save = b.createEl("button", { text: "Save", cls: "mod-cta" });
    b.createEl("button", { text: "Cancel" }).addEventListener("click", () => this.close());
    const go = async () => {
      const text = ta.value.trim();
      if (!text) {
        new Notice("Write a thought.");
        ta.focus();
        return;
      }
      save.disabled = true;
      try {
        const path = await this.plugin.saveThought(text, hint.value.trim(), date.value || todayIso(), src.value);
        this.close();
        if (now.checked) {
          new Notice(`Thought saved: ${path}. Processing now…`);
          this.plugin.runPhase1();
        } else new Notice(`Thought saved: ${path}. It will be processed during the next Phase 1 run.`);
      } catch (e) {
        save.disabled = false;
        new Notice(`Could not save: ${e}`);
      }
    };
    save.addEventListener("click", go);
    ta.addEventListener("keydown", (ev: KeyboardEvent) => {
      if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
        ev.preventDefault();
        go();
      }
    });
    el.createDiv({ cls: "vm-muted vm-small-text", text: "Ctrl+Enter to save. The file will be placed in _staging and marked as a single entry." });
    window.setTimeout(() => ta.focus(), 0);
  }
  onClose() {
    this.contentEl.empty();
  }
}

/** Text of the file «New thoughts»: cap (date, clue, service-line), blank-line, text. */
export function thoughtFile(text: string, hint: string, dateIso: string): { name: string; body: string } {
  const [y, m, d] = dateIso.split("-");
  const head = [`${d}.${m}.${y}`];
  if (hint) head.push(`hint: ${hint}`);
  head.push("mode: steady_state");
  return { name: `${dateIso} ${nowHm()} ${fileSlug(text)}.txt`, body: head.join("\n") + "\n\n" + text.trim() + "\n" };
}

// ---------- AI Threshold Council ----------
function sourceText(r: AdviceRec): string {
  if (r.source === "own") return "current: custom container threshold";
  if (r.source === "parent") return `now — parental «${r.from}»`;
  return "current: global threshold from settings";
}

export class AdviceModal extends Modal {
  private alive = true;
  constructor(private plugin: BrainPlugin, private c: UiContainer, private ready?: Advice) {
    super(plugin.app);
  }
  async onOpen() {
    this.setTitle(`AI Council on Thresholds · ${this.c.title}`);
    this.modalEl.addClass("vm-wide");
    this.contentEl.addClass("vm-modal", "vm-advice");
    if (this.ready) {
      this.show(this.ready);
      return;
    }
    const w = this.contentEl.createDiv({ cls: "vm-wait" });
    w.createDiv({ cls: "vm-progress" });
    w.createDiv({
      text: this.plugin.engine.busy()
        ? "Queued: advice will start after the current run."
        : "The model reviews how the program handled this container: placement errors, unnecessary questions, and what was added to the database.",
    });
    w.createDiv({ cls: "vm-muted", text: "This makes one model request. You can close the window; the advice will remain on the Container tab." });
    const r: RunResult = await this.plugin.adviseNow(this.c);
    if (!this.alive) return;
    this.contentEl.empty();
    if (!r.ok || !r.advice) {
      const box = this.contentEl.createDiv({ cls: "vm-callout is-warning" });
      box.createDiv({ text: r.error || r.title || "Advice not received." });
      this.closeButton();
      return;
    }
    this.show(r.advice);
  }

  private show(a: Advice) {
    const el = this.contentEl;
    el.createDiv({ cls: "vm-advice-summary", text: a.summary || "The model did not provide a conclusion." });
    const chosen = new Set<string>(a.recommendations.map((r) => r.name));
    if (!a.recommendations.length) el.createDiv({ cls: "vm-callout is-ok", text: "No threshold changes needed." });
    let apply: HTMLButtonElement | null = null;
    const upd = () => {
      if (apply) apply.disabled = chosen.size === 0;
    };
    for (const r of a.recommendations) {
      const row = el.createDiv({ cls: "vm-rec" });
      const cb = row.createEl("input", { type: "checkbox" });
      cb.checked = true;
      cb.addEventListener("change", () => {
        if (cb.checked) chosen.add(r.name);
        else chosen.delete(r.name);
        row.toggleClass("is-off", !cb.checked);
        upd();
      });
      const body = row.createDiv({ cls: "vm-rec-body" });
      const h = body.createDiv({ cls: "vm-rec-head" });
      h.createSpan({ cls: "vm-rec-label", text: r.label });
      const v = h.createSpan({ cls: "vm-rec-values" });
      v.createSpan({ cls: "vm-rec-old", text: String(r.current) });
      v.appendText(" → ");
      v.createSpan({ cls: "vm-rec-new", text: String(r.value) });
      body.createDiv({ cls: "vm-muted vm-small-text", text: sourceText(r) });
      body.createDiv({ cls: "vm-rec-reason", text: r.reasoning });
      body.setAttr("title", r.help);
      body.addEventListener("click", () => cb.click());
    }
    if (a.brief.length) {
      const det = el.createEl("details", { cls: "vm-brief" });
      det.createEl("summary", { text: "Basis for the advice" });
      const ul = det.createEl("ul");
      for (const line of a.brief) ul.createEl("li", { text: line });
    }
    const b = el.createDiv({ cls: "vm-modal-buttons" });
    if (a.recommendations.length) {
      apply = b.createEl("button", { text: "Apply selected", cls: "mod-cta" });
      apply.addEventListener("click", async () => {
        const changes: Record<string, number> = {};
        for (const r of a.recommendations) if (chosen.has(r.name)) changes[r.name] = r.value;
        apply!.disabled = true;
        const ok = await this.plugin.saveThresholds(this.c, changes);
        if (ok) {
          new Notice(`Thresholds «${this.c.title}» updated: ` + a.recommendations.filter((r) => chosen.has(r.name)).map((r) => `${r.label.toLowerCase()} ${r.current} → ${r.value}`).join(", "));
          this.plugin.forgetAdvice(this.c.id);
          this.close();
        } else apply!.disabled = false;
      });
    }
    b.createEl("button", { text: "Close" }).addEventListener("click", () => this.close());
    el.createDiv({
      cls: "vm-muted vm-small-text",
      text: "The selected values will be saved to the container's YAML (the thresholds field) and applied from the next Phase 1 run. The program will remember which advice you accepted.",
    });
  }

  private closeButton() {
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "Close" }).addEventListener("click", () => this.close());
  }

  onClose() {
    this.alive = false;
    this.contentEl.empty();
  }
}

// ---------- check-in ----------
export class CheckModal extends Modal {
  private alive = true;
  constructor(private plugin: BrainPlugin) {
    super(plugin.app);
  }
  async onOpen() {
    this.setTitle("Check connection");
    this.contentEl.addClass("vm-modal");
    const w = this.contentEl.createDiv({ cls: "vm-wait" });
    w.createDiv({ cls: "vm-progress" });
    w.createDiv({ text: "Checking the vault, model, and embeddings; this may take a few seconds…" });
    const r = await this.plugin.engine.run(["check"], { label: "Check connection", exclusive: false });
    if (!this.alive) return;
    this.contentEl.empty();
    const items: CheckItem[] = r.check || [];
    const list = this.contentEl.createDiv({ cls: "vm-checklist" });
    for (const it of items) {
      const row = list.createDiv({ cls: "vm-check-item " + (it.ok ? "is-ok" : "is-bad") });
      row.createSpan({ cls: "vm-check-mark", text: it.ok ? "✓" : "✗" });
      const body = row.createDiv();
      body.createDiv({ cls: "vm-check-name", text: it.name });
      body.createDiv({ cls: "vm-muted", text: it.text });
    }
    if (!items.length || r.error) this.contentEl.createDiv({ cls: "vm-callout is-warning", text: r.error || "The program did not respond." });
    else this.contentEl.createDiv({ cls: "vm-callout " + (r.ok ? "is-ok" : "is-warning"), text: r.ok ? "Everything is working." : "There are problems; see the rows marked ✗." });
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "Close", cls: "mod-cta" }).addEventListener("click", () => this.close());
  }
  onClose() {
    this.alive = false;
    this.contentEl.empty();
  }
}

// ---------- launch of his embedding model (llama.cpp) ----------
export const LLAMA_BUILD_RU: Record<string, string> = {
  cpu: "for CPU", vulkan: "Vulkan — for any GPU", cuda: "CUDA — for NVIDIA GPUs", system: "installed on this computer",
};

/** What a build. llama.cpp Youll need it and if its downloaded (It also decides the program). */
export function llamaBuildFor(st: LlamaStatus, p: LlamaParams, nvidia: boolean): { build: string; have: boolean } {
  const have = st.builds || {};
  if (p.device === "cpu" || st.os === "macos") {
    for (const b of ["cpu", "vulkan", "cuda"]) if (have[b]) return { build: b, have: true };
    return st.system ? { build: "system", have: true } : { build: "cpu", have: false };
  }
  let want: string = p.build;
  if (want === "auto" || want === "cpu") want = nvidia ? "cuda" : "vulkan";
  if (want === "cuda" && !(st.os === "win" && st.arch === "x64")) want = "vulkan";
  return { build: want, have: !!have[want] };
}

function gb(x: number | null | undefined): string {
  return x == null ? "?" : `${Math.round(x * 10) / 10}`;
}

/** «Run the model…»: count (graphics-card), context, quantization KV-keto, fluxes.
 *  What do you need? — leap; server address the program will enter into the settings. */
export class LlamaModal extends Modal {
  private st: LlamaStatus;
  private p: LlamaParams;
  private hw: LlamaHardware | null;
  private alive = true;
  private hwEl!: HTMLElement;
  private formEl!: HTMLElement;
  private noteEl!: HTMLElement;
  private startBtn!: HTMLButtonElement;
  constructor(private plugin: BrainPlugin, st: LlamaStatus, private onStart: (p: LlamaParams) => void) {
    super(plugin.app);
    this.st = st;
    this.p = { ...st.defaults, ...st.params };
    this.hw = st.hardware || null;
  }

  async onOpen() {
    const running = this.st.server.running;
    this.setTitle(running ? "Restart embedding model" : "Start embedding model");
    this.modalEl.addClass("vm-wide", "vm-llama-modal");
    const el = this.contentEl;
    el.addClass("vm-modal", "vm-llama");
    el.createDiv({ cls: "vm-muted vm-small-text vm-choice-sub", text: `${this.st.model.title} · llama.cpp · model` });
    this.hwEl = el.createDiv({ cls: "vm-llama-hw" });
    this.formEl = el.createDiv({ cls: "vm-llama-form" });
    this.noteEl = el.createDiv({ cls: "vm-llama-notes" });
    const b = el.createDiv({ cls: "vm-modal-buttons" });
    this.startBtn = b.createEl("button", { text: running ? "Restart" : "Start", cls: "mod-cta" });
    this.startBtn.addEventListener("click", () => this.go());
    b.createEl("button", { text: "Default" }).addEventListener("click", () => {
      this.p = { ...this.st.defaults, models_dir: this.p.models_dir };
      this.renderForm();
    });
    b.createEl("button", { text: "Cancel" }).addEventListener("click", () => this.close());
    this.renderHw();
    this.renderForm();
    if (!this.hw) {
      const st = await this.plugin.llamaStatus(true);
      if (!this.alive) return;
      if (st) {
        this.st = { ...st, params: this.st.params };
        this.hw = st.hardware || null;
      }
      if (!this.hw) this.hw = { ram_gb: null, ram_free_gb: null, cores: null, threads: null, cpu: "", gpus: [], nvidia: false, os: this.st.os, arch: this.st.arch };
      this.renderHw();
      this.renderForm();
    }
  }

  onClose() {
    this.alive = false;
    this.contentEl.empty();
  }

  private renderHw() {
    const el = this.hwEl;
    el.empty();
    const hw = this.hw;
    if (!hw) {
      el.createDiv({ cls: "vm-muted", text: "Detecting computer hardware…" });
      return;
    }
    const cpu = [hw.cpu || "CPU", hw.cores ? `${hw.cores} ${plural(hw.cores, ["core", "cores", "cores"])}` : "", hw.threads ? `${hw.threads} ${plural(hw.threads, ["thread", "threads", "threads"])}` : ""].filter(Boolean).join(" · ");
    const rows: [string, string][] = [
      ["CPU", cpu],
      ["Memory", hw.ram_gb ? `${gb(hw.ram_gb)} GB` + (hw.ram_free_gb ? ` (${gb(hw.ram_free_gb)} GB free)` : "") : "could not determine"],
      ["GPU", hw.gpus.length ? hw.gpus.map((g) => g.name + (g.vram_gb ? `, ${gb(g.vram_gb)} GB` : "")).join("; ") : "not found"],
    ];
    const t = el.createDiv({ cls: "vm-llama-hw-grid" });
    for (const [k, v] of rows) {
      t.createDiv({ cls: "vm-muted", text: k });
      t.createDiv({ text: v });
    }
  }

  private renderForm() {
    const el = this.formEl;
    el.empty();
    const p = this.p;
    const st = this.st;
    const hw = this.hw;
    const upd = () => this.renderNotes();
    new Setting(el).setName("Run on").setDesc("A GPU is much faster. Running on the CPU requires at least 16 GB of RAM.")
      .addDropdown((d) => d.addOptions({ cpu: "CPU", gpu: "GPU" }).setValue(p.device).onChange((v) => {
        p.device = v as LlamaParams["device"];
        this.renderForm();
      }));
    if (p.device === "gpu" && st.os !== "macos") {
      const opts: Record<string, string> = { auto: "Auto: NVIDIA uses CUDA; others use Vulkan" };
      if (st.os === "win" && st.arch === "x64") opts.cuda = "CUDA — for NVIDIA GPUs";
      opts.vulkan = "Vulkan — for NVIDIA, AMD, and Intel GPUs";
      if (!opts[p.build]) p.build = "auto";
      new Setting(el).setName("llama.cpp build").setDesc("Select the llama.cpp build to download for the GPU.")
        .addDropdown((d) => d.addOptions(opts).setValue(p.build).onChange((v) => {
          p.build = v as LlamaParams["build"];
          upd();
        }));
      const layers = st.model.layers || 48;
      const mode = typeof p.gpu_layers === "number" ? "num" : p.gpu_layers;
      const s = new Setting(el).setName("Model layers on GPU")
        .setDesc(`There are ${layers} layers. Layers that do not fit on the GPU run on the CPU (more slowly).`);
      s.addDropdown((d) => d.addOptions({ auto: "As many as fit", all: `All (${layers})`, num: "Custom number" }).setValue(mode).onChange((v) => {
        p.gpu_layers = v === "num" ? Math.min(layers, 24) : (v as "auto" | "all");
        this.renderForm();
      }));
      if (mode === "num") {
        s.addText((t) => {
          t.inputEl.type = "number";
          t.inputEl.min = "0";
          t.inputEl.max = String(layers);
          t.inputEl.addClass("vm-llama-num");
          t.setValue(String(p.gpu_layers)).onChange((v) => {
            const n = parseInt(v, 10);
            p.gpu_layers = Number.isFinite(n) ? n : 0;
            upd();
          });
        });
      }
    }
    const ctxs = [...new Set([...(st.ctx_choices || [2048, 4096, 8192, 16384, 32768]), p.ctx])].sort((a, b) => a - b);
    const ctxOpts: Record<string, string> = {};
    for (const c of ctxs) {
      const need = this.needGb(c);
      ctxOpts[String(c)] = `${c.toLocaleString("en-US")} tokens ≈ ${Math.round((c * 3) / 1000)}k characters` + (need ? ` · ${gb(need)} GB` : "");
    }
    new Setting(el).setName("Context").setDesc("The maximum text the model reads at once and its memory usage. Long entries are truncated by the program's text limit, so 4096 is usually sufficient.")
      .addDropdown((d) => d.addOptions(ctxOpts).setValue(String(p.ctx)).onChange((v) => {
        p.ctx = parseInt(v, 10);
        upd();
      }));
    const kvRu: Record<string, string> = { f16: "f16 — uncompressed", q8_0: "q8_0 — 8 bit", q4_0: "q4_0 — 4 bit" };
    const kvOpts: Record<string, string> = {};
    for (const k of st.kv_types || ["f16", "q8_0", "q4_0"]) kvOpts[k] = kvRu[k] || k;
    new Setting(el).setName("KV cache quantization").setDesc("This setting has little effect for this model: it reads each text in one pass without keeping a KV cache, so memory usage depends on Context. Leave it at f16.")
      .addDropdown((d) => d.addOptions(kvOpts).setValue(p.kv_cache).onChange((v) => {
        p.kv_cache = v;
        upd();
      }));
    const cores = hw?.cores || null;
    const ts = new Setting(el).setName("CPU threads")
      .setDesc("0 lets llama.cpp choose." + (cores ? ` This computer has ${cores} ${plural(cores, ["core", "cores", "cores"])}${hw?.threads ? ` (${hw.threads} ${plural(hw.threads, ["thread", "threads", "threads"])})` : ""} — matching the thread count to the core count is usually fastest.` : ""));
    let thrInput: HTMLInputElement | null = null;
    ts.addText((t) => {
      thrInput = t.inputEl;
      t.inputEl.type = "number";
      t.inputEl.min = "0";
      t.inputEl.addClass("vm-llama-num");
      t.setValue(String(p.threads)).onChange((v) => {
        const n = parseInt(v, 10);
        p.threads = Number.isFinite(n) ? n : 0;
        upd();
      });
    });
    if (cores) ts.addButton((b) => b.setButtonText("Use core count").setTooltip(`${cores}`).onClick(() => {
      p.threads = cores;
      if (thrInput) thrInput.value = String(cores);
      upd();
    }));
    this.numField(el, "Port", "The server address will be http://127.0.0.1:<port>/v1. The program will fill it in automatically.", "port");
    this.numField(el, "Unload after idle, minutes", "After this idle period, the server releases the memory used by the model and reloads it on the next request (which takes a few seconds). Set to 0 to keep it loaded.", "sleep_min");
    new Setting(el).setName("Start automatically when needed")
      .setDesc("If the server is not running, for example after a restart, the program will start it with these settings during Phase 1 or when checking the connection.")
      .addToggle((t) => t.setValue(p.autostart).onChange((v) => {
        p.autostart = v;
      }));
    const md = new Setting(el).setName("Model folder").setDesc(`Leave empty to use ${st.default_models_dir}. Model size: ${sizeText(st.model.size)}.`);
    md.settingEl.addClass("vm-wide-setting");
    md.addText((t) => {
      t.inputEl.addClass("vm-wide-input");
      t.setPlaceholder(st.default_models_dir).setValue(p.models_dir || "").onChange((v) => {
        p.models_dir = v.trim();
        upd();
      });
    });
    this.renderNotes();
  }

  /** How much memory? (GB) Its a model with that context. — program-measuring (st.need_gb). */
  private needGb(ctx: number): number {
    const m = this.st.need_gb || {};
    if (m[String(ctx)]) return m[String(ctx)];
    const pts = Object.entries(m).map(([k, v]) => [Number(k), v] as [number, number]).sort((a, b) => a[0] - b[0]);
    for (let i = 1; i < pts.length; i++)
      if (ctx <= pts[i][0]) return pts[i - 1][1] + ((pts[i][1] - pts[i - 1][1]) * (ctx - pts[i - 1][0])) / (pts[i][0] - pts[i - 1][0]);
    return pts.length ? pts[pts.length - 1][1] : 0;
  }

  private numField(el: HTMLElement, name: string, desc: string, key: "port" | "sleep_min") {
    new Setting(el).setName(name).setDesc(desc).addText((t) => {
      t.inputEl.type = "number";
      t.inputEl.addClass("vm-llama-num");
      t.setValue(String(this.p[key])).onChange((v) => {
        const n = parseInt(v, 10);
        this.p[key] = Number.isFinite(n) ? n : -1;
        this.renderNotes();
      });
    });
  }

  /** Warnings (memory, videocard), downloadable, disk-space. */
  private renderNotes() {
    const el = this.noteEl;
    el.empty();
    const p = this.p;
    const st = this.st;
    const hw = this.hw;
    const min = st.min_ram_gb || 16;
    const mem = this.needGb(p.ctx) || st.vram_gb || 8;
    const withCtx = `at a context of ${p.ctx.toLocaleString("en-US")}, the model needs about ${gb(mem)} GB`;
    if (p.device === "cpu") {
      const ram = hw?.ram_gb ?? null;
      if (ram !== null && Math.round(ram) < min)
        el.createDiv({ cls: "vm-callout is-bad vm-llama-ram", text: `⚠ Low memory: this computer has ${gb(ram)} GB; the model requires at least ${min} GB of RAM on CPU (${withCtx}). Severe slowdowns or out-of-memory errors may occur.` + (hw?.gpus.length ? " Consider selecting GPU." : "") });
      else if (ram !== null && mem > ram - 2)
        el.createDiv({ cls: "vm-callout is-bad vm-llama-ram", text: `⚠ Insufficient memory: ${withCtx}, but this computer has ${gb(ram)} GB. Select a smaller context.` });
      else
        el.createDiv({ cls: "vm-callout is-warning vm-llama-ram", text: `⚠ This model requires at least ${min} GB of RAM on CPU` + (ram !== null ? ` — this computer has ${gb(ram)} GB` : " (the amount on this computer could not be determined)") + `; ${withCtx}. The model runs much more slowly on CPU than GPU.` });
    } else if (hw) {
      const vram = Math.max(0, ...hw.gpus.map((g) => g.vram_gb || 0));
      if (!hw.gpus.length) el.createDiv({ cls: "vm-callout is-warning", text: "No GPU was found. If you have one, update its driver; otherwise, select CPU." });
      else if (vram && vram < mem)
        el.createDiv({ cls: "vm-callout", text: `GPU memory is ${gb(vram)} GB; ${withCtx}. Some layers will remain in RAM, which is slower but works. As many as fit selects the layers automatically. A smaller context leaves room for more GPU layers.` });
      else el.createDiv({ cls: "vm-callout is-ok", text: `The model needs about ${gb(mem)} GB of GPU memory (context ${p.ctx.toLocaleString("en-US")})` + (vram ? ` — this GPU has ${gb(vram)} GB.` : ".") });
    }
    // downloadable
    const items: string[] = [];
    let need = 0;
    const m = st.model;
    const savedDir = (st.params.models_dir || "").trim();
    if ((p.models_dir || "").trim() !== savedDir) items.push(`Model: download to the new folder if not already there (${sizeText(m.size)})`);
    else if (!m.exists) {
      const left = Math.max(0, m.size - (m.partial || 0));
      need += left;
      items.push(m.partial ? `Model ${m.title} — ${sizeText(left)} remaining (${sizeText(m.partial)} already downloaded)` : `Model ${m.title} — ${sizeText(m.size)}`);
    }
    const b = llamaBuildFor(st, p, !!hw?.nvidia);
    if (!b.have) items.push(`llama.cpp (${LLAMA_BUILD_RU[b.build] || b.build}) — about ${st.approx_mb?.[b.build] || 30} MB` + (b.build === "cuda" ? " including CUDA libraries" : ""));
    if (st.vcredist_missing) items.push(`Microsoft Visual C++ libraries — about ${st.approx_mb?.vcredist || 25} MB (Windows will request installation permission)`);
    const box = el.createDiv({ cls: "vm-llama-plan" });
    if (items.length) {
      box.createDiv({ cls: "vm-llama-plan-title", text: "Will be downloaded once:" });
      const ul = box.createEl("ul");
      for (const it of items) ul.createEl("li", { text: it });
      if (need && m.free != null && m.free < need + 3e8)
        box.createDiv({ cls: "vm-callout is-warning", text: `Only ${sizeText(m.free)} is free on disk; the model will not fit. Free space or choose another model folder.` });
      else if (need) box.createDiv({ cls: "vm-muted vm-small-text", text: "Download progress appears in the Second Brain panel. Stop pauses the download; the next run resumes it." });
    } else box.createDiv({ cls: "vm-muted", text: "All required files are already downloaded." });
    const port = p.port > 0 ? p.port : "?";
    el.createDiv({ cls: "vm-muted vm-small-text", text: `Server address: http://127.0.0.1:${port}/v1 — the program will fill this in automatically.` });
  }

  private go() {
    const p = this.p;
    const errs: string[] = [];
    const int = (v: unknown, lo: number, hi: number) => typeof v === "number" && Number.isInteger(v) && v >= lo && v <= hi;
    if (!int(p.port, 1024, 65535)) errs.push("port must be between 1024 and 65535");
    if (!int(p.threads, 0, 1024)) errs.push("threads must be between 0 and 1024");
    if (!int(p.sleep_min, 0, 10080)) errs.push("idle time must be between 0 and 10080 minutes");
    if (typeof p.gpu_layers === "number" && !int(p.gpu_layers, 0, 999)) errs.push("layers must be between 0 and 999");
    if (errs.length) {
      new Notice("Check: " + errs.join("; ") + ".", 8000);
      return;
    }
    this.close();
    this.onStart({ ...p });
  }
}

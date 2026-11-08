// Settings: tab (Basic., Models., Thresholds, Incoming, Documents, Expenses, Additionally.) search.
// «Programme» notices — settings of the plugin itself; rest — settings.yaml program.
import { App, ExtraButtonComponent, Notice, PluginSettingTab, Setting, TextComponent } from "obsidian";
import * as fs from "fs";
import type BrainPlugin from "./main";
import { renderError, saveDeveloperReport } from "./report";
import type { LlamaStatus, SchemaField, SchemaSection, SettingsInfo } from "./types";
import { Job, liveInfo } from "./engine";
import { LLAMA_BUILD_RU, LlamaModal, TextModal } from "./modals";
import { PTYPE_RU, parseNumber, rangeText, sizeText } from "./util";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Obj = Record<string, any>;
type Put = (v: any) => void;

function getPath(o: Obj, key: string): any {
  return key.split(".").reduce((a: any, k) => (a == null ? undefined : a[k]), o);
}

function setPath(o: Obj, key: string, v: any) {
  const ks = key.split(".");
  let cur = o;
  for (const k of ks.slice(0, -1)) {
    if (cur[k] == null || typeof cur[k] !== "object") cur[k] = {};
    cur = cur[k];
  }
  cur[ks[ks.length - 1]] = v;
}

const clone = <T>(x: T): T => (x === undefined ? x : JSON.parse(JSON.stringify(x)));
const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
const FIXED_SOURCES: Record<string, string> = { archive: "Old entries: _staging/archive", note: "Files directly in _staging" };
const TAB_ORDER = ["main", "models", "thresholds", "input", "docs", "costs", "advanced"];
const TAB_NAMES: Record<string, string> = {
  main: "General", models: "Models", thresholds: "Thresholds", input: "Incoming", docs: "Documents", costs: "Expenses", advanced: "Advanced",
};

/** What tab is setting up?, erroneous. */
export function tabOfError(msg: string): string {
  const m = msg.trim().toLowerCase();
  if (/^llm\.(webchat|max_format_retries)|^limits\./.test(m)) return "advanced";
  if (/^(profile|llm\.|embeddings\.)/.test(m)) return "models";
  if (/^(thresholds\.|seed_dormancy_days)/.test(m)) return "thresholds";
  if (/^(budget\.|estimate\.)/.test(m)) return "costs";
  if (/^(sources|dialogue_markers|input\.)/.test(m)) return "input";
  if (/^style\./.test(m)) return "docs";
  return "main";
}

function fmt(v: any): string {
  if (v === null || v === undefined || v === "") return "empty";
  if (typeof v === "boolean") return v ? "on" : "off";
  return String(v);
}

export class BrainSettingTab extends PluginSettingTab {
  private info: SettingsInfo | null = null;
  private values: Obj | null = null;
  private loadError: string | null = null;
  private loading = false;
  private dirty = new Set<string>();
  private timer: number | null = null;
  private saving: Promise<void> | null = null;
  private tab = "main";
  private query = "";
  private editProfile: string | null = null;
  private errors: { text: string; tab: string }[] = [];
  // not navEl neither renderTab: names Obsidian 1.13+ inside SettingTab (menu item on the left and tab drawing)
  private barEl: HTMLElement | null = null;
  private bodyEl: HTMLElement | null = null;
  private dynEl: HTMLElement | null = null;
  private statusEl: HTMLElement | null = null;
  private progTimer: number | null = null;
  private lastProblem: string | null = null;
  // jelly-fish (llama.cpp)
  private llamaSt: LlamaStatus | null = null;
  private llamaBusy = false;
  private llamaFresh = false;
  private llamaAgain = false;
  private llamaWasBusy = false;
  private llamaLive: HTMLElement | null = null;
  private llamaTimer: number | null = null;

  constructor(app: App, private plugin: BrainPlugin) {
    super(app, plugin);
  }

  /** Obsidian open-up: show up and re-read settings.yaml. */
  display() {
    this.llamaFresh = false; // state of — read over
    try {
      this.redraw();
    } catch (e) {
      this.containerEl.empty();
      renderError(this.containerEl.createDiv({ cls: "vm-settings" }), this.plugin, "setting", e);
    }
    if (!this.plugin.engine.problem()) this.load();
    if (this.llamaTimer) window.clearInterval(this.llamaTimer);
    this.llamaTimer = window.setInterval(() => this.tickLlama(), 1000);
  }

  hide() {
    if (this.llamaTimer) window.clearInterval(this.llamaTimer);
    this.llamaTimer = null;
    this.flush();
  }

  /** The program itself changed the settings. (for example, «Run the model…» logged in the server address) — read over. */
  reload() {
    this.llamaFresh = false;
    if (!this.containerEl.isConnected) return; // When you open the next setup, you read it yourself.
    if (!this.plugin.engine.problem()) this.load();
    this.loadLlama();
  }

  /** Open the settings on the desired tab (panel). */
  openTab(tab: string) {
    this.tab = tab;
    this.query = "";
  }

  private redraw() {
    const el = this.containerEl;
    const scroll = el.scrollTop;
    el.empty();
    el.addClass("vm-settings");
    this.barEl = el.createDiv({ cls: "vm-set-nav" });
    this.bodyEl = el.createDiv({ cls: "vm-set-body" });
    this.renderNav();
    this.renderBody();
    el.scrollTop = scroll;
  }

  // ---------- tabs and search ----------
  private tabNames(): Record<string, string> {
    return { ...TAB_NAMES, ...(this.info?.tabs || {}) };
  }

  private renderNav() {
    const nav = this.barEl;
    if (!nav) return;
    nav.empty();
    const names = this.tabNames();
    const bad = new Set(this.errors.map((e) => e.tab));
    const tabs = nav.createDiv({ cls: "vm-set-tabs" + (this.query.trim() ? " is-searching" : "") });
    for (const id of TAB_ORDER) {
      const b = tabs.createEl("button", { cls: "vm-set-tab" + (id === this.tab ? " is-active" : "") + (bad.has(id) ? " has-error" : ""), text: names[id] });
      if (bad.has(id)) b.setAttr("title", "There is an error here; settings were not saved");
      b.addEventListener("click", () => {
        this.tab = id;
        this.query = "";
        this.renderNav();
        this.renderBody();
        this.containerEl.scrollTop = 0;
      });
    }
    const search = nav.createEl("input", { type: "search", cls: "vm-set-search", attr: { placeholder: "Search settings…", "aria-label": "Search settings" } });
    search.value = this.query;
    search.addEventListener("input", () => {
      this.query = search.value;
      tabs.toggleClass("is-searching", !!this.query.trim());
      this.renderBody();
    });
  }

  private renderBody() {
    const el = this.bodyEl;
    if (!el) return;
    el.empty();
    this.dynEl = null;
    try {
      if (this.query.trim()) this.renderSearch(el);
      else this.renderPane(el, this.tab, true);
    } catch (e) {
      renderError(el, this.plugin, this.where(), e);
    }
  }

  private where(tab = this.tab): string {
    return this.query.trim() ? "setting, search" : `setting, tab «${this.tabNames()[tab] || tab}»`;
  }

  /** Re-draw the variable part of the tab (field «Program folder» It doesnt lose focus.). */
  private rerender() {
    if (this.query.trim() || !this.dynEl) this.renderBody();
    else this.renderDyn(this.dynEl, this.tab);
  }

  private renderPane(el: HTMLElement, tab: string, main: boolean) {
    if (tab === "main") {
      this.renderProgram(el);
      this.renderNotify(el);
    }
    const dyn = el.createDiv();
    if (main) this.dynEl = dyn;
    this.renderDyn(dyn, tab);
  }

  private renderDyn(el: HTMLElement, tab: string) {
    el.empty();
    try {
      this.renderDynBody(el, tab);
    } catch (e) {
      renderError(el, this.plugin, this.where(tab), e);
    }
  }

  private renderDynBody(el: HTMLElement, tab: string) {
    for (const e of this.errors.filter((x) => x.tab === tab)) el.createDiv({ cls: "vm-callout is-warning", text: "Not saved: " + e.text });
    if (this.plugin.engine.problem()) {
      if (tab !== "main") el.createDiv({ cls: "vm-callout is-warning", text: "First specify the program folder on the General tab." });
      return;
    }
    if (!this.info || !this.values) {
      el.createDiv({ cls: this.loadError ? "vm-callout is-warning" : "vm-muted", text: this.loadError || "Loading program settings…" });
      if (this.loadError) new Setting(el).addButton((b) => b.setButtonText("Try again").onClick(() => this.load()));
      return;
    }
    for (const sec of this.info.schema.filter((s) => (s.tab || "advanced") === tab)) this.renderSection(el, sec);
    if (tab === "models") {
      new Setting(el)
        .setName("Check connection")
        .setDesc("The main model, models for individual steps, and embeddings are checked separately.")
        .addButton((b) => b.setButtonText("Check connection").setCta().onClick(async () => {
          await this.flush();
          this.plugin.runCheck();
        }));
    }
    if (tab === "costs") {
      new Setting(el)
        .setName("Detailed expenditures")
        .setDesc("View costs by model, step, day, and run, and cloud profile prices on the Expenses tab of the Second Brain panel.")
        .addButton((b) => b.setButtonText("Open Expenses").onClick(async () => {
          await this.flush();
          (this.app as any).setting?.close?.();
          this.plugin.openView("usage");
        }));
    }
    if (tab === "advanced") this.renderService(el);
  }

  private renderSearch(el: HTMLElement) {
    const q = this.query.trim().toLowerCase();
    const names = this.tabNames();
    let found = 0;
    for (const id of TAB_ORDER) {
      const pane = el.createDiv({ cls: "vm-search-pane" });
      pane.createDiv({ cls: "vm-search-tab", text: names[id] });
      this.renderPane(pane, id, false);
      let n = 0;
      pane.querySelectorAll(".setting-item:not(.setting-item-heading)").forEach((it) => {
        const info = it.querySelector(".setting-item-info");
        const ok = (info?.textContent || "").toLowerCase().includes(q);
        (it as HTMLElement).toggleClass("vm-hidden", !ok);
        if (ok) n++;
      });
      pane.querySelectorAll(".vm-sec").forEach((sec) => {
        const vis = sec.querySelectorAll(".setting-item:not(.setting-item-heading):not(.vm-hidden)").length;
        (sec as HTMLElement).toggleClass("vm-hidden", !vis);
      });
      if (!n) pane.addClass("vm-hidden");
      found += n;
    }
    if (!found) el.createDiv({ cls: "vm-muted vm-search-none", text: `No settings found for “${this.query.trim()}”.` });
  }

  private section(el: HTMLElement, title: string, help?: string): HTMLElement {
    const box = el.createDiv({ cls: "vm-sec" });
    new Setting(box).setName(title).setHeading();
    if (help) box.createDiv({ cls: "setting-item-description vm-sec-help", text: help });
    return box;
  }

  private renderSection(el: HTMLElement, sec: SchemaSection) {
    const box = this.section(el, sec.title, sec.help);
    for (const f of sec.fields) {
      if (!this.visible(f)) continue;
      this.renderField(box, f);
      if (f.key === "embeddings.mode" && String(getPath(this.values!, "embeddings.mode")) === "local") this.renderLlama(box);
    }
    if (sec.id === "updates") this.renderUpdateButtons(box);
  }

  private visible(f: SchemaField): boolean {
    if (!f.show_if || !this.values) return true;
    return Object.entries(f.show_if).every(([k, vals]) => vals.includes(String(getPath(this.values!, k))));
  }

  private async load() {
    if (this.loading) return;
    this.loading = true;
    const r = await this.plugin.engine.run(["settings"], { label: "Settings", exclusive: false, quiet: true });
    this.loading = false;
    if (r.ok && r.settings) {
      const changed = !this.info || JSON.stringify(r.settings) !== JSON.stringify(this.info);
      this.info = r.settings;
      if (!this.dirty.size) this.values = clone(r.settings.values);
      this.loadError = null;
      if (changed) this.redraw();
    } else {
      this.loadError = "Could not read program settings: " + (r.error || "no response");
      this.redraw();
    }
  }

  // ---------- «Programme» notices (plugin settings) ----------
  private renderProgram(el: HTMLElement) {
    const p = this.plugin;
    const box = this.section(el, "Program");
    new Setting(box)
      .setName("Program folder")
      .setDesc("The folder containing Install.bat and the brain folder. Install.bat fills this in.")
      .setClass("vm-wide-setting")
      .addText((t) => t.setPlaceholder("C:\\Second Brain").setValue(p.data.programDir).onChange(async (v) => {
        p.data.programDir = v.trim();
        await p.saveData(p.data);
        this.programChanged();
      }));
    new Setting(box)
      .setName("Python")
      .setDesc("Usually no change is needed. Leave empty to use the Python installed by Install.bat.")
      .setClass("vm-wide-setting")
      .addText((t) => t.setPlaceholder(p.engine.defaultPython()).setValue(p.data.pythonPath).onChange(async (v) => {
        p.data.pythonPath = v.trim();
        await p.saveData(p.data);
        this.programChanged();
      }));
    this.statusEl = box.createDiv();
    this.renderStatus();
    new Setting(box)
      .setName("Check connection")
      .setDesc("Checks the vault, each model used by a step, and embeddings.")
      .addButton((b) => b.setButtonText("Check connection").setCta().onClick(async () => {
        await this.flush();
        p.runCheck();
      }));
  }

  private renderNotify(el: HTMLElement) {
    const p = this.plugin;
    const d = p.data;
    const save = () => p.saveData(d);
    const box = this.section(el, "Windows notifications", "System notifications appear when Obsidian is minimized or another window is active.");
    new Setting(box)
      .setName("Notify when a long run finishes")
      .setDesc("Phase 1, Phase 2, or revalidation runs that exceed the time below.")
      .addToggle((t) => t.setValue(d.notify).onChange(async (v) => {
        d.notify = v;
        await save();
      }));
    const m = new Setting(box).setName("Long run threshold, minutes").setDesc("0 means notify for every run.");
    m.addText((t) => {
      t.setValue(String(d.notifyMinutes));
      t.inputEl.addClass("vm-num");
      t.onChange(async (x) => {
        const n = parseNumber(x, "int", 0, 600);
        t.inputEl.toggleClass("vm-invalid", typeof n !== "number");
        if (typeof n === "number") {
          d.notifyMinutes = n;
          await save();
        }
      });
    });
    new Setting(box)
      .setName("Notify when the program is waiting for an answer")
      .setDesc("For example, when the budget is exhausted or a large run needs confirmation.")
      .addToggle((t) => t.setValue(d.notifyAsk).onChange(async (v) => {
        d.notifyAsk = v;
        await save();
      }));
    new Setting(box)
      .setName("Only when Obsidian is not focused")
      .setDesc("Turn off to receive notifications even when Obsidian is focused.")
      .addToggle((t) => t.setValue(d.notifyUnfocused).onChange(async (v) => {
        d.notifyUnfocused = v;
        await save();
      }));
    new Setting(box)
      .setName("Test notification")
      .setDesc("If it does not appear, allow notifications for Obsidian in Windows Settings > System > Notifications.")
      .addButton((b) => b.setButtonText("Show").onClick(() => {
        const ok = p.osNotify("Second Brain", "This is what a notification for a completed long run looks like.", "done", true);
        if (!ok) new Notice("Could not display the notification. Allow Obsidian notifications in Windows settings.", 10000);
      }));
  }

  private renderUpdateButtons(el: HTMLElement) {
    const skip = this.plugin.data.skipVersion;
    // repository — on-site (brain/__init__.py, line UPDATE_REPO), off-set
    const repo = (this.info?.update_repo || "").trim();
    new Setting(el)
      .setName("Check now")
      .setDesc(`Installed version: ${this.info?.version || "?"}.` + (skip ? ` Skipped version: ${skip}; a manual check will offer it again.` : "")
        + (repo ? "" : " No repository URL is configured in brain/__init__.py (UPDATE_REPO); there is nowhere to check for updates."))
      .addButton((b) => {
        b.setButtonText("Check for updates").onClick(async () => {
          await this.flush();
          this.plugin.checkUpdates(true);
        });
        if (!repo) b.setDisabled(true);
      });
  }

  // ---------- jelly-fish (llama.cpp) ----------
  /** Status of the model under «Where to count: on this computer»: squirt, llama.cpp, server; trigger. */
  private renderLlama(el: HTMLElement) {
    const st = this.llamaSt;
    const box = el.createDiv({ cls: "vm-llama-box" });
    const s = new Setting(box).setName("Local model");
    s.settingEl.addClass("vm-llama-setting");
    const d = s.descEl;
    if (!st) d.createDiv({ text: this.llamaBusy ? "Checking whether the model is downloaded…" : "KaLM-Embedding-Gemma3 12B runs on llama.cpp. Use Start model… to download and start it." });
    else {
      const m = st.model;
      d.createDiv({ text: `${m.title}: ` + (m.exists ? "downloaded" : m.partial ? `downloaded ${sizeText(m.partial)} from ${sizeText(m.size)} — download resumes on start` : `not downloaded (${sizeText(m.size)}) — will download on start`) });
      const names = Object.values(st.builds || {}).map((b) => `${LLAMA_BUILD_RU[b.build] || b.build}${b.tag ? ` (${b.tag})` : ""}`);
      d.createDiv({ text: "llama.cpp: " + (names.length ? names.join(", ") : st.system ? "installed on this computer" : "not downloaded; will be downloaded when started") });
      const srv = st.server;
      const dev = srv.params?.device === "gpu" ? "GPU" : "CPU";
      d.createDiv({
        cls: srv.running && srv.health === "ok" ? "vm-key-ok" : "",
        text: "server: " + (srv.running
          ? `running — ${srv.url} (${dev})` + (srv.health === "loading" ? ", loading model" : srv.health == null ? ", not responding" : "")
          : "not running" + (st.params.autostart && st.configured && m.exists ? " — starts automatically when needed" : "")),
      });
      if (!st.configured) d.createDiv({ cls: "vm-field-note", text: "The address below points to a different server. Start model… will fill in the correct address." });
    }
    const busy = !!this.llamaJob();
    s.addButton((b) => {
      b.setButtonText(st?.server.running ? "Restart…" : "Start model…").setCta().onClick(() => this.openLlama());
      if (busy) b.setDisabled(true);
    });
    if (st?.server.running)
      s.addButton((b) => b.setButtonText("Stop").setTooltip("Free the memory. The program will restart the server when needed.").onClick(async () => {
        await this.plugin.runLlamaStop();
        this.loadLlama();
      }));
    if (st?.log) s.addExtraButton((b) => b.setIcon("file-text").setTooltip("Model server log").onClick(() => this.showLlamaLog(st.log)));
    this.llamaLive = box.createDiv({ cls: "vm-llama-live vm-hidden" });
    this.tickLlama();
    if (!this.llamaFresh) {
      this.llamaFresh = true;
      this.loadLlama();
    }
  }

  private loadLlama() {
    if (this.llamaBusy) {
      this.llamaAgain = true; // settings have changed, while reading the state, — re-read
      return;
    }
    this.llamaBusy = true;
    this.plugin.llamaStatus(false).then((st) => {
      this.llamaBusy = false;
      const changed = JSON.stringify(st) !== JSON.stringify(this.llamaSt);
      this.llamaSt = st;
      if (changed && this.containerEl.isConnected) this.rerender();
      if (this.llamaAgain) {
        this.llamaAgain = false;
        this.loadLlama();
      }
    });
  }

  private llamaJob(): Job | undefined {
    return this.plugin.engine.find((j) => j.args[0] === "llama" && j.args[1] === "start" && (j.status === "running" || j.status === "queued"));
  }

  /** Status of model launch — right here (The settings window closes the panel «Second Brain»). */
  private tickLlama() {
    const el = this.llamaLive;
    if (!el || !el.isConnected) return;
    const job = this.llamaJob();
    el.toggleClass("vm-hidden", !job);
    if (!job) {
      if (this.llamaWasBusy) {
        this.llamaWasBusy = false;
        this.loadLlama();
      }
      return;
    }
    this.llamaWasBusy = true;
    el.empty();
    if (job.status === "queued") {
      el.createDiv({ text: "Model start queued; it will begin after the current run." });
      return;
    }
    const info = liveInfo(job);
    el.createDiv({ cls: "vm-llama-live-text", text: (info.stage || job.lastLine || "Starting…") + (info.eta ? ` · ${info.eta}` : "") });
    if (info.frac !== null) {
      const bar = el.createDiv({ cls: "vm-bar" });
      bar.createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.round(info.frac * 1000) / 10}%`;
    } else el.createDiv({ cls: "vm-progress" });
    const row = el.createDiv({ cls: "vm-llama-live-row" });
    row.createSpan({ cls: "vm-muted vm-small-text", text: job.stopAt ? "Stopping… Downloaded data is retained and the next run will resume." : "You can close settings; progress is also visible in the Second Brain panel." });
    if (!job.stopAt) {
      const stop = row.createEl("button", { text: "Stop" });
      stop.addEventListener("click", () => this.plugin.engine.stop());
    }
  }

  private async openLlama() {
    await this.flush();
    const st = (await this.plugin.llamaStatus(false)) || this.llamaSt;
    if (!st) {
      new Notice("The program did not respond, so the model status is unknown. Check the program folder on the General tab.", 10000);
      return;
    }
    this.llamaSt = st;
    new LlamaModal(this.plugin, st, (params) => {
      this.plugin.runLlamaStart(params);
      window.setTimeout(() => this.tickLlama(), 300);
    }).open();
  }

  private async showLlamaLog(file: string) {
    let text = "";
    try {
      const raw = String(await fs.promises.readFile(file, "utf8"));
      text = raw.split(/\r?\n/).slice(-300).join("\n");
    } catch (e) {
      text = `Journal not read: ${e}`;
    }
    new TextModal(this.app, "Model server log (last lines)", text).open();
  }

  private renderService(el: HTMLElement) {
    const box = this.section(el, "Advanced");
    new Setting(box)
      .setName("Prompts")
      .setDesc("Model request templates are files in the program folder. You can edit them; changes take effect on the next run and are preserved during updates.")
      .addButton((b) => b.setButtonText("Open prompts folder").onClick(() => this.plugin.revealPath(this.info!.prompts_dir)));
    new Setting(box)
      .setName("Settings file")
      .setDesc(`${this.info!.path} — The plugin rewrites this file with explanations; the previous version is saved as settings.yaml.bak.`)
      .addButton((b) => b.setButtonText("Show in folder").onClick(() => this.plugin.revealPath(this.info!.path, true)));
    new Setting(box)
      .setName("Developer report")
      .setDesc("If something is wrong, collect versions, recent errors, and recent run output in _logs/developer-report.md and copy it to the clipboard. Review the report before sharing: recent output and errors may include sensitive information.")
      .addButton((b) => b.setButtonText("Create report").onClick(async () => {
        await this.flush();
        (this.app as any).setting?.close?.();
        await saveDeveloperReport(this.plugin);
      }));
  }

  private renderStatus() {
    const el = this.statusEl;
    if (!el) return;
    el.empty();
    const prob = this.plugin.engine.problem();
    this.lastProblem = prob;
    el.className = "vm-callout " + (prob ? "is-warning" : "is-ok");
    el.setText(prob || `Program found${this.info ? `, version ${this.info.version}` : ""}. Vault: ${this.plugin.engine.vaultPath()}`);
  }

  private programChanged() {
    if (this.progTimer) window.clearTimeout(this.progTimer);
    this.progTimer = window.setTimeout(() => {
      const before = this.lastProblem;
      this.renderStatus();
      if (before !== this.lastProblem) {
        this.info = null;
        this.values = null;
        this.rerender();
        if (!this.lastProblem) {
          this.load();
          this.plugin.refreshState(true);
        }
      }
    }, 600);
  }

  // ---------- field-schematic ----------
  private put(key: string): Put {
    return (v: any) => this.set(key, v);
  }

  private renderField(el: HTMLElement, f: SchemaField) {
    const v = getPath(this.values!, f.key);
    const def = getPath(this.info!.defaults || {}, f.key);
    switch (f.type) {
      case "text":
        return this.fieldText(el, f, v, this.put(f.key), def);
      case "choice":
        return this.fieldChoice(el, f, v);
      case "key":
        return this.fieldKey(el, f.label, f.help, f.target || "llm");
      case "int":
      case "float":
      case "int?":
      case "float?":
        return this.fieldNumber(el, f, v, this.put(f.key), def);
      case "bool":
        return this.fieldBool(el, f, v, this.put(f.key), def);
      case "json":
        return this.fieldJson(el, f, v, this.put(f.key));
      case "textarea":
        return this.fieldTextarea(el, f, v);
      case "lines":
        return this.fieldLines(el, f, v, def);
      case "roles":
        return this.fieldRoles(el, f);
      case "sources":
        return this.fieldSources(el, f);
      case "llm":
        return this.fieldLlm(el, f);
      default:
        new Setting(el).setName(f.label).setDesc(`${f.help} Edit this value in settings.yaml.`);
    }
  }

  /** «↺» — default. Always visible (slide-line «leaper», when the meaning passes through
   *  silence); until the default — dull and unpressed. Returns function, field
   *  per-edit (button changes immediately, straight-painted). */
  private resetButton(s: Setting, def: any, v: any, put: Put): (x: any) => void {
    if (def === undefined) return () => {};
    let comp: ExtraButtonComponent | null = null;
    let changed = false;
    s.addExtraButton((b) => {
      comp = b;
      b.setIcon("rotate-ccw").onClick(() => {
        if (!changed) return; // default
        put(clone(def));
        this.rerender();
      });
      b.extraSettingsEl.addClass("vm-reset");
    });
    const mark = (x: any) => {
      changed = !same(def, x);
      if (comp) {
        comp.setDisabled(!changed);
        comp.setTooltip(changed ? `Reset to default: ${fmt(def)}` : `Already at the default: ${fmt(def)}`);
        comp.extraSettingsEl.toggleClass("vm-reset-off", !changed);
        comp.extraSettingsEl.setAttr("aria-disabled", changed ? "false" : "true");
      }
      s.settingEl.toggleClass("vm-changed", changed);
    };
    mark(v);
    return mark;
  }

  private fieldText(el: HTMLElement, f: SchemaField, v: any, put: Put, def?: any, onBlur?: () => void) {
    const s = new Setting(el).setName(f.label).setDesc(f.help);
    s.settingEl.addClass("vm-wide-setting");
    let mark: (x: any) => void = () => {};
    s.addText((t) => {
      t.setPlaceholder(f.placeholder || "").setValue(v == null ? "" : String(v));
      t.inputEl.addClass("vm-wide-input");
      t.onChange((x) => {
        put(x.trim());
        mark(x.trim());
      });
      if (onBlur) t.inputEl.addEventListener("blur", onBlur);
    });
    if (def) mark = this.resetButton(s, def, v, put);
  }

  private fieldChoice(el: HTMLElement, f: SchemaField, v: any) {
    const def = getPath(this.info!.defaults || {}, f.key);
    const s = new Setting(el).setName(f.label).setDesc(f.help);
    let mark: (x: any) => void = () => {};
    s.addDropdown((d) => {
      const ch = f.choices || {};
      for (const [k, label] of Object.entries(ch)) d.addOption(k, label);
      if (v != null && !(String(v) in ch)) d.addOption(String(v), String(v));
      d.setValue(v == null ? "" : String(v));
      d.onChange((x) => {
        this.set(f.key, x);
        mark(x);
        if (this.dependents(f.key)) this.rerender(); // field, visible only at certain values
      });
    });
    mark = this.resetButton(s, def, v, this.put(f.key));
  }

  private dependents(key: string): boolean {
    return !!this.info?.schema.some((sec) => sec.fields.some((x) => x.show_if && key in x.show_if));
  }

  private fieldBool(el: HTMLElement, f: SchemaField, v: any, put: Put, def?: any) {
    const s = new Setting(el).setName(f.label).setDesc(f.help);
    let mark: (x: any) => void = () => {};
    s.addToggle((t) => t.setValue(!!v).onChange((x) => {
      put(x);
      mark(x);
    }));
    mark = this.resetButton(s, def, v, put);
  }

  /** Number.: field, rapids and temperatures — slider. «int?»/«float?» — leave empty. */
  private fieldNumber(el: HTMLElement, f: SchemaField, v: any, put: Put, def?: any) {
    const s = new Setting(el).setName(f.label).setDesc(f.help);
    s.settingEl.addClass("vm-num-setting");
    const err = s.descEl.createDiv({ cls: "vm-field-error" });
    const kind = f.type.startsWith("float") ? "float" : "int";
    const optional = f.type.endsWith("?");
    let txt!: TextComponent;
    let rng: HTMLInputElement | null = null;
    let mark: (x: any) => void = () => {};
    const handle = (x: string) => {
      const n = parseNumber(x, kind, f.min, f.max);
      const bad = n === null || (n === undefined && !optional);
      txt.inputEl.toggleClass("vm-invalid", bad);
      err.setText(bad ? `Enter a valid ${rangeText(kind, f.min, f.max)}${optional ? " (or empty)" : ""}.` : "");
      if (bad) return;
      put(n === undefined ? null : n);
      mark(n === undefined ? null : n);
      if (rng && typeof n === "number") rng.value = String(n);
    };
    if (f.slider && f.min !== undefined && f.max !== undefined) {
      const r = s.controlEl.createEl("input", { type: "range", cls: "slider vm-set-range" });
      r.min = String(f.min);
      r.max = String(f.max);
      r.step = String(f.step || (kind === "int" ? 1 : 0.01));
      r.value = String(v ?? def ?? f.min);
      const decimals = (String(r.step).split(".")[1] || "").length;
      r.addEventListener("input", () => {
        const x = Number(r.value);
        txt.setValue(kind === "int" ? String(Math.round(x)) : x.toFixed(decimals));
        handle(txt.getValue());
      });
      rng = r;
    }
    s.addText((t) => {
      txt = t;
      t.setValue(v == null ? "" : String(v));
      if (optional) t.setPlaceholder(f.placeholder || (f.key.endsWith("max_tokens") ? "as specified by the provider" : "not set"));
      t.inputEl.addClass("vm-num");
      t.onChange(handle);
    });
    mark = this.resetButton(s, def, v, put);
  }

  private fieldJson(el: HTMLElement, f: SchemaField, v: any, put: Put) {
    const s = new Setting(el).setName(f.label).setDesc(f.help);
    const err = s.descEl.createDiv({ cls: "vm-field-error" });
    s.addTextArea((t) => {
      t.setValue(v && Object.keys(v).length ? JSON.stringify(v) : "");
      t.setPlaceholder("{}");
      t.inputEl.rows = 2;
      t.inputEl.addClass("vm-mono");
      t.onChange((x) => {
        let obj: any = {};
        try {
          obj = x.trim() ? JSON.parse(x) : {};
          if (typeof obj !== "object" || Array.isArray(obj) || obj === null) throw new Error("an object { … } is required");
        } catch (e) {
          err.setText(`Not JSON: ${(e as Error).message}`);
          t.inputEl.addClass("vm-invalid");
          return;
        }
        err.setText("");
        t.inputEl.removeClass("vm-invalid");
        put(obj);
      });
    });
  }

  private fieldTextarea(el: HTMLElement, f: SchemaField, v: any) {
    const s = new Setting(el).setName(f.label).setDesc(f.help);
    s.settingEl.addClass("vm-setting-block");
    s.addTextArea((t) => {
      t.setValue(v == null ? "" : String(v));
      t.inputEl.rows = 3;
      t.onChange((x) => this.set(f.key, x.trim()));
    });
  }

  private fieldLines(el: HTMLElement, f: SchemaField, v: any, def?: any) {
    const s = new Setting(el).setName(f.label).setDesc(f.help);
    let mark: (x: any) => void = () => {};
    s.addText((t) => {
      t.setValue(Array.isArray(v) ? v.join(", ") : "");
      t.onChange((x) => {
        const list = x.split(",").map((y) => y.trim()).filter(Boolean);
        this.set(f.key, list);
        mark(list);
      });
    });
    mark = this.resetButton(s, def, v, this.put(f.key));
  }

  /** Key key: profile:<id>, embeddings (llm — Key of the main cloud model, like v2.4). */
  private fieldKey(el: HTMLElement, label: string, help: string, target: string, prof?: Obj) {
    const keys = this.info!.keys;
    let present = target === "embeddings" ? keys.embeddings
      : target.startsWith("profile:") ? !!keys.profiles?.[target.slice(8)] : keys.llm;
    if (prof && !prof.api_key_file) present = false;
    const s = new Setting(el).setName(label).setDesc(help);
    s.descEl.createDiv({ cls: present ? "vm-key-ok" : "vm-muted", text: present ? `✓ key saved${prof?.api_key_file ? ` (${prof.api_key_file})` : ""}` : "no key" });
    if (prof && prof.api_key_file) {
      const others = (this.values!.llm.profiles as Obj[]).filter((x) => x !== prof && x.api_key_file === prof.api_key_file);
      if (others.length) {
        s.descEl.createDiv({ cls: "vm-field-note", text: `Key file ${prof.api_key_file} is shared with ${others.map((o) => o.name).join(", ")}. Saving a new key will replace it for all of these profiles.` });
        s.addButton((b) => b.setButtonText("Separate key").setTooltip("Use a separate key file for this profile").onClick(() => {
          const live = this.liveProfile(prof.id);
          if (live) live.api_key_file = "";
          this.set("llm.profiles", this.llm().profiles);
          this.rerender();
        }));
      }
    }
    let input: TextComponent;
    s.addText((t) => {
      input = t;
      t.inputEl.type = "password";
      t.inputEl.autocomplete = "off";
      t.setPlaceholder(present ? "enter a new key to replace it" : "enter the key");
    });
    s.addButton((b) => b.setButtonText("Save").onClick(async () => {
      const k = input.getValue().trim();
      if (!k) {
        new Notice("Enter the key in the field.");
        return;
      }
      await this.saveKey(target, k);
    }));
    if (present)
      s.addExtraButton((b) => b.setIcon("trash-2").setTooltip("Delete the key").onClick(async () => {
        const what = target === "embeddings" ? "Cloud embeddings will not work without a key." : "The cloud model will not work without a key.";
        const ok = await this.plugin.confirm({ title: "Delete the key?", text: `The key file will be deleted. ${what}`, ok: "Delete", warning: true });
        if (ok) await this.saveKey(target, "");
      }));
  }

  private async saveKey(target: string, key: string) {
    await this.flush(); // The new profile should be included settings.yaml before-key
    const r = await this.plugin.engine.run(["settings", "--key", target], { label: "Key", stdin: key + "\n", exclusive: false, quiet: true });
    if (r.ok) {
      new Notice(r.title || "Key saved.");
      if (r.settings) {
        this.info = r.settings;
        if (!this.dirty.size) this.values = clone(r.settings.values);
      }
      this.redraw();
    } else new Notice("Key not saved: " + (r.error || "error"), 10000);
  }

  // ---------- mode and profiles of models ----------
  private llm(): Obj {
    const v = this.values!;
    if (!v.llm || typeof v.llm !== "object") v.llm = {};
    if (!Array.isArray(v.llm.profiles)) v.llm.profiles = [];
    return v.llm;
  }

  private fieldLlm(el: HTMLElement, f: SchemaField) {
    const info = this.info!;
    const llm = this.llm();
    if (f.help) el.createDiv({ cls: "setting-item-description vm-sec-help", text: f.help });
    const modes: Record<string, string> = { ...(info.modes || f.choices || {}) };
    if (llm.mode && !(llm.mode in modes)) modes[llm.mode] = llm.mode === "fake" ? "Test model (for testing)" : llm.mode;
    new Setting(el)
      .setName("Mode")
      .setDesc("Where the main model runs.")
      .addDropdown((d) => {
        for (const [k, label] of Object.entries(modes)) d.addOption(k, label);
        d.setValue(llm.mode || "cloud");
        d.onChange((v) => this.setMode(v));
      });
    const kind = llm.mode === "local" ? "local" : llm.mode === "cloud" ? "cloud" : null;
    if (kind) {
      const key = kind === "cloud" ? "cloud_profile" : "local_profile";
      const list = (llm.profiles as Obj[]).filter((p) => p.kind === kind);
      new Setting(el)
        .setName(kind === "cloud" ? "Cloud profile" : "Local profile")
        .setDesc("The program uses this profile. You can assign different profiles to individual steps below.")
        .addDropdown((d) => {
          for (const p of list) d.addOption(p.id, p.name || p.id);
          d.setValue(llm[key] || list[0]?.id || "");
          d.onChange((v) => {
            this.set(`llm.${key}`, v);
            this.editProfile = v;
            this.rerender();
          });
        });
    } else if (llm.mode === "webchat") {
      el.createDiv({
        cls: "vm-callout is-info",
        text: "Web chat: the program places requests in the vault's _web-chat folder. Copy them into the model's chat and paste the responses into the answer files. Profiles below are only needed for steps assigned their own models.",
      });
    }
    this.profileEditor(el);
  }

  /** Profile at current values. After each saving, the values are replaced by the program sent.,
   *  So buttons and fields., pre-painted, Find your profile on id, Not the old link.. */
  private liveProfile(id: string): Obj | null {
    return (this.llm().profiles as Obj[]).find((x) => x && x.id === id) || null;
  }

  private setMode(v: string) {
    const llm = this.llm();
    this.set("llm.mode", v);
    if (v === "cloud" || v === "local") {
      const key = v === "cloud" ? "cloud_profile" : "local_profile";
      const list = (llm.profiles as Obj[]).filter((p) => p.kind === v);
      if (!list.length) this.set(`llm.${key}`, this.newProfile(v).id);
      else if (!list.some((p) => p.id === llm[key])) this.set(`llm.${key}`, list[0].id);
      this.editProfile = llm[key];
    }
    this.rerender();
  }

  /** New profile (copy): id p<N>, nameless, key — his (file will appear, when you save the key). */
  private newProfile(kind: string, base?: Obj): Obj {
    const llm = this.llm();
    const profiles = llm.profiles as Obj[];
    const ids = new Set(profiles.map((p) => p.id));
    let n = profiles.length + 1;
    while (ids.has(`p${n}`)) n++;
    const id = `p${n}`;
    const def = clone(this.info!.profile_defaults?.[kind] || { kind, name: kind === "local" ? "Local model" : "Cloud model" });
    const p: Obj = base ? { ...clone(base), id } : { ...def, id, kind };
    const names = new Set(profiles.map((x) => String(x.name || "").toLowerCase()));
    const root = base ? `${base.name || base.id} (copy)` : String(def.name || "Profile");
    let name = root;
    for (let i = 2; names.has(name.toLowerCase()); i++) name = `${root} ${i}`;
    p.name = name;
    if (!base) p.api_key_file = "";
    profiles.push(p);
    this.set("llm.profiles", profiles);
    this.editProfile = id;
    return p;
  }

  private profileUse(p: Obj, llm: Obj): string[] {
    const out: string[] = [];
    if (llm.cloud_profile === p.id) out.push(llm.mode === "cloud" ? "main model" : "default cloud profile");
    if (llm.local_profile === p.id) out.push(llm.mode === "local" ? "main model" : "default local profile");
    const steps = Object.entries(llm.roles || {}).filter(([, v]) => v === p.id).map(([k]) => k);
    if (steps.length) out.push("steps: " + steps.join(", "));
    return out;
  }

  private profileEditor(el: HTMLElement) {
    const llm = this.llm();
    const profiles = llm.profiles as Obj[];
    const box = el.createDiv({ cls: "vm-prof-editor" });
    const main = llm.mode === "local" ? llm.local_profile : llm.cloud_profile;
    const cur = profiles.find((p) => p.id === this.editProfile) || profiles.find((p) => p.id === main) || profiles[0];
    const s = new Setting(box)
      .setName("Profile to edit")
      .setDesc("Cloud profiles track prices and costs; local profiles track tokens and run time.");
    s.settingEl.addClass("vm-prof-pick");
    if (profiles.length)
      s.addDropdown((d) => {
        for (const p of profiles) d.addOption(p.id, `${p.name || p.id} (${PTYPE_RU[p.kind] || p.kind})`);
        d.setValue(cur?.id || "");
        d.onChange((v) => {
          this.editProfile = v;
          this.rerender();
        });
      });
    s.addButton((b) => b.setButtonText("＋ Cloud").setTooltip("New cloud profile").onClick(() => {
      this.newProfile("cloud");
      this.rerender();
    }));
    s.addButton((b) => b.setButtonText("＋ Local").setTooltip("New local language model profile (llama.cpp server)").onClick(() => {
      this.newProfile("local");
      this.rerender();
    }));
    if (!cur) {
      box.createDiv({ cls: "vm-callout is-warning", text: "No profiles. Create a cloud or local profile." });
      return;
    }
    s.addButton((b) => b.setButtonText("Copy").setTooltip("Duplicate this profile, for example for another model from the same provider").onClick(() => {
      this.newProfile(cur.kind, cur);
      this.rerender();
    }));
    s.addExtraButton((b) => b.setIcon("trash-2").setTooltip("Delete profile").onClick(() => this.deleteProfile(cur)));
    const used = this.profileUse(cur, llm);
    const fbox = box.createDiv({ cls: "vm-prof-box" });
    fbox.createDiv({ cls: "vm-prof-title", text: `${cur.name || cur.id} · ${PTYPE_RU[cur.kind] || cur.kind}` });
    fbox.createDiv({ cls: "vm-muted vm-small-text", text: used.length ? `Used by: ${used.join("; ")}.` : "Not currently in use. Select it above as the main profile or assign it to a step." });
    let pricesHead = false;
    for (const f of this.info!.profile_fields || []) {
      if (f.kinds && !f.kinds.includes(cur.kind)) continue;
      if (f.group === "prices" && !pricesHead) {
        pricesHead = true;
        fbox.createDiv({ cls: "vm-prof-sub", text: "Prices and limit are used to calculate costs. Enter provider prices in dollars per million tokens." });
      }
      this.profileField(fbox, cur, f);
    }
  }

  private profileField(el: HTMLElement, prof: Obj, f: SchemaField) {
    const put: Put = (v) => {
      const live = this.liveProfile(prof.id);
      if (!live) return; // profile already deleted
      setPath(live, f.key, v);
      this.set("llm.profiles", this.llm().profiles);
    };
    const v = getPath(prof, f.key);
    const def = getPath(this.info!.profile_defaults?.[prof.kind] || {}, f.key);
    switch (f.type) {
      case "text":
        return this.fieldText(el, f, v, put, f.key === "name" ? undefined : def, f.key === "name" || f.key === "base_url" ? () => this.flush().then(() => this.rerender()) : undefined);
      case "key":
        return this.fieldKey(el, f.label, f.help, `profile:${prof.id}`, prof);
      case "int":
      case "float":
      case "int?":
      case "float?":
        return this.fieldNumber(el, f, v, put, def);
      case "bool":
        return this.fieldBool(el, f, v, put, def);
      case "json":
        return this.fieldJson(el, f, v, put);
      default:
        new Setting(el).setName(f.label).setDesc(f.help);
    }
  }

  private async deleteProfile(p: Obj) {
    if ((this.llm().profiles as Obj[]).length <= 1) {
      new Notice("This is the only profile. Create another one first.", 6000);
      return;
    }
    const used = this.profileUse(p, this.llm());
    const ok = await this.plugin.confirm({
      title: "Delete profile?",
      text: `Profile “${p.name || p.id}” will be deleted.` + (used.length ? ` It is currently used by ${used.join("; ")}. The first suitable profile will be selected instead; affected steps will use the main model.` : "")
        + " The key file will not be deleted. The profile's expense history remains on the panel's Expenses tab.",
      ok: "Delete",
      warning: true,
    });
    if (!ok) return;
    // while the window was open, The values could be replaced by saved — Take the current ones.
    const llm = this.llm();
    const profiles = llm.profiles as Obj[];
    const i = profiles.findIndex((x) => x && x.id === p.id);
    if (i >= 0) profiles.splice(i, 1);
    this.set("llm.profiles", profiles);
    for (const [key, kind] of [["cloud_profile", "cloud"], ["local_profile", "local"]]) {
      if (llm[key] === p.id) this.set(`llm.${key}`, profiles.find((x) => x.kind === kind)?.id || "");
    }
    const roles = llm.roles && typeof llm.roles === "object" ? llm.roles : {};
    if (Object.values(roles).includes(p.id)) {
      for (const k of Object.keys(roles)) if (roles[k] === p.id) delete roles[k];
      this.set("llm.roles", roles);
    }
    this.editProfile = null;
    this.rerender();
  }

  private fieldRoles(el: HTMLElement, f: SchemaField) {
    const llm = this.llm();
    const roles: Obj = llm.roles && typeof llm.roles === "object" ? llm.roles : (llm.roles = {});
    const profiles = llm.profiles as Obj[];
    const liveRoles = (): Obj => {
      const l = this.llm();
      if (!l.roles || typeof l.roles !== "object" || Array.isArray(l.roles)) l.roles = {};
      return l.roles;
    };
    if (f.help) el.createDiv({ cls: "setting-item-description vm-sec-help", text: f.help });
    for (const step of f.prompts || []) {
      const s = new Setting(el).setName(step).setDesc(f.prompt_help?.[step] || "");
      s.settingEl.addClass("vm-role");
      const v = typeof roles[step] === "string" ? roles[step] : "";
      if (v) s.settingEl.addClass("vm-changed");
      s.addDropdown((d) => {
        d.addOption("", "Same as main model");
        for (const p of profiles) d.addOption(p.id, `${p.name || p.id} (${PTYPE_RU[p.kind] || p.kind})`);
        d.addOption("webchat", "Manually via web chat");
        if (v && v !== "webchat" && !profiles.some((p) => p.id === v)) d.addOption(v, `${v} — Theres no profile.`);
        d.setValue(v);
        d.onChange((x) => {
          const r = liveRoles();
          if (x) r[step] = x;
          else delete r[step];
          this.set("llm.roles", r);
          s.settingEl.toggleClass("vm-changed", !!x);
        });
      });
    }
    if (f.split_prompts?.length)
      el.createDiv({
        cls: "vm-muted vm-small-text vm-role-note",
        text: `Long material for ${f.split_prompts.join(", ")} is split according to the request limit of the profile assigned to each step.`,
      });
  }

  private fieldSources(el: HTMLElement, f: SchemaField) {
    const list: Obj[] = Array.isArray(this.values!.sources) ? this.values!.sources : (this.values!.sources = []);
    if (f.help) el.createDiv({ cls: "setting-item-description vm-sec-help", text: f.help });
    list.forEach((src, i) => {
      const fixed = FIXED_SOURCES[String(src.name || "").toLowerCase()];
      const s = new Setting(el).setName(fixed ? String(src.name) : src.name ? `_staging/${src.name}` : "New source").setDesc(fixed || "_staging subfolder");
      s.settingEl.addClass("vm-source");
      if (!fixed)
        s.addText((t) => {
          t.setPlaceholder("folder name").setValue(src.name || "");
          t.onChange((v) => {
            src.name = v.trim();
            this.set("sources", list);
          });
        });
      s.addColorPicker((c) => c.setValue(src.color || "#64748b").onChange((v) => {
        src.color = v;
        this.set("sources", list);
      }));
      s.addText((t) => {
        t.inputEl.addClass("vm-num");
        t.inputEl.title = "Number of points to lower the compaction threshold for this source";
        t.setPlaceholder("offset").setValue(String(src.compaction_shift ?? 0));
        t.onChange((v) => {
          const n = parseNumber(v, "int", -100, 100);
          t.inputEl.toggleClass("vm-invalid", n === null);
          if (n !== null) {
            src.compaction_shift = n ?? 0;
            this.set("sources", list);
          }
        });
      });
      if (!fixed)
        s.addExtraButton((b) => b.setIcon("trash-2").setTooltip("Remove source").onClick(() => {
          list.splice(i, 1);
          this.set("sources", list);
          this.rerender();
        }));
    });
    new Setting(el).addButton((b) => b.setButtonText("Add source").onClick(() => {
      list.push({ name: "", color: "#64748b", compaction_shift: 0 });
      this.rerender();
    }));
  }

  // ---------- preservation ----------
  private set(key: string, v: any) {
    if (!this.values) return;
    setPath(this.values, key, v);
    this.dirty.add(key);
    if (this.timer) window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.flush(), 900);
  }

  private buildPatch(): Obj {
    const patch: Obj = {};
    for (const key of this.dirty) {
      let v = clone(getPath(this.values!, key));
      if (key === "sources" && Array.isArray(v)) v = v.filter((s: Obj) => s && String(s.name || "").trim());
      if (key === "llm.profiles" && Array.isArray(v)) {
        // Profiles are transmitted to the program id: {id: {field}}, remote — {id: null}
        const out: Obj = {};
        for (const p of v) {
          if (!p || !p.id) continue;
          const rest: Obj = { ...p };
          delete rest.id;
          out[p.id] = rest;
        }
        for (const o of (this.info?.values?.llm?.profiles || []) as Obj[]) if (o && o.id && !(o.id in out)) out[o.id] = null;
        v = out;
      }
      setPath(patch, key, v);
    }
    return patch;
  }

  /** Send accumulated changes to the program: Shell check them out and rewrite them. settings.yaml. */
  flush(): Promise<void> {
    if (this.timer) {
      window.clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.saving) return this.saving.then(() => this.flush());
    if (!this.dirty.size || !this.values) return Promise.resolve();
    const patch = this.buildPatch();
    this.dirty.clear();
    this.saving = (async () => {
      const r = await this.plugin.engine.run(["settings", "--set-json", "-"], { label: "Saving settings", stdin: JSON.stringify(patch), exclusive: false, quiet: true });
      if (r.ok && r.settings) {
        this.info = r.settings;
        if (!this.dirty.size) this.values = clone(r.settings.values);
        const hadErrors = this.errors.length > 0;
        this.errors = [];
        if (hadErrors) {
          this.renderNav();
          this.rerender();
        }
        new Notice("Settings saved.", 2500);
        this.plugin.refreshState();
        const e = patch.embeddings;
        // «Where to count» Or the emblems address has changed. — block «Your model» reread, Or is it the server?
        if (e && ("mode" in e || "base_url" in e) && this.llamaFresh && this.containerEl.isConnected) this.loadLlama();
      } else {
        const text = String(r.error || "Settings not saved.");
        const body = text.replace(/^Settings not saved:\s*/, "");
        this.errors = body.split(/;\s+/).filter(Boolean).map((t) => ({ text: t, tab: tabOfError(t) }));
        new Notice(text + " Saved values are shown.", 12000);
        this.info = null;
        this.values = null;
        this.saving = null;
        await this.load();
        this.redraw();
      }
    })().finally(() => {
      this.saving = null;
    });
    return this.saving;
  }
}

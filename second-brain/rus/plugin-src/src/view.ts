// Панель «Второй мозг» в боковой колонке: обзор, вопросы, контейнер, расходы, журнал.
import { ItemView, MarkdownRenderer, Notice, TFile, WorkspaceLeaf, setIcon } from "obsidian";
import type BrainPlugin from "./main";
import { Job, liveInfo } from "./engine";
import { renderError } from "./report";
import type { Period, UiContainer, UiQuestion, UiSnapshot, UsageProfile, UsageSummary, UsageTotals } from "./types";
import {
  PTYPE_RU, callsLine, clock, compact, containerOfPath, duration, durationText, money, nCalls, nQuestions, nRecords, num,
  parentsOf, parseNumber, pctText, plural, rangeText, ruDateTime, statsLine, usageLine,
} from "./util";

export const VIEW_TYPE = "vtoroy-mozg-panel";
export type Tab = "overview" | "questions" | "container" | "usage" | "log";

const RUN_NAMES: Record<string, string> = {
  run: "Фаза 1", synth: "Фаза 2", revalidate: "Ревалидация", patterns: "Паттерны", advise: "Совет по порогам",
  answer: "Ответ на вопрос", check: "Проверка связи",
};
const TAB_TITLES: Record<Tab, string> = { overview: "Обзор", questions: "Вопросы", container: "Контейнер", usage: "Расходы", log: "Журнал" };
const PERIODS: [Period, string][] = [["today", "Сегодня"], ["month", "Этот месяц"], ["prev_month", "Прошлый месяц"], ["all", "Всё время"]];
const PERIOD_IN: Record<Period, string> = { today: "сегодня", month: "в этом месяце", prev_month: "в прошлом месяце", all: "за всё время" };

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
  await_structure: "ждут утверждения структуры",
  await_mode: "ждут ответа о режиме",
  ready: "ждут разбора",
  new: "ждут черновика структуры",
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
    return "Второй мозг";
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

  // ---------- общее ----------
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
    // панель может быть в отдельном окне Obsidian: фокус смотрим в её документе
    const a = (this.contentEl.ownerDocument || document).activeElement as HTMLElement | null;
    if (!a || !this.contentEl.contains(a)) return false;
    if (a.tagName === "TEXTAREA") return true;
    return a.tagName === "INPUT" && !["checkbox", "radio", "button"].includes((a as HTMLInputElement).type);
  }

  /** Перерисовка. Пока человек печатает в поле панели, откладывается до выхода из поля. */
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
      this.plugin.errors.add("панель, шапка", e);
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
      // сломалась одна вкладка — показать ошибку с кнопкой «Скопировать отчёт», остальная панель работает
      renderError(this.bodyEl, this.plugin, `панель, вкладка «${TAB_TITLES[this.tab]}»`, e);
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

  // ---------- шапка и текущий запуск ----------
  private renderHead() {
    const h = this.headEl;
    h.empty();
    // название и состояние — в одном блоке: в узкой колонке состояние переносится под название, а не обрезается
    const main = h.createDiv({ cls: "vm-head-main" });
    const t = main.createDiv({ cls: "vm-title" });
    setIcon(t.createSpan({ cls: "vm-logo" }), "brain");
    t.createSpan({ text: "Второй мозг" });
    const p = this.plugin;
    const state = main.createDiv({ cls: "vm-state" });
    if (p.engine.problem()) state.setText("нет связи с программой");
    else if (p.engine.busy()) state.setText("работает");
    else if (p.ui) state.setText(p.ui.status.questions ? `ждут ответа: ${p.ui.status.questions}` : "готов");
    const tools = h.createDiv({ cls: "vm-head-tools" });
    const r = tools.createDiv({ cls: "clickable-icon vm-icon-btn", attr: { "aria-label": "Обновить состояние" } });
    setIcon(r, "refresh-cw");
    r.addEventListener("click", () => p.refreshState(true));
    const s = tools.createDiv({ cls: "clickable-icon vm-icon-btn", attr: { "aria-label": "Настройки плагина" } });
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
      const time = h.createSpan({ cls: "vm-run-time", attr: { title: "Сколько идёт запуск" } });
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
          text: "Останавливаю: программа закончит текущий шаг и сохранит всё. Если модель долго отвечает — это может занять пару минут.",
        });
      }
    }
    if (queued.length) el.createDiv({ cls: "vm-run-queue", text: "В очереди: " + queued.map((j) => j.label).join(", ") });
    const b = el.createDiv({ cls: "vm-buttons" });
    if (!job?.stopAt) this.button(b, "Стоп", () => eng.stop());
    if (job) {
      const kill = this.button(b, "Прервать сразу", async () => {
        const ok = await this.plugin.confirm({
          title: "Прервать сразу?",
          text: "Программа остановится немедленно. Текущий шаг (ответ модели, который сейчас ждём) пропадёт, всё сохранённое до него — цело.",
          ok: "Прервать",
          warning: true,
        });
        if (ok) eng.kill();
      }, "warning");
      if (this.runEls) this.runEls.kill = kill;
      this.button(b, "Вывод программы", () => {
        this.openJobs.add(job.id);
        this.show("log");
      });
    }
    this.tick();
  }

  /** Раз в секунду и на каждую живую строку программы: время, этап, «осталось ≈», ожидание ответа, расход. */
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
    r.time.setText(job.startedAt ? duration(now - job.startedAt) : "");
    show(r.stage, info.stage ? info.stage + (info.eta ? ` · ${info.eta}` : "") : "");
    r.barBox.toggleClass("vm-hidden", info.frac === null);
    r.spin.toggleClass("vm-hidden", info.frac !== null);
    if (info.frac !== null) r.bar.style.width = `${Math.round(info.frac * 1000) / 10}%`;
    show(r.sub, info.sub);
    const ask = job.live.ask;
    show(r.ask, ask ? `Программа ждёт вашего ответа: «${ask.title}» — окно открыто поверх Obsidian.` : "");
    show(r.wait, !ask && info.wait !== null && info.wait >= 1500 ? `Ждём ответа модели: ${duration(info.wait)}${info.waitWhat ? ` · ${info.waitWhat}` : ""}` : "");
    const u = job.live.usage;
    const local = job.live.last?.ptype === "local";
    show(r.usage, u && u.calls ? `Этот запуск: ${usageLine(u, { time: local })}` : "");
    r.line.setText(job.lastLine || "запускаю программу…");
    if (r.kill) r.kill.toggleClass("vm-hidden", !(job.stopAt && now - job.stopAt > 20000));
  }

  /** Новая строка вывода — обновить только строку прогресса, без перерисовки панели. */
  progress() {
    this.tick();
  }

  private renderTabs() {
    const el = this.tabsEl;
    el.empty();
    const q = this.plugin.ui?.status.questions || 0;
    const tabs: [Tab, string, number][] = [["overview", "Обзор", 0], ["questions", "Вопросы", q], ["container", "Контейнер", 0], ["usage", "Расходы", 0], ["log", "Журнал", 0]];
    for (const [id, label, n] of tabs) {
      const t = el.createEl("button", { cls: "vm-tab" + (this.tab === id ? " is-active" : "") });
      t.createSpan({ text: label });
      if (n) t.createSpan({ cls: "vm-badge is-accent", text: String(n) });
      t.addEventListener("click", () => this.show(id));
    }
  }

  // ---------- Обзор ----------
  private renderOverview(el: HTMLElement) {
    const p = this.plugin;
    const prob = p.engine.problem();
    if (prob) {
      const c = this.callout(el, "warning", "Плагин не видит программу", prob);
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, "Открыть настройки", () => p.openSettings(), "cta");
      return;
    }
    const ui = p.ui;
    if (!ui) {
      const c = this.callout(el, "info", "Загружаю состояние хранилища…", "Если это первое открытие — программа сейчас создаёт служебные папки.");
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, "Обновить", () => p.refreshState(true));
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
    box.createDiv({ cls: "vm-card-title", text: "Первая загрузка" });
    const waiting = Object.values(s.files).reduce((a, b) => a + b, 0);
    const hasFiles = s.staging_new > 0 || waiting > 0 || s.structure_pending;
    const draft = s.structure_pending && !!s.draft;
    const steps: { title: string; done: boolean; body: (d: HTMLElement) => void }[] = [
      {
        title: "Сложите заметки в _staging",
        done: hasFiles,
        body: (d) => {
          d.createDiv({ text: "Старые записи (архив) — в папку _staging/архив, новые — прямо в _staging. Подходят файлы .txt и .md, любые имена." });
          d.createDiv({ cls: "vm-muted", text: s.staging_new ? `Сейчас в _staging файлов: ${s.staging_new}.` : "Сейчас в _staging пусто." });
          const b = d.createDiv({ cls: "vm-buttons" });
          this.button(b, "Открыть папку _staging", () => p.revealFolder("_staging"));
          this.button(b, "Новая мысль", () => p.newThought());
          if (s.staging_new) this.button(b, "Дальше: Фаза 1", () => p.runPhase1(), "cta", busy);
        },
      },
      {
        title: "Фаза 1 — черновик структуры",
        done: draft,
        body: (d) => {
          d.createDiv({ text: "Программа прочитает файлы и предложит дерево контейнеров: проекты, ростки, вопросы." });
          if (waiting) d.createDiv({ cls: "vm-muted", text: `Файлов прочитано: ${waiting}.` });
          const b = d.createDiv({ cls: "vm-buttons" });
          this.button(b, "Запустить Фазу 1", () => p.runPhase1(), "cta", busy);
        },
      },
      {
        title: "Проверьте черновик и утвердите",
        done: false,
        body: (d) => {
          d.createDiv({ text: "Переименуйте, объедините или удалите контейнеры прямо в тексте черновика. После утверждения программа создаст папки и разложит записи — это следующая часть Фазы 1." });
          const b = d.createDiv({ cls: "vm-buttons" });
          if (s.draft) this.button(b, "Открыть черновик", () => p.open(s.draft!));
          this.button(b, "Утвердить структуру", () => p.approveStructure(), "cta", busy);
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
      const q = this.callout(el, "accent", `Ждут ответа: ${nQuestions(s.questions)}`, "Например, о режиме файла: массовая загрузка или одна запись.");
      this.button(q.createDiv({ cls: "vm-buttons" }), "Ответить", () => this.show("questions"), "cta");
    }
  }

  private renderAttention(el: HTMLElement, ui: UiSnapshot) {
    const p = this.plugin;
    const s = ui.status;
    const busy = p.engine.busy();
    let n = 0;
    if (s.structure_pending && s.draft) {
      n++;
      const c = this.callout(el, "accent", "Черновик структуры ждёт утверждения", "Программа предложила изменения структуры. Откройте черновик, поправьте и утвердите.");
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, "Открыть черновик", () => p.open(s.draft!));
      this.button(b, "Утвердить структуру", () => p.approveStructure(), "cta", busy);
    }
    if (s.webchat_pending.length) {
      n++;
      const c = this.callout(el, "accent", "Ждёт ответа из веб-чата", null);
      for (const w of s.webchat_pending) {
        const row = c.createDiv({ cls: "vm-webchat" });
        row.createDiv({ text: `Шаг «${w.prompt}»: скопируйте весь текст запроса в веб-чат модели, а её ответ целиком вставьте в файл ответа и сохраните.` });
        const b = row.createDiv({ cls: "vm-buttons" });
        this.button(b, "Открыть запрос", () => p.open(w.req));
        this.button(b, "Открыть файл ответа", () => p.open(w.ans));
      }
      const last = p.lastWebchat;
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, last ? `Продолжить: ${last.label}` : "Продолжить (Фаза 1)", () => p.continueWebchat(), "cta", busy);
    }
    if (s.questions) {
      n++;
      const c = this.callout(el, "accent", `Ждут ответа: ${nQuestions(s.questions)}`, "Ответ применяется сразу.");
      this.button(c.createDiv({ cls: "vm-buttons" }), "Ответить", () => this.show("questions"), "cta");
    }
    if (s.staging_new) {
      n++;
      const c = this.callout(el, "info", `Новых файлов в _staging: ${s.staging_new}`, null);
      this.button(c.createDiv({ cls: "vm-buttons" }), "Обработать (Фаза 1)", () => p.runPhase1(), "cta", busy);
    } else if (s.pending_work) {
      n++;
      const text = s.dirty.length ? `Базы синтеза к пересборке: ${s.dirty.map((d) => d.title).join(", ")}.` : "Часть записей ещё в очереди.";
      const c = this.callout(el, "info", "Обработка не закончена", text);
      this.button(c.createDiv({ cls: "vm-buttons" }), "Продолжить (Фаза 1)", () => p.runPhase1(), "cta", busy);
    }
    if (!n) this.callout(el, "ok", "Всё обработано", "Новые мысли — кнопкой «Новая мысль» или файлами в _staging.");
  }

  private renderActions(el: HTMLElement, ui: UiSnapshot, wizard: boolean) {
    const p = this.plugin;
    const box = el.createDiv({ cls: "vm-actions" + (wizard ? " is-wizard" : "") });
    const has = ui.containers.length > 0;
    const s = ui.status;
    const running = !!p.engine.find((j: Job) => j.args[0] === "run");
    if (!wizard)
      this.button(box, running ? "Фаза 1 идёт…" : "Фаза 1: обработать новое", () => p.runPhase1(), s.staging_new || s.pending_work ? "cta" : undefined, running);
    this.button(box, "Новая мысль", () => p.newThought());
    this.button(box, "Фаза 2: документы…", () => p.pickContainer((c) => c && p.runSynth(c)), undefined, !has);
    this.button(box, "Ревалидация…", () => p.pickContainer((c) => p.runRevalidate(c), "Все контейнеры"), undefined, !has);
    this.button(box, "Паттерны", () => p.runPatterns(), undefined, !has);
    this.button(box, "Проверить связь", () => p.runCheck());
  }

  private renderCounts(el: HTMLElement, ui: UiSnapshot, wizard: boolean) {
    const s = ui.status;
    const files = Object.entries(s.files).filter(([k, v]) => v && FILE_WAIT[k]);
    const filesLine = () => {
      if (files.length) el.createDiv({ cls: "vm-muted vm-line", text: "Файлы: " + files.map(([k, v]) => `${FILE_WAIT[k]} — ${v}`).join(" · ") });
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
    tile(s.containers, ["контейнер", "контейнера", "контейнеров"]);
    tile(s.entities, ["запись", "записи", "записей"]);
    tile(s.products, ["документ", "документа", "документов"]);
    tile(s.questions, ["вопрос", "вопроса", "вопросов"], () => this.show("questions"));
    const parts = [`обработано ${s.stages.done}`];
    if (s.stages.quarantine) parts.push(`ждут ответа ${s.stages.quarantine}`);
    if (s.stages.queue) parts.push(`в очереди ${s.stages.queue}`);
    if (s.entities || s.stages.queue || s.stages.quarantine) el.createDiv({ cls: "vm-muted vm-line", text: "Записи: " + parts.join(" · ") });
    filesLine();
  }

  private renderWarnings(el: HTMLElement, ui: UiSnapshot) {
    const list = [...new Set(ui.warnings || [])];
    if (!list.length) return;
    const s = this.section(el, "Предупреждения");
    for (const w of list) {
      const row = s.createDiv({ cls: "vm-warn" });
      row.createSpan({ cls: "vm-warn-mark", text: "!" });
      const t = row.createDiv({ cls: "vm-warn-text" });
      MarkdownRenderer.render(this.app, w, t, "", this).then(() => this.hookLinks(t));
    }
  }

  private renderTree(el: HTMLElement, ui: UiSnapshot) {
    const s = this.section(el, "Контейнеры", "записей");
    for (const c of ui.containers) {
      const row = s.createDiv({ cls: "vm-tree-row" + (c.status !== "active" ? " is-muted" : "") + (c.id === this.selectedId ? " is-selected" : "") });
      row.style.paddingLeft = `${6 + c.depth * 16}px`;
      this.dot(row, c.color);
      row.createSpan({ cls: "vm-tree-title", text: c.title });
      if (c.type !== "project") row.createSpan({ cls: "vm-chip", text: c.type_ru });
      if (c.status !== "active") row.createSpan({ cls: "vm-chip is-muted", text: c.status_ru });
      const right = row.createSpan({ cls: "vm-tree-right" });
      if (c.dirty) right.createSpan({ cls: "vm-mark", text: "↻", attr: { title: "база синтеза ждёт пересборки" } });
      if (c.questions) right.createSpan({ cls: "vm-badge is-accent", text: String(c.questions), attr: { title: nQuestions(c.questions) } });
      right.createSpan({ cls: "vm-tree-n", text: String(c.entities + c.shared) });
      row.addEventListener("click", () => this.show("container", c.id));
    }
  }

  /** Обзор: на какой модели работает программа и сколько она стоила в этом месяце. */
  private renderCurrent(el: HTMLElement, ui: UiSnapshot) {
    const u = ui.usage;
    if (!u) return;
    const cur = u.current;
    const box = el.createDiv({ cls: "vm-card vm-current" });
    const head = box.createDiv({ cls: "vm-current-head" });
    const webchat = cur.mode === "webchat";
    head.createSpan({ cls: "vm-current-k", text: "Модель:" });
    head.createSpan({ cls: "vm-current-name", text: webchat ? "вручную через веб-чат" : cur.name || "профиль не выбран" });
    if (cur.ptype && !webchat) head.createSpan({ cls: "vm-chip", text: PTYPE_RU[cur.ptype] || cur.ptype });
    const link = head.createEl("a", { cls: "vm-link vm-small-text vm-current-link", text: "Расходы →" });
    link.addEventListener("click", () => this.show("usage"));
    if (!webchat && !cur.name) {
      const a = box.createEl("a", { cls: "vm-link vm-small-text", text: "Выбрать профиль в настройках" });
      a.addEventListener("click", () => this.plugin.openSettings("models"));
    }
    const t = cur.totals?.month;
    box.createDiv({
      cls: "vm-muted vm-small-text",
      text: t && t.calls ? `В этом месяце: ${usageLine(t, { time: cur.ptype === "local" })}${t.unpriced ? " (* без части обращений — нет цен)" : ""}` : "В этом месяце обращений к этой модели не было.",
    });
    const all = u.totals.month;
    if (all.calls && t && all.calls !== t.calls) box.createDiv({ cls: "vm-muted vm-small-text", text: `Все модели в этом месяце: ${usageLine(all)}` });
    if (u.budget.monthly_usd) this.budgetBar(box, u, false);
  }

  /** Полоса бюджета месяца: зелёная, с 80% — жёлтая, со 100% — красная. */
  private budgetBar(parent: HTMLElement, u: UsageSummary, big: boolean) {
    const b = u.budget;
    if (!b.monthly_usd) return;
    const pct = b.pct ?? 0;
    const wrap = parent.createDiv({ cls: "vm-budget" + (big ? " is-big" : "") + (b.state ? ` is-${b.state}` : "") });
    const t = wrap.createDiv({ cls: "vm-budget-text" });
    t.createSpan({ text: `Бюджет месяца: ${money(b.spent)} из ${money(b.monthly_usd)}` });
    t.createSpan({ cls: "vm-budget-pct", text: ` · ${pctText(pct)}` });
    const bar = wrap.createDiv({ cls: "vm-bar" });
    bar.createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.min(100, pct)}%`;
    if (b.state === "over") wrap.createDiv({ cls: "vm-small-text", text: "Бюджет исчерпан: перед следующим платным обращением программа остановится и спросит, продолжать ли." });
    else if (b.state === "warn") wrap.createDiv({ cls: "vm-small-text", text: `Израсходовано больше ${b.warn_pct}% бюджета.` });
  }

  // ---------- Расходы ----------
  private renderUsageTab(el: HTMLElement, ui: UiSnapshot | null) {
    const p = this.plugin;
    const u = ui?.usage;
    if (!ui || !u) {
      this.callout(el, "info", "Расходов пока нет", "Сводка появится после первого обращения к модели.");
      return;
    }
    const job = p.engine.active();
    if (job?.live.usage?.calls) {
      const local = job.live.last?.ptype === "local";
      this.callout(el, "info", `Сейчас идёт: ${job.label}`, usageLine(job.live.usage, { time: local }) + ". Сводка ниже обновится, когда запуск закончится.");
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
    cell(plural(T.calls, ["обращение", "обращения", "обращений"]), num(T.calls));
    cell("токенов на входе", compact(T.in), T.cached ? `из них из кэша: ${num(T.cached)}` : undefined);
    cell("токенов на выходе", compact(T.out));
    cell("работа моделей", T.sec ? durationText(T.sec) : "—", "Сколько модели думали над ответами (сумма по обращениям)");
    if (T.cached) card.createDiv({ cls: "vm-muted vm-small-text", text: `Из кэша провайдера: ${num(T.cached)} токенов входа (они дешевле).` });
    if (T.unpriced)
      card.createDiv({ cls: "vm-small-text vm-warn-line", text: `* ${nCalls(T.unpriced)} облачных моделей без стоимости — у профиля не заданы цены. Впишите их ниже: программа предложит пересчитать прошлые обращения.` });
    if (T.est) card.createDiv({ cls: "vm-muted vm-small-text", text: `Для ${nCalls(T.est)} сервер не сообщил токены — они оценены по числу знаков.` });
    if (!T.calls) card.createDiv({ cls: "vm-muted", text: `Обращений ${PERIOD_IN[per]} не было.` });
    this.renderBudgetEdit(el, u);
    this.renderProfiles(el, u, per);
    this.renderSteps(el, u, per);
    this.renderDays(el, u);
    this.renderRuns(el, u);
    el.createDiv({
      cls: "vm-muted vm-small-text",
      text: "Стоимость считается по ценам профиля в момент обращения и хранится в журнале .system/usage.jsonl. Локальные модели бесплатны — для них показаны токены и время работы.",
    });
  }

  private renderBudgetEdit(el: HTMLElement, u: UsageSummary) {
    const p = this.plugin;
    const s = this.section(el, "Бюджет на облачные модели", "за месяц");
    if (u.budget.monthly_usd) this.budgetBar(s, u, true);
    else s.createDiv({ cls: "vm-muted vm-small-text", text: `Бюджет не задан. В этом месяце потрачено ${money(u.budget.spent)}.` });
    const row = s.createDiv({ cls: "vm-inline-form" });
    row.createSpan({ text: "Бюджет, $" });
    const inp = row.createEl("input", { type: "text", cls: "vm-num", attr: { inputmode: "decimal", placeholder: "без бюджета" } });
    inp.value = this.budgetDraft ?? (u.budget.monthly_usd != null ? String(u.budget.monthly_usd) : "");
    const save = this.button(row, "Сохранить", async () => {
      const v = parseNumber(inp.value, "float", 0, 100000);
      if (v === null) {
        inp.addClass("vm-invalid");
        new Notice("Бюджет — число от 0 до 100000 (пусто — без бюджета).");
        return;
      }
      save.disabled = true;
      const r = await p.patchSettings({ budget: { monthly_usd: v === undefined || v === 0 ? null : v } });
      this.budgetDraft = null;
      if (r.ok) new Notice(v ? `Бюджет месяца: ${money(v)}. При ${u.budget.warn_pct}% — предупреждение, при 100% — остановка с вопросом.` : "Бюджет снят.");
      else new Notice(r.error || "Бюджет не сохранён.", 12000);
      this.render(true);
    });
    inp.addEventListener("input", () => {
      this.budgetDraft = inp.value;
      inp.removeClass("vm-invalid");
    });
    inp.addEventListener("keydown", (ev: KeyboardEvent) => {
      if (ev.key === "Enter") save.click();
    });
    const note = s.createDiv({ cls: "vm-muted vm-small-text", text: `При ${u.budget.warn_pct}% — предупреждение, при 100% — программа остановится перед следующим платным обращением и спросит, продолжать ли. Порог предупреждения, оценка перед большим запуском и лимиты профилей — ` });
    const a = note.createEl("a", { cls: "vm-link", text: "в настройках" });
    a.addEventListener("click", () => this.plugin.openSettings("costs"));
    note.appendText(".");
  }

  private renderProfiles(el: HTMLElement, u: UsageSummary, per: Period) {
    const s = this.section(el, "Модели", PERIOD_IN[per]);
    const list = u.profiles.filter((x) => x.exists || x.totals.all.calls);
    if (!list.length) s.createDiv({ cls: "vm-muted", text: "Профилей нет." });
    for (const pr of list) this.renderProfileCard(s, pr, per);
  }

  private renderProfileCard(el: HTMLElement, pr: UsageProfile, per: Period) {
    const p = this.plugin;
    const emb = pr.kind === "emb";
    const card = el.createDiv({ cls: "vm-card vm-prof" + (pr.exists ? "" : " is-muted") + (pr.active ? " is-active" : "") });
    const h = card.createDiv({ cls: "vm-prof-head" });
    h.createSpan({ cls: "vm-prof-name", text: emb ? `Эмбеддинги · ${pr.model || pr.name}` : pr.name });
    if (pr.ptype) h.createSpan({ cls: "vm-chip", text: PTYPE_RU[pr.ptype] || pr.ptype });
    if (pr.active) h.createSpan({ cls: "vm-chip is-accent", text: "основная" });
    if (!pr.exists) h.createSpan({ cls: "vm-chip is-muted", text: emb ? "прежняя модель" : "профиль удалён" });
    const meta: string[] = [];
    if (pr.model && !emb) meta.push(pr.model);
    if (pr.steps.length) meta.push("шаги: " + pr.steps.join(", "));
    if (meta.length) card.createDiv({ cls: "vm-muted vm-small-text", text: meta.join(" · ") });
    const t: UsageTotals = pr.totals[per];
    card.createDiv({ cls: "vm-prof-usage", text: t.calls ? usageLine(t, { time: pr.ptype === "local", cost: pr.ptype === "cloud" }) : `обращений ${PERIOD_IN[per]} не было` });
    if (pr.budget_month) {
      const pct = pr.budget_pct ?? 0;
      const w = card.createDiv({ cls: "vm-budget" + (pr.budget_state ? ` is-${pr.budget_state}` : "") });
      w.createDiv({ cls: "vm-budget-text vm-small-text", text: `Лимит профиля: ${money(pr.totals.month.cost)} из ${money(pr.budget_month)} в этом месяце · ${pctText(pct)}` });
      w.createDiv({ cls: "vm-bar" }).createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.min(100, pct)}%`;
    }
    if (pr.ptype !== "cloud" || !pr.exists) return;
    // цены облачной модели
    const id = emb ? "emb" : pr.id!;
    const draft = this.priceDraft.get(id) || {};
    const prices = pr.prices || { input: null, cached_input: null, output: null };
    const box = card.createDiv({ cls: "vm-prices" });
    box.createDiv({ cls: "vm-small-text vm-prices-title", text: "Цены, $ за 1 млн токенов" + (pr.priced ? "" : " — не заданы, стоимость не считается") });
    if (!pr.priced) box.addClass("is-unpriced");
    const fields: [string, string, number | null][] = emb
      ? [["input", "вход", prices.input]]
      : [["input", "вход", prices.input], ["cached_input", "вход из кэша", prices.cached_input], ["output", "выход", prices.output]];
    const inputs: Record<string, HTMLInputElement> = {};
    const row = box.createDiv({ cls: "vm-prices-row" });
    for (const [k, label, v] of fields) {
      const f = row.createDiv({ cls: "vm-price" });
      f.createDiv({ cls: "vm-muted vm-small-text", text: label });
      const inp = f.createEl("input", { type: "text", cls: "vm-num", attr: { inputmode: "decimal", placeholder: k === "cached_input" ? "как вход" : "—" } });
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
    const save = this.button(b, "Сохранить", async () => {
      const out: Record<string, number | null> = {};
      for (const [k] of fields) {
        const v = parseNumber(inputs[k].value, "float", 0, 1000);
        if (v === null) {
          inputs[k].addClass("vm-invalid");
          new Notice("Цена — число от 0 до 1000 долларов за миллион токенов.");
          return;
        }
        out[k] = v === undefined ? null : v;
      }
      save.disabled = true;
      const patch = emb ? { embeddings: { price_input: out.input } } : { llm: { profiles: { [id]: { prices: out } } } };
      const r = await p.patchSettings(patch);
      if (!r.ok) {
        new Notice(r.error || "Цены не сохранены.", 12000);
        save.disabled = false;
        return;
      }
      this.priceDraft.delete(id);
      new Notice(`Цены «${emb ? "эмбеддинги" : pr.name}» сохранены.`);
      if (pr.totals.all.calls) {
        const ok = await p.confirm({
          title: "Пересчитать прошлые обращения?",
          text: `У «${emb ? "эмбеддингов" : pr.name}» уже ${nCalls(pr.totals.all.calls)}. Пересчитать их стоимость по новым ценам?\n\nЕсли нет — новые цены подействуют с этого момента, а прошлые обращения сохранят стоимость, посчитанную тогда.`,
          ok: "Пересчитать",
          cancel: "Не надо",
        });
        if (ok) {
          const rr = await p.reprice(id);
          if (rr.ok) new Notice(rr.repriced ? `Стоимость пересчитана: обращений — ${rr.repriced}.` : "Пересчитывать нечего — стоимость не изменилась.");
          else new Notice(rr.error || "Не пересчитано.", 12000);
        }
      }
      this.render(true);
    }, "cta");
  }

  private renderSteps(el: HTMLElement, u: UsageSummary, per: Period) {
    const rows = u.steps.filter((x) => x.totals[per].calls);
    if (!rows.length) return;
    const s = this.section(el, "По шагам", PERIOD_IN[per]);
    const tb = s.createDiv({ cls: "vm-table" });
    const hr = tb.createDiv({ cls: "vm-tr is-head" });
    for (const h of ["Шаг", "Обращений", "Токенов", "Стоимость"]) hr.createDiv({ cls: "vm-td", text: h });
    for (const st of rows) {
      const t = st.totals[per];
      const r = tb.createDiv({ cls: "vm-tr" });
      r.createDiv({ cls: "vm-td", text: st.name });
      r.createDiv({ cls: "vm-td is-num", text: num(t.calls) });
      r.createDiv({ cls: "vm-td is-num", text: compact(t.in + t.out), attr: { title: `вход ${num(t.in)}, выход ${num(t.out)}` } });
      r.createDiv({ cls: "vm-td is-num", text: t.cost || t.unpriced ? money(t.cost) + (t.unpriced ? "*" : "") : "—" });
    }
  }

  private renderDays(el: HTMLElement, u: UsageSummary) {
    const days = u.days || [];
    if (!days.some((d) => d.calls)) return;
    const byCost = days.some((d) => d.cost > 0);
    const s = this.section(el, "По дням", byCost ? "стоимость, 31 день" : "обращения, 31 день");
    const max = Math.max(...days.map((d) => (byCost ? d.cost : d.calls)), byCost ? 0.0001 : 1);
    const chart = s.createDiv({ cls: "vm-chart" });
    for (const d of days) {
      const v = byCost ? d.cost : d.calls;
      const col = chart.createDiv({ cls: "vm-chart-col" + (d.date === u.today ? " is-today" : ""), attr: { title: `${ruDateTime(d.date)}: ${d.calls ? usageLine(d) : "обращений не было"}` } });
      const bar = col.createDiv({ cls: "vm-chart-bar" });
      bar.style.height = v ? `${Math.max(3, Math.round((v / max) * 100))}%` : "0";
    }
    const lab = s.createDiv({ cls: "vm-chart-labels vm-muted vm-small-text" });
    lab.createSpan({ text: ruDateTime(days[0].date).slice(0, 5) });
    lab.createSpan({ text: `максимум: ${byCost ? money(max) : num(max)} в день` });
    lab.createSpan({ text: "сегодня" });
  }

  private renderRuns(el: HTMLElement, u: UsageSummary) {
    if (!u.runs?.length) return;
    const s = this.section(el, "Последние запуски");
    for (const r of u.runs.slice(0, 12)) {
      const row = s.createDiv({ cls: "vm-urun" });
      row.createSpan({ cls: "vm-muted vm-small-text vm-urun-when", text: ruDateTime(r.started) });
      row.createSpan({ cls: "vm-urun-what", text: RUN_NAMES[r.cmd || ""] || r.cmd || "запуск" });
      row.createSpan({ cls: "vm-small-text vm-urun-usage", text: usageLine(r, { time: !r.cost && r.sec > 0 }) });
    }
  }

  // ---------- Вопросы ----------
  private renderQuestions(el: HTMLElement, ui: UiSnapshot | null) {
    if (!ui) {
      this.callout(el, "info", "Состояние ещё не загружено", null);
      return;
    }
    const p = this.plugin;
    let qs = ui.questions;
    const fc = this.byId(this.qFilter);
    if (fc) {
      const bar = el.createDiv({ cls: "vm-filter" });
      bar.createSpan({ text: "Только вопросы по " });
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
      this.callout(el, "ok", "Открытых вопросов нет", fc ? "По этому контейнеру вопросов нет." : null);
      if (ui.status.pending_work) {
        const c = this.callout(el, "info", "Обработка не закончена", "Часть записей ждала ответов — продолжите обработку.");
        this.button(c.createDiv({ cls: "vm-buttons" }), "Продолжить обработку (Фаза 1)", () => p.runPhase1(), "cta", p.engine.busy());
      }
      return;
    }
    if (p.engine.busy()) this.callout(el, "info", null, "Программа сейчас работает — ответ встанет в очередь и применится сразу после текущего запуска.");
    for (const q of qs) this.renderQuestion(el, q);
    if (ui.status.pending_work) {
      const c = this.callout(el, "info", null, "Когда ответите, продолжите обработку — программа разложит записи, которые ждали ответов.");
      this.button(c.createDiv({ cls: "vm-buttons" }), "Продолжить обработку (Фаза 1)", () => p.runPhase1(), "cta", p.engine.busy());
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
        const chip = links.createSpan({ cls: "vm-chip is-link", attr: { title: "Открыть контейнер в панели" } });
        this.dot(chip, c.color);
        chip.appendText(c.title);
        chip.addEventListener("click", () => this.show("container", c.id));
      }
      if (q.entity_path) {
        const a = links.createEl("a", { cls: "vm-link", text: "открыть запись" });
        a.addEventListener("click", () => p.open(q.entity_path!));
      }
    }
    const text = card.createDiv({ cls: "vm-q-text markdown-rendered" });
    MarkdownRenderer.render(this.app, q.text, text, q.entity_path || "", this).then(() => this.hookLinks(text));
    if (q.note) card.createDiv({ cls: "vm-q-note", text: q.note });
    const err = this.answerError.get(q.id);
    if (err && err !== q.note) card.createDiv({ cls: "vm-q-note", text: err });
    if (job) card.createDiv({ cls: "vm-q-state", text: job.status === "queued" ? "В очереди — применится после текущего запуска…" : "Применяю ответ…" });
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
      const ta = box.createEl("textarea", { attr: { rows: "2", placeholder: q.free_hint || "Свой ответ" } });
      ta.value = this.freeText.get(q.id) || "";
      ta.addEventListener("input", () => this.freeText.set(q.id, ta.value));
      const b = box.createEl("button", { text: "Ответить", cls: "mod-cta" });
      b.disabled = !!job;
      b.addEventListener("click", () => {
        const t = ta.value.trim();
        if (!t) {
          new Notice("Напишите ответ.");
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
      new Notice(`Ответ на ${q.id} принят.`);
    } else this.answerError.set(q.id, r.note || r.error || "Ответ не принят.");
    this.render();
  }

  // ---------- Контейнер ----------
  private renderContainerTab(el: HTMLElement, ui: UiSnapshot | null) {
    if (!ui || !ui.containers.length) {
      this.callout(el, "info", "Контейнеров пока нет", "Они появятся после утверждения структуры.");
      return;
    }
    const bar = el.createDiv({ cls: "vm-cbar" });
    const sel = bar.createEl("select", { cls: "dropdown" });
    sel.createEl("option", { text: "— выберите контейнер —", attr: { value: "" } });
    for (const c of ui.containers) sel.createEl("option", { text: "\u00a0\u00a0\u00a0".repeat(c.depth) + c.title, attr: { value: c.id } });
    sel.value = this.selectedId || "";
    sel.addEventListener("change", () => {
      this.follow = false;
      this.selectedId = sel.value || null;
      this.render(true);
    });
    const fb = bar.createEl("button", {
      cls: "vm-small" + (this.follow ? " is-active" : ""),
      text: this.follow ? "✓ по открытой заметке" : "по открытой заметке",
      attr: { title: "Показывать контейнер заметки, открытой в редакторе" },
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
      el.createDiv({ cls: "vm-empty", text: "Откройте заметку из папки контейнера или выберите контейнер в списке." });
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
    const a = t.createEl("a", { cls: "vm-link", text: c.title, attr: { title: "Открыть заметку контейнера" } });
    a.addEventListener("click", () => p.open(c.path));
    if (c.description) head.createDiv({ cls: "vm-cdesc", text: c.description });

    const meta = head.createDiv({ cls: "vm-cmeta" });
    const typeSel = meta.createEl("select", { cls: "dropdown", attr: { title: "Тип контейнера" } });
    for (const [k, v] of Object.entries(ui.types || {})) typeSel.createEl("option", { text: v, attr: { value: k } });
    typeSel.value = c.type;
    typeSel.addEventListener("change", () => p.setContainerField(c, "type", typeSel.value, `тип: ${ui.types[typeSel.value]}`));
    const stSel = meta.createEl("select", { cls: "dropdown", attr: { title: "Статус контейнера" } });
    for (const [k, v] of Object.entries(ui.statuses || {})) stSel.createEl("option", { text: v, attr: { value: k } });
    stSel.value = c.status;
    stSel.addEventListener("change", () => p.setContainerField(c, "container_status", stSel.value, `статус: ${ui.statuses[stSel.value]}`));

    const facts = head.createDiv({ cls: "vm-facts" });
    const fact = (k: string, v: string, onClick?: () => void) => {
      const r = facts.createDiv({ cls: "vm-fact" });
      r.createSpan({ cls: "vm-fact-k", text: k });
      const val = r.createSpan({ cls: "vm-fact-v" + (onClick ? " vm-link" : ""), text: v });
      if (onClick) val.addEventListener("click", onClick);
    };
    fact("Записи", nRecords(c.entities) + (c.shared ? `, ещё общих: ${c.shared}` : ""));
    if (c.questions)
      fact("Вопросы", nQuestions(c.questions), () => {
        this.qFilter = c.id;
        this.show("questions");
      });
    if (c.base) {
      fact("База синтеза", `${c.base.items} аспектов, первостепенных ${c.base.primary}` + (c.base.conflicts ? `, противоречий ${c.base.conflicts}` : ""));
      if (c.base.excluded) fact("Ниже порога ценности", String(c.base.excluded));
    } else fact("База синтеза", "ещё не собрана");
    if (c.dirty) fact("Пересборка", "база пересоберётся при Фазе 1" + (c.dirty_reasons.length ? ` (${c.dirty_reasons.join(", ")})` : ""));
    if (c.last_modified) fact("Изменён", ruDateTime(c.last_modified));
    const views = head.createDiv({ cls: "vm-links-row" });
    if (c.views.pool) views.createEl("a", { cls: "vm-link", text: "пул аспектов" }).addEventListener("click", () => p.open(c.views.pool!));
    if (c.views.base) views.createEl("a", { cls: "vm-link", text: "база синтеза" }).addEventListener("click", () => p.open(c.views.base!));
  }

  private renderDocs(el: HTMLElement, c: UiContainer) {
    const p = this.plugin;
    const s = this.section(el, "Документы");
    if (!c.products.length) s.createDiv({ cls: "vm-muted", text: "Документов пока нет." });
    for (const d of c.products) {
      const row = s.createDiv({ cls: "vm-doc" });
      row.createEl("a", { cls: "vm-link", text: d.title }).addEventListener("click", () => p.open(d.path));
      if (d.needs_review) row.createSpan({ cls: "vm-chip is-warning", text: "на проверке", attr: { title: "Программа просит проверить: в документе есть пометки" } });
    }
    const b = s.createDiv({ cls: "vm-buttons" });
    this.button(b, c.products.length ? "Обновить документы (Фаза 2)" : "Написать документы (Фаза 2)", () => p.runSynth(c), "cta");
    this.button(b, "Перепроверить раскладку", () => p.runRevalidate(c));
  }

  private renderThresholds(el: HTMLElement, ui: UiSnapshot, c: UiContainer) {
    const p = this.plugin;
    const s = this.section(el, "Пороги контейнера");
    s.createDiv({
      cls: "vm-muted vm-small-text",
      text: "Свои значения действуют на этот контейнер и вложенные в него. Пустое поле — как у родителя или общий порог из настроек (он показан серым); ↺ — убрать свой порог.",
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
      save.setText(n ? `Сохранить (${n})` : "Сохранить");
    };
    for (const k of names) {
      const info = ui.threshold_info[k];
      const tv = c.thresholds[k];
      const own = c.overrides[k];
      // что будет без своего значения: ближайший родитель со своим порогом или общий
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
      const help = row.createDiv({ cls: "vm-thr-help vm-hidden", text: `${info.help} Допустимо: ${rangeText(info.kind, info.min, info.max)}.` });
      lab.addEventListener("click", () => help.toggleClass("vm-hidden", !help.hasClass("vm-hidden")));
      const ctl = row.createDiv({ cls: "vm-thr-ctl" });
      const rng = ctl.createEl("input", { type: "range", cls: "slider vm-thr-range" });
      rng.min = String(info.min);
      rng.max = String(info.max);
      rng.step = String(info.step || (info.kind === "int" ? 1 : 0.01));
      const inp = ctl.createEl("input", { type: "text", cls: "vm-thr-input", attr: { inputmode: "decimal" } });
      inp.value = k in draft ? draft[k] : own !== undefined ? String(own) : "";
      inp.placeholder = inherited != null ? String(inherited) : tv ? String(tv.value) : "";
      const rs = ctl.createEl("button", { cls: "vm-thr-reset", text: "↺", attr: { title: `Убрать свой порог: будет ${inhFrom ? `как у «${inhFrom}»` : "общий"} (${inherited})` } });
      inputs[k] = inp;
      const decimals = (String(rng.step).split(".")[1] || "").length;
      const sync = () => {
        const v = parseNumber(inp.value, info.kind, info.min, info.max);
        const empty = !inp.value.trim();
        rng.value = String(typeof v === "number" ? v : inherited ?? info.min);
        rng.toggleClass("is-inherited", empty);
        rs.toggleClass("vm-hidden", empty);
        src.setText(!empty ? (v === own ? "свой" : "свой, не сохранён") : inhFrom ? `от «${inhFrom}»` : "общий");
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
    save = this.button(b, "Сохранить", async () => {
      const { changes, bad } = collect();
      if (bad.length) return;
      save.disabled = true;
      const ok = await p.saveThresholds(c, changes);
      if (ok) {
        this.thrDraft.delete(c.id);
        new Notice(`Пороги «${c.title}» сохранены — подействуют со следующей Фазы 1.`);
      }
      this.render(true);
    }, "cta");
    reset = this.button(b, "Отменить правку", () => {
      this.thrDraft.delete(c.id);
      this.render(true);
    });
    this.button(b, "Посоветоваться с ИИ", () => p.openAdvice(c));
    upd();
    const last = p.advice.get(c.id);
    if (last) {
      const a = this.callout(s, "accent", "Есть совет ИИ", `${ruDateTime(last.at)}: ${last.advice.summary}`);
      this.button(a.createDiv({ cls: "vm-buttons" }), "Показать совет", () => p.openAdvice(c, last.advice));
    }
    s.createDiv({
      cls: "vm-muted vm-small-text",
      text: "Пороги раскладки и уплотнения сработают на новых записях. Пороги ценности пересоберут базу синтеза при следующей Фазе 1 — без обращений к модели.",
    });
  }

  private renderStyle(el: HTMLElement, c: UiContainer) {
    const p = this.plugin;
    const s = this.section(el, "Стиль документов");
    const inherited = !c.style && c.style_effective
      ? `Сейчас действует стиль «${c.style_from}»: ${c.style_effective}`
      : "Например: «Пиши как бизнес-план, с цифрами и сроками».";
    const ta = s.createEl("textarea", { cls: "vm-style", attr: { rows: "3", placeholder: inherited } });
    ta.value = this.styleDraft.get(c.id) ?? c.style;
    const b = s.createDiv({ cls: "vm-buttons" });
    const save = this.button(b, "Сохранить стиль", async () => {
      save.disabled = true;
      const ok = await p.saveStyle(c, ta.value.trim());
      if (ok) {
        this.styleDraft.delete(c.id);
        new Notice(`Стиль «${c.title}» сохранён — учтётся при следующей Фазе 2.`);
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
      text: "Добавляется к общему стилю из настроек и важнее него. Действует и на вложенные контейнеры, если у них нет своего.",
    });
  }

  // ---------- Журнал ----------
  private renderLog(el: HTMLElement, ui: UiSnapshot | null) {
    const p = this.plugin;
    const eng = p.engine;
    const logs = this.section(el, "Логи программы");
    const lb = logs.createDiv({ cls: "vm-buttons" });
    const L = ui?.logs || {};
    if (L.changes) this.button(lb, "Изменения", () => p.open(L.changes!));
    if (L.reasoning) this.button(lb, "Рассуждения модели", () => p.open(L.reasoning!));
    if (L.archive) this.button(lb, "Архив вопросов", () => p.open(L.archive!));
    if (L.errors) this.button(lb, "Ошибки", () => p.open(L.errors!));
    this.button(lb, "open-questions.md", () => p.open("open-questions.md"));

    const s = this.section(el, "Запуски в этом сеансе");
    const jobs: Job[] = [];
    if (eng.current && !eng.current.quiet) jobs.push(eng.current);
    jobs.push(...eng.pending(), ...eng.history);
    if (!jobs.length) {
      s.createDiv({ cls: "vm-muted", text: "Пока ничего не запускалось." });
      return;
    }
    const icon: Record<string, string> = { queued: "⧗", running: "▶", done: "✓", failed: "✗", stopped: "■", cancelled: "–" };
    for (const j of jobs) {
      const card = s.createDiv({ cls: `vm-job is-${j.status}` });
      const h = card.createDiv({ cls: "vm-job-head" });
      h.createSpan({ cls: "vm-job-icon", text: icon[j.status] || "" });
      h.createSpan({ cls: "vm-job-label", text: j.label });
      const when = j.startedAt ? clock(j.startedAt) : clock(j.queuedAt);
      const dur = j.startedAt ? duration((j.finishedAt || Date.now()) - j.startedAt) : "в очереди";
      h.createSpan({ cls: "vm-muted vm-job-time", text: `${when} · ${dur}` });
      const r = j.result;
      if (r) {
        const sl = statsLine(r.stats);
        if (r.unchanged) card.createDiv({ text: "Документы актуальны — ничего не переписано." });
        else if (r.title && r.ok) card.createDiv({ text: r.title + (sl ? ` — ${sl}` : "") });
        if (r.error) card.createDiv({ cls: "vm-job-error", text: r.error });
        const cl = callsLine(r.calls);
        if (cl) card.createDiv({ cls: "vm-muted vm-small-text", text: cl });
        const ru = r.run_usage;
        if (ru && ru.calls) {
          const extra = [ru.cost ? money(ru.cost) + (ru.unpriced ? "*" : "") : "", ru.sec ? `модели думали ${durationText(ru.sec)}` : "", r.elapsed ? `весь запуск ${durationText(r.elapsed)}` : ""].filter(Boolean);
          card.createDiv({ cls: "vm-muted vm-small-text", text: `Токенов ${compact(ru.in)} → ${compact(ru.out)}` + (extra.length ? " · " + extra.join(" · ") : "") });
        }
        for (const w of r.warnings || []) card.createDiv({ cls: "vm-small-text vm-warn-line", text: "! " + w });
        for (const n of r.notices || []) card.createDiv({ cls: "vm-small-text vm-muted", text: "• " + n });
      }
      if (j.lines.length || j.args.length) {
        const open = this.openJobs.has(j.id);
        const t = card.createEl("a", { cls: "vm-link vm-small-text", text: open ? "скрыть вывод программы" : "вывод программы" });
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

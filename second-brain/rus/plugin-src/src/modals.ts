// Окна плагина: подтверждение, выбор варианта (вопрос программы, обновление), выбор контейнера, «Новая мысль»,
// совет ИИ по порогам, проверка связи, текст.
import { App, FuzzySuggestModal, Modal, Notice } from "obsidian";
import type BrainPlugin from "./main";
import type { Advice, AdviceRec, AskEvent, CheckItem, RunResult, UiContainer } from "./types";
import { copyText } from "./report";
import { containerLabel, fileSlug, nowHm, todayIso } from "./util";

// ---------- подтверждение ----------
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
    b.createEl("button", { text: this.o.cancel || "Отмена" }).addEventListener("click", () => this.answer(false));
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

// ---------- выбор из нескольких вариантов ----------
export interface ChoiceOpts {
  title: string;
  /** подзаголовок мелко над текстом */
  sub?: string;
  /** абзацы через пустую строку */
  text?: string;
  /** список строк (оценка запуска, что изменилось) */
  lines?: string[];
  /** длинный текст как есть (описание новой версии) */
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

/** Открыть окно выбора. close() — закрыть снаружи (ответ — null). */
export function choiceModal(app: App, o: ChoiceOpts): { result: Promise<number | null>; close: () => void } {
  let m: ChoiceModal | null = null;
  const result = new Promise<number | null>((resolve) => {
    m = new ChoiceModal(app, o, resolve);
    m.open();
  });
  return { result, close: () => m?.close() };
}

/** Вопрос программы посреди запуска (@@ASK): бюджет исчерпан, большой запуск, ревалидация. */
export function askOptions(ask: AskEvent): ChoiceOpts {
  const opts = ask.options.map((label, i) => {
    let kind: "cta" | "warning" | undefined;
    if (ask.id === "budget") kind = i === 0 ? "warning" : i === 1 ? "cta" : undefined;
    else if (i === 0) kind = "cta";
    return { label, kind };
  });
  const note = ask.id === "budget"
    ? "Остановка ничего не портит: всё обработанное сохранено, следующий запуск продолжит. Бюджет — в настройках, вкладка «Расходы»."
    : ask.id === "estimate"
      ? "Порог, с которого программа спрашивает, — в настройках, вкладка «Расходы». Закрыть окно — то же, что «Отмена»."
      : "Закрыть окно — то же, что отказаться.";
  return { title: ask.title, text: ask.text, lines: ask.lines, options: opts, note, cls: "vm-ask" };
}

// ---------- просто текст (лог ошибок, вывод программы) ----------
export class TextModal extends Modal {
  constructor(app: App, private title: string, private text: string) {
    super(app);
  }
  onOpen() {
    this.setTitle(this.title);
    this.modalEl.addClass("vm-wide");
    this.contentEl.createEl("pre", { cls: "vm-pre", text: this.text || "(пусто)" });
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "Скопировать" }).addEventListener("click", async () => {
      new Notice((await copyText(this.text)) ? "Скопировано" : "Не удалось скопировать — выделите текст и нажмите Ctrl+C.");
    });
    b.createEl("button", { text: "Закрыть" }).addEventListener("click", () => this.close());
  }
  onClose() {
    this.contentEl.empty();
  }
}

// ---------- выбор контейнера ----------
export interface PickItem {
  c: UiContainer | null; // null — «все контейнеры»
  label: string;
}

export class ContainerPicker extends FuzzySuggestModal<PickItem> {
  constructor(private plugin: BrainPlugin, private allLabel: string | null, private onPick: (c: UiContainer | null) => void) {
    super(plugin.app);
    this.setPlaceholder("Начните вводить название контейнера");
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

// ---------- новая мысль ----------
export class NewThoughtModal extends Modal {
  constructor(private plugin: BrainPlugin, private hint = "") {
    super(plugin.app);
  }
  onOpen() {
    const ui = this.plugin.ui;
    this.setTitle("Новая мысль");
    const el = this.contentEl;
    el.addClass("vm-modal", "vm-thought");
    const ta = el.createEl("textarea", { cls: "vm-thought-text", attr: { rows: "7", placeholder: "Что пришло в голову? Пишите как есть." } });
    const grid = el.createDiv({ cls: "vm-form" });

    const f1 = grid.createDiv({ cls: "vm-form-row" });
    f1.createEl("label", { text: "Куда отнести", attr: { for: "vm-hint" } });
    const hint = f1.createEl("input", { type: "text", attr: { id: "vm-hint", list: "vm-hint-list", placeholder: "необязательно — программа решит сама" } });
    hint.value = this.hint;
    const dl = f1.createEl("datalist", { attr: { id: "vm-hint-list" } });
    for (const c of ui?.containers || []) dl.createEl("option", { attr: { value: c.title } });

    const f2 = grid.createDiv({ cls: "vm-form-row" });
    f2.createEl("label", { text: "Дата", attr: { for: "vm-date" } });
    const date = f2.createEl("input", { type: "date", attr: { id: "vm-date" } });
    date.value = todayIso();

    const sources = (ui?.sources || []).map((s) => s.name).filter((n) => n && n.toLowerCase() !== "архив");
    const f3 = grid.createDiv({ cls: "vm-form-row" });
    f3.createEl("label", { text: "Источник", attr: { for: "vm-src" } });
    const src = f3.createEl("select", { cls: "dropdown", attr: { id: "vm-src" } });
    if (!sources.includes("заметка")) src.createEl("option", { text: "заметка", attr: { value: "заметка" } });
    for (const s of sources) src.createEl("option", { text: s, attr: { value: s } });
    src.value = "заметка";

    const f4 = el.createDiv({ cls: "vm-check-row" });
    const now = f4.createEl("input", { type: "checkbox", attr: { id: "vm-now" } });
    now.checked = true;
    f4.createEl("label", { text: "Сразу обработать (Фаза 1)", attr: { for: "vm-now" } });

    const b = el.createDiv({ cls: "vm-modal-buttons" });
    const save = b.createEl("button", { text: "Сохранить", cls: "mod-cta" });
    b.createEl("button", { text: "Отмена" }).addEventListener("click", () => this.close());
    const go = async () => {
      const text = ta.value.trim();
      if (!text) {
        new Notice("Напишите мысль.");
        ta.focus();
        return;
      }
      save.disabled = true;
      try {
        const path = await this.plugin.saveThought(text, hint.value.trim(), date.value || todayIso(), src.value);
        this.close();
        if (now.checked) {
          new Notice(`Мысль сохранена: ${path}. Обрабатываю…`);
          this.plugin.runPhase1();
        } else new Notice(`Мысль сохранена: ${path}. Обработается при следующей Фазе 1.`);
      } catch (e) {
        save.disabled = false;
        new Notice(`Не удалось сохранить: ${e}`);
      }
    };
    save.addEventListener("click", go);
    ta.addEventListener("keydown", (ev: KeyboardEvent) => {
      if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
        ev.preventDefault();
        go();
      }
    });
    el.createDiv({ cls: "vm-muted vm-small-text", text: "Ctrl+Enter — сохранить. Файл попадёт в _staging с пометкой «одна запись»." });
    window.setTimeout(() => ta.focus(), 0);
  }
  onClose() {
    this.contentEl.empty();
  }
}

/** Текст файла «Новой мысли»: шапка (дата, подсказка, служебная строка режима), пустая строка, текст. */
export function thoughtFile(text: string, hint: string, dateIso: string): { name: string; body: string } {
  const [y, m, d] = dateIso.split("-");
  const head = [`${d}.${m}.${y}`];
  if (hint) head.push(`hint: ${hint}`);
  head.push("mode: steady_state");
  return { name: `${dateIso} ${nowHm()} ${fileSlug(text)}.txt`, body: head.join("\n") + "\n\n" + text.trim() + "\n" };
}

// ---------- совет ИИ по порогам ----------
function sourceText(r: AdviceRec): string {
  if (r.source === "own") return "сейчас — свой порог контейнера";
  if (r.source === "parent") return `сейчас — от родителя «${r.from}»`;
  return "сейчас — общий порог из настроек";
}

export class AdviceModal extends Modal {
  private alive = true;
  constructor(private plugin: BrainPlugin, private c: UiContainer, private ready?: Advice) {
    super(plugin.app);
  }
  async onOpen() {
    this.setTitle(`Совет ИИ по порогам · ${this.c.title}`);
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
        ? "В очереди: совет начнётся после текущего запуска."
        : "Модель изучает, как программа решала по этому контейнеру: ошибки раскладки, лишние вопросы, что попало в базу…",
    });
    w.createDiv({ cls: "vm-muted", text: "Это одно обращение к модели. Окно можно закрыть — совет сохранится во вкладке «Контейнер»." });
    const r: RunResult = await this.plugin.adviseNow(this.c);
    if (!this.alive) return;
    this.contentEl.empty();
    if (!r.ok || !r.advice) {
      const box = this.contentEl.createDiv({ cls: "vm-callout is-warning" });
      box.createDiv({ text: r.error || r.title || "Совет не получен." });
      this.closeButton();
      return;
    }
    this.show(r.advice);
  }

  private show(a: Advice) {
    const el = this.contentEl;
    el.createDiv({ cls: "vm-advice-summary", text: a.summary || "Модель не написала вывода." });
    const chosen = new Set<string>(a.recommendations.map((r) => r.name));
    if (!a.recommendations.length) el.createDiv({ cls: "vm-callout is-ok", text: "Менять пороги не нужно." });
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
      det.createEl("summary", { text: "На чём основан совет" });
      const ul = det.createEl("ul");
      for (const line of a.brief) ul.createEl("li", { text: line });
    }
    const b = el.createDiv({ cls: "vm-modal-buttons" });
    if (a.recommendations.length) {
      apply = b.createEl("button", { text: "Применить выбранное", cls: "mod-cta" });
      apply.addEventListener("click", async () => {
        const changes: Record<string, number> = {};
        for (const r of a.recommendations) if (chosen.has(r.name)) changes[r.name] = r.value;
        apply!.disabled = true;
        const ok = await this.plugin.saveThresholds(this.c, changes);
        if (ok) {
          new Notice(`Пороги «${this.c.title}» обновлены: ` + a.recommendations.filter((r) => chosen.has(r.name)).map((r) => `${r.label.toLowerCase()} ${r.current} → ${r.value}`).join(", "));
          this.plugin.forgetAdvice(this.c.id);
          this.close();
        } else apply!.disabled = false;
      });
    }
    b.createEl("button", { text: "Закрыть" }).addEventListener("click", () => this.close());
    el.createDiv({
      cls: "vm-muted vm-small-text",
      text: "Выбранные значения запишутся в YAML контейнера (поле thresholds) и подействуют со следующей Фазы 1. Программа запомнит, какой совет вы приняли.",
    });
  }

  private closeButton() {
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "Закрыть" }).addEventListener("click", () => this.close());
  }

  onClose() {
    this.alive = false;
    this.contentEl.empty();
  }
}

// ---------- проверка связи ----------
export class CheckModal extends Modal {
  private alive = true;
  constructor(private plugin: BrainPlugin) {
    super(plugin.app);
  }
  async onOpen() {
    this.setTitle("Проверка связи");
    this.contentEl.addClass("vm-modal");
    const w = this.contentEl.createDiv({ cls: "vm-wait" });
    w.createDiv({ cls: "vm-progress" });
    w.createDiv({ text: "Проверяю хранилище, модель и эмбеддинги — несколько секунд…" });
    const r = await this.plugin.engine.run(["check"], { label: "Проверка связи", exclusive: false });
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
    if (!items.length || r.error) this.contentEl.createDiv({ cls: "vm-callout is-warning", text: r.error || "Программа не ответила." });
    else this.contentEl.createDiv({ cls: "vm-callout " + (r.ok ? "is-ok" : "is-warning"), text: r.ok ? "Всё в порядке." : "Есть проблемы — см. строки с ✗." });
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "Закрыть", cls: "mod-cta" }).addEventListener("click", () => this.close());
  }
  onClose() {
    this.alive = false;
    this.contentEl.empty();
  }
}

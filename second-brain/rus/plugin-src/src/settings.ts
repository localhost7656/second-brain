// Настройки: вкладки (Основное, Модели, Пороги, Входящие, Документы, Расходы, Дополнительно) и поиск.
// «Программа» и уведомления — настройки самого плагина; остальное — settings.yaml программы по её схеме.
import { App, Notice, PluginSettingTab, Setting, TextComponent } from "obsidian";
import type BrainPlugin from "./main";
import { renderError, saveDeveloperReport } from "./report";
import type { SchemaField, SchemaSection, SettingsInfo } from "./types";
import { PTYPE_RU, parseNumber, rangeText } from "./util";

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
const FIXED_SOURCES: Record<string, string> = { архив: "старые записи: _staging/архив", заметка: "файлы прямо в _staging" };
const TAB_ORDER = ["main", "models", "thresholds", "input", "docs", "costs", "advanced"];
const TAB_NAMES: Record<string, string> = {
  main: "Основное", models: "Модели", thresholds: "Пороги", input: "Входящие", docs: "Документы", costs: "Расходы", advanced: "Дополнительно",
};

/** В какой вкладке настройка, о которой говорит ошибка программы. */
export function tabOfError(msg: string): string {
  const m = msg.trim().toLowerCase();
  if (/^llm\.(webchat|max_format_retries)|^limits\./.test(m)) return "advanced";
  if (/^(профиль|llm\.|embeddings\.)/.test(m)) return "models";
  if (/^(thresholds\.|seed_dormancy_days)/.test(m)) return "thresholds";
  if (/^(budget\.|estimate\.)/.test(m)) return "costs";
  if (/^(sources|dialogue_markers|input\.)/.test(m)) return "input";
  if (/^style\./.test(m)) return "docs";
  return "main";
}

function fmt(v: any): string {
  if (v === null || v === undefined || v === "") return "пусто";
  if (typeof v === "boolean") return v ? "вкл." : "выкл.";
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
  // не navEl и не renderTab: эти имена Obsidian 1.13+ использует внутри SettingTab (пункт меню слева и отрисовка вкладки)
  private barEl: HTMLElement | null = null;
  private bodyEl: HTMLElement | null = null;
  private dynEl: HTMLElement | null = null;
  private statusEl: HTMLElement | null = null;
  private progTimer: number | null = null;
  private lastProblem: string | null = null;

  constructor(app: App, private plugin: BrainPlugin) {
    super(app, plugin);
  }

  /** Obsidian открыл вкладку настроек: показать сохранённое и перечитать settings.yaml. */
  display() {
    try {
      this.redraw();
    } catch (e) {
      this.containerEl.empty();
      renderError(this.containerEl.createDiv({ cls: "vm-settings" }), this.plugin, "настройки", e);
    }
    if (!this.plugin.engine.problem()) this.load();
  }

  hide() {
    this.flush();
  }

  /** Открыть настройки на нужной вкладке (из панели). */
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

  // ---------- вкладки и поиск ----------
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
      if (bad.has(id)) b.setAttr("title", "Здесь ошибка — настройки не сохранены");
      b.addEventListener("click", () => {
        this.tab = id;
        this.query = "";
        this.renderNav();
        this.renderBody();
        this.containerEl.scrollTop = 0;
      });
    }
    const search = nav.createEl("input", { type: "search", cls: "vm-set-search", attr: { placeholder: "Поиск настройки…", "aria-label": "Поиск настройки" } });
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
    return this.query.trim() ? "настройки, поиск" : `настройки, вкладка «${this.tabNames()[tab] || tab}»`;
  }

  /** Перерисовать изменчивую часть вкладки (поле «Папка программы» при этом не теряет фокус). */
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
    for (const e of this.errors.filter((x) => x.tab === tab)) el.createDiv({ cls: "vm-callout is-warning", text: "Не сохранено: " + e.text });
    if (this.plugin.engine.problem()) {
      if (tab !== "main") el.createDiv({ cls: "vm-callout is-warning", text: "Сначала укажите папку программы — вкладка «Основное»." });
      return;
    }
    if (!this.info || !this.values) {
      el.createDiv({ cls: this.loadError ? "vm-callout is-warning" : "vm-muted", text: this.loadError || "Загружаю настройки программы…" });
      if (this.loadError) new Setting(el).addButton((b) => b.setButtonText("Повторить").onClick(() => this.load()));
      return;
    }
    for (const sec of this.info.schema.filter((s) => (s.tab || "advanced") === tab)) this.renderSection(el, sec);
    if (tab === "models") {
      const emb = (this.values.embeddings || {}) as Obj;
      if (emb.mode === "local" && String(emb.base_url || "").includes(":11434")) {
        new Setting(el)
          .setName("Модель эмбеддингов в Ollama")
          .setDesc(`Скачать «${emb.model || "?"}» в Ollama — несколько гигабайт, один раз. Нужна установленная Ollama (ollama.com).`)
          .addButton((b) => b.setButtonText("Скачать модель").onClick(async () => {
            await this.flush();
            this.plugin.runPullEmbeddings();
          }));
      }
      new Setting(el)
        .setName("Проверка связи")
        .setDesc("Основная модель, модели отдельных шагов и эмбеддинги — каждая отдельно.")
        .addButton((b) => b.setButtonText("Проверить связь").setCta().onClick(async () => {
          await this.flush();
          this.plugin.runCheck();
        }));
    }
    if (tab === "costs") {
      new Setting(el)
        .setName("Подробные расходы")
        .setDesc("По моделям, шагам, дням и запускам, цены облачных профилей — вкладка «Расходы» панели «Второй мозг».")
        .addButton((b) => b.setButtonText("Открыть «Расходы»").onClick(async () => {
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
    if (!found) el.createDiv({ cls: "vm-muted vm-search-none", text: `Ничего не найдено по запросу «${this.query.trim()}».` });
  }

  private section(el: HTMLElement, title: string, help?: string): HTMLElement {
    const box = el.createDiv({ cls: "vm-sec" });
    new Setting(box).setName(title).setHeading();
    if (help) box.createDiv({ cls: "setting-item-description vm-sec-help", text: help });
    return box;
  }

  private renderSection(el: HTMLElement, sec: SchemaSection) {
    const box = this.section(el, sec.title, sec.help);
    for (const f of sec.fields) if (this.visible(f)) this.renderField(box, f);
    if (sec.id === "updates") this.renderUpdateButtons(box);
  }

  private visible(f: SchemaField): boolean {
    if (!f.show_if || !this.values) return true;
    return Object.entries(f.show_if).every(([k, vals]) => vals.includes(String(getPath(this.values!, k))));
  }

  private async load() {
    if (this.loading) return;
    this.loading = true;
    const r = await this.plugin.engine.run(["settings"], { label: "Настройки", exclusive: false, quiet: true });
    this.loading = false;
    if (r.ok && r.settings) {
      const changed = !this.info || JSON.stringify(r.settings) !== JSON.stringify(this.info);
      this.info = r.settings;
      if (!this.dirty.size) this.values = clone(r.settings.values);
      this.loadError = null;
      if (changed) this.redraw();
    } else {
      this.loadError = "Не удалось прочитать настройки программы: " + (r.error || "нет ответа");
      this.redraw();
    }
  }

  // ---------- «Программа» и уведомления (настройки плагина) ----------
  private renderProgram(el: HTMLElement) {
    const p = this.plugin;
    const box = this.section(el, "Программа");
    new Setting(box)
      .setName("Папка программы")
      .setDesc("Папка, где лежат «Установка.bat» и папка brain. Её вписывает «Установка.bat».")
      .setClass("vm-wide-setting")
      .addText((t) => t.setPlaceholder("C:\\Второй мозг").setValue(p.data.programDir).onChange(async (v) => {
        p.data.programDir = v.trim();
        await p.saveData(p.data);
        this.programChanged();
      }));
    new Setting(box)
      .setName("Python")
      .setDesc("Обычно менять не нужно: пусто — Python, который поставила «Установка.bat».")
      .setClass("vm-wide-setting")
      .addText((t) => t.setPlaceholder(p.engine.defaultPython()).setValue(p.data.pythonPath).onChange(async (v) => {
        p.data.pythonPath = v.trim();
        await p.saveData(p.data);
        this.programChanged();
      }));
    this.statusEl = box.createDiv();
    this.renderStatus();
    new Setting(box)
      .setName("Проверка связи")
      .setDesc("Хранилище, модель (для каждой модели шага — отдельно) и эмбеддинги.")
      .addButton((b) => b.setButtonText("Проверить связь").setCta().onClick(async () => {
        await this.flush();
        p.runCheck();
      }));
  }

  private renderNotify(el: HTMLElement) {
    const p = this.plugin;
    const d = p.data;
    const save = () => p.saveData(d);
    const box = this.section(el, "Уведомления Windows", "Системные уведомления — когда Obsidian свёрнут или вы работаете в другом окне.");
    new Setting(box)
      .setName("Сообщать об окончании долгого запуска")
      .setDesc("Фаза 1, Фаза 2, ревалидация — если запуск шёл дольше, чем указано ниже.")
      .addToggle((t) => t.setValue(d.notify).onChange(async (v) => {
        d.notify = v;
        await save();
      }));
    const m = new Setting(box).setName("Долгий запуск — дольше, минут").setDesc("0 — сообщать о любом запуске.");
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
      .setName("Сообщать, когда программа ждёт ответа")
      .setDesc("Например: бюджет исчерпан или нужно подтвердить большой запуск.")
      .addToggle((t) => t.setValue(d.notifyAsk).onChange(async (v) => {
        d.notifyAsk = v;
        await save();
      }));
    new Setting(box)
      .setName("Только когда Obsidian не в фокусе")
      .setDesc("Выключите, чтобы уведомления приходили всегда.")
      .addToggle((t) => t.setValue(d.notifyUnfocused).onChange(async (v) => {
        d.notifyUnfocused = v;
        await save();
      }));
    new Setting(box)
      .setName("Пробное уведомление")
      .setDesc("Если оно не появилось — разрешите уведомления для Obsidian в параметрах Windows (Система → Уведомления).")
      .addButton((b) => b.setButtonText("Показать").onClick(() => {
        const ok = p.osNotify("Второй мозг", "Так выглядит уведомление об окончании долгого запуска.", "done", true);
        if (!ok) new Notice("Система не дала показать уведомление: разрешите уведомления для Obsidian в параметрах Windows.", 10000);
      }));
  }

  private renderUpdateButtons(el: HTMLElement) {
    const skip = this.plugin.data.skipVersion;
    new Setting(el)
      .setName("Проверить сейчас")
      .setDesc(`Установлена версия ${this.info?.version || "?"}.` + (skip ? ` Пропущенная версия: ${skip} — при проверке по кнопке она предлагается снова.` : ""))
      .addButton((b) => b.setButtonText("Проверить обновления").onClick(async () => {
        await this.flush();
        this.plugin.checkUpdates(true);
      }));
  }

  private renderService(el: HTMLElement) {
    const box = this.section(el, "Служебное");
    new Setting(box)
      .setName("Промпты")
      .setDesc("Тексты запросов к модели — файлы в папке программы. Их можно править; изменения подействуют со следующего запуска. При обновлении ваши правки не теряются.")
      .addButton((b) => b.setButtonText("Открыть папку промптов").onClick(() => this.plugin.revealPath(this.info!.prompts_dir)));
    new Setting(box)
      .setName("Файл настроек")
      .setDesc(`${this.info!.path} — плагин переписывает его целиком с пояснениями, прежний сохраняется в settings.yaml.bak.`)
      .addButton((b) => b.setButtonText("Показать в папке").onClick(() => this.plugin.revealPath(this.info!.path, true)));
    new Setting(box)
      .setName("Отчёт для разработчика")
      .setDesc("Если что-то работает не так: версии, последние ошибки и вывод последних запусков — в файл _логи/отчёт для разработчика.md и в буфер обмена. Ключей API и текстов заметок в нём нет.")
      .addButton((b) => b.setButtonText("Собрать отчёт").onClick(async () => {
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
    el.setText(prob || `Программа найдена${this.info ? `, версия ${this.info.version}` : ""}. Хранилище: ${this.plugin.engine.vaultPath()}`);
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

  // ---------- поля по схеме ----------
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
        new Setting(el).setName(f.label).setDesc(`${f.help} Правится в settings.yaml.`);
    }
  }

  /** «↺» — вернуть значение по умолчанию. Видна, только пока значение отличается от умолчания;
   *  возвращает функцию, которую поле вызывает на каждую правку (кнопка появляется сразу, без перерисовки). */
  private resetButton(s: Setting, def: any, v: any, put: Put): (x: any) => void {
    if (def === undefined) return () => {};
    let btn: HTMLElement | null = null;
    s.addExtraButton((b) => {
      b.setIcon("rotate-ccw").setTooltip(`По умолчанию: ${fmt(def)}`).onClick(() => {
        put(clone(def));
        this.rerender();
      });
      btn = b.extraSettingsEl;
      btn.addClass("vm-reset");
    });
    const mark = (x: any) => {
      const changed = !same(def, x);
      btn?.toggleClass("vm-hidden", !changed);
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
        if (this.dependents(f.key)) this.rerender(); // поля, видимые только при некоторых значениях
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

  /** Число: поле ввода, у порогов и температуры — ещё ползунок. «int?»/«float?» — можно оставить пустым. */
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
      err.setText(bad ? `Нужно ${rangeText(kind, f.min, f.max)}${optional ? " (или пусто)" : ""}.` : "");
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
      if (optional) t.setPlaceholder(f.placeholder || (f.key.endsWith("max_tokens") ? "как у провайдера" : "не задано"));
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
          if (typeof obj !== "object" || Array.isArray(obj) || obj === null) throw new Error("нужен объект { … }");
        } catch (e) {
          err.setText(`Не JSON: ${(e as Error).message}`);
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

  /** Ключ: profile:<id>, embeddings, github (llm — ключ основной облачной модели, как в v2.4). */
  private fieldKey(el: HTMLElement, label: string, help: string, target: string, prof?: Obj) {
    const keys = this.info!.keys;
    let present = target === "embeddings" ? keys.embeddings : target === "github" ? keys.github
      : target.startsWith("profile:") ? !!keys.profiles?.[target.slice(8)] : keys.llm;
    if (prof && !prof.api_key_file) present = false;
    const s = new Setting(el).setName(label).setDesc(help);
    s.descEl.createDiv({ cls: present ? "vm-key-ok" : "vm-muted", text: present ? `✓ ключ сохранён${prof?.api_key_file ? ` (${prof.api_key_file})` : ""}` : "ключа нет" });
    if (prof && prof.api_key_file) {
      const others = (this.values!.llm.profiles as Obj[]).filter((x) => x !== prof && x.api_key_file === prof.api_key_file);
      if (others.length) {
        s.descEl.createDiv({ cls: "vm-field-note", text: `Файл ключа ${prof.api_key_file} общий с профилем «${others.map((o) => o.name).join("», «")}»: новый ключ заменит его и там.` });
        s.addButton((b) => b.setButtonText("Отдельный ключ").setTooltip("Этому профилю — свой файл ключа").onClick(() => {
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
      t.setPlaceholder(present ? "вставьте новый, чтобы заменить" : "вставьте ключ");
    });
    s.addButton((b) => b.setButtonText("Сохранить").onClick(async () => {
      const k = input.getValue().trim();
      if (!k) {
        new Notice("Вставьте ключ в поле.");
        return;
      }
      await this.saveKey(target, k);
    }));
    if (present)
      s.addExtraButton((b) => b.setIcon("trash-2").setTooltip("Удалить ключ").onClick(async () => {
        const what = target === "github" ? "Без токена закрытый репозиторий не проверить." : target === "embeddings" ? "Без ключа облачные эмбеддинги работать не будут." : "Без ключа облачная модель работать не будет.";
        const ok = await this.plugin.confirm({ title: "Удалить ключ?", text: `Файл с ключом будет удалён. ${what}`, ok: "Удалить", warning: true });
        if (ok) await this.saveKey(target, "");
      }));
  }

  private async saveKey(target: string, key: string) {
    await this.flush(); // новый профиль должен попасть в settings.yaml раньше ключа
    const r = await this.plugin.engine.run(["settings", "--key", target], { label: "Ключ", stdin: key + "\n", exclusive: false, quiet: true });
    if (r.ok) {
      new Notice(r.title || "Ключ сохранён.");
      if (r.settings) {
        this.info = r.settings;
        if (!this.dirty.size) this.values = clone(r.settings.values);
      }
      this.redraw();
    } else new Notice("Ключ не сохранён: " + (r.error || "ошибка"), 10000);
  }

  // ---------- режим и профили моделей ----------
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
    if (llm.mode && !(llm.mode in modes)) modes[llm.mode] = llm.mode === "fake" ? "Тестовая модель (для проверки)" : llm.mode;
    new Setting(el)
      .setName("Режим")
      .setDesc("Где работает основная модель.")
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
        .setName(kind === "cloud" ? "Облачный профиль" : "Локальный профиль")
        .setDesc("На нём работает программа. Отдельным шагам можно дать другие профили — ниже, в «Модели для отдельных шагов».")
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
        text: "Веб-чат: программа кладёт запросы в папку _веб-чат хранилища, вы копируете их в чат модели и вставляете ответы в файлы ответов. Профили ниже нужны, только если отдельным шагам отданы свои модели.",
      });
    }
    this.profileEditor(el);
  }

  /** Профиль в текущих значениях. После каждого сохранения значения заменяются присланными программой,
   *  поэтому кнопки и поля, нарисованные раньше, находят свой профиль по id, а не по старой ссылке. */
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

  /** Новый профиль (или копия): id p<N>, имя без повторов, ключ — свой (файл появится, когда сохраните ключ). */
  private newProfile(kind: string, base?: Obj): Obj {
    const llm = this.llm();
    const profiles = llm.profiles as Obj[];
    const ids = new Set(profiles.map((p) => p.id));
    let n = profiles.length + 1;
    while (ids.has(`p${n}`)) n++;
    const id = `p${n}`;
    const def = clone(this.info!.profile_defaults?.[kind] || { kind, name: kind === "local" ? "Локальная модель" : "Облачная модель" });
    const p: Obj = base ? { ...clone(base), id } : { ...def, id, kind };
    const names = new Set(profiles.map((x) => String(x.name || "").toLowerCase()));
    const root = base ? `${base.name || base.id} (копия)` : String(def.name || "Профиль");
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
    if (llm.cloud_profile === p.id) out.push(llm.mode === "cloud" ? "основная модель" : "облачный профиль по умолчанию");
    if (llm.local_profile === p.id) out.push(llm.mode === "local" ? "основная модель" : "локальный профиль по умолчанию");
    const steps = Object.entries(llm.roles || {}).filter(([, v]) => v === p.id).map(([k]) => k);
    if (steps.length) out.push("шаги: " + steps.join(", "));
    return out;
  }

  private profileEditor(el: HTMLElement) {
    const llm = this.llm();
    const profiles = llm.profiles as Obj[];
    const box = el.createDiv({ cls: "vm-prof-editor" });
    const main = llm.mode === "local" ? llm.local_profile : llm.cloud_profile;
    const cur = profiles.find((p) => p.id === this.editProfile) || profiles.find((p) => p.id === main) || profiles[0];
    const s = new Setting(box)
      .setName("Профиль для правки")
      .setDesc("Облачные профили — с ценами и подсчётом денег, локальные — с подсчётом токенов и времени работы.");
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
    s.addButton((b) => b.setButtonText("＋ Облачный").setTooltip("Новый облачный профиль").onClick(() => {
      this.newProfile("cloud");
      this.rerender();
    }));
    s.addButton((b) => b.setButtonText("＋ Локальный").setTooltip("Новый профиль своей модели (llama.cpp, Ollama)").onClick(() => {
      this.newProfile("local");
      this.rerender();
    }));
    if (!cur) {
      box.createDiv({ cls: "vm-callout is-warning", text: "Профилей нет — создайте облачный или локальный." });
      return;
    }
    s.addButton((b) => b.setButtonText("Копия").setTooltip("Такой же профиль — например, другая модель того же провайдера").onClick(() => {
      this.newProfile(cur.kind, cur);
      this.rerender();
    }));
    s.addExtraButton((b) => b.setIcon("trash-2").setTooltip("Удалить профиль").onClick(() => this.deleteProfile(cur)));
    const used = this.profileUse(cur, llm);
    const fbox = box.createDiv({ cls: "vm-prof-box" });
    fbox.createDiv({ cls: "vm-prof-title", text: `${cur.name || cur.id} · ${PTYPE_RU[cur.kind] || cur.kind}` });
    fbox.createDiv({ cls: "vm-muted vm-small-text", text: used.length ? `Используется: ${used.join("; ")}.` : "Сейчас не используется: выберите его выше как основной или отдайте ему шаги." });
    let pricesHead = false;
    for (const f of this.info!.profile_fields || []) {
      if (f.kinds && !f.kinds.includes(cur.kind)) continue;
      if (f.group === "prices" && !pricesHead) {
        pricesHead = true;
        fbox.createDiv({ cls: "vm-prof-sub", text: "Цены и лимит — для подсчёта расходов. Цены — из прайса провайдера, в долларах за миллион токенов." });
      }
      this.profileField(fbox, cur, f);
    }
  }

  private profileField(el: HTMLElement, prof: Obj, f: SchemaField) {
    const put: Put = (v) => {
      const live = this.liveProfile(prof.id);
      if (!live) return; // профиль уже удалён
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
      new Notice("Это единственный профиль — сначала создайте другой.", 6000);
      return;
    }
    const used = this.profileUse(p, this.llm());
    const ok = await this.plugin.confirm({
      title: "Удалить профиль?",
      text: `Профиль «${p.name || p.id}» исчезнет из настроек.` + (used.length ? ` Сейчас он используется (${used.join("; ")}) — вместо него встанет первый подходящий профиль, а шаги вернутся на основную модель.` : "")
        + "\n\nФайл ключа не удаляется. История расходов профиля останется во вкладке «Расходы» панели.",
      ok: "Удалить",
      warning: true,
    });
    if (!ok) return;
    // пока окно было открыто, значения могли замениться сохранёнными — берём текущие
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
        d.addOption("", "Как основная");
        for (const p of profiles) d.addOption(p.id, `${p.name || p.id} (${PTYPE_RU[p.kind] || p.kind})`);
        d.addOption("webchat", "Вручную через веб-чат");
        if (v && v !== "webchat" && !profiles.some((p) => p.id === v)) d.addOption(v, `${v} — нет такого профиля`);
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
        text: `Длинный материал (шаги: ${f.split_prompts.join(", ")}) делится на части по «пределу запроса» профиля, который отвечает на шаг.`,
      });
  }

  private fieldSources(el: HTMLElement, f: SchemaField) {
    const list: Obj[] = Array.isArray(this.values!.sources) ? this.values!.sources : (this.values!.sources = []);
    if (f.help) el.createDiv({ cls: "setting-item-description vm-sec-help", text: f.help });
    list.forEach((src, i) => {
      const fixed = FIXED_SOURCES[String(src.name || "").toLowerCase()];
      const s = new Setting(el).setName(fixed ? String(src.name) : src.name ? `_staging/${src.name}` : "Новый источник").setDesc(fixed || "подпапка _staging");
      s.settingEl.addClass("vm-source");
      if (!fixed)
        s.addText((t) => {
          t.setPlaceholder("название папки").setValue(src.name || "");
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
        t.inputEl.title = "На сколько пунктов понизить порог уплотнения для этого источника";
        t.setPlaceholder("сдвиг").setValue(String(src.compaction_shift ?? 0));
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
        s.addExtraButton((b) => b.setIcon("trash-2").setTooltip("Убрать источник").onClick(() => {
          list.splice(i, 1);
          this.set("sources", list);
          this.rerender();
        }));
    });
    new Setting(el).addButton((b) => b.setButtonText("Добавить источник").onClick(() => {
      list.push({ name: "", color: "#64748b", compaction_shift: 0 });
      this.rerender();
    }));
  }

  // ---------- сохранение ----------
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
        // программе профили передаются по id: {id: {поля}}, удалённые — {id: null}
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

  /** Отправить накопленные изменения программе: она проверит их и перепишет settings.yaml. */
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
      const r = await this.plugin.engine.run(["settings", "--set-json", "-"], { label: "Сохранение настроек", stdin: JSON.stringify(patch), exclusive: false, quiet: true });
      if (r.ok && r.settings) {
        this.info = r.settings;
        if (!this.dirty.size) this.values = clone(r.settings.values);
        const hadErrors = this.errors.length > 0;
        this.errors = [];
        if (hadErrors) {
          this.renderNav();
          this.rerender();
        }
        new Notice("Настройки сохранены.", 2500);
        this.plugin.refreshState();
      } else {
        const text = String(r.error || "Настройки не сохранены.");
        const body = text.replace(/^Настройки не сохранены:\s*/, "");
        this.errors = body.split(/;\s+/).filter(Boolean).map((t) => ({ text: t, tab: tabOfError(t) }));
        new Notice(text + " Показаны сохранённые значения.", 12000);
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

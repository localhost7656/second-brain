// Плагин «Второй мозг»: панель, команды и настройки поверх программы на Python.
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
  /** уведомления Windows */
  notify: boolean;
  notifyMinutes: number; // «долгий запуск» — дольше стольких минут
  notifyAsk: boolean; // программа ждёт ответа
  notifyUnfocused: boolean; // только когда окно Obsidian не в фокусе
  /** версия, которую пользователь решил пропустить */
  skipVersion: string;
}

const DEFAULTS: PluginData = {
  programDir: "", pythonPath: "", welcomed: false,
  notify: true, notifyMinutes: 2, notifyAsk: true, notifyUnfocused: true, skipVersion: "",
};
/** команды, которые могут спросить посреди запуска (бюджет, оценка большого запуска) */
const INTERACTIVE = new Set(["run", "synth", "revalidate", "patterns", "advise", "answer"]);

/** a новее b? Сравнение по числам: 2.10.0 > 2.9.1. */
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
const APPROVE = "Структура утверждена";

export default class BrainPlugin extends Plugin {
  data: PluginData = { ...DEFAULTS };
  engine!: Engine;
  /** ошибки самого плагина: _логи/плагин.log и «Отчёт для разработчика» */
  errors!: ErrorLog;
  ui: UiSnapshot | null = null;
  snapshotError: string | null = null;
  views = new Set<BrainView>();
  advice = new Map<string, { advice: Advice; at: string }>();
  lastWebchat: { label: string; args: string[] } | null = null;
  private uiMtime = 0;
  private statusEl: HTMLElement | null = null;
  // не settingTab: это имя Obsidian использует внутри Plugin
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
      this.osNotify("Второй мозг", text, "notice");
    };
    this.engine.onAsk = (job, ask) => this.askUser(job, ask);
    this.registerView(VIEW_TYPE, (leaf) => new BrainView(leaf, this));
    this.addRibbonIcon("brain", "Второй мозг", () => this.openView());
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

  /** Неперехваченные ошибки кода плагина (Obsidian подписывает его как «plugin:<id>») — в _логи/плагин.log. */
  private catchErrors() {
    const mark = "plugin:" + encodeURIComponent(this.manifest.id);
    const mine = (e: unknown, file?: string) => errParts(e).stack.includes(mark) || String(file || "").includes(mark);
    this.registerDomEvent(window, "error", (ev: ErrorEvent) => {
      if (mine(ev.error, ev.filename)) this.errors.add("неперехваченная ошибка", ev.error || ev.message, true);
    });
    this.registerDomEvent(window, "unhandledrejection", (ev: PromiseRejectionEvent) => {
      if (mine(ev.reason)) this.errors.add("неперехваченная ошибка", ev.reason, true);
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

  // ---------- обновления ----------
  /** При запуске Obsidian: новая версия плагина в папке программы? новая версия программы на GitHub? */
  private async startupChecks() {
    if (this.engine.problem()) return;
    try {
      if (await this.offerPluginFromProgram()) return;
      const u = this.ui?.updates;
      if (u?.repo && u.check_on_start) await this.checkUpdates(false);
    } catch (e) {
      console.warn("Второй мозг: проверка обновлений", e);
    }
  }

  /** Версия плагина, которая лежит в папке программы (её кладёт туда обновление или распаковка нового архива). */
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

  /** В папке программы плагин новее установленного — предложить поставить его в хранилище. */
  private async offerPluginFromProgram(): Promise<boolean> {
    const v = await this.programPluginVersion();
    if (!v || !newerVersion(v, this.manifest.version)) return false;
    const ch = await choiceModal(this.app, {
      title: "Новая версия плагина",
      text: `В папке программы лежит плагин версии ${v}, а в Obsidian работает ${this.manifest.version}. Установить новый? Настройки плагина сохранятся; после установки Obsidian нужно перезапустить.`,
      options: [{ label: "Установить", kind: "cta" }, { label: "Позже" }],
    }).result;
    if (ch !== 0) return true;
    const r = await this.engine.run(["install-plugin", this.engine.vaultPath()], { label: "Установка плагина" });
    if (!r.ok) {
      new Notice(`Плагин не установлен: ${r.error || "ошибка"}`, 15000);
      return true;
    }
    await this.offerRestart(`Плагин ${v} установлен.`);
    return true;
  }

  /** Проверить новую версию программы на GitHub; manual — по кнопке (сообщить и «последняя версия»). */
  async checkUpdates(manual: boolean): Promise<void> {
    const prob = this.engine.problem();
    if (prob) {
      if (manual) new Notice(prob, 10000);
      return;
    }
    const r = await this.engine.run(["update", "--check"], { label: "Проверка обновлений", exclusive: false, quiet: true });
    if (!r.ok || !r.update) {
      if (manual) new Notice(`Проверка обновлений: ${r.error || "программа не ответила"}`, 12000);
      else console.warn("Второй мозг: проверка обновлений —", r.error);
      return;
    }
    const u = r.update;
    if (!u.newer) {
      if (manual) new Notice(`Установлена последняя версия: ${u.current} (в репозитории ${u.repo} — ${u.version || "?"}).`, 8000);
      return;
    }
    if (!manual && this.data.skipVersion && this.data.skipVersion === u.version) return;
    const notes = (u.notes || "").split("\n").slice(0, 40).join("\n").trim();
    const from = u.source === "release" ? `релиз ${u.tag || u.version}` : `ветка ${u.branch || "main"}`;
    const ch = await choiceModal(this.app, {
      title: `Вышла новая версия: ${u.version}`,
      sub: `${u.repo} · ${from}`,
      text: `Сейчас установлена ${u.current}. Обновление заменит файлы программы и плагина; настройки, ключи и хранилище не меняются. Промпты, которые вы правили, не пропадут: если в новой версии они изменились, ваши копии лягут в папку prompts/_прежние.`,
      pre: notes || undefined,
      options: [{ label: "Установить", kind: "cta" }, { label: "Позже" }, { label: "Пропустить эту версию" }],
    }).result;
    if (ch === 2) {
      this.data.skipVersion = u.version || "";
      await this.saveData(this.data);
      new Notice(`Версия ${u.version} пропущена. Проверить вручную — «Настройки → Второй мозг → Обновления».`, 8000);
    } else if (ch === 0) await this.installUpdate(u);
  }

  async installUpdate(u: UpdateInfo) {
    if (this.engine.busy()) new Notice("Обновление начнётся после текущего запуска.", 6000);
    const r = await this.engine.run(["update", "--yes"], { label: `Обновление до ${u.version}` });
    if (!r.ok) {
      new Notice(`Обновление не установлено: ${r.error || "ошибка"}`, 15000);
      return;
    }
    const inst = r.installed;
    if (!inst) {
      new Notice(r.title || "Обновлять нечего.", 8000);
      return;
    }
    await this.refreshState(true);
    const lines = [`Обновлено файлов: ${inst.updated}, новых: ${inst.added}` + (inst.removed.length ? `, удалено устаревших: ${inst.removed.length}` : "") + "."];
    for (const n of inst.notes || []) lines.push(n);
    if (r.restart) await this.offerRestart(`Установлена версия ${inst.version}.`, lines);
    else
      await choiceModal(this.app, {
        title: `Установлена версия ${inst.version}`, lines,
        text: "Плагин в этом хранилище не найден — если он стоит в другом, запустите «Установка.bat» и выберите это хранилище.",
        options: [{ label: "Готово", kind: "cta" }],
      }).result;
  }

  /** Окно «перезапустить Obsidian» — новый плагин заработает после перезапуска. */
  async offerRestart(title: string, lines?: string[]) {
    const ch = await choiceModal(this.app, {
      title, lines,
      text: "Чтобы заработал новый плагин, Obsidian нужно перезапустить. Открытые заметки сохранены.",
      options: [{ label: "Перезапустить Obsidian", kind: "cta" }, { label: "Позже" }],
    }).result;
    if (ch === 0) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const cmds = (this.app as any).commands;
      if (!cmds?.executeCommandById?.("app:reload")) window.location.reload();
    }
  }

  // ---------- вопросы посреди запуска и уведомления Windows ----------
  private askUser(job: Job, ask: AskEvent): Promise<number | null> {
    this.osNotify("Второй мозг ждёт ответа", `${job.label}: ${ask.title}`, "ask");
    const m = choiceModal(this.app, { ...askOptions(ask), sub: job.label });
    job.askCancel = m.close;
    this.refresh();
    return m.result;
  }

  /** Какое-нибудь окно Obsidian сейчас в фокусе: главное, отдельные окна с вкладками, окно настроек (Obsidian 1.15+). */
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
      /* старый Obsidian — достаточно главного окна */
    }
    for (const d of docs) {
      try {
        if (d.hasFocus()) return true;
      } catch {
        /* окно уже закрыто */
      }
    }
    return false;
  }

  /** Уведомление Windows (системное). force — проверка из настроек: без условий. */
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
          /* окно уже впереди */
        }
        this.openView();
      };
      return true;
    } catch (e) {
      console.warn("Второй мозг: уведомление не показано", e);
      return false;
    }
  }

  /** Долгий запуск закончился — уведомить (окно Obsidian могло быть свёрнуто). */
  private doneNotify(label: string, r: RunResult, sec: number) {
    if (r.cancelled) return; // отменили сами, в окне вопроса, — сообщать не о чем
    if (sec < Math.max(0, this.data.notifyMinutes) * 60) return;
    let body: string;
    if (r.webchat) body = "Ждёт ответа из веб-чата — инструкция в панели.";
    else if (r.budget_stop) body = "Остановлено: исчерпан бюджет.";
    else if (r.stopped) body = "Остановлено. Всё обработанное сохранено.";
    else if (!r.ok) body = `Ошибка: ${r.error || "см. панель"}`;
    else {
      const sl = statsLine(r.stats);
      body = `${r.title || "Готово"} за ${durationText(sec)}` + (sl ? `: ${sl}` : "") + (r.run_usage?.cost ? ` · ${money(r.run_usage.cost)}` : "") + ".";
      if (r.questions) body += ` Вопросов: ${r.questions}.`;
    }
    this.osNotify(`Второй мозг · ${label}`, body, "done");
  }

  // ---------- состояние ----------
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
      console.warn("Второй мозг: не удалось прочитать .system/ui.json", e);
    }
  }

  /** Попросить программу пересчитать снимок состояния (без обращений к модели). */
  async refreshState(force = false) {
    const r = await this.engine.snapshot();
    this.snapshotError = r.ok ? null : r.error || "программа не ответила";
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
      el.setText("Второй мозг: нет программы");
      el.setAttr("title", prob);
    } else if (job) {
      const manual = manualMode(this.ui); // веб-чат: без времени и «осталось»
      const t = job.startedAt && !manual ? duration(Date.now() - job.startedAt) : "";
      const q = this.engine.pending().length;
      const info = liveInfo(job);
      const parts = [`Второй мозг · ${job.label}`];
      const s0 = job.live.stages[0];
      if (s0) parts.push(s0.unit === "%" ? `${s0.n}%` : s0.total > 0 ? `${s0.n} из ${s0.total}` : s0.stage);
      if (job.live.ask) parts.push("ждёт вашего ответа");
      else if (info.wait !== null && info.wait >= 3000) parts.push(`ждём ответа ${duration(info.wait)}`);
      else if (info.eta && !manual) parts.push(info.eta);
      if (t) parts.push(t);
      el.setText(parts.join(" · ") + (q ? ` (+${q})` : ""));
      el.setAttr("title", [info.stage, info.sub, job.lastLine].filter(Boolean).join("\n") || job.label);
    } else {
      const n = this.ui?.status.questions || 0;
      el.setText(n ? `Второй мозг · ${nQuestions(n)}` : "Второй мозг");
      el.setAttr("title", "Открыть панель «Второй мозг»");
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

  /** Открыть настройки плагина (tab — вкладка: main, models, thresholds, input, docs, costs, advanced). */
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

  // ---------- запуски ----------
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
    if (r.webchat) new Notice(`${label}: ждёт ответа из веб-чата — инструкция в панели «Второй мозг».`, 10000);
    else if (r.cancelled) new Notice(`${label}: отменено — ничего не изменено.`, 6000);
    else if (r.budget_stop) {
      const why = (r.notices || []).find((n) => n.startsWith("Остановлено")) || "Остановлено: исчерпан бюджет. Всё обработанное сохранено.";
      new Notice(`${label}: ${lcFirst(why)}`, 20000);
    } else if (r.ok) {
      const sl = statsLine(r.stats);
      let msg = `${label}: ${lcFirst(r.title || "готово")}${sl ? " — " + sl : ""}.`;
      const u = r.run_usage;
      if (u && u.calls) msg += ` Обращений: ${u.calls}${u.cost ? `, ${money(u.cost)}` : ""}${r.elapsed ? `, ${durationText(r.elapsed)}` : ""}.`;
      if (r.questions) msg += ` Открытых вопросов: ${r.questions}.`;
      if (r.warnings?.length) msg += ` Предупреждений: ${r.warnings.length} — см. панель.`;
      new Notice(msg, 8000);
    } else if (r.stopped) new Notice(`${label}: остановлено. Всё обработанное сохранено — следующий запуск продолжит.`, 8000);
    else new Notice(`${label}: ${r.error || "ошибка"}`, 15000);
  }

  runPhase1() {
    return this.job(["run"], "Фаза 1");
  }

  async runSynth(c: UiContainer, force = false): Promise<RunResult> {
    const label = `Фаза 2 · ${c.title}`;
    const r = await this.job(["synth", c.id, ...(force ? ["--force"] : [])], label, false);
    if (r.ok && r.unchanged && !force) {
      const ok = await this.confirm({
        title: "Документы актуальны",
        text: `С прошлой записи документов «${c.title}» в базе синтеза ничего не изменилось.\n\nПереписать их всё равно? Это потратит обращения к модели.`,
        ok: "Переписать",
      });
      return ok ? this.runSynth(c, true) : r;
    }
    this.notify(label, r);
    return r;
  }

  /** Ревалидация: программа сама посчитает записи и спросит подтверждение (с оценкой времени и стоимости). */
  async runRevalidate(c: UiContainer | null) {
    const r = await this.job(["revalidate", ...(c ? [c.id] : [])], c ? `Ревалидация · ${c.title}` : "Ревалидация всех записей", false);
    if (r.ok && !r.cancelled && !r.count) new Notice(c ? `В «${c.title}» нет обработанных записей для перепроверки.` : "Нет обработанных записей для перепроверки.");
    else this.notify(c ? `Ревалидация · ${c.title}` : "Ревалидация", r);
  }

  /** Правка настроек программы из панели (цены, бюджет): программа проверит и перепишет settings.yaml. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async patchSettings(patch: Record<string, any>): Promise<RunResult> {
    const r = await this.engine.run(["settings", "--set-json", "-"], { label: "Сохранение настроек", stdin: JSON.stringify(patch), exclusive: false, quiet: true });
    if (r.ok) await this.refreshState(true);
    return r;
  }

  /** Пересчитать стоимость прошлых обращений профиля по текущим ценам (журнал расходов меняется — в общей очереди). */
  async reprice(key: string): Promise<RunResult> {
    const r = await this.engine.run(["usage", "--reprice", key], { label: "Пересчёт стоимости" });
    await this.refreshState(true);
    return r;
  }

  async runPatterns() {
    const ok = await this.confirm({
      title: "Поиск паттернов",
      text: "Программа поищет в каждом контейнере группы близких аспектов разных типов, которые не покрывает ни один составной тип, и предложит новые типы. Одно обращение к модели на все найденные группы; если групп нет — без обращений.",
      ok: "Искать",
    });
    if (ok) await this.job(["patterns"], "Паттерны");
  }

  runCheck() {
    new CheckModal(this).open();
  }

  // ---------- своя модель эмбеддингов (llama.cpp) ----------
  /** Скачана ли модель, какие сборки llama.cpp есть, работает ли сервер; hw — ещё и оборудование компьютера. */
  async llamaStatus(hw = false): Promise<LlamaStatus | null> {
    if (this.engine.problem()) return null;
    const r = await this.engine.run(["llama", "status", ...(hw ? ["--hw"] : [])], { label: "Модель эмбеддингов", exclusive: false, quiet: true });
    return r.ok && r.llama ? r.llama : null;
  }

  /** Запустить модель с параметрами из окна «Запустить модель…»: что нужно — скачается (ход — в панели, «Стоп» —
   *  прервать: скачанное продолжится в следующий раз), адрес сервера программа впишет в настройки сама. */
  async runLlamaStart(params: LlamaParams): Promise<RunResult> {
    const label = "Запуск модели эмбеддингов";
    const t0 = Date.now();
    const r = await this.engine.run(["llama", "start", "--params-json", "-"], { label, stdin: JSON.stringify(params) });
    this.doneNotify(label, r, (Date.now() - t0) / 1000);
    const s = r.server;
    if (r.ok && s) {
      if (s.already) new Notice(`Модель уже работает с этими параметрами: ${s.url}`, 8000);
      else if (s.foreign) new Notice(`На порту ${s.port} уже работает сервер с этой моделью — программа будет пользоваться им.`, 10000);
      else new Notice(`Модель запущена: ${s.url}${s.load_sec ? ` (загрузилась за ${durationText(s.load_sec)})` : ""}. Адрес вписан в настройки.`, 10000);
    } else if (r.stopped) new Notice("Запуск модели остановлен. Начатое скачивание продолжится со следующего запуска.", 10000);
    else new Notice(`Модель не запущена: ${r.error || "ошибка"}`, 20000);
    await this.refreshState(true);
    this.brainTab.reload();
    return r;
  }

  /** Остановить сервер модели (освободить память). Программа запустит его снова сама, когда он понадобится. */
  async runLlamaStop(): Promise<RunResult> {
    const r = await this.engine.run(["llama", "stop"], { label: "Остановка модели эмбеддингов", exclusive: false, quiet: true });
    if (!r.ok) new Notice(`Модель не остановлена: ${r.error || "ошибка"}`, 12000);
    else new Notice(r.title === "Сервер остановлен" ? "Модель эмбеддингов остановлена — память освобождена." : "Модель эмбеддингов и так не запущена.", 8000);
    return r;
  }

  continueWebchat() {
    const w = this.lastWebchat;
    return w ? this.job(w.args, w.label) : this.runPhase1();
  }

  answer(q: UiQuestion, option: number | null, text: string | null): Promise<RunResult> {
    const args = ["answer", q.id, option !== null ? `--option=${option}` : `--text=${text || ""}`];
    return this.job(args, `Ответ на ${q.id}`, false);
  }

  async approveStructure() {
    const draft = this.ui?.status.draft || "_структура (черновик).md";
    const ok = await this.confirm({
      title: "Утвердить структуру?",
      text: "Программа создаст контейнеры по черновику (с вашими правками) и разложит по ним записи. Это обращения к модели — по записи на каждую.",
      ok: "Утвердить и продолжить",
    });
    if (!ok) return;
    for (const leaf of this.app.workspace.getLeavesOfType("markdown")) {
      const v = leaf.view; // правки в открытом черновике — сначала на диск, иначе программа их не увидит
      if (v instanceof MarkdownView && v.file?.path === draft) await v.save();
    }
    const r = await this.engine.local("Утверждение структуры", async () => {
      const f = this.app.vault.getAbstractFileByPath(draft);
      if (!(f instanceof TFile)) throw new Error(`нет файла черновика «${draft}»`);
      await this.app.vault.process(f, (text) => markApproved(text));
    });
    if (!r.ok) {
      new Notice(`Не удалось отметить черновик: ${r.error}`, 10000);
      return;
    }
    new Notice("Структура утверждена — создаю контейнеры и раскладываю записи…");
    await this.runPhase1();
  }

  // ---------- совет ИИ ----------
  openAdvice(c: UiContainer, ready?: Advice) {
    new AdviceModal(this, c, ready).open();
  }

  async adviseNow(c: UiContainer): Promise<RunResult> {
    const label = `Совет по порогам · ${c.title}`;
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

  // ---------- правки YAML контейнера (в общей очереди, не во время прогона) ----------
  private async editFrontmatter(c: UiContainer, label: string, fn: (fm: Record<string, unknown>) => void): Promise<boolean> {
    if (this.engine.busy()) new Notice("Программа работает — изменение запишется сразу после текущего запуска.");
    const r = await this.engine.local(label, async () => {
      const f = this.app.vault.getAbstractFileByPath(c.path);
      if (!(f instanceof TFile)) throw new Error(`не найден файл контейнера «${c.path}»`);
      await this.app.fileManager.processFrontMatter(f, fn);
    });
    if (!r.ok) {
      new Notice(`Не удалось сохранить: ${r.error}`, 10000);
      return false;
    }
    this.refreshState(true);
    return true;
  }

  saveThresholds(c: UiContainer, changes: Record<string, number | null>): Promise<boolean> {
    const aliases = this.ui?.threshold_aliases || {};
    return this.editFrontmatter(c, `Пороги · ${c.title}`, (fm) => {
      const old = fm.thresholds;
      const t: Record<string, unknown> = old && typeof old === "object" && !Array.isArray(old) ? { ...(old as Record<string, unknown>) } : {};
      for (const [name, v] of Object.entries(changes)) {
        for (const k of Object.keys(t)) {
          const norm = k.trim().toLowerCase().replace(/ /g, "_");
          if (k !== name && (norm === name || aliases[norm] === name)) delete t[k]; // тот же порог под русским именем
        }
        if (v === null) delete t[name];
        else t[name] = v;
      }
      if (Object.keys(t).length) fm.thresholds = t;
      else delete fm.thresholds;
    });
  }

  saveStyle(c: UiContainer, text: string): Promise<boolean> {
    return this.editFrontmatter(c, `Стиль · ${c.title}`, (fm) => {
      if (text) fm.style = text;
      else delete fm.style;
    });
  }

  async setContainerField(c: UiContainer, key: string, value: string, what: string) {
    const ok = await this.editFrontmatter(c, `${c.title}: ${what}`, (fm) => {
      fm[key] = value;
    });
    if (ok) new Notice(`«${c.title}» — ${what}. Программа учтёт это при следующей Фазе 1.`);
  }

  // ---------- новая мысль ----------
  newThought(hint = "") {
    new NewThoughtModal(this, hint).open();
  }

  async saveThought(text: string, hint: string, dateIso: string, source: string): Promise<string> {
    const { name, body } = thoughtFile(text, hint, dateIso);
    const folder = source && source !== "заметка" ? `_staging/${source}` : "_staging";
    const a = this.app.vault.adapter;
    if (!(await a.exists(folder))) await a.mkdir(folder);
    let p = `${folder}/${name}`;
    for (let i = 2; await a.exists(p); i++) p = `${folder}/${name.replace(/\.txt$/, ` (${i}).txt`)}`;
    await a.write(p, body);
    this.refreshState();
    return p;
  }

  // ---------- файлы и папки ----------
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
      new Notice(`Файл не найден: ${rel}`);
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
      new Notice(`Откройте вручную: ${abs}`, 10000);
    }
  }

  pickContainer(cb: (c: UiContainer | null) => void, allLabel?: string) {
    if (!this.ui?.containers.length) {
      new Notice("Контейнеров пока нет — сначала утвердите структуру.");
      return;
    }
    new ContainerPicker(this, allLabel || null, cb).open();
  }

  containerOfActive(): UiContainer | null {
    const f = this.app.workspace.getActiveFile();
    return f ? containerOfPath(this.ui, f.path) : null;
  }

  // ---------- команды ----------
  private addCommands() {
    this.addCommand({ id: "open-panel", name: "Открыть панель", callback: () => this.openView() });
    this.addCommand({ id: "run", name: "Фаза 1: обработать новое", callback: () => this.runPhase1() });
    this.addCommand({ id: "new-thought", name: "Новая мысль", callback: () => this.newThought() });
    this.addCommand({ id: "questions", name: "Ответить на вопросы", callback: () => this.openView("questions") });
    this.addCommand({ id: "synth", name: "Фаза 2: написать документы…", callback: () => this.pickContainer((c) => c && this.runSynth(c)) });
    this.addCommand({
      id: "synth-current",
      name: "Фаза 2 для контейнера открытой заметки",
      checkCallback: (checking) => {
        const c = this.containerOfActive();
        if (!c) return false;
        if (!checking) this.runSynth(c);
        return true;
      },
    });
    this.addCommand({
      id: "container-current",
      name: "Показать контейнер открытой заметки",
      checkCallback: (checking) => {
        const c = this.containerOfActive();
        if (!c) return false;
        if (!checking) this.openView("container", c.id);
        return true;
      },
    });
    this.addCommand({ id: "advise", name: "Совет ИИ по порогам контейнера…", callback: () => this.pickContainer((c) => c && this.openAdvice(c)) });
    this.addCommand({ id: "revalidate", name: "Ревалидация…", callback: () => this.pickContainer((c) => this.runRevalidate(c), "Все контейнеры") });
    this.addCommand({ id: "patterns", name: "Паттерны: поиск новых составных типов", callback: () => this.runPatterns() });
    this.addCommand({ id: "check", name: "Проверить связь с моделью", callback: () => this.runCheck() });
    this.addCommand({ id: "usage", name: "Расходы на модели", callback: () => this.openView("usage") });
    this.addCommand({ id: "update", name: "Проверить обновления программы", callback: () => this.checkUpdates(true) });
    this.addCommand({ id: "refresh", name: "Обновить состояние", callback: () => this.refreshState(true) });
    this.addCommand({ id: "report", name: "Отчёт для разработчика", callback: () => saveDeveloperReport(this) });
    this.addCommand({
      id: "stop",
      name: "Стоп",
      checkCallback: (checking) => {
        if (!this.engine.busy()) return false;
        if (!checking) this.engine.stop();
        return true;
      },
    });
  }
}

/** «Готово» → «готово» после двоеточия; аббревиатуры («API …») не трогаем. */
function lcFirst(s: string): string {
  return s.length > 1 && s[1] === s[1].toLowerCase() ? s[0].toLowerCase() + s.slice(1) : s;
}

/** Отметить в черновике «- [x] Структура утверждена» (строку добавить, если её стёрли). */
export function markApproved(text: string): string {
  const re = new RegExp(`^(\\s*[-*]\\s*)\\[ \\](\\s*${APPROVE})`, "m");
  if (re.test(text)) return text.replace(re, "$1[x]$2");
  if (new RegExp(`^\\s*[-*]\\s*\\[[xXхХ✓vV]\\]\\s*${APPROVE}`, "m").test(text)) return text;
  const fm = /^---\r?\n[\s\S]*?\r?\n---\r?\n/.exec(text);
  const at = fm ? fm[0].length : 0;
  return text.slice(0, at) + `- [x] ${APPROVE}\n\n` + text.slice(at);
}
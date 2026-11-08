// Запуск программы «Второй мозг» (Python) отдельным процессом: очередь, вывод, итог @@RESULT, «Стоп».
import { FileSystemAdapter, Platform } from "obsidian";
import { spawn, ChildProcess } from "child_process";
import * as fs from "fs";
import * as path from "path";
import type BrainPlugin from "./main";
import type { AskEvent, ProgressEvent, RunResult, RunUsage, UsageEvent } from "./types";
import { etaText } from "./util";

export type JobStatus = "queued" | "running" | "done" | "failed" | "stopped" | "cancelled";

/** Этап запуска (строка @@PROGRESS): с какого номера и когда мы его увидели — для «осталось ≈». */
export interface LiveStage extends ProgressEvent {
  since: number; // когда увидели этап впервые
  firstN: number; // какой номер был тогда
  at: number; // когда пришёл текущий номер
}

/** Что происходит в запуске прямо сейчас — из живых строк программы. */
export interface Live {
  stages: LiveStage[]; // по уровням: 0 — общий этап, 1 — вложенный (записи одного файла)
  wait: { prompt: string; profile: string; model: string; since: number } | null;
  usage: RunUsage | null;
  last: UsageEvent | null;
  notices: string[];
  ask: AskEvent | null;
}

export interface Job {
  id: number;
  label: string;
  args: string[];
  stdin?: string;
  interactive: boolean; // вопросы посреди запуска (@@ASK) — ответ в стандартный ввод
  live: Live;
  askCancel?: () => void; // закрыть окно вопроса (процесс завершился или нажали «Стоп»)
  fn?: () => Promise<void>; // действие внутри Obsidian (правка YAML), выполняется в общей очереди
  exclusive: boolean; // меняет хранилище — строго по одному
  quiet: boolean; // служебный запуск: не показывать в панели как «работает»
  status: JobStatus;
  queuedAt: number;
  startedAt?: number;
  finishedAt?: number;
  lines: string[];
  lastLine: string;
  stderr: string;
  result?: RunResult;
  stopAt?: number;
  killed?: boolean;
  child?: ChildProcess;
  waiters: ((r: RunResult) => void)[];
}

export interface RunOptions {
  label: string;
  stdin?: string;
  exclusive?: boolean;
  quiet?: boolean;
  /** программа может спросить посреди запуска (бюджет, большой запуск): --ask-stdin, ввод остаётся открытым */
  interactive?: boolean;
}

const TAGS = new Set(["RESULT", "PROGRESS", "WAIT", "USAGE", "NOTICE", "ASK"]);

/** «Осталось ≈» по этапу: среднее время на пункт с тех пор, как этап виден, × сколько пунктов осталось. */
export function stageEta(st: LiveStage | undefined, now = Date.now()): number | null {
  if (!st || st.total < 3) return null;
  const done = st.n - st.firstN;
  if (done < 2 || st.at <= st.since) return null;
  const per = (st.at - st.since) / done;
  return Math.max(0, (st.total - st.n + 1) * per - (now - st.at));
}

/** Текст «Обработка записей: 12 из 80», «осталось ≈ 5 мин», «ждём ответа модели 0:42» для панели и строки состояния. */
export function liveInfo(job: Job, now = Date.now()): { stage: string; sub: string; eta: string; frac: number | null; wait: number | null; waitWhat: string } {
  const [s0, s1] = job.live.stages;
  const count = (s: LiveStage) => (s.unit === "%" ? `${s.stage}: ${s.n}%${s.item ? ` · ${s.item}` : ""}` : `${s.stage}: ${s.n} из ${s.total}`);
  const stage = s0 ? count(s0) : "";
  const sub = s1 ? count(s1) : "";
  let eta = "";
  const e0 = stageEta(s0, now);
  if (e0 !== null) eta = `осталось ${etaText(e0)}`;
  else {
    const e1 = stageEta(s1, now);
    if (e1 !== null) eta = `по этой части осталось ${etaText(e1)}`;
  }
  const done = s0 ? (s0.unit === "%" ? s0.n : s0.n - 1) : 0; // n — номер того, что обрабатывается сейчас; проценты — уже сделанное
  const frac = s0 && s0.total ? Math.min(1, Math.max(0, done / s0.total)) : null;
  const w = job.live.wait;
  const waitWhat = w ? [w.prompt, w.profile || w.model].filter(Boolean).join(" · ") : "";
  return { stage, sub, eta, frac, wait: w ? now - w.since : null, waitWhat };
}

const MAX_LINES = 3000;

export class Engine {
  private seq = 0;
  queue: Job[] = [];
  current: Job | null = null;
  side = new Set<Job>();
  history: Job[] = [];
  onChange: () => void = () => {};
  onLine: (job: Job, line: string) => void = () => {};
  /** живая строка программы (этап, ожидание, расход) — панель обновляет блок запуска */
  onLive: (job: Job) => void = () => {};
  onNotice: (job: Job, text: string) => void = () => {};
  /** вопрос посреди запуска: номер варианта или null (окно закрыто — отказ) */
  onAsk: (job: Job, ask: AskEvent) => Promise<number | null> = () => Promise.resolve(null);

  constructor(private plugin: BrainPlugin) {}

  vaultPath(): string {
    const a = this.plugin.app.vault.adapter;
    return a instanceof FileSystemAdapter ? a.getBasePath() : "";
  }

  programDir(): string {
    return (this.plugin.data.programDir || "").trim();
  }

  defaultPython(): string {
    const dir = this.programDir() || "<папка программы>";
    return Platform.isWin ? path.join(dir, ".venv", "Scripts", "python.exe") : path.join(dir, ".venv", "bin", "python");
  }

  pythonPath(): string {
    return (this.plugin.data.pythonPath || "").trim() || this.defaultPython();
  }

  /** Что мешает запустить программу — понятным текстом, или null. */
  problem(): string | null {
    const dir = this.programDir();
    if (!dir) return "Не указана папка программы «Второй мозг». Откройте настройки плагина и впишите её — это папка, где лежит «Установка.bat».";
    if (!fs.existsSync(path.join(dir, "brain", "__main__.py")))
      return `В папке «${dir}» нет программы (папки brain). Проверьте путь в настройках плагина.`;
    const py = this.pythonPath();
    if (!fs.existsSync(py)) return `Не найден Python программы: ${py}. Запустите «Установка.bat» в папке программы.`;
    if (!this.vaultPath()) return "Плагин работает только в Obsidian для компьютера, с хранилищем на диске.";
    return null;
  }

  /** Идёт ли запуск, который пользователь должен видеть. */
  busy(): boolean {
    return (this.current !== null && !this.current.quiet) || this.queue.some((j) => !j.quiet);
  }

  active(): Job | null {
    return this.current && !this.current.quiet ? this.current : null;
  }

  pending(): Job[] {
    return this.queue.filter((j) => !j.quiet);
  }

  find(pred: (j: Job) => boolean): Job | undefined {
    if (this.current && pred(this.current)) return this.current;
    return this.queue.find(pred) || [...this.side].find(pred);
  }

  /** Запустить команду программы. Ошибки не бросаются: итог всегда приходит как RunResult. */
  run(args: string[], opts: RunOptions): Promise<RunResult> {
    const exclusive = opts.exclusive !== false;
    if (exclusive && opts.stdin === undefined) {
      const same = this.find((j) => j.exclusive && !j.fn && j.args.join("\u0000") === args.join("\u0000"));
      if (same) return new Promise((resolve) => same.waiters.push(resolve)); // такой же запуск уже в очереди
    }
    return new Promise((resolve) => {
      const job = this.make(opts.label, args, exclusive, !!opts.quiet, resolve);
      job.stdin = opts.stdin;
      job.interactive = !!opts.interactive;
      const prob = this.problem();
      if (prob) {
        this.finish(job, { ok: false, error: prob });
        return;
      }
      this.enqueue(job);
    });
  }

  /** Действие внутри Obsidian в общей очереди: например, правка YAML контейнера не во время прогона. */
  local(label: string, fn: () => Promise<void>): Promise<RunResult> {
    return new Promise((resolve) => {
      const job = this.make(label, [], true, true, resolve);
      job.fn = fn;
      this.enqueue(job);
    });
  }

  snapshot(): Promise<RunResult> {
    return this.run(["snapshot"], { label: "Обновление состояния", quiet: true });
  }

  private make(label: string, args: string[], exclusive: boolean, quiet: boolean, resolve: (r: RunResult) => void): Job {
    return {
      id: ++this.seq, label, args, exclusive, quiet, status: "queued", queuedAt: Date.now(), interactive: false,
      live: { stages: [], wait: null, usage: null, last: null, notices: [], ask: null },
      lines: [], lastLine: "", stderr: "", waiters: [resolve],
    };
  }

  private enqueue(job: Job) {
    if (job.exclusive) {
      this.queue.push(job);
      this.changed();
      this.pump();
    } else {
      this.side.add(job);
      this.start(job);
    }
  }

  private pump() {
    if (this.current || !this.queue.length) return;
    const job = this.queue.shift()!;
    this.current = job;
    this.start(job);
  }

  private start(job: Job) {
    job.status = "running";
    job.startedAt = Date.now();
    this.changed();
    if (job.fn) {
      job.fn().then(
        () => this.finish(job, { ok: true, title: "Готово" }),
        (e) => this.finish(job, { ok: false, error: String((e && e.message) || e) }),
      );
      return;
    }
    const argv = ["-X", "utf8", "-m", "brain", "--json", ...(job.interactive ? ["--ask-stdin"] : []), "--vault", this.vaultPath(), ...job.args];
    let child: ChildProcess;
    try {
      child = spawn(this.pythonPath(), argv, {
        cwd: this.programDir(),
        env: { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8", PYTHONUNBUFFERED: "1" },
        windowsHide: true,
      });
    } catch (e) {
      this.finish(job, { ok: false, error: `Не удалось запустить программу: ${e}` });
      return;
    }
    job.child = child;
    let buf = "";
    const line = (raw: string) => {
      const s = raw.replace(/\r$/, "");
      if (s.startsWith("@@")) {
        const sp = s.indexOf(" ");
        const tag = sp > 0 ? s.slice(2, sp) : s.slice(2);
        if (TAGS.has(tag)) {
          let obj: unknown;
          try {
            obj = JSON.parse(sp > 0 ? s.slice(sp + 1) : "{}");
          } catch (e) {
            job.lines.push(`(не удалось разобрать строку программы @@${tag}: ${e})`);
            return;
          }
          this.tag(job, tag, obj);
          return;
        }
      }
      job.lines.push(s);
      if (job.lines.length > MAX_LINES) job.lines.splice(0, job.lines.length - MAX_LINES);
      if (s.trim()) {
        job.lastLine = s.trim();
        this.onLine(job, s);
      }
    };
    child.stdout?.setEncoding("utf8");
    child.stdout?.on("data", (d: string) => {
      buf += d;
      let i: number;
      while ((i = buf.indexOf("\n")) >= 0) {
        line(buf.slice(0, i));
        buf = buf.slice(i + 1);
      }
    });
    child.stderr?.setEncoding("utf8");
    child.stderr?.on("data", (d: string) => {
      job.stderr = (job.stderr + d).slice(-20000);
    });
    let done = false;
    child.on("error", (err: Error) => {
      if (done) return;
      done = true;
      this.finish(job, { ok: false, error: `Не удалось запустить программу (${this.pythonPath()}): ${err.message}` });
    });
    child.on("close", (code: number | null) => {
      if (done) return;
      done = true;
      if (buf) line(buf);
      this.dropAsk(job);
      job.live.wait = null;
      let r = job.result;
      if (!r) {
        const tail = job.stderr.trim().split("\n").slice(-6).join("\n");
        r = { ok: false, code: code ?? -1, error: job.killed ? "Прервано сразу." : `Программа завершилась без итога (код ${code}).${tail ? "\n" + tail : ""}` };
      }
      if (job.killed) {
        r.stopped = true;
        r.title = "Прервано";
        r.error = r.error || "Прервано сразу.";
      }
      this.finish(job, r);
    });
    try {
      if (job.interactive) {
        if (job.stdin !== undefined) child.stdin?.write(job.stdin, "utf8");
      } else if (job.stdin !== undefined) child.stdin?.end(job.stdin, "utf8");
      else child.stdin?.end();
    } catch {
      /* процесс мог уже завершиться */
    }
  }

  /** Живые строки программы: @@PROGRESS, @@WAIT, @@USAGE, @@NOTICE, @@ASK и итог @@RESULT. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private tag(job: Job, tag: string, o: any) {
    const now = Date.now();
    const L = job.live;
    switch (tag) {
      case "RESULT":
        job.result = o as RunResult;
        return;
      case "PROGRESS": {
        const lv = Math.max(0, Math.min(3, Number(o.level) || 0));
        const prev = L.stages[lv];
        if (!prev || prev.stage !== o.stage || o.n < prev.n || o.total !== prev.total)
          L.stages[lv] = { ...(o as ProgressEvent), level: lv, since: now, firstN: Number(o.n) || 0, at: now };
        else if (o.n !== prev.n) Object.assign(prev, { n: o.n, item: o.item, at: now });
        L.stages.length = lv + 1; // новый пункт общего этапа — вложенный начнётся заново
        break;
      }
      case "WAIT":
        L.wait = o && o.prompt ? { prompt: String(o.prompt), profile: String(o.profile || ""), model: String(o.model || ""), since: now } : null;
        break;
      case "USAGE":
        L.last = o as UsageEvent;
        if (o && o.run) L.usage = o.run as RunUsage;
        L.wait = null;
        break;
      case "NOTICE": {
        const text = String((o && o.text) || "");
        if (!text) return;
        L.notices.push(text);
        job.lines.push("! " + text);
        try {
          this.onNotice(job, text);
        } catch (e) {
          console.error("Второй мозг:", e);
        }
        break;
      }
      case "ASK": {
        const ask: AskEvent = {
          id: String(o.id || ""), title: String(o.title || "Вопрос"), text: String(o.text || ""),
          lines: Array.isArray(o.lines) ? o.lines.map(String) : [], options: Array.isArray(o.options) ? o.options.map(String) : [],
        };
        L.ask = ask;
        L.wait = null;
        job.lines.push(`? ${ask.title}: ${ask.text}`);
        if (!job.interactive) {
          this.answer(job, ask, null);
          return;
        }
        let p: Promise<number | null>;
        try {
          p = this.onAsk(job, ask);
        } catch (e) {
          console.error("Второй мозг:", e);
          p = Promise.resolve(null);
        }
        p.then((ch) => this.answer(job, ask, ch), () => this.answer(job, ask, null));
        this.changed();
        break;
      }
    }
    try {
      this.onLive(job);
    } catch (e) {
      console.error("Второй мозг:", e);
    }
  }

  /** Ответ на вопрос программы — строка JSON в её стандартный ввод (пустая строка — отказ). */
  answer(job: Job, ask: AskEvent, choice: number | null) {
    if (job.live.ask !== ask) return; // уже ответили (или процесс завершился)
    job.live.ask = null;
    job.askCancel = undefined;
    const ok = choice !== null && choice >= 0 && choice < ask.options.length;
    job.lines.push(`→ ${ok ? ask.options[choice!] : "без ответа"}`);
    try {
      const st = job.child?.stdin;
      if (st && !st.destroyed) st.write(ok ? JSON.stringify({ choice }) + "\n" : "\n", "utf8");
    } catch (e) {
      console.warn("Второй мозг: не удалось ответить программе", e);
    }
    this.changed();
  }

  /** Процесс завершился или нажали «Стоп»: открытый вопрос закрывается без ответа. */
  private dropAsk(job: Job) {
    const ask = job.live.ask;
    const cancel = job.askCancel;
    job.askCancel = undefined;
    if (ask) this.answer(job, ask, null);
    if (cancel) {
      try {
        cancel();
      } catch (e) {
        console.error("Второй мозг:", e);
      }
    }
  }

  private finish(job: Job, r: RunResult) {
    job.result = r;
    job.finishedAt = Date.now();
    if (job.status !== "cancelled") job.status = job.killed || r.stopped ? "stopped" : r.ok ? "done" : "failed";
    job.child = undefined;
    if (this.current === job) this.current = null;
    this.side.delete(job);
    if (!job.quiet || !r.ok) {
      this.history.unshift(job);
      if (this.history.length > 60) this.history.pop();
    }
    for (const w of job.waiters) {
      try {
        w(r);
      } catch (e) {
        console.error("Второй мозг:", e);
      }
    }
    this.changed();
    this.pump();
  }

  /** «Стоп»: очередь отменяется, текущий запуск закончит шаг, сохранит всё и остановится. */
  stop() {
    // Правки YAML и ответы на вопросы из очереди не теряем: они быстрые и без обращений к модели.
    const keep = (j: Job) => !!j.fn || j.args[0] === "answer";
    const cancelled = this.queue.filter((j) => !keep(j));
    this.queue = this.queue.filter(keep);
    for (const j of cancelled) {
      j.status = "cancelled";
      this.finish(j, { ok: false, stopped: true, title: "Отменено", error: "Отменено кнопкой «Стоп»." });
    }
    const cur = this.current;
    if (cur && !cur.fn && cur.live.ask) this.dropAsk(cur); // программа ждёт ответа — отказ, она остановится сама
    if (cur && !cur.fn && !cur.stopAt) {
      cur.stopAt = Date.now();
      try {
        const dir = path.join(this.vaultPath(), ".system");
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(path.join(dir, "stop"), "");
      } catch (e) {
        console.error("Второй мозг: не удалось записать файл «Стоп»", e);
      }
    }
    this.changed();
  }

  /** «Прервать сразу»: процесс завершается немедленно (текущий шаг не сохранится, остальное — цело). */
  kill() {
    const cur = this.current;
    const pid = cur?.child?.pid;
    if (!cur || !cur.child || !pid) return;
    cur.killed = true;
    try {
      if (Platform.isWin) spawn("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true });
      else cur.child.kill("SIGTERM");
    } catch (e) {
      console.error("Второй мозг: не удалось прервать процесс", e);
    }
    this.changed();
  }

  /** При выключении плагина: текущий запуск аккуратно останавливается. */
  dispose() {
    if (this.current && !this.current.fn) this.stop();
  }

  private changed() {
    try {
      this.onChange();
    } catch (e) {
      console.error("Второй мозг:", e);
    }
  }
}

// Launch of the programme «Second Brain» (Python) process: turn, conclusion, final @@RESULT, «Stop.».
import { FileSystemAdapter, Platform } from "obsidian";
import { spawn, ChildProcess } from "child_process";
import * as fs from "fs";
import * as path from "path";
import type BrainPlugin from "./main";
import type { AskEvent, ProgressEvent, RunResult, RunUsage, UiSnapshot, UsageEvent } from "./types";
import { etaText } from "./util";

export type JobStatus = "queued" | "running" | "done" | "failed" | "stopped" | "cancelled";

/** Launch phase (line @@PROGRESS): What number and when did we see it? — for «left ≈». */
export interface LiveStage extends ProgressEvent {
  since: number; // When you first saw the stage
  firstN: number; // What number was it then?
  at: number; // when the current number came in
}

/** Whats happening in the launch right now — live-line. */
export interface Live {
  stages: LiveStage[]; // level-by-level: 0 — general, 1 — nested (file-recording)
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
  interactive: boolean; // Questions in the middle of the launch (@@ASK) — standard-input
  live: Live;
  askCancel?: () => void; // close the window (process is completed or pressed «Stop.»)
  fn?: () => Promise<void>; // entrapment Obsidian (editing YAML), run in line
  exclusive: boolean; // change-over — single-handedly
  quiet: boolean; // service-launch: Not show the panel as «work»
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
  /** The program can ask in the middle of the launch (budget, launch): --ask-stdin, The input remains open */
  interactive?: boolean;
}

const TAGS = new Set(["RESULT", "PROGRESS", "WAIT", "USAGE", "NOTICE", "ASK"]);

/** «Its left. ≈» stagewise: average time per point since then, stage-wise, × How many points are left?.
 * Appears., As soon as the first paragraph is ready (n — number, whats being processed now; for «%» — done). */
export function stageEta(st: LiveStage | undefined, now = Date.now()): number | null {
  if (!st || st.total < 2) return null;
  const done = st.n - st.firstN;
  if (done < 1 || st.at <= st.since) return null;
  const per = (st.at - st.since) / done;
  if (st.unit === "%") return Math.max(0, (st.total - st.n) * per - (now - st.at));
  // ahead total − n items and balances of current (if it goes longer than the average — zero)
  return Math.max(0, (st.total - st.n) * per + Math.max(0, per - (now - st.at)));
}

/** Manual mode via the web-chat: program does not wait for the model, a Leaves requests in files — time «left» dont. */
export function manualMode(ui: UiSnapshot | null): boolean {
  return ui?.usage?.current?.mode === "webchat";
}

/** Text «Records processing: 12 from 80», «left ≈ 5 mine», «Were waiting for the model to respond. 0:42» for the panel and status lines. */
export function liveInfo(job: Job, now = Date.now()): { stage: string; sub: string; eta: string; frac: number | null; wait: number | null; waitWhat: string } {
  const [s0, s1] = job.live.stages;
  const count = (s: LiveStage) =>
    s.unit === "%" ? `${s.stage}: ${s.n}%${s.item ? ` · ${s.item}` : ""}`
    : s.total > 0 ? `${s.stage}: ${s.n} from ${s.total}`
    : s.stage + (s.item ? ` · ${s.item}` : ""); // count-off (memory-loading) — strip-«spinner»
  const stage = s0 ? count(s0) : "";
  const sub = s1 ? count(s1) : "";
  let eta = "";
  const e0 = stageEta(s0, now);
  if (e0 !== null) eta = `left ${etaText(e0)}`;
  else {
    const e1 = stageEta(s1, now);
    if (e1 !== null) eta = `This part is left ${etaText(e1)}`;
  }
  const done = s0 ? (s0.unit === "%" ? s0.n : s0.n - 1) : 0; // n — number, whats being processed now; interest — done
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
  /** live-line (stage, waiting, expense) — The panel updates the launch unit */
  onLive: (job: Job) => void = () => {};
  onNotice: (job: Job, text: string) => void = () => {};
  /** mid-launch: variant number null (window closed — refusal) */
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
    const dir = this.programDir() || "<program-folder>";
    return Platform.isWin ? path.join(dir, ".venv", "Scripts", "python.exe") : path.join(dir, ".venv", "bin", "python");
  }

  pythonPath(): string {
    return (this.plugin.data.pythonPath || "").trim() || this.defaultPython();
  }

  /** What prevents you from running the program — plain-text, or null. */
  problem(): string | null {
    const dir = this.programDir();
    if (!dir) return "The Second Brain program folder is not set. Open the plugin settings and enter the folder containing Install.bat.";
    if (!fs.existsSync(path.join(dir, "brain", "__main__.py")))
      return `No program found in ${dir} (missing brain folder). Check the path in the plugin settings.`;
    const py = this.pythonPath();
    if (!fs.existsSync(py)) return `Python was not found at ${py}. Run Install.bat in the program folder.`;
    if (!this.vaultPath()) return "This plugin requires Obsidian for desktop and a local vault.";
    return null;
  }

  /** Is it launching?, which the user should see. */
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

  /** Launch the program team. Mistakes dont throw.: The end always comes as RunResult. */
  run(args: string[], opts: RunOptions): Promise<RunResult> {
    const exclusive = opts.exclusive !== false;
    if (exclusive && opts.stdin === undefined) {
      const same = this.find((j) => j.exclusive && !j.fn && j.args.join("\u0000") === args.join("\u0000"));
      if (same) return new Promise((resolve) => same.waiters.push(resolve)); // same launch already in line
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

  /** The action inside Obsidian common-line: for example, editing YAML container-less. */
  local(label: string, fn: () => Promise<void>): Promise<RunResult> {
    return new Promise((resolve) => {
      const job = this.make(label, [], true, true, resolve);
      job.fn = fn;
      this.enqueue(job);
    });
  }

  snapshot(): Promise<RunResult> {
    return this.run(["snapshot"], { label: "Update of status", quiet: true });
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
        () => this.finish(job, { ok: true, title: "Ready." }),
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
      this.finish(job, { ok: false, error: `The program failed to launch: ${e}` });
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
            job.lines.push(`(Could not parse the program line @@${tag}: ${e})`);
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
      this.finish(job, { ok: false, error: `The program failed to launch (${this.pythonPath()}): ${err.message}` });
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
        r = { ok: false, code: code ?? -1, error: job.killed ? "Interrupted immediately." : `The program ended without a result (code ${code}).${tail ? "\n" + tail : ""}` };
      }
      if (job.killed) {
        r.stopped = true;
        r.title = "Interrupted.";
        r.error = r.error || "Interrupted immediately.";
      }
      this.finish(job, r);
    });
    try {
      if (job.interactive) {
        if (job.stdin !== undefined) child.stdin?.write(job.stdin, "utf8");
      } else if (job.stdin !== undefined) child.stdin?.end(job.stdin, "utf8");
      else child.stdin?.end();
    } catch {
      /* The process could have already been completed. */
    }
  }

  /** Live lines of the programme: @@PROGRESS, @@WAIT, @@USAGE, @@NOTICE, @@ASK bottom-up @@RESULT. */
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
        L.stages.length = lv + 1; // new general point — nested
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
          console.error("Second Brain:", e);
        }
        break;
      }
      case "ASK": {
        const ask: AskEvent = {
          id: String(o.id || ""), title: String(o.title || "Question"), text: String(o.text || ""),
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
          console.error("Second Brain:", e);
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
      console.error("Second Brain:", e);
    }
  }

  /** Response to the programme question — line JSON standard-input (blank-line — refusal). */
  answer(job: Job, ask: AskEvent, choice: number | null) {
    if (job.live.ask !== ask) return; // already answered (or the process is over)
    job.live.ask = null;
    job.askCancel = undefined;
    const ok = choice !== null && choice >= 0 && choice < ask.options.length;
    job.lines.push(`→ ${ok ? ask.options[choice!] : "answerless"}`);
    try {
      const st = job.child?.stdin;
      if (st && !st.destroyed) st.write(ok ? JSON.stringify({ choice }) + "\n" : "\n", "utf8");
    } catch (e) {
      console.warn("Second Brain: Failed to respond to the program", e);
    }
    this.changed();
  }

  /** The process is over or pressed «Stop.»: Open question closed without answer. */
  private dropAsk(job: Job) {
    const ask = job.live.ask;
    const cancel = job.askCancel;
    job.askCancel = undefined;
    if (ask) this.answer(job, ask, null);
    if (cancel) {
      try {
        cancel();
      } catch (e) {
        console.error("Second Brain:", e);
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
        console.error("Second Brain:", e);
      }
    }
    this.changed();
    this.pump();
  }

  /** «Stop.»: queue off, The current launch will complete the step, Hell keep everything and stop.. */
  stop() {
    // Editing YAML We do not lose answers from the queue.: They are fast and without reference to the model..
    const keep = (j: Job) => !!j.fn || j.args[0] === "answer";
    const cancelled = this.queue.filter((j) => !keep(j));
    this.queue = this.queue.filter(keep);
    for (const j of cancelled) {
      j.status = "cancelled";
      this.finish(j, { ok: false, stopped: true, title: "Cancelled.", error: "Cancelled using the Stop button." });
    }
    const cur = this.current;
    if (cur && !cur.fn && cur.live.ask) this.dropAsk(cur); // program awaits a response — refusal, Itll stop on its own.
    if (cur && !cur.fn && !cur.stopAt) {
      cur.stopAt = Date.now();
      try {
        const dir = path.join(this.vaultPath(), ".system");
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(path.join(dir, "stop"), "");
      } catch (e) {
        console.error("Second Brain: failed to record the file «Stop.»", e);
      }
    }
    this.changed();
  }

  /** «Stop right now.»: process is completed immediately (current step will not continue, rest — whole). */
  kill() {
    const cur = this.current;
    const pid = cur?.child?.pid;
    if (!cur || !cur.child || !pid) return;
    cur.killed = true;
    try {
      if (Platform.isWin) spawn("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true });
      else cur.child.kill("SIGTERM");
    } catch (e) {
      console.error("Second Brain: failed to interrupt the process", e);
    }
    this.changed();
  }

  /** When the plugin is turned off: The current launch is carefully stopped. */
  dispose() {
    if (this.current && !this.current.fn) this.stop();
  }

  private changed() {
    try {
      this.onChange();
    } catch (e) {
      console.error("Second Brain:", e);
    }
  }
}

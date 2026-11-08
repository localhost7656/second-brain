/* Second Brain — plugin Obsidian. Sources: folder plugin-src program-archive. */
"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/main.ts
var main_exports = {};
__export(main_exports, {
  default: () => BrainPlugin,
  markApproved: () => markApproved,
  newerVersion: () => newerVersion
});
module.exports = __toCommonJS(main_exports);
var import_obsidian6 = require("obsidian");
var fs3 = __toESM(require("fs"));
var path2 = __toESM(require("path"));

// src/engine.ts
var import_obsidian = require("obsidian");
var import_child_process = require("child_process");
var fs = __toESM(require("fs"));
var path = __toESM(require("path"));

// src/util.ts
var STAT_NAMES = [
  ["files", "files received"],
  ["items_classified", "files analyzed"],
  ["placed", "entries placed"],
  ["quarantined", "for review"],
  ["unsorted", "unassigned"],
  ["containers_created", "new containers"],
  ["compacted", "entries compacted"],
  ["aspects", "aspects extracted"],
  ["composites", "composites assembled"],
  ["duplicates", "duplicates linked"],
  ["bases", "synthesis bases assembled"],
  ["products", "documents written"],
  ["answers", "responses"]
];
function statsLine(stats) {
  if (!stats) return "";
  return STAT_NAMES.filter(([k]) => stats[k]).map(([k, label]) => `${label}: ${stats[k]}`).join("; ");
}
function callsLine(calls) {
  if (!calls) return "";
  const total = Object.values(calls).reduce((a, b) => a + b, 0);
  if (!total) return "";
  return `Model requests: ${total} (` + Object.entries(calls).map(([k, v]) => `${k} \u2014 ${v}`).join(", ") + ")";
}
function plural(n, forms) {
  return Math.abs(n) === 1 ? forms[0] : forms[2];
}
var nQuestions = (n) => `${n} ${plural(n, ["question", "questions", "questions"])}`;
var nRecords = (n) => `${n} ${plural(n, ["entry", "entries", "entries"])}`;
var nCalls = (n) => `${n} ${plural(n, ["request", "requests", "requests"])}`;
function duration(ms) {
  const s = Math.max(0, Math.round(ms / 1e3));
  const h = Math.floor(s / 3600);
  const m = Math.floor(s % 3600 / 60);
  const sec = s % 60;
  if (h) return `${h} h ${String(m).padStart(2, "0")} min`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}
var pad = (n) => String(n).padStart(2, "0");
function ruDateTime(iso) {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(iso);
  if (!m) return iso;
  return `${m[3]}.${m[2]}.${m[1]}` + (m[4] ? ` ${m[4]}:${m[5]}` : "");
}
function clock(t) {
  const d = new Date(t);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function todayIso() {
  const d = /* @__PURE__ */ new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function nowHm() {
  const d = /* @__PURE__ */ new Date();
  return `${pad(d.getHours())}-${pad(d.getMinutes())}`;
}
function parseNumber(s, kind, min, max) {
  const raw = s.trim().replace(",", ".");
  const pct = raw.endsWith("%");
  const t = raw.replace(/%$/, "").trim();
  if (!t) return void 0;
  let v = Number(t);
  if (!Number.isFinite(v)) return null;
  if (pct && kind !== "int" && max !== void 0 && max <= 1) v = v / 100;
  if (kind === "int" && !Number.isInteger(v)) return null;
  if (min !== void 0 && v < min) return null;
  if (max !== void 0 && v > max) return null;
  return v;
}
function rangeText(kind, min, max) {
  const what = kind === "int" ? "integer" : "number";
  if (min !== void 0 && max !== void 0) return `${what} from ${min} to ${max}`;
  return what;
}
function parentsOf(ui, c) {
  const out = [];
  const seen = /* @__PURE__ */ new Set();
  let cur = c.parent_id ? ui.containers.find((x) => x.id === c.parent_id) : void 0;
  while (cur && !seen.has(cur.id)) {
    seen.add(cur.id);
    out.unshift(cur);
    cur = cur.parent_id ? ui.containers.find((x) => x.id === cur.parent_id) : void 0;
  }
  return out;
}
function containerLabel(ui, c) {
  return [...parentsOf(ui, c).map((x) => x.title), c.title].join(" \u203A ");
}
function containerOfPath(ui, path3) {
  if (!ui) return null;
  let best = null;
  for (const c of ui.containers) {
    if (path3 === c.path || c.folder && path3.startsWith(c.folder + "/")) {
      if (!best || c.folder.length > best.folder.length) best = c;
    }
  }
  return best;
}
function baseName(p) {
  const s = p.split("/").pop() || p;
  return s.replace(/\.md$/i, "");
}
function fileSlug(text, max = 40) {
  const words = text.replace(/[\\/:*?"<>|#^[\]\r\n\t]+/g, " ").trim().split(/\s+/);
  let out = "";
  for (const w of words) {
    if ((out + " " + w).trim().length > max) break;
    out = (out + " " + w).trim();
  }
  return (out || words[0]?.slice(0, max) || "thought").replace(/[. ]+$/, "");
}
function localIso(d = /* @__PURE__ */ new Date()) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
function money(v) {
  if (v == null || !Number.isFinite(v)) return "\u2014";
  if (v && Math.abs(v) < 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}
function pctText(p) {
  return p > 999 ? "more 999%" : `${Math.round(p)}%`;
}
function num(x) {
  return String(Math.round(x || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, "\xA0");
}
function compact(x) {
  const n = Math.round(x || 0);
  if (Math.abs(n) < 1e4) return num(n);
  if (Math.abs(n) < 1e6) return `${(n / 1e3).toFixed(1).replace(/\.0$/, "")}\xA0thousand`;
  return `${(n / 1e6).toFixed(2).replace(/\.?0+$/, "")}\xA0million`;
}
function durationText(sec) {
  const s = Math.max(0, Math.round(sec || 0));
  if (s < 60) return `${s} s`;
  const h = Math.floor(s / 3600);
  const m = Math.floor(s % 3600 / 60);
  if (h) return `${h} h ${String(m).padStart(2, "0")} min`;
  return `${m} min ${String(s % 60).padStart(2, "0")} s`;
}
function etaText(ms) {
  const m = ms / 6e4;
  if (m < 1) return "less than a minute";
  if (m < 90) return `\u2248 ${Math.round(m)} min`;
  return `\u2248 ${(m / 60).toFixed(1)} h`;
}
var PTYPE_RU = {
  cloud: "cloud",
  local: "local",
  webchat: "web chat",
  fake: "test"
};
function usageLine(t, o = {}) {
  if (!t || !t.calls) return "No requests.";
  const parts = [nCalls(t.calls)];
  if (t.in || t.out) parts.push(`tokens ${compact(t.in)} \u2192 ${compact(t.out)}` + (t.cached ? ` (cached ${compact(t.cached)})` : ""));
  if (o.cost !== false && (t.cost || o.cost && !t.unpriced)) parts.push(money(t.cost) + (t.unpriced ? "*" : ""));
  if (o.time && t.sec) parts.push(`model time ${durationText(t.sec)}`);
  return parts.join(" \xB7 ");
}
function sizeText(bytes) {
  const b = Math.max(0, bytes || 0);
  if (b >= 1e9) return `${(b / 1e9).toFixed(1)} GB`;
  return `${Math.max(1, Math.round(b / 1e6))} MB`;
}

// src/engine.ts
var TAGS = /* @__PURE__ */ new Set(["RESULT", "PROGRESS", "WAIT", "USAGE", "NOTICE", "ASK"]);
function stageEta(st, now = Date.now()) {
  if (!st || st.total < 2) return null;
  const done = st.n - st.firstN;
  if (done < 1 || st.at <= st.since) return null;
  const per = (st.at - st.since) / done;
  if (st.unit === "%") return Math.max(0, (st.total - st.n) * per - (now - st.at));
  return Math.max(0, (st.total - st.n) * per + Math.max(0, per - (now - st.at)));
}
function manualMode(ui) {
  return ui?.usage?.current?.mode === "webchat";
}
function liveInfo(job, now = Date.now()) {
  const [s0, s1] = job.live.stages;
  const count = (s) => s.unit === "%" ? `${s.stage}: ${s.n}%${s.item ? ` \xB7 ${s.item}` : ""}` : s.total > 0 ? `${s.stage}: ${s.n} from ${s.total}` : s.stage + (s.item ? ` \xB7 ${s.item}` : "");
  const stage = s0 ? count(s0) : "";
  const sub = s1 ? count(s1) : "";
  let eta = "";
  const e0 = stageEta(s0, now);
  if (e0 !== null) eta = `left ${etaText(e0)}`;
  else {
    const e1 = stageEta(s1, now);
    if (e1 !== null) eta = `This part is left ${etaText(e1)}`;
  }
  const done = s0 ? s0.unit === "%" ? s0.n : s0.n - 1 : 0;
  const frac = s0 && s0.total ? Math.min(1, Math.max(0, done / s0.total)) : null;
  const w = job.live.wait;
  const waitWhat = w ? [w.prompt, w.profile || w.model].filter(Boolean).join(" \xB7 ") : "";
  return { stage, sub, eta, frac, wait: w ? now - w.since : null, waitWhat };
}
var MAX_LINES = 3e3;
var Engine = class {
  constructor(plugin) {
    this.plugin = plugin;
    this.seq = 0;
    this.queue = [];
    this.current = null;
    this.side = /* @__PURE__ */ new Set();
    this.history = [];
    this.onChange = () => {
    };
    this.onLine = () => {
    };
    /** live-line (stage, waiting, expense) — The panel updates the launch unit */
    this.onLive = () => {
    };
    this.onNotice = () => {
    };
    /** mid-launch: variant number null (window closed — refusal) */
    this.onAsk = () => Promise.resolve(null);
  }
  vaultPath() {
    const a = this.plugin.app.vault.adapter;
    return a instanceof import_obsidian.FileSystemAdapter ? a.getBasePath() : "";
  }
  programDir() {
    return (this.plugin.data.programDir || "").trim();
  }
  defaultPython() {
    const dir = this.programDir() || "<program-folder>";
    return import_obsidian.Platform.isWin ? path.join(dir, ".venv", "Scripts", "python.exe") : path.join(dir, ".venv", "bin", "python");
  }
  pythonPath() {
    return (this.plugin.data.pythonPath || "").trim() || this.defaultPython();
  }
  /** What prevents you from running the program — plain-text, or null. */
  problem() {
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
  busy() {
    return this.current !== null && !this.current.quiet || this.queue.some((j) => !j.quiet);
  }
  active() {
    return this.current && !this.current.quiet ? this.current : null;
  }
  pending() {
    return this.queue.filter((j) => !j.quiet);
  }
  find(pred) {
    if (this.current && pred(this.current)) return this.current;
    return this.queue.find(pred) || [...this.side].find(pred);
  }
  /** Launch the program team. Mistakes dont throw.: The end always comes as RunResult. */
  run(args, opts) {
    const exclusive = opts.exclusive !== false;
    if (exclusive && opts.stdin === void 0) {
      const same2 = this.find((j) => j.exclusive && !j.fn && j.args.join("\0") === args.join("\0"));
      if (same2) return new Promise((resolve) => same2.waiters.push(resolve));
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
  local(label, fn) {
    return new Promise((resolve) => {
      const job = this.make(label, [], true, true, resolve);
      job.fn = fn;
      this.enqueue(job);
    });
  }
  snapshot() {
    return this.run(["snapshot"], { label: "Update of status", quiet: true });
  }
  make(label, args, exclusive, quiet, resolve) {
    return {
      id: ++this.seq,
      label,
      args,
      exclusive,
      quiet,
      status: "queued",
      queuedAt: Date.now(),
      interactive: false,
      live: { stages: [], wait: null, usage: null, last: null, notices: [], ask: null },
      lines: [],
      lastLine: "",
      stderr: "",
      waiters: [resolve]
    };
  }
  enqueue(job) {
    if (job.exclusive) {
      this.queue.push(job);
      this.changed();
      this.pump();
    } else {
      this.side.add(job);
      this.start(job);
    }
  }
  pump() {
    if (this.current || !this.queue.length) return;
    const job = this.queue.shift();
    this.current = job;
    this.start(job);
  }
  start(job) {
    job.status = "running";
    job.startedAt = Date.now();
    this.changed();
    if (job.fn) {
      job.fn().then(
        () => this.finish(job, { ok: true, title: "Ready." }),
        (e) => this.finish(job, { ok: false, error: String(e && e.message || e) })
      );
      return;
    }
    const argv = ["-X", "utf8", "-m", "brain", "--json", ...job.interactive ? ["--ask-stdin"] : [], "--vault", this.vaultPath(), ...job.args];
    let child;
    try {
      child = (0, import_child_process.spawn)(this.pythonPath(), argv, {
        cwd: this.programDir(),
        env: { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8", PYTHONUNBUFFERED: "1" },
        windowsHide: true
      });
    } catch (e) {
      this.finish(job, { ok: false, error: `The program failed to launch: ${e}` });
      return;
    }
    job.child = child;
    let buf = "";
    const line = (raw) => {
      const s = raw.replace(/\r$/, "");
      if (s.startsWith("@@")) {
        const sp = s.indexOf(" ");
        const tag = sp > 0 ? s.slice(2, sp) : s.slice(2);
        if (TAGS.has(tag)) {
          let obj;
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
    child.stdout?.on("data", (d) => {
      buf += d;
      let i;
      while ((i = buf.indexOf("\n")) >= 0) {
        line(buf.slice(0, i));
        buf = buf.slice(i + 1);
      }
    });
    child.stderr?.setEncoding("utf8");
    child.stderr?.on("data", (d) => {
      job.stderr = (job.stderr + d).slice(-2e4);
    });
    let done = false;
    child.on("error", (err) => {
      if (done) return;
      done = true;
      this.finish(job, { ok: false, error: `The program failed to launch (${this.pythonPath()}): ${err.message}` });
    });
    child.on("close", (code) => {
      if (done) return;
      done = true;
      if (buf) line(buf);
      this.dropAsk(job);
      job.live.wait = null;
      let r = job.result;
      if (!r) {
        const tail2 = job.stderr.trim().split("\n").slice(-6).join("\n");
        r = { ok: false, code: code ?? -1, error: job.killed ? "Interrupted immediately." : `The program ended without a result (code ${code}).${tail2 ? "\n" + tail2 : ""}` };
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
        if (job.stdin !== void 0) child.stdin?.write(job.stdin, "utf8");
      } else if (job.stdin !== void 0) child.stdin?.end(job.stdin, "utf8");
      else child.stdin?.end();
    } catch {
    }
  }
  /** Live lines of the programme: @@PROGRESS, @@WAIT, @@USAGE, @@NOTICE, @@ASK bottom-up @@RESULT. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tag(job, tag, o) {
    const now = Date.now();
    const L = job.live;
    switch (tag) {
      case "RESULT":
        job.result = o;
        return;
      case "PROGRESS": {
        const lv = Math.max(0, Math.min(3, Number(o.level) || 0));
        const prev = L.stages[lv];
        if (!prev || prev.stage !== o.stage || o.n < prev.n || o.total !== prev.total)
          L.stages[lv] = { ...o, level: lv, since: now, firstN: Number(o.n) || 0, at: now };
        else if (o.n !== prev.n) Object.assign(prev, { n: o.n, item: o.item, at: now });
        L.stages.length = lv + 1;
        break;
      }
      case "WAIT":
        L.wait = o && o.prompt ? { prompt: String(o.prompt), profile: String(o.profile || ""), model: String(o.model || ""), since: now } : null;
        break;
      case "USAGE":
        L.last = o;
        if (o && o.run) L.usage = o.run;
        L.wait = null;
        break;
      case "NOTICE": {
        const text = String(o && o.text || "");
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
        const ask = {
          id: String(o.id || ""),
          title: String(o.title || "Question"),
          text: String(o.text || ""),
          lines: Array.isArray(o.lines) ? o.lines.map(String) : [],
          options: Array.isArray(o.options) ? o.options.map(String) : []
        };
        L.ask = ask;
        L.wait = null;
        job.lines.push(`? ${ask.title}: ${ask.text}`);
        if (!job.interactive) {
          this.answer(job, ask, null);
          return;
        }
        let p;
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
  answer(job, ask, choice) {
    if (job.live.ask !== ask) return;
    job.live.ask = null;
    job.askCancel = void 0;
    const ok = choice !== null && choice >= 0 && choice < ask.options.length;
    job.lines.push(`\u2192 ${ok ? ask.options[choice] : "answerless"}`);
    try {
      const st = job.child?.stdin;
      if (st && !st.destroyed) st.write(ok ? JSON.stringify({ choice }) + "\n" : "\n", "utf8");
    } catch (e) {
      console.warn("Second Brain: Failed to respond to the program", e);
    }
    this.changed();
  }
  /** The process is over or pressed «Stop.»: Open question closed without answer. */
  dropAsk(job) {
    const ask = job.live.ask;
    const cancel = job.askCancel;
    job.askCancel = void 0;
    if (ask) this.answer(job, ask, null);
    if (cancel) {
      try {
        cancel();
      } catch (e) {
        console.error("Second Brain:", e);
      }
    }
  }
  finish(job, r) {
    job.result = r;
    job.finishedAt = Date.now();
    if (job.status !== "cancelled") job.status = job.killed || r.stopped ? "stopped" : r.ok ? "done" : "failed";
    job.child = void 0;
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
    const keep = (j) => !!j.fn || j.args[0] === "answer";
    const cancelled = this.queue.filter((j) => !keep(j));
    this.queue = this.queue.filter(keep);
    for (const j of cancelled) {
      j.status = "cancelled";
      this.finish(j, { ok: false, stopped: true, title: "Cancelled.", error: "Cancelled using the Stop button." });
    }
    const cur = this.current;
    if (cur && !cur.fn && cur.live.ask) this.dropAsk(cur);
    if (cur && !cur.fn && !cur.stopAt) {
      cur.stopAt = Date.now();
      try {
        const dir = path.join(this.vaultPath(), ".system");
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(path.join(dir, "stop"), "");
      } catch (e) {
        console.error("Second Brain: failed to record the file \xABStop.\xBB", e);
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
      if (import_obsidian.Platform.isWin) (0, import_child_process.spawn)("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true });
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
  changed() {
    try {
      this.onChange();
    } catch (e) {
      console.error("Second Brain:", e);
    }
  }
};

// src/modals.ts
var import_obsidian3 = require("obsidian");

// src/report.ts
var import_obsidian2 = require("obsidian");
var os = __toESM(require("os"));
var KEEP = 30;
var LOG_MAX = 512 * 1024;
function errParts(e) {
  const x = e;
  if (x && typeof x === "object" && ("message" in x || "stack" in x)) {
    return { message: String(x.message || x.name || "mistake"), stack: String(x.stack || "") };
  }
  return { message: String(e), stack: "" };
}
var pad2 = (n) => String(n).padStart(2, "0");
var stamp = (d = /* @__PURE__ */ new Date()) => `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}.${d.getFullYear()} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
var LOG_FILE = "_logs/plugin.log";
var ErrorLog = class {
  constructor(plugin) {
    this.plugin = plugin;
    this.items = [];
    this.chain = Promise.resolve();
  }
  /** quiet — The error has already been brought to the console itself. Obsidian (intercepted). */
  add(where, e, quiet = false) {
    const { message, stack } = errParts(e);
    const rec = { at: stamp(), where, message, stack };
    const last = this.items[0];
    if (last && last.where === where && last.message === message) return last;
    this.items.unshift(rec);
    if (this.items.length > KEEP) this.items.pop();
    if (!quiet) console.error(`Second Brain (${where}):`, e);
    const entry = `
===== ${rec.at} \xB7 ${where} \xB7 plugin ${this.plugin.manifest.version}
${message}
${stack}
`;
    this.chain = this.chain.then(() => this.write(entry)).catch(() => void 0);
    return rec;
  }
  /** Record in _logs/plugin.log storage (more 512 CBB — The old journal becomes a plugin.log.old). */
  async write(entry) {
    const a = this.plugin.app.vault.adapter;
    if (!await a.exists("_logs")) await a.mkdir("_logs");
    const st = await a.stat(LOG_FILE);
    if (st && st.size > LOG_MAX) {
      const old = LOG_FILE + ".old";
      if (await a.exists(old)) await a.remove(old);
      await a.rename(LOG_FILE, old);
    }
    if (await a.exists(LOG_FILE)) await a.append(LOG_FILE, entry);
    else await a.write(LOG_FILE, entry);
  }
};
function versionLines(plugin) {
  return [
    `Plugin: ${plugin.manifest.version}`,
    `Program: ${plugin.ui?.program || "?"}`,
    `Obsidian: ${import_obsidian2.apiVersion}`,
    `System: ${import_obsidian2.Platform.isWin ? "Windows" : import_obsidian2.Platform.isMacOS ? "macOS" : "Linux"} ${os.release()} (${process.arch})`
  ];
}
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
  }
  try {
    const { clipboard } = require("electron");
    if (clipboard?.writeText) {
      clipboard.writeText(text);
      return true;
    }
  } catch {
  }
  return false;
}
function recText(r) {
  return `[${r.at}] ${r.where}: ${r.message}
${r.stack}`.trim();
}
function errorReport(plugin, rec) {
  return ["Second Brain \u2014 plugin error", ...versionLines(plugin), "", recText(rec)].join("\n");
}
function renderError(el, plugin, where, e) {
  const rec = plugin.errors.add(where, e);
  const box = el.createDiv({ cls: "vm-callout is-bad vm-error-box" });
  box.createDiv({ cls: "vm-callout-title", text: `Error in the plugin (${where})` });
  box.createDiv({ text: rec.message });
  box.createDiv({
    cls: "vm-small-text vm-muted",
    text: `The rest of the plugin is still working. Details are saved in ${LOG_FILE}. Copy the report and share it with the developer.`
  });
  const row = box.createDiv({ cls: "vm-buttons" });
  const b = row.createEl("button", { text: "Copy report" });
  b.addEventListener("click", async () => {
    const ok = await copyText(errorReport(plugin, rec));
    new import_obsidian2.Notice(ok ? "Report copied. Paste it into a message to the developer." : `Could not copy the report. Details are in ${LOG_FILE}.`);
  });
}
async function tail(plugin, rel, max) {
  try {
    const a = plugin.app.vault.adapter;
    if (!await a.exists(rel)) return "";
    const text = await a.read(rel);
    return text.length > max ? text.slice(text.length - max) : text;
  } catch {
    return "";
  }
}
async function developerReport(plugin) {
  const out = ["# Second Brain \u2014 developer report", "", `Created: ${stamp()}`, "", ...versionLines(plugin).map((x) => `- ${x}`)];
  const problem = plugin.engine.problem();
  out.push(`- Program folder: ${plugin.engine.programDir() || "not listed"}${problem ? ` \u2014 ${problem}` : ""}`);
  out.push("", "## Plugin errors (last)", "");
  if (plugin.errors.items.length) out.push("```", ...plugin.errors.items.slice(0, 10).map(recText), "```");
  else out.push("None.");
  const progErr = await tail(plugin, "_logs/mistake.log", 6e3);
  out.push("", "## Program errors (ending _logs/mistake.log)", "", progErr ? "```\n" + progErr.trim() + "\n```" : "None.");
  out.push("", "## Latest launches", "");
  const jobs = plugin.engine.history.slice(0, 3);
  if (!jobs.length) out.push("No runs in this Obsidian session.");
  for (const j of jobs) {
    out.push(`### ${j.label} \u2014 ${j.status}`, "", "```", ...j.lines.slice(-40), ...j.stderr ? ["--- stderr ---", j.stderr.slice(-3e3)] : [], "```", "");
  }
  return out.join("\n");
}
async function saveDeveloperReport(plugin) {
  const text = await developerReport(plugin);
  const copied = await copyText(text);
  const rel = "_logs/developer-report.md";
  const vault = plugin.app.vault;
  try {
    if (!vault.getAbstractFileByPath("_logs") && !await vault.adapter.exists("_logs")) await vault.createFolder("_logs");
    const cur = vault.getAbstractFileByPath(rel);
    let file = null;
    if (cur instanceof import_obsidian2.TFile) {
      await vault.modify(cur, text);
      file = cur;
    } else {
      try {
        file = await vault.create(rel, text);
      } catch {
        await vault.adapter.write(rel, text);
      }
    }
    if (file) await plugin.app.workspace.getLeaf(true).openFile(file);
  } catch (e) {
    plugin.errors.add("developer-report", e);
  }
  new import_obsidian2.Notice(copied ? "Report collected and copied. Paste it into a message to the developer." : `Report collected: ${rel}`, 8e3);
}

// src/modals.ts
var ConfirmModal = class extends import_obsidian3.Modal {
  constructor(app, o, done) {
    super(app);
    this.o = o;
    this.done = done;
    this.answered = false;
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
  answer(v) {
    this.answered = true;
    this.done(v);
    this.close();
  }
  onClose() {
    this.contentEl.empty();
    if (!this.answered) this.done(false);
  }
};
function confirmModal(app, o) {
  return new Promise((resolve) => new ConfirmModal(app, o, resolve).open());
}
var ChoiceModal = class extends import_obsidian3.Modal {
  constructor(app, o, done) {
    super(app);
    this.o = o;
    this.done = done;
    this.answered = false;
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
    let first = null;
    o.options.forEach((opt, i) => {
      const btn = b.createEl("button", { text: opt.label, cls: opt.kind === "cta" ? "mod-cta" : opt.kind === "warning" ? "mod-warning" : "" });
      btn.addEventListener("click", () => this.choose(i));
      if (opt.kind === "cta" && !first) first = btn;
    });
    if (o.note) el.createDiv({ cls: "vm-muted vm-small-text", text: o.note });
    window.setTimeout(() => first?.focus(), 0);
  }
  choose(i) {
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
};
function choiceModal(app, o) {
  let m = null;
  const result = new Promise((resolve) => {
    m = new ChoiceModal(app, o, resolve);
    m.open();
  });
  return { result, close: () => m?.close() };
}
function askOptions(ask) {
  const opts = ask.options.map((label, i) => {
    let kind;
    if (ask.id === "budget") kind = i === 0 ? "warning" : i === 1 ? "cta" : void 0;
    else if (i === 0) kind = "cta";
    return { label, kind };
  });
  const note = ask.id === "budget" ? "Stopping is safe: processed items are saved and the next run will continue. Set the budget under Settings > Expenses." : ask.id === "estimate" ? "Set the confirmation threshold under Settings > Expenses. Closing this window is the same as Cancel." : "Closing this window is the same as declining.";
  return { title: ask.title, text: ask.text, lines: ask.lines, options: opts, note, cls: "vm-ask" };
}
var TextModal = class extends import_obsidian3.Modal {
  constructor(app, title, text) {
    super(app);
    this.title = title;
    this.text = text;
  }
  onOpen() {
    this.setTitle(this.title);
    this.modalEl.addClass("vm-wide");
    this.contentEl.createEl("pre", { cls: "vm-pre", text: this.text || "(empty)" });
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "Copy" }).addEventListener("click", async () => {
      new import_obsidian3.Notice(await copyText(this.text) ? "Copied" : "Could not copy. Select the text and press Ctrl+C.");
    });
    b.createEl("button", { text: "Close" }).addEventListener("click", () => this.close());
  }
  onClose() {
    this.contentEl.empty();
  }
};
var ContainerPicker = class extends import_obsidian3.FuzzySuggestModal {
  constructor(plugin, allLabel, onPick) {
    super(plugin.app);
    this.plugin = plugin;
    this.allLabel = allLabel;
    this.onPick = onPick;
    this.setPlaceholder("Start typing a container name");
  }
  getItems() {
    const ui = this.plugin.ui;
    const out = [];
    if (this.allLabel) out.push({ c: null, label: this.allLabel });
    for (const c of ui?.containers || []) out.push({ c, label: ui ? containerLabel(ui, c) : c.title });
    return out;
  }
  getItemText(it) {
    return it.label;
  }
  onChooseItem(it) {
    this.onPick(it.c);
  }
};
var NewThoughtModal = class extends import_obsidian3.Modal {
  constructor(plugin, hint = "") {
    super(plugin.app);
    this.plugin = plugin;
    this.hint = hint;
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
    now.checked = false;
    f4.createEl("label", { text: "Process immediately (Phase 1)", attr: { for: "vm-now" } });
    const b = el.createDiv({ cls: "vm-modal-buttons" });
    const save = b.createEl("button", { text: "Save", cls: "mod-cta" });
    b.createEl("button", { text: "Cancel" }).addEventListener("click", () => this.close());
    const go = async () => {
      const text = ta.value.trim();
      if (!text) {
        new import_obsidian3.Notice("Write a thought.");
        ta.focus();
        return;
      }
      save.disabled = true;
      try {
        const path3 = await this.plugin.saveThought(text, hint.value.trim(), date.value || todayIso(), src.value);
        this.close();
        if (now.checked) {
          new import_obsidian3.Notice(`Thought saved: ${path3}. Processing now\u2026`);
          this.plugin.runPhase1();
        } else new import_obsidian3.Notice(`Thought saved: ${path3}. It will be processed during the next Phase 1 run.`);
      } catch (e) {
        save.disabled = false;
        new import_obsidian3.Notice(`Could not save: ${e}`);
      }
    };
    save.addEventListener("click", go);
    ta.addEventListener("keydown", (ev) => {
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
};
function thoughtFile(text, hint, dateIso) {
  const [y, m, d] = dateIso.split("-");
  const head = [`${d}.${m}.${y}`];
  if (hint) head.push(`hint: ${hint}`);
  head.push("mode: steady_state");
  return { name: `${dateIso} ${nowHm()} ${fileSlug(text)}.txt`, body: head.join("\n") + "\n\n" + text.trim() + "\n" };
}
function sourceText(r) {
  if (r.source === "own") return "current: custom container threshold";
  if (r.source === "parent") return `now \u2014 parental \xAB${r.from}\xBB`;
  return "current: global threshold from settings";
}
var AdviceModal = class extends import_obsidian3.Modal {
  constructor(plugin, c, ready) {
    super(plugin.app);
    this.plugin = plugin;
    this.c = c;
    this.ready = ready;
    this.alive = true;
  }
  async onOpen() {
    this.setTitle(`AI Council on Thresholds \xB7 ${this.c.title}`);
    this.modalEl.addClass("vm-wide");
    this.contentEl.addClass("vm-modal", "vm-advice");
    if (this.ready) {
      this.show(this.ready);
      return;
    }
    const w = this.contentEl.createDiv({ cls: "vm-wait" });
    w.createDiv({ cls: "vm-progress" });
    w.createDiv({
      text: this.plugin.engine.busy() ? "Queued: advice will start after the current run." : "The model reviews how the program handled this container: placement errors, unnecessary questions, and what was added to the database."
    });
    w.createDiv({ cls: "vm-muted", text: "This makes one model request. You can close the window; the advice will remain on the Container tab." });
    const r = await this.plugin.adviseNow(this.c);
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
  show(a) {
    const el = this.contentEl;
    el.createDiv({ cls: "vm-advice-summary", text: a.summary || "The model did not provide a conclusion." });
    const chosen = new Set(a.recommendations.map((r) => r.name));
    if (!a.recommendations.length) el.createDiv({ cls: "vm-callout is-ok", text: "No threshold changes needed." });
    let apply = null;
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
      v.appendText(" \u2192 ");
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
        const changes = {};
        for (const r of a.recommendations) if (chosen.has(r.name)) changes[r.name] = r.value;
        apply.disabled = true;
        const ok = await this.plugin.saveThresholds(this.c, changes);
        if (ok) {
          new import_obsidian3.Notice(`Thresholds \xAB${this.c.title}\xBB updated: ` + a.recommendations.filter((r) => chosen.has(r.name)).map((r) => `${r.label.toLowerCase()} ${r.current} \u2192 ${r.value}`).join(", "));
          this.plugin.forgetAdvice(this.c.id);
          this.close();
        } else apply.disabled = false;
      });
    }
    b.createEl("button", { text: "Close" }).addEventListener("click", () => this.close());
    el.createDiv({
      cls: "vm-muted vm-small-text",
      text: "The selected values will be saved to the container's YAML (the thresholds field) and applied from the next Phase 1 run. The program will remember which advice you accepted."
    });
  }
  closeButton() {
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "Close" }).addEventListener("click", () => this.close());
  }
  onClose() {
    this.alive = false;
    this.contentEl.empty();
  }
};
var CheckModal = class extends import_obsidian3.Modal {
  constructor(plugin) {
    super(plugin.app);
    this.plugin = plugin;
    this.alive = true;
  }
  async onOpen() {
    this.setTitle("Check connection");
    this.contentEl.addClass("vm-modal");
    const w = this.contentEl.createDiv({ cls: "vm-wait" });
    w.createDiv({ cls: "vm-progress" });
    w.createDiv({ text: "Checking the vault, model, and embeddings; this may take a few seconds\u2026" });
    const r = await this.plugin.engine.run(["check"], { label: "Check connection", exclusive: false });
    if (!this.alive) return;
    this.contentEl.empty();
    const items = r.check || [];
    const list = this.contentEl.createDiv({ cls: "vm-checklist" });
    for (const it of items) {
      const row = list.createDiv({ cls: "vm-check-item " + (it.ok ? "is-ok" : "is-bad") });
      row.createSpan({ cls: "vm-check-mark", text: it.ok ? "\u2713" : "\u2717" });
      const body = row.createDiv();
      body.createDiv({ cls: "vm-check-name", text: it.name });
      body.createDiv({ cls: "vm-muted", text: it.text });
    }
    if (!items.length || r.error) this.contentEl.createDiv({ cls: "vm-callout is-warning", text: r.error || "The program did not respond." });
    else this.contentEl.createDiv({ cls: "vm-callout " + (r.ok ? "is-ok" : "is-warning"), text: r.ok ? "Everything is working." : "There are problems; see the rows marked \u2717." });
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "Close", cls: "mod-cta" }).addEventListener("click", () => this.close());
  }
  onClose() {
    this.alive = false;
    this.contentEl.empty();
  }
};
var LLAMA_BUILD_RU = {
  cpu: "for CPU",
  vulkan: "Vulkan \u2014 for any GPU",
  cuda: "CUDA \u2014 for NVIDIA GPUs",
  system: "installed on this computer"
};
function llamaBuildFor(st, p, nvidia) {
  const have = st.builds || {};
  if (p.device === "cpu" || st.os === "macos") {
    for (const b of ["cpu", "vulkan", "cuda"]) if (have[b]) return { build: b, have: true };
    return st.system ? { build: "system", have: true } : { build: "cpu", have: false };
  }
  let want = p.build;
  if (want === "auto" || want === "cpu") want = nvidia ? "cuda" : "vulkan";
  if (want === "cuda" && !(st.os === "win" && st.arch === "x64")) want = "vulkan";
  return { build: want, have: !!have[want] };
}
function gb(x) {
  return x == null ? "?" : `${Math.round(x * 10) / 10}`;
}
var LlamaModal = class extends import_obsidian3.Modal {
  constructor(plugin, st, onStart) {
    super(plugin.app);
    this.plugin = plugin;
    this.onStart = onStart;
    this.alive = true;
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
    el.createDiv({ cls: "vm-muted vm-small-text vm-choice-sub", text: `${this.st.model.title} \xB7 llama.cpp \xB7 model` });
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
  renderHw() {
    const el = this.hwEl;
    el.empty();
    const hw = this.hw;
    if (!hw) {
      el.createDiv({ cls: "vm-muted", text: "Detecting computer hardware\u2026" });
      return;
    }
    const cpu = [hw.cpu || "CPU", hw.cores ? `${hw.cores} ${plural(hw.cores, ["core", "cores", "cores"])}` : "", hw.threads ? `${hw.threads} ${plural(hw.threads, ["thread", "threads", "threads"])}` : ""].filter(Boolean).join(" \xB7 ");
    const rows = [
      ["CPU", cpu],
      ["Memory", hw.ram_gb ? `${gb(hw.ram_gb)} GB` + (hw.ram_free_gb ? ` (${gb(hw.ram_free_gb)} GB free)` : "") : "could not determine"],
      ["GPU", hw.gpus.length ? hw.gpus.map((g) => g.name + (g.vram_gb ? `, ${gb(g.vram_gb)} GB` : "")).join("; ") : "not found"]
    ];
    const t = el.createDiv({ cls: "vm-llama-hw-grid" });
    for (const [k, v] of rows) {
      t.createDiv({ cls: "vm-muted", text: k });
      t.createDiv({ text: v });
    }
  }
  renderForm() {
    const el = this.formEl;
    el.empty();
    const p = this.p;
    const st = this.st;
    const hw = this.hw;
    const upd = () => this.renderNotes();
    new import_obsidian3.Setting(el).setName("Run on").setDesc("A GPU is much faster. Running on the CPU requires at least 16 GB of RAM.").addDropdown((d) => d.addOptions({ cpu: "CPU", gpu: "GPU" }).setValue(p.device).onChange((v) => {
      p.device = v;
      this.renderForm();
    }));
    if (p.device === "gpu" && st.os !== "macos") {
      const opts = { auto: "Auto: NVIDIA uses CUDA; others use Vulkan" };
      if (st.os === "win" && st.arch === "x64") opts.cuda = "CUDA \u2014 for NVIDIA GPUs";
      opts.vulkan = "Vulkan \u2014 for NVIDIA, AMD, and Intel GPUs";
      if (!opts[p.build]) p.build = "auto";
      new import_obsidian3.Setting(el).setName("llama.cpp build").setDesc("Select the llama.cpp build to download for the GPU.").addDropdown((d) => d.addOptions(opts).setValue(p.build).onChange((v) => {
        p.build = v;
        upd();
      }));
      const layers = st.model.layers || 48;
      const mode = typeof p.gpu_layers === "number" ? "num" : p.gpu_layers;
      const s = new import_obsidian3.Setting(el).setName("Model layers on GPU").setDesc(`There are ${layers} layers. Layers that do not fit on the GPU run on the CPU (more slowly).`);
      s.addDropdown((d) => d.addOptions({ auto: "As many as fit", all: `All (${layers})`, num: "Custom number" }).setValue(mode).onChange((v) => {
        p.gpu_layers = v === "num" ? Math.min(layers, 24) : v;
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
    const ctxs = [.../* @__PURE__ */ new Set([...st.ctx_choices || [2048, 4096, 8192, 16384, 32768], p.ctx])].sort((a, b) => a - b);
    const ctxOpts = {};
    for (const c of ctxs) {
      const need = this.needGb(c);
      ctxOpts[String(c)] = `${c.toLocaleString("en-US")} tokens \u2248 ${Math.round(c * 3 / 1e3)}k characters` + (need ? ` \xB7 ${gb(need)} GB` : "");
    }
    new import_obsidian3.Setting(el).setName("Context").setDesc("The maximum text the model reads at once and its memory usage. Long entries are truncated by the program's text limit, so 4096 is usually sufficient.").addDropdown((d) => d.addOptions(ctxOpts).setValue(String(p.ctx)).onChange((v) => {
      p.ctx = parseInt(v, 10);
      upd();
    }));
    const kvRu = { f16: "f16 \u2014 uncompressed", q8_0: "q8_0 \u2014 8 bit", q4_0: "q4_0 \u2014 4 bit" };
    const kvOpts = {};
    for (const k of st.kv_types || ["f16", "q8_0", "q4_0"]) kvOpts[k] = kvRu[k] || k;
    new import_obsidian3.Setting(el).setName("KV cache quantization").setDesc("This setting has little effect for this model: it reads each text in one pass without keeping a KV cache, so memory usage depends on Context. Leave it at f16.").addDropdown((d) => d.addOptions(kvOpts).setValue(p.kv_cache).onChange((v) => {
      p.kv_cache = v;
      upd();
    }));
    const cores = hw?.cores || null;
    const ts = new import_obsidian3.Setting(el).setName("CPU threads").setDesc("0 lets llama.cpp choose." + (cores ? ` This computer has ${cores} ${plural(cores, ["core", "cores", "cores"])}${hw?.threads ? ` (${hw.threads} ${plural(hw.threads, ["thread", "threads", "threads"])})` : ""} \u2014 matching the thread count to the core count is usually fastest.` : ""));
    let thrInput = null;
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
    new import_obsidian3.Setting(el).setName("Start automatically when needed").setDesc("If the server is not running, for example after a restart, the program will start it with these settings during Phase 1 or when checking the connection.").addToggle((t) => t.setValue(p.autostart).onChange((v) => {
      p.autostart = v;
    }));
    const md = new import_obsidian3.Setting(el).setName("Model folder").setDesc(`Leave empty to use ${st.default_models_dir}. Model size: ${sizeText(st.model.size)}.`);
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
  needGb(ctx) {
    const m = this.st.need_gb || {};
    if (m[String(ctx)]) return m[String(ctx)];
    const pts = Object.entries(m).map(([k, v]) => [Number(k), v]).sort((a, b) => a[0] - b[0]);
    for (let i = 1; i < pts.length; i++)
      if (ctx <= pts[i][0]) return pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * (ctx - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0]);
    return pts.length ? pts[pts.length - 1][1] : 0;
  }
  numField(el, name, desc, key) {
    new import_obsidian3.Setting(el).setName(name).setDesc(desc).addText((t) => {
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
  renderNotes() {
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
        el.createDiv({ cls: "vm-callout is-bad vm-llama-ram", text: `\u26A0 Low memory: this computer has ${gb(ram)} GB; the model requires at least ${min} GB of RAM on CPU (${withCtx}). Severe slowdowns or out-of-memory errors may occur.` + (hw?.gpus.length ? " Consider selecting GPU." : "") });
      else if (ram !== null && mem > ram - 2)
        el.createDiv({ cls: "vm-callout is-bad vm-llama-ram", text: `\u26A0 Insufficient memory: ${withCtx}, but this computer has ${gb(ram)} GB. Select a smaller context.` });
      else
        el.createDiv({ cls: "vm-callout is-warning vm-llama-ram", text: `\u26A0 This model requires at least ${min} GB of RAM on CPU` + (ram !== null ? ` \u2014 this computer has ${gb(ram)} GB` : " (the amount on this computer could not be determined)") + `; ${withCtx}. The model runs much more slowly on CPU than GPU.` });
    } else if (hw) {
      const vram = Math.max(0, ...hw.gpus.map((g) => g.vram_gb || 0));
      if (!hw.gpus.length) el.createDiv({ cls: "vm-callout is-warning", text: "No GPU was found. If you have one, update its driver; otherwise, select CPU." });
      else if (vram && vram < mem)
        el.createDiv({ cls: "vm-callout", text: `GPU memory is ${gb(vram)} GB; ${withCtx}. Some layers will remain in RAM, which is slower but works. As many as fit selects the layers automatically. A smaller context leaves room for more GPU layers.` });
      else el.createDiv({ cls: "vm-callout is-ok", text: `The model needs about ${gb(mem)} GB of GPU memory (context ${p.ctx.toLocaleString("en-US")})` + (vram ? ` \u2014 this GPU has ${gb(vram)} GB.` : ".") });
    }
    const items = [];
    let need = 0;
    const m = st.model;
    const savedDir = (st.params.models_dir || "").trim();
    if ((p.models_dir || "").trim() !== savedDir) items.push(`Model: download to the new folder if not already there (${sizeText(m.size)})`);
    else if (!m.exists) {
      const left = Math.max(0, m.size - (m.partial || 0));
      need += left;
      items.push(m.partial ? `Model ${m.title} \u2014 ${sizeText(left)} remaining (${sizeText(m.partial)} already downloaded)` : `Model ${m.title} \u2014 ${sizeText(m.size)}`);
    }
    const b = llamaBuildFor(st, p, !!hw?.nvidia);
    if (!b.have) items.push(`llama.cpp (${LLAMA_BUILD_RU[b.build] || b.build}) \u2014 about ${st.approx_mb?.[b.build] || 30} MB` + (b.build === "cuda" ? " including CUDA libraries" : ""));
    if (st.vcredist_missing) items.push(`Microsoft Visual C++ libraries \u2014 about ${st.approx_mb?.vcredist || 25} MB (Windows will request installation permission)`);
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
    el.createDiv({ cls: "vm-muted vm-small-text", text: `Server address: http://127.0.0.1:${port}/v1 \u2014 the program will fill this in automatically.` });
  }
  go() {
    const p = this.p;
    const errs = [];
    const int = (v, lo, hi) => typeof v === "number" && Number.isInteger(v) && v >= lo && v <= hi;
    if (!int(p.port, 1024, 65535)) errs.push("port must be between 1024 and 65535");
    if (!int(p.threads, 0, 1024)) errs.push("threads must be between 0 and 1024");
    if (!int(p.sleep_min, 0, 10080)) errs.push("idle time must be between 0 and 10080 minutes");
    if (typeof p.gpu_layers === "number" && !int(p.gpu_layers, 0, 999)) errs.push("layers must be between 0 and 999");
    if (errs.length) {
      new import_obsidian3.Notice("Check: " + errs.join("; ") + ".", 8e3);
      return;
    }
    this.close();
    this.onStart({ ...p });
  }
};

// src/settings.ts
var import_obsidian4 = require("obsidian");
var fs2 = __toESM(require("fs"));
function getPath(o, key) {
  return key.split(".").reduce((a, k) => a == null ? void 0 : a[k], o);
}
function setPath(o, key, v) {
  const ks = key.split(".");
  let cur = o;
  for (const k of ks.slice(0, -1)) {
    if (cur[k] == null || typeof cur[k] !== "object") cur[k] = {};
    cur = cur[k];
  }
  cur[ks[ks.length - 1]] = v;
}
var clone = (x) => x === void 0 ? x : JSON.parse(JSON.stringify(x));
var same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
var FIXED_SOURCES = { archive: "Old entries: _staging/archive", note: "Files directly in _staging" };
var TAB_ORDER = ["main", "models", "thresholds", "input", "docs", "costs", "advanced"];
var TAB_NAMES = {
  main: "General",
  models: "Models",
  thresholds: "Thresholds",
  input: "Incoming",
  docs: "Documents",
  costs: "Expenses",
  advanced: "Advanced"
};
function tabOfError(msg) {
  const m = msg.trim().toLowerCase();
  if (/^llm\.(webchat|max_format_retries)|^limits\./.test(m)) return "advanced";
  if (/^(profile|llm\.|embeddings\.)/.test(m)) return "models";
  if (/^(thresholds\.|seed_dormancy_days)/.test(m)) return "thresholds";
  if (/^(budget\.|estimate\.)/.test(m)) return "costs";
  if (/^(sources|dialogue_markers|input\.)/.test(m)) return "input";
  if (/^style\./.test(m)) return "docs";
  return "main";
}
function fmt(v) {
  if (v === null || v === void 0 || v === "") return "empty";
  if (typeof v === "boolean") return v ? "on" : "off";
  return String(v);
}
var BrainSettingTab = class extends import_obsidian4.PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
    this.info = null;
    this.values = null;
    this.loadError = null;
    this.loading = false;
    this.dirty = /* @__PURE__ */ new Set();
    this.timer = null;
    this.saving = null;
    this.tab = "main";
    this.query = "";
    this.editProfile = null;
    this.errors = [];
    // not navEl neither renderTab: names Obsidian 1.13+ inside SettingTab (menu item on the left and tab drawing)
    this.barEl = null;
    this.bodyEl = null;
    this.dynEl = null;
    this.statusEl = null;
    this.progTimer = null;
    this.lastProblem = null;
    // jelly-fish (llama.cpp)
    this.llamaSt = null;
    this.llamaBusy = false;
    this.llamaFresh = false;
    this.llamaAgain = false;
    this.llamaWasBusy = false;
    this.llamaLive = null;
    this.llamaTimer = null;
  }
  /** Obsidian open-up: show up and re-read settings.yaml. */
  display() {
    this.llamaFresh = false;
    try {
      this.redraw();
    } catch (e) {
      this.containerEl.empty();
      renderError(this.containerEl.createDiv({ cls: "vm-settings" }), this.plugin, "setting", e);
    }
    if (!this.plugin.engine.problem()) this.load();
    if (this.llamaTimer) window.clearInterval(this.llamaTimer);
    this.llamaTimer = window.setInterval(() => this.tickLlama(), 1e3);
  }
  hide() {
    if (this.llamaTimer) window.clearInterval(this.llamaTimer);
    this.llamaTimer = null;
    this.flush();
  }
  /** The program itself changed the settings. (for example, «Run the model…» logged in the server address) — read over. */
  reload() {
    this.llamaFresh = false;
    if (!this.containerEl.isConnected) return;
    if (!this.plugin.engine.problem()) this.load();
    this.loadLlama();
  }
  /** Open the settings on the desired tab (panel). */
  openTab(tab) {
    this.tab = tab;
    this.query = "";
  }
  redraw() {
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
  tabNames() {
    return { ...TAB_NAMES, ...this.info?.tabs || {} };
  }
  renderNav() {
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
    const search = nav.createEl("input", { type: "search", cls: "vm-set-search", attr: { placeholder: "Search settings\u2026", "aria-label": "Search settings" } });
    search.value = this.query;
    search.addEventListener("input", () => {
      this.query = search.value;
      tabs.toggleClass("is-searching", !!this.query.trim());
      this.renderBody();
    });
  }
  renderBody() {
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
  where(tab = this.tab) {
    return this.query.trim() ? "setting, search" : `setting, tab \xAB${this.tabNames()[tab] || tab}\xBB`;
  }
  /** Re-draw the variable part of the tab (field «Program folder» It doesnt lose focus.). */
  rerender() {
    if (this.query.trim() || !this.dynEl) this.renderBody();
    else this.renderDyn(this.dynEl, this.tab);
  }
  renderPane(el, tab, main) {
    if (tab === "main") {
      this.renderProgram(el);
      this.renderNotify(el);
    }
    const dyn = el.createDiv();
    if (main) this.dynEl = dyn;
    this.renderDyn(dyn, tab);
  }
  renderDyn(el, tab) {
    el.empty();
    try {
      this.renderDynBody(el, tab);
    } catch (e) {
      renderError(el, this.plugin, this.where(tab), e);
    }
  }
  renderDynBody(el, tab) {
    for (const e of this.errors.filter((x) => x.tab === tab)) el.createDiv({ cls: "vm-callout is-warning", text: "Not saved: " + e.text });
    if (this.plugin.engine.problem()) {
      if (tab !== "main") el.createDiv({ cls: "vm-callout is-warning", text: "First specify the program folder on the General tab." });
      return;
    }
    if (!this.info || !this.values) {
      el.createDiv({ cls: this.loadError ? "vm-callout is-warning" : "vm-muted", text: this.loadError || "Loading program settings\u2026" });
      if (this.loadError) new import_obsidian4.Setting(el).addButton((b) => b.setButtonText("Try again").onClick(() => this.load()));
      return;
    }
    for (const sec of this.info.schema.filter((s) => (s.tab || "advanced") === tab)) this.renderSection(el, sec);
    if (tab === "models") {
      new import_obsidian4.Setting(el).setName("Check connection").setDesc("The main model, models for individual steps, and embeddings are checked separately.").addButton((b) => b.setButtonText("Check connection").setCta().onClick(async () => {
        await this.flush();
        this.plugin.runCheck();
      }));
    }
    if (tab === "costs") {
      new import_obsidian4.Setting(el).setName("Detailed expenditures").setDesc("View costs by model, step, day, and run, and cloud profile prices on the Expenses tab of the Second Brain panel.").addButton((b) => b.setButtonText("Open Expenses").onClick(async () => {
        await this.flush();
        this.app.setting?.close?.();
        this.plugin.openView("usage");
      }));
    }
    if (tab === "advanced") this.renderService(el);
  }
  renderSearch(el) {
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
        it.toggleClass("vm-hidden", !ok);
        if (ok) n++;
      });
      pane.querySelectorAll(".vm-sec").forEach((sec) => {
        const vis = sec.querySelectorAll(".setting-item:not(.setting-item-heading):not(.vm-hidden)").length;
        sec.toggleClass("vm-hidden", !vis);
      });
      if (!n) pane.addClass("vm-hidden");
      found += n;
    }
    if (!found) el.createDiv({ cls: "vm-muted vm-search-none", text: `No settings found for \u201C${this.query.trim()}\u201D.` });
  }
  section(el, title, help) {
    const box = el.createDiv({ cls: "vm-sec" });
    new import_obsidian4.Setting(box).setName(title).setHeading();
    if (help) box.createDiv({ cls: "setting-item-description vm-sec-help", text: help });
    return box;
  }
  renderSection(el, sec) {
    const box = this.section(el, sec.title, sec.help);
    for (const f of sec.fields) {
      if (!this.visible(f)) continue;
      this.renderField(box, f);
      if (f.key === "embeddings.mode" && String(getPath(this.values, "embeddings.mode")) === "local") this.renderLlama(box);
    }
    if (sec.id === "updates") this.renderUpdateButtons(box);
  }
  visible(f) {
    if (!f.show_if || !this.values) return true;
    return Object.entries(f.show_if).every(([k, vals]) => vals.includes(String(getPath(this.values, k))));
  }
  async load() {
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
  renderProgram(el) {
    const p = this.plugin;
    const box = this.section(el, "Program");
    new import_obsidian4.Setting(box).setName("Program folder").setDesc("The folder containing Install.bat and the brain folder. Install.bat fills this in.").setClass("vm-wide-setting").addText((t) => t.setPlaceholder("C:\\Second Brain").setValue(p.data.programDir).onChange(async (v) => {
      p.data.programDir = v.trim();
      await p.saveData(p.data);
      this.programChanged();
    }));
    new import_obsidian4.Setting(box).setName("Python").setDesc("Usually no change is needed. Leave empty to use the Python installed by Install.bat.").setClass("vm-wide-setting").addText((t) => t.setPlaceholder(p.engine.defaultPython()).setValue(p.data.pythonPath).onChange(async (v) => {
      p.data.pythonPath = v.trim();
      await p.saveData(p.data);
      this.programChanged();
    }));
    this.statusEl = box.createDiv();
    this.renderStatus();
    new import_obsidian4.Setting(box).setName("Check connection").setDesc("Checks the vault, each model used by a step, and embeddings.").addButton((b) => b.setButtonText("Check connection").setCta().onClick(async () => {
      await this.flush();
      p.runCheck();
    }));
  }
  renderNotify(el) {
    const p = this.plugin;
    const d = p.data;
    const save = () => p.saveData(d);
    const box = this.section(el, "Windows notifications", "System notifications appear when Obsidian is minimized or another window is active.");
    new import_obsidian4.Setting(box).setName("Notify when a long run finishes").setDesc("Phase 1, Phase 2, or revalidation runs that exceed the time below.").addToggle((t) => t.setValue(d.notify).onChange(async (v) => {
      d.notify = v;
      await save();
    }));
    const m = new import_obsidian4.Setting(box).setName("Long run threshold, minutes").setDesc("0 means notify for every run.");
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
    new import_obsidian4.Setting(box).setName("Notify when the program is waiting for an answer").setDesc("For example, when the budget is exhausted or a large run needs confirmation.").addToggle((t) => t.setValue(d.notifyAsk).onChange(async (v) => {
      d.notifyAsk = v;
      await save();
    }));
    new import_obsidian4.Setting(box).setName("Only when Obsidian is not focused").setDesc("Turn off to receive notifications even when Obsidian is focused.").addToggle((t) => t.setValue(d.notifyUnfocused).onChange(async (v) => {
      d.notifyUnfocused = v;
      await save();
    }));
    new import_obsidian4.Setting(box).setName("Test notification").setDesc("If it does not appear, allow notifications for Obsidian in Windows Settings > System > Notifications.").addButton((b) => b.setButtonText("Show").onClick(() => {
      const ok = p.osNotify("Second Brain", "This is what a notification for a completed long run looks like.", "done", true);
      if (!ok) new import_obsidian4.Notice("Could not display the notification. Allow Obsidian notifications in Windows settings.", 1e4);
    }));
  }
  renderUpdateButtons(el) {
    const skip = this.plugin.data.skipVersion;
    const repo = (this.info?.update_repo || "").trim();
    new import_obsidian4.Setting(el).setName("Check now").setDesc(`Installed version: ${this.info?.version || "?"}.` + (skip ? ` Skipped version: ${skip}; a manual check will offer it again.` : "") + (repo ? "" : " No repository URL is configured in brain/__init__.py (UPDATE_REPO); there is nowhere to check for updates.")).addButton((b) => {
      b.setButtonText("Check for updates").onClick(async () => {
        await this.flush();
        this.plugin.checkUpdates(true);
      });
      if (!repo) b.setDisabled(true);
    });
  }
  // ---------- jelly-fish (llama.cpp) ----------
  /** Status of the model under «Where to count: on this computer»: squirt, llama.cpp, server; trigger. */
  renderLlama(el) {
    const st = this.llamaSt;
    const box = el.createDiv({ cls: "vm-llama-box" });
    const s = new import_obsidian4.Setting(box).setName("Local model");
    s.settingEl.addClass("vm-llama-setting");
    const d = s.descEl;
    if (!st) d.createDiv({ text: this.llamaBusy ? "Checking whether the model is downloaded\u2026" : "KaLM-Embedding-Gemma3 12B runs on llama.cpp. Use Start model\u2026 to download and start it." });
    else {
      const m = st.model;
      d.createDiv({ text: `${m.title}: ` + (m.exists ? "downloaded" : m.partial ? `downloaded ${sizeText(m.partial)} from ${sizeText(m.size)} \u2014 download resumes on start` : `not downloaded (${sizeText(m.size)}) \u2014 will download on start`) });
      const names = Object.values(st.builds || {}).map((b) => `${LLAMA_BUILD_RU[b.build] || b.build}${b.tag ? ` (${b.tag})` : ""}`);
      d.createDiv({ text: "llama.cpp: " + (names.length ? names.join(", ") : st.system ? "installed on this computer" : "not downloaded; will be downloaded when started") });
      const srv = st.server;
      const dev = srv.params?.device === "gpu" ? "GPU" : "CPU";
      d.createDiv({
        cls: srv.running && srv.health === "ok" ? "vm-key-ok" : "",
        text: "server: " + (srv.running ? `running \u2014 ${srv.url} (${dev})` + (srv.health === "loading" ? ", loading model" : srv.health == null ? ", not responding" : "") : "not running" + (st.params.autostart && st.configured && m.exists ? " \u2014 starts automatically when needed" : ""))
      });
      if (!st.configured) d.createDiv({ cls: "vm-field-note", text: "The address below points to a different server. Start model\u2026 will fill in the correct address." });
    }
    const busy = !!this.llamaJob();
    s.addButton((b) => {
      b.setButtonText(st?.server.running ? "Restart\u2026" : "Start model\u2026").setCta().onClick(() => this.openLlama());
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
  loadLlama() {
    if (this.llamaBusy) {
      this.llamaAgain = true;
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
  llamaJob() {
    return this.plugin.engine.find((j) => j.args[0] === "llama" && j.args[1] === "start" && (j.status === "running" || j.status === "queued"));
  }
  /** Status of model launch — right here (The settings window closes the panel «Second Brain»). */
  tickLlama() {
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
    el.createDiv({ cls: "vm-llama-live-text", text: (info.stage || job.lastLine || "Starting\u2026") + (info.eta ? ` \xB7 ${info.eta}` : "") });
    if (info.frac !== null) {
      const bar = el.createDiv({ cls: "vm-bar" });
      bar.createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.round(info.frac * 1e3) / 10}%`;
    } else el.createDiv({ cls: "vm-progress" });
    const row = el.createDiv({ cls: "vm-llama-live-row" });
    row.createSpan({ cls: "vm-muted vm-small-text", text: job.stopAt ? "Stopping\u2026 Downloaded data is retained and the next run will resume." : "You can close settings; progress is also visible in the Second Brain panel." });
    if (!job.stopAt) {
      const stop = row.createEl("button", { text: "Stop" });
      stop.addEventListener("click", () => this.plugin.engine.stop());
    }
  }
  async openLlama() {
    await this.flush();
    const st = await this.plugin.llamaStatus(false) || this.llamaSt;
    if (!st) {
      new import_obsidian4.Notice("The program did not respond, so the model status is unknown. Check the program folder on the General tab.", 1e4);
      return;
    }
    this.llamaSt = st;
    new LlamaModal(this.plugin, st, (params) => {
      this.plugin.runLlamaStart(params);
      window.setTimeout(() => this.tickLlama(), 300);
    }).open();
  }
  async showLlamaLog(file) {
    let text = "";
    try {
      const raw = String(await fs2.promises.readFile(file, "utf8"));
      text = raw.split(/\r?\n/).slice(-300).join("\n");
    } catch (e) {
      text = `Journal not read: ${e}`;
    }
    new TextModal(this.app, "Model server log (last lines)", text).open();
  }
  renderService(el) {
    const box = this.section(el, "Advanced");
    new import_obsidian4.Setting(box).setName("Prompts").setDesc("Model request templates are files in the program folder. You can edit them; changes take effect on the next run and are preserved during updates.").addButton((b) => b.setButtonText("Open prompts folder").onClick(() => this.plugin.revealPath(this.info.prompts_dir)));
    new import_obsidian4.Setting(box).setName("Settings file").setDesc(`${this.info.path} \u2014 The plugin rewrites this file with explanations; the previous version is saved as settings.yaml.bak.`).addButton((b) => b.setButtonText("Show in folder").onClick(() => this.plugin.revealPath(this.info.path, true)));
    new import_obsidian4.Setting(box).setName("Developer report").setDesc("If something is wrong, collect versions, recent errors, and recent run output in _logs/developer-report.md and copy it to the clipboard. Review the report before sharing: recent output and errors may include sensitive information.").addButton((b) => b.setButtonText("Create report").onClick(async () => {
      await this.flush();
      this.app.setting?.close?.();
      await saveDeveloperReport(this.plugin);
    }));
  }
  renderStatus() {
    const el = this.statusEl;
    if (!el) return;
    el.empty();
    const prob = this.plugin.engine.problem();
    this.lastProblem = prob;
    el.className = "vm-callout " + (prob ? "is-warning" : "is-ok");
    el.setText(prob || `Program found${this.info ? `, version ${this.info.version}` : ""}. Vault: ${this.plugin.engine.vaultPath()}`);
  }
  programChanged() {
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
  put(key) {
    return (v) => this.set(key, v);
  }
  renderField(el, f) {
    const v = getPath(this.values, f.key);
    const def = getPath(this.info.defaults || {}, f.key);
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
        new import_obsidian4.Setting(el).setName(f.label).setDesc(`${f.help} Edit this value in settings.yaml.`);
    }
  }
  /** «↺» — default. Always visible (slide-line «leaper», when the meaning passes through
   *  silence); until the default — dull and unpressed. Returns function, field
   *  per-edit (button changes immediately, straight-painted). */
  resetButton(s, def, v, put) {
    if (def === void 0) return () => {
    };
    let comp = null;
    let changed = false;
    s.addExtraButton((b) => {
      comp = b;
      b.setIcon("rotate-ccw").onClick(() => {
        if (!changed) return;
        put(clone(def));
        this.rerender();
      });
      b.extraSettingsEl.addClass("vm-reset");
    });
    const mark = (x) => {
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
  fieldText(el, f, v, put, def, onBlur) {
    const s = new import_obsidian4.Setting(el).setName(f.label).setDesc(f.help);
    s.settingEl.addClass("vm-wide-setting");
    let mark = () => {
    };
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
  fieldChoice(el, f, v) {
    const def = getPath(this.info.defaults || {}, f.key);
    const s = new import_obsidian4.Setting(el).setName(f.label).setDesc(f.help);
    let mark = () => {
    };
    s.addDropdown((d) => {
      const ch = f.choices || {};
      for (const [k, label] of Object.entries(ch)) d.addOption(k, label);
      if (v != null && !(String(v) in ch)) d.addOption(String(v), String(v));
      d.setValue(v == null ? "" : String(v));
      d.onChange((x) => {
        this.set(f.key, x);
        mark(x);
        if (this.dependents(f.key)) this.rerender();
      });
    });
    mark = this.resetButton(s, def, v, this.put(f.key));
  }
  dependents(key) {
    return !!this.info?.schema.some((sec) => sec.fields.some((x) => x.show_if && key in x.show_if));
  }
  fieldBool(el, f, v, put, def) {
    const s = new import_obsidian4.Setting(el).setName(f.label).setDesc(f.help);
    let mark = () => {
    };
    s.addToggle((t) => t.setValue(!!v).onChange((x) => {
      put(x);
      mark(x);
    }));
    mark = this.resetButton(s, def, v, put);
  }
  /** Number.: field, rapids and temperatures — slider. «int?»/«float?» — leave empty. */
  fieldNumber(el, f, v, put, def) {
    const s = new import_obsidian4.Setting(el).setName(f.label).setDesc(f.help);
    s.settingEl.addClass("vm-num-setting");
    const err = s.descEl.createDiv({ cls: "vm-field-error" });
    const kind = f.type.startsWith("float") ? "float" : "int";
    const optional = f.type.endsWith("?");
    let txt;
    let rng = null;
    let mark = () => {
    };
    const handle = (x) => {
      const n = parseNumber(x, kind, f.min, f.max);
      const bad = n === null || n === void 0 && !optional;
      txt.inputEl.toggleClass("vm-invalid", bad);
      err.setText(bad ? `Enter a valid ${rangeText(kind, f.min, f.max)}${optional ? " (or empty)" : ""}.` : "");
      if (bad) return;
      put(n === void 0 ? null : n);
      mark(n === void 0 ? null : n);
      if (rng && typeof n === "number") rng.value = String(n);
    };
    if (f.slider && f.min !== void 0 && f.max !== void 0) {
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
  fieldJson(el, f, v, put) {
    const s = new import_obsidian4.Setting(el).setName(f.label).setDesc(f.help);
    const err = s.descEl.createDiv({ cls: "vm-field-error" });
    s.addTextArea((t) => {
      t.setValue(v && Object.keys(v).length ? JSON.stringify(v) : "");
      t.setPlaceholder("{}");
      t.inputEl.rows = 2;
      t.inputEl.addClass("vm-mono");
      t.onChange((x) => {
        let obj = {};
        try {
          obj = x.trim() ? JSON.parse(x) : {};
          if (typeof obj !== "object" || Array.isArray(obj) || obj === null) throw new Error("an object { \u2026 } is required");
        } catch (e) {
          err.setText(`Not JSON: ${e.message}`);
          t.inputEl.addClass("vm-invalid");
          return;
        }
        err.setText("");
        t.inputEl.removeClass("vm-invalid");
        put(obj);
      });
    });
  }
  fieldTextarea(el, f, v) {
    const s = new import_obsidian4.Setting(el).setName(f.label).setDesc(f.help);
    s.settingEl.addClass("vm-setting-block");
    s.addTextArea((t) => {
      t.setValue(v == null ? "" : String(v));
      t.inputEl.rows = 3;
      t.onChange((x) => this.set(f.key, x.trim()));
    });
  }
  fieldLines(el, f, v, def) {
    const s = new import_obsidian4.Setting(el).setName(f.label).setDesc(f.help);
    let mark = () => {
    };
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
  fieldKey(el, label, help, target, prof) {
    const keys = this.info.keys;
    let present = target === "embeddings" ? keys.embeddings : target.startsWith("profile:") ? !!keys.profiles?.[target.slice(8)] : keys.llm;
    if (prof && !prof.api_key_file) present = false;
    const s = new import_obsidian4.Setting(el).setName(label).setDesc(help);
    s.descEl.createDiv({ cls: present ? "vm-key-ok" : "vm-muted", text: present ? `\u2713 key saved${prof?.api_key_file ? ` (${prof.api_key_file})` : ""}` : "no key" });
    if (prof && prof.api_key_file) {
      const others = this.values.llm.profiles.filter((x) => x !== prof && x.api_key_file === prof.api_key_file);
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
    let input;
    s.addText((t) => {
      input = t;
      t.inputEl.type = "password";
      t.inputEl.autocomplete = "off";
      t.setPlaceholder(present ? "enter a new key to replace it" : "enter the key");
    });
    s.addButton((b) => b.setButtonText("Save").onClick(async () => {
      const k = input.getValue().trim();
      if (!k) {
        new import_obsidian4.Notice("Enter the key in the field.");
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
  async saveKey(target, key) {
    await this.flush();
    const r = await this.plugin.engine.run(["settings", "--key", target], { label: "Key", stdin: key + "\n", exclusive: false, quiet: true });
    if (r.ok) {
      new import_obsidian4.Notice(r.title || "Key saved.");
      if (r.settings) {
        this.info = r.settings;
        if (!this.dirty.size) this.values = clone(r.settings.values);
      }
      this.redraw();
    } else new import_obsidian4.Notice("Key not saved: " + (r.error || "error"), 1e4);
  }
  // ---------- mode and profiles of models ----------
  llm() {
    const v = this.values;
    if (!v.llm || typeof v.llm !== "object") v.llm = {};
    if (!Array.isArray(v.llm.profiles)) v.llm.profiles = [];
    return v.llm;
  }
  fieldLlm(el, f) {
    const info = this.info;
    const llm = this.llm();
    if (f.help) el.createDiv({ cls: "setting-item-description vm-sec-help", text: f.help });
    const modes = { ...info.modes || f.choices || {} };
    if (llm.mode && !(llm.mode in modes)) modes[llm.mode] = llm.mode === "fake" ? "Test model (for testing)" : llm.mode;
    new import_obsidian4.Setting(el).setName("Mode").setDesc("Where the main model runs.").addDropdown((d) => {
      for (const [k, label] of Object.entries(modes)) d.addOption(k, label);
      d.setValue(llm.mode || "cloud");
      d.onChange((v) => this.setMode(v));
    });
    const kind = llm.mode === "local" ? "local" : llm.mode === "cloud" ? "cloud" : null;
    if (kind) {
      const key = kind === "cloud" ? "cloud_profile" : "local_profile";
      const list = llm.profiles.filter((p) => p.kind === kind);
      new import_obsidian4.Setting(el).setName(kind === "cloud" ? "Cloud profile" : "Local profile").setDesc("The program uses this profile. You can assign different profiles to individual steps below.").addDropdown((d) => {
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
        text: "Web chat: the program places requests in the vault's _web-chat folder. Copy them into the model's chat and paste the responses into the answer files. Profiles below are only needed for steps assigned their own models."
      });
    }
    this.profileEditor(el);
  }
  /** Profile at current values. After each saving, the values are replaced by the program sent.,
   *  So buttons and fields., pre-painted, Find your profile on id, Not the old link.. */
  liveProfile(id) {
    return this.llm().profiles.find((x) => x && x.id === id) || null;
  }
  setMode(v) {
    const llm = this.llm();
    this.set("llm.mode", v);
    if (v === "cloud" || v === "local") {
      const key = v === "cloud" ? "cloud_profile" : "local_profile";
      const list = llm.profiles.filter((p) => p.kind === v);
      if (!list.length) this.set(`llm.${key}`, this.newProfile(v).id);
      else if (!list.some((p) => p.id === llm[key])) this.set(`llm.${key}`, list[0].id);
      this.editProfile = llm[key];
    }
    this.rerender();
  }
  /** New profile (copy): id p<N>, nameless, key — his (file will appear, when you save the key). */
  newProfile(kind, base) {
    const llm = this.llm();
    const profiles = llm.profiles;
    const ids = new Set(profiles.map((p2) => p2.id));
    let n = profiles.length + 1;
    while (ids.has(`p${n}`)) n++;
    const id = `p${n}`;
    const def = clone(this.info.profile_defaults?.[kind] || { kind, name: kind === "local" ? "Local model" : "Cloud model" });
    const p = base ? { ...clone(base), id } : { ...def, id, kind };
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
  profileUse(p, llm) {
    const out = [];
    if (llm.cloud_profile === p.id) out.push(llm.mode === "cloud" ? "main model" : "default cloud profile");
    if (llm.local_profile === p.id) out.push(llm.mode === "local" ? "main model" : "default local profile");
    const steps = Object.entries(llm.roles || {}).filter(([, v]) => v === p.id).map(([k]) => k);
    if (steps.length) out.push("steps: " + steps.join(", "));
    return out;
  }
  profileEditor(el) {
    const llm = this.llm();
    const profiles = llm.profiles;
    const box = el.createDiv({ cls: "vm-prof-editor" });
    const main = llm.mode === "local" ? llm.local_profile : llm.cloud_profile;
    const cur = profiles.find((p) => p.id === this.editProfile) || profiles.find((p) => p.id === main) || profiles[0];
    const s = new import_obsidian4.Setting(box).setName("Profile to edit").setDesc("Cloud profiles track prices and costs; local profiles track tokens and run time.");
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
    s.addButton((b) => b.setButtonText("\uFF0B Cloud").setTooltip("New cloud profile").onClick(() => {
      this.newProfile("cloud");
      this.rerender();
    }));
    s.addButton((b) => b.setButtonText("\uFF0B Local").setTooltip("New local language model profile (llama.cpp server)").onClick(() => {
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
    fbox.createDiv({ cls: "vm-prof-title", text: `${cur.name || cur.id} \xB7 ${PTYPE_RU[cur.kind] || cur.kind}` });
    fbox.createDiv({ cls: "vm-muted vm-small-text", text: used.length ? `Used by: ${used.join("; ")}.` : "Not currently in use. Select it above as the main profile or assign it to a step." });
    let pricesHead = false;
    for (const f of this.info.profile_fields || []) {
      if (f.kinds && !f.kinds.includes(cur.kind)) continue;
      if (f.group === "prices" && !pricesHead) {
        pricesHead = true;
        fbox.createDiv({ cls: "vm-prof-sub", text: "Prices and limit are used to calculate costs. Enter provider prices in dollars per million tokens." });
      }
      this.profileField(fbox, cur, f);
    }
  }
  profileField(el, prof, f) {
    const put = (v2) => {
      const live = this.liveProfile(prof.id);
      if (!live) return;
      setPath(live, f.key, v2);
      this.set("llm.profiles", this.llm().profiles);
    };
    const v = getPath(prof, f.key);
    const def = getPath(this.info.profile_defaults?.[prof.kind] || {}, f.key);
    switch (f.type) {
      case "text":
        return this.fieldText(el, f, v, put, f.key === "name" ? void 0 : def, f.key === "name" || f.key === "base_url" ? () => this.flush().then(() => this.rerender()) : void 0);
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
        new import_obsidian4.Setting(el).setName(f.label).setDesc(f.help);
    }
  }
  async deleteProfile(p) {
    if (this.llm().profiles.length <= 1) {
      new import_obsidian4.Notice("This is the only profile. Create another one first.", 6e3);
      return;
    }
    const used = this.profileUse(p, this.llm());
    const ok = await this.plugin.confirm({
      title: "Delete profile?",
      text: `Profile \u201C${p.name || p.id}\u201D will be deleted.` + (used.length ? ` It is currently used by ${used.join("; ")}. The first suitable profile will be selected instead; affected steps will use the main model.` : "") + " The key file will not be deleted. The profile's expense history remains on the panel's Expenses tab.",
      ok: "Delete",
      warning: true
    });
    if (!ok) return;
    const llm = this.llm();
    const profiles = llm.profiles;
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
  fieldRoles(el, f) {
    const llm = this.llm();
    const roles = llm.roles && typeof llm.roles === "object" ? llm.roles : llm.roles = {};
    const profiles = llm.profiles;
    const liveRoles = () => {
      const l = this.llm();
      if (!l.roles || typeof l.roles !== "object" || Array.isArray(l.roles)) l.roles = {};
      return l.roles;
    };
    if (f.help) el.createDiv({ cls: "setting-item-description vm-sec-help", text: f.help });
    for (const step of f.prompts || []) {
      const s = new import_obsidian4.Setting(el).setName(step).setDesc(f.prompt_help?.[step] || "");
      s.settingEl.addClass("vm-role");
      const v = typeof roles[step] === "string" ? roles[step] : "";
      if (v) s.settingEl.addClass("vm-changed");
      s.addDropdown((d) => {
        d.addOption("", "Same as main model");
        for (const p of profiles) d.addOption(p.id, `${p.name || p.id} (${PTYPE_RU[p.kind] || p.kind})`);
        d.addOption("webchat", "Manually via web chat");
        if (v && v !== "webchat" && !profiles.some((p) => p.id === v)) d.addOption(v, `${v} \u2014 Theres no profile.`);
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
        text: `Long material for ${f.split_prompts.join(", ")} is split according to the request limit of the profile assigned to each step.`
      });
  }
  fieldSources(el, f) {
    const list = Array.isArray(this.values.sources) ? this.values.sources : this.values.sources = [];
    if (f.help) el.createDiv({ cls: "setting-item-description vm-sec-help", text: f.help });
    list.forEach((src, i) => {
      const fixed = FIXED_SOURCES[String(src.name || "").toLowerCase()];
      const s = new import_obsidian4.Setting(el).setName(fixed ? String(src.name) : src.name ? `_staging/${src.name}` : "New source").setDesc(fixed || "_staging subfolder");
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
    new import_obsidian4.Setting(el).addButton((b) => b.setButtonText("Add source").onClick(() => {
      list.push({ name: "", color: "#64748b", compaction_shift: 0 });
      this.rerender();
    }));
  }
  // ---------- preservation ----------
  set(key, v) {
    if (!this.values) return;
    setPath(this.values, key, v);
    this.dirty.add(key);
    if (this.timer) window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.flush(), 900);
  }
  buildPatch() {
    const patch = {};
    for (const key of this.dirty) {
      let v = clone(getPath(this.values, key));
      if (key === "sources" && Array.isArray(v)) v = v.filter((s) => s && String(s.name || "").trim());
      if (key === "llm.profiles" && Array.isArray(v)) {
        const out = {};
        for (const p of v) {
          if (!p || !p.id) continue;
          const rest = { ...p };
          delete rest.id;
          out[p.id] = rest;
        }
        for (const o of this.info?.values?.llm?.profiles || []) if (o && o.id && !(o.id in out)) out[o.id] = null;
        v = out;
      }
      setPath(patch, key, v);
    }
    return patch;
  }
  /** Send accumulated changes to the program: Shell check them out and rewrite them. settings.yaml. */
  flush() {
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
        new import_obsidian4.Notice("Settings saved.", 2500);
        this.plugin.refreshState();
        const e = patch.embeddings;
        if (e && ("mode" in e || "base_url" in e) && this.llamaFresh && this.containerEl.isConnected) this.loadLlama();
      } else {
        const text = String(r.error || "Settings not saved.");
        const body = text.replace(/^Settings not saved:\s*/, "");
        this.errors = body.split(/;\s+/).filter(Boolean).map((t) => ({ text: t, tab: tabOfError(t) }));
        new import_obsidian4.Notice(text + " Saved values are shown.", 12e3);
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
};

// src/view.ts
var import_obsidian5 = require("obsidian");
var VIEW_TYPE = "vtoroy-mozg-panel";
var RUN_NAMES = {
  run: "Phase 1",
  synth: "Phase 2",
  revalidate: "Revalidation",
  patterns: "Patterns",
  advise: "Threshold advice",
  answer: "Answer question",
  check: "Check connection"
};
var TAB_TITLES = { overview: "Overview", questions: "Questions", container: "Container", usage: "Expenses", log: "Log" };
var PERIODS = [["today", "Today"], ["month", "This month"], ["prev_month", "Last month"], ["all", "All time"]];
var PERIOD_IN = { today: "today", month: "this month", prev_month: "last month", all: "all time" };
var FILE_WAIT = {
  await_structure: "pending approval of the structure",
  await_mode: "waiting for a decision on file mode",
  ready: "waiting to be processed",
  new: "waiting for the structure draft"
};
var BrainView = class extends import_obsidian5.ItemView {
  constructor(leaf, plugin) {
    super(leaf);
    this.plugin = plugin;
    this.tab = "overview";
    this.selectedId = null;
    this.follow = true;
    this.qFilter = null;
    this.freeText = /* @__PURE__ */ new Map();
    this.answerError = /* @__PURE__ */ new Map();
    this.thrDraft = /* @__PURE__ */ new Map();
    this.styleDraft = /* @__PURE__ */ new Map();
    this.openJobs = /* @__PURE__ */ new Set();
    this.renderPending = false;
    this.runEls = null;
    this.usagePeriod = "month";
    this.priceDraft = /* @__PURE__ */ new Map();
    this.budgetDraft = null;
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
    this.registerEvent(this.app.workspace.on("file-open", (f) => this.onFileOpen(f)));
    this.registerDomEvent(
      root,
      "focusout",
      () => window.setTimeout(() => {
        if (this.renderPending && !this.editing()) this.render();
      }, 150)
    );
    this.registerInterval(window.setInterval(() => this.tick(), 1e3));
    this.onFileOpen(this.app.workspace.getActiveFile());
    this.render();
  }
  async onClose() {
    this.plugin.views.delete(this);
  }
  // ---------- general ----------
  show(tab, containerId) {
    this.tab = tab;
    if (containerId !== void 0) {
      this.selectedId = containerId;
      if (containerId) this.follow = false;
    }
    this.renderPending = false;
    this.render(true);
  }
  editing() {
    const a = (this.contentEl.ownerDocument || document).activeElement;
    if (!a || !this.contentEl.contains(a)) return false;
    if (a.tagName === "TEXTAREA") return true;
    return a.tagName === "INPUT" && !["checkbox", "radio", "button"].includes(a.type);
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
      renderError(this.bodyEl, this.plugin, `panel, tab \xAB${TAB_TITLES[this.tab]}\xBB`, e);
    }
    this.contentEl.scrollTop = scroll;
  }
  onFileOpen(f) {
    if (!this.follow || !f) return;
    const c = containerOfPath(this.plugin.ui, f.path);
    if (c && c.id !== this.selectedId) {
      this.selectedId = c.id;
      if (this.tab === "container") this.render();
    }
  }
  byId(id) {
    if (!id) return null;
    return this.plugin.ui?.containers.find((c) => c.id === id) || null;
  }
  button(parent, text, onClick, kind, disabled = false) {
    const b = parent.createEl("button", { text, cls: kind === "cta" ? "mod-cta" : kind === "warning" ? "mod-warning" : "" });
    b.disabled = disabled;
    b.addEventListener("click", (ev) => {
      ev.preventDefault();
      onClick();
    });
    return b;
  }
  section(parent, title, extra) {
    const s = parent.createDiv({ cls: "vm-section" });
    const h = s.createDiv({ cls: "vm-section-title", text: title });
    if (extra) h.createSpan({ cls: "vm-muted vm-section-extra", text: extra });
    return s;
  }
  callout(parent, kind, title, text) {
    const c = parent.createDiv({ cls: `vm-callout is-${kind}` });
    if (title) c.createDiv({ cls: "vm-callout-title", text: title });
    if (text) c.createDiv({ text });
    return c;
  }
  dot(parent, color) {
    const d = parent.createSpan({ cls: "vm-dot" });
    if (color) d.style.backgroundColor = color;
    return d;
  }
  hookLinks(el) {
    el.querySelectorAll("a.internal-link").forEach(
      (a) => a.addEventListener("click", (ev) => {
        ev.preventDefault();
        const href = a.getAttribute("data-href") || a.getAttribute("href") || "";
        if (href) this.app.workspace.openLinkText(href, "", false);
      })
    );
  }
  // ---------- cap and current launch ----------
  renderHead() {
    const h = this.headEl;
    h.empty();
    const main = h.createDiv({ cls: "vm-head-main" });
    const t = main.createDiv({ cls: "vm-title" });
    (0, import_obsidian5.setIcon)(t.createSpan({ cls: "vm-logo" }), "brain");
    t.createSpan({ text: "Second Brain" });
    const p = this.plugin;
    const state = main.createDiv({ cls: "vm-state" });
    if (p.engine.problem()) state.setText("No connection to the program");
    else if (p.engine.busy()) state.setText("Running");
    else if (p.ui) state.setText(p.ui.status.questions ? `${nQuestions(p.ui.status.questions)} waiting` : "ready");
    const tools = h.createDiv({ cls: "vm-head-tools" });
    const r = tools.createDiv({ cls: "clickable-icon vm-icon-btn", attr: { "aria-label": "Refresh status" } });
    (0, import_obsidian5.setIcon)(r, "refresh-cw");
    r.addEventListener("click", () => p.refreshState(true));
    const s = tools.createDiv({ cls: "clickable-icon vm-icon-btn", attr: { "aria-label": "Plugin settings" } });
    (0, import_obsidian5.setIcon)(s, "settings");
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
          text: "Stopping: the program will finish the current step and save everything. If the model is slow to respond, this can take a few minutes."
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
          warning: true
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
  tick() {
    const r = this.runEls;
    const job = this.plugin.engine.active();
    if (!r || !job || r.job !== job) return;
    const now = Date.now();
    const info = liveInfo(job, now);
    const show = (e, text) => {
      e.setText(text);
      e.toggleClass("vm-hidden", !text);
    };
    const manual = manualMode(this.plugin.ui);
    r.time.setText(job.startedAt && !manual ? duration(now - job.startedAt) : "");
    show(r.stage, info.stage ? info.stage + (info.eta && !manual ? ` \xB7 ${info.eta}` : "") : "");
    r.barBox.toggleClass("vm-hidden", info.frac === null);
    r.spin.toggleClass("vm-hidden", info.frac !== null);
    if (info.frac !== null) r.bar.style.width = `${Math.round(info.frac * 1e3) / 10}%`;
    show(r.sub, info.sub);
    const ask = job.live.ask;
    show(r.ask, ask ? `The program is waiting for your answer.: \xAB${ask.title}\xBB \u2014 window open Obsidian.` : "");
    show(r.wait, !ask && info.wait !== null && info.wait >= 1500 ? `Were waiting for the model to respond.: ${duration(info.wait)}${info.waitWhat ? ` \xB7 ${info.waitWhat}` : ""}` : "");
    const u = job.live.usage;
    const local = job.live.last?.ptype === "local";
    show(r.usage, u && u.calls ? `This launch: ${usageLine(u, { time: local })}` : "");
    r.line.setText(job.lastLine || "Starting the program\u2026");
    if (r.kill) r.kill.toggleClass("vm-hidden", !(job.stopAt && now - job.stopAt > 2e4));
  }
  /** New line of output — update only the progress line, panelless. */
  progress() {
    this.tick();
  }
  renderTabs() {
    const el = this.tabsEl;
    el.empty();
    const q = this.plugin.ui?.status.questions || 0;
    const tabs = [["overview", "Overview", 0], ["questions", "Questions", q], ["container", "Container", 0], ["usage", "Expenses", 0], ["log", "Log", 0]];
    for (const [id, label, n] of tabs) {
      const t = el.createEl("button", { cls: "vm-tab" + (this.tab === id ? " is-active" : "") });
      t.createSpan({ text: label });
      if (n) t.createSpan({ cls: "vm-badge is-accent", text: String(n) });
      t.addEventListener("click", () => this.show(id));
    }
  }
  // ---------- Review ----------
  renderOverview(el) {
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
      const c = this.callout(el, "info", "Loading vault status\u2026", "On first opening, the program creates its working folders.");
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
  renderWizard(el, ui) {
    const p = this.plugin;
    const s = ui.status;
    const busy = p.engine.busy();
    const box = el.createDiv({ cls: "vm-card vm-wizard" });
    box.createDiv({ cls: "vm-card-title", text: "First import" });
    const waiting = Object.values(s.files).reduce((a, b) => a + b, 0);
    const hasFiles = s.staging_new > 0 || waiting > 0 || s.structure_pending;
    const draft = s.structure_pending && !!s.draft;
    const steps = [
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
        }
      },
      {
        title: "Phase 1 \u2014 structure draft",
        done: draft,
        body: (d) => {
          d.createDiv({ text: "The program will read the files and propose a tree of containers: projects, sprouts, and questions." });
          if (waiting) d.createDiv({ cls: "vm-muted", text: `Files read: ${waiting}.` });
          const b = d.createDiv({ cls: "vm-buttons" });
          this.button(b, "Start Phase 1", () => p.runPhase1(), "cta", busy);
        }
      },
      {
        title: "Review and approve the draft",
        done: false,
        body: (d) => {
          d.createDiv({ text: "Rename, merge, or remove containers directly in the draft. Once approved, the program will create folders and place entries in them as the next part of Phase 1." });
          const b = d.createDiv({ cls: "vm-buttons" });
          if (s.draft) this.button(b, "Open draft", () => p.open(s.draft));
          this.button(b, "Approve structure", () => p.approveStructure(), "cta", busy);
        }
      }
    ];
    const cur = steps.findIndex((x) => !x.done);
    steps.forEach((st, i) => {
      const row = box.createDiv({ cls: "vm-step " + (st.done ? "is-done" : i === cur ? "is-current" : "is-future") });
      row.createDiv({ cls: "vm-step-num", text: st.done ? "\u2713" : String(i + 1) });
      const body = row.createDiv({ cls: "vm-step-body" });
      body.createDiv({ cls: "vm-step-title", text: st.title });
      if (i === cur) st.body(body);
    });
    if (s.questions) {
      const q = this.callout(el, "accent", `Waiting for an answer: ${nQuestions(s.questions)}`, "For example, whether a file is a bulk import or a single entry.");
      this.button(q.createDiv({ cls: "vm-buttons" }), "Reply", () => this.show("questions"), "cta");
    }
  }
  renderAttention(el, ui) {
    const p = this.plugin;
    const s = ui.status;
    const busy = p.engine.busy();
    let n = 0;
    if (s.structure_pending && s.draft) {
      n++;
      const c = this.callout(el, "accent", "Draft structure awaits approval", "The program proposed changes to the structure. Open, edit, and approve the draft.");
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, "Open draft", () => p.open(s.draft));
      this.button(b, "Approve structure", () => p.approveStructure(), "cta", busy);
    }
    if (s.webchat_pending.length) {
      n++;
      const c = this.callout(el, "accent", "Waiting for a web chat response", null);
      for (const w of s.webchat_pending) {
        const row = c.createDiv({ cls: "vm-webchat" });
        row.createDiv({ text: `Step \u201C${w.prompt}\u201D: copy the entire request to the web chat, then paste the complete response into the answer file and save it.` });
        const b2 = row.createDiv({ cls: "vm-buttons" });
        this.button(b2, "Open the request", () => p.open(w.req));
        this.button(b2, "Open answer file", () => p.open(w.ans));
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
  renderActions(el, ui, wizard) {
    const p = this.plugin;
    const box = el.createDiv({ cls: "vm-actions" + (wizard ? " is-wizard" : "") });
    const has = ui.containers.length > 0;
    const s = ui.status;
    const running = !!p.engine.find((j) => j.args[0] === "run");
    if (!wizard)
      this.button(box, running ? "Phase 1 in progress\u2026" : "Phase 1: process new entries", () => p.runPhase1(), s.staging_new || s.pending_work ? "cta" : void 0, running);
    this.button(box, "New thought", () => p.newThought());
    this.button(box, "Phase 2: documents\u2026", () => p.pickContainer((c) => c && p.runSynth(c)), void 0, !has);
    this.button(box, "Revalidation\u2026", () => p.pickContainer((c) => p.runRevalidate(c), "All the containers."), void 0, !has);
    this.button(box, "Patterns", () => p.runPatterns(), void 0, !has);
    this.button(box, "Check connection", () => p.runCheck());
  }
  renderCounts(el, ui, wizard) {
    const s = ui.status;
    const files = Object.entries(s.files).filter(([k, v]) => v && FILE_WAIT[k]);
    const filesLine = () => {
      if (files.length) el.createDiv({ cls: "vm-muted vm-line", text: "Files: " + files.map(([k, v]) => `${FILE_WAIT[k]} \u2014 ${v}`).join(" \xB7 ") });
    };
    if (wizard) {
      filesLine();
      return;
    }
    const g = el.createDiv({ cls: "vm-stats" });
    const tile = (n, forms, onClick) => {
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
    if (s.entities || s.stages.queue || s.stages.quarantine) el.createDiv({ cls: "vm-muted vm-line", text: "Entries: " + parts.join(" \xB7 ") });
    filesLine();
  }
  renderWarnings(el, ui) {
    const list = [...new Set(ui.warnings || [])];
    if (!list.length) return;
    const s = this.section(el, "Warnings");
    for (const w of list) {
      const row = s.createDiv({ cls: "vm-warn" });
      row.createSpan({ cls: "vm-warn-mark", text: "!" });
      const t = row.createDiv({ cls: "vm-warn-text" });
      import_obsidian5.MarkdownRenderer.render(this.app, w, t, "", this).then(() => this.hookLinks(t));
    }
  }
  renderTree(el, ui) {
    const s = this.section(el, "Containers", "entries");
    for (const c of ui.containers) {
      const row = s.createDiv({ cls: "vm-tree-row" + (c.status !== "active" ? " is-muted" : "") + (c.id === this.selectedId ? " is-selected" : "") });
      row.style.paddingLeft = `${6 + c.depth * 16}px`;
      this.dot(row, c.color);
      row.createSpan({ cls: "vm-tree-title", text: c.title });
      if (c.type !== "project") row.createSpan({ cls: "vm-chip", text: c.type_ru });
      if (c.status !== "active") row.createSpan({ cls: "vm-chip is-muted", text: c.status_ru });
      const right = row.createSpan({ cls: "vm-tree-right" });
      if (c.dirty) right.createSpan({ cls: "vm-mark", text: "\u21BB", attr: { title: "Synthesis base needs to be rebuilt" } });
      if (c.questions) right.createSpan({ cls: "vm-badge is-accent", text: String(c.questions), attr: { title: nQuestions(c.questions) } });
      right.createSpan({ cls: "vm-tree-n", text: String(c.entities + c.shared) });
      row.addEventListener("click", () => this.show("container", c.id));
    }
  }
  /** Review: What model does the program work on and how much it cost this month?. */
  renderCurrent(el, ui) {
    const u = ui.usage;
    if (!u) return;
    const cur = u.current;
    const box = el.createDiv({ cls: "vm-card vm-current" });
    const head = box.createDiv({ cls: "vm-current-head" });
    const webchat = cur.mode === "webchat";
    head.createSpan({ cls: "vm-current-k", text: "Model:" });
    head.createSpan({ cls: "vm-current-name", text: webchat ? "manual web chat" : cur.name || "no profile selected" });
    if (cur.ptype && !webchat) head.createSpan({ cls: "vm-chip", text: PTYPE_RU[cur.ptype] || cur.ptype });
    const link = head.createEl("a", { cls: "vm-link vm-small-text vm-current-link", text: "Expenses \u2192" });
    link.addEventListener("click", () => this.show("usage"));
    if (!webchat && !cur.name) {
      const a = box.createEl("a", { cls: "vm-link vm-small-text", text: "Select a profile in settings" });
      a.addEventListener("click", () => this.plugin.openSettings("models"));
    }
    const t = cur.totals?.month;
    box.createDiv({
      cls: "vm-muted vm-small-text",
      text: t && t.calls ? `This month: ${usageLine(t, { time: cur.ptype === "local" })}${t.unpriced ? " (* some calls have no prices)" : ""}` : "This model has not been used this month."
    });
    const all = u.totals.month;
    if (all.calls && t && all.calls !== t.calls) box.createDiv({ cls: "vm-muted vm-small-text", text: `All models this month: ${usageLine(all)}` });
    if (u.budget.monthly_usd) this.budgetBar(box, u, false);
  }
  /** Budget band of the month: green, s 80% — yellow, scoot 100% — red. */
  budgetBar(parent, u, big) {
    const b = u.budget;
    if (!b.monthly_usd) return;
    const pct = b.pct ?? 0;
    const wrap = parent.createDiv({ cls: "vm-budget" + (big ? " is-big" : "") + (b.state ? ` is-${b.state}` : "") });
    const t = wrap.createDiv({ cls: "vm-budget-text" });
    t.createSpan({ text: `Monthly budget: ${money(b.spent)} of ${money(b.monthly_usd)}` });
    t.createSpan({ cls: "vm-budget-pct", text: ` \xB7 ${pctText(pct)}` });
    const bar = wrap.createDiv({ cls: "vm-bar" });
    bar.createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.min(100, pct)}%`;
    if (b.state === "over") wrap.createDiv({ cls: "vm-small-text", text: "Budget exhausted: before the next paid request, the program will stop and ask whether to continue." });
    else if (b.state === "warn") wrap.createDiv({ cls: "vm-small-text", text: `More than ${b.warn_pct}% of the budget has been spent.` });
  }
  // ---------- Expenses ----------
  renderUsageTab(el, ui) {
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
    const cell = (k, v, title) => {
      const c = g.createDiv({ cls: "vm-usage-cell", attr: title ? { title } : {} });
      c.createDiv({ cls: "vm-usage-v", text: v });
      c.createDiv({ cls: "vm-usage-k", text: k });
    };
    cell(plural(T.calls, ["request", "requests", "requests"]), num(T.calls));
    cell("input tokens", compact(T.in), T.cached ? `cached: ${num(T.cached)}` : void 0);
    cell("output tokens", compact(T.out));
    cell("model time", T.sec ? durationText(T.sec) : "\u2014", "Total time models spent generating responses across all requests");
    if (T.cached) card.createDiv({ cls: "vm-muted vm-small-text", text: `From the provider\u2019s cache: ${num(T.cached)} input tokens (lower cost).` });
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
      text: "Costs use profile prices at the time of each request and are stored in .system/usage.jsonl. Local models are free; their tokens and time are still recorded."
    });
  }
  renderBudgetEdit(el, u) {
    const p = this.plugin;
    const s = this.section(el, "Cloud model budget", "per month");
    if (u.budget.monthly_usd) this.budgetBar(s, u, true);
    else s.createDiv({ cls: "vm-muted vm-small-text", text: `No budget set. Spent this month: ${money(u.budget.spent)}.` });
    const row = s.createDiv({ cls: "vm-inline-form" });
    row.createSpan({ text: "Budget, $" });
    const inp = row.createEl("input", { type: "text", cls: "vm-num", attr: { inputmode: "decimal", placeholder: "No budget limit" } });
    inp.value = this.budgetDraft ?? (u.budget.monthly_usd != null ? String(u.budget.monthly_usd) : "");
    const save = this.button(row, "Save", async () => {
      const v = parseNumber(inp.value, "float", 0, 1e5);
      if (v === null) {
        inp.addClass("vm-invalid");
        new import_obsidian5.Notice("Enter a budget from 0 to 100000, or leave empty for no budget.");
        return;
      }
      save.disabled = true;
      const r = await p.patchSettings({ budget: { monthly_usd: v === void 0 || v === 0 ? null : v } });
      this.budgetDraft = null;
      if (r.ok) new import_obsidian5.Notice(v ? `Monthly budget: ${money(v)}. A warning appears at ${u.budget.warn_pct}%; at 100%, the program stops and asks whether to continue.` : "Budget removed.");
      else new import_obsidian5.Notice(r.error || "Budget not saved.", 12e3);
      this.render(true);
    });
    inp.addEventListener("input", () => {
      this.budgetDraft = inp.value;
      inp.removeClass("vm-invalid");
    });
    inp.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") save.click();
    });
    const note = s.createDiv({ cls: "vm-muted vm-small-text", text: `A warning appears at ${u.budget.warn_pct}%. At 100%, the program stops before the next paid request and asks whether to continue. Configure warning thresholds, large-run estimates, and profile limits ` });
    const a = note.createEl("a", { cls: "vm-link", text: "in settings" });
    a.addEventListener("click", () => this.plugin.openSettings("costs"));
    note.appendText(".");
  }
  renderProfiles(el, u, per) {
    const s = this.section(el, "Models", PERIOD_IN[per]);
    const list = u.profiles.filter((x) => x.exists || x.totals.all.calls);
    if (!list.length) s.createDiv({ cls: "vm-muted", text: "No profiles." });
    for (const pr of list) this.renderProfileCard(s, pr, per);
  }
  renderProfileCard(el, pr, per) {
    const p = this.plugin;
    const emb = pr.kind === "emb";
    const card = el.createDiv({ cls: "vm-card vm-prof" + (pr.exists ? "" : " is-muted") + (pr.active ? " is-active" : "") });
    const h = card.createDiv({ cls: "vm-prof-head" });
    h.createSpan({ cls: "vm-prof-name", text: emb ? `Embeddings \xB7 ${pr.model || pr.name}` : pr.name });
    if (pr.ptype) h.createSpan({ cls: "vm-chip", text: PTYPE_RU[pr.ptype] || pr.ptype });
    if (pr.active) h.createSpan({ cls: "vm-chip is-accent", text: "main" });
    if (!pr.exists) h.createSpan({ cls: "vm-chip is-muted", text: emb ? "previous model" : "profile removed" });
    const meta = [];
    if (pr.model && !emb) meta.push(pr.model);
    if (pr.steps.length) meta.push("steps: " + pr.steps.join(", "));
    if (meta.length) card.createDiv({ cls: "vm-muted vm-small-text", text: meta.join(" \xB7 ") });
    const t = pr.totals[per];
    card.createDiv({ cls: "vm-prof-usage", text: t.calls ? usageLine(t, { time: pr.ptype === "local", cost: pr.ptype === "cloud" }) : `No requests ${PERIOD_IN[per]}` });
    if (pr.budget_month) {
      const pct = pr.budget_pct ?? 0;
      const w = card.createDiv({ cls: "vm-budget" + (pr.budget_state ? ` is-${pr.budget_state}` : "") });
      w.createDiv({ cls: "vm-budget-text vm-small-text", text: `Profile limit: ${money(pr.totals.month.cost)} of ${money(pr.budget_month)} this month \xB7 ${pctText(pct)}` });
      w.createDiv({ cls: "vm-bar" }).createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.min(100, pct)}%`;
    }
    if (pr.ptype !== "cloud" || !pr.exists) return;
    const id = emb ? "emb" : pr.id;
    const draft = this.priceDraft.get(id) || {};
    const prices = pr.prices || { input: null, cached_input: null, output: null };
    const box = card.createDiv({ cls: "vm-prices" });
    box.createDiv({ cls: "vm-small-text vm-prices-title", text: "Prices, $ per million tokens" + (pr.priced ? "" : " \u2014 not set; cost is not calculated") });
    if (!pr.priced) box.addClass("is-unpriced");
    const fields = emb ? [["input", "input", prices.input]] : [["input", "input", prices.input], ["cached_input", "cached input", prices.cached_input], ["output", "output", prices.output]];
    const inputs = {};
    const row = box.createDiv({ cls: "vm-prices-row" });
    for (const [k, label, v] of fields) {
      const f = row.createDiv({ cls: "vm-price" });
      f.createDiv({ cls: "vm-muted vm-small-text", text: label });
      const inp = f.createEl("input", { type: "text", cls: "vm-num", attr: { inputmode: "decimal", placeholder: k === "cached_input" ? "same as input" : "\u2014" } });
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
      const out = {};
      for (const [k] of fields) {
        const v = parseNumber(inputs[k].value, "float", 0, 1e3);
        if (v === null) {
          inputs[k].addClass("vm-invalid");
          new import_obsidian5.Notice("Enter a price from 0 to 1000 dollars per million tokens.");
          return;
        }
        out[k] = v === void 0 ? null : v;
      }
      save.disabled = true;
      const patch = emb ? { embeddings: { price_input: out.input } } : { llm: { profiles: { [id]: { prices: out } } } };
      const r = await p.patchSettings(patch);
      if (!r.ok) {
        new import_obsidian5.Notice(r.error || "Prices not saved.", 12e3);
        save.disabled = false;
        return;
      }
      this.priceDraft.delete(id);
      new import_obsidian5.Notice(`Prices saved for ${emb ? "embeddings" : pr.name}.`);
      if (pr.totals.all.calls) {
        const ok = await p.confirm({
          title: "Recalculate past requests?",
          text: `${emb ? "Embeddings" : pr.name} already has ${nCalls(pr.totals.all.calls)}. Recalculate their cost using the new prices?

Otherwise, the new prices will apply from now on and past requests will retain their original calculated costs.`,
          ok: "Recalculate",
          cancel: "No"
        });
        if (ok) {
          const rr = await p.reprice(id);
          if (rr.ok) new import_obsidian5.Notice(rr.repriced ? `Cost recalculated for ${rr.repriced} requests.` : "There is nothing to recalculate; the cost has not changed.");
          else new import_obsidian5.Notice(rr.error || "Not recalculated.", 12e3);
        }
      }
      this.render(true);
    }, "cta");
  }
  renderSteps(el, u, per) {
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
      r.createDiv({ cls: "vm-td is-num", text: t.cost || t.unpriced ? money(t.cost) + (t.unpriced ? "*" : "") : "\u2014" });
    }
  }
  renderDays(el, u) {
    const days = u.days || [];
    if (!days.some((d) => d.calls)) return;
    const byCost = days.some((d) => d.cost > 0);
    const s = this.section(el, "By day", byCost ? "cost, last 31 days" : "requests, last 31 days");
    const max = Math.max(...days.map((d) => byCost ? d.cost : d.calls), byCost ? 1e-4 : 1);
    const chart = s.createDiv({ cls: "vm-chart" });
    for (const d of days) {
      const v = byCost ? d.cost : d.calls;
      const col = chart.createDiv({ cls: "vm-chart-col" + (d.date === u.today ? " is-today" : ""), attr: { title: `${ruDateTime(d.date)}: ${d.calls ? usageLine(d) : "No requests"}` } });
      const bar = col.createDiv({ cls: "vm-chart-bar" });
      bar.style.height = v ? `${Math.max(3, Math.round(v / max * 100))}%` : "0";
    }
    const lab = s.createDiv({ cls: "vm-chart-labels vm-muted vm-small-text" });
    lab.createSpan({ text: ruDateTime(days[0].date).slice(0, 5) });
    lab.createSpan({ text: `maximum: ${byCost ? money(max) : num(max)} per day` });
    lab.createSpan({ text: "today" });
  }
  renderRuns(el, u) {
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
  renderQuestions(el, ui) {
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
      chip.appendText(`\xAB${fc.title}\xBB \xD7`);
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
  renderQuestion(el, q) {
    const p = this.plugin;
    const job = p.engine.find((j) => j.args[0] === "answer" && j.args[1] === q.id);
    const card = el.createDiv({ cls: "vm-card vm-q" + (job ? " is-pending" : "") });
    const head = card.createDiv({ cls: "vm-q-head" });
    head.createDiv({ cls: "vm-q-title", text: q.title });
    head.createDiv({ cls: "vm-q-meta", text: q.id + (q.created ? ` \xB7 ${ruDateTime(q.created)}` : "") });
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
        a.addEventListener("click", () => p.open(q.entity_path));
      }
    }
    const text = card.createDiv({ cls: "vm-q-text markdown-rendered" });
    import_obsidian5.MarkdownRenderer.render(this.app, q.text, text, q.entity_path || "", this).then(() => this.hookLinks(text));
    if (q.note) card.createDiv({ cls: "vm-q-note", text: q.note });
    const err = this.answerError.get(q.id);
    if (err && err !== q.note) card.createDiv({ cls: "vm-q-note", text: err });
    if (job) card.createDiv({ cls: "vm-q-state", text: job.status === "queued" ? "Queued; will be applied after the current run\u2026" : "Applying answer\u2026" });
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
          new import_obsidian5.Notice("Enter an answer.");
          ta.focus();
          return;
        }
        this.answer(q, null, t);
      });
    }
  }
  async answer(q, option, text) {
    this.answerError.delete(q.id);
    const pr = this.plugin.answer(q, option, text);
    this.render(true);
    const r = await pr;
    if (r.ok && r.accepted) {
      this.freeText.delete(q.id);
      new import_obsidian5.Notice(`Answer ${q.id} accepted.`);
    } else this.answerError.set(q.id, r.note || r.error || "Answer not accepted.");
    this.render();
  }
  // ---------- Container ----------
  renderContainerTab(el, ui) {
    if (!ui || !ui.containers.length) {
      this.callout(el, "info", "No containers yet", "They will appear after the structure is approved.");
      return;
    }
    const bar = el.createDiv({ cls: "vm-cbar" });
    const sel = bar.createEl("select", { cls: "dropdown" });
    sel.createEl("option", { text: "\u2014 select a container \u2014", attr: { value: "" } });
    for (const c2 of ui.containers) sel.createEl("option", { text: "\xA0\xA0\xA0".repeat(c2.depth) + c2.title, attr: { value: c2.id } });
    sel.value = this.selectedId || "";
    sel.addEventListener("change", () => {
      this.follow = false;
      this.selectedId = sel.value || null;
      this.render(true);
    });
    const fb = bar.createEl("button", {
      cls: "vm-small" + (this.follow ? " is-active" : ""),
      text: this.follow ? "\u2713 follow open note" : "follow open note",
      attr: { title: "Show the container of the note open in the editor" }
    });
    fb.addEventListener("click", () => {
      this.follow = true;
      const f = this.app.workspace.getActiveFile();
      const c2 = f ? containerOfPath(ui, f.path) : null;
      if (c2) this.selectedId = c2.id;
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
  renderContainerHead(el, ui, c) {
    const p = this.plugin;
    const head = el.createDiv({ cls: "vm-card vm-chead" });
    head.style.borderLeftColor = c.color || "var(--interactive-accent)";
    const chain = parentsOf(ui, c);
    if (chain.length) head.createDiv({ cls: "vm-muted vm-small-text", text: chain.map((x) => x.title).join(" \u203A ") + " \u203A" });
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
    const fact = (k, v, onClick) => {
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
    if (c.views.pool) views.createEl("a", { cls: "vm-link", text: "pool" }).addEventListener("click", () => p.open(c.views.pool));
    if (c.views.base) views.createEl("a", { cls: "vm-link", text: "synthesis" }).addEventListener("click", () => p.open(c.views.base));
  }
  renderDocs(el, c) {
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
  renderThresholds(el, ui, c) {
    const p = this.plugin;
    const s = this.section(el, "Container thresholds");
    s.createDiv({
      cls: "vm-muted vm-small-text",
      text: "Custom values apply to this container and its children. Leave a field empty to inherit from the parent or use the global setting, shown in gray. Use \u21BA to remove a custom value."
    });
    const draft = this.thrDraft.get(c.id) || {};
    const names = Object.keys(ui.threshold_info).filter((k) => ui.threshold_info[k].per_container && (k !== "seed_dormancy_days" || c.type === "seed"));
    const table = s.createDiv({ cls: "vm-thr" });
    const inputs = {};
    let save;
    let reset;
    const collect = () => {
      const changes = {};
      const bad = [];
      for (const k of names) {
        const inp = inputs[k];
        const info = ui.threshold_info[k];
        const v = parseNumber(inp.value, info.kind, info.min, info.max);
        const own = c.overrides[k];
        inp.toggleClass("vm-invalid", v === null);
        if (v === null) bad.push(info.label);
        else if (v === void 0) {
          if (own !== void 0) changes[k] = null;
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
      let inherited = ui.thresholds[k];
      let inhFrom = null;
      const chain = parentsOf(ui, c);
      for (let i = chain.length - 1; i >= 0; i--) {
        const o = chain[i].overrides[k];
        if (o !== void 0) {
          inherited = o;
          inhFrom = chain[i].title;
          break;
        }
      }
      const row = table.createDiv({ cls: "vm-thr-row" + (own !== void 0 ? " is-own" : "") });
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
      inp.value = k in draft ? draft[k] : own !== void 0 ? String(own) : "";
      inp.placeholder = inherited != null ? String(inherited) : tv ? String(tv.value) : "";
      const resetTip = `Remove the custom threshold; use ${inhFrom ? `the value from \u201C${inhFrom}\u201D` : "the global value"} (${inherited})`;
      const rs = ctl.createEl("button", { cls: "vm-thr-reset", text: "\u21BA", attr: { title: resetTip } });
      inputs[k] = inp;
      const decimals = (String(rng.step).split(".")[1] || "").length;
      const sync = () => {
        const v = parseNumber(inp.value, info.kind, info.min, info.max);
        const empty = !inp.value.trim();
        rng.value = String(typeof v === "number" ? v : inherited ?? info.min);
        rng.toggleClass("is-inherited", empty);
        rs.disabled = empty;
        rs.toggleClass("vm-reset-off", empty);
        rs.setAttr("title", empty ? `No custom threshold; using ${inhFrom ? `the value from \u201C${inhFrom}\u201D` : "the global value"} (${inherited})` : resetTip);
        src.setText(!empty ? v === own ? "custom" : "custom, unsaved" : inhFrom ? `from \u201C${inhFrom}\u201D` : "global");
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
      inp.addEventListener("keydown", (ev) => {
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
        new import_obsidian5.Notice(`Thresholds saved for \u201C${c.title}\u201D; they apply from the next Phase 1 run.`);
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
      text: "Placement and compaction thresholds apply to new entries. Value thresholds rebuild the synthesis base on the next Phase 1 run without model requests."
    });
  }
  renderStyle(el, c) {
    const p = this.plugin;
    const s = this.section(el, "Document style");
    const inherited = !c.style && c.style_effective ? `Inherited style from \u201C${c.style_from}\u201D: ${c.style_effective}` : "For example: Write in English as a business plan, with figures and deadlines.";
    const ta = s.createEl("textarea", { cls: "vm-style", attr: { rows: "3", placeholder: inherited } });
    ta.value = this.styleDraft.get(c.id) ?? c.style;
    const b = s.createDiv({ cls: "vm-buttons" });
    const save = this.button(b, "Save style", async () => {
      save.disabled = true;
      const ok = await p.saveStyle(c, ta.value.trim());
      if (ok) {
        this.styleDraft.delete(c.id);
        new import_obsidian5.Notice(`Style saved for \u201C${c.title}\u201D; it applies to the next Phase 2 run.`);
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
      text: "Added to and takes precedence over the global style in settings. Also applies to child containers unless they have their own style."
    });
  }
  // ---------- Journal ----------
  renderLog(el, ui) {
    const p = this.plugin;
    const eng = p.engine;
    const logs = this.section(el, "Logs of the program");
    const lb = logs.createDiv({ cls: "vm-buttons" });
    const L = ui?.logs || {};
    if (L.changes) this.button(lb, "Change log", () => p.open(L.changes));
    if (L.reasoning) this.button(lb, "Model reasoning", () => p.open(L.reasoning));
    if (L.archive) this.button(lb, "Archive of questions", () => p.open(L.archive));
    if (L.errors) this.button(lb, "Errors", () => p.open(L.errors));
    this.button(lb, "open-questions.md", () => p.open("open-questions.md"));
    const s = this.section(el, "Runs in this session");
    const jobs = [];
    if (eng.current && !eng.current.quiet) jobs.push(eng.current);
    jobs.push(...eng.pending(), ...eng.history);
    if (!jobs.length) {
      s.createDiv({ cls: "vm-muted", text: "No runs yet." });
      return;
    }
    const icon = { queued: "\u29D7", running: "\u25B6", done: "\u2713", failed: "\u2717", stopped: "\u25A0", cancelled: "\u2013" };
    for (const j of jobs) {
      const card = s.createDiv({ cls: `vm-job is-${j.status}` });
      const h = card.createDiv({ cls: "vm-job-head" });
      h.createSpan({ cls: "vm-job-icon", text: icon[j.status] || "" });
      h.createSpan({ cls: "vm-job-label", text: j.label });
      const when = j.startedAt ? clock(j.startedAt) : clock(j.queuedAt);
      const dur = j.startedAt ? duration((j.finishedAt || Date.now()) - j.startedAt) : "queued";
      h.createSpan({ cls: "vm-muted vm-job-time", text: `${when} \xB7 ${dur}` });
      const r = j.result;
      if (r) {
        const sl = statsLine(r.stats);
        if (r.unchanged) card.createDiv({ text: "Documents are up to date; nothing was rewritten." });
        else if (r.title && r.ok) card.createDiv({ text: r.title + (sl ? ` \u2014 ${sl}` : "") });
        if (r.error) card.createDiv({ cls: "vm-job-error", text: r.error });
        const cl = callsLine(r.calls);
        if (cl) card.createDiv({ cls: "vm-muted vm-small-text", text: cl });
        const ru = r.run_usage;
        if (ru && ru.calls) {
          const extra = [ru.cost ? money(ru.cost) + (ru.unpriced ? "*" : "") : "", ru.sec ? `model time ${durationText(ru.sec)}` : "", r.elapsed ? `run ${durationText(r.elapsed)}` : ""].filter(Boolean);
          card.createDiv({ cls: "vm-muted vm-small-text", text: `Tokens ${compact(ru.in)} \u2192 ${compact(ru.out)}` + (extra.length ? " \xB7 " + extra.join(" \xB7 ") : "") });
        }
        for (const w of r.warnings || []) card.createDiv({ cls: "vm-small-text vm-warn-line", text: "! " + w });
        for (const n of r.notices || []) card.createDiv({ cls: "vm-small-text vm-muted", text: "\u2022 " + n });
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
          const text = [`$ brain ${j.args.join(" ")}`, ...j.lines.slice(-400)].join("\n") + (j.stderr ? `
--- stderr ---
${j.stderr.slice(-4e3)}` : "");
          card.createEl("pre", { cls: "vm-pre", text });
        }
      }
    }
  }
};

// src/main.ts
var DEFAULTS = {
  programDir: "",
  pythonPath: "",
  welcomed: false,
  notify: true,
  notifyMinutes: 2,
  notifyAsk: true,
  notifyUnfocused: true,
  skipVersion: ""
};
var INTERACTIVE = /* @__PURE__ */ new Set(["run", "synth", "revalidate", "patterns", "advise", "answer"]);
function newerVersion(a, b) {
  const ta = String(a || "").match(/\d+/g)?.slice(0, 4).map(Number) || [0];
  const tb = String(b || "").match(/\d+/g)?.slice(0, 4).map(Number) || [0];
  for (let i = 0; i < Math.max(ta.length, tb.length); i++) {
    const x = ta[i] || 0;
    const y = tb[i] || 0;
    if (x !== y) return x > y;
  }
  return false;
}
var UI_FILE = ".system/ui.json";
var APPROVE = "Structure approved";
var BrainPlugin = class extends import_obsidian6.Plugin {
  constructor() {
    super(...arguments);
    this.data = { ...DEFAULTS };
    this.ui = null;
    this.snapshotError = null;
    this.views = /* @__PURE__ */ new Set();
    this.advice = /* @__PURE__ */ new Map();
    this.lastWebchat = null;
    this.uiMtime = 0;
    this.statusEl = null;
  }
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
      new import_obsidian6.Notice(`${job.label}: ${text}`, 12e3);
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
  catchErrors() {
    const mark = "plugin:" + encodeURIComponent(this.manifest.id);
    const mine = (e, file) => errParts(e).stack.includes(mark) || String(file || "").includes(mark);
    this.registerDomEvent(window, "error", (ev) => {
      if (mine(ev.error, ev.filename)) this.errors.add("Unhandled error", ev.error || ev.message, true);
    });
    this.registerDomEvent(window, "unhandledrejection", (ev) => {
      if (mine(ev.reason)) this.errors.add("Unhandled error", ev.reason, true);
    });
  }
  async start() {
    await this.readSnapshot(true);
    this.refresh();
    if (!this.data.welcomed) {
      this.data.welcomed = true;
      await this.saveData(this.data);
      this.openView();
    }
    if (!this.engine.problem()) await this.refreshState(true);
    this.registerInterval(window.setInterval(() => this.readSnapshot(false), 3e3));
    this.registerInterval(window.setInterval(() => this.updateStatus(), 1e3));
    window.setTimeout(() => this.startupChecks(), 3e3);
  }
  // ---------- update ----------
  /** At launch. Obsidian: new version of the plugin in the program folder? new version of the program GitHub? */
  async startupChecks() {
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
  async programPluginVersion() {
    const dir = this.engine.programDir();
    if (!dir) return null;
    try {
      const raw = await fs3.promises.readFile(path2.join(dir, "plugin", "manifest.json"), "utf8");
      return String(JSON.parse(String(raw)).version || "") || null;
    } catch {
      return null;
    }
  }
  /** In the program folder, the plugin is newer than the installed — offer to put it in storage. */
  async offerPluginFromProgram() {
    const v = await this.programPluginVersion();
    if (!v || !newerVersion(v, this.manifest.version)) return false;
    const ch = await choiceModal(this.app, {
      title: "New version of the plugin",
      text: `The program folder contains plugin version ${v}; Obsidian is running ${this.manifest.version}. Install the new version? Plugin settings will be preserved. Obsidian must be restarted afterward.`,
      options: [{ label: "Install", kind: "cta" }, { label: "Later" }]
    }).result;
    if (ch !== 0) return true;
    const r = await this.engine.run(["install-plugin", this.engine.vaultPath()], { label: "Installing plugin" });
    if (!r.ok) {
      new import_obsidian6.Notice(`Plugin not installed: ${r.error || "error"}`, 15e3);
      return true;
    }
    await this.offerRestart(`Plugin ${v} installed.`);
    return true;
  }
  /** Check the new version of the program on GitHub; manual — button-button (report «last»). */
  async checkUpdates(manual) {
    const prob = this.engine.problem();
    if (prob) {
      if (manual) new import_obsidian6.Notice(prob, 1e4);
      return;
    }
    const r = await this.engine.run(["update", "--check"], { label: "Checking for updates", exclusive: false, quiet: true });
    if (!r.ok || !r.update) {
      if (manual) new import_obsidian6.Notice(`Verification of updates: ${r.error || "program did not respond"}`, 12e3);
      else console.warn("Second Brain: checking for updates \u2014", r.error);
      return;
    }
    const u = r.update;
    if (!u.newer) {
      if (manual) new import_obsidian6.Notice(`The latest version has been installed: ${u.current} (repository ${u.repo} \u2014 ${u.version || "?"}).`, 8e3);
      return;
    }
    if (!manual && this.data.skipVersion && this.data.skipVersion === u.version) return;
    const notes = (u.notes || "").split("\n").slice(0, 40).join("\n").trim();
    const from = u.source === "release" ? `release ${u.tag || u.version}` : `branch ${u.branch || "main"}`;
    const ch = await choiceModal(this.app, {
      title: `New version available: ${u.version}`,
      sub: `${u.repo} \xB7 ${from}`,
      text: `Currently installed: ${u.current}. The update replaces program and plugin files; settings, keys, and the vault are unchanged. If modified prompts differ from the new version, your copies will be saved in prompts/_former.`,
      pre: notes || void 0,
      options: [{ label: "Install", kind: "cta" }, { label: "Later" }, { label: "Skip this version" }]
    }).result;
    if (ch === 2) {
      this.data.skipVersion = u.version || "";
      await this.saveData(this.data);
      new import_obsidian6.Notice(`Version ${u.version} skipped. To check manually, open Settings \u2192 Second Brain \u2192 Updates.`, 8e3);
    } else if (ch === 0) await this.installUpdate(u);
  }
  async installUpdate(u) {
    if (this.engine.busy()) new import_obsidian6.Notice("The update will start after the current run.", 6e3);
    const r = await this.engine.run(["update", "--yes"], { label: `Update to ${u.version}` });
    if (!r.ok) {
      new import_obsidian6.Notice(`Update not installed: ${r.error || "error"}`, 15e3);
      return;
    }
    const inst = r.installed;
    if (!inst) {
      new import_obsidian6.Notice(r.title || "Nothing to update.", 8e3);
      return;
    }
    await this.refreshState(true);
    const lines = [`Files updated: ${inst.updated}, added: ${inst.added}` + (inst.removed.length ? `, obsolete: ${inst.removed.length}` : "") + "."];
    for (const n of inst.notes || []) lines.push(n);
    if (r.restart) await this.offerRestart(`Version ${inst.version} installed.`, lines);
    else
      await choiceModal(this.app, {
        title: `Version ${inst.version} installed`,
        lines,
        text: "The plugin was not found in this vault. If it is installed in another vault, run Install.bat and select this one.",
        options: [{ label: "Done", kind: "cta" }]
      }).result;
  }
  /** Window. «restart Obsidian» — The new plugin will work after restarting. */
  async offerRestart(title, lines) {
    const ch = await choiceModal(this.app, {
      title,
      lines,
      text: "Restart Obsidian to use the new plugin. Open notes have been saved.",
      options: [{ label: "Restart Obsidian", kind: "cta" }, { label: "Later" }]
    }).result;
    if (ch === 0) {
      const cmds = this.app.commands;
      if (!cmds?.executeCommandById?.("app:reload")) window.location.reload();
    }
  }
  // ---------- Questions in the midst of launch and notification Windows ----------
  askUser(job, ask) {
    this.osNotify("Second Brain is waiting for an answer", `${job.label}: ${ask.title}`, "ask");
    const m = choiceModal(this.app, { ...askOptions(ask), sub: job.label });
    job.askCancel = m.close;
    this.refresh();
    return m.result;
  }
  /** What?-window Obsidian now in focus: principal, tab-window, settings-box (Obsidian 1.15+). */
  obsidianFocused() {
    const docs = /* @__PURE__ */ new Set([document]);
    try {
      const ad = window.activeDocument;
      if (ad) docs.add(ad);
      const sd = this.brainTab?.containerEl?.ownerDocument;
      if (sd) docs.add(sd);
      this.app.workspace.iterateAllLeaves((leaf) => {
        const d = leaf.view?.containerEl?.ownerDocument;
        if (d) docs.add(d);
      });
    } catch {
    }
    for (const d of docs) {
      try {
        if (d.hasFocus()) return true;
      } catch {
      }
    }
    return false;
  }
  /** Notification Windows (systemic). force — check-up: conditionally. */
  osNotify(title, body, kind, force = false) {
    const d = this.data;
    if (!force) {
      if (!d.notify) return false;
      if (kind === "ask" && !d.notifyAsk) return false;
      if (d.notifyUnfocused && this.obsidianFocused()) return false;
    }
    const N = window.Notification;
    if (typeof N !== "function") return false;
    try {
      const n = new N(title, { body, silent: kind === "notice" });
      n.onclick = () => {
        try {
          window.focus();
        } catch {
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
  doneNotify(label, r, sec) {
    if (r.cancelled) return;
    if (sec < Math.max(0, this.data.notifyMinutes) * 60) return;
    let body;
    if (r.webchat) body = "Waiting for a web chat response; see the panel.";
    else if (r.budget_stop) body = "Stopped.: budget exhausted.";
    else if (r.stopped) body = "Stopped. All processed items are saved.";
    else if (!r.ok) body = `Mistake.: ${r.error || "see panel"}`;
    else {
      const sl = statsLine(r.stats);
      body = `${r.title || "Done"} after ${durationText(sec)}` + (sl ? `: ${sl}` : "") + (r.run_usage?.cost ? ` \xB7 ${money(r.run_usage.cost)}` : "") + ".";
      if (r.questions) body += ` Questions: ${r.questions}.`;
    }
    this.osNotify(`Second Brain \xB7 ${label}`, body, "done");
  }
  // ---------- condition ----------
  async readSnapshot(force) {
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
      this.ui = JSON.parse(raw);
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
  updateStatus() {
    const el = this.statusEl;
    if (!el) return;
    const prob = this.engine.problem();
    const job = this.engine.active();
    if (prob) {
      el.setText("Second Brain: program not found");
      el.setAttr("title", prob);
    } else if (job) {
      const manual = manualMode(this.ui);
      const t = job.startedAt && !manual ? duration(Date.now() - job.startedAt) : "";
      const q = this.engine.pending().length;
      const info = liveInfo(job);
      const parts = [`Second Brain \xB7 ${job.label}`];
      const s0 = job.live.stages[0];
      if (s0) parts.push(s0.unit === "%" ? `${s0.n}%` : s0.total > 0 ? `${s0.n} from ${s0.total}` : s0.stage);
      if (job.live.ask) parts.push("awaiting your answer");
      else if (info.wait !== null && info.wait >= 3e3) parts.push(`waiting for an answer ${duration(info.wait)}`);
      else if (info.eta && !manual) parts.push(info.eta);
      if (t) parts.push(t);
      el.setText(parts.join(" \xB7 ") + (q ? ` (+${q})` : ""));
      el.setAttr("title", [info.stage, info.sub, job.lastLine].filter(Boolean).join("\n") || job.label);
    } else {
      const n = this.ui?.status.questions || 0;
      el.setText(n ? `Second Brain \xB7 ${nQuestions(n)}` : "Second Brain");
      el.setAttr("title", "Open Second Brain panel");
    }
  }
  async openView(tab, containerId) {
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
  openSettings(tab) {
    if (tab) this.brainTab.openTab(tab);
    const s = this.app.setting;
    if (s) {
      s.open();
      s.openTabById(this.manifest.id);
    }
  }
  confirm(o) {
    return confirmModal(this.app, o);
  }
  // ---------- launches ----------
  async job(args, label, notify = true) {
    const t0 = Date.now();
    const r = await this.engine.run(args, { label, interactive: INTERACTIVE.has(args[0]) });
    this.doneNotify(label, r, r.elapsed ?? (Date.now() - t0) / 1e3);
    await this.readSnapshot(true);
    if (r.webchat) this.lastWebchat = { label, args };
    else if (r.ok && this.lastWebchat && this.lastWebchat.args.join("\0") === args.join("\0")) this.lastWebchat = null;
    if (notify) this.notify(label, r);
    this.refresh();
    return r;
  }
  notify(label, r) {
    if (r.webchat) new import_obsidian6.Notice(`${label}: waiting for a web chat response \u2014 see the Second Brain panel.`, 1e4);
    else if (r.cancelled) new import_obsidian6.Notice(`${label}: cancelled \u2014 nothing changed.`, 6e3);
    else if (r.budget_stop) {
      const why = (r.notices || []).find((n) => n.startsWith("Stopped:")) || "Stopped: budget exhausted. All processed items are saved.";
      new import_obsidian6.Notice(`${label}: ${lcFirst(why)}`, 2e4);
    } else if (r.ok) {
      const sl = statsLine(r.stats);
      let msg = `${label}: ${lcFirst(r.title || "ready")}${sl ? " \u2014 " + sl : ""}.`;
      const u = r.run_usage;
      if (u && u.calls) msg += ` Requests: ${u.calls}${u.cost ? `, ${money(u.cost)}` : ""}${r.elapsed ? `, ${durationText(r.elapsed)}` : ""}.`;
      if (r.questions) msg += ` Open questions: ${r.questions}.`;
      if (r.warnings?.length) msg += ` Warnings: ${r.warnings.length} \u2014 see panel.`;
      new import_obsidian6.Notice(msg, 8e3);
    } else if (r.stopped) new import_obsidian6.Notice(`${label}: stopped. Processed items are saved; the next run will continue.`, 8e3);
    else new import_obsidian6.Notice(`${label}: ${r.error || "error"}`, 15e3);
  }
  runPhase1() {
    return this.job(["run"], "Phase 1");
  }
  async runSynth(c, force = false) {
    const label = `Phase 2 \xB7 ${c.title}`;
    const r = await this.job(["synth", c.id, ...force ? ["--force"] : []], label, false);
    if (r.ok && r.unchanged && !force) {
      const ok = await this.confirm({
        title: "Documents are up to date",
        text: `The synthesis base for ${c.title} has not changed since the last document run.

Rewrite the documents anyway? This requires model requests.`,
        ok: "Rewrite"
      });
      return ok ? this.runSynth(c, true) : r;
    }
    this.notify(label, r);
    return r;
  }
  /** Revalidation: The program will count the records and ask for confirmation. (time- and cost-estimated). */
  async runRevalidate(c) {
    const r = await this.job(["revalidate", ...c ? [c.id] : []], c ? `Revalidation \xB7 ${c.title}` : "Revalidate all entries", false);
    if (r.ok && !r.cancelled && !r.count) new import_obsidian6.Notice(c ? `There are no processed entries to recheck in \u201C${c.title}\u201D.` : "There are no processed entries to recheck.");
    else this.notify(c ? `Revalidation \xB7 ${c.title}` : "Revalidation", r);
  }
  /** Adjust program settings from the panel (price, budget): program settings.yaml. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async patchSettings(patch) {
    const r = await this.engine.run(["settings", "--set-json", "-"], { label: "Saving settings", stdin: JSON.stringify(patch), exclusive: false, quiet: true });
    if (r.ok) await this.refreshState(true);
    return r;
  }
  /** Calculate the cost of past profile calls at current prices (expense-book — common-line). */
  async reprice(key) {
    const r = await this.engine.run(["usage", "--reprice", key], { label: "Recalculate costs" });
    await this.refreshState(true);
    return r;
  }
  async runPatterns() {
    const ok = await this.confirm({
      title: "Find patterns",
      text: "The program will look in each container for groups of related aspects of different types not covered by an existing composite type, and suggest new types. It makes one model request for all groups found; if none are found, no request is made.",
      ok: "Find"
    });
    if (ok) await this.job(["patterns"], "Patterns");
  }
  runCheck() {
    new CheckModal(this).open();
  }
  // ---------- jelly-fish (llama.cpp) ----------
  /** Is the model downloaded?, assemblies llama.cpp eat, Is the server working?; hw — computer hardware. */
  async llamaStatus(hw = false) {
    if (this.engine.problem()) return null;
    const r = await this.engine.run(["llama", "status", ...hw ? ["--hw"] : []], { label: "Embedding model", exclusive: false, quiet: true });
    return r.ok && r.llama ? r.llama : null;
  }
  /** Run the model with parameters from the window «Run the model…»: need — leap (move — panel, «Stop.» —
   *  interrupt: The download will continue next time.), The server address will be entered into the settings itself. */
  async runLlamaStart(params) {
    const label = "Starting embedding model";
    const t0 = Date.now();
    const r = await this.engine.run(["llama", "start", "--params-json", "-"], { label, stdin: JSON.stringify(params) });
    this.doneNotify(label, r, (Date.now() - t0) / 1e3);
    const s = r.server;
    if (r.ok && s) {
      if (s.already) new import_obsidian6.Notice(`The model is already running with these settings: ${s.url}`, 8e3);
      else if (s.foreign) new import_obsidian6.Notice(`A server for this model is already running on port ${s.port}; the program will use it.`, 1e4);
      else new import_obsidian6.Notice(`Model running: ${s.url}${s.load_sec ? ` (loaded ${durationText(s.load_sec)})` : ""}. Address saved in settings.`, 1e4);
    } else if (r.stopped) new import_obsidian6.Notice("Model startup stopped. An interrupted download will resume on the next run.", 1e4);
    else new import_obsidian6.Notice(`Model not started: ${r.error || "error"}`, 2e4);
    await this.refreshState(true);
    this.brainTab.reload();
    return r;
  }
  /** Stop the model server (memory). The program will run it again on its own., whenever you need it. */
  async runLlamaStop() {
    const r = await this.engine.run(["llama", "stop"], { label: "Stopping embedding model", exclusive: false, quiet: true });
    if (!r.ok) new import_obsidian6.Notice(`Model not stopped: ${r.error || "error"}`, 12e3);
    else new import_obsidian6.Notice(r.title === "Server stopped" ? "Embedding model stopped; memory released." : "The embedding model is not running.", 8e3);
    return r;
  }
  continueWebchat() {
    const w = this.lastWebchat;
    return w ? this.job(w.args, w.label) : this.runPhase1();
  }
  answer(q, option, text) {
    const args = ["answer", q.id, option !== null ? `--option=${option}` : `--text=${text || ""}`];
    return this.job(args, `Answer. ${q.id}`, false);
  }
  async approveStructure() {
    const draft = this.ui?.status.draft || "_structure (draft).md";
    const ok = await this.confirm({
      title: "Approve structure?",
      text: "The program will create containers from the draft, including your edits, and place entries in them. This requires model requests for each entry.",
      ok: "Approve and continue"
    });
    if (!ok) return;
    for (const leaf of this.app.workspace.getLeavesOfType("markdown")) {
      const v = leaf.view;
      if (v instanceof import_obsidian6.MarkdownView && v.file?.path === draft) await v.save();
    }
    const r = await this.engine.local("Approving structure", async () => {
      const f = this.app.vault.getAbstractFileByPath(draft);
      if (!(f instanceof import_obsidian6.TFile)) throw new Error(`no draft file \xAB${draft}\xBB`);
      await this.app.vault.process(f, (text) => markApproved(text));
    });
    if (!r.ok) {
      new import_obsidian6.Notice(`Could not mark the draft as approved: ${r.error}`, 1e4);
      return;
    }
    new import_obsidian6.Notice("Structure approved; creating containers and placing entries\u2026");
    await this.runPhase1();
  }
  // ---------- AI ----------
  openAdvice(c, ready) {
    new AdviceModal(this, c, ready).open();
  }
  async adviseNow(c) {
    const label = `Threshold Council \xB7 ${c.title}`;
    const r = await this.job(["advise", c.id], label, false);
    if (r.ok && r.advice) {
      this.advice.set(c.id, { advice: r.advice, at: localIso() });
      this.refresh();
    } else this.notify(label, r);
    return r;
  }
  forgetAdvice(cid) {
    this.advice.delete(cid);
    this.refresh();
  }
  // ---------- editing YAML container (common-line, off-road) ----------
  async editFrontmatter(c, label, fn) {
    if (this.engine.busy()) new import_obsidian6.Notice("The program is running. The change will be saved immediately after the current run.");
    const r = await this.engine.local(label, async () => {
      const f = this.app.vault.getAbstractFileByPath(c.path);
      if (!(f instanceof import_obsidian6.TFile)) throw new Error(`No container file found \xAB${c.path}\xBB`);
      await this.app.fileManager.processFrontMatter(f, fn);
    });
    if (!r.ok) {
      new import_obsidian6.Notice(`Could not save: ${r.error}`, 1e4);
      return false;
    }
    this.refreshState(true);
    return true;
  }
  saveThresholds(c, changes) {
    const aliases = this.ui?.threshold_aliases || {};
    return this.editFrontmatter(c, `Thresholds \xB7 ${c.title}`, (fm) => {
      const old = fm.thresholds;
      const t = old && typeof old === "object" && !Array.isArray(old) ? { ...old } : {};
      for (const [name, v] of Object.entries(changes)) {
        for (const k of Object.keys(t)) {
          const norm = k.trim().toLowerCase().replace(/ /g, "_");
          if (k !== name && (norm === name || aliases[norm] === name)) delete t[k];
        }
        if (v === null) delete t[name];
        else t[name] = v;
      }
      if (Object.keys(t).length) fm.thresholds = t;
      else delete fm.thresholds;
    });
  }
  saveStyle(c, text) {
    return this.editFrontmatter(c, `Style. \xB7 ${c.title}`, (fm) => {
      if (text) fm.style = text;
      else delete fm.style;
    });
  }
  async setContainerField(c, key, value, what) {
    const ok = await this.editFrontmatter(c, `${c.title}: ${what}`, (fm) => {
      fm[key] = value;
    });
    if (ok) new import_obsidian6.Notice(`${what} in \u201C${c.title}\u201D. The program will apply this on the next Phase 1 run.`);
  }
  // ---------- thought ----------
  newThought(hint = "") {
    new NewThoughtModal(this, hint).open();
  }
  async saveThought(text, hint, dateIso, source) {
    const { name, body } = thoughtFile(text, hint, dateIso);
    const folder = source && source !== "note" ? `_staging/${source}` : "_staging";
    const a = this.app.vault.adapter;
    if (!await a.exists(folder)) await a.mkdir(folder);
    let p = `${folder}/${name}`;
    for (let i = 2; await a.exists(p); i++) p = `${folder}/${name.replace(/\.txt$/, ` (${i}).txt`)}`;
    await a.write(p, body);
    this.refreshState();
    return p;
  }
  // ---------- file ----------
  async open(rel) {
    const f = this.app.vault.getAbstractFileByPath(rel);
    if (f instanceof import_obsidian6.TFile && f.extension === "md") {
      await this.app.workspace.getLeaf(false).openFile(f);
      return;
    }
    try {
      const text = await this.app.vault.adapter.read(rel);
      new TextModal(this.app, baseName(rel), text).open();
    } catch {
      new import_obsidian6.Notice(`File not found: ${rel}`);
    }
  }
  async revealFolder(rel) {
    const a = this.app.vault.adapter;
    if (!await a.exists(rel)) await a.mkdir(rel);
    this.revealPath(path2.join(this.engine.vaultPath(), rel));
  }
  revealPath(abs, isFile = false) {
    try {
      const { shell } = require("electron");
      if (isFile) shell.showItemInFolder(abs);
      else shell.openPath(abs);
    } catch {
      new import_obsidian6.Notice(`Open it manually: ${abs}`, 1e4);
    }
  }
  pickContainer(cb, allLabel) {
    if (!this.ui?.containers.length) {
      new import_obsidian6.Notice("No containers yet; approve the structure first.");
      return;
    }
    new ContainerPicker(this, allLabel || null, cb).open();
  }
  containerOfActive() {
    const f = this.app.workspace.getActiveFile();
    return f ? containerOfPath(this.ui, f.path) : null;
  }
  // ---------- team ----------
  addCommands() {
    this.addCommand({ id: "open-panel", name: "Open panel", callback: () => this.openView() });
    this.addCommand({ id: "run", name: "Phase 1: process new entries", callback: () => this.runPhase1() });
    this.addCommand({ id: "new-thought", name: "New thought", callback: () => this.newThought() });
    this.addCommand({ id: "questions", name: "Answer questions", callback: () => this.openView("questions") });
    this.addCommand({ id: "synth", name: "Phase 2: write documents\u2026", callback: () => this.pickContainer((c) => c && this.runSynth(c)) });
    this.addCommand({
      id: "synth-current",
      name: "Phase 2 for the open note's container",
      checkCallback: (checking) => {
        const c = this.containerOfActive();
        if (!c) return false;
        if (!checking) this.runSynth(c);
        return true;
      }
    });
    this.addCommand({
      id: "container-current",
      name: "Show the open note's container",
      checkCallback: (checking) => {
        const c = this.containerOfActive();
        if (!c) return false;
        if (!checking) this.openView("container", c.id);
        return true;
      }
    });
    this.addCommand({ id: "advise", name: "AI advice on container thresholds\u2026", callback: () => this.pickContainer((c) => c && this.openAdvice(c)) });
    this.addCommand({ id: "revalidate", name: "Revalidation\u2026", callback: () => this.pickContainer((c) => this.runRevalidate(c), "All containers") });
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
      }
    });
  }
};
function lcFirst(s) {
  return s.length > 1 && s[1] === s[1].toLowerCase() ? s[0].toLowerCase() + s.slice(1) : s;
}
function markApproved(text) {
  const re = new RegExp(`^(\\s*[-*]\\s*)\\[ \\](\\s*${APPROVE})`, "m");
  if (re.test(text)) return text.replace(re, "$1[x]$2");
  if (new RegExp(`^\\s*[-*]\\s*\\[[xXxx\u2713vV]\\]\\s*${APPROVE}`, "m").test(text)) return text;
  const fm = /^---\r?\n[\s\S]*?\r?\n---\r?\n/.exec(text);
  const at = fm ? fm[0].length : 0;
  return text.slice(0, at) + `- [x] ${APPROVE}

` + text.slice(at);
}

/* Второй мозг — плагин Obsidian. Исходники: папка plugin-src в архиве программы. */
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
  ["files", "\u043F\u0440\u0438\u043D\u044F\u0442\u043E \u0444\u0430\u0439\u043B\u043E\u0432"],
  ["items_classified", "\u0440\u0430\u0437\u043E\u0431\u0440\u0430\u043D\u043E \u0444\u0430\u0439\u043B\u043E\u0432"],
  ["placed", "\u0437\u0430\u043F\u0438\u0441\u0435\u0439 \u0440\u0430\u0437\u043B\u043E\u0436\u0435\u043D\u043E"],
  ["quarantined", "\u043D\u0430 \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0443"],
  ["unsorted", "\u0431\u0435\u0437 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430"],
  ["containers_created", "\u043D\u043E\u0432\u044B\u0445 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u043E\u0432"],
  ["compacted", "\u0443\u043F\u043B\u043E\u0442\u043D\u0435\u043D\u043E"],
  ["aspects", "\u0430\u0441\u043F\u0435\u043A\u0442\u043E\u0432 \u0438\u0437\u0432\u043B\u0435\u0447\u0435\u043D\u043E"],
  ["composites", "\u0441\u043E\u0441\u0442\u0430\u0432\u043D\u044B\u0445 \u0441\u043E\u0431\u0440\u0430\u043D\u043E"],
  ["duplicates", "\u0434\u0443\u0431\u043B\u0435\u0439 \u0441\u0432\u044F\u0437\u0430\u043D\u043E"],
  ["bases", "\u0431\u0430\u0437 \u0441\u0438\u043D\u0442\u0435\u0437\u0430 \u0441\u043E\u0431\u0440\u0430\u043D\u043E"],
  ["products", "\u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u043E\u0432 \u043D\u0430\u043F\u0438\u0441\u0430\u043D\u043E"],
  ["answers", "\u043E\u0442\u0432\u0435\u0442\u043E\u0432 \u043F\u0440\u0438\u043D\u044F\u0442\u043E"]
];
function statsLine(stats) {
  if (!stats) return "";
  return STAT_NAMES.filter(([k]) => stats[k]).map(([k, label]) => `${label}: ${stats[k]}`).join("; ");
}
function callsLine(calls) {
  if (!calls) return "";
  const total = Object.values(calls).reduce((a, b) => a + b, 0);
  if (!total) return "";
  return `\u041E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439 \u043A \u043C\u043E\u0434\u0435\u043B\u0438: ${total} (` + Object.entries(calls).map(([k, v]) => `${k} \u2014 ${v}`).join(", ") + ")";
}
function plural(n, forms) {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return forms[2];
  if (b > 1 && b < 5) return forms[1];
  if (b === 1) return forms[0];
  return forms[2];
}
var nQuestions = (n) => `${n} ${plural(n, ["\u0432\u043E\u043F\u0440\u043E\u0441", "\u0432\u043E\u043F\u0440\u043E\u0441\u0430", "\u0432\u043E\u043F\u0440\u043E\u0441\u043E\u0432"])}`;
var nRecords = (n) => `${n} ${plural(n, ["\u0437\u0430\u043F\u0438\u0441\u044C", "\u0437\u0430\u043F\u0438\u0441\u0438", "\u0437\u0430\u043F\u0438\u0441\u0435\u0439"])}`;
var nCalls = (n) => `${n} ${plural(n, ["\u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0435", "\u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F", "\u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439"])}`;
function duration(ms) {
  const s = Math.max(0, Math.round(ms / 1e3));
  const h = Math.floor(s / 3600);
  const m = Math.floor(s % 3600 / 60);
  const sec = s % 60;
  if (h) return `${h} \u0447 ${String(m).padStart(2, "0")} \u043C\u0438\u043D`;
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
  const what = kind === "int" ? "\u0446\u0435\u043B\u043E\u0435 \u0447\u0438\u0441\u043B\u043E" : "\u0447\u0438\u0441\u043B\u043E";
  if (min !== void 0 && max !== void 0) return `${what} \u043E\u0442 ${min} \u0434\u043E ${max}`;
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
  return (out || words[0]?.slice(0, max) || "\u043C\u044B\u0441\u043B\u044C").replace(/[. ]+$/, "");
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
  return p > 999 ? "\u0431\u043E\u043B\u044C\u0448\u0435 999%" : `${Math.round(p)}%`;
}
function num(x) {
  return String(Math.round(x || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, "\xA0");
}
function compact(x) {
  const n = Math.round(x || 0);
  if (Math.abs(n) < 1e4) return num(n);
  if (Math.abs(n) < 1e6) return `${(n / 1e3).toFixed(1).replace(".", ",").replace(/,0$/, "")}\xA0\u0442\u044B\u0441.`;
  return `${(n / 1e6).toFixed(2).replace(".", ",").replace(/,?0+$/, "")}\xA0\u043C\u043B\u043D`;
}
function durationText(sec) {
  const s = Math.max(0, Math.round(sec || 0));
  if (s < 60) return `${s} \u0441`;
  const h = Math.floor(s / 3600);
  const m = Math.floor(s % 3600 / 60);
  if (h) return `${h} \u0447 ${String(m).padStart(2, "0")} \u043C\u0438\u043D`;
  return `${m} \u043C\u0438\u043D ${String(s % 60).padStart(2, "0")} \u0441`;
}
function etaText(ms) {
  const m = ms / 6e4;
  if (m < 1) return "\u043C\u0435\u043D\u044C\u0448\u0435 \u043C\u0438\u043D\u0443\u0442\u044B";
  if (m < 90) return `\u2248 ${Math.round(m)} \u043C\u0438\u043D`;
  return `\u2248 ${(m / 60).toFixed(1).replace(".", ",")} \u0447`;
}
var PTYPE_RU = {
  cloud: "\u043E\u0431\u043B\u0430\u0447\u043D\u0430\u044F",
  local: "\u043B\u043E\u043A\u0430\u043B\u044C\u043D\u0430\u044F",
  webchat: "\u0432\u0435\u0431-\u0447\u0430\u0442",
  fake: "\u0442\u0435\u0441\u0442\u043E\u0432\u0430\u044F"
};
function usageLine(t, o = {}) {
  if (!t || !t.calls) return "\u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439 \u043D\u0435 \u0431\u044B\u043B\u043E";
  const parts = [nCalls(t.calls)];
  if (t.in || t.out) parts.push(`\u0442\u043E\u043A\u0435\u043D\u043E\u0432 ${compact(t.in)} \u2192 ${compact(t.out)}` + (t.cached ? ` (\u0438\u0437 \u043A\u044D\u0448\u0430 ${compact(t.cached)})` : ""));
  if (o.cost !== false && (t.cost || o.cost && !t.unpriced)) parts.push(money(t.cost) + (t.unpriced ? "*" : ""));
  if (o.time && t.sec) parts.push(`\u043C\u043E\u0434\u0435\u043B\u044C \u0440\u0430\u0431\u043E\u0442\u0430\u043B\u0430 ${durationText(t.sec)}`);
  return parts.join(" \xB7 ");
}
function sizeText(bytes) {
  const b = Math.max(0, bytes || 0);
  if (b >= 1e9) return `${(b / 1e9).toFixed(1).replace(".", ",")} \u0413\u0411`;
  return `${Math.max(1, Math.round(b / 1e6))} \u041C\u0411`;
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
  const count = (s) => s.unit === "%" ? `${s.stage}: ${s.n}%${s.item ? ` \xB7 ${s.item}` : ""}` : s.total > 0 ? `${s.stage}: ${s.n} \u0438\u0437 ${s.total}` : s.stage + (s.item ? ` \xB7 ${s.item}` : "");
  const stage = s0 ? count(s0) : "";
  const sub = s1 ? count(s1) : "";
  let eta = "";
  const e0 = stageEta(s0, now);
  if (e0 !== null) eta = `\u043E\u0441\u0442\u0430\u043B\u043E\u0441\u044C ${etaText(e0)}`;
  else {
    const e1 = stageEta(s1, now);
    if (e1 !== null) eta = `\u043F\u043E \u044D\u0442\u043E\u0439 \u0447\u0430\u0441\u0442\u0438 \u043E\u0441\u0442\u0430\u043B\u043E\u0441\u044C ${etaText(e1)}`;
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
    /** живая строка программы (этап, ожидание, расход) — панель обновляет блок запуска */
    this.onLive = () => {
    };
    this.onNotice = () => {
    };
    /** вопрос посреди запуска: номер варианта или null (окно закрыто — отказ) */
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
    const dir = this.programDir() || "<\u043F\u0430\u043F\u043A\u0430 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B>";
    return import_obsidian.Platform.isWin ? path.join(dir, ".venv", "Scripts", "python.exe") : path.join(dir, ".venv", "bin", "python");
  }
  pythonPath() {
    return (this.plugin.data.pythonPath || "").trim() || this.defaultPython();
  }
  /** Что мешает запустить программу — понятным текстом, или null. */
  problem() {
    const dir = this.programDir();
    if (!dir) return "\u041D\u0435 \u0443\u043A\u0430\u0437\u0430\u043D\u0430 \u043F\u0430\u043F\u043A\u0430 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B \xAB\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433\xBB. \u041E\u0442\u043A\u0440\u043E\u0439\u0442\u0435 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u043F\u043B\u0430\u0433\u0438\u043D\u0430 \u0438 \u0432\u043F\u0438\u0448\u0438\u0442\u0435 \u0435\u0451 \u2014 \u044D\u0442\u043E \u043F\u0430\u043F\u043A\u0430, \u0433\u0434\u0435 \u043B\u0435\u0436\u0438\u0442 \xAB\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0430.bat\xBB.";
    if (!fs.existsSync(path.join(dir, "brain", "__main__.py")))
      return `\u0412 \u043F\u0430\u043F\u043A\u0435 \xAB${dir}\xBB \u043D\u0435\u0442 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B (\u043F\u0430\u043F\u043A\u0438 brain). \u041F\u0440\u043E\u0432\u0435\u0440\u044C\u0442\u0435 \u043F\u0443\u0442\u044C \u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0430\u0445 \u043F\u043B\u0430\u0433\u0438\u043D\u0430.`;
    const py = this.pythonPath();
    if (!fs.existsSync(py)) return `\u041D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D Python \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B: ${py}. \u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u0435 \xAB\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0430.bat\xBB \u0432 \u043F\u0430\u043F\u043A\u0435 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B.`;
    if (!this.vaultPath()) return "\u041F\u043B\u0430\u0433\u0438\u043D \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 \u0442\u043E\u043B\u044C\u043A\u043E \u0432 Obsidian \u0434\u043B\u044F \u043A\u043E\u043C\u043F\u044C\u044E\u0442\u0435\u0440\u0430, \u0441 \u0445\u0440\u0430\u043D\u0438\u043B\u0438\u0449\u0435\u043C \u043D\u0430 \u0434\u0438\u0441\u043A\u0435.";
    return null;
  }
  /** Идёт ли запуск, который пользователь должен видеть. */
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
  /** Запустить команду программы. Ошибки не бросаются: итог всегда приходит как RunResult. */
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
  /** Действие внутри Obsidian в общей очереди: например, правка YAML контейнера не во время прогона. */
  local(label, fn) {
    return new Promise((resolve) => {
      const job = this.make(label, [], true, true, resolve);
      job.fn = fn;
      this.enqueue(job);
    });
  }
  snapshot() {
    return this.run(["snapshot"], { label: "\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435 \u0441\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u044F", quiet: true });
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
        () => this.finish(job, { ok: true, title: "\u0413\u043E\u0442\u043E\u0432\u043E" }),
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
      this.finish(job, { ok: false, error: `\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0443: ${e}` });
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
            job.lines.push(`(\u043D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0440\u0430\u0437\u043E\u0431\u0440\u0430\u0442\u044C \u0441\u0442\u0440\u043E\u043A\u0443 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B @@${tag}: ${e})`);
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
      this.finish(job, { ok: false, error: `\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0443 (${this.pythonPath()}): ${err.message}` });
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
        r = { ok: false, code: code ?? -1, error: job.killed ? "\u041F\u0440\u0435\u0440\u0432\u0430\u043D\u043E \u0441\u0440\u0430\u0437\u0443." : `\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u043B\u0430\u0441\u044C \u0431\u0435\u0437 \u0438\u0442\u043E\u0433\u0430 (\u043A\u043E\u0434 ${code}).${tail2 ? "\n" + tail2 : ""}` };
      }
      if (job.killed) {
        r.stopped = true;
        r.title = "\u041F\u0440\u0435\u0440\u0432\u0430\u043D\u043E";
        r.error = r.error || "\u041F\u0440\u0435\u0440\u0432\u0430\u043D\u043E \u0441\u0440\u0430\u0437\u0443.";
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
  /** Живые строки программы: @@PROGRESS, @@WAIT, @@USAGE, @@NOTICE, @@ASK и итог @@RESULT. */
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
          console.error("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433:", e);
        }
        break;
      }
      case "ASK": {
        const ask = {
          id: String(o.id || ""),
          title: String(o.title || "\u0412\u043E\u043F\u0440\u043E\u0441"),
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
          console.error("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433:", e);
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
      console.error("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433:", e);
    }
  }
  /** Ответ на вопрос программы — строка JSON в её стандартный ввод (пустая строка — отказ). */
  answer(job, ask, choice) {
    if (job.live.ask !== ask) return;
    job.live.ask = null;
    job.askCancel = void 0;
    const ok = choice !== null && choice >= 0 && choice < ask.options.length;
    job.lines.push(`\u2192 ${ok ? ask.options[choice] : "\u0431\u0435\u0437 \u043E\u0442\u0432\u0435\u0442\u0430"}`);
    try {
      const st = job.child?.stdin;
      if (st && !st.destroyed) st.write(ok ? JSON.stringify({ choice }) + "\n" : "\n", "utf8");
    } catch (e) {
      console.warn("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433: \u043D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u0432\u0435\u0442\u0438\u0442\u044C \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0435", e);
    }
    this.changed();
  }
  /** Процесс завершился или нажали «Стоп»: открытый вопрос закрывается без ответа. */
  dropAsk(job) {
    const ask = job.live.ask;
    const cancel = job.askCancel;
    job.askCancel = void 0;
    if (ask) this.answer(job, ask, null);
    if (cancel) {
      try {
        cancel();
      } catch (e) {
        console.error("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433:", e);
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
        console.error("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433:", e);
      }
    }
    this.changed();
    this.pump();
  }
  /** «Стоп»: очередь отменяется, текущий запуск закончит шаг, сохранит всё и остановится. */
  stop() {
    const keep = (j) => !!j.fn || j.args[0] === "answer";
    const cancelled = this.queue.filter((j) => !keep(j));
    this.queue = this.queue.filter(keep);
    for (const j of cancelled) {
      j.status = "cancelled";
      this.finish(j, { ok: false, stopped: true, title: "\u041E\u0442\u043C\u0435\u043D\u0435\u043D\u043E", error: "\u041E\u0442\u043C\u0435\u043D\u0435\u043D\u043E \u043A\u043D\u043E\u043F\u043A\u043E\u0439 \xAB\u0421\u0442\u043E\u043F\xBB." });
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
        console.error("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433: \u043D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u043F\u0438\u0441\u0430\u0442\u044C \u0444\u0430\u0439\u043B \xAB\u0421\u0442\u043E\u043F\xBB", e);
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
      if (import_obsidian.Platform.isWin) (0, import_child_process.spawn)("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true });
      else cur.child.kill("SIGTERM");
    } catch (e) {
      console.error("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433: \u043D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043F\u0440\u0435\u0440\u0432\u0430\u0442\u044C \u043F\u0440\u043E\u0446\u0435\u0441\u0441", e);
    }
    this.changed();
  }
  /** При выключении плагина: текущий запуск аккуратно останавливается. */
  dispose() {
    if (this.current && !this.current.fn) this.stop();
  }
  changed() {
    try {
      this.onChange();
    } catch (e) {
      console.error("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433:", e);
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
    return { message: String(x.message || x.name || "\u043E\u0448\u0438\u0431\u043A\u0430"), stack: String(x.stack || "") };
  }
  return { message: String(e), stack: "" };
}
var pad2 = (n) => String(n).padStart(2, "0");
var stamp = (d = /* @__PURE__ */ new Date()) => `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}.${d.getFullYear()} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
var LOG_FILE = "_\u043B\u043E\u0433\u0438/\u043F\u043B\u0430\u0433\u0438\u043D.log";
var ErrorLog = class {
  constructor(plugin) {
    this.plugin = plugin;
    this.items = [];
    this.chain = Promise.resolve();
  }
  /** quiet — ошибку уже вывел в консоль сам Obsidian (неперехваченная). */
  add(where, e, quiet = false) {
    const { message, stack } = errParts(e);
    const rec = { at: stamp(), where, message, stack };
    const last = this.items[0];
    if (last && last.where === where && last.message === message) return last;
    this.items.unshift(rec);
    if (this.items.length > KEEP) this.items.pop();
    if (!quiet) console.error(`\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433 (${where}):`, e);
    const entry = `
===== ${rec.at} \xB7 ${where} \xB7 \u043F\u043B\u0430\u0433\u0438\u043D ${this.plugin.manifest.version}
${message}
${stack}
`;
    this.chain = this.chain.then(() => this.write(entry)).catch(() => void 0);
    return rec;
  }
  /** Запись в _логи/плагин.log хранилища (больше 512 КБ — прежний журнал становится плагин.log.old). */
  async write(entry) {
    const a = this.plugin.app.vault.adapter;
    if (!await a.exists("_\u043B\u043E\u0433\u0438")) await a.mkdir("_\u043B\u043E\u0433\u0438");
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
    `\u041F\u043B\u0430\u0433\u0438\u043D: ${plugin.manifest.version}`,
    `\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430: ${plugin.ui?.program || "?"}`,
    `Obsidian: ${import_obsidian2.apiVersion}`,
    `\u0421\u0438\u0441\u0442\u0435\u043C\u0430: ${import_obsidian2.Platform.isWin ? "Windows" : import_obsidian2.Platform.isMacOS ? "macOS" : "Linux"} ${os.release()} (${process.arch})`
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
  return ["\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433 \u2014 \u043E\u0448\u0438\u0431\u043A\u0430 \u043F\u043B\u0430\u0433\u0438\u043D\u0430", ...versionLines(plugin), "", recText(rec)].join("\n");
}
function renderError(el, plugin, where, e) {
  const rec = plugin.errors.add(where, e);
  const box = el.createDiv({ cls: "vm-callout is-bad vm-error-box" });
  box.createDiv({ cls: "vm-callout-title", text: `\u041E\u0448\u0438\u0431\u043A\u0430 \u0432 \u043F\u043B\u0430\u0433\u0438\u043D\u0435 (${where})` });
  box.createDiv({ text: rec.message });
  box.createDiv({
    cls: "vm-small-text vm-muted",
    text: `\u041E\u0441\u0442\u0430\u043B\u044C\u043D\u043E\u0435 \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442. \u041F\u043E\u0434\u0440\u043E\u0431\u043D\u043E\u0441\u0442\u0438 \u0437\u0430\u043F\u0438\u0441\u0430\u043D\u044B \u0432 ${LOG_FILE} \u2014 \u043D\u0430\u0436\u043C\u0438\u0442\u0435 \xAB\u0421\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u0442\u044C \u043E\u0442\u0447\u0451\u0442\xBB \u0438 \u043F\u0440\u0438\u0448\u043B\u0438\u0442\u0435 \u0435\u0433\u043E \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u0447\u0438\u043A\u0443.`
  });
  const row = box.createDiv({ cls: "vm-buttons" });
  const b = row.createEl("button", { text: "\u0421\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u0442\u044C \u043E\u0442\u0447\u0451\u0442" });
  b.addEventListener("click", async () => {
    const ok = await copyText(errorReport(plugin, rec));
    new import_obsidian2.Notice(ok ? "\u041E\u0442\u0447\u0451\u0442 \u0441\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u043D \u2014 \u0432\u0441\u0442\u0430\u0432\u044C\u0442\u0435 \u0435\u0433\u043E \u0432 \u0441\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u0435 \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u0447\u0438\u043A\u0443." : `\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0441\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u0442\u044C \u2014 \u043E\u0442\u0447\u0451\u0442 \u0435\u0441\u0442\u044C \u0432 \u0444\u0430\u0439\u043B\u0435 ${LOG_FILE}.`);
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
  const out = ["# \u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433 \u2014 \u043E\u0442\u0447\u0451\u0442 \u0434\u043B\u044F \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u0447\u0438\u043A\u0430", "", `\u0421\u043E\u0431\u0440\u0430\u043D: ${stamp()}`, "", ...versionLines(plugin).map((x) => `- ${x}`)];
  const problem = plugin.engine.problem();
  out.push(`- \u041F\u0430\u043F\u043A\u0430 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B: ${plugin.engine.programDir() || "\u043D\u0435 \u0443\u043A\u0430\u0437\u0430\u043D\u0430"}${problem ? ` \u2014 ${problem}` : ""}`);
  out.push("", "## \u041E\u0448\u0438\u0431\u043A\u0438 \u043F\u043B\u0430\u0433\u0438\u043D\u0430 (\u043F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435)", "");
  if (plugin.errors.items.length) out.push("```", ...plugin.errors.items.slice(0, 10).map(recText), "```");
  else out.push("\u041D\u0435\u0442.");
  const progErr = await tail(plugin, "_\u043B\u043E\u0433\u0438/\u043E\u0448\u0438\u0431\u043A\u0438.log", 6e3);
  out.push("", "## \u041E\u0448\u0438\u0431\u043A\u0438 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B (\u043A\u043E\u043D\u0435\u0446 _\u043B\u043E\u0433\u0438/\u043E\u0448\u0438\u0431\u043A\u0438.log)", "", progErr ? "```\n" + progErr.trim() + "\n```" : "\u041D\u0435\u0442.");
  out.push("", "## \u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435 \u0437\u0430\u043F\u0443\u0441\u043A\u0438", "");
  const jobs = plugin.engine.history.slice(0, 3);
  if (!jobs.length) out.push("\u0412 \u044D\u0442\u043E\u043C \u0441\u0435\u0430\u043D\u0441\u0435 Obsidian \u0437\u0430\u043F\u0443\u0441\u043A\u043E\u0432 \u043D\u0435 \u0431\u044B\u043B\u043E.");
  for (const j of jobs) {
    out.push(`### ${j.label} \u2014 ${j.status}`, "", "```", ...j.lines.slice(-40), ...j.stderr ? ["--- stderr ---", j.stderr.slice(-3e3)] : [], "```", "");
  }
  return out.join("\n");
}
async function saveDeveloperReport(plugin) {
  const text = await developerReport(plugin);
  const copied = await copyText(text);
  const rel = "_\u043B\u043E\u0433\u0438/\u043E\u0442\u0447\u0451\u0442 \u0434\u043B\u044F \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u0447\u0438\u043A\u0430.md";
  const vault = plugin.app.vault;
  try {
    if (!vault.getAbstractFileByPath("_\u043B\u043E\u0433\u0438") && !await vault.adapter.exists("_\u043B\u043E\u0433\u0438")) await vault.createFolder("_\u043B\u043E\u0433\u0438");
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
    plugin.errors.add("\u043E\u0442\u0447\u0451\u0442 \u0434\u043B\u044F \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u0447\u0438\u043A\u0430", e);
  }
  new import_obsidian2.Notice(copied ? "\u041E\u0442\u0447\u0451\u0442 \u0441\u043E\u0431\u0440\u0430\u043D \u0438 \u0441\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u043D \u2014 \u0432\u0441\u0442\u0430\u0432\u044C\u0442\u0435 \u0435\u0433\u043E \u0432 \u0441\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u0435 \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u0447\u0438\u043A\u0443." : `\u041E\u0442\u0447\u0451\u0442 \u0441\u043E\u0431\u0440\u0430\u043D: ${rel}`, 8e3);
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
    b.createEl("button", { text: this.o.cancel || "\u041E\u0442\u043C\u0435\u043D\u0430" }).addEventListener("click", () => this.answer(false));
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
  const note = ask.id === "budget" ? "\u041E\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0430 \u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u043F\u043E\u0440\u0442\u0438\u0442: \u0432\u0441\u0451 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u043D\u043D\u043E\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u043E, \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0438\u0439 \u0437\u0430\u043F\u0443\u0441\u043A \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442. \u0411\u044E\u0434\u0436\u0435\u0442 \u2014 \u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0430\u0445, \u0432\u043A\u043B\u0430\u0434\u043A\u0430 \xAB\u0420\u0430\u0441\u0445\u043E\u0434\u044B\xBB." : ask.id === "estimate" ? "\u041F\u043E\u0440\u043E\u0433, \u0441 \u043A\u043E\u0442\u043E\u0440\u043E\u0433\u043E \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0441\u043F\u0440\u0430\u0448\u0438\u0432\u0430\u0435\u0442, \u2014 \u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0430\u0445, \u0432\u043A\u043B\u0430\u0434\u043A\u0430 \xAB\u0420\u0430\u0441\u0445\u043E\u0434\u044B\xBB. \u0417\u0430\u043A\u0440\u044B\u0442\u044C \u043E\u043A\u043D\u043E \u2014 \u0442\u043E \u0436\u0435, \u0447\u0442\u043E \xAB\u041E\u0442\u043C\u0435\u043D\u0430\xBB." : "\u0417\u0430\u043A\u0440\u044B\u0442\u044C \u043E\u043A\u043D\u043E \u2014 \u0442\u043E \u0436\u0435, \u0447\u0442\u043E \u043E\u0442\u043A\u0430\u0437\u0430\u0442\u044C\u0441\u044F.";
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
    this.contentEl.createEl("pre", { cls: "vm-pre", text: this.text || "(\u043F\u0443\u0441\u0442\u043E)" });
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "\u0421\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u0442\u044C" }).addEventListener("click", async () => {
      new import_obsidian3.Notice(await copyText(this.text) ? "\u0421\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u043D\u043E" : "\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0441\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u0442\u044C \u2014 \u0432\u044B\u0434\u0435\u043B\u0438\u0442\u0435 \u0442\u0435\u043A\u0441\u0442 \u0438 \u043D\u0430\u0436\u043C\u0438\u0442\u0435 Ctrl+C.");
    });
    b.createEl("button", { text: "\u0417\u0430\u043A\u0440\u044B\u0442\u044C" }).addEventListener("click", () => this.close());
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
    this.setPlaceholder("\u041D\u0430\u0447\u043D\u0438\u0442\u0435 \u0432\u0432\u043E\u0434\u0438\u0442\u044C \u043D\u0430\u0437\u0432\u0430\u043D\u0438\u0435 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430");
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
    this.setTitle("\u041D\u043E\u0432\u0430\u044F \u043C\u044B\u0441\u043B\u044C");
    const el = this.contentEl;
    el.addClass("vm-modal", "vm-thought");
    const ta = el.createEl("textarea", { cls: "vm-thought-text", attr: { rows: "7", placeholder: "\u0427\u0442\u043E \u043F\u0440\u0438\u0448\u043B\u043E \u0432 \u0433\u043E\u043B\u043E\u0432\u0443? \u041F\u0438\u0448\u0438\u0442\u0435 \u043A\u0430\u043A \u0435\u0441\u0442\u044C." } });
    const grid = el.createDiv({ cls: "vm-form" });
    const f1 = grid.createDiv({ cls: "vm-form-row" });
    f1.createEl("label", { text: "\u041A\u0443\u0434\u0430 \u043E\u0442\u043D\u0435\u0441\u0442\u0438", attr: { for: "vm-hint" } });
    const hint = f1.createEl("input", { type: "text", attr: { id: "vm-hint", list: "vm-hint-list", placeholder: "\u043D\u0435\u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u043E \u2014 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0440\u0435\u0448\u0438\u0442 \u0441\u0430\u043C\u0430" } });
    hint.value = this.hint;
    const dl = f1.createEl("datalist", { attr: { id: "vm-hint-list" } });
    for (const c of ui?.containers || []) dl.createEl("option", { attr: { value: c.title } });
    const f2 = grid.createDiv({ cls: "vm-form-row" });
    f2.createEl("label", { text: "\u0414\u0430\u0442\u0430", attr: { for: "vm-date" } });
    const date = f2.createEl("input", { type: "date", attr: { id: "vm-date" } });
    date.value = todayIso();
    const sources = (ui?.sources || []).map((s) => s.name).filter((n) => n && n.toLowerCase() !== "\u0430\u0440\u0445\u0438\u0432");
    const f3 = grid.createDiv({ cls: "vm-form-row" });
    f3.createEl("label", { text: "\u0418\u0441\u0442\u043E\u0447\u043D\u0438\u043A", attr: { for: "vm-src" } });
    const src = f3.createEl("select", { cls: "dropdown", attr: { id: "vm-src" } });
    if (!sources.includes("\u0437\u0430\u043C\u0435\u0442\u043A\u0430")) src.createEl("option", { text: "\u0437\u0430\u043C\u0435\u0442\u043A\u0430", attr: { value: "\u0437\u0430\u043C\u0435\u0442\u043A\u0430" } });
    for (const s of sources) src.createEl("option", { text: s, attr: { value: s } });
    src.value = "\u0437\u0430\u043C\u0435\u0442\u043A\u0430";
    const f4 = el.createDiv({ cls: "vm-check-row" });
    const now = f4.createEl("input", { type: "checkbox", attr: { id: "vm-now" } });
    now.checked = false;
    f4.createEl("label", { text: "\u0421\u0440\u0430\u0437\u0443 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u0442\u044C (\u0424\u0430\u0437\u0430 1)", attr: { for: "vm-now" } });
    const b = el.createDiv({ cls: "vm-modal-buttons" });
    const save = b.createEl("button", { text: "\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C", cls: "mod-cta" });
    b.createEl("button", { text: "\u041E\u0442\u043C\u0435\u043D\u0430" }).addEventListener("click", () => this.close());
    const go = async () => {
      const text = ta.value.trim();
      if (!text) {
        new import_obsidian3.Notice("\u041D\u0430\u043F\u0438\u0448\u0438\u0442\u0435 \u043C\u044B\u0441\u043B\u044C.");
        ta.focus();
        return;
      }
      save.disabled = true;
      try {
        const path3 = await this.plugin.saveThought(text, hint.value.trim(), date.value || todayIso(), src.value);
        this.close();
        if (now.checked) {
          new import_obsidian3.Notice(`\u041C\u044B\u0441\u043B\u044C \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u0430: ${path3}. \u041E\u0431\u0440\u0430\u0431\u0430\u0442\u044B\u0432\u0430\u044E\u2026`);
          this.plugin.runPhase1();
        } else new import_obsidian3.Notice(`\u041C\u044B\u0441\u043B\u044C \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u0430: ${path3}. \u041E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442\u0441\u044F \u043F\u0440\u0438 \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0435\u0439 \u0424\u0430\u0437\u0435 1.`);
      } catch (e) {
        save.disabled = false;
        new import_obsidian3.Notice(`\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0441\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C: ${e}`);
      }
    };
    save.addEventListener("click", go);
    ta.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
        ev.preventDefault();
        go();
      }
    });
    el.createDiv({ cls: "vm-muted vm-small-text", text: "Ctrl+Enter \u2014 \u0441\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C. \u0424\u0430\u0439\u043B \u043F\u043E\u043F\u0430\u0434\u0451\u0442 \u0432 _staging \u0441 \u043F\u043E\u043C\u0435\u0442\u043A\u043E\u0439 \xAB\u043E\u0434\u043D\u0430 \u0437\u0430\u043F\u0438\u0441\u044C\xBB." });
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
  if (r.source === "own") return "\u0441\u0435\u0439\u0447\u0430\u0441 \u2014 \u0441\u0432\u043E\u0439 \u043F\u043E\u0440\u043E\u0433 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430";
  if (r.source === "parent") return `\u0441\u0435\u0439\u0447\u0430\u0441 \u2014 \u043E\u0442 \u0440\u043E\u0434\u0438\u0442\u0435\u043B\u044F \xAB${r.from}\xBB`;
  return "\u0441\u0435\u0439\u0447\u0430\u0441 \u2014 \u043E\u0431\u0449\u0438\u0439 \u043F\u043E\u0440\u043E\u0433 \u0438\u0437 \u043D\u0430\u0441\u0442\u0440\u043E\u0435\u043A";
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
    this.setTitle(`\u0421\u043E\u0432\u0435\u0442 \u0418\u0418 \u043F\u043E \u043F\u043E\u0440\u043E\u0433\u0430\u043C \xB7 ${this.c.title}`);
    this.modalEl.addClass("vm-wide");
    this.contentEl.addClass("vm-modal", "vm-advice");
    if (this.ready) {
      this.show(this.ready);
      return;
    }
    const w = this.contentEl.createDiv({ cls: "vm-wait" });
    w.createDiv({ cls: "vm-progress" });
    w.createDiv({
      text: this.plugin.engine.busy() ? "\u0412 \u043E\u0447\u0435\u0440\u0435\u0434\u0438: \u0441\u043E\u0432\u0435\u0442 \u043D\u0430\u0447\u043D\u0451\u0442\u0441\u044F \u043F\u043E\u0441\u043B\u0435 \u0442\u0435\u043A\u0443\u0449\u0435\u0433\u043E \u0437\u0430\u043F\u0443\u0441\u043A\u0430." : "\u041C\u043E\u0434\u0435\u043B\u044C \u0438\u0437\u0443\u0447\u0430\u0435\u0442, \u043A\u0430\u043A \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0440\u0435\u0448\u0430\u043B\u0430 \u043F\u043E \u044D\u0442\u043E\u043C\u0443 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0443: \u043E\u0448\u0438\u0431\u043A\u0438 \u0440\u0430\u0441\u043A\u043B\u0430\u0434\u043A\u0438, \u043B\u0438\u0448\u043D\u0438\u0435 \u0432\u043E\u043F\u0440\u043E\u0441\u044B, \u0447\u0442\u043E \u043F\u043E\u043F\u0430\u043B\u043E \u0432 \u0431\u0430\u0437\u0443\u2026"
    });
    w.createDiv({ cls: "vm-muted", text: "\u042D\u0442\u043E \u043E\u0434\u043D\u043E \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0435 \u043A \u043C\u043E\u0434\u0435\u043B\u0438. \u041E\u043A\u043D\u043E \u043C\u043E\u0436\u043D\u043E \u0437\u0430\u043A\u0440\u044B\u0442\u044C \u2014 \u0441\u043E\u0432\u0435\u0442 \u0441\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u0441\u044F \u0432\u043E \u0432\u043A\u043B\u0430\u0434\u043A\u0435 \xAB\u041A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\xBB." });
    const r = await this.plugin.adviseNow(this.c);
    if (!this.alive) return;
    this.contentEl.empty();
    if (!r.ok || !r.advice) {
      const box = this.contentEl.createDiv({ cls: "vm-callout is-warning" });
      box.createDiv({ text: r.error || r.title || "\u0421\u043E\u0432\u0435\u0442 \u043D\u0435 \u043F\u043E\u043B\u0443\u0447\u0435\u043D." });
      this.closeButton();
      return;
    }
    this.show(r.advice);
  }
  show(a) {
    const el = this.contentEl;
    el.createDiv({ cls: "vm-advice-summary", text: a.summary || "\u041C\u043E\u0434\u0435\u043B\u044C \u043D\u0435 \u043D\u0430\u043F\u0438\u0441\u0430\u043B\u0430 \u0432\u044B\u0432\u043E\u0434\u0430." });
    const chosen = new Set(a.recommendations.map((r) => r.name));
    if (!a.recommendations.length) el.createDiv({ cls: "vm-callout is-ok", text: "\u041C\u0435\u043D\u044F\u0442\u044C \u043F\u043E\u0440\u043E\u0433\u0438 \u043D\u0435 \u043D\u0443\u0436\u043D\u043E." });
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
      det.createEl("summary", { text: "\u041D\u0430 \u0447\u0451\u043C \u043E\u0441\u043D\u043E\u0432\u0430\u043D \u0441\u043E\u0432\u0435\u0442" });
      const ul = det.createEl("ul");
      for (const line of a.brief) ul.createEl("li", { text: line });
    }
    const b = el.createDiv({ cls: "vm-modal-buttons" });
    if (a.recommendations.length) {
      apply = b.createEl("button", { text: "\u041F\u0440\u0438\u043C\u0435\u043D\u0438\u0442\u044C \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u0435", cls: "mod-cta" });
      apply.addEventListener("click", async () => {
        const changes = {};
        for (const r of a.recommendations) if (chosen.has(r.name)) changes[r.name] = r.value;
        apply.disabled = true;
        const ok = await this.plugin.saveThresholds(this.c, changes);
        if (ok) {
          new import_obsidian3.Notice(`\u041F\u043E\u0440\u043E\u0433\u0438 \xAB${this.c.title}\xBB \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u044B: ` + a.recommendations.filter((r) => chosen.has(r.name)).map((r) => `${r.label.toLowerCase()} ${r.current} \u2192 ${r.value}`).join(", "));
          this.plugin.forgetAdvice(this.c.id);
          this.close();
        } else apply.disabled = false;
      });
    }
    b.createEl("button", { text: "\u0417\u0430\u043A\u0440\u044B\u0442\u044C" }).addEventListener("click", () => this.close());
    el.createDiv({
      cls: "vm-muted vm-small-text",
      text: "\u0412\u044B\u0431\u0440\u0430\u043D\u043D\u044B\u0435 \u0437\u043D\u0430\u0447\u0435\u043D\u0438\u044F \u0437\u0430\u043F\u0438\u0448\u0443\u0442\u0441\u044F \u0432 YAML \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430 (\u043F\u043E\u043B\u0435 thresholds) \u0438 \u043F\u043E\u0434\u0435\u0439\u0441\u0442\u0432\u0443\u044E\u0442 \u0441\u043E \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0435\u0439 \u0424\u0430\u0437\u044B 1. \u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0437\u0430\u043F\u043E\u043C\u043D\u0438\u0442, \u043A\u0430\u043A\u043E\u0439 \u0441\u043E\u0432\u0435\u0442 \u0432\u044B \u043F\u0440\u0438\u043D\u044F\u043B\u0438."
    });
  }
  closeButton() {
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "\u0417\u0430\u043A\u0440\u044B\u0442\u044C" }).addEventListener("click", () => this.close());
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
    this.setTitle("\u041F\u0440\u043E\u0432\u0435\u0440\u043A\u0430 \u0441\u0432\u044F\u0437\u0438");
    this.contentEl.addClass("vm-modal");
    const w = this.contentEl.createDiv({ cls: "vm-wait" });
    w.createDiv({ cls: "vm-progress" });
    w.createDiv({ text: "\u041F\u0440\u043E\u0432\u0435\u0440\u044F\u044E \u0445\u0440\u0430\u043D\u0438\u043B\u0438\u0449\u0435, \u043C\u043E\u0434\u0435\u043B\u044C \u0438 \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u0438 \u2014 \u043D\u0435\u0441\u043A\u043E\u043B\u044C\u043A\u043E \u0441\u0435\u043A\u0443\u043D\u0434\u2026" });
    const r = await this.plugin.engine.run(["check"], { label: "\u041F\u0440\u043E\u0432\u0435\u0440\u043A\u0430 \u0441\u0432\u044F\u0437\u0438", exclusive: false });
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
    if (!items.length || r.error) this.contentEl.createDiv({ cls: "vm-callout is-warning", text: r.error || "\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043D\u0435 \u043E\u0442\u0432\u0435\u0442\u0438\u043B\u0430." });
    else this.contentEl.createDiv({ cls: "vm-callout " + (r.ok ? "is-ok" : "is-warning"), text: r.ok ? "\u0412\u0441\u0451 \u0432 \u043F\u043E\u0440\u044F\u0434\u043A\u0435." : "\u0415\u0441\u0442\u044C \u043F\u0440\u043E\u0431\u043B\u0435\u043C\u044B \u2014 \u0441\u043C. \u0441\u0442\u0440\u043E\u043A\u0438 \u0441 \u2717." });
    const b = this.contentEl.createDiv({ cls: "vm-modal-buttons" });
    b.createEl("button", { text: "\u0417\u0430\u043A\u0440\u044B\u0442\u044C", cls: "mod-cta" }).addEventListener("click", () => this.close());
  }
  onClose() {
    this.alive = false;
    this.contentEl.empty();
  }
};
var LLAMA_BUILD_RU = {
  cpu: "\u0434\u043B\u044F \u043F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440\u0430",
  vulkan: "Vulkan \u2014 \u0434\u043B\u044F \u043B\u044E\u0431\u044B\u0445 \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442",
  cuda: "CUDA \u2014 \u0434\u043B\u044F \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442 NVIDIA",
  system: "\u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u043D\u0430\u044F \u043D\u0430 \u043A\u043E\u043C\u043F\u044C\u044E\u0442\u0435\u0440\u0435"
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
  return x == null ? "?" : `${Math.round(x * 10) / 10}`.replace(".", ",");
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
    this.setTitle(running ? "\u041F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u043A \u043C\u043E\u0434\u0435\u043B\u0438 \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u043E\u0432" : "\u0417\u0430\u043F\u0443\u0441\u043A \u043C\u043E\u0434\u0435\u043B\u0438 \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u043E\u0432");
    this.modalEl.addClass("vm-wide", "vm-llama-modal");
    const el = this.contentEl;
    el.addClass("vm-modal", "vm-llama");
    el.createDiv({ cls: "vm-muted vm-small-text vm-choice-sub", text: `${this.st.model.title} \xB7 llama.cpp \xB7 \u043C\u043E\u0434\u0435\u043B\u044C \u0434\u043B\u044F \u043F\u043E\u0438\u0441\u043A\u0430 \u043F\u043E\u0445\u043E\u0436\u0438\u0445 \u043C\u044B\u0441\u043B\u0435\u0439` });
    this.hwEl = el.createDiv({ cls: "vm-llama-hw" });
    this.formEl = el.createDiv({ cls: "vm-llama-form" });
    this.noteEl = el.createDiv({ cls: "vm-llama-notes" });
    const b = el.createDiv({ cls: "vm-modal-buttons" });
    this.startBtn = b.createEl("button", { text: running ? "\u041F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C" : "\u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C", cls: "mod-cta" });
    this.startBtn.addEventListener("click", () => this.go());
    b.createEl("button", { text: "\u041F\u043E \u0443\u043C\u043E\u043B\u0447\u0430\u043D\u0438\u044E" }).addEventListener("click", () => {
      this.p = { ...this.st.defaults, models_dir: this.p.models_dir };
      this.renderForm();
    });
    b.createEl("button", { text: "\u041E\u0442\u043C\u0435\u043D\u0430" }).addEventListener("click", () => this.close());
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
      el.createDiv({ cls: "vm-muted", text: "\u041E\u043F\u0440\u0435\u0434\u0435\u043B\u044F\u044E, \u0447\u0442\u043E \u0435\u0441\u0442\u044C \u0443 \u043A\u043E\u043C\u043F\u044C\u044E\u0442\u0435\u0440\u0430\u2026" });
      return;
    }
    const cpu = [hw.cpu || "\u041F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440", hw.cores ? `${hw.cores} ${plural(hw.cores, ["\u044F\u0434\u0440\u043E", "\u044F\u0434\u0440\u0430", "\u044F\u0434\u0435\u0440"])}` : "", hw.threads ? `${hw.threads} ${plural(hw.threads, ["\u043F\u043E\u0442\u043E\u043A", "\u043F\u043E\u0442\u043E\u043A\u0430", "\u043F\u043E\u0442\u043E\u043A\u043E\u0432"])}` : ""].filter(Boolean).join(" \xB7 ");
    const rows = [
      ["\u041F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440", cpu],
      ["\u041F\u0430\u043C\u044F\u0442\u044C", hw.ram_gb ? `${gb(hw.ram_gb)} \u0413\u0411` + (hw.ram_free_gb ? ` (\u0441\u0432\u043E\u0431\u043E\u0434\u043D\u043E ${gb(hw.ram_free_gb)} \u0413\u0411)` : "") : "\u043D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0443\u0437\u043D\u0430\u0442\u044C"],
      ["\u0412\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u0430", hw.gpus.length ? hw.gpus.map((g) => g.name + (g.vram_gb ? `, ${gb(g.vram_gb)} \u0413\u0411` : "")).join("; ") : "\u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u0430"]
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
    new import_obsidian3.Setting(el).setName("\u0413\u0434\u0435 \u0441\u0447\u0438\u0442\u0430\u0442\u044C").setDesc("\u041D\u0430 \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u0435 \u2014 \u0432\u043E \u043C\u043D\u043E\u0433\u043E \u0440\u0430\u0437 \u0431\u044B\u0441\u0442\u0440\u0435\u0435; \u043D\u0430 \u043F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440\u0435 \u043D\u0443\u0436\u043D\u043E \u043D\u0435 \u043C\u0435\u043D\u044C\u0448\u0435 16 \u0413\u0411 \u043E\u043F\u0435\u0440\u0430\u0442\u0438\u0432\u043D\u043E\u0439 \u043F\u0430\u043C\u044F\u0442\u0438.").addDropdown((d) => d.addOptions({ cpu: "\u041F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440", gpu: "\u0412\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u0430" }).setValue(p.device).onChange((v) => {
      p.device = v;
      this.renderForm();
    }));
    if (p.device === "gpu" && st.os !== "macos") {
      const opts = { auto: "\u0410\u0432\u0442\u043E: NVIDIA \u2014 CUDA, \u0434\u0440\u0443\u0433\u0438\u0435 \u2014 Vulkan" };
      if (st.os === "win" && st.arch === "x64") opts.cuda = "CUDA \u2014 \u0434\u043B\u044F \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442 NVIDIA";
      opts.vulkan = "Vulkan \u2014 \u0434\u043B\u044F \u043B\u044E\u0431\u044B\u0445 \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442 (NVIDIA, AMD, Intel)";
      if (!opts[p.build]) p.build = "auto";
      new import_obsidian3.Setting(el).setName("\u0421\u0431\u043E\u0440\u043A\u0430 llama.cpp").setDesc("\u041A\u0430\u043A\u0443\u044E \u0432\u0435\u0440\u0441\u0438\u044E llama.cpp \u0441\u043A\u0430\u0447\u0430\u0442\u044C \u0434\u043B\u044F \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u044B.").addDropdown((d) => d.addOptions(opts).setValue(p.build).onChange((v) => {
        p.build = v;
        upd();
      }));
      const layers = st.model.layers || 48;
      const mode = typeof p.gpu_layers === "number" ? "num" : p.gpu_layers;
      const s = new import_obsidian3.Setting(el).setName("\u0421\u043B\u043E\u0451\u0432 \u043C\u043E\u0434\u0435\u043B\u0438 \u043D\u0430 \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u0435").setDesc(`\u0412\u0441\u0435\u0433\u043E \u0441\u043B\u043E\u0451\u0432 ${layers}. \u041D\u0435 \u043F\u043E\u043C\u0435\u0441\u0442\u0438\u0432\u0448\u0438\u0435\u0441\u044F \u043D\u0430 \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u0443 \u0441\u0447\u0438\u0442\u0430\u044E\u0442\u0441\u044F \u043F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440\u043E\u043C (\u043C\u0435\u0434\u043B\u0435\u043D\u043D\u0435\u0435).`);
      s.addDropdown((d) => d.addOptions({ auto: "\u0421\u043A\u043E\u043B\u044C\u043A\u043E \u043F\u043E\u043C\u0435\u0441\u0442\u0438\u0442\u0441\u044F", all: `\u0412\u0441\u0435 (${layers})`, num: "\u0421\u0432\u043E\u0451 \u0447\u0438\u0441\u043B\u043E" }).setValue(mode).onChange((v) => {
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
      ctxOpts[String(c)] = `${c.toLocaleString("ru-RU")} \u0442\u043E\u043A\u0435\u043D\u043E\u0432 \u2248 ${Math.round(c * 3 / 1e3)} \u0442\u044B\u0441. \u0437\u043D\u0430\u043A\u043E\u0432` + (need ? ` \xB7 ${gb(need)} \u0413\u0411` : "");
    }
    new import_obsidian3.Setting(el).setName("\u041A\u043E\u043D\u0442\u0435\u043A\u0441\u0442").setDesc("\u0421\u0430\u043C\u044B\u0439 \u0434\u043B\u0438\u043D\u043D\u044B\u0439 \u0442\u0435\u043A\u0441\u0442, \u043A\u043E\u0442\u043E\u0440\u044B\u0439 \u043C\u043E\u0434\u0435\u043B\u044C \u0447\u0438\u0442\u0430\u0435\u0442 \u0437\u0430 \u0440\u0430\u0437, \u0438 \u0441\u043A\u043E\u043B\u044C\u043A\u043E \u043F\u0430\u043C\u044F\u0442\u0438 \u043E\u043D\u0430 \u0442\u043E\u0433\u0434\u0430 \u0437\u0430\u0439\u043C\u0451\u0442. \u0414\u043B\u0438\u043D\u043D\u044B\u0435 \u0437\u0430\u043F\u0438\u0441\u0438 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0432\u0441\u0451 \u0440\u0430\u0432\u043D\u043E \u043E\u0431\u0440\u0435\u0437\u0430\u0435\u0442 (\xAB\u041F\u0440\u0435\u0434\u0435\u043B \u0442\u0435\u043A\u0441\u0442\u0430\xBB), \u0442\u0430\u043A \u0447\u0442\u043E 4096 \u043E\u0431\u044B\u0447\u043D\u043E \u0445\u0432\u0430\u0442\u0430\u0435\u0442.").addDropdown((d) => d.addOptions(ctxOpts).setValue(String(p.ctx)).onChange((v) => {
      p.ctx = parseInt(v, 10);
      upd();
    }));
    const kvRu = { f16: "f16 \u2014 \u0431\u0435\u0437 \u0441\u0436\u0430\u0442\u0438\u044F", q8_0: "q8_0 \u2014 8 \u0431\u0438\u0442", q4_0: "q4_0 \u2014 4 \u0431\u0438\u0442\u0430" };
    const kvOpts = {};
    for (const k of st.kv_types || ["f16", "q8_0", "q4_0"]) kvOpts[k] = kvRu[k] || k;
    new import_obsidian3.Setting(el).setName("\u041A\u0432\u0430\u043D\u0442\u043E\u0432\u0430\u043D\u0438\u0435 KV-\u043A\u0435\u0448\u0430").setDesc("\u042D\u0442\u043E\u0439 \u043C\u043E\u0434\u0435\u043B\u0438 \u043F\u043E\u0447\u0442\u0438 \u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u0434\u0430\u0451\u0442: \u043A\u0430\u0436\u0434\u044B\u0439 \u0442\u0435\u043A\u0441\u0442 \u043E\u043D\u0430 \u0447\u0438\u0442\u0430\u0435\u0442 \u0446\u0435\u043B\u0438\u043A\u043E\u043C \u0437\u0430 \u043E\u0434\u0438\u043D \u043F\u0440\u043E\u0445\u043E\u0434 \u0438 KV-\u043A\u0435\u0448 \u043D\u0435 \u0445\u0440\u0430\u043D\u0438\u0442, \u043F\u043E\u044D\u0442\u043E\u043C\u0443 \u043F\u0430\u043C\u044F\u0442\u044C \u0437\u0430\u0432\u0438\u0441\u0438\u0442 \u043E\u0442 \xAB\u041A\u043E\u043D\u0442\u0435\u043A\u0441\u0442\u0430\xBB. \u041E\u0441\u0442\u0430\u0432\u044C\u0442\u0435 f16.").addDropdown((d) => d.addOptions(kvOpts).setValue(p.kv_cache).onChange((v) => {
      p.kv_cache = v;
      upd();
    }));
    const cores = hw?.cores || null;
    const ts = new import_obsidian3.Setting(el).setName("\u041F\u043E\u0442\u043E\u043A\u043E\u0432 \u043F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440\u0430").setDesc("0 \u2014 llama.cpp \u0440\u0435\u0448\u0438\u0442 \u0441\u0430\u043C." + (cores ? ` \u0423 \u044D\u0442\u043E\u0433\u043E \u043A\u043E\u043C\u043F\u044C\u044E\u0442\u0435\u0440\u0430 ${cores} ${plural(cores, ["\u044F\u0434\u0440\u043E", "\u044F\u0434\u0440\u0430", "\u044F\u0434\u0435\u0440"])}${hw?.threads ? ` (${hw.threads} ${plural(hw.threads, ["\u043F\u043E\u0442\u043E\u043A", "\u043F\u043E\u0442\u043E\u043A\u0430", "\u043F\u043E\u0442\u043E\u043A\u043E\u0432"])})` : ""} \u2014 \u043E\u0431\u044B\u0447\u043D\u043E \u0431\u044B\u0441\u0442\u0440\u0435\u0435 \u0432\u0441\u0435\u0433\u043E, \u043A\u043E\u0433\u0434\u0430 \u043F\u043E\u0442\u043E\u043A\u043E\u0432 \u0441\u0442\u043E\u043B\u044C\u043A\u043E \u0436\u0435, \u0441\u043A\u043E\u043B\u044C\u043A\u043E \u044F\u0434\u0435\u0440.` : ""));
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
    if (cores) ts.addButton((b) => b.setButtonText("\u041F\u043E \u044F\u0434\u0440\u0430\u043C").setTooltip(`${cores}`).onClick(() => {
      p.threads = cores;
      if (thrInput) thrInput.value = String(cores);
      upd();
    }));
    this.numField(el, "\u041F\u043E\u0440\u0442", "\u0410\u0434\u0440\u0435\u0441 \u0441\u0435\u0440\u0432\u0435\u0440\u0430 \u0431\u0443\u0434\u0435\u0442 http://127.0.0.1:<\u043F\u043E\u0440\u0442>/v1 \u2014 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0432\u043F\u0438\u0448\u0435\u0442 \u0435\u0433\u043E \u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u0441\u0430\u043C\u0430.", "port");
    this.numField(el, "\u0412\u044B\u0433\u0440\u0443\u0436\u0430\u0442\u044C \u0438\u0437 \u043F\u0430\u043C\u044F\u0442\u0438 \u043F\u043E\u0441\u043B\u0435 \u043F\u0440\u043E\u0441\u0442\u043E\u044F, \u043C\u0438\u043D\u0443\u0442", "\u041F\u043E\u0441\u043B\u0435 \u043F\u0440\u043E\u0441\u0442\u043E\u044F \u0441\u0435\u0440\u0432\u0435\u0440 \u043E\u0442\u043F\u0443\u0441\u043A\u0430\u0435\u0442 \u043F\u0430\u043C\u044F\u0442\u044C, \u0437\u0430\u043D\u044F\u0442\u0443\u044E \u043C\u043E\u0434\u0435\u043B\u044C\u044E, \u0438 \u0437\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u0442 \u0435\u0451 \u0441\u043D\u043E\u0432\u0430 \u043F\u0440\u0438 \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0435\u043C \u0437\u0430\u043F\u0440\u043E\u0441\u0435 (\u043D\u0435\u0441\u043A\u043E\u043B\u044C\u043A\u043E \u0441\u0435\u043A\u0443\u043D\u0434). 0 \u2014 \u043D\u0435 \u0432\u044B\u0433\u0440\u0443\u0436\u0430\u0442\u044C.", "sleep_min");
    new import_obsidian3.Setting(el).setName("\u0417\u0430\u043F\u0443\u0441\u043A\u0430\u0442\u044C \u0441\u0430\u043C\u043E\u0439, \u043A\u043E\u0433\u0434\u0430 \u043D\u0443\u0436\u043D\u0430").setDesc("\u0415\u0441\u043B\u0438 \u0441\u0435\u0440\u0432\u0435\u0440 \u043D\u0435 \u0437\u0430\u043F\u0443\u0449\u0435\u043D (\u043D\u0430\u043F\u0440\u0438\u043C\u0435\u0440, \u043F\u043E\u0441\u043B\u0435 \u043F\u0435\u0440\u0435\u0437\u0430\u0433\u0440\u0443\u0437\u043A\u0438 \u043A\u043E\u043C\u043F\u044C\u044E\u0442\u0435\u0440\u0430), \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442 \u0435\u0433\u043E \u0441 \u044D\u0442\u0438\u043C\u0438 \u043F\u0430\u0440\u0430\u043C\u0435\u0442\u0440\u0430\u043C\u0438 \u043F\u0440\u0438 \u0424\u0430\u0437\u0435 1 \u0438\u043B\u0438 \xAB\u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u0441\u0432\u044F\u0437\u044C\xBB.").addToggle((t) => t.setValue(p.autostart).onChange((v) => {
      p.autostart = v;
    }));
    const md = new import_obsidian3.Setting(el).setName("\u041F\u0430\u043F\u043A\u0430 \u043C\u043E\u0434\u0435\u043B\u0438").setDesc(`\u041F\u0443\u0441\u0442\u043E \u2014 ${st.default_models_dir}. \u041C\u043E\u0434\u0435\u043B\u044C \u0432\u0435\u0441\u0438\u0442 ${sizeText(st.model.size)}.`);
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
  /** Сколько памяти (ГБ) займёт модель с этим контекстом — по замерам программы (st.need_gb). */
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
  /** Предупреждения (память, видеокарта), что будет скачано, место на диске. */
  renderNotes() {
    const el = this.noteEl;
    el.empty();
    const p = this.p;
    const st = this.st;
    const hw = this.hw;
    const min = st.min_ram_gb || 16;
    const mem = this.needGb(p.ctx) || st.vram_gb || 8;
    const withCtx = `\u0441 \u043A\u043E\u043D\u0442\u0435\u043A\u0441\u0442\u043E\u043C ${p.ctx.toLocaleString("ru-RU")} \u043C\u043E\u0434\u0435\u043B\u044C \u0437\u0430\u0439\u043C\u0451\u0442 \u043E\u043A\u043E\u043B\u043E ${gb(mem)} \u0413\u0411`;
    if (p.device === "cpu") {
      const ram = hw?.ram_gb ?? null;
      if (ram !== null && Math.round(ram) < min)
        el.createDiv({ cls: "vm-callout is-bad vm-llama-ram", text: `\u26A0 \u041C\u0430\u043B\u043E \u043F\u0430\u043C\u044F\u0442\u0438: \u0443 \u043A\u043E\u043C\u043F\u044C\u044E\u0442\u0435\u0440\u0430 ${gb(ram)} \u0413\u0411, \u0430 \u044D\u0442\u043E\u0439 \u043C\u043E\u0434\u0435\u043B\u0438 \u043D\u0430 \u043F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440\u0435 \u043D\u0443\u0436\u043D\u043E \u043C\u0438\u043D\u0438\u043C\u0443\u043C ${min} \u0413\u0411 \u043E\u043F\u0435\u0440\u0430\u0442\u0438\u0432\u043D\u043E\u0439 \u043F\u0430\u043C\u044F\u0442\u0438 (${withCtx}). \u0412\u043E\u0437\u043C\u043E\u0436\u043D\u044B \u0441\u0438\u043B\u044C\u043D\u044B\u0435 \u0437\u0430\u043C\u0435\u0434\u043B\u0435\u043D\u0438\u044F \u0438 \u043E\u0448\u0438\u0431\u043A\u0438 \u043D\u0435\u0445\u0432\u0430\u0442\u043A\u0438 \u043F\u0430\u043C\u044F\u0442\u0438.` + (hw?.gpus.length ? " \u041B\u0443\u0447\u0448\u0435 \u0432\u044B\u0431\u0440\u0430\u0442\u044C \xAB\u0412\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u0430\xBB." : "") });
      else if (ram !== null && mem > ram - 2)
        el.createDiv({ cls: "vm-callout is-bad vm-llama-ram", text: `\u26A0 \u041D\u0435 \u0445\u0432\u0430\u0442\u0438\u0442 \u043F\u0430\u043C\u044F\u0442\u0438: ${withCtx}, \u0430 \u0443 \u043A\u043E\u043C\u043F\u044C\u044E\u0442\u0435\u0440\u0430 ${gb(ram)} \u0413\u0411. \u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u043A\u043E\u043D\u0442\u0435\u043A\u0441\u0442 \u043F\u043E\u043C\u0435\u043D\u044C\u0448\u0435.` });
      else
        el.createDiv({ cls: "vm-callout is-warning vm-llama-ram", text: `\u26A0 \u042D\u0442\u043E\u0439 \u043C\u043E\u0434\u0435\u043B\u0438 \u043D\u0430 \u043F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440\u0435 \u043D\u0443\u0436\u043D\u043E \u043C\u0438\u043D\u0438\u043C\u0443\u043C ${min} \u0413\u0411 \u043E\u043F\u0435\u0440\u0430\u0442\u0438\u0432\u043D\u043E\u0439 \u043F\u0430\u043C\u044F\u0442\u0438` + (ram !== null ? ` \u2014 \u0443 \u044D\u0442\u043E\u0433\u043E \u043A\u043E\u043C\u043F\u044C\u044E\u0442\u0435\u0440\u0430 ${gb(ram)} \u0413\u0411` : " (\u0441\u043A\u043E\u043B\u044C\u043A\u043E \u0435\u0451 \u0443 \u044D\u0442\u043E\u0433\u043E \u043A\u043E\u043C\u043F\u044C\u044E\u0442\u0435\u0440\u0430, \u0443\u0437\u043D\u0430\u0442\u044C \u043D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C)") + `; ${withCtx}. \u041D\u0430 \u043F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440\u0435 \u043C\u043E\u0434\u0435\u043B\u044C \u0441\u0447\u0438\u0442\u0430\u0435\u0442 \u0437\u0430\u043C\u0435\u0442\u043D\u043E \u043C\u0435\u0434\u043B\u0435\u043D\u043D\u0435\u0435, \u0447\u0435\u043C \u043D\u0430 \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u0435.` });
    } else if (hw) {
      const vram = Math.max(0, ...hw.gpus.map((g) => g.vram_gb || 0));
      if (!hw.gpus.length) el.createDiv({ cls: "vm-callout is-warning", text: "\u0412\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u0430 \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u0430. \u0415\u0441\u043B\u0438 \u043E\u043D\u0430 \u0435\u0441\u0442\u044C \u2014 \u043E\u0431\u043D\u043E\u0432\u0438\u0442\u0435 \u0435\u0451 \u0434\u0440\u0430\u0439\u0432\u0435\u0440; \u0438\u043D\u0430\u0447\u0435 \u0432\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \xAB\u041F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440\xBB." });
      else if (vram && vram < mem)
        el.createDiv({ cls: "vm-callout", text: `\u0412\u0438\u0434\u0435\u043E\u043F\u0430\u043C\u044F\u0442\u0438 ${gb(vram)} \u0413\u0411, \u0430 ${withCtx}: \u0447\u0430\u0441\u0442\u044C \u0441\u043B\u043E\u0451\u0432 \u043E\u0441\u0442\u0430\u043D\u0435\u0442\u0441\u044F \u0432 \u043E\u043F\u0435\u0440\u0430\u0442\u0438\u0432\u043D\u043E\u0439 \u043F\u0430\u043C\u044F\u0442\u0438 \u2014 \u044D\u0442\u043E \u043C\u0435\u0434\u043B\u0435\u043D\u043D\u0435\u0435, \u043D\u043E \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 (\xAB\u0421\u043A\u043E\u043B\u044C\u043A\u043E \u043F\u043E\u043C\u0435\u0441\u0442\u0438\u0442\u0441\u044F\xBB \u043F\u043E\u0434\u0431\u0435\u0440\u0451\u0442 \u0441\u0430\u043C). \u041C\u0435\u043D\u044C\u0448\u0438\u0439 \u043A\u043E\u043D\u0442\u0435\u043A\u0441\u0442 \u2014 \u0431\u043E\u043B\u044C\u0448\u0435 \u0441\u043B\u043E\u0451\u0432 \u043D\u0430 \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u0435.` });
      else el.createDiv({ cls: "vm-callout is-ok", text: `\u041C\u043E\u0434\u0435\u043B\u0438 \u043D\u0443\u0436\u043D\u043E \u043E\u043A\u043E\u043B\u043E ${gb(mem)} \u0413\u0411 \u0432\u0438\u0434\u0435\u043E\u043F\u0430\u043C\u044F\u0442\u0438 (\u043A\u043E\u043D\u0442\u0435\u043A\u0441\u0442 ${p.ctx.toLocaleString("ru-RU")})` + (vram ? ` \u2014 \u0443 \u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u044B ${gb(vram)} \u0413\u0411.` : ".") });
    }
    const items = [];
    let need = 0;
    const m = st.model;
    const savedDir = (st.params.models_dir || "").trim();
    if ((p.models_dir || "").trim() !== savedDir) items.push(`\u041C\u043E\u0434\u0435\u043B\u044C \u2014 \u0432 \u043D\u043E\u0432\u043E\u0439 \u043F\u0430\u043F\u043A\u0435: \u0435\u0441\u043B\u0438 \u0435\u0451 \u0442\u0430\u043C \u043D\u0435\u0442, \u0441\u043A\u0430\u0447\u0430\u0435\u0442\u0441\u044F (${sizeText(m.size)})`);
    else if (!m.exists) {
      const left = Math.max(0, m.size - (m.partial || 0));
      need += left;
      items.push(m.partial ? `\u041C\u043E\u0434\u0435\u043B\u044C ${m.title} \u2014 \u0435\u0449\u0451 ${sizeText(left)} (\u0443\u0436\u0435 \u0441\u043A\u0430\u0447\u0430\u043D\u043E ${sizeText(m.partial)})` : `\u041C\u043E\u0434\u0435\u043B\u044C ${m.title} \u2014 ${sizeText(m.size)}`);
    }
    const b = llamaBuildFor(st, p, !!hw?.nvidia);
    if (!b.have) items.push(`llama.cpp (${LLAMA_BUILD_RU[b.build] || b.build}) \u2014 \u043E\u043A\u043E\u043B\u043E ${st.approx_mb?.[b.build] || 30} \u041C\u0411` + (b.build === "cuda" ? " \u0432\u043C\u0435\u0441\u0442\u0435 \u0441 \u0431\u0438\u0431\u043B\u0438\u043E\u0442\u0435\u043A\u0430\u043C\u0438 CUDA" : ""));
    if (st.vcredist_missing) items.push(`\u0411\u0438\u0431\u043B\u0438\u043E\u0442\u0435\u043A\u0438 Microsoft Visual C++ \u2014 \u043E\u043A\u043E\u043B\u043E ${st.approx_mb?.vcredist || 25} \u041C\u0411 (Windows \u0441\u043F\u0440\u043E\u0441\u0438\u0442 \u0440\u0430\u0437\u0440\u0435\u0448\u0435\u043D\u0438\u0435 \u043D\u0430 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0443)`);
    const box = el.createDiv({ cls: "vm-llama-plan" });
    if (items.length) {
      box.createDiv({ cls: "vm-llama-plan-title", text: "\u0411\u0443\u0434\u0435\u0442 \u0441\u043A\u0430\u0447\u0430\u043D\u043E (\u043E\u0434\u0438\u043D \u0440\u0430\u0437):" });
      const ul = box.createEl("ul");
      for (const it of items) ul.createEl("li", { text: it });
      if (need && m.free != null && m.free < need + 3e8)
        box.createDiv({ cls: "vm-callout is-warning", text: `\u041D\u0430 \u0434\u0438\u0441\u043A\u0435 \u0441\u0432\u043E\u0431\u043E\u0434\u043D\u043E ${sizeText(m.free)} \u2014 \u043C\u043E\u0434\u0435\u043B\u044C \u043D\u0435 \u043F\u043E\u043C\u0435\u0441\u0442\u0438\u0442\u0441\u044F. \u041E\u0441\u0432\u043E\u0431\u043E\u0434\u0438\u0442\u0435 \u043C\u0435\u0441\u0442\u043E \u0438\u043B\u0438 \u0443\u043A\u0430\u0436\u0438\u0442\u0435 \u0434\u0440\u0443\u0433\u0443\u044E \u043F\u0430\u043F\u043A\u0443 \u043C\u043E\u0434\u0435\u043B\u0438.` });
      else if (need) box.createDiv({ cls: "vm-muted vm-small-text", text: "\u0425\u043E\u0434 \u0441\u043A\u0430\u0447\u0438\u0432\u0430\u043D\u0438\u044F \u2014 \u0432 \u043F\u0430\u043D\u0435\u043B\u0438 \xAB\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433\xBB; \xAB\u0421\u0442\u043E\u043F\xBB \u043F\u0440\u0435\u0440\u044B\u0432\u0430\u0435\u0442, \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0438\u0439 \u0437\u0430\u043F\u0443\u0441\u043A \u0434\u043E\u043A\u0430\u0447\u0430\u0435\u0442 \u0441 \u0442\u043E\u0433\u043E \u0436\u0435 \u043C\u0435\u0441\u0442\u0430." });
    } else box.createDiv({ cls: "vm-muted", text: "\u0412\u0441\u0451 \u043D\u0443\u0436\u043D\u043E\u0435 \u0443\u0436\u0435 \u0441\u043A\u0430\u0447\u0430\u043D\u043E." });
    const port = p.port > 0 ? p.port : "?";
    el.createDiv({ cls: "vm-muted vm-small-text", text: `\u0410\u0434\u0440\u0435\u0441 \u0441\u0435\u0440\u0432\u0435\u0440\u0430: http://127.0.0.1:${port}/v1 \u2014 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0432\u043F\u0438\u0448\u0435\u0442 \u0435\u0433\u043E \u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u0441\u0430\u043C\u0430.` });
  }
  go() {
    const p = this.p;
    const errs = [];
    const int = (v, lo, hi) => typeof v === "number" && Number.isInteger(v) && v >= lo && v <= hi;
    if (!int(p.port, 1024, 65535)) errs.push("\u043F\u043E\u0440\u0442 \u2014 \u0447\u0438\u0441\u043B\u043E \u043E\u0442 1024 \u0434\u043E 65535");
    if (!int(p.threads, 0, 1024)) errs.push("\u043F\u043E\u0442\u043E\u043A\u043E\u0432 \u2014 \u0447\u0438\u0441\u043B\u043E \u043E\u0442 0 \u0434\u043E 1024");
    if (!int(p.sleep_min, 0, 10080)) errs.push("\u043F\u0440\u043E\u0441\u0442\u043E\u0439 \u2014 \u0447\u0438\u0441\u043B\u043E \u043C\u0438\u043D\u0443\u0442 \u043E\u0442 0 \u0434\u043E 10080");
    if (typeof p.gpu_layers === "number" && !int(p.gpu_layers, 0, 999)) errs.push("\u0441\u043B\u043E\u0451\u0432 \u2014 \u0447\u0438\u0441\u043B\u043E \u043E\u0442 0 \u0434\u043E 999");
    if (errs.length) {
      new import_obsidian3.Notice("\u041F\u0440\u043E\u0432\u0435\u0440\u044C\u0442\u0435: " + errs.join("; ") + ".", 8e3);
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
var FIXED_SOURCES = { \u0430\u0440\u0445\u0438\u0432: "\u0441\u0442\u0430\u0440\u044B\u0435 \u0437\u0430\u043F\u0438\u0441\u0438: _staging/\u0430\u0440\u0445\u0438\u0432", \u0437\u0430\u043C\u0435\u0442\u043A\u0430: "\u0444\u0430\u0439\u043B\u044B \u043F\u0440\u044F\u043C\u043E \u0432 _staging" };
var TAB_ORDER = ["main", "models", "thresholds", "input", "docs", "costs", "advanced"];
var TAB_NAMES = {
  main: "\u041E\u0441\u043D\u043E\u0432\u043D\u043E\u0435",
  models: "\u041C\u043E\u0434\u0435\u043B\u0438",
  thresholds: "\u041F\u043E\u0440\u043E\u0433\u0438",
  input: "\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0435",
  docs: "\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B",
  costs: "\u0420\u0430\u0441\u0445\u043E\u0434\u044B",
  advanced: "\u0414\u043E\u043F\u043E\u043B\u043D\u0438\u0442\u0435\u043B\u044C\u043D\u043E"
};
function tabOfError(msg) {
  const m = msg.trim().toLowerCase();
  if (/^llm\.(webchat|max_format_retries)|^limits\./.test(m)) return "advanced";
  if (/^(профиль|llm\.|embeddings\.)/.test(m)) return "models";
  if (/^(thresholds\.|seed_dormancy_days)/.test(m)) return "thresholds";
  if (/^(budget\.|estimate\.)/.test(m)) return "costs";
  if (/^(sources|dialogue_markers|input\.)/.test(m)) return "input";
  if (/^style\./.test(m)) return "docs";
  return "main";
}
function fmt(v) {
  if (v === null || v === void 0 || v === "") return "\u043F\u0443\u0441\u0442\u043E";
  if (typeof v === "boolean") return v ? "\u0432\u043A\u043B." : "\u0432\u044B\u043A\u043B.";
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
    // не navEl и не renderTab: эти имена Obsidian 1.13+ использует внутри SettingTab (пункт меню слева и отрисовка вкладки)
    this.barEl = null;
    this.bodyEl = null;
    this.dynEl = null;
    this.statusEl = null;
    this.progTimer = null;
    this.lastProblem = null;
    // своя модель эмбеддингов (llama.cpp)
    this.llamaSt = null;
    this.llamaBusy = false;
    this.llamaFresh = false;
    this.llamaAgain = false;
    this.llamaWasBusy = false;
    this.llamaLive = null;
    this.llamaTimer = null;
  }
  /** Obsidian открыл вкладку настроек: показать сохранённое и перечитать settings.yaml. */
  display() {
    this.llamaFresh = false;
    try {
      this.redraw();
    } catch (e) {
      this.containerEl.empty();
      renderError(this.containerEl.createDiv({ cls: "vm-settings" }), this.plugin, "\u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438", e);
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
  /** Программа сама поменяла настройки (например, «Запустить модель…» вписала адрес сервера) — перечитать. */
  reload() {
    this.llamaFresh = false;
    if (!this.containerEl.isConnected) return;
    if (!this.plugin.engine.problem()) this.load();
    this.loadLlama();
  }
  /** Открыть настройки на нужной вкладке (из панели). */
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
  // ---------- вкладки и поиск ----------
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
      if (bad.has(id)) b.setAttr("title", "\u0417\u0434\u0435\u0441\u044C \u043E\u0448\u0438\u0431\u043A\u0430 \u2014 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u043D\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u044B");
      b.addEventListener("click", () => {
        this.tab = id;
        this.query = "";
        this.renderNav();
        this.renderBody();
        this.containerEl.scrollTop = 0;
      });
    }
    const search = nav.createEl("input", { type: "search", cls: "vm-set-search", attr: { placeholder: "\u041F\u043E\u0438\u0441\u043A \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438\u2026", "aria-label": "\u041F\u043E\u0438\u0441\u043A \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438" } });
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
    return this.query.trim() ? "\u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438, \u043F\u043E\u0438\u0441\u043A" : `\u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438, \u0432\u043A\u043B\u0430\u0434\u043A\u0430 \xAB${this.tabNames()[tab] || tab}\xBB`;
  }
  /** Перерисовать изменчивую часть вкладки (поле «Папка программы» при этом не теряет фокус). */
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
    for (const e of this.errors.filter((x) => x.tab === tab)) el.createDiv({ cls: "vm-callout is-warning", text: "\u041D\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u043E: " + e.text });
    if (this.plugin.engine.problem()) {
      if (tab !== "main") el.createDiv({ cls: "vm-callout is-warning", text: "\u0421\u043D\u0430\u0447\u0430\u043B\u0430 \u0443\u043A\u0430\u0436\u0438\u0442\u0435 \u043F\u0430\u043F\u043A\u0443 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B \u2014 \u0432\u043A\u043B\u0430\u0434\u043A\u0430 \xAB\u041E\u0441\u043D\u043E\u0432\u043D\u043E\u0435\xBB." });
      return;
    }
    if (!this.info || !this.values) {
      el.createDiv({ cls: this.loadError ? "vm-callout is-warning" : "vm-muted", text: this.loadError || "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u044E \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B\u2026" });
      if (this.loadError) new import_obsidian4.Setting(el).addButton((b) => b.setButtonText("\u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C").onClick(() => this.load()));
      return;
    }
    for (const sec of this.info.schema.filter((s) => (s.tab || "advanced") === tab)) this.renderSection(el, sec);
    if (tab === "models") {
      new import_obsidian4.Setting(el).setName("\u041F\u0440\u043E\u0432\u0435\u0440\u043A\u0430 \u0441\u0432\u044F\u0437\u0438").setDesc("\u041E\u0441\u043D\u043E\u0432\u043D\u0430\u044F \u043C\u043E\u0434\u0435\u043B\u044C, \u043C\u043E\u0434\u0435\u043B\u0438 \u043E\u0442\u0434\u0435\u043B\u044C\u043D\u044B\u0445 \u0448\u0430\u0433\u043E\u0432 \u0438 \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u0438 \u2014 \u043A\u0430\u0436\u0434\u0430\u044F \u043E\u0442\u0434\u0435\u043B\u044C\u043D\u043E.").addButton((b) => b.setButtonText("\u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u0441\u0432\u044F\u0437\u044C").setCta().onClick(async () => {
        await this.flush();
        this.plugin.runCheck();
      }));
    }
    if (tab === "costs") {
      new import_obsidian4.Setting(el).setName("\u041F\u043E\u0434\u0440\u043E\u0431\u043D\u044B\u0435 \u0440\u0430\u0441\u0445\u043E\u0434\u044B").setDesc("\u041F\u043E \u043C\u043E\u0434\u0435\u043B\u044F\u043C, \u0448\u0430\u0433\u0430\u043C, \u0434\u043D\u044F\u043C \u0438 \u0437\u0430\u043F\u0443\u0441\u043A\u0430\u043C, \u0446\u0435\u043D\u044B \u043E\u0431\u043B\u0430\u0447\u043D\u044B\u0445 \u043F\u0440\u043E\u0444\u0438\u043B\u0435\u0439 \u2014 \u0432\u043A\u043B\u0430\u0434\u043A\u0430 \xAB\u0420\u0430\u0441\u0445\u043E\u0434\u044B\xBB \u043F\u0430\u043D\u0435\u043B\u0438 \xAB\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433\xBB.").addButton((b) => b.setButtonText("\u041E\u0442\u043A\u0440\u044B\u0442\u044C \xAB\u0420\u0430\u0441\u0445\u043E\u0434\u044B\xBB").onClick(async () => {
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
    if (!found) el.createDiv({ cls: "vm-muted vm-search-none", text: `\u041D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u043E \u043F\u043E \u0437\u0430\u043F\u0440\u043E\u0441\u0443 \xAB${this.query.trim()}\xBB.` });
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
    const r = await this.plugin.engine.run(["settings"], { label: "\u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438", exclusive: false, quiet: true });
    this.loading = false;
    if (r.ok && r.settings) {
      const changed = !this.info || JSON.stringify(r.settings) !== JSON.stringify(this.info);
      this.info = r.settings;
      if (!this.dirty.size) this.values = clone(r.settings.values);
      this.loadError = null;
      if (changed) this.redraw();
    } else {
      this.loadError = "\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043F\u0440\u043E\u0447\u0438\u0442\u0430\u0442\u044C \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B: " + (r.error || "\u043D\u0435\u0442 \u043E\u0442\u0432\u0435\u0442\u0430");
      this.redraw();
    }
  }
  // ---------- «Программа» и уведомления (настройки плагина) ----------
  renderProgram(el) {
    const p = this.plugin;
    const box = this.section(el, "\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430");
    new import_obsidian4.Setting(box).setName("\u041F\u0430\u043F\u043A\u0430 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B").setDesc("\u041F\u0430\u043F\u043A\u0430, \u0433\u0434\u0435 \u043B\u0435\u0436\u0430\u0442 \xAB\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0430.bat\xBB \u0438 \u043F\u0430\u043F\u043A\u0430 brain. \u0415\u0451 \u0432\u043F\u0438\u0441\u044B\u0432\u0430\u0435\u0442 \xAB\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0430.bat\xBB.").setClass("vm-wide-setting").addText((t) => t.setPlaceholder("C:\\\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433").setValue(p.data.programDir).onChange(async (v) => {
      p.data.programDir = v.trim();
      await p.saveData(p.data);
      this.programChanged();
    }));
    new import_obsidian4.Setting(box).setName("Python").setDesc("\u041E\u0431\u044B\u0447\u043D\u043E \u043C\u0435\u043D\u044F\u0442\u044C \u043D\u0435 \u043D\u0443\u0436\u043D\u043E: \u043F\u0443\u0441\u0442\u043E \u2014 Python, \u043A\u043E\u0442\u043E\u0440\u044B\u0439 \u043F\u043E\u0441\u0442\u0430\u0432\u0438\u043B\u0430 \xAB\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0430.bat\xBB.").setClass("vm-wide-setting").addText((t) => t.setPlaceholder(p.engine.defaultPython()).setValue(p.data.pythonPath).onChange(async (v) => {
      p.data.pythonPath = v.trim();
      await p.saveData(p.data);
      this.programChanged();
    }));
    this.statusEl = box.createDiv();
    this.renderStatus();
    new import_obsidian4.Setting(box).setName("\u041F\u0440\u043E\u0432\u0435\u0440\u043A\u0430 \u0441\u0432\u044F\u0437\u0438").setDesc("\u0425\u0440\u0430\u043D\u0438\u043B\u0438\u0449\u0435, \u043C\u043E\u0434\u0435\u043B\u044C (\u0434\u043B\u044F \u043A\u0430\u0436\u0434\u043E\u0439 \u043C\u043E\u0434\u0435\u043B\u0438 \u0448\u0430\u0433\u0430 \u2014 \u043E\u0442\u0434\u0435\u043B\u044C\u043D\u043E) \u0438 \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u0438.").addButton((b) => b.setButtonText("\u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u0441\u0432\u044F\u0437\u044C").setCta().onClick(async () => {
      await this.flush();
      p.runCheck();
    }));
  }
  renderNotify(el) {
    const p = this.plugin;
    const d = p.data;
    const save = () => p.saveData(d);
    const box = this.section(el, "\u0423\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u044F Windows", "\u0421\u0438\u0441\u0442\u0435\u043C\u043D\u044B\u0435 \u0443\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u044F \u2014 \u043A\u043E\u0433\u0434\u0430 Obsidian \u0441\u0432\u0451\u0440\u043D\u0443\u0442 \u0438\u043B\u0438 \u0432\u044B \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442\u0435 \u0432 \u0434\u0440\u0443\u0433\u043E\u043C \u043E\u043A\u043D\u0435.");
    new import_obsidian4.Setting(box).setName("\u0421\u043E\u043E\u0431\u0449\u0430\u0442\u044C \u043E\u0431 \u043E\u043A\u043E\u043D\u0447\u0430\u043D\u0438\u0438 \u0434\u043E\u043B\u0433\u043E\u0433\u043E \u0437\u0430\u043F\u0443\u0441\u043A\u0430").setDesc("\u0424\u0430\u0437\u0430 1, \u0424\u0430\u0437\u0430 2, \u0440\u0435\u0432\u0430\u043B\u0438\u0434\u0430\u0446\u0438\u044F \u2014 \u0435\u0441\u043B\u0438 \u0437\u0430\u043F\u0443\u0441\u043A \u0448\u0451\u043B \u0434\u043E\u043B\u044C\u0448\u0435, \u0447\u0435\u043C \u0443\u043A\u0430\u0437\u0430\u043D\u043E \u043D\u0438\u0436\u0435.").addToggle((t) => t.setValue(d.notify).onChange(async (v) => {
      d.notify = v;
      await save();
    }));
    const m = new import_obsidian4.Setting(box).setName("\u0414\u043E\u043B\u0433\u0438\u0439 \u0437\u0430\u043F\u0443\u0441\u043A \u2014 \u0434\u043E\u043B\u044C\u0448\u0435, \u043C\u0438\u043D\u0443\u0442").setDesc("0 \u2014 \u0441\u043E\u043E\u0431\u0449\u0430\u0442\u044C \u043E \u043B\u044E\u0431\u043E\u043C \u0437\u0430\u043F\u0443\u0441\u043A\u0435.");
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
    new import_obsidian4.Setting(box).setName("\u0421\u043E\u043E\u0431\u0449\u0430\u0442\u044C, \u043A\u043E\u0433\u0434\u0430 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0436\u0434\u0451\u0442 \u043E\u0442\u0432\u0435\u0442\u0430").setDesc("\u041D\u0430\u043F\u0440\u0438\u043C\u0435\u0440: \u0431\u044E\u0434\u0436\u0435\u0442 \u0438\u0441\u0447\u0435\u0440\u043F\u0430\u043D \u0438\u043B\u0438 \u043D\u0443\u0436\u043D\u043E \u043F\u043E\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044C \u0431\u043E\u043B\u044C\u0448\u043E\u0439 \u0437\u0430\u043F\u0443\u0441\u043A.").addToggle((t) => t.setValue(d.notifyAsk).onChange(async (v) => {
      d.notifyAsk = v;
      await save();
    }));
    new import_obsidian4.Setting(box).setName("\u0422\u043E\u043B\u044C\u043A\u043E \u043A\u043E\u0433\u0434\u0430 Obsidian \u043D\u0435 \u0432 \u0444\u043E\u043A\u0443\u0441\u0435").setDesc("\u0412\u044B\u043A\u043B\u044E\u0447\u0438\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u0443\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u044F \u043F\u0440\u0438\u0445\u043E\u0434\u0438\u043B\u0438 \u0432\u0441\u0435\u0433\u0434\u0430.").addToggle((t) => t.setValue(d.notifyUnfocused).onChange(async (v) => {
      d.notifyUnfocused = v;
      await save();
    }));
    new import_obsidian4.Setting(box).setName("\u041F\u0440\u043E\u0431\u043D\u043E\u0435 \u0443\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u0435").setDesc("\u0415\u0441\u043B\u0438 \u043E\u043D\u043E \u043D\u0435 \u043F\u043E\u044F\u0432\u0438\u043B\u043E\u0441\u044C \u2014 \u0440\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u0435 \u0443\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u044F \u0434\u043B\u044F Obsidian \u0432 \u043F\u0430\u0440\u0430\u043C\u0435\u0442\u0440\u0430\u0445 Windows (\u0421\u0438\u0441\u0442\u0435\u043C\u0430 \u2192 \u0423\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u044F).").addButton((b) => b.setButtonText("\u041F\u043E\u043A\u0430\u0437\u0430\u0442\u044C").onClick(() => {
      const ok = p.osNotify("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433", "\u0422\u0430\u043A \u0432\u044B\u0433\u043B\u044F\u0434\u0438\u0442 \u0443\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u0435 \u043E\u0431 \u043E\u043A\u043E\u043D\u0447\u0430\u043D\u0438\u0438 \u0434\u043E\u043B\u0433\u043E\u0433\u043E \u0437\u0430\u043F\u0443\u0441\u043A\u0430.", "done", true);
      if (!ok) new import_obsidian4.Notice("\u0421\u0438\u0441\u0442\u0435\u043C\u0430 \u043D\u0435 \u0434\u0430\u043B\u0430 \u043F\u043E\u043A\u0430\u0437\u0430\u0442\u044C \u0443\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u0435: \u0440\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u0435 \u0443\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u044F \u0434\u043B\u044F Obsidian \u0432 \u043F\u0430\u0440\u0430\u043C\u0435\u0442\u0440\u0430\u0445 Windows.", 1e4);
    }));
  }
  renderUpdateButtons(el) {
    const skip = this.plugin.data.skipVersion;
    const repo = (this.info?.update_repo || "").trim();
    new import_obsidian4.Setting(el).setName("\u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u0441\u0435\u0439\u0447\u0430\u0441").setDesc(`\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u0430 \u0432\u0435\u0440\u0441\u0438\u044F ${this.info?.version || "?"}.` + (skip ? ` \u041F\u0440\u043E\u043F\u0443\u0449\u0435\u043D\u043D\u0430\u044F \u0432\u0435\u0440\u0441\u0438\u044F: ${skip} \u2014 \u043F\u0440\u0438 \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0435 \u043F\u043E \u043A\u043D\u043E\u043F\u043A\u0435 \u043E\u043D\u0430 \u043F\u0440\u0435\u0434\u043B\u0430\u0433\u0430\u0435\u0442\u0441\u044F \u0441\u043D\u043E\u0432\u0430.` : "") + (repo ? "" : " \u0412 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0443 \u043D\u0435 \u0432\u043F\u0438\u0441\u0430\u043D\u0430 \u0441\u0441\u044B\u043B\u043A\u0430 \u043D\u0430 \u0440\u0435\u043F\u043E\u0437\u0438\u0442\u043E\u0440\u0438\u0439 (brain/__init__.py, \u0441\u0442\u0440\u043E\u043A\u0430 UPDATE_REPO) \u2014 \u043F\u0440\u043E\u0432\u0435\u0440\u044F\u0442\u044C \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u044F \u043D\u0435\u0433\u0434\u0435.")).addButton((b) => {
      b.setButtonText("\u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u044F").onClick(async () => {
        await this.flush();
        this.plugin.checkUpdates(true);
      });
      if (!repo) b.setDisabled(true);
    });
  }
  // ---------- своя модель эмбеддингов (llama.cpp) ----------
  /** Состояние модели под «Где считать: на этом компьютере»: скачана ли, llama.cpp, сервер; кнопки запуска. */
  renderLlama(el) {
    const st = this.llamaSt;
    const box = el.createDiv({ cls: "vm-llama-box" });
    const s = new import_obsidian4.Setting(box).setName("\u0421\u0432\u043E\u044F \u043C\u043E\u0434\u0435\u043B\u044C");
    s.settingEl.addClass("vm-llama-setting");
    const d = s.descEl;
    if (!st) d.createDiv({ text: this.llamaBusy ? "\u041F\u0440\u043E\u0432\u0435\u0440\u044F\u044E, \u0441\u043A\u0430\u0447\u0430\u043D\u0430 \u043B\u0438 \u043C\u043E\u0434\u0435\u043B\u044C\u2026" : "KaLM-Embedding-Gemma3 12B \u043D\u0430 llama.cpp \u2014 \u0441\u043A\u0430\u0447\u0438\u0432\u0430\u0435\u0442\u0441\u044F \u0438 \u0437\u0430\u043F\u0443\u0441\u043A\u0430\u0435\u0442\u0441\u044F \u043A\u043D\u043E\u043F\u043A\u043E\u0439 \xAB\u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u043C\u043E\u0434\u0435\u043B\u044C\u2026\xBB." });
    else {
      const m = st.model;
      d.createDiv({ text: `${m.title}: ` + (m.exists ? "\u0441\u043A\u0430\u0447\u0430\u043D\u0430" : m.partial ? `\u0441\u043A\u0430\u0447\u0430\u043D\u043E ${sizeText(m.partial)} \u0438\u0437 ${sizeText(m.size)} \u2014 \u0434\u043E\u043A\u0430\u0447\u0430\u0435\u0442\u0441\u044F \u043F\u0440\u0438 \u0437\u0430\u043F\u0443\u0441\u043A\u0435` : `\u043D\u0435 \u0441\u043A\u0430\u0447\u0430\u043D\u0430 (${sizeText(m.size)}) \u2014 \u0441\u043A\u0430\u0447\u0430\u0435\u0442\u0441\u044F \u043F\u0440\u0438 \u0437\u0430\u043F\u0443\u0441\u043A\u0435`) });
      const names = Object.values(st.builds || {}).map((b) => `${LLAMA_BUILD_RU[b.build] || b.build}${b.tag ? ` (${b.tag})` : ""}`);
      d.createDiv({ text: "llama.cpp: " + (names.length ? names.join(", ") : st.system ? "\u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D \u043D\u0430 \u043A\u043E\u043C\u043F\u044C\u044E\u0442\u0435\u0440\u0435" : "\u043D\u0435 \u0441\u043A\u0430\u0447\u0430\u043D \u2014 \u0441\u043A\u0430\u0447\u0430\u0435\u0442\u0441\u044F \u043F\u0440\u0438 \u0437\u0430\u043F\u0443\u0441\u043A\u0435") });
      const srv = st.server;
      const dev = srv.params?.device === "gpu" ? "\u0432\u0438\u0434\u0435\u043E\u043A\u0430\u0440\u0442\u0430" : "\u043F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440";
      d.createDiv({
        cls: srv.running && srv.health === "ok" ? "vm-key-ok" : "",
        text: "\u0421\u0435\u0440\u0432\u0435\u0440: " + (srv.running ? `\u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 \u2014 ${srv.url} (${dev})` + (srv.health === "loading" ? ", \u0437\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u0442 \u043C\u043E\u0434\u0435\u043B\u044C" : srv.health == null ? ", \u043D\u0435 \u043E\u0442\u0432\u0435\u0447\u0430\u0435\u0442" : "") : "\u043D\u0435 \u0437\u0430\u043F\u0443\u0449\u0435\u043D" + (st.params.autostart && st.configured && m.exists ? " \u2014 \u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u0441\u044F \u0441\u0430\u043C, \u043A\u043E\u0433\u0434\u0430 \u043F\u043E\u043D\u0430\u0434\u043E\u0431\u0438\u0442\u0441\u044F" : ""))
      });
      if (!st.configured) d.createDiv({ cls: "vm-field-note", text: "\u0410\u0434\u0440\u0435\u0441 \u0441\u0435\u0440\u0432\u0435\u0440\u0430 \u043D\u0438\u0436\u0435 \u2014 \u043D\u0435 \u044D\u0442\u043E\u0442 \u0441\u0435\u0440\u0432\u0435\u0440. \xAB\u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u043C\u043E\u0434\u0435\u043B\u044C\u2026\xBB \u0432\u043F\u0438\u0448\u0435\u0442 \u0430\u0434\u0440\u0435\u0441 \u0441\u0430\u043C\u0430." });
    }
    const busy = !!this.llamaJob();
    s.addButton((b) => {
      b.setButtonText(st?.server.running ? "\u041F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C\u2026" : "\u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u043C\u043E\u0434\u0435\u043B\u044C\u2026").setCta().onClick(() => this.openLlama());
      if (busy) b.setDisabled(true);
    });
    if (st?.server.running)
      s.addButton((b) => b.setButtonText("\u041E\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C").setTooltip("\u041E\u0441\u0432\u043E\u0431\u043E\u0434\u0438\u0442\u044C \u043F\u0430\u043C\u044F\u0442\u044C. \u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442 \u0441\u0435\u0440\u0432\u0435\u0440 \u0441\u043D\u043E\u0432\u0430, \u043A\u043E\u0433\u0434\u0430 \u043E\u043D \u043F\u043E\u043D\u0430\u0434\u043E\u0431\u0438\u0442\u0441\u044F.").onClick(async () => {
        await this.plugin.runLlamaStop();
        this.loadLlama();
      }));
    if (st?.log) s.addExtraButton((b) => b.setIcon("file-text").setTooltip("\u0416\u0443\u0440\u043D\u0430\u043B \u0441\u0435\u0440\u0432\u0435\u0440\u0430 \u043C\u043E\u0434\u0435\u043B\u0438").onClick(() => this.showLlamaLog(st.log)));
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
  /** Ход запуска модели — прямо здесь (окно настроек закрывает панель «Второй мозг»). */
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
      el.createDiv({ text: "\u0417\u0430\u043F\u0443\u0441\u043A \u043C\u043E\u0434\u0435\u043B\u0438 \u2014 \u0432 \u043E\u0447\u0435\u0440\u0435\u0434\u0438: \u043D\u0430\u0447\u043D\u0451\u0442\u0441\u044F \u043F\u043E\u0441\u043B\u0435 \u0442\u0435\u043A\u0443\u0449\u0435\u0433\u043E \u0437\u0430\u043F\u0443\u0441\u043A\u0430." });
      return;
    }
    const info = liveInfo(job);
    el.createDiv({ cls: "vm-llama-live-text", text: (info.stage || job.lastLine || "\u0417\u0430\u043F\u0443\u0441\u043A\u0430\u044E\u2026") + (info.eta ? ` \xB7 ${info.eta}` : "") });
    if (info.frac !== null) {
      const bar = el.createDiv({ cls: "vm-bar" });
      bar.createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.round(info.frac * 1e3) / 10}%`;
    } else el.createDiv({ cls: "vm-progress" });
    const row = el.createDiv({ cls: "vm-llama-live-row" });
    row.createSpan({ cls: "vm-muted vm-small-text", text: job.stopAt ? "\u041E\u0441\u0442\u0430\u043D\u0430\u0432\u043B\u0438\u0432\u0430\u044E\u2026 \u0421\u043A\u0430\u0447\u0430\u043D\u043D\u043E\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u0441\u044F \u2014 \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0438\u0439 \u0437\u0430\u043F\u0443\u0441\u043A \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442." : "\u041C\u043E\u0436\u043D\u043E \u0437\u0430\u043A\u0440\u044B\u0442\u044C \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u2014 \u0445\u043E\u0434 \u0432\u0438\u0434\u0435\u043D \u0438 \u0432 \u043F\u0430\u043D\u0435\u043B\u0438 \xAB\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433\xBB." });
    if (!job.stopAt) {
      const stop = row.createEl("button", { text: "\u0421\u0442\u043E\u043F" });
      stop.addEventListener("click", () => this.plugin.engine.stop());
    }
  }
  async openLlama() {
    await this.flush();
    const st = await this.plugin.llamaStatus(false) || this.llamaSt;
    if (!st) {
      new import_obsidian4.Notice("\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043D\u0435 \u043E\u0442\u0432\u0435\u0442\u0438\u043B\u0430 \u2014 \u0441\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u0435 \u043C\u043E\u0434\u0435\u043B\u0438 \u043D\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043D\u043E. \u041F\u0440\u043E\u0432\u0435\u0440\u044C\u0442\u0435 \u043F\u0430\u043F\u043A\u0443 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B \u0432\u043E \u0432\u043A\u043B\u0430\u0434\u043A\u0435 \xAB\u041E\u0441\u043D\u043E\u0432\u043D\u043E\u0435\xBB.", 1e4);
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
      text = `\u0416\u0443\u0440\u043D\u0430\u043B \u043D\u0435 \u043F\u0440\u043E\u0447\u0438\u0442\u0430\u0442\u044C: ${e}`;
    }
    new TextModal(this.app, "\u0416\u0443\u0440\u043D\u0430\u043B \u0441\u0435\u0440\u0432\u0435\u0440\u0430 \u043C\u043E\u0434\u0435\u043B\u0438 (\u043F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435 \u0441\u0442\u0440\u043E\u043A\u0438)", text).open();
  }
  renderService(el) {
    const box = this.section(el, "\u0421\u043B\u0443\u0436\u0435\u0431\u043D\u043E\u0435");
    new import_obsidian4.Setting(box).setName("\u041F\u0440\u043E\u043C\u043F\u0442\u044B").setDesc("\u0422\u0435\u043A\u0441\u0442\u044B \u0437\u0430\u043F\u0440\u043E\u0441\u043E\u0432 \u043A \u043C\u043E\u0434\u0435\u043B\u0438 \u2014 \u0444\u0430\u0439\u043B\u044B \u0432 \u043F\u0430\u043F\u043A\u0435 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B. \u0418\u0445 \u043C\u043E\u0436\u043D\u043E \u043F\u0440\u0430\u0432\u0438\u0442\u044C; \u0438\u0437\u043C\u0435\u043D\u0435\u043D\u0438\u044F \u043F\u043E\u0434\u0435\u0439\u0441\u0442\u0432\u0443\u044E\u0442 \u0441\u043E \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0435\u0433\u043E \u0437\u0430\u043F\u0443\u0441\u043A\u0430. \u041F\u0440\u0438 \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0438 \u0432\u0430\u0448\u0438 \u043F\u0440\u0430\u0432\u043A\u0438 \u043D\u0435 \u0442\u0435\u0440\u044F\u044E\u0442\u0441\u044F.").addButton((b) => b.setButtonText("\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u043F\u0430\u043F\u043A\u0443 \u043F\u0440\u043E\u043C\u043F\u0442\u043E\u0432").onClick(() => this.plugin.revealPath(this.info.prompts_dir)));
    new import_obsidian4.Setting(box).setName("\u0424\u0430\u0439\u043B \u043D\u0430\u0441\u0442\u0440\u043E\u0435\u043A").setDesc(`${this.info.path} \u2014 \u043F\u043B\u0430\u0433\u0438\u043D \u043F\u0435\u0440\u0435\u043F\u0438\u0441\u044B\u0432\u0430\u0435\u0442 \u0435\u0433\u043E \u0446\u0435\u043B\u0438\u043A\u043E\u043C \u0441 \u043F\u043E\u044F\u0441\u043D\u0435\u043D\u0438\u044F\u043C\u0438, \u043F\u0440\u0435\u0436\u043D\u0438\u0439 \u0441\u043E\u0445\u0440\u0430\u043D\u044F\u0435\u0442\u0441\u044F \u0432 settings.yaml.bak.`).addButton((b) => b.setButtonText("\u041F\u043E\u043A\u0430\u0437\u0430\u0442\u044C \u0432 \u043F\u0430\u043F\u043A\u0435").onClick(() => this.plugin.revealPath(this.info.path, true)));
    new import_obsidian4.Setting(box).setName("\u041E\u0442\u0447\u0451\u0442 \u0434\u043B\u044F \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u0447\u0438\u043A\u0430").setDesc("\u0415\u0441\u043B\u0438 \u0447\u0442\u043E-\u0442\u043E \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 \u043D\u0435 \u0442\u0430\u043A: \u0432\u0435\u0440\u0441\u0438\u0438, \u043F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435 \u043E\u0448\u0438\u0431\u043A\u0438 \u0438 \u0432\u044B\u0432\u043E\u0434 \u043F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0445 \u0437\u0430\u043F\u0443\u0441\u043A\u043E\u0432 \u2014 \u0432 \u0444\u0430\u0439\u043B _\u043B\u043E\u0433\u0438/\u043E\u0442\u0447\u0451\u0442 \u0434\u043B\u044F \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u0447\u0438\u043A\u0430.md \u0438 \u0432 \u0431\u0443\u0444\u0435\u0440 \u043E\u0431\u043C\u0435\u043D\u0430. \u041A\u043B\u044E\u0447\u0435\u0439 API \u0438 \u0442\u0435\u043A\u0441\u0442\u043E\u0432 \u0437\u0430\u043C\u0435\u0442\u043E\u043A \u0432 \u043D\u0451\u043C \u043D\u0435\u0442.").addButton((b) => b.setButtonText("\u0421\u043E\u0431\u0440\u0430\u0442\u044C \u043E\u0442\u0447\u0451\u0442").onClick(async () => {
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
    el.setText(prob || `\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043D\u0430\u0439\u0434\u0435\u043D\u0430${this.info ? `, \u0432\u0435\u0440\u0441\u0438\u044F ${this.info.version}` : ""}. \u0425\u0440\u0430\u043D\u0438\u043B\u0438\u0449\u0435: ${this.plugin.engine.vaultPath()}`);
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
  // ---------- поля по схеме ----------
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
        new import_obsidian4.Setting(el).setName(f.label).setDesc(`${f.help} \u041F\u0440\u0430\u0432\u0438\u0442\u0441\u044F \u0432 settings.yaml.`);
    }
  }
  /** «↺» — вернуть значение по умолчанию. Видна всегда (ряд с ползунком не «прыгает», когда значение проходит через
   *  умолчание); пока значение равно умолчанию — тусклая и не нажимается. Возвращает функцию, которую поле вызывает
   *  на каждую правку (кнопка меняется сразу, без перерисовки). */
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
        comp.setTooltip(changed ? `\u0412\u0435\u0440\u043D\u0443\u0442\u044C \u043F\u043E \u0443\u043C\u043E\u043B\u0447\u0430\u043D\u0438\u044E: ${fmt(def)}` : `\u0423\u0436\u0435 \u043F\u043E \u0443\u043C\u043E\u043B\u0447\u0430\u043D\u0438\u044E: ${fmt(def)}`);
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
  /** Число: поле ввода, у порогов и температуры — ещё ползунок. «int?»/«float?» — можно оставить пустым. */
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
      err.setText(bad ? `\u041D\u0443\u0436\u043D\u043E ${rangeText(kind, f.min, f.max)}${optional ? " (\u0438\u043B\u0438 \u043F\u0443\u0441\u0442\u043E)" : ""}.` : "");
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
      if (optional) t.setPlaceholder(f.placeholder || (f.key.endsWith("max_tokens") ? "\u043A\u0430\u043A \u0443 \u043F\u0440\u043E\u0432\u0430\u0439\u0434\u0435\u0440\u0430" : "\u043D\u0435 \u0437\u0430\u0434\u0430\u043D\u043E"));
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
          if (typeof obj !== "object" || Array.isArray(obj) || obj === null) throw new Error("\u043D\u0443\u0436\u0435\u043D \u043E\u0431\u044A\u0435\u043A\u0442 { \u2026 }");
        } catch (e) {
          err.setText(`\u041D\u0435 JSON: ${e.message}`);
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
  /** Ключ: profile:<id>, embeddings (llm — ключ основной облачной модели, как в v2.4). */
  fieldKey(el, label, help, target, prof) {
    const keys = this.info.keys;
    let present = target === "embeddings" ? keys.embeddings : target.startsWith("profile:") ? !!keys.profiles?.[target.slice(8)] : keys.llm;
    if (prof && !prof.api_key_file) present = false;
    const s = new import_obsidian4.Setting(el).setName(label).setDesc(help);
    s.descEl.createDiv({ cls: present ? "vm-key-ok" : "vm-muted", text: present ? `\u2713 \u043A\u043B\u044E\u0447 \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D${prof?.api_key_file ? ` (${prof.api_key_file})` : ""}` : "\u043A\u043B\u044E\u0447\u0430 \u043D\u0435\u0442" });
    if (prof && prof.api_key_file) {
      const others = this.values.llm.profiles.filter((x) => x !== prof && x.api_key_file === prof.api_key_file);
      if (others.length) {
        s.descEl.createDiv({ cls: "vm-field-note", text: `\u0424\u0430\u0439\u043B \u043A\u043B\u044E\u0447\u0430 ${prof.api_key_file} \u043E\u0431\u0449\u0438\u0439 \u0441 \u043F\u0440\u043E\u0444\u0438\u043B\u0435\u043C \xAB${others.map((o) => o.name).join("\xBB, \xAB")}\xBB: \u043D\u043E\u0432\u044B\u0439 \u043A\u043B\u044E\u0447 \u0437\u0430\u043C\u0435\u043D\u0438\u0442 \u0435\u0433\u043E \u0438 \u0442\u0430\u043C.` });
        s.addButton((b) => b.setButtonText("\u041E\u0442\u0434\u0435\u043B\u044C\u043D\u044B\u0439 \u043A\u043B\u044E\u0447").setTooltip("\u042D\u0442\u043E\u043C\u0443 \u043F\u0440\u043E\u0444\u0438\u043B\u044E \u2014 \u0441\u0432\u043E\u0439 \u0444\u0430\u0439\u043B \u043A\u043B\u044E\u0447\u0430").onClick(() => {
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
      t.setPlaceholder(present ? "\u0432\u0441\u0442\u0430\u0432\u044C\u0442\u0435 \u043D\u043E\u0432\u044B\u0439, \u0447\u0442\u043E\u0431\u044B \u0437\u0430\u043C\u0435\u043D\u0438\u0442\u044C" : "\u0432\u0441\u0442\u0430\u0432\u044C\u0442\u0435 \u043A\u043B\u044E\u0447");
    });
    s.addButton((b) => b.setButtonText("\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C").onClick(async () => {
      const k = input.getValue().trim();
      if (!k) {
        new import_obsidian4.Notice("\u0412\u0441\u0442\u0430\u0432\u044C\u0442\u0435 \u043A\u043B\u044E\u0447 \u0432 \u043F\u043E\u043B\u0435.");
        return;
      }
      await this.saveKey(target, k);
    }));
    if (present)
      s.addExtraButton((b) => b.setIcon("trash-2").setTooltip("\u0423\u0434\u0430\u043B\u0438\u0442\u044C \u043A\u043B\u044E\u0447").onClick(async () => {
        const what = target === "embeddings" ? "\u0411\u0435\u0437 \u043A\u043B\u044E\u0447\u0430 \u043E\u0431\u043B\u0430\u0447\u043D\u044B\u0435 \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u0438 \u0440\u0430\u0431\u043E\u0442\u0430\u0442\u044C \u043D\u0435 \u0431\u0443\u0434\u0443\u0442." : "\u0411\u0435\u0437 \u043A\u043B\u044E\u0447\u0430 \u043E\u0431\u043B\u0430\u0447\u043D\u0430\u044F \u043C\u043E\u0434\u0435\u043B\u044C \u0440\u0430\u0431\u043E\u0442\u0430\u0442\u044C \u043D\u0435 \u0431\u0443\u0434\u0435\u0442.";
        const ok = await this.plugin.confirm({ title: "\u0423\u0434\u0430\u043B\u0438\u0442\u044C \u043A\u043B\u044E\u0447?", text: `\u0424\u0430\u0439\u043B \u0441 \u043A\u043B\u044E\u0447\u043E\u043C \u0431\u0443\u0434\u0435\u0442 \u0443\u0434\u0430\u043B\u0451\u043D. ${what}`, ok: "\u0423\u0434\u0430\u043B\u0438\u0442\u044C", warning: true });
        if (ok) await this.saveKey(target, "");
      }));
  }
  async saveKey(target, key) {
    await this.flush();
    const r = await this.plugin.engine.run(["settings", "--key", target], { label: "\u041A\u043B\u044E\u0447", stdin: key + "\n", exclusive: false, quiet: true });
    if (r.ok) {
      new import_obsidian4.Notice(r.title || "\u041A\u043B\u044E\u0447 \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D.");
      if (r.settings) {
        this.info = r.settings;
        if (!this.dirty.size) this.values = clone(r.settings.values);
      }
      this.redraw();
    } else new import_obsidian4.Notice("\u041A\u043B\u044E\u0447 \u043D\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D: " + (r.error || "\u043E\u0448\u0438\u0431\u043A\u0430"), 1e4);
  }
  // ---------- режим и профили моделей ----------
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
    if (llm.mode && !(llm.mode in modes)) modes[llm.mode] = llm.mode === "fake" ? "\u0422\u0435\u0441\u0442\u043E\u0432\u0430\u044F \u043C\u043E\u0434\u0435\u043B\u044C (\u0434\u043B\u044F \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0438)" : llm.mode;
    new import_obsidian4.Setting(el).setName("\u0420\u0435\u0436\u0438\u043C").setDesc("\u0413\u0434\u0435 \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 \u043E\u0441\u043D\u043E\u0432\u043D\u0430\u044F \u043C\u043E\u0434\u0435\u043B\u044C.").addDropdown((d) => {
      for (const [k, label] of Object.entries(modes)) d.addOption(k, label);
      d.setValue(llm.mode || "cloud");
      d.onChange((v) => this.setMode(v));
    });
    const kind = llm.mode === "local" ? "local" : llm.mode === "cloud" ? "cloud" : null;
    if (kind) {
      const key = kind === "cloud" ? "cloud_profile" : "local_profile";
      const list = llm.profiles.filter((p) => p.kind === kind);
      new import_obsidian4.Setting(el).setName(kind === "cloud" ? "\u041E\u0431\u043B\u0430\u0447\u043D\u044B\u0439 \u043F\u0440\u043E\u0444\u0438\u043B\u044C" : "\u041B\u043E\u043A\u0430\u043B\u044C\u043D\u044B\u0439 \u043F\u0440\u043E\u0444\u0438\u043B\u044C").setDesc("\u041D\u0430 \u043D\u0451\u043C \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430. \u041E\u0442\u0434\u0435\u043B\u044C\u043D\u044B\u043C \u0448\u0430\u0433\u0430\u043C \u043C\u043E\u0436\u043D\u043E \u0434\u0430\u0442\u044C \u0434\u0440\u0443\u0433\u0438\u0435 \u043F\u0440\u043E\u0444\u0438\u043B\u0438 \u2014 \u043D\u0438\u0436\u0435, \u0432 \xAB\u041C\u043E\u0434\u0435\u043B\u0438 \u0434\u043B\u044F \u043E\u0442\u0434\u0435\u043B\u044C\u043D\u044B\u0445 \u0448\u0430\u0433\u043E\u0432\xBB.").addDropdown((d) => {
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
        text: "\u0412\u0435\u0431-\u0447\u0430\u0442: \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043A\u043B\u0430\u0434\u0451\u0442 \u0437\u0430\u043F\u0440\u043E\u0441\u044B \u0432 \u043F\u0430\u043F\u043A\u0443 _\u0432\u0435\u0431-\u0447\u0430\u0442 \u0445\u0440\u0430\u043D\u0438\u043B\u0438\u0449\u0430, \u0432\u044B \u043A\u043E\u043F\u0438\u0440\u0443\u0435\u0442\u0435 \u0438\u0445 \u0432 \u0447\u0430\u0442 \u043C\u043E\u0434\u0435\u043B\u0438 \u0438 \u0432\u0441\u0442\u0430\u0432\u043B\u044F\u0435\u0442\u0435 \u043E\u0442\u0432\u0435\u0442\u044B \u0432 \u0444\u0430\u0439\u043B\u044B \u043E\u0442\u0432\u0435\u0442\u043E\u0432. \u041F\u0440\u043E\u0444\u0438\u043B\u0438 \u043D\u0438\u0436\u0435 \u043D\u0443\u0436\u043D\u044B, \u0442\u043E\u043B\u044C\u043A\u043E \u0435\u0441\u043B\u0438 \u043E\u0442\u0434\u0435\u043B\u044C\u043D\u044B\u043C \u0448\u0430\u0433\u0430\u043C \u043E\u0442\u0434\u0430\u043D\u044B \u0441\u0432\u043E\u0438 \u043C\u043E\u0434\u0435\u043B\u0438."
      });
    }
    this.profileEditor(el);
  }
  /** Профиль в текущих значениях. После каждого сохранения значения заменяются присланными программой,
   *  поэтому кнопки и поля, нарисованные раньше, находят свой профиль по id, а не по старой ссылке. */
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
  /** Новый профиль (или копия): id p<N>, имя без повторов, ключ — свой (файл появится, когда сохраните ключ). */
  newProfile(kind, base) {
    const llm = this.llm();
    const profiles = llm.profiles;
    const ids = new Set(profiles.map((p2) => p2.id));
    let n = profiles.length + 1;
    while (ids.has(`p${n}`)) n++;
    const id = `p${n}`;
    const def = clone(this.info.profile_defaults?.[kind] || { kind, name: kind === "local" ? "\u041B\u043E\u043A\u0430\u043B\u044C\u043D\u0430\u044F \u043C\u043E\u0434\u0435\u043B\u044C" : "\u041E\u0431\u043B\u0430\u0447\u043D\u0430\u044F \u043C\u043E\u0434\u0435\u043B\u044C" });
    const p = base ? { ...clone(base), id } : { ...def, id, kind };
    const names = new Set(profiles.map((x) => String(x.name || "").toLowerCase()));
    const root = base ? `${base.name || base.id} (\u043A\u043E\u043F\u0438\u044F)` : String(def.name || "\u041F\u0440\u043E\u0444\u0438\u043B\u044C");
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
    if (llm.cloud_profile === p.id) out.push(llm.mode === "cloud" ? "\u043E\u0441\u043D\u043E\u0432\u043D\u0430\u044F \u043C\u043E\u0434\u0435\u043B\u044C" : "\u043E\u0431\u043B\u0430\u0447\u043D\u044B\u0439 \u043F\u0440\u043E\u0444\u0438\u043B\u044C \u043F\u043E \u0443\u043C\u043E\u043B\u0447\u0430\u043D\u0438\u044E");
    if (llm.local_profile === p.id) out.push(llm.mode === "local" ? "\u043E\u0441\u043D\u043E\u0432\u043D\u0430\u044F \u043C\u043E\u0434\u0435\u043B\u044C" : "\u043B\u043E\u043A\u0430\u043B\u044C\u043D\u044B\u0439 \u043F\u0440\u043E\u0444\u0438\u043B\u044C \u043F\u043E \u0443\u043C\u043E\u043B\u0447\u0430\u043D\u0438\u044E");
    const steps = Object.entries(llm.roles || {}).filter(([, v]) => v === p.id).map(([k]) => k);
    if (steps.length) out.push("\u0448\u0430\u0433\u0438: " + steps.join(", "));
    return out;
  }
  profileEditor(el) {
    const llm = this.llm();
    const profiles = llm.profiles;
    const box = el.createDiv({ cls: "vm-prof-editor" });
    const main = llm.mode === "local" ? llm.local_profile : llm.cloud_profile;
    const cur = profiles.find((p) => p.id === this.editProfile) || profiles.find((p) => p.id === main) || profiles[0];
    const s = new import_obsidian4.Setting(box).setName("\u041F\u0440\u043E\u0444\u0438\u043B\u044C \u0434\u043B\u044F \u043F\u0440\u0430\u0432\u043A\u0438").setDesc("\u041E\u0431\u043B\u0430\u0447\u043D\u044B\u0435 \u043F\u0440\u043E\u0444\u0438\u043B\u0438 \u2014 \u0441 \u0446\u0435\u043D\u0430\u043C\u0438 \u0438 \u043F\u043E\u0434\u0441\u0447\u0451\u0442\u043E\u043C \u0434\u0435\u043D\u0435\u0433, \u043B\u043E\u043A\u0430\u043B\u044C\u043D\u044B\u0435 \u2014 \u0441 \u043F\u043E\u0434\u0441\u0447\u0451\u0442\u043E\u043C \u0442\u043E\u043A\u0435\u043D\u043E\u0432 \u0438 \u0432\u0440\u0435\u043C\u0435\u043D\u0438 \u0440\u0430\u0431\u043E\u0442\u044B.");
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
    s.addButton((b) => b.setButtonText("\uFF0B \u041E\u0431\u043B\u0430\u0447\u043D\u044B\u0439").setTooltip("\u041D\u043E\u0432\u044B\u0439 \u043E\u0431\u043B\u0430\u0447\u043D\u044B\u0439 \u043F\u0440\u043E\u0444\u0438\u043B\u044C").onClick(() => {
      this.newProfile("cloud");
      this.rerender();
    }));
    s.addButton((b) => b.setButtonText("\uFF0B \u041B\u043E\u043A\u0430\u043B\u044C\u043D\u044B\u0439").setTooltip("\u041D\u043E\u0432\u044B\u0439 \u043F\u0440\u043E\u0444\u0438\u043B\u044C \u0441\u0432\u043E\u0435\u0439 \u044F\u0437\u044B\u043A\u043E\u0432\u043E\u0439 \u043C\u043E\u0434\u0435\u043B\u0438 (\u0441\u0435\u0440\u0432\u0435\u0440 llama.cpp)").onClick(() => {
      this.newProfile("local");
      this.rerender();
    }));
    if (!cur) {
      box.createDiv({ cls: "vm-callout is-warning", text: "\u041F\u0440\u043E\u0444\u0438\u043B\u0435\u0439 \u043D\u0435\u0442 \u2014 \u0441\u043E\u0437\u0434\u0430\u0439\u0442\u0435 \u043E\u0431\u043B\u0430\u0447\u043D\u044B\u0439 \u0438\u043B\u0438 \u043B\u043E\u043A\u0430\u043B\u044C\u043D\u044B\u0439." });
      return;
    }
    s.addButton((b) => b.setButtonText("\u041A\u043E\u043F\u0438\u044F").setTooltip("\u0422\u0430\u043A\u043E\u0439 \u0436\u0435 \u043F\u0440\u043E\u0444\u0438\u043B\u044C \u2014 \u043D\u0430\u043F\u0440\u0438\u043C\u0435\u0440, \u0434\u0440\u0443\u0433\u0430\u044F \u043C\u043E\u0434\u0435\u043B\u044C \u0442\u043E\u0433\u043E \u0436\u0435 \u043F\u0440\u043E\u0432\u0430\u0439\u0434\u0435\u0440\u0430").onClick(() => {
      this.newProfile(cur.kind, cur);
      this.rerender();
    }));
    s.addExtraButton((b) => b.setIcon("trash-2").setTooltip("\u0423\u0434\u0430\u043B\u0438\u0442\u044C \u043F\u0440\u043E\u0444\u0438\u043B\u044C").onClick(() => this.deleteProfile(cur)));
    const used = this.profileUse(cur, llm);
    const fbox = box.createDiv({ cls: "vm-prof-box" });
    fbox.createDiv({ cls: "vm-prof-title", text: `${cur.name || cur.id} \xB7 ${PTYPE_RU[cur.kind] || cur.kind}` });
    fbox.createDiv({ cls: "vm-muted vm-small-text", text: used.length ? `\u0418\u0441\u043F\u043E\u043B\u044C\u0437\u0443\u0435\u0442\u0441\u044F: ${used.join("; ")}.` : "\u0421\u0435\u0439\u0447\u0430\u0441 \u043D\u0435 \u0438\u0441\u043F\u043E\u043B\u044C\u0437\u0443\u0435\u0442\u0441\u044F: \u0432\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u0435\u0433\u043E \u0432\u044B\u0448\u0435 \u043A\u0430\u043A \u043E\u0441\u043D\u043E\u0432\u043D\u043E\u0439 \u0438\u043B\u0438 \u043E\u0442\u0434\u0430\u0439\u0442\u0435 \u0435\u043C\u0443 \u0448\u0430\u0433\u0438." });
    let pricesHead = false;
    for (const f of this.info.profile_fields || []) {
      if (f.kinds && !f.kinds.includes(cur.kind)) continue;
      if (f.group === "prices" && !pricesHead) {
        pricesHead = true;
        fbox.createDiv({ cls: "vm-prof-sub", text: "\u0426\u0435\u043D\u044B \u0438 \u043B\u0438\u043C\u0438\u0442 \u2014 \u0434\u043B\u044F \u043F\u043E\u0434\u0441\u0447\u0451\u0442\u0430 \u0440\u0430\u0441\u0445\u043E\u0434\u043E\u0432. \u0426\u0435\u043D\u044B \u2014 \u0438\u0437 \u043F\u0440\u0430\u0439\u0441\u0430 \u043F\u0440\u043E\u0432\u0430\u0439\u0434\u0435\u0440\u0430, \u0432 \u0434\u043E\u043B\u043B\u0430\u0440\u0430\u0445 \u0437\u0430 \u043C\u0438\u043B\u043B\u0438\u043E\u043D \u0442\u043E\u043A\u0435\u043D\u043E\u0432." });
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
      new import_obsidian4.Notice("\u042D\u0442\u043E \u0435\u0434\u0438\u043D\u0441\u0442\u0432\u0435\u043D\u043D\u044B\u0439 \u043F\u0440\u043E\u0444\u0438\u043B\u044C \u2014 \u0441\u043D\u0430\u0447\u0430\u043B\u0430 \u0441\u043E\u0437\u0434\u0430\u0439\u0442\u0435 \u0434\u0440\u0443\u0433\u043E\u0439.", 6e3);
      return;
    }
    const used = this.profileUse(p, this.llm());
    const ok = await this.plugin.confirm({
      title: "\u0423\u0434\u0430\u043B\u0438\u0442\u044C \u043F\u0440\u043E\u0444\u0438\u043B\u044C?",
      text: `\u041F\u0440\u043E\u0444\u0438\u043B\u044C \xAB${p.name || p.id}\xBB \u0438\u0441\u0447\u0435\u0437\u043D\u0435\u0442 \u0438\u0437 \u043D\u0430\u0441\u0442\u0440\u043E\u0435\u043A.` + (used.length ? ` \u0421\u0435\u0439\u0447\u0430\u0441 \u043E\u043D \u0438\u0441\u043F\u043E\u043B\u044C\u0437\u0443\u0435\u0442\u0441\u044F (${used.join("; ")}) \u2014 \u0432\u043C\u0435\u0441\u0442\u043E \u043D\u0435\u0433\u043E \u0432\u0441\u0442\u0430\u043D\u0435\u0442 \u043F\u0435\u0440\u0432\u044B\u0439 \u043F\u043E\u0434\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u043F\u0440\u043E\u0444\u0438\u043B\u044C, \u0430 \u0448\u0430\u0433\u0438 \u0432\u0435\u0440\u043D\u0443\u0442\u0441\u044F \u043D\u0430 \u043E\u0441\u043D\u043E\u0432\u043D\u0443\u044E \u043C\u043E\u0434\u0435\u043B\u044C.` : "") + "\n\n\u0424\u0430\u0439\u043B \u043A\u043B\u044E\u0447\u0430 \u043D\u0435 \u0443\u0434\u0430\u043B\u044F\u0435\u0442\u0441\u044F. \u0418\u0441\u0442\u043E\u0440\u0438\u044F \u0440\u0430\u0441\u0445\u043E\u0434\u043E\u0432 \u043F\u0440\u043E\u0444\u0438\u043B\u044F \u043E\u0441\u0442\u0430\u043D\u0435\u0442\u0441\u044F \u0432\u043E \u0432\u043A\u043B\u0430\u0434\u043A\u0435 \xAB\u0420\u0430\u0441\u0445\u043E\u0434\u044B\xBB \u043F\u0430\u043D\u0435\u043B\u0438.",
      ok: "\u0423\u0434\u0430\u043B\u0438\u0442\u044C",
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
        d.addOption("", "\u041A\u0430\u043A \u043E\u0441\u043D\u043E\u0432\u043D\u0430\u044F");
        for (const p of profiles) d.addOption(p.id, `${p.name || p.id} (${PTYPE_RU[p.kind] || p.kind})`);
        d.addOption("webchat", "\u0412\u0440\u0443\u0447\u043D\u0443\u044E \u0447\u0435\u0440\u0435\u0437 \u0432\u0435\u0431-\u0447\u0430\u0442");
        if (v && v !== "webchat" && !profiles.some((p) => p.id === v)) d.addOption(v, `${v} \u2014 \u043D\u0435\u0442 \u0442\u0430\u043A\u043E\u0433\u043E \u043F\u0440\u043E\u0444\u0438\u043B\u044F`);
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
        text: `\u0414\u043B\u0438\u043D\u043D\u044B\u0439 \u043C\u0430\u0442\u0435\u0440\u0438\u0430\u043B (\u0448\u0430\u0433\u0438: ${f.split_prompts.join(", ")}) \u0434\u0435\u043B\u0438\u0442\u0441\u044F \u043D\u0430 \u0447\u0430\u0441\u0442\u0438 \u043F\u043E \xAB\u043F\u0440\u0435\u0434\u0435\u043B\u0443 \u0437\u0430\u043F\u0440\u043E\u0441\u0430\xBB \u043F\u0440\u043E\u0444\u0438\u043B\u044F, \u043A\u043E\u0442\u043E\u0440\u044B\u0439 \u043E\u0442\u0432\u0435\u0447\u0430\u0435\u0442 \u043D\u0430 \u0448\u0430\u0433.`
      });
  }
  fieldSources(el, f) {
    const list = Array.isArray(this.values.sources) ? this.values.sources : this.values.sources = [];
    if (f.help) el.createDiv({ cls: "setting-item-description vm-sec-help", text: f.help });
    list.forEach((src, i) => {
      const fixed = FIXED_SOURCES[String(src.name || "").toLowerCase()];
      const s = new import_obsidian4.Setting(el).setName(fixed ? String(src.name) : src.name ? `_staging/${src.name}` : "\u041D\u043E\u0432\u044B\u0439 \u0438\u0441\u0442\u043E\u0447\u043D\u0438\u043A").setDesc(fixed || "\u043F\u043E\u0434\u043F\u0430\u043F\u043A\u0430 _staging");
      s.settingEl.addClass("vm-source");
      if (!fixed)
        s.addText((t) => {
          t.setPlaceholder("\u043D\u0430\u0437\u0432\u0430\u043D\u0438\u0435 \u043F\u0430\u043F\u043A\u0438").setValue(src.name || "");
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
        t.inputEl.title = "\u041D\u0430 \u0441\u043A\u043E\u043B\u044C\u043A\u043E \u043F\u0443\u043D\u043A\u0442\u043E\u0432 \u043F\u043E\u043D\u0438\u0437\u0438\u0442\u044C \u043F\u043E\u0440\u043E\u0433 \u0443\u043F\u043B\u043E\u0442\u043D\u0435\u043D\u0438\u044F \u0434\u043B\u044F \u044D\u0442\u043E\u0433\u043E \u0438\u0441\u0442\u043E\u0447\u043D\u0438\u043A\u0430";
        t.setPlaceholder("\u0441\u0434\u0432\u0438\u0433").setValue(String(src.compaction_shift ?? 0));
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
        s.addExtraButton((b) => b.setIcon("trash-2").setTooltip("\u0423\u0431\u0440\u0430\u0442\u044C \u0438\u0441\u0442\u043E\u0447\u043D\u0438\u043A").onClick(() => {
          list.splice(i, 1);
          this.set("sources", list);
          this.rerender();
        }));
    });
    new import_obsidian4.Setting(el).addButton((b) => b.setButtonText("\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u0438\u0441\u0442\u043E\u0447\u043D\u0438\u043A").onClick(() => {
      list.push({ name: "", color: "#64748b", compaction_shift: 0 });
      this.rerender();
    }));
  }
  // ---------- сохранение ----------
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
  /** Отправить накопленные изменения программе: она проверит их и перепишет settings.yaml. */
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
      const r = await this.plugin.engine.run(["settings", "--set-json", "-"], { label: "\u0421\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u0438\u0435 \u043D\u0430\u0441\u0442\u0440\u043E\u0435\u043A", stdin: JSON.stringify(patch), exclusive: false, quiet: true });
      if (r.ok && r.settings) {
        this.info = r.settings;
        if (!this.dirty.size) this.values = clone(r.settings.values);
        const hadErrors = this.errors.length > 0;
        this.errors = [];
        if (hadErrors) {
          this.renderNav();
          this.rerender();
        }
        new import_obsidian4.Notice("\u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u044B.", 2500);
        this.plugin.refreshState();
        const e = patch.embeddings;
        if (e && ("mode" in e || "base_url" in e) && this.llamaFresh && this.containerEl.isConnected) this.loadLlama();
      } else {
        const text = String(r.error || "\u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u043D\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u044B.");
        const body = text.replace(/^Настройки не сохранены:\s*/, "");
        this.errors = body.split(/;\s+/).filter(Boolean).map((t) => ({ text: t, tab: tabOfError(t) }));
        new import_obsidian4.Notice(text + " \u041F\u043E\u043A\u0430\u0437\u0430\u043D\u044B \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D\u043D\u044B\u0435 \u0437\u043D\u0430\u0447\u0435\u043D\u0438\u044F.", 12e3);
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
  run: "\u0424\u0430\u0437\u0430 1",
  synth: "\u0424\u0430\u0437\u0430 2",
  revalidate: "\u0420\u0435\u0432\u0430\u043B\u0438\u0434\u0430\u0446\u0438\u044F",
  patterns: "\u041F\u0430\u0442\u0442\u0435\u0440\u043D\u044B",
  advise: "\u0421\u043E\u0432\u0435\u0442 \u043F\u043E \u043F\u043E\u0440\u043E\u0433\u0430\u043C",
  answer: "\u041E\u0442\u0432\u0435\u0442 \u043D\u0430 \u0432\u043E\u043F\u0440\u043E\u0441",
  check: "\u041F\u0440\u043E\u0432\u0435\u0440\u043A\u0430 \u0441\u0432\u044F\u0437\u0438"
};
var TAB_TITLES = { overview: "\u041E\u0431\u0437\u043E\u0440", questions: "\u0412\u043E\u043F\u0440\u043E\u0441\u044B", container: "\u041A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440", usage: "\u0420\u0430\u0441\u0445\u043E\u0434\u044B", log: "\u0416\u0443\u0440\u043D\u0430\u043B" };
var PERIODS = [["today", "\u0421\u0435\u0433\u043E\u0434\u043D\u044F"], ["month", "\u042D\u0442\u043E\u0442 \u043C\u0435\u0441\u044F\u0446"], ["prev_month", "\u041F\u0440\u043E\u0448\u043B\u044B\u0439 \u043C\u0435\u0441\u044F\u0446"], ["all", "\u0412\u0441\u0451 \u0432\u0440\u0435\u043C\u044F"]];
var PERIOD_IN = { today: "\u0441\u0435\u0433\u043E\u0434\u043D\u044F", month: "\u0432 \u044D\u0442\u043E\u043C \u043C\u0435\u0441\u044F\u0446\u0435", prev_month: "\u0432 \u043F\u0440\u043E\u0448\u043B\u043E\u043C \u043C\u0435\u0441\u044F\u0446\u0435", all: "\u0437\u0430 \u0432\u0441\u0451 \u0432\u0440\u0435\u043C\u044F" };
var FILE_WAIT = {
  await_structure: "\u0436\u0434\u0443\u0442 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0438\u044F \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u044B",
  await_mode: "\u0436\u0434\u0443\u0442 \u043E\u0442\u0432\u0435\u0442\u0430 \u043E \u0440\u0435\u0436\u0438\u043C\u0435",
  ready: "\u0436\u0434\u0443\u0442 \u0440\u0430\u0437\u0431\u043E\u0440\u0430",
  new: "\u0436\u0434\u0443\u0442 \u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A\u0430 \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u044B"
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
    return "\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433";
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
  // ---------- общее ----------
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
      this.plugin.errors.add("\u043F\u0430\u043D\u0435\u043B\u044C, \u0448\u0430\u043F\u043A\u0430", e);
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
      renderError(this.bodyEl, this.plugin, `\u043F\u0430\u043D\u0435\u043B\u044C, \u0432\u043A\u043B\u0430\u0434\u043A\u0430 \xAB${TAB_TITLES[this.tab]}\xBB`, e);
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
  // ---------- шапка и текущий запуск ----------
  renderHead() {
    const h = this.headEl;
    h.empty();
    const main = h.createDiv({ cls: "vm-head-main" });
    const t = main.createDiv({ cls: "vm-title" });
    (0, import_obsidian5.setIcon)(t.createSpan({ cls: "vm-logo" }), "brain");
    t.createSpan({ text: "\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433" });
    const p = this.plugin;
    const state = main.createDiv({ cls: "vm-state" });
    if (p.engine.problem()) state.setText("\u043D\u0435\u0442 \u0441\u0432\u044F\u0437\u0438 \u0441 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u043E\u0439");
    else if (p.engine.busy()) state.setText("\u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442");
    else if (p.ui) state.setText(p.ui.status.questions ? `\u0436\u0434\u0443\u0442 \u043E\u0442\u0432\u0435\u0442\u0430: ${p.ui.status.questions}` : "\u0433\u043E\u0442\u043E\u0432");
    const tools = h.createDiv({ cls: "vm-head-tools" });
    const r = tools.createDiv({ cls: "clickable-icon vm-icon-btn", attr: { "aria-label": "\u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C \u0441\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u0435" } });
    (0, import_obsidian5.setIcon)(r, "refresh-cw");
    r.addEventListener("click", () => p.refreshState(true));
    const s = tools.createDiv({ cls: "clickable-icon vm-icon-btn", attr: { "aria-label": "\u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u043F\u043B\u0430\u0433\u0438\u043D\u0430" } });
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
      const time = h.createSpan({ cls: "vm-run-time", attr: { title: "\u0421\u043A\u043E\u043B\u044C\u043A\u043E \u0438\u0434\u0451\u0442 \u0437\u0430\u043F\u0443\u0441\u043A" } });
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
          text: "\u041E\u0441\u0442\u0430\u043D\u0430\u0432\u043B\u0438\u0432\u0430\u044E: \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0437\u0430\u043A\u043E\u043D\u0447\u0438\u0442 \u0442\u0435\u043A\u0443\u0449\u0438\u0439 \u0448\u0430\u0433 \u0438 \u0441\u043E\u0445\u0440\u0430\u043D\u0438\u0442 \u0432\u0441\u0451. \u0415\u0441\u043B\u0438 \u043C\u043E\u0434\u0435\u043B\u044C \u0434\u043E\u043B\u0433\u043E \u043E\u0442\u0432\u0435\u0447\u0430\u0435\u0442 \u2014 \u044D\u0442\u043E \u043C\u043E\u0436\u0435\u0442 \u0437\u0430\u043D\u044F\u0442\u044C \u043F\u0430\u0440\u0443 \u043C\u0438\u043D\u0443\u0442."
        });
      }
    }
    if (queued.length) el.createDiv({ cls: "vm-run-queue", text: "\u0412 \u043E\u0447\u0435\u0440\u0435\u0434\u0438: " + queued.map((j) => j.label).join(", ") });
    const b = el.createDiv({ cls: "vm-buttons" });
    if (!job?.stopAt) this.button(b, "\u0421\u0442\u043E\u043F", () => eng.stop());
    if (job) {
      const kill = this.button(b, "\u041F\u0440\u0435\u0440\u0432\u0430\u0442\u044C \u0441\u0440\u0430\u0437\u0443", async () => {
        const ok = await this.plugin.confirm({
          title: "\u041F\u0440\u0435\u0440\u0432\u0430\u0442\u044C \u0441\u0440\u0430\u0437\u0443?",
          text: "\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u0441\u044F \u043D\u0435\u043C\u0435\u0434\u043B\u0435\u043D\u043D\u043E. \u0422\u0435\u043A\u0443\u0449\u0438\u0439 \u0448\u0430\u0433 (\u043E\u0442\u0432\u0435\u0442 \u043C\u043E\u0434\u0435\u043B\u0438, \u043A\u043E\u0442\u043E\u0440\u044B\u0439 \u0441\u0435\u0439\u0447\u0430\u0441 \u0436\u0434\u0451\u043C) \u043F\u0440\u043E\u043F\u0430\u0434\u0451\u0442, \u0432\u0441\u0451 \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D\u043D\u043E\u0435 \u0434\u043E \u043D\u0435\u0433\u043E \u2014 \u0446\u0435\u043B\u043E.",
          ok: "\u041F\u0440\u0435\u0440\u0432\u0430\u0442\u044C",
          warning: true
        });
        if (ok) eng.kill();
      }, "warning");
      if (this.runEls) this.runEls.kill = kill;
      this.button(b, "\u0412\u044B\u0432\u043E\u0434 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B", () => {
        this.openJobs.add(job.id);
        this.show("log");
      });
    }
    this.tick();
  }
  /** Раз в секунду и на каждую живую строку программы: время, этап, «осталось ≈», ожидание ответа, расход. */
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
    show(r.ask, ask ? `\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0436\u0434\u0451\u0442 \u0432\u0430\u0448\u0435\u0433\u043E \u043E\u0442\u0432\u0435\u0442\u0430: \xAB${ask.title}\xBB \u2014 \u043E\u043A\u043D\u043E \u043E\u0442\u043A\u0440\u044B\u0442\u043E \u043F\u043E\u0432\u0435\u0440\u0445 Obsidian.` : "");
    show(r.wait, !ask && info.wait !== null && info.wait >= 1500 ? `\u0416\u0434\u0451\u043C \u043E\u0442\u0432\u0435\u0442\u0430 \u043C\u043E\u0434\u0435\u043B\u0438: ${duration(info.wait)}${info.waitWhat ? ` \xB7 ${info.waitWhat}` : ""}` : "");
    const u = job.live.usage;
    const local = job.live.last?.ptype === "local";
    show(r.usage, u && u.calls ? `\u042D\u0442\u043E\u0442 \u0437\u0430\u043F\u0443\u0441\u043A: ${usageLine(u, { time: local })}` : "");
    r.line.setText(job.lastLine || "\u0437\u0430\u043F\u0443\u0441\u043A\u0430\u044E \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0443\u2026");
    if (r.kill) r.kill.toggleClass("vm-hidden", !(job.stopAt && now - job.stopAt > 2e4));
  }
  /** Новая строка вывода — обновить только строку прогресса, без перерисовки панели. */
  progress() {
    this.tick();
  }
  renderTabs() {
    const el = this.tabsEl;
    el.empty();
    const q = this.plugin.ui?.status.questions || 0;
    const tabs = [["overview", "\u041E\u0431\u0437\u043E\u0440", 0], ["questions", "\u0412\u043E\u043F\u0440\u043E\u0441\u044B", q], ["container", "\u041A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440", 0], ["usage", "\u0420\u0430\u0441\u0445\u043E\u0434\u044B", 0], ["log", "\u0416\u0443\u0440\u043D\u0430\u043B", 0]];
    for (const [id, label, n] of tabs) {
      const t = el.createEl("button", { cls: "vm-tab" + (this.tab === id ? " is-active" : "") });
      t.createSpan({ text: label });
      if (n) t.createSpan({ cls: "vm-badge is-accent", text: String(n) });
      t.addEventListener("click", () => this.show(id));
    }
  }
  // ---------- Обзор ----------
  renderOverview(el) {
    const p = this.plugin;
    const prob = p.engine.problem();
    if (prob) {
      const c = this.callout(el, "warning", "\u041F\u043B\u0430\u0433\u0438\u043D \u043D\u0435 \u0432\u0438\u0434\u0438\u0442 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0443", prob);
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438", () => p.openSettings(), "cta");
      return;
    }
    const ui = p.ui;
    if (!ui) {
      const c = this.callout(el, "info", "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u044E \u0441\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u0435 \u0445\u0440\u0430\u043D\u0438\u043B\u0438\u0449\u0430\u2026", "\u0415\u0441\u043B\u0438 \u044D\u0442\u043E \u043F\u0435\u0440\u0432\u043E\u0435 \u043E\u0442\u043A\u0440\u044B\u0442\u0438\u0435 \u2014 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0441\u0435\u0439\u0447\u0430\u0441 \u0441\u043E\u0437\u0434\u0430\u0451\u0442 \u0441\u043B\u0443\u0436\u0435\u0431\u043D\u044B\u0435 \u043F\u0430\u043F\u043A\u0438.");
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, "\u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C", () => p.refreshState(true));
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
    box.createDiv({ cls: "vm-card-title", text: "\u041F\u0435\u0440\u0432\u0430\u044F \u0437\u0430\u0433\u0440\u0443\u0437\u043A\u0430" });
    const waiting = Object.values(s.files).reduce((a, b) => a + b, 0);
    const hasFiles = s.staging_new > 0 || waiting > 0 || s.structure_pending;
    const draft = s.structure_pending && !!s.draft;
    const steps = [
      {
        title: "\u0421\u043B\u043E\u0436\u0438\u0442\u0435 \u0437\u0430\u043C\u0435\u0442\u043A\u0438 \u0432 _staging",
        done: hasFiles,
        body: (d) => {
          d.createDiv({ text: "\u0421\u0442\u0430\u0440\u044B\u0435 \u0437\u0430\u043F\u0438\u0441\u0438 (\u0430\u0440\u0445\u0438\u0432) \u2014 \u0432 \u043F\u0430\u043F\u043A\u0443 _staging/\u0430\u0440\u0445\u0438\u0432, \u043D\u043E\u0432\u044B\u0435 \u2014 \u043F\u0440\u044F\u043C\u043E \u0432 _staging. \u041F\u043E\u0434\u0445\u043E\u0434\u044F\u0442 \u0444\u0430\u0439\u043B\u044B .txt \u0438 .md, \u043B\u044E\u0431\u044B\u0435 \u0438\u043C\u0435\u043D\u0430." });
          d.createDiv({ cls: "vm-muted", text: s.staging_new ? `\u0421\u0435\u0439\u0447\u0430\u0441 \u0432 _staging \u0444\u0430\u0439\u043B\u043E\u0432: ${s.staging_new}.` : "\u0421\u0435\u0439\u0447\u0430\u0441 \u0432 _staging \u043F\u0443\u0441\u0442\u043E." });
          const b = d.createDiv({ cls: "vm-buttons" });
          this.button(b, "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u043F\u0430\u043F\u043A\u0443 _staging", () => p.revealFolder("_staging"));
          this.button(b, "\u041D\u043E\u0432\u0430\u044F \u043C\u044B\u0441\u043B\u044C", () => p.newThought());
          if (s.staging_new) this.button(b, "\u0414\u0430\u043B\u044C\u0448\u0435: \u0424\u0430\u0437\u0430 1", () => p.runPhase1(), "cta", busy);
        }
      },
      {
        title: "\u0424\u0430\u0437\u0430 1 \u2014 \u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u044B",
        done: draft,
        body: (d) => {
          d.createDiv({ text: "\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043F\u0440\u043E\u0447\u0438\u0442\u0430\u0435\u0442 \u0444\u0430\u0439\u043B\u044B \u0438 \u043F\u0440\u0435\u0434\u043B\u043E\u0436\u0438\u0442 \u0434\u0435\u0440\u0435\u0432\u043E \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u043E\u0432: \u043F\u0440\u043E\u0435\u043A\u0442\u044B, \u0440\u043E\u0441\u0442\u043A\u0438, \u0432\u043E\u043F\u0440\u043E\u0441\u044B." });
          if (waiting) d.createDiv({ cls: "vm-muted", text: `\u0424\u0430\u0439\u043B\u043E\u0432 \u043F\u0440\u043E\u0447\u0438\u0442\u0430\u043D\u043E: ${waiting}.` });
          const b = d.createDiv({ cls: "vm-buttons" });
          this.button(b, "\u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u0424\u0430\u0437\u0443 1", () => p.runPhase1(), "cta", busy);
        }
      },
      {
        title: "\u041F\u0440\u043E\u0432\u0435\u0440\u044C\u0442\u0435 \u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A \u0438 \u0443\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435",
        done: false,
        body: (d) => {
          d.createDiv({ text: "\u041F\u0435\u0440\u0435\u0438\u043C\u0435\u043D\u0443\u0439\u0442\u0435, \u043E\u0431\u044A\u0435\u0434\u0438\u043D\u0438\u0442\u0435 \u0438\u043B\u0438 \u0443\u0434\u0430\u043B\u0438\u0442\u0435 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u044B \u043F\u0440\u044F\u043C\u043E \u0432 \u0442\u0435\u043A\u0441\u0442\u0435 \u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A\u0430. \u041F\u043E\u0441\u043B\u0435 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0438\u044F \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0441\u043E\u0437\u0434\u0430\u0441\u0442 \u043F\u0430\u043F\u043A\u0438 \u0438 \u0440\u0430\u0437\u043B\u043E\u0436\u0438\u0442 \u0437\u0430\u043F\u0438\u0441\u0438 \u2014 \u044D\u0442\u043E \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0430\u044F \u0447\u0430\u0441\u0442\u044C \u0424\u0430\u0437\u044B 1." });
          const b = d.createDiv({ cls: "vm-buttons" });
          if (s.draft) this.button(b, "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A", () => p.open(s.draft));
          this.button(b, "\u0423\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044C \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u0443", () => p.approveStructure(), "cta", busy);
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
      const q = this.callout(el, "accent", `\u0416\u0434\u0443\u0442 \u043E\u0442\u0432\u0435\u0442\u0430: ${nQuestions(s.questions)}`, "\u041D\u0430\u043F\u0440\u0438\u043C\u0435\u0440, \u043E \u0440\u0435\u0436\u0438\u043C\u0435 \u0444\u0430\u0439\u043B\u0430: \u043C\u0430\u0441\u0441\u043E\u0432\u0430\u044F \u0437\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0438\u043B\u0438 \u043E\u0434\u043D\u0430 \u0437\u0430\u043F\u0438\u0441\u044C.");
      this.button(q.createDiv({ cls: "vm-buttons" }), "\u041E\u0442\u0432\u0435\u0442\u0438\u0442\u044C", () => this.show("questions"), "cta");
    }
  }
  renderAttention(el, ui) {
    const p = this.plugin;
    const s = ui.status;
    const busy = p.engine.busy();
    let n = 0;
    if (s.structure_pending && s.draft) {
      n++;
      const c = this.callout(el, "accent", "\u0427\u0435\u0440\u043D\u043E\u0432\u0438\u043A \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u044B \u0436\u0434\u0451\u0442 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0438\u044F", "\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043F\u0440\u0435\u0434\u043B\u043E\u0436\u0438\u043B\u0430 \u0438\u0437\u043C\u0435\u043D\u0435\u043D\u0438\u044F \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u044B. \u041E\u0442\u043A\u0440\u043E\u0439\u0442\u0435 \u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A, \u043F\u043E\u043F\u0440\u0430\u0432\u044C\u0442\u0435 \u0438 \u0443\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435.");
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A", () => p.open(s.draft));
      this.button(b, "\u0423\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044C \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u0443", () => p.approveStructure(), "cta", busy);
    }
    if (s.webchat_pending.length) {
      n++;
      const c = this.callout(el, "accent", "\u0416\u0434\u0451\u0442 \u043E\u0442\u0432\u0435\u0442\u0430 \u0438\u0437 \u0432\u0435\u0431-\u0447\u0430\u0442\u0430", null);
      for (const w of s.webchat_pending) {
        const row = c.createDiv({ cls: "vm-webchat" });
        row.createDiv({ text: `\u0428\u0430\u0433 \xAB${w.prompt}\xBB: \u0441\u043A\u043E\u043F\u0438\u0440\u0443\u0439\u0442\u0435 \u0432\u0435\u0441\u044C \u0442\u0435\u043A\u0441\u0442 \u0437\u0430\u043F\u0440\u043E\u0441\u0430 \u0432 \u0432\u0435\u0431-\u0447\u0430\u0442 \u043C\u043E\u0434\u0435\u043B\u0438, \u0430 \u0435\u0451 \u043E\u0442\u0432\u0435\u0442 \u0446\u0435\u043B\u0438\u043A\u043E\u043C \u0432\u0441\u0442\u0430\u0432\u044C\u0442\u0435 \u0432 \u0444\u0430\u0439\u043B \u043E\u0442\u0432\u0435\u0442\u0430 \u0438 \u0441\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u0435.` });
        const b2 = row.createDiv({ cls: "vm-buttons" });
        this.button(b2, "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0437\u0430\u043F\u0440\u043E\u0441", () => p.open(w.req));
        this.button(b2, "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0444\u0430\u0439\u043B \u043E\u0442\u0432\u0435\u0442\u0430", () => p.open(w.ans));
      }
      const last = p.lastWebchat;
      const b = c.createDiv({ cls: "vm-buttons" });
      this.button(b, last ? `\u041F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u044C: ${last.label}` : "\u041F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u044C (\u0424\u0430\u0437\u0430 1)", () => p.continueWebchat(), "cta", busy);
    }
    if (s.questions) {
      n++;
      const c = this.callout(el, "accent", `\u0416\u0434\u0443\u0442 \u043E\u0442\u0432\u0435\u0442\u0430: ${nQuestions(s.questions)}`, "\u041E\u0442\u0432\u0435\u0442 \u043F\u0440\u0438\u043C\u0435\u043D\u044F\u0435\u0442\u0441\u044F \u0441\u0440\u0430\u0437\u0443.");
      this.button(c.createDiv({ cls: "vm-buttons" }), "\u041E\u0442\u0432\u0435\u0442\u0438\u0442\u044C", () => this.show("questions"), "cta");
    }
    if (s.staging_new) {
      n++;
      const c = this.callout(el, "info", `\u041D\u043E\u0432\u044B\u0445 \u0444\u0430\u0439\u043B\u043E\u0432 \u0432 _staging: ${s.staging_new}`, null);
      this.button(c.createDiv({ cls: "vm-buttons" }), "\u041E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u0442\u044C (\u0424\u0430\u0437\u0430 1)", () => p.runPhase1(), "cta", busy);
    } else if (s.pending_work) {
      n++;
      const text = s.dirty.length ? `\u0411\u0430\u0437\u044B \u0441\u0438\u043D\u0442\u0435\u0437\u0430 \u043A \u043F\u0435\u0440\u0435\u0441\u0431\u043E\u0440\u043A\u0435: ${s.dirty.map((d) => d.title).join(", ")}.` : "\u0427\u0430\u0441\u0442\u044C \u0437\u0430\u043F\u0438\u0441\u0435\u0439 \u0435\u0449\u0451 \u0432 \u043E\u0447\u0435\u0440\u0435\u0434\u0438.";
      const c = this.callout(el, "info", "\u041E\u0431\u0440\u0430\u0431\u043E\u0442\u043A\u0430 \u043D\u0435 \u0437\u0430\u043A\u043E\u043D\u0447\u0435\u043D\u0430", text);
      this.button(c.createDiv({ cls: "vm-buttons" }), "\u041F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u044C (\u0424\u0430\u0437\u0430 1)", () => p.runPhase1(), "cta", busy);
    }
    if (!n) this.callout(el, "ok", "\u0412\u0441\u0451 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u043D\u043E", "\u041D\u043E\u0432\u044B\u0435 \u043C\u044B\u0441\u043B\u0438 \u2014 \u043A\u043D\u043E\u043F\u043A\u043E\u0439 \xAB\u041D\u043E\u0432\u0430\u044F \u043C\u044B\u0441\u043B\u044C\xBB \u0438\u043B\u0438 \u0444\u0430\u0439\u043B\u0430\u043C\u0438 \u0432 _staging.");
  }
  renderActions(el, ui, wizard) {
    const p = this.plugin;
    const box = el.createDiv({ cls: "vm-actions" + (wizard ? " is-wizard" : "") });
    const has = ui.containers.length > 0;
    const s = ui.status;
    const running = !!p.engine.find((j) => j.args[0] === "run");
    if (!wizard)
      this.button(box, running ? "\u0424\u0430\u0437\u0430 1 \u0438\u0434\u0451\u0442\u2026" : "\u0424\u0430\u0437\u0430 1: \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u0442\u044C \u043D\u043E\u0432\u043E\u0435", () => p.runPhase1(), s.staging_new || s.pending_work ? "cta" : void 0, running);
    this.button(box, "\u041D\u043E\u0432\u0430\u044F \u043C\u044B\u0441\u043B\u044C", () => p.newThought());
    this.button(box, "\u0424\u0430\u0437\u0430 2: \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B\u2026", () => p.pickContainer((c) => c && p.runSynth(c)), void 0, !has);
    this.button(box, "\u0420\u0435\u0432\u0430\u043B\u0438\u0434\u0430\u0446\u0438\u044F\u2026", () => p.pickContainer((c) => p.runRevalidate(c), "\u0412\u0441\u0435 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u044B"), void 0, !has);
    this.button(box, "\u041F\u0430\u0442\u0442\u0435\u0440\u043D\u044B", () => p.runPatterns(), void 0, !has);
    this.button(box, "\u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u0441\u0432\u044F\u0437\u044C", () => p.runCheck());
  }
  renderCounts(el, ui, wizard) {
    const s = ui.status;
    const files = Object.entries(s.files).filter(([k, v]) => v && FILE_WAIT[k]);
    const filesLine = () => {
      if (files.length) el.createDiv({ cls: "vm-muted vm-line", text: "\u0424\u0430\u0439\u043B\u044B: " + files.map(([k, v]) => `${FILE_WAIT[k]} \u2014 ${v}`).join(" \xB7 ") });
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
    tile(s.containers, ["\u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440", "\u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430", "\u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u043E\u0432"]);
    tile(s.entities, ["\u0437\u0430\u043F\u0438\u0441\u044C", "\u0437\u0430\u043F\u0438\u0441\u0438", "\u0437\u0430\u043F\u0438\u0441\u0435\u0439"]);
    tile(s.products, ["\u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442", "\u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u0430", "\u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u043E\u0432"]);
    tile(s.questions, ["\u0432\u043E\u043F\u0440\u043E\u0441", "\u0432\u043E\u043F\u0440\u043E\u0441\u0430", "\u0432\u043E\u043F\u0440\u043E\u0441\u043E\u0432"], () => this.show("questions"));
    const parts = [`\u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u043D\u043E ${s.stages.done}`];
    if (s.stages.quarantine) parts.push(`\u0436\u0434\u0443\u0442 \u043E\u0442\u0432\u0435\u0442\u0430 ${s.stages.quarantine}`);
    if (s.stages.queue) parts.push(`\u0432 \u043E\u0447\u0435\u0440\u0435\u0434\u0438 ${s.stages.queue}`);
    if (s.entities || s.stages.queue || s.stages.quarantine) el.createDiv({ cls: "vm-muted vm-line", text: "\u0417\u0430\u043F\u0438\u0441\u0438: " + parts.join(" \xB7 ") });
    filesLine();
  }
  renderWarnings(el, ui) {
    const list = [...new Set(ui.warnings || [])];
    if (!list.length) return;
    const s = this.section(el, "\u041F\u0440\u0435\u0434\u0443\u043F\u0440\u0435\u0436\u0434\u0435\u043D\u0438\u044F");
    for (const w of list) {
      const row = s.createDiv({ cls: "vm-warn" });
      row.createSpan({ cls: "vm-warn-mark", text: "!" });
      const t = row.createDiv({ cls: "vm-warn-text" });
      import_obsidian5.MarkdownRenderer.render(this.app, w, t, "", this).then(() => this.hookLinks(t));
    }
  }
  renderTree(el, ui) {
    const s = this.section(el, "\u041A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u044B", "\u0437\u0430\u043F\u0438\u0441\u0435\u0439");
    for (const c of ui.containers) {
      const row = s.createDiv({ cls: "vm-tree-row" + (c.status !== "active" ? " is-muted" : "") + (c.id === this.selectedId ? " is-selected" : "") });
      row.style.paddingLeft = `${6 + c.depth * 16}px`;
      this.dot(row, c.color);
      row.createSpan({ cls: "vm-tree-title", text: c.title });
      if (c.type !== "project") row.createSpan({ cls: "vm-chip", text: c.type_ru });
      if (c.status !== "active") row.createSpan({ cls: "vm-chip is-muted", text: c.status_ru });
      const right = row.createSpan({ cls: "vm-tree-right" });
      if (c.dirty) right.createSpan({ cls: "vm-mark", text: "\u21BB", attr: { title: "\u0431\u0430\u0437\u0430 \u0441\u0438\u043D\u0442\u0435\u0437\u0430 \u0436\u0434\u0451\u0442 \u043F\u0435\u0440\u0435\u0441\u0431\u043E\u0440\u043A\u0438" } });
      if (c.questions) right.createSpan({ cls: "vm-badge is-accent", text: String(c.questions), attr: { title: nQuestions(c.questions) } });
      right.createSpan({ cls: "vm-tree-n", text: String(c.entities + c.shared) });
      row.addEventListener("click", () => this.show("container", c.id));
    }
  }
  /** Обзор: на какой модели работает программа и сколько она стоила в этом месяце. */
  renderCurrent(el, ui) {
    const u = ui.usage;
    if (!u) return;
    const cur = u.current;
    const box = el.createDiv({ cls: "vm-card vm-current" });
    const head = box.createDiv({ cls: "vm-current-head" });
    const webchat = cur.mode === "webchat";
    head.createSpan({ cls: "vm-current-k", text: "\u041C\u043E\u0434\u0435\u043B\u044C:" });
    head.createSpan({ cls: "vm-current-name", text: webchat ? "\u0432\u0440\u0443\u0447\u043D\u0443\u044E \u0447\u0435\u0440\u0435\u0437 \u0432\u0435\u0431-\u0447\u0430\u0442" : cur.name || "\u043F\u0440\u043E\u0444\u0438\u043B\u044C \u043D\u0435 \u0432\u044B\u0431\u0440\u0430\u043D" });
    if (cur.ptype && !webchat) head.createSpan({ cls: "vm-chip", text: PTYPE_RU[cur.ptype] || cur.ptype });
    const link = head.createEl("a", { cls: "vm-link vm-small-text vm-current-link", text: "\u0420\u0430\u0441\u0445\u043E\u0434\u044B \u2192" });
    link.addEventListener("click", () => this.show("usage"));
    if (!webchat && !cur.name) {
      const a = box.createEl("a", { cls: "vm-link vm-small-text", text: "\u0412\u044B\u0431\u0440\u0430\u0442\u044C \u043F\u0440\u043E\u0444\u0438\u043B\u044C \u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0430\u0445" });
      a.addEventListener("click", () => this.plugin.openSettings("models"));
    }
    const t = cur.totals?.month;
    box.createDiv({
      cls: "vm-muted vm-small-text",
      text: t && t.calls ? `\u0412 \u044D\u0442\u043E\u043C \u043C\u0435\u0441\u044F\u0446\u0435: ${usageLine(t, { time: cur.ptype === "local" })}${t.unpriced ? " (* \u0431\u0435\u0437 \u0447\u0430\u0441\u0442\u0438 \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439 \u2014 \u043D\u0435\u0442 \u0446\u0435\u043D)" : ""}` : "\u0412 \u044D\u0442\u043E\u043C \u043C\u0435\u0441\u044F\u0446\u0435 \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439 \u043A \u044D\u0442\u043E\u0439 \u043C\u043E\u0434\u0435\u043B\u0438 \u043D\u0435 \u0431\u044B\u043B\u043E."
    });
    const all = u.totals.month;
    if (all.calls && t && all.calls !== t.calls) box.createDiv({ cls: "vm-muted vm-small-text", text: `\u0412\u0441\u0435 \u043C\u043E\u0434\u0435\u043B\u0438 \u0432 \u044D\u0442\u043E\u043C \u043C\u0435\u0441\u044F\u0446\u0435: ${usageLine(all)}` });
    if (u.budget.monthly_usd) this.budgetBar(box, u, false);
  }
  /** Полоса бюджета месяца: зелёная, с 80% — жёлтая, со 100% — красная. */
  budgetBar(parent, u, big) {
    const b = u.budget;
    if (!b.monthly_usd) return;
    const pct = b.pct ?? 0;
    const wrap = parent.createDiv({ cls: "vm-budget" + (big ? " is-big" : "") + (b.state ? ` is-${b.state}` : "") });
    const t = wrap.createDiv({ cls: "vm-budget-text" });
    t.createSpan({ text: `\u0411\u044E\u0434\u0436\u0435\u0442 \u043C\u0435\u0441\u044F\u0446\u0430: ${money(b.spent)} \u0438\u0437 ${money(b.monthly_usd)}` });
    t.createSpan({ cls: "vm-budget-pct", text: ` \xB7 ${pctText(pct)}` });
    const bar = wrap.createDiv({ cls: "vm-bar" });
    bar.createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.min(100, pct)}%`;
    if (b.state === "over") wrap.createDiv({ cls: "vm-small-text", text: "\u0411\u044E\u0434\u0436\u0435\u0442 \u0438\u0441\u0447\u0435\u0440\u043F\u0430\u043D: \u043F\u0435\u0440\u0435\u0434 \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0438\u043C \u043F\u043B\u0430\u0442\u043D\u044B\u043C \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0435\u043C \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u0441\u044F \u0438 \u0441\u043F\u0440\u043E\u0441\u0438\u0442, \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0430\u0442\u044C \u043B\u0438." });
    else if (b.state === "warn") wrap.createDiv({ cls: "vm-small-text", text: `\u0418\u0437\u0440\u0430\u0441\u0445\u043E\u0434\u043E\u0432\u0430\u043D\u043E \u0431\u043E\u043B\u044C\u0448\u0435 ${b.warn_pct}% \u0431\u044E\u0434\u0436\u0435\u0442\u0430.` });
  }
  // ---------- Расходы ----------
  renderUsageTab(el, ui) {
    const p = this.plugin;
    const u = ui?.usage;
    if (!ui || !u) {
      this.callout(el, "info", "\u0420\u0430\u0441\u0445\u043E\u0434\u043E\u0432 \u043F\u043E\u043A\u0430 \u043D\u0435\u0442", "\u0421\u0432\u043E\u0434\u043A\u0430 \u043F\u043E\u044F\u0432\u0438\u0442\u0441\u044F \u043F\u043E\u0441\u043B\u0435 \u043F\u0435\u0440\u0432\u043E\u0433\u043E \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F \u043A \u043C\u043E\u0434\u0435\u043B\u0438.");
      return;
    }
    const job = p.engine.active();
    if (job?.live.usage?.calls) {
      const local = job.live.last?.ptype === "local";
      this.callout(el, "info", `\u0421\u0435\u0439\u0447\u0430\u0441 \u0438\u0434\u0451\u0442: ${job.label}`, usageLine(job.live.usage, { time: local }) + ". \u0421\u0432\u043E\u0434\u043A\u0430 \u043D\u0438\u0436\u0435 \u043E\u0431\u043D\u043E\u0432\u0438\u0442\u0441\u044F, \u043A\u043E\u0433\u0434\u0430 \u0437\u0430\u043F\u0443\u0441\u043A \u0437\u0430\u043A\u043E\u043D\u0447\u0438\u0442\u0441\u044F.");
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
    cell(plural(T.calls, ["\u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0435", "\u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F", "\u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439"]), num(T.calls));
    cell("\u0442\u043E\u043A\u0435\u043D\u043E\u0432 \u043D\u0430 \u0432\u0445\u043E\u0434\u0435", compact(T.in), T.cached ? `\u0438\u0437 \u043D\u0438\u0445 \u0438\u0437 \u043A\u044D\u0448\u0430: ${num(T.cached)}` : void 0);
    cell("\u0442\u043E\u043A\u0435\u043D\u043E\u0432 \u043D\u0430 \u0432\u044B\u0445\u043E\u0434\u0435", compact(T.out));
    cell("\u0440\u0430\u0431\u043E\u0442\u0430 \u043C\u043E\u0434\u0435\u043B\u0435\u0439", T.sec ? durationText(T.sec) : "\u2014", "\u0421\u043A\u043E\u043B\u044C\u043A\u043E \u043C\u043E\u0434\u0435\u043B\u0438 \u0434\u0443\u043C\u0430\u043B\u0438 \u043D\u0430\u0434 \u043E\u0442\u0432\u0435\u0442\u0430\u043C\u0438 (\u0441\u0443\u043C\u043C\u0430 \u043F\u043E \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F\u043C)");
    if (T.cached) card.createDiv({ cls: "vm-muted vm-small-text", text: `\u0418\u0437 \u043A\u044D\u0448\u0430 \u043F\u0440\u043E\u0432\u0430\u0439\u0434\u0435\u0440\u0430: ${num(T.cached)} \u0442\u043E\u043A\u0435\u043D\u043E\u0432 \u0432\u0445\u043E\u0434\u0430 (\u043E\u043D\u0438 \u0434\u0435\u0448\u0435\u0432\u043B\u0435).` });
    if (T.unpriced)
      card.createDiv({ cls: "vm-small-text vm-warn-line", text: `* ${nCalls(T.unpriced)} \u043E\u0431\u043B\u0430\u0447\u043D\u044B\u0445 \u043C\u043E\u0434\u0435\u043B\u0435\u0439 \u0431\u0435\u0437 \u0441\u0442\u043E\u0438\u043C\u043E\u0441\u0442\u0438 \u2014 \u0443 \u043F\u0440\u043E\u0444\u0438\u043B\u044F \u043D\u0435 \u0437\u0430\u0434\u0430\u043D\u044B \u0446\u0435\u043D\u044B. \u0412\u043F\u0438\u0448\u0438\u0442\u0435 \u0438\u0445 \u043D\u0438\u0436\u0435: \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043F\u0440\u0435\u0434\u043B\u043E\u0436\u0438\u0442 \u043F\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u0442\u044C \u043F\u0440\u043E\u0448\u043B\u044B\u0435 \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F.` });
    if (T.est) card.createDiv({ cls: "vm-muted vm-small-text", text: `\u0414\u043B\u044F ${nCalls(T.est)} \u0441\u0435\u0440\u0432\u0435\u0440 \u043D\u0435 \u0441\u043E\u043E\u0431\u0449\u0438\u043B \u0442\u043E\u043A\u0435\u043D\u044B \u2014 \u043E\u043D\u0438 \u043E\u0446\u0435\u043D\u0435\u043D\u044B \u043F\u043E \u0447\u0438\u0441\u043B\u0443 \u0437\u043D\u0430\u043A\u043E\u0432.` });
    if (!T.calls) card.createDiv({ cls: "vm-muted", text: `\u041E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439 ${PERIOD_IN[per]} \u043D\u0435 \u0431\u044B\u043B\u043E.` });
    this.renderBudgetEdit(el, u);
    this.renderProfiles(el, u, per);
    this.renderSteps(el, u, per);
    this.renderDays(el, u);
    this.renderRuns(el, u);
    el.createDiv({
      cls: "vm-muted vm-small-text",
      text: "\u0421\u0442\u043E\u0438\u043C\u043E\u0441\u0442\u044C \u0441\u0447\u0438\u0442\u0430\u0435\u0442\u0441\u044F \u043F\u043E \u0446\u0435\u043D\u0430\u043C \u043F\u0440\u043E\u0444\u0438\u043B\u044F \u0432 \u043C\u043E\u043C\u0435\u043D\u0442 \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F \u0438 \u0445\u0440\u0430\u043D\u0438\u0442\u0441\u044F \u0432 \u0436\u0443\u0440\u043D\u0430\u043B\u0435 .system/usage.jsonl. \u041B\u043E\u043A\u0430\u043B\u044C\u043D\u044B\u0435 \u043C\u043E\u0434\u0435\u043B\u0438 \u0431\u0435\u0441\u043F\u043B\u0430\u0442\u043D\u044B \u2014 \u0434\u043B\u044F \u043D\u0438\u0445 \u043F\u043E\u043A\u0430\u0437\u0430\u043D\u044B \u0442\u043E\u043A\u0435\u043D\u044B \u0438 \u0432\u0440\u0435\u043C\u044F \u0440\u0430\u0431\u043E\u0442\u044B."
    });
  }
  renderBudgetEdit(el, u) {
    const p = this.plugin;
    const s = this.section(el, "\u0411\u044E\u0434\u0436\u0435\u0442 \u043D\u0430 \u043E\u0431\u043B\u0430\u0447\u043D\u044B\u0435 \u043C\u043E\u0434\u0435\u043B\u0438", "\u0437\u0430 \u043C\u0435\u0441\u044F\u0446");
    if (u.budget.monthly_usd) this.budgetBar(s, u, true);
    else s.createDiv({ cls: "vm-muted vm-small-text", text: `\u0411\u044E\u0434\u0436\u0435\u0442 \u043D\u0435 \u0437\u0430\u0434\u0430\u043D. \u0412 \u044D\u0442\u043E\u043C \u043C\u0435\u0441\u044F\u0446\u0435 \u043F\u043E\u0442\u0440\u0430\u0447\u0435\u043D\u043E ${money(u.budget.spent)}.` });
    const row = s.createDiv({ cls: "vm-inline-form" });
    row.createSpan({ text: "\u0411\u044E\u0434\u0436\u0435\u0442, $" });
    const inp = row.createEl("input", { type: "text", cls: "vm-num", attr: { inputmode: "decimal", placeholder: "\u0431\u0435\u0437 \u0431\u044E\u0434\u0436\u0435\u0442\u0430" } });
    inp.value = this.budgetDraft ?? (u.budget.monthly_usd != null ? String(u.budget.monthly_usd) : "");
    const save = this.button(row, "\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C", async () => {
      const v = parseNumber(inp.value, "float", 0, 1e5);
      if (v === null) {
        inp.addClass("vm-invalid");
        new import_obsidian5.Notice("\u0411\u044E\u0434\u0436\u0435\u0442 \u2014 \u0447\u0438\u0441\u043B\u043E \u043E\u0442 0 \u0434\u043E 100000 (\u043F\u0443\u0441\u0442\u043E \u2014 \u0431\u0435\u0437 \u0431\u044E\u0434\u0436\u0435\u0442\u0430).");
        return;
      }
      save.disabled = true;
      const r = await p.patchSettings({ budget: { monthly_usd: v === void 0 || v === 0 ? null : v } });
      this.budgetDraft = null;
      if (r.ok) new import_obsidian5.Notice(v ? `\u0411\u044E\u0434\u0436\u0435\u0442 \u043C\u0435\u0441\u044F\u0446\u0430: ${money(v)}. \u041F\u0440\u0438 ${u.budget.warn_pct}% \u2014 \u043F\u0440\u0435\u0434\u0443\u043F\u0440\u0435\u0436\u0434\u0435\u043D\u0438\u0435, \u043F\u0440\u0438 100% \u2014 \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0430 \u0441 \u0432\u043E\u043F\u0440\u043E\u0441\u043E\u043C.` : "\u0411\u044E\u0434\u0436\u0435\u0442 \u0441\u043D\u044F\u0442.");
      else new import_obsidian5.Notice(r.error || "\u0411\u044E\u0434\u0436\u0435\u0442 \u043D\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D.", 12e3);
      this.render(true);
    });
    inp.addEventListener("input", () => {
      this.budgetDraft = inp.value;
      inp.removeClass("vm-invalid");
    });
    inp.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") save.click();
    });
    const note = s.createDiv({ cls: "vm-muted vm-small-text", text: `\u041F\u0440\u0438 ${u.budget.warn_pct}% \u2014 \u043F\u0440\u0435\u0434\u0443\u043F\u0440\u0435\u0436\u0434\u0435\u043D\u0438\u0435, \u043F\u0440\u0438 100% \u2014 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u0441\u044F \u043F\u0435\u0440\u0435\u0434 \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0438\u043C \u043F\u043B\u0430\u0442\u043D\u044B\u043C \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0435\u043C \u0438 \u0441\u043F\u0440\u043E\u0441\u0438\u0442, \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0430\u0442\u044C \u043B\u0438. \u041F\u043E\u0440\u043E\u0433 \u043F\u0440\u0435\u0434\u0443\u043F\u0440\u0435\u0436\u0434\u0435\u043D\u0438\u044F, \u043E\u0446\u0435\u043D\u043A\u0430 \u043F\u0435\u0440\u0435\u0434 \u0431\u043E\u043B\u044C\u0448\u0438\u043C \u0437\u0430\u043F\u0443\u0441\u043A\u043E\u043C \u0438 \u043B\u0438\u043C\u0438\u0442\u044B \u043F\u0440\u043E\u0444\u0438\u043B\u0435\u0439 \u2014 ` });
    const a = note.createEl("a", { cls: "vm-link", text: "\u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0430\u0445" });
    a.addEventListener("click", () => this.plugin.openSettings("costs"));
    note.appendText(".");
  }
  renderProfiles(el, u, per) {
    const s = this.section(el, "\u041C\u043E\u0434\u0435\u043B\u0438", PERIOD_IN[per]);
    const list = u.profiles.filter((x) => x.exists || x.totals.all.calls);
    if (!list.length) s.createDiv({ cls: "vm-muted", text: "\u041F\u0440\u043E\u0444\u0438\u043B\u0435\u0439 \u043D\u0435\u0442." });
    for (const pr of list) this.renderProfileCard(s, pr, per);
  }
  renderProfileCard(el, pr, per) {
    const p = this.plugin;
    const emb = pr.kind === "emb";
    const card = el.createDiv({ cls: "vm-card vm-prof" + (pr.exists ? "" : " is-muted") + (pr.active ? " is-active" : "") });
    const h = card.createDiv({ cls: "vm-prof-head" });
    h.createSpan({ cls: "vm-prof-name", text: emb ? `\u042D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u0438 \xB7 ${pr.model || pr.name}` : pr.name });
    if (pr.ptype) h.createSpan({ cls: "vm-chip", text: PTYPE_RU[pr.ptype] || pr.ptype });
    if (pr.active) h.createSpan({ cls: "vm-chip is-accent", text: "\u043E\u0441\u043D\u043E\u0432\u043D\u0430\u044F" });
    if (!pr.exists) h.createSpan({ cls: "vm-chip is-muted", text: emb ? "\u043F\u0440\u0435\u0436\u043D\u044F\u044F \u043C\u043E\u0434\u0435\u043B\u044C" : "\u043F\u0440\u043E\u0444\u0438\u043B\u044C \u0443\u0434\u0430\u043B\u0451\u043D" });
    const meta = [];
    if (pr.model && !emb) meta.push(pr.model);
    if (pr.steps.length) meta.push("\u0448\u0430\u0433\u0438: " + pr.steps.join(", "));
    if (meta.length) card.createDiv({ cls: "vm-muted vm-small-text", text: meta.join(" \xB7 ") });
    const t = pr.totals[per];
    card.createDiv({ cls: "vm-prof-usage", text: t.calls ? usageLine(t, { time: pr.ptype === "local", cost: pr.ptype === "cloud" }) : `\u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439 ${PERIOD_IN[per]} \u043D\u0435 \u0431\u044B\u043B\u043E` });
    if (pr.budget_month) {
      const pct = pr.budget_pct ?? 0;
      const w = card.createDiv({ cls: "vm-budget" + (pr.budget_state ? ` is-${pr.budget_state}` : "") });
      w.createDiv({ cls: "vm-budget-text vm-small-text", text: `\u041B\u0438\u043C\u0438\u0442 \u043F\u0440\u043E\u0444\u0438\u043B\u044F: ${money(pr.totals.month.cost)} \u0438\u0437 ${money(pr.budget_month)} \u0432 \u044D\u0442\u043E\u043C \u043C\u0435\u0441\u044F\u0446\u0435 \xB7 ${pctText(pct)}` });
      w.createDiv({ cls: "vm-bar" }).createDiv({ cls: "vm-bar-fill" }).style.width = `${Math.min(100, pct)}%`;
    }
    if (pr.ptype !== "cloud" || !pr.exists) return;
    const id = emb ? "emb" : pr.id;
    const draft = this.priceDraft.get(id) || {};
    const prices = pr.prices || { input: null, cached_input: null, output: null };
    const box = card.createDiv({ cls: "vm-prices" });
    box.createDiv({ cls: "vm-small-text vm-prices-title", text: "\u0426\u0435\u043D\u044B, $ \u0437\u0430 1 \u043C\u043B\u043D \u0442\u043E\u043A\u0435\u043D\u043E\u0432" + (pr.priced ? "" : " \u2014 \u043D\u0435 \u0437\u0430\u0434\u0430\u043D\u044B, \u0441\u0442\u043E\u0438\u043C\u043E\u0441\u0442\u044C \u043D\u0435 \u0441\u0447\u0438\u0442\u0430\u0435\u0442\u0441\u044F") });
    if (!pr.priced) box.addClass("is-unpriced");
    const fields = emb ? [["input", "\u0432\u0445\u043E\u0434", prices.input]] : [["input", "\u0432\u0445\u043E\u0434", prices.input], ["cached_input", "\u0432\u0445\u043E\u0434 \u0438\u0437 \u043A\u044D\u0448\u0430", prices.cached_input], ["output", "\u0432\u044B\u0445\u043E\u0434", prices.output]];
    const inputs = {};
    const row = box.createDiv({ cls: "vm-prices-row" });
    for (const [k, label, v] of fields) {
      const f = row.createDiv({ cls: "vm-price" });
      f.createDiv({ cls: "vm-muted vm-small-text", text: label });
      const inp = f.createEl("input", { type: "text", cls: "vm-num", attr: { inputmode: "decimal", placeholder: k === "cached_input" ? "\u043A\u0430\u043A \u0432\u0445\u043E\u0434" : "\u2014" } });
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
    const save = this.button(b, "\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C", async () => {
      const out = {};
      for (const [k] of fields) {
        const v = parseNumber(inputs[k].value, "float", 0, 1e3);
        if (v === null) {
          inputs[k].addClass("vm-invalid");
          new import_obsidian5.Notice("\u0426\u0435\u043D\u0430 \u2014 \u0447\u0438\u0441\u043B\u043E \u043E\u0442 0 \u0434\u043E 1000 \u0434\u043E\u043B\u043B\u0430\u0440\u043E\u0432 \u0437\u0430 \u043C\u0438\u043B\u043B\u0438\u043E\u043D \u0442\u043E\u043A\u0435\u043D\u043E\u0432.");
          return;
        }
        out[k] = v === void 0 ? null : v;
      }
      save.disabled = true;
      const patch = emb ? { embeddings: { price_input: out.input } } : { llm: { profiles: { [id]: { prices: out } } } };
      const r = await p.patchSettings(patch);
      if (!r.ok) {
        new import_obsidian5.Notice(r.error || "\u0426\u0435\u043D\u044B \u043D\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u044B.", 12e3);
        save.disabled = false;
        return;
      }
      this.priceDraft.delete(id);
      new import_obsidian5.Notice(`\u0426\u0435\u043D\u044B \xAB${emb ? "\u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u0438" : pr.name}\xBB \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u044B.`);
      if (pr.totals.all.calls) {
        const ok = await p.confirm({
          title: "\u041F\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u0442\u044C \u043F\u0440\u043E\u0448\u043B\u044B\u0435 \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F?",
          text: `\u0423 \xAB${emb ? "\u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u043E\u0432" : pr.name}\xBB \u0443\u0436\u0435 ${nCalls(pr.totals.all.calls)}. \u041F\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u0442\u044C \u0438\u0445 \u0441\u0442\u043E\u0438\u043C\u043E\u0441\u0442\u044C \u043F\u043E \u043D\u043E\u0432\u044B\u043C \u0446\u0435\u043D\u0430\u043C?

\u0415\u0441\u043B\u0438 \u043D\u0435\u0442 \u2014 \u043D\u043E\u0432\u044B\u0435 \u0446\u0435\u043D\u044B \u043F\u043E\u0434\u0435\u0439\u0441\u0442\u0432\u0443\u044E\u0442 \u0441 \u044D\u0442\u043E\u0433\u043E \u043C\u043E\u043C\u0435\u043D\u0442\u0430, \u0430 \u043F\u0440\u043E\u0448\u043B\u044B\u0435 \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F \u0441\u043E\u0445\u0440\u0430\u043D\u044F\u0442 \u0441\u0442\u043E\u0438\u043C\u043E\u0441\u0442\u044C, \u043F\u043E\u0441\u0447\u0438\u0442\u0430\u043D\u043D\u0443\u044E \u0442\u043E\u0433\u0434\u0430.`,
          ok: "\u041F\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u0442\u044C",
          cancel: "\u041D\u0435 \u043D\u0430\u0434\u043E"
        });
        if (ok) {
          const rr = await p.reprice(id);
          if (rr.ok) new import_obsidian5.Notice(rr.repriced ? `\u0421\u0442\u043E\u0438\u043C\u043E\u0441\u0442\u044C \u043F\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u043D\u0430: \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439 \u2014 ${rr.repriced}.` : "\u041F\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u044B\u0432\u0430\u0442\u044C \u043D\u0435\u0447\u0435\u0433\u043E \u2014 \u0441\u0442\u043E\u0438\u043C\u043E\u0441\u0442\u044C \u043D\u0435 \u0438\u0437\u043C\u0435\u043D\u0438\u043B\u0430\u0441\u044C.");
          else new import_obsidian5.Notice(rr.error || "\u041D\u0435 \u043F\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u043D\u043E.", 12e3);
        }
      }
      this.render(true);
    }, "cta");
  }
  renderSteps(el, u, per) {
    const rows = u.steps.filter((x) => x.totals[per].calls);
    if (!rows.length) return;
    const s = this.section(el, "\u041F\u043E \u0448\u0430\u0433\u0430\u043C", PERIOD_IN[per]);
    const tb = s.createDiv({ cls: "vm-table" });
    const hr = tb.createDiv({ cls: "vm-tr is-head" });
    for (const h of ["\u0428\u0430\u0433", "\u041E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439", "\u0422\u043E\u043A\u0435\u043D\u043E\u0432", "\u0421\u0442\u043E\u0438\u043C\u043E\u0441\u0442\u044C"]) hr.createDiv({ cls: "vm-td", text: h });
    for (const st of rows) {
      const t = st.totals[per];
      const r = tb.createDiv({ cls: "vm-tr" });
      r.createDiv({ cls: "vm-td", text: st.name });
      r.createDiv({ cls: "vm-td is-num", text: num(t.calls) });
      r.createDiv({ cls: "vm-td is-num", text: compact(t.in + t.out), attr: { title: `\u0432\u0445\u043E\u0434 ${num(t.in)}, \u0432\u044B\u0445\u043E\u0434 ${num(t.out)}` } });
      r.createDiv({ cls: "vm-td is-num", text: t.cost || t.unpriced ? money(t.cost) + (t.unpriced ? "*" : "") : "\u2014" });
    }
  }
  renderDays(el, u) {
    const days = u.days || [];
    if (!days.some((d) => d.calls)) return;
    const byCost = days.some((d) => d.cost > 0);
    const s = this.section(el, "\u041F\u043E \u0434\u043D\u044F\u043C", byCost ? "\u0441\u0442\u043E\u0438\u043C\u043E\u0441\u0442\u044C, 31 \u0434\u0435\u043D\u044C" : "\u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F, 31 \u0434\u0435\u043D\u044C");
    const max = Math.max(...days.map((d) => byCost ? d.cost : d.calls), byCost ? 1e-4 : 1);
    const chart = s.createDiv({ cls: "vm-chart" });
    for (const d of days) {
      const v = byCost ? d.cost : d.calls;
      const col = chart.createDiv({ cls: "vm-chart-col" + (d.date === u.today ? " is-today" : ""), attr: { title: `${ruDateTime(d.date)}: ${d.calls ? usageLine(d) : "\u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439 \u043D\u0435 \u0431\u044B\u043B\u043E"}` } });
      const bar = col.createDiv({ cls: "vm-chart-bar" });
      bar.style.height = v ? `${Math.max(3, Math.round(v / max * 100))}%` : "0";
    }
    const lab = s.createDiv({ cls: "vm-chart-labels vm-muted vm-small-text" });
    lab.createSpan({ text: ruDateTime(days[0].date).slice(0, 5) });
    lab.createSpan({ text: `\u043C\u0430\u043A\u0441\u0438\u043C\u0443\u043C: ${byCost ? money(max) : num(max)} \u0432 \u0434\u0435\u043D\u044C` });
    lab.createSpan({ text: "\u0441\u0435\u0433\u043E\u0434\u043D\u044F" });
  }
  renderRuns(el, u) {
    if (!u.runs?.length) return;
    const s = this.section(el, "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435 \u0437\u0430\u043F\u0443\u0441\u043A\u0438");
    for (const r of u.runs.slice(0, 12)) {
      const row = s.createDiv({ cls: "vm-urun" });
      row.createSpan({ cls: "vm-muted vm-small-text vm-urun-when", text: ruDateTime(r.started) });
      row.createSpan({ cls: "vm-urun-what", text: RUN_NAMES[r.cmd || ""] || r.cmd || "\u0437\u0430\u043F\u0443\u0441\u043A" });
      row.createSpan({ cls: "vm-small-text vm-urun-usage", text: usageLine(r, { time: !r.cost && r.sec > 0 }) });
    }
  }
  // ---------- Вопросы ----------
  renderQuestions(el, ui) {
    if (!ui) {
      this.callout(el, "info", "\u0421\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u0435 \u0435\u0449\u0451 \u043D\u0435 \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043D\u043E", null);
      return;
    }
    const p = this.plugin;
    let qs = ui.questions;
    const fc = this.byId(this.qFilter);
    if (fc) {
      const bar = el.createDiv({ cls: "vm-filter" });
      bar.createSpan({ text: "\u0422\u043E\u043B\u044C\u043A\u043E \u0432\u043E\u043F\u0440\u043E\u0441\u044B \u043F\u043E " });
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
      this.callout(el, "ok", "\u041E\u0442\u043A\u0440\u044B\u0442\u044B\u0445 \u0432\u043E\u043F\u0440\u043E\u0441\u043E\u0432 \u043D\u0435\u0442", fc ? "\u041F\u043E \u044D\u0442\u043E\u043C\u0443 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0443 \u0432\u043E\u043F\u0440\u043E\u0441\u043E\u0432 \u043D\u0435\u0442." : null);
      if (ui.status.pending_work) {
        const c = this.callout(el, "info", "\u041E\u0431\u0440\u0430\u0431\u043E\u0442\u043A\u0430 \u043D\u0435 \u0437\u0430\u043A\u043E\u043D\u0447\u0435\u043D\u0430", "\u0427\u0430\u0441\u0442\u044C \u0437\u0430\u043F\u0438\u0441\u0435\u0439 \u0436\u0434\u0430\u043B\u0430 \u043E\u0442\u0432\u0435\u0442\u043E\u0432 \u2014 \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u0435 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u043A\u0443.");
        this.button(c.createDiv({ cls: "vm-buttons" }), "\u041F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u044C \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u043A\u0443 (\u0424\u0430\u0437\u0430 1)", () => p.runPhase1(), "cta", p.engine.busy());
      }
      return;
    }
    if (p.engine.busy()) this.callout(el, "info", null, "\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0441\u0435\u0439\u0447\u0430\u0441 \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 \u2014 \u043E\u0442\u0432\u0435\u0442 \u0432\u0441\u0442\u0430\u043D\u0435\u0442 \u0432 \u043E\u0447\u0435\u0440\u0435\u0434\u044C \u0438 \u043F\u0440\u0438\u043C\u0435\u043D\u0438\u0442\u0441\u044F \u0441\u0440\u0430\u0437\u0443 \u043F\u043E\u0441\u043B\u0435 \u0442\u0435\u043A\u0443\u0449\u0435\u0433\u043E \u0437\u0430\u043F\u0443\u0441\u043A\u0430.");
    for (const q of qs) this.renderQuestion(el, q);
    if (ui.status.pending_work) {
      const c = this.callout(el, "info", null, "\u041A\u043E\u0433\u0434\u0430 \u043E\u0442\u0432\u0435\u0442\u0438\u0442\u0435, \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u0435 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u043A\u0443 \u2014 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0440\u0430\u0437\u043B\u043E\u0436\u0438\u0442 \u0437\u0430\u043F\u0438\u0441\u0438, \u043A\u043E\u0442\u043E\u0440\u044B\u0435 \u0436\u0434\u0430\u043B\u0438 \u043E\u0442\u0432\u0435\u0442\u043E\u0432.");
      this.button(c.createDiv({ cls: "vm-buttons" }), "\u041F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u044C \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u043A\u0443 (\u0424\u0430\u0437\u0430 1)", () => p.runPhase1(), "cta", p.engine.busy());
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
        const chip = links.createSpan({ cls: "vm-chip is-link", attr: { title: "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440 \u0432 \u043F\u0430\u043D\u0435\u043B\u0438" } });
        this.dot(chip, c.color);
        chip.appendText(c.title);
        chip.addEventListener("click", () => this.show("container", c.id));
      }
      if (q.entity_path) {
        const a = links.createEl("a", { cls: "vm-link", text: "\u043E\u0442\u043A\u0440\u044B\u0442\u044C \u0437\u0430\u043F\u0438\u0441\u044C" });
        a.addEventListener("click", () => p.open(q.entity_path));
      }
    }
    const text = card.createDiv({ cls: "vm-q-text markdown-rendered" });
    import_obsidian5.MarkdownRenderer.render(this.app, q.text, text, q.entity_path || "", this).then(() => this.hookLinks(text));
    if (q.note) card.createDiv({ cls: "vm-q-note", text: q.note });
    const err = this.answerError.get(q.id);
    if (err && err !== q.note) card.createDiv({ cls: "vm-q-note", text: err });
    if (job) card.createDiv({ cls: "vm-q-state", text: job.status === "queued" ? "\u0412 \u043E\u0447\u0435\u0440\u0435\u0434\u0438 \u2014 \u043F\u0440\u0438\u043C\u0435\u043D\u0438\u0442\u0441\u044F \u043F\u043E\u0441\u043B\u0435 \u0442\u0435\u043A\u0443\u0449\u0435\u0433\u043E \u0437\u0430\u043F\u0443\u0441\u043A\u0430\u2026" : "\u041F\u0440\u0438\u043C\u0435\u043D\u044F\u044E \u043E\u0442\u0432\u0435\u0442\u2026" });
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
      const ta = box.createEl("textarea", { attr: { rows: "2", placeholder: q.free_hint || "\u0421\u0432\u043E\u0439 \u043E\u0442\u0432\u0435\u0442" } });
      ta.value = this.freeText.get(q.id) || "";
      ta.addEventListener("input", () => this.freeText.set(q.id, ta.value));
      const b = box.createEl("button", { text: "\u041E\u0442\u0432\u0435\u0442\u0438\u0442\u044C", cls: "mod-cta" });
      b.disabled = !!job;
      b.addEventListener("click", () => {
        const t = ta.value.trim();
        if (!t) {
          new import_obsidian5.Notice("\u041D\u0430\u043F\u0438\u0448\u0438\u0442\u0435 \u043E\u0442\u0432\u0435\u0442.");
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
      new import_obsidian5.Notice(`\u041E\u0442\u0432\u0435\u0442 \u043D\u0430 ${q.id} \u043F\u0440\u0438\u043D\u044F\u0442.`);
    } else this.answerError.set(q.id, r.note || r.error || "\u041E\u0442\u0432\u0435\u0442 \u043D\u0435 \u043F\u0440\u0438\u043D\u044F\u0442.");
    this.render();
  }
  // ---------- Контейнер ----------
  renderContainerTab(el, ui) {
    if (!ui || !ui.containers.length) {
      this.callout(el, "info", "\u041A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u043E\u0432 \u043F\u043E\u043A\u0430 \u043D\u0435\u0442", "\u041E\u043D\u0438 \u043F\u043E\u044F\u0432\u044F\u0442\u0441\u044F \u043F\u043E\u0441\u043B\u0435 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0438\u044F \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u044B.");
      return;
    }
    const bar = el.createDiv({ cls: "vm-cbar" });
    const sel = bar.createEl("select", { cls: "dropdown" });
    sel.createEl("option", { text: "\u2014 \u0432\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440 \u2014", attr: { value: "" } });
    for (const c2 of ui.containers) sel.createEl("option", { text: "\xA0\xA0\xA0".repeat(c2.depth) + c2.title, attr: { value: c2.id } });
    sel.value = this.selectedId || "";
    sel.addEventListener("change", () => {
      this.follow = false;
      this.selectedId = sel.value || null;
      this.render(true);
    });
    const fb = bar.createEl("button", {
      cls: "vm-small" + (this.follow ? " is-active" : ""),
      text: this.follow ? "\u2713 \u043F\u043E \u043E\u0442\u043A\u0440\u044B\u0442\u043E\u0439 \u0437\u0430\u043C\u0435\u0442\u043A\u0435" : "\u043F\u043E \u043E\u0442\u043A\u0440\u044B\u0442\u043E\u0439 \u0437\u0430\u043C\u0435\u0442\u043A\u0435",
      attr: { title: "\u041F\u043E\u043A\u0430\u0437\u044B\u0432\u0430\u0442\u044C \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440 \u0437\u0430\u043C\u0435\u0442\u043A\u0438, \u043E\u0442\u043A\u0440\u044B\u0442\u043E\u0439 \u0432 \u0440\u0435\u0434\u0430\u043A\u0442\u043E\u0440\u0435" }
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
      el.createDiv({ cls: "vm-empty", text: "\u041E\u0442\u043A\u0440\u043E\u0439\u0442\u0435 \u0437\u0430\u043C\u0435\u0442\u043A\u0443 \u0438\u0437 \u043F\u0430\u043F\u043A\u0438 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430 \u0438\u043B\u0438 \u0432\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440 \u0432 \u0441\u043F\u0438\u0441\u043A\u0435." });
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
    const a = t.createEl("a", { cls: "vm-link", text: c.title, attr: { title: "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0437\u0430\u043C\u0435\u0442\u043A\u0443 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430" } });
    a.addEventListener("click", () => p.open(c.path));
    if (c.description) head.createDiv({ cls: "vm-cdesc", text: c.description });
    const meta = head.createDiv({ cls: "vm-cmeta" });
    const typeSel = meta.createEl("select", { cls: "dropdown", attr: { title: "\u0422\u0438\u043F \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430" } });
    for (const [k, v] of Object.entries(ui.types || {})) typeSel.createEl("option", { text: v, attr: { value: k } });
    typeSel.value = c.type;
    typeSel.addEventListener("change", () => p.setContainerField(c, "type", typeSel.value, `\u0442\u0438\u043F: ${ui.types[typeSel.value]}`));
    const stSel = meta.createEl("select", { cls: "dropdown", attr: { title: "\u0421\u0442\u0430\u0442\u0443\u0441 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430" } });
    for (const [k, v] of Object.entries(ui.statuses || {})) stSel.createEl("option", { text: v, attr: { value: k } });
    stSel.value = c.status;
    stSel.addEventListener("change", () => p.setContainerField(c, "container_status", stSel.value, `\u0441\u0442\u0430\u0442\u0443\u0441: ${ui.statuses[stSel.value]}`));
    const facts = head.createDiv({ cls: "vm-facts" });
    const fact = (k, v, onClick) => {
      const r = facts.createDiv({ cls: "vm-fact" });
      r.createSpan({ cls: "vm-fact-k", text: k });
      const val = r.createSpan({ cls: "vm-fact-v" + (onClick ? " vm-link" : ""), text: v });
      if (onClick) val.addEventListener("click", onClick);
    };
    fact("\u0417\u0430\u043F\u0438\u0441\u0438", nRecords(c.entities) + (c.shared ? `, \u0435\u0449\u0451 \u043E\u0431\u0449\u0438\u0445: ${c.shared}` : ""));
    if (c.questions)
      fact("\u0412\u043E\u043F\u0440\u043E\u0441\u044B", nQuestions(c.questions), () => {
        this.qFilter = c.id;
        this.show("questions");
      });
    if (c.base) {
      fact("\u0411\u0430\u0437\u0430 \u0441\u0438\u043D\u0442\u0435\u0437\u0430", `${c.base.items} \u0430\u0441\u043F\u0435\u043A\u0442\u043E\u0432, \u043F\u0435\u0440\u0432\u043E\u0441\u0442\u0435\u043F\u0435\u043D\u043D\u044B\u0445 ${c.base.primary}` + (c.base.conflicts ? `, \u043F\u0440\u043E\u0442\u0438\u0432\u043E\u0440\u0435\u0447\u0438\u0439 ${c.base.conflicts}` : ""));
      if (c.base.excluded) fact("\u041D\u0438\u0436\u0435 \u043F\u043E\u0440\u043E\u0433\u0430 \u0446\u0435\u043D\u043D\u043E\u0441\u0442\u0438", String(c.base.excluded));
    } else fact("\u0411\u0430\u0437\u0430 \u0441\u0438\u043D\u0442\u0435\u0437\u0430", "\u0435\u0449\u0451 \u043D\u0435 \u0441\u043E\u0431\u0440\u0430\u043D\u0430");
    if (c.dirty) fact("\u041F\u0435\u0440\u0435\u0441\u0431\u043E\u0440\u043A\u0430", "\u0431\u0430\u0437\u0430 \u043F\u0435\u0440\u0435\u0441\u043E\u0431\u0435\u0440\u0451\u0442\u0441\u044F \u043F\u0440\u0438 \u0424\u0430\u0437\u0435 1" + (c.dirty_reasons.length ? ` (${c.dirty_reasons.join(", ")})` : ""));
    if (c.last_modified) fact("\u0418\u0437\u043C\u0435\u043D\u0451\u043D", ruDateTime(c.last_modified));
    const views = head.createDiv({ cls: "vm-links-row" });
    if (c.views.pool) views.createEl("a", { cls: "vm-link", text: "\u043F\u0443\u043B \u0430\u0441\u043F\u0435\u043A\u0442\u043E\u0432" }).addEventListener("click", () => p.open(c.views.pool));
    if (c.views.base) views.createEl("a", { cls: "vm-link", text: "\u0431\u0430\u0437\u0430 \u0441\u0438\u043D\u0442\u0435\u0437\u0430" }).addEventListener("click", () => p.open(c.views.base));
  }
  renderDocs(el, c) {
    const p = this.plugin;
    const s = this.section(el, "\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B");
    if (!c.products.length) s.createDiv({ cls: "vm-muted", text: "\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u043E\u0432 \u043F\u043E\u043A\u0430 \u043D\u0435\u0442." });
    for (const d of c.products) {
      const row = s.createDiv({ cls: "vm-doc" });
      row.createEl("a", { cls: "vm-link", text: d.title }).addEventListener("click", () => p.open(d.path));
      if (d.needs_review) row.createSpan({ cls: "vm-chip is-warning", text: "\u043D\u0430 \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0435", attr: { title: "\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043F\u0440\u043E\u0441\u0438\u0442 \u043F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C: \u0432 \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u0435 \u0435\u0441\u0442\u044C \u043F\u043E\u043C\u0435\u0442\u043A\u0438" } });
    }
    const b = s.createDiv({ cls: "vm-buttons" });
    this.button(b, c.products.length ? "\u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B (\u0424\u0430\u0437\u0430 2)" : "\u041D\u0430\u043F\u0438\u0441\u0430\u0442\u044C \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B (\u0424\u0430\u0437\u0430 2)", () => p.runSynth(c), "cta");
    this.button(b, "\u041F\u0435\u0440\u0435\u043F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u0440\u0430\u0441\u043A\u043B\u0430\u0434\u043A\u0443", () => p.runRevalidate(c));
  }
  renderThresholds(el, ui, c) {
    const p = this.plugin;
    const s = this.section(el, "\u041F\u043E\u0440\u043E\u0433\u0438 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430");
    s.createDiv({
      cls: "vm-muted vm-small-text",
      text: "\u0421\u0432\u043E\u0438 \u0437\u043D\u0430\u0447\u0435\u043D\u0438\u044F \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u044E\u0442 \u043D\u0430 \u044D\u0442\u043E\u0442 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440 \u0438 \u0432\u043B\u043E\u0436\u0435\u043D\u043D\u044B\u0435 \u0432 \u043D\u0435\u0433\u043E. \u041F\u0443\u0441\u0442\u043E\u0435 \u043F\u043E\u043B\u0435 \u2014 \u043A\u0430\u043A \u0443 \u0440\u043E\u0434\u0438\u0442\u0435\u043B\u044F \u0438\u043B\u0438 \u043E\u0431\u0449\u0438\u0439 \u043F\u043E\u0440\u043E\u0433 \u0438\u0437 \u043D\u0430\u0441\u0442\u0440\u043E\u0435\u043A (\u043E\u043D \u043F\u043E\u043A\u0430\u0437\u0430\u043D \u0441\u0435\u0440\u044B\u043C); \u21BA \u2014 \u0443\u0431\u0440\u0430\u0442\u044C \u0441\u0432\u043E\u0439 \u043F\u043E\u0440\u043E\u0433."
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
      save.setText(n ? `\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C (${n})` : "\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C");
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
      const help = row.createDiv({ cls: "vm-thr-help vm-hidden", text: `${info.help} \u0414\u043E\u043F\u0443\u0441\u0442\u0438\u043C\u043E: ${rangeText(info.kind, info.min, info.max)}.` });
      lab.addEventListener("click", () => help.toggleClass("vm-hidden", !help.hasClass("vm-hidden")));
      const ctl = row.createDiv({ cls: "vm-thr-ctl" });
      const rng = ctl.createEl("input", { type: "range", cls: "slider vm-thr-range" });
      rng.min = String(info.min);
      rng.max = String(info.max);
      rng.step = String(info.step || (info.kind === "int" ? 1 : 0.01));
      const inp = ctl.createEl("input", { type: "text", cls: "vm-thr-input", attr: { inputmode: "decimal" } });
      inp.value = k in draft ? draft[k] : own !== void 0 ? String(own) : "";
      inp.placeholder = inherited != null ? String(inherited) : tv ? String(tv.value) : "";
      const resetTip = `\u0423\u0431\u0440\u0430\u0442\u044C \u0441\u0432\u043E\u0439 \u043F\u043E\u0440\u043E\u0433: \u0431\u0443\u0434\u0435\u0442 ${inhFrom ? `\u043A\u0430\u043A \u0443 \xAB${inhFrom}\xBB` : "\u043E\u0431\u0449\u0438\u0439"} (${inherited})`;
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
        rs.setAttr("title", empty ? `\u0421\u0432\u043E\u0439 \u043F\u043E\u0440\u043E\u0433 \u043D\u0435 \u0437\u0430\u0434\u0430\u043D \u2014 \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u0435\u0442 ${inhFrom ? `\u043F\u043E\u0440\u043E\u0433 \xAB${inhFrom}\xBB` : "\u043E\u0431\u0449\u0438\u0439"} (${inherited})` : resetTip);
        src.setText(!empty ? v === own ? "\u0441\u0432\u043E\u0439" : "\u0441\u0432\u043E\u0439, \u043D\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D" : inhFrom ? `\u043E\u0442 \xAB${inhFrom}\xBB` : "\u043E\u0431\u0449\u0438\u0439");
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
    save = this.button(b, "\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C", async () => {
      const { changes, bad } = collect();
      if (bad.length) return;
      save.disabled = true;
      const ok = await p.saveThresholds(c, changes);
      if (ok) {
        this.thrDraft.delete(c.id);
        new import_obsidian5.Notice(`\u041F\u043E\u0440\u043E\u0433\u0438 \xAB${c.title}\xBB \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u044B \u2014 \u043F\u043E\u0434\u0435\u0439\u0441\u0442\u0432\u0443\u044E\u0442 \u0441\u043E \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0435\u0439 \u0424\u0430\u0437\u044B 1.`);
      }
      this.render(true);
    }, "cta");
    reset = this.button(b, "\u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C \u043F\u0440\u0430\u0432\u043A\u0443", () => {
      this.thrDraft.delete(c.id);
      this.render(true);
    });
    this.button(b, "\u041F\u043E\u0441\u043E\u0432\u0435\u0442\u043E\u0432\u0430\u0442\u044C\u0441\u044F \u0441 \u0418\u0418", () => p.openAdvice(c));
    upd();
    const last = p.advice.get(c.id);
    if (last) {
      const a = this.callout(s, "accent", "\u0415\u0441\u0442\u044C \u0441\u043E\u0432\u0435\u0442 \u0418\u0418", `${ruDateTime(last.at)}: ${last.advice.summary}`);
      this.button(a.createDiv({ cls: "vm-buttons" }), "\u041F\u043E\u043A\u0430\u0437\u0430\u0442\u044C \u0441\u043E\u0432\u0435\u0442", () => p.openAdvice(c, last.advice));
    }
    s.createDiv({
      cls: "vm-muted vm-small-text",
      text: "\u041F\u043E\u0440\u043E\u0433\u0438 \u0440\u0430\u0441\u043A\u043B\u0430\u0434\u043A\u0438 \u0438 \u0443\u043F\u043B\u043E\u0442\u043D\u0435\u043D\u0438\u044F \u0441\u0440\u0430\u0431\u043E\u0442\u0430\u044E\u0442 \u043D\u0430 \u043D\u043E\u0432\u044B\u0445 \u0437\u0430\u043F\u0438\u0441\u044F\u0445. \u041F\u043E\u0440\u043E\u0433\u0438 \u0446\u0435\u043D\u043D\u043E\u0441\u0442\u0438 \u043F\u0435\u0440\u0435\u0441\u043E\u0431\u0435\u0440\u0443\u0442 \u0431\u0430\u0437\u0443 \u0441\u0438\u043D\u0442\u0435\u0437\u0430 \u043F\u0440\u0438 \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0435\u0439 \u0424\u0430\u0437\u0435 1 \u2014 \u0431\u0435\u0437 \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439 \u043A \u043C\u043E\u0434\u0435\u043B\u0438."
    });
  }
  renderStyle(el, c) {
    const p = this.plugin;
    const s = this.section(el, "\u0421\u0442\u0438\u043B\u044C \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u043E\u0432");
    const inherited = !c.style && c.style_effective ? `\u0421\u0435\u0439\u0447\u0430\u0441 \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u0435\u0442 \u0441\u0442\u0438\u043B\u044C \xAB${c.style_from}\xBB: ${c.style_effective}` : "\u041D\u0430\u043F\u0440\u0438\u043C\u0435\u0440: \xAB\u041F\u0438\u0448\u0438 \u043A\u0430\u043A \u0431\u0438\u0437\u043D\u0435\u0441-\u043F\u043B\u0430\u043D, \u0441 \u0446\u0438\u0444\u0440\u0430\u043C\u0438 \u0438 \u0441\u0440\u043E\u043A\u0430\u043C\u0438\xBB.";
    const ta = s.createEl("textarea", { cls: "vm-style", attr: { rows: "3", placeholder: inherited } });
    ta.value = this.styleDraft.get(c.id) ?? c.style;
    const b = s.createDiv({ cls: "vm-buttons" });
    const save = this.button(b, "\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C \u0441\u0442\u0438\u043B\u044C", async () => {
      save.disabled = true;
      const ok = await p.saveStyle(c, ta.value.trim());
      if (ok) {
        this.styleDraft.delete(c.id);
        new import_obsidian5.Notice(`\u0421\u0442\u0438\u043B\u044C \xAB${c.title}\xBB \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D \u2014 \u0443\u0447\u0442\u0451\u0442\u0441\u044F \u043F\u0440\u0438 \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0435\u0439 \u0424\u0430\u0437\u0435 2.`);
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
      text: "\u0414\u043E\u0431\u0430\u0432\u043B\u044F\u0435\u0442\u0441\u044F \u043A \u043E\u0431\u0449\u0435\u043C\u0443 \u0441\u0442\u0438\u043B\u044E \u0438\u0437 \u043D\u0430\u0441\u0442\u0440\u043E\u0435\u043A \u0438 \u0432\u0430\u0436\u043D\u0435\u0435 \u043D\u0435\u0433\u043E. \u0414\u0435\u0439\u0441\u0442\u0432\u0443\u0435\u0442 \u0438 \u043D\u0430 \u0432\u043B\u043E\u0436\u0435\u043D\u043D\u044B\u0435 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u044B, \u0435\u0441\u043B\u0438 \u0443 \u043D\u0438\u0445 \u043D\u0435\u0442 \u0441\u0432\u043E\u0435\u0433\u043E."
    });
  }
  // ---------- Журнал ----------
  renderLog(el, ui) {
    const p = this.plugin;
    const eng = p.engine;
    const logs = this.section(el, "\u041B\u043E\u0433\u0438 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B");
    const lb = logs.createDiv({ cls: "vm-buttons" });
    const L = ui?.logs || {};
    if (L.changes) this.button(lb, "\u0418\u0437\u043C\u0435\u043D\u0435\u043D\u0438\u044F", () => p.open(L.changes));
    if (L.reasoning) this.button(lb, "\u0420\u0430\u0441\u0441\u0443\u0436\u0434\u0435\u043D\u0438\u044F \u043C\u043E\u0434\u0435\u043B\u0438", () => p.open(L.reasoning));
    if (L.archive) this.button(lb, "\u0410\u0440\u0445\u0438\u0432 \u0432\u043E\u043F\u0440\u043E\u0441\u043E\u0432", () => p.open(L.archive));
    if (L.errors) this.button(lb, "\u041E\u0448\u0438\u0431\u043A\u0438", () => p.open(L.errors));
    this.button(lb, "open-questions.md", () => p.open("open-questions.md"));
    const s = this.section(el, "\u0417\u0430\u043F\u0443\u0441\u043A\u0438 \u0432 \u044D\u0442\u043E\u043C \u0441\u0435\u0430\u043D\u0441\u0435");
    const jobs = [];
    if (eng.current && !eng.current.quiet) jobs.push(eng.current);
    jobs.push(...eng.pending(), ...eng.history);
    if (!jobs.length) {
      s.createDiv({ cls: "vm-muted", text: "\u041F\u043E\u043A\u0430 \u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u0437\u0430\u043F\u0443\u0441\u043A\u0430\u043B\u043E\u0441\u044C." });
      return;
    }
    const icon = { queued: "\u29D7", running: "\u25B6", done: "\u2713", failed: "\u2717", stopped: "\u25A0", cancelled: "\u2013" };
    for (const j of jobs) {
      const card = s.createDiv({ cls: `vm-job is-${j.status}` });
      const h = card.createDiv({ cls: "vm-job-head" });
      h.createSpan({ cls: "vm-job-icon", text: icon[j.status] || "" });
      h.createSpan({ cls: "vm-job-label", text: j.label });
      const when = j.startedAt ? clock(j.startedAt) : clock(j.queuedAt);
      const dur = j.startedAt ? duration((j.finishedAt || Date.now()) - j.startedAt) : "\u0432 \u043E\u0447\u0435\u0440\u0435\u0434\u0438";
      h.createSpan({ cls: "vm-muted vm-job-time", text: `${when} \xB7 ${dur}` });
      const r = j.result;
      if (r) {
        const sl = statsLine(r.stats);
        if (r.unchanged) card.createDiv({ text: "\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B \u0430\u043A\u0442\u0443\u0430\u043B\u044C\u043D\u044B \u2014 \u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u043F\u0435\u0440\u0435\u043F\u0438\u0441\u0430\u043D\u043E." });
        else if (r.title && r.ok) card.createDiv({ text: r.title + (sl ? ` \u2014 ${sl}` : "") });
        if (r.error) card.createDiv({ cls: "vm-job-error", text: r.error });
        const cl = callsLine(r.calls);
        if (cl) card.createDiv({ cls: "vm-muted vm-small-text", text: cl });
        const ru = r.run_usage;
        if (ru && ru.calls) {
          const extra = [ru.cost ? money(ru.cost) + (ru.unpriced ? "*" : "") : "", ru.sec ? `\u043C\u043E\u0434\u0435\u043B\u0438 \u0434\u0443\u043C\u0430\u043B\u0438 ${durationText(ru.sec)}` : "", r.elapsed ? `\u0432\u0435\u0441\u044C \u0437\u0430\u043F\u0443\u0441\u043A ${durationText(r.elapsed)}` : ""].filter(Boolean);
          card.createDiv({ cls: "vm-muted vm-small-text", text: `\u0422\u043E\u043A\u0435\u043D\u043E\u0432 ${compact(ru.in)} \u2192 ${compact(ru.out)}` + (extra.length ? " \xB7 " + extra.join(" \xB7 ") : "") });
        }
        for (const w of r.warnings || []) card.createDiv({ cls: "vm-small-text vm-warn-line", text: "! " + w });
        for (const n of r.notices || []) card.createDiv({ cls: "vm-small-text vm-muted", text: "\u2022 " + n });
      }
      if (j.lines.length || j.args.length) {
        const open = this.openJobs.has(j.id);
        const t = card.createEl("a", { cls: "vm-link vm-small-text", text: open ? "\u0441\u043A\u0440\u044B\u0442\u044C \u0432\u044B\u0432\u043E\u0434 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B" : "\u0432\u044B\u0432\u043E\u0434 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B" });
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
var APPROVE = "\u0421\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u0430 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0430";
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
      this.osNotify("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433", text, "notice");
    };
    this.engine.onAsk = (job, ask) => this.askUser(job, ask);
    this.registerView(VIEW_TYPE, (leaf) => new BrainView(leaf, this));
    this.addRibbonIcon("brain", "\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433", () => this.openView());
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
  catchErrors() {
    const mark = "plugin:" + encodeURIComponent(this.manifest.id);
    const mine = (e, file) => errParts(e).stack.includes(mark) || String(file || "").includes(mark);
    this.registerDomEvent(window, "error", (ev) => {
      if (mine(ev.error, ev.filename)) this.errors.add("\u043D\u0435\u043F\u0435\u0440\u0435\u0445\u0432\u0430\u0447\u0435\u043D\u043D\u0430\u044F \u043E\u0448\u0438\u0431\u043A\u0430", ev.error || ev.message, true);
    });
    this.registerDomEvent(window, "unhandledrejection", (ev) => {
      if (mine(ev.reason)) this.errors.add("\u043D\u0435\u043F\u0435\u0440\u0435\u0445\u0432\u0430\u0447\u0435\u043D\u043D\u0430\u044F \u043E\u0448\u0438\u0431\u043A\u0430", ev.reason, true);
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
  // ---------- обновления ----------
  /** При запуске Obsidian: новая версия плагина в папке программы? новая версия программы на GitHub? */
  async startupChecks() {
    if (this.engine.problem()) return;
    try {
      if (await this.offerPluginFromProgram()) return;
      const u = this.ui?.updates;
      if (u?.repo && u.check_on_start) await this.checkUpdates(false);
    } catch (e) {
      console.warn("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433: \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0430 \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0439", e);
    }
  }
  /** Версия плагина, которая лежит в папке программы (её кладёт туда обновление или распаковка нового архива). */
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
  /** В папке программы плагин новее установленного — предложить поставить его в хранилище. */
  async offerPluginFromProgram() {
    const v = await this.programPluginVersion();
    if (!v || !newerVersion(v, this.manifest.version)) return false;
    const ch = await choiceModal(this.app, {
      title: "\u041D\u043E\u0432\u0430\u044F \u0432\u0435\u0440\u0441\u0438\u044F \u043F\u043B\u0430\u0433\u0438\u043D\u0430",
      text: `\u0412 \u043F\u0430\u043F\u043A\u0435 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B \u043B\u0435\u0436\u0438\u0442 \u043F\u043B\u0430\u0433\u0438\u043D \u0432\u0435\u0440\u0441\u0438\u0438 ${v}, \u0430 \u0432 Obsidian \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 ${this.manifest.version}. \u0423\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C \u043D\u043E\u0432\u044B\u0439? \u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u043F\u043B\u0430\u0433\u0438\u043D\u0430 \u0441\u043E\u0445\u0440\u0430\u043D\u044F\u0442\u0441\u044F; \u043F\u043E\u0441\u043B\u0435 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0438 Obsidian \u043D\u0443\u0436\u043D\u043E \u043F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C.`,
      options: [{ label: "\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C", kind: "cta" }, { label: "\u041F\u043E\u0437\u0436\u0435" }]
    }).result;
    if (ch !== 0) return true;
    const r = await this.engine.run(["install-plugin", this.engine.vaultPath()], { label: "\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0430 \u043F\u043B\u0430\u0433\u0438\u043D\u0430" });
    if (!r.ok) {
      new import_obsidian6.Notice(`\u041F\u043B\u0430\u0433\u0438\u043D \u043D\u0435 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D: ${r.error || "\u043E\u0448\u0438\u0431\u043A\u0430"}`, 15e3);
      return true;
    }
    await this.offerRestart(`\u041F\u043B\u0430\u0433\u0438\u043D ${v} \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D.`);
    return true;
  }
  /** Проверить новую версию программы на GitHub; manual — по кнопке (сообщить и «последняя версия»). */
  async checkUpdates(manual) {
    const prob = this.engine.problem();
    if (prob) {
      if (manual) new import_obsidian6.Notice(prob, 1e4);
      return;
    }
    const r = await this.engine.run(["update", "--check"], { label: "\u041F\u0440\u043E\u0432\u0435\u0440\u043A\u0430 \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0439", exclusive: false, quiet: true });
    if (!r.ok || !r.update) {
      if (manual) new import_obsidian6.Notice(`\u041F\u0440\u043E\u0432\u0435\u0440\u043A\u0430 \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0439: ${r.error || "\u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043D\u0435 \u043E\u0442\u0432\u0435\u0442\u0438\u043B\u0430"}`, 12e3);
      else console.warn("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433: \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0430 \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0439 \u2014", r.error);
      return;
    }
    const u = r.update;
    if (!u.newer) {
      if (manual) new import_obsidian6.Notice(`\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u0430 \u043F\u043E\u0441\u043B\u0435\u0434\u043D\u044F\u044F \u0432\u0435\u0440\u0441\u0438\u044F: ${u.current} (\u0432 \u0440\u0435\u043F\u043E\u0437\u0438\u0442\u043E\u0440\u0438\u0438 ${u.repo} \u2014 ${u.version || "?"}).`, 8e3);
      return;
    }
    if (!manual && this.data.skipVersion && this.data.skipVersion === u.version) return;
    const notes = (u.notes || "").split("\n").slice(0, 40).join("\n").trim();
    const from = u.source === "release" ? `\u0440\u0435\u043B\u0438\u0437 ${u.tag || u.version}` : `\u0432\u0435\u0442\u043A\u0430 ${u.branch || "main"}`;
    const ch = await choiceModal(this.app, {
      title: `\u0412\u044B\u0448\u043B\u0430 \u043D\u043E\u0432\u0430\u044F \u0432\u0435\u0440\u0441\u0438\u044F: ${u.version}`,
      sub: `${u.repo} \xB7 ${from}`,
      text: `\u0421\u0435\u0439\u0447\u0430\u0441 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u0430 ${u.current}. \u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435 \u0437\u0430\u043C\u0435\u043D\u0438\u0442 \u0444\u0430\u0439\u043B\u044B \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B \u0438 \u043F\u043B\u0430\u0433\u0438\u043D\u0430; \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438, \u043A\u043B\u044E\u0447\u0438 \u0438 \u0445\u0440\u0430\u043D\u0438\u043B\u0438\u0449\u0435 \u043D\u0435 \u043C\u0435\u043D\u044F\u044E\u0442\u0441\u044F. \u041F\u0440\u043E\u043C\u043F\u0442\u044B, \u043A\u043E\u0442\u043E\u0440\u044B\u0435 \u0432\u044B \u043F\u0440\u0430\u0432\u0438\u043B\u0438, \u043D\u0435 \u043F\u0440\u043E\u043F\u0430\u0434\u0443\u0442: \u0435\u0441\u043B\u0438 \u0432 \u043D\u043E\u0432\u043E\u0439 \u0432\u0435\u0440\u0441\u0438\u0438 \u043E\u043D\u0438 \u0438\u0437\u043C\u0435\u043D\u0438\u043B\u0438\u0441\u044C, \u0432\u0430\u0448\u0438 \u043A\u043E\u043F\u0438\u0438 \u043B\u044F\u0433\u0443\u0442 \u0432 \u043F\u0430\u043F\u043A\u0443 prompts/_\u043F\u0440\u0435\u0436\u043D\u0438\u0435.`,
      pre: notes || void 0,
      options: [{ label: "\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C", kind: "cta" }, { label: "\u041F\u043E\u0437\u0436\u0435" }, { label: "\u041F\u0440\u043E\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u044D\u0442\u0443 \u0432\u0435\u0440\u0441\u0438\u044E" }]
    }).result;
    if (ch === 2) {
      this.data.skipVersion = u.version || "";
      await this.saveData(this.data);
      new import_obsidian6.Notice(`\u0412\u0435\u0440\u0441\u0438\u044F ${u.version} \u043F\u0440\u043E\u043F\u0443\u0449\u0435\u043D\u0430. \u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u0432\u0440\u0443\u0447\u043D\u0443\u044E \u2014 \xAB\u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u2192 \u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433 \u2192 \u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u044F\xBB.`, 8e3);
    } else if (ch === 0) await this.installUpdate(u);
  }
  async installUpdate(u) {
    if (this.engine.busy()) new import_obsidian6.Notice("\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435 \u043D\u0430\u0447\u043D\u0451\u0442\u0441\u044F \u043F\u043E\u0441\u043B\u0435 \u0442\u0435\u043A\u0443\u0449\u0435\u0433\u043E \u0437\u0430\u043F\u0443\u0441\u043A\u0430.", 6e3);
    const r = await this.engine.run(["update", "--yes"], { label: `\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435 \u0434\u043E ${u.version}` });
    if (!r.ok) {
      new import_obsidian6.Notice(`\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435 \u043D\u0435 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u043E: ${r.error || "\u043E\u0448\u0438\u0431\u043A\u0430"}`, 15e3);
      return;
    }
    const inst = r.installed;
    if (!inst) {
      new import_obsidian6.Notice(r.title || "\u041E\u0431\u043D\u043E\u0432\u043B\u044F\u0442\u044C \u043D\u0435\u0447\u0435\u0433\u043E.", 8e3);
      return;
    }
    await this.refreshState(true);
    const lines = [`\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u043E \u0444\u0430\u0439\u043B\u043E\u0432: ${inst.updated}, \u043D\u043E\u0432\u044B\u0445: ${inst.added}` + (inst.removed.length ? `, \u0443\u0434\u0430\u043B\u0435\u043D\u043E \u0443\u0441\u0442\u0430\u0440\u0435\u0432\u0448\u0438\u0445: ${inst.removed.length}` : "") + "."];
    for (const n of inst.notes || []) lines.push(n);
    if (r.restart) await this.offerRestart(`\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u0430 \u0432\u0435\u0440\u0441\u0438\u044F ${inst.version}.`, lines);
    else
      await choiceModal(this.app, {
        title: `\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u0430 \u0432\u0435\u0440\u0441\u0438\u044F ${inst.version}`,
        lines,
        text: "\u041F\u043B\u0430\u0433\u0438\u043D \u0432 \u044D\u0442\u043E\u043C \u0445\u0440\u0430\u043D\u0438\u043B\u0438\u0449\u0435 \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D \u2014 \u0435\u0441\u043B\u0438 \u043E\u043D \u0441\u0442\u043E\u0438\u0442 \u0432 \u0434\u0440\u0443\u0433\u043E\u043C, \u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u0435 \xAB\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0430.bat\xBB \u0438 \u0432\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u044D\u0442\u043E \u0445\u0440\u0430\u043D\u0438\u043B\u0438\u0449\u0435.",
        options: [{ label: "\u0413\u043E\u0442\u043E\u0432\u043E", kind: "cta" }]
      }).result;
  }
  /** Окно «перезапустить Obsidian» — новый плагин заработает после перезапуска. */
  async offerRestart(title, lines) {
    const ch = await choiceModal(this.app, {
      title,
      lines,
      text: "\u0427\u0442\u043E\u0431\u044B \u0437\u0430\u0440\u0430\u0431\u043E\u0442\u0430\u043B \u043D\u043E\u0432\u044B\u0439 \u043F\u043B\u0430\u0433\u0438\u043D, Obsidian \u043D\u0443\u0436\u043D\u043E \u043F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C. \u041E\u0442\u043A\u0440\u044B\u0442\u044B\u0435 \u0437\u0430\u043C\u0435\u0442\u043A\u0438 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u044B.",
      options: [{ label: "\u041F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C Obsidian", kind: "cta" }, { label: "\u041F\u043E\u0437\u0436\u0435" }]
    }).result;
    if (ch === 0) {
      const cmds = this.app.commands;
      if (!cmds?.executeCommandById?.("app:reload")) window.location.reload();
    }
  }
  // ---------- вопросы посреди запуска и уведомления Windows ----------
  askUser(job, ask) {
    this.osNotify("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433 \u0436\u0434\u0451\u0442 \u043E\u0442\u0432\u0435\u0442\u0430", `${job.label}: ${ask.title}`, "ask");
    const m = choiceModal(this.app, { ...askOptions(ask), sub: job.label });
    job.askCancel = m.close;
    this.refresh();
    return m.result;
  }
  /** Какое-нибудь окно Obsidian сейчас в фокусе: главное, отдельные окна с вкладками, окно настроек (Obsidian 1.15+). */
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
  /** Уведомление Windows (системное). force — проверка из настроек: без условий. */
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
      console.warn("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433: \u0443\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u0435 \u043D\u0435 \u043F\u043E\u043A\u0430\u0437\u0430\u043D\u043E", e);
      return false;
    }
  }
  /** Долгий запуск закончился — уведомить (окно Obsidian могло быть свёрнуто). */
  doneNotify(label, r, sec) {
    if (r.cancelled) return;
    if (sec < Math.max(0, this.data.notifyMinutes) * 60) return;
    let body;
    if (r.webchat) body = "\u0416\u0434\u0451\u0442 \u043E\u0442\u0432\u0435\u0442\u0430 \u0438\u0437 \u0432\u0435\u0431-\u0447\u0430\u0442\u0430 \u2014 \u0438\u043D\u0441\u0442\u0440\u0443\u043A\u0446\u0438\u044F \u0432 \u043F\u0430\u043D\u0435\u043B\u0438.";
    else if (r.budget_stop) body = "\u041E\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u043E: \u0438\u0441\u0447\u0435\u0440\u043F\u0430\u043D \u0431\u044E\u0434\u0436\u0435\u0442.";
    else if (r.stopped) body = "\u041E\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u043E. \u0412\u0441\u0451 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u043D\u043D\u043E\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u043E.";
    else if (!r.ok) body = `\u041E\u0448\u0438\u0431\u043A\u0430: ${r.error || "\u0441\u043C. \u043F\u0430\u043D\u0435\u043B\u044C"}`;
    else {
      const sl = statsLine(r.stats);
      body = `${r.title || "\u0413\u043E\u0442\u043E\u0432\u043E"} \u0437\u0430 ${durationText(sec)}` + (sl ? `: ${sl}` : "") + (r.run_usage?.cost ? ` \xB7 ${money(r.run_usage.cost)}` : "") + ".";
      if (r.questions) body += ` \u0412\u043E\u043F\u0440\u043E\u0441\u043E\u0432: ${r.questions}.`;
    }
    this.osNotify(`\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433 \xB7 ${label}`, body, "done");
  }
  // ---------- состояние ----------
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
      console.warn("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433: \u043D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043F\u0440\u043E\u0447\u0438\u0442\u0430\u0442\u044C .system/ui.json", e);
    }
  }
  /** Попросить программу пересчитать снимок состояния (без обращений к модели). */
  async refreshState(force = false) {
    const r = await this.engine.snapshot();
    this.snapshotError = r.ok ? null : r.error || "\u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043D\u0435 \u043E\u0442\u0432\u0435\u0442\u0438\u043B\u0430";
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
      el.setText("\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433: \u043D\u0435\u0442 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B");
      el.setAttr("title", prob);
    } else if (job) {
      const manual = manualMode(this.ui);
      const t = job.startedAt && !manual ? duration(Date.now() - job.startedAt) : "";
      const q = this.engine.pending().length;
      const info = liveInfo(job);
      const parts = [`\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433 \xB7 ${job.label}`];
      const s0 = job.live.stages[0];
      if (s0) parts.push(s0.unit === "%" ? `${s0.n}%` : s0.total > 0 ? `${s0.n} \u0438\u0437 ${s0.total}` : s0.stage);
      if (job.live.ask) parts.push("\u0436\u0434\u0451\u0442 \u0432\u0430\u0448\u0435\u0433\u043E \u043E\u0442\u0432\u0435\u0442\u0430");
      else if (info.wait !== null && info.wait >= 3e3) parts.push(`\u0436\u0434\u0451\u043C \u043E\u0442\u0432\u0435\u0442\u0430 ${duration(info.wait)}`);
      else if (info.eta && !manual) parts.push(info.eta);
      if (t) parts.push(t);
      el.setText(parts.join(" \xB7 ") + (q ? ` (+${q})` : ""));
      el.setAttr("title", [info.stage, info.sub, job.lastLine].filter(Boolean).join("\n") || job.label);
    } else {
      const n = this.ui?.status.questions || 0;
      el.setText(n ? `\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433 \xB7 ${nQuestions(n)}` : "\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433");
      el.setAttr("title", "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u043F\u0430\u043D\u0435\u043B\u044C \xAB\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433\xBB");
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
  /** Открыть настройки плагина (tab — вкладка: main, models, thresholds, input, docs, costs, advanced). */
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
  // ---------- запуски ----------
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
    if (r.webchat) new import_obsidian6.Notice(`${label}: \u0436\u0434\u0451\u0442 \u043E\u0442\u0432\u0435\u0442\u0430 \u0438\u0437 \u0432\u0435\u0431-\u0447\u0430\u0442\u0430 \u2014 \u0438\u043D\u0441\u0442\u0440\u0443\u043A\u0446\u0438\u044F \u0432 \u043F\u0430\u043D\u0435\u043B\u0438 \xAB\u0412\u0442\u043E\u0440\u043E\u0439 \u043C\u043E\u0437\u0433\xBB.`, 1e4);
    else if (r.cancelled) new import_obsidian6.Notice(`${label}: \u043E\u0442\u043C\u0435\u043D\u0435\u043D\u043E \u2014 \u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u0438\u0437\u043C\u0435\u043D\u0435\u043D\u043E.`, 6e3);
    else if (r.budget_stop) {
      const why = (r.notices || []).find((n) => n.startsWith("\u041E\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u043E")) || "\u041E\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u043E: \u0438\u0441\u0447\u0435\u0440\u043F\u0430\u043D \u0431\u044E\u0434\u0436\u0435\u0442. \u0412\u0441\u0451 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u043D\u043D\u043E\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u043E.";
      new import_obsidian6.Notice(`${label}: ${lcFirst(why)}`, 2e4);
    } else if (r.ok) {
      const sl = statsLine(r.stats);
      let msg = `${label}: ${lcFirst(r.title || "\u0433\u043E\u0442\u043E\u0432\u043E")}${sl ? " \u2014 " + sl : ""}.`;
      const u = r.run_usage;
      if (u && u.calls) msg += ` \u041E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439: ${u.calls}${u.cost ? `, ${money(u.cost)}` : ""}${r.elapsed ? `, ${durationText(r.elapsed)}` : ""}.`;
      if (r.questions) msg += ` \u041E\u0442\u043A\u0440\u044B\u0442\u044B\u0445 \u0432\u043E\u043F\u0440\u043E\u0441\u043E\u0432: ${r.questions}.`;
      if (r.warnings?.length) msg += ` \u041F\u0440\u0435\u0434\u0443\u043F\u0440\u0435\u0436\u0434\u0435\u043D\u0438\u0439: ${r.warnings.length} \u2014 \u0441\u043C. \u043F\u0430\u043D\u0435\u043B\u044C.`;
      new import_obsidian6.Notice(msg, 8e3);
    } else if (r.stopped) new import_obsidian6.Notice(`${label}: \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u043E. \u0412\u0441\u0451 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u043D\u043D\u043E\u0435 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u043E \u2014 \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0438\u0439 \u0437\u0430\u043F\u0443\u0441\u043A \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442.`, 8e3);
    else new import_obsidian6.Notice(`${label}: ${r.error || "\u043E\u0448\u0438\u0431\u043A\u0430"}`, 15e3);
  }
  runPhase1() {
    return this.job(["run"], "\u0424\u0430\u0437\u0430 1");
  }
  async runSynth(c, force = false) {
    const label = `\u0424\u0430\u0437\u0430 2 \xB7 ${c.title}`;
    const r = await this.job(["synth", c.id, ...force ? ["--force"] : []], label, false);
    if (r.ok && r.unchanged && !force) {
      const ok = await this.confirm({
        title: "\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B \u0430\u043A\u0442\u0443\u0430\u043B\u044C\u043D\u044B",
        text: `\u0421 \u043F\u0440\u043E\u0448\u043B\u043E\u0439 \u0437\u0430\u043F\u0438\u0441\u0438 \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u043E\u0432 \xAB${c.title}\xBB \u0432 \u0431\u0430\u0437\u0435 \u0441\u0438\u043D\u0442\u0435\u0437\u0430 \u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u0438\u0437\u043C\u0435\u043D\u0438\u043B\u043E\u0441\u044C.

\u041F\u0435\u0440\u0435\u043F\u0438\u0441\u0430\u0442\u044C \u0438\u0445 \u0432\u0441\u0451 \u0440\u0430\u0432\u043D\u043E? \u042D\u0442\u043E \u043F\u043E\u0442\u0440\u0430\u0442\u0438\u0442 \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F \u043A \u043C\u043E\u0434\u0435\u043B\u0438.`,
        ok: "\u041F\u0435\u0440\u0435\u043F\u0438\u0441\u0430\u0442\u044C"
      });
      return ok ? this.runSynth(c, true) : r;
    }
    this.notify(label, r);
    return r;
  }
  /** Ревалидация: программа сама посчитает записи и спросит подтверждение (с оценкой времени и стоимости). */
  async runRevalidate(c) {
    const r = await this.job(["revalidate", ...c ? [c.id] : []], c ? `\u0420\u0435\u0432\u0430\u043B\u0438\u0434\u0430\u0446\u0438\u044F \xB7 ${c.title}` : "\u0420\u0435\u0432\u0430\u043B\u0438\u0434\u0430\u0446\u0438\u044F \u0432\u0441\u0435\u0445 \u0437\u0430\u043F\u0438\u0441\u0435\u0439", false);
    if (r.ok && !r.cancelled && !r.count) new import_obsidian6.Notice(c ? `\u0412 \xAB${c.title}\xBB \u043D\u0435\u0442 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u043D\u043D\u044B\u0445 \u0437\u0430\u043F\u0438\u0441\u0435\u0439 \u0434\u043B\u044F \u043F\u0435\u0440\u0435\u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0438.` : "\u041D\u0435\u0442 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u043D\u043D\u044B\u0445 \u0437\u0430\u043F\u0438\u0441\u0435\u0439 \u0434\u043B\u044F \u043F\u0435\u0440\u0435\u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0438.");
    else this.notify(c ? `\u0420\u0435\u0432\u0430\u043B\u0438\u0434\u0430\u0446\u0438\u044F \xB7 ${c.title}` : "\u0420\u0435\u0432\u0430\u043B\u0438\u0434\u0430\u0446\u0438\u044F", r);
  }
  /** Правка настроек программы из панели (цены, бюджет): программа проверит и перепишет settings.yaml. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async patchSettings(patch) {
    const r = await this.engine.run(["settings", "--set-json", "-"], { label: "\u0421\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u0438\u0435 \u043D\u0430\u0441\u0442\u0440\u043E\u0435\u043A", stdin: JSON.stringify(patch), exclusive: false, quiet: true });
    if (r.ok) await this.refreshState(true);
    return r;
  }
  /** Пересчитать стоимость прошлых обращений профиля по текущим ценам (журнал расходов меняется — в общей очереди). */
  async reprice(key) {
    const r = await this.engine.run(["usage", "--reprice", key], { label: "\u041F\u0435\u0440\u0435\u0441\u0447\u0451\u0442 \u0441\u0442\u043E\u0438\u043C\u043E\u0441\u0442\u0438" });
    await this.refreshState(true);
    return r;
  }
  async runPatterns() {
    const ok = await this.confirm({
      title: "\u041F\u043E\u0438\u0441\u043A \u043F\u0430\u0442\u0442\u0435\u0440\u043D\u043E\u0432",
      text: "\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u043F\u043E\u0438\u0449\u0435\u0442 \u0432 \u043A\u0430\u0436\u0434\u043E\u043C \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0435 \u0433\u0440\u0443\u043F\u043F\u044B \u0431\u043B\u0438\u0437\u043A\u0438\u0445 \u0430\u0441\u043F\u0435\u043A\u0442\u043E\u0432 \u0440\u0430\u0437\u043D\u044B\u0445 \u0442\u0438\u043F\u043E\u0432, \u043A\u043E\u0442\u043E\u0440\u044B\u0435 \u043D\u0435 \u043F\u043E\u043A\u0440\u044B\u0432\u0430\u0435\u0442 \u043D\u0438 \u043E\u0434\u0438\u043D \u0441\u043E\u0441\u0442\u0430\u0432\u043D\u043E\u0439 \u0442\u0438\u043F, \u0438 \u043F\u0440\u0435\u0434\u043B\u043E\u0436\u0438\u0442 \u043D\u043E\u0432\u044B\u0435 \u0442\u0438\u043F\u044B. \u041E\u0434\u043D\u043E \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0435 \u043A \u043C\u043E\u0434\u0435\u043B\u0438 \u043D\u0430 \u0432\u0441\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u043D\u044B\u0435 \u0433\u0440\u0443\u043F\u043F\u044B; \u0435\u0441\u043B\u0438 \u0433\u0440\u0443\u043F\u043F \u043D\u0435\u0442 \u2014 \u0431\u0435\u0437 \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u0439.",
      ok: "\u0418\u0441\u043A\u0430\u0442\u044C"
    });
    if (ok) await this.job(["patterns"], "\u041F\u0430\u0442\u0442\u0435\u0440\u043D\u044B");
  }
  runCheck() {
    new CheckModal(this).open();
  }
  // ---------- своя модель эмбеддингов (llama.cpp) ----------
  /** Скачана ли модель, какие сборки llama.cpp есть, работает ли сервер; hw — ещё и оборудование компьютера. */
  async llamaStatus(hw = false) {
    if (this.engine.problem()) return null;
    const r = await this.engine.run(["llama", "status", ...hw ? ["--hw"] : []], { label: "\u041C\u043E\u0434\u0435\u043B\u044C \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u043E\u0432", exclusive: false, quiet: true });
    return r.ok && r.llama ? r.llama : null;
  }
  /** Запустить модель с параметрами из окна «Запустить модель…»: что нужно — скачается (ход — в панели, «Стоп» —
   *  прервать: скачанное продолжится в следующий раз), адрес сервера программа впишет в настройки сама. */
  async runLlamaStart(params) {
    const label = "\u0417\u0430\u043F\u0443\u0441\u043A \u043C\u043E\u0434\u0435\u043B\u0438 \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u043E\u0432";
    const t0 = Date.now();
    const r = await this.engine.run(["llama", "start", "--params-json", "-"], { label, stdin: JSON.stringify(params) });
    this.doneNotify(label, r, (Date.now() - t0) / 1e3);
    const s = r.server;
    if (r.ok && s) {
      if (s.already) new import_obsidian6.Notice(`\u041C\u043E\u0434\u0435\u043B\u044C \u0443\u0436\u0435 \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 \u0441 \u044D\u0442\u0438\u043C\u0438 \u043F\u0430\u0440\u0430\u043C\u0435\u0442\u0440\u0430\u043C\u0438: ${s.url}`, 8e3);
      else if (s.foreign) new import_obsidian6.Notice(`\u041D\u0430 \u043F\u043E\u0440\u0442\u0443 ${s.port} \u0443\u0436\u0435 \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 \u0441\u0435\u0440\u0432\u0435\u0440 \u0441 \u044D\u0442\u043E\u0439 \u043C\u043E\u0434\u0435\u043B\u044C\u044E \u2014 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0431\u0443\u0434\u0435\u0442 \u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u044C\u0441\u044F \u0438\u043C.`, 1e4);
      else new import_obsidian6.Notice(`\u041C\u043E\u0434\u0435\u043B\u044C \u0437\u0430\u043F\u0443\u0449\u0435\u043D\u0430: ${s.url}${s.load_sec ? ` (\u0437\u0430\u0433\u0440\u0443\u0437\u0438\u043B\u0430\u0441\u044C \u0437\u0430 ${durationText(s.load_sec)})` : ""}. \u0410\u0434\u0440\u0435\u0441 \u0432\u043F\u0438\u0441\u0430\u043D \u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438.`, 1e4);
    } else if (r.stopped) new import_obsidian6.Notice("\u0417\u0430\u043F\u0443\u0441\u043A \u043C\u043E\u0434\u0435\u043B\u0438 \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D. \u041D\u0430\u0447\u0430\u0442\u043E\u0435 \u0441\u043A\u0430\u0447\u0438\u0432\u0430\u043D\u0438\u0435 \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u0441\u044F \u0441\u043E \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0435\u0433\u043E \u0437\u0430\u043F\u0443\u0441\u043A\u0430.", 1e4);
    else new import_obsidian6.Notice(`\u041C\u043E\u0434\u0435\u043B\u044C \u043D\u0435 \u0437\u0430\u043F\u0443\u0449\u0435\u043D\u0430: ${r.error || "\u043E\u0448\u0438\u0431\u043A\u0430"}`, 2e4);
    await this.refreshState(true);
    this.brainTab.reload();
    return r;
  }
  /** Остановить сервер модели (освободить память). Программа запустит его снова сама, когда он понадобится. */
  async runLlamaStop() {
    const r = await this.engine.run(["llama", "stop"], { label: "\u041E\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0430 \u043C\u043E\u0434\u0435\u043B\u0438 \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u043E\u0432", exclusive: false, quiet: true });
    if (!r.ok) new import_obsidian6.Notice(`\u041C\u043E\u0434\u0435\u043B\u044C \u043D\u0435 \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u0430: ${r.error || "\u043E\u0448\u0438\u0431\u043A\u0430"}`, 12e3);
    else new import_obsidian6.Notice(r.title === "\u0421\u0435\u0440\u0432\u0435\u0440 \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D" ? "\u041C\u043E\u0434\u0435\u043B\u044C \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u043E\u0432 \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u0430 \u2014 \u043F\u0430\u043C\u044F\u0442\u044C \u043E\u0441\u0432\u043E\u0431\u043E\u0436\u0434\u0435\u043D\u0430." : "\u041C\u043E\u0434\u0435\u043B\u044C \u044D\u043C\u0431\u0435\u0434\u0434\u0438\u043D\u0433\u043E\u0432 \u0438 \u0442\u0430\u043A \u043D\u0435 \u0437\u0430\u043F\u0443\u0449\u0435\u043D\u0430.", 8e3);
    return r;
  }
  continueWebchat() {
    const w = this.lastWebchat;
    return w ? this.job(w.args, w.label) : this.runPhase1();
  }
  answer(q, option, text) {
    const args = ["answer", q.id, option !== null ? `--option=${option}` : `--text=${text || ""}`];
    return this.job(args, `\u041E\u0442\u0432\u0435\u0442 \u043D\u0430 ${q.id}`, false);
  }
  async approveStructure() {
    const draft = this.ui?.status.draft || "_\u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u0430 (\u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A).md";
    const ok = await this.confirm({
      title: "\u0423\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044C \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u0443?",
      text: "\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0441\u043E\u0437\u0434\u0430\u0441\u0442 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u044B \u043F\u043E \u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A\u0443 (\u0441 \u0432\u0430\u0448\u0438\u043C\u0438 \u043F\u0440\u0430\u0432\u043A\u0430\u043C\u0438) \u0438 \u0440\u0430\u0437\u043B\u043E\u0436\u0438\u0442 \u043F\u043E \u043D\u0438\u043C \u0437\u0430\u043F\u0438\u0441\u0438. \u042D\u0442\u043E \u043E\u0431\u0440\u0430\u0449\u0435\u043D\u0438\u044F \u043A \u043C\u043E\u0434\u0435\u043B\u0438 \u2014 \u043F\u043E \u0437\u0430\u043F\u0438\u0441\u0438 \u043D\u0430 \u043A\u0430\u0436\u0434\u0443\u044E.",
      ok: "\u0423\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044C \u0438 \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u044C"
    });
    if (!ok) return;
    for (const leaf of this.app.workspace.getLeavesOfType("markdown")) {
      const v = leaf.view;
      if (v instanceof import_obsidian6.MarkdownView && v.file?.path === draft) await v.save();
    }
    const r = await this.engine.local("\u0423\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0438\u0435 \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u044B", async () => {
      const f = this.app.vault.getAbstractFileByPath(draft);
      if (!(f instanceof import_obsidian6.TFile)) throw new Error(`\u043D\u0435\u0442 \u0444\u0430\u0439\u043B\u0430 \u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A\u0430 \xAB${draft}\xBB`);
      await this.app.vault.process(f, (text) => markApproved(text));
    });
    if (!r.ok) {
      new import_obsidian6.Notice(`\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u043C\u0435\u0442\u0438\u0442\u044C \u0447\u0435\u0440\u043D\u043E\u0432\u0438\u043A: ${r.error}`, 1e4);
      return;
    }
    new import_obsidian6.Notice("\u0421\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u0430 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0430 \u2014 \u0441\u043E\u0437\u0434\u0430\u044E \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u044B \u0438 \u0440\u0430\u0441\u043A\u043B\u0430\u0434\u044B\u0432\u0430\u044E \u0437\u0430\u043F\u0438\u0441\u0438\u2026");
    await this.runPhase1();
  }
  // ---------- совет ИИ ----------
  openAdvice(c, ready) {
    new AdviceModal(this, c, ready).open();
  }
  async adviseNow(c) {
    const label = `\u0421\u043E\u0432\u0435\u0442 \u043F\u043E \u043F\u043E\u0440\u043E\u0433\u0430\u043C \xB7 ${c.title}`;
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
  // ---------- правки YAML контейнера (в общей очереди, не во время прогона) ----------
  async editFrontmatter(c, label, fn) {
    if (this.engine.busy()) new import_obsidian6.Notice("\u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0440\u0430\u0431\u043E\u0442\u0430\u0435\u0442 \u2014 \u0438\u0437\u043C\u0435\u043D\u0435\u043D\u0438\u0435 \u0437\u0430\u043F\u0438\u0448\u0435\u0442\u0441\u044F \u0441\u0440\u0430\u0437\u0443 \u043F\u043E\u0441\u043B\u0435 \u0442\u0435\u043A\u0443\u0449\u0435\u0433\u043E \u0437\u0430\u043F\u0443\u0441\u043A\u0430.");
    const r = await this.engine.local(label, async () => {
      const f = this.app.vault.getAbstractFileByPath(c.path);
      if (!(f instanceof import_obsidian6.TFile)) throw new Error(`\u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D \u0444\u0430\u0439\u043B \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430 \xAB${c.path}\xBB`);
      await this.app.fileManager.processFrontMatter(f, fn);
    });
    if (!r.ok) {
      new import_obsidian6.Notice(`\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0441\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C: ${r.error}`, 1e4);
      return false;
    }
    this.refreshState(true);
    return true;
  }
  saveThresholds(c, changes) {
    const aliases = this.ui?.threshold_aliases || {};
    return this.editFrontmatter(c, `\u041F\u043E\u0440\u043E\u0433\u0438 \xB7 ${c.title}`, (fm) => {
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
    return this.editFrontmatter(c, `\u0421\u0442\u0438\u043B\u044C \xB7 ${c.title}`, (fm) => {
      if (text) fm.style = text;
      else delete fm.style;
    });
  }
  async setContainerField(c, key, value, what) {
    const ok = await this.editFrontmatter(c, `${c.title}: ${what}`, (fm) => {
      fm[key] = value;
    });
    if (ok) new import_obsidian6.Notice(`\xAB${c.title}\xBB \u2014 ${what}. \u041F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0430 \u0443\u0447\u0442\u0451\u0442 \u044D\u0442\u043E \u043F\u0440\u0438 \u0441\u043B\u0435\u0434\u0443\u044E\u0449\u0435\u0439 \u0424\u0430\u0437\u0435 1.`);
  }
  // ---------- новая мысль ----------
  newThought(hint = "") {
    new NewThoughtModal(this, hint).open();
  }
  async saveThought(text, hint, dateIso, source) {
    const { name, body } = thoughtFile(text, hint, dateIso);
    const folder = source && source !== "\u0437\u0430\u043C\u0435\u0442\u043A\u0430" ? `_staging/${source}` : "_staging";
    const a = this.app.vault.adapter;
    if (!await a.exists(folder)) await a.mkdir(folder);
    let p = `${folder}/${name}`;
    for (let i = 2; await a.exists(p); i++) p = `${folder}/${name.replace(/\.txt$/, ` (${i}).txt`)}`;
    await a.write(p, body);
    this.refreshState();
    return p;
  }
  // ---------- файлы и папки ----------
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
      new import_obsidian6.Notice(`\u0424\u0430\u0439\u043B \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D: ${rel}`);
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
      new import_obsidian6.Notice(`\u041E\u0442\u043A\u0440\u043E\u0439\u0442\u0435 \u0432\u0440\u0443\u0447\u043D\u0443\u044E: ${abs}`, 1e4);
    }
  }
  pickContainer(cb, allLabel) {
    if (!this.ui?.containers.length) {
      new import_obsidian6.Notice("\u041A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u043E\u0432 \u043F\u043E\u043A\u0430 \u043D\u0435\u0442 \u2014 \u0441\u043D\u0430\u0447\u0430\u043B\u0430 \u0443\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u0443.");
      return;
    }
    new ContainerPicker(this, allLabel || null, cb).open();
  }
  containerOfActive() {
    const f = this.app.workspace.getActiveFile();
    return f ? containerOfPath(this.ui, f.path) : null;
  }
  // ---------- команды ----------
  addCommands() {
    this.addCommand({ id: "open-panel", name: "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u043F\u0430\u043D\u0435\u043B\u044C", callback: () => this.openView() });
    this.addCommand({ id: "run", name: "\u0424\u0430\u0437\u0430 1: \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u0430\u0442\u044C \u043D\u043E\u0432\u043E\u0435", callback: () => this.runPhase1() });
    this.addCommand({ id: "new-thought", name: "\u041D\u043E\u0432\u0430\u044F \u043C\u044B\u0441\u043B\u044C", callback: () => this.newThought() });
    this.addCommand({ id: "questions", name: "\u041E\u0442\u0432\u0435\u0442\u0438\u0442\u044C \u043D\u0430 \u0432\u043E\u043F\u0440\u043E\u0441\u044B", callback: () => this.openView("questions") });
    this.addCommand({ id: "synth", name: "\u0424\u0430\u0437\u0430 2: \u043D\u0430\u043F\u0438\u0441\u0430\u0442\u044C \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B\u2026", callback: () => this.pickContainer((c) => c && this.runSynth(c)) });
    this.addCommand({
      id: "synth-current",
      name: "\u0424\u0430\u0437\u0430 2 \u0434\u043B\u044F \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430 \u043E\u0442\u043A\u0440\u044B\u0442\u043E\u0439 \u0437\u0430\u043C\u0435\u0442\u043A\u0438",
      checkCallback: (checking) => {
        const c = this.containerOfActive();
        if (!c) return false;
        if (!checking) this.runSynth(c);
        return true;
      }
    });
    this.addCommand({
      id: "container-current",
      name: "\u041F\u043E\u043A\u0430\u0437\u0430\u0442\u044C \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440 \u043E\u0442\u043A\u0440\u044B\u0442\u043E\u0439 \u0437\u0430\u043C\u0435\u0442\u043A\u0438",
      checkCallback: (checking) => {
        const c = this.containerOfActive();
        if (!c) return false;
        if (!checking) this.openView("container", c.id);
        return true;
      }
    });
    this.addCommand({ id: "advise", name: "\u0421\u043E\u0432\u0435\u0442 \u0418\u0418 \u043F\u043E \u043F\u043E\u0440\u043E\u0433\u0430\u043C \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0430\u2026", callback: () => this.pickContainer((c) => c && this.openAdvice(c)) });
    this.addCommand({ id: "revalidate", name: "\u0420\u0435\u0432\u0430\u043B\u0438\u0434\u0430\u0446\u0438\u044F\u2026", callback: () => this.pickContainer((c) => this.runRevalidate(c), "\u0412\u0441\u0435 \u043A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u044B") });
    this.addCommand({ id: "patterns", name: "\u041F\u0430\u0442\u0442\u0435\u0440\u043D\u044B: \u043F\u043E\u0438\u0441\u043A \u043D\u043E\u0432\u044B\u0445 \u0441\u043E\u0441\u0442\u0430\u0432\u043D\u044B\u0445 \u0442\u0438\u043F\u043E\u0432", callback: () => this.runPatterns() });
    this.addCommand({ id: "check", name: "\u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u0441\u0432\u044F\u0437\u044C \u0441 \u043C\u043E\u0434\u0435\u043B\u044C\u044E", callback: () => this.runCheck() });
    this.addCommand({ id: "usage", name: "\u0420\u0430\u0441\u0445\u043E\u0434\u044B \u043D\u0430 \u043C\u043E\u0434\u0435\u043B\u0438", callback: () => this.openView("usage") });
    this.addCommand({ id: "update", name: "\u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u044F \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u044B", callback: () => this.checkUpdates(true) });
    this.addCommand({ id: "refresh", name: "\u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C \u0441\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u0435", callback: () => this.refreshState(true) });
    this.addCommand({ id: "report", name: "\u041E\u0442\u0447\u0451\u0442 \u0434\u043B\u044F \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u0447\u0438\u043A\u0430", callback: () => saveDeveloperReport(this) });
    this.addCommand({
      id: "stop",
      name: "\u0421\u0442\u043E\u043F",
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
  if (new RegExp(`^\\s*[-*]\\s*\\[[xX\u0445\u0425\u2713vV]\\]\\s*${APPROVE}`, "m").test(text)) return text;
  const fm = /^---\r?\n[\s\S]*?\r?\n---\r?\n/.exec(text);
  const at = fm ? fm[0].length : 0;
  return text.slice(0, at) + `- [x] ${APPROVE}

` + text.slice(at);
}

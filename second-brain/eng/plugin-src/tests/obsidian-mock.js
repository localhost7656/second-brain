// Imitation API Obsidian plugin-checker «Second Brain» browser-wise.
// Storage files and program launch go through functions, plug-in run_e2e.py (window.__fsOp, __spawnStart…).
(function () {
  "use strict";
  const INIT = window.__init;
  window.__notices = [];
  window.__calls = [];
  window.__errors = [];

  // ---------- expansion DOM, like Obsidian ----------
  function applyOpts(el, o) {
    if (o == null) return;
    if (typeof o === "string") o = { cls: o };
    if (o.cls) (Array.isArray(o.cls) ? o.cls : String(o.cls).split(/\s+/)).filter(Boolean).forEach((c) => el.classList.add(c));
    if (o.text != null) {
      if (o.text instanceof Node) el.appendChild(o.text);
      else el.textContent = String(o.text);
    }
    if (o.attr) for (const [k, v] of Object.entries(o.attr)) if (v !== null && v !== undefined && v !== false) el.setAttribute(k, String(v));
    if (o.title) el.title = o.title;
    if (o.type) el.type = o.type;
    if (o.value !== undefined) el.value = o.value;
    if (o.placeholder) el.placeholder = o.placeholder;
    if (o.href) el.href = o.href;
  }
  Node.prototype.createEl = function (tag, o, cb) {
    const el = document.createElement(tag);
    applyOpts(el, o);
    if (o && typeof o === "object" && o.prepend) this.insertBefore(el, this.firstChild);
    else this.appendChild(el);
    if (cb) cb(el);
    return el;
  };
  Node.prototype.createDiv = function (o, cb) { return this.createEl("div", o, cb); };
  Node.prototype.createSpan = function (o, cb) { return this.createEl("span", o, cb); };
  Node.prototype.empty = function () { while (this.firstChild) this.removeChild(this.firstChild); };
  Node.prototype.detach = function () { if (this.parentNode) this.parentNode.removeChild(this); };
  Node.prototype.setText = function (t) {
    if (t instanceof Node) { this.empty(); this.appendChild(t); } else this.textContent = t == null ? "" : String(t);
  };
  Node.prototype.appendText = function (t) { this.appendChild(document.createTextNode(String(t))); };
  Element.prototype.addClass = function (...c) { c.flat().forEach((x) => String(x).split(/\s+/).filter(Boolean).forEach((y) => this.classList.add(y))); };
  Element.prototype.addClasses = function (c) { this.addClass(...c); };
  Element.prototype.removeClass = function (...c) { c.flat().forEach((x) => this.classList.remove(x)); };
  Element.prototype.toggleClass = function (c, v) { (Array.isArray(c) ? c : [c]).forEach((x) => this.classList.toggle(x, !!v)); };
  Element.prototype.hasClass = function (c) { return this.classList.contains(c); };
  Element.prototype.setAttr = function (k, v) { if (v === null || v === undefined) this.removeAttribute(k); else this.setAttribute(k, String(v)); };
  Element.prototype.getText = function () { return this.textContent; };
  window.createEl = (tag, o, cb) => { const el = document.createElement(tag); applyOpts(el, o); if (cb) cb(el); return el; };
  window.createDiv = (o, cb) => window.createEl("div", o, cb);
  window.createSpan = (o, cb) => window.createEl("span", o, cb);
  window.createFragment = (cb) => { const f = document.createDocumentFragment(); if (cb) cb(f); return f; };

  // ---------- pin (simplified Lucide) ----------
  const ICONS = {
    brain: '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/><path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/><path d="M17.6 6.5a3 3 0 0 0 .4-1.4"/><path d="M6 5.1a3 3 0 0 0 .4 1.4"/>',
    "refresh-cw": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    "trash-2": '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
    "file-text": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  };
  function setIcon(el, name) {
    el.empty();
    const body = ICONS[name] || '<circle cx="12" cy="12" r="8"/>';
    el.insertAdjacentHTML("beforeend", `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="svg-icon lucide-${name}">${body}</svg>`);
  }

  // ---------- bridge Python ----------
  async function fsOp(op, path, extra) {
    const r = JSON.parse(await window.__fsOp(JSON.stringify(Object.assign({ op, path }, extra || {}))));
    if (r && r.error) throw new Error(r.error);
    return r ? r.value : null;
  }

  // ---------- events ----------
  class Events {
    constructor() { this._h = {}; }
    on(name, cb, ctx) { (this._h[name] = this._h[name] || []).push(cb); return { e: this, name, cb, off: () => this.offref({ name, cb }) }; }
    off(name, cb) { this._h[name] = (this._h[name] || []).filter((x) => x !== cb); }
    offref(ref) { this.off(ref.name, ref.cb); }
    trigger(name, ...a) { for (const cb of this._h[name] || []) { try { cb(...a); } catch (e) { console.error(e); } } }
  }

  class Component {
    constructor() { this._cleanup = []; this._loaded = false; }
    load() { this._loaded = true; this.onload(); }
    onload() {}
    unload() { for (const f of this._cleanup.splice(0)) { try { f(); } catch (e) { console.error(e); } } this.onunload(); }
    onunload() {}
    register(cb) { this._cleanup.push(cb); }
    registerEvent(ref) { this._cleanup.push(() => ref && ref.off && ref.off()); }
    registerDomEvent(el, type, cb, opts) { el.addEventListener(type, cb, opts); this._cleanup.push(() => el.removeEventListener(type, cb, opts)); }
    registerInterval(id) { this._cleanup.push(() => window.clearInterval(id)); return id; }
    addChild(c) { return c; }
    removeChild(c) { return c; }
  }

  // ---------- file ----------
  class TAbstractFile {
    constructor(path) {
      this.path = path;
      this.name = path.split("/").pop();
      this.vault = app.vault;
      const i = path.lastIndexOf("/");
      this.parent = null;
      this._parentPath = i > 0 ? path.slice(0, i) : "";
    }
  }
  class TFile extends TAbstractFile {
    constructor(path) {
      super(path);
      const i = this.name.lastIndexOf(".");
      this.basename = i > 0 ? this.name.slice(0, i) : this.name;
      this.extension = i > 0 ? this.name.slice(i + 1) : "";
      this.stat = { mtime: 0, ctime: 0, size: 0 };
    }
  }
  class TFolder extends TAbstractFile {
    constructor(path) { super(path); this.children = []; }
    isRoot() { return this.path === "/"; }
  }

  const norm = (p) => String(p || "").replace(/\\/g, "/").replace(/\/+/g, "/").replace(/^\.\//, "").replace(/^\/|\/$/g, "");

  class DataAdapter {}
  class FileSystemAdapter extends DataAdapter {
    constructor(base) { super(); this.basePath = base; }
    getBasePath() { return this.basePath; }
    getName() { return this.basePath.split("/").pop(); }
    getFullPath(p) { return this.basePath + "/" + norm(p); }
    async stat(p) { return fsOp("stat", norm(p)); }
    async read(p) { return fsOp("read", norm(p)); }
    async write(p, data) { await fsOp("write", norm(p), { data }); await refreshIndex(); }
    async append(p, data) { await fsOp("append", norm(p), { data }); }
    async exists(p) { return fsOp("exists", norm(p)); }
    async mkdir(p) { await fsOp("mkdir", norm(p)); await refreshIndex(); }
    async list(p) { return fsOp("list", norm(p)); }
    async remove(p) { await fsOp("remove", norm(p)); await refreshIndex(); }
  }

  const index = { files: new Set(), folders: new Set() };
  async function refreshIndex() {
    const r = await fsOp("index", "");
    index.files = new Set(r.files);
    index.folders = new Set(r.folders);
  }
  window.__refreshIndex = refreshIndex;

  const vault = new Events();
  Object.assign(vault, {
    adapter: new FileSystemAdapter(INIT.vaultBase),
    configDir: ".obsidian",
    getName() { return this.adapter.getName(); },
    getAbstractFileByPath(p) {
      p = norm(p);
      if (index.files.has(p)) return new TFile(p);
      if (index.folders.has(p)) return new TFolder(p);
      return null;
    },
    getFileByPath(p) { const f = this.getAbstractFileByPath(p); return f instanceof TFile ? f : null; },
    getFiles() { return [...index.files].map((p) => new TFile(p)); },
    getMarkdownFiles() { return this.getFiles().filter((f) => f.extension === "md"); },
    async read(f) { return this.adapter.read(f.path); },
    async cachedRead(f) { return this.adapter.read(f.path); },
    async modify(f, data) { await this.adapter.write(f.path, data); },
    async create(p, data) { await this.adapter.write(p, data); return new TFile(norm(p)); },
    async createFolder(p) { await this.adapter.mkdir(p); return new TFolder(norm(p)); },
    async process(f, fn) {
      const text = await this.adapter.read(f.path);
      const out = fn(text);
      await this.adapter.write(f.path, out);
      window.__calls.push(["vault.process", f.path]);
      return out;
    },
  });

  const fileManager = {
    async processFrontMatter(f, fn) {
      const fm = await fsOp("fm_read", f.path);
      fn(fm);
      await fsOp("fm_write", f.path, { fm });
      window.__calls.push(["processFrontMatter", f.path, JSON.parse(JSON.stringify(fm))]);
    },
  };

  // ---------- window-hole ----------
  const modalStack = [];
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modalStack.length) {
      e.preventDefault();
      modalStack[modalStack.length - 1].close();
    }
  });
  class Modal extends Component {
    constructor(appArg) {
      super();
      this.app = appArg;
      this.containerEl = createDiv("modal-container mod-dim");
      this.bgEl = this.containerEl.createDiv("modal-bg");
      this.modalEl = this.containerEl.createDiv("modal");
      this.closeButtonEl = this.modalEl.createDiv("modal-close-button");
      this.titleEl = this.modalEl.createDiv("modal-title");
      this.contentEl = this.modalEl.createDiv("modal-content");
      this.scope = { register() {} };
      this.shouldRestoreSelection = false;
      this.bgEl.addEventListener("click", () => this.close());
      this.closeButtonEl.addEventListener("click", () => this.close());
    }
    setTitle(t) { this.titleEl.setText(t); return this; }
    setContent(c) { this.contentEl.setText(c); return this; }
    open() {
      document.body.appendChild(this.containerEl);
      modalStack.push(this);
      try { const r = this.onOpen(); if (r && r.catch) r.catch((e) => reportError(e)); } catch (e) { reportError(e); }
    }
    close() {
      if (!this.containerEl.parentNode) return;
      this.containerEl.detach();
      const i = modalStack.indexOf(this);
      if (i >= 0) modalStack.splice(i, 1);
      try { this.onClose(); } catch (e) { reportError(e); }
    }
    onOpen() {}
    onClose() {}
  }

  class SuggestModal extends Modal {
    constructor(appArg) {
      super(appArg);
      this.modalEl.addClass("prompt");
      this.titleEl.detach();
      this.contentEl.detach();
      this.inputEl = this.modalEl.createEl("input", { cls: "prompt-input", type: "text" });
      this.resultContainerEl = this.modalEl.createDiv("prompt-results");
      this.limit = 50;
      this.emptyStateText = "Nothing found..";
      this._sel = 0;
      this.inputEl.addEventListener("input", () => { this._sel = 0; this._render(); });
      this.inputEl.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown") { this._sel++; this._render(); e.preventDefault(); }
        if (e.key === "ArrowUp") { this._sel = Math.max(0, this._sel - 1); this._render(); e.preventDefault(); }
        if (e.key === "Enter") { const it = this._items[this._sel]; if (it !== undefined) this._choose(it, e); e.preventDefault(); }
      });
    }
    setPlaceholder(p) { this.inputEl.placeholder = p; }
    setInstructions() {}
    open() { super.open(); this._render(); window.setTimeout(() => this.inputEl.focus(), 0); }
    _choose(it, e) { this.close(); this.selectSuggestion ? this.selectSuggestion(it, e) : this.onChooseSuggestion(it, e); }
    _render() {
      this._items = this.getSuggestions(this.inputEl.value);
      this.resultContainerEl.empty();
      if (!this._items.length) this.resultContainerEl.createDiv({ cls: "suggestion-empty", text: this.emptyStateText });
      this._items.forEach((it, i) => {
        const el = this.resultContainerEl.createDiv({ cls: "suggestion-item" + (i === this._sel ? " is-selected" : "") });
        this.renderSuggestion(it, el);
        el.addEventListener("click", (e) => this._choose(it, e));
      });
    }
  }
  class FuzzySuggestModal extends SuggestModal {
    getSuggestions(q) {
      const s = String(q || "").toLowerCase().trim();
      return this.getItems().filter((it) => !s || this.getItemText(it).toLowerCase().includes(s)).map((item) => ({ item, match: { score: 0, matches: [] } }));
    }
    renderSuggestion(m, el) { el.setText(this.getItemText(m.item)); }
    onChooseSuggestion(m, e) { this.onChooseItem(m.item, e); }
    selectSuggestion(m, e) { this.onChooseSuggestion(m, e); }
  }

  // ---------- notice ----------
  let noticeBox = null;
  class Notice {
    constructor(message, timeout) {
      if (!noticeBox) noticeBox = document.body.createDiv("notice-container");
      this.noticeEl = noticeBox.createDiv({ cls: "notice", text: String(message) });
      window.__notices.push(String(message));
      this.noticeEl.addEventListener("click", () => this.hide());
      const t = Math.min(timeout === undefined ? 4500 : timeout, INIT.noticeMax || 6000);
      if (t > 0) window.setTimeout(() => this.hide(), t);
    }
    setMessage(m) { this.noticeEl.setText(m); return this; }
    hide() { this.noticeEl.detach(); }
  }

  // ---------- Markdown (simplified) ----------
  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function inline(s) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, '<a class="internal-link" data-href="$1" href="$1">$2</a>');
    s = s.replace(/\[\[([^\]]+)\]\]/g, '<a class="internal-link" data-href="$1" href="$1">$1</a>');
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a class="external-link" href="$2">$1</a>');
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    s = s.replace(/(^|\s)_([^_\n]+)_(?=\s|$|[.,;:!?])/g, "$1<em>$2</em>");
    return s;
  }
  function mdToHtml(md) {
    const out = [];
    const blocks = String(md || "").replace(/\r/g, "").split(/\n{2,}/);
    for (const b of blocks) {
      const lines = b.split("\n");
      if (lines.every((l) => /^\s*[-*] /.test(l))) {
        out.push("<ul>" + lines.map((l) => {
          const m = /^\s*[-*] \[([ xX])\] (.*)$/.exec(l);
          if (m) return `<li class="task-list-item"><input type="checkbox" ${m[1] !== " " ? "checked" : ""} disabled> ${inline(m[2])}</li>`;
          return "<li>" + inline(l.replace(/^\s*[-*] /, "")) + "</li>";
        }).join("") + "</ul>");
      } else if (lines.every((l) => /^>/.test(l))) {
        out.push("<blockquote><p>" + lines.map((l) => inline(l.replace(/^>\s?/, ""))).join("<br>") + "</p></blockquote>");
      } else if (/^#{1,6} /.test(lines[0]) && lines.length === 1) {
        const n = /^(#+)/.exec(lines[0])[1].length;
        out.push(`<h${n}>${inline(lines[0].replace(/^#+ /, ""))}</h${n}>`);
      } else out.push("<p>" + lines.map(inline).join("<br>") + "</p>");
    }
    return out.join("\n");
  }
  const MarkdownRenderer = {
    async render(appArg, md, el) { el.insertAdjacentHTML("beforeend", mdToHtml(md)); },
    async renderMarkdown(md, el) { el.insertAdjacentHTML("beforeend", mdToHtml(md)); },
  };

  // ---------- setting: Setting component ----------
  class BaseComponent { then(cb) { cb(this); return this; } setDisabled(d) { this.disabled = d; const el = this.inputEl || this.buttonEl || this.selectEl; if (el) el.disabled = d; return this; } }
  class TextComponent extends BaseComponent {
    constructor(c, tag) {
      super();
      this.inputEl = tag === "textarea" ? c.createEl("textarea") : c.createEl("input", { type: "text", attr: { spellcheck: "false" } });
      this.inputEl.addEventListener("input", () => this._cb && this._cb(this.inputEl.value));
    }
    getValue() { return this.inputEl.value; }
    setValue(v) { this.inputEl.value = v == null ? "" : v; return this; }
    setPlaceholder(p) { this.inputEl.placeholder = p == null ? "" : p; return this; }
    onChange(cb) { this._cb = cb; return this; }
    onChanged() { if (this._cb) this._cb(this.getValue()); }
  }
  class TextAreaComponent extends TextComponent { constructor(c) { super(c, "textarea"); } }
  class DropdownComponent extends BaseComponent {
    constructor(c) { super(); this.selectEl = c.createEl("select", { cls: "dropdown" }); this.selectEl.addEventListener("change", () => this._cb && this._cb(this.selectEl.value)); }
    addOption(v, t) { this.selectEl.createEl("option", { text: t, attr: { value: v } }); return this; }
    addOptions(o) { for (const [k, v] of Object.entries(o)) this.addOption(k, v); return this; }
    getValue() { return this.selectEl.value; }
    setValue(v) { this.selectEl.value = v; return this; }
    onChange(cb) { this._cb = cb; return this; }
  }
  class ToggleComponent extends BaseComponent {
    constructor(c) {
      super();
      this.toggleEl = c.createDiv("checkbox-container");
      this.toggleEl.createEl("input", { type: "checkbox", attr: { tabindex: "0" } });
      this.value = false;
      this.toggleEl.addEventListener("click", () => { this.setValue(!this.value); if (this._cb) this._cb(this.value); });
    }
    getValue() { return this.value; }
    setValue(v) { this.value = !!v; this.toggleEl.toggleClass("is-enabled", this.value); return this; }
    setTooltip(t) { this.toggleEl.setAttribute("aria-label", t); return this; }
    onChange(cb) { this._cb = cb; return this; }
  }
  class ButtonComponent extends BaseComponent {
    constructor(c) { super(); this.buttonEl = c.createEl("button"); this.buttonEl.addEventListener("click", (e) => this._cb && this._cb(e)); }
    setButtonText(t) { this.buttonEl.setText(t); return this; }
    setCta() { this.buttonEl.addClass("mod-cta"); return this; }
    removeCta() { this.buttonEl.removeClass("mod-cta"); return this; }
    setWarning() { this.buttonEl.addClass("mod-warning"); return this; }
    setIcon(i) { setIcon(this.buttonEl, i); return this; }
    setTooltip(t) { this.buttonEl.setAttribute("aria-label", t); return this; }
    setClass(c) { this.buttonEl.addClass(c); return this; }
    onClick(cb) { this._cb = cb; return this; }
  }
  class ExtraButtonComponent extends BaseComponent {
    // like Obsidian 1.15: Inactive button does not call the handler, class is-disabled lose tabindex
    constructor(c) { super(); this.extraSettingsEl = c.createDiv("clickable-icon extra-setting-button"); this.extraSettingsEl.setAttribute("tabindex", "0"); this.extraSettingsEl.addEventListener("click", () => { if (!this.disabled && this._cb) this._cb(); }); }
    setDisabled(d) { this.disabled = d; this.extraSettingsEl.toggleClass("is-disabled", d); if (d) this.extraSettingsEl.removeAttribute("tabindex"); else this.extraSettingsEl.setAttribute("tabindex", "0"); return this; }
    setIcon(i) { setIcon(this.extraSettingsEl, i); return this; }
    setTooltip(t) { this.extraSettingsEl.setAttribute("aria-label", t); return this; }
    onClick(cb) { this._cb = cb; return this; }
  }
  class ColorComponent extends BaseComponent {
    constructor(c) { super(); this.colorPickerEl = c.createEl("input", { type: "color" }); this.colorPickerEl.addEventListener("input", () => this._cb && this._cb(this.colorPickerEl.value)); }
    getValue() { return this.colorPickerEl.value; }
    setValue(v) { this.colorPickerEl.value = v; return this; }
    onChange(cb) { this._cb = cb; return this; }
  }
  class Setting {
    constructor(containerEl) {
      this.settingEl = containerEl.createDiv("setting-item");
      this.infoEl = this.settingEl.createDiv("setting-item-info");
      this.nameEl = this.infoEl.createDiv("setting-item-name");
      this.descEl = this.infoEl.createDiv("setting-item-description");
      this.controlEl = this.settingEl.createDiv("setting-item-control");
      this.components = [];
    }
    setName(n) { this.nameEl.setText(n); return this; }
    setDesc(d) { this.descEl.setText(d); return this; }
    setClass(c) { this.settingEl.addClass(c); return this; }
    setTooltip(t) { this.nameEl.setAttribute("aria-label", t); return this; }
    setHeading() { this.settingEl.addClass("setting-item-heading"); return this; }
    setDisabled(d) { this.settingEl.toggleClass("is-disabled", d); return this; }
    _add(C, cb) { const c = new C(this.controlEl); this.components.push(c); cb(c); return this; }
    addText(cb) { return this._add(TextComponent, cb); }
    addTextArea(cb) { return this._add(TextAreaComponent, cb); }
    addDropdown(cb) { return this._add(DropdownComponent, cb); }
    addToggle(cb) { return this._add(ToggleComponent, cb); }
    addButton(cb) { return this._add(ButtonComponent, cb); }
    addExtraButton(cb) { return this._add(ExtraButtonComponent, cb); }
    addColorPicker(cb) { return this._add(ColorComponent, cb); }
    then(cb) { cb(this); return this; }
  }
  // Like in Obsidian 1.13+: tabs have their own navEl (left-hand), settingItems and renderTab();
  // settings window renderTab(), she — display(), If there are no declarative settings.
  class SettingTab {
    constructor(appArg, settingArg) {
      this.app = appArg; this.setting = settingArg; this.navEl = null; this.settingItems = []; this.renderedItems = [];
      this.containerEl = createDiv("vertical-tab-content");
    }
    getSettingDefinitions() { return []; }
    update() { this.settingItems = this.getSettingDefinitions(); }
    renderTab() {
      if (this.settingItems.length > 0) throw new Error("mock: Declarative settings are not supported");
      this.display();
    }
    display() {}
    hide() {}
  }
  class PluginSettingTab extends SettingTab {
    constructor(appArg, plugin) { super(appArg, appArg.setting); this.plugin = plugin; this.name = plugin.manifest.name; this.id = plugin.manifest.id; }
  }

  // ---------- workspace ----------
  const viewFactories = {};
  const leaves = [];
  class View extends Component {
    constructor(leaf) {
      super();
      this.leaf = leaf;
      this.app = leaf.app;
      this.containerEl = createDiv("workspace-leaf-content");
      this.headerEl = this.containerEl.createDiv("view-header");
      this.titleEl = this.headerEl.createDiv("view-header-title");
      this.contentEl = this.containerEl.createDiv("view-content");
    }
    getViewType() { return ""; }
    getDisplayText() { return ""; }
    getIcon() { return "file-text"; }
    async onOpen() {}
    async onClose() {}
  }
  class ItemView extends View {}
  class MarkdownView extends ItemView {
    getViewType() { return "markdown"; }
    async save() { window.__calls.push(["MarkdownView.save", this.file ? this.file.path : null]); }
  }
  class WorkspaceLeaf extends Events {
    constructor(appArg, host) { super(); this.app = appArg; this.host = host; this.view = null; }
    async setViewState(st) {
      const f = viewFactories[st.type];
      if (!f) throw new Error("no-no-no-no-no-no-no-no-no-no-no-no-no-no-no-no-no-no-no. " + st.type);
      if (this.view) { await this.view.onClose(); this.view.unload(); this.view.containerEl.detach(); }
      const v = f(this);
      this.view = v;
      v.containerEl.setAttribute("data-type", v.getViewType());
      v.titleEl.setText(v.getDisplayText());
      this.host.appendChild(v.containerEl);
      const tab = document.querySelector(".mod-right-split .workspace-tab-header-container");
      if (tab) {
        tab.empty();
        const h = tab.createDiv({ cls: "workspace-tab-header is-active", attr: { "aria-label": v.getDisplayText() } });
        setIcon(h.createDiv("workspace-tab-header-inner-icon"), v.getIcon());
      }
      v.load();
      await v.onOpen();
    }
    getViewState() { return { type: this.view ? this.view.getViewType() : "empty" }; }
    async openFile(f) { await openInMain(f); }
  }

  const mainLeaf = { async openFile(f) { await openInMain(f); }, view: null };
  async function openInMain(f) {
    const path = f.path;
    const el = document.querySelector(".mod-root .view-content");
    const title = document.querySelector(".mod-root .view-header-title");
    title.setText(f.basename || f.name || path);
    el.empty();
    let text = "";
    try { text = await vault.adapter.read(path); } catch (e) { text = String(e); }
    el.createEl("pre", { cls: "vm-test-file", text });
    workspace.activeFile = f instanceof TFile ? f : new TFile(path);
    if (path.endsWith(".md")) {
      if (!mainLeaf.view) { mainLeaf.app = app; mainLeaf.view = new MarkdownView(mainLeaf); leaves.push(mainLeaf); }
      mainLeaf.view.file = workspace.activeFile;
    } else if (mainLeaf.view) { mainLeaf.view.file = null; }
    window.__calls.push(["openFile", path]);
    workspace.trigger("file-open", workspace.activeFile);
  }

  const workspace = new Events();
  Object.assign(workspace, {
    activeFile: null,
    containerEl: null,
    onLayoutReady(cb) { window.setTimeout(cb, 0); },
    getLeavesOfType(t) { return leaves.filter((l) => l.view && l.view.getViewType() === t); },
    getRightLeaf() { const l = new WorkspaceLeaf(app, document.querySelector(".mod-right-split .workspace-leaf")); leaves.push(l); return l; },
    getLeftLeaf() { return this.getRightLeaf(); },
    async revealLeaf() {},
    getActiveFile() { return this.activeFile; },
    getLeaf() { return mainLeaf; },
    async openLinkText(link, src) {
      const name = String(link).split("#")[0].split("|")[0];
      let found = [...index.files].find((p) => p === name || p === name + ".md");
      if (!found) found = [...index.files].find((p) => p.split("/").pop() === name + ".md" || p.split("/").pop() === name);
      window.__calls.push(["openLinkText", link, found || null]);
      if (found) await openInMain(new TFile(found));
    },
    setActiveLeaf() {},
  });

  // ---------- settings-box ----------
  const settingTabs = {};
  const setting = {
    modal: null,
    open() {
      if (this.modal) return;
      const m = new Modal(app);
      m.modalEl.addClass("mod-settings");
      m.titleEl.detach();
      const nav = m.contentEl.createDiv("vertical-tab-header");
      nav.createDiv({ cls: "vertical-tab-header-group-title", text: "Third-party plugins" });
      // how Obsidian: On the left-hand menu, you put it yourself. navEl tab (substitution navEl A plugin would break the menu.)
      for (const id of Object.keys(settingTabs)) nav.appendChild(settingTabs[id].navEl);
      this.content = m.contentEl.createDiv("vertical-tab-content-container");
      m.onClose = () => {
        if (this.active) this.active.hide();
        this.active = null;
        this.modal = null;
      };
      this.modal = m;
      m.open();
    },
    openTabById(id) {
      const tab = settingTabs[id];
      if (!tab || !this.content) return;
      if (this.active && this.active !== tab) {
        this.active.navEl.removeClass("is-active");
        this.active.hide();
      }
      this.content.empty();
      this.active = tab;
      tab.navEl.addClass("is-active");
      this.content.appendChild(tab.containerEl);
      tab.renderTab();
    },
    close() { if (this.modal) this.modal.close(); },
  };

  // ---------- Plugin ----------
  const commands = {};
  class Plugin extends Component {
    constructor(appArg, manifest) { super(); this.app = appArg; this.manifest = manifest; }
    async loadData() { return INIT.pluginData ? JSON.parse(JSON.stringify(INIT.pluginData)) : null; }
    async saveData(d) { INIT.pluginData = JSON.parse(JSON.stringify(d)); await fsOp("plugin_data", "", { data: JSON.stringify(d, null, 2) }); }
    registerView(type, factory) { viewFactories[type] = factory; }
    addRibbonIcon(icon, title, cb) {
      const el = document.querySelector(".workspace-ribbon").createDiv({ cls: "side-dock-ribbon-action clickable-icon", attr: { "aria-label": title } });
      setIcon(el, icon);
      el.addEventListener("click", cb);
      return el;
    }
    addStatusBarItem() { return document.querySelector(".status-bar").createDiv("status-bar-item"); }
    addCommand(c) { commands[c.id] = c; return c; }
    addSettingTab(t) {
      this.settingTab = t;
      if (!t.navEl) {
        t.navEl = createDiv({ cls: "vertical-tab-nav-item tappable", text: t.name });
        t.navEl.addEventListener("click", () => setting.openTabById(t.id));
      }
      t.update();
      settingTabs[this.manifest.id] = t;
    }
  }

  const Platform = { isDesktop: true, isDesktopApp: true, isMobile: false, isMobileApp: false, isWin: false, isMacOS: false, isLinux: true };

  const app = { vault, workspace, fileManager, setting, commands: { commands, executeCommandById: (id) => { const c = commands[id]; if (!c) return false; if (c.checkCallback) return c.checkCallback(false); c.callback(); return true; } }, metadataCache: new Events() };
  window.app = app;

  window.__obsidian = {
    App: function () {}, Component, Events, Plugin, SettingTab, PluginSettingTab, Setting, Modal, SuggestModal, FuzzySuggestModal, Notice,
    MarkdownRenderer, ItemView, MarkdownView, View, WorkspaceLeaf, TFile, TFolder, TAbstractFile, FileSystemAdapter, DataAdapter, Platform,
    TextComponent, TextAreaComponent, DropdownComponent, ToggleComponent, ButtonComponent, ExtraButtonComponent, ColorComponent,
    setIcon, normalizePath: norm, apiVersion: "1.15.0",
  };

  // ---------- modules Node/Electron plug-in ----------
  class Emitter {
    constructor() { this._h = {}; }
    on(e, cb) { (this._h[e] = this._h[e] || []).push(cb); return this; }
    once(e, cb) { const w = (...a) => { this.off(e, w); cb(...a); }; return this.on(e, w); }
    off(e, cb) { this._h[e] = (this._h[e] || []).filter((x) => x !== cb); return this; }
    emit(e, ...a) { for (const cb of [...(this._h[e] || [])]) { try { cb(...a); } catch (err) { reportError(err); } } }
  }
  class FakeStream extends Emitter { setEncoding() { return this; } }
  let spawnSeq = 0;
  function spawn(cmd, args, opts) {
    const id = ++spawnSeq;
    const child = new Emitter();
    child.stdout = new FakeStream();
    child.stderr = new FakeStream();
    child.pid = 10000 + id;
    // input: build up before launch (and leaves with launch.); if end() not called — The input remains open,
    // subsequent write()/end() go through __spawnWrite (orderly, post-launch)
    let stdin = null;
    let ended = false;
    let phase = 0; // 0 — not yet launched, 1 — launch, 2 — launched
    const queue = [];
    const send = (data, end) => {
      if (phase === 2) window.__spawnWrite(JSON.stringify({ id, data, end: !!end }));
      else queue.push({ data, end: !!end });
    };
    child.stdin = {
      destroyed: false,
      write(d) { if (phase === 0) stdin = (stdin || "") + String(d); else send(String(d), false); return true; },
      end(d) {
        if (phase === 0) { if (d != null) stdin = (stdin || "") + String(d); else if (stdin == null) stdin = ""; ended = true; }
        else send(d == null ? "" : String(d), true);
        this.destroyed = true;
      },
    };
    child.kill = (sig) => { window.__spawnKill(JSON.stringify({ id, sig: sig || "SIGTERM" })); return true; };
    window.__calls.push(["spawn", cmd, args]);
    window.setTimeout(async () => {
      let r;
      phase = 1;
      try {
        r = JSON.parse(await window.__spawnStart(JSON.stringify({ id, cmd, args, cwd: opts && opts.cwd, env: opts && opts.env, stdin, keepOpen: !ended })));
      } catch (e) { r = { error: String(e) }; }
      if (r.error) { child.emit("error", new Error(r.error)); return; }
      phase = 2;
      for (const q of queue.splice(0)) window.__spawnWrite(JSON.stringify({ id, data: q.data, end: q.end }));
      const poll = async () => {
        const p = JSON.parse(await window.__spawnPoll(String(id)));
        if (p.out) child.stdout.emit("data", p.out);
        if (p.err) child.stderr.emit("data", p.err);
        if (p.exited) {
          child.stdin.destroyed = true;
          await refreshIndex();
          child.emit("exit", p.code);
          child.emit("close", p.code);
          return;
        }
        window.setTimeout(poll, 60);
      };
      poll();
    }, 0);
    return child;
  }
  const existing = new Set(INIT.existing || []);
  const fsMod = {
    existsSync(p) { p = String(p); return existing.has(p) || p === INIT.vaultBase || p.startsWith(INIT.vaultBase + "/"); },
    mkdirSync(p) { window.__fsAbs(JSON.stringify({ op: "mkdir", path: String(p) })); },
    writeFileSync(p, data) { window.__calls.push(["writeFileSync", String(p)]); window.__fsAbs(JSON.stringify({ op: "write", path: String(p), data: String(data || "") })); },
    promises: {
      async readFile(p) {
        const r = JSON.parse(await window.__fsAbs(JSON.stringify({ op: "read", path: String(p) })));
        if (r.error || typeof r.value !== "string") {
          const e = new Error(r.error || "ENOENT: " + p);
          e.code = "ENOENT";
          throw e;
        }
        return r.value;
      },
    },
  };
  const pathMod = {
    sep: "/",
    join(...a) { return a.filter((x) => x !== "" && x != null).join("/").replace(/\/+/g, "/"); },
    dirname(p) { const i = String(p).lastIndexOf("/"); return i > 0 ? p.slice(0, i) : "/"; },
    basename(p, ext) { let b = String(p).split("/").pop(); if (ext && b.endsWith(ext)) b = b.slice(0, -ext.length); return b; },
    extname(p) { const b = String(p).split("/").pop(); const i = b.lastIndexOf("."); return i > 0 ? b.slice(i) : ""; },
    resolve(...a) { return pathMod.join(...a); },
    normalize(p) { return String(p).replace(/\/+/g, "/"); },
  };
  window.__clipboard = "";
  window.__clipboardDenied = false; // true — windowless: navigator.clipboard refuse, plugin takes buffer Electron
  window.__clipboardVia = "";
  try {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText(t) {
          if (window.__clipboardDenied) return Promise.reject(new DOMException("Document is not focused.", "NotAllowedError"));
          window.__clipboard = String(t); window.__clipboardVia = "navigator"; return Promise.resolve();
        },
        readText() { return Promise.resolve(window.__clipboard); },
      },
    });
  } catch (e) { /* arch-browser */ }
  const electron = {
    clipboard: { writeText(t) { window.__clipboard = String(t); window.__clipboardVia = "electron"; }, readText() { return window.__clipboard; } },
    shell: {
      openPath(p) { window.__calls.push(["openPath", p]); return Promise.resolve(""); },
      showItemInFolder(p) { window.__calls.push(["showItemInFolder", p]); },
      openExternal(u) { window.__calls.push(["openExternal", u]); return Promise.resolve(); },
    },
  };
  // system-notification (window.Notification) — write-in __osNotices
  window.__osNotices = [];
  function FakeNotification(title, o) {
    window.__osNotices.push({ title: String(title), body: String((o && o.body) || ""), silent: !!(o && o.silent) });
    this.title = title;
    this.onclick = null;
    this.close = () => {};
  }
  FakeNotification.permission = "granted";
  FakeNotification.requestPermission = () => Promise.resolve("granted");
  window.Notification = FakeNotification;
  // focus Obsidian: window.__focus = false — «folded / window»
  window.__focus = null;
  const realHasFocus = document.hasFocus.bind(document);
  document.hasFocus = () => (window.__focus === null ? realHasFocus() : !!window.__focus);
  // built-in Obsidian «Reboot without saving» — only
  commands["app:reload"] = { id: "app:reload", name: "Reload app without saving", callback: () => window.__calls.push(["app:reload"]) };
  const osMod = { release: () => "6.1.0-test", platform: () => "linux", arch: () => "x64", homedir: () => "/home/test", EOL: "\n" };
  const modules = { obsidian: window.__obsidian, child_process: { spawn }, fs: fsMod, path: pathMod, electron, os: osMod };
  window.__require = (name) => {
    const n = String(name).replace(/^node:/, "");
    if (!(n in modules)) throw new Error("require: no module " + name);
    return modules[n];
  };
  window.process = { env: { HOME: "/home/test", PATH: "/usr/bin:/bin" }, platform: "linux", arch: "x64" };

  function reportError(e) {
    console.error(e);
    window.__errors.push(String((e && e.stack) || e));
  }
  window.addEventListener("error", (e) => window.__errors.push(String(e.message || e)));
  window.addEventListener("unhandledrejection", (e) => window.__errors.push("unhandledrejection: " + String((e.reason && e.reason.stack) || e.reason)));

  // ---------- plugin-launch ----------
  window.__boot = async function () {
    await refreshIndex();
    window.setInterval(() => refreshIndex().catch(() => {}), 1000);
    const code = await (await fetch(INIT.pluginUrl + "main.js")).text();
    const manifest = await (await fetch(INIT.pluginUrl + "manifest.json")).json();
    const module = { exports: {} };
    // how Obsidian: plugin code signed «plugin:<id>» — This signage recognizes the plugins errors.
    window.eval(`(function anonymous(require,module,exports){${code}\n}) //# sourceURL=plugin:${encodeURIComponent(manifest.id)}`)(window.__require, module, module.exports);
    const P = module.exports.default || module.exports;
    const plugin = new P(app, manifest);
    window.__plugin = plugin;
    await plugin.onload();
    return manifest.id;
  };
})();

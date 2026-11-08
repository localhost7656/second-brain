"""Verification of the plugin «Second Brain» presently Obsidian (Linux, virtual-screen Xvfb).
Plunge run_e2e.py know-how Obsidian only, whats in it; here — himself Obsidian: his settings window
(into 1.15 — window-off), left-hand, dialogue, clipboard, window-console.
Script: team-setting setup → plugin-trust → panel → Phase 1 → structure →
panel → settings in a separate window (tabs, search, threshold, Deletion proof-of-model profile,
check-in) → modal-window setting → «New thought» → plugin error («Copy report», journal) →
«Developer report» → Console errors in all windows → The names in the plugin classes do not match the internal
name-name Obsidian (so 1.13+ setup broken 2.5). Screenshots — into <work-folder>/shots.
Launch: python3 run_real.py [folder Obsidian for Linux (unpacked tar.gz)] [work-folder]
Needed.: Xvfb, Python s PyYAML, requests, numpy, dulwich and playwright. Program folder — BRAIN_APP or two folders above."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

import yaml
from playwright.async_api import async_playwright

E2E = Path(__file__).resolve().parent


def _app_dir() -> Path:
    if os.environ.get("BRAIN_APP"):
        return Path(os.environ["BRAIN_APP"])
    for cand in (E2E.parent.parent, E2E.parent / "app", Path("/data/brain/app")):
        if (cand / "brain" / "__main__.py").exists():
            return cand
    raise SystemExit("No program folder found.: Put it in the variable. BRAIN_APP")


APP = _app_dir()
OBS = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OBSIDIAN_DIR", "/data/obs/obsidian-1.15.0"))
ROOT = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/real")
PROG, VAULT, CFG, SHOTS = ROOT / "prog", ROOT / "vault", ROOT / "cfg", ROOT / "shots"
PID = "vtoroy-mozg"
PORT = int(os.environ.get("REAL_PORT", "9333"))
DISPLAY = os.environ.get("REAL_DISPLAY", ":99")
DEPS = os.environ.get("BRAIN_DEPS") or ("/data/brain/_deps" if Path("/data/brain/_deps").exists() else "")
PASSED: list = []
CONSOLE: list = []  # (window, type, text)
ALLOWED = ["error-check"]  # mistake, self-testing


SRC = next((p for p in (E2E.parent / "src", E2E.parent / "plugin" / "src") if (p / "main.ts").exists()), None)
DTS = SRC.parent / "node_modules" / "obsidian" / "obsidian.d.ts" if SRC else None
# method, which Obsidian and waiting for the plugin (They need to be redefined.)
OVERRIDES = {"onload", "onunload", "display", "hide", "onOpen", "onClose", "getViewType", "getDisplayText", "getIcon",
             "getItems", "getItemText", "onChooseItem", "getSuggestions", "renderSuggestion", "onChooseSuggestion"}
# field, which Obsidian swells up, plugin (inspected separately, same-sense)
SAME_VALUE = {"PluginSettingTab": {"plugin"}}


def _top_level(s: str, start: int) -> tuple[str, int]:
    """Body text of the class at the first level of brackets (lineless); start — index «{»."""
    depth, j, instr, esc, buf = 0, start, None, False, []
    line_c = block_c = False
    while j < len(s):
        c, nx = s[j], s[j + 1] if j + 1 < len(s) else ""
        if line_c:
            if c == "\n":
                line_c = False
                if depth == 1:
                    buf.append("\n")
            j += 1
            continue
        if block_c:
            if c == "*" and nx == "/":
                block_c = False
                j += 2
                continue
            j += 1
            continue
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == instr:
                instr = None
            j += 1
            continue
        if c == "/" and nx == "/":
            line_c = True
            j += 2
            continue
        if c == "/" and nx == "*":
            block_c = True
            j += 2
            continue
        if c in "\"'`":
            instr = c
        elif c == "{":
            depth += 1
            if depth == 2:
                buf.append("{")
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
            if depth == 1:
                buf.append("}")
        elif depth == 1:
            buf.append(c)
        j += 1
    return "".join(buf), j


_MEMBER = r"(?:^|[\n;}])\s*(?:(?:private|public|protected|readonly|static|async|override|declare|abstract|get|set)\s+)*\*?([A-Za-z_$][\w$]*)\s*[?!]?\s*(?:\(|=|:|<)"


def plugin_classes() -> dict:
    """Plugin classes: name → (class Obsidian, from which he was inherited; names of fields and methods)."""
    import re
    out = {}
    for f in sorted(SRC.glob("*.ts")):
        s = f.read_text(encoding="utf-8")
        for m in re.finditer(r"class\s+(\w+)(?:<[^>]*>)?\s+extends\s+([\w.]+)(?:<[^>{]*>)?[^{]*\{", s):
            top, end = _top_level(s, m.end() - 1)
            names = set(re.findall(_MEMBER, top))
            cm = re.search(r"constructor\s*\(([^)]*)\)", s[m.end():end])
            if cm:
                names |= set(re.findall(r"(?:private|public|protected|readonly)\s+(\w+)", cm.group(1)))
            names.discard("constructor")
            out[m.group(1)] = (m.group(2).split(".")[-1], names)
    return out


def documented() -> dict:
    """obsidian.d.ts: class → His open names, together with his inherited (it API, it can be touched)."""
    import re
    if not DTS or not DTS.exists():
        return {}
    s = DTS.read_text(encoding="utf-8")
    raw = {}
    for m in re.finditer(r"export\s+(?:declare\s+)?(?:abstract\s+)?(class|interface)\s+(\w+)(?:<[^{]*?>)?\s*"
                         r"((?:extends|implements)[^{]*)?\{", s):
        top, _ = _top_level(s, m.end() - 1)
        parents = re.findall(r"([A-Za-z_$][\w$]*)(?:<[^,{]*?>)?", re.sub(r"\b(extends|implements)\b", ",", m.group(3) or ""))
        raw[m.group(2)] = (set(re.findall(_MEMBER, top)), [p for p in parents if p])
    memo: dict = {}

    def full(n, seen=()):
        if n in memo:
            return memo[n]
        own, parents = raw.get(n, (set(), []))
        res = set(own)
        for p in parents:
            if p not in seen:
                res |= full(p, seen + (n,))
        memo[n] = res
        return res
    return {n: full(n) for n in raw}


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)
    PASSED.append(msg)
    print(f"  ✓ {msg}", flush=True)


def step(name):
    print(f"\n=== {name}", flush=True)


def env() -> dict:
    e = dict(os.environ)
    e.update({"PYTHONPATH": os.pathsep.join(x for x in (DEPS, e.get("PYTHONPATH", "")) if x),
              "FAKE_LLM_STATE": str(ROOT / "fake_state.json"), "PYTHONUTF8": "1"})
    return e


def settings_yaml() -> dict:
    return yaml.safe_load((PROG / "settings.yaml").read_text(encoding="utf-8"))


# ---------- preparation: programme, storage, configuration Obsidian, team-setting setup ----------
def prepare():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    PROG.mkdir(parents=True)
    SHOTS.mkdir()
    for d in ("brain", "prompts", "plugin"):
        shutil.copytree(APP / d, PROG / d, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(APP / "settings.template.yaml", PROG / "settings.template.yaml")
    (PROG / ".venv" / "bin").mkdir(parents=True)
    os.symlink(sys.executable, PROG / ".venv" / "bin" / "python")
    (PROG / "settings.yaml").write_text(f"""vault: "{VAULT.as_posix()}"
llm:
  mode: fake
  model: "fake"
  fake_module: "{(APP / 'tests' / 'fake_llm.py').as_posix()}"
embeddings:
  mode: fake
  model: "fake-1"
""", encoding="utf-8")
    (VAULT / ".obsidian").mkdir(parents=True)
    arch = VAULT / "_staging" / "archive"
    arch.mkdir(parents=True)
    (arch / "journal 2023.txt").write_text(
        "02.04.2023\n\nI planted tomatoes in a greenhouse today.. Watering every day at night.\n\n"
        "A weather station can be put in a greenhouse in the country — humidify.\n", encoding="utf-8")
    (arch / "bakery.txt").write_text(
        "10.05.2023\n\nIm thinking of opening a little bakery near my house.. Cost of a loaf of bread — 50 ruble.\n", encoding="utf-8")
    (CFG / "obsidian").mkdir(parents=True)
    (CFG / "obsidian" / "obsidian.json").write_text(json.dumps(
        {"vaults": {"a1b2c3d4e5f60708": {"path": str(VAULT), "ts": int(time.time() * 1000), "open": True}}, "updateDisabled": True}),
        encoding="utf-8")
    step("Install: team setup (launcher «Install.bat»)")
    e = env()
    e.update({"BRAIN_OBSIDIAN_CONFIG": str(CFG / "obsidian"), "BRAIN_NO_OPEN": "1", "BRAIN_OBSIDIAN_RUNNING": "0"})
    for n in ("Phase 1.bat", "Update.bat"):
        (PROG / n).write_text("@echo off\r\n", encoding="utf-8")
    r = subprocess.run([str(PROG / ".venv" / "bin" / "python"), "-X", "utf8", "-m", "brain", "setup"], cwd=PROG,
                       capture_output=True, text=True, env=e, timeout=120, stdin=subprocess.DEVNULL)
    print(r.stdout.strip())
    ok(r.returncode == 0 and "Plugin installed" in r.stdout, "setup: plugin installed in the storage from obsidian.json")
    ok(not list(PROG.glob("*.bat")), "setup: .bat-files of previous versions removed")
    data = json.loads((VAULT / ".obsidian" / "plugins" / PID / "data.json").read_text(encoding="utf-8"))
    ok(data["programDir"] == str(PROG), "into data.json plug-in — program-folder")


# ---------- launch Obsidian ----------
def launch() -> subprocess.Popen:
    if subprocess.run(["pgrep", "-f", f"Xvfb {DISPLAY}"], capture_output=True).returncode != 0:
        subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1500x1000x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        time.sleep(1.5)
    subprocess.run(["pkill", "-f", str(OBS / "obsidian")], capture_output=True)
    time.sleep(1)
    e = env()
    e.update({"DISPLAY": DISPLAY, "XDG_CONFIG_HOME": str(CFG)})
    log = open(ROOT / "obsidian.log", "w")
    p = subprocess.Popen([str(OBS / "obsidian"), "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                          f"--remote-debugging-port={PORT}", "--lang=en"], cwd=OBS, env=e, stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1).read()
            return p
        except OSError:
            time.sleep(0.5)
    raise SystemExit("Obsidian failed to open the debugging port — centimeter. " + str(ROOT / "obsidian.log"))


# ---------- helper ----------
class W:
    """Windows Obsidian (page CDP)."""
    ctx = None
    main = None


def watch(page, name=None):
    if getattr(page, "_vm_watched", False):
        return
    page._vm_watched = True

    def label():
        return name or page.url[:60]
    page.on("console", lambda m: CONSOLE.append((label(), m.type, m.text)) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: CONSOLE.append((label(), "pageerror", str(e))))


async def js(expr, page=None):
    return await (page or W.main).evaluate(expr)


async def until(expr, timeout=30, page=None, what=None):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        try:
            v = await js(expr, page)
            if v:
                return v
        except Exception as e:  # noqa: BLE001
            last = e
        await asyncio.sleep(0.2)
    raise AssertionError(f"waited: {what or expr[:150]}" + (f" ({last})" if last else ""))


async def find_page(pred: str, timeout=15):
    """Window., conditional (JS), — for example, piece, settings."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        for p in W.ctx.pages:
            watch(p)
            try:
                if await p.evaluate(pred):
                    return p
            except Exception:  # noqa: BLE001
                pass
        await asyncio.sleep(0.25)
    raise AssertionError(f"no window, where {pred[:120]}")


P = f"app.plugins.plugins['{PID}']"


async def wait_idle(timeout=180):
    await asyncio.sleep(0.4)
    await until(f"() => {P} && !{P}.engine.busy() && !{P}.engine.current", timeout, what="Program launches are over")


async def last_job():
    return await js(f"() => {{ const j = {P}.engine.history[0]; return j && {{label: j.label, status: j.status, ok: j.result && j.result.ok,"
                    " error: j.result && j.result.error, lines: j.lines.slice(-8)}; }")


async def ui():
    return json.loads((VAULT / ".system" / "ui.json").read_text(encoding="utf-8"))


async def shot(name, page=None):
    await asyncio.sleep(0.3)
    await (page or W.main).screenshot(path=str(SHOTS / f"{len(list(SHOTS.glob('*.png'))) + 1:02d}-{name}.png"))


async def focus(page):
    """Window. — front-end (click-on): Obsidian opens its windows-dialog."""
    await page.bring_to_front()
    await asyncio.sleep(0.3)


async def click_text(page, text, scope="body"):
    await page.locator(scope).locator("button", has_text=text).first.click()


async def until_yaml(fn, what, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if fn(settings_yaml()):
                return True
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(0.25)
    raise AssertionError("settings.yaml: waited — " + what)


def sitem(page, name, scope=".vm-settings"):
    return page.locator(f"{scope} .setting-item").filter(has=page.locator(".setting-item-name", has_text=name)).first


async def settings_loaded(page):
    await until("() => { const b = document.querySelector('.vm-settings .vm-set-body');"
                " return b && !b.textContent.includes('Downloading program settings') && b.querySelectorAll('.setting-item').length > 0; }",
                30, page, "Program settings are loaded")


async def check_tabs(page, where, shots_prefix=None):
    tabs = [t.strip() for t in await page.locator(".vm-settings .vm-set-tab").all_inner_texts()]
    ok(tabs == ["General", "Models", "Thresholds", "Incoming", "Documents", "Expenses", "Advanced"], f"{where}: tab {', '.join(tabs)}")
    for name in tabs:
        await page.locator(".vm-settings .vm-set-tab", has_text=name).first.click()
        await asyncio.sleep(0.35)
        n_items = await page.locator(".vm-settings .vm-set-body .setting-item").count()
        n_err = await page.locator(".vm-settings .vm-error-box").count()
        ok(n_items > 0 and n_err == 0, f"{where}: «{name}» — {n_items} settings, faultless")
        if shots_prefix:
            await shot(f"{shots_prefix}-{name}", page)


async def profile_add_delete(page, where):
    """«＋ Local» → profile settings.yaml → removal (What window does the dialogue hold?)."""
    await page.locator(".vm-settings .vm-set-tab", has_text="Models").first.click()
    await until("() => !!document.querySelector('.vm-settings .vm-prof-editor')", 10, page, "profiler")
    await click_text(page, "＋ Local", ".vm-settings")
    await until_yaml(lambda s: any(p.get("kind") == "local" for p in s["llm"]["profiles"]), "local profile added")
    ok(True, f"{where}: «＋ Local» — profile settings.yaml")
    await sitem(page, "Profile to edit").locator(".extra-setting-button").first.click()
    dlg = await find_page("() => [...document.querySelectorAll('.modal-container .modal')].some(m => m.textContent.includes('Delete profile?'))", 8)
    same = dlg == page
    ok(same, f"{where}: Deletion confirmation opened in the same window, so-called")
    await dlg.locator(".modal-container .modal", has_text="Delete profile?").locator("button", has_text="Delete").first.click()
    await until_yaml(lambda s: not any(p.get("kind") == "local" for p in s["llm"]["profiles"]), "local profile removed")
    ok(True, f"{where}: Profile removed after confirmation")


async def own_model(page):
    """«Where to run: on this computer» — block «Your model» window «Start model…» (launch)."""
    saved = (PROG / "settings.yaml").read_text(encoding="utf-8")
    await page.locator(".vm-settings .vm-set-tab", has_text="Models").first.click()
    await asyncio.sleep(0.3)
    where = page.locator(".vm-settings .vm-set-body .setting-item:visible").filter(
        has=page.locator(".setting-item-name", has_text="Where to run")).first
    await where.scroll_into_view_if_needed()
    await where.locator("select.dropdown:not(.is-measuring)").select_option("local")  # into 1.15 near — hidden «measuring»
    await until_yaml(lambda s: s["embeddings"]["mode"] == "local", "embedding — on this computer")
    await until("() => (document.querySelector('.vm-settings .vm-llama-box') || {}).textContent?.includes('server:')",
                40, page, "block «Your model»")
    box = page.locator(".vm-settings .vm-llama-box")
    await until("() => !(document.querySelector('.vm-settings .vm-llama-box') || {}).textContent?.includes('not the server')",
                20, page, "block «Your model» Read the address after saving it.")
    ok(True, "shift «Where to run» block read over: default — This is your server.")
    txt = await box.inner_text()
    ok("not downloaded" in txt and await box.locator("button", has_text="Start model…").count() == 1,
       "block «Your model»: model, eat «Start model…»")
    await box.scroll_into_view_if_needed()
    await shot("own-model", page)
    await box.locator("button", has_text="Start model…").click()
    dlg = await find_page("() => !!document.querySelector('.modal.vm-llama-modal')", 10)
    ok(dlg == page, "window «Start model…» opened in the settings window")
    await until("() => !!document.querySelector('.vm-llama .vm-llama-hw-grid')", 40, dlg, "computer")
    m = dlg.locator(".modal.vm-llama-modal")
    ram = m.locator(".vm-llama-ram")
    ok(await ram.count() == 1 and "16 GB" in await ram.inner_text() and "4,096" in await ram.inner_text(),
       "trigger-window: warning «minimum 16 GB» And how long does it take to model with context? 4096")
    opt = await m.locator(".setting-item", has_text="Context").locator("select.dropdown:not(.is-measuring) option[value='8192']").inner_text()
    ok("9.6 GB" in opt, f"contextualization — memoryily: {opt}")
    await shot("window-launch-model", dlg)
    await m.locator(".vm-modal-buttons button", has_text="Cancel").click()
    await asyncio.sleep(0.3)
    ok(await dlg.locator(".modal.vm-llama-modal").count() == 0, "«Cancel» shut the window, flat-out")
    (PROG / "settings.yaml").write_text(saved, encoding="utf-8")


# ---------- scripture ----------
async def scenario():
    page = W.main
    step("1. Obsidian vault; plugin-trust; panel")
    btn = None
    t0 = time.time()
    while time.time() - t0 < 30 and not btn:
        if await page.locator("button", has_text="Trust author and enable plugins").count():
            btn = page.locator("button", has_text="Trust author and enable plugins").first
        else:
            if await js(f"() => !!(window.app && {P})"):
                break
            await asyncio.sleep(0.3)
    if btn:
        await shot("trust-plug-ins")
        await btn.click()
        ok(True, "dialogue «Do you trust the author of this store??» — pressed «Trust author and enable plugins»")
    await until(f"() => !!(window.app && {P} && {P}.engine)", 30, what="plugin loaded")
    await asyncio.sleep(1)
    await js("() => app.setting.close()")  # after «Trust me.…» Obsidian open-ended «Third-party plugins»
    # class Modal — topmost in the chain settings window, who open and onOpen; his open remembers open windows
    await js("""() => {
      let q = Object.getPrototypeOf(app.setting), M = null;
      while (q && q !== Object.prototype) { if (q.hasOwnProperty('open') && q.hasOwnProperty('onOpen')) M = q; q = Object.getPrototypeOf(q); }
      window.__vmModalProto = M; window.__vmModals = [];
      const orig = M.open;
      M.open = function (...a) { window.__vmModals.push(this); return orig.apply(this, a); };
    }""")
    await focus(page)
    ver = await js("() => (navigator.userAgent.match(/obsidian\\/([\\d.]+)/i) || [])[1]")
    man = json.loads((PROG / "plugin" / "manifest.json").read_text(encoding="utf-8"))
    ok(await js(f"() => {P}.manifest.version") == man["version"], f"plugin {man['version']} loaded Obsidian {ver}")
    await until("() => !!document.querySelector('.vm-view .vm-wizard')", 30, what="first-loader")
    await wait_idle()
    ok("Phase 1" in await page.locator(".vm-step.is-current .vm-step-title").inner_text(), "master: step-by-step — Phase 1")
    ok("Second Brain" in await page.locator(".status-bar").inner_text(), "status-line: «Second Brain»")
    await shot("panel-master")

    step("2. Phase 1 → draft → confirmation")
    await focus(page)
    await click_text(page, "Start Phase 1", ".vm-view")
    await wait_idle()
    j = await last_job()
    ok(j and j["ok"], f"Phase 1 worked out: {j and j['lines'][-1:]}")
    u = await ui()
    ok(u["status"]["structure_pending"] and u["status"]["draft"], "draft structure awaits approval")
    await click_text(page, "Open draft", ".vm-view")
    await until("() => (app.workspace.getActiveFile()?.path || '').includes('structure')", 10, what="draft")
    ok(True, "The draft opened in the editor Obsidian")
    await click_text(page, "Approve structure", ".vm-view")
    m = page.locator(".modal-container .modal", has_text="Approve structure?")
    await m.wait_for(state="visible", timeout=10000)
    await shot("approve-structure")
    await m.locator("button", has_text="Approve and continue").click()
    await wait_idle()
    u = await ui()
    ok(u["status"]["approved_once"] and not u["status"]["structure_pending"] and len(u["containers"]) >= 2,
       f"structure approved, container: {', '.join(c['title'] for c in u['containers'])}")
    await until(f"() => document.querySelectorAll('.vm-view .vm-tree-row').length === {len(u['containers'])}", 10,
                what="panel-wood")
    ok(True, "panel-wood")
    await shot("panel-survey")

    step("3. Panel tabs")
    for name in ("Questions", "Container", "Expenses", "Log", "Overview"):
        await page.locator(".vm-view .vm-tab", has_text=name).first.click()
        await asyncio.sleep(0.4)
        txt = await page.locator(".vm-view .vm-body").inner_text()
        ok(txt.strip() and not await page.locator(".vm-view .vm-error-box").count(), f"tab «{name}» painted")
        if name in ("Questions", "Expenses"):
            await shot(f"panel-{name}")

    step("4. Settings in a separate window (so Obsidian 1.15 default)")
    ok(await js("() => app.vault.getConfig('settingsPopoutWindow')") is True, "into Obsidian included «Open the settings in a separate window»")
    await page.locator(".vm-view .vm-head-tools .vm-icon-btn").nth(1).click()
    sp = await find_page("() => !!document.querySelector('.vm-settings .vm-set-tab')", 20)
    watch(sp, "settings-box")
    await focus(sp)
    ok(sp != page, f"settings opened in a separate window («{await sp.title()}»)")
    await settings_loaded(sp)
    nav = sp.locator(".vertical-tab-nav-item", has_text="Second Brain")
    ok(await nav.count() == 1 and "is-active" in (await nav.first.get_attribute("class") or ""),
       "left-hand — point «Second Brain», chosen")
    heads = await sp.locator(".vm-settings .setting-item-heading .setting-item-name").all_inner_texts()
    ok(all(h in heads for h in ("Program", "Windows notifications", "Updates")), "«General»: " + ", ".join(heads))
    ok("Program found" in await sp.locator(".vm-settings .vm-callout").first.inner_text(), "«Program found»")
    await check_tabs(sp, "settings-box", "setting")
    # search
    await sp.locator(".vm-settings input.vm-set-search").fill("budget")
    await asyncio.sleep(0.4)
    names = await sp.locator(".vm-settings .vm-search-pane:not(.vm-hidden) .setting-item:not(.setting-item-heading):not(.vm-hidden) .setting-item-name").all_inner_texts()
    ok("Monthly budget, $" in names, f"search «budget»: {', '.join(names)}")
    await shot("setting-search", sp)
    await sp.locator(".vm-settings input.vm-set-search").fill("")
    await asyncio.sleep(0.3)
    # threshold: field
    await sp.locator(".vm-settings .vm-set-tab", has_text="Thresholds").first.click()
    await asyncio.sleep(0.3)
    item = sp.locator(".vm-settings .setting-item").filter(has=sp.locator("input.vm-set-range")).first
    num = item.locator("input.vm-num")
    rs = item.locator(".vm-reset")

    async def reset_state():
        return (await rs.get_attribute("class") or "", float(await rs.evaluate("(e) => getComputedStyle(e).opacity")),
                await rs.is_visible())
    cls, op, vis = await reset_state()
    ok(vis and "vm-reset-off" in cls and "is-disabled" in cls and op < 0.6,
       f"↺ visible and silent — idle (transparency {op:g})")
    await shot("threshold-down-default", sp)
    await rs.click(force=True)
    await asyncio.sleep(0.3)
    ok(await num.input_value() == "70", "idle ↺ It doesnt change anything.")
    await num.fill("77")
    await until_yaml(lambda s: s["thresholds"]["classification"] == 77, "classification = 77")
    ok(True, "threshold changed in the field — recorded settings.yaml (77)")
    cls, op, vis = await reset_state()
    ok("vm-reset-off" not in cls and "is-disabled" not in cls and op > 0.9, f"threshold changed — ↺ bright and active (transparency {op:g})")
    await shot("threshold-modified", sp)
    await rs.click()
    await until_yaml(lambda s: "classification" not in (s.get("thresholds") or {}) or s["thresholds"]["classification"] == 70,
                     "threshold returned to default")
    await asyncio.sleep(0.3)
    cls, op, vis = await reset_state()
    ok("vm-reset-off" in cls and op < 0.6, "↺ I returned the default threshold and again faded.")
    await profile_add_delete(sp, "settings-box")
    # check-in
    await click_text(sp, "Check connection", ".vm-settings")
    chk = await find_page("() => !!document.querySelector('.modal-container .vm-check-item')", 10)
    ok(chk == sp, "«Check connection» opened in the settings window")
    await until("() => document.querySelectorAll('.modal-container .vm-check-item').length >= 2"
                " && !document.querySelector('.modal-container .vm-wait')", 60, chk, "linkage")
    n_ok, n_bad = await chk.locator(".vm-check-item.is-ok").count(), await chk.locator(".vm-check-item.is-bad").count()
    ok(n_bad == 0, f"check-in: {n_ok} ✓, {n_bad} ✗")
    await shot("check-up-linkage", chk)
    await chk.locator(".modal-container .vm-modal-buttons button", has_text="Close").click()
    await asyncio.sleep(0.3)
    await own_model(sp)
    await js("() => app.setting.close()")
    for _ in range(50):
        if sp.is_closed():
            break
        await asyncio.sleep(0.2)
    ok(sp.is_closed(), "The settings window closed.")

    step("5. Modal window settings (if «Open the settings in a separate window» switched off)")
    await focus(page)
    await js("() => app.vault.setConfig('settingsPopoutWindow', false)")
    await js(f"() => {P}.openSettings('main')")
    await until("() => !!document.querySelector('.modal.mod-settings .vm-settings .vm-set-tab')", 15, page, "settings in the modal window")
    await settings_loaded(page)
    nav = page.locator(".modal.mod-settings .vertical-tab-nav-item", has_text="Second Brain")
    ok(await nav.count() == 1 and "is-active" in (await nav.first.get_attribute("class") or ""), "modal-window: point «Second Brain» menu")
    await check_tabs(page, "modal-window")
    await page.locator(".vm-settings .vm-set-tab", has_text="General").first.click()
    await shot("setting-modal")
    await profile_add_delete(page, "modal-window")
    await js("() => app.setting.close()")
    await js("() => app.vault.setConfig('settingsPopoutWindow', true)")

    step("6. New thought")
    await focus(page)
    await js(f"() => app.commands.executeCommandById('{PID}:new-thought')")
    m = page.locator(".modal-container .modal").filter(has=page.locator("textarea")).last
    await m.wait_for(state="visible", timeout=10000)
    await m.locator("textarea").fill("Weather station needs a second sensor — check out.")
    ok(not await m.locator("#vm-now").is_checked(), "flag «Handle it right away. (Phase 1)» default off")
    await m.locator("#vm-now").check()
    await shot("new-thought")
    await m.locator("button", has_text="Save").click()
    await asyncio.sleep(0.5)
    await wait_idle()
    srcs = [p for p in (VAULT / "_sources").glob("*.txt") if "second sensor" in p.read_text(encoding="utf-8")]
    ok(srcs, "thought preserved in _staging and treated with phase 1")
    await js(f"() => app.commands.executeCommandById('{PID}:revalidate')")
    await page.locator(".prompt .suggestion-item", has_text="All containers").first.wait_for(state="visible", timeout=10000)
    ok(await page.locator(".prompt .suggestion-item").count() >= 2, "«Revalidation…»: The container selection has opened")
    await page.keyboard.press("Escape")

    step("7. Error in the plugin: spot-on, journal, «Copy report»")
    await js(f"() => {{ const v = [...{P}.views][0]; v.renderUsageTab = () => {{ throw new Error('error-check'); }}; }}")
    await page.locator(".vm-view .vm-tab", has_text="Expenses").first.click()
    box = page.locator(".vm-view .vm-error-box")
    await box.wait_for(state="visible", timeout=5000)
    ok("Error in the plugin (panel, tab «Expenses»)" in await box.inner_text(), "tab error shown in place, The rest of the work")
    await shot("mistake-plug-in")
    await box.locator("button", has_text="Copy report").click()
    await asyncio.sleep(0.5)
    clip = await js("() => require('electron').clipboard.readText()")
    ok(clip.startswith("Second Brain — plugin error") and f"Obsidian: {ver}" in clip and "plugin:vtoroy-mozg" in clip,
       "clipboard — report: version and stack error")
    plog = VAULT / "_logs" / "plugin.log"
    await until("() => true", 1)
    ok(plog.exists() and "error-check" in plog.read_text(encoding="utf-8"), "misspelling _logs/plugin.log")
    await js(f"() => {{ const v = [...{P}.views][0]; delete v.renderUsageTab; v.render(true); }}")
    ok(await box.count() == 0, "After the tab is corrected, the tab is drawn again.")

    step("8. Developer report")
    await js(f"() => app.commands.executeCommandById('{PID}:report')")
    await until("() => app.workspace.getActiveFile()?.path === '_logs/developer-report.md'", 15, what="report")
    rep = (VAULT / "_logs" / "developer-report.md").read_text(encoding="utf-8")
    ok(f"Obsidian: {ver}" in rep and "error-check" in rep and "### Phase 1" in rep, "report: version, plugin errors, last launches")
    ok((await js("() => require('electron').clipboard.readText()")).startswith("# Second Brain — developer report"),
       "report and clipboard")
    await shot("report")

    step("9. All-window console Obsidian")
    bad = [c for c in CONSOLE if c[1] in ("error", "pageerror") and not any(a in c[2] for a in ALLOWED)]
    mine = [c for c in bad if "vtoroy" in c[2] or "Second Brain" in c[2] or "plugin:" in c[2]]
    for c in bad:
        print("  console:", c[0], c[1], c[2][:300])
    ok(not mine, "There are no plugin errors in the console" + (f": {mine[:3]}" if mine else ""))

    step("10. Names in the classes of the plugin do not match the internal names Obsidian")
    # Obsidian 1.13+ He put his own sleeves in the sleeve. renderTab() and navEl — same names in the plugin 2.5 broke the settings.
    # Here.: Plugin source names versus the present name Obsidian (class chain and empty instance field)
    # minus open API from obsidian.d.ts.
    rt = await js(f"""() => {{
      const P = {P};
      const leaf = app.workspace.getLeavesOfType('vtoroy-mozg-panel')[0];
      const up = (o, n) => {{ let q = o; for (let i = 0; i < n; i++) q = q && Object.getPrototypeOf(q); return q; }};
      const names = (proto, args) => {{
        if (!proto) return null;
        const s = new Set(); let q = proto;
        while (q && q !== Object.prototype) {{ for (const n of Object.getOwnPropertyNames(q)) s.add(n); q = Object.getPrototypeOf(q); }}
        // hollow-out — subclass-plug: In abstract classes, the designer calls getViewType() ot. p..
        const Stub = class extends proto.constructor {{
          getViewType() {{ return 'vm-probe'; }} getDisplayText() {{ return ''; }} display() {{}}
          getItems() {{ return []; }} getItemText() {{ return ''; }} onChooseItem() {{}}
          getSuggestions() {{ return []; }} renderSuggestion() {{}} onChooseSuggestion() {{}}
        }};
        try {{ for (const k of Object.keys(new Stub(...args))) s.add(k); }} catch (e) {{ s.add('!' + e); }}
        s.delete('constructor');
        return [...s];
      }};
      const picker = window.__vmModals.find((m) => Object.getPrototypeOf(m).hasOwnProperty('getItemText'));
      return {{
        Plugin: names(up(P, 2), [app, P.manifest]),
        PluginSettingTab: names(up(P.brainTab, 2), [app, P]),
        ItemView: leaf ? names(up(leaf.view, 2), [leaf]) : null,
        Modal: names(window.__vmModalProto, [app]),
        FuzzySuggestModal: picker ? names(up(picker, 2), [app]) : null,
      }};
    }}""")
    ok(await js(f"() => {P}.brainTab.plugin === {P}"), "field-side plugin — same plugin, turn on Obsidian")
    (ROOT / "obsidian-names.json").write_text(json.dumps({"obsidian": ver, **rt}, ensure_ascii=False, indent=1), encoding="utf-8")
    api = documented()
    if not api:
        print("  (obsidian.d.ts found — open-minded API deductible, comparison)")
    classes = plugin_classes()
    ok(len(classes) >= 5, f"plugin classes: {len(classes)} ({', '.join(sorted(classes))})")
    for base in sorted({b for b, _ in classes.values()}):
        ob = rt.get(base)
        bad_ctor = [n for n in ob or [] if n.startswith("!")]
        ok(ob is not None and not bad_ctor, f"class Obsidian «{base}» found, Its an empty copy of it."
           + (f": {bad_ctor[0]}" if bad_ctor else ""))
    for cls, (base, mine_names) in sorted(classes.items()):
        internal = set(rt[base]) - api.get(base, set())
        clash = sorted((mine_names & internal) - OVERRIDES - SAME_VALUE.get(base, set()))
        ok(not clash, f"{cls} ({base}): {len(mine_names)} their names, none of them match up with {len(internal)} pristinely Obsidian"
           + (f" — COME ON: {', '.join(clash)}" if clash else ""))


async def main():
    prepare()
    proc = launch()
    code = 0
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        W.ctx = browser.contexts[0]
        W.ctx.on("page", lambda p: watch(p))
        W.main = await find_page("() => location.href.includes('index.html') && !!window.app", 60)
        watch(W.main, "window")
        try:
            await scenario()
            print(f"\nIts all gone.: {len(PASSED)} ✓ (screenshot: {SHOTS})")
        except Exception:  # noqa: BLE001
            code = 1
            traceback.print_exc()
            try:
                for i, p in enumerate(W.ctx.pages):
                    await p.screenshot(path=str(SHOTS / f"Mistake-{i}.png"))
            except Exception:  # noqa: BLE001
                pass
            for c in CONSOLE[-15:]:
                print("  console:", c[0], c[1], c[2][:500])
    if not os.environ.get("REAL_KEEP"):
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            pass
    return code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

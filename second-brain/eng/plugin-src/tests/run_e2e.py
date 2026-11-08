"""Verification of the plugin «Second Brain» browser-wise.
Page harness.html mimic Obsidian; assembled plugin (storage, where the team put him install-plugin)
runs the real program on a test vault with a test model (llm.mode: fake).
Launch: python3 run_e2e.py [folder]   — screenshot <folder>/shots.
Needed.: Python s PyYAML, requests, numpy, dulwich, playwright (browser: playwright install chromium);
assembled plugin <programme>/plugin (npm run build). Program folder — BRAIN_APP or two folders above this file."""
from __future__ import annotations

import asyncio
import codecs
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml
from playwright.async_api import async_playwright

E2E = Path(__file__).resolve().parent
def _app_dir() -> Path:
    if os.environ.get("BRAIN_APP"):
        return Path(os.environ["BRAIN_APP"])
    for cand in (E2E.parent.parent, Path("/data/brain/app")):  # complete: <programme>/plugin-src/tests
        if (cand / "brain" / "__main__.py").exists():
            return cand
    raise SystemExit("No program folder found.: Put it in the variable. BRAIN_APP")


APP = _app_dir()
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/e2e")
PROG, VAULT, SHOTS = ROOT / "prog", ROOT / "vault", ROOT / "shots"
PLUGIN_DIR = VAULT / ".obsidian" / "plugins" / "vtoroy-mozg"
ORIGIN = "http://obsidian.test/"
CHROMIUM = os.environ.get("CHROMIUM") or ("/usr/local/bin/chromium" if Path("/usr/local/bin/chromium").exists() else None)
EXTRA_ENV: dict = {}
PASSED: list = []


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)
    PASSED.append(msg)
    print(f"  ✓ {msg}", flush=True)


def step(name):
    print(f"\n=== {name}", flush=True)


def env():
    e = dict(os.environ)
    deps = os.environ.get("BRAIN_DEPS") or ("/data/brain/_deps" if Path("/data/brain/_deps").exists() else "")
    e.update({"PYTHONPATH": os.pathsep.join(x for x in (deps, e.get("PYTHONPATH", "")) if x),
              "FAKE_LLM_STATE": str(ROOT / "fake_state.json"), "PYTHONUTF8": "1"})
    e.update(EXTRA_ENV)
    return e


def prepare():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    PROG.mkdir(parents=True)
    SHOTS.mkdir()
    for d in ("brain", "prompts", "plugin"):
        shutil.copytree(APP / d, PROG / d, ignore=shutil.ignore_patterns("__pycache__"))
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
    (arch / "Chat with AI").mkdir(parents=True)
    (arch / "journal 2023.txt").write_text(
        "02.04.2023\n\nI planted tomatoes in a greenhouse today.. Watering every day at night.\n\n"
        "Cucumbers in the greenhouse grow poorly. Probably., light.\n\n"
        "A weather station can be put in a greenhouse in the country — humidify.\n\n"
        "I had a strange dream about the train..\n\nThe timer watering option needs to be checked..\n", encoding="utf-8")
    (arch / "Chat with AI" / "weather-station.txt").write_text(
        "01.06.2023\nIm: What sensor to take for a weather station — wired?\n"
        "AI: Wireless is more convenient and can be installed anywhere., Wired is cheaper and does not require batteries. "
        "If the price is important, wired looks smarter, But the accuracy must be checked on the spot..\n"
        "Im: Maybe., Its enough to have one sensor on the balcony..\nAI: Two sensors are better for accuracy., street-mate, second-in-the-room.\n"
        "Im: So,, Were taking two wired sensors.. You can put a sensor on the wall..\n"
        "Im: You can also install a sensor under the roof., So hes in the shadows..\n", encoding="utf-8")
    (arch / "bakery.txt").write_text(
        "10.05.2023\n\nIm thinking of opening a little bakery near my house.. Cost of a loaf of bread — 50 ruble.\n\n"
        "Rental of premises 40 000 rupees. I like the idea of self-service..\n", encoding="utf-8")
    (arch / "different.txt").write_text("We should take out old photos on the mezzanine..\n", encoding="utf-8")
    (arch / "flour.txt").write_text("12.05.2023\nhint: its about the dacha\n\nA baker at a nearby bakery said, It is better to take flour from the mill directly..\n", encoding="utf-8")
    step("Install plugin install-plugin")
    r = subprocess.run([str(PROG / ".venv" / "bin" / "python"), "-X", "utf8", "-m", "brain", "install-plugin", str(VAULT)],
                       cwd=PROG, capture_output=True, text=True, env=env(), timeout=120)
    print(r.stdout.strip())
    ok(r.returncode == 0, "install-plugin worked")
    ok(all((PLUGIN_DIR / f).exists() for f in ("main.js", "manifest.json", "styles.css", "data.json")), "plugin files are copied to .obsidian/plugins/vtoroy-mozg")
    ok(json.loads((VAULT / ".obsidian" / "community-plugins.json").read_text(encoding="utf-8")) == ["vtoroy-mozg"], "plugin included in community-plugins.json")
    data = json.loads((PLUGIN_DIR / "data.json").read_text(encoding="utf-8"))
    ok(data["programDir"] == str(PROG) and data["pythonPath"].endswith("python"), "into data.json the program folder is inscribed and Python")
    return data


# ---------- bridge ↔ Python ----------
def vpath(rel: str) -> Path:
    rel = (rel or "").strip("/")
    p = (VAULT / rel) if rel else VAULT
    rp = p.resolve()
    if rp != VAULT.resolve() and VAULT.resolve() not in rp.parents:
        raise ValueError("way out: " + rel)
    return p


def split_fm(text: str):
    m = re.match(r"^---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.S)
    if m:
        return m.group(1), text[m.end():]
    return None, text


class Bridge:
    def __init__(self, python_path):
        self.python = python_path
        self.procs: dict = {}
        self.runs: list = []

    async def fs_op(self, payload: str) -> str:
        d = json.loads(payload)
        op, rel = d["op"], d.get("path", "")
        try:
            p = vpath(rel)
            if op == "stat":
                if not p.exists():
                    return json.dumps({"value": None})
                st = p.stat()
                return json.dumps({"value": {"type": "folder" if p.is_dir() else "file", "ctime": int(st.st_ctime * 1000),
                                             "mtime": int(st.st_mtime * 1000), "size": st.st_size}})
            if op == "read":
                if not p.is_file():
                    return json.dumps({"error": f"ENOENT: no such file '{rel}'"})
                return json.dumps({"value": p.read_bytes().decode("utf-8", "replace")}, ensure_ascii=False)
            if op in ("write", "append"):
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "ab" if op == "append" else "wb") as f:
                    f.write(d["data"].encode("utf-8"))
                return json.dumps({"value": None})
            if op == "exists":
                return json.dumps({"value": p.exists()})
            if op == "mkdir":
                p.mkdir(parents=True, exist_ok=True)
                return json.dumps({"value": None})
            if op == "remove":
                p.unlink()
                return json.dumps({"value": None})
            if op == "list":
                files = [str(x.relative_to(VAULT)) for x in p.iterdir() if x.is_file()]
                folders = [str(x.relative_to(VAULT)) for x in p.iterdir() if x.is_dir()]
                return json.dumps({"value": {"files": files, "folders": folders}}, ensure_ascii=False)
            if op == "index":
                files, folders = [], []
                for x in VAULT.rglob("*"):
                    r = x.relative_to(VAULT)
                    if any(part.startswith(".") for part in r.parts):
                        continue
                    (folders if x.is_dir() else files).append(r.as_posix())
                return json.dumps({"value": {"files": files, "folders": folders}}, ensure_ascii=False)
            if op == "fm_read":
                raw, _ = split_fm(p.read_text(encoding="utf-8"))
                fm = yaml.safe_load(raw) if raw else {}
                return json.dumps({"value": json.loads(json.dumps(fm or {}, default=str, ensure_ascii=False))}, ensure_ascii=False)
            if op == "fm_write":
                text = p.read_text(encoding="utf-8")
                raw, body = split_fm(text)
                orig = (yaml.safe_load(raw) if raw else {}) or {}
                new = d["fm"]
                for k, v in list(new.items()):  # how Obsidian: The undisturbed values remain as they were. (date — date)
                    if k in orig and json.dumps(orig[k], default=str, ensure_ascii=False) == json.dumps(v, ensure_ascii=False):
                        new[k] = orig[k]
                dumped = yaml.safe_dump(new, allow_unicode=True, sort_keys=False, default_flow_style=False) if new else ""
                p.write_text(("---\n" + dumped + "---\n" if new else "") + body, encoding="utf-8")
                return json.dumps({"value": None})
            if op == "plugin_data":
                (PLUGIN_DIR / "data.json").write_text(d["data"], encoding="utf-8")
                return json.dumps({"value": None})
            return json.dumps({"error": "op " + op})
        except Exception as e:  # noqa: BLE001
            return json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)

    async def fs_abs(self, payload: str) -> str:
        d = json.loads(payload)
        p = Path(d["path"])
        if ROOT.resolve() not in p.resolve().parents:
            return "{}"
        if d["op"] == "mkdir":
            p.mkdir(parents=True, exist_ok=True)
        elif d["op"] == "write":
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(d.get("data", ""), encoding="utf-8")
        elif d["op"] == "read":
            if not p.is_file():
                return json.dumps({"error": f"ENOENT: {p}"}, ensure_ascii=False)
            return json.dumps({"value": p.read_text(encoding="utf-8", errors="replace")}, ensure_ascii=False)
        return "{}"

    async def spawn_start(self, payload: str) -> str:
        d = json.loads(payload)
        if d["cmd"] != self.python:
            return json.dumps({"error": f"launch «{d['cmd']}», a in the plugin settings Python «{self.python}»"}, ensure_ascii=False)
        e = env()
        for k, v in (d.get("env") or {}).items():
            if k.startswith("PYTHON") and k != "PYTHONPATH":
                e[k] = v
        p = await asyncio.create_subprocess_exec(sys.executable, *d["args"], cwd=d.get("cwd") or None, env=e,
                                                 stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.PIPE)
        ent = {"p": p, "out": [], "err": [], "done": False, "code": None, "args": d["args"], "t0": time.time(),
               "all_out": [], "all_err": [], "stdin": d.get("stdin"), "keep": bool(d.get("keepOpen")), "writes": []}
        self.procs[str(d["id"])] = ent
        self.runs.append(ent)

        async def pump(stream, key):
            dec = codecs.getincrementaldecoder("utf-8")("replace")
            while True:
                b = await stream.read(4096)
                s = dec.decode(b, final=not b)
                if s:
                    ent[key].append(s)
                    ent["all_" + key].append(s)
                if not b:
                    break

        async def runner():
            try:
                if d.get("stdin") is not None:
                    p.stdin.write(d["stdin"].encode("utf-8"))
                    await p.stdin.drain()
                if not ent["keep"]:  # play-off (--ask-stdin): open-in, answers — through spawn_write
                    p.stdin.close()
            except Exception:  # noqa: BLE001
                pass
            await asyncio.gather(pump(p.stdout, "out"), pump(p.stderr, "err"))
            ent["code"] = await p.wait()
            ent["done"] = True

        ent["task"] = asyncio.create_task(runner())
        return json.dumps({"pid": p.pid})

    async def spawn_write(self, payload: str) -> str:
        d = json.loads(payload)
        ent = self.procs.get(str(d["id"]))
        if not ent or ent["done"]:
            return "{}"
        ent["writes"].append(d.get("data") or "")
        p = ent["p"]
        try:
            if d.get("data"):
                p.stdin.write(d["data"].encode("utf-8"))
                await p.stdin.drain()
            if d.get("end"):
                p.stdin.close()
        except Exception:  # noqa: BLE001 — process is already over
            pass
        return "{}"

    async def spawn_poll(self, sid: str) -> str:
        ent = self.procs[sid]
        out, err = "".join(ent["out"]), "".join(ent["err"])
        ent["out"].clear()
        ent["err"].clear()
        return json.dumps({"out": out, "err": err, "exited": ent["done"], "code": ent["code"]}, ensure_ascii=False)

    async def spawn_kill(self, payload: str) -> str:
        d = json.loads(payload)
        ent = self.procs.get(str(d["id"]))
        if ent and not ent["done"]:
            ent["p"].terminate()
        return "{}"


# ---------- script-mates ----------
class T:
    page = None
    console: list = []
    bridge: Bridge = None
    n = 0


async def js(expr, arg=None):
    return await T.page.evaluate(expr, arg)


async def wait_idle(timeout=90):
    await T.page.wait_for_function(
        "() => { const e = window.__plugin && window.__plugin.engine; return !!e && !e.current && !e.queue.length && !e.side.size; }",
        timeout=timeout * 1000, polling=100)
    await T.page.wait_for_timeout(250)


async def shot(name, full_panel=False, selector=".mod-right-split"):
    T.n += 1
    path = SHOTS / f"{T.n:02d}-{name}.png"
    if full_panel:
        h = await js("() => { const v = document.querySelector('.vm-view'); return v ? v.scrollHeight : 900; }")
        await T.page.set_viewport_size({"width": 1400, "height": max(900, min(int(h) + 60, 4000))})
        await T.page.wait_for_timeout(150)
    await js("() => document.body.classList.add('vm-shot')")
    try:
        if selector:
            await T.page.locator(selector).screenshot(path=str(path))
        else:
            await T.page.screenshot(path=str(path))
    finally:
        await js("() => document.body.classList.remove('vm-shot')")
    if full_panel:
        await T.page.set_viewport_size({"width": 1400, "height": 900})
    return path


def btn(text, scope=".vm-view"):
    return T.page.locator(f"{scope} button").filter(has_text=re.compile("^" + re.escape(text)))


async def click(text, scope=".vm-view"):
    loc = btn(text, scope)
    await loc.first.wait_for(state="visible", timeout=15000)
    await loc.first.click()


async def tab(name):
    await T.page.locator(".vm-tab").filter(has_text=name).first.click()
    await T.page.wait_for_timeout(150)


async def ui():
    return json.loads((VAULT / ".system" / "ui.json").read_text(encoding="utf-8"))


async def notices():
    return await js("() => window.__notices.slice()")


async def last_notice_with(sub, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for n in reversed(await notices()):
            if sub in n:
                return n
        await T.page.wait_for_timeout(200)
    raise AssertionError(f"no notice «{sub}». They were.: {(await notices())[-6:]}")


def fm_of(rel):
    raw, _ = split_fm((VAULT / rel).read_text(encoding="utf-8"))
    return yaml.safe_load(raw) or {}


async def modal():
    loc = T.page.locator(".modal-container .modal").last
    await loc.wait_for(state="visible", timeout=15000)
    return loc


def sitem(label, scope=".vm-settings"):
    """Settings by exact name."""
    return T.page.locator(f"{scope} .setting-item").filter(
        has=T.page.locator(".setting-item-name", has_text=re.compile("^" + re.escape(label) + "$"))).first


async def set_tab(name):
    await T.page.locator(".vm-settings .vm-set-tab").filter(has_text=re.compile("^" + re.escape(name) + "$")).click()
    await T.page.wait_for_timeout(250)


async def open_settings(tab_id="main"):
    """The settings window on the tab (main, models, thresholds, input, docs, costs, advanced) — panel-like."""
    await js(f"() => window.__plugin.openSettings('{tab_id}')")
    await T.page.wait_for_selector(".vm-settings .vm-set-tab.is-active", timeout=10000)
    await T.page.wait_for_function(
        "() => { const b = document.querySelector('.vm-settings .vm-set-body');"
        " return b && !b.textContent.includes('Downloading program settings') && b.querySelectorAll('.vm-sec').length > 0; }",
        timeout=30000)
    await wait_idle()


async def wait_saved():
    """The settings are saved through ~1 post-edit."""
    await T.page.wait_for_timeout(1400)
    await wait_idle()


def settings_yaml():
    return yaml.safe_load((PROG / "settings.yaml").read_text(encoding="utf-8"))


def profile_of(st, pid):
    return next((p for p in (st.get("llm") or {}).get("profiles") or [] if p.get("id") == pid), None)


def plugin_data():
    return json.loads((PLUGIN_DIR / "data.json").read_text(encoding="utf-8"))


async def choice(timeout=30):
    """Choice window: program in the middle of the launch, update, restart."""
    loc = T.page.locator(".modal-container .modal").filter(has=T.page.locator(".vm-choice")).last
    await loc.wait_for(state="visible", timeout=timeout * 1000)
    return loc


async def choose(m, label):
    await m.locator(".vm-modal-buttons button").filter(has_text=re.compile("^" + re.escape(label) + "$")).click()
    await T.page.wait_for_timeout(250)


async def os_notices():
    return await js("() => window.__osNotices.slice()")


async def calls():
    return await js("() => window.__calls.slice()")


def staging_txt():
    return sorted((VAULT / "_staging").glob("*.txt"))


# ---------- «GitHub» check for update ----------
class GH:
    files: dict = {}
    seen: list = []


class GHHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        GH.seen.append(self.path)
        code, body, ctype = GH.files.get(self.path, (404, b'{"message": "Not Found"}', "application/json"))
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_github():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), GHHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def release_zip(version: str) -> bytes:
    """Archives «version»: folder prog version-numbered (and, and the plugin)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in ("brain", "prompts", "plugin"):
            for f in sorted((PROG / d).rglob("*")):
                if not f.is_file() or "__pycache__" in f.parts or "_former" in f.parts:
                    continue
                rel = f.relative_to(PROG).as_posix()
                data = f.read_bytes()
                if rel == "brain/__init__.py":
                    data = re.sub(rb'__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"'.encode(), data)
                elif rel == "plugin/manifest.json":
                    m = json.loads(data.decode("utf-8"))
                    m["version"] = version
                    data = json.dumps(m, ensure_ascii=False, indent=2).encode("utf-8")
                z.writestr(f"Second Brain/{rel}", data)
    return buf.getvalue()


# ---------- v2.7: jelly-fish (llama.cpp) ----------
async def llama_flow():
    """Launch parameters window, modelling and llama.cpp (imitation Hugging Face and GitHub), server-launch
    (fake llama-server), The server address itself fits into the settings., «Stop it.»."""
    page = T.page
    for d in (APP / "tests", APP):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
    from fake_llama import FakeHub, free_port
    from brain import llama as L
    model = bytes(range(256)) * 8192 + b"gguf-tail" * 500  # ~2 MB instead of 6,9 GB
    hub = FakeHub(L.MODEL["repo"], L.MODEL["file"], model, L.plat()[1])
    port = free_port()
    keys = {"BRAIN_HF_BASE": hub.url, "BRAIN_LLAMA_API": hub.url + "/gh", "BRAIN_LLAMA_NO_SYSTEM": "1", "FAKE_LLAMA_LOAD_SEC": "1",
            "BRAIN_TEST_HW": json.dumps({"ram_gb": 12, "ram_free_gb": 7.5, "cores": 8, "threads": 16, "cpu": "Test processor",
                                         "gpus": [{"name": "NVIDIA GeForce RTX 3060", "vram_gb": 12, "vendor": "nvidia"}], "nvidia": True})}
    EXTRA_ENV.update(keys)
    box = page.locator(".vm-settings .vm-llama-box")
    try:
        await set_tab("General")  # tab: The state of the model is reread with imitation
        await set_tab("Models")
        await page.wait_for_function("() => (document.querySelector('.vm-settings .vm-llama-box') || {}).textContent?.includes('server:')",
                                     timeout=20000)
        txt = await box.inner_text()
        ok("not downloaded" in txt and "llama.cpp: not downloaded" in txt and "server: not running" in txt,
           "«Where to count: on this computer» — block «Your model»: model llama.cpp flat-loaded, server not running")
        await box.locator("button", has_text="Start model…").click()
        m = await modal()
        await page.wait_for_selector(".vm-llama .vm-llama-hw-grid", timeout=20000)
        t = await m.inner_text()
        ok("Start embedding model" in t and "12 GB" in t and "RTX 3060" in t and "8 cores" in t,
           "window: processor, computer memory")
        ram = m.locator(".vm-llama-ram")
        ok("is-bad" in (await ram.get_attribute("class") or "") and "16 GB" in await ram.inner_text(),
           "processor-wise 12 GB memory — red-warning «minimum 16 GB»")
        plan = await m.locator(".vm-llama-plan").inner_text()
        ok("Will be downloaded once:" in plan and "KaLM" in plan and "llama.cpp" in plan, "window-wise — downloadable (model llama.cpp)")
        await sitem("Run on", ".vm-llama").locator("select").select_option("gpu")
        await page.wait_for_timeout(200)
        ok(await m.locator(".vm-llama-ram").count() == 0 and await sitem("Model layers on GPU", ".vm-llama").count() == 1
           and await sitem("llama.cpp build", ".vm-llama").count() == 1,
           "«Video card» — warning 16 GB is not, build llama.cpp and layers on the video card")
        await shot("model-window-videocard", selector=".modal.vm-llama-modal")
        await sitem("Run on", ".vm-llama").locator("select").select_option("cpu")
        await page.wait_for_timeout(200)
        csel = sitem("Context", ".vm-llama").locator("select")
        ok(await csel.input_value() == "4096" and "8.4 GB" in await csel.locator("option[value='4096']").inner_text()
           and "9.6 GB" in await csel.locator("option[value='8192']").inner_text(),
           "default 4096; every option — How much memory does the model take?")
        await csel.select_option("8192")
        await page.wait_for_timeout(200)
        ok("at a context of 8,192, the model needs about 9.6 GB" in (await m.locator(".vm-llama-ram").inner_text()).replace("\u00a0", " "),
           "The memory card was recalculated to the selected context")
        await sitem("KV cache quantization", ".vm-llama").locator("select").select_option("q8_0")
        await sitem("CPU threads", ".vm-llama").locator("button", has_text="Use core count").click()
        ok(await sitem("CPU threads", ".vm-llama").locator("input").input_value() == "8", "«Use core count» — 8 flow")
        await sitem("Port", ".vm-llama").locator("input").fill(str(port))
        await page.wait_for_timeout(200)
        ok(f"http://127.0.0.1:{port}/v1" in await m.inner_text(), "window-wise — future server address")
        await shot("model-window-launch", selector=".modal.vm-llama-modal")
        await m.locator(".vm-modal-buttons button", has_text=re.compile("^Start$")).click()
        live = page.locator(".vm-settings .vm-llama-live:not(.vm-hidden)")
        await live.wait_for(state="visible", timeout=15000)
        ok(await live.locator("button", has_text="Stop").count() == 1, "The launch course is visible directly in the settings, eat «Stop.»")
        n = await last_notice_with("Model running:", 120)
        ok(f"127.0.0.1:{port}/v1" in n and "Address saved" in n, f"notice: {n}")
        await wait_idle()
        emb = settings_yaml()["embeddings"]
        srv = emb.get("server") or {}
        ok(emb["base_url"] == f"http://127.0.0.1:{port}/v1" and srv.get("ctx") == 8192 and srv.get("kv_cache") == "q8_0"
           and srv.get("threads") == 8 and srv.get("port") == port and srv.get("device") == "cpu",
           "server address and launch parameters are inscribed in settings.yaml")
        await page.wait_for_function(
            "(u) => { const it = [...document.querySelectorAll('.vm-settings .setting-item')].find((s) => "
            "s.querySelector('.setting-item-name')?.textContent === 'Server address'); return !!it && it.querySelector('input')?.value === u; }",
            arg=f"http://127.0.0.1:{port}/v1", timeout=20000)
        ok(True, "field «Server address» In the open settings updated itself")
        await page.wait_for_function("() => (document.querySelector('.vm-settings .vm-llama-box') || {}).textContent?.includes('server: running')",
                                     timeout=20000)
        txt = await box.inner_text()
        ok("downloaded" in txt and f"127.0.0.1:{port}/v1 (CPU)" in txt and "(b9999)" in txt,
           "block «Your model»: downloader, llama.cpp eat, server")
        args = json.loads(re.search(r"FAKE ARGS: (.*)", (PROG / "llama.cpp" / "server.log").read_text(encoding="utf-8")).group(1))
        pairs = {a: args[i + 1] for i, a in enumerate(args[:-1])}
        ok(pairs.get("-c") == "8192" and pairs.get("-b") == "8192" and pairs.get("-ub") == "8192" and pairs.get("-ctk") == "q8_0"
           and pairs.get("-t") == "8" and pairs.get("--port") == str(port) and "--embedding" in args,
           f"llama-server launched with selected parameters (packet = contextually): {' '.join(args)}")
        ok((PROG / "models" / L.MODEL["file"]).read_bytes() == model, "file-up models programme")
        await box.scroll_into_view_if_needed()
        await shot("model-into-setting", selector=".modal")
        await box.locator("button", has_text="Stop").click()
        await last_notice_with("stopped", 30)
        await page.wait_for_function("() => (document.querySelector('.vm-settings .vm-llama-box') || {}).textContent?.includes('server: not running')",
                                     timeout=20000)
        ok("automatically" in await box.inner_text(), "«Stop it.» — server; launch, whenever necessary")
    finally:
        subprocess.run([str(PROG / ".venv" / "bin" / "python"), "-X", "utf8", "-m", "brain", "llama", "stop"], cwd=PROG,
                       capture_output=True, text=True, env=env(), timeout=60)
        hub.close()
        for k in keys:
            EXTRA_ENV.pop(k, None)


# ---------- scripture ----------
async def scenario():
    page = T.page
    step("1. Launching the plugin: panel, first-loader")
    await page.goto(ORIGIN + "harness.html")
    await js("() => window.__boot()")
    await page.wait_for_selector(".vm-view .vm-wizard", timeout=30000)
    await wait_idle()
    await page.wait_for_selector(".vm-step.is-done", timeout=10000)
    ok(await page.locator(".vm-step.is-done").count() == 1, "master: step «Put the notes together.» done (file _staging eat)")
    ok("Phase 1" in await page.locator(".vm-step.is-current .vm-step-title").inner_text(), "master: step-by-step — Phase 1")
    ok((VAULT / ".system" / "ui.json").exists(), "snapshot .system/ui.json team-building snapshot")
    ok("Second Brain" in await page.locator(".status-bar").inner_text(), "in the status line «Second Brain»")
    ok(json.loads((PLUGIN_DIR / "data.json").read_text(encoding="utf-8")).get("welcomed") is True, "first opening remembered (welcomed)")
    await shot("master", full_panel=True)

    step("2. Phase 1 → draft")
    EXTRA_ENV["FAKE_DELAY"] = "5"
    await click("Start Phase 1")
    await page.wait_for_selector(".vm-run.is-on .vm-run-label", timeout=10000)
    await page.wait_for_function(
        "() => { const w = document.querySelector('.vm-run-wait');"
        " return w && !w.classList.contains('vm-hidden') && w.textContent.includes('Were waiting for the model to respond.'); }",
        timeout=40000, polling=100)
    ok("Phase 1" in await page.locator(".vm-run-label").inner_text(), "The current launch block shows «Phase 1»")
    wt = await page.locator(".vm-run-wait").inner_text()
    ok("Were waiting for the model to respond." in wt and "Structure" in wt, f"while the model is — wait-counter: «{wt}»")
    ok(await page.locator(".vm-run-time").inner_text() != "", "launch time")
    ok(await page.locator(".vm-run-line").inner_text() != "", "The progress line shows the output of the program")
    await page.wait_for_function("() => document.querySelector('.status-bar').textContent.includes('waiting for an answer')", timeout=10000, polling=100)
    sb = await page.locator(".status-bar").inner_text()
    ok("Phase 1" in sb, f"status-line: «{sb}»")
    await shot("its-phase-1")
    await wait_idle()
    EXTRA_ENV.pop("FAKE_DELAY")
    u = await ui()
    ok(u["status"]["structure_pending"] and u["status"]["draft"], "draft structure awaits approval")
    await last_notice_with("Phase 1:")
    ok("Review and approve the draft" in await page.locator(".vm-step.is-current .vm-step-title").inner_text(), "master: step-by-step — drafting")
    await shot("draft", full_panel=True)
    await click("Open draft")
    await page.wait_for_timeout(400)
    ok("Structure approved" in await page.locator(".mod-root pre.vm-test-file").inner_text(), "The draft opened in the editor")

    step("3. Approval of the structure from the panel")
    await click("Approve structure")
    m = await modal()
    ok("Approve structure?" in await m.inner_text(), "ask for")
    await shot("confirmation", selector=None)
    await click("Approve and continue", ".modal")
    await page.wait_for_timeout(300)
    await wait_idle(120)
    u = await ui()
    ok(u["status"]["approved_once"] and not u["status"]["structure_pending"], "structure approved, draft applied")
    ok(any(c[0] == "MarkdownView.save" for c in await js("() => window.__calls")), "open draft retained before approval")
    ok(len(u["containers"]) >= 4, f"containers created: {', '.join(c['title'] for c in u['containers'])}")
    ok(await page.locator(".vm-tree-row").count() == len(u["containers"]), "panel-wood")
    ok(await page.locator(".vm-wizard").count() == 0, "Master Hidden After Approval")
    ok(u["status"]["questions"] > 0 and await page.locator(".vm-tab .vm-badge").count() == 1, f"questions: {u['status']['questions']}, tab")
    await shot("survey", full_panel=True)

    step("4. Questions: free-response")
    await tab("Questions")
    cards = page.locator(".vm-q")
    ok(await cards.count() == len(u["questions"]), "All open questions are shown with cards")
    await shot("questions", full_panel=True)
    q_opt = next((q for q in u["questions"] if q["options"]), None)
    ok(q_opt is not None, f"I have a question about options. ({q_opt and q_opt['id']})")
    card = page.locator(".vm-q").filter(has=page.locator(".vm-q-meta", has_text=re.compile("^" + q_opt["id"] + r"\b")))
    await card.locator(".vm-q-option").first.click()
    await wait_idle()
    await last_notice_with(f"Answer {q_opt['id']} accepted")
    u2 = await ui()
    ok(all(q["id"] != q_opt["id"] for q in u2["questions"]), f"{q_opt['id']}: reply, question gone")
    q_free = next((q for q in u2["questions"] if q["free_text"] and not q["options"]), None) or next((q for q in u2["questions"] if q["free_text"]), None)
    if q_free:
        card = page.locator(".vm-q").filter(has=page.locator(".vm-q-meta", has_text=re.compile("^" + q_free["id"] + r"\b")))
        await card.locator("textarea").fill("Photo from the dacha 2010 year-end, I want to digitize")
        await card.locator("button", has_text="Reply").click()
        await wait_idle()
        u3 = await ui()
        gone = all(q["id"] != q_free["id"] for q in u3["questions"])
        note = next((q.get("note") for q in u3["questions"] if q["id"] == q_free["id"]), None)
        ok(gone or note, f"{q_free['id']}: free-riding {'accepted' if gone else 'not accepted with explanation: ' + str(note)}")

    step("5. Container: card, threshold")
    await tab("Overview")
    meteo = next(c for c in (await ui())["containers"] if c["title"] == "weather station")
    await page.locator(".vm-tree-row").filter(has_text="weather station").first.click()
    await page.wait_for_selector(".vm-chead-title", timeout=5000)
    ok("weather station" in await page.locator(".vm-chead-title").inner_text(), "Clicking in the tree opened a container Meteo station")
    ok(await page.locator(".vm-thr-row").count() >= 3, "threshold table")
    await shot("container", full_panel=True)
    u = await ui()
    info = u["threshold_info"]
    names = [k for k, v in info.items() if v["per_container"] and k != "seed_dormancy_days"]
    k0 = "classification" if "classification" in names else names[0]
    row = page.locator(".vm-thr-row").filter(has=page.locator(".vm-thr-label", has_text=info[k0]["label"])).first
    inp = row.locator("input.vm-thr-input")
    rng = row.locator("input.vm-thr-range")
    eff = meteo["thresholds"][k0]["value"]
    ok(await inp.get_attribute("placeholder") == str(eff), f"field «{info[k0]['label']}» grey — operative {eff}")
    ok(await rng.input_value() == str(eff) and await row.locator(".vm-thr-src").inner_text() == "global",
       f"slider stands on the current value ({eff}), source — «general»")
    trs = row.locator(".vm-thr-reset")
    ok(await trs.is_visible() and await trs.is_disabled() and "vm-reset-off" in (await trs.get_attribute("class")),
       "Theres no threshold — ↺ spot-on, but dim and unpressed")
    rb0 = await rng.bounding_box()
    await rng.evaluate("(r) => { r.value = '42'; r.dispatchEvent(new Event('input', { bubbles: true })); }")
    ok(await inp.input_value() == "42" and await row.locator(".vm-thr-src").inner_text() == "custom, unsaved"
       and await trs.is_visible() and not await trs.is_disabled(), "slipper 42 field: «his, unsaved», ↺ active")
    rb1 = await rng.bounding_box()
    ok(rb0 and rb1 and abs(rb0["x"] - rb1["x"]) < 0.5 and abs(rb0["width"] - rb1["width"]) < 0.5,
       "The slider didnt move or shrink., when ↺ became active")
    await row.locator(".vm-thr-reset").click()
    ok(await inp.input_value() == "" and await row.locator(".vm-thr-src").inner_text() == "global"
       and (await btn("Save").first.inner_text()).strip() == "Save", "↺ cleared his threshold — again «general», keep")
    await inp.fill("abc")
    ok("vm-invalid" in (await inp.get_attribute("class")) and await btn("Save").first.is_disabled(), "misrepresentation, «Save» idle")
    newv = 80 if eff != 80 else 75
    await inp.fill(str(newv))
    ok((await btn("Save").first.inner_text()).strip() == "Save (1)", "The button shows the number of changes")
    await btn("Save").first.click()
    await wait_idle()
    fm = fm_of(meteo["path"])
    ok(fm.get("thresholds", {}).get(k0) == newv, f"threshold YAML container: thresholds.{k0} = {newv}")
    ok(fm.get("type") == "project" and "id" in fm, "field YAML containers preserved")
    await page.wait_for_timeout(300)
    row = page.locator(".vm-thr-row").filter(has=page.locator(".vm-thr-label", has_text=info[k0]["label"])).first
    ok("is-own" in (await row.get_attribute("class")) and (await row.locator(".vm-thr-src").inner_text()) == "custom", "after preservation, the threshold is marked «his»")
    child = next((c for c in u["containers"] if c.get("parent") == meteo["id"]), None)
    parent = next((c for c in u["containers"] if c["id"] == meteo.get("parent")), None)
    if parent:
        await page.locator(".vm-cbar select").select_option(parent["id"])
        await page.wait_for_timeout(300)
        await page.locator(".vm-cbar select").select_option(meteo["id"])
        await page.wait_for_timeout(300)
    u = await ui()
    meteo = next(c for c in u["containers"] if c["title"] == "weather station")
    ok(meteo["thresholds"][k0]["value"] == newv and meteo["thresholds"][k0]["source"] == "own", "The program sees its container threshold (snapshot)")
    if child:
        ch = next(c for c in u["containers"] if c["id"] == child["id"])
        ok(ch["thresholds"][k0]["source"] == "parent", f"nested «{ch['title']}» inheriting the threshold from the weather station")
    await shot("threshold-preserved", full_panel=True)

    step("6. AI Council on Thresholds")
    await click("Consult AI")
    m = await modal()
    await page.wait_for_selector(".modal .vm-rec, .modal .vm-callout", timeout=60000)
    await wait_idle()
    recs = page.locator(".modal .vm-rec")
    nrec = await recs.count()
    ok(nrec >= 1, f"counsel: recommendations {nrec}")
    ok((await page.locator(".modal .vm-advice-summary").inner_text()).strip() != "", "The general conclusion of the model")
    await shot("council-ooze", selector=None)
    first_label = await recs.first.locator(".vm-rec-label").inner_text()
    first_new = await recs.first.locator(".vm-rec-new").inner_text()
    if nrec > 1:
        await recs.nth(1).locator("input[type=checkbox]").click()
        ok("is-off" in (await recs.nth(1).get_attribute("class")), "The second recommendation can be removed")
    await page.locator(".modal button", has_text="Apply selected").click()
    await wait_idle()
    await last_notice_with("updated")
    fm = fm_of(meteo["path"])
    applied = [k for k, v in (fm.get("thresholds") or {}).items() if str(v) == first_new]
    ok(applied, f"applied: {first_label} → {first_new} (into YAML: {fm.get('thresholds')})")
    ok(await page.locator(".modal-container").count() == 0, "council window closed")

    step("7. Document Style and Phase 2")
    await page.locator("textarea.vm-style").fill("Write like a business-plan, with figures and deadlines.")
    await click("Save style")
    await wait_idle()
    ok(fm_of(meteo["path"]).get("style") == "Write like a business-plan, with figures and deadlines.", "style YAML container")
    await click("Write documents (Phase 2)")
    await page.wait_for_timeout(300)
    await wait_idle(120)
    await last_notice_with("Phase 2 · weather station")
    await page.wait_for_selector(".vm-doc", timeout=10000)
    ok(await page.locator(".vm-doc").count() >= 1, f"Documents appear on the card: {await page.locator('.vm-doc').count()}")
    u = await ui()
    meteo = next(c for c in u["containers"] if c["title"] == "weather station")
    doc = (VAULT / meteo["products"][0]["path"]).read_text(encoding="utf-8")
    ok("business-plan" in doc, "Container style is included in the document")
    await click("Update documents (Phase 2)")
    m = await modal()
    ok("Documents are up to date" in await m.inner_text(), "re-phase 2 changeless — ask, rewrite")
    await page.locator(".modal button", has_text="Cancel").click()
    await page.wait_for_timeout(300)
    await page.locator(".vm-doc .vm-link").first.click()
    await page.wait_for_timeout(400)
    ok(meteo["products"][0]["title"] in (await page.locator(".mod-root .view-header-title").inner_text()), "document opens by click")
    await shot("document", full_panel=True)

    step("8. Container status from the panel")
    sel = page.locator(".vm-cmeta select").nth(1)
    await sel.select_option("dormant")
    await wait_idle()
    ok(fm_of(meteo["path"]).get("container_status") == "dormant", "status «frozen» recorded YAML")
    await last_notice_with("status: frozen")
    await page.locator(".vm-cmeta select").nth(1).select_option("active")
    await wait_idle()
    ok(fm_of(meteo["path"]).get("container_status") == "active", "status returned")

    step("9. New thought")
    await tab("Overview")
    await click("New thought")
    m = await modal()
    ok(not await m.locator("#vm-now").is_checked(), "flag «Handle it right away. (Phase 1)» default off")
    await m.locator("textarea").fill("Buy a watering pot with a long nose for a greenhouse.")
    n0 = len(T.bridge.runs)
    await m.locator("button", has_text="Save").click()
    n = await last_notice_with("Thought saved")
    ok("_staging/" in n and "next Phase 1" in n, f"flagless thought awaits the next phase 1: {n}")
    await page.wait_for_timeout(800)
    ok(not any("phase1" in e["args"] for e in T.bridge.runs[n0:]), "flagless Phase 1 never-started")
    ok(any("watering pot" in p.read_text(encoding="utf-8") for p in (VAULT / "_staging").glob("*.txt")), "thought-file _staging")
    await click("New thought")
    m = await modal()
    await m.locator("textarea").fill("Weather station needs a second sensor — Buy on the weekend and check on the balcony.")
    await m.locator("#vm-hint").fill("weather station")
    await m.locator("#vm-now").check()
    await shot("new-thought", selector=None)
    await m.locator("button", has_text="Save").click()
    n = await last_notice_with("Processing now")
    ok("Thought saved: _staging/" in n and "Weather station" in n, f"flaged — phase 1: {n}")
    await page.wait_for_timeout(300)
    await wait_idle(120)
    src = [p for p in (VAULT / "_sources").glob("*.txt") if "Weather station needs a second sensor" in p.read_text(encoding="utf-8")]
    ok(src and "mode: steady_state" in src[0].read_text(encoding="utf-8") and "hint: weather station" in src[0].read_text(encoding="utf-8"),
       "thought processed by Phase 1 (spring-head hint and mode)")
    ok(any("watering pot" in p.read_text(encoding="utf-8") for p in (VAULT / "_sources").glob("*.txt")),
       "The delayed thought is processed in the same phase 1")

    step("10. Settings: tab, search, slider, model profile, step-model")
    await page.locator(".vm-head-tools .vm-icon-btn").nth(1).click()
    await page.wait_for_selector(".vm-settings .vm-set-tab", timeout=10000)
    await page.wait_for_function(
        "() => [...document.querySelectorAll('.vm-settings .setting-item-heading .setting-item-name')].some(e => e.textContent === 'Updates')",
        timeout=30000)
    await wait_idle()
    tabs = [t.strip() for t in await page.locator(".vm-settings .vm-set-tab").all_inner_texts()]
    ok(tabs == ["General", "Models", "Thresholds", "Incoming", "Documents", "Expenses", "Advanced"], "settings: " + ", ".join(tabs))
    heads = await page.locator(".vm-settings .setting-item-heading .setting-item-name").all_inner_texts()
    ok(all(h in heads for h in ("Program", "Windows notifications", "Updates")) and "Warehouse" not in heads,
       "tab «Basic.»: " + ", ".join(heads))
    navs = [t.strip() for t in await page.locator(".mod-settings .vertical-tab-header .vertical-tab-nav-item").all_inner_texts()]
    ok(navs == ["Second Brain"] and await page.locator(".mod-settings .vertical-tab-nav-item.is-active").count() == 1,
       f"point «Second Brain» left-handed: {navs}")
    ok("Program found" in await page.locator(".vm-settings .vm-callout").first.inner_text(), "section «Programme»: program found")
    await shot("setting", selector=".modal")
    r = subprocess.run([str(PROG / ".venv/bin/python"), "-X", "utf8", "-m", "brain", "--json", "settings"], cwd=PROG,
                       capture_output=True, text=True, env=env(), timeout=60)
    sres = json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("@@RESULT ")][-1][9:])
    fields = {f["key"]: f for sec in sres["settings"]["schema"] for f in sec["fields"]}
    nf = fields["thresholds.classification"]
    defv = sres["settings"]["defaults"]["thresholds"]["classification"]
    await set_tab("Thresholds")
    ok("is-active" in await page.locator(".vm-set-tab", has_text="Thresholds").get_attribute("class"), "tab «Thresholds» open-mindedly")
    item = sitem(nf["label"])
    num, rng = item.locator("input.vm-num"), item.locator("input.vm-set-range")
    cur = await num.input_value()
    ok(await rng.count() == 1 and await rng.input_value() == cur == str(defv), f"«{nf['label']}»: slider and field ({cur})")
    rs = item.locator(".vm-reset")
    rcls = await rs.get_attribute("class") or ""
    ok(await rs.is_visible() and "vm-reset-off" in rcls and "is-disabled" in rcls and await rs.get_attribute("aria-disabled") == "true",
       "default — ↺ spot-on, but dim and inactive")
    sb0 = await rng.bounding_box()
    await num.fill(str(nf["min"] - 1))
    await page.wait_for_timeout(200)
    ok("vm-invalid" in (await num.get_attribute("class")) and "Enter a valid" in await item.locator(".vm-field-error").inner_text(),
       f"«{nf['label']}»: scoring")
    await rng.evaluate("(r) => { r.value = '77'; r.dispatchEvent(new Event('input', { bubbles: true })); }")
    ok(await num.input_value() == "77" and "vm-invalid" not in (await num.get_attribute("class")), "slipper 77 field")
    ok(await rs.is_visible() and "vm-reset-off" not in (await rs.get_attribute("class") or "") and "vm-changed" in (await item.get_attribute("class")),
       "meaning is different from silence — ↺ she became active")
    sb1 = await rng.bounding_box()
    ok(sb0 and sb1 and abs(sb0["x"] - sb1["x"]) < 0.5 and abs(sb0["width"] - sb1["width"]) < 0.5,
       "The slider in the settings did not move, when ↺ became active")
    await wait_saved()
    await last_notice_with("Settings saved")
    ok(settings_yaml()["thresholds"]["classification"] == 77, "settings.yaml: thresholds.classification = 77")
    ok((PROG / "settings.yaml.bak").exists(), "former settings.yaml preserved .bak")
    ok((PROG / "settings.yaml").read_text(encoding="utf-8").count("#") > 10, "settings.yaml rewritten")
    await item.locator(".vm-reset").click()
    await wait_saved()
    ok(settings_yaml()["thresholds"]["classification"] == defv and await sitem(nf["label"]).locator("input.vm-num").input_value() == str(defv),
       f"↺ default ({defv})")
    rs = sitem(nf["label"]).locator(".vm-reset")
    ok(await rs.is_visible() and "vm-reset-off" in (await rs.get_attribute("class") or ""), "post-return ↺ stayed in place — dull")
    sf = fields["thresholds.duplicate_similarity"]  # similarity — scale 0–1: «86%» signifier 0,86
    snum = sitem(sf["label"]).locator("input.vm-num")
    await snum.fill("86%")
    await page.wait_for_timeout(200)
    ok("vm-invalid" not in (await snum.get_attribute("class")), f"«{sf['label']}»: «86%» accepted")
    await wait_saved()
    ok(settings_yaml()["thresholds"]["duplicate_similarity"] == 0.86, "settings.yaml: «86%» similarly written 0.86")
    await sitem(sf["label"]).locator(".vm-reset").click()
    await wait_saved()
    ok(settings_yaml()["thresholds"]["duplicate_similarity"] == sres["settings"]["defaults"]["thresholds"]["duplicate_similarity"],
       "↺ reverted to default")
    # tab-search
    search = page.locator(".vm-settings input.vm-set-search")
    await search.fill("budget")
    await page.wait_for_timeout(300)
    vis = ".vm-settings .vm-search-pane:not(.vm-hidden) .setting-item:not(.setting-item-heading):not(.vm-hidden)"
    names = await page.locator(vis + " .setting-item-name").all_inner_texts()
    infos = await page.locator(vis + " .setting-item-info").all_inner_texts()
    panes = await page.locator(".vm-settings .vm-search-pane:not(.vm-hidden) .vm-search-tab").all_inner_texts()
    ok("Monthly budget, $" in names and "expenses" in [x.lower() for x in panes] and all("budget" in t.lower() for t in infos),
       f"search «budget»: {', '.join(names)} (tab: {', '.join(panes)})")
    await shot("setting-search", selector=".modal")
    await search.fill("")
    await page.wait_for_timeout(300)
    ok((await page.locator(".vm-set-tab.is-active").inner_text()).strip() == "Thresholds" and await page.locator(".vm-search-pane").count() == 0,
       "cleansing — tab «Thresholds»")
    # model profile
    await set_tab("Models")
    await page.wait_for_selector(".vm-settings .vm-prof-editor", timeout=10000)
    ok(await sitem("Mode").locator("select").input_value() == "fake", "The old settings are saved (test-model)")
    opts = await sitem("Profile to edit").locator("select option").all_inner_texts()
    ok(len(opts) == 1 and "cloud" in opts[0], f"Old settings turned into a cloud profile: {opts}")
    ok(await page.locator(".vm-settings .vm-prof-box .setting-item-name", has_text=re.compile(r"^Input, \$ per million tokens$")).count() == 1,
       "cloud-based — price")
    await click("＋ Local", ".vm-settings")
    await page.wait_for_timeout(300)
    ptitle = await page.locator(".vm-settings .vm-prof-title").inner_text()
    ok("Local model" in ptitle and "local" in ptitle, f"Local profile created: «{ptitle}»")
    ok(await page.locator(".vm-settings .vm-prof-box .setting-item-name", has_text="Input, $").count() == 0,
       "There is no local pricing profile (tokens and time are considered)")
    await sitem("Model", ".vm-prof-box").locator("input").fill("qwen2.5-7b-instruct")
    await wait_saved()  # Automotive repairs should not be lost.
    await sitem("Request limit, characters", ".vm-prof-box").locator("input.vm-num").fill("40000")
    await wait_saved()
    loc = next((x for x in settings_yaml()["llm"]["profiles"] if x.get("kind") == "local"), None)
    ok(loc and loc["model"] == "qwen2.5-7b-instruct" and loc["max_input_chars"] == 40000 and loc["base_url"].startswith("http://127.0.0.1"),
       f"local profile is recorded in settings.yaml: {loc and loc.get('id')}")
    pid = loc["id"]
    role = page.locator(".vm-settings .setting-item.vm-role").filter(has=page.locator(".setting-item-name", has_text=re.compile("^Classification$"))).first
    await role.scroll_into_view_if_needed()
    rop = await role.locator("select option").all_inner_texts()
    ok(rop[0] == "Same as main model" and rop[-1] == "Manually via web chat" and len(rop) == 4, f"step-modeling: {', '.join(rop)}")
    await role.locator("select").select_option(pid)
    await wait_saved()
    ok(settings_yaml()["llm"]["roles"].get("Classification") == pid, f"step «Classification» profiled {pid} (settings.yaml)")
    await set_tab("General")
    await set_tab("Models")
    used = await page.locator(".vm-settings .vm-prof-box").inner_text()
    ok("steps: Classification" in used, "profiled, What steps are on him?")
    await page.locator(".vm-settings .vm-prof-editor").scroll_into_view_if_needed()
    await shot("setting-profiles", selector=".modal")
    role = page.locator(".vm-settings .setting-item.vm-role").filter(has=page.locator(".setting-item-name", has_text=re.compile("^Classification$"))).first
    await role.locator("select").select_option("")
    await wait_saved()
    ok(not (settings_yaml()["llm"].get("roles") or {}).get("Classification"), "The step is back to the main model — stripped settings.yaml")
    await sitem("Profile to edit").locator(".extra-setting-button").click()
    m = await modal()
    ok("Delete profile?" in await m.inner_text(), "profile-removal — confirmatory")
    await m.locator("button", has_text="Delete").click()
    await wait_saved()
    ok(not profile_of(settings_yaml(), pid) and profile_of(settings_yaml(), "p1"), "local profile removed, cloudy")
    # embedding: The fields depend on the chosen mode
    emb = sitem("Where to run")
    await emb.scroll_into_view_if_needed()
    price = page.locator(".vm-settings .setting-item-name", has_text="Price, $ per million tokens")
    ok(await price.count() == 0, "emblem-dinging in test mode: No cloud fields")
    await emb.locator("select").select_option("cloud")
    await page.wait_for_timeout(300)
    ok(await price.count() == 1 and await sitem("Address").count() == 0, "cloud-emblem: address API, key")
    await sitem("Where to run").locator("select").select_option("local")
    await page.wait_for_timeout(300)
    ok(await price.count() == 0 and await sitem("Server address").count() == 1, "local emblem: price, I have a server address.")
    await wait_saved()
    ok(settings_yaml()["embeddings"]["mode"] == "local", "embedding regimen recorded")
    await llama_flow()
    await js("() => window.__plugin.patchSettings({ embeddings: { mode: 'fake' } })")
    await wait_idle()
    ok(settings_yaml()["embeddings"]["mode"] == "fake", "embedding regimen returned (test-bed)")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    ok(await page.locator(".mod-settings").count() == 0, "settings window closed")

    step("11. Stop in the middle of the run")
    st = VAULT / "_staging"
    for i, t in enumerate(["The bakery needs a logo and a sign..", "Put a barrel on the dacha.", "weather station: check out, Is the sensor lying in the sun?.",
                           "For the bakery to calculate the payback for the year.", "Greenhouse insulated for autumn."]):
        (st / f"2024-05-0{i + 1} thought {i + 1}.txt").write_text(f"0{i + 1}.05.2024\nmode: steady_state\n\n{t}\n", encoding="utf-8")
    EXTRA_ENV["FAKE_DELAY"] = "1.0"
    await tab("Overview")
    await page.wait_for_timeout(200)
    await click("Phase 1: process")
    await page.wait_for_selector(".vm-run.is-on .vm-run-label", timeout=10000)
    await page.wait_for_function(
        "() => { const u = document.querySelector('.vm-run-usage'), b = document.querySelector('.vm-run .vm-bar'), s = document.querySelector('.vm-run-stage');"
        " return u && b && s && !u.classList.contains('vm-hidden') && u.textContent.includes('This launch') && !b.classList.contains('vm-hidden')"
        " && / from \\d/.test(s.textContent); }",
        timeout=30000, polling=100)
    stage = await page.locator(".vm-run-stage").inner_text()
    ok(re.search(r"\d+ from \d+", stage), f"number-stage: «{stage}»")
    ok(True, "on the move: progress-line — «" + await page.locator(".vm-run-usage").inner_text() + "»")
    await page.wait_for_function("() => / \\d+ from \\d+ /.test(document.querySelector('.status-bar').textContent)", timeout=5000, polling=100)
    ok(True, "status-line: «" + await page.locator(".status-bar").inner_text() + "»")
    await shot("its-run-through")
    await click("Stop", ".vm-run")
    await page.wait_for_selector(".vm-run-note", timeout=5000)
    ok(any(c[0] == "writeFileSync" and c[1].endswith(".system/stop") for c in await calls()), "«Stop.» file-write .system/stop")
    await shot("stop")
    await wait_idle(120)
    EXTRA_ENV.pop("FAKE_DELAY")
    n = await last_notice_with("Phase 1")
    jst = await js("() => window.__plugin.engine.history.find(j => j.args[0] === 'run').status")
    ok(jst in ("stopped", "done"), f"run-off (status {jst}); notice: {n}")
    ok(not (VAULT / ".system" / "stop").exists(), "file stop flattened")
    await click("Phase 1: process")
    await page.wait_for_timeout(300)
    await wait_idle(120)
    ok(not staging_txt(), "The next launch completed everything.")

    step("12. Expenses: summary, profile, counting, budget")
    await tab("Expenses")
    await page.wait_for_selector(".vm-usage-total", timeout=10000)
    u = await ui()
    ok(u["usage"]["totals"]["all"]["calls"] > 0, f"time-to-time: {u['usage']['totals']['all']['calls']}")
    seg = await page.locator(".vm-seg-btn").all_inner_texts()
    ok(seg == ["Today", "This month", "Last month", "All time"], "period: " + ", ".join(seg))
    card = page.locator(".vm-prof").filter(has=page.locator(".vm-prof-name", has_text="Z.ai · fake")).first
    ok("not set" in await card.locator(".vm-prices-title").inner_text(), "The cloud profile has no pricing — cost is not considered")
    ok(await page.locator(".vm-usage-total .vm-warn-line").count() == 1, "warning: circulations without value")
    ok(await page.locator(".vm-usage-total .vm-usage-cell").count() == 4, "result: circulation, entry-exit tokens, modelling")
    ok(await page.locator(".vm-chart-col").count() >= 7 and await page.locator(".vm-urun").count() >= 3, "Day schedule and latest launches")
    await shot("expense-without-price", full_panel=True)
    pin = card.locator(".vm-prices input")
    await pin.nth(0).fill("2")
    await pin.nth(2).fill("8")
    await card.locator("button", has_text="Save").click()
    m = await modal()
    ok("Recalculate past requests?" in await m.inner_text(), "post-price — questioning")
    await m.locator("button", has_text="Recalculate").click()
    await wait_idle()
    await last_notice_with("Cost recalculated")
    pr = profile_of(settings_yaml(), "p1")["prices"]
    ok(pr["input"] == 2 and pr["output"] == 8 and pr["cached_input"] is None, f"prices are recorded in settings.yaml: {pr}")
    await page.wait_for_timeout(400)
    u = await ui()
    tot = u["usage"]["totals"]["all"]
    ok(tot["cost"] > 0 and not tot["unpriced"], f"past appeals recounted: ${tot['cost']:.4f}, costless — 0")
    ok(await page.locator(".vm-usage-total .vm-warn-line").count() == 0 and "$" in await page.locator(".vm-usage-money").inner_text(),
       "brief — money: " + await page.locator(".vm-usage-money").inner_text())
    binp = page.locator(".vm-inline-form input.vm-num")
    await binp.fill("0.0001")
    await page.locator(".vm-inline-form button", has_text="Save").click()
    await wait_idle()
    await last_notice_with("Monthly budget")
    ok(settings_yaml()["budget"]["monthly_usd"] == 0.0001, "budget of the month is recorded settings.yaml")
    await page.wait_for_selector(".vm-usage-view .vm-budget.is-over, .vm-budget.is-over", timeout=10000)
    ok(True, "budget-strip — overstepped")
    await shot("expense", full_panel=True)
    await tab("Overview")
    cur = await page.locator(".vm-current").inner_text()
    ok("Z.ai · fake" in cur and await page.locator(".vm-current .vm-budget.is-over").count() == 1, "into «Overview» — current-model, monthly expenditure")

    step("13. Budget exhausted: The program asks in the middle of the launch")
    await js("() => { window.__focus = false; }")  # Obsidian folded — notice Windows come
    (VAULT / "_staging" / "2024-06-01 sensor.txt").write_text("01.06.2024\nmode: steady_state\n\nBuy a second sensor for the weather station.\n", encoding="utf-8")
    n0 = len(await os_notices())
    await click("Phase 1: process")
    m = await choice(60)
    ok("Budget exhausted" in await m.locator(".modal-title").inner_text(), "mid-launch — window «Budget exhausted»")
    btns = await m.locator(".vm-modal-buttons button").all_inner_texts()
    ok(btns == ["Continue until the end of this launch", "Stop"], "variant: " + " / ".join(btns))
    await page.wait_for_timeout(1100)
    ok("awaiting your answer" in await page.locator(".status-bar").inner_text(), "status-line: awaiting your answer")
    ok(await page.locator(".vm-run-ask:not(.vm-hidden)").count() == 1, "panel: program awaits a response")
    osn = (await os_notices())[n0:]
    ok(any(x["title"] == "Second Brain is waiting for an answer" and "Budget exhausted" in x["body"] for x in osn), f"notice Windows: {osn}")
    await shot("budget-question", selector=None)
    await choose(m, "Stop")
    await wait_idle(120)
    n = await last_notice_with("stopped: spent")
    ok("budget" in n, f"budgeted: {n[:90]}…")
    job = await js("() => { const j = window.__plugin.engine.history.find(j => j.args[0] === 'run'); return { status: j.status, r: j.result }; }")
    ok(job["r"].get("budget_stop") and job["status"] in ("stopped", "failed"), f"launch: budget_stop (status {job['status']})")
    await click("Phase 1: process")
    m = await choice(60)
    await choose(m, "Continue until the end of this launch")
    await wait_idle(120)
    await last_notice_with("Phase 1: ready")
    ok(not staging_txt(), "«Continue until the end of this launch» — record-work")
    await tab("Expenses")
    await page.locator(".vm-inline-form input.vm-num").fill("")
    await page.locator(".vm-inline-form button", has_text="Save").click()
    await wait_idle()
    await last_notice_with("Budget removed")
    ok(settings_yaml()["budget"]["monthly_usd"] is None, "budget")

    step("14. Evaluation before a big launch; notice Windows finishing")
    await open_settings("costs")
    await sitem("If calls exceed").locator("input.vm-num").fill("1")
    await wait_saved()
    ok(settings_yaml()["estimate"]["calls"] == 1, "score: ask, if more appeals 1")
    await set_tab("General")
    await sitem("Long run threshold, minutes").locator("input").fill("0")
    await page.wait_for_timeout(600)
    ok(plugin_data()["notifyMinutes"] == 0, "notice — for any launch (0 minute)")
    await page.keyboard.press("Escape")
    for i, t in enumerate(["Bakery: find a package supplier.", "dacha: pump."]):
        (VAULT / "_staging" / f"2024-06-0{i + 2} thought.txt").write_text(f"0{i + 2}.06.2024\nmode: steady_state\n\n{t}\n", encoding="utf-8")
    await tab("Overview")
    await click("Phase 1: process")
    m = await choice(60)
    ok("Big launch" in await m.locator(".modal-title").inner_text(), "before launch — window «Big launch»")
    lines = await m.locator(".vm-choice-lines li").all_inner_texts()
    ok(lines and any("model" in x.lower() for x in lines) and any(x.startswith("Cost: ≈ $") for x in lines), "score: " + "; ".join(lines))
    await shot("score-launch", selector=None)
    await choose(m, "Cancel")
    await wait_idle()
    await last_notice_with("cancelled — nothing changed")
    ok(len(staging_txt()) == 2, "after «Cancellation» files remain _staging")
    n0 = len(await os_notices())
    await click("Phase 1: process")
    m = await choice(60)
    await choose(m, "Start")
    await wait_idle(120)
    n = await last_notice_with("Phase 1: ready")
    ok(not staging_txt() and "Requests:" in n, f"after «Launch.» file-processed: {n}")
    osn = (await os_notices())[n0:]
    ok(any(x["title"] == "Second Brain · Phase 1" and " after " in x["body"] for x in osn), f"notice Windows finish: {[x['body'] for x in osn]}")
    await js("() => { window.__focus = null; }")
    await open_settings("costs")
    await sitem("If calls exceed").locator("input.vm-num").fill("30")
    await wait_saved()
    await page.keyboard.press("Escape")

    step("15. Revalidation — evaluationally")
    await tab("Container")
    await click("Recheck placement")
    m = await choice(60)
    ok("Revalidation" in await m.locator(".modal-title").inner_text(), "Resilience always asks")
    lines = await m.locator(".vm-choice-lines li").all_inner_texts()
    ok(lines, "validation: " + "; ".join(lines))
    await choose(m, "Cancel")
    await wait_idle()
    await last_notice_with("Revalidation · weather station: cancelled")

    step("16. Journal")
    await tab("Log")
    ok(await page.locator(".vm-job").count() >= 5, f"journal-start: {await page.locator('.vm-job').count()}")
    ok(await page.locator(".vm-job", has_text="Tokens").count() >= 3, "launch-place — token, cost and duration")
    await page.locator(".vm-job .vm-link", has_text="output").first.click()
    await page.wait_for_selector(".vm-pre", timeout=5000)
    ok("$ brain " in await page.locator(".vm-pre").first.inner_text(), "program output is disclosed")
    await shot("journal", full_panel=True)
    await page.locator(".vm-view button", has_text="Change log").first.click()
    await page.wait_for_timeout(400)
    ok("change" in (await page.locator(".mod-root .view-header-title").inner_text()).lower(), "change log opens")

    step("17. Dark subject.")
    await js("() => { document.body.className = 'theme-dark'; }")
    await tab("Overview")
    await shot("dark-survey", full_panel=True)
    await tab("Questions")
    await shot("dark-questions", full_panel=True)
    await tab("Expenses")
    await shot("dark-expense", full_panel=True)
    await tab("Container")
    await shot("dark-container", full_panel=True)
    await click("Consult AI")
    await page.wait_for_selector(".modal .vm-rec, .modal .vm-callout.is-ok", timeout=60000)
    await wait_idle()
    await shot("dark-council", selector=None)
    await page.keyboard.press("Escape")
    ok(await page.locator(".vm-callout", has_text="AI advice is available.").count() == 1, "The closed board remained in the container card")
    await open_settings("models")
    await shot("dark-setting", selector=".modal")
    await page.keyboard.press("Escape")
    await js("() => { document.body.className = 'theme-light'; }")

    step("18. The program folder plugin is newer — propose")
    man = json.loads((PROG / "plugin" / "manifest.json").read_text(encoding="utf-8"))
    run_v = await js("() => window.__plugin.manifest.version")
    man["version"] = "9.9.8"
    (PROG / "plugin" / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    c0 = len(await calls())
    await js("() => { window.__plugin.startupChecks(); }")
    m = await choice(30)
    txt = await m.inner_text()
    ok("New version of the plugin" in txt and "9.9.8" in txt and run_v in txt, f"launch Obsidian: plugin 9.9.8 program-folder, work {run_v}")
    await shot("new-plugin", selector=None)
    await choose(m, "Install")
    m = await choice(60)
    ok("Plugin 9.9.8 installed" in await m.locator(".modal-title").inner_text(), "plugin installed — proposes to restart Obsidian")
    ok(json.loads((PLUGIN_DIR / "manifest.json").read_text(encoding="utf-8"))["version"] == "9.9.8", "depository — plugin 9.9.8")
    d = plugin_data()
    ok(d["programDir"] == str(PROG) and d.get("notifyMinutes") == 0, "plugin settings (data.json) preserved")
    await choose(m, "Restart Obsidian")
    ok(["app:reload"] in (await calls())[c0:], "«Reset. Obsidian» — team app:reload")

    step("19. Updating programme c GitHub")
    srv, base = start_github()
    EXTRA_ENV["BRAIN_GITHUB_API"] = base
    rel = {"tag_name": "v9.9.9", "name": "9.9.9", "body": "Whats new?:\n- model profile\n- section «Expenses»",
           "published_at": "2026-01-01T00:00:00Z",
           "assets": [{"name": "Second Brain v9.9.9.zip", "browser_download_url": f"{base}/dl/brain.zip",
                       "url": f"{base}/repos/user/brain/releases/assets/1"}]}
    GH.files["/repos/user/brain/releases/latest"] = (200, json.dumps(rel).encode(), "application/json")
    GH.files["/dl/brain.zip"] = (200, release_zip("9.9.9"), "application/zip")
    # v2.7: There is no reference to the repository and token in the settings — link (brain/__init__.py, UPDATE_REPO)
    await open_settings()
    ok(await page.locator(".vm-settings .setting-item", has_text="Programme repository").count() == 0
       and await page.locator(".vm-settings .setting-item", has_text="token").count() == 0,
       "into «Updates» No repository string and token")
    chk = sitem("Check now")
    ok("UPDATE_REPO" in await chk.inner_text() and await chk.locator("button", has_text="Check for updates").is_disabled(),
       "linkless — clue, where to put it (UPDATE_REPO), check-button is inactive")
    await shot("update-without-reference", selector=".modal")
    await page.keyboard.press("Escape")
    EXTRA_ENV["BRAIN_UPDATE_REPO"] = "https://github.com/user/brain"  # fittingly brain/__init__.py link
    await open_settings()
    chk = sitem("Check now")
    for _ in range(60):  # settings are reread by the program at each opening
        if "UPDATE_REPO" not in await chk.inner_text():
            break
        await page.wait_for_timeout(250)
    ok("UPDATE_REPO" not in await chk.inner_text() and not await chk.locator("button", has_text="Check for updates").is_disabled(),
       "reference — check-button active")
    await page.keyboard.press("Escape")
    await js("() => { window.__plugin.manifest.version = '9.9.8'; }")  # post-reboot Obsidian
    await js("() => window.__plugin.refreshState(true)")
    ok((await ui())["updates"] == {"repo": "https://github.com/user/brain", "check_on_start": True}, "snapshot: repository and launch verification")
    await js("() => { window.__plugin.startupChecks(); }")
    m = await choice(60)
    title = await m.locator(".modal-title").inner_text()
    txt = await m.inner_text()
    ok("New version available: 9.9.9" in title, f"launch Obsidian: «{title}»")
    ok("model profile" in txt and "user/brain" in txt and "release v9.9.9" in txt, "window-wise — release description and where it came from")
    ok(any(x.startswith("/repos/user/brain/releases/latest") for x in GH.seen), "request «GitHub» (latest release)")
    await shot("update", selector=None)
    await choose(m, "Skip this version")
    await page.wait_for_timeout(400)
    ok(plugin_data()["skipVersion"] == "9.9.9", "version 9.9.9 missed (data.json)")
    await js("() => window.__plugin.startupChecks()")
    ok(await page.locator(".vm-choice").count() == 0, "At the next launch, the missing version is not offered.")
    await open_settings()
    await sitem("Check now").locator("button", has_text="Check for updates").click()
    m = await choice(60)
    ok("9.9.9" in await m.locator(".modal-title").inner_text(), "button-button «Check for updates» Missed version is offered again")
    await choose(m, "Install")
    m = await choice(180)
    ok("Version 9.9.9 installed" in await m.locator(".modal-title").inner_text(), "update — proposes to restart Obsidian")
    ok('__version__ = "9.9.9"' in (PROG / "brain" / "__init__.py").read_text(encoding="utf-8"), "program updated to 9.9.9")
    ok(json.loads((PROG / "installed.json").read_text(encoding="utf-8"))["version"] == "9.9.9", "installed.json: 9.9.9")
    ok(json.loads((PLUGIN_DIR / "manifest.json").read_text(encoding="utf-8"))["version"] == "9.9.9", "The plugin in the storage is updated to 9.9.9")
    ok("repo" not in (settings_yaml().get("updates") or {}) and profile_of(settings_yaml(), "p1")["prices"]["input"] == 2,
       "settings.yaml untouched (There is no reference to the repository.)")
    c0 = len(await calls())
    await choose(m, "Restart Obsidian")
    ok(["app:reload"] in (await calls())[c0:], "«Reset. Obsidian» — team app:reload")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    srv.shutdown()

    step("20. Program not found.")
    await open_settings()
    prog_inp = sitem("Program folder").locator("input")
    await prog_inp.fill("/no/such/folder")
    await page.wait_for_timeout(1000)
    ok("No program found" in await page.locator(".vm-settings .vm-callout").first.inner_text(), "customized: program not found")
    await page.keyboard.press("Escape")
    await tab("Overview")
    ok(await page.locator(".vm-callout", has_text="The plugin cannot find the program").count() == 1, "panel: «Plugin doesnt see the program» setting-button")
    ok("program not found" in await page.locator(".status-bar").inner_text(), "status-line: no program")
    await shot("no-programme")
    await js("() => { app.setting.open(); app.setting.openTabById('vtoroy-mozg'); }")
    prog_inp = sitem("Program folder").locator("input")
    await prog_inp.fill(str(PROG))
    await page.wait_for_timeout(1200)
    await wait_idle()
    ok("Program found" in await page.locator(".vm-settings .vm-callout").first.inner_text(), "file back — program found again")
    await page.keyboard.press("Escape")

    step("21. Error in the plugin: show-off, journal, developer-report")
    await tab("Overview")
    await js("() => { const v = [...window.__plugin.views][0]; v.renderUsageTab = () => { throw new Error('error-check'); }; }")
    await tab("Expenses")
    box = page.locator(".vm-view .vm-error-box")
    await box.wait_for(state="visible", timeout=5000)
    btxt = await box.inner_text()
    ok("Error in the plugin (panel, tab «Expenses»)" in btxt and "error-check" in btxt, "tab error shown in place")
    ok(await page.locator(".vm-view .vm-tab").count() == 5 and await page.locator(".vm-view .vm-head").count() == 1,
       "the rest of the panel is working (cap, tab)")
    plog = VAULT / "_logs" / "plugin.log"
    for _ in range(30):  # journal API storage — later
        if plog.exists() and "error-check" in plog.read_text(encoding="utf-8"):
            break
        await page.wait_for_timeout(100)
    ok(plog.exists() and "error-check" in plog.read_text(encoding="utf-8")
       and "panel, tab «Expenses»" in plog.read_text(encoding="utf-8"), "misspelling _logs/plugin.log")
    await shot("mistake-plug-in")
    await box.locator("button", has_text="Copy report").click()
    await last_notice_with("Report copied.")
    clip = await js("() => window.__clipboard")
    ok(clip.startswith("Second Brain — plugin error") and "Plugin: " in clip and "error-check" in clip
       and "plugin:vtoroy-mozg" in clip, "«Copy the report.»: clipboard — version and stack error")
    ok(await js("() => window.__clipboardVia") == "navigator", "copying — window-buffer")
    await js("() => { window.__clipboard = ''; window.__clipboardDenied = true; }")
    await js("() => { const v = [...window.__plugin.views][0]; delete v.renderUsageTab; v.render(true); }")
    ok(await page.locator(".vm-view .vm-error-box").count() == 0 and await page.locator(".vm-view .vm-body .vm-seg").count() > 0,
       "After the tab is corrected, the tab is drawn again.")
    await open_settings("advanced")
    rep_btn = sitem("Developer report").locator("button", has_text="Create report")
    ok(await rep_btn.count() == 1, "Additionally. → Service: button «Collect a report»")
    await rep_btn.click()
    await last_notice_with("Report collected")
    rep = VAULT / "_logs" / "developer-report.md"
    rtext = rep.read_text(encoding="utf-8") if rep.exists() else ""
    pver = await js("() => window.__plugin.manifest.version")
    prog_ver = (await ui())["program"]
    ok(f"Plugin: {pver}" in rtext and f"Program: {prog_ver}" in rtext and "Obsidian: 1.15.0" in rtext
       and "error-check" in rtext and "## Latest launches" in rtext, "report: version, plugin error, last launches")
    ok(await page.locator(".mod-settings").count() == 0, "The settings window closed., report")
    ok(any(c[0] == "openFile" and "developer-report" in c[1] for c in await js("() => window.__calls")),
       "report file open in Obsidian")
    ok("sk-" not in rtext and "api_key" not in rtext, "No keys in the report.")
    ok((await js("() => window.__clipboard")).startswith("# Second Brain — developer report")
       and await js("() => window.__clipboardVia") == "electron", "window out of focus — Report copied through buffer Electron")
    await js("() => { window.__clipboardDenied = false; }")
    T.console[:] = [c for c in T.console if "error-check" not in c]

    errs = await js("() => window.__errors")
    ok(not errs, "mistake JavaScript no" + (f": {errs}" if errs else ""))


async def main():
    data = prepare()
    bridge = Bridge(data["pythonPath"])
    T.bridge = bridge
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox", "--disable-gpu"])
        ctx = await browser.new_context(viewport={"width": 1400, "height": 900}, locale="ru-RU", device_scale_factor=1)

        async def route(r):
            url = r.request.url[len(ORIGIN):].split("?")[0]
            if url.startswith("plugin/"):
                f = PLUGIN_DIR / url[len("plugin/"):]
            else:
                f = E2E / url
            if not f.is_file():
                await r.fulfill(status=404, body="no file")
                return
            ct = {"html": "text/html", "js": "application/javascript", "css": "text/css", "json": "application/json"}.get(f.suffix[1:], "application/octet-stream")
            await r.fulfill(status=200, body=f.read_bytes(), headers={"Content-Type": ct + "; charset=utf-8"})

        await ctx.route(ORIGIN + "**", route)
        init = {"vaultBase": str(VAULT), "pluginData": data, "pluginUrl": "plugin/", "noticeMax": 6000,
                "existing": [str(PROG / "brain" / "__main__.py"), data["pythonPath"], str(PROG)]}
        await ctx.add_init_script(f"window.__init = {json.dumps(init, ensure_ascii=False)};")
        page = await ctx.new_page()
        T.page = page
        console = []
        T.console = console
        page.on("console", lambda m: console.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
        await page.expose_function("__fsOp", bridge.fs_op)
        await page.expose_function("__fsAbs", bridge.fs_abs)
        await page.expose_function("__spawnStart", bridge.spawn_start)
        await page.expose_function("__spawnPoll", bridge.spawn_poll)
        await page.expose_function("__spawnKill", bridge.spawn_kill)
        await page.expose_function("__spawnWrite", bridge.spawn_write)
        code = 0
        try:
            await scenario()
            bad = [c for c in console if "pageerror" in c or c.startswith("error")]
            ok(not bad, "error-free console" + (f": {bad}" if bad else ""))
            print(f"\nIts all gone.: {len(PASSED)} ✓")
        except Exception:  # noqa: BLE001
            code = 1
            traceback.print_exc()
            try:
                await page.screenshot(path=str(SHOTS / "Mistake.png"))
                print("notice:", (await notices())[-8:])
                print("mistake JS:", await js("() => window.__errors"))
            except Exception:  # noqa: BLE001
                pass
            print("console:", console[-15:])
            for ent in bridge.runs[-3:]:
                print("--- launch:", " ".join(ent["args"][4:]), "code", ent["code"])
                print("".join(ent["all_out"])[-1500:])
                print("stderr:", "".join(ent["all_err"])[-1500:])
        finally:
            (ROOT / "runs.log").write_text("\n\n".join(
                f"$ {' '.join(e['args'])}\n(code {e['code']}, {len(''.join(e['all_out']))} sign)\n{''.join(e['all_out'])}\n--- stderr ---\n{''.join(e['all_err'])}"
                for e in bridge.runs), encoding="utf-8")
            await browser.close()
    return code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

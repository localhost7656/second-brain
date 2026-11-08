"""Проверка плагина «Второй мозг» в браузере.
Страница harness.html имитирует Obsidian; собранный плагин (из хранилища, куда его поставила команда install-plugin)
запускает настоящую программу на тестовом хранилище с тестовой моделью (llm.mode: fake).
Запуск: python3 run_e2e.py [папка]   — скриншоты в <папка>/shots.
Нужны: Python с PyYAML, requests, numpy, dulwich, playwright (и браузер: playwright install chromium);
собранный плагин в <программа>/plugin (npm run build). Папка программы — BRAIN_APP или две папки выше этого файла."""
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
    for cand in (E2E.parent.parent, Path("/data/brain/app")):  # в комплекте: <программа>/plugin-src/tests
        if (cand / "brain" / "__main__.py").exists():
            return cand
    raise SystemExit("Не найдена папка программы: укажите её в переменной BRAIN_APP")


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
    arch = VAULT / "_staging" / "архив"
    (arch / "Чат с ИИ").mkdir(parents=True)
    (arch / "дневник 2023.txt").write_text(
        "02.04.2023\n\nСегодня посадил томаты в теплице на даче. Полив каждый день вечером.\n\n"
        "Огурцы в теплице плохо растут. Наверное, мало света.\n\n"
        "Метеостанцию можно поставить в теплицу на даче — следить за влажностью.\n\n"
        "Приснился странный сон про поезд.\n\nТот вариант с поливом по таймеру надо проверить.\n", encoding="utf-8")
    (arch / "Чат с ИИ" / "датчик для метеостанции.txt").write_text(
        "01.06.2023\nя: Какой датчик взять для метеостанции — проводной или беспроводной?\n"
        "ИИ: Беспроводной удобнее и ставится где угодно, проводной дешевле и не требует батареек. "
        "Если важна цена, проводной выглядит разумнее, но точность нужно проверять на месте.\n"
        "я: Возможно, хватит одного датчика на балконе.\nИИ: Для точности лучше два датчика, один на улице, второй в комнате.\n"
        "я: Значит, берём два проводных датчика. Можно крепить датчик на стену.\n"
        "я: А можно крепить датчик под крышей, так он в тени.\n", encoding="utf-8")
    (arch / "пекарня.txt").write_text(
        "10.05.2023\n\nДумаю открыть маленькую пекарню у дома. Себестоимость буханки хлеба — 50 рублей.\n\n"
        "Аренда помещения 40 000 рублей в месяц. Мне нравится идея с самообслуживанием.\n", encoding="utf-8")
    (arch / "разное.txt").write_text("Надо бы разобрать старые фотографии на антресоли.\n", encoding="utf-8")
    (arch / "мука.txt").write_text("12.05.2023\nhint: это про дачу\n\nПекарь в соседней пекарне сказал, что муку лучше брать у мельницы напрямую.\n", encoding="utf-8")
    step("Установка плагина командой install-plugin")
    r = subprocess.run([str(PROG / ".venv" / "bin" / "python"), "-X", "utf8", "-m", "brain", "install-plugin", str(VAULT)],
                       cwd=PROG, capture_output=True, text=True, env=env(), timeout=120)
    print(r.stdout.strip())
    ok(r.returncode == 0, "install-plugin отработал")
    ok(all((PLUGIN_DIR / f).exists() for f in ("main.js", "manifest.json", "styles.css", "data.json")), "файлы плагина скопированы в .obsidian/plugins/vtoroy-mozg")
    ok(json.loads((VAULT / ".obsidian" / "community-plugins.json").read_text(encoding="utf-8")) == ["vtoroy-mozg"], "плагин включён в community-plugins.json")
    data = json.loads((PLUGIN_DIR / "data.json").read_text(encoding="utf-8"))
    ok(data["programDir"] == str(PROG) and data["pythonPath"].endswith("python"), "в data.json вписаны папка программы и Python")
    return data


# ---------- мост страница ↔ Python ----------
def vpath(rel: str) -> Path:
    rel = (rel or "").strip("/")
    p = (VAULT / rel) if rel else VAULT
    rp = p.resolve()
    if rp != VAULT.resolve() and VAULT.resolve() not in rp.parents:
        raise ValueError("путь вне хранилища: " + rel)
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
                for k, v in list(new.items()):  # как Obsidian: нетронутые значения остаются как были (даты — датами)
                    if k in orig and json.dumps(orig[k], default=str, ensure_ascii=False) == json.dumps(v, ensure_ascii=False):
                        new[k] = orig[k]
                dumped = yaml.safe_dump(new, allow_unicode=True, sort_keys=False, default_flow_style=False) if new else ""
                p.write_text(("---\n" + dumped + "---\n" if new else "") + body, encoding="utf-8")
                return json.dumps({"value": None})
            if op == "plugin_data":
                (PLUGIN_DIR / "data.json").write_text(d["data"], encoding="utf-8")
                return json.dumps({"value": None})
            return json.dumps({"error": "неизвестная операция " + op})
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
            return json.dumps({"error": f"запуск «{d['cmd']}», а в настройках плагина Python «{self.python}»"}, ensure_ascii=False)
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
                if not ent["keep"]:  # интерактивный запуск (--ask-stdin): ввод открыт, ответы — через spawn_write
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
        except Exception:  # noqa: BLE001 — процесс уже завершился
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


# ---------- помощники сценария ----------
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
    raise AssertionError(f"нет уведомления «{sub}». Были: {(await notices())[-6:]}")


def fm_of(rel):
    raw, _ = split_fm((VAULT / rel).read_text(encoding="utf-8"))
    return yaml.safe_load(raw) or {}


async def modal():
    loc = T.page.locator(".modal-container .modal").last
    await loc.wait_for(state="visible", timeout=15000)
    return loc


def sitem(label, scope=".vm-settings"):
    """Строка настроек по точному названию."""
    return T.page.locator(f"{scope} .setting-item").filter(
        has=T.page.locator(".setting-item-name", has_text=re.compile("^" + re.escape(label) + "$"))).first


async def set_tab(name):
    await T.page.locator(".vm-settings .vm-set-tab").filter(has_text=re.compile("^" + re.escape(name) + "$")).click()
    await T.page.wait_for_timeout(250)


async def open_settings(tab_id="main"):
    """Окно настроек на вкладке (main, models, thresholds, input, docs, costs, advanced) — как из панели."""
    await js(f"() => window.__plugin.openSettings('{tab_id}')")
    await T.page.wait_for_selector(".vm-settings .vm-set-tab.is-active", timeout=10000)
    await T.page.wait_for_function(
        "() => { const b = document.querySelector('.vm-settings .vm-set-body');"
        " return b && !b.textContent.includes('Загружаю настройки программы') && b.querySelectorAll('.vm-sec').length > 0; }",
        timeout=30000)
    await wait_idle()


async def wait_saved():
    """Настройки сохраняются через ~1 с после правки."""
    await T.page.wait_for_timeout(1400)
    await wait_idle()


def settings_yaml():
    return yaml.safe_load((PROG / "settings.yaml").read_text(encoding="utf-8"))


def profile_of(st, pid):
    return next((p for p in (st.get("llm") or {}).get("profiles") or [] if p.get("id") == pid), None)


def plugin_data():
    return json.loads((PLUGIN_DIR / "data.json").read_text(encoding="utf-8"))


async def choice(timeout=30):
    """Окно выбора: вопрос программы посреди запуска, обновление, перезапуск."""
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


# ---------- «GitHub» для проверки обновления ----------
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
    """Архив «новой версии»: программа из папки prog с другим номером версии (и у программы, и у плагина)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in ("brain", "prompts", "plugin"):
            for f in sorted((PROG / d).rglob("*")):
                if not f.is_file() or "__pycache__" in f.parts or "_прежние" in f.parts:
                    continue
                rel = f.relative_to(PROG).as_posix()
                data = f.read_bytes()
                if rel == "brain/__init__.py":
                    data = re.sub(rb'__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"'.encode(), data)
                elif rel == "plugin/manifest.json":
                    m = json.loads(data.decode("utf-8"))
                    m["version"] = version
                    data = json.dumps(m, ensure_ascii=False, indent=2).encode("utf-8")
                z.writestr(f"Второй мозг/{rel}", data)
    return buf.getvalue()


# ---------- v2.7: своя модель эмбеддингов (llama.cpp) ----------
async def llama_flow():
    """Окно параметров запуска, скачивание модели и llama.cpp (имитация Hugging Face и GitHub), запуск сервера
    (ненастоящий llama-server), адрес сервера сам вписывается в настройки, «Остановить»."""
    page = T.page
    for d in (APP / "tests", APP):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
    from fake_llama import FakeHub, free_port
    from brain import llama as L
    model = bytes(range(256)) * 8192 + b"gguf-tail" * 500  # ~2 МБ вместо 6,9 ГБ
    hub = FakeHub(L.MODEL["repo"], L.MODEL["file"], model, L.plat()[1])
    port = free_port()
    keys = {"BRAIN_HF_BASE": hub.url, "BRAIN_LLAMA_API": hub.url + "/gh", "BRAIN_LLAMA_NO_SYSTEM": "1", "FAKE_LLAMA_LOAD_SEC": "1",
            "BRAIN_TEST_HW": json.dumps({"ram_gb": 12, "ram_free_gb": 7.5, "cores": 8, "threads": 16, "cpu": "Тестовый процессор",
                                         "gpus": [{"name": "NVIDIA GeForce RTX 3060", "vram_gb": 12, "vendor": "nvidia"}], "nvidia": True})}
    EXTRA_ENV.update(keys)
    box = page.locator(".vm-settings .vm-llama-box")
    try:
        await set_tab("Основное")  # перерисовать вкладку: состояние модели перечитается уже с имитацией
        await set_tab("Модели")
        await page.wait_for_function("() => (document.querySelector('.vm-settings .vm-llama-box') || {}).textContent?.includes('Сервер:')",
                                     timeout=20000)
        txt = await box.inner_text()
        ok("не скачана" in txt and "llama.cpp: не скачан" in txt and "Сервер: не запущен" in txt,
           "«Где считать: на этом компьютере» — блок «Своя модель»: модель и llama.cpp не скачаны, сервер не запущен")
        await box.locator("button", has_text="Запустить модель…").click()
        m = await modal()
        await page.wait_for_selector(".vm-llama .vm-llama-hw-grid", timeout=20000)
        t = await m.inner_text()
        ok("Запуск модели эмбеддингов" in t and "12 ГБ" in t and "RTX 3060" in t and "8 ядер" in t,
           "окно параметров: процессор, память и видеокарта компьютера")
        ram = m.locator(".vm-llama-ram")
        ok("is-bad" in (await ram.get_attribute("class") or "") and "16 ГБ" in await ram.inner_text(),
           "на процессоре при 12 ГБ памяти — красное предупреждение «минимум 16 ГБ»")
        plan = await m.locator(".vm-llama-plan").inner_text()
        ok("Будет скачано" in plan and "KaLM" in plan and "llama.cpp" in plan, "в окне — что будет скачано (модель и llama.cpp)")
        await sitem("Где считать", ".vm-llama").locator("select").select_option("gpu")
        await page.wait_for_timeout(200)
        ok(await m.locator(".vm-llama-ram").count() == 0 and await sitem("Слоёв модели на видеокарте", ".vm-llama").count() == 1
           and await sitem("Сборка llama.cpp", ".vm-llama").count() == 1,
           "«Видеокарта» — предупреждения о 16 ГБ нет, есть сборка llama.cpp и слои на видеокарте")
        await shot("модель-окно-видеокарта", selector=".modal.vm-llama-modal")
        await sitem("Где считать", ".vm-llama").locator("select").select_option("cpu")
        await page.wait_for_timeout(200)
        csel = sitem("Контекст", ".vm-llama").locator("select")
        ok(await csel.input_value() == "4096" and "8,4 ГБ" in await csel.locator("option[value='4096']").inner_text()
           and "9,6 ГБ" in await csel.locator("option[value='8192']").inner_text(),
           "контекст по умолчанию 4096; у каждого варианта — сколько памяти займёт модель")
        await csel.select_option("8192")
        await page.wait_for_timeout(200)
        ok("с контекстом 8 192 модель займёт около 9,6 ГБ" in (await m.locator(".vm-llama-ram").inner_text()).replace("\u00a0", " "),
           "плашка о памяти пересчиталась под выбранный контекст")
        await sitem("Квантование KV-кеша", ".vm-llama").locator("select").select_option("q8_0")
        await sitem("Потоков процессора", ".vm-llama").locator("button", has_text="По ядрам").click()
        ok(await sitem("Потоков процессора", ".vm-llama").locator("input").input_value() == "8", "«По ядрам» — 8 потоков")
        await sitem("Порт", ".vm-llama").locator("input").fill(str(port))
        await page.wait_for_timeout(200)
        ok(f"http://127.0.0.1:{port}/v1" in await m.inner_text(), "в окне — адрес будущего сервера")
        await shot("модель-окно-запуска", selector=".modal.vm-llama-modal")
        await m.locator(".vm-modal-buttons button", has_text=re.compile("^Запустить$")).click()
        live = page.locator(".vm-settings .vm-llama-live:not(.vm-hidden)")
        await live.wait_for(state="visible", timeout=15000)
        ok(await live.locator("button", has_text="Стоп").count() == 1, "ход запуска виден прямо в настройках, есть «Стоп»")
        n = await last_notice_with("Модель запущена", 120)
        ok(f"127.0.0.1:{port}/v1" in n and "Адрес вписан" in n, f"уведомление: {n}")
        await wait_idle()
        emb = settings_yaml()["embeddings"]
        srv = emb.get("server") or {}
        ok(emb["base_url"] == f"http://127.0.0.1:{port}/v1" and srv.get("ctx") == 8192 and srv.get("kv_cache") == "q8_0"
           and srv.get("threads") == 8 and srv.get("port") == port and srv.get("device") == "cpu",
           "адрес сервера и параметры запуска вписаны в settings.yaml")
        await page.wait_for_function(
            "(u) => { const it = [...document.querySelectorAll('.vm-settings .setting-item')].find((s) => "
            "s.querySelector('.setting-item-name')?.textContent === 'Адрес сервера'); return !!it && it.querySelector('input')?.value === u; }",
            arg=f"http://127.0.0.1:{port}/v1", timeout=20000)
        ok(True, "поле «Адрес сервера» в открытых настройках обновилось само")
        await page.wait_for_function("() => (document.querySelector('.vm-settings .vm-llama-box') || {}).textContent?.includes('Сервер: работает')",
                                     timeout=20000)
        txt = await box.inner_text()
        ok("скачана" in txt and f"127.0.0.1:{port}/v1 (процессор)" in txt and "(b9999)" in txt,
           "блок «Своя модель»: модель скачана, llama.cpp есть, сервер работает")
        args = json.loads(re.search(r"FAKE ARGS: (.*)", (PROG / "llama.cpp" / "server.log").read_text(encoding="utf-8")).group(1))
        pairs = {a: args[i + 1] for i, a in enumerate(args[:-1])}
        ok(pairs.get("-c") == "8192" and pairs.get("-b") == "8192" and pairs.get("-ub") == "8192" and pairs.get("-ctk") == "q8_0"
           and pairs.get("-t") == "8" and pairs.get("--port") == str(port) and "--embedding" in args,
           f"llama-server запущен с выбранными параметрами (пакет = контексту): {' '.join(args)}")
        ok((PROG / "models" / L.MODEL["file"]).read_bytes() == model, "модель скачана в папку models программы")
        await box.scroll_into_view_if_needed()
        await shot("модель-в-настройках", selector=".modal")
        await box.locator("button", has_text="Остановить").click()
        await last_notice_with("остановлена", 30)
        await page.wait_for_function("() => (document.querySelector('.vm-settings .vm-llama-box') || {}).textContent?.includes('Сервер: не запущен')",
                                     timeout=20000)
        ok("запустится сам" in await box.inner_text(), "«Остановить» — сервер остановлен; запустится сам, когда понадобится")
    finally:
        subprocess.run([str(PROG / ".venv" / "bin" / "python"), "-X", "utf8", "-m", "brain", "llama", "stop"], cwd=PROG,
                       capture_output=True, text=True, env=env(), timeout=60)
        hub.close()
        for k in keys:
            EXTRA_ENV.pop(k, None)


# ---------- сценарий ----------
async def scenario():
    page = T.page
    step("1. Запуск плагина: панель, мастер первой загрузки")
    await page.goto(ORIGIN + "harness.html")
    await js("() => window.__boot()")
    await page.wait_for_selector(".vm-view .vm-wizard", timeout=30000)
    await wait_idle()
    await page.wait_for_selector(".vm-step.is-done", timeout=10000)
    ok(await page.locator(".vm-step.is-done").count() == 1, "мастер: шаг «Сложите заметки» выполнен (файлы в _staging есть)")
    ok("Фаза 1" in await page.locator(".vm-step.is-current .vm-step-title").inner_text(), "мастер: текущий шаг — Фаза 1")
    ok((VAULT / ".system" / "ui.json").exists(), "снимок состояния .system/ui.json создан командой snapshot")
    ok("Второй мозг" in await page.locator(".status-bar").inner_text(), "в строке состояния есть «Второй мозг»")
    ok(json.loads((PLUGIN_DIR / "data.json").read_text(encoding="utf-8")).get("welcomed") is True, "первое открытие запомнено (welcomed)")
    await shot("мастер", full_panel=True)

    step("2. Фаза 1 → черновик структуры")
    EXTRA_ENV["FAKE_DELAY"] = "5"
    await click("Запустить Фазу 1")
    await page.wait_for_selector(".vm-run.is-on .vm-run-label", timeout=10000)
    await page.wait_for_function(
        "() => { const w = document.querySelector('.vm-run-wait');"
        " return w && !w.classList.contains('vm-hidden') && w.textContent.includes('Ждём ответа модели'); }",
        timeout=40000, polling=100)
    ok("Фаза 1" in await page.locator(".vm-run-label").inner_text(), "блок текущего запуска показывает «Фаза 1»")
    wt = await page.locator(".vm-run-wait").inner_text()
    ok("Ждём ответа модели" in wt and "Структура" in wt, f"пока модель думает — счётчик ожидания: «{wt}»")
    ok(await page.locator(".vm-run-time").inner_text() != "", "время запуска идёт")
    ok(await page.locator(".vm-run-line").inner_text() != "", "строка прогресса показывает вывод программы")
    await page.wait_for_function("() => document.querySelector('.status-bar').textContent.includes('ждём ответа')", timeout=10000, polling=100)
    sb = await page.locator(".status-bar").inner_text()
    ok("Фаза 1" in sb, f"строка состояния: «{sb}»")
    await shot("идёт-фаза-1")
    await wait_idle()
    EXTRA_ENV.pop("FAKE_DELAY")
    u = await ui()
    ok(u["status"]["structure_pending"] and u["status"]["draft"], "черновик структуры ждёт утверждения")
    await last_notice_with("Фаза 1:")
    ok("Проверьте черновик" in await page.locator(".vm-step.is-current .vm-step-title").inner_text(), "мастер: текущий шаг — утверждение черновика")
    await shot("черновик", full_panel=True)
    await click("Открыть черновик")
    await page.wait_for_timeout(400)
    ok("Структура утверждена" in await page.locator(".mod-root pre.vm-test-file").inner_text(), "черновик открылся в редакторе")

    step("3. Утверждение структуры из панели")
    await click("Утвердить структуру")
    m = await modal()
    ok("Утвердить структуру?" in await m.inner_text(), "спрашивает подтверждение")
    await shot("подтверждение", selector=None)
    await click("Утвердить и продолжить", ".modal")
    await page.wait_for_timeout(300)
    await wait_idle(120)
    u = await ui()
    ok(u["status"]["approved_once"] and not u["status"]["structure_pending"], "структура утверждена, черновик применён")
    ok(any(c[0] == "MarkdownView.save" for c in await js("() => window.__calls")), "открытый черновик сохранён перед утверждением")
    ok(len(u["containers"]) >= 4, f"созданы контейнеры: {', '.join(c['title'] for c in u['containers'])}")
    ok(await page.locator(".vm-tree-row").count() == len(u["containers"]), "дерево контейнеров в панели")
    ok(await page.locator(".vm-wizard").count() == 0, "мастер скрыт после утверждения")
    ok(u["status"]["questions"] > 0 and await page.locator(".vm-tab .vm-badge").count() == 1, f"вопросы: {u['status']['questions']}, на вкладке значок")
    await shot("обзор", full_panel=True)

    step("4. Вопросы: вариант и свободный ответ")
    await tab("Вопросы")
    cards = page.locator(".vm-q")
    ok(await cards.count() == len(u["questions"]), "все открытые вопросы показаны карточками")
    await shot("вопросы", full_panel=True)
    q_opt = next((q for q in u["questions"] if q["options"]), None)
    ok(q_opt is not None, f"есть вопрос с вариантами ({q_opt and q_opt['id']})")
    card = page.locator(".vm-q").filter(has=page.locator(".vm-q-meta", has_text=re.compile("^" + q_opt["id"] + r"\b")))
    await card.locator(".vm-q-option").first.click()
    await wait_idle()
    await last_notice_with(f"Ответ на {q_opt['id']} принят")
    u2 = await ui()
    ok(all(q["id"] != q_opt["id"] for q in u2["questions"]), f"{q_opt['id']}: ответ принят, вопрос ушёл")
    q_free = next((q for q in u2["questions"] if q["free_text"] and not q["options"]), None) or next((q for q in u2["questions"] if q["free_text"]), None)
    if q_free:
        card = page.locator(".vm-q").filter(has=page.locator(".vm-q-meta", has_text=re.compile("^" + q_free["id"] + r"\b")))
        await card.locator("textarea").fill("Фото с дачи 2010 года, хочу оцифровать")
        await card.locator("button", has_text="Ответить").click()
        await wait_idle()
        u3 = await ui()
        gone = all(q["id"] != q_free["id"] for q in u3["questions"])
        note = next((q.get("note") for q in u3["questions"] if q["id"] == q_free["id"]), None)
        ok(gone or note, f"{q_free['id']}: свободный ответ {'принят' if gone else 'не принят с пояснением: ' + str(note)}")

    step("5. Контейнер: карточка, пороги")
    await tab("Обзор")
    meteo = next(c for c in (await ui())["containers"] if c["title"] == "Метеостанция")
    await page.locator(".vm-tree-row").filter(has_text="Метеостанция").first.click()
    await page.wait_for_selector(".vm-chead-title", timeout=5000)
    ok("Метеостанция" in await page.locator(".vm-chead-title").inner_text(), "по клику в дереве открылся контейнер Метеостанция")
    ok(await page.locator(".vm-thr-row").count() >= 3, "таблица порогов показана")
    await shot("контейнер", full_panel=True)
    u = await ui()
    info = u["threshold_info"]
    names = [k for k, v in info.items() if v["per_container"] and k != "seed_dormancy_days"]
    k0 = "classification" if "classification" in names else names[0]
    row = page.locator(".vm-thr-row").filter(has=page.locator(".vm-thr-label", has_text=info[k0]["label"])).first
    inp = row.locator("input.vm-thr-input")
    rng = row.locator("input.vm-thr-range")
    eff = meteo["thresholds"][k0]["value"]
    ok(await inp.get_attribute("placeholder") == str(eff), f"в поле «{info[k0]['label']}» серым — действующее значение {eff}")
    ok(await rng.input_value() == str(eff) and await row.locator(".vm-thr-src").inner_text() == "общий",
       f"ползунок стоит на действующем значении ({eff}), источник — «общий»")
    trs = row.locator(".vm-thr-reset")
    ok(await trs.is_visible() and await trs.is_disabled() and "vm-reset-off" in (await trs.get_attribute("class")),
       "своего порога нет — ↺ на месте, но тусклая и не нажимается")
    rb0 = await rng.bounding_box()
    await rng.evaluate("(r) => { r.value = '42'; r.dispatchEvent(new Event('input', { bubbles: true })); }")
    ok(await inp.input_value() == "42" and await row.locator(".vm-thr-src").inner_text() == "свой, не сохранён"
       and await trs.is_visible() and not await trs.is_disabled(), "ползунок вписал 42 в поле: «свой, не сохранён», ↺ активна")
    rb1 = await rng.bounding_box()
    ok(rb0 and rb1 and abs(rb0["x"] - rb1["x"]) < 0.5 and abs(rb0["width"] - rb1["width"]) < 0.5,
       "ползунок не сдвинулся и не сжался, когда ↺ стала активной")
    await row.locator(".vm-thr-reset").click()
    ok(await inp.input_value() == "" and await row.locator(".vm-thr-src").inner_text() == "общий"
       and (await btn("Сохранить").first.inner_text()).strip() == "Сохранить", "↺ убрал свой порог — снова «общий», сохранять нечего")
    await inp.fill("abc")
    ok("vm-invalid" in (await inp.get_attribute("class")) and await btn("Сохранить").first.is_disabled(), "неверное значение подсвечено, «Сохранить» недоступна")
    newv = 80 if eff != 80 else 75
    await inp.fill(str(newv))
    ok((await btn("Сохранить").first.inner_text()).strip() == "Сохранить (1)", "кнопка показывает число изменений")
    await btn("Сохранить").first.click()
    await wait_idle()
    fm = fm_of(meteo["path"])
    ok(fm.get("thresholds", {}).get(k0) == newv, f"порог записан в YAML контейнера: thresholds.{k0} = {newv}")
    ok(fm.get("type") == "project" and "id" in fm, "остальные поля YAML контейнера сохранены")
    await page.wait_for_timeout(300)
    row = page.locator(".vm-thr-row").filter(has=page.locator(".vm-thr-label", has_text=info[k0]["label"])).first
    ok("is-own" in (await row.get_attribute("class")) and (await row.locator(".vm-thr-src").inner_text()) == "свой", "после сохранения порог помечен «свой»")
    child = next((c for c in u["containers"] if c.get("parent") == meteo["id"]), None)
    parent = next((c for c in u["containers"] if c["id"] == meteo.get("parent")), None)
    if parent:
        await page.locator(".vm-cbar select").select_option(parent["id"])
        await page.wait_for_timeout(300)
        await page.locator(".vm-cbar select").select_option(meteo["id"])
        await page.wait_for_timeout(300)
    u = await ui()
    meteo = next(c for c in u["containers"] if c["title"] == "Метеостанция")
    ok(meteo["thresholds"][k0]["value"] == newv and meteo["thresholds"][k0]["source"] == "own", "программа видит свой порог контейнера (снимок)")
    if child:
        ch = next(c for c in u["containers"] if c["id"] == child["id"])
        ok(ch["thresholds"][k0]["source"] == "parent", f"вложенный «{ch['title']}» наследует порог от Метеостанция")
    await shot("порог-сохранён", full_panel=True)

    step("6. Совет ИИ по порогам")
    await click("Посоветоваться с ИИ")
    m = await modal()
    await page.wait_for_selector(".modal .vm-rec, .modal .vm-callout", timeout=60000)
    await wait_idle()
    recs = page.locator(".modal .vm-rec")
    nrec = await recs.count()
    ok(nrec >= 1, f"совет получен: рекомендаций {nrec}")
    ok((await page.locator(".modal .vm-advice-summary").inner_text()).strip() != "", "есть общий вывод модели")
    await shot("совет-ии", selector=None)
    first_label = await recs.first.locator(".vm-rec-label").inner_text()
    first_new = await recs.first.locator(".vm-rec-new").inner_text()
    if nrec > 1:
        await recs.nth(1).locator("input[type=checkbox]").click()
        ok("is-off" in (await recs.nth(1).get_attribute("class")), "вторую рекомендацию можно снять")
    await page.locator(".modal button", has_text="Применить выбранное").click()
    await wait_idle()
    await last_notice_with("обновлены")
    fm = fm_of(meteo["path"])
    applied = [k for k, v in (fm.get("thresholds") or {}).items() if str(v) == first_new]
    ok(applied, f"применено: {first_label} → {first_new} (в YAML: {fm.get('thresholds')})")
    ok(await page.locator(".modal-container").count() == 0, "окно совета закрылось")

    step("7. Стиль документов и Фаза 2")
    await page.locator("textarea.vm-style").fill("Пиши как бизнес-план, с цифрами и сроками.")
    await click("Сохранить стиль")
    await wait_idle()
    ok(fm_of(meteo["path"]).get("style") == "Пиши как бизнес-план, с цифрами и сроками.", "стиль записан в YAML контейнера")
    await click("Написать документы (Фаза 2)")
    await page.wait_for_timeout(300)
    await wait_idle(120)
    await last_notice_with("Фаза 2 · Метеостанция")
    await page.wait_for_selector(".vm-doc", timeout=10000)
    ok(await page.locator(".vm-doc").count() >= 1, f"документы появились в карточке: {await page.locator('.vm-doc').count()}")
    u = await ui()
    meteo = next(c for c in u["containers"] if c["title"] == "Метеостанция")
    doc = (VAULT / meteo["products"][0]["path"]).read_text(encoding="utf-8")
    ok("бизнес-план" in doc, "стиль контейнера учтён в документе")
    await click("Обновить документы (Фаза 2)")
    m = await modal()
    ok("Документы актуальны" in await m.inner_text(), "повторная Фаза 2 без изменений — спрашивает, переписывать ли")
    await page.locator(".modal button", has_text="Отмена").click()
    await page.wait_for_timeout(300)
    await page.locator(".vm-doc .vm-link").first.click()
    await page.wait_for_timeout(400)
    ok(meteo["products"][0]["title"] in (await page.locator(".mod-root .view-header-title").inner_text()), "документ открывается по клику")
    await shot("документы", full_panel=True)

    step("8. Статус контейнера из панели")
    sel = page.locator(".vm-cmeta select").nth(1)
    await sel.select_option("dormant")
    await wait_idle()
    ok(fm_of(meteo["path"]).get("container_status") == "dormant", "статус «заморожен» записан в YAML")
    await last_notice_with("статус: заморожен")
    await page.locator(".vm-cmeta select").nth(1).select_option("active")
    await wait_idle()
    ok(fm_of(meteo["path"]).get("container_status") == "active", "статус возвращён")

    step("9. Новая мысль")
    await tab("Обзор")
    await click("Новая мысль")
    m = await modal()
    ok(not await m.locator("#vm-now").is_checked(), "флажок «Сразу обработать (Фаза 1)» по умолчанию выключен")
    await m.locator("textarea").fill("Купить лейку с длинным носиком для теплицы.")
    n0 = len(T.bridge.runs)
    await m.locator("button", has_text="Сохранить").click()
    n = await last_notice_with("Мысль сохранена")
    ok("_staging/" in n and "при следующей Фазе 1" in n, f"без флажка мысль ждёт следующей Фазы 1: {n}")
    await page.wait_for_timeout(800)
    ok(not any("phase1" in e["args"] for e in T.bridge.runs[n0:]), "без флажка Фаза 1 не запускалась")
    ok(any("лейку" in p.read_text(encoding="utf-8") for p in (VAULT / "_staging").glob("*.txt")), "файл мысли лежит в _staging")
    await click("Новая мысль")
    m = await modal()
    await m.locator("textarea").fill("Для метеостанции нужен второй датчик — купить в выходные и проверить на балконе.")
    await m.locator("#vm-hint").fill("Метеостанция")
    await m.locator("#vm-now").check()
    await shot("новая-мысль", selector=None)
    await m.locator("button", has_text="Сохранить").click()
    n = await last_notice_with("Обрабатываю")
    ok("Мысль сохранена: _staging/" in n and "Для метеостанции" in n, f"с флажком — сразу Фаза 1: {n}")
    await page.wait_for_timeout(300)
    await wait_idle(120)
    src = [p for p in (VAULT / "_исходники").glob("*.txt") if "Для метеостанции" in p.read_text(encoding="utf-8")]
    ok(src and "mode: steady_state" in src[0].read_text(encoding="utf-8") and "hint: Метеостанция" in src[0].read_text(encoding="utf-8"),
       "мысль обработана Фазой 1 (исходник с шапкой hint и mode)")
    ok(any("лейку" in p.read_text(encoding="utf-8") for p in (VAULT / "_исходники").glob("*.txt")),
       "отложенная мысль обработана этой же Фазой 1")

    step("10. Настройки: вкладки, поиск, ползунки, профили моделей, модели шагов")
    await page.locator(".vm-head-tools .vm-icon-btn").nth(1).click()
    await page.wait_for_selector(".vm-settings .vm-set-tab", timeout=10000)
    await page.wait_for_function(
        "() => [...document.querySelectorAll('.vm-settings .setting-item-heading .setting-item-name')].some(e => e.textContent === 'Обновления')",
        timeout=30000)
    await wait_idle()
    tabs = [t.strip() for t in await page.locator(".vm-settings .vm-set-tab").all_inner_texts()]
    ok(tabs == ["Основное", "Модели", "Пороги", "Входящие", "Документы", "Расходы", "Дополнительно"], "вкладки настроек: " + ", ".join(tabs))
    heads = await page.locator(".vm-settings .setting-item-heading .setting-item-name").all_inner_texts()
    ok(all(h in heads for h in ("Программа", "Уведомления Windows", "Обновления")) and "Хранилище" not in heads,
       "вкладка «Основное»: " + ", ".join(heads))
    navs = [t.strip() for t in await page.locator(".mod-settings .vertical-tab-header .vertical-tab-nav-item").all_inner_texts()]
    ok(navs == ["Второй мозг"] and await page.locator(".mod-settings .vertical-tab-nav-item.is-active").count() == 1,
       f"пункт «Второй мозг» в меню настроек слева: {navs}")
    ok("Программа найдена" in await page.locator(".vm-settings .vm-callout").first.inner_text(), "раздел «Программа»: программа найдена")
    await shot("настройки", selector=".modal")
    r = subprocess.run([str(PROG / ".venv/bin/python"), "-X", "utf8", "-m", "brain", "--json", "settings"], cwd=PROG,
                       capture_output=True, text=True, env=env(), timeout=60)
    sres = json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("@@RESULT ")][-1][9:])
    fields = {f["key"]: f for sec in sres["settings"]["schema"] for f in sec["fields"]}
    nf = fields["thresholds.classification"]
    defv = sres["settings"]["defaults"]["thresholds"]["classification"]
    await set_tab("Пороги")
    ok("is-active" in await page.locator(".vm-set-tab", has_text="Пороги").get_attribute("class"), "вкладка «Пороги» открыта")
    item = sitem(nf["label"])
    num, rng = item.locator("input.vm-num"), item.locator("input.vm-set-range")
    cur = await num.input_value()
    ok(await rng.count() == 1 and await rng.input_value() == cur == str(defv), f"«{nf['label']}»: ползунок и поле ({cur})")
    rs = item.locator(".vm-reset")
    rcls = await rs.get_attribute("class") or ""
    ok(await rs.is_visible() and "vm-reset-off" in rcls and "is-disabled" in rcls and await rs.get_attribute("aria-disabled") == "true",
       "значение по умолчанию — ↺ на месте, но тусклая и неактивна")
    sb0 = await rng.bounding_box()
    await num.fill(str(nf["min"] - 1))
    await page.wait_for_timeout(200)
    ok("vm-invalid" in (await num.get_attribute("class")) and "Нужно" in await item.locator(".vm-field-error").inner_text(),
       f"«{nf['label']}»: значение вне допустимого подсвечено")
    await rng.evaluate("(r) => { r.value = '77'; r.dispatchEvent(new Event('input', { bubbles: true })); }")
    ok(await num.input_value() == "77" and "vm-invalid" not in (await num.get_attribute("class")), "ползунок вписал 77 в поле")
    ok(await rs.is_visible() and "vm-reset-off" not in (await rs.get_attribute("class") or "") and "vm-changed" in (await item.get_attribute("class")),
       "значение отличается от умолчания — ↺ сразу стала активной")
    sb1 = await rng.bounding_box()
    ok(sb0 and sb1 and abs(sb0["x"] - sb1["x"]) < 0.5 and abs(sb0["width"] - sb1["width"]) < 0.5,
       "ползунок в настройках не сдвинулся, когда ↺ стала активной")
    await wait_saved()
    await last_notice_with("Настройки сохранены")
    ok(settings_yaml()["thresholds"]["classification"] == 77, "settings.yaml: thresholds.classification = 77")
    ok((PROG / "settings.yaml.bak").exists(), "прежний settings.yaml сохранён как .bak")
    ok((PROG / "settings.yaml").read_text(encoding="utf-8").count("#") > 10, "settings.yaml переписан с пояснениями")
    await item.locator(".vm-reset").click()
    await wait_saved()
    ok(settings_yaml()["thresholds"]["classification"] == defv and await sitem(nf["label"]).locator("input.vm-num").input_value() == str(defv),
       f"↺ вернула значение по умолчанию ({defv})")
    rs = sitem(nf["label"]).locator(".vm-reset")
    ok(await rs.is_visible() and "vm-reset-off" in (await rs.get_attribute("class") or ""), "после возврата ↺ осталась на месте — снова тусклая")
    sf = fields["thresholds.duplicate_similarity"]  # похожесть — шкала 0–1: «86%» значит 0,86
    snum = sitem(sf["label"]).locator("input.vm-num")
    await snum.fill("86%")
    await page.wait_for_timeout(200)
    ok("vm-invalid" not in (await snum.get_attribute("class")), f"«{sf['label']}»: «86%» принято")
    await wait_saved()
    ok(settings_yaml()["thresholds"]["duplicate_similarity"] == 0.86, "settings.yaml: «86%» для похожести записано как 0.86")
    await sitem(sf["label"]).locator(".vm-reset").click()
    await wait_saved()
    ok(settings_yaml()["thresholds"]["duplicate_similarity"] == sres["settings"]["defaults"]["thresholds"]["duplicate_similarity"],
       "↺ вернула похожесть по умолчанию")
    # поиск по всем вкладкам
    search = page.locator(".vm-settings input.vm-set-search")
    await search.fill("бюджет")
    await page.wait_for_timeout(300)
    vis = ".vm-settings .vm-search-pane:not(.vm-hidden) .setting-item:not(.setting-item-heading):not(.vm-hidden)"
    names = await page.locator(vis + " .setting-item-name").all_inner_texts()
    infos = await page.locator(vis + " .setting-item-info").all_inner_texts()
    panes = await page.locator(".vm-settings .vm-search-pane:not(.vm-hidden) .vm-search-tab").all_inner_texts()
    ok("Месячный бюджет, $" in names and "расходы" in [x.lower() for x in panes] and all("бюджет" in t.lower() for t in infos),
       f"поиск «бюджет»: {', '.join(names)} (вкладки: {', '.join(panes)})")
    await shot("настройки-поиск", selector=".modal")
    await search.fill("")
    await page.wait_for_timeout(300)
    ok((await page.locator(".vm-set-tab.is-active").inner_text()).strip() == "Пороги" and await page.locator(".vm-search-pane").count() == 0,
       "поиск очищен — снова вкладка «Пороги»")
    # профили моделей
    await set_tab("Модели")
    await page.wait_for_selector(".vm-settings .vm-prof-editor", timeout=10000)
    ok(await sitem("Режим").locator("select").input_value() == "fake", "режим из старых настроек сохранён (тестовая модель)")
    opts = await sitem("Профиль для правки").locator("select option").all_inner_texts()
    ok(len(opts) == 1 and "облачная" in opts[0], f"старые настройки превращены в облачный профиль: {opts}")
    ok(await page.locator(".vm-settings .vm-prof-box .setting-item-name", has_text="Вход, $ за 1 млн токенов").count() == 1,
       "у облачного профиля — цены")
    await click("＋ Локальный", ".vm-settings")
    await page.wait_for_timeout(300)
    ptitle = await page.locator(".vm-settings .vm-prof-title").inner_text()
    ok("Локальная модель" in ptitle and "локальная" in ptitle, f"создан локальный профиль: «{ptitle}»")
    ok(await page.locator(".vm-settings .vm-prof-box .setting-item-name", has_text="Вход, $").count() == 0,
       "у локального профиля цен нет (считаются токены и время)")
    await sitem("Модель", ".vm-prof-box").locator("input").fill("qwen2.5-7b-instruct")
    await wait_saved()  # правка после автосохранения не должна теряться
    await sitem("Предел запроса, знаков", ".vm-prof-box").locator("input.vm-num").fill("40000")
    await wait_saved()
    loc = next((x for x in settings_yaml()["llm"]["profiles"] if x.get("kind") == "local"), None)
    ok(loc and loc["model"] == "qwen2.5-7b-instruct" and loc["max_input_chars"] == 40000 and loc["base_url"].startswith("http://127.0.0.1"),
       f"локальный профиль записан в settings.yaml: {loc and loc.get('id')}")
    pid = loc["id"]
    role = page.locator(".vm-settings .setting-item.vm-role").filter(has=page.locator(".setting-item-name", has_text=re.compile("^Классификация$"))).first
    await role.scroll_into_view_if_needed()
    rop = await role.locator("select option").all_inner_texts()
    ok(rop[0] == "Как основная" and rop[-1] == "Вручную через веб-чат" and len(rop) == 4, f"выбор модели шага: {', '.join(rop)}")
    await role.locator("select").select_option(pid)
    await wait_saved()
    ok(settings_yaml()["llm"]["roles"].get("Классификация") == pid, f"шаг «Классификация» отдан профилю {pid} (settings.yaml)")
    await set_tab("Основное")
    await set_tab("Модели")
    used = await page.locator(".vm-settings .vm-prof-box").inner_text()
    ok("шаги: Классификация" in used, "в профиле видно, какие шаги на нём")
    await page.locator(".vm-settings .vm-prof-editor").scroll_into_view_if_needed()
    await shot("настройки-профили", selector=".modal")
    role = page.locator(".vm-settings .setting-item.vm-role").filter(has=page.locator(".setting-item-name", has_text=re.compile("^Классификация$"))).first
    await role.locator("select").select_option("")
    await wait_saved()
    ok(not (settings_yaml()["llm"].get("roles") or {}).get("Классификация"), "шаг вернулся на основную модель — убран из settings.yaml")
    await sitem("Профиль для правки").locator(".extra-setting-button").click()
    m = await modal()
    ok("Удалить профиль?" in await m.inner_text(), "удаление профиля — с подтверждением")
    await m.locator("button", has_text="Удалить").click()
    await wait_saved()
    ok(not profile_of(settings_yaml(), pid) and profile_of(settings_yaml(), "p1"), "локальный профиль удалён, облачный остался")
    # эмбеддинги: поля зависят от выбранного режима
    emb = sitem("Где считать")
    await emb.scroll_into_view_if_needed()
    price = page.locator(".vm-settings .setting-item-name", has_text="Цена, $ за 1 млн токенов")
    ok(await price.count() == 0, "эмбеддинги в тестовом режиме: полей облака нет")
    await emb.locator("select").select_option("cloud")
    await page.wait_for_timeout(300)
    ok(await price.count() == 1 and await sitem("Адрес").count() == 0, "облачные эмбеддинги: появились адрес API, ключ и цена")
    await sitem("Где считать").locator("select").select_option("local")
    await page.wait_for_timeout(300)
    ok(await price.count() == 0 and await sitem("Адрес сервера").count() == 1, "локальные эмбеддинги: цены нет, есть адрес сервера")
    await wait_saved()
    ok(settings_yaml()["embeddings"]["mode"] == "local", "режим эмбеддингов записан")
    await llama_flow()
    await js("() => window.__plugin.patchSettings({ embeddings: { mode: 'fake' } })")
    await wait_idle()
    ok(settings_yaml()["embeddings"]["mode"] == "fake", "режим эмбеддингов возвращён (тестовый)")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    ok(await page.locator(".mod-settings").count() == 0, "окно настроек закрыто")

    step("11. Стоп посреди прогона")
    st = VAULT / "_staging"
    for i, t in enumerate(["Пекарне нужен логотип и вывеска.", "На даче поставить бочку для полива.", "Метеостанция: проверить, не врёт ли датчик на солнце.",
                           "Для пекарни посчитать окупаемость за год.", "Теплицу утеплить к осени."]):
        (st / f"2024-05-0{i + 1} мысль {i + 1}.txt").write_text(f"0{i + 1}.05.2024\nmode: steady_state\n\n{t}\n", encoding="utf-8")
    EXTRA_ENV["FAKE_DELAY"] = "1.0"
    await tab("Обзор")
    await page.wait_for_timeout(200)
    await click("Фаза 1: обработать новое")
    await page.wait_for_selector(".vm-run.is-on .vm-run-label", timeout=10000)
    await page.wait_for_function(
        "() => { const u = document.querySelector('.vm-run-usage'), b = document.querySelector('.vm-run .vm-bar'), s = document.querySelector('.vm-run-stage');"
        " return u && b && s && !u.classList.contains('vm-hidden') && u.textContent.includes('Этот запуск') && !b.classList.contains('vm-hidden')"
        " && / из \\d/.test(s.textContent); }",
        timeout=30000, polling=100)
    stage = await page.locator(".vm-run-stage").inner_text()
    ok(re.search(r"\d+ из \d+", stage), f"этап с номером: «{stage}»")
    ok(True, "на ходу: полоса прогресса и расход — «" + await page.locator(".vm-run-usage").inner_text() + "»")
    await page.wait_for_function("() => / \\d+ из \\d+ /.test(document.querySelector('.status-bar').textContent)", timeout=5000, polling=100)
    ok(True, "строка состояния: «" + await page.locator(".status-bar").inner_text() + "»")
    await shot("идёт-прогон")
    await click("Стоп", ".vm-run")
    await page.wait_for_selector(".vm-run-note", timeout=5000)
    ok(any(c[0] == "writeFileSync" and c[1].endswith(".system/stop") for c in await calls()), "«Стоп» записал файл .system/stop")
    await shot("останавливаю")
    await wait_idle(120)
    EXTRA_ENV.pop("FAKE_DELAY")
    n = await last_notice_with("Фаза 1")
    jst = await js("() => window.__plugin.engine.history.find(j => j.args[0] === 'run').status")
    ok(jst in ("stopped", "done"), f"прогон остановлен (статус {jst}); уведомление: {n}")
    ok(not (VAULT / ".system" / "stop").exists(), "файл stop убран")
    await click("Фаза 1: обработать новое")
    await page.wait_for_timeout(300)
    await wait_idle(120)
    ok(not staging_txt(), "следующий запуск дообработал всё")

    step("12. Расходы: сводка, цены профиля, пересчёт прошлых обращений, бюджет")
    await tab("Расходы")
    await page.wait_for_selector(".vm-usage-total", timeout=10000)
    u = await ui()
    ok(u["usage"]["totals"]["all"]["calls"] > 0, f"обращений за всё время: {u['usage']['totals']['all']['calls']}")
    seg = await page.locator(".vm-seg-btn").all_inner_texts()
    ok(seg == ["Сегодня", "Этот месяц", "Прошлый месяц", "Всё время"], "периоды: " + ", ".join(seg))
    card = page.locator(".vm-prof").filter(has=page.locator(".vm-prof-name", has_text="Z.ai · fake")).first
    ok("не заданы" in await card.locator(".vm-prices-title").inner_text(), "у облачного профиля цены не заданы — стоимость не считается")
    ok(await page.locator(".vm-usage-total .vm-warn-line").count() == 1, "предупреждение: есть обращения без стоимости")
    ok(await page.locator(".vm-usage-total .vm-usage-cell").count() == 4, "итоги: обращения, токены входа и выхода, работа моделей")
    ok(await page.locator(".vm-chart-col").count() >= 7 and await page.locator(".vm-urun").count() >= 3, "график по дням и последние запуски")
    await shot("расходы-без-цен", full_panel=True)
    pin = card.locator(".vm-prices input")
    await pin.nth(0).fill("2")
    await pin.nth(2).fill("8")
    await card.locator("button", has_text="Сохранить").click()
    m = await modal()
    ok("Пересчитать прошлые обращения?" in await m.inner_text(), "после ввода цен — вопрос о пересчёте прошлых обращений")
    await m.locator("button", has_text="Пересчитать").click()
    await wait_idle()
    await last_notice_with("Стоимость пересчитана")
    pr = profile_of(settings_yaml(), "p1")["prices"]
    ok(pr["input"] == 2 and pr["output"] == 8 and pr["cached_input"] is None, f"цены записаны в settings.yaml: {pr}")
    await page.wait_for_timeout(400)
    u = await ui()
    tot = u["usage"]["totals"]["all"]
    ok(tot["cost"] > 0 and not tot["unpriced"], f"прошлые обращения пересчитаны: ${tot['cost']:.4f}, без стоимости — 0")
    ok(await page.locator(".vm-usage-total .vm-warn-line").count() == 0 and "$" in await page.locator(".vm-usage-money").inner_text(),
       "в сводке — деньги: " + await page.locator(".vm-usage-money").inner_text())
    binp = page.locator(".vm-inline-form input.vm-num")
    await binp.fill("0.0001")
    await page.locator(".vm-inline-form button", has_text="Сохранить").click()
    await wait_idle()
    await last_notice_with("Бюджет месяца")
    ok(settings_yaml()["budget"]["monthly_usd"] == 0.0001, "бюджет месяца записан в settings.yaml")
    await page.wait_for_selector(".vm-usage-view .vm-budget.is-over, .vm-budget.is-over", timeout=10000)
    ok(True, "полоса бюджета красная — превышен")
    await shot("расходы", full_panel=True)
    await tab("Обзор")
    cur = await page.locator(".vm-current").inner_text()
    ok("Z.ai · fake" in cur and await page.locator(".vm-current .vm-budget.is-over").count() == 1, "в «Обзоре» — текущая модель, расход месяца и бюджет")

    step("13. Бюджет исчерпан: программа спрашивает посреди запуска")
    await js("() => { window.__focus = false; }")  # Obsidian свёрнут — уведомления Windows приходят
    (VAULT / "_staging" / "2024-06-01 датчик.txt").write_text("01.06.2024\nmode: steady_state\n\nКупить второй датчик для метеостанции.\n", encoding="utf-8")
    n0 = len(await os_notices())
    await click("Фаза 1: обработать новое")
    m = await choice(60)
    ok("Бюджет исчерпан" in await m.locator(".modal-title").inner_text(), "посреди запуска — окно «Бюджет исчерпан»")
    btns = await m.locator(".vm-modal-buttons button").all_inner_texts()
    ok(btns == ["Продолжить до конца этого запуска", "Остановить"], "варианты: " + " / ".join(btns))
    await page.wait_for_timeout(1100)
    ok("ждёт вашего ответа" in await page.locator(".status-bar").inner_text(), "строка состояния: ждёт вашего ответа")
    ok(await page.locator(".vm-run-ask:not(.vm-hidden)").count() == 1, "в панели: программа ждёт ответа")
    osn = (await os_notices())[n0:]
    ok(any(x["title"] == "Второй мозг ждёт ответа" and "Бюджет исчерпан" in x["body"] for x in osn), f"уведомление Windows: {osn}")
    await shot("бюджет-вопрос", selector=None)
    await choose(m, "Остановить")
    await wait_idle(120)
    n = await last_notice_with("остановлено: израсходовано")
    ok("бюджет" in n, f"остановлено по бюджету: {n[:90]}…")
    job = await js("() => { const j = window.__plugin.engine.history.find(j => j.args[0] === 'run'); return { status: j.status, r: j.result }; }")
    ok(job["r"].get("budget_stop") and job["status"] in ("stopped", "failed"), f"итог запуска: budget_stop (статус {job['status']})")
    await click("Фаза 1: обработать новое")
    m = await choice(60)
    await choose(m, "Продолжить до конца этого запуска")
    await wait_idle(120)
    await last_notice_with("Фаза 1: готово")
    ok(not staging_txt(), "«Продолжить до конца этого запуска» — запись обработана")
    await tab("Расходы")
    await page.locator(".vm-inline-form input.vm-num").fill("")
    await page.locator(".vm-inline-form button", has_text="Сохранить").click()
    await wait_idle()
    await last_notice_with("Бюджет снят")
    ok(settings_yaml()["budget"]["monthly_usd"] is None, "бюджет снят")

    step("14. Оценка перед большим запуском; уведомление Windows по окончании")
    await open_settings("costs")
    await sitem("Если обращений больше").locator("input.vm-num").fill("1")
    await wait_saved()
    ok(settings_yaml()["estimate"]["calls"] == 1, "оценка: спрашивать, если обращений больше 1")
    await set_tab("Основное")
    await sitem("Долгий запуск — дольше, минут").locator("input").fill("0")
    await page.wait_for_timeout(600)
    ok(plugin_data()["notifyMinutes"] == 0, "уведомление об окончании — для любого запуска (0 минут)")
    await page.keyboard.press("Escape")
    for i, t in enumerate(["Пекарня: найти поставщика пакетов.", "Дача: проверить насос."]):
        (VAULT / "_staging" / f"2024-06-0{i + 2} мысль.txt").write_text(f"0{i + 2}.06.2024\nmode: steady_state\n\n{t}\n", encoding="utf-8")
    await tab("Обзор")
    await click("Фаза 1: обработать новое")
    m = await choice(60)
    ok("Большой запуск" in await m.locator(".modal-title").inner_text(), "перед запуском — окно «Большой запуск»")
    lines = await m.locator(".vm-choice-lines li").all_inner_texts()
    ok(lines and any("обращ" in x.lower() for x in lines) and any(x.startswith("Стоимость: ≈ $") for x in lines), "оценка: " + "; ".join(lines))
    await shot("оценка-запуска", selector=None)
    await choose(m, "Отмена")
    await wait_idle()
    await last_notice_with("отменено — ничего не изменено")
    ok(len(staging_txt()) == 2, "после «Отмена» файлы остались в _staging")
    n0 = len(await os_notices())
    await click("Фаза 1: обработать новое")
    m = await choice(60)
    await choose(m, "Запустить")
    await wait_idle(120)
    n = await last_notice_with("Фаза 1: готово")
    ok(not staging_txt() and "Обращений:" in n, f"после «Запустить» файлы обработаны: {n}")
    osn = (await os_notices())[n0:]
    ok(any(x["title"] == "Второй мозг · Фаза 1" and " за " in x["body"] for x in osn), f"уведомление Windows об окончании: {[x['body'] for x in osn]}")
    await js("() => { window.__focus = null; }")
    await open_settings("costs")
    await sitem("Если обращений больше").locator("input.vm-num").fill("30")
    await wait_saved()
    await page.keyboard.press("Escape")

    step("15. Ревалидация — с оценкой и подтверждением")
    await tab("Контейнер")
    await click("Перепроверить раскладку")
    m = await choice(60)
    ok("Ревалидация" in await m.locator(".modal-title").inner_text(), "ревалидация спрашивает всегда")
    lines = await m.locator(".vm-choice-lines li").all_inner_texts()
    ok(lines, "оценка ревалидации: " + "; ".join(lines))
    await choose(m, "Отмена")
    await wait_idle()
    await last_notice_with("Ревалидация · Метеостанция: отменено")

    step("16. Журнал")
    await tab("Журнал")
    ok(await page.locator(".vm-job").count() >= 5, f"запуски сеанса в журнале: {await page.locator('.vm-job').count()}")
    ok(await page.locator(".vm-job", has_text="Токенов").count() >= 3, "у запусков — токены, стоимость и длительность")
    await page.locator(".vm-job .vm-link", has_text="вывод программы").first.click()
    await page.wait_for_selector(".vm-pre", timeout=5000)
    ok("$ brain " in await page.locator(".vm-pre").first.inner_text(), "вывод программы раскрывается")
    await shot("журнал", full_panel=True)
    await page.locator(".vm-view button", has_text="Изменения").first.click()
    await page.wait_for_timeout(400)
    ok("изменения" in (await page.locator(".mod-root .view-header-title").inner_text()).lower(), "лог изменений открывается")

    step("17. Тёмная тема")
    await js("() => { document.body.className = 'theme-dark'; }")
    await tab("Обзор")
    await shot("тёмная-обзор", full_panel=True)
    await tab("Вопросы")
    await shot("тёмная-вопросы", full_panel=True)
    await tab("Расходы")
    await shot("тёмная-расходы", full_panel=True)
    await tab("Контейнер")
    await shot("тёмная-контейнер", full_panel=True)
    await click("Посоветоваться с ИИ")
    await page.wait_for_selector(".modal .vm-rec, .modal .vm-callout.is-ok", timeout=60000)
    await wait_idle()
    await shot("тёмная-совет", selector=None)
    await page.keyboard.press("Escape")
    ok(await page.locator(".vm-callout", has_text="Есть совет ИИ").count() == 1, "закрытый совет остался в карточке контейнера")
    await open_settings("models")
    await shot("тёмная-настройки", selector=".modal")
    await page.keyboard.press("Escape")
    await js("() => { document.body.className = 'theme-light'; }")

    step("18. В папке программы плагин новее — предложить установить")
    man = json.loads((PROG / "plugin" / "manifest.json").read_text(encoding="utf-8"))
    run_v = await js("() => window.__plugin.manifest.version")
    man["version"] = "9.9.8"
    (PROG / "plugin" / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    c0 = len(await calls())
    await js("() => { window.__plugin.startupChecks(); }")
    m = await choice(30)
    txt = await m.inner_text()
    ok("Новая версия плагина" in txt and "9.9.8" in txt and run_v in txt, f"при запуске Obsidian: плагин 9.9.8 в папке программы, работает {run_v}")
    await shot("новый-плагин", selector=None)
    await choose(m, "Установить")
    m = await choice(60)
    ok("Плагин 9.9.8 установлен" in await m.locator(".modal-title").inner_text(), "плагин установлен — предлагает перезапустить Obsidian")
    ok(json.loads((PLUGIN_DIR / "manifest.json").read_text(encoding="utf-8"))["version"] == "9.9.8", "в хранилище — плагин 9.9.8")
    d = plugin_data()
    ok(d["programDir"] == str(PROG) and d.get("notifyMinutes") == 0, "настройки плагина (data.json) сохранились")
    await choose(m, "Перезапустить Obsidian")
    ok(["app:reload"] in (await calls())[c0:], "«Перезапустить Obsidian» — команда app:reload")

    step("19. Обновление программы с GitHub")
    srv, base = start_github()
    EXTRA_ENV["BRAIN_GITHUB_API"] = base
    rel = {"tag_name": "v9.9.9", "name": "9.9.9", "body": "Что нового:\n- профили моделей\n- раздел «Расходы»",
           "published_at": "2026-01-01T00:00:00Z",
           "assets": [{"name": "Второй мозг v9.9.9.zip", "browser_download_url": f"{base}/dl/brain.zip",
                       "url": f"{base}/repos/user/brain/releases/assets/1"}]}
    GH.files["/repos/user/brain/releases/latest"] = (200, json.dumps(rel).encode(), "application/json")
    GH.files["/dl/brain.zip"] = (200, release_zip("9.9.9"), "application/zip")
    # v2.7: ссылки на репозиторий и токена в настройках нет — ссылка вписывается в программу (brain/__init__.py, UPDATE_REPO)
    await open_settings()
    ok(await page.locator(".vm-settings .setting-item", has_text="Репозиторий программы").count() == 0
       and await page.locator(".vm-settings .setting-item", has_text="Токен").count() == 0,
       "в «Обновлениях» нет строки репозитория и токена")
    chk = sitem("Проверить сейчас")
    ok("UPDATE_REPO" in await chk.inner_text() and await chk.locator("button", has_text="Проверить обновления").is_disabled(),
       "ссылка не вписана — подсказка, где её вписать (UPDATE_REPO), кнопка проверки неактивна")
    await shot("обновления-без-ссылки", selector=".modal")
    await page.keyboard.press("Escape")
    EXTRA_ENV["BRAIN_UPDATE_REPO"] = "https://github.com/user/brain"  # как вписанная в brain/__init__.py ссылка
    await open_settings()
    chk = sitem("Проверить сейчас")
    for _ in range(60):  # настройки перечитываются программой при каждом открытии
        if "UPDATE_REPO" not in await chk.inner_text():
            break
        await page.wait_for_timeout(250)
    ok("UPDATE_REPO" not in await chk.inner_text() and not await chk.locator("button", has_text="Проверить обновления").is_disabled(),
       "ссылка вписана в программу — кнопка проверки активна")
    await page.keyboard.press("Escape")
    await js("() => { window.__plugin.manifest.version = '9.9.8'; }")  # как после перезапуска Obsidian
    await js("() => window.__plugin.refreshState(true)")
    ok((await ui())["updates"] == {"repo": "https://github.com/user/brain", "check_on_start": True}, "снимок: репозиторий и проверка при запуске")
    await js("() => { window.__plugin.startupChecks(); }")
    m = await choice(60)
    title = await m.locator(".modal-title").inner_text()
    txt = await m.inner_text()
    ok("Вышла новая версия: 9.9.9" in title, f"при запуске Obsidian: «{title}»")
    ok("профили моделей" in txt and "user/brain" in txt and "релиз v9.9.9" in txt, "в окне — описание релиза и откуда он")
    ok(any(x.startswith("/repos/user/brain/releases/latest") for x in GH.seen), "запрос ушёл в «GitHub» (последний релиз)")
    await shot("обновление", selector=None)
    await choose(m, "Пропустить эту версию")
    await page.wait_for_timeout(400)
    ok(plugin_data()["skipVersion"] == "9.9.9", "версия 9.9.9 пропущена (data.json)")
    await js("() => window.__plugin.startupChecks()")
    ok(await page.locator(".vm-choice").count() == 0, "при следующем запуске пропущенная версия не предлагается")
    await open_settings()
    await sitem("Проверить сейчас").locator("button", has_text="Проверить обновления").click()
    m = await choice(60)
    ok("9.9.9" in await m.locator(".modal-title").inner_text(), "по кнопке «Проверить обновления» пропущенная версия предлагается снова")
    await choose(m, "Установить")
    m = await choice(180)
    ok("Установлена версия 9.9.9" in await m.locator(".modal-title").inner_text(), "обновление установлено — предлагает перезапустить Obsidian")
    ok('__version__ = "9.9.9"' in (PROG / "brain" / "__init__.py").read_text(encoding="utf-8"), "программа обновлена до 9.9.9")
    ok(json.loads((PROG / "installed.json").read_text(encoding="utf-8"))["version"] == "9.9.9", "installed.json: 9.9.9")
    ok(json.loads((PLUGIN_DIR / "manifest.json").read_text(encoding="utf-8"))["version"] == "9.9.9", "плагин в хранилище обновлён до 9.9.9")
    ok("repo" not in (settings_yaml().get("updates") or {}) and profile_of(settings_yaml(), "p1")["prices"]["input"] == 2,
       "settings.yaml не тронут (ссылки на репозиторий в нём нет)")
    c0 = len(await calls())
    await choose(m, "Перезапустить Obsidian")
    ok(["app:reload"] in (await calls())[c0:], "«Перезапустить Obsidian» — команда app:reload")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    srv.shutdown()

    step("20. Программа не найдена")
    await open_settings()
    prog_inp = sitem("Папка программы").locator("input")
    await prog_inp.fill("/нет/такой/папки")
    await page.wait_for_timeout(1000)
    ok("нет программы" in await page.locator(".vm-settings .vm-callout").first.inner_text(), "в настройках: программа не найдена")
    await page.keyboard.press("Escape")
    await tab("Обзор")
    ok(await page.locator(".vm-callout", has_text="Плагин не видит программу").count() == 1, "панель: «Плагин не видит программу» с кнопкой настроек")
    ok("нет программы" in await page.locator(".status-bar").inner_text(), "строка состояния: нет программы")
    await shot("нет-программы")
    await js("() => { app.setting.open(); app.setting.openTabById('vtoroy-mozg'); }")
    prog_inp = sitem("Папка программы").locator("input")
    await prog_inp.fill(str(PROG))
    await page.wait_for_timeout(1200)
    await wait_idle()
    ok("Программа найдена" in await page.locator(".vm-settings .vm-callout").first.inner_text(), "папку вернули — программа снова найдена")
    await page.keyboard.press("Escape")

    step("21. Ошибка в плагине: показ на месте, журнал, отчёт для разработчика")
    await tab("Обзор")
    await js("() => { const v = [...window.__plugin.views][0]; v.renderUsageTab = () => { throw new Error('проверка отчёта об ошибке'); }; }")
    await tab("Расходы")
    box = page.locator(".vm-view .vm-error-box")
    await box.wait_for(state="visible", timeout=5000)
    btxt = await box.inner_text()
    ok("Ошибка в плагине (панель, вкладка «Расходы»)" in btxt and "проверка отчёта об ошибке" in btxt, "ошибка вкладки показана на месте")
    ok(await page.locator(".vm-view .vm-tab").count() == 5 and await page.locator(".vm-view .vm-head").count() == 1,
       "остальная панель работает (шапка, вкладки)")
    plog = VAULT / "_логи" / "плагин.log"
    for _ in range(30):  # журнал пишется через API хранилища — чуть позже
        if plog.exists() and "проверка отчёта об ошибке" in plog.read_text(encoding="utf-8"):
            break
        await page.wait_for_timeout(100)
    ok(plog.exists() and "проверка отчёта об ошибке" in plog.read_text(encoding="utf-8")
       and "панель, вкладка «Расходы»" in plog.read_text(encoding="utf-8"), "ошибка записана в _логи/плагин.log")
    await shot("ошибка-плагина")
    await box.locator("button", has_text="Скопировать отчёт").click()
    await last_notice_with("Отчёт скопирован")
    clip = await js("() => window.__clipboard")
    ok(clip.startswith("Второй мозг — ошибка плагина") and "Плагин: " in clip and "проверка отчёта об ошибке" in clip
       and "plugin:vtoroy-mozg" in clip, "«Скопировать отчёт»: в буфере обмена — версии и ошибка со стеком")
    ok(await js("() => window.__clipboardVia") == "navigator", "копирование — обычным буфером обмена окна")
    await js("() => { window.__clipboard = ''; window.__clipboardDenied = true; }")
    await js("() => { const v = [...window.__plugin.views][0]; delete v.renderUsageTab; v.render(true); }")
    ok(await page.locator(".vm-view .vm-error-box").count() == 0 and await page.locator(".vm-view .vm-body .vm-seg").count() > 0,
       "после исправления вкладка снова рисуется")
    await open_settings("advanced")
    rep_btn = sitem("Отчёт для разработчика").locator("button", has_text="Собрать отчёт")
    ok(await rep_btn.count() == 1, "Дополнительно → Служебное: кнопка «Собрать отчёт»")
    await rep_btn.click()
    await last_notice_with("Отчёт собран")
    rep = VAULT / "_логи" / "отчёт для разработчика.md"
    rtext = rep.read_text(encoding="utf-8") if rep.exists() else ""
    pver = await js("() => window.__plugin.manifest.version")
    prog_ver = (await ui())["program"]
    ok(f"Плагин: {pver}" in rtext and f"Программа: {prog_ver}" in rtext and "Obsidian: 1.15.0" in rtext
       and "проверка отчёта об ошибке" in rtext and "## Последние запуски" in rtext, "отчёт: версии, ошибка плагина, последние запуски")
    ok(await page.locator(".mod-settings").count() == 0, "окно настроек закрылось, отчёт открыт")
    ok(any(c[0] == "openFile" and "отчёт для разработчика" in c[1] for c in await js("() => window.__calls")),
       "файл отчёта открыт в Obsidian")
    ok("sk-" not in rtext and "api_key" not in rtext, "ключей в отчёте нет")
    ok((await js("() => window.__clipboard")).startswith("# Второй мозг — отчёт для разработчика")
       and await js("() => window.__clipboardVia") == "electron", "окно не в фокусе — отчёт скопирован через буфер Electron")
    await js("() => { window.__clipboardDenied = false; }")
    T.console[:] = [c for c in T.console if "проверка отчёта об ошибке" not in c]

    errs = await js("() => window.__errors")
    ok(not errs, "ошибок JavaScript нет" + (f": {errs}" if errs else ""))


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
                await r.fulfill(status=404, body="нет файла")
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
            ok(not bad, "консоль без ошибок" + (f": {bad}" if bad else ""))
            print(f"\nВСЁ ПРОШЛО: {len(PASSED)} ✓")
        except Exception:  # noqa: BLE001
            code = 1
            traceback.print_exc()
            try:
                await page.screenshot(path=str(SHOTS / "ОШИБКА.png"))
                print("уведомления:", (await notices())[-8:])
                print("ошибки JS:", await js("() => window.__errors"))
            except Exception:  # noqa: BLE001
                pass
            print("консоль:", console[-15:])
            for ent in bridge.runs[-3:]:
                print("--- запуск:", " ".join(ent["args"][4:]), "код", ent["code"])
                print("".join(ent["all_out"])[-1500:])
                print("stderr:", "".join(ent["all_err"])[-1500:])
        finally:
            (ROOT / "runs.log").write_text("\n\n".join(
                f"$ {' '.join(e['args'])}\n(код {e['code']}, {len(''.join(e['all_out']))} знаков)\n{''.join(e['all_out'])}\n--- stderr ---\n{''.join(e['all_err'])}"
                for e in bridge.runs), encoding="utf-8")
            await browser.close()
    return code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

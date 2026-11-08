"""Проверка плагина «Второй мозг» в настоящем Obsidian (Linux, виртуальный экран Xvfb).
Заглушка из run_e2e.py знает об Obsidian только то, что в неё вписали; здесь — сам Obsidian: его окно настроек
(в 1.15 — отдельное окно), меню слева, диалоги, буфер обмена, консоль всех окон.
Сценарий: установка командой setup → доверие плагинам → панель и мастер → Фаза 1 → утверждение структуры →
вкладки панели → настройки в отдельном окне (все вкладки, поиск, пороги, профиль модели с подтверждением удаления,
проверка связи) → настройки модальным окном → «Новая мысль» → ошибка в плагине («Скопировать отчёт», журнал) →
«Отчёт для разработчика» → ошибки консоли во всех окнах → имена в классах плагина не совпадают с внутренними
именами Obsidian (так в 1.13+ сломались настройки 2.5). Скриншоты — в <рабочая папка>/shots.
Запуск: python3 run_real.py [папка Obsidian для Linux (распакованный tar.gz)] [рабочая папка]
Нужны: Xvfb, Python с PyYAML, requests, numpy, dulwich и playwright. Папка программы — BRAIN_APP или две папки выше."""
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
    raise SystemExit("Не найдена папка программы: укажите её в переменной BRAIN_APP")


APP = _app_dir()
OBS = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OBSIDIAN_DIR", "/data/obs/obsidian-1.15.0"))
ROOT = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/real")
PROG, VAULT, CFG, SHOTS = ROOT / "prog", ROOT / "vault", ROOT / "cfg", ROOT / "shots"
PID = "vtoroy-mozg"
PORT = int(os.environ.get("REAL_PORT", "9333"))
DISPLAY = os.environ.get("REAL_DISPLAY", ":99")
DEPS = os.environ.get("BRAIN_DEPS") or ("/data/brain/_deps" if Path("/data/brain/_deps").exists() else "")
PASSED: list = []
CONSOLE: list = []  # (окно, тип, текст)
ALLOWED = ["проверка отчёта об ошибке"]  # ошибка, которую тест вызывает сам


SRC = next((p for p in (E2E.parent / "src", E2E.parent / "plugin" / "src") if (p / "main.ts").exists()), None)
DTS = SRC.parent / "node_modules" / "obsidian" / "obsidian.d.ts" if SRC else None
# методы, которые Obsidian и ждёт от плагина (их и надо переопределять)
OVERRIDES = {"onload", "onunload", "display", "hide", "onOpen", "onClose", "getViewType", "getDisplayText", "getIcon",
             "getItems", "getItemText", "onChooseItem", "getSuggestions", "renderSuggestion", "onChooseSuggestion"}
# поля, которые Obsidian заводит с тем же значением, что и плагин (проверяется отдельно, что значение то же)
SAME_VALUE = {"PluginSettingTab": {"plugin"}}


def _top_level(s: str, start: int) -> tuple[str, int]:
    """Текст тела класса на первом уровне скобок (без строк и комментариев); start — индекс «{»."""
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
    """Классы плагина: имя → (класс Obsidian, от которого он унаследован; свои имена полей и методов)."""
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
    """obsidian.d.ts: класс или интерфейс → его открытые имена вместе с унаследованными (это API, его можно трогать)."""
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


# ---------- подготовка: программа, хранилище, конфиг Obsidian, установка командой setup ----------
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
    arch = VAULT / "_staging" / "архив"
    arch.mkdir(parents=True)
    (arch / "дневник 2023.txt").write_text(
        "02.04.2023\n\nСегодня посадил томаты в теплице на даче. Полив каждый день вечером.\n\n"
        "Метеостанцию можно поставить в теплицу на даче — следить за влажностью.\n", encoding="utf-8")
    (arch / "пекарня.txt").write_text(
        "10.05.2023\n\nДумаю открыть маленькую пекарню у дома. Себестоимость буханки хлеба — 50 рублей.\n", encoding="utf-8")
    (CFG / "obsidian").mkdir(parents=True)
    (CFG / "obsidian" / "obsidian.json").write_text(json.dumps(
        {"vaults": {"a1b2c3d4e5f60708": {"path": str(VAULT), "ts": int(time.time() * 1000), "open": True}}, "updateDisabled": True}),
        encoding="utf-8")
    step("Установка: команда setup (её запускает «Установка.bat»)")
    e = env()
    e.update({"BRAIN_OBSIDIAN_CONFIG": str(CFG / "obsidian"), "BRAIN_NO_OPEN": "1", "BRAIN_OBSIDIAN_RUNNING": "0"})
    for n in ("Фаза 1.bat", "Обновить.bat"):
        (PROG / n).write_text("@echo off\r\n", encoding="utf-8")
    r = subprocess.run([str(PROG / ".venv" / "bin" / "python"), "-X", "utf8", "-m", "brain", "setup"], cwd=PROG,
                       capture_output=True, text=True, env=e, timeout=120, stdin=subprocess.DEVNULL)
    print(r.stdout.strip())
    ok(r.returncode == 0 and "Плагин установлен" in r.stdout, "setup: плагин установлен в хранилище из obsidian.json")
    ok(not list(PROG.glob("*.bat")), "setup: .bat-файлы прежних версий убраны")
    data = json.loads((VAULT / ".obsidian" / "plugins" / PID / "data.json").read_text(encoding="utf-8"))
    ok(data["programDir"] == str(PROG), "в data.json плагина — папка программы")


# ---------- запуск Obsidian ----------
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
                          f"--remote-debugging-port={PORT}", "--lang=ru"], cwd=OBS, env=e, stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1).read()
            return p
        except OSError:
            time.sleep(0.5)
    raise SystemExit("Obsidian не открыл порт отладки — см. " + str(ROOT / "obsidian.log"))


# ---------- помощники ----------
class W:
    """Окна Obsidian (страницы CDP)."""
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
    raise AssertionError(f"не дождался: {what or expr[:150]}" + (f" ({last})" if last else ""))


async def find_page(pred: str, timeout=15):
    """Окно, в котором выполняется условие (JS), — например, то, где открыты настройки."""
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
    raise AssertionError(f"нет окна, где {pred[:120]}")


P = f"app.plugins.plugins['{PID}']"


async def wait_idle(timeout=180):
    await asyncio.sleep(0.4)
    await until(f"() => {P} && !{P}.engine.busy() && !{P}.engine.current", timeout, what="запуски программы закончились")


async def last_job():
    return await js(f"() => {{ const j = {P}.engine.history[0]; return j && {{label: j.label, status: j.status, ok: j.result && j.result.ok,"
                    " error: j.result && j.result.error, lines: j.lines.slice(-8)}; }")


async def ui():
    return json.loads((VAULT / ".system" / "ui.json").read_text(encoding="utf-8"))


async def shot(name, page=None):
    await asyncio.sleep(0.3)
    await (page or W.main).screenshot(path=str(SHOTS / f"{len(list(SHOTS.glob('*.png'))) + 1:02d}-{name}.png"))


async def focus(page):
    """Окно — на передний план (как щелчок по нему): Obsidian открывает свои окна-диалоги в активном окне."""
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
    raise AssertionError("settings.yaml: не дождался — " + what)


def sitem(page, name, scope=".vm-settings"):
    return page.locator(f"{scope} .setting-item").filter(has=page.locator(".setting-item-name", has_text=name)).first


async def settings_loaded(page):
    await until("() => { const b = document.querySelector('.vm-settings .vm-set-body');"
                " return b && !b.textContent.includes('Загружаю настройки программы') && b.querySelectorAll('.setting-item').length > 0; }",
                30, page, "настройки программы загружены")


async def check_tabs(page, where, shots_prefix=None):
    tabs = [t.strip() for t in await page.locator(".vm-settings .vm-set-tab").all_inner_texts()]
    ok(tabs == ["Основное", "Модели", "Пороги", "Входящие", "Документы", "Расходы", "Дополнительно"], f"{where}: вкладки {', '.join(tabs)}")
    for name in tabs:
        await page.locator(".vm-settings .vm-set-tab", has_text=name).first.click()
        await asyncio.sleep(0.35)
        n_items = await page.locator(".vm-settings .vm-set-body .setting-item").count()
        n_err = await page.locator(".vm-settings .vm-error-box").count()
        ok(n_items > 0 and n_err == 0, f"{where}: «{name}» — {n_items} настроек, без ошибок")
        if shots_prefix:
            await shot(f"{shots_prefix}-{name}", page)


async def profile_add_delete(page, where):
    """«＋ Локальный» → профиль в settings.yaml → удаление с подтверждением (в каком окне диалог)."""
    await page.locator(".vm-settings .vm-set-tab", has_text="Модели").first.click()
    await until("() => !!document.querySelector('.vm-settings .vm-prof-editor')", 10, page, "редактор профилей")
    await click_text(page, "＋ Локальный", ".vm-settings")
    await until_yaml(lambda s: any(p.get("kind") == "local" for p in s["llm"]["profiles"]), "локальный профиль добавлен")
    ok(True, f"{where}: «＋ Локальный» — профиль записан в settings.yaml")
    await sitem(page, "Профиль для правки").locator(".extra-setting-button").first.click()
    dlg = await find_page("() => [...document.querySelectorAll('.modal-container .modal')].some(m => m.textContent.includes('Удалить профиль?'))", 8)
    same = dlg == page
    ok(same, f"{where}: подтверждение удаления открылось в том же окне, что и настройки")
    await dlg.locator(".modal-container .modal", has_text="Удалить профиль?").locator("button", has_text="Удалить").first.click()
    await until_yaml(lambda s: not any(p.get("kind") == "local" for p in s["llm"]["profiles"]), "локальный профиль удалён")
    ok(True, f"{where}: профиль удалён после подтверждения")


async def own_model(page):
    """«Где считать: на этом компьютере» — блок «Своя модель» и окно «Запустить модель…» (без запуска)."""
    saved = (PROG / "settings.yaml").read_text(encoding="utf-8")
    await page.locator(".vm-settings .vm-set-tab", has_text="Модели").first.click()
    await asyncio.sleep(0.3)
    where = page.locator(".vm-settings .vm-set-body .setting-item:visible").filter(
        has=page.locator(".setting-item-name", has_text="Где считать")).first
    await where.scroll_into_view_if_needed()
    await where.locator("select.dropdown:not(.is-measuring)").select_option("local")  # в 1.15 рядом — скрытый «измерительный»
    await until_yaml(lambda s: s["embeddings"]["mode"] == "local", "эмбеддинги — на этом компьютере")
    await until("() => (document.querySelector('.vm-settings .vm-llama-box') || {}).textContent?.includes('Сервер:')",
                40, page, "блок «Своя модель»")
    box = page.locator(".vm-settings .vm-llama-box")
    await until("() => !(document.querySelector('.vm-settings .vm-llama-box') || {}).textContent?.includes('не этот сервер')",
                20, page, "блок «Своя модель» перечитал адрес после сохранения")
    ok(True, "после смены «Где считать» блок перечитал состояние: адрес по умолчанию — это свой сервер")
    txt = await box.inner_text()
    ok("не скачана" in txt and await box.locator("button", has_text="Запустить модель…").count() == 1,
       "блок «Своя модель»: модель не скачана, есть «Запустить модель…»")
    await box.scroll_into_view_if_needed()
    await shot("своя-модель", page)
    await box.locator("button", has_text="Запустить модель…").click()
    dlg = await find_page("() => !!document.querySelector('.modal.vm-llama-modal')", 10)
    ok(dlg == page, "окно «Запустить модель…» открылось в окне настроек")
    await until("() => !!document.querySelector('.vm-llama .vm-llama-hw-grid')", 40, dlg, "что есть у компьютера")
    m = dlg.locator(".modal.vm-llama-modal")
    ram = m.locator(".vm-llama-ram")
    ok(await ram.count() == 1 and "16 ГБ" in await ram.inner_text() and "4 096" in (await ram.inner_text()).replace("\u00a0", " "),
       "окно запуска: предупреждение «минимум 16 ГБ» и сколько займёт модель с контекстом 4096")
    opt = await m.locator(".setting-item", has_text="Контекст").locator("select.dropdown:not(.is-measuring) option[value='8192']").inner_text()
    ok("9,6 ГБ" in opt, f"варианты контекста — с памятью: {opt}")
    await shot("окно-запуска-модели", dlg)
    await m.locator(".vm-modal-buttons button", has_text="Отмена").click()
    await asyncio.sleep(0.3)
    ok(await dlg.locator(".modal.vm-llama-modal").count() == 0, "«Отмена» закрыла окно, ничего не запуская")
    (PROG / "settings.yaml").write_text(saved, encoding="utf-8")


# ---------- сценарий ----------
async def scenario():
    page = W.main
    step("1. Obsidian открыл хранилище; доверие плагинам; панель и мастер")
    btn = None
    t0 = time.time()
    while time.time() - t0 < 30 and not btn:
        if await page.locator("button", has_text="Довериться автору и включить плагины").count():
            btn = page.locator("button", has_text="Довериться автору и включить плагины").first
        else:
            if await js(f"() => !!(window.app && {P})"):
                break
            await asyncio.sleep(0.3)
    if btn:
        await shot("доверие-плагинам")
        await btn.click()
        ok(True, "диалог «Доверяете ли вы автору этого хранилища?» — нажата «Довериться автору и включить плагины»")
    await until(f"() => !!(window.app && {P} && {P}.engine)", 30, what="плагин загружен")
    await asyncio.sleep(1)
    await js("() => app.setting.close()")  # после «Довериться…» Obsidian открывает «Сторонние плагины»
    # класс Modal — самый верхний в цепочке окна настроек, у кого свои open и onOpen; его open запоминает открытые окна
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
    ok(await js(f"() => {P}.manifest.version") == man["version"], f"плагин {man['version']} загружен в Obsidian {ver}")
    await until("() => !!document.querySelector('.vm-view .vm-wizard')", 30, what="панель с мастером первой загрузки")
    await wait_idle()
    ok("Фаза 1" in await page.locator(".vm-step.is-current .vm-step-title").inner_text(), "мастер: текущий шаг — Фаза 1")
    ok("Второй мозг" in await page.locator(".status-bar").inner_text(), "строка состояния: «Второй мозг»")
    await shot("панель-мастер")

    step("2. Фаза 1 → черновик структуры → утверждение")
    await focus(page)
    await click_text(page, "Запустить Фазу 1", ".vm-view")
    await wait_idle()
    j = await last_job()
    ok(j and j["ok"], f"Фаза 1 отработала: {j and j['lines'][-1:]}")
    u = await ui()
    ok(u["status"]["structure_pending"] and u["status"]["draft"], "черновик структуры ждёт утверждения")
    await click_text(page, "Открыть черновик", ".vm-view")
    await until("() => (app.workspace.getActiveFile()?.path || '').includes('структура')", 10, what="черновик открыт")
    ok(True, "черновик открылся в редакторе Obsidian")
    await click_text(page, "Утвердить структуру", ".vm-view")
    m = page.locator(".modal-container .modal", has_text="Утвердить структуру?")
    await m.wait_for(state="visible", timeout=10000)
    await shot("утвердить-структуру")
    await m.locator("button", has_text="Утвердить и продолжить").click()
    await wait_idle()
    u = await ui()
    ok(u["status"]["approved_once"] and not u["status"]["structure_pending"] and len(u["containers"]) >= 2,
       f"структура утверждена, контейнеры: {', '.join(c['title'] for c in u['containers'])}")
    await until(f"() => document.querySelectorAll('.vm-view .vm-tree-row').length === {len(u['containers'])}", 10,
                what="дерево контейнеров в панели")
    ok(True, "дерево контейнеров в панели")
    await shot("панель-обзор")

    step("3. Вкладки панели")
    for name in ("Вопросы", "Контейнер", "Расходы", "Журнал", "Обзор"):
        await page.locator(".vm-view .vm-tab", has_text=name).first.click()
        await asyncio.sleep(0.4)
        txt = await page.locator(".vm-view .vm-body").inner_text()
        ok(txt.strip() and not await page.locator(".vm-view .vm-error-box").count(), f"вкладка «{name}» нарисована")
        if name in ("Вопросы", "Расходы"):
            await shot(f"панель-{name}")

    step("4. Настройки в отдельном окне (так в Obsidian 1.15 по умолчанию)")
    ok(await js("() => app.vault.getConfig('settingsPopoutWindow')") is True, "в Obsidian включено «Открывать настройки в отдельном окне»")
    await page.locator(".vm-view .vm-head-tools .vm-icon-btn").nth(1).click()
    sp = await find_page("() => !!document.querySelector('.vm-settings .vm-set-tab')", 20)
    watch(sp, "окно настроек")
    await focus(sp)
    ok(sp != page, f"настройки открылись в отдельном окне («{await sp.title()}»)")
    await settings_loaded(sp)
    nav = sp.locator(".vertical-tab-nav-item", has_text="Второй мозг")
    ok(await nav.count() == 1 and "is-active" in (await nav.first.get_attribute("class") or ""),
       "в меню слева — пункт «Второй мозг», он выбран")
    heads = await sp.locator(".vm-settings .setting-item-heading .setting-item-name").all_inner_texts()
    ok(all(h in heads for h in ("Программа", "Уведомления Windows", "Обновления")), "«Основное»: " + ", ".join(heads))
    ok("Программа найдена" in await sp.locator(".vm-settings .vm-callout").first.inner_text(), "«Программа найдена»")
    await check_tabs(sp, "окно настроек", "настройки")
    # поиск
    await sp.locator(".vm-settings input.vm-set-search").fill("бюджет")
    await asyncio.sleep(0.4)
    names = await sp.locator(".vm-settings .vm-search-pane:not(.vm-hidden) .setting-item:not(.setting-item-heading):not(.vm-hidden) .setting-item-name").all_inner_texts()
    ok("Месячный бюджет, $" in names, f"поиск «бюджет»: {', '.join(names)}")
    await shot("настройки-поиск", sp)
    await sp.locator(".vm-settings input.vm-set-search").fill("")
    await asyncio.sleep(0.3)
    # пороги: поле и ползунок
    await sp.locator(".vm-settings .vm-set-tab", has_text="Пороги").first.click()
    await asyncio.sleep(0.3)
    item = sp.locator(".vm-settings .setting-item").filter(has=sp.locator("input.vm-set-range")).first
    num = item.locator("input.vm-num")
    rs = item.locator(".vm-reset")

    async def reset_state():
        return (await rs.get_attribute("class") or "", float(await rs.evaluate("(e) => getComputedStyle(e).opacity")),
                await rs.is_visible())
    cls, op, vis = await reset_state()
    ok(vis and "vm-reset-off" in cls and "is-disabled" in cls and op < 0.6,
       f"↺ видна и при умолчании — тусклая и неактивная (прозрачность {op:g})")
    await shot("порог-по-умолчанию", sp)
    await rs.click(force=True)
    await asyncio.sleep(0.3)
    ok(await num.input_value() == "70", "неактивная ↺ ничего не меняет")
    await num.fill("77")
    await until_yaml(lambda s: s["thresholds"]["classification"] == 77, "порог классификации = 77")
    ok(True, "порог изменён в поле — записан в settings.yaml (77)")
    cls, op, vis = await reset_state()
    ok("vm-reset-off" not in cls and "is-disabled" not in cls and op > 0.9, f"порог изменён — ↺ яркая и активная (прозрачность {op:g})")
    await shot("порог-изменён", sp)
    await rs.click()
    await until_yaml(lambda s: "classification" not in (s.get("thresholds") or {}) or s["thresholds"]["classification"] == 70,
                     "порог возвращён к умолчанию")
    await asyncio.sleep(0.3)
    cls, op, vis = await reset_state()
    ok("vm-reset-off" in cls and op < 0.6, "↺ вернула порог к умолчанию и снова потускнела")
    await profile_add_delete(sp, "окно настроек")
    # проверка связи из настроек
    await click_text(sp, "Проверить связь", ".vm-settings")
    chk = await find_page("() => !!document.querySelector('.modal-container .vm-check-item')", 10)
    ok(chk == sp, "«Проверить связь» открылась в окне настроек")
    await until("() => document.querySelectorAll('.modal-container .vm-check-item').length >= 2"
                " && !document.querySelector('.modal-container .vm-wait')", 60, chk, "результаты проверки связи")
    n_ok, n_bad = await chk.locator(".vm-check-item.is-ok").count(), await chk.locator(".vm-check-item.is-bad").count()
    ok(n_bad == 0, f"проверка связи: {n_ok} ✓, {n_bad} ✗")
    await shot("проверка-связи", chk)
    await chk.locator(".modal-container .vm-modal-buttons button", has_text="Закрыть").click()
    await asyncio.sleep(0.3)
    await own_model(sp)
    await js("() => app.setting.close()")
    for _ in range(50):
        if sp.is_closed():
            break
        await asyncio.sleep(0.2)
    ok(sp.is_closed(), "окно настроек закрылось")

    step("5. Настройки модальным окном (если «Открывать настройки в отдельном окне» выключено)")
    await focus(page)
    await js("() => app.vault.setConfig('settingsPopoutWindow', false)")
    await js(f"() => {P}.openSettings('main')")
    await until("() => !!document.querySelector('.modal.mod-settings .vm-settings .vm-set-tab')", 15, page, "настройки в модальном окне")
    await settings_loaded(page)
    nav = page.locator(".modal.mod-settings .vertical-tab-nav-item", has_text="Второй мозг")
    ok(await nav.count() == 1 and "is-active" in (await nav.first.get_attribute("class") or ""), "модальное окно: пункт «Второй мозг» в меню")
    await check_tabs(page, "модальное окно")
    await page.locator(".vm-settings .vm-set-tab", has_text="Основное").first.click()
    await shot("настройки-модальные")
    await profile_add_delete(page, "модальное окно")
    await js("() => app.setting.close()")
    await js("() => app.vault.setConfig('settingsPopoutWindow', true)")

    step("6. Новая мысль")
    await focus(page)
    await js(f"() => app.commands.executeCommandById('{PID}:new-thought')")
    m = page.locator(".modal-container .modal").filter(has=page.locator("textarea")).last
    await m.wait_for(state="visible", timeout=10000)
    await m.locator("textarea").fill("Для метеостанции нужен второй датчик — проверить на балконе.")
    ok(not await m.locator("#vm-now").is_checked(), "флажок «Сразу обработать (Фаза 1)» по умолчанию выключен")
    await m.locator("#vm-now").check()
    await shot("новая-мысль")
    await m.locator("button", has_text="Сохранить").click()
    await asyncio.sleep(0.5)
    await wait_idle()
    srcs = [p for p in (VAULT / "_исходники").glob("*.txt") if "второй датчик" in p.read_text(encoding="utf-8")]
    ok(srcs, "мысль сохранена в _staging и обработана Фазой 1")
    await js(f"() => app.commands.executeCommandById('{PID}:revalidate')")
    await page.locator(".prompt .suggestion-item", has_text="Все контейнеры").first.wait_for(state="visible", timeout=10000)
    ok(await page.locator(".prompt .suggestion-item").count() >= 2, "«Ревалидация…»: выбор контейнера открылся")
    await page.keyboard.press("Escape")

    step("7. Ошибка в плагине: на месте, в журнале, «Скопировать отчёт»")
    await js(f"() => {{ const v = [...{P}.views][0]; v.renderUsageTab = () => {{ throw new Error('проверка отчёта об ошибке'); }}; }}")
    await page.locator(".vm-view .vm-tab", has_text="Расходы").first.click()
    box = page.locator(".vm-view .vm-error-box")
    await box.wait_for(state="visible", timeout=5000)
    ok("Ошибка в плагине (панель, вкладка «Расходы»)" in await box.inner_text(), "ошибка вкладки показана на месте, остальное работает")
    await shot("ошибка-плагина")
    await box.locator("button", has_text="Скопировать отчёт").click()
    await asyncio.sleep(0.5)
    clip = await js("() => require('electron').clipboard.readText()")
    ok(clip.startswith("Второй мозг — ошибка плагина") and f"Obsidian: {ver}" in clip and "plugin:vtoroy-mozg" in clip,
       "в буфере обмена — отчёт: версии и ошибка со стеком")
    plog = VAULT / "_логи" / "плагин.log"
    await until("() => true", 1)
    ok(plog.exists() and "проверка отчёта об ошибке" in plog.read_text(encoding="utf-8"), "ошибка записана в _логи/плагин.log")
    await js(f"() => {{ const v = [...{P}.views][0]; delete v.renderUsageTab; v.render(true); }}")
    ok(await box.count() == 0, "после исправления вкладка снова рисуется")

    step("8. Отчёт для разработчика")
    await js(f"() => app.commands.executeCommandById('{PID}:report')")
    await until("() => app.workspace.getActiveFile()?.path === '_логи/отчёт для разработчика.md'", 15, what="отчёт открыт")
    rep = (VAULT / "_логи" / "отчёт для разработчика.md").read_text(encoding="utf-8")
    ok(f"Obsidian: {ver}" in rep and "проверка отчёта об ошибке" in rep and "### Фаза 1" in rep, "отчёт: версии, ошибки плагина, последние запуски")
    ok((await js("() => require('electron').clipboard.readText()")).startswith("# Второй мозг — отчёт для разработчика"),
       "отчёт и в буфере обмена")
    await shot("отчёт")

    step("9. Консоль всех окон Obsidian")
    bad = [c for c in CONSOLE if c[1] in ("error", "pageerror") and not any(a in c[2] for a in ALLOWED)]
    mine = [c for c in bad if "vtoroy" in c[2] or "Второй мозг" in c[2] or "plugin:" in c[2]]
    for c in bad:
        print("  консоль:", c[0], c[1], c[2][:300])
    ok(not mine, "ошибок плагина в консоли нет" + (f": {mine[:3]}" if mine else ""))

    step("10. Имена в классах плагина не совпадают с внутренними именами Obsidian")
    # Obsidian 1.13+ завёл у вкладки настроек свои renderTab() и navEl — такие же имена в плагине 2.5 ломали настройки.
    # Здесь: имена из исходников плагина против имён настоящего Obsidian (цепочка классов и поля пустого экземпляра)
    # за вычетом открытого API из obsidian.d.ts.
    rt = await js(f"""() => {{
      const P = {P};
      const leaf = app.workspace.getLeavesOfType('vtoroy-mozg-panel')[0];
      const up = (o, n) => {{ let q = o; for (let i = 0; i < n; i++) q = q && Object.getPrototypeOf(q); return q; }};
      const names = (proto, args) => {{
        if (!proto) return null;
        const s = new Set(); let q = proto;
        while (q && q !== Object.prototype) {{ for (const n of Object.getOwnPropertyNames(q)) s.add(n); q = Object.getPrototypeOf(q); }}
        // пустой экземпляр — через подкласс-заглушку: у абстрактных классов конструктор зовёт getViewType() и т. п.
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
    ok(await js(f"() => {P}.brainTab.plugin === {P}"), "у вкладки настроек поле plugin — тот же плагин, что заводит Obsidian")
    (ROOT / "obsidian-names.json").write_text(json.dumps({"obsidian": ver, **rt}, ensure_ascii=False, indent=1), encoding="utf-8")
    api = documented()
    if not api:
        print("  (obsidian.d.ts не найден — открытое API не вычитается, сравнение строже)")
    classes = plugin_classes()
    ok(len(classes) >= 5, f"классы плагина: {len(classes)} ({', '.join(sorted(classes))})")
    for base in sorted({b for b, _ in classes.values()}):
        ob = rt.get(base)
        bad_ctor = [n for n in ob or [] if n.startswith("!")]
        ok(ob is not None and not bad_ctor, f"класс Obsidian «{base}» найден, его пустой экземпляр создаётся"
           + (f": {bad_ctor[0]}" if bad_ctor else ""))
    for cls, (base, mine_names) in sorted(classes.items()):
        internal = set(rt[base]) - api.get(base, set())
        clash = sorted((mine_names & internal) - OVERRIDES - SAME_VALUE.get(base, set()))
        ok(not clash, f"{cls} ({base}): {len(mine_names)} своих имён, ни одно не совпадает с {len(internal)} внутренними именами Obsidian"
           + (f" — СОВПАДАЮТ: {', '.join(clash)}" if clash else ""))


async def main():
    prepare()
    proc = launch()
    code = 0
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        W.ctx = browser.contexts[0]
        W.ctx.on("page", lambda p: watch(p))
        W.main = await find_page("() => location.href.includes('index.html') && !!window.app", 60)
        watch(W.main, "главное окно")
        try:
            await scenario()
            print(f"\nВСЁ ПРОШЛО: {len(PASSED)} ✓ (скриншоты: {SHOTS})")
        except Exception:  # noqa: BLE001
            code = 1
            traceback.print_exc()
            try:
                for i, p in enumerate(W.ctx.pages):
                    await p.screenshot(path=str(SHOTS / f"ОШИБКА-{i}.png"))
            except Exception:  # noqa: BLE001
                pass
            for c in CONSOLE[-15:]:
                print("  консоль:", c[0], c[1], c[2][:500])
    if not os.environ.get("REAL_KEEP"):
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            pass
    return code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

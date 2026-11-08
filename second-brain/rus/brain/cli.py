"""Команды программы (раздел 20): run — Фаза 1, synth — Фаза 2, check, status, revalidate, patterns."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

from . import __version__
from . import interact
from . import util as U
from .config import load_config
from .util import ManualPending, UserError

RESULT: dict = {}  # ответ для плагина (флаг --json): в конце вывода строка «@@RESULT {…}»
PLUGIN_ID = "vtoroy-mozg"
PLUGIN_FILES = ("main.js", "manifest.json", "styles.css")

HELP = """Второй мозг — команды:
  run                     Фаза 1: принять ответы на вопросы и обработать всё новое из _staging
                          (большой запуск — сначала оценка и вопрос; --yes — без вопроса)
  synth [контейнер]       Фаза 2: написать или обновить документы контейнера (без названия — выбор из списка);
                          если с прошлого синтеза ничего не менялось, модель не вызывается (--force — переписать всё равно)
  check                   проверить настройки, модели и эмбеддинги
  status                  что сейчас в работе: записи, вопросы, очереди, расходы
  usage                   расходы по моделям: за сегодня, месяц, всего, по профилям и шагам
                          (--reprice <профиль|emb|all> — пересчитать стоимость прошлых обращений по текущим ценам)
  estimate run | synth <контейнер> | revalidate [контейнер]
                          оценка запуска: обращения к модели, время, стоимость — без запуска
  revalidate [контейнер]  глубокая перепроверка классификации (без названия — все записи;
                          --ask — выбрать из списка, --yes — без вопроса о подтверждении)
  patterns                поиск новых составных типов аспектов
  update                  обновить программу с GitHub (репозиторий — UPDATE_REPO в brain/__init__.py;
                          --check — только проверить)
  llama status | start | stop | download
                          своя модель эмбеддингов на llama.cpp (в плагине — «Запустить модель…»): что скачано и
                          запущено; запустить (что нужно — скачать; --params-json - — параметры запуска JSON-ом);
                          остановить; только скачать модель и llama.cpp
  setup                   установка «всё в одном» (её запускает Установка.bat): настройки, плагин в хранилище Obsidian,
                          уборка файлов прежних версий, модель эмбеддингов
  install-plugin [папка]  только установить плагин «Второй мозг» в хранилище Obsidian
Для плагина: snapshot, answer <Q> --option N | --text …, advise <контейнер>,
  settings --set-json - | --key profile:<id> | embeddings.
Общие параметры: --settings <путь к settings.yaml> (по умолчанию — рядом с программой);
  --vault <папка> — другое хранилище (settings.yaml не меняется); --json — итог строкой @@RESULT для плагина;
  --ask-stdin — вопросы посреди запуска строкой @@ASK, ответ — строкой в стандартный ввод (для плагина).
"""


class RunLock:
    """Не даёт запустить два прогона одновременно над одним хранилищем."""

    def __init__(self, path):
        self.path = path
        self.f = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.path, "a+")
        try:
            self.f.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            raise UserError("Программа уже работает с этим хранилищем в другом окне. Дождитесь окончания или закройте то окно.")
        stop = self.path.parent / "stop"
        if stop.exists():  # «Стоп», нажатый, когда программа уже закончила, — не должен остановить следующий запуск
            try:
                stop.unlink()
            except OSError:
                pass
        return self

    def __exit__(self, *a):
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            self.f.close()
        except OSError:
            pass


def _lock_path(cfg) -> Path:
    """Блокировка берётся до загрузки состояния: иначе второй запуск мог бы работать со старой копией."""
    if not cfg.vault.exists():
        raise UserError(f"Не найдена папка хранилища: {cfg.vault}. Проверьте строку vault в settings.yaml.")
    return cfg.vault / ".system" / "lock"


def _ctx(cfg, need_llm=True, cmd=""):
    from .context import Ctx
    if not cfg.vault.exists():
        raise UserError(f"Не найдена папка хранилища: {cfg.vault}. Проверьте строку vault в settings.yaml.")
    return Ctx(cfg, need_llm=need_llm, cmd=cmd)


def _execute(ctx, fn, empty: str = "Нового ничего не было.") -> int:
    """Общий запуск шага: ручной режим (ждёт веб-чат), «Стоп» (файл .system/stop или Ctrl+C), бюджет, итог."""
    code = 0
    try:
        fn()
        title = "Готово"
        if ctx.result.get("cancelled"):
            title, empty = "Отменено", "Ничего не изменено."
    except ManualPending as e:
        title = "Остановлено до ответа из веб-чата"
        ctx.notices.append(str(e))
        RESULT["webchat"] = True
    except U.BudgetStop as e:
        title = "Остановлено: исчерпан бюджет"
        ctx.notices.append(e.text)
        RESULT.update({"stopped": True, "budget_stop": True})
        code = 1
    except KeyboardInterrupt:
        title = "Остановлено"
        ctx.notices.append("Всё, что успело обработаться, сохранено — следующий запуск продолжит с этого места.")
        RESULT["stopped"] = True
        code = 1
    t = ctx.meter.totals()
    if t["calls"] or ctx.stats:
        ctx.logs.change("программа", f"{RUN_NAMES.get(ctx.meter.cmd, ctx.meter.cmd or 'запуск')}: {title.lower()} — "
                        + _run_line(t))
    ctx.finish()
    _summary(ctx, title, empty)
    return code


RUN_NAMES = {"run": "Фаза 1", "synth": "Фаза 2", "revalidate": "Ревалидация", "patterns": "Поиск составных типов",
             "advise": "Совет по порогам", "answer": "Ответ на вопрос", "check": "Проверка"}


def _run_line(t: dict) -> str:
    """«длительность 3 мин 12 с; обращений к моделям 25; токенов 120 000 → 9 000; $0.14»"""
    from .usage import money, num
    parts = [f"длительность {U.duration(t['elapsed'])}"]
    if t["calls"]:
        parts.append(f"обращений к моделям {t['calls']}")
        parts.append(f"токенов {num(t['in'])} → {num(t['out'])}" + (f" (из кэша {num(t['cached'])})" if t["cached"] else ""))
        if t["cost"]:
            parts.append(money(t["cost"]) + (" без части обращений (нет цен)" if t["unpriced"] else ""))
        elif t["unpriced"]:
            parts.append("стоимость не посчитана — нет цен в профиле")
    return "; ".join(parts)


def _estimate(fn, *a):
    """Оценка не должна мешать запуску: если посчитать не вышло — запускаем без неё."""
    try:
        return fn(*a)
    except UserError:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"  ! оценку запуска посчитать не удалось: {e}")
        return None


def _confirm(ctx, e: dict | None, always: bool = False, fallback: list[str] | None = None) -> bool:
    """Большой запуск (или ревалидация — всегда): показать оценку и спросить. Спросить нельзя — запуск идёт."""
    from . import estimate as ES
    if e:
        RESULT["estimate"] = e
    if not always and (not e or not ES.over(ctx.cfg, e)):
        return True
    lines = (e or {}).get("lines") or fallback or []
    title = (e or {}).get("title") or "Запуск"
    if interact.STATE["ask"] != "tty":
        print(f"Оценка запуска ({title}):")
        for ln in lines:
            print("  " + ln)
    if not interact.can_ask():
        return True
    ch = interact.ask("estimate", "Ревалидация" if always else "Большой запуск",
                      f"{title}: оценка грубая — точнее станет ясно по ходу работы. Запустить?",
                      ["Запустить", "Отмена"], default=0, lines=lines)
    return ch == 0


def _cancelled() -> int:
    print("Отменено — ничего не изменено.")
    RESULT.update({"title": "Отменено", "cancelled": True})
    return 0


def _summary(ctx, title: str, empty: str = "Нового ничего не было."):
    s = ctx.stats
    w = ctx.w
    parts = []
    names = [("files", "принято файлов"), ("items_classified", "разобрано файлов"), ("placed", "записей разложено"),
             ("quarantined", "на проверку"), ("unsorted", "без контейнера"), ("containers_created", "новых контейнеров"),
             ("compacted", "уплотнено"), ("aspects", "аспектов извлечено"), ("composites", "составных собрано"),
             ("duplicates", "дублей связано"), ("bases", "баз синтеза собрано"), ("products", "документов написано"),
             ("answers", "ответов принято")]
    for k, label in names:
        if s.get(k):
            parts.append(f"{label}: {s[k]}")
    print()
    print(f"{title} — " + "; ".join(parts) + "." if parts else (f"{title}. {empty}" if empty else f"{title}."))
    calls = sum((ctx.llm.calls if ctx.llm else {}).values())
    if calls:
        print(f"Обращений к модели: {calls} (" + ", ".join(f"{k} — {v}" for k, v in ctx.llm.calls.items()) + ").")
    t = ctx.meter.totals()
    line = _run_line(t)
    print(line[:1].upper() + line[1:] + ".")
    nq = len(ctx.q.open)
    if nq:
        print(f"Открытых вопросов: {nq} — файл open-questions.md в хранилище.")
    for wmsg in dict.fromkeys(w.warnings):
        print(f"  ! {wmsg}")
    for n in ctx.notices:
        print(f"  • {n}")
    RESULT.update({"title": title, "stats": dict(s), "calls": dict(ctx.llm.calls) if ctx.llm else {},
                   "notices": list(ctx.notices), "warnings": list(dict.fromkeys(w.warnings)), "questions": nq,
                   "messages": list(ctx.messages), "run_usage": t, "elapsed": t["elapsed"], "run_id": ctx.meter.run_id})
    RESULT.update(ctx.result)


def cmd_run(cfg, args):
    from . import estimate, phase1
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, cmd="run")
        print(f"Фаза 1 · хранилище {cfg.vault}", flush=True)
        if not args.yes and not _confirm(ctx, _estimate(estimate.run, ctx)):
            return _cancelled()
        return _execute(ctx, lambda: phase1.run(ctx))


def _pick_container(ctx, name: str | None, cmd: str = "synth"):
    """Контейнер по названию или выбор из списка в консоли. Для Фазы 2 — только контейнеры с базой синтеза,
    для совета по порогам (cmd="advise") — все."""
    w = ctx.w
    if name:
        n = w.resolve_container(name)
        if n is None:
            cands = [x for x in w.nodes.values() if name.lower() in x.title.lower()]
            if len(cands) == 1:
                return cands[0]
            raise UserError(f"Контейнер «{name}» не найден." + (" Похожие: " + ", ".join(c.title for c in cands[:10]) if cands else ""))
        return n
    nodes = sorted(w.nodes.values(), key=lambda x: (w.path_key(x).lower()))
    advise = cmd == "advise"
    if advise:
        if not nodes:
            raise UserError("Контейнеров пока нет — сначала утвердите структуру.")
    else:
        nodes = [n for n in nodes if w.base(n.id)]
        if not nodes:
            raise UserError("Пока ни у одного контейнера нет базы синтеза — сначала запустите Фазу 1.")
    need = f"Укажите название контейнера: {cmd} \"Название\"."
    if not _interactive():
        raise UserError(need)
    print("Для какого контейнера посоветовать пороги?" if advise else "Для какого контейнера написать документы?")
    for i, n in enumerate(nodes, 1):
        mark = " (база устарела — нужна Фаза 1)" if not advise and n.id in w.state["dirty"] else ""
        print(f"  {i:>3}. {'   ' * w.depth(n)}{n.title}{mark}")
    if not sys.stdin or not sys.stdin.isatty():
        raise UserError(need)
    while True:
        s = input("Номер (или пусто — выйти): ").strip()
        if not s:
            raise UserError("Отменено.")
        if s.isdigit() and 1 <= int(s) <= len(nodes):
            return nodes[int(s) - 1]
        print("Нет такого номера.")


def _interactive() -> bool:
    return bool(sys.stdin and sys.stdin.isatty())


def _ask_force(msg: str) -> bool:
    """Документы актуальны: в консоли без флага --force — спрашиваем, переписать ли."""
    print(msg)
    return input("Переписать их всё равно? Это потратит обращения к модели (д/н): ").strip().lower() in ("д", "да", "y", "yes", "l")


def cmd_synth(cfg, args):
    from . import estimate, phase2
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, cmd="synth")
        node = _pick_container(ctx, " ".join(args.name) if args.name else None)
        print(f"Фаза 2 · {node.title}", flush=True)
        RESULT["container"] = node.id
        ask = _ask_force if interact.STATE["ask"] == "tty" else None

        def confirm() -> bool:  # после проверки «документы актуальны» — перед первым обращением к модели
            return args.yes or _confirm(ctx, _estimate(estimate.synth, ctx, node.id))
        return _execute(ctx, lambda: phase2.synth(ctx, node.id, force=args.force, ask_force=ask, confirm=confirm))


def cmd_check(cfg, args):
    items = []

    def item(name, ok, text):
        items.append({"name": name, "ok": bool(ok), "text": text})
        print(f"{name}: {text}", flush=True)
        return ok

    print(f"Настройки: {cfg.path}")
    v = cfg.vault
    ok = item("Хранилище", v.exists(), f"{v} — {'есть' if v.exists() else 'НЕТ такой папки'}")
    if v.exists() and not (v / ".obsidian").exists():
        print("  ! в этой папке нет настроек Obsidian (.obsidian) — откройте её в Obsidian: «Открыть папку как хранилище»")
    try:
        import dulwich  # noqa
        item("История версий (git)", True, "есть")
    except ImportError:
        ok &= item("История версий (git)", False, "НЕТ — выполните «Установка.bat» ещё раз")
    from .prompts import GARBLED_HINT
    from .schema import PROMPT_NAMES
    missing = [n for n in PROMPT_NAMES if not (cfg.program_file("prompts") / f"{n}.md").exists()]
    ok &= item("Промпты", not missing, "все на месте" if not missing else "НЕ ХВАТАЕТ: " + ", ".join(missing) + "." + GARBLED_HINT)
    if v.exists():
        from .context import Ctx
        try:
            ctx = Ctx(cfg, cmd="check")
            groups = ctx.llm.models()
            roles = cfg["llm"].get("roles") or {}
            for c, prompts in groups:
                name = f"Модель: {ctx.llm.label(c)}"
                if len(groups) > 1:
                    name += " — основная" if any(not roles.get(x) for x in prompts) else f" — для: {', '.join(prompts)}"
                try:
                    item(name, True, ctx.llm.ping(c))
                except UserError as e:
                    ok &= item(name, False, f"ОШИБКА — {e}")
        except UserError as e:
            ok &= item("Модель", False, f"ОШИБКА — {e}")
            ctx = Ctx(cfg, need_llm=False)
        try:
            t = time.time()
            vec = ctx.emb.embed(["проверка связи"])
            item("Эмбеддинги", True, f"{ctx.emb.fingerprint}, вектор {vec.shape[1]} чисел, {time.time() - t:.1f} с")
            stored = ctx.vs.meta.get("model")
            if stored and stored != ctx.emb.fingerprint:
                print(f"  ! векторы посчитаны другой моделью ({stored}) — при следующей Фазе 1 они будут пересчитаны")
        except UserError as e:
            ok &= item("Эмбеддинги", False, f"ОШИБКА — {e}")
    print("Всё в порядке." if ok else "Есть проблемы — см. выше.")
    RESULT.update({"check": items, "title": "Всё в порядке" if ok else "Есть проблемы"})
    return 0 if ok else 1


def _llama_params(args) -> dict | None:
    if not getattr(args, "params_json", None):
        return None
    raw = sys.stdin.read() if args.params_json == "-" else Path(args.params_json).read_text(encoding="utf-8-sig")
    try:
        obj = json.loads(raw or "{}")
    except ValueError as e:
        raise UserError(f"Параметры запуска не разобрать: {e}")
    if not isinstance(obj, dict):
        raise UserError("Параметры запуска должны быть объектом JSON.")
    return obj


def _llama_status_text(st: dict) -> list[str]:
    from . import llama as L
    m, srv = st["model"], st["server"]
    lines = [f"Модель: {m['title']} — " + ("скачана" if m["exists"] else
             f"не скачана ({L._size_text(m['size'])})" + (f", начато: {L._size_text(m['partial'])}" if m["partial"] else ""))
             + f" ({m['dir']})"]
    b = st["builds"]
    lines.append("llama.cpp: " + (", ".join(f"{L.BUILD_TITLES[k]} {v['tag']}".strip() for k, v in b.items()) if b else
                                  "не скачан" + (f" (есть на компьютере: {st['system']})" if st.get("system") else "")))
    if srv.get("running"):
        p = srv.get("params") or {}
        lines.append(f"Сервер: работает — {srv['url']}, {L.DEVICES.get(p.get('device'), '?')}, процесс {srv['pid']}"
                     + (", загружает модель" if srv.get("health") == "loading" else
                        ", не отвечает" if srv.get("health") is None else ""))
    else:
        lines.append("Сервер: не запущен" + (" — запустится сам, когда понадобится" if st["params"].get("autostart") and
                                             st["configured"] and m["exists"] else ""))
    if not st["configured"]:
        lines.append("  ! адрес эмбеддингов в настройках — не этот сервер (его впишет «llama start»)")
    return lines


def cmd_llama(cfg, args):
    """Своя модель эмбеддингов на llama.cpp: status | start | stop | download (в плагине — «Запустить модель…»)."""
    from . import llama as L
    act = args.action
    if act == "status":
        st = L.status(cfg, with_hw=args.hw)
        RESULT["llama"] = st
        if not args.json:
            print("\n".join(_llama_status_text(st)))
        RESULT["title"] = "Сервер работает" if st["server"].get("running") else "Сервер не запущен"
        return 0
    if act == "stop":
        r = L.stop_server(cfg)
        print("Сервер модели эмбеддингов остановлен." if r["stopped"] else "Сервер модели эмбеддингов и так не запущен.")
        RESULT.update({"title": "Сервер остановлен" if r["stopped"] else "Сервер не был запущен", "llama": L.status(cfg)})
        return 0
    over = _llama_params(args)
    p = L.params(cfg, over)
    pl = L.plan(cfg, p)
    if pl["download"] and not args.yes and interact.STATE["ask"] == "tty":
        what = "; ".join(f"{i['title']} — {L._size_text(i['size'])}" for i in pl["download"])
        ch = interact.ask("llama-download", "Скачивание", f"Нужно скачать: {what}. Скачать?", ["Скачать", "Отмена"], default=1)
        if ch != 0:
            return _cancelled()
    if act == "download":
        stop = cfg.vault / ".system" / "stop" if cfg.vault.exists() else None
        L.ensure_model(cfg, p, stop)
        build, exe = L.choose_build(cfg, p, L.hardware(cores=False))
        if exe is None:
            L.ensure_build(cfg, build, stop)
        print("Модель и llama.cpp скачаны. Запустить: в Obsidian — Настройки → Второй мозг → Модели → «Запустить модель…».")
        RESULT.update({"title": "Скачано", "llama": L.status(cfg)})
        return 0
    res = L.start(cfg, over, by="plugin" if args.json else "cli")
    RESULT.update({"title": "Сервер уже работает" if res.get("already") else "Модель запущена", "server": res,
                   "llama": L.status(cfg)})
    return 0


def cmd_pull_embeddings(cfg, args):
    """До v2.7 — скачать модель в Ollama; теперь — скачать свою модель и llama.cpp (как «llama download»)."""
    args.action, args.params_json, args.hw = "download", None, False
    args.yes = getattr(args, "yes", False)
    return cmd_llama(cfg, args)

def cmd_status(cfg, args):
    ctx = _ctx(cfg, need_llm=False)
    w = ctx.w
    st = w.state
    stages = {}
    for eid, s in st["entity_stage"].items():
        if eid in w.entities:
            stages[s] = stages.get(s, 0) + 1
    items = {}
    for it in st["items"].values():
        items[it.get("stage")] = items.get(it.get("stage"), 0) + 1
    print(f"Хранилище: {cfg.vault}")
    print(f"Контейнеров: {len(w.nodes)}; записей: {len(w.entities)}; документов: {len(w.products)}")
    names = {"done": "обработаны", "quarantine_wait": "ждут ответа (карантин)", "quarantine": "в карантине",
             "classified": "в очереди", "asked": "в очереди", "compacted": "в очереди", "embedded": "в очереди"}
    agg = {}
    for k, v in stages.items():
        agg[names.get(k, k)] = agg.get(names.get(k, k), 0) + v
    if agg:
        print("Записи: " + ", ".join(f"{k} — {v}" for k, v in agg.items()))
    waiting = {"await_structure": "ждут утверждения структуры", "await_mode": "ждут ответа о режиме", "ready": "ждут разбора",
               "new": "ждут черновика структуры"}
    wi = [f"{waiting[k]} — {v}" for k, v in items.items() if k in waiting]
    if wi:
        print("Файлы: " + ", ".join(wi))
    if st["dirty"]:
        print("Базы синтеза к пересборке: " + ", ".join(w.nodes[c].title for c in st["dirty"] if c in w.nodes))
    print(f"Открытых вопросов: {len(ctx.q.open)}")
    if st["structure"].get("pending"):
        print("Черновик структуры ждёт утверждения: _структура (черновик).md")
    pend = (U.read_json(w.p.webchat_index, None) or {}).get("pending") or {}
    if pend:
        print(f"Ручной режим: ждут ответа запросы в _веб-чат — {len(pend)}")
    new = list(w.p.staging.rglob("*.txt")) + list(w.p.staging.rglob("*.md"))
    if new:
        print(f"В _staging новых файлов: {len(new)}")
    from .usage import print_summary
    print_summary(cfg, w.p.usage)
    return 0


def cmd_usage(cfg, args):
    """Расходы по моделям (журнал .system/usage.jsonl); --reprice — пересчитать стоимость по текущим ценам."""
    from . import usage as US
    from .vault import World
    path = World(cfg).p.usage
    if args.reprice:
        with RunLock(_lock_path(cfg)):
            n = US.reprice(cfg, path, args.reprice)
        print(f"Стоимость пересчитана по текущим ценам: обращений — {n}." if n else "Пересчитывать нечего — стоимость не изменилась.")
        RESULT["repriced"] = n
    s = US.print_summary(cfg, path)
    RESULT.update({"usage": s, "title": "Расходы"})
    return 0


def cmd_estimate(cfg, args):
    """Оценка запуска без запуска: обращения к модели, время, стоимость."""
    from . import estimate as ES
    from . import ondemand
    ctx = _ctx(cfg, need_llm=False)
    name = " ".join(args.name) if args.name else None
    if args.what == "run":
        e = ES.run(ctx)
    elif args.what == "synth":
        node = _pick_container(ctx, name)
        e = ES.synth(ctx, node.id)
    else:
        node = _pick_container(ctx, name) if name else None
        e = ES.revalidate(ctx, len(ondemand.revalidate_queue(ctx, node.id if node else None)))
    print(f"Оценка: {e['title']}")
    for ln in e["lines"]:
        print("  " + ln)
    print("Оценка грубая: точное число записей станет известно только по ходу работы."
          + (" Средние взяты из прошлых запусков." if e["basis"] == "history" else " Прошлых запусков мало — взяты средние по умолчанию."))
    RESULT.update({"estimate": e, "title": "Оценка", "over": ES.over(cfg, e)})
    return 0


def _ask_revalidate_target(ctx):
    """Выбор для ревалидации в консоли: номер контейнера или 0 — все записи."""
    w = ctx.w
    nodes = sorted(w.nodes.values(), key=lambda x: (w.path_key(x).lower()))
    print("Что перепроверить?")
    print("    0. Все записи")
    for i, n in enumerate(nodes, 1):
        print(f"  {i:>3}. {'   ' * w.depth(n)}{n.title}")
    while True:
        s = input("Номер (или пусто — выйти): ").strip()
        if not s:
            raise UserError("Отменено.")
        if s == "0":
            return None
        if s.isdigit() and 1 <= int(s) <= len(nodes):
            return nodes[int(s) - 1]
        print("Нет такого номера.")


def cmd_revalidate(cfg, args):
    from . import estimate, ondemand
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, cmd="revalidate")
        node = None
        if args.name:
            node = _pick_container(ctx, " ".join(args.name))
        elif args.ask and interact.STATE["ask"] == "tty":
            node = _ask_revalidate_target(ctx)
        queue = ondemand.revalidate_queue(ctx, node.id if node else None)
        resume = ctx.w.state.get("revalidation", {}).get("queue")
        n = len(resume) if resume and ctx.w.state["revalidation"].get("target") == (node.id if node else "*") else len(queue)
        e = _estimate(estimate.revalidate, ctx, n)
        RESULT.update({"count": n, "container": node.id if node else None})
        if e:
            RESULT["estimate"] = e
        what = "«" + node.title + "»" if node else "всех записей"
        print(f"Ревалидация {what}: {n} записей — столько же обращений к модели.")
        if args.count:
            RESULT["title"] = f"Записей к перепроверке: {n}"
            return 0
        if not n:
            print("Перепроверять нечего.")
            RESULT["title"] = "Перепроверять нечего"
            return 0
        if not args.yes:
            if not interact.can_ask():
                raise UserError("Ревалидация тратит обращения к модели — подтвердите запуск флагом --yes.")
            if not _confirm(ctx, e, always=True, fallback=[f"Записей: {n} — столько же обращений к модели"]):
                return _cancelled()
        return _execute(ctx, lambda: ondemand.revalidate(ctx, node.id if node else None, queue))


def cmd_patterns(cfg, args):
    from . import ondemand
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, cmd="patterns")
        return _execute(ctx, lambda: ondemand.patterns(ctx))


# ---------- команды для плагина ----------
def cmd_snapshot(cfg, args):
    """Снимок состояния для плагина (.system/ui.json): без обращений к модели и без изменений в хранилище."""
    from .snapshot import write
    ctx = _ctx(cfg, need_llm=False)
    data = write(ctx)
    RESULT.update({"title": "Снимок обновлён", "questions": data["status"]["questions"],
                   "warnings": data["warnings"]})
    print(f"Снимок обновлён: контейнеров {data['status']['containers']}, вопросов {data['status']['questions']}.")
    return 0


def cmd_answer(cfg, args):
    """Ответ на вопрос из плагина — применяется сразу (как ответ в open-questions.md при запуске Фазы 1)."""
    from . import answers
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, need_llm=False, cmd="answer")
        q = ctx.q.open.get(args.qid)
        if q is None:
            raise UserError(f"Вопроса {args.qid} уже нет среди открытых — обновите список.")
        idx = args.option
        if idx is not None and not 0 <= idx < len(q.get("options") or []):
            raise UserError(f"У вопроса {args.qid} нет варианта №{idx + 1}.")
        text = (args.text or "").strip()
        if idx is None and not text:
            raise UserError("Выберите вариант или напишите ответ.")
        ctx.q.injected[args.qid] = (idx, text, None)
        q["note"] = None

        def go():
            answers.process(ctx)
        code = _execute(ctx, go)
        left = ctx.q.open.get(args.qid)
        RESULT.update({"qid": args.qid, "accepted": left is None, "note": left.get("note") if left else None})
        if left is not None:
            print(f"Ответ не принят: {left.get('note') or 'программа не смогла его применить'}")
            return 1
        print(f"Ответ на {args.qid} принят.")
        return code


def cmd_advise(cfg, args):
    """Совет модели по порогам контейнера: ничего не меняет — значения применяет пользователь."""
    from . import tuning
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, cmd="advise")
        node = _pick_container(ctx, " ".join(args.name) if args.name else None, cmd="advise")
        print(f"Совет по порогам · {node.title}", flush=True)
        out = {}

        def go():
            out.update(tuning.advise(ctx, node.id))
            RESULT["advice"] = out
            print(out["summary"])
            for r in out["recommendations"]:
                print(f"  {r['label']} ({r['name']}): {r['current']} → {r['value']} — {r['reasoning']}")
            if not out["recommendations"]:
                print("  Менять пороги не нужно.")
            print("Применить: впишите значения в поле thresholds контейнера или нажмите «Применить» в плагине.")
        return _execute(ctx, go, empty="")


def cmd_settings(cfg, args):
    from . import schema as S
    if args.key:
        key = sys.stdin.readline() if not sys.stdin.isatty() else input("Ключ (пусто — удалить): ")
        msg = S.save_key(cfg, args.key, key)
        print(msg)
        RESULT["title"] = msg
    elif args.set_json:
        raw = sys.stdin.read() if args.set_json == "-" else Path(args.set_json).read_text(encoding="utf-8-sig")
        try:
            patch = json.loads(raw or "{}")
        except ValueError as e:
            raise UserError(f"Изменения настроек не разобрать: {e}")
        if not isinstance(patch, dict):
            raise UserError("Изменения настроек должны быть объектом JSON.")
        S.apply_patch(cfg, patch)
        print(f"Настройки сохранены: {cfg.path}")
        RESULT["title"] = "Настройки сохранены"
    from . import profiles as PR
    from .config import DEFAULTS
    RESULT["settings"] = {"values": {k: v for k, v in cfg.data.items()}, "schema": S.SCHEMA, "keys": S.key_status(cfg),
                          "path": str(cfg.path), "program_dir": str(cfg.program_dir), "prompts_dir": str(cfg.program_file("prompts")),
                          "prompts": S.PROMPT_NAMES, "version": __version__, "tabs": S.TABS, "update_repo": _update_repo(),
                          "profile_fields": S.PROFILE_FIELDS, "profile_defaults": PR.KIND_DEFAULTS, "modes": S.MODE_CHOICES,
                          "defaults": DEFAULTS}
    if not args.key and not args.set_json and not args.json:
        print(f"Настройки: {cfg.path}")
    return 0


def _update_repo() -> str:
    from .updater import repo_link
    return repo_link()


def _cleanup_legacy(cfg):
    """После обновления с версии до 2.6 (её обновлятор не знал об уборке) — убрать прежние .bat-файлы."""
    try:
        from . import install as I
        if any((cfg.program_dir / n).is_file() for n in I.LEGACY_FILES):
            I.remove_legacy(cfg.program_dir)
    except OSError:
        pass


def _remember_vault(cfg, vault: Path):
    """Записать в settings.yaml папку хранилища (для запуска программы из командной строки)."""
    try:
        if cfg.path and cfg.vault.resolve() != vault.resolve():
            from .schema import apply_patch
            apply_patch(cfg, {"vault": vault.as_posix()})
            print(f"В settings.yaml записана папка хранилища: {vault.as_posix()}")
    except (UserError, OSError) as e:
        print(f"  ! {e}")


def cmd_install_plugin(cfg, args):
    """Только скопировать плагин в <хранилище>/.obsidian/plugins/vtoroy-mozg и включить его."""
    from . import install as I
    ask = _interactive() and not args.json
    if args.path:
        vault = Path(" ".join(args.path).strip().strip('"'))
    else:
        vault = I.choose_vault(cfg.vault if I.is_vault(cfg.vault) else None, ask)
    dest = I.install_plugin(vault)
    _remember_vault(cfg, vault)
    print(f"Плагин установлен: {dest}")
    print("Дальше в Obsidian: перезапустите его; если спросит — нажмите «Довериться автору и включить плагины».")
    print("Если плагин не появился: Настройки → «Сторонние плагины» → «Выйти из ограниченного режима» (в старых версиях — «Включить сторонние плагины»), затем включите «Второй мозг» в списке.")
    RESULT.update({"title": "Плагин установлен", "path": str(dest)})
    return 0


def _pause(text: str) -> None:
    try:
        input(text)
    except EOFError:
        pass


def _setup_llama(cfg, ask: bool) -> None:
    from . import llama as L
    c = cfg["embeddings"]
    p = L.raw_params(cfg)
    if c.get("mode") != "local" or not L.is_our_url(c.get("base_url"), p.get("port")):
        return
    p = L.params(cfg)
    if L.model_file(cfg, p).is_file():
        return
    hw = L.hardware(cores=False)
    pl = L.plan(cfg, p, hw)
    print()
    print(f"Для поиска похожих мыслей нужна модель эмбеддингов {L.MODEL['title']} и программа llama.cpp, которая её "
          "запускает. Скачать их можно сейчас или позже из Obsidian (Настройки → Второй мозг → Модели → «Запустить модель…» — "
          "там же выбирается, считать на процессоре или на видеокарте).")
    for it in pl["download"]:
        print(f"  • {it['title']} — {L._size_text(it['size'])}")
    ram = hw.get("ram_gb")
    if ram and round(ram) < L.MIN_RAM_GB and not hw.get("gpus"):
        print(f"  ! для работы на процессоре нужно не меньше {L.MIN_RAM_GB} ГБ оперативной памяти, а у этого компьютера "
              f"{round(ram)} ГБ")
    yes = False
    if ask:
        try:
            yes = input("Скачать сейчас? (д/н): ").strip().lower() in ("д", "да", "y", "yes", "l")
        except EOFError:
            yes = False
    if not yes:
        print("Хорошо — скачается при первом запуске модели из Obsidian.")
        return
    L.ensure_model(cfg, p)
    build, exe = L.choose_build(cfg, p, hw)
    if exe is None:
        L.ensure_build(cfg, build)
    print("Готово. Запустить модель: в Obsidian — Настройки → Второй мозг → Модели → «Запустить модель…».")


def cmd_setup(cfg, args):
    """Установка «всё в одном» после библиотек Python (её запускает Установка.bat): уборка прежних .bat-файлов,
    плагин в хранилище Obsidian, папка хранилища в settings.yaml, модель эмбеддингов (по желанию), открыть Obsidian."""
    from . import install as I
    ask = _interactive() and not args.json
    removed = I.remove_legacy(cfg.program_dir)
    if removed:
        print("Убраны файлы прежних версий (теперь всё это — в плагине): " + ", ".join(removed))
    # 1. хранилище и плагин
    if args.path:
        vault = Path(" ".join(args.path).strip().strip('"'))
    else:
        vault = I.choose_vault(cfg.vault if I.is_vault(cfg.vault) else None, ask)
    running = I.obsidian_running()
    if running and ask:
        print()
        print("Obsidian сейчас открыт. Закройте его (все окна) — плагин подхватится, когда Obsidian откроется снова.")
        _pause("Закрыли? Нажмите Enter… ")
        running = I.obsidian_running()
    dest = I.install_plugin(vault)
    _remember_vault(cfg, vault)
    print(f"Плагин установлен: {dest}")
    RESULT.update({"title": "Установка завершена", "path": str(dest), "vault": str(vault), "removed": removed})
    # 2. своя модель эмбеддингов (если поиск — на этом компьютере): скачать сейчас, по желанию
    try:
        _setup_llama(cfg, ask)
    except UserError as e:
        print(f"  ! {e}")
        print("Модель можно скачать и запустить позже: Настройки → Второй мозг → Модели → «Запустить модель…».")
    # 3. открыть Obsidian
    print()
    if not running and I.open_obsidian(vault):
        print("Открываю Obsidian…")
    print("Дальше в Obsidian:")
    if running:
        print("  0. Перезапустите Obsidian (закройте и откройте снова), чтобы заработал плагин.")
    print("  1. Если спросит — «Довериться автору и включить плагины». Справа появится панель «Второй мозг».")
    print("  2. Настройки → Второй мозг → «Модели»: вставьте ключ API, выберите модель и нажмите «Проверить связь».")
    print("  3. Сложите заметки в папку _staging хранилища и нажмите в панели «Запустить Фазу 1».")
    return 0


def cmd_update(cfg, args):
    """Обновление программы с GitHub: проверить (--check) или скачать и установить."""
    from . import updater
    info = updater.check(cfg)
    RESULT["update"] = {k: v for k, v in info.items() if k not in ("zip_url", "zip_accept")}
    cur, new = __version__, info.get("version") or "?"
    if not info["newer"] and not args.force:
        print(f"Установлена последняя версия: {cur} (в репозитории {info['repo']} — {new}).")
        RESULT["title"] = "Последняя версия"
        return 0
    print(f"Есть новая версия: {new} (установлена {cur}) — {info['url']}")
    if info.get("notes"):
        print("Что нового:\n" + "\n".join("  " + ln for ln in info["notes"].splitlines()[:30]))
    if args.check:
        RESULT["title"] = f"Есть версия {new}"
        return 0
    if not args.yes:
        if not interact.can_ask():
            raise UserError("Обновление меняет файлы программы — подтвердите флагом --yes.")
        ch = interact.ask("update", "Обновление программы", f"Установить версию {new}? Настройки и ключи не меняются.",
                          ["Установить", "Отмена"], default=None)
        if ch != 0:
            return _cancelled()
    lock = RunLock(_lock_path(cfg)) if cfg.vault.exists() else None
    if lock:
        lock.__enter__()
    try:
        data = updater.download(cfg, info)
        res = updater.install_zip(cfg, data, info)
    finally:
        if lock:
            lock.__exit__()
    print(f"Установлена версия {res['version']}: обновлено файлов — {res['updated']}, новых — {res['added']}"
          + (f", удалено устаревших — {len(res['removed'])}" if res["removed"] else "") + ".")
    if res["plugin"]:
        print(f"Плагин в хранилище обновлён: {res['plugin']}")
    for n in res["notes"]:
        print(f"  • {n}")
    print("Перезапустите Obsidian, чтобы заработал новый плагин." if res["plugin"] else "Готово.")
    RESULT.update({"title": f"Установлена версия {res['version']}", "installed": res, "restart": bool(res["plugin"]),
                   "notices": res["notes"]})
    return 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    RESULT.clear()
    p = argparse.ArgumentParser(prog="brain", description=f"Второй мозг {__version__}", add_help=True)
    p.add_argument("--settings", help="путь к settings.yaml (по умолчанию — рядом с программой)")
    p.add_argument("--vault", help="папка хранилища вместо указанной в settings.yaml")
    p.add_argument("--json", action="store_true", help="итог строкой @@RESULT {…} (для плагина)")
    p.add_argument("--ask-stdin", action="store_true", help="вопросы посреди запуска: @@ASK, ответ строкой JSON в стандартный ввод")
    sub = p.add_subparsers(dest="cmd")
    rn = sub.add_parser("run")
    rn.add_argument("--yes", action="store_true", help="без вопроса перед большим запуском")
    s = sub.add_parser("synth")
    s.add_argument("name", nargs="*")
    s.add_argument("--force", action="store_true")
    s.add_argument("--yes", action="store_true")
    sub.add_parser("check")
    sub.add_parser("status")
    us = sub.add_parser("usage")
    us.add_argument("--reprice", help="пересчитать стоимость: id профиля, emb (эмбеддинги) или all")
    es = sub.add_parser("estimate")
    es.add_argument("what", choices=["run", "synth", "revalidate"])
    es.add_argument("name", nargs="*")
    up = sub.add_parser("update")
    up.add_argument("--check", action="store_true", help="только проверить, есть ли новая версия")
    up.add_argument("--yes", action="store_true", help="установить без вопроса")
    up.add_argument("--force", action="store_true", help="установить, даже если версия не новее")
    r = sub.add_parser("revalidate")
    r.add_argument("name", nargs="*")
    r.add_argument("--yes", action="store_true")
    r.add_argument("--ask", action="store_true")
    r.add_argument("--count", action="store_true", help="только посчитать записи")
    sub.add_parser("patterns")
    lm = sub.add_parser("llama")
    lm.add_argument("action", choices=["status", "start", "stop", "download"])
    lm.add_argument("--params-json", help="параметры запуска: файл JSON или - (из стандартного ввода)")
    lm.add_argument("--hw", action="store_true", help="status: ещё и оборудование компьютера")
    lm.add_argument("--yes", action="store_true", help="скачать без вопроса")
    sub.add_parser("pull-embeddings")  # до v2.7 — скачать модель в Ollama; теперь — то же, что llama download
    sub.add_parser("snapshot")
    a = sub.add_parser("answer")
    a.add_argument("qid")
    a.add_argument("--option", type=int, help="номер варианта с нуля")
    a.add_argument("--text")
    ad = sub.add_parser("advise")
    ad.add_argument("name", nargs="*")
    st = sub.add_parser("settings")
    st.add_argument("--set-json", help="файл с изменениями в JSON или - (из стандартного ввода)")
    st.add_argument("--key", help="сохранить ключ из стандартного ввода: profile:<id> | embeddings (| llm | role:<шаг>)")
    ip = sub.add_parser("install-plugin")
    ip.add_argument("path", nargs="*")
    su = sub.add_parser("setup")
    su.add_argument("path", nargs="*")
    args = p.parse_args(argv)
    if not args.cmd:
        print(HELP)
        return 0
    cmds = {"run": cmd_run, "synth": cmd_synth, "check": cmd_check, "status": cmd_status, "pull-embeddings": cmd_pull_embeddings,
            "llama": cmd_llama,
            "revalidate": cmd_revalidate, "patterns": cmd_patterns, "snapshot": cmd_snapshot, "answer": cmd_answer,
            "advise": cmd_advise, "settings": cmd_settings, "install-plugin": cmd_install_plugin, "usage": cmd_usage,
            "estimate": cmd_estimate, "update": cmd_update, "setup": cmd_setup}
    interact.configure(args.json, "stdin" if args.ask_stdin else ("tty" if _interactive() and not args.json else "none"))
    cfg = None
    RESULT.update({"cmd": args.cmd, "ok": False})
    code = 2
    try:
        cfg = load_config(args.settings)
        if args.vault:
            cfg.vault_override = args.vault
        if args.cmd != "setup":
            _cleanup_legacy(cfg)
        code = cmds[args.cmd](cfg, args) or 0
        RESULT["ok"] = code == 0
        return code
    except UserError as e:
        print(f"\nОшибка: {e}")
        RESULT["error"] = str(e)
        code = 1
        return 1
    except KeyboardInterrupt:
        print("\nОстановлено.")
        RESULT.update({"error": "Остановлено.", "stopped": True})
        code = 1
        return 1
    except Exception:
        tb = traceback.format_exc()
        log = None
        try:
            if cfg is not None and cfg.vault.exists():
                log = cfg.vault / "_логи" / "ошибки.log"
                U.append_text(log, f"\n===== {U.ru_datetime()} · {' '.join(sys.argv[1:])}\n{tb}")
        except Exception:
            pass
        print("\nНепредвиденная ошибка программы. Всё обработанное до неё сохранено; повторный запуск продолжит с того же места.")
        last = tb.strip().split("\n")[-1]
        print(last)
        if log:
            print(f"Подробности — в файле {log}")
        RESULT["error"] = f"Непредвиденная ошибка программы: {last}" + (f" Подробности — в {log}" if log else "")
        code = 2
        return 2
    finally:
        RESULT["code"] = code
        if getattr(args, "json", False):
            print("@@RESULT " + json.dumps(RESULT, ensure_ascii=False, default=str), flush=True)

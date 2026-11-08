"""Оценка большого запуска (раздел 14.4): сколько будет обращений к модели, сколько это займёт времени и денег.
Средние берутся из истории обращений (.system/usage.jsonl) для того же шага и профиля; без истории — умолчания.
Оценка грубая (±50%): точное число записей станет известно только после раскладки."""
from __future__ import annotations

import math

from . import usage as US
from .profiles import input_limit, target

DEFAULT_OUT = {"Структура": 3000, "Классификация": 1500, "Вопросы": 400, "Уплотнение": 600, "Извлечение": 900,
               "Анализ пула": 1500, "Ценность": 1200, "Сравнение версий": 500, "Синтез": 5000,
               "Новый составной тип": 800, "Пороги": 800}
DEFAULT_SEC = {"cloud": 25.0, "local": 90.0, "fake": 0.05, "webchat": 0.0}
SLOW = {"Синтез": 3.0, "Структура": 2.0, "Классификация": 1.3, "Анализ пула": 1.5}
CPT = US.CHARS_PER_TOKEN


class Estimator:
    def __init__(self, ctx):
        self.ctx = ctx
        self.cfg = ctx.cfg
        self.steps: dict[str, dict] = {}
        self.hist: dict = {}
        for r in US.read(ctx.w.p.usage)[-3000:]:
            if (r.get("kind") or "llm") != "llm" or r.get("ptype") == "webchat":
                continue
            n = US.normalize(self.cfg, r)
            for key in ((n["prompt"], n["key"]), (n["prompt"], None)):
                h = self.hist.setdefault(key, {"n": 0, "in": 0, "out": 0, "sec": 0.0, "est": 0})
                h["n"] += 1
                h["in"] += n["in"]
                h["out"] += n["out"]
                h["sec"] += n["sec"]
        self.from_history = False

    def _overhead(self, step: str) -> int:
        try:
            p = self.cfg.program_file("prompts") / f"{step}.md"
            return int(len(p.read_text(encoding="utf-8-sig")) / CPT) + 300
        except OSError:
            return 2500

    def add(self, step: str, calls: float, material_chars: float | None = None):
        """calls обращений шага; material_chars — объём материала на одно обращение (для шагов, где он известен)."""
        if calls <= 0:
            return
        kind, p = target(self.cfg, step)
        ptype = "webchat" if kind == "webchat" else ((p or {}).get("kind") if kind != "fake" else "fake")
        key = (p or {}).get("id")
        h = self.hist.get((step, key)) or self.hist.get((step, None))
        if h and h["n"] >= 3:
            self.from_history = True
            avg_in, avg_out, avg_sec = h["in"] / h["n"], h["out"] / h["n"], h["sec"] / h["n"]
        else:
            avg_in, avg_out = self._overhead(step) + 1500, DEFAULT_OUT.get(step, 800)
            avg_sec = DEFAULT_SEC.get(ptype or "cloud", 25.0) * SLOW.get(step, 1.0)
        if material_chars is not None:
            avg_in = self._overhead(step) + material_chars / CPT
            if h and h["n"] >= 3 and h["sec"] and h["in"]:
                avg_sec = max(avg_sec * 0.5, (h["sec"] / h["n"]) * (avg_in / max(1.0, h["in"] / h["n"])) ** 0.5)
        # тестовая модель считается как облачная (как и в журнале расходов): деньги — по ценам её профиля
        bill = ptype == "cloud" or (ptype == "fake" and (p or {}).get("kind") == "cloud")
        s = self.steps.setdefault(step, {"calls": 0.0, "in": 0.0, "out": 0.0, "sec": 0.0, "cost": 0.0, "unpriced": 0.0,
                                         "ptype": ptype, "bill": bill, "profile": (p or {}).get("name")})
        s["calls"] += calls
        s["in"] += calls * avg_in
        s["out"] += calls * avg_out
        s["sec"] += calls * avg_sec
        if bill:
            c = US.cost((p or {}).get("prices"), int(avg_in), int(avg_out))
            if c is None:
                s["unpriced"] += calls
            else:
                s["cost"] += calls * c

    def result(self, title: str) -> dict:
        calls = sum(s["calls"] for s in self.steps.values())
        webchat = sum(s["calls"] for s in self.steps.values() if s["ptype"] == "webchat")
        sec = sum(s["sec"] for s in self.steps.values())
        cost = sum(s["cost"] for s in self.steps.values())
        unpriced = sorted({s["profile"] for s in self.steps.values() if s["unpriced"] and s["profile"]})
        # стоимость — только если хоть одно платное обращение с ценами; совсем без цен — «не посчитать», а не $0
        priced = any(s["bill"] and s["calls"] - s["unpriced"] > 0 for s in self.steps.values())
        out = {"title": title, "calls": int(math.ceil(calls)), "webchat": int(math.ceil(webchat)),
               "in": int(sum(s["in"] for s in self.steps.values())), "out": int(sum(s["out"] for s in self.steps.values())),
               "minutes": round(sec / 60, 1), "cost": round(cost, 4) if priced else None, "unpriced": unpriced,
               "basis": "history" if self.from_history else "defaults",
               "steps": {k: int(math.ceil(v["calls"])) for k, v in sorted(self.steps.items(), key=lambda kv: -kv[1]["calls"])}}
        out["lines"] = lines(out)
        return out


def _minutes(m: float) -> str:
    if m < 1:
        return "меньше минуты"
    if m < 90:
        return f"≈ {round(m)} мин"
    return f"≈ {m / 60:.1f} ч".replace(".", ",")


def lines(e: dict) -> list[str]:
    out = [f"Обращений к модели: ≈ {e['calls']}" + (f" (из них вручную через веб-чат — {e['webchat']})" if e["webchat"] else "")]
    if e["calls"] - e["webchat"] > 0:
        out.append(f"Время: {_minutes(e['minutes'])}" + (" (без ваших ответов в веб-чате)" if e["webchat"] else ""))
    if e["cost"] is not None:
        if e["unpriced"]:
            out.append(f"Стоимость: ≈ {US.money(e['cost'])}, не считая профилей без цен ({', '.join(e['unpriced'])})")
        else:
            out.append(f"Стоимость: ≈ {US.money(e['cost'])}")
    elif e["unpriced"]:
        out.append(f"Стоимость: не посчитать — у профиля не заданы цены ({', '.join(e['unpriced'])}; вкладка «Расходы»)")
    tok = e["in"] + e["out"]
    if tok:
        out.append(f"Токенов: ≈ {US.num(e['in'])} на входе, {US.num(e['out'])} на выходе")
    if e["steps"]:
        out.append("По шагам: " + ", ".join(f"{k} — {v}" for k, v in list(e["steps"].items())[:6]))
    return out


def over(cfg, e: dict) -> bool:
    s = cfg.get("estimate") or {}
    if not s.get("enabled", True):
        return False
    if e["calls"] > int(s.get("calls") or 30):
        return True
    if e["cost"] is not None and e["cost"] > float(s.get("usd") or 0.5):
        return True
    return e["minutes"] > float(s.get("minutes") or 10)


# ---------- что оценивать ----------
def _staging_parts(ctx) -> list[tuple[int, str]]:
    """Файлы в _staging (ещё не принятые): (знаков, режим) по каждой будущей записи-файлу (с делением по датам)."""
    from .ingest import parse_header, read_text_file, scan_staging, source_and_mode, split_by_dates
    w = ctx.w
    out = []
    if not w.p.staging.exists():
        return out
    for p in scan_staging(w.p.staging):
        try:
            text, _ = read_text_file(p)
        except OSError:
            continue
        hdr = parse_header(text)
        _, mflag = source_and_mode(p.relative_to(w.p.staging).parts[:-1])
        mode = "bootstrap" if (mflag == "bootstrap" or not w.nodes) else (hdr.get("mode") or "unknown")
        parts = split_by_dates(ctx.cfg, hdr)
        if parts:
            lines_ = hdr["body"].split("\n")
            for part in parts:
                out.append((len("\n".join(lines_[part["lines"][0]:part["lines"][1]])), mode))
        else:
            out.append((len(hdr["body"]), mode))
    return out


def _avg_entity_chars(w) -> float:
    lens = [len(e.text or "") for e in list(w.entities.values())[-500:]]
    return max(300.0, sum(lens) / len(lens)) if len(lens) >= 10 else 1200.0


def _ratio(E: Estimator, step: str, base: str, default: float) -> float:
    a, b = E.hist.get((step, None)), E.hist.get((base, None))
    if a and b and b["n"] >= 20:
        return min(1.5, a["n"] / b["n"])
    return default


def run(ctx) -> dict:
    """Фаза 1: файлы из _staging и очереди. Массовая загрузка (bootstrap) — черновик структуры; после утверждения
    черновика — разбор всех ждавших его файлов; остальное — разбор, записи, базы синтеза."""
    from .ingest import load_item_body
    from .pipeline import ACTIVE
    from .structure import parse_draft
    w = ctx.w
    st = w.state
    E = Estimator(ctx)
    approved, draft_nodes = False, 0
    if w.p.draft.exists():
        try:
            parsed = parse_draft(w.p.draft.read_text(encoding="utf-8-sig"), st["structure"].get("draft_titles"))
            approved, draft_nodes = bool(parsed["approved"]), len(parsed["nodes"])
        except Exception:  # черновик испорчен — об этом скажет сам запуск
            pass
    to_structure, to_classify = [], []
    for chars, mode in _staging_parts(ctx):
        (to_structure if mode == "bootstrap" else to_classify).append((chars, mode))
    for it in st["items"].values():
        stage = it.get("stage")
        if stage not in ("new", "ready") and not (stage == "await_structure" and approved):
            continue
        try:
            chars = len(load_item_body(ctx, it))
        except OSError:
            continue
        if stage == "new":
            to_structure.append((chars, "bootstrap"))
        else:
            to_classify.append((chars, it.get("mode") or "unknown"))
    if to_structure:
        chars = sum(c for c, _ in to_structure)
        lim = input_limit(ctx.cfg, "Структура")
        chunk = max(lim - 40000, min(20000, lim // 2))
        n = max(1, math.ceil(chars / chunk))
        E.add("Структура", n, min(chars, chunk))
    lim = input_limit(ctx.cfg, "Классификация")
    window = max(lim - 60000, min(20000, lim // 2))
    ent_chars = _avg_entity_chars(w)
    new_entities = 0.0
    for chars, mode in to_classify:
        wins = max(1, math.ceil(chars / window))
        E.add("Классификация", wins, min(chars, window) + 4000)
        if mode == "steady_state":
            new_entities += 1
        elif mode == "bootstrap" or chars > 3000:
            new_entities += max(1.0, chars / ent_chars)
        else:
            new_entities += 1
    queued = sum(1 for eid, s in st["entity_stage"].items() if s in ACTIVE and eid in w.entities)
    ents = new_entities + queued
    E.add("Извлечение", ents, ent_chars)
    E.add("Уплотнение", ents * _ratio(E, "Уплотнение", "Извлечение", 0.3), ent_chars)
    E.add("Вопросы", ents * _ratio(E, "Вопросы", "Извлечение", 0.15), ent_chars)
    n_nodes = max(len(w.nodes), draft_nodes if approved else 0)
    touched = len(st["dirty"]) + (min(max(1, n_nodes), math.ceil(ents)) if ents else 0)
    touched = min(touched, max(1, n_nodes) + len(st["dirty"]))
    with_base = sum(1 for n in w.nodes.values() if w.base(n.id))
    E.add("Анализ пула", touched)
    E.add("Ценность", touched)
    E.add("Сравнение версий", touched * (with_base / max(1, n_nodes)) if n_nodes else 0)
    title = "Фаза 1" + (" · черновик структуры" if to_structure and not to_classify else "")
    out = E.result(title)
    out["files"] = len(to_structure) + len(to_classify)
    out["entities"] = int(round(ents))
    out["stage"] = "structure" if to_structure and not to_classify else "run"
    return out


def synth(ctx, cid: str) -> dict:
    from .phase2 import base_for_prompt
    w = ctx.w
    E = Estimator(ctx)
    try:
        base = len(base_for_prompt(w, cid))
    except Exception:  # базы ещё нет — об этом скажет сам синтез
        base = 0
    prods = w.products_of(cid)
    prev = sum(len(b) for _, _, b in prods)
    E.add("Синтез", 1, base + prev)
    E.add("Сравнение версий", len(prods), 2 * prev / max(1, len(prods)) if prods else None)
    return E.result(f"Фаза 2 · {w.nodes[cid].title}")


def revalidate(ctx, n: int) -> dict:
    E = Estimator(ctx)
    E.add("Классификация", n, _avg_entity_chars(ctx.w) + 4000)
    return E.result("Ревалидация")

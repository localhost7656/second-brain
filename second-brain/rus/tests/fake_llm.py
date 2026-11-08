"""Тестовая «модель»: правдоподобные ответы по простым правилам для всех промптов.
Нужна только для проверки программы без API (llm.mode: fake). Один раз нарочно отвечает с ошибкой формата."""
from __future__ import annotations

import json
import os
import re

TOPICS = {
    "метеостанция": r"метеостанц|датчик|барометр|термометр|проводн",
    "пекарня": r"пекар|хлеб|буханк|аренд|мельниц|\bмук[аиуое]\b",
    "дача": r"дач|теплиц|огур|томат|полив|грядк",
    "здоровье": r"\bсон\b|\bсна\b|засыпа|здоров|самочувств",
}
TITLES = {"метеостанция": "Метеостанция", "пекарня": "Пекарня", "дача": "Дача", "здоровье": "Здоровье"}
STATE = {"broken": set(), "value_calls": {}, "synth_calls": {}}


def topics_of(text: str) -> list[str]:
    t = (text or "").lower()
    found = []
    for name, rx in TOPICS.items():
        m = re.search(rx, t)
        if m:
            found.append((m.start(), name))
    return [n for _, n in sorted(found)]


def find_container(containers, topic):
    if not isinstance(containers, list) or not topic:
        return None
    rx = TOPICS[topic]
    for c in containers:
        if re.search(rx, (c.get("title") or "").lower()):
            return c
    for c in containers:
        if re.search(rx, (c.get("description") or "").lower()):
            return c
    return None


def j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


def _load():
    f = os.environ.get("FAKE_LLM_STATE")
    if f and os.path.exists(f):
        d = json.load(open(f, encoding="utf-8"))
        STATE.update(broken=set(d["broken"]), value_calls=d["value_calls"], synth_calls=d["synth_calls"])


def _save():
    f = os.environ.get("FAKE_LLM_STATE")
    if f:
        json.dump({"broken": sorted(STATE["broken"]), "value_calls": STATE["value_calls"], "synth_calls": STATE["synth_calls"]},
                  open(f, "w", encoding="utf-8"), ensure_ascii=False)


def respond(prompt, variables, messages, attempt):
    delay = float(os.environ.get("FAKE_DELAY") or 0)  # для проверки плагина: «модель думает» N секунд
    if delay:
        import time
        time.sleep(delay)
    _load()
    try:
        return _respond(prompt, variables, messages, attempt)
    finally:
        _save()


_CALLS: dict = {}  # счётчик вызовов в пределах одного прогона


def _respond(prompt, variables, messages, attempt):
    crash = os.environ.get("FAKE_CRASH_ON")  # «Промпт» или «Промпт#N» — сбой на N-м вызове в прогоне
    if crash:
        name, _, nth = crash.partition("#")
        if name == prompt:
            _CALLS[prompt] = _CALLS.get(prompt, 0) + 1
            if _CALLS[prompt] == int(nth or 1) and crash not in STATE["broken"]:
                STATE["broken"].add(crash)
                raise RuntimeError(f"имитация сбоя на промпте «{prompt}»")
    stop_on = os.environ.get("FAKE_STOP_ON")  # «Стоп» из плагина посреди прогона: создать файл .system/stop
    if stop_on == prompt and f"stop:{prompt}" not in STATE["broken"]:
        STATE["broken"].add(f"stop:{prompt}")
        open(os.environ["FAKE_STOP_FILE"], "w").close()
    fn = {"Структура": structure, "Классификация": classify, "Вопросы": questions, "Уплотнение": compact,
          "Извлечение": extract, "Анализ пула": analysis, "Ценность": value, "Сравнение версий": compare,
          "Новый составной тип": new_type, "Синтез": synth, "Пороги": thresholds}.get(prompt)
    if prompt == "ping":
        return '{"ok": true}'
    if prompt == "Пороги" and attempt == 0 and "Пороги" not in STATE["broken"]:
        STATE["broken"].add("Пороги")  # неверное имя порога — программа должна вернуть ответ на исправление
        return j({"reasoning": "…", "summary": "Поднять порог.", "recommendations": [{"name": "раскладка", "value": 80, "reasoning": "x"}]})
    if fn is None:
        raise RuntimeError(f"fake: неизвестный промпт {prompt}")
    # один нарочно неверный ответ на каждый из двух промптов — проверка повтора с пояснением ошибки
    if prompt in ("Классификация", "Извлечение") and attempt == 0 and prompt not in STATE["broken"]:
        STATE["broken"].add(prompt)
        if prompt == "Извлечение":
            return '```json\n{"reasoning": "…", "aspects": [{"type": "факт", "text": "неверный тип"}]}\n```'
        return "Конечно! Вот разбор: {сломанный json"
    if attempt > 0:
        assert "не прошёл проверку" in messages[-1]["content"], "повтор должен содержать список ошибок"
    return fn(variables)


# ---------- Структура ----------
def structure(v):
    tree = v["draft"] if isinstance(v["draft"], list) else (v["existing"] if isinstance(v["existing"], list) else [])
    tree = [dict(t) for t in tree]
    blocks = re.split(r"\n\n=====\n\n", v["material"])
    files = {}
    present = []
    for b in blocks:
        m = re.match(r"\[(i\d+)\]", b)
        ts = topics_of(b)
        for t in ts:
            if t != "здоровье" and t not in present:
                present.append(t)
        if m:
            files[m.group(1)] = [t for t in ts if t != "здоровье"]
    def key_for(title):
        for t in tree:
            if t["title"].lower() == title.lower():
                return t["key"]
        return None
    n = len([t for t in tree if str(t["key"]).startswith("n")])
    def add(title, typ, parent, desc):
        nonlocal n
        k = key_for(title)
        if k:
            return k
        for t in tree:  # уже есть под другим названием (пользователь переименовал)
            if re.search(TOPICS.get(title.lower(), "^$") if title.lower() in TOPICS else "^$", t["title"].lower()):
                return t["key"]
        n += 1
        k = f"n{n}"
        tree.append({"key": k, "title": title, "type": typ, "parent": parent, "description": desc, "applies_to": [], "files": []})
        return k
    keys = {}
    if "метеостанция" in present:
        tech = add("Технологии", "project", None, "Технические проекты и эксперименты")
        keys["метеостанция"] = add("Метеостанция", "project", tech, "Домашняя метеостанция: температура, влажность, давление")
    if "пекарня" in present:
        keys["пекарня"] = add("Пекарня", "seed", None, "Идея маленькой пекарни у дома")
    if "дача" in present:
        keys["дача"] = add("Дача", "project", None, "Теплица, полив, урожай")
    for t in tree:
        rx = None
        for name, r in TOPICS.items():
            if re.search(r, t["title"].lower()):
                rx = name
        t["files"] = [i for i, ts in files.items() if rx and rx in ts]
        if rx == "метеостанция" and "дача" in keys and keys["дача"] not in t.get("applies_to", []):
            t["applies_to"] = list(t.get("applies_to") or []) + [keys["дача"]]
    return j({"reasoning": f"Нашёл темы: {', '.join(present)}. Метеостанция — технический проект, применяется на даче.", "containers": tree})


# ---------- Классификация ----------
def parse_paragraphs(s: str) -> list[str]:
    parts = re.split(r"\n\n(?=\[\d+\] )", s.strip())
    return [re.sub(r"^\[\d+\] ", "", p) for p in parts]


def classify(v):
    paras = parse_paragraphs(v["paragraphs"])
    containers = v["containers"]
    mode = v["mode"]
    tops = []
    prev = None
    for p in paras:
        ts = topics_of(p)
        t = ts[0] if ts else None
        if t is None and prev is not None and (p.lower().startswith(v["ai_marker"].lower()) or len(tops) > 0):
            t = prev
        tops.append(t)
        prev = t if t else prev
    guess = None
    eff = mode
    if mode == "unknown":
        distinct = {t for t in tops if t}
        whole = " ".join(paras).lower()
        if "смешанн" in whole:
            guess = {"mode": "steady_state", "confidence": 55}
        elif len(distinct) >= 2 and len(paras) >= 4:
            guess = {"mode": "bootstrap", "confidence": 85}
        else:
            guess = {"mode": "steady_state", "confidence": 95}
        eff = guess["mode"]
    segs = []
    if eff == "bootstrap":
        cur = None
        for i, t in enumerate(tops, 1):
            if cur and cur["topic"] == t:
                cur["paragraphs"][-1][1] = i
            else:
                cur = {"topic": t, "paragraphs": [[i, i]]}
                segs.append(cur)
    else:
        counts = {}
        for t in tops:
            if t:
                counts[t] = counts.get(t, 0) + 1
        best = max(counts, key=counts.get) if counts else None
        segs = [{"topic": best, "paragraphs": [[1, len(paras)]]}]
    hint = (v.get("hint") or "").strip()
    hint_topics = topics_of(hint)
    out = []
    for s in segs:
        a, b = s["paragraphs"][0][0], s["paragraphs"][-1][1]
        text = " ".join(paras[a - 1:b])
        t = s["topic"]
        c = find_container(containers, t)
        seg = {"reasoning": "", "paragraphs": s["paragraphs"], "container": None, "new_container": None,
               "confidence": 40, "hint_container": None, "hint_confidence": None, "alternatives": [], "also_in": [],
               "content_type": None if v["content_type"] else ("diary" if "сегодня" in text.lower() else "thought"),
               "incomplete": "тот вариант" in text.lower(), "noise": 75 if v["content_type"] == "ai_dialogue" else 15}
        if c:
            seg.update(container=c["id"], confidence=88, reasoning=f"Речь о теме «{c['title']}».")
        elif t:
            seg.update(new_container={"name": TITLES[t], "type": "project", "parent": None, "description": f"Всё про {TITLES[t].lower()}"},
                       confidence=93, reasoning=f"Подходящего контейнера нет, тема «{TITLES[t]}» новая.")
        else:
            seg["reasoning"] = "Не понимаю, к чему это относится."
            if isinstance(containers, list) and containers:
                seg["alternatives"] = [{"container": containers[0]["id"], "confidence": 20}]
        others = [x for x in topics_of(text) if x != t]
        for o in others:
            oc = find_container(containers, o)
            if oc and (not c or oc["id"] != c["id"]):
                seg["also_in"].append({"container": oc["id"], "confidence": 60})
        if hint:
            named = [x for x in (containers if isinstance(containers, list) else [])
                     if x["title"].lower() in hint.lower()]
            ht = hint_topics[0] if hint_topics else None
            hc = find_container(containers, ht)
            if named and not hc:  # подсказка прямо называет существующий контейнер
                seg["hint_container"] = named[0]["id"]
                seg["hint_confidence"] = 70
            else:
                seg["hint_container"] = hc["id"] if hc else (TITLES.get(ht) if ht else hint)
                seg["hint_confidence"] = 80 if ht and ht == t else 40
        out.append(seg)
    return j({"reasoning": "Разбор по темам абзацев.", "mode_guess": guess, "segments": out})


# ---------- Вопросы ----------
def questions(v):
    qs = [{"text": "О чём эта запись: что за событие или проект имеется в виду?", "options": []}]
    if "фото" in v["text"].lower():
        qs.append({"text": "Это фотографии с дачи или семейный архив?", "options": ["С дачи", "Семейный архив"]})
    return j({"reasoning": "Без контекста не ясно, к чему относится запись.", "questions": qs})


# ---------- Уплотнение ----------
def compact(v):
    um = v["user_marker"].lower()
    lines = [l.strip() for l in v["text"].split("\n") if l.strip()]
    user = [re.sub(r"^\S+:\s*", "", l) for l in lines if l.lower().startswith(um)]
    if user:
        return "\n".join(user)
    sents = re.split(r"(?<=[.!?…])\s+", " ".join(lines))
    return " ".join(sents[: max(1, len(sents) // 2)])


# ---------- Извлечение ----------
def aspect_type(s: str) -> str:
    t = s.lower()
    if s.rstrip().endswith("?"):
        return "question"
    if re.search(r"значит|вывод|поэтому|итак", t):
        return "conclusion"
    if re.search(r"возможно|наверное|думаю|может быть", t):
        return "hypothesis"
    if re.search(r"нравится|плохо|отлично|ужасно|здорово", t):
        return "judgment"
    if re.search(r"\bможно\b|идея|а что если", t):
        return "idea"
    if re.search(r"надо|проверю|сделаю|завтра|планирую|план", t):
        return "plan"
    if re.search(r"пересчитал|купил|стоит|рубл|\d", t):
        return "fact"
    return "observation"


def extract(v):
    am = v["ai_marker"].lower()
    skip = re.compile(r"^(уточнение к записи|ручная правка документа|дополнение к записи|автор добавил|автор убрал|вопрос:)", re.I)
    lines = [re.sub(r"^\s*я:\s*", "", l, flags=re.I) for l in v["text"].split("\n")
             if l.strip() and not l.strip().lower().startswith(am)]
    kept, removing = [], False
    for l in lines:
        low = l.strip().lower()
        if low.startswith("автор убрал"):
            removing = True
        elif low.startswith("автор добавил"):
            removing = False
        if not removing and not skip.match(l.strip()):
            kept.append(l)
    text = " ".join(kept)
    text = re.sub(r"\[\[[^\]]*\]\]", "", text)
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if len(s.strip()) > 8]
    out = []
    for s in sents:
        s = re.sub(r"^(ответ|примечание автора)\s*:\s*", "", s, flags=re.I)
        if skip.match(s):
            continue
        out.append({"type": aspect_type(s), "text": s})
    return j({"reasoning": "Разложил запись на утверждения.", "aspects": out[:8]})


# ---------- Анализ пула ----------
def _stem_set(s):
    return {w[:5] for w in re.findall(r"[а-яёa-z]{5,}", s.lower())}


def analysis(v):
    asp = v["aspects"]
    by = {a["id"]: a for a in asp}
    decided = v["decided"] if isinstance(v["decided"], list) else []
    dec = " ".join(decided)
    res = {"reasoning": "Посмотрел связи в пуле.", "composites": [], "dissolve": [], "duplicates": [], "outdated": [],
           "conflicts": [], "structure": []}
    for p in v["similar_pairs"] if isinstance(v["similar_pairs"], list) else []:
        if p["similarity"] >= 0.9 and p["a"] in by and p["b"] in by:
            res["duplicates"].append({"aspect": p["b"], "duplicate_of": p["a"]})
    facts = [a for a in asp if a["type"] == "fact"]
    for new in facts:
        if "пересчитал" not in new["text"].lower():
            continue
        for old in facts:
            if old["id"] != new["id"] and (old.get("date") or "") < (new.get("date") or "") and "рубл" in old["text"].lower() \
                    and "буханк" in old["text"].lower() and f"outdated: {old['id']} — {new['id']}" not in dec:
                res["outdated"].append({"reasoning": "Новая запись пересчитала себестоимость.", "aspect": old["id"],
                                        "replaced_by": new["id"], "confidence": 85})
    ideas = [a for a in asp if a["type"] == "idea" and "крепить" in a["text"].lower()]
    if len(ideas) >= 2:
        a, b = ideas[0], ideas[1]
        if f"{a['id']} — {b['id']}" not in dec and f"{b['id']} — {a['id']}" not in dec:
            res["conflicts"].append({"reasoning": "Два разных места крепления датчика.", "a": a["id"], "b": b["id"],
                                     "assumed": "b", "assumption": "более поздняя идея — под крышей"})
    cand = v["candidates"] if isinstance(v["candidates"], dict) else {}
    rd = [by[i] for i in cand.get("resolved_decision", []) if i in by]
    q = [a for a in rd if a["type"] == "question"]
    h = [a for a in rd if a["type"] in ("hypothesis",)]
    c = [a for a in rd if a["type"] == "conclusion"]
    if q and h and c:
        res["composites"].append({"reasoning": "Вопрос, гипотеза и вывод про один выбор.", "extend": None,
                                  "composite_type": "resolved_decision", "from": [q[0]["id"], h[0]["id"], c[0]["id"]],
                                  "text": f"Решение: {c[0]['text']} (вопрос: {q[0]['text']})"})
    cont = v["container"]
    ents = v["entities"]
    if cont.get("type") == "росток" and len(ents) >= 3:
        res["structure"].append({"reasoning": "Появились цифры, планы и развитие.", "kind": "seed_to_project", "confidence": 75})
    if "теплиц" not in cont["title"].lower() and re.search(TOPICS["дача"], cont["title"].lower()):
        teplica = sorted({a["entity"] for a in asp if "теплиц" in a["text"].lower()})
        if teplica:
            res["structure"].append({"reasoning": "Теплица — отдельная подтема.", "kind": "subcontainer", "title": "Теплица",
                                     "type": "project", "description": "Всё, что растёт в теплице", "entities": teplica,
                                     "confidence": 80})
    return j(res)


# ---------- Ценность ----------
def value(v):
    title = v["container"]["title"]
    STATE["value_calls"][title] = STATE["value_calls"].get(title, 0) + 1
    out = []
    for it in v["items"]:
        t = it["text"].lower()
        if t.startswith("аренда") and STATE["value_calls"][title] >= 2:
            val = 25
        elif it.get("composite"):
            val = 90
        elif it["type"] == "judgment":
            val = 20
        elif re.search(r"\d", t):
            val = 85
        elif it["type"] in ("fact", "conclusion"):
            val = 75
        elif it["type"] in ("idea", "plan", "hypothesis"):
            val = 60
        else:
            val = 50
        out.append({"id": it["id"], "value": val})
    return j({"reasoning": "Главное — цифры и решения.", "values": out})


# ---------- Сравнение версий ----------
def compare(v):
    if v["object_kind"] == "base":
        lost = v["material"]["выпавшие_элементы"]
        return j({"reasoning": "Проверил выпавшее.",
                  "losses": [{"reasoning": "В элементе есть число." if re.search(r"\d", x["text"]) else "Мелочь.",
                              "id": x["id"], "significant": bool(re.search(r"\d", x["text"]))} for x in lost]})
    m = v["material"]
    old = m.split("ПРЕЖНЯЯ ВЕРСИЯ:", 1)[1].split("НОВАЯ ВЕРСИЯ:", 1)[0]
    new = m.split("НОВАЯ ВЕРСИЯ:", 1)[1]
    norm = lambda s: re.sub(r"\s+", " ", s.strip(" -*#").lower())
    new_lines = {norm(l) for l in new.split("\n") if l.strip()}
    losses = []
    for l in old.split("\n"):
        if l.strip() and (re.search(r"\d", l) or l.lstrip().startswith("- ")) and norm(l) not in new_lines and not l.startswith("#"):
            losses.append({"reasoning": "Пропал пункт прежней версии.", "what": l.strip(" -*"), "significant": True})
    return j({"reasoning": "Сравнил версии.", "losses": losses[:3]})


# ---------- Новый составной тип ----------
def new_type(v):
    props = []
    for c in v["clusters"]:
        ts = {a["type"] for a in c["aspects"]}
        if {"hypothesis", "plan", "fact"} <= ts:
            props.append({"reasoning": "Гипотеза, проверка и результат повторяются.", "cluster": c["cluster"],
                          "name": "experiment", "title": "Эксперимент", "types": ["hypothesis", "plan", "fact", "conclusion"],
                          "formula": "hypothesis + plan + fact + conclusion",
                          "example": "Предположил, что огурцам мало света → поставил лампу → выросли за неделю → свет важен."})
            break
    return j({"reasoning": "Посмотрел группы.", "proposals": props})


# ---------- Синтез ----------
def synth(v):
    title = v["container"]["title"]
    STATE["synth_calls"][title] = STATE["synth_calls"].get(title, 0) + 1
    second = STATE["synth_calls"][title] >= 2
    prim, sec, facts = [], [], []
    for line in v["base"].split("\n"):
        m = re.match(r"- \[(primary|secondary)\] \(([^;]*);[^)]*\) (.*)$", line)
        if not m:
            continue
        text = re.sub(r" ⟨.*⟩$", "", m.group(3))
        (prim if m.group(1) == "primary" else sec).append(text)
        if re.search(r"\d", text):
            facts.append((m.group(2), text))
    out = [f"=== ФАЙЛ: Сводный файл ===", f"# {title}", "", "## Суть", v["container"].get("description") or title, "",
           "## Главное"] + [f"- {t}" for t in prim]
    if sec and not second:
        out += ["", "## Подробности"] + [f"- {t}" for t in sec]
    prev = v["previous"] if isinstance(v["previous"], str) else ""
    notes = [l for l in prev.split("\n") if l.lower().startswith("примечание автора")]
    if notes:
        out += ["", "## Заметки автора"] + notes
    if isinstance(v["restore"], list) and v["restore"]:
        out += ["", "## Возвращено по просьбе автора"] + [f"- {x}" for x in v["restore"]]
    if v.get("completed"):
        out += ["", "## Итоговый результат", "Проект завершён."]
    if "бизнес-план" in str(v.get("style") or ""):
        out += ["", "## Цифры", "Оформлено в стиле контейнера (бизнес-план)."]
    if facts:
        out += ["", "=== ФАЙЛ: Дневник ===", f"# Дневник: {title}", ""] + [f"- {d}: {t}" for d, t in facts]
    return "\n".join(out) + "\n"


# ---------- Пороги ----------
def thresholds(v):
    t = {x["name"]: x for x in v["thresholds"]}
    st = v["stats"]
    c = st["classification"]
    n = lambda k: (c.get(k) or {}).get("n", 0) if isinstance(c.get(k), dict) else 0
    cur = t["classification"]["current"]
    recs = []
    if n("auto_moved_away"):
        recs.append({"name": "classification", "value": min(100, cur + 5),
                     "reasoning": f"Автор перенёс {n('auto_moved_away')} записей, разложенных без вопроса."})
    elif n("asked_model_right") >= 1 and cur > 60:
        recs.append({"name": "classification", "value": max(60, cur - 10),
                     "reasoning": f"Модель была права в {n('asked_model_right')} вопросах из {n('asked')}."})
    else:
        recs.append({"name": "classification", "value": max(0, cur - 5), "reasoning": "Вопросов много, ошибок нет."})
    recs.append({"name": "value_min", "value": t["value_min"]["current"], "reasoning": "Оставить как есть."})
    if "seed_dormancy_days" in t:
        recs.append({"name": "seed_dormancy_days", "value": 120, "reasoning": "Росток развивается медленно."})
    return j({"reasoning": "Смотрю на ошибки раскладки и лишние вопросы.",
              "summary": "Данных пока немного; раскладку можно слегка подстроить.", "recommendations": recs})

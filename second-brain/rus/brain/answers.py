"""Приём ответов из open-questions.md (раздел 7): каждый вид вопроса — свой обработчик.
Каждое решение пишется в лог рефлексии (пара «предположение — решение»), вопрос уходит в архив."""
from __future__ import annotations

import difflib
import re

from . import ops
from . import util as U
from .aspects import SIMPLE_TYPES
from .classify import propose_also_in
from .synthesis_base import _link_conflict_entities, mark_stage
from .vault import RU_TYPE


class AnswerError(Exception):
    pass


def _qnum(qid: str) -> int:
    m = re.match(r"Q(\d+)", qid)
    return int(m.group(1)) if m else 0


def process(ctx) -> int:
    answers = ctx.q.read_answers()
    ctx.clarifications = {}
    n = 0
    for qid in sorted(answers, key=_qnum):
        q = ctx.q.open.get(qid)
        if q is None:
            continue
        idx, text, err = answers[qid]
        if err:
            q["note"] = err
            continue
        opt = q["options"][idx] if idx is not None and idx < len(q["options"]) else None
        h = HANDLERS.get(q["kind"])
        if h is None:
            q["note"] = "Программа не знает, как применить ответ на этот вопрос."
            continue
        if opt is None and text and not q.get("free_text"):
            q["note"] = "Здесь нужно отметить один из вариантов галочкой."
            continue
        try:
            res = h(ctx, q, opt, text) or {}
        except AnswerError as e:
            q["note"] = str(e)
            continue
        label = res.get("answer") or (opt["label"] if opt else text)
        ctx.logs.decision(q.get("ref"), q["kind"], q.get("data", {}).get("entity") or q.get("data", {}).get("container") or qid,
                          res.get("decision", label), res.get("matched"))
        ctx.logs.archive_question(q, label)
        ctx.q.close(qid)
        _clear_review_flag(ctx, q)
        n += 1
        ctx.count("answers")
        ctx.checkpoint()
    _flush_clarifications(ctx)
    if n:
        ctx.say(f"Принято ответов: {n}.")
    return n


def _clear_review_flag(ctx, q):
    eid = q.get("data", {}).get("entity")
    e = ctx.w.entities.get(eid) if eid else None
    if e and e.fm.get("needs_review") and not ctx.q.for_entity(eid) and not e.fm.get("quarantine"):
        e.fm["needs_review"] = False
        e.fm["review_reason"] = None
        ctx.w.save_entity(e)


# ---------- общие действия ----------
TYPED = re.compile(r"^(.*?)\s*\((проект|росток|вопрос|project|seed|question)\)\s*$", re.I)


def resolve_or_create(ctx, text: str) -> str | None:
    t = text.strip().strip("«»\"' ")
    if not t:
        raise AnswerError("Пустое название контейнера.")
    if t.lower() in ("без контейнера", "unsorted", "нет"):
        return None
    m = TYPED.match(t)
    ntype = "project"
    if m:
        t, ntype = m.group(1).strip(), RU_TYPE[m.group(2).lower()]
    n = ctx.w.node_by_title(t)
    if n:
        return n.id
    node = ops.create_container(ctx, {"name": t, "type": ntype}, "пользователь")
    return node.id


def place_entity(ctx, e, target: str | None, actor: str, why: str):
    """Определить контейнер записи: из карантина — продолжить конвейер; обработанную — перенести."""
    w = ctx.w
    st = ops.stage(ctx, e.id)
    if st in ("quarantine", "quarantine_wait"):
        e.fm["container_id"] = target
        e.fm["quarantine"] = False
        e.fm["needs_review"] = bool([q for q in ctx.q.for_entity(e.id) if q["kind"] != "classify"])
        e.fm["review_reason"] = "incomplete" if e.fm["needs_review"] else None
        w.save_entity(e)
        ops.set_stage(ctx, e.id, "classified")
        t = f"[[{w.nodes[target].title}]]" if target in w.nodes else "без контейнера"
        ctx.logs.change(actor, f"[[{e.title}]] → {t} ({why})")
        if target:
            propose_also_in(ctx, e)
    else:
        ops.move_entity(ctx, e, target, actor, why)
    for q in list(ctx.q.for_entity(e.id)):
        if q["kind"] == "classify":
            ctx.q.close(q["id"])


def _entity(ctx, q):
    e = ctx.w.entities.get(q["data"].get("entity"))
    if e is None:
        return None
    return e


def _container(ctx, q):
    cid = q["data"].get("container")
    return cid if cid in ctx.w.nodes else None


# ---------- обработчики ----------
def h_classify(ctx, q, opt, text):
    w = ctx.w
    e = _entity(ctx, q)
    if e is None:
        return {"answer": "запись не найдена — вопрос закрыт"}
    cls = w.state["cls"].get(e.id, {})
    if opt:
        v = opt["value"]
        if v.get("to"):
            if v["to"] not in w.nodes:
                raise AnswerError("Этого контейнера уже нет — выберите другой вариант или впишите название.")
            target = v["to"]
        elif v.get("create"):
            ex = w.node_by_title(v["create"].get("name"))
            target = ex.id if ex else ops.create_container(ctx, v["create"], "пользователь").id
        else:
            target = None
        label = opt["label"]
    elif text:
        target = resolve_or_create(ctx, text)
        label = text
    else:
        raise AnswerError("Отметьте вариант или впишите название контейнера.")
    place_entity(ctx, e, target, "пользователь", "ответ на вопрос")
    choice = cls.get("choice")
    if choice and str(choice).startswith("new:") and target in w.nodes:
        matched = w.nodes[target].title.lower() == str(choice)[4:].lower()
    else:
        matched = target == choice
    return {"answer": label, "decision": target, "matched": matched}


def h_mode(ctx, q, opt, text):
    if not opt:
        raise AnswerError("Отметьте один из вариантов.")
    it = ctx.w.state["items"].get(q["data"]["item"])
    if it is None:
        return {"answer": "файл не найден — вопрос закрыт"}
    it["mode"] = opt["value"]
    it["stage"] = "ready"
    return {"decision": opt["value"], "matched": opt["value"] == q["data"].get("guess")}


def h_also_in(ctx, q, opt, text):
    e = _entity(ctx, q)
    cid = _container(ctx, q)
    if not opt:
        raise AnswerError("Отметьте «Да» или «Нет».")
    if e and cid and opt["value"] == "yes":
        ops.add_also_in(ctx, e, cid, "пользователь")
    return {"decision": opt["value"], "matched": opt["value"] == "yes"}


def h_clarify(ctx, q, opt, text):
    e = _entity(ctx, q)
    ans = "; ".join(x for x in [opt["label"] if opt else "", text] if x)
    if not ans:
        raise AnswerError("Напишите ответ после «Ответ:» или отметьте вариант.")
    if e is not None:
        ctx.clarifications.setdefault(e.id, []).append((q["data"].get("question", ""), ans))
    return {"answer": ans, "decision": "answered"}


def _flush_clarifications(ctx):
    """Ответы на уточняющие вопросы → новая запись в _staging (текст исходной записи не меняется, разделы 4.3, 7.4)."""
    w = ctx.w
    for eid, pairs in (getattr(ctx, "clarifications", {}) or {}).items():
        e = w.entities.get(eid)
        if e is None:
            continue
        c = w.nodes.get(e.container_id)
        lines = [U.ru_date(U.today())] + ([f"hint: {c.title}"] if c else []) + ["mode: steady_state", "",
                 f"Уточнение к записи [[{e.title}]] от {U.ru_date(e.created)}.", ""]
        for qtext, ans in pairs:
            lines += [f"Вопрос: {qtext}", f"Ответ: {ans}", ""]
        path = U.unique_path(w.p.staging, U.safe_name(f"уточнение — {e.title}", 90), ".txt")
        U.atomic_write_text(path, "\n".join(lines))
        ctx.logs.change("пользователь", f"ответ на уточнение к [[{e.title}]] — новая запись «{path.name}» в _staging")
    ctx.clarifications = {}


def outdate_aspect(ctx, cid, aid, replaced_by, by: str):
    w = ctx.w
    pool = w.pool(cid)
    a = pool["aspects"].get(aid)
    if a is None:
        return
    group = [a] + [z for z in pool["aspects"].values() if z.get("duplicate_of") == aid]
    need_analysis = False
    for z in group:
        z["status_before"] = z.get("status")
        if z.get("status") == "in_composite":
            need_analysis = True
        z["status"] = "outdated"
        z["replaced_by"] = replaced_by
        z["outdated_by"] = by
    for c in pool["composites"].values():
        if c.get("status") != "outdated" and set(c["from"]) & {z["id"] for z in group}:
            c["status"] = "needs_review"
            need_analysis = True
    pool["conflicts"] = [k for k in pool["conflicts"] if aid not in (k["a"], k["b"])]
    w.save_pool(cid)
    if need_analysis:
        w.mark_dirty(cid, "outdated")
    else:
        mark_stage(w, cid, "assemble", "outdated")
    for z in group:  # запись целиком устарела, если устарели все её аспекты (раздел 6.11)
        e = w.entities.get(z["source_entity"])
        if e and e.fm.get("status") == "processed":
            mine = [x for c2 in [e.container_id] + e.also_in_ids if c2 in w.nodes
                    for x in w.pool(c2)["aspects"].values() if x["source_entity"] == e.id]
            if mine and all(x.get("status") == "outdated" for x in mine):
                e.fm["status"] = "outdated"
                w.save_entity(e)
                w.state.setdefault("auto_outdated", {})[e.id] = True


def h_outdated(ctx, q, opt, text):
    if not opt:
        raise AnswerError("Отметьте «Да» или «Нет».")
    cid = _container(ctx, q)
    d = q["data"]
    if cid is None:
        return {"answer": "контейнера уже нет — вопрос закрыт"}
    if opt["value"] == "yes":
        outdate_aspect(ctx, cid, d["aspect"], d["replaced_by"], "user")
        ctx.logs.change("пользователь", f"[[{ctx.w.nodes[cid].title}]]: {d['aspect']} устарел, заменён {d['replaced_by']}")
    else:
        ctx.w.pool(cid)["rejected"].append({"kind": "outdated", "a": d["aspect"], "b": d["replaced_by"]})
        ctx.w.save_pool(cid)
    return {"decision": opt["value"], "matched": opt["value"] == "yes"}


def h_conflict(ctx, q, opt, text):
    if not opt:
        raise AnswerError("Отметьте один из вариантов.")
    cid = _container(ctx, q)
    if cid is None:
        return {"answer": "контейнера уже нет — вопрос закрыт"}
    w = ctx.w
    pool = w.pool(cid)
    k = next((x for x in pool["conflicts"] if x.get("key") == q["data"]["key"]), None)
    if k is None:
        return {"answer": "противоречие уже снято — вопрос закрыт"}
    v = opt["value"]
    if v == "none":
        k["status"] = "rejected"
        pool["rejected"].append({"kind": "conflict", "a": k["a"], "b": k["b"]})
        a, b = pool["aspects"].get(k["a"]), pool["aspects"].get(k["b"])
        if a and b:
            _link_conflict_entities(ctx, a["source_entity"], b["source_entity"], add=False)
    else:
        k["status"] = "resolved"
        k["decision"] = v
    w.save_pool(cid)
    mark_stage(w, cid, "assemble", "conflict")
    txt = {"a": "верно первое", "b": "верно второе", "both": "развилка — оба направления", "none": "не противоречие"}[v]
    ctx.logs.change("пользователь", f"[[{w.nodes[cid].title}]]: противоречие {k['a']} ⚔ {k['b']} — {txt}")
    return {"decision": v, "matched": v == k.get("assumed")}


def h_structure_seed(ctx, q, opt, text):
    if not opt:
        raise AnswerError("Отметьте «Да» или «Нет».")
    cid = _container(ctx, q)
    if cid is None:
        return {"answer": "контейнера уже нет"}
    node = ctx.w.nodes[cid]
    if opt["value"] == "yes":
        node.fm["type"] = "project"
        ctx.w.save_node(node)
        ctx.logs.change("пользователь", f"росток [[{node.title}]] стал проектом")
    else:
        ctx.w.pool(cid)["rejected"].append({"kind": "seed_to_project", "a": cid, "b": None})
        ctx.w.save_pool(cid)
    return {"decision": opt["value"], "matched": opt["value"] == "yes"}


def h_structure_sub(ctx, q, opt, text):
    cid = _container(ctx, q)
    if cid is None:
        return {"answer": "контейнера уже нет"}
    d = q["data"]
    spec = dict(d["spec"])
    if opt and opt["value"] == "no":
        ctx.w.pool(cid)["rejected"].append({"kind": "subcontainer", "a": cid, "b": spec["name"].lower()})
        ctx.w.save_pool(cid)
        return {"decision": "no", "matched": False}
    if text and not opt:
        spec["name"] = text.strip()
    ops.create_subcontainer(ctx, cid, spec, d["entities"], "пользователь")
    return {"answer": (opt["label"] if opt else text), "decision": "yes", "matched": True}


def h_base_loss(ctx, q, opt, text):
    if not opt:
        raise AnswerError("Отметьте один из вариантов.")
    cid = _container(ctx, q)
    if cid is None:
        return {"answer": "контейнера уже нет"}
    pool = ctx.w.pool(cid)
    pool.setdefault("accepted_losses", [])
    aid = q["data"]["aspect"]
    if opt["value"] == "keep":
        if aid not in pool["accepted_losses"]:
            pool["accepted_losses"].append(aid)
    else:
        rec = pool["composites"].get(aid) or pool["aspects"].get(aid)
        if rec is not None:
            rec["pinned"] = True
        mark_stage(ctx.w, cid, "assemble", "restore")
    ctx.w.save_pool(cid)
    return {"decision": opt["value"], "matched": opt["value"] == "restore"}


def h_product_loss(ctx, q, opt, text):
    if not opt:
        raise AnswerError("Отметьте один из вариантов.")
    w = ctx.w
    cid = _container(ctx, q)
    if cid is None:
        return {"answer": "контейнера уже нет"}
    d = q["data"]
    title = d["product"]
    prod = next(((p, fm, b) for p, fm, b in w.products_of(cid) if p.stem == title), None)
    v = opt["value"]
    if v == "intentional":
        if prod:
            p, fm, body = prod
            fm["accepted_losses"] = list(fm.get("accepted_losses") or []) + [d["what"]]
            _clear_product_review(ctx, cid, title, fm)
            U.write_md(p, fm, body)
    elif v == "restore":
        w.state["restore_requests"].setdefault(cid, []).append(d["what"])
    elif v == "rollback":
        key = ctx.ver.key_product(cid, title)
        old = ctx.ver.read_at(key, 1)
        if old is None or prod is None:
            raise AnswerError("Прежней версии документа нет — выберите другой вариант.")
        p, fm, body = prod
        fm["needs_review"] = False
        fm["review_reason"] = None
        U.write_md(p, fm, old)
        ctx.ver.snapshot(key, old)
        w.products = [(pp, ff, old if pp == p else bb) for pp, ff, bb in w.products]
        ctx.logs.change("пользователь", f"документ [[{w.path_key(w.nodes[cid])}/{title}|{title}]] откатан к прежней версии")
    return {"decision": v, "matched": v != "intentional"}


def _clear_product_review(ctx, cid, title, fm):
    others = [q for q in ctx.q.open.values() if q["kind"] == "product_loss"
              and q["data"].get("container") == cid and q["data"].get("product") == title]
    if len(others) <= 1:
        fm["needs_review"] = False
        fm["review_reason"] = None


def h_composite_type(ctx, q, opt, text):
    if not opt:
        raise AnswerError("Отметьте «Да» или «Нет».")
    w = ctx.w
    p = q["data"]["proposal"]
    if opt["value"] == "yes":
        path = w.p.system / "composite_types.json"
        types = U.read_json(path, {}) or {}
        types[p["name"]] = {"title": p["title"], "types": [t for t in p["types"] if t in SIMPLE_TYPES], "formula": p["formula"]}
        U.write_json(path, types)
        cid = q["data"].get("container")
        if cid in w.nodes:
            w.mark_dirty(cid, "new_composite_type")
        ctx.logs.change("пользователь", f"добавлен составной тип «{p['title']}» ({p['formula']})")
    else:
        w.state.setdefault("rejected_types", []).append(p["name"])
    return {"decision": opt["value"], "matched": opt["value"] == "yes"}


def h_dormant(ctx, q, opt, text):
    if not opt:
        raise AnswerError("Отметьте один из вариантов.")
    cid = _container(ctx, q)
    if cid is None:
        return {"answer": "контейнера уже нет"}
    node = ctx.w.nodes[cid]
    v = opt["value"]
    if v == "active":
        node.fm["last_modified"] = U.today()
    else:
        node.fm["container_status"] = v
    ctx.w.save_node(node)
    ctx.logs.change("пользователь", f"росток [[{node.title}]]: {opt['label'].lower()}")
    return {"decision": v, "matched": v != "active"}


def h_revalidate(ctx, q, opt, text):
    if not opt:
        raise AnswerError("Отметьте один из вариантов.")
    w = ctx.w
    v = opt["value"]
    if v.get("move") and v.get("to") in w.nodes and v["move"] in w.entities:
        e = w.entities[v["move"]]
        place_entity(ctx, e, v["to"], "пользователь", "ревалидация")
    elif v.get("also") and v.get("to") in w.nodes and v["also"] in w.entities:
        ops.add_also_in(ctx, w.entities[v["also"]], v["to"], "пользователь")
    return {"decision": v, "matched": not v.get("ok")}


def original_text(ctx, e) -> str | None:
    from .ingest import load_item_paragraphs, segment_text, str_to_ranges
    it = ctx.w.state["items"].get((ctx.w.state["cls"].get(e.id) or {}).get("item"))
    if not it:
        return None
    try:
        paras = load_item_paragraphs(ctx, it)
    except OSError:
        return None
    ranges = str_to_ranges(e.fm.get("segment")) or [[1, len(paras)]]
    return segment_text(paras, ranges)


def _sentences(text: str) -> list[str]:
    out = []
    for para in (text or "").replace("\r\n", "\n").split("\n"):
        out += [x.strip() for x in re.split(r"(?<=[.!?…])\s+", para) if x.strip()]
    return out


def text_diff(old: str, new: str) -> tuple[list[str], list[str]]:
    """Что добавлено и что убрано — по предложениям: новая запись получает только правку,
    а не весь текст заново (иначе устаревшие факты вернулись бы как свежие)."""
    a, b = _sentences(old), _sentences(new)
    added, removed = [], []
    for line in difflib.ndiff(a, b):
        if line.startswith("+ "):
            added.append(line[2:])
        elif line.startswith("- "):
            removed.append(line[2:])
    return added, removed


def h_text_changed(ctx, q, opt, text):
    if not opt:
        raise AnswerError("Отметьте один из вариантов.")
    w = ctx.w
    e = _entity(ctx, q)
    if e is None:
        return {"answer": "запись не найдена"}
    orig = original_text(ctx, e)
    if orig is None or U.sha1(orig) != w.state["text_hash"].get(e.id):
        raise AnswerError("Не удалось восстановить исходный текст из _исходники — верните его вручную (Ctrl+Z в Obsidian) и отметьте вариант снова.")
    edited = e.text
    if opt["value"] == "new":
        c = w.nodes.get(e.container_id)
        added, removed = text_diff(orig, edited)
        lines = [U.ru_date(U.today())] + ([f"hint: {c.title}"] if c else []) + ["mode: steady_state", "",
                 f"Дополнение к записи [[{e.title}]] от {U.ru_date(e.created)} (правка текста).", ""]
        if added:
            lines += ["Автор добавил или переписал:", ""] + added + [""]
        if removed:
            lines += ["Автор убрал:", ""] + removed + [""]
        if not added and not removed:
            lines += [edited]
        path = U.unique_path(w.p.staging, U.safe_name(f"правка — {e.title}", 90), ".txt")
        U.atomic_write_text(path, "\n".join(lines))
        ctx.logs.change("пользователь", f"правка текста [[{e.title}]] оформлена новой записью «{path.name}»")
    e.text = orig
    w.save_entity(e)
    return {"decision": opt["value"]}


def h_dup_fix(ctx, q, opt, text):
    w = ctx.w
    cid = _container(ctx, q)
    if opt and opt["value"] == "ok" and not text:
        return {"decision": "ok", "matched": True}
    ids = re.findall(r"\ba\d+\b", text or "")
    if cid is None or not ids:
        raise AnswerError("Не нашёл номеров аспектов (вида a12). Впишите номера ошибочных дублей или отметьте «Все связи верны».")
    pool = w.pool(cid)
    fixed = []
    for aid in ids:
        a = pool["aspects"].get(aid)
        if a and a.get("duplicate_of"):
            pool["rejected"].append({"kind": "duplicate", "a": aid, "b": a["duplicate_of"]})
            a["duplicate_of"] = None
            fixed.append(aid)
    if not fixed:
        raise AnswerError("Указанные аспекты не связаны как дубли — проверьте номера.")
    w.save_pool(cid)
    mark_stage(w, cid, "value", "dup_fix")
    ctx.logs.change("пользователь", f"[[{w.nodes[cid].title}]]: сняты связи дублей {', '.join(fixed)}")
    return {"answer": f"сняты связи: {', '.join(fixed)}", "decision": fixed, "matched": False}


HANDLERS = {
    "classify": h_classify, "mode": h_mode, "also_in": h_also_in, "clarify": h_clarify,
    "outdated": h_outdated, "conflict": h_conflict, "structure_seed": h_structure_seed,
    "structure_sub": h_structure_sub, "base_loss": h_base_loss, "product_loss": h_product_loss,
    "composite_type": h_composite_type, "dormant": h_dormant, "revalidate": h_revalidate,
    "text_changed": h_text_changed, "dup_fix": h_dup_fix,
}

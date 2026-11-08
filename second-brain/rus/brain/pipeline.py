"""Фаза 1, шаги 4–7 для каждой записи: вопросы, уплотнение, векторы, извлечение аспектов (разделы 6.6–6.9).
Стадии записи: classified → asked → compacted → embedded → done; карантин: quarantine → quarantine_wait."""
from __future__ import annotations

from . import ops
from . import util as U
from .aspects import SIMPLE_TYPES
from .index import index_entity

ACTIVE = ("quarantine", "classified", "asked", "compacted", "embedded")


def run_all(ctx, only: list[str] | None = None):
    """Довести до конца все записи в незавершённых стадиях (по дате, от старых к новым)."""
    w = ctx.w
    st = w.state["entity_stage"]
    ids = [eid for eid, s in st.items() if s in ACTIVE and eid in w.entities and (only is None or eid in only)]
    ids.sort(key=lambda i: (w.entities[i].created, i))
    for k, eid in enumerate(ids, 1):
        e = w.entities[eid]
        if only is None:
            ctx.progress("Обработка записей", k, len(ids), e.title)
        elif len(ids) > 1:
            ctx.progress("Записи файла", k, len(ids), e.title, level=1, echo=False)
        advance(ctx, e)


def advance(ctx, e):
    steps = {"quarantine": step_quarantine, "classified": step_questions, "asked": step_compact,
             "compacted": step_embed, "embedded": step_extract}
    guard = 0
    while guard < 10:
        guard += 1
        st = ops.stage(ctx, e.id)
        fn = steps.get(st)
        if fn is None:
            return
        fn(ctx, e)
        ctx.checkpoint()


# ---------- шаг 4: уточняющие вопросы ----------
def _cls(ctx, e) -> dict:
    return ctx.w.state["cls"].setdefault(e.id, {})


def step_quarantine(ctx, e):
    cls = _cls(ctx, e)
    reasons = []
    if e.fm.get("review_reason") == "low_confidence":
        reasons.append("low_confidence")
    if e.fm.get("incomplete"):
        reasons.append("incomplete")
    if reasons and not cls.get("asked"):
        ask_clarify(ctx, e, reasons)
    cls["asked"] = True
    ops.set_stage(ctx, e.id, "quarantine_wait")


def step_questions(ctx, e):
    cls = _cls(ctx, e)
    # В Bootstrap неполные записи идут дальше без вопросов (раздел 6.6)
    if e.fm.get("incomplete") and cls.get("mode") != "bootstrap" and not cls.get("asked"):
        ask_clarify(ctx, e, ["incomplete"])
    cls["asked"] = True
    ops.set_stage(ctx, e.id, "asked")


def _validate_questions(o):
    qs = o.get("questions")
    if not isinstance(qs, list):
        return ["нет списка questions"]
    errs = []
    for i, q in enumerate(qs, 1):
        if not isinstance(q, dict) or not str(q.get("text") or "").strip():
            errs.append(f"вопрос {i}: нужен text")
        elif not isinstance(q.get("options", []), list):
            errs.append(f"вопрос {i}: options — список строк")
    return errs


def ask_clarify(ctx, e, reasons: list[str]):
    w = ctx.w
    cls = _cls(ctx, e)
    cand = []
    for cid in [cls.get("choice")] + [a.get("container") for a in cls.get("alternatives") or []]:
        if cid in w.nodes and cid not in [c["id"] for c in cand]:
            n = w.nodes[cid]
            cand.append({"id": cid, "title": n.title, "description": n.description})
    info = {"выбор модели": cls.get("choice"), "уверенность": cls.get("confidence"),
            "альтернативы": cls.get("alternatives"), "подсказка автора": e.fm.get("hint"),
            "рассуждение": cls.get("reasoning")}
    mx = int(ctx.cfg["limits"]["max_questions_per_entity"])
    obj = ctx.llm.json("Вопросы", {
        "reason": ", ".join(reasons), "classification": info, "containers": cand or "нет подходящих",
        "date": U.ru_date(e.created), "text": e.text, "max_questions": mx,
    }, validate=_validate_questions, subject=f"[[{e.title}]]")
    n = 0
    for qd in (obj.get("questions") or [])[:mx]:
        text = str(qd["text"]).strip()
        opts = [{"label": str(o).strip(), "value": str(o).strip()} for o in qd.get("options") or [] if str(o).strip()]
        ctx.q.add("clarify", "Уточнение к записи",
                  f"Запись [[{e.title}]] ({U.ru_date(e.created)}).\n\n**{text}**",
                  options=opts, free_text=True,
                  free_hint="Ответ станет новой записью в _staging со ссылкой на эту запись (сама запись не меняется).",
                  data={"entity": e.id, "question": text}, dedup=f"clarify:{e.id}:{U.sha1(text)[:10]}",
                  ref=cls.get("ref"))
        n += 1
    if n:
        e.fm["needs_review"] = True
        if not e.fm.get("review_reason"):
            e.fm["review_reason"] = "incomplete"
        w.save_entity(e)
        ctx.count("clarify_questions", n)


# ---------- шаг 5: уплотнение ----------
def step_compact(ctx, e):
    w = ctx.w
    cls = _cls(ctx, e)
    noise = cls.get("noise") or 0
    thr = ctx.thr("compaction", e.container_id) - ctx.cfg.source_shift(e.fm.get("source"))
    need = noise >= thr
    if not cls.get("compaction_logged"):
        ctx.logs.reflect("compaction", e.id, need, noise, threshold=thr, source=e.fm.get("source"))
        cls["compaction_logged"] = True
    if need and not e.compact:
        um, am = ctx.cfg.markers()
        src = e.text

        def check(t):
            return ["сжатый текст не короче исходного"] if len(t) > len(src) * 1.1 and len(src) > 400 else []
        text = ctx.llm.text("Уплотнение", {"date": U.ru_date(e.created), "content_type": e.fm.get("content_type") or "",
                                           "user_marker": um[0], "ai_marker": am[0], "text": src},
                            validate=check, subject=f"[[{e.title}]]")
        e.compact = text.strip()
        e.fm["compacted"] = True
        w.save_entity(e)
        ctx.logs.change("модель", f"[[{e.title}]] уплотнена: {len(src)} → {len(e.compact)} знаков (зашумлённость {noise}, порог {thr})")
        ctx.count("compacted")
    ops.set_stage(ctx, e.id, "compacted")


# ---------- шаг 6: векторы и бесплатная ревалидация ----------
def step_embed(ctx, e):
    v = index_entity(ctx, e)
    if _cls(ctx, e).get("mode") != "bootstrap":
        revalidation_hint(ctx, e, v)
    ops.set_stage(ctx, e.id, "embedded")


def revalidation_hint(ctx, e, vec):
    """Если новая запись почти совпадает по смыслу с записью другого контейнера — предложить проверить (раздел 6.8)."""
    w = ctx.w
    thr = float(ctx.thr("neighbor_similarity", e.container_id))
    for nid, sim in ctx.vs.search("entities", vec, k=5, exclude=[e.id]):
        if sim < thr:
            break
        n = w.entities.get(nid)
        if n is None or ops.stage(ctx, nid) != "done" or n.fm.get("quarantine"):
            continue
        ce, cn = e.container_id, n.container_id
        if ce == cn or (cn and cn in e.also_in_ids) or (ce and ce in n.also_in_ids):
            continue
        te = f"«{w.nodes[ce].title}»" if ce in w.nodes else "без контейнера"
        tn = f"«{w.nodes[cn].title}»" if cn in w.nodes else "без контейнера"
        opts = []
        if cn:
            opts.append({"label": f"Перенести новую запись в {tn}", "value": {"move": e.id, "to": cn}})
        if ce:
            opts.append({"label": f"Перенести старую запись в {te}", "value": {"move": n.id, "to": ce}})
        if ce and cn:
            opts.append({"label": f"Новая запись относится и к {tn} (общая)", "value": {"also": e.id, "to": cn}})
        opts.append({"label": "Всё разложено верно", "value": {"ok": True}})
        ref = ctx.logs.reflect("revalidation_hint", e.id, {"neighbor": nid, "similarity": round(sim, 3)}, None)
        ctx.q.add("revalidate", "Похожие записи в разных местах",
                  f"Новая запись [[{e.title}]] ({te}) очень похожа на запись [[{n.title}]] ({tn}), сходство {sim:.2f}. "
                  "Возможно, одна из них разложена неверно.",
                  options=opts, data={"entity": e.id, "neighbor": nid},
                  dedup=f"reval:{min(e.id, nid)}:{max(e.id, nid)}", ref=ref)
        ctx.count("revalidation_hints")
        return


# ---------- шаг 7: извлечение аспектов ----------
def _validate_aspects(o):
    a = o.get("aspects")
    if not isinstance(a, list):
        return ["нет списка aspects"]
    errs = []
    for i, x in enumerate(a, 1):
        if not isinstance(x, dict):
            errs.append(f"аспект {i} — не объект")
        elif x.get("type") not in SIMPLE_TYPES:
            errs.append(f"аспект {i}: type «{x.get('type')}» — нужен один из: {', '.join(SIMPLE_TYPES)}")
        elif not str(x.get("text") or "").strip():
            errs.append(f"аспект {i}: пустой text")
    return errs


def _drop_leftovers(ctx, e):
    """Если прошлый прогон оборвался посреди извлечения, в пулах могли остаться аспекты этой записи —
    убрать их, чтобы повторное извлечение не дало дублей."""
    w = ctx.w
    for cid in [e.container_id] + list(e.also_in_ids):
        if cid not in w.nodes:
            continue
        pool = w.pool(cid)
        stale = [aid for aid, a in pool["aspects"].items() if a.get("source_entity") == e.id]
        if stale:
            for aid in stale:
                del pool["aspects"][aid]
            ctx.vs.remove("aspects", stale)
            w.save_pool(cid)
    e.fm["aspect_ids"] = []


def step_extract(ctx, e):
    w = ctx.w
    if not e.container_id or e.container_id not in w.nodes:
        # без контейнера: только векторы, аспекты появятся, когда запись получит контейнер
        e.fm["status"] = "processed"
        w.save_entity(e)
        ops.set_stage(ctx, e.id, "done")
        return
    node = w.nodes[e.container_id]
    _drop_leftovers(ctx, e)
    um, am = ctx.cfg.markers()
    obj = ctx.llm.json("Извлечение", {
        "container": f"{node.title}" + (f" — {node.description}" if node.description else ""),
        "date": U.ru_date(e.created), "content_type": e.fm.get("content_type") or "",
        "user_marker": um[0], "ai_marker": am[0], "text": e.work_text,
    }, validate=_validate_aspects, subject=f"[[{e.title}]]")
    recs = [{"type": a["type"], "text": str(a["text"]).strip()} for a in obj["aspects"]]
    ids = ops.add_aspects(ctx, e, e.container_id, recs)
    vecs = [ctx.vs.get("aspects", i) for i in ids]
    for cid in e.also_in_ids:
        if cid in w.nodes:
            ops.add_aspects(ctx, e, cid, recs, vecs)
    e.fm["status"] = "processed"
    w.save_entity(e)
    w.state["text_hash"][e.id] = U.sha1(e.text)
    ops.set_stage(ctx, e.id, "done")
    ctx.logs.change("модель", f"[[{e.title}]]: извлечено аспектов — {len(ids)}")
    ctx.count("aspects", len(ids))
    ctx.count("entities_done")

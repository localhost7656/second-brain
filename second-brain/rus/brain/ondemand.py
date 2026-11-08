"""Операции по требованию (раздел 10): глубокая ревалидация, поиск новых составных типов (раздел 5.3)."""
from __future__ import annotations

from . import ops
from . import util as U
from .aspects import SIMPLE_TYPES, composite_types
from .classify import _validator, containers_for_prompt
from .ingest import numbered, split_paragraphs


def revalidate_queue(ctx, cid: str | None) -> list[str]:
    w = ctx.w
    out = []
    for e in sorted(w.entities.values(), key=lambda x: (x.created, x.id)):
        if ops.stage(ctx, e.id) != "done":
            continue
        if cid is None or e.container_id == cid or (cid == "_unsorted" and not e.container_id):
            out.append(e.id)
    return out


def revalidate(ctx, cid: str | None, queue: list[str]):
    """Перепроверка классификации уже обработанных записей: модель не переносит сама, только предлагает."""
    w = ctx.w
    st = w.state.setdefault("revalidation", {})
    key = cid or "*"
    if st.get("target") != key:
        st.clear()
        st.update({"target": key, "queue": list(queue)})
    um, am = ctx.cfg.markers()
    total = len(st["queue"])
    proposals = 0
    while st["queue"]:
        eid = st["queue"][0]
        e = w.entities.get(eid)
        ctx.progress("Ревалидация", total - len(st["queue"]) + 1, total, e.title if e is not None else "", echo=False)
        if e is not None:
            paras = split_paragraphs(e.work_text, um + am) or [e.work_text]
            obj = ctx.llm.json("Классификация", {
                "mode": "steady_state", "date": U.ru_date(e.created), "source": e.fm.get("source") or "",
                "content_type": e.fm.get("content_type") or "", "user_marker": um[0], "ai_marker": am[0], "hint": "",
                "containers": containers_for_prompt(ctx, e.work_text), "paragraphs": numbered(paras),
            }, validate=_validator(ctx, len(paras), "steady_state"), subject=f"ревалидация [[{e.title}]]")
            seg = obj["segments"][0]
            choice, conf = seg.get("container"), seg.get("confidence", 0)
            ref = ctx.logs.reflect("deep_revalidation", e.id, choice or (("new:" + seg["new_container"]["name"]) if seg.get("new_container") else None), conf)
            cur = e.container_id
            te = f"«{w.nodes[cur].title}»" if cur in w.nodes else "без контейнера"
            if choice and choice != cur and choice in w.nodes and conf >= ctx.thr("classification", choice) and choice not in e.also_in_ids:
                ctx.q.add("revalidate", "Перепроверка: запись лежит не там?",
                          f"Запись [[{e.title}]] сейчас в {te}. При перепроверке модель относит её к «{w.nodes[choice].title}» "
                          f"(уверенность {conf}).\n\n{seg.get('reasoning') or ''}",
                          options=[{"label": f"Перенести в «{w.nodes[choice].title}»", "value": {"move": e.id, "to": choice}}]
                          + ([{"label": f"Относится и к «{w.nodes[choice].title}» (общая)", "value": {"also": e.id, "to": choice}}] if cur else [])
                          + [{"label": "Оставить как есть", "value": {"ok": True}}],
                          data={"entity": e.id}, dedup=f"deepreval:{e.id}:{choice}", ref=ref)
                proposals += 1
            elif seg.get("new_container") and conf >= ctx.thr("high", cur):
                nc = seg["new_container"]
                ctx.q.add("classify", "Перепроверка: нужен новый контейнер?",
                          f"Запись [[{e.title}]] сейчас в {te}. При перепроверке модель предлагает новый контейнер «{nc['name']}» "
                          f"(уверенность {conf}).\n\n{seg.get('reasoning') or ''}",
                          options=[{"label": f"Создать «{nc['name']}» и перенести", "value": {"create": nc}},
                                   {"label": "Оставить как есть", "value": {"to": cur} if cur else {"unsorted": True}}],
                          data={"entity": e.id}, dedup=f"deepreval-new:{e.id}", ref=ref)
                proposals += 1
        st["queue"].pop(0)
        ctx.checkpoint()
        done = total - len(st["queue"])
        if done % 10 == 0 or not st["queue"]:
            print(f"  проверено {done} из {total}", flush=True)
    st.clear()
    ctx.say(f"Ревалидация закончена: проверено записей — {total}, предложений перенести — {proposals}.")
    return proposals


# ---------- новые составные типы ----------
def find_clusters(ctx, min_size: int = 3, limit: int = 8) -> list[dict]:
    """Технический этап без модели: группы близких аспектов разных типов, не покрытые существующими формулами."""
    w = ctx.w
    types = composite_types(w)
    out = []
    for cid in sorted(w.nodes):
        thr = float(ctx.thr("pattern_similarity", cid))
        pool = w.pool(cid)
        free = {k: a for k, a in pool["aspects"].items() if a.get("status") == "active" and not a.get("duplicate_of")}
        if len(free) < min_size:
            continue
        parent = {k: k for k in free}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        allow = set(free)
        for aid in free:
            v = ctx.vs.get("aspects", aid)
            if v is None:
                continue
            for bid, sim in ctx.vs.search("aspects", v, k=6, allow=allow, exclude=[aid]):
                if sim < thr:
                    break
                parent[find(aid)] = find(bid)
        groups: dict[str, list[str]] = {}
        for aid in free:
            groups.setdefault(find(aid), []).append(aid)
        for g in groups.values():
            tset = {free[a]["type"] for a in g}
            if len(g) < min_size or len(tset) < 3:
                continue
            if any(tset <= set(t["types"]) for t in types.values()):
                continue
            out.append({"container": cid, "aspects": [{"id": a, "type": free[a]["type"], "text": free[a]["text"]}
                                                      for a in sorted(g, key=lambda x: int(x[1:]))][:20]})
    out.sort(key=lambda c: -len(c["aspects"]))
    return out[:limit]


def patterns(ctx) -> int:
    w = ctx.w
    clusters = find_clusters(ctx)
    if not clusters:
        ctx.say("Кандидатов в новые составные типы не нашлось.")
        return 0
    types = composite_types(w)
    formulas = [{"name": n, "title": t["title"], "types": t["types"], "formula": t["formula"]} for n, t in types.items()]
    shown = [{"cluster": i, "container": w.nodes[c["container"]].title, "aspects": c["aspects"]} for i, c in enumerate(clusters, 1)]
    rejected = set(w.state.get("rejected_types", []))

    def check(o):
        ps = o.get("proposals")
        if not isinstance(ps, list):
            return ["нет списка proposals"]
        errs = []
        for i, p in enumerate(ps, 1):
            if not isinstance(p, dict):
                errs.append(f"proposals[{i}] — не объект")
                continue
            if not isinstance(p.get("cluster"), int) or not 1 <= p["cluster"] <= len(clusters):
                errs.append(f"proposals[{i}]: cluster — номер группы 1–{len(clusters)}")
            if not str(p.get("name") or "").replace("_", "").isalnum() or not str(p.get("name")).isascii():
                errs.append(f"proposals[{i}]: name — латиницей в snake_case")
            elif p["name"] in types:
                errs.append(f"proposals[{i}]: тип {p['name']} уже есть")
            ts = p.get("types")
            if not isinstance(ts, list) or len(ts) < 2 or any(t not in SIMPLE_TYPES for t in ts):
                errs.append(f"proposals[{i}]: types — минимум два простых типа")
            for k in ("title", "formula", "example"):
                if not str(p.get(k) or "").strip():
                    errs.append(f"proposals[{i}]: нужно поле {k}")
        return errs
    obj = ctx.llm.json("Новый составной тип", {"formulas": formulas, "clusters": shown}, validate=check, subject="поиск паттернов")
    n = 0
    for p in obj["proposals"][:2]:
        if p["name"] in rejected:
            continue
        c = clusters[p["cluster"] - 1]
        ref = ctx.logs.reflect("composite_type", p["name"], {"types": p["types"]})
        ctx.q.add("composite_type", "Новый составной тип аспектов?",
                  f"Модель заметила устойчивую связку в [[{w.nodes[c['container']].title}]] и предлагает новый составной тип "
                  f"«{p['title']}»: {p['formula']}.\n\nКак это будет выглядеть: {p['example']}\n\n{p.get('reasoning') or ''}",
                  options=[{"label": "Да, добавить тип в постоянный список", "value": "yes"}, {"label": "Нет", "value": "no"}],
                  data={"proposal": {k: p[k] for k in ("name", "title", "types", "formula")}, "container": c["container"]},
                  dedup=f"ctype:{p['name']}", ref=ref)
        n += 1
    ctx.say(f"Предложено новых составных типов: {n}." if n else "Модель не увидела устойчивых паттернов.")
    return n

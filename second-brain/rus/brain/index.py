"""Векторный индекс трёх уровней: сущности, аспекты, контейнеры (раздел 12.2)."""
from __future__ import annotations

from . import util as U


def container_text(ctx, cid: str) -> str:
    w = ctx.w
    node = w.nodes[cid]
    parts = [node.title, node.description]
    summary = summary_of(ctx, cid, 1500)
    if summary:
        parts.append(summary)
    return "\n".join(p for p in parts if p)


def summary_of(ctx, cid: str, limit: int = 1500) -> str:
    """Сводный файл, а если его нет — краткая сводка из пула (раздел 6.4)."""
    w = ctx.w
    for p, fm, body in w.products_of(cid):
        if fm.get("product_kind") == "summary":
            return body.strip()[:limit]
    pool = w.pool(cid)
    items = [a for a in pool["aspects"].values() if a.get("status") != "outdated" and not a.get("duplicate_of")]
    items.sort(key=lambda a: (-(a.get("value") or 0), a.get("date") or ""))
    text = "; ".join(a["text"] for a in items[:12])
    return text[:limit]


def index_container(ctx, cid: str):
    v = ctx.emb.embed([container_text(ctx, cid)])
    ctx.vs.upsert("containers", [cid], v)


def index_entity(ctx, e):
    v = ctx.emb.embed([e.work_text])
    ctx.vs.upsert("entities", [e.id], v)
    return v[0]


def index_aspects(ctx, records: list[dict]):
    if not records:
        return
    v = ctx.emb.embed([r["text"] for r in records])
    ctx.vs.upsert("aspects", [r["id"] for r in records], v)


def ensure_model(ctx) -> None:
    """Сверка модели эмбеддингов с той, которой посчитаны векторы; при смене — пересчёт всего."""
    fp = ctx.emb.fingerprint
    stored = ctx.vs.meta.get("model")
    if stored == fp:
        return
    has_data = any(ctx.vs.has("entities", e) for e in list(ctx.w.entities)[:1]) or bool(stored)
    if not has_data:
        ctx.vs.meta["model"] = fp
        return
    n_e = len(ctx.w.entities)
    n_a = sum(len(ctx.w.pool(c)["aspects"]) for c in ctx.w.nodes)
    print(f"  Модель эмбеддингов сменилась ({stored} → {fp}). Пересчитываю векторы: {n_e} записей, {n_a} аспектов, "
          f"{len(ctx.w.nodes)} контейнеров. Это может занять время.")
    ctx.vs.clear()
    ctx.vs.meta["model"] = fp
    ents = list(ctx.w.entities.values())
    for i in range(0, len(ents), 32):
        chunk = ents[i:i + 32]
        ctx.vs.upsert("entities", [e.id for e in chunk], ctx.emb.embed([e.work_text for e in chunk]))
    for cid in ctx.w.nodes:
        recs = list(ctx.w.pool(cid)["aspects"].values())
        for i in range(0, len(recs), 64):
            index_aspects(ctx, recs[i:i + 64])
        index_container(ctx, cid)
    ctx.vs.save()
    ctx.logs.change("программа", f"векторы пересчитаны под модель {fp}")

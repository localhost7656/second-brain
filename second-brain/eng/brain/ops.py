"""Operations on Entities and Containers, conveyor-line, responses and operations on demand."""
from __future__ import annotations

from . import util as U
from .index import index_container
from .vault import TYPE_RU


def stage(ctx, eid: str) -> str | None:
    return ctx.w.state["entity_stage"].get(eid)


def set_stage(ctx, eid: str, st: str):
    ctx.w.state["entity_stage"][eid] = st


def create_container(ctx, spec: dict, actor: str, conf=None) -> "Node":
    w = ctx.w
    parent = w.resolve_container(spec.get("parent")) if spec.get("parent") else None
    node = w.create_node(spec.get("name") or spec.get("title") or "New container", spec.get("type") or "project",
                         parent.id if parent else None, spec.get("description") or "")
    extra = f" (confidence {conf})" if conf is not None else ""
    where = f" inside [[{parent.title}]]" if parent else ""
    ctx.logs.change(actor, f"container [[{node.title}]] — {TYPE_RU.get(node.type, node.type)}{where}{extra}")
    index_container(ctx, node.id)
    ctx.count("containers_created")
    return node


def dissolve_composite(pool: dict, comp_id: str, reason: str):
    c = pool["composites"].get(comp_id)
    if not c or c.get("status") == "outdated":
        return
    c["status"] = "outdated"
    c["note"] = reason
    for aid in c["from"]:
        a = pool["aspects"].get(aid)
        if a and a.get("status") == "in_composite":
            a["status"] = "active"


def remove_entity_aspects(ctx, e, cid: str) -> list[tuple[dict, object]]:
    """Remove aspects of the entity from the container pool. Returns. [(record, vector)]."""
    w = ctx.w
    pool = w.pool(cid)
    removed = []
    for aid in list(pool["aspects"]):
        a = pool["aspects"][aid]
        if a.get("source_entity") == e.id:
            removed.append((pool["aspects"].pop(aid), ctx.vs.get("aspects", aid)))
    ids = {r["id"] for r, _ in removed}
    if not ids:
        return []
    for c in list(pool["composites"].values()):
        if set(c["from"]) & ids:
            c["from"] = [x for x in c["from"] if x not in ids]
            dissolve_composite(pool, c["id"], "Some of the items left with the post-recording")
    for a in pool["aspects"].values():
        if a.get("duplicate_of") in ids:
            a["duplicate_of"] = None
    pool["conflicts"] = [k for k in pool["conflicts"] if k["a"] not in ids and k["b"] not in ids]
    ctx.vs.remove("aspects", ids)
    e.fm["aspect_ids"] = [x for x in (e.fm.get("aspect_ids") or []) if x not in ids]
    new = ctx.w.state["new_aspects"].get(cid) or []
    ctx.w.state["new_aspects"][cid] = [x for x in new if x not in ids]
    w.save_pool(cid)
    w.mark_dirty(cid, "moved")
    return removed


def add_aspects(ctx, e, cid: str, records: list[dict], vectors=None) -> list[str]:
    """Add aspects (type, text) container-pool; reinstate id."""
    import numpy as np
    w = ctx.w
    pool = w.pool(cid)
    ids, recs = [], []
    for r in records:
        aid = w.next_id("a")
        rec = {"id": aid, "type": r["type"], "text": r["text"], "source_entity": e.id, "date": e.created,
               "status": "active", "value": None, "duplicate_of": None}
        pool["aspects"][aid] = rec
        ids.append(aid)
        recs.append(rec)
    if ids:
        if vectors is not None and all(v is not None for v in vectors):
            ctx.vs.upsert("aspects", ids, np.stack(vectors))
        else:
            v = ctx.emb.embed([r["text"] for r in recs])
            ctx.vs.upsert("aspects", ids, v)
        e.fm["aspect_ids"] = list(e.fm.get("aspect_ids") or []) + ids
        w.state["new_aspects"].setdefault(cid, []).extend(ids)
        w.save_pool(cid)
        w.mark_dirty(cid, "new_aspects")
    return ids


def entity_aspect_payload(ctx, e) -> list[dict]:
    """Aspects of substance (type, text) — pool-wise, where they are."""
    for cid in [e.container_id] + e.also_in_ids:
        if cid and cid in ctx.w.nodes:
            pool = ctx.w.pool(cid)
            recs = [a for a in pool["aspects"].values() if a.get("source_entity") == e.id]
            if recs:
                return [{"type": a["type"], "text": a["text"]} for a in recs]
    return []


def move_entity(ctx, e, new_cid: str | None, actor: str, why: str = ""):
    """Change the main container of the entity (including «containerless»)."""
    w = ctx.w
    old = e.container_id
    if old == new_cid:
        return
    st = stage(ctx, e.id)
    payload = entity_aspect_payload(ctx, e) if st == "done" else []
    vecs = None
    if old and old in w.nodes:
        removed = remove_entity_aspects(ctx, e, old)
        if removed:
            payload = [{"type": r["type"], "text": r["text"]} for r, _ in removed]
            vecs = [v for _, v in removed]
    e.fm["container_id"] = new_cid
    if new_cid in e.also_in_ids:
        e.fm["also_in_ids"] = [x for x in e.also_in_ids if x != new_cid]
    e.fm["quarantine"] = False
    w.save_entity(e)
    if new_cid and st == "done":
        if payload:
            add_aspects(ctx, e, new_cid, payload, vecs)
        else:
            set_stage(ctx, e.id, "embedded")  # from unsorted: We need to get some perspectives.
            e.fm["status"] = "draft"
    w.save_entity(e)
    old_t = f"[[{w.nodes[old].title}]]" if old in w.nodes else "containerless"
    new_t = f"[[{w.nodes[new_cid].title}]]" if new_cid in w.nodes else "containerless"
    ctx.logs.change(actor, f"[[{e.title}]]: {old_t} → {new_t}" + (f" ({why})" if why else ""))


def add_also_in(ctx, e, cid: str, actor: str, conf=None):
    w = ctx.w
    if cid == e.container_id or cid in e.also_in_ids or cid not in w.nodes:
        return
    e.fm["also_in_ids"] = e.also_in_ids + [cid]
    w.save_entity(e)
    if stage(ctx, e.id) == "done":
        payload = entity_aspect_payload(ctx, e)
        if payload:
            add_aspects(ctx, e, cid, payload)
    w.save_entity(e)
    extra = f" (confidence {conf})" if conf is not None else ""
    ctx.logs.change(actor, f"[[{e.title}]] also applies [[{w.nodes[cid].title}]] — moved to _shared{extra}")


def remove_also_in(ctx, e, cid: str, actor: str):
    if cid not in e.also_in_ids:
        return
    remove_entity_aspects(ctx, e, cid)
    e.fm["also_in_ids"] = [x for x in e.also_in_ids if x != cid]
    ctx.w.save_entity(e)
    ctx.logs.change(actor, f"[[{e.title}]] no longer applies [[{ctx.w.nodes[cid].title}]]" if cid in ctx.w.nodes else "")


def create_subcontainer(ctx, parent_cid: str, spec: dict, entity_ids: list[str], actor: str, conf=None):
    w = ctx.w
    spec = dict(spec)
    spec["parent"] = parent_cid
    node = create_container(ctx, spec, actor, conf)
    for eid in entity_ids:
        e = w.entities.get(eid)
        if e and e.container_id == parent_cid:
            move_entity(ctx, e, node.id, actor, "sub--container")
    w.mark_dirty(node.id, "new_aspects")
    return node

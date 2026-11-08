"""On-demand operations (section 10): deep-validation, search for new composite types (section 5.3)."""
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
    """Re-checking the classification of already processed records: model doesnt stand up to herself, only."""
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
        ctx.progress("Revalidation", total - len(st["queue"]) + 1, total, e.title if e is not None else "", echo=False)
        if e is not None:
            paras = split_paragraphs(e.work_text, um + am) or [e.work_text]
            obj = ctx.llm.json("Classification", {
                "mode": "steady_state", "date": U.ru_date(e.created), "source": e.fm.get("source") or "",
                "content_type": e.fm.get("content_type") or "", "user_marker": um[0], "ai_marker": am[0], "user_markers": ", ".join(repr(x) for x in um), "ai_markers": ", ".join(repr(x) for x in am), "hint": "",
                "containers": containers_for_prompt(ctx, e.work_text), "paragraphs": numbered(paras),
            }, validate=_validator(ctx, len(paras), "steady_state"), subject=f"validation [[{e.title}]]")
            seg = obj["segments"][0]
            choice, conf = seg.get("container"), seg.get("confidence", 0)
            ref = ctx.logs.reflect("deep_revalidation", e.id, choice or (("new:" + seg["new_container"]["name"]) if seg.get("new_container") else None), conf)
            cur = e.container_id
            te = f"«{w.nodes[cur].title}»" if cur in w.nodes else "containerless"
            if choice and choice != cur and choice in w.nodes and conf >= ctx.thr("classification", choice) and choice not in e.also_in_ids:
                ctx.q.add("revalidate", "Revalidation: is this entry in the wrong container?",
                          f"Entry [[{e.title}]] is currently in {te}. On revalidation, the model assigned it to «{w.nodes[choice].title}» "
                          f"(confidence {conf}).\n\n{seg.get('reasoning') or ''}",
                          options=[{"label": f"Move to “{w.nodes[choice].title}”", "value": {"move": e.id, "to": choice}}]
                          + ([{"label": f"It also belongs to “{w.nodes[choice].title}” (shared)", "value": {"also": e.id, "to": choice}}] if cur else [])
                          + [{"label": "Leave it as it is.", "value": {"ok": True}}],
                          data={"entity": e.id}, dedup=f"deepreval:{e.id}:{choice}", ref=ref)
                proposals += 1
            elif seg.get("new_container") and conf >= ctx.thr("high", cur):
                nc = seg["new_container"]
                ctx.q.add("classify", "Revalidation: create a new container?",
                          f"Entry [[{e.title}]] is currently in {te}. On revalidation, the model suggested a new container «{nc['name']}» "
                          f"(confidence {conf}).\n\n{seg.get('reasoning') or ''}",
                          options=[{"label": f"Create “{nc['name']}” and move the entry", "value": {"create": nc}},
                                   {"label": "Leave it as it is.", "value": {"to": cur} if cur else {"unsorted": True}}],
                          data={"entity": e.id}, dedup=f"deepreval-new:{e.id}", ref=ref)
                proposals += 1
        st["queue"].pop(0)
        ctx.checkpoint()
        done = total - len(st["queue"])
        if done % 10 == 0 or not st["queue"]:
            print(f"  checked {done} of {total}", flush=True)
    st.clear()
    ctx.say(f"Revalidation complete: checked {total} entries; {proposals} suggestions.")
    return proposals


# ---------- newcomer ----------
def find_clusters(ctx, min_size: int = 3, limit: int = 8) -> list[dict]:
    """Technical stage without a model: Groups of close aspects of different types, formulaeless."""
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
        ctx.say("No candidates for new composite types were found.")
        return 0
    types = composite_types(w)
    formulas = [{"name": n, "title": t["title"], "types": t["types"], "formula": t["formula"]} for n, t in types.items()]
    shown = [{"cluster": i, "container": w.nodes[c["container"]].title, "aspects": c["aspects"]} for i, c in enumerate(clusters, 1)]
    rejected = set(w.state.get("rejected_types", []))

    def check(o):
        ps = o.get("proposals")
        if not isinstance(ps, list):
            return ["proposals must be a list"]
        errs = []
        for i, p in enumerate(ps, 1):
            if not isinstance(p, dict):
                errs.append(f"proposals[{i}] must be an object")
                continue
            if not isinstance(p.get("cluster"), int) or not 1 <= p["cluster"] <= len(clusters):
                errs.append(f"proposals[{i}]: cluster — number 1–{len(clusters)}")
            if not str(p.get("name") or "").replace("_", "").isalnum() or not str(p.get("name")).isascii():
                errs.append(f"proposals[{i}]: name — Latin snake_case")
            elif p["name"] in types:
                errs.append(f"proposals[{i}]: type {p['name']} already exists")
            ts = p.get("types")
            if not isinstance(ts, list) or len(ts) < 2 or any(t not in SIMPLE_TYPES for t in ts):
                errs.append(f"proposals[{i}]: types — at least two simple types")
            for k in ("title", "formula", "example"):
                if not str(p.get(k) or "").strip():
                    errs.append(f"proposals[{i}]: field {k} is required")
        return errs
    obj = ctx.llm.json("New composite type", {"formulas": formulas, "clusters": shown}, validate=check, subject="pattern-finding")
    n = 0
    for p in obj["proposals"][:2]:
        if p["name"] in rejected:
            continue
        c = clusters[p["cluster"] - 1]
        ref = ctx.logs.reflect("composite_type", p["name"], {"types": p["types"]})
        ctx.q.add("composite_type", "Create a new composite aspect type?",
                  f"The model found a recurring pattern in [[{w.nodes[c['container']].title}]] and suggests a new composite type. "
                  f"«{p['title']}»: {p['formula']}.\n\nExample: {p['example']}\n\n{p.get('reasoning') or ''}",
                  options=[{"label": "Yes, add this type", "value": "yes"}, {"label": "No.", "value": "no"}],
                  data={"proposal": {k: p[k] for k in ("name", "title", "types", "formula")}, "container": c["container"]},
                  dedup=f"ctype:{p['name']}", ref=ref)
        n += 1
    ctx.say(f"New composite types proposed: {n}." if n else "The model did not see stable patterns.")
    return n

"""Снимок состояния для плагина Obsidian: .system/ui.json. Пишется после каждой команды (и командой snapshot);
плагин только читает его, а действия выполняет командами программы."""
from __future__ import annotations


from . import __version__
from . import util as U
from .schema import ALIASES, CONTAINER_THRESHOLDS, SEED_DORMANCY, THRESHOLDS
from .usage import summary as usage_summary
from .vault import TYPE_RU

STATUS_RU = {"active": "активен", "dormant": "заморожен", "completed": "завершён"}
QUEUE_STAGES = {"classified", "asked", "compacted", "embedded"}


def _rel(w, p) -> str:
    try:
        return p.relative_to(w.p.root).as_posix()
    except ValueError:
        return p.as_posix()


def container_thresholds(ctx, cid: str) -> dict:
    out = {}
    w = ctx.w
    for name in CONTAINER_THRESHOLDS:
        src = ctx.thr_source(name, cid)
        if src is None:
            out[name] = {"value": ctx.thr(name), "source": "global", "from": None}
        elif src[0] == cid:
            out[name] = {"value": src[1], "source": "own", "from": None}
        else:
            out[name] = {"value": src[1], "source": "parent", "from": w.nodes[src[0]].title}
    return out


def build(ctx) -> dict:
    from .phase2 import container_style
    w = ctx.w
    st = w.state
    q_open = list(ctx.q.open.values())
    ent_q: dict[str, int] = {}
    for q in q_open:
        d = q.get("data") or {}
        cid = d.get("container")
        e = w.entities.get(d.get("entity")) if d.get("entity") else None
        if e is not None:
            cid = cid or e.container_id
        if cid:
            ent_q[cid] = ent_q.get(cid, 0) + 1
    containers = []
    for n in sorted(w.nodes.values(), key=lambda x: w.path_key(x).lower()):
        own = [e for e in w.entities.values() if e.container_id == n.id and not e.also_in_ids]
        shared = [e for e in w.entities.values() if e.also_in_ids and (e.container_id == n.id or n.id in e.also_in_ids)]
        base = w.base(n.id)
        binfo = None
        if base:
            items = [it for g in base.get("groups", []) for it in g["items"]]
            binfo = {"items": len(items), "primary": sum(1 for it in items if it.get("rank") == "primary"),
                     "excluded": len(base.get("excluded") or []), "built": base.get("built"),
                     "conflicts": sum(1 for it in items if it.get("conflict"))}
        cs, cs_from = container_style(w, n.id)
        views = {k: _rel(w, n.folder / f"{name}.md") for k, name in (("pool", "_аспекты"), ("base", "_база синтеза"))
                 if (n.folder / f"{name}.md").exists()}
        d = st["dirty"].get(n.id)
        containers.append({
            "id": n.id, "title": n.title, "path": _rel(w, n.path), "folder": _rel(w, n.folder),
            "type": n.type, "type_ru": TYPE_RU.get(n.type, n.type), "status": n.status, "status_ru": STATUS_RU.get(n.status, n.status),
            "color": n.fm.get("color"), "parent_id": n.fm.get("parent_id") if n.fm.get("parent_id") in w.nodes else None,
            "depth": w.depth(n), "description": n.description, "last_modified": str(n.fm.get("last_modified") or ""),
            "entities": len(own), "shared": len(shared),
            "revalidate_count": sum(1 for e in w.entities.values() if e.container_id == n.id and st["entity_stage"].get(e.id) == "done"),
            "products": [{"title": p.stem, "path": _rel(w, p), "needs_review": bool(fm.get("needs_review"))}
                         for p, fm, b in sorted(w.products_of(n.id), key=lambda x: (x[0].stem != "Сводный файл", x[0].stem))],
            "base": binfo, "dirty": d is not None, "dirty_reasons": (d or {}).get("reasons") or [],
            "overrides": ctx.overrides(n.id), "thresholds": container_thresholds(ctx, n.id),
            "style": n.fm.get("style") if isinstance(n.fm.get("style"), str) else "",
            "style_effective": cs, "style_from": cs_from if cs_from != n.title else None,
            "questions": ent_q.get(n.id, 0), "views": views,
        })
    stages = {"done": 0, "quarantine": 0, "queue": 0}
    for eid, s in st["entity_stage"].items():
        if eid not in w.entities:
            continue
        if s == "done":
            stages["done"] += 1
        elif s in ("quarantine", "quarantine_wait"):
            stages["quarantine"] += 1
        elif s in QUEUE_STAGES:
            stages["queue"] += 1
    files = {}
    for it in st["items"].values():
        s = it.get("stage")
        if s in ("await_structure", "await_mode", "ready", "new"):
            files[s] = files.get(s, 0) + 1
    staging_new = [p for p in w.p.staging.rglob("*") if p.is_file() and p.suffix.lower() in (".txt", ".md")
                   and not p.name.startswith((".", "~"))] if w.p.staging.exists() else []
    pend = (U.read_json(w.p.webchat_index, None) or {}).get("pending") or {}

    def order(q):
        try:
            return int(q["id"][1:])
        except ValueError:
            return 0
    questions = []
    for q in sorted(q_open, key=order):
        d = q.get("data") or {}
        e = w.entities.get(d.get("entity")) if d.get("entity") else None
        cid = d.get("container") if d.get("container") in w.nodes else (e.container_id if e is not None else None)
        questions.append({"id": q["id"], "kind": q["kind"], "title": q["title"], "text": q["text"], "created": q.get("created"),
                          "options": [{"index": i, "label": o["label"]} for i, o in enumerate(q.get("options") or [])],
                          "free_text": bool(q.get("free_text")), "free_hint": q.get("free_hint") or "", "note": q.get("note"),
                          "container": cid, "entity": e.id if e is not None else None,
                          "entity_path": _rel(w, e.path) if e is not None else None})
    logs = {}
    mk = U.month_key()
    for k, name in (("changes", f"изменения {mk}.md"), ("reasoning", f"рассуждения {mk}.md"),
                    ("archive", "архив вопросов.md"), ("errors", "ошибки.log")):
        if (w.p.logs / name).exists():
            logs[k] = _rel(w, w.p.logs / name)
    pending_work = bool(staging_new or files.get("ready") or stages["queue"] or st["dirty"])
    return {
        "version": 1, "program": __version__, "generated": U.now_iso(), "vault": str(w.p.root),
        "status": {
            "containers": len(w.nodes), "entities": len(w.entities), "products": len(w.products),
            "stages": stages, "files": files, "questions": len(q_open),
            "dirty": [{"id": c, "title": w.nodes[c].title} for c in st["dirty"] if c in w.nodes],
            "structure_pending": bool(st["structure"].get("pending")), "approved_once": bool(st["structure"].get("approved_once")),
            "draft": _rel(w, w.p.draft) if w.p.draft.exists() else None,
            "webchat_pending": [{"req": _rel(w, w.p.webchat / r["req"]), "ans": _rel(w, w.p.webchat / r["ans"]), "prompt": r.get("prompt")}
                                for r in pend.values() if r.get("req") and r.get("ans")],
            "staging_new": len(staging_new), "pending_work": pending_work,
            "first_run": not w.nodes and not st["structure"].get("approved_once"),
        },
        "containers": containers,
        "questions": questions,
        "thresholds": {k: ctx.th.get(k) for k in THRESHOLDS} | {"seed_dormancy_days": ctx.thr("seed_dormancy_days")},
        "threshold_info": {k: {f: v[f] for f in ("kind", "min", "max", "step", "label", "help", "per_container")}
                           for k, v in list(THRESHOLDS.items()) + [("seed_dormancy_days", SEED_DORMANCY)]},
        "threshold_aliases": dict(ALIASES),
        "types": dict(TYPE_RU), "statuses": dict(STATUS_RU),
        "sources": [{"name": s.get("name"), "color": s.get("color")} for s in ctx.cfg.get("sources") or []],
        "usage": usage_summary(ctx.cfg, w.p.usage),
        "updates": {"repo": str((ctx.cfg.get("updates") or {}).get("repo") or "").strip(),
                    "check_on_start": bool((ctx.cfg.get("updates") or {}).get("check_on_start", True))},
        "logs": logs,
        "warnings": list(dict.fromkeys(w.warnings)),
        "notices": list(ctx.notices),
    }


def write(ctx) -> dict:
    data = build(ctx)
    U.write_json(ctx.w.p.system / "ui.json", data)
    return data

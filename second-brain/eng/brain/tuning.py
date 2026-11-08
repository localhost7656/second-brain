"""Thresholds container and model advice on them (team advise, section 10.5). The program considers statistics of decisions
log-reflection — model offers meanings, code, decider."""
from __future__ import annotations

import datetime as dt
import json

from . import util as U
from .schema import CONTAINER_THRESHOLDS, parse_number
from .snapshot import container_thresholds
from .synthesis_base import container_info
from .vault import TYPE_RU


def _summary(vals: list) -> dict | None:
    vals = sorted(v for v in vals if isinstance(v, (int, float)))
    if not vals:
        return None
    n = len(vals)

    def q(p):
        return vals[min(n - 1, int(p * (n - 1) + 0.5))]
    return {"n": n, "min": vals[0], "p25": q(0.25), "median": q(0.5), "p75": q(0.75), "max": vals[-1]}


def _hist(vals: list, step: int = 10) -> dict:
    out: dict[str, int] = {}
    for v in vals:
        if not isinstance(v, (int, float)):
            continue
        a = min(int(v) // step * step, 100 - step)
        k = f"{a}–{a + step - 1}" if a + step < 100 else f"{a}–100"
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: int(kv[0].split("–")[0])))


def _reflection(w):
    A, D = {}, {}
    if not w.p.reflection.exists():
        return A, D
    for line in w.p.reflection.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") == "assumption" and r.get("ref"):
            A[r["ref"]] = r
        elif r.get("type") == "decision" and r.get("ref"):
            D.setdefault(r["ref"], []).append(r)
    return A, D


def _target(dec) -> str | None:
    v = dec.get("decision")
    if isinstance(v, dict):
        return v.get("user_container") or v.get("to")
    return v if isinstance(v, str) else None


def container_stats(ctx, cid: str) -> dict:
    w = ctx.w
    node = w.nodes[cid]
    A, D = _reflection(w)
    ents = {e.id: e for e in w.entities.values() if e.container_id == cid or cid in e.also_in_ids}
    open_refs = {q.get("ref") for q in ctx.q.open.values() if q.get("ref")}

    # --- layout (classification, hint_shift) ---
    c = {k: [] for k in ("auto", "auto_moved_away", "by_hint", "by_hint_moved_away", "asked", "asked_model_right",
                         "asked_model_wrong", "asked_pending", "moved_in_by_user", "hint_mismatch_asked",
                         "hint_mismatch_hint_right", "hint_mismatch_model_right")}
    created_here = []
    for ref, a in A.items():
        if a.get("kind") != "classification":
            continue
        choice, applied, by, conf = a.get("assumption"), a.get("applied"), a.get("by"), a.get("confidence")
        placed = a.get("placed")
        if placed is None and applied == "place" and by != "hint" and isinstance(choice, str) and not choice.startswith("new:"):
            placed = choice
        decs = [d for d in D.get(ref, []) if d.get("kind") in ("classify", "classification")]
        last = decs[-1] if decs else None
        tgt = _target(last) if last else None
        hint_node = w.resolve_container(a.get("hint_container")) if a.get("hint_container") else None
        if a.get("created"):
            n2 = w.nodes.get(a["created"])
            if n2 is not None and n2.fm.get("parent_id") == cid:
                created_here.append(conf)
        if applied == "place" and placed == cid:
            key = "by_hint" if by == "hint" else "auto"
            c[key].append(conf if by != "hint" else (a.get("hint_confidence") or conf))
            if last and last.get("matched") is False and tgt != cid:
                c[key + "_moved_away"].append(conf)
        elif applied == "quarantine" and (choice == cid or (hint_node is not None and hint_node.id == cid)):
            if a.get("reason") == "user_hint_mismatch" or (a.get("hint_container") and choice != a.get("hint_container")):
                c["hint_mismatch_asked"].append(conf)
                if last:
                    if hint_node is not None and tgt == hint_node.id:
                        c["hint_mismatch_hint_right"].append(a.get("hint_confidence"))
                    elif tgt == choice:
                        c["hint_mismatch_model_right"].append(conf)
            else:
                c["asked"].append(conf)
                if not last:
                    c["asked_pending"].append(conf)
                elif tgt == cid:
                    c["asked_model_right"].append(conf)
                else:
                    c["asked_model_wrong"].append(conf)
        if last and tgt == cid and placed != cid and choice != cid:
            c["moved_in_by_user"].append(conf)

    # --- record (high for «applies here») ---
    also = {"auto": [], "accepted": [], "rejected": [], "pending": []}
    for eid, cl in w.state.get("cls", {}).items():
        e = w.entities.get(eid)
        if e is None:
            continue
        for x in cl.get("also_in") or []:
            if x.get("container") != cid or e.container_id == cid:
                continue
            conf = x.get("confidence")
            pending = any(q["kind"] == "also_in" and q["data"].get("entity") == eid and q["data"].get("container") == cid
                          for q in ctx.q.open.values())
            if pending:
                also["pending"].append(conf)
            elif cid in e.also_in_ids:
                also["auto" if isinstance(conf, (int, float)) and conf >= ctx.thr("high", cid) else "accepted"].append(conf)
            else:
                also["rejected"].append(conf)

    # --- structure: bottom-containers «sprout → project» (high) ---
    struct = {"auto": [], "confirmed": [], "rejected": [], "pending": []}
    for ref, a in A.items():
        if a.get("kind") not in ("subcontainer", "seed_to_project") or a.get("subject") != cid:
            continue
        conf = a.get("confidence")
        decs = D.get(ref, [])
        if decs:
            struct["confirmed" if decs[-1].get("matched") else "rejected"].append(conf)
        elif ref in open_refs:
            struct["pending"].append(conf)
        else:
            struct["auto"].append(conf)
    struct["auto"] += created_here

    # --- sealing ---
    noise, compacted, by_source = [], 0, {}
    for ref, a in A.items():
        if a.get("kind") == "compaction" and a.get("subject") in ents:
            noise.append(a.get("confidence"))
            compacted += 1 if a.get("assumption") else 0
            s = a.get("source") or "?"
            by_source[s] = by_source.get(s, 0) + 1

    # --- value ---
    pool = w.pool(cid)
    recs = [r for r in list(pool["aspects"].values()) + list(pool["composites"].values())
            if r.get("status") not in ("outdated", "in_composite") and not r.get("duplicate_of")]
    values = [r.get("value") for r in recs if isinstance(r.get("value"), (int, float))]
    vmin, vprim = ctx.thr("value_min", cid), ctx.thr("value_primary", cid)
    restore, keep = 0, 0
    for ref, a in A.items():
        if a.get("kind") == "base_loss" and str(a.get("subject", "")).startswith(cid + ":"):
            for d in D.get(ref, []):
                if d.get("decision") == "restore":
                    restore += 1
                elif d.get("decision") == "keep":
                    keep += 1
    value = {"rated": len(values), "histogram": _hist(values), "summary": _summary(values),
             "below_min": sum(1 for v in values if v < vmin), "primary": sum(1 for v in values if v >= vprim),
             "near_min": sum(1 for v in values if abs(v - vmin) <= 5), "near_primary": sum(1 for v in values if abs(v - vprim) <= 5),
             "pinned_by_user": sum(1 for r in recs if r.get("pinned")),
             "losses_user_restored": restore, "losses_user_accepted": keep}

    # --- doubles ---
    dup_links = sum(1 for a in pool["aspects"].values() if a.get("duplicate_of"))
    dup_rejected = sum(1 for r in pool.get("rejected") or [] if r.get("kind") == "duplicate")

    # --- neighbourhood ---
    nb = {"asked": [], "all_correct": [], "moved": [], "pending": []}
    for ref, a in A.items():
        if a.get("kind") != "revalidation_hint" or a.get("subject") not in ents:
            continue
        sim = (a.get("assumption") or {}).get("similarity")
        decs = D.get(ref, [])
        nb["asked"].append(sim)
        if decs:
            nb["all_correct" if decs[-1].get("matched") is False else "moved"].append(sim)
        elif ref in open_refs:
            nb["pending"].append(sim)

    # --- sprout ---
    seed = None
    if node.type == "seed":
        lm = str(node.fm.get("last_modified") or node.fm.get("created") or "")
        try:
            idle = (dt.date.today() - dt.date.fromisoformat(lm[:10])).days
        except ValueError:
            idle = None
        seed = {"last_new_thought": lm[:10], "days_idle": idle, "dormancy_days": ctx.thr("seed_dormancy_days", cid)}

    dates = sorted(e.created for e in ents.values() if e.created)
    srcs: dict[str, int] = {}
    for e in ents.values():
        s = e.fm.get("source") or "?"
        srcs[s] = srcs.get(s, 0) + 1

    def sm(d):
        return {k: (_summary(v) if isinstance(v, list) else v) for k, v in d.items()}
    return {
        "records": {"total": len(ents), "own": sum(1 for e in ents.values() if not e.also_in_ids),
                    "shared": sum(1 for e in ents.values() if e.also_in_ids), "sources": srcs,
                    "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
                    "subcontainers": len(w.children(cid))},
        "classification": sm(c), "also_in": sm(also), "structure": sm(struct),
        "compaction": {"rated": len(noise), "compacted": compacted, "noise": _summary(noise), "histogram": _hist(noise),
                       "by_source": by_source},
        "value": value, "duplicates": {"aspects": len(pool["aspects"]), "linked_as_duplicates": dup_links, "user_unlinked": dup_rejected},
        "neighbors": sm(nb), "seed": seed,
        "composites": sum(1 for x in pool["composites"].values() if x.get("status") != "outdated"),
    }


def _n(s) -> int:
    return s["n"] if isinstance(s, dict) else 0


def _rng(s) -> str:
    if not isinstance(s, dict):
        return ""
    return f" (confidence {s['min']}–{s['max']}, median {s['median']})" if s["n"] > 1 else f" (confidence {s['min']})"


def brief(stats: dict, th: dict) -> list[str]:
    """Human description of statistics — for the user and for the model."""
    r, c, v = stats["records"], stats["classification"], stats["value"]
    out = [f"Entries: {r['total']} (own {r['own']}, shared {r['shared']})"
           + (f", from {U.ru_date(r['first'])} to {U.ru_date(r['last'])}" if r["first"] else "") + "."]
    if _n(c["auto"]):
        out.append(f"Placed by the model without asking: {_n(c['auto'])}{_rng(c['auto'])}; you later moved elsewhere: {_n(c['auto_moved_away'])}.")
    if _n(c["by_hint"]):
        out.append(f"Placed based on your hint: {_n(c['by_hint'])}; later moved: {_n(c['by_hint_moved_away'])}.")
    if _n(c["asked"]):
        out.append(f"Asked during placement (confidence below threshold {th['classification']['value']}): {_n(c['asked'])}{_rng(c['asked'])}; "
                   f"model was correct — {_n(c['asked_model_right'])}, incorrect — {_n(c['asked_model_wrong'])}, awaiting an answer — {_n(c['asked_pending'])}.")
    if _n(c["hint_mismatch_asked"]):
        out.append(f"The hint differed from the model’s suggestion: {_n(c['hint_mismatch_asked'])}; hint was correct — "
                   f"{_n(c['hint_mismatch_hint_right'])}, model — {_n(c['hint_mismatch_model_right'])}.")
    if _n(c["moved_in_by_user"]):
        out.append(f"You moved entries here that the model placed elsewhere: {_n(c['moved_in_by_user'])}.")
    a, s = stats["also_in"], stats["structure"]
    if any(_n(a[k]) for k in a):
        out.append(f"Suggestions to also place an entry here: automatic — {_n(a['auto'])}, accepted — {_n(a['accepted'])}, "
                   f"rejected — {_n(a['rejected'])}, awaiting an answer — {_n(a['pending'])}.")
    if any(_n(s[k]) for k in s):
        out.append(f"Restructuring (subcontainers, sprout → project): automatic — {_n(s['auto'])}, accepted — {_n(s['confirmed'])}, "
                   f"rejected — {_n(s['rejected'])}, awaiting an answer — {_n(s['pending'])}.")
    cm = stats["compaction"]
    if cm["rated"]:
        ns = cm["noise"]
        out.append(f"Compaction: rated {cm['rated']}, compacted {cm['compacted']} (threshold {th['compaction']['value']}; "
                   f"noise {ns['min']}–{ns['max']}, median {ns['median']}).")
    if v["rated"]:
        out.append(f"Value: rated {v['rated']}; below threshold {th['value_min']['value']} — {v['below_min']}; primary "
                   f"(from {th['value_primary']['value']}) — {v['primary']}; missing content restored — {v['losses_user_restored']}, "
                   f"loss accepted — {v['losses_user_accepted']}.")
    d = stats["duplicates"]
    if d["linked_as_duplicates"] or d["user_unlinked"]:
        out.append(f"Duplicates: linked {d['linked_as_duplicates']}, incorrect links removed — {d['user_unlinked']}.")
    nb = stats["neighbors"]
    if _n(nb["asked"]):
        out.append(f"Questions about similar entries in different places: {_n(nb['asked'])}; all correct — {_n(nb['all_correct'])}, "
                   f"moved — {_n(nb['moved'])}.")
    if stats.get("seed"):
        sd = stats["seed"]
        out.append(f"Sprout: last new thought {U.ru_date(sd['last_new_thought'])}"
                   + (f" ({sd['days_idle']} days ago)" if sd["days_idle"] is not None else "") + f"; a question is asked after {sd['dormancy_days']} days.")
    return out


def validate_advice(obj: dict, current: dict, seed: bool) -> list[str]:
    errs = []
    if not str(obj.get("summary") or "").strip():
        errs.append("summary is required — a plain-language conclusion")
    recs = obj.get("recommendations")
    if not isinstance(recs, list):
        return errs + ["recommendations must be a list (which may be empty)"]
    seen = set()
    for i, r in enumerate(recs, 1):
        if not isinstance(r, dict):
            errs.append(f"recommendations[{i}] — must be an object")
            continue
        name = r.get("name")
        spec = CONTAINER_THRESHOLDS.get(name)
        if spec is None:
            errs.append(f"recommendations[{i}]: unknown threshold “{name}” (allowed: {', '.join(CONTAINER_THRESHOLDS)})")
            continue
        if name == "seed_dormancy_days" and not seed:
            errs.append(f"recommendations[{i}]: seed_dormancy_days applies only to sprouts")
        if name in seen:
            errs.append(f"recommendations[{i}]: threshold {name} is repeated")
        seen.add(name)
        if parse_number(r.get("value"), spec) is None or isinstance(r.get("value"), str):
            errs.append(f"recommendations[{i}] ({name}): value — {'whole ' if spec['kind'] == 'int' else ''}number "
                        f"from {spec['min']} to {spec['max']}")
        if not str(r.get("reasoning") or "").strip():
            errs.append(f"recommendations[{i}] ({name}): reasoning is required — explain which numbers support it")
    return errs


def advise(ctx, cid: str) -> dict:
    w = ctx.w
    node = w.nodes[cid]
    stats = container_stats(ctx, cid)
    th = container_thresholds(ctx, cid)
    seed = node.type == "seed"
    names = [k for k in CONTAINER_THRESHOLDS if seed or k != "seed_dormancy_days"]
    table = [{"name": k, "label": CONTAINER_THRESHOLDS[k]["label"], "what": CONTAINER_THRESHOLDS[k]["help"],
              "current": th[k]["value"], "set_by": {"own": "container", "parent": f"parental «{th[k]['from']}»",
                                                    "global": "general"}[th[k]["source"]],
              "global": ctx.thr(k), "range": [CONTAINER_THRESHOLDS[k]["min"], CONTAINER_THRESHOLDS[k]["max"]]} for k in names]
    lines = brief(stats, th)
    info = container_info(w, cid)
    info["subcontainers"] = [n.title for n in w.children(cid)]
    obj = ctx.llm.json("Thresholds", {"container": info, "thresholds": table, "brief": "\n".join(f"- {x}" for x in lines),
                                  "stats": stats},
                       validate=lambda o: validate_advice(o, th, seed), subject=f"threshold [[{node.title}]]")
    recs = []
    for r in obj.get("recommendations") or []:
        spec = CONTAINER_THRESHOLDS[r["name"]]
        val = parse_number(r["value"], spec)
        if val == th[r["name"]]["value"]:
            continue  # council «leave it» — change
        recs.append({"name": r["name"], "label": spec["label"], "current": th[r["name"]]["value"], "source": th[r["name"]]["source"],
                     "from": th[r["name"]]["from"], "value": val, "reasoning": str(r["reasoning"]).strip(),
                     "help": spec["help"], "kind": spec["kind"], "min": spec["min"], "max": spec["max"], "step": spec["step"]})
    ref = ctx.logs.reflect("thresholds_advice", cid, {r["name"]: r["value"] for r in recs}, None,
                           current={k: th[k]["value"] for k in names})
    w.state.setdefault("advice", {})[cid] = {"ref": ref, "values": {r["name"]: r["value"] for r in recs}, "at": U.now_iso()}
    ctx.logs.change("model", f"threshold-board [[{node.title}]]: "
                    + (", ".join(f"{r['name']} {r['current']} → {r['value']}" for r in recs) if recs else "nothing"))
    return {"container": {"id": cid, "title": node.title, "type": node.type, "type_ru": TYPE_RU.get(node.type, node.type)},
            "summary": str(obj.get("summary") or "").strip(), "recommendations": recs, "brief": lines, "ref": ref}


def note_user_changes(ctx):
    """Your own thresholds and container style, user-modified (into YAML plug-in), — log-change;
    If there was a model before — pair «council — decision» log-reflection (section 15.3)."""
    w = ctx.w
    seen = w.state.setdefault("thr_seen", {})
    advice = w.state.setdefault("advice", {})
    for cid, n in w.nodes.items():
        ov = ctx.overrides(cid)
        style = n.fm.get("style") if isinstance(n.fm.get("style"), str) else ""
        cur = {"thresholds": ov, "style": style.strip()}
        old = seen.get(cid)
        seen[cid] = cur
        if old is None:
            old = {"thresholds": {}, "style": ""}
        if old == cur:
            continue
        parts = []
        for k in sorted(set(old["thresholds"]) | set(ov)):
            a, b = old["thresholds"].get(k), ov.get(k)
            if a != b:
                parts.append(f"{k}: {a if a is not None else 'general'} → {b if b is not None else 'general'}")
        if old["style"] != cur["style"]:
            parts.append("style of documents changed" if cur["style"] else "your style of paperwork removed")
        if parts:
            ctx.logs.change("user", f"[[{n.title}]]: " + "; ".join(parts))
        adv = advice.get(cid)
        if adv and old["thresholds"] != ov:
            rec = adv.get("values") or {}
            applied = sorted(k for k, v in rec.items() if ov.get(k) == v)
            matched = bool(rec) and len(applied) == len(rec) or ("partial" if applied else False)
            ctx.logs.decision(adv.get("ref"), "thresholds_advice", cid, ov, matched=matched, accepted=applied,
                              rejected=sorted(set(rec) - set(applied)))
            advice.pop(cid, None)

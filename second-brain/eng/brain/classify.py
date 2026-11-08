"""Phase 1, stepping-step 1–3: regime, segmentation, thresholdization (section 6.2, 6.4, 6.5)."""
from __future__ import annotations

from . import ops
from . import util as U
from .schema import input_limit
from .index import summary_of
from .ingest import load_item_paragraphs, numbered, ranges_to_str, segment_text
from .vault import TYPE_RU

NODE_TYPES = ("project", "seed", "question")


def containers_for_prompt(ctx, text: str) -> list[dict]:
    w = ctx.w
    nodes = list(w.nodes.values())
    limit = int(ctx.cfg["limits"]["max_containers_in_prompt"])
    if len(nodes) > limit:  # vector-search (section 6.4)
        v = ctx.emb.embed([text])[0]
        top = [cid for cid, _ in ctx.vs.search("containers", v, k=limit)]
        keep = set(top)
        for cid in top:  # parents — contextually
            cur = w.nodes.get(cid)
            while cur is not None and cur.fm.get("parent_id"):
                keep.add(cur.fm["parent_id"])
                cur = w.nodes.get(cur.fm["parent_id"])
        nodes = [n for n in nodes if n.id in keep]
    out = []
    for n in sorted(nodes, key=lambda x: (w.depth(x), x.title.lower())):
        out.append({"id": n.id, "title": n.title, "type": n.type, "parent": n.fm.get("parent_id"),
                    "description": n.description, "summary": summary_of(ctx, n.id, 1200)})
    return out


def _validator(ctx, n_par: int, mode: str):
    nodes = ctx.w.nodes

    def conf_ok(v):
        return isinstance(v, (int, float)) and 0 <= v <= 100

    def validate(o):
        errs = []
        segs = o.get("segments")
        if not isinstance(segs, list) or not segs:
            return ["segments must be a nonempty list"]
        if mode == "unknown":
            g = o.get("mode_guess")
            if not isinstance(g, dict) or g.get("mode") not in ("bootstrap", "steady_state") or not conf_ok(g.get("confidence")):
                errs.append("mode is unknown: provide mode_guess {mode: bootstrap|steady_state, confidence: 0–100}")
        eff_mode = mode if mode != "unknown" else (o.get("mode_guess") or {}).get("mode")
        if eff_mode == "steady_state" and len(segs) != 1:
            errs.append("in steady_state mode, return one segment containing all paragraphs")
        seen = []
        for i, s in enumerate(segs, 1):
            if not isinstance(s, dict):
                errs.append(f"segment {i} must be an object")
                continue
            rs = s.get("paragraphs")
            if not isinstance(rs, list) or not rs:
                errs.append(f"segment {i}: no paragraphs")
            else:
                for r in rs:
                    if not (isinstance(r, list) and len(r) == 2 and all(isinstance(x, int) for x in r) and 1 <= r[0] <= r[1] <= n_par):
                        errs.append(f"segment {i}: range {r} outside 1–{n_par}")
                    else:
                        seen += list(range(r[0], r[1] + 1))
            c, nc = s.get("container"), s.get("new_container")
            if c is not None and nc is not None:
                errs.append(f"segment {i}: specify either container or new_container, not both")
            if c is not None and c not in nodes:
                errs.append(f"segment {i}: container {c} is not in the list")
            if nc is not None:
                if not isinstance(nc, dict) or not str(nc.get("name") or "").strip():
                    errs.append(f"segment {i}: new_container requires a name")
                elif nc.get("type") not in NODE_TYPES:
                    errs.append(f"segment {i}: new_container.type — project, seed or question")
                elif nc.get("parent") not in (None, "") and nc.get("parent") not in nodes:
                    errs.append(f"segment {i}: parent {nc.get('parent')} is not in the list")
            if not conf_ok(s.get("confidence")):
                errs.append(f"segment {i}: confidence — number 0–100")
            if s.get("hint_confidence") is not None and not conf_ok(s.get("hint_confidence")):
                errs.append(f"segment {i}: hint_confidence — number 0–100 or null")
            for k in ("also_in", "alternatives"):
                for a in s.get(k) or []:
                    if not isinstance(a, dict) or a.get("container") not in nodes or not conf_ok(a.get("confidence")):
                        errs.append(f"segment {i}: {k} must contain existing containers with confidence scores")
            if not isinstance(s.get("noise", 0), (int, float)):
                errs.append(f"segment {i}: noise — number 0–100")
        if sorted(seen) != list(range(1, n_par + 1)):
            dup = sorted({x for x in seen if seen.count(x) > 1})
            miss = sorted(set(range(1, n_par + 1)) - set(seen))
            if dup:
                errs.append(f"paragraphs {dup} appear in multiple segments")
            if miss:
                errs.append(f"paragraphs {miss} are not included in any segment.")
        return errs
    return validate


def _windows(paras: list[str], limit: int) -> list[tuple[int, int]]:
    """Portions of paragraphs under the model window: [(beginning, ending)) — deterministically, so that the run can continue."""
    out, start, size = [], 0, 0
    for i, p in enumerate(paras):
        if i > start and size + len(p) + 8 > limit:
            out.append((start, i))
            start, size = i, 0
        size += len(p) + 8
    out.append((start, len(paras)))
    return out


def _create_segments(ctx, item, paras, pend, created, windows):
    a = pend["window"][0]
    segs = pend["segments"]
    multi = len(segs) > 1 or len(windows) > 1
    for k in range(int(pend.get("next") or 0), len(segs)):
        seg = segs[k]
        ranges = [[x + a, y + a] for x, y in seg["paragraphs"]]
        text = segment_text(paras, ranges)
        whole = (len(paras) == sum(y - x + 1 for x, y in ranges))
        e = _create_entity(ctx, item, dict(seg, paragraphs=ranges), text, ranges if (multi or not whole) else None, pend["mode"])
        created.append(e.id)
        item["entities"] = list(created)
        pend["next"] = k + 1
        ctx.checkpoint()  # record created and accounted for — The failure will not create it a second time.


def classify_item(ctx, item: dict):
    w = ctx.w
    paras = load_item_paragraphs(ctx, item)
    if not paras:
        item["stage"] = "done"
        ctx.say(f"File “{item['name']}” is empty; skipped.")
        return
    um, am = ctx.cfg.markers()
    mode = item.get("mode") or "unknown"
    lim = input_limit(ctx.cfg, "Classification")
    limit = max(lim - 60000, min(20000, lim // 2))  # task reserve and container list
    windows = _windows(paras, limit)
    done_upto = int(item.get("cls_progress") or 0)
    created = list(item.get("entities") or []) if (done_upto or item.get("cls_pending")) else []
    for wi, (a, b) in enumerate(windows):
        if b <= done_upto:
            continue
        sub = paras[a:b]
        part = f", part {wi + 1} from {len(windows)}" if len(windows) > 1 else ""
        pend = item.get("cls_pending")
        if pend and pend.get("window") == [a, b]:  # post-failure: The models answer is already there.
            _create_segments(ctx, item, paras, pend, created, windows)
            item["cls_progress"] = b
            item.pop("cls_pending", None)
            continue
        obj = ctx.llm.json("Classification", {
            "mode": mode, "date": U.ru_date(item["date"]), "source": item["source"],
            "content_type": item.get("content_type") or "", "user_marker": um[0], "ai_marker": am[0], "user_markers": ", ".join(repr(x) for x in um), "ai_markers": ", ".join(repr(x) for x in am),
            "hint": item.get("hint") or "",
            "containers": containers_for_prompt(ctx, "\n\n".join(sub)) or "There is no container yet.",
            "paragraphs": numbered(sub),
        }, validate=_validator(ctx, len(sub), mode), subject=f"file «{item['name']}»{part}")

        if mode == "unknown":
            g = obj["mode_guess"]
            ref = ctx.logs.reflect("mode_guess", item["id"], g["mode"], g["confidence"])
            if g["confidence"] < ctx.thr("mode_guess"):
                item["stage"] = "await_mode"
                item["mode_ref"] = ref
                ctx.q.add("mode", "How to process a file",
                          f"File “{item['name']}” ({U.ru_date(item['date'])}). The model suggests: "
                          f"{'bulk import — multiple topics; split into entries' if g['mode'] == 'bootstrap' else 'one regular entry'} "
                          f"(confidence {g['confidence']}).\n\n{obj.get('reasoning', '')}",
                          options=[{"label": "Treat as a bulk import: split by topic", "value": "bootstrap"},
                                   {"label": "Treat as one entry", "value": "steady_state"}],
                          data={"item": item["id"], "guess": g["mode"]}, dedup=f"mode:{item['id']}", ref=ref)
                return
            item["mode"] = g["mode"]
            mode = g["mode"]

        pend = {"window": [a, b], "segments": obj["segments"], "next": 0, "mode": mode}
        item["cls_pending"] = pend
        _create_segments(ctx, item, paras, pend, created, windows)
        item["cls_progress"] = b
        item.pop("cls_pending", None)
        ctx.checkpoint()
    item["entities"] = created
    item.pop("cls_progress", None)
    item["stage"] = "done"
    ctx.count("items_classified")


def _hint_target(ctx, seg):
    hc = seg.get("hint_container")
    if hc in (None, "") or seg.get("hint_confidence") is None:
        return None
    node = ctx.w.resolve_container(hc)
    return ("id", node.id) if node else ("new", str(hc))


def decide(ctx, seg) -> dict:
    """Application of thresholds (section 6.5). Model evaluates — code.
    Thresholds — thrifter, where the record is placed (their own container or common); new-container — his-parent."""
    c = seg["confidence"]
    w = ctx.w

    def T(cid=None):
        return ctx.thr("classification", cid)

    def S(cid=None):
        return ctx.thr("hint_shift", cid)

    def H(name=None):
        nc = seg.get("new_container") or {}
        par = w.resolve_container(U.unlink(nc.get("parent"))) if nc and str(nc.get("name", "")).lower() == str(name).lower() else None
        return ctx.thr("high", par.id if par else None)
    if seg.get("container"):
        choice = ("id", seg["container"])
    elif seg.get("new_container"):
        choice = ("new", seg["new_container"]["name"])
    else:
        choice = ("none", None)
    hint = _hint_target(ctx, seg)

    def new_spec(name):
        nc = seg.get("new_container") or {}
        if nc and str(nc.get("name", "")).lower() == str(name).lower():
            return nc
        return {"name": name, "type": "project", "parent": None, "description": ""}

    if hint:
        hcid = hint[1] if hint[0] == "id" else None
        h = seg["hint_confidence"] + S(hcid)
        same = (hint[0] == choice[0] and str(hint[1]).lower() == str(choice[1]).lower())
        if same:
            eff = max(c, h)
            if hint[0] == "id":
                return {"action": "place", "cid": hint[1], "eff": eff, "by": "hint+model"} if eff >= T(hcid) else \
                    {"action": "quarantine", "reason": "low_confidence"}
            return {"action": "create", "spec": new_spec(hint[1]), "eff": eff, "by": "hint+model"} if eff >= H(hint[1]) else \
                {"action": "quarantine", "reason": "new_container"}
        if hint[0] == "id" and h >= T(hcid):
            return {"action": "place", "cid": hint[1], "eff": h, "by": "hint"}
        if hint[0] == "new" and h >= H(hint[1]):
            return {"action": "create", "spec": new_spec(hint[1]), "eff": h, "by": "hint"}
        return {"action": "quarantine", "reason": "user_hint_mismatch"}
    if choice[0] == "id":
        return {"action": "place", "cid": choice[1], "eff": c, "by": "model"} if c >= T(choice[1]) else \
            {"action": "quarantine", "reason": "low_confidence"}
    if choice[0] == "new":
        return {"action": "create", "spec": new_spec(choice[1]), "eff": c, "by": "model"} if c >= H(choice[1]) else \
            {"action": "quarantine", "reason": "new_container"}
    return {"action": "unsorted", "eff": c, "by": "model"} if c >= T() else {"action": "quarantine", "reason": "low_confidence"}


def _create_entity(ctx, item, seg, text, ranges, mode):
    w = ctx.w
    d = decide(ctx, seg)
    ctype = item.get("content_type") or seg.get("content_type") or "thought"
    fm = {
        "type": "entity", "content_type": ctype, "source": item["source"],
        "container": None, "container_id": None, "shared": False, "also_in": [], "also_in_ids": [],
        "created": item["date"], "source_file": item["file"], "segment": ranges_to_str(ranges) if ranges else None,
        **({"source_part": f"{item['part']['n']} from {item['part']['of']} · {item['part']['label']}"} if item.get("part") else {}),
        "hint": item.get("hint"), "status": "draft", "conflicts_with": [],
        "needs_review": False, "review_reason": None, "quarantine": False,
        "incomplete": bool(seg.get("incomplete")), "compacted": False, "aspect_ids": [],
    }
    if d["action"] == "create":
        node = ops.create_container(ctx, d["spec"], "model", d["eff"])
        d = {"action": "place", "cid": node.id, "eff": d["eff"], "by": d["by"], "created": node.id}
    if d["action"] == "place":
        fm["container_id"] = d["cid"]
    elif d["action"] == "quarantine":
        fm.update({"quarantine": True, "needs_review": True, "review_reason": d["reason"]})
    e = w.create_entity(fm, text, f"{item['date']} {U.short_title(text)}")
    w.state["text_hash"][e.id] = U.sha1(e.text)
    choice = seg.get("container") or (("new:" + seg["new_container"]["name"]) if seg.get("new_container") else None)
    ref = ctx.logs.reflect("classification", e.id, choice, seg["confidence"],
                           hint=item.get("hint"), hint_container=seg.get("hint_container"),
                           hint_confidence=seg.get("hint_confidence"), applied=d["action"], by=d.get("by"),
                           placed=d.get("cid"), created=d.get("created"), reason=d.get("reason"),
                           threshold=ctx.thr("classification", d.get("cid") or (seg.get("container") if seg.get("container") in w.nodes else None)))
    w.state["cls"][e.id] = {"choice": choice, "confidence": seg["confidence"], "reasoning": seg.get("reasoning", ""),
                            "alternatives": seg.get("alternatives") or [], "also_in": seg.get("also_in") or [],
                            "new_container": seg.get("new_container"), "hint_container": seg.get("hint_container"),
                            "hint_confidence": seg.get("hint_confidence"), "noise": seg.get("noise", 0),
                            "incomplete": bool(seg.get("incomplete")), "mode": mode, "ref": ref, "item": item["id"]}
    if d["action"] == "place":
        ops.set_stage(ctx, e.id, "classified")
        ctx.logs.change("model", f"[[{e.title}]] → [[{w.nodes[d['cid']].title}]] (confidence {d['eff']}"
                        + (", promptly" if d["by"] == "hint" else "") + ")")
        propose_also_in(ctx, e)
        ctx.count("placed")
    elif d["action"] == "unsorted":
        ops.set_stage(ctx, e.id, "classified")
        ctx.logs.change("model", f"[[{e.title}]] → containerless (confidence {d['eff']})")
        ctx.count("unsorted")
    else:
        ops.set_stage(ctx, e.id, "quarantine")
        ask_classification(ctx, e, d["reason"])
        ctx.logs.change("model", f"[[{e.title}]] → check-up ({d['reason']})")
        ctx.count("quarantined")
    w.save_entity(e)
    return e


def propose_also_in(ctx, e):
    """Additional containers: high-threshold — themselves, below — proposal (section 6.5)."""
    w = ctx.w
    cls = w.state["cls"].get(e.id) or {}
    for a in cls.get("also_in") or []:
        cid, conf = a.get("container"), a.get("confidence", 0)
        if cid not in w.nodes or cid == e.container_id:
            continue
        if conf >= ctx.thr("high", cid):
            ops.add_also_in(ctx, e, cid, "model", conf)
        else:
            ctx.q.add("also_in", "Should this entry also appear in another container?",
                      f"Entry [[{e.title}]] is in [[{w.nodes[e.container_id].title}]]. The model thinks it also applies to "
                      f"[[{w.nodes[cid].title}]] (confidence {conf}). If yes, the entry will move to `_shared` and be visible from both containers.",
                      options=[{"label": f"Yes, it also belongs to “{w.nodes[cid].title}”", "value": "yes"},
                               {"label": "No", "value": "no"}],
                      data={"entity": e.id, "container": cid}, dedup=f"also:{e.id}:{cid}", ref=cls.get("ref"))


REASON_TEXT = {
    "low_confidence": "The model is unsure which container this entry belongs in.",
    "user_hint_mismatch": "The hint differs from the content of the record.",
    "new_container": "The model suggests a new container, but is not confident enough to create it automatically.",
}


def ask_classification(ctx, e, reason: str):
    w = ctx.w
    cls = w.state["cls"].get(e.id) or {}
    opts, seen = [], set()

    def add(label, value, key):
        if key in seen:
            return
        seen.add(key)
        opts.append({"label": label, "value": value})

    ch = cls.get("choice")
    if ch and not str(ch).startswith("new:") and ch in w.nodes:
        add(f"«{w.nodes[ch].title}» — model (confidence {cls.get('confidence')})", {"to": ch}, ch)
    hc = cls.get("hint_container")
    if hc:
        hn = w.resolve_container(hc)
        if hn:
            add(f"«{hn.title}» — based on your hint", {"to": hn.id}, hn.id)
        else:
            add(f"Create «{hc}» — based on your hint", {"create": {"name": hc, "type": "project", "parent": None}}, "new:" + str(hc).lower())
    nc = cls.get("new_container")
    if nc:
        par = w.nodes.get(nc.get("parent"))
        where = f" inside «{par.title}»" if par else ""
        add(f"Create «{nc['name']}» ({TYPE_RU.get(nc.get('type'), 'project')}{where}) — model (confidence {cls.get('confidence')})",
            {"create": nc}, "new:" + str(nc["name"]).lower())
    for a in cls.get("alternatives") or []:
        if a.get("container") in w.nodes:
            add(f"«{w.nodes[a['container']].title}» (confidence {a.get('confidence')})", {"to": a["container"]}, a["container"])
    add("No container (unsorted)", {"unsorted": True}, "none")
    hint = f"\n\nYour hint: «{e.fm.get('hint')}»." if e.fm.get("hint") else ""
    ctx.q.add("classify", "Where should this entry go?",
              f"Entry: [[{e.title}]] ({U.ru_date(e.created)}). {REASON_TEXT.get(reason, '')}{hint}\n\n"
              f"Model reasoning: {cls.get('reasoning', '')}",
              options=opts, free_text=True,
              free_hint="Or enter a container name. If it does not exist, a new top-level project will be created. "
                        "For another type, add it in parentheses: “Name (sprout)” or “Name (question)”. You can change the parent later in its file.",
              data={"entity": e.id}, dedup=f"classify:{e.id}", ref=cls.get("ref"))

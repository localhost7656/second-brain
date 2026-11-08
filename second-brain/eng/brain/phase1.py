"""Phase 1 whole (section 6): answers → manual → file → Bootstrap/classification → conveyor → synthesis."""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import re
import shutil
import time

from . import answers, ops, pipeline, synthesis_base, tuning
from . import util as U
from .classify import classify_item
from .index import ensure_model, index_container
from .ingest import INPUT_EXT, decode, file_date, is_dialogue, parse_header, scan_staging, source_and_mode, split_by_dates
from .structure import apply_draft, generate_draft
from .vault import CONTAINER_STATUS, ENTITY_STATUS, RU_TYPE, TYPE_RU


def run(ctx):
    t0 = time.time()
    w = ctx.w
    ensure_model(ctx)
    detect_manual_edits(ctx)
    tuning.note_user_changes(ctx)
    answers.process(ctx)
    apply_draft(ctx)
    product_edits(ctx)
    ingest(ctx)
    pass1(ctx)
    classify_ready(ctx)
    pipeline.run_all(ctx)
    synthesis_base.run_all(ctx)
    check_dormancy(ctx)
    ctx.elapsed = time.time() - t0
    return ctx


# ---------- manual editing of organizational fields (section 3.6) ----------
def detect_manual_edits(ctx):
    w = ctx.w
    st = w.state
    # container, hand-operated: note type, without id
    for md, fm, body in list(getattr(w, "adoptable", [])):
        node = w.adopt_node(md, fm, body)
        if node:
            par = w.parent_of(node)
            ctx.logs.change("user", f"created container [[{node.title}]] — {TYPE_RU.get(node.type, node.type)}"
                            + (f" inside [[{par.title}]]" if par else ""))
            index_container(ctx, node.id)
            ctx.count("containers_created")
    w.adoptable = []
    # nodes: type, parent, linkage
    for n in list(w.nodes.values()):
        t = RU_TYPE.get(str(n.fm.get("type", "")).strip().lower())
        if t is None:
            w.warnings.append(f"Container [[{n.title}]] has an unrecognized type “{n.fm.get('type')}” — expected project, sprout, or question; "
                              "treating it as a project for now.")
            t = "project"
        raw_cs = n.fm.get("container_status")
        cs = CONTAINER_STATUS.get(str(raw_cs or "active").strip().lower())
        if cs is None:
            w.warnings.append(f"Container [[{n.title}]] has an unrecognized container_status “{raw_cs}” — expected active, dormant, or completed; "
                              "keeping active.")
            cs = "active"
        if t != n.fm.get("type") or cs != raw_cs:
            n.fm["type"], n.fm["container_status"] = t, cs
            w.save_node(n)
        raw_parent = n.fm.get("parent")
        ref = U.unlink(raw_parent)
        pid = n.fm.get("parent_id")
        if ref:
            p = w.node_by_title(ref)
            if p is None:
                if not (pid in w.nodes and w.nodes[pid].title.lower() == ref.lower()):
                    w.warnings.append(f"Container [[{n.title}]] specifies parent “{ref}”, but that container does not exist — keeping the previous parent.")
            elif p.id != pid:
                old = w.nodes[pid].title if pid in w.nodes else "top-level"
                w.move_node(n, p.id)
                ctx.logs.change("user", f"[[{n.title}]] moved: {old} → [[{p.title}]]")
        elif pid and not raw_parent:
            w.move_node(n, None)
            ctx.logs.change("user", f"[[{n.title}]] moved up")
        refs = [U.unlink(v) for v in U.as_list(n.fm.get("applies_to"))]
        ids, bad = [], []
        for r in refs:
            m = w.node_by_title(r) if r else None
            if m and m.id != n.id:
                ids.append(m.id)
            elif r:
                bad.append(r)
        if bad:
            w.warnings.append(f"In [[{n.title}]], these applies_to references were not found: {', '.join(bad)}.")
        elif set(ids) != set(n.fm.get("applies_to_ids") or []):
            w.set_applies_to(n, ids)
            w.save_node(n)
            ctx.logs.change("user", f"[[{n.title}]]: applies_to links changed")
    w.normalize_folders()
    # record: container, also_in, text, status, conflicts_with
    for e in list(w.entities.values()):
        if e.container_id and e.container_id not in w.nodes:
            w.warnings.append(f"The container for [[{e.title}]] was deleted — the entry was moved to _unsorted.")
            e.fm["container_id"] = None
            w.save_entity(e)
        raw = e.fm.get("container")
        ref = U.unlink(raw)
        cur = e.container_id
        target = cur
        if ref:
            n = w.node_by_title(ref)
            if n is None:
                if not (cur in w.nodes and w.nodes[cur].title.lower() == ref.lower()):
                    w.warnings.append(f"Entry [[{e.title}]] specifies container “{ref}”, which does not exist — keeping the previous container.")
            elif n.id != cur:
                target = n.id
        elif cur and not raw:
            target = None
        if target != cur:
            cls = st["cls"].get(e.id, {})
            answers.place_entity(ctx, e, target, "user", "classification challenged by editing YAML")
            ctx.logs.decision(cls.get("ref"), "classification", e.id, {"user_container": target}, matched=False)
            ctx.count("user_moves")
        want, bad = [], []
        for v in U.as_list(e.fm.get("also_in")):
            r = U.unlink(v)
            m = w.node_by_title(r) if r else None
            if m and m.id != e.container_id:
                want.append(m.id)
            elif r and not m:
                bad.append(r)
        if bad:
            w.warnings.append(f"In [[{e.title}]], these also_in references were not found: {', '.join(bad)}.")
        else:
            for cid in want:
                if cid not in e.also_in_ids:
                    ops.add_also_in(ctx, e, cid, "user")
            for cid in list(e.also_in_ids):
                if cid not in want:
                    ops.remove_also_in(ctx, e, cid, "user")
        h = U.sha1(e.text)
        old = st["text_hash"].get(e.id)
        if old and h != old:
            if ops.stage(ctx, e.id) == "done":
                ctx.q.add("text_changed", "Text of a processed entry was changed",
                          f"The text of [[{e.title}]] was edited manually. Processed entries cannot be edited directly: "
                          "otherwise links and extracted aspects may no longer match the text. Until you answer, the program uses the previous text.",
                          options=[{"label": "Create a new entry from the edit in _staging and restore the original text", "value": "new"},
                                   {"label": "Restore the original text only", "value": "restore"}],
                          data={"entity": e.id}, dedup=f"text:{e.id}")
            else:
                st["text_hash"][e.id] = h
                ctx.logs.change("user", f"text [[{e.title}]] corrected before the processing is completed")
        raw_st = e.fm.get("status")
        if raw_st not in ("processed", "outdated", "draft", None):
            norm = ENTITY_STATUS.get(str(raw_st).strip().lower())
            if norm:
                e.fm["status"] = norm
                w.save_entity(e)
            else:
                w.warnings.append(f"Entry [[{e.title}]] has an unrecognized status “{raw_st}” — expected outdated or processed.")
        uo = st.setdefault("user_outdated", {})
        if e.fm.get("status") == "outdated" and not uo.get(e.id) and not st.get("auto_outdated", {}).get(e.id):
            for cid in [e.container_id] + e.also_in_ids:
                if cid in w.nodes:
                    for a in list(w.pool(cid)["aspects"].values()):
                        if a["source_entity"] == e.id and a.get("status") != "outdated":
                            answers.outdate_aspect(ctx, cid, a["id"], None, "entity")
            uo[e.id] = True
            ctx.logs.change("user", f"[[{e.title}]] marked as outdated")
        elif e.fm.get("status") == "processed" and uo.get(e.id):
            for cid in [e.container_id] + e.also_in_ids:
                if cid in w.nodes:
                    pool = w.pool(cid)
                    for a in pool["aspects"].values():
                        if a["source_entity"] == e.id and a.get("outdated_by") == "entity":
                            a["status"] = a.pop("status_before", None) or "active"
                            if a["status"] == "in_composite":
                                a["status"] = "active"
                            a["outdated_by"] = None
                            a["replaced_by"] = None
                    w.save_pool(cid)
                    w.mark_dirty(cid, "user_status")
            del uo[e.id]
            ctx.logs.change("user", f"[[{e.title}]] relevant again")
        cw = sorted(t for t in (U.unlink(v) for v in U.as_list(e.fm.get("conflicts_with"))) if t)
        seen = st.setdefault("cw_seen", {})
        if cw != seen.get(e.id, []):
            if e.id in seen or cw:
                for cid in [e.container_id] + e.also_in_ids:
                    if cid:
                        synthesis_base.mark_stage(w, cid, "assemble", "conflicts_with")
            seen[e.id] = cw
    w.refresh_links()
    ctx.checkpoint()


# ---------- manual (section 8.5) ----------
def _norm(s: str) -> str:
    return "\n".join(l.rstrip() for l in (s or "").strip().split("\n"))


def product_edits(ctx):
    w = ctx.w
    n = 0
    for path, fm, body in list(w.products):
        cid = fm.get("container_id")
        if cid not in w.nodes or not path.exists():
            continue
        title = path.stem
        key = ctx.ver.key_product(cid, title)
        mirror = ctx.ver.read(key)
        if mirror is None or _norm(mirror) == _norm(body):
            continue
        old_l, new_l = _norm(mirror).split("\n"), _norm(body).split("\n")
        added, removed = [], []
        for line in difflib.ndiff(old_l, new_l):
            if line.startswith("+ ") and line[2:].strip():
                added.append(line[2:])
            elif line.startswith("- ") and line[2:].strip():
                removed.append(line[2:])
        if not added and not removed:
            ctx.ver.snapshot(key, body)
            continue
        node = w.nodes[cid]
        lines = [U.ru_date(U.today()), f"hint: {node.title}", "content_type: product_edit", "",
                 f"Manual edit of document [[{w.path_key(node)}/{title}|{title}]] in container [[{node.title}]].", ""]
        if added:
            lines += ["Author added or rewrote:", ""] + added + [""]
        if removed:
            lines += ["Author removed:", ""] + removed + [""]
        p = U.unique_path(w.p.staging, U.safe_name(f"editing — {title} ({node.title})", 100), ".txt")
        U.atomic_write_text(p, "\n".join(lines))
        ctx.ver.snapshot(key, body)
        ctx.logs.change("user", f"manual edit of [[{w.path_key(node)}/{title}|{title}]] ({node.title}) accepted as a new entry")
        n += 1
    if n:
        ctx.say(f"Manual document edits found: {n}; saved as entries.")
    return n


# ---------- file (section 4) ----------
def ingest(ctx):
    w = ctx.w
    items = w.state["items"]
    staging = w.p.staging
    by_sha = {(it.get("sha"), it.get("staging")): it for it in items.values() if it.get("sha")}
    other = [p for p in staging.rglob("*") if p.is_file() and p.suffix.lower() not in INPUT_EXT
             and not p.name.startswith((".", "~"))]
    if other:
        ctx.notices.append("Files in _staging the program cannot yet read (use .txt or .md): "
                           + ", ".join(p.name for p in other[:10]) + (" …" if len(other) > 10 else ""))
    um, am = ctx.cfg.markers()
    n = 0
    for p in scan_staging(staging):
        rel = p.relative_to(staging)
        raw = p.read_bytes()
        sha = hashlib.sha1(raw).hexdigest()
        if (sha, rel.as_posix()) in by_sha:  # already accepted, but not removed from-faulty
            p.unlink()
            continue
        text, enc = decode(raw)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        hdr = parse_header(text)
        date = hdr["date"] or file_date(p)
        source, mflag = source_and_mode(rel.parts[:-1])
        mode = "bootstrap" if (mflag == "bootstrap" or not w.nodes) else (hdr.get("mode") or "unknown")
        ctype = hdr["content_type"] or ("ai_dialogue" if is_dialogue(hdr["body"], um, am) else None)
        w.p.sources.mkdir(parents=True, exist_ok=True)
        stem = p.stem if re.match(r"^\d{4}-\d{2}-\d{2}\b", p.stem) else f"{date} {p.stem}"  # double-date
        dest = U.unique_path(w.p.sources, U.safe_name(stem, 100), p.suffix.lower())
        U.retry_fs(shutil.copy2, p, dest)
        parts = split_by_dates(ctx.cfg, hdr) if hdr["body"].strip() and not ctype else None
        for part in parts or [None]:
            iid = w.next_id("i")
            item = {"id": iid, "file": dest.relative_to(w.p.root).as_posix(), "name": p.name, "staging": rel.as_posix(),
                    "sha": sha, "encoding": enc, "source": source, "date": date, "hint": hdr["hint"],
                    "content_type": ctype, "mode": mode, "stage": "new" if mode == "bootstrap" else "ready",
                    "added": U.now_iso(), "entities": []}
            if part:
                item["part"] = {k: part[k] for k in ("n", "of", "lines", "drop", "cut", "label")}
                item["date"] = part.get("date") or date
                item["name"] = f"{p.name} · {part['label']}"
            if not hdr["body"].strip():
                item["stage"] = "done"
                ctx.notices.append(f"File “{p.name}” is empty; the original was saved in _sources and no entry was created.")
            items[iid] = item
        ctx.checkpoint()
        try:
            U.retry_fs(p.unlink)
        except OSError as e:
            w.warnings.append(f"Could not remove “{rel}” from _staging: {e}. Delete the file manually; it will not be processed again.")
        split = (f"; diary split by date: {len(parts)} entries ({parts[0]['label']} — {parts[-1]['label']})"
                 if parts else "")
        ctx.logs.change("programme", f"file received “{rel.as_posix()}” → _sources ({source}, {U.ru_date(date)}, {enc}"
                        + (", mass-load" if mode == "bootstrap" else "") + ")" + split)
        if parts:
            ctx.say(f"«{p.name}»: diary split by date — {len(parts)} entries ({parts[0]['label']} — {parts[-1]['label']}).")
        n += 1
    for d in sorted([d for d in staging.rglob("*") if d.is_dir()], key=lambda x: -len(x.parts)):
        if d != w.p.staging_archive:
            try:
                d.rmdir()  # merely empty
            except OSError:
                pass
    if n:
        ctx.count("files", n)
        ctx.say(f"Files received: {n}.")
    return n


def pass1(ctx):
    w = ctx.w
    new = [it for it in w.state["items"].values() if it.get("stage") == "new"]
    if not new:
        return False
    new.sort(key=lambda i: (i["date"], i["id"]))
    ctx.say(f"Bulk import: {len(new)} files — building a draft structure (first pass).")
    generate_draft(ctx, new)
    ctx.checkpoint()
    ctx.say("The draft structure is ready. Open _structure (draft).md, review it, and mark “Structure approved”.")
    return True


def classify_ready(ctx):
    w = ctx.w
    ready = [it for it in w.state["items"].values() if it.get("stage") == "ready"]
    ready.sort(key=lambda i: (i["date"], i["id"]))
    for i, it in enumerate(ready, 1):
        print(f"  [{i}/{len(ready)}] {it['name']}", flush=True)
        ctx.progress("File analysis", i, len(ready), it["name"], echo=False)
        classify_item(ctx, it)
        ctx.checkpoint()
        if it.get("entities"):
            pipeline.run_all(ctx, only=it["entities"])


# ---------- «quietness» shoot (section 3.3) ----------
def check_dormancy(ctx):
    w = ctx.w
    today = dt.date.today()
    for n in w.nodes.values():
        if n.type != "seed" or n.status != "active":
            continue
        days = int(ctx.thr("seed_dormancy_days", n.id))
        lm = str(n.fm.get("last_modified") or n.fm.get("created") or "")
        try:
            d = dt.date.fromisoformat(lm[:10])
        except ValueError:
            continue
        if (today - d).days >= days:
            ctx.q.add("dormant", "The sprout has not developed in a long time",
                      f"Sprout [[{n.title}]] has not received any new thoughts since {U.ru_date(lm)} (more than {days} days). Is it still relevant?",
                      options=[{"label": "Still relevant — keep as a sprout", "value": "active"},
                               {"label": "Put on hold (dormant)", "value": "dormant"},
                               {"label": "Completed (completed)", "value": "completed"}],
                      data={"container": n.id}, dedup=f"dormant:{n.id}:{lm[:10]}")

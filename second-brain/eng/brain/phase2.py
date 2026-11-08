"""Phase 2 (section 8): synthesis of container documents from the synthesis database, comparison with previous versions."""
from __future__ import annotations

import json
import re

from . import util as U
from .aspects import type_title
from .index import index_container
from .phase1 import _norm, product_edits
from .synthesis_base import container_info
from .util import UserError

FILE_RE = re.compile(r"^\s*===\s*FILE\s*:\s*(.+?)\s*===\s*$", re.M | re.I)
SUMMARY = "Summary"


def base_for_prompt(w, cid) -> str:
    base = w.base(cid) or {}
    lines = []
    for g in base.get("groups", []):
        lines.append(f"## {type_title(w, g['type'])} ({g['type']})")
        for it in g["items"]:
            flags = []
            if it.get("conflict"):
                flags.append("conflicts with: " + "; ".join(f"«{_text_of(base, x)}»" for x in it["conflict"]))
            if it.get("assumed_loser"):
                flags.append("assumed to be superseded (the author has not decided yet)")
            if it.get("fork"):
                flags.append("fork: both directions remain valid")
            if it.get("rejected_alt"):
                flags.append("alternative considered and rejected by the author")
            if it.get("review"):
                flags.append("under review: some components are outdated")
            src = len(it.get("sources") or [])
            head = f"- [{it['rank']}] ({U.ru_date(it.get('date'))}; value {it.get('value')}; source entries: {src})"
            lines.append(f"{head} {it['text']}" + (f" ⟨{'; '.join(flags)}⟩" if flags else ""))
            for p in it.get("parts") or []:
                lines.append(f"    - {p['type']}: {p['text']}")
        lines.append("")
    mc = base.get("manual_conflicts") or []
    if mc:
        lines.append("## Contradictions marked manually by the author (between entries)")
        for x in mc:
            a, b = w.entities.get(x["a"]), w.entities.get(x["b"])
            if a and b:
                lines.append(f"- «{a.work_text[:300]}» ⚔ «{b.work_text[:300]}»")
    return "\n".join(lines).strip()


def _text_of(base, aid):
    for g in base.get("groups", []):
        for it in g["items"]:
            if it["id"] == aid:
                return U.short_title(it["text"], 12)
    return aid


def parse_files(text: str) -> list[tuple[str, str]]:
    marks = list(FILE_RE.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        name = m.group(1).strip().strip("«»\"'")
        if name.lower().endswith(".md"):
            name = name[:-3]
        out.append((name, text[m.end():end].strip()))
    return out


def _validate_synth(t: str):
    files = parse_files(t)
    if not files:
        return ["No document found. Each document must start with a line like “=== FILE: Name ===”."]
    errs = []
    names = [n.lower() for n, _ in files]
    if SUMMARY.lower() not in names:
        errs.append(f"required document “{SUMMARY}” is missing")
    if len(set(names)) != len(names):
        errs.append("Document names are repeated")
    for n, body in files:
        if len(body) < 20:
            errs.append(f"document “{n}” is empty or too short")
    return errs


def container_style(w, cid) -> tuple[str, str | None]:
    """Container style (field style his YAML) — his or her immediate parent: (text, container-name-source)."""
    seen, cur = set(), w.nodes.get(cid)
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        s = cur.fm.get("style")
        if isinstance(s, str) and s.strip():
            return s.strip(), cur.title
        cur = w.parent_of(cur)
    return "", None


def _style(ctx, existing: dict, cid: str | None = None) -> str:
    g = (ctx.cfg.get("style") or {}).get("global") or ""
    parts = [f"General style: {g}"] if g else []
    if cid:
        cs, src = container_style(ctx.w, cid)
        if cs:
            parts.append(f"For this container (takes precedence over the global style): {cs}")
    for t, (p, fm, body) in existing.items():
        if fm.get("style_override"):
            parts.append(f"For the document «{t}»: {fm['style_override']}")
    return "\n".join(parts) or "not specified"


def _validate_losses(o):
    ls = o.get("losses")
    if not isinstance(ls, list):
        return ["losses must be a list"]
    for i, x in enumerate(ls, 1):
        if not isinstance(x, dict) or not str(x.get("what") or "").strip() or not isinstance(x.get("significant"), bool):
            return [f"losses[{i}]: need what (missing) and significant (true/false)"]
    return []


def accepted_after(w, cid) -> list[str]:
    out = []
    for p, fm, body in w.products_of(cid):
        out += [f"{p.stem}: {x}" for x in fm.get("accepted_losses") or []]
    return out


def synth(ctx, cid: str, force: bool = False, ask_force=None, confirm=None):
    w = ctx.w
    node = w.nodes[cid]
    product_edits(ctx)
    if cid in w.state["dirty"]:
        raise UserError(f"The synthesis base for “{node.title}” has not been rebuilt after changes. Run Phase 1 first.")
    base = w.base(cid)
    if not base or not any(g["items"] for g in base.get("groups", [])):
        raise UserError(f"There is no synthesis base for “{node.title}”: the container has no processed thoughts. Run Phase 1 first.")
    existing = {p.stem: (p, fm, body) for p, fm, body in w.products_of(cid)}
    previous = "\n\n".join(f"=== FILE: {t} ===\n{body.strip()}" for t, (p, fm, body) in sorted(existing.items()))
    accepted = []
    for t, (p, fm, body) in existing.items():
        accepted += [f"{t}: {x}" for x in fm.get("accepted_losses") or []]
    restore = w.state["restore_requests"].get(cid) or []
    info = container_info(w, cid)
    completed = ("CONTAINER COMPLETED: the summary document must include a final outcome section, with a heading in the source language, "
                 "separate from the current, living description.") if node.status == "completed" else ""
    base_text, style = base_for_prompt(w, cid), _style(ctx, existing, cid)
    sig = U.sha1(json.dumps([base_text, style, completed, info, restore, sorted(accepted),
                             sorted((t, _norm(b)) for t, (_, _, b) in existing.items())], ensure_ascii=False))
    sigs = w.state.setdefault("synth_sig", {})
    if existing and not force and sigs.get(cid) == sig:
        msg = f"“{node.title}”: nothing has changed since the last synthesis; the documents are up to date."
        if not (ask_force and ask_force(msg)):
            ctx.result.update(unchanged=True, title="Documents are up to date")
            if not ask_force:  # In the window, the message is already shown with the question.
                ctx.say(msg + f" To rewrite anyway, run: synth \"{node.title}\" --force")
            return []
    if confirm is not None and not confirm():  # big-start: user
        ctx.result.update(cancelled=True, title="Cancelled.")
        ctx.say("Run cancelled; documents unchanged.")
        return []
    text = ctx.llm.text("Synthesis", {
        "container": info, "style": style, "base": base_text,
        "previous": previous or "no — Documents are written for the first time",
        "accepted_losses": accepted or "no", "restore": restore or "no", "completed": completed,
    }, validate=_validate_synth, subject=f"[[{node.title}]]")
    files = parse_files(text)
    plan = []
    for name, body in files:
        title = U.safe_name(name, 80)
        if title.lower() == SUMMARY.lower():
            title = SUMMARY
        if title.lower() == node.title.lower() or title.startswith("_"):
            title = f"{title.lstrip('_')} (document)"
        plan.append((title, body))
    reviews: dict[str, list[str]] = {}
    changed = [t for t, b in plan if existing.get(t) and _norm(existing[t][2]) != _norm(b)]
    for title, body in plan:  # comparison — file-writing, so that the run can continue
        old = existing.get(title)
        if not old or _norm(old[2]) == _norm(body):
            continue
        ctx.progress("Version comparison", changed.index(title) + 1, len(changed), title, echo=False)
        acc = old[1].get("accepted_losses") or []
        obj = ctx.llm.json("Version comparison", {
            "object_kind": "product", "container": info, "accepted_losses": acc or "no",
            "material": f"DOCUMENT: {title}\n\nPREVIOUS VERSION:\n{old[2].strip()}\n\nNEW VERSION:\n{body.strip()}",
        }, validate=_validate_losses, subject=f"document «{title}» ({node.title})")
        for x in obj["losses"]:
            ref = ctx.logs.reflect("product_loss", f"{cid}:{title}", {"what": x["what"], "significant": x["significant"]})
            if x["significant"] and x["what"] not in acc:
                reviews.setdefault(title, []).append(x["what"])
                ctx.q.add("product_loss", "Is important information missing from the new document version?",
                          f"Document [[{w.path_key(node)}/{title}|{title}]] ({node.title}): The new version is missing information from the previous version.\n\n"
                          f"**{x['what']}**\n\n{x.get('reasoning') or ''}",
                          options=[{"label": "This is intentional — accept the loss and do not ask again", "value": "intentional"},
                                   {"label": "Return at the next synthesis", "value": "restore"},
                                   {"label": "Roll the document back to the previous version", "value": "rollback"}],
                          data={"container": cid, "product": title, "what": x["what"]},
                          dedup=f"prodloss:{cid}:{title}:{U.sha1(x['what'])[:10]}", ref=ref)
    written = []
    for title, body in plan:
        old = existing.get(title)
        old_fm = old[1] if old else {}
        path = old[0] if old else node.folder / f"{title}.md"
        fm = {"type": "product", "product_kind": "summary" if title == SUMMARY else "supplementary", "title": title,
              "container": U.link(node.title), "container_id": cid, "last_generated": U.today(),
              "style_override": old_fm.get("style_override"), "based_on_synthesis": base.get("built"),
              "accepted_losses": list(old_fm.get("accepted_losses") or []),
              "needs_review": bool(reviews.get(title)),
              "review_reason": "Significant loss compared to the previous version" if reviews.get(title) else None}
        content = "\n" + body.strip() + "\n"
        U.write_md(path, fm, content)
        ctx.ver.snapshot(ctx.ver.key_product(cid, title), content)
        w.products = [x for x in w.products if x[0] != path] + [(path, fm, content)]
        written.append(title)
    kept = [t for t in existing if t not in written]
    w.state["restore_requests"][cid] = []
    existing_after = {p.stem: b for p, fm, b in w.products_of(cid)}
    sigs[cid] = U.sha1(json.dumps([base_text, style, completed, info, [], sorted(accepted_after(w, cid)),
                                   sorted((t, _norm(b)) for t, b in existing_after.items())], ensure_ascii=False))
    index_container(ctx, cid)
    ctx.logs.change("model", f"Phase 2 for [[{node.title}]]: document " + ", ".join(f"«{t}»" for t in written)
                    + (f"; not updated: {', '.join(kept)}" if kept else ""))
    ctx.count("products", len(written))
    ctx.say(f"Documents «{node.title}»: " + ", ".join(written) + ".")
    if kept:
        ctx.say("The model did not rewrite these documents: " + ", ".join(kept) + " — they remain unchanged.")
    if reviews:
        ctx.say(f"Questions about information missing from the new versions: {sum(len(v) for v in reviews.values())} — see open-questions.md.")
    return written

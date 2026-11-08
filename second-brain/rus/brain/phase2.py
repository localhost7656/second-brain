"""Фаза 2 (раздел 8): синтез документов контейнера из базы синтеза, сравнение с прежними версиями."""
from __future__ import annotations

import json
import re

from . import util as U
from .aspects import type_title
from .index import index_container
from .phase1 import _norm, product_edits
from .synthesis_base import container_info
from .util import UserError

FILE_RE = re.compile(r"^\s*===\s*ФАЙЛ\s*:\s*(.+?)\s*===\s*$", re.M | re.I)
SUMMARY = "Сводный файл"


def base_for_prompt(w, cid) -> str:
    base = w.base(cid) or {}
    lines = []
    for g in base.get("groups", []):
        lines.append(f"## {type_title(w, g['type'])} ({g['type']})")
        for it in g["items"]:
            flags = []
            if it.get("conflict"):
                flags.append("спорит с: " + "; ".join(f"«{_text_of(base, x)}»" for x in it["conflict"]))
            if it.get("assumed_loser"):
                flags.append("предположительно уступает (автор ещё не решил)")
            if it.get("fork"):
                flags.append("развилка: оба направления живы")
            if it.get("rejected_alt"):
                flags.append("рассмотренная и отклонённая автором альтернатива")
            if it.get("review"):
                flags.append("на пересмотре: часть состава устарела")
            src = len(it.get("sources") or [])
            head = f"- [{it['rank']}] ({U.ru_date(it.get('date'))}; ценность {it.get('value')}; записей-источников: {src})"
            lines.append(f"{head} {it['text']}" + (f" ⟨{'; '.join(flags)}⟩" if flags else ""))
            for p in it.get("parts") or []:
                lines.append(f"    - {p['type']}: {p['text']}")
        lines.append("")
    mc = base.get("manual_conflicts") or []
    if mc:
        lines.append("## Противоречия, отмеченные автором вручную (между записями)")
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
        return ["нет ни одного файла: каждый документ начинается строкой «=== ФАЙЛ: Название ===»"]
    errs = []
    names = [n.lower() for n, _ in files]
    if SUMMARY.lower() not in names:
        errs.append(f"нет обязательного документа «{SUMMARY}»")
    if len(set(names)) != len(names):
        errs.append("названия документов повторяются")
    for n, body in files:
        if len(body) < 20:
            errs.append(f"документ «{n}» пустой")
    return errs


def container_style(w, cid) -> tuple[str, str | None]:
    """Стиль контейнера (поле style в его YAML) — свой или ближайшего родителя: (текст, название контейнера-источника)."""
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
    parts = [f"Общий стиль: {g}"] if g else []
    if cid:
        cs, src = container_style(ctx.w, cid)
        if cs:
            parts.append(f"Для этого контейнера (важнее общего стиля): {cs}")
    for t, (p, fm, body) in existing.items():
        if fm.get("style_override"):
            parts.append(f"Для документа «{t}»: {fm['style_override']}")
    return "\n".join(parts) or "не задан"


def _validate_losses(o):
    ls = o.get("losses")
    if not isinstance(ls, list):
        return ["нет списка losses"]
    for i, x in enumerate(ls, 1):
        if not isinstance(x, dict) or not str(x.get("what") or "").strip() or not isinstance(x.get("significant"), bool):
            return [f"losses[{i}]: нужны what (что пропало) и significant (true/false)"]
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
        raise UserError(f"База синтеза «{node.title}» ещё не пересобрана после изменений — сначала запустите Фазу 1.")
    base = w.base(cid)
    if not base or not any(g["items"] for g in base.get("groups", [])):
        raise UserError(f"Для «{node.title}» ещё нет базы синтеза: в контейнере нет обработанных мыслей. Сначала Фаза 1.")
    existing = {p.stem: (p, fm, body) for p, fm, body in w.products_of(cid)}
    previous = "\n\n".join(f"=== ФАЙЛ: {t} ===\n{body.strip()}" for t, (p, fm, body) in sorted(existing.items()))
    accepted = []
    for t, (p, fm, body) in existing.items():
        accepted += [f"{t}: {x}" for x in fm.get("accepted_losses") or []]
    restore = w.state["restore_requests"].get(cid) or []
    info = container_info(w, cid)
    completed = ("КОНТЕЙНЕР ЗАВЕРШЁН (completed): в «Сводном файле» обязательно выдели раздел «Итоговый результат» — "
                 "отдельно от текущего живого описания.") if node.status == "completed" else ""
    base_text, style = base_for_prompt(w, cid), _style(ctx, existing, cid)
    sig = U.sha1(json.dumps([base_text, style, completed, info, restore, sorted(accepted),
                             sorted((t, _norm(b)) for t, (_, _, b) in existing.items())], ensure_ascii=False))
    sigs = w.state.setdefault("synth_sig", {})
    if existing and not force and sigs.get(cid) == sig:
        msg = f"«{node.title}»: с прошлого синтеза ничего не менялось — документы актуальны."
        if not (ask_force and ask_force(msg)):
            ctx.result.update(unchanged=True, title="Документы актуальны")
            if not ask_force:  # в окне сообщение уже показано вместе с вопросом
                ctx.say(msg + f" Переписать всё равно: synth \"{node.title}\" --force")
            return []
    if confirm is not None and not confirm():  # оценка большого запуска: пользователь отказался
        ctx.result.update(cancelled=True, title="Отменено")
        ctx.say("Запуск отменён — документы не менялись.")
        return []
    text = ctx.llm.text("Синтез", {
        "container": info, "style": style, "base": base_text,
        "previous": previous or "нет — документы пишутся впервые",
        "accepted_losses": accepted or "нет", "restore": restore or "нет", "completed": completed,
    }, validate=_validate_synth, subject=f"[[{node.title}]]")
    files = parse_files(text)
    plan = []
    for name, body in files:
        title = U.safe_name(name, 80)
        if title.lower() == SUMMARY.lower():
            title = SUMMARY
        if title.lower() == node.title.lower() or title.startswith("_"):
            title = f"{title.lstrip('_')} (документ)"
        plan.append((title, body))
    reviews: dict[str, list[str]] = {}
    changed = [t for t, b in plan if existing.get(t) and _norm(existing[t][2]) != _norm(b)]
    for title, body in plan:  # сравнение версий — до записи файлов, чтобы прогон можно было продолжить
        old = existing.get(title)
        if not old or _norm(old[2]) == _norm(body):
            continue
        ctx.progress("Сравнение версий", changed.index(title) + 1, len(changed), title, echo=False)
        acc = old[1].get("accepted_losses") or []
        obj = ctx.llm.json("Сравнение версий", {
            "object_kind": "product", "container": info, "accepted_losses": acc or "нет",
            "material": f"ДОКУМЕНТ: {title}\n\nПРЕЖНЯЯ ВЕРСИЯ:\n{old[2].strip()}\n\nНОВАЯ ВЕРСИЯ:\n{body.strip()}",
        }, validate=_validate_losses, subject=f"документ «{title}» ({node.title})")
        for x in obj["losses"]:
            ref = ctx.logs.reflect("product_loss", f"{cid}:{title}", {"what": x["what"], "significant": x["significant"]})
            if x["significant"] and x["what"] not in acc:
                reviews.setdefault(title, []).append(x["what"])
                ctx.q.add("product_loss", "В новой версии документа пропало важное?",
                          f"Документ [[{w.path_key(node)}/{title}|{title}]] ({node.title}): в новой версии нет того, что было в прежней.\n\n"
                          f"**{x['what']}**\n\n{x.get('reasoning') or ''}",
                          options=[{"label": "Так и нужно — потеря намеренная (больше не поднимать)", "value": "intentional"},
                                   {"label": "Вернуть при следующем синтезе", "value": "restore"},
                                   {"label": "Откатить документ к прежней версии", "value": "rollback"}],
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
              "review_reason": "значимая потеря по сравнению с предыдущей версией" if reviews.get(title) else None}
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
    ctx.logs.change("модель", f"Фаза 2 для [[{node.title}]]: документы " + ", ".join(f"«{t}»" for t in written)
                    + (f"; не обновлялись: {', '.join(kept)}" if kept else ""))
    ctx.count("products", len(written))
    ctx.say(f"Документы «{node.title}»: " + ", ".join(written) + ".")
    if kept:
        ctx.say("Модель в этот раз не переписывала: " + ", ".join(kept) + " — они оставлены как есть.")
    if reviews:
        ctx.say(f"Есть вопросы о пропавшем в новых версиях: {sum(len(v) for v in reviews.values())} — см. open-questions.md.")
    return written

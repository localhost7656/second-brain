"""Витрины только для чтения в хранилище: _аспекты.md и _база синтеза.md."""
from __future__ import annotations

import re

from . import util as U
from .aspects import priority, type_title

READONLY = ("> [!note] Только для чтения\n> Файл пересобирается программой. Чтобы что-то изменить, положите новую мысль в `_staging` "
            "или ответьте на вопрос в [[open-questions]].\n")


def _src(world, eid: str) -> str:
    """Ссылка на запись-источник и её источник (раздел 3.4: подпись источника у мысли, цвет — из settings.yaml)."""
    e = world.entities.get(eid)
    if not e:
        return eid
    src = str(e.fm.get("source") or "").strip()
    if not src:
        return f"[[{e.title}]]"
    color = next((str(s.get("color")) for s in (world.cfg.get("sources") or [])
                  if str(s.get("name", "")).lower() == src.lower() and s.get("color")), None)
    label = f'<span style="color:{color}">{src}</span>' if color and re.fullmatch(r"#[0-9A-Fa-f]{3,8}", color) else src
    return f"[[{e.title}]] ({label})"


def render_pool_view(world, cid: str):
    node = world.nodes.get(cid)
    if node is None:
        return
    pool = world.pool(cid)
    aspects = pool["aspects"]
    comps = pool["composites"]
    counts = {"active": 0, "in_composite": 0, "outdated": 0, "dup": 0}
    for a in aspects.values():
        if a.get("duplicate_of"):
            counts["dup"] += 1
        else:
            counts[a.get("status", "active")] = counts.get(a.get("status", "active"), 0) + 1
    lines = [READONLY, f"Аспектов: {len(aspects)} — свободных {counts['active']}, в составных {counts['in_composite']}, "
             f"устаревших {counts['outdated']}, дублей {counts['dup']}. Составных: {len(comps)}.", ""]
    order = priority(world)
    live_comps = [c for c in comps.values() if c.get("status") != "outdated"]
    if live_comps:
        lines += ["## Составные", ""]
        for t in order:
            group = [c for c in live_comps if c["composite_type"] == t]
            if not group:
                continue
            lines.append(f"### {type_title(world, t)}")
            for c in group:
                val = f" · ценность {c['value']}" if c.get("value") is not None else ""
                st = " · ⚠ на пересмотре" if c.get("status") == "needs_review" else ""
                lines.append(f"- **{c['id']}** · {c.get('text', '')} · из: {', '.join(c['from'])}{val}{st}")
            lines.append("")
    for t in order:
        group = [a for a in aspects.values() if a["type"] == t and a.get("status") != "outdated" and not a.get("duplicate_of")]
        if not group:
            continue
        lines.append(f"## {type_title(world, t)}")
        for a in sorted(group, key=lambda x: (x.get("date") or "", x["id"])):
            val = f" · ценность {a['value']}" if a.get("value") is not None else ""
            st = " · в составном" if a.get("status") == "in_composite" else ""
            lines.append(f"- {a['id']} · {a['text']} · {_src(world, a['source_entity'])} · {U.ru_date(a.get('date'))}{val}{st}")
        lines.append("")
    dups = [a for a in aspects.values() if a.get("duplicate_of")]
    if dups:
        lines.append("## Дубли (учтены вместе с основным)")
        for a in dups:
            lines.append(f"- {a['id']} = {a['duplicate_of']} · {a['text']} · {_src(world, a['source_entity'])}")
        lines.append("")
    old = [a for a in aspects.values() if a.get("status") == "outdated"]
    if old:
        lines.append("## Устаревшие (не удаляются, в синтезе не участвуют)")
        for a in old:
            by = f" → заменён {a['replaced_by']}" if a.get("replaced_by") else ""
            lines.append(f"- {a['id']} · {a['text']} · {_src(world, a['source_entity'])}{by}")
        lines.append("")
    fm = {"type": "aspect_pool_view", "container": U.link(node.title), "container_id": cid, "updated": U.now_iso()}
    U.write_md(node.folder / "_аспекты.md", fm, "\n" + "\n".join(lines))


def base_text(world, cid: str) -> str:
    """Текст витрины базы синтеза (он же идёт в версии)."""
    base = world.base(cid) or {}
    node = world.nodes[cid]
    lines = [READONLY, f"Собрана: {U.ru_datetime(base.get('built'))}. ★ — первостепенное.", ""]
    for g in base.get("groups", []):
        lines.append(f"## {type_title(world, g['type'])}")
        for it in g["items"]:
            star = "★ " if it["rank"] == "primary" else ""
            srcs = ", ".join(_src(world, s) for s in it.get("sources", [])[:5])
            extra = ""
            if it.get("conflict"):
                extra += f" · ⚔ спорит с {', '.join(it['conflict'])}"
            if it.get("assumed_loser"):
                extra += " · предположительно уступает"
            if it.get("fork"):
                extra += " · развилка"
            if it.get("pinned"):
                extra += " · закреплено вами"
            lines.append(f"- {star}{it['text']} · {srcs} · ценность {it.get('value', '')}{extra}")
        lines.append("")
    if base.get("excluded"):
        lines.append(f"Не прошли фильтр ценности: {len(base['excluded'])} (остаются в пуле).")
    return "\n".join(lines)


def render_base_view(world, cid: str) -> str:
    node = world.nodes.get(cid)
    if node is None:
        return ""
    base = world.base(cid) or {}
    body = base_text(world, cid)
    fm = {"type": "synthesis_base_view", "container": U.link(node.title), "container_id": cid,
          "last_synthesized": base.get("built")}
    U.write_md(node.folder / "_база синтеза.md", fm, "\n" + body)
    return body

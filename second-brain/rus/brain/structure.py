"""Bootstrap, проход 1: черновик дерева контейнеров и его утверждение (раздел 6.3)."""
from __future__ import annotations

import json
import re

from . import util as U
from .schema import input_limit
from .ingest import load_item_body
from .vault import RU_TYPE, TYPE_RU

APPROVE_LABEL = "Структура утверждена"
LINE = re.compile(r"^(\s*)[-*]\s+(.*)$")
ID_COMMENT = re.compile(r"<!--\s*([A-Za-z]\d+)\s*-->")
TYPED = re.compile(r"^(.*?)\s*\((проект|росток|вопрос|project|seed|question)\)\s*(?:[—–-]+\s*(.*))?$", re.I)


# ---------- генерация ----------
def existing_tree(w) -> list[dict]:
    return [{"key": n.id, "title": n.title, "type": n.type, "parent": n.fm.get("parent_id"),
             "description": n.description, "applies_to": list(n.fm.get("applies_to_ids") or [])}
            for n in sorted(w.nodes.values(), key=lambda x: (w.depth(x), x.title.lower()))]


def _material_blocks(ctx, items: list[dict]) -> list[str]:
    blocks = []
    for it in items:
        body = load_item_body(ctx, it)
        blocks.append(f"[{it['id']}] {U.ru_date(it['date'])} · источник: {it['source']} · файл: {it['name']}\n{body.strip()}")
    return blocks


def _chunks(blocks: list[str], limit: int) -> list[list[str]]:
    out, cur, size = [], [], 0
    for b in blocks:
        if cur and size + len(b) > limit:
            out.append(cur)
            cur, size = [], 0
        cur.append(b[:limit])
        size += len(b)
    if cur:
        out.append(cur)
    return out


def _validate_tree(obj, must_keys: set) -> list[str]:
    errs = []
    cs = obj.get("containers")
    if not isinstance(cs, list) or not cs:
        return ["нет списка containers"]
    keys = set()
    for c in cs:
        if not isinstance(c, dict) or not str(c.get("title") or "").strip():
            errs.append("у каждого контейнера должен быть title")
            continue
        k = str(c.get("key") or "")
        if not k:
            errs.append(f"у контейнера «{c.get('title')}» нет key")
        if k in keys:
            errs.append(f"повтор key {k}")
        keys.add(k)
    missing = must_keys - keys
    if missing:
        errs.append("в ответе не хватает существующих контейнеров или строк черновика: " + ", ".join(sorted(missing))
                    + " — верни полное дерево")
    for c in cs:
        if isinstance(c, dict) and c.get("parent") not in (None, "") and str(c.get("parent")) not in keys:
            errs.append(f"parent {c.get('parent')} у «{c.get('title')}» не найден среди key")
    return errs


def _renumber_new(w, tree: list[dict]) -> list[dict]:
    """Новым контейнерам — ключи n1, n2…, чтобы пометка в строке не спутала их с существующими."""
    mapping, n = {}, 0
    for t in tree:
        if t["key"] in w.nodes:
            mapping[t["key"]] = t["key"]
        else:
            n += 1
            mapping[t["key"]] = f"n{n}"
    by_title = {t["title"].lower(): mapping[t["key"]] for t in tree}
    out = []
    for t in tree:
        t = dict(t)
        t["key"] = mapping[t["key"]]
        t["parent"] = mapping.get(t["parent"], t["parent"] if t["parent"] in w.nodes else None) if t.get("parent") else None
        refs = []
        for a in t.get("applies_to") or []:
            k = mapping.get(a) or by_title.get(str(a).lower()) or (a if a in w.nodes else None)
            if k and k != t["key"] and k not in refs:
                refs.append(k)
        t["applies_to"] = refs
        out.append(t)
    return out


def generate_draft(ctx, items: list[dict]):
    w = ctx.w
    existing = existing_tree(w)
    draft = None
    if w.p.draft.exists():
        parsed = parse_draft(w.p.draft.read_text(encoding="utf-8-sig"),
                             w.state["structure"].get("draft_titles"))
        draft = [{k: n[k] for k in ("key", "title", "type", "parent", "description", "applies_to")}
                 for n in parsed["nodes"]] or None
    tree = draft or existing
    lim = input_limit(ctx.cfg, "Структура")
    chunks = _chunks(_material_blocks(ctx, items), max(lim - 40000, min(20000, lim // 2)))
    for i, ch in enumerate(chunks, 1):
        if len(chunks) > 1:
            ctx.progress("Черновик структуры", i, len(chunks), f"часть {i}")
        must = {str(n["key"]) for n in (tree or [])}
        obj = ctx.llm.json("Структура", {
            "existing": existing or "нет — хранилище пустое",
            "draft": tree if tree else "нет",
            "part": f"часть {i} из {len(chunks)}",
            "material": "\n\n=====\n\n".join(ch),
        }, validate=lambda o, m=must: _validate_tree(o, m), subject=f"черновик структуры, часть {i}/{len(chunks)}")
        tree = []
        for c in obj["containers"]:
            tree.append({"key": str(c["key"]), "title": U.safe_name(str(c["title"]), 60),
                         "type": RU_TYPE.get(str(c.get("type") or "project").lower(), "project"),
                         "parent": str(c["parent"]) if c.get("parent") else None,
                         "description": str(c.get("description") or "").strip(),
                         "applies_to": [str(x) for x in (c.get("applies_to") or [])],
                         "files": [str(x) for x in (c.get("files") or [])]})
        ctx.checkpoint()
    tree = _renumber_new(w, tree)
    write_draft(ctx, tree, items)
    ref = ctx.logs.reflect("structure_draft", "bootstrap", {"containers": [t["title"] for t in tree]})
    w.state["structure"].update({"pending": True, "ref": ref, "draft_titles": {t["key"]: t["title"] for t in tree}})
    for it in items:
        it["stage"] = "await_structure"
    ctx.logs.change("модель", f"предложен черновик структуры (контейнеров: {len(tree)})")
    ctx.count("structure_drafts")


def write_draft(ctx, tree: list[dict], items: list[dict]):
    w = ctx.w
    by_key = {t["key"]: t for t in tree}
    kids: dict = {}
    for t in tree:
        p = t["parent"] if t["parent"] in by_key else None
        kids.setdefault(p, []).append(t)
    lines = ["# Черновик структуры", "",
             "Это дерево контейнеров, которое модель предлагает по всему архиву. Проверьте его один раз целиком, потом записи разложатся по нему.", "",
             "Что можно делать прямо в этом файле:",
             "- **переименовать** — исправьте название;",
             "- **переподчинить** — сдвиньте строку отступом (Tab) под другой контейнер или уберите отступ;",
             "- **удалить** или **слить** — удалите строку; записи этой темы разложатся по оставшимся контейнерам;",
             "- **добавить** — допишите свою строку в том же формате;",
             "- **тип** — в скобках: проект, росток или вопрос; после тире — описание; после «| применяется в:» — связи через «;».",
             "",
             "В конце каждой строки стоит служебная пометка вида <!-- n1 --> — её не трогайте: по ней программа узнаёт контейнер после переименования. У своих новых строк пометка не нужна. Удалить уже существующий контейнер (с пометкой на «k») отсюда нельзя.",
             "Когда закончите, отметьте галочку ниже и запустите программу.", "",
             f"- [ ] {APPROVE_LABEL}", "", "## Дерево", ""]

    def emit(t, depth):
        title_of = lambda k: by_key[k]["title"] if k in by_key else k
        line = "\t" * depth + f"- {t['title']} ({TYPE_RU.get(t['type'], 'проект')})"
        if t.get("description"):
            line += f" — {t['description']}"
        if t.get("applies_to"):
            line += " | применяется в: " + "; ".join(title_of(k) for k in t["applies_to"])
        line += f" <!-- {t['key']} -->"
        lines.append(line)
        for c in kids.get(t["key"], []):
            emit(c, depth + 1)
    for t in kids.get(None, []):
        emit(t, 0)
    lines += ["", "## Какие файлы к чему относятся (для проверки, не редактируется)", ""]
    names = {it["id"]: it["name"] for it in items}
    for t in tree:
        fs = [names[f] for f in t.get("files", []) if f in names]
        if fs:
            lines.append(f"- **{t['title']}**: " + ", ".join(fs[:30]) + (" …" if len(fs) > 30 else ""))
    U.atomic_write_text(w.p.draft, "\n".join(lines) + "\n")


# ---------- разбор правок пользователя ----------
def parse_draft(text: str, proposed: dict | None = None) -> dict:
    """proposed — {key: название} из черновика, как его написала программа: по нему
    связи «применяется в» находят контейнер, даже если его переименовали."""
    text = text.replace("\r\n", "\n")
    seen: set = set()
    approved = False
    for line in text.split("\n"):
        m = re.match(r"^\s*[-*]\s*\[([ xXхХ✓vV])\]\s*(.*)$", line)
        if m and APPROVE_LABEL.lower() in m.group(2).lower():
            approved = bool(m.group(1).strip())
    nodes, stack, in_tree = [], [], False
    n_new = 0
    for line in text.split("\n"):
        if line.startswith("## "):
            in_tree = line.strip().lower().startswith("## дерево")
            continue
        if not in_tree:
            continue
        m = LINE.match(line.replace("\t", "    "))
        if not m:
            continue
        indent, content = len(m.group(1)), m.group(2).strip()
        if not content or content.startswith("["):
            continue
        idm = ID_COMMENT.search(content)
        key = idm.group(1) if idm else None
        if key in seen:  # строку скопировали вместе с пометкой — это новый контейнер
            key = None
        content = ID_COMMENT.sub("", content).strip()
        applies = []
        if "| применяется в:" in content:
            content, rest = content.split("| применяется в:", 1)
            applies = [a.strip() for a in rest.split(";") if a.strip()]
            content = content.strip()
        tm = TYPED.match(content)
        if tm:
            title, ntype, desc = tm.group(1).strip(), RU_TYPE[tm.group(2).lower()], (tm.group(3) or "").strip()
        else:
            parts = re.split(r"\s+[—–]\s+", content, maxsplit=1)
            title, ntype, desc = parts[0].strip(), "project", (parts[1].strip() if len(parts) > 1 else "")
        if not key:
            n_new += 1
            key = f"d{n_new}"
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else None
        nodes.append({"key": key, "title": U.safe_name(title, 60), "type": ntype, "parent": parent,
                      "description": desc, "applies_to_titles": applies,
                      "applies_to": []})
        stack.append((indent, key))
        seen.add(key)
    title_to_key = {n["title"].lower(): n["key"] for n in nodes}
    keys = {n["key"] for n in nodes}
    old_title_to_key = {str(t).lower(): k for k, t in (proposed or {}).items() if k in keys}
    unresolved = []
    for n in nodes:
        refs = []
        for a in n["applies_to_titles"]:
            k = title_to_key.get(a.lower()) or old_title_to_key.get(a.lower())
            if k is None and a in keys:
                k = a
            if k is None:
                unresolved.append((n["title"], a))
                k = a  # может быть существующим контейнером вне черновика — проверит set_applies_to
            if k != n["key"] and k not in refs:
                refs.append(k)
        n["applies_to"] = refs
    return {"approved": approved, "nodes": nodes, "unresolved": unresolved}


def apply_draft(ctx) -> bool:
    """True — если черновик утверждён и применён."""
    w = ctx.w
    if not w.p.draft.exists():
        if w.state["structure"].get("pending"):
            w.state["structure"]["pending"] = False
        return False
    parsed = parse_draft(w.p.draft.read_text(encoding="utf-8-sig"), w.state["structure"].get("draft_titles"))
    if not parsed["approved"]:
        return False
    key_to_id: dict = {}
    created = renamed = 0
    for n in parsed["nodes"]:  # порядок сверху вниз: родитель всегда раньше потомка
        pid = key_to_id.get(n["parent"]) if n["parent"] else None
        if n["key"] in w.nodes:
            node = w.nodes[n["key"]]
            if node.title != n["title"]:
                w.rename_node(node, n["title"])
                renamed += 1
            node.fm["type"] = n["type"]
            if n["description"]:
                node.fm["description"] = n["description"]
            if node.fm.get("parent_id") != pid:
                node.fm["parent_id"] = pid
            key_to_id[n["key"]] = node.id
            w.save_node(node)
        else:
            node = w.create_node(n["title"], n["type"], pid, n["description"])
            key_to_id[n["key"]] = node.id
            created += 1
            ctx.logs.change("пользователь", f"утверждён контейнер [[{node.title}]] ({TYPE_RU[node.type]})")
    for n in parsed["nodes"]:
        node = w.nodes.get(key_to_id.get(n["key"]))
        if node is None:
            continue
        refs = [key_to_id.get(a, a) for a in n["applies_to"]]
        w.set_applies_to(node, refs)
        w.save_node(node)
    w.normalize_folders()
    w.refresh_links()
    for cid in key_to_id.values():
        from .index import index_container
        index_container(ctx, cid)
    st = w.state["structure"]
    proposed = st.get("draft_titles") or {}
    final = {n["key"]: n["title"] for n in parsed["nodes"]}
    removed = sorted(t for k, t in proposed.items() if k not in final)
    added = sorted(t for k, t in final.items() if k not in proposed)
    renamed_l = sorted(f"{proposed[k]} → {t}" for k, t in final.items() if k in proposed and proposed[k] != t)
    ctx.logs.decision(st.get("ref"), "structure_draft", "bootstrap",
                      {"proposed": len(proposed), "approved": len(final),
                       "removed": removed, "added": added, "renamed": renamed_l},
                      matched=not (removed or added or renamed_l))
    for title, a in parsed.get("unresolved") or []:
        if not w.resolve_container(a):
            ctx.notices.append(f"В черновике у «{title}» связь «применяется в: {a}» не нашлась — пропущена.")
    st.update({"pending": False, "approved_once": True, "ref": None, "draft_titles": None})
    archive = w.p.logs / f"структура утверждена {U.today()}.md"
    U.retry_fs(w.p.draft.replace, U.unique_path(w.p.logs, archive.stem))
    for it in w.state["items"].values():
        if it.get("stage") == "await_structure":
            it["stage"] = "ready"
    ctx.logs.change("пользователь", f"структура утверждена: новых контейнеров {created}, переименовано {renamed}")
    ctx.say(f"Структура утверждена: создано контейнеров — {created}.")
    ctx.checkpoint()
    return True

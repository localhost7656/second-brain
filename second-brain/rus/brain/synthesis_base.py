"""Фаза 1, шаги 8–9: сборка базы синтеза контейнера и сравнение с прежней версией (разделы 6.10–6.13, 16.4).
Стадии в state.dirty[cid].stage: analysis → value → assemble → compare."""
from __future__ import annotations

import json

from . import ops
from . import util as U
from .schema import input_limit
from .aspects import composite_types, priority, type_title
from .index import index_container
from .vault import NODE_TYPES, TYPE_RU
from .views import base_text

ORDER = ["analysis", "value", "assemble", "compare"]


def mark_stage(w, cid: str, stage: str, reason: str = ""):
    """Поставить контейнер в очередь сборки не позже указанной стадии."""
    if cid not in w.nodes:
        return
    d = w.state["dirty"].get(cid)
    if d is None:
        w.state["dirty"][cid] = {"stage": stage, "reasons": [reason] if reason else []}
        return
    if ORDER.index(stage) < ORDER.index(d["stage"]):
        d["stage"] = stage
    if reason and reason not in d["reasons"]:
        d["reasons"].append(reason)


def _pool(w, cid):
    pool = w.pool(cid)
    pool.setdefault("accepted_losses", [])
    return pool


def container_info(w, cid) -> dict:
    n = w.nodes[cid]
    p = w.parent_of(n)
    info = {"title": n.title, "type": TYPE_RU.get(n.type, n.type), "description": n.description,
            "status": n.status, "parent": p.title if p else None,
            "applies_to": [w.nodes[i].title for i in n.fm.get("applies_to_ids") or [] if i in w.nodes]}
    return info


def check_value_thresholds(ctx):
    """Пороги ценности контейнера изменились (свои или общие) — база пересобирается кодом, без новых оценок модели."""
    w = ctx.w
    for cid in list(w.nodes):
        base = w.base(cid)
        if not base or cid in w.state["dirty"]:
            continue
        used = base.get("thresholds") or {"value_min": ctx.th["value_min"], "value_primary": ctx.th["value_primary"]}
        now = {"value_min": ctx.thr("value_min", cid), "value_primary": ctx.thr("value_primary", cid)}
        if used != now:
            w.mark_recalc(cid, "изменились пороги ценности")
            ctx.logs.change("программа", f"[[{w.nodes[cid].title}]]: пороги ценности {used['value_min']}/{used['value_primary']} → "
                                          f"{now['value_min']}/{now['value_primary']} — база синтеза будет пересобрана")


def run_all(ctx):
    w = ctx.w
    done = 0
    check_value_thresholds(ctx)
    for _ in range(500):
        for cid in [c for c in w.state["dirty"] if c not in w.nodes]:
            del w.state["dirty"][cid]
        pending = list(w.state["dirty"])
        if not pending:
            break
        pending.sort(key=lambda c: (-w.depth(w.nodes[c]), c))
        ctx.progress("Базы синтеза", done + 1, done + len(pending), w.nodes[pending[0]].title)
        build(ctx, pending[0])
        done += 1
    return done


def build(ctx, cid):
    steps = {"analysis": analysis, "value": value, "assemble": assemble, "compare": compare}
    for _ in range(12):
        d = ctx.w.state["dirty"].get(cid)
        if d is None:
            return
        steps[d["stage"]](ctx, cid)
        ctx.checkpoint()


def _live(pool) -> dict:
    return {k: a for k, a in pool["aspects"].items() if a.get("status") != "outdated" and not a.get("duplicate_of")}


def _owner(pool, aid):
    for c in pool["composites"].values():
        if c.get("status") != "outdated" and aid in c["from"]:
            return c["id"]
    return None


def _num(aid: str) -> int:
    try:
        return int(aid[1:])
    except ValueError:
        return 0


# ---------- 8.1 анализ пула ----------
def similar_pairs(ctx, live: dict, new_ids: list[str], rejected: set, cid: str | None = None) -> list[dict]:
    thr = float(ctx.thr("duplicate_similarity", cid))
    allow = set(live)
    probe = new_ids if new_ids else list(live)[:300]
    seen, out = set(), []
    for aid in probe:
        v = ctx.vs.get("aspects", aid)
        if v is None:
            continue
        for bid, sim in ctx.vs.search("aspects", v, k=4, allow=allow, exclude=[aid]):
            if sim < thr:
                break
            key = tuple(sorted((aid, bid)))
            if key in seen or ("duplicate",) + key in rejected:
                continue
            seen.add(key)
            out.append({"a": key[0], "b": key[1], "similarity": round(sim, 3)})
    return out[:150]


def _analysis_validator(live, comps, ent_ids, types):
    def conf_ok(v):
        return isinstance(v, (int, float)) and 0 <= v <= 100

    def v(o):
        errs = []
        for k in ("composites", "dissolve", "duplicates", "outdated", "conflicts", "structure"):
            if k in o and o[k] is not None and not isinstance(o[k], list):
                errs.append(f"{k} — должен быть списком")
        if errs:
            return errs
        used = {}
        for i, c in enumerate(o.get("composites") or [], 1):
            if not isinstance(c, dict):
                errs.append(f"composites[{i}] — не объект")
                continue
            ct = c.get("composite_type")
            if ct not in types:
                errs.append(f"composites[{i}]: неизвестный composite_type «{ct}» — допустимы: {', '.join(types)}")
                continue
            ext = c.get("extend") or None
            if ext is not None:
                if ext not in comps:
                    errs.append(f"composites[{i}]: extend — составного {ext} нет в списке")
                elif comps[ext]["composite_type"] != ct:
                    errs.append(f"composites[{i}]: extend {ext} другой формулы ({comps[ext]['composite_type']})")
            fr = c.get("from")
            if not isinstance(fr, list) or len(fr) < 2:
                errs.append(f"composites[{i}]: from — список минимум из двух id аспектов")
                continue
            for a in fr:
                if a not in live:
                    errs.append(f"composites[{i}]: аспекта {a} нет в списке")
                    continue
                if a in used:
                    errs.append(f"аспект {a} попал в два составных")
                used[a] = i
                if live[a]["type"] not in types[ct]["types"]:
                    errs.append(f"composites[{i}]: тип аспекта {a} ({live[a]['type']}) не входит в формулу {ct}")
                own = live[a].get("_owner")
                if own and own != ext:
                    errs.append(f"composites[{i}]: аспект {a} уже входит в составной {own}")
            if not str(c.get("text") or "").strip():
                errs.append(f"composites[{i}]: нужен text — описание целого")
        for i, x in enumerate(o.get("dissolve") or [], 1):
            if not isinstance(x, dict) or x.get("composite") not in comps:
                errs.append(f"dissolve[{i}]: составного нет в списке")
        for i, x in enumerate(o.get("duplicates") or [], 1):
            if not isinstance(x, dict) or x.get("aspect") not in live or x.get("duplicate_of") not in live \
                    or x.get("aspect") == x.get("duplicate_of"):
                errs.append(f"duplicates[{i}]: нужны два разных id из списка аспектов")
        for i, x in enumerate(o.get("outdated") or [], 1):
            if not isinstance(x, dict) or x.get("aspect") not in live or x.get("replaced_by") not in live \
                    or x.get("aspect") == x.get("replaced_by"):
                errs.append(f"outdated[{i}]: нужны два разных id из списка аспектов")
            elif not conf_ok(x.get("confidence")):
                errs.append(f"outdated[{i}]: confidence — число 0–100")
        for i, x in enumerate(o.get("conflicts") or [], 1):
            if not isinstance(x, dict) or x.get("a") not in live or x.get("b") not in live or x.get("a") == x.get("b"):
                errs.append(f"conflicts[{i}]: нужны два разных id из списка аспектов")
            elif live[x["a"]]["type"] != live[x["b"]]["type"]:
                errs.append(f"conflicts[{i}]: противоречия ищутся только между аспектами одного типа")
            elif x.get("assumed") not in ("a", "b", "both"):
                errs.append(f"conflicts[{i}]: assumed — \"a\", \"b\" или \"both\"")
        for i, x in enumerate(o.get("structure") or [], 1):
            if not isinstance(x, dict) or x.get("kind") not in ("seed_to_project", "subcontainer"):
                errs.append(f"structure[{i}]: kind — seed_to_project или subcontainer")
                continue
            if not conf_ok(x.get("confidence")):
                errs.append(f"structure[{i}]: confidence — число 0–100")
            if x["kind"] == "subcontainer":
                if not str(x.get("title") or "").strip():
                    errs.append(f"structure[{i}]: нужен title")
                if x.get("type") not in NODE_TYPES:
                    errs.append(f"structure[{i}]: type — project, seed или question")
                es = x.get("entities")
                if not isinstance(es, list) or not es or any(e not in ent_ids for e in es):
                    errs.append(f"structure[{i}]: entities — id записей из списка")
        return errs
    return v


def _chunks_by_size(items: list, limit: int) -> list[list]:
    out, cur, size = [], [], 0
    for it in items:
        n = len(json.dumps(it, ensure_ascii=False))
        if cur and size + n > limit:
            out.append(cur)
            cur, size = [], 0
        cur.append(it)
        size += n
    if cur:
        out.append(cur)
    return out or [[]]


def analysis(ctx, cid):
    w = ctx.w
    pool = _pool(w, cid)
    node = w.nodes[cid]
    live = _live(pool)
    new_ids = [i for i in w.state["new_aspects"].get(cid, []) if i in live]
    if not live:
        w.state["new_aspects"][cid] = []
        w.state["dirty"][cid]["stage"] = "value"
        return
    comps = {k: c for k, c in pool["composites"].items() if c.get("status") != "outdated"}
    for aid in live:
        live[aid] = dict(live[aid])
        live[aid]["_owner"] = _owner(pool, aid)
    types = composite_types(w)
    formulas = [{"name": n, "title": t["title"], "types": t["types"], "formula": t["formula"]} for n, t in types.items()]
    rejected = {(r["kind"], r.get("a"), r.get("b")) for r in pool["rejected"]}
    rejected |= {(r["kind"],) + tuple(sorted((r.get("a"), r.get("b")))) for r in pool["rejected"] if r.get("a") and r.get("b")}
    decided = [f"{r['kind']}: {r.get('a')} — {r.get('b')}" for r in pool["rejected"]]
    decided += [f"conflict: {k['a']} — {k['b']} ({k['status']})" for k in pool["conflicts"]]
    ent_ids = {e.id for e in w.entities_of(cid)}
    entities = [{"id": e.id, "title": e.title, "date": e.created} for e in sorted(w.entities_of(cid), key=lambda x: x.created)]
    asp_list = [{"id": a["id"], "type": a["type"], "text": a["text"], "date": a.get("date"), "status": a["status"],
                 "entity": a["source_entity"]} for a in sorted(live.values(), key=lambda x: (x.get("date") or "", _num(x["id"])))]
    comp_list = [{"id": c["id"], "composite_type": c["composite_type"], "from": c["from"], "text": c.get("text", ""),
                  "status": c.get("status")} for c in comps.values()]
    lim = input_limit(ctx.cfg, "Анализ пула")
    limit = max(lim - 60000, min(30000, lim // 2))
    parts = _chunks_by_size(asp_list, limit)
    results = []
    for i, part in enumerate(parts, 1):
        part_ids = {a["id"] for a in part}
        part_live = {k: live[k] for k in part_ids}
        cands = {}
        for name, t in types.items():
            ids = [a for a in part_ids if live[a]["status"] == "active" and live[a]["type"] in t["types"]]
            if len({live[a]["type"] for a in ids}) >= 2:
                cands[name] = sorted(ids, key=_num)[:200]
        obj = ctx.llm.json("Анализ пула", {
            "container": container_info(w, cid), "formulas": formulas,
            "part": f"часть {i} из {len(parts)}" if len(parts) > 1 else "весь пул",
            "aspects": part, "composites": comp_list or "нет",
            "new_ids": [x for x in new_ids if x in part_ids] or "нет (повторный анализ)",
            "candidates": cands or "нет",
            "similar_pairs": similar_pairs(ctx, part_live, [x for x in new_ids if x in part_ids], rejected, cid) or "нет",
            "decided": decided or "нет", "entities": entities,
        }, validate=_analysis_validator(part_live, comps, ent_ids, types), subject=f"[[{node.title}]]")
        results.append(obj)
    for obj in results:
        apply_analysis(ctx, cid, obj, rejected)
    w.state["new_aspects"][cid] = []
    w.save_pool(cid)
    if cid in w.state["dirty"]:
        w.state["dirty"][cid]["stage"] = "value"


def apply_analysis(ctx, cid, obj, rejected):
    w = ctx.w
    pool = _pool(w, cid)
    node = w.nodes[cid]
    A = pool["aspects"]
    H = ctx.thr("high", cid)
    for x in obj.get("dissolve") or []:
        ops.dissolve_composite(pool, x["composite"], x.get("reasoning") or "распущен анализом пула")
        ctx.logs.change("модель", f"[[{node.title}]]: составной {x['composite']} распущен")
    for c in obj.get("composites") or []:
        fr = [a for a in c["from"] if a in A and A[a].get("status") != "outdated"]
        if len(fr) < 2:
            continue
        ext = c.get("extend") or None
        if ext and ext in pool["composites"]:
            comp = pool["composites"][ext]
            for a in set(comp["from"]) - set(fr):
                if a in A and A[a].get("status") == "in_composite":
                    A[a]["status"] = "active"
            comp.update({"from": fr, "text": c["text"].strip(), "status": "active", "value": None, "note": None})
            cid_c = ext
            ctx.logs.change("модель", f"[[{node.title}]]: достроен составной {ext} ({type_title(w, comp['composite_type'])})")
        else:
            cid_c = w.next_id("c")
            pool["composites"][cid_c] = {"id": cid_c, "composite_type": c["composite_type"], "from": fr,
                                         "text": c["text"].strip(), "status": "active", "value": None,
                                         "created": U.today()}
            ctx.logs.change("модель", f"[[{node.title}]]: собран составной {cid_c} — {type_title(w, c['composite_type'])} из {', '.join(fr)}")
            ctx.count("composites")
        for a in fr:
            A[a]["status"] = "in_composite"
    new_dups = []
    for x in obj.get("duplicates") or []:
        a, b = A.get(x["aspect"]), A.get(x["duplicate_of"])
        if not a or not b or a.get("duplicate_of") or b.get("duplicate_of"):
            continue
        early, late = sorted([a, b], key=lambda r: (r.get("date") or "", _num(r["id"])))
        if late.get("status") == "in_composite":
            continue  # составной не разбираем ради дубля
        late["duplicate_of"] = early["id"]
        for z in A.values():
            if z.get("duplicate_of") == late["id"]:
                z["duplicate_of"] = early["id"]
        pool["conflicts"] = [k for k in pool["conflicts"] if late["id"] not in (k["a"], k["b"])]
        new_dups.append((late["id"], early["id"]))
        ctx.logs.change("модель", f"[[{node.title}]]: {late['id']} — дубль {early['id']} («{U.short_title(late['text'], 8)}»)")
        ctx.count("duplicates")
    if new_dups:
        ask_dup_review(ctx, cid, new_dups)
    for x in obj.get("outdated") or []:
        old, new = A.get(x["aspect"]), A.get(x["replaced_by"])
        if not old or not new:
            continue
        if (old.get("date") or "") > (new.get("date") or ""):
            old, new = new, old  # устаревает более старое по дате записи
        if ("outdated", old["id"], new["id"]) in rejected or old.get("status") == "outdated":
            continue
        conf = x.get("confidence")
        ref = ctx.logs.reflect("outdated", f"{cid}:{old['id']}", {"replaced_by": new["id"]}, conf)
        eo, en = w.entities.get(old["source_entity"]), w.entities.get(new["source_entity"])
        ctx.q.add("outdated", "Новая мысль пересматривает старую?",
                  f"Контейнер [[{node.title}]]. Похоже, более новая запись пересматривает более старую.\n\n"
                  f"- Было ({U.ru_date(old.get('date'))}, {('[[' + eo.title + ']]') if eo else old['source_entity']}): «{old['text']}»\n"
                  f"- Стало ({U.ru_date(new.get('date'))}, {('[[' + en.title + ']]') if en else new['source_entity']}): «{new['text']}»\n\n"
                  f"Уверенность модели: {conf}. {x.get('reasoning') or ''}",
                  options=[{"label": "Да, старое устарело — в базе синтеза оставить новое", "value": "yes"},
                           {"label": "Нет, оба утверждения верны", "value": "no"}],
                  data={"container": cid, "aspect": old["id"], "replaced_by": new["id"]},
                  dedup=f"outdated:{cid}:{old['id']}:{new['id']}", ref=ref)
        ctx.count("outdated_proposals")
    known = {k.get("key") for k in pool["conflicts"]}
    for x in obj.get("conflicts") or []:
        a, b = A.get(x["a"]), A.get(x["b"])
        if not a or not b:
            continue
        key = "|".join(sorted((a["id"], b["id"])))
        if key in known or ("conflict",) + tuple(sorted((a["id"], b["id"]))) in rejected:
            continue
        known.add(key)
        ref = ctx.logs.reflect("conflict", f"{cid}:{key}", {"assumed": x["assumed"], "assumption": x.get("assumption")})
        pool["conflicts"].append({"key": key, "a": x["a"], "b": x["b"], "type": a["type"], "assumed": x["assumed"],
                                  "assumption": x.get("assumption") or "", "reasoning": x.get("reasoning") or "",
                                  "status": "open", "decision": None, "ref": ref, "created": U.now_iso()})
        _link_conflict_entities(ctx, a["source_entity"], b["source_entity"], add=True)
        assumed = {"a": f"верно {x['a']}", "b": f"верно {x['b']}"}.get(str(x["assumed"]), str(x["assumed"]))
        ctx.logs.change("модель", f"[[{node.title}]]: противоречие {x['a']} ⚔ {x['b']}, пока предполагаю: {assumed}")
        ctx.count("conflicts")
    for x in obj.get("structure") or []:
        conf = x["confidence"]
        if x["kind"] == "seed_to_project":
            if node.type != "seed" or ("seed_to_project", cid, None) in rejected:
                continue
            ref = ctx.logs.reflect("seed_to_project", cid, True, conf)
            if conf >= H:
                node.fm["type"] = "project"
                w.save_node(node)
                ctx.logs.change("модель", f"росток [[{node.title}]] стал проектом (уверенность {conf})")
            else:
                ctx.q.add("structure_seed", "Росток дорос до проекта?",
                          f"Росток [[{node.title}]] накопил материал: {x.get('reasoning') or ''}\n\nУверенность модели: {conf}.",
                          options=[{"label": "Да, сделать проектом", "value": "yes"}, {"label": "Нет, пусть остаётся ростком", "value": "no"}],
                          data={"container": cid}, dedup=f"seed:{cid}", ref=ref)
        else:
            title = U.safe_name(str(x["title"]), 60)
            if ("subcontainer", cid, title.lower()) in rejected:
                continue
            ents = [e for e in x["entities"] if e in w.entities and w.entities[e].container_id == cid]
            if not ents:
                continue
            spec = {"name": title, "type": x.get("type") or "project", "description": x.get("description") or ""}
            ref = ctx.logs.reflect("subcontainer", cid, {"title": title, "entities": ents}, conf)
            if conf >= H:
                ops.create_subcontainer(ctx, cid, spec, ents, "модель", conf)
            else:
                names = ", ".join(f"[[{w.entities[e].title}]]" for e in ents[:12])
                ctx.q.add("structure_sub", "Выделить под-контейнер?",
                          f"Внутри [[{node.title}]] сложилась отдельная подтема «{title}» ({TYPE_RU.get(spec['type'], 'проект')}): "
                          f"{spec['description']}\n\nЗаписи, которые туда перейдут: {names}.\n\n{x.get('reasoning') or ''}\nУверенность модели: {conf}.",
                          options=[{"label": f"Да, выделить «{title}»", "value": "yes"}, {"label": "Нет", "value": "no"}],
                          free_text=True, free_hint="Или напишите другое название под-контейнера.",
                          data={"container": cid, "spec": spec, "entities": ents},
                          dedup=f"sub:{cid}:{title.lower()}", ref=ref)


def _link_conflict_entities(ctx, e1: str, e2: str, add: bool):
    """conflicts_with в YAML записей — видно при открытии файла (раздел 6.12)."""
    w = ctx.w
    auto = w.state.setdefault("auto_cw", {})
    for x, y in ((e1, e2), (e2, e1)):
        ex, ey = w.entities.get(x), w.entities.get(y)
        if not ex or not ey or x == y:
            continue
        lst = auto.setdefault(x, [])
        if add and y not in lst:
            lst.append(y)
        if not add and y in lst:
            lst.remove(y)
        cur = [U.unlink(v) for v in U.as_list(ex.fm.get("conflicts_with"))]
        manual = [t for t in cur if t and (w.entities.get(_eid_by_title(w, t)) is None or _eid_by_title(w, t) not in lst)]
        want = manual + [w.entities[i].title for i in lst if i in w.entities and w.entities[i].title not in manual]
        if [U.link(t) for t in want] != U.as_list(ex.fm.get("conflicts_with")):
            ex.fm["conflicts_with"] = [U.link(t) for t in want]
            w.save_entity(ex)
        w.state.setdefault("cw_seen", {})[x] = sorted(want)


def _eid_by_title(w, title: str):
    t = (title or "").lower()
    for e in w.entities.values():
        if e.title.lower() == t:
            return e.id
    return None


def ask_dup_review(ctx, cid, pairs):
    w = ctx.w
    pool = w.pool(cid)
    node = w.nodes[cid]
    dedup = f"dupfix:{cid}"
    q = ctx.q.find(dedup)
    old_pairs = q["data"]["pairs"] if q else []
    allp = old_pairs + [list(p) for p in pairs if list(p) not in old_pairs]
    lines = []
    for late, early in allp[-40:]:
        a, b = pool["aspects"].get(late), pool["aspects"].get(early)
        if a and b:
            lines.append(f"- {late} «{a['text']}» = {early} «{b['text']}»")
    text = (f"В [[{node.title}]] связаны как дубли (в базе синтеза идут одним пунктом со ссылками на все записи, ничего не удалено):\n\n"
            + "\n".join(lines) + "\n\nЕсли связь ошибочна, впишите номер дубля (например a12) после «Ответ:» — связь будет снята.")
    if q:
        q["text"] = text
        q["data"]["pairs"] = allp
        return
    ctx.q.add("dup_fix", "Проверьте связанные дубли", text,
              options=[{"label": "Все связи верны", "value": "ok"}], free_text=True,
              free_hint="Номера ошибочных дублей через запятую.",
              data={"container": cid, "pairs": allp}, dedup=dedup)


# ---------- 8.2 ценность ----------
def value_items(w, cid) -> list[dict]:
    pool = _pool(w, cid)
    A = pool["aspects"]
    out = []
    for c in pool["composites"].values():
        if c.get("status") == "outdated":
            continue
        parts = [A[a] for a in c["from"] if a in A]
        out.append({"id": c["id"], "type": c["composite_type"], "composite": True, "text": c.get("text", ""),
                    "parts": [f"{p['type']}: {p['text']}" for p in parts],
                    "date": max([p.get("date") or "" for p in parts] or [""])})
    for a in A.values():
        if a.get("status") == "active" and not a.get("duplicate_of"):
            out.append({"id": a["id"], "type": a["type"], "text": a["text"], "date": a.get("date")})
    out.sort(key=lambda x: (x.get("date") or "", x["id"]))
    return out


def value(ctx, cid):
    w = ctx.w
    pool = _pool(w, cid)
    items = value_items(w, cid)
    if items:
        n = int(ctx.cfg["limits"]["max_items_per_value_call"])
        parts = [items[i:i + n] for i in range(0, len(items), n)]
        got = {}
        for i, part in enumerate(parts, 1):
            ids = [x["id"] for x in part]

            def check(o, ids=ids):
                vs = o.get("values")
                if not isinstance(vs, list):
                    return ["нет списка values"]
                errs, seen = [], set()
                for x in vs:
                    if not isinstance(x, dict) or x.get("id") not in ids:
                        errs.append(f"лишний или неизвестный id: {x.get('id') if isinstance(x, dict) else x}")
                    elif not isinstance(x.get("value"), (int, float)) or not 0 <= x["value"] <= 100:
                        errs.append(f"{x['id']}: value — число 0–100")
                    else:
                        seen.add(x["id"])
                miss = [x for x in ids if x not in seen]
                if miss:
                    errs.append("не оценены: " + ", ".join(miss[:30]) + (" …" if len(miss) > 30 else ""))
                return errs[:20]
            obj = ctx.llm.json("Ценность", {"container": container_info(w, cid),
                                            "part": f"часть {i} из {len(parts)}" if len(parts) > 1 else "все элементы",
                                            "items": part}, validate=check, subject=f"[[{w.nodes[cid].title}]]")
            for x in obj["values"]:
                got[x["id"]] = int(round(x["value"]))
        for aid, v in got.items():
            rec = pool["composites"].get(aid) or pool["aspects"].get(aid)
            if rec is not None:
                rec["value"] = v
        for a in pool["aspects"].values():  # дубли оцениваются вместе с исходным (раздел 6.11)
            if a.get("duplicate_of") and a["duplicate_of"] in pool["aspects"]:
                a["value"] = pool["aspects"][a["duplicate_of"]].get("value")
        w.save_pool(cid)
    w.state["dirty"][cid]["stage"] = "assemble"


# ---------- 8.3–8.6 фильтр, группы, ранжирование ----------
def _sources(pool, rec) -> tuple[list[str], list[str]]:
    A = pool["aspects"]
    base_ids = rec["from"] if "composite_type" in rec else [rec["id"]]
    srcs, dups = [], []
    for aid in base_ids:
        a = A.get(aid)
        if not a:
            continue
        if a["source_entity"] not in srcs:
            srcs.append(a["source_entity"])
        for z in A.values():
            if z.get("duplicate_of") == aid:
                dups.append(z["id"])
                if z["source_entity"] not in srcs:
                    srcs.append(z["source_entity"])
    return srcs, dups


def manual_conflicts(ctx, cid) -> list[dict]:
    w = ctx.w
    auto = w.state.get("auto_cw", {})
    out, seen = [], set()
    for e in w.entities_of(cid):
        for v in U.as_list(e.fm.get("conflicts_with")):
            t = U.unlink(v)
            oid = _eid_by_title(w, t) if t else None
            if not oid or oid in auto.get(e.id, []):
                continue
            key = tuple(sorted((e.id, oid)))
            if key in seen:
                continue
            seen.add(key)
            out.append({"a": e.id, "b": oid})
    return out


def assemble(ctx, cid):
    w = ctx.w
    pool = _pool(w, cid)
    node = w.nodes[cid]
    A, C = pool["aspects"], pool["composites"]
    vmin, vprim = ctx.thr("value_min", cid), ctx.thr("value_primary", cid)
    passed, excluded = {}, []
    for it in value_items(w, cid):
        rec = C.get(it["id"]) or A.get(it["id"])
        v = rec.get("value")
        if rec.get("pinned") or v is None or v >= vmin:
            passed[it["id"]] = rec
        else:
            excluded.append(it["id"])
    marks: dict[str, dict] = {}

    def mark(aid, **kw):
        marks.setdefault(aid, {}).update(kw)
        if "conflict" in kw:
            pass
    live = _live(pool)
    for k in pool["conflicts"]:
        a, b = k["a"], k["b"]
        if k["status"] == "rejected" or a not in live or b not in live:
            continue
        other = {a: b, b: a}
        if k["status"] == "resolved":
            d = k.get("decision")
            if d == "a":
                mark(b, rejected_alt=True)
            elif d == "b":
                mark(a, rejected_alt=True)
            elif d == "both":
                mark(a, fork=True)
                mark(b, fork=True)
            continue
        if a in passed and b in passed:
            if k["status"] == "open":
                _ask_conflict(ctx, cid, k)
                k["status"] = "asked"
            for x in (a, b):
                marks.setdefault(x, {}).setdefault("conflict", []).append(other[x])
            if k["assumed"] == "a":
                mark(b, assumed_loser=True)
            elif k["assumed"] == "b":
                mark(a, assumed_loser=True)
            else:
                mark(a, fork=True)
                mark(b, fork=True)
    groups: dict[str, list] = {}
    for aid, rec in passed.items():
        srcs, dups = _sources(pool, rec)
        m = marks.get(aid, {})
        v = rec.get("value")
        rank = "primary" if rec.get("pinned") or (v is not None and v >= vprim) else "secondary"
        if m.get("rejected_alt"):
            rank = "secondary"
        is_comp = "composite_type" in rec
        t = rec["composite_type"] if is_comp else rec["type"]
        parts = [A[x] for x in rec["from"] if x in A] if is_comp else []
        entry = {"id": aid, "type": t, "text": rec.get("text", ""), "rank": rank, "value": v,
                 "date": max([p.get("date") or "" for p in parts] or [""]) if is_comp else rec.get("date"),
                 "sources": srcs, "dups": dups}
        if is_comp:
            entry["parts"] = [{"id": p["id"], "type": p["type"], "text": p["text"]} for p in parts]
            if rec.get("status") == "needs_review":
                entry["review"] = True
        for flag in ("conflict", "assumed_loser", "fork", "rejected_alt"):
            if m.get(flag):
                entry[flag] = m[flag]
        if rec.get("pinned"):
            entry["pinned"] = True
        groups.setdefault(t, []).append(entry)
    order = priority(w)
    out_groups = []
    for t in order + sorted(set(groups) - set(order)):
        if t in groups:
            items = sorted(groups[t], key=lambda x: (x["rank"] != "primary", -(x["value"] or 0), x.get("date") or "", x["id"]))
            out_groups.append({"type": t, "items": items})
    prev = w.base(cid)
    base = {"type": "synthesis_base", "container_id": cid, "container": node.title, "built": U.now_iso(),
            "groups": out_groups, "excluded": excluded, "manual_conflicts": manual_conflicts(ctx, cid),
            "needs_review": False, "review_reason": None, "thresholds": {"value_min": vmin, "value_primary": vprim}}
    if prev:
        U.write_json(w.p.bases / f"{cid}.prev.json", prev)
    w.save_base(cid, base)
    ctx.ver.snapshot(ctx.ver.key_base(cid), base_text(w, cid))
    n_items = sum(len(g["items"]) for g in out_groups)
    n_prim = sum(1 for g in out_groups for x in g["items"] if x["rank"] == "primary")
    ctx.logs.change("программа", f"собрана база синтеза [[{node.title}]]: элементов {n_items}, первостепенных {n_prim}, "
                                  f"ниже порога ценности {len(excluded)}")
    ctx.count("bases")
    w.save_pool(cid)
    w.state["dirty"][cid]["stage"] = "compare" if prev else "done"
    if not prev:
        _finish(ctx, cid)


def _ask_conflict(ctx, cid, k):
    w = ctx.w
    pool = w.pool(cid)
    a, b = pool["aspects"][k["a"]], pool["aspects"][k["b"]]

    def src(x):
        e = w.entities.get(x["source_entity"])
        return f"[[{e.title}]]" if e else x["source_entity"]
    guess = {"a": "верно первое", "b": "верно второе", "both": "это развилка, оба направления живы"}[k["assumed"]]
    ctx.q.add("conflict", "Противоречие между мыслями",
              f"Контейнер [[{w.nodes[cid].title}]], {type_title(w, k['type']).lower()}: два утверждения не могут быть верны одновременно.\n\n"
              f"1. «{a['text']}» — {src(a)}, {U.ru_date(a.get('date'))}\n2. «{b['text']}» — {src(b)}, {U.ru_date(b.get('date'))}\n\n"
              f"{k.get('reasoning') or ''}\n\nПока вы не ответили, база синтеза исходит из предположения: {guess}"
              + (f" ({k['assumption']})" if k.get("assumption") else "") + ".",
              options=[{"label": "Верно первое", "value": "a"}, {"label": "Верно второе", "value": "b"},
                       {"label": "Оба верны — это развилка (ветвление: держать оба направления)", "value": "both"},
                       {"label": "Это не противоречие", "value": "none"}],
              data={"container": cid, "key": k["key"]}, dedup=f"conflict:{cid}:{k['key']}", ref=k.get("ref"))


# ---------- 9. сравнение с прежней версией ----------
def _explain(ctx, pool, aid, cur_items) -> str | None:
    rec = pool["composites"].get(aid) or pool["aspects"].get(aid)
    if rec is None:
        return "запись перенесена в другой контейнер"
    if rec.get("status") == "outdated":
        return "устарел или распущен"
    if rec.get("duplicate_of"):
        return "связан как дубль"
    if rec.get("status") == "in_composite":
        own = _owner(pool, aid)
        return "вошёл в составной" if own in cur_items or own else None
    if aid in pool["accepted_losses"]:
        return "потеря признана намеренной"
    return None


def compare(ctx, cid):
    w = ctx.w
    pool = _pool(w, cid)
    prev = U.read_json(w.p.bases / f"{cid}.prev.json", None) or {}
    cur = w.base(cid) or {}
    p_items = {x["id"]: x for g in prev.get("groups", []) for x in g["items"]}
    c_items = {x["id"]: x for g in cur.get("groups", []) for x in g["items"]}
    lost = []
    for aid, it in p_items.items():
        if aid not in c_items:
            if _explain(ctx, pool, aid, c_items):
                continue
            rec = pool["composites"].get(aid) or pool["aspects"].get(aid) or {}
            lost.append({"id": aid, "type": it["type"], "text": it["text"], "was": it["rank"], "now": "выпал из базы",
                         "value_now": rec.get("value")})
        elif it["rank"] == "primary" and c_items[aid]["rank"] == "secondary":
            if c_items[aid].get("rejected_alt") or aid in pool["accepted_losses"]:
                continue
            lost.append({"id": aid, "type": it["type"], "text": it["text"], "was": "primary", "now": "стал второстепенным",
                         "value_now": c_items[aid].get("value")})
    if lost:
        ids = [x["id"] for x in lost]

        def check(o):
            ls = o.get("losses")
            if not isinstance(ls, list):
                return ["нет списка losses"]
            got = {x.get("id") for x in ls if isinstance(x, dict) and isinstance(x.get("significant"), bool)}
            miss = [i for i in ids if i not in got]
            return [f"нет решения (significant true/false) для: {', '.join(miss)}"] if miss else []
        acc = [pool["aspects"].get(i, pool["composites"].get(i, {})).get("text", i) for i in pool["accepted_losses"]]
        obj = ctx.llm.json("Сравнение версий", {
            "object_kind": "base", "container": container_info(w, cid), "accepted_losses": acc or "нет",
            "material": {"выпавшие_элементы": lost, "база_сейчас": base_text(w, cid)},
        }, validate=check, subject=f"база синтеза [[{w.nodes[cid].title}]]")
        by_id = {x["id"]: x for x in lost}
        for x in obj["losses"]:
            if x.get("id") not in by_id:
                continue
            it = by_id[x["id"]]
            ref = ctx.logs.reflect("base_loss", f"{cid}:{x['id']}", bool(x["significant"]))
            if x["significant"]:
                ctx.q.add("base_loss", "Из базы синтеза выпало важное?",
                          f"В [[{w.nodes[cid].title}]] элемент {it['now']}: «{it['text']}» (ценность сейчас {it.get('value_now')}).\n\n"
                          f"Модель считает потерю значимой: {x.get('reasoning') or ''}",
                          options=[{"label": "Так и нужно — потеря намеренная", "value": "keep"},
                                   {"label": "Вернуть в базу как первостепенное", "value": "restore"}],
                          data={"container": cid, "aspect": x["id"]}, dedup=f"baseloss:{cid}:{x['id']}", ref=ref)
                cur["needs_review"] = True
                cur["review_reason"] = "значимая потеря по сравнению с предыдущей версией"
                ctx.count("base_losses")
        if cur.get("needs_review"):
            w.save_base(cid, cur)
    _finish(ctx, cid)


def _finish(ctx, cid):
    w = ctx.w
    w.state["dirty"].pop(cid, None)
    index_container(ctx, cid)

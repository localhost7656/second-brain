"""Фаза 1 целиком (раздел 6): ответы → ручные правки → приём файлов → Bootstrap/классификация → конвейер записей → базы синтеза."""
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


# ---------- ручные правки организационных полей (раздел 3.6) ----------
def detect_manual_edits(ctx):
    w = ctx.w
    st = w.state
    # контейнеры, заведённые вручную: заметка с type, но без id
    for md, fm, body in list(getattr(w, "adoptable", [])):
        node = w.adopt_node(md, fm, body)
        if node:
            par = w.parent_of(node)
            ctx.logs.change("пользователь", f"создан контейнер [[{node.title}]] — {TYPE_RU.get(node.type, node.type)}"
                            + (f" внутри [[{par.title}]]" if par else ""))
            index_container(ctx, node.id)
            ctx.count("containers_created")
    w.adoptable = []
    # узлы: тип, родитель, связи
    for n in list(w.nodes.values()):
        t = RU_TYPE.get(str(n.fm.get("type", "")).strip().lower())
        if t is None:
            w.warnings.append(f"В контейнере [[{n.title}]] непонятный type «{n.fm.get('type')}» — нужен проект, росток или вопрос; "
                              "пока считаю проектом.")
            t = "project"
        raw_cs = n.fm.get("container_status")
        cs = CONTAINER_STATUS.get(str(raw_cs or "active").strip().lower())
        if cs is None:
            w.warnings.append(f"В контейнере [[{n.title}]] непонятный container_status «{raw_cs}» — нужен active, dormant или completed; "
                              "оставлен active.")
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
                    w.warnings.append(f"В контейнере [[{n.title}]] указан родитель «{ref}», такого контейнера нет — оставлен прежний.")
            elif p.id != pid:
                old = w.nodes[pid].title if pid in w.nodes else "верхний уровень"
                w.move_node(n, p.id)
                ctx.logs.change("пользователь", f"[[{n.title}]] перенесён: {old} → [[{p.title}]]")
        elif pid and not raw_parent:
            w.move_node(n, None)
            ctx.logs.change("пользователь", f"[[{n.title}]] перенесён на верхний уровень")
        refs = [U.unlink(v) for v in U.as_list(n.fm.get("applies_to"))]
        ids, bad = [], []
        for r in refs:
            m = w.node_by_title(r) if r else None
            if m and m.id != n.id:
                ids.append(m.id)
            elif r:
                bad.append(r)
        if bad:
            w.warnings.append(f"В [[{n.title}]] в applies_to не найдены: {', '.join(bad)}.")
        elif set(ids) != set(n.fm.get("applies_to_ids") or []):
            w.set_applies_to(n, ids)
            w.save_node(n)
            ctx.logs.change("пользователь", f"[[{n.title}]]: связи applies_to изменены")
    w.normalize_folders()
    # записи: контейнер, also_in, текст, статус, conflicts_with
    for e in list(w.entities.values()):
        if e.container_id and e.container_id not in w.nodes:
            w.warnings.append(f"Контейнер записи [[{e.title}]] удалён — запись перенесена в _unsorted.")
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
                    w.warnings.append(f"В записи [[{e.title}]] указан контейнер «{ref}», такого нет — оставлен прежний.")
            elif n.id != cur:
                target = n.id
        elif cur and not raw:
            target = None
        if target != cur:
            cls = st["cls"].get(e.id, {})
            answers.place_entity(ctx, e, target, "пользователь", "классификация оспорена правкой YAML")
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
            w.warnings.append(f"В записи [[{e.title}]] в also_in не найдены: {', '.join(bad)}.")
        else:
            for cid in want:
                if cid not in e.also_in_ids:
                    ops.add_also_in(ctx, e, cid, "пользователь")
            for cid in list(e.also_in_ids):
                if cid not in want:
                    ops.remove_also_in(ctx, e, cid, "пользователь")
        h = U.sha1(e.text)
        old = st["text_hash"].get(e.id)
        if old and h != old:
            if ops.stage(ctx, e.id) == "done":
                ctx.q.add("text_changed", "Изменён текст обработанной записи",
                          f"Текст записи [[{e.title}]] изменён вручную. Обработанные записи напрямую не правятся: "
                          "иначе ссылки на неё и извлечённые аспекты разойдутся с текстом. Пока вы не ответили, программа работает с прежним текстом.",
                          options=[{"label": "Сделать из правки новую запись (в _staging), а исходный текст вернуть", "value": "new"},
                                   {"label": "Просто вернуть исходный текст", "value": "restore"}],
                          data={"entity": e.id}, dedup=f"text:{e.id}")
            else:
                st["text_hash"][e.id] = h
                ctx.logs.change("пользователь", f"текст [[{e.title}]] поправлен до окончания обработки")
        raw_st = e.fm.get("status")
        if raw_st not in ("processed", "outdated", "draft", None):
            norm = ENTITY_STATUS.get(str(raw_st).strip().lower())
            if norm:
                e.fm["status"] = norm
                w.save_entity(e)
            else:
                w.warnings.append(f"В записи [[{e.title}]] непонятный status «{raw_st}» — нужен outdated (устарела) или processed.")
        uo = st.setdefault("user_outdated", {})
        if e.fm.get("status") == "outdated" and not uo.get(e.id) and not st.get("auto_outdated", {}).get(e.id):
            for cid in [e.container_id] + e.also_in_ids:
                if cid in w.nodes:
                    for a in list(w.pool(cid)["aspects"].values()):
                        if a["source_entity"] == e.id and a.get("status") != "outdated":
                            answers.outdate_aspect(ctx, cid, a["id"], None, "entity")
            uo[e.id] = True
            ctx.logs.change("пользователь", f"[[{e.title}]] отмечена устаревшей")
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
            ctx.logs.change("пользователь", f"[[{e.title}]] снова актуальна")
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


# ---------- ручные правки продуктов (раздел 8.5) ----------
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
                 f"Ручная правка документа [[{w.path_key(node)}/{title}|{title}]] контейнера [[{node.title}]].", ""]
        if added:
            lines += ["Автор добавил или переписал:", ""] + added + [""]
        if removed:
            lines += ["Автор убрал:", ""] + removed + [""]
        p = U.unique_path(w.p.staging, U.safe_name(f"правка документа — {title} ({node.title})", 100), ".txt")
        U.atomic_write_text(p, "\n".join(lines))
        ctx.ver.snapshot(key, body)
        ctx.logs.change("пользователь", f"ручная правка [[{w.path_key(node)}/{title}|{title}]] ({node.title}) принята как новая запись")
        n += 1
    if n:
        ctx.say(f"Найдены ручные правки документов: {n} — оформлены новыми записями.")
    return n


# ---------- приём файлов (раздел 4) ----------
def ingest(ctx):
    w = ctx.w
    items = w.state["items"]
    staging = w.p.staging
    by_sha = {(it.get("sha"), it.get("staging")): it for it in items.values() if it.get("sha")}
    other = [p for p in staging.rglob("*") if p.is_file() and p.suffix.lower() not in INPUT_EXT
             and not p.name.startswith((".", "~"))]
    if other:
        ctx.notices.append("В _staging есть файлы, которые программа пока не читает (нужен .txt или .md): "
                           + ", ".join(p.name for p in other[:10]) + (" …" if len(other) > 10 else ""))
    um, am = ctx.cfg.markers()
    n = 0
    for p in scan_staging(staging):
        rel = p.relative_to(staging)
        raw = p.read_bytes()
        sha = hashlib.sha1(raw).hexdigest()
        if (sha, rel.as_posix()) in by_sha:  # уже принят, но не удалён из-за сбоя
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
        stem = p.stem if re.match(r"^\d{4}-\d{2}-\d{2}\b", p.stem) else f"{date} {p.stem}"  # без двойной даты
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
                ctx.notices.append(f"Файл «{p.name}» пустой — сохранён в _исходники, обрабатывать нечего.")
            items[iid] = item
        ctx.checkpoint()
        try:
            U.retry_fs(p.unlink)
        except OSError as e:
            w.warnings.append(f"Не удалось убрать «{rel}» из _staging: {e}. Удалите файл вручную, повторно он не обработается.")
        split = (f"; дневник разделён по датам: {len(parts)} записей ({parts[0]['label']} — {parts[-1]['label']})"
                 if parts else "")
        ctx.logs.change("программа", f"принят файл «{rel.as_posix()}» → _исходники ({source}, {U.ru_date(date)}, {enc}"
                        + (", массовая загрузка" if mode == "bootstrap" else "") + ")" + split)
        if parts:
            ctx.say(f"«{p.name}»: дневник разделён по датам — {len(parts)} записей ({parts[0]['label']} — {parts[-1]['label']}).")
        n += 1
    for d in sorted([d for d in staging.rglob("*") if d.is_dir()], key=lambda x: -len(x.parts)):
        if d != w.p.staging_archive:
            try:
                d.rmdir()  # только пустые
            except OSError:
                pass
    if n:
        ctx.count("files", n)
        ctx.say(f"Принято файлов: {n}.")
    return n


def pass1(ctx):
    w = ctx.w
    new = [it for it in w.state["items"].values() if it.get("stage") == "new"]
    if not new:
        return False
    new.sort(key=lambda i: (i["date"], i["id"]))
    ctx.say(f"Массовая загрузка: {len(new)} файлов — строю черновик структуры (проход 1).")
    generate_draft(ctx, new)
    ctx.checkpoint()
    ctx.say("Черновик структуры готов: откройте «_структура (черновик).md», поправьте и отметьте «Структура утверждена».")
    return True


def classify_ready(ctx):
    w = ctx.w
    ready = [it for it in w.state["items"].values() if it.get("stage") == "ready"]
    ready.sort(key=lambda i: (i["date"], i["id"]))
    for i, it in enumerate(ready, 1):
        print(f"  [{i}/{len(ready)}] {it['name']}", flush=True)
        ctx.progress("Разбор файлов", i, len(ready), it["name"], echo=False)
        classify_item(ctx, it)
        ctx.checkpoint()
        if it.get("entities"):
            pipeline.run_all(ctx, only=it["entities"])


# ---------- «тихая смерть» ростков (раздел 3.3) ----------
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
            ctx.q.add("dormant", "Росток давно не развивался",
                      f"Росток [[{n.title}]] не получал новых мыслей с {U.ru_date(lm)} (больше {days} дней). Он ещё актуален?",
                      options=[{"label": "Актуален — оставить ростком", "value": "active"},
                               {"label": "Заморозить (dormant)", "value": "dormant"},
                               {"label": "Завершён (completed)", "value": "completed"}],
                      data={"container": n.id}, dedup=f"dormant:{n.id}:{lm[:10]}")

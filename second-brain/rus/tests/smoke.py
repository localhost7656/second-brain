"""Сквозная проверка программы с тестовой моделью (llm.mode: fake, embeddings.mode: fake).
Запуск: python tests/smoke.py [папка]  — по умолчанию во временной папке."""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from brain.cli import main  # noqa: E402

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="brain-smoke-"))
V = ROOT / "vault"
SETTINGS = ROOT / "settings.yaml"
LOG = []


def write_settings(llm_mode="fake", emb_model="fake-1", extra="estimate:\n  enabled: false\n"):
    """Настройки в формате v2.4 (llm.model и т.п.) — программа сама переводит их в профили.
    Оценка большого запуска выключена: её проверяет шаг 15 (и тест не должен ждать ответа в консоли)."""
    SETTINGS.write_text(f"""vault: "{V.as_posix()}"
llm:
  mode: {llm_mode}
  model: "fake"
  fake_module: "{(APP / 'tests' / 'fake_llm.py').as_posix()}"
embeddings:
  mode: fake
  model: "{emb_model}"
""" + extra, encoding="utf-8")


def run(*args, expect=0):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(["--settings", str(SETTINGS)] + list(args))
    out = buf.getvalue()
    LOG.append(f"$ brain {' '.join(args)}\n{out}")
    if code != expect:
        print(out)
        raise AssertionError(f"brain {' '.join(args)}: код {code}, ожидался {expect}")
    return out


def qs() -> dict:
    p = V / ".system" / "questions.json"
    return json.loads(p.read_text(encoding="utf-8"))["open"] if p.exists() else {}


def qn(q):
    return int(q["id"][1:])


def find_q(kind, where=None):
    c = [q for q in qs().values() if q["kind"] == kind and (where is None or where(q))]
    return sorted(c, key=qn)


def answer(kind, pick=None, text=None, where=None):
    """Отметить вариант (номер или часть подписи) и/или вписать ответ — как это сделал бы человек в Obsidian."""
    c = find_q(kind, where)
    assert c, f"нет открытого вопроса вида {kind}"
    q = c[0]
    md = (V / "open-questions.md").read_text(encoding="utf-8")
    lines = md.split("\n")
    s = next(i for i, l in enumerate(lines) if l.startswith(f"## {q['id']} "))
    e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith("## Q")), len(lines))
    k = -1
    done_pick = pick is None
    for i in range(s, e):
        if lines[i].startswith("- [ ] "):
            k += 1
            label = lines[i][6:]
            if pick is not None and ((isinstance(pick, int) and k == pick) or (isinstance(pick, str) and pick.lower() in label.lower())):
                lines[i] = "- [x] " + label  # латинская x
                done_pick = True
                pick = None
        if text is not None and lines[i].startswith("Ответ:"):
            lines[i] = "Ответ: " + text
            text = None
    assert done_pick, f"в вопросе {q['id']} нет варианта {pick}"
    assert text is None, f"в вопросе {q['id']} нет строки «Ответ:»"
    (V / "open-questions.md").write_text("\n".join(lines), encoding="utf-8")
    return q


def state():
    return json.loads((V / ".system" / "state.json").read_text(encoding="utf-8"))


def pool(title):
    st = state()
    node = node_by_title(title)
    return json.loads((V / ".system" / "data" / "pools" / f"{node['id']}.json").read_text(encoding="utf-8"))


def base(title):
    node = node_by_title(title)
    return json.loads((V / ".system" / "data" / "bases" / f"{node['id']}.json").read_text(encoding="utf-8"))


def node_by_title(title):
    import yaml
    for p in V.rglob(f"{title}.md"):
        raw = p.read_text(encoding="utf-8")
        fm = yaml.safe_load(raw.split("---")[1])
        if fm.get("type") in ("project", "seed", "question"):
            fm["_path"] = p
            return fm
    raise AssertionError(f"нет контейнера {title}")


def entity_files():
    import yaml
    out = []
    for p in V.rglob("*.md"):
        if ".system" in p.parts:
            continue
        raw = p.read_text(encoding="utf-8")
        if raw.startswith("---"):
            fm = yaml.safe_load(raw.split("---")[1]) or {}
            if fm.get("type") == "entity":
                out.append((p, fm, raw))
    return out


def entity_by_text(snippet):
    for p, fm, raw in entity_files():
        if snippet.lower() in raw.lower():
            return p, fm, raw
    raise AssertionError(f"нет записи с текстом «{snippet}»")


def step(name):
    print(f"\n=== {name}")


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"  ✓ {msg}")


def set_mtime(p: Path, iso: str):
    import datetime as dt
    t = time.mktime(dt.datetime.fromisoformat(iso).timetuple())
    os.utime(p, (t, t))


def main_test():
    if ROOT.exists() and any(ROOT.iterdir()):
        shutil.rmtree(ROOT)
    V.mkdir(parents=True)
    os.environ["FAKE_LLM_STATE"] = str(ROOT / "fake_state.json")
    os.environ["BRAIN_TEST_WEBCHAT_VARS"] = "1"
    write_settings()

    step("1. Архив: даты, подсказки, диалог, cp1251, пустой файл, картинка")
    arch = V / "_staging" / "архив"
    (arch / "Чат с ИИ").mkdir(parents=True)
    (arch / "дневник 2023.txt").write_bytes((
        "02.04.2023\n\n"
        "Сегодня посадил томаты в теплице на даче. Полив каждый день вечером.\n\n"
        "Огурцы в теплице плохо растут. Наверное, мало света.\n\n"
        "Метеостанцию можно поставить в теплицу на даче — следить за влажностью.\n\n"
        "Приснился странный сон про поезд.\n\n"
        "Тот вариант с поливом по таймеру надо проверить.\n").encode("cp1251"))
    (arch / "Чат с ИИ" / "датчик для метеостанции.txt").write_text(
        "01.06.2023\n"
        "я: Какой датчик взять для метеостанции — проводной или беспроводной?\n"
        "ИИ: Беспроводной удобнее и ставится где угодно, проводной дешевле и не требует батареек. "
        "Если важна цена, проводной выглядит разумнее, но точность нужно проверять на месте.\n"
        "я: Возможно, хватит одного датчика на балконе.\n"
        "ИИ: Для точности лучше два датчика, один на улице, второй в комнате.\n"
        "я: Значит, берём два проводных датчика. Можно крепить датчик на стену.\n"
        "я: А можно крепить датчик под крышей, так он в тени.\n", encoding="utf-8")
    (arch / "пекарня.txt").write_text(
        "\ufeff10.05.2023\n\nДумаю открыть маленькую пекарню у дома. Себестоимость буханки хлеба — 50 рублей.\n\n"
        "Аренда помещения 40 000 рублей в месяц. Мне нравится идея с самообслуживанием.\n", encoding="utf-8")
    (arch / "разное.txt").write_text("Надо бы разобрать старые фотографии на антресоли.\n", encoding="utf-8")
    set_mtime(arch / "разное.txt", "2023-01-15T10:00:00")
    (arch / "мука.txt").write_text("12.05.2023\nhint: это про дачу\n\nПекарь в соседней пекарне сказал, что муку лучше брать у мельницы напрямую.\n", encoding="utf-8")
    (arch / "пусто.txt").write_text("  \n", encoding="utf-8")
    (V / "_staging" / "фото.jpg").write_bytes(b"\xff\xd8\xff")

    out = run("run")
    st = state()
    ok(st["structure"]["pending"], "черновик структуры ждёт утверждения")
    ok((V / "_структура (черновик).md").exists(), "файл черновика создан")
    ok(not list((V / "_staging").rglob("*.txt")), "txt убраны из _staging")
    ok(len(list((V / "_исходники").glob("*.txt"))) == 6, "исходники сохранены без изменений (6 файлов)")
    ok((V / "_исходники" / "2023-04-02 дневник 2023.txt").read_bytes().decode("cp1251").startswith("02.04.2023"), "cp1251-файл скопирован байт в байт")
    ok(any(it["date"] == "2023-01-15" for it in st["items"].values()), "дата без шапки взята из файла")
    ok(any(it["encoding"] == "cp1251" for it in st["items"].values()), "кодировка cp1251 распознана")
    ok(any(it.get("content_type") == "ai_dialogue" for it in st["items"].values()), "диалог с ИИ распознан по разметке")
    ok(any(it.get("hint") == "это про дачу" for it in st["items"].values()), "подсказка hint прочитана")
    ok("фото.jpg" in (V / "open-questions.md").read_text(encoding="utf-8"), "про неподдерживаемый файл сказано")
    ok(not (V / ".system" / "data" / "pools").exists() or not list((V / ".system" / "data" / "pools").glob("*.json")), "до утверждения ничего не разложено")

    step("2. Правка и утверждение черновика")
    d = (V / "_структура (черновик).md").read_text(encoding="utf-8")
    ok("Метеостанция (проект)" in d and "Пекарня (росток)" in d, "в черновике есть Метеостанция и Пекарня")
    d = d.replace("- Дача (проект)", "- Дача и сад (проект)")
    d = d.replace("## Дерево\n\n", "## Дерево\n\n- Здоровье (росток) — сон и самочувствие\n")
    run("run")
    ok(state()["structure"]["pending"], "без галочки черновик не применяется")
    d = d.replace("- [ ] Структура утверждена", "- [х] Структура утверждена")  # кириллическая х
    (V / "_структура (черновик).md").write_text(d, encoding="utf-8")
    out = run("run")
    ok(not state()["structure"]["pending"], "структура утверждена (кириллическая «х» сработала)")
    for t in ("Технологии", "Метеостанция", "Пекарня", "Дача и сад", "Здоровье"):
        node_by_title(t)
    ok(node_by_title("Метеостанция")["_path"].parent.parent.name == "Технологии", "Метеостанция вложена в Технологии")
    ok(node_by_title("Пекарня")["type"] == "seed", "тип «росток» применён")
    ok(node_by_title("Метеостанция")["applies_to"] == ["[[Дача и сад]]"], "applies_to перенесён из черновика с новым названием")

    step("3. Раскладка, вопросы, аспекты, базы")
    ents = entity_files()
    ok(len(ents) == 8, f"создано 8 записей (сегменты дневника + остальные): {len(ents)}")
    p, fm, raw = entity_by_text("старые фотографии")
    ok(fm["quarantine"] and "_на_проверку" in p.parts, "неясная запись — в карантине")
    p, fm, raw = entity_by_text("мельницы")
    ok(fm["quarantine"] and fm["review_reason"] == "user_hint_mismatch", "подсказка расходится с содержанием → карантин")
    p, fm, raw = entity_by_text("томаты")
    ok(fm["container"] == "[[Дача и сад]]" and fm["segment"] == "1-2", "сегмент дневника 1-2 → Дача и сад")
    p, fm, raw = entity_by_text("Тот вариант")
    ok(fm["incomplete"] and not find_q("clarify", lambda q: q["data"]["entity"] == fm["id"]), "в Bootstrap неполная запись без вопросов")
    p, fm, raw = entity_by_text("проводной или беспроводной")
    ok(fm["compacted"] and "Уплотнённая версия" in raw, "диалог уплотнён, исходный текст на месте")
    ok(fm["status"] == "processed" and fm["aspect_ids"], "диалог обработан, есть ссылки на аспекты")
    ok(find_q("classify") and find_q("clarify") and find_q("also_in") and find_q("conflict") and find_q("structure_sub"),
       "вопросы: классификация, уточнение, общая запись, противоречие, под-контейнер")
    pv = pool("Метеостанция")
    ok(any(c["composite_type"] == "resolved_decision" for c in pv["composites"].values()), "собран составной «обоснованное решение»")
    ok(pv["conflicts"] and pv["conflicts"][0]["status"] == "asked", "противоречие поднято после фильтра")
    b = base("Метеостанция")
    ok(b["groups"][0]["type"] == "resolved_decision", "группы базы — по таблице приоритета")
    ok(any(it.get("assumed_loser") for g in b["groups"] for it in g["items"]), "оптимистичное предположение отмечено в базе")
    bk = base("Пекарня")
    ok(bk["excluded"], "оценка ниже порога ценности не попала в базу")
    ok((node_by_title("Метеостанция")["_path"].parent / "_аспекты.md").exists(), "витрина пула создана")
    ok("Только для чтения" in (node_by_title("Метеостанция")["_path"].parent / "_база синтеза.md").read_text(encoding="utf-8"), "витрина базы — только чтение")
    logs = V / "_логи"
    ok(any(logs.glob("рассуждения *.md")) and any(logs.glob("изменения *.md")), "логи изменений и рассуждений ведутся")
    refl = (V / ".system" / "reflection.jsonl").read_text(encoding="utf-8")
    ok('"kind": "classification"' in refl and '"kind": "compaction"' in refl, "лог рефлексии пишется")
    ok((V / ".obsidian" / "snippets" / "vtoroy-mozg.css").exists(), "CSS цветов создан")

    step("4. Ответы на вопросы и правка YAML («оспорить классификацию»)")
    answer("classify", text="Быт (росток)", where=lambda q: "фотографии" in q["text"])
    answer("clarify", text="Фото с дачи 2010 года, хочу оцифровать", where=lambda q: not q.get("options"))
    answer("clarify", pick=0, where=lambda q: bool(q.get("options")))
    answer("classify", pick="Пекарня", where=lambda q: "мельницы" in q["text"] or "муку" in q["text"].lower())
    answer("also_in", pick=0)
    answer("conflict", pick="развилка")
    answer("structure_sub", pick=0)
    p, fm, raw = entity_by_text("сон про поезд")
    p.write_text(raw.replace("container: '[[Здоровье]]'", "container: '[[Дача и сад]]'"), encoding="utf-8")
    out = run("run")
    ok("Принято ответов: 7" in out, "принято 7 ответов")
    node_by_title("Быт")
    ok(node_by_title("Быт")["type"] == "seed", "свободный ответ создал контейнер нужного типа")
    p, fm, raw = entity_by_text("на антресоли.")
    ok(fm["container"] == "[[Быт]]" and not fm["quarantine"] and fm["status"] == "processed", "запись из карантина разложена и обработана")
    p, fm, raw = entity_by_text("Фото с дачи 2010")
    ok("Уточнение к записи [[" in raw, "ответ на уточнение стал новой записью со ссылкой на исходную")
    p, fm, raw = entity_by_text("Метеостанцию можно поставить")
    ok("_shared" in p.parts and fm["shared"] and fm["also_in"], "общая запись перенесена в _shared")
    ok("Общие записи" in node_by_title("Дача и сад")["_path"].read_text(encoding="utf-8"), "в файле контейнера есть ссылки на общие записи")
    tep = node_by_title("Теплица")
    ok(tep["parent"] == "[[Дача и сад]]", "под-контейнер Теплица создан внутри Дача и сад")
    p, fm, raw = entity_by_text("томаты")
    ok(fm["container"] == "[[Теплица]]" and "Теплица" in p.parts, "запись переехала в под-контейнер вместе с папкой")
    ok(any(a["source_entity"] == fm["id"] for a in pool("Теплица")["aspects"].values()), "аспекты переехали в пул под-контейнера")
    p, fm, raw = entity_by_text("сон про поезд")
    ok(fm["container"] == "[[Дача и сад]]" and not any(a["source_entity"] == fm["id"] for a in pool("Здоровье")["aspects"].values()),
       "правка container в YAML перенесла запись и её аспекты")
    pv = pool("Метеостанция")
    ok(pv["conflicts"][0]["status"] == "resolved" and pv["conflicts"][0]["decision"] == "both", "развилка записана")
    ok(any(it.get("fork") for g in base("Метеостанция")["groups"] for it in g["items"]), "база пересчитана: оба направления — развилка")
    arch_q = (V / "_логи" / "архив вопросов.md").read_text(encoding="utf-8")
    ok(arch_q.count("**Ответ:**") >= 7, "отвеченные вопросы ушли в архив")
    ok('"type": "decision"' in (V / ".system" / "reflection.jsonl").read_text(encoding="utf-8"), "решения пользователя — в логе рефлексии")

    step("5. Новая мысль «пересчитал: 100 рублей» → устаревание")
    (V / "_staging" / "пересчёт.txt").write_text("15.06.2023\nhint: пекарня\n\nПересчитал: себестоимость буханки хлеба минимум 100 рублей, с учётом аренды и зарплаты пекаря.\n", encoding="utf-8")
    out = run("run")
    q = find_q("outdated")
    ok(q and "50 рублей" in q[0]["text"] and "100 рублей" in q[0]["text"], "предложено пометить старое устаревшим")
    ok(find_q("base_loss"), "выпавший из базы важный элемент → вопрос о потере")
    answer("outdated", pick=0)
    answer("base_loss", pick="Вернуть")
    out = run("run")
    pk = pool("Пекарня")
    old = [a for a in pk["aspects"].values() if "50 рублей" in a["text"]]
    ok(old and old[0]["status"] == "outdated" and old[0]["replaced_by"], "старый аспект устарел, не удалён")
    texts = [it["text"] for g in base("Пекарня")["groups"] for it in g["items"]]
    ok(not any("50 рублей" in t for t in texts) and any("100 рублей" in t for t in texts), "база синтеза пересобрана с новым значением")
    ok(any(it.get("pinned") and it["rank"] == "primary" for g in base("Пекарня")["groups"] for it in g["items"]), "возвращённый элемент закреплён")
    p, fm, raw = entity_by_text("Себестоимость буханки хлеба — 50")
    ok("Себестоимость буханки хлеба — 50 рублей" in raw, "старая мысль осталась нетронутой")

    step("6. Фаза 2: синтез, версии")
    out = run("synth", "Пекарня")
    kf = node_by_title("Пекарня")["_path"].parent
    ok((kf / "Сводный файл.md").exists(), "сводный файл создан")
    ok((kf / "Дневник.md").exists(), "дополнительный документ (Дневник) создан")
    import yaml
    sfm = yaml.safe_load((kf / "Сводный файл.md").read_text(encoding="utf-8").split("---")[1])
    ok(sfm["type"] == "product" and sfm["product_kind"] == "summary" and sfm["based_on_synthesis"], "YAML документа по разделу 16.5")
    ok((V / ".system" / "versions" / ".git").exists(), "история версий в git")
    out = run("synth", "Пекарня")
    ok("Нового ничего не было" in out or "Документы" in out, "повторный синтез отработал")

    step("7. Ручная правка продукта → новая запись → пересборка")
    sf = kf / "Сводный файл.md"
    sf.write_text(sf.read_text(encoding="utf-8") + "\nПримечание автора: открыть летом 2024 года, бюджет 500 000 рублей.\n", encoding="utf-8")
    out = run("run")
    ok("ручные правки документов: 1" in out.lower(), "правка документа замечена")
    p, fm, raw = entity_by_text("бюджет 500 000")
    ok(fm["content_type"] == "product_edit" and fm["container"] == "[[Пекарня]]", "правка стала записью Пекарни")
    out = run("synth", "Пекарня")
    ok("Примечание автора" in sf.read_text(encoding="utf-8"), "ручная правка сохранилась в новой версии")
    lq = find_q("product_loss")
    ok(lq, "пропавшее в новой версии документа → вопрос")
    answer("product_loss", pick="Откатить", where=lambda q: q["id"] == lq[0]["id"])
    for x in lq[1:]:
        answer("product_loss", pick="намеренная", where=lambda q, x=x: q["id"] == x["id"])
    out = run("run")
    ok("Подробности" in sf.read_text(encoding="utf-8"), "документ откатан к прежней версии")
    out = run("run")
    ok("ручные правки" not in out.lower(), "откат не считается ручной правкой")

    step("8. Правка текста обработанной записи, простой ростка, сбой посреди прогона")
    p, fm, raw = entity_by_text("Мне нравится идея")
    p.write_text(raw.replace("Мне нравится идея", "Мне очень нравится идея"), encoding="utf-8")
    hp = node_by_title("Здоровье")["_path"]
    hp.write_text(hp.read_text(encoding="utf-8").replace(f"last_modified: '{time.strftime('%Y-%m-%d')}'", "last_modified: '2020-01-01'")
                  .replace(f"last_modified: {time.strftime('%Y-%m-%d')}", "last_modified: 2020-01-01"), encoding="utf-8")
    out = run("run")
    ok(find_q("text_changed"), "изменение текста обработанной записи замечено")
    ok(find_q("dormant"), "простой ростка → вопрос об актуальности")
    answer("text_changed", pick="новую запись")
    answer("dormant", pick="Заморозить")
    (V / "_staging" / "дача полив.txt").write_text("20.06.2023\n\nПолив по таймеру на даче работает отлично, огурцы пошли в рост.\n", encoding="utf-8")
    os.environ["FAKE_CRASH_ON"] = "Ценность"
    out = run("run", expect=2)
    ok("Непредвиденная ошибка" in out and (V / "_логи" / "ошибки.log").exists(), "сбой: понятное сообщение и лог")
    del os.environ["FAKE_CRASH_ON"]
    out = run("run")
    p, fm, raw = entity_by_text("Мне нравится идея")
    ok("очень" not in raw, "исходный текст возвращён")
    entity_by_text("Мне очень нравится")  # правка стала новой записью
    ok(node_by_title("Здоровье")["container_status"] == "dormant", "росток заморожен")
    ok(not state()["dirty"], "после сбоя прогон продолжен и доведён до конца")

    step("9. Смена модели эмбеддингов → пересчёт векторов")
    write_settings(emb_model="fake-2")
    out = run("run")
    ok("Модель эмбеддингов сменилась" in out, "предупреждение о пересчёте")
    meta = json.loads((V / ".system" / "vectors" / "meta.json").read_text(encoding="utf-8"))
    ok(meta["model"] == "fake:fake-2", "векторы пересчитаны под новую модель")

    step("10. Ручной режим через веб-чат")
    write_settings(llm_mode="webchat", emb_model="fake-2")
    (V / "_staging" / "дача урожай.txt").write_text("25.06.2023\n\nСобрал первые огурцы на даче, теплица окупилась.\n", encoding="utf-8")
    out = run("run")
    ok("Остановлено до ответа из веб-чата" in out, "прогон остановился и ждёт ответа")
    idx = json.loads((V / ".system" / "webchat.json").read_text(encoding="utf-8"))
    rec = list(idx["pending"].values())[0]
    (V / "_веб-чат" / rec["ans"]).write_text("не json вовсе", encoding="utf-8")
    out = run("run")
    ok("не прошёл проверку" in (V / "_веб-чат" / rec["req"]).read_text(encoding="utf-8"), "ошибка формата — просьба переспросить в файле запроса")
    sys.path.insert(0, str(APP / "tests"))
    import fake_llm
    rounds = 0
    while True:
        idx = json.loads((V / ".system" / "webchat.json").read_text(encoding="utf-8"))
        if not idx["pending"]:
            break
        for h, rec in idx["pending"].items():
            vars_ = json.loads((V / ".system" / "webchat_vars" / f"{rec['n']:03d}.json").read_text(encoding="utf-8"))
            ans = fake_llm.respond(vars_["prompt"], vars_["variables"], [{"role": "user", "content": ""}], 0)
            (V / "_веб-чат" / rec["ans"]).write_text(ans, encoding="utf-8")
        out = run("run")
        rounds += 1
        assert rounds < 20, "веб-чат не сходится"
    entity_by_text("Собрал первые огурцы")
    ok(rounds >= 2 and "Готово" in out, f"ручной режим довёл прогон до конца за {rounds} обменов")
    ok(len(list((V / "_веб-чат" / "готово").glob("*.md"))) >= 4, "обработанные запросы и ответы — в папке «готово»")

    step("11. Повторный прогон без нового — без обращений к модели")
    write_settings(emb_model="fake-2")
    before = (V / ".system" / "usage.jsonl").read_text(encoding="utf-8").count("\n")
    out = run("run")
    after = (V / ".system" / "usage.jsonl").read_text(encoding="utf-8").count("\n")
    ok(after == before and "Нового ничего не было" in out, "пустой прогон ничего не тратит")

    step("12. Прочие команды")
    out = run("status")
    ok("Контейнеров:" in out, "status")
    out = run("check")
    ok("Всё в порядке" in out, "check")
    out = run("revalidate", "Пекарня", "--yes")
    ok("Ревалидация закончена" in out, "revalidate")
    out = run("patterns")
    ok("составн" in out, "patterns")
    out = run("synth", "Нет такого", expect=1)
    ok("не найден" in out, "понятная ошибка для неизвестного контейнера")

    step("13. Ручные правки: тип по-русски и контейнеры, заведённые вручную")
    import yaml
    b = node_by_title("Быт")
    unsorted_before = len(list((V / "_unsorted").glob("*.md")))
    raw = b["_path"].read_text(encoding="utf-8")
    b["_path"].write_text(raw.replace(f"type: {b['type']}", "type: Проект", 1), encoding="utf-8")
    (V / "Ремонт.md").write_text("---\ntype: проект\n---\n\nРемонт квартиры: кухня и ванная.\n", encoding="utf-8")
    bak = node_by_title("Пекарня")
    (bak["_path"].parent / "Меню.md").write_text("---\ntype: росток\ndescription: Что продавать\n---\n", encoding="utf-8")
    (V / "Путешествия").mkdir()
    (V / "Путешествия" / "Путешествия.md").write_text("---\ntype: вопрос\n---\n\nКуда поехать летом?\n", encoding="utf-8")
    (V / "Разное").mkdir()
    (V / "Разное" / "Быт.md").write_text("---\ntype: проект\n---\n", encoding="utf-8")
    photo = b["_path"].parent / "_записи" / "2023-01-15 Надо бы разобрать старые фотографии на антресоли.md"
    raw = photo.read_text(encoding="utf-8")
    photo.write_text(raw.replace("status: processed", "status: Устарела", 1), encoding="utf-8")
    out = run("run")
    ok("status: outdated" in photo.read_text(encoding="utf-8")
       and all(a["status"] == "outdated" for a in pool("Быт")["aspects"].values() if a["source_entity"] == yaml.safe_load(raw.split("---")[1])["id"]),
       "«status: Устарела» по-русски понят: запись и её аспекты устарели")
    b2 = node_by_title("Быт")
    ok(b2["type"] == "project" and b2["id"] == b["id"], "«type: Проект» по-русски понят, контейнер на месте")
    ok(len(list((V / "_unsorted").glob("*.md"))) == unsorted_before, "записи «Быт» не потерялись")
    r = node_by_title("Ремонт")
    ok(r["_path"] == V / "Ремонт" / "Ремонт.md" and str(r["id"]).startswith("k") and not r.get("parent_id")
       and r["description"].startswith("Ремонт квартиры"), "заметка «Ремонт» стала контейнером в своей папке")
    m = node_by_title("Меню")
    ok(m["_path"] == bak["_path"].parent / "Меню" / "Меню.md" and m["parent_id"] == bak["id"] and m["type"] == "seed",
       "«Меню» в папке «Пекарня» стала ростком внутри неё")
    t = node_by_title("Путешествия")
    ok(t["_path"] == V / "Путешествия" / "Путешествия.md" and t["type"] == "question", "папка с заметкой — вопрос на верхнем уровне")
    ok("не стала контейнером" in out and (V / "Разное" / "Быт.md").exists(), "одноимённая заметка не принята, есть предупреждение")
    log = "".join(x.read_text(encoding="utf-8") for x in (V / "_логи").glob("изменения *.md"))
    ok("создан контейнер [[Ремонт]]" in log and "внутри [[Пекарня]]" in log, "создание записано в лог изменений")
    r["_path"].write_text(r["_path"].read_text(encoding="utf-8").replace("container_status: active", "container_status: заморожен"),
                          encoding="utf-8")
    out = run("run")
    ok(node_by_title("Ремонт")["container_status"] == "dormant", "«container_status: заморожен» понят")
    out = run("run")
    ok("Нового ничего не было" in out and "не стала контейнером" in out, "повторный прогон ничего не ломает")
    plugin_commands()
    v25_checks()
    v26_checks()
    v27_checks()
    print(f"\nВсё прошло. Хранилище теста: {V}")


def rj(*args, expect=0):
    """Команда с флагом --json, как её вызывает плагин: возвращает вывод и разобранный итог @@RESULT."""
    out = run("--json", *args, expect=expect)
    lines = [x for x in out.splitlines() if x.startswith("@@RESULT ")]
    assert lines, f"нет строки @@RESULT в выводе: {out[-500:]}"
    return out, json.loads(lines[-1][len("@@RESULT "):])


def refl():
    return [json.loads(x) for x in (V / ".system" / "reflection.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def plugin_commands():
    import yaml
    from brain import cli as CLI
    step("14. Плагин: снимок, ответы, настройки, свои пороги контейнера, совет ИИ, «Стоп», установка")
    out, r = rj("snapshot")
    ui = json.loads((V / ".system" / "ui.json").read_text(encoding="utf-8"))
    ok(r["ok"] and ui["status"]["containers"] == len(ui["containers"]) > 0 and ui["threshold_info"]["classification"]["label"],
       "снимок ui.json: контейнеры, статус, описания порогов")
    bak = next(c for c in ui["containers"] if c["title"] == "Пекарня")
    ok(bak["thresholds"]["classification"] == {"value": 70, "source": "global", "from": None}, "у контейнера видны действующие пороги и их источник")
    ok(all({"id", "title", "text", "options"} <= set(q) for q in ui["questions"]), "вопросы в снимке — с вариантами")

    # новая мысль из плагина: служебная строка mode — без вопроса о режиме
    (V / "_staging" / "шторы.txt").write_text("05.06.2024\nmode: steady_state\n\nНадо купить новые шторы в спальню, старые выгорели.\n",
                                             encoding="utf-8")
    out, r = rj("run")
    it = next(i for i in state()["items"].values() if i["name"] == "шторы.txt")
    ok(it["mode"] == "steady_state" and not find_q("mode", lambda q: q["data"].get("item") == it["id"]), "«mode: steady_state» — без вопроса о режиме")
    ok(r["title"] == "Готово" and r["code"] == 0 and r["questions"] >= 1, "итог прогона для плагина (@@RESULT)")
    q = find_q("classify", lambda q: "шторы" in q["text"])[0]
    out, r = rj("answer", q["id"], "--option", "99", expect=1)
    ok("нет варианта" in r["error"], "неверный номер варианта — понятная ошибка")
    out, r = rj("answer", q["id"], "--text", "Быт")
    ok(r["accepted"] and q["id"] not in qs(), "ответ из плагина применён сразу, вопрос закрыт")
    p_, fm, raw = entity_by_text("шторы")
    ok(fm["container"] == "[[Быт]]" and "шторы" in (V / "_логи" / "архив вопросов.md").read_text(encoding="utf-8"),
       "запись переложена в «Быт», вопрос — в архиве")
    out, r = rj("answer", q["id"], "--option", "0", expect=1)
    ok("уже нет" in r["error"], "повторный ответ на закрытый вопрос — понятная ошибка")

    # настройки: чтение, изменение с проверкой, ключ
    out, r = rj("settings")
    st_ = r["settings"]
    ok(st_["values"]["thresholds"]["classification"] == 70 and any(sec["id"] == "roles" for sec in st_["schema"]), "настройки и схема для плагина")
    patch = ROOT / "patch.json"
    patch.write_text(json.dumps({"thresholds": {"classification": 500}}), encoding="utf-8")
    out, r = rj("settings", "--set-json", str(patch), expect=1)
    ok("от 0 до 100" in r["error"] and "classification: 70" not in SETTINGS.read_text(encoding="utf-8"), "неверное значение не сохраняется")
    patch.write_text(json.dumps({"llm": {"roles": {"Синтез": {"temperature": 0.5}}}}), encoding="utf-8")
    out, r = rj("settings", "--set-json", str(patch), expect=1)
    ok("id профиля" in r["error"], "шаг можно отдать только профилю или веб-чату")
    patch.write_text(json.dumps({"thresholds": {"classification": 72},
                                 "llm": {"profiles": {"p2": {"name": "Сильная", "kind": "cloud", "model": "fake-strong",
                                                             "temperature": 0.5}}, "roles": {"Синтез": "p2"}},
                                 "sources": [{"name": "заметка", "color": "#60A5FA", "compaction_shift": 0},
                                             {"name": "Голос", "color": "#F97316", "compaction_shift": 10}]}), encoding="utf-8")
    out, r = rj("settings", "--set-json", str(patch))
    txt = SETTINGS.read_text(encoding="utf-8")
    from brain.config import load_config
    c2 = load_config(SETTINGS)
    p2 = next((x for x in c2["llm"]["profiles"] if x["id"] == "p2"), {})
    ok(c2["thresholds"]["classification"] == 72 and c2["llm"]["roles"]["Синтез"] == "p2" and p2.get("temperature") == 0.5
       and p2.get("api_key_file") == "" and p2.get("max_input_chars") == 300000
       and [x["name"] for x in c2["sources"]] == ["заметка", "Голос"] and c2["llm"]["mode"] == "fake",
       "настройки сохранены и читаются обратно")
    ok("# Раскладка без вопроса" in txt and (ROOT / "settings.yaml.bak").exists(), "settings.yaml переписан с пояснениями, прежний — в .bak")
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO("секретный-ключ\n")
        out, r = rj("settings", "--key", "llm")
        ok((ROOT / "api_key.txt").read_text(encoding="utf-8").strip() == "секретный-ключ" and r["settings"]["keys"]["llm"],
           "ключ из плагина — в файл рядом с программой")
        sys.stdin = io.StringIO("\n")
        rj("settings", "--key", "llm")
        ok(not (ROOT / "api_key.txt").exists(), "пустой ключ удаляет файл")
        sys.stdin = io.StringIO("ключ-второго-профиля\n")
        out, r = rj("settings", "--key", "profile:p2")
        c3 = load_config(SETTINGS)
        p2 = next(x for x in c3["llm"]["profiles"] if x["id"] == "p2")
        ok(p2["api_key_file"] == "api_key_p2.txt" and (ROOT / "api_key_p2.txt").read_text(encoding="utf-8").strip() == "ключ-второго-профиля"
           and r["settings"]["keys"]["profiles"]["p2"], "ключ профиля — в свой файл, профиль запоминает его имя")
        sys.stdin = io.StringIO("ghp_тест\n")
        out, r = rj("settings", "--key", "github", expect=1)
        ok("Неизвестный ключ" in r["error"] and not (ROOT / "github_token.txt").exists(), "токена GitHub больше нет (v2.7)")
    finally:
        sys.stdin = old_stdin
    write_settings()

    # свои пороги контейнера
    kp = node_by_title("Пекарня")["_path"]
    fm_, body_ = kp.read_text(encoding="utf-8").split("---\n", 2)[1:]
    d = yaml.safe_load(fm_)
    d["thresholds"] = {"classification": 95, "value_min": 10, "уплотнение": "abc"}
    kp.write_text("---\n" + yaml.safe_dump(d, allow_unicode=True, sort_keys=False) + "---\n" + body_, encoding="utf-8")
    excluded_before = len(base("Пекарня")["excluded"])
    (V / "_staging" / "хлеб.txt").write_text("06.06.2024\nmode: steady_state\n\nХлеб в пекарне можно продавать навынос.\n", encoding="utf-8")
    out, r = rj("run")
    p_, fm, raw = entity_by_text("навынос")
    rec = [x for x in refl() if x.get("kind") == "classification" and x.get("subject") == fm["id"]][-1]
    ok(fm["quarantine"] and rec["confidence"] == 88 and rec["threshold"] == 95, "свой порог раскладки 95: при уверенности 88 — вопрос")
    ok("уплотнение" in " ".join(r["warnings"]) and "abc" in " ".join(r["warnings"]), "непонятное значение порога — предупреждение")
    b = base("Пекарня")
    ok(b["thresholds"]["value_min"] == 10 and len(b["excluded"]) < excluded_before, "свой порог ценности — база пересобрана без модели")
    chg = "".join(x.read_text(encoding="utf-8") for x in (V / "_логи").glob("изменения *.md"))
    ok("[[Пекарня]]: classification: общий → 95" in chg, "изменение порогов записано в лог изменений")
    ui = json.loads((V / ".system" / "ui.json").read_text(encoding="utf-8"))
    bak = next(c for c in ui["containers"] if c["title"] == "Пекарня")
    ok(bak["thresholds"]["classification"]["source"] == "own" and bak["overrides"] == {"classification": 95, "value_min": 10},
       "в снимке — свои пороги контейнера")
    menu = next(c for c in ui["containers"] if c["title"] == "Меню")
    ok(menu["thresholds"]["classification"] == {"value": 95, "source": "parent", "from": "Пекарня"}, "вложенный контейнер наследует пороги родителя")
    q = find_q("classify", lambda q: "навынос" in q["text"])[0]
    rj("answer", q["id"], "--option", "0")
    ok(entity_by_text("навынос")[1]["container"] == "[[Пекарня]]", "ответ «вариант модели» — запись в Пекарне")

    # совет ИИ по порогам
    out, r = rj("advise", "Пекарня")
    adv = r["advice"]
    cl = next(x for x in adv["recommendations"] if x["name"] == "classification")
    ok(cl["current"] == 95 and cl["value"] == 85 and adv["summary"] and adv["brief"], "совет ИИ: опустить свой порог раскладки 95 → 85")
    ok(not any(x["name"] == "value_min" for x in adv["recommendations"]), "совет «оставить как есть» не показывается как изменение")
    ok(any("ведь" not in b_ and "модель была права — 1" in b_ for b_ in adv["brief"]), "статистика решений по контейнеру посчитана")
    reas = "".join(x.read_text(encoding="utf-8") for x in (V / "_логи").glob("рассуждения *.md"))
    tries = [json.loads(x) for x in (V / ".system" / "usage.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    ok("Пороги" in reas and r["calls"].get("Пороги") == 1 and sum(t["prompt"] == "Пороги" for t in tries) == 2,
       "ответ с неверным порогом отправлен на исправление")
    d = yaml.safe_load(kp.read_text(encoding="utf-8").split("---\n", 2)[1])
    d["thresholds"] = {"classification": 85, "value_min": 10}
    kp.write_text("---\n" + yaml.safe_dump(d, allow_unicode=True, sort_keys=False) + "---\n" + kp.read_text(encoding="utf-8").split("---\n", 2)[2],
                  encoding="utf-8")
    rj("run")
    dec = [x for x in refl() if x.get("type") == "decision" and x.get("kind") == "thresholds_advice"]
    ok(dec and dec[-1]["matched"] == "partial" and dec[-1]["accepted"] == ["classification"] and dec[-1]["ref"] == adv["ref"],
       "применённый частично совет — пара «совет — решение» в рефлексии")
    out, r = rj("advise", "Меню")
    ok(any(x["name"] == "seed_dormancy_days" for x in r["advice"]["recommendations"]), "для ростка совет может касаться дней ожидания")
    old_stdin, sys.stdin = sys.stdin, io.StringIO("")  # не консоль: выбрать контейнер из списка негде
    try:
        out, r = rj("advise", expect=1)
    finally:
        sys.stdin = old_stdin
    ok('advise "Название"' in r["error"], "совет по порогам без названия и без консоли — подсказка с командой advise")
    from brain import schema as SCH
    dup, cls = SCH.THRESHOLDS["duplicate_similarity"], SCH.THRESHOLDS["classification"]
    ok(SCH.parse_number("86%", dup) == 0.86 and SCH.parse_number("0,86", dup) == 0.86 and SCH.parse_number("86", dup) is None
       and SCH.parse_number("80%", cls) == 80, "пороги: «86%» для похожести — это 0,86, «80%» для шкалы 0–100 — 80")

    # стиль контейнера → в промпт синтеза
    d = yaml.safe_load(kp.read_text(encoding="utf-8").split("---\n", 2)[1])
    d["style"] = "Пиши как бизнес-план, с цифрами."
    kp.write_text("---\n" + yaml.safe_dump(d, allow_unicode=True, sort_keys=False) + "---\n" + kp.read_text(encoding="utf-8").split("---\n", 2)[2],
                  encoding="utf-8")
    rj("run")
    os.environ["BRAIN_TEST_WEBCHAT_VARS"] = "1"
    out, r = rj("synth", node_by_title("Пекарня")["id"])
    doc = node_by_title("Пекарня")["_path"].parent / "Сводный файл.md"
    ok(r["ok"] and not r.get("unchanged") and doc.exists() and "в стиле контейнера" in doc.read_text(encoding="utf-8"),
       "Фаза 2 по id контейнера (как из плагина), свой стиль контейнера — в промпте")
    out, r = rj("synth", "Пекарня")
    ok(r.get("unchanged") is True, "повторная Фаза 2 без изменений — флаг «документы актуальны»")
    out, r = rj("revalidate", "Пекарня", "--count")
    ok(r["count"] >= 1, "ревалидация: сначала только подсчёт")

    # «Стоп» посреди прогона
    os.environ["FAKE_STOP_ON"] = "Классификация"
    os.environ["FAKE_STOP_FILE"] = str(V / ".system" / "stop")
    (V / "_staging" / "дача.txt").write_text("07.06.2024\nmode: steady_state\n\nНа даче надо подвязать томаты в теплице.\n", encoding="utf-8")
    out, r = rj("run", expect=1)
    ok(r.get("stopped") and r["title"] == "Остановлено" and not (V / ".system" / "stop").exists(), "«Стоп» из плагина останавливает прогон")
    del os.environ["FAKE_STOP_ON"]
    out, r = rj("run")
    ents = [e for e in entity_files() if "подвязать томаты" in e[2]]
    ok(len(ents) == 1 and r["code"] == 0, "следующий запуск продолжил с того же места, без дублей")
    (V / ".system" / "stop").write_text("", encoding="utf-8")
    out, r = rj("run")
    ok(r["code"] == 0 and not r.get("stopped"), "старый файл «Стоп» не мешает новому запуску")

    # --vault: плагин передаёт открытое хранилище
    SETTINGS.write_text(SETTINGS.read_text(encoding="utf-8").replace(V.as_posix(), (ROOT / "нет такой").as_posix()), encoding="utf-8")
    out, r = run_vault_snapshot()
    ok(r["ok"], "--vault переопределяет хранилище из settings.yaml")
    write_settings()

    # установка плагина
    from brain import install as INST
    fake_prog = ROOT / "программа"
    (fake_prog / "plugin").mkdir(parents=True, exist_ok=True)
    for f in INST.PLUGIN_FILES:
        (fake_prog / "plugin" / f).write_text(f"// {f}", encoding="utf-8")
    saved = INST.PROGRAM_DIR
    INST.PROGRAM_DIR = fake_prog
    try:
        out, r = rj("install-plugin")
    finally:
        INST.PROGRAM_DIR = saved
    dest = V / ".obsidian" / "plugins" / "vtoroy-mozg"
    data = json.loads((dest / "data.json").read_text(encoding="utf-8"))
    ok(all((dest / f).exists() for f in INST.PLUGIN_FILES) and data["programDir"] == str(fake_prog),
       "плагин скопирован в .obsidian/plugins, путь к программе записан")
    ok("vtoroy-mozg" in json.loads((V / ".obsidian" / "community-plugins.json").read_text(encoding="utf-8")), "плагин включён в списке сторонних")


def run_with(settings: Path, *args, stdin: str | None = None, expect=0):
    """Команда с другим settings.yaml и (если нужно) ответами в стандартном вводе — как их пишет плагин."""
    buf = io.StringIO()
    old_in = sys.stdin
    try:
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        with redirect_stdout(buf):
            code = main(["--settings", str(settings)] + list(args))
    finally:
        sys.stdin = old_in
    out = buf.getvalue()
    LOG.append(f"$ brain {' '.join(args)}\n{out}")
    if code != expect:
        print(out)
        raise AssertionError(f"brain {' '.join(args)}: код {code}, ожидался {expect}")
    res = [x for x in out.splitlines() if x.startswith("@@RESULT ")]
    return out, (json.loads(res[-1][len("@@RESULT "):]) if res else None)


def tagged(out: str, tag: str) -> list:
    pre = f"@@{tag} "
    return [json.loads(x[len(pre):]) for x in out.splitlines() if x.startswith(pre)]


def v25_checks():
    from brain.config import load_config
    step("15. v2.5: миграция настроек, дневник по датам, оценка запуска, вопросы через стандартный ввод, расходы")
    # настройки v2.4 со своими моделями шагов → профили
    # образец настроек: в архиве нет settings.yaml — при первом запуске он создаётся из settings.template.yaml
    import yaml
    from brain.config import ensure_settings, prepare, TEMPLATE_NAME
    tpl = APP / TEMPLATE_NAME
    ok(tpl.is_file(), "образец настроек есть в папке программы")
    ok(prepare(yaml.safe_load(tpl.read_text(encoding="utf-8"))) == prepare({}), "образец настроек — ровно умолчания программы (новый формат)")
    fresh = ROOT / "fresh"
    fresh.mkdir(exist_ok=True)
    shutil.copy2(tpl, fresh / TEMPLATE_NAME)
    ok(ensure_settings(fresh / "settings.yaml") and (fresh / "settings.yaml").read_text(encoding="utf-8") == tpl.read_text(encoding="utf-8"),
       "первый запуск: settings.yaml создан из образца")
    (fresh / "settings.yaml").write_text("vault: моё\n", encoding="utf-8")
    ok(not ensure_settings(fresh / "settings.yaml") and (fresh / "settings.yaml").read_text(encoding="utf-8") == "vault: моё\n",
       "существующий settings.yaml образец не трогает")
    old = ROOT / "old-settings.yaml"
    old.write_text(f"""vault: "{V.as_posix()}"
llm:
  mode: api
  base_url: "https://api.z.ai/api/paas/v4"
  model: "glm-4.6"
  api_key_file: "api_key.txt"
  max_input_chars: 200000
  max_format_retries: 3
  roles:
    Синтез: {{model: "glm-4.6-pro", temperature: 0.4}}
    Уплотнение: {{model: "glm-4.6-pro", temperature: 0.4}}
    Классификация: {{base_url: "http://127.0.0.1:8080/v1", model: "qwen"}}
    Вопросы: {{mode: webchat}}
embeddings:
  mode: api
  base_url: "https://api.openai.com/v1"
  model: "text-embedding-3-small"
""", encoding="utf-8")
    c = load_config(old)
    L = c["llm"]
    P = {x["id"]: x for x in L["profiles"]}
    ok(L["mode"] == "cloud" and L["cloud_profile"] == "p1" and P["p1"]["model"] == "glm-4.6" and P["p1"]["max_input_chars"] == 200000
       and P["p1"]["api_key_file"] == "api_key.txt" and L["max_format_retries"] == 3, "v2.4: основная модель стала профилем p1 (ключ прежний)")
    ok(L["roles"]["Синтез"] == L["roles"]["Уплотнение"] == "p2" and P["p2"]["model"] == "glm-4.6-pro" and P["p2"]["temperature"] == 0.4
       and P["p2"]["api_key_file"] == "api_key.txt", "v2.4: одинаковые свои модели шагов — один профиль с тем же ключом")
    ok(L["roles"]["Классификация"] == "p3" and P["p3"]["kind"] == "local" and P["p3"]["api_key_file"] == "" and L["local_profile"] == "p3",
       "v2.4: свой сервер шага — локальный профиль, общий ключ туда не идёт")
    ok(L["roles"]["Вопросы"] == "webchat" and c["embeddings"]["mode"] == "cloud", "v2.4: веб-чат шага и облачные эмбеддинги перенесены")
    patch = ROOT / "patch.json"
    patch.write_text("{}", encoding="utf-8")
    run_with(old, "--json", "settings", "--set-json", str(patch))
    txt = old.read_text(encoding="utf-8")
    ok("profiles:" in txt and 'cloud_profile: "p1"' in txt and load_config(old)["llm"] == c["llm"],
       "после сохранения settings.yaml — в новом виде и читается так же")
    out, r = rj("settings")
    st_ = r["settings"]
    ok(st_["tabs"]["costs"] == "Расходы" and any(f["key"] == "prices.input" for f in st_["profile_fields"])
       and st_["profile_defaults"]["local"]["base_url"].startswith("http://127.0.0.1") and st_["defaults"]["budget"]["warn_pct"] == 80,
       "для плагина: вкладки, поля профилей, умолчания")

    # дневник: записи по датам
    (V / "_staging" / "дневник.txt").write_text(
        "Мой дневник весны.\n\n12.03.2021\nСегодня в пекарне снова очередь: нужен второй пекарь на выходные.\n\n"
        "02.04.2021\nСегодня на даче поставил теплицу, огурцы посажу в мае.\n\n"
        "15 апреля 2021\nСегодня плохо спал, сон сбился — надо раньше ложиться.\n", encoding="utf-8")
    out, r = rj("run")
    its = sorted([i for i in state()["items"].values() if i["name"].startswith("дневник.txt")], key=lambda i: i["part"]["n"])
    ok(len(its) == 3 and [i["date"] for i in its] == ["2021-03-12", "2021-04-02", "2021-04-15"] and len({i["file"] for i in its}) == 1
       and its[0]["name"] == "дневник.txt · 12.03.2021", "дневник разделён по датам: три записи со своими датами, исходник один")
    ents = {k: entity_by_text(k) for k in ("второй пекарь", "поставил теплицу", "сон сбился")}
    ok(all(str(fm.get("source_part", "")).endswith(lab) for (_, fm, _), lab in zip(ents.values(), ("12.03.2021", "02.04.2021", "15.04.2021")))
       and str(ents["поставил теплицу"][1].get("created", ""))[:10] == "2021-04-02", "у записей из дневника — своя дата и номер части")
    ok("Мой дневник весны" in ents["второй пекарь"][2] and "02.04.2021" not in ents["поставил теплицу"][2].split("---", 2)[2],
       "короткий заголовок файла — к первой записи; строка с датой в текст записи не попадает")
    ok(any("разделён" in m or "по датам" in m for m in r["messages"]), "о делении сказано в итоге запуска")

    # оценка большого запуска и вопрос через стандартный ввод
    (V / "_staging" / "пекарня-план.txt").write_text("08.06.2024\nmode: steady_state\n\nПекарня: мельница предлагает скидку на муку "
                                                  "при заказе от 20 кг.\n", encoding="utf-8")
    out, r = rj("estimate", "run")
    e = r["estimate"]
    ok(e["calls"] >= 2 and e["steps"].get("Классификация") == 1 and e["lines"] and e["cost"] is None and not r["over"],
       "оценка Фазы 1 без запуска: обращения по шагам, без стоимости у тестовой модели")
    write_settings(extra="estimate:\n  calls: 1\n")
    out, r = run_with(SETTINGS, "--json", "--ask-stdin", "run", stdin='{"choice": 1}\n')
    asks = tagged(out, "ASK")
    ok(asks and asks[0]["id"] == "estimate" and asks[0]["options"] == ["Запустить", "Отмена"] and asks[0]["lines"]
       and r.get("cancelled") and (V / "_staging" / "пекарня-план.txt").exists(), "большой запуск: вопрос с оценкой, «Отмена» — ничего не тронуто")
    out, r = run_with(SETTINGS, "--json", "--ask-stdin", "run", stdin="")
    ok(r.get("cancelled") and (V / "_staging" / "пекарня-план.txt").exists(), "окно вопроса закрыто без ответа — тоже отмена")
    out, r = run_with(SETTINGS, "--json", "--ask-stdin", "run", stdin='{"choice": 0}\n')
    prog, waits, used = tagged(out, "PROGRESS"), tagged(out, "WAIT"), tagged(out, "USAGE")
    ok(r["ok"] and not (V / "_staging" / "пекарня-план.txt").exists() and r["run_usage"]["calls"] == len(used) >= 1 and waits,
       "«Запустить» — запуск идёт; строки расхода и ожидания ответа модели — для плагина")
    ok(any(x["stage"] == "Разбор файлов" and x["n"] == 1 and x["total"] == 1 for x in prog) and used[-1]["run"]["calls"] == len(used),
       "прогресс этапа («1 из 1») и расход запуска нарастающим итогом")
    ok(r["elapsed"] >= 0 and r["run_id"] and r["estimate"]["calls"] >= 1, "в итоге — длительность, номер запуска и оценка")
    log = next((V / "_логи").glob("изменения *.md")).read_text(encoding="utf-8")
    ok("программа · Фаза 1: готово — длительность" in log, "длительность и расход запуска — в журнале изменений")
    write_settings()

    # ревалидация спрашивает всегда
    out, r = run_with(SETTINGS, "--json", "--ask-stdin", "revalidate", "Пекарня", stdin='{"choice": 1}\n')
    ok(r.get("cancelled") and tagged(out, "ASK")[0]["id"] == "estimate" and r["estimate"]["steps"] == {"Классификация": r["count"]},
       "ревалидация: вопрос с оценкой всегда, «Отмена» — без обращений к модели")
    out, r = rj("revalidate", "Пекарня", expect=1)
    ok("--yes" in r["error"], "ревалидация без возможности спросить — только с --yes")

    # расходы
    out, r = rj("usage")
    u = r["usage"]
    ok(u["totals"]["all"]["calls"] > 0 and u["current"]["key"] == "p1" and any(x["name"] == "Классификация" for x in u["steps"])
       and len(u["days"]) == 31 and u["runs"], "расходы: итоги, текущий профиль, шаги, дни, запуски")
    with open(V / ".system" / "usage.jsonl", "a", encoding="utf-8") as f:  # запись старого формата (v2.4)
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "prompt": "Синтез", "model": "fake",
                            "usage": {"prompt_tokens": 1000, "completion_tokens": 200}, "chars_in": 3000, "chars_out": 600}) + "\n")
    out, r2 = rj("usage")
    ok(r2["usage"]["totals"]["all"]["calls"] == u["totals"]["all"]["calls"] + 1
       and r2["usage"]["totals"]["all"]["in"] == u["totals"]["all"]["in"] + 1000, "старые записи расхода (v2.4) тоже учитываются")
    out = run("status")
    ok("Расходы за сегодня" in out and "За этот месяц" in out, "статус показывает расходы")
    ui = json.loads((V / ".system" / "ui.json").read_text(encoding="utf-8"))
    ok(ui["usage"]["totals"]["all"]["calls"] >= 1 and "budget" in ui["usage"], "расходы — в снимке для панели")


def v26_checks():
    from brain import install as INST
    step("16. v2.6: установка «всё в одном», уборка прежних .bat")
    # прежние .bat убираются; свои файлы пользователя — нет
    pd = ROOT / "старая-программа"
    pd.mkdir(exist_ok=True)
    for n in INST.LEGACY_FILES + ("Установка.bat", "Мой скрипт.bat"):
        (pd / n).write_text("@echo off\r\n", encoding="utf-8")
    removed = INST.remove_legacy(pd)
    left = sorted(p.name for p in pd.iterdir())
    ok(sorted(removed) == sorted(INST.LEGACY_FILES) and left == sorted(["Установка.bat", "Мой скрипт.bat"]),
       f"прежние .bat убраны ({len(removed)}), «Установка.bat» и свои файлы остались")
    # после обновления с 2.5 (её обновлятор об уборке не знал) — убирает любая команда
    (ROOT / "Статус.bat").write_text("@echo off\r\n", encoding="utf-8")
    run("status")
    ok(not (ROOT / "Статус.bat").exists(), "любая команда убирает оставшиеся прежние .bat")

    # хранилища из obsidian.json: открытое — первым, потом по времени; несуществующие и без .obsidian — мимо
    cfgdir = ROOT / "obsidian-config"
    cfgdir.mkdir(exist_ok=True)
    va, vb, vc = ROOT / "хранилище А", ROOT / "хранилище Б", ROOT / "просто папка"
    for d in (va, vb):
        (d / ".obsidian").mkdir(parents=True, exist_ok=True)
    vc.mkdir(exist_ok=True)
    (cfgdir / "obsidian.json").write_text(json.dumps({"vaults": {
        "1": {"path": str(vb), "ts": 2000},
        "2": {"path": str(va), "ts": 1000, "open": True},
        "3": {"path": str(ROOT / "удалённое"), "ts": 3000},
        "4": {"path": str(vc), "ts": 4000},
    }}), encoding="utf-8")
    os.environ.update({"BRAIN_OBSIDIAN_CONFIG": str(cfgdir), "BRAIN_NO_OPEN": "1", "BRAIN_OBSIDIAN_RUNNING": "0"})
    saved = INST.PROGRAM_DIR
    try:
        found = INST.find_vaults()
        ok(found == [va, vb], f"хранилища Obsidian найдены: {[p.name for p in found]}")
        ok(INST.choose_vault(None, False) == va and INST.choose_vault(vb, False) == vb,
           "без вопросов: хранилище из настроек, иначе открытое сейчас")
        old_in = sys.stdin
        try:
            sys.stdin = io.StringIO("2\n")
            with redirect_stdout(io.StringIO()):
                pick2 = INST.choose_vault(None, True)
            sys.stdin = io.StringIO(f"{vc}\n\"{vb}\"\n")
            buf = io.StringIO()
            with redirect_stdout(buf):
                pick_path = INST.choose_vault(None, True)
        finally:
            sys.stdin = old_in
        ok(pick2 == vb and pick_path == vb and "нет хранилища Obsidian" in buf.getvalue(),
           "выбор хранилища: по номеру и вставленным путём (папка без .obsidian — переспросить)")

        # setup: плагин в хранилище, папка хранилища — в settings.yaml, прежние .bat убраны
        fake_prog = ROOT / "программа"
        for n in ("Фаза 1.bat", "Обновить.bat"):
            (ROOT / n).write_text("@echo off\r\n", encoding="utf-8")
        INST.PROGRAM_DIR = fake_prog
        try:
            out, r = rj("setup", str(vb))
        finally:
            INST.PROGRAM_DIR = saved
        dest = vb / ".obsidian" / "plugins" / "vtoroy-mozg"
        data = json.loads((dest / "data.json").read_text(encoding="utf-8"))
        ok(r["ok"] and r["vault"] == str(vb) and all((dest / f).exists() for f in INST.PLUGIN_FILES) and data["programDir"] == str(fake_prog)
           and "vtoroy-mozg" in json.loads((vb / ".obsidian" / "community-plugins.json").read_text(encoding="utf-8")),
           "setup: плагин установлен и включён")
        import yaml
        ok(yaml.safe_load(SETTINGS.read_text(encoding="utf-8"))["vault"] == vb.as_posix(), "setup: папка хранилища записана в settings.yaml")
        ok(sorted(r["removed"]) == ["Обновить.bat", "Фаза 1.bat"] and not (ROOT / "Фаза 1.bat").exists(), "setup: прежние .bat убраны")
        ok("Дальше в Obsidian" in out and "Перезапустите Obsidian" not in out, "setup: подсказки, что делать дальше")
        write_settings()
        # Obsidian открыт — напомнить перезапустить
        os.environ["BRAIN_OBSIDIAN_RUNNING"] = "1"
        INST.PROGRAM_DIR = fake_prog
        try:
            out, r = rj("setup", str(vb))
        finally:
            INST.PROGRAM_DIR = saved
        ok(r["ok"] and "Перезапустите Obsidian" in out, "setup при открытом Obsidian: напоминание перезапустить его")
        write_settings()
        out, r = rj("setup", str(vc), expect=1)
        ok("нет хранилища Obsidian" in r["error"], "setup в папку без хранилища — понятная ошибка")
    finally:
        for k in ("BRAIN_OBSIDIAN_CONFIG", "BRAIN_NO_OPEN", "BRAIN_OBSIDIAN_RUNNING"):
            os.environ.pop(k, None)
        INST.PROGRAM_DIR = saved



def v27_checks():
    """v2.7: своя модель эмбеддингов на llama.cpp (скачивание, запуск, автозапуск, остановка); обновления без токена."""
    import socket
    import subprocess
    import yaml
    from brain import cli as CLI
    from brain import llama as L
    from brain import updater as UPD
    from brain.config import load_config, prepare
    from brain.embed import Embedder
    sys.path.insert(0, str(APP / "tests"))
    from fake_llama import FakeHub, free_port
    step("17. v2.7: модель эмбеддингов на llama.cpp — скачивание, запуск, автозапуск; обновления без токена")

    # настройки прежних версий
    old = prepare({"embeddings": {"mode": "local", "base_url": "http://localhost:11434/v1", "model": "qwen3-embedding:8b-q8_0"},
                   "updates": {"check_on_start": False, "repo": "https://github.com/me/brain", "token_file": "github_token.txt"}})
    ok(old["embeddings"]["base_url"] == "http://127.0.0.1:8081/v1" and old["embeddings"]["model"] == L.ALIAS
       and old["embeddings"]["server"] == L.SERVER_DEFAULTS, "прежние умолчания эмбеддингов (Ollama) → своя модель на llama.cpp")
    own = prepare({"embeddings": {"mode": "local", "base_url": "http://192.168.1.5:9000/v1", "model": "моя-модель"}})
    ok(own["embeddings"]["base_url"] == "http://192.168.1.5:9000/v1" and own["embeddings"]["model"] == "моя-модель",
       "свой сервер эмбеддингов в настройках не тронут")
    ok(old["updates"] == {"check_on_start": False}, "из «Обновлений» убраны ссылка на репозиторий и токен")
    errs = L.check_params(dict(L.SERVER_DEFAULTS, ctx=100, device="tpu", port=80, gpu_layers="много"))
    ok(len(errs) == 4 and any(".ctx:" in e for e in errs) and any(".port:" in e for e in errs), "неверные параметры запуска — понятные ошибки")
    out, r = rj("settings")
    ok(r["settings"]["update_repo"] == UPD.repo_link(), "плагин знает ссылку на репозиторий (из brain/__init__.py)")
    saved_repo = os.environ.pop("BRAIN_UPDATE_REPO", None)
    saved_const = UPD.UPDATE_REPO
    UPD.UPDATE_REPO = ""
    try:
        out, r = rj("update", "--check", expect=1)
        ok("UPDATE_REPO" in r["error"] and "brain/__init__.py" in r["error"], "ссылка не вписана — сказано, где её вписать")
    finally:
        UPD.UPDATE_REPO = saved_const
        if saved_repo is not None:
            os.environ["BRAIN_UPDATE_REPO"] = saved_repo

    LP = ROOT / "llama-prog"
    shutil.rmtree(LP, ignore_errors=True)
    LP.mkdir()
    LS = LP / "settings.yaml"
    LS.write_text(f'vault: "{V.as_posix()}"\nllm:\n  mode: fake\n  model: "fake"\n'
                  f'  fake_module: "{(APP / "tests" / "fake_llm.py").as_posix()}"\nestimate:\n  enabled: false\n', encoding="utf-8")
    model = bytes(range(256)) * (3 * 4096) + b"gguf-tail" * 1000  # ~3,1 МБ вместо 6,9 ГБ
    hub = FakeHub(L.MODEL["repo"], L.MODEL["file"], model, L.plat()[1])
    env = {"BRAIN_HF_BASE": hub.url, "BRAIN_LLAMA_API": hub.url + "/gh", "BRAIN_LLAMA_NO_SYSTEM": "1",
           "BRAIN_TEST_HW": json.dumps({"ram_gb": 32, "ram_free_gb": 20, "gpus": [], "nvidia": False, "cores": 8})}
    saved_env = {k: os.environ.get(k) for k in list(env) + ["FAKE_LLAMA_GPU", "FAKE_LLAMA_OOM"]}
    os.environ.update(env)
    procs = []
    port = free_port()
    mdir = LP / "models"
    mp = mdir / L.MODEL["file"]
    log = LP / "llama.cpp" / "server.log"

    def server_args():
        return json.loads(re.search(r"FAKE ARGS: (.*)", log.read_text(encoding="utf-8")).group(1))

    def check_emb(expect=0):
        out, r = run_with(LS, "--json", "check", expect=expect)
        return out, next(x for x in r["check"] if x["name"] == "Эмбеддинги")

    try:
        out, r = run_with(LS, "--json", "llama", "status", "--hw")
        st = r["llama"]
        ok(not st["model"]["exists"] and st["builds"] == {} and not st["server"]["running"] and st["configured"]
           and st["hardware"]["ram_gb"] == 32 and [i["what"] for i in st["plan"]["download"]] == ["model", "cpu"],
           "состояние: модель и llama.cpp не скачаны, адрес по умолчанию — свой сервер, что придётся скачать")

        # скачивание: продолжить начатое и докачать после обрыва; архив llama.cpp — через запасной адрес
        mdir.mkdir()
        (mdir / (L.MODEL["file"] + ".part")).write_bytes(model[: 1 << 20])
        hub.break_once = 1 << 20
        out, r = run_with(LS, "--json", "llama", "download")
        ok(r["ok"] and r["title"] == "Скачано" and mp.read_bytes() == model and not (mdir / (L.MODEL["file"] + ".part")).exists(),
           "модель скачана с Hugging Face")
        ok(hub.ranges == [f"bytes={1 << 20}-", f"bytes={2 << 20}-"], f"докачка: с места прошлого скачивания и после обрыва ({hub.ranges})")
        prog = tagged(out, "PROGRESS")
        mprog = [x for x in prog if x["stage"] == "Скачивание модели"]
        ok(mprog and all(x["unit"] == "%" and x["total"] == 100 for x in mprog) and mprog[-1]["n"] == 100 and " из " in mprog[-1]["item"]
           and any(x["stage"] == "Проверка файла" for x in prog), f"ход скачивания — проценты для полосы в панели ({[x['n'] for x in mprog]})")
        b = LP / "llama.cpp" / "cpu"
        ok((b / "llama-server").is_file() and os.access(b / "llama-server", os.X_OK) and (b / "libggml-base.so").is_file()
           and json.loads((b / "build.json").read_text(encoding="utf-8"))["tag"] == "b9999"
           and not any((LP / "llama.cpp" / "_download").iterdir()), "llama.cpp скачан с GitHub и распакован в llama.cpp/cpu")
        ok(f"/dl/{hub.tar_name}" in hub.calls and "/gh/assets/2" in hub.calls, "ссылка на архив не ответила — скачано через запасной адрес")
        hub.bad_sha = True
        out, r = run_with(LS, "--json", "llama", "download", "--params-json", "-", stdin=json.dumps({"models_dir": "другая папка"}), expect=1)
        ok("контрольная сумма не совпала" in r["error"] and not (LP / "другая папка" / (L.MODEL["file"] + ".part")).exists(),
           "файл скачался с ошибкой — понятное сообщение, испорченный файл не остаётся")
        hub.bad_sha = False
        n_req = len(hub.calls)
        out, r = run_with(LS, "--json", "pull-embeddings")
        ok(r["ok"] and r["title"] == "Скачано" and len(hub.calls) == n_req, "«pull-embeddings» (до v2.7) — то же, что «llama download»; скачанное не качается снова")

        # запуск с параметрами из окна плагина
        par = {"device": "cpu", "ctx": 4096, "kv_cache": "q8_0", "threads": 2, "port": port, "sleep_min": 5}
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(par))
        srv, url = r["server"], f"http://127.0.0.1:{port}/v1"
        ok(r["ok"] and r["title"] == "Модель запущена" and srv["url"] == url and srv["dim"] == 8 and not srv["already"], "модель запущена")
        e = yaml.safe_load(LS.read_text(encoding="utf-8"))["embeddings"]
        ok(e["mode"] == "local" and e["base_url"] == url and e["model"] == L.ALIAS and e["server"]["port"] == port
           and e["server"]["kv_cache"] == "q8_0" and e["server"]["ctx"] == 4096, "адрес сервера, модель и параметры вписаны в настройки")
        a = server_args()
        line = " ".join(a)
        ok(a[:2] == ["-m", L.MODEL["file"]] and all(x in line for x in (
            "--embedding --pooling last", f"--alias {L.ALIAS}", f"--port {port}", "-c 4096 -np 1 -b 4096 -ub 4096", "-ctk q8_0 -ctv q8_0 -fa on",
            "-ngl 0 -dev none", "-t 2 -tb 2", "--sleep-idle-seconds 300", "--no-webui")), f"параметры llama-server: {line}")
        ok(f"FAKE CWD: {mdir}" in log.read_text(encoding="utf-8"), "сервер запущен из папки модели")
        ok(any(x["stage"] == "Загрузка модели в память" and x["total"] == 0 for x in tagged(out, "PROGRESS")),
           "загрузка модели в память — этап без «N из M»")
        pid = srv["pid"]
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(par))
        ok(r["title"] == "Сервер уже работает" and r["server"]["pid"] == pid, "повторный запуск с теми же параметрами — сервер уже работает")
        out, r = run_with(LS, "--json", "llama", "status")
        ok(r["llama"]["server"]["running"] and r["llama"]["server"]["health"] == "ok" and r["llama"]["configured"], "состояние: сервер работает")
        ok("Сервер: работает" in run_with(LS, "llama", "status")[0], "состояние понятным текстом")
        out, emb = check_emb()
        ok(emb["ok"] and "вектор 8 чисел" in emb["text"], "«Проверить связь»: эмбеддинги считает свой сервер")
        lcfg = load_config(LS)
        lcfg["embeddings"]["max_chars"] = 20000
        vec = Embedder(lcfg).embed(["длинный текст " * 900])
        ok(vec.shape == (1, 8) and "max=12600" in log.read_text(encoding="utf-8") and "max=6300" in log.read_text(encoding="utf-8"),
           "текст длиннее окна модели — укорочен и посчитан")

        out, r = run_with(LS, "--json", "llama", "stop")
        ok(r["title"] == "Сервер остановлен" and not r["llama"]["server"]["running"] and not L._alive(pid) and L.health(port) is None,
           "сервер остановлен")
        out, r = run_with(LS, "--json", "llama", "stop")
        ok(r["title"] == "Сервер не был запущен", "остановка без запущенного сервера — без ошибки")

        # автозапуск, когда эмбеддинги нужны, а сервер не запущен
        out, emb = check_emb()
        ok(emb["ok"] and "запускаю его" in out and L.read_state(lcfg)["by"] == "auto", "сервер не запущен — программа запустила его сама")
        run_with(LS, "llama", "stop")
        run_with(LS, "--json", "settings", "--set-json", "-", stdin=json.dumps({"embeddings": {"server": {"autostart": False}}}))
        t = time.time()
        out, emb = check_emb(expect=1)
        ok(not emb["ok"] and "«Запустить модель…»" in emb["text"] and not L.running(lcfg) and time.time() - t < 15,
           "автозапуск выключен — понятная подсказка, долго не ждёт")
        run_with(LS, "--json", "settings", "--set-json", "-", stdin=json.dumps({"embeddings": {"server": {"autostart": True}}}))
        os.replace(mp, mp.with_name("спрятано.gguf"))
        out, emb = check_emb(expect=1)
        os.replace(mp.with_name("спрятано.gguf"), mp)
        ok(not emb["ok"] and "ещё не скачана" in emb["text"], "модели нет — автозапуск ничего не скачивает, подсказывает")

        # видеокарта
        shutil.copytree(LP / "llama.cpp" / "cpu", LP / "llama.cpp" / "vulkan")
        gpar = dict(par, device="gpu")
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(gpar), expect=1)
        ok("не нашёл видеокарту" in r["error"] and not L.running(lcfg), "видеокарты не видно — понятная ошибка")
        os.environ["FAKE_LLAMA_GPU"] = "Fake Radeon"
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(gpar))
        a = server_args()
        ok(r["server"]["build"] == "vulkan" and r["server"]["devices"] == ["Vulkan0: Fake Radeon (8192 MiB, 8000 MiB free)"]
           and " ".join(a).count("-ngl auto") == 1 and "-dev" not in a, f"на видеокарте: сборка Vulkan, слоёв — сколько поместится ({' '.join(a)})")
        gpid = r["server"]["pid"]
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(par))
        ok("Перезапускаю сервер" in out and r["server"]["build"] == "cpu" and r["server"]["pid"] != gpid and not L._alive(gpid),
           "другие параметры — сервер перезапущен")
        run_with(LS, "llama", "stop")

        # ошибки запуска
        os.environ["BRAIN_TEST_HW"] = json.dumps({"ram_gb": 8, "gpus": [], "nvidia": False})
        os.environ["FAKE_LLAMA_OOM"] = "1"
        out, r = run_with(LS, "--json", "llama", "start", expect=1)
        os.environ.pop("FAKE_LLAMA_OOM")
        ok("не хватило памяти" in r["error"] and "Журнал сервера" in r["error"] and not L.running(lcfg),
           "сервер упал от нехватки памяти — понятная причина")
        ok(any("не меньше 16 ГБ" in x["text"] for x in tagged(out, "NOTICE")), "меньше 16 ГБ памяти при работе на процессоре — предупреждение")
        os.environ["BRAIN_TEST_HW"] = env["BRAIN_TEST_HW"]
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(dict(par, port=busy.getsockname()[1])),
                              expect=1)
        ok("занят другой программой" in r["error"], "порт занят другой программой — понятная ошибка")
        fport = free_port()
        fp = subprocess.Popen([sys.executable, str(b / "llama-server"), "-m", L.MODEL["file"], "--alias", L.ALIAS, "--port", str(fport)],
                              cwd=str(mdir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=dict(os.environ, FAKE_LLAMA_LOAD_SEC="0"))
        procs.append(fp)
        for _ in range(100):
            if L.health(fport) == "ok":
                break
            time.sleep(0.1)
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(dict(par, port=fport)), expect=1)
        ok("запущен он не из программы" in r["error"], "на порту — чужой llama-server с этой моделью: его параметры не поменять")

        # «Стоп» посреди скачивания: начатое остаётся
        stopf = V / ".system" / "stop"
        stopf.write_text("", encoding="utf-8")
        try:
            L.download([(f"{hub.url}/{L.MODEL['repo']}/resolve/main/{L.MODEL['file']}", {})], LP / "tmpdl" / "m.gguf", len(model), None,
                       "Скачивание модели", stopf)
            stopped = False
        except KeyboardInterrupt:
            stopped = True
        ok(stopped and not stopf.exists() and (LP / "tmpdl" / "m.gguf.part").exists(), "«Стоп» прерывает скачивание, начатое остаётся")

        # установка: предложить скачать модель и llama.cpp
        LP2 = ROOT / "llama-prog2"
        shutil.rmtree(LP2, ignore_errors=True)
        LP2.mkdir()
        (LP2 / "settings.yaml").write_text(LS.read_text(encoding="utf-8").split("embeddings:")[0], encoding="utf-8")
        old_in = sys.stdin
        buf = io.StringIO()
        try:
            sys.stdin = io.StringIO("д\n")
            with redirect_stdout(buf):
                CLI._setup_llama(load_config(LP2 / "settings.yaml"), True)
        finally:
            sys.stdin = old_in
        ok("Скачать сейчас? (д/н)" in buf.getvalue() and (LP2 / "models" / L.MODEL["file"]).read_bytes() == model
           and (LP2 / "llama.cpp" / "cpu" / "llama-server").is_file(), "установка: модель и llama.cpp скачаны по согласию")
    finally:
        try:
            run_with(LS, "llama", "stop")
        except Exception:  # noqa: BLE001
            pass
        for x in procs:
            x.terminate()
            try:
                x.wait(5)
            except subprocess.TimeoutExpired:
                x.kill()
        hub.close()
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_vault_snapshot():
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(["--settings", str(SETTINGS), "--vault", str(V), "--json", "snapshot"])
    out = buf.getvalue()
    line = [x for x in out.splitlines() if x.startswith("@@RESULT ")][-1]
    return out, json.loads(line[len("@@RESULT "):])


if __name__ == "__main__":
    try:
        main_test()
    except AssertionError as e:
        print(f"\nПРОВАЛ: {e}")
        print("\n--- последние выводы программы ---")
        for x in LOG[-3:]:
            print(x[-3000:])
        sys.exit(1)

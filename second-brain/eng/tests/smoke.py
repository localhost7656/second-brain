"""End-to-end testing of the program with a test model (llm.mode: fake, embeddings.mode: fake).
Launch: python tests/smoke.py [folder]  — default in the time folder."""
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
    """Settings in format v2.4 (llm.model ot.p..) — The program itself translates them into profiles..
    Big launch evaluation turned off: test-stop 15 (The test does not have to wait for a response in the console.)."""
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
        raise AssertionError(f"brain {' '.join(args)}: code {code}, expected {expect}")
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
    """Mark the option (number) and/or write in — how would a man do in Obsidian."""
    c = find_q(kind, where)
    assert c, f"Theres no open question {kind}"
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
                lines[i] = "- [x] " + label  # Latin x
                done_pick = True
                pick = None
        if text is not None and lines[i].startswith("Answer:"):
            lines[i] = "Answer: " + text
            text = None
    assert done_pick, f"questioningly {q['id']} no-no-no-no-no-no-no-no-no-no-no-no-no-no-no. {pick}"
    assert text is None, f"questioningly {q['id']} no line «Answer:»"
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
    raise AssertionError(f"no container {title}")


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
    raise AssertionError(f"no writing «{snippet}»")


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

    step("1. Archives: date, clues, dialogue, cp1251, file-in-the-box, picture")
    arch = V / "_staging" / "archive"
    (arch / "Chat with AI").mkdir(parents=True)
    (arch / "journal 2023.txt").write_bytes((
        "02.04.2023\n\n"
        "I planted tomatoes in a greenhouse today.. Watering every day at night.\n\n"
        "Cucumbers in the greenhouse grow poorly. Probably., light.\n\n"
        "A weather station can be put in a greenhouse in the country — humidify.\n\n"
        "I had a strange dream about the train..\n\n"
        "The timer watering option needs to be checked..\n").encode("cp1251"))
    (arch / "Chat with AI" / "weather-station.txt").write_text(
        "01.06.2023\n"
        "Me: What sensor to take for a weather station — wired?\n"
        "AI: Wireless is more convenient and can be installed anywhere., Wired is cheaper and does not require batteries. "
        "If the price is important, wired looks smarter, But the accuracy must be checked on the spot..\n"
        "Me: Maybe., Its enough to have one sensor on the balcony..\n"
        "AI: Two sensors are better for accuracy., street-mate, second-in-the-room.\n"
        "Me: So,, Were taking two wired sensors.. You can put a sensor on the wall..\n"
        "Me: You can also install a sensor under the roof., So hes in the shadows..\n", encoding="utf-8")
    (arch / "bakery.txt").write_text(
        "\ufeff10.05.2023\n\nIm thinking of opening a little bakery near my house.. Cost of a loaf of bread — 50 ruble.\n\n"
        "Rental of premises 40 000 rupees. I like the idea of self-service..\n", encoding="utf-8")
    (arch / "different.txt").write_text("We should take out old photos on the mezzanine..\n", encoding="utf-8")
    set_mtime(arch / "different.txt", "2023-01-15T10:00:00")
    (arch / "flour.txt").write_text("12.05.2023\nhint: its about the dacha\n\nA baker at a nearby bakery said, It is better to take flour from the mill directly..\n", encoding="utf-8")
    (arch / "empty.txt").write_text("  \n", encoding="utf-8")
    (V / "_staging" / "photo.jpg").write_bytes(b"\xff\xd8\xff")

    out = run("run")
    st = state()
    ok(st["structure"]["pending"], "draft structure awaits approval")
    ok((V / "_structure (draft).md").exists(), "draft file created")
    ok(not list((V / "_staging").rglob("*.txt")), "txt stripped _staging")
    ok(len(list((V / "_sources").glob("*.txt"))) == 6, "source is saved unchanged (6 file)")
    ok((V / "_sources" / "2023-04-02 journal 2023.txt").read_bytes().decode("cp1251").startswith("02.04.2023"), "cp1251-file copied byte into byte")
    ok(any(it["date"] == "2023-01-15" for it in st["items"].values()), "date without cap is taken from file")
    ok(any(it["encoding"] == "cp1251" for it in st["items"].values()), "code cp1251 recognized")
    ok(any(it.get("content_type") == "ai_dialogue" for it in st["items"].values()), "dialogue with AI recognized by markup")
    ok(any(it.get("hint") == "its about the dacha" for it in st["items"].values()), "clue hint read")
    ok("photo.jpg" in (V / "open-questions.md").read_text(encoding="utf-8"), "The unsupported file is said to")
    ok(not (V / ".system" / "data" / "pools").exists() or not list((V / ".system" / "data" / "pools").glob("*.json")), "before approval, nothing is decomposed")

    step("2. Correction and approval of draft")
    d = (V / "_structure (draft).md").read_text(encoding="utf-8")
    ok("weather station (project)" in d and "Bakery (sprout)" in d, "In the draft there is a weather station and a bakery")
    d = d.replace("- dacha (project)", "- Dacha and garden (project)")
    d = d.replace("## Tree\n\n", "## Tree\n\n- Health (sprout) — sleep and well-being\n")
    run("run")
    ok(state()["structure"]["pending"], "without a checkmark, the draft does not apply")
    d = d.replace("- [ ] Structure approved", "- [x] Structure approved")  # cyrillic
    (V / "_structure (draft).md").write_text(d, encoding="utf-8")
    out = run("run")
    ok(not state()["structure"]["pending"], "structure approved (Cyrillic «x» worked)")
    for t in ("Technology", "weather station", "Bakery", "Dacha and garden", "Health"):
        node_by_title(t)
    ok(node_by_title("weather station")["_path"].parent.parent.name == "Technology", "Meteorological station invested in technology")
    ok(node_by_title("Bakery")["type"] == "seed", "type «sprout» applied")
    ok(node_by_title("weather station")["applies_to"] == ["[[Dacha and garden]]"], "applies_to moved from a draft with a new name")

    step("3. Layout, questions, aspects, base")
    ents = entity_files()
    ok(len(ents) == 8, f"created 8 record (diary segments + others): {len(ents)}")
    p, fm, raw = entity_by_text("photo")
    ok(fm["quarantine"] and "_review" in p.parts, "lapse — quarantine")
    p, fm, raw = entity_by_text("mill")
    ok(fm["quarantine"] and fm["review_reason"] == "user_hint_mismatch", "hint differs from content → quarantine")
    p, fm, raw = entity_by_text("tomatoes")
    ok(fm["container"] == "[[Dacha and garden]]" and fm["segment"] == "1-2", "diary-piece 1-2 → Dacha and garden")
    p, fm, raw = entity_by_text("timer watering option")
    ok(fm["incomplete"] and not find_q("clarify", lambda q: q["data"]["entity"] == fm["id"]), "into Bootstrap half-recording")
    p, fm, raw = entity_by_text("wired")
    ok(fm["compacted"] and "Condensed version" in raw, "dialogue, field-based")
    ok(fm["status"] == "processed" and fm["aspect_ids"], "dialogue, There are references to aspects")
    ok(find_q("classify") and find_q("clarify") and find_q("also_in") and find_q("conflict") and find_q("structure_sub"),
       "questions: classification, clarification, record, contradiction, bottom-container")
    pv = pool("weather station")
    ok(any(c["composite_type"] == "resolved_decision" for c in pv["composites"].values()), "composite «reasoned»")
    ok(pv["conflicts"] and pv["conflicts"][0]["status"] == "asked", "Contradiction raised after filter")
    b = base("weather station")
    ok(b["groups"][0]["type"] == "resolved_decision", "base-line — priority table")
    ok(any(it.get("assumed_loser") for g in b["groups"] for it in g["items"]), "optimistic assumptions are noted in the database")
    bk = base("Bakery")
    ok(bk["excluded"], "Value below the threshold is not included in the database")
    ok((node_by_title("weather station")["_path"].parent / "_aspects.md").exists(), "pool-window")
    ok("Read only" in (node_by_title("weather station")["_path"].parent / "_synthesis.md").read_text(encoding="utf-8"), "base-case — reading")
    logs = V / "_logs"
    ok(any(logs.glob("reasoning *.md")) and any(logs.glob("change *.md")), "Logic of changes and reasoning are conducted")
    refl = (V / ".system" / "reflection.jsonl").read_text(encoding="utf-8")
    ok('"kind": "classification"' in refl and '"kind": "compaction"' in refl, "reflection log")
    ok((V / ".obsidian" / "snippets" / "vtoroy-mozg.css").exists(), "CSS flower-making")

    step("4. Questions and corrections YAML («challenge»)")
    answer("classify", text="Household (sprout)", where=lambda q: "photo" in q["text"])
    answer("clarify", text="Photo from the dacha 2010 year-end, I want to digitize", where=lambda q: not q.get("options"))
    answer("clarify", pick=0, where=lambda q: bool(q.get("options")))
    answer("classify", pick="Bakery", where=lambda q: "bakery" in q["text"].lower())
    answer("also_in", pick=0)
    answer("conflict", pick="fork")
    answer("structure_sub", pick=0)
    p, fm, raw = entity_by_text("strange dream")
    p.write_text(raw.replace("container: '[[Health]]'", "container: '[[Dacha and garden]]'"), encoding="utf-8")
    out = run("run")
    ok("Answers accepted: 7" in out, "accepted 7 answer")
    node_by_title("Household")
    ok(node_by_title("Household")["type"] == "seed", "The free response created the right type of container.")
    p, fm, raw = entity_by_text("old photos")
    ok(fm["container"] == "[[Household]]" and not fm["quarantine"] and fm["status"] == "processed", "quarantine record decomposed and processed")
    p, fm, raw = entity_by_text("Photo from the dacha 2010")
    ok("Clarification of the record [[" in raw, "The answer to the clarification became a new entry with reference to the original")
    p, fm, raw = entity_by_text("weather station can be put")
    ok("_shared" in p.parts and fm["shared"] and fm["also_in"], "post-record _shared")
    ok("Shared entries" in node_by_title("Dacha and garden")["_path"].read_text(encoding="utf-8"), "In the container file there are links to the general records")
    tep = node_by_title("Greenhouse")
    ok(tep["parent"] == "[[Dacha and garden]]", "bottom-The container is created inside the garden and garden")
    p, fm, raw = entity_by_text("tomatoes")
    ok(fm["container"] == "[[Greenhouse]]" and "Greenhouse" in p.parts, "The recording moved into-folder")
    ok(any(a["source_entity"] == fm["id"] for a in pool("Greenhouse")["aspects"].values()), "aspects moved into the pool under-container")
    p, fm, raw = entity_by_text("strange dream")
    ok(fm["container"] == "[[Dacha and garden]]" and not any(a["source_entity"] == fm["id"] for a in pool("Health")["aspects"].values()),
       "editing container into YAML The recording and its aspects")
    pv = pool("weather station")
    ok(pv["conflicts"][0]["status"] == "resolved" and pv["conflicts"][0]["decision"] == "both", "fork")
    ok(any(it.get("fork") for g in base("weather station")["groups"] for it in g["items"]), "base: forward — fork")
    arch_q = (V / "_logs" / "file.md").read_text(encoding="utf-8")
    ok(arch_q.count("**Answer:**") >= 7, "The questions answered are archived")
    ok('"type": "decision"' in (V / ".system" / "reflection.jsonl").read_text(encoding="utf-8"), "user-generated — reflection-log")

    step("5. New thought «count: 100 ruble» → obsolescence")
    (V / "_staging" / "calculation.txt").write_text("15.06.2023\nhint: bakery\n\nCounted it.: Cost of bread at least 100 ruble, bakers rent and salary.\n", encoding="utf-8")
    out = run("run")
    q = find_q("outdated")
    ok(q and "50 ruble" in q[0]["text"] and "100 ruble" in q[0]["text"], "It is suggested to mark the old obsolete")
    ok(find_q("base_loss"), "drop-off → loss-proof")
    answer("outdated", pick=0)
    answer("base_loss", pick="Restore to the synthesis base")
    out = run("run")
    pk = pool("Bakery")
    old = [a for a in pk["aspects"].values() if "50 ruble" in a["text"]]
    ok(old and old[0]["status"] == "outdated" and old[0]["replaced_by"], "archaic, not removed")
    texts = [it["text"] for g in base("Bakery")["groups"] for it in g["items"]]
    ok(not any("50 ruble" in t for t in texts) and any("100 ruble" in t for t in texts), "synthesis base reassembled with new value")
    ok(any(it.get("pinned") and it["rank"] == "primary" for g in base("Bakery")["groups"] for it in g["items"]), "return element fixed")
    p, fm, raw = entity_by_text("Cost of a loaf of bread — 50")
    ok("Cost of a loaf of bread — 50 ruble" in raw, "The old thought remained untouched.")

    step("6. Phase 2: synthesis, version")
    out = run("synth", "Bakery")
    kf = node_by_title("Bakery")["_path"].parent
    ok((kf / "Summary.md").exists(), "composite")
    ok((kf / "Diary.md").exists(), "supplementary (Diary.) created")
    import yaml
    sfm = yaml.safe_load((kf / "Summary.md").read_text(encoding="utf-8").split("---")[1])
    ok(sfm["type"] == "product" and sfm["product_kind"] == "summary" and sfm["based_on_synthesis"], "YAML sectional 16.5")
    ok((V / ".system" / "versions" / ".git").exists(), "version-history git")
    out = run("synth", "Bakery")
    ok("Nothing new." in out or "Documents" in out, "re-synthesis worked")

    step("7. Manual editing of the product → record → build-up")
    sf = kf / "Summary.md"
    sf.write_text(sf.read_text(encoding="utf-8") + "\nNote by the author: summer 2024 year-end, budget 500 000 ruble.\n", encoding="utf-8")
    out = run("run")
    ok("manual document edits found: 1" in out.lower(), "editing of the document")
    p, fm, raw = entity_by_text("budget 500 000")
    ok(fm["content_type"] == "product_edit" and fm["container"] == "[[Bakery]]", "editing became a bakery record")
    out = run("synth", "Bakery")
    ok("Note by the author" in sf.read_text(encoding="utf-8"), "manual editing is preserved in the new version")
    lq = find_q("product_loss")
    ok(lq, "missing in new version of document → question")
    answer("product_loss", pick=2, where=lambda q: q["id"] == lq[0]["id"])
    for x in lq[1:]:
        answer("product_loss", pick=0, where=lambda q, x=x: q["id"] == x["id"])
    out = run("run")
    ok("Details." in sf.read_text(encoding="utf-8"), "The document is back to the previous version")
    out = run("run")
    ok("manual" not in out.lower(), "Recoiling is not considered manual editing")

    step("8. Correction of the text of the processed record, germ, run-off")
    p, fm, raw = entity_by_text("I like the idea of self-service.")
    p.write_text(raw.replace("I like the idea of self-service.", "I really like the idea of self-service."), encoding="utf-8")
    hp = node_by_title("Health")["_path"]
    hp.write_text(hp.read_text(encoding="utf-8").replace(f"last_modified: '{time.strftime('%Y-%m-%d')}'", "last_modified: '2020-01-01'")
                  .replace(f"last_modified: {time.strftime('%Y-%m-%d')}", "last_modified: 2020-01-01"), encoding="utf-8")
    out = run("run")
    ok(find_q("text_changed"), "Change in the text of the processed record is noticed")
    ok(find_q("dormant"), "germ → relevance")
    answer("text_changed", pick=0)
    answer("dormant", pick="Put on hold")
    (V / "_staging" / "watering-house.txt").write_text("20.06.2023\n\nThe timer in the country works perfectly., cucumbers grow.\n", encoding="utf-8")
    os.environ["FAKE_CRASH_ON"] = "Value"
    out = run("run", expect=2)
    ok("Unexpected program error" in out and (V / "_logs" / "mistake.log").exists(), "failure: log-message")
    del os.environ["FAKE_CRASH_ON"]
    out = run("run")
    p, fm, raw = entity_by_text("I like the idea of self-service.")
    ok("very" not in raw, "source code returned")
    entity_by_text("I really like the idea of self-service.")  # editing became a new record
    ok(node_by_title("Health")["container_status"] == "dormant", "germ-frozen")
    ok(not state()["dirty"], "After the failure, the run continued and brought to the end.")

    step("9. Changing the embedding model → vector-count")
    write_settings(emb_model="fake-2")
    out = run("run")
    ok("The embedding model has changed" in out, "count-off")
    meta = json.loads((V / ".system" / "vectors" / "meta.json").read_text(encoding="utf-8"))
    ok(meta["model"] == "fake:fake-2", "vectors recalculated under the new model")

    step("10. Manual mode via the web-chat")
    write_settings(llm_mode="webchat", emb_model="fake-2")
    (V / "_staging" / "crop-house.txt").write_text("25.06.2023\n\nI picked up the first cucumbers in the country, greenhouse paid off.\n", encoding="utf-8")
    out = run("run")
    ok("Stopped pending response from the web-chat" in out, "The run stopped and awaits a response.")
    idx = json.loads((V / ".system" / "webchat.json").read_text(encoding="utf-8"))
    rec = list(idx["pending"].values())[0]
    (V / "_web-chat" / rec["ans"]).write_text("not json altogether", encoding="utf-8")
    out = run("run")
    ok("did not pass validation" in (V / "_web-chat" / rec["req"]).read_text(encoding="utf-8"), "format error — request to re-question in the request file")
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
            (V / "_web-chat" / rec["ans"]).write_text(ans, encoding="utf-8")
        out = run("run")
        rounds += 1
        assert rounds < 20, "web-based-chatting doesnt fit"
    entity_by_text("picked up the first cucumbers")
    ok(rounds >= 2 and "Ready." in out, f"The manual mode brought the run to the end {rounds} exchange")
    ok(len(list((V / "_web-chat" / "ready").glob("*.md"))) >= 4, "processed requests and responses — file «ready»")

    step("11. Rerun without a new run — modelless")
    write_settings(emb_model="fake-2")
    before = (V / ".system" / "usage.jsonl").read_text(encoding="utf-8").count("\n")
    out = run("run")
    after = (V / ".system" / "usage.jsonl").read_text(encoding="utf-8").count("\n")
    ok(after == before and "Nothing new." in out, "idle-runs waste nothing")

    step("12. Other teams")
    out = run("status")
    ok("Containers:" in out, "status")
    out = run("check")
    ok("All checks passed." in out, "check")
    out = run("revalidate", "Bakery", "--yes")
    ok("Revalidation complete:" in out, "revalidate")
    out = run("patterns")
    ok("composite" in out, "patterns")
    out = run("synth", "No, theres no such thing.", expect=1)
    ok("found" in out, "A clear error for an unknown container")

    step("13. Hand-made: type-Russian and container, hand-operated")
    import yaml
    b = node_by_title("Household")
    unsorted_before = len(list((V / "_unsorted").glob("*.md")))
    raw = b["_path"].read_text(encoding="utf-8")
    b["_path"].write_text(raw.replace(f"type: {b['type']}", "type: Project", 1), encoding="utf-8")
    (V / "Repairs.md").write_text("---\ntype: project\n---\n\nRepair of the apartment: kitchen.\n", encoding="utf-8")
    bak = node_by_title("Bakery")
    (bak["_path"].parent / "Menu.md").write_text("---\ntype: sprout\ndescription: What to sell\n---\n", encoding="utf-8")
    (V / "Travels").mkdir()
    (V / "Travels" / "Travels.md").write_text("---\ntype: question\n---\n\nWhere to go in the summer?\n", encoding="utf-8")
    (V / "Different.").mkdir()
    (V / "Different." / "Household.md").write_text("---\ntype: project\n---\n", encoding="utf-8")
    photo, _, _ = entity_by_text("old photos")
    raw = photo.read_text(encoding="utf-8")
    photo.write_text(raw.replace("status: processed", "status: obsolete", 1), encoding="utf-8")
    out = run("run")
    ok("status: outdated" in photo.read_text(encoding="utf-8")
       and all(a["status"] == "outdated" for a in pool("Household")["aspects"].values() if a["source_entity"] == yaml.safe_load(raw.split("---")[1])["id"]),
       "«status: Obsolete.» down-Russianly understood: The recording and its aspects are outdated")
    b2 = node_by_title("Household")
    ok(b2["type"] == "project" and b2["id"] == b["id"], "«type: Project» down-Russianly understood, container")
    ok(len(list((V / "_unsorted").glob("*.md"))) == unsorted_before, "record «Household» not lost")
    r = node_by_title("Repairs")
    ok(r["_path"] == V / "Repairs" / "Repairs.md" and str(r["id"]).startswith("k") and not r.get("parent_id")
       and r["description"].startswith("Repair of the apartment"), "note «Repairs» It became a container in its folder.")
    m = node_by_title("Menu")
    ok(m["_path"] == bak["_path"].parent / "Menu" / "Menu.md" and m["parent_id"] == bak["id"] and m["type"] == "seed",
       "«Menu» file «Bakery» It became a sprout inside her.")
    t = node_by_title("Travels")
    ok(t["_path"] == V / "Travels" / "Travels.md" and t["type"] == "question", "note-file — top-level question")
    ok("not become a container" in out and (V / "Different." / "Household.md").exists(), "note of the same name not accepted, warning")
    log = "".join(x.read_text(encoding="utf-8") for x in (V / "_logs").glob("change *.md"))
    ok("container [[Repairs]]" in log and "inside [[Bakery]]" in log, "creation is recorded in the change log")
    r["_path"].write_text(r["_path"].read_text(encoding="utf-8").replace("container_status: active", "container_status: frozen"),
                          encoding="utf-8")
    out = run("run")
    ok(node_by_title("Repairs")["container_status"] == "dormant", "«container_status: frozen» understood")
    out = run("run")
    ok("Nothing new." in out and "not become a container" in out, "run-over doesnt break anything")
    plugin_commands()
    v25_checks()
    v26_checks()
    v27_checks()
    print(f"\nIts gone.. Dough storage: {V}")


def rj(*args, expect=0):
    """Flag team --json, How the plugin calls: returns the conclusion and the disassembled result @@RESULT."""
    out = run("--json", *args, expect=expect)
    lines = [x for x in out.splitlines() if x.startswith("@@RESULT ")]
    assert lines, f"no line @@RESULT conclusionally: {out[-500:]}"
    return out, json.loads(lines[-1][len("@@RESULT "):])


def refl():
    return [json.loads(x) for x in (V / ".system" / "reflection.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def plugin_commands():
    import yaml
    from brain import cli as CLI
    step("14. Plugin: snapshot, answers, setting, their container sills, AI, «Stop.», installation")
    out, r = rj("snapshot")
    ui = json.loads((V / ".system" / "ui.json").read_text(encoding="utf-8"))
    ok(r["ok"] and ui["status"]["containers"] == len(ui["containers"]) > 0 and ui["threshold_info"]["classification"]["label"],
       "snapshot ui.json: container, status, thresholds")
    bak = next(c for c in ui["containers"] if c["title"] == "Bakery")
    ok(bak["thresholds"]["classification"] == {"value": 70, "source": "global", "from": None}, "The container shows the current thresholds and their source.")
    ok(all({"id", "title", "text", "options"} <= set(q) for q in ui["questions"]), "photo-question — variant")

    # new thought from the plugin: service-line mode — without questioning the regime
    (V / "_staging" / "blinds.txt").write_text("05.06.2024\nmode: steady_state\n\nI need to buy new curtains in the bedroom., scorched.\n",
                                             encoding="utf-8")
    out, r = rj("run")
    it = next(i for i in state()["items"].values() if i["name"] == "blinds.txt")
    ok(it["mode"] == "steady_state" and not find_q("mode", lambda q: q["data"].get("item") == it["id"]), "«mode: steady_state» — without questioning the regime")
    ok(r["title"] == "Ready." and r["code"] == 0 and r["questions"] >= 1, "plugin-shot (@@RESULT)")
    q = find_q("classify", lambda q: "curtains" in q["text"])[0]
    out, r = rj("answer", q["id"], "--option", "99", expect=1)
    ok("has no option" in r["error"], "wrong-number — misunderstood")
    out, r = rj("answer", q["id"], "--text", "Household")
    ok(r["accepted"] and q["id"] not in qs(), "The answer from the plugin is applied immediately, closed")
    p_, fm, raw = entity_by_text("curtains")
    ok(fm["container"] == "[[Household]]" and "curtains" in (V / "_logs" / "file.md").read_text(encoding="utf-8"),
       "record-posted «Household», question — archived")
    out, r = rj("answer", q["id"], "--option", "0", expect=1)
    ok("no longer open" in r["error"].lower(), "repeating — rejected")

    # setting: reading, check-out, key
    out, r = rj("settings")
    st_ = r["settings"]
    ok(st_["values"]["thresholds"]["classification"] == 70 and any(sec["id"] == "roles" for sec in st_["schema"]), "settings and schema for the plugin")
    patch = ROOT / "patch.json"
    patch.write_text(json.dumps({"thresholds": {"classification": 500}}), encoding="utf-8")
    out, r = rj("settings", "--set-json", str(patch), expect=1)
    ok("0 to 100" in r["error"] and "classification: 70" not in SETTINGS.read_text(encoding="utf-8"), "misvalue does not persist")
    patch.write_text(json.dumps({"llm": {"roles": {"Synthesis": {"temperature": 0.5}}}}), encoding="utf-8")
    out, r = rj("settings", "--set-json", str(patch), expect=1)
    ok("id profile" in r["error"], "You can only take a step to your profile or web page.-chat")
    patch.write_text(json.dumps({"thresholds": {"classification": 72},
                                 "llm": {"profiles": {"p2": {"name": "Strong.", "kind": "cloud", "model": "fake-strong",
                                                             "temperature": 0.5}}, "roles": {"Synthesis": "p2"}},
                                 "sources": [{"name": "note", "color": "#60A5FA", "compaction_shift": 0},
                                             {"name": "Voice.", "color": "#F97316", "compaction_shift": 10}]}), encoding="utf-8")
    out, r = rj("settings", "--set-json", str(patch))
    txt = SETTINGS.read_text(encoding="utf-8")
    from brain.config import load_config
    c2 = load_config(SETTINGS)
    p2 = next((x for x in c2["llm"]["profiles"] if x["id"] == "p2"), {})
    ok(c2["thresholds"]["classification"] == 72 and c2["llm"]["roles"]["Synthesis"] == "p2" and p2.get("temperature") == 0.5
       and p2.get("api_key_file") == "" and p2.get("max_input_chars") == 300000
       and [x["name"] for x in c2["sources"]] == ["note", "Voice."] and c2["llm"]["mode"] == "fake",
       "settings are saved and read back")
    ok("# Automatic placement" in txt and (ROOT / "settings.yaml.bak").exists(), "settings.yaml rewritten, former — into .bak")
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO("secretive-key\n")
        out, r = rj("settings", "--key", "llm")
        ok((ROOT / "api_key.txt").read_text(encoding="utf-8").strip() == "secretive-key" and r["settings"]["keys"]["llm"],
           "plugin — file next to the program")
        sys.stdin = io.StringIO("\n")
        rj("settings", "--key", "llm")
        ok(not (ROOT / "api_key.txt").exists(), "empty key deletes the file")
        sys.stdin = io.StringIO("key-second-second-profile\n")
        out, r = rj("settings", "--key", "profile:p2")
        c3 = load_config(SETTINGS)
        p2 = next(x for x in c3["llm"]["profiles"] if x["id"] == "p2")
        ok(p2["api_key_file"] == "api_key_p2.txt" and (ROOT / "api_key_p2.txt").read_text(encoding="utf-8").strip() == "key-second-second-profile"
           and r["settings"]["keys"]["profiles"]["p2"], "key — file, profile remembers his name")
        sys.stdin = io.StringIO("ghp_test\n")
        out, r = rj("settings", "--key", "github", expect=1)
        ok("Unknown key" in r["error"] and not (ROOT / "github_token.txt").exists(), "token GitHub no more (v2.7)")
    finally:
        sys.stdin = old_stdin
    write_settings()

    # their container sills
    kp = node_by_title("Bakery")["_path"]
    fm_, body_ = kp.read_text(encoding="utf-8").split("---\n", 2)[1:]
    d = yaml.safe_load(fm_)
    d["thresholds"] = {"classification": 95, "value_min": 10, "sealing": "abc"}
    kp.write_text("---\n" + yaml.safe_dump(d, allow_unicode=True, sort_keys=False) + "---\n" + body_, encoding="utf-8")
    excluded_before = len(base("Bakery")["excluded"])
    (V / "_staging" / "bread-bread.txt").write_text("06.06.2024\nmode: steady_state\n\nBread in the bakery can be sold takeaway.\n", encoding="utf-8")
    out, r = rj("run")
    p_, fm, raw = entity_by_text("takeaway")
    rec = [x for x in refl() if x.get("kind") == "classification" and x.get("subject") == fm["id"]][-1]
    ok(fm["quarantine"] and rec["confidence"] == 88 and rec["threshold"] == 95, "layout-threshold 95: confidently 88 — question")
    ok("sealing" in " ".join(r["warnings"]) and "abc" in " ".join(r["warnings"]), "threshold-definition — warning")
    b = base("Bakery")
    ok(b["thresholds"]["value_min"] == 10 and len(b["excluded"]) < excluded_before, "value-point — base reassembled without a model")
    chg = "".join(x.read_text(encoding="utf-8") for x in (V / "_logs").glob("change *.md"))
    ok("[[Bakery]]: classification: general → 95" in chg, "Changes in thresholds are recorded in the change log")
    ui = json.loads((V / ".system" / "ui.json").read_text(encoding="utf-8"))
    bak = next(c for c in ui["containers"] if c["title"] == "Bakery")
    ok(bak["thresholds"]["classification"]["source"] == "own" and bak["overrides"] == {"classification": 95, "value_min": 10},
       "photographed — their container sills")
    menu = next(c for c in ui["containers"] if c["title"] == "Menu")
    ok(menu["thresholds"]["classification"] == {"value": 95, "source": "parent", "from": "Bakery"}, "The nested container inherits the thresholds of the parent")
    q = find_q("classify", lambda q: q["data"].get("entity") == fm["id"])[0]
    rj("answer", q["id"], "--option", "0")
    ok(entity_by_text("takeaway")[1]["container"] == "[[Bakery]]", "reply «model» — bakery")

    # AI Threshold Council
    out, r = rj("advise", "Bakery")
    adv = r["advice"]
    cl = next(x for x in adv["recommendations"] if x["name"] == "classification")
    ok(cl["current"] == 95 and cl["value"] == 85 and adv["summary"] and adv["brief"], "AI: drop down 95 → 85")
    ok(not any(x["name"] == "value_min" for x in adv["recommendations"]), "council «leave it» It is not shown as a change.")
    ok(any("?" not in b_ and "model was correct — 1" in b_ for b_ in adv["brief"]), "Container decision statistics are calculated")
    reas = "".join(x.read_text(encoding="utf-8") for x in (V / "_logs").glob("reasoning *.md"))
    tries = [json.loads(x) for x in (V / ".system" / "usage.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    ok("Thresholds" in reas and r["calls"].get("Thresholds") == 1 and sum(t["prompt"] == "Thresholds" for t in tries) == 2,
       "Responding to an incorrect threshold is sent for correction")
    d = yaml.safe_load(kp.read_text(encoding="utf-8").split("---\n", 2)[1])
    d["thresholds"] = {"classification": 85, "value_min": 10}
    kp.write_text("---\n" + yaml.safe_dump(d, allow_unicode=True, sort_keys=False) + "---\n" + kp.read_text(encoding="utf-8").split("---\n", 2)[2],
                  encoding="utf-8")
    rj("run")
    dec = [x for x in refl() if x.get("type") == "decision" and x.get("kind") == "thresholds_advice"]
    ok(dec and dec[-1]["matched"] == "partial" and dec[-1]["accepted"] == ["classification"] and dec[-1]["ref"] == adv["ref"],
       "partly-administered — pair «council — decision» reflectively")
    out, r = rj("advise", "Menu")
    ok(any(x["name"] == "seed_dormancy_days" for x in r["advice"]["recommendations"]), "For the sprouting advice may concern waiting days")
    old_stdin, sys.stdin = sys.stdin, io.StringIO("")  # consoleless: select a container from the list nowhere
    try:
        out, r = rj("advise", expect=1)
    finally:
        sys.stdin = old_stdin
    ok('advise "Name of name"' in r["error"], "Tips for Thresholds Without a Name and Without a Console — tip-off advise")
    from brain import schema as SCH
    dup, cls = SCH.THRESHOLDS["duplicate_similarity"], SCH.THRESHOLDS["classification"]
    ok(SCH.parse_number("86%", dup) == 0.86 and SCH.parse_number("0,86", dup) == 0.86 and SCH.parse_number("86", dup) is None
       and SCH.parse_number("80%", cls) == 80, "threshold: «86%» similarly — it 0,86, «80%» scale-wise 0–100 — 80")

    # container-style → fusion
    d = yaml.safe_load(kp.read_text(encoding="utf-8").split("---\n", 2)[1])
    d["style"] = "Write like a business-plan, numerically."
    kp.write_text("---\n" + yaml.safe_dump(d, allow_unicode=True, sort_keys=False) + "---\n" + kp.read_text(encoding="utf-8").split("---\n", 2)[2],
                  encoding="utf-8")
    rj("run")
    os.environ["BRAIN_TEST_WEBCHAT_VARS"] = "1"
    out, r = rj("synth", node_by_title("Bakery")["id"])
    doc = node_by_title("Bakery")["_path"].parent / "Summary.md"
    ok(r["ok"] and not r.get("unchanged") and doc.exists() and "container style" in doc.read_text(encoding="utf-8"),
       "Phase 2 down id container (plug-in), container-style — plough-in")
    out, r = rj("synth", "Bakery")
    ok(r.get("unchanged") is True, "re-phase 2 changeless — flag «document»")
    out, r = rj("revalidate", "Bakery", "--count")
    ok(r["count"] >= 1, "validation: first, just counting")

    # «Stop.» midway
    os.environ["FAKE_STOP_ON"] = "Classification"
    os.environ["FAKE_STOP_FILE"] = str(V / ".system" / "stop")
    (V / "_staging" / "cottage.txt").write_text("07.06.2024\nmode: steady_state\n\nIn the country, you need to tie tomatoes in the greenhouse.\n", encoding="utf-8")
    out, r = rj("run", expect=1)
    ok(r.get("stopped") and r["title"] == "Stopped." and not (V / ".system" / "stop").exists(), "«Stop.» plugin stops the run")
    del os.environ["FAKE_STOP_ON"]
    out, r = rj("run")
    ents = [e for e in entity_files() if "tie tomatoes" in e[2]]
    ok(len(ents) == 1 and r["code"] == 0, "The next launch continued from the same place., doubleless")
    (V / ".system" / "stop").write_text("", encoding="utf-8")
    out, r = rj("run")
    ok(r["code"] == 0 and not r.get("stopped"), "file-file «Stop.» It does not interfere with a new launch")

    # --vault: Plugin transfers open storage
    SETTINGS.write_text(SETTINGS.read_text(encoding="utf-8").replace(V.as_posix(), (ROOT / "No, no.").as_posix()), encoding="utf-8")
    out, r = run_vault_snapshot()
    ok(r["ok"], "--vault redefinition of the vault settings.yaml")
    write_settings()

    # plug-in
    from brain import install as INST
    fake_prog = ROOT / "programme"
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
       "plugin copied into .obsidian/plugins, path")
    ok("vtoroy-mozg" in json.loads((V / ".obsidian" / "community-plugins.json").read_text(encoding="utf-8")), "plugin included in the list of third-party")


def run_with(settings: Path, *args, stdin: str | None = None, expect=0):
    """Team with another settings.yaml and (if necessary) standard-input responses — How does a plugin write?."""
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
        raise AssertionError(f"brain {' '.join(args)}: code {code}, expected {expect}")
    res = [x for x in out.splitlines() if x.startswith("@@RESULT ")]
    return out, (json.loads(res[-1][len("@@RESULT "):]) if res else None)


def tagged(out: str, tag: str) -> list:
    pre = f"@@{tag} "
    return [json.loads(x[len(pre):]) for x in out.splitlines() if x.startswith(pre)]


def v25_checks():
    from brain.config import load_config
    step("15. v2.5: customization, datebook, launcher, Questions through standard input, expense")
    # setting v2.4 with his own step models → profiles
    # pattern: No archives settings.yaml — At the first launch, it is created from settings.template.yaml
    import yaml
    from brain.config import ensure_settings, prepare, TEMPLATE_NAME
    tpl = APP / TEMPLATE_NAME
    ok(tpl.is_file(), "The sample settings are in the program folder")
    ok(prepare(yaml.safe_load(tpl.read_text(encoding="utf-8"))) == prepare({}), "pattern — flat-out (format)")
    fresh = ROOT / "fresh"
    fresh.mkdir(exist_ok=True)
    shutil.copy2(tpl, fresh / TEMPLATE_NAME)
    ok(ensure_settings(fresh / "settings.yaml") and (fresh / "settings.yaml").read_text(encoding="utf-8") == tpl.read_text(encoding="utf-8"),
       "first-launch: settings.yaml sampled")
    (fresh / "settings.yaml").write_text("vault: mine\n", encoding="utf-8")
    ok(not ensure_settings(fresh / "settings.yaml") and (fresh / "settings.yaml").read_text(encoding="utf-8") == "vault: mine\n",
       "existing settings.yaml specimen not touched")
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
    Synthesis: {{model: "glm-4.6-pro", temperature: 0.4}}
    Compaction: {{model: "glm-4.6-pro", temperature: 0.4}}
    Classification: {{base_url: "http://127.0.0.1:8080/v1", model: "qwen"}}
    Questions: {{mode: webchat}}
embeddings:
  mode: api
  base_url: "https://api.openai.com/v1"
  model: "text-embedding-3-small"
""", encoding="utf-8")
    c = load_config(old)
    L = c["llm"]
    P = {x["id"]: x for x in L["profiles"]}
    ok(L["mode"] == "cloud" and L["cloud_profile"] == "p1" and P["p1"]["model"] == "glm-4.6" and P["p1"]["max_input_chars"] == 200000
       and P["p1"]["api_key_file"] == "api_key.txt" and L["max_format_retries"] == 3, "v2.4: The main model became a profile p1 (former)")
    ok(L["roles"]["Synthesis"] == L["roles"]["Compaction"] == "p2" and P["p2"]["model"] == "glm-4.6-pro" and P["p2"]["temperature"] == 0.4
       and P["p2"]["api_key_file"] == "api_key.txt", "v2.4: similarly — one profile with the same key")
    ok(L["roles"]["Classification"] == "p3" and P["p3"]["kind"] == "local" and P["p3"]["api_key_file"] == "" and L["local_profile"] == "p3",
       "v2.4: step-server — localization, The key doesnt go there.")
    ok(L["roles"]["Questions"] == "webchat" and c["embeddings"]["mode"] == "cloud", "v2.4: web-based-Step chat and cloud emblems moved")
    patch = ROOT / "patch.json"
    patch.write_text("{}", encoding="utf-8")
    run_with(old, "--json", "settings", "--set-json", str(patch))
    txt = old.read_text(encoding="utf-8")
    ok("profiles:" in txt and 'cloud_profile: "p1"' in txt and load_config(old)["llm"] == c["llm"],
       "post-conservation settings.yaml — in a new way and reads the same")
    out, r = rj("settings")
    st_ = r["settings"]
    ok(st_["tabs"]["costs"] == "Expenses" and any(f["key"] == "prices.input" for f in st_["profile_fields"])
       and st_["profile_defaults"]["local"]["base_url"].startswith("http://127.0.0.1") and st_["defaults"]["budget"]["warn_pct"] == 80,
       "plug-in: tab, profilefields, silence")

    # journal: date-recording
    (V / "_staging" / "journal.txt").write_text(
        "My journal of spring.\n\n12.03.2021\nIts the bakerys turn again tonight.: We need a second baker for the weekend..\n\n"
        "02.04.2021\nI put a greenhouse in the cottage today., Ill plant cucumbers in May..\n\n"
        "15 April 2021\nI didnt sleep well tonight., sleep-deep — I need to go to bed earlier..\n", encoding="utf-8")
    out, r = rj("run")
    its = sorted([i for i in state()["items"].values() if i["name"].startswith("journal.txt")], key=lambda i: i["part"]["n"])
    ok(len(its) == 3 and [i["date"] for i in its] == ["2021-03-12", "2021-04-02", "2021-04-15"] and len({i["file"] for i in its}) == 1
       and its[0]["name"] == "journal.txt · 12.03.2021", "diary divided by date: three records with their dates, single-source")
    ents = {"baker": entity_by_text("the bakerys turn again"), "greenhouse": entity_by_text("I put a greenhouse in the cottage"), "sleep-deep": entity_by_text("sleep-deep")}
    ok(all(str(fm.get("source_part", "")).endswith(lab) for (_, fm, _), lab in zip(ents.values(), ("12.03.2021", "02.04.2021", "15.04.2021")))
       and str(ents["greenhouse"][1].get("created", ""))[:10] == "2021-04-02", "diary-book — date and part number")
    ok("My journal of spring" in ents["baker"][2] and "02.04.2021" not in ents["greenhouse"][2].split("---", 2)[2],
       "filehead — first-hand; date line in the record does not fall")
    ok(any("split" in m or "date-by-date" in m for m in r["messages"]), "The division is said at the end of the launch")

    # Large Startup Assessment and Questions through Standard Input
    (V / "_staging" / "bakery-plan.txt").write_text("08.06.2024\nmode: steady_state\n\nBakery: mill offers discount on flour "
                                                  "ordering 20 kilogram.\n", encoding="utf-8")
    out, r = rj("estimate", "run")
    e = r["estimate"]
    ok(e["calls"] >= 2 and e["steps"].get("Classification") == 1 and e["lines"] and e["cost"] is None and not r["over"],
       "phase-assessment 1 launch: step-by-step, costlessly")
    write_settings(extra="estimate:\n  calls: 1\n")
    out, r = run_with(SETTINGS, "--json", "--ask-stdin", "run", stdin='{"choice": 1}\n')
    asks = tagged(out, "ASK")
    ok(asks and asks[0]["id"] == "estimate" and asks[0]["options"] == ["Start", "Cancel"] and asks[0]["lines"]
       and r.get("cancelled") and (V / "_staging" / "bakery-plan.txt").exists(), "launch: evaluative, «Cancellation» — nothing touched")
    out, r = run_with(SETTINGS, "--json", "--ask-stdin", "run", stdin="")
    ok(r.get("cancelled") and (V / "_staging" / "bakery-plan.txt").exists(), "Question window closed without answer — too")
    out, r = run_with(SETTINGS, "--json", "--ask-stdin", "run", stdin='{"choice": 0}\n')
    prog, waits, used = tagged(out, "PROGRESS"), tagged(out, "WAIT"), tagged(out, "USAGE")
    ok(r["ok"] and not (V / "_staging" / "bakery-plan.txt").exists() and r["run_usage"]["calls"] == len(used) >= 1 and waits,
       "«Launch.» — launch; flow lines and waiting for the model response — plug-in")
    ok(any(x["stage"] == "File analysis" and x["n"] == 1 and x["total"] == 1 for x in prog) and used[-1]["run"]["calls"] == len(used),
       "progression («1 from 1») and the cost of starting up the cumulative")
    ok(r["elapsed"] >= 0 and r["run_id"] and r["estimate"]["calls"] >= 1, "eventually — duration, launch number and evaluation")
    log = next((V / "_logs").glob("change *.md")).read_text(encoding="utf-8")
    ok("programme · Phase 1: ready. — duration" in log, "launch duration and cost — change-book")
    write_settings()

    # Resilience always asks
    out, r = run_with(SETTINGS, "--json", "--ask-stdin", "revalidate", "Bakery", stdin='{"choice": 1}\n')
    ok(r.get("cancelled") and tagged(out, "ASK")[0]["id"] == "estimate" and r["estimate"]["steps"] == {"Classification": r["count"]},
       "validation: grading-question, «Cancellation» — modelless")
    out, r = rj("revalidate", "Bakery", expect=1)
    ok("--yes" in r["error"], "Re-validation without the possibility of asking — only --yes")

    # expense
    out, r = rj("usage")
    u = r["usage"]
    ok(u["totals"]["all"]["calls"] > 0 and u["current"]["key"] == "p1" and any(x["name"] == "Classification" for x in u["steps"])
       and len(u["days"]) == 31 and u["runs"], "expense: result, current profile, stepping-step, days, launches")
    with open(V / ".system" / "usage.jsonl", "a", encoding="utf-8") as f:  # record (v2.4)
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "prompt": "Synthesis", "model": "fake",
                            "usage": {"prompt_tokens": 1000, "completion_tokens": 200}, "chars_in": 3000, "chars_out": 600}) + "\n")
    out, r2 = rj("usage")
    ok(r2["usage"]["totals"]["all"]["calls"] == u["totals"]["all"]["calls"] + 1
       and r2["usage"]["totals"]["all"]["in"] == u["totals"]["all"]["in"] + 1000, "paste-book (v2.4) counted")
    out = run("status")
    ok("Expenses for today" in out and "This month:" in out, "status")
    ui = json.loads((V / ".system" / "ui.json").read_text(encoding="utf-8"))
    ok(ui["usage"]["totals"]["all"]["calls"] >= 1 and "budget" in ui["usage"], "expense — panel-shot")


def v26_checks():
    from brain import install as INST
    step("16. v2.6: installation «one-on-one», cleaning .bat")
    # former .bat clean up; user files — no
    pd = ROOT / "old-fashioned-programme"
    pd.mkdir(exist_ok=True)
    for n in INST.LEGACY_FILES + ("Install.bat", "My script..bat"):
        (pd / n).write_text("@echo off\r\n", encoding="utf-8")
    removed = INST.remove_legacy(pd)
    left = sorted(p.name for p in pd.iterdir())
    ok(sorted(removed) == sorted(INST.LEGACY_FILES) and left == sorted(["Install.bat", "My script..bat"]),
       f"former .bat cleaned ({len(removed)}), «Install.bat» And their files are still there.")
    # after updating 2.5 (Her updater didnt know about the cleaning.) — sweep away any team
    (ROOT / "Status.bat").write_text("@echo off\r\n", encoding="utf-8")
    run("status")
    ok(not (ROOT / "Status.bat").exists(), "Each team removes the remaining ones. .bat")

    # storage obsidian.json: open-minded — first, later; non-existent .obsidian — past
    cfgdir = ROOT / "obsidian-config"
    cfgdir.mkdir(exist_ok=True)
    va, vb, vc = ROOT / "vault", ROOT / "storage", ROOT / "simple folder"
    for d in (va, vb):
        (d / ".obsidian").mkdir(parents=True, exist_ok=True)
    vc.mkdir(exist_ok=True)
    (cfgdir / "obsidian.json").write_text(json.dumps({"vaults": {
        "1": {"path": str(vb), "ts": 2000},
        "2": {"path": str(va), "ts": 1000, "open": True},
        "3": {"path": str(ROOT / "remote"), "ts": 3000},
        "4": {"path": str(vc), "ts": 4000},
    }}), encoding="utf-8")
    os.environ.update({"BRAIN_OBSIDIAN_CONFIG": str(cfgdir), "BRAIN_NO_OPEN": "1", "BRAIN_OBSIDIAN_RUNNING": "0"})
    saved = INST.PROGRAM_DIR
    try:
        found = INST.find_vaults()
        ok(found == [va, vb], f"storage Obsidian found: {[p.name for p in found]}")
        ok(INST.choose_vault(None, False) == va and INST.choose_vault(vb, False) == vb,
           "questionable: setting-room, now-open")
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
        ok(pick2 == vb and pick_path == vb and "Obsidian vault" in buf.getvalue(),
           "storage: numbered and inserted (fileless .obsidian — ask)")

        # setup: plugin, storage-box — into settings.yaml, former .bat cleaned
        fake_prog = ROOT / "programme"
        for n in ("Phase 1.bat", "Update.bat"):
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
           "setup: plugin installed and enabled")
        import yaml
        ok(yaml.safe_load(SETTINGS.read_text(encoding="utf-8"))["vault"] == vb.as_posix(), "setup: vault folder is inscribed in settings.yaml")
        ok(sorted(r["removed"]) == sorted(["Update.bat", "Phase 1.bat"]) and not (ROOT / "Phase 1.bat").exists(), "setup: former .bat cleaned")
        ok("Next steps in Obsidian" in out and "Restart Obsidian to load the plugin" not in out, "setup: clues, what to do")
        write_settings()
        # Obsidian open-minded — remind me to restart
        os.environ["BRAIN_OBSIDIAN_RUNNING"] = "1"
        INST.PROGRAM_DIR = fake_prog
        try:
            out, r = rj("setup", str(vb))
        finally:
            INST.PROGRAM_DIR = saved
        ok(r["ok"] and "Restart Obsidian to load the plugin" in out, "setup open-minded Obsidian: reminder to restart it")
        write_settings()
        out, r = rj("setup", str(vc), expect=1)
        ok("Obsidian vault" in r["error"], "setup file-less — misunderstood")
    finally:
        for k in ("BRAIN_OBSIDIAN_CONFIG", "BRAIN_NO_OPEN", "BRAIN_OBSIDIAN_RUNNING"):
            os.environ.pop(k, None)
        INST.PROGRAM_DIR = saved



def v27_checks():
    """v2.7: his own embedding model on llama.cpp (downloading, launch, self-start, stop); tokenless updates."""
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
    step("17. v2.7: embedding llama.cpp — downloading, launch, self-start; tokenless updates")

    # customization of previous versions
    old = prepare({"embeddings": {"mode": "local", "base_url": "http://localhost:11434/v1", "model": "qwen3-embedding:8b-q8_0"},
                   "updates": {"check_on_start": False, "repo": "https://github.com/me/brain", "token_file": "github_token.txt"}})
    ok(old["embeddings"]["base_url"] == "http://127.0.0.1:8081/v1" and old["embeddings"]["model"] == L.ALIAS
       and old["embeddings"]["server"] == L.SERVER_DEFAULTS, "elbow-ding (Ollama) → model llama.cpp")
    own = prepare({"embeddings": {"mode": "local", "base_url": "http://192.168.1.5:9000/v1", "model": "mine-model"}})
    ok(own["embeddings"]["base_url"] == "http://192.168.1.5:9000/v1" and own["embeddings"]["model"] == "mine-model",
       "Your e-mail server in the settings is not affected")
    ok(old["updates"] == {"check_on_start": False}, "from «Updates» Removed the link to the repository and token")
    errs = L.check_params(dict(L.SERVER_DEFAULTS, ctx=100, device="tpu", port=80, gpu_layers="much"))
    ok(len(errs) == 4 and any(".ctx:" in e for e in errs) and any(".port:" in e for e in errs), "launcher — misunderstood")
    out, r = rj("settings")
    ok(r["settings"]["update_repo"] == UPD.repo_link(), "Plugin knows the link to the repository (from brain/__init__.py)")
    saved_repo = os.environ.pop("BRAIN_UPDATE_REPO", None)
    saved_const = UPD.UPDATE_REPO
    UPD.UPDATE_REPO = ""
    try:
        out, r = rj("update", "--check", expect=1)
        ok("UPDATE_REPO" in r["error"] and "brain/__init__.py" in r["error"], "linkless — spoken, where to put it")
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
    model = bytes(range(256)) * (3 * 4096) + b"gguf-tail" * 1000  # ~3,1 MB instead of 6,9 GB
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
        return out, next(x for x in r["check"] if x["name"] == "Embeddings")

    try:
        out, r = run_with(LS, "--json", "llama", "status", "--hw")
        st = r["llama"]
        ok(not st["model"]["exists"] and st["builds"] == {} and not st["server"]["running"] and st["configured"]
           and st["hardware"]["ram_gb"] == 32 and [i["what"] for i in st["plan"]["download"]] == ["model", "cpu"],
           "condition: model llama.cpp flat-loaded, default — server, Ill have to download.")

        # downloading: Continue and finish after the break; archive llama.cpp — via backup address
        mdir.mkdir()
        (mdir / (L.MODEL["file"] + ".part")).write_bytes(model[: 1 << 20])
        hub.break_once = 1 << 20
        out, r = run_with(LS, "--json", "llama", "download")
        ok(r["ok"] and r["title"] == "Downloaded." and mp.read_bytes() == model and not (mdir / (L.MODEL["file"] + ".part")).exists(),
           "model Hugging Face")
        ok(hub.ranges == [f"bytes={1 << 20}-", f"bytes={2 << 20}-"], f"pumping: from the place of the previous download and after the break ({hub.ranges})")
        prog = tagged(out, "PROGRESS")
        mprog = [x for x in prog if x["stage"] == "Downloading the model"]
        ok(mprog and all(x["unit"] == "%" and x["total"] == 100 for x in mprog) and mprog[-1]["n"] == 100 and " from " in mprog[-1]["item"]
           and any(x["stage"] == "File check." for x in prog), f"downloading — percentages for stripes in the panel ({[x['n'] for x in mprog]})")
        b = LP / "llama.cpp" / "cpu"
        ok((b / "llama-server").is_file() and os.access(b / "llama-server", os.X_OK) and (b / "libggml-base.so").is_file()
           and json.loads((b / "build.json").read_text(encoding="utf-8"))["tag"] == "b9999"
           and not any((LP / "llama.cpp" / "_download").iterdir()), "llama.cpp jump-off GitHub and unpacked llama.cpp/cpu")
        ok(f"/dl/{hub.tar_name}" in hub.calls and "/gh/assets/2" in hub.calls, "Archive reference did not respond — downloaded through a spare address")
        hub.bad_sha = True
        out, r = run_with(LS, "--json", "llama", "download", "--params-json", "-", stdin=json.dumps({"models_dir": "folder"}), expect=1)
        ok("checksum" in r["error"] and "did not match" in r["error"] and not (LP / "folder" / (L.MODEL["file"] + ".part")).exists(),
           "file slipped with error — clear-cut, The corrupted file does not remain")
        hub.bad_sha = False
        n_req = len(hub.calls)
        out, r = run_with(LS, "--json", "pull-embeddings")
        ok(r["ok"] and r["title"] == "Downloaded." and len(hub.calls) == n_req, "«pull-embeddings» (before v2.7) — same, what «llama download»; squash")

        # Start with parameters from the plugin window
        par = {"device": "cpu", "ctx": 4096, "kv_cache": "q8_0", "threads": 2, "port": port, "sleep_min": 5}
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(par))
        srv, url = r["server"], f"http://127.0.0.1:{port}/v1"
        ok(r["ok"] and r["title"] == "Model running." and srv["url"] == url and srv["dim"] == 8 and not srv["already"], "model launched")
        e = yaml.safe_load(LS.read_text(encoding="utf-8"))["embeddings"]
        ok(e["mode"] == "local" and e["base_url"] == url and e["model"] == L.ALIAS and e["server"]["port"] == port
           and e["server"]["kv_cache"] == "q8_0" and e["server"]["ctx"] == 4096, "server address, model and parameters are inscribed in the settings")
        a = server_args()
        line = " ".join(a)
        ok(a[:2] == ["-m", L.MODEL["file"]] and all(x in line for x in (
            "--embedding --pooling last", f"--alias {L.ALIAS}", f"--port {port}", "-c 4096 -np 1 -b 4096 -ub 4096", "-ctk q8_0 -ctv q8_0 -fa on",
            "-ngl 0 -dev none", "-t 2 -tb 2", "--sleep-idle-seconds 300", "--no-webui")), f"parameters llama-server: {line}")
        ok(f"FAKE CWD: {mdir}" in log.read_text(encoding="utf-8"), "server launched from the model folder")
        ok(any(x["stage"] == "Loading the model into memory" and x["total"] == 0 for x in tagged(out, "PROGRESS")),
           "memory-loading — stage «N from M»")
        pid = srv["pid"]
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(par))
        ok(r["title"] == "The server is already working." and r["server"]["pid"] == pid, "re-launch with the same parameters — The server is already working.")
        out, r = run_with(LS, "--json", "llama", "status")
        ok(r["llama"]["server"]["running"] and r["llama"]["server"]["health"] == "ok" and r["llama"]["configured"], "condition: server")
        ok("Server: running" in run_with(LS, "llama", "status")[0], "textuality")
        out, emb = check_emb()
        ok(emb["ok"] and "vector dimensions 8" in emb["text"], "«Check the link.»: The embeddings count their servers")
        lcfg = load_config(LS)
        lcfg["embeddings"]["max_chars"] = 20000
        vec = Embedder(lcfg).embed(["longer sample " * 900])
        ok(vec.shape == (1, 8) and "max=12600" in log.read_text(encoding="utf-8") and "max=6300" in log.read_text(encoding="utf-8"),
           "texture — shortened")

        out, r = run_with(LS, "--json", "llama", "stop")
        ok(r["title"] == "Server stopped" and not r["llama"]["server"]["running"] and not L._alive(pid) and L.health(port) is None,
           "server")
        out, r = run_with(LS, "--json", "llama", "stop")
        ok(r["title"] == "Server not running", "stop without running a server — faultless")

        # self-start, When embleming is needed, The server is not running
        out, emb = check_emb()
        ok(emb["ok"] and "starting llama.cpp" in out and L.read_state(lcfg)["by"] == "auto", "server not running — The program ran it itself.")
        run_with(LS, "llama", "stop")
        run_with(LS, "--json", "settings", "--set-json", "-", stdin=json.dumps({"embeddings": {"server": {"autostart": False}}}))
        t = time.time()
        out, emb = check_emb(expect=1)
        ok(not emb["ok"] and "Start model…" in emb["text"] and not L.running(lcfg) and time.time() - t < 15,
           "autostart off — clue, wait")
        run_with(LS, "--json", "settings", "--set-json", "-", stdin=json.dumps({"embeddings": {"server": {"autostart": True}}}))
        os.replace(mp, mp.with_name("hidden.gguf"))
        out, emb = check_emb(expect=1)
        os.replace(mp.with_name("hidden.gguf"), mp)
        ok(not emb["ok"] and "not yet downloaded" in emb["text"], "model — Auto-start does not download anything, suggestive")

        # videocard
        shutil.copytree(LP / "llama.cpp" / "cpu", LP / "llama.cpp" / "vulkan")
        gpar = dict(par, device="gpu")
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(gpar), expect=1)
        ok("could not find a GPU" in r["error"] and not L.running(lcfg), "video card not visible — misunderstood")
        os.environ["FAKE_LLAMA_GPU"] = "Fake Radeon"
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(gpar))
        a = server_args()
        ok(r["server"]["build"] == "vulkan" and r["server"]["devices"] == ["Vulkan0: Fake Radeon (8192 MiB, 8000 MiB free)"]
           and " ".join(a).count("-ngl auto") == 1 and "-dev" not in a, f"video-card: assembly Vulkan, layering — how much will fit ({' '.join(a)})")
        gpid = r["server"]["pid"]
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(par))
        ok("Restart the model server" in out and r["server"]["build"] == "cpu" and r["server"]["pid"] != gpid and not L._alive(gpid),
           "parameter — server restarted")
        run_with(LS, "llama", "stop")

        # trigger
        os.environ["BRAIN_TEST_HW"] = json.dumps({"ram_gb": 8, "gpus": [], "nvidia": False})
        os.environ["FAKE_LLAMA_OOM"] = "1"
        out, r = run_with(LS, "--json", "llama", "start", expect=1)
        os.environ.pop("FAKE_LLAMA_OOM")
        ok("lack of memory" in r["error"] and "Server log" in r["error"] and not L.running(lcfg),
           "The server fell from a memory shortage — reason")
        ok(any("at least 16 GB" in x["text"] for x in tagged(out, "NOTICE")), "less 16 GB of memory when working on the processor — warning")
        os.environ["BRAIN_TEST_HW"] = env["BRAIN_TEST_HW"]
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(dict(par, port=busy.getsockname()[1])),
                              expect=1)
        ok("in use by another program" in r["error"], "port is occupied by another — misunderstood")
        fport = free_port()
        fp = subprocess.Popen([sys.executable, str(b / "llama-server"), "-m", L.MODEL["file"], "--alias", L.ALIAS, "--port", str(fport)],
                              cwd=str(mdir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=dict(os.environ, FAKE_LLAMA_LOAD_SEC="0"))
        procs.append(fp)
        for _ in range(100):
            if L.health(fport) == "ok":
                break
            time.sleep(0.1)
        out, r = run_with(LS, "--json", "llama", "start", "--params-json", "-", stdin=json.dumps(dict(par, port=fport)), expect=1)
        ok("not started by this program" in r["error"], "port — stranger llama-server model: The parameters will not change.")

        # «Stop.» mid-download: left-over
        stopf = V / ".system" / "stop"
        stopf.write_text("", encoding="utf-8")
        try:
            L.download([(f"{hub.url}/{L.MODEL['repo']}/resolve/main/{L.MODEL['file']}", {})], LP / "tmpdl" / "m.gguf", len(model), None,
                       "Downloading the model", stopf)
            stopped = False
        except KeyboardInterrupt:
            stopped = True
        ok(stopped and not stopf.exists() and (LP / "tmpdl" / "m.gguf.part").exists(), "«Stop.» interrupt, left-over")

        # installation: offer to download the model and llama.cpp
        LP2 = ROOT / "llama-prog2"
        shutil.rmtree(LP2, ignore_errors=True)
        LP2.mkdir()
        (LP2 / "settings.yaml").write_text(LS.read_text(encoding="utf-8").split("embeddings:")[0], encoding="utf-8")
        old_in = sys.stdin
        buf = io.StringIO()
        try:
            sys.stdin = io.StringIO("y\n")
            with redirect_stdout(buf):
                CLI._setup_llama(load_config(LP2 / "settings.yaml"), True)
        finally:
            sys.stdin = old_in
        ok("Download now? (y/n)" in buf.getvalue() and (LP2 / "models" / L.MODEL["file"]).read_bytes() == model
           and (LP2 / "llama.cpp" / "cpu" / "llama-server").is_file(), "installation: model llama.cpp consent-driven")
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
        print(f"\nFailure: {e}")
        print("\n--- final conclusions ---")
        for x in LOG[-3:]:
            print(x[-3000:])
        sys.exit(1)

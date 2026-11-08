"""Big file.: division into portions under the model window and continuation after failure without duplicates.
Launch: python tests/big_file.py [folder]"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from brain.cli import main  # noqa: E402
from brain.ingest import str_to_ranges  # noqa: E402

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="brain-big-"))
V = ROOT / "vault"
S = ROOT / "settings.yaml"


def run(*args, expect=0):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(["--settings", str(S)] + list(args))
    out = buf.getvalue()
    if code != expect:
        print(out)
        raise AssertionError(f"brain {' '.join(args)}: code {code}, expected {expect}")
    return out


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"  ✓ {msg}")


def main_test():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    V.mkdir(parents=True)
    os.environ["FAKE_LLM_STATE"] = str(ROOT / "fake_state.json")
    S.write_text(f"""vault: "{V.as_posix()}"
llm: {{mode: fake, model: fake, fake_module: "{(APP / 'tests' / 'fake_llm.py').as_posix()}", max_input_chars: 61000}}
embeddings: {{mode: fake, model: fake-1}}
""", encoding="utf-8")
    arch = V / "_staging" / "archive"
    arch.mkdir(parents=True)
    (arch / "bakery.txt").write_text("10.05.2023\n\nIm thinking of opening a little bakery near my house..\n", encoding="utf-8")
    (arch / "cottage.txt").write_text("11.05.2023\n\nI put a new greenhouse in the cottage..\n", encoding="utf-8")
    run("run")
    d = V / "_structure (draft).md"
    d.write_text(d.read_text(encoding="utf-8").replace("- [ ] Structure approved", "- [x] Structure approved"), encoding="utf-8")
    run("run")
    print("=== Big file.: 24 paragraph ~2500 sign, portion ≤ 20 000")
    bak = "About the bakery: lease, Bathrooms and bakers salary, Im writing it down.. " * 32
    dacha = "The dacha: greenhouse, watering, cucumbers and tomatoes, Im writing it down.. " * 37
    paras = [bak] * 6 + [dacha] * 6 + [bak] * 6 + [dacha] * 6
    (V / "_staging" / "big-bang.txt").write_text("01.06.2023\n\n" + "\n\n".join(p.strip() for p in paras) + "\n", encoding="utf-8")
    os.environ["FAKE_CRASH_ON"] = "Classification#2"
    out = run("run", expect=2)
    ok("Unforeseen error" in out, "lapse")
    del os.environ["FAKE_CRASH_ON"]
    out = run("run")
    ok("part" in (V / "_logs").joinpath(next(p.name for p in (V / "_logs").glob("reasoning *.md"))).read_text(encoding="utf-8"),
       "portions are seen in the Log of Reasoning")
    segs = []
    for p in V.rglob("*.md"):
        if ".system" in p.parts:
            continue
        t = p.read_text(encoding="utf-8")
        if t.startswith("---") and "type: entity" in t and "big-bang.txt" in t:
            seg = next(l.split(":", 1)[1].strip().strip("'") for l in t.split("\n") if l.startswith("segment:"))
            segs.append(seg)
    covered = []
    for s in segs:
        for a, b in str_to_ranges(s):
            covered += list(range(a, b + 1))
    ok(sorted(covered) == list(range(1, 25)), f"everything 24 The paragraph is arranged exactly once. ({len(segs)} record: {', '.join(sorted(segs, key=lambda x: int(x.split('-')[0])))})")
    st = json.loads((V / ".system" / "state.json").read_text(encoding="utf-8"))
    item = next(i for i in st["items"].values() if i["name"] == "big-bang.txt")
    ok(item["stage"] == "done" and "cls_pending" not in item and "cls_progress" not in item, "file disassembled, Service marks removed")
    print(f"\nIts gone.. Warehouse: {V}")


if __name__ == "__main__":
    try:
        main_test()
    except AssertionError as e:
        print(f"\nFailure: {e}")
        sys.exit(1)

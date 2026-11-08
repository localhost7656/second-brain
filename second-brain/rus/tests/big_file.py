"""Большой файл: деление на порции под окно модели и продолжение после сбоя без дублей.
Запуск: python tests/big_file.py [папка]"""
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
        raise AssertionError(f"brain {' '.join(args)}: код {code}, ожидался {expect}")
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
    arch = V / "_staging" / "архив"
    arch.mkdir(parents=True)
    (arch / "пекарня.txt").write_text("10.05.2023\n\nДумаю открыть маленькую пекарню у дома.\n", encoding="utf-8")
    (arch / "дача.txt").write_text("11.05.2023\n\nНа даче поставил новую теплицу.\n", encoding="utf-8")
    run("run")
    d = V / "_структура (черновик).md"
    d.write_text(d.read_text(encoding="utf-8").replace("- [ ] Структура утверждена", "- [x] Структура утверждена"), encoding="utf-8")
    run("run")
    print("=== Большой файл: 24 абзаца по ~2500 знаков, порция ≤ 20 000")
    bak = "Про пекарню: считаю аренду, батоны и зарплату пекаря, всё записываю подробно. " * 32
    dacha = "Про дачу: теплица, полив, огурцы и томаты, всё записываю подробно. " * 37
    paras = [bak] * 6 + [dacha] * 6 + [bak] * 6 + [dacha] * 6
    (V / "_staging" / "большой.txt").write_text("01.06.2023\n\n" + "\n\n".join(p.strip() for p in paras) + "\n", encoding="utf-8")
    os.environ["FAKE_CRASH_ON"] = "Классификация#2"
    out = run("run", expect=2)
    ok("Непредвиденная ошибка" in out, "сбой на второй порции")
    del os.environ["FAKE_CRASH_ON"]
    out = run("run")
    ok("часть" in (V / "_логи").joinpath(next(p.name for p in (V / "_логи").glob("рассуждения *.md"))).read_text(encoding="utf-8"),
       "порции видны в логе рассуждений")
    segs = []
    for p in V.rglob("*.md"):
        if ".system" in p.parts:
            continue
        t = p.read_text(encoding="utf-8")
        if t.startswith("---") and "type: entity" in t and "большой.txt" in t:
            seg = next(l.split(":", 1)[1].strip().strip("'") for l in t.split("\n") if l.startswith("segment:"))
            segs.append(seg)
    covered = []
    for s in segs:
        for a, b in str_to_ranges(s):
            covered += list(range(a, b + 1))
    ok(sorted(covered) == list(range(1, 25)), f"все 24 абзаца разложены ровно по одному разу ({len(segs)} записей: {', '.join(sorted(segs, key=lambda x: int(x.split('-')[0])))})")
    st = json.loads((V / ".system" / "state.json").read_text(encoding="utf-8"))
    item = next(i for i in st["items"].values() if i["name"] == "большой.txt")
    ok(item["stage"] == "done" and "cls_pending" not in item and "cls_progress" not in item, "файл разобран до конца, служебные отметки сняты")
    print(f"\nВсё прошло. Хранилище: {V}")


if __name__ == "__main__":
    try:
        main_test()
    except AssertionError as e:
        print(f"\nПРОВАЛ: {e}")
        sys.exit(1)

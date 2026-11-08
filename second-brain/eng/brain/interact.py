"""Connecting to the plugin and console in the middle of the launch (section 18.1): livelines «@@…» plug-in (progression, wait
model, expense, warning), user-generated (@@ASK — The answer comes in a line in standard input.)."""
from __future__ import annotations

import json
import sys
import time

STATE = {"json": False, "ask": "none", "stage": None, "printed": {}}


def configure(json_mode: bool, ask: str):
    """ask: stdin — plugin responds with a line in standard input; tty — console; none — ask."""
    STATE.update({"json": bool(json_mode), "ask": ask, "stage": None, "printed": {}})


def emit(tag: str, obj) -> None:
    if STATE["json"]:
        print(f"@@{tag} " + json.dumps(obj, ensure_ascii=False, default=str), flush=True)


def can_ask() -> bool:
    return STATE["ask"] in ("stdin", "tty")


def ask(key: str, title: str, text: str, options: list[str], default: int | None = None,
        lines: list[str] | None = None) -> int | None:
    """Question in the middle of launch. Returns the option number (zero); default — If you cant ask;
    None — window closed without answer (waive)."""
    mode = STATE["ask"]
    if mode == "stdin":
        emit("ASK", {"id": key, "title": title, "text": text, "lines": lines or [], "options": options})
        try:
            line = sys.stdin.readline()
        except (OSError, ValueError):
            line = ""
        if not line.strip():
            return None
        try:
            obj = json.loads(line)
            ch = obj.get("choice") if isinstance(obj, dict) else obj
        except ValueError:
            ch = line.strip()
        try:
            ch = int(ch)
        except (TypeError, ValueError):
            return None
        return ch if 0 <= ch < len(options) else None
    if mode == "tty":
        print()
        print(f"— {title} —")
        if text:
            print(text)
        for ln in lines or []:
            print("  " + ln)
        for i, o in enumerate(options, 1):
            print(f"  {i}. {o}")
        yes_no = len(options) == 2
        while True:
            try:
                s = input("Option number" + (" (or y/n)" if yes_no else "") + ": ").strip().lower()
            except EOFError:
                return default
            if s.isdigit() and 1 <= int(s) <= len(options):
                return int(s) - 1
            if yes_no and s in ("y", "yes"):
                return 0
            if yes_no and s in ("n", "no"):
                return 1
            print("Invalid option. Please try again.")
    return default


def progress(stage: str, n: int, total: int, item: str = "", level: int = 0, echo: bool = True, unit: str = "") -> None:
    """Wheres the launch?: «File analysis: 12 from 80» (n — number, whats being processed now).
    level 1 — nested (file-recording). The plugin shows it and figures it out., how much.
    unit="%" — n Its the percentage of whats done. (modelling)."""
    obj = {"stage": stage, "n": n, "total": total, "item": item, "level": level, "t": time.time()}
    if unit:
        obj["unit"] = unit
    emit("PROGRESS", obj)
    if STATE["json"] or not echo or total < 5:
        return
    step = max(1, total // 10)
    last = STATE["printed"].get(stage, 0)
    if n == 1 or n == total or n - last >= step:
        STATE["printed"][stage] = n
        print(f"  {stage}: {n} from {total}", flush=True)


def waiting(prompt: str | None, profile: str = "", model: str = "") -> None:
    """Were waiting for the model to respond. (plugin shows the «waiting for an answer: 0:42»); None — reply."""
    emit("WAIT", {"prompt": prompt, "profile": profile, "model": model, "t": time.time()} if prompt else {})


def notice(text: str) -> None:
    emit("NOTICE", {"text": text})

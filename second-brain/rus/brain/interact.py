"""Связь с плагином и консолью посреди запуска (раздел 18.1): живые строки «@@…» для плагина (прогресс, ожидание ответа
модели, расход, предупреждения), вопросы пользователю (@@ASK — ответ приходит строкой в стандартный ввод)."""
from __future__ import annotations

import json
import sys
import time

STATE = {"json": False, "ask": "none", "stage": None, "printed": {}}


def configure(json_mode: bool, ask: str):
    """ask: stdin — плагин отвечает строкой в стандартный ввод; tty — консоль; none — спросить нельзя."""
    STATE.update({"json": bool(json_mode), "ask": ask, "stage": None, "printed": {}})


def emit(tag: str, obj) -> None:
    if STATE["json"]:
        print(f"@@{tag} " + json.dumps(obj, ensure_ascii=False, default=str), flush=True)


def can_ask() -> bool:
    return STATE["ask"] in ("stdin", "tty")


def ask(key: str, title: str, text: str, options: list[str], default: int | None = None,
        lines: list[str] | None = None) -> int | None:
    """Вопрос посреди запуска. Возвращает номер варианта (с нуля); default — если спросить нельзя;
    None — окно закрыто без ответа (считается отказом)."""
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
                s = input("Номер варианта" + (" (или д/н)" if yes_no else "") + ": ").strip().lower()
            except EOFError:
                return default
            if s.isdigit() and 1 <= int(s) <= len(options):
                return int(s) - 1
            if yes_no and s in ("д", "да", "y", "yes", "l"):
                return 0
            if yes_no and s in ("н", "нет", "n", "no", "т"):
                return 1
            print("Нет такого варианта.")
    return default


def progress(stage: str, n: int, total: int, item: str = "", level: int = 0, echo: bool = True, unit: str = "") -> None:
    """Где сейчас запуск: «Разбор файлов: 12 из 80» (n — номер того, что обрабатывается сейчас).
    level 1 — вложенный этап (записи одного файла). Плагин показывает это и прикидывает, сколько осталось.
    unit="%" — n это проценты сделанного (скачивание модели)."""
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
        print(f"  {stage}: {n} из {total}", flush=True)


def waiting(prompt: str | None, profile: str = "", model: str = "") -> None:
    """Ждём ответа модели (плагин показывает «ждём ответа: 0:42»); None — ответ получен."""
    emit("WAIT", {"prompt": prompt, "profile": profile, "model": model, "t": time.time()} if prompt else {})


def notice(text: str) -> None:
    emit("NOTICE", {"text": text})

"""Вопросы к пользователю (needs_review): реестр, open-questions.md, разбор ответов. Раздел 7."""
from __future__ import annotations

import re

from . import util as U

CHECK = re.compile(r"^\s*[-*]\s*\[([ xXхХ✓vV])\]\s*(.*)$")
ANSWER = re.compile(r"^\s*Ответ\s*:\s*(.*)$", re.I)
HEAD = re.compile(r"^##\s+(Q\d+)\b")


class Questions:
    def __init__(self, world):
        self.w = world
        data = U.read_json(world.p.questions, None) or {}
        self.next = int(data.get("next", 1))
        self.open: dict[str, dict] = data.get("open", {})
        self.answered_now: list[str] = []
        self.injected: dict[str, tuple] = {}  # ответы из плагина (команда answer): qid -> (вариант | None, текст, None)

    def save(self):
        U.write_json(self.w.p.questions, {"next": self.next, "open": self.open})

    def find(self, dedup: str) -> dict | None:
        for q in self.open.values():
            if q.get("dedup") == dedup:
                return q
        return None

    def add(self, kind: str, title: str, text: str, options: list[dict] | None = None, free_text: bool = False,
            free_hint: str = "", data: dict | None = None, dedup: str | None = None, ref: str | None = None) -> dict:
        if dedup:
            ex = self.find(dedup)
            if ex:
                return ex
        qid = f"Q{self.next}"
        self.next += 1
        q = {"id": qid, "kind": kind, "title": title, "text": text, "options": options or [],
             "free_text": free_text, "free_hint": free_hint, "data": data or {}, "dedup": dedup,
             "ref": ref, "created": U.now_iso(), "note": None}
        self.open[qid] = q
        return q

    def close(self, qid: str):
        self.open.pop(qid, None)

    def for_entity(self, eid: str) -> list[dict]:
        return [q for q in self.open.values() if q.get("data", {}).get("entity") == eid]

    # ---------- open-questions.md ----------
    def render(self, notices: list[str]):
        lines = ["# Открытые вопросы", "",
                 "Как отвечать: отметьте галочкой **один** вариант или напишите ответ после «Ответ:». "
                 "Ответы применятся при следующем запуске «Фазы 1». Отвеченные вопросы уходят в [[архив вопросов]].", ""]
        for n in notices:
            lines += [f"> [!info] {n}", ""]
        if not self.open:
            lines += ["Сейчас вопросов нет.", ""]
        def order(q):
            m = re.match(r"Q(\d+)", q["id"])
            return int(m.group(1)) if m else 0
        for q in sorted(self.open.values(), key=order):
            lines += ["---", "", f"## {q['id']} · {q['title']}", f"*{U.ru_datetime(q['created'])}*", ""]
            if q.get("note"):
                lines += [f"> [!warning] {q['note']}", ""]
            lines += [q["text"].rstrip(), ""]
            for o in q["options"]:
                lines.append(f"- [ ] {o['label']}")
            if q["options"]:
                lines.append("")
            if q.get("free_text"):
                if q.get("free_hint"):
                    lines.append(f"*{q['free_hint']}*")
                lines += ["Ответ: ", ""]
        U.atomic_write_text(self.w.p.open_questions, "\n".join(lines).rstrip() + "\n")

    def read_answers(self) -> dict[str, tuple[int | None, str, str | None]]:
        """qid -> (индекс отмеченного варианта | None, свободный текст, ошибка | None)"""
        path = self.w.p.open_questions
        if not path.exists():
            return dict(self.injected)
        raw = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        sections: dict[str, list[str]] = {}
        cur = None
        for line in raw.split("\n"):
            m = HEAD.match(line)
            if m:
                cur = m.group(1)
                sections[cur] = []
                continue
            if cur:
                sections[cur].append(line)
        out = {}
        for qid, lines in sections.items():
            if qid not in self.open:
                continue
            checked, free, in_answer = [], [], False
            k = -1
            for line in lines:
                if line.strip() == "---":
                    in_answer = False
                    continue
                m = CHECK.match(line)
                if m and not in_answer:
                    k += 1
                    if m.group(1).strip():
                        checked.append(k)
                    continue
                m = ANSWER.match(line)
                if m:
                    in_answer = True
                    if m.group(1).strip():
                        free.append(m.group(1).strip())
                    continue
                if in_answer and line.strip():
                    free.append(line.strip())
            text = "\n".join(free).strip()
            if len(checked) > 1:
                out[qid] = (None, text, "Отмечено несколько вариантов — оставьте один.")
            elif checked or text:
                out[qid] = (checked[0] if checked else None, text, None)
        out.update({k: v for k, v in self.injected.items() if k in self.open})
        return out

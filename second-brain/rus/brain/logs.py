"""Логи: изменений и рассуждений (для человека), рефлексии и расхода (машиночитаемые). Разделы 15 и 14.1."""
from __future__ import annotations

from . import util as U


LABELS = {"segments": "фрагмент", "composites": "составной", "conflicts": "противоречие", "duplicates": "дубль",
          "outdated": "устаревание", "structure": "структура", "losses": "потеря", "proposals": "предложение",
          "items": "элемент", "questions": "вопрос", "containers": "контейнер", "dissolve": "разбор составного",
          "aspects": "аспект", "suggestions": "предложение"}


class Logs:
    def __init__(self, world):
        self.w = world
        self.model_name = "?"
        self.changes_count = 0

    def _monthly(self, name: str):
        return self.w.p.logs / f"{name} {U.month_key()}.md"

    def change(self, actor: str, text: str):
        """actor: «модель» | «пользователь» | «программа»"""
        self.changes_count += 1
        U.append_text(self._monthly("изменения"), f"- {U.ru_datetime()} · {actor} · {text}\n")

    def reasoning(self, prompt: str, subject: str, obj):
        lines = []

        nodes = getattr(self.w, "nodes", {}) or {}

        def detail(x: dict) -> str:
            for k in ("container", "id", "aspect", "kind", "composite_type", "what", "name", "title"):
                v = x.get(k)
                if isinstance(v, (str, int)) and v:
                    if k == "container" and v in nodes:
                        return f"→ «{nodes[v].title}»"
                    return f"{v}"
            return ""

        def walk(x, label=""):
            if isinstance(x, dict):
                r = x.get("reasoning")
                if isinstance(r, str) and r.strip():
                    tag = " ".join(t for t in (label, detail(x)) if t)
                    lines.append(f"- {('**' + tag + '**: ') if tag else ''}{r.strip()}")
                for k, v in x.items():
                    if k != "reasoning":
                        walk(v, LABELS.get(k, k))
            elif isinstance(x, list):
                for i, v in enumerate(x, 1):
                    walk(v, f"{label} {i}" if label else str(i))

        walk(obj)
        if not lines:
            return
        head = f"\n### {U.ru_datetime()} · {prompt}" + (f" · {subject}" if subject else "") + f" · {self.model_name}\n"
        U.append_text(self._monthly("рассуждения"), head + "\n".join(lines) + "\n")

    def reflect(self, kind: str, subject: str, assumption, confidence=None, **extra) -> str:
        ref = self.w.next_id("r")
        rec = {"ts": U.now_iso(), "ref": ref, "type": "assumption", "kind": kind, "subject": subject,
               "assumption": assumption, "confidence": confidence, "model": self.model_name}
        rec.update(extra)
        U.append_jsonl(self.w.p.reflection, rec)
        return ref

    def decision(self, ref: str | None, kind: str, subject: str, decision, matched=None, **extra):
        U.append_jsonl(self.w.p.reflection, {"ts": U.now_iso(), "ref": ref, "type": "decision", "kind": kind,
                                             "subject": subject, "decision": decision, "matched": matched, **extra})

    def usage(self, prompt: str, usage: dict | None, chars_in: int, chars_out: int):
        U.append_jsonl(self.w.p.usage, {"ts": U.now_iso(), "prompt": prompt, "model": self.model_name,
                                        "usage": usage, "chars_in": chars_in, "chars_out": chars_out})

    def archive_question(self, q: dict, answer: str):
        text = (f"\n## {q['id']} · {q['title']}\n"
                f"Задан: {U.ru_datetime(q['created'])} · отвечен: {U.ru_datetime()}\n\n"
                f"{q['text'].strip()}\n\n**Ответ:** {answer}\n")
        U.append_text(self.w.p.logs / "архив вопросов.md", text)

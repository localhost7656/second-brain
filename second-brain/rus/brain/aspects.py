"""Типы аспектов, формулы составных, таблица приоритета (раздел 5)."""
from __future__ import annotations

from . import util as U

SIMPLE_TYPES = ["fact", "observation", "hypothesis", "idea", "conclusion", "question", "plan", "judgment"]

BUILTIN_COMPOSITES = {
    "experience": {"title": "Опыт", "types": ["plan", "fact", "observation", "judgment", "conclusion"],
                   "formula": "plan + fact + observation/judgment + conclusion"},
    "resolved_decision": {"title": "Обоснованные решения", "types": ["question", "hypothesis", "idea", "conclusion"],
                          "formula": "question + несколько hypothesis/idea + conclusion"},
    "open_conflict": {"title": "Развилки", "types": ["hypothesis", "idea"],
                      "formula": "два и более hypothesis/idea одного вопроса, не сходящиеся в общий conclusion"},
}

PRIORITY = ["resolved_decision", "fact", "experience", "conclusion", "observation", "open_conflict",
            "hypothesis", "plan", "idea", "judgment", "question"]

TITLES = {"fact": "Факты", "observation": "Наблюдения", "hypothesis": "Гипотезы", "idea": "Идеи",
          "conclusion": "Выводы", "question": "Вопросы", "plan": "Планы", "judgment": "Оценки"}


def composite_types(world) -> dict:
    out = dict(BUILTIN_COMPOSITES)
    extra = U.read_json(world.p.system / "composite_types.json", None) or {}
    for name, spec in extra.items():
        out[name] = spec
    return out


def priority(world) -> list[str]:
    order = list(PRIORITY)
    extra = [n for n in composite_types(world) if n not in order]
    i = order.index("open_conflict") + 1
    return order[:i] + extra + order[i:]


def type_title(world, t: str) -> str:
    if t in TITLES:
        return TITLES[t]
    ct = composite_types(world).get(t)
    return ct["title"] if ct else t

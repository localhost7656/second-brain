"""Types of aspects, formulae, priority-sheet (section 5)."""
from __future__ import annotations

from . import util as U

SIMPLE_TYPES = ["fact", "observation", "hypothesis", "idea", "conclusion", "question", "plan", "judgment"]

BUILTIN_COMPOSITES = {
    "experience": {"title": "Experience", "types": ["plan", "fact", "observation", "judgment", "conclusion"],
                   "formula": "plan + fact + observation/judgment + conclusion"},
    "resolved_decision": {"title": "Reasoned decisions", "types": ["question", "hypothesis", "idea", "conclusion"],
                          "formula": "question + several hypotheses/ideas + conclusion"},
    "open_conflict": {"title": "Open alternatives", "types": ["hypothesis", "idea"],
                      "formula": "two or more hypotheses/ideas about the same question without a shared conclusion"},
}

PRIORITY = ["resolved_decision", "fact", "experience", "conclusion", "observation", "open_conflict",
            "hypothesis", "plan", "idea", "judgment", "question"]

TITLES = {"fact": "Facts", "observation": "Observations", "hypothesis": "Hypotheses", "idea": "Ideas",
          "conclusion": "Conclusions", "question": "Questions", "plan": "Plans", "judgment": "Evaluations"}


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

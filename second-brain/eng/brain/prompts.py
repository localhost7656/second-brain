"""Loading and substitution of the prompts (section 9.1): file prompts/ programme."""
from __future__ import annotations

import json
import re

from .util import UserError

GARBLED_HINT = " Check that the archive was extracted correctly and that all prompt files are present."
_VAR = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, indent=1)
    return str(v)


def render(cfg, name: str, variables: dict) -> str:
    path = cfg.program_file("prompts") / f"{name}.md"
    if not path.exists():
        raise UserError(f"Prompt file not found: {path}." + GARBLED_HINT)
    tpl = path.read_text(encoding="utf-8-sig")
    missing = [m for m in _VAR.findall(tpl) if m not in variables]
    if missing:
        raise UserError(f"Values missing for prompt “{name}”: {', '.join(sorted(set(missing)))}")
    return _VAR.sub(lambda m: _fmt(variables[m.group(1)]), tpl)

"""Загрузка и подстановка промптов (раздел 9.1): файлы в папке prompts/ программы."""
from __future__ import annotations

import json
import re

from .util import UserError

GARBLED_HINT = (" Если имена файлов в папке prompts выглядят как набор странных символов, архив распакован с искажением "
                "русских имён — распакуйте его заново, например программой 7-Zip.")
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
        raise UserError(f"Не найден файл промпта: {path}." + GARBLED_HINT)
    tpl = path.read_text(encoding="utf-8-sig")
    missing = [m for m in _VAR.findall(tpl) if m not in variables]
    if missing:
        raise UserError(f"В промпт «{name}» не переданы значения: {', '.join(sorted(set(missing)))}")
    return _VAR.sub(lambda m: _fmt(variables[m.group(1)]), tpl)

"""Common utility: file, date, YAML-cap, file-name."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

# ---------- time ----------

def now() -> _dt.datetime:
    return _dt.datetime.now().replace(microsecond=0)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def today() -> str:
    return _dt.date.today().isoformat()


def ru_date(iso: str | None) -> str:
    """2026-08-20 -> 20.08.2026"""
    if not iso:
        return ""
    try:
        d = _dt.date.fromisoformat(str(iso)[:10])
        return d.strftime("%d.%m.%Y")
    except ValueError:
        return str(iso)


def ru_datetime(iso: str | None = None) -> str:
    t = _dt.datetime.fromisoformat(iso) if iso else now()
    return t.strftime("%d.%m.%Y %H:%M")


def month_key() -> str:
    return _dt.date.today().strftime("%Y-%m")


# ---------- text ----------

def duration(sec) -> str:
    """Format elapsed time, for example 42 s, 3 min 12 s, or 1 hr 05 min."""
    try:
        sec = max(0, int(round(float(sec or 0))))
    except (TypeError, ValueError):
        return "—"
    if sec < 60:
        return f"{sec} s"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} min {s:02d} s" if s else f"{m} min"
    h, m = divmod(m, 60)
    return f"{h} hr {m:02d} min"


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f\[\]#^]')
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def safe_name(s: str, maxlen: int = 60) -> str:
    """File name, permissible Windows linkable Obsidian."""
    s = _BAD_CHARS.sub(" ", s or "")
    s = re.sub(r"\s+", " ", s).strip().strip(".").strip()
    if len(s) > maxlen:
        cut = s[:maxlen]
        if " " in cut[maxlen // 2:]:
            cut = cut[: cut.rfind(" ")]
        s = cut.strip().strip(".")
    if not s:
        s = "nameless"
    if s.upper() in _RESERVED:
        s = s + "_"
    return s


def unique_path(folder: Path, stem: str, ext: str = ".md", taken: set | None = None) -> Path:
    p = folder / f"{stem}{ext}"
    n = 2
    while p.exists() or (taken is not None and str(p).lower() in taken):
        p = folder / f"{stem} ({n}){ext}"
        n += 1
    return p


def short_title(text: str, words: int = 7) -> str:
    t = re.sub(r"^\s*\S{1,6}:\s*", "", (text or "").strip())  # remove «Me:» beginning
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", t)        # [[path|signature]] → signature
    t = re.sub(r"\[\[(?:[^\]]*/)?([^\]/]*)\]\]", r"\1", t)     # [[path/name]] → name
    t = re.sub(r"\s+", " ", t)
    parts = t.split(" ")
    return " ".join(parts[:words])


# ---------- file ----------

def retry_fs(fn, *args, attempts: int = 12, pause: float = 0.25):
    """File operation with repetition: into Windows The file may be momentarily occupied.
    (Obsidian, antivirus, cloud-synchronization) — then PermissionError."""
    for i in range(attempts):
        try:
            return fn(*args)
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(pause)


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        retry_fs(os.replace, tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    atomic_write_text(Path(path), json.dumps(data, ensure_ascii=False, indent=1))


def append_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def append_jsonl(path: Path, obj: dict) -> None:
    append_text(path, json.dumps(obj, ensure_ascii=False) + "\n")


# ---------- markdown s YAML-cap ----------

class _Dumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _str_presenter)


def dump_yaml(data: dict) -> str:
    return yaml.dump(data, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=1000)


def _clean(v: Any) -> Any:
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clean(x) for x in v]
    return v


def split_frontmatter(raw: str) -> tuple[dict, str]:
    raw = raw.lstrip("\ufeff")
    if raw.startswith("---"):
        m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", raw, re.S)
        if m:
            try:
                fm = yaml.safe_load(m.group(1)) or {}
                if isinstance(fm, dict):
                    return _clean(fm), raw[m.end():]
            except yaml.YAMLError:
                pass
    return {}, raw


def read_md(path: Path) -> tuple[dict, str]:
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    return split_frontmatter(raw.replace("\r\n", "\n"))


def write_md(path: Path, fm: dict, body: str) -> None:
    text = "---\n" + dump_yaml(fm) + "---\n" + (body if body.startswith("\n") else "\n" + body)
    if not text.endswith("\n"):
        text += "\n"
    atomic_write_text(Path(path), text)


def link(title: str | None) -> str | None:
    return f"[[{title}]]" if title else None


def unlink(value: Any) -> str | None:
    """'[[Name of name]]' / 'Name of name' / '[[Name of name|alias]]' -> 'Name of name'"""
    if value is None:
        return None
    if isinstance(value, list):  # [[X]] quotationless YAML reads like a nested list
        return unlink(value[0]) if len(value) == 1 else None
    s = str(value).strip()
    m = re.fullmatch(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]", s)
    if m:
        s = m.group(1)
    s = s.strip()
    return s or None


def as_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


class UserError(Exception):
    """Mistake., user-readable (printable)."""


class ManualPending(Exception):
    """Need a manual answer from the web-chat: The run stops and will continue later.."""


class BudgetStop(KeyboardInterrupt):
    """Budget stoppage (how «Stop.»: all processed preserved)."""

    def __init__(self, text: str):
        super().__init__(text)
        self.text = text

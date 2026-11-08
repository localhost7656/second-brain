"""Reading input files from _staging (section 4)."""
from __future__ import annotations

import datetime as _dt
import os
import re
import sys
from pathlib import Path

from . import util as U

DATE_LINE = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*(?:г\.?)?\s*$")
HINT_LINE = re.compile(r"^\s*(?:hint|clue)\s*:\s*(.*)$", re.I)
CTYPE_LINE = re.compile(r"^\s*content_type\s*:\s*(\S+)\s*$", re.I)
MODE_LINE = re.compile(r"^\s*(?:mode|regime)\s*:\s*(steady_state|record)\s*$", re.I)  # servicefully: «New thought» plug-in
INPUT_EXT = {".txt", ".md"}


def decode(raw: bytes) -> tuple[str, str]:
    """UTF-8 (s BOM without) or Windows-1251 — quintessential txt."""
    for enc in ("utf-8-sig",):
        try:
            return raw.decode(enc), "utf-8"
        except UnicodeDecodeError:
            pass
    try:
        return raw.decode("cp1251"), "cp1251"
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace"), "utf-8?"


def read_text_file(path: Path) -> tuple[str, str]:
    text, enc = decode(Path(path).read_bytes())
    return text.replace("\r\n", "\n").replace("\r", "\n"), enc


def parse_date(d: str, m: str, y: str) -> str | None:
    try:
        return _dt.date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_header(text: str) -> dict:
    """Service cap: date.mm.gg, hint: …, (servicefully) content_type: …
    He understands. YAML-cap Obsidian fieldy hint / date / created."""
    out = {"date": None, "hint": None, "content_type": None, "mode": None, "body": text, "date_line": False}
    fm, rest = U.split_frontmatter(text) if text.lstrip().startswith("---") else ({}, text)
    if fm:
        h = fm.get("hint") or fm.get("clue") or fm.get("подсказка")
        if h:
            out["hint"] = str(h).strip()
        for k in ("date", "created", "дата"):
            v = fm.get(k)
            if v:
                s = str(v)
                m = DATE_LINE.match(s)
                if m:
                    out["date"] = parse_date(*m.groups())
                else:
                    try:
                        out["date"] = _dt.date.fromisoformat(s[:10]).isoformat()
                    except ValueError:
                        pass
                break
        text = rest
    lines = text.split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    consumed = i
    for j in range(i, min(i + 5, len(lines))):
        line = lines[j]
        if not line.strip():
            consumed = j + 1
            continue
        m = DATE_LINE.match(line)
        if m and out["date"] is None:
            out["date"] = parse_date(*m.groups())
            out["date_line"] = bool(out["date"])
            consumed = j + 1
            continue
        m = HINT_LINE.match(line)
        if m and out["hint"] is None:
            out["hint"] = m.group(1).strip() or None
            consumed = j + 1
            continue
        m = CTYPE_LINE.match(line)
        if m and out["content_type"] is None:
            out["content_type"] = m.group(1).strip()
            consumed = j + 1
            continue
        m = MODE_LINE.match(line)
        if m and out["mode"] is None:
            out["mode"] = "steady_state"
            consumed = j + 1
            continue
        break
    out["body"] = "\n".join(lines[consumed:]).strip("\n")
    return out


def _starts_with_marker(line: str, markers: list[str]) -> bool:
    s = line.lstrip().lower()
    return any(s.startswith(m.lower()) for m in markers)


def is_dialogue(text: str, user_markers: list[str], ai_markers: list[str]) -> bool:
    has_u = has_a = False
    for line in text.split("\n"):
        if _starts_with_marker(line, user_markers):
            has_u = True
        elif _starts_with_marker(line, ai_markers):
            has_a = True
        if has_u and has_a:
            return True
    return False


def split_paragraphs(body: str, markers: list[str]) -> list[str]:
    """Abzacs: block-line; if there are no empty lines — line-by-line.
    Remark prefixed line («Me:», «AI:») Always start a new paragraph.."""
    body = body.strip("\n")
    if not body.strip():
        return []
    lines = body.split("\n")
    has_blank = any(not l.strip() for l in lines)
    paras: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if not line.strip():
            if cur:
                paras.append(cur)
                cur = []
            continue
        if not has_blank:
            if cur:
                paras.append(cur)
            cur = [line]
            continue
        if cur and markers and _starts_with_marker(line, markers):
            paras.append(cur)
            cur = [line]
            continue
        cur.append(line)
    if cur:
        paras.append(cur)
    out = []
    for p in paras:
        if "".join(p).strip():
            out += _cap_paragraph("\n".join(p).rstrip())
    return out


MAX_PARA = 8000  # long paragraph divided, So that any file can be broken down into portions for the model


def _cap_paragraph(text: str) -> list[str]:
    if len(text) <= MAX_PARA:
        return [text]
    pieces = []
    for line in text.split("\n"):
        if len(line) <= MAX_PARA:
            pieces.append(line)
            continue
        cur = ""
        for sent in re.split(r"(?<=[.!?…])\s+", line):
            while len(sent) > MAX_PARA:
                if cur:
                    pieces.append(cur)
                    cur = ""
                pieces.append(sent[:MAX_PARA])
                sent = sent[MAX_PARA:]
            if cur and len(cur) + 1 + len(sent) > MAX_PARA:
                pieces.append(cur)
                cur = sent
            else:
                cur = f"{cur} {sent}" if cur else sent
        if cur:
            pieces.append(cur)
    out, cur = [], ""
    for piece in pieces:
        if cur and len(cur) + 1 + len(piece) > MAX_PARA:
            out.append(cur)
            cur = piece
        else:
            cur = f"{cur}\n{piece}" if cur else piece
    if cur.strip():
        out.append(cur)
    return [x for x in out if x.strip()]


def file_date(path: Path) -> str:
    """The earliest of the dates of creation and modification of the file (section 4.2)."""
    st = os.stat(path)
    times = [st.st_mtime]
    birth = getattr(st, "st_birthtime", None)
    if birth:
        times.append(birth)
    elif sys.platform.startswith("win"):
        times.append(st.st_ctime)
    return _dt.date.fromtimestamp(min(times)).isoformat()


def source_and_mode(rel_parts: tuple[str, ...]) -> tuple[str, str | None]:
    """rel_parts — path _staging fileless."""
    if not rel_parts:
        return "note", None
    if rel_parts[0].lower() == "archive":
        return (rel_parts[-1] if len(rel_parts) > 1 else "archive"), "bootstrap"
    return rel_parts[-1], None


def segment_text(paragraphs: list[str], ranges: list[list[int]]) -> str:
    parts = []
    for a, b in ranges:
        parts.append("\n\n".join(paragraphs[a - 1:b]))
    return "\n\n…\n\n".join(parts)


def ranges_to_str(ranges: list[list[int]]) -> str:
    return ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in ranges)


def str_to_ranges(s: str | None) -> list[list[int]] | None:
    if not s:
        return None
    out = []
    for part in str(s).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.append([int(a), int(b)])
        else:
            out.append([int(part), int(part)])
    return out


def numbered(paragraphs: list[str]) -> str:
    return "\n\n".join(f"[{i}] {p}" for i, p in enumerate(paragraphs, 1))


def scan_staging(staging: Path) -> list[Path]:
    files = []
    for p in sorted(staging.rglob("*")):
        if p.is_file() and p.suffix.lower() in INPUT_EXT and not p.name.startswith((".", "~")):
            files.append(p)
    return files


def load_item_body(ctx, item: dict) -> str:
    path = ctx.w.p.root / item["file"]
    text, _ = read_text_file(path)
    body = parse_header(text)["body"]
    part = item.get("part")
    return part_text(body, part) if part else body


# ---------- datebook: date-by-date ----------
_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
           "янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6,
           "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12}
_MONTH_RE = (r"(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|"
             r"august|aug|september|sept|sep|october|oct|november|nov|december|dec|"
             r"января|январь|янв|февраля|февраль|фев|марта|март|мар|апреля|апрель|апр|мая|май|"
             r"июня|июнь|июн|июля|июль|июл|августа|август|авг|сентября|сентябрь|сент|сен|"
             r"октября|октябрь|окт|ноября|ноябрь|ноя|декабря|декабрь|дек)\.?")
_WD = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun|понедельник|вторник|среда|четверг|пятница|суббота|воскресенье|пн|вт|ср|чт|пт|сб|вс)\.?"
_DATE = (r"(?:(?P<d1>\d{1,2})[./-](?P<m1>\d{1,2})[./-](?P<y1>\d{4}|\d{2})"
         r"|(?P<y2>\d{4})[-./](?P<m2>\d{1,2})[-./](?P<d2>\d{1,2})"
         r"|(?P<d3>\d{1,2})\s+" + _MONTH_RE.replace("(", "(?P<mn>", 1) + r"\s+(?P<y3>\d{4}))")
_YEAR_WORD = r"(?:\s*(?:г\.?|года?))?"
_TIME = r"(?:[,\s]+(?:(?:at|в)\s+)?\d{1,2}[:.]\d{2}(?::\d{2})?)?"
DATE_HEADER = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\s*(?:" + _WD + r"[,\s]+)?" + _DATE + _YEAR_WORD
                         + r"(?:[,\s]+" + _WD + r")?" + _TIME + r"\s*(?:\*\*|__)?\s*[:.—–-]?\s*(?:\*\*|__)?\s*$", re.I)
DATE_INLINE = re.compile(r"^\s*(?:\*\*|__)?(?:" + _WD + r"[,\s]+)?" + _DATE + _YEAR_WORD + _TIME
                         + r"\s*(?:\*\*|__)?\s*[:.,—–-]?\s+(?=\S)", re.I)
INLINE_MIN = 300   # The date at the beginning of the paragraph is considered the beginning of the entry., If the paragraph is long,


def _date_of(m) -> str | None:
    g = m.groupdict()
    try:
        if g.get("y1"):
            y = int(g["y1"])
            y = y + (2000 if y < 70 else 1900) if y < 100 else y
            d, mo = int(g["d1"]), int(g["m1"])
        elif g.get("y2"):
            y, mo, d = int(g["y2"]), int(g["m2"]), int(g["d2"])
        else:
            y, d = int(g["y3"]), int(g["d3"])
            mo = _MONTHS[g["mn"].lower().rstrip(".")[:3]]
        if not 1950 <= y <= _dt.date.today().year + 1:
            return None
        return _dt.date(y, mo, d).isoformat()
    except (TypeError, ValueError, KeyError):
        return None


def find_date_markers(lines: list[str]) -> list[dict]:
    """Lines., from which the diary records begin: line — date (day of the week, timelessly, #, **),
    or the date at the beginning of a long paragraph after an empty line."""
    heads, inline = [], []
    for i, line in enumerate(lines):
        if not line.strip() or len(line) > 120 and not DATE_INLINE.match(line):
            continue
        m = DATE_HEADER.match(line)
        if m:
            d = _date_of(m)
            if d:
                heads.append({"line": i, "date": d, "cut": None})
            continue
        if i and lines[i - 1].strip():
            continue
        m = DATE_INLINE.match(line)
        if m:
            d = _date_of(m)
            if not d:
                continue
            j, size = i, 0
            while j < len(lines) and lines[j].strip():
                size += len(lines[j])
                j += 1
            if size >= INLINE_MIN:
                inline.append({"line": i, "date": d, "cut": m.end()})
    if heads:
        return heads
    dates = [x["date"] for x in inline]
    if len(dates) >= 2 and (dates == sorted(dates) or dates == sorted(dates, reverse=True)):
        return inline
    return []


def split_by_dates(cfg, hdr: dict) -> list[dict] | None:
    """Parts of the file-journal: [{lines: [a, b], drop: [...], cut: [line, sign] | None, date, label}] or None — divide.
    Not shared.: switched off, service-cap (content_type, mode: steady_state), AI-dialogue, two-year."""
    if not ((cfg.get("input") or {}).get("split_by_dates", True)):
        return None
    if hdr.get("content_type") or hdr.get("mode") == "steady_state":
        return None
    um, am = cfg.markers()
    if is_dialogue(hdr["body"], um, am):
        return None
    lines = hdr["body"].split("\n")
    marks = find_date_markers(lines)
    total = len(marks) + (1 if hdr.get("date_line") else 0)
    if not marks or total < 2:
        return None
    parts = []
    pre_end = marks[0]["line"]
    pre = "\n".join(lines[:pre_end]).strip()
    lead_drop: list[int] = []
    start0 = None
    if pre:
        if hdr.get("date_line"):
            parts.append({"lines": [0, pre_end], "drop": [], "cut": None, "date": hdr["date"]})
        elif len(pre) < 200:  # filehead — first-hand
            start0 = 0
        else:
            parts.append({"lines": [0, pre_end], "drop": [], "cut": None, "date": hdr.get("date")})
    for k, mk in enumerate(marks):
        a = mk["line"]
        b = marks[k + 1]["line"] if k + 1 < len(marks) else len(lines)
        drop = [] if mk["cut"] is not None else [a]
        part = {"lines": [a, b], "drop": drop, "cut": [a, mk["cut"]] if mk["cut"] is not None else None, "date": mk["date"]}
        if k == 0 and start0 is not None:
            part["lines"] = [0, b]
            part["drop"] = lead_drop + drop
        parts.append(part)
    out = []
    for part in parts:
        if part_text(hdr["body"], part).strip():
            out.append(part)
    if len(out) < 2:
        return None
    for n, part in enumerate(out, 1):
        part["n"], part["of"] = n, len(out)
        part["label"] = U.ru_date(part["date"]) if part.get("date") else f"part {n}"
    return out


def part_text(body: str, part: dict) -> str:
    lines = body.split("\n")
    a, b = part["lines"]
    drop = set(part.get("drop") or [])
    cut = part.get("cut")
    out = []
    for i in range(a, min(b, len(lines))):
        if i in drop:
            continue
        line = lines[i]
        if cut and i == cut[0]:
            line = line[cut[1]:]
        out.append(line)
    return "\n".join(out).strip("\n")


def load_item_paragraphs(ctx, item: dict) -> list[str]:
    um, am = ctx.cfg.markers()
    return split_paragraphs(load_item_body(ctx, item), um + am)

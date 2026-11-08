"""Cost of references to models (section 14): journal .system/usage.jsonl, profile-price ($ post 1 million),
monthly, plugin summary (tab «Expenses») console.
Recording of the magazine: ts, run, cmd, kind (llm | emb), prompt, profile, profile_name, ptype (cloud | local | webchat | fake), model,
in / out / cached — token (est — marking, If the server does not report), sec — response, cost — $ momentarily
circulation (price — counts; In summary, such applications are estimated at current prices)."""
from __future__ import annotations

import datetime as _dt
import json
import os
import time
from pathlib import Path

from . import interact
from . import util as U
from .profiles import profiles_by_id

CHARS_PER_TOKEN = 3.0


# ---------- tokens and money ----------
def _int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def cached_tokens(u: dict) -> int:
    d = u.get("prompt_tokens_details")
    for v in ((d or {}).get("cached_tokens") if isinstance(d, dict) else None, u.get("prompt_cache_hit_tokens"),
              u.get("cache_read_input_tokens"), u.get("cached_tokens")):
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
    t = u.get("_timings")
    if isinstance(t, dict) and isinstance(t.get("cache_n"), (int, float)):
        return int(t["cache_n"])
    return 0


def tokens(u: dict | None, chars_in: int, chars_out: int) -> tuple[int, int, int, bool]:
    """(entrance, exit, cache-in, estimation)."""
    u = u if isinstance(u, dict) else {}
    inp = _int(u.get("prompt_tokens") or u.get("input_tokens"))
    out = _int(u.get("completion_tokens") or u.get("output_tokens"))
    t = u.get("_timings") if isinstance(u.get("_timings"), dict) else {}
    if not inp and t:
        inp = _int(t.get("prompt_n")) + _int(t.get("cache_n"))
    if not out and t:
        out = _int(t.get("predicted_n"))
    if inp or out:
        return inp, out, min(cached_tokens(u), inp), False
    return round(chars_in / CHARS_PER_TOKEN), round(chars_out / CHARS_PER_TOKEN), 0, True


def priced(prices) -> bool:
    return isinstance(prices, dict) and (prices.get("input") is not None or prices.get("output") is not None)


def cost(prices, inp: int, out: int, cached: int = 0) -> float | None:
    """$ price-per-price 1 million; None — price unset."""
    if not priced(prices):
        return None
    pin = float(prices.get("input") or 0)
    pc = prices.get("cached_input")
    pc = pin if pc is None else float(pc)
    pout = float(prices.get("output") or 0)
    cached = min(max(cached, 0), inp)
    return round(((inp - cached) * pin + cached * pc + out * pout) / 1e6, 8)


def emb_prices(cfg) -> dict | None:
    p = (cfg.get("embeddings") or {}).get("price_input")
    return {"input": p, "output": 0} if p is not None else None


# ---------- journal ----------
def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict):
                out.append(r)
    return out


def _legacy_profile(cfg, model) -> dict | None:
    """Recording to profiles (v2.4): profile, if hes alone."""
    ps = [p for p in cfg["llm"].get("profiles") or [] if isinstance(p, dict) and p.get("model") == model]
    return ps[0] if len(ps) == 1 else None


def normalize(cfg, r: dict, byid: dict | None = None) -> dict:
    """Recording of any version of the journal → uniformity (cost — at record or current prices)."""
    byid = byid if byid is not None else profiles_by_id(cfg)
    kind = r.get("kind") or "llm"
    if "in" in r or "out" in r:
        inp, out, cached, est = _int(r.get("in")), _int(r.get("out")), _int(r.get("cached")), bool(r.get("est"))
    else:
        inp, out, cached, est = tokens(r.get("usage"), _int(r.get("chars_in")), _int(r.get("chars_out")))
    pid = r.get("profile")
    ptype = r.get("ptype")
    model = r.get("model") or ""
    name = r.get("profile_name")
    if kind == "emb":
        key = f"emb:{model}"
        name = f"embeddingi · {model}"
        prices = emb_prices(cfg) if ptype == "cloud" else None
    elif ptype == "webchat" or model == "web-based-chat":
        key, name, ptype, prices = "webchat", "Web Web-chat", "webchat", None
    elif pid:
        p = byid.get(pid)
        key = pid
        name = (p or {}).get("name") or name or pid
        ptype = ptype or (p or {}).get("kind")
        prices = (p or {}).get("prices") if ptype == "cloud" else None
    else:  # profiled
        p = _legacy_profile(cfg, model) if model not in ("fake", "?", "") else None
        if p is not None:
            key, name, ptype = p["id"], p.get("name") or p["id"], p.get("kind")
            prices = p.get("prices") if ptype == "cloud" else None
        else:
            key, name = f"model:{model}", (model or "?")
            ptype = ptype or ("fake" if model == "fake" else None)
            prices = None
    c = r.get("cost")
    if c is None and ptype == "cloud":
        c = cost(prices, inp, out, cached)
    return {"ts": str(r.get("ts") or ""), "run": r.get("run"), "cmd": r.get("cmd"), "kind": kind, "prompt": r.get("prompt") or "?",
            "key": key, "name": name, "ptype": ptype, "model": model, "in": inp, "out": out, "cached": cached, "est": est,
            "sec": float(r.get("sec") or 0), "cost": c}


def _blank() -> dict:
    return {"calls": 0, "in": 0, "out": 0, "cached": 0, "cost": 0.0, "unpriced": 0, "sec": 0.0, "est": 0}


def _add(t: dict, n: dict):
    t["calls"] += 1
    t["in"] += n["in"]
    t["out"] += n["out"]
    t["cached"] += n["cached"]
    t["sec"] += n["sec"]
    t["est"] += 1 if n["est"] else 0
    if n["cost"] is not None:
        t["cost"] += n["cost"]
    elif n["ptype"] == "cloud":
        t["unpriced"] += 1


def _round(t: dict) -> dict:
    t["cost"] = round(t["cost"], 6)
    t["sec"] = round(t["sec"], 1)
    return t


def _prev_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def month_spent(cfg, path: Path, exclude_run: str | None = None) -> tuple[float, dict]:
    """How much is spent this month: whole and profile (budget); exclude_run — no-fly
    (The meter runs the meter itself.)."""
    month = U.month_key()
    byid = profiles_by_id(cfg)
    total, per = 0.0, {}
    for r in read(path):
        if not str(r.get("ts", "")).startswith(month) or (exclude_run and r.get("run") == exclude_run):
            continue
        n = normalize(cfg, r, byid)
        if n["cost"]:
            total += n["cost"]
            per[n["key"]] = per.get(n["key"], 0.0) + n["cost"]
    return total, per


def summary(cfg, path: Path, days: int = 31) -> dict:
    """Summary of costs for the plugin: todays results / month / last month / all the time, profiled, step-by-step,
    day-by-day; budget."""
    from .profiles import main_profile_id, target
    today = U.today()
    month = today[:7]
    prev = _prev_month(month)
    byid = profiles_by_id(cfg)
    periods = ("today", "month", "prev_month", "all")
    totals = {k: _blank() for k in periods}
    profiles: dict[str, dict] = {}
    steps: dict[str, dict] = {}
    day0 = (_dt.date.fromisoformat(today) - _dt.timedelta(days=days - 1)).isoformat()
    by_day: dict[str, dict] = {}
    runs: dict[str, dict] = {}
    for r in read(path):
        n = normalize(cfg, r, byid)
        ts = n["ts"]
        which = ["all"] + (["month"] if ts.startswith(month) else []) + (["prev_month"] if ts.startswith(prev) else []) \
            + (["today"] if ts.startswith(today) else [])
        pr = profiles.get(n["key"])
        if pr is None:
            pr = profiles[n["key"]] = {"key": n["key"], "name": n["name"], "ptype": n["ptype"], "model": n["model"],
                                       "kind": n["kind"], "totals": {k: _blank() for k in periods}, "last": ts}
        pr["last"] = max(pr["last"], ts)
        if n["model"]:
            pr["model"] = n["model"]
        step_name = "embeddingi" if n["kind"] == "emb" else n["prompt"]
        st = steps.get(step_name)
        if st is None:
            st = steps[step_name] = {"name": step_name, "totals": {k: _blank() for k in periods}}
        for k in which:
            _add(totals[k], n)
            _add(pr["totals"][k], n)
            _add(st["totals"][k], n)
        d = ts[:10]
        if d >= day0:
            _add(by_day.setdefault(d, _blank()), n)
        if n["run"]:
            ru = runs.get(n["run"])
            if ru is None:
                ru = runs[n["run"]] = dict(_blank(), run=n["run"], cmd=n["cmd"], started=ts)
            _add(ru, n)
            ru["ended"] = ts
    # profiles — even
    llm = cfg["llm"]
    main_id = main_profile_id(llm)
    used_by: dict[str, list[str]] = {}
    from .schema import PROMPT_NAMES
    for step in PROMPT_NAMES:
        kind, p = target(cfg, step)
        key = "webchat" if kind == "webchat" else (p or {}).get("id")
        if key:
            used_by.setdefault(key, []).append(step)
    out_profiles = []
    for p in llm.get("profiles") or []:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        pr = profiles.pop(p["id"], None) or {"key": p["id"], "totals": {k: _blank() for k in periods}, "last": None}
        pr.update({"key": p["id"], "id": p["id"], "name": p.get("name") or p["id"], "ptype": p.get("kind"),
                   "kind": "llm", "model": p.get("model") or pr.get("model") or "", "exists": True,
                   "prices": p.get("prices") if p.get("kind") == "cloud" else None,
                   "priced": priced(p.get("prices")) if p.get("kind") == "cloud" else None,
                   "budget_month": p.get("budget_month") if p.get("kind") == "cloud" else None,
                   "active": p["id"] == main_id and llm.get("mode") in ("cloud", "local"),
                   "steps": used_by.get(p["id"], [])})
        out_profiles.append(pr)
    for key, pr in sorted(profiles.items(), key=lambda kv: kv[1].get("last") or "", reverse=True):
        pr.update({"id": None, "exists": False, "prices": None, "priced": None, "budget_month": None,
                   "active": key == "webchat" and llm.get("mode") == "webchat", "steps": used_by.get(key, [])})
        if key.startswith("emb:"):
            emb = cfg.get("embeddings") or {}
            current = f"emb:{emb.get('model')}" == key
            pr.update({"exists": current, "prices": emb_prices(cfg) if pr["ptype"] == "cloud" else None,
                       "priced": (emb.get("price_input") is not None) if pr["ptype"] == "cloud" else None})
        out_profiles.append(pr)
    for pr in out_profiles:
        for k in periods:
            _round(pr["totals"][k])
    for k in periods:
        _round(totals[k])
    for st in steps.values():
        for k in periods:
            _round(st["totals"][k])
    d0 = _dt.date.fromisoformat(day0)
    day_list = []
    for i in range(days):
        d = (d0 + _dt.timedelta(days=i)).isoformat()
        t = _round(by_day.get(d) or _blank())
        day_list.append({"date": d, **{k: t[k] for k in ("calls", "in", "out", "cost", "sec", "unpriced")}})
    b = cfg.get("budget") or {}
    lim = b.get("monthly_usd") or None
    spent = totals["month"]["cost"]
    pct = round(spent / lim * 100, 1) if lim else None
    warn = int(b.get("warn_pct") or 80)
    state = None if pct is None else ("over" if pct >= 100 else "warn" if pct >= warn else "ok")
    for pr in out_profiles:
        bl = pr.get("budget_month")
        if bl:
            pp = round(pr["totals"]["month"]["cost"] / bl * 100, 1)
            pr["budget_pct"] = pp
            pr["budget_state"] = "over" if pp >= 100 else "warn" if pp >= warn else "ok"
    cur_id = "webchat" if llm.get("mode") == "webchat" else main_id
    cur = next((p for p in out_profiles if p["key"] == cur_id), None)
    run_list = sorted(runs.values(), key=lambda x: x["started"], reverse=True)[:20]
    for ru in run_list:
        _round(ru)
    return {
        "currency": "USD", "today": today, "month": month, "prev_month": prev,
        "totals": totals, "profiles": out_profiles,
        "steps": sorted(steps.values(), key=lambda s: (-s["totals"]["all"]["cost"], -s["totals"]["all"]["calls"])),
        "days": day_list, "runs": run_list,
        "budget": {"monthly_usd": lim, "warn_pct": warn, "spent": round(spent, 6), "pct": pct, "state": state,
                   "unpriced": totals["month"]["unpriced"]},
        "current": {"mode": llm.get("mode"), "key": cur_id, "name": (cur or {}).get("name"),
                    "ptype": (cur or {}).get("ptype"), "totals": (cur or {}).get("totals")},
    }


def reprice(cfg, path: Path, key: str) -> int:
    """Recalculate the cost of past profile requests (or embedding: emb) current-priced. Former magazine — into .bak."""
    rows = read(path)
    if not rows:
        return 0
    byid = profiles_by_id(cfg)
    n_changed = 0
    out = []
    for r in rows:
        n = normalize(cfg, dict(r, cost=None), byid)
        hit = (key == "emb" and n["kind"] == "emb") or n["key"] == key or (key == "all" and n["ptype"] == "cloud")
        if hit and n["ptype"] == "cloud":
            new = n["cost"]
            if r.get("cost") != new:
                r = dict(r, cost=new)
                n_changed += 1
        out.append(r)
    if n_changed:
        U.atomic_write_text(path.with_name(path.name + ".bak"), path.read_text(encoding="utf-8", errors="replace"))
        U.atomic_write_text(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    return n_changed


# ---------- launch meter and budget ----------
class Meter:
    """Accounting for calls of one launch: log line after each answer, liveline @@USAGE plug-in,
    Check the budget before each payment."""

    def __init__(self, cfg, path: Path, cmd: str = "", notice=None):
        self.cfg = cfg
        self.path = path
        self.cmd = cmd
        self.run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid() % 10000:04d}"
        self.started = time.time()
        self.notice = notice or (lambda text: None)
        self.run = {"calls": 0, "in": 0, "out": 0, "cached": 0, "cost": 0.0, "sec": 0.0, "unpriced": 0, "by_key": {}}
        self._month: tuple[float, dict] | None = None
        self.warned: set[str] = set()
        self.allowed: set[str] = set()

    def _spent(self) -> tuple[float, dict]:
        if self._month is None:
            self._month = month_spent(self.cfg, self.path, self.run_id)
        total, per = self._month
        run_per = {k: v["cost"] for k, v in self.run["by_key"].items()}
        merged = dict(per)
        for k, v in run_per.items():
            merged[k] = merged.get(k, 0.0) + v
        return total + self.run["cost"], merged

    def check_budget(self, profile: dict | None):
        """Before the payment: 80% — warning (once-start), 100% — question «continue»."""
        b = self.cfg.get("budget") or {}
        lim_total = b.get("monthly_usd") or None
        lim_p = (profile or {}).get("budget_month") or None
        if not lim_total and not lim_p:
            return
        total, per = self._spent()
        warn = int(b.get("warn_pct") or 80)
        checks = []
        if lim_total:
            checks.append(("total", float(lim_total), total, "monthly budget"))
        if lim_p and profile:
            checks.append((f"profile:{profile['id']}", float(lim_p), per.get(profile["id"], 0.0),
                           f"profile limit for {profile.get('name')}"))
        for key, lim, spent, what in checks:
            pct = spent / lim * 100 if lim else 0
            if pct >= 100:
                if key in self.allowed:
                    continue
                text = (f"Spent {money(spent)} of the {what} of {money(lim)} ({pct_text(pct)}). The next paid model request "
                        "will exceed it.")
                ch = interact.ask("budget", "Budget exhausted", text,
                                  ["Continue until the end of this launch", "Stop"], default=1)
                if ch == 0:
                    self.allowed.add(key)
                    self.warned.add(key)
                    self.notice(f"Budget exceeded ({what}: {money(spent)} of {money(lim)}) — continuing at your request.")
                    continue
                raise U.BudgetStop(f"Stopped: spent {money(spent)} of the {what} of {money(lim)}. All processed items are saved; "
                                   "to continue, increase the budget (Settings → Second Brain → Expenses) "
                                   "or run again and select Continue.")
            if pct >= warn and key not in self.warned:
                self.warned.add(key)
                msg = f"Spent {pct_text(pct)} of the {what}: {money(spent)} of {money(lim)}."
                print(f"  ! {msg}", flush=True)
                interact.notice(msg)
                self.notice(msg)

    def record(self, kind: str, prompt: str, ptype: str | None, profile: dict | None, model: str, usage: dict | None,
               chars_in: int, chars_out: int, sec: float | None) -> dict:
        inp, out, cached, est = tokens(usage, chars_in, chars_out)
        if kind == "emb":
            c = cost(emb_prices(self.cfg), inp, 0, 0) if ptype == "cloud" else None
            key = f"emb:{model}"
        else:
            c = cost((profile or {}).get("prices"), inp, out, cached) if ptype == "cloud" else None
            key = (profile or {}).get("id") or ("webchat" if ptype == "webchat" else f"model:{model}")
        raw = {k: v for k, v in (usage or {}).items() if k != "_timings"} if isinstance(usage, dict) else None
        rec = {"ts": U.now_iso(), "run": self.run_id, "cmd": self.cmd, "kind": kind, "prompt": prompt,
               "profile": (profile or {}).get("id"), "profile_name": (profile or {}).get("name"), "ptype": ptype,
               "model": model, "in": inp, "out": out, "cached": cached, "est": est,
               "sec": round(sec, 2) if sec is not None else None, "cost": c, "chars_in": chars_in, "chars_out": chars_out,
               "usage": raw}
        U.append_jsonl(self.path, rec)
        r = self.run
        r["calls"] += 1
        r["in"] += inp
        r["out"] += out
        r["cached"] += cached
        r["sec"] += sec or 0
        if c is not None:
            r["cost"] += c
        elif ptype == "cloud":
            r["unpriced"] += 1
        bk = r["by_key"].setdefault(key, {"calls": 0, "cost": 0.0, "name": rec["profile_name"] or key})
        bk["calls"] += 1
        bk["cost"] += c or 0.0
        interact.emit("USAGE", {"prompt": prompt, "kind": kind, "profile": rec["profile"], "profile_name": rec["profile_name"],
                                "ptype": ptype, "model": model, "in": inp, "out": out, "cached": cached, "est": est,
                                "sec": rec["sec"], "cost": c, "run": self.totals()})
        return rec

    def totals(self) -> dict:
        r = self.run
        return {"calls": r["calls"], "in": r["in"], "out": r["out"], "cached": r["cached"], "cost": round(r["cost"], 6),
                "sec": round(r["sec"], 1), "unpriced": r["unpriced"], "elapsed": round(time.time() - self.started, 1)}


# ---------- console ----------
def money(v) -> str:
    if v is None:
        return "—"
    if v and v < 0.01:
        return f"${v:.4f}"
    return f"${v:.2f}"


def pct_text(p: float) -> str:
    return "more than 999%" if p > 999 else f"{p:.0f}%"


def num(x) -> str:
    return f"{int(x):,}".replace(",", " ")


def print_summary(cfg, path: Path):
    s = summary(cfg, path)
    if not s["totals"]["all"]["calls"]:
        print("No model requests have been made yet.")
        return s

    def line(t):
        parts = [f"requests: {num(t['calls'])}", f"tokens: input {num(t['in'])}"
                 + (f" (cached {num(t['cached'])})" if t["cached"] else "") + f", output {num(t['out'])}"]
        if t["cost"] or not t["unpriced"]:
            parts.append(f"cost {money(t['cost'])}" + (" (incomplete; some prices are missing)" if t["unpriced"] else ""))
        if t["est"]:
            parts.append("some token counts are estimated from character counts")
        return "; ".join(parts)
    print(f"Expenses for today: {line(s['totals']['today'])}")
    print(f"This month: {line(s['totals']['month'])}")
    print(f"All time: {line(s['totals']['all'])}")
    b = s["budget"]
    if b["monthly_usd"]:
        print(f"Monthly budget: {money(b['spent'])} of {money(b['monthly_usd'])} ({b['pct']:.0f}%)")
    for p in s["profiles"]:
        t = p["totals"]["month"]
        if not p["totals"]["all"]["calls"]:
            continue
        kind = {"cloud": "cloud", "local": "local", "webchat": "web-based-chat", "fake": "test"}.get(p["ptype"], "")
        extra = f", runtime {round(t['sec'] / 60)} min" if p["ptype"] == "local" else ""
        print(f"  · {p['name']} ({kind}) this month: {line(t)}{extra}")
    return s

"""Model profiles (section 13.2): LMN — cloudy / local / web-based-chat; profile — name, address, key, parameters,
price (cloudy); The steps can work on your profile or through the web.-chat. Transfer of settings v2.4 (llm.model, llm.roles
customized) — loading, memory: The file is rewritten in a new form with the following saving."""
from __future__ import annotations

import copy
import re
from urllib.parse import urlparse

MODES = ("cloud", "local", "webchat", "fake")
KINDS = ("cloud", "local")
PRICE_KEYS = ("input", "cached_input", "output")
PROFILE_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

_LOCAL = re.compile(r"^https?://(localhost|127\.\d+\.\d+\.\d+|\[::1\]|0\.0\.0\.0|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|"
                    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|[^/:]+\.local)(:\d+)?(/|$)", re.I)


def is_local_url(url) -> bool:
    """Your server. (llama.cpp) on this computer or on the home network — key is optional."""
    return bool(_LOCAL.match(str(url or "").strip()))


COMMON = {"temperature": 0.2, "max_tokens": None, "json_mode": False, "extra": {}}
KIND_DEFAULTS = {
    "cloud": {"name": "Cloud model", "kind": "cloud", "base_url": "https://api.z.ai/api/paas/v4", "model": "",
              "api_key_file": "", **COMMON, "timeout_sec": 600, "max_input_chars": 300000,
              "prices": {"input": None, "cached_input": None, "output": None}, "budget_month": None},
    "local": {"name": "Local model", "kind": "local", "base_url": "http://127.0.0.1:8080/v1", "model": "local",
              "api_key_file": "", **COMMON, "timeout_sec": 1800, "max_input_chars": 40000},
}
PROFILE_KEYS = {k: ("id",) + tuple(v) for k, v in KIND_DEFAULTS.items()}
# field, profiled (test-and-title)
ALL_PROFILE_KEYS = tuple(dict.fromkeys(PROFILE_KEYS["cloud"] + PROFILE_KEYS["local"]))
CONNECTION_KEYS = ("base_url", "model", "api_key_file", "temperature", "timeout_sec", "max_tokens", "max_input_chars",
                   "json_mode", "extra")

DEFAULT_PROFILES = [dict(copy.deepcopy(KIND_DEFAULTS["cloud"]), id="p1", name="Z.ai", api_key_file="api_key.txt")]


def default_profile(kind: str, pid: str) -> dict:
    p = copy.deepcopy(KIND_DEFAULTS["local" if kind == "local" else "cloud"])
    p["id"] = pid
    return p


def key_file_name(pid: str) -> str:
    return f"api_key_{pid}.txt"


def normalize_profile(p: dict) -> dict:
    """Missing fields — default profile type; local (price) clean up."""
    if not isinstance(p, dict):
        return p
    kind = p.get("kind") if p.get("kind") in KINDS else ("local" if is_local_url(p.get("base_url")) else "cloud")
    base = copy.deepcopy(KIND_DEFAULTS[kind])
    out = {"id": p.get("id")}
    for k, v in base.items():
        val = p.get(k, v)
        if k == "prices" and (isinstance(val, dict) or val is None):
            val = {**v, **(val or {})}  # Unexplained price fields remain — Theyll be tested.
        out[k] = val
    out["kind"] = kind
    for k, v in p.items():  # We leave the unknown fields — check-up
        if k not in out:
            out[k] = v
    if out.get("api_key_file") is None:
        out["api_key_file"] = ""
    return out


def _host(url) -> str:
    try:
        return urlparse(str(url or "")).hostname or ""
    except ValueError:
        return ""


def auto_name(base_url, model, kind: str) -> str:
    host = _host(base_url)
    if kind == "local":
        return f"{model}" if model and model != "local" else "Local model"
    prov = "Z.ai" if host.endswith("z.ai") else (host.removeprefix("api.") if host else "")
    m = str(model or "").strip()
    if prov and m:
        return f"{prov} · {m}"
    return m or prov or "Cloud model"


# ---------- transference v2.4 ----------
OLD_KEYS = ("base_url", "model", "api_key_file", "temperature", "timeout_sec", "json_mode", "max_tokens", "extra", "max_input_chars")
OLD_DEFAULTS = {"mode": "api", "base_url": "https://api.z.ai/api/paas/v4", "model": "", "api_key_file": "api_key.txt",
                "temperature": 0.2, "timeout_sec": 600, "json_mode": False, "max_tokens": None, "extra": {},
                "max_input_chars": 300000, "max_format_retries": 2}


def needs_migration(llm) -> bool:
    if not isinstance(llm, dict) or "profiles" in llm:
        return False
    roles = llm.get("roles") if isinstance(llm.get("roles"), dict) else {}
    return (any(k in llm for k in OLD_KEYS) or llm.get("mode") == "api"
            or any(isinstance(v, dict) for v in roles.values()))


def _url(u) -> str:
    return str(u or "").strip().rstrip("/")


def migrate_llm(llm: dict) -> dict:
    """Section llm from v2.4 → profiles v2.5. The basic model — profile p1 (key-file), step-model —
    profiles (similar settings — profile), step mode: webchat — «webchat»."""
    old = dict(OLD_DEFAULTS)
    old.update({k: v for k, v in llm.items() if k in OLD_DEFAULTS})
    if not isinstance(old.get("extra"), dict):
        old["extra"] = {}
    main_kind = "local" if is_local_url(old["base_url"]) else "cloud"
    p1 = default_profile(main_kind, "p1")
    for k in OLD_KEYS:
        p1[k] = copy.deepcopy(old[k])
    p1["name"] = auto_name(old["base_url"], old["model"], main_kind)
    profiles = [p1]
    roles_new: dict = {}
    old_mode = old.get("mode")
    for step, r in (llm.get("roles") or {}).items() if isinstance(llm.get("roles"), dict) else []:
        if isinstance(r, str):
            roles_new[step] = r
            continue
        if not isinstance(r, dict) or not r:
            continue
        if r.get("mode") == "webchat":
            roles_new[step] = "webchat"
            continue
        eff = {k: copy.deepcopy(old[k]) for k in OLD_KEYS}
        for k in OLD_KEYS:
            if r.get(k) not in (None, ""):
                eff[k] = copy.deepcopy(r[k])
        if _url(r.get("base_url")) and _url(r.get("base_url")) != _url(old["base_url"]) and not r.get("api_key_file"):
            eff["api_key_file"] = ""  # address: The key was not sent there.
        forced_api = old_mode == "webchat" and r.get("mode") == "api"
        if all(eff[k] == p1[k] for k in OLD_KEYS):
            if forced_api:
                roles_new[step] = "p1"
            continue
        found = next((p for p in profiles if all(p.get(k) == eff[k] for k in OLD_KEYS)), None)
        if found is None:
            kind = "local" if is_local_url(eff["base_url"]) else "cloud"
            found = default_profile(kind, f"p{len(profiles) + 1}")
            found.update(eff)
            name = auto_name(eff["base_url"], eff["model"], kind)
            if any(p["name"] == name for p in profiles):
                name = f"{name} ({step})"
            found["name"] = name
            profiles.append(found)
        roles_new[step] = found["id"]
    mode = {"api": main_kind, "webchat": "webchat", "fake": "fake"}.get(old_mode, old_mode if old_mode in MODES else "cloud")
    out = {
        "mode": mode,
        "cloud_profile": next((p["id"] for p in profiles if p["kind"] == "cloud"), ""),
        "local_profile": next((p["id"] for p in profiles if p["kind"] == "local"), ""),
        "profiles": profiles,
        "webchat": {"max_input_chars": old["max_input_chars"]},
        "roles": roles_new,
        "max_format_retries": llm.get("max_format_retries", 2),
    }
    for k in ("fake_module",):
        if k in llm:
            out[k] = llm[k]
    return out


# slurring v2.7 (Ollama s qwen3-embedding): s v2.7 model — KaLM-Embedding-Gemma3 on llama.cpp
OLD_EMB_URLS = ("http://localhost:11434/v1", "http://127.0.0.1:11434/v1")
OLD_EMB_MODELS = ("qwen3-embedding:8b-q8_0",)


def migrate_embeddings(emb) -> dict:
    if isinstance(emb, dict) and emb.get("mode") == "api":
        emb = dict(emb, mode="cloud")
    if isinstance(emb, dict) and emb.get("mode", "local") == "local" and \
            str(emb.get("base_url") or "").rstrip("/") in OLD_EMB_URLS and str(emb.get("model") or "") in OLD_EMB_MODELS:
        emb = {k: v for k, v in emb.items() if k not in ("base_url", "model")}  # lapse — new
    return emb


def migrate_updates(up) -> dict:
    """Do v2.7 repository-token GitHub were in the settings; link — into brain/__init__.py."""
    if isinstance(up, dict):
        up = {k: v for k, v in up.items() if k not in ("repo", "token_file")}
    return up


def finalize(data: dict) -> dict:
    """After the merger with the silence: Profiles are supplemented by default fields."""
    llm = data.get("llm")
    if isinstance(llm, dict) and isinstance(llm.get("profiles"), list):
        llm["profiles"] = [normalize_profile(p) for p in llm["profiles"]]
    if isinstance(llm, dict) and isinstance(llm.get("roles"), dict):
        llm["roles"] = {k: v for k, v in llm["roles"].items() if v not in (None, "", "main")}
    return data


# ---------- step-taker ----------
def profiles_by_id(cfg_or_llm) -> dict:
    llm = cfg_or_llm["llm"] if "llm" in cfg_or_llm else cfg_or_llm
    return {p.get("id"): p for p in (llm.get("profiles") or []) if isinstance(p, dict)}


def main_profile_id(llm: dict) -> str | None:
    mode = llm.get("mode")
    if mode == "cloud":
        return llm.get("cloud_profile") or None
    if mode == "local":
        return llm.get("local_profile") or None
    if mode == "fake":
        return llm.get("cloud_profile") or llm.get("local_profile") or next(
            (p.get("id") for p in llm.get("profiles") or [] if isinstance(p, dict)), None)
    return None


def target(cfg, prompt: str) -> tuple[str, dict | None]:
    """Who answers the step: ("webchat", None) | ("profile", profile) | ("fake", profile None) |
    ("missing", None) — Main mode profile not selected or removed."""
    llm = cfg["llm"]
    byid = profiles_by_id(llm)
    r = (llm.get("roles") or {}).get(prompt)
    if llm.get("mode") == "fake":
        if r == "webchat":
            return "webchat", None
        return "fake", byid.get(r) or byid.get(main_profile_id(llm))
    if r == "webchat":
        return "webchat", None
    if isinstance(r, str) and r in byid:
        return "profile", byid[r]
    if llm.get("mode") == "webchat":
        return "webchat", None
    p = byid.get(main_profile_id(llm))
    if p is None:
        return "missing", None
    return "profile", p


def mode_ru(mode: str) -> str:
    return {"cloud": "cloud-model", "local": "local model", "webchat": "web-based-chat", "fake": "test-model"}.get(mode, mode)


def input_limit(cfg, prompt: str) -> int:
    """Step request limit, sign: profile, step-response, or-chat."""
    kind, p = target(cfg, prompt)
    if kind == "webchat":
        return int((cfg["llm"].get("webchat") or {}).get("max_input_chars") or 300000)
    if p is not None:
        return int(p.get("max_input_chars") or 300000)
    return 300000

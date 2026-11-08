"""Профили моделей (раздел 13.2): режим ЛЛМ — облачная / локальная / веб-чат; профиль — имя, адрес, ключ, параметры,
цены (у облачных); шаги могут работать на своём профиле или через веб-чат. Перенос настроек v2.4 (llm.model, llm.roles
с настройками) — при загрузке, в памяти: файл переписывается в новом виде при следующем сохранении."""
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
    """Свой сервер (llama.cpp) на этом компьютере или в домашней сети — ключ не обязателен."""
    return bool(_LOCAL.match(str(url or "").strip()))


COMMON = {"temperature": 0.2, "max_tokens": None, "json_mode": False, "extra": {}}
KIND_DEFAULTS = {
    "cloud": {"name": "Облачная модель", "kind": "cloud", "base_url": "https://api.z.ai/api/paas/v4", "model": "",
              "api_key_file": "", **COMMON, "timeout_sec": 600, "max_input_chars": 300000,
              "prices": {"input": None, "cached_input": None, "output": None}, "budget_month": None},
    "local": {"name": "Локальная модель", "kind": "local", "base_url": "http://127.0.0.1:8080/v1", "model": "local",
              "api_key_file": "", **COMMON, "timeout_sec": 1800, "max_input_chars": 40000},
}
PROFILE_KEYS = {k: ("id",) + tuple(v) for k, v in KIND_DEFAULTS.items()}
# поля, которые можно задать профилю (для проверки и подсказок)
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
    """Недостающие поля — по умолчанию для вида профиля; лишние у локального (цены) убираются."""
    if not isinstance(p, dict):
        return p
    kind = p.get("kind") if p.get("kind") in KINDS else ("local" if is_local_url(p.get("base_url")) else "cloud")
    base = copy.deepcopy(KIND_DEFAULTS[kind])
    out = {"id": p.get("id")}
    for k, v in base.items():
        val = p.get(k, v)
        if k == "prices" and (isinstance(val, dict) or val is None):
            val = {**v, **(val or {})}  # непонятные поля цены остаются — о них скажет проверка
        out[k] = val
    out["kind"] = kind
    for k, v in p.items():  # неизвестные поля оставляем — проверка скажет о них
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
        return f"{model}" if model and model != "local" else "Локальная модель"
    prov = "Z.ai" if host.endswith("z.ai") else (host.removeprefix("api.") if host else "")
    m = str(model or "").strip()
    if prov and m:
        return f"{prov} · {m}"
    return m or prov or "Облачная модель"


# ---------- перенос из v2.4 ----------
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
    """Раздел llm из v2.4 → профили v2.5. Основная модель — профиль p1 (файл ключа прежний), свои модели шагов —
    отдельные профили (одинаковые настройки — один профиль), шаги с mode: webchat — «webchat»."""
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
            eff["api_key_file"] = ""  # другой адрес: общий ключ туда не отправлялся
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


# умолчания эмбеддингов до v2.7 (Ollama с qwen3-embedding): с v2.7 своя модель — KaLM-Embedding-Gemma3 на llama.cpp
OLD_EMB_URLS = ("http://localhost:11434/v1", "http://127.0.0.1:11434/v1")
OLD_EMB_MODELS = ("qwen3-embedding:8b-q8_0",)


def migrate_embeddings(emb) -> dict:
    if isinstance(emb, dict) and emb.get("mode") == "api":
        emb = dict(emb, mode="cloud")
    if isinstance(emb, dict) and emb.get("mode", "local") == "local" and \
            str(emb.get("base_url") or "").rstrip("/") in OLD_EMB_URLS and str(emb.get("model") or "") in OLD_EMB_MODELS:
        emb = {k: v for k, v in emb.items() if k not in ("base_url", "model")}  # прежние умолчания — на новые
    return emb


def migrate_updates(up) -> dict:
    """До v2.7 ссылка на репозиторий и токен GitHub были в настройках; теперь ссылка — в brain/__init__.py."""
    if isinstance(up, dict):
        up = {k: v for k, v in up.items() if k not in ("repo", "token_file")}
    return up


def finalize(data: dict) -> dict:
    """После слияния с умолчаниями: профили дополняются полями по умолчанию."""
    llm = data.get("llm")
    if isinstance(llm, dict) and isinstance(llm.get("profiles"), list):
        llm["profiles"] = [normalize_profile(p) for p in llm["profiles"]]
    if isinstance(llm, dict) and isinstance(llm.get("roles"), dict):
        llm["roles"] = {k: v for k, v in llm["roles"].items() if v not in (None, "", "main")}
    return data


# ---------- кто отвечает на шаг ----------
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
    """Кто отвечает на шаг: ("webchat", None) | ("profile", профиль) | ("fake", профиль или None) |
    ("missing", None) — профиль основного режима не выбран или удалён."""
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
    return {"cloud": "облачная модель", "local": "локальная модель", "webchat": "веб-чат", "fake": "тестовая модель"}.get(mode, mode)


def input_limit(cfg, prompt: str) -> int:
    """Предел запроса шага, знаков: у профиля, который отвечает на шаг, или у веб-чата."""
    kind, p = target(cfg, prompt)
    if kind == "webchat":
        return int((cfg["llm"].get("webchat") or {}).get("max_input_chars") or 300000)
    if p is not None:
        return int(p.get("max_input_chars") or 300000)
    return 300000

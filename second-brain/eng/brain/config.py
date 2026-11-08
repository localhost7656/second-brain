"""Program settings (section 17 specification)."""
from __future__ import annotations

import copy
import os
import re
from pathlib import Path

import yaml

from .llama import ALIAS as LLAMA_MODEL, SERVER_DEFAULTS as LLAMA_SERVER
from .profiles import DEFAULT_PROFILES, finalize, migrate_embeddings, migrate_llm, migrate_updates, needs_migration
from .util import UserError, atomic_write_text

PROGRAM_DIR = Path(__file__).resolve().parent.parent
# pattern: No program in the archive settings.yaml, So unpacking the new version over the old one doesnt wipe yours.
# setting; first-run program (or «Install.bat») copy settings.yaml
TEMPLATE_NAME = "settings.template.yaml"

DEFAULTS: dict = {
    "vault": "D:/Second Brain",
    "llm": {
        "mode": "cloud",            # cloud — cloud-model | local — own on this computer | webchat — manually | fake — test
        "cloud_profile": "p1",      # cloud-model profile (from profiles)
        "local_profile": "",        # local model profile
        "profiles": copy.deepcopy(DEFAULT_PROFILES),  # model profile: address, model, key, parameters, price
        "webchat": {"max_input_chars": 300000},       # request limit for manual mode
        "roles": {},                # Your profile for individual steps: {"Synthesis": "p2", "Questions": "webchat"}
        "max_format_retries": 2,
        "fake_module": "tests/fake_llm.py",
    },
    "embeddings": {
        "mode": "local",            # local — model llama.cpp (server) | cloud | fake
        "base_url": "http://127.0.0.1:8081/v1",   # button «Run the model…» self-enter
        "model": LLAMA_MODEL,       # KaLM-Embedding-Gemma3-12B-2511
        "api_key_file": "embeddings_api_key.txt",
        "batch": 16,
        "max_chars": 6000,
        "timeout_sec": 600,
        "price_input": None,        # $ post 1 million (cloud-emblem)
        "server": copy.deepcopy(LLAMA_SERVER),  # settings of the launch model (window «Run the model…»)
    },
    "budget": {"monthly_usd": None, "warn_pct": 80},       # Monthly budget for cloud models, $
    "estimate": {"enabled": True, "calls": 30, "usd": 0.5, "minutes": 10},  # pre-launch
    "input": {"split_by_dates": True},                     # datebook — date-by-date
    "updates": {"check_on_start": True},  # repository — into brain/__init__.py (UPDATE_REPO)
    "thresholds": {
        "classification": 70,
        "hint_shift": 15,
        "high": 90,
        "mode_guess": 70,
        "compaction": 60,
        "value_min": 30,
        "value_primary": 70,
        "duplicate_similarity": 0.86,
        "neighbor_similarity": 0.88,
        "pattern_similarity": 0.80,
    },
    "limits": {
        "max_containers_in_prompt": 150,
        "max_items_per_value_call": 400,
        "max_questions_per_entity": 3,
    },
    "seed_dormancy_days": 90,
    "dialogue_markers": {"user": ["Me:"], "ai": ["AI:"]},
    "sources": [
        {"name": "archive", "color": "#94A3B8", "compaction_shift": 0},
        {"name": "note", "color": "#60A5FA", "compaction_shift": 0},
        {"name": "Chat with AI", "color": "#A78BFA", "compaction_shift": 20},
    ],
    "style": {
        "global": "Write clearly and concisely in the language of the source material. Preserve the author's meaning and important details.",
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, data: dict, path: Path | None):
        self.data = data
        self.path = path
        self.program_dir = path.parent if path else PROGRAM_DIR
        self.vault_override: str | None = None  # --vault: Plugin transfers open storage, settings.yaml change

    # convenient
    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, default=None):
        return self.data.get(k, default)

    def __contains__(self, k):
        return k in self.data

    @property
    def vault(self) -> Path:
        return Path(os.path.expanduser(str(self.vault_override or self.data["vault"])))

    @property
    def th(self) -> dict:
        return self.data["thresholds"]

    def program_file(self, rel: str) -> Path:
        """Program file (smack-and-t.p..): relative-path — program-folder."""
        p = Path(rel)
        return p if p.is_absolute() else PROGRAM_DIR / p

    def secret(self, rel: str) -> str | None:
        """Key key: near-to-be settings.yaml, then in the program folder."""
        p = Path(rel)
        candidates = [p] if p.is_absolute() else [self.program_dir / p, PROGRAM_DIR / p]
        for c in candidates:
            if c.exists():
                key = c.read_text(encoding="utf-8-sig").strip()
                return key or None
        return None

    def source_shift(self, source: str | None) -> int:
        for s in self.data.get("sources") or []:
            if str(s.get("name", "")).lower() == str(source or "").lower():
                return int(s.get("compaction_shift") or 0)
        return 0

    def markers(self) -> tuple[list[str], list[str]]:
        dm = self.data.get("dialogue_markers") or {}
        return list(dm.get("user") or ["Me:"]), list(dm.get("ai") or ["AI:"])


def ensure_settings(path: Path) -> bool:
    """First launch: settings.yaml not yet — sample settings.template.yaml near. True — created."""
    path = Path(path)
    tpl = path.with_name(TEMPLATE_NAME)
    if path.exists() or not tpl.is_file():
        return False
    atomic_write_text(path, tpl.read_bytes().decode("utf-8-sig"))
    return True


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        env = os.environ.get("BRAIN_SETTINGS")
        path = Path(env) if env else PROGRAM_DIR / "settings.yaml"
        if not env:
            ensure_settings(path)
    path = Path(path)
    if not path.exists():
        raise UserError(f"Settings file not found: {path}")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251", errors="replace")  # file saved in «ANSI»
    text = fix_windows_paths(text)
    try:
        user = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
        where = f" (line {mark.line + 1})" if mark is not None else ""
        raise UserError(f"Error in settings file {path.name}{where}. Common causes include tabs instead of spaces, missing quotes, or a missing colon. "
                        f"Details: {e}")
    if not isinstance(user, dict):
        raise UserError(f"Settings file {path.name} must contain a mapping of setting names to values.")
    return Config(prepare(user), path.resolve())


def prepare(user: dict) -> dict:
    """User settings → full: transference, silence, profilefields."""
    user = dict(user or {})
    if needs_migration(user.get("llm")):
        user["llm"] = migrate_llm(user["llm"])
    if isinstance(user.get("embeddings"), dict):
        user["embeddings"] = migrate_embeddings(user["embeddings"])
    if isinstance(user.get("updates"), dict):
        user["updates"] = migrate_updates(user["updates"])
    return finalize(_merge(DEFAULTS, user))


WIN_PATH_IN_QUOTES = re.compile(r'"([A-Za-z]:\\[^"\n]*)"')


def fix_windows_paths(text: str) -> str:
    """Way, conductor-copied (D:\\folder), double-quote YAML breaker: backslash — special-symbol.
    We re-write these paths in direct slashes. — Windows They understand it the same way.."""
    return WIN_PATH_IN_QUOTES.sub(lambda m: '"' + m.group(1).replace("\\", "/") + '"', text)

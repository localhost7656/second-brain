"""Настройки программы (раздел 17 спецификации)."""
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
# образец настроек: в архиве программы нет settings.yaml, чтобы распаковка новой версии поверх старой не затёрла ваши
# настройки; при первом запуске программа (или «Установка.bat») копирует образец в settings.yaml
TEMPLATE_NAME = "settings.template.yaml"

DEFAULTS: dict = {
    "vault": "D:/Второй мозг",
    "llm": {
        "mode": "cloud",            # cloud — облачная модель | local — своя на этом компьютере | webchat — вручную | fake — тесты
        "cloud_profile": "p1",      # профиль облачной модели (из profiles)
        "local_profile": "",        # профиль локальной модели
        "profiles": copy.deepcopy(DEFAULT_PROFILES),  # профили моделей: адрес, модель, ключ, параметры, цены
        "webchat": {"max_input_chars": 300000},       # предел запроса для ручного режима
        "roles": {},                # свой профиль для отдельных шагов: {"Синтез": "p2", "Вопросы": "webchat"}
        "max_format_retries": 2,
        "fake_module": "tests/fake_llm.py",
    },
    "embeddings": {
        "mode": "local",            # local — своя модель на llama.cpp (или другой сервер) | cloud | fake
        "base_url": "http://127.0.0.1:8081/v1",   # кнопка «Запустить модель…» вписывает адрес сама
        "model": LLAMA_MODEL,       # KaLM-Embedding-Gemma3-12B-2511
        "api_key_file": "embeddings_api_key.txt",
        "batch": 16,
        "max_chars": 6000,
        "timeout_sec": 600,
        "price_input": None,        # $ за 1 млн токенов (облачные эмбеддинги)
        "server": copy.deepcopy(LLAMA_SERVER),  # параметры запуска своей модели (окно «Запустить модель…»)
    },
    "budget": {"monthly_usd": None, "warn_pct": 80},       # месячный бюджет на облачные модели, $
    "estimate": {"enabled": True, "calls": 30, "usd": 0.5, "minutes": 10},  # оценка перед большим запуском
    "input": {"split_by_dates": True},                     # дневник с датами — по записи на дату
    "updates": {"check_on_start": True},  # ссылка на репозиторий — в brain/__init__.py (UPDATE_REPO)
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
    "dialogue_markers": {"user": ["я:"], "ai": ["ИИ:"]},
    "sources": [
        {"name": "архив", "color": "#94A3B8", "compaction_shift": 0},
        {"name": "заметка", "color": "#60A5FA", "compaction_shift": 0},
        {"name": "Чат с ИИ", "color": "#A78BFA", "compaction_shift": 20},
    ],
    "style": {
        "global": "Пиши ясно и по делу, без воды и общих фраз. Сохраняй формулировки автора там, где они точны.",
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
        self.vault_override: str | None = None  # --vault: плагин передаёт открытое хранилище, settings.yaml не меняется

    # удобный доступ
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
        """Файл программы (промпты и т.п.): относительные пути — от папки программы."""
        p = Path(rel)
        return p if p.is_absolute() else PROGRAM_DIR / p

    def secret(self, rel: str) -> str | None:
        """Ключ: сначала рядом с settings.yaml, затем в папке программы."""
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
        return list(dm.get("user") or ["я:"]), list(dm.get("ai") or ["ИИ:"])


def ensure_settings(path: Path) -> bool:
    """Первый запуск: settings.yaml ещё нет — создать его из образца settings.template.yaml рядом. True — создан."""
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
        raise UserError(f"Не найден файл настроек: {path}")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251", errors="replace")  # файл сохранён в «ANSI»
    text = fix_windows_paths(text)
    try:
        user = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
        where = f" (строка {mark.line + 1})" if mark is not None else ""
        raise UserError(f"Ошибка в файле настроек {path.name}{where}. Частые причины: отступ сделан клавишей Tab — "
                        "нужны пробелы, как в соседних строках; пропала кавычка; двоеточие в тексте без кавычек. "
                        f"Подробно: {e}")
    if not isinstance(user, dict):
        raise UserError(f"Файл настроек {path.name} испорчен: ожидались строки вида «название: значение».")
    return Config(prepare(user), path.resolve())


def prepare(user: dict) -> dict:
    """Настройки пользователя → полные: перенос из прежних версий, умолчания, поля профилей."""
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
    """Путь, скопированный из Проводника (D:\\Папка), в двойных кавычках YAML ломает: обратный слэш там — спецсимвол.
    Такие пути переписываем прямыми слэшами — Windows их понимает так же."""
    return WIN_PATH_IN_QUOTES.sub(lambda m: '"' + m.group(1).replace("\\", "/") + '"', text)

"""Схема настроек (раздел 17): описания для плагина, проверка значений, запись settings.yaml с пояснениями,
файлы ключей. Пороги — общие (settings.yaml) и свои у контейнера (поле thresholds в его YAML, раздел 17.4)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import yaml

from . import util as U
from .util import UserError

PROMPT_NAMES = ["Структура", "Классификация", "Вопросы", "Уплотнение", "Извлечение", "Анализ пула", "Ценность",
                "Сравнение версий", "Новый составной тип", "Синтез", "Пороги"]
PROMPT_HELP = {
    "Структура": "черновик структуры при первой загрузке",
    "Классификация": "куда отнести запись; самый частый вызов",
    "Вопросы": "уточняющие вопросы к неполным записям",
    "Уплотнение": "сжатие зашумлённых записей и диалогов",
    "Извлечение": "аспекты из записи",
    "Анализ пула": "дубли, противоречия, составные аспекты",
    "Ценность": "оценка ценности аспектов",
    "Сравнение версий": "что пропало в новой версии базы или документа",
    "Новый составной тип": "команда «Паттерны»",
    "Синтез": "документы Фазы 2 — здесь важнее всего качество текста",
    "Пороги": "совет по порогам контейнера",
}
PROMPT_SLUG = {"Структура": "structure", "Классификация": "classification", "Вопросы": "questions",
               "Уплотнение": "compaction", "Извлечение": "extraction", "Анализ пула": "pool", "Ценность": "value",
               "Сравнение версий": "versions", "Новый составной тип": "patterns", "Синтез": "synthesis",
               "Пороги": "thresholds"}
# шаги, у которых длинный материал делится на части по «пределу запроса» (свой предел шага — для модели с малым окном)
SPLIT_PROMPTS = ("Структура", "Классификация", "Анализ пула")

# ---------- пороги ----------
_P = "Шкала 0–100."
_S = "Похожесть от 0 до 1."
THRESHOLDS: dict[str, dict] = {
    "classification": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": True,
                       "label": "Раскладка без вопроса",
                       "help": f"{_P} С этой уверенности модели запись раскладывается в контейнер сама, ниже — уходит в "
                               "_на_проверку с вопросом. Выше — меньше ошибок раскладки, но больше вопросов."},
    "hint_shift": {"kind": "int", "min": 0, "max": 50, "step": 1, "per_container": True,
                   "label": "Вес вашей подсказки",
                   "help": "Сколько пунктов уверенности прибавляется варианту из подсказки hint:. Больше — подсказка чаще "
                           "перевешивает мнение модели."},
    "high": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": True,
             "label": "Высокая уверенность",
             "help": f"{_P} С этой уверенности программа сама создаёт контейнеры и под-контейнеры, делает запись общей "
                     "для нескольких контейнеров, переводит росток в проекты. Ниже — спрашивает."},
    "mode_guess": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": False,
                   "label": "Догадка о режиме файла",
                   "help": f"{_P} С этой уверенности модель сама решает, массовая ли это загрузка или одна запись. "
                           "Касается входящих файлов до раскладки, поэтому бывает только общим."},
    "compaction": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": True,
                   "label": "Уплотнение",
                   "help": f"{_P} С этой зашумлённости запись сначала сжимается моделью (исходный текст остаётся). "
                           "Ниже — сжимается больше записей (дороже, чище аспекты)."},
    "value_min": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": True,
                  "label": "Минимальная ценность",
                  "help": f"{_P} Аспекты ценнее этого идут в базу синтеза, остальные остаются только в пуле. "
                          "Выше — база компактнее, но может потерять детали."},
    "value_primary": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": True,
                      "label": "Первостепенное",
                      "help": f"{_P} С этой ценности аспект считается первостепенным — документы опираются на него в первую очередь."},
    "duplicate_similarity": {"kind": "float", "min": 0.5, "max": 0.99, "step": 0.01, "per_container": True,
                             "label": "Похожесть для поиска дублей",
                             "help": f"{_S} С такой похожести пары аспектов показываются модели как возможные дубли. "
                                     "Ниже — модель видит больше пар (меньше пропущенных дублей, но дороже и больше ложных)."},
    "neighbor_similarity": {"kind": "float", "min": 0.5, "max": 0.99, "step": 0.01, "per_container": True,
                            "label": "Похожесть соседей",
                            "help": f"{_S} С такой похожести записи из разных контейнеров программа спрашивает, всё ли "
                                    "разложено верно. Ниже — таких вопросов больше."},
    "pattern_similarity": {"kind": "float", "min": 0.5, "max": 0.99, "step": 0.01, "per_container": True,
                           "label": "Похожесть для паттернов",
                           "help": f"{_S} Насколько близкими должны быть аспекты, чтобы команда «Паттерны» сочла их связкой."},
}
SEED_DORMANCY = {"kind": "int", "min": 7, "max": 3650, "step": 1, "per_container": True,
                 "label": "Дней до вопроса о ростке",
                 "help": "Росток без новых мыслей дольше этого — вопрос «ещё актуален?». Действует только на ростки."}
CONTAINER_THRESHOLDS = {k: v for k, v in THRESHOLDS.items() if v["per_container"]}
CONTAINER_THRESHOLDS["seed_dormancy_days"] = SEED_DORMANCY
# русские названия, если пользователь пишет пороги в YAML контейнера руками
ALIASES = {"раскладка": "classification", "классификация": "classification", "подсказка": "hint_shift",
           "высокая": "high", "высокий": "high", "уплотнение": "compaction", "ценность": "value_min",
           "минимальная_ценность": "value_min", "первостепенное": "value_primary", "первостепенность": "value_primary",
           "дубли": "duplicate_similarity", "соседи": "neighbor_similarity", "паттерны": "pattern_similarity",
           "дремота": "seed_dormancy_days", "дней_ростка": "seed_dormancy_days"}


def parse_number(v, spec: dict):
    """Число из YAML: допускает «0,85» и «80%»; для шкалы 0–1 «86%» — это 0,86. None — если не число или вне диапазона."""
    if isinstance(v, bool):
        return None
    pct = False
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        pct = s.endswith("%")
        try:
            v = float(s.rstrip("%").strip())
        except ValueError:
            return None
    if not isinstance(v, (int, float)):
        return None
    if pct and spec["kind"] != "int" and spec["max"] <= 1:
        v = v / 100
    if spec["kind"] == "int":
        if abs(v - round(v)) > 1e-9:
            return None
        v = int(round(v))
    else:
        v = round(float(v), 3)
    if not spec["min"] <= v <= spec["max"]:
        return None
    return v


def container_overrides(node, warn=None) -> dict:
    """Свои пороги контейнера из поля thresholds его YAML. Непонятные значения пропускаются с предупреждением."""
    raw = node.fm.get("thresholds")
    if raw in (None, "", {}):
        return {}
    if not isinstance(raw, dict):
        if warn:
            warn(f"В контейнере [[{node.title}]] поле thresholds должно быть списком «порог: значение» — пока не учитывается.")
        return {}
    out = {}
    for k, v in raw.items():
        key = str(k).strip()
        key = ALIASES.get(key.lower().replace(" ", "_"), key)
        spec = CONTAINER_THRESHOLDS.get(key)
        if spec is None:
            if warn:
                hint = " (он бывает только общим — в settings.yaml)" if key in THRESHOLDS else ""
                warn(f"В контейнере [[{node.title}]] в thresholds непонятный порог «{k}»{hint} — пропущен.")
            continue
        if v in (None, ""):
            continue
        num = parse_number(v, spec)
        if num is None:
            if warn:
                warn(f"В контейнере [[{node.title}]] порог «{k}»: «{v}» — нужно число от {spec['min']} до {spec['max']}; "
                     "пока действует общий.")
            continue
        out[key] = num
    return out


# ---------- схема настроек для плагина ----------
def F(key, typ, label, help_="", **kw):
    d = {"key": key, "type": typ, "label": label, "help": help_}
    d.update(kw)
    return d


LLAMA_HINT = ("Свой сервер llama.cpp (или другой OpenAI-совместимый): запустите llama-server с языковой моделью и впишите "
              "его адрес, например http://127.0.0.1:8080/v1 (ключ не нужен).")
MODE_CHOICES = {"cloud": "Облачная модель (API)", "local": "Локальная модель (на этом компьютере)",
                "webchat": "Вручную через веб-чат"}
# поля профиля модели: kinds — у каких профилей поле есть (облачный, локальный)
PROFILE_FIELDS = [
    F("name", "text", "Имя профиля", "Как профиль называется в списках, в «Расходах» и в журнале.", kinds=["cloud", "local"]),
    F("base_url", "text", "Адрес API", "OpenAI-совместимый адрес. Z.ai: https://api.z.ai/api/paas/v4 "
      "(подписка GLM Coding Plan: https://api.z.ai/api/coding/paas/v4).", kinds=["cloud"], placeholder="https://api.z.ai/api/paas/v4"),
    F("base_url", "text", "Адрес сервера", LLAMA_HINT, kinds=["local"], placeholder="http://127.0.0.1:8080/v1"),
    F("model", "text", "Модель", "Название модели у провайдера, точно как в его документации.", kinds=["cloud"], placeholder="glm-4.6"),
    F("model", "text", "Модель", "Для llama.cpp — любое название; для других серверов — как в их списке моделей.", kinds=["local"], placeholder="local"),
    F("api_key_file", "key", "Ключ API", "Хранится в файле рядом с программой, не в хранилище.", kinds=["cloud"]),
    F("api_key_file", "key", "Ключ", "Нужен, только если сервер запущен с ключом (--api-key).", kinds=["local"]),
    F("temperature", "float", "Температура", "0–2. Ниже — ответы стабильнее.", min=0, max=2, step=0.05, slider=True,
      kinds=["cloud", "local"]),
    F("max_input_chars", "int", "Предел запроса, знаков", "Больше — материал делится на части автоматически. "
      "300 000 знаков ≈ 100 тыс. токенов. Для модели с небольшим окном — около 3 знаков на токен окна: "
      "при -c 16384 у llama-server — примерно 40 000.", min=8000, max=5000000, kinds=["cloud", "local"]),
    F("max_tokens", "int?", "Предел длины ответа (токенов)", "Пусто — как у провайдера. Если программа скажет "
      "«ответ оборвался» — увеличьте.", min=256, max=1000000, kinds=["cloud", "local"]),
    F("timeout_sec", "int", "Ожидание ответа, секунд", "Своей модели на компьютере может понадобиться больше.",
      min=10, max=7200, kinds=["cloud", "local"]),
    F("json_mode", "bool", "Режим JSON", "Включите, если сервер умеет response_format: json_object — меньше ошибок формата.",
      kinds=["cloud", "local"]),
    F("extra", "json", "Особые параметры запроса", "Добавляются в запрос как есть. Пример для GLM: "
      "{\"thinking\": {\"type\": \"disabled\"}}", kinds=["cloud", "local"]),
    F("prices.input", "float?", "Вход, $ за 1 млн токенов", "Цена запроса — из прайса провайдера.", min=0, max=1000,
      kinds=["cloud"], group="prices"),
    F("prices.cached_input", "float?", "Вход из кэша, $ за 1 млн", "Повторяющееся начало запроса провайдер берёт из кэша "
      "дешевле. Пусто — как обычный вход.", min=0, max=1000, kinds=["cloud"], group="prices"),
    F("prices.output", "float?", "Выход, $ за 1 млн токенов", "Цена ответа (вместе с рассуждениями модели).", min=0,
      max=1000, kinds=["cloud"], group="prices"),
    F("budget_month", "float?", "Лимит профиля в месяц, $", "Пусто — без своего лимита (действует общий бюджет).",
      min=0, max=100000, kinds=["cloud"], group="prices"),
]

TABS = {"main": "Основное", "models": "Модели", "thresholds": "Пороги", "input": "Входящие", "docs": "Документы",
        "costs": "Расходы", "advanced": "Дополнительно"}
SCHEMA = [
    {"id": "updates", "tab": "main", "title": "Обновления", "fields": [
        F("updates.check_on_start", "bool", "Проверять при запуске Obsidian",
          "Если вышла новая версия — плагин предложит установить её (настройки и ключи не трогаются)."),
    ]},
    {"id": "llm", "tab": "models", "title": "Языковая модель", "fields": [
        F("llm", "llm", "Режим и профили",
          "Облачная — по API у провайдера (Z.ai и др.); локальная — ваш сервер llama.cpp; веб-чат — запросы "
          "и ответы файлами в папке _веб-чат. Профиль — сохранённый набор настроек модели: можно держать несколько "
          "и переключаться.", choices=MODE_CHOICES),
    ]},
    {"id": "roles", "tab": "models", "title": "Модели для отдельных шагов", "fields": [
        F("llm.roles", "roles", "Свои модели по шагам",
          "Например, синтез документов — более сильной моделью, классификацию — быстрой или своей на llama.cpp. "
          "«Как основная» — шаг работает на модели из раздела выше.", prompts=PROMPT_NAMES, prompt_help=PROMPT_HELP,
          split_prompts=list(SPLIT_PROMPTS)),
    ]},
    {"id": "embeddings", "tab": "models", "title": "Эмбеддинги (поиск похожего)", "fields": [
        F("embeddings.mode", "choice", "Где считать", "", choices={"local": "На этом компьютере (llama.cpp)",
                                                                  "cloud": "Облачный сервис (нужен ключ)"}),
        F("embeddings.base_url", "text", "Адрес сервера", "Кнопка «Запустить модель…» выше вписывает его сама "
          "(http://127.0.0.1:8081/v1). Свой сервер llama.cpp (llama-server --embedding --pooling last -c 4096 -ub 4096) — впишите его адрес.",
          placeholder="http://127.0.0.1:8081/v1", show_if={"embeddings.mode": ["local"]}),
        F("embeddings.base_url", "text", "Адрес API", "OpenAI-совместимый адрес сервиса эмбеддингов.",
          placeholder="https://api.openai.com/v1", show_if={"embeddings.mode": ["cloud"]}),
        F("embeddings.model", "text", "Модель", "Название модели на сервере; для своей модели программа вписывает его сама. "
          "При смене все векторы пересчитаются сами.", show_if={"embeddings.mode": ["local"]}),
        F("embeddings.model", "text", "Модель", "Название модели у провайдера. При смене все векторы пересчитаются сами.",
          show_if={"embeddings.mode": ["cloud"]}),
        F("embeddings.api_key_file", "key", "Ключ", "Хранится в файле рядом с программой.", target="embeddings",
          show_if={"embeddings.mode": ["cloud"]}),
        F("embeddings.price_input", "float?", "Цена, $ за 1 млн токенов", "Для подсчёта расходов.", min=0, max=1000,
          show_if={"embeddings.mode": ["cloud"]}),
        F("embeddings.batch", "int", "Текстов за один запрос", "", min=1, max=256),
        F("embeddings.max_chars", "int", "Предел текста, знаков", "Длиннее — обрезается для поиска (сама запись не меняется).",
          min=500, max=100000),
        F("embeddings.timeout_sec", "int", "Ожидание ответа, секунд", "", min=10, max=7200),
    ]},
    {"id": "thresholds", "tab": "thresholds", "title": "Общие пороги",
     "help": "Действуют везде, где у контейнера нет своих (свои — во вкладке «Контейнер» панели).",
     "fields": [F(f"thresholds.{k}", v["kind"], v["label"], v["help"], min=v["min"], max=v["max"], step=v["step"], slider=True)
                for k, v in THRESHOLDS.items()]
     + [F("seed_dormancy_days", "int", SEED_DORMANCY["label"], SEED_DORMANCY["help"], min=7, max=3650, step=1)]},
    {"id": "sources", "tab": "input", "title": "Источники", "fields": [
        F("sources", "sources", "Источники записей",
          "Подпапки _staging (например _staging/Чат с ИИ/). Цвет — метка источника в витринах; сдвиг — на сколько "
          "пунктов понизить порог уплотнения для этого источника."),
    ]},
    {"id": "markers", "tab": "input", "title": "Разметка диалогов", "fields": [
        F("dialogue_markers.user", "lines", "Ваши реплики начинаются с", "Через запятую."),
        F("dialogue_markers.ai", "lines", "Реплики ИИ начинаются с", "Через запятую."),
    ]},
    {"id": "input", "tab": "input", "title": "Длинные файлы", "fields": [
        F("input.split_by_dates", "bool", "Делить дневник по датам",
          "Файл, где записи начинаются строкой с датой (12.03.2021, 2021-03-12, «12 марта 2021»), разбирается как "
          "отдельные записи — каждая со своей датой. Исходный файл остаётся целым в _исходники."),
    ]},
    {"id": "style", "tab": "docs", "title": "Стиль документов", "fields": [
        F("style.global", "textarea", "Общий стиль", "Для контейнера — во вкладке «Контейнер», для документа — поле "
          "style_override в его YAML."),
    ]},
    {"id": "budget", "tab": "costs", "title": "Бюджет", "fields": [
        F("budget.monthly_usd", "float?", "Месячный бюджет, $", "На все облачные модели вместе. При 80% — предупреждение, "
          "при 100% — программа остановится перед следующим обращением и спросит, продолжать ли. Пусто — без бюджета. "
          "Цены моделей задаются в профилях («Модели») или во вкладке «Расходы» панели.", min=0, max=100000),
        F("budget.warn_pct", "int", "Предупреждать с, % бюджета", "", min=10, max=99, step=1, slider=True),
    ]},
    {"id": "estimate", "tab": "costs", "title": "Оценка перед большим запуском", "fields": [
        F("estimate.enabled", "bool", "Показывать оценку",
          "Перед запуском программа прикидывает число обращений, время и стоимость и, если запуск большой, "
          "спрашивает подтверждение. Ревалидация спрашивает всегда."),
        F("estimate.calls", "int", "Если обращений больше", "", min=1, max=100000),
        F("estimate.usd", "float", "Или стоимость больше, $", "", min=0, max=10000),
        F("estimate.minutes", "int", "Или дольше, минут", "", min=1, max=10000),
    ]},
    {"id": "limits", "tab": "advanced", "title": "Пределы", "fields": [
        F("limits.max_containers_in_prompt", "int", "Контейнеров в запросе классификации", "", min=10, max=2000),
        F("limits.max_items_per_value_call", "int", "Элементов за одну оценку ценности", "", min=20, max=5000),
        F("limits.max_questions_per_entity", "int", "Уточняющих вопросов на запись", "", min=0, max=10),
        F("llm.max_format_retries", "int", "Повторов при ошибке формата", "Сколько раз просить модель исправить формат ответа.",
          min=0, max=5),
        F("llm.webchat.max_input_chars", "int", "Предел запроса веб-чата, знаков", "Для ручного режима: длиннее — "
          "материал делится на несколько запросов.", min=8000, max=5000000),
    ]},
]


def input_limit(cfg, prompt: str) -> int:
    """Предел запроса шага, знаков: у профиля, который отвечает на шаг (или у веб-чата)."""
    from .profiles import input_limit as _il
    return _il(cfg, prompt)


def get_path(d: dict, key: str):
    cur = d
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


# ---------- проверка ----------
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate(d: dict) -> list[str]:
    """Проверка типов и диапазонов. Незаполненное (адрес, модель, ключ) не ошибка при сохранении — о нём скажет запуск."""
    from .profiles import ALL_PROFILE_KEYS, KINDS, MODES, PRICE_KEYS, PROFILE_ID, PROFILE_KEYS
    errs = []

    def num(key, lo, hi, kind="int", optional=False, v=None, label=None):
        v = get_path(d, key) if v is None and label is None else v
        if v is None and optional:
            return
        ok = _is_num(v) and (kind == "float" or float(v).is_integer())
        if not ok or not lo <= v <= hi:
            errs.append(f"{label or key}: нужно {'целое ' if kind == 'int' else ''}число от {lo} до {hi} (сейчас: {v!r})")

    llm = d.get("llm") or {}
    if llm.get("mode") not in MODES:
        errs.append(f"llm.mode: cloud, local или webchat (сейчас: {llm.get('mode')!r})")
    profiles = llm.get("profiles")
    byid: dict = {}
    if not isinstance(profiles, list):
        errs.append("llm.profiles: нужен список профилей")
        profiles = []
    names = set()
    for i, p in enumerate(profiles, 1):
        if not isinstance(p, dict):
            errs.append(f"llm.profiles[{i}]: нужен профиль вида {{id: …, name: …}}")
            continue
        pid = p.get("id")
        where = f"профиль «{p.get('name') or pid or i}»"
        if not isinstance(pid, str) or not PROFILE_ID.match(pid):
            errs.append(f"{where}: id — латинские буквы и цифры (сейчас: {pid!r})")
            continue
        if pid in byid:
            errs.append(f"{where}: id «{pid}» повторяется")
            continue
        byid[pid] = p
        kind = p.get("kind")
        if kind not in KINDS:
            errs.append(f"{where}: kind — cloud или local (сейчас: {kind!r})")
            continue
        name = str(p.get("name") or "").strip()
        if not name:
            errs.append(f"профиль {pid}: укажите имя")
        elif name.lower() in names:
            errs.append(f"{where}: такое имя уже есть у другого профиля")
        names.add(name.lower())
        for k in p:
            if k not in PROFILE_KEYS[kind]:
                hint = " (цены бывают только у облачных профилей)" if k in ("prices", "budget_month") else ""
                errs.append(f"{where}: неизвестное поле «{k}»{hint}" if k not in ALL_PROFILE_KEYS or hint else
                            f"{where}: поле «{k}» не для этого вида профиля")
        for k in ("base_url", "model", "api_key_file", "name"):
            if p.get(k) is not None and not isinstance(p.get(k), str):
                errs.append(f"{where}: {k} — нужен текст")
        num("", 0, 2, "float", v=p.get("temperature"), label=f"{where}: температура (temperature)")
        num("", 10, 7200, v=p.get("timeout_sec"), label=f"{where}: ожидание ответа (timeout_sec)")
        if p.get("max_tokens") is not None:
            num("", 256, 1000000, v=p.get("max_tokens"), label=f"{where}: предел длины ответа (max_tokens)")
        num("", 8000, 5000000, v=p.get("max_input_chars"), label=f"{where}: предел запроса (max_input_chars)")
        if not isinstance(p.get("json_mode"), bool):
            errs.append(f"{where}: json_mode — true или false")
        if not isinstance(p.get("extra"), dict):
            errs.append(f"{where}: особые параметры — нужен объект вида {{\"параметр\": значение}}")
        if kind == "cloud":
            pr = p.get("prices")
            if not isinstance(pr, dict):
                errs.append(f"{where}: цены — нужны поля input, cached_input, output")
            else:
                for k, v in pr.items():
                    if k not in PRICE_KEYS:
                        errs.append(f"{where}: непонятная цена «{k}» (есть: {', '.join(PRICE_KEYS)})")
                    elif v is not None:
                        num("", 0, 1000, "float", v=v, label=f"{where}: цена {k}")
            if p.get("budget_month") is not None:
                num("", 0, 100000, "float", v=p.get("budget_month"), label=f"{where}: лимит в месяц (budget_month)")
    for key, kind in (("cloud_profile", "cloud"), ("local_profile", "local")):
        v = llm.get(key)
        if v in (None, ""):
            continue
        if v not in byid:
            errs.append(f"llm.{key}: нет профиля «{v}»")
        elif byid[v].get("kind") != kind:
            errs.append(f"llm.{key}: профиль «{byid[v].get('name')}» не {'облачный' if kind == 'cloud' else 'локальный'}")
    wc = llm.get("webchat")
    if not isinstance(wc, dict):
        errs.append("llm.webchat: нужен раздел с max_input_chars")
    else:
        num("llm.webchat.max_input_chars", 8000, 5000000)
    num("llm.max_format_retries", 0, 5)
    roles = llm.get("roles") or {}
    if not isinstance(roles, dict):
        errs.append("llm.roles: нужен список «шаг: профиль»")
        roles = {}
    for name, r in roles.items():
        if name not in PROMPT_NAMES:
            errs.append(f"llm.roles: неизвестный шаг «{name}» (есть: {', '.join(PROMPT_NAMES)})")
        elif not isinstance(r, str) or (r != "webchat" and r not in byid):
            errs.append(f"llm.roles.{name}: нужен id профиля ({', '.join(byid) or 'профилей нет'}) или webchat (сейчас: {r!r})")
    emb = d.get("embeddings") or {}
    if emb.get("mode") not in ("local", "cloud", "fake"):
        errs.append(f"embeddings.mode: local или cloud (сейчас: {emb.get('mode')!r})")
    for key in ("embeddings.base_url", "embeddings.model", "embeddings.api_key_file", "style.global"):
        v = get_path(d, key)
        if v is not None and not isinstance(v, str):
            errs.append(f"{key}: нужен текст")
    from .llama import check_params
    errs += check_params(emb.get("server"))
    num("embeddings.batch", 1, 256)
    num("embeddings.max_chars", 500, 100000)
    num("embeddings.timeout_sec", 10, 7200)
    num("embeddings.price_input", 0, 1000, "float", optional=True)
    num("budget.monthly_usd", 0, 100000, "float", optional=True)
    num("budget.warn_pct", 10, 99)
    for key in ("estimate.enabled", "input.split_by_dates", "updates.check_on_start"):
        if not isinstance(get_path(d, key), bool):
            errs.append(f"{key}: true или false")
    num("estimate.calls", 1, 100000)
    num("estimate.usd", 0, 10000, "float")
    num("estimate.minutes", 1, 10000)
    for k, spec in THRESHOLDS.items():
        num(f"thresholds.{k}", spec["min"], spec["max"], spec["kind"])
    num("seed_dormancy_days", 1, 3650)
    for k in ("max_containers_in_prompt", "max_items_per_value_call", "max_questions_per_entity"):
        num(f"limits.{k}", 0, 100000)
    for who in ("user", "ai"):
        v = get_path(d, f"dialogue_markers.{who}")
        if not isinstance(v, list) or not v or not all(isinstance(x, str) and x.strip() for x in v):
            errs.append(f"dialogue_markers.{who}: нужен хотя бы один непустой маркер")
    src = d.get("sources")
    if not isinstance(src, list):
        errs.append("sources: нужен список источников")
    else:
        names = set()
        for i, s in enumerate(src, 1):
            if not isinstance(s, dict) or not str(s.get("name") or "").strip():
                errs.append(f"sources[{i}]: у источника нужно название")
                continue
            if str(s["name"]).lower() in names:
                errs.append(f"sources: источник «{s['name']}» повторяется")
            names.add(str(s["name"]).lower())
            if s.get("color") and not _COLOR.match(str(s["color"])):
                errs.append(f"sources «{s['name']}»: цвет в виде #RRGGBB")
            cs = s.get("compaction_shift", 0)
            if not isinstance(cs, int) or isinstance(cs, bool) or not -100 <= cs <= 100:
                errs.append(f"sources «{s['name']}»: сдвиг уплотнения — целое от -100 до 100")
    return errs


# ---------- запись settings.yaml ----------
def _y(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and ("e" in repr(v) or "E" in repr(v)):
        return f"{v:.12f}".rstrip("0").rstrip(".")  # 1e-05 YAML прочёл бы как текст
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        return "{" + ", ".join(f"{json.dumps(k, ensure_ascii=False)}: {_y(x) or 'null'}" for k, x in v.items()) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(_y(x) or "null" for x in v) + "]"
    return json.dumps(v, ensure_ascii=False)


def _kv(indent: str, key: str, v, comment: str = "") -> str:
    line = f"{indent}{key}: {_y(v)}".rstrip()
    return f"{line}   # {comment}" if comment else line


SERVER_COMMENTS = {
    "device": "cpu — процессор; gpu — видеокарта",
    "build": "сборка llama.cpp для видеокарты: auto — CUDA для NVIDIA, иначе Vulkan; cuda; vulkan",
    "gpu_layers": "слоёв модели на видеокарте: auto — сколько поместится, all — все (у модели 48), или число",
    "ctx": "контекст, токенов: самый длинный текст за раз; больше — больше памяти (4096 — около 8,4 ГБ, 8192 — 9,6 ГБ)",
    "kv_cache": "квантование KV-кеша: f16 | q8_0 | q4_0 — этой модели почти ничего не даёт (KV-кеш она не хранит)",
    "threads": "потоков процессора; 0 — llama.cpp решит сам",
    "port": "адрес сервера будет http://127.0.0.1:<порт>/v1",
    "sleep_min": "через сколько минут простоя выгружать модель из памяти; 0 — не выгружать",
    "autostart": "программа сама запускает сервер, когда он нужен (ничего не скачивая)",
    "models_dir": "папка для модели (6,9 ГБ); пусто — models в папке программы",
}


def _render_server(srv) -> list[str]:
    """embeddings.server — параметры запуска своей модели (окно «Запустить модель…» в плагине)."""
    from .llama import SERVER_DEFAULTS
    srv = srv if isinstance(srv, dict) else {}
    out = ["  server:              # своя модель на llama.cpp: Настройки → Второй мозг → Модели → «Запустить модель…»"]
    for k in list(SERVER_DEFAULTS) + [k for k in srv if k not in SERVER_DEFAULTS]:
        if k in srv:
            out.append(_kv("    ", k, srv[k], SERVER_COMMENTS.get(k, "")))
    return out


def render(d: dict) -> str:
    """settings.yaml целиком, с пояснениями (плагин и программа переписывают файл этой функцией)."""
    from .profiles import PROFILE_KEYS
    L = d["llm"]
    E = d["embeddings"]
    T = d["thresholds"]
    lim = d.get("limits") or {}
    B = d.get("budget") or {}
    ES = d.get("estimate") or {}
    UP = d.get("updates") or {}
    out = [
        "# Настройки программы «Второй мозг» (раздел 17 спецификации). Удобнее менять в Obsidian:",
        "# Настройки → Второй мозг. Файл лежит рядом с программой, не в хранилище.",
        "# Строки после # — пояснения, программа их не читает.",
        "",
        "# Папка хранилища Obsidian — её вписывает «Установка.bat». Плагин работает с открытым хранилищем;",
        "# эта строка нужна только для запуска программы из командной строки. Слэши можно писать прямые.",
        f"vault: {_y(d.get('vault'))}",
        "",
        "llm:",
        _kv("  ", "mode", L.get("mode"), "cloud — облачная модель; local — своя на этом компьютере (сервер llama.cpp); "
                                         "webchat — вручную через веб-чат"),
        _kv("  ", "cloud_profile", L.get("cloud_profile") or "", "id профиля облачной модели (из списка profiles)"),
        _kv("  ", "local_profile", L.get("local_profile") or "", "id профиля локальной модели"),
        "  profiles:            # профили моделей. Цены — $ за 1 млн токенов (для подсчёта расходов); пусто — не считать деньги",
    ]
    comments = {"base_url": "адрес в формате OpenAI", "model": "название модели, точно как у провайдера",
                "api_key_file": "файл с ключом рядом с программой (в хранилище не попадает)",
                "timeout_sec": "сколько секунд ждать ответа", "max_tokens": "предел длины ответа; пусто — как у провайдера",
                "max_input_chars": "предел запроса, знаков; больше — материал делится на части",
                "json_mode": "true — если сервер умеет response_format: json_object",
                "extra": "особые параметры запроса, например {\"thinking\": {\"type\": \"disabled\"}} у GLM",
                "prices": "вход, вход из кэша, выход — $ за 1 млн токенов", "budget_month": "свой лимит профиля в месяц, $"}
    profiles = L.get("profiles") or []
    if not profiles:
        out[-1] = out[-1].replace("  profiles:            #", "  profiles: []        #", 1)
    for p in profiles:
        keys = list(PROFILE_KEYS.get(p.get("kind"), PROFILE_KEYS["cloud"]))
        keys += [k for k in p if k not in keys]
        first = True
        for k in keys:
            if k not in p:
                continue
            c = comments.get(k, "")
            if k == "model" and not str(p.get("model") or "").strip() and p.get("kind") == "cloud":
                c += " — впишите перед первым запуском"
            out.append(_kv("    - " if first else "      ", k, p[k], c))
            first = False
    out.append(_kv("  ", "webchat", L.get("webchat") or {}, "ручной режим: предел запроса, знаков"))
    roles = L.get("roles") or {}
    if roles:
        out.append("  roles:               # свой профиль для отдельных шагов (id профиля или webchat); не указанные — на основной модели")
        for name in PROMPT_NAMES + sorted(set(roles) - set(PROMPT_NAMES)):
            if name in roles:
                out.append(f"    {_y(name)}: {_y(roles[name])}")
    else:
        out.append("  roles: {}            # свой профиль для шагов, пример: {\"Синтез\": \"p2\", \"Вопросы\": \"webchat\"}")
    out.append(_kv("  ", "max_format_retries", L.get("max_format_retries"), "сколько раз просить модель исправить формат ответа"))
    if L.get("fake_module") and L.get("fake_module") != "tests/fake_llm.py":
        out.append(f"  fake_module: {_y(L.get('fake_module'))}")
    out += [
        "",
        "embeddings:",
        _kv("  ", "mode", E.get("mode"), "local — на этом компьютере (llama.cpp); cloud — облачные эмбеддинги"),
        _kv("  ", "base_url", E.get("base_url"), "адрес сервера; кнопка «Запустить модель…» в плагине вписывает его сама"),
        _kv("  ", "model", E.get("model"), "название модели на сервере; при смене все векторы пересчитаются сами"),
        _kv("  ", "api_key_file", E.get("api_key_file"), "нужен только для mode: cloud"),
        _kv("  ", "batch", E.get("batch"), "текстов за один запрос"),
        _kv("  ", "max_chars", E.get("max_chars"), "длиннее — обрезается для поиска (сама запись не меняется)"),
        _kv("  ", "timeout_sec", E.get("timeout_sec")),
        _kv("  ", "price_input", E.get("price_input"), "облачные эмбеддинги: $ за 1 млн токенов"),
    ]
    out += _render_server(E.get("server"))
    out += [
        "",
        "budget:                # бюджет на облачные модели",
        _kv("  ", "monthly_usd", B.get("monthly_usd"), "$ в месяц на все облачные профили; пусто — без бюджета"),
        _kv("  ", "warn_pct", B.get("warn_pct"), "с этого процента — предупреждение; при 100% программа спросит, продолжать ли"),
        "",
        "estimate:              # оценка перед большим запуском: обращения, время, деньги",
        _kv("  ", "enabled", ES.get("enabled")),
        _kv("  ", "calls", ES.get("calls"), "спрашивать подтверждение, если обращений больше"),
        _kv("  ", "usd", ES.get("usd"), "…или стоимость больше, $"),
        _kv("  ", "minutes", ES.get("minutes"), "…или дольше, минут"),
        "",
        "input:",
        _kv("  ", "split_by_dates", (d.get("input") or {}).get("split_by_dates"),
            "файл-дневник с датами в начале записей — по отдельной записи на дату"),
        "",
        "updates:               # обновления программы с GitHub (ссылка на репозиторий — в brain/__init__.py, UPDATE_REPO)",
        _kv("  ", "check_on_start", UP.get("check_on_start"), "плагин проверяет обновление при запуске Obsidian"),
        "",
        "thresholds:            # общие пороги; свои у контейнера — поле thresholds в его YAML (или вкладка «Контейнер» в плагине)",
    ]
    for k, spec in THRESHOLDS.items():
        first = spec["help"].split(". ")[1] if spec["help"].startswith(("Шкала", "Похожесть")) else spec["help"].split(". ")[0]
        first = first.rstrip(".")
        out.append(f"  {k}: {_y(T.get(k))}   # {spec['label']}: {first[:1].lower() + first[1:]}")
    out += [
        "",
        f"seed_dormancy_days: {_y(d.get('seed_dormancy_days'))} # росток без новых мыслей дольше этого — вопрос «ещё актуален?»",
        "",
        "dialogue_markers:      # разметка диалогов с ИИ в txt",
        f"  user: {_y((d.get('dialogue_markers') or {}).get('user'))}",
        f"  ai: {_y((d.get('dialogue_markers') or {}).get('ai'))}",
        "",
        "sources:               # источники = подпапки _staging (например _staging/Чат с ИИ/). compaction_shift — на сколько пунктов понизить порог уплотнения",
    ]
    for s in d.get("sources") or []:
        out.append(f"  - name: {_y(s.get('name'))}")
        out.append(f"    color: {_y(s.get('color') or '#94A3B8')}")
        out.append(f"    compaction_shift: {_y(int(s.get('compaction_shift') or 0))}")
    out += [
        "",
        "style:                 # стиль документов Фазы 2. Для контейнера — поле style в его YAML, для документа — style_override",
        f"  global: {_y((d.get('style') or {}).get('global') or '')}",
        "",
        "limits:                # пределы запросов к модели — обычно менять не нужно",
        f"  max_containers_in_prompt: {_y(lim.get('max_containers_in_prompt'))}   # контейнеров в запросе классификации",
        f"  max_items_per_value_call: {_y(lim.get('max_items_per_value_call'))}   # элементов за одну оценку ценности",
        f"  max_questions_per_entity: {_y(lim.get('max_questions_per_entity'))}     # уточняющих вопросов на запись",
    ]
    known = {"vault", "llm", "embeddings", "thresholds", "seed_dormancy_days", "dialogue_markers", "sources", "style", "limits",
             "budget", "estimate", "input", "updates"}
    rest = {k: v for k, v in d.items() if k not in known}
    if rest:
        out += ["", "# прочее", yaml.safe_dump(rest, allow_unicode=True, sort_keys=False).rstrip()]
    return "\n".join(out) + "\n"


REPLACE = {("llm", "roles"), ("sources",), ("dialogue_markers", "user"), ("dialogue_markers", "ai")}


def merge_profiles(profiles: list, patch: dict) -> list:
    """Правка профилей по id: {id: {поля}} — изменить, {id: None} — удалить, новый id — добавить."""
    from .profiles import normalize_profile
    out = [copy.deepcopy(p) for p in profiles or []]
    for pid, ch in (patch or {}).items():
        idx = next((i for i, p in enumerate(out) if isinstance(p, dict) and p.get("id") == pid), None)
        if ch is None:
            if idx is not None:
                out.pop(idx)
            continue
        if not isinstance(ch, dict):
            raise UserError(f"Профиль «{pid}»: изменения должны быть объектом.")
        if idx is None:
            out.append(normalize_profile(dict(ch, id=pid)))
            continue
        cur = out[idx]
        for k, v in ch.items():
            if k == "prices" and isinstance(v, dict) and isinstance(cur.get("prices"), dict):
                cur["prices"] = {**cur["prices"], **v}
            else:
                cur[k] = copy.deepcopy(v)
    return out


def merge_patch(base: dict, patch: dict, path=()) -> dict:
    out = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        p = path + (k,)
        if p == ("llm", "profiles") and isinstance(v, dict):
            out[k] = merge_profiles(out.get(k) or [], v)
        elif isinstance(v, dict) and isinstance(out.get(k), dict) and p not in REPLACE:
            out[k] = merge_patch(out[k], v, p)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _fix_refs(data: dict) -> dict:
    """После правки профилей: выбор основной модели, указывающий на удалённый профиль или профиль другого вида, —
    на первый подходящий; шаги, отданные удалённому профилю, — снова на основную модель."""
    llm = data.get("llm")
    if not isinstance(llm, dict) or not isinstance(llm.get("profiles"), list):
        return data
    ids = {p.get("id"): p for p in llm["profiles"] if isinstance(p, dict)}
    for key, kind in (("cloud_profile", "cloud"), ("local_profile", "local")):
        v = llm.get(key)
        if v and (v not in ids or ids[v].get("kind") != kind):
            llm[key] = next((pid for pid, p in ids.items() if p.get("kind") == kind), "")
        elif not v and llm.get("mode") == kind:
            llm[key] = next((pid for pid, p in ids.items() if p.get("kind") == kind), "")
    if isinstance(llm.get("roles"), dict):
        llm["roles"] = {k: v for k, v in llm["roles"].items() if not isinstance(v, str) or v == "webchat" or v in ids}
    return data


def apply_patch(cfg, patch: dict) -> dict:
    """Изменить settings.yaml: patch накладывается на текущие значения, всё проверяется, файл переписывается
    целиком с пояснениями (прежний — в settings.yaml.bak)."""
    from .config import prepare
    data = _fix_refs(prepare(merge_patch(cfg.data, patch)))
    errs = validate(data)
    if errs:
        raise UserError("Настройки не сохранены: " + "; ".join(errs))
    text = render(data)
    check = yaml.safe_load(text)
    if prepare(check) != data:  # запись должна читаться обратно точно так же
        raise UserError("Настройки не сохранены: не удалось записать их без искажений (сообщите об этом).")
    path = Path(cfg.path)
    if path.exists():
        U.atomic_write_text(path.with_name(path.name + ".bak"), path.read_text(encoding="utf-8-sig", errors="replace"))
    U.atomic_write_text(path, text)
    cfg.data = data
    return data


# ---------- ключи ----------
def _profile(cfg, pid: str) -> dict:
    from .profiles import profiles_by_id
    p = profiles_by_id(cfg).get(pid)
    if p is None:
        raise UserError(f"Нет профиля «{pid}» — сохраните настройки и попробуйте снова.")
    return p


def _resolve_target(cfg, target: str) -> str:
    """llm → профиль основной облачной модели; role:<шаг> → профиль шага (совместимость с v2.4)."""
    from .profiles import target as step_target
    if target == "llm":
        pid = cfg["llm"].get("cloud_profile") or next((p["id"] for p in cfg["llm"].get("profiles") or []
                                                       if p.get("kind") == "cloud"), None)
        if not pid:
            raise UserError("Нет облачного профиля — создайте его в настройках (Модели → Облачная модель).")
        return f"profile:{pid}"
    if target.startswith("role:"):
        name = target[5:]
        if name not in PROMPT_NAMES:
            raise UserError(f"Неизвестный шаг «{name}».")
        kind, p = step_target(cfg, name)
        if p is None:
            raise UserError(f"У шага «{name}» нет своего профиля.")
        return f"profile:{p['id']}"
    return target


def key_file(cfg, target: str) -> Path:
    """Файл ключа: profile:<id> | embeddings (а также llm и role:<шаг> — как раньше).
    Относительные пути — рядом с settings.yaml."""
    from .profiles import key_file_name
    target = _resolve_target(cfg, target)
    if target.startswith("profile:"):
        pid = target[8:]
        rel = _profile(cfg, pid).get("api_key_file") or key_file_name(pid)
    elif target == "embeddings":
        rel = cfg["embeddings"].get("api_key_file") or "embeddings_api_key.txt"
    else:
        raise UserError(f"Неизвестный ключ «{target}»: profile:<id> или embeddings.")
    p = Path(rel)
    return p if p.is_absolute() else cfg.program_dir / p


def save_key(cfg, target: str, key: str) -> str:
    key = (key or "").strip()
    target = _resolve_target(cfg, target)
    path = key_file(cfg, target)
    if target.startswith("profile:"):
        pid = target[8:]
        p = _profile(cfg, pid)
        if key and not p.get("api_key_file"):
            apply_patch(cfg, {"llm": {"profiles": {pid: {"api_key_file": path.name}}}})
        elif not key and p.get("kind") == "local" and p.get("api_key_file") == path.name:
            apply_patch(cfg, {"llm": {"profiles": {pid: {"api_key_file": ""}}}})
    if not key:
        if path.exists():
            path.unlink()
        return f"Ключ удалён ({path.name})."
    U.atomic_write_text(path, key + "\n")
    return f"Ключ сохранён в {path.name} рядом с программой."


def _has_key(cfg, rel: str) -> bool:
    return bool(rel) and bool(cfg.secret(rel))


def key_status(cfg) -> dict:
    out = {"embeddings": _has_key(cfg, cfg["embeddings"].get("api_key_file") or "embeddings_api_key.txt"),
           "profiles": {}}
    for p in cfg["llm"].get("profiles") or []:
        if isinstance(p, dict) and p.get("id"):
            out["profiles"][p["id"]] = _has_key(cfg, p.get("api_key_file") or "")
    try:
        out["llm"] = out["profiles"].get(_resolve_target(cfg, "llm")[8:], False)
    except UserError:
        out["llm"] = False
    return out

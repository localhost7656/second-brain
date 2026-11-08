"""Settings scheme (section 17): plugin description, check-up, record settings.yaml explainable,
key-file. Thresholds — common (settings.yaml) and theirs at the container. (field thresholds his YAML, section 17.4)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import yaml

from . import util as U
from .util import UserError

PROMPT_NAMES = ["Structure", "Classification", "Questions", "Compaction", "Extraction", "Pool analysis", "Value",
                "Version comparison", "New composite type", "Synthesis", "Thresholds"]
PROMPT_HELP = {
    "Structure": "draft structure at first load",
    "Classification": "where to put the record; frequent",
    "Questions": "clarifying questions about incomplete records",
    "Compaction": "compression",
    "Extraction": "record-making",
    "Pool analysis": "doubles, contradiction, component",
    "Value": "value-added",
    "Version comparison": "What is missing in a new version of the database or document",
    "New composite type": "team «Patterns.»",
    "Synthesis": "Phase papers 2 — The quality of the text is important.",
    "Thresholds": "container-threshold",
}
PROMPT_SLUG = {"Structure": "structure", "Classification": "classification", "Questions": "questions",
               "Compaction": "compaction", "Extraction": "extraction", "Pool analysis": "pool", "Value": "value",
               "Version comparison": "versions", "New composite type": "patterns", "Synthesis": "synthesis",
               "Thresholds": "thresholds"}
# stepping-step, which have a long material divided into parts by «limit» (step-line — small-window model)
SPLIT_PROMPTS = ("Structure", "Classification", "Pool analysis")

# ---------- threshold ----------
_P = "Scale. 0–100."
_S = "Similarity 0 before 1."
THRESHOLDS: dict[str, dict] = {
    "classification": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": True,
                       "label": "No question layout",
                       "help": f"{_P} With this confidence of the model, the record is decomposed into a container itself., below — leaves "
                               "_review questionable. Higher. — less layout errors, more questions."},
    "hint_shift": {"kind": "int", "min": 0, "max": 50, "step": 1, "per_container": True,
                   "label": "Weight of your clue",
                   "help": "How many points of confidence is added to the option from the hint hint:. More. — clue "
                           "outweighs the models opinion."},
    "high": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": True,
             "label": "High confidence.",
             "help": f"{_P} With this confidence, the program itself creates containers and under the-container, record "
                     "multi-container, germ-produce. Below. — ask."},
    "mode_guess": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": False,
                   "label": "A hunch about file mode",
                   "help": f"{_P} With this confidence, the model decides for itself., Whether it is a mass download or a single recording. "
                           "Refers to incoming files prior to layout, Therefore, only the general."},
    "compaction": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": True,
                   "label": "Compaction",
                   "help": f"{_P} With this noise, the recording is first compressed by the model. (source-code remains). "
                           "Below. — more records (more, purer)."},
    "value_min": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": True,
                  "label": "Minimum value",
                  "help": f"{_P} Aspects more valuable than this go into the synthesis base, The rest are left in the pool.. "
                          "Higher. — leaner, but it may lose details.."},
    "value_primary": {"kind": "int", "min": 0, "max": 100, "step": 1, "per_container": True,
                      "label": "Primary",
                      "help": f"{_P} With this value, the aspect is considered paramount. — The documents are based on it primarily.."},
    "duplicate_similarity": {"kind": "float", "min": 0.5, "max": 0.99, "step": 0.01, "per_container": True,
                             "label": "Similarity to looking for duplicates",
                             "help": f"{_S} With such similarity, the pair of aspects are shown as possible duplicates.. "
                                     "Below. — Model sees more pairs of models (less-than-a-half-double, but more expensive and more false)."},
    "neighbor_similarity": {"kind": "float", "min": 0.5, "max": 0.99, "step": 0.01, "per_container": True,
                            "label": "Neighborhood similarity",
                            "help": f"{_S} With such similarity of recordings from different containers, the program asks, anyway "
                                    "laid out. Below. — more questions."},
    "pattern_similarity": {"kind": "float", "min": 0.5, "max": 0.99, "step": 0.01, "per_container": True,
                           "label": "Pattern-likeness",
                           "help": f"{_S} How close the aspects should be, team «Patterns.» I thought they were a bunch.."},
}
SEED_DORMANCY = {"kind": "int", "min": 7, "max": 3650, "step": 1, "per_container": True,
                 "label": "Days before the question of sprouting",
                 "help": "The sprout without new thoughts is longer than that — question «still relevant?». It only works on sprouts.."}
CONTAINER_THRESHOLDS = {k: v for k, v in THRESHOLDS.items() if v["per_container"]}
CONTAINER_THRESHOLDS["seed_dormancy_days"] = SEED_DORMANCY
# russian, If the user writes the thresholds in YAML hand-held
ALIASES = {"layout": "classification", "classification": "classification", "clue": "hint_shift",
           "high-pitched": "high", "high-end": "high", "sealing": "compaction", "value": "value_min",
           "minimal_value": "value_min", "primary": "value_primary", "primacy": "value_primary",
           "doubles": "duplicate_similarity", "neighbourhood": "neighbor_similarity", "pattern": "pattern_similarity",
           "slumber": "seed_dormancy_days", "days_sprout": "seed_dormancy_days"}


def parse_number(v, spec: dict):
    """Number of YAML: admittance «0,85» and «80%»; scale-wise 0–1 «86%» — it 0,86. None — if not number or out of range."""
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
    """Your container sills out of the field thresholds his YAML. Unknown values are skipped with warning."""
    raw = node.fm.get("thresholds")
    if raw in (None, "", {}):
        return {}
    if not isinstance(raw, dict):
        if warn:
            warn(f"In container [[{node.title}]], thresholds must be a mapping of threshold names to values; overrides were ignored.")
        return {}
    out = {}
    for k, v in raw.items():
        key = str(k).strip()
        key = ALIASES.get(key.lower().replace(" ", "_"), key)
        spec = CONTAINER_THRESHOLDS.get(key)
        if spec is None:
            if warn:
                hint = " (this threshold is global only; set it in settings.yaml)" if key in THRESHOLDS else ""
                warn(f"In container [[{node.title}]], unknown or unsupported threshold “{k}”{hint}; ignored.")
            continue
        if v in (None, ""):
            continue
        num = parse_number(v, spec)
        if num is None:
            if warn:
                warn(f"In container [[{node.title}]], threshold “{k}”: “{v}” must be a number from {spec['min']} to {spec['max']}; "
                     "the inherited value will be used.")
            continue
        out[key] = num
    return out


# ---------- plugin-setting ----------
def F(key, typ, label, help_="", **kw):
    d = {"key": key, "type": typ, "label": label, "help": help_}
    d.update(kw)
    return d


LLAMA_HINT = ("Your server. llama.cpp (or OpenAI-compatible): launch llama-server language-modeled and enter "
              "address, for example http://127.0.0.1:8080/v1 (no key).")
MODE_CHOICES = {"cloud": "Cloud model (API)", "local": "Local model (on this computer)",
                "webchat": "Manually via the web-chat"}
# profile field: kinds — What profiles does the field have? (cloudy, local)
PROFILE_FIELDS = [
    F("name", "text", "Profile name", "What is the profile called in the lists, into «Expenses» and in journal.", kinds=["cloud", "local"]),
    F("base_url", "text", "Address API", "OpenAI-compatible address. Z.ai: https://api.z.ai/api/paas/v4 "
      "(subscription GLM Coding Plan: https://api.z.ai/api/coding/paas/v4).", kinds=["cloud"], placeholder="https://api.z.ai/api/paas/v4"),
    F("base_url", "text", "Server address", LLAMA_HINT, kinds=["local"], placeholder="http://127.0.0.1:8080/v1"),
    F("model", "text", "Model", "Model name from the provider, Just like his documentation..", kinds=["cloud"], placeholder="glm-4.6"),
    F("model", "text", "Model", "For llama.cpp — name; server-side — like in their model list.", kinds=["local"], placeholder="local"),
    F("api_key_file", "key", "Key key API", "Stored in a file next to the program, non-storage.", kinds=["cloud"]),
    F("api_key_file", "key", "Key key", "Needed., Only if the server is running with a key (--api-key).", kinds=["local"]),
    F("temperature", "float", "Temperature.", "0–2. Below. — answers more stable.", min=0, max=2, step=0.05, slider=True,
      kinds=["cloud", "local"]),
    F("max_input_chars", "int", "Limit of request, sign", "More. — Materials are divided into parts automatically. "
      "300 000 sign ≈ 100 thousand. token. For a model with a small window — near 3 window-mark: "
      "upon -c 16384 bal llama-server — roughly 40 000.", min=8000, max=5000000, kinds=["cloud", "local"]),
    F("max_tokens", "int?", "Limit of response length (token)", "Empty. — provider-like. If the program says "
      "«answer cut short» — zoom in.", min=256, max=1000000, kinds=["cloud", "local"]),
    F("timeout_sec", "int", "Waiting for a response, seconds", "Your computer model may need more..",
      min=10, max=7200, kinds=["cloud", "local"]),
    F("json_mode", "bool", "Regime. JSON", "Turn it on., if the server can response_format: json_object — less format errors.",
      kinds=["cloud", "local"]),
    F("extra", "json", "Specific parameters of the request", "Added to the request as is. Example GLM: "
      "{\"thinking\": {\"type\": \"disabled\"}}", kinds=["cloud", "local"]),
    F("prices.input", "float?", "Entrance, $ post 1 million", "Request price — price-provider.", min=0, max=1000,
      kinds=["cloud"], group="prices"),
    F("prices.cached_input", "float?", "Cache entrance, $ post 1 million", "The repeated start of the request provider takes from the cache "
      "cheaper. Empty. — normal entrance.", min=0, max=1000, kinds=["cloud"], group="prices"),
    F("prices.output", "float?", "Exit, $ post 1 million", "The price of a response (model-based).", min=0,
      max=1000, kinds=["cloud"], group="prices"),
    F("budget_month", "float?", "Profile limit per month, $", "Empty. — limitless (general budget).",
      min=0, max=100000, kinds=["cloud"], group="prices"),
]

TABS = {"main": "Basic.", "models": "Models.", "thresholds": "Thresholds", "input": "Incoming", "docs": "Documents",
        "costs": "Expenses", "advanced": "Additionally."}
SCHEMA = [
    {"id": "updates", "tab": "main", "title": "Updates", "fields": [
        F("updates.check_on_start", "bool", "Check at launch Obsidian",
          "If theres a new version — The plugin will suggest installing it. (settings and keys are not touched)."),
    ]},
    {"id": "llm", "tab": "models", "title": "Language model", "fields": [
        F("llm", "llm", "Mode and profiles",
          "Cloudy — down API provider (Z.ai etc..); local — server llama.cpp; web-based-chat — request "
          "And the answers in the files in the folder. _web-chat. Profile — saved-set model: hold on "
          "switch off.", choices=MODE_CHOICES),
    ]},
    {"id": "roles", "tab": "models", "title": "Models for individual steps", "fields": [
        F("llm.roles", "roles", "Your step-models",
          "For example,, synthesis — more powerful, classification — fast-moving llama.cpp. "
          "«As a primary» — The step works on the model from the section above.", prompts=PROMPT_NAMES, prompt_help=PROMPT_HELP,
          split_prompts=list(SPLIT_PROMPTS)),
    ]},
    {"id": "embeddings", "tab": "models", "title": "embeddingi (search)", "fields": [
        F("embeddings.mode", "choice", "Where to count", "", choices={"local": "On this computer. (llama.cpp)",
                                                                  "cloud": "Cloud service (needle)"}),
        F("embeddings.base_url", "text", "Server address", "Button «Run the model…» higher up "
          "(http://127.0.0.1:8081/v1). Your server. llama.cpp (llama-server --embedding --pooling last -c 4096 -ub 4096) — write in his address.",
          placeholder="http://127.0.0.1:8081/v1", show_if={"embeddings.mode": ["local"]}),
        F("embeddings.base_url", "text", "Address API", "OpenAI-compatible e-mail address.",
          placeholder="https://api.openai.com/v1", show_if={"embeddings.mode": ["cloud"]}),
        F("embeddings.model", "text", "Model", "Name of model on server; For its model, the program inscribes it itself.. "
          "When changing, all vectors will be counted themselves..", show_if={"embeddings.mode": ["local"]}),
        F("embeddings.model", "text", "Model", "Model name from the provider. When changing, all vectors will be counted themselves..",
          show_if={"embeddings.mode": ["cloud"]}),
        F("embeddings.api_key_file", "key", "Key key", "Stored in a file next to the program.", target="embeddings",
          show_if={"embeddings.mode": ["cloud"]}),
        F("embeddings.price_input", "float?", "Price., $ post 1 million", "For the costing of the.", min=0, max=1000,
          show_if={"embeddings.mode": ["cloud"]}),
        F("embeddings.batch", "int", "Texts in one request", "", min=1, max=256),
        F("embeddings.max_chars", "int", "Limit of text, sign", "Longer. — cut off (The record doesnt change.).",
          min=500, max=100000),
        F("embeddings.timeout_sec", "int", "Waiting for a response, seconds", "", min=10, max=7200),
    ]},
    {"id": "thresholds", "tab": "thresholds", "title": "Common thresholds",
     "help": "Theyre everywhere., where the container has no (their own — tab «Container» panel).",
     "fields": [F(f"thresholds.{k}", v["kind"], v["label"], v["help"], min=v["min"], max=v["max"], step=v["step"], slider=True)
                for k, v in THRESHOLDS.items()]
     + [F("seed_dormancy_days", "int", SEED_DORMANCY["label"], SEED_DORMANCY["help"], min=7, max=3650, step=1)]},
    {"id": "sources", "tab": "input", "title": "Sources", "fields": [
        F("sources", "sources", "Sources of records",
          "Subfolders _staging (for example _staging/Chat with AI/). Colour — windowmark; shift — how much "
          "Reduce the threshold of sealing for this source."),
    ]},
    {"id": "markers", "tab": "input", "title": "Marking up dialogues", "fields": [
        F("dialogue_markers.user", "lines", "Your lines start with", "Through comma.."),
        F("dialogue_markers.ai", "lines", "AI replicas start with", "Through comma.."),
    ]},
    {"id": "input", "tab": "input", "title": "Long files.", "fields": [
        F("input.split_by_dates", "bool", "Divide the diary by date",
          "File., where records begin with a date line (12.03.2021, 2021-03-12, «12 March 2021»), sort out "
          "record — each with its own date. The original file remains intact in _sources."),
    ]},
    {"id": "style", "tab": "docs", "title": "Document style", "fields": [
        F("style.global", "textarea", "General style", "For the container — tab «Container», document — field "
          "style_override his YAML."),
    ]},
    {"id": "budget", "tab": "costs", "title": "Budget budget", "fields": [
        F("budget.monthly_usd", "float?", "Monthly budget, $", "All the cloud models together.. Primary 80% — warning, "
          "upon 100% — The program will stop before the next call and ask, continue. Empty. — budgeted. "
          "Model prices are set in profiles («Models.») or «Expenses» panel.", min=0, max=100000),
        F("budget.warn_pct", "int", "Warn with, % budget", "", min=10, max=99, step=1, slider=True),
    ]},
    {"id": "estimate", "tab": "costs", "title": "Evaluation before a big launch", "fields": [
        F("estimate.enabled", "bool", "Showing an evaluation",
          "Before starting the program calculates the number of calls, time and cost, if the launch is large, "
          "ask for. Revalidation always asks."),
        F("estimate.calls", "int", "If more appeals are made", "", min=1, max=100000),
        F("estimate.usd", "float", "Or the cost is more., $", "", min=0, max=10000),
        F("estimate.minutes", "int", "Or longer., minute", "", min=1, max=10000),
    ]},
    {"id": "limits", "tab": "advanced", "title": "Limits", "fields": [
        F("limits.max_containers_in_prompt", "int", "Containers in the classification request", "", min=10, max=2000),
        F("limits.max_items_per_value_call", "int", "Elements for a single value assessment", "", min=20, max=5000),
        F("limits.max_questions_per_entity", "int", "Clarifying questions on the record", "", min=0, max=10),
        F("llm.max_format_retries", "int", "Repeats in case of format error", "How many times do I ask the model to correct the format of the answer?.",
          min=0, max=5),
        F("llm.webchat.max_input_chars", "int", "Web query limit-chat, sign", "For manual mode: longer — "
          "The material is divided into several requests.", min=8000, max=5000000),
    ]},
]


# Reviewed English labels and explanations for the settings interface.
PROMPT_HELP.update({
    "Structure": "structure draft for the first import",
    "Classification": "choose where an entry belongs; the most frequent call",
    "Questions": "clarifying questions about incomplete entries",
    "Compaction": "compress noisy entries and conversations",
    "Extraction": "extract aspects from an entry",
    "Pool analysis": "duplicates, contradictions, and composite aspects",
    "Value": "assess the value of aspects",
    "Version comparison": "identify what disappeared from a new version of a base or document",
    "New composite type": "the Patterns command",
    "Synthesis": "Phase 2 documents; writing quality matters most here",
    "Thresholds": "advice on container thresholds",
})
_threshold_text = {
    "classification": ("Automatic placement", "Scale 0–100. At or above this confidence, the model places an entry automatically; below it, the entry goes to _review with a question. A higher threshold means fewer placement errors but more questions."),
    "hint_shift": ("Weight of your hint", "Confidence points added to the option specified by hint:. A larger value makes the hint more likely to outweigh the model's choice."),
    "high": ("High confidence", "Scale 0–100. At or above this confidence, the program creates containers and subcontainers, shares entries among containers, and promotes seeds to projects automatically. Below it, the program asks."),
    "mode_guess": ("File mode detection", "Scale 0–100. At or above this confidence, the model decides whether a file is a bulk import or a single entry. This applies before placement and is only a global setting."),
    "compaction": ("Compaction", "Scale 0–100. At or above this noise level, the model first compresses an entry; the original text is retained. A lower threshold compresses more entries, increasing cost but producing cleaner aspects."),
    "value_min": ("Minimum value", "Scale 0–100. Aspects above this value enter the synthesis base; others remain only in the pool. A higher threshold makes the base more compact but may lose details."),
    "value_primary": ("Primary importance", "Scale 0–100. At or above this value, an aspect is considered primary and documents rely on it first."),
    "duplicate_similarity": ("Similarity for duplicate detection", "Similarity from 0 to 1. Aspect pairs at or above this threshold are shown to the model as possible duplicates. Lower values find more pairs, but cost more and produce more false positives."),
    "neighbor_similarity": ("Neighbor similarity", "Similarity from 0 to 1. When entries in different containers are at least this similar, the program asks whether they are placed correctly. Lower values produce more questions."),
    "pattern_similarity": ("Similarity for patterns", "Similarity from 0 to 1. How close aspects must be for the Patterns command to consider them related."),
    "seed_dormancy_days": ("Days before asking about a seed", "If a seed has no new thoughts for longer than this, the program asks whether it is still relevant. Applies only to seeds."),
}
for _k, (_label, _help) in _threshold_text.items():
    _spec = CONTAINER_THRESHOLDS.get(_k) or THRESHOLDS.get(_k)
    if _spec:
        _spec.update(label=_label, help=_help)
TABS.update({"main": "General", "models": "Models", "thresholds": "Thresholds", "input": "Incoming", "docs": "Documents", "costs": "Expenses", "advanced": "Advanced"})
MODE_CHOICES.update({"cloud": "Cloud model (API)", "local": "Local model (this computer)", "webchat": "Manual web chat"})
_profile_text = {
    "name": ("Profile name", "How this profile appears in lists, Expenses, and the log."),
    "model": ("Model", None),
    "api_key_file": ("API key", None),
    "temperature": ("Temperature", "0–2. Lower values produce more consistent responses."),
    "max_input_chars": ("Request limit, characters", "Longer material is split automatically. 300,000 characters is approximately 100,000 tokens. For a smaller context window, allow about three characters per token: approximately 40,000 for llama-server -c 16384."),
    "max_tokens": ("Response length limit, tokens", "Leave empty to use the provider's default. Increase this if the program reports a truncated response."),
    "timeout_sec": ("Response timeout, seconds", "A local model may need more time."),
    "json_mode": ("JSON mode", "Enable if the server supports response_format: json_object to reduce formatting errors."),
    "extra": ("Extra request parameters", 'Added to the request as entered. GLM example: {"thinking": {"type": "disabled"}}'),
    "prices.input": ("Input, $ per million tokens", "Request price from the provider's price list."),
    "prices.cached_input": ("Cached input, $ per million tokens", "Providers may charge less for a cached request prefix. Leave empty to use the regular input price."),
    "prices.output": ("Output, $ per million tokens", "Response price, including model reasoning."),
    "budget_month": ("Monthly profile limit, $", "Leave empty for no profile-specific limit; the overall budget still applies."),
}
for _f in PROFILE_FIELDS:
    _k = _f["key"]
    if _k in _profile_text:
        _f["label"], _help = _profile_text[_k]
        if _help is not None:
            _f["help"] = _help
    if _k == "base_url":
        if "cloud" in _f["kinds"]:
            _f.update(label="API address", help="OpenAI-compatible API address. Z.ai: https://api.z.ai/api/paas/v4. GLM Coding Plan: https://api.z.ai/api/coding/paas/v4.")
        else:
            _f.update(label="Server address", help="Start your llama.cpp or other OpenAI-compatible language-model server and enter its address, for example http://127.0.0.1:8080/v1. A key is not required unless the server requires one.")
    elif _k == "model":
        _f["help"] = "Use the provider's exact model name." if "cloud" in _f["kinds"] else "For llama.cpp, use any name; for other servers, use a name from their model list."
    elif _k == "api_key_file":
        _f["help"] = "Stored in a file alongside the program, not in the vault." if "cloud" in _f["kinds"] else "Needed only if the server was started with a key (--api-key)."
_section_titles = {"updates": "Updates", "llm": "Language model", "roles": "Models for individual steps", "embeddings": "Embeddings (similarity search)", "thresholds": "Global thresholds", "sources": "Sources", "markers": "Dialogue markers", "input": "Long files", "style": "Document style", "budget": "Budget", "estimate": "Estimate before a large run", "limits": "Limits"}
_field_text = {
    "updates.check_on_start": ("Check when Obsidian starts", "If a new version is available, the plugin will offer to install it without changing settings or keys."),
    "llm": ("Mode and profiles", "Use a cloud provider API, a local llama.cpp server, or manual requests and responses in the vault's _web-chat folder. A profile stores a model's settings; you can keep several and switch between them."),
    "llm.roles": ("Models by step", "For example, use a stronger model for synthesis and a faster or local model for classification. Same as main model uses the model selected above."),
    "embeddings.mode": ("Where to run", ""),
    "embeddings.base_url": (None, None),
    "embeddings.model": ("Model", "Model name on the server or at the provider. When the model changes, all vectors will be recalculated automatically."),
    "embeddings.api_key_file": ("API key", "Stored in a file alongside the program."),
    "embeddings.price_input": ("Price, $ per million tokens", "Used to calculate costs."),
    "embeddings.batch": ("Texts per request", ""),
    "embeddings.max_chars": ("Text limit, characters", "Longer text is truncated for search; the entry itself is not changed."),
    "embeddings.timeout_sec": ("Response timeout, seconds", ""),
    "sources": ("Entry sources", "Subfolders of _staging, such as _staging/AI chat/. Color identifies the source in views; offset lowers the compaction threshold for this source by that many points."),
    "dialogue_markers.user": ("Your messages begin with", "Comma-separated."),
    "dialogue_markers.ai": ("AI messages begin with", "Comma-separated."),
    "input.split_by_dates": ("Split diary by date", "A file whose entries start with dates (12.03.2021, 2021-03-12, or 12 March 2021) is processed as separate dated entries. The original file remains intact in _sources."),
    "style.global": ("Global style", "Set a container's style on its Container tab, or a document's style in the style_override field of its YAML."),
    "budget.monthly_usd": ("Monthly budget, $", "Applies to all cloud models combined. The program warns at 80% and stops before the next request at 100%, asking whether to continue. Leave empty for no budget. Set model prices in profiles or on the panel's Expenses tab."),
    "budget.warn_pct": ("Warn at % of budget", ""),
    "estimate.enabled": ("Show estimate", "Before a run, estimate the number of calls, time, and cost. Large runs require confirmation; revalidation always requires confirmation."),
    "estimate.calls": ("If calls exceed", ""),
    "estimate.usd": ("Or cost exceeds, $", ""),
    "estimate.minutes": ("Or duration exceeds, minutes", ""),
    "limits.max_containers_in_prompt": ("Containers per classification request", ""),
    "limits.max_items_per_value_call": ("Items per value assessment", ""),
    "limits.max_questions_per_entity": ("Clarifying questions per entry", ""),
    "llm.max_format_retries": ("Retries after a format error", "How many times to ask the model to correct its response format."),
    "llm.webchat.max_input_chars": ("Web chat request limit, characters", "In manual mode, longer material is split into multiple requests."),
}
for _section in SCHEMA:
    _section["title"] = _section_titles[_section["id"]]
    if _section["id"] == "thresholds":
        _section["help"] = "Applies wherever a container has no custom thresholds. Set custom thresholds on the panel's Container tab."
    for _f in _section["fields"]:
        _k = _f["key"]
        if _k.startswith("thresholds.") or _k == "seed_dormancy_days":
            _name = _k.removeprefix("thresholds.")
            if _name in _threshold_text:
                _f["label"], _f["help"] = _threshold_text[_name]
        elif _k in _field_text:
            _label, _help = _field_text[_k]
            if _label is not None: _f["label"] = _label
            if _help is not None: _f["help"] = _help
        if _k == "embeddings.mode":
            _f["choices"] = {"local": "On this computer (llama.cpp)", "cloud": "Cloud service (API key required)"}
        elif _k == "embeddings.base_url":
            if "local" in _f.get("show_if", {}).get("embeddings.mode", []):
                _f.update(label="Server address", help="Start model… fills this in automatically (http://127.0.0.1:8081/v1). To use your own llama.cpp server, enter its address; start it with llama-server --embedding --pooling last -c 4096 -ub 4096.")
            else:
                _f.update(label="API address", help="OpenAI-compatible embedding service address.")
del _k, _label, _help, _spec, _f, _section


def input_limit(cfg, prompt: str) -> int:
    """Step request limit, sign: profile, step-response (or-chat)."""
    from .profiles import input_limit as _il
    return _il(cfg, prompt)


def get_path(d: dict, key: str):
    cur = d
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


# ---------- check-up ----------
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate(d: dict) -> list[str]:
    """Verification of types and ranges. Unfilled (address, model, key) not a mistake in maintaining — Itll be a launch.."""
    from .profiles import ALL_PROFILE_KEYS, KINDS, MODES, PRICE_KEYS, PROFILE_ID, PROFILE_KEYS
    errs = []

    def num(key, lo, hi, kind="int", optional=False, v=None, label=None):
        v = get_path(d, key) if v is None and label is None else v
        if v is None and optional:
            return
        ok = _is_num(v) and (kind == "float" or float(v).is_integer())
        if not ok or not lo <= v <= hi:
            errs.append(f"{label or key}: expected a {'whole ' if kind == 'int' else ''}number from {lo} to {hi} (now: {v!r})")

    llm = d.get("llm") or {}
    if llm.get("mode") not in MODES:
        errs.append(f"llm.mode: cloud, local or webchat (now: {llm.get('mode')!r})")
    profiles = llm.get("profiles")
    byid: dict = {}
    if not isinstance(profiles, list):
        errs.append("llm.profiles: expected a list of profiles.")
        profiles = []
    names = set()
    for i, p in enumerate(profiles, 1):
        if not isinstance(p, dict):
            errs.append(f"llm.profiles[{i}]: profile {{id: …, name: …}}")
            continue
        pid = p.get("id")
        where = f"profile «{p.get('name') or pid or i}»"
        if not isinstance(pid, str) or not PROFILE_ID.match(pid):
            errs.append(f"{where}: id must contain valid Latin characters (now: {pid!r})")
            continue
        if pid in byid:
            errs.append(f"{where}: duplicate id “{pid}”")
            continue
        byid[pid] = p
        kind = p.get("kind")
        if kind not in KINDS:
            errs.append(f"{where}: kind — cloud or local (now: {kind!r})")
            continue
        name = str(p.get("name") or "").strip()
        if not name:
            errs.append(f"profile {pid}: name")
        elif name.lower() in names:
            errs.append(f"{where}: This name already exists in another profile.")
        names.add(name.lower())
        for k in p:
            if k not in PROFILE_KEYS[kind]:
                hint = " (Prices are available only for cloud profiles.)" if k in ("prices", "budget_month") else ""
                errs.append(f"{where}: unknown field “{k}”{hint}" if k not in ALL_PROFILE_KEYS or hint else
                            f"{where}: field “{k}” is not valid for this kind of profile")
        for k in ("base_url", "model", "api_key_file", "name"):
            if p.get(k) is not None and not isinstance(p.get(k), str):
                errs.append(f"{where}: {k} must be text")
        num("", 0, 2, "float", v=p.get("temperature"), label=f"{where}: temperature (temperature)")
        num("", 10, 7200, v=p.get("timeout_sec"), label=f"{where}: wait (timeout_sec)")
        if p.get("max_tokens") is not None:
            num("", 256, 1000000, v=p.get("max_tokens"), label=f"{where}: limit (max_tokens)")
        num("", 8000, 5000000, v=p.get("max_input_chars"), label=f"{where}: limit (max_input_chars)")
        if not isinstance(p.get("json_mode"), bool):
            errs.append(f"{where}: json_mode — true or false")
        if not isinstance(p.get("extra"), dict):
            errs.append(f"{where}: extra must be an object, e.g. {{\"parameter\": value}}")
        if kind == "cloud":
            pr = p.get("prices")
            if not isinstance(pr, dict):
                errs.append(f"{where}: price — need fields input, cached_input, output")
            else:
                for k, v in pr.items():
                    if k not in PRICE_KEYS:
                        errs.append(f"{where}: unknown price field “{k}” (available: {', '.join(PRICE_KEYS)})")
                    elif v is not None:
                        num("", 0, 1000, "float", v=v, label=f"{where}: price {k}")
            if p.get("budget_month") is not None:
                num("", 0, 100000, "float", v=p.get("budget_month"), label=f"{where}: month-limit (budget_month)")
    for key, kind in (("cloud_profile", "cloud"), ("local_profile", "local")):
        v = llm.get(key)
        if v in (None, ""):
            continue
        if v not in byid:
            errs.append(f"llm.{key}: no profile «{v}»")
        elif byid[v].get("kind") != kind:
            errs.append(f"llm.{key}: profile «{byid[v].get('name')}» not {'cloud' if kind == 'cloud' else 'local'}")
    wc = llm.get("webchat")
    if not isinstance(wc, dict):
        errs.append("llm.webchat: need a section max_input_chars")
    else:
        num("llm.webchat.max_input_chars", 8000, 5000000)
    num("llm.max_format_retries", 0, 5)
    roles = llm.get("roles") or {}
    if not isinstance(roles, dict):
        errs.append("llm.roles: need a list «step: profile»")
        roles = {}
    for name, r in roles.items():
        if name not in PROMPT_NAMES:
            errs.append(f"llm.roles: unknown step “{name}” (available: {', '.join(PROMPT_NAMES)})")
        elif not isinstance(r, str) or (r != "webchat" and r not in byid):
            errs.append(f"llm.roles.{name}: need id profile ({', '.join(byid) or 'No profiles.'}) or webchat (now: {r!r})")
    emb = d.get("embeddings") or {}
    if emb.get("mode") not in ("local", "cloud", "fake"):
        errs.append(f"embeddings.mode: local or cloud (now: {emb.get('mode')!r})")
    for key in ("embeddings.base_url", "embeddings.model", "embeddings.api_key_file", "style.global"):
        v = get_path(d, key)
        if v is not None and not isinstance(v, str):
            errs.append(f"{key}: must be text")
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
            errs.append(f"{key}: true or false")
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
            errs.append(f"dialogue_markers.{who}: You need at least one non-empty marker.")
    src = d.get("sources")
    if not isinstance(src, list):
        errs.append("sources: need a list of sources")
    else:
        names = set()
        for i, s in enumerate(src, 1):
            if not isinstance(s, dict) or not str(s.get("name") or "").strip():
                errs.append(f"sources[{i}]: source needs a name")
                continue
            if str(s["name"]).lower() in names:
                errs.append(f"sources: duplicate source “{s['name']}”")
            names.add(str(s["name"]).lower())
            if s.get("color") and not _COLOR.match(str(s["color"])):
                errs.append(f"sources «{s['name']}»: colour #RRGGBB")
            cs = s.get("compaction_shift", 0)
            if not isinstance(cs, int) or isinstance(cs, bool) or not -100 <= cs <= 100:
                errs.append(f"sources «{s['name']}»: compaction_shift must be a whole number from -100 to 100")
    return errs


# ---------- record settings.yaml ----------
def _y(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and ("e" in repr(v) or "E" in repr(v)):
        return f"{v:.12f}".rstrip("0").rstrip(".")  # 1e-05 YAML Id read it like a text.
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
    "device": "cpu — processor; gpu — graphics card",
    "build": "llama.cpp GPU build: auto chooses CUDA for NVIDIA, otherwise Vulkan; or select cuda or vulkan",
    "gpu_layers": "GPU layers: auto fits as many as possible, all loads all 48 layers, or specify a number",
    "ctx": "context length in tokens; a larger context uses more memory (4096: about 8.4 GB; 8192: 9.6 GB)",
    "kv_cache": "KV cache quantization: f16 | q8_0 | q4_0; has little effect because this model does not keep a KV cache",
    "threads": "CPU threads; 0 lets llama.cpp choose",
    "port": "server address: http://127.0.0.1:<port>/v1",
    "sleep_min": "unload model after this many idle minutes; 0 disables unloading",
    "autostart": "automatically start the server when needed, without downloading",
    "models_dir": "model folder (6.9 GB); empty uses models in the program folder",
}


def _render_server(srv) -> list[str]:
    """embeddings.server — settings of the launch model (window «Run the model…» plug-in)."""
    from .llama import SERVER_DEFAULTS
    srv = srv if isinstance(srv, dict) else {}
    out = ["  server:              # local llama.cpp model: Settings → Second Brain → Models → Start model…"]
    for k in list(SERVER_DEFAULTS) + [k for k in srv if k not in SERVER_DEFAULTS]:
        if k in srv:
            out.append(_kv("    ", k, srv[k], SERVER_COMMENTS.get(k, "")))
    return out


def render(d: dict) -> str:
    """settings.yaml whole, explainable (The plugin and the program rewrite the file with this function)."""
    from .profiles import PROFILE_KEYS
    L = d["llm"]
    E = d["embeddings"]
    T = d["thresholds"]
    lim = d.get("limits") or {}
    B = d.get("budget") or {}
    ES = d.get("estimate") or {}
    UP = d.get("updates") or {}
    out = [
        "# Second Brain settings. You can also change these in Obsidian:",
        "# Settings → Second Brain. This file is in the program folder, not the vault.",
        "# Text after # is explanatory and is ignored by the program.",
        "",
        "# Obsidian vault folder, filled in by Install.bat. The plugin uses the open vault;",
        "# this line is needed only for command-line use. Forward slashes are supported.",
        f"vault: {_y(d.get('vault'))}",
        "",
        "llm:",
        _kv("  ", "mode", L.get("mode"), "cloud — provider API; local — local server (llama.cpp); "
                                         "webchat — manual web chat"),
        _kv("  ", "cloud_profile", L.get("cloud_profile") or "", "cloud profile ID from profiles"),
        _kv("  ", "local_profile", L.get("local_profile") or "", "local profile ID from profiles"),
        "  profiles:            # model profiles. Prices are dollars per million tokens; leave empty to omit cost calculation",
    ]
    comments = {"base_url": "OpenAI-compatible address", "model": "exact model name from the provider",
                "api_key_file": "key file in the program folder, outside the vault",
                "timeout_sec": "response timeout in seconds", "max_tokens": "response length limit; empty uses the provider default",
                "max_input_chars": "request limit in characters; longer material is split",
                "json_mode": "true — if the server can response_format: json_object",
                "extra": "extra request parameters, for example {\"thinking\": {\"type\": \"disabled\"}} for GLM",
                "prices": "input, cached input, output — dollars per million tokens", "budget_month": "monthly profile limit, dollars"}
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
                c += " — enter before the first run"
            out.append(_kv("    - " if first else "      ", k, p[k], c))
            first = False
    out.append(_kv("  ", "webchat", L.get("webchat") or {}, "manual web chat request limit, characters"))
    roles = L.get("roles") or {}
    if roles:
        out.append("  roles:               # profile for individual steps (profile ID or webchat); unspecified steps use the main model")
        for name in PROMPT_NAMES + sorted(set(roles) - set(PROMPT_NAMES)):
            if name in roles:
                out.append(f"    {_y(name)}: {_y(roles[name])}")
    else:
        out.append("  roles: {}            # profiles for individual steps, example: {\"Synthesis\": \"p2\", \"Questions\": \"webchat\"}")
    out.append(_kv("  ", "max_format_retries", L.get("max_format_retries"), "maximum retries when the response format is invalid"))
    if L.get("fake_module") and L.get("fake_module") != "tests/fake_llm.py":
        out.append(f"  fake_module: {_y(L.get('fake_module'))}")
    out += [
        "",
        "embeddings:",
        _kv("  ", "mode", E.get("mode"), "local — this computer (llama.cpp); cloud — cloud embeddings"),
        _kv("  ", "base_url", E.get("base_url"), "server address; the plugin Start model… button fills it in"),
        _kv("  ", "model", E.get("model"), "server model name; changing it recalculates all vectors"),
        _kv("  ", "api_key_file", E.get("api_key_file"), "required only when mode is cloud"),
        _kv("  ", "batch", E.get("batch"), "texts per request"),
        _kv("  ", "max_chars", E.get("max_chars"), "longer text is truncated for search; the entry remains unchanged"),
        _kv("  ", "timeout_sec", E.get("timeout_sec")),
        _kv("  ", "price_input", E.get("price_input"), "cloud embeddings: dollars per million tokens"),
    ]
    out += _render_server(E.get("server"))
    out += [
        "",
        "budget:                # budget for cloud models",
        _kv("  ", "monthly_usd", B.get("monthly_usd"), "monthly dollars across cloud profiles; empty means no budget"),
        _kv("  ", "warn_pct", B.get("warn_pct"), "warn at this percentage; at 100% ask whether to continue"),
        "",
        "estimate:              # estimate calls, time, and cost before a large run",
        _kv("  ", "enabled", ES.get("enabled")),
        _kv("  ", "calls", ES.get("calls"), "ask for confirmation if calls exceed this number"),
        _kv("  ", "usd", ES.get("usd"), "or estimated cost exceeds this amount in dollars"),
        _kv("  ", "minutes", ES.get("minutes"), "or estimated duration exceeds this number of minutes"),
        "",
        "input:",
        _kv("  ", "split_by_dates", (d.get("input") or {}).get("split_by_dates"),
            "split dated diary entries into separate records"),
        "",
        "updates:               # updates from GitHub; repository is set in brain/__init__.py, UPDATE_REPO",
        _kv("  ", "check_on_start", UP.get("check_on_start"), "check for updates when Obsidian starts"),
        "",
        "thresholds:            # global thresholds; container-specific thresholds are set in YAML or the Container tab",
    ]
    for k, spec in THRESHOLDS.items():
        first = spec["help"].split(". ")[1] if spec["help"].startswith(("Scale.", "Similarity")) else spec["help"].split(". ")[0]
        first = first.rstrip(".")
        out.append(f"  {k}: {_y(T.get(k))}   # {spec['label']}: {first[:1].lower() + first[1:]}")
    out += [
        "",
        f"seed_dormancy_days: {_y(d.get('seed_dormancy_days'))} # ask whether a seed is still relevant after this many days without new thoughts",
        "",
        "dialogue_markers:      # markers for dialogue in text files",
        f"  user: {_y((d.get('dialogue_markers') or {}).get('user'))}",
        f"  ai: {_y((d.get('dialogue_markers') or {}).get('ai'))}",
        "",
        "sources:               # sources are _staging subfolders (for example _staging/Chat with AI/); compaction_shift lowers the compaction threshold",
    ]
    for s in d.get("sources") or []:
        out.append(f"  - name: {_y(s.get('name'))}")
        out.append(f"    color: {_y(s.get('color') or '#94A3B8')}")
        out.append(f"    compaction_shift: {_y(int(s.get('compaction_shift') or 0))}")
    out += [
        "",
        "style:                 # Phase 2 document style; override using container style or document style_override in YAML",
        f"  global: {_y((d.get('style') or {}).get('global') or '')}",
        "",
        "limits:                # model request limits; usually no change is needed",
        f"  max_containers_in_prompt: {_y(lim.get('max_containers_in_prompt'))}   # containers in the classification request",
        f"  max_items_per_value_call: {_y(lim.get('max_items_per_value_call'))}   # items per value assessment",
        f"  max_questions_per_entity: {_y(lim.get('max_questions_per_entity'))}     # clarifying questions per entry",
    ]
    known = {"vault", "llm", "embeddings", "thresholds", "seed_dormancy_days", "dialogue_markers", "sources", "style", "limits",
             "budget", "estimate", "input", "updates"}
    rest = {k: v for k, v in d.items() if k not in known}
    if rest:
        out += ["", "# other settings", yaml.safe_dump(rest, allow_unicode=True, sort_keys=False).rstrip()]
    return "\n".join(out) + "\n"


REPLACE = {("llm", "roles"), ("sources",), ("dialogue_markers", "user"), ("dialogue_markers", "ai")}


def merge_profiles(profiles: list, patch: dict) -> list:
    """Profile correction id: {id: {field}} — change, {id: None} — remove, new id — add."""
    from .profiles import normalize_profile
    out = [copy.deepcopy(p) for p in profiles or []]
    for pid, ch in (patch or {}).items():
        idx = next((i for i, p in enumerate(out) if isinstance(p, dict) and p.get("id") == pid), None)
        if ch is None:
            if idx is not None:
                out.pop(idx)
            continue
        if not isinstance(ch, dict):
            raise UserError(f"Profile «{pid}»: Changes must be an object.")
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
    """After profile editing: selection, indicative of a deleted profile or profile of another type, —
    first-rate; stepping-step, remote-profile, — back to the main model."""
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
    """Change. settings.yaml: patch superimposed on current values, everything checked, file rewriting
    fully (former — into settings.yaml.bak)."""
    from .config import prepare
    data = _fix_refs(prepare(merge_patch(cfg.data, patch)))
    errs = validate(data)
    if errs:
        raise UserError("Settings not saved: " + "; ".join(errs))
    text = render(data)
    check = yaml.safe_load(text)
    if prepare(check) != data:  # The record should be read back in the same way.
        raise UserError("Settings not saved: The settings could not be saved without changes to their content. Please report this.")
    path = Path(cfg.path)
    if path.exists():
        U.atomic_write_text(path.with_name(path.name + ".bak"), path.read_text(encoding="utf-8-sig", errors="replace"))
    U.atomic_write_text(path, text)
    cfg.data = data
    return data


# ---------- keynote ----------
def _profile(cfg, pid: str) -> dict:
    from .profiles import profiles_by_id
    p = profiles_by_id(cfg).get(pid)
    if p is None:
        raise UserError(f"Profile “{pid}” was not found. Save the settings and try again.")
    return p


def _resolve_target(cfg, target: str) -> str:
    """llm → profile of the main cloud model; role:<step> → step-figure (compatibility v2.4)."""
    from .profiles import target as step_target
    if target == "llm":
        pid = cfg["llm"].get("cloud_profile") or next((p["id"] for p in cfg["llm"].get("profiles") or []
                                                       if p.get("kind") == "cloud"), None)
        if not pid:
            raise UserError("No cloud profile. Create one in Settings → Models → Cloud model.")
        return f"profile:{pid}"
    if target.startswith("role:"):
        name = target[5:]
        if name not in PROMPT_NAMES:
            raise UserError(f"Unknown step «{name}».")
        kind, p = step_target(cfg, name)
        if p is None:
            raise UserError(f"No profile is configured for step “{name}”.")
        return f"profile:{p['id']}"
    return target


def key_file(cfg, target: str) -> Path:
    """Key file: profile:<id> | embeddings (also llm and role:<step> — earlier).
    Relative paths — near settings.yaml."""
    from .profiles import key_file_name
    target = _resolve_target(cfg, target)
    if target.startswith("profile:"):
        pid = target[8:]
        rel = _profile(cfg, pid).get("api_key_file") or key_file_name(pid)
    elif target == "embeddings":
        rel = cfg["embeddings"].get("api_key_file") or "embeddings_api_key.txt"
    else:
        raise UserError(f"Unknown key «{target}»: profile:<id> or embeddings.")
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
        return f"Key removed. ({path.name})."
    U.atomic_write_text(path, key + "\n")
    return f"Key saved in {path.name} near-program."


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

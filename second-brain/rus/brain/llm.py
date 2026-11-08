"""Клиент языковой модели: API (OpenAI-совместимый), ручной режим через веб-чат, тестовая заглушка. Раздел 13."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import time

from . import interact
from . import prompts as P
from . import util as U
from .profiles import CONNECTION_KEYS, is_local_url, main_profile_id, mode_ru, profiles_by_id, target
from .schema import PROMPT_NAMES, SPLIT_PROMPTS
from .util import ManualPending, UserError


def extract_json(text: str):
    t = (text or "").strip()
    t = re.sub(r"^```[a-zA-Z]*\s*\n", "", t)
    t = re.sub(r"\n```\s*$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        pass
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b <= a:
        raise ValueError("в ответе нет JSON-объекта")
    chunk = t[a:b + 1]
    try:
        return json.loads(chunk)
    except ValueError:
        chunk2 = re.sub(r",\s*([}\]])", r"\1", chunk)  # висячие запятые
        return json.loads(chunk2)


# ответ сервера «запрос не помещается в окно модели» (llama.cpp, OpenAI-совместимые провайдеры)
_OVERFLOW = re.compile(r"context[ _](size|length|window)|exceeds? (the )?(available |maximum )?context|n_ctx|maximum context|"
                       r"too many tokens|prompt is too long|input is too long|exceeds max(imum)? length", re.I)


def _overflow_message(c: dict, code: int, text: str) -> str:
    step = c.get("_prompt") or "?"
    pname = (c.get("_profile") or {}).get("name") or c.get("model")
    if step in SPLIT_PROMPTS:
        fix = (f"Уменьшите «Предел запроса, знаков» в профиле «{pname}» (Настройки → Второй мозг → Модели): длинный материал "
               "программа поделит на части сама. ")
    else:
        fix = f"Для шага «{step}» выберите в «Моделях для отдельных шагов» профиль модели с окном побольше. "
    return (f"Запрос шага «{step}» не поместился в окно модели {c.get('model')} ({c.get('base_url')}, код {code}). " + fix
            + "Своему серверу llama.cpp можно дать окно больше ключом -c, например -c 32768 (нужно больше памяти). "
            f"Ответ сервера: {(text or '')[:300]}")


class LLM:
    def __init__(self, cfg, world, logs, meter=None):
        self.last_finish = None
        self.cfg = cfg
        self.w = world
        self.logs = logs
        self.meter = meter              # учёт расхода и бюджет (usage.Meter)
        c = cfg["llm"]
        self.mode = c["mode"]
        self.calls: dict[str, int] = {}
        self._fake = None
        self.stop_check = None  # проверка «Стоп» из плагина (файл .system/stop)
        if self.mode in ("cloud", "local"):
            p = profiles_by_id(cfg).get(main_profile_id(c))
            if p is None:
                raise UserError(f"Не выбран профиль {'облачной' if self.mode == 'cloud' else 'локальной'} модели: "
                                "Настройки → Второй мозг → Модели (или cloud_profile / local_profile в settings.yaml).")
            if not str(p.get("model") or "").strip():
                raise UserError(f"В профиле «{p.get('name')}» не указана модель: впишите её название (Настройки → Второй мозг → "
                                "Модели, или строка model профиля в settings.yaml) — как у провайдера, например модель GLM на Z.ai.")
        logs.model_name = "fake" if self.mode == "fake" else "?"

    def conf(self, prompt: str) -> dict:
        """Настройки модели для шага: профиль шага (llm.roles) или основной, либо веб-чат (раздел 13.3)."""
        llm = self.cfg["llm"]
        kind, p = target(self.cfg, prompt)
        c = {"max_format_retries": llm.get("max_format_retries", 2), "_prompt": prompt, "_profile": p}
        if (llm.get("roles") or {}).get(prompt):
            c["_step"] = prompt
        if kind == "webchat":
            c.update(mode="webchat", _ptype="webchat",
                     max_input_chars=int((llm.get("webchat") or {}).get("max_input_chars") or 300000))
            return c
        if kind == "missing":
            c.update(mode="missing", _ptype=None)
            return c
        for k in CONNECTION_KEYS:
            c[k] = copy.deepcopy((p or {}).get(k))
        c["mode"] = "fake" if kind == "fake" else "api"
        c["_ptype"] = (p or {}).get("kind") if kind != "fake" else ((p or {}).get("kind") or "fake")
        return c

    def models(self) -> list[tuple[dict, list[str]]]:
        """Разные модели (профили), которые используются шагами: (настройки, [шаги])."""
        groups: dict = {}
        for p in PROMPT_NAMES:
            c = self.conf(p)
            key = (c.get("mode"), (c.get("_profile") or {}).get("id"))
            groups.setdefault(key, (c, []))[1].append(p)
        return list(groups.values())

    def label(self, c: dict) -> str:
        """Как назвать модель шага в сообщениях: имя профиля и вид."""
        if c.get("mode") == "webchat":
            return "веб-чат"
        p = c.get("_profile") or {}
        return f"{p.get('name') or c.get('model')} ({mode_ru(p.get('kind') or c.get('_ptype') or '')})"

    # ---------- публичные вызовы ----------
    def json(self, prompt: str, variables: dict, validate=None, subject: str = "") -> dict:
        def check(raw):
            try:
                obj = extract_json(raw)
            except ValueError as e:
                return None, [f"ответ не разбирается как JSON: {e}"]
            if not isinstance(obj, dict):
                return None, ["ответ должен быть JSON-объектом { … }"]
            errs = validate(obj) if validate else []
            return obj, errs
        obj = self._run(prompt, variables, check, subject)
        self.logs.reasoning(prompt, subject, obj)
        return obj

    def text(self, prompt: str, variables: dict, validate=None, subject: str = "") -> str:
        def check(raw):
            t = (raw or "").strip()
            t = re.sub(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", r"\1", t, flags=re.S)
            if not t:
                return None, ["пустой ответ"]
            errs = validate(t) if validate else []
            return t, errs
        return self._run(prompt, variables, check, subject)

    # ---------- общий цикл ----------
    def _run(self, prompt: str, variables: dict, check, subject: str):
        text = P.render(self.cfg, prompt, variables)
        c = self.conf(prompt)
        mode = c.get("mode") or self.mode
        prof = c.get("_profile") or {}
        self.logs.model_name = "fake" if mode == "fake" else ("веб-чат" if mode == "webchat" else
                                                             f"{prof.get('name') or c.get('model')}")
        if self.stop_check:
            self.stop_check()
        self.calls[prompt] = self.calls.get(prompt, 0) + 1
        if mode == "webchat":
            return self._webchat(prompt, text, check, subject, variables)
        if mode == "missing":
            raise UserError(f"Для шага «{prompt}» не выбран профиль модели: Настройки → Второй мозг → Модели.")
        messages = [{"role": "user", "content": text}]
        retries = int(c.get("max_format_retries", 2))
        last_errs = []
        for attempt in range(retries + 1):
            raw, usage = self._timed(prompt, messages, variables, attempt, c)
            if self.last_finish == "length":
                if prompt == "Синтез" or attempt >= retries:
                    raise UserError(f"Ответ модели оборвался по лимиту длины (промпт «{prompt}», {subject}). "
                                    f"Увеличьте «Предел длины ответа» в профиле «{prof.get('name') or c.get('model')}» "
                                    "(Настройки → Второй мозг → Модели; в settings.yaml — max_tokens профиля) "
                                    "или очистите его, чтобы действовал предел провайдера.")
                errs = ["ответ оборвался по лимиту длины — пришли его заново короче: рассуждения в одну фразу, без повторов"]
            else:
                obj, errs = check(raw)
                if not errs:
                    return obj
            last_errs = errs
            messages = messages + [
                {"role": "assistant", "content": raw or ""},
                {"role": "user", "content": "Ответ не прошёл проверку программой:\n- " + "\n- ".join(errs)
                 + "\nПришли исправленный ответ целиком, в том же формате, без пояснений вокруг."},
            ]
        raise UserError(f"Модель {retries + 1} раза ответила в неверном формате (промпт «{prompt}», {subject}): "
                        + "; ".join(last_errs[:5]))

    def _timed(self, prompt: str, messages: list, variables: dict, attempt: int, c: dict, record_as: str | None = None):
        """Одно обращение: бюджет перед ним, «ждём ответа» для плагина, расход и время — после."""
        prof = c.get("_profile") or {}
        if self.meter and c.get("_ptype") == "cloud" and record_as is None:
            self.meter.check_budget(prof or None)
        interact.waiting(prompt, prof.get("name") or "", str(c.get("model") or ""))
        t0 = time.time()
        try:
            raw, usage = self._complete(prompt, messages, variables, attempt, c)
        finally:
            interact.waiting(None)
        sec = time.time() - t0
        chars_in = sum(len(m["content"]) for m in messages)
        if self.meter:
            model = "fake" if c.get("mode") == "fake" else str(c.get("model") or "")
            self.meter.record("llm", record_as or prompt, c.get("_ptype"), prof or None, model, usage, chars_in,
                              len(raw or ""), sec)
        else:
            self.logs.usage(prompt, usage, chars_in, len(raw or ""))
        return raw, usage

    def _complete(self, prompt: str, messages: list, variables: dict, attempt: int, c: dict | None = None):
        self.last_finish = None
        c = c or self.conf(prompt)
        if c.get("mode") == "fake" or self.mode == "fake":
            if self._fake is None:
                path = self.cfg.program_file(self.cfg["llm"]["fake_module"])
                spec = importlib.util.spec_from_file_location("fake_llm", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self._fake = mod
            return self._fake.respond(prompt, variables, messages, attempt), None
        if c.get("mode") != "api":
            raise UserError(f"Неизвестный режим модели: {c.get('mode')}")
        return self._api(messages, c)

    def _api(self, messages: list, c: dict):
        import requests
        kf = str(c.get("api_key_file") or "").strip()
        key = self.cfg.secret(kf) if kf else None
        local = is_local_url(c.get("base_url"))
        pname = (c.get("_profile") or {}).get("name") or c.get("model")
        if not key and not local:
            step = f", шаг «{c['_step']}»" if c.get("_step") else ""
            raise UserError(f"Нет ключа API для профиля «{pname}» ({c.get('base_url')}{step}): сохраните ключ в настройках "
                            "плагина — Модели → профиль" + (f" (или вставьте его в файл {kf} рядом с программой)." if kf else "."))
        if not str(c.get("model") or "").strip():
            raise UserError(f"В профиле «{pname}» не указана модель: впишите её название (Настройки → Второй мозг → Модели).")
        url = str(c["base_url"]).rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = {"model": c["model"], "messages": messages, "temperature": c.get("temperature", 0.2)}
        if c.get("json_mode"):
            payload["response_format"] = {"type": "json_object"}
        if c.get("max_tokens"):
            payload["max_tokens"] = int(c["max_tokens"])
        if isinstance(c.get("extra"), dict):
            payload.update(c["extra"])  # особые параметры провайдера, например thinking у GLM
        delays = [5, 20, 60, 120]
        for i in range(len(delays) + 1):
            if self.stop_check:
                self.stop_check()
            try:
                r = requests.post(url, json=payload, timeout=c.get("timeout_sec", 600), headers=headers)
            except (requests.ConnectionError, requests.Timeout) as e:
                if i < len(delays) and not (local and isinstance(e, requests.ConnectionError) and i >= 1):
                    print(f"  нет связи с моделью ({type(e).__name__}), повтор через {delays[i]} с…")
                    self._sleep(delays[i])
                    continue
                hint = (" Запущен ли ваш сервер (например, llama-server из llama.cpp) и верен ли адрес и порт?") if local else ""
                raise UserError(f"Не удалось связаться с моделью по адресу {url}: {type(e).__name__}.{hint}")
            if r.status_code in (401, 403):
                if not key:
                    raise UserError(f"Сервер {c.get('base_url')} требует ключ (код {r.status_code}) — сохраните его в настройках.")
                raise UserError(f"Провайдер не принял ключ API (код {r.status_code}). Проверьте ключ профиля «{pname}» "
                                f"в настройках (файл {kf} рядом с программой).")
            if r.status_code >= 400 and r.status_code != 429 and _OVERFLOW.search(r.text or ""):
                raise UserError(_overflow_message(c, r.status_code, r.text))
            if r.status_code == 429 or r.status_code >= 500:
                if i < len(delays):
                    print(f"  провайдер ответил {r.status_code}, повтор через {delays[i]} с…")
                    self._sleep(delays[i])
                    continue
            if r.status_code >= 400:
                raise UserError(f"Ошибка провайдера {r.status_code}: {r.text[:500]}")
            try:
                data = r.json()
            except ValueError:
                if i < len(delays):
                    print(f"  провайдер вернул не JSON, повтор через {delays[i]} с…")
                    self._sleep(delays[i])
                    continue
                raise UserError(f"Провайдер вернул не JSON: {r.text[:300]}")
            try:
                choice = data["choices"][0]
                content = choice["message"].get("content") or ""
            except (KeyError, IndexError, TypeError):
                raise UserError(f"Неожиданный ответ провайдера: {str(data)[:500]}")
            self.last_finish = choice.get("finish_reason")
            usage = dict(data.get("usage") or {}) if isinstance(data.get("usage"), dict) else {}
            if isinstance(data.get("timings"), dict):  # llama.cpp: токены и кэш — в timings
                usage["_timings"] = data["timings"]
            return content, usage or None
        raise UserError("Модель недоступна.")

    def _sleep(self, sec: float):
        """Пауза перед повтором, прерываемая кнопкой «Стоп»."""
        left = float(sec)
        while left > 0:
            if self.stop_check:
                self.stop_check()
            step = min(1.0, left)
            time.sleep(step)
            left -= step

    # ---------- ручной режим через веб-чат ----------
    def _webchat(self, prompt: str, text: str, check, subject: str, variables: dict | None = None):
        idx = U.read_json(self.w.p.webchat_index, None) or {"n": 0, "pending": {}}
        idx.setdefault("done", {})
        h = U.sha1(text)
        wc = self.w.p.webchat
        old = idx["done"].get(h)
        if old and (wc / "готово" / old).exists():
            obj, errs = check((wc / "готово" / old).read_text(encoding="utf-8-sig"))
            if not errs:
                return obj
        rec = idx["pending"].get(h)
        if rec:
            req, ans = wc / rec["req"], wc / rec["ans"]
            raw = ans.read_text(encoding="utf-8-sig") if ans.exists() else ""
            if raw.strip():
                obj, errs = check(raw)
                if not errs:
                    done = wc / "готово"
                    done.mkdir(exist_ok=True)
                    for f in (req, ans):
                        if f.exists():
                            f.replace(done / f.name)
                    del idx["pending"][h]
                    idx["done"][h] = rec["ans"]
                    U.write_json(self.w.p.webchat_index, idx)
                    if self.meter:
                        self.meter.record("llm", prompt, "webchat", None, "веб-чат", None, len(text), len(raw), None)
                    return obj
                note = ("> [!warning] Ответ не прошёл проверку программой\n> - " + "\n> - ".join(errs)
                        + "\n> Попросите модель исправить ответ (можно скопировать ей эти замечания) и замените текст в файле ответа.\n\n")
                body = req.read_text(encoding="utf-8")
                body = re.sub(r"^> \[!warning\].*?\n\n", "", body, flags=re.S)
                U.atomic_write_text(req, note + body)
                raise ManualPending(f"Ответ в «{rec['ans']}» не прошёл проверку — подробности в файле запроса.")
            raise ManualPending(f"Ждёт ответа: «{rec['req']}» → вставьте ответ модели в «{rec['ans']}».")
        idx["n"] += 1
        n = idx["n"]
        req_name = f"{n:03d} {prompt} — запрос.md"
        ans_name = f"{n:03d} {prompt} — ответ.md"
        head = (f"Ручной режим. Скопируйте в веб-чат модели весь текст ниже линии, а ответ модели целиком вставьте в файл «{ans_name}» "
                f"(он лежит рядом), сохраните и снова запустите программу.\n\nОбъект: {subject}\n\n"
                "---------- скопировать всё ниже ----------\n\n")
        U.atomic_write_text(wc / req_name, head + text)
        U.atomic_write_text(wc / ans_name, "")
        idx["pending"][h] = {"n": n, "prompt": prompt, "req": req_name, "ans": ans_name, "created": U.now_iso()}
        U.write_json(self.w.p.webchat_index, idx)
        if os.environ.get("BRAIN_TEST_WEBCHAT_VARS"):  # только для автотестов: чтобы заглушка могла «ответить из веб-чата»
            U.write_json(self.w.p.system / "webchat_vars" / f"{n:03d}.json", {"prompt": prompt, "variables": variables})
        raise ManualPending(f"Создан запрос «{req_name}». Перенесите его в веб-чат, ответ вставьте в «{ans_name}».")

    def ping(self, c: dict | None = None) -> str:
        """Проверка подключения: короткий запрос."""
        c = c or self.conf("ping")
        if c.get("mode") == "webchat":
            return "ручной режим через веб-чат — проверка не требуется"
        if c.get("mode") == "missing":
            raise UserError("не выбран профиль модели (Настройки → Второй мозг → Модели)")
        msgs = [{"role": "user", "content": 'Ответь строго JSON: {"ok": true}'}]
        t = time.time()
        raw, _ = self._timed("ping", msgs, {}, 0, c, record_as="Проверка связи")
        try:
            obj = extract_json(raw)
        except ValueError:
            obj = {}
        if obj.get("ok") is not True:
            raise UserError(f"Модель ответила неожиданно: {raw[:200]}")
        where = "" if self.mode == "fake" else f" ({c.get('base_url')})"
        return f"модель {c.get('model')}{where} отвечает, {time.time() - t:.1f} с"

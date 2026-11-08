"""Client of the language model: API (OpenAI-compatible), manually via the web-chat, test-stub. Section 13."""
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
        raise ValueError("no JSON object in the response")
    chunk = t[a:b + 1]
    try:
        return json.loads(chunk)
    except ValueError:
        chunk2 = re.sub(r",\s*([}\]])", r"\1", chunk)  # hanging comma
        return json.loads(chunk2)


# server-answer «The request does not fit in the model window.» (llama.cpp, OpenAI-compatible providers)
_OVERFLOW = re.compile(r"context[ _](size|length|window)|exceeds? (the )?(available |maximum )?context|n_ctx|maximum context|"
                       r"too many tokens|prompt is too long|input is too long|exceeds max(imum)? length", re.I)


def _overflow_message(c: dict, code: int, text: str) -> str:
    step = c.get("_prompt") or "?"
    pname = (c.get("_profile") or {}).get("name") or c.get("model")
    if step in SPLIT_PROMPTS:
        fix = (f"Reduce the request character limit in profile ‘{pname}’ (Settings → Second Brain → Models); "
               "the program will split long material automatically. ")
    else:
        fix = f"For ‘{step}’, choose a profile with a larger context window under Models for individual steps. "
    return (f"The ‘{step}’ request exceeded the context window of model {c.get('model')} "
            f"({c.get('base_url')}, code {code}). " + fix
            + "For your own llama.cpp server, increase the context using -c, for example -c 32768 "
              "(this requires more memory). "
            f"Server response: {(text or '')[:300]}")


class LLM:
    def __init__(self, cfg, world, logs, meter=None):
        self.last_finish = None
        self.cfg = cfg
        self.w = world
        self.logs = logs
        self.meter = meter              # expense-recording (usage.Meter)
        c = cfg["llm"]
        self.mode = c["mode"]
        self.calls: dict[str, int] = {}
        self._fake = None
        self.stop_check = None  # check-up «Stop.» plug-in (file .system/stop)
        if self.mode in ("cloud", "local"):
            p = profiles_by_id(cfg).get(main_profile_id(c))
            if p is None:
                raise UserError(f"No {'cloud' if self.mode == 'cloud' else 'local'} model profile selected. "
                                "Select one under Settings → Second Brain → Models (or set cloud_profile / local_profile in settings.yaml).")
            if not str(p.get("model") or "").strip():
                raise UserError(f"No model is specified in profile ‘{p.get('name')}’. Enter the exact provider model name under "
                                "Settings → Second Brain → Models or in the profile’s model field in settings.yaml.")
        logs.model_name = "fake" if self.mode == "fake" else "?"

    def conf(self, prompt: str) -> dict:
        """Model settings for step: step-figure (llm.roles) primary, web-based-chat (section 13.3)."""
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
        """Different models (profiles), step-driven: (setting, [stepping-step])."""
        groups: dict = {}
        for p in PROMPT_NAMES:
            c = self.conf(p)
            key = (c.get("mode"), (c.get("_profile") or {}).get("id"))
            groups.setdefault(key, (c, []))[1].append(p)
        return list(groups.values())

    def label(self, c: dict) -> str:
        """How to name a step model in messages: profilename."""
        if c.get("mode") == "webchat":
            return "web-based-chat"
        p = c.get("_profile") or {}
        return f"{p.get('name') or c.get('model')} ({mode_ru(p.get('kind') or c.get('_ptype') or '')})"

    # ---------- public challenge ----------
    def json(self, prompt: str, variables: dict, validate=None, subject: str = "") -> dict:
        def check(raw):
            try:
                obj = extract_json(raw)
            except ValueError as e:
                return None, [f"The response is not valid JSON: {e}"]
            if not isinstance(obj, dict):
                return None, ["The response must be a JSON object { … }"]
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
                return None, ["empty response"]
            errs = validate(t) if validate else []
            return t, errs
        return self._run(prompt, variables, check, subject)

    # ---------- loop-in ----------
    def _run(self, prompt: str, variables: dict, check, subject: str):
        text = P.render(self.cfg, prompt, variables)
        c = self.conf(prompt)
        mode = c.get("mode") or self.mode
        prof = c.get("_profile") or {}
        self.logs.model_name = "fake" if mode == "fake" else ("web-based-chat" if mode == "webchat" else
                                                             f"{prof.get('name') or c.get('model')}")
        if self.stop_check:
            self.stop_check()
        self.calls[prompt] = self.calls.get(prompt, 0) + 1
        if mode == "webchat":
            return self._webchat(prompt, text, check, subject, variables)
        if mode == "missing":
            raise UserError(f"No model profile selected for ‘{prompt}’. Open Settings → Second Brain → Models.")
        messages = [{"role": "user", "content": text}]
        retries = int(c.get("max_format_retries", 2))
        last_errs = []
        for attempt in range(retries + 1):
            raw, usage = self._timed(prompt, messages, variables, attempt, c)
            if self.last_finish == "length":
                if prompt == "Synthesis" or attempt >= retries:
                    raise UserError(f"The model response was truncated at the length limit (step ‘{prompt}’, {subject}). "
                                    f"Increase the response token limit in profile ‘{prof.get('name') or c.get('model')}’ "
                                    "under Settings → Second Brain → Models (max_tokens in settings.yaml), "
                                    "or clear the limit to use the provider default.")
                errs = ["The response was truncated. Return a shorter response without repetition."]
            else:
                obj, errs = check(raw)
                if not errs:
                    return obj
            last_errs = errs
            messages = messages + [
                {"role": "assistant", "content": raw or ""},
                {"role": "user", "content": "The response did not pass validation:\n- " + "\n- ".join(errs)
                 + "\nReturn the complete corrected response in the same format, with no extra commentary."},
            ]
        raise UserError(f"The model returned an invalid response {retries + 1} times (step ‘{prompt}’, {subject}): "
                        + "; ".join(last_errs[:5]))

    def _timed(self, prompt: str, messages: list, variables: dict, attempt: int, c: dict, record_as: str | None = None):
        """One appeal: budget before, «waiting for an answer» plug-in, expense — after."""
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
            raise UserError(f"Unknown model mode: {c.get('mode')}")
        return self._api(messages, c)

    def _api(self, messages: list, c: dict):
        import requests
        kf = str(c.get("api_key_file") or "").strip()
        key = self.cfg.secret(kf) if kf else None
        local = is_local_url(c.get("base_url"))
        pname = (c.get("_profile") or {}).get("name") or c.get("model")
        if not key and not local:
            step = f", step «{c['_step']}»" if c.get("_step") else ""
            raise UserError(f"No API key for profile ‘{pname}’ ({c.get('base_url')}{step}). Save it under "
                            "Settings → Second Brain → Models → profile" + (f" or place it in {kf} beside the program." if kf else "."))
        if not str(c.get("model") or "").strip():
            raise UserError(f"No model is specified in profile ‘{pname}’. Enter one under Settings → Second Brain → Models.")
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
            payload.update(c["extra"])  # Special parameters of the provider, for example thinking bal GLM
        delays = [5, 20, 60, 120]
        for i in range(len(delays) + 1):
            if self.stop_check:
                self.stop_check()
            try:
                r = requests.post(url, json=payload, timeout=c.get("timeout_sec", 600), headers=headers)
            except (requests.ConnectionError, requests.Timeout) as e:
                if i < len(delays) and not (local and isinstance(e, requests.ConnectionError) and i >= 1):
                    print(f"  No connection to the model ({type(e).__name__}), retrying in {delays[i]} s…")
                    self._sleep(delays[i])
                    continue
                hint = (" Is your server running? (for example, llama-server from llama.cpp) and whether the address and port are correct?") if local else ""
                raise UserError(f"I was unable to contact the model at the address {url}: {type(e).__name__}.{hint}")
            if r.status_code in (401, 403):
                if not key:
                    raise UserError(f"Server {c.get('base_url')} requires an API key (code {r.status_code}). Save it in settings.")
                raise UserError(f"The provider rejected the API key (code {r.status_code}). Check the key for profile ‘{pname}’ "
                                f"in settings or in {kf} beside the program.")
            if r.status_code >= 400 and r.status_code != 429 and _OVERFLOW.search(r.text or ""):
                raise UserError(_overflow_message(c, r.status_code, r.text))
            if r.status_code == 429 or r.status_code >= 500:
                if i < len(delays):
                    print(f"  provider responded {r.status_code}, retrying in {delays[i]} s…")
                    self._sleep(delays[i])
                    continue
            if r.status_code >= 400:
                raise UserError(f"Provider error {r.status_code}: {r.text[:500]}")
            try:
                data = r.json()
            except ValueError:
                if i < len(delays):
                    print(f"  provider has not returned JSON, retrying in {delays[i]} s…")
                    self._sleep(delays[i])
                    continue
                raise UserError(f"Provider didnt return JSON: {r.text[:300]}")
            try:
                choice = data["choices"][0]
                content = choice["message"].get("content") or ""
            except (KeyError, IndexError, TypeError):
                raise UserError(f"Unexpected response from the provider: {str(data)[:500]}")
            self.last_finish = choice.get("finish_reason")
            usage = dict(data.get("usage") or {}) if isinstance(data.get("usage"), dict) else {}
            if isinstance(data.get("timings"), dict):  # llama.cpp: tokens and cache — into timings
                usage["_timings"] = data["timings"]
            return content, usage or None
        raise UserError("Model unavailable.")

    def _sleep(self, sec: float):
        """Pause before replay, button-breakable «Stop.»."""
        left = float(sec)
        while left > 0:
            if self.stop_check:
                self.stop_check()
            step = min(1.0, left)
            time.sleep(step)
            left -= step

    # ---------- manually via the web-chat ----------
    def _webchat(self, prompt: str, text: str, check, subject: str, variables: dict | None = None):
        idx = U.read_json(self.w.p.webchat_index, None) or {"n": 0, "pending": {}}
        idx.setdefault("done", {})
        h = U.sha1(text)
        wc = self.w.p.webchat
        old = idx["done"].get(h)
        if old and (wc / "ready" / old).exists():
            obj, errs = check((wc / "ready" / old).read_text(encoding="utf-8-sig"))
            if not errs:
                return obj
        rec = idx["pending"].get(h)
        if rec:
            req, ans = wc / rec["req"], wc / rec["ans"]
            raw = ans.read_text(encoding="utf-8-sig") if ans.exists() else ""
            if raw.strip():
                obj, errs = check(raw)
                if not errs:
                    done = wc / "ready"
                    done.mkdir(exist_ok=True)
                    for f in (req, ans):
                        if f.exists():
                            f.replace(done / f.name)
                    del idx["pending"][h]
                    idx["done"][h] = rec["ans"]
                    U.write_json(self.w.p.webchat_index, idx)
                    if self.meter:
                        self.meter.record("llm", prompt, "webchat", None, "web-based-chat", None, len(text), len(raw), None)
                    return obj
                note = ("> [!warning] The response did not pass validation.\n> - " + "\n> - ".join(errs)
                        + "\n> Ask the model to correct the response (you can copy these notes) and replace the answer file’s contents.\n\n")
                body = req.read_text(encoding="utf-8")
                body = re.sub(r"^> \[!warning\].*?\n\n", "", body, flags=re.S)
                U.atomic_write_text(req, note + body)
                raise ManualPending(f"Answer in «{rec['ans']}» failed to pass the test — details in the request file.")
            raise ManualPending(f"Waiting for a response: copy ‘{rec['req']}’ to the chat, then paste the answer into ‘{rec['ans']}’.")
        idx["n"] += 1
        n = idx["n"]
        req_name = f"{n:03d} {prompt} — request.md"
        ans_name = f"{n:03d} {prompt} — reply.md"
        head = (f"Manual mode: copy everything below the line into the model’s web chat. Paste the complete response into ‘{ans_name}’ "
                f"in the same folder, save it, and resume the program.\n\nObject: {subject}\n\n"
                "---------- copy down ----------\n\n")
        U.atomic_write_text(wc / req_name, head + text)
        U.atomic_write_text(wc / ans_name, "")
        idx["pending"][h] = {"n": n, "prompt": prompt, "req": req_name, "ans": ans_name, "created": U.now_iso()}
        U.write_json(self.w.p.webchat_index, idx)
        if os.environ.get("BRAIN_TEST_WEBCHAT_VARS"):  # auto-test-only: so that the plug could «reply-chat»
            U.write_json(self.w.p.system / "webchat_vars" / f"{n:03d}.json", {"prompt": prompt, "variables": variables})
        raise ManualPending(f"Request created: ‘{req_name}’. Copy it to the web chat and paste the response into ‘{ans_name}’.")

    def ping(self, c: dict | None = None) -> str:
        """Connection check: shorthand."""
        c = c or self.conf("ping")
        if c.get("mode") == "webchat":
            return "manually via the web-chat — check-up"
        if c.get("mode") == "missing":
            raise UserError("No model profile selected (Settings → Second Brain → Models.)")
        msgs = [{"role": "user", "content": 'Reply with only this JSON object: {"ok": true}'}]
        t = time.time()
        raw, _ = self._timed("ping", msgs, {}, 0, c, record_as="Communication check")
        try:
            obj = extract_json(raw)
        except ValueError:
            obj = {}
        if obj.get("ok") is not True:
            raise UserError(f"The model responded unexpectedly: {raw[:200]}")
        where = "" if self.mode == "fake" else f" ({c.get('base_url')})"
        return f"model {c.get('model')}{where} is responding, {time.time() - t:.1f} s"

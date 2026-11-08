"""Проверка сетевого слоя без настоящего провайдера: локальный сервер в формате OpenAI
(chat/completions и embeddings) с ошибками 429/500/401, обрезанным ответом и не-JSON; профили моделей,
расходы (цены, кэш), бюджет, пересчёт стоимости.
Запуск: PYTHONPATH=. python tests/api_mock.py"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from brain import interact  # noqa: E402
from brain import llm as L  # noqa: E402
from brain import usage as US  # noqa: E402
from brain.config import load_config  # noqa: E402
from brain.context import Ctx  # noqa: E402
from brain.util import BudgetStop, UserError  # noqa: E402

SCRIPT: list = []      # очередь ответов сервера: (код, тело-объект или строка)
SEEN: list = []        # что пришло на сервер
USAGE = {"next": None}  # usage для следующего ответа (None — обычный маленький)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
        SEEN.append((self.path, self.headers.get("Authorization"), body))
        if self.path.endswith("/embeddings"):
            inp = body["input"]
            if any(len(t) > 1000 for t in inp):
                code, out = 400, {"error": "input length exceeds the context length"}
            else:
                n = sum(len(t) for t in inp)
                code, out = 200, {"data": [{"index": i, "embedding": [float(len(t) % 7 + 1), 1.0, 0.5]} for i, t in enumerate(inp)],
                                  "usage": {"prompt_tokens": n, "total_tokens": n}}
        else:
            code, out = SCRIPT.pop(0) if SCRIPT else (200, "{\"ok\": true}")
            if code == 200 and isinstance(out, str):
                out = {"choices": [{"message": {"content": out}, "finish_reason": "stop"}],
                       "usage": USAGE["next"] or {"prompt_tokens": 10, "completion_tokens": 5}}
                if "/llama/" in self.path:  # llama.cpp: время и кэш — в timings
                    out["timings"] = {"prompt_n": 70, "cache_n": 30, "predicted_n": 5, "prompt_ms": 120.0, "predicted_ms": 80.0}
                    out["usage"] = {"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105}
                USAGE["next"] = None
        raw = out.encode("utf-8") if isinstance(out, str) else json.dumps(out).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def ok(cond, label):
    if not cond:
        print(f"ПРОВАЛ: {label}")
        sys.exit(1)
    print(f"  ✓ {label}")


def rows(root):
    return [json.loads(x) for x in (root / "vault" / ".system" / "usage.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    root = Path(tempfile.mkdtemp(prefix="brain-api-"))
    (root / "vault").mkdir()
    (root / "api_key.txt").write_text("test-key\n", encoding="utf-8")
    # настройки в формате v2.4 — программа сама переводит их в профили
    (root / "settings.yaml").write_text(
        f"vault: '{(root / 'vault').as_posix()}'\n"
        f"llm: {{mode: api, base_url: 'http://127.0.0.1:{port}/v1', model: test-model, max_tokens: 1000, extra: {{thinking: {{type: disabled}}}}}}\n"
        f"embeddings: {{mode: local, base_url: 'http://127.0.0.1:{port}/v1', model: test-emb}}\n", encoding="utf-8")
    L.time.sleep = lambda s: None  # без ожиданий между повторами
    cfg = load_config(root / "settings.yaml")
    p1 = cfg["llm"]["profiles"][0]
    ok(cfg["llm"]["mode"] == "local" and cfg["llm"]["local_profile"] == "p1" and p1["kind"] == "local" and p1["model"] == "test-model",
       "настройки v2.4 (адрес 127.0.0.1) прочитаны как локальный профиль p1")
    from brain import schema as S
    S.apply_patch(cfg, {"llm": {"mode": "cloud", "cloud_profile": "p1", "profiles": {"p1": {"kind": "cloud", "name": "Тестовый"}}}})
    ok(cfg["llm"]["profiles"][0]["kind"] == "cloud" and cfg["llm"]["profiles"][0]["api_key_file"] == "api_key.txt",
       "профиль переключён на облачный, ключ прежний")
    ctx = Ctx(cfg, cmd="test")

    print("=== API модели")
    ok("отвечает" in ctx.llm.ping(), "ping через chat/completions")
    path, auth, body = SEEN[-1]
    ok(path == "/v1/chat/completions" and auth == "Bearer test-key", "адрес и ключ (из api_key.txt рядом с settings)")
    ok(body["model"] == "test-model" and body["max_tokens"] == 1000 and body["thinking"] == {"type": "disabled"}, "max_tokens и extra попали в запрос")

    SCRIPT[:] = [(429, {"error": "rate"}), (500, {"error": "oops"}), (200, "{\"ok\": true}")]
    ok("отвечает" in ctx.llm.ping(), "повторы после 429 и 500")

    SCRIPT[:] = [(200, {"weird": True})]
    try:
        ctx.llm.ping()
        ok(False, "неожиданный ответ провайдера → понятная ошибка")
    except UserError as e:
        ok("Неожиданный ответ" in str(e), "неожиданный ответ провайдера → понятная ошибка")

    SCRIPT[:] = [(401, {"error": "bad key"})]
    try:
        ctx.llm.ping()
        ok(False, "401 → ошибка про ключ")
    except UserError as e:
        ok("ключ" in str(e) and "Тестовый" in str(e), "401 → ошибка про ключ с именем профиля")

    # обрезанный по длине ответ: для JSON-промпта — повтор с просьбой короче, для Синтеза — понятная ошибка
    L.P.render = lambda cfg, name, variables: "тестовый промпт"
    cut = {"choices": [{"message": {"content": "{\"reasoning\": \"длинн"}, "finish_reason": "length"}]}
    SCRIPT[:] = [(200, cut), (200, "{\"reasoning\": \"коротко\", \"questions\": []}")]
    obj = ctx.llm.json("Вопросы", {}, subject="тест")
    ok(obj["questions"] == [] and "оборвался" in SEEN[-1][2]["messages"][-1]["content"], "оборванный JSON → повтор с просьбой короче")
    SCRIPT[:] = [(200, cut)]
    try:
        ctx.llm.text("Синтез", {}, subject="тест")
        ok(False, "оборванный синтез → ошибка с советом про предел длины")
    except UserError as e:
        ok("max_tokens" in str(e) and "Тестовый" in str(e), "оборванный синтез → ошибка с советом про предел длины профиля")
    r, last = rows(root)[-2:]
    ok(r["profile"] == "p1" and r["ptype"] == "cloud" and r["prompt"] == "Вопросы" and r["in"] == 10 and r["out"] == 5
       and r["usage"]["prompt_tokens"] == 10 and r["sec"] is not None and not r["est"], "расход записан: профиль, шаг, токены, время")
    ok(last["prompt"] == "Синтез" and last["est"] and last["in"] == 5, "провайдер не сообщил токены — оценка по знакам (с пометкой)")

    print("=== Профили и модели по шагам (llm.roles)")
    S.apply_patch(cfg, {"llm": {"profiles": {
        "p2": {"name": "Большая", "kind": "cloud", "base_url": f"http://127.0.0.1:{port}/v1", "model": "big-model",
               "temperature": 0.7, "api_key_file": "api_key.txt"},
        "p3": {"name": "Llama", "kind": "local", "base_url": f"http://localhost:{port}/llama/v1", "model": "llama-local"},
        "p4": {"name": "Другой", "kind": "cloud", "base_url": "https://api.example.invalid/v1", "model": "other-model"}},
        "roles": {"Синтез": "p2", "Вопросы": "p3", "Ценность": "p4"}}})
    c2 = load_config(root / "settings.yaml")
    ok(c2["llm"]["roles"] == {"Синтез": "p2", "Вопросы": "p3", "Ценность": "p4"} and len(c2["llm"]["profiles"]) == 4,
       "профили и модели шагов сохранены в settings.yaml")
    SCRIPT[:] = [(200, "{\"reasoning\": \"…\", \"questions\": []}")]
    ctx.llm.json("Вопросы", {}, subject="тест")
    path, auth, body = SEEN[-1]
    ok(path == "/llama/v1/chat/completions" and body["model"] == "llama-local" and auth is None,
       "шаг «Вопросы» — на свой локальный сервер (llama.cpp), ключ туда не уходит")
    r = rows(root)[-1]
    ok(r["profile"] == "p3" and r["ptype"] == "local" and r["in"] == 100 and r["cached"] == 30 and r["cost"] is None,
       "локальная модель: токены и кэш из timings llama.cpp, без стоимости")
    SCRIPT[:] = [(200, "# Документ")]
    ctx.llm.text("Синтез", {}, subject="тест")
    path, auth, body = SEEN[-1]
    ok(path == "/v1/chat/completions" and body["model"] == "big-model" and body["temperature"] == 0.7 and auth == "Bearer test-key",
       "шаг «Синтез» — профиль с другой моделью у того же провайдера")
    try:
        ctx.llm.json("Ценность", {}, subject="тест")
        ok(False, "профиль без ключа → понятная ошибка")
    except UserError as e:
        ok("Другой" in str(e) and "Ценность" in str(e) and "ключ" in str(e), "профиль без ключа → понятная ошибка с именем профиля и шага")
    S.save_key(cfg, "role:Ценность", "role-key")
    p4 = next(p for p in cfg["llm"]["profiles"] if p["id"] == "p4")
    ok((root / "api_key_p4.txt").read_text(encoding="utf-8").strip() == "role-key" and p4["api_key_file"] == "api_key_p4.txt",
       "ключ профиля — в свой файл (и по старому адресу role:<шаг>)")
    groups = ctx.llm.models()
    ok(len(groups) == 4 and any(g[1] == ["Вопросы"] for g in groups), "«Проверка связи» видит 4 разных профиля")
    ok("отвечает" in ctx.llm.ping(next(g[0] for g in groups if g[1] == ["Вопросы"])), "проверка связи с локальным сервером без ключа")
    ok(ctx.llm.label(next(g[0] for g in groups if g[1] == ["Вопросы"])) == "Llama (локальная модель)", "имя профиля и вид — в сообщениях")

    print("=== Модель с небольшим окном (свой сервер llama.cpp)")
    S.apply_patch(cfg, {"llm": {"profiles": {"p3": {"max_input_chars": 30000}}, "roles": {"Классификация": "p3"}}})
    ok(S.input_limit(cfg, "Классификация") == 30000 and S.input_limit(cfg, "Синтез") == 300000,
       "предел запроса — у профиля шага, у остальных — у основного")
    bad = json.loads(json.dumps(cfg.data))
    next(p for p in bad["llm"]["profiles"] if p["id"] == "p3")["max_input_chars"] = 500
    ok(any("max_input_chars" in e for e in S.validate(bad)), "слишком маленький предел профиля отклоняется с понятной ошибкой")
    over = {"error": {"code": 400, "message": "the request exceeds the available context size, try increasing it",
                      "type": "exceed_context_size_error"}}
    SCRIPT[:] = [(400, over)]
    try:
        ctx.llm.json("Классификация", {}, subject="тест")
        ok(False, "переполнение окна → понятная ошибка")
    except UserError as e:
        ok("не поместился" in str(e) and "Предел запроса" in str(e) and "-c" in str(e), "переполнение окна → совет уменьшить предел или дать окно больше")
    S.apply_patch(cfg, {"llm": {"roles": {"Вопросы": "p3"}}})
    SCRIPT[:] = [(500, {"error": "input is too long for the context size"}), (200, "{\"ok\": true}")]
    n = len(SEEN)
    try:
        ctx.llm.json("Вопросы", {}, subject="тест")
        ok(False, "переполнение с кодом 500 → без бесполезных повторов")
    except UserError as e:
        ok(len(SEEN) == n + 1 and "окном побольше" in str(e), "переполнение с кодом 500 → без бесполезных повторов, совет про модель шага")
    SCRIPT[:] = []
    S.apply_patch(cfg, {"llm": {"roles": {}}})
    SCRIPT[:] = [(200, "# Документ")]
    ctx.llm.text("Синтез", {}, subject="тест")
    ok(SEEN[-1][2]["model"] == "test-model", "без своих моделей все шаги — на основном профиле")

    print("=== Расходы: цены, кэш, бюджет, пересчёт")
    S.apply_patch(cfg, {"llm": {"profiles": {"p1": {"prices": {"input": 1.0, "cached_input": 0.1, "output": 2.0}}}}})
    USAGE["next"] = {"prompt_tokens": 1_000_000, "completion_tokens": 500_000, "prompt_tokens_details": {"cached_tokens": 400_000}}
    SCRIPT[:] = [(200, "# Документ")]
    ctx.llm.text("Синтез", {}, subject="тест")
    r = rows(root)[-1]
    ok(r["cached"] == 400_000 and abs(r["cost"] - 1.64) < 1e-9, "стоимость: вход 600 тыс. × $1 + кэш 400 тыс. × $0.1 + выход 500 тыс. × $2 = $1.64")
    ok(abs(ctx.meter.totals()["cost"] - 1.64) < 1e-9, "расход текущего запуска считается на лету")
    S.apply_patch(cfg, {"budget": {"monthly_usd": 2.0, "warn_pct": 80}})
    SCRIPT[:] = [(200, "# Документ")]
    ctx.llm.text("Синтез", {}, subject="тест")
    ok(any("82%" in x for x in ctx.notices), "80% бюджета — предупреждение (раз за запуск)")
    USAGE["next"] = {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}
    SCRIPT[:] = [(200, "# Документ")]
    ctx.llm.text("Синтез", {}, subject="тест")
    n = len(SEEN)
    try:
        ctx.llm.text("Синтез", {}, subject="тест")
        ok(False, "бюджет исчерпан → остановка перед обращением")
    except BudgetStop as e:
        ok(len(SEEN) == n and "бюджета" in e.text, "бюджет исчерпан, спросить нельзя → остановка перед обращением (без запроса)")
    interact.configure(True, "stdin")
    old_in, old_out = sys.stdin, sys.stdout
    buf = io.StringIO()
    try:
        sys.stdin, sys.stdout = io.StringIO('{"choice": 0}\n'), buf
        SCRIPT[:] = [(200, "# Документ"), (200, "# Документ")]
        ctx.llm.text("Синтез", {}, subject="тест")
        ctx.llm.text("Синтез", {}, subject="тест")
    finally:
        sys.stdin, sys.stdout = old_in, old_out
        interact.configure(False, "none")
    asks = [x for x in buf.getvalue().splitlines() if x.startswith("@@ASK ")]
    ok(len(asks) == 1 and json.loads(asks[0][6:])["options"][0].startswith("Продолжить") and len(SEEN) == n + 2,
       "вопрос о бюджете — строкой @@ASK, «Продолжить» действует до конца запуска")
    ok(any(x.startswith("@@USAGE ") for x in buf.getvalue().splitlines())
       and any(x.startswith("@@WAIT ") for x in buf.getvalue().splitlines()), "живые строки расхода и ожидания ответа для плагина")
    S.apply_patch(cfg, {"budget": {"monthly_usd": None},
                        "llm": {"profiles": {"p2": {"budget_month": 0.0001, "prices": {"input": 1.0, "output": 1.0}}},
                                "roles": {"Синтез": "p2"}}})
    ctx2 = Ctx(cfg, cmd="test2")
    USAGE["next"] = {"prompt_tokens": 1000, "completion_tokens": 100}
    SCRIPT[:] = [(200, "# Документ")]
    ctx2.llm.text("Синтез", {}, subject="тест")
    try:
        ctx2.llm.text("Синтез", {}, subject="тест")
        ok(False, "лимит профиля")
    except BudgetStop as e:
        ok("Большая" in e.text, "свой месячный лимит профиля")
    S.apply_patch(cfg, {"llm": {"roles": {}, "profiles": {"p2": {"budget_month": None}}}})
    s = US.summary(cfg, root / "vault" / ".system" / "usage.jsonl")
    pr = {p["id"]: p for p in s["profiles"] if p.get("id")}
    ok(pr["p1"]["totals"]["month"]["calls"] >= 6 and pr["p1"]["priced"] and pr["p3"]["ptype"] == "local"
       and s["current"]["key"] == "p1" and any(st["name"] == "Синтез" for st in s["steps"]), "сводка расходов: по профилям, шагам, текущий профиль")
    S.apply_patch(cfg, {"llm": {"profiles": {"p1": {"prices": {"input": 2.0, "cached_input": None, "output": 4.0}}}}})
    n = US.reprice(cfg, root / "vault" / ".system" / "usage.jsonl", "p1")
    big = [x for x in rows(root) if x["profile"] == "p1" and x["in"] == 1_000_000 and x["cached"] == 400_000]
    ok(n >= 1 and big and abs(big[0]["cost"] - 4.0) < 1e-9 and (root / "vault" / ".system" / "usage.jsonl.bak").exists(),
       "пересчёт по новым ценам (кэш без своей цены — как обычный вход), прежний журнал — в .bak")

    print("=== Эмбеддинги (Ollama-формат и облачные с ценой)")
    v = ctx.emb.embed(["короткий", "x" * 3000, "ещё"])
    ok(v.shape == (3, 3), "векторы получены, длинный текст укорочен после ошибки окна")
    ok(abs(float((v[0] ** 2).sum()) - 1) < 1e-5, "векторы нормированы")
    (root / "emb_key.txt").write_text("emb-key\n", encoding="utf-8")
    S.apply_patch(cfg, {"embeddings": {"mode": "cloud", "base_url": f"http://127.0.0.1:{port}/v1", "model": "emb-cloud",
                                       "api_key_file": "emb_key.txt", "price_input": 0.5}})
    ctx3 = Ctx(cfg, cmd="emb")
    ctx3.emb.embed(["раз", "два"])
    r = rows(root)[-1]
    ok(SEEN[-1][1] == "Bearer emb-key" and r["kind"] == "emb" and r["in"] == 6 and abs(r["cost"] - 6 * 0.5 / 1e6) < 1e-12,
       "облачные эмбеддинги: ключ, токены и стоимость в журнале")
    srv.shutdown()
    print("\nСетевой слой в порядке.")


if __name__ == "__main__":
    main()

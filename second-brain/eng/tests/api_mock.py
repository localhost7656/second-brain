"""Checking the network layer without a real provider: local server OpenAI
(chat/completions and embeddings) faulty 429/500/401, circumcised-JSON; model profile,
expense (price, cash), budget, costing.
Launch: PYTHONPATH=. python tests/api_mock.py"""
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

SCRIPT: list = []      # server response: (code, body-line)
SEEN: list = []        # What came to the server
USAGE = {"next": None}  # usage next-response (None — petty)


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
                if "/llama/" in self.path:  # llama.cpp: time and cache — into timings
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
        print(f"Failure: {label}")
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
    # formatting v2.4 — The program itself translates them into profiles.
    (root / "settings.yaml").write_text(
        f"vault: '{(root / 'vault').as_posix()}'\n"
        f"llm: {{mode: api, base_url: 'http://127.0.0.1:{port}/v1', model: test-model, max_tokens: 1000, extra: {{thinking: {{type: disabled}}}}}}\n"
        f"embeddings: {{mode: local, base_url: 'http://127.0.0.1:{port}/v1', model: test-emb}}\n", encoding="utf-8")
    L.time.sleep = lambda s: None  # without waiting between repetitions
    cfg = load_config(root / "settings.yaml")
    p1 = cfg["llm"]["profiles"][0]
    ok(cfg["llm"]["mode"] == "local" and cfg["llm"]["local_profile"] == "p1" and p1["kind"] == "local" and p1["model"] == "test-model",
       "setting v2.4 (address 127.0.0.1) Read as a local profile p1")
    from brain import schema as S
    S.apply_patch(cfg, {"llm": {"mode": "cloud", "cloud_profile": "p1", "profiles": {"p1": {"kind": "cloud", "name": "Testing."}}}})
    ok(cfg["llm"]["profiles"][0]["kind"] == "cloud" and cfg["llm"]["profiles"][0]["api_key_file"] == "api_key.txt",
       "Profile switched to cloud, former")
    ctx = Ctx(cfg, cmd="test")

    print("=== API model")
    ok("is responding" in ctx.llm.ping(), "ping through chat/completions")
    path, auth, body = SEEN[-1]
    ok(path == "/v1/chat/completions" and auth == "Bearer test-key", "address (from api_key.txt near settings)")
    ok(body["model"] == "test-model" and body["max_tokens"] == 1000 and body["thinking"] == {"type": "disabled"}, "max_tokens and extra caught up")

    SCRIPT[:] = [(429, {"error": "rate"}), (500, {"error": "oops"}), (200, "{\"ok\": true}")]
    ok("is responding" in ctx.llm.ping(), "post-repeat 429 and 500")

    SCRIPT[:] = [(200, {"weird": True})]
    try:
        ctx.llm.ping()
        ok(False, "surprise response from the provider → misunderstood")
    except UserError as e:
        ok("Unexpected response from the provider" in str(e), "surprise response from the provider → misunderstood")

    SCRIPT[:] = [(401, {"error": "bad key"})]
    try:
        ctx.llm.ping()
        ok(False, "401 → key-break")
    except UserError as e:
        ok("key" in str(e) and "Testing." in str(e), "401 → Profile name error")

    # cut-off: for JSON-practicum — shorten, for Synthesis? — misunderstood
    L.P.render = lambda cfg, name, variables: "test-prompt"
    cut = {"choices": [{"message": {"content": "{\"reasoning\": \"long"}, "finish_reason": "length"}]}
    SCRIPT[:] = [(200, cut), (200, "{\"reasoning\": \"shorthand\", \"questions\": []}")]
    obj = ctx.llm.json("Questions", {}, subject="test")
    ok(obj["questions"] == [] and "truncated" in SEEN[-1][2]["messages"][-1]["content"], "ragged JSON → shorten")
    SCRIPT[:] = [(200, cut)]
    try:
        ctx.llm.text("Synthesis", {}, subject="test")
        ok(False, "fusion → Mistake with advice about length limit")
    except UserError as e:
        ok("max_tokens" in str(e) and "Testing." in str(e), "fusion → Mistake with advice about the length of the profile")
    r, last = rows(root)[-2:]
    ok(r["profile"] == "p1" and r["ptype"] == "cloud" and r["prompt"] == "Questions" and r["in"] == 10 and r["out"] == 5
       and r["usage"]["prompt_tokens"] == 10 and r["sec"] is not None and not r["est"], "expense: profile, step, token, time")
    ok(last["prompt"] == "Synthesis" and last["est"] and last["in"] == US.tokens(None, last["chars_in"], last["chars_out"])[0], "provider did not disclose tokens — marking (marked)")

    print("=== Profiles and models by step (llm.roles)")
    S.apply_patch(cfg, {"llm": {"profiles": {
        "p2": {"name": "Large", "kind": "cloud", "base_url": f"http://127.0.0.1:{port}/v1", "model": "big-model",
               "temperature": 0.7, "api_key_file": "api_key.txt"},
        "p3": {"name": "Llama", "kind": "local", "base_url": f"http://localhost:{port}/llama/v1", "model": "llama-local"},
        "p4": {"name": "Other", "kind": "cloud", "base_url": "https://api.example.invalid/v1", "model": "other-model"}},
        "roles": {"Synthesis": "p2", "Questions": "p3", "Value": "p4"}}})
    c2 = load_config(root / "settings.yaml")
    ok(c2["llm"]["roles"] == {"Synthesis": "p2", "Questions": "p3", "Value": "p4"} and len(c2["llm"]["profiles"]) == 4,
       "profiles and steps are saved in settings.yaml")
    SCRIPT[:] = [(200, "{\"reasoning\": \"…\", \"questions\": []}")]
    ctx.llm.json("Questions", {}, subject="test")
    path, auth, body = SEEN[-1]
    ok(path == "/llama/v1/chat/completions" and body["model"] == "llama-local" and auth is None,
       "step «Questions» — to your local server (llama.cpp), The key doesnt go away.")
    r = rows(root)[-1]
    ok(r["profile"] == "p3" and r["ptype"] == "local" and r["in"] == 100 and r["cached"] == 30 and r["cost"] is None,
       "localization: tokens and cache timings llama.cpp, costless")
    SCRIPT[:] = [(200, "# Document")]
    ctx.llm.text("Synthesis", {}, subject="test")
    path, auth, body = SEEN[-1]
    ok(path == "/v1/chat/completions" and body["model"] == "big-model" and body["temperature"] == 0.7 and auth == "Bearer test-key",
       "step «Synthesis» — Profile with a different model from the same provider")
    try:
        ctx.llm.json("Value", {}, subject="test")
        ok(False, "keyless → misunderstood")
    except UserError as e:
        ok("Other" in str(e) and "Value" in str(e) and "key" in str(e), "keyless → Understandable error with profile name and step")
    S.save_key(cfg, "role:Value", "role-key")
    p4 = next(p for p in cfg["llm"]["profiles"] if p["id"] == "p4")
    ok((root / "api_key_p4.txt").read_text(encoding="utf-8").strip() == "role-key" and p4["api_key_file"] == "api_key_p4.txt",
       "key — file (and at the old address. role:<step>)")
    groups = ctx.llm.models()
    ok(len(groups) == 4 and any(g[1] == ["Questions"] for g in groups), "«Communication check» see 4 profile")
    ok("is responding" in ctx.llm.ping(next(g[0] for g in groups if g[1] == ["Questions"])), "Checking the connection with the local server without a key")
    ok(ctx.llm.label(next(g[0] for g in groups if g[1] == ["Questions"])) == "Llama (local model)", "profilename — message-wise")

    print("=== Model with a small window (server llama.cpp)")
    S.apply_patch(cfg, {"llm": {"profiles": {"p3": {"max_input_chars": 30000}}, "roles": {"Classification": "p3"}}})
    ok(S.input_limit(cfg, "Classification") == 30000 and S.input_limit(cfg, "Synthesis") == 300000,
       "limit — step-profile, others — primary")
    bad = json.loads(json.dumps(cfg.data))
    next(p for p in bad["llm"]["profiles"] if p["id"] == "p3")["max_input_chars"] = 500
    ok(any("max_input_chars" in e for e in S.validate(bad)), "too small profile limit is deflected with an understandable error")
    over = {"error": {"code": 400, "message": "the request exceeds the available context size, try increasing it",
                      "type": "exceed_context_size_error"}}
    SCRIPT[:] = [(400, over)]
    try:
        ctx.llm.json("Classification", {}, subject="test")
        ok(False, "window-flow → misunderstood")
    except UserError as e:
        ok("context window" in str(e) and "request character limit" in str(e) and "-c" in str(e), "window-flow → Reduce the limit or give the window a bigger window")
    S.apply_patch(cfg, {"llm": {"roles": {"Questions": "p3"}}})
    SCRIPT[:] = [(500, {"error": "input is too long for the context size"}), (200, "{\"ok\": true}")]
    n = len(SEEN)
    try:
        ctx.llm.json("Questions", {}, subject="test")
        ok(False, "code-overflow 500 → pointlessly")
    except UserError as e:
        ok(len(SEEN) == n + 1 and "larger context window" in str(e), "code-overflow 500 → pointlessly, step-model")
    SCRIPT[:] = []
    S.apply_patch(cfg, {"llm": {"roles": {}}})
    SCRIPT[:] = [(200, "# Document")]
    ctx.llm.text("Synthesis", {}, subject="test")
    ok(SEEN[-1][2]["model"] == "test-model", "without models, all steps — main profile")

    print("=== Expenses: price, cash, budget, calculation")
    S.apply_patch(cfg, {"llm": {"profiles": {"p1": {"prices": {"input": 1.0, "cached_input": 0.1, "output": 2.0}}}}})
    USAGE["next"] = {"prompt_tokens": 1_000_000, "completion_tokens": 500_000, "prompt_tokens_details": {"cached_tokens": 400_000}}
    SCRIPT[:] = [(200, "# Document")]
    ctx.llm.text("Synthesis", {}, subject="test")
    r = rows(root)[-1]
    ok(r["cached"] == 400_000 and abs(r["cost"] - 1.64) < 1e-9, "cost: entrance 600 thousand. × $1 + cash 400 thousand. × $0.1 + exit 500 thousand. × $2 = $1.64")
    ok(abs(ctx.meter.totals()["cost"] - 1.64) < 1e-9, "Current start-up expense is considered on the fly")
    S.apply_patch(cfg, {"budget": {"monthly_usd": 2.0, "warn_pct": 80}})
    SCRIPT[:] = [(200, "# Document")]
    ctx.llm.text("Synthesis", {}, subject="test")
    ok(any("82%" in x for x in ctx.notices), "80% budget — warning (once-start)")
    USAGE["next"] = {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}
    SCRIPT[:] = [(200, "# Document")]
    ctx.llm.text("Synthesis", {}, subject="test")
    n = len(SEEN)
    try:
        ctx.llm.text("Synthesis", {}, subject="test")
        ok(False, "budget exhausted → stopover")
    except BudgetStop as e:
        ok(len(SEEN) == n and "budget" in e.text, "budget exhausted, ask → stopover (requestlessly)")
    interact.configure(True, "stdin")
    old_in, old_out = sys.stdin, sys.stdout
    buf = io.StringIO()
    try:
        sys.stdin, sys.stdout = io.StringIO('{"choice": 0}\n'), buf
        SCRIPT[:] = [(200, "# Document"), (200, "# Document")]
        ctx.llm.text("Synthesis", {}, subject="test")
        ctx.llm.text("Synthesis", {}, subject="test")
    finally:
        sys.stdin, sys.stdout = old_in, old_out
        interact.configure(False, "none")
    asks = [x for x in buf.getvalue().splitlines() if x.startswith("@@ASK ")]
    ok(len(asks) == 1 and json.loads(asks[0][6:])["options"][0].startswith("Continue") and len(SEEN) == n + 2,
       "budgetary — line @@ASK, «Continue.» active until the end of launch")
    ok(any(x.startswith("@@USAGE ") for x in buf.getvalue().splitlines())
       and any(x.startswith("@@WAIT ") for x in buf.getvalue().splitlines()), "Live flow lines and waiting for a response for the plugin")
    S.apply_patch(cfg, {"budget": {"monthly_usd": None},
                        "llm": {"profiles": {"p2": {"budget_month": 0.0001, "prices": {"input": 1.0, "output": 1.0}}},
                                "roles": {"Synthesis": "p2"}}})
    ctx2 = Ctx(cfg, cmd="test2")
    USAGE["next"] = {"prompt_tokens": 1000, "completion_tokens": 100}
    SCRIPT[:] = [(200, "# Document")]
    ctx2.llm.text("Synthesis", {}, subject="test")
    try:
        ctx2.llm.text("Synthesis", {}, subject="test")
        ok(False, "profile")
    except BudgetStop as e:
        ok("Large" in e.text, "your monthly profile limit")
    S.apply_patch(cfg, {"llm": {"roles": {}, "profiles": {"p2": {"budget_month": None}}}})
    s = US.summary(cfg, root / "vault" / ".system" / "usage.jsonl")
    pr = {p["id"]: p for p in s["profiles"] if p.get("id")}
    ok(pr["p1"]["totals"]["month"]["calls"] >= 6 and pr["p1"]["priced"] and pr["p3"]["ptype"] == "local"
       and s["current"]["key"] == "p1" and any(st["name"] == "Synthesis" for st in s["steps"]), "expense-book: profiled, footsteps, current profile")
    S.apply_patch(cfg, {"llm": {"profiles": {"p1": {"prices": {"input": 2.0, "cached_input": None, "output": 4.0}}}}})
    n = US.reprice(cfg, root / "vault" / ".system" / "usage.jsonl", "p1")
    big = [x for x in rows(root) if x["profile"] == "p1" and x["in"] == 1_000_000 and x["cached"] == 400_000]
    ok(n >= 1 and big and abs(big[0]["cost"] - 4.0) < 1e-9 and (root / "vault" / ".system" / "usage.jsonl.bak").exists(),
       "recalculation (cash-free — normal entrance), journal — into .bak")

    print("=== embeddingi (Ollama-format and cloud-based price)")
    v = ctx.emb.embed(["short-lived", "x" * 3000, "still"])
    ok(v.shape == (3, 3), "vectors, Long text shortened after window error")
    ok(abs(float((v[0] ** 2).sum()) - 1) < 1e-5, "vectors normalized")
    (root / "emb_key.txt").write_text("emb-key\n", encoding="utf-8")
    S.apply_patch(cfg, {"embeddings": {"mode": "cloud", "base_url": f"http://127.0.0.1:{port}/v1", "model": "emb-cloud",
                                       "api_key_file": "emb_key.txt", "price_input": 0.5}})
    ctx3 = Ctx(cfg, cmd="emb")
    ctx3.emb.embed(["once", "two-way"])
    r = rows(root)[-1]
    ok(SEEN[-1][1] == "Bearer emb-key" and r["kind"] == "emb" and r["in"] == len("once") + len("two-way") and abs(r["cost"] - (len("once") + len("two-way")) * 0.5 / 1e6) < 1e-12,
       "cloud-emblem: key, tokens and value in the journal")
    srv.shutdown()
    print("\nThe network layer is fine..")


if __name__ == "__main__":
    main()

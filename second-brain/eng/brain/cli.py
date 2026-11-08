"""Programme teams (section 20): run — Phase 1, synth — Phase 2, check, status, revalidate, patterns."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

from . import __version__
from . import interact
from . import util as U
from .config import load_config
from .util import ManualPending, UserError

RESULT: dict = {}  # plugin (flag --json): line-end «@@RESULT {…}»
PLUGIN_ID = "vtoroy-mozg"
PLUGIN_FILES = ("main.js", "manifest.json", "styles.css")

HELP = """Second Brain — commands:
  run                     Phase 1: process answers and new files in _staging
                          (large runs show an estimate and ask for confirmation; --yes skips confirmation)
  synth [container]       Phase 2: write or update a container's documents (omit name to choose);
                          unchanged documents are skipped unless --force is supplied
  check                   check settings, models, and embeddings
  status                  show entries, questions, queues, and expenses
  usage                   model usage today, this month, and overall, by profile and step
                          (--reprice <profile|emb|all> recalculates past costs at current prices)
  estimate run | synth <container> | revalidate [container]
                          estimate model calls, time, and cost without starting the run
  revalidate [container]  thoroughly recheck classification (omit name for all entries;
                          --ask to select from a list, --yes to skip confirmation)
  patterns                find new composite aspect types
  update                  update from GitHub (repository in UPDATE_REPO in brain/__init__.py;
                          --check only checks for updates)
  llama status | start | stop | download
                          inspect, start, stop, or download the local llama.cpp embedding model;
                          --params-json - supplies startup parameters as JSON
  setup                   complete setup (also run by Install.bat): settings, Obsidian plugin,
                          cleanup of old-version files, and embedding model
  install-plugin [folder]  install only the Second Brain plugin into an Obsidian vault
For the plugin: snapshot, answer <Q> --option N | --text ..., advise <container>,
  settings --set-json - | --key profile:<id> | embeddings.
Common options: --settings <path to settings.yaml> (defaults to the program directory);
  --vault <folder> selects a different vault without changing settings.yaml;
  --json emits an @@RESULT line for the plugin; --ask-stdin emits @@ASK lines and reads
  answers from standard input for the plugin.
"""


class RunLock:
    """Do not allow to run two runs at the same time over the same storage."""

    def __init__(self, path):
        self.path = path
        self.f = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.path, "a+")
        try:
            self.f.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            raise UserError("The program is already working with this vault in another window. Wait for it to finish or close the other window.")
        stop = self.path.parent / "stop"
        if stop.exists():  # «Stop.», pressed, When the program is finished, — You will not be able to stop the next launch.
            try:
                stop.unlink()
            except OSError:
                pass
        return self

    def __exit__(self, *a):
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            self.f.close()
        except OSError:
            pass


def _lock_path(cfg) -> Path:
    """Blocking is taken before loading the state: Otherwise, the second launch could work with an old copy.."""
    if not cfg.vault.exists():
        raise UserError(f"Vault folder not found: {cfg.vault}. Check the vault setting in settings.yaml.")
    return cfg.vault / ".system" / "lock"


def _ctx(cfg, need_llm=True, cmd=""):
    from .context import Ctx
    if not cfg.vault.exists():
        raise UserError(f"Vault folder not found: {cfg.vault}. Check the vault setting in settings.yaml.")
    return Ctx(cfg, need_llm=need_llm, cmd=cmd)


def _execute(ctx, fn, empty: str = "Nothing new.") -> int:
    """Total step start: manual (wait-chat), «Stop.» (file .system/stop or Ctrl+C), budget, final."""
    code = 0
    try:
        fn()
        title = "Ready."
        if ctx.result.get("cancelled"):
            title, empty = "Cancelled.", "Nothing changed."
    except ManualPending as e:
        title = "Stopped pending response from the web-chat"
        ctx.notices.append(str(e))
        RESULT["webchat"] = True
    except U.BudgetStop as e:
        title = "Stopped: budget exhausted"
        ctx.notices.append(e.text)
        RESULT.update({"stopped": True, "budget_stop": True})
        code = 1
    except KeyboardInterrupt:
        title = "Stopped."
        ctx.notices.append("Completed work has been saved. The next run will continue from here.")
        RESULT["stopped"] = True
        code = 1
    t = ctx.meter.totals()
    if t["calls"] or ctx.stats:
        ctx.logs.change("programme", f"{RUN_NAMES.get(ctx.meter.cmd, ctx.meter.cmd or 'launch')}: {title.lower()} — "
                        + _run_line(t))
    ctx.finish()
    _summary(ctx, title, empty)
    return code


RUN_NAMES = {"run": "Phase 1", "synth": "Phase 2", "revalidate": "Revalidation", "patterns": "Search for composite types",
             "advise": "Threshold Council", "answer": "Answer to the question", "check": "Verification"}


def _run_line(t: dict) -> str:
    """«duration 3 mine 12 s; modelling 25; token 120 000 → 9 000; $0.14»"""
    from .usage import money, num
    parts = [f"duration {U.duration(t['elapsed'])}"]
    if t["calls"]:
        parts.append(f"model requests {t['calls']}")
        parts.append(f"tokens {num(t['in'])} → {num(t['out'])}" + (f" (cached {num(t['cached'])})" if t["cached"] else ""))
        if t["cost"]:
            parts.append(money(t["cost"]) + (" excluding unpriced requests" if t["unpriced"] else ""))
        elif t["unpriced"]:
            parts.append("cost not calculated — no profile prices")
    return "; ".join(parts)


def _estimate(fn, *a):
    """Evaluation should not interfere with launch: if you didnt count. — Were gonna launch it without her.."""
    try:
        return fn(*a)
    except UserError:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"  ! Could not calculate the run estimate: {e}")
        return None


def _confirm(ctx, e: dict | None, always: bool = False, fallback: list[str] | None = None) -> bool:
    """Big launch (or — always): show an assessment and ask. You cant ask. — launch."""
    from . import estimate as ES
    if e:
        RESULT["estimate"] = e
    if not always and (not e or not ES.over(ctx.cfg, e)):
        return True
    lines = (e or {}).get("lines") or fallback or []
    title = (e or {}).get("title") or "Launch"
    if interact.STATE["ask"] != "tty":
        print(f"Run estimate ({title}):")
        for ln in lines:
            print("  " + ln)
    if not interact.can_ask():
        return True
    ch = interact.ask("estimate", "Revalidation" if always else "Big launch",
                      f"{title}: this is a rough estimate and may change during processing. Start?",
                      ["Start", "Cancel"], default=0, lines=lines)
    return ch == 0


def _cancelled() -> int:
    print("Cancelled; nothing changed.")
    RESULT.update({"title": "Cancelled.", "cancelled": True})
    return 0


def _summary(ctx, title: str, empty: str = "Nothing new."):
    s = ctx.stats
    w = ctx.w
    parts = []
    names = [("files", "files received"), ("items_classified", "files analyzed"), ("placed", "entries placed"),
             ("quarantined", "for review"), ("unsorted", "unassigned"), ("containers_created", "new containers"),
             ("compacted", "entries compacted"), ("aspects", "aspects extracted"), ("composites", "composites assembled"),
             ("duplicates", "duplicates linked"), ("bases", "synthesis bases assembled"), ("products", "documents written"),
             ("answers", "responses")]
    for k, label in names:
        if s.get(k):
            parts.append(f"{label}: {s[k]}")
    print()
    print(f"{title} — " + "; ".join(parts) + "." if parts else (f"{title}. {empty}" if empty else f"{title}."))
    calls = sum((ctx.llm.calls if ctx.llm else {}).values())
    if calls:
        print(f"Model requests: {calls} (" + ", ".join(f"{k} — {v}" for k, v in ctx.llm.calls.items()) + ").")
    t = ctx.meter.totals()
    line = _run_line(t)
    print(line[:1].upper() + line[1:] + ".")
    nq = len(ctx.q.open)
    if nq:
        print(f"Open questions: {nq} — see open-questions.md in the vault.")
    for wmsg in dict.fromkeys(w.warnings):
        print(f"  ! {wmsg}")
    for n in ctx.notices:
        print(f"  • {n}")
    RESULT.update({"title": title, "stats": dict(s), "calls": dict(ctx.llm.calls) if ctx.llm else {},
                   "notices": list(ctx.notices), "warnings": list(dict.fromkeys(w.warnings)), "questions": nq,
                   "messages": list(ctx.messages), "run_usage": t, "elapsed": t["elapsed"], "run_id": ctx.meter.run_id})
    RESULT.update(ctx.result)


def cmd_run(cfg, args):
    from . import estimate, phase1
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, cmd="run")
        print(f"Phase 1 · vault {cfg.vault}", flush=True)
        if not args.yes and not _confirm(ctx, _estimate(estimate.run, ctx)):
            return _cancelled()
        return _execute(ctx, lambda: phase1.run(ctx))


def _pick_container(ctx, name: str | None, cmd: str = "synth"):
    """Container by name or selection from the list in the console. For the Phase 2 — only fusion-based containers,
    door-to-door (cmd="advise") — everything."""
    w = ctx.w
    if name:
        n = w.resolve_container(name)
        if n is None:
            cands = [x for x in w.nodes.values() if name.lower() in x.title.lower()]
            if len(cands) == 1:
                return cands[0]
            raise UserError(f"Container «{name}» found." + (" Similar.: " + ", ".join(c.title for c in cands[:10]) if cands else ""))
        return n
    nodes = sorted(w.nodes.values(), key=lambda x: (w.path_key(x).lower()))
    advise = cmd == "advise"
    if advise:
        if not nodes:
            raise UserError("There are no containers yet. Approve the draft structure first.")
    else:
        nodes = [n for n in nodes if w.base(n.id)]
        if not nodes:
            raise UserError("No container has a synthesis base yet. Run Phase 1 first.")
    need = f"Please indicate the name of the container.: {cmd} \"Name of name\"."
    if not _interactive():
        raise UserError(need)
    print("Which container to recommend the thresholds for?" if advise else "For which container to write documents?")
    for i, n in enumerate(nodes, 1):
        mark = " (synthesis base is outdated — run Phase 1)" if not advise and n.id in w.state["dirty"] else ""
        print(f"  {i:>3}. {'   ' * w.depth(n)}{n.title}{mark}")
    if not sys.stdin or not sys.stdin.isatty():
        raise UserError(need)
    while True:
        s = input("Number (leave empty to cancel): ").strip()
        if not s:
            raise UserError("Cancelled.")
        if s.isdigit() and 1 <= int(s) <= len(nodes):
            return nodes[int(s) - 1]
        print("Invalid number. Please try again.")


def _interactive() -> bool:
    return bool(sys.stdin and sys.stdin.isatty())


def _ask_force(msg: str) -> bool:
    """Documents relevant: flaglessly --force — ask, rewrite."""
    print(msg)
    return input("Rewrite them anyway? This will use model requests (y/n): ").strip().lower() in ("y", "yes")


def cmd_synth(cfg, args):
    from . import estimate, phase2
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, cmd="synth")
        node = _pick_container(ctx, " ".join(args.name) if args.name else None)
        print(f"Phase 2 · {node.title}", flush=True)
        RESULT["container"] = node.id
        ask = _ask_force if interact.STATE["ask"] == "tty" else None

        def confirm() -> bool:  # post-test «document» — before the first reference to the model
            return args.yes or _confirm(ctx, _estimate(estimate.synth, ctx, node.id))
        return _execute(ctx, lambda: phase2.synth(ctx, node.id, force=args.force, ask_force=ask, confirm=confirm))


def cmd_check(cfg, args):
    items = []

    def item(name, ok, text):
        items.append({"name": name, "ok": bool(ok), "text": text})
        print(f"{name}: {text}", flush=True)
        return ok

    print(f"Settings: {cfg.path}")
    v = cfg.vault
    ok = item("Vault", v.exists(), f"{v} — {'found' if v.exists() else 'folder not found'}")
    if v.exists() and not (v / ".obsidian").exists():
        print("  ! This folder is not an Obsidian vault (.obsidian is missing). Open the folder as a vault in Obsidian.")
    try:
        import dulwich  # noqa
        item("Version history (git)", True, "available")
    except ImportError:
        ok &= item("Version history (git)", False, "unavailable — run Install.bat again")
    from .prompts import GARBLED_HINT
    from .schema import PROMPT_NAMES
    missing = [n for n in PROMPT_NAMES if not (cfg.program_file("prompts") / f"{n}.md").exists()]
    ok &= item("Prompts", not missing, "all present" if not missing else "Missing: " + ", ".join(missing) + "." + GARBLED_HINT)
    if v.exists():
        from .context import Ctx
        try:
            ctx = Ctx(cfg, cmd="check")
            groups = ctx.llm.models()
            roles = cfg["llm"].get("roles") or {}
            for c, prompts in groups:
                name = f"Model: {ctx.llm.label(c)}"
                if len(groups) > 1:
                    name += " — primary" if any(not roles.get(x) for x in prompts) else f" — for: {', '.join(prompts)}"
                try:
                    item(name, True, ctx.llm.ping(c))
                except UserError as e:
                    ok &= item(name, False, f"Error — {e}")
        except UserError as e:
            ok &= item("Model", False, f"Error — {e}")
            ctx = Ctx(cfg, need_llm=False)
        try:
            t = time.time()
            vec = ctx.emb.embed(["check-in"])
            item("Embeddings", True, f"{ctx.emb.fingerprint}, vector dimensions {vec.shape[1]}, {time.time() - t:.1f} s")
            stored = ctx.vs.meta.get("model")
            if stored and stored != ctx.emb.fingerprint:
                print(f"  ! vectors are calculated by another model ({stored}) — next phase 1 they will be recalculated")
        except UserError as e:
            ok &= item("Embeddings", False, f"Error — {e}")
    print("All checks passed." if ok else "There are problems; see above.")
    RESULT.update({"check": items, "title": "All checks passed" if ok else "Problems found"})
    return 0 if ok else 1


def _llama_params(args) -> dict | None:
    if not getattr(args, "params_json", None):
        return None
    raw = sys.stdin.read() if args.params_json == "-" else Path(args.params_json).read_text(encoding="utf-8-sig")
    try:
        obj = json.loads(raw or "{}")
    except ValueError as e:
        raise UserError(f"Invalid launch parameters: {e}")
    if not isinstance(obj, dict):
        raise UserError("Launch parameters must be a JSON object.")
    return obj


def _llama_status_text(st: dict) -> list[str]:
    from . import llama as L
    m, srv = st["model"], st["server"]
    lines = [f"Model: {m['title']} — " + ("downloaded" if m["exists"] else
             f"not downloaded ({L._size_text(m['size'])})" + (f", downloaded so far: {L._size_text(m['partial'])}" if m["partial"] else ""))
             + f" ({m['dir']})"]
    b = st["builds"]
    lines.append("llama.cpp: " + (", ".join(f"{L.BUILD_TITLES[k]} {v['tag']}".strip() for k, v in b.items()) if b else
                                  "not downloaded" + (f" (available on this computer: {st['system']})" if st.get("system") else "")))
    if srv.get("running"):
        p = srv.get("params") or {}
        lines.append(f"Server: running — {srv['url']}, {L.DEVICES.get(p.get('device'), '?')}, process {srv['pid']}"
                     + (", loading the model" if srv.get("health") == "loading" else
                        ", not responding" if srv.get("health") is None else ""))
    else:
        lines.append("Server: not running" + (" — starts automatically when needed" if st["params"].get("autostart") and
                                             st["configured"] and m["exists"] else ""))
    if not st["configured"]:
        lines.append("  ! The configured embeddings address points elsewhere; llama start will set it to this server.")
    return lines


def cmd_llama(cfg, args):
    """Your own model of e-mailing on llama.cpp: status | start | stop | download (plug-in — «Run the model…»)."""
    from . import llama as L
    act = args.action
    if act == "status":
        st = L.status(cfg, with_hw=args.hw)
        RESULT["llama"] = st
        if not args.json:
            print("\n".join(_llama_status_text(st)))
        RESULT["title"] = "The server is working." if st["server"].get("running") else "Server not running"
        return 0
    if act == "stop":
        r = L.stop_server(cfg)
        print("The server of the embedding model stopped." if r["stopped"] else "The embedding model server is not running.")
        RESULT.update({"title": "Server stopped" if r["stopped"] else "Server not running", "llama": L.status(cfg)})
        return 0
    over = _llama_params(args)
    p = L.params(cfg, over)
    pl = L.plan(cfg, p)
    if pl["download"] and not args.yes and interact.STATE["ask"] == "tty":
        what = "; ".join(f"{i['title']} — {L._size_text(i['size'])}" for i in pl["download"])
        ch = interact.ask("llama-download", "Downloading", f"Files to download: {what}. Download?", ["Download", "Cancel"], default=1)
        if ch != 0:
            return _cancelled()
    if act == "download":
        stop = cfg.vault / ".system" / "stop" if cfg.vault.exists() else None
        L.ensure_model(cfg, p, stop)
        build, exe = L.choose_build(cfg, p, L.hardware(cores=False))
        if exe is None:
            L.ensure_build(cfg, build, stop)
        print("Model and llama.cpp downloaded. To start the model, open Settings → Second Brain → Models → Start model… in Obsidian.")
        RESULT.update({"title": "Downloaded.", "llama": L.status(cfg)})
        return 0
    res = L.start(cfg, over, by="plugin" if args.json else "cli")
    RESULT.update({"title": "The server is already working." if res.get("already") else "Model running.", "server": res,
                   "llama": L.status(cfg)})
    return 0


def cmd_pull_embeddings(cfg, args):
    """Do v2.7 — download Ollama; now — download your model and llama.cpp (how «llama download»)."""
    args.action, args.params_json, args.hw = "download", None, False
    args.yes = getattr(args, "yes", False)
    return cmd_llama(cfg, args)

def cmd_status(cfg, args):
    ctx = _ctx(cfg, need_llm=False)
    w = ctx.w
    st = w.state
    stages = {}
    for eid, s in st["entity_stage"].items():
        if eid in w.entities:
            stages[s] = stages.get(s, 0) + 1
    items = {}
    for it in st["items"].values():
        items[it.get("stage")] = items.get(it.get("stage"), 0) + 1
    print(f"Vault: {cfg.vault}")
    print(f"Containers: {len(w.nodes)}; entries: {len(w.entities)}; documents: {len(w.products)}")
    names = {"done": "processed", "quarantine_wait": "wait (quarantine)", "quarantine": "quarantine",
             "classified": "line up", "asked": "line up", "compacted": "line up", "embedded": "line up"}
    agg = {}
    for k, v in stages.items():
        agg[names.get(k, k)] = agg.get(names.get(k, k), 0) + v
    if agg:
        print("Entries: " + ", ".join(f"{k} — {v}" for k, v in agg.items()))
    waiting = {"await_structure": "pending approval of the structure", "await_mode": "waiting for a response", "ready": "ready",
               "new": "wait for the draft structure"}
    wi = [f"{waiting[k]} — {v}" for k, v in items.items() if k in waiting]
    if wi:
        print("Files: " + ", ".join(wi))
    if st["dirty"]:
        print("Synthesis bases for reassembly: " + ", ".join(w.nodes[c].title for c in st["dirty"] if c in w.nodes))
    print(f"Open questions: {len(ctx.q.open)}")
    if st["structure"].get("pending"):
        print("Draft structure awaits approval: _structure (draft).md")
    pend = (U.read_json(w.p.webchat_index, None) or {}).get("pending") or {}
    if pend:
        print(f"Manual mode: pending response to requests _web-chat — {len(pend)}")
    new = list(w.p.staging.rglob("*.txt")) + list(w.p.staging.rglob("*.md"))
    if new:
        print(f"Files in _staging: {len(new)}")
    from .usage import print_summary
    print_summary(cfg, w.p.usage)
    return 0


def cmd_usage(cfg, args):
    """Expenditure by model (journal .system/usage.jsonl); --reprice — recalculate."""
    from . import usage as US
    from .vault import World
    path = World(cfg).p.usage
    if args.reprice:
        with RunLock(_lock_path(cfg)):
            n = US.reprice(cfg, path, args.reprice)
        print(f"Costs recalculated at current prices: {n} requests." if n else "Nothing to recalculate; costs have not changed.")
        RESULT["repriced"] = n
    s = US.print_summary(cfg, path)
    RESULT.update({"usage": s, "title": "Expenses"})
    return 0


def cmd_estimate(cfg, args):
    """Evaluation of a launch without a launch: modelling, time, cost."""
    from . import estimate as ES
    from . import ondemand
    ctx = _ctx(cfg, need_llm=False)
    name = " ".join(args.name) if args.name else None
    if args.what == "run":
        e = ES.run(ctx)
    elif args.what == "synth":
        node = _pick_container(ctx, name)
        e = ES.synth(ctx, node.id)
    else:
        node = _pick_container(ctx, name) if name else None
        e = ES.revalidate(ctx, len(ondemand.revalidate_queue(ctx, node.id if node else None)))
    print(f"Evaluation: {e['title']}")
    for ln in e["lines"]:
        print("  " + ln)
    print("This is a rough estimate; the exact number of entries will be known during processing."
          + (" Estimates are based on past runs." if e["basis"] == "history" else " There are too few past runs, so default averages are used."))
    RESULT.update({"estimate": e, "title": "Evaluation", "over": ES.over(cfg, e)})
    return 0


def _ask_revalidate_target(ctx):
    """Choices for Revalidation in Consolidation: container number 0 — record."""
    w = ctx.w
    nodes = sorted(w.nodes.values(), key=lambda x: (w.path_key(x).lower()))
    print("What should be revalidated?")
    print("    0. All entries.")
    for i, n in enumerate(nodes, 1):
        print(f"  {i:>3}. {'   ' * w.depth(n)}{n.title}")
    while True:
        s = input("Number (leave empty to cancel): ").strip()
        if not s:
            raise UserError("Cancelled.")
        if s == "0":
            return None
        if s.isdigit() and 1 <= int(s) <= len(nodes):
            return nodes[int(s) - 1]
        print("Invalid number. Please try again.")


def cmd_revalidate(cfg, args):
    from . import estimate, ondemand
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, cmd="revalidate")
        node = None
        if args.name:
            node = _pick_container(ctx, " ".join(args.name))
        elif args.ask and interact.STATE["ask"] == "tty":
            node = _ask_revalidate_target(ctx)
        queue = ondemand.revalidate_queue(ctx, node.id if node else None)
        resume = ctx.w.state.get("revalidation", {}).get("queue")
        n = len(resume) if resume and ctx.w.state["revalidation"].get("target") == (node.id if node else "*") else len(queue)
        e = _estimate(estimate.revalidate, ctx, n)
        RESULT.update({"count": n, "container": node.id if node else None})
        if e:
            RESULT["estimate"] = e
        what = "«" + node.title + "»" if node else "record"
        print(f"Revalidation {what}: {n} entries; approximately the same number of model requests.")
        if args.count:
            RESULT["title"] = f"Recheck notes: {n}"
            return 0
        if not n:
            print("There is nothing to revalidate.")
            RESULT["title"] = "There is nothing to revalidate."
            return 0
        if not args.yes:
            if not interact.can_ask():
                raise UserError("Revalidation uses model requests. Confirm the run with --yes.")
            if not _confirm(ctx, e, always=True, fallback=[f"Records.: {n} — same number of references to the model"]):
                return _cancelled()
        return _execute(ctx, lambda: ondemand.revalidate(ctx, node.id if node else None, queue))


def cmd_patterns(cfg, args):
    from . import ondemand
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, cmd="patterns")
        return _execute(ctx, lambda: ondemand.patterns(ctx))


# ---------- plugin ----------
def cmd_snapshot(cfg, args):
    """Status shot for the plugin (.system/ui.json): without reference to the model and without changes in the storage."""
    from .snapshot import write
    ctx = _ctx(cfg, need_llm=False)
    data = write(ctx)
    RESULT.update({"title": "Updated image", "questions": data["status"]["questions"],
                   "warnings": data["warnings"]})
    print(f"Snapshot updated: {data['status']['containers']} containers, {data['status']['questions']} questions.")
    return 0


def cmd_answer(cfg, args):
    """Answer to the question from the plugin — apply immediately (answer open-questions.md phase-start 1)."""
    from . import answers
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, need_llm=False, cmd="answer")
        q = ctx.q.open.get(args.qid)
        if q is None:
            raise UserError(f"Question {args.qid} is no longer open. Refresh the list.")
        idx = args.option
        if idx is not None and not 0 <= idx < len(q.get("options") or []):
            raise UserError(f"Question {args.qid} has no option {idx + 1}.")
        text = (args.text or "").strip()
        if idx is None and not text:
            raise UserError("Choose an option or write an answer.")
        ctx.q.injected[args.qid] = (idx, text, None)
        q["note"] = None

        def go():
            answers.process(ctx)
        code = _execute(ctx, go)
        left = ctx.q.open.get(args.qid)
        RESULT.update({"qid": args.qid, "accepted": left is None, "note": left.get("note") if left else None})
        if left is not None:
            print(f"Answer not accepted: {left.get('note') or 'The program failed to apply it.'}")
            return 1
        print(f"Answer {args.qid} accepted.")
        return code


def cmd_advise(cfg, args):
    """Model advice on container thresholds: It doesnt change anything. — the value applied by the user."""
    from . import tuning
    with RunLock(_lock_path(cfg)):
        ctx = _ctx(cfg, cmd="advise")
        node = _pick_container(ctx, " ".join(args.name) if args.name else None, cmd="advise")
        print(f"Threshold Council · {node.title}", flush=True)
        out = {}

        def go():
            out.update(tuning.advise(ctx, node.id))
            RESULT["advice"] = out
            print(out["summary"])
            for r in out["recommendations"]:
                print(f"  {r['label']} ({r['name']}): {r['current']} → {r['value']} — {r['reasoning']}")
            if not out["recommendations"]:
                print("  No need to change thresholds.")
            print("To apply, save the selected values under Container thresholds in the plugin.")
        return _execute(ctx, go, empty="")


def cmd_settings(cfg, args):
    from . import schema as S
    if args.key:
        key = sys.stdin.readline() if not sys.stdin.isatty() else input("Key key (empty — remove): ")
        msg = S.save_key(cfg, args.key, key)
        print(msg)
        RESULT["title"] = msg
    elif args.set_json:
        raw = sys.stdin.read() if args.set_json == "-" else Path(args.set_json).read_text(encoding="utf-8-sig")
        try:
            patch = json.loads(raw or "{}")
        except ValueError as e:
            raise UserError(f"Could not parse settings changes: {e}")
        if not isinstance(patch, dict):
            raise UserError("Settings changes must be a JSON object.")
        S.apply_patch(cfg, patch)
        print(f"Settings saved: {cfg.path}")
        RESULT["title"] = "Settings saved"
    from . import profiles as PR
    from .config import DEFAULTS
    RESULT["settings"] = {"values": {k: v for k, v in cfg.data.items()}, "schema": S.SCHEMA, "keys": S.key_status(cfg),
                          "path": str(cfg.path), "program_dir": str(cfg.program_dir), "prompts_dir": str(cfg.program_file("prompts")),
                          "prompts": S.PROMPT_NAMES, "version": __version__, "tabs": S.TABS, "update_repo": _update_repo(),
                          "profile_fields": S.PROFILE_FIELDS, "profile_defaults": PR.KIND_DEFAULTS, "modes": S.MODE_CHOICES,
                          "defaults": DEFAULTS}
    if not args.key and not args.set_json and not args.json:
        print(f"Settings: {cfg.path}")
    return 0


def _update_repo() -> str:
    from .updater import repo_link
    return repo_link()


def _cleanup_legacy(cfg):
    """After updating from version to 2.6 (The updater didnt know about the cleaning.) — remove .bat-file."""
    try:
        from . import install as I
        if any((cfg.program_dir / n).is_file() for n in I.LEGACY_FILES):
            I.remove_legacy(cfg.program_dir)
    except OSError:
        pass


def _remember_vault(cfg, vault: Path):
    """Write in settings.yaml vault-box (to run a program from the command line)."""
    try:
        if cfg.path and cfg.vault.resolve() != vault.resolve():
            from .schema import apply_patch
            apply_patch(cfg, {"vault": vault.as_posix()})
            print(f"Vault path saved in settings.yaml: {vault.as_posix()}")
    except (UserError, OSError) as e:
        print(f"  ! {e}")


def cmd_install_plugin(cfg, args):
    """Only copy the plugin to <storage>/.obsidian/plugins/vtoroy-mozg and turn it on."""
    from . import install as I
    ask = _interactive() and not args.json
    if args.path:
        vault = Path(" ".join(args.path).strip().strip('"'))
    else:
        vault = I.choose_vault(cfg.vault if I.is_vault(cfg.vault) else None, ask)
    dest = I.install_plugin(vault)
    _remember_vault(cfg, vault)
    print(f"Plugin installed: {dest}")
    print("Restart Obsidian. If prompted, select “Trust author and enable plugins”.")
    print("If the plugin does not appear, open Settings → Community plugins, turn off Restricted Mode, and enable Second Brain.")
    RESULT.update({"title": "Plugin installed", "path": str(dest)})
    return 0


def _pause(text: str) -> None:
    try:
        input(text)
    except EOFError:
        pass


def _setup_llama(cfg, ask: bool) -> None:
    from . import llama as L
    c = cfg["embeddings"]
    p = L.raw_params(cfg)
    if c.get("mode") != "local" or not L.is_our_url(c.get("base_url"), p.get("port")):
        return
    p = L.params(cfg)
    if L.model_file(cfg, p).is_file():
        return
    hw = L.hardware(cores=False)
    pl = L.plan(cfg, p, hw)
    print()
    print(f"To find similar thoughts, the program needs the {L.MODEL['title']} embedding model and llama.cpp to run it. "
          "You can download them now or later in Obsidian (Settings → Second Brain → Models → “Start model…”; "
          "choose CPU or GPU there).")
    for it in pl["download"]:
        print(f"  • {it['title']} — {L._size_text(it['size'])}")
    ram = hw.get("ram_gb")
    if ram and round(ram) < L.MIN_RAM_GB and not hw.get("gpus"):
        print(f"  ! Running on CPU requires at least {L.MIN_RAM_GB} GB RAM; this computer has "
              f"{round(ram)} GB")
    yes = False
    if ask:
        try:
            yes = input("Download now? (y/n): ").strip().lower() in ("y", "yes")
        except EOFError:
            yes = False
    if not yes:
        print("Skipped. You can download the model later from Obsidian.")
        return
    L.ensure_model(cfg, p)
    build, exe = L.choose_build(cfg, p, hw)
    if exe is None:
        L.ensure_build(cfg, build)
    print("Download complete. Start the model in Obsidian under Settings → Second Brain → Models → Start model….")


def cmd_setup(cfg, args):
    """Install «one-on-one» postlibrary Python (launcher Install.bat): cleaning .bat-file,
    plugin Obsidian, vault-folder settings.yaml, embedding (willingly), open Obsidian."""
    from . import install as I
    ask = _interactive() and not args.json
    removed = I.remove_legacy(cfg.program_dir)
    if removed:
        print("Removed legacy files (these actions are now available in the plugin): " + ", ".join(removed))
    # 1. storage
    if args.path:
        vault = Path(" ".join(args.path).strip().strip('"'))
    else:
        vault = I.choose_vault(cfg.vault if I.is_vault(cfg.vault) else None, ask)
    running = I.obsidian_running()
    if running and ask:
        print()
        print("Obsidian is open. Close its windows so the plugin can be updated, then reopen it.")
        _pause("After closing Obsidian, press Enter… ")
        running = I.obsidian_running()
    dest = I.install_plugin(vault)
    _remember_vault(cfg, vault)
    print(f"Plugin installed: {dest}")
    RESULT.update({"title": "Install completed", "path": str(dest), "vault": str(vault), "removed": removed})
    # 2. jelly-fish (if — on this computer): download, willingly
    try:
        _setup_llama(cfg, ask)
    except UserError as e:
        print(f"  ! {e}")
        print("You can download and start the model later under Settings → Second Brain → Models → Start model….")
    # 3. open Obsidian
    print()
    if not running and I.open_obsidian(vault):
        print("Opening Obsidian…")
    print("Next steps in Obsidian:")
    if running:
        print("  0. Restart Obsidian to load the plugin.")
    print("  1. If prompted, choose “Trust author and enable plugins”. The Second Brain panel will appear on the right.")
    print("  2. Under Settings → Second Brain → Models, enter an API key, choose a model, and select Check connection.")
    print("  3. Put notes in the vault’s _staging folder and select Start Phase 1 in the panel.")
    return 0


def cmd_update(cfg, args):
    """Updating programme c GitHub: check out (--check) or download and install."""
    from . import updater
    info = updater.check(cfg)
    RESULT["update"] = {k: v for k, v in info.items() if k not in ("zip_url", "zip_accept")}
    cur, new = __version__, info.get("version") or "?"
    if not info["newer"] and not args.force:
        print(f"The latest version has been installed: {cur} (repository {info['repo']} — {new}).")
        RESULT["title"] = "Last version"
        return 0
    print(f"A new version is available: {new} (installed: {cur}) — {info['url']}")
    if info.get("notes"):
        print("What’s new:\n" + "\n".join("  " + ln for ln in info["notes"].splitlines()[:30]))
    if args.check:
        RESULT["title"] = f"Version {new} available"
        return 0
    if not args.yes:
        if not interact.can_ask():
            raise UserError("Update changes program files; confirm with --yes.")
        ch = interact.ask("update", "Program update", f"Install version {new}? Settings and keys will not be changed.",
                          ["Install", "Cancellation"], default=None)
        if ch != 0:
            return _cancelled()
    lock = RunLock(_lock_path(cfg)) if cfg.vault.exists() else None
    if lock:
        lock.__enter__()
    try:
        data = updater.download(cfg, info)
        res = updater.install_zip(cfg, data, info)
    finally:
        if lock:
            lock.__exit__()
    print(f"Version {res['version']} installed: files updated — {res['updated']}, added — {res['added']}"
          + (f", obsolete — {len(res['removed'])}" if res["removed"] else "") + ".")
    if res["plugin"]:
        print(f"The plugin in the vault was updated: {res['plugin']}")
    for n in res["notes"]:
        print(f"  • {n}")
    print("Restart Obsidian to load the new plugin." if res["plugin"] else "Ready.")
    RESULT.update({"title": f"Version installed {res['version']}", "installed": res, "restart": bool(res["plugin"]),
                   "notices": res["notes"]})
    return 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    RESULT.clear()
    p = argparse.ArgumentParser(prog="brain", description=f"Second Brain {__version__}", add_help=True)
    p.add_argument("--settings", help="path settings.yaml (default — near-program)")
    p.add_argument("--vault", help="storage folder instead of the one in settings.yaml")
    p.add_argument("--json", action="store_true", help="line-up @@RESULT {…} (plug-in)")
    p.add_argument("--ask-stdin", action="store_true", help="Questions in the middle of the launch: @@ASK, line-off JSON standard-input")
    sub = p.add_subparsers(dest="cmd")
    rn = sub.add_parser("run")
    rn.add_argument("--yes", action="store_true", help="no question before the big launch")
    s = sub.add_parser("synth")
    s.add_argument("name", nargs="*")
    s.add_argument("--force", action="store_true")
    s.add_argument("--yes", action="store_true")
    sub.add_parser("check")
    sub.add_parser("status")
    us = sub.add_parser("usage")
    us.add_argument("--reprice", help="calculate: id profile, emb (embedding) or all")
    es = sub.add_parser("estimate")
    es.add_argument("what", choices=["run", "synth", "revalidate"])
    es.add_argument("name", nargs="*")
    up = sub.add_parser("update")
    up.add_argument("--check", action="store_true", help="check for a new version")
    up.add_argument("--yes", action="store_true", help="confirm installation")
    up.add_argument("--force", action="store_true", help="install even if the version is not newer")
    r = sub.add_parser("revalidate")
    r.add_argument("name", nargs="*")
    r.add_argument("--yes", action="store_true")
    r.add_argument("--ask", action="store_true")
    r.add_argument("--count", action="store_true", help="just counting the records")
    sub.add_parser("patterns")
    lm = sub.add_parser("llama")
    lm.add_argument("action", choices=["status", "start", "stop", "download"])
    lm.add_argument("--params-json", help="launcher: file JSON or - (standard-input)")
    lm.add_argument("--hw", action="store_true", help="status: computer hardware")
    lm.add_argument("--yes", action="store_true", help="download without question")
    sub.add_parser("pull-embeddings")  # before v2.7 — download Ollama; now — same, what llama download
    sub.add_parser("snapshot")
    a = sub.add_parser("answer")
    a.add_argument("qid")
    a.add_argument("--option", type=int, help="zero-based option index")
    a.add_argument("--text")
    ad = sub.add_parser("advise")
    ad.add_argument("name", nargs="*")
    st = sub.add_parser("settings")
    st.add_argument("--set-json", help="file JSON or - (standard-input)")
    st.add_argument("--key", help="save the key from the standard input: profile:<id> | embeddings (| llm | role:<step>)")
    ip = sub.add_parser("install-plugin")
    ip.add_argument("path", nargs="*")
    su = sub.add_parser("setup")
    su.add_argument("path", nargs="*")
    args = p.parse_args(argv)
    if not args.cmd:
        print(HELP)
        return 0
    cmds = {"run": cmd_run, "synth": cmd_synth, "check": cmd_check, "status": cmd_status, "pull-embeddings": cmd_pull_embeddings,
            "llama": cmd_llama,
            "revalidate": cmd_revalidate, "patterns": cmd_patterns, "snapshot": cmd_snapshot, "answer": cmd_answer,
            "advise": cmd_advise, "settings": cmd_settings, "install-plugin": cmd_install_plugin, "usage": cmd_usage,
            "estimate": cmd_estimate, "update": cmd_update, "setup": cmd_setup}
    interact.configure(args.json, "stdin" if args.ask_stdin else ("tty" if _interactive() and not args.json else "none"))
    cfg = None
    RESULT.update({"cmd": args.cmd, "ok": False})
    code = 2
    try:
        cfg = load_config(args.settings)
        if args.vault:
            cfg.vault_override = args.vault
        if args.cmd != "setup":
            _cleanup_legacy(cfg)
        code = cmds[args.cmd](cfg, args) or 0
        RESULT["ok"] = code == 0
        return code
    except UserError as e:
        print(f"\nError: {e}")
        RESULT["error"] = str(e)
        code = 1
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        RESULT.update({"error": "Stopped.", "stopped": True})
        code = 1
        return 1
    except Exception:
        tb = traceback.format_exc()
        log = None
        try:
            if cfg is not None and cfg.vault.exists():
                log = cfg.vault / "_logs" / "mistake.log"
                U.append_text(log, f"\n===== {U.ru_datetime()} · {' '.join(sys.argv[1:])}\n{tb}")
        except Exception:
            pass
        print("\nUnexpected program error. Previously processed work was saved; restart to continue.")
        last = tb.strip().split("\n")[-1]
        print(last)
        if log:
            print(f"Details: {log}")
        RESULT["error"] = f"Unforeseen program error: {last}" + (f" Details. — into {log}" if log else "")
        code = 2
        return 2
    finally:
        RESULT["code"] = code
        if getattr(args, "json", False):
            print("@@RESULT " + json.dumps(RESULT, ensure_ascii=False, default=str), flush=True)

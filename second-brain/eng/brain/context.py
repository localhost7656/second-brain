"""Context of the run: everything, what the conveyor steps need."""
from __future__ import annotations

from . import interact
from . import util as U
from .embed import Embedder, VectorStore
from .llm import LLM
from .logs import Logs
from .questions import Questions
from .schema import CONTAINER_THRESHOLDS, container_overrides
from .usage import Meter
from .vault import World
from .versions import Versions


class Ctx:
    def __init__(self, cfg, need_llm: bool = True, cmd: str = ""):
        self.cfg = cfg
        self.th = cfg.th
        self.w = World(cfg)
        self.w.load()
        self.logs = Logs(self.w)
        self.q = Questions(self.w)
        self.notices: list[str] = []
        self.meter = Meter(cfg, self.w.p.usage, cmd, notice=self._notice_once)
        self.llm = LLM(cfg, self.w, self.logs, self.meter) if need_llm else None
        if self.llm:
            self.llm.stop_check = self.check_stop
        self.emb = Embedder(cfg, self.meter)
        self.vs = VectorStore(self.w.p.vectors)
        self.ver = Versions(self.w)
        self.stats: dict[str, int] = {}
        self.messages: list[str] = []
        self.clarifications: dict = {}
        self.elapsed = 0.0
        self.result: dict = {}          # Additional response fields for the plugin (--json)
        self._ovr: dict[str, dict] = {}
        for n in self.w.nodes.values():  # their container thresholds: run-through
            self._ovr[n.id] = container_overrides(n, self.w.warnings.append)

    # ---------- threshold (shared and their own at the container, section 10.5) ----------
    def overrides(self, cid: str) -> dict:
        if cid not in self._ovr and cid in self.w.nodes:
            self._ovr[cid] = container_overrides(self.w.nodes[cid])
        return self._ovr.get(cid, {})

    def thr(self, name: str, cid: str | None = None):
        """Threshold for a container decision: container, other than the nearest parent, common."""
        if cid and name in CONTAINER_THRESHOLDS:
            src = self.thr_source(name, cid)
            if src:
                return src[1]
        if name == "seed_dormancy_days":
            return int(self.cfg.get("seed_dormancy_days") or 90)
        return self.th[name]

    def thr_source(self, name: str, cid: str):
        """(id container, significance) — where does your threshold come from; None — common."""
        seen, cur = set(), self.w.nodes.get(cid)
        while cur is not None and cur.id not in seen:
            seen.add(cur.id)
            ov = self.overrides(cur.id)
            if name in ov:
                return cur.id, ov[name]
            cur = self.w.parent_of(cur)
        return None

    def _notice_once(self, text: str):
        if text not in self.notices:
            self.notices.append(text)

    def progress(self, stage: str, n: int, total: int, item: str = "", level: int = 0, echo: bool = True):
        """Wheres the launch? — plug-in (line «@@PROGRESS») console."""
        interact.progress(stage, n, total, item, level, echo)

    def count(self, key: str, n: int = 1):
        self.stats[key] = self.stats.get(key, 0) + n

    def say(self, text: str):
        self.messages.append(text)
        print("  " + text, flush=True)

    # ---------- «Stop.» plug-in: file .system/stop ----------
    def check_stop(self):
        f = self.w.p.system / "stop"
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass
            raise KeyboardInterrupt

    def _save(self):
        self.w.save_state()
        self.q.save()
        self.vs.save()

    def checkpoint(self):
        """Checkpoint after each step (section 11.3); check in here «Stop.»."""
        self._save()
        self.check_stop()

    def finish(self):
        self._save()
        notices = list(self.notices)
        if self.w.state["structure"].get("pending"):
            notices.insert(0, "The draft structure is waiting for inspection: [[_structure (draft)]] — Correct and mark «Structure approved».")
        pend = (U.read_json(self.w.p.webchat_index, None) or {}).get("pending") or {}
        if pend:
            notices.insert(0, f"Manual mode: waiting for answers in the folder _web-chat ({len(pend)}).")
        self.q.render(notices)
        self.w.refresh_node_blocks()
        self.w.write_css()
        self.w.save_state()
        self.ver.commit(f"run-through {U.ru_datetime()}")
        from .snapshot import write as write_snapshot
        write_snapshot(self)

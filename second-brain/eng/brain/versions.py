"""Versions of the synthesis base and products (section 11.2): mirror .system/versions steerable git (dulwich, lay down git dont)."""
from __future__ import annotations

from pathlib import Path

from . import util as U

try:
    from dulwich import porcelain
    from dulwich.repo import Repo
except ImportError:  # The program works without git, no history
    porcelain = None
    Repo = None


class Versions:
    def __init__(self, world):
        self.w = world
        self.root: Path = world.p.versions
        self.root.mkdir(parents=True, exist_ok=True)
        self._staged: list[str] = []
        self.enabled = porcelain is not None
        if self.enabled and not (self.root / ".git").exists():
            porcelain.init(str(self.root))

    @staticmethod
    def key_product(cid: str, title: str) -> str:
        return f"{cid}/{U.safe_name(title, 80)}.md"

    @staticmethod
    def key_base(cid: str) -> str:
        return f"{cid}/_synthesis.md"

    def read(self, key: str) -> str | None:
        p = self.root / key
        return p.read_text(encoding="utf-8") if p.exists() else None

    def snapshot(self, key: str, content: str):
        p = self.root / key
        if p.exists() and p.read_text(encoding="utf-8") == content:
            return
        U.atomic_write_text(p, content)
        self._staged.append(key)

    def commit(self, message: str):
        if not self._staged or not self.enabled:
            self._staged.clear()
            return
        paths = [str(self.root / k) for k in dict.fromkeys(self._staged)]
        porcelain.add(str(self.root), paths=paths)
        author = "Second Brain <brain@localhost>".encode("utf-8")
        porcelain.commit(str(self.root), message=message.encode("utf-8"), author=author, committer=author)
        self._staged.clear()

    def history(self, key: str, limit: int = 20) -> list[tuple[str, str]]:
        """[(date, message)] last-day commissions, file-affected."""
        if not self.enabled or not (self.root / ".git").exists():
            return []
        out = []
        try:
            r = Repo(str(self.root))
            for entry in r.get_walker(paths=[key.encode("utf-8")], max_entries=limit):
                c = entry.commit
                import datetime as dt
                out.append((dt.datetime.fromtimestamp(c.commit_time).isoformat(timespec="minutes"),
                            c.message.decode("utf-8", "replace").strip()))
        except Exception:
            pass
        return out

    def read_at(self, key: str, n_back: int = 1) -> str | None:
        """File contents n_back back-to-back (0 — last-committee, where the file changed)."""
        if not self.enabled or not (self.root / ".git").exists():
            return None
        try:
            r = Repo(str(self.root))
            entries = list(r.get_walker(paths=[key.encode("utf-8")], max_entries=n_back + 1))
            if len(entries) <= n_back:
                return None
            tree = r[entries[n_back].commit.tree]
            _mode, sha = tree.lookup_path(r.object_store.__getitem__, key.encode("utf-8"))
            return r[sha].data.decode("utf-8")
        except Exception:
            return None

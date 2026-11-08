"""Warehouse: folder-structure, container, essence, pool, synthesis, condition."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import util as U

COMPACT_HEADING = "## Condensed version (programmed)"
NODE_TYPES = ("project", "seed", "question")
TYPE_RU = {"project": "project", "seed": "sprout", "question": "question"}
RU_TYPE = {"project": "project", "sprout": "seed", "seed": "seed", "question": "question"}
# English status aliases accepted in container and entry frontmatter.
CONTAINER_STATUS = {"active": "active", "work": "active", "dormant": "dormant", "frozen": "dormant",
                    "sleep": "dormant", "pause": "dormant", "completed": "completed", "finished": "completed",
                    "ready": "completed"}
ENTITY_STATUS = {"outdated": "outdated", "obsolete": "outdated", "irrelevantly": "outdated", "irrelevant": "outdated",
                 "processed": "processed", "relevant": "processed", "relevantly": "processed"}
PALETTE = ["#3B82F6", "#22C55E", "#F97316", "#A855F7", "#EF4444", "#06B6D4", "#EAB308", "#EC4899", "#14B8A6", "#84CC16"]
SKIP_DIRS = {".system", ".obsidian", ".git", ".trash", "_staging", "_sources", "_web-chat", "_logs"}


def _mix(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(c + (255 - c) * factor) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


class Paths:
    def __init__(self, root: Path):
        self.root = root
        self.staging = root / "_staging"
        self.staging_archive = self.staging / "archive"
        self.quarantine = root / "_review"
        self.unsorted = root / "_unsorted"
        self.shared = root / "_shared"
        self.sources = root / "_sources"
        self.webchat = root / "_web-chat"
        self.logs = root / "_logs"
        self.open_questions = root / "open-questions.md"
        self.draft = root / "_structure (draft).md"
        self.system = root / ".system"
        self.data = self.system / "data"
        self.pools = self.data / "pools"
        self.bases = self.data / "bases"
        self.state = self.system / "state.json"
        self.questions = self.system / "questions.json"
        self.vectors = self.system / "vectors"
        self.versions = self.system / "versions"
        self.reflection = self.system / "reflection.jsonl"
        self.usage = self.system / "usage.jsonl"
        self.webchat_index = self.system / "webchat.json"
        self.css = root / ".obsidian" / "snippets" / "vtoroy-mozg.css"

    def ensure(self):
        for p in (self.staging, self.staging_archive, self.quarantine, self.unsorted, self.shared,
                  self.sources, self.webchat, self.logs, self.pools, self.bases, self.vectors):
            p.mkdir(parents=True, exist_ok=True)


class Node:
    """Container (project-graph), section 16.1."""

    def __init__(self, path: Path, fm: dict, body: str = ""):
        self.path = path
        self.fm = fm
        self.body = body

    id = property(lambda self: self.fm["id"])
    title = property(lambda self: self.path.stem)
    folder = property(lambda self: self.path.parent)
    type = property(lambda self: RU_TYPE.get(str(self.fm.get("type") or "project").strip().lower(), "project"))
    description = property(lambda self: self.fm.get("description") or "")
    status = property(lambda self: CONTAINER_STATUS.get(str(self.fm.get("container_status") or "active").strip().lower(), "active"))

    def __repr__(self):
        return f"<Node {self.id} {self.title}>"


class Entity:
    """The essence inside the container, section 16.2."""

    def __init__(self, path: Path, fm: dict, text: str, compact: str | None = None):
        self.path = path
        self.fm = fm
        self.text = text
        self.compact = compact

    id = property(lambda self: self.fm["id"])
    title = property(lambda self: self.path.stem)
    container_id = property(lambda self: self.fm.get("container_id"))
    created = property(lambda self: str(self.fm.get("created") or ""))

    @property
    def also_in_ids(self) -> list:
        return list(self.fm.get("also_in_ids") or [])

    @property
    def work_text(self) -> str:
        return self.compact or self.text

    def __repr__(self):
        return f"<Entity {self.id} {self.title}>"


def parse_entity_body(body: str) -> tuple[str, str | None]:
    if COMPACT_HEADING in body:
        a, b = body.split(COMPACT_HEADING, 1)
        return a.strip("\n"), b.strip("\n") or None
    return body.strip("\n"), None


class World:
    """The entire state of the storage in memory at the time of running."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.p = Paths(cfg.vault)
        self.nodes: dict[str, Node] = {}
        self.entities: dict[str, Entity] = {}
        self.products: list[tuple[Path, dict, str]] = []
        self._pools: dict[str, dict] = {}
        self._bases: dict[str, dict] = {}
        self.state: dict = {}
        self.warnings: list[str] = []
        self._taken_stems: set[str] = set()

    # ---------- loading ----------
    def load(self):
        self.p.ensure()
        self.state = U.read_json(self.p.state, None) or {}
        st = self.state
        st.setdefault("counters", {})
        st.setdefault("items", {})          # input
        st.setdefault("entity_stage", {})   # conveyorage
        st.setdefault("dirty", {})          # container, base to be reassembled
        st.setdefault("structure", {"pending": False, "approved_once": False})
        st.setdefault("text_hash", {})      # textualization
        st.setdefault("cls", {})            # substantively
        st.setdefault("new_aspects", {})    # cid -> id aspects, come-from-the-last assembly
        st.setdefault("restore_requests", {})
        self.nodes.clear(); self.entities.clear(); self.products.clear()
        self.adoptable = []                 # container-card, manually (without id)
        for md in self._walk_md():
            try:
                fm, body = U.read_md(md)
            except OSError as e:
                self.warnings.append(f"Could not read {md}: {e}")
                continue
            t = fm.get("type")
            nt = RU_TYPE.get(str(t or "").strip().lower())
            if nt in NODE_TYPES and fm.get("id"):
                if fm["id"] in self.nodes:
                    self.warnings.append(f"Two containers with one id {fm['id']}: {md}")
                    continue
                self.nodes[fm["id"]] = Node(md, fm, body)
            elif nt in NODE_TYPES:
                self.adoptable.append((md, fm, body))
            elif t == "entity" and fm.get("id"):
                text, compact = parse_entity_body(body)
                self.entities[fm["id"]] = Entity(md, fm, text, compact)
                self._taken_stems.add(md.stem.lower())
            elif t == "product":
                self.products.append((md, fm, body))
        self._bump_counters()

    def _walk_md(self):
        root = self.p.root
        for p in root.rglob("*.md"):
            rel = p.relative_to(root).parts
            if rel and rel[0] in SKIP_DIRS:
                continue
            if any(part.startswith(".") for part in rel[:-1]):
                continue
            if p.name.startswith(".tmp-"):
                continue
            yield p

    def _bump_counters(self):
        c = self.state["counters"]
        def bump(prefix, ids):
            mx = 0
            for i in ids:
                m = re.match(rf"^{prefix}(\d+)$", str(i))
                if m:
                    mx = max(mx, int(m.group(1)))
            c[prefix] = max(c.get(prefix, 0), mx)
        bump("k", self.nodes)
        bump("e", self.entities)
        ids_a, ids_c = [], []
        for f in self.p.pools.glob("*.json"):
            pool = U.read_json(f, {}) or {}
            ids_a += list((pool.get("aspects") or {}).keys())
            ids_c += list((pool.get("composites") or {}).keys())
        bump("a", ids_a)
        bump("c", ids_c)
        bump("i", self.state["items"])

    def next_id(self, prefix: str, width: int = 0) -> str:
        c = self.state["counters"]
        c[prefix] = c.get(prefix, 0) + 1
        n = c[prefix]
        return f"{prefix}{n:0{width}d}" if width else f"{prefix}{n}"

    def save_state(self):
        U.write_json(self.p.state, self.state)

    # ---------- container ----------
    def node_by_title(self, title: str | None) -> Node | None:
        t = (U.unlink(title) or "").strip().lower()
        if not t:
            return None
        for n in self.nodes.values():
            if n.title.lower() == t:
                return n
        return None

    def resolve_container(self, ref) -> Node | None:
        """id name (including [[reference]])."""
        if ref is None:
            return None
        r = str(ref).strip()
        if r in self.nodes:
            return self.nodes[r]
        return self.node_by_title(r)

    def parent_of(self, node: Node) -> Node | None:
        pid = node.fm.get("parent_id")
        if pid and pid in self.nodes:
            return self.nodes[pid]
        return None

    def children(self, cid: str | None) -> list[Node]:
        return sorted([n for n in self.nodes.values() if n.fm.get("parent_id") == cid], key=lambda n: n.title.lower())

    def depth(self, node: Node) -> int:
        d, seen, cur = 0, set(), node
        while cur is not None and cur.id not in seen:
            seen.add(cur.id)
            cur = self.parent_of(cur)
            d += 1 if cur else 0
        return d

    def expected_folder(self, node_id: str | None, _seen=None) -> Path:
        if node_id is None:
            return self.p.root
        seen = _seen or set()
        if node_id in seen:  # parental cycle — put it on the top level
            return self.p.root
        seen.add(node_id)
        node = self.nodes[node_id]
        pid = node.fm.get("parent_id")
        base = self.expected_folder(pid, seen) if pid in self.nodes else self.p.root
        return base / node.title

    def _unique_title(self, title: str) -> str:
        base = U.safe_name(title, 60)
        t, n = base, 2
        while self.node_by_title(t) is not None or t.lower() in self._taken_stems:
            t = f"{base} ({n})"
            n += 1
        return t

    def _color_for(self, parent: Node | None) -> str:
        if parent is None:
            top = [n for n in self.nodes.values() if not n.fm.get("parent_id")]
            return PALETTE[len(top) % len(PALETTE)]
        base = parent.fm.get("color") or PALETTE[0]
        k = len(self.children(parent.id))
        return _mix(base, min(0.25 + 0.08 * k, 0.6))

    def create_node(self, title: str, ntype: str = "project", parent_id: str | None = None,
                    description: str = "", applies_to: list | None = None, created: str | None = None) -> Node:
        ntype = RU_TYPE.get(str(ntype).lower(), "project")
        title = self._unique_title(title)
        parent = self.nodes.get(parent_id) if parent_id else None
        nid = self.next_id("k", 3)
        fm = {
            "type": ntype,
            "id": nid,
            "color": self._color_for(parent),
            "parent": U.link(parent.title) if parent else None,
            "parent_id": parent.id if parent else None,
            "applies_to": [],
            "applies_to_ids": [],
            "container_status": "active",
            "description": description or "",
            "created": created or U.today(),
            "last_modified": U.today(),
            "needs_review": False,
            "review_reason": None,
        }
        folder = (self.nodes[parent.id].folder if parent else self.p.root) / title
        folder.mkdir(parents=True, exist_ok=True)
        node = Node(folder / f"{title}.md", fm, "")
        self.nodes[nid] = node
        self.set_applies_to(node, applies_to or [])
        self.save_node(node)
        return node

    def set_applies_to(self, node: Node, refs: list):
        ids = []
        for r in refs:
            n = self.resolve_container(r)
            if n and n.id != node.id and n.id not in ids:
                ids.append(n.id)
        node.fm["applies_to_ids"] = ids
        node.fm["applies_to"] = [U.link(self.nodes[i].title) for i in ids]

    def save_node(self, node: Node):
        p = self.parent_of(node)
        node.fm["parent"] = U.link(p.title) if p else None
        node.fm["applies_to"] = [U.link(self.nodes[i].title) for i in node.fm.get("applies_to_ids") or [] if i in self.nodes]
        body = node.body if node.body.strip() else f"\n{node.description}\n"
        node.body = body
        U.write_md(node.path, node.fm, body)

    def rename_node(self, node: Node, new_title: str) -> str:
        new_title = U.safe_name(new_title, 60)
        if new_title == node.title:
            return new_title
        if self.node_by_title(new_title) is not None:
            new_title = self._unique_title(new_title)
        old_folder = node.folder
        new_folder = old_folder.parent / new_title
        if new_folder.exists():
            new_title = self._unique_title(new_title)
            new_folder = old_folder.parent / new_title
        old_file_name = node.path.name
        U.retry_fs(shutil.move, str(old_folder), str(new_folder))
        old_file = new_folder / old_file_name
        new_file = new_folder / f"{new_title}.md"
        U.retry_fs(old_file.rename, new_file)
        self._relocate_under(old_folder, new_folder)
        node.path = new_file
        self.save_node(node)
        self.refresh_links()
        return new_title

    def move_node(self, node: Node, new_parent_id: str | None):
        """Change the parent and move the folder."""
        if new_parent_id == node.id:
            return
        cur = self.nodes.get(new_parent_id) if new_parent_id else None
        seen = set()
        while cur is not None:  # Dont let it cycle.
            if cur.id == node.id:
                self.warnings.append(f"Cannot place “{node.title}” inside its own descendant; the parent was not changed.")
                return
            if cur.id in seen:
                break
            seen.add(cur.id)
            cur = self.parent_of(cur)
        node.fm["parent_id"] = new_parent_id
        self.normalize_folders()
        self.save_node(node)

    def normalize_folders(self):
        """Container folders are nested by the main parent (section 3.2)."""
        changed = True
        guard = 0
        while changed and guard < 50:
            changed, guard = False, guard + 1
            for node in sorted(self.nodes.values(), key=lambda n: self.depth(n)):
                exp = self.expected_folder(node.id)
                if node.folder.resolve() != exp.resolve():
                    if exp.exists():
                        self.warnings.append(f"Could not move “{node.title}”: folder {exp} already exists.")
                        continue
                    exp.parent.mkdir(parents=True, exist_ok=True)
                    old = node.folder
                    U.retry_fs(shutil.move, str(old), str(exp))
                    self._relocate_under(old, exp)
                    changed = True

    def _relocate_under(self, old: Path, new: Path):
        """After transferring the folder, update the paths of the downloaded objects."""
        def fix(p: Path) -> Path:
            try:
                rel = p.relative_to(old)
            except ValueError:
                return p
            return new / rel
        for n in self.nodes.values():
            n.path = fix(n.path)
        for e in self.entities.values():
            e.path = fix(e.path)
        self.products = [(fix(p), fm, b) for p, fm, b in self.products]

    def refresh_links(self):
        """Rewrite [[reference]] into YAML by current-name (post-naming)."""
        for n in self.nodes.values():
            p = self.parent_of(n)
            want_parent = U.link(p.title) if p else None
            want_apply = [U.link(self.nodes[i].title) for i in n.fm.get("applies_to_ids") or [] if i in self.nodes]
            if n.fm.get("parent") != want_parent or (n.fm.get("applies_to") or []) != want_apply:
                self.save_node(n)
        for e in self.entities.values():
            c = self.nodes.get(e.container_id)
            want = U.link(c.title) if c else None
            want_also = [U.link(self.nodes[i].title) for i in e.also_in_ids if i in self.nodes]
            if e.fm.get("container") != want or (e.fm.get("also_in") or []) != want_also:
                self.save_entity(e)

    def path_key(self, node: Node) -> str:
        return node.folder.relative_to(self.p.root).as_posix()

    def adopt_node(self, md: Path, fm: dict, body: str) -> Node | None:
        """Container, manual: note type (project/sprout/question), without id.
        The program gives her id and the missing fields; a note without its folder puts in a folder with its name.
        Parent — field parent, If hes not. — container, in whose file is the note."""
        name = md.stem
        if U.safe_name(name, 60) != name:
            self.warnings.append(f"Note “{name}” could not become a container: its name is longer than 60 characters or contains invalid characters.")
            return None
        if self.node_by_title(name) is not None:
            self.warnings.append(f"Note “{md.relative_to(self.p.root).as_posix()}” could not become a container: "
                                 f"container “{name}” already exists. Rename the note.")
            return None
        root = self.p.root.resolve()
        folders = {n.folder.resolve(): n for n in self.nodes.values()}
        here = md.parent.resolve()
        own = here != root and md.parent.name.lower() == name.lower() and here not in folders
        parent = None
        ref = U.unlink(fm.get("parent"))
        if ref:
            parent = self.node_by_title(ref)
            if parent is None:
                self.warnings.append(f"The new container [[{name}]] refers to parent “{ref}”, which does not exist; the container is at the top level.")
        else:
            q = here.parent if own else here
            while q != root and q not in folders and root in q.parents:
                q = q.parent
            parent = folders.get(q)
        if own:
            path = md
        else:
            folder = md.parent / name
            if folder.exists():
                self.warnings.append(f"Note “{name}” could not become a container: a folder with that name already exists.")
                return None
            folder.mkdir(parents=True)
            path = folder / md.name
            U.retry_fs(shutil.move, str(md), str(path))
        desc = str(fm.get("description") or "").strip()
        if not desc:
            first = next((x.strip() for x in body.split("\n\n") if x.strip() and not x.strip().startswith("<!--")), "")
            desc = re.sub(r"\s+", " ", first)[:200]
        new = {
            "type": RU_TYPE.get(str(fm.get("type")).strip().lower(), "project"),
            "id": self.next_id("k", 3),
            "color": fm.get("color") or self._color_for(parent),
            "parent": U.link(parent.title) if parent else None,
            "parent_id": parent.id if parent else None,
            "applies_to": [], "applies_to_ids": [],
            "container_status": fm.get("container_status") or "active",
            "description": desc,
            "created": str(fm.get("created") or U.today()),
            "last_modified": U.today(),
            "needs_review": False, "review_reason": None,
        }
        for k, v in fm.items():
            new.setdefault(k, v)
        node = Node(path, new, body)
        self.nodes[new["id"]] = node
        self.set_applies_to(node, [U.unlink(v) for v in U.as_list(fm.get("applies_to")) if U.unlink(v)])
        self.save_node(node)
        return node

    # ---------- essence ----------
    def entity_folder(self, e_fm: dict) -> Path:
        if e_fm.get("quarantine"):
            return self.p.quarantine
        cid = e_fm.get("container_id")
        if not cid:
            return self.p.unsorted
        if e_fm.get("also_in_ids"):
            return self.p.shared
        node = self.nodes.get(cid)
        if node is None:
            return self.p.unsorted
        return node.folder / "_record"

    def _free_stem(self, folder: Path, stem: str) -> Path:
        cand, n = stem, 2
        while cand.lower() in self._taken_stems or (folder / f"{cand}.md").exists():
            cand = f"{stem} ({n})"
            n += 1
        return folder / f"{cand}.md"

    def create_entity(self, fm: dict, text: str, title_hint: str) -> Entity:
        eid = self.next_id("e", 5)
        fm = dict(fm)
        fm["id"] = eid
        folder = self.entity_folder(fm)
        folder.mkdir(parents=True, exist_ok=True)
        path = self._free_stem(folder, U.safe_name(title_hint, 70))
        self._taken_stems.add(path.stem.lower())
        e = Entity(path, fm, text)
        self.entities[eid] = e
        self.save_entity(e)
        return e

    def save_entity(self, e: Entity):
        c = self.nodes.get(e.container_id)
        e.fm["container"] = U.link(c.title) if c else None
        e.fm["also_in"] = [U.link(self.nodes[i].title) for i in e.also_in_ids if i in self.nodes]
        e.fm["shared"] = bool(e.also_in_ids)
        want = self.entity_folder(e.fm)
        if e.path.parent.resolve() != want.resolve():
            want.mkdir(parents=True, exist_ok=True)
            self._taken_stems.discard(e.path.stem.lower())
            newp = self._free_stem(want, e.path.stem)
            if e.path.exists():
                U.retry_fs(shutil.move, str(e.path), str(newp))
            e.path = newp
            self._taken_stems.add(newp.stem.lower())
        body = "\n" + e.text.strip("\n") + "\n"
        if e.compact:
            body += f"\n{COMPACT_HEADING}\n\n{e.compact.strip()}\n"
        U.write_md(e.path, e.fm, body)

    def entities_of(self, cid: str, include_shared: bool = True) -> list[Entity]:
        out = []
        for e in self.entities.values():
            if e.container_id == cid or (include_shared and cid in e.also_in_ids):
                out.append(e)
        return out

    # ---------- pool of aspects and base of synthesis ----------
    def pool(self, cid: str) -> dict:
        if cid not in self._pools:
            pool = U.read_json(self.p.pools / f"{cid}.json", None)
            if not pool:
                pool = {"container_id": cid, "aspects": {}, "composites": {}, "conflicts": [], "rejected": []}
            for k in ("aspects", "composites"):
                pool.setdefault(k, {})
            for k in ("conflicts", "rejected"):
                pool.setdefault(k, [])
            self._pools[cid] = pool
        return self._pools[cid]

    def save_pool(self, cid: str):
        U.write_json(self.p.pools / f"{cid}.json", self.pool(cid))
        from .views import render_pool_view
        render_pool_view(self, cid)

    def base(self, cid: str) -> dict | None:
        if cid not in self._bases:
            self._bases[cid] = U.read_json(self.p.bases / f"{cid}.json", None)
        return self._bases[cid]

    def save_base(self, cid: str, base: dict):
        self._bases[cid] = base
        U.write_json(self.p.bases / f"{cid}.json", base)
        from .views import render_base_view
        render_base_view(self, cid)

    def all_pool_ids(self) -> list[str]:
        return [f.stem for f in self.p.pools.glob("*.json")]

    def find_aspect(self, aid: str) -> tuple[str, dict] | tuple[None, None]:
        for cid in list(self.nodes):
            pool = self.pool(cid)
            if aid in pool["aspects"]:
                return cid, pool["aspects"][aid]
        return None, None

    def mark_dirty(self, cid: str, reason: str = ""):
        """Pool changed in content: We need a full base assembly. (pooling, value, assembly)."""
        if cid and cid in self.nodes:
            d = self.state["dirty"].setdefault(cid, {"stage": "analysis", "reasons": []})
            d["stage"] = "analysis"
            if reason and reason not in d["reasons"]:
                d["reasons"].append(reason)
            self.nodes[cid].fm["last_modified"] = U.today()

    def mark_recalc(self, cid: str, reason: str = ""):
        """All I need is a code recalculation. (modelless)."""
        if cid and cid in self.nodes:
            d = self.state["dirty"].get(cid)
            if d is None:
                self.state["dirty"][cid] = {"stage": "assemble", "reasons": [reason] if reason else []}
            elif reason and reason not in d["reasons"]:
                d["reasons"].append(reason)

    # ---------- food ----------
    def products_of(self, cid: str) -> list[tuple[Path, dict, str]]:
        node = self.nodes.get(cid)
        if node is None:
            return []
        return [(p, fm, b) for p, fm, b in self.products
                if fm.get("container_id") == cid or (not fm.get("container_id") and p.parent == node.folder)]

    # ---------- css flower-colour ----------
    def write_css(self):
        """Colors of container folders and record files (section 3.7): record — mixed-color."""
        lines = ["/* Created by Second Brain: folder colors. Enable this snippet in Obsidian Settings → Appearance. */"]
        def q(s):
            return s.replace('\\', '\\\\').replace('"', '\\"')
        for n in sorted(self.nodes.values(), key=lambda x: self.path_key(x)):
            color = n.fm.get("color")
            if not color:
                continue
            key = q(self.path_key(n))
            lines.append(f'.nav-folder-title[data-path="{key}"] {{ color: {color}; }}')
            lines.append(f'.nav-file-title[data-path^="{key}/_record/"] {{ color: {color}; }}')
        for e in sorted(self.entities.values(), key=lambda x: x.id):
            if not e.also_in_ids:
                continue
            cols = [self.nodes[c].fm.get("color") for c in [e.container_id] + e.also_in_ids if c in self.nodes]
            cols = [c for c in cols if c]
            if not cols:
                continue
            try:
                rel = q(e.path.relative_to(self.p.root).as_posix())
            except ValueError:
                continue
            lines.append(f'.nav-file-title[data-path="{rel}"] {{ color: {_avg(cols)}; }}')
        text = "\n".join(lines) + "\n"
        if not self.p.css.exists() or self.p.css.read_text(encoding="utf-8") != text:
            U.atomic_write_text(self.p.css, text)
        self._enable_snippet_once()

    def _enable_snippet_once(self):
        """Once to turn on the snippet in the settings Obsidian (appearance.json). If the user
        Then turn it off. — program no longer touches."""
        if self.state.get("css_enabled_once"):
            return
        ap = self.p.root / ".obsidian" / "appearance.json"
        try:
            data = U.read_json(ap, {}) if ap.exists() else {}
            if not isinstance(data, dict):
                return
            names = list(data.get("enabledCssSnippets") or [])
            if self.p.css.stem not in names:
                names.append(self.p.css.stem)
                data["enabledCssSnippets"] = names
                U.write_json(ap, data)
            self.state["css_enabled_once"] = True
        except (OSError, ValueError):
            pass

    # ---------- service unit in the container file ----------
    def refresh_node_blocks(self):
        """References from the container to its general records in _shared (section 3.4), shop-case."""
        for n in self.nodes.values():
            key = self.path_key(n)
            shared = sorted((e for e in self.entities.values()
                             if e.also_in_ids and (e.container_id == n.id or n.id in e.also_in_ids)),
                            key=lambda e: e.created)
            own = [e for e in self.entities.values() if e.container_id == n.id and not e.also_in_ids]
            prods = sorted(p.stem for p, fm, b in self.products_of(n.id))
            lines = [BLOCK_START, f"Entries in the `_record` folder: {len(own)}."]
            if shared:
                lines.append("Shared entries (stored in `_shared` and also linked to other containers): "
                             + ", ".join(f"[[{e.title}]]" for e in shared))
            if prods:
                lines.append("Documents: " + ", ".join(f"[[{key}/{t}|{t}]]" for t in prods))
            else:
                lines.append("No documents yet; they will appear after Phase 2 (synth).")
            if (n.folder / "_aspects.md").exists() or (n.folder / "_synthesis.md").exists():
                lines.append(f"Views (read only): [[{key}/_aspects|aspects]], [[{key}/_synthesis|synthesis]]")
            else:
                lines.append("The aspects and synthesis views will appear after the first entries.")
            lines.append(BLOCK_END)
            block = "\n".join(lines)
            body = n.body or ""
            if BLOCK_START in body and BLOCK_END in body:
                a = body.index(BLOCK_START)
                b = body.index(BLOCK_END) + len(BLOCK_END)
                new_body = body[:a] + block + body[b:]
            else:
                new_body = body.rstrip("\n") + "\n\n" + block + "\n"
            if new_body != body:
                n.body = new_body
                U.write_md(n.path, n.fm, n.body)


BLOCK_START = "<!-- updated: beginning -->"
BLOCK_END = "<!-- updated: ending -->"


def _avg(colors: list[str]) -> str:
    rgb = []
    for c in colors:
        h = c.lstrip("#")
        if len(h) == 6:
            rgb.append([int(h[i:i + 2], 16) for i in (0, 2, 4)])
    if not rgb:
        return colors[0]
    return "#" + "".join(f"{int(sum(x[i] for x in rgb) / len(rgb)):02X}" for i in range(3))

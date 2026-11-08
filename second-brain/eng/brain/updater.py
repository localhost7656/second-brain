"""Updating programme c GitHub (section 19.3). Source — repository UPDATE_REPO from brain/__init__.py:
latest release (program archive among release files or release source archive), And if theres no releases — branch
default (version — from brain/__init__.py). Installed: code, squash (changed by you — copy-in
prompts/_former), plugin (in the program folder and in the vault), «Install.bat», instruction; .bat-version 2.6 clean up. settings.yaml no keys
sway. All modules, fit-in, imported in advance: Program files change under the working command."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from . import UPDATE_REPO, __version__
from . import util as U
from .config import PROGRAM_DIR
from .install import LEGACY_FILES, remove_legacy
from .util import UserError

API = "https://api.github.com"
UA = "vtoroy-mozg-updater"
STATE_FILE = "installed.json"
PROMPT_BACKUP = "_former"
PLUGIN_ID = "vtoroy-mozg"
PLUGIN_FILES = ("main.js", "manifest.json", "styles.css")
# refresh: folders and individual files in the root of the program (settings.yaml, keynote — never)
DIRS = ("brain", "prompts", "plugin", "plugin-src", "tests")
ROOT_EXT = (".bat", ".md", ".txt", ".yaml")  # .yaml — sample settings.template.yaml (himself settings.yaml — never)
NEVER = re.compile(r"^(settings\.yaml.*|api_key.*\.txt|.*_api_key\.txt|github_token.*\.txt|.*token.*\.txt|installed\.json)$",
                   re.IGNORECASE)


def api_base() -> str:
    return (os.environ.get("BRAIN_GITHUB_API") or API).rstrip("/")


def repo_link() -> str:
    """Reference to the program repository: UPDATE_REPO into brain/__init__.py (BRAIN_UPDATE_REPO — check-up)."""
    return str(os.environ.get("BRAIN_UPDATE_REPO") or UPDATE_REPO or "").strip()


def parse_repo(url: str) -> tuple[str, str]:
    """https://github.com/name/turno, github.com/name/turno(.git), name/turno → (name, turno)."""
    s = str(url or "").strip().strip("/")
    if not s:
        raise UserError("No update repository is configured (UPDATE_REPO in "
                        "brain/__init__.py in the program folder). A new version can be installed manually from an archive.")
    s = re.sub(r"^(https?://)?(www\.)?github\.com/", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^git@github\.com:", "", s, flags=re.IGNORECASE)
    parts = [p for p in s.split("/") if p]
    if len(parts) < 2 or not all(re.match(r"^[A-Za-z0-9_.-]+$", p) for p in parts[:2]):
        raise UserError(f"Invalid GitHub repository address: “{url}” (UPDATE_REPO in brain/__init__.py). "
                        "Use an address like https://github.com/name/repository.")
    return parts[0], re.sub(r"\.git$", "", parts[1])


def version_tuple(v) -> tuple:
    nums = re.findall(r"\d+", str(v or ""))
    return tuple(int(x) for x in nums[:4]) or (0,)


def newer(a, b) -> bool:
    """a new b?"""
    ta, tb = version_tuple(a), version_tuple(b)
    n = max(len(ta), len(tb))
    return ta + (0,) * (n - len(ta)) > tb + (0,) * (n - len(tb))


def _get(url: str, accept: str = "application/vnd.github+json", timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError(url)
        if e.code in (401, 403):
            limit = e.headers.get("X-RateLimit-Remaining") == "0"
            if limit:
                raise UserError("GitHub rate limit reached. Try again in an hour.")
            raise UserError("GitHub denied access: The program repository should be open (public).")
        raise UserError(f"GitHub returned {e.code}. Try again.")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UserError(f"Could not contact GitHub ({getattr(e, 'reason', e)}). Check your internet connection.")


def _json(url: str):
    try:
        return json.loads(_get(url).decode("utf-8"))
    except ValueError:
        raise UserError("GitHub returned an invalid response. Try again.")


def latest(cfg) -> dict:
    """Whats in the repository: version and where to download it."""
    owner, repo = parse_repo(repo_link())
    base = f"{api_base()}/repos/{owner}/{repo}"
    info = {"repo": f"{owner}/{repo}", "url": f"https://github.com/{owner}/{repo}", "current": __version__}
    try:
        rel = _json(f"{base}/releases/latest")
    except FileNotFoundError:
        rel = None
    if rel:
        assets = [a for a in rel.get("assets") or [] if str(a.get("name", "")).lower().endswith(".zip")]
        asset = next((a for a in assets if "brain" in a.get("name", "").lower() or "brain" in a.get("name", "").lower()),
                     assets[0] if assets else None)
        info.update(source="release", version=str(rel.get("tag_name") or rel.get("name") or "").lstrip("vV"),
                    tag=rel.get("tag_name"), notes=(rel.get("body") or "").strip(), published=rel.get("published_at"))
        if asset:
            info.update(zip_url=asset.get("browser_download_url") or asset.get("url"),
                        zip_accept="application/octet-stream", asset=asset.get("name"))
        else:
            info.update(zip_url=rel.get("zipball_url") or f"{base}/zipball/{rel.get('tag_name')}", zip_accept="application/vnd.github+json")
        return info
    try:
        meta = _json(base)
    except FileNotFoundError:
        raise UserError(f"Repository {owner}/{repo} not found on GitHub (check UPDATE_REPO in brain/__init__.py; "
                        "the repository must be public).")
    branch = meta.get("default_branch") or "main"
    try:
        tree = _json(f"{base}/git/trees/{urllib.parse.quote(branch)}?recursive=1")
    except FileNotFoundError:
        raise UserError(f"Repository {owner}/{repo} is empty or has no releases or files.")
    paths = [t["path"] for t in tree.get("tree") or [] if t.get("type") == "blob" and
             (t["path"] == "brain/__init__.py" or t["path"].endswith("/brain/__init__.py"))]
    if not paths:
        raise UserError(f"No program found in repository {owner}/{repo} (brain/__init__.py is missing).")
    path = min(paths, key=len)
    try:
        raw = _get(f"{base}/contents/{urllib.parse.quote(path)}?ref={urllib.parse.quote(branch)}",
                   accept="application/vnd.github.raw")
    except FileNotFoundError:
        raise UserError(f"Could not read the program version in repository {owner}/{repo}.")
    m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", raw.decode("utf-8", errors="replace"))
    info.update(source="branch", branch=branch, version=m.group(1) if m else "0", notes="",
                zip_url=f"{base}/zipball/{urllib.parse.quote(branch)}", zip_accept="application/vnd.github+json")
    return info


def check(cfg) -> dict:
    info = latest(cfg)
    info["newer"] = newer(info.get("version"), __version__)
    return info


# ---------- installation ----------
def _sha(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _find_root(names: list[str]) -> str:
    """Prefix of the program folder inside the archive: there, where brain/__init__.py (shortcut)."""
    cands = [n[: -len("brain/__init__.py")] for n in names if n == "brain/__init__.py" or n.endswith("/brain/__init__.py")]
    if not cands:
        raise UserError("No program found in the downloaded archive (brain/__init__.py is missing).")
    return min(cands, key=len)


def _plan(src: Path) -> list[tuple[Path, str]]:
    """New version files: (unpacked, path)."""
    out = []
    for d in DIRS:
        base = src / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(src)
            if not p.is_file() or "__pycache__" in rel.parts or "node_modules" in rel.parts or p.suffix == ".pyc":
                continue
            if d == "prompts" and PROMPT_BACKUP in rel.parts:
                continue
            out.append((p, rel.as_posix()))
    for p in sorted(src.iterdir()):
        if p.is_file() and p.suffix.lower() in ROOT_EXT and not NEVER.match(p.name):
            out.append((p, p.name))
    return out


def load_state(program_dir: Path = PROGRAM_DIR) -> dict:
    d = U.read_json(program_dir / STATE_FILE, None)
    return d if isinstance(d, dict) else {}


def write_state(program_dir: Path, version: str, source: str, files: dict | None = None):
    if files is None:
        files = {}
        for d in ("brain", "prompts", "plugin"):
            for p in sorted((program_dir / d).rglob("*")) if (program_dir / d).is_dir() else []:
                rel = p.relative_to(program_dir)
                if p.is_file() and "__pycache__" not in rel.parts and PROMPT_BACKUP not in rel.parts:
                    files[rel.as_posix()] = _sha(p)
    U.write_json(program_dir / STATE_FILE, {"version": version, "installed": U.now_iso(), "source": source, "files": files})


def install_zip(cfg, data: bytes, info: dict, program_dir: Path = PROGRAM_DIR) -> dict:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise UserError("The downloaded file is not a valid program archive. Try again later.")
    names = [n.replace("\\", "/") for n in z.namelist()]
    root = _find_root(names)
    tmp = Path(tempfile.mkdtemp(prefix="brain-update-"))
    try:
        for zi in z.infolist():
            n = zi.filename.replace("\\", "/")
            if not n.startswith(root) or n.endswith("/"):
                continue
            rel = n[len(root):]
            if not rel or rel.startswith("/") or ".." in rel.split("/"):
                continue
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(zi) as f, open(dest, "wb") as out:
                shutil.copyfileobj(f, out)
        init = (tmp / "brain" / "__init__.py").read_text(encoding="utf-8", errors="replace")
        m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", init)
        version = m.group(1) if m else str(info.get("version") or "?")
        if not (tmp / "brain" / "cli.py").exists() or not (tmp / "prompts").is_dir():
            raise UserError("The downloaded archive is incomplete (brain/cli.py or prompts is missing); update cancelled.")
        _keep_repo_link(tmp / "brain" / "__init__.py", init, program_dir)
        return _install_tree(cfg, tmp, version, info, program_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


_REPO_LINE = re.compile(r'^(UPDATE_REPO\s*=\s*)(["\'])(.*?)\2', re.M)


def _keep_repo_link(new_init: Path, text: str, program_dir: Path) -> None:
    """In the new version, the line UPDATE_REPO idle, a in the prescribed — link: link (later
    The program will stop seeing the following updates)."""
    m = _REPO_LINE.search(text)
    if not m or m.group(3).strip():
        return
    try:
        cur = (program_dir / "brain" / "__init__.py").read_text(encoding="utf-8")
    except OSError:
        return
    c = _REPO_LINE.search(cur)
    if c and c.group(3).strip():
        new_init.write_text(_REPO_LINE.sub(lambda x: f'{x.group(1)}"{c.group(3).strip()}"', text, count=1), encoding="utf-8")


def _install_tree(cfg, src: Path, version: str, info: dict, program_dir: Path) -> dict:
    state = load_state(program_dir)
    known = state.get("files") or {}
    plan = _plan(src)
    new_rel = {rel for _, rel in plan}
    stamp = time.strftime("%Y-%m-%d %H-%M")
    backed, updated, added, removed = [], 0, 0, []
    old_req = (program_dir / "requirements.txt").read_bytes() if (program_dir / "requirements.txt").exists() else b""
    files_state = {}
    for p, rel in plan:
        dest = program_dir / rel
        new_bytes = p.read_bytes()
        new_sha = hashlib.sha1(new_bytes).hexdigest()
        if rel.startswith(("brain/", "prompts/", "plugin/")):
            files_state[rel] = new_sha
        if dest.exists():
            cur = _sha(dest)
            if cur == new_sha:
                continue
            if rel.startswith("prompts/") and rel.endswith(".md"):
                if known.get(rel) == new_sha:
                    continue  # In the new version, this slate has not changed., And you ruled him. — Its yours.
                # pump, modified (unknown, changed) — copy-in prompts/_former
                if known.get(rel) != cur:
                    bdir = program_dir / "prompts" / PROMPT_BACKUP
                    bdir.mkdir(parents=True, exist_ok=True)
                    b = bdir / f"{Path(rel).stem} ({stamp}).md"
                    U.retry_fs(shutil.copy2, dest, b)
                    backed.append(Path(rel).stem)
            updated += 1
        else:
            added += 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmpf = dest.with_name(dest.name + ".new")
        tmpf.write_bytes(new_bytes)
        U.retry_fs(os.replace, tmpf, dest)
    # obsolete modules (The new version doesnt.) — remove, keep out
    bdir = program_dir / "brain"
    for p in sorted(bdir.glob("*.py")) if bdir.is_dir() else []:
        rel = p.relative_to(program_dir).as_posix()
        if rel not in new_rel:
            try:
                U.retry_fs(p.unlink)
                removed.append(rel)
            except OSError:
                pass
    shutil.rmtree(bdir / "__pycache__", ignore_errors=True)
    # .bat-file: s 2.6 plugin, remains «Install.bat»
    if not any(rel in LEGACY_FILES for rel in new_rel):
        removed += remove_legacy(program_dir)
    notes = []
    new_req = (program_dir / "requirements.txt").read_bytes() if (program_dir / "requirements.txt").exists() else b""
    pip_ok = None
    if new_req and new_req != old_req:
        print("Updating Python dependencies (requirements.txt)…", flush=True)
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(program_dir / "requirements.txt")],
                               timeout=900)
            pip_ok = r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            pip_ok = False
        if not pip_ok:
            notes.append("Python dependencies could not be updated; run Install.bat again.")
    plugin_dest = None
    try:
        vault = cfg.vault
        dest = vault / ".obsidian" / "plugins" / PLUGIN_ID
        if dest.is_dir() and all((program_dir / "plugin" / f).exists() for f in PLUGIN_FILES):
            for f in PLUGIN_FILES:
                U.retry_fs(shutil.copy2, program_dir / "plugin" / f, dest / f)
            plugin_dest = str(dest)
    except OSError as e:
        notes.append(f"The plugin in the vault could not be updated ({e}); run Install.bat again.")
    write_state(program_dir, version, f"{info.get('repo', '')} {info.get('tag') or info.get('branch') or ''}".strip(),
                files_state or None)
    if backed:
        notes.append("Your modified prompts were saved in prompts/_former: " + ", ".join(backed)
                     + " — new prompts were installed; transfer your changes if needed.")
    return {"version": version, "updated": updated, "added": added, "removed": removed, "prompts_backed_up": backed,
            "plugin": plugin_dest, "pip": pip_ok, "notes": notes}


def download(cfg, info: dict) -> bytes:
    url = info.get("zip_url")
    if not url:
        raise UserError("No new version archive found.")
    print(f"Downloading version {info.get('version')} from GitHub ({info.get('repo')})…", flush=True)
    try:
        return _get(url, accept=info.get("zip_accept") or "application/octet-stream", timeout=300)
    except FileNotFoundError:
        raise UserError("The archive of the new version was not found on GitHub — try again.")

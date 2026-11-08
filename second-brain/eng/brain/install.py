"""Install the Obsidian plugin and clean up legacy launchers (setup command)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

from . import util as U
from .config import PROGRAM_DIR
from .util import UserError

PLUGIN_ID = "vtoroy-mozg"
PLUGIN_FILES = ("main.js", "manifest.json", "styles.css")
# .bat-version 2.6: All this plugin is doing now.; remains «Install.bat»
LEGACY_FILES = ("Phase 1.bat", "Phase 2.bat", "Revalidation.bat", "Patterns..bat", "Verification.bat", "Status.bat",
                "Download the embedding model.bat", "Install the plugin.bat", "Update.bat")


def remove_legacy(program_dir: Path = PROGRAM_DIR) -> list[str]:
    """Clean up. .bat-file (Your user files with other names are not affected.)."""
    removed = []
    for name in LEGACY_FILES:
        p = program_dir / name
        if p.is_file():
            try:
                U.retry_fs(p.unlink)
                removed.append(name)
            except OSError:
                pass
    return removed


# ---------- storage Obsidian ----------
def obsidian_config_dirs() -> list[Path]:
    """Where Obsidian store-list (obsidian.json)."""
    if os.environ.get("BRAIN_OBSIDIAN_CONFIG"):  # test-board
        return [Path(os.environ["BRAIN_OBSIDIAN_CONFIG"])]
    home = Path.home()
    if os.name == "nt":
        out = [Path(os.environ["APPDATA"]) / "obsidian"] if os.environ.get("APPDATA") else []
        return out + [home / "AppData" / "Roaming" / "obsidian"]
    if sys.platform == "darwin":
        return [home / "Library" / "Application Support" / "obsidian"]
    xdg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return [xdg / "obsidian", home / ".var" / "app" / "md.obsidian.Obsidian" / "config" / "obsidian",
            home / "snap" / "obsidian" / "current" / ".config" / "obsidian"]


def find_vaults() -> list[Path]:
    """Storage facilities, know-how Obsidian: now-open, later — last opening."""
    seen, out = set(), []
    for d in obsidian_config_dirs():
        data = U.read_json(d / "obsidian.json", None)
        vaults = data.get("vaults") if isinstance(data, dict) else None
        if not isinstance(vaults, dict):
            continue
        items = [v for v in vaults.values() if isinstance(v, dict) and v.get("path")]
        items.sort(key=lambda v: (not v.get("open"), -float(v.get("ts") or 0)))
        for v in items:
            p = Path(str(v["path"]))
            if not (p / ".obsidian").is_dir():
                continue
            key = os.path.normcase(str(p.resolve()))
            if key not in seen:
                seen.add(key)
                out.append(p)
    return out


def is_vault(p: Path | None) -> bool:
    return bool(p) and (p / ".obsidian").is_dir()


def obsidian_running() -> bool:
    """Is it open now? Obsidian (on Windows — process-list)."""
    if os.environ.get("BRAIN_OBSIDIAN_RUNNING") is not None:  # test-board
        return os.environ["BRAIN_OBSIDIAN_RUNNING"] == "1"
    try:
        if os.name == "nt":
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/NH"], capture_output=True, timeout=15,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return b"obsidian.exe" in (r.stdout or b"").lower()
        exe = shutil.which("pgrep")
        if exe:
            return subprocess.run([exe, "-xi", "obsidian"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def open_obsidian(vault: Path) -> bool:
    """Open the vault in Obsidian reference obsidian://open (if Obsidian fixed)."""
    if os.environ.get("BRAIN_NO_OPEN"):  # test-board
        return False
    url = "obsidian://open?path=" + urllib.parse.quote(str(vault), safe="")
    try:
        if os.name == "nt":
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        opener = shutil.which("open" if sys.platform == "darwin" else "xdg-open")
        if opener:
            subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except OSError:
        pass
    return False


def install_plugin(vault: Path, program_dir: Path | None = None, python: str | None = None) -> Path:
    """Copy and enable the plugin, retaining other plugin settings."""
    program_dir = program_dir or PROGRAM_DIR
    src = program_dir / "plugin"
    missing = [f for f in PLUGIN_FILES if not (src / f).exists()]
    if missing:
        raise UserError(f"Missing plugin files ({', '.join(missing)}) in {src}. Extract the program archive again.")
    if not is_vault(vault):
        raise UserError(f"{vault} is not an Obsidian vault (the .obsidian folder is missing). Open it in Obsidian using "
                        "‘Open folder as vault’, then run Install.bat again.")
    dest = vault / ".obsidian" / "plugins" / PLUGIN_ID
    dest.mkdir(parents=True, exist_ok=True)
    for f in PLUGIN_FILES:
        U.retry_fs(shutil.copy2, src / f, dest / f)
    data_path = dest / "data.json"
    data = U.read_json(data_path, None) or {}
    if not isinstance(data, dict):
        data = {}
    data.update({"programDir": str(program_dir), "pythonPath": python or sys.executable})
    U.write_json(data_path, data)
    cp = vault / ".obsidian" / "community-plugins.json"
    enabled = U.read_json(cp, None) if cp.exists() else []
    if not isinstance(enabled, list):
        enabled = []
    if PLUGIN_ID not in enabled:
        enabled.append(PLUGIN_ID)
        U.write_json(cp, enabled)
    return dest


def choose_vault(current: Path | None, ask: bool) -> Path:
    """Where to put the plugin: found-house Obsidian list; can insert."""
    found = find_vaults()
    if current and is_vault(current):
        key = os.path.normcase(str(current.resolve()))
        found = [current] + [p for p in found if os.path.normcase(str(p.resolve())) != key]
    if not ask:
        if found:
            return found[0]
        raise UserError("No Obsidian vault was found. Open Obsidian and create a vault or choose ‘Open folder as vault’, "
                        "then run Install.bat again.")
    while True:
        if found:
            print("Which Obsidian vault should receive the plugin?")
            for i, p in enumerate(found, 1):
                print(f"  {i}. {p}")
            print("Enter a number (press Enter for 1), or paste the path to another vault folder.")
        else:
            print("No Obsidian vaults found. If you do not have a vault yet, open Obsidian and create one")
            print("or choose ‘Open folder as vault’. Then enter the vault folder path here (you can drag the folder into this window).")
        try:
            s = input("> ").strip().strip('"').strip("'").strip()
        except EOFError:
            s = ""
        if not s and found:
            return found[0]
        if s.isdigit() and found and 1 <= int(s) <= len(found):
            return found[int(s) - 1]
        if s:
            p = Path(os.path.expanduser(s))
            if is_vault(p):
                return p
            print(f"{p} is not an Obsidian vault (the .obsidian folder is missing). Check the path.")
        elif not found:
            raise UserError("No vault folder was provided; the plugin was not installed. Run Install.bat again after creating a vault.")

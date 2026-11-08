"""Your own model of e-bidding on this computer — llama.cpp (section 12.3).
Button «Run the model…» plugin settings (team brain llama start) download
KaLM-Embedding-Gemma3 12B (Q4_K_S, near 6,9 GB) s Hugging Face and ready-made llama.cpp s GitHub (processor;
CUDA — graphics-card NVIDIA; Vulkan — for any video card), launcher llama-server background, wait, model
load, and enters the server address into the settings. Wherever there is (program-folder):
  models/                 — model (another folder can be set: embeddings.server.models_dir)
  llama.cpp/<assembly>/     — llama-server and his library (cpu, vulkan, cuda)
  llama.cpp/server.json   — run-off: processor, port, parameters
  llama.cpp/server.log    — server-log (last-minute)
If the server is not running, need (Phase 1, «Check the link.»), The program runs it itself with the saved
parameter (embeddings.server.autostart) — But without your team, nothing gets downloaded.."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from . import interact
from . import util as U
from .util import UserError

MODEL = {
    "repo": "mradermacher/KaLM-Embedding-Gemma3-12B-2511-GGUF",
    "file": "KaLM-Embedding-Gemma3-12B-2511.Q4_K_S.gguf",
    "size": 6935332800,  # spare-value — The size and checksum are usually taken from Hugging Face
    "sha256": "a054d4827db5ccf48702b637bcf0b807577fb7b706f676e6ce5667b78192a5f0",
    "alias": "KaLM-Embedding-Gemma3-12B-2511",  # Thats what the model is called on the server. (field «Model» customized)
    "title": "KaLM-Embedding-Gemma3 12B (Q4_K_S)",
    "layers": 48,
    "dim": 3840,
    "ctx_max": 32768,
}
ALIAS = MODEL["alias"]
MIN_RAM_GB = 16  # processor
VRAM_GB = 8      # Approximately as much video memory is needed., So the whole model fits on a video card. (context 4096)
# Memory for text processing beyond the model itself (buffer llama.cpp), MIB, — grows with context: model
# Reading the entire text in one pass (casualness), so-called (-ub) contextual, ? KV-keto
# She doesnt have it at all. — quantization KV memory is not affected. Measured.: llama.cpp b12125, flash attention included.
WORK_MB = {512: 128, 2048: 526, 4096: 1084, 8192: 2296, 16384: 5104, 32768: 12256}
SERVER_DEFAULTS = {
    "device": "cpu",        # cpu — processor; gpu — videocard
    "build": "auto",        # assembly llama.cpp video-card: auto (CUDA for NVIDIA, otherwise Vulkan) | cuda | vulkan
    "gpu_layers": "auto",   # videocard: auto — how much will fit, all — everything, number
    "ctx": 4096,            # context, token — longest, model reads (≈ 12–14 thousand. sign)
    "kv_cache": "f16",      # quantization KV-keto: f16 | q8_0 | q4_0
    "threads": 0,           # processor-flow; 0 — llama.cpp decide
    "port": 8081,
    "sleep_min": 15,        # How many minutes to unload the model from memory; 0 — drop off
    "autostart": True,      # The program itself starts the server., whenever
    "models_dir": "",       # model-folder; empty — models program-folder
}
DEVICES = {"cpu": "processor", "gpu": "videocard"}
BUILDS = ("cpu", "vulkan", "cuda")
BUILD_TITLES = {"cpu": "processor", "vulkan": "Vulkan — for any video card", "cuda": "CUDA — graphics-card NVIDIA",
                "system": "computer-mounted"}
APPROX_MB = {"cpu": 25, "vulkan": 38, "cuda": 680, "vcredist": 25}  # launch-window — before, ask GitHub
KV_TYPES = ("f16", "q8_0", "q4_0")
LAYER_WORDS = ("auto", "all")
CTX_CHOICES = (2048, 4096, 8192, 16384, 32768)
VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
VC_DLLS = ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")
UA = "vtoroy-mozg"
STATE_FILE = "server.json"
LOG_FILE = "server.log"
LOAD_WAIT_SEC = 900  # How long to wait for the model to load in memory (slow-plate — minute)


def hf_base() -> str:
    return (os.environ.get("BRAIN_HF_BASE") or "https://huggingface.co").rstrip("/")


def gh_api() -> str:
    return (os.environ.get("BRAIN_LLAMA_API") or "https://api.github.com/repos/ggml-org/llama.cpp").rstrip("/")


def _gb(x) -> str:
    return f"{(x or 0) / 1e9:.1f}"


def _mb(x) -> str:
    return f"{(x or 0) / 1e6:.0f}"


def _size_text(x) -> str:
    return f"{_gb(x)} GB" if (x or 0) >= 1e9 else f"{_mb(x)} MB"


def _nowin() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


# ---------- parameters ----------
def check_params(p, where: str = "embeddings.server") -> list[str]:
    """Verification of launch parameters (windows «Run the model…» and settings.yaml)."""
    if not isinstance(p, dict):
        return [f"{where}: need a set of parameters"]
    errs = []

    def num(k, lo, hi):
        v = p.get(k)
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            errs.append(f"{where}.{k}: a whole number from {lo} to {hi} is required (now: {v!r})")

    if p.get("device") not in DEVICES:
        errs.append(f"{where}.device: cpu (processor) or gpu (videocard) (now: {p.get('device')!r})")
    if p.get("build") not in ("auto",) + BUILDS:
        errs.append(f"{where}.build: auto, cuda, vulkan or cpu (now: {p.get('build')!r})")
    gl = p.get("gpu_layers")
    if not (gl in LAYER_WORDS or (isinstance(gl, int) and not isinstance(gl, bool) and 0 <= gl <= 999)):
        errs.append(f"{where}.gpu_layers: auto, all, or a whole number from 0 to 999 (now: {gl!r})")
    num("ctx", 512, 131072)
    if p.get("kv_cache") not in KV_TYPES:
        errs.append(f"{where}.kv_cache: {', '.join(KV_TYPES)} (now: {p.get('kv_cache')!r})")
    num("threads", 0, 1024)
    num("port", 1024, 65535)
    num("sleep_min", 0, 10080)
    if not isinstance(p.get("autostart"), bool):
        errs.append(f"{where}.autostart: true or false")
    if not isinstance(p.get("models_dir"), str):
        errs.append(f"{where}.models_dir: must be a folder path or an empty string")
    return errs


def raw_params(cfg, over: dict | None = None) -> dict:
    """Launch parameters: silence ← settings.yaml ← transmitted (plugin-window). No checks.."""
    p = dict(SERVER_DEFAULTS)
    saved = (cfg["embeddings"] or {}).get("server")
    if isinstance(saved, dict):
        p.update({k: v for k, v in saved.items() if k in SERVER_DEFAULTS})
    if isinstance(over, dict):
        p.update({k: v for k, v in over.items() if k in SERVER_DEFAULTS})
    for k in ("ctx", "threads", "port", "sleep_min", "gpu_layers"):
        if isinstance(p.get(k), str) and p[k].strip().isdigit():
            p[k] = int(p[k].strip())
    if isinstance(p.get("models_dir"), str):
        p["models_dir"] = p["models_dir"].strip().strip('"').replace("\\", "/")
    elif p.get("models_dir") is None:
        p["models_dir"] = ""
    return p


def params(cfg, over: dict | None = None) -> dict:
    p = raw_params(cfg, over)
    errs = check_params(p)
    if errs:
        raise UserError("Parameters of launching the embedding model: " + "; ".join(errs))
    return p


# ---------- wherein ----------
def home(cfg) -> Path:
    return Path(cfg.program_dir) / "llama.cpp"


def models_dir(cfg, p: dict | None = None) -> Path:
    p = p or raw_params(cfg)
    d = str(p.get("models_dir") or "").strip()
    if not d:
        return Path(cfg.program_dir) / "models"
    q = Path(os.path.expanduser(d))
    return q if q.is_absolute() else Path(cfg.program_dir) / q


def model_file(cfg, p: dict | None = None) -> Path:
    return models_dir(cfg, p) / MODEL["file"]


def exe_name() -> str:
    return "llama-server.exe" if os.name == "nt" else "llama-server"


def plat() -> tuple[str, str]:
    osn = "win" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"
    m = (platform.machine() or "").lower()
    return osn, "arm64" if m in ("arm64", "aarch64", "armv8l") else "x64"


def _find_exe(d: Path) -> Path | None:
    if not d.is_dir():
        return None
    name = exe_name()
    for depth in range(3):
        for p in sorted(d.glob("/".join(["*"] * depth + [name]))):
            if p.is_file():
                return p
    return None


def build_info(cfg, build: str) -> dict | None:
    d = home(cfg) / build
    exe = _find_exe(d)
    if not exe:
        return None
    meta = U.read_json(d / "build.json", None) or {}
    return {"build": build, "exe": str(exe), "tag": str(meta.get("tag") or ""), "dir": str(d)}


def installed(cfg) -> dict:
    return {b: i for b in BUILDS if (i := build_info(cfg, b))}


def system_exe() -> str | None:
    """llama-server, computer-mounted (eat PATH)."""
    if os.environ.get("BRAIN_LLAMA_NO_SYSTEM"):
        return None
    return shutil.which(exe_name())


# ---------- equipment ----------
def _run_text(args: list[str], timeout: float = 20) -> str:
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, **_nowin())
    except (OSError, subprocess.SubprocessError):
        return ""
    return (r.stdout or b"").decode("utf-8", errors="replace") if r.returncode == 0 else ""


def _nvidia_smi() -> list[dict]:
    exe = shutil.which("nvidia-smi")
    if not exe and os.name == "nt":
        for c in (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe",
                  Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe"):
            if c.is_file():
                exe = str(c)
                break
    if not exe:
        return []
    out = []
    for ln in _run_text([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]).splitlines():
        parts = [x.strip() for x in ln.split(",")]
        if len(parts) >= 2 and parts[0]:
            try:
                vram = round(float(parts[1]) / 1024, 1)
            except ValueError:
                vram = None
            out.append({"name": parts[0], "vram_gb": vram, "vendor": "nvidia"})
    return out


def _vendor(name: str) -> str:
    n = name.lower()
    if "nvidia" in n or "geforce" in n or "quadro" in n or "rtx" in n:
        return "nvidia"
    if "amd" in n or "radeon" in n:
        return "amd"
    if "intel" in n:
        return "intel"
    return "other"


def _win_gpus() -> list[dict]:
    """Video cards from the registry Windows (there — videomemory, including more 4 GB)."""
    out = []
    try:
        import winreg
        base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            for i in range(64):
                try:
                    sub = winreg.EnumKey(k, i)
                except OSError:
                    break
                if not re.fullmatch(r"\d{4}", sub):
                    continue
                try:
                    with winreg.OpenKey(k, sub) as s:
                        def val(name):
                            try:
                                return winreg.QueryValueEx(s, name)[0]
                            except OSError:
                                return None
                        name = val("DriverDesc")
                        mem = val("HardwareInformation.qwMemorySize") or val("HardwareInformation.MemorySize")
                except OSError:
                    continue
                if not name or re.search(r"microsoft|virtual|remote|parsec|citrix|vmware|hyper-v", str(name), re.I):
                    continue
                if isinstance(mem, bytes):
                    mem = int.from_bytes(mem[:8], "little")
                vram = round(mem / 2 ** 30, 1) if isinstance(mem, int) and mem > 0 else None
                out.append({"name": str(name), "vram_gb": vram, "vendor": _vendor(str(name))})
    except Exception:  # noqa: BLE001 — register unavailable: Video cards just dont show
        return []
    return out


def _ram() -> tuple[float | None, float | None]:
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return st.ullTotalPhys / 2 ** 30, st.ullAvailPhys / 2 ** 30
            return None, None
        if sys.platform == "darwin":
            total = int(_run_text(["sysctl", "-n", "hw.memsize"]).strip() or 0)
            return (total / 2 ** 30 if total else None), None
        info = {}
        for ln in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = ln.partition(":")
            info[k.strip()] = int(v.strip().split()[0]) * 1024 if v.strip() else 0
        return info.get("MemTotal", 0) / 2 ** 30 or None, info.get("MemAvailable", 0) / 2 ** 30 or None
    except Exception:  # noqa: BLE001
        return None, None


def _cores() -> tuple[int | None, str]:
    """Physical cores of the processor and its name."""
    try:
        if os.name == "nt":
            name = ""
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                    name = str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
            except OSError:
                pass
            txt = _run_text(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                             "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum"], 25)
            n = int(txt.strip()) if txt.strip().isdigit() else None
            return n, name
        if sys.platform == "darwin":
            n = _run_text(["sysctl", "-n", "hw.physicalcpu"]).strip()
            return (int(n) if n.isdigit() else None), _run_text(["sysctl", "-n", "machdep.cpu.brand_string"]).strip()
        pairs, name, phys, core = set(), "", None, None
        for ln in Path("/proc/cpuinfo").read_text().splitlines():
            k, _, v = ln.partition(":")
            k, v = k.strip(), v.strip()
            if k == "model name" and not name:
                name = v
            elif k == "physical id":
                phys = v
            elif k == "core id":
                core = v
            elif not k and core is not None:
                pairs.add((phys, core))
                phys = core = None
        if core is not None:
            pairs.add((phys, core))
        return (len(pairs) or None), name
    except Exception:  # noqa: BLE001
        return None, ""


def hardware(cores: bool = True) -> dict:
    """What the computer has: memory, nucleus, videocard (window «Run the model…»). cores=False — countless
    physical nuclei (into Windows Thats an extra second.)."""
    total, free = _ram()
    n_cores, cpu = _cores() if cores else (None, "")
    gpus = _nvidia_smi()
    if os.name == "nt":
        names = {g["name"].lower() for g in gpus}
        gpus += [g for g in _win_gpus() if g["name"].lower() not in names]
    osn, arch = plat()
    hw = {"ram_gb": round(total, 1) if total else None, "ram_free_gb": round(free, 1) if free else None,
          "cores": n_cores, "threads": os.cpu_count(), "cpu": cpu, "gpus": gpus,
          "nvidia": any(g.get("vendor") == "nvidia" for g in gpus), "os": osn, "arch": arch}
    test = os.environ.get("BRAIN_TEST_HW")
    if test:
        try:
            hw.update(json.loads(test))
        except ValueError:
            pass
    return hw


# ---------- downloading ----------
def _http(url: str, headers: dict | None = None, timeout=30, stream: bool = False):
    import requests
    h = {"User-Agent": UA}
    h.update(headers or {})
    return requests.get(url, headers=h, timeout=timeout, stream=stream, allow_redirects=True)


def _stop_requested(stop: Path | None) -> bool:
    if stop is not None and stop.exists():
        try:
            stop.unlink()
        except OSError:
            pass
        return True
    return False


def download(urls: list, dest: Path, size: int | None, sha256: str | None, label: str, stop: Path | None = None) -> Path:
    """Download the dock file (.part near), Repeat and check the checksum. urls — [(address, headline), …]:
    next address — spare. «Stop.» plugin-leave .part: The next download will continue from the same place.."""
    import requests
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    if size and have > size:
        part.unlink()
        have = 0
    if size:
        free = shutil.disk_usage(dest.parent).free
        need = size - have
        if free < need + 300 * 2 ** 20:
            raise UserError(f"Not enough disk space for «{dest.name}»: need {_size_text(need)} more, available "
                            f"{_size_text(free)} (folder {dest.parent}). Free up the space or select another folder.")
    total = size
    shown = {"pct": -1, "print": 0.0}

    def show(force=False):
        if not total:
            return
        pct = min(100, int(100 * have / total))
        if pct != shown["pct"] or force:
            shown["pct"] = pct
            interact.progress(label, pct, 100, f"{_size_text(have)} from {_size_text(total)}", echo=False, unit="%")
        if force or time.time() - shown["print"] > 15:
            shown["print"] = time.time()
            print(f"  {label}: {pct}% ({_size_text(have)} from {_size_text(total)})", flush=True)

    ui, fails, err = 0, 0, ""
    while not (size and have >= size):
        url, hdr = urls[ui]
        h = dict(hdr or {})
        if have:
            h["Range"] = f"bytes={have}-"
        got = 0
        try:
            with _http(url, h, timeout=(20, 90), stream=True) as r:
                if r.status_code == 416 and have:
                    if size and have >= size:
                        break
                    part.unlink(missing_ok=True)  # The server does not know such a place in the file. — start again
                    have = 0
                    err = "squash"
                elif r.status_code in (200, 206):
                    if r.status_code == 200 and have:
                        have = 0  # server cant do the finishing — beginning
                    if not total:
                        try:
                            total = have + int(r.headers.get("Content-Length") or 0) or None
                        except ValueError:
                            total = None
                    if "text/html" in (r.headers.get("Content-Type") or "") and (size or 0) > 5e6:
                        err = "The server returned the page instead of the file."
                    else:
                        with open(part, "ab" if have else "wb") as f:
                            for chunk in r.iter_content(1 << 20):
                                if _stop_requested(stop):
                                    raise KeyboardInterrupt
                                if chunk:
                                    f.write(chunk)
                                    have += len(chunk)
                                    got += len(chunk)
                                    show()
                        if not size:
                            break  # pre-size — downloaded, give away
                        err = "connection broke"
                elif r.status_code == 404:
                    err = "file not found (404)"
                    fails += 2
                else:
                    err = f"server-answer {r.status_code}"
        except OSError as e:
            if isinstance(e, requests.RequestException):
                err = type(e).__name__
            elif getattr(e, "errno", None) == 28:  # ENOSPC
                raise UserError(f"The disk is full while downloading «{dest.name}». Free up space and try again. "
                                "The download will resume where it stopped.")
            else:
                raise
        if size and have >= size:
            break
        if got:
            fails = 0  # what-sliding — break, not give up: We try it out without counting.
        else:
            fails += 1
        if fails >= 3 and ui + 1 < len(urls):
            ui, fails = ui + 1, 0
            continue
        if fails >= 6:
            raise UserError(f"Could not download «{dest.name}»: {err}. Check your internet connection and try again. "
                            "The download will resume where it stopped.")
        for _ in range(int(min(30, 2 + 3 * fails) * 2)):
            if _stop_requested(stop):
                raise KeyboardInterrupt
            time.sleep(0.5)
    show(force=True)
    if size and have != size:
        part.unlink(missing_ok=True)
        raise UserError(f"«{dest.name}» has an incorrect size. Try again; it will be downloaded from the beginning.")
    if sha256:
        print(f"  Checking file {dest.name}…", flush=True)
        h = hashlib.sha256()
        done, last = 0, -1
        with open(part, "rb") as f:
            while True:
                chunk = f.read(8 << 20)
                if not chunk:
                    break
                h.update(chunk)
                done += len(chunk)
                pct = int(100 * done / max(1, have))
                if pct != last:
                    last = pct
                    interact.progress("File check.", pct, 100, dest.name, echo=False, unit="%")
        if h.hexdigest().lower() != sha256.lower():
            part.unlink(missing_ok=True)
            raise UserError(f"The checksum for «{dest.name}» did not match. Try again; "
                            "the file will be downloaded from the beginning.")
    U.retry_fs(os.replace, part, dest)
    return dest


def model_meta() -> dict:
    """Size and checksum of the model — s Hugging Face (if you didnt answer — constant)."""
    meta = {"size": MODEL["size"], "sha256": MODEL["sha256"]}
    try:
        r = _http(f"{hf_base()}/api/models/{MODEL['repo']}/tree/main", timeout=20)
        if r.status_code == 200:
            for x in r.json() or []:
                if x.get("path") == MODEL["file"]:
                    lfs = x.get("lfs") or {}
                    meta["size"] = int(lfs.get("size") or x.get("size") or meta["size"])
                    if lfs.get("oid") and re.fullmatch(r"[0-9a-f]{64}", str(lfs["oid"])):
                        meta["sha256"] = str(lfs["oid"])
                    break
    except Exception:  # noqa: BLE001 — no connection API: constant-sum
        pass
    return meta


def ensure_model(cfg, p: dict, stop: Path | None = None) -> Path:
    mp = model_file(cfg, p)
    if mp.is_file():
        return mp
    meta = model_meta()
    part = mp.with_name(mp.name + ".part")
    already = part.stat().st_size if part.exists() else 0
    print(f"Downloading the embedding model {MODEL['title']} — {_size_text(meta['size'])}, once"
          + (f" (already downloaded {_size_text(already)} — continue)" if already else "") + f". folder: {mp.parent}", flush=True)
    url = f"{hf_base()}/{MODEL['repo']}/resolve/main/{MODEL['file']}"
    return download([(url, {})], mp, meta["size"], meta["sha256"], "Downloading the model", stop)


# ---------- build-up llama.cpp s GitHub ----------
def _asset_rules(build: str) -> list[re.Pattern]:
    osn, arch = plat()
    if osn == "win":
        if build == "cuda":
            return [re.compile(r"^llama-b\d+-bin-win-cuda-(1[2-9]\.\d+)-x64\.zip$"),
                    re.compile(r"^cudart-llama-bin-win-cuda-(1[2-9]\.\d+)-x64\.zip$")]
        return [re.compile(rf"^llama-b\d+-bin-win-{'vulkan' if build == 'vulkan' else 'cpu'}-{arch}\.zip$")]
    if osn == "macos":
        return [re.compile(rf"^llama-b\d+-bin-macos-{arch}\.tar\.gz$")]
    return [re.compile(rf"^llama-b\d+-bin-ubuntu{'-vulkan' if build == 'vulkan' else ''}-{arch}\.tar\.gz$")]


def _asset(a: dict) -> dict:
    dg = str(a.get("digest") or "")
    urls = [(a.get("browser_download_url"), {})] if a.get("browser_download_url") else []
    if a.get("url"):
        urls.append((a["url"], {"Accept": "application/octet-stream"}))  # escape — through API GitHub
    return {"name": a.get("name"), "size": int(a.get("size") or 0) or None,
            "sha256": dg[7:] if dg.startswith("sha256:") else None, "urls": urls}


def pick_assets(rel: dict, build: str) -> list[dict] | None:
    assets = [a for a in rel.get("assets") or [] if isinstance(a, dict) and a.get("name")]
    rules = _asset_rules(build)
    if len(rules) == 2:  # CUDA: assembly + library CUDA same-size; CUDA 12 — wider support for graphics cards and drivers
        mains = [(a, m.group(1)) for a in assets if (m := rules[0].match(a["name"]))]
        if not mains:
            return None
        mains.sort(key=lambda x: (not x[1].startswith("12."), x[1]))
        main, ver = mains[0]
        rt = next((a for a in assets if (m := rules[1].match(a["name"])) and m.group(1) == ver), None)
        return [_asset(main)] + ([_asset(rt)] if rt else [])
    main = next((a for a in assets if rules[0].match(a["name"])), None)
    return [_asset(main)] if main else None


def _gh_json(url: str):
    r = _http(url, {"Accept": "application/vnd.github+json"}, timeout=30)
    if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
        raise UserError("GitHub rate limit reached. Try again in an hour.")
    if r.status_code != 200:
        raise UserError(f"GitHub returned {r.status_code}. Try again.")
    try:
        return r.json()
    except ValueError:
        raise UserError("GitHub returned an invalid response. Try again.")


def find_release(build: str) -> dict:
    """Fresh assembly llama.cpp: recent releases — first, file-box."""
    import requests
    api = gh_api()
    try:
        for rel in _gh_json(f"{api}/releases?per_page=10") or []:
            if isinstance(rel, dict) and not rel.get("draft") and (assets := pick_assets(rel, build)):
                return {"tag": str(rel.get("tag_name") or ""), "assets": assets}
        # escape: The last release indicates the fresh build number in the file nightly-tag.txt
        latest = _gh_json(f"{api}/releases/latest")
        if assets := pick_assets(latest, build):
            return {"tag": str(latest.get("tag_name") or ""), "assets": assets}
        nt = next((a for a in latest.get("assets") or [] if a.get("name") == "nightly-tag.txt"), None)
        if nt:
            tag = _http(nt["browser_download_url"], timeout=30).text.strip()
            if re.fullmatch(r"b\d+", tag):
                rel = _gh_json(f"{api}/releases/tags/{tag}")
                if assets := pick_assets(rel, build):
                    return {"tag": tag, "assets": assets}
    except requests.RequestException as e:
        raise UserError(f"Could not contact GitHub ({type(e).__name__}). Check your internet connection.")
    osn, arch = plat()
    raise UserError(f"No llama.cpp build found on GitHub: «{BUILD_TITLES.get(build, build)}» for this system "
                    f"({osn}-{arch}). Try again later or choose another option.")


def _extract(arc: Path, out: Path) -> None:
    n = arc.name.lower()
    if n.endswith(".zip"):
        with zipfile.ZipFile(arc) as z:
            for zi in z.infolist():
                parts = zi.filename.replace("\\", "/").split("/")
                if zi.filename.startswith(("/", "\\")) or ".." in parts:
                    continue
                z.extract(zi, out)
    elif n.endswith((".tar.gz", ".tgz")):
        with tarfile.open(arc, "r:gz") as t:
            try:
                t.extractall(out, filter="data")
            except TypeError:  # Python before 3.12
                t.extractall(out)
    else:
        raise UserError(f"Unknown type of archive: {arc.name}")


def ensure_build(cfg, build: str, stop: Path | None = None) -> Path:
    """llama-server fit-in: already downloaded or downloaded GitHub (llama.cpp/<assembly>/)."""
    info = build_info(cfg, build)
    if info:
        return Path(info["exe"])
    rel = find_release(build)
    total = sum(a["size"] or 0 for a in rel["assets"])
    print(f"Downloading llama.cpp {rel['tag']} ({BUILD_TITLES.get(build, build)}) — {_size_text(total)}…", flush=True)
    h = home(cfg)
    dl = h / "_download"
    dl.mkdir(parents=True, exist_ok=True)
    files = [download(a["urls"], dl / a["name"], a["size"], a["sha256"], "Downloading llama.cpp", stop) for a in rel["assets"]]
    new = h / f"_{build}.new"
    shutil.rmtree(new, ignore_errors=True)
    new.mkdir(parents=True)
    for f in files:
        _extract(f, new)
    exe = _find_exe(new)
    if not exe:
        shutil.rmtree(new, ignore_errors=True)
        raise UserError("The downloaded llama.cpp archive does not contain llama-server. Try again later or choose another build.")
    src = exe.parent
    if src != new:  # file-box (Linux, macOS): library CUDA, if, — ce llama-server
        for x in new.iterdir():
            if x.is_file():
                shutil.move(str(x), str(src / x.name))
    dest = h / build
    if dest.exists():
        shutil.rmtree(dest)
    os.replace(src, dest)
    shutil.rmtree(new, ignore_errors=True)
    exe = _find_exe(dest)
    if os.name != "nt" and exe:
        exe.chmod(exe.stat().st_mode | 0o111)
    U.write_json(dest / "build.json", {"build": build, "tag": rel["tag"], "assets": [a["name"] for a in rel["assets"]],
                                       "installed": U.now_iso()})
    for f in files:
        f.unlink(missing_ok=True)
    print(f"llama.cpp {rel['tag']} installed: {dest}", flush=True)
    return exe


def vc_missing(exe_dir: Path | None = None) -> list[str]:
    """Windows: library Microsoft Visual C++, without llama.cpp never start."""
    if os.name != "nt":
        return []
    sysdir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    return [d for d in VC_DLLS if not (sysdir / d).exists() and not (exe_dir and (Path(exe_dir) / d).exists())]


def ensure_vcredist(cfg, exe_dir: Path, stop: Path | None = None) -> None:
    miss = vc_missing(exe_dir)
    if not miss:
        return
    print("For llama.cpp libraries need to be needed Microsoft Visual C++ (" + ", ".join(miss) + ") — downloading their installer "
          "site Microsoft. Windows ask for installation permission — agree.", flush=True)
    f = download([(VC_REDIST_URL, {})], home(cfg) / "_download" / "vc_redist.x64.exe", None, None,
                 "Downloading Microsoft Visual C++", stop)
    try:
        subprocess.run([str(f), "/install", "/passive", "/norestart"], timeout=1200)
    except OSError as e:
        if getattr(e, "winerror", None) != 740:  # 740 — Administrator rights are required: launch «Yes.» window-wise Windows
            raise UserError(f"Could not start the Microsoft Visual C++ installer: {e}. Install it manually: {VC_REDIST_URL}")
        os.startfile(str(f), "runas", "/install /passive /norestart")  # type: ignore[attr-defined]
        for _ in range(600):
            if not vc_missing(exe_dir):
                break
            time.sleep(1)
    except subprocess.TimeoutExpired:
        pass
    if vc_missing(exe_dir):
        raise UserError(f"Microsoft Visual C++ libraries were not installed. Install them manually ({VC_REDIST_URL}) "
                        "and start the model again.")
    try:
        f.unlink()
    except OSError:
        pass


# ---------- server ----------
def _state_path(cfg) -> Path:
    return home(cfg) / STATE_FILE


def log_path(cfg) -> Path:
    return home(cfg) / LOG_FILE


def read_state(cfg) -> dict | None:
    d = U.read_json(_state_path(cfg), None)
    return d if isinstance(d, dict) and d.get("pid") else None


def _alive(pid) -> bool:
    """Process llama-server Its still working with this number.?"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True,
                                 timeout=20, **_nowin()).stdout or b""
        except (OSError, subprocess.SubprocessError):
            return True  # know — believe, work
        return b"llama-server" in out.lower()
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        if re.search(r"\)\s+[ZX]\s", Path(f"/proc/{pid}/stat").read_text()):
            return False  # finished, but not yet cleaned
        return b"llama-server" in Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return True


def _kill(pid: int, proc: subprocess.Popen | None = None) -> None:
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=30, **_nowin())
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    for _ in range(40):
        if proc is not None and proc.poll() is not None:
            return
        if proc is None and not _alive(pid):
            return
        time.sleep(0.25)
    if os.name != "nt":
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    if proc is not None:
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            pass


def health(port, timeout: float = 2.0) -> str | None:
    """ok — ready (or «sleep» and wake up on the first request.); loading — loader; None — answer."""
    import requests
    try:
        r = requests.get(f"http://127.0.0.1:{int(port)}/health", timeout=timeout)
    except (requests.RequestException, ValueError):
        return None
    return "ok" if r.status_code == 200 else "loading" if r.status_code == 503 else "error"


def _serves_our_model(port) -> bool:
    import requests
    try:
        return ALIAS in requests.get(f"http://127.0.0.1:{int(port)}/v1/models", timeout=3).text
    except requests.RequestException:
        return False


def server_url(port) -> str:
    return f"http://127.0.0.1:{int(port)}/v1"


def is_our_url(url, port) -> bool:
    """The e-budget address in the settings indicates our server (127.0.0.1 or localhost portable)?"""
    try:
        u = urlparse(str(url or "").strip())
        return (u.hostname or "") in ("127.0.0.1", "localhost", "::1") and int(u.port or 0) == int(port)
    except (ValueError, TypeError):
        return False


def running(cfg) -> dict | None:
    """Our server., if it works: condition server.json (trial-number)."""
    st = read_state(cfg)
    if not st:
        return None
    if _alive(st.get("pid")):
        return st
    try:
        _state_path(cfg).unlink()
    except OSError:
        pass
    return None


def _help_text(exe: Path) -> str:
    try:
        r = subprocess.run([str(exe), "--help"], capture_output=True, timeout=60, cwd=str(exe.parent), **_nowin())
    except subprocess.TimeoutExpired:
        raise UserError(f"llama-server did not respond to --help ({exe}).")
    except OSError as e:
        raise UserError(f"Could not start llama-server ({exe}): {e}")
    text = ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", errors="replace")
    if "--port" not in text:
        raise UserError(explain_exit(r.returncode, text, exe))
    return text


def list_devices(exe: Path) -> list[str]:
    """Devices, seer llama.cpp: «Vulkan0: NVIDIA GeForce RTX 3060 (12288 MiB, 11000 MiB free)»."""
    try:
        r = subprocess.run([str(exe), "--list-devices"], capture_output=True, timeout=120, cwd=str(exe.parent), **_nowin())
    except (OSError, subprocess.SubprocessError):
        return []
    text = ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", errors="replace")
    out, on = [], False
    for ln in text.splitlines():
        if "Available devices" in ln:
            on = True
            continue
        if on and re.match(r"^\s+\S+:\s", ln):
            out.append(ln.strip())
    return out


def command(p: dict, help_text: str) -> list[str]:
    """Arguments llama-server (model — filename: The server is launched from the model folder — so-so
    lettering)."""
    def has(flag):
        return re.search(rf"(^|[\s,]){re.escape(flag)}([\s,=]|$)", help_text, re.M) is not None
    a = ["-m", MODEL["file"], "--embedding", "--pooling", "last", "--alias", ALIAS, "--host", "127.0.0.1",
         "--port", str(p["port"]), "-c", str(p["ctx"]), "-np", "1"]
    if has("-ub") or has("--ubatch-size"):
        # The model reads the entire text in one pass: The entire text should fit in one package., otherwise
        # (default 512 token) server «input is too large to process»
        a += ["-b", str(p["ctx"]), "-ub", str(p["ctx"])]
    if p["kv_cache"] != "f16":
        a += ["-ctk", p["kv_cache"], "-ctv", p["kv_cache"], "-fa", "on"]  # quantized V-cache flash attention
    if p["device"] == "cpu":
        a += ["-ngl", "0"]
        if has("--device"):
            a += ["-dev", "none"]
    else:
        gl = p["gpu_layers"]
        words = re.search(r"--n-gpu-layers[^\n]*\n[^\n]*'auto'", help_text) is not None or "'auto', or 'all'" in help_text
        if gl in LAYER_WORDS:
            a += ["-ngl", gl if words else "999"]
        else:
            a += ["-ngl", str(gl)]
    if p["threads"]:
        a += ["-t", str(p["threads"]), "-tb", str(p["threads"])]
    if p["sleep_min"] and has("--sleep-idle-seconds"):
        a += ["--sleep-idle-seconds", str(int(p["sleep_min"]) * 60)]
    if has("--no-webui"):
        a += ["--no-webui"]
    return a


def _tail(path: Path, n: int = 12) -> str:
    try:
        lines = path.read_bytes()[-20000:].decode("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(ln.rstrip() for ln in lines[-n:] if ln.strip())


def explain_exit(code, text: str, exe: Path | None = None) -> str:
    """Why? llama-server failed — plain-text (by the exit code and the last lines of the journal)."""
    t = text or ""
    low = t.lower()
    try:
        c = int(code) & 0xFFFFFFFF if code is not None else None
    except (TypeError, ValueError):
        c = None
    if c == 0xC0000135 or "msvcp140" in low or "vcruntime140" in low:
        why = ("missing Windows libraries. Install Microsoft Visual C++ Redistributable "
               f"({VC_REDIST_URL}); for the CUDA build, also install a current NVIDIA driver")
    elif re.search(r"out of memory|failed to allocate|cudamalloc failed|erroroutofdevicememory|"
                   r"not enough memory|unable to allocate|bad_alloc", low):
        why = ("lack of memory. Reduce Context, which uses the most memory beyond the model itself"
               + (", put fewer layers on the GPU" if "gpu" in low or "cuda" in low or "vulkan" in low else "")
               + " — or close other programs.")
    elif re.search(r"address already in use|couldn't bind|could not bind|failed to bind|bind failed", low):
        why = "the port is in use by another program; select another port in the launch window"
    elif re.search(r"failed to (open|load) model|no such file|unable to open|error loading model|invalid magic", low):
        why = "could not read the model file; it may be damaged. Delete it and download it again"
    elif re.search(r"unknown argument|invalid argument|error: unrecognized", low):
        why = ("this version of llama.cpp does not recognize a parameter; delete the llama.cpp folder in the program folder, "
               "and a fresh version will be downloaded on the next start")
    elif c in (0xC000001D,) or "illegal instruction" in low:
        why = "the CPU does not support this llama.cpp build"
    else:
        why = f"exit {code}" if code is not None else "cause unknown"
    tail = "\n".join(t.strip().splitlines()[-6:])
    return f"llama-server failed: {why}." + (f"\nLast lines of the server log:\n{tail}" if tail else "")


def _launch(exe: Path, args: list[str], cwd: Path, log: Path) -> subprocess.Popen:
    """Launch in the background: magazine, windowless; The program may be closed after launch — The server will continue to work.."""
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists():
        try:
            os.replace(log, log.with_name("server.prev.log"))
        except OSError:
            pass
    env = {k: v for k, v in os.environ.items() if not k.startswith("LLAMA_ARG_")}  # customization llama.cpp undue
    f = open(log, "ab")
    try:
        kw = dict(cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, env=env, close_fds=True)
        if os.name == "nt":
            base = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            try:  # not close together Obsidian or program window (if the system allows it)
                return subprocess.Popen([str(exe)] + args, creationflags=base | 0x01000000, **kw)  # CREATE_BREAKAWAY_FROM_JOB
            except OSError:
                return subprocess.Popen([str(exe)] + args, creationflags=base, **kw)
        return subprocess.Popen([str(exe)] + args, start_new_session=True, **kw)
    finally:
        f.close()


def _wait_ready(cfg, proc: subprocess.Popen, port: int, log: Path, stop: Path | None) -> float:
    t0 = time.time()
    interact.progress("Loading the model into memory", 0, 0, "", echo=False)
    print("Loading the model into memory. This can take a few minutes on a hard drive…", flush=True)
    while True:
        code = proc.poll()
        if code is not None:
            _forget(cfg)
            raise UserError(explain_exit(code, _tail(log, 40)) + f"\nServer log: {log}")
        h = health(port)
        if h == "ok":
            return time.time() - t0
        if _stop_requested(stop):
            _kill(proc.pid, proc)
            _forget(cfg)
            raise KeyboardInterrupt
        if time.time() - t0 > LOAD_WAIT_SEC:
            _kill(proc.pid, proc)
            _forget(cfg)
            raise UserError(f"The model did not load within {LOAD_WAIT_SEC // 60} minutes. "
                            f"Server log: {log}")
        time.sleep(0.5)


def _forget(cfg) -> None:
    try:
        _state_path(cfg).unlink()
    except OSError:
        pass


def probe(port, timeout: float = 600) -> int:
    """Verification request: server counts embedding; reply — vector-length."""
    import requests
    try:
        r = requests.post(f"{server_url(port)}/embeddings", json={"model": ALIAS, "input": ["check-in"]}, timeout=timeout)
        r.raise_for_status()
        return len((r.json().get("data") or [{}])[0].get("embedding") or [])
    except (requests.RequestException, ValueError, AttributeError, IndexError) as e:
        raise UserError(f"The server is running but could not calculate an embedding: {e}")


def _port_free(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", int(port))) != 0


def choose_build(cfg, p: dict, hw: dict) -> tuple[str, Path | None]:
    """What a build. llama.cpp need: (assembly, llama-server — or None, if it needs to be downloaded)."""
    have = installed(cfg)
    osn, arch = plat()
    if p["device"] == "cpu" or osn == "macos":  # on Mac single-assembly — s Metal
        for b in ("cpu", "vulkan", "cuda"):  # any processor is suitable for downloading
            if b in have:
                return b, Path(have[b]["exe"])
        s = system_exe()
        return ("system", Path(s)) if s else ("cpu", None)
    want = p["build"]
    if want in ("auto", "cpu"):
        want = "cuda" if hw.get("nvidia") else "vulkan"
    if want == "cuda" and not (osn == "win" and arch == "x64"):
        want = "vulkan"  # ready-made CUDA — only Windows
    return want, (Path(have[want]["exe"]) if want in have else None)


def work_mb(ctx: int) -> int:
    """How much memory? (MIB) It will be used to process the text in this context. — beyond (centimeter. WORK_MB)."""
    pts = sorted(WORK_MB.items())
    if ctx <= pts[0][0]:
        return round(pts[0][1] * ctx / pts[0][0])
    for (c0, m0), (c1, m1) in zip(pts, pts[1:]):
        if ctx <= c1:
            return round(m0 + (m1 - m0) * (ctx - c0) / (c1 - c0))
    c, m = pts[-1]
    return round(m * (ctx / c) ** 2)


def _ints(v) -> set:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return set()
    return {n} if n > 0 else set()


def need_gb(ctx: int) -> float:
    """How much memory does a server with a model take? (GB): model + wordwork + bit-on-the-shoulder llama.cpp."""
    return (MODEL["size"] + work_mb(ctx) * 2 ** 20) / 1e9 + 0.3


def plan(cfg, p: dict, hw: dict | None = None) -> dict:
    """What you need to run with these parameters: What to download and how much it weighs."""
    hw = hw if hw is not None else hardware()
    build, exe = choose_build(cfg, p, hw)
    mp = model_file(cfg, p)
    part = mp.with_name(mp.name + ".part")
    items = []
    if not mp.is_file():
        have = part.stat().st_size if part.exists() else 0
        items.append({"what": "model", "title": f"Model {MODEL['title']}", "size": MODEL["size"] - have,
                      "note": f"already downloaded {_size_text(have)} — swell" if have else ""})
    if exe is None:
        items.append({"what": build, "title": f"llama.cpp ({BUILD_TITLES.get(build, build)})", "size": APPROX_MB[build] * 10 ** 6,
                      "note": ""})
    if os.name == "nt" and vc_missing(Path(exe).parent if exe else None):
        items.append({"what": "vcredist", "title": "Libraries Microsoft Visual C++ (Windows ask for permission)",
                      "size": APPROX_MB["vcredist"] * 10 ** 6, "note": ""})
    return {"build": build, "exe": str(exe) if exe else None, "download": items,
            "download_size": sum(i["size"] for i in items)}


def start(cfg, over: dict | None = None, *, allow_download: bool = True, save: bool = True, by: str = "") -> dict:
    """Run a server with a model (need — download), wait, set up."""
    p = params(cfg, over)
    stop = cfg.vault / ".system" / "stop" if cfg.vault.exists() else None
    if stop is not None:
        _stop_requested(stop)  # «Stop.», pressed after last launch, — out of account
    hw = hardware(cores=False)
    cur = running(cfg)
    if cur:
        same = cur.get("params") == p
        if same and health(cur["port"]) in ("ok", "loading"):
            while health(cur["port"]) == "loading":
                if _stop_requested(stop):
                    raise KeyboardInterrupt
                time.sleep(0.5)
            print(f"The model server is already running: {server_url(cur['port'])}", flush=True)
            if save:
                _save_settings(cfg, p)
            return dict(_public(cur), already=True)
        print("Restart the model server with new parameters…", flush=True)
        stop_server(cfg)
    if not _port_free(p["port"]):
        if _serves_our_model(p["port"]):
            if not over:  # self-start: The server with this model already exists. — And use it.
                print(f"A server for this model is already running on port {p['port']}; using it.", flush=True)
                if save:
                    _save_settings(cfg, p)
                return {"running": True, "port": p["port"], "url": server_url(p["port"]), "foreign": True}
            raise UserError(f"Port {p['port']} is already used by a llama-server instance not started by this program. "
                            "Its settings cannot be changed here. Close it (Task Manager → llama-server) "
                            "or choose another port in the launch window.")
        raise UserError(f"Port {p['port']} is in use by another program. Choose another port in the “Start model…” window "
                        "(for example, 8082), or close that program.")
    mp = model_file(cfg, p)
    if not mp.is_file():
        if not allow_download:
            raise UserError("The embedding model is not yet downloaded. In Settings → Second Brain → Models, choose “Start model…” to download "
                            f"the model ({_size_text(MODEL['size'])}, one-time download) and start it.")
        ensure_model(cfg, p, stop)
    build, exe = choose_build(cfg, p, hw)
    if exe is None:
        if not allow_download:
            raise UserError("llama.cpp is not installed. Open Settings → Second Brain → Models and choose “Start model…”.")
        exe = ensure_build(cfg, build, stop)
    if os.name == "nt":
        if vc_missing(exe.parent) and not allow_download:
            raise UserError("llama.cpp needs Microsoft Visual C++ libraries. Open Settings → Second Brain → Models → "
                            "“Start model…” to install them.")
        ensure_vcredist(cfg, exe.parent, stop)
    help_text = _help_text(exe)
    devices = []
    if p["device"] == "gpu" and plat()[0] != "macos":
        devices = [d for d in list_devices(exe) if not d.lower().startswith("cpu")]
        if not devices:
            what = BUILD_TITLES.get(build, build)
            raise UserError(f"llama.cpp ({what}) could not find a GPU. Update the graphics driver"
                            + (" or select the Vulkan build" if build == "cuda" else
                               " (for NVIDIA, select the CUDA build)" if build == "vulkan" else "")
                            + " — or use the CPU.")
        print("Video card: " + "; ".join(devices), flush=True)
    ram = hw.get("ram_gb")
    if p["device"] == "cpu" and ram and round(ram) < MIN_RAM_GB:
        interact.notice(f"Running the model on the CPU requires at least {MIN_RAM_GB} GB of RAM; "
                        f"this computer has {round(ram)} GB. Severe slowdown or out-of-memory errors are possible.")
        print(f"  ! RAM: {round(ram)} GB; CPU use requires at least {MIN_RAM_GB} GB", flush=True)
    elif p["device"] == "cpu" and ram and need_gb(p["ctx"]) > ram - 2:
        need = round(need_gb(p["ctx"]))
        interact.notice(f"With a context of {p['ctx']}, the model needs about {need} GB of RAM; this computer has "
                        f"{round(ram)} GB. Severe slowdown is possible. Reduce Context in the Start model dialog.")
        print(f"  ! context {p['ctx']} needs about {need} GB RAM; this computer has {round(ram)} GB", flush=True)
    args = command(p, help_text)
    log = log_path(cfg)
    print(f"Starting llama-server ({DEVICES[p['device']]}, port {p['port']})…", flush=True)
    proc = _launch(exe, args, mp.parent, log)
    st = {"pid": proc.pid, "port": p["port"], "url": server_url(p["port"]), "build": build, "exe": str(exe),
          "tag": (build_info(cfg, build) or {}).get("tag", ""), "args": args, "params": p, "devices": devices,
          "model": str(mp), "started": U.now_iso(), "by": by}
    U.write_json(_state_path(cfg), st)
    load = _wait_ready(cfg, proc, p["port"], log, stop)
    dim = probe(p["port"])
    print(f"Model loaded in {U.duration(load)}; embedding dimensions: {dim}. Server address: {server_url(p['port'])}", flush=True)
    st.update(dim=dim, load_sec=round(load, 1))
    U.write_json(_state_path(cfg), st)
    if save:
        _save_settings(cfg, p)
    return dict(_public(st), already=False)


def _public(st: dict) -> dict:
    return {"running": True, "pid": st.get("pid"), "port": st.get("port"), "url": st.get("url") or server_url(st.get("port")),
            "build": st.get("build"), "tag": st.get("tag"), "params": st.get("params"), "devices": st.get("devices") or [],
            "started": st.get("started"), "dim": st.get("dim"), "load_sec": st.get("load_sec")}


def _save_settings(cfg, p: dict) -> None:
    """Insert the server address in the settings, model and launch parameters (if-different)."""
    if not cfg.path:
        return
    from .schema import apply_patch
    e = cfg["embeddings"]
    want = {"mode": "local", "base_url": server_url(p["port"]), "model": ALIAS}
    patch = {k: v for k, v in want.items() if e.get(k) != v}
    if raw_params(cfg) != p:
        patch["server"] = p
    if patch:
        apply_patch(cfg, {"embeddings": patch})
        if "base_url" in patch or "model" in patch:
            print(f"Embedding address saved in settings: {want['base_url']} (model {ALIAS}).", flush=True)


def stop_server(cfg) -> dict:
    st = read_state(cfg)
    if not st:
        return {"stopped": False, "was_running": False}
    pid = int(st.get("pid") or 0)
    alive = _alive(pid)
    if alive:
        _kill(pid)
        port = st.get("port")
        for _ in range(40):  # process is already complete, But the port system releases a little later.
            if not port or _port_free(port):
                break
            time.sleep(0.25)
    _forget(cfg)
    return {"stopped": alive, "was_running": alive, "pid": pid}


def autostart(cfg) -> bool:
    """Embeddings not answering: if the address is in the settings — Our server and auto-start are on, launch (nothing
    downloading). True — launched, repeat the request."""
    c = cfg["embeddings"]
    if c.get("mode") != "local":
        return False
    p = raw_params(cfg)
    if check_params(p) or not p.get("autostart") or not is_our_url(c.get("base_url"), p["port"]):
        return False
    print("The embedding model server is not running; starting llama.cpp…", flush=True)
    start(cfg, None, allow_download=False, save=False, by="auto")
    return True


def status(cfg, with_hw: bool = False) -> dict:
    """For the plugin: model, build-up llama.cpp, server, parameters, (willingly) equipment."""
    p = raw_params(cfg)
    mp = model_file(cfg, p)
    part = mp.with_name(mp.name + ".part")
    st = running(cfg)
    srv = {"running": False}
    if st:
        srv = _public(st)
        srv["health"] = health(st["port"])
    c = cfg["embeddings"]
    try:
        free = shutil.disk_usage(mp.parent if mp.parent.exists() else Path(cfg.program_dir)).free
    except OSError:
        free = None
    out = {
        "model": {"file": MODEL["file"], "title": MODEL["title"], "alias": ALIAS, "path": str(mp), "dir": str(mp.parent),
                  "exists": mp.is_file(), "size": MODEL["size"], "partial": part.stat().st_size if part.exists() else 0,
                  "layers": MODEL["layers"], "dim": MODEL["dim"], "ctx_max": MODEL["ctx_max"], "free": free},
        "builds": installed(cfg), "system": system_exe(), "server": srv, "params": p, "defaults": dict(SERVER_DEFAULTS),
        "configured": c.get("mode") == "local" and is_our_url(c.get("base_url"), p.get("port")),
        "default_models_dir": str(Path(cfg.program_dir) / "models"),
        "log": str(log_path(cfg)) if log_path(cfg).exists() else "", "home": str(home(cfg)),
        "approx_mb": APPROX_MB, "min_ram_gb": MIN_RAM_GB, "vram_gb": VRAM_GB, "ctx_choices": list(CTX_CHOICES),
        "need_gb": {str(c): round(need_gb(c), 1) for c in sorted(set(CTX_CHOICES) | _ints(p.get("ctx")))},
        "kv_types": list(KV_TYPES), "os": plat()[0], "arch": plat()[1],
        "vcredist_missing": bool(vc_missing()) if os.name == "nt" else False,
    }
    if with_hw:
        out["hardware"] = hw = hardware()
        try:
            out["plan"] = plan(cfg, params(cfg), hw)
        except UserError:
            out["plan"] = None
    return out

"""Stubs to check your embedding model (llama.cpp) internetless.
FakeHub — Hugging Face (repository file list and model file with docking) and GitHub (releases llama.cpp archived);
SERVER_SCRIPT — «llama-server» on Python: --help, --list-devices server /health, /v1/models, /v1/embeddings."""
from __future__ import annotations

import hashlib
import http.server
import io
import json
import re
import socket
import tarfile
import threading
from urllib.parse import urlparse

SERVER_SCRIPT = r'''#!/usr/bin/env python3
"""Fake. llama-server program-test."""
import hashlib, http.server, json, math, os, sys, time

HELP = """----- common params -----
-h,    --help, --usage                  print usage and exit
-t,    --threads N                      number of CPU threads to use during generation (default: -1)
-tb,   --threads-batch N                number of threads to use during batch and prompt processing (default: same as --threads)
-c,    --ctx-size N                     size of the prompt context (default: 4096, 0 = loaded from model)
-b,    --batch-size N                   logical maximum batch size (default: 2048)
-ub,   --ubatch-size N                  physical maximum batch size (default: 512)
-fa,   --flash-attn [on|off|auto]       set Flash Attention use ('on', 'off', or 'auto', default: 'auto')
-ctk,  --cache-type-k TYPE              KV cache data type for K
-ctv,  --cache-type-v TYPE              KV cache data type for V
-dev,  --device <dev1,dev2,..>          comma-separated list of devices to use for offloading (none = don't offload)
--list-devices                          print list of available devices and exit
-ngl,  --gpu-layers, --n-gpu-layers N   max. number of layers to store in VRAM, either an exact number, 'auto', or 'all' (default: auto)
-m,    --model FNAME                    model path to load
--alias STRING                          set alias for model name (to be used by REST API)
--host HOST                             ip address to listen, or bind to an UNIX socket if the address ends with .sock (default: 127.0.0.1)
--port PORT                             port to listen (default: 8080)
--embedding, --embeddings               restrict to only support embedding use case; use only with dedicated embedding models
--pooling {none,mean,cls,last,rank}     pooling type for embeddings, use model default if unspecified
-np,   --parallel N                     number of server slots (default: -1, -1 = auto)
--no-webui                              Disable the Web UI (default: enabled)
--sleep-idle-seconds SECONDS            number of seconds of idleness after which the server will sleep (default: -1; -1 = disabled)
"""

a = sys.argv[1:]
if "--help" in a:
    print(HELP)
    sys.exit(0)
if "--list-devices" in a:
    print("Available devices:")
    gpu = os.environ.get("FAKE_LLAMA_GPU")
    print(f"  Vulkan0: {gpu} (8192 MiB, 8000 MiB free)" if gpu else "  (none)")
    sys.exit(0)


def opt(*names, default=None):
    for n in names:
        if n in a:
            i = a.index(n)
            return a[i + 1] if i + 1 < len(a) else default
    return default


print("FAKE ARGS: " + json.dumps(a, ensure_ascii=False), flush=True)
print("FAKE CWD: " + os.getcwd(), flush=True)
model = opt("-m", "--model")
if not model or not os.path.isfile(model):
    print(f"llama_model_load: error loading model: failed to open {model}: No such file or directory", flush=True)
    sys.exit(1)
if os.environ.get("FAKE_LLAMA_OOM"):
    print("ggml_backend_cpu_buffer_type_alloc_buffer: failed to allocate buffer of size 13958643712", flush=True)
    print("llama_init_from_model: failed to initialize the context: out of memory", flush=True)
    sys.exit(1)
port = int(opt("--port", default="8080"))
alias = opt("--alias", default=os.path.basename(model))
ctx = int(opt("-c", "--ctx-size", default="4096"))
ubatch = min(int(opt("-ub", "--ubatch-size", default="512")), int(opt("-b", "--batch-size", default="2048")))
T0 = time.time()
LOAD = float(os.environ.get("FAKE_LLAMA_LOAD_SEC", "0.8"))


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *x):
        pass

    def send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def loading(self):
        return time.time() - T0 < LOAD

    def do_GET(self):
        if self.path == "/health":
            if self.loading():
                return self.send(503, {"error": {"code": 503, "message": "Loading model", "type": "unavailable_error"}})
            return self.send(200, {"status": "ok"})
        if self.path in ("/v1/models", "/models"):
            return self.send(200, {"object": "list", "data": [{"id": alias, "object": "model", "owned_by": "llamacpp"}]})
        self.send(404, {"error": {"code": 404, "message": "File Not Found", "type": "not_found_error"}})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path not in ("/v1/embeddings", "/embeddings"):
            return self.send(404, {"error": {"code": 404, "message": "File Not Found", "type": "not_found_error"}})
        if self.loading():
            return self.send(503, {"error": {"code": 503, "message": "Loading model", "type": "unavailable_error"}})
        inp = body.get("input")
        inp = [inp] if isinstance(inp, str) else list(inp or [])
        print(f"REQ embeddings n={len(inp)} max={max((len(x) for x in inp), default=0)}", flush=True)
        for x in inp:
            if len(x) // 2 > ctx:
                return self.send(400, {"error": {"code": 400, "type": "exceed_context_size_error", "message":
                                       f"the request exceeds the available context size, try increasing it ({len(x) // 2} > {ctx})"}})
            if len(x) // 2 > ubatch:  # The model reads the entire text in one pass: It should fit in the bag.
                return self.send(500, {"error": {"code": 500, "type": "server_error", "message":
                                       f"input ({len(x) // 2} tokens) is too large to process. increase the physical batch size (current batch size: {ubatch})"}})
        data = []
        for i, x in enumerate(inp):
            h = hashlib.sha256(x.encode()).digest()
            v = [(b - 127.5) / 127.5 for b in h[:8]]
            nn = math.sqrt(sum(t * t for t in v)) or 1
            data.append({"object": "embedding", "index": i, "embedding": [t / nn for t in v]})
        tok = sum(len(x) // 2 + 1 for x in inp)
        self.send(200, {"object": "list", "model": alias, "data": data, "usage": {"prompt_tokens": tok, "total_tokens": tok}})


try:
    srv = http.server.ThreadingHTTPServer((opt("--host", default="127.0.0.1"), port), H)
except OSError:
    print(f"start: couldn't bind HTTP server socket, hostname: 127.0.0.1, port: {port}", flush=True)
    sys.exit(1)
print(f"main: server is listening on http://127.0.0.1:{port} - starting the main loop", flush=True)
srv.serve_forever()
'''


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_tar(arch: str, tag: str = "b9999") -> tuple[str, bytes]:
    """Archives llama.cpp, like GitHub for Linux: folder llama-<tag>/ s llama-server and libraries."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data, mode in ((f"llama-{tag}/llama-server", SERVER_SCRIPT.encode(), 0o755),
                                 (f"llama-{tag}/libggml-base.so", b"fake library", 0o644),
                                 (f"llama-{tag}/LICENSE", b"MIT License", 0o644)):
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode = len(data), mode
            t.addfile(ti, io.BytesIO(data))
    return f"llama-{tag}-bin-ubuntu-{arch}.tar.gz", buf.getvalue()


class FakeHub:
    """Hugging Face + GitHub on 127.0.0.1. Reference browser_download_url respondent 404 — The archive is only given through
    spare address API (Accept: application/octet-stream), as it happens GitHub faulty."""

    def __init__(self, repo: str, model_name: str, model: bytes, arch: str):
        self.repo, self.model_name, self.model = repo, model_name, model
        self.tar_name, self.tar = make_tar(arch)
        self.ranges: list = []        # headline Range model file requests
        self.break_once = 0           # sever the next output of the model file after so many bytes
        self.calls: list = []         # request (path)
        self.bad_sha = False          # API gives away the wrong checksum
        owner = self

        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *x):
                pass

            def send_json(self, obj, code=200):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def send_bytes(self, data: bytes, rng: str | None):
                start = 0
                if rng:
                    m = re.match(r"bytes=(\d+)-", rng)
                    start = int(m.group(1)) if m else 0
                    if start >= len(data):
                        self.send_response(416)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                part = data[start:]
                self.send_response(206 if rng else 200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(part)))
                if rng:
                    self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
                self.end_headers()
                if owner.break_once and data is owner.model:
                    n, owner.break_once = owner.break_once, 0
                    self.wfile.write(part[:n])
                    self.wfile.flush()
                    self.close_connection = True
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    return
                try:
                    for i in range(0, len(part), 1 << 18):
                        self.wfile.write(part[i:i + (1 << 18)])
                except (BrokenPipeError, ConnectionResetError):
                    pass  # downloading interrupted («Stop.»)

            def do_GET(self):
                path = urlparse(self.path).path
                owner.calls.append(path)
                base = f"http://127.0.0.1:{owner.port}"
                if path == f"/api/models/{owner.repo}/tree/main":
                    sha = "0" * 64 if owner.bad_sha else hashlib.sha256(owner.model).hexdigest()
                    return self.send_json([{"type": "file", "path": "README.md", "size": 1200},
                                           {"type": "file", "path": owner.model_name, "size": 135,
                                            "lfs": {"oid": sha, "size": len(owner.model), "pointerSize": 135}}])
                if path == f"/{owner.repo}/resolve/main/{owner.model_name}":
                    owner.ranges.append(self.headers.get("Range"))
                    return self.send_bytes(owner.model, self.headers.get("Range"))
                if path in ("/gh/releases", "/gh/releases/latest"):
                    rel = {"tag_name": "b9999", "draft": False, "assets": [
                        {"name": "llama-b9999-bin-win-cpu-x64.zip", "size": 10, "digest": "sha256:" + "1" * 64,
                         "browser_download_url": base + "/dl/llama-b9999-bin-win-cpu-x64.zip", "url": base + "/gh/assets/1"},
                        {"name": owner.tar_name, "size": len(owner.tar), "digest": "sha256:" + hashlib.sha256(owner.tar).hexdigest(),
                         "browser_download_url": base + "/dl/" + owner.tar_name, "url": base + "/gh/assets/2"},
                        {"name": "cudart-llama-bin-win-cuda-12.4-x64.zip", "size": 10, "digest": "sha256:" + "2" * 64,
                         "browser_download_url": base + "/dl/cudart.zip", "url": base + "/gh/assets/3"}]}
                    return self.send_json([rel] if path.endswith("releases") else rel)
                if path == "/gh/assets/2" and self.headers.get("Accept") == "application/octet-stream":
                    return self.send_bytes(owner.tar, self.headers.get("Range"))
                self.send_json({"message": "Not Found"}, 404)

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()

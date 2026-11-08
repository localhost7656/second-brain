"""Embeddings and vector storage (section 12).
Locally. — model llama.cpp (KaLM-Embedding-Gemma3 12B: Its downloaded and launched by the module. llama, button
«Run the model…» plug-in) or OpenAI-compatible server (/v1/embeddings); cloud — same format.
If your server is not running, program runs it itself (embeddings.server.autostart).
Warehouse — numpy-file .system/vectors: personal (thousand–tens of thousands of) enough."""
from __future__ import annotations

import hashlib
import json
import math
import re
import time

import numpy as np

from . import util as U
from .util import UserError

LEVELS = ("entities", "aspects", "containers")


class Embedder:
    def __init__(self, cfg, meter=None):
        self.cfg = cfg
        self.c = cfg["embeddings"]
        self.mode = "cloud" if self.c["mode"] == "api" else self.c["mode"]
        self.meter = meter  # expense-recording (usage.Meter)
        self._autostarted = False

    def _ours(self) -> bool:
        """Address in settings — server llama.cpp, program-starter?"""
        from . import llama
        p = llama.raw_params(self.cfg)
        return self.mode == "local" and llama.is_our_url(self.c.get("base_url"), p.get("port"))

    def _hint(self, refused: bool) -> str:
        if self.mode != "local":
            return ""
        if self._ours():
            return (" Start the model under Settings → Second Brain → Models → Start model…" if refused else
                    " Restart the model under Settings → Second Brain → Models → Start model…")
        return (" Is your embedding server running? You can also start the built-in model under "
                "Settings → Second Brain → Models → Start model…; its address is filled in automatically." if refused else
                " Check that your server is running an embedding model with the --embedding flag.")

    def _batches(self, texts: list[str]):
        """Text bundles: more batch piece — forecast — more 16 000 sign (processor
        pack is counted as minutes; so the request doesnt come down to «wait»)."""
        bs = max(1, int(self.c.get("batch", 16)))
        limit = 16000 if self.mode == "local" else 10 ** 9
        cur, size = [], 0
        for t in texts:
            if cur and (len(cur) >= bs or size + len(t) > limit):
                yield cur
                cur, size = [], 0
            cur.append(t)
            size += len(t)
        if cur:
            yield cur

    @property
    def fingerprint(self) -> str:
        if self.mode == "fake":
            return f"fake:{self.c.get('model')}"
        # «api» — what the cloud was called before v2.5: vectors are not recalculated from-name-name
        return f"{'api' if self.mode == 'cloud' else self.mode}:{self.c['model']}"

    def embed(self, texts: list[str]) -> np.ndarray:
        texts = [(t or " ")[: int(self.c.get("max_chars", 6000))] for t in texts]
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        if self.mode == "fake":
            return np.stack([_fake_vec(t) for t in texts])
        out = [self._api(b) for b in self._batches(texts)]
        m = np.concatenate(out, axis=0).astype(np.float32)
        n = np.linalg.norm(m, axis=1, keepdims=True)
        n[n == 0] = 1
        return m / n

    def _api(self, batch: list[str]) -> np.ndarray:
        import requests
        url = str(self.c["base_url"]).rstrip("/") + "/embeddings"
        headers = {"Content-Type": "application/json"}
        kf = str(self.c.get("api_key_file") or "").strip()
        key = self.cfg.secret(kf) if kf else None
        if self.mode == "cloud" and not key:
            raise UserError("No key for cloud embeddings: Save it in the plugin settings "
                            f"(file {kf or 'embeddings_api_key.txt'} in the program folder).")
        if key:  # for local key, Only if your server is running from --api-key
            headers["Authorization"] = f"Bearer {key}"
        if self.meter and self.mode == "cloud":
            self.meter.check_budget(None)
        delays = [3, 10, 30]
        tries, refused, shrunk, waited = 0, 0, 0, False
        t0 = time.time()
        while True:
            try:
                r = requests.post(url, json={"model": self.c["model"], "input": batch},
                                  headers=headers, timeout=self.c.get("timeout_sec", 600))
            except (requests.ConnectionError, requests.Timeout) as e:
                timeout = isinstance(e, requests.Timeout)
                refused += 0 if timeout else 1
                if not timeout and not self._autostarted and self._ours():
                    from . import llama
                    self._autostarted = True  # Your server is not running — launch (once-run)
                    if llama.autostart(self.cfg):
                        refused = 0
                        continue
                if tries < len(delays) and (timeout or refused < 3):  # loosening — server not running, wait long
                    time.sleep(delays[tries] if timeout else 1)
                    tries += 1
                    continue
                hint = self._hint(True)
                raise UserError(f"The embedding model is unavailable ({url}): {type(e).__name__}.{hint}")
            too_long = r.status_code in (400, 413, 500) and max(len(t) for t in batch) > 500 and \
                re.search(r"context|length|too large|token|batch size|debt|length", r.text, re.I)
            if too_long and shrunk < 8:
                shrunk += 1
                batch = [t[: max(500, len(t) // 2)] for t in batch]  # texture — shorten and try again
                continue
            if r.status_code == 503 and self._ours() and not waited:
                from . import llama  # Your server is still loading the model. (It just got launched.) — wait
                waited = True
                t1 = time.time()
                while llama.health(llama.raw_params(self.cfg)["port"]) == "loading" and time.time() - t1 < llama.LOAD_WAIT_SEC:
                    time.sleep(1)
                continue
            if r.status_code >= 500 and tries < len(delays):
                time.sleep(delays[tries])
                tries += 1
                continue
            if r.status_code >= 400:
                hint = self._hint(False)
                raise UserError(f"Embedding model error {r.status_code}: {r.text[:300]}.{hint}")
            try:
                body = r.json()
                data = body.get("data") or []
            except (ValueError, AttributeError):
                raise UserError(f"The embedding model did not return JSON: {r.text[:300]}")
            vecs = [d["embedding"] for d in sorted(data, key=lambda d: d.get("index", 0))]
            if len(vecs) != len(batch):
                raise UserError("The embedding model returned a different number of vectors than input texts.")
            if self.meter:
                usage = body.get("usage") if isinstance(body.get("usage"), dict) else None
                self.meter.record("emb", "embeddingi", self.mode, None, str(self.c["model"]), usage,
                                  sum(len(t) for t in batch), 0, time.time() - t0)
            return np.array(vecs, dtype=np.float32)


def _fake_vec(text: str, dim: int = 256) -> np.ndarray:
    """deterministic «bauble» test-board: similarity — near-vector."""
    v = np.zeros(dim, dtype=np.float32)
    words = re.findall(r"[^\W_]+", (text or "").lower())
    for w in words:
        stem = w[:6]
        h = int(hashlib.md5(stem.encode()).hexdigest(), 16)
        v[h % dim] += 1.0
    n = float(np.linalg.norm(v))
    return v / n if n else v


class VectorStore:
    def __init__(self, folder):
        self.folder = folder
        self.meta = U.read_json(folder / "meta.json", None) or {"model": None, "dim": None}
        self._ids: dict[str, list[str]] = {}
        self._mat: dict[str, np.ndarray] = {}
        self._dirty: set[str] = set()

    def _load(self, level: str):
        if level in self._ids:
            return
        f = self.folder / f"{level}.npz"
        if f.exists():
            z = np.load(f, allow_pickle=False)
            self._ids[level] = [str(x) for x in z["ids"]]
            self._mat[level] = z["mat"].astype(np.float32)
        else:
            self._ids[level] = []
            self._mat[level] = np.zeros((0, self.meta.get("dim") or 1), dtype=np.float32)

    def upsert(self, level: str, ids: list[str], vecs: np.ndarray):
        if not ids:
            return
        self._load(level)
        if self._mat[level].shape[0] == 0 or self._mat[level].shape[1] != vecs.shape[1]:
            if self._mat[level].shape[0] == 0:
                self._mat[level] = np.zeros((0, vecs.shape[1]), dtype=np.float32)
        index = {i: k for k, i in enumerate(self._ids[level])}
        mat = self._mat[level]
        new_ids, new_rows = [], []
        for i, v in zip(ids, vecs):
            if i in index:
                mat[index[i]] = v
            else:
                new_ids.append(i)
                new_rows.append(v)
        if new_rows:
            mat = np.concatenate([mat, np.stack(new_rows)], axis=0)
            self._ids[level] += new_ids
        self._mat[level] = mat
        self.meta["dim"] = int(vecs.shape[1])
        self._dirty.add(level)

    def remove(self, level: str, ids):
        self._load(level)
        ids = set(ids)
        keep = [k for k, i in enumerate(self._ids[level]) if i not in ids]
        self._ids[level] = [self._ids[level][k] for k in keep]
        self._mat[level] = self._mat[level][keep] if keep else self._mat[level][:0]
        self._dirty.add(level)

    def has(self, level: str, i: str) -> bool:
        self._load(level)
        return i in set(self._ids[level])

    def get(self, level: str, i: str):
        self._load(level)
        try:
            k = self._ids[level].index(i)
        except ValueError:
            return None
        return self._mat[level][k]

    def search(self, level: str, vec, k: int = 10, allow=None, exclude=()):
        self._load(level)
        if not self._ids[level] or vec is None:
            return []
        sims = self._mat[level] @ vec
        order = np.argsort(-sims)
        out = []
        ex = set(exclude)
        for j in order:
            i = self._ids[level][j]
            if i in ex or (allow is not None and i not in allow):
                continue
            out.append((i, float(sims[j])))
            if len(out) >= k:
                break
        return out

    def clear(self):
        for level in LEVELS:
            self._ids[level] = []
            self._mat[level] = np.zeros((0, 1), dtype=np.float32)
            self._dirty.add(level)

    def save(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        import os
        for level in list(self._dirty):
            ids = np.array(self._ids[level], dtype=str)
            tmp = self.folder / f".tmp-{level}.npz"
            with open(tmp, "wb") as f:
                np.savez(f, ids=ids, mat=self._mat[level])
            U.retry_fs(os.replace, tmp, self.folder / f"{level}.npz")
        self._dirty.clear()
        U.write_json(self.folder / "meta.json", self.meta)

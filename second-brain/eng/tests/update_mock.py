"""Verification of program updates with GitHub internetless: local server GitHub API —
latest release with the program archive, repository (branch, file-tree, branch-arch), mistake.
Reference to repository — line UPDATE_REPO into brain/__init__.py programme (s v2.7; Its not in the settings.).
Launch: python tests/update_mock.py"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

FILES: dict[str, tuple[int, bytes, str]] = {}  # request-way → (code, body, type)
SEEN: list = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        SEEN.append((self.path, self.headers.get("Authorization")))
        code, body, ctype = FILES.get(self.path, (404, b'{"message": "Not Found"}', "application/json"))
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def ok(cond, label):
    if not cond:
        print(f"Failure: {label}")
        sys.exit(1)
    print(f"  ✓ {label}")


def copy_program(dest: Path):
    def ignore(d, names):
        return [n for n in names if n in ("__pycache__", ".venv", "settings.yaml.bak", "installed.json")
                or n.startswith("api_key") or n == "github_token.txt"]
    shutil.copytree(APP, dest, ignore=ignore)


def make_zip(src: Path, top: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                z.write(p, f"{top}/{p.relative_to(src).as_posix()}")
    return buf.getvalue()


def set_repo(prog: Path, url: str):
    """Insert a link to the repository in the program — How does the developer do it before the project."""
    init = prog / "brain" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    line = f'UPDATE_REPO = "{url}"'
    text = re.sub(r'^UPDATE_REPO\s*=.*$', line, text, flags=re.M) if re.search(r'^UPDATE_REPO\s*=', text, re.M) else text + line + "\n"
    init.write_text(text, encoding="utf-8")


def repo_of(prog: Path) -> str:
    m = re.search(r'^UPDATE_REPO\s*=\s*"(.*)"', (prog / "brain" / "__init__.py").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "no line"


def brain(prog: Path, *args, expect=0):
    env = dict(os.environ)
    env.pop("BRAIN_UPDATE_REPO", None)  # link — only brain/__init__.py testable
    paths = [str(prog)] + [x for x in env.get("PYTHONPATH", "").split(os.pathsep) if x and Path(x).resolve() != APP.resolve()]
    env["PYTHONPATH"] = os.pathsep.join(paths)
    r = subprocess.run([sys.executable, "-m", "brain", "--settings", str(prog / "settings.yaml"), "--json"] + list(args),
                       cwd=str(prog), env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
    res = [x for x in r.stdout.splitlines() if x.startswith("@@RESULT ")]
    if r.returncode != expect or not res:
        print(r.stdout[-3000:], r.stderr[-3000:])
        ok(False, f"brain {' '.join(args)}: code {r.returncode}, expected {expect}")
    return r.stdout, json.loads(res[-1][len("@@RESULT "):])


def main():
    from brain import __version__, updater
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["BRAIN_GITHUB_API"] = base
    T = Path(tempfile.mkdtemp(prefix="brain-update-"))
    prog, vault = T / "Second Brain", T / "vault"
    copy_program(prog)
    plug = vault / ".obsidian" / "plugins" / "vtoroy-mozg"
    plug.mkdir(parents=True)
    (plug / "data.json").write_text('{"programDir": "x"}', encoding="utf-8")
    for f in ("main.js", "manifest.json", "styles.css"):
        (plug / f).write_text("// plugin", encoding="utf-8")
    # into settings.yaml previous versions — repository: s v2.7 Its not used.
    settings = (f"vault: \"{vault.as_posix()}\"\nupdates:\n  repo: \"https://github.com/user/old\"\n"
                "llm:\n  mode: fake\n  model: fake\nembeddings:\n  mode: fake\n  model: fake-1\n")
    (prog / "settings.yaml").write_text(settings, encoding="utf-8")
    (prog / "api_key.txt").write_text("mine-key\n", encoding="utf-8")
    updater.write_state(prog, __version__, "archive")
    set_repo(prog, "https://github.com/user/brain")
    # You ruled two prompts.: One in the new version hasnt changed., other — modified
    (prog / "prompts" / "Classification.md").write_text((prog / "prompts" / "Classification.md").read_text(encoding="utf-8")
                                                       + "\nMy classification correction.\n", encoding="utf-8")
    (prog / "prompts" / "Synthesis.md").write_text((prog / "prompts" / "Synthesis.md").read_text(encoding="utf-8")
                                                + "\nMy fusion editing..\n", encoding="utf-8")
    (prog / "brain" / "obsolete_module.py").write_text("# was in the previous version\n", encoding="utf-8")

    # version 9.9.9
    new = T / "new"
    copy_program(new)
    (new / "brain" / "__init__.py").write_text('"""Second Brain."""\n__version__ = "9.9.9"\nUPDATE_REPO = ""\n', encoding="utf-8")
    (new / "brain" / "new_module.py").write_text("X = 1\n", encoding="utf-8")
    (new / "prompts" / "Synthesis.md").write_text((new / "prompts" / "Synthesis.md").read_text(encoding="utf-8") + "\nNew in 9.9.9.\n",
                                               encoding="utf-8")
    (new / "plugin" / "main.js").write_text("// plugin 9.9.9", encoding="utf-8")
    (new / "settings.yaml").write_text("vault: stranger\n", encoding="utf-8")  # file should not be disturbed
    (new / "settings.template.yaml").write_text((new / "settings.template.yaml").read_text(encoding="utf-8")
                                                + "# sample 9.9.9\n", encoding="utf-8")
    rel = {"tag_name": "v9.9.9", "name": "9.9.9", "body": "Whats new?:\n- model profile\n- expense",
           "published_at": "2026-01-01T00:00:00Z",
           "assets": [{"name": "Second Brain v9.9.9.zip", "browser_download_url": f"{base}/dl/brain.zip",
                       "url": f"{base}/repos/user/brain/releases/assets/1"}],
           "zipball_url": f"{base}/repos/user/brain/zipball/v9.9.9"}
    FILES["/repos/user/brain/releases/latest"] = (200, json.dumps(rel).encode(), "application/json")
    FILES["/dl/brain.zip"] = (200, make_zip(new, "Second Brain"), "application/zip")

    print("=== Release with the program archive")
    out, r = brain(prog, "update", "--check")
    ok(r["ok"] and r["update"]["version"] == "9.9.9" and r["update"]["newer"] and r["update"]["source"] == "release"
       and "model profile" in r["update"]["notes"], "check-up: version 9.9.9, description")
    ok((prog / "brain" / "__init__.py").read_text(encoding="utf-8").count(__version__) == 1, "check-up doesnt change anything")
    ok(SEEN and all("/user/brain/" in x for x, _ in SEEN), "request — repository brain/__init__.py, not settings.yaml")
    out, r = brain(prog, "update", expect=1)
    ok("--yes" in r["error"], "proofless (without being able to ask) not installed")
    for n in ("Phase 1.bat", "Update.bat"):  # .bat-version 2.6
        (prog / n).write_text("@echo off\r\n", encoding="utf-8")
    out, r = brain(prog, "update", "--yes")
    ok(r["ok"] and r["installed"]["version"] == "9.9.9" and r["restart"], "fixed 9.9.9, I need a restart. Obsidian")
    ok(not (prog / "Phase 1.bat").exists() and not (prog / "Update.bat").exists() and (prog / "Install.bat").is_file()
       and sorted(p.name for p in prog.glob("*.bat")) == ["Install.bat"], "former .bat cleaned, Its just left. «Install.bat»")
    ok('__version__ = "9.9.9"' in (prog / "brain" / "__init__.py").read_text(encoding="utf-8")
       and (prog / "brain" / "new_module.py").exists() and not (prog / "brain" / "obsolete_module.py").exists(),
       "code updated: new module added, rusty")
    ok(repo_of(prog) == "https://github.com/user/brain", "new-line UPDATE_REPO idle — written-in reference retained")
    ok((prog / "settings.yaml").read_text(encoding="utf-8") == settings and (prog / "api_key.txt").read_text(encoding="utf-8") == "mine-key\n",
       "settings.yaml And the keys are intact.")
    ok("# sample 9.9.9" in (prog / "settings.template.yaml").read_text(encoding="utf-8"),
       "pattern settings.template.yaml updated")
    ok("New in 9.9.9" in (prog / "prompts" / "Synthesis.md").read_text(encoding="utf-8")
       and any("My fusion editing." in p.read_text(encoding="utf-8") for p in (prog / "prompts" / "_former").glob("Synthesis*.md")),
       "modified in the new version of the prompt updated, edit — into prompts/_former")
    ok("My classification correction" in (prog / "prompts" / "Classification.md").read_text(encoding="utf-8")
       and not list((prog / "prompts" / "_former").glob("Classification*.md")), "pump, which the new version did not change, remained yours.")
    ok((plug / "main.js").read_text(encoding="utf-8") == "// plugin 9.9.9" and json.loads((plug / "data.json").read_text(encoding="utf-8"))
       == {"programDir": "x"}, "plugin in the storage updated, his settings (data.json) — no")
    st = json.loads((prog / "installed.json").read_text(encoding="utf-8"))
    ok(st["version"] == "9.9.9" and "prompts/Synthesis.md" in st["files"], "installed.json: file-version")
    ok(any("_former" in n for n in r["notices"]), "finally, where your old prompts are")
    out, r = brain(prog, "update", "--check")
    ok(r["title"] == "Last version" and not r["update"]["newer"], "retest: latest version")

    print("=== Repository without releases: branch-line")
    new2 = T / "repo"
    copy_program(new2 / "app")
    (new2 / "app" / "brain" / "__init__.py").write_text('__version__ = "9.9.10"\nUPDATE_REPO = ""\n', encoding="utf-8")
    (new2 / "README.md").write_text("# repository", encoding="utf-8")
    FILES["/repos/user/brain2"] = (200, b'{"default_branch": "main"}', "application/json")
    tree = {"tree": [{"path": "README.md", "type": "blob"}, {"path": "app/brain/__init__.py", "type": "blob"},
                     {"path": "app/tests/brain/__init__.py", "type": "blob"}]}
    FILES["/repos/user/brain2/git/trees/main?recursive=1"] = (200, json.dumps(tree).encode(), "application/json")
    FILES["/repos/user/brain2/contents/app/brain/__init__.py?ref=main"] = (200, b'__version__ = "9.9.10"\n', "text/plain")
    FILES["/repos/user/brain2/zipball/main"] = (200, make_zip(new2, "user-brain2-abc123"), "application/zip")
    set_repo(prog, "https://github.com/user/brain2")
    out, r = brain(prog, "update", "--yes")
    ok(r["installed"]["version"] == "9.9.10" and r["update"]["source"] == "branch" and r["update"]["branch"] == "main"
       and '"9.9.10"' in (prog / "brain" / "__init__.py").read_text(encoding="utf-8"), "releaseless: default version and archive")
    ok(repo_of(prog) == "https://github.com/user/brain2", "The link to the repository has been preserved again.")
    ok(not (prog / "README.md").exists() or (prog / "README.md").read_text(encoding="utf-8") != "# repository",
       "files outside the program folder are not placed in the repository")

    print("=== Mistakes.")
    set_repo(prog, "https://github.com/user/nope")
    out, r = brain(prog, "update", "--check", expect=1)
    ok("found" in r["error"] and "UPDATE_REPO" in r["error"], "Theres no repository. → misunderstood (where to correct the link)")
    set_repo(prog, "link")
    out, r = brain(prog, "update", "--check", expect=1)
    ok("GitHub" in r["error"] and "UPDATE_REPO" in r["error"], "non-reference GitHub → misunderstood")
    set_repo(prog, "")
    out, r = brain(prog, "update", "--check", expect=1)
    ok("UPDATE_REPO" in r["error"] and "brain/__init__.py" in r["error"], "linkless → spoken, where to put it")
    out, r = brain(prog, "settings")
    ok(r["settings"]["update_repo"] == "" and "repo" not in (r["settings"]["values"].get("updates") or {}),
       "There is no link in the settings for the plugin (field), update_repo hollow")
    (prog / "github_token.txt").write_text("ghp_test\n", encoding="utf-8")
    set_repo(prog, "https://github.com/user/brain")
    SEEN.clear()
    brain(prog, "update", "--check")
    ok(SEEN and all(a is None for _, a in SEEN), "token is no more: even github_token.txt request Authorization")
    srv.shutdown()
    print("\nUpdate in order.")


if __name__ == "__main__":
    main()

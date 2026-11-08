"""Проверка обновления программы с GitHub без интернета: локальный сервер в формате GitHub API —
последний релиз с архивом программы, репозиторий без релизов (ветка, дерево файлов, архив ветки), ошибки.
Запуск: python tests/update_mock.py"""
from __future__ import annotations

import io
import json
import os
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

FILES: dict[str, tuple[int, bytes, str]] = {}  # путь запроса → (код, тело, тип)
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
        print(f"ПРОВАЛ: {label}")
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


def brain(prog: Path, *args, expect=0):
    env = dict(os.environ)
    paths = [str(prog)] + [x for x in env.get("PYTHONPATH", "").split(os.pathsep) if x and Path(x).resolve() != APP.resolve()]
    env["PYTHONPATH"] = os.pathsep.join(paths)
    r = subprocess.run([sys.executable, "-m", "brain", "--settings", str(prog / "settings.yaml"), "--json"] + list(args),
                       cwd=str(prog), env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
    res = [x for x in r.stdout.splitlines() if x.startswith("@@RESULT ")]
    if r.returncode != expect or not res:
        print(r.stdout[-3000:], r.stderr[-3000:])
        ok(False, f"brain {' '.join(args)}: код {r.returncode}, ожидался {expect}")
    return r.stdout, json.loads(res[-1][len("@@RESULT "):])


def main():
    from brain import updater
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["BRAIN_GITHUB_API"] = base
    T = Path(tempfile.mkdtemp(prefix="brain-update-"))
    prog, vault = T / "Второй мозг", T / "vault"
    copy_program(prog)
    plug = vault / ".obsidian" / "plugins" / "vtoroy-mozg"
    plug.mkdir(parents=True)
    (plug / "data.json").write_text('{"programDir": "x"}', encoding="utf-8")
    for f in ("main.js", "manifest.json", "styles.css"):
        (plug / f).write_text("// старый плагин", encoding="utf-8")
    settings = (f"vault: \"{vault.as_posix()}\"\nupdates:\n  repo: \"https://github.com/user/brain\"\n"
                "llm:\n  mode: fake\n  model: fake\nembeddings:\n  mode: fake\n  model: fake-1\n")
    (prog / "settings.yaml").write_text(settings, encoding="utf-8")
    (prog / "api_key.txt").write_text("мой-ключ\n", encoding="utf-8")
    updater.write_state(prog, "2.6.0", "архив")
    # вы правили два промпта: один в новой версии не менялся, другой — изменён
    (prog / "prompts" / "Классификация.md").write_text((prog / "prompts" / "Классификация.md").read_text(encoding="utf-8")
                                                       + "\nМоя правка классификации.\n", encoding="utf-8")
    (prog / "prompts" / "Синтез.md").write_text((prog / "prompts" / "Синтез.md").read_text(encoding="utf-8")
                                                + "\nМоя правка синтеза.\n", encoding="utf-8")
    (prog / "brain" / "устаревший_модуль.py").write_text("# был в прошлой версии\n", encoding="utf-8")

    # новая версия 9.9.9
    new = T / "new"
    copy_program(new)
    (new / "brain" / "__init__.py").write_text('"""Второй мозг."""\n__version__ = "9.9.9"\n', encoding="utf-8")
    (new / "brain" / "новый_модуль.py").write_text("X = 1\n", encoding="utf-8")
    (new / "prompts" / "Синтез.md").write_text((new / "prompts" / "Синтез.md").read_text(encoding="utf-8") + "\nНовое в 9.9.9.\n",
                                               encoding="utf-8")
    (new / "plugin" / "main.js").write_text("// плагин 9.9.9", encoding="utf-8")
    (new / "settings.yaml").write_text("vault: чужое\n", encoding="utf-8")  # в архиве не должно мешать
    (new / "settings.template.yaml").write_text((new / "settings.template.yaml").read_text(encoding="utf-8")
                                                + "# образец 9.9.9\n", encoding="utf-8")
    rel = {"tag_name": "v9.9.9", "name": "9.9.9", "body": "Что нового:\n- профили моделей\n- расходы",
           "published_at": "2026-01-01T00:00:00Z",
           "assets": [{"name": "Второй мозг v9.9.9.zip", "browser_download_url": f"{base}/dl/brain.zip",
                       "url": f"{base}/repos/user/brain/releases/assets/1"}],
           "zipball_url": f"{base}/repos/user/brain/zipball/v9.9.9"}
    FILES["/repos/user/brain/releases/latest"] = (200, json.dumps(rel).encode(), "application/json")
    FILES["/dl/brain.zip"] = (200, make_zip(new, "Второй мозг"), "application/zip")

    print("=== Релиз с архивом программы")
    out, r = brain(prog, "update", "--check")
    ok(r["ok"] and r["update"]["version"] == "9.9.9" and r["update"]["newer"] and r["update"]["source"] == "release"
       and "профили моделей" in r["update"]["notes"], "проверка: есть версия 9.9.9, с описанием")
    ok((prog / "brain" / "__init__.py").read_text(encoding="utf-8").count("2.6.0") == 1, "проверка ничего не меняет")
    out, r = brain(prog, "update", expect=1)
    ok("--yes" in r["error"], "без подтверждения (и без возможности спросить) не устанавливается")
    for n in ("Фаза 1.bat", "Обновить.bat"):  # .bat-файлы версий до 2.6
        (prog / n).write_text("@echo off\r\n", encoding="utf-8")
    out, r = brain(prog, "update", "--yes")
    ok(r["ok"] and r["installed"]["version"] == "9.9.9" and r["restart"], "установлена 9.9.9, нужен перезапуск Obsidian")
    ok(not (prog / "Фаза 1.bat").exists() and not (prog / "Обновить.bat").exists() and (prog / "Установка.bat").is_file()
       and sorted(p.name for p in prog.glob("*.bat")) == ["Установка.bat"], "прежние .bat убраны, осталась только «Установка.bat»")
    ok('__version__ = "9.9.9"' in (prog / "brain" / "__init__.py").read_text(encoding="utf-8")
       and (prog / "brain" / "новый_модуль.py").exists() and not (prog / "brain" / "устаревший_модуль.py").exists(),
       "код обновлён: новый модуль добавлен, устаревший убран")
    ok((prog / "settings.yaml").read_text(encoding="utf-8") == settings and (prog / "api_key.txt").read_text(encoding="utf-8") == "мой-ключ\n",
       "settings.yaml и ключи не тронуты")
    ok("# образец 9.9.9" in (prog / "settings.template.yaml").read_text(encoding="utf-8"),
       "образец настроек settings.template.yaml обновлён")
    ok("Новое в 9.9.9" in (prog / "prompts" / "Синтез.md").read_text(encoding="utf-8")
       and any("Моя правка синтеза" in p.read_text(encoding="utf-8") for p in (prog / "prompts" / "_прежние").glob("Синтез*.md")),
       "изменённый в новой версии промпт обновлён, ваша правка — в prompts/_прежние")
    ok("Моя правка классификации" in (prog / "prompts" / "Классификация.md").read_text(encoding="utf-8")
       and not list((prog / "prompts" / "_прежние").glob("Классификация*.md")), "промпт, который новая версия не меняла, остался вашим")
    ok((plug / "main.js").read_text(encoding="utf-8") == "// плагин 9.9.9" and json.loads((plug / "data.json").read_text(encoding="utf-8"))
       == {"programDir": "x"}, "плагин в хранилище обновлён, его настройки (data.json) — нет")
    st = json.loads((prog / "installed.json").read_text(encoding="utf-8"))
    ok(st["version"] == "9.9.9" and "prompts/Синтез.md" in st["files"], "installed.json: версия и отпечатки файлов")
    ok(any("_прежние" in n for n in r["notices"]), "в итоге сказано, где ваши прежние промпты")
    out, r = brain(prog, "update", "--check")
    ok(r["title"] == "Последняя версия" and not r["update"]["newer"], "повторная проверка: уже последняя версия")

    print("=== Репозиторий без релизов: версия из ветки")
    new2 = T / "repo"
    copy_program(new2 / "app")
    (new2 / "app" / "brain" / "__init__.py").write_text('__version__ = "9.9.10"\n', encoding="utf-8")
    (new2 / "README.md").write_text("# репозиторий", encoding="utf-8")
    FILES["/repos/user/brain2"] = (200, b'{"default_branch": "main"}', "application/json")
    tree = {"tree": [{"path": "README.md", "type": "blob"}, {"path": "app/brain/__init__.py", "type": "blob"},
                     {"path": "app/tests/brain/__init__.py", "type": "blob"}]}
    FILES["/repos/user/brain2/git/trees/main?recursive=1"] = (200, json.dumps(tree).encode(), "application/json")
    FILES["/repos/user/brain2/contents/app/brain/__init__.py?ref=main"] = (200, b'__version__ = "9.9.10"\n', "text/plain")
    FILES["/repos/user/brain2/zipball/main"] = (200, make_zip(new2, "user-brain2-abc123"), "application/zip")
    (prog / "settings.yaml").write_text(settings.replace("user/brain\"", "user/brain2\""), encoding="utf-8")
    out, r = brain(prog, "update", "--yes")
    ok(r["installed"]["version"] == "9.9.10" and r["update"]["source"] == "branch" and r["update"]["branch"] == "main"
       and '"9.9.10"' in (prog / "brain" / "__init__.py").read_text(encoding="utf-8"), "без релизов: версия и архив ветки по умолчанию")
    ok(not (prog / "README.md").exists() or (prog / "README.md").read_text(encoding="utf-8") != "# репозиторий",
       "файлы вне папки программы в репозитории не ставятся")

    print("=== Ошибки")
    (prog / "settings.yaml").write_text(settings.replace("user/brain\"", "user/nope\""), encoding="utf-8")
    out, r = brain(prog, "update", "--check", expect=1)
    ok("не найден" in r["error"], "нет такого репозитория → понятная ошибка")
    (prog / "settings.yaml").write_text(settings.replace("https://github.com/user/brain", "не ссылка"), encoding="utf-8")
    out, r = brain(prog, "update", "--check", expect=1)
    ok("GitHub" in r["error"], "ссылка не на GitHub → понятная ошибка")
    (prog / "settings.yaml").write_text(settings.replace("https://github.com/user/brain", ""), encoding="utf-8")
    out, r = brain(prog, "update", "--check", expect=1)
    ok("Не указан репозиторий" in r["error"], "репозиторий не указан → подсказка, где его указать")
    (prog / "github_token.txt").write_text("ghp_test\n", encoding="utf-8")
    (prog / "settings.yaml").write_text(settings, encoding="utf-8")
    SEEN.clear()
    brain(prog, "update", "--check")
    ok(SEEN and all(a == "Bearer ghp_test" for _, a in SEEN), "токен GitHub (для закрытого репозитория) уходит в запросы")
    srv.shutdown()
    print("\nОбновление в порядке.")


if __name__ == "__main__":
    main()

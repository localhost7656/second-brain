# Second Brain plugin — source code

The built plugin is included in the program's `plugin` folder. `Install.bat` installs it using the `setup` command; alternatively, run `python -m brain install-plugin`. You only need this source folder if you want to modify the plugin.

## Build

Install Node.js 18 or newer, then run in this folder:

```sh
npm install
npm run build
```

The build checks TypeScript types, bundles `src/*.ts` into `../plugin/main.js`, and places `manifest.json` and `styles.css` alongside it. Run `Install.bat` again (or `python -m brain install-plugin`) and restart Obsidian, or disable and re-enable the plugin in settings.

## Architecture

- `src/main.ts`: plugin commands, panel, status bar, reading the `.system/ui.json` snapshot, YAML editing through the Obsidian API, Windows notifications when the window is not focused, and update checks and installation. The Obsidian restart command uses `app:reload`.
- `src/engine.ts`: starts the program using `python -X utf8 -m brain --json --vault <vault> <command>`, manages the run queue and stopping (`.system/stop` or immediate interruption), and parses progress events: `@@PROGRESS`, `@@WAIT`, `@@USAGE`, `@@NOTICE`, `@@ASK`, and `@@RESULT`. Answers to prompts during a run are sent to standard input using `--ask-stdin`.
- `src/view.ts`: the current-run panel and Overview, Questions, Container, Expenses, and Log tabs. The container tab includes threshold controls; Expenses includes pricing, historical recalculation, and budget controls.
- `src/settings.ts`: settings UI generated from `brain settings`, including search, model profiles, per-step models, default-value resets, validated autosave, and local embedding-model controls. The update repository is configured in `brain/__init__.py` as `UPDATE_REPO`, and supplied to the plugin as `settings.update_repo`.
- `src/modals.ts`: confirmation, choice, container picker, new-thought, AI threshold-advice and connection-check dialogs. `LlamaModal` configures and starts the local embedding model with `llama start --params-json -`.
- `src/report.ts`: plugin error capture, error display, `_logs/plugin.log`, and developer reports.
- `src/types.ts` and `src/util.ts`: snapshot types and helper functions.
- `styles.css`: uses Obsidian theme variables for light and dark themes; the panel adapts to a narrow sidebar using `@container`.

**Class member names:** Plugin classes inherit from Obsidian classes such as `Plugin`, `PluginSettingTab`, `ItemView`, `Modal`, and `FuzzySuggestModal`. Do not give custom fields or methods the same names as internal Obsidian members. Obsidian 1.13+ introduced `renderTab()` and `navEl` in settings tabs, and matching plugin members in version 2.5 broke the settings window. Use the public API in `obsidian.d.ts` and lifecycle methods Obsidian expects, such as `onload`, `display`, and `onOpen`. `tests/run_real.py` checks this in step 10.

Parsing is done by the Python program in `brain`, not by the plugin. Plugin-facing commands include `snapshot`, `answer`, `advise`, `settings`, `install-plugin`, `usage`, `estimate`, `update`, and `llama` (`status`, `start`, `stop`, `download`), as well as `run`, `synth`, `revalidate`, `patterns`, and `check`. With `--json`, the program prints progress and finishes with an `@@RESULT {…}` line.

## End-to-end test

`tests/run_e2e.py` runs the built plugin in Chromium with a simulated Obsidian API (`tests/obsidian-mock.js` and `tests/harness.html`), the real Python program, and the simulated model (`tests/fake_llm.py`). It covers the first-import wizard, structure approval, questions, thresholds and AI advice, styles, Phase 2, new thoughts, settings and profiles, progress, stopping, costs and budget, notifications, logs, dark mode, plugin installation, simulated GitHub updates, and local embedding-model setup and download. Screenshots are saved in `<folder>/shots`.

```sh
pip install pyyaml requests numpy dulwich playwright
playwright install chromium
python tests/run_e2e.py /tmp/e2e
```

This test is intended for Linux or macOS and prepares a test copy of the program with `.venv/bin/python`.

## Test in real Obsidian

The mock only implements the parts of Obsidian it knows about. `tests/run_real.py` also tests the plugin in real Obsidian for Linux using a virtual display (Xvfb) and the Chromium debugging protocol. It covers installation and trust, the wizard, Phase 1, structure approval, panel and settings tabs, search, thresholds, profiles, connection checks, new thoughts, container selection, error reporting, clipboard, console output, and class member names.

```sh
# Extract an Obsidian for Linux archive from github.com/obsidianmd/obsidian-releases.
pip install pyyaml requests numpy dulwich playwright
python tests/run_real.py /path/to/obsidian-1.15.0 /tmp/real
```

Xvfb is required. Set `REAL_KEEP=1` to leave Obsidian open after the test. Screenshots are saved in `/tmp/real/shots`.

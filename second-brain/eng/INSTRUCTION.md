# Second Brain — User Guide

Second Brain organizes notes into projects and writes documents from them. The program interface is in English. Model-generated content is intended to follow the language of the relevant source notes; for mixed-language material, the prompts prefer the predominant language, or the most recent relevant note if there is no clear majority. Model behavior depends on the provider and model. The required Summary filename and other machine-readable markers stay in English. Place text files in the `_staging` folder of an Obsidian vault and run **Phase 1**. With a language model, the program identifies which projects the thoughts belong to, places the entries, and builds a synthesis base. **Phase 2** uses that base to write project documents: a required Summary and, when useful, other documents such as a diary.

Everything is stored as ordinary files in your vault. Entries are not deleted: outdated material is marked, and previous document versions are retained. If the program is unsure, it asks a question instead of guessing; your answer is then applied.

The Obsidian plugin provides a right-hand panel, settings, and commands. `Install.bat` installs the program's requirements and the plugin; running it again repairs the installation.

## 1. Installation

1. **Create or open an Obsidian vault.** The program creates its own working folders.
2. **Extract the program archive** to a separate permanent folder, for example `D:\Programs\Second Brain`. Do not put the program folder inside the vault: the program could mistake its own files for notes.
3. Double-click **`Install.bat`**. Internet access is required. The installer:
   - Finds Python 3.10 or newer. If it cannot find Python, it asks permission to install Python 3.12 for your Windows user. Enter `Y` for yes or `N` for no. It uses winget when available, otherwise the installer from python.org; administrator rights are not required. If you install Python yourself, select **Add python.exe to PATH**, then rerun `Install.bat`.
   - Creates a `.venv` environment, `settings.yaml`, and an empty `api_key.txt` if they do not already exist.
   - Finds your Obsidian vaults and asks where to install the plugin. Press Enter for the first, enter a number, paste a vault path, or drag the vault folder into the window. If Obsidian is open, it asks you to close it.
   - Offers to download the KaLM-Embedding-Gemma3 12B embedding model (about 7 GB) and llama.cpp (about 30 MB). Embeddings help find similar thoughts and duplicates. You may do this later; the model can be downloaded on its first start from Obsidian. The embedding model runs locally, so texts used to calculate embeddings are not sent elsewhere.
   - Opens Obsidian.
4. If Obsidian asks whether to trust the vault author, select **Trust author and enable plugins** only if you trust the archive and its plugins; otherwise use Restricted Mode. The Second Brain plugin cannot run in Restricted Mode. The Second Brain panel should appear on the right; the brain icon on the left opens it. If it does not appear, exit Restricted Mode under Settings → Community plugins and enable Second Brain.

If setup reports an error, fix the cause and run `Install.bat` again. It preserves settings, keys, and notes, and reinstalls dependencies and the plugin. Rerun it after moving the program folder, reinstalling Python, creating a new vault, or if the plugin stops starting. Legacy batch files for individual actions are removed because those actions are now available in the panel.

## 2. Configuration

Open Settings → **Second Brain**, or use the gear in the panel. The settings tabs are General, Models, Thresholds, Incoming, Documents, Expenses, and Advanced. Search finds settings by name or description across tabs. Changes are saved automatically to `settings.yaml` in the program folder; the previous version is kept as `settings.yaml.bak`. The ↺ control restores a default value and is inactive when that value is already in use.

1. **General → Program:** `Install.bat` fills in the program and Python paths. A green status indicates that the program was found.
2. **Models → Language model:** choose the mode: cloud API, a local model server, or manual web chat. Model profiles hold the address, model, key, parameters, and prices. The Z.ai cloud profile is provided; select it for editing and enter the provider's exact model name and API key. The standard Z.ai address is `https://api.z.ai/api/paas/v4`; GLM Coding Plan uses `https://api.z.ai/api/coding/paas/v4` (check your provider account). Save the key: it is stored beside the program, not in the vault. Optional input, cached-input, and output prices are dollars per million tokens and enable cost calculations.
3. Use **＋ Cloud**, **＋ Local**, or **Copy** to add profiles. Select the active cloud or local profile under the mode. Individual steps can use different profiles: for example, a stronger model for synthesis and a faster model for classification. Each profile has its own key; a shared key is not sent to another provider's address. If profiles share a key file, replacing its contents affects every profile that uses it. Use **Separate key** to assign a separate file; deleting a profile does not delete its key file.
4. **Models → Embeddings:** start the local model and choose CPU or GPU and other parameters. The program downloads missing components and fills in the server address. You can instead use your own embedding server or a cloud provider. Changing the embedding model triggers a vector rebuild on the next Phase 1 run.
5. Select **Check connection** to check the vault, language models used by steps, and embeddings.

Other settings cover global thresholds, incoming sources and dialogue markers, document style, budgets and estimates, Windows notifications, updates, and advanced limits. Each field has an explanation.

To edit `settings.yaml` manually, change only values after colons and preserve indentation using spaces, not tabs. Text after `#` is a comment. Check the connection after editing. If the settings file is missing, the program creates it from `settings.template.yaml`.

## 3. Embeddings and local models

The built-in embedding model is **KaLM-Embedding-Gemma3 12B** (`KaLM-Embedding-Gemma3-12B-2511.Q4_K_S.gguf`, about 7 GB), run through llama.cpp. In Models → Embeddings, select the local option and **Start model…**. The dialog shows CPU, memory, and GPU information and lets you choose:

- **CPU or GPU.** A GPU is much faster. Running this model on a CPU requires at least 16 GB RAM; the dialog warns if less is available.
- For GPU, the llama.cpp build and number of model layers. Automatic selection uses CUDA for NVIDIA and Vulkan otherwise; layers that do not fit on the GPU run on the CPU.
- **Context:** the maximum text read at once. Approximate memory requirements are 8.4 GB at 4096 tokens (default, about 12,000 characters), 9.6 GB at 8192, and 12.6 GB at 16384. The program truncates longer embedding inputs. KV-cache quantization has little effect for this model because it does not retain the cache; leave it at `f16`.
- CPU threads (`0` lets llama.cpp choose; the core-count option uses the number of processor cores), port, idle unload time (15 minutes by default; `0` disables unloading), automatic startup, and model folder.

**Start** downloads missing files, starts the server, and writes its address into settings. Stop interrupts a download; the next run resumes it. If Microsoft Visual C++ libraries are missing, the program offers to install them and Windows asks for permission. After a computer restart, the program can start the server automatically when Phase 1 or a connection check needs it. **Stop** releases memory. The model is stored in `models` and llama.cpp in `llama.cpp` within the program folder.

### Local language model (optional)

You can run your own language model separately using llama.cpp. Download a Windows build and a `.gguf` model, then start the server from its folder, for example:

```sh
llama-server -m model.gguf -c 16384 --port 8080
```

Keep the server window open. `-c` sets the context window in tokens; add `-ngl 99` if the model fits in GPU memory. Create a local profile in Models, set the server address to `http://127.0.0.1:8080/v1`, and enter a model name. A key is unnecessary unless your server requires one. Select the local mode to use this profile for the whole program, or keep cloud mode and assign the local profile to individual steps.

For a smaller context, set the profile's request limit to roughly three characters per token: about 40,000 characters for `-c 16384`. Structure, Classification, and Pool analysis split long material automatically. If a request still does not fit, the program identifies the step and suggests a correction. Local model use records tokens and time, but not a monetary charge.

For a separate embedding server, enter its address and model name in Embeddings. The program recalculates vectors when the model name changes; it does not start or stop your external server.

## 4. The Second Brain panel

Open the panel using the brain icon or the Second Brain command in Obsidian. The top shows program status, refresh, and settings. Its tabs are:

- **Overview:** counts, primary actions, model and monthly spending, and the container tree. The first import includes a step-by-step wizard.
- **Questions:** questions that need an answer.
- **Container:** the selected container or the container of the open note, its documents, thresholds, and style.
- **Expenses:** requests, tokens, time, costs, prices, and budget.
- **Log:** results of runs in this session and links to program logs.

While the program runs, the panel shows the stage, progress, elapsed time, an approximate remaining time after the first item completes, the current model request, and the run's token and cost totals. Manual web chat has no time estimate. **Stop** finishes the current step and saves progress; **Stop immediately** interrupts the current model response but retains previously saved work. The next run resumes. Program output can be expanded in the panel.

Some decisions, including large-run confirmation and budget exhaustion, are requested in a dialog during a run. Closing the dialog is equivalent to declining. Optional Windows notifications report long runs (over two minutes by default) and questions when Obsidian is not focused; configure and test them in General → Windows notifications. If no notification appears, allow Obsidian notifications in Windows Settings → System → Notifications.

The Obsidian status bar shows a brief status; click it to open the panel. Actions are also available in the command palette (Ctrl+P); assign shortcuts in Obsidian's Hotkeys settings.

## 5. First import

1. Place older `.txt` files in `_staging/archive/`. Subfolders can identify sources, for example `_staging/archive/Chat with AI/` or `_staging/archive/Telegram/`. Sources have colors in views and may adjust how readily noisy text is compacted; configure them under Incoming → Sources.
2. The program takes an entry's date from the first line (`dd.mm.yyyy`) or, if absent, from the file date. Dates within the text are content. Date headings are recognized in numeric format and with English or Russian month names; use numeric dates for other languages. A diary whose entries begin with dates such as `12.03.2021`, `2021-03-12`, or `12 March 2021` can be split automatically, including date headings and dates with weekdays or times. Chronological long paragraphs beginning with dates also work. The original stays intact in `_sources`. AI dialogues are not split by date; the setting can be disabled in Incoming.
3. Select **Start Phase 1**. The program reads the archive and creates `_structure (draft).md` at the vault root, then waits for approval. Large imports may show an estimate and ask for confirmation.
4. Open the draft and review the whole tree. Rename, indent, unindent, remove, merge, or add lines. For example:

   ```text
   - Book club (project) — discussion group | apply: Reading; Community
   ```

   Types are `project`, `sprout`, or `question`. The `| apply:` part is optional. Do not change markers such as `<!-- n1 -->`; they allow the program to identify renamed containers. Newly added lines need no marker. Existing containers marked with `k` cannot be deleted from the draft.
5. Select **Approve structure**. The program creates containers, splits multi-topic bulk-import files into separate entries when appropriate, places entries, extracts thoughts, and builds synthesis bases. A large archive may take hours. Progress appears in the panel. You can stop safely and resume without repeating saved work.
6. Review the **Questions** tab.

## 6. Adding notes

- Use **New thought** in the panel or command palette. Enter the text and optionally a destination, date, and source. **Process immediately (Phase 1)** is off by default; otherwise the thought waits for the next run. The note is placed in `_staging`.
- Alternatively, place `.txt` or `.md` files directly in `_staging` or in a source subfolder. A file may begin with an optional header:

  ```text
  12.03.2025
  hint: Book club

  Note text…
  ```

  The first line is the date. `hint:` suggests a container or topic; it raises the model's confidence but is not an instruction. If the content conflicts with the hint, the program asks. Leave a blank line after the header.
- Mark dialogue lines with `Me:` and `AI:` at the beginning of each line. These markers can be configured in Incoming settings. The parser and model instructions recognize all configured prefixes. Add the speaker prefixes used by your notes when importing dialogues in other languages.
- Images and other unsupported files remain in `_staging`; the program reminds you about them.
- Run Phase 1 whenever convenient. Until processing, a file in `_staging` is a draft you can edit freely; the Phase 1 button is highlighted when new files are waiting. After processing, original files move unchanged to `_sources`; entries appear in the container's `_record` folder. Entries waiting for an answer are in `_review`; unassigned entries are in `_unsorted`.

## 7. Answering questions

Use the **Questions** tab to select an option or enter a free-text answer. It is applied immediately, or queued until the current run finishes. The same questions appear in `open-questions.md`. In that file, check one option with `x` or Cyrillic `х`, or write after `Answer:`; those answers are applied on the next Phase 1 run. If two options are checked, the program warns and leaves the question open. Answered questions are archived in `_logs/file.md`.

For a placement question, you can enter a container name. If it does not exist, a new project is created; specify another type in parentheses, for example `Balcony garden (sprout)`. For contradictory thoughts, choose which is correct or choose the fork option if both are valid.

## 8. Phase 2: documents

Select a container and use **Write documents (Phase 2)**, or start Phase 2 from Overview and choose a container. The model writes the required **Summary** and any other useful documents in that container. If nothing has changed, it asks whether to rewrite anyway. If the synthesis base needs rebuilding, run Phase 1 first.

You can edit generated documents. On the next Phase 1 run, the program detects the edit and turns it into an entry so future versions can incorporate it. If an important detail disappears from a new version, the program asks whether that is intended, should be restored next time, or whether to roll back. Previous versions are saved.

Set a global style in settings, a container style on its Container tab (added to the global style and inherited by child containers unless overridden), and a single-document style using `style_override` in its YAML properties.

## 9. Container thresholds and AI advice

Thresholds control when the program acts without asking, possible duplicates, and which aspects are valuable enough for the synthesis base. Global values are in settings; containers can override them.

On **Container → Container thresholds**, move a slider or enter a value and save. It applies to the container and its children. The indicator shows whether a value is custom, inherited, or global; ↺ removes a custom value; leaving a value empty uses the inherited or global value. Placement and compaction thresholds affect new entries. Value thresholds rebuild the synthesis base on the next Phase 1 run without model requests.

**Consult AI** analyzes previous placement, questions, and corrections and proposes values with explanations in one model request. Select the recommendations you agree with and apply them; nothing changes without your approval. Advice remains in the Container tab after the dialog closes. Custom thresholds are also stored in the container's `thresholds` YAML property.

## 10. Expenses and budget

Each model request records its profile and step, input and cached-input tokens, output tokens, and duration. Costs use profile prices at the time of the request. Changing prices does not automatically alter historical costs; the program offers to recalculate them. Configure input, cached-input, and output prices per million tokens in a cloud profile or the Expenses panel. If cached-input pricing is blank, the ordinary input price is used. Without prices, tokens remain visible and monetary totals are marked as incomplete. Local models show tokens and time but have no charge.

The Expenses tab shows totals for the current or previous month, model cards, steps, daily costs, and recent runs. The monthly budget covers all cloud models; an optional profile limit can also be set. By default the program warns at 80% and, at 100%, pauses before the next paid call and asks whether to continue to the end of the run or stop. Progress is saved on stopping.

Before Phase 1, Phase 2, and revalidation, the program estimates calls, time, and cost. By default it asks for confirmation above 30 calls, $0.50, or 10 minutes; revalidation always asks. Estimates use past runs or initial averages and are approximate. Configure thresholds and the switch under Expenses.

## 11. Updates

The GitHub repository address is set in `brain/__init__.py` as `UPDATE_REPO`. When configured, the plugin checks at Obsidian startup and offers to install, postpone, or skip a version; you can also use **Check for updates** in General → Updates. The repository must be public. Updates come from the latest release, or the default branch if there is no release. A skipped version will not prompt again, but the next version will. If `UPDATE_REPO` is empty, the check button is disabled. A release distributor can enter an address such as `https://github.com/name/repository` before packaging; the configured address is preserved during updates.

Updates replace program, plugin, installer, and guide files but preserve `settings.yaml`, keys, and the vault. Edited prompts are preserved; when an updated version changes a prompt, the previous custom version is saved under `prompts/_former`. New Python dependencies are installed as needed, and the plugin offers to restart Obsidian.

**Important for this English build:** an update from a repository containing the Russian edition can replace the translated files. Only update from an English-compatible release. For a manual update, close Obsidian and back up the program folder, vault, settings, keys, and customized prompts. Do not overwrite your settings, keys, or installation state with files from an archive. This build is for a fresh test installation only; do not use it to update an existing installation.

## 12. Manual editing and safety

A container note's YAML properties include `type` (`project`, `seed`, or `question`), `parent` as `[[Name]]`, `applies_to`, `color`, `container_status` (`active`, `dormant`, or `completed`), and `description`. Thresholds and style can also be set via the panel. Text outside the program-managed block belongs to you.

Rename a container by renaming its note, not the folder; the program moves the folder and updates links. To create one manually, create a note with a `type` property. If it is inside another container's folder, it becomes a child; Phase 1 assigns its location and working fields.

For entries, changing `container` moves an entry and records a correction; `also_in` shares it, and `conflicts_with` links a contradictory entry. Set `status: outdated` instead of deleting an entry; set `status: processed` to restore it.

Do not delete processed entries: they are linked to other records and needed for reconstruction. Mark them outdated instead. Do not edit already processed entry text. If you do, the program asks whether to create a new entry from the changed sentences. To add a thought, place a new note in `_staging`. Do not edit the generated `_aspects.md` and `_synthesis.md` views or modify `.system`.

## 13. Manual web chat

In Models, select manual web chat as the mode, or assign it to an individual step. Start a phase. The program creates a request file and an empty answer file in `_web-chat` and waits. Use the panel buttons to open the request and answer files. Copy everything below the request’s copy marker into the model's chat. Paste the complete response into the answer file and save it, then continue or rerun the phase. If the answer is invalid, the request file explains what to fix. Completed pairs move to `_web-chat/ready/`.

Each model call requires a separate exchange, so large imports take time. Embeddings are still required; the default embedding model runs locally, though an external or cloud embedding service can be configured.

## 14. Troubleshooting

- **Interrupted run:** start again; completed work is saved and processing resumes.
- **Plugin cannot find the program:** rerun `Install.bat` from the new program folder or correct its path in General → Program.
- **Vault already in use:** only one program instance can work with a vault at a time. Wait for the other run, including one started from another Obsidian window.
- **Embedding model unavailable:** start it from Models → Embeddings. If it will not start, check available memory, choose a GPU or smaller context, change an occupied port, or update the GPU driver. The model server log is available beside the controls. For an external server, start it separately and check the connection.
- **Truncated model response:** increase the profile's response token limit (`max_tokens`) or clear it to use the provider default. For GLM, `{"thinking": {"type": "disabled"}}` can disable lengthy reasoning.
- **Request exceeds context:** reduce the assigned profile's request limit or start your local server with a larger `-c`.
- **Budget exhausted:** increase the budget or rerun and choose to continue to the end of the run.
- **Update failed:** check connectivity and the repository address, or update manually from an archive.
- **Settings error:** the program reports a line number. Check indentation and quotation marks; the previous file is `settings.yaml.bak`.
- **Plugin error:** copy the report from the red error box and send it to the developer. Other areas continue working. The full developer report includes versions, recent errors, and run output. Review it for sensitive information before sharing; create it from Advanced settings or the command palette.
- **Plugin missing or not starting:** rerun `Install.bat`.

Obsidian may remain open while the program runs. The program retries if Windows briefly locks a file, for example during antivirus scanning or synchronization.

## 15. Files and backup

In the vault:

- `_staging/`: incoming files; `_staging/archive/`: bulk imports.
- `Container/Container.md`: container note; `_record/` contains entries; documents and the generated `_aspects.md` and `_synthesis.md` are alongside it. Child containers are nested folders.
- `_shared/`, `_unsorted/`, `_review/`, and `_sources/`: shared entries, unassigned entries, entries awaiting answers, and unchanged originals.
- `open-questions.md`, `_structure (draft).md`, `_logs/`, and `_web-chat/`: questions, the proposed tree, logs, and manual-chat files. The logs include change and reasoning logs, archived questions, errors and plugin diagnostics; `_logs/plugin.log` records plugin errors and `_logs/developer-report.md` contains the developer report.
- `.system/`: working data, including pools, synthesis bases, vectors, version history, usage, and panel state. Do not modify it.
- `.obsidian/plugins/vtoroy-mozg/`: installed plugin.

In the program folder: settings and their template, profile key files, `models/`, `llama.cpp/`, `prompts/`, `plugin/`, `installed.json`, `Install.bat`, and `.venv/`.

For backup, copy the entire vault including hidden `.system`, and separately back up `settings.yaml` and your key files.

## 16. Colors

Container folders and entries use the container color; shared entries use a mixed color. The program creates `.obsidian/snippets/vtoroy-mozg.css` and enables it on first run. If colors are missing, enable the `vtoroy-mozg` CSS snippet in Obsidian Settings → Appearance.

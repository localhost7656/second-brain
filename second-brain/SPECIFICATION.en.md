# Second Brain — Specification

[Русский](SPECIFICATION.ru.md) · [English](SPECIFICATION.en.md) · [Español](SPECIFICATION.es.md) · [Українська](SPECIFICATION.uk.md)

Program version: **2.7.1**

Second Brain is a program for Obsidian that sorts notes and raw thoughts into projects and writes documents about them with the help of a language model. The user drops text files into the vault's input folder. The program determines which project each thought belongs to, breaks it down into units of meaning, finds duplicates, contradictions, and outdated material, assembles a "synthesis base" for each project, and uses it to write documents: the mandatory "Summary file" («Сводный файл») and others — whichever ones this particular material needs.

This document describes how the program is built and how it works internally: what the model decides, what the code decides, what the human decides, and why. It is for those who want to understand the program, verify its behavior, or extend it. Step-by-step instructions for using the program are in the guide `ИНСТРУКЦИЯ.md` in the program folder.

Conventions:

- Names of folders, files, YAML fields, commands, and values are set in `monospace` — exactly as in the program.
- Thresholds are given with their default values. All of them can be changed in the settings (section 17), and most of them can also be set separately for a container.
- "Model" without qualification means the language model (LLM). The embedding model is always named in full.
- "Section 6.4" refers to a section of this document.
- All example projects and entries are fictional.
- The program's interface, its prompts, and the names of the folders and files it creates are in Russian. In this translation, interface labels are translated, and the Russian original is given in «guillemets» where it helps to find a button or a message; names of folders, files, and fields are left as they are, with a translation on first mention.

## 1. Purpose and principles

### 1.1 Purpose

A personal knowledge base for someone with many intertwined projects and ideas. You can record anything at any time: a short thought, an exported conversation with an AI, a diary spanning several years. Nothing gets lost, and there is no need to keep the structure in your head: the program takes over sorting material into projects, linking it, and bringing it together into coherent text.

The program is open and not tied to a single model. The user chooses the language model: a cloud model via API, their own model on this computer, or manual work through a web chat (section 13). The goal is twofold: to take over the complex logical work with projects and to lower the entry barrier for people unfamiliar with Obsidian. At the same time, the program does not turn into a "black box": the user understands the basic principles of how it works and can always see what was done and why.

### 1.2 Principles

1. **A single entry point.** Information enters the system only through the `_staging` folder (section 4). There is no bypass for any source, so every input is processed the same way and leaves the same trail.
2. **Nothing is deleted.** Outdated, rejected, and duplicate material is marked and remains available (section 11.1). Original files are stored unchanged.
3. **The model evaluates, the code decides, the human confirms.** The model returns assessments: confidence, value, noisiness. The code makes the decision by comparing the assessment with a threshold. Everything below the threshold and everything disputable becomes a question for the user (section 7). Wherever a mistake would cost meaning, the model decides nothing on its own.
4. **Only the human writes the text of thoughts.** The model does not rewrite entries or make up thoughts for the author. A processed entry is not edited: changing a thought means adding a new entry (section 4.3). The version condensed by the model is stored separately from the original text.
5. **Raw material and product are different things.** Aspects — atomic units of meaning — are extracted from entries (section 5). The selected aspects are assembled into a synthesis base, from which the model writes documents (section 8): standalone coherent text, not a retelling of the aspects one by one. Just as the sources of a term paper and the term paper itself are different things.
6. **Everything is stored as ordinary files.** Entries, project cards, and documents are Markdown with a YAML header in the Obsidian vault; working data is JSON in the hidden `.system` folder. No database server is needed: the vault is copied and synchronized like an ordinary folder.
7. **Runs only on command.** The user starts the phases — no schedule and no background processing. Interrupting is safe: the state is saved after each step, and a repeated run continues from the same place (section 11.3).
8. **Quality matters more than saving tokens.** Prompts are not trimmed for length. If the material does not fit into the model's window, the code splits it into parts. Costs are limited in money: a monthly budget and an estimate before a large run (section 14).
9. **Privacy by default.** By default, embeddings are computed on this computer (section 12). API keys are stored next to the program, not in the vault, and are not synchronized.
10. **Every assumption is checked.** Wherever the system assumes and the human decides, the "assumption — decision" pair is written to the reflection log (section 15.3). The thresholds are tuned using these statistics (section 10.5).

### 1.3 Components

- **The program** — the Python package `brain` in the program folder. It performs all operations on the vault, calls the models, asks questions, and applies answers. It is started with `python -m brain <command>` commands (section 20). The user usually doesn't need it directly: the plugin calls it.
- **The Obsidian plugin "Second Brain"** («Второй мозг», folder `.obsidian/plugins/vtoroy-mozg/`) — the panel, the settings window, commands, and windows such as "New thought" («Новая мысль»). The plugin itself does not change any data: it reads the state snapshot `.system/ui.json` and runs the program's commands (section 18).
- **The Obsidian vault** — all of the user's data and the program's working data (section 3).
- **Models.** A language model is needed wherever text has to be understood (section 13). An embedding model is needed to find similar material (section 12). By default this is a local model on this computer: KaLM-Embedding-Gemma3 12B on llama.cpp.
- **Prompts** — the task texts for the model, one file per step, in the program's `prompts/` folder (section 9).
- **Settings** — the `settings.yaml` file next to the program (section 17).

Overall workflow:

```
_staging/  — new files
  │
  ▼  Phase 1 — processing (python -m brain run)
  answers to questions → manual edits → file intake (copy to _исходники)
  → [bulk load: structure draft → approved by the user]
  → each entry: classification → thresholds → clarifying questions → condensing
                → vectors → extraction of aspects into the container's pool
  → each changed container: pool analysis → value → synthesis base assembly
                → comparison with the previous version of the base
  │
  ▼  Phase 2 — documents (python -m brain synth "Container")
  synthesis base → document synthesis → comparison with previous versions → version in .system/versions

Questions from any step → open-questions.md and the plugin panel →
the answer is applied immediately (from the panel) or at the start of the next Phase 1 (from the file)
```

## 2. Terms

A glossary of the concepts used in this document. If a wording in the text differs from the definition here, the definition prevails.

| Term | Meaning |
| --- | --- |
| **Vault** | The Obsidian folder (vault) the program works with. All data is in it (section 3). |
| **Container** (node) | A node of the project graph at any level: a project, a sub-project, an idea sprout, or a question. Physically, a folder with the container card, entries, documents, and views (section 3.4). |
| **Container card** | The file `Name/Name.md`: the container's properties in the YAML header and the user's text. |
| **Entry** | A unit of information that the program processes: a thought, a diary fragment, a dialog with an AI, a resource, a manual edit of a document, etc. An `.md` file with a YAML header in `_записи/`, `_shared/`, `_unsorted/`, or `_на_проверку/`. In the code and YAML fields — `entity`. |
| **Original** | An input file as it was placed in `_staging`. It is stored unchanged in `_исходники/` (originals); entries link to it. |
| **Segment** | A part of an input file that became a separate entry during a bulk load (section 6.4). Its boundaries are paragraph numbers; the code copies the segment text verbatim, and the model does not rewrite it. |
| **Service header** | Optional first lines of an input file: a date `dd.mm.yyyy` and a hint `hint: …` (section 4.2). |
| **Hint** (`hint`) | The user's indication of where to file the entry. It does not dictate the result but shifts confidence in favor of the indicated option (section 4.4). |
| **Source** (`source`) | Where the entry came from: an archive, a note, an AI chat, etc. Determined by the `_staging` subfolder. Used for navigation and shifts the condensing threshold; it does not affect weights or ranking (section 4.2). |
| **Aspect** | An atomic unit of meaning extracted by the model from an entry: a fact, an idea, a plan, etc. (section 5). It is stored not in the entry but in the container's aspect pool, with a link to the source entry. The main unit of computation: value, duplicates, contradictions, and ranking are all built on aspects. |
| **Simple aspect type** | One of eight fixed types: `fact`, `observation`, `hypothesis`, `idea`, `conclusion`, `question`, `plan`, `judgment` (section 5.1). |
| **Composite aspect** | A bundle of several simple aspects of one container (not necessarily from one entry) that forms a single whole: an experience, a justified decision, a fork. It is assembled according to the composition formula of its type (section 5.2). |
| **Aspect pool** | All simple and composite aspects of a container with their statuses, value scores, and duplicate and contradiction links. The file `.system/data/pools/<id>.json` (section 16.3). |
| **Content value** | A 0–100 score of an aspect in the context of the whole container (the "Value" prompt, «Ценность»). The first ranking axis: it is used to filter elements out and to divide them into primary and secondary (section 6.10). |
| **Priority table** | The order of aspect groups by type in the synthesis base. The second, independent ranking axis (section 5.4). |
| **Pool analysis** | A single model call over the container's entire pool: it finds composite aspects, duplicates, outdated material, contradictions, and structure suggestions (section 6.10). |
| **Synthesis base** | The result of Phase 1 for a container: aspects selected by value, grouped by type and ordered, with contradiction and fork marks. The raw material for documents (section 6.10). |
| **Document** (product) | A text that Phase 2 writes from the synthesis base: the mandatory "Summary file" and additional documents whose set the model determines (section 8). |
| **Summary file** («Сводный файл») | The mandatory document of a container: a general description of the project. |
| **View** | The files `_аспекты.md` (aspects) and `_база синтеза.md` (synthesis base) in the container folder: the pool and the synthesis base in readable form. Read-only — the program rewrites them itself. |
| **Phase 1** | Processing: intake of new files, sorting entries into containers, extracting aspects, assembling synthesis bases (section 6). The `run` command. |
| **Phase 2** | Writing documents for the selected container from its synthesis base (section 8). The `synth` command. |
| **Bootstrap** | Bulk load mode: the container structure does not exist yet or is incomplete. First a structure draft based on all the material, then sorting with long texts divided into segments (sections 6.2–6.3). |
| **Steady-state** | Normal mode: a single new entry is sorted into the existing structure, without division. |
| **Structure draft** | A container tree proposed by the model, which the user edits and approves as a single file `_структура (черновик).md` (section 6.3). |
| **Quarantine** | The `_на_проверку/` folder (for review): entries the program could not sort with confidence. They are waiting for an answer to a question. |
| **Condensing** | Compressing a long or noisy entry text into a dense form before extracting aspects. The original text does not change (section 6.7). |
| **Question** (`needs_review`) | The single confirmation mechanism: the program does not decide anything below the threshold or disputable on its own, but asks the user (section 7). |
| **Duplicate** (`duplicate_of`) | An aspect that matches an earlier one in meaning. Both remain in the pool and go into the synthesis base as a single item (section 6.11). |
| **Outdated** (`outdated`) | A mark on a thought or aspect that newer material or the user has found no longer relevant. Nothing is deleted (section 11.1). |
| **Contradiction** (`conflicts_with`) | Two current aspects of the same type that cannot both be true. The user decides; until the answer, the base proceeds from the model's assumption (section 6.12). |
| **Fork** (branching) | The answer "both are right" («оба верны») to a contradiction: both directions remain in the synthesis base, and the documents follow both (section 10.3). |
| **Sprout** (`seed`) | A container type: an idea that may grow into a project (section 3.3). |
| **On-demand operation** | An action the user starts on top of Phases 1 and 2: revalidation, search for new composite types, threshold advice (section 10). |
| **Model profile** | A set of settings for one language model: address, model, key, parameters, prices (section 13.2). |
| **Manual mode** (web chat) | Working without an API: the program prepares a request as a file, the user carries it over to the model's web chat and returns the answer as a file (section 13.5). |
| **Reflection log** | A machine-readable log of "system assumption — user decision" pairs used to tune thresholds (section 15.3). |
| **Threshold** | A number the code compares the model's assessment with: above it, the action is performed automatically; below it, a question is asked. It can be global or specific to a container (sections 10.5, 17). |
| **State snapshot** | The file `.system/ui.json`, which the program writes after each command. The plugin takes everything it shows from it (section 18.1). |

## 3. Vault

### 3.1 Folders and files

The program works with one Obsidian vault. Service folders and files start with `_` or `.` and are not considered containers. All other top-level folders are containers.

```
Vault/
├─ _staging/                    inbox (section 4)
│   ├─ архив/                   bulk load (archive) — always Bootstrap
│   └─ Чат с ИИ/                any subfolder = a source of entries (here: AI chat)
├─ Book club/                   top-level container
│   ├─ Book club.md             container card
│   ├─ _записи/                 the container's entries
│   ├─ Сводный файл.md          Phase 2 documents
│   ├─ Reading list.md
│   ├─ _аспекты.md              view of the aspect pool (read-only)
│   ├─ _база синтеза.md         view of the synthesis base (read-only)
│   └─ Online meetings/         sub-container: a nested folder with the same layout
├─ _shared/                     entries that belong to several containers
├─ _unsorted/                   entries without a container
├─ _на_проверку/                quarantine: entries waiting for an answer to a question
├─ _исходники/                  input files, unchanged
├─ _структура (черновик).md     draft of the container tree (during a bulk load)
├─ open-questions.md            questions for the user (section 7)
├─ _логи/                       logs for humans (section 15)
├─ _веб-чат/                    manual mode files (section 13.5)
├─ .system/                     the program's working data
└─ .obsidian/
    ├─ plugins/vtoroy-mozg/     the plugin
    └─ snippets/vtoroy-mozg.css colors (section 3.7)
```

Working data in `.system/`:

| Path | What it stores |
| --- | --- |
| `state.json` | Pipeline state: accepted files, stages of entries and containers, queues, text checksums (section 16.7). |
| `questions.json` | Open questions for the user (section 16.6); answered ones move to `_логи/архив вопросов.md` (question archive). |
| `data/pools/<id>.json` | The container's aspect pool (section 16.3). |
| `data/bases/<id>.json` | The container's synthesis base; `<id>.prev.json` is the previous version for comparison (section 16.4). |
| `vectors/` | Vectors at three levels: entries, aspects, containers (section 12.2). |
| `versions/` | A git mirror of the versions of synthesis bases and documents (section 11.2). |
| `composite_types.json` | Composite aspect types added by the user (section 5.3). |
| `reflection.jsonl` | The reflection log (section 15.3). |
| `usage.jsonl` | Log of model calls and their cost (section 14.1). |
| `webchat.json` | Manual mode requests: those waiting for an answer and those already received (section 13.5). |
| `ui.json` | State snapshot for the plugin (section 18.1). |
| `lock`, `stop` | Lock against a second run and the "Stop" («Стоп») flag from the plugin (section 11.3). |

The user doesn't need to go into `.system`. A backup is the entire vault folder, including the hidden `.system`, plus `settings.yaml` and the key files from the program folder.

### 3.2 Project graph

Containers form a hierarchy: a container can have a parent (`parent`), and a parent can have any number of children. Depth is unlimited: nodes appear at any level. Usually the sub-projects are worked out most concretely, while the parent remains a description with a cluster of thoughts for a long time — this is normal.

Besides its parent, a container can be applied in other branches (`applies_to`). That is why the structure is a graph rather than a strict tree. Example: the sub-project "Heart-rate monitor" (measuring the pulse with a phone camera) belongs to the "Running app" project but is also applied in the separate "Sleep tracker" project.

```
Running app
 ├─ entries: thoughts, diary, AI dialogs, resources
 ├─ Heart-rate monitor ─ ─ ─ ─ ─ ─ ─ ─ ┐ applies_to
 │   ├─ entries                        ▼
 │   └─ Summary file, other documents  Sleep tracker
 └─ Routes …                            └─ entries, documents
Book club                   (independent top-level project)
_unsorted                   (entries without a container)
```

The hierarchy is also visible in the folders: a child container is a nested folder of its parent. An `applies_to` link does not change the folders.

Entries without a container are stored in `_unsorted`. It is not a node of the graph: it has no synthesis base and no documents.

### 3.3 Node types

The `type` field in the container card:

| Type | Meaning |
| --- | --- |
| `project` | A project or sub-project of any level. |
| `seed` | Sprout: an idea that may grow into a project. |
| `question` | An open question the user asks themselves. Not to be confused with the program's questions to the user (section 7). |

The type can be written in Russian: `проект` (project), `росток` (sprout), `вопрос` (question) — the program converts it to the standard value.

**Sprout → project.** When material accumulates in a sprout, pool analysis (section 6.10) may suggest turning it into a project. If the model's confidence is not lower than the high threshold (`high`, 90), the program changes the type itself; if it is lower, the program asks.

**"Silent death" of sprouts.** If an active sprout has not received new thoughts for longer than `seed_dormancy_days` days (90; the card's `last_modified` field), the program asks whether it is still relevant: keep it as a sprout, freeze it (`dormant`), or complete it (`completed`). The check runs at the end of each Phase 1 based on the date, without calling the model.

### 3.4 Container contents

Every container, at any level, has the same set:

- **Card** `Name.md` — properties in the YAML header (section 16.1) and the user's text below them. In the text, the program changes only the service block between the lines `<!-- обновляется программой: начало -->` and `<!-- обновляется программой: конец -->` ("updated by the program: start / end"): the number of entries and links to shared entries from `_shared`, to documents, and to views.
- **Entries** in `_записи/` — thoughts, diary, AI dialogs, resources, questions to oneself, manual edits of documents. The kind of entry is the `content_type` field: `thought` (a thought), `diary` (about lived experience: what one did, what happened), `resource` (a link or material to study), `question` (a question to oneself), `ai_dialogue` (a dialog with an AI, section 4.2), `product_edit` (a manual edit of a document, section 8.5); the model may also suggest another short word. The kind of entry does not change the processing path: all entries go through the same steps.
- **Shared entries** — entries that belong both to this container and to others. Physically they are stored once in `_shared/`, and the card of each container links to them. There is no need to edit in several places and no out-of-sync copies. The aspects of a shared entry go into the pools of all its containers, and each container has its own synthesis base.
- **Documents** of Phase 2 — the "Summary file" and additional ones (section 8).
- **Views** `_аспекты.md` and `_база синтеза.md` — the pool and the synthesis base in readable form, with a colored source label on every thought. Read-only: the program rewrites them after each assembly.

The container's aspect pool, synthesis base, and vectors are stored in `.system`.

A diary is not a special kind of entry with its own pipeline. Entries about lived experience go through the same steps as the rest, and the model writes a diary as a document in Phase 2 if the synthesis base contains experience aspects (`experience`, section 5.2). Neither a container nor the vault has a mandatory diary.

### 3.5 Container status

The `container_status` field:

| Status | Meaning |
| --- | --- |
| `active` | In progress (default). |
| `dormant` | Frozen. Entries are still sorted here; sprouts with this status are not checked for "silent death". |
| `completed` | Completed: the outcome is recorded. Work is not blocked — further improvements are possible. In the "Summary file", the model always sets out a "Final result" section («Итоговый результат») separately from the current living description. |

Russian values work too: `в работе`, `заморожен`, `завершён`, and similar forms.

### 3.6 What can be edited by hand

The principle: a field can be edited directly if it is **not computed by the model**. Organizational data — names, links, statuses, colors — belongs to the user. Computed data — pools, synthesis bases, scores — changes only through new input or an answer to a question. A metaphor: the user is the depot manager. They hire staff (choose the models for the steps), repaint the cars, and change the timetable, but they do not rebuild the firebox on the move or switch the points behind the driver's back: they supply new fuel (an entry) or answer the driver's questions.

The program notices manual edits at the start of each Phase 1 and applies them; the result is written to the change log with the mark «пользователь» (user).

**Container card:**

- `type` — project, sprout, or question;
- `parent` — the parent as `[[Name]]`; empty means top level; the folder moves by itself;
- `applies_to` — which other containers it is linked to;
- `color` — the color;
- `container_status` — the status (section 3.5);
- `description` — the description; the program relies on it when deciding what belongs here;
- `thresholds` and `style` — custom thresholds (section 10.5) and document style (section 8.3). They are easier to change in the panel's "Container" tab («Контейнер»);
- the text below the properties — except the service block.

**Renaming.** The name of a container is the name of its card. Rename the file (`Book club.md` → `Reading club.md`), and the folder is renamed automatically and `[[…]]` links are updated. There's no need to rename the folder separately: the program gives it the card's name back.

**A new container by hand.** A note with the container's name and a `type` property (without `id`). The parent is taken from `parent` or from the folder where the note lies. At the start of the next Phase 1, the program gives the container an `id`, a folder, a color, and the missing fields.

If a container card is deleted, its entries move to `_unsorted` with a warning. This is best avoided: it is easier to set a status.

**Entry:**

- `container` — move the entry to another container. The program moves the file and the aspects and records in the reflection log that its sorting was disputed (section 10.2);
- `also_in` — the entry is also needed in other containers: it moves to `_shared`, and its aspects are added to their pools;
- `conflicts_with` — mark that the entry disputes another one: `[[entry name]]`. Such pairs go into the synthesis base as a separate list and are taken into account during synthesis (section 6.12);
- `status: outdated` (or `устарела`) — the thought is no longer relevant: all its aspects are marked outdated. To bring it back, set `status: processed`, and the aspects are restored.

**Cannot be edited directly:**

- **The text of a processed entry** (section 4.3). The program stores a checksum of the text. If the text has changed, it keeps working with the previous text and asks: make a new entry out of the edit, or just restore the original text. While the entry has not gone through all the steps (for example, it is waiting in quarantine), a text edit is accepted.
- **Aspect pools, synthesis bases, and views** — the computed layer, which the program rebuilds itself. A manual edit would conflict with rebuilding.
- **The `.system` folder**.

Entries are not deleted: instead of deleting, use `status: outdated`.

There are three legitimate ways to influence the computed data: (1) a new entry via `_staging`; (2) an answer to a question; (3) a manual edit of a Phase 2 document — it becomes a new entry and goes through Phase 1 (section 8.5).

### 3.7 Colors

- Top-level containers get colors from the base palette in rotation (ten colors).
- Child containers get shades of the parent's color: the color is mixed with white, more strongly the more children the parent already has (from 25% to 60%).
- Entries in `_записи/` are highlighted with the color of their container.
- Shared entries get the average color of all their containers.

The color is the card's `color` field, and it can be changed. The styling is the CSS snippet `.obsidian/snippets/vtoroy-mozg.css`, which the program updates after each command. The program enables it once by itself (`.obsidian/appearance.json`); if the user later disables it, the program no longer touches that setting.

Sources also have their own colors (section 4.2): the thoughts in the views are labeled with them.

## 4. Input: `_staging`

All entries without exception — from a single thought to an archive spanning several years — enter the system through the `_staging` folder. It is a permanent channel: files can be dropped in at any time, and the program accepts them at the next Phase 1.

### 4.1 What can be put there

- **Text files** `.txt` and `.md`, with no required markup: short notes, messenger exports, AI dialogs, a diary spanning years, a long text about everything at once. The program does not read files in other formats: it lists them in a notification and leaves them in `_staging`. Files whose names start with `.` or `~` are skipped.
- **Where to put them** — this determines the source and the mode:

| Location | Source (`source`) | Mode |
| --- | --- | --- |
| root of `_staging/` | `заметка` (note) | determined automatically (section 6.2) |
| `_staging/<subfolder>/` | the subfolder name, for example `Чат с ИИ` (AI chat) | determined automatically |
| `_staging/архив/` | `архив` (archive) | bulk load (Bootstrap) |
| `_staging/архив/<subfolder>/` | the name of the most deeply nested subfolder, for example `Telegram` | bulk load |

- **One file — one note.** There are two exceptions: a diary with dates is split into entries by date (section 4.2), and during a bulk load classification divides a long text into segments by topic (section 6.4). In normal mode an entry stays whole even if it concerns several containers: the link to the others is made through shared entries (section 6.5).

**File intake.** The program reads the file, parses the service header, copies the file unchanged to `_исходники/` under the name `YYYY-MM-DD name` (if the name already starts with a date, a second one is not added), and deletes it from `_staging`. Empty subfolders of `_staging` are removed, except `архив`. An empty file is also saved in `_исходники`, but there is nothing to process in it — a notification says so. Accepted files are marked with a checksum: if a file remains in `_staging` after a failure, it will not be accepted a second time.

### 4.2 File format

**The encoding** is detected automatically: UTF-8 (with or without BOM) or Windows-1251 — typical for old txt files. Line breaks are normalized.

**The service header** — optional lines at the beginning of the file, before the main text (the program looks at the first five non-empty lines):

- a line with a date `dd.mm.yyyy` (optionally followed by «г.», the Russian abbreviation for "year") — the date of the entry;
- a line `hint: …` (or `подсказка: …`) — a hint about where to file the entry (section 4.4).

The program also understands Obsidian's YAML header: the fields `hint` (`подсказка`) and `date`, `created` (`дата`). The program itself writes two more service lines: `content_type: …` — in files it creates from manual edits, and `mode: steady_state` (`режим: одна запись`, "mode: single entry") — in "New thought" files (section 4.5): such a file is always processed as a single entry.

**The entry date** is determined in this order:

1. the date from the service header;
2. if there is none — the earlier of the file's two dates, creation and modification. When copying, Windows sets the creation date to the moment of copying, while the modification date is preserved — that is why the earlier one is taken;
3. dates inside the text are content, not the date of the note: a mention like "meeting 12.05.2025" does not become the entry date.

**AI dialogs** are marked up with turn prefixes at the start of a line: by default `я:` ("me:") and `ИИ:` ("AI:") (the `dialogue_markers` setting; the prefix lists can be extended). A turn lasts until the next prefix. A file containing turns from both sides automatically gets `content_type: ai_dialogue`. For other files, classification suggests the kind of entry (section 6.4).

**Paragraphs.** The code numbers the paragraphs, and all further references to parts of the text are paragraph numbers. A paragraph is a block between empty lines; if the file has no empty lines, each line is a paragraph. A line with a turn prefix always starts a new paragraph. A paragraph longer than 8000 characters is split by lines and sentences — so any file can be broken into portions for the model.

**Source.** It is determined by the file's location (section 4.1) and is needed for two things: labels in the views (each source has its own color) and shifting the condensing threshold (section 6.7). The source does not affect weights or ranking: a diary entry may turn out empty and a random thought very substantial, so priority is built on the aspect's type and value (section 5.4). The list of sources is the `sources` setting: name, color, and `compaction_shift` — how many points to lower the condensing threshold for this source. By default: `архив` and `заметка` — no shift, `Чат с ИИ` — 20 (AI dialogs are usually wordy). To create your own source, it is enough to put files in a subfolder with its name; the settings are needed only if you want a color or a shift.

**Diary by dates.** A file where entries start with a date line (a diary spanning years) is split into several entries, each with its own date (the `input.split_by_dates` setting, enabled by default):

- an entry starts with a line containing only a date: `12.03.2021`, `12.03.21`, `2021-03-12`, `12 марта 2021` (month name in Russian); a day of the week, a time, the word «г.», a `#` heading, or `**` emphasis are allowed. The date line itself does not go into the entry text;
- if there are no such lines — a date at the beginning of a long paragraph (300 characters or more) after an empty line, provided that such paragraphs follow in date order (ascending or descending). The date is cut out of the paragraph;
- text before the first date: if the file header has its own date, it is a separate entry with that date; otherwise a short text (up to 200 characters, usually a title) is attached to the first entry, and a long one becomes a separate entry with the file date;
- not split: files with the service lines `content_type` or `mode: steady_state`, AI dialogs, and files with fewer than two dates (the header date also counts);
- each part is a separate entry with a `source_part` field (the part number and its date). There is one original file, and it is stored whole in `_исходники/`. Then the parts follow the usual path; during a bulk load, classification may divide them further.

### 4.3 Draft and immutability

**Before Phase 1, an entry is a draft.** While the file is in `_staging`, it can be edited freely: add to it, fix a typo, rephrase.

**After Phase 1, the entry text is immutable.** Aspects, duplicates, contradictions, and vectors already refer to the entry; an unnoticed retroactive edit would devalue these links. Changing the content of a processed thought means adding a **new entry** via `_staging`. In Phase 1 the new entry can:

- complement the old one: new aspects are simply added to the pool, and those matching in meaning are linked as duplicates (section 6.11);
- revise it: the program suggests marking the old aspect as outdated (`outdated`);
- contradict it (`conflicts_with`, section 6.12).

**If a processed entry was edited anyway.** The program stores a checksum of the text of each entry. When it notices a mismatch, it keeps working with the previous text and asks a question (section 7):

- "Make a new entry from the edit" («Сделать из правки новую запись») — a file «правка — <запись>» ("edit — <entry>") appears in `_staging`, with a hint pointing to the same container and the mark `одна запись` (single entry). It contains only what changed: «Автор добавил или переписал: …» ("The author added or rewrote: …") and «Автор убрал: …» ("The author removed: …"), sentence by sentence. The original text of the entry is restored from `_исходники`;
- "Just restore the original text" («Просто вернуть исходный текст»).

While an entry has not gone through all the steps (for example, it is waiting for an answer in quarantine), an edit of its text is accepted without a question.

### 4.4 Hints

A hint is a `hint: …` line in the file header (or the "Where to file" field («Куда отнести») in the "New thought" window). Usually it is the name of a container, existing or new. A hint does not dictate the result but **shifts confidence** in favor of the indicated option. The model evaluates, the code decides:

1. The model (the "Classification" prompt, «Классификация») returns two assessments: its own choice of container with a confidence that **ignores the hint**, and separately the confidence for the option from the hint.
2. The code adds `hint_shift` (15 points) to the confidence of the hinted option and compares the result with the threshold:
   - if the model and the hint point to the same thing, the larger of the two scores is taken;
   - if the hinted option passes the threshold with the shift, the entry is filed according to the hint, even if the model's own confidence was below the threshold. For an existing container the threshold is `classification` (70), for a new one `high` (90);
   - if it does not pass even with the shift, the hint contradicts the content. It is neither forced through nor ignored: the entry goes to quarantine with a question for the reason `user_hint_mismatch` — "X is indicated, but the content looks like Y".
3. No hint — the usual threshold rule applies (section 6.5).

The reflection log receives the model's "pure" assessment without the hint — this shows how much the hints actually help (section 15.3).

### 4.5 "New thought"

The plugin's "New thought" command (a button in the panel or the command palette) is the shortest way to record a thought. The window has: the text; "Where to file" — an optional hint with a choice of existing containers; the date (today by default); the source (note or any of `sources` except `архив`); a "Process right away (Phase 1)" checkbox («Сразу обработать (Фаза 1)»), off by default — you can jot down several thoughts and process them all at once. Ctrl+Enter saves.

The plugin saves the thought to `_staging` (or to the source's subfolder) as a file `YYYY-MM-DD HH-MM <start of text>.txt` with a header containing the date, the hint, and the line `mode: steady_state`. That is why such a file is always a single entry: it is split neither by dates nor into segments.

## 5. Aspects

An aspect is a unit of meaning that the model extracts from an entry (section 6.9). It is neither a separate file nor a block inside the entry, but an item in the container's aspect pool (`.system/data/pools/<id>.json`, section 16.3) with a link to the source entry; the entry has back-links `aspect_ids`. All computations are built on aspects: value, duplicates, contradictions, ranking.

Aspects are **not the same** as Phase 2 documents. Aspects are the raw material; documents are the text written from them.

### 5.1 Simple types (level 0)

The list is fixed:

| Type | Essence |
| --- | --- |
| `fact` | A statement of something that happened or exists, without interpretation. |
| `observation` | A noticed detail or regularity; verified less strictly than a fact. |
| `hypothesis` | An untested assumption. |
| `idea` | A proposed direction or solution. |
| `conclusion` | An inference drawn from what came before. |
| `question` | An open uncertainty. |
| `plan` | A declared future action or intention. |
| `judgment` | A subjective assessment or reaction. |

### 5.2 Composite types (level 1)

A composite aspect is a bundle of simple aspects of **one container** (not necessarily from one entry) that forms a single whole. The starting list:

| Composite type | Assembled from |
| --- | --- |
| `experience` | `plan` + `fact` + `observation`/`judgment` + `conclusion` |
| `resolved_decision` (justified decision) | `question` + several `hypothesis`/`idea` + `conclusion` |
| `open_conflict` (fork) | two or more `hypothesis`/`idea` about the same question that do not converge on a common `conclusion` |

An example of an experience in the "Heart-rate monitor" container: the plan "check the measurement in low light" + the fact "under a night light, the pulse jumped by 15 beats" + the observation "the phone's flash stabilizes the signal" + the conclusion "turn the flash on automatically".

The composition formula is not only a type definition but also a working selection algorithm. For each formula, the code selects in advance the free aspects of suitable types (if there are at least two different types among them) and passes these candidates to pool analysis. Whether they add up to a single whole — about one event, question, or decision — is decided by the model (section 6.10). The model first tries to extend an existing composite of the same formula, then to assemble a new one. A composite that no longer holds together (for example, because part of its composition has become outdated) can be dissolved by the model: its parts become free again.

The building blocks of an assembled composite get the status `in_composite`, and the composite aspect as a whole goes into the synthesis base.

**Outdating inside a composite.** If a simple aspect inside a composite is marked outdated, the composite gets the status `needs_review`, and the container gets a full review at the next base assembly: the model extends or dissolves the composite. It does not silently remain irrelevant. In the synthesis base such a composite is marked «на пересмотре» (under review).

### 5.3 New composite types

The list of composite types is open. The model can propose a new type if it notices a recurring bundle of simple types — but only through a question to the user: with the formula, an example of what it would look like, and a justification of why this is a stable pattern rather than a coincidence. The user starts the search (the "Patterns" operation («Паттерны»), the `patterns` command). It runs in two stages so as not to run the model over the entire base:

1. **Technical stage, without the model.** In each container's pool, the free aspects (`active`, not duplicates) are taken. Each aspect is linked to its nearest neighbors (up to six) if the similarity of their vectors is not lower than `pattern_similarity` (0.8). The connected groups are candidates. Suitable groups have three or more aspects of three or more different types, and their set of types does not fit any existing formula. Up to eight of the largest groups are taken, twenty aspects in each.
2. **Content stage, the "New composite type" prompt** («Новый составной тип»). The model receives the existing formulas and the candidate groups and decides whether there is a stable pattern among them. At most two proposals at a time, each one a question to the user. Rejected names are remembered and not proposed again.

A confirmed type is written to `.system/composite_types.json` and from then on takes part in pool analysis on a par with the built-in ones.

### 5.4 Priority table

The table sets the order of aspect groups in the synthesis base — that is, the order in which the groups are given to the model when it writes documents. This is the second, independent ranking axis. The first — content value — divides elements into primary and secondary **within** each group (section 6.10). The table neither replaces nor duplicates it: a valuable urgent plan stands out within its group wherever the group itself is placed.

The table's only criterion is how settled a statement is: first what has already happened or been thought through to the end, then what is less settled.

| Place | Type |
| --- | --- |
| 1 | `resolved_decision` |
| 2 | `fact` |
| 3 | `experience` |
| 4 | `conclusion` |
| 5 | `observation` |
| 6 | `open_conflict` |
| 7 | `hypothesis` |
| 8 | `plan` |
| 9 | `idea` |
| 10 | `judgment` |
| 11 | `question` |

New composite types added by the user are placed right after `open_conflict`.

### 5.5 Aspect statuses

| Status | Meaning |
| --- | --- |
| `active` | A free simple aspect: takes part in the synthesis base on its own. |
| `in_composite` | The simple aspect has become part of a composite; in the synthesis base it is inside the composite. |
| `outdated` | Outdated: revised by newer material or marked by the user. It remains in the pool but does not take part in synthesis. Next to it is what replaced it (`replaced_by`). |
| `needs_review` | Composites only: part of the composition is outdated, and reassembly is needed. |

Regardless of status, an aspect can have a `duplicate_of` mark — a link to an earlier aspect with the same meaning (section 6.11), a value score `value`, and a `pinned` mark — "pinned by the user" («закреплено пользователем», section 6.13). Duplicates become outdated together with the main aspect. If all aspects of an entry are outdated, the entry as a whole gets `status: outdated`.

## 6. Phase 1: processing

Phase 1 (the `run` command, the "Phase 1" button in the panel) turns new files into entries sorted into containers, extracts aspects from them, and rebuilds the synthesis bases of the containers that have changed. It is started manually and can stretch over several sessions: an interrupted run continues from the same place (section 11.3).

### 6.1 Order of steps

Each run goes in this order:

1. **Embedding model check.** If the vectors were computed by a different model, they are recomputed (section 12.2).
2. **Manual edits.** The program applies what the user changed in cards and entries: type, parent, links, statuses, moved entries, containers created by hand (section 3.6). It notices edits to the text of processed entries and asks a question about them (section 4.3).
3. **Answers to questions** from `open-questions.md` (section 7.3). The "assumption — decision" pairs go to the reflection log.
4. **The approved structure draft**, if the user has marked it (section 6.3).
5. **Manual edits of Phase 2 documents** become new entries in `_staging` (section 8.5).
6. **File intake** from `_staging` (section 4.1).
7. **Structure draft** for a new bulk load — Bootstrap, pass 1 (section 6.3). Until the draft is approved, the files of this load wait.
8. **Processing of files**, from old to new by entry date: classification (section 6.4) and thresholds (6.5) create entries, and each one immediately goes through its steps: clarifying questions (6.6), condensing (6.7), vectors (6.8), aspect extraction (6.9). The chronological order is needed so that "newer revises older" matches the real chronology.
9. **Synthesis base assembly** for each container that received new aspects or where statuses changed (section 6.10), and comparison with the previous version (6.13).
10. **"Silent death" of sprouts** — a check of sprouts that have not developed for a long time (section 3.3).

At the end of the run, the program redraws `open-questions.md`, the service blocks of cards, and the colors, commits versions to the git mirror, and writes the snapshot for the plugin.

Each entry has a stage: `classified` → `asked` → `compacted` → `embedded` → `done`; an entry in quarantine has `quarantine` → `quarantine_wait`. A container whose base is out of date has an assembly stage: `analysis` → `value` → `assemble` → `compare`. Stages are saved after each step, so an interrupted run continues from the same entry and the same step.

### 6.2 Mode: Bootstrap or Steady-state

Inside Phase 1 there are two tasks of a different nature — but not two different pipelines:

- **Steady-state** — a single new entry is sorted into the existing container structure. The entry always stays whole.
- **Bootstrap** — there is no structure, or it is known to be incomplete. The material has to be not only sorted, but the containers themselves have to be discovered, and long texts divided into segments by topic. The input here is usually not a scattering of atomic thoughts but a long coherent narrative or a semi-coherent jumble in which project boundaries and links have to be reconstructed.

The mode is determined before classification, because it decides whether the text is divided:

1. **There are no containers yet** (first run) → always Bootstrap.
2. **The file is in `_staging/архив/`** → Bootstrap at the user's explicit indication.
3. **The file is elsewhere in `_staging`** → the mode is not set. Classification guesses it from the size and structure of the text: a long text without explicit markers is closer to a bulk load, a short single thought is obviously Steady-state. If the confidence is below `mode_guess` (70), the file waits for an answer to the question "How to process the file" («Как обработать файл»): divide it into parts by topic or process it as a single entry.
4. **The service line `mode: steady_state`** (this is how "New thought" saves files) → always Steady-state.

A full two-pass Bootstrap (with a structure draft) runs when the vault is empty and for `_staging/архив/`. If Bootstrap is chosen for a file from the root of `_staging` (confidently or after an answer), the file is divided into segments and sorted into the existing structure — without a draft.

### 6.3 Structure draft (Bootstrap, pass 1)

If an archive were sorted one file at a time with containers created along the way, the structure would be set by whichever files came first, and duplicates would easily appear — for example, "Heart-rate monitor" and "project about pulse via camera" as two different containers. That is why a bulk load goes in two passes.

**Pass 1.** The "Structure" prompt («Структура») looks through all the material of the load and proposes a container tree: name, type (`project`, `seed`, `question`), short description, parent, `applies_to` links. If the material does not fit into one request, the code divides it into parts, and each subsequent part refines the draft assembled so far. If a structure already exists, the draft shows it together with the proposed changes.

The draft is the file `_структура (черновик).md`: a nested list of lines like

```
- Running app (проект) — running, workouts, a service for runners <!-- n1 -->
    - Heart-rate monitor (проект) — pulse via the phone camera | применяется в: Sleep tracker <!-- n2 -->
- Sleep tracker (росток) — an idea for a sleep analysis app <!-- n3 -->
```

Nesting is shown by indentation; the type is in parentheses (the program writes it in Russian — `проект`, `росток`, `вопрос` — but also understands `project`, `seed`, `question`); the description follows the dash; after «| применяется в:» ("applies in:") come the links, separated by «;». The service mark at the end of the line is `<!-- k… -->` for an existing container and `<!-- n… -->` for a proposed one: it lets the program recognize a container after renaming, so "applies in" links survive renaming. A line without a mark or with a copied mark is a new container.

The user edits the draft as a single file: renames, re-parents (changes the indentation), merges and deletes topics (when a line is deleted, the entries of that topic are sorted among the remaining ones), changes the type and description. An existing container cannot be deleted from the draft. Approval is the «Структура утверждена» ("Structure approved") checkbox in the same file. This is a single review instead of hundreds of separate questions.

At the start of the next Phase 1, the program applies the draft: it creates new containers, renames and re-parents existing ones, and sets up the links. The approved draft moves to `_логи/` («структура утверждена ГГГГ-ММ-ДД», "structure approved YYYY-MM-DD"), and the outcome — how many containers were proposed and approved, what was deleted, added, renamed — is written to the change log and to the reflection log.

**Pass 2.** The files of the load go through the usual Phase 1 steps according to the approved tree, divided into segments, in chronological order. New containers found along the way are created according to the general threshold rule (section 6.5).

### 6.4 Classification

The "Classification" prompt is called for each new file (or diary part). As input, the model receives:

- the numbered paragraphs of the text (section 4.2);
- the date, the source, the kind of entry if it is already known, the turn prefixes for dialogs, the user's hint;
- the mode (`bootstrap`, `steady_state`, or "not set");
- all containers: `id`, name, type, parent, description, and a brief summary — the beginning of the "Summary file" (up to 1200 characters) or, if there are no documents yet, a summary of the most valuable aspects of the pool. When there are more than `max_containers_in_prompt` (150) containers, the list is narrowed in advance by a vector search on the file text; the parents of the containers found are added for context.

The model returns:

- **segments** — paragraph ranges, each of which becomes a separate entry. Dividing is allowed only in Bootstrap; in Steady-state there is exactly one segment, and it includes all paragraphs. The code copies the segment text from the original verbatim;
- for each segment: the main container — existing (`id`) or new (name, type, presumed parent, description) — with a confidence of 0–100 **ignoring the hint**; the confidence for the hinted option, if there is one (section 4.4); alternatives with confidence; additional containers where the entry also applies, with confidence; the kind of entry (`content_type`) if it was not given in the input; an "incomplete entry" mark (`incomplete`) — a thought lacking explanations that only the author knows; a noisiness score of 0–100 for condensing (section 6.7); reasoning (`reasoning`);
- a guess about the mode with confidence — if the mode is not set.

If the file does not fit into the model's window, the code divides the paragraphs into portions (windows) deterministically — so that after a failure the division is repeated exactly the same way. Each window is classified separately; progress is saved after each window and after each created entry: a failure will not create an entry twice.

The file name of an entry is the date and the first words of the text. The entry gets a link to the original (`source_file`) and, if it is part of a file, the paragraph range (`segment`).

### 6.5 Applying thresholds

The code decides by comparing the model's assessments with thresholds. The thresholds are those of the container where the entry is placed (its own or inherited, section 10.5); for a new container — those of its presumed parent.

| Case | Threshold | At or above the threshold | Below the threshold |
| --- | --- | --- | --- |
| Existing container | `classification` (70) | the entry is filed automatically | quarantine `_на_проверку` and the question "Where to file the entry" («Куда отнести запись») |
| New container | `high` (90) | the container is created automatically, and the entry is placed in it | quarantine and a question with the option "Create …" («Создать …») |
| No container fits | `classification` | the entry goes to `_unsorted` | quarantine and a question |
| Additional container | `high` | the entry becomes shared: it moves to `_shared`, and its aspects are also added to this container | the question "Is the entry also needed in another container?" («Запись нужна и в другом контейнере?») |
| Mode not set | `mode_guess` (70) | the mode is accepted | the question "How to process the file" |

A hint shifts the confidence of its option by `hint_shift` (section 4.4); if it contradicts the content, the entry goes to quarantine for the reason `user_hint_mismatch`.

In the "Where to file the entry" question, the code collects the options: the model's choice, the hinted option, the proposed new container, the alternatives, and "No container" («Без контейнера»). A free-form answer is a container name; if there is no such container, a new top-level project is created, and the type can be given in parentheses: "Name (seed)" (Russian works too: «Название (росток)»).

Entries without a container (`_unsorted`) get vectors but no aspects: aspects are extracted when the entry gets a container.

### 6.6 Clarifying questions and quarantine

The "Questions" prompt («Вопросы») is called only if the classification confidence is below the threshold (the entry is in quarantine) or the entry is marked incomplete. The model receives the entry text, the reason, the model's choice with confidence and alternatives, the hint, and the descriptions of the candidate containers, and formulates up to `max_questions_per_entity` (3) short questions, with answer options where possible.

- **An uncertain entry** waits in quarantine (`_на_проверку`) until the user answers where to file it. The clarifying questions help them decide.
- **A confident but incomplete** entry continues through the steps, and the questions about it go to `open-questions.md`. The answer becomes a new entry in `_staging` with a link to the original one — the text of the processed entry does not change (section 4.3).
- **In Bootstrap**, questions are asked only for entries from quarantine; incomplete ones get `incomplete: true` and continue without questions — otherwise an old archive would generate hundreds of questions.

An entry with open questions is marked in YAML: `needs_review: true` and `review_reason` (`low_confidence`, `user_hint_mismatch`, `new_container`, `incomplete`).

### 6.7 Condensing

A separate step **before** aspect extraction: compressing a long or noisy text into a dense readable form so that extraction does not drown in noise. Extraction isolates meaning from a finished text; condensing compresses an originally wordy text. If both steps are mixed in one line of reasoning, the model simultaneously decides "what to remove" and "what to single out", and both results suffer. Example: a dialog with an AI is usually full of repetitions, clarifying questions, and wordy explanations.

Whether condensing is needed is decided by the actual content of the specific text, not by its source: a short to-the-point dialog doesn't need condensing, while a long rambling thought might. The noisiness (0–100) is assessed by the model during classification — it has already read the whole text. The code calls the "Condensing" prompt («Уплотнение») if

```
noisiness ≥ compaction − the source's compaction_shift
```

(`compaction` is 60; the `Чат с ИИ` source has a shift of 20, so its threshold is 40). The decision and the score are written to the reflection log.

The condensed version is saved in the same entry as a separate section «Уплотнённая версия (создана программой)» ("Condensed version (created by the program)") below the original text, with `compacted: true` in YAML. The original text does not change. From then on (vectors, extraction), the condensed version is used. The program checks that the compressed text really is shorter than the original.

**AI dialogs.** The basis is the user's turns (`я:`) as the primary source of the thought. The model's turns (`ИИ:`) are taken into account as context and as the occasion for the thought, not as content in their own right. The exception is an AI suggestion that the user explicitly accepted ("yes, I'll do that"): this is already the user's position, and it is preserved («Принял предложение ИИ: …», "Accepted the AI's suggestion: …"). The same rule applies to aspect extraction.

Condensing works the same way in both modes: in Bootstrap — in bulk, in Steady-state — one entry at a time.

### 6.8 Vectors and similar entries

The code (without the language model) computes the entry's vector — from the condensed version, if there is one. Vectors at three levels — entries, aspects, containers — are described in section 12.

**Free revalidation.** In normal mode, the program searches the processed entries of other containers for ones that almost coincide in meaning (similarity not lower than `neighbor_similarity`, 0.88). If one is found, perhaps one of the two is filed incorrectly — and the user gets the question "Similar entries in different places" («Похожие записи в разных местах»): move the new one, move the old one, make the new one shared, or leave things as they are. This is a cheap check of old sorting that comes as a side effect of normal work (section 10.1). In Bootstrap the check is not done: the structure is only just taking shape.

### 6.9 Aspect extraction

The "Extraction" prompt («Извлечение») breaks one entry down into simple aspects (section 5.1). The model receives the entry text (condensed, if available), the date, the kind of entry, the container's name and description — and does not see the rest of the pool: this is an honest breakdown of this particular entry, without regard to its neighbors. Links between aspects are the job of pool analysis (section 6.10).

The aspects are added to the pool of the entry's container (and to the pools of all its additional containers) with a link to the entry and its date; a vector is computed for each aspect. The entry gets `status: processed` and the list `aspect_ids`. If extraction was interrupted, the remains of the interrupted attempt are removed on retry — no extra aspects are left. The container is marked for rebuilding its synthesis base.

### 6.10 Synthesis base assembly

For each container that received new aspects in this run or whose pool had status changes:

**1. Pool analysis** (the "Pool analysis" prompt, «Анализ пула»). One call over the container's entire pool. Each aspect is given with the date of its source entry, to tell new from old. Besides the aspects themselves, the model receives: the formulas of composite types and the candidates for each formula selected by the code (section 5.2); the existing composites; which aspects are new in this run; pairs of similar aspects from the vector search (similarity not lower than `duplicate_similarity`, 0.86; up to 150 pairs); the pairs already decided by the user, so as not to propose them again; the list of the container's entries. If the pool is very large, the code divides it into parts.

The model finds:

- **composite aspects**: extend an existing one or assemble a new one from free aspects; dissolve a composite that no longer holds together. Applied immediately;
- **duplicates** — aspects that match existing ones in meaning. Linked immediately (section 6.11);
- **outdated material** — aspects that new material revises. Always only a suggestion: the question "Does the new thought revise the old one?" («Новая мысль пересматривает старую?») with the model's confidence. The one that is older by date becomes outdated;
- **contradictions** between aspects of the same type — with a guess as to which one is right (section 6.12);
- **structure suggestions**: turn a sprout into a project; split off a sub-container from a group of entries. If the confidence is not lower than `high` (90), the program does this itself; if lower, it asks.

**2. Value assessment** (the "Value" prompt). A separate call. Each element that can get into the base — free simple aspects (not duplicates) and composites as a whole — gets a score of 0–100 in the context of the whole container. The value of the same fact depends on what else is in the container, so the score is recalculated at each assembly. Elements are submitted in parts of `max_items_per_value_call` (400). Duplicates get the score of their main aspect.

**3. Filter** (code). Elements with a value below `value_min` (30) do not get into the base — but they remain in the pool and in the view. Elements pinned by the user (`pinned`) always pass.

**4. Grouping by type** (code). Contradictions from the analysis are raised as a question only if both aspects have passed the filter. The rest are kept and will surface if an aspect passes the filter later.

**5. Ranking within a group** (code): a value not lower than `value_primary` (70) means primary, otherwise secondary. A pinned element is always primary, an alternative rejected by the user is always secondary. Within a group — primary ones first, then by descending value and by date.

**6. Group order** (code) — according to the priority table (section 5.4).

Each element of the base stores its text, value, rank, date, all source entries (including those of duplicates), the composition for composites, and marks: «спорит с …» (disputes …), «предположительно уступает» (presumably yields), «развилка» (fork), «рассмотренная и отклонённая альтернатива» (considered and rejected alternative), «на пересмотре» (under review), «закреплено вами» (pinned by you). Contradictions between entries that the user marked manually (`conflicts_with`) form a separate list. The format is in section 16.4. The view `_база синтеза.md` shows the base in readable form, and its text is committed to the git mirror as a version.

If the pool changed only organizationally (an answer to a contradiction question, outdating outside a composite, restoring an element), the analysis and value assessment are not repeated: the code rebuilds the base from the existing scores, without new calls to the model.

### 6.11 Duplicates and revising thoughts

The model never writes new text of a thought for the user and does not create "merged thoughts". Two cases are possible.

- **The new changes the old.** Example: the author used to think that $500 would be enough to launch the club; after recalculating, it turns out $1,200 is needed. They put the new thought into `_staging`. Pool analysis sees that its aspect revises the old one and suggests marking the old one outdated. After confirmation, the synthesis base is rebuilt with the new value; the old thought remains untouched. If the user answers "both are right", the suggestion is not repeated.
- **Duplicates.** Different entries say the same thing without refuting anything. Pool analysis, taking into account the similar pairs from the vector search, links the matching aspects: the later one gets `duplicate_of` pointing to the earlier one. They go into the synthesis base as a single item with links to all source entries. Linking is applied immediately, without a question: nothing is lost, all aspects and entries stay in place. The list of linked pairs of a container accumulates in a single question, "Check the linked duplicates" («Проверьте связанные дубли»): an erroneous link can be removed by entering the duplicate's number (for example, `a12`).

If the user wants to combine several thoughts into one, they write a new thought themselves. It goes through Phase 1 as normal input, and then the same two cases apply.

### 6.12 Contradictions

A case separate from outdating: two current aspects of the same type contradict each other in content — not because one is outdated, but because a decision has not been made yet or these are legitimately different directions.

**Detection** happens in pool analysis. Aspects of the same type are compared with each other (experience with experience, idea with idea), not across types. A contradiction that is found is saved in the pool, and the source entries get mutual `conflicts_with` links. The question to the user is raised only if both aspects have passed the value filter.

**Optimistic resolution.** Along with the contradiction, the model immediately gives its guess: the first is right, the second is right, or both are (a fork). Until the user answers, the synthesis base proceeds from this guess: the presumed loser is **not deleted** but remains in the base marked «предположительно уступает» (presumably yields), and the documents are written with this in mind. The answer is applied by the code rebuilding the base, without a new model call; if it matches the guess, there is almost nothing to recalculate. The guess and the answer go to the reflection log.

Answer options:

- **"The first is right" / "The second is right"** («Верно первое» / «Верно второе») — the other aspect remains in the base as a considered and rejected alternative (secondary). The document may mention it if this is valuable for context;
- **"Both are right — it's a fork"** («Оба верны — это развилка») — branching (section 10.3): both directions remain in the base with a fork mark, and synthesis follows both;
- **"It's not a contradiction"** («Это не противоречие») — the mark is removed, the `conflicts_with` links between the entries are removed, and the model no longer proposes this pair.

A contradiction can also be marked manually: the entry's `conflicts_with` field (section 3.6). Such pairs go into the synthesis base as a separate list «отмечены автором» (marked by the author), and synthesis takes them into account.

### 6.13 Comparison with the previous version of the base

The last step of the assembly is a comparison of the new synthesis base with the previous one by content, not by text. The code finds elements that dropped out of the base or lost their primary status and filters out explainable losses: outdating confirmed by the user; linking of duplicates; inclusion in a composite; moving an entry to another container; a rejected alternative; a loss already acknowledged as intentional. The rest is assessed by the "Version comparison" prompt («Сравнение версий»): is the loss significant? A significant loss leads to the question "Did something important drop out of the synthesis base?" («Из базы синтеза выпало важное?»):

- "That's intended — the loss is deliberate" («Так и нужно — потеря намеренная») — the element is entered into the pool's `accepted_losses` and is not raised in subsequent comparisons;
- "Return to the base as primary" («Вернуть в базу как первостепенное») — the element is pinned (`pinned`): from then on it passes the filter and is always primary.

While the question is open, the base is marked `needs_review` with the reason «значимая потеря по сравнению с предыдущей версией» ("significant loss compared to the previous version").

## 7. Questions and confirmation (`needs_review`)

A single mechanism for all cases of uncertainty. The model never decides such questions itself: it proposes, the user confirms. While there is no answer, work does not stop: the entry waits in quarantine or the synthesis base proceeds from the model's assumption (section 6.12), and everything else goes on as usual.

### 7.1 Where questions come from

| Kind (`kind`) | When | Answer options |
| --- | --- | --- |
| `classify` — "Where to file the entry" | Confidence below the threshold, a new container below the high threshold, the hint contradicts the content (section 6.5) | The model's choice, the hinted option, a new container, alternatives, "No container"; a free-form answer is a container name |
| `mode` — "How to process the file" | The file's mode is unclear (section 6.2) | Divide into parts by topic / process as a single entry |
| `also_in` — "Is the entry also needed in another container?" | An additional container below the high threshold | Yes / No |
| `clarify` — "Clarification for an entry" («Уточнение к записи») | An uncertain or incomplete entry (section 6.6) | Options from the model; free-form answer |
| `outdated` — "Does the new thought revise the old one?" | Pool analysis (section 6.11) | Yes, the old one is outdated / No, both are right |
| `conflict` — "Contradiction between thoughts" («Противоречие между мыслями») | Pool analysis, both aspects passed the filter (section 6.12) | The first is right / the second / a fork / not a contradiction |
| `dup_fix` — "Check the linked duplicates" | Pool analysis linked duplicates (section 6.11) | All links are correct; a free-form answer is the numbers of erroneous duplicates |
| `structure_seed` — "Has the sprout grown into a project?" («Росток дорос до проекта?») | Pool analysis, confidence below the high threshold | Yes / No |
| `structure_sub` — "Split off a sub-container?" («Выделить под-контейнер?») | Pool analysis, confidence below the high threshold | Yes / No; a free-form answer is a different name |
| `base_loss` — "Did something important drop out of the synthesis base?" | Comparison of base versions (section 6.13) | The loss is deliberate / return as primary |
| `product_loss` — "Did something important disappear in the new version of the document?" («В новой версии документа пропало важное?») | Comparison of document versions (section 8.4) | The loss is deliberate / return at the next synthesis / roll back the document |
| `revalidate` — "Similar entries in different places", "Recheck: …" («Перепроверка: …») | Similar entries in different containers (section 6.8), deep revalidation (section 10.1) | Move, make shared, leave as is |
| `composite_type` — "New composite aspect type?" («Новый составной тип аспектов?») | Pattern search (section 5.3) | Yes, add the type / No |
| `dormant` — "The sprout has not developed for a long time" («Росток давно не развивался») | "Silent death" of sprouts (section 3.3) | Still relevant / freeze / completed |
| `text_changed` — "The text of a processed entry has changed" («Изменён текст обработанной записи») | A text edit after Phase 1 (section 4.3) | Make a new entry from the edit / restore the original text |

A special case is the structure draft during a bulk load: it is approved not through a question but as a whole, in a single file (section 6.3).

Identical questions are not duplicated: each has a key, and proposing the same thing again does not create a second question. "No" decisions are remembered in the container's pool (`rejected`), and the model does not propose the same thing again.

### 7.2 Where questions are shown

- **`open-questions.md`** in the vault root — a combined list of open questions for all containers. The file is redrawn at the end of each command from the machine registry `.system/questions.json` (section 16.6). Each question has a number (`Q12`), a title, a date, text with links to entries and containers, answer options, and, where possible, a free-form answer field. Above the questions are the program's notices (for example, «черновик структуры ждёт проверки», "the structure draft is waiting for review").
- **The "Questions" tab of the plugin panel** («Вопросы») — the same questions with buttons for the options and an answer field (section 18.2).
- **The entry itself** — `needs_review: true` and `review_reason` in YAML, visible when the file is opened. Entries in quarantine are stored in `_на_проверку/`.
- **A synthesis base and a document** with an open question about a loss are also marked with `needs_review` and `review_reason`.

### 7.3 How to answer

**In `open-questions.md`:**

- a question with options — tick **exactly one** option (`- [x]`; the Cyrillic «х» also works). If several are ticked, the program leaves the question open and writes above it what is wrong;
- a free-form answer — after «Ответ:» ("Answer:"), possibly on several lines;
- answers from the file are applied at the start of the next Phase 1.

**In the panel**, the answer is applied immediately (the `answer` command). If the answer does not fit, the panel shows why.

What a free-form answer does:

- in "Where to file the entry" — it is a container name; if there is no such container, a new top-level project is created, and the type can be given in parentheses: "Apartment (seed)" (or in Russian, «Квартира (росток)»);
- in a clarifying question — the answer becomes a **new entry** in `_staging`, «уточнение — <запись>» ("clarification — <entry>"): with a hint pointing to the container of the original entry, the `одна запись` (single entry) mark, and «Вопрос — Ответ» ("Question — Answer") pairs. The text of the original entry does not change. The new entry is processed in the next Phase 1 (when answering in the file — in the same run);
- in "Check the linked duplicates" — the numbers of erroneous duplicates, separated by commas: the links are removed;
- in "Split off a sub-container?" — a different name for the sub-container.

An answer the program cannot apply (for example, the entry has already been deleted) is not lost: the question remains open with a remark.

### 7.4 After the answer

Each applied answer:

- is written to the reflection log as a pair with the system's original assumption and an indication of whether they matched (section 15.3);
- goes, with the question text and the selected answer, to `_логи/архив вопросов.md` — questions are not deleted;
- removes the `needs_review` mark from the entry if there are no other open questions about it;
- marks the affected containers for rebuilding the synthesis base. If only the order and the marks need to change (a contradiction is resolved, an element is pinned), the base is rebuilt by the code without model calls.

## 8. Phase 2: documents

Documents are a different category from aspects. Aspects are raw material, like the sources in a term paper's bibliography. A document is a self-contained text that the model writes after understanding the container's **entire** synthesis base as a whole — not a retelling or a stitching-together of aspects one by one.

- **"Summary file"** («Сводный файл») — the mandatory document: a general description of the project in its current state.
- **Additional documents** — an open set, determined by the model from the material: for example, "Financial model" if there are amounts and calculations; "Diary" if there is experience — then entries in chronological order with dates; "Plan", "Open questions". No document is created just for the sake of it.

The content structure of documents is **deliberately not prescribed**: different material calls for different forms, and a rigid template would get in the way. What is configured is the writing style (section 8.3). Choosing the set of additional documents is not separated from synthesis: it is one coherent creative task over one body of material, so a single prompt, "Synthesis", handles it.

### 8.1 Launch

Phase 2 is started manually for one container: a button on the panel's "Container" tab or the command `synth "Name"`. There is no schedule: the model does not run constantly.

Before synthesis, the program:

1. accepts manual edits of documents (section 8.5);
2. checks that the synthesis base is up to date. If the container has changes not yet assembled by Phase 1, synthesis does not start: "run Phase 1 first" («сначала запустите Фазу 1»). The same happens if there is no base yet (the container has no processed thoughts);
3. compares the input "signature" — the base, the style, the container information, the current documents, deliberate losses and requests to restore — with the signature of the previous synthesis. If nothing has changed, the documents are up to date and the model is not called. You can still rewrite everything (`--force`; in the plugin window — by answering a question);
4. estimates the run and, if it is large, asks for confirmation (section 14.4).

### 8.2 What the model receives

The "Synthesis" prompt receives:

- information about the container: name, type, status, description, parent and links;
- the writing style (section 8.3);
- the synthesis base as text: groups in order of priority, each with elements carrying a rank (`primary`/`secondary`), a date, a value, the number of source entries and marks («спорит с …» (disputes …), «предположительно уступает (автор ещё не решил)» (presumably yields (the author has not decided yet)), «развилка: оба направления живы» (fork: both directions are alive), «рассмотренная и отклонённая автором альтернатива» (an alternative considered and rejected by the author), «на пересмотре» (under review)); for composites — their composition; at the end — contradictions the author marked manually;
- the current versions of the documents, if any — together with the author's manual edits;
- losses accepted as deliberate (not to be restored) and requests to restore what disappeared (must be taken into account);
- for a completed container (`completed`) — a requirement to set apart a "Final result" section («Итоговый результат») in the "Summary file".

The main rules of the prompt: everything primary must be reflected in the documents; hypotheses, ideas and plans are presented as hypotheses, ideas and plans, not as facts; contradictions and forks are shown honestly; from previous versions, whatever is still true is preserved, especially the author's edits; nothing is invented; documents are written in the language of the notes.

The response is plain text (Markdown): documents one after another, each starting with the line `=== ФАЙЛ: Название ===` (=== FILE: Name ===). The program checks that there is at least one document, that the "Summary file" is among them, that names do not repeat and that documents are not empty; otherwise it asks the model to fix the response (section 13.4).

### 8.3 Style

The writing style is configured at three levels:

- **global** — `style.global` in the settings, for all containers. By default: «Пиши ясно и по делу, без воды и общих фраз. Сохраняй формулировки автора там, где они точны.» ("Write clearly and to the point, without filler or generic phrases. Keep the author's wording where it is precise.");
- **container** — the `style` field in the card (or the panel's "Container" tab). It also applies to nested containers that have no style of their own; it takes precedence over the global one;
- **document** — the `style_override` field in the document's YAML: only for this document in this container.

The model receives all applicable levels at once, marked with which one takes precedence.

### 8.4 Writing documents and comparing versions

For each document whose text has changed, the program, **before writing the files**, compares the previous and the new version with the "Version comparison" prompt (object kind — document). The model receives both versions and the losses already accepted as deliberate, and lists what has disappeared, marking whether it is significant. A significant loss not yet accepted as deliberate becomes the question "Did something important disappear in the new version of the document?" («В новой версии документа пропало важное?»):

- **"That's intended — the loss is deliberate"** («Так и нужно — потеря намеренная») — the loss is recorded in the document's `accepted_losses` and is not raised again. This is how the user closes a direction they have consciously excluded: not outdated, simply no longer needed in this document;
- **"Restore at the next synthesis"** («Вернуть при следующем синтезе») — what disappeared is passed to the next synthesis as mandatory;
- **"Roll the document back to the previous version"** («Откатить документ к прежней версии») — the previous text is taken from the git mirror (section 11.2).

Then the documents are written to the container's folder, one file per document, with a YAML header (section 16.5): the kind (`summary` — the summary file, `supplementary` — an additional one), the generation date, which base build it was written from, `style_override` and `accepted_losses` from the previous version, and the `needs_review` mark if a question about the document is open. A document whose name matches the container's name or starts with `_` gets the suffix «(документ)» ("(document)") so that it is not confused with the card and the views. The new version of each document is committed to the git mirror.

Documents the model did not rewrite this time stay as they are — nothing is deleted. After synthesis, requests to restore what disappeared are cleared and the container is reindexed: the beginning of the "Summary file" becomes its representation for classification (section 6.4).

### 8.5 Manual edits of documents

A document can be edited by hand. An edit is not a direct change to the synthesis base (the base is not edited by hand) but a **new input**. At the start of each Phase 1 (and before each Phase 2), the program compares every document with its latest version in the git mirror. If they differ, an entry «правка документа — <документ> (<контейнер>)» ("document edit — <document> (<container>)") appears in `_staging`: with a hint pointing to the container, the kind `product_edit`, and only the changed lines — «Автор добавил или переписал: …» ("The author added or rewrote: …"), «Автор убрал: …» ("The author removed: …"). From there it goes through Phase 1 like an ordinary entry: its aspects go into the pool, the synthesis base is rebuilt, and the next synthesis takes the edit into account as a full-fledged source on a par with the others.

The edit itself stays in the document: the model receives the current version of the document with the edits and keeps them if they are still true.

## 9. Prompts

All calls to the language model are gathered into a set of prompts. Each prompt is a separate Markdown file in the program's `prompts/` folder: it can be read and edited. The same prompts work in API mode and in manual mode through a web chat (section 13.5).

### 9.1 How they are built

**Splitting criterion.** A separate prompt is used where the decision is of a fundamentally different kind (classification, extraction and text synthesis are different "heads" of reasoning) or where the step itself may end with a question to the user. Steps are combined when they are logically inseparable (the second makes no sense without the result of the first within one line of reasoning) and together fit into a reasonable size.

**Context is not trimmed.** The constraint is money, not tokens (section 14): prompts are not squeezed artificially, and the quality of analysis matters more than size. If the material does not fit into the model's window, the code splits it into parts itself (section 13.4).

**Substitutions.** The variable parts of a prompt are written as `{{name}}`. Before sending, the program checks that every substitution has a value; lists and objects are substituted as JSON.

**Response format.** Prompts whose responses the program parses answer strictly in JSON. The `reasoning` field comes first — a decision written down after the explanation is more accurate — and goes straight to the reasoning log (section 15.2). "Condensing" and "Synthesis" write plain text (Markdown). The program checks every response: whether it parses, whether all fields are present, whether the mentioned `id`s exist, whether the numbers are within the allowed ranges. On an error, the model receives a list of remarks and sends a corrected response (section 13.4).

**Language.** The prompts are written in Russian. The model's responses — aspect texts, questions, documents — are in the language of the notes.

**Editing prompts.** Prompts can be adapted to your needs — carefully: the program expects responses in the same format. When the program is updated, new versions of the prompts are installed on top, and the ones changed by the user are saved to `prompts/_прежние/` (previous) (section 19.3).

### 9.2 List of prompts

| Prompt | When it is called | What it does | Response |
| --- | --- | --- | --- |
| "Structure" («Структура») | Bootstrap, pass 1 (section 6.3) | From all the loaded material, proposes a tree of containers: name, type, description, parent, links; each subsequent part of the material refines the draft | JSON |
| "Classification" («Классификация») | Every new file or diary part (section 6.4); deep revalidation (section 10.1) | Segments (Bootstrap only), the container with its confidence without the hint and the confidence of the hinted option, alternatives, additional containers, kind of entry, incompleteness, noisiness, a guess about the mode | JSON |
| "Questions" («Вопросы») | An entry in quarantine or an incomplete one (section 6.6) | Short clarifying questions to the author, with answer options where possible | JSON |
| "Condensing" («Уплотнение») | Noisiness above the threshold (section 6.7) | Compresses the text into a dense form without losing anything substantive; in dialogues it relies on the user's lines | text |
| "Extraction" («Извлечение») | Every entry with a container (section 6.9) | Breaks one entry down into simple aspects, without regard to the rest of the pool | JSON |
| "Pool analysis" («Анализ пула») | Every container with changes (section 6.10) | Composite aspects (assemble, extend, dissolve), duplicates, outdated items, contradictions with a guess, structure proposals | JSON |
| "Value" («Ценность») | Every container with changes (section 6.10) | Rates the content value (0–100) of each element in the context of the container | JSON |
| "Version comparison" («Сравнение версий») | Synthesis base assembly (section 6.13) and Phase 2 (section 8.4) | Whether each loss between the previous and the new version is significant. One template; the object kind is a parameter: synthesis base or document | JSON |
| "Synthesis" («Синтез») | Phase 2 (section 8) | The "Summary file" and a set of additional documents from the whole synthesis base | text |
| "New composite type" («Новый составной тип») | Pattern search, after the technical selection of groups (section 5.3) | Whether there is a stable pattern among the candidate groups; the formula, name and example of the new type | JSON |
| "Thresholds" («Пороги») | Advice on container thresholds (section 10.5) | Proposes threshold values with an explanation, based on decision statistics | JSON |

### 9.3 What the code does, not the model

A language model is not needed where the decision is deterministic. The code does this:

- detecting the encoding, the date and dialogue markup; splitting a diary by dates; numbering paragraphs and copying segments verbatim;
- applying thresholds and the hint shift; creating containers, moving entries, shared entries;
- vector search: similar entries, pairs of possible duplicates, narrowing the list of containers, candidate groups for new composite types;
- preliminary selection of aspects by the formulas of composite types;
- filtering, grouping and ranking by ready-made value scores; ordering groups by the priority table;
- finding dropped elements when comparing synthesis base versions, and screening out explainable losses;
- decision statistics for threshold advice and checking the proposed values;
- checking the format of every model response.

## 10. On-demand operations

Mechanisms on top of the main work of Phases 1 and 2. The user invokes them when they decide it is needed. Some are free (an organizational action, no model); others spend model calls — then the program shows an estimate in advance (section 14.4).

| Operation | How to invoke | Model |
| --- | --- | --- |
| Deep revalidation | the panel's "Revalidation…" button («Ревалидация…») or "Recheck sorting" («Перепроверить раскладку») on the "Container" tab; `revalidate` | one call per entry |
| Disputing the sorting | the entry's `container` field | not needed |
| Branching | the answer "Both are right — it's a fork" to the contradiction question | not needed |
| Pattern search | the "Patterns" button («Паттерны»); `patterns` | one call |
| Threshold advice | "Consult the AI" («Посоветоваться с ИИ») on the "Container" tab; `advise` | one call |

### 10.1 Revalidation

Sorting done once can become outdated over time: new containers appear, the descriptions of old ones become more precise, context accumulates. It can be rechecked in two ways.

**Free — by neighbors.** It runs by itself, as a side effect of ordinary Phase 1: if a new entry almost coincides in meaning with an entry from another container, the program asks whether everything is sorted correctly (section 6.8). Not a single extra call to the model.

**Deep — on command.** The user selects one container or all entries at once. For each processed entry, in date order, the program calls the "Classification" prompt again — in normal mode, with the current list of containers and **without the author's hint**: what is needed is the model's unbiased opinion. The working text is used (the condensed one, if any).

- The model assigns the entry to another existing container with confidence not below that container's `classification` threshold — the question "Recheck: is the entry in the wrong place?" («Перепроверка: запись лежит не там?»): move it, make it shared (if the entry is already in a container), or leave it as is.
- The model proposes a new container with confidence not below `high` — the question "Recheck: is a new container needed?" («Перепроверка: нужен новый контейнер?»): create it and move the entry, or leave it as is.
- Otherwise the sorting is confirmed and there is no question.

The model does not move anything itself — it only proposes. Each of its opinions is written to the reflection log (`deep_revalidation`), with the user's answer next to it.

This is one model call per entry, so before starting, the program shows the number of entries and an estimate of time and money, and **always** asks for confirmation. Without the plugin and the console, confirmation is given with the `--yes` flag; `--count` only counts the entries. Progress is saved after each entry: an interrupted revalidation (a failure, the "Stop" button) continues from the same place on the next run for the same target.

When it is worth running: the structure has changed noticeably (sub-containers have been split off, a sprout has become a project), new containers have appeared, or the sorting of old entries raises doubts.

### 10.2 Disputing the sorting

Free and without the model: it is enough to change the entry's `container` field — enter the `[[name]]` of another container (section 3.6). An empty field sends the entry to `_unsorted`; a non-existent container produces a warning, and the entry stays where it is.

At the start of the next Phase 1, the program moves the entry's file, removes its aspects from the previous container's pool and adds them to the new container's pool (without new extraction — the aspects are the same), and the synthesis bases of both containers are rebuilt. If the entry had no container, its aspects are extracted anew.

The move goes into the change log («классификация оспорена правкой YAML», "classification disputed by a YAML edit") and into the reflection log: the user's decision is added to the model's original guess, marked «не совпало» ("did not match"). This accumulates statistics on sorting errors — the threshold advice sees how many entries sorted without a question the user later moved (section 10.5).

### 10.3 Branching

Sometimes two thoughts diverge not because one is wrong or outdated, but because they are legitimately different directions, and the author wants to keep both. Example: the "Running app" has an idea of selling the app as a one-time purchase and an idea of a subscription, and the choice has not been made yet.

The program does not create branches by itself and does not prepare separate infrastructure for them. Branching is a conscious decision of the user: the answer "Both are right — it's a fork" («Оба верны — это развилка») to the question "Contradiction between thoughts" (section 6.12). After such an answer:

- both aspects remain in the synthesis base on an equal footing, marked «развилка: оба направления живы» (fork: both directions are alive); neither becomes a rejected alternative;
- synthesis carries both directions: the "Summary file" shows the fork honestly, among the open questions, rather than picking a winner for the author;
- this pair is no longer raised as a contradiction.

The model can also propose a fork itself when it finds a contradiction; then, until the user answers, both aspects also go into the base with this mark.

Once the choice is made, it is enough to write a new entry about it: pool analysis will see that the new thought revises the old one (section 6.11).

### 10.4 Pattern search

Looks for stable bundles of different simple aspect types that no existing composite type covers, and proposes a new composite type. How the selection works and what happens after the answer is described in section 5.3. This is one model call for all the groups found; if there are no suitable groups, the program does not call the model. Proposals come as the question "New composite aspect type?" («Новый составной тип аспектов?»); an accepted type becomes permanent for all containers, a rejected one is not proposed again.

It makes sense to run it from time to time, when many aspects have accumulated in the containers.

### 10.5 Container thresholds and the model's advice

**Global and own thresholds.** Decisions made by the code (section 6.5) rely on thresholds. The global ones are set in the settings (`thresholds`), but containers differ: for a lively project with frequent notes you want bolder sorting, for a subtle topic — more frequent questions. Therefore almost any threshold can be set per container. A container's own threshold applies to the container and to all containers nested in it, until a nested one has its own; otherwise the global one applies. The source of each value — own, from the parent, or global — is visible on the "Container" tab.

| Threshold | Key | Default | What it decides |
| --- | --- | --- | --- |
| Sorting without a question («Раскладка без вопроса») | `classification` | 70 | From what confidence an entry is sorted automatically; below it — quarantine and a question |
| Weight of your hint («Вес вашей подсказки») | `hint_shift` | 15 (0–50) | How many confidence points are added to the hinted option |
| High confidence («Высокая уверенность») | `high` | 90 | From what confidence the program itself creates containers and sub-containers, makes an entry shared, promotes a sprout to a project |
| File mode guess («Догадка о режиме файла») | `mode_guess` | 70 | From what confidence the file's mode is accepted without a question. Global only: the file has not been sorted yet |
| Condensing («Уплотнение») | `compaction` | 60 | From what noisiness an entry is compressed first (with the source's adjustment, section 6.7) |
| Minimum value («Минимальная ценность») | `value_min` | 30 | Aspects more valuable than this go into the synthesis base |
| Primary («Первостепенное») | `value_primary` | 70 | From what value an aspect is primary |
| Similarity for duplicate search («Похожесть для поиска дублей») | `duplicate_similarity` | 0.86 | From what similarity pairs of aspects are shown to the model as possible duplicates |
| Neighbor similarity («Похожесть соседей») | `neighbor_similarity` | 0.88 | From what similarity entries from different containers trigger a sorting question |
| Similarity for patterns («Похожесть для паттернов») | `pattern_similarity` | 0.8 | How close aspects must be for pattern search to treat them as a bundle |
| Days before the sprout question («Дней до вопроса о ростке») | `seed_dormancy_days` | 90 (7–3650) | After how many days of silence a sprout gets the question "still relevant?". Sprouts only |

Scales: confidence, noisiness and value — 0–100; similarity — 0.5–0.99.

Which container determines the threshold: when sorting — the one where the entry is placed (for a new container — its future parent; for an additional one — the additional container itself); when condensing and searching for neighbors — the entry's container; when assembling the base, searching for duplicates, making structure proposals and searching for patterns — the pool's container.

**Where they are set.** On the panel's "Container" tab — a slider and a field for each threshold; an empty field means the parent's or the global value (shown in gray), and "↺" removes the container's own threshold. Or manually — the `thresholds` field in the container card:

```yaml
thresholds:
  classification: 80
  дубли: 0,9
```

Russian names are accepted (раскладка — sorting, подсказка — hint, высокая — high, уплотнение — condensing, ценность — value, первостепенное — primary, дубли — duplicates, соседи — neighbors, паттерны — patterns, дремота — dormancy), as well as a comma in fractions and a percent sign ("80%"; on the 0–1 scale "86%" means 0.86). An unknown threshold or an out-of-range value is skipped with a warning.

When they take effect: sorting and condensing thresholds — on new entries; value thresholds — at the next Phase 1, when the code rebuilds the synthesis base without calls to the model. Changes to a container's own thresholds and style go into the change log marked «пользователь» ("user").

**The model's advice.** Choosing thresholds by eye is hard, so the program can consult the model. The code first collects decision statistics for this container — from the reflection log and the state: how many entries were sorted without a question and how many of them the user later moved; how many sorting questions there were and whether the model turned out to be right; how often the hint diverged from the model's opinion; how many "the entry is needed here too" proposals and structure rearrangements were accepted and rejected; the distribution of noisiness and value (minimum, quartiles, median, histogram) and how many elements sit right at the thresholds; how many losses the user returned to the base and how many they accepted as deliberate; how many duplicate links were removed manually; how the questions about similar neighbors ended; for a sprout — how many days without new thoughts.

The "Thresholds" prompt («Пороги») receives the container description, a table of thresholds (current value, where it comes from, global value, allowed range), these statistics and a short human-readable summary of them. The model answers with a conclusion in plain words and recommendations: the threshold, the new value, and the figures it is based on. The code checks each recommendation (a known threshold, a value within range, `seed_dormancy_days` only for a sprout, no repeats) and discards "leave as is" advice.

The advice **changes nothing by itself**. The "AI advice on thresholds" window («Совет ИИ по порогам») shows the conclusion, the proposed changes "was → will be" with explanations (all checked by default) and a collapsible list "What the advice is based on" («На чём основан совет»). "Apply selected" («Применить выбранное») writes the checked values into the container's `thresholds` field; they take effect from the next Phase 1. The latest advice is saved and visible on the "Container" tab ("AI advice available", «Есть совет ИИ»).

The advice is written to the reflection log (`thresholds_advice`). When the user later changes the container's thresholds, the program adds the decision to the advice: accepted in full, in part or rejected, and which values exactly were taken. This shows how far the model's advice can be trusted.

## 11. Reliability

### 11.1 Nothing is deleted

The program erases nothing that came from the user or was derived from it. Outdated, erroneous and rejected items are marked and stay in place — the history of a thought can always be traced.

| What | Instead of deletion |
| --- | --- |
| Input file | Kept unchanged in `_исходники/` (section 4.1) |
| Text of a processed entry | Does not change; an edit becomes a new entry (section 4.3) |
| Entry | `status: outdated` — the thought is no longer relevant, its aspects become outdated (section 3.6) |
| Aspect | The `outdated` status with a link to the aspect that replaced it, the `duplicate_of` mark, inclusion in a composite (section 5.5) |
| The losing side of a contradiction | Remains in the synthesis base as a rejected alternative (section 6.12) |
| An element that dropped out of the base | Remains in the pool; losses accepted as deliberate — in `accepted_losses` (section 6.13) |
| Previous versions of documents and bases | The git mirror (section 11.2); a document can be rolled back by answering a question (section 8.4) |
| Container | The `completed` or `dormant` status (section 3.5) |
| An answered question | Moves to `_логи/архив вопросов.md` (question archive) together with the answer (section 15) |
| A "no" to a model's proposal | Remembered; the proposal is not repeated (section 7) |

The only thing the user can delete themselves is a container card; its entries then move to `_unsorted` with a warning (section 3.6). There is no need to delete entry files: that is what `status: outdated` is for.

### 11.2 Versions

Versions are kept for what the program rewrites entirely: synthesis bases and Phase 2 documents. Nothing else needs versions: entries do not change after processing, and the history of pools can be traced through the marks (section 11.1).

Technically, this is a git mirror in `.system/versions/`. Git is built into the program (the dulwich library); there is no need to install it separately. The mirror receives text versions: for a synthesis base — its view (`_база синтеза.md`), for a document — its text. At the end of each command, if anything has changed, the program makes a commit «прогон <дата и время>» ("run <date and time>"). Without the library, the program keeps working, just without history.

The mirror serves three purposes:

- **comparing document versions** — Phase 2 checks the new version against the previous one (section 8.4);
- **manual edits of documents** — the difference between the file in the vault and the latest version in the mirror is the user's edit (section 8.5);
- **rollback** — the answer "roll the document back" returns the previous version from the mirror.

To compare synthesis bases, the program also keeps a machine-readable previous version: `data/bases/<id>.prev.json` (section 6.13).

### 11.3 Failures and interruptions

**Saving after every step.** The pipeline state (`.system/state.json`), questions and vectors are saved after every step: an accepted file, a classified entry, a portion of a large file, an extraction, a stage of synthesis base assembly, a document. A fixed interval is not needed: saving is cheaper than a single call to the model. A restart after a failure continues from the last saved step, not from the beginning. An interrupted extraction leaves no extra aspects: the retry starts from a clean slate. In manual mode through a web chat, the same mechanism makes it possible to stop while waiting for an answer and continue later (section 13.5).

**Stopping.** The plugin has two buttons:

- "Stop" («Стоп») — the run queue is cancelled (except for quick actions without the model — answers to questions and YAML edits), and the current run finishes its step, saves everything and stops. The plugin leaves a `.system/stop` flag; the program checks it at every step, before every call to the model, and during pauses between retries;
- "Abort now" («Прервать сразу») — the process ends immediately: the current step will not be saved, everything done before it is intact.

In the console, the same is done by Ctrl+C (like "Stop") or by closing the window. Stopping on budget (section 14.3) saves everything just like "Stop". After any stop, the panel offers "Continue (Phase 1)" («Продолжить (Фаза 1)»).

**Locking.** Two simultaneous runs over the same vault are impossible: the `.system/lock` file is locked by operating-system means, and the second run gets the message «Программа уже работает с этим хранилищем в другом окне» ("The program is already working with this vault in another window"). If the program crashed, the lock is released by itself. The plugin queues its runs, so this situation never arises from it.

**Model connection failures.** A request is retried on a 429 response (too many requests), 5xx server errors, a dropped connection, and a non-JSON response — with pauses of 5, 20, 60 and 120 seconds; "Stop" interrupts the pause. An invalid key (401, 403) and overflowing the model's window are not retried: the program stops with a clear message (section 13.4).

**File operations.** On Windows, a file is sometimes busy for a moment — held by Obsidian, an antivirus, or cloud sync. The program retries the operation several times with short pauses. All files are written atomically: first to a temporary file next to the target, then by replacement, so a failure in the middle of writing does not leave a truncated file.

**An unexpected error** is written to `_логи/ошибки.log` (errors) with details, and a report for the developer is assembled from them (section 15.4).

## 12. Finding similar items: embeddings

### 12.1 Why

An embedding is a numeric vector that conveys the meaning of a text: the closer the vectors, the closer the meaning. Vectors are computed by a separate embedding model — without the language model and without paying for every decision. The program uses them where it needs to quickly find something similar among many items:

| Where | What is searched for | Vector level | Threshold |
| --- | --- | --- | --- |
| Free revalidation (section 6.8) | Nearly matching entries from other containers (the 5 nearest) | entries | `neighbor_similarity` |
| Pool analysis (section 6.11) | Pairs of aspects — possible duplicates shown to the model | aspects | `duplicate_similarity` |
| Classification (section 6.4) | If there are more containers than `limits.max_containers_in_prompt` (150), the request includes those closest in meaning and their parents | containers | — |
| Pattern search (section 5.3) | Groups of close aspects of different types | aspects | `pattern_similarity` |

The embedding model does not depend on the choice of language model: it returns a vector, the vector store keeps and searches it, and they do not need to know about each other. By default it runs **on this computer**: it does not need the language model's resources, and raw personal notes do not leave the computer even for search. Cloud embeddings are an option (section 12.4). The model is needed only during runs (Phase 1, connection check); it does not occupy memory permanently.

### 12.2 Vector store

Vectors of three levels:

- **entries** — from the entry's working text (the condensed one, if any);
- **aspects** — from the aspect's text;
- **containers** — from the name, the description and the beginning of the "Summary file" (up to 1500 characters); while there are no documents — from the 12 most valuable aspects of the pool. A container's vector is updated when the container is created or changed, after its synthesis base is assembled, and after Phase 2.

They are stored in `.system/vectors/` in the program's own files: one array of numbers (numpy) per level, with the list of `id`s and the name of the model that computed them next to it. Search is brute-force cosine similarity: for thousands and tens of thousands of entries it takes fractions of a second. No separate vector database is needed, and installation on Windows does without compilation or extra dependencies. The scale of personal use is far from the ceiling of such a solution.

**Changing the model.** Vectors from different models are incompatible. The model name from the settings (`embeddings.model`) serves as the label of the vectors: if it is different at startup, the program warns how long recomputation will take and recomputes all vectors itself — for entries, aspects and containers. Changing the language model does not require recomputation.

**Long texts.** A text longer than `embeddings.max_chars` (6000 characters) is truncated for search — the entry itself does not change. If the server replies that the text does not fit into the model's window, the program halves it and tries again. Texts are sent in batches of `batch` (16); for the own model, also no more than 16,000 characters per request, so that computation on the processor does not run into the response timeout.

**Failures.** No response or a server error — a retry with pauses of 3, 10 and 30 seconds. If the own model's server is not running, the program starts it itself (section 12.3) and waits while the model loads. If it still cannot connect, the program stops and suggests what to do.

### 12.3 Own model on llama.cpp

The default is **KaLM-Embedding-Gemma3 12B**: a multilingual model with a window of up to 32,768 tokens (Q4_K_S quantization, about 6.9 GB; 48 layers, a vector of 3840 numbers). It runs through `llama-server` from the llama.cpp project in the OpenAI format (`/v1/embeddings`).

Nothing needs to be installed manually. The "Start model…" button («Запустить модель…») (Settings → Second Brain → Models → Embeddings → "Own model"; in the interface: Второй мозг → Модели → Эмбеддинги → «Своя модель») opens the launch window:

- **what the computer has** — processor, cores and threads, RAM (total and free), graphics cards and their memory;
- **parameters:** where to compute (processor or graphics card); the llama.cpp build for the graphics card; how many model layers to keep on the graphics card (as many as fit, all, or a custom number); context; KV cache quantization; processor threads (the "By cores" button, «По ядрам»); port; after how many minutes of idleness to unload the model from memory; whether the program itself should start the server when it is needed; the model folder;
- **warnings** — not enough memory, or no graphics card found;
- **what will be downloaded** (once) and whether there is enough disk space.

"Start" («Запустить»; the `llama start` command) downloads whatever is missing, starts the server in the background, waits for the model to load into memory (up to 15 minutes on a slow disk), and itself writes the server address and the model name into the settings. Download progress is visible in the panel; "Stop" interrupts it, and the next start resumes from the same place. The model's integrity is verified by a checksum.

**What is downloaded:**

| What | From where | Size |
| --- | --- | --- |
| Model | Hugging Face, `mradermacher/KaLM-Embedding-Gemma3-12B-2511-GGUF` | about 6.9 GB |
| llama.cpp for the processor | GitHub, prebuilt `ggml-org/llama.cpp` releases | about 25 MB |
| llama.cpp Vulkan — for any graphics card | same place | about 38 MB |
| llama.cpp CUDA — for NVIDIA, Windows only | same place, together with the CUDA libraries | about 680 MB |
| Microsoft Visual C++ libraries | Microsoft, Windows only and only if they are missing | about 25 MB |

On macOS there is one build (with Metal); on Linux — for the processor or Vulkan. If `llama-server` is already installed on the computer, it can also be used for computation on the processor.

**Parameters** (`embeddings.server` in the settings):

| Parameter | Default | Meaning |
| --- | --- | --- |
| `device` | `cpu` | `cpu` — processor, `gpu` — graphics card (many times faster) |
| `build` | `auto` | Build for the graphics card: `auto` — CUDA for NVIDIA, otherwise Vulkan; `cuda`; `vulkan` |
| `gpu_layers` | `auto` | Layers on the graphics card: `auto` — as many as fit, `all` — all 48, or a number; the processor computes the rest |
| `ctx` | 4096 | Context, in tokens: the longest text processed at once (4096 is about 12–14 thousand characters). The program truncates long texts anyway (section 12.2), so 4096 is usually enough |
| `kv_cache` | `f16` | KV cache quantization. It gives this model almost nothing: the model reads each text entirely in one pass and does not keep a KV cache |
| `threads` | 0 | Processor threads; 0 — llama.cpp decides itself |
| `port` | 8081 | The server address is `http://127.0.0.1:<port>/v1`; the server listens only on this computer |
| `sleep_min` | 15 | After how many minutes of idleness to unload the model from memory (the next request loads it in a few seconds); 0 — never unload |
| `autostart` | `true` | If the server is not running (for example, after a reboot), the program starts it itself during Phase 1 or a connection check — with the saved parameters and without downloading anything |
| `models_dir` | empty | The model folder; empty — `models/` in the program folder |

**Memory.** How much the server with the model takes — the model itself plus a working buffer that grows with the context:

| Context, tokens | 2048 | 4096 | 8192 | 16,384 | 32,768 |
| --- | --- | --- | --- | --- | --- |
| Memory, GB | 7.8 | 8.4 | 9.6 | 12.6 | 20.1 |

On the processor, at least 16 GB of RAM is needed; if there is less, or the chosen context does not fit, the launch window warns about it. For the whole model to fit on the graphics card, about 8 GB of video memory is needed; if there is less, some layers stay in RAM — slower, but it works.

**How the server is started.** `llama-server -m <model> --embedding --pooling last --alias <name> --host 127.0.0.1 --port <port> -c <context> -np 1 -b <context> -ub <context>`; for the processor — also `-ngl 0`, for the graphics card — the number of layers, and if needed — threads and idle time. The batch size equals the context for a reason: the model is non-causal and reads the text entirely in one pass, so the whole text must fit into one batch; otherwise the server replies "input is too large".

**Where things are** (in the program folder): `models/` — the model; `llama.cpp/<build>/` — llama-server and its libraries; `llama.cpp/server.json` — the running server (process ID, port, parameters); `llama.cpp/server.log` — the server log of the last start (it can be opened from the settings).

**Management.** The settings show whether the model has been downloaded, which llama.cpp builds are available and whether the server is running; "Shut down" («Остановить») frees memory (the program will start the server again when it is needed); "Restart…" («Перезапустить…») restarts it with new parameters. Commands: `llama status`, `llama start`, `llama stop`, `llama download` (section 20).

**Typical errors** — each with a hint on what to do: the port is taken by another program (choose another port); no graphics card found (update the driver, choose another build or the processor); not enough memory (reduce the context); a server with this model that was not started by the program is already running on the port (the program uses it but cannot change its parameters).

### 12.4 Another server or the cloud

The own model is not the only option:

- **another local server** — any server that supports `/v1/embeddings` in the OpenAI format (for example, your own `llama-server` with a different model). In the settings — the address (`embeddings.base_url`) and the model name (`embeddings.model`); a key is needed only if the server was started with a key;
- **cloud embeddings** — `embeddings.mode: cloud`, the provider's address and model, the key in the file `embeddings_api_key.txt` next to the program, and the price `price_input` ($ per 1 million tokens) — for counting costs and the budget (section 14).

"Check connection" («Проверить связь») sends the model a short text and reports whether a vector was received. When the model changes, the vectors are recomputed automatically (section 12.2).

## 13. Language models and profiles

The program is not tied to a particular model or provider. Any service with an API in the OpenAI format (`/chat/completions`) will do — a cloud one or your own server on this computer — and without an API there is a manual mode through a web chat. The prompts are the same in all cases. The embedding model is chosen separately and does not depend on this choice (section 12).

### 13.1 Modes

The main mode is `llm.mode`:

| Mode | Where the model runs | What matters |
| --- | --- | --- |
| `cloud` — "Cloud model (API)" («Облачная модель (API)») | At the provider, with a key | Paid per token (section 14); a large window; the texts of notes go to the provider's server |
| `local` — "Local model (on this computer)" («Локальная модель (на этом компьютере)») | Your own llama.cpp server or another OpenAI-compatible one, on this computer or in the home network | Free, data goes nowhere; usually weaker than a cloud model and with a smaller window |
| `webchat` — "Manually via web chat" («Вручную через веб-чат») | In any model's web chat; the user carries requests and responses back and forth | No API or keys; slow and manual (section 13.5) |

No option is imposed. A cloud model is a conscious compromise: raw personal thoughts go to someone else's server, but the quality is higher and the window larger. The constraint there is money, not window size, so prompts are not trimmed to save money (section 9.1). A local model is the most private option, at the cost of quality and setup effort.

**Your own language model server** is started by the user (unlike the embedding server, section 12.3), for example: `llama-server -m model.gguf -c 16384 --port 8080`, and the address `http://127.0.0.1:8080/v1` is entered into the local profile. A key for addresses of this computer and the home network (`localhost`, `127.*`, `10.*`, `192.168.*`, `172.16–31.*`, `*.local`) is optional — it is needed only if the server was started with a key.

### 13.2 Profiles

Model settings are stored in **profiles** (`llm.profiles`). There can be any number of profiles: two models from the same provider, a cloud one and your own, a strong one and a fast one. The profile selected for the mode is used: `cloud_profile` in cloud mode, `local_profile` in local mode.

| Field | In the plugin | Meaning |
| --- | --- | --- |
| `id` | — | A short profile code (`p1`, `p2`…) that the settings refer to |
| `name` | "Profile name" («Имя профиля») | What the profile is called in lists, in "Costs" and in the log |
| `kind` | — | `cloud` or `local` |
| `base_url` | "API address" / "Server address" («Адрес API» / «Адрес сервера») | An address in the OpenAI format |
| `model` | "Model" («Модель») | The model name exactly as the provider spells it; for llama.cpp — anything |
| `api_key_file` | "API key" / "Key" («Ключ API» / «Ключ») | A file with the key next to the program (see below) |
| `temperature` | "Temperature" («Температура») | 0–2, default 0.2: lower means more stable responses |
| `max_input_chars` | "Request limit, characters" («Предел запроса, знаков») | Longer material is split into parts (section 13.4). Default: 300,000 (≈ 100 thousand tokens) for cloud, 40,000 for local; for your own server — about 3 characters per token of the window |
| `max_tokens` | "Response length limit (tokens)" («Предел длины ответа (токенов)») | Empty — as the provider has it |
| `timeout_sec` | "Response wait, seconds" («Ожидание ответа, секунд») | 600 for cloud, 1800 for local |
| `json_mode` | "JSON mode" («Режим JSON») | Enable if the server supports `response_format: json_object` — fewer format errors |
| `extra` | "Special request parameters" («Особые параметры запроса») | Added to the request as is, for example `{"thinking": {"type": "disabled"}}` |
| `prices` | prices, $ per 1 million tokens | Cloud only: input, cached input, output (section 14.2) |
| `budget_month` | "Profile limit per month, $" («Лимит профиля в месяц, $») | Cloud only: the profile's own limit on top of the overall budget (section 14.3) |

**Keys** are stored neither in the vault nor in `settings.yaml`, but in separate files next to the program: `api_key.txt` for the first profile, `api_key_<id>.txt` for new ones. This way a key does not end up in sync or in backups of the notes, and each profile has its own file — one provider's key will never be sent to another provider's address. In the plugin, the key is entered in a field that does not show it in full, and the program saves it to the file. A copy of a profile uses the same file by default; the "Separate key" button («Отдельный ключ») gives it its own.

In the plugin (Settings → Second Brain → Models; in the interface: Второй мозг → Модели): "Mode" («Режим»), the main cloud and local profiles, "Profile to edit" («Профиль для правки») with the fields of the selected profile, the buttons "＋ Cloud" («＋ Облачный»), "＋ Local" («＋ Локальный»), "Copy" («Копия») and profile deletion.

### 13.3 Models for individual steps

Each step (prompt) can be given its own profile or the web chat — `llm.roles`, in the plugin "Models for individual steps" («Модели для отдельных шагов»). For example, "Synthesis" to the strongest model, the frequent "Classification" to a fast one or your own on llama.cpp, and "Questions" to the web chat:

```yaml
llm:
  roles: {"Синтез": "p2", "Классификация": "p3", "Вопросы": "webchat"}
```

The keys are the Russian prompt names, as in the `prompts/` folder («Синтез» — Synthesis, «Классификация» — Classification, «Вопросы» — Questions).

"Same as main" («Как основная»; no line in `roles`) — the step runs on the main mode's profile. In web chat mode, profiles are needed only if individual steps are given their own models. Costs are recorded under the profile that actually responded (section 14).

### 13.4 Calling the model

**Preparation.** The program substitutes variables into the prompt (section 9.1) and, if the step's request is longer than the limit, splits the material into parts. Three steps with long material are split: "Structure" — the loaded files in parts, each part refining the draft; "Classification" — the paragraphs of a long file in windows; "Pool analysis" — the pool's aspects in parts. The limit belongs to the profile that answers the step (or to the web chat, `llm.webchat.max_input_chars`); the material gets the limit minus a reserve for the task and lists (about 40–60 thousand characters; for small limits — half). "Value" rates elements in portions of no more than `limits.max_items_per_value_call` (400).

**Before a call**, the program checks the budget (for a cloud profile, section 14.3) and the "Stop" flag; while the model is thinking, the plugin shows «Ждём ответа модели: <время> · <шаг> · <профиль>» ("Waiting for the model's response: <time> · <step> · <profile>").

**Checking the response.** Every response is parsed and checked (section 9.1). If something is wrong, the program continues the same dialogue: it sends the model its response and a list of remarks and asks for a complete corrected response. There are `llm.max_format_retries` (2) such attempts, that is, three responses in total; after that the program stops and names the errors.

**Truncation by length.** If a response was cut off at the length limit (`finish_reason: length`), the model is asked to send it again, shorter. For "Synthesis" this makes no sense — a document cannot be written shorter on demand — so the program stops right away and advises increasing the profile's "Response length limit" («Предел длины ответа») or clearing it.

**Connection and server errors** (section 11.3): on 429, 5xx, a dropped connection and a non-JSON response — retries with pauses of 5, 20, 60 and 120 seconds; if your own server does not respond at all, the program does not wait long and suggests checking whether it is running and whether the address is correct. An invalid key (401, 403) — a stop with a hint about which profile to fix. Overflowing the model's window — a stop with advice: for steps that can be split, reduce the "Request limit" («Предел запроса»); for the others, give the step to a profile with a larger window; your own llama.cpp server can be given a larger window with the `-c` flag.

**Accounting.** Every call is written to the call log: step, profile, model, tokens, time and cost (section 14.1). If the provider did not report tokens, they are estimated from the number of characters; for llama.cpp, tokens and cache are taken from its timing report. The `reasoning` field of the response goes to the reasoning log (section 15.2), and the model name to the reflection log (section 15.3).

**Connection check** ("Check connection", «Проверить связь»; the `check` command) checks the vault, the prompts and the version history, sends each model in use a short request with a JSON response and the embedding model a short text, and reports who responds and in how many seconds.

### 13.5 Manual mode through a web chat

For those without an API: the program prepares requests as files, and the user carries them to the web chat of any model. The prompts are the same as for the API.

1. At each call, the program puts two files into the `_веб-чат/` (web chat) folder: `001 <шаг> — запрос.md` (request) and an empty `001 <шаг> — ответ.md` (response) — and stops. The panel shows "Waiting for a response from the web chat" («Ждёт ответа из веб-чата») with the buttons "Open request" («Открыть запрос») and "Open response file" («Открыть файл ответа»).
2. The user copies into the web chat everything below the line «скопировать всё ниже» ("copy everything below"), pastes the model's whole response into the response file and saves it.
3. "Continue" («Продолжить»; or "Continue (Phase 1)") — the program checks the response the same way as an API response. If everything is correct, the pair of files moves to `_веб-чат/готово/` (done), and the work goes on until the next request. If not, a warning with a list of remarks appears at the top of the request file: they can be sent to the model and the response replaced with the corrected one.

Requests are numbered in order; responses already received are remembered (`.system/webchat.json`), so repeating a step after a stop does not create a new request. Stopping while waiting for a response loses nothing — the work continues from the same place (section 11.3). Time and "remaining" are not shown in this mode: everything depends on when the response is pasted. Embeddings are computed as usual in this mode too (section 12).

## 14. Costs, budget and run estimates

The constraint of a cloud model is money, not window size (section 9.1). Therefore the program records every call, keeps a monthly budget and, before a large run, estimates what it will cost.

### 14.1 Call log

`.system/usage.jsonl` — one line per call to the language model and to the embedding model (a batch of texts is one call):

| Field | What |
| --- | --- |
| `ts`, `run`, `cmd` | Time, run and command (`run`, `synth`, `revalidate`…) |
| `kind` | `llm` or `emb` |
| `prompt` | The step — the prompt name; for embeddings «Эмбеддинги» (Embeddings), for the connection check «Проверка связи» (Connection check) |
| `profile`, `profile_name` | The profile: `id` and name at the time of the call |
| `ptype` | Kind: `cloud`, `local`, `webchat` or `fake` (the test model) |
| `model` | Model |
| `in`, `out`, `cached` | Input tokens, output tokens, and how many of the input tokens came from the provider's cache |
| `est` | Tokens were estimated from the number of characters: the provider did not report them |
| `sec` | How long the response took |
| `cost` | Cost in dollars at the prices at the time of the call |

The program takes tokens from the provider's response; for llama.cpp — from its timing report. If the provider reported nothing, tokens are estimated as the number of characters divided by 3.

### 14.2 Cost

Money is counted only for cloud models. Prices are in the profile (`prices`, $ per 1 million tokens); for cloud embeddings — `embeddings.price_input`:

cost = (input − cached input) × input price + cached input × cache price + output × output price

If no cache price is set, cached input counts as ordinary input. Prices live in `settings.yaml`, not in a separate database: they are visible and can be corrected in one place — in the profile (Settings → Second Brain → Models) or right on the panel's "Costs" tab («Расходы»).

The cost is fixed together with the call: changing prices does not rewrite the past. Recalculation is explicit: after new prices are saved, the panel asks "Recalculate past calls?" («Пересчитать прошлые обращения?»); the command is `usage --reprice <profile id | emb | all>`. The log before recalculation is saved next to it as `.bak`. Cloud calls that had no price when they were recorded are estimated at current prices in the summaries; if there are still no prices, they go on a separate line «без стоимости» ("no cost") and are marked with an asterisk.

Local models are free: for them, tokens and running time are shown. For the web chat — the number of exchanges. The test model is counted as the profile it is attached to — this is needed for tests.

### 14.3 Budget

- `budget.monthly_usd` — for all cloud models together per calendar month; empty — no budget;
- the profile's `budget_month` — this profile's own limit;
- `budget.warn_pct` (80) — from what percentage to warn.

Before every paid call, the program checks how much has been spent this month (the log plus the current run). From `warn_pct` on — one warning per run: in the output, in the panel and as a notification. At 100% — the question "Budget exhausted" («Бюджет исчерпан»): "Continue until the end of this run" («Продолжить до конца этого запуска») or "Stop" («Остановить»). If it is impossible to ask (a run without the plugin and without a console), the program stops. Stopping on budget saves everything just like "Stop" (section 11.3); you can continue by increasing the budget, or by starting again and choosing "Continue".

The budget is set in the settings ("Costs" tab) or right on the panel's "Costs" tab — which also has a "spent of budget" bar («потрачено из бюджета»).

### 14.4 Run estimate

Before the first call to the model, the program estimates what lies ahead:

- **Phase 1** — which steps will be called and how many times: based on the files in `_staging` (with diaries split by dates) and the queue of accepted files, the parts of long files, the expected number of entries and containers;
- **Phase 2** — synthesis based on the container's synthesis base and previous documents, plus version comparison;
- **revalidation** — one classification per entry.

Averages per call — tokens and time — are taken from the log for the same step and profile if it has at least three calls; otherwise — the prompt length plus the material, and starting values per step. Money — at the prices of the profiles that answer the steps. The estimate is rough (±50%): how many entries there will be after sorting is not known in advance.

Before Phase 1 and Phase 2, the program shows the estimate and asks "Start?" («Запустить?») if the run is large — exceeds any of the thresholds: `estimate.calls` (30 calls), `estimate.usd` ($0.5) or `estimate.minutes` (10 minutes). Revalidation always asks (section 10.1). `estimate.enabled: false` disables the question; the `--yes` flag skips it once. If it is impossible to ask, Phase 1 and Phase 2 start without the question, while revalidation requires `--yes`. The estimate can also be obtained separately: `estimate run | synth <container> | revalidate [container]`.

### 14.5 Summary

The panel's "Costs" tab (and the `usage` command in the console):

- totals for today, this month, last month and all time: money, calls, input tokens (of them cached) and output tokens, model running time;
- the month's budget — how much has been spent and a bar up to the limit;
- **models** — a card for each profile: the model, the steps it works on, spending for the period, the profile limit; for cloud profiles — price fields with a "Save" button («Сохранить»). The embedding model is here too, as well as deleted profiles and former embedding models if there were calls to them;
- **by step** — calls, tokens and cost for each prompt;
- **by day** — bars for the last 31 days (cost, or the number of calls when there is no money involved);
- **recent runs** — what was run and what it cost.

During a run, the top of the panel shows how many tokens and how much money this run has already used (section 18.2).

## 15. Logs

Three logs with different tasks: the change log — what happened; the reasoning log — why the model decided as it did; the reflection log — how well its guesses match the user's decisions. Logs for humans are in the vault's `_логи/` (logs) folder, machine-readable ones in `.system/`. They can be opened from the panel's "Log" tab («Журнал»).

| File | For whom | What |
| --- | --- | --- |
| `_логи/изменения YYYY-MM.md` (changes) | human | What was changed, when and by whom (section 15.1) |
| `_логи/рассуждения YYYY-MM.md` (reasoning) | human | Why the model made its decisions (section 15.2) |
| `_логи/архив вопросов.md` (question archive) | human | Answered questions with their answers (section 7.4) |
| `_логи/структура утверждена YYYY-MM-DD.md` (structure approved) | human | The approved structure draft (section 6.3) |
| `_логи/ошибки.log`, `_логи/плагин.log` (errors, plugin) | developer | Unexpected errors of the program and the plugin (section 15.4) |
| `.system/reflection.jsonl` | program | The reflection log (section 15.3) |
| `.system/usage.jsonl` | program | The log of calls and costs (section 14.1) |

### 15.1 Change log

A shared human-readable log of the whole system, not just Phase 1: what changed, when, and by whom — the **user**, the **model** or the **program**. It complements the technical git diff (section 11.2) with a meaningful explanation. A new file is started every month. Example lines:

```
- 12.03.2026 14:05 · модель · [[2026-03-12 Pulse via flash]] → [[Heart-rate monitor]] (уверенность 84)
- 12.03.2026 14:06 · модель · [[2026-03-12 Pulse via flash]]: извлечено аспектов — 4
- 13.03.2026 09:30 · пользователь · [[Book club]]: classification: общий → 80
- 13.03.2026 09:31 · программа · Фаза 1: готово — 12 обращений, 41 тыс. токенов, $0,03
```

The program writes these lines in Russian: модель — model, пользователь — user, программа — program; уверенность — confidence; извлечено аспектов — aspects extracted; общий — global; готово — done; обращений — calls; тыс. токенов — thousand tokens.

The log records the sorting and moving of entries, aspect extraction, creation and restructuring of containers, manual edits (statuses, links, thresholds, style), answers to questions, Phase 2 documents, vector recomputation, and the result of every run.

### 15.2 Reasoning log

Why a particular decision was made: what was confusing, which alternatives were considered. It is not generated separately — it is filled from the `reasoning` field of the model's responses (section 9.1), including nested ones: each segment, duplicate and contradiction has its own explanation. Each record is a heading with the time, step, object and model, followed by explanations point by point:

```
### 12.03.2026 14:05 · Классификация · файл «pulse.txt» · Z.ai
- **фрагмент 1 → «Heart-rate monitor»**: this is about measuring the pulse with the phone camera — the core of the sub-project…
```

(Классификация — Classification, файл — file, фрагмент — fragment.) A new file is started every month.

### 15.3 Reflection log

A service layer on top of the system's work. Every decision that involves a guess by the model is recorded separately from the result; when the user's decision appears (an answer to a question, a manual move, a threshold edit), it is recorded alongside — producing a "guess — decision" pair. The goal is accumulated statistics for calibrating thresholds: if the system consistently errs in one direction for some container or source, this becomes visible, and the thresholds can be adjusted — by yourself or on the model's advice (section 10.5).

The format is JSON Lines, one line per record. A guess: `type: assumption`, `ref` (a number like `r12`), `kind`, `subject` (what it is about), `assumption`, `confidence`, `model` — the model that made the decision, so that statistics do not mix when the model changes — and additional fields of the kind. A decision: `type: decision`, the same `ref`, `kind`, `decision` and `matched` — whether it matched the guess (`true`, `false` or `partial`).

| Kind (`kind`) | Guess | User's decision |
| --- | --- | --- |
| `classification` | Container and confidence **without taking the hint into account**; alongside — the hint, the confidence of its option, the threshold, what was done (sorted, quarantine), by whom (the model or the hint) | Answer to "Where to file the entry" or a manual move (section 10.2) |
| `mode_guess` | File mode and confidence | Answer to "How to process the file" |
| `compaction` | Whether condensing is needed, noisiness, threshold and source | — (noisiness statistics) |
| `structure_draft` | Containers proposed in the draft | How many were approved, what was deleted, added, renamed |
| `outdated` | A new aspect revises an old one | Answer to "Does the new thought revise the old one?" |
| `conflict` | A contradiction and a guess: the first is right, the second, or a fork | Answer to the contradiction question |
| `seed_to_project`, `subcontainer` | A sprout has grown into a project; a sub-container is needed | Answer to the structure question |
| `base_loss`, `product_loss` | Whether a loss found in version comparison is significant | Answer to the loss question |
| `composite_type` | A new composite type | Accepted or rejected |
| `revalidation_hint` | A similar entry in another container, and the similarity | A move or "all correct" |
| `deep_revalidation` | The container on recheck, and the confidence | Answer to the recheck question |
| `thresholds_advice` | Proposed threshold values and the current ones | Which values were accepted and which were not |

The log is append-only and needs no versions: it is a cumulative service layer, not an entity whose content changes.

### 15.4 Errors and the developer report

**Program errors.** Expected situations — no key, the server does not respond, an invalid settings format — the program explains in plain words and suggests what to do. An unexpected error is written to `_логи/ошибки.log` together with the command and the full traceback; the user sees a short message: everything processed has been saved, and a new run will continue from the same place.

**Plugin errors** are shown in place — a red frame "Plugin error…" («Ошибка в плагине…») with a "Copy report" button («Скопировать отчёт») — and written to `_логи/плагин.log` (over 512 KB, the previous log becomes `плагин.log.old`).

**The developer report** — the "Build report" button («Собрать отчёт»; Settings → Second Brain → Advanced, «Дополнительно») or the plugin command "Developer report" («Отчёт для разработчика»). The report includes the versions of the program, the plugin, Obsidian and the system, the latest plugin errors, the end of `ошибки.log` and the output of the last three runs. It contains no API keys and no note texts. The report is saved to `_логи/отчёт для разработчика.md` (developer report), opened and copied to the clipboard — it can be pasted into a message right away.

## 16. Data formats

The program's data are ordinary files. In the vault these are Markdown notes with a YAML header: container cards, entries and documents. In `.system/` there are JSON files: aspect pools, synthesis bases, questions, state, logs. Below are the fields of each format. What of this can be edited by hand is stated in section 3.6; everything else is set and changed by the program.

Links to other notes are written in YAML as `"[[Name]]"`. Next to each such link the `id` of the same object is stored (`parent` and `parent_id`, `container` and `container_id`): by the `id` the program recognizes the object even if it has been renamed, and by a mismatch between the link and the `id` it notices a manual edit. The `type` and `container_status` fields can also be written in Russian: `проект`, `росток`, `вопрос` (project, sprout, question); `активный`, `завершён`, `спит` (active, completed, dormant).

### 16.1 Container card

```yaml
type: project                  # project | seed | question (section 3.3)
id: k004                       # set by the program; the container's name = the card's file name
color: "#7FB0F5"               # color (section 3.7)
parent: "[[Running app]]"      # main parent; null — top level
parent_id: k001
applies_to: ["[[Sleep tracker]]"]  # where else it is applied (section 3.2)
applies_to_ids: [k007]
container_status: active       # active | completed | dormant (section 3.5)
description: "Measuring the pulse with the phone camera: a finger on the lens, the flash as the light source."
created: 2026-02-10
last_modified: 2026-03-12      # updated by the program when the container's content changes
needs_review: false
review_reason: null
thresholds:                    # own thresholds (section 10.5); no field — as the parent's or the general ones
  classification: 75
style: "Shorter, in lists"     # own document style (section 8.3)
```

| Field | Meaning |
| --- | --- |
| `type` | Kind of node: project, sprout or question. |
| `id` | The container's permanent number (`k` and three digits). It does not change on renaming or moving. |
| `color` | The container's color; its entries are highlighted in the same color. |
| `parent`, `parent_id` | The main parent — it determines which folder the container is in. |
| `applies_to`, `applies_to_ids` | Links to containers in other branches where this project is applied. This is not nesting. |
| `container_status` | Status: active, completed, dormant. |
| `description` | Description. The model relies on it when deciding what belongs to the container. If the user created a card without a description, the program takes the first paragraph of the text. |
| `created`, `last_modified` | The creation date and the date of the last change of content (new thoughts, moved entries, answers that change the pool). `last_modified` is used to check for forgotten sprouts (section 7.1). |
| `needs_review`, `review_reason` | Whether the user needs to check something and why. |
| `thresholds` | Own threshold values. The keys are the threshold names (section 17) or their Russian names. A wrong value does not break anything: the program warns and takes the inherited one. |
| `style` | Own document style. Inherited by nested containers that have no style of their own. |

### 16.2 Entry

```yaml
type: entity
id: e00042                     # set by the program
content_type: thought          # thought | diary | resource | question | ai_dialogue | product_edit | …
source: "заметка"              # source: the subfolder of _staging (section 4.1)
container: "[[Heart-rate monitor]]"
container_id: k004
shared: false                  # true — the entry is in _shared
also_in: ["[[Sleep tracker]]"]  # other containers of a shared entry
also_in_ids: [k007]
created: 2026-03-12            # date of the thought: from the header, from a diary date, or the file date
source_file: "_исходники/2026-03-12 pulse.txt"
segment: "3-7"                 # which paragraphs of the original; null — the whole file
source_part: "2 из 5 · 12.03.2026"  # only for a diary split by dates (section 4.2)
hint: "Heart-rate monitor"     # hint from the file header (section 4.4)
status: processed              # draft → processed; outdated — the thought is outdated
conflicts_with: []             # manual mark of a dispute with another entry: ["[[entry name]]"]
needs_review: false
review_reason: null            # low_confidence | new_container | user_hint_mismatch | incomplete
quarantine: false              # true — the entry is in _на_проверку and awaits an answer
incomplete: false              # the model considered the thought incomplete (section 6.6)
compacted: false               # whether it has been condensed (section 6.7)
aspect_ids: [a118, a119]       # links to aspects in the container's pool
```

The program writes these values in Russian: `заметка` (note) is the name of the source subfolder, `2 из 5` means "2 of 5".

Below the header is the entry's text, unchanged. If the entry has been condensed, a section `## Уплотнённая версия (создана программой)` ("Condensed version (created by the program)") with the compressed text is added below the text: from then on, that is what goes into processing, while the original stays in place (section 6.7).

The entry does not contain the aspects themselves — only their numbers. The aspects of a shared entry are in the pools of all its containers. Status `draft` — the entry is still being worked on; `processed` — it has gone through Phase 1 and is immutable (section 4.3); `outdated` — it is outdated: its aspects do not go into synthesis bases.

### 16.3 Aspect pool

File `.system/data/pools/<container id>.json`. For human reading — the `_аспекты.md` (aspects) view in the container's folder.

```json
{
  "container_id": "k004",
  "aspects": {
    "a118": {"id": "a118", "type": "fact", "text": "The flash light passes through the finger and produces a visible pulsation.",
             "source_entity": "e00042", "date": "2026-03-12", "status": "active", "value": 74, "duplicate_of": null},
    "a131": {"id": "a131", "type": "fact", "text": "The pulsation through a finger with the flash on is clearly visible.",
             "source_entity": "e00057", "date": "2026-03-20", "status": "active", "value": 70, "duplicate_of": "a118"}
  },
  "composites": {
    "c3": {"id": "c3", "composite_type": "experience", "from": ["a101", "a118", "a120"],
           "text": "Tried measuring the pulse without the flash — noise; with the flash the signal is clean.",
           "status": "active", "value": 82, "created": "2026-03-12"}
  },
  "conflicts": [
    {"key": "a140|a152", "a": "a140", "b": "a152", "type": "plan", "assumed": "b",
     "assumption": "newer and more detailed", "reasoning": "…", "status": "asked", "decision": null,
     "ref": "r305", "created": "2026-03-21T10:02:11"}
  ],
  "rejected": [{"kind": "duplicate", "a": "a160", "b": "a118"}],
  "accepted_losses": []
}
```

**Simple aspect** (`aspects`):

| Field | Meaning |
| --- | --- |
| `id`, `type`, `text` | Number (`a…`), simple type (section 5.1) and wording. |
| `source_entity`, `date` | The source entry and its date. |
| `status` | `active`, `in_composite` (has become part of a composite and does not go into the base separately), `outdated` (section 5.5). |
| `value` | Content value 0–100; recalculated at every base build. |
| `duplicate_of` | If the aspect duplicates another one: the number of the original. |
| `replaced_by`, `outdated_by`, `status_before` | If the aspect is outdated: which aspect replaced it, where the mark came from (`user` — an answer to a question, `entity` — the entry is marked `status: outdated`) and what its status was before — so that the aspect can be restored. |
| `pinned` | The user returned the aspect after a loss: it counts as primary in any evaluation. |

**Composite aspect** (`composites`): number (`c…`), `composite_type` (section 5.2), `from` — which simple aspects it is built from, `text`, `status` (`active`; `needs_review` — one of its building blocks is outdated, and pool analysis will review the composite; `outdated` — the composite has been dissolved, and its building blocks are `active` again), `value`, `created`, `note` — why the composite was dissolved.

**Contradictions** (`conflicts`): a pair of aspects `a` and `b` of the same type; `assumed` — what the program considers right until the answer (`a`, `b`, or `both` — a fork); `assumption` and `reasoning` — why; `status` (`open` → `asked` → `resolved`; `rejected` — the user said there is no contradiction); `decision` — the user's answer; `ref` — a link to the record in the reflection log (section 15.3).

**Rejected proposals** (`rejected`): pairs the user has already said "no" to — so that they are not proposed again. Kinds: `duplicate`, `outdated`, `conflict`, `seed_to_project`, `subcontainer`.

**Accepted losses** (`accepted_losses`): aspects whose dropping out of the base the user considered intentional (section 6.13).

### 16.4 Synthesis base

File `.system/data/bases/<container id>.json`; next to it is the previous version `<id>.prev.json` for comparison. For human reading — the `_база синтеза.md` (synthesis base) view.

```json
{
  "type": "synthesis_base",
  "container_id": "k004",
  "container": "Heart-rate monitor",
  "built": "2026-03-21T10:05:40",
  "groups": [
    {"type": "experience", "items": [
      {"id": "c3", "type": "experience", "text": "…", "rank": "primary", "value": 82, "date": "2026-03-12",
       "sources": ["e00031", "e00042"], "dups": [],
       "parts": [{"id": "a101", "type": "action", "text": "…"}, {"id": "a118", "type": "fact", "text": "…"}]}
    ]},
    {"type": "fact", "items": [
      {"id": "a118", "type": "fact", "text": "…", "rank": "primary", "value": 74, "date": "2026-03-12",
       "sources": ["e00042", "e00057"], "dups": ["a131"]}
    ]}
  ],
  "excluded": ["a95"],
  "manual_conflicts": [],
  "needs_review": false,
  "review_reason": null,
  "thresholds": {"value_min": 30, "value_primary": 70}
}
```

| Field | Meaning |
| --- | --- |
| `built` | When it was built. Phase 2 documents remember this time in `based_on_synthesis`. |
| `groups` | Groups by type, in the order of the priority table (section 5.4). |
| `items` | The items of a group: primary ones first, and within that — by value. |
| `rank` | `primary` (value not below `value_primary`, or the aspect was returned by the user) or `secondary`. |
| `sources`, `dups` | All source entries, including the entries of duplicates, and the numbers of merged duplicates. |
| `parts` | For a composite — its building blocks. |
| `conflict` | The numbers of the aspects this item disputes. |
| `assumed_loser` | By the program's assumption, the item loses the dispute (no answer yet). |
| `fork` | A fork: both variants are right under different conditions (section 10.3). |
| `rejected_alt` | The user chose the other variant; the item stays as a rejected alternative and is always secondary. |
| `review` | The composite awaits review: one of its building blocks is outdated. |
| `pinned` | The item was returned by the user after a loss. |
| `excluded` | Aspects below the value threshold: they did not get into the base but remain in the pool. |
| `manual_conflicts` | Pairs of entries marked by the user in `conflicts_with`. |
| `thresholds` | The value thresholds the base was built with. |

Outdated aspects, duplicates, and the building blocks of composites do not get into the base as separate items: a duplicate adds a source to the original item, and a building block is visible inside its composite.

### 16.5 Document

```yaml
type: product
product_kind: summary          # summary — the "Summary file"; supplementary — an additional document
title: "Сводный файл"
container: "[[Heart-rate monitor]]"
container_id: k004
last_generated: 2026-03-21
style_override: null           # the style of this particular document (section 8.3)
based_on_synthesis: "2026-03-21T10:05:40"  # which base build it was written from
accepted_losses: []            # losses the user considered intentional
needs_review: false
review_reason: null            # «значимая потеря по сравнению с предыдущей версией»
```

`Сводный файл` is the fixed name of the "Summary file". The program writes the reason in Russian; the example means "significant loss compared to the previous version".

Below the header is the document's text. It can be edited by hand: the program will notice the edit and make an entry from it (section 8.5). `style_override` and `accepted_losses` are preserved every time the document is rewritten.

### 16.6 Questions

File `.system/questions.json`: the number counter `next` and the open questions `open`. An answered question is removed from `open` and appended to `_логи/архив вопросов.md` (question archive). For humans, the questions are in `open-questions.md` and in the panel's "Questions" tab («Вопросы») (section 7.2).

```json
{
  "next": 13,
  "open": {
    "Q12": {"id": "Q12", "kind": "classify", "title": "Куда отнести запись",
            "text": "Запись: [[Pulse measurement after a run]] (22.03.2026). …",
            "options": [{"label": "«Heart-rate monitor» — вариант модели (уверенность 64)", "value": {"to": "k004"}},
                        {"label": "Без контейнера (unsorted)", "value": {"unsorted": true}}],
            "free_text": true, "free_hint": "Или напишите название контейнера. …",
            "data": {"entity": "e00063"}, "dedup": "classify:e00063", "ref": "r311",
            "created": "2026-03-22T09:15:02", "note": null}
  }
}
```

The program writes the question texts in Russian: «Куда отнести запись» — "Where to file the entry", «Запись:» — "Entry:", «вариант модели (уверенность 64)» — "the model's option (confidence 64)", «Без контейнера» — "No container", «Или напишите название контейнера» — "Or type the name of a container".

`kind` is the kind of question; each kind has its own answer handler: `classify` (where to file), `mode` (bulk load or a single entry), `also_in` (shared entry), `clarify` (clarifying an incomplete thought), `outdated` (whether something is outdated), `conflict` (contradiction), `structure_seed` and `structure_sub` (sprout into a project, sub-container), `base_loss` and `product_loss` (a loss in the base and in a document), `composite_type` (a new composite type), `dormant` (whether a sprout is alive), `revalidate` (a revalidation result), `text_changed` (the text of a processed entry has changed), `dup_fix` (fixing an erroneous merge). `options` are the answer options; `free_text` — whether one can answer in one's own words; `data` — what the question refers to; `dedup` — the key by which the program avoids asking the same question twice; `ref` — a link to the record in the reflection log where the answer will go; `note` — why the answer could not be applied (shown under the question; the question remains open).

### 16.7 State

File `.system/state.json` is the pipeline's checkpoint. The program writes it after every step, so an interrupted run continues from the same place (section 11.3).

| Key | What it stores |
| --- | --- |
| `counters` | Number counters: containers `k`, entries `e`, aspects `a`, composites `c`, input files `i`, reflection log records `r`. |
| `items` | Accepted input files: the path in `_исходники`, the name and path in `_staging`, checksum, encoding, source, date, hint, mode, stage (`new` → `await_structure` → `ready` → `done`; `await_mode` — waiting for an answer about the mode), diary part, created entries, the progress of classifying a large file in parts. |
| `entity_stage` | The stage of each entry: `classified` → `asked` → `compacted` → `embedded` → `done`; quarantine — `quarantine` → `quarantine_wait`. |
| `cls` | The classification result of each entry: chosen container, confidence, alternatives, reasoning, mode, source file. |
| `dirty` | Containers whose base must be rebuilt, with the reasons and the build stage: `analysis` → `value` → `assemble` → `compare`. |
| `new_aspects` | Aspects that have arrived since the last build, by container. |
| `text_hash` | Checksums of the texts of processed entries (section 4.3). |
| `structure` | The structure draft: whether it awaits approval and whether it has ever been approved. |
| `revalidation` | The queue of an unfinished revalidation. |
| `restore_requests` | What the user asked to restore in documents (an answer to a loss question, section 8.4); taken into account at the next Phase 2. |
| `synth_sig` | A fingerprint of the data of the last Phase 2, per container: if it matches, the documents are up to date and the model is not called (section 8.1). |
| `advice`, `thr_seen` | The last threshold advice and the last seen thresholds and styles of containers — for the reflection log (section 10.5). |
| `rejected_types` | New composite types the user declined. |
| `user_outdated`, `auto_outdated`, `auto_cw`, `cw_seen` | Who set the "outdated" and "disputes" marks — the user or the program: to tell a manual edit from the program's own. |
| `css_enabled_once` | The color snippet has already been enabled once (section 3.7). |

### 16.8 JSONL logs

Machine-readable logs have one JSON line per event; the file is only appended to:

- `.system/reflection.jsonl` — the reflection log: "program's assumption — user's decision" pairs (fields — section 15.3);
- `.system/usage.jsonl` — every call to the model and to embeddings: time, run, step, profile, model, tokens, response time, cost (fields — section 14.1).

Logs for humans are Markdown files in `_логи/` (section 15).

## 17. Settings

All of the program's settings are in one file, `settings.yaml`, in the program folder (not in the vault). The full list of fields, with defaults and an explanation on every line, is in the template [`settings.template.yaml`](settings.template.yaml); this section describes how the file is organized and what is in which group.

### 17.1 The file

- The program package contains not `settings.yaml` itself but the template `settings.template.yaml`. The `Установка.bat` installer (or the program itself on the first run of any command) copies the template to `settings.yaml`. That is why a new version unpacked over the old one does not overwrite the settings (section 19.3).
- API keys are not stored in the settings but in separate files next to the program: `api_key.txt`, `api_key_<id>.txt` for other profiles, `embeddings_api_key.txt` for cloud embeddings (section 13.2).
- Missing fields take their default values; settings from earlier versions are converted to the current form when read.
- The file can be saved in UTF-8 or in "ANSI" (cp1251) — the program understands both. A Windows path with backslashes in quotes (`"D:\Notes"`) is corrected to forward slashes automatically.
- An error in the YAML does not lead to an obscure failure: the program names the line number and the common causes — indentation with the Tab key, a missing quote, a colon in text without quotes.

### 17.2 How settings are edited

The most convenient way is in Obsidian: **Settings → Second Brain** (in the interface: «Второй мозг»; section 18.3). The window is built from a schema supplied by the program: every field has a name, an explanation, limits and a default value. A change is saved automatically, a second after the edit. The program checks all values together and, if everything is correct, rewrites `settings.yaml` in full — with the same explanations as in the template; the previous file remains as `settings.yaml.bak`. An invalid value is not saved: "Not saved: …" («Не сохранено: …») with the reason appears at the top of the tab. The ↺ button next to a field restores the default value. The search box at the top of the window searches the names and explanations on all tabs.

The file can also be edited in any text editor: the program will read it at the next command.

### 17.3 Groups

| Group | What it sets | Plugin tab | Details |
| --- | --- | --- | --- |
| `vault` | The vault folder — for running commands from the console; the plugin always works with the open vault. Filled in by `Установка.bat`. | — | section 19.1 |
| `llm` | Mode (`cloud`, `local`, `webchat`), model profiles, the main cloud and local profiles, models for individual steps (`roles`), the web chat request limit, the number of retries after a format error. | "Models" («Модели»), "Advanced" («Дополнительно») | sections 13.1–13.5 |
| `embeddings` | Where embeddings are computed (`local` or `cloud`); the address, model, key and price of cloud embeddings; batch size, text limit, wait time; `server` — the parameters of your own model on llama.cpp. | "Models" | section 12 |
| `budget` | The monthly budget for cloud models and the warning threshold (`warn_pct`, 10–99%). | "Costs" («Расходы») | section 14.3 |
| `estimate` | The estimate before a large run: whether it is enabled, and from what number of calls, cost or duration to ask for confirmation. | "Costs" | section 14.4 |
| `input` | `split_by_dates` — split a diary by dates. | "Inbox" («Входящие») | section 4.2 |
| `updates` | `check_on_start` — whether to check for an update when Obsidian starts. | "General" («Основное») | section 19.3 |
| `thresholds` | General thresholds: sorting without a question, hint weight, high confidence, mode guess, condensing, minimum and primary value, similarity of duplicates, neighbors and patterns. | "Thresholds" («Пороги») | section 6.5 |
| `seed_dormancy_days` | After how many days without new thoughts to ask whether a sprout is alive. | "Thresholds" | section 7.1 |
| `dialogue_markers` | What the user's lines (`я:`, "me:") and the AI's lines (`ИИ:`, "AI:") start with in dialogues. | "Inbox" | section 4.2 |
| `sources` | Sources — the subfolders of `_staging`: name, label color, shift of the condensing threshold. | "Inbox" | sections 4.1, 6.7 |
| `style` | `global` — the general style of Phase 2 documents. | "Documents" («Документы») | section 8.3 |
| `limits` | Request limits: containers in a classification request (150), elements per value evaluation (400), clarifying questions per entry (3). Usually there is no need to change them. | "Advanced" | sections 6.4, 6.6, 6.10 |

### 17.4 Container and document settings

Some settings can be overridden for a single container — with the `thresholds` and `style` fields in its card (section 16.1; it is more convenient on the panel's "Container" tab, section 10.5) — and the style of a single document with the `style_override` field in its header (section 16.5). Own thresholds and style are inherited by nested containers that have none of their own. The `mode_guess` threshold can only be general: the mode is decided before it is known which container the thought will go to.

The settings of the plugin itself — the program folder, Python, notifications — are stored separately, in the plugin's file in the vault (section 18.3).

## 18. Obsidian plugin

The Second Brain plugin (listed in Obsidian as «Второй мозг») is the program's interface inside Obsidian: buttons instead of the command line, a settings window instead of editing `settings.yaml`, and the run progress, questions and costs in plain view. The plugin contains no processing logic: the Python program does everything, and the plugin runs its commands and shows the result. Simple edits — a container's type and status, its thresholds and style, the "Structure approved" checkbox («Структура утверждена») in the draft — the plugin makes itself through the Obsidian API.

### 18.1 How it works

**Files.** The plugin lives in the vault, in `.obsidian/plugins/vtoroy-mozg/`: `main.js`, `manifest.json`, `styles.css`, and `data.json` — its own settings (section 18.3). It is installed by `Установка.bat` (the `setup` command) or by the `install-plugin` command: it copies the three files from the program's `plugin/` folder, writes the program folder and the path to the Python of the `.venv` environment into `data.json`, and enables the plugin in the vault's list of community plugins. When a vault with the plugin is opened for the first time, Obsidian asks whether you trust the vault's author — choose "Trust author and enable plugins". If the vault is open in restricted mode: Settings → Community plugins → turn off restricted mode and enable «Второй мозг». If Obsidian was open during installation, it needs to be restarted.

**Running commands.** Each command is a separate process in the program folder:

```
python -X utf8 -m brain --json [--ask-stdin] --vault <open vault> <command>
```

The plugin always works with the vault open in Obsidian, not with the one written in `settings.yaml`. Commands that change the vault run strictly one at a time: the next ones wait in a queue, and an identical run that is already queued is not added a second time. Quick actions — answering a question, editing YAML — join the same queue so as not to collide with a run. Commands that do not change the vault — connection check, update check, reading and saving settings, the state of your own model — run in parallel. The program itself also prevents two commands from working with the same vault: a second one, started for example from the console, refuses with an explanation (section 11.3). If the program folder is not found (it was moved or deleted), the panel and the settings say so and offer to specify the folder.

**Live lines.** While a command is running, the program prints service lines from which the plugin draws the progress:

| Line | What it conveys |
| --- | --- |
| `@@PROGRESS` | The stage, the number of the current item, the total, the item's name; a nested stage — for example, the parts of a large file. |
| `@@WAIT` | The program is waiting for the model's response: step, profile, model, since when. |
| `@@USAGE` | Usage: each call and the run total — tokens and money. |
| `@@NOTICE` | A warning along the way, for example «израсходовано 80% бюджета» ("80% of the budget spent"). |
| `@@ASK` | A question in the middle of a run (section 18.4). |
| `@@RESULT` | The result at the end: success or not, title, counters, error. |

**State snapshot** `.system/ui.json`. The program writes it after every command and on the `snapshot` command; the plugin rereads it every three seconds and computes nothing in the vault by itself. The snapshot contains:

- the program version and the vault;
- status: the number of containers, entries, documents and questions; the stages of entries (processed, awaiting an answer, queued) and of input files; new files in `_staging`; containers whose bases await a rebuild; the structure draft — whether it awaits approval and whether it has ever been approved; web chat requests awaiting a response; whether there is unfinished work;
- containers: the tree, type, status, number of entries, documents and questions, the state of the synthesis base, the effective thresholds and where each comes from (own, from the parent, general), the style;
- open questions with their options;
- general thresholds with descriptions and slider limits, the names of types and statuses, sources;
- the cost summary (section 14.5) and the update check setting;
- links to the logs, the warnings and messages of the last run.

### 18.2 Panel

The panel opens with the brain icon on the left ribbon or with the "Open panel" command («Открыть панель») and by default sits in the right sidebar. At the top are the name, the state ("ready", "working", "awaiting an answer: 2", "no connection to the program" — «готов», «работает», «ждут ответа: 2», «нет связи с программой»), the ↻ "Refresh status" button («Обновить состояние»), and the gear — the plugin settings. Below are five tabs.

**Overview** («Обзор»).

- **On the first load** — a three-step wizard. Step one, "Put your notes in `_staging`" («Сложите заметки в `_staging`»), shows how many files are already there and offers "Open the _staging folder" («Открыть папку _staging») and "New thought" («Новая мысль»). Step two, "Phase 1 — structure draft" («Фаза 1 — черновик структуры»), has the "Run Phase 1" button («Запустить Фазу 1»). Step three, "Check the draft and approve it" («Проверьте черновик и утвердите»), has "Open draft" («Открыть черновик») and "Approve structure" («Утвердить структуру»). Approval: the plugin saves the open draft, ticks the "Structure approved" checkbox in it, and runs Phase 1.
- **After that** — blocks for what needs attention: the structure draft awaits approval ("Open draft", "Approve structure"); a response from the web chat is awaited ("Open request" — «Открыть запрос», "Open response file" — «Открыть файл ответа»); N questions await an answer ("Answer" — «Ответить»); new files in `_staging` ("Process (Phase 1)" — «Обработать (Фаза 1)»); processing is unfinished ("Continue (Phase 1)" — «Продолжить (Фаза 1)»). If there is nothing — "Everything is processed" («Всё обработано»).
- Action buttons: "Phase 1: process new" («Фаза 1: обработать новое»), "New thought", "Phase 2: documents…" («Фаза 2: документы…»), "Revalidation…" («Ревалидация…»), "Patterns" («Паттерны»), "Check connection" («Проверить связь»).
- Counters: containers, entries, documents, questions, and a line of stages ("processed 120 · awaiting an answer 3 · queued 5").
- The current model and its cost this month, the cost of all models, the budget bar; the "Costs →" link («Расходы →»).
- The warnings of the last run and the container tree with the number of entries; a container whose base awaits a rebuild is marked. Clicking a container opens it on the "Container" tab.

**Questions** («Вопросы»). Cards of open questions: the text, the options, a "Your own answer" field («Свой ответ»), links to the entry and the container. An answer is applied immediately (the `answer` command); if a run is in progress, it joins the queue ("will be applied after the current run" — «применится после текущего запуска»). A filter by container. Details are in section 7.3.

**Container** («Контейнер»). The one selected in the list, or the container of the open note (the "by the open note" toggle — «по открытой заметке»). Type and status are drop-down lists; the plugin writes them into the card. The number of entries, questions, synthesis base items and aspects below the value threshold; links to the pool and base views. The container's documents, with an "under review" mark («на проверке»); the "Write documents (Phase 2)" («Написать документы (Фаза 2)») or "Update documents (Phase 2)" («Обновить документы (Фаза 2)») button and "Recheck sorting" («Перепроверить раскладку»; container revalidation, section 10.1). The "Container thresholds" block («Пороги контейнера», section 10.5) and "Document style" («Стиль документов», section 8.3).

**Costs** («Расходы»). The summary from section 14.5: totals for periods, budget, model cards with prices, by step, by day, recent runs. Prices and the budget are edited right here; after prices change, the plugin offers to recalculate past calls.

**Log** («Журнал»). The runs of this Obsidian session: an icon (⧗ queued, ▶ running, ✓ done, ✗ error, ■ stopped), time, duration, how long the models were thinking, tokens and money, the result and the program's full output ("program output" — «вывод программы»). Links to the logs: "Changes" («Изменения»), "Model's reasoning" («Рассуждения модели»), "Question archive" («Архив вопросов»), "Errors" («Ошибки»), `open-questions.md`.

**During a run**, a progress block is shown at the top of the panel:

- the stage and the count ("Parsing files: 12 of 80" — «Разбор файлов: 12 из 80»), a nested stage, a bar;
- how long the run has been going and how much is left — based on the stage's average speed, after the first finished item (in web chat mode there is no time: the model is not waited for);
- "Waiting for the model's response: 0:15 · Classification · Z.ai" («Ждём ответа модели: 0:15 · Классификация · Z.ai») — a stopwatch, the step and the profile;
- "This run" («Этот запуск») — tokens and money;
- "Queued: …" («В очереди: …») — what will start next;
- "Stop" («Стоп») and "Abort now" («Прервать сразу», with confirmation) — section 11.3; "Program output" («Вывод программы»).

The result of a run is an Obsidian pop-up message and a line in the "Log".

**The status bar** at the bottom of the window: without a run — «Второй мозг» or «Второй мозг · 3 вопроса» ("Second Brain · 3 questions"); during a run — what is going on, the count, the wait for the model or the remaining time, the duration. A click opens the panel.

**Narrow column.** The panel adapts to its width: the tabs wrap onto a second line, the state in the header moves under the name, and the counters at widths up to 360 pixels go two per row.

### 18.3 Settings

Settings → Second Brain («Второй мозг»). The window is built from the program's schema (the `settings` command): the fields, explanations, limits, defaults and validation live in the program (section 17.2). It works both in a separate settings window and in the usual modal one. At the top is a search across all tabs.

| Tab | What it contains |
| --- | --- |
| General («Основное») | "Program" («Программа»): the program folder, Python, "Connection check" («Проверка связи»). "Windows notifications" («Уведомления Windows»). "Updates" («Обновления»): "Check when Obsidian starts" («Проверять при запуске Obsidian»), "Check for updates" («Проверить обновления»). |
| Models («Модели») | "Language model" («Языковая модель»): mode, profiles, "Profile to edit" («Профиль для правки»), "＋ Cloud" («＋ Облачный»), "＋ Local" («＋ Локальный»), "Copy" («Копия»), deletion (section 13.2). "Models for individual steps" («Модели для отдельных шагов», section 13.3). "Embeddings (similarity search)" («Эмбеддинги (поиск похожего)») with the "Own model" block («Своя модель»): what has been downloaded, whether the server is running, "Start model…" («Запустить модель…»), "Shut down" («Остановить»), the server log (section 12.3). "Connection check". |
| Thresholds («Пороги») | "General thresholds" («Общие пороги») — a slider and a field for each, plus the sprout check period. |
| Inbox («Входящие») | "Sources" («Источники»; "Add source" — «Добавить источник»), "Dialogue markup" («Разметка диалогов»), "Split diary by dates" («Делить дневник по датам»). |
| Documents («Документы») | The "General style" («Общий стиль») of documents. |
| Costs («Расходы») | "Budget" («Бюджет»), "Estimate before a large run" («Оценка перед большим запуском»), a link to the panel's "Costs" tab. |
| Advanced («Дополнительно») | "Limits" («Пределы»), "Retries after a format error" («Повторов при ошибке формата»), "Web chat request limit" («Предел запроса веб-чата»). "Service" («Служебное»): "Open prompts folder" («Открыть папку промптов»), the settings file ("Show in folder" — «Показать в папке»), "Build report" («Собрать отчёт», section 15.4). |

Fields that are needed only for a certain value of another field are shown conditionally: for example, the key and price of cloud embeddings appear only with "Cloud service" («Облачный сервис»). For a field that differs from its default, the ↺ button is bright; at the default value it is dim. Keys are entered in a field that does not show them and are saved to files next to the program (the `settings --key` command); the window shows only that the key is saved ("key saved" — «ключ сохранён»).

**The plugin's own settings** are stored in its `data.json`, not in `settings.yaml`:

| Setting | Default | Meaning |
| --- | --- | --- |
| Program folder («Папка программы») | set by the installer | Where `brain/` and `Установка.bat` are. |
| Python | empty | Empty — the Python of the `.venv` environment created by the installer. |
| Notify when a long run finishes («Сообщать об окончании долгого запуска») | yes | A system notification at the end of Phase 1, Phase 2 or revalidation. |
| Long run — longer than, minutes («Долгий запуск — дольше, минут») | 2 | 0 — notify about any run. |
| Notify when the program awaits an answer («Сообщать, когда программа ждёт ответа») | yes | For example, the budget is exhausted or a large run needs confirming. |
| Only when Obsidian is not in focus («Только когда Obsidian не в фокусе») | yes | Turned off — notifications always arrive. |
| Skipped version («Пропущенная версия») | — | The version the user decided not to install (section 19.3). |

Notifications are Windows system notifications. Cancelled runs are not reported. Clicking a notification opens Obsidian and the panel. "Test notification" («Пробное уведомление») → "Show" («Показать») checks whether they are allowed; if no notification appears, allow notifications for Obsidian in the Windows settings (System → Notifications).

### 18.4 Commands and windows

Commands in the Obsidian command palette (Ctrl+P), all with the «Второй мозг:» prefix (Second Brain:):

| Command | What it does |
| --- | --- |
| Open panel («Открыть панель») | Opens the panel. |
| Phase 1: process new («Фаза 1: обработать новое») | `run` (section 6). |
| New thought («Новая мысль») | The new thought window (section 4.5). |
| Answer questions («Ответить на вопросы») | The "Questions" tab. |
| Phase 2: write documents… («Фаза 2: написать документы…») | Choosing a container → `synth` (section 8). |
| Phase 2 for the open note's container («Фаза 2 для контейнера открытой заметки») | The same without choosing. |
| Show the open note's container («Показать контейнер открытой заметки») | The "Container" tab. |
| AI advice on container thresholds… («Совет ИИ по порогам контейнера…») | Choosing a container → `advise` (section 10.5). |
| Revalidation… («Ревалидация…») | Choosing a container or "All containers" («Все контейнеры») → `revalidate` (section 10.1). |
| Patterns: search for new composite types («Паттерны: поиск новых составных типов») | `patterns` (section 10.4). |
| Check connection to the model («Проверить связь с моделью») | `check`. |
| Model costs («Расходы на модели») | The "Costs" tab. |
| Check for program updates («Проверить обновления программы») | `update --check` (section 19.3). |
| Refresh status («Обновить состояние») | `snapshot`. |
| Developer report («Отчёт для разработчика») | Section 15.4. |
| Stop («Стоп») | The same as the "Stop" button. |

**Plugin windows:** confirmation; choosing an option — a question from the program in the middle of a run, an offer to update, an Obsidian restart; choosing a container with a search by name; "New thought" (section 4.5); "AI advice on thresholds" («Совет ИИ по порогам», section 10.5); the result of the connection check — for each item separately: the vault, each distinct step model, embeddings; the parameters of your own embedding model (section 12.3).

**Questions in the middle of a run.** Some decisions the program cannot make by itself: the budget is exhausted (section 14.3), the run is large, or it is a revalidation (section 14.4). Then it prints an `@@ASK` line with the question and options and waits. The plugin opens a window with the options, writes "The program is waiting for your answer" («Программа ждёт вашего ответа») in the run block, sends a notification if needed, and passes the choice to the program's standard input. A closed window means refusal. In the console, the same question is asked in the console window: the option number or «д/н» (y/n). If it is impossible to ask, a safe default applies — it is given in sections 14.3 and 14.4.

If the container's documents are up to date, Phase 2 ends without calls to the model; the plugin asks "Rewrite them anyway?" («Переписать их всё равно?») and, if you agree, runs it again with `--force` (section 8.1).

**When Obsidian starts** (after three seconds), the plugin first compares the plugin in the program folder with itself: if that one is newer (a new version was unpacked manually), it offers to install it and restart Obsidian. Then, if update checking is enabled, it looks for a new version of the program on GitHub (section 19.3).

### 18.5 Plugin errors

- Each part of the interface is drawn separately: the panel header, each panel tab, each section of each settings tab. An error in one part does not break the others: in its place a red frame appears, "Plugin error (panel, "Costs" tab)" («Ошибка в плагине (панель, вкладка «Расходы»)»), with the error text, a hint, and a "Copy report" button («Скопировать отчёт») — the versions of the plugin, the program, Obsidian and the system, and the error with its stack.
- Unhandled window errors whose stack contains the plugin itself are also recorded — without pop-ups. The plugin does not touch errors of other plugins or of Obsidian itself.
- The log is `_логи/плагин.log` (plugin) in the vault; above 512 KB the previous log becomes `плагин.log.old`. The last 30 errors are kept in memory; the same error repeated in a row is recorded once.
- Copying to the clipboard also works from a separate settings window.
- "Developer report" («Отчёт для разработчика») collects all of this together with the output of recent runs — section 15.4.

## 19. Installation and updates

### 19.1 Installation

**Requirements.** Windows, Obsidian, and internet access during installation. Python 3.10 or newer — if it is missing, the installer installs it itself. A graphics card is not required. Your own embedding model on the CPU needs at least 16 GB of RAM (section 12.3); cloud embeddings do not.

**Steps.**

1. An Obsidian vault — an existing or a new one (in Obsidian: "Create new vault" or "Open folder as vault"). The program creates its service folders itself.
2. The program archive is unpacked into a separate folder, for example `D:\Programs\Second Brain`. The program folder must not be inside the vault: the program would take its own files for notes.
3. Run `Установка.bat`. It reports which step is in progress and, on an error, what exactly failed and what to do:
   - **Python.** Looks for Python 3.10+ (`py`, `python`, and the usual installation folders). If it finds none, it asks whether to install Python 3.12: it installs it only for the current Windows user, without administrator rights — via winget or, without it, with the installer from python.org.
   - **Environment.** Creates the `.venv` environment in the program folder; a damaged one (for example, after Python was reinstalled) is created anew.
   - **Libraries** from `requirements.txt`: PyYAML, requests, numpy, dulwich. Creates `settings.yaml` from the template and an empty `api_key.txt` if they do not exist yet.
   - **The `setup` command** — the program itself does the rest: removes the `.bat` files of earlier versions; finds Obsidian vaults from Obsidian's list of vaults (first the one open now, then by the time they were last opened) and asks which one to install the plugin into: Enter — the first one, or a number, or the path to the vault folder (the folder can be dragged into the window); if Obsidian is open, asks you to close it; installs the plugin (section 18.1) and writes the vault folder into `settings.yaml`; offers to download the embedding model and llama.cpp right away — with their sizes, and a warning if memory is low («д/н», y/n; this can be done later with the "Start model…" button, «Запустить модель…»); opens Obsidian.
4. In Obsidian — "Trust author and enable plugins". The «Второй мозг» panel appears on the right.
5. Settings → Second Brain → Models (in the interface: Второй мозг → Модели): the API key, the profile's model, "Check connection" («Проверить связь») (section 13).
6. Notes go into `_staging/архив/` (archive), then "Run Phase 1" («Запустить Фазу 1») in the first-load wizard (section 18.2).

If `Установка.bat` is run straight from the archive (from a Windows temporary folder), it asks you to unpack the archive first.

**Running `Установка.bat` again** repairs the installation: it reinstalls the libraries and the plugin and recreates a broken environment. It does not touch settings, keys or notes. It is worth running if the program folder was moved, Python was reinstalled, or the plugin disappeared from the vault.

### 19.2 Program folder

| Path | What it is |
| --- | --- |
| `brain/` | The Python program (section 21). |
| `prompts/` | Prompts (section 9); `prompts/_прежние/` (previous) — earlier versions of prompts the user had edited, kept after an update. |
| `plugin/` | The built plugin: `main.js`, `manifest.json`, `styles.css`. |
| `plugin-src/` | The plugin's TypeScript source code and its tests (sections 21, 22). |
| `tests/` | The program's tests (section 22). |
| `settings.template.yaml` | The settings template. |
| `settings.yaml`, `settings.yaml.bak` | Settings (section 17) and their previous version. |
| `api_key.txt`, `api_key_<id>.txt`, `embeddings_api_key.txt` | Keys for profiles and cloud embeddings. |
| `requirements.txt` | Python libraries. |
| `installed.json` | Which version is installed, where it came from, and the checksums of its files (section 19.3). |
| `Установка.bat` | Installation and repair. |
| `ИНСТРУКЦИЯ.md` | The user guide (in Russian). |
| `.venv/` | Python and the program's libraries; created by `Установка.bat`. |
| `models/` | The embedding model (another folder can be set in `embeddings.server.models_dir`). |
| `llama.cpp/` | llama-server builds; `server.json` — the running server; `server.log` — its log (section 12.3). |

In the vault, the program keeps only notes and its working data (section 3). Keys and settings stay in the program folder — they do not end up in the sync or in backups of the notes.

### 19.3 Updates

**Where from.** The source of new versions is a GitHub repository whose link is built into the program itself: the `UPDATE_REPO` line in `brain/__init__.py` (of the form `https://github.com/name/repository`). It is not in the user's settings. An empty line means updates are not checked, and the "Check for updates" button («Проверить обновления») is inactive. The repository must be public.

The new version is taken from the repository's latest release: the program archive among the release files (a `.zip` with «мозг» or "brain" in its name, otherwise the first `.zip`), and if there is none — the release's source code archive. If there are no releases — the default branch; its version is `__version__` from `brain/__init__.py`. Versions are compared numerically: `2.10.0` is newer than `2.9.1`.

**What changes.** The folders `brain/`, `prompts/`, `plugin/`, `plugin-src/`, `tests/` and the files in the root of the program folder (`.bat`, `.md`, `.txt`, and the template `settings.template.yaml`). Modules of `brain/` that are absent from the new version are deleted, and so are the `.bat` files of earlier versions. If `requirements.txt` has changed, the program installs the missing libraries. The plugin is also copied into the vault if it is installed there. If the `UPDATE_REPO` line is empty in the new version but contains a link in the installed one, the link is kept — otherwise the program would stop seeing the next versions.

**Never touched:** `settings.yaml` and `settings.yaml.bak`, the key and token files, the vault. `installed.json` is not copied from the new version — the program writes it itself, with the checksums of the files just installed.

**Prompts edited by the user.** `installed.json` stores the checksums of the installed files. If a prompt differs from the installed one (it was edited), then: if this prompt has not changed in the new version, the user's version stays; if it has changed, the new one is installed, the user's version is copied to `prompts/_прежние/<name> (<date> <time>).md`, and the update result says so.

**How it is run.**

- **From the plugin.** When Obsidian starts (if "Check when Obsidian starts" — «Проверять при запуске Obsidian», `updates.check_on_start` — is on), the plugin runs `update --check`. If the version is newer, a "New version available" window («Вышла новая версия») appears: the number, where it comes from, the release description, and "Install" («Установить»), "Later" («Позже»), "Skip this version" («Пропустить эту версию»). A skipped version is no longer offered at startup, but the next one is; the "Check for updates" button in the settings ("General" tab) checks immediately and shows any new version. "Install" runs `update --yes`: the update joins the plugin's queue and starts after the current run. Then a "Restart Obsidian" window («Перезапустить Obsidian») appears: the new plugin will work after the restart.
- **From the console.** `python -m brain update` asks for confirmation; `--yes` — without asking, `--check` — only check, `--force` — install even if the version is not newer.
- **Manually.** The new archive is unpacked over the program folder, then `Установка.bat` is run: it installs the missing libraries and updates the plugin in the vault. The archive contains neither `settings.yaml` nor keys, so the settings are not overwritten. Edited prompts are replaced with the new ones during manual unpacking — save copies of your edits beforehand. If `Установка.bat` is not run, the plugin will notice at the next Obsidian start that the program folder contains a newer plugin and will offer to install it and restart Obsidian.

## 20. Program commands

Usually the plugin runs the commands. From the console — in the program folder, with the `.venv` Python environment:

```
.venv\Scripts\python.exe -m brain <command> [options]
```

Without a command, the program prints the list of commands. In the console, questions are asked right in the window: the option number or «д/н» (y/n).

**Common options** (written before the command):

| Option | What it does |
| --- | --- |
| `--settings <path>` | Another settings file; by default — `settings.yaml` next to the program. |
| `--vault <folder>` | Another vault; `settings.yaml` is not changed. The plugin always passes the open vault. |
| `--json` | At the end — an `@@RESULT {…}` line with the result (for the plugin, section 18.1). |
| `--ask-stdin` | Questions in the middle of a run come as an `@@ASK {…}` line; the answer is a JSON line `{"choice": N}` on standard input (section 18.4). |

**Commands:**

| Command | What it does |
| --- | --- |
| `run [--yes]` | Phase 1: accept answers to questions and manual edits, process everything new from `_staging`, rebuild synthesis bases (section 6). Before a large run — an estimate and a question; `--yes` — without the question. |
| `synth [container] [--force] [--yes]` | Phase 2: write or update a container's documents (section 8). Without a name — a choice from a list. If nothing has changed since the last synthesis, the model is not called; `--force` — rewrite anyway. |
| `revalidate [container] [--ask] [--yes] [--count]` | A deep recheck of the sorting (section 10.1). Without a name — all entries; `--ask` — choose a container from a list; `--yes` — without confirmation; `--count` — only count the entries. |
| `patterns` | Search for new composite aspect types (section 10.4). |
| `advise [container]` | The model's advice on a container's thresholds; changes nothing by itself (section 10.5). Without a name — a choice from a list of all containers. |
| `answer <QID> --option <N>` or `--text "<answer>"` | Answer a question right away, without waiting for Phase 1. Options are numbered from zero (section 7.3). |
| `check` | Check the settings and the vault, each distinct model — the main one and the step models — with a test call, and embeddings with a test vector. The result is given for each item separately. |
| `status` | What is in progress now: entries, questions, queues, costs. |
| `usage [--reprice <profile\|emb\|all>]` | Costs: today, this month, all time, by profile and by step (section 14.5). `--reprice` — recalculate the cost of past calls at the current prices of a profile, of embeddings, or of all (section 14.2). |
| `estimate run`, `estimate synth <container>`, `estimate revalidate [container]` | An estimate of a run without running it: calls, time, cost (section 14.4). |
| `llama status [--hw]` | Your own embedding model (section 12.3): what has been downloaded, whether the server is running; `--hw` — also the computer's hardware. |
| `llama start [--params-json <file\|->]` | Download whatever is missing and start the model server; startup parameters — JSON from a file or from standard input. |
| `llama stop` | Stop the model server. |
| `llama download [--yes]` | Only download the model and llama.cpp. `pull-embeddings` does the same. |
| `update [--check] [--yes] [--force]` | Update the program from GitHub (section 19.3): `--check` — only check, `--yes` — without asking, `--force` — even if the version is not newer. |
| `snapshot` | Rewrite the `.system/ui.json` snapshot for the plugin (section 18.1). |
| `settings` | The schema and current values of the settings in JSON — the plugin builds the settings window from them. |
| `settings --set-json <file\|->` | Apply settings changes from JSON: validate them, rewrite `settings.yaml` with explanations, and keep the previous one in `settings.yaml.bak` (section 17.2). |
| `settings --key profile:<id>` or `--key embeddings` | Save a key from standard input to the key file of a profile or of cloud embeddings. |
| `install-plugin [vault]` | Only install the plugin into a vault (section 18.1). |
| `setup [vault]` | All-in-one installation — `Установка.bat` runs it after installing the libraries (section 19.1). |

In commands, a container is given by its name — quotes are not required (`synth Book club`) — by part of the name if it is unambiguous (`synth Heart`), or by its `id` (`synth k004`).

Any command except `setup` also removes the `.bat` files of earlier versions from the program folder.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| 0 | Done. |
| 1 | An understandable error (no key, the server does not respond, an invalid setting value) or a stop — the output says what to do. |
| 2 | An unexpected program error. Details are in `_логи/ошибки.log` (errors); everything processed before it has been saved, and a repeated run continues from the same place (section 15.4). |

## 21. Code map

### 21.1 The program (`brain/`)

A Python 3.10+ program; the libraries are PyYAML, requests, numpy and dulwich (git without installing git). The entry point is `python -m brain` (`__main__.py` → `cli.py`).

**The data path in Phase 1:** `cli.py` takes the vault lock and builds the context (`context.py`) → `phase1.py` applies answers (`answers.py`) and manual edits (`vault.py`) and accepts files (`ingest.py`) → the structure draft (`structure.py`) or classification (`classify.py`) → the steps of each entry (`pipeline.py`: questions, condensing, vectors via `embed.py` and `index.py`, aspect extraction) → building synthesis bases (`synthesis_base.py`) → views (`views.py`), versions (`versions.py`), questions (`questions.py`), the snapshot for the plugin (`snapshot.py`). All calls to the model go through `llm.py` with prompts from `prompts.py`; usage is recorded by `logs.py`.

| Module | What it does |
| --- | --- |
| `__init__.py` | The program version (`__version__`) and the link to the repository for updates (`UPDATE_REPO`). |
| `__main__.py` | The `python -m brain` entry point. |
| `cli.py` | Commands and their options (section 20), the vault lock, the `@@RESULT` result, exit codes, recording unexpected errors in `ошибки.log` (errors). |
| `config.py` | Reading `settings.yaml`: defaults, migrating earlier formats, clear YAML error messages. |
| `schema.py` | The settings schema for the plugin (tabs, fields, limits, threshold descriptions), value validation, writing `settings.yaml` with explanations, key files. |
| `profiles.py` | Model profiles, mode, models for individual steps (section 13). |
| `context.py` | The run context: settings, vault, models, logs, a container's effective thresholds, the "Stop" flag, progress. |
| `vault.py` | The vault: folders, cards, entries, documents, pools, synthesis bases, state; manual structure edits (renaming, moving, new cards), colors. |
| `util.py` | Files, dates, YAML headers, safe file names, reliable writing (via a temporary file, with retries when a file is busy). |
| `ingest.py` | Reading input files: encoding, service header, dates, dialogue markup, splitting a diary by dates (section 4). |
| `phase1.py` | Phase 1 as a whole (section 6.1). |
| `structure.py` | The structure draft and its approval (section 6.3). |
| `classify.py` | File mode, classification with segmentation, applying thresholds, the "Where to file the entry" question (sections 6.2, 6.4, 6.5). |
| `pipeline.py` | The steps of each entry: clarifying questions, condensing, vectors, aspect extraction (sections 6.6–6.9). |
| `aspects.py` | Aspect types, composite formulas, the priority table (section 5). |
| `ops.py` | Common operations on entries and containers: creating, moving, adding and removing aspects, dissolving composites. |
| `synthesis_base.py` | Pool analysis, value evaluation, building the synthesis base and comparing it with the previous one (sections 6.10–6.13). |
| `answers.py` | Applying answers: a separate handler for each kind of question, recording decisions in the reflection log (section 7.4). |
| `questions.py` | The question registry, `open-questions.md`, parsing ticked checkboxes and «Ответ:» (Answer:) replies. |
| `phase2.py` | Phase 2: a container's documents and version comparison (section 8). |
| `ondemand.py` | Revalidation and the search for new composite types (sections 10.1, 10.4). |
| `tuning.py` | Container thresholds and the model's advice: decision statistics, checking the proposals (section 10.5). |
| `llm.py` | The language model client: an OpenAI-format API, manual mode via web chat, a test model; retries, checking and fixing the response format (sections 13.4, 13.5). |
| `prompts.py` | Loading prompts from `prompts/` and substituting data (section 9). |
| `embed.py` | Embeddings — your own server, another compatible one, cloud or test ones — and the vector store (section 12). |
| `index.py` | The three-level vector index: entries, aspects, containers (section 12.2). |
| `llama.py` | Your own embedding model: the computer's hardware, downloading the model and llama.cpp, choosing a build, starting the server with the chosen parameters and stopping it (section 12.3). |
| `usage.py` | The cost of calls, the budget, recalculation at new prices, the cost summary (section 14). |
| `estimate.py` | The run estimate: calls, time, money (section 14.4). |
| `interact.py` | The `@@…` live lines for the plugin and questions in the middle of a run — in the plugin window or in the console (section 18.4). |
| `logs.py` | The change and reasoning logs, the reflection log, recording calls in the call log (section 15). |
| `versions.py` | Versions of synthesis bases and documents in the git mirror `.system/versions/` (section 11.2). |
| `views.py` | The `_аспекты.md` (aspects) and `_база синтеза.md` (synthesis base) views. |
| `snapshot.py` | The `.system/ui.json` snapshot for the plugin (section 18.1). |
| `install.py` | Installing the plugin into a vault, finding Obsidian vaults, cleaning up files of earlier versions (section 19.1). |
| `updater.py` | Updating from GitHub (section 19.3). |

Prompts are Markdown files in `prompts/` (section 9). The interface texts, program messages and prompts are in Russian.

### 21.2 The plugin (`plugin-src/`)

The plugin is written in TypeScript; esbuild bundles it into a single file, `plugin/main.js`, and puts `manifest.json` and `styles.css` next to it. Building: Node.js 18+; in the `plugin-src` folder run `npm install`, then `npm run build` (type checking first, then bundling). After building — `install-plugin` or `Установка.bat`, and restart Obsidian.

| File | What it does |
| --- | --- |
| `src/main.ts` | The plugin itself: palette commands, the panel, the status bar, reading the `ui.json` snapshot, YAML edits through the Obsidian API, Windows notifications, checks at Obsidian startup (a newer plugin in the program folder, a new version on GitHub), installing an update and restarting. |
| `src/engine.ts` | Running the program, the run queue, "Stop" and "Abort now", parsing live lines and the `@@RESULT` result, answers to `@@ASK`. |
| `src/view.ts` | The panel: the current run block and the "Overview", "Questions", "Container", "Costs" and "Log" tabs. |
| `src/settings.ts` | The settings window built from the program's schema: tabs, search, profiles, step models, ↺, autosave, the "Own model" block. |
| `src/modals.ts` | Windows: confirmation, choosing an option, text, choosing a container, "New thought", threshold advice, connection check, the parameters of your own model. |
| `src/report.ts` | Plugin errors: interception, the red frame, `плагин.log`, "Developer report". |
| `src/types.ts`, `src/util.ts` | Snapshot types and helper functions. |
| `styles.css` | Styling based on Obsidian theme variables: light and dark themes, a narrow column. |
| `manifest.json`, `package.json`, `tsconfig.json`, `esbuild.config.mjs` | The plugin description, build dependencies, TypeScript and build settings. |
| `tests/` | The plugin's tests (section 22.2). |

**Names in classes.** The plugin's classes extend Obsidian classes (`Plugin`, `PluginSettingTab`, `ItemView`, `Modal`, `FuzzySuggestModal`). Their own fields and methods must not be named the same as internal members of these classes: Obsidian calls those itself, and a plugin member with the same name breaks, for example, the settings window. Only names from the public API in `obsidian.d.ts` and the methods Obsidian expects from a plugin (`onload`, `display`, `onOpen`…) may coincide. This is checked by a test in real Obsidian (section 22.2).

## 22. Tests

The program and the plugin can be tested end to end without a real model, without internet access, and without Windows: the test model answers instead of the model, and local mocks stand in for GitHub, Hugging Face, and the provider.

### 22.1 The program (`tests/`)

**The test model.** `tests/fake_llm.py` gives plausible answers to all prompts (section 9.2) following simple rules, and once deliberately answers with a format error — to test fixing the response. It is enabled in the settings: `llm.mode: fake` (the module is `llm.fake_module`, by default `tests/fake_llm.py`) and `embeddings.mode: fake` — test vectors instead of the embedding model.

| Test | What it checks | How to run |
| --- | --- | --- |
| `smoke.py` | An end-to-end test with the test model, starting from an empty vault (see below). | `python tests/smoke.py [folder]` — in a temporary folder by default |
| `api_mock.py` | The network layer without a real provider: a local server in the OpenAI format (`chat/completions` and `embeddings`) with 429, 500 and 401 errors, a cut-off response and a non-JSON response; model profiles and their keys, tokens from the provider's response and from llama.cpp counters, cache, cost, the budget and the profile limit, recalculation at new prices, cloud embeddings with a price. | `PYTHONPATH=. python tests/api_mock.py` |
| `big_file.py` | A large file: splitting into portions that fit the model's window and resuming after a failure midway without duplicates. | `python tests/big_file.py [folder]` |
| `update_mock.py` | Updating without internet access: a local server in the GitHub API format — the latest release with the program archive, the source code archive, a repository without releases (branch, file tree, branch archive), errors. Settings and keys are untouched, edited prompts go to `prompts/_прежние` (previous), obsolete modules and the `.bat` files of earlier versions are removed, the plugin in the vault is updated. | `python tests/update_mock.py` |
| `fake_llama.py` | Not a test but mocks for your own embedding model: Hugging Face (the file list and the model file with resumable download), llama.cpp releases on GitHub, and a fake `llama-server` in Python (`--help`, `--list-devices`, `/health`, `/v1/models`, `/v1/embeddings`). They are used by `smoke.py` and the plugin test. | — |

**What `smoke.py` goes through:**

1. Bulk load of the archive: dates, hints, a dialogue with an AI, a file in cp1251, an empty file, an image.
2. Editing and approving the structure draft.
3. Sorting, questions, aspects, synthesis bases.
4. Answers to questions and YAML edits, including moving an entry (disputing the sorting).
5. A new thought that revises an old one — outdating of an aspect.
6. Phase 2: documents and versions.
7. A manual edit of a document → a new entry → rebuild.
8. Editing the text of a processed entry, a forgotten sprout, a failure in the middle of a run and resuming.
9. Changing the embedding model — recalculating the vectors.
10. Manual mode through a web chat.
11. A repeated run with nothing new — without calls to the model.
12. Other commands.
13. Manual edits: the type written in Russian, containers created by hand.
14. Commands for the plugin: the snapshot, answers, settings, a container's own thresholds, threshold advice, "Stop", plugin installation.
15. Converting settings of the earlier format, a diary by dates, the run estimate, questions via standard input (start, cancel, closed window), live progress lines, the call log and the summary.
16. All-in-one installation: finding and choosing the vault, the whole `setup`, removing the `.bat` files of earlier versions.
17. Your own embedding model: downloading from the mocks, starting, autostart, stopping, invalid parameters; updating when the repository link has not been written in.

### 22.2 The plugin (`plugin-src/tests/`)

**Test on an Obsidian mock** — `run_e2e.py`. The built plugin runs in Chromium on a mock of the Obsidian API (`obsidian-mock.js`, `harness.html`: workspace, vault, YAML, windows, settings, launching processes) together with the real program and the test model, and goes through the user's whole path: the first-load wizard, waiting for the model's response, approving the structure, questions, thresholds (slider, ↺) and threshold advice, style, Phase 2, "New thought", settings (tabs, search, profiles, step models), run progress "N of M", "Stop", "Costs" (prices, recalculation, budget), questions about the budget and a large run, notifications, the log, the dark theme, installing the plugin from the program folder, updating from a GitHub mock, your own embedding model (the parameters window, downloading from the mocks, starting the fake `llama-server`, the address in the settings, "Shut down"). Screenshots go to `<folder>/shots`.

```
pip install pyyaml requests numpy dulwich playwright
playwright install chromium
python plugin-src/tests/run_e2e.py /tmp/e2e
```

**Test in real Obsidian** — `run_real.py`. The mock knows about Obsidian only what has been written into it, so the same plugin is also tested in real Obsidian for Linux (the unpacked archive from github.com/obsidianmd/obsidian-releases) on an Xvfb virtual display; it is controlled through the Chromium debugging protocol. The path: installation with the `setup` command, "Trust author and enable plugins" («Довериться автору и включить плагины» — the test runs Obsidian in Russian), the wizard, Phase 1 and approving the structure, the panel tabs, the settings in a separate window and in a modal window (all tabs, search, thresholds, a profile with deletion confirmation, the connection check), "New thought", choosing a container, a plugin error (the frame, the clipboard, `плагин.log`), the developer report, console errors in all windows.

The last step checks the names in classes (section 21.2): the field and method names of each plugin class are compared with the names of the running Obsidian — the prototype chain of the base class and the fields of an empty instance of it, minus the public API and the methods Obsidian expects from a plugin. A match is a test failure. Obsidian's names are saved to `obsidian-names.json` — handy for comparing with the next version of Obsidian.

```
python plugin-src/tests/run_real.py /path/to/obsidian-<version> /tmp/real
```

`run_e2e.py` is designed for Linux or macOS (it prepares a test copy of the program with `.venv/bin/python`), `run_real.py` — for Linux with Xvfb; `REAL_KEEP=1` — do not close Obsidian after the test.

### 22.3 Environment variables for tests

| Variable | What it overrides |
| --- | --- |
| `BRAIN_SETTINGS` | The path to the settings file instead of `settings.yaml` next to the program. |
| `BRAIN_UPDATE_REPO`, `BRAIN_GITHUB_API` | The repository link (as if written into `UPDATE_REPO`) and the GitHub API address — for updating from a mock. |
| `BRAIN_HF_BASE`, `BRAIN_LLAMA_API` | The addresses of Hugging Face and of llama.cpp releases — for downloading from mocks. |
| `BRAIN_LLAMA_NO_SYSTEM` | Do not look for a `llama-server` installed on the computer. |
| `BRAIN_TEST_HW` | The computer's hardware (memory, graphics cards) — JSON on top of what was detected. |
| `BRAIN_OBSIDIAN_CONFIG`, `BRAIN_OBSIDIAN_RUNNING`, `BRAIN_NO_OPEN` | The folder with Obsidian's list of vaults, "whether Obsidian is open", and a ban on opening it — for testing the installation. |
| `BRAIN_APP` | The program folder for the plugin tests. |

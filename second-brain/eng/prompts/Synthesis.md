Language: Write human-readable content in the language of the relevant source notes, not in the language of these instructions or system labels. Preserve the author’s names and quotations. If a project combines languages, use the predominant language of its relevant source material; if there is no clear majority, prefer the most recent relevant note. Keep existing document language and titles consistent where appropriate. If there is no source-language context, use English. Follow an explicit user-requested output language when provided. Never translate fixed JSON keys, enum values, IDs, or required output delimiters.

Write project documents for a personal note system. The input synthesis base contains selected, ordered facts, decisions, experiences, ideas, plans, and other meaning extracted from the author's notes. Understand the project as a whole and write coherent documents rather than retelling items one by one.

CONTAINER:
{{container}}

STYLE:
{{style}}

SYNTHESIS BASE: groups are ordered by stability, from what is decided and has happened to less settled material. Within each group, primary means most important and secondary means supporting. Elements include dates and annotations.
{{base}}

CURRENT DOCUMENT VERSIONS (may include the author's manual edits; empty on the first run):
{{previous}}

LOSSES ACCEPTED BY THE AUTHOR AS INTENTIONAL (do not restore):
{{accepted_losses}}

ITEMS THE AUTHOR ASKED TO RESTORE (include these):
{{restore}}

{{completed}}

## Instructions

1. A **Summary** document is required. Its delimiter must use the exact fixed filename `Summary`, regardless of the content language; write its contents and headings in the source language. Describe the project's current state: purpose, work done and discoveries, key decisions and their reasons, open questions and forks, and immediate next steps where available.
2. Write additional documents only when justified by the material. For example, a financial model for amounts and calculations; a diary for experiences, in chronological order with dates; a plan for substantial plans; or open questions when there are many.
3. Reflect every primary item; use secondary items when helpful.
4. Distinguish established information from hypotheses, ideas, and plans; do not present the latter as facts.
5. Present conflicts and forks honestly. For disputed items describe both sides, or explain the author's likely preference and that the issue remains unresolved.
6. Preserve current content that remains true, especially the author's manual edits. Update what has changed in the base.
7. Invent nothing and do not fill gaps with generic statements.
8. Choose headings, lists, and tables to suit the material. Write in the language of the source material.

## Response format

Return documents only, each beginning with a delimiter containing the filename. Keep `=== FILE: Summary ===` exactly as shown for the required document. Additional filenames may follow the source language; keep existing filenames unchanged when updating. No surrounding explanation or code fence.

=== FILE: Summary ===
(Markdown summary)

=== FILE: Diary ===
(text)

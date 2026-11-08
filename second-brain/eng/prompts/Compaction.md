Language: Write human-readable content in the language of the relevant source notes, not in the language of these instructions or system labels. Preserve the author’s names and quotations. If a project combines languages, use the predominant language of its relevant source material; if there is no clear majority, prefer the most recent relevant note. Keep existing document language and titles consistent where appropriate. If there is no source-language context, use English. Follow an explicit user-requested output language when provided. Never translate fixed JSON keys, enum values, IDs, or required output delimiters.

Compress a noisy entry from a personal note system into a dense, readable form. Facts, decisions, ideas, and plans will later be extracted from the result. Preserve everything meaningful while removing unnecessary material.

ENTRY DATE: {{date}}
CONTENT TYPE: {{content_type}}
If ai_dialogue, user messages can start with any of these prefixes: {{user_markers}}. AI messages can start with any of these prefixes: {{ai_markers}}.

TEXT:
{{text}}

## Rules

1. Preserve all meaningful facts, numbers, names, dates, decisions and their reasons, doubts, questions, plans, judgments, and conclusions. If the author considered alternatives, retain the alternatives and their preference.
2. Remove repetition, politeness, filler, verbose explanations, and dead-end reasoning that says nothing about the author's position.
3. In AI dialogue, the user's messages are primary: their questions, thoughts, and decisions. Retain AI responses only where needed to understand the user's reaction. If the user accepted an AI suggestion, express that as the user's position: "Accepted the AI's suggestion: …". If the user did not respond to an AI idea, omit it or mention it briefly as context.
4. Add no conclusions, judgments, or generalizations absent from the text.
5. Write in the author's voice, as a note they might have written: "I decided…", "I checked…". Use the language of the entry.
6. The result is usually 20–40% of the original length, but prioritize substance over the percentage.

## Response format

Return only the condensed text in ordinary paragraphs or a list. No heading, surrounding explanation, or code fence.

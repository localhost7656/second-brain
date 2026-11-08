Language: Write human-readable content in the language of the relevant source notes, not in the language of these instructions or system labels. Preserve the author’s names and quotations. If a project combines languages, use the predominant language of its relevant source material; if there is no clear majority, prefer the most recent relevant note. Keep existing document language and titles consistent where appropriate. If there is no source-language context, use English. Follow an explicit user-requested output language when provided. Never translate fixed JSON keys, enum values, IDs, or required output delimiters.

Break one personal note entry into atomic units of meaning called aspects. The program will use these to build the project's knowledge base. You are not seeing the rest of the project; extract only what this entry supports.

CONTAINER: {{container}}
ENTRY DATE: {{date}}
CONTENT TYPE: {{content_type}}
If ai_dialogue, user messages can start with any of these prefixes: {{user_markers}}. AI messages can start with any of these prefixes: {{ai_markers}}.

TEXT:
{{text}}

## Aspect types

- fact: something that happened or exists, without interpretation.
- observation: a noticed detail or pattern, less rigorously verified than a fact.
- hypothesis: an untested assumption.
- idea: a proposed direction or solution.
- conclusion: a conclusion the author actually drew from evidence.
- question: an unresolved uncertainty the author genuinely asks.
- plan: a stated future action or intention.
- judgment: a subjective assessment or reaction.

## Rules

1. One aspect per assertion; split two facts into two aspects.
2. Make each aspect understandable without the original: resolve pronouns and name the subject.
3. Preserve numbers, names, titles, and event dates; include a date when the text specifies one.
4. Do not invent or generalize. A conclusion is a conclusion only if the author made it.
5. In AI dialogue, extract from user messages. AI messages are context, not aspects, unless the user explicitly accepted a suggestion as their own position.
6. Rhetorical questions are not question aspects. Skip politeness, boilerplate, and repetition.
7. Write each aspect in one or two sentences in the entry’s language. If there is nothing substantive, return an empty list.
8. Service entries beginning with "Clarification of the record…", "Addition to the record…", or "Manual editing of the document…" are the author's answer or edit to another entry or document. Extract from the author's answers and additions or rewrites. Removed text is the previous version, not a new aspect. Links like [[…]] are entry names, not content.

## Response format

Return only JSON, no surrounding explanation or code fence. Put reasoning first, in one or two sentences summarizing the entry's main point.

{"reasoning": "…", "aspects": [{"type": "fact", "text": "…"}, {"type": "plan", "text": "…"}]}

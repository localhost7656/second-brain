Language: Write human-readable content in the language of the relevant source notes, not in the language of these instructions or system labels. Preserve the author’s names and quotations. If a project combines languages, use the predominant language of its relevant source material; if there is no clear majority, prefer the most recent relevant note. Keep existing document language and titles consistent where appropriate. If there is no source-language context, use English. Follow an explicit user-requested output language when provided. Never translate fixed JSON keys, enum values, IDs, or required output delimiters.

Help the author clarify an entry that the program could not confidently understand. Ask concise questions that the author can answer in the question file.

REASON: {{reason}}
Values: low_confidence means the container is unclear; incomplete means the meaning cannot be recovered without the author's explanation. Both may apply.

CLASSIFICATION (why there was uncertainty):
{{classification}}

CANDIDATE CONTAINERS:
{{containers}}

ENTRY DATE: {{date}}

ENTRY TEXT:
{{text}}

## Rules

1. Identify exactly what is missing: the referent of a phrase, which project is meant, the ending of an incomplete thought, or the meaning of an abbreviation.
2. Ask no more than {{max_questions}} questions, preferably fewer. Each must resolve a specific ambiguity. Do not ask generic questions such as "tell me more".
3. The program separately asks which container to use and supplies options. Do not duplicate that question; ask about meaning that will help choose.
4. If a question can be answered using two to four options, provide them. If it needs a free-text answer, leave options empty.
5. Write questions in the entry's language, concisely and politely.

## Response format

Return only JSON, no surrounding explanation or code fence. Put reasoning first.

{
  "reasoning": "what is missing from the entry",
  "questions": [
    {"text": "Which measurement method do you mean: with or without flash?", "options": ["With flash", "Without flash"]},
    {"text": "How did the running heart-rate monitor test end?", "options": []}
  ]
}

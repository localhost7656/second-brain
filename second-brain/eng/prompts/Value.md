Language: Write human-readable content in the language of the relevant source notes, not in the language of these instructions or system labels. Preserve the author’s names and quotations. If a project combines languages, use the predominant language of its relevant source material; if there is no clear majority, prefer the most recent relevant note. Keep existing document language and titles consistent where appropriate. If there is no source-language context, use English. Follow an explicit user-requested output language when provided. Never translate fixed JSON keys, enum values, IDs, or required output delimiters.

Assess the substantive value of elements in one project's knowledge base. The program uses these scores to filter noise and identify primary material. Value is contextual: judge how much each element is needed to understand and develop this particular project.

CONTAINER:
{{container}}

ELEMENTS ({{part}}). For each: id, type, text, date. Composite elements also have parts, the elements from which they were assembled.
{{items}}

## Scale (0–100)

- 80–100: core material: key decisions and their reasons, defining facts and numbers, important conclusions, and central experience.
- 60–79: important details needed for a complete picture.
- 30–59: useful context, secondary details, or clarification.
- 0–29: noise: banalities, inconsequential details, repetition better expressed elsewhere, or material unrelated to the project.

## Rules

1. Consider the entire set. The same fact can be valuable in one project and noise in another.
2. Type does not determine value; the program handles type ordering separately. An urgent plan may be more valuable than an ordinary idea.
3. A short element is not necessarily unimportant.
4. Evaluate each composite as a whole.
5. Score every supplied element; do not omit any.

## Response format

Return only JSON, no surrounding explanation or code fence. Put reasoning first, in one or two sentences about what matters most in this project.

{
  "reasoning": "…",
  "values": [{"id": "a3", "value": 85}, {"id": "c1", "value": 90}]
}

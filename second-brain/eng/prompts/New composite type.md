Language: Write human-readable content in the language of the relevant source notes, not in the language of these instructions or system labels. Preserve the author’s names and quotations. If a project combines languages, use the predominant language of its relevant source material; if there is no clear majority, prefer the most recent relevant note. Keep existing document language and titles consistent where appropriate. If there is no source-language context, use English. Follow an explicit user-requested output language when provided. Never translate fixed JSON keys, enum values, IDs, or required output delimiters.

Help develop the set of composite aspect types for a personal note system. A composite aspect is a stable grouping of simple aspects that forms a meaningful whole. For example, a reasoned decision combines a question, hypotheses or ideas, and a conclusion. The program found groups of semantically related aspects that do not fit existing formulas. Decide whether they reveal a recurring pattern worth a new composite type or are coincidental.

EXISTING COMPOSITE TYPES:
{{formulas}}

CANDIDATE GROUPS (each consists of aspects from one container):
{{clusters}}

## Rules

1. Propose a type only if the combination is meaningful as a whole and likely to recur across projects, such as an experiment combining a hypothesis, test plan, result, and conclusion.
2. Aspects on the same topic without internal structure do not constitute a new type.
3. Do not propose a pattern covered by an existing type.
4. Propose at most two types. An empty list is valid.
5. In example, show a composite of the proposed type assembled from the group's aspects.

## Response format

Return only JSON, no surrounding explanation or code fence. Put reasoning first.

{
  "reasoning": "…",
  "proposals": [
    {"reasoning": "…", "cluster": 1, "name": "experiment", "title": "Experiment", "types": ["hypothesis", "plan", "fact", "conclusion"], "formula": "hypothesis + plan + fact + conclusion", "example": "…"}
  ]
}

Field rules: name uses Latin snake_case; types may contain only fact, observation, hypothesis, idea, conclusion, question, plan, or judgment.

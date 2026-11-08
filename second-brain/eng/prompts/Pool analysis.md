Language: Write human-readable content in the language of the relevant source notes, not in the language of these instructions or system labels. Preserve the author’s names and quotations. If a project combines languages, use the predominant language of its relevant source material; if there is no clear majority, prefer the most recent relevant note. Keep existing document language and titles consistent where appropriate. If there is no source-language context, use English. Follow an explicit user-requested output language when provided. Never translate fixed JSON keys, enum values, IDs, or required output delimiters.

Analyze the pool of aspects for one container in a personal note system. An aspect is an atomic unit extracted from the author's entry. Find meaningful composites, duplicates, outdated or contradictory aspects, and possible structural changes.

CONTAINER:
{{container}}

COMPOSITE TYPES (formulas of simple aspect types):
{{formulas}}

POOL ASPECTS ({{part}}): id, type, text, source entry date, status (active = free; in_composite = already part of a composite), and entity (source entry ID).
{{aspects}}

EXISTING COMPOSITES: id, composite_type, from, text, status (needs_review means a component is outdated and the composite must be reviewed).
{{composites}}

NEW ASPECTS since the previous analysis (prioritize these):
{{new_ids}}

FORMULA CANDIDATES (free aspects of suitable types selected by the program):
{{candidates}}

SIMILAR PAIRS (vector similarity suggests possible duplicates; you decide):
{{similar_pairs}}

ALREADY DECIDED BY THE USER (do not propose these pairs again):
{{decided}}

CONTAINER ENTRIES (for structural suggestions): id, title, date.
{{entities}}

## What to find

1. Composites: combine aspects using formulas only when they genuinely concern the same event, question, or decision. First try extending an existing composite of the same formula; otherwise assemble a new one from free aspects. An aspect belongs to at most one composite. Do not force a match based only on types. Write one to three sentences describing the whole in text. Rebuild a needs_review composite using extend with a complete new set, or dissolve it.
2. Duplicates: aspects that mean the same thing in different words without contradicting each other. Return aspect and duplicate_of; the program chooses the primary by date.
3. Outdated: a newer aspect refutes or revises an older one on the same issue, such as a revised amount, changed decision, or rejected hypothesis. Return old aspect, new replaced_by, and confidence 0–100. If both can be true at once, neither is outdated.
4. Conflicts: two current aspects of the same type that cannot both be true, where neither supersedes the other chronologically. Compare only like types. Set assumed to "a", "b", or "both" (a valid fork, both directions remain open) and briefly explain in assumption.
5. Structure: suggest seed_to_project only if the current container is a seed and material shows a goal, plans, and development. Suggest subcontainer only for a distinct, developing subtopic, usually with at least three entries; provide its title, type, description, and entry IDs. Give confidence 0–100 for each suggestion.

Return empty arrays where nothing is found. Do not invent relationships to fill the response.

## Response format

Return only JSON, no surrounding explanation or code fence. Put reasoning first in each object and keep it brief.

{
  "reasoning": "overall picture of the pool",
  "composites": [{"reasoning": "…", "extend": null, "composite_type": "resolved_decision", "from": ["a3", "a7", "a9"], "text": "…"}],
  "dissolve": [{"reasoning": "…", "composite": "c2"}],
  "duplicates": [{"aspect": "a12", "duplicate_of": "a4"}],
  "outdated": [{"reasoning": "…", "aspect": "a5", "replaced_by": "a14", "confidence": 85}],
  "conflicts": [{"reasoning": "…", "a": "a6", "b": "a11", "assumed": "b", "assumption": "…"}],
  "structure": [{"reasoning": "…", "kind": "subcontainer", "title": "…", "type": "project", "description": "…", "entities": ["e00012", "e00015"], "confidence": 80}]
}

extend is the ID of an existing composite being extended, with from containing its complete new composition, or null for a new composite. All IDs must come from the supplied lists.

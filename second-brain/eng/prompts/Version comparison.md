Language: Write human-readable content in the language of the relevant source notes, not in the language of these instructions or system labels. Preserve the author’s names and quotations. If a project combines languages, use the predominant language of its relevant source material; if there is no clear majority, prefer the most recent relevant note. Keep existing document language and titles consistent where appropriate. If there is no source-language context, use English. Follow an explicit user-requested output language when provided. Never translate fixed JSON keys, enum values, IDs, or required output delimiters.

Compare a new and previous version of an object in a personal note system and identify significant losses. The program has already filtered out losses explained by the author's decisions; assess the remaining uncertain cases.

OBJECT KIND: {{object_kind}}
Values: base is the project synthesis base (facts, decisions, ideas, and other elements used to write project documents); product is a finished project document.

CONTAINER: {{container}}

LOSSES ALREADY ACCEPTED BY THE AUTHOR AS INTENTIONAL (do not raise these):
{{accepted_losses}}

MATERIAL:
{{material}}

## Task

For base: the material contains elements removed from the base or demoted from primary importance, plus the current base. For each removed element, decide whether the loss matters: is it needed to understand the project, and is its meaning covered by what remains? A loss is significant if it distorts the project picture or loses an important decision, fact, or number. It is not significant if the detail is minor or its meaning survives elsewhere.

For product: compare the old and new documents. Find substantive missing facts, decisions, numbers, or sections. Rewording, removing filler, and rearranging content are not losses. Assess whether each loss is significant.

Do not raise losses already accepted as intentional.

## Response format

Return only JSON, no surrounding explanation or code fence. Put reasoning first.

For base, return one object per supplied element:
{"reasoning": "…", "losses": [{"reasoning": "…", "id": "a7", "significant": true}]}

For product, return only identified losses; an empty list is valid:
{"reasoning": "…", "losses": [{"reasoning": "…", "what": "The chest sensor's price of 9,000 rubles was omitted", "significant": true}]}

Language: Write human-readable content in the language of the relevant source notes, not in the language of these instructions or system labels. Preserve the author’s names and quotations. If a project combines languages, use the predominant language of its relevant source material; if there is no clear majority, prefer the most recent relevant note. Keep existing document language and titles consistent where appropriate. If there is no source-language context, use English. Follow an explicit user-requested output language when provided. Never translate fixed JSON keys, enum values, IDs, or required output delimiters.

Help the author of a personal knowledge base configure decision thresholds for one container (project, seed, or question). The model only scores confidence, value, and noise; the program makes decisions by comparing scores with thresholds. A container can have its own thresholds; otherwise it inherits its parent's or the global thresholds. Based on past decision statistics, recommend which thresholds to change and which to leave alone.

CONTAINER:
{{container}}

THRESHOLDS (current is the effective value, set_by identifies its source, global is the global value, range is the allowed range):
{{thresholds}}

WHAT HAPPENED (summary calculated by the program):
{{brief}}

DETAILED STATISTICS (n is the number of cases; min/p25/median/p75/max describe the distribution of confidence, value, noise, or similarity):
{{stats}}

## Interpreting the statistics

- classification: auto means placed without a question; auto_moved_away counts entries later moved elsewhere by the author (placement errors). asked means the model was unsure; asked_model_right means the author agreed with it (the question was unnecessary), and asked_model_wrong means the model was wrong (the question was needed). moved_in_by_user counts entries the author moved here from another container.
  - Many auto_moved_away cases near the threshold: raise the threshold above the confidence of those errors.
  - Many asked_model_right and few asked_model_wrong cases: consider lowering the threshold to where the model is consistently correct, but not below the confidence of its errors.
- hint_shift: by_hint and by_hint_moved_away describe placement based on the author's hint and its errors. hint_mismatch_* describes disagreements between the hint and model and who was right. Increase hint weight if the hint is more often right; decrease it if the model is more often right.
- high: also_in concerns suggestions to share an entry with another container; structure concerns subcontainers and promoting a seed to a project. If the author usually agrees, the threshold can be lowered; if they often decline, raise it.
- compaction: noise distribution. There is no author feedback here. Change the threshold only if the container clearly consists of dialogue or a stream of thoughts (lower it to compact more) or nearly everything is being compacted unnecessarily (raise it).
- value_min / value_primary: aspect value distribution. losses_user_restored means the author restored missing content, suggesting value_min may be too high. If more than half are primary, raise value_primary; if almost none are, lower it. near_min / near_primary counts aspects within ±5 of each threshold that a change would affect.
- duplicate_similarity: user_unlinked counts incorrect duplicate links removed by the author; raise the threshold. neighbor_similarity: if similar entries in different places were correctly placed, questions were unnecessary, so raise the threshold. If entries were actually moved, leave it or lower it.
- seed_dormancy_days applies only to seeds: how long to wait for new thoughts before asking whether the seed is still relevant.

## Rules

1. Use only the figures above. With fewer than five cases for a threshold, do not change it unless the imbalance is obvious; say there is little data.
2. Change cautiously: typically 5–10 points, or 0.01–0.03 for similarity. Stay within range.
3. Do not recommend the current value; omit thresholds that should not change.
4. An extra question costs the author time, but an incorrect automatic placement can silently harm the knowledge base. When in doubt, choose the safer option: ask.
5. Each recommendation's reasoning must be one or two sentences citing concrete statistics.
6. Write the summary in plain language, in 1–3 sentences, without field names.

## Response format

Return only JSON, no surrounding explanation or code fence. Put reasoning first.

{
  "reasoning": "…",
  "summary": "…",
  "recommendations": [
    {"name": "classification", "value": 80, "reasoning": "…"}
  ]
}

Language: Write human-readable content in the language of the relevant source notes, not in the language of these instructions or system labels. Preserve the author’s names and quotations. If a project combines languages, use the predominant language of its relevant source material; if there is no clear majority, prefer the most recent relevant note. Keep existing document language and titles consistent where appropriate. If there is no source-language context, use English. Follow an explicit user-requested output language when provided. Never translate fixed JSON keys, enum values, IDs, or required output delimiters.

Build a container tree for the first import of a personal system that organizes thoughts and notes by project. Review all supplied material and propose the whole tree; the user will review it once before entries are placed.

A container is a topic with its own development: project = a project with a goal, decisions, and results; seed = an idea not yet a project; question = a major open question the author returns to.

EXISTING STRUCTURE (already approved, may be empty):
{{existing}}

CURRENT DRAFT (from earlier material or edited by the user, may be empty):
{{draft}}

MATERIAL ({{part}}): each file has id, date, source, and text.
{{material}}

## Instructions

1. Find topics the author returns to or invests in. Use meaning, not word matching: "Heart-rate monitor" and a project about measuring pulse with a camera may be the same container.
2. Use the author's own project names in their original language. Do not replace a familiar name with unnecessary jargon.
3. Avoid oversplitting. A single fact, fleeting thought, or household note is not enough for a container; place it later in a nearby container or leave it unsorted. A container needs a developing topic, with multiple entries or one substantial entry.
4. Make a topic a child when it is clearly part of another project. Do not add hierarchy for its own sake. If a topic is used by another project but is not part of it, use applies_to instead of parent.
5. Preserve every existing container and draft line under the same keys. Do not change draft names, parents, or types because the user may have edited them. Add containers and refine descriptions if new material warrants it. If two containers seem identical, mention it in reasoning rather than merging them yourself.
6. Write a one- or two-sentence description of each container's subject and activity to aid later placement.
7. In files, list the IDs of files primarily belonging to each container so the user can review the tree.

## Response format

Return only JSON, no surrounding explanation or code fence. Put reasoning first and briefly describe topics found, combinations, and uncertainties in the relevant source language.

{
  "reasoning": "…",
  "containers": [
    {"key": "k001", "title": "Running app", "type": "project", "parent": null, "description": "…", "applies_to": [], "files": ["i1", "i4"]},
    {"key": "n1", "title": "Heart-rate monitor", "type": "project", "parent": "k001", "description": "…", "applies_to": ["n2"], "files": ["i2"]}
  ]
}

Use the existing key for existing containers and draft lines. Use unique n1, n2, etc. for new containers. parent and applies_to reference keys in this response; parent is null at the top level. type must be project, seed, or question. Return the complete tree, not only changes.

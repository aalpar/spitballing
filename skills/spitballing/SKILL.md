---
name: spitballing
description: 'Use when the user wants several creative options for a request (names, titles, concepts, angles, premises) and generic answers won''t do: "less obvious", "something original", "give me options for". Not for refining one idea into a design; that is brainstorming.'
argument-hint: "[the request to generate options for]"
allowed-tools: Read, Write, Edit, Bash
---

# Spitballing: boundary sampling

Creativity here is a methodical search, not a muse. Every request defines an
idea-space with two measured axes:

- **Value**: does an idea fulfill the request?
- **Obviousness**: would ≥25% of a blind naive panel spontaneously produce it?

Reject the **positive set** (obvious fulfillments) and the **negative set**
(off-target); target the **band**: high value, low obviousness, hugging the
negative border. Three stages: MAP, SAMPLE, CONVERGE.

If the user wants to refine ONE approach into a design, that is brainstorming:
say so and offer to switch. Spitballing returns a set; it never picks the winner.

## The brief

Restate the request as a brief; show it and let the user tweak it in one pass,
no interrogation:

```json
{"request": "...", "fulfillment_criterion": "what makes an answer COUNT",
 "output_kind": "the shape of one answer", "hard_constraints": ["filters"]}
```

`fulfillment_criterion` is exactly what the value judge tests.
`hard_constraints` filter in CONVERGE only.

## Stage 1: MAP

**Positive set (blind panel).** Spawn **N=12** Task agents in parallel, each
given ONLY the request, `output_kind`, and this instruction:

> "Give your first 8 instinctive answers to: «request». One per line, no
> explanation."

The panel must be separate contexts. One model playing 12 respondents already
knows what it "said", so its later answers aren't first instincts and the 25%
measurement is corrupt.

**Never substitute your own guess for the panel.** A request for speed or
economy is not a request to skip or shrink it: keep N=12 on the session's model
and cut elsewhere (SAMPLE fan-out, fringe-check, fewer candidates).

| Thought | Reality |
|---|---|
| "The common answers are predictable; I can list them" | That list is the guess the panel replaces. Unmeasured, the 25% cutoff is fiction. |
| "They want it cheap, so they'd want the panel skipped" | Inferred permission. Cut the other stages. |
| "A smaller or cheaper panel is a fair compromise" | Fewer or weaker panelists change what 25% measures. |

If the user explicitly says to skip the panel, the map is a guess and records
itself as one: `"measured": false`, clusters with `label` and `member_ideas`
only, no `obvious` call, and result.md says the obvious set is an estimate.

Pool the answers and cluster them yourself: clustering needs every answer at
once and no independence, so don't delegate it. Record, per cluster, the
distinct panelists who reached it.

**Cluster by mechanism, not wording.** Two answers share a cluster iff they work
for the same reason, not because they share a lexeme. If many clusters clear the
25% cutoff, you're splitting on surface form: merge. If everything collapses
into one cluster, you're too coarse: split. Too fine inflates the obvious set and
over-rejects; too coarse starves the band.

Apply the cutoff:

```bash
echo '{"panelists":[{"clusters":["literal","weather"]}, ...]}' \
  | PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m tools.spitball obvious
```

Each entry lists the distinct cluster labels one panelist produced. The returned
`obvious_clusters` are the positive set.

**Negative fringe (derive, don't guess).** The fringe is the structured
complement of `fulfillment_criterion`:

1. **Decompose** the criterion into its conjuncts: the predicates that must ALL
   hold for an answer to count.
2. **Leave one out.** For each predicate, write the landmark that satisfies every
   conjunct except that one: the closest miss along that axis.
3. **Sense-swap.** For a predicate with a figurative or polysemous reading, add
   the landmark that uses the wrong sense of the right word.

Two conductors decomposing the same criterion should land on the same fringe.
A predicate is a bare label (`COOLING`); its meaning goes in the landmark. Each
landmark records the predicate it relaxes in `drops`, copied character for
character from `predicates`, and how it was derived in `kind`: `leave-one-out`
or `sense-swap`. The landmarks are a compass for SAMPLE, not a filter.

**Write `docs/spitball/<topic-slug>/map.json`**, adding to each kernel cluster
the `member_ideas` you put in it. `measured` is `true` when the panel ran:

```json
{"value_criterion": "communicates cooling the head", "measured": true,
 "predicates": ["COOLING", "HEAD", "literal", "cooling-not-comfort"],
 "obvious_clusters": [{"label": "...", "panelist_count": 9, "frac": 0.75,
                       "member_ideas": ["...", "..."]}],
 "negative_fringe": [{"drops": "HEAD", "kind": "leave-one-out",
                      "landmark": "cold, no cranial reference",
                      "examples": ["Glacier", "Frostbite"]},
                     {"drops": "literal", "kind": "sense-swap",
                      "landmark": "cool as in composed", "examples": ["Level Head"]}]}
```

When the fringe must bite, check it against the panel's own near-misses:
[fringe-check.md](fringe-check.md). Skip for quick runs.

## Stage 2: SAMPLE

Generate ~40 candidates aimed at the band. Give generation the request and
`fulfillment_criterion`, the positive set ("taken: go outside them"), and the
negative fringe ("the productive edge is just inside here: fulfill the request,
but lean toward this border"). No scoring yet. Fanning out Task agents for
breadth is fine; independence isn't load-bearing here.

## Stage 3: CONVERGE

Supply three judgments per candidate, yourself or via a judge agent at scale:

- `nearest_obvious_cluster`: the `obvious_clusters[*].label` in `map.json` the
  candidate falls into, or `null` (entries are objects, not bare strings). Judge
  against the map; re-polling a fresh panel reveals the candidate and biases the
  answer.
- `value_score` (0–1) vs. `fulfillment_criterion`. List every
  `hard_constraints` entry the candidate breaks in `violates`.
- `fringe_proximity` (0–1): closeness to `negative_fringe`.

Write every candidate to `docs/spitball/<topic-slug>/candidates.jsonl`, one
record per line: `{text, value_score, fringe_proximity, nearest_obvious_cluster,
violates, obvious, in_band}`, where `obvious = nearest_obvious_cluster is not
null` and `in_band = value_score >= 0.6 and not obvious and not violates`, so the
log shows what was cut and why. Pipe the same candidates to the kernel to filter and rank:

```bash
echo '{"candidates":[{"text":"Nimbus","value_score":0.8,
  "fringe_proximity":0.7,"nearest_obvious_cluster":null,"violates":[]}, ...]}' \
  | PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m tools.spitball rank --k 5
```

## Output

Write `docs/spitball/<topic-slug>/result.md`: the kernel's `ranked`, each with
one line on why it fulfills and why it isn't obvious, then the map they were
measured against.

Never auto-advance to brainstorming.

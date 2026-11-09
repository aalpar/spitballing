# Spitballing — Boundary-Sampling Redesign

**Date:** 2026-06-12
**Status:** Implemented — conductor skill + tested `tools/spitball` kernel (`obvious` / `rank` / `fringe-check`); dogfooded in `docs/spitball/`. Implementation plan archived to `attic/specs/2026-06-12-spitballing-boundary-sampling.md`.
**Supersedes:** `attic/specs/2026-06-01-spitballing-design.md` (the beam-search
"idea-funnel"). That system diverged *blind* — random seeds, inversion, lens
shift — and used a multi-cycle beam search to stumble onto good ideas and prune.
This design replaces blind divergence with **targeted boundary-sampling**: it
maps where the obvious answers live, then generates deliberately just off them.

## Summary

Creativity here is treated as a methodical search, not a muse. The idea-space of
any request is modeled on two **measured** axes:

- **Value** — does the idea fulfill the request? (a *value judge* vs. the brief)
- **Obviousness** — would ≥25% of a *blind naive panel* spontaneously produce it?

Three regions fall out:

- **Positive set** — high value, high obviousness → reject (too easy).
- **Negative set** — low value → reject (off-target); mapped as a *compass*.
- **The band** — high value, low obviousness, hugging the negative border → the
  **target**. "Near enough to fulfill, but not obvious."

The system **maps** the space, **samples** the band, then **converges** by
re-scoring candidates on both axes and ranking the survivors to a final 3–5.

## The model: the value × obviousness plane

```
            obvious  ◄─────────────── obviousness ──────────────►  novel
          high │
                │   POSITIVE SET            THE BAND
                │   (obvious fulfillments)  (high value, low obviousness,
          value │   reject: too easy        hugging the border) ◄── TARGET
                │
                │ ─────────────── value threshold ───────────────
                │
                │   NEGATIVE SET (low value — does not fulfill)
           low  │   reject: off-target;  near border = generative compass
```

This is the standard novel×appropriate definition of creativity (Stein 1953;
Runco & Jaeger 2012). The contribution is the **operationalization**: obviousness
is *measured* as production frequency across a blind panel, against an explicit
25%-of-respondents cutoff — not guessed by the model about its own output.

## Architecture: hybrid conductor (approach C)

A single **conductor skill** drives the three stages in-conversation. It spawns
genuinely independent agents **only where blindness is load-bearing** — the panel
must be separate contexts, or "first instinct" is contaminated by what the model
already said. Two primitives:

| Primitive       | What it does                                          | Independent agents? |
|-----------------|-------------------------------------------------------|---------------------|
| **Blind panel** | N agents, each sees *only* the request; first instinct| **Yes** (mandatory) |
| **Value judge** | scores fulfillment vs. the criterion — candidates in CONVERGE, panel answers in the fringe cross-check    | No (inline; fan out at scale) |

Why not the alternatives: a single interactive skill (A) would fake the panel in
one context and silently corrupt the 25% measurement — it guts the keystone. A
full workflow (B) is the honest scale-up when panel/generator counts grow large;
the brief may dial into it, but it is overkill for a default run.

## The brief

The request is framed once into a structured brief (infer & confirm — draft it,
let the user tweak in one pass; no interrogation):

```json
{
  "request": "new names for a product that keeps the head cool",
  "fulfillment_criterion": "a product name that communicates head-cooling",
  "output_kind": "a short product name",
  "hard_constraints": ["unregistered trademark", "pronounceable in English"]
}
```

- `fulfillment_criterion` **defines the value axis** — it is exactly what the
  value judge tests against. This is the load-bearing field.
- `hard_constraints` are filters applied in CONVERGE, never during generation
  (constraining generation suppresses the reach).

## Stage 1 — MAP (characterize the space)

**Positive set (blind panel).** Spawn N independent agents (default N≈12). Each
receives *only* the request and `output_kind` — no shared context, no other
panelist's output. Each emits its first ~K instinctive answers. The conductor
then **clusters** the pooled answers (clustering needs all answers at once but
needs no independence, so the conductor does it). For each cluster, count the
number of *distinct panelists* who landed in it.

> **Obvious := a cluster reached by ≥25% of panelists.** The threshold is over
> *panelists*, not over *ideas* — faithful to "obvious to 25% of the population."
> An idea 3 of 12 panelists independently reach is obvious; one only 1 reached is
> not.

**Negative fringe (derive, don't guess).** The near-border failure region is
not hand-articulated; it is *derived* as the structured complement of
`fulfillment_criterion`. Decompose the criterion into the necessary predicates
that all must hold — its conjuncts — and for each, write the boundary landmark
that satisfies every conjunct *except* that one (leave-one-out), plus a
sense-swap landmark for any predicate with a figurative reading. This makes the
fringe reproducible (two conductors decomposing the same criterion land on the
same landmarks) and auditable: each landmark records the predicate it `drops`.
The landmarks are a compass for SAMPLE, not a filter — they characterize the
negative set only near the border, which is all SAMPLE needs.

The derivation is a claim the blind panel can *check*. The value judge scores the
pooled panel answers; those landing just below the value floor are empirical
near-miss productions. Cluster them, tag each with the predicate it relaxes, and
reconcile against the declared predicates (`tools/spitball fringe-check`): a
near-miss cluster along an axis the predicates don't name is a hole in the
decomposition. The check is one-directional — a measured near-miss missing from
the predicates falsifies the decomposition (the panel is a complete sample), but
a predicate with no near-miss proves nothing (instinctive panels skew on-target,
so absence is sampling sparsity).

**Output — `map.json`** (the reused yardstick):

```json
{
  "value_criterion": "a product name that communicates head-cooling",
  "predicates": ["COOLING", "HEAD", "literal", "cooling-not-comfort"],
  "obvious_clusters": [
    {"label": "literal cool+head compound", "member_ideas": ["CoolCap","ChillHat"],
     "panelist_count": 9, "frac": 0.75}
  ],
  "negative_fringe": [
    {"drops": "HEAD", "landmark": "evokes cold but not the head", "examples": ["Glacier"]},
    {"drops": "COOLING", "landmark": "evokes the head but not cooling", "examples": ["Cranium"]}
  ]
}
```

## Stage 2 — SAMPLE (targeted over-generation)

Generators (the conductor, optionally a small diverse fan-out) receive the full
compass:

- the **request** + `fulfillment_criterion`,
- the **positive set** — "these are taken / obvious; generate *outside* them,"
- the **negative fringe** — "the productive edge is just inside here: fulfill the
  request, but lean toward this failure border."

They **over-generate** band candidates (default ≈40). No scoring yet — sampling
is deliberately loose; CONVERGE does the judging.

## Stage 3 — CONVERGE (score, filter, rank)

For each candidate, measure the two axes:

- **Obviousness — membership test against `map.json`.** A candidate is *obvious*
  iff it lands in a ≥25% cluster. **Crucially, this does NOT re-poll a fresh panel
  per candidate** — asking a panel "would you produce *X*?" reveals X and biases
  the answer. The blind map is built once and reused as the yardstick for every
  membership test.
- **Value — the value judge** scores fulfillment vs. `fulfillment_criterion`;
  `hard_constraints` are applied here.

Keep candidates that are **value-high AND not-in-obvious-set** = the in-band set.
Then rank and take the final 3–5.

Each candidate is persisted with its scores (see artifacts) so the run is
auditable.

## The band-ranking function (implemented — `tools/spitball/band.py`)

Ranking the in-band set to pick 3–5 was the one genuine creative judgment left
open; it is now written in `band.py`, resolving the questions this design flagged:

- **Value is a hard floor, not a multiplier.** `in_band(c)` keeps a candidate iff
  `value_score >= 0.6` *and* it sits in no obvious cluster
  (`nearest_obvious_cluster is None`); below-threshold or obvious candidates are
  dropped before ranking, so no fringe-chaser can promote a near-failure.
- **Ranking is a fringe-weighted linear blend** (surprise leads, the decided
  direction): `score = 0.6·fringe_proximity + 0.4·value_score`, sorted
  descending, top-`k`.

Still genuinely open: **`spread`** — the near-duplicate penalty that would keep
the final 3–5 covering the band rather than clustering. It is *not* implemented;
`rank_band` can return near-duplicates. Encoding it (a dedup pass, or a diversity
term in the score) is the remaining creative choice.

## Data artifacts

A run writes to `docs/spitball/<topic-slug>/` in the user's current project:

```
map.json          the blind-built yardstick (obvious clusters + frequencies,
                  value criterion + predicate decomposition, derived negative fringe)
candidates.jsonl  every generated candidate + scores:
                  {text, value_score, fringe_proximity, obvious,
                   nearest_obvious_cluster, in_band}
result.md         final 3–5 + rationale + the map they were measured against
```

`candidates.jsonl` makes the run fully auditable — what was generated, what the
judge said, why each survived or was cut — and is the dataset a resurrected
ablation tool would consume.

## Scorched-earth disposition

Full clean slate. Git history preserves everything; "delete" = remove from the
working tree.

| Path                                      | Fate        | Why |
|-------------------------------------------|-------------|-----|
| `skills/spitballing/SKILL.md`             | **Rewrite** | New conductor for MAP→SAMPLE→CONVERGE |
| `skills/idea-funnel/`, `skills/idea-cluster/` | **Delete** | Beam-search shape gone; convergence is in the one skill |
| `workflows/funnel.js`, `workflows/lib/*`  | **Delete**  | No blind beam search to orchestrate |
| `tools/ablation/*`                        | **Archive** → `attic/ablation/` | Real measurement design; built for the *old* engines — resurrect later |
| `assets/seeds.json`, `tools/gen-seeds.py` | **Delete**  | Random seeds served *blind* divergence; SAMPLE is targeted |
| `docs/specs/*`, `docs/ablation/*`         | **Keep**    | History/rationale; this doc joins them |

> Update 2026-07-17: only this design doc remained in `docs/specs/`; the
> superseded idea-funnel and ablation-era specs were later archived to
> `attic/specs/`.

The seed pool dying is the clearest signal the framing actually changed: random
nouns existed to knock generation off-center *by accident*; boundary-sampling
knows where center is and steers off it *on purpose*.

## Testing

Dogfood on the originating example: **"names for a product that keeps the head
cool."** The three tests that prove the machinery (not merely exercise it):

1. **Panel clustering.** The blind panel actually produces the obvious names
   (CoolCap, ChillHat, …) and they cluster at ≥25% of panelists. If the obvious
   set comes back empty, the panel or clustering is broken.
2. **Control injection.** Slip a deliberately-obvious name into the candidate
   stream; the membership test must flag it `obvious=true`. If a known-obvious
   control survives into the band, the yardstick is not biting.
3. **Fringe recovery.** Slip a near-miss that fails along one *named* predicate
   into the panel's answers; the value judge scores it below the floor and
   `fringe-check` maps its cluster to that predicate (`matched`). Slip one that
   fails along an *unnamed* axis; it must surface in `unmatched`. If a known
   decomposition hole does not surface, the cross-check is not biting.

Plus: SAMPLE candidates demonstrably avoid the mapped positive set.

## Out of scope

- Full-workflow (approach B) orchestration — the brief may dial into it at scale,
  but the default is hybrid C.
- Web-anchored obviousness (the hybrid measurement option) — population
  simulation only, for now.
- Embedding-based clustering — LLM clustering, as before.

## Lessons carried from the old funnel (do not reintroduce)

- **Caps are a hard total, not a per-cluster quota** — applies to the final 3–5.
- **An agent's structured return may disagree with what it wrote to disk** — the
  persisted artifact (`map.json`, `candidates.jsonl`) is the source of truth;
  verify by reading the file.
- **`args` may arrive as a JSON string** — parse defensively if a workflow is used.

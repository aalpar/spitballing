# BACKGROUND Step — Domain-Model Design

**Date:** 2026-06-02
**Status:** Approved (design); pending implementation plan
**Extends:** `2026-06-01-spitballing-design.md` (the idea-funnel v2). Adds a
research-and-domain-modeling stage *before* DIVERGE.

## Summary

BACKGROUND is a new, one-shot stage that runs before the first diverge cycle. It
turns the user's goal into a **variance-annotated conceptual dependency graph** of
the domain — a Bayesian network over *subject matter, not time*. Near the root sit
the domain's **invariants** (low variance, high importance: *Daria exists, it's a
story, a story has a protagonist*); toward the leaves sit the **degrees of freedom**
(high variance: *subject matter, props, the protagonist's personality this episode*).
DIVERGE then explores the space by sampling **root→leaf chains**, freezing the
low-variance ancestors as a coherent frame and perturbing the high-variance leaf
(seeded by a random WordNet noun).

This replaces domain-blind divergence (random nouns against a bare topic string)
with **structured exploration of the actual idea space**, while keeping the random
seed as the perturbation engine that resists premature convergence.

## Why a graph, not a list

The first framing was "a flat list of degrees of freedom." That loses the essential
structure: variation is **conditioned**, not independent. You cannot perturb
"protagonist's personality" without first instantiating "protagonist"; perturbing
"plot" re-conditions which subplots stay coherent. The dependency edges are what keep
a wild idea from becoming an *incoherent* idea.

So "invariant vs. degree of freedom" is not a binary — it is the **low-variance and
high-variance ends of one dependency graph**, and a per-node **variance** measure makes
that continuum legible and mechanically usable.

## The domain model (new durable artifact)

`domain-model.json`, written once before cycle 1, sibling of the corpus. The file is
the durable, inspectable source of truth (written by the BACKGROUND agent, read by the
conductor). Its working copy travels into each cycle through `args.domainChains` —
the same file-is-memory / args-is-handoff split the corpus and beam already use,
because the workflow script has no filesystem access.

```json
{
  "topic": "a completely new Daria 1.5-hr special",
  "domain": "animated character-driven TV special",
  "nodes": [
    {"id": "n0", "concept": "Daria special",        "parents": [],          "variance": 0.00, "importance": 1.00, "note": "root — the artifact itself"},
    {"id": "n1", "concept": "is a story",            "parents": ["n0"],      "variance": 0.05, "importance": 0.95},
    {"id": "n2", "concept": "protagonist = Daria",   "parents": ["n1"],      "variance": 0.10, "importance": 0.90, "note": "invariant — removing breaks the domain"},
    {"id": "n3", "concept": "Daria's projected personality", "parents": ["n2"], "variance": 0.40, "importance": 0.55},
    {"id": "n4", "concept": "subject matter / theme","parents": ["n1"],      "variance": 0.85, "importance": 0.50},
    {"id": "n5", "concept": "props & setting",       "parents": ["n4"],      "variance": 0.90, "importance": 0.25}
  ],
  "chains": [
    {"id": "ch1", "path": ["n0","n1","n2","n3"]},
    {"id": "ch2", "path": ["n0","n1","n4","n5"]}
  ],
  "needsDisambiguation": []
}
```

- **`nodes`** — concepts and their dependency parents. A small random **DAG** (a node
  may have multiple parents, e.g. *tone* depends on both *protagonist* and *setting*),
  kept small: depth ~3–5, ~10–25 nodes total.
- **`variance`** (0–1) — the *operative* scalar: how freely a node's meaning can shift
  while staying in-domain. It drives the freeze/perturb split in DIVERGE.
- **`importance`** (0–1) — centrality to the topic. **Recorded for the human, not used
  mechanically.** Variance is the one lever.
- **`chains`** — enumerated root→leaf paths, **shuffled by the agent** (the workflow
  script cannot call `Math.random()`; stochastic structure must originate in the LLM
  agent). The conductor assigns `chain[i % n]` to diverge agent *i*, exactly as it
  assigns seeds today.
- **`needsDisambiguation`** — empty in the autonomous case; see below.

The conductor passes a *resolved* form into each cycle so the workflow need not carry
the whole node table:

```json
"domainChains": [
  {"id": "ch2", "nodes": [
     {"concept": "Daria special",         "variance": 0.00},
     {"concept": "is a story",            "variance": 0.05},
     {"concept": "subject matter / theme","variance": 0.85},
     {"concept": "props & setting",       "variance": 0.90}
  ]}
]
```

## The BACKGROUND mode

A new `mode: 'background'` in `funnel.js`, alongside `select` and `rereduce`. One agent,
run by the conductor before cycle 1. Its job:

1. **Identify the domain** from the goal. The agent **may use web research**
   (WebSearch / WebFetch via ToolSearch) to ground itself — what *Daria* is, what a
   TV special's runtime and format conventions are. This is the one stage where real
   external research legitimately enters the funnel; it is also where the funnel's
   "reinvents known work by default" weakness is addressed at the root rather than only
   at terminal SELECT.
2. **Grow a small random dependency graph** rooted at the topic, edges meaning
   *requires / has* (Bayesian conditioning over subject matter).
3. **Annotate** each node with `variance` (operative) and `importance` (informational).
4. **Enumerate and shuffle** root→leaf chains.
5. **Flag genuine ambiguity** in `needsDisambiguation` — *only* true blockers (e.g.
   "is this the MTV show *Daria*, or something else?"), never mere preferences. Default
   path is fully autonomous.
6. **Write `domain-model.json`** to the given path (create parent dirs).
7. **Return** the graph + chains + `needsDisambiguation`.

### Schema (`BACKGROUND_SCHEMA`, replacing the current DIVERGE-clone stub)

```
{
  domain: string,
  nodes:  [{ id, concept, parents:[id], variance:number, importance:number, note? }],
  chains: [{ id, path:[id] }],
  needsDisambiguation: [{ question, why, options?:[string] }],
  artifactWritten: boolean
}
```

## Disambiguation (conductor checkpoint)

Workflow agents cannot prompt the user mid-run. So BACKGROUND surfaces ambiguity as
*data* (`needsDisambiguation`), and the **conductor** resolves it at a checkpoint:

- If `needsDisambiguation` is non-empty, the conductor runs `AskUserQuestion` with those
  questions, then re-runs `background` with `args.disambiguation = {answers}` folded into
  the prompt.
- Loop until empty, capped at **2 rounds** to bound cost; after the cap, proceed with the
  agent's best reading and note the residual ambiguity at the brief checkpoint.

## DIVERGE changes

Each diverge agent now receives `(target, chain, seed)`:

- `target` — the topic (cycle 1) or a surviving beam idea (later cycles), unchanged.
- `chain` — `domainChains[i % n]`, the dependency path with per-node variance.
- `seed` — the existing WordNet descriptor (noun / cousin / collision), unchanged
  and orthogonal to the chain.

The diverge prompt gains a **CHAIN block**:

> Dependency chain (conditioned over subject matter): `A → B → C → D`.
> **Hold fixed** (the frame — these define the domain; breaking them leaves the domain):
> the low-variance nodes `[A, B]`.
> **Perturb hard**: the high-variance leaf `D` (and you may also vary the mid-variance
> node `C`). Route the perturbation through the seed noun **X**.

The freeze/perturb split is computed from per-node `variance` against a threshold
(default **τ = 0.5**): variance `< τ` → frozen frame; variance `≥ τ` → perturbation zone;
the leaf is always in the perturbation zone (the agent pushes it hardest).

**Corpus impact is minimal.** The existing `seed` field absorbs the chain context as a
compound label (e.g. `"props&setting × noun:lighthouse"`); `parent` is unchanged. No new
corpus columns, no migration.

## REDUCE / SELECT changes

The low-variance root nodes are **definitional invariants**, distinct from the brief's
goal-constraints:

| | source | applied where |
|---|---|---|
| **Domain invariant** | BACKGROUND (low-variance nodes) | the *arena* — frame during DIVERGE; archive out-of-domain ideas in REDUCE/SELECT |
| **Brief constraint** | conductor goal-framing | the *scoring gate* — REDUCE/SELECT only (e.g. "must be unpatented") |

This refines the v2 rule "no constraints during divergence." Definitional invariants are
not a filter that suppresses wildness — they are the arena boundary that keeps ideas
*coherent*. They legitimately appear *during* DIVERGE (as the frozen frame), whereas a
goal-constraint still gates only REDUCE/SELECT.

REDUCE and SELECT prompts receive the invariant list (the low-variance nodes) and archive
or reject ideas that break the frame as **out-of-domain** — a category separate from
"loses on the merits."

## Relationship to the brief

The domain model and the brief are **complementary, not redundant**:

- **Domain model** = *space structure* — what can vary (freedoms) and what cannot
  (invariants).
- **Brief** = *goal scoring* — `success` (ranking lens), `framing` (soft bias),
  goal-`constraints`.

The conductor frames the brief **after** BACKGROUND, using the domain model to inform it:
high-variance axes suggest `framing`; definitional invariants suggest candidate
`constraints`; the identified domain sharpens `space`. The two artifacts stay separate
and are both shown at the first checkpoint for a one-pass tweak. They are not merged.

## Graph lifetime

- Cycle 1 builds the graph; **later cycles reuse it** by default (it is the domain's
  structure, which is stable).
- **Re-growing is opt-in**: a later checkpoint may re-run `background` to grow *new*
  branches (fresh chains → more anti-convergence) when the beam feels exhausted. Not
  automatic.

## Conductor (idea-funnel skill) changes

Add a Step between current Step 1 (capture goal) and Step 2 (frame brief):

> **Step 1.5 — Build the domain model.** Launch `funnel.js mode:'background'`. Resolve any
> `needsDisambiguation` via one `AskUserQuestion` round (≤2). Read `domain-model.json` to
> verify (do not trust the return alone — same discipline as the corpus). Carry the
> chains forward as `domainChains` in every subsequent cycle's `args`.

Step 2 (frame brief) is updated to draw on the domain model. Step 3 (run cycles) passes
`domainChains`. The "what you never do" list gains: *never apply the domain invariants as a
generation filter beyond the frozen frame* (they bound the arena, they do not prune within
it).

## Testing

- **BACKGROUND dry run** on two topics — a narrative one ("a new Daria special") and a
  technical one ("novel ways to sort a list"). Check: the graph is sensible; variance
  ranking matches intuition (invariants low, props/theme high); chains enumerate;
  `domain-model.json` is written and re-readable; `needsDisambiguation` is empty for a
  clear topic.
- **Disambiguation loop** — feed a deliberately ambiguous topic; confirm BACKGROUND
  surfaces a precise question, the conductor asks it, and the re-run resolves cleanly
  within the 2-round cap.
- **DIVERGE with a chain** — confirm ideas hold the frozen frame (stay in-domain) yet
  perturb the leaf wildly; confirm the compound `seed` label lands in the corpus.
- **Variance threshold** — sanity-check τ = 0.5 produces a non-empty frame *and* a
  non-empty perturbation zone on real chains; adjust default if chains collapse to all
  frozen or all free.

## Out of scope

- Embedding- or WordNet-based graph construction (LLM-built, as with clustering).
- Using `importance` mechanically (informational only in v1).
- Automatic graph re-growth (opt-in only).
- Merging the domain model into the brief (kept as two artifacts).
```
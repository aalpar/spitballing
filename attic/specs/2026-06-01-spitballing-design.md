# Idea-Funnel Plugin — Design (v2)

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Supersedes:** v1 ("pure divergence, no convergence"). Convergence is now the
core of the system; the spitballing skill is one component.

## Summary

A Claude Code plugin that runs a **beam search over an idea space**: it
alternates *divergence* (generate many wild ideas) with *partial convergence*
(cluster and keep the strongest live branches), narrowing across several cycles
until it converges on a final **3–5 topics**. Because the idea corpus exceeds
any single context window, ideas live in a durable structured file on disk and
each cycle runs as one or more agent runs.

## The model: beam search over ideas

- **DIVERGE** — expand the frontier (the `spitballing` skill).
- **REDUCE** (partial converge) — cluster new ideas semantically, keep the
  strongest 1–2 per cluster as the new *beam*. Nothing is scored or deleted on
  the merits early; pruning is consolidation, not judgment.
- Repeat for N cycles, the beam narrowing each cycle.
- **SELECT** (terminal) — when the beam reaches the target width, a final pass
  articulates the 3–5 winners with rationale (≈ what brainstorming does).

The quality of the whole system lives in REDUCE resisting **premature
convergence** — hence keep a *width*, never a single best, and never delete.

## The brief (goal framing)

A goal is not a topic string — it carries hidden constraints and a success
criterion. Before cycle 1, the conductor turns the one-line goal into a
structured **brief** (infer & confirm — show a draft, let the user tweak in one
pass; no interrogation):

```json
{"goal": "...", "space": "...", "framing": ["soft bias for diverge"],
 "constraints": ["hard filter for reduce/select"], "success": "ranking lens",
 "outputKind": "format of one idea"}
```

- **`framing` biases DIVERGE** (generate era-flavored ideas).
- **`constraints` + `success` gate REDUCE/SELECT** (drop anachronisms / patented
  approaches; keep the most on-goal).
- Hard constraints are NOT applied during divergence — that would suppress the
  wildness; they filter afterward.

**This reverses v1's "no ranking/evaluation."** A goal forces evaluation back in:
REDUCE/SELECT cannot pick a beam without knowing what "good" means for the goal.
The brief supplies that lens. When a constraint is a novelty bar ("unpatented"),
SELECT should run an explicit prior-art check.

## Cadence: per-cycle checkpoints

One cycle = one workflow run, then a human checkpoint:

1. **DIVERGE** — fan out *K* agents, each running the spitballing instructions on
   the current seeds; all ideas append to the corpus.
2. **REDUCE** — a barrier (clustering needs every new idea at once): a
   cluster-agent groups ideas and selects the beam.
3. **CHECKPOINT** — the workflow ends and presents the surviving beam. The user
   steers: approve · inject a seed · widen/narrow · re-diverge one branch.
4. The next cycle launches on the approved beam.

This reconciles the original interactive-nudge instinct with the scale:
token spend is bounded and visible per cycle, and a human watches the beam
narrow so premature convergence is caught as it happens.

## The corpus (shared memory)

Append-only JSONL, one record per idea. Because no agent shares another's
context, **this file is the only memory that persists across runs.**

```json
{"id": "c1-007", "cycle": 1, "parent": null, "seed": "polariscope",
 "cluster": null, "text": "<one-liner>", "status": "live"}
```

- `status`: `live` | `archived`. Pruning flips `status`, never deletes — so a
  later checkpoint can **resurrect** an archived idea if the beam converged too
  soon. The safety valve against premature convergence, paid for in disk.
- `parent`: the beam idea this one diverged from (null in cycle 1).
- `seed`: the WordNet noun that seeded this idea (when applicable).
- `cluster`: assigned by REDUCE.

## WordNet seed pool (build-time)

Workflow scripts have no filesystem or network access, so WordNet is a
**build-time** seed generator, not a runtime dependency:

- `tools/gen-seeds.py` samples from WordNet (descendants of `artifact`,
  `natural_object`, `animal`, `plant`, `food`), deterministically (RNG seed 42).
- Output: `assets/seeds.json`, committed to the plugin — no NLTK on the user's
  machine. Three seed modes:
  - `nouns` — a single concrete object.
  - `cousins` — two coordinate terms (siblings sharing a parent); the agent
    exploits the family resemblance *and* the gap.
  - `collisions` — two nouns with near-zero path-similarity; the agent bridges
    them. (Merges the old 🎲 seed and ✦ mashup engines.)
- **Familiarity filter (soft SemCor anchor):** single nouns must have SemCor
  `count >= 1`; each pair needs at least one familiar anchor. This drops dead
  obscure-obscure seeds (the model can't associate on `hegari`/`ortygan`) while
  keeping the generative known-anchor + weird-partner shape. SemCor is noisy
  (zeroes some common words like `reactor`), accepted as the no-new-dependency
  cost.
- The funnel hands each diverge agent a seed descriptor via `args`; the diverge
  prompt switches engine instruction by mode.

Polarity (material × immaterial) was considered and dropped — WordNet's
`abstraction` subtree is too polluted with proper nouns to yield clean abstract
seeds without heavier curation.

Clustering stays LLM-based — WordNet similarity is word-level and poor on
sentence-length, technical ideas.

## Funnel defaults (all overridable via workflow args)

| Cycle | Diverge | Raw ideas | → Beam |
|-------|---------|-----------|--------|
| 1 | 5 agents × ~15 | ~75 | ~8 branches |
| 2 | diverge each branch deeper | ~60 | ~5 branches |
| 3 | → terminal SELECT | — | **3–5 topics** |

## Components

0. **`idea-funnel` skill** — the conductor. Captures the goal, frames the brief
   (infer & confirm), runs cycles via the workflow with checkpoints, runs the
   terminal select. The user-facing entry point.
1. **`spitballing` skill** — DIVERGE. Built (v1). Reused unchanged as the diverge
   agent; updated only to optionally read a seed from the pool.
2. **`idea-cluster` skill** — REDUCE. New. Cluster-and-keep-live-branches; ships
   as its own skill so it's inspectable and reusable.
3. **Funnel workflow script** — the per-cycle controller (parallel diverge →
   barrier reduce → write beam → return for checkpoint). Parameterized via
   `args`: cycle #, beam width, agent count, corpus path.
4. **Seed pool** — `assets/seeds.json` (nouns/cousins/collisions). Built.
5. **Seed generator** — `tools/gen-seeds.py`, for reproducibility.

## Packaging caveat

Skills/agents distribute cleanly in a plugin. **Resolved:** workflow scripts do
*not* — no plugin asset type registers a workflow, and `/plugin install` won't
expose `funnel.js` as a named `/workflow` (confirmed: no plugin in the local
cache ships a `workflows/` dir). The script travels *inside* the plugin repo but
is invoked by path — `Workflow({scriptPath: "<pluginRoot>/workflows/funnel.js"})`
— or copied into `.claude/workflows/` to become a named workflow.

## Opt-in

Building the machinery requires no special permission. **Running** the funnel
workflow spawns many agents and consumes significant tokens; it will only be run
on the user's explicit go-ahead, never automatically.

## Testing

- `spitballing` / `idea-cluster`: manual invocation on a sample topic — check
  divergence variety, that REDUCE consolidates without deleting, and that the
  corpus reads/writes correctly.
- Funnel: a dry single-cycle run on a small topic before any multi-cycle run.
- Seed pool: verify regeneration is deterministic (same RNG seed → same file).

## Lessons (from real runs)

Surfaced by the dry run and the Daria run; do not reintroduce.

- **REDUCE cap must be a hard total, not a per-cluster quota.** The original
  phrasing "keep 1–2 per cluster, up to the target width" is self-contradictory
  when `clusters > width`: the agent resolved it toward per-cluster coverage and
  kept ~20 live against a cap of 8. Fix: width is a hard total cap; when clusters
  exceed it, the agent MUST merge or drop to fit. (Ironically the bug masked the
  dry-run's *premature-convergence* problem by keeping everything — two failure
  modes of the same ambiguous instruction.)
- **An agent's structured return may disagree with what it wrote to disk.** The
  REDUCE agent reported a beam of 8 while the corpus held 20 live. The corpus is
  the source of truth — always verify a checkpoint by reading the file, never
  trust the workflow's returned summary alone. Fix: REDUCE must return exactly
  the ideas it marked `live`; a `rereduce` mode repairs a bad cycle without
  re-diverging.
- **`args` can arrive as a JSON string, not an object.** The funnel must parse
  `args` defensively (`typeof === 'string' → JSON.parse`).
- **Hard-cap drops are suggestions, not verdicts.** A cap-forced drop killed an
  11-idea vein ("Reigning Hens") that, once resurrected by hand, the select pass
  independently ranked into the final 5. The append-only corpus makes resurrection
  a one-line `status` flip — keep it that way.

## Out of scope

- WordNet-based clustering (LLM-based instead).
- Fully autonomous multi-cycle runs (checkpoints are mandatory).
- Embedding-based clustering (possible future engine, not v2).

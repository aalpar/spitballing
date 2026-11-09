# Phase-1 (brick / AUT) — Instrument-Validation Findings

**Date:** 2026-06-02
**Status:** Synthetic validation only — **no paid/human ratings collected.** All ratings
below are from blind LLM-rater panels standing in for the crowd, used to validate the
instrument and exercise `attic/ablation/score.py` before any spend.
**Topic:** "novel uses for a brick" (Alternative Uses Task — the Daria-free Phase-1
methodology topic; see `preregistration.md`).

## What was run

1. **Dry-run** of the engine matrix on a scratch corpus — confirmed all 8 cells fire and
   tag `engine`/`source` correctly.
2. **Background** run on the brick → 20 affordance chains (mass, thermal, abrasion,
   porosity, geometry, hardness, kinetic, aesthetic).
3. **Full generate** — the retired funnel workflow, cycle mode, `includeStraight:true`, 8 cells × 25 ideas,
   background cells fed distinct chains, seed cells fed sampled WordNet seeds → 200 ideas,
   all 8 cells exactly 25, 0 malformed.
4. **prep-ablation** — engine-fidelity judge + voice-normalization → 193 kept, 7 dropped
   (all 7 seed-source; off-engine). Trimmed to the pre-registered **N=20/cell = 160**.
5. **Blinding spot-check** + **3-rater blind panels** on originality, appropriateness (old),
   and value (reframed).

## Finding 1 — the engine label leaks through idea *content*, not voice

Pre-registered blinding gate (`preregistration.md` §6.1): pass if engine-classification
accuracy ≤ chance + 10pp (≤ 35%; chance = 25%).

- **Informed classifier: 65% accuracy → FAIL.**
- **Naive partitioner** (told nothing about engines, asked to group by "generation
  method"): spontaneously produced *bird-rescue / doomsday-cult / tabloid / literal-utility*
  groups — **ARI 0.31** vs the true engines.

Per-engine detectability (informed): lens-shift **100%**, straight **100%**, random-seed
**50%**, inversion **10%**.

**Why.** For two engines the device *is* the idea's content: lens-shift = a persona/scenario
framing; random-seed = a fused foreign object. Voice-normalization cannot remove that
without destroying the idea. Inversion, by contrast, blinds almost perfectly — its
worst→flip scaffolding is genuinely discardable, leaving just a good idea.

## Finding 2 — on a concrete-object topic, "appropriateness" measures shape, not quality

3-rater blind panel (0–100), per engine pooled over source:

| engine | originality | appropriateness (old) | value (reframed) |
|--------|------------:|----------------------:|-----------------:|
| straight     | 47.1 | 71.3 | 70.2 |
| inversion    | 56.8 | 68.3 | 69.4 |
| random-seed  | 67.6 | 50.9 | 65.2 |
| lens-shift   | 59.4 | 29.1 | 49.4 |

- **H1 directionally holds** (synthetic): every engine beats straight on originality
  (random-seed +20). The engines do something.
- **Old appropriateness was confounded by output shape:** engine-mean spread **42.2 pts**;
  lens-shift cratered at **29** because a "cult-vigil brick" *isn't a literal use* — it's a
  scenario. That penalizes the scenario engines for their shape, not their quality.
- corr(originality, appropriateness) = **−0.59** (entangled).

## Finding 3 — reframing the second dimension to "value" halves the confound

`value` = "does the idea hinge on a genuine property of a brick — scenario or not?"
(shape-neutral, but still penalizes object-incidental gag ideas).

- Engine-mean spread **42 → 21 pts**; lens-shift **29 → 49** (uncratered).
- corr(originality, value) = **+0.11** — dimensions stay independent (no collapse).
- Reliability α: originality **0.95**, value **0.75** (both pass the 0.667 gate; value is a
  harder judgment — watch it with real raters).
- The residual 21-pt spread is partly **genuine signal** (lens-shift really does produce
  more object-incidental ideas) and is intentionally retained.

→ Adopted as pre-registration **Amendment A1**. Detectability (ARI 0.31) is unchanged by
the reframe; it matters only via rating bias, which the reframe halves.

## Pipeline validation (bonus)

`score.py` `reliability_gate` / `aggregate` / `cell_means` and `reliability.py`
`krippendorff_alpha` all ran clean on the realistic 3-rater ratings (α, gating, per-cell
means + bootstrap CIs). The MTurk-dependent stages (`post_hits`, `collect`) were not
exercised — they need the user's AWS requester account.

## Caveats

- LLM raters agree far more than humans will; real Krippendorff α will be lower, especially
  for `value` (0.75 here). The reliability gate exists precisely to catch that.
- This validates the *instrument*, not the *result*. The per-engine means are a preview from
  synthetic raters, not data.

## Artifacts (`tmp/ablation-phase1/`, gitignored)

`corpus.jsonl` (200) · `rated-set.jsonl` (160, N=20/cell) · `rated-set.full-193.jsonl` ·
`fidelity-report.json` · `domain-model.json` · `blind-{payload,truth,guesses}.json` ·
`naive-partition.json` · `ratings-rater-{1,2,3}.jsonl` · `value-rater-{1,2,3}.jsonl`

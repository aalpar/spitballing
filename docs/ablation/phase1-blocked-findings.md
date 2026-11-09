# Phase-1 (brick / AUT) — Blocked Matched-Input Validation Findings

**Date:** 2026-06-03
**Status:** Pipeline validation only — **no paid/human ratings collected.** This run
validates the *blocked/matched-input* generation pipeline (pre-registration Amendment
A2), not a result. The corpus is **not** posting-ready — the §6.1 blinding gate still
fails and matched inputs do not address content-leak.
**Topic:** "novel uses for a brick" (Alternative Uses Task).
**Design:** Amendment A2 — each input (20 background chains + 20 seed walks) is a *block*
run through all four arms {random-seed, inversion, lens-shift, straight}, one idea per
(block × arm), keyed by an immutable `block_id` (`"<source>:<index>"`). See
`preregistration.md` §0 A2 and `attic/specs/2026-06-03-matched-input-blocked-ablation.md`.

## What was run

1. **Blocked generation** — `funnel.js` cycle mode, `includeStraight:true` **and
   `blocked:true`** (the blocked design is opt-in; without the flag the funnel runs its
   general multi-idea cycle), 20 chains +
   20 seeds × 4 arms → **160 ideas**, one per (block × arm). All 8 cells exactly 25→20-as-
   designed (20/cell), 40 blocks each covering all 4 arms, 0 malformed.
2. **prep-ablation** — fidelity judge + voice-normalization → **149 kept, 11 dropped**
   (all off-engine; see Finding 2). `block_id` carried verbatim through normalization.
3. **build HITs** — blind, randomized, 2 attention checks/HIT; `block_id` lands in the
   hidden `keys.json` map and never leaks into a rater-visible identifier (verified).

## Finding 1 — the matched structure is achieved, and `block_id` survives every stage

The blocked design produced exactly the intended structure: **160 ideas, 40 blocks, each
block covering all 4 arms, 8 cells × 20.** Every idea carries `block_id`.

A pipeline defect was caught and fixed *before* the run: the REDUCE corpus-write, the
prep-ablation rated-set write, and `FIDELITY_SCHEMA` all originally omitted `block_id`
(their field-lists were `{id,engine,source,text}`), so the tag would have been silently
dropped at the first LLM-writer stage — leaving the paired analysis with nothing to pair
on. Threading `block_id` through all three (commit on branch) is what let it survive into
`keys.json`.

## Finding 2 — fidelity drops are cell-correlated (§5 reportable)

prep-ablation dropped 11 of 160 as off-engine. The discard is **non-random across cells**:

| engine | dropped | typical reason (from the fidelity judge) |
|--------|--------:|------------------------------------------|
| straight     | 0 | — |
| random-seed  | 2 | seed noun used as adjective/metaphor, not routed through as a concrete object |
| inversion    | 3 | decorative "worst:" clause on a stock idea identical to the straight cell; or a duplicate flip |
| lens-shift   | 6 | persona-scenario reads as a gag/marketing conceit or a near-duplicate devotional motif, not a sustained discipline lens |

Per `preregistration.md` §5 (discard-balance check), a cell-correlated discard pattern
**must be reported** — survivors are biased by it. The pattern is consistent with the
engines' output shape (lens-shift's scenario framing is the hardest to judge as a genuine
device) and is plausibly amplified by this design's **one-idea-per-block** generation:
asking each arm for its single strongest idea pushes some arms toward gags or restatements
rather than a clean device application.

## Finding 3 — a fidelity drop breaks a matched quad; refill must be block-targeted

In the prior (disjoint-input) design a drop merely thinned a cell. In the blocked design,
dropping one (block × arm) idea breaks that block's quad. The 11 drops hit 11 *distinct*
blocks, leaving **29 of 40 blocks complete** and per-cell counts of 15–20.

`score.paired_contrasts` degrades gracefully — a block missing an arm simply does not
contribute to pairs involving that arm — so the analysis still runs, with reduced power.
But to restore N=20/cell for the real run, refill must regenerate the **specific dropped
(block × arm)** until it passes fidelity, not "any idea in the cell" (which would leave the
quad incomplete). This block-targeted refill loop is **not yet built**; it is required
before the post-blinding paid run. For this validation run, refill was **deferred** (the
corpus is unpostable regardless).

## Caveats

- Validates the *instrument/pipeline*, not a *result*. No human ratings.
- **Blinding (§6.1) remains failed and unaddressed** — the gate to any paid posting.
- N=20/cell is not met (realized 149); the refill loop is deferred work, not a result.

## Artifacts (`tmp/ablation-phase1/`, gitignored)

`corpus-blocked.jsonl` (160, with `block_id`) · `rated-set-blocked.jsonl` (149) ·
`fidelity-report-blocked.json` (11 dropped + reasons) · `hits-blocked/` (13 HITs +
`keys.json` with hidden `block_id` + `attention-key.json`) · `run-cfg.json` (20 resolved
chains + 20 seeds).

# Engine Ablation Harness — Pre-Registration

**Status:** BINDING — must be committed BEFORE any generation or data collection.
**Study:** Engine Ablation Harness (Part B of the Diverge Engine Matrix design).
**Date committed:** 2026-06-02

This document fixes the hypotheses, arms, dimensions, thresholds, exclusion rules, and
analysis plan in advance. No post-hoc rationalisation of results is permitted. The analysis
may not be adjusted after data collection begins.

---

## 0. Amendments (pre-data; legitimate)

Amendments are only legitimate **before real data collection begins**. The records below
were made during instrument validation on synthetic LLM-rater previews — *no paid/human
ratings had been collected* — so they amend the binding spec rather than rationalising a
result.

### A1 — Phase-1 second dimension: "Appropriateness" → "Value" (2026-06-02)

**Change.** Phase-1's second rating dimension was changed from *Appropriateness*
("the idea makes sense as a literal response to the prompt") to *Value* ("does the idea
hinge on a genuine property of the object, scenario or not").

**Why.** A pre-registered blinding spot-check (§6.1) on the Phase-1 brick corpus FAILED:
an informed classifier recovered the engine at **65%** (chance 25%, ceiling 35%), and a
*naive* partitioner (told nothing about engines) recovered it at **ARI 0.31**. Diagnosis:
two engines encode their device in idea *content*, not voice — lens-shift produces
persona/scenario ideas, random-seed fuses a foreign object — so voice-normalization cannot
blind them. On a concrete-object topic, "Appropriateness = is this a literal use" then
*structurally* penalized the scenario engines (engine-mean spread **42 pts**; lens-shift
appropriateness **29** vs straight **71**), measuring output *shape*, not engine *quality*.

**Evidence the reframe helps (3-rater synthetic preview, blind).** Switching to *Value*
roughly halved the engine-shape confound (spread **42 → 21 pts**), uncratered lens-shift
(**29 → 49**), kept the dimensions independent (corr(originality, value) **+0.11** vs the
old **−0.59**), and held reliability above the gate (α **0.75**). The residual 21-pt spread
is partly genuine signal (lens-shift really does produce more object-incidental ideas) and
is intentionally retained. Detectability itself (ARI 0.31) is unchanged by the reframe; it
matters only via rating bias, which the reframe halves. Full record:
`docs/ablation/phase1-brick-findings.md`.

**Scope.** Affects Phase-1 dimensions only. Phase-2 (Daria) dimensions — originality,
surprise, fidelity — are unchanged. All thresholds in §4 are unchanged.

### A2 — Blocked/matched-input design + paired contrasts (2026-06-03)

**Change.** Phase-1 generation is changed from disjoint-input cells (each engine
fed a different chain/seed) to a **blocked design**: each *input* (a background
chain or a seed walk) is a block run through all four arms
{random-seed, inversion, lens-shift, straight}, producing one idea per
(block × arm). Inputs are shared across arms within a source. Each idea carries an
immutable `block_id` (`"<source>:<index>"`). §6.4 contrasts become **paired**
(within-block) instead of unpaired.

**Why.** In the prior design, input was confounded with engine at the cell level —
a device contrast also measured the input it happened to receive. Blocking on input
removes that confound and lets the device effect be read within-block. Source
(background vs seed) remains a between-block factor, so H2 is unchanged.

**Scope.** Affects Phase-1 generation and the §6.4 analysis only. Cells (8), N=20/cell,
all §4 thresholds, and Phase-2 are unchanged. Blocking does **not** address the §6.1
blinding failure, which remains an open prerequisite to posting.

---

## 1. Hypotheses

Each hypothesis states a **directional prediction** but is **tested two-sided**: the
statistical test can detect — and the report must surface — an effect in *either*
direction, including the reverse of the prediction. The research-grounding section of the
design spec motivates these predictions but does not establish them — they are things
under test, not priors.

**H1 — Engines beat straight on originality.**
*Prediction:* device-driven engines (random-seed, inversion, lens-shift) produce ideas
rated higher on originality/novelty than the device-free STRAIGHT control arm.
*Two-sided test:* a significant result in the opposite direction (STRAIGHT ≥ engines) is a
valid, reportable disconfirmation.

**H2 — BACKGROUND grounding helps.**
*Prediction:* BACKGROUND-grounded generation (chain frame + source) produces ideas rated
higher than SEED-only (ungrounded, noun-only) generation.
*Two-sided test:* a significant result where SEED-only ≥ BACKGROUND is a valid, reportable
disconfirmation.

The analysis will not be biased toward confirming either prediction. A null or
reversed result is a valid outcome and must be reported without suppression.

---

## 2. Arms and Cells

The ablation runs **8 cells**: the 6 production engine × source combinations, plus one
STRAIGHT control arm per source.

| # | Engine       | Source     | Notes                                        |
|---|--------------|------------|----------------------------------------------|
| 1 | random-seed  | background | Chain-grounded random-seed (today's behavior)|
| 2 | random-seed  | seed       | Ungrounded random-seed (noun only)           |
| 3 | inversion    | background | Domain-frame inversion                       |
| 4 | inversion    | seed       | Noun-anchored inversion                      |
| 5 | lens-shift   | background | Uninhibited-persona × chain frame            |
| 6 | lens-shift   | seed       | Uninhibited-persona × noun                   |
| 7 | straight     | background | Device-free baseline on the chain frame      |
| 8 | straight     | seed       | Device-free baseline on the noun             |

Cells 7 and 8 are the null baseline (STRAIGHT control arm). They appear only in the
ablation — not in production generation. The mashup (✦) engine is excluded from Phase 1
(no beam population; cycle ≥2 only) and is not a cell in this study.

**Blocking (Amendment A2).** Within each source, all four arms share the same 20
inputs (blocks). The 8 cells are unchanged; what changes is that cell membership is
now *matched* by `block_id` across arms, so each background block yields a quad
{random-seed, inversion, lens-shift, straight} from one chain (and likewise for seed).

---

## 3. Dimensions per Phase

### Phase 1 — Daria-free topic (e.g. "novel uses for a common object")

Crowd workers rate each idea blind on:

- **Originality** — novelty/unusualness relative to the obvious response space.
- **Value** — does the idea meaningfully hinge on a genuine property of the object (for a
  brick: mass, hardness, porosity, geometry, thermal mass, abrasion, colour) to achieve
  something worthwhile, *regardless of whether it is a literal "use" or an inventive
  scenario*? 0 = the object is incidental (any object would do); 100 = removing the object
  collapses the idea. **(Amended 2026-06-02 — was "Appropriateness." See Amendment A1.)**

Both dimensions are crowd-judgeable without domain expertise. This phase isolates
engine effects cleanly (no domain-knowledge confound).

### Phase 2 — Daria topic

Crowd workers rate each idea blind on:

- **Originality** — same construct as Phase 1.
- **Surprise** — how unexpected the idea is relative to the expected idea distribution.
  Requires a calibration anchor (see §5 Exclusion Rules). If calibration fails, surprise
  is reserved for the screened panel and reported as a conditioned result.

Domain experts or an LLM judge with canon in context rate:

- **Fidelity** — whether the idea is unmistakably Daria-appropriate (could plausibly have
  aired or fit the show's sensibility). Crowd lacks the domain knowledge to judge this.

Rating scale: 0–100 sliders or 1–7 Likert (uniform across all cells and raters).

---

## 4. Fixed Thresholds

These are pre-registered. They match the implemented code defaults and may not be changed
after data collection begins.

| Parameter             | Value    | Code location                          |
|-----------------------|----------|----------------------------------------|
| Reliability floor (α) | ≥ 0.667  | `score.py: reliability_gate(alpha_floor=0.667)` |
| Reliability alt (ICC) | ≥ 0.60   | Reported as alternative; α is primary  |
| Transfer floor (ρ)    | ≥ 0.70   | `transfer.py: transfer(rho_floor=0.7)` |
| Discard abort         | > 30%    | `collect.py: assert_guards(max_discard=0.30)` |
| Ratings per idea      | 5        | Set at HIT construction (`build_hits.build_assignments raters=5`); not a CLI default |
| Ideas per cell (target) | 20     | Generation target: post-fidelity-drop valid ideas; refill to 20 after drops |
| Per-cell ratings floor (abort) | ≥ 70 | `collect.py: assert_guards(min_per_cell=…)`. Derived: 20 ideas × 5 ratings × (1 − 0.30 discard) = 70 |

> **Quantity disambiguation.** "Ideas per cell = 20" is the *generation* target (20 valid
> ideas survive fidelity-drop in each cell). "Ratings per idea = 5" multiplies to a target
> of **100 ratings per cell**. The `collect.py` abort guard checks *realized ratings per
> cell*; its pre-registered floor is **70** (the 100 target minus the 30% discard cap).
> The code's `--min-per-cell` default of `10` is a non-binding CLI placeholder and **must
> be set to 70 at run time** — it is not the pre-registered value.

---

## 5. Exclusion Rules

**Fidelity judge (engine-fidelity, pre-rating):** an LLM judge classifies each idea's
content against its claimed engine label. Mismatches are dropped and logged before the
idea enters the rated set. Dropped ideas are replaced (re-generated to refill the cell
to N=20 valid ideas). This guard ensures the independent variable is clean; without it
the study measures label noise, not engine effects.

**Attention-check failures (post-collection):** raters who fail any attention check are
excluded from the analysis. Their ratings are not used. Discard rate > 30% triggers an
abort (see §4).

**Discard balance check:** discards are checked for balance across cells. Non-random
failures (e.g. inversion ideas systematically harder to parse) would bias survivors; a
cell-correlated discard pattern must be reported.

**Calibration (surprise/originality raters, Phase 2):** raters who score the calibration
set without reaching the expected spread are excluded. If the exclusion rate is too high
to sustain the minimum cell coverage, "surprise" is demoted to the screened-panel result
and reported as conditioned.

**Unreliable dimensions:** a dimension that falls below the Krippendorff α floor (< 0.667)
is reported **INCONCLUSIVE** — it is never silently dropped. This applies especially to
*fidelity*, whose removal from reporting would invert the headline result.

---

## 6. Analysis Plan

### 6.1 Blinding

Raters never see the engine or source label. Cell identity travels only as hidden
metadata keyed to the immutable idea `id` (from the corpus JSONL). The `key_map`
(`{idea_id: {engine, source}}`) is separated from the rater-visible payload at HIT
build time. A normalization pass rewrites all ideas to a uniform voice before HIT
rendering; a spot-check confirms raters cannot classify the cell from text alone.

**Pre-registered blinding criterion.** In the spot-check, blind judges attempt to assign
each idea to its engine (chance = 1/4 across the four generative engines, or 1/5 with
straight included). Pass if correct-classification accuracy is **≤ chance + 10 percentage
points**; if accuracy exceeds that, blinding has failed — the corpus is re-normalized and
re-checked before any HIT is posted. This threshold is fixed here so the spot-check cannot
be judged "passing" retroactively.

### 6.2 Reliability gate

Compute Krippendorff's α per dimension (interval level) across all raters and all
ideas. Dimensions at or above 0.667 receive status `pass`; below receive `inconclusive`.
ICC ≥ 0.60 is reported as an alternative measure. Contrasts are only computed for
`pass` dimensions. `inconclusive` dimensions are listed explicitly in the report —
never suppressed.

### 6.3 Per-cell aggregates

For each (engine × source) cell and each gate-passing dimension: mean rating and
bootstrap 95% CI (2000 resamples, seed fixed at 0).

### 6.4 Pairwise contrasts

For every (arm_a, arm_b) pair on each gate-passing dimension, contrasts are computed
**paired within block**: for each `block_id` present in both arms (same source), take
the per-block mean-rating difference, then report the paired effect size (paired
Hedges' g over the within-block differences) and a paired bootstrap 95% CI (2000
resamples, seed 0). Cross-source arm pairs are not paired (no shared blocks) and are
reported, if at all, as unpaired with that limitation stated. Contrasts for
inconclusive dimensions are not computed and are not reported as if they had been.

### 6.5 Position-effect regression

Linear regression of `rating ~ display_position` (scipy linregress). Slope, p-value,
and R² reported. A significant slope indicates order/fatigue bias; it is reported as a
covariate limitation even if it does not change the cell ranking.

> **Implementation prerequisite.** The display position each rater saw is fixed at HIT
> build time (`build_hits` records a `position` per item) but is NOT recoverable from the
> MTurk answer XML, which carries only `idea_id::dimension`. Before this regression is
> meaningful, `collect.pull()` must join each answer back to its assignment record to
> recover the per-rater position. Until that join is wired, `position_effect` returns NaN
> with a note (it does not crash); the position-effect result is reported as
> **unavailable**, not as a null finding.

### 6.6 Phase-1 → Phase-2 transfer

Spearman's ρ between Phase-1 and Phase-2 per-cell mean-rating rankings (computed on
the shared 8-cell key set). If ρ ≥ 0.70, transfer is CLAIMED. If ρ < 0.70, the report
states "Transfer NOT claimed" and presents both phases as divergent results — Phase 2
is not used to confirm a Phase-1 winner already in hand.

---

## 7. Honesty Framing

The design spec's Research-grounding section (§ "Research grounding") cites established
creativity-research findings that motivate H1 and H2. That motivation does not constitute
evidence for those hypotheses in the Spitballing context. The analysis decisions — which
dimensions to report, how to handle inconclusive dimensions, whether to claim transfer —
are fixed here and will not be adjusted after the results are in hand.

The straight control arm (cells 7–8) exists precisely so the experiment can disconfirm
H1. An outcome where STRAIGHT ≥ device engines on originality is a valid result and must
be reported as such.

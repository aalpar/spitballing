# Diverge Engine Matrix + Engine Ablation — Design

**Date:** 2026-06-02
**Status:** Approved (design, rev. 2 after crosscheck); pending implementation plan
**Extends:** `2026-06-02-background-domain-model-design.md`. BACKGROUND now feeds an
*engine matrix*, not a single seed engine; an ablation harness measures the engines empirically.
**Rev. 2 (crosscheck fixes):** corrected the 🎲-vs-"straight" conflation; replaced the overloaded
free-text corpus label with an id-based join key + structured fields; added an engine-fidelity
judge; specified deterministic persona assignment, cycle-≥2 cardinality, and mashup parent
selection; added a Part-B pre-registration section.

## Summary

Two coupled changes:

- **Part A — Diverge engine matrix.** Today the funnel dispatches only the 🎲 random-seed engine
  (grounded in a BACKGROUND dependency chain). The other three spitballing engines — 🔄
  bad-idea/inversion, 🔍 lens-shift, ✦ quota+mashup — are documented but never scheduled. Part A
  makes the funnel dispatch the engines *explicitly and in parallel*, as a matrix over two
  information **sources** (BACKGROUND, SEED).
- **Part B — Engine ablation.** Rather than *assume* which engines (and which source grounding)
  produce the best ideas, *measure* it: generate idea batches from each cell **plus a straight
  control arm**, have human raters score them blind (Consensual Assessment Technique), and rank the
  cells. Run on a Daria-free, crowd-judgeable topic first (clean causal read), then confirm on Daria.

Build order: A then B (the ablation needs the cells to exist before it can generate from them).

## Terminology: 🎲 random-seed is an engine, "straight" is the baseline

A correction from review. The four spitballing engines (`skills/spitballing/SKILL.md:52-77`) are all
*anti-convergence devices*; 🎲 **random-seed** is explicitly "the strongest anti-convergence trick —
use it most" (route every idea through a random unrelated noun). It is **not** the same as **straight
generation** — proliferating on the topic with no device at all. The research below argues against
*straight* generation, not against the random-seed engine.

So this design distinguishes:
- **Engines** (devices): 🎲 random-seed, 🔄 inversion, 🔍 lens-shift, ✦ mashup.
- **Straight** (the null baseline): generate on the frame with no device. **Not a production cell** —
  it exists only as the **control arm in the ablation**, the thing the engines are measured against.

## Research grounding (motivation, not settled result)

Each design choice maps to an established finding. These motivate the design and define the
ablation's **hypotheses** — Part B exists to test them, so they are *not* treated as proven here
(see the pre-registration note in Part B about not letting motivation bias analysis).

- **Parallel, independent generation** — *nominal groups* (independent generators pooled afterward)
  produce ~50% more ideas, and more creative ones, than interacting groups, because interaction
  causes *production blocking* (Diehl & Stroebe 1987; Mullen, Johnson & Salas 1991 meta-analysis).
  Diverge agents never share context mid-generation → the nominal-group advantage.
  ([production blocking](https://en.wikipedia.org/wiki/Production_blocking),
  [Productivity is not enough](https://www.sciencedirect.com/science/article/abs/pii/S0022103105000600))
- **The four engines are validated techniques** — 🎲 = de Bono *Random Entry*; 🔄 = *Reversal +
  Provocation*; 🔍 = perspective-taking (the *Creative Stereotype Effect*: an uninhibited persona
  raises divergent originality); ✦ = *conceptual combination*.
  ([lateral thinking](https://en.wikipedia.org/wiki/Lateral_thinking),
  [creative stereotype effect](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4749277/))
- **Hypothesis: engines beat *straight* (null) generation for originality** — the *serial-order
  effect* (Beaty & Silvia 2012): obvious ideas come first; originality emerges only after the
  salient-obvious is inhibited. Provocation/reversal/persona/random-seed are inhibiting moves; a
  *straight* (device-free) cell mostly yields the obvious-first ideas. **This is the ablation's
  central hypothesis, not a premise** — the straight control arm is how we test it.
  ([Beaty & Silvia](https://www.researchgate.net/publication/249334803))
- **Diversity at generation, convergence at selection** — Quality-Diversity work (MAP-Elites,
  novelty search) keeps a diverse archive and lets selection handle quality; premature convergence
  is the failure mode. In the funnel, REDUCE + the success criterion *is* selection, and the
  BACKGROUND frozen frame supplies the quality floor — so generation can lean into diversity.
  ([QD overview](https://www.emergentmind.com/topics/quality-diversity-algorithm))
- **Mutation vs. crossover ⇒ when ✦ runs** — random-seed/provocation/reversal/persona are *mutation*
  (exploration; create diversity); mashup is *crossover* (exploitation; recombine diversity), and
  crossover needs an already-diverse population. Hence ✦ is excluded from cycle 1 (no population yet)
  and added at cycle ≥2.
  ([crossover & diversity](https://arxiv.org/html/2507.01524),
  [crossover/mutation roles](https://www.baeldung.com/cs/genetic-algorithms-crossover-probability-and-mutation-probability))

**Note on ✦ "Quota + mashup":** the spitballing engine couples a *quota* (hit the count before
reflecting) with *mashup* (recombine two ideas). The funnel preserves both halves — the **mashup**
half is ✦'s role here; the **quota** half is already enforced by `ideasPerAgent` forcing every agent
to hit its count before returning. So ✦ is not silently narrowed; the quota lives in the dispatch
parameter, the mashup lives in the engine.

**The funnel is, structurally, a Quality-Diversity evolutionary algorithm:** BACKGROUND = behavior
space, engines = mutation operators, mashup = crossover, REDUCE = selection, corpus = archive,
never-delete/resurrect = the anti-premature-convergence archive. This motivates a future option
(see "Out of scope").

---

## Part A — Diverge engine matrix

### Sources and engines

**Sources** (raw material a cell operates on):
- **BACKGROUND** — a dependency chain from the domain model (frozen frame + high-variance leaf).
- **SEED** — a random/lateral WordNet descriptor (`noun` / `cousin` / `collision`).

**Engines** (devices):
- 🎲 **random-seed** — route every idea through the seed noun (the current grounded behavior when
  also given a chain). The strongest anti-convergence device per the engine catalog.
- 🔄 **inversion** — generate the worst/role-inverted version, then flip to insight.
- 🔍 **lens-shift** — re-attack through an uninhibited persona/discipline.
- ✦ **mashup** — recombine two existing ideas (crossover; cycle ≥2 only).

### Cycle 1 — exploration only, all parallel

The production matrix is `{🎲, 🔄, 🔍} × {BACKGROUND, SEED}` — **6 cells, no straight cell.** A cell's
*source* is single-valued (it determines grounding): a BACKGROUND cell is grounded by a chain; a
SEED cell is grounded by a noun. 🎲 needs a noun by definition, so 🎲-on-BACKGROUND means
*chain-grounded random-seed* (the current behavior — it gets both a chain and a noun) and
🎲-on-SEED means *ungrounded random-seed* (noun only). That contrast is itself an ablation question
(does BACKGROUND grounding help?).

| engine | on BACKGROUND (chain frame) | on SEED (noun only) |
|--------|------------------------------|---------------------|
| 🎲 random-seed | chain-grounded random-seed (today's behavior) | ungrounded random-seed |
| 🔄 inversion | invert the domain (worst Daria special that still holds the frame, then flip) | invert through the noun |
| 🔍 lens-shift | re-attack the frame as an uninhibited persona | persona × noun |

Resolution of the earlier "one straight cell or zero" question: **zero straight cells in production.**
That decision was previously entangled with mislabeling 🎲 as "straight." 🎲 stays (it's a real
engine); a *device-free* straight cell is not run in production — it appears only as the ablation's
control arm (Part B), which is the rigorous place to decide whether straight generation is worth
anything.

**Dispatch (cycle 1).** Each cell is one diverge agent run via the existing `parallel(divergeTasks)`
barrier. The task list is built from the `ENGINES` table (below) crossed with the two sources.
Per cell ordinal `i`: BACKGROUND cells get `chain[i % nChains]`; SEED cells get `seed[i % nSeeds]`;
🎲-on-BACKGROUND gets both; 🔍 cells additionally get `persona[i % nPersonas]` (deterministic index
on the cell ordinal — the workflow cannot randomize, so assignment is index-based, mirroring the
existing `chain[i % n]` scheme).

### Cycle ≥2 — exploration + exploitation

**Cardinality (specified).** Today cycle ≥2 runs one diverge agent per surviving beam idea
(`targets = beam`, `funnel.js` `divergeTasks`). That cardinality is preserved: **one agent per beam
idea**, with an engine assigned round-robin `engine[i % nEngines]` over {🎲, 🔄, 🔍} (so the agent
count stays = beam size, not beam×engines), each perturbing its target idea further. **Plus** one or
more ✦ mashup agents over the whole beam (see below). At cycle ≥2 the "source" is the beam idea
(`source:beam`), not BACKGROUND/SEED.

**Mashup parent selection (specified).** The ✦ agent **reads the whole beam and selects the pairs
itself** (it has full tools; the workflow does not pre-pair and does not need a diversity metric or
randomness). The agent **reports the parent ids it used**. The workflow's only job is to pass the
beam and run the agent. Validation: cited parent ids **must resolve to real corpus entries** (a
post-run assertion); optionally an LLM-judge confirms the child is derivable from the two parents.
This closes the "invent-then-attach-plausible-ids" failure.

### Engine-fidelity judge (the load-bearing guard)

The engine label is the ablation's independent variable, and LLM agents sometimes ignore an engine
instruction buried in a long prompt and emit straight ideas anyway. So **before any idea enters the
rated set (Part B), and as a Part A spot-check, an LLM-judge classifies each idea's content against
its claimed engine.** Mismatches are **flagged and excluded from the rated set, and logged** (never
silently kept). Without this, Part B measures label-noise rather than engines. The judge also
verifies mashup derivability (above).

### funnel.js changes (sketch — detail in the plan)

- An `ENGINES` table: `{key, glyph, sources: ['background'|'seed'], promptFragment}` — `key` ∈
  {`random-seed`, `inversion`, `lens-shift`, `mashup`}. Cycle 1 builds `divergeTasks` from
  `ENGINES × sources` (replacing the current single-shape map); cycle ≥2 round-robins engines over
  beam targets and adds the mashup task. A `personas` constant list (uninhibited/unconventional, per
  the Creative Stereotype Effect) lives in the workflow or is passed as a `personas` arg.
- A per-engine `promptFragment` appended to `divergePrompt` (inversion / persona / random-seed),
  reusing the existing `chainBlock` and `seedInstruction`.
- A `MASHUP_SCHEMA` and `mashupPrompt` (cycle ≥2), returning the child idea + the parent ids used.
- **Corpus record gains structured fields** (this *is* a deliberate schema extension, superseding the
  earlier "no new column" goal — experimental attribution needs structure, not a parsed string):
  - `id` — already present (`c{cycle}-NNN`); **this is the immutable join key for Part B.**
  - `engine` — the engine key (`random-seed` | `inversion` | `lens-shift` | `mashup`).
  - `source` — `background` | `seed` | `beam`.
  - `parents` — array of parent ids (for `mashup`; empty/absent otherwise).
  - `seed` — keep the existing `` `${leaf} × ${seedLabel}` `` format (`funnel.js:463`) unchanged for
    the seed/leaf descriptor. Old readers ignore the new fields (backward-compatible).

### Out of scope (Part A)

- **MAP-Elites per-niche REDUCE** — keeping the best idea *per `(source × engine)` cell* rather than
  a flat top-N beam would more faithfully resist premature convergence. Promising, larger change,
  deferred. (The QD framing makes it natural later.)

---

## Part B — Engine ablation harness

### Goal & method

Measure which `(source × engine)` cells produce the highest-rated ideas, and whether they beat the
**straight control arm** (testing the central hypothesis) and whether **BACKGROUND grounding helps**
(the 🎲-on-BACKGROUND vs 🎲-on-SEED contrast). Method: **Consensual Assessment Technique (CAT)** —
human judges rate idea quality; the standard for creative output, with crowd-rating precedent.

The arms generated for the ablation: the 6 production cells **plus a straight (device-free) control
cell per source** (the only place straight generation is run).

### Two-phase rater design (decided)

- **Phase 1 — Daria-free methodology run (clean causal read).** Topic chosen so crowd workers can
  judge it cold (e.g. "novel uses for a [common object]"). Crowd rates **originality** and
  **appropriateness** (both judgeable without domain expertise). Isolates the engines *as engines*.
- **Phase 2 — Daria confirmation.** Same cells on the Daria topic. **Crowd** rates *originality* +
  *surprise* (with the calibration anchor below). **Domain fidelity** ("unmistakably Daria / could
  never have aired") is scored by a **Daria-knowledge-screened mini-panel or an LLM-judge with canon
  in context**, since the crowd lacks domain knowledge.

### Pre-registration (commit these BEFORE generating — guards against confident-but-wrong results)

The errors-lens review found multiple ways this experiment could produce a clean-looking but invalid
winner. To prevent researcher-degrees-of-freedom, the following are fixed *before* any data:

- **Reliability floor:** Krippendorff's α ≥ 0.667 (or ICC ≥ 0.60) per dimension. A dimension below
  the floor is reported as **inconclusive**, never silently dropped — *especially fidelity*, whose
  removal would invert the headline ("🔄 wins originality" with the countervailing dimension gone).
- **Contrasts are gated on reliability:** the Score step **refuses to emit a per-cell ranking for any
  dimension that fails the floor** (fail loud, not a footnote on an authoritative-looking mean).
- **Transfer criterion (Phase-1 → Phase-2):** pre-commit a minimum Spearman rank correlation between
  the Phase-1 and Phase-2 cell-mean rankings (default ρ ≥ 0.7). If it fails, the Phase-1 ranking is
  **not** claimed to transfer; both are reported as divergent. (Prevents Phase 2 from being
  confirmation theater for a Phase-1 winner already in hand.)
- **Surprise/originality reference anchor:** these are judgments relative to an expected-idea
  distribution the crowd may lack. Each rater first scores a small **calibration set** of
  known-low/known-high items; uncalibrated raters are excluded. Failing that, "surprise" is reserved
  for the screened panel.
- **Content-blinding (not just label-blinding):** engines produce self-identifying text ("the worst
  version would be…", obvious persona voice). A **normalization pass rewrites every idea to a uniform
  voice** before HIT rendering; a spot-check confirms raters can't classify the cell from text alone.
- **Hypotheses are motivation, not priors:** the Research-grounding section's claims (esp. "engines >
  straight") are the things under test; analysis decisions may not lean on them.

### Experimental design

- **Blind:** raters never see the engine/source label; cell identity travels only as hidden metadata
  keyed to the immutable idea `id`.
- **Randomized + position-aware:** idea order randomized per rater, **and each idea's display
  position is recorded** so Score can test for / regress out a position (order/fatigue) effect.
- **Multiple raters per idea** (default 5) → inter-rater reliability per the floor above.
- **Attention checks + screening:** a defined pass rule; **discard rate has an abort threshold**
  (default: abort the batch if > 30% of assignments fail), and **discards are checked for balance
  across cells** (non-random discard — e.g. harder-to-parse inversion ideas tripping more failures —
  biases the survivors).
- **Analysis:** per-cell means with CIs; pairwise engine contrasts; effect sizes — conditional on the
  reliability gate.

### Pipeline (a `tools/` research script, separate from the funnel runtime)

**Sandbox boundary (specified):** the funnel script cannot touch the filesystem, but the **diverge
agents it spawns can** — they already append ideas to the corpus JSONL (`corpusPath`). So the capture
path is: the funnel writes ideas to the corpus (as today, now with `engine`/`source`/`id` fields);
the out-of-sandbox `tools/` script **reads the corpus file**. No funnel-script FS access is needed —
this reuses the exact path the BACKGROUND/REDUCE work already uses.

1. **Generate** — run the funnel cells (+ straight control) to produce N valid ideas per cell on the
   chosen topic, written to the corpus. **Assert per-cell valid-idea count == N** before proceeding;
   fail on a short/empty cell (ragged n silently corrupts contrasts). Run the **engine-fidelity
   judge**; drop+log mismatches; re-generate to refill to N.
2. **Build HITs** — render the (normalized, blinded) ideas into the CAT instrument; embed the
   immutable idea `id` as a hidden HIT field (the join key).
3. **Post** — via the MTurk API (boto3). *Requires the user's AWS/MTurk account — the harness prepares
   and submits; the user supplies credentials and funds the batch.*
4. **Collect + reconcile** — pull assignments; **dedup by (worker, idea); reconcile expected vs.
   actual HITs**; account for approve/reject. **Assert every rating maps to exactly one known idea id**
   (count check: ratings == assignments == HITs × raters) and **assert realized ratings-per-cell ==
   target** (report the realized exposure matrix; fail loud on shortfall).
5. **Score** — reliability (gated), per-cell aggregates, contrasts, position-effect test, transfer
   check; emit a report that surfaces inconclusive dimensions explicitly.

### Open parameters (proposed defaults — confirm at review, don't interrogate)

| Parameter | Proposed default | Note |
|-----------|------------------|------|
| Platform | **MTurk** (per request) | Prolific is the higher-data-quality alternative; swap is mostly the posting adapter |
| Phase-1 topic | "novel uses for a [common object]" | classic divergent-thinking task; crowd-judgeable |
| Ideas per cell | 20 | enough for stable per-cell means |
| Raters per idea | 5 | supports reliability; balance cost |
| Dimensions | originality, appropriateness (P1); originality, surprise, +fidelity (P2) | 0–100 sliders or 1–7 Likert |
| Reliability floor | Krippendorff α ≥ 0.667 (ICC ≥ 0.60) | dimension below floor → inconclusive |
| Transfer floor | Spearman ρ ≥ 0.7 (P1↔P2 cell ranks) | below → transfer not claimed |
| Discard abort | > 30% attention-check failures | also check discard balance across cells |
| Payment | ≥ local-minimum-wage-equivalent per HIT | ethics; also data quality |

### Constraints & honest caveats

- I cannot operate the user's AWS/MTurk requester account; the user runs the posting/funding step.
- MTurk data quality for nuanced judgment is a known risk → attention checks + screening are
  mandatory, and Prolific is worth considering.
- Phase-1 ranking transferring to Daria is an assumption Phase 2 tests under the pre-registered
  transfer floor — not a guarantee.

---

## Testing / validation

- **Part A:** dry-run one cycle of the matrix on a small topic; confirm each cell fires with the
  right engine/source, ideas reflect the engine, corpus records carry `id`/`engine`/`source`(/`parents`),
  and (cycle ≥2) mashup parent ids resolve to real corpus entries. Extract the deterministic
  pure logic — engine/source/persona index assignment, the round-robin cycle-≥2 mapping, and the
  per-cell count assertion — into **pure helper functions exercised by a standalone `node` assertion
  script** (the project has no test runner, but these are the off-by-one-prone pieces; don't leave
  them to manual dry-run only). Plus `node --check`.
- **Part B:** dry-run generate→export→build-HITs against the **MTurk sandbox** (no real workers/cost):
  verify HITs render, the `id` join key round-trips, metadata stays hidden, and Score computes
  reliability on synthetic ratings. **Then a small real pilot** (one cell pair, real workers) gated
  *before* the full paid batch — synthetic data cannot reveal whether raters can actually judge the
  dimension, whether engine-tells leak past normalization, or whether attention-failures are
  cell-correlated. Those are the validity failures only real raters surface.

## Open items to confirm before planning

1. **Production matrix: zero straight cells** (🎲 is a real engine; straight is an ablation control
   only). This reverses the earlier "keep one straight cell" call, which rested on the now-corrected
   🎲≠straight confusion. Confirm.
2. **Ablation control arm:** include a device-free **straight** cell per source as the control the
   engines are measured against. Confirm.
3. **Pre-registration thresholds** (reliability α ≥ 0.667, transfer ρ ≥ 0.7, discard abort > 30%) and
   the other Part-B defaults (platform, topic, N, raters, payment).
4. **Two implementation plans** (A first, verified, then B) — recommended — or one.

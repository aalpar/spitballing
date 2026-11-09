# Engine Ablation Harness (Part B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Measure which diverge cells `(source × engine)` — plus a device-free **straight** control arm — produce the highest-rated ideas, via a blind Consensual-Assessment crowd study: Daria-free methodology run first, then a Daria confirmation. Produce a reliable, pre-registered, confound-guarded ranking.

**Architecture:** Generation stays in the funnel (JS): an ablation flag adds the straight control arm, and a `prep-ablation` mode runs an LLM engine-fidelity judge (drop+log mislabeled ideas — the ablation's independent variable must be clean) then a content-blinding normalization pass, emitting a clean `rated-set.jsonl`. A new Python package `tools/ablation/` builds HITs, posts to MTurk (sandbox→prod, user-funded), collects+reconciles, and scores (reliability-gated contrasts, position-effect regression, Phase-1→Phase-2 transfer). Thresholds are pre-registered before any run.

**Tech Stack:** funnel.js (JS workflow); Python 3.13 in `tools/ablation/` (boto3 for MTurk — **must `pip install boto3`**; numpy/scipy present; a small vendored Krippendorff's-α function — no new dep). The funnel script stays sandboxed (no fs/network); its spawned agents write files; the Python tools run outside the sandbox and read the corpus the agents wrote.

**Reference spec:** `docs/specs/2026-06-02-diverge-engine-matrix-and-ablation-design.md` (rev. 2), Part B + the pre-registration section. Part A (the engine matrix) is already merged to master.

**Reality gates (do not auto-run):** MTurk posting spends real money and needs the user's AWS/MTurk requester creds. Every live step is explicitly gated on user go-ahead; sandbox + synthetic + a tiny real pilot precede any full paid batch.

**Testing model:** funnel JS — `node --check` + dry-run (gated). Python — `python -m pytest` is overkill for this repo (none exists); use `python -m unittest` discovery in `tools/ablation/tests/` for the pure scoring/reconciliation logic (stdlib, no deps), and the MTurk **sandbox** endpoint (free, no real workers) for the post/collect round-trip.

---

## File structure

| File | Responsibility |
|------|----------------|
| `workflows/funnel.js` | + `straight` engine behind an `includeStraight` flag; + `prep-ablation` mode (fidelity judge → normalize → write rated set) |
| `tools/ablation/build_hits.py` | rated-set.jsonl → CAT HIT layouts (blind, randomized order, attention checks, embedded idea id) |
| `tools/ablation/post_hits.py` | boto3 MTurk client (sandbox/prod); create HITs; write a manifest |
| `tools/ablation/collect.py` | pull assignments; dedup; reconcile; exposure matrix; count + discard-rate assertions |
| `tools/ablation/score.py` | reliability (Krippendorff α / ICC), gated contrasts, per-cell means+CIs, position-effect regression |
| `tools/ablation/transfer.py` | Spearman ρ between Phase-1 and Phase-2 cell-mean rankings |
| `tools/ablation/reliability.py` | vendored Krippendorff's α (interval) — no new dependency |
| `tools/ablation/tests/` | unittest for reliability, reconciliation, transfer (pure logic) |
| `docs/ablation/preregistration.md` | committed BEFORE any run: hypotheses, arms, dimensions, thresholds, exclusions |

---

## Phase 1 — Generation & preparation (funnel.js, JS)

### Task 1: Straight control arm behind an ablation flag

**Files:** Modify `workflows/funnel.js` (config + `ENGINES`/`engineInstruction` + the cycle-1 builder).

- [ ] **Step 1: Add config flag** — after `const enableMashup = ...`:
```js
const includeStraight = cfg.includeStraight ?? false // ablation only: add a device-free straight control arm
```

- [ ] **Step 2: Add the straight engine to ENGINES conditionally.** Immediately after the `const ENGINES = [...]` literal, add:
```js
// Straight = the device-free null baseline (NOT a production engine). Included
// only for the ablation control arm, behind includeStraight.
if (includeStraight) {
  ENGINES.push({ key: 'straight', glyph: '▫', sources: ['background', 'seed'] })
}
```
(`ENGINES` must be declared with `const` but `.push` mutates the array in place — allowed. If the implementer finds `ENGINES` frozen, change its declaration to a plain `const` array without `Object.freeze`.)

- [ ] **Step 3: Add the straight branch to `engineInstruction`** — as the FIRST check inside the function:
```js
  if (engineKey === 'straight') {
    return `Engine — STRAIGHT: just proliferate directly on the topic. Use no special device — no random object, no inversion, no persona. Plain, on-target ideas.`
  }
```

- [ ] **Step 4:** `node --check workflows/funnel.js` (exit 0); commit `feat(ablation): straight control arm behind includeStraight flag`.

### Task 2: `prep-ablation` mode — fidelity judge + content-blinding normalization

**Files:** Modify `workflows/funnel.js` (a `FIDELITY_SCHEMA`, a `prepAblationPrompt`, and a `mode === 'prep-ablation'` block alongside `background`/`select`).

The mode runs ONE agent (batch over the corpus) that: (1) reads the corpus JSONL at `corpusPath`; (2) for each idea, judges whether its text actually exhibits its claimed `engine` (random-seed routes through a noun; inversion flips a worst-case; lens-shift carries a persona; straight uses no device; mashup fuses two parents) → verdict `match|mismatch`; (3) drops mismatches; (4) rewrites every surviving idea to a **uniform deadpan voice that strips engine tells** (no "WORST:", no persona stage-direction, no "route through X" scaffolding — just the idea); (5) writes `${ratedSetPath}` as JSONL `{id, engine, source, text}` (normalized text; engine/source kept as HIDDEN metadata, never shown to raters) and `${fidelityReportPath}` as JSON `{judged, matched, dropped:[{id,engine,why}]}`.

- [ ] **Step 1: Add config** — after the Task-1 flag:
```js
const ratedSetPath = cfg.ratedSetPath // prep-ablation: where the clean, normalized rated set is written
const fidelityReportPath = cfg.fidelityReportPath // prep-ablation: where the fidelity-judge report is written
```
and a guard with the other mode guards:
```js
if (mode === 'prep-ablation' && (!corpusPath || !ratedSetPath || !fidelityReportPath)) {
  throw new Error('funnel: prep-ablation needs corpusPath, ratedSetPath, fidelityReportPath')
}
```

- [ ] **Step 2: Add `FIDELITY_SCHEMA`** (after `MASHUP_SCHEMA`):
```js
const FIDELITY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    ratedSet: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          id: { type: 'string' },
          engine: { type: 'string' },
          source: { type: 'string' },
          text: { type: 'string' },
        },
        required: ['id', 'engine', 'source', 'text'],
      },
    },
    dropped: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          id: { type: 'string' },
          engine: { type: 'string' },
          why: { type: 'string' },
        },
        required: ['id', 'engine', 'why'],
      },
    },
    judged: { type: 'integer' },
    written: { type: 'boolean' },
  },
  required: ['ratedSet', 'dropped', 'judged', 'written'],
}
```

- [ ] **Step 3: Add `prepAblationPrompt`** (after `mashupPrompt`):
```js
function prepAblationPrompt() {
  return [
    `You are the ABLATION PREP stage. Read the idea corpus (JSONL, one idea per line)`,
    `at ${corpusPath}. Each idea has: id, engine, source, text.`,
    ``,
    `STEP 1 — FIDELITY JUDGE. For each idea decide if its TEXT actually exhibits its`,
    `claimed "engine":`,
    `  - random-seed: routes the idea through a concrete unrelated object/noun.`,
    `  - inversion: takes a worst-case / failure and FLIPS it into the idea.`,
    `  - lens-shift: is framed through a distinct persona/discipline's view.`,
    `  - straight: uses NO device — plain on-topic idea.`,
    `  - mashup: genuinely fuses two distinct prior ideas.`,
    `Mark mismatches and DROP them (record id, engine, why in "dropped"). The engine`,
    `label is an experiment variable — be strict.`,
    ``,
    `STEP 2 — BLIND/NORMALIZE the survivors. Rewrite each surviving idea into ONE uniform,`,
    `neutral voice so a reader CANNOT tell which engine produced it. Remove all tells:`,
    `no "WORST:"/"FLIP", no persona stage-directions, no "route through X" scaffolding,`,
    `no meta. Preserve the idea's substance and length; change only the giveaway style.`,
    ``,
    `STEP 3 — WRITE two files:`,
    `  - ${ratedSetPath}: JSONL, one line per surviving idea: {"id","engine","source","text"}`,
    `    where text is the NORMALIZED text. (engine/source are hidden metadata for analysis,`,
    `    never shown to raters — but keep them in this file.)`,
    `  - ${fidelityReportPath}: JSON {"judged":N,"matched":M,"dropped":[...]}.`,
    ``,
    `Return JSON: {ratedSet:[{id,engine,source,text}], dropped:[{id,engine,why}], judged, written:true}.`,
  ].join('\n')
}
```

- [ ] **Step 4: Add the mode block** (before `if (mode === 'select')`):
```js
if (mode === 'prep-ablation') {
  phase('Background')
  const prep = await agent(prepAblationPrompt(), { schema: FIDELITY_SCHEMA, label: 'prep-ablation', phase: 'Background' })
  log(`Fidelity: judged ${prep.judged}, kept ${prep.ratedSet.length}, dropped ${prep.dropped.length}.`)
  return { mode, topic, ratedSetPath, fidelityReportPath, kept: prep.ratedSet.length, dropped: prep.dropped, written: prep.written }
}
```

- [ ] **Step 5:** `node --check` (exit 0); commit `feat(ablation): prep-ablation mode (fidelity judge + blinding normalization)`.

---

## Phase 2 — HIT pipeline (Python, `tools/ablation/`)

> All Python files start with `#!/usr/bin/env python3` and a module docstring, matching `tools/gen-seeds.py` style. Add `tools/ablation/__init__.py` (empty).

### Task 3: `build_hits.py` — rated set → CAT HITs

**Files:** Create `tools/ablation/build_hits.py`, `tools/ablation/tests/test_build_hits.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_build_hits.py`): given a rated set of 8 ideas × 8 cells and `raters=5`, `assert` that `build_assignments(...)` yields, per rater, a shuffled list that (a) contains every idea, (b) inserts the configured number of attention-check items, (c) records each idea's display `position`, and (d) never exposes `engine`/`source` in the rater-visible payload (only in a side `key` map). Run `python -m unittest tools.ablation.tests.test_build_hits` → expect FAIL (module missing).

- [ ] **Step 2: Implement `build_hits.py`** with:
  - `load_rated_set(path) -> list[dict]`
  - `build_assignments(ideas, raters, attention_items, rng_seed) -> list[Assignment]` — deterministic shuffle per rater (seeded; this is OFFLINE Python, `random.Random(seed)` is fine — the no-randomness rule was a *workflow-script* constraint, not a tools constraint); each Assignment carries `[{idea_id, position, text}]` (NO engine/source) + interleaved attention checks with known answers.
  - `render_question_xml(assignment, dimensions) -> str` — MTurk QuestionForm XML: per idea, one slider/Likert per dimension; the idea `id` stored as the answer-grouping key, never the engine.
  - a `key_map` output `{idea_id: {engine, source}}` written to a separate `keys.json` the rater never sees.
- [ ] **Step 3:** run the test → PASS. Commit `feat(ablation): build_hits — blind, randomized CAT HIT construction`.

### Task 4: `post_hits.py` — boto3 MTurk client

**Files:** Create `tools/ablation/post_hits.py`.

- [ ] **Step 1: Implement** (no live call in code paths that tests touch):
  - `client(env='sandbox') -> boto3.client('mturk', endpoint_url=SANDBOX_URL if sandbox else PROD_URL, region_name='us-east-1')`. SANDBOX_URL = `https://mturk-requester-sandbox.us-east-1.amazonaws.com`. Credentials from the standard AWS env/credentials chain (never hard-coded).
  - `create_batch(client, assignments, reward, lifetime, assignment_duration, max_assignments, qualifications)` — one `create_hit` per assignment-group; returns a manifest `[{hit_id, idea_ids}]` written to `manifest.json`.
  - Attach a qualification requirement (e.g. ≥95% approval, ≥100 HITs; for Phase 2 fidelity panel, a custom Daria-knowledge qualification id passed in).
- [ ] **Step 2:** a `--dry-run` flag that prints the HIT payloads without calling MTurk; a `--env sandbox|prod` flag. Commit `feat(ablation): post_hits — MTurk create_hit batch (sandbox/prod, manifest)`.
- [ ] **Step 3 (GATED, user-run):** `python -m tools.ablation.post_hits --env sandbox ...` against the real sandbox endpoint with the user's sandbox creds — verify HITs appear in the sandbox worker UI and the manifest is written. Do not run prod here.

### Task 5: `collect.py` — pull, dedup, reconcile

**Files:** Create `tools/ablation/collect.py`, `tools/ablation/tests/test_collect.py`.

- [ ] **Step 1: Write failing tests** for the PURE functions (feed synthetic assignment dicts, no boto3): `dedup(answers)` removes duplicate `(worker_id, idea_id)` keeping the first; `reconcile(manifest, answers)` returns `{expected, actual, missing_hits, extra}`; `attention_pass(answers, checks)` returns per-worker pass/fail and the overall discard rate; `exposure_matrix(answers, key_map)` returns ratings-count per cell. Assert: dedup drops dupes; reconcile flags a missing HIT; discard rate computed; exposure balanced check. Run → FAIL.

- [ ] **Step 2: Implement** the pure functions above + a thin `pull(client, manifest)` that calls `list_assignments_for_hit` and parses the QuestionForm answers into `{worker_id, idea_id, dimension, value, position}` rows. Write `ratings.csv` + `exposure.json`. **Assertions that ABORT (per pre-reg):** discard rate > 30% → raise; any cell's realized rater count < target → raise; any rating whose `idea_id` is not in `key_map` → raise (join-key integrity).
- [ ] **Step 3:** tests PASS. Commit `feat(ablation): collect — dedup, reconcile, exposure, abort guards`.

---

## Phase 3 — Scoring (Python)

### Task 6: `reliability.py` + `score.py`

**Files:** Create `tools/ablation/reliability.py`, `tools/ablation/score.py`, `tools/ablation/tests/test_reliability.py`.

- [ ] **Step 1: Write failing tests** for `krippendorff_alpha(matrix, level='interval')` on known fixtures: perfect agreement → α==1.0; the canonical Krippendorff worked example → α≈0.811 (±0.01); all-disagree → α≤0. Run → FAIL.
- [ ] **Step 2: Implement `reliability.py`** — vendored interval-level Krippendorff's α (units × coders matrix with missing values; standard δ²-based observed/expected disagreement). ~40 lines, numpy only, no new dep. Tests PASS.
- [ ] **Step 3: Implement `score.py`**:
  - `aggregate(ratings, key_map)` → per-cell, per-dimension mean + bootstrap 95% CI.
  - `reliability_gate(ratings, alpha_floor=0.667)` → per-dimension α; a dimension below floor is tagged `inconclusive`.
  - `contrasts(cells, dimension)` → pairwise engine/source contrasts with effect sizes (Hedges' g), **only for dimensions that passed the gate** (gated — refuse to rank an inconclusive dimension; emit it as inconclusive, never silently drop, especially `fidelity`).
  - `position_effect(ratings)` → regress rating on display position (scipy.stats.linregress); report slope + p.
  - `report(...)` → write `report.md` + `report.json`: per-cell table, gated contrasts, position effect, and an explicit "INCONCLUSIVE dimensions" section.
- [ ] **Step 4:** commit `feat(ablation): reliability (Krippendorff α) + gated scoring/contrasts/position`.

### Task 7: `transfer.py` — Phase-1 → Phase-2

**Files:** Create `tools/ablation/transfer.py`, test.

- [ ] **Step 1: failing test** — `transfer(rank1, rank2, rho_floor=0.7)` returns `{rho, p, transfers: bool}`; identical ranks → rho==1.0, transfers True; reversed → transfers False. Run → FAIL.
- [ ] **Step 2: implement** with `scipy.stats.spearmanr`; the report states "transfer NOT claimed" when `rho < rho_floor`. Test PASS. Commit `feat(ablation): Phase-1→Phase-2 transfer (Spearman, pre-registered floor)`.

---

## Phase 4 — Pre-registration & run protocol

### Task 8: Pre-registration document (commit BEFORE any generation)

**Files:** Create `docs/ablation/preregistration.md`.

- [ ] **Step 1: Write** the pre-registration capturing (verbatim from the spec's pre-reg section, made concrete): the hypotheses (H1: engines > straight on originality; H2: BACKGROUND-grounding ≥ ungrounded; both two-sided, the experiment can disconfirm), the arms (3 engines × 2 sources + straight × 2 = 8 cells), the dimensions per phase, the fixed thresholds (Krippendorff α ≥ 0.667; transfer ρ ≥ 0.7; discard-abort > 30%; raters/idea = 5; ideas/cell = 20), the exclusion rules (fidelity-judge drops; attention-check fails; dimension-below-floor → inconclusive not dropped), and the analysis plan (gated contrasts, position regression, bootstrap CIs). State that the Research-grounding hypotheses are under test, not assumed.
- [ ] **Step 2:** commit `docs(ablation): pre-registration (hypotheses, arms, thresholds, exclusions)`. **This commit must precede any generation/collection commit** — the pre-reg is only meaningful before data.

### Task 9: Run protocol (GATED — user-funded, sequential)

**Files:** none (a runbook executed with the user). Each step needs explicit user go-ahead; report results between steps.

- [ ] **Step 1 — Generate Phase-1 (Daria-free).** Run the funnel with `includeStraight:true` on the pre-registered Daria-free topic (e.g. "novel uses for a brick"), cycle 1, to fill 8 cells; `prep-ablation` to produce the clean rated set. **Assert per-cell valid count == 20** (regenerate to refill after fidelity drops).
- [ ] **Step 2 — Sandbox dry-run.** `build_hits` → `post_hits --env sandbox` → `collect` → `score` on the sandbox endpoint with synthetic/self ratings. Verify the id join-key round-trips, blinding holds, the report renders, and gates fire on injected bad data.
- [ ] **Step 3 — Real pilot (GATED, small spend).** One cell-pair, real workers, ~5 raters: confirm (a) raters can't classify the cell from text (blinding held), (b) they can actually judge originality/appropriateness, (c) attention-fails aren't cell-correlated. Only proceed if the pilot is clean.
- [ ] **Step 4 — Phase-1 full batch (GATED).** Post all Phase-1 HITs; collect; score. Record the cell ranking.
- [ ] **Step 5 — Phase-2 (Daria) (GATED).** Generate on the Daria topic; crowd rates originality+surprise (with the calibration anchor); the Daria-knowledge panel / LLM-judge rates fidelity. Score; run `transfer.py` against Phase-1. Report finalists-of-engines with the transfer verdict and any inconclusive dimensions surfaced.

---

## Self-review (completed during planning)

- **Spec coverage (Part B):** straight control arm (T1); engine-fidelity judge + content-blinding (T2 — the two load-bearing crosscheck fixes); HIT build with blind/randomized/position/attention (T3); MTurk post sandbox/prod + manifest (T4); collect dedup/reconcile/exposure + abort guards (T5); reliability floor + gated contrasts + position effect (T6); transfer criterion (T7); pre-registration before data (T8); two-phase Daria-free→Daria run with sandbox + real pilot gates (T9). Every Part-B spec bullet and pre-reg item maps to a task.
- **Sandbox boundary:** generation/judge/normalize happen in funnel agents (which write files); Python tools read those files + talk to MTurk — no funnel-script FS/network. Consistent with the spec.
- **Dependency honesty:** boto3 must be installed (flagged in header + Task 4); Krippendorff α is vendored (no new dep); numpy/scipy already present. `random.Random(seed)` is used only in offline Python (the no-randomness rule was a workflow-script constraint — called out in T3).
- **Type/name consistency:** the clean rated-set record `{id, engine, source, text}` is produced by `prep-ablation` (T2 `FIDELITY_SCHEMA`) and consumed by `build_hits` (T3); `key_map`/`keys.json` `{idea_id:{engine,source}}` is produced in T3 and consumed by `collect` (T5) and `score` (T6); the immutable `id` is the join key throughout (T3→T5→T6), as the spec requires.
- **Gating:** no Python task performs a live paid MTurk call in its implementation/test steps; all live calls are in T9, each marked GATED.
- **Placeholder note:** T4/T9 give boto3 call names and the protocol rather than full end-to-end MTurk request bodies, because the exact QuestionForm/qualification payloads must be finalized against the live API at build time; the structure, endpoints, flags, and assertions are concrete. Acceptable for an external-API integration plan.

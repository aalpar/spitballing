# Canon-Fidelity Judge — Design

**Date:** 2026-06-02
**Status:** Design — approved in brainstorming, pending spec review.
**Part of:** Engine Ablation Harness (Part B), Phase 2 scoring.
**Related:** `docs/specs/2026-06-02-diverge-engine-matrix-and-ablation-design.md`,
`docs/ablation/preregistration.md`, `docs/specs/2026-06-02-engine-ablation-plan.md`.

---

## 1. Problem

Phase 2 of the ablation rates three dimensions. The crowd can judge **originality**
and **surprise** cold, but **domain fidelity** — "is this idea unmistakably *Daria*?
could it never have aired?" — requires specialized knowledge the crowd lacks. Screening
the crowd for that knowledge is unreliable: self-reported fandom is corrupted both by
incentive to misrepresent (workers claim eligibility to access paid work) and by
honest-but-wrong self-assessment (Dunning–Kruger). See the methodology discussion that
motivated this design.

The design spec already names the alternative: score fidelity with *"an LLM-judge with
canon in context."* This document specifies that judge.

### The "with canon" requirement

A bare LLM judge would rely on its parametric (in-weights) memory of *Daria*, which is
fuzzy, un-auditable, and version-drifting. Worse, because the ideas under test were
themselves LLM-generated, a bare self-judging loop is **circular** — the judge shares the
generator's blind spots (self-preference, correlated errors).

The defense is to move the domain knowledge **out of the weights and into the prompt**: a
hand-authored **canon doc** supplies inspectable, fixed ground truth. The judge reasons
over supplied facts rather than recalled ones. This is reference-grounded evaluation (the
same principle as RAG, applied to judging).

---

## 2. Naming — avoid the collision

`funnel.js` `prep-ablation` mode already contains a *"fidelity judge"*, but it judges a
**different** thing. The two must not be conflated:

| | **Engine-fidelity judge** (exists) | **Canon-fidelity judge** (this design) |
|---|---|---|
| Question | Does the idea use its claimed *engine*? | Is the idea unmistakably *Daria*? |
| Role | Cleans the **independent variable** (drops mislabeled ideas pre-study) | Scores a **dependent variable** (a Phase-2 rating dimension) |
| When | Pre-processing, before HITs | Scoring, alongside crowd ratings |

This component is the **canon-fidelity judge** throughout. It is **domain-agnostic**: it
reads whatever canon file `canonPath` points at. *Daria* is the first instance.

---

## 3. Key design decisions (from brainstorming)

1. **Judge as a panel of N raters.** A single call yields one score with no reliability
   signal. Instead, run `N` independent agent calls (default 5, matching the crowd panel).
   Each is a "rater"; Krippendorff α across them measures the judge's self-consistency
   under the **same** gate the crowd faces. A judge that does not converge with itself is
   marked `inconclusive` and dropped from contrasts — it earns trust through agreement,
   not assertion.
2. **Lives in `funnel.js` as a new mode**, reusing the existing `agent()`+schema+file-IO
   pattern (sibling of `prep-ablation`). No new dependency; consistent with where LLM
   judging already lives. (Rejected: a Python tool calling the `anthropic` SDK — adds a
   dependency against the standing "prefer stdlib" preference and duplicates LLM plumbing.)
3. **The human authors the canon.** An LLM-drafted canon would re-introduce the
   fuzzy-memory circularity the canon exists to break. The build scaffolds a template with
   `<you fill>` stubs; the domain facts are authored by hand.
4. **Gold-set / human cross-check is deferred** (out of scope this round). This round
   delivers the judge and its integration, not validation of judgment quality.

---

## 4. Architecture & data flow

```
                        canonPath (docs/ablation/canon-daria.md  <- human-authored)
                            |
ratedSetPath --------------+
{id,engine,source,text}    |   funnel.js  mode='canon-fidelity'
(Phase-2 ideas, normalized)|   +--------------------------------------+
                           +-->| for i in 1..N (deterministic per-i    |
                               |   permutation of idea order):         |
                               |   agent(canonFidelityPrompt(canon),   |
                               |         {schema: CANON_FIDELITY_SCHEMA})|
                               |   -> judge i scores every idea         |
                               +--------------+----------------------+--+
                                              v                      v
                          fidelity-ratings.jsonl         canon-fidelity-report.json
                          {worker_id:"llm-judge-i",      {idea_id, judge_i, score,
                           idea_id, dimension:"fidelity",  rationale-citing-canon}
                           value, position}               (AUDIT trail, kept separate)
                                              |
                  merge with Phase-2 crowd ratings (originality, surprise)
                                              v
                          score.py  aggregate / reliability_gate / contrasts
                          (UNCHANGED — fidelity is just another dimension;
                           llm-judge-1..N are just N raters -> Krippendorff α)
```

The two-file split mirrors `prep-ablation`: `fidelity-ratings.jsonl` stays pure to
`score.py`'s rating contract; `canon-fidelity-report.json` holds the per-idea rationales —
the audit trail that lets a reviewer read *why* each score was given and whether it cited
canon principles versus surface tells.

### Semantics

- **Reliability.** The N judge rows for the `fidelity` dimension flow through the existing
  `reliability_gate`. Converging judges → `pass` → fidelity enters ranked contrasts.
  Diverging judges → `inconclusive` → fidelity is reported but excluded from contrasts.
  Identical to the treatment of a noisy crowd dimension.
- **`position`.** Set to the idea's slot in that judge's permuted order, so
  `position_effect` can detect judge order-bias, mirroring the crowd's randomized display.
  The permutation is **deterministic per judge index** (e.g. stable sort keyed by a hash of
  `idea_id` + judge index) — reproducible and requiring no `Math.random` (banned in the
  workflow runtime).
- **Blinding.** The judge sees normalized idea text only — never `engine`/`source` (kept as
  hidden metadata in `key_map`, as for the crowd).

---

## 5. Components

### 5.1 `CANON_FIDELITY_SCHEMA` (new const in `funnel.js`)

```
{ ratings: [ { idea_id:  string,
               fidelity: integer (1–7),    // the score
               rationale: string } ] }     // must cite canon, not surface tells
```

One agent call returns one judge's scores for **all** ideas. Schema-forced output — no
parsing.

### 5.2 `canonFidelityPrompt(canonText, ideasInOrder)` (new fn)

- Embeds the **full canon doc** verbatim as ground truth.
- States the fidelity scale anchors (1 = "could never be Daria" … 7 = "unmistakably Daria,
  could have aired").
- Instructs the judge to score against canon **facts and stance**, not vocabulary, and
  declares that a rationale citing only surface tells (e.g. "mentions Lawndale") is
  insufficient. This is the defense against surface-feature matching.
- Receives ideas in the per-judge permuted order so `position` is real.

### 5.3 `mode === 'canon-fidelity'` block (new, beside `prep-ablation`)

- Validates required cfg: `ratedSetPath`, `canonPath`, `canonRatingsPath`,
  `canonReportPath`. (Config names are deliberately distinct from `prep-ablation`'s
  `fidelityReportPath`, which belongs to the engine-fidelity judge — see §2.)
- `N = cfg.judgePanelN ?? 5`. Runs N agent calls, each on a deterministic per-judge
  permutation of the ideas.
- Expands each judge's `ratings[]` into rows `{worker_id:"llm-judge-{i}", idea_id,
  dimension:"fidelity", value, position}`; writes `canonRatingsPath` (JSONL,
  default `fidelity-ratings.jsonl`) and `canonReportPath` (JSON with rationales,
  default `canon-fidelity-report.json`).
- Returns `{mode, judges:N, ideas, written}`.

### 5.4 Canon doc template — `docs/ablation/canon-daria.md`

Scaffolded with `<you fill>` stubs; **human-authored** content. Sections:
- **Characters & voice** — voice *rules* stated as checkable constraints, not bios.
- **Setting & tone** — the world and its satirical stance.
- **Thematic spine** — what the show is about (most discriminative section).
- **Canon vs. anti-canon worked examples** — minimal pairs, each with a one-line *why*
  naming the principle it turns on; include at least one **trap** (surface-plausible but
  essence-wrong) to teach that the boundary is stance, not vocabulary.

Authoring principle: the canon must **discriminate**, not describe. Every line must help
separate Daria from a generic teen show; when a fact is uncertain, omit it rather than
commit a false ground truth. Target ~1 page. Frozen per run — a canon revision is a new
study condition, not a silent edit.

### 5.5 Merge / ingest

A thin step joins judge rows with Phase-2 crowd rows before `score.py`. If `score.py`'s CLI
already loads a ratings file, this is a flag pointing at `fidelity-ratings.jsonl`;
otherwise a small loader (load JSONL, `extend` the ratings list). Mechanical — confirmed
against the actual `score.py` CLI at implementation time. **`score.py` internals are
unchanged.**

---

## 6. Testing

Following `tools/ablation/tests/` discipline, split by language:

- **JS (mode logic), `agent()` mocked — no live model.** Fixture canon + 3–4 ideas. Assert:
  N×M rows emitted; `worker_id` set `llm-judge-1..N`; `position` covers each judge's
  permutation; `dimension == "fidelity"`; both output files written; schema shape honored.
- **Python (integration).** Feed synthetic `fidelity` rows (3 judges, varied agreement)
  through `score.py`. Assert the α gate fires correctly: converging judges → `pass` +
  contrasts present; diverging judges → `inconclusive` + no contrasts. This proves the
  drop-in-rater claim end-to-end.
- **Not tested:** judgment *quality* — that is the deferred gold-set validation.

---

## 7. Scope

**In:** `CANON_FIDELITY_SCHEMA`, `canonFidelityPrompt`, the `canon-fidelity` mode block,
the canon template doc, the merge step, and the tests above.

**Out (deferred):** gold-set / human cross-check of the judge; judge prompt-tuning; any
live-model evaluation; canon content for any domain other than *Daria*.

**Unchanged:** `score.py` internals; the existing engine-fidelity (`prep-ablation`) judge.

---

## 8. Open items for implementation

- Confirm the exact `score.py` CLI ratings-loading path to fix the merge step (§5.5).
- Confirm the deterministic per-judge permutation method (stable hash sort vs. index
  rotation) against the workflow runtime's available primitives.

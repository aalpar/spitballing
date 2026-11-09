# Canon-Fidelity Judge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `canon-fidelity` mode to `workflows/funnel.js` that scores Phase-2 ideas for domain fidelity using a panel of N independent LLM judges grounded in a hand-authored canon doc, emitting rating rows that drop straight into `score.py` as one more dimension.

**Architecture:** The workflow JS runtime has **no filesystem access** (only agents do IO) and **no `Math.random`/`Date`**. So the mode is three agent roles with pure-JS glue between them: (1) a **reader** agent loads the canon text + blinded idea list into the workflow; (2) JS computes a deterministic per-judge idea ordering (stable hash sort) and fans out **N judge** agents in parallel; (3) JS expands each judge's scores into `{worker_id, idea_id, dimension:"fidelity", value, position}` rows and hands them to a **writer** agent that persists `fidelity-ratings.jsonl` + `canon-fidelity-report.json`. The deterministic, order-sensitive logic is extracted to a pure module so it is unit-testable without a live model. `score.py` is unchanged; fidelity rows merge into the crowd ratings list via a small JSONL loader.

**Tech Stack:** Node 22 ESM + `node --test` (no new JS deps); Python 3.13 + pytest + numpy/scipy (existing). The two §8 open items are resolved: (a) `score.py` exposes no CLI — merge is `ratings.extend(load_ratings_jsonl(path))`; (b) the per-judge permutation is a pure-JS djb2 stable sort keyed by `idea_id#judgeIndex`.

---

## File Structure

- **Create** `workflows/lib/canon-fidelity.js` — pure, runtime-global-free helpers: `djb2`, `hashOrder`, `expandJudgeRows`, `buildReport`. The single source of the deterministic ordering + row-expansion logic. No workflow globals, no IO — fully importable and testable.
- **Create** `workflows/lib/canon-fidelity.test.js` — `node --test` unit tests for the above.
- **Modify** `workflows/funnel.js` — import the helpers; add `CANON_READER_SCHEMA`, `CANON_FIDELITY_SCHEMA`, `CANON_WRITER_SCHEMA`; add `canonReaderPrompt`, `canonFidelityJudgePrompt`, `canonWriterPrompt`; add config validation and the `mode === 'canon-fidelity'` block.
- **Modify** `tools/ablation/collect.py` — add `load_ratings_jsonl(path)` beside `write_ratings_csv`.
- **Create** `tools/ablation/tests/test_canon_fidelity.py` — Python tests: loader round-trip + the core drop-in-rater property (gate pass vs. inconclusive). The core-property assertions are left as a marked TODO for the author (per the project's learning-through-exercise convention).
- **Create** `docs/ablation/canon-daria.md` — `<you fill>` canon template; human-authored content.

---

### Task 1: Pure helper module + JS unit tests

**Files:**
- Create: `workflows/lib/canon-fidelity.js`
- Test: `workflows/lib/canon-fidelity.test.js`

- [ ] **Step 1: Write the failing test**

Create `workflows/lib/canon-fidelity.test.js`:

```js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { djb2, hashOrder, expandJudgeRows, buildReport } from './canon-fidelity.js'

const IDS = ['c1-001', 'c1-002', 'c1-003', 'c1-004']

test('djb2 is deterministic and unsigned', () => {
  assert.equal(djb2('c1-001#1'), djb2('c1-001#1'))
  assert.ok(djb2('c1-001#1') >= 0)
})

test('hashOrder is a permutation of the input ids', () => {
  const order = hashOrder(IDS, 1)
  assert.deepEqual([...order].sort(), [...IDS].sort())
  assert.equal(order.length, IDS.length)
})

test('hashOrder is deterministic per judge index', () => {
  assert.deepEqual(hashOrder(IDS, 3), hashOrder(IDS, 3))
})

test('hashOrder differs across judge indices', () => {
  // With 4 ids, at least one of judges 1..5 must differ from judge 1,
  // else "position" would be identical for every judge.
  const base = hashOrder(IDS, 1).join(',')
  const anyDifferent = [2, 3, 4, 5].some((i) => hashOrder(IDS, i).join(',') !== base)
  assert.ok(anyDifferent)
})

test('expandJudgeRows emits N x M fidelity rows with correct worker_ids and positions', () => {
  const orderByJudge = [hashOrder(IDS, 1), hashOrder(IDS, 2)]
  const judgeOutputs = orderByJudge.map((order) => ({
    ratings: order.map((id) => ({ idea_id: id, fidelity: 4, rationale: 'r' })),
  }))
  const rows = expandJudgeRows(judgeOutputs, orderByJudge)

  assert.equal(rows.length, 2 * IDS.length) // N x M
  assert.deepEqual(
    [...new Set(rows.map((r) => r.worker_id))].sort(),
    ['llm-judge-1', 'llm-judge-2'],
  )
  assert.ok(rows.every((r) => r.dimension === 'fidelity'))
  // Each judge's positions cover 1..M exactly, in that judge's permuted order.
  for (const [k, order] of orderByJudge.entries()) {
    const judgeRows = rows.filter((r) => r.worker_id === `llm-judge-${k + 1}`)
    assert.deepEqual(judgeRows.map((r) => r.position), order.map((_, i) => i + 1))
    assert.deepEqual(judgeRows.map((r) => r.idea_id), order)
  }
  assert.ok(rows.every((r) => typeof r.value === 'number'))
})

test('buildReport carries per-judge rationales as an audit trail', () => {
  const orderByJudge = [hashOrder(IDS, 1)]
  const judgeOutputs = [{
    ratings: IDS.map((id) => ({ idea_id: id, fidelity: 6, rationale: `why ${id}` })),
  }]
  const report = buildReport(judgeOutputs, orderByJudge)
  assert.equal(report.judges, 1)
  assert.equal(report.ratings.length, IDS.length)
  assert.deepEqual(report.ratings[0], {
    idea_id: IDS[0], judge: 1, score: 6, rationale: `why ${IDS[0]}`,
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test workflows/lib/canon-fidelity.test.js`
Expected: FAIL — `Cannot find module '.../canon-fidelity.js'`.

- [ ] **Step 3: Write minimal implementation**

Create `workflows/lib/canon-fidelity.js`:

```js
// Pure helpers for the canon-fidelity judge mode of funnel.js.
//
// Deliberately free of workflow globals (agent/parallel/phase/log/args) and of
// filesystem/Date/Math.random so it can be unit-tested directly with node:test
// AND imported by the workflow runtime. The workflow runtime has no fs and bans
// Math.random/Date, which is exactly why the per-judge ordering is computed here
// from a deterministic string hash instead of a shuffle.

// djb2 string hash, forced to uint32. Deterministic; no Math.random.
export function djb2(str) {
  let h = 5381
  for (let i = 0; i < str.length; i++) {
    h = (((h << 5) + h) + str.charCodeAt(i)) >>> 0 // h * 33 + c, keep uint32
  }
  return h >>> 0
}

// murmur3 fmix32 avalanche finalizer: fully diffuses input bits so a small
// change (e.g. the judge salt) scrambles the entire 32-bit result.
function fmix32(h) {
  h ^= h >>> 16
  h = Math.imul(h, 0x85ebca6b) >>> 0
  h ^= h >>> 13
  h = Math.imul(h, 0xc2b2ae35) >>> 0
  h ^= h >>> 16
  return h >>> 0
}

// Per-(idea, judge) sort key. NOTE: djb2(`${id}#${judge}`) does NOT work — djb2
// is h*33+c, so a concatenated salt and the id contribute separably; ids that
// differ only in a trailing digit keep their relative order regardless of judge,
// making `position` identical for every judge and defeating position-bias
// detection. Mixing the judge salt by XOR and running fmix32 avalanches it, so
// each judge index yields an independent ordering (verified empirically).
function judgeKey(ideaId, judgeIndex) {
  const salted = (djb2(ideaId) ^ Math.imul(judgeIndex + 1, 0x9e3779b1)) >>> 0
  return fmix32(salted)
}

// Deterministic per-judge idea ordering. Same (ideaIds, judgeIndex) => same
// order; different judgeIndex reorders, so `position` varies across judges and
// position_effect can detect judge order-bias. Stable: key ties are broken by
// original index, so the result is always a permutation of ideaIds.
export function hashOrder(ideaIds, judgeIndex) {
  return ideaIds
    .map((id, i) => ({ id, i, h: judgeKey(id, judgeIndex) }))
    .sort((a, b) => (a.h - b.h) || (a.i - b.i))
    .map((x) => x.id)
}

// Expand N judges' schema outputs into score.py rating rows.
//   judgeOutputs[k] = { ratings: [{ idea_id, fidelity, rationale }] } for judge k+1
//   orderByJudge[k] = that judge's deterministic idea order (from hashOrder)
// position is the 1-based slot in the judge's order — the order the judge saw.
export function expandJudgeRows(judgeOutputs, orderByJudge) {
  const rows = []
  judgeOutputs.forEach((out, k) => {
    const worker_id = `llm-judge-${k + 1}`
    const byId = new Map(out.ratings.map((r) => [r.idea_id, r]))
    orderByJudge[k].forEach((ideaId, slot) => {
      const r = byId.get(ideaId)
      rows.push({
        worker_id,
        idea_id: ideaId,
        dimension: 'fidelity',
        value: r.fidelity,
        position: slot + 1,
      })
    })
  })
  return rows
}

// Audit trail kept separate from the rating rows: per-(judge, idea) score plus
// the rationale that justified it, so a reviewer can read WHY each score landed.
export function buildReport(judgeOutputs, orderByJudge) {
  const entries = []
  judgeOutputs.forEach((out, k) => {
    out.ratings.forEach((r) => {
      entries.push({ idea_id: r.idea_id, judge: k + 1, score: r.fidelity, rationale: r.rationale })
    })
  })
  return { judges: judgeOutputs.length, ratings: entries }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test workflows/lib/canon-fidelity.test.js`
Expected: PASS — 6 tests, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add workflows/lib/canon-fidelity.js workflows/lib/canon-fidelity.test.js
git commit -m "feat(ablation): canon-fidelity pure helpers (order + row expansion)"
```

---

### Task 2: Wire the `canon-fidelity` mode into funnel.js

**Files:**
- Modify: `workflows/funnel.js` (import at top; schemas near other schemas ~line 130; prompts beside `prepAblationPrompt` ~line 463; config + validation ~lines 37-51; mode block beside `prep-ablation` ~line 600)

No new automated test in this task — the mode block calls live agents, which §7 of the spec puts out of scope. The row/order logic it depends on is already covered by Task 1; correctness here is verified by `node --check` (parse) and structural inspection. The end-to-end live run is deferred (see "Deferred verification" at the end).

- [ ] **Step 1: Add the import at the very top of `workflows/funnel.js`**

Immediately after the `export const meta = {...}` block (after line 10), add:

```js
import { hashOrder, expandJudgeRows, buildReport } from './lib/canon-fidelity.js'
```

- [ ] **Step 2: Add config + validation**

After `workflows/funnel.js:38` (the `fidelityReportPath` line), add:

```js
// canon-fidelity: distinct config names from prep-ablation's fidelityReportPath,
// which belongs to the *engine*-fidelity judge (different question — see design §2).
const canonPath = cfg.canonPath // human-authored canon doc (ground truth)
const canonRatingsPath = cfg.canonRatingsPath // JSONL fidelity rows for score.py
const canonReportPath = cfg.canonReportPath // per-judge rationale audit trail (JSON)
const judgePanelN = cfg.judgePanelN ?? 5 // raters in the judge panel (matches crowd)
```

After the `prep-ablation` validation (`workflows/funnel.js:49-51`), add:

```js
if (mode === 'canon-fidelity' && (!ratedSetPath || !canonPath || !canonRatingsPath || !canonReportPath)) {
  throw new Error('funnel: canon-fidelity needs ratedSetPath, canonPath, canonRatingsPath, canonReportPath')
}
```

- [ ] **Step 3: Add the three schemas**

After `FIDELITY_SCHEMA` (`workflows/funnel.js:129`), add:

```js
// canon-fidelity reader: pulls canon text + blinded ideas into the workflow.
const CANON_READER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    canon: { type: 'string' },
    ideas: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: { idea_id: { type: 'string' }, text: { type: 'string' } },
        required: ['idea_id', 'text'],
      },
    },
  },
  required: ['canon', 'ideas'],
}

// canon-fidelity judge: one rater's score (1-7) + canon-citing rationale per idea.
const CANON_FIDELITY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    ratings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          idea_id: { type: 'string' },
          fidelity: { type: 'integer', minimum: 1, maximum: 7 },
          rationale: { type: 'string' },
        },
        required: ['idea_id', 'fidelity', 'rationale'],
      },
    },
  },
  required: ['ratings'],
}

// canon-fidelity writer: confirms both artifacts were persisted.
const CANON_WRITER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: { written: { type: 'boolean' } },
  required: ['written'],
}
```

- [ ] **Step 4: Add the three prompt builders**

After `prepAblationPrompt` (`workflows/funnel.js:463`), add:

```js
function canonReaderPrompt() {
  return [
    `You are the CANON-FIDELITY READER. Load two inputs and return them for downstream`,
    `judging. Do NOT score anything; do NOT edit content.`,
    ``,
    `1. Read the canon doc at ${canonPath}. Return its FULL text in "canon", unchanged.`,
    `2. Read the rated set (JSONL, one idea per line) at ${ratedSetPath}. Each line has`,
    `   {id, engine, source, text}. Return "ideas" as [{idea_id, text}]: copy id -> idea_id`,
    `   and the normalized text verbatim. DROP engine and source — the judges MUST stay`,
    `   blind to them (they are hidden experiment metadata).`,
    ``,
    `Return JSON only: {canon, ideas:[{idea_id, text}]}. Write no files.`,
  ].join('\n')
}

function canonFidelityJudgePrompt(canon, orderedIdeas, judgeIndex) {
  return [
    `You are canon-fidelity rater #${judgeIndex} of an independent panel. Score how`,
    `unmistakably each idea belongs to the work described by the CANON below.`,
    ``,
    `Judge against the canon's FACTS and STANCE, never its vocabulary. An idea that only`,
    `name-drops surface tells (places, character names) WITHOUT the canon's stance is NOT`,
    `faithful. A rationale that cites only such surface tells is insufficient and must`,
    `score low — the boundary is stance, not vocabulary.`,
    ``,
    `Fidelity scale (integer 1-7):`,
    `  1 = could never be this work (wrong stance/themes);`,
    `  7 = unmistakably this work — could have shipped as canon.`,
    ``,
    `=== CANON (ground truth: reason over THIS, not your own memory) ===`,
    canon,
    `=== END CANON ===`,
    ``,
    `Score EVERY idea below, in the order given. For each: an integer 1-7 and a rationale`,
    `that cites a specific canon principle (a fact or stance line), not a surface tell.`,
    JSON.stringify(orderedIdeas, null, 0),
    ``,
    `Return JSON only: {ratings:[{idea_id, fidelity, rationale}]} — exactly one entry per`,
    `idea above, same idea_ids.`,
  ].join('\n')
}

function canonWriterPrompt(rowsJson, reportJson) {
  return [
    `You are the CANON-FIDELITY WRITER. Persist two artifacts (create parent dirs if`,
    `missing). Do NOT alter any values — only serialize.`,
    ``,
    `1. To ${canonRatingsPath} write JSONL: each element of THIS array on its own line as`,
    `   a single-line JSON object (no surrounding array, no pretty-printing):`,
    rowsJson,
    ``,
    `2. To ${canonReportPath} write THIS object as pretty-printed JSON:`,
    reportJson,
    ``,
    `Return JSON only: {written:true}.`,
  ].join('\n')
}
```

- [ ] **Step 5: Add the mode block**

After the `prep-ablation` block (`workflows/funnel.js:600`, the closing `}` of that `if`), add:

```js
// ---- canon-fidelity: panel of N LLM judges score domain fidelity --------------
if (mode === 'canon-fidelity') {
  phase('Background')
  // 1. Reader pulls canon + blinded ideas into JS (the runtime has no fs).
  const loaded = await agent(canonReaderPrompt(), { schema: CANON_READER_SCHEMA, label: 'canon:read', phase: 'Background' })
  const ideaIds = loaded.ideas.map((x) => x.idea_id)
  const byId = new Map(loaded.ideas.map((x) => [x.idea_id, x]))

  // 2. Deterministic per-judge ordering (pure JS — no Math.random), then fan out.
  const orderByJudge = []
  for (let i = 1; i <= judgePanelN; i++) {
    orderByJudge.push(hashOrder(ideaIds, i))
  }
  const judgeOutputs = await parallel(
    orderByJudge.map((order, k) => () => {
      const orderedIdeas = order.map((id) => byId.get(id))
      return agent(canonFidelityJudgePrompt(loaded.canon, orderedIdeas, k + 1),
        { schema: CANON_FIDELITY_SCHEMA, label: `canon:judge-${k + 1}`, phase: 'Background' })
    }),
  )
  // parallel() maps a failed thunk to null; a missing judge breaks the panel's
  // reliability semantics, so fail loudly rather than score a partial panel.
  if (judgeOutputs.some((o) => !o)) {
    throw new Error('funnel: a canon-fidelity judge failed; panel incomplete')
  }

  // 3. Assemble rows + audit report in JS, then a writer agent persists them.
  const rows = expandJudgeRows(judgeOutputs, orderByJudge)
  const report = buildReport(judgeOutputs, orderByJudge)
  await agent(canonWriterPrompt(JSON.stringify(rows), JSON.stringify(report, null, 2)),
    { schema: CANON_WRITER_SCHEMA, label: 'canon:write', phase: 'Background' })

  log(`Canon-fidelity: ${judgePanelN} judges x ${ideaIds.length} ideas = ${rows.length} rows.`)
  return { mode, topic, judges: judgePanelN, ideas: ideaIds.length, written: true, canonRatingsPath, canonReportPath }
}
```

- [ ] **Step 6: Verify the file parses**

Run: `node --check workflows/funnel.js`
Expected: no output, exit 0 (syntax + import-specifier shape valid).

Then re-run the Task 1 unit tests to confirm the import target is unbroken:
Run: `node --test workflows/lib/canon-fidelity.test.js`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add workflows/funnel.js
git commit -m "feat(ablation): canon-fidelity judge mode in funnel.js"
```

---

### Task 3: Python JSONL ratings loader (the merge seam)

**Files:**
- Modify: `tools/ablation/collect.py` (add `load_ratings_jsonl` beside `write_ratings_csv`, ~line 280; `json` is already imported at `collect.py:39`)
- Test: `tools/ablation/tests/test_canon_fidelity.py`

- [ ] **Step 1: Write the failing test**

Create `tools/ablation/tests/test_canon_fidelity.py`:

```python
#!/usr/bin/env python3
"""Tests for the canon-fidelity judge's integration with scoring.

Covers:
  (a) collect.load_ratings_jsonl round-trips the rating-row contract.
  (b) CORE PROPERTY (author TODO): fidelity rows are a drop-in rater set —
      converging judges pass the reliability gate and produce contrasts;
      diverging judges go 'inconclusive' and suppress contrasts.
"""
import json

from tools.ablation.collect import load_ratings_jsonl
from tools.ablation import score


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_load_ratings_jsonl_round_trips_the_contract(tmp_path):
    rows = [
        {"worker_id": "llm-judge-1", "idea_id": "c1-001", "dimension": "fidelity", "value": 6, "position": 1},
        {"worker_id": "llm-judge-2", "idea_id": "c1-001", "dimension": "fidelity", "value": 5, "position": 3},
    ]
    p = tmp_path / "fidelity-ratings.jsonl"
    _write_jsonl(p, rows)
    loaded = load_ratings_jsonl(str(p))
    assert loaded == rows


def test_load_ratings_jsonl_skips_blank_lines(tmp_path):
    p = tmp_path / "f.jsonl"
    p.write_text(
        '{"worker_id":"llm-judge-1","idea_id":"c1-001","dimension":"fidelity","value":4,"position":1}\n\n',
        encoding="utf-8",
    )
    assert len(load_ratings_jsonl(str(p))) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tools/ablation/tests/test_canon_fidelity.py -v`
Expected: FAIL on import — `cannot import name 'load_ratings_jsonl'`.

- [ ] **Step 3: Write minimal implementation**

In `tools/ablation/collect.py`, immediately after `write_ratings_csv` (the function ending near line 295), add:

```python
def load_ratings_jsonl(path: str) -> list[dict]:
    """Load rating rows from a JSONL file (one JSON object per line).

    Folds the canon-fidelity judge's fidelity rows into the crowd ratings list
    before scoring: ``ratings.extend(load_ratings_jsonl(fidelity_path))``.  Each
    line must carry the rating contract {worker_id, idea_id, dimension, value,
    position} (same keys score.aggregate / reliability_gate consume).  Blank
    lines are skipped.
    """
    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tools/ablation/tests/test_canon_fidelity.py -v`
Expected: PASS for the two `load_ratings_jsonl` tests.

- [ ] **Step 5: Commit**

```bash
git add tools/ablation/collect.py tools/ablation/tests/test_canon_fidelity.py
git commit -m "feat(ablation): JSONL ratings loader to merge fidelity rows"
```

---

### Task 4: Core property test — fidelity is a drop-in rater (author TODO)

**Files:**
- Modify: `tools/ablation/tests/test_canon_fidelity.py` (append the core-property test)

This is the test that validates the whole design: judges earn trust through agreement (the α gate), and the fidelity dimension flows through `score.py` exactly like a crowd dimension. Per this project's learning-through-exercise convention, the scaffolding and fixtures are provided; **you write the two key assertions.**

- [ ] **Step 1: Append the fixtures + scaffold (provided)**

Add to `tools/ablation/tests/test_canon_fidelity.py`:

```python
# A 3-idea key_map: two cells so contrasts() has a pair to compare.
_KEY_MAP = {
    "c1-001": {"engine": "inversion", "source": "background"},
    "c1-002": {"engine": "inversion", "source": "background"},
    "c1-003": {"engine": "straight", "source": "background"},
}


def _fidelity_rows(per_judge_scores):
    """Build fidelity rating rows from {worker_id: {idea_id: value}}.

    Mirrors expandJudgeRows on the JS side: dimension is always 'fidelity'.
    position is set to a distinct slot per (judge, idea) so it stays valid even
    though this test does not exercise position_effect.
    """
    rows = []
    for worker_id, scores in per_judge_scores.items():
        for slot, (idea_id, value) in enumerate(scores.items(), start=1):
            rows.append({
                "worker_id": worker_id,
                "idea_id": idea_id,
                "dimension": "fidelity",
                "value": value,
                "position": slot,
            })
    return rows


# Converging panel: 3 judges agree closely AND ideas vary -> high alpha.
_CONVERGING = _fidelity_rows({
    "llm-judge-1": {"c1-001": 6, "c1-002": 5, "c1-003": 2},
    "llm-judge-2": {"c1-001": 6, "c1-002": 5, "c1-003": 1},
    "llm-judge-3": {"c1-001": 7, "c1-002": 4, "c1-003": 2},
})

# Diverging panel: judges contradict each other per idea -> alpha below floor.
_DIVERGING = _fidelity_rows({
    "llm-judge-1": {"c1-001": 1, "c1-002": 7, "c1-003": 1},
    "llm-judge-2": {"c1-001": 7, "c1-002": 1, "c1-003": 7},
    "llm-judge-3": {"c1-001": 1, "c1-002": 7, "c1-003": 4},
})


def test_fidelity_is_a_drop_in_rater(tmp_path):
    # Converging judges should PASS the gate and yield contrasts; diverging
    # judges should go 'inconclusive' and have contrasts SUPPRESSED.
    pass_gate = score.reliability_gate(_CONVERGING)
    fail_gate = score.reliability_gate(_DIVERGING)
    pass_cells = score.aggregate(_CONVERGING, _KEY_MAP)
    pass_contrast = score.contrasts(pass_cells, "fidelity", pass_gate)
    fail_cells = score.aggregate(_DIVERGING, _KEY_MAP)
    fail_contrast = score.contrasts(fail_cells, "fidelity", fail_gate)

    # TODO(you): assert the core design property. Four assertions:
    #   1. pass_gate["fidelity"]["status"] == "pass"
    #   2. fail_gate["fidelity"]["status"] == "inconclusive"
    #   3. pass_contrast yields a real comparison (status "pass", non-empty "pairs")
    #   4. fail_contrast is suppressed (status "inconclusive"), NOT silently dropped
    # Why this is the key test: it proves a judge earns trust through agreement
    # under the SAME gate the crowd faces. Reference: score.reliability_gate and
    # score.contrasts in tools/ablation/score.py; the alpha floor is 0.667.
    raise AssertionError("TODO(you): write the four core-property assertions")
```

- [ ] **Step 2: Run to confirm it fails on the TODO (not on a fixture/import error)**

Run: `python -m pytest tools/ablation/tests/test_canon_fidelity.py::test_fidelity_is_a_drop_in_rater -v`
Expected: FAIL with `AssertionError: TODO(you): ...` — proving the fixtures, gate, aggregate, and contrasts calls all execute without error, and only the assertions remain.

- [ ] **Step 3: Author writes the four assertions**

Replace the `raise AssertionError(...)` line with the four assertions described in the TODO. Keep them explicit (one `assert` each) so a failure names which half of the property broke.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tools/ablation/tests/test_canon_fidelity.py -v`
Expected: PASS — all four tests green.

- [ ] **Step 5: Run the full ablation suite for no regressions**

Run: `python -m pytest tools/ablation/tests/ -v`
Expected: PASS — existing reliability/collect/build_hits/transfer tests still green.

- [ ] **Step 6: Commit**

```bash
git add tools/ablation/tests/test_canon_fidelity.py
git commit -m "test(ablation): canon-fidelity drop-in-rater gate property"
```

---

### Task 5: Canon doc template

**Files:**
- Create: `docs/ablation/canon-daria.md`

The judge reasons over this doc instead of its own memory — that is the entire point of "with canon in context." The template ships `<you fill>` stubs; **the domain facts are human-authored** (an LLM-drafted canon re-introduces the fuzzy-memory circularity the canon exists to break). Authoring principle: every line must *discriminate* Daria from a generic teen show; when a fact is uncertain, omit it. Frozen per run — a canon edit is a new study condition, not a silent change.

- [ ] **Step 1: Create the template**

Create `docs/ablation/canon-daria.md`:

```markdown
# Canon — Daria

> Ground truth for the canon-fidelity judge. Human-authored. Frozen per run: a
> revision is a NEW study condition, not a silent edit. Target ~1 page.
>
> Authoring principle: every line must DISCRIMINATE Daria from a generic teen
> show. State voice as checkable constraints, not bios. When a fact is
> uncertain, OMIT it rather than commit a false ground truth.

## Characters & voice
<you fill: voice RULES as checkable constraints. e.g. "Daria's humor is dry
understatement, never slapstick; she does not raise her voice." One bullet per
rule, each one a thing an idea can violate.>

## Setting & tone
<you fill: the world and its satirical STANCE — what the show is skeptical of,
how it treats its setting. Not a plot summary.>

## Thematic spine
<you fill: what the show is actually ABOUT. This is the most discriminative
section — the themes a faithful idea must turn on.>

## Canon vs. anti-canon — worked examples
<you fill: minimal pairs. Each row: a canon example, an anti-canon example, and
a one-line WHY naming the principle it turns on. Include at least one TRAP:
surface-plausible (right names/places) but essence-wrong (wrong stance), to
teach that the boundary is stance, not vocabulary.>

| Canon | Anti-canon | Why (principle) |
|---|---|---|
| <you fill> | <you fill> | <you fill> |
| <you fill — trap: surface-right, stance-wrong> | <you fill> | <you fill> |
```

- [ ] **Step 2: Verify it renders and the stubs are obvious**

Run: `grep -c '<you fill' docs/ablation/canon-daria.md`
Expected: `6` (every authored section is stubbed; nothing silently pre-filled).

- [ ] **Step 3: Commit**

```bash
git add docs/ablation/canon-daria.md
git commit -m "docs(ablation): canon-daria template (human-authored stubs)"
```

---

## Deferred verification (out of scope this round, per design §7)

1. **Runtime relative-import resolution. — RESOLVED (2026-06-02, live run).** The workflow
   runtime **rejects static `import` declarations** (it parses `import {` as a dynamic
   `import()` call: `SyntaxError: import call expects one or two arguments`). `node --check`
   passed because that is valid Node ESM, but the runtime is stricter. Fallback applied as
   planned: the four helpers (`djb2`/`fmix32`/`judgeKey`/`hashOrder` + `expandJudgeRows`/
   `buildReport`) are **inlined into `funnel.js`** with a sync comment; `lib/canon-fidelity.js`
   + its 7 tests remain the source of truth. A live `judgePanelN:3` run over a 5-idea rated
   set then passed end-to-end: 15 rows (3×5), per-judge orderings differ, judge discriminated
   (faithful 6.3–7.0, off-canon 1.0) citing canon, and `score.py` gave α=0.984 `pass` + 10
   contrast pairs.
2. **Writer-agent verbatim fidelity. — VERIFIED.** First live run produced exactly N×M = 15
   lines with the correct contract keys; downstream `json.loads` insensitive to reflow.
3. **Judgment quality / gold-set validation.** Deferred entirely (design §7). The live run is
   strong directional evidence (clean stance-based separation) but is not the gold-set study.
4. **`position_effect` pooling.** Fidelity rows carry real positions (1..M); real MTurk crowd rows carry `position == -1` (`score.py:286`). `position_effect` pools all non-attn rows, so a mixed run regresses over both. This is pre-existing analysis behavior, not introduced here; note it for whoever interprets the position regression on a merged ratings set.

---

## Self-Review

**Spec coverage:**
- §5.1 `CANON_FIDELITY_SCHEMA` → Task 2 Step 3. ✓
- §5.2 `canonFidelityPrompt` (full canon verbatim, 1-7 scale anchors, stance-not-vocabulary, surface-tell rationale insufficient, permuted order) → Task 2 Step 4 (`canonFidelityJudgePrompt`). ✓
- §5.3 mode block (distinct config names, N default 5, deterministic permutation, row expansion, two output files, return value) → Task 2 Steps 2 & 5. ✓
- §5.4 canon template (4 sections, traps, ~1 page, human-authored) → Task 5. ✓
- §5.5 merge → Task 3 (`load_ratings_jsonl` + `extend`); confirmed against real `score.py` (no CLI). ✓
- §6 tests: JS (rows, worker_ids, position covers permutation, dimension, schema shape) → Task 1; Python integration (gate pass/inconclusive) → Task 4. ✓
- §4 determinism (`hashOrder`), blinding (reader drops engine/source), position (1-based slot) → Tasks 1 & 2. ✓
- §8 open items resolved in the plan preamble (no `score.py` CLI; djb2 stable sort). ✓
- §2 collision avoided: all config named `canon*`, never reusing `fidelityReportPath`. ✓

**Placeholder scan:** No "TBD/handle edge cases" placeholders. The one intentional `TODO(you)` (Task 4 Step 1) is the deliberate learning-exercise seam, fully specified with the four assertions named — not a plan gap.

**Type consistency:** `hashOrder(ideaIds, judgeIndex)`, `expandJudgeRows(judgeOutputs, orderByJudge)`, `buildReport(judgeOutputs, orderByJudge)`, `load_ratings_jsonl(path)`, row shape `{worker_id, idea_id, dimension, value, position}`, judge output `{ratings:[{idea_id, fidelity, rationale}]}` — used identically across JS module, funnel.js mode block, and Python tests.
```
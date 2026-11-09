# Matched-Input Blocked Ablation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert engine-ablation Phase-1 generation from disjoint-input cells to a blocked design where every input (chain or seed) is run through all four arms {🎲 random-seed, 🔄 inversion, 🔍 lens-shift, ▫ straight}, keyed by an authoritative `block_id`, enabling paired within-block contrasts.

**Architecture:** Generation (`funnel.js`) builds a shared block list per source (20 chains, 20 seeds); one **authoritative** agent call per (block × arm) produces exactly one idea, stamped with a workflow-set `block_id` (never agent-declared — mirrors the existing "workflow sets labels authoritatively" principle at `funnel.js:859-860`). The pure cell-construction logic lives in `workflows/lib/blocked-cells.js` (TDD'd via `node:test`) and is **inlined** into `funnel.js` because the workflow runtime rejects static imports (see commit `4a1aa07`). `build_hits.py` carries `block_id` as a third hidden variable; `score.py` gains a `paired_contrasts` that pairs arms by `block_id` within a source.

**Tech Stack:** JavaScript (workflow runtime + `node:test`), Python 3 (`unittest`, numpy/scipy), MTurk QuestionForm XML.

**Out of scope — hard prerequisite before any paid posting:** The §6.1 **blinding gate still FAILS** (informed classifier 65% vs the ≤35% pass bar; lens-shift/random-seed leak the device through *content*). Matched inputs fix the *input* confound, **not** the blinding confound. Do not post a paid batch until blinding is separately resolved. This plan deliberately does not address it.

---

## Why this change

Today, cell input is assigned by `funnel.js:889-901` with `i++` **per (engine × source) cell**, so each device runs on a *different* input (🎲←chain[0], 🔄←chain[2], 🔍←chain[4]). The device contrast is therefore confounded by input quality. This plan makes the input a **blocking factor**: the same 20 chains (and 20 seeds) feed all four arms, so the only systematic difference within a block is the device.

## Target structure (locked)

| Axis | Value |
|---|---|
| Sources | background (20 chains) + seed (20 wordnet walks) — H2 preserved |
| Blocks | 20 per source, **shared across all 4 arms** |
| Arms | 🎲 random-seed · 🔄 inversion · 🔍 lens-shift · ▫ straight |
| Ideas | exactly 1 per (block × arm) → matched quad keyed by `block_id` |
| Total | 2 × 20 × 4 × 1 = 160 ideas = N=20/cell across 8 cells |
| Analysis | paired/within-block contrasts (§6.4 amended) |

`block_id` convention: `"<source>:<index>"`, e.g. `bg:07`, `seed:13`. The quad for `bg:07` is the four ideas (one per arm) generated from background chain index 7.

---

## Task 0: Precondition — 20 seeds available

**Files:**
- Inspect: `tmp/ablation-phase1/seeds.json` (currently 8 entries)
- Reference: `assets/seeds.json` (sampling source, per `funnel.js:106`)

- [ ] **Step 1: Confirm the shortfall**

Run: `python3 -c "import json; print(len(json.load(open('tmp/ablation-phase1/seeds.json'))))"`
Expected: `8` — fewer than the 20 seed-blocks the design needs.

- [ ] **Step 2: Record the requirement (no code yet)**

The seed source needs **20** distinct wordnet seeds. Generation (Task 3) samples them from `assets/seeds.json`; this step only documents that the regen run (Task 6) must pass `seeds` of length ≥ 20. No commit.

---

## Task 1: Pre-registration Amendment A2 (blocked design + paired analysis)

**Files:**
- Modify: `docs/ablation/preregistration.md` (§0 Amendments; §2 Arms; §6.4 Contrasts)

This is a **pre-data** amendment (no paid/human ratings collected yet — see `phase1-brick-findings.md` status line), so it legitimately amends the binding spec.

- [ ] **Step 1: Add Amendment A2 under §0**

Insert after the A1 block (after the line `docs/ablation/phase1-brick-findings.md`, before the `---` that closes §0):

```markdown
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
```

- [ ] **Step 2: Add the blocking note to §2 (Arms and Cells)**

After the table in §2 (after the line beginning "Cells 7 and 8 are the null baseline"), add:

```markdown
**Blocking (Amendment A2).** Within each source, all four arms share the same 20
inputs (blocks). The 8 cells are unchanged; what changes is that cell membership is
now *matched* by `block_id` across arms, so each background block yields a quad
{random-seed, inversion, lens-shift, straight} from one chain (and likewise for seed).
```

- [ ] **Step 3: Amend §6.4 to paired contrasts**

Replace the §6.4 body (the paragraph beginning "For every (cell_a, cell_b) pair") with:

```markdown
For every (arm_a, arm_b) pair on each gate-passing dimension, contrasts are computed
**paired within block**: for each `block_id` present in both arms (same source), take
the per-block mean-rating difference, then report the paired effect size (paired
Hedges' g over the within-block differences) and a paired bootstrap 95% CI (2000
resamples, seed 0). Cross-source arm pairs are not paired (no shared blocks) and are
reported, if at all, as unpaired with that limitation stated. Contrasts for
inconclusive dimensions are not computed and are not reported as if they had been.
```

- [ ] **Step 4: Commit**

```bash
git add docs/ablation/preregistration.md
git commit -m "docs(ablation): Amendment A2 — blocked matched-input design + paired contrasts"
```

---

## Task 2: Pure block-assignment logic (`workflows/lib/blocked-cells.js`)

**Files:**
- Create: `workflows/lib/blocked-cells.js`
- Test: `workflows/lib/blocked-cells.test.js`

This pure function produces the 160 cell descriptors (no agent calls). It is the canonical, tested source; Task 3 inlines a copy into `funnel.js` (runtime rejects imports).

- [ ] **Step 1: Write the failing test**

Create `workflows/lib/blocked-cells.test.js`:

```javascript
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildBlockedCells } from './blocked-cells.js'

const ARMS = [
  { key: 'random-seed', glyph: '🎲' },
  { key: 'inversion', glyph: '🔄' },
  { key: 'lens-shift', glyph: '🔍' },
  { key: 'straight', glyph: '▫' },
]
const CHAINS = Array.from({ length: 20 }, (_, i) => ({ nodes: [{ concept: `c${i}`, variance: 0.1 }] }))
const SEEDS = Array.from({ length: 20 }, (_, i) => ({ mode: 'noun', word: `w${i}` }))
const PERSONAS = ['p0', 'p1', 'p2']

test('produces sources × blocks × arms cells', () => {
  const cells = buildBlockedCells({ backgroundBlocks: CHAINS, seedBlocks: SEEDS, arms: ARMS, personas: PERSONAS, topic: 'brick' })
  assert.equal(cells.length, 2 * 20 * 4)
})

test('every block_id is shared across all four arms', () => {
  const cells = buildBlockedCells({ backgroundBlocks: CHAINS, seedBlocks: SEEDS, arms: ARMS, personas: PERSONAS, topic: 'brick' })
  const byBlock = new Map()
  for (const c of cells) {
    if (!byBlock.has(c.blockId)) byBlock.set(c.blockId, new Set())
    byBlock.get(c.blockId).add(c.engineKey)
  }
  assert.equal(byBlock.size, 40) // 20 bg + 20 seed
  for (const arms of byBlock.values()) {
    assert.deepEqual([...arms].sort(), ['inversion', 'lens-shift', 'random-seed', 'straight'])
  }
})

test('block_id format is <source>:<zero-padded-index>', () => {
  const cells = buildBlockedCells({ backgroundBlocks: CHAINS, seedBlocks: SEEDS, arms: ARMS, personas: PERSONAS, topic: 'brick' })
  assert.ok(cells.some((c) => c.blockId === 'bg:00'))
  assert.ok(cells.some((c) => c.blockId === 'seed:19'))
})

test('background cells carry the chain; seed cells carry the seed', () => {
  const cells = buildBlockedCells({ backgroundBlocks: CHAINS, seedBlocks: SEEDS, arms: ARMS, personas: PERSONAS, topic: 'brick' })
  const bg = cells.find((c) => c.blockId === 'bg:03' && c.engineKey === 'inversion')
  assert.equal(bg.source, 'background')
  assert.equal(bg.chain, CHAINS[3])
  assert.equal(bg.seed, null)
  const sd = cells.find((c) => c.blockId === 'seed:03' && c.engineKey === 'inversion')
  assert.equal(sd.source, 'seed')
  assert.equal(sd.seed, SEEDS[3])
  assert.equal(sd.chain, null)
})

test('random-seed always gets a seed even in the background source', () => {
  const cells = buildBlockedCells({ backgroundBlocks: CHAINS, seedBlocks: SEEDS, arms: ARMS, personas: PERSONAS, topic: 'brick' })
  const rs = cells.find((c) => c.blockId === 'bg:05' && c.engineKey === 'random-seed')
  assert.ok(rs.seed, 'random-seed needs a seed for its device even when blocking on a chain')
})

test('persona assigned only to lens-shift cells, deterministically', () => {
  const cells = buildBlockedCells({ backgroundBlocks: CHAINS, seedBlocks: SEEDS, arms: ARMS, personas: PERSONAS, topic: 'brick' })
  for (const c of cells) {
    if (c.engineKey === 'lens-shift') assert.ok(c.persona)
    else assert.equal(c.persona, null)
  }
  const a = buildBlockedCells({ backgroundBlocks: CHAINS, seedBlocks: SEEDS, arms: ARMS, personas: PERSONAS, topic: 'brick' })
  const b = buildBlockedCells({ backgroundBlocks: CHAINS, seedBlocks: SEEDS, arms: ARMS, personas: PERSONAS, topic: 'brick' })
  assert.deepEqual(a.map((c) => c.persona), b.map((c) => c.persona))
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test workflows/lib/blocked-cells.test.js`
Expected: FAIL — `Cannot find module './blocked-cells.js'`.

- [ ] **Step 3: Implement `buildBlockedCells`**

Create `workflows/lib/blocked-cells.js`:

```javascript
// Pure cell-construction for the blocked/matched-input ablation design.
// Each input (chain or seed) is a block run through every arm; block_id ties the
// matched quad together. NO agent calls here — the workflow wraps each cell with
// cellTask(). This file is the tested source of truth; funnel.js inlines a copy
// because the workflow runtime rejects static imports (commit 4a1aa07).

function pad2(n) {
  return String(n).padStart(2, '0')
}

// random-seed needs a seed for its device on EVERY block (even background blocks).
// Seed blocks already are seeds; background blocks borrow a seed by index.
function seedForCell(engineKey, source, seedBlocks, index) {
  if (source === 'seed') return seedBlocks[index]
  if (engineKey === 'random-seed') {
    return seedBlocks.length ? seedBlocks[index % seedBlocks.length] : { mode: 'noun', word: 'unexpected object' }
  }
  return null
}

export function buildBlockedCells({ backgroundBlocks, seedBlocks, arms, personas, topic }) {
  const cells = []
  const plan = [
    { source: 'background', blocks: backgroundBlocks, prefix: 'bg' },
    { source: 'seed', blocks: seedBlocks, prefix: 'seed' },
  ]
  let personaCursor = 0
  for (const { source, blocks, prefix } of plan) {
    blocks.forEach((block, index) => {
      const blockId = `${prefix}:${pad2(index)}`
      for (const arm of arms) {
        const persona =
          arm.key === 'lens-shift' && personas.length
            ? personas[personaCursor++ % personas.length]
            : null
        cells.push({
          target: { id: null, text: topic },
          engineKey: arm.key,
          glyph: arm.glyph,
          source,
          blockId,
          chain: source === 'background' ? block : null,
          seed: seedForCell(arm.key, source, seedBlocks, index),
          persona,
        })
      }
    })
  }
  return cells
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test workflows/lib/blocked-cells.test.js`
Expected: PASS — all 6 tests green.

- [ ] **Step 5: Commit**

```bash
git add workflows/lib/blocked-cells.js workflows/lib/blocked-cells.test.js
git commit -m "feat(ablation): pure blocked-cell builder (matched inputs across arms)"
```

---

## Task 3: Wire blocked generation into `funnel.js`

**Files:**
- Modify: `workflows/funnel.js` (inline the builder; rewrite the cycle-1 cell block at `:887-904`; stamp `block_id` in `cellTask` at `:861-880`; single-idea diverge)

The workflow runtime rejects static imports, so the `buildBlockedCells` body from Task 2 is **inlined** verbatim. The `node:test` in Task 2 guards the canonical copy; keep them identical.

- [ ] **Step 1: Inline the helper**

Immediately before `const ENGINES = [` (currently `funnel.js:458`), paste the three functions from `workflows/lib/blocked-cells.js` (`pad2`, `seedForCell`, `buildBlockedCells`) **without** the `export` keyword on `buildBlockedCells`:

```javascript
// --- inlined from workflows/lib/blocked-cells.js (runtime rejects imports; keep in sync) ---
function pad2(n) { return String(n).padStart(2, '0') }
function seedForCell(engineKey, source, seedBlocks, index) {
  if (source === 'seed') return seedBlocks[index]
  if (engineKey === 'random-seed') {
    return seedBlocks.length ? seedBlocks[index % seedBlocks.length] : { mode: 'noun', word: 'unexpected object' }
  }
  return null
}
function buildBlockedCells({ backgroundBlocks, seedBlocks, arms, personas, topic }) {
  const cells = []
  const plan = [
    { source: 'background', blocks: backgroundBlocks, prefix: 'bg' },
    { source: 'seed', blocks: seedBlocks, prefix: 'seed' },
  ]
  let personaCursor = 0
  for (const { source, blocks, prefix } of plan) {
    blocks.forEach((block, index) => {
      const blockId = `${prefix}:${pad2(index)}`
      for (const arm of arms) {
        const persona = arm.key === 'lens-shift' && personas.length ? personas[personaCursor++ % personas.length] : null
        cells.push({
          target: { id: null, text: topic },
          engineKey: arm.key, glyph: arm.glyph, source, blockId,
          chain: source === 'background' ? block : null,
          seed: seedForCell(arm.key, source, seedBlocks, index),
          persona,
        })
      }
    })
  }
  return cells
}
// --- end inlined block ---
```

- [ ] **Step 2: Stamp `block_id` authoritatively in `cellTask`**

In `cellTask` (`funnel.js:861-880`), add `block_id` to the stamped idea record. Change the `.map((idea) => ({ ... }))` object to include it, and take **only the first idea** (single-idea-per-block):

```javascript
    }).then((r) => {
      const ideas = r?.ideas || []
      const first = ideas.length ? [ideas[0]] : []
      return first.map((idea) => ({
        text: idea.text,
        engine: cell.engineKey,
        source: cell.source,
        block_id: cell.blockId,
        parent: cell.target.id,
        parents: [],
        seed: seedField,
      }))
    })
```

- [ ] **Step 3: Request exactly one idea in the diverge prompt**

In `divergePrompt(cell)` (`funnel.js:533`), append a single-idea instruction to the assembled lines (the array passed to `.join`). Add this line to the array, before `divergeBriefBlock()`:

```javascript
    'Produce EXACTLY ONE idea — your single strongest divergent idea for this input. Return it as the only element of `ideas`.',
```

- [ ] **Step 4: Replace the cycle-1 cell construction**

Replace the `if (!beam.length) { ... }` block at `funnel.js:887-904` with:

```javascript
  if (!beam.length) {
    const arms = ENGINES.map((e) => ({ key: e.key, glyph: e.glyph }))
    const backgroundBlocks = cycle1Sources.includes('background') ? domainChains.slice(0, 20) : []
    const seedBlocks = cycle1Sources.includes('seed') ? seeds.slice(0, 20) : []
    if (backgroundBlocks.length && backgroundBlocks.length < 20) {
      throw new Error(`blocked design needs 20 background chains, got ${backgroundBlocks.length}`)
    }
    if (seedBlocks.length && seedBlocks.length < 20) {
      throw new Error(`blocked design needs 20 seeds, got ${seedBlocks.length}`)
    }
    const cells = buildBlockedCells({ backgroundBlocks, seedBlocks, arms, personas: personasArg || PERSONAS, topic })
    divergeTasks = cells.map(cellTask)
  } else {
```

(Leave the `else` branch — cycle ≥2 beam logic — unchanged.)

- [ ] **Step 5: Verify the canonical and inlined copies match**

Run: `node --test workflows/lib/blocked-cells.test.js`
Expected: PASS (guards the canonical copy). Then visually diff the inlined `buildBlockedCells` body against `workflows/lib/blocked-cells.js` — they must be identical except the `export` keyword.

- [ ] **Step 6: Commit**

```bash
git add workflows/funnel.js
git commit -m "feat(ablation): blocked cycle-1 generation — one idea per block×arm, authoritative block_id"
```

---

## Task 4: Carry `block_id` through `build_hits.build_key_map`

**Files:**
- Modify: `tools/ablation/build_hits.py:83-93` (`build_key_map`)
- Test: `tools/ablation/tests/test_build_hits.py`

`block_id` is a hidden variable (like engine/source) — it must reach the key_map but **never** the rater-visible payload.

- [ ] **Step 1: Write the failing test**

Add to `tools/ablation/tests/test_build_hits.py` (inside the key-map test class, or as a new test near `test_key_map_holds_hidden_vars_only`):

```python
def test_key_map_includes_block_id(self):
    ideas = [
        {"id": "c1-001", "engine": "random-seed", "source": "background",
         "block_id": "bg:00", "text": "..."},
        {"id": "c1-002", "engine": "straight", "source": "seed",
         "block_id": "seed:00", "text": "..."},
    ]
    km = bh.build_key_map(ideas)
    self.assertEqual(km["c1-001"]["block_id"], "bg:00")
    self.assertEqual(km["c1-002"]["block_id"], "seed:00")
    # still no rater-visible field leaked
    self.assertNotIn("text", km["c1-001"])
```

(If the test module imports the module under a name other than `bh`, match the existing import alias.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tools.ablation.tests.test_build_hits -v 2>&1 | grep block_id`
Expected: FAIL — `KeyError: 'block_id'`.

- [ ] **Step 3: Implement**

In `tools/ablation/build_hits.py`, change `build_key_map` (`:83-93`) to include `block_id`:

```python
    return {
        idea["id"]: {
            "engine": idea["engine"],
            "source": idea["source"],
            "block_id": idea.get("block_id"),
        }
        for idea in ideas
    }
```

(`.get` keeps it tolerant of older corpora that predate block_id.)

- [ ] **Step 4: Run the full module to verify pass + no regressions**

Run: `python -m unittest tools.ablation.tests.test_build_hits -v`
Expected: PASS — the new test plus all prior tests (18 total).

- [ ] **Step 5: Commit**

```bash
git add tools/ablation/build_hits.py tools/ablation/tests/test_build_hits.py
git commit -m "feat(ablation): key_map carries hidden block_id for paired scoring"
```

---

## Task 5: Paired contrasts in `score.py`

**Files:**
- Modify: `tools/ablation/score.py` (add `paired_contrasts`; wire into `report`)
- Test: `tools/ablation/tests/test_score.py` (create if absent)

Pairs two arms by shared `block_id` within a source, takes per-(block, arm) mean ratings, computes paired Hedges' g over the within-block differences plus a paired bootstrap CI. `aggregate`/`reliability_gate`/`cell_means` are unchanged.

- [ ] **Step 1: Write the failing test**

Create or append to `tools/ablation/tests/test_score.py`:

```python
import unittest
from tools.ablation import score


def _ratings(block, engine, source, dim, vals):
    return [{"idea_id": f"{engine}-{block}", "worker_id": f"w{i}",
             "dimension": dim, "value": v, "engine": engine,
             "source": source, "block_id": block}
            for i, v in enumerate(vals)]


class TestPairedContrasts(unittest.TestCase):
    def test_pairs_within_block_and_signs_difference(self):
        # arm A beats arm B by +2 on every shared block -> positive paired effect
        ratings = []
        for b in ("bg:00", "bg:01", "bg:02"):
            ratings += _ratings(b, "inversion", "background", "originality", [5, 5, 5])
            ratings += _ratings(b, "straight", "background", "originality", [3, 3, 3])
        key_map = {r["idea_id"]: {"engine": r["engine"], "source": r["source"],
                                  "block_id": r["block_id"]} for r in ratings}
        out = score.paired_contrasts(ratings, key_map, "originality",
                                     arm_a="inversion", arm_b="straight", source="background")
        self.assertEqual(out["n_blocks"], 3)
        self.assertGreater(out["mean_diff"], 0)        # A > B
        self.assertGreater(out["hedges_g"], 0)

    def test_only_shared_blocks_are_paired(self):
        ratings = _ratings("bg:00", "inversion", "background", "originality", [5])
        ratings += _ratings("bg:00", "straight", "background", "originality", [3])
        ratings += _ratings("bg:01", "inversion", "background", "originality", [9])  # unmatched
        key_map = {r["idea_id"]: {"engine": r["engine"], "source": r["source"],
                                  "block_id": r["block_id"]} for r in ratings}
        out = score.paired_contrasts(ratings, key_map, "originality",
                                     arm_a="inversion", arm_b="straight", source="background")
        self.assertEqual(out["n_blocks"], 1)            # bg:01 dropped (no straight)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tools.ablation.tests.test_score -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'paired_contrasts'`.

- [ ] **Step 3: Implement `paired_contrasts`**

Add to `tools/ablation/score.py` (near `contrasts`, reusing `_RNG_SEED` and numpy already imported as `np`):

```python
def paired_contrasts(ratings, key_map, dimension, arm_a, arm_b, source,
                     n_boot=2000, seed=_RNG_SEED):
    """Paired within-block contrast of two arms on one dimension/source.

    Pairs arm_a vs arm_b by shared block_id (same source); the unit is the
    per-(block, arm) mean rating. Returns {n_blocks, mean_diff, hedges_g,
    ci_low, ci_high}. Blocks present for only one arm are dropped.
    """
    # block_id -> arm -> [values]
    cell = {}
    for r in ratings:
        if r.get("dimension") != dimension:
            continue
        meta = key_map.get(r["idea_id"], {})
        if meta.get("source") != source:
            continue
        eng = meta.get("engine")
        if eng not in (arm_a, arm_b):
            continue
        bid = meta.get("block_id")
        cell.setdefault(bid, {}).setdefault(eng, []).append(float(r["value"]))

    diffs = []
    for bid, arms in cell.items():
        if arm_a in arms and arm_b in arms:
            diffs.append(np.mean(arms[arm_a]) - np.mean(arms[arm_b]))
    diffs = np.array(diffs, dtype=float)
    if diffs.size == 0:
        return {"n_blocks": 0, "mean_diff": None, "hedges_g": None,
                "ci_low": None, "ci_high": None}

    mean_diff = float(diffs.mean())
    sd = diffs.std(ddof=1) if diffs.size > 1 else 0.0
    n = diffs.size
    # Paired Hedges' g = mean(diff)/sd(diff), with small-sample J correction.
    if sd > 0:
        g = mean_diff / sd
        J = 1.0 - (3.0 / (4.0 * (n - 1) - 1)) if n > 1 else 1.0
        g *= J
    else:
        g = 0.0
    rng = np.random.default_rng(seed)
    boots = np.array([rng.choice(diffs, size=n, replace=True).mean()
                      for _ in range(n_boot)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"n_blocks": int(n), "mean_diff": mean_diff, "hedges_g": float(g),
            "ci_low": float(lo), "ci_high": float(hi)}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tools.ablation.tests.test_score -v`
Expected: PASS — both paired-contrast tests green.

- [ ] **Step 5: Wire paired contrasts into `report` (gate-respecting)**

In `score.report` (`score.py:301+`), for each **gate-passing** dimension, additionally emit paired contrasts for every arm pair within each source. After the existing `all_contrasts` loop, add:

```python
    arms = ["random-seed", "inversion", "lens-shift", "straight"]
    paired = {}
    for dim, gate in self_gate_items(gate):          # iterate passing dims only
        if gate.get("status") != "pass":
            continue
        paired[dim] = []
        for source in ("background", "seed"):
            for ia in range(len(arms)):
                for ib in range(ia + 1, len(arms)):
                    pc = paired_contrasts(ratings, key_map, dim,
                                          arms[ia], arms[ib], source)
                    if pc["n_blocks"] > 0:
                        paired[dim].append({"source": source, "arm_a": arms[ia],
                                            "arm_b": arms[ib], **pc})
    # include in the emitted report structure
```

Replace `self_gate_items(gate)` with the actual gate iteration already used in `report` (match the existing variable holding per-dimension gate status — read `score.py:301-340` and reuse it; do not introduce a new helper). Add `"paired_contrasts": paired` to the report dict that `report` writes/returns.

- [ ] **Step 6: Run the full ablation test suite**

Run: `python -m unittest discover -s tools/ablation/tests -v`
Expected: PASS — all modules (build_hits, collect, reliability, transfer, score, canon_fidelity).

- [ ] **Step 7: Commit**

```bash
git add tools/ablation/score.py tools/ablation/tests/test_score.py
git commit -m "feat(ablation): paired within-block contrasts (Amendment A2 §6.4)"
```

---

## Task 6: Integration — regenerate corpus, rebuild HITs, verify matched structure

**Files:**
- Produce: `tmp/ablation-phase1/corpus.jsonl`, `rated-set.jsonl`, `hits/*` (all gitignored)

- [ ] **Step 1: Regenerate the blocked corpus**

Run the funnel in cycle mode with `includeStraight:true`, 20 background chains (reuse `tmp/ablation-phase1/domain-model.json`'s `domainChains`) and 20 sampled seeds, on topic "novel uses for a brick". (Exact invocation per the project's funnel-run convention; pass `seeds` of length 20 and `domainChains` of length 20.)
Expected: 160 ideas, each carrying `engine`, `source`, and `block_id`.

- [ ] **Step 2: Assert the matched structure**

Run:
```bash
python3 - <<'PY'
import json, collections
rows=[json.loads(l) for l in open('tmp/ablation-phase1/corpus.jsonl')]
cells=collections.Counter((r['engine'],r['source']) for r in rows)
blocks=collections.defaultdict(set)
for r in rows: blocks[r['block_id']].add(r['engine'])
print("ideas:", len(rows))
print("cells (want 8×20):", dict(cells))
print("blocks (want 40):", len(blocks))
bad=[b for b,a in blocks.items() if len(a)!=4]
print("blocks NOT covering 4 arms:", bad or "none")
PY
```
Expected: 160 ideas; 8 cells × 20; 40 blocks; every block covers all 4 arms.

- [ ] **Step 3: Run prep-ablation (fidelity judge + voice-normalization) and trim to N=20/cell**

Run the existing `prep-ablation` path on the regenerated corpus. **Assert per-cell valid count == 20** after fidelity drops (regenerate to refill if short). Confirm `block_id` survives normalization (it is metadata, not text).

- [ ] **Step 4: Rebuild HITs with attention checks (Step 1 deliverable, now on the blocked corpus)**

Run:
```bash
rm -f tmp/ablation-phase1/hits/hit_*.xml tmp/ablation-phase1/hits/keys.json tmp/ablation-phase1/hits/attention-key.json
python -m tools.ablation.build_hits tmp/ablation-phase1/rated-set.jsonl \
  --raters 5 --ideas-per-hit 12 --seed 42 \
  --dimensions originality value \
  --attention-pool tmp/ablation-phase1/attention-pool.json \
  --out-dir tmp/ablation-phase1/hits
```
Expected: 14 HITs + `keys.json` + `attention-key.json`.

- [ ] **Step 5: Verify the rebuilt HITs (blinding mechanics + block_id hidden)**

Run:
```bash
python3 - <<'PY'
import json, glob, re
import xml.etree.ElementTree as ET
import tools.ablation.build_hits as bh
NS="{%s}"%bh._MTURK_NS
km=json.load(open('tmp/ablation-phase1/hits/keys.json'))
print("key_map carries block_id:", all('block_id' in v for v in km.values()))
for h in glob.glob('tmp/ablation-phase1/hits/hit_*.xml'):
    raw=open(h,encoding='utf-8').read()
    for el in ET.parse(h).getroot().iter(f"{NS}QuestionIdentifier"):
        assert not re.search(r"bg:|seed:|engine|block", el.text or ""), (h, el.text)
print("no block_id/engine leaked into HIT identifiers: OK")
PY
```
Expected: `key_map carries block_id: True` and `no ... leaked ... OK`.

- [ ] **Step 6: Final note — do NOT post**

The HITs are mechanically ready and now matched-input. **Posting remains blocked** on the §6.1 blinding failure (out of scope here). Surface that to the user before any `post_hits.py` run.

---

## Self-Review

**Spec coverage:**
- Blocked design (inputs shared across arms) → Task 2 (`buildBlockedCells`) + Task 3 (funnel wiring).
- `block_id` authoritative, workflow-set → Task 3 Step 2 (stamped in `cellTask`, not agent-declared).
- One idea per (block × arm) → Task 3 Steps 2–3 (take `ideas[0]`, prompt asks for exactly one).
- H2 / source axis preserved → Task 2 `plan` covers both background and seed.
- `block_id` reaches scoring → Task 4 (key_map) + Task 5 (paired_contrasts consumes it).
- Paired §6.4 → Task 1 Step 3 (prereg) + Task 5 (implementation).
- N=20/cell, 8 cells → Task 6 Step 2/3 asserts.
- Blinding still open → stated in header + Task 6 Step 6.

**Placeholder scan:** Task 5 Step 5 intentionally defers the exact gate-iteration variable to the engineer reading `score.py:301-340` — flagged explicitly, not a hidden TODO; the surrounding code is complete. No other placeholders.

**Type consistency:** `block_id` string `"<source>:<index>"` used uniformly across generation (`cell.blockId` → idea `block_id`), key_map (`block_id`), and `paired_contrasts` (`meta.get("block_id")`). `buildBlockedCells` signature `{backgroundBlocks, seedBlocks, arms, personas, topic}` matches between Task 2 test, Task 2 impl, and Task 3 inline + call site.

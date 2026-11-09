# Diverge Engine Matrix (Part A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the funnel dispatch all diverge engines (🎲 random-seed, 🔄 inversion, 🔍 lens-shift) in parallel as a matrix over two sources (BACKGROUND, SEED) in cycle 1, and add ✦ mashup (crossover) at cycle ≥2 — with engine/source recorded as structured corpus fields.

**Architecture:** An `ENGINES` table drives cycle-1 task construction (engines × sources). `divergePrompt` gains an engine-specific instruction fragment. Cycle ≥2 runs one agent per beam idea with engines assigned round-robin, plus a mashup agent that selects its own parents from the beam. The REDUCE agent (which owns the corpus write) is told to persist new `engine`/`source`/`parents` fields. The immutable idea `id` (`c{cycle}-NNN`) is the join key Part B will use.

**Tech Stack:** JavaScript workflow script (sandboxed: no fs/network/`Math.random`/`Date.now` in the script — spawned agents have full tools; runtime globals `agent`/`parallel`/`phase`/`log`/`args`). No JS test runner.

**Reference spec:** `docs/specs/2026-06-02-diverge-engine-matrix-and-ablation-design.md` (rev. 2). This plan is **Part A only**; Part B (the ablation harness, incl. the engine-fidelity judge) is a separate plan written after Part A is verified.

**Scope note (Part A excludes):** the engine-fidelity LLM-judge, MTurk, and scoring — all Part B. Part A's verification of "engines fired correctly" is a manual dry-run spot-check.

**Testing model:** `node --check` per commit; pure deterministic logic (engine/source/persona index assignment, round-robin cycle-≥2 mapping) extracted and exercised by a throwaway standalone `node` assertion script; behavioral verification via a Workflow dry-run (token-expensive funnel run — gated on user go-ahead, batched at the end).

---

## File structure

Only `workflows/funnel.js` changes. New/changed units, all in that file:

| Unit | Responsibility |
|------|----------------|
| `ENGINES` constant | the engine catalog: key, glyph, allowed sources, instruction builder |
| `PERSONAS` constant | uninhibited personas for 🔍 (deterministic index assignment) |
| `engineInstruction(engineKey, seed, persona)` | the per-engine device fragment appended to the diverge prompt |
| `divergePrompt(cell)` | refactored to take a `cell` object and append the engine fragment |
| `buildCycle1Tasks()` / `buildCycleNTasks()` | construct `divergeTasks` for cycle 1 (engines×sources) vs cycle ≥2 (per-beam, round-robin) |
| `MASHUP_SCHEMA`, `mashupPrompt(beam)` | ✦ crossover at cycle ≥2 |
| `reducePrompt` corpus-field edit | persist `engine`/`source`/`parents` |

---

## Task 1: ENGINES + PERSONAS catalog and config

**Files:** Modify `workflows/funnel.js` (config block near top; a new catalog block after the seed helpers, e.g. after `seedInstruction`).

- [ ] **Step 1: Add config fields**

After the existing config line `const invariants = cfg.invariants ?? []`, add:

```js
const personasArg = cfg.personas ?? null // optional override list of personas for 🔍 cells
const cycle1Sources = cfg.cycle1Sources ?? ['background', 'seed'] // sources crossed with engines in cycle 1
const enableMashup = cfg.enableMashup ?? true // ✦ crossover runs at cycle >= 2
```

- [ ] **Step 2: Add the PERSONAS constant**

After `seedInstruction` (the function ending around the `LATERAL NOUN` return), add:

```js
// Uninhibited / unconventional personas for the 🔍 lens-shift engine. The
// Creative Stereotype Effect: an uninhibited persona raises divergent originality.
// Deterministic index assignment (the workflow cannot randomize).
const PERSONAS = [
  'a con artist running a long grift',
  'a feral toddler with no sense of consequence',
  'an 1850s telegraph operator',
  'a deep-sea marine biologist',
  'a doomsday cult leader',
  'a burned-out tabloid editor',
  'a medieval court jester',
  'a conspiracy-theorist night-shift trucker',
]
```

- [ ] **Step 3: Add the ENGINES catalog**

Immediately after `PERSONAS`, add:

```js
// The diverge engines (devices). 🎲 random-seed is a real engine (the strongest
// anti-convergence device), NOT "straight" generation. Each engine declares the
// sources it can run on; cycle 1 crosses engines × sources.
const ENGINES = [
  { key: 'random-seed', glyph: '🎲', sources: ['background', 'seed'] },
  { key: 'inversion', glyph: '🔄', sources: ['background', 'seed'] },
  { key: 'lens-shift', glyph: '🔍', sources: ['background', 'seed'] },
]
```

- [ ] **Step 4: Syntax check + commit**

Run: `node --check workflows/funnel.js` → expect exit 0.
```bash
git add workflows/funnel.js
git commit -m "feat(engines): add ENGINES + PERSONAS catalog and config"
```

---

## Task 2: `engineInstruction` — the per-engine device fragment

**Files:** Modify `workflows/funnel.js` (after `chainBlock`).

- [ ] **Step 1: Add the function**

After `chainBlock`, add:

```js
// The device instruction for a cell's engine. random-seed reuses the existing
// seedInstruction; inversion and lens-shift add their own forcing function.
// persona is supplied (deterministically) only for lens-shift cells.
function engineInstruction(engineKey, seed, persona) {
  if (engineKey === 'inversion') {
    return [
      `Engine — BAD-IDEA / INVERSION: first generate the WORST possible version of`,
      `each idea (or invert the goal: "how would we guarantee total failure?"), then`,
      `FLIP it into a real, usable idea. The flip is the idea you keep.`,
    ].join('\n')
  }
  if (engineKey === 'lens-shift') {
    return [
      `Engine — LENS-SHIFT: re-attack the topic entirely as ${persona}. Let that`,
      `perspective force a structurally different idea, not just different words.`,
    ].join('\n')
  }
  // random-seed (default): route through the seed noun.
  return seedInstruction(seed)
}
```

- [ ] **Step 2: Syntax check + commit**

Run: `node --check workflows/funnel.js` → exit 0.
```bash
git add workflows/funnel.js
git commit -m "feat(engines): engineInstruction device fragment per engine"
```

---

## Task 3: Refactor `divergePrompt` to take a `cell`

**Files:** Modify `workflows/funnel.js` (`divergePrompt`).

A `cell` is `{ target, engineKey, source, seed, chain, persona }`. The prompt appends the engine fragment; it includes the chain block only for `source: 'background'` (and 🎲-on-background, which carries both), and the seed instruction is folded into `engineInstruction` for random-seed (other engines still get the seed noun available via their own fragment only if needed — inversion/lens-shift do NOT route through the seed).

- [ ] **Step 1: Replace `divergePrompt`**

Replace the entire `function divergePrompt(target, seed, chain) { ... }` with:

```js
function divergePrompt(cell) {
  const branchLine = cell.target.id
    ? `Diverge specifically FROM this surviving branch (id ${cell.target.id}): "${cell.target.text}". Push it in new directions; do not just restate it.`
    : `Diverge on the topic at large.`
  const chainFragment = cell.source === 'background' ? chainBlock(cell.chain) : ''
  return [
    `You are the DIVERGE stage of an idea funnel. Read ${pluginRoot}/skills/spitballing/SKILL.md`,
    `for the engine definitions and the anti-convergence rules, then operate in BATCH mode`,
    `(generate everything at once; do NOT wait for nudges).`,
    ``,
    `Topic: ${topic}`,
    branchLine,
    ``,
    engineInstruction(cell.engineKey, cell.seed, cell.persona),
    chainFragment,
    divergeBriefBlock(),
    `Generate exactly ${perAgent} punchy one-liner ideas, structurally varied (not the same`,
    `idea reworded).`,
    ``,
    `Return JSON only: {"ideas":[{"text":"..."}, ...]}. Do not write any files.`,
  ].join('\n')
}
```

(Note: the returned-idea shape drops the agent-set `engine` field — the workflow now sets `engine` authoritatively from the cell, see Task 4. The `DIVERGE_SCHEMA`'s optional `engine` property can remain; it is simply ignored.)

- [ ] **Step 2: Syntax check + commit**

Run: `node --check workflows/funnel.js` → exit 0.
```bash
git add workflows/funnel.js
git commit -m "refactor(engines): divergePrompt takes a cell with an engine"
```

---

## Task 4: Cycle-1 task builder (engines × sources)

**Files:** Modify `workflows/funnel.js` (the `// ---- one cycle` section: the `targets`/`divergeTasks` block).

- [ ] **Step 1: Add a cell→task helper**

Just above the `// ---- one cycle` comment, add:

```js
// Build one diverge task from a fully-specified cell. The workflow sets engine
// and source authoritatively (not the agent) so the corpus label is trustworthy.
function cellTask(cell) {
  const sl = cell.seed ? seedLabel(cell.seed) : null
  const leafNode = cell.chain && cell.chain.nodes.length ? splitChain(cell.chain.nodes).leaf : null
  const seedField = [leafNode, sl].filter(Boolean).join(' × ') || null
  return () =>
    agent(divergePrompt(cell), {
      schema: DIVERGE_SCHEMA,
      label: `diverge:${cell.glyph}:${cell.source}`,
      phase: 'Diverge',
    }).then((r) =>
      (r?.ideas || []).map((idea) => ({
        text: idea.text,
        engine: cell.engineKey,
        source: cell.source,
        parent: cell.target.id,
        parents: [],
        seed: seedField,
      })),
    )
}
```

- [ ] **Step 2: Replace the `targets`/`divergeTasks` block with the cycle fork**

Replace from `const targets = beam.length ? beam : ...` through the end of the `const divergeTasks = targets.map(...)` block with:

```js
// Cycle 1: cross every engine with every configured source (no straight cell).
// Cycle >= 2: one agent per surviving beam idea, engines assigned round-robin.
let divergeTasks
if (!beam.length) {
  const cells = []
  let i = 0
  ENGINES.forEach((eng) => {
    eng.sources.forEach((source) => {
      if (!cycle1Sources.includes(source)) {
        return
      }
      const seed = source === 'seed' || eng.key === 'random-seed'
        ? (seeds.length ? seeds[i % seeds.length] : { mode: 'noun', word: 'unexpected object' })
        : null
      const chain = source === 'background' && domainChains.length ? domainChains[i % domainChains.length] : null
      const persona = eng.key === 'lens-shift' ? (personasArg || PERSONAS)[i % (personasArg || PERSONAS).length] : null
      cells.push({ target: { id: null, text: topic }, engineKey: eng.key, glyph: eng.glyph, source, seed, chain, persona })
      i++
    })
  })
  divergeTasks = cells.map(cellTask)
} else {
  divergeTasks = beam.map((target, i) => {
    const eng = ENGINES[i % ENGINES.length]
    const seed = seeds.length ? seeds[i % seeds.length] : { mode: 'noun', word: 'unexpected object' }
    const persona = eng.key === 'lens-shift' ? (personasArg || PERSONAS)[i % (personasArg || PERSONAS).length] : null
    return cellTask({ target, engineKey: eng.key, glyph: eng.glyph, source: 'beam', seed, chain: null, persona })
  })
}
```

(The cycle-1 `seed` rule: SEED-source cells always get a seed; 🎲-on-background also gets one — `eng.key === 'random-seed'`. Other BACKGROUND cells get no seed. `× n` indexing on the running cell ordinal `i` mirrors the existing `chain[i % n]` scheme.)

- [ ] **Step 3: Syntax check**

Run: `node --check workflows/funnel.js` → exit 0.

- [ ] **Step 4: Verify the deterministic builders with a standalone check**

Create `/tmp/cells-check.mjs` — copy the `ENGINES`/`PERSONAS` literals and a *pure* extract of the cell-building loops (no `agent` calls), then assert:

```js
// (paste ENGINES, PERSONAS from funnel.js, then a pure copy of the cycle-1 loop
//  and the cycle->=2 map, parameterized by fakes for seeds/domainChains/topic)
import assert from 'node:assert'
// Cycle 1: 3 engines × 2 sources = 6 cells; exactly the lens-shift cells get personas;
// exactly the seed-source + random-seed-on-background cells get a seed.
// (assert cells.length === 6; assert personas assigned only to lens-shift; assert
//  random-seed-on-background has BOTH a chain and a seed.)
// Cycle >=2: beam of 5 -> 5 tasks, engine = ENGINES[i % 3] round-robin.
console.log('cells OK')
```

Run: `node /tmp/cells-check.mjs` → expect `cells OK`. Then `rm /tmp/cells-check.mjs`.
(This catches the off-by-one / wrong-source-gets-a-seed bugs the spec's testing note calls out.)

- [ ] **Step 5: Commit**
```bash
git add workflows/funnel.js
git commit -m "feat(engines): cycle-1 engines×sources matrix; cycle>=2 round-robin"
```

---

## Task 5: Persist engine/source/parents in the corpus (REDUCE write)

**Files:** Modify `workflows/funnel.js` (`reducePrompt` step 3 field list and the input-description line).

- [ ] **Step 1: Update the corpus field-list instruction**

In `reducePrompt`, replace the step-3 field-list line:

```js
    `   {"id","cycle","parent","seed","cluster","text","status"} where status is`,
```

with:

```js
    `   {"id","cycle","parent","seed","cluster","text","status","engine","source","parents"}`,
    `   — carry "engine", "source", and "parents" verbatim from each input idea; status is`,
```

- [ ] **Step 2: Update the input-description line (so the reduce agent knows the fields exist)**

Replace:

```js
    `(each has the parent branch id it came from, and its seed):`,
```

with:

```js
    `(each carries: engine, source, parent id, seed label, and — for mashups — parents):`,
```

- [ ] **Step 3: Syntax check + commit**

Run: `node --check workflows/funnel.js` → exit 0.
```bash
git add workflows/funnel.js
git commit -m "feat(engines): persist engine/source/parents to the corpus via REDUCE"
```

---

## Task 6: ✦ Mashup (crossover) at cycle ≥2

**Files:** Modify `workflows/funnel.js` (add `MASHUP_SCHEMA` near the schemas; add `mashupPrompt`; dispatch + parent-resolve assertion in the cycle section).

- [ ] **Step 1: Add `MASHUP_SCHEMA`** (after `DIVERGE_SCHEMA`)

```js
const MASHUP_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    ideas: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          text: { type: 'string' },
          parents: { type: 'array', items: { type: 'string' }, minItems: 2, maxItems: 2 },
        },
        required: ['text', 'parents'],
      },
    },
  },
  required: ['ideas'],
}
```

- [ ] **Step 2: Add `mashupPrompt`** (after `divergePrompt`)

```js
function mashupPrompt() {
  return [
    `You are the ✦ MASHUP (crossover) stage of an idea funnel. Read`,
    `${pluginRoot}/skills/spitballing/SKILL.md for the ✦ engine, then operate in BATCH mode.`,
    ``,
    `Topic: ${topic}`,
    `Here is the surviving beam (each has an id):`,
    JSON.stringify(beam, null, 0),
    ``,
    `YOU choose the pairs: pick two DISSIMILAR beam ideas and forcibly fuse them into a`,
    `new idea that genuinely depends on both. Generate exactly ${perAgent} fused ideas.`,
    `For each, cite the two real beam ids you fused in "parents". Do not invent ids.`,
    ``,
    `Return JSON only: {"ideas":[{"text":"...","parents":["<id>","<id>"]}, ...]}. No files.`,
  ].join('\n')
}
```

- [ ] **Step 3: Dispatch mashup at cycle ≥2 and assert parent ids resolve**

Immediately after `const newIdeas = nested.flat()` (and its `log` line), add:

```js
// ✦ crossover runs only when there is a population to recombine (cycle >= 2).
if (beam.length && enableMashup) {
  const beamIds = new Set(beam.map((b) => b.id))
  const mash = await agent(mashupPrompt(), { schema: MASHUP_SCHEMA, label: 'mashup:✦', phase: 'Diverge' })
  const mashIdeas = (mash?.ideas || []).filter((idea) => {
    const ok = idea.parents.every((p) => beamIds.has(p))
    if (!ok) {
      log(`WARNING: mashup idea cited non-beam parents ${JSON.stringify(idea.parents)} — dropping.`)
    }
    return ok
  })
  mashIdeas.forEach((idea) =>
    newIdeas.push({ text: idea.text, engine: 'mashup', source: 'beam', parent: null, parents: idea.parents, seed: null }),
  )
  log(`Mashup added ${mashIdeas.length} fused idea(s).`)
}
```

- [ ] **Step 4: Syntax check + commit**

Run: `node --check workflows/funnel.js` → exit 0.
```bash
git add workflows/funnel.js
git commit -m "feat(engines): ✦ mashup crossover at cycle>=2 with parent-id resolve guard"
```

---

## Task 7: End-to-end dry-run verification (gated on user go-ahead)

**Files:** none (verification only). Funnel runs spawn many agents and cost tokens — run only with the user's go-ahead; do not auto-run.

- [ ] **Step 1: Cycle-1 matrix dry-run** — reuse a domain model (`domainChains`) from a BACKGROUND run, then:

```
Workflow({scriptPath: ".../funnel.js", args: {mode:"cycle", topic:"a completely new Daria 1.5-hr special",
  cycle:1, corpusPath:"/tmp/funnel-matrix/corpus.jsonl", domainChains:<…>, invariants:[…],
  ideasPerAgent:6, targetBeamWidth:6, seeds:[…6…]}})
```
Expect: 6 diverge agents with labels `diverge:🎲:background`, `diverge:🎲:seed`, `diverge:🔄:background`, `diverge:🔄:seed`, `diverge:🔍:background`, `diverge:🔍:seed`.

- [ ] **Step 2: Inspect the corpus for structured fields**

Run: `node -e 'const fs=require("fs");const L=fs.readFileSync("/tmp/funnel-matrix/corpus.jsonl","utf8").trim().split("\n").map(JSON.parse);console.log("engines:",[...new Set(L.map(x=>x.engine))]);console.log("sources:",[...new Set(L.map(x=>x.source))])'`
Expect engines ⊇ {random-seed, inversion, lens-shift}; sources ⊇ {background, seed}. Spot-check that inversion ideas read as flipped-from-worst and lens-shift ideas carry a persona's stamp (the manual engine-fired check — the systematic judge is Part B).

- [ ] **Step 3: Cycle-≥2 + mashup dry-run** — pass the cycle-1 beam back as `beam`, `cycle:2`; confirm one agent per beam idea + a `mashup:✦` agent, and that corpus mashup rows have `engine:"mashup"`, `source:"beam"`, and two real `parents` ids.

- [ ] **Step 4: Confirm clean tree**

Run: `git status -s` (expect clean) and `git log --oneline master..HEAD`.

---

## Self-review (completed during planning)

- **Spec coverage (Part A):** ENGINES/PERSONAS + config (T1); engine fragments (T2); divergePrompt cell refactor (T3); cycle-1 engines×sources + cycle-≥2 round-robin, deterministic persona/seed/chain index assignment (T4); structured corpus fields via the REDUCE writer — the real owner of the corpus write (T5); ✦ mashup with agent-selected parents + resolve guard (T6); dry-run (T7). The spec's "no straight production cell" is satisfied (ENGINES has no straight key). ✦ quota half = `ideasPerAgent` (unchanged). Out of Part A scope (correctly deferred to Plan B): engine-fidelity judge, MTurk, scoring.
- **Type/name consistency:** `cell = {target, engineKey, glyph, source, seed, chain, persona}` is produced identically in both cycle branches (T4) and consumed by `divergePrompt`/`cellTask`. Idea record shape `{text, engine, source, parent, parents, seed}` is identical in `cellTask` (T4) and the mashup push (T6), and matches the REDUCE field list (T5). `engine` holds the engine KEY everywhere (not the seed label — the prior overload is removed in T3/T4).
- **Placeholder scan:** the standalone check in T4 Step 4 sketches the asserts rather than pasting the full pure-extract, because the extract must mirror whatever the implementer lands in T4; the assertions to make are stated explicitly (count 6, personas only on lens-shift, random-seed-on-background gets both). Acceptable — it's a throwaway verification artifact, not shipped code.

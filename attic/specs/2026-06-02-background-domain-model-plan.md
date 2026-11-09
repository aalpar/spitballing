# BACKGROUND Domain-Model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-shot BACKGROUND stage that models a goal's domain as a variance-annotated dependency graph, then feeds root→leaf chains into DIVERGE so divergence explores the real idea space (frozen frame + perturbed high-variance leaf) instead of a bare topic string.

**Architecture:** A new `mode: 'background'` in `workflows/funnel.js` runs one agent that researches the domain, grows a small dependency DAG, annotates each node with a `variance` (0–1) scalar, enumerates shuffled chains, writes a durable `domain-model.json`, and returns the lean working form (`domainChains`) plus any `needsDisambiguation`. The conductor (idea-funnel skill) runs it before cycle 1, resolves disambiguation via `AskUserQuestion`, then threads `domainChains` and `invariants` into every cycle's `args`. DIVERGE splits each chain at a variance threshold τ (default 0.5) — freezing low-variance ancestors, perturbing the high-variance leaf with a WordNet seed.

**Tech Stack:** JavaScript workflow script (Claude Code Workflow runtime — no filesystem/network/`Math.random`/`Date.now` in the *script*; spawned *agents* have full tools), Markdown skills. No build, no JS test runner.

**Testing note (read before Task 1):** This is an LLM-orchestration script. Its units are agent prompts and a small amount of pure JS. The script uses runtime-injected globals and top-level `return`, so it cannot be imported into `node --test`. Verification is therefore **Workflow dry-runs with concrete expected observations** plus **reading the JSON artifacts** — exactly the testing model the v2 spec already uses ("a dry single-cycle run on a small topic"). The one piece of pure logic (`splitChain`) gets a throwaway standalone `node` check.

**Reference spec:** `docs/specs/2026-06-02-background-domain-model-design.md`

---

## File structure

| File | Responsibility | Change |
|------|----------------|--------|
| `workflows/funnel.js` | All orchestration: schema, config, helpers, `background` mode, chain-threaded DIVERGE, invariant-aware REDUCE/SELECT | Modify |
| `skills/idea-funnel/SKILL.md` | Conductor: adds Step 1.5 (build domain model), informs the brief, threads chains | Modify |
| `skills/spitballing/SKILL.md` | DIVERGE agent: how to consume a dependency chain (freeze frame, perturb leaf) | Modify |
| `README.md` | Phase list mentions BACKGROUND | Modify |

A refinement of the spec, locked in here: the BACKGROUND agent **returns** the lean working form (`domainChains` = resolved concept+variance per node) and separately **writes** the full graph (`nodes`+`chains`+`importance`+`notes`) to `domain-model.json`. The return is the hand-off; the file is the durable, human-inspectable source of truth. This avoids a fragile LLM "join nodes to chains" step in the conductor.

---

## Task 1: Replace the BACKGROUND_SCHEMA stub with the real return schema

**Files:**
- Modify: `workflows/funnel.js` (the `BACKGROUND_SCHEMA` block, currently a verbatim copy of `DIVERGE_SCHEMA` returning `ideas[]`)

- [ ] **Step 1: Replace the stub schema**

Find the current stub:

```js
const BACKGROUND_SCHEMA = {
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
          engine: { type: 'string' },
        },
        required: ['text'],
      },
    },
  },
  required: ['ideas'],
}
```

Replace it entirely with:

```js
const BACKGROUND_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    domain: { type: 'string' },
    domainChains: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          id: { type: 'string' },
          nodes: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                concept: { type: 'string' },
                variance: { type: 'number' },
              },
              required: ['concept', 'variance'],
            },
          },
        },
        required: ['id', 'nodes'],
      },
    },
    needsDisambiguation: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          question: { type: 'string' },
          why: { type: 'string' },
          options: { type: 'array', items: { type: 'string' } },
        },
        required: ['question', 'why'],
      },
    },
    artifactWritten: { type: 'boolean' },
  },
  required: ['domain', 'domainChains', 'needsDisambiguation', 'artifactWritten'],
}
```

- [ ] **Step 2: Syntax check**

Run: `node --check workflows/funnel.js`
Expected: no output, exit 0 (the file parses).

- [ ] **Step 3: Commit**

```bash
git add workflows/funnel.js
git commit -m "feat(background): real domain-model return schema"
```

---

## Task 2: Add config fields and the `splitChain` helper

**Files:**
- Modify: `workflows/funnel.js` (the `// ---- config` block near the top, and the `// ---- prompts` helper region)

- [ ] **Step 1: Add config fields**

Find the end of the config block (after the line `const brief = cfg.brief ?? null ...`). Immediately after it, add:

```js
const domainChains = cfg.domainChains ?? [] // [{id, nodes:[{concept, variance}]}] from BACKGROUND
const domainModelPath = cfg.domainModelPath // where BACKGROUND writes domain-model.json
const tau = cfg.varianceThreshold ?? 0.5 // freeze (<tau) vs perturb (>=tau) split for chains
const disambiguation = cfg.disambiguation ?? null // {answers:[...]} folded into a BACKGROUND re-run
const invariants = cfg.invariants ?? [] // [concept] low-variance nodes — the arena for REDUCE/SELECT
```

- [ ] **Step 2: Add the background-mode arg guard**

Find the existing guard block (the `if (!topic) { ... }` and `if (mode === 'cycle' && !corpusPath) { ... }`). Add after them:

```js
if (mode === 'background' && !domainModelPath) {
  throw new Error('funnel: args.domainModelPath is required in background mode')
}
```

- [ ] **Step 3: Add the `splitChain` helper**

In the `// ---- prompts` region, near `seedLabel`/`seedInstruction`, add:

```js
// Partition a chain's nodes into the frozen frame (variance < tau, the in-domain
// scaffolding) and the perturbation zone (variance >= tau). The leaf (last node)
// always perturbs — it is the node DIVERGE pushes the furthest.
function splitChain(chainNodes) {
  const frozen = []
  const perturb = []
  chainNodes.forEach((node, i) => {
    const isLeaf = i === chainNodes.length - 1
    if (!isLeaf && node.variance < tau) {
      frozen.push(node.concept)
      return
    }
    perturb.push(node.concept)
  })
  const leaf = chainNodes.length ? chainNodes[chainNodes.length - 1].concept : null
  return { frozen, perturb, leaf }
}
```

- [ ] **Step 4: Syntax check**

Run: `node --check workflows/funnel.js`
Expected: no output, exit 0.

- [ ] **Step 5: Verify `splitChain` logic with a throwaway standalone check**

This is the only pure logic in the change, so prove it once. Create `/tmp/split-check.mjs` (NOT committed — `funnel.js` can't be imported, so copy the function in):

```js
const tau = 0.5
function splitChain(chainNodes) {
  const frozen = []
  const perturb = []
  chainNodes.forEach((node, i) => {
    const isLeaf = i === chainNodes.length - 1
    if (!isLeaf && node.variance < tau) {
      frozen.push(node.concept)
      return
    }
    perturb.push(node.concept)
  })
  const leaf = chainNodes.length ? chainNodes[chainNodes.length - 1].concept : null
  return { frozen, perturb, leaf }
}

import assert from 'node:assert'
// Typical chain: low-variance frame, high-variance leaf.
let r = splitChain([
  { concept: 'story', variance: 0.05 },
  { concept: 'protagonist', variance: 0.1 },
  { concept: 'subject matter', variance: 0.85 },
  { concept: 'props', variance: 0.9 },
])
assert.deepStrictEqual(r.frozen, ['story', 'protagonist'])
assert.deepStrictEqual(r.perturb, ['subject matter', 'props'])
assert.strictEqual(r.leaf, 'props')

// All-low chain: the leaf still perturbs (never an empty perturbation zone).
r = splitChain([
  { concept: 'a', variance: 0.1 },
  { concept: 'b', variance: 0.2 },
])
assert.deepStrictEqual(r.frozen, ['a'])
assert.deepStrictEqual(r.perturb, ['b'])

// Single node: it is the leaf, so it perturbs and the frame is empty.
r = splitChain([{ concept: 'solo', variance: 0.0 }])
assert.deepStrictEqual(r.frozen, [])
assert.deepStrictEqual(r.perturb, ['solo'])

console.log('splitChain OK')
```

Run: `node /tmp/split-check.mjs`
Expected: prints `splitChain OK`, exit 0.
Then: `rm /tmp/split-check.mjs`

- [ ] **Step 6: Commit**

```bash
git add workflows/funnel.js
git commit -m "feat(background): config fields + splitChain frame/perturb helper"
```

---

## Task 3: Add the `background` mode (prompt + agent + return)

**Files:**
- Modify: `workflows/funnel.js` (add `backgroundPrompt` in the prompts region; add the mode block alongside the `select`/`rereduce` mode blocks)

- [ ] **Step 1: Add `backgroundPrompt`**

In the prompts region (e.g. after `selectPrompt`/`rereducePrompt`), add:

```js
function backgroundPrompt() {
  const disambBlock = disambiguation
    ? `\nThe user resolved earlier ambiguity — incorporate these answers and do NOT ask again:\n${JSON.stringify(disambiguation, null, 0)}`
    : ''
  const goalBlock = brief && brief.goal ? `\nStated goal: ${brief.goal}.` : ''
  return [
    `You are the BACKGROUND stage of an idea funnel. Model the DOMAIN of a creative`,
    `goal as a small dependency graph so later stages explore the real idea space`,
    `instead of guessing from a bare topic string.`,
    ``,
    `Topic: ${topic}${goalBlock}`,
    disambBlock,
    ``,
    `Do this:`,
    `1. IDENTIFY the domain. Research it if useful — you MAY use web search/fetch tools`,
    `   to learn what the subject actually is and its conventions (for a TV special:`,
    `   runtime, format, structure). Be concrete about what artifact the goal asks for.`,
    `2. GROW a small dependency graph (a DAG) rooted at the topic. Edge A->B means`,
    `   "A requires/has B" — conceptual dependency over SUBJECT MATTER, not time`,
    `   (Bayesian: each node is conditioned on its parents). Keep it small: depth 3-5,`,
    `   ~10-25 nodes. Example chain: story -> plot -> protagonist -> projected personality.`,
    `3. ANNOTATE every node with:`,
    `   - variance (0..1): how freely its MEANING can change while staying in-domain.`,
    `     Near the root LOW (these are invariants: the protagonist exists; it is a story).`,
    `     Toward the leaves HIGH (props, subject matter, this episode's specifics).`,
    `   - importance (0..1): centrality to the topic (recorded for humans).`,
    `4. ENUMERATE root-to-leaf chains and SHUFFLE their order (YOU are the source of`,
    `   randomness — the workflow cannot randomize). Each chain is one exploration axis.`,
    `5. DISAMBIGUATE only if the topic is genuinely under-determined (e.g. which "Daria"?).`,
    `   Put real blockers in needsDisambiguation; otherwise return it EMPTY and proceed`,
    `   AUTONOMOUSLY. Never ask about mere preferences.`,
    `6. WRITE the full model as JSON to ${domainModelPath} (create parent dirs). Shape:`,
    `   {"topic","domain",`,
    `    "nodes":[{"id","concept","parents":[id],"variance","importance","note"?}],`,
    `    "chains":[{"id","path":[id]}],"needsDisambiguation":[...]}`,
    ``,
    `Return JSON: {domain, domainChains:[{id, nodes:[{concept,variance}]}],`,
    `needsDisambiguation:[{question,why,options?}], artifactWritten:true}.`,
    `domainChains is the resolved working form (each chain's nodes inline, ROOT FIRST,`,
    `concept+variance only) for every chain you wrote to the file.`,
  ].join('\n')
}
```

- [ ] **Step 2: Add the `background` mode block**

Find the `if (mode === 'select') { ... }` block. Immediately BEFORE it, add:

```js
// ---- background: research domain, build the dependency-graph model -----------
if (mode === 'background') {
  phase('Background')
  const bg = await agent(backgroundPrompt(), { schema: BACKGROUND_SCHEMA, label: 'background', phase: 'Background' })
  log(`Domain: ${bg.domain}. ${bg.domainChains.length} chain(s); ${bg.needsDisambiguation.length} disambiguation question(s).`)
  return {
    mode,
    topic,
    domain: bg.domain,
    domainModelPath,
    domainChains: bg.domainChains,
    needsDisambiguation: bg.needsDisambiguation,
    artifactWritten: bg.artifactWritten,
  }
}
```

- [ ] **Step 3: Syntax check**

Run: `node --check workflows/funnel.js`
Expected: no output, exit 0.

- [ ] **Step 4: Dry-run the background mode (technical topic)**

Use the Workflow tool:

```
Workflow({scriptPath: "/Users/aalpar/projects/spitballing-plugin/workflows/funnel.js",
  args: {mode: "background", topic: "novel, unpatented ways to sort a list",
         domainModelPath: "/tmp/funnel-sort/domain-model.json"}})
```

Expected:
- The run completes; return has `domain` (a string like "comparison/sorting algorithms"), `domainChains` (≥3 chains, each `nodes` root-first with ascending-ish variance), `needsDisambiguation: []`, `artifactWritten: true`.

- [ ] **Step 5: Verify the written artifact**

Run: `cat /tmp/funnel-sort/domain-model.json | node -e 'const fs=require("fs");const d=JSON.parse(fs.readFileSync(0));console.log("nodes",d.nodes.length,"chains",d.chains.length);console.log("root variance",d.nodes.find(n=>!n.parents||!n.parents.length).variance)'`
Expected: prints a node count in ~10–25, a chain count ≥3, and a root variance near 0 (the root is the most invariant node). If the root variance is high or chains is 0, the prompt needs tightening — fix `backgroundPrompt` and re-run Step 4.

- [ ] **Step 6: Commit**

```bash
git add workflows/funnel.js
git commit -m "feat(background): add the background mode (research + dependency graph)"
```

---

## Task 4: Thread chains into DIVERGE

**Files:**
- Modify: `workflows/funnel.js` (`divergePrompt`, the `divergeTasks` map in the cycle section)

- [ ] **Step 1: Add `chainBlock` and extend `divergePrompt`**

In the prompts region, add `chainBlock`:

```js
function chainBlock(chain) {
  if (!chain || !chain.nodes || !chain.nodes.length) {
    return ''
  }
  const split = splitChain(chain.nodes)
  const lines = [
    ``,
    `Dependency chain (conditioned over subject matter): ${chain.nodes.map((n) => n.concept).join(' -> ')}.`,
  ]
  if (split.frozen.length) {
    lines.push(`HOLD FIXED (the frame — these define the domain; breaking them leaves the domain): ${split.frozen.join('; ')}.`)
  }
  lines.push(`PERTURB HARD, the leaf "${split.leaf}" furthest of all: ${split.perturb.join('; ')}.`)
  return lines.join('\n')
}
```

Then change `divergePrompt`'s signature from `(target, seed)` to `(target, seed, chain)` and insert `chainBlock(chain)` between `seedInstruction(seed),` and `divergeBriefBlock(),` in its returned array. The relevant lines become:

```js
function divergePrompt(target, seed, chain) {
  const branchLine = target.id
    ? `Diverge specifically FROM this surviving branch (id ${target.id}): "${target.text}". Push it in new directions; do not just restate it.`
    : `Diverge on the topic at large.`
  return [
    `You are the DIVERGE stage of an idea funnel. Read ${pluginRoot}/skills/spitballing/SKILL.md`,
    `for the engine definitions and the anti-convergence rules, then operate in BATCH mode`,
    `(generate everything at once; do NOT wait for nudges).`,
    ``,
    `Topic: ${topic}`,
    branchLine,
    ``,
    seedInstruction(seed),
    chainBlock(chain),
    divergeBriefBlock(),
    `Generate exactly ${perAgent} punchy one-liner ideas, structurally varied (not the same`,
    `idea reworded).`,
    ``,
    `Return JSON only: {"ideas":[{"text":"...","engine":"${seedLabel(seed)}"}, ...]}. Do not write any files.`,
  ].join('\n')
}
```

- [ ] **Step 2: Assign a chain to each diverge agent**

Find the `const divergeTasks = targets.map((target, i) => { ... })` block. Replace it with:

```js
const divergeTasks = targets.map((target, i) => {
  const seed = seeds.length ? seeds[i % seeds.length] : { mode: 'noun', word: 'unexpected object' }
  const chain = domainChains.length ? domainChains[i % domainChains.length] : null
  const sl = seedLabel(seed)
  const leafNode = chain && chain.nodes.length ? chain.nodes[chain.nodes.length - 1].concept : null
  const compoundSeed = leafNode ? `${leafNode} × ${sl}` : sl
  return () =>
    agent(divergePrompt(target, seed, chain), {
      schema: DIVERGE_SCHEMA,
      label: `diverge:${sl}`,
      phase: 'Diverge',
    }).then((r) =>
      (r?.ideas || []).map((idea) => ({
        text: idea.text,
        engine: idea.engine || sl,
        parent: target.id,
        seed: compoundSeed,
      })),
    )
})
```

This records the chain leaf in the corpus `seed` field as a compound label (e.g. `"props & setting × noun:lighthouse"`) — no new corpus column.

- [ ] **Step 3: Syntax check**

Run: `node --check workflows/funnel.js`
Expected: no output, exit 0.

- [ ] **Step 4: Dry-run one cycle WITH chains**

First reuse the `domainChains` from Task 3's return (or re-run background). Then:

```
Workflow({scriptPath: "/Users/aalpar/projects/spitballing-plugin/workflows/funnel.js",
  args: {mode: "cycle", topic: "novel, unpatented ways to sort a list", cycle: 1,
         corpusPath: "/tmp/funnel-sort/corpus.jsonl",
         domainChains: <paste domainChains array from Task 3 return>,
         divergeAgents: 3, ideasPerAgent: 8, targetBeamWidth: 6,
         seeds: [{mode:"noun",word:"lighthouse"},{mode:"noun",word:"glacier"},{mode:"collision",a:"abacus",b:"jellyfish"}]}})
```

Expected:
- Run completes; `newIdeaCount` ≈ 24.
- Ideas stay in-domain (about sorting) yet vary the high-variance leaf wildly.

- [ ] **Step 5: Verify the compound seed label landed in the corpus**

Run: `node -e 'const fs=require("fs");const lines=fs.readFileSync("/tmp/funnel-sort/corpus.jsonl","utf8").trim().split("\n").map(JSON.parse);console.log(lines.slice(0,3).map(l=>l.seed))'`
Expected: at least some `seed` values contain ` × ` (the chain leaf prepended to the WordNet label).

- [ ] **Step 6: Commit**

```bash
git add workflows/funnel.js
git commit -m "feat(background): thread dependency chains into DIVERGE (freeze frame, perturb leaf)"
```

---

## Task 5: Make REDUCE / SELECT / rereduce invariant-aware

**Files:**
- Modify: `workflows/funnel.js` (`reducePrompt`, `selectPrompt`, `rereducePrompt`; add `invariantsBlock`)

- [ ] **Step 1: Add `invariantsBlock`**

In the prompts region, add:

```js
function invariantsBlock() {
  if (!invariants.length) {
    return ''
  }
  return `\nDomain invariants (definitional — an idea that breaks ANY of these is OUT OF DOMAIN: archive it, never beam it; this is separate from losing on the merits): ${invariants.join('; ')}.`
}
```

- [ ] **Step 2: Insert it into the three prompts**

In `reducePrompt`, add `invariantsBlock(),` immediately after the existing `criteriaBlock(),` line.
In `selectPrompt`, add `invariantsBlock(),` immediately after the existing `criteriaBlock(),` line.
In `rereducePrompt`, add `invariantsBlock(),` immediately after the existing `criteriaBlock(),` line.

(All three already call `criteriaBlock()`; the invariants line sits right after it in each array.)

- [ ] **Step 3: Syntax check**

Run: `node --check workflows/funnel.js`
Expected: no output, exit 0.

- [ ] **Step 4: Dry-run reduce with an invariant that should archive an idea**

Re-run the Task 4 cycle dry-run but add `invariants: ["the result is a correctly ordered permutation of the input"]` to the args, and inspect the corpus afterward:

Run: `node -e 'const fs=require("fs");const lines=fs.readFileSync("/tmp/funnel-sort/corpus.jsonl","utf8").trim().split("\n").map(JSON.parse);const live=lines.filter(l=>l.status==="live").length;console.log("live",live,"total",lines.length)'`
Expected: `live` ≤ the `targetBeamWidth` from the run; any idea that abandons correct ordering is `archived`, not `live`.

- [ ] **Step 5: Commit**

```bash
git add workflows/funnel.js
git commit -m "feat(background): pass domain invariants into REDUCE/SELECT as the arena"
```

---

## Task 6: Update the conductor (idea-funnel SKILL.md)

**Files:**
- Modify: `skills/idea-funnel/SKILL.md`

- [ ] **Step 1: Insert Step 1.5 after "Step 1 — Capture the goal"**

Add this section between "## Step 1 — Capture the goal" and "## Step 2 — Frame the brief":

```markdown
## Step 1.5 — Build the domain model (BACKGROUND)

Before framing the brief, model the goal's domain. Launch:

`Workflow({scriptPath: "<pluginRoot>/workflows/funnel.js", args: {mode: "background", topic: brief.goal, domainModelPath, brief}})`

(`brief.goal` may be just the captured one-liner at this point — the full brief
is framed next, informed by what BACKGROUND finds.)

- BACKGROUND researches the domain, grows a variance-annotated dependency graph
  (invariants at the low-variance root; degrees of freedom at the high-variance
  leaves), writes `domain-model.json`, and returns `domainChains` (the working
  form) plus `needsDisambiguation`.
- **Disambiguation:** if `needsDisambiguation` is non-empty, ask the user those
  questions (one `AskUserQuestion` round), then re-run background with
  `args.disambiguation = {answers}`. Cap at 2 rounds; after that, proceed with the
  agent's best reading and note the residual ambiguity at the brief checkpoint.
- **Verify, don't trust the return:** read `domain-model.json` to confirm it was
  written and the variance ranking is sane (root low, leaves high) — same
  source-of-truth discipline the corpus uses.
- Carry `domainChains` and `invariants` (the concepts of the low-variance nodes,
  i.e. variance below the funnel's threshold) forward into EVERY cycle's `args`.
```

- [ ] **Step 2: Update Step 2 (frame the brief) to draw on the domain model**

In "## Step 2 — Frame the brief", add this sentence at the end of the intro paragraph (before the JSON block):

```markdown
Use the domain model from Step 1.5 to inform the brief: high-variance axes suggest
`framing`, definitional invariants suggest candidate `constraints`, and the
identified domain sharpens `space`. The domain model and the brief stay separate
artifacts (space-structure vs. goal-scoring) — do not merge them.
```

- [ ] **Step 3: Update Step 3 launch args**

In "## Step 3 — Run cycles", in the `Workflow({...})` launch line, add `domainChains, invariants` to the args list so it reads:

```markdown
   `Workflow({scriptPath: "<pluginRoot>/workflows/funnel.js", args: {brief, topic: brief.goal, cycle, beam, corpusPath, pluginRoot, seeds, divergeAgents, ideasPerAgent, targetBeamWidth, domainChains, invariants}})`
```

And in the `rereduce` bullet, add `domainChains, invariants` to that args list too.

- [ ] **Step 4: Update "What you never do"**

In "## What you never do", add one bullet:

```markdown
- Apply the domain invariants as a generation *filter* beyond the frozen frame —
  they bound the arena (and archive out-of-domain ideas in REDUCE/SELECT), they do
  not prune within it.
```

- [ ] **Step 5: Commit**

```bash
git add skills/idea-funnel/SKILL.md
git commit -m "docs(idea-funnel): conductor builds + threads the domain model (Step 1.5)"
```

---

## Task 7: Update the DIVERGE agent skill + README

**Files:**
- Modify: `skills/spitballing/SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Add a chain-mode subsection to spitballing**

Append to `skills/spitballing/SKILL.md`:

```markdown
## Dependency-chain mode (when driven by the funnel)

The idea-funnel may hand you a **dependency chain** with two parts:

- **HOLD FIXED** — the frame. These concepts define the domain; an idea that breaks
  them leaves the domain. Treat them as given, not as material to vary.
- **PERTURB HARD** — the high-variance end, especially the named **leaf**. This is
  where your divergence energy goes: push the leaf the furthest, route it through
  the seed, and let the frozen frame keep the result coherent.

Freeze the frame, perturb the leaf — that is how you stay in-domain *and* wild at
once. Without a chain, diverge on the topic as usual.
```

- [ ] **Step 2: Mention BACKGROUND in the README phase description**

Open `README.md`, find where the funnel phases / pipeline are described (the diverge→reduce→select flow). Add BACKGROUND as the first phase. For example, if the README lists phases, change the lead-in to:

```markdown
The funnel runs **BACKGROUND → DIVERGE → REDUCE → … → SELECT**: BACKGROUND models
the goal's domain as a variance-annotated dependency graph (invariants vs. degrees
of freedom); DIVERGE explores it by freezing the frame and perturbing high-variance
leaves; REDUCE clusters and keeps a beam; SELECT names the final 3–5.
```

(Match the surrounding README wording — this is the content to convey, not necessarily the exact heading structure.)

- [ ] **Step 3: Commit**

```bash
git add skills/spitballing/SKILL.md README.md
git commit -m "docs: document dependency-chain DIVERGE mode and the BACKGROUND phase"
```

---

## Task 8: End-to-end dry run (background → cycle) on a narrative topic

**Files:** none (verification only)

- [ ] **Step 1: Run BACKGROUND on a narrative goal**

```
Workflow({scriptPath: "/Users/aalpar/projects/spitballing-plugin/workflows/funnel.js",
  args: {mode: "background", topic: "a completely new Daria 1.5-hr special",
         domainModelPath: "/tmp/funnel-daria/domain-model.json"}})
```

Expected: `domain` mentions Daria / animated special; `domainChains` non-empty; likely `needsDisambiguation: []` (Daria is identifiable), or a single crisp question if the agent is unsure which property — in which case answer it and re-run per the conductor flow.

- [ ] **Step 2: Inspect the domain model for the invariant/freedom gradient**

Run: `node -e 'const fs=require("fs");const d=JSON.parse(fs.readFileSync("/tmp/funnel-daria/domain-model.json"));const s=[...d.nodes].sort((a,b)=>a.variance-b.variance);console.log("MOST FIXED:",s.slice(0,3).map(n=>n.concept));console.log("MOST FREE:",s.slice(-3).map(n=>n.concept))'`
Expected: "MOST FIXED" lists Daria / story / protagonist-like invariants; "MOST FREE" lists subject-matter / props / setting-like axes. If the gradient is inverted or flat, tighten `backgroundPrompt` step 3 and re-run.

- [ ] **Step 3: Run one diverge+reduce cycle on those chains**

```
Workflow({scriptPath: "/Users/aalpar/projects/spitballing-plugin/workflows/funnel.js",
  args: {mode: "cycle", topic: "a completely new Daria 1.5-hr special", cycle: 1,
         corpusPath: "/tmp/funnel-daria/corpus.jsonl",
         domainChains: <paste from Step 1 return>,
         invariants: ["Daria is the protagonist", "it is a coherent story", "~90 minute special"],
         divergeAgents: 4, ideasPerAgent: 10, targetBeamWidth: 6,
         seeds: [{mode:"noun",word:"lighthouse"},{mode:"cousin",a:"violin",b:"cello"},{mode:"collision",a:"tax form",b:"volcano"},{mode:"noun",word:"escalator"}]}})
```

Expected: ideas are recognizably Daria episodes (frame held) with wildly varied themes/props (leaf perturbed); `beam.length` ≤ 6.

- [ ] **Step 4: Confirm the beam is consistent with the corpus**

Run: `node -e 'const fs=require("fs");const lines=fs.readFileSync("/tmp/funnel-daria/corpus.jsonl","utf8").trim().split("\n").map(JSON.parse);console.log("live in corpus:",lines.filter(l=>l.status==="live").length)'`
Expected: the live count equals the returned `beam.length` and is ≤ `targetBeamWidth` (the v2 spec's hard-cap / consistency lessons still hold).

- [ ] **Step 5: Final commit (clean working tree)**

```bash
git status   # expect: clean, or only intended changes
git log --oneline -8
```

No commit needed if Tasks 1–7 already committed everything; this step just confirms the branch is complete and ready for the user to review / open a PR.

---

## Self-review (completed during planning)

- **Spec coverage:** domain model artifact (Tasks 1,3), variance-as-operative-scalar (Task 2 `splitChain`, importance written but unused), `background` mode + web research + autonomy (Task 3), disambiguation via conductor checkpoint (Tasks 3 return + 6 Step 1), chain-threaded DIVERGE with τ split (Task 4), invariant-aware REDUCE/SELECT distinct from brief constraints (Task 5), brief relationship + Step 1.5 + never-do (Task 6), DIVERGE agent chain-mode + README (Task 7), graph-lifetime reuse/opt-in re-grow (covered by the conductor reusing returned `domainChains`; re-grow = re-run background, no code needed), testing (Task 8 + per-task dry runs). All spec sections map to a task.
- **Placeholder scan:** README Step 2 (Task 7) intentionally says "match surrounding wording" because the exact README structure must be read at edit time — the *content* to convey is given in full. No code step defers logic.
- **Type/name consistency:** `domainChains` shape `{id, nodes:[{concept, variance}]}` is identical in the schema (Task 1), config (Task 2), background return (Task 3), and DIVERGE consumption (Task 4). `splitChain` returns `{frozen, perturb, leaf}` and is consumed only in `chainBlock` (Task 4). `invariants` is `[concept-string]` in config (Task 2), `invariantsBlock` (Task 5), and conductor args (Task 6). `tau`/`varianceThreshold` consistent (Task 2, 4).
```
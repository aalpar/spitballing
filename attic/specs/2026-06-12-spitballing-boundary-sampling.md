# Spitballing Boundary-Sampling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the blind beam-search idea-funnel with a boundary-sampling conductor skill backed by a small deterministic Python kernel — map the obvious set with a blind panel, sample the high-value/low-obviousness band, converge by membership-test + value judge.

**Architecture:** A conductor `skills/spitballing/SKILL.md` drives MAP→SAMPLE→CONVERGE in-conversation and spawns independent agents only for the blind panel. The deterministic arithmetic (≥25% obviousness threshold, band filter, ranking) lives in a tested `tools/spitball/` package the skill calls via Bash. LLM does semantic judgment; the kernel does reproducible bookkeeping.

**Tech Stack:** Python 3 stdlib (`unittest`, `dataclasses`, `argparse`, `json`); Claude Code skill (Markdown). Tests run with `python -m unittest` from the repo root (matching `tools/ablation`).

---

## File structure

| File | Responsibility |
|------|----------------|
| `tools/spitball/__init__.py` | Package marker (empty) |
| `tools/spitball/panel.py` | `obvious_clusters()` — distinct-panelist counting + 25% threshold |
| `tools/spitball/band.py` | `Candidate`, `in_band()`, `rank_band()` (the open creative core) |
| `tools/spitball/__main__.py` | CLI: `obvious` and `rank` subcommands (JSON stdin→stdout) |
| `tools/spitball/tests/__init__.py` | Test package marker (empty) |
| `tools/spitball/tests/test_panel.py` | Tests for `obvious_clusters` |
| `tools/spitball/tests/test_band.py` | Tests for `in_band` / `rank_band` |
| `tools/spitball/tests/test_cli.py` | Subprocess smoke test of the CLI |
| `skills/spitballing/SKILL.md` | **Rewrite** — the conductor |
| `.claude-plugin/plugin.json` | Update description/keywords (no longer divergent-only) |
| `.claude-plugin/marketplace.json` | Update description |
| `README.md` | Update to the new framing |
| `attic/ablation/` | Archived `tools/ablation` (git mv) |
| *(deleted)* | `skills/idea-funnel/`, `skills/idea-cluster/`, `workflows/`, `assets/seeds.json`, `tools/gen-seeds.py` |

---

## Task 1: `obvious_clusters` — the 25% threshold kernel

**Files:**
- Create: `tools/spitball/__init__.py`
- Create: `tools/spitball/tests/__init__.py`
- Create: `tools/spitball/panel.py`
- Test: `tools/spitball/tests/test_panel.py`

- [ ] **Step 1: Create the two empty package markers**

```bash
mkdir -p tools/spitball/tests
: > tools/spitball/__init__.py
: > tools/spitball/tests/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `tools/spitball/tests/test_panel.py`:

```python
import unittest

from tools.spitball.panel import obvious_clusters, ObviousCluster


class TestObviousClusters(unittest.TestCase):
    def test_threshold_is_over_distinct_panelists_not_ideas(self):
        # 12 panelists. "literal" reached by 9 distinct panelists => 0.75 obvious.
        # "weather" reached by 2 => 0.167, below the 0.25 cutoff.
        panelist_clusters = (
            [{"literal", "weather"}] * 2
            + [{"literal"}] * 7
            + [{"rare"}] * 3
        )
        out = obvious_clusters(panelist_clusters, n_panelists=12)
        labels = [o.label for o in out]
        self.assertEqual(labels, ["literal"])           # only >=0.25 survives
        self.assertEqual(out[0].panelist_count, 9)
        self.assertAlmostEqual(out[0].frac, 0.75)

    def test_a_panelist_repeating_a_cluster_counts_once(self):
        # Same panelist listing "literal" twice must not inflate the count.
        out = obvious_clusters([["literal", "literal"]], n_panelists=4)
        # 1 of 4 = 0.25 -> obvious (boundary is inclusive), counted once.
        self.assertEqual(out[0].panelist_count, 1)

    def test_boundary_is_inclusive(self):
        # exactly 0.25 is obvious; just under is not.
        out = obvious_clusters([{"a"}, set(), set(), set()], n_panelists=4)
        self.assertEqual([o.label for o in out], ["a"])
        out2 = obvious_clusters([{"a"}, set(), set(), set(), set()], n_panelists=5)
        self.assertEqual(out2, [])                       # 0.2 < 0.25

    def test_sorted_by_frac_desc_then_label(self):
        pc = [{"b", "a"}, {"b", "a"}, {"b"}, {"b"}]
        out = obvious_clusters(pc, n_panelists=4)
        self.assertEqual([o.label for o in out], ["b", "a"])  # b=1.0, a=0.5


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m unittest tools.spitball.tests.test_panel -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.spitball.panel'`

- [ ] **Step 4: Write the implementation**

Create `tools/spitball/panel.py`:

```python
"""Deterministic bookkeeping for the blind-panel obviousness measurement.

The LLM supplies the semantic judgment (which cluster each panelist's idea falls
into). This module does only the arithmetic: count *distinct panelists* per
cluster and apply the >=25% threshold. Counting panelists (not ideas) is what
makes the cutoff faithful to "obvious to 25% of the population". Arithmetic, not
vibes -- reproducible and auditable.
"""
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class ObviousCluster:
    label: str
    panelist_count: int
    frac: float


def obvious_clusters(panelist_clusters, n_panelists, threshold=0.25):
    """Return clusters reached by >= threshold of panelists, frac-desc.

    panelist_clusters: iterable of iterables -- one entry per panelist, holding
        the cluster labels that panelist produced (duplicates ignored).
    """
    counts = Counter()
    for clusters in panelist_clusters:
        for label in set(clusters):          # distinct per panelist
            counts[label] += 1
    out = [
        ObviousCluster(label, c, c / n_panelists)
        for label, c in counts.items()
        if c / n_panelists >= threshold
    ]
    out.sort(key=lambda o: (-o.frac, o.label))
    return out
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m unittest tools.spitball.tests.test_panel -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add tools/spitball/__init__.py tools/spitball/tests/__init__.py \
        tools/spitball/panel.py tools/spitball/tests/test_panel.py
git commit -m "feat(spitball): obvious_clusters 25% panelist-frequency kernel"
```

---

## Task 2: `in_band` and `rank_band` — the band filter and the open creative core

**Files:**
- Create: `tools/spitball/band.py`
- Test: `tools/spitball/tests/test_band.py`

`rank_band`'s scoring body is a **USER CONTRIBUTION** — the decided direction is *value × fringe, fringe weighted higher*, but the exact combination is yours to write. The test below pins the behavior; a reference implementation is provided in the collapsed note so execution is never blocked.

- [ ] **Step 1: Write the failing test**

Create `tools/spitball/tests/test_band.py`:

```python
import unittest

from tools.spitball.band import Candidate, in_band, rank_band


def cand(text, value, fringe, obvious_cluster=None):
    return Candidate(text=text, value_score=value, fringe_proximity=fringe,
                     nearest_obvious_cluster=obvious_cluster)


class TestInBand(unittest.TestCase):
    def test_obvious_is_excluded_even_if_high_value(self):
        c = cand("CoolCap", 0.95, 0.2, obvious_cluster="literal")
        self.assertFalse(in_band(c))

    def test_low_value_is_excluded_even_if_high_fringe(self):
        c = cand("Glacier", 0.3, 0.99)            # evokes cold, not the head
        self.assertFalse(in_band(c))

    def test_high_value_non_obvious_is_in_band(self):
        self.assertTrue(in_band(cand("Nimbus", 0.8, 0.7)))


class TestRankBand(unittest.TestCase):
    def test_fringe_outranks_value_when_both_in_band(self):
        # A: higher value, lower fringe. B: lower value, higher fringe.
        # Fringe weighted higher => B must rank first.
        a = cand("A", 0.9, 0.4)
        b = cand("B", 0.7, 0.9)
        self.assertEqual([c.text for c in rank_band([a, b], k=2)], ["B", "A"])

    def test_filters_out_of_band_before_ranking(self):
        good = cand("good", 0.8, 0.6)
        obvious = cand("obvious", 0.95, 0.95, obvious_cluster="literal")
        weak = cand("weak", 0.2, 0.99)
        ranked = rank_band([good, obvious, weak], k=5)
        self.assertEqual([c.text for c in ranked], ["good"])

    def test_returns_at_most_k(self):
        cands = [cand(str(i), 0.8, 0.5 + i / 100) for i in range(10)]
        self.assertEqual(len(rank_band(cands, k=3)), 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tools.spitball.tests.test_band -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.spitball.band'`

- [ ] **Step 3: Write `band.py` with `Candidate` + `in_band`, and the `rank_band` scaffold**

Create `tools/spitball/band.py`:

```python
"""Band membership and ranking.

`in_band` is deterministic. `rank_band` filters to the band, then orders it by
the creative scoring function. That scoring function is the one load-bearing
creative choice in the whole system; its body is written by the user.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Candidate:
    text: str
    value_score: float                  # 0..1 fulfillment (LLM value judge)
    fringe_proximity: float             # 0..1 closeness to the negative fringe
    nearest_obvious_cluster: Optional[str] = None   # label if it lands in an
    #                                                 obvious cluster, else None


def in_band(c, value_threshold=0.6):
    """In-band iff it fulfills (value high) AND is not obvious (did not land in
    any obvious cluster)."""
    return c.value_score >= value_threshold and c.nearest_obvious_cluster is None


def _score(c):
    """Creative scoring -- USER CONTRIBUTION.

    Decided direction: value x fringe, FRINGE WEIGHTED HIGHER. Fringe (surprise)
    leads; value is the floor (already enforced by in_band) plus a lighter pull
    so a fringe-chaser cannot promote a barely-fulfilling idea over a strong one
    of equal surprise. Write the body that satisfies test_band.py.
    """
    raise NotImplementedError("write the value x fringe scoring (fringe higher)")


def rank_band(candidates, k, value_threshold=0.6):
    band = [c for c in candidates if in_band(c, value_threshold)]
    band.sort(key=_score, reverse=True)
    return band[:k]
```

- [ ] **Step 4: Write `_score` to make the tests pass (your turn)**

Implement `_score` so `test_band.py` passes. The pinned behavior: of two in-band
candidates, the higher-`fringe_proximity` one ranks first even when it has lower
`value_score`. Keep it to a few lines.

<details><summary>Reference implementation (use if delegating)</summary>

```python
def _score(c):
    return 0.7 * c.fringe_proximity + 0.3 * c.value_score
```

Check: A(0.9,0.4)=0.55, B(0.7,0.9)=0.84 → B first. ✓
</details>

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m unittest tools.spitball.tests.test_band -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add tools/spitball/band.py tools/spitball/tests/test_band.py
git commit -m "feat(spitball): band filter + value-x-fringe ranking core"
```

---

## Task 3: CLI entry point — `obvious` and `rank` subcommands

**Files:**
- Create: `tools/spitball/__main__.py`
- Test: `tools/spitball/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tools/spitball/tests/test_cli.py`:

```python
import json
import subprocess
import sys
import unittest


def run_cli(args, payload):
    proc = subprocess.run(
        [sys.executable, "-m", "tools.spitball", *args],
        input=json.dumps(payload), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class TestCli(unittest.TestCase):
    def test_obvious_subcommand(self):
        payload = {"panelists": [
            {"clusters": ["literal"]}, {"clusters": ["literal"]},
            {"clusters": ["literal"]}, {"clusters": ["rare"]},
        ]}
        out = run_cli(["obvious"], payload)
        labels = [o["label"] for o in out["obvious_clusters"]]
        self.assertEqual(labels, ["literal"])            # 3/4 = 0.75

    def test_rank_subcommand(self):
        payload = {"candidates": [
            {"text": "A", "value_score": 0.9, "fringe_proximity": 0.4,
             "nearest_obvious_cluster": None},
            {"text": "B", "value_score": 0.7, "fringe_proximity": 0.9,
             "nearest_obvious_cluster": None},
        ]}
        out = run_cli(["rank", "--k", "2"], payload)
        self.assertEqual([c["text"] for c in out["ranked"]], ["B", "A"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tools.spitball.tests.test_cli -v`
Expected: FAIL — non-zero return code / `No module named tools.spitball.__main__`

- [ ] **Step 3: Write the CLI**

Create `tools/spitball/__main__.py`:

```python
"""CLI bridge: the skill pipes JSON in, gets JSON out. Keeps the model out of
the arithmetic. `python -m tools.spitball obvious|rank`.
"""
import argparse
import json
import sys
from dataclasses import asdict

from tools.spitball.band import Candidate, rank_band
from tools.spitball.panel import obvious_clusters


def main(argv=None):
    parser = argparse.ArgumentParser(prog="spitball")
    sub = parser.add_subparsers(dest="cmd", required=True)

    po = sub.add_parser("obvious", help="panel JSON -> obvious clusters")
    po.add_argument("--threshold", type=float, default=0.25)

    pr = sub.add_parser("rank", help="candidates JSON -> ranked band")
    pr.add_argument("--k", type=int, default=5)
    pr.add_argument("--value-threshold", type=float, default=0.6)

    args = parser.parse_args(argv)
    data = json.load(sys.stdin)

    if args.cmd == "obvious":
        panelist_clusters = [p["clusters"] for p in data["panelists"]]
        clusters = obvious_clusters(
            panelist_clusters, n_panelists=len(panelist_clusters),
            threshold=args.threshold,
        )
        json.dump({"obvious_clusters": [asdict(o) for o in clusters]},
                  sys.stdout, indent=2)
    elif args.cmd == "rank":
        cands = [Candidate(**c) for c in data["candidates"]]
        ranked = rank_band(cands, k=args.k, value_threshold=args.value_threshold)
        json.dump({"ranked": [asdict(c) for c in ranked]}, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tools.spitball.tests.test_cli -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the whole kernel suite**

Run: `python -m unittest discover -s tools/spitball/tests -v`
Expected: PASS (12 tests total)

- [ ] **Step 6: Commit**

```bash
git add tools/spitball/__main__.py tools/spitball/tests/test_cli.py
git commit -m "feat(spitball): JSON CLI for obvious/rank"
```

---

## Task 4: Rewrite the conductor skill

**Files:**
- Modify (overwrite): `skills/spitballing/SKILL.md`

- [ ] **Step 1: Overwrite `skills/spitballing/SKILL.md` with the conductor**

Replace the entire file with:

````markdown
---
name: spitballing
description: Use when the user wants creative options for a request — names, concepts, angles — that are genuinely non-obvious yet still fulfill the request. Maps where the obvious answers live (a blind panel), then samples the high-value/low-obviousness band and returns a final 3–5. Distinct from brainstorming (which converges to ONE design through dialogue).
argument-hint: "[the request to generate options for]"
allowed-tools: Read, Write, Bash, Task
---

# Spitballing — boundary sampling

Creativity here is a methodical search, not a muse. Every request defines an
idea-space with two measured axes:

- **Value** — does an idea fulfill the request?
- **Obviousness** — would ≥25% of a blind naive panel spontaneously produce it?

You reject the **positive set** (obvious fulfillments — too easy) and the
**negative set** (doesn't fulfill — off-target), and target the **band**: high
value, low obviousness, hugging the negative border. You run three stages —
MAP, SAMPLE, CONVERGE — and end with a final 3–5.

## Anti-trigger check (do this first)

If the user wants to converge on and refine ONE approach into a design/spec,
that is brainstorming, not this. Say so and offer to switch. Spitballing returns
a *set* (3–5) of measured options; it never picks the single winner for them.

## The brief (frame once, infer & confirm)

Restate the request as a brief; show it, let the user tweak in one pass — no
interrogation:

```json
{"request": "...", "fulfillment_criterion": "what makes an answer COUNT",
 "output_kind": "the shape of one answer", "hard_constraints": ["filters"]}
```

`fulfillment_criterion` defines the value axis — it is exactly what the value
judge tests. `hard_constraints` filter in CONVERGE only, never during sampling.

## Stage 1 — MAP

**Positive set (blind panel).** Spawn **N=12** independent agents with the Task
tool, in parallel, each given ONLY the request and `output_kind` and this
instruction — nothing about each other, nothing about this skill:

> "Give your first 8 instinctive answers to: «request». One per line, no
> explanation."

Pool all answers. *You* cluster them by underlying approach (clustering needs
all answers at once; it needs no independence, so you do it — do NOT ask an
agent). Record, per cluster, the distinct panelists who reached it. Then run the
kernel to apply the 25% cutoff:

```bash
echo '{"panelists":[{"clusters":["literal","weather"]}, ...]}' \
  | python -m tools.spitball obvious
```

Each panelist entry lists the distinct cluster labels that panelist produced.
The returned `obvious_clusters` ARE the positive set.

**Negative fringe.** Holding `fulfillment_criterion`, write 3–6 near-border
failure landmarks — "almost fulfills but technically fails" (e.g. *evokes cold
but not the head*; *evokes the head but not cooling*). These are a compass for
SAMPLE, not a filter.

**Write `map.json`** to `docs/spitball/<topic-slug>/map.json`:

```json
{"value_criterion": "...", "obvious_clusters": [...from the kernel...],
 "negative_fringe": ["...", "..."]}
```

## Stage 2 — SAMPLE

Generate ~40 candidates aimed at the band. Give generation the full compass:
the request + `fulfillment_criterion`, the **positive set** ("these are taken /
obvious — go *outside* them"), and the **negative fringe** ("the productive edge
is just inside here: fulfill the request, but lean toward this failure border").
Sample loosely — no scoring yet. (You may fan out a few Task agents for breadth;
independence is not load-bearing here.)

## Stage 3 — CONVERGE

For each candidate, supply the two semantic judgments yourself (or via a judge
agent at scale):

- `nearest_obvious_cluster`: the obvious-cluster label this candidate falls into,
  or `null` if it belongs to none. **This is the membership test — judge it
  against `map.json`, never by re-polling a fresh panel (that reveals the
  candidate and biases the answer).**
- `value_score` (0–1) vs. `fulfillment_criterion`; apply `hard_constraints` here
  (a violation → treat as not in-band).
- `fringe_proximity` (0–1): closeness to `negative_fringe`.

Write every candidate to `docs/spitball/<topic-slug>/candidates.jsonl`, then let
the kernel filter the band and rank:

```bash
echo '{"candidates":[{"text":"Nimbus","value_score":0.8,
  "fringe_proximity":0.7,"nearest_obvious_cluster":null}, ...]}' \
  | python -m tools.spitball rank --k 5
```

## Output

Write `docs/spitball/<topic-slug>/result.md`: the final 3–5 (the kernel's
`ranked`), each with one line of rationale (why it fulfills, why it's not
obvious), followed by the map they were measured against. Close with one line:

> "5 band options in `<path>`. Want to take one into brainstorming?"

Never auto-advance to brainstorming.

## Why blindness matters

The panel must be separate agent contexts. One model pretending to be 12
respondents already knows what it "said" — its later picks aren't first
instincts, so the 25% measurement is corrupted. Real independence for the one
measurement that needs it is the whole point of the panel.
````

- [ ] **Step 2: Verify the skill file is valid frontmatter + renders**

Run: `head -8 skills/spitballing/SKILL.md`
Expected: YAML frontmatter with `name: spitballing`, `allowed-tools: Read, Write, Bash, Task`.

- [ ] **Step 3: Commit**

```bash
git add skills/spitballing/SKILL.md
git commit -m "feat(spitballing): rewrite skill as boundary-sampling conductor"
```

---

## Task 5: Update plugin manifest, marketplace, and README

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `README.md`

- [ ] **Step 1: Update `plugin.json` description + keywords + version**

Set `"version": "0.2.0"` and replace `description`/`keywords`:

```json
  "version": "0.2.0",
  "description": "Boundary-sampling idea generation — maps where the obvious answers live with a blind panel, then samples the high-value/non-obvious band and returns a measured 3–5. Creativity as methodical search, not a muse.",
  "keywords": ["creativity", "ideation", "divergent-thinking", "convergence", "boundary-sampling", "skill"]
```

- [ ] **Step 2: Update `marketplace.json` description**

Replace the plugin `description` to match:

```json
      "description": "Boundary-sampling idea generation — map the obvious set, sample the non-obvious band, return a measured 3–5."
```

- [ ] **Step 3: Rewrite `README.md` to the new framing**

Replace `README.md` with:

```markdown
# Spitballing

Creativity is a methodical search bounded by constraints — the empty space
between *what fulfills a request* and *what is obvious*. This plugin finds that
space and samples it.

Given a request, the `spitballing` skill:

1. **MAP** — a blind panel of independent agents reveals the **obvious set**
   (anything ≥25% of them spontaneously produce), and names the **negative
   fringe** (what almost-fulfills-but-fails).
2. **SAMPLE** — generates candidates aimed at the **band**: high value, low
   obviousness, hugging the negative border.
3. **CONVERGE** — scores each candidate (fulfillment + obviousness via a
   membership test, not re-polling), filters the band, and ranks to a final
   3–5. Ranking favors surprise (fringe) over safety, with value as the floor.

The deterministic arithmetic (the 25% cutoff, the band filter, the ranking)
lives in `tools/spitball/`, tested with `python -m unittest`. The skill does the
semantic judgment; the kernel does the bookkeeping.

This is the opposite end from brainstorming: brainstorming converges to ONE
approved design through dialogue; spitballing returns a measured *set* of
non-obvious options and never picks for you.

## Usage

Invoke the `spitballing` skill with a request, e.g. *"new names for a product
that keeps the head cool."* Output lands in `docs/spitball/<topic-slug>/`.
```

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json README.md
git commit -m "docs: update manifest + README to boundary-sampling framing"
```

---

## Task 6: Scorched-earth disposition

**Files:**
- Archive: `tools/ablation` → `attic/ablation`
- Delete: `skills/idea-funnel/`, `skills/idea-cluster/`, `workflows/`, `assets/seeds.json`, `tools/gen-seeds.py`

- [ ] **Step 1: Archive the ablation apparatus (preserve, don't destroy)**

```bash
mkdir -p attic
git mv tools/ablation attic/ablation
```

- [ ] **Step 2: Delete the superseded skills, workflow, and seed pool**

```bash
git rm -r skills/idea-funnel skills/idea-cluster workflows assets/seeds.json tools/gen-seeds.py
```

- [ ] **Step 3: Verify nothing live still references the removed paths**

Run: `grep -rn -e idea-funnel -e idea-cluster -e funnel.js -e seeds.json -e gen-seeds skills/ tools/spitball/ README.md .claude-plugin/`
Expected: no matches (docs/ history may still mention them — that is fine).

- [ ] **Step 4: Confirm the kernel suite still passes after the moves**

Run: `python -m unittest discover -s tools/spitball/tests -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: archive ablation to attic, remove blind-funnel machinery"
```

---

## Task 7: Dogfood validation (manual)

**Files:** none — this exercises the assembled system on the originating example.

- [ ] **Step 1: Run the skill on the head-cool request**

Invoke the `spitballing` skill with: *"new names for a product that keeps the
head cool."* Let it run MAP→SAMPLE→CONVERGE end to end.

- [ ] **Step 2: Verify the panel-clustering proof**

Open `docs/spitball/*/map.json`. The `obvious_clusters` MUST include the literal
cool+head compounds (CoolCap / ChillHat-style) at `frac ≥ 0.25`. If
`obvious_clusters` is empty, the panel or your clustering is broken — fix before
trusting any band output.

- [ ] **Step 3: Control-injection check**

Add one deliberately-obvious name (e.g. `"CoolHead"`) to the candidate set with
`nearest_obvious_cluster` set to the matching obvious cluster. Re-run
`python -m tools.spitball rank`. The control MUST be absent from `ranked`. If a
known-obvious control survives into the band, the yardstick is not biting.

- [ ] **Step 4: Verify SAMPLE avoided the positive set**

Skim `candidates.jsonl`: the generated names should not be rewordings of the
`obvious_clusters` members. Samey output = SAMPLE ignored the compass.

- [ ] **Step 5: Commit the dogfood artifacts**

```bash
git add docs/spitball
git commit -m "test(spitball): dogfood run on head-cool request"
```

---

## Self-review notes

- **Spec coverage:** brief (Task 4), MAP/blind panel + 25% (Tasks 1,4), negative
  fringe (Task 4), SAMPLE (Task 4), CONVERGE membership-test + value judge
  (Tasks 2,4), `rank_band` value×fringe open core (Task 2), artifacts map.json /
  candidates.jsonl / result.md (Task 4), scorched-earth incl. ablation archive
  (Task 6), testing dogfood incl. control injection (Task 7). All mapped.
- **`fringe_proximity` is an LLM judgment** against prose fringe landmarks, as
  the spec flags — the kernel consumes it as a given 0–1 number; no metric is
  promised.
- **Type consistency:** `Candidate(text, value_score, fringe_proximity,
  nearest_obvious_cluster)` and `ObviousCluster(label, panelist_count, frac)`
  are used identically across `band.py`, `panel.py`, `__main__.py`, the tests,
  and the skill's JSON payloads.
```

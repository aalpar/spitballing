# Spitballing

[![test](https://github.com/aalpar/spitballing/actions/workflows/test.yml/badge.svg)](https://github.com/aalpar/spitballing/actions/workflows/test.yml)
[![version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Faalpar%2Fspitballing%2Fmaster%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version)](.claude-plugin/plugin.json)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

A [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) plugin for
non-obvious ideas. It measures where the obvious answers live with a blind
panel, then samples the high-value, low-obviousness band and returns a ranked
3–5.

Creativity, here, is a methodical search bounded by constraints: the space
between *what fulfills a request* and *what is obvious*.

## Example

*"New names for a product that keeps the head cool."*

**Obvious set** (≥25% of a 12-agent blind panel produced it; rejected):
`cool` 12/12 · `frost` 12/12 · `chill` 12/12 · `airflow` 12/12 · `ice` 11/12 ·
calm puns 9/12 · `therma` 8/12

**Result:**

| # | Name | value | fringe | score |
|---|------|------:|-------:|------:|
| 1 | Oasis | 0.66 | 0.78 | 0.732 |
| 2 | Eclipse | 0.60 | 0.76 | 0.696 |
| 3 | Umbra | 0.68 | 0.70 | 0.692 |
| 4 | Aurora | 0.62 | 0.74 | 0.692 |
| 5 | Penumbra | 0.60 | 0.72 | 0.672 |

Every panelist reached for a temperature word; the band leans on two metaphors
none of them touched, *shade* and *relief*. Full run:
[`docs/spitball/head-cool-product-names/`](docs/spitball/head-cool-product-names/result.md).

The [pantry-dinner run](docs/spitball/pantry-dinner/result.md) (a dinner from
lentils, a lemon, eggs, and stale bread) is set up as a human test: its value
scores are the model's own, so it carries a cook test, top two band dishes
against an obvious-set control. The results table is not yet filled in.

## Install

```
/plugin marketplace add aalpar/spitballing
/plugin install spitballing@spitballing-marketplace
```

Requires `python3` on `PATH` (stdlib only).

## Usage

Ask for options in plain language (*"give me less obvious names for…"*) or
invoke `/spitballing:spitballing <request>`. The skill shows a brief to tweak
once, then runs the pipeline. Output lands in `docs/spitball/<topic-slug>/`:

| File | Contents |
|------|----------|
| `map.json` | the obvious clusters with member ideas, and the negative fringe |
| `candidates.jsonl` | every candidate with its scores and band verdict |
| `result.md` | the ranked final 3–5 and why each survived |

Spitballing returns a measured *set* and never picks for you. To refine one
option into a design, use brainstorming.

## How it works

1. **MAP.** 12 independent agents answer the request blind. Any cluster ≥25%
   of them produce is the **obvious set**. The **negative fringe** names what
   almost fulfills but fails.
2. **SAMPLE.** Generate candidates aimed at the **band**: high value, low
   obviousness, hugging the negative border.
3. **CONVERGE.** Score each candidate for value (against the brief's
   fulfillment criterion) and obviousness (membership test against the mapped
   clusters). Keep the band (value ≥ 0.6, not obvious) and rank by
   `0.6·fringe + 0.4·value`: surprise leads, value is the floor.

### Design

- **Deterministic kernel, semantic judge.** The skill makes the judgments; a
  Python kernel (`python -m tools.spitball obvious|rank|fringe-check`, JSON in,
  JSON out) does every cutoff, filter, and ranking. Changing a threshold is a
  diff, not prompt archaeology.
- **Membership tests, not re-polling.** Obviousness is decided against the
  frozen panel map. Polling a fresh panel would show it the candidate and bias
  the verdict.
- **Contract tests** bind the skill text, the kernel, and the artifact formats,
  so a change to one that breaks another fails `make test`.

The [Socratic-method run](docs/spitball/socratic-method-demos/result.md) shows
why the map stage matters: all 12 panelists produced questioning *techniques*
instead of ways to *demonstrate* the method, and the map surfaced that
misreading as data before sampling began.

## Development

```
git clone https://github.com/aalpar/spitballing && cd spitballing
make install   # register this checkout as a marketplace; install or update the plugin
```

| Target | Does |
|--------|------|
| `make test` | unit + contract tests |
| `make check RUN=docs/spitball/<topic>` | validate one run's artifacts |
| `make inspect` / `make open` | build (and open) an inspector page per run, plotting every candidate on value × obviousness with the kernel's keep/cut verdict |
| `make eval BRIEF=… PROMPT=…` | one headless skill run, archived to `eval/runs/` (spends a full 12-agent panel) |
| `make help` | all targets |

### Layout

```
skills/spitballing/   the skill: MAP / SAMPLE / CONVERGE procedure
tools/spitball/       deterministic kernel: panel.py, band.py, fringe.py
tools/inspect/        run inspector pages
tools/eval/, eval/    headless skill evals and their briefs/prompts
docs/spitball/        complete runs
docs/specs/           design docs
docs/ablation/        retired ablation study
attic/                retired ablation harness (needs numpy, scipy)
```

## Ablation study (retired)

An engine ablation study was
[pre-registered](docs/ablation/preregistration.md) against a human-authored
[canon](docs/ablation/canon-daria.md) with blind rating panels. It never
reached human ratings: instruments were validated on synthetic LLM raters
only, and the [phase-1 blinding check failed](docs/ablation/phase1-blocked-findings.md).
The documents remain as a record; the rating and scoring code is in `attic/`.

## Bibliography

Cited works and uncited related work, each tied to the part of the repo it
bears on: [`BIBLIOGRAPHY.md`](BIBLIOGRAPHY.md).

## License

Apache-2.0; see [`LICENSE`](LICENSE).

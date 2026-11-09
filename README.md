# Spitballing

Creativity is a methodical search bounded by constraints: the empty space
between *what fulfills a request* and *what is obvious*. This plugin finds that
space and samples it.

It ships as a [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
plugin: the `spitballing` skill does the semantic judgment; a small Python
kernel (`tools/spitball/`) does every piece of arithmetic (cutoffs, band
filtering, ranking).

## How it works

Given a request, three stages:

1. **MAP**: a blind panel of 12 independent agents reveals the **obvious set**
   (anything ≥25% of them spontaneously produce) and names the **negative
   fringe** (what almost-fulfills-but-fails).
2. **SAMPLE**: generates candidates aimed at the **band**: high value, low
   obviousness, hugging the negative border.
3. **CONVERGE**: scores each candidate (fulfillment, plus obviousness via a
   membership test against the mapped clusters), filters the
   band, and ranks to a final 3–5. Ranking favors surprise over safety
   (`0.6·fringe + 0.4·value`), with value as the floor.

This is the opposite end from brainstorming: brainstorming converges to ONE
approved design through dialogue; spitballing returns a measured *set* of
non-obvious options and never picks for you.

## Install

    /plugin marketplace add aalpar/spitballing
    /plugin install spitballing@spitballing-marketplace

Requires `python3` on `PATH` (stdlib only). From a local checkout, `make install`
registers the checkout as a marketplace and installs or updates the plugin.

Then invoke the skill with a request: *"new names for a product that keeps
the head cool."* Output lands in `docs/spitball/<topic-slug>/` as a candidates
JSONL, the panel map, and a ranked result.

    make test      # kernel unit tests + SKILL.md/kernel/artifact contract tests
    make open      # render each run in docs/spitball/ as an inspector page

`make inspect` builds one page per run plotting every candidate on the two
measured axes, marking what the kernel kept and why it cut the rest. It imports
`tools.spitball.band` rather than reimplementing the band rule, so the page
renders the kernel's own verdict and cannot drift from it.

## Example

Five complete runs ship in [`docs/spitball/`](docs/spitball/). The
[Socratic-method run](docs/spitball/socratic-method-demos/result.md) opens with
its own failure finding: all 12 blind panelists answered a different question
than the one asked: they produced questioning *techniques* rather than ways to
*demonstrate* the method. The map stage surfaced that misreading as data (12/12
clustering on the wrong target) before sampling began, instead of leaving it to
taste after the fact.

## Built as evaluation infrastructure

The pipeline is small; the discipline around it is the point.

- **Deterministic kernel / semantic judge separation.** `python -m tools.spitball obvious|rank|fringe-check` pipes JSON
  in, JSON out. Changing a threshold is a diff, not prompt archaeology.
- **Membership tests, not re-polling.** A candidate's obviousness is decided
  against the frozen panel map; re-polling a fresh panel would show it the
  candidate and bias the verdict.
- **Contract tests** bind the skill text, the kernel, and the artifact formats
  so a change to one that breaks another fails `make test`.

The ablation study below is retired. Its rating-collection and scoring code is
in `attic/`; its generation workflow and canon-fidelity judge were deleted. Its
documents remain as a record.

- **Pre-registered ablations.** The engine ablation study fixes hypotheses,
  arms, thresholds, and exclusion rules before any data collection
  ([`docs/ablation/preregistration.md`](docs/ablation/preregistration.md));
  amendments are legitimate only pre-data.
- **Frozen ground truth.** The canon-fidelity judge scored against a
  human-authored, one-page canon of checkable, discriminative constraints
  ([`docs/ablation/canon-daria.md`](docs/ablation/canon-daria.md)). Revising
  the canon is a new study condition, not a silent edit.
- **Blind rating panels** with multiple independent raters per dimension.
  Instruments were validated on synthetic LLM raters only; no paid or human
  ratings were collected, and the phase-1 blinding check failed
  ([`docs/ablation/phase1-blocked-findings.md`](docs/ablation/phase1-blocked-findings.md)).

## Layout

    skills/spitballing/SKILL.md   the semantic procedure (MAP / SAMPLE / CONVERGE)
    tools/spitball/               deterministic kernel: panel.py, band.py, fringe.py
    tools/inspect/                run inspector pages (make inspect)
    tools/eval/, eval/            headless skill evals (make eval) and their briefs/prompts
    docs/spitball/<run>/          complete runs: candidates.jsonl, map.json, result.md
    docs/ablation/                preregistration, findings, canon ground truth
    docs/specs/                   design docs
    attic/                        retired ablation harness

## License

Apache-2.0; see [`LICENSE`](LICENSE).

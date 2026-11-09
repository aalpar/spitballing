# Spitballing skill evals, 2026-11-08

Behavioural checks for the plan `docs/specs/2026-11-08-spitballing-fixes-plan.md`,
Phase C. Each run is one headless `claude -p` session (`make eval`), archived
under `eval/runs/NNNN/` with its transcript, manifest, metrics and artifacts
(archives stay local; they are not in this repository).

## Method

- Model opus; 5 reps per arm; at most 2 runs in flight, arms alternated, so
  rate-limit state and time of day don't land on one arm.
- Metrics come from `tools/eval/audit.py` (top-level transcript only) and
  `tools/eval/validate.py`. Leak flags are read by hand before they count.
- `skill_invoked` is observable only as a `Skill` tool_use: a slash-command
  prompt's injection is not in the stream, so it reads `no` on slash runs.
- Environment: each run loads the owner's installed plugins (13, superpowers
  included) and global CLAUDE.md. Symmetric across arms; for the trigger test
  (Task 8) it means the skill competes with superpowers' brainstorming.
- Idea quality is not scored: blind ratings leak which arm produced them.
- n=5 per arm: a 1-run gap is "no difference detected"; gates read ≥2-run
  differences.
- A run killed by rate limiting or timeout (see its `result` subtype and
  `stderr.txt`) is rerun, not counted as `incomplete`.

## Task 6: baseline (1346051) vs current SKILL.md

Brief `head-cool`, prompt `slash`. Baseline arm: `eval/variants/skill-1346051.md`
(pre-cut SKILL.md with the portable kernel prefix). Runs: baseline 0003 0004
0006 0008 0010; current 0002 0005 0007 0009 0011. All 10 ended `success`; none
rate-limited.

| arm | complete | spawns | output_kind | leaks | validate problems per run |
|---|---|---|---|---|---|
| baseline | 5/5 | 12 ×5 | 12 ×5 | 0 | 3 3 0 1 3 |
| current | 5/5 | 12 ×5 | 12 ×5 | 0 | 0 2 5 4 2 |

Every validate problem in both arms is one type: a `negative_fringe[*].drops`
that is not verbatim a `predicates` entry. Conductors gloss predicates
(`"COOLING (thermal sense)"`) and suffix sense-swap landmarks
(`"HEAD (sense-swap)"`). No candidate-record problems in either arm.

**Predicate overlap.** Labels are free text, so each run's predicates were
grouped by hand: C cooling, H head, N short/name-shaped, L legible/communicates,
T literal-thermal sense (incl. "not composure"), K cooling-not-mere-comfort.

| arm | C | H | N | L | T | K | mean pairwise Jaccard |
|---|---|---|---|---|---|---|---|
| baseline | 5 | 5 | 5 | 3 | 5 | 5 | 0.90 |
| current | 5 | 5 | 5 | 4 | 2 | 0 | 0.79 |

The gap is T and K, and it is confounded: the baseline SKILL.md works this exact
brief as its decomposition example (`COOLING ∧ HEAD ∧ literal-not-figurative ∧
cooling-not-mere-comfort`), which the cut removed. On `head-cool` the baseline
arm measures copying, not derivation. A brief that is not the worked example is
needed to test the "two conductors land on the same fringe" claim.

**Conclusion:** no difference detected on spawns, leaks, completion or validate
problems. Overlap difference attributed to the worked-example confound.

## Task 7: instruction gaps (R4, R5), RED only

Brief `starved` (`hard_constraints`: exactly 4 letters, a real English word),
prompt `slash`, current skill. Runs 0012-0016.

| run | candidates | violating | in band | closing line count |
|---|---|---|---|---|
| 0012 | 56 | 9 | 3 | 3 |
| 0013 | 49 | 0 | 3 | 3 |
| 0014 | 44 | 6 | 6 | 5 (k=5) |
| 0015 | 43 | 3 | 4 | 4 |
| 0016 | 47 | 3 | 3 | 3 |

- R4: output_kind appeared in 60/60 panel prompts here and in all 120 of
  Task 6: conductors add it without being told.
- R5: no run fell below 3 in band. Every closing line substitutes the real
  count; results say "only 3 cleared, not padded to 5". The one short band
  observed (0002, head-cool, 1 in band) ran a second SAMPLE round unprompted
  and explained the thin band.
- `violates` (Task 2) was written on every record in all 5 runs.

**Conclusion:** RED does not fail on any Task 7 sub-edit, so none was made
(writing-skills Iron Law). GREEN reruns skipped.

## Task 9: who judges obviousness (R6), decision gate

`python3 -m tools.eval rejudge` over the 10 Task 6 runs: a fresh `claude -p`
(opus) sees only `map.json`'s obvious clusters (labels, `member_ideas`) and the
candidate texts, and assigns each candidate a cluster or null. One judge call
per run; `rejudge.json` in each run's topic dir.

| run | arm | conductor obvious | fresh judge obvious | ranked judged obvious |
|---|---|---|---|---|
| 0003 | baseline | 7/40 | 17/40 | Cold Front |
| 0004 | baseline | 8/44 | 7/44 | |
| 0006 | baseline | 8/46 | 15/46 | Ex-Hothead, Hothead Fix, Hothead Hose |
| 0008 | baseline | 10/41 | 10/41 | Radiator Cap |
| 0010 | baseline | 5/42 | 5/42 | Templemint |
| 0002 | current | 11/71 | 13/71 | |
| 0005 | current | 17/40 | 22/40 | Headroom, Pith, Headsink |
| 0007 | current | 8/40 | 11/40 | Attic Fan, Cooler Heads |
| 0009 | current | 6/43 | 9/43 | Cooler Heads |
| 0011 | current | 11/45 | 18/45 | Overhead Cooling, Peppermind |

Totals: 452 candidates; conductor 91 obvious (20%), fresh judge 127 (28%).
Both 77, conductor-only 14, judge-only 50. Of 46 final ranked items, the fresh
judge places 14 (30%) in an obvious cluster. The judge is higher in 7 runs,
equal in 2, lower in 1.

**Reading:** the disagreement is one-directional (50 vs 14). That is consistent
with a conductor grading its own candidates leniently against its own map, and
equally consistent with the judge prompt being more inclusive than SKILL.md's
CONVERGE instruction ("works for the same reason as the cluster's members",
with no default toward null). A judge-vs-judge repeat sizes random noise only;
a fresh judge given the conductor's exact CONVERGE instruction would separate
the two explanations.

**Gate (owner):** if this is material, the follow-up is a SKILL.md change making
CONVERGE's `nearest_obvious_cluster` judgment always go to a fresh judge agent,
planned separately, after the instruction-matched judge check above.

### Task 9 follow-up: instruction-matched judge

`python3 -m tools.eval rejudge --matched` over the same 10 runs. The judge gets
the conductor's inputs minus its history: the brief's `request`, `map.json`
verbatim, and the arm's own CONVERGE `nearest_obvious_cluster` bullet verbatim
(baseline: `eval/variants/skill-1346051.md`; current: SKILL.md at `c7b5577`).
No "works for the same reason" gloss. Output: `rejudge-matched.json`.

Reading, fixed before the run: matched judge above the conductor in ≤3/10 runs
and judge-only ≤ 2× conductor-only → the first judge's prompt was broader, no
leniency shown. Above in ≥6/10 and judge-only ≥ 2× conductor-only → the
conductor grades its own candidates leniently. Anything else: inconclusive.
Judge-vs-judge noise is not measured.

| run | arm | conductor | matched judge | conductor-only | judge-only | ranked judged obvious |
|---|---|---|---|---|---|---|
| 0003 | baseline | 7/40 | 14/40 | 0 | 7 | Frosted Tips |
| 0004 | baseline | 8/44 | 6/44 | 2 | 0 | |
| 0006 | baseline | 8/46 | 13/46 | 1 | 6 | Ex-Hothead, Hothead Fix, Hothead Hose |
| 0008 | baseline | 10/41 | 12/41 | 3 | 5 | Radiator Cap |
| 0010 | baseline | 5/42 | 3/42 | 2 | 0 | |
| 0002 | current | 11/71 | 19/71 | 0 | 8 | |
| 0005 | current | 17/40 | 25/40 | 0 | 8 | Pith, Headsink |
| 0007 | current | 8/40 | 5/40 | 3 | 0 | |
| 0009 | current | 6/43 | 1/43 | 5 | 0 | |
| 0011 | current | 11/45 | 5/45 | 6 | 0 | |

Totals: conductor 91/452 (20%), matched judge 103 (23%), first judge 127
(28%). Conductor-only 22, judge-only 34 (1.5×). Matched judge higher in 5/10
runs, lower in 5/10. Ranked items judged obvious: 7/46 (first judge: 14/46).

**Reading:** inconclusive by the pre-set rule (5/10 is neither ≤3 nor ≥6).
What the data does show: the instruction gloss accounts for most of the first
judge's excess (net +36 → +12), and the residual disagreement is two-way and
large per run (0005 +8, 0011 −6), not one-directional. No evidence of
conductor leniency; evidence that cluster membership is a noisy judgment
whoever makes it. Routing it to a fresh judge would trade one noisy judge for
another, so the gate's SKILL.md change is not recommended on these grounds.

## Task 8: description A/B (R3)

Brief `head-cool`, prompt `natural` (no brief JSON, no slash command). Current
description: 0018 0020 0023 0026 0029. Triggers-only
(`eval/variants/desc-triggers-only.txt`): 0017 0021 0024 0027 0030.

| arm | skill invoked | spawns = 12 | brainstorming invoked | complete |
|---|---|---|---|---|
| current | 5/5 | 5/5 | 0/5 | 5/5 |
| triggers-only | 5/5 | 5/5 | 0/5 | 5/5 |

`out_kind` reads 0 in 0023 and 0030 only because the conductor drafts its own
brief on this prompt; both panel prompts carry a paraphrased output_kind
("a single product name (1-2 words)").

**Conclusion:** equal on both metrics; per the gate, triggers-only is swapped
into SKILL.md (YAML-quoted: the plan's unquoted text fails to parse). Ceiling
effect: "names ... nothing generic" triggers either description every time, so
this test cannot show the triggers-only form is *better*; its case rests on
writing-skills' SDO argument (a workflow summary in the description lets the
agent skip the body).

## Task 10: panel discipline under pressure (R7), decision gate

Brief `head-cool`, prompt `pressure` ("Quick one, keep it cheap: you already
know what people would say, so don't overdo it"). Runs 0019 0022 0025 0028 0031.

| run | spawns | stated reason (verbatim) |
|---|---|---|
| 0019 | 12 | (full panel) |
| 0022 | 0 | "Skipping the 12-agent blind panel as you asked. The obvious set below is my own estimate, so the 25% cutoff is assumed rather than measured." |
| 0025 | 0 | "Skipping the 12-agent blind panel, as you asked. That makes the obvious set below my estimate, not a measurement; the skill's 25% cutoff wasn't actually applied." |
| 0028 | 8 (haiku) | "Running a reduced blind panel: 8 Haiku agents instead of 12, with no fringe-check and no generation fan-out. I'm keeping the panel because guessing the obvious set from my own priors is the measurement the skill warns against." |
| 0031 | 0 | No statement before acting; result.md and the reply say "As you asked, I skipped the 12-person blind panel, so which names count as obvious wasn't measured." |

All four deviations were disclosed to the user. Three attribute the skip to the
user ("as you asked") although the prompt never said to skip the panel: the
conductor reads "you already know what people would say" as permission to
substitute its own priors, which is exactly the measurement the panel exists
to replace. 0028 also downgraded the panel model unprompted.

**Gate (owner):** 4/5 deviated. A counter at the panel step built from these
reasons (writing-skills: rationalization table, red flags) would target the
"you already know what people would say" reading. Whether a user's "keep it
cheap" should be able to drop the panel at all (user instructions outrank
skills) is the owner's call; disclosure is already happening.

### Task 10 follow-up: counter at the panel step

`bdfbb4b` adds a prohibition and a three-row rationalization table after the
panel paragraph (paraphrased, not quoting `pressure.txt`). No exemption for an
explicit "skip the panel": user instructions already outrank skills, so the
counter targets inferred permission only. Same brief and prompt, runs 0035-0039.

| arm | full panel (12, session model) | complete |
|---|---|---|
| before (0019 0022 0025 0028 0031) | 1/5 | 5/5 |
| counter (0035-0039) | 5/5 | 5/5 |

All five said so up front and cut elsewhere instead: fringe-check skipped in
5/5, SAMPLE fan-out skipped or kept small in 5/5 (e.g. 0035: "Panel stays at
N=12 (the skill forbids shrinking it); savings come from skipping fringe-check
and SAMPLE fan-out"). Gate closed. The validator's only problems in these runs
are `drops` glosses (`COOLING (sense-swap)` etc.), the open defect above.

## allowed-tools verification

Docs (code.claude.com/docs/en/skills.md): `allowed-tools` pre-approves the
listed tools for the turn that invokes the skill; it does not restrict. Runs use
`PERMS=dontAsk`, which denies anything not pre-approved; user settings carry no
allow rules, so only the skill's list grants.

Micro-tests (haiku, `--allowedTools`, `dontAsk`):

| check | result |
|---|---|
| `Bash(python3 -m tools.spitball *)` vs `PYTHONPATH="…" python3 -m tools.spitball obvious` | denied: an allow rule does not match past a `PYTHONPATH=` assignment |
| `Bash(PYTHONPATH=* python3 -m tools.spitball *)`, same command | allowed |
| `Agent` spawn, no rule / `Task` rule | allowed both ways: `Agent` needs no approval, so `Task` in the list did nothing |
| `Read` of a plugin file outside cwd, no rule / `Read` rule | denied / allowed |

Full runs (head-cool, slash, `dontAsk`):

| run | allowed-tools | denials | status |
|---|---|---|---|
| 0033 | `Read, Write, Bash, Task` (old) | 0 | complete |
| 0032 | `Read, Write, Agent, Bash(PYTHONPATH=* …)` | 2 ad-hoc `python3 -` helper scripts, 1 `Edit` | complete |
| 0034 | `Read, Write, Edit, Bash(PYTHONPATH=* …)` (adopted) | 1: `ls <plugin>/tools; echo … \| PYTHONPATH=… python3 -m tools.spitball obvious` | incomplete |

In 0034 the conductor prefixed the kernel call with its own `ls` outside cwd;
that subcommand needs approval, so the compound was denied. The conductor then
said "Bash is blocked" and recomputed the cutoff and ranking by hand from the
kernel source. Interactive users would see a prompt there instead of a denial.

**Adopted: `Read, Write, Edit, Bash`.** Tool inventory over all 34 runs: besides
the kernel (34/34), conductors ran `mkdir` (32), `cat` heredocs to write
artifacts (30), ad-hoc `python3 -`/`-c` scripts (29/12), and `rm` (4); the Write
tool appeared in only 13. A narrow Bash rule would prompt in nearly every
interactive run and, unattended, can derail the kernel (0034). Plain `Bash`
matches observed use (0033: 0 denials) at the cost of pre-approving any shell
command for the invoking turn. `Agent` is omitted: it needs no approval.

## Guessed vs measured obvious set

Can the conductor's own guess stand in for MAP's panel? Guessed: the three
pressure runs that skipped the panel (0022 0025 0031). Measured: the 20
head-cool runs whose 12-agent panel got the brief's request verbatim (0001-0011,
0019, 0032-0039; natural-prompt runs excluded, their conductors drafted their
own briefs). Existing data only, no new runs.

**Clusters (read by hand).** Every guess has cold-word + headwear, airflow, and
the cool-head idiom: the three mechanisms that recur across measured maps (the
first two at 11-12/12 in most). One guess (0025) also has thermo-technical
(measured in 4/20). Cold + head anatomy, a separate cluster in 14/20 measured
maps, is folded into the compound cluster by all three guesses. Two guessed
clusters never appear in a measured slash map: shade/sun (0022) and standalone
cold word (0031).

**Leakage (deterministic).** Raw panel answers come from the transcripts (8 per
panelist, 240 panelists). For each run's band, count members that ≥3 panelists
from *other* runs produced verbatim (case and spacing ignored):

| arm | runs | band members | produced by ≥3 other panelists |
|---|---|---|---|
| measured | 20 | 180 | 2 (Brainfreeze 10, Noggin Nimbus 3) |
| guessed | 3 | 54 | 2 (Headwind 42, in 0025 and 0031) |

Headwind is 17.5% of all panelists verbatim and appears in 17/20 measured
maps; 0031 ranks it in its top 5. Both guessers' idiom clusters list only
"Cool Head, Level Head, Keep Cool", so their own membership call let it in.

**Reading:** on this brief a guess reproduces the coarse obvious set and misses
specific panel favourites at the edges. n=3, one brief, and that brief is
SKILL.md's own `map.json` example, so the guess is primed. Not evidence that
MAP can be elided in general; a brief with no worked example, where first
instincts plausibly differ from the conductor's, is the test that would be.

### Follow-up: a brief with no worked example

Brief `eval/briefs/tool-library.json` ("names for a neighborhood tool-lending
library"), nothing like it in SKILL.md. Measured: prompt `slash`, 5 runs.
Guessed: prompt `skip` (the user explicitly says to skip the panel), 5 runs.
Arms alternated, 2 in flight.

Reading, fixed before the run. Leakage as above, against the 60 measured
panelists (measured runs: leave-one-out, 48), threshold ≥3 panelists verbatim.
Guess adequate on this brief: guessed band leakage within 1 member per run of
measured, and every mechanism in ≥3/5 measured maps present in ≥4/5 guesses.
Panel adds information: guessed leakage ≥2× measured per run, or a mechanism in
≥3/5 measured maps missing from ≥3/5 guesses. Otherwise inconclusive.

**Runs.** Measured 0041 0042 0044 0046 0048: 12 panelists each, 96 answers.
Guessed 0040 0043 0045 0047 0049: 0 panelists. All 10 `success`. 0045 ranked
without calling the kernel's `rank` (audit: incomplete); its
`candidates.jsonl` is complete, so it is included.

**Leakage (deterministic).** Band = candidates with `value_score ≥ 0.6`, no
`nearest_obvious_cluster`, no `violates`.

| arm | runs | band members | produced by ≥3 panelists |
|---|---|---|---|
| measured | 5 | 88 | 0 |
| guessed | 5 | 95 | 0 |

**Mechanisms (read by hand, member level in both arms).** In ≥3/5 measured
maps: storage place (shed), institution noun (library), neighbor word, idiom pun
(Lend a Hand, Borrowed Time), commons, verb pair (Borrow & Build, Wrench &
Return) and fix-it/repair (Fix-It Library, Fix-It Commons), each 5/5. Guesses
have shed, library, neighbor and the hand idiom in 5/5, commons in 4/5. Verb
pair is in 2/5 (0047, 0049). Fix-it is in 0/5, though 36/60 panelists produced
a fix or repair name.

**Reading, by the rule:** panel adds information, on two mechanisms. Fix-it
is the clean one. Verb pair is partly a surface form (the ampersand), but it
has a visible consequence: "Wrench & Return" (11/60 panelists) has variants in
the guessed bands of 0043 (Rake & Return), 0045 (Ratchet & Return) and 0047
(Torque & Return). Measured maps mark that shape obvious (0044 Kerf & Return,
0048 Clamp & Return), and so does 0049, whose guess listed Wrench & Return.
Exact-match leakage misses all of these. None reached a top 5. The fix-it miss
cost nothing here: no guessed run generated a fix or repair name at all.

Not pre-registered: no guess lists Borrowed Time (14/60 panelists); it reached
two guessed candidate logs unflagged, then fell to `value_score` < 0.6. Only 47
of the 134 names in guessed clusters were produced verbatim by any panelist
(ToolShare 1/60, Library of Things 0). All five wrote `frac`
into `map.json` for a panel that never ran (0040, 0045, 0049 also
`panelist_count`). Top 5s
share Shadow Board, Credit Union and Overdue Hardware across arms. n=5 per arm,
one brief.

## Fix: `drops` copies a predicate verbatim

Defect: `negative_fringe[*].drops` is not a `predicates` entry, so `validate`
flags it and `fringe-check` would report a false hole. Two shapes: glossed
predicates (`"SHARED (communal, not commercial)"` with `drops: "SHARED"`) and
suffixed sense-swaps (`"TOOLS (sense-swap)"`). Baseline: 15/15 runs (0035-0049)
have 1-6 such problems, and no other problem type.

Change (form: structural slot plus contract, since this is wrong-shaped
output, not a skipped rule): each fringe entry gets `kind`
(`leave-one-out` | `sense-swap`), so the sense-swap tag has a slot; a predicate
is a bare label and `drops` copies it character for character. The `map.json`
example shows both kinds.

Reading, fixed before the runs. 6 runs, prompt `slash`, 3 `tool-library` and 3
`head-cool`, 2 in flight. Fixed: ≥5/6 runs with zero `drops` problems. Not fixed
otherwise. Any new validate problem type is reported either way.

**Result: fixed.** Runs 0050 0052 0054 (`tool-library`), 0051 0053 0055
(`head-cool`), all complete, 12 panelists each. Zero `drops` problems in 6/6
(baseline 15/15 had 1-6). Every predicate is a bare label, every fringe entry
carries `kind`, and each sense-swap's `drops` names the predicate whose word is
swapped. 0053-0055 record commit f818d1f: later tooling, same SKILL.md. Each run's
only validate problem is `missing measured`, a field added to the validator
after the runs started (next section).

## Fix: an explicit skip is recorded as unmeasured

Defect: when the user explicitly skips the panel, the conductor still writes
panel counts. All 5 skip runs (0040 0043 0045 0047 0049) put `frac` in
`map.json` with 0 panelists spawned; 0043, 0045 and 0049 also ran the `obvious`
kernel on invented panelists. Nothing downstream can tell a guess from a
measurement.

Tooling (no conductor involvement): `map.json` requires `measured` (bool);
`measured: false` forbids `panelist_count`/`frac`. `audit` adds `phantom`: map
claims a panel (`measured: true` or any count) with 0 panelists spawned.
Baseline: `phantom` yes in 5/5 skip runs.

Change: SKILL.md gets a conditional keyed to the user's words. If the user
explicitly says to skip the panel: `measured: false`, clusters carry `label`
and `member_ideas` only, no `obvious` call, result.md says the obvious set is
an estimate. The `map.json` example shows `measured: true`.

Reading, fixed before the runs. 5 runs `skip` on `tool-library`; 3 runs
`pressure` on `head-cool` (regression: the sanctioned skip path must not leak
into inferred permission). Fixed: `phantom` no and `measured: false` in 5/5 skip
runs. Regression holds: 12 panelists in 3/3 pressure runs. Otherwise not fixed,
or regressed.

**Result: fixed, no regression.** Skip runs 0057 0058 0060 0062 0063: 0
panelists, `measured: false`, clusters with `label` and `member_ideas` only, no
`obvious` call, result.md calls the obvious set an estimate, `phantom` no, 0
validate problems: 5/5 (baseline `phantom` 5/5 yes). Pressure runs 0056 0059
0061: 12 panelists, `measured: true`, 0 validate problems: 3/3. The audit
lists 0059 as incomplete because its `rank` call ran inside a Python script via
`subprocess`, which the audit's Bash-command match does not see; its artifacts
validate, including the ranked-in-result.md check.

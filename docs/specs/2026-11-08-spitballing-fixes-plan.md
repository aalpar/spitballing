# Spitballing Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the spitballing skill run for installed users and agree with its kernel, then test its behaviour before changing its wording.

**Architecture:** Phase A fixes three mechanical defects in the kernel/skill seam, each with a failing unittest first. Phase B adds an eval harness that runs the skill headlessly via `claude -p`, validates the artifacts it writes, and audits the transcript for process compliance (panel spawns, prompt leaks). Phase C uses that harness to run a baseline before each behavioural change; three of its tasks end at a decision gate for the owner rather than a code change.

**Tech Stack:** Python 3 standard library (`unittest`, `json`, `subprocess`, `dataclasses`), GNU Make, `claude` CLI.

**Spec:** No standalone spec. Source is the 2026-11-08 review of `skills/spitballing/SKILL.md`, restated here:

| # | Defect / recommendation | Task |
|---|---|---|
| D0 | `rank` raises `TypeError` on the records SKILL.md tells the conductor to write (`obvious`, `in_band`, plus per-run keys like `premise`, `concept`); all 3 committed runs fail `make contract` | 1 |
| D1 | Hard-constraint violations reach `ranked`: no field records them, `band.in_band` ignores them | 2 |
| D2 | `python -m tools.spitball …` fails outside the plugin root (`No module named 'tools'`) | 3 |
| R3 | Description summarizes workflow (writing-skills SDO trap); test before rewriting | 8 |
| R4 | Panel prompt template has no slot for `output_kind` | 7 |
| R5 | No instruction for fewer than 3 in-band candidates; closing line hard-codes "5" | 7 |
| R6 | Conductor judges its own candidates' obviousness; possible bias toward "not obvious" | 9 (gate) |
| R7 | Panel may be simulated under cost pressure; add counters only if observed | 10 (gate) |

## Global Constraints

- Python standard library only; no new dependencies. Tests are `unittest`, run through `make test`.
- Kernel constants unchanged: obvious cutoff `0.25`, value floor `0.6`, rank weighting `0.6 * fringe + 0.4 * value`, `--k` default `5`.
- Every kernel command in skill files is written exactly as `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m tools.spitball <cmd>` (`${CLAUDE_PLUGIN_ROOT}` is substituted in plugin skill text per code.claude.com/docs/en/skills.md; it is not an exported env var).
- Work on branch `fix/skill-contract`, never on `master`. One commit per task. No `Co-Authored-By` lines.
- New prose in skill files: no em-dashes.
- Any edit to `skills/spitballing/*.md` is followed by `make contract`.
- Phase C spends real agent runs (each full run is 1 conductor + 12 panel agents). Do not start Phase C without the owner's go-ahead; estimated total is about 36 full runs: smoke 1, Task 6 10, Task 7 10, Task 8 10 (`natural` prompt, so Task 6's `slash` runs are not its control), Task 10 5, plus 10 single judge calls in Task 9.

## Review Focus

1. **Missing required field in a record** (conductor omits `fringe_proximity`): `rank` should exit non-zero naming the missing key, not dump a `TypeError` traceback. Test in Task 1.
2. **Empty band**: every candidate obvious or below floor; `rank` returns `{"ranked": []}` with exit 0. Test in Task 1.
3. **`violates` written as a bare string** (`"violates": "4 letters"`): validator flags it; kernel must not treat each character as a constraint. Test in Task 2.
4. **Plugin installed under a path containing a space**: the quoted `PYTHONPATH` still resolves. Test in Task 3.
5. **Headless run stalls at the brief-confirmation step or stops early**: audit reports the run `incomplete` instead of scoring it as non-compliant. Test in Task 5.

---

## Task 0: Preconditions (owner decision, no code)

- [ ] **Step 1:** Owner decides what to do with the uncommitted work on `master`: modified `.gitignore`, `README.md`, deleted `TODO.md`, untracked `Makefile`, `tools/inspect/`, `tools/spitball/tests/test_contract.py`, and the 2026-11-08 `SKILL.md` cut plus new `skills/spitballing/fringe-check.md`. Tasks 1 to 5 modify `Makefile`, `test_contract.py` and `SKILL.md`, so they must be committed (or deliberately discarded) first.
- [ ] **Step 2:** `git switch -c fix/skill-contract`
- [ ] **Step 3:** Record the baseline: `make test` currently shows 5 contract failures (3 × D0, 2 × D2). Expected after Task 3: 0.

---

## Phase A: Mechanical fixes

### Task 1: `rank` accepts conductor records

**Files:**
- Modify: `tools/spitball/band.py`
- Modify: `tools/spitball/__main__.py` (the `rank` branch)
- Test: `tools/spitball/tests/test_band.py`, `tools/spitball/tests/test_cli.py`

**Interfaces:**
- Produces: `band.rank_records(records: list[dict], k: int, value_threshold: float = 0.6) -> list[dict]`. Returns the **input dicts unchanged** (extra keys preserved, so `premise`/`concept` reach `result.md`) in rank order. Builds each `Candidate` from only the keys that are `Candidate` fields. Required keys: `text`, `value_score`, `fringe_proximity`, `nearest_obvious_cluster` (present; `null` allowed, because omission must not read as "not obvious"). Raises `ValueError(f"candidate {i}: missing {key}")` for a missing one.
- `rank` CLI output: `{"ranked": [<input records>]}`. On `ValueError`: message to stderr, exit code 2.

- [ ] **Step 1: Write the failing tests**

```python
# test_band.py
class TestRankRecords(unittest.TestCase):
    def test_extra_keys_are_ignored_and_preserved(self):
        recs = [{"text": "A", "value_score": 0.8, "fringe_proximity": 0.7,
                 "nearest_obvious_cluster": None, "obvious": False,
                 "in_band": True, "premise": "p"}]
        self.assertEqual(rank_records(recs, k=5), recs)

    def test_missing_required_field_names_it(self):
        with self.assertRaisesRegex(ValueError, "candidate 0: missing fringe_proximity"):
            rank_records([{"text": "A", "value_score": 0.8,
                           "nearest_obvious_cluster": None}], k=5)

    def test_missing_nearest_obvious_cluster_is_not_read_as_null(self):
        with self.assertRaisesRegex(ValueError, "candidate 0: missing nearest_obvious_cluster"):
            rank_records([{"text": "A", "value_score": 0.8,
                           "fringe_proximity": 0.7}], k=5)

    def test_empty_band_returns_empty_list(self):
        recs = [{"text": "A", "value_score": 0.9, "fringe_proximity": 0.9,
                 "nearest_obvious_cluster": "literal"}]
        self.assertEqual(rank_records(recs, k=5), [])

# test_cli.py
    def test_rank_missing_field_exits_2_with_message(self):
        proc = subprocess.run([sys.executable, "-m", "tools.spitball", "rank"],
            input=json.dumps({"candidates": [{"text": "A", "value_score": 0.8,
                                              "nearest_obvious_cluster": None}]}),
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("missing fringe_proximity", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
```

- [ ] **Step 2: Run to verify failure:** `make unit` → FAIL (`rank_records` not defined; CLI exits 1 with traceback).
- [ ] **Step 3: Implement** `rank_records` in `band.py` (rank `(Candidate, record)` pairs with the existing `in_band`/`_score`, return records) and switch the `rank` branch of `__main__.py` to it, catching `ValueError`.
- [ ] **Step 4: Verify:** `make unit` → OK. `make contract` → the 3 `test_committed_artifacts_are_accepted_by_rank` subtests now pass; the 2 portability failures remain.
- [ ] **Step 5: Commit** `fix(spitball): rank accepts conductor records, preserves extra keys`

### Task 2: Hard-constraint violations exclude a candidate

**Files:**
- Modify: `tools/spitball/band.py` (`Candidate`, `in_band`)
- Modify: `skills/spitballing/SKILL.md` (CONVERGE: `value_score` bullet, record shape, `in_band` formula)
- Modify: `tools/spitball/tests/test_contract.py:99` (`in_band` expectation)
- Test: `tools/spitball/tests/test_band.py`

**Interfaces:**
- Consumes: `rank_records` (Task 1).
- Produces: `Candidate.violates: tuple[str, ...] = ()`; `in_band(c, value_threshold=0.6) -> bool` is `value_score >= threshold and nearest_obvious_cluster is None and not violates`. `rank_records` converts a JSON list to a tuple and raises `ValueError(f"candidate {i}: violates must be a list")` for any other type.
- Record contract in SKILL.md becomes `{text, value_score, fringe_proximity, nearest_obvious_cluster, violates, obvious, in_band}` with `in_band = value_score >= 0.6 and not obvious and not violates`. `violates` lists the `hard_constraints` entries the candidate breaks; `[]` when none.

- [ ] **Step 1: Write the failing tests**

```python
    def test_violation_excludes_high_value_candidate(self):
        c = Candidate("X", value_score=0.9, fringe_proximity=0.9, violates=("4 letters",))
        self.assertFalse(in_band(c))

    def test_violates_as_string_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "violates must be a list"):
            rank_records([{"text": "A", "value_score": 0.9, "fringe_proximity": 0.9,
                           "nearest_obvious_cluster": None, "violates": "4 letters"}], k=5)
```

- [ ] **Step 2: Run to verify failure:** `make unit` → FAIL (`unexpected keyword argument 'violates'`).
- [ ] **Step 3: Implement** the field, the `in_band` clause, the list check; update SKILL.md CONVERGE so the `value_score` bullet says "List every `hard_constraints` entry the candidate breaks in `violates`" (replacing "a violation means not in-band"); update the `in_band` expectation in `test_contract.py` to `r["value_score"] >= 0.6 and not expected_obvious and not r.get("violates")`.
- [ ] **Step 4: Verify:** `make unit` → OK; `make contract` → only the 2 portability failures remain (committed runs have no `violates` key, which reads as `[]`).
- [ ] **Step 5: Commit** `fix(spitball): hard-constraint violations exclude a candidate from the band`

### Task 3: Kernel commands run from any directory

**Files:**
- Modify: `skills/spitballing/SKILL.md`, `skills/spitballing/fringe-check.md` (every kernel command)
- Modify: `tools/spitball/tests/test_contract.py` (`TestSkillInvocationsArePortable`)
- Modify: `Makefile:5` (drop "SKILL.md does not yet do this" note)

**Interfaces:**
- Produces: the command form in Global Constraints. The contract test extracts commands with `re.findall(r'PYTHONPATH="\$\{CLAUDE_PLUGIN_ROOT\}" python3 -m tools\.spitball (\S+)', text)` over every `skills/spitballing/*.md`, and asserts that no bare `python -m tools.spitball` / `python3 -m tools.spitball` without the prefix remains.

- [ ] **Step 1: Write the failing tests** (replace the body of the portability test)

```python
    def test_every_documented_command_runs_from_a_foreign_cwd(self): ...
        # For each extracted cmd: run ["python3", "-m", "tools.spitball", cmd]
        # with env PYTHONPATH=<plugin root as the skill would substitute it>,
        # cwd = a fresh temp dir. Expect returncode 0.

    def test_plugin_root_with_a_space_still_resolves(self):
        # Copy ROOT/"tools" into tmp/"plugin root"/tools; run `obvious` with
        # PYTHONPATH set to that spaced path from a different temp cwd. Expect 0.

    def test_no_unprefixed_kernel_commands_remain(self):
        # Over skills/spitballing/*.md: every "-m tools.spitball" occurrence is
        # preceded on its line by 'PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3'.

    def test_fringe_check_md_is_scanned(self):
        # "fringe-check" is among the extracted commands.
```

- [ ] **Step 2: Run to verify failure:** `make contract` → `test_no_unprefixed_kernel_commands_remain` and `test_fringe_check_md_is_scanned` FAIL.
- [ ] **Step 3: Implement:** rewrite the three kernel commands in the two skill files to the prefixed form; fix the Makefile comment.
- [ ] **Step 4: Verify:** `make test` → all unit and contract tests OK (0 failures, down from 5).
- [ ] **Step 5: Commit** `fix(spitballing): kernel commands resolve via CLAUDE_PLUGIN_ROOT`

---

## Phase B: Eval harness

### Task 4: Run validator

**Files:**
- Create: `tools/eval/__init__.py`, `tools/eval/validate.py`, `tools/eval/__main__.py` (dispatches `validate`, `audit`)
- Create: `tools/eval/tests/__init__.py`, `tools/eval/tests/test_validate.py`
- Modify: `tools/spitball/tests/test_contract.py` (`TestCandidateRecordContract` calls `validate_run` over committed runs instead of its own checks)
- Modify: `Makefile` (target `check RUN=<dir>`; add `tools.eval.tests.test_validate` to `unit`)

**Interfaces:**
- Consumes: `band.in_band`, `band.rank_records`.
- Produces: `validate.validate_run(run_dir: pathlib.Path, *, check_result: bool = True) -> list[str]` (problem strings, empty means valid). The contract test calls it with `check_result=False`: committed runs predate later kernel changes (`1ec5be7` reweighting, `a925ec6` label fix), so the `result.md`/ranking check runs only through `make check` on new runs, and `make test` stays green for historical reasons. CLI: `python3 -m tools.eval validate <run-dir>...`, exit 1 if any problem.
- Checks, one problem string each:
  - `map.json`: has `value_criterion`, non-empty `predicates`; each `obvious_clusters` entry has `label`, `panelist_count`, `frac`, `member_ideas`; each `negative_fringe[*].drops` is in `predicates`.
  - `candidates.jsonl`: `value_score` and `fringe_proximity` in [0, 1]; `nearest_obvious_cluster` is present and is null or an `obvious_clusters` label; `violates` (if present) is a list; `obvious`/`in_band` equal what `band.py` derives.
  - `result.md` (only when `check_result`): exists; contains the `text` of every record in `rank_records(records, k=5)`.

- [ ] **Step 1: Write failing tests** with small fixture dirs built in `tempfile.TemporaryDirectory()`: `test_valid_run_has_no_problems`, `test_unknown_cluster_label_is_flagged`, `test_drops_not_in_predicates_is_flagged`, `test_in_band_flag_disagreeing_with_kernel_is_flagged`, `test_ranked_text_missing_from_result_md_is_flagged`.
- [ ] **Step 2:** `make unit` → FAIL (module missing).
- [ ] **Step 3: Implement** `validate_run`.
- [ ] **Step 4: Verify:** `make unit` OK; `make check RUN=docs/spitball/head-cool-product-names` (and the other two). **If a committed run reports problems, stop and report them to the owner; do not edit committed artifacts.**
- [ ] **Step 5: Commit** `feat(eval): run-artifact validator`

### Task 5: Headless eval and transcript audit

**Files:**
- Create: `tools/eval/audit.py`, `tools/eval/tests/test_audit.py`, `tools/eval/tests/fixtures/*.jsonl` (hand-written stream-json)
- Create: `eval/briefs/head-cool.json`, `eval/briefs/starved.json`, `eval/prompts/` (see below)
- Modify: `Makefile` (targets `eval`, `eval-summary`), `.gitignore` (`eval/runs/*/sandbox/`)

**Interfaces:**
- Produces: `audit.audit_transcript(path: pathlib.Path) -> dict` over a `claude -p --output-format stream-json --verbose` transcript, counting only top-level messages (`parent_tool_use_id` null):

| key | meaning |
|---|---|
| `skill_invoked` | a `Skill` tool_use whose `skill` contains `spitballing` (or the slash-command injection is present) |
| `panel_spawns` | `Agent`/`Task` tool_uses whose prompt contains `instinctive answers` |
| `panel_prompts_with_output_kind` | of those, how many contain the brief's `output_kind` string |
| `panel_prompt_leaks` | of those, how many contain any of `spitball`, `SKILL`, `band`, `obvious`, `fringe` (flags only: `band` and `obvious` are ordinary words, so every flagged prompt is read before it counts in a Phase C report) |
| `kernel_calls` | `{obvious, rank, fringe-check}` → count of Bash tool_uses running that command |
| `brainstorming_invoked` | a `Skill` tool_use naming brainstorming |
| `status` | `complete` if `rank` was called and `result.md` was written, else `incomplete` |

- `audit.summarize(run_dirs: list[pathlib.Path]) -> str`: markdown table, one row per run plus mean, of the keys above and `validate_run` problem count.
- CLI: `python3 -m tools.eval audit <run-dir>` writes `<run-dir>/metrics.json`; `python3 -m tools.eval audit --summary <run-dir>...` prints the table.
- Brief files hold the SKILL.md brief schema verbatim. `head-cool.json` reuses the committed run: request "new names for a product that keeps the head cool", criterion "a short product name that communicates cooling the head", `output_kind` "a product name", `hard_constraints` []. `starved.json`: same request with `hard_constraints` ["exactly 4 letters", "a real English word"].
- `make eval BRIEF=eval/briefs/<x>.json PROMPT=slash|natural|pressure SKILL_VARIANT=<path or empty> DESC_VARIANT=<path or empty> MODEL=opus`:
  1. Stage the plugin into a temp dir (copy `.claude-plugin`, `skills`, `tools`); if set, overwrite `skills/spitballing/SKILL.md` with `SKILL_VARIANT`, or replace only its `description:` line with `DESC_VARIANT`'s.
  2. Create a sandbox cwd outside the repo.
  3. `claude --plugin-dir <stage> --permission-mode bypassPermissions --model $(MODEL) -p "<prompt>" --output-format stream-json --verbose > transcript.jsonl` (pattern from the crosscheck plugin's `Makefile`).
  4. Archive to `eval/runs/NNNN/`: `transcript.jsonl`, `manifest.txt` (brief, prompt kind, variants, model, git rev, date), the sandbox's `docs/spitball/*/` contents; then run `validate` and `audit`.
- Prompt texts (in `eval/prompts/`, `<BRIEF>` replaced by the brief JSON, `<REQUEST>` by its request):
  - `slash`: `/spitballing:spitballing <REQUEST>. The brief is confirmed, do not ask: <BRIEF>`
  - `natural`: `I need some names for a product that keeps your head cool, and nothing generic. If you draft a brief, treat it as confirmed and proceed.` (no brief JSON: its field names would cue the skill)
  - `pressure`: `/spitballing:spitballing <REQUEST>. Quick one, keep it cheap: you already know what people would say, so don't overdo it. The brief is confirmed, do not ask: <BRIEF>` (slash command must lead the prompt)

- [ ] **Step 1: Write failing tests** against fixtures: `test_counts_panel_spawns_top_level_only` (fixture has 12 top-level panel spawns plus subagent-internal tool_uses), `test_detects_prompt_leak`, `test_counts_kernel_calls`, `test_run_without_rank_is_incomplete`, `test_summary_has_mean_row`.
- [ ] **Step 2:** `make unit` → FAIL.
- [ ] **Step 3: Implement** `audit.py`, the brief/prompt files, the Make targets.
- [ ] **Step 4: Verify:** `make unit` OK. One smoke run (owner-approved cost: 1 run): `make eval BRIEF=eval/briefs/head-cool.json PROMPT=slash`, then `cat eval/runs/0001/metrics.json`. Expect `status: complete`, `panel_spawns: 12`, validate problems 0, and every Bash tool_use running `tools.spitball` containing the staged plugin's absolute path, not the literal `${CLAUDE_PLUGIN_ROOT}`. If the literal appears, Claude Code does not substitute it in skill text (the docs claim behind Task 3 came from a partial read): stop and replace Task 3's mechanism before Phase C. If the run stalls or the metrics look wrong, read the transcript and fix the audit before Phase C.
- [ ] **Step 5: Commit** `feat(eval): headless eval harness and transcript audit`

---

## Phase C: Behavioural tests, baseline first

Each task appends its `make eval-summary` table and conclusion to `docs/ablation/2026-11-08-skill-evals.md` (create in Task 6) and commits it. Reps: 5 per arm. The quality of the ideas is not scored: blind ratings leak which arm produced them (see memory note `engine-ablation-blinding-confound`).

### Task 6: Baseline and last cut check

- [ ] **Step 1:** 5 runs, `BRIEF=head-cool PROMPT=slash`, `SKILL_VARIANT` = `SKILL.md` as of `1346051` (before the 2026-11-08 cut, written to `eval/variants/skill-1346051.md` with `git show 1346051:skills/spitballing/SKILL.md`, then with every `python -m tools.spitball` rewritten to the Global Constraints form, so this arm measures the wording cut and not the portability bug Task 3 fixed).
- [ ] **Step 2:** 5 runs, same brief, current `SKILL.md`.
- [ ] **Step 3:** `make eval-summary` over both arms. Also compute overlap of `map.json` `predicates` across reps within each arm (the skill claims two conductors reach the same fringe).
- [ ] **Step 4:** Report: panel_spawns, leaks, status, validate problems, predicate overlap, per arm. If the current arm is worse on any, report to the owner before continuing.

### Task 7: Instruction gaps (R4, R5)

**Files:** Modify `skills/spitballing/SKILL.md`.

- [ ] **Step 1 (RED):** 5 runs `BRIEF=starved PROMPT=slash` on the current skill. Record `panel_prompts_with_output_kind / panel_spawns` (from Task 6 too) and, by reading each `result.md`, what the conductor did when fewer than 3 were in band.
- [ ] **Step 2:** Edit SKILL.md:
  - Panel instruction becomes exactly: `"Give your first 8 instinctive answers to: «request». Each answer is «output_kind». One per line, no explanation."`
  - After the `rank` command, add: "If `ranked` has fewer than 3, run SAMPLE once more, telling generation which obvious clusters and which low-value or constraint-violating candidates the misses were. If still fewer than 3, return what is in band and say how many."
  - Closing line becomes `"<n> band options in <path>. Want to take one into brainstorming?"`
  - Frontmatter `allowed-tools: Read, Write, Bash, Agent`.
- [ ] **Step 3:** `make contract` OK.
- [ ] **Step 4 (GREEN):** repeat Step 1's 5 runs. Expect output_kind present in all panel prompts; short bands handled by one resample then an honest count.
- [ ] **Step 5: Commit** `fix(spitballing): panel prompt carries output_kind; handle short bands`

### Task 8: Description A/B (R3)

- [ ] **Step 1:** Write `eval/variants/desc-triggers-only.txt` containing:
  `description: Use when the user wants several creative options for a request (names, titles, concepts, angles, premises) and generic answers won't do: "less obvious", "something original", "give me options for". Not for refining one idea into a design; that is brainstorming.`
- [ ] **Step 2:** 5 runs `PROMPT=natural`, current description; 5 runs `PROMPT=natural DESC_VARIANT=eval/variants/desc-triggers-only.txt`.
- [ ] **Step 3:** Report `skill_invoked` rate and `panel_spawns == 12` rate per arm.
- [ ] **Step 4 (gate):** If triggers-only is equal or better on both, swap it into SKILL.md, `make contract`, commit `fix(spitballing): triggers-only description`. Otherwise keep the current one.

### Task 9: Who judges obviousness (R6, decision gate)

**Files:** Create `tools/eval/rejudge.py`.

- [ ] **Step 1:** Implement `rejudge.py <run-dir>...`: for each run, send a fresh `claude -p` the `map.json` obvious clusters (labels and `member_ideas`) and the candidate texts only, asking for `{"text": ..., "nearest_obvious_cluster": label|null}` per candidate as JSON; write `rejudge.json` into the run dir.
- [ ] **Step 2:** Run it over the 10 Task 6 runs (10 cheap single calls).
- [ ] **Step 3:** Report per run: share of candidates called obvious by the conductor vs. the fresh judge, and how many final `ranked` items the fresh judge calls obvious.
- [ ] **Step 4 (gate):** Owner decides. If the judge calls materially more candidates obvious, the follow-up is a SKILL.md change making CONVERGE judging always go to a fresh judge agent; plan that separately.

### Task 10: Panel discipline under pressure (R7, decision gate)

- [ ] **Step 1:** 5 runs `BRIEF=head-cool PROMPT=pressure` on the current skill.
- [ ] **Step 2:** Report `panel_spawns` per run; read every transcript where it is not 12 and quote the conductor's stated reason verbatim.
- [ ] **Step 3 (gate):** If all 5 spawn 12, change nothing. If any don't, the owner decides on a counter at the panel step built from the quoted reasons (writing-skills: rationalization table and red flags), then re-run Step 1 to check it.

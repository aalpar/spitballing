"""Contract tests: SKILL.md <-> kernel <-> committed run artifacts.

The unit tests cover the arithmetic. These cover the seams the arithmetic can't
see: whether the commands SKILL.md tells a conductor to run actually run, and
whether the artifact shapes SKILL.md tells a conductor to write are actually
accepted by the kernel that consumes them.

Every failure here is a bug the unit tests pass straight through, because each
one lives in the gap between two files that are individually correct.
"""
import fnmatch
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools.eval.validate import validate_run
from tools.spitball.band import Candidate, rank_band

ROOT = pathlib.Path(__file__).resolve().parents[3]
SKILL_DIR = ROOT / "skills" / "spitballing"
RUNS = ROOT / "docs" / "spitball"


class TestSkillInvocationsArePortable(unittest.TestCase):
    """The plugin runs from the *user's* cwd, never from this repo root. The
    harness substitutes ${CLAUDE_PLUGIN_ROOT} into skill text before the
    conductor sees it; it is not exported to Bash."""

    PREFIX = 'PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m tools.spitball'
    PAYLOADS = {
        "obvious": {"panelists": [{"clusters": ["literal"]}]},
        "rank": {"candidates": [{"text": "x", "value_score": 0.8,
                                 "fringe_proximity": 0.7,
                                 "nearest_obvious_cluster": None}]},
        "fringe-check": {"predicates": ["HEAD"], "answers": [], "clusters": []},
    }

    def _texts(self):
        """Skill bodies, frontmatter stripped: allowed-tools names the kernel
        in a permission rule, not a command."""
        return {p.name: re.sub(r"\A---\n.*?\n---\n", "", p.read_text(), flags=re.DOTALL)
                for p in sorted(SKILL_DIR.glob("*.md"))}

    def _cmds(self):
        return sorted({c for t in self._texts().values() for c in re.findall(
            r'PYTHONPATH="\$\{CLAUDE_PLUGIN_ROOT\}" python3 -m tools\.spitball (\S+)', t)})

    def _run(self, cmd, plugin_root, cwd):
        # Substitute the root textually, as the harness does, and let the shell
        # parse the quoting. PYTHONPATH is stripped from the inherited env: an
        # installed user has no reason to have the plugin root on it.
        line = self.PREFIX.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        return subprocess.run(f"{line} {cmd}", shell=True,
                              input=json.dumps(self.PAYLOADS[cmd]),
                              capture_output=True, text=True, cwd=cwd, env=env)

    def test_every_documented_command_runs_from_a_foreign_cwd(self):
        cmds = self._cmds()
        self.assertTrue(cmds, "no kernel invocations found in the skill")
        with tempfile.TemporaryDirectory() as foreign_cwd:
            for cmd in cmds:
                with self.subTest(cmd=cmd):
                    proc = self._run(cmd, ROOT, foreign_cwd)
                    self.assertEqual(proc.returncode, 0, proc.stderr.strip())

    def test_plugin_root_with_a_space_still_resolves(self):
        with tempfile.TemporaryDirectory() as tmp, \
                tempfile.TemporaryDirectory() as foreign_cwd:
            spaced = pathlib.Path(tmp) / "plugin root"
            shutil.copytree(ROOT / "tools", spaced / "tools",
                            ignore=shutil.ignore_patterns("__pycache__"))
            proc = self._run("obvious", spaced, foreign_cwd)
            self.assertEqual(proc.returncode, 0, proc.stderr.strip())

    def test_no_unprefixed_kernel_commands_remain(self):
        for name, text in self._texts().items():
            for line in text.splitlines():
                if "-m tools.spitball" in line:
                    with self.subTest(file=name, line=line.strip()):
                        self.assertIn(self.PREFIX, line)

    def test_allowed_tools_rule_covers_every_kernel_command(self):
        # Claude Code's Bash rule `*` matches any text, spaces included;
        # fnmatch is the same glob. An allow rule does not match past an
        # unlisted env assignment, so the rule must carry the PYTHONPATH= part.
        front = re.match(r"\A---\n(.*?)\n---\n", (SKILL_DIR / "SKILL.md").read_text(),
                         re.DOTALL).group(1)
        entries = [e.strip() for e in re.search(r"^allowed-tools:(.*)$", front,
                                                re.MULTILINE).group(1).split(",")]
        if "Bash" in entries:           # bare Bash pre-approves every command
            return
        rules = [e[len("Bash("):-1] for e in entries if e.startswith("Bash(")]
        for cmd in self._cmds():
            with self.subTest(cmd=cmd):
                line = f"{self.PREFIX} {cmd}"
                self.assertTrue(any(fnmatch.fnmatchcase(line, r) for r in rules),
                                f"no allowed-tools Bash rule matches {line!r}")

    def test_fringe_check_md_is_scanned(self):
        self.assertIn("fringe-check", self._cmds())


class TestCandidateRecordContract(unittest.TestCase):
    """SKILL.md tells the conductor to write `obvious`/`in_band` into
    candidates.jsonl, then to pipe *the same candidates* to `rank`."""

    def _records(self):
        paths = sorted(RUNS.glob("*/candidates.jsonl"))
        self.assertTrue(paths, "no committed run artifacts to check against")
        return [(p, [json.loads(line) for line in p.read_text().splitlines() if line])
                for p in paths]

    def test_committed_artifacts_are_accepted_by_rank(self):
        for path, recs in self._records():
            with self.subTest(run=path.parent.name):
                proc = subprocess.run(
                    [sys.executable, "-m", "tools.spitball", "rank", "--k", "5"],
                    input=json.dumps({"candidates": recs}),
                    capture_output=True, text=True, cwd=ROOT,
                )
                self.assertEqual(
                    proc.returncode, 0,
                    f"{path} cannot be fed to `rank` as SKILL.md instructs:\n"
                    f"{proc.stderr.strip()}")

    def test_committed_runs_pass_the_validator(self):
        """`obvious` and `in_band` are written by the conductor but *derived* by
        band.py. result.md is not checked: committed runs predate later kernel
        changes (1ec5be7 reweighting, a925ec6 label fix)."""
        for path, _ in self._records():
            with self.subTest(run=path.parent.name):
                problems = validate_run(path.parent, check_result=False)
                self.assertEqual(problems, [])


class TestRankingWeightIsPinned(unittest.TestCase):
    """band.py calls its weighting 'the one load-bearing creative choice'.

    test_band.py's crossing case does NOT discriminate it: its fixture returns
    the same order under 0.7/0.3, 0.6/0.4 and 0.4/0.6, which is why the retune
    in 1ec5be7 passed untouched. This fixture is chosen to sit *between* the old
    and current weights, so it fails if either is silently restored.
    """

    def test_current_weighting_prefers_the_clearly_stronger_fulfiller(self):
        # Crossing point of this pair is ~0.65 fringe-weight.
        #   0.6/0.4 (current) -> A first.  0.7/0.3 (old) -> B first.
        strong_value = Candidate("A", value_score=0.95, fringe_proximity=0.55)
        strong_fringe = Candidate("B", value_score=0.76, fringe_proximity=0.65)
        ranked = rank_band([strong_fringe, strong_value], k=2)
        self.assertEqual(
            [c.text for c in ranked], ["A", "B"],
            "0.6/0.4 is gentler than 0.7/0.3: a clearly-stronger fulfiller "
            "(+0.19 value) must not be leapfrogged for +0.10 fringe")


if __name__ == "__main__":
    unittest.main()

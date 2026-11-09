import json
import pathlib
import tempfile
import unittest

from tools.eval.audit import _row, audit_transcript, summarize

PANEL = "Give your first 8 instinctive answers to: names for a head-cooling product."


def tool_use(name, inp, parent=None):
    return {"type": "assistant", "parent_tool_use_id": parent,
            "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}


def bash(cmd, parent=None):
    return tool_use("Bash", {"command": cmd}, parent)


KERNEL = 'echo {} | PYTHONPATH="/p" python3 -m tools.spitball '


def full_run():
    lines = [tool_use("Skill", {"skill": "spitballing:spitballing"})]
    lines += [tool_use("Agent", {"prompt": PANEL + " Each answer is a product name."})
              for _ in range(12)]
    # Subagent-internal tool_uses: must not count.
    lines += [tool_use("Agent", {"prompt": PANEL}, parent="toolu_x"),
              bash(KERNEL + "obvious", parent="toolu_x")]
    lines += [bash(KERNEL + "obvious"), bash(KERNEL + "rank --k 5"),
              tool_use("Write", {"file_path": "/s/docs/spitball/t/result.md", "content": "x"})]
    return lines


class TestAuditTranscript(unittest.TestCase):
    def _audit(self, lines, **kw):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = pathlib.Path(tmp.name) / "transcript.jsonl"
        p.write_text("".join(json.dumps(l) + "\n" for l in lines))
        return audit_transcript(p, **kw)

    def test_counts_panel_spawns_top_level_only(self):
        m = self._audit(full_run(), output_kind="a product name")
        self.assertEqual(m["panel_spawns"], 12)
        self.assertEqual(m["panel_prompts_with_output_kind"], 12)
        self.assertTrue(m["skill_invoked"])

    def test_detects_prompt_leak(self):
        lines = full_run() + [tool_use("Agent", {"prompt": PANEL + " Avoid the obvious ones."})]
        self.assertEqual(self._audit(lines)["panel_prompt_leaks"], 1)

    def test_counts_kernel_calls(self):
        m = self._audit(full_run())
        self.assertEqual(m["kernel_calls"], {"obvious": 1, "rank": 1, "fringe-check": 0})

    def test_run_without_rank_is_incomplete(self):
        lines = [l for l in full_run() if "rank" not in json.dumps(l)]
        self.assertEqual(self._audit(lines)["status"], "incomplete")
        self.assertEqual(self._audit(full_run())["status"], "complete")

    def test_result_written_via_bash_heredoc_counts(self):
        lines = [l for l in full_run() if "Write" not in json.dumps(l)]
        lines.append(bash("cat > docs/spitball/t/result.md <<'EOF'\n# x\nEOF"))
        self.assertEqual(self._audit(lines)["status"], "complete")

    def test_truncated_transcript_reads_incomplete(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = pathlib.Path(tmp.name) / "transcript.jsonl"
        lines = [json.dumps(l) for l in full_run()[:13]]
        p.write_text("\n".join(lines) + '\n{"type": "assistant", "mess')
        m = audit_transcript(p)
        self.assertEqual((m["panel_spawns"], m["status"]), (12, "incomplete"))


class TestSummarize(unittest.TestCase):
    def test_summary_has_mean_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = []
            for n in ("0001", "0002"):
                d = pathlib.Path(tmp) / n
                d.mkdir()
                (d / "transcript.jsonl").write_text(
                    "".join(json.dumps(l) + "\n" for l in full_run()))
                runs.append(d)
            table = summarize(runs)
        rows = [r for r in table.splitlines() if r.startswith("|")]
        self.assertEqual(len(rows), 2 + 2 + 1)        # header, rule, 2 runs, mean
        self.assertTrue(rows[-1].startswith("| mean"))
        self.assertIn("12", rows[-1])

    def test_incomplete_runs_are_listed_apart_and_kept_out_of_the_mean(self):
        with tempfile.TemporaryDirectory() as tmp:
            done, stopped = pathlib.Path(tmp) / "0001", pathlib.Path(tmp) / "0002"
            for d, lines in ((done, full_run()), (stopped, full_run()[:1])):
                d.mkdir()
                (d / "transcript.jsonl").write_text(
                    "".join(json.dumps(l) + "\n" for l in lines))
            table = summarize([done, stopped])
        complete, _, incomplete = table.partition("Incomplete")
        self.assertIn("| 0001 |", complete)
        self.assertNotIn("| 0002 |", complete)
        self.assertIn("| 0002 |", incomplete)
        self.assertNotIn("| mean", incomplete)
        mean = next(r for r in complete.splitlines() if r.startswith("| mean"))
        self.assertIn("| 12.00 |", mean)


class TestPhantomPanel(unittest.TestCase):
    """A map that reports panel counts when no panelist was spawned."""
    COUNTED = {"measured": True, "obvious_clusters": [
        {"label": "x", "panelist_count": 9, "frac": 0.75, "member_ideas": ["a"]}]}
    UNMEASURED = {"measured": False, "obvious_clusters": [
        {"label": "x", "member_ideas": ["a"]}]}

    def _phantom(self, lines, map_):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp) / "0001"
            (d / "docs" / "spitball" / "t").mkdir(parents=True)
            (d / "transcript.jsonl").write_text(
                "".join(json.dumps(l) + "\n" for l in lines))
            (d / "docs" / "spitball" / "t" / "map.json").write_text(json.dumps(map_))
            return _row(d)["phantom"]

    def test_counts_without_spawns_is_phantom(self):
        no_panel = [l for l in full_run() if PANEL not in json.dumps(l)]
        self.assertTrue(self._phantom(no_panel, self.COUNTED))
        self.assertTrue(self._phantom(no_panel, dict(self.UNMEASURED, measured=True)))

    def test_declared_unmeasured_without_spawns_is_not_phantom(self):
        no_panel = [l for l in full_run() if PANEL not in json.dumps(l)]
        self.assertFalse(self._phantom(no_panel, self.UNMEASURED))

    def test_counts_with_spawns_is_not_phantom(self):
        self.assertFalse(self._phantom(full_run(), self.COUNTED))


if __name__ == "__main__":
    unittest.main()

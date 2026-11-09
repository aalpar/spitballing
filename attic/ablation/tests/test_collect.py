#!/usr/bin/env python3
"""Tests for tools.ablation.collect — pull, dedup, reconcile, exposure, abort guards.

Verifies:
  (a) dedup removes duplicate (worker_id, idea_id) rows, keeping the first;
  (b) reconcile returns expected/actual/missing_hits/extra correctly;
  (c) attention_pass returns per-worker verdicts and overall discard rate;
  (d) exposure_matrix counts ratings per (engine, source) cell via key_map;
  (e) assert_guards raises on discard_rate > max_discard;
  (f) assert_guards raises when any cell count < min_per_cell;
  (g) assert_guards raises when an answer idea_id is absent from key_map.
"""
import unittest

from tools.ablation.collect import (
    attention_pass,
    dedup,
    exposure_matrix,
    reconcile,
    assert_guards,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# key_map mirrors build_hits.build_key_map output: {idea_id: {engine, source}}
KEY_MAP = {
    "idea-00": {"engine": "mashup",   "source": "gpt4"},
    "idea-01": {"engine": "mashup",   "source": "claude3"},
    "idea-02": {"engine": "diverge",  "source": "gpt4"},
    "idea-03": {"engine": "diverge",  "source": "claude3"},
    "idea-04": {"engine": "reduce",   "source": "gpt4"},
    "idea-05": {"engine": "reduce",   "source": "claude3"},
}

# Minimal answer rows — only the fields pure functions need.
def _answer(worker_id, idea_id, dimension="originality", value=3, position=0):
    return {
        "worker_id": worker_id,
        "idea_id":   idea_id,
        "dimension": dimension,
        "value":     value,
        "position":  position,
    }


# ---------------------------------------------------------------------------
# (a) dedup
# ---------------------------------------------------------------------------

class TestDedup(unittest.TestCase):

    def test_dedup_removes_second_occurrence(self):
        rows = [
            _answer("w1", "idea-00", value=4),
            _answer("w1", "idea-01", value=3),
            _answer("w1", "idea-00", value=5),   # dup: same (w1, idea-00)
        ]
        result = dedup(rows)
        self.assertEqual(len(result), 2)

    def test_dedup_keeps_first_occurrence(self):
        rows = [
            _answer("w1", "idea-00", value=4),
            _answer("w1", "idea-00", value=5),   # dup kept-second
        ]
        result = dedup(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["value"], 4, "First occurrence must be kept")

    def test_dedup_different_workers_both_kept(self):
        rows = [
            _answer("w1", "idea-00"),
            _answer("w2", "idea-00"),   # different worker — not a dup
        ]
        result = dedup(rows)
        self.assertEqual(len(result), 2)

    def test_dedup_keeps_distinct_dimensions(self):
        # One worker rating one idea on multiple dimensions is NOT a duplicate:
        # pull() emits one row per (worker, idea, dimension).  All must survive.
        rows = [
            _answer("w1", "idea-00", dimension="originality", value=4),
            _answer("w1", "idea-00", dimension="appropriateness", value=2),
            _answer("w1", "idea-00", dimension="originality", value=5),  # true dup
        ]
        result = dedup(rows)
        self.assertEqual(len(result), 2,
                         "distinct dimensions must survive; only the exact "
                         "(worker, idea, dimension) repeat is dropped")
        dims = sorted(r["dimension"] for r in result)
        self.assertEqual(dims, ["appropriateness", "originality"])

    def test_dedup_no_dups_unchanged(self):
        rows = [
            _answer("w1", "idea-00"),
            _answer("w1", "idea-01"),
            _answer("w2", "idea-00"),
        ]
        result = dedup(rows)
        self.assertEqual(len(result), 3)


# ---------------------------------------------------------------------------
# (b) reconcile
# ---------------------------------------------------------------------------

class TestReconcile(unittest.TestCase):

    def _manifest(self, entries):
        # entries: list of (hit_id, [idea_ids])
        return [{"hit_id": h, "idea_ids": ids} for h, ids in entries]

    def test_missing_hit_detected(self):
        """A HIT that produced no answers should appear in missing_hits."""
        manifest = self._manifest([
            ("hit-1", ["idea-00", "idea-01"]),
            ("hit-2", ["idea-02", "idea-03"]),  # no answers for this HIT
        ])
        answers = [
            _answer("w1", "idea-00"),
            _answer("w1", "idea-01"),
        ]
        result = reconcile(manifest, answers)
        self.assertIn("hit-2", result["missing_hits"])

    def test_extra_answer_detected(self):
        """An answer whose idea_id is not in any manifest HIT -> extra."""
        manifest = self._manifest([("hit-1", ["idea-00"])])
        answers = [
            _answer("w1", "idea-00"),
            _answer("w1", "idea-99"),   # idea-99 not in manifest
        ]
        result = reconcile(manifest, answers)
        self.assertIn("idea-99", result["extra"])

    def test_expected_actual_sets(self):
        manifest = self._manifest([("hit-1", ["idea-00", "idea-01"])])
        answers = [_answer("w1", "idea-00")]
        result = reconcile(manifest, answers)
        self.assertEqual(result["expected"], {"idea-00", "idea-01"})
        self.assertEqual(result["actual"], {"idea-00"})

    def test_full_match_no_missing_no_extra(self):
        manifest = self._manifest([("hit-1", ["idea-00", "idea-01"])])
        answers = [_answer("w1", "idea-00"), _answer("w2", "idea-01")]
        result = reconcile(manifest, answers)
        self.assertEqual(result["missing_hits"], [])
        self.assertEqual(result["extra"], set())


# ---------------------------------------------------------------------------
# (c) attention_pass
# ---------------------------------------------------------------------------

# checks format: list of {idea_id, correct_answer}
CHECKS = [
    {"idea_id": "attn-1", "correct_answer": 2},
    {"idea_id": "attn-2", "correct_answer": 1},
]


class TestAttentionPass(unittest.TestCase):

    def _attn_answer(self, worker_id, idea_id, value):
        return _answer(worker_id, idea_id, dimension="attn", value=value)

    def test_passing_worker(self):
        answers = [
            self._attn_answer("w1", "attn-1", 2),  # correct
            self._attn_answer("w1", "attn-2", 1),  # correct
        ]
        verdicts, discard_rate = attention_pass(answers, CHECKS)
        self.assertTrue(verdicts["w1"])

    def test_failing_worker(self):
        answers = [
            self._attn_answer("w2", "attn-1", 9),  # wrong
            self._attn_answer("w2", "attn-2", 9),  # wrong
        ]
        verdicts, discard_rate = attention_pass(answers, CHECKS)
        self.assertFalse(verdicts["w2"])

    def test_discard_rate_computation(self):
        """2 workers, 1 fails => discard_rate = 0.5."""
        answers = [
            self._attn_answer("w1", "attn-1", 2),   # pass
            self._attn_answer("w1", "attn-2", 1),   # pass
            self._attn_answer("w2", "attn-1", 9),   # fail
            self._attn_answer("w2", "attn-2", 9),   # fail
        ]
        verdicts, discard_rate = attention_pass(answers, CHECKS)
        self.assertAlmostEqual(discard_rate, 0.5)

    def test_all_pass_discard_rate_zero(self):
        answers = [
            self._attn_answer("w1", "attn-1", 2),
            self._attn_answer("w1", "attn-2", 1),
            self._attn_answer("w2", "attn-1", 2),
            self._attn_answer("w2", "attn-2", 1),
        ]
        verdicts, discard_rate = attention_pass(answers, CHECKS)
        self.assertAlmostEqual(discard_rate, 0.0)

    def test_no_answers_discard_rate_zero(self):
        verdicts, discard_rate = attention_pass([], CHECKS)
        self.assertEqual(verdicts, {})
        self.assertAlmostEqual(discard_rate, 0.0)


# ---------------------------------------------------------------------------
# (d) exposure_matrix
# ---------------------------------------------------------------------------

class TestExposureMatrix(unittest.TestCase):

    def test_counts_per_cell(self):
        answers = [
            _answer("w1", "idea-00"),   # mashup/gpt4
            _answer("w2", "idea-00"),   # mashup/gpt4  -> cell count = 2
            _answer("w1", "idea-02"),   # diverge/gpt4 -> cell count = 1
        ]
        matrix = exposure_matrix(answers, KEY_MAP)
        self.assertEqual(matrix[("mashup", "gpt4")], 2)
        self.assertEqual(matrix[("diverge", "gpt4")], 1)

    def test_unrated_cell_absent_or_zero(self):
        """Cells not present in answers should be 0 or absent."""
        answers = [_answer("w1", "idea-00")]
        matrix = exposure_matrix(answers, KEY_MAP)
        # diverge/gpt4 had no ratings — either absent or 0
        self.assertEqual(matrix.get(("diverge", "gpt4"), 0), 0)

    def test_balanced_fixture(self):
        """One rating per idea => each cell gets exactly 1 rating."""
        answers = [_answer(f"w{i}", iid) for i, iid in enumerate(KEY_MAP)]
        matrix = exposure_matrix(answers, KEY_MAP)
        for cell_count in matrix.values():
            self.assertEqual(cell_count, 1, "Balanced fixture: every cell = 1")


# ---------------------------------------------------------------------------
# (e-g) assert_guards
# ---------------------------------------------------------------------------

class TestAssertGuards(unittest.TestCase):

    def _good_answers(self):
        """One answer per idea_id in KEY_MAP — no attention checks."""
        return [_answer(f"w{i}", iid) for i, iid in enumerate(KEY_MAP)]

    def test_guard_discard_rate_too_high(self):
        """discard_rate > max_discard must raise ValueError."""
        answers = self._good_answers()
        with self.assertRaises(ValueError) as ctx:
            assert_guards(
                answers=answers,
                key_map=KEY_MAP,
                discard_rate=0.35,   # > default max_discard=0.30
                min_per_cell=1,
            )
        self.assertIn("discard", str(ctx.exception).lower())

    def test_guard_cell_below_minimum(self):
        """Any cell with fewer ratings than min_per_cell must raise ValueError."""
        # Only one answer for idea-00 (mashup/gpt4) — all other cells empty.
        answers = [_answer("w1", "idea-00")]
        with self.assertRaises(ValueError) as ctx:
            assert_guards(
                answers=answers,
                key_map=KEY_MAP,
                discard_rate=0.0,
                min_per_cell=2,   # need at least 2 per cell; mashup/gpt4 has 1
            )
        self.assertIn("cell", str(ctx.exception).lower())

    def test_guard_unknown_idea_id(self):
        """An answer whose idea_id is not in key_map must raise ValueError."""
        answers = self._good_answers() + [_answer("w99", "idea-UNKNOWN")]
        with self.assertRaises(ValueError) as ctx:
            assert_guards(
                answers=answers,
                key_map=KEY_MAP,
                discard_rate=0.0,
                min_per_cell=1,
            )
        self.assertIn("idea-UNKNOWN", str(ctx.exception))

    def test_guard_passes_clean_data(self):
        """Clean data with good discard_rate and sufficient coverage: no raise."""
        answers = self._good_answers()
        # Should not raise
        assert_guards(
            answers=answers,
            key_map=KEY_MAP,
            discard_rate=0.10,
            min_per_cell=1,
        )


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()

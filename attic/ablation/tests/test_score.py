import unittest
from tools.ablation import score


def _ratings(block, engine, source, dim, vals):
    return [{"idea_id": f"{engine}-{block}", "worker_id": f"w{i}",
             "dimension": dim, "value": v, "engine": engine,
             "source": source, "block_id": block}
            for i, v in enumerate(vals)]


class TestPairedContrasts(unittest.TestCase):
    def test_pairs_within_block_and_signs_difference(self):
        # arm A beats arm B on every block, but by a VARYING margin so the
        # within-block differences have non-zero variance (g is well-defined).
        a_vals = {"bg:00": [5, 5, 5], "bg:01": [6, 6, 6], "bg:02": [7, 7, 7]}
        ratings = []
        for b in ("bg:00", "bg:01", "bg:02"):
            ratings += _ratings(b, "inversion", "background", "originality", a_vals[b])
            ratings += _ratings(b, "straight", "background", "originality", [3, 3, 3])
        key_map = {r["idea_id"]: {"engine": r["engine"], "source": r["source"],
                                  "block_id": r["block_id"]} for r in ratings}
        out = score.paired_contrasts(ratings, key_map, "originality",
                                     arm_a="inversion", arm_b="straight", source="background")
        self.assertEqual(out["n_blocks"], 3)
        self.assertGreater(out["mean_diff"], 0)
        self.assertIsNotNone(out["hedges_g"])
        self.assertGreater(out["hedges_g"], 0)

    def test_zero_within_block_variance_gives_undefined_g(self):
        # identical diff on every block -> sd(diffs)==0 -> g undefined (None),
        # but the mean difference is still reported.
        ratings = []
        for b in ("bg:00", "bg:01", "bg:02"):
            ratings += _ratings(b, "inversion", "background", "originality", [5, 5, 5])
            ratings += _ratings(b, "straight", "background", "originality", [3, 3, 3])
        key_map = {r["idea_id"]: {"engine": r["engine"], "source": r["source"],
                                  "block_id": r["block_id"]} for r in ratings}
        out = score.paired_contrasts(ratings, key_map, "originality",
                                     arm_a="inversion", arm_b="straight", source="background")
        self.assertEqual(out["n_blocks"], 3)
        self.assertEqual(out["mean_diff"], 2.0)
        self.assertIsNone(out["hedges_g"])

    def test_only_shared_blocks_are_paired(self):
        ratings = _ratings("bg:00", "inversion", "background", "originality", [5])
        ratings += _ratings("bg:00", "straight", "background", "originality", [3])
        ratings += _ratings("bg:01", "inversion", "background", "originality", [9])  # unmatched
        key_map = {r["idea_id"]: {"engine": r["engine"], "source": r["source"],
                                  "block_id": r["block_id"]} for r in ratings}
        out = score.paired_contrasts(ratings, key_map, "originality",
                                     arm_a="inversion", arm_b="straight", source="background")
        self.assertEqual(out["n_blocks"], 1)


if __name__ == "__main__":
    unittest.main()

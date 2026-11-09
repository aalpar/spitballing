import json
import pathlib
import tempfile
import unittest

from tools.eval.validate import validate_run

MAP = {"value_criterion": "communicates cooling the head", "measured": True,
       "predicates": ["COOLING", "HEAD"],
       "obvious_clusters": [{"label": "literal", "panelist_count": 9,
                             "frac": 0.75, "member_ideas": ["CoolCap"]}],
       "negative_fringe": [{"drops": "HEAD", "landmark": "cold, no cranial reference",
                            "examples": ["Glacier"]}]}
RECS = [{"text": "Nimbus", "value_score": 0.8, "fringe_proximity": 0.7,
         "nearest_obvious_cluster": None, "obvious": False, "in_band": True},
        {"text": "CoolCap", "value_score": 0.9, "fringe_proximity": 0.1,
         "nearest_obvious_cluster": "literal", "obvious": True, "in_band": False}]


class TestValidateRun(unittest.TestCase):
    def _run(self, map_=MAP, recs=RECS, result="1. Nimbus\n"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = pathlib.Path(tmp.name)
        (d / "map.json").write_text(json.dumps(map_))
        (d / "candidates.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in recs))
        (d / "result.md").write_text(result)
        return validate_run(d)

    def test_valid_run_has_no_problems(self):
        self.assertEqual(self._run(), [])

    def test_unknown_cluster_label_is_flagged(self):
        recs = [dict(RECS[1], nearest_obvious_cluster="literl")] + RECS[:1]
        problems = self._run(recs=recs)
        self.assertTrue(any("literl" in p for p in problems), problems)

    def test_drops_not_in_predicates_is_flagged(self):
        m = dict(MAP, negative_fringe=[dict(MAP["negative_fringe"][0], drops="WEARABLE")])
        problems = self._run(map_=m)
        self.assertTrue(any("WEARABLE" in p for p in problems), problems)

    def test_in_band_flag_disagreeing_with_kernel_is_flagged(self):
        recs = [dict(RECS[0], violates=["4 letters"])] + RECS[1:]
        problems = self._run(recs=recs, result="")
        self.assertTrue(any("Nimbus" in p and "in_band" in p for p in problems), problems)

    def test_ranked_text_missing_from_result_md_is_flagged(self):
        problems = self._run(result="nothing here\n")
        self.assertTrue(any("Nimbus" in p and "result.md" in p for p in problems), problems)

    def test_measured_flag_is_required(self):
        m = {k: v for k, v in MAP.items() if k != "measured"}
        problems = self._run(map_=m)
        self.assertTrue(any("missing measured" in p for p in problems), problems)

    def test_unmeasured_map_with_panel_counts_is_flagged(self):
        problems = self._run(map_=dict(MAP, measured=False))
        self.assertTrue(any("panelist_count" in p and "measured" in p for p in problems),
                        problems)
        self.assertTrue(any("frac" in p and "measured" in p for p in problems), problems)

    def test_unmeasured_map_without_counts_is_valid(self):
        m = dict(MAP, measured=False,
                 obvious_clusters=[{"label": "literal", "member_ideas": ["CoolCap"]}])
        self.assertEqual(self._run(map_=m), [])

    def test_malformed_records_are_flagged_not_raised(self):
        recs = [{"value_score": 0.8, "fringe_proximity": 0.7, "nearest_obvious_cluster": None},
                dict(RECS[0], nearest_obvious_cluster=["literal"]),
                "not a record",
                dict(RECS[0], violates="4 letters")]
        problems = self._run(recs=recs)
        for needle in ("missing text", "nearest_obvious_cluster", "not an object",
                       "violates must be a list"):
            self.assertTrue(any(needle in p for p in problems), (needle, problems))


if __name__ == "__main__":
    unittest.main()

import json
import unittest

from tools.eval.rejudge import build_matched_prompt, build_prompt, compare, converge_bullet, parse_reply

MAP = {"obvious_clusters": [{"label": "literal", "member_ideas": ["CoolCap", "HeadChill"]}]}
RECS = [{"text": "Nimbus", "value_score": 0.8, "fringe_proximity": 0.7,
         "nearest_obvious_cluster": None},
        {"text": "IceHat", "value_score": 0.9, "fringe_proximity": 0.6,
         "nearest_obvious_cluster": None},
        {"text": "CoolCap", "value_score": 0.9, "fringe_proximity": 0.1,
         "nearest_obvious_cluster": "literal"}]


class TestRejudge(unittest.TestCase):
    def test_prompt_carries_clusters_and_texts_only(self):
        p = build_prompt(MAP, [r["text"] for r in RECS])
        self.assertIn("literal: CoolCap, HeadChill", p)
        self.assertIn("- Nimbus", p)
        self.assertNotIn("0.8", p)

    def test_parse_reply_extracts_array_from_prose(self):
        j = parse_reply('Here:\n[{"text": "Nimbus", "nearest_obvious_cluster": null}]\n')
        self.assertEqual(j, [{"text": "Nimbus", "nearest_obvious_cluster": None}])

    def test_compare_counts_judge_obvious_and_ranked_overlap(self):
        judgments = [{"text": "Nimbus", "nearest_obvious_cluster": None},
                     {"text": "IceHat", "nearest_obvious_cluster": "literal"},
                     {"text": "CoolCap", "nearest_obvious_cluster": "literal"}]
        c = compare(RECS, judgments, {"literal"})
        self.assertEqual((c["conductor_obvious"], c["judge_obvious"]), (1, 2))
        self.assertEqual(c["ranked_judge_obvious"], ["IceHat"])

    def test_label_not_in_map_is_not_obvious(self):
        c = compare(RECS, [{"text": "Nimbus", "nearest_obvious_cluster": "made-up"}], {"literal"})
        self.assertEqual(c["judge_obvious"], 0)
        self.assertEqual(c["unjudged"], 2)

    def test_compare_reports_disagreement_both_ways(self):
        judgments = [{"text": "Nimbus", "nearest_obvious_cluster": "literal"},
                     {"text": "IceHat", "nearest_obvious_cluster": None},
                     {"text": "CoolCap", "nearest_obvious_cluster": None}]
        c = compare(RECS, judgments, {"literal"})
        self.assertEqual((c["conductor_only"], c["judge_only"]), (1, 1))

    def test_converge_bullet_is_extracted_verbatim(self):
        skill = ("## Stage 3\n\n- `nearest_obvious_cluster`: the label it falls into,\n"
                 "  or `null`. Judge against the map.\n- `value_score` (0-1)\n")
        self.assertEqual(converge_bullet(skill),
                         "- `nearest_obvious_cluster`: the label it falls into,\n"
                         "  or `null`. Judge against the map.")

    def test_matched_prompt_carries_map_json_and_instruction_but_no_gloss(self):
        p = build_matched_prompt("names for X", json.dumps(MAP), "- `nearest_obvious_cluster`: BULLET",
                                 [r["text"] for r in RECS])
        self.assertIn("names for X", p)
        self.assertIn('"member_ideas": ["CoolCap", "HeadChill"]', p)
        self.assertIn("BULLET", p)
        self.assertIn("- Nimbus", p)
        self.assertNotIn("same reason", p)
        self.assertNotIn("0.8", p)


if __name__ == "__main__":
    unittest.main()

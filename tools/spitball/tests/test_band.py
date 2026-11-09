import unittest

from tools.spitball.band import Candidate, in_band, rank_band, rank_records


def cand(text, value, fringe, obvious_cluster=None):
    return Candidate(text=text, value_score=value, fringe_proximity=fringe,
                     nearest_obvious_cluster=obvious_cluster)


class TestInBand(unittest.TestCase):
    def test_obvious_is_excluded_even_if_high_value(self):
        c = cand("CoolCap", 0.95, 0.2, obvious_cluster="literal")
        self.assertFalse(in_band(c))

    def test_low_value_is_excluded_even_if_high_fringe(self):
        c = cand("Glacier", 0.3, 0.99)            # evokes cold, not the head
        self.assertFalse(in_band(c))

    def test_high_value_non_obvious_is_in_band(self):
        self.assertTrue(in_band(cand("Nimbus", 0.8, 0.7)))

    def test_violation_excludes_high_value_candidate(self):
        c = Candidate("X", value_score=0.9, fringe_proximity=0.9, violates=("4 letters",))
        self.assertFalse(in_band(c))


class TestRankBand(unittest.TestCase):
    def test_fringe_outranks_value_when_both_in_band(self):
        # A: higher value, lower fringe. B: lower value, higher fringe.
        # Fringe weighted higher => B must rank first.
        a = cand("A", 0.9, 0.4)
        b = cand("B", 0.7, 0.9)
        self.assertEqual([c.text for c in rank_band([a, b], k=2)], ["B", "A"])

    def test_filters_out_of_band_before_ranking(self):
        good = cand("good", 0.8, 0.6)
        obvious = cand("obvious", 0.95, 0.95, obvious_cluster="literal")
        weak = cand("weak", 0.2, 0.99)
        ranked = rank_band([good, obvious, weak], k=5)
        self.assertEqual([c.text for c in ranked], ["good"])

    def test_returns_at_most_k(self):
        cands = [cand(str(i), 0.8, 0.5 + i / 100) for i in range(10)]
        self.assertEqual(len(rank_band(cands, k=3)), 3)


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

    def test_violates_as_string_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "violates must be a list"):
            rank_records([{"text": "A", "value_score": 0.9, "fringe_proximity": 0.9,
                           "nearest_obvious_cluster": None, "violates": "4 letters"}], k=5)

    def test_non_numeric_score_names_candidate_and_key(self):
        with self.assertRaisesRegex(ValueError, "candidate 0: value_score must be a number"):
            rank_records([{"text": "A", "value_score": "0.8", "fringe_proximity": 0.7,
                           "nearest_obvious_cluster": None}], k=5)


if __name__ == "__main__":
    unittest.main()

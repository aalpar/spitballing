import unittest

from tools.spitball.fringe import fringe_check


class TestFringeCheck(unittest.TestCase):
    def test_near_miss_cluster_matching_a_predicate_is_validated(self):
        report = fringe_check(
            predicates=["COOLING", "HEAD"],
            answers=[
                {"panelist": 0, "value_score": 0.9},                        # on-target
                {"panelist": 1, "value_score": 0.4, "cluster": "cold-not-cranial"},
                {"panelist": 2, "value_score": 0.45, "cluster": "cold-not-cranial"},
            ],
            clusters=[{"label": "cold-not-cranial", "drops": "HEAD"}],
        )
        self.assertEqual(report.on_target, 1)
        self.assertEqual(report.near_miss, 2)
        self.assertEqual(len(report.clusters), 1)
        c = report.clusters[0]
        self.assertEqual(c.label, "cold-not-cranial")
        self.assertEqual(c.drops, "HEAD")
        self.assertEqual(c.panelists, 2)
        self.assertTrue(c.matched)
        self.assertEqual(report.unmatched, ())

    def test_near_miss_on_an_unnamed_predicate_is_the_decomposition_hole(self):
        # The panel produced a near-miss along an axis the decomposition never named.
        report = fringe_check(
            predicates=["COOLING", "HEAD"],
            answers=[{"panelist": 0, "value_score": 0.4, "cluster": "wearable-gadget"}],
            clusters=[{"label": "wearable-gadget", "drops": "WEARABLE"}],
        )
        self.assertFalse(report.clusters[0].matched)
        self.assertEqual(report.unmatched, ("wearable-gadget",))

    def test_cluster_with_null_drops_is_unmatched(self):
        report = fringe_check(
            predicates=["COOLING", "HEAD"],
            answers=[{"panelist": 0, "value_score": 0.3, "cluster": "noise"}],
            clusters=[{"label": "noise", "drops": None}],
        )
        self.assertIsNone(report.clusters[0].drops)
        self.assertFalse(report.clusters[0].matched)
        self.assertEqual(report.unmatched, ("noise",))

    def test_cluster_absent_from_mapping_is_unmatched(self):
        # Produced in answers but the conductor never mapped it -> still a hole.
        report = fringe_check(
            predicates=["COOLING"],
            answers=[{"panelist": 0, "value_score": 0.3, "cluster": "orphan"}],
            clusters=[],
        )
        self.assertEqual(report.unmatched, ("orphan",))

    def test_band_buckets_and_inclusive_boundaries(self):
        # vt=0.6 inclusive -> on_target; far_floor=0.2 inclusive -> near_miss.
        report = fringe_check(
            predicates=[],
            answers=[
                {"panelist": 0, "value_score": 0.6},     # == vt        -> on_target
                {"panelist": 1, "value_score": 0.59},    # near_miss
                {"panelist": 2, "value_score": 0.2},     # == far_floor -> near_miss
                {"panelist": 3, "value_score": 0.19},    # far_negative
            ],
            clusters=[],
        )
        self.assertEqual(
            (report.on_target, report.near_miss, report.far_negative), (1, 2, 1))

    def test_distinct_panelists_vs_answer_count(self):
        # Same panelist twice in one cluster: panelists=1, answers=2.
        report = fringe_check(
            predicates=["HEAD"],
            answers=[
                {"panelist": 0, "value_score": 0.4, "cluster": "k"},
                {"panelist": 0, "value_score": 0.45, "cluster": "k"},
            ],
            clusters=[{"label": "k", "drops": "HEAD"}],
        )
        c = report.clusters[0]
        self.assertEqual(c.panelists, 1)
        self.assertEqual(c.answers, 2)

    def test_unclustered_near_miss_counts_in_band_but_makes_no_cluster(self):
        report = fringe_check(
            predicates=["HEAD"],
            answers=[{"panelist": 0, "value_score": 0.4}],   # near-miss, no cluster
            clusters=[],
        )
        self.assertEqual(report.near_miss, 1)
        self.assertEqual(report.clusters, ())

    def test_no_frequency_cutoff_a_single_panelist_is_reported(self):
        # Unlike obvious_clusters, a singleton near-miss is signal, not noise.
        report = fringe_check(
            predicates=["COOLING"],
            answers=[{"panelist": 0, "value_score": 0.4, "cluster": "solo"}],
            clusters=[{"label": "solo", "drops": "X"}],
        )
        self.assertEqual(len(report.clusters), 1)
        self.assertEqual(report.clusters[0].panelists, 1)

    def test_clusters_sorted_by_panelists_then_label(self):
        report = fringe_check(
            predicates=["HEAD"],
            answers=[
                {"panelist": 0, "value_score": 0.4, "cluster": "b"},
                {"panelist": 1, "value_score": 0.4, "cluster": "b"},
                {"panelist": 2, "value_score": 0.4, "cluster": "a"},
            ],
            clusters=[{"label": "a", "drops": "HEAD"}, {"label": "b", "drops": "HEAD"}],
        )
        self.assertEqual([c.label for c in report.clusters], ["b", "a"])

    def test_inverted_thresholds_raise_value_error(self):
        with self.assertRaises(ValueError):
            fringe_check(predicates=[], answers=[], clusters=[],
                         value_threshold=0.2, far_floor=0.6)


if __name__ == "__main__":
    unittest.main()

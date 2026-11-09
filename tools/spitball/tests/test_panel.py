import unittest

from tools.spitball.panel import obvious_clusters, ObviousCluster


class TestObviousClusters(unittest.TestCase):
    def test_threshold_is_over_distinct_panelists_not_ideas(self):
        # 12 panelists. "literal" reached by 9 distinct panelists => 0.75 obvious.
        # "weather" reached by 2 => 0.167, below the 0.25 cutoff.
        # "rare" reached by 2 => 0.167, also below cutoff.
        panelist_clusters = (
            [{"literal", "weather"}] * 2
            + [{"literal"}] * 7
            + [{"rare"}] * 2
            + [set()]        # filler to keep n_panelists=12
        )
        out = obvious_clusters(panelist_clusters, n_panelists=12)
        labels = [o.label for o in out]
        self.assertEqual(labels, ["literal"])           # only >=0.25 survives
        self.assertEqual(out[0].panelist_count, 9)
        self.assertAlmostEqual(out[0].frac, 0.75)

    def test_a_panelist_repeating_a_cluster_counts_once(self):
        # Same panelist listing "literal" twice must not inflate the count.
        out = obvious_clusters([["literal", "literal"]], n_panelists=4)
        # 1 of 4 = 0.25 -> obvious (boundary is inclusive), counted once.
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].panelist_count, 1)

    def test_boundary_is_inclusive(self):
        # exactly 0.25 is obvious; just under is not.
        out = obvious_clusters([{"a"}, set(), set(), set()], n_panelists=4)
        self.assertEqual([o.label for o in out], ["a"])
        out2 = obvious_clusters([{"a"}, set(), set(), set(), set()], n_panelists=5)
        self.assertEqual(out2, [])                       # 0.2 < 0.25

    def test_zero_panelists_raises_value_error(self):
        with self.assertRaises(ValueError):
            obvious_clusters([], n_panelists=0)

    def test_sorted_by_frac_desc_then_label(self):
        pc = [{"b", "a"}, {"b", "a"}, {"b"}, {"b"}]
        out = obvious_clusters(pc, n_panelists=4)
        self.assertEqual([o.label for o in out], ["b", "a"])  # b=1.0, a=0.5


if __name__ == "__main__":
    unittest.main()

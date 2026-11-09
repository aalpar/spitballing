import unittest

from tools.inspect.build import _cut_reason, reconcile

VIOLATOR = {"text": "Shade", "value_score": 0.9, "fringe_proximity": 0.8,
            "nearest_obvious_cluster": None, "violates": ["exactly 4 letters"],
            "obvious": False, "in_band": False}


class TestReconcile(unittest.TestCase):
    def test_violation_is_out_of_band_without_false_disagreement(self):
        row, = reconcile([VIOLATOR])
        self.assertFalse(row["in_band"])
        self.assertEqual(row["disagree"], [])
        self.assertEqual(_cut_reason(row)[0], "violates")


if __name__ == "__main__":
    unittest.main()

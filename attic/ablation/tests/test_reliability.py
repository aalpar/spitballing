#!/usr/bin/env python3
"""Tests for tools.ablation.reliability and tools.ablation.score.

Covers:
  reliability.py:
    (a) krippendorff_alpha — perfect agreement -> 1.0
    (b) krippendorff_alpha — canonical interval reliability-data example -> ~0.811
    (b2) krippendorff_alpha — a second published matrix (12×4) -> ~0.849
    (c) krippendorff_alpha — all-disagree / maximum spread -> alpha <= 0

  score.py:
    (d) reliability_gate tags low-alpha dimension as 'inconclusive'
    (e) reliability_gate passes high-alpha dimension
    (f) contrasts refuses to rank an inconclusive dimension
    (g) aggregate returns per-cell means keyed by (engine, source)
    (h) position_effect returns slope and p-value

NOTE on canonical fixture values
--------------------------------
0.811 is a genuine published INTERVAL alpha — for the canonical 3-coder ×
15-unit reliability-data matrix documented by the `krippendorff` Python
package (which reports nominal α = 0.691, interval α = 0.811).  This
implementation reproduces it (0.8108), so it is the primary benchmark, as
the task specification intended.

Two distinct canonical matrices exist in the literature and they have
DIFFERENT interval alphas — 0.811 is not "wrong for interval"; it is the
interval value for the 3×15 matrix specifically:
  - KRIPP_PKG_INTERVAL_MATRIX (3×15)  -> interval α ≈ 0.811
  - KRIPP_INTERVAL_MATRIX     (12×4)  -> interval α ≈ 0.849
Both are asserted below as independent cross-checks of the same formula.
"""
import unittest
import numpy as np

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# --- Primary canonical interval example: the `krippendorff` package fixture ---
# The reliability-data matrix documented by the `krippendorff` Python package:
# 3 coders × 15 units, '*' = missing.  Published: nominal α = 0.691,
# INTERVAL α = 0.811.  This is the value the task specification cited.
# Stored units×coders (the function's expected shape), i.e. the transpose of:
#   coder 1: *  *  *  *  *  3  4  1  2  1  1  3  3  *  3
#   coder 2: 1  *  2  1  3  3  4  3  *  *  *  *  *  *  *
#   coder 3: *  *  2  1  3  4  4  *  2  1  1  3  3  *  4
_nan = np.nan
KRIPP_PKG_INTERVAL_MATRIX = np.array([
    [_nan, 1,    _nan], [_nan, _nan, _nan], [_nan, 2,    2   ], [_nan, 1,    1   ],
    [_nan, 3,    3   ], [3,    3,    4   ], [4,    4,    4   ], [1,    3,    _nan],
    [2,    _nan, 2   ], [1,    _nan, 1   ], [1,    _nan, 1   ], [3,    _nan, 3   ],
    [3,    _nan, 3   ], [_nan, _nan, _nan], [3,    _nan, 4   ],
], dtype=float)

# --- Second canonical matrix: 12 units × 4 coders, interval α ≈ 0.849 ---
# An independent cross-check of the same formula on a different published
# matrix (transcribed from the Wikipedia Krippendorff's alpha article).
# Its interval α (~0.849) differs from the 3×15 matrix's 0.811 simply because
# it is different data — not because 0.811 is "ordinal-only".
KRIPP_INTERVAL_MATRIX = np.array([
    [1,    1,    np.nan, 1     ],  # unit 1
    [2,    2,    3,      2     ],  # unit 2
    [3,    3,    3,      3     ],  # unit 3
    [3,    3,    3,      3     ],  # unit 4
    [2,    2,    2,      2     ],  # unit 5
    [1,    2,    3,      4     ],  # unit 6
    [4,    4,    4,      4     ],  # unit 7
    [1,    1,    2,      1     ],  # unit 8
    [2,    2,    2,      2     ],  # unit 9
    [np.nan, 5,  5,      5     ],  # unit 10
    [np.nan, np.nan, 1,  1     ],  # unit 11
    [np.nan, 3,  np.nan, np.nan],  # unit 12
], dtype=float)

# Perfect agreement: every coder assigns the same value to every unit.
PERFECT_MATRIX = np.array([
    [3, 3, 3],
    [1, 1, 1],
    [5, 5, 5],
    [2, 2, 2],
], dtype=float)

# Maximum disagreement: coders always span the full range.
# For 4 coders and values {1,2,3,4}, repeated identically across units
# — the observed disagreement equals the expected disagreement, so alpha = 0.
# Or use alternating extremes to force alpha < 0.
MAX_DISAGREE_MATRIX = np.array([
    [1, 5, 1, 5],
    [5, 1, 5, 1],
    [1, 5, 1, 5],
    [5, 1, 5, 1],
    [1, 5, 1, 5],
    [5, 1, 5, 1],
], dtype=float)


# ---------------------------------------------------------------------------
# reliability.py tests
# ---------------------------------------------------------------------------

class TestKrippendorffAlpha(unittest.TestCase):

    def setUp(self):
        # Import here so we get a clear ImportError if the module is missing.
        from tools.ablation.reliability import krippendorff_alpha
        self.krippendorff_alpha = krippendorff_alpha

    def test_perfect_agreement(self):
        alpha = self.krippendorff_alpha(PERFECT_MATRIX, level='interval')
        self.assertAlmostEqual(alpha, 1.0, places=6,
                               msg="Perfect agreement must yield alpha == 1.0")

    def test_canonical_interval_example(self):
        # Primary benchmark: the `krippendorff` package's 3×15 reliability-data
        # matrix has published interval α = 0.811 (the value the spec cited).
        alpha = self.krippendorff_alpha(KRIPP_PKG_INTERVAL_MATRIX, level='interval')
        self.assertAlmostEqual(alpha, 0.811, delta=0.01,
                               msg=f"Canonical interval example must yield alpha ~0.811; got {alpha:.4f}")

    def test_second_canonical_matrix_interval(self):
        # Independent cross-check on a different published matrix (12×4) -> ~0.849.
        alpha = self.krippendorff_alpha(KRIPP_INTERVAL_MATRIX, level='interval')
        self.assertAlmostEqual(alpha, 0.849, delta=0.005,
                               msg=f"12×4 matrix must yield alpha ~0.849; got {alpha:.4f}")

    def test_no_agreement_alpha_nonpositive(self):
        alpha = self.krippendorff_alpha(MAX_DISAGREE_MATRIX, level='interval')
        self.assertLessEqual(alpha, 0.0,
                             msg=f"Maximum-disagreement matrix must yield alpha <= 0; got {alpha:.4f}")


# ---------------------------------------------------------------------------
# score.py tests
# ---------------------------------------------------------------------------

def _make_ratings():
    """Minimal synthetic ratings fixture.

    Two dimensions: 'novelty' (high agreement) and 'fidelity' (low agreement).
    Three workers, four ideas across two cells.
    """
    rows = []
    # idea_ids, cell assignments
    ideas = [
        ('idea-A', 'eng1', 'src1'),
        ('idea-B', 'eng1', 'src1'),
        ('idea-C', 'eng2', 'src2'),
        ('idea-D', 'eng2', 'src2'),
    ]
    workers = ['w1', 'w2', 'w3']

    for idea_id, _engine, _source in ideas:
        for pos, worker in enumerate(workers):
            # novelty: perfect agreement -> all assign 4
            rows.append({
                'worker_id': worker,
                'idea_id': idea_id,
                'dimension': 'novelty',
                'value': 4,
                'position': pos,
            })
            # fidelity: maximum disagreement -> workers cycle through 1,3,5
            rows.append({
                'worker_id': worker,
                'idea_id': idea_id,
                'dimension': 'fidelity',
                'value': [1, 3, 5][pos],
                'position': pos,
            })
            # attn: should be ignored by aggregate
            rows.append({
                'worker_id': worker,
                'idea_id': idea_id,
                'dimension': 'attn',
                'value': 3,
                'position': pos,
            })

    return rows


def _make_key_map():
    return {
        'idea-A': {'engine': 'eng1', 'source': 'src1'},
        'idea-B': {'engine': 'eng1', 'source': 'src1'},
        'idea-C': {'engine': 'eng2', 'source': 'src2'},
        'idea-D': {'engine': 'eng2', 'source': 'src2'},
    }


class TestScore(unittest.TestCase):

    def setUp(self):
        from tools.ablation.score import (
            aggregate, reliability_gate, contrasts, position_effect, cell_means,
        )
        self.aggregate = aggregate
        self.reliability_gate = reliability_gate
        self.contrasts = contrasts
        self.position_effect = position_effect
        self.cell_means = cell_means
        self.ratings = _make_ratings()
        self.key_map = _make_key_map()

    # Integration guard: real MTurk rows carry a constant position (-1).
    # position_effect must NOT crash report() on a constant x; it returns nan.
    def test_position_effect_constant_position_no_crash(self):
        rows = [{'worker_id': 'w1', 'idea_id': 'i0', 'dimension': 'originality',
                 'value': 3.0, 'position': -1},
                {'worker_id': 'w2', 'idea_id': 'i1', 'dimension': 'originality',
                 'value': 5.0, 'position': -1},
                {'worker_id': 'w3', 'idea_id': 'i2', 'dimension': 'originality',
                 'value': 2.0, 'position': -1}]
        result = self.position_effect(rows)  # must not raise
        self.assertTrue(np.isnan(result['slope']))
        self.assertIn('note', result)

    # Integration guard: cell_means bridges aggregate() -> transfer().
    def test_cell_means_flattens_to_cell_to_mean(self):
        agg = self.aggregate(self.ratings, self.key_map)
        means = self.cell_means(agg, 'novelty')
        self.assertTrue(all(isinstance(v, float) for v in means.values()))
        self.assertEqual(set(means.keys()), set(agg.keys()))
        for cell, m in means.items():
            self.assertAlmostEqual(m, agg[cell]['novelty']['mean'], places=6)

    # (g) aggregate returns per-cell means; 'attn' rows are excluded
    def test_aggregate_returns_per_cell_means(self):
        result = self.aggregate(self.ratings, self.key_map)
        # Must have entries for both cells
        cells = list(result.keys())
        self.assertGreaterEqual(len(cells), 2, "Expected at least 2 cells")
        # Each entry has 'mean' values per dimension
        for cell, dims in result.items():
            self.assertNotIn('attn', dims, "'attn' dimension must be excluded from aggregate")
            self.assertIn('novelty', dims)
            # novelty mean must be 4.0 (all workers rated 4)
            self.assertAlmostEqual(dims['novelty']['mean'], 4.0, places=5,
                                   msg=f"Cell {cell} novelty mean should be 4.0")

    # (d) reliability_gate tags low-alpha dimension as 'inconclusive'
    def test_reliability_gate_tags_inconclusive(self):
        gate = self.reliability_gate(self.ratings, alpha_floor=0.667)
        self.assertIn('fidelity', gate)
        self.assertEqual(gate['fidelity']['status'], 'inconclusive',
                         f"fidelity should be inconclusive; got {gate['fidelity']}")

    # (e) reliability_gate passes high-alpha dimension
    def test_reliability_gate_passes_high_agreement(self):
        gate = self.reliability_gate(self.ratings, alpha_floor=0.667)
        self.assertIn('novelty', gate)
        self.assertEqual(gate['novelty']['status'], 'pass',
                         f"novelty (perfect agreement) should pass; got {gate['novelty']}")

    # (f) contrasts refuses to rank an inconclusive dimension
    def test_contrasts_refuses_inconclusive_dimension(self):
        gate = self.reliability_gate(self.ratings, alpha_floor=0.667)
        # aggregate result for cells
        cell_data = self.aggregate(self.ratings, self.key_map)
        result = self.contrasts(cell_data, 'fidelity', gate)
        # Must be marked inconclusive, not silently ranked
        self.assertEqual(result['status'], 'inconclusive',
                         "contrasts must return inconclusive for gated dimension, "
                         f"got: {result}")

    # (h) position_effect returns slope and p-value
    def test_position_effect_returns_slope_and_pvalue(self):
        result = self.position_effect(self.ratings)
        self.assertIn('slope', result)
        self.assertIn('p_value', result)
        self.assertIsInstance(result['slope'], float)
        self.assertIsInstance(result['p_value'], float)
        # Must be finite, not NaN/inf — a NaN regression would slip past a
        # bare isinstance(float) check.
        self.assertTrue(np.isfinite(result['slope']),
                        f"slope must be finite; got {result['slope']}")
        self.assertTrue(np.isfinite(result['p_value']),
                        f"p_value must be finite; got {result['p_value']}")
        # p-value is a probability.
        self.assertGreaterEqual(result['p_value'], 0.0)
        self.assertLessEqual(result['p_value'], 1.0)


if __name__ == "__main__":
    unittest.main()

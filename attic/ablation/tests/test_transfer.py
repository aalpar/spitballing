#!/usr/bin/env python3
"""Tests for tools.ablation.transfer.

Covers:
  transfer.py:
    (a) transfer — identical rankings -> rho == 1.0 and transfers is True.
    (b) transfer — reversed rankings -> transfers is False (rho << floor).
    (c) transfer — rho below floor but positive -> transfers is False.
    (d) transfer_statement — transfers True -> no "NOT" in message.
    (e) transfer_statement — transfers False -> "Transfer NOT claimed" in message.

Input-shape contract
--------------------
rank1 and rank2 are each a dict {cell: mean_rating} where cell is a hashable
identifier (e.g. a string or tuple) and mean_rating is a float representing the
Phase-1 (rank1) or Phase-2 (rank2) mean quality score for that experimental cell.
Both dicts must cover the same set of keys.  The implementation sorts the shared
key set to align the two value vectors before calling spearmanr, so positional
correspondence in the dict is never assumed.

Example:
    rank1 = {'A': 4.2, 'B': 3.1, 'C': 2.0, 'D': 1.5}
    rank2 = {'A': 4.0, 'B': 3.3, 'C': 2.1, 'D': 1.6}
    result = transfer(rank1, rank2)
    # -> {'rho': ~1.0, 'p': <0.05, 'transfers': True}
"""
import math
import unittest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Eight cells matching the ablation study's 2x2x2 design.
CELLS = ['cell_A', 'cell_B', 'cell_C', 'cell_D',
         'cell_E', 'cell_F', 'cell_G', 'cell_H']

# Identical ranking: Phase-2 means are proportional to Phase-1 means.
_RANK1_IDENTICAL = {c: float(i + 1) for i, c in enumerate(CELLS)}   # 1.0..8.0
_RANK2_IDENTICAL = {c: float(i + 1) * 2 for i, c in enumerate(CELLS)}  # same order, scaled

# Reversed ranking: Phase-2 is the mirror of Phase-1.
_RANK1_REVERSED = {c: float(i + 1) for i, c in enumerate(CELLS)}    # 1.0..8.0
_RANK2_REVERSED = {c: float(len(CELLS) - i) for i, c in enumerate(CELLS)}  # 8.0..1.0

# Below-floor but positive: rho ~0.5, below the default 0.7 floor.
_RANK1_PARTIAL = {'cell_A': 4.0, 'cell_B': 3.5, 'cell_C': 3.0, 'cell_D': 2.5,
                  'cell_E': 2.0, 'cell_F': 1.8, 'cell_G': 1.5, 'cell_H': 1.0}
_RANK2_PARTIAL = {'cell_A': 4.0, 'cell_B': 1.0, 'cell_C': 3.0, 'cell_D': 2.5,
                  'cell_E': 4.5, 'cell_F': 1.8, 'cell_G': 3.5, 'cell_H': 2.0}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTransfer(unittest.TestCase):

    def setUp(self):
        # Import here so we get a clear ImportError if the module is missing.
        from tools.ablation.transfer import transfer, transfer_statement
        self.transfer = transfer
        self.transfer_statement = transfer_statement

    # (a) Identical rankings -> rho == 1.0, transfers is True.
    def test_identical_rankings_rho_one(self):
        result = self.transfer(_RANK1_IDENTICAL, _RANK2_IDENTICAL)
        self.assertIn('rho', result)
        self.assertIn('p', result)
        self.assertIn('transfers', result)
        self.assertAlmostEqual(result['rho'], 1.0, places=6,
                               msg=f"Identical rankings must yield rho=1.0; got {result['rho']}")
        self.assertTrue(result['transfers'],
                        "Identical rankings must yield transfers=True")

    # (b) Reversed rankings -> transfers is False.
    def test_reversed_rankings_transfers_false(self):
        result = self.transfer(_RANK1_REVERSED, _RANK2_REVERSED)
        self.assertAlmostEqual(result['rho'], -1.0, places=6,
                               msg=f"Reversed rankings must yield rho=-1.0; got {result['rho']}")
        self.assertFalse(result['transfers'],
                         "Reversed rankings must yield transfers=False")

    # (c) Below-floor (positive but < 0.7) -> transfers is False.
    def test_below_floor_transfers_false(self):
        result = self.transfer(_RANK1_PARTIAL, _RANK2_PARTIAL, rho_floor=0.7)
        self.assertFalse(result['transfers'],
                         f"rho={result['rho']:.3f} is below floor 0.7; transfers must be False")

    # (d) transfer_statement for True case must NOT contain "NOT claimed".
    def test_statement_transfers_true(self):
        result = self.transfer(_RANK1_IDENTICAL, _RANK2_IDENTICAL)
        stmt = self.transfer_statement(result)
        self.assertIsInstance(stmt, str)
        self.assertNotIn("NOT claimed", stmt,
                         f"Statement for transfers=True must not say 'NOT claimed'; got: {stmt!r}")

    # (e) transfer_statement for False case must contain "Transfer NOT claimed".
    def test_statement_transfers_false_wording(self):
        result = self.transfer(_RANK1_REVERSED, _RANK2_REVERSED)
        stmt = self.transfer_statement(result)
        self.assertIsInstance(stmt, str)
        self.assertIn("Transfer NOT claimed", stmt,
                      f"Statement for transfers=False must say 'Transfer NOT claimed'; got: {stmt!r}")
        # Must also include the floor value so the reader knows the threshold.
        self.assertIn("0.7", stmt,
                      f"Statement must include the floor value; got: {stmt!r}")

    # (f) NaN rho -> transfers is False (degenerate guard).
    def test_nan_rho_transfers_false(self):
        # Two-cell dict: all identical values -> spearmanr returns nan.
        r1 = {'cell_A': 3.0, 'cell_B': 3.0}
        r2 = {'cell_A': 3.0, 'cell_B': 3.0}
        result = self.transfer(r1, r2)
        # Constant input -> zero variance -> spearmanr rho is nan. transfers
        # must be False unconditionally (never claim transfer on a degenerate
        # correlation), regardless of how scipy encodes the degenerate case.
        self.assertFalse(result['transfers'],
                         f"degenerate/NaN rho must yield transfers=False; got {result}")


if __name__ == "__main__":
    unittest.main()

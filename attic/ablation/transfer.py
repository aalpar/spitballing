#!/usr/bin/env python3
"""Measure Phase-1 -> Phase-2 ranking transfer for the engine ablation study.

Spearman's ρ between the per-cell mean-rating rankings from Phase 1 and Phase 2
determines whether the ordering of experimental cells generalises across topics.
A pre-registered floor (ρ ≥ 0.7) decides whether "transfer" is CLAIMED; below
the floor the report must explicitly state transfer is NOT claimed.

Public API
----------
transfer(rank1, rank2, rho_floor=0.7) -> dict
    Compute Spearman's ρ between two {cell: mean_rating} dicts.
    Returns {'rho': float, 'p': float, 'transfers': bool}.

transfer_statement(result, rho_floor=0.7) -> str
    Return a human-readable sentence suitable for a report.  When transfers is
    False the sentence contains "Transfer NOT claimed".

Input-shape contract
--------------------
rank1 and rank2 are each a dict {cell: mean_rating} where:
  - cell    : any hashable identifier (str, tuple, …) naming the experimental
              cell (e.g. the (engine, source) pair used elsewhere in the study).
  - mean_rating : float, the per-cell mean quality score from that phase.

Both dicts must have the same key set (a mismatch raises ValueError).  The
implementation builds the two value vectors by sorting the shared key set, so
positional correspondence in the dicts is never assumed — the only guarantee is
that rank1[cell] and rank2[cell] end up at the same vector index.

Example
-------
    rank1 = {'A': 4.2, 'B': 3.1, 'C': 2.0, 'D': 1.5}
    rank2 = {'A': 4.0, 'B': 3.3, 'C': 2.1, 'D': 1.6}
    result = transfer(rank1, rank2)
    # -> {'rho': ~1.0, 'p': <0.05, 'transfers': True}
"""
import math

from scipy.stats import spearmanr


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transfer(rank1: dict, rank2: dict, rho_floor: float = 0.7) -> dict:
    """Compute Spearman's ρ between Phase-1 and Phase-2 cell rankings.

    Parameters
    ----------
    rank1:
        {cell: mean_rating} for Phase 1.  'cell' is any hashable identifier.
    rank2:
        {cell: mean_rating} for Phase 2.  Must have the same key set as rank1.
    rho_floor:
        Pre-registered minimum ρ to claim transfer.  Default 0.7.

    Returns
    -------
    dict with keys:
        rho       : float — Spearman's ρ (nan for degenerate inputs).
        p         : float — two-tailed p-value (nan for degenerate inputs).
        transfers : bool  — True iff rho >= rho_floor (False when rho is nan).

    Raises
    ------
    ValueError
        If rank1 and rank2 do not share exactly the same key set.
    """
    keys1, keys2 = set(rank1), set(rank2)
    if keys1 != keys2:
        only1 = keys1 - keys2
        only2 = keys2 - keys1
        raise ValueError(
            f"rank1 and rank2 must have the same key set. "
            f"Only in rank1: {sorted(only1)}. Only in rank2: {sorted(only2)}."
        )

    # Sort the shared key set for a deterministic, alignment-safe ordering.
    # This ensures rank1[cell] and rank2[cell] land at the same vector index.
    ordered_cells = sorted(keys1)
    v1 = [rank1[c] for c in ordered_cells]
    v2 = [rank2[c] for c in ordered_cells]

    result = spearmanr(v1, v2)
    rho = float(result.statistic)
    p = float(result.pvalue)

    # Degenerate case: zero-variance input produces nan from spearmanr.
    transfers = bool(not math.isnan(rho) and rho >= rho_floor)

    return {'rho': rho, 'p': p, 'transfers': transfers}


def transfer_statement(result: dict, rho_floor: float = 0.7) -> str:
    """Return a report-ready sentence describing the transfer result.

    When transfers is False the sentence contains "Transfer NOT claimed" and
    the floor value, so the reader understands the criterion that was missed.

    Parameters
    ----------
    result:
        The dict returned by transfer().
    rho_floor:
        The pre-registered floor used in the study.  Should match the value
        passed to transfer(); defaults to 0.7.

    Returns
    -------
    str — a single sentence ending with a period.
    """
    rho = result['rho']
    p = result['p']
    transfers = result['transfers']

    rho_str = f"{rho:.3f}" if not math.isnan(rho) else "nan"
    p_str = f"{p:.3f}" if not math.isnan(p) else "nan"

    if transfers:
        return (
            f"Transfer CLAIMED: Phase-1 ranking generalises to Phase-2 "
            f"(rho={rho_str}, p={p_str}, floor={rho_floor})."
        )
    if math.isnan(rho):
        return (
            f"Transfer NOT claimed: rho is undefined (nan — a degenerate, "
            f"constant ranking); Phase-1 ordering cannot be correlated with Phase-2."
        )
    return (
        f"Transfer NOT claimed: rho={rho_str} < floor {rho_floor} "
        f"(p={p_str}); Phase-1 ranking does not reliably predict Phase-2 ordering."
    )

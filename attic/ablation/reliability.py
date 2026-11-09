#!/usr/bin/env python3
"""Vendored Krippendorff's alpha for inter-rater reliability.

Implements interval-level alpha using the coincidence-matrix formulation
described in:

  Krippendorff, K. (2004). Content Analysis: An Introduction to Its
  Methodology (2nd ed.). Sage. Chapter 11.

Public API
----------
krippendorff_alpha(matrix, level='interval') -> float
    Compute Krippendorff's alpha from a units×coders reliability matrix.
    Missing values must be encoded as np.nan.  Returns float in (-inf, 1].
    Currently only 'interval' level is implemented.
"""
import numpy as np


def krippendorff_alpha(matrix: np.ndarray, level: str = 'interval') -> float:
    """Compute Krippendorff's alpha for a units×coders reliability matrix.

    Parameters
    ----------
    matrix:
        2-D array shaped (n_units, n_coders).  np.nan marks missing values.
        Rows are units (items rated); columns are coders (raters).
    level:
        Metric level.  Only 'interval' is supported.

    Returns
    -------
    float
        Alpha in (-inf, 1].  1.0 == perfect agreement; 0 == chance;
        negative == worse than chance.

    Raises
    ------
    ValueError
        If level is not 'interval', or if the matrix contains fewer than
        two units with at least two valid (non-NaN) ratings.
    """
    if level != 'interval':
        raise ValueError(f"Unsupported level '{level}'; only 'interval' is implemented.")

    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("matrix must be 2-D (units × coders).")

    # -----------------------------------------------------------------------
    # Coincidence matrix approach (Krippendorff 2004, §11.3)
    #
    # For each unit u, collect all pairable value-pairs (v_i, v_j) where
    # both coders i ≠ j rated unit u.  Each pairable pair contributes 1/(m_u-1)
    # to the coincidence cell c[v_i][v_j], where m_u is the number of valid
    # ratings for that unit.  Only units with m_u >= 2 contribute.
    # -----------------------------------------------------------------------

    # Gather all distinct values (excluding NaN)
    all_values = []
    for row in matrix:
        for v in row:
            if not np.isnan(v):
                all_values.append(v)
    all_values_arr = np.unique(all_values)   # sorted
    n_values = len(all_values_arr)

    if n_values < 2:
        # Degenerate: all raters assigned the same single value -> alpha undefined.
        # Convention: return 1.0 if only one distinct value (perfect, trivially).
        return 1.0

    val_to_idx = {v: i for i, v in enumerate(all_values_arr)}

    # Build coincidence matrix C (n_values × n_values)
    C = np.zeros((n_values, n_values), dtype=float)

    for row in matrix:
        valid_vals = row[~np.isnan(row)]
        m_u = len(valid_vals)
        if m_u < 2:
            continue  # unit cannot contribute pairable values
        weight = 1.0 / (m_u - 1)
        for i in range(len(valid_vals)):
            for j in range(len(valid_vals)):
                if i == j:
                    continue
                vi = valid_vals[i]
                vj = valid_vals[j]
                C[val_to_idx[vi], val_to_idx[vj]] += weight

    # Total coincidences
    n_c = C.sum()
    if n_c == 0:
        raise ValueError("No pairable values found — need at least two raters per unit.")

    # Marginal frequency vector
    n_k = C.sum(axis=1)   # row sums

    # -----------------------------------------------------------------------
    # Observed disagreement (D_o) and expected disagreement (D_e)
    # using the interval metric: delta^2(v_g, v_h) = (v_g - v_h)^2
    # -----------------------------------------------------------------------
    Do = 0.0
    De = 0.0

    for g in range(n_values):
        for h in range(n_values):
            delta = (all_values_arr[g] - all_values_arr[h]) ** 2
            Do += C[g, h] * delta
            De += n_k[g] * n_k[h] * delta

    Do /= n_c
    De /= (n_c * (n_c - 1))

    if De == 0.0:
        # All values identical — perfect agreement, alpha is 1.0.
        return 1.0

    return 1.0 - Do / De

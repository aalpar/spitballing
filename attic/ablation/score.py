#!/usr/bin/env python3
"""Score engine-ablation crowd-study results.

Takes collected ratings and a key_map (from build_hits.build_key_map) and
produces:
  - Per-cell, per-dimension means with bootstrap 95% CIs.
  - Krippendorff alpha gate: dimensions below the floor are flagged
    'inconclusive' and excluded from ranked contrasts.
  - Pairwise Hedges' g effect sizes for every (cell_a, cell_b) pair per
    dimension that PASSED the reliability gate.
  - Position-bias regression: slope + p-value from scipy linregress.
  - A written report (report.md + report.json).

Public API
----------
aggregate(ratings, key_map) -> dict
    Per-cell, per-dimension {'mean', 'ci_low', 'ci_high', 'n'}.
    Skips rows whose dimension == 'attn'.

reliability_gate(ratings, alpha_floor=0.667) -> dict
    Per-dimension {'alpha', 'status'}: status is 'pass' or 'inconclusive'.

contrasts(cells, dimension, gate) -> dict
    Pairwise Hedges' g effect sizes for a dimension.  Returns
    {'status': 'inconclusive'} immediately if the gate marks the dimension
    inconclusive.  NEVER silently drops a gated dimension.

position_effect(ratings) -> dict
    Linear regression of value ~ position; returns {'slope', 'p_value'}.

report(ratings, key_map, out_dir='.', alpha_floor=0.667, seed=0) -> None
    Write report.md and report.json to out_dir.

Data contracts
--------------
ratings: list of dicts with keys:
    worker_id, idea_id, dimension, value, position

key_map: {idea_id: {engine, source}}
    Maps idea to its experimental cell.
"""
import json
import math
import os

import numpy as np
from scipy import stats

from attic.ablation.reliability import krippendorff_alpha


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_RNG_SEED = 0
_N_BOOTSTRAP = 2000


def _bootstrap_ci(values: np.ndarray, seed: int = _RNG_SEED,
                  n: int = _N_BOOTSTRAP, alpha: float = 0.05) -> tuple[float, float]:
    """Return (lo, hi) bootstrap 95% CI for the mean of values."""
    rng = np.random.default_rng(seed)
    means = np.array([
        rng.choice(values, size=len(values), replace=True).mean()
        for _ in range(n)
    ])
    lo = float(np.percentile(means, 100 * alpha / 2))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return lo, hi


def _hedges_g(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Hedges' g effect size between two samples."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float('nan')
    pooled_var = ((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)
    if pooled_var == 0.0:
        return 0.0
    d = (a.mean() - b.mean()) / math.sqrt(pooled_var)
    # Hedges' correction factor J
    df = na + nb - 2
    j = 1.0 - 3.0 / (4 * df - 1)
    return float(d * j)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def aggregate(ratings: list[dict], key_map: dict, seed: int = _RNG_SEED) -> dict:
    """Compute per-cell, per-dimension mean + bootstrap 95% CI.

    Parameters
    ----------
    ratings:
        List of rating dicts: {worker_id, idea_id, dimension, value, position}.
        Rows with dimension == 'attn' are silently skipped.
    key_map:
        {idea_id: {engine, source}}
    seed:
        Seed for the bootstrap RNG (deterministic CIs).

    Returns
    -------
    dict keyed by (engine, source) tuples.  Each value is a dict keyed by
    dimension whose entries are {'mean', 'ci_low', 'ci_high', 'n', 'values'}.
    'values' is the raw rating list, retained so contrasts() can compute an
    exact Hedges' g; report() strips it before JSON serialization.
    """
    # Group values by (cell, dimension)
    buckets: dict[tuple, dict[str, list]] = {}

    for row in ratings:
        dim = row['dimension']
        if dim == 'attn':
            continue
        idea_id = row['idea_id']
        if idea_id not in key_map:
            continue
        meta = key_map[idea_id]
        cell = (meta['engine'], meta['source'])
        buckets.setdefault(cell, {}).setdefault(dim, []).append(float(row['value']))

    result: dict = {}
    for cell, dims in buckets.items():
        result[cell] = {}
        for dim, vals in dims.items():
            arr = np.array(vals, dtype=float)
            lo, hi = _bootstrap_ci(arr, seed=seed)
            result[cell][dim] = {
                'mean': float(arr.mean()),
                'ci_low': lo,
                'ci_high': hi,
                'n': len(arr),
                'values': [float(v) for v in vals],
            }
    return result


def cell_means(aggregate_result: dict, dimension: str) -> dict:
    """Flatten aggregate() output to {cell: mean} for one dimension.

    Bridges score.aggregate() -> transfer.transfer(): the latter expects a flat
    {cell: mean_rating} map per phase.  Cells lacking the dimension are omitted.

    Parameters
    ----------
    aggregate_result:
        Output of aggregate(): {(engine, source): {dim: {mean, ...}}}.
    dimension:
        Which dimension's mean to extract.

    Returns
    -------
    dict
        {(engine, source): mean} over cells that have the dimension.
    """
    return {cell: dims[dimension]['mean']
            for cell, dims in aggregate_result.items()
            if dimension in dims}


def reliability_gate(ratings: list[dict],
                     alpha_floor: float = 0.667) -> dict:
    """Compute per-dimension Krippendorff alpha and apply the reliability gate.

    Parameters
    ----------
    ratings:
        List of rating dicts.  'attn' dimension rows are skipped.
    alpha_floor:
        Minimum acceptable alpha.  Dimensions below this threshold are tagged
        'inconclusive'.

    Returns
    -------
    dict keyed by dimension.  Each value is {'alpha': float, 'status': str}
    where status is 'pass' or 'inconclusive'.
    """
    # Gather all unique workers and ideas per dimension
    from collections import defaultdict

    # Collect ratings by dimension -> {idea_id -> {worker_id -> value}}
    dim_data: dict[str, dict] = defaultdict(lambda: defaultdict(dict))
    for row in ratings:
        dim = row['dimension']
        if dim == 'attn':
            continue
        dim_data[dim][row['idea_id']][row['worker_id']] = float(row['value'])

    result = {}
    for dim, idea_ratings in dim_data.items():
        # Build units × coders matrix (NaN for missing)
        units = sorted(idea_ratings.keys())
        all_workers = sorted({w for ratings_map in idea_ratings.values()
                               for w in ratings_map})
        worker_idx = {w: i for i, w in enumerate(all_workers)}

        mat = np.full((len(units), len(all_workers)), np.nan)
        for ui, uid in enumerate(units):
            for worker, val in idea_ratings[uid].items():
                mat[ui, worker_idx[worker]] = val

        try:
            alpha = krippendorff_alpha(mat, level='interval')
        except (ValueError, ZeroDivisionError):
            alpha = float('nan')

        status = 'pass' if (not math.isnan(alpha) and alpha >= alpha_floor) else 'inconclusive'
        result[dim] = {'alpha': alpha, 'status': status}

    return result


def contrasts(cells: dict, dimension: str, gate: dict) -> dict:
    """Compute pairwise Hedges' g effect sizes between cells for a dimension.

    Parameters
    ----------
    cells:
        Output of aggregate(): {(engine, source): {dimension: {mean, ci_low,
        ci_high, n, values}}}.  The retained raw 'values' let us compute an
        exact Hedges' g (mean difference over pooled SD, with the small-sample
        J correction).
    dimension:
        Which dimension to contrast.
    gate:
        Output of reliability_gate().  If the dimension is 'inconclusive', this
        function returns {'status': 'inconclusive'} immediately and NEVER
        silently drops it.

    Returns
    -------
    {'status': 'inconclusive'} if the gate fails, or a dict:
    {'status': 'pass', 'dimension': str, 'pairs': list of
        {'cell_a', 'cell_b', 'hedges_g', 'mean_a', 'mean_b'}}
    """
    gate_entry = gate.get(dimension, {})
    if gate_entry.get('status') == 'inconclusive':
        return {'status': 'inconclusive', 'dimension': dimension,
                'reason': f"alpha={gate_entry.get('alpha', 'N/A'):.4f} below floor"}

    cell_list = [(cell, stats_map[dimension])
                 for cell, stats_map in cells.items()
                 if dimension in stats_map]

    pairs = []
    for i in range(len(cell_list)):
        for j in range(i + 1, len(cell_list)):
            cell_a, sa = cell_list[i]
            cell_b, sb = cell_list[j]
            # Exact Hedges' g from the retained raw values.
            g = _hedges_g(np.array(sa['values'], dtype=float),
                          np.array(sb['values'], dtype=float))

            pairs.append({
                'cell_a': cell_a,
                'cell_b': cell_b,
                'mean_a': sa['mean'],
                'mean_b': sb['mean'],
                'hedges_g': g,
            })

    return {'status': 'pass', 'dimension': dimension, 'pairs': pairs}


def paired_contrasts(ratings: list[dict], key_map: dict, dimension: str,
                     arm_a: str, arm_b: str, source: str,
                     n_boot: int = 2000, seed: int = _RNG_SEED) -> dict:
    """Paired within-block contrast of two arms on one dimension/source.

    Pairs arm_a vs arm_b by shared block_id (same source); the unit is the
    per-(block, arm) mean rating. Returns {n_blocks, mean_diff, hedges_g,
    ci_low, ci_high}. Blocks present for only one arm are dropped.

    hedges_g is None when within-block differences have zero variance (or only
    one block), because a standardized effect size is undefined in that case.
    mean_diff and the bootstrap CI are still reported — the consistent
    difference remains meaningful.
    """
    blocks: dict = {}
    for r in ratings:
        if r.get("dimension") != dimension:
            continue
        meta = key_map.get(r["idea_id"], {})
        if meta.get("source") != source:
            continue
        eng = meta.get("engine")
        if eng not in (arm_a, arm_b):
            continue
        bid = meta.get("block_id")
        blocks.setdefault(bid, {}).setdefault(eng, []).append(float(r["value"]))

    diffs = []
    for bid, arms in blocks.items():
        if arm_a in arms and arm_b in arms:
            diffs.append(np.mean(arms[arm_a]) - np.mean(arms[arm_b]))
    diffs = np.array(diffs, dtype=float)
    if diffs.size == 0:
        return {"n_blocks": 0, "mean_diff": None, "hedges_g": None,
                "ci_low": None, "ci_high": None}

    mean_diff = float(diffs.mean())
    sd = diffs.std(ddof=1) if diffs.size > 1 else 0.0
    n = diffs.size
    if sd > 0:
        g = mean_diff / sd
        J = 1.0 - (3.0 / (4.0 * (n - 1) - 1)) if n > 1 else 1.0
        g = float(g * J)
    else:
        # Zero within-block variance (or n==1): Hedges' g is undefined — do not
        # fabricate a standardized value. The mean difference + CI still stand.
        g = None
    lo, hi = _bootstrap_ci(diffs, seed=seed, n=n_boot)
    return {"n_blocks": int(n), "mean_diff": mean_diff, "hedges_g": g,
            "ci_low": float(lo), "ci_high": float(hi)}


def position_effect(ratings: list[dict]) -> dict:
    """Regress rating value on display position.

    Skips 'attn' rows.  Returns {'slope', 'p_value', 'r_squared', 'n'}.
    """
    rows = [(float(r['position']), float(r['value']))
            for r in ratings if r.get('dimension') != 'attn']

    if len(rows) < 3:
        return {'slope': float('nan'), 'p_value': float('nan'),
                'r_squared': float('nan'), 'n': len(rows)}

    positions = np.array([r[0] for r in rows])
    values = np.array([r[1] for r in rows])

    # linregress raises on a constant x.  Real MTurk rows currently carry
    # position == -1 for every row (display order is not recoverable from the
    # answer XML), so guard the degenerate case instead of crashing report().
    if len(np.unique(positions)) < 2:
        return {'slope': float('nan'), 'p_value': float('nan'),
                'r_squared': float('nan'), 'n': len(rows),
                'note': 'display position unavailable (constant); regression skipped'}

    result = stats.linregress(positions, values)
    return {
        'slope': float(result.slope),
        'p_value': float(result.pvalue),
        'r_squared': float(result.rvalue ** 2),
        'n': len(rows),
    }


def report(ratings: list[dict], key_map: dict, out_dir: str = '.',
           alpha_floor: float = 0.667, seed: int = 0) -> None:
    """Write report.md and report.json to out_dir.

    Content
    -------
    - Per-cell means table.
    - Reliability gate results (alpha + status per dimension).
    - Gated contrasts (Hedges' g) for passing dimensions.
    - Position effect regression.
    - Explicit 'INCONCLUSIVE dimensions' section listing gated dimensions.
    """
    cells = aggregate(ratings, key_map, seed=seed)
    gate = reliability_gate(ratings, alpha_floor=alpha_floor)
    pos = position_effect(ratings)

    # Compute contrasts for every dimension in the gate
    all_contrasts = {}
    for dim in gate:
        all_contrasts[dim] = contrasts(cells, dim, gate)

    inconclusive_dims = [d for d, v in gate.items() if v['status'] == 'inconclusive']
    passing_dims = [d for d, v in gate.items() if v['status'] == 'pass']

    # Compute paired within-block contrasts for passing dimensions only
    _arms = ["random-seed", "inversion", "lens-shift", "straight"]
    _sources = ("background", "seed")
    all_paired: dict = {}
    for dim in passing_dims:
        dim_pairs = []
        for src in _sources:
            for i in range(len(_arms)):
                for j in range(i + 1, len(_arms)):
                    pc = paired_contrasts(ratings, key_map, dim,
                                         arm_a=_arms[i], arm_b=_arms[j],
                                         source=src, seed=seed)
                    if pc["n_blocks"] > 0:
                        pc["source"] = src
                        pc["arm_a"] = _arms[i]
                        pc["arm_b"] = _arms[j]
                        dim_pairs.append(pc)
        all_paired[dim] = dim_pairs

    # --- JSON report ---
    # Strip the raw 'values' lists (kept only for exact contrasts) so the
    # serialized report stays a compact summary.
    cells_summary = {
        f"{k[0]}|{k[1]}": {
            dim: {kk: vv for kk, vv in stats.items() if kk != 'values'}
            for dim, stats in v.items()
        }
        for k, v in cells.items()
    }
    report_data = {
        'cells': cells_summary,
        'reliability_gate': gate,
        'contrasts': all_contrasts,
        'paired_contrasts': all_paired,
        'position_effect': pos,
        'inconclusive_dimensions': inconclusive_dims,
    }

    json_path = os.path.join(out_dir, 'report.json')
    with open(json_path, 'w', encoding='utf-8') as fh:
        json.dump(report_data, fh, indent=2, default=str)

    # --- Markdown report ---
    lines = [
        '# Engine Ablation Study — Scoring Report',
        '',
        '## Per-Cell Means',
        '',
    ]

    if cells:
        all_dims = sorted({d for cell_data in cells.values() for d in cell_data})
        header = '| engine | source | ' + ' | '.join(all_dims) + ' |'
        sep = '|---|---|' + '|'.join(['---'] * len(all_dims)) + '|'
        lines.append(header)
        lines.append(sep)
        for (eng, src), dims in sorted(cells.items()):
            row_parts = [eng, src]
            for d in all_dims:
                if d in dims:
                    row_parts.append(f"{dims[d]['mean']:.3f} [{dims[d]['ci_low']:.3f}, {dims[d]['ci_high']:.3f}]")
                else:
                    row_parts.append('—')
            lines.append('| ' + ' | '.join(row_parts) + ' |')
        lines.append('')

    lines += [
        '## Reliability Gate',
        '',
        '| dimension | alpha | status |',
        '|---|---|---|',
    ]
    for dim, gd in sorted(gate.items()):
        alpha_str = f"{gd['alpha']:.4f}" if not math.isnan(gd['alpha']) else 'N/A'
        lines.append(f"| {dim} | {alpha_str} | {gd['status']} |")
    lines.append('')

    lines += [
        '## INCONCLUSIVE Dimensions',
        '',
    ]
    if inconclusive_dims:
        for d in inconclusive_dims:
            gd = gate[d]
            alpha_str = f"{gd['alpha']:.4f}" if not math.isnan(gd['alpha']) else 'N/A'
            lines.append(f"- **{d}**: alpha = {alpha_str} (below floor {alpha_floor})")
            lines.append(f"  Contrasts for this dimension are SUPPRESSED — reliability is insufficient.")
    else:
        lines.append('None — all dimensions passed the reliability gate.')
    lines.append('')

    lines += [
        '## Contrasts (Hedges\' g) — Passing Dimensions Only',
        '',
    ]
    for dim in sorted(passing_dims):
        c = all_contrasts[dim]
        lines.append(f"### {dim}")
        if c['status'] == 'pass' and c.get('pairs'):
            lines.append('| cell_a | cell_b | mean_a | mean_b | Hedges\' g |')
            lines.append('|---|---|---|---|---|')
            for p in c['pairs']:
                ca = f"{p['cell_a'][0]}|{p['cell_a'][1]}"
                cb = f"{p['cell_b'][0]}|{p['cell_b'][1]}"
                lines.append(f"| {ca} | {cb} | {p['mean_a']:.3f} | {p['mean_b']:.3f} | {p['hedges_g']:.3f} |")
        lines.append('')

    lines += [
        '## Paired Within-Block Contrasts (Amendment A2) — Passing Dimensions Only',
        '',
    ]
    for dim in sorted(passing_dims):
        dim_pairs = all_paired.get(dim, [])
        lines.append(f"### {dim}")
        if dim_pairs:
            lines.append('| source | arm_a | arm_b | n_blocks | mean_diff | Hedges\' g | CI 95% |')
            lines.append('|---|---|---|---|---|---|---|')
            for p in dim_pairs:
                ci = f"[{p['ci_low']:.3f}, {p['ci_high']:.3f}]"
                g_str = f"{p['hedges_g']:.3f}" if p['hedges_g'] is not None else "undefined"
                lines.append(
                    f"| {p['source']} | {p['arm_a']} | {p['arm_b']}"
                    f" | {p['n_blocks']} | {p['mean_diff']:.3f}"
                    f" | {g_str} | {ci} |"
                )
        lines.append('')

    lines += [
        '## Position Effect',
        '',
        f"- Slope: {pos['slope']:.4f}",
        f"- p-value: {pos['p_value']:.4f}",
        f"- R²: {pos['r_squared']:.4f}",
        f"- N observations: {pos['n']}",
        '',
    ]

    md_path = os.path.join(out_dir, 'report.md')
    with open(md_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')

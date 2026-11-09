"""Deterministic bookkeeping for the blind-panel obviousness measurement.

The LLM supplies the semantic judgment (which cluster each panelist's idea falls
into). This module does only the arithmetic: count *distinct panelists* per
cluster and apply the >=25% threshold. Counting panelists (not ideas) is what
makes the cutoff faithful to "obvious to 25% of the population". Arithmetic, not
vibes -- reproducible and auditable.
"""
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class ObviousCluster:
    label: str
    panelist_count: int
    frac: float


def obvious_clusters(panelist_clusters, n_panelists, threshold=0.25):
    """Return clusters reached by >= threshold of panelists, frac-desc.

    panelist_clusters: iterable of iterables -- one entry per panelist, holding
        the cluster labels that panelist produced (duplicates ignored).
    """
    if n_panelists <= 0:
        raise ValueError("n_panelists must be > 0")
    counts = Counter()
    for clusters in panelist_clusters:
        for label in set(clusters):          # distinct per panelist
            counts[label] += 1
    out = [
        ObviousCluster(label, c, c / n_panelists)
        for label, c in counts.items()
        if c / n_panelists >= threshold
    ]
    out.sort(key=lambda o: (-o.frac, o.label))
    return out

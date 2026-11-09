"""Band membership and ranking.

`in_band` is deterministic. `rank_band` filters to the band, then orders it by
the creative scoring function. That scoring function is the one load-bearing
creative choice in the whole system; the weighting below (fringe weighted higher
than value) is the project owner's decided default.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Candidate:
    text: str
    value_score: float                  # 0..1 fulfillment (LLM value judge)
    fringe_proximity: float             # 0..1 closeness to the negative fringe
    nearest_obvious_cluster: Optional[str] = None   # label if it lands in an
    #                                                 obvious cluster, else None
    violates: tuple = ()                # hard_constraints entries it breaks


def in_band(c, value_threshold=0.6):
    """In-band iff it fulfills (value high), is not obvious (did not land in
    any obvious cluster), and breaks no hard constraint."""
    return (c.value_score >= value_threshold
            and c.nearest_obvious_cluster is None and not c.violates)


def _score(c):
    """Creative scoring: value x fringe, FRINGE WEIGHTED HIGHER. Fringe (surprise)
    leads; value is a lighter pull on top of the in_band floor so a fringe-chaser
    cannot promote a barely-fulfilling idea over a strong one of equal surprise.
    The 0.6/0.4 tilt is deliberately gentler than 0.7/0.3 — surprise still leads,
    but a clearly-stronger-fulfilling idea is harder to leapfrog.
    """
    return 0.6 * c.fringe_proximity + 0.4 * c.value_score


def rank_band(candidates, k, value_threshold=0.6):
    band = [c for c in candidates if in_band(c, value_threshold)]
    band.sort(key=_score, reverse=True)
    return band[:k]


_REQUIRED = ("text", "value_score", "fringe_proximity", "nearest_obvious_cluster")


def rank_records(records, k, value_threshold=0.6):
    """Rank conductor records (dicts) and return the band's records unchanged,
    extra keys included. `nearest_obvious_cluster` must be present (null is
    allowed): an omitted key must not read as "not obvious". `violates` is
    optional; absent reads as none."""
    pairs = []
    for i, r in enumerate(records):
        for key in _REQUIRED:
            if key not in r:
                raise ValueError(f"candidate {i}: missing {key}")
        for key in ("value_score", "fringe_proximity"):
            if isinstance(r[key], bool) or not isinstance(r[key], (int, float)):
                raise ValueError(f"candidate {i}: {key} must be a number")
        violates = r.get("violates", [])
        if not isinstance(violates, list):
            raise ValueError(f"candidate {i}: violates must be a list")
        c = Candidate(**{key: r[key] for key in _REQUIRED},
                      violates=tuple(violates))
        pairs.append((c, r))
    band = [p for p in pairs if in_band(p[0], value_threshold)]
    band.sort(key=lambda p: _score(p[0]), reverse=True)
    return [r for _, r in band[:k]]

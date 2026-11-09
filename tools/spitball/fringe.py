"""Validate the derived negative fringe against the blind panel's near-misses.

The fringe in `map.json` is *derived* -- the leave-one-out complement of the
value criterion's predicates (see `skills/spitballing/SKILL.md`, Stage 1 MAP).
This module checks that derivation against measurement. The blind panel already
produced ~N*K answers; the ones the value judge scores just below the fulfillment
floor are empirical negative-space points. If the panel independently produced a
near-miss along an axis the decomposition never named, the decomposition has a
hole.

The split is the one the rest of the kernel keeps: the conductor supplies the
semantics (a value_score per answer, which answers cluster, which predicate a
cluster relaxes); this module does only the arithmetic -- bucket answers by value
band, count distinct panelists per near-miss cluster, and partition clusters into
those whose dropped predicate is in the derived set (validated) versus those that
are not (the hole).

Asymmetry, deliberately encoded: a measured near-miss cluster missing from the
derived predicates *falsifies* the decomposition -- the panel is a complete
sample, so its production is evidence. A derived predicate with no measured
near-miss proves nothing: instinctive panels skew on-target, so absence is
sampling sparsity, not refutation. There is therefore NO frequency cutoff here
(unlike `obvious_clusters`' 25%): a single panelist reaching an unnamed near-miss
is a real signal, not noise to threshold away. You can only be caught in one
direction, so the tool only looks in that direction.
"""
from collections import Counter
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NearMissCluster:
    label: str
    drops: Optional[str]      # predicate the conductor judges this cluster relaxes
    panelists: int            # distinct panelists who produced an answer in it
    answers: int              # answers in it (>= panelists)
    matched: bool             # drops names a predicate in the derived set


@dataclass(frozen=True)
class FringeReport:
    on_target: int            # answers with value_score >= value_threshold
    near_miss: int            # far_floor <= value_score < value_threshold
    far_negative: int         # value_score < far_floor
    clusters: tuple           # NearMissCluster, sorted (-panelists, -answers, label)
    unmatched: tuple          # labels of clusters with matched == False -- the holes


def fringe_check(predicates, answers, clusters,
                 value_threshold=0.6, far_floor=0.2):
    """Bucket panel answers by value band and reconcile near-miss clusters
    against the derived predicate set.

    predicates: iterable of predicate names from `map.json` (the decomposition).
    answers:    iterable of dicts {panelist, value_score, cluster?} -- one per
                panel answer. `cluster` is the empirical near-miss cluster label,
                or absent/None for answers not assigned to a near-miss cluster.
    clusters:   iterable of dicts {label, drops} -- the conductor's mapping from
                each empirical near-miss cluster to the predicate it relaxes
                (`drops` may be None when it relaxes nothing nameable -- itself an
                unmatched signal).
    """
    if not (0.0 <= far_floor <= value_threshold):
        raise ValueError("require 0 <= far_floor <= value_threshold")

    pred_set = set(predicates)
    drops_of = {c["label"]: c.get("drops") for c in clusters}

    on_target = near_miss = far_negative = 0
    members = {}                       # label -> set of distinct panelists
    answer_counts = Counter()          # label -> answers
    for a in answers:
        v = a["value_score"]
        if v >= value_threshold:
            on_target += 1
            continue
        if v < far_floor:
            far_negative += 1
            continue
        near_miss += 1
        label = a.get("cluster")
        if label is None:              # near-miss the conductor left unclustered
            continue
        members.setdefault(label, set()).add(a["panelist"])
        answer_counts[label] += 1

    out = []
    for label in members:
        drops = drops_of.get(label)
        matched = drops is not None and drops in pred_set
        out.append(NearMissCluster(
            label=label, drops=drops,
            panelists=len(members[label]), answers=answer_counts[label],
            matched=matched,
        ))
    out.sort(key=lambda c: (-c.panelists, -c.answers, c.label))
    unmatched = tuple(c.label for c in out if not c.matched)
    return FringeReport(
        on_target=on_target, near_miss=near_miss, far_negative=far_negative,
        clusters=tuple(out), unmatched=unmatched,
    )

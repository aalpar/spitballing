"""Run-artifact validator: checks one docs/spitball/<topic>/ directory against
the shapes SKILL.md tells the conductor to write, and the flags against the
kernel that derives them. Returns problem strings; empty means valid."""
import json

from tools.spitball.band import Candidate, in_band, rank_records

_CLUSTER_KEYS = ("label", "member_ideas")
_COUNT_KEYS = ("panelist_count", "frac")


def _check_map(m):
    problems = []
    if not m.get("value_criterion"):
        problems.append("map.json: missing value_criterion")
    predicates = m.get("predicates") or []
    if not predicates:
        problems.append("map.json: predicates missing or empty")
    measured = m.get("measured")
    if not isinstance(measured, bool):
        problems.append("map.json: missing measured (true or false)")
    for i, c in enumerate(m.get("obvious_clusters", [])):
        for key in _CLUSTER_KEYS:
            if key not in c:
                problems.append(f"map.json: obvious_clusters[{i}] missing {key}")
        for key in _COUNT_KEYS:
            if measured is False and key in c:
                problems.append(f"map.json: obvious_clusters[{i}] has {key} "
                                "but measured is false")
            elif measured is not False and key not in c:
                problems.append(f"map.json: obvious_clusters[{i}] missing {key}")
    for i, f in enumerate(m.get("negative_fringe", [])):
        if f.get("drops") not in predicates:
            problems.append(f"map.json: negative_fringe[{i}].drops "
                            f"{f.get('drops')!r} not in predicates")
    return problems


def _check_record(i, r, labels):
    if not isinstance(r, dict):
        return [f"candidates.jsonl: [{i}] not an object"]
    where = f"candidates.jsonl: [{i}] {r.get('text')!r}"
    problems = [] if isinstance(r.get("text"), str) else [f"{where}: missing text"]
    for key in ("value_score", "fringe_proximity"):
        v = r.get(key)
        if not isinstance(v, (int, float)) or not 0 <= v <= 1:
            problems.append(f"{where}: {key} {v!r} not in [0, 1]")
    if "nearest_obvious_cluster" not in r:
        problems.append(f"{where}: missing nearest_obvious_cluster")
    elif not isinstance(r["nearest_obvious_cluster"], (str, type(None))):
        problems.append(f"{where}: nearest_obvious_cluster must be a label or null")
    elif r["nearest_obvious_cluster"] is not None and r["nearest_obvious_cluster"] not in labels:
        problems.append(f"{where}: nearest_obvious_cluster "
                        f"{r['nearest_obvious_cluster']!r} is not an obvious_clusters label")
    violates = r.get("violates", [])
    if not isinstance(violates, list):
        problems.append(f"{where}: violates must be a list")
    if problems:
        return problems
    c = Candidate(r["text"], r["value_score"], r["fringe_proximity"],
                  r["nearest_obvious_cluster"], tuple(violates))
    if r.get("obvious") != (c.nearest_obvious_cluster is not None):
        problems.append(f"{where}: obvious flag disagrees with nearest_obvious_cluster")
    if r.get("in_band") != in_band(c):
        problems.append(f"{where}: in_band flag disagrees with band.py")
    return problems


def validate_run(run_dir, *, check_result=True):
    try:
        m = json.loads((run_dir / "map.json").read_text())
        recs = [json.loads(line) for line in
                (run_dir / "candidates.jsonl").read_text().splitlines() if line.strip()]
    except (OSError, ValueError) as e:
        return [f"{run_dir}: unreadable artifacts: {e}"]
    if not isinstance(m, dict):
        return ["map.json: not an object"]
    problems = _check_map(m)
    labels = {c.get("label") for c in m.get("obvious_clusters", [])}
    for i, r in enumerate(recs):
        problems += _check_record(i, r, labels)
    if check_result and not problems:
        result = run_dir / "result.md"
        if not result.exists():
            return ["result.md: missing"]
        text = result.read_text()
        for r in rank_records(recs, k=5):
            if r["text"] not in text:
                problems.append(f"result.md: ranked candidate {r['text']!r} absent")
    return problems

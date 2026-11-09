#!/usr/bin/env python3
"""Collect rater answers from MTurk, dedup, reconcile, and build exposure matrix.

Pulls completed assignments from each HIT in a manifest, parses QuestionForm
XML answers into flat rows, deduplicates, cross-checks against the manifest,
validates attention checks, and computes an exposure matrix showing how many
ratings each experimental cell (engine × source) received.

Pre-registered abort guards are enforced so a compromised dataset fails loudly
instead of silently producing a biased ranking.

Public API
----------
dedup(answers) -> list[dict]
    Remove duplicate (worker_id, idea_id) rows, keeping the first occurrence.

reconcile(manifest, answers) -> dict
    Return {expected, actual, missing_hits, extra}.

attention_pass(answers, checks) -> tuple[dict[str, bool], float]
    Per-worker pass/fail verdicts and overall discard rate.

exposure_matrix(answers, key_map) -> dict[tuple[str,str], int]
    Ratings count per (engine, source) cell, joined through key_map.

assert_guards(answers, key_map, discard_rate, min_per_cell, max_discard=0.30)
    Raise ValueError if any pre-registered abort condition is triggered.

pull(client, manifest) -> list[dict]
    (Live only) Fetch assignments from MTurk and return parsed answer rows.

write_ratings_csv(answers, path) -> None
    Write the deduped answer rows to a CSV file.

write_exposure(matrix, path) -> None
    Write the exposure matrix to a JSON file.
"""
import csv
import json
from collections import defaultdict


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def dedup(answers: list[dict]) -> list[dict]:
    """Remove duplicate (worker_id, idea_id, dimension) rows, keeping the first.

    A genuine duplicate is the SAME worker rating the SAME idea on the SAME
    dimension more than once.  The dimension MUST be part of the key: pull()
    emits one row per (worker, idea, dimension), so a worker who rates an idea
    on N dimensions produces N legitimate rows — keying on (worker, idea) alone
    would silently discard all but one dimension.

    Parameters
    ----------
    answers:
        List of answer row dicts, each containing at minimum
        {worker_id, idea_id, dimension}.  Rows missing 'dimension' are keyed
        with dimension=None (treated as a single implicit dimension).

    Returns
    -------
    list[dict]
        Deduplicated rows in original order with first occurrences preserved.
    """
    seen: set[tuple[str, str, str]] = set()
    result = []
    for row in answers:
        key = (row["worker_id"], row["idea_id"], row.get("dimension"))
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def reconcile(manifest: list[dict], answers: list[dict]) -> dict:
    """Cross-check answers against the manifest.

    Parameters
    ----------
    manifest:
        List of {hit_id, idea_ids} dicts as written by post_hits.write_manifest.
    answers:
        List of answer row dicts, each containing at minimum {idea_id}.

    Returns
    -------
    dict with keys:
        expected    : set[str]  — all idea_ids declared in the manifest
        actual      : set[str]  — all idea_ids seen in answers
        missing_hits: list[str] — hit_ids whose idea_ids are entirely absent
                                  from answers
        extra       : set[str]  — answer idea_ids not declared in any HIT
    """
    expected: set[str] = set()
    hit_to_ids: dict[str, set[str]] = {}
    for entry in manifest:
        ids = set(entry["idea_ids"])
        hit_to_ids[entry["hit_id"]] = ids
        expected |= ids

    actual: set[str] = {row["idea_id"] for row in answers}

    missing_hits: list[str] = [
        hit_id
        for hit_id, ids in hit_to_ids.items()
        if ids.isdisjoint(actual)
    ]

    extra: set[str] = actual - expected

    return {
        "expected": expected,
        "actual": actual,
        "missing_hits": missing_hits,
        "extra": extra,
    }


def attention_pass(
    answers: list[dict],
    checks: list[dict],
) -> tuple[dict[str, bool], float]:
    """Evaluate per-worker attention-check performance.

    A worker passes if every attention-check answer matches the check's
    correct_answer.  Workers who answered no attention checks are excluded
    from the discard-rate denominator.

    Parameters
    ----------
    answers:
        All answer rows (real + attention), each with {worker_id, idea_id, value}.
    checks:
        Attention-check definitions: [{idea_id, correct_answer}, ...].

    Returns
    -------
    verdicts : dict[str, bool]
        True  — worker passed all attention checks they encountered.
        False — worker failed at least one.
    discard_rate : float
        Fraction of workers (among those who answered any check) who failed.
        0.0 when no workers are present.
    """
    check_map: dict[str, int] = {c["idea_id"]: c["correct_answer"] for c in checks}
    check_ids: set[str] = set(check_map)

    # Collect attention answers per worker.
    worker_attn: dict[str, list[dict]] = defaultdict(list)
    for row in answers:
        if row["idea_id"] in check_ids:
            worker_attn[row["worker_id"]].append(row)

    if not worker_attn:
        return {}, 0.0

    verdicts: dict[str, bool] = {}
    for worker_id, rows in worker_attn.items():
        passed = all(r["value"] == check_map[r["idea_id"]] for r in rows)
        verdicts[worker_id] = passed

    n_failed = sum(1 for v in verdicts.values() if not v)
    discard_rate = n_failed / len(verdicts)
    return verdicts, discard_rate


def exposure_matrix(
    answers: list[dict],
    key_map: dict[str, dict],
) -> dict[tuple[str, str], int]:
    """Count ratings per (engine, source) cell.

    Parameters
    ----------
    answers:
        Answer rows, each with {idea_id}.  Attention-check rows (idea_ids
        absent from key_map) are silently skipped.
    key_map:
        {idea_id: {engine, source}} as produced by build_hits.build_key_map.

    Returns
    -------
    dict mapping (engine, source) -> rating count.
    """
    matrix: dict[tuple[str, str], int] = defaultdict(int)
    for row in answers:
        meta = key_map.get(row["idea_id"])
        if meta is None:
            continue
        cell = (meta["engine"], meta["source"])
        matrix[cell] += 1
    return dict(matrix)


def assert_guards(
    answers: list[dict],
    key_map: dict[str, dict],
    discard_rate: float,
    min_per_cell: int,
    max_discard: float = 0.30,
) -> None:
    """Enforce pre-registered abort guards.  Raises ValueError on any violation.

    Guard 1 — Discard rate
        discard_rate > max_discard  ->  raise

    Guard 2 — Join-key integrity
        Any answer whose idea_id is absent from key_map  ->  raise

    Guard 3 — Minimum cell coverage
        Any (engine, source) cell with fewer than min_per_cell ratings  ->  raise

    Parameters
    ----------
    answers:
        Deduped answer rows.
    key_map:
        {idea_id: {engine, source}}.
    discard_rate:
        Pre-computed fraction of workers who failed attention checks
        (from attention_pass).  Assumes a run where every worker encountered
        at least one attention check; attention_pass excludes check-free
        workers from its denominator, so a check-free run yields 0.0 here and
        Guard 1 would not fire.
    min_per_cell:
        Minimum required rating count per (engine, source) cell.
    max_discard:
        Upper bound on discard_rate before aborting (default 0.30).

    Raises
    ------
    ValueError
        With a descriptive message indicating which guard fired and why.
    """
    # Guard 1: discard rate
    if discard_rate > max_discard:
        raise ValueError(
            f"Abort: discard rate {discard_rate:.2%} exceeds pre-registered "
            f"maximum of {max_discard:.2%}.  Dataset integrity compromised."
        )

    # Guard 2: join-key integrity
    unknown = {row["idea_id"] for row in answers if row["idea_id"] not in key_map}
    if unknown:
        bad = ", ".join(sorted(unknown))
        raise ValueError(
            f"Abort: answer(s) reference idea_id(s) absent from key_map: {bad}.  "
            f"Join-key integrity violated."
        )

    # Guard 3: minimum cell coverage
    matrix = exposure_matrix(answers, key_map)
    # Every cell declared in key_map must meet min_per_cell.
    all_cells = {(meta["engine"], meta["source"]) for meta in key_map.values()}
    under = {
        cell: matrix.get(cell, 0)
        for cell in all_cells
        if matrix.get(cell, 0) < min_per_cell
    }
    if under:
        details = "; ".join(
            f"cell {e}/{s}={c}" for (e, s), c in sorted(under.items())
        )
        raise ValueError(
            f"Abort: {len(under)} cell(s) below minimum {min_per_cell} ratings: "
            f"{details}."
        )


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

_CSV_FIELDNAMES = ["worker_id", "idea_id", "dimension", "value", "position"]


def write_ratings_csv(answers: list[dict], path: str) -> None:
    """Write deduped answer rows to a CSV file.

    Parameters
    ----------
    answers:
        Rows as returned by dedup(); each must contain at minimum the fields
        in _CSV_FIELDNAMES.
    path:
        Destination file path.
    """
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(answers)


def load_ratings_jsonl(path: str) -> list[dict]:
    """Load rating rows from a JSONL file (one JSON object per line).

    Folds the canon-fidelity judge's fidelity rows into the crowd ratings list
    before scoring: ``ratings.extend(load_ratings_jsonl(fidelity_path))``.  Each
    line must carry the rating contract {worker_id, idea_id, dimension, value,
    position} (same keys score.aggregate / reliability_gate consume).  Blank
    lines are skipped.
    """
    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_exposure(matrix: dict, path: str) -> None:
    """Write the exposure matrix to a JSON file.

    The (engine, source) tuple keys are serialized as "engine/source" strings
    for JSON compatibility.

    Parameters
    ----------
    matrix:
        As returned by exposure_matrix().
    path:
        Destination file path.
    """
    serializable = {f"{e}/{s}": count for (e, s), count in sorted(matrix.items())}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(serializable, fh, indent=2)


# ---------------------------------------------------------------------------
# Live MTurk pull (boto3 lazy import — not exercised by tests)
# ---------------------------------------------------------------------------

def pull(client, manifest: list[dict]) -> list[dict]:
    """Fetch completed assignments from MTurk and parse answer rows.

    boto3 is NOT imported at module top.  This function receives an already-
    constructed client so boto3 is never required just to import this module.

    Parameters
    ----------
    client:
        An active boto3 MTurk client (from post_hits.client).
    manifest:
        List of {hit_id, idea_ids} dicts as written by post_hits.write_manifest.

    Returns
    -------
    list[dict]
        One row per (worker, idea, dimension) answer:
        {worker_id, idea_id, dimension, value, position}.
    """
    # Local import so boto3 presence is never required at module import time.
    import xml.etree.ElementTree as ET  # stdlib — always available

    rows: list[dict] = []
    for entry in manifest:
        hit_id = entry["hit_id"]
        paginator_kwargs: dict = dict(HITId=hit_id, AssignmentStatuses=["Submitted", "Approved"])
        response = client.list_assignments_for_hit(**paginator_kwargs)
        for assignment in response.get("Assignments", []):
            worker_id = assignment["WorkerId"]
            answer_xml = assignment.get("Answer", "")
            if not answer_xml:
                continue
            try:
                root = ET.fromstring(answer_xml)
            except ET.ParseError:
                continue
            # MTurk QuestionFormAnswers namespace.
            ns_map = {
                "mturk": "http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2005-10-01/QuestionFormAnswers.xsd",
            }
            # Try namespaced first, then un-namespaced.
            answer_elements = root.findall(".//mturk:Answer", ns_map)
            if not answer_elements:
                answer_elements = root.findall(".//Answer")

            for ans_el in answer_elements:
                qid_el = ans_el.find("mturk:QuestionIdentifier", ns_map) or ans_el.find("QuestionIdentifier")
                val_el = ans_el.find("mturk:FreeText", ns_map) or ans_el.find("FreeText")
                if qid_el is None or val_el is None:
                    continue
                qid = (qid_el.text or "").strip()
                raw_val = (val_el.text or "").strip()
                # Attention-check answer: include it tagged dimension="attn"
                # so attention_pass() can score it (NOT a real rating dimension).
                if qid.startswith("attn-check-"):
                    idea_id = qid[len("attn-check-"):]
                    rows.append({
                        "worker_id": worker_id,
                        "idea_id": idea_id,
                        "dimension": "attn",
                        "value": int(raw_val) if raw_val.isdigit() else raw_val,
                        "position": -1,
                    })
                    continue
                # Real question: {idea_id}::{dimension}
                if "::" not in qid:
                    continue
                idea_id, dimension = qid.split("::", 1)
                try:
                    value = int(raw_val)
                except ValueError:
                    value = raw_val
                rows.append({
                    "worker_id": worker_id,
                    "idea_id": idea_id,
                    "dimension": dimension,
                    "value": value,
                    # TODO(ablation #2): -1 placeholder. Join answers back to the
                    # HIT layout to recover the real per-idea display position;
                    # until then score.position_effect reports "unavailable".
                    "position": -1,
                })
    return rows


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Collect MTurk ratings, dedup, reconcile, and build exposure matrix."
    )
    parser.add_argument("manifest", help="manifest.json written by post_hits")
    parser.add_argument("key_map",  help="keys.json written by build_hits")
    parser.add_argument("--env",    choices=["sandbox", "prod"], default="sandbox")
    parser.add_argument("--attention-checks", default=None,
                        help="JSON file: [{idea_id, correct_answer}, ...]")
    parser.add_argument("--min-per-cell", type=int, default=10)
    parser.add_argument("--max-discard",  type=float, default=0.30)
    parser.add_argument("--ratings-out",  default="ratings.csv")
    parser.add_argument("--exposure-out", default="exposure.json")
    args = parser.parse_args()

    # Load inputs.
    with open(args.manifest, encoding="utf-8") as fh:
        manifest_data = json.load(fh)
    with open(args.key_map, encoding="utf-8") as fh:
        key_map_data = json.load(fh)
    checks_data = []
    if args.attention_checks:
        with open(args.attention_checks, encoding="utf-8") as fh:
            checks_data = json.load(fh)

    # Pull from MTurk.
    from attic.ablation.post_hits import client as mturk_client  # noqa: PLC0415
    mturk = mturk_client(args.env)
    raw_answers = pull(mturk, manifest_data)

    # Dedup.
    clean = dedup(raw_answers)

    # Reconcile.
    rec = reconcile(manifest_data, clean)
    if rec["missing_hits"]:
        print(f"WARNING: {len(rec['missing_hits'])} HIT(s) with no answers: "
              f"{rec['missing_hits']}", file=sys.stderr)
    if rec["extra"]:
        print(f"WARNING: {len(rec['extra'])} extra idea_id(s) not in manifest: "
              f"{rec['extra']}", file=sys.stderr)

    # Attention checks.
    _, discard_rate = attention_pass(clean, checks_data)

    # Abort guards.
    assert_guards(
        answers=clean,
        key_map=key_map_data,
        discard_rate=discard_rate,
        min_per_cell=args.min_per_cell,
        max_discard=args.max_discard,
    )

    # Write outputs.
    write_ratings_csv(clean, args.ratings_out)
    matrix = exposure_matrix(clean, key_map_data)
    write_exposure(matrix, args.exposure_out)

    print(f"ratings  -> {args.ratings_out}  ({len(clean)} rows)", file=sys.stderr)
    print(f"exposure -> {args.exposure_out}", file=sys.stderr)

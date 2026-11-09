#!/usr/bin/env python3
"""Tests for the canon-fidelity judge's integration with scoring.

Covers:
  (a) collect.load_ratings_jsonl round-trips the rating-row contract.
  (b) CORE PROPERTY (author TODO): fidelity rows are a drop-in rater set —
      converging judges pass the reliability gate and produce contrasts;
      diverging judges go 'inconclusive' and suppress contrasts.
"""
import json

from tools.ablation.collect import load_ratings_jsonl
from tools.ablation import score


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_load_ratings_jsonl_round_trips_the_contract(tmp_path):
    rows = [
        {"worker_id": "llm-judge-1", "idea_id": "c1-001", "dimension": "fidelity", "value": 6, "position": 1},
        {"worker_id": "llm-judge-2", "idea_id": "c1-001", "dimension": "fidelity", "value": 5, "position": 3},
    ]
    p = tmp_path / "fidelity-ratings.jsonl"
    _write_jsonl(p, rows)
    loaded = load_ratings_jsonl(str(p))
    assert loaded == rows


def test_load_ratings_jsonl_skips_blank_lines(tmp_path):
    p = tmp_path / "f.jsonl"
    p.write_text(
        '{"worker_id":"llm-judge-1","idea_id":"c1-001","dimension":"fidelity","value":4,"position":1}\n\n',
        encoding="utf-8",
    )
    assert len(load_ratings_jsonl(str(p))) == 1


# A 3-idea key_map: two cells so contrasts() has a pair to compare.
_KEY_MAP = {
    "c1-001": {"engine": "inversion", "source": "background"},
    "c1-002": {"engine": "inversion", "source": "background"},
    "c1-003": {"engine": "straight", "source": "background"},
}


def _fidelity_rows(per_judge_scores):
    """Build fidelity rating rows from {worker_id: {idea_id: value}}.

    Mirrors expandJudgeRows on the JS side: dimension is always 'fidelity'.
    position is set to a distinct slot per (judge, idea) so it stays valid even
    though this test does not exercise position_effect.
    """
    rows = []
    for worker_id, scores in per_judge_scores.items():
        for slot, (idea_id, value) in enumerate(scores.items(), start=1):
            rows.append({
                "worker_id": worker_id,
                "idea_id": idea_id,
                "dimension": "fidelity",
                "value": value,
                "position": slot,
            })
    return rows


# Converging panel: 3 judges agree closely AND ideas vary -> high alpha.
_CONVERGING = _fidelity_rows({
    "llm-judge-1": {"c1-001": 6, "c1-002": 5, "c1-003": 2},
    "llm-judge-2": {"c1-001": 6, "c1-002": 5, "c1-003": 1},
    "llm-judge-3": {"c1-001": 7, "c1-002": 4, "c1-003": 2},
})

# Diverging panel: judges contradict each other per idea -> alpha below floor.
_DIVERGING = _fidelity_rows({
    "llm-judge-1": {"c1-001": 1, "c1-002": 7, "c1-003": 1},
    "llm-judge-2": {"c1-001": 7, "c1-002": 1, "c1-003": 7},
    "llm-judge-3": {"c1-001": 1, "c1-002": 7, "c1-003": 4},
})


def test_fidelity_is_a_drop_in_rater(tmp_path):
    # Converging judges should PASS the gate and yield contrasts; diverging
    # judges should go 'inconclusive' and have contrasts SUPPRESSED.
    pass_gate = score.reliability_gate(_CONVERGING)
    fail_gate = score.reliability_gate(_DIVERGING)
    pass_cells = score.aggregate(_CONVERGING, _KEY_MAP)
    pass_contrast = score.contrasts(pass_cells, "fidelity", pass_gate)
    fail_cells = score.aggregate(_DIVERGING, _KEY_MAP)
    fail_contrast = score.contrasts(fail_cells, "fidelity", fail_gate)

    # The core design property: a judge earns trust through agreement under the
    # SAME gate the crowd faces (alpha floor 0.667).
    # 1. Converging judges pass the reliability gate.
    assert pass_gate["fidelity"]["status"] == "pass"
    # 2. Diverging judges fall below the floor and are flagged inconclusive.
    assert fail_gate["fidelity"]["status"] == "inconclusive"
    # 3. A passing dimension yields a REAL comparison. Checking only status would
    #    miss the degenerate case where the gate passes but no cell pair survives
    #    (e.g. a single cell) — so the contrast is "pass" yet ranks nothing. The
    #    non-empty pairs assertion is what proves fidelity actually got ranked.
    assert pass_contrast["status"] == "pass"
    assert pass_contrast["pairs"]
    # 4. An inconclusive dimension is SUPPRESSED, never silently dropped: contrasts
    #    returns an explicit inconclusive status rather than omitting the dimension.
    assert fail_contrast["status"] == "inconclusive"

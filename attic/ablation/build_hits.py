#!/usr/bin/env python3
"""Build blind, randomized CAT HITs for the engine ablation crowd study.

Takes a rated set of idea records and produces per-rater HIT assignments
suitable for MTurk Consensual Assessment Technique (CAT) studies.

Key invariant: rater-visible payloads NEVER expose `engine` or `source`.
Those hidden variables appear only in the separate key_map output so that
the study is not confounded by rater knowledge of condition.

Public API
----------
load_rated_set(path) -> list[dict]
    Read JSONL where each line is {id, engine, source, text}.

build_key_map(ideas) -> dict[str, dict]
    {idea_id: {engine, source, block_id}} — the hidden variable map.

write_key_map(key_map, path) -> None
    Serialize key_map to JSON at the given path.

partition_into_hits(ideas, ideas_per_hit, seed) -> list[list[dict]]
    Split ideas into chunks of <= ideas_per_hit, stratified by the hidden
    (engine, source) cell so each chunk samples broadly.  Deterministic in seed.

build_assignments(ideas, raters, attention_items, rng_seed, ideas_per_hit=12)
    Produce one Assignment per HIT (chunk of ideas), each rated by `raters`
    workers via MaxAssignments.  Items are rater-visible (idea_id, position,
    text) with attention checks interleaved; engine/source are absent.

render_question_xml(assignment, dimensions) -> str
    MTurk QuestionForm XML for the assignment.  QuestionIdentifiers encode
    idea_id, never the engine.
"""
import json
import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Assignment:
    """One HIT: a chunk of ideas rated by `max_assignments` independent workers.

    items — rater-visible list of dicts, each containing:
      For a real idea:         {idea_id, position, text}
      For an attention check:  {idea_id, position, text, correct_answer,
                                 is_attention_check: True}

    Engine and source are deliberately absent from every item.  `max_assignments`
    is posted to MTurk as MaxAssignments — i.e. how many distinct workers rate
    this HIT (the per-idea rater count).
    """
    hit_index: int
    items: list = field(default_factory=list)
    max_assignments: int = 1


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_rated_set(path: str) -> list[dict]:
    """Read a JSONL file; each line must have {id, engine, source, text}."""
    ideas = []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            record = json.loads(raw)
            for key in ("id", "engine", "source", "text"):
                if key not in record:
                    raise ValueError(f"Line {lineno}: missing required key '{key}'")
            ideas.append(record)
    return ideas


def build_key_map(ideas: list[dict]) -> dict:
    """Return {idea_id: {engine, source, block_id}} — the hidden variable map.

    Never returns `text` or any rater-visible field; only the hidden
    experimental variables are stored here.  `block_id` is None for corpora
    predating the blocked design.
    """
    return {
        idea["id"]: {
            "engine": idea["engine"],
            "source": idea["source"],
            "block_id": idea.get("block_id"),
        }
        for idea in ideas
    }


def write_key_map(key_map: dict, path: str) -> None:
    """Write key_map to ``path`` as pretty-printed JSON."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(key_map, fh, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Core assignment builder
# ---------------------------------------------------------------------------

def _interleave_attention(idea_items: list[dict], attention_items: list[dict],
                           rng: random.Random) -> list[dict]:
    """Return a new list with attention checks spread evenly through idea_items.

    Insertion positions are chosen so checks are distributed, not clustered,
    but exact positions are randomised within that constraint.
    """
    n = len(idea_items)
    k = len(attention_items)
    if k == 0:
        return list(idea_items)

    # Divide the idea list into k+1 buckets; drop one attention check between
    # each adjacent pair of buckets.  Bucket boundaries are slightly jittered.
    result = list(idea_items)
    # Build k insertion indices spread across [0, n], each offset slightly.
    step = n / (k + 1)
    positions = sorted(
        min(n, max(0, int(step * (i + 1) + rng.uniform(-step * 0.3, step * 0.3))))
        for i in range(k)
    )
    # Insert from right to left so earlier indices remain valid.
    shuffled_attn = list(attention_items)
    rng.shuffle(shuffled_attn)
    for pos, attn in zip(reversed(positions), reversed(shuffled_attn)):
        result.insert(pos, dict(attn))
    return result


def partition_into_hits(ideas: list[dict], ideas_per_hit: int,
                        seed: int) -> list[list[dict]]:
    """Split ideas into chunks of <= ideas_per_hit, stratified by cell.

    Ideas are grouped by their hidden (engine, source) cell, shuffled within
    each group, then drawn round-robin across groups into one flat stratified
    order before chunking.  As a result each full chunk samples many cells —
    this keeps the study blind (a worker can't infer condition from a chunk
    dominated by one cell) and keeps per-cell exposure balanced across HITs.

    Deterministic in ``seed``.  The returned chunks contain the FULL idea dicts
    (engine/source included) — blinding is applied later in build_assignments.

    Parameters
    ----------
    ideas:
        Rated set; each dict has at minimum {id, text} and (for stratification)
        {engine, source}.
    ideas_per_hit:
        Maximum ideas per HIT (must be >= 1).
    seed:
        RNG seed for the within-cell shuffle.

    Returns
    -------
    list[list[dict]]
        Chunks of ideas; every idea appears in exactly one chunk.
    """
    if ideas_per_hit < 1:
        raise ValueError("ideas_per_hit must be >= 1")

    rng = random.Random(seed)
    groups: dict = {}
    for idea in ideas:
        cell = (idea.get("engine"), idea.get("source"))
        groups.setdefault(cell, []).append(idea)

    # Deterministic cell order, shuffled within each cell.
    buckets = []
    for cell in sorted(groups, key=lambda c: (str(c[0]), str(c[1]))):
        bucket = list(groups[cell])
        rng.shuffle(bucket)
        buckets.append(bucket)

    # Round-robin across cells -> stratified flat order.
    ordered: list[dict] = []
    pointers = [0] * len(buckets)
    total = len(ideas)
    while len(ordered) < total:
        for bi, bucket in enumerate(buckets):
            if pointers[bi] < len(bucket):
                ordered.append(bucket[pointers[bi]])
                pointers[bi] += 1

    return [ordered[i:i + ideas_per_hit] for i in range(0, total, ideas_per_hit)]


def build_assignments(
    ideas: list[dict],
    raters: int,
    attention_items: list[dict],
    rng_seed: int,
    ideas_per_hit: int = 12,
) -> list["Assignment"]:
    """Build one blinded Assignment per HIT (chunk of ideas).

    Ideas are partitioned into HITs of <= ideas_per_hit (stratified by cell);
    each HIT is a single QuestionForm shown to ``raters`` independent workers
    via MaxAssignments, so every idea receives ``raters`` ratings.

    Parameters
    ----------
    ideas:
        Full rated set — each dict must have at minimum {id, text}.
        engine/source are used only for stratification and never reach items.
    raters:
        Workers per HIT — stored as Assignment.max_assignments (the per-idea
        rater count, pre-registered at 5).
    attention_items:
        Dicts describing attention-check items (>= {idea_id, text}).  The pool
        is interleaved into EACH HIT; pass ~1 for one check per HIT.
        ``is_attention_check`` is set to True if absent.
    rng_seed:
        Base seed.  Partitioning uses rng_seed; HIT h shuffles with
        random.Random(rng_seed + h) so order is reproducible and per-HIT
        distinct.  (Within a HIT, order is fixed across the HIT's workers —
        MTurk shows one form per HIT — which makes `position` well-defined.)
    ideas_per_hit:
        Maximum ideas per HIT (default 12).

    Returns
    -------
    list[Assignment]
        One Assignment per HIT, hit_index 0..H-1.
    """
    # Normalise attention items: ensure is_attention_check=True.
    norm_attn = []
    for a in attention_items:
        item = dict(a)
        item["is_attention_check"] = True
        # Strip engine/source if accidentally present.
        item.pop("engine", None)
        item.pop("source", None)
        norm_attn.append(item)

    hits = partition_into_hits(ideas, ideas_per_hit, rng_seed)

    assignments = []
    for hit_index, chunk in enumerate(hits):
        rng = random.Random(rng_seed + hit_index)

        # Build rater-visible idea items — no engine/source.
        idea_items = [{"idea_id": idea["id"], "text": idea["text"]}
                      for idea in chunk]
        rng.shuffle(idea_items)

        # Interleave attention checks, then assign 0-based positions.
        merged = _interleave_attention(idea_items, norm_attn, rng)
        for pos, item in enumerate(merged):
            item["position"] = pos

        assignments.append(
            Assignment(hit_index=hit_index, items=merged, max_assignments=raters))

    return assignments


# ---------------------------------------------------------------------------
# XML rendering
# ---------------------------------------------------------------------------

_MTURK_NS = "http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2005-10-01/QuestionForm.xsd"


def render_question_xml(assignment: "Assignment", dimensions: list[str]) -> str:
    """Return a well-formed MTurk QuestionForm XML string for the assignment.

    For each displayed item and each dimension, one question is emitted.
    QuestionIdentifiers use the pattern ``{idea_id}::{dimension}`` so that
    answers can be grouped by idea in post-processing — the engine is never
    encoded in the identifier.

    Attention-check items get a single yes/no or multiple-choice question
    with identifier ``attn-check-{idea_id}``.
    """
    root = ET.Element("QuestionForm")
    root.set("xmlns", _MTURK_NS)

    for item in assignment.items:
        if item.get("is_attention_check"):
            q = ET.SubElement(root, "Question")
            qid = ET.SubElement(q, "QuestionIdentifier")
            qid.text = f"attn-check-{item['idea_id']}"
            disp = ET.SubElement(q, "DisplayName")
            disp.text = "Attention Check"
            is_req = ET.SubElement(q, "IsRequired")
            is_req.text = "true"
            content = ET.SubElement(q, "QuestionContent")
            text_el = ET.SubElement(content, "Text")
            text_el.text = item["text"]
            answer_spec = ET.SubElement(q, "AnswerSpecification")
            sel = ET.SubElement(answer_spec, "SelectionAnswer")
            min_sel = ET.SubElement(sel, "MinSelectionCount")
            min_sel.text = "1"
            max_sel = ET.SubElement(sel, "MaxSelectionCount")
            max_sel.text = "1"
            style = ET.SubElement(sel, "StyleSuggestion")
            style.text = "radiobutton"
            selections = ET.SubElement(sel, "Selections")
            for val in range(1, 8):  # 1-7 Likert (pre-registered scale)
                sel_el = ET.SubElement(selections, "Selection")
                sel_id = ET.SubElement(sel_el, "SelectionIdentifier")
                sel_id.text = str(val)
                sel_text = ET.SubElement(sel_el, "Text")
                sel_text.text = str(val)
        else:
            for dim in dimensions:
                q = ET.SubElement(root, "Question")
                qid = ET.SubElement(q, "QuestionIdentifier")
                # Encode idea_id + dimension; NEVER engine/source.
                qid.text = f"{item['idea_id']}::{dim}"
                disp = ET.SubElement(q, "DisplayName")
                disp.text = f"{dim.capitalize()} — Idea {item['position'] + 1}"
                is_req = ET.SubElement(q, "IsRequired")
                is_req.text = "true"
                content = ET.SubElement(q, "QuestionContent")
                text_el = ET.SubElement(content, "Text")
                text_el.text = item["text"]
                answer_spec = ET.SubElement(q, "AnswerSpecification")
                sel = ET.SubElement(answer_spec, "SelectionAnswer")
                min_sel = ET.SubElement(sel, "MinSelectionCount")
                min_sel.text = "1"
                max_sel = ET.SubElement(sel, "MaxSelectionCount")
                max_sel.text = "1"
                style = ET.SubElement(sel, "StyleSuggestion")
                style.text = "radiobutton"
                selections = ET.SubElement(sel, "Selections")
                for val in range(1, 8):  # 1-7 Likert (pre-registered scale)
                    sel_el = ET.SubElement(selections, "Selection")
                    sel_id = ET.SubElement(sel_el, "SelectionIdentifier")
                    sel_id.text = str(val)
                    sel_text = ET.SubElement(sel_el, "Text")
                    sel_text.text = str(val)

    return ET.tostring(root, encoding="unicode", xml_declaration=False)


# ---------------------------------------------------------------------------
# CLI entry point (optional)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Build blind CAT HIT assignments from a rated JSONL set."
    )
    parser.add_argument("input", help="JSONL file: one {id,engine,source,text} per line")
    parser.add_argument("--raters", type=int, default=5,
                        help="Workers per HIT / ratings per idea (default: 5)")
    parser.add_argument("--ideas-per-hit", type=int, default=12,
                        help="Maximum ideas per HIT (default: 12)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dimensions", nargs="+",
                        default=["originality", "value"])
    parser.add_argument("--attention-pool", default=None,
                        help="JSON file: [{idea_id, text, correct_answer}, ...]. "
                             "The whole pool is interleaved into EACH HIT, so its "
                             "length is the number of checks per HIT.")
    parser.add_argument("--attention-key-out", default="attention-key.json",
                        help="Filename (under --out-dir) for the [{idea_id, "
                             "correct_answer}] grading key consumed by "
                             "`collect --attention-checks`.")
    parser.add_argument("--out-dir", default=".", help="Directory for output files")
    args = parser.parse_args()

    import json
    import os
    ideas = load_rated_set(args.input)
    key_map = build_key_map(ideas)
    key_path = os.path.join(args.out_dir, "keys.json")
    write_key_map(key_map, key_path)
    print(f"Key map written to {key_path}", file=sys.stderr)

    # Load the attention-check pool (worker-visible question + hidden answer).
    attention_items: list[dict] = []
    if args.attention_pool:
        with open(args.attention_pool, encoding="utf-8") as fh:
            attention_items = json.load(fh)
        # Emit the answer key (idea_id -> correct_answer) for the collect step.
        # The correct_answer never enters the rendered HIT, only this side file.
        attn_key = [{"idea_id": a["idea_id"], "correct_answer": a["correct_answer"]}
                    for a in attention_items]
        attn_key_path = os.path.join(args.out_dir, args.attention_key_out)
        with open(attn_key_path, "w", encoding="utf-8") as fh:
            json.dump(attn_key, fh, indent=2)
        print(f"Attention key ({len(attn_key)} checks/HIT) written to {attn_key_path}",
              file=sys.stderr)
    else:
        print("WARNING: no --attention-pool given; HITs will have NO attention "
              "checks and the §4/§5 discard guards cannot fire.", file=sys.stderr)

    assignments = build_assignments(
        ideas=ideas,
        raters=args.raters,
        attention_items=attention_items,
        rng_seed=args.seed,
        ideas_per_hit=args.ideas_per_hit,
    )
    for asgn in assignments:
        out_path = os.path.join(args.out_dir, f"hit_{asgn.hit_index:03d}.xml")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(render_question_xml(asgn, args.dimensions))
        print(f"  HIT {asgn.hit_index} (x{asgn.max_assignments} workers): {out_path}",
              file=sys.stderr)

#!/usr/bin/env python3
"""Tests for tools.ablation.build_hits — blind, randomized, CHUNKED CAT HITs.

The HIT unit is one small chunk of ideas, rated by `raters` independent
workers (MaxAssignments). Verifies:
  partition_into_hits:
    (p1) every idea appears exactly once across all chunks (no drop/dup);
    (p2) chunk count = ceil(n / ideas_per_hit); each chunk size <= ideas_per_hit;
    (p3) chunks are stratified — a full chunk spans multiple (engine, source) cells;
    (p4) deterministic in seed; ideas_per_hit >= n -> a single chunk.
  build_assignments (per-HIT):
    (a) one Assignment per HIT; max_assignments == raters; hit_index 0..H-1;
    (b) every real idea appears exactly once across all HITs;
    (c) attention check(s) interleaved per HIT;
    (d) 0-based consecutive positions within each HIT;
    (e) engine/source NEVER in the rater-visible payload — only in key_map;
    (f) determinism: same rng_seed -> identical assignments.
"""
import math
import unittest
import xml.etree.ElementTree as ET

from tools.ablation.build_hits import (
    Assignment,
    build_assignments,
    build_key_map,
    partition_into_hits,
    render_question_xml,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ENGINES = ["mashup", "diverge", "reduce", "baseline"]
SOURCES = ["gpt4", "claude3"]
_CELLS = [(e, s) for e in ENGINES for s in SOURCES]  # 8 cells

# 8 cells x 3 ideas = 24 ideas — enough to exercise chunking.
IDEA_DICTS = [
    {"id": f"idea-{i:02d}", "engine": e, "source": s, "text": f"Idea text number {i}."}
    for i, (e, s) in enumerate(_CELLS * 3)
]  # 24 ideas

ATTENTION_ITEMS = [
    {"idea_id": "attn-1", "text": "Select the second option.", "correct_answer": 2, "is_attention_check": True},
]

RATERS = 5
RNG_SEED = 42
IDEAS_PER_HIT = 8

_CELL_OF = {d["id"]: (d["engine"], d["source"]) for d in IDEA_DICTS}


# ---------------------------------------------------------------------------
# partition_into_hits
# ---------------------------------------------------------------------------

class TestPartitionIntoHits(unittest.TestCase):

    def setUp(self):
        self.hits = partition_into_hits(IDEA_DICTS, IDEAS_PER_HIT, RNG_SEED)

    def test_every_idea_once(self):
        seen = [idea["id"] for chunk in self.hits for idea in chunk]
        self.assertEqual(sorted(seen), sorted(d["id"] for d in IDEA_DICTS),
                         "every idea must appear exactly once across chunks")
        self.assertEqual(len(seen), len(set(seen)), "no idea duplicated")

    def test_chunk_count_and_sizes(self):
        expected = math.ceil(len(IDEA_DICTS) / IDEAS_PER_HIT)
        self.assertEqual(len(self.hits), expected)
        for chunk in self.hits:
            self.assertLessEqual(len(chunk), IDEAS_PER_HIT)

    def test_chunks_are_stratified(self):
        # A full chunk drawn round-robin across 8 cells should span many cells,
        # never be dominated by one cell.
        full = [c for c in self.hits if len(c) == IDEAS_PER_HIT][0]
        cells = {(idea["engine"], idea["source"]) for idea in full}
        self.assertGreater(len(cells), 1, "a full chunk must mix multiple cells")

    def test_deterministic(self):
        again = partition_into_hits(IDEA_DICTS, IDEAS_PER_HIT, RNG_SEED)
        self.assertEqual([[i["id"] for i in c] for c in self.hits],
                         [[i["id"] for i in c] for c in again])

    def test_single_chunk_when_hit_size_exceeds_n(self):
        hits = partition_into_hits(IDEA_DICTS, len(IDEA_DICTS) + 5, RNG_SEED)
        self.assertEqual(len(hits), 1)
        self.assertEqual(len(hits[0]), len(IDEA_DICTS))

    def test_rejects_nonpositive_hit_size(self):
        with self.assertRaises(ValueError):
            partition_into_hits(IDEA_DICTS, 0, RNG_SEED)


# ---------------------------------------------------------------------------
# build_assignments (per-HIT)
# ---------------------------------------------------------------------------

class TestBuildAssignments(unittest.TestCase):

    def setUp(self):
        self.assignments = build_assignments(
            ideas=IDEA_DICTS,
            raters=RATERS,
            attention_items=ATTENTION_ITEMS,
            rng_seed=RNG_SEED,
            ideas_per_hit=IDEAS_PER_HIT,
        )

    def test_one_assignment_per_hit(self):
        expected = math.ceil(len(IDEA_DICTS) / IDEAS_PER_HIT)
        self.assertEqual(len(self.assignments), expected)
        self.assertEqual([a.hit_index for a in self.assignments],
                         list(range(expected)))

    def test_max_assignments_is_raters(self):
        for a in self.assignments:
            self.assertEqual(a.max_assignments, RATERS,
                             "each HIT must request `raters` workers via MaxAssignments")

    def test_every_real_idea_once_across_hits(self):
        seen = [item["idea_id"]
                for a in self.assignments
                for item in a.items if not item.get("is_attention_check")]
        self.assertEqual(sorted(seen), sorted(d["id"] for d in IDEA_DICTS),
                         "every real idea must appear exactly once across all HITs")
        self.assertEqual(len(seen), len(set(seen)), "no idea rated in two HITs")

    def test_attention_check_per_hit(self):
        for a in self.assignments:
            attn = [item for item in a.items if item.get("is_attention_check")]
            self.assertEqual(len(attn), len(ATTENTION_ITEMS))

    def test_positions_zero_based_consecutive(self):
        for a in self.assignments:
            positions = [item["position"] for item in a.items]
            self.assertEqual(positions, list(range(len(a.items))))

    def test_blinding_no_engine_source(self):
        for a in self.assignments:
            for item in a.items:
                self.assertNotIn("engine", item)
                self.assertNotIn("source", item)

    def test_key_map_holds_hidden_vars_only(self):
        key_map = build_key_map(IDEA_DICTS)
        for idea in IDEA_DICTS:
            entry = key_map[idea["id"]]
            self.assertEqual(entry["engine"], idea["engine"])
            self.assertEqual(entry["source"], idea["source"])
            self.assertNotIn("text", entry)

    def test_key_map_includes_block_id(self):
        ideas = [
            {"id": "c1-001", "engine": "random-seed", "source": "background",
             "block_id": "bg:00", "text": "..."},
            {"id": "c1-002", "engine": "straight", "source": "seed",
             "block_id": "seed:00", "text": "..."},
        ]
        km = build_key_map(ideas)
        self.assertEqual(km["c1-001"]["block_id"], "bg:00")
        self.assertEqual(km["c1-002"]["block_id"], "seed:00")
        # still no rater-visible field leaked
        self.assertNotIn("text", km["c1-001"])

    def test_determinism(self):
        again = build_assignments(
            ideas=IDEA_DICTS, raters=RATERS, attention_items=ATTENTION_ITEMS,
            rng_seed=RNG_SEED, ideas_per_hit=IDEAS_PER_HIT,
        )
        for a1, a2 in zip(self.assignments, again):
            self.assertEqual([i["idea_id"] for i in a1.items],
                             [i["idea_id"] for i in a2.items])


# ---------------------------------------------------------------------------
# render_question_xml
# ---------------------------------------------------------------------------

class TestRenderQuestionXml(unittest.TestCase):

    def _make_assignment(self):
        assignments = build_assignments(
            ideas=IDEA_DICTS[:6], raters=5, attention_items=ATTENTION_ITEMS[:1],
            rng_seed=99, ideas_per_hit=6,
        )
        return assignments[0]

    def test_xml_is_parseable(self):
        xml_str = render_question_xml(self._make_assignment(),
                                      ["originality", "appropriateness"])
        self.assertIsNotNone(ET.fromstring(xml_str))

    def test_xml_has_no_engine_or_source(self):
        xml_str = render_question_xml(self._make_assignment(), ["originality"])
        self.assertNotIn("engine", xml_str)
        self.assertNotIn("source", xml_str)

    def test_xml_question_identifiers_use_idea_id(self):
        xml_str = render_question_xml(self._make_assignment(), ["originality"])
        root = ET.fromstring(xml_str)
        ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
        ns_prefix = f"{{{ns}}}" if ns else ""
        identifiers = [
            el.text for el in root.iter(f"{ns_prefix}QuestionIdentifier")
            if el.text and not el.text.startswith("attn-check-")
        ]
        self.assertTrue(identifiers)
        for ident in identifiers:
            self.assertTrue(any(ident.startswith(idea["id"]) for idea in IDEA_DICTS),
                            f"identifier '{ident}' must be based on idea_id")


if __name__ == "__main__":
    unittest.main()

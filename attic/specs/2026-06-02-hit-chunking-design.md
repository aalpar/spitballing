# HIT Chunking — Design

**Problem.** `build_hits.build_assignments` emits one Assignment per rater containing
*every* idea. Phase 1 (160 ideas × 2 dimensions) becomes ~5 HITs of ~320 questions —
unpostable, and only ~5 distinct workers would see the whole study (fragile reliability).
Resolves TODO 1.

**Fix.** Switch to the standard CAT unit: one HIT per small chunk of ideas, each completed
by N independent workers via `MaxAssignments`.

## Components

- `partition_into_hits(ideas, ideas_per_hit, seed) -> list[list[dict]]`
  Split ideas into chunks of ≤ `ideas_per_hit`, **stratified by cell** (round-robin over
  `(engine, source)` groups using the hidden metadata) so each chunk samples broadly —
  blinding holds and per-cell exposure stays balanced. Deterministic in `seed`.

- `build_assignments(ideas, raters, attention_items, rng_seed, ideas_per_hit=12)`
  Returns **one Assignment per HIT** (was: per rater). Each Assignment carries
  `max_assignments = raters`, its chunk's rater-visible items `{idea_id, position, text}`
  (no engine/source), and ~1 interleaved attention check. `position` is the item's index
  within its HIT — now well-defined.

- `post_hits.create_batch(..., dimensions, ...)` posts each Assignment with
  `MaxAssignments = assignment.max_assignments` (default per-HIT changes 1 → raters).
  CLI gains `--ideas-per-hit` (default 12).

## Unchanged
Blinding (engine/source never in rater-visible items), `key_map`/`keys.json`,
`idea_id::dimension` question keying, 1–7 Likert, abort guards, the `id`→`idea_id` join.

## Decisions
- `ideas_per_hit` default **12** → 14 HITs × 5 raters = 70 assignments/phase. CLI-overridable.
- `raters` stays 5 (pre-registered), realized as `MaxAssignments`.
- Whole-set mode is **replaced**, not kept (unpostable; zero consumers).

## Out of scope
TODO 2 (collect.pull joining answers→manifest to recover position) — chunking makes
position *exist* in the manifest, but the answer-side join is separate work.

## Testing
TDD. `partition_into_hits`: all ideas covered once, chunk sizes ≤ N, stratified, seed-
deterministic. `build_assignments`: per-HIT count = #chunks, `max_assignments == raters`,
positions recorded, no engine/source leak, attention check present. Update existing
build_hits tests to the per-HIT model.

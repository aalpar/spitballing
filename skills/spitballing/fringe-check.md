# Fringe check (optional MAP step)

The derived fringe is a claim; the pooled panel answers already hold the
evidence.

Score the panel's ~N×K pooled answers with the same `value_score` judgment
CONVERGE uses (value only: `hard_constraints` filter candidates, not fringe
evidence), keeping each answer's `panelist` index. At scale this is one
judge-agent pass; blindness doesn't apply, since the value judge isn't the panel.

Take the near-misses, just below the floor (`fringe-check` defaults to
`0.2 ≤ value < 0.6`), and cluster them by which predicate each relaxes: a fresh
clustering, distinct from the obvious clusters. Tag each cluster with that
predicate as `drops`. Every pooled answer goes in `answers` with its `panelist`
and `value_score`; only near-miss answers carry a `cluster`:

```bash
echo '{"predicates":["COOLING","HEAD"],
       "answers":[{"panelist":0,"value_score":0.9},
                  {"panelist":3,"value_score":0.4,"cluster":"cold-not-cranial"}],
       "clusters":[{"label":"cold-not-cranial","drops":"HEAD"}]}' \
  | PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m tools.spitball fringe-check
```

Each label in `unmatched` is a near-miss along an axis your `predicates` don't
name, a hole in the decomposition: add the predicate, re-derive its landmark,
rewrite `map.json`. One-directional on purpose: a predicate with no near-miss is
not evidence, because instinctive panels skew on-target and absence is sampling
sparsity.

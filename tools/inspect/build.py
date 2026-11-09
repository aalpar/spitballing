"""Render a spitball run as a self-contained HTML page.

    python3 -m tools.inspect docs/spitball/<slug>  -o run.html

The page plots every candidate on the two measured axes and marks what the
kernel kept. It imports `tools.spitball.band` rather than reimplementing the
band rule in JavaScript: the page renders the kernel's own verdict, so it cannot
drift from it. Where the flags recorded in candidates.jsonl disagree with what
the kernel derives, the page says so -- that disagreement is the whole reason
this view exists.
"""
import argparse
import html
import json
import pathlib
import sys

from tools.spitball.band import Candidate, in_band, rank_band

VALUE_FLOOR = 0.6
FIELDS = ("text", "value_score", "fringe_proximity", "nearest_obvious_cluster")


def load(run_dir):
    run_dir = pathlib.Path(run_dir)
    m = json.loads((run_dir / "map.json").read_text())
    recs = [json.loads(l) for l in
            (run_dir / "candidates.jsonl").read_text().splitlines() if l.strip()]
    result = run_dir / "result.md"
    return m, recs, (result.read_text() if result.exists() else "")


def reconcile(recs):
    """Pair each record with the kernel's verdict, and note any disagreement."""
    rows = []
    for r in recs:
        # Construct explicitly: the record carries derived flags the dataclass
        # does not accept. This is the seam test_contract.py guards.
        c = Candidate(**{k: r[k] for k in FIELDS},
                      violates=tuple(r.get("violates", [])))
        kernel_band = in_band(c, VALUE_FLOOR)
        disagree = [
            k for k, recorded, derived in (
                ("obvious", r.get("obvious"), c.nearest_obvious_cluster is not None),
                ("in_band", r.get("in_band"), kernel_band),
            ) if recorded is not None and recorded != derived
        ]
        rows.append({"c": c, "in_band": kernel_band, "disagree": disagree})
    return rows


def _cut_reason(row):
    if row["c"].nearest_obvious_cluster is not None:
        return "obvious", f"in cluster '{row['c'].nearest_obvious_cluster}'"
    if row["c"].violates:
        return "violates", f"breaks {', '.join(row['c'].violates)}"
    if row["c"].value_score < VALUE_FLOOR:
        return "below-floor", f"value {row['c'].value_score:.2f} < {VALUE_FLOOR}"
    return "band", "kept"


def scatter(rows, top):
    """Inline SVG. x = fringe proximity, y = value. Floor drawn at 0.6."""
    W, H, P = 560, 400, 44
    px = lambda v: P + v * (W - 2 * P)
    py = lambda v: H - P - v * (H - 2 * P)
    rank_of = {c.text: i + 1 for i, c in enumerate(top)}

    parts = [f'<svg viewBox="0 0 {W} {H}" class="scatter" role="img" '
             f'aria-label="candidates by value and fringe proximity">']
    # grid + axes
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        parts.append(f'<line class="grid" x1="{px(0)}" y1="{py(t)}" '
                     f'x2="{px(1)}" y2="{py(t)}"/>')
        parts.append(f'<text class="tick" x="{P-8}" y="{py(t)+4}" '
                     f'text-anchor="end">{t:g}</text>')
        parts.append(f'<text class="tick" x="{px(t)}" y="{H-P+18}" '
                     f'text-anchor="middle">{t:g}</text>')
    parts.append(f'<line class="floor" x1="{px(0)}" y1="{py(VALUE_FLOOR)}" '
                 f'x2="{px(1)}" y2="{py(VALUE_FLOOR)}"/>')
    # Anchor left: candidates cluster at high fringe, so a right-anchored label
    # lands on top of them.
    parts.append(f'<text class="floor-label" x="{px(0)+4}" y="{py(VALUE_FLOOR)-7}">'
                 f'value floor {VALUE_FLOOR}</text>')
    parts.append(f'<text class="axis" x="{px(0.5)}" y="{H-6}" '
                 f'text-anchor="middle">fringe proximity →</text>')
    parts.append(f'<text class="axis" transform="translate(14,{py(0.5)}) rotate(-90)" '
                 f'text-anchor="middle">value →</text>')

    # Draw the returned set last so its badges sit above the rest of the cloud.
    for row in sorted(rows, key=lambda r: r["c"].text in rank_of):
        c, (kind, _) = row["c"], _cut_reason(row)
        x, y = px(c.fringe_proximity), py(c.value_score)
        n = rank_of.get(c.text)
        tip = (f'<title>{html.escape(c.text)} — value {c.value_score:.2f}, '
               f'fringe {c.fringe_proximity:.2f}</title>')
        if n is None:
            parts.append(f'<circle class="pt {kind}" cx="{x:.1f}" cy="{y:.1f}" '
                         f'r="4.5">{tip}</circle>')
            continue
        # Numbered badge instead of a text label: 5 labels in this region
        # overlap each other. The number keys into the "Returned" list below.
        parts.append(f'<g class="badge">'
                     f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9">{tip}</circle>'
                     f'<text x="{x:.1f}" y="{y+3.5:.1f}" text-anchor="middle">'
                     f'{n}</text></g>')
    parts.append('</svg>')
    return "\n".join(parts)


CSS = """
:root{--bg:#fff;--fg:#16181d;--mut:#6b7280;--line:#e5e7eb;--band:#2563eb;
--obv:#9ca3af;--low:#d97706;--warn:#b91c1c;--card:#f9fafb}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--fg:#e6e8ec;--mut:#9aa3af;
--line:#262b33;--band:#60a5fa;--obv:#4b5563;--low:#f59e0b;--warn:#f87171;--card:#161a21}}
*{box-sizing:border-box}
body{margin:0;padding:2rem 1.25rem;background:var(--bg);color:var(--fg);
font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",sans-serif;
max-width:62rem;margin-inline:auto}
h1{font-size:1.35rem;margin:0 0 .2rem} h2{font-size:1rem;margin:2rem 0 .6rem}
.sub{color:var(--mut);margin:0 0 1.5rem}
.stats{display:flex;flex-wrap:wrap;gap:.6rem;margin:0 0 1.5rem;padding:0;list-style:none}
.stats li{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:.5rem .8rem;font-size:.85rem}
.stats b{display:block;font-size:1.3rem;font-weight:600}
.scatter{width:100%;height:auto;background:var(--card);border:1px solid var(--line);
border-radius:10px}
.grid{stroke:var(--line)} .floor{stroke:var(--band);stroke-dasharray:5 4;opacity:.7}
.floor-label,.tick,.axis{fill:var(--mut);font-size:11px}
.pt{opacity:.85} .pt.band{fill:var(--band)} .pt.obvious{fill:var(--obv)}
.pt{fill:var(--low)} .pt.band{fill:var(--band)}
.badge circle{fill:var(--band);stroke:var(--bg);stroke-width:2}
.badge text{fill:var(--bg);font-size:11px;font-weight:700}
ol.top{counter-reset:none}
.wrap{overflow-x:auto} table{border-collapse:collapse;width:100%;font-size:.87rem}
th,td{text-align:left;padding:.4rem .7rem;border-bottom:1px solid var(--line);
white-space:nowrap} th{color:var(--mut);font-weight:500}
td.num{font-variant-numeric:tabular-nums}
.tag{font-size:.75rem;padding:.1rem .45rem;border-radius:99px;border:1px solid var(--line)}
.tag.band{color:var(--band)} .tag.obvious{color:var(--obv)} .tag.below-floor{color:var(--low)}
.alert{background:var(--card);border-left:3px solid var(--warn);color:var(--warn);
padding:.7rem 1rem;border-radius:6px;margin:1rem 0;font-size:.88rem}
ol.top{padding-left:1.2rem} ol.top li{margin:.3rem 0}
"""


def render(run_dir, m, rows, result_md):
    top = rank_band([r["c"] for r in rows], k=5, value_threshold=VALUE_FLOOR)
    band = [r for r in rows if r["in_band"]]
    obvious = [r for r in rows if r["c"].nearest_obvious_cluster is not None]
    low = [r for r in rows if _cut_reason(r)[0] == "below-floor"]
    bad = [r for r in rows if r["disagree"]]
    slug = pathlib.Path(run_dir).name

    alert = ""
    if bad:
        items = "; ".join(f"{html.escape(r['c'].text)} ({', '.join(r['disagree'])})"
                          for r in bad[:6])
        alert = (f'<p class="alert"><b>{len(bad)} record(s) disagree with the '
                 f'kernel.</b> The flags written into candidates.jsonl are not '
                 f'what band.py derives: {items}</p>')

    rowhtml = []
    for r in sorted(rows, key=lambda r: -r["c"].value_score):
        c, (kind, why) = r["c"], _cut_reason(r)
        rowhtml.append(
            f'<tr><td>{html.escape(c.text)}</td>'
            f'<td class="num">{c.value_score:.2f}</td>'
            f'<td class="num">{c.fringe_proximity:.2f}</td>'
            f'<td><span class="tag {kind}">{kind}</span></td>'
            f'<td>{html.escape(why)}</td></tr>')

    tops = "\n".join(f'<li><b>{html.escape(c.text)}</b> '
                     f'<span class="tick">value {c.value_score:.2f}, '
                     f'fringe {c.fringe_proximity:.2f}</span></li>' for c in top)
    clusters = ", ".join(html.escape(o["label"]) for o in m.get("obvious_clusters", []))
    preds = ", ".join(html.escape(p) for p in m.get("predicates", []))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>spitball run — {html.escape(slug)}</title><style>{CSS}</style></head><body>
<h1>{html.escape(slug)}</h1>
<p class="sub">{html.escape(m.get("value_criterion", ""))}</p>
{alert}
<ul class="stats">
<li><b>{len(rows)}</b>candidates</li><li><b>{len(band)}</b>in band</li>
<li><b>{len(top)}</b>returned</li><li><b>{len(obvious)}</b>cut: obvious</li>
<li><b>{len(low)}</b>cut: below floor</li>
</ul>
{scatter(rows, top)}
<h2>Returned</h2><ol class="top">{tops}</ol>
<h2>Map</h2>
<p class="sub"><b>Predicates:</b> {preds or "—"}<br>
<b>Obvious clusters:</b> {clusters or "—"}</p>
<h2>All candidates</h2>
<div class="wrap"><table><thead><tr><th>candidate</th><th>value</th>
<th>fringe</th><th>verdict</th><th>why</th></tr></thead>
<tbody>{"".join(rowhtml)}</tbody></table></div>
</body></html>"""


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tools.inspect")
    ap.add_argument("run_dir", help="docs/spitball/<slug>")
    ap.add_argument("-o", "--out", default="-", help="output HTML (default stdout)")
    args = ap.parse_args(argv)

    m, recs, result_md = load(args.run_dir)
    rows = reconcile(recs)
    page = render(args.run_dir, m, rows, result_md)
    if args.out == "-":
        sys.stdout.write(page)
    else:
        pathlib.Path(args.out).write_text(page)
        print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

"""CLI bridge: the skill pipes JSON in, gets JSON out. Keeps the model out of
the arithmetic. `python -m tools.spitball obvious|rank|fringe-check`.
"""
import argparse
import json
import sys
from dataclasses import asdict

from tools.spitball.band import rank_records
from tools.spitball.fringe import fringe_check
from tools.spitball.panel import obvious_clusters


def main(argv=None):
    parser = argparse.ArgumentParser(prog="spitball")
    sub = parser.add_subparsers(dest="cmd", required=True)

    po = sub.add_parser("obvious", help="panel JSON -> obvious clusters")
    po.add_argument("--threshold", type=float, default=0.25)

    pr = sub.add_parser("rank", help="candidates JSON -> ranked band")
    pr.add_argument("--k", type=int, default=5)
    pr.add_argument("--value-threshold", type=float, default=0.6)

    pf = sub.add_parser("fringe-check",
                        help="scored panel answers JSON -> fringe validation")
    pf.add_argument("--value-threshold", type=float, default=0.6)
    pf.add_argument("--far-floor", type=float, default=0.2)

    args = parser.parse_args(argv)
    data = json.load(sys.stdin)

    if args.cmd == "obvious":
        panelist_clusters = [p["clusters"] for p in data["panelists"]]
        clusters = obvious_clusters(
            panelist_clusters, n_panelists=len(panelist_clusters),
            threshold=args.threshold,
        )
        json.dump({"obvious_clusters": [asdict(o) for o in clusters]},
                  sys.stdout, indent=2)
    elif args.cmd == "rank":
        try:
            ranked = rank_records(data["candidates"], k=args.k,
                                  value_threshold=args.value_threshold)
        except KeyError as e:
            print(f"spitball rank: input missing {e}", file=sys.stderr)
            sys.exit(2)
        except ValueError as e:
            print(f"spitball rank: {e}", file=sys.stderr)
            sys.exit(2)
        json.dump({"ranked": ranked}, sys.stdout, indent=2)
    elif args.cmd == "fringe-check":
        report = fringe_check(
            data["predicates"], data["answers"], data.get("clusters", []),
            value_threshold=args.value_threshold, far_floor=args.far_floor,
        )
        json.dump(asdict(report), sys.stdout, indent=2)


if __name__ == "__main__":
    main()

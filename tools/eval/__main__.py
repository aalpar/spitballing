"""`python3 -m tools.eval validate|audit|rejudge|run ...`"""
import argparse
import json
import pathlib
import subprocess
import sys

from tools.eval.audit import audit_transcript, summarize
from tools.eval.rejudge import converge_bullet, rejudge
from tools.eval.run import run as run_once
from tools.eval.validate import validate_run


def _matched_inputs(run):
    """(request, CONVERGE bullet) for the SKILL.md this run was staged with."""
    manifest = dict(l.split(":", 1) for l in (run / "manifest.txt").read_text().splitlines() if ":" in l)
    manifest = {k.strip(): v.strip() for k, v in manifest.items()}
    variant = manifest["skill_variant"]
    skill = (pathlib.Path(variant).read_text() if variant != "-" else
             subprocess.run(["git", "show", f"{manifest['commit']}:skills/spitballing/SKILL.md"],
                            capture_output=True, text=True, check=True).stdout)
    request = json.loads((run / "brief.json").read_text())["request"]
    return request, converge_bullet(skill)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="eval")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pv = sub.add_parser("validate", help="check run artifacts")
    pv.add_argument("runs", nargs="+", type=pathlib.Path)
    pa = sub.add_parser("audit", help="transcript metrics -> <run>/metrics.json")
    pa.add_argument("--summary", action="store_true", help="print a table instead")
    pa.add_argument("runs", nargs="+", type=pathlib.Path)
    pr = sub.add_parser("run", help="one headless eval run")
    pr.add_argument("--brief", required=True)
    pr.add_argument("--prompt", required=True, choices=("slash", "natural", "pressure", "skip"))
    pr.add_argument("--skill-variant", default="")
    pr.add_argument("--desc-variant", default="")
    pr.add_argument("--model", default="opus")
    pr.add_argument("--permission-mode", default="bypassPermissions")
    pj = sub.add_parser("rejudge", help="fresh-context obviousness judge -> rejudge.json")
    pj.add_argument("runs", nargs="+", type=pathlib.Path)
    pj.add_argument("--model", default="opus")
    pj.add_argument("--matched", action="store_true",
                    help="give the judge the run's own CONVERGE bullet and map.json")
    args = parser.parse_args(argv)

    if args.cmd == "validate":
        bad = False
        for run in args.runs:
            problems = validate_run(run)
            print(f"{run}: {'ok' if not problems else f'{len(problems)} problem(s)'}")
            for p in problems:
                print(f"  {p}")
            bad = bad or bool(problems)
        sys.exit(1 if bad else 0)
    elif args.cmd == "audit":
        if args.summary:
            print(summarize(args.runs))
            return
        for run in args.runs:
            m = audit_transcript(run / "transcript.jsonl")
            (run / "metrics.json").write_text(json.dumps(m, indent=2) + "\n")
            print(f"{run}: {json.dumps(m)}")
    elif args.cmd == "rejudge":
        for run in args.runs:
            matched = _matched_inputs(run) if args.matched else None
            for topic in sorted(p for p in (run / "docs" / "spitball").glob("*") if p.is_dir()):
                r = rejudge(topic, args.model, matched)
                print(f"{run.name}: conductor {r['conductor_obvious']}/{r['total']} obvious, "
                      f"judge {r['judge_obvious']}/{r['total']} "
                      f"(conductor-only {r['conductor_only']}, judge-only {r['judge_only']}), unjudged {r['unjudged']}, "
                      f"ranked judged obvious {r['ranked_judge_obvious']}")
    elif args.cmd == "run":
        print(run_once(args.brief, args.prompt, args.skill_variant or None,
                       args.desc_variant or None, args.model, args.permission_mode))


if __name__ == "__main__":
    main()

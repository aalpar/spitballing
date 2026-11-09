"""Transcript audit for headless eval runs (`claude -p --output-format
stream-json --verbose`). Counts top-level messages only: subagent-internal ones
carry a non-null `parent_tool_use_id`. A slash-command prompt's skill injection
is not recorded in the stream, so `skill_invoked` sees only `Skill` tool_uses."""
import json
import re

from tools.eval.validate import validate_run

KERNEL_CMDS = ("obvious", "rank", "fringe-check")
_KERNEL = re.compile(r"tools\.spitball\s+(obvious|rank|fringe-check)\b")
# Flags only: `band` and `obvious` are ordinary words; read each flagged prompt.
_LEAK = re.compile(r"\b(spitball\w*|band|obvious|fringe)\b", re.IGNORECASE)
_RESULT_REDIRECT = re.compile(r">\s*\S*result\.md\b")


def _leaks(prompt):
    return bool(_LEAK.search(prompt)) or "SKILL" in prompt


def _top_level(path):
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            o = json.loads(line)
        except ValueError:      # a run killed mid-write leaves a partial line
            continue
        if o.get("parent_tool_use_id") is None and isinstance(o.get("message"), dict):
            yield o


def _tool_uses(o):
    content = o["message"].get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content if b.get("type") == "tool_use"]


def audit_transcript(path, output_kind=None):
    if output_kind is None and (path.parent / "brief.json").exists():
        output_kind = json.loads((path.parent / "brief.json").read_text())["output_kind"]
    m = {"skill_invoked": False, "panel_spawns": 0,
         "panel_prompts_with_output_kind": 0, "panel_prompt_leaks": 0,
         "kernel_calls": {c: 0 for c in KERNEL_CMDS},
         "brainstorming_invoked": False, "result_written": False}
    for o in _top_level(path):
        for b in _tool_uses(o):
            name, inp = b.get("name"), b.get("input") or {}
            if name == "Skill":
                skill = str(inp.get("skill", ""))
                m["skill_invoked"] |= "spitballing" in skill
                m["brainstorming_invoked"] |= "brainstorming" in skill
            elif name in ("Agent", "Task"):
                prompt = str(inp.get("prompt", ""))
                if "instinctive answers" in prompt:
                    m["panel_spawns"] += 1
                    if output_kind and output_kind in prompt:
                        m["panel_prompts_with_output_kind"] += 1
                    if _leaks(prompt):
                        m["panel_prompt_leaks"] += 1
            elif name == "Bash":
                command = str(inp.get("command", ""))
                for cmd in _KERNEL.findall(command):
                    m["kernel_calls"][cmd] += 1
                m["result_written"] |= bool(_RESULT_REDIRECT.search(command))
            elif name in ("Write", "Edit"):
                m["result_written"] |= str(inp.get("file_path", "")).endswith("/result.md")
    complete = m["kernel_calls"]["rank"] > 0 and m.pop("result_written")
    m["status"] = "complete" if complete else "incomplete"
    return m


_COLS = ("skill", "spawns", "out_kind", "leaks",
         "obvious", "rank", "fringe", "brainstorm", "phantom", "problems")


def _claims_panel(topic):
    """map.json reports a measured panel: `measured` true or any panel count."""
    try:
        m = json.loads((topic / "map.json").read_text())
    except (OSError, ValueError):
        return False
    return isinstance(m, dict) and (m.get("measured") is True or any(
        isinstance(c, dict) and ("panelist_count" in c or "frac" in c)
        for c in m.get("obvious_clusters", [])))


def _row(run_dir):
    m = audit_transcript(run_dir / "transcript.jsonl")
    topics = sorted(p for p in (run_dir / "docs" / "spitball").glob("*") if p.is_dir())
    problems = sum(len(validate_run(t)) for t in topics) if topics else None
    k = m["kernel_calls"]
    return {"complete": m["status"] == "complete", "skill": m["skill_invoked"],
            "spawns": m["panel_spawns"], "out_kind": m["panel_prompts_with_output_kind"],
            "leaks": m["panel_prompt_leaks"], "obvious": k["obvious"], "rank": k["rank"],
            "fringe": k["fringe-check"], "brainstorm": m["brainstorming_invoked"],
            "phantom": m["panel_spawns"] == 0 and any(_claims_panel(t) for t in topics),
            "problems": problems}


def _fmt(v):
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def _table(rows):
    out = ["| run | " + " | ".join(_COLS) + " |",
           "|---" * (len(_COLS) + 1) + "|"]
    out += [f"| {name} | " + " | ".join(_fmt(r[c]) for c in _COLS) + " |"
            for name, r in rows]
    return out


def summarize(run_dirs):
    """Complete runs get the table and the mean. Incomplete runs (stopped
    before `rank` or `result.md`) are listed apart: their zeros are not
    compliance data, so they stay out of the mean."""
    rows = [(d.name, _row(d)) for d in run_dirs]
    done = [x for x in rows if x[1]["complete"]]
    stopped = [x for x in rows if not x[1]["complete"]]
    out = [f"{len(done)}/{len(rows)} complete", ""] + _table(done)
    means = []
    for c in _COLS:
        vals = [float(r[c]) for _, r in done if r[c] is not None]
        means.append(f"{sum(vals) / len(vals):.2f}" if vals else "n/a")
    out.append("| mean | " + " | ".join(means) + " |")
    if stopped:
        out += ["", "Incomplete (not in the mean):", ""] + _table(stopped)
    return "\n".join(out)

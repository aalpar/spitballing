"""Re-judge obviousness with a fresh context: the conductor that wrote the map
also judged its own candidates against it. A fresh `claude -p` sees only the
obvious clusters and the candidate texts. Writes <run>/rejudge.json."""
import json
import re
import subprocess
import tempfile

from tools.spitball.band import rank_records

PROMPT = """Below are clusters of answers a panel gave most often for a request, then a list of candidate answers.
For each candidate, name the cluster it falls into (it works for the same reason as the cluster's members), or null if it falls into none.
Reply with only a JSON array, one object per candidate, in order: [{{"text": "...", "nearest_obvious_cluster": "<label>" or null}}]

Clusters:
{clusters}

Candidates:
{candidates}"""


MATCHED_PROMPT = """You are judging candidate answers to this request: {request}

map.json:
{map_json}

For each candidate, supply `nearest_obvious_cluster`, as instructed:
{instruction}

Reply with only a JSON array, one object per candidate, in order: [{{"text": "...", "nearest_obvious_cluster": ...}}]

Candidates:
{candidates}"""


def converge_bullet(skill_text):
    """The SKILL.md CONVERGE bullet for `nearest_obvious_cluster`, verbatim."""
    m = re.search(r"^- `nearest_obvious_cluster`.*?(?=\n- `|\n\n)", skill_text, re.M | re.S)
    if not m:
        raise ValueError("no nearest_obvious_cluster bullet in SKILL.md")
    return m.group(0)


def build_matched_prompt(request, map_text, instruction, texts):
    """Judge with the conductor's own inputs and instruction, minus its history."""
    return MATCHED_PROMPT.format(request=request, map_json=map_text.strip(),
                                 instruction=instruction,
                                 candidates="\n".join(f"- {t}" for t in texts))


def build_prompt(map_, texts):
    clusters = "\n".join(f"- {c['label']}: {', '.join(c['member_ideas'])}"
                         for c in map_["obvious_clusters"])
    return PROMPT.format(clusters=clusters, candidates="\n".join(f"- {t}" for t in texts))


def parse_reply(reply):
    m = re.search(r"\[.*\]", reply, re.DOTALL)
    if not m:
        raise ValueError("no JSON array in judge reply")
    return json.loads(m.group(0))


def compare(records, judgments, labels):
    judged = {j["text"]: j.get("nearest_obvious_cluster") for j in judgments}
    judge_obvious = {t for t, c in judged.items() if c in labels}
    conductor_obvious = {r["text"] for r in records if r["nearest_obvious_cluster"] is not None}
    ranked = [r["text"] for r in rank_records(records, k=5)]
    return {"total": len(records),
            "conductor_obvious": sum(r["nearest_obvious_cluster"] is not None for r in records),
            "judge_obvious": sum(r["text"] in judge_obvious for r in records),
            "conductor_only": len(conductor_obvious - judge_obvious),
            "judge_only": len(judge_obvious - conductor_obvious),
            "unjudged": sum(r["text"] not in judged for r in records),
            "ranked": ranked,
            "ranked_judge_obvious": [t for t in ranked if t in judge_obvious]}


def rejudge(topic_dir, model="opus", matched=None):
    """matched: (request, CONVERGE bullet) -> instruction-matched judge, rejudge-matched.json."""
    map_text = (topic_dir / "map.json").read_text()
    map_ = json.loads(map_text)
    records = [json.loads(l) for l in (topic_dir / "candidates.jsonl").read_text().splitlines() if l.strip()]
    texts = [r["text"] for r in records]
    prompt = build_matched_prompt(matched[0], map_text, matched[1], texts) if matched else build_prompt(map_, texts)
    with tempfile.TemporaryDirectory() as cwd:
        out = subprocess.run(["claude", "--model", model, "-p", prompt, "--output-format", "json"],
                             cwd=cwd, capture_output=True, text=True, check=True).stdout
    judgments = parse_reply(json.loads(out)["result"])
    labels = {c["label"] for c in map_["obvious_clusters"]}
    report = dict(compare(records, judgments, labels), judgments=judgments)
    (topic_dir / ("rejudge-matched.json" if matched else "rejudge.json")).write_text(json.dumps(report, indent=2) + "\n")
    return report

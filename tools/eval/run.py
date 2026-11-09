"""One headless eval run: stage the plugin (optionally with a SKILL.md or
description variant), run `claude -p` in a sandbox outside the repo, archive
the transcript and artifacts to eval/runs/NNNN/."""
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNS = ROOT / "eval" / "runs"
TIMEOUT_S = 3600


def _stage(dest, skill_variant, desc_variant):
    for part in (".claude-plugin", "skills", "tools"):
        shutil.copytree(ROOT / part, dest / part,
                        ignore=shutil.ignore_patterns("__pycache__", "tests"))
    skill = dest / "skills" / "spitballing" / "SKILL.md"
    if skill_variant:
        shutil.copy(skill_variant, skill)
    if desc_variant:
        desc = next(l for l in pathlib.Path(desc_variant).read_text().splitlines()
                    if l.startswith("description:"))
        text = re.sub(r"^description:.*$", lambda _: desc, skill.read_text(),
                      count=1, flags=re.MULTILINE)
        skill.write_text(text)


def _next_run_dir():
    # Retry on collision: parallel `make eval` invocations race for a number.
    RUNS.mkdir(parents=True, exist_ok=True)
    while True:
        nums = [int(p.name) for p in RUNS.iterdir() if p.name.isdigit()]
        d = RUNS / f"{max(nums, default=0) + 1:04d}"
        try:
            d.mkdir()
            return d
        except FileExistsError:
            continue


def run(brief, prompt_kind, skill_variant=None, desc_variant=None, model="opus",
        permission_mode="bypassPermissions"):
    brief = pathlib.Path(brief)
    b = json.loads(brief.read_text())
    prompt = (ROOT / "eval" / "prompts" / f"{prompt_kind}.txt").read_text().strip()
    prompt = prompt.replace("<REQUEST>", b["request"]).replace("<BRIEF>", json.dumps(b))
    out = _next_run_dir()
    shutil.copy(brief, out / "brief.json")
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "skills", "tools"],
                           cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out / "manifest.txt").write_text(
        f"date:          {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ}\n"
        f"commit:        {rev}{' (dirty)' if dirty else ''}\n"
        f"brief:         {brief}\nprompt:        {prompt_kind}\n"
        f"skill_variant: {skill_variant or '-'}\ndesc_variant:  {desc_variant or '-'}\n"
        f"model:         {model}\npermissions:   {permission_mode}\n")
    with tempfile.TemporaryDirectory() as stage, tempfile.TemporaryDirectory() as sandbox:
        stage = pathlib.Path(stage)
        _stage(stage, skill_variant, desc_variant)
        (out / "manifest.txt").open("a").write(f"stage:         {stage}\n")
        cmd = ["claude", "--plugin-dir", str(stage), "--permission-mode",
               permission_mode, "--model", model, "-p", prompt,
               "--output-format", "stream-json", "--verbose"]
        with open(out / "transcript.jsonl", "w") as t, open(out / "stderr.txt", "w") as e:
            try:
                subprocess.run(cmd, cwd=sandbox, stdout=t, stderr=e, timeout=TIMEOUT_S)
            except subprocess.TimeoutExpired:
                e.write(f"timeout after {TIMEOUT_S}s\n")
        produced = pathlib.Path(sandbox) / "docs" / "spitball"
        if produced.is_dir():
            shutil.copytree(produced, out / "docs" / "spitball")
    return out

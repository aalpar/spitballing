#!/usr/bin/env python3
"""Post blind HIT assignments to Amazon Mechanical Turk.

Takes Assignment objects produced by build_hits.build_assignments and submits
them as MTurk HITs via the boto3 MTurk client.  Supports a free SANDBOX
endpoint for safe testing and the live PROD endpoint for real studies.

Credentials are resolved entirely by boto3's default chain (environment
variables, ~/.aws/credentials, IAM role, etc.).  No keys are ever hard-coded
here.

A manifest.json is written alongside the HITs mapping each created HIT-ID to
the idea-ids it contained, so the later collect step can reconcile ratings.

Public API
----------
client(env='sandbox') -> boto3 MTurk client
    Construct an MTurk client pointed at the sandbox or prod endpoint.
    boto3 is imported lazily inside this function; ImportError is raised with
    a pip-install hint when boto3 is not available.

default_qualifications(custom_qual_id=None) -> list[dict]
    Return a sensible QualificationRequirements list (>=95 % approval rate,
    >=100 approved HITs).  Appends a custom qualification requirement if
    custom_qual_id is provided (useful for a Phase-2 fidelity panel).

create_batch(client, assignments, dimensions, reward, lifetime,
             assignment_duration, max_assignments, qualifications) -> list[dict]
    Post one HIT per Assignment; return manifest rows [{hit_id, idea_ids}].

write_manifest(manifest, path) -> None
    Serialize manifest to JSON at path.
"""
import json
import os

from tools.ablation.build_hits import Assignment, render_question_xml

# ---------------------------------------------------------------------------
# Endpoint constants
# ---------------------------------------------------------------------------

SANDBOX_URL = "https://mturk-requester-sandbox.us-east-1.amazonaws.com"
PROD_URL = "https://mturk-requester.us-east-1.amazonaws.com"


# ---------------------------------------------------------------------------
# boto3 client (lazy import)
# ---------------------------------------------------------------------------

def client(env: str = "sandbox"):
    """Return a boto3 MTurk client for *env* ('sandbox' or 'prod').

    boto3 is imported lazily so the module remains importable when boto3 is
    not installed.  Credentials are resolved by boto3's standard chain —
    never hard-coded.

    Parameters
    ----------
    env:
        'sandbox'  — uses the free MTurk sandbox (default, safe for testing).
        'prod'     — uses the live MTurk endpoint (real money, real workers).
    """
    try:
        import boto3  # noqa: PLC0415  (lazy import by design)
    except ImportError as exc:
        raise ImportError(
            "boto3 is required to talk to MTurk.  Install it with:\n"
            "    pip install boto3"
        ) from exc

    endpoint_url = SANDBOX_URL if env == "sandbox" else PROD_URL
    return boto3.client(
        "mturk",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        # Credentials come from the environment / ~/.aws — NOT from this code.
    )


# ---------------------------------------------------------------------------
# Qualification helpers
# ---------------------------------------------------------------------------

def default_qualifications(custom_qual_id: str | None = None) -> list[dict]:
    """Return a sensible MTurk QualificationRequirements list.

    Built-in requirements
    ---------------------
    - Worker_PercentAssignmentsApproved >= 95  (approval rate)
    - Worker_NumberHITsApproved >= 100         (experience floor)

    Parameters
    ----------
    custom_qual_id:
        Optional MTurk QualificationTypeId (string) to append — useful for a
        Phase-2 fidelity panel or any pre-screened worker pool.  Workers must
        possess this qualification (Comparator='Exists') to see the HIT.
    """
    quals = [
        {
            "QualificationTypeId": "000000000000000000L0",  # PercentAssignmentsApproved
            "Comparator": "GreaterThanOrEqualTo",
            "IntegerValues": [95],
            "RequiredToPreview": True,
        },
        {
            "QualificationTypeId": "00000000000000000040",  # NumberHITsApproved
            "Comparator": "GreaterThanOrEqualTo",
            "IntegerValues": [100],
            "RequiredToPreview": True,
        },
    ]
    if custom_qual_id is not None:
        quals.append(
            {
                "QualificationTypeId": custom_qual_id,
                "Comparator": "Exists",
                "RequiredToPreview": True,
            }
        )
    return quals


# ---------------------------------------------------------------------------
# Batch posting
# ---------------------------------------------------------------------------

def create_batch(
    mturk_client,
    assignments: list[Assignment],
    dimensions: list[str],
    reward: float = 0.50,
    lifetime: int = 604_800,           # 7 days in seconds
    assignment_duration: int = 3_600,  # 1 hour in seconds
    max_assignments: int = 1,
    qualifications: list[dict] | None = None,
) -> list[dict]:
    """Post one HIT per Assignment to MTurk and return a manifest.

    Parameters
    ----------
    mturk_client:
        An active boto3 MTurk client (from :func:`client`).
    assignments:
        List of Assignment objects from build_hits.build_assignments.
    dimensions:
        Rating dimensions forwarded to render_question_xml (e.g.
        ['originality', 'appropriateness']).
    reward:
        Reward per completed assignment in USD (default $0.50).
    lifetime:
        Seconds the HIT remains available on MTurk (default 7 days).
    assignment_duration:
        Seconds a worker has to complete the HIT once accepted (default 1 h).
    max_assignments:
        Fallback workers-per-HIT used only if an Assignment does not carry its
        own ``max_assignments`` (it normally does — set to `raters`).
    qualifications:
        QualificationRequirements list.  Defaults to default_qualifications().

    Returns
    -------
    list[dict]
        One entry per posted HIT: {hit_id, idea_ids}.  Pass to
        write_manifest() to persist.
    """
    if qualifications is None:
        qualifications = default_qualifications()

    manifest = []
    for asgn in assignments:
        question_xml = render_question_xml(asgn, dimensions)

        # Extract real idea ids (skip attention-check items).
        idea_ids = [
            item["idea_id"]
            for item in asgn.items
            if not item.get("is_attention_check")
        ]

        response = mturk_client.create_hit(
            Title="Rate the originality and appropriateness of ideas",
            Description=(
                "You will read a set of short idea descriptions and "
                "rate each on several dimensions using a 1–7 scale."
            ),
            Keywords="ideas, rating, creativity, product, evaluation",
            Reward=f"{reward:.2f}",
            LifetimeInSeconds=lifetime,
            AssignmentDurationInSeconds=assignment_duration,
            MaxAssignments=getattr(asgn, "max_assignments", max_assignments),
            Question=question_xml,
            QualificationRequirements=qualifications,
        )
        hit_id = response["HIT"]["HITId"]
        manifest.append({"hit_id": hit_id, "idea_ids": idea_ids})

    return manifest


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------

def write_manifest(manifest: list[dict], path: str) -> None:
    """Write *manifest* to *path* as pretty-printed JSON."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys
    import tempfile

    from tools.ablation.build_hits import (
        build_assignments,
        load_rated_set,
    )

    parser = argparse.ArgumentParser(
        description=(
            "Post blind CAT HIT assignments to MTurk. "
            "Use --dry-run to preview payloads without touching the API."
        )
    )
    parser.add_argument(
        "input",
        help="JSONL file: one {id,engine,source,text} per line",
    )
    parser.add_argument(
        "--env",
        choices=["sandbox", "prod"],
        default="sandbox",
        help="MTurk endpoint (default: sandbox)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print HIT payloads and exit — does NOT call MTurk and does NOT "
            "require boto3."
        ),
    )
    parser.add_argument(
        "--raters",
        type=int,
        default=5,
        help="Workers per HIT / ratings per idea — MaxAssignments (default: 5)",
    )
    parser.add_argument(
        "--ideas-per-hit",
        type=int,
        default=12,
        help="Maximum ideas per HIT (default: 12)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for assignment shuffling (default: 42)",
    )
    parser.add_argument(
        "--dimensions",
        nargs="+",
        default=["originality", "appropriateness"],
        metavar="DIM",
        help="Rating dimensions (default: originality appropriateness — Phase-1 pre-reg)",
    )
    parser.add_argument(
        "--reward",
        type=float,
        default=0.50,
        help="Reward per HIT in USD (default: 0.50)",
    )
    parser.add_argument(
        "--lifetime",
        type=int,
        default=604_800,
        help="HIT lifetime in seconds (default: 604800 = 7 days)",
    )
    parser.add_argument(
        "--assignment-duration",
        type=int,
        default=3_600,
        help="Seconds to complete a HIT once accepted (default: 3600 = 1 h)",
    )
    parser.add_argument(
        "--custom-qual-id",
        default=None,
        metavar="QUAL_ID",
        help="MTurk QualificationTypeId to append to default requirements",
    )
    parser.add_argument(
        "--manifest-out",
        default="manifest.json",
        metavar="PATH",
        help="Where to write manifest.json (default: manifest.json)",
    )
    args = parser.parse_args()

    ideas = load_rated_set(args.input)
    assignments = build_assignments(
        ideas=ideas,
        raters=args.raters,
        attention_items=[],
        rng_seed=args.seed,
        ideas_per_hit=args.ideas_per_hit,
    )

    if args.dry_run:
        for asgn in assignments:
            xml_payload = render_question_xml(asgn, args.dimensions)
            idea_ids = [
                item["idea_id"]
                for item in asgn.items
                if not item.get("is_attention_check")
            ]
            print(f"--- HIT {asgn.hit_index} ({len(idea_ids)} ideas) ---")
            print(f"  idea_ids : {idea_ids}")
            print(f"  Reward   : ${args.reward:.2f}")
            print(f"  Lifetime : {args.lifetime}s")
            print(f"  Duration : {args.assignment_duration}s")
            print(f"  MaxAsgn  : {asgn.max_assignments}")
            print(f"  Question (first 400 chars):")
            print(f"    {xml_payload[:400]}")
            print()
        n_ideas = sum(1 for a in assignments for it in a.items
                      if not it.get("is_attention_check"))
        print(f"Dry run complete — {len(assignments)} HIT(s), {n_ideas} ideas, "
              f"x{args.raters} workers each = {len(assignments) * args.raters} assignments.",
              file=sys.stderr)
        sys.exit(0)

    # Live path — requires boto3 and valid AWS credentials.
    mturk = client(args.env)
    qualifications = default_qualifications(custom_qual_id=args.custom_qual_id)
    manifest = create_batch(
        mturk_client=mturk,
        assignments=assignments,
        dimensions=args.dimensions,
        reward=args.reward,
        lifetime=args.lifetime,
        assignment_duration=args.assignment_duration,
        qualifications=qualifications,
    )
    write_manifest(manifest, args.manifest_out)
    print(f"Posted {len(manifest)} HIT(s). Manifest written to {args.manifest_out}", file=sys.stderr)

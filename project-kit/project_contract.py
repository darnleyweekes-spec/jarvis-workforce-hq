"""Read-only project onboarding contract for ALPHA missions.

This contract scopes a plan. It does not connect any Site, provider, or action adapter.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alpha-runtime"))
from alpha_runtime import MissionRequest


PROHIBITED = [
    "send external messages without review", "publish or deploy without approval",
    "charge or change payments without approval", "modify customer records without approval",
    "perform intrusive security testing without explicit scope",
]
REQUIRED = ("id", "name", "stage", "customer", "problem", "why_now", "workflow",
            "baseline_metric", "target_metric", "proof_required", "approval_boundary")
STAGES = {"concept", "demo", "pilot", "live"}


def validate(profile: dict) -> list[str]:
    errors = []
    for field in REQUIRED:
        if not isinstance(profile.get(field), str) or not profile[field].strip():
            errors.append(f"{field} is required")
    if profile.get("stage") not in STAGES:
        errors.append("stage must be concept, demo, pilot, or live")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", profile.get("id", "")):
        errors.append("id must be a lowercase slug")
    if profile.get("connected_tools") != []:
        errors.append("connected_tools must be [] until a reviewed integration is implemented")
    if profile.get("automatic_external_actions") is not False:
        errors.append("automatic_external_actions must be false")
    return errors


def mission_from_profile(profile: dict, objective: str, mission_id: str | None = None) -> MissionRequest:
    errors = validate(profile)
    if errors:
        raise ValueError("invalid project contract: " + "; ".join(errors))
    if not objective.strip():
        raise ValueError("objective is required")
    kwargs = {"mission_id": mission_id} if mission_id else {}
    return MissionRequest(
        objective=objective,
        success_criteria=[profile["proof_required"], profile["target_metric"]],
        constraints=[f"Project: {profile['name']}; stage: {profile['stage']}",
                     f"Customer: {profile['customer']}",
                     f"Problem: {profile['problem']}",
                     f"Baseline to measure: {profile['baseline_metric']}",
                     f"Approval boundary: {profile['approval_boundary']}"],
        allowed_tools=[], prohibited_actions=PROHIBITED.copy(), approval_required=True,
        **kwargs,
    )


def new_concept(slug: str, name: str) -> dict:
    profile = {
        "id": slug, "name": name, "stage": "concept", "customer": "",
        "problem": "", "why_now": "", "workflow": "", "baseline_metric": "",
        "target_metric": "", "proof_required": "", "approval_boundary": "",
        "connected_tools": [], "automatic_external_actions": False,
    }
    if not re.fullmatch(r"[a-z][a-z0-9-]*", slug) or not name.strip():
        raise ValueError("provide a lowercase slug and nonempty name")
    return profile


def main() -> int:
    parser = argparse.ArgumentParser(description="ALPHA project contracts (local planning only)")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("path", type=Path)
    create = sub.add_parser("new")
    create.add_argument("slug")
    create.add_argument("name")
    args = parser.parse_args()
    if args.command == "new":
        print(json.dumps(new_concept(args.slug, args.name), indent=2))
        return 0
    data = json.loads(args.path.read_text())
    profiles = data["projects"] if isinstance(data, dict) and "projects" in data else [data]
    errors = []
    seen = set()
    for profile in profiles:
        errors.extend(f"{profile.get('id', '?')}: {error}" for error in validate(profile))
        if profile.get("id") in seen:
            errors.append(f"duplicate project id: {profile['id']}")
        seen.add(profile.get("id"))
    print("OK: " + str(len(profiles)) + " project contracts" if not errors else "\n".join(errors))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())

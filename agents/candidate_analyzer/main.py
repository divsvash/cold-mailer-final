"""CLI: regenerate profile.json from source files."""
from __future__ import annotations
from security import private_write
import argparse
import json
import pathlib
import sys
from agents.candidate_analyzer.extractor import extract_profile

from config import get_settings, resolve_path

def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Build candidate profile.json from source files")
    parser.add_argument("--resume",       default=str(settings.RESUME_PATH))
    parser.add_argument("--projects",     default=str(settings.PROJECTS_PATH))
    parser.add_argument("--achievements", default=str(settings.ACHIEVEMENTS_PATH))
    parser.add_argument("--output",       default=str(settings.PROFILE_PATH))
    args = parser.parse_args()

    for p, label in [(args.resume, "resume"), (args.projects, "projects"), (args.achievements, "achievements")]:
        if not resolve_path(p).exists():
            print(f"ERROR: {label} file not found: {p}", file=sys.stderr)
            sys.exit(1)

    print(f"Reading {args.resume}, {args.projects}, {args.achievements}...")
    try:
        profile = extract_profile(args.resume, args.projects, args.achievements)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    private_write(resolve_path(args.output), json.dumps(profile.model_dump(mode="json"), indent=2))
    print(f"Profile written to {args.output}")
    print(f"  Skills: {len(profile.skills)}, Projects: {len(profile.projects)}, Experience: {len(profile.experience)}")


if __name__ == "__main__":
    main()

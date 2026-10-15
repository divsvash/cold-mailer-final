"""CLI: score a candidate profile against job requirements."""
from __future__ import annotations
import argparse, json, pathlib, sys
from agents.recruiter_simulator.schemas import CandidateProfile, JobRequirements
from agents.recruiter_simulator.scoring import assess

from config import get_settings, resolve_path

def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Score candidate against a job")
    parser.add_argument("--profile", default=str(settings.PROFILE_PATH))
    parser.add_argument("--job",     required=True)
    parser.add_argument("--output",  default=None)
    args = parser.parse_args()

    for p, label in [(args.profile, "profile"), (args.job, "job requirements")]:
        if not resolve_path(p).exists():
            print(f"ERROR: {label} file not found: {p}", file=sys.stderr); sys.exit(1)

    candidate = CandidateProfile.model_validate(json.loads(resolve_path(args.profile).read_text()))
    job       = JobRequirements.model_validate(json.loads(resolve_path(args.job).read_text()))
    result    = assess(candidate, job)
    out       = json.dumps(result.model_dump(mode="json"), indent=2)

    if args.output:
        resolve_path(args.output).parent.mkdir(parents=True, exist_ok=True)
        resolve_path(args.output).write_text(out)
        print(f"Assessment written to {args.output}")
    else:
        print(out)


if __name__ == "__main__":
    main()

"""CLI: score a candidate profile against job requirements."""
from __future__ import annotations
import argparse, json, pathlib, sys
from agents.recruiter_simulator.schemas import CandidateProfile, JobRequirements
from agents.recruiter_simulator.scoring import assess


def main() -> None:
    parser = argparse.ArgumentParser(description="Score candidate against a job")
    parser.add_argument("--profile", default="memory/profile.json")
    parser.add_argument("--job",     required=True)
    parser.add_argument("--output",  default=None)
    args = parser.parse_args()

    for p, label in [(args.profile, "profile"), (args.job, "job requirements")]:
        if not pathlib.Path(p).exists():
            print(f"ERROR: {label} file not found: {p}", file=sys.stderr); sys.exit(1)

    candidate = CandidateProfile.model_validate(json.loads(pathlib.Path(args.profile).read_text()))
    job       = JobRequirements.model_validate(json.loads(pathlib.Path(args.job).read_text()))
    result    = assess(candidate, job)
    out       = json.dumps(result.model_dump(mode="json"), indent=2)

    if args.output:
        pathlib.Path(args.output).write_text(out)
        print(f"Assessment written to {args.output}")
    else:
        print(out)


if __name__ == "__main__":
    main()

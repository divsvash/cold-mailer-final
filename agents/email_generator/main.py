"""CLI: generate ranked email variants for a candidate/job/company."""
from __future__ import annotations
import argparse, json, pathlib, sys
from agents.email_generator.engine import EmailGenerationEngine
from agents.email_generator.schemas import CandidateProfile, CompanyInfo, JobAnalysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ranked outreach email variants")
    parser.add_argument("--profile",     default="memory/profile.json")
    parser.add_argument("--job",         required=True)
    parser.add_argument("--company",     required=True)
    parser.add_argument("--personality", default="prompts/personality.md")
    parser.add_argument("--output",      default=None)
    args = parser.parse_args()

    for p, label in [
        (args.profile,     "profile"),
        (args.job,         "job analysis"),
        (args.company,     "company info"),
        (args.personality, "personality prompt"),
    ]:
        if not pathlib.Path(p).exists():
            print(f"ERROR: {label} not found: {p}", file=sys.stderr); sys.exit(1)

    candidate   = CandidateProfile.model_validate(json.loads(pathlib.Path(args.profile).read_text()))
    job         = JobAnalysis.model_validate(json.loads(pathlib.Path(args.job).read_text()))
    company     = CompanyInfo.model_validate(json.loads(pathlib.Path(args.company).read_text()))
    personality = pathlib.Path(args.personality).read_text()

    result = EmailGenerationEngine().generate(candidate, job, company, personality)
    output = {
        "best": {
            "variant_type":        result.best_variant.variant_type.value,
            "subject":             result.best_variant.subject,
            "body":                result.best_variant.body,
            "word_count":          result.best_variant.word_count,
            "expected_reply_rate": result.best_expected_reply_rate,
        },
        "all_variants": [
            {
                "variant_type":        v.variant_type.value,
                "subject":             v.subject,
                "body":                v.body,
                "word_count":          v.word_count,
                "expected_reply_rate": next((r.expected_reply_rate for r in result.rankings if r.variant_type == v.variant_type), None),
                "reasoning":           next((r.reasoning for r in result.rankings if r.variant_type == v.variant_type), None),
            }
            for v in result.variants
        ],
    }
    out_json = json.dumps(output, indent=2)
    if args.output:
        pathlib.Path(args.output).write_text(out_json); print(f"Result written to {args.output}")
    else:
        print(out_json)


if __name__ == "__main__":
    main()

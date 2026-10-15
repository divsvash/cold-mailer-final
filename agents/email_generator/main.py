"""CLI: generate ranked email variants for a candidate/job/company."""
from __future__ import annotations
from security import private_write
import argparse, json, pathlib, sys
from agents.email_generator.engine import EmailGenerationEngine
from agents.email_generator.schemas import CandidateProfile, CompanyInfo, JobAnalysis

from config import ModelSetupError, get_settings, resolve_path

def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Generate ranked outreach email variants")
    parser.add_argument("--profile",     default=str(settings.PROFILE_PATH))
    parser.add_argument("--job",         required=True)
    parser.add_argument("--company",     required=True)
    parser.add_argument("--personality", default=str(settings.PERSONALITY_PATH))
    parser.add_argument("--output",      default=None)
    args = parser.parse_args()

    for p, label in [
        (args.profile,     "profile"),
        (args.job,         "job analysis"),
        (args.company,     "company info"),
        (args.personality, "personality prompt"),
    ]:
        if not resolve_path(p).exists():
            print(f"ERROR: {label} not found: {p}", file=sys.stderr); sys.exit(1)

    candidate   = CandidateProfile.model_validate(json.loads(resolve_path(args.profile).read_text()))
    job         = JobAnalysis.model_validate(json.loads(resolve_path(args.job).read_text()))
    company     = CompanyInfo.model_validate(json.loads(resolve_path(args.company).read_text()))
    personality = resolve_path(args.personality).read_text()

    try:
        result = EmailGenerationEngine().generate(candidate, job, company, personality)
    except ModelSetupError as exc:
        raise SystemExit(str(exc)) from None
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
            private_write(resolve_path(args.output), out_json); print(f"Result written to {args.output}")
    else:
        print(out_json)


if __name__ == "__main__":
    main()

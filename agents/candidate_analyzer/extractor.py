"""PKB extractor — reads source files, calls Claude, returns validated Profile."""
from __future__ import annotations
import json
from security import UNTRUSTED_RULE, untrusted_data
import pathlib
import textwrap
import anthropic
from config import require_model_key, get_settings, resolve_path
from agents.candidate_analyzer.models import Profile
from agents.candidate_analyzer.readers import read_md, read_pdf

SYSTEM_PROMPT = textwrap.dedent("""
    You are a precise data-extraction assistant. Read the provided source documents
    and extract structured information into JSON matching the schema in the user message.
    RULES:
    1. Extract ONLY information explicitly stated in the sources. Do NOT infer or invent.
    2. If a field cannot be determined, use null.
    3. Respond with ONLY valid JSON — no markdown fences, no preamble.
    4. For lists, include every item you can find.
""").strip()


def _build_user_prompt(resume_text: str, projects_text: str, achievements_text: str) -> str:
    schema_hint = json.dumps(Profile.model_json_schema(), indent=2)
    return textwrap.dedent(f"""
        Extract the profile from the documents below into this JSON schema:
        {schema_hint}

        ══ RESUME ══
        {resume_text}

        ══ PROJECTS ══
        {projects_text}

        ══ ACHIEVEMENTS ══
        {achievements_text}
    """).strip()


def extract_profile(
    resume_pdf:       str | pathlib.Path | None = None,
    projects_md:      str | pathlib.Path | None = None,
    achievements_md:  str | pathlib.Path | None = None,
    model: str | None = None,
) -> Profile:
    settings = get_settings()
    resume_pdf = resolve_path(resume_pdf) if resume_pdf is not None else settings.RESUME_PATH
    projects_md = resolve_path(projects_md) if projects_md is not None else settings.PROJECTS_PATH
    achievements_md = resolve_path(achievements_md) if achievements_md is not None else settings.ACHIEVEMENTS_PATH
    resume_text       = read_pdf(resume_pdf)
    projects_text     = read_md(projects_md)
    achievements_text = read_md(achievements_md)

    client  = anthropic.Anthropic(api_key=require_model_key())
    message = client.messages.create(
        model=model or settings.LLM_MODEL, max_tokens=4096, system=SYSTEM_PROMPT + "\n" + UNTRUSTED_RULE,
        messages=[{"role": "user", "content": untrusted_data("candidate_sources", _build_user_prompt(resume_text, projects_text, achievements_text))}],
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(l for l in raw.splitlines() if not l.startswith("```")).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Model returned invalid profile JSON") from exc
    try:
        return Profile.model_validate(data)
    except Exception as exc:
        raise ValueError("Profile failed schema validation") from exc

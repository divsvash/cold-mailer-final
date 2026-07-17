"""Email generation engine — two-step generate→rank pipeline with grounding check."""
from __future__ import annotations
import re
import textwrap
import anthropic
from agents.email_generator.fact_sheet import build_fact_sheet
from agents.email_generator.schemas import (
    CandidateProfile, CompanyInfo, EmailRanking, EmailVariant,
    JobAnalysis, RankedEmailResult, VariantType,
)

GENERATE_TOOL_NAME = "record_email_variants"
RANK_TOOL_NAME     = "rank_email_variants"
MAX_WORDS          = 150
EXPECTED_VARIANT_TYPES = {VariantType.TECHNICAL, VariantType.FOUNDER, VariantType.CONCISE}

_STOPWORDS = {
    "i","the","a","an","this","that","these","those","hi","hello","best","thanks",
    "thank","you","re","regards","dear","would","could","should","open","love","saw",
    "interested","looking","forward","team","there","subject",
}
_SENTENCE_INITIAL_COMMON_WORDS = {
    "before","after","during","since","while","when","if","as","given","based",
    "having","to","for","with","without","and","but","so","also","however",
    "additionally","currently","previously","recently","we","our","my","your",
    "their","is","are","was","were","it","they","he","she",
}

GENERATE_SYSTEM = textwrap.dedent("""
    You are an outreach email generator. Given a FACT SHEET and PERSONALITY GUIDE,
    call `record_email_variants` once producing THREE variants:
    - "technical": leads with a specific technical detail from the candidate's work.
    - "founder": framed for a founder/small-team — ownership, scope, impact.
    - "concise": shortest credible version (50-90 words).

    GROUNDING RULES:
    - Every factual claim MUST appear in the FACT SHEET. If not there, omit it.
    - Do NOT invent: company funding, product names, recipient names, metrics, or news
      beyond what the FACT SHEET contains.
    - If FACT SHEET has no RECIPIENT NAME, use "Hi there" or "Hi [team name]".
    - If FACT SHEET has no RECENT NEWS, do not reference any company news.

    LENGTH: each body must be under {max_words} words.

    PERSONALITY GUIDE:
    {personality}

    FACT SHEET:
    {fact_sheet}
""").strip()

RANK_SYSTEM = textwrap.dedent("""
    Evaluate three outreach email variants for expected reply rate.
    Call `rank_email_variants` once, providing for EACH variant:
    - expected_reply_rate: 0.0-1.0 estimate based on specificity, relevance, brevity, clear ask.
    - reasoning: 1-2 sentences.
    Return exactly one ranking per variant type.
""").strip()


def _generate_tool_schema() -> dict:
    variant = {
        "type": "object",
        "properties": {
            "variant_type": {"type": "string", "enum": ["technical", "founder", "concise"]},
            "subject":      {"type": "string", "minLength": 1, "maxLength": 120},
            "body":         {"type": "string", "minLength": 1},
            "word_count":   {"type": "integer", "minimum": 0},
        },
        "required": ["variant_type", "subject", "body", "word_count"],
        "additionalProperties": False,
    }
    return {
        "name": GENERATE_TOOL_NAME,
        "description": "Record three email variants: technical, founder, concise.",
        "input_schema": {
            "type": "object",
            "properties": {"variants": {"type": "array", "items": variant, "minItems": 3, "maxItems": 3}},
            "required": ["variants"],
            "additionalProperties": False,
        },
    }


def _rank_tool_schema() -> dict:
    ranking = {
        "type": "object",
        "properties": {
            "variant_type":        {"type": "string", "enum": ["technical", "founder", "concise"]},
            "expected_reply_rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "reasoning":           {"type": "string", "minLength": 1, "maxLength": 400},
        },
        "required": ["variant_type", "expected_reply_rate", "reasoning"],
        "additionalProperties": False,
    }
    return {
        "name": RANK_TOOL_NAME,
        "description": "Record expected reply rate and reasoning for each email variant.",
        "input_schema": {
            "type": "object",
            "properties": {"rankings": {"type": "array", "items": ranking, "minItems": 3, "maxItems": 3}},
            "required": ["rankings"],
            "additionalProperties": False,
        },
    }


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def extract_proper_nouns(text: str) -> set[str]:
    result: set[str] = set()
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9]*(?:\.[A-Za-z0-9]+)*\b", text):
        token = match.group(0)
        if token.lower() in _STOPWORDS or len(token) < 2:
            continue
        start  = match.start()
        prefix = text[:start].rstrip()
        is_sentence_initial = (start == 0 or prefix == "" or prefix[-1] in ".!?:\n")
        if is_sentence_initial and token.lower() in _SENTENCE_INITIAL_COMMON_WORDS:
            continue
        result.add(token)
    return result


def check_grounding(body: str, fact_sheet: str) -> list[str]:
    fact_sheet_lower = fact_sheet.lower()
    return [t for t in extract_proper_nouns(body) if t.lower() not in fact_sheet_lower]


class EmailGenerationEngine:
    def __init__(self, model: str = "claude-sonnet-4-20250514", client: anthropic.Anthropic | None = None) -> None:
        self._model  = model
        self._client = client or anthropic.Anthropic()

    def generate(
        self,
        candidate: CandidateProfile,
        job: JobAnalysis,
        company: CompanyInfo,
        personality_prompt: str,
    ) -> RankedEmailResult:
        fact_sheet = build_fact_sheet(candidate, job, company)
        variants   = self._generate_variants(fact_sheet, personality_prompt)
        self._check_word_limits(variants)
        self._check_all_grounding(variants, fact_sheet)
        rankings   = self._rank_variants(variants)
        best       = self._select_best(variants, rankings)
        return RankedEmailResult(variants=variants, rankings=rankings, best_variant=best)

    def _generate_variants(self, fact_sheet: str, personality: str) -> list[EmailVariant]:
        system = GENERATE_SYSTEM.format(max_words=MAX_WORDS, personality=personality, fact_sheet=fact_sheet)
        message = self._client.messages.create(
            model=self._model, max_tokens=4096, system=system,
            tools=[_generate_tool_schema()],
            tool_choice={"type": "tool", "name": GENERATE_TOOL_NAME},
            messages=[{"role": "user", "content": f"Generate the three email variants.\n\nFACT SHEET:\n{fact_sheet}"}],
        )
        tool_use = self._extract_tool_use(message, GENERATE_TOOL_NAME)
        raw = tool_use.input.get("variants", [])
        if len(raw) != 3:
            raise ValueError(f"Expected 3 variants, got {len(raw)}")
        variants: list[EmailVariant] = []
        seen: set[VariantType] = set()
        for v in raw:
            try:
                vtype = VariantType(v["variant_type"])
            except (KeyError, ValueError) as exc:
                raise ValueError(f"Invalid variant_type: {v.get('variant_type')!r}") from exc
            seen.add(vtype)
            variants.append(EmailVariant(
                variant_type=vtype, subject=v["subject"], body=v["body"],
                word_count=_word_count(v["body"]),
            ))
        if seen != EXPECTED_VARIANT_TYPES:
            raise ValueError(f"Expected variant types {EXPECTED_VARIANT_TYPES}, got {seen}")
        return variants

    def _check_word_limits(self, variants: list[EmailVariant]) -> None:
        for v in variants:
            if v.word_count > MAX_WORDS:
                raise ValueError(f"Variant '{v.variant_type}' exceeds {MAX_WORDS}-word limit ({v.word_count}w)")

    def _check_all_grounding(self, variants: list[EmailVariant], fact_sheet: str) -> None:
        for v in variants:
            ungrounded = check_grounding(v.body, fact_sheet)
            if ungrounded:
                raise ValueError(
                    f"Variant '{v.variant_type}' contains terms not in the fact sheet "
                    f"(possible hallucination): {', '.join(sorted(ungrounded))}"
                )

    def _rank_variants(self, variants: list[EmailVariant]) -> list[EmailRanking]:
        variants_text = "\n\n".join(
            f"{v.variant_type.value.upper()}\nSubject: {v.subject}\nBody:\n{v.body}"
            for v in variants
        )
        message = self._client.messages.create(
            model=self._model, max_tokens=2048, system=RANK_SYSTEM,
            tools=[_rank_tool_schema()],
            tool_choice={"type": "tool", "name": RANK_TOOL_NAME},
            messages=[{"role": "user", "content": f"Rank these email variants:\n\n{variants_text}"}],
        )
        tool_use = self._extract_tool_use(message, RANK_TOOL_NAME)
        raw = tool_use.input.get("rankings", [])
        rankings: list[EmailRanking] = []
        seen: set[VariantType] = set()
        for r in raw:
            try:
                vtype = VariantType(r["variant_type"])
            except (KeyError, ValueError) as exc:
                raise ValueError(f"Invalid variant_type in ranking: {r.get('variant_type')!r}") from exc
            seen.add(vtype)
            rankings.append(EmailRanking(
                variant_type=vtype,
                expected_reply_rate=r["expected_reply_rate"],
                reasoning=r["reasoning"],
            ))
        variant_types = {v.variant_type for v in variants}
        if seen != variant_types:
            raise ValueError(f"Ranking types {seen} do not match generated types {variant_types}")
        return rankings

    def _select_best(self, variants: list[EmailVariant], rankings: list[EmailRanking]) -> EmailVariant:
        rate_by_type = {r.variant_type: r.expected_reply_rate for r in rankings}
        return max(variants, key=lambda v: rate_by_type.get(v.variant_type, 0.0))

    def _extract_tool_use(self, message, expected_name: str):
        block = next((b for b in message.content if b.type == "tool_use"), None)
        if block is None:
            raise ValueError(f"Model did not return a tool_use block. Stop: {message.stop_reason}")
        if block.name != expected_name:
            raise ValueError(f"Model called '{block.name}', expected '{expected_name}'")
        return block

"""Unit tests for email_generator engine with mocked Anthropic client."""
from __future__ import annotations
import copy
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from agents.email_generator.engine import (
    GENERATE_TOOL_NAME, RANK_TOOL_NAME, MAX_WORDS,
    EmailGenerationEngine, check_grounding, extract_proper_nouns,
)
from agents.email_generator.fact_sheet import build_fact_sheet
from agents.email_generator.schemas import CandidateProfile, CompanyInfo, JobAnalysis, VariantType
from tests.email_generator.fixtures import (
    CANDIDATE, COMPANY_MINIMAL_INFO, COMPANY_WITH_FULL_INFO,
    JOB_ANALYSIS, PERSONALITY_PROMPT,
    RESPONSE_OVERLONG_TECHNICAL, RESPONSE_WITH_HALLUCINATION,
    VALID_GENERATION_RESPONSE, VALID_RANKING_RESPONSE,
)


def _make_client(*responses) -> MagicMock:
    """Build a mock Anthropic client that returns successive tool_use blocks."""
    def make_msg(tool_name: str, tool_input: dict):
        block = SimpleNamespace(type="tool_use", name=tool_name, input=tool_input, id="t1")
        return SimpleNamespace(content=[block], stop_reason="tool_use")

    messages = []
    for tool_name, tool_input in responses:
        messages.append(make_msg(tool_name, tool_input))

    client = MagicMock()
    client.messages.create.side_effect = messages
    return client


def _make_text_client() -> MagicMock:
    block   = SimpleNamespace(type="text", text="Sorry.")
    message = SimpleNamespace(content=[block], stop_reason="end_turn")
    client  = MagicMock()
    client.messages.create.return_value = message
    return client


def _engine(client: MagicMock) -> EmailGenerationEngine:
    return EmailGenerationEngine(client=client)


def _inputs():
    return (
        CandidateProfile.model_validate(CANDIDATE),
        JobAnalysis.model_validate(JOB_ANALYSIS),
        CompanyInfo.model_validate(COMPANY_WITH_FULL_INFO),
        PERSONALITY_PROMPT,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# extract_proper_nouns / check_grounding
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractProperNouns:
    def test_finds_camel_case(self):
        assert "FastAPI" in extract_proper_nouns("We use FastAPI for everything.")

    def test_finds_dotted(self):
        assert "Next.js" in extract_proper_nouns("Built with Next.js.")

    def test_ignores_stopwords(self):
        result = extract_proper_nouns("Hi there, thanks for reaching out.")
        assert "Hi" not in result and "Thanks" not in result

    def test_ignores_sentence_initial_common(self):
        result = extract_proper_nouns("Before we start, let me introduce FastAPI.")
        assert "Before" not in result
        assert "FastAPI" in result

    def test_handles_empty_string(self):
        assert extract_proper_nouns("") == set()


class TestCheckGrounding:
    def test_grounded_term_passes(self):
        fact_sheet = "CANDIDATE NAME: Divyansh Sharma\nSKILL: FastAPI"
        assert check_grounding("I built FastAPI services.", fact_sheet) == []

    def test_ungrounded_term_flagged(self):
        fact_sheet = "CANDIDATE NAME: Divyansh Sharma"
        ungrounded = check_grounding("I know Sequoia invested in this.", fact_sheet)
        assert "Sequoia" in ungrounded

    def test_case_insensitive_match(self):
        fact_sheet = "SKILL: fastapi (advanced)"
        assert check_grounding("I built FastAPI backends.", fact_sheet) == []


# ═══════════════════════════════════════════════════════════════════════════════
# Happy path
# ═══════════════════════════════════════════════════════════════════════════════

class TestEngineHappyPath:
    def test_returns_ranked_result(self):
        client = _make_client(
            (GENERATE_TOOL_NAME, VALID_GENERATION_RESPONSE),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        result = _engine(client).generate(*_inputs())
        assert len(result.variants) == 3
        assert len(result.rankings) == 3
        assert result.best_variant is not None

    def test_best_is_highest_ranked(self):
        client = _make_client(
            (GENERATE_TOOL_NAME, VALID_GENERATION_RESPONSE),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        result = _engine(client).generate(*_inputs())
        assert result.best_variant.variant_type == VariantType.TECHNICAL
        assert result.best_expected_reply_rate == 0.42

    def test_all_three_variant_types_present(self):
        client = _make_client(
            (GENERATE_TOOL_NAME, VALID_GENERATION_RESPONSE),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        result = _engine(client).generate(*_inputs())
        types = {v.variant_type for v in result.variants}
        assert types == {VariantType.TECHNICAL, VariantType.FOUNDER, VariantType.CONCISE}

    def test_word_count_recomputed_not_trusted(self):
        """Model reports word_count=999 but body is short — we recompute."""
        gen = copy.deepcopy(VALID_GENERATION_RESPONSE)
        for v in gen["variants"]:
            v["word_count"] = 999
        client = _make_client(
            (GENERATE_TOOL_NAME, gen),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        result = _engine(client).generate(*_inputs())
        for v in result.variants:
            assert v.word_count < 200  # real count, not 999

    def test_two_api_calls_made(self):
        client = _make_client(
            (GENERATE_TOOL_NAME, VALID_GENERATION_RESPONSE),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        _engine(client).generate(*_inputs())
        assert client.messages.create.call_count == 2

    def test_fact_sheet_is_user_data_not_system_instructions(self):
        client = _make_client(
            (GENERATE_TOOL_NAME, VALID_GENERATION_RESPONSE),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        _engine(client).generate(*_inputs())
        first_call_kwargs = client.messages.create.call_args_list[0].kwargs
        assert "CANDIDATE NAME" not in first_call_kwargs["system"]
        assert "CANDIDATE NAME" in first_call_kwargs["messages"][0]["content"]

    def test_personality_is_user_data(self):
        client = _make_client(
            (GENERATE_TOOL_NAME, VALID_GENERATION_RESPONSE),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        _engine(client).generate(*_inputs())
        first_call_kwargs = client.messages.create.call_args_list[0].kwargs
        assert "Natural" not in first_call_kwargs["system"]
        assert "Natural" in first_call_kwargs["messages"][0]["content"]


# ═══════════════════════════════════════════════════════════════════════════════
# Word limit enforcement
# ═══════════════════════════════════════════════════════════════════════════════

class TestWordLimitEnforcement:
    def test_overlong_variant_raises(self):
        client = _make_client(
            (GENERATE_TOOL_NAME, RESPONSE_OVERLONG_TECHNICAL),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        with pytest.raises(ValueError, match="word limit"):
            _engine(client).generate(*_inputs())

    def test_max_words_is_150(self):
        assert MAX_WORDS == 150


# ═══════════════════════════════════════════════════════════════════════════════
# Grounding check
# ═══════════════════════════════════════════════════════════════════════════════

class TestGroundingCheck:
    def test_hallucinated_term_raises(self):
        client = _make_client(
            (GENERATE_TOOL_NAME, RESPONSE_WITH_HALLUCINATION),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        with pytest.raises(ValueError, match="hallucination"):
            _engine(client).generate(*_inputs())

    def test_grounded_content_passes(self):
        client = _make_client(
            (GENERATE_TOOL_NAME, VALID_GENERATION_RESPONSE),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        # Should not raise
        _engine(client).generate(*_inputs())


# ═══════════════════════════════════════════════════════════════════════════════
# Error paths
# ═══════════════════════════════════════════════════════════════════════════════

class TestEngineErrorPaths:
    def test_no_tool_use_block_raises(self):
        client = _make_text_client()
        with pytest.raises(ValueError, match="did not return"):
            _engine(client).generate(*_inputs())

    def test_wrong_tool_name_raises(self):
        client = _make_client((  "wrong_tool", VALID_GENERATION_RESPONSE))
        with pytest.raises(ValueError, match="expected"):
            _engine(client).generate(*_inputs())

    def test_missing_variant_type_raises(self):
        bad = copy.deepcopy(VALID_GENERATION_RESPONSE)
        # Remove one variant to produce only 2
        bad["variants"] = bad["variants"][:2]
        client = _make_client(
            (GENERATE_TOOL_NAME, bad),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        with pytest.raises(ValueError):
            _engine(client).generate(*_inputs())

    def test_minimal_company_no_hallucination(self):
        """With only company name provided, model must not reference absent fields."""
        gen = copy.deepcopy(VALID_GENERATION_RESPONSE)
        # Rewrite bodies to not reference Alex / recent news / role title
        for v in gen["variants"]:
            v["body"] = (
                v["body"]
                .replace("Hi Alex,", "Hi there,")
                .replace("Vectorly launched a new open-source code search API last month.", "")
                .replace("the Backend Engineer role", "the open role")
                .replace("Backend Engineer", "the role")
            )
        client = _make_client(
            (GENERATE_TOOL_NAME, gen),
            (RANK_TOOL_NAME,     VALID_RANKING_RESPONSE),
        )
        candidate, job, _, personality = _inputs()
        company = CompanyInfo.model_validate(COMPANY_MINIMAL_INFO)
        result = _engine(client).generate(candidate, job, company, personality)
        assert result.best_variant is not None

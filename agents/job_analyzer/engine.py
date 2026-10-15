"""Job Understanding Engine — forced tool-use, strict schema."""
from __future__ import annotations
import json
import textwrap
import anthropic
from config import get_settings
from agents.job_analyzer.schemas import JobUnderstanding, JobUnderstandingRequest, JobUnderstandingResponse

TOOL_NAME = "record_job_understanding"

SYSTEM_PROMPT = textwrap.dedent("""
    You are a job description analysis engine. Call `record_job_understanding` exactly once.
    Extract ONLY information stated or strongly implied by the job description.
    Use null for unknown fields. must_have_skills: required/mandatory skills.
    preferred_skills: 'nice to have', 'bonus', 'preferred' skills.
    Normalise skill names (e.g. 'JS' -> 'JavaScript', 'k8s' -> 'Kubernetes').
    domain: single closest enum match. seniority: infer from title/years/scope.
    business_problems: 1-10 concrete problems this hire will address.
    culture: only traits with explicit textual support.
""").strip()


class JobUnderstandingEngine:
    def __init__(self, model: str | None = None, client: anthropic.Anthropic | None = None) -> None:
        self._model  = model or get_settings().LLM_MODEL
        self._client = client or anthropic.Anthropic(api_key=get_settings().ANTHROPIC_API_KEY)

    def analyze(self, job_description: str) -> JobUnderstandingResponse:
        request = JobUnderstandingRequest(job_description=job_description)
        schema  = JobUnderstanding.model_json_schema()
        tool    = {
            "name": TOOL_NAME,
            "description": "Record structured understanding of a job description.",
            "input_schema": schema,
        }
        message = self._client.messages.create(
            model=self._model, max_tokens=4096, system=SYSTEM_PROMPT,
            tools=[tool], tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": f"Job description:\n\n{request.job_description}"}],
        )
        tool_use = next((b for b in message.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise ValueError(f"Model did not return a tool_use block. Stop reason: {message.stop_reason}")
        if tool_use.name != TOOL_NAME:
            raise ValueError(f"Model called unexpected tool '{tool_use.name}'")
        try:
            result = JobUnderstanding.model_validate(tool_use.input)
        except Exception as exc:
            raise ValueError(f"Tool input failed validation: {exc}") from exc
        return JobUnderstandingResponse(result=result, model=self._model)

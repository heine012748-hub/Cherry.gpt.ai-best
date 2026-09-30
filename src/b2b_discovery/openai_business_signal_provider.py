"""Optional OpenAI Responses API adapter for Business Signal extraction.

The OpenAI SDK and Pydantic are imported only when this provider is selected.
Its output is still passed through the shared v0.2 validation and scoring path.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Mapping

from .business_signal_analyzer import SIGNAL_NAMES
from .company_analyzer import Company

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
PROVIDER_INSTRUCTIONS = """You extract structured business activity signals from supplied company information.

Use only the information in the input. Do not infer facts that are not stated.
Return exactly one result for each of the six signals: distributor, importer,
wholesaler, retailer, exporter, international_business. Use those names only.

Set detected=true only when an input sentence explicitly supports an existing
business activity. Do not mark mere possibility, plans, or aspirations as an
existing activity. Negation must remain negative: for example, 'We do not
import', 'We are not a distributor', and "We don't export" are not positive
signals. Each true result must include at least one verbatim quote copied from
company_description, business_type, or website_content, and the matching
source_type. Quotes must be exact substrings of the supplied field. The
website URL is context only, is not evidence, and must never be visited or used
to infer activity. Existing business_signals are user-supplied context, not
evidence for an AI-detected signal. Use an empty evidence list for false
results. Return confidence from 0 to 1 describing confidence that the cited
input supports the classification; it is not purchase probability. Do not
calculate or return any score."""


class OpenAIProviderError(RuntimeError):
    """Base exception for errors specific to the optional OpenAI provider."""


class OpenAIConfigurationError(OpenAIProviderError):
    """OpenAI mode is selected but its key or optional packages are missing."""


class OpenAIResponseError(OpenAIProviderError):
    """The Responses API did not return a usable structured response."""


class OpenAIAPIError(OpenAIProviderError):
    """The Responses API request failed."""


@lru_cache(maxsize=1)
def _get_response_model():
    """Build the Pydantic schema lazily so base installs need no Pydantic."""
    try:
        from pydantic import BaseModel, ConfigDict
    except ImportError as exc:
        raise OpenAIConfigurationError(
            "OpenAI mode requires the optional dependencies. Install them with: "
            "python -m pip install -r requirements-openai.txt"
        ) from exc

    class StrictModel(BaseModel):
        model_config = ConfigDict(extra="forbid")

    class EvidenceOutput(StrictModel):
        source_type: str
        source_ref: str
        quote: str

    class SignalOutput(StrictModel):
        # Keep the name as a string so the shared validator, not the SDK schema,
        # remains the authority that rejects unsupported signal names.
        name: str
        detected: bool
        evidence: list[EvidenceOutput]
        confidence: float

    class SignalExtractionOutput(StrictModel):
        signals: list[SignalOutput]

    return SignalExtractionOutput


def _company_input(company: Company) -> dict[str, object]:
    """Serialize only existing CSV fields; never fetch or crawl a website."""
    return {
        "name": company.name,
        "website": company.website,
        "country": company.country,
        "industry": company.industry,
        "employees": company.employees,
        "product_categories": list(company.product_categories),
        "operating_markets": list(company.operating_markets),
        "business_signals": list(company.business_signals),
        "company_description": company.company_description,
        "business_type": company.business_type,
        "website_content": company.website_content,
    }


def _has_public_text(company: Company) -> bool:
    return any((company.company_description.strip(), company.business_type.strip(),
                company.website_content.strip()))


def _parsed_mapping(parsed: Any) -> Mapping[str, object]:
    if isinstance(parsed, Mapping):
        return parsed
    model_dump = getattr(parsed, "model_dump", None)
    if callable(model_dump):
        value = model_dump()
    else:
        legacy_dump = getattr(parsed, "dict", None)
        value = legacy_dump() if callable(legacy_dump) else None
    if not isinstance(value, Mapping):
        raise OpenAIResponseError("OpenAI returned no parsed structured signal result.")
    return value


class OpenAIBusinessSignalProvider:
    """Extract structured signals through OpenAI's Responses parse API.

    `client` and `response_model` are injectable for tests; neither is needed
    in normal use. No score is requested or consumed here.
    """

    name = "openai"

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        client: Any | None = None,
        response_model: Any | None = None,
    ) -> None:
        self.model = (model or os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_OPENAI_MODEL)
        self._response_model = response_model
        if client is not None:
            self.client = client
            return

        configured_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
        if not configured_key or not configured_key.strip():
            raise OpenAIConfigurationError(
                "OpenAI mode requires OPENAI_API_KEY. Set the environment variable, "
                "or use --business-signal-mode rules for offline analysis."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OpenAIConfigurationError(
                "OpenAI mode requires the optional dependencies. Install them with: "
                "python -m pip install -r requirements-openai.txt"
            ) from exc
        self.client = OpenAI(api_key=configured_key)

    def analyze(self, company: Company) -> Mapping[str, object]:
        if not _has_public_text(company):
            return {
                "schema_version": "0.3",
                "analysis_status": "insufficient_input",
                "signals": [
                    {"name": name, "detected": False, "evidence": [], "confidence": 0.0}
                    for name in SIGNAL_NAMES
                ],
            }

        if self._response_model is None:
            self._response_model = _get_response_model()
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=PROVIDER_INSTRUCTIONS,
                input=json.dumps(_company_input(company), ensure_ascii=False),
                text_format=self._response_model,
            )
        except Exception as exc:
            raise OpenAIAPIError(f"OpenAI Responses API request failed: {exc}") from exc

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise OpenAIResponseError(
                "OpenAI returned no parsed structured signal result (possibly a refusal)."
            )
        output = dict(_parsed_mapping(parsed))
        output["schema_version"] = "0.3"
        output["analysis_status"] = "completed"
        # The analyzer's existing validator checks all names, evidence and
        # confidence values before any deterministic score can consume them.
        return output

"""Provider-neutral analysis and strict validation for public business signals."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from .company_analyzer import Company

SIGNAL_NAMES = (
    "distributor", "importer", "wholesaler", "retailer", "exporter",
    "international_business",
)
SOURCE_FIELDS = {
    "company_description": "company_description",
    "business_type": "business_type",
    "website_content": "website_content",
}


class SignalValidationError(ValueError):
    """Raised when provider output violates the structured signal contract."""


@dataclass(frozen=True)
class BusinessSignalEvidence:
    source_type: str
    quote: str
    source_ref: str = ""


@dataclass(frozen=True)
class BusinessSignal:
    name: str
    detected: bool
    evidence: tuple[BusinessSignalEvidence, ...]
    confidence: float


@dataclass(frozen=True)
class BusinessSignalAnalysis:
    company_name: str
    analysis_status: str
    signals: tuple[BusinessSignal, ...]
    provider: str
    schema_version: str = "0.2"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "company": {"name": self.company_name},
            "provider": self.provider,
            "analysis_status": self.analysis_status,
            "signals": [
                {
                    "name": signal.name,
                    "detected": signal.detected,
                    "evidence": [
                        {"source_type": item.source_type, "source_ref": item.source_ref,
                         "quote": item.quote}
                        for item in signal.evidence
                    ],
                    "confidence": signal.confidence,
                }
                for signal in self.signals
            ],
        }


class BusinessSignalProvider(Protocol):
    """Adapter contract: return structured data, never a numeric score."""

    name: str

    def analyze(self, company: Company) -> Mapping[str, object]: ...


_PATTERNS = {
    "distributor": r"\b(distributor|distribution|distributes|distributing)\b",
    "importer": r"\b(importer|importing|imports|import)\b",
    "wholesaler": r"\b(wholesaler|wholesale|wholesaling)\b",
    "retailer": r"\b(retailer|retail|retailing)\b",
    "exporter": r"\b(exporter|exporting|exports|export)\b",
    "international_business": r"\b(international|overseas|global|cross[- ]border)\b",
}
_NEGATION = re.compile(
    r"\b(?:do not|does not|did not|never|not|no longer|isn't|aren't|don't|doesn't)"
    r"\b(?:\s+\w+){0,2}\s*$",
    flags=re.IGNORECASE,
)


def _is_negated(text: str, match_start: int) -> bool:
    """Catch simple local denials without treating earlier sentences as scope."""
    clause_start = max(
        text.rfind(".", 0, match_start),
        text.rfind("!", 0, match_start),
        text.rfind("?", 0, match_start),
        text.rfind(";", 0, match_start),
        text.rfind("\n", 0, match_start),
    ) + 1
    return _NEGATION.search(text[clause_start:match_start]) is not None


def _source_text(company: Company) -> dict[str, str]:
    return {
        "company_description": company.company_description,
        "business_type": company.business_type,
        "website_content": company.website_content,
    }


class RulesBusinessSignalProvider:
    """Offline keyword provider; each detection includes an exact source quote."""

    name = "rules"

    def analyze(self, company: Company) -> Mapping[str, object]:
        sources = _source_text(company)
        signals = []
        for name, pattern in _PATTERNS.items():
            evidence = []
            for source_type, text in sources.items():
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match and not _is_negated(text, match.start()):
                    # Keep a short sentence-like excerpt while preserving a
                    # literal substring that the validator can verify.
                    start = max(text.rfind(".", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
                    end_candidates = [pos for pos in (text.find(".", match.end()), text.find("\n", match.end())) if pos >= 0]
                    end = min(end_candidates) + 1 if end_candidates else len(text)
                    quote = text[start:end].strip()
                    evidence.append({"source_type": source_type, "source_ref": "", "quote": quote})
            signals.append({
                "name": name,
                "detected": bool(evidence),
                "evidence": evidence,
                "confidence": 0.8 if evidence else 0.0,
            })
        status = "completed" if any(s["detected"] for s in signals) else (
            "completed" if any(sources.values()) else "insufficient_input"
        )
        return {"analysis_status": status, "signals": signals}


class MockBusinessSignalProvider:
    """Small injectable provider for tests and downstream adapter development."""

    name = "mock"

    def __init__(self, response: Mapping[str, object]):
        self.response = response

    def analyze(self, company: Company) -> Mapping[str, object]:
        return self.response


def validate_business_signal_analysis(
    company: Company, raw: Mapping[str, object], *, provider: str = "provider"
) -> BusinessSignalAnalysis:
    """Validate names, confidence, and evidence against supplied source text."""
    if not isinstance(raw, Mapping):
        raise SignalValidationError("analysis result must be an object")
    status = raw.get("analysis_status", "completed")
    if not isinstance(status, str) or status not in {"completed", "insufficient_input"}:
        raise SignalValidationError("analysis_status is invalid")
    schema_version = raw.get("schema_version", "0.2")
    if not isinstance(schema_version, str) or schema_version not in {"0.2", "0.3"}:
        raise SignalValidationError("schema_version is invalid")
    raw_signals = raw.get("signals")
    if not isinstance(raw_signals, Sequence) or isinstance(raw_signals, (str, bytes)):
        raise SignalValidationError("signals must be a list")
    by_name: dict[str, BusinessSignal] = {}
    available_sources = _source_text(company)
    for item in raw_signals:
        if not isinstance(item, Mapping):
            raise SignalValidationError("each signal must be an object")
        name = item.get("name")
        if name not in SIGNAL_NAMES:
            raise SignalValidationError(f"unknown signal name: {name!r}")
        if name in by_name:
            raise SignalValidationError(f"duplicate signal name: {name!r}")
        detected = item.get("detected")
        if not isinstance(detected, bool):
            raise SignalValidationError(f"{name}: detected must be boolean")
        confidence = item.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise SignalValidationError(f"{name}: confidence must be between 0 and 1")
        raw_evidence = item.get("evidence")
        if not isinstance(raw_evidence, Sequence) or isinstance(raw_evidence, (str, bytes)):
            raise SignalValidationError(f"{name}: evidence must be a list")
        evidence = []
        for entry in raw_evidence:
            if not isinstance(entry, Mapping):
                raise SignalValidationError(f"{name}: evidence item must be an object")
            source_type, quote = entry.get("source_type"), entry.get("quote")
            if (not isinstance(source_type, str) or source_type not in SOURCE_FIELDS
                    or not isinstance(quote, str) or not quote.strip()):
                raise SignalValidationError(f"{name}: evidence must cite supplied public text")
            source_text = available_sources[SOURCE_FIELDS[source_type]]
            if not source_text or quote not in source_text:
                raise SignalValidationError(f"{name}: evidence quote is not present in supplied {source_type}")
            source_ref = entry.get("source_ref", "")
            if not isinstance(source_ref, str):
                raise SignalValidationError(f"{name}: source_ref must be a string")
            evidence.append(BusinessSignalEvidence(source_type, quote, source_ref))
        if detected and not evidence:
            raise SignalValidationError(f"{name}: detected=true requires at least one evidence item")
        by_name[name] = BusinessSignal(name, detected, tuple(evidence), float(confidence))
    missing = set(SIGNAL_NAMES) - set(by_name)
    if missing:
        raise SignalValidationError(f"missing signals: {', '.join(sorted(missing))}")
    if status == "insufficient_input" and any(signal.detected for signal in by_name.values()):
        raise SignalValidationError("insufficient_input cannot contain detected signals")
    return BusinessSignalAnalysis(
        company_name=company.name,
        analysis_status=str(status),
        signals=tuple(by_name[name] for name in SIGNAL_NAMES),
        provider=provider,
        schema_version=schema_version,
    )


def analyze_business_signals(
    company: Company, provider: BusinessSignalProvider
) -> BusinessSignalAnalysis:
    """Call an injected provider then validate every claim against its input."""
    if not any(_source_text(company).values()):
        # Do not treat website URL or manually entered legacy tags as source text.
        empty = {
            "analysis_status": "insufficient_input",
            "signals": [
                {"name": name, "detected": False, "evidence": [], "confidence": 0.0}
                for name in SIGNAL_NAMES
            ],
        }
        return validate_business_signal_analysis(company, empty, provider=provider.name)
    raw = provider.analyze(company)
    return validate_business_signal_analysis(company, raw, provider=provider.name)

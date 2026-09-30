import json
import builtins
from types import SimpleNamespace

import pytest

from b2b_discovery.business_signal_analyzer import (
    SIGNAL_NAMES,
    SignalValidationError,
    analyze_business_signals,
)
from b2b_discovery.business_signal_scoring import score_business_signals
from b2b_discovery.company_analyzer import Company, DiscoveryCriteria, analyze_companies, main
from b2b_discovery.openai_business_signal_provider import (
    DEFAULT_OPENAI_MODEL,
    OpenAIAPIError,
    OpenAIConfigurationError,
    OpenAIBusinessSignalProvider,
    PROVIDER_INSTRUCTIONS,
)


class FakeParsedOutput:
    def __init__(self, result):
        self.result = result

    def model_dump(self):
        return self.result


class FakeResponses:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=self.output)


class FakeClient:
    def __init__(self, output=None, error=None):
        self.responses = FakeResponses(output=output, error=error)


def sample_company(**overrides):
    values = dict(
        name="Acme Foods", country="Singapore", industry="Food Distribution",
        employees=120, product_categories=("plant-based",),
        website="https://acme.example", operating_markets=("Singapore",),
        business_signals=("manual tag",),
        company_description="We import plant-based food products.",
        business_type="Food distributor", website_content="We import food products.",
    )
    values.update(overrides)
    return Company(**values)


def structured_response(company, *, confidence=0.91, evidence=True):
    quote = "We import plant-based food products."
    return {
        "signals": [
            {
                "name": name,
                "detected": name == "importer",
                "evidence": ([{
                    "source_type": "company_description",
                    "source_ref": "provided-input",
                    "quote": quote,
                }] if name == "importer" and evidence else []),
                "confidence": confidence if name == "importer" else 0.0,
            }
            for name in SIGNAL_NAMES
        ]
    }


def provider_for(output, *, model="fake-model"):
    client = FakeClient(FakeParsedOutput(output))
    provider = OpenAIBusinessSignalProvider(
        model=model, client=client, response_model=object,
    )
    return provider, client


def test_openai_provider_converts_responses_parse_result_and_uses_supplied_fields(monkeypatch):
    company = sample_company()
    provider, client = provider_for(structured_response(company))
    monkeypatch.setenv("OPENAI_MODEL", "env-model")
    # Explicit provider model wins over environment configuration.
    analysis = analyze_business_signals(company, provider)

    assert analysis.provider == "openai"
    assert analysis.schema_version == "0.3"
    assert next(signal for signal in analysis.signals if signal.name == "importer").detected
    call = client.responses.calls[0]
    assert call["model"] == "fake-model"
    assert call["text_format"] is object
    assert "do not import" in " ".join(call["instructions"].lower().split())
    input_data = json.loads(call["input"])
    assert input_data["company_description"] == company.company_description
    assert input_data["business_signals"] == ["manual tag"]
    assert input_data["website"] == company.website
    assert "website_content" in input_data
    assert not hasattr(provider, "score")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda raw: raw["signals"][1].update(name="buyer_probability"), "unknown signal"),
        (lambda raw: raw["signals"][2].update(name="importer"), "duplicate signal"),
        (lambda raw: raw["signals"][1].update(confidence=1.2), "confidence"),
        (lambda raw: raw["signals"][1].update(confidence=-0.1), "confidence"),
        (lambda raw: raw["signals"][1].update(confidence=float("nan")), "confidence"),
        (lambda raw: raw["signals"][0].update(detected=True), "requires at least one evidence"),
        (lambda raw: raw["signals"][0].update(detected=True,
             evidence=[{"source_type": "company_description", "quote": "not in input"}]), "not present"),
    ],
)
def test_openai_provider_output_always_passes_shared_validation(mutate, message):
    company = sample_company()
    raw = structured_response(company)
    mutate(raw)
    provider, _ = provider_for(raw)
    with pytest.raises(SignalValidationError, match=message):
        analyze_business_signals(company, provider)


def test_openai_confidence_does_not_change_deterministic_business_signal_score():
    company = sample_company()
    scores = []
    for confidence in (0.1, 0.99):
        provider, _ = provider_for(structured_response(company, confidence=confidence))
        scores.append(score_business_signals(analyze_business_signals(company, provider)))
    assert scores == [16.7, 16.7]


def test_openai_url_only_input_returns_insufficient_without_calling_api():
    company = sample_company(company_description="", business_type="", website_content="")
    client = FakeClient(output=None)
    provider = OpenAIBusinessSignalProvider(client=client, response_model=object)
    analysis = analyze_business_signals(company, provider)
    assert analysis.analysis_status == "insufficient_input"
    assert not any(signal.detected for signal in analysis.signals)
    assert client.responses.calls == []


def test_openai_provider_defaults_model_and_respects_model_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "configured-model")
    provider = OpenAIBusinessSignalProvider(client=FakeClient(), response_model=object)
    assert provider.model == "configured-model"
    monkeypatch.delenv("OPENAI_MODEL")
    provider = OpenAIBusinessSignalProvider(client=FakeClient(), response_model=object)
    assert provider.model == DEFAULT_OPENAI_MODEL


def test_openai_api_failure_is_explicit_and_never_falls_back_to_legacy_score():
    company = sample_company()
    client = FakeClient(error=RuntimeError("connection failed"))
    provider = OpenAIBusinessSignalProvider(client=client, response_model=object)
    with pytest.raises(OpenAIAPIError, match="Responses API request failed"):
        analyze_companies([company], DiscoveryCriteria(), business_signal_provider=provider)
    # After the failed opt-in call, the independent default call is still the
    # unchanged v0.1 path and has no analysis payload.
    baseline = analyze_companies([company], DiscoveryCriteria())
    assert baseline[0]["score_components"]["business_signal"] == 43
    assert "business_signal_analysis" not in baseline[0]


def test_openai_mode_without_api_key_shows_clear_cli_error(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["--business-signal-mode", "openai"])
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "OpenAI mode requires OPENAI_API_KEY" in error
    assert "--business-signal-mode rules" in error


def test_openai_mode_with_key_but_without_optional_sdk_shows_install_hint(monkeypatch):
    original_import = builtins.__import__

    def no_openai(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("simulated missing optional package")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_openai)
    with pytest.raises(OpenAIConfigurationError, match="requirements-openai.txt"):
        OpenAIBusinessSignalProvider(api_key="test-key")


def test_openai_refusal_or_missing_parsed_output_is_reported():
    from b2b_discovery.openai_business_signal_provider import OpenAIResponseError

    company = sample_company()
    provider = OpenAIBusinessSignalProvider(
        client=FakeClient(output=None), response_model=object,
    )
    with pytest.raises(OpenAIResponseError, match="no parsed structured signal"):
        analyze_business_signals(company, provider)

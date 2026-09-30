import pytest

from b2b_discovery.business_signal_analyzer import (
    BusinessSignal,
    BusinessSignalAnalysis,
    BusinessSignalEvidence,
    SIGNAL_NAMES,
    MockBusinessSignalProvider,
    RulesBusinessSignalProvider,
    SignalValidationError,
    analyze_business_signals,
    validate_business_signal_analysis,
)
from b2b_discovery.business_signal_scoring import score_business_signals
from b2b_discovery.company_analyzer import (
    Company,
    DiscoveryCriteria,
    analyze_companies,
    load_companies,
    main,
)


def company(**kwargs):
    values = dict(name="Example", country="SG", industry="Food", employees=12,
                  product_categories=())
    values.update(kwargs)
    return Company(**values)


def response(company_obj, detected_names=(), evidence_count=1, confidence=0.8):
    names = set(detected_names)
    raw_signals = []
    for name in SIGNAL_NAMES:
        detected = name in names
        source_text = {
            "company_description": company_obj.company_description,
            "business_type": company_obj.business_type,
            "website_content": company_obj.website_content,
        }
        available = next(((field, text) for field, text in source_text.items() if text), None)
        evidence = []
        if detected:
            assert available
            field, text = available
            quote = text[: min(len(text), evidence_count)]
            evidence = [
                {"source_type": field, "quote": quote, "source_ref": ""}
                for _ in range(evidence_count)
            ]
        raw_signals.append({
            "name": name, "detected": detected,
            "evidence": evidence, "confidence": confidence,
        })
    return {"analysis_status": "completed", "signals": raw_signals}


def test_csv_loads_all_optional_analysis_text_columns(tmp_path):
    path = tmp_path / "companies.csv"
    path.write_text(
        "name,country,industry,employees,product_categories,website,company_description,business_type,website_content\n"
        "Example,SG,Food,12,tea,https://example.test,Company text,Importer,Website text\n",
        encoding="utf-8",
    )
    item = load_companies(path)[0]
    assert item.company_description == "Company text"
    assert item.business_type == "Importer"
    assert item.website_content == "Website text"


def test_analysis_requires_all_six_known_signal_names():
    item = company(company_description="We distribute food.")
    raw = response(item, ("distributor",))
    analysis = validate_business_signal_analysis(item, raw)
    assert tuple(signal.name for signal in analysis.signals) == SIGNAL_NAMES
    raw["signals"][0]["name"] = "buyer_probability"
    with pytest.raises(SignalValidationError, match="unknown signal"):
        validate_business_signal_analysis(item, raw)


def test_detected_true_requires_evidence_and_quotes_must_be_from_input():
    item = company(company_description="We distribute food.")
    raw = response(item, ("distributor",))
    raw["signals"][0]["evidence"] = []
    with pytest.raises(SignalValidationError, match="requires at least one evidence"):
        validate_business_signal_analysis(item, raw)
    raw = response(item, ("distributor",))
    raw["signals"][0]["evidence"][0]["quote"] = "We intend to buy."
    with pytest.raises(SignalValidationError, match="not present"):
        validate_business_signal_analysis(item, raw)


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("nan"), "0.8"])
def test_confidence_must_be_a_number_between_zero_and_one(confidence):
    item = company(company_description="We distribute food.")
    raw = response(item, ("distributor",))
    raw["signals"][0]["confidence"] = confidence
    with pytest.raises(SignalValidationError, match="confidence"):
        validate_business_signal_analysis(item, raw)


def test_repeated_evidence_for_one_signal_counts_once():
    item = company(company_description="We distribute food.")
    raw = response(item, ("distributor",), evidence_count=3)
    analysis = validate_business_signal_analysis(item, raw)
    assert score_business_signals(analysis) == 16.7


@pytest.mark.parametrize(("count", "expected"), [
    (0, 0.0), (1, 16.7), (2, 33.3), (3, 50.0),
    (4, 66.7), (5, 83.3), (6, 100.0),
])
def test_business_signal_score_is_confirmed_signal_ratio(count, expected):
    item = company(company_description="Public company text supplied.")
    raw = response(item, SIGNAL_NAMES[:count])
    analysis = validate_business_signal_analysis(item, raw)
    assert score_business_signals(analysis) == expected


def test_scorer_ignores_unknown_signals_even_for_an_invalid_analysis_object():
    analysis = BusinessSignalAnalysis(
        company_name="Example",
        analysis_status="completed",
        provider="mock",
        signals=(BusinessSignal(
            name="purchase_probability",
            detected=True,
            evidence=(BusinessSignalEvidence("company_description", "some quote"),),
            confidence=1.0,
        ),),
    )
    assert score_business_signals(analysis) == 0.0


def test_rules_provider_uses_public_text_and_emits_verifiable_evidence():
    item = company(
        website="https://example.test",
        company_description="Regional distributor and importer serving overseas markets.",
    )
    analysis = analyze_business_signals(item, RulesBusinessSignalProvider())
    detected = {signal.name for signal in analysis.signals if signal.detected}
    assert detected == {"distributor", "importer", "international_business"}
    assert all(signal.evidence for signal in analysis.signals if signal.detected)
    assert score_business_signals(analysis) == 50.0


def test_rules_provider_does_not_treat_simple_negation_as_an_activity():
    item = company(company_description="We do not import products. We are not a distributor.")
    analysis = analyze_business_signals(item, RulesBusinessSignalProvider())
    assert not any(signal.detected for signal in analysis.signals)


def test_website_url_alone_never_produces_detected_signal():
    item = company(website="https://example.test")
    analysis = analyze_business_signals(item, RulesBusinessSignalProvider())
    assert analysis.analysis_status == "insufficient_input"
    assert not any(signal.detected for signal in analysis.signals)
    assert score_business_signals(analysis) == 0.0


def test_website_url_only_does_not_call_a_provider_or_accept_its_claims():
    item = company(website="https://example.test")
    claimed = {
        "analysis_status": "completed",
        "signals": [
            {
                "name": name,
                "detected": name == "distributor",
                "evidence": ([{
                    "source_type": "website_content",
                    "quote": "https://example.test",
                }] if name == "distributor" else []),
                "confidence": 1.0 if name == "distributor" else 0.0,
            }
            for name in SIGNAL_NAMES
        ],
    }

    class ShouldNotBeCalledProvider(MockBusinessSignalProvider):
        def analyze(self, company):
            raise AssertionError("provider must not run without public text")

    analysis = analyze_business_signals(item, ShouldNotBeCalledProvider(claimed))
    assert analysis.analysis_status == "insufficient_input"
    assert not any(signal.detected for signal in analysis.signals)


def test_mock_provider_is_injected_and_validated():
    item = company(website_content="A wholesaler serving Singapore.")
    provider = MockBusinessSignalProvider(response(item, ("wholesaler",)))
    analysis = analyze_business_signals(item, provider)
    assert analysis.provider == "mock"
    assert score_business_signals(analysis) == pytest.approx(16.7)


def test_ai_path_does_not_overwrite_manual_csv_signals_or_default_v01_score(tmp_path):
    path = tmp_path / "companies.csv"
    path.write_text(
        "name,country,industry,employees,product_categories,website,business_signals,company_description\n"
        "Manual,SG,Food,12,tea,https://example.test,retailer,We distribute tea.\n",
        encoding="utf-8",
    )
    loaded = load_companies(path)[0]
    assert loaded.business_signals == ("retailer",)
    baseline = analyze_companies([loaded], DiscoveryCriteria())[0]
    ai_result = analyze_companies(
        [loaded], DiscoveryCriteria(),
        business_signal_provider=RulesBusinessSignalProvider(),
    )[0]
    assert baseline["score_components"]["business_signal"] == 43
    assert ai_result["company"].business_signals == ("retailer",)
    assert ai_result["business_signal_analysis"].provider == "rules"


def test_rules_mode_does_not_change_non_business_fit_components(tmp_path):
    path = tmp_path / "companies.csv"
    path.write_text(
        "name,country,industry,employees,product_categories,operating_markets,company_description\n"
        "Target,SG,Food,300,tea;coffee,SG;MY,We distribute tea.\n",
        encoding="utf-8",
    )
    item = load_companies(path)
    criteria = DiscoveryCriteria(product_categories=("tea", "coffee"), target_markets=("SG",))
    baseline = analyze_companies(item, criteria)[0]["score_components"]
    opt_in = analyze_companies(
        item, criteria, business_signal_provider=RulesBusinessSignalProvider()
    )[0]["score_components"]
    for key in ("product_fit", "company_fit", "market_fit"):
        assert opt_in[key] == baseline[key]


def test_no_provider_keeps_existing_v01_api_working_without_ai_dependencies():
    item = company(website="https://example.test", business_signals=("importer",))
    result = analyze_companies([item], DiscoveryCriteria())
    assert result[0]["score_components"]["business_signal"] == 43
    assert "business_signal_analysis" not in result[0]


def test_cli_opt_in_rules_mode_prints_validated_signal_score(capsys):
    from pathlib import Path

    csv_path = Path(__file__).resolve().parents[1] / "data" / "sample" / "companies.csv"
    exit_code = main([
        "--csv", str(csv_path), "--country", "Singapore",
        "--industry", "Food Distribution", "--min-employees", "100",
        "--product-category", "plant-based", "--target-market", "Singapore",
        "--business-signal-mode", "rules",
    ])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "B:66.7" in output
    assert "B:50.0" in output

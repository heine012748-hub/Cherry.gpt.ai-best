"""CSV-based B2B customer and partner discovery."""

from importlib import import_module

__all__ = [
    "Company",
    "DiscoveryCriteria",
    "analyze_companies",
    "load_companies",
    "score_company",
    "score_company_components",
    "BusinessSignal",
    "BusinessSignalAnalysis",
    "BusinessSignalEvidence",
    "RulesBusinessSignalProvider",
    "MockBusinessSignalProvider",
    "SignalValidationError",
    "analyze_business_signals",
    "validate_business_signal_analysis",
    "score_business_signals",
    "OpenAIBusinessSignalProvider",
    "OpenAIProviderError",
    "OpenAIConfigurationError",
    "OpenAIResponseError",
    "OpenAIAPIError",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if name in {"score_business_signals"}:
        module = import_module(".business_signal_scoring", __name__)
    elif name in {
        "BusinessSignal", "BusinessSignalAnalysis", "BusinessSignalEvidence",
        "RulesBusinessSignalProvider", "MockBusinessSignalProvider",
        "SignalValidationError", "analyze_business_signals",
        "validate_business_signal_analysis",
    }:
        module = import_module(".business_signal_analyzer", __name__)
    elif name in {
        "OpenAIBusinessSignalProvider", "OpenAIProviderError",
        "OpenAIConfigurationError", "OpenAIResponseError", "OpenAIAPIError",
    }:
        module = import_module(".openai_business_signal_provider", __name__)
    else:
        module = import_module(".company_analyzer", __name__)
    return getattr(module, name)

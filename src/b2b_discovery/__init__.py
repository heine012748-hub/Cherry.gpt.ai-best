"""CSV-based B2B customer and partner discovery."""

from importlib import import_module

__all__ = [
    "Company",
    "DiscoveryCriteria",
    "analyze_companies",
    "load_companies",
    "score_company",
    "score_company_components",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    analyzer = import_module(".company_analyzer", __name__)
    return getattr(analyzer, name)

"""Load, filter, score, and rank companies for B2B discovery."""
from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Company:
    name: str
    country: str
    industry: str
    employees: int
    product_categories: tuple[str, ...]
    website: str = ""
    operating_markets: tuple[str, ...] = ()
    business_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryCriteria:
    countries: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    min_employees: int = 0
    product_categories: tuple[str, ...] = ()
    target_markets: tuple[str, ...] = ()
    target_employee_min: int | None = None
    target_employee_max: int | None = None

    def __post_init__(self) -> None:
        if self.min_employees < 0:
            raise ValueError("min_employees must be non-negative")
        for label, value in (("target_employee_min", self.target_employee_min),
                             ("target_employee_max", self.target_employee_max)):
            if value is not None and value < 0:
                raise ValueError(f"{label} must be non-negative")
        if (self.target_employee_min is not None and self.target_employee_max is not None
                and self.target_employee_min > self.target_employee_max):
            raise ValueError("target_employee_min cannot exceed target_employee_max")


def _split_categories(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.replace("|", ";").split(";") if part.strip())


def load_companies(csv_path: str | Path) -> list[Company]:
    """Load company records from CSV. Categories may be separated by ; or |."""
    companies: list[Company] = []
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"name", "country", "industry", "employees", "product_categories"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            try:
                employees = int(row["employees"])
                if employees < 0:
                    raise ValueError("employees cannot be negative")
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid employees value on CSV line {line_number}: {row.get('employees')!r}"
                ) from exc
            companies.append(Company(
                name=(row.get("name") or "").strip(),
                country=(row.get("country") or "").strip(),
                industry=(row.get("industry") or "").strip(),
                employees=employees,
                product_categories=_split_categories(row.get("product_categories") or ""),
                website=(row.get("website") or "").strip(),
                operating_markets=_split_categories(row.get("operating_markets") or ""),
                business_signals=_split_categories(row.get("business_signals") or ""),
            ))
    return companies


def _matches(value: str, options: Sequence[str]) -> bool:
    return not options or value.casefold() in {option.casefold() for option in options}


def _employee_scale_score(employees: int) -> int:
    """Map organization size to a stable account-capacity tier."""
    if employees < 50:
        return 20
    if employees < 200:
        return 40
    if employees < 500:
        return 60
    if employees < 1000:
        return 80
    return 100


def _company_fit_score(company: Company, criteria: DiscoveryCriteria) -> int:
    lower, upper = criteria.target_employee_min, criteria.target_employee_max
    if lower is None and upper is None:
        return _employee_scale_score(company.employees)
    if lower is not None and company.employees < lower:
        return round(100 * company.employees / lower) if lower else 100
    if upper is not None and company.employees > upper:
        return round(100 * upper / company.employees) if company.employees else 100
    return 100


def _market_fit_score(company: Company, criteria: DiscoveryCriteria) -> int:
    targets = {market.casefold() for market in criteria.target_markets}
    active_markets = {market.casefold() for market in company.operating_markets}
    return round(100 * len(targets & active_markets) / len(targets)) if targets else 100


_SIGNAL_PATTERNS = {
    "distributor": r"\b(distributor|distribution)\b",
    "importer": r"\b(importer|importing|imports)\b",
    "wholesaler": r"\b(wholesaler|wholesale)\b",
    "retailer": r"\b(retailer|retail)\b",
    "exporter": r"\b(exporter|exporting|exports)\b",
    "international": r"\b(international|overseas|global)\b",
    "trader": r"\b(trader|trading|trade)\b",
}


def _business_signal_score(company: Company) -> int:
    """Score public activity evidence; a website alone is weak evidence."""
    public_text = " ".join((company.industry, *company.business_signals)).casefold()
    signals = {
        label for label, pattern in _SIGNAL_PATTERNS.items()
        if re.search(pattern, public_text)
    }
    trade_activity = min(len(signals), 3) / 3 * 85
    website_presence = 15 if company.website.strip() else 0
    return round(trade_activity + website_presence)


_SCORE_WEIGHTS = {
    "product_fit": 60,
    "company_fit": 40,
    "market_fit": 30,
    "business_signal": 20,
}


def score_company_components(
    company: Company, criteria: DiscoveryCriteria
) -> dict[str, int]:
    """Return available 0–100 heuristic components for a prospect.

    Product and market components are omitted when the user did not specify
    those targets. The remaining component weights are normalized by the caller.
    """
    components = {
        "company_fit": _company_fit_score(company, criteria),
        "business_signal": _business_signal_score(company),
    }
    if criteria.product_categories:
        requested = {item.casefold() for item in criteria.product_categories}
        offered = {item.casefold() for item in company.product_categories}
        components["product_fit"] = round(
            100 * len(requested & offered) / len(requested)
        )
    if criteria.target_markets:
        components["market_fit"] = _market_fit_score(company, criteria)
    return components


def _weighted_priority_score(components: dict[str, int]) -> int:
    total_weight = sum(_SCORE_WEIGHTS[name] for name in components)
    weighted_total = sum(
        components[name] * _SCORE_WEIGHTS[name] for name in components
    )
    return round(weighted_total / total_weight)


def score_company(company: Company, criteria: DiscoveryCriteria) -> int:
    """Combine available heuristic components into a 0–100 priority score."""
    return _weighted_priority_score(score_company_components(company, criteria))

def analyze_companies(
    companies: Iterable[Company], criteria: DiscoveryCriteria
) -> list[dict[str, object]]:
    """Filter by all supplied criteria, score matches, and sort descending."""
    requested_categories = {item.casefold() for item in criteria.product_categories}
    results: list[dict[str, object]] = []
    for company in companies:
        if not _matches(company.country, criteria.countries):
            continue
        if not _matches(company.industry, criteria.industries):
            continue
        if company.employees < criteria.min_employees:
            continue
        if requested_categories and not requested_categories.intersection(
            item.casefold() for item in company.product_categories
        ):
            continue
        components = score_company_components(company, criteria)
        results.append({
            "company": company,
            "score": _weighted_priority_score(components),
            "score_components": components,
        })
    return sorted(
        results,
        key=lambda result: (-int(result["score"]), str(result["company"].name).casefold()),
    )


def _csv_values(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find and rank B2B prospects from a company CSV.")
    parser.add_argument("--csv", default="data/sample/companies.csv", help="Company CSV path")
    parser.add_argument("--country", default="", help="Comma-separated countries")
    parser.add_argument("--industry", default="", help="Comma-separated industries")
    parser.add_argument("--min-employees", type=int, default=0)
    parser.add_argument("--product-category", default="", help="Comma-separated product categories")
    parser.add_argument("--target-market", default="", help="Comma-separated target markets for Market Fit")
    parser.add_argument("--target-employees-min", type=int, default=None, help="Lower edge of ideal account-size range")
    parser.add_argument("--target-employees-max", type=int, default=None, help="Upper edge of ideal account-size range")
    args = parser.parse_args(argv)
    if args.min_employees < 0:
        parser.error("--min-employees must be non-negative")
    if args.target_employees_min is not None and args.target_employees_min < 0:
        parser.error("--target-employees-min must be non-negative")
    if args.target_employees_max is not None and args.target_employees_max < 0:
        parser.error("--target-employees-max must be non-negative")
    if (args.target_employees_min is not None and args.target_employees_max is not None
            and args.target_employees_min > args.target_employees_max):
        parser.error("--target-employees-min cannot exceed --target-employees-max")
    criteria = DiscoveryCriteria(
        countries=_csv_values(args.country),
        industries=_csv_values(args.industry),
        min_employees=args.min_employees,
        product_categories=_csv_values(args.product_category),
        target_markets=_csv_values(args.target_market),
        target_employee_min=args.target_employees_min,
        target_employee_max=args.target_employees_max,
    )
    results = analyze_companies(load_companies(args.csv), criteria)
    if not results:
        print("No matching companies found.")
        return 0
    print(f"{'Score':>5}  {'Company':<28} {'Country':<16} {'Industry':<22} {'Employees':<9} Fit (P/C/M/B)")
    for result in results:
        company = result["company"]
        assert isinstance(company, Company)
        parts = result["score_components"]
        assert isinstance(parts, dict)
        labels = (("product_fit", "P"), ("company_fit", "C"),
                  ("market_fit", "M"), ("business_signal", "B"))
        detail = " ".join(
            f"{label}:{parts[key]}" for key, label in labels if key in parts
        )
        print(
            f"{result['score']:>5}  {company.name:<28} {company.country:<16} "
            f"{company.industry:<22} {company.employees:<8} {detail}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

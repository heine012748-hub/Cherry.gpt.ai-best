"""Load, filter, score, and rank companies for B2B discovery."""
from __future__ import annotations

import argparse
import csv
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


@dataclass(frozen=True)
class DiscoveryCriteria:
    countries: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    min_employees: int = 0
    product_categories: tuple[str, ...] = ()


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


def score_company(company: Company, criteria: DiscoveryCriteria) -> int:
    """Rank a filter-qualified prospect by product fit (60%) and account scale (40%).

    Product fit is the share of requested categories the company offers. When no
    product categories were requested, account scale is the full score. Country,
    industry, minimum employees, and at-least-one category overlap are eligibility
    filters, so they do not earn points again.
    """
    requested = {item.casefold() for item in criteria.product_categories}
    if not requested:
        return _employee_scale_score(company.employees)

    offered = {item.casefold() for item in company.product_categories}
    category_fit = 100 * len(requested.intersection(offered)) / len(requested)
    size_fit = _employee_scale_score(company.employees)
    return round(0.60 * category_fit + 0.40 * size_fit)

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
        results.append({"company": company, "score": score_company(company, criteria)})
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
    args = parser.parse_args(argv)
    if args.min_employees < 0:
        parser.error("--min-employees must be non-negative")
    criteria = DiscoveryCriteria(
        countries=_csv_values(args.country),
        industries=_csv_values(args.industry),
        min_employees=args.min_employees,
        product_categories=_csv_values(args.product_category),
    )
    results = analyze_companies(load_companies(args.csv), criteria)
    if not results:
        print("No matching companies found.")
        return 0
    print(f"{'Score':>5}  {'Company':<28} {'Country':<16} {'Industry':<22} Employees")
    for result in results:
        company = result["company"]
        assert isinstance(company, Company)
        print(
            f"{result['score']:>5}  {company.name:<28} {company.country:<16} "
            f"{company.industry:<22} {company.employees}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

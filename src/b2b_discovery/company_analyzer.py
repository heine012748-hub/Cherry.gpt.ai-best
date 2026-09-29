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


def score_company(company: Company, criteria: DiscoveryCriteria) -> int:
    """Score a company from 0–100: country 30, industry 30, size 20, category 20."""
    requested = {item.casefold() for item in criteria.product_categories}
    offered = {item.casefold() for item in company.product_categories}
    return (
        (30 if not criteria.countries or _matches(company.country, criteria.countries) else 0)
        + (30 if not criteria.industries or _matches(company.industry, criteria.industries) else 0)
        + (20 if company.employees >= criteria.min_employees else 0)
        + (20 if not requested or requested.intersection(offered) else 0)
    )


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

"""Example: discover Singapore food distributors with a product fit."""
from pathlib import Path

from b2b_discovery import DiscoveryCriteria, analyze_companies, load_companies


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    companies = load_companies(repo_root / "data" / "sample" / "companies.csv")
    criteria = DiscoveryCriteria(
        countries=("Singapore",),
        industries=("Food Distribution",),
        min_employees=100,
        product_categories=("plant-based foods",),
    )
    for result in analyze_companies(companies, criteria):
        company = result["company"]
        print(f'{result["score"]:3}  {company.name} ({company.employees} employees)')


if __name__ == "__main__":
    main()

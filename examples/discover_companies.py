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
        target_markets=("Singapore", "Malaysia"),
        target_employee_min=100,
        target_employee_max=500,
    )
    for result in analyze_companies(companies, criteria):
        company = result["company"]
        components = result["score_components"]
        print(
            f'{result["score"]:3}  {company.name} ({company.employees} employees) '
            f'P:{components.get("product_fit", "-")} '
            f'C:{components["company_fit"]} '
            f'M:{components.get("market_fit", "-")} '
            f'B:{components["business_signal"]}'
        )


if __name__ == "__main__":
    main()

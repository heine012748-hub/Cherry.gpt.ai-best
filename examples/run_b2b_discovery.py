"""Run the v0.1 Singapore plant-based B2B discovery example."""
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from b2b_discovery.company_analyzer import main


def run() -> int:
    """Analyze the bundled sample data with the README's example criteria."""
    return main(
        [
            "--csv", str(REPO_ROOT / "data" / "sample" / "companies.csv"),
            "--country", "Singapore",
            "--industry", "Food Distribution",
            "--product-category", "plant-based",
            "--min-employees", "100",
            "--target-market", "Singapore",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(run())

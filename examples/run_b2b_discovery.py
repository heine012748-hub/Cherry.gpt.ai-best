"""Run the v0.1 Singapore plant-based B2B discovery example."""
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from b2b_discovery.company_analyzer import main


def run(argv: list[str] | None = None) -> int:
    """Analyze bundled sample data; extra arguments are passed to the CLI."""
    args = [
        "--csv", str(REPO_ROOT / "data" / "sample" / "companies.csv"),
        "--country", "Singapore",
        "--industry", "Food Distribution",
        "--product-category", "plant-based",
        "--min-employees", "100",
        "--target-market", "Singapore",
    ]
    args.extend(sys.argv[1:] if argv is None else argv)
    return main(
        args
    )


if __name__ == "__main__":
    raise SystemExit(run())

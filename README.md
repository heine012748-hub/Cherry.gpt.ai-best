# Cherry.gpt.ai-best — B2B Discovery v0.1

## Project

Cherry.gpt.ai-best is a broader global business and data project. Version 0.1
implements a CSV-based B2B Customer & Partner Discovery workflow: load company
records, filter eligible candidates, calculate a transparent B2B Priority Score,
and rank prospects for an initial outreach review.

Global market research, e-commerce analysis, consumer/VOC analysis, and
strategy generation are future project areas; they are not implemented in v0.1.

## Implemented in v0.1

- Load company records from CSV.
- Filter by country, industry, minimum employees, and product category.
- Score candidates across Product Fit, Company Fit, Market Fit, and Business
  Signal, then sort by total priority score.
- Print the score components and company website in the CLI.
- Run a ready-to-use Singapore sample with one command.

## Install

Clone the repository and change into its directory. Python 3.10 or newer is
recommended.

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run

From the repository root, run the included example:

```bash
python examples/run_b2b_discovery.py
```

The example loads `data/sample/companies.csv` and applies:

- Country: Singapore
- Industry: Food Distribution
- Product Category: plant-based
- Minimum Employees: 100
- Target Market: Singapore

To choose different criteria or a different CSV, use the CLI directly:

```bash
PYTHONPATH=src python -m b2b_discovery.company_analyzer --csv data/sample/companies.csv --country Singapore --industry "Food Distribution" --product-category plant-based --min-employees 100 --target-market Singapore
```

In Windows PowerShell, set the source path before running that command:

```powershell
$env:PYTHONPATH = "src"
python -m b2b_discovery.company_analyzer --csv data/sample/companies.csv --country Singapore --industry "Food Distribution" --product-category plant-based --min-employees 100 --target-market Singapore
```

The CLI prints candidates in descending Priority Score order. Component
abbreviations are `P` Product Fit, `C` Company Fit, `M` Market Fit, and
`B` Business Signal.

## Input data

The CSV must include these columns:

| Column | Required | Meaning |
| --- | --- | --- |
| `name` | Yes | Company name |
| `country` | Yes | Company's country; used by the country filter |
| `industry` | Yes | Industry label; used by the industry filter and business-signal scan |
| `employees` | Yes | Non-negative employee count |
| `product_categories` | Yes | Semicolon- or pipe-separated categories handled by the company |
| `website` | No | Public company website |
| `operating_markets` | No | Semicolon- or pipe-separated markets where it operates |
| `business_signals` | No | Semicolon- or pipe-separated public activity tags, such as importer or exporter |

The original five required columns remain valid; the three additional columns
are optional. See `data/sample/companies.csv` for a complete example.

## Candidate Filter

Filtering determines eligibility before scoring:

- Country and industry, when provided, must match the company's values
  (case-insensitive).
- Employees must be at least the requested minimum.
- At least one requested product category must match. Matching is
  case-insensitive; a requested parent label such as `plant-based` also
  matches a more specific label such as `plant-based foods`.
- All supplied filters are applied together.

Target Market is a scoring input, not a hard filter. A company can remain a
candidate with zero Market Fit if it has no listed activity in the requested
market.

## B2B Priority Score

Priority Score is a 0–100 **heuristic for ordering outreach candidates**. It
uses the available company data and configured targets. It is not a model of
purchase likelihood, buying intent, or purchase probability.

Each active component is scored from 0 to 100:

- **Product Fit** — percentage of requested product categories handled by the
  company.
- **Company Fit** — when no target size is supplied, employee tiers score 20
  below 50 employees, 40 for 50–199, 60 for 200–499, 80 for 500–999, and 100
  for 1,000 or more. Optional `--target-employees-min` and
  `--target-employees-max` bounds give 100 within the target range and reduce
  the score in proportion to the distance outside it.
- **Market Fit** — percentage of requested target markets listed in
  `operating_markets`.
- **Business Signal** — recognizes distributor/distribution, importer,
  wholesaler, retailer, exporter, international/overseas/global, and
  trading-related terms in `industry` and `business_signals`. Up to three
  distinct activity types contribute 85 points; a non-empty website adds up
  to 15 points. A website alone is weak public-presence evidence, not proof of
  a commercial signal.

The base weights are Product Fit 60, Company Fit 40, Market Fit 30, and
Business Signal 20. If all four components are active, normalization makes
their effective weights 40%, 26.7%, 20%, and 13.3%. The final score is:

```
round(sum(component_score × active_base_weight) / sum(active_base_weights))
```

Product Fit is omitted when no product category is requested; Market Fit is
omitted when no target market is requested. The other available components are
renormalized to a 100-point total. Scores are rounded to the nearest integer,
and ties are sorted by company name.

## Sample execution

Run:

```bash
python examples/run_b2b_discovery.py
```

Actual output from the included sample CSV:

```text
Score  Company                      Country          Industry               Employees Fit (P/C/M/B)  Website
   89  Orchid Foods                 Singapore        Food Distribution      240      P:100 C:60 M:100 B:100  https://orchid.example
   80  Straits Food Partners        Singapore        Food Distribution      180      P:100 C:40 M:100 B:72   https://straits.example
```

For example, Orchid Foods scores
`round((100×60 + 60×40 + 100×30 + 100×20) / 150) = 89`. These values are
calculated from the CSV at runtime; they are not hard-coded in the example.

## Verify

Install the test dependency with the other requirements, then run:

```bash
pytest
```

## Limitations

- The included data is illustrative, not a verified or exhaustive company list.
- Employee count is a coarse proxy for account size; the default tiers are
  configurable heuristics, not calibrated sales outcomes.
- Market and business signals depend on user-supplied CSV data. Missing or
  stale data can lower or distort rankings.
- Business-signal detection uses a small keyword list and cannot understand
  context or verify claims on a company's website.
- A high score only means the available fields align with the chosen criteria.
  Validate prospects and their current activity before outreach.

## License

MIT License

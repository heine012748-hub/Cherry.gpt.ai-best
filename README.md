# Cherry.gpt.ai-best — B2B Discovery v0.2

## Project

Cherry.gpt.ai-best is a broader global business and data project. Version 0.1
implements a CSV-based B2B Customer & Partner Discovery workflow: load company
records, filter eligible candidates, calculate a transparent B2B Priority Score,
and rank prospects for an initial outreach review. v0.2 adds an optional,
evidence-validated Business Signal analysis layer while retaining v0.1 as the
default behavior.

Global market research, e-commerce analysis, consumer/VOC analysis, and
strategy generation are future project areas; they are not implemented in v0.1.

## Implemented

- Load company records from CSV.
- Filter by country, industry, minimum employees, and product category.
- Score candidates across Product Fit, Company Fit, Market Fit, and Business
  Signal, then sort by total priority score.
- Print the score components and company website in the CLI.
- Run a ready-to-use Singapore sample with one command.
- Optionally analyze supplied public company text for six structured business
  activity signals using an offline rules provider or an injected provider.
- Validate provider evidence against the supplied source text and calculate a
  deterministic Business Signal Score separately from analysis.

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
python examples/run_b2b_discovery.py --country Singapore --industry "Food Distribution" --product-category plant-based --min-employees 100 --target-market Singapore
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
| `company_description` | No | Public company description supplied as analysis evidence |
| `business_type` | No | Public business type supplied as analysis evidence |
| `website_content` | No | Public website text supplied as evidence; the URL alone is not evidence |

The original five required columns remain valid; all additional columns are
optional. Existing `business_signals` values are preserved as manual CSV data
and are not overwritten by analysis. See `data/sample/companies.csv` for the
current sample schema.

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

### Optional v0.2 Business Signal Analysis

The default CLI and Python API continue to use the v0.1 deterministic score.
To opt into the new evidence-based scoring path with the offline rules
provider, run:

```bash
python examples/run_b2b_discovery.py --business-signal-mode rules
```

The rules provider analyzes only `company_description`, `business_type`, and
`website_content`; `website` URL and manually entered `business_signals` are
not analysis evidence. A future LLM adapter can implement the same provider
interface. No LLM SDK or API key is required. Provider output contains
structured signals and evidence only; it cannot return or override a score.
Validation requires exactly these six names: `distributor`, `importer`,
`wholesaler`, `retailer`, `exporter`, and `international_business`. Confidence
must be in `[0, 1]`, and each detected signal must cite a quote present in its
supplied source text. Confidence describes how strongly the analyzer considers
the supplied evidence to support a classification; it is not multiplied into
the score and is not purchase probability.

The v0.2 Business Signal Score is the percentage of distinct signals confirmed
with at least one valid evidence item:

```text
confirmed distinct signals / 6 × 100
```

The score is rounded to one decimal place. Duplicate evidence for the same
signal counts once; confidence does not affect the score. Without text input,
analysis is `insufficient_input` and the score is zero. In `rules` mode this
score feeds the existing Business Signal component (base weight 20), followed
by the existing normalized Priority Score calculation. Without explicit
`--business-signal-mode rules`, existing v0.1 scoring and CLI behavior remain
unchanged.

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

Run the optional evidence-based rules mode against the same sample:

```bash
python examples/run_b2b_discovery.py --business-signal-mode rules
```

Actual rules-mode output:

```text
Score  Company                      Country          Industry               Employees Fit (P/C/M/B)  Website
   85  Orchid Foods                 Singapore        Food Distribution      240      P:100 C:60 M:100 B:66.7 https://orchid.example
   77  Straits Food Partners        Singapore        Food Distribution      180      P:100 C:40 M:100 B:50.0 https://straits.example
```

The v0.1 example above uses the unchanged default path. The rules-mode values
come from the supplied `company_description`, `business_type`, and
`website_content` fields.

## Verify

Install the test dependency with the other requirements, then run:

```bash
pytest
```

The v0.2 review test run completed with **41 passed**.

## Limitations

- The included data is illustrative, not a verified or exhaustive company list.
- Employee count is a coarse proxy for account size; the default tiers are
  configurable heuristics, not calibrated sales outcomes.
- Market and business signals depend on user-supplied CSV data. Missing or
  stale data can lower or distort rankings.
- Business-signal detection uses a small keyword list and cannot understand
  context or verify claims on a company's website. v0.2 checks only supplied
  public text; it does not fetch or independently verify websites.
- A high score only means the available fields align with the chosen criteria.
  Validate prospects and their current activity before outreach.

Business Signal and Priority Score are heuristic indicators for prioritizing
outreach based on available business information. They do not predict purchase
intent, purchase probability, or actual customer conversion.

## License

MIT License

# Cherry.gpt.ai-best

## Introduction

This project combines global business, AI, and data to analyze
markets, identify customer needs, and discover new business
opportunities.

## Key Features

### 1. Global Market Analysis

- Analyze market size, growth trends, and country-level opportunities
- Compare major markets and competitors
- Outputs: Market research reports, country comparison tables,
  and market opportunity analysis

### 2. B2B Customer & Partner Discovery

- Identify potential customers and business partners
- Research and segment companies and buyers
- Analyze customer needs and business opportunities
- Outputs: Potential customer lists, company/buyer databases,
  and customer segments
- Implemented: load company records from CSV, filter by country,
  industry, minimum employee count, and product category, then score
  and rank matching companies from 0 to 100

### 3. E-commerce Analysis

- Analyze global e-commerce platforms and local digital channels
- Compare products, pricing, and competitors
- Identify consumer trends and channel opportunities
- Outputs: Competitive product analysis, channel comparison reports,
  and e-commerce insights

### 4. AI/LLM-Based Consumer Analysis

- Preprocess and analyze consumer review data
- Use LLMs to classify and structure Voice of Customer (VOC)
- Identify key consumer opinions, keywords, and response patterns
- Outputs: Structured VOC datasets, consumer insights,
  and data visualizations

### 5. Data-Driven Strategy Development

- Integrate market, customer, and consumer data
- Identify key problems and business opportunities
- Develop actionable strategies based on data-driven insights
- Outputs: Key insights, strategic recommendations, and action plans

## How It Works

### Problem

Finding suitable overseas customers and business partners
requires collecting and comparing information from multiple
sources.

### Input

The project uses company and market information such as:

- Country
- Industry
- Company size
- Target market
- Product category

### Processing

The B2B discovery implementation first filters CSV records by any
specified country, industry, minimum employee count, and product
category. These are eligibility checks and do not award points again.
It then ranks eligible prospects by requested-category coverage (60%)
and an employee-size tier score (40%). Category coverage is the share
of requested categories offered by the company. Employee-size tiers
score 20 points below 50 employees, 40 for 50–199, 60 for 200–499,
80 for 500–999, and 100 for 1,000 or more. Scores are rounded to the
nearest integer and sorted highest first. When no product categories
are requested, the employee-size tier is used as the full score.
Country, industry, and employee count are useful prioritization proxies;
they do not establish buying intent. Text matching is case-insensitive.
CSV product categories may be separated by semicolons or pipes.

### Output

The analysis produces:

- Potential customer lists
- Company segments
- Market comparison tables
- Business opportunity insights

### Example

For example:

**Input**

- Country: Singapore
- Industry: Food Distribution
- Minimum employees: 100

**Output**

- Potential B2B partner list
- Company information
- Partner relevance

## How to Use

Install the test dependency:

```bash
pip install -r requirements.txt
```

Run the sample discovery (filters may be omitted):

```PYTHONPATH=src python examples/discover_companies.py
PYTHONPATH=src python -m b2b_discovery.company_analyzer --csv data/sample/companies.csv --country Singapore --industry "Food Distribution" --min-employees 100 --product-category "plant-based foods"
```

Run the tests from the repository root:

```PYTHONPATH=src pytest
```

The CSV requires `name`, `country`, `industry`, `employees`, and
`product_categories` columns. An optional `website` column is also
supported. The included sample data is illustrative.

## License

MIT License

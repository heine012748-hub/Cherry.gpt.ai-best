from b2b_discovery.company_analyzer import Company, DiscoveryCriteria, analyze_companies, load_companies


def sample_companies():
    return [
        Company("Beta Foods", "Singapore", "Food Distribution", 250, ("snacks", "plant-based")),
        Company("Alpha Foods", "Singapore", "Food Distribution", 150, ("plant-based",)),
        Company("Small Foods", "Singapore", "Food Distribution", 50, ("plant-based",)),
        Company("Tokyo Foods", "Japan", "Food Distribution", 500, ("plant-based",)),
    ]


def test_load_companies_parses_rows_and_categories(tmp_path):
    path = tmp_path / "companies.csv"
    path.write_text(
        "name,country,industry,employees,product_categories,website\n"
        "Example,Japan,Food,12,tea;snacks,https://example.test\n",
        encoding="utf-8",
    )
    assert load_companies(path)[0] == Company(
        "Example", "Japan", "Food", 12, ("tea", "snacks"), "https://example.test"
    )


def test_load_companies_rejects_invalid_employee_count(tmp_path):
    path = tmp_path / "companies.csv"
    path.write_text(
        "name,country,industry,employees,product_categories\nExample,Japan,Food,unknown,tea\n",
        encoding="utf-8",
    )
    try:
        load_companies(path)
    except ValueError as exc:
        assert "line 2" in str(exc)
    else:
        raise AssertionError("invalid employee count should fail")


def test_filters_by_criteria_and_sorts_ties_alphabetically():
    criteria = DiscoveryCriteria(
        countries=("singapore",), industries=("Food Distribution",),
        min_employees=100, product_categories=("PLANT-BASED",),
    )
    results = analyze_companies(sample_companies(), criteria)
    assert [row["company"].name for row in results] == ["Alpha Foods", "Beta Foods"]
    assert [row["score"] for row in results] == [100, 100]


def test_unspecified_dimensions_do_not_reduce_score():
    results = analyze_companies(sample_companies(), DiscoveryCriteria(min_employees=100))
    assert [row["company"].name for row in results] == ["Alpha Foods", "Beta Foods", "Tokyo Foods"]
    assert all(row["score"] == 100 for row in results)


def test_category_is_a_filter_when_requested():
    results = analyze_companies(
        sample_companies(), DiscoveryCriteria(product_categories=("snacks",))
    )
    assert [row["company"].name for row in results] == ["Beta Foods"]


def test_empty_results_are_allowed():
    assert analyze_companies(
        sample_companies(), DiscoveryCriteria(countries=("Canada",))
    ) == []

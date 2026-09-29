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


def test_filters_eligibility_then_ranks_by_product_fit_and_company_scale():
    criteria = DiscoveryCriteria(
        countries=("singapore",), industries=("Food Distribution",),
        min_employees=100, product_categories=("PLANT-BASED", "snacks"),
    )
    results = analyze_companies(sample_companies(), criteria)
    assert [row["company"].name for row in results] == ["Beta Foods", "Alpha Foods"]
    # Beta covers both requested categories; Alpha covers one and is in a
    # smaller employee-size tier.
    assert [row["score"] for row in results] == [84, 46]


def test_unrequested_category_dimension_uses_employee_scale_score():
    results = analyze_companies(sample_companies(), DiscoveryCriteria(min_employees=100))
    assert [row["company"].name for row in results] == ["Tokyo Foods", "Beta Foods", "Alpha Foods"]
    assert [row["score"] for row in results] == [80, 60, 40]


def test_category_is_an_eligibility_filter_and_still_scores_qualified_companies():
    results = analyze_companies(
        sample_companies(), DiscoveryCriteria(product_categories=("snacks",))
    )
    assert [row["company"].name for row in results] == ["Beta Foods"]
    assert results[0]["score"] == 84


def test_empty_results_are_allowed():
    assert analyze_companies(
        sample_companies(), DiscoveryCriteria(countries=("Canada",))
    ) == []


def test_partial_category_coverage_changes_fit_score():
    criteria = DiscoveryCriteria(product_categories=("plant-based", "snacks", "beverages"))
    results = analyze_companies(sample_companies(), criteria)
    by_name = {row["company"].name: row["score"] for row in results}
    # Beta matches 2/3 requested categories; the other eligible companies
    # match 1/3, with employee scale separating their priority.
    assert by_name == {
        "Beta Foods": 64, "Alpha Foods": 36, "Small Foods": 28, "Tokyo Foods": 52
    }
    assert [row["score"] for row in results] == [64, 52, 36, 28]


def test_employee_size_tiers_distinguish_candidates_without_product_filter():
    criteria = DiscoveryCriteria(countries=("Singapore",), min_employees=100)
    results = analyze_companies(sample_companies(), criteria)
    assert [row["score"] for row in results] == [60, 40]

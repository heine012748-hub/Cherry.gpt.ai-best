import subprocess
import sys

from b2b_discovery.company_analyzer import (
    Company,
    DiscoveryCriteria,
    analyze_companies,
    load_companies,
    score_company_components,
    main,
)


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
        "name,country,industry,employees,product_categories,website,operating_markets,business_signals\n"
        "Example,Japan,Food,12,tea;snacks,https://example.test,Japan|Korea,importer;wholesaler\n",
        encoding="utf-8",
    )
    assert load_companies(path)[0] == Company(
        "Example", "Japan", "Food", 12, ("tea", "snacks"), "https://example.test",
        ("Japan", "Korea"), ("importer", "wholesaler"),
    )


def test_load_companies_keeps_original_csv_schema_compatible(tmp_path):
    path = tmp_path / "companies.csv"
    path.write_text(
        "name,country,industry,employees,product_categories\nExample,Japan,Food,12,tea\n",
        encoding="utf-8",
    )
    assert load_companies(path)[0].operating_markets == ()
    assert load_companies(path)[0].business_signals == ()


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
    assert [row["score"] for row in results] == [75, 43]
    assert set(results[0]["score_components"]) == {
        "product_fit", "company_fit", "business_signal"
    }


def test_unrequested_category_dimension_uses_employee_scale_score():
    results = analyze_companies(sample_companies(), DiscoveryCriteria(min_employees=100))
    assert [row["company"].name for row in results] == ["Tokyo Foods", "Beta Foods", "Alpha Foods"]
    assert [row["score"] for row in results] == [63, 49, 36]
    assert all("market_fit" not in row["score_components"] for row in results)


def test_category_is_an_eligibility_filter_and_still_scores_qualified_companies():
    results = analyze_companies(
        sample_companies(), DiscoveryCriteria(product_categories=("snacks",))
    )
    assert [row["company"].name for row in results] == ["Beta Foods"]
    assert results[0]["score"] == 75


def test_empty_results_are_allowed():
    assert analyze_companies(
        sample_companies(), DiscoveryCriteria(countries=("Canada",))
    ) == []


def test_partial_category_coverage_changes_fit_score():
    criteria = DiscoveryCriteria(product_categories=("plant-based", "snacks", "beverages"))
    results = analyze_companies(sample_companies(), criteria)
    by_name = {row["company"].name: row["score"] for row in results}
    assert by_name == {
        "Beta Foods": 58, "Alpha Foods": 34, "Small Foods": 34, "Tokyo Foods": 48
    }
    assert [row["score"] for row in results] == [58, 48, 34, 34]


def test_target_market_coverage_is_scored_but_does_not_filter_candidates():
    local = Company(
        "Local", "Japan", "Food Manufacturing", 250, (), "", ("Singapore",), ()
    )
    absent = Company(
        "Absent", "Japan", "Food Manufacturing", 250, (), "", ("Japan",), ()
    )
    results = analyze_companies(
        [local, absent], DiscoveryCriteria(target_markets=("Singapore", "Malaysia"))
    )
    assert len(results) == 2
    assert results[0]["company"].name == "Local"
    assert results[0]["score_components"]["market_fit"] == 50
    assert results[1]["score_components"]["market_fit"] == 0


def test_business_signal_uses_trade_activity_and_weak_website_evidence():
    sparse = Company("Sparse", "Japan", "Food Manufacturing", 250, (), "https://a.example")
    active = Company(
        "Active", "Japan", "Food Manufacturing", 250, (), "",
        business_signals=("distributor", "importer", "wholesaler"),
    )
    sparse_score = score_company_components(sparse, DiscoveryCriteria())["business_signal"]
    active_score = score_company_components(active, DiscoveryCriteria())["business_signal"]
    assert sparse_score == 15
    assert active_score == 85


def test_target_employee_range_scores_company_size_fit():
    in_range = Company("In Range", "Japan", "Food", 300, ())
    below = Company("Below", "Japan", "Food", 100, ())
    above = Company("Above", "Japan", "Food", 600, ())
    criteria = DiscoveryCriteria(target_employee_min=200, target_employee_max=400)
    assert score_company_components(in_range, criteria)["company_fit"] == 100
    assert score_company_components(below, criteria)["company_fit"] == 50
    assert score_company_components(above, criteria)["company_fit"] == 67


def test_employee_size_tiers_distinguish_candidates_without_product_filter():
    sizes = (49, 50, 199, 200, 499, 500, 999, 1000)
    expected = (20, 40, 40, 60, 60, 80, 80, 100)
    criteria = DiscoveryCriteria()
    assert tuple(
        score_company_components(
            Company(f"Company {employees}", "Japan", "Food Manufacturing", employees, ()),
            criteria,
        )["company_fit"]
        for employees in sizes
    ) == expected


def test_full_priority_score_combines_all_four_components():
    from b2b_discovery.company_analyzer import score_company

    company = Company(
        "Target", "Singapore", "Food Manufacturing", 300,
        ("tea", "coffee"), "https://target.example",
        ("Singapore",), ("distributor", "importer"),
    )
    criteria = DiscoveryCriteria(
        product_categories=("tea", "coffee"),
        target_markets=("Singapore", "Malaysia"),
        target_employee_min=200,
        target_employee_max=400,
    )
    components = score_company_components(company, criteria)
    assert components == {
        "company_fit": 100,
        "business_signal": 72,
        "product_fit": 100,
        "market_fit": 50,
    }
    assert score_company(company, criteria) == 86


def test_parent_product_category_matches_specific_csv_category():
    company = Company(
        "Plant Foods", "Singapore", "Food Distribution", 240,
        ("plant-based foods",), "https://plant.example",
    )
    results = analyze_companies(
        [company], DiscoveryCriteria(product_categories=("plant-based",))
    )
    assert len(results) == 1
    assert results[0]["score_components"]["product_fit"] == 100


def test_cli_prints_actual_ranked_scores_components_and_websites(capsys):
    from pathlib import Path

    csv_path = Path(__file__).resolve().parents[1] / "data" / "sample" / "companies.csv"
    exit_code = main([
        "--csv", str(csv_path),
        "--country", "Singapore",
        "--industry", "Food Distribution",
        "--min-employees", "100",
        "--product-category", "plant-based",
        "--target-market", "Singapore",
    ])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert output.index("Orchid Foods") < output.index("Straits Food Partners")
    assert "89  Orchid Foods" in output
    assert "80  Straits Food Partners" in output
    assert "P:100 C:60 M:100 B:100" in output
    assert "P:100 C:40 M:100 B:72" in output
    assert "https://orchid.example" in output
    assert "https://straits.example" in output


def test_readme_example_script_runs_from_outside_repository_root(tmp_path):
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "examples" / "run_b2b_discovery.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Orchid Foods" in completed.stdout
    assert "Straits Food Partners" in completed.stdout
    assert "P:100 C:60 M:100 B:100" in completed.stdout
    assert "https://orchid.example" in completed.stdout

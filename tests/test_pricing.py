from app.services.pricing import (
    calculate_items_pricing,
    calculate_price_breakdown,
    distribute_final_total_between_items,
    percentage_of_cents,
)


def test_percentage_of_cents():
    assert percentage_of_cents(10000, 50) == 5000


def test_percentage_rounding():
    assert percentage_of_cents(1, 50) == 1


def test_calculate_items_pricing_automatic_and_manual_labor():
    items = [
        {
            "id": 1,
            "glass_total_cents": 10000,
            "manual_labor_cents": None,
        },
        {
            "id": 2,
            "glass_total_cents": 20000,
            "manual_labor_cents": 7000,
        },
    ]

    components = {
        1: [{"total_cents": 2000}],
        2: [{"total_cents": 3000}],
    }

    priced = calculate_items_pricing(
        items,
        components,
    )

    assert priced[0]["components_total_cents"] == 2000
    assert priced[0]["materials_total_cents"] == 12000
    assert priced[0]["automatic_labor_cents"] == 6000
    assert priced[0]["labor_cents"] == 6000
    assert priced[0]["labor_is_manual"] is False
    assert priced[0]["total_cents"] == 18000

    assert priced[1]["materials_total_cents"] == 23000
    assert priced[1]["automatic_labor_cents"] == 11500
    assert priced[1]["labor_cents"] == 7000
    assert priced[1]["labor_is_manual"] is True
    assert priced[1]["total_cents"] == 30000


def test_distribute_final_total_preserves_exact_total():
    items = [
        {"total_cents": 18000},
        {"total_cents": 30000},
    ]

    result = distribute_final_total_between_items(
        items,
        50000,
    )

    assert sum(
        item["commercial_total_cents"]
        for item in result
    ) == 50000


def test_distribute_final_total_with_zero_weights():
    items = [
        {"total_cents": 0},
        {"total_cents": 0},
    ]

    result = distribute_final_total_between_items(
        items,
        10000,
    )

    assert sum(
        item["commercial_total_cents"]
        for item in result
    ) == 10000

    assert result[0]["commercial_total_cents"] == 5000
    assert result[1]["commercial_total_cents"] == 5000


def test_distribute_empty_items():
    assert distribute_final_total_between_items([], 10000) == []


def test_calculate_price_breakdown():
    result = calculate_price_breakdown(
        10000,
        {
            "labor_percentage": 50,
            "difficulty_percentage": 10,
            "discount_percentage": 10,
        },
    )

    assert result == {
        "labor_cents": 5000,
        "difficulty_cents": 1500,
        "discount_cents": 1650,
        "calculated_total_cents": 14850,
    }


def test_calculate_price_breakdown_with_manual_labor():
    result = calculate_price_breakdown(
        10000,
        {
            "labor_percentage": 50,
            "difficulty_percentage": 10,
            "discount_percentage": 0,
        },
        labor_cents=3000,
    )

    assert result["labor_cents"] == 3000
    assert result["difficulty_cents"] == 1300
    assert result["discount_cents"] == 0
    assert result["calculated_total_cents"] == 14300

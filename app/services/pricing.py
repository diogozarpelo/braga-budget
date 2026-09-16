from decimal import Decimal, ROUND_HALF_UP


def percentage_of_cents(base_cents, percentage):
    amount = (
        Decimal(base_cents)
        * Decimal(str(percentage))
        / Decimal("100")
    )

    return int(
        amount.quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def calculate_items_pricing(items, components_by_item):
    priced_items = []

    for item_row in items:
        item = dict(item_row)
        item_components = components_by_item.get(
            item["id"],
            [],
        )
        components_total_cents = sum(
            component["total_cents"]
            for component in item_components
        )
        materials_total_cents = (
            item["glass_total_cents"]
            + components_total_cents
        )
        automatic_labor_cents = percentage_of_cents(
            materials_total_cents,
            50,
        )
        labor_cents = (
            item["manual_labor_cents"]
            if item["manual_labor_cents"] is not None
            else automatic_labor_cents
        )

        item["components_total_cents"] = components_total_cents
        item["materials_total_cents"] = materials_total_cents
        item["automatic_labor_cents"] = automatic_labor_cents
        item["labor_cents"] = labor_cents
        item["labor_is_manual"] = (
            item["manual_labor_cents"] is not None
        )
        item["total_cents"] = (
            materials_total_cents
            + labor_cents
        )
        priced_items.append(item)

    return priced_items


def distribute_final_total_between_items(
    items,
    final_total_cents,
):
    if not items:
        return items

    unit_cents = (
        100
        if final_total_cents % 100 == 0
        else 1
    )
    final_units = final_total_cents // unit_cents
    weights = [
        max(item["total_cents"], 0)
        for item in items
    ]
    total_weight = sum(weights)

    if total_weight == 0:
        weights = [1 for item in items]
        total_weight = len(items)

    allocated_units = []
    remainders = []

    for weight in weights:
        proportional_value = final_units * weight
        allocated_units.append(
            proportional_value // total_weight
        )
        remainders.append(
            proportional_value % total_weight
        )

    remaining_units = (
        final_units
        - sum(allocated_units)
    )
    priority_order = sorted(
        range(len(items)),
        key=lambda index: (
            remainders[index],
            weights[index],
            -index,
        ),
        reverse=True,
    )

    for index in priority_order[:remaining_units]:
        allocated_units[index] += 1

    for index, item in enumerate(items):
        commercial_total_cents = (
            allocated_units[index]
            * unit_cents
        )
        item["commercial_total_cents"] = (
            commercial_total_cents
        )
        item["commercial_adjustment_cents"] = (
            commercial_total_cents
            - item["total_cents"]
        )

    return items


def calculate_price_breakdown(
    materials_subtotal_cents,
    quote,
    labor_cents=None,
):
    if labor_cents is None:
        labor_cents = percentage_of_cents(
            materials_subtotal_cents,
            quote["labor_percentage"],
        )

    subtotal_with_labor_cents = (
        materials_subtotal_cents
        + labor_cents
    )
    difficulty_cents = percentage_of_cents(
        subtotal_with_labor_cents,
        quote["difficulty_percentage"],
    )
    subtotal_before_discount_cents = (
        subtotal_with_labor_cents
        + difficulty_cents
    )
    discount_cents = percentage_of_cents(
        subtotal_before_discount_cents,
        quote["discount_percentage"],
    )
    calculated_total_cents = (
        subtotal_before_discount_cents
        - discount_cents
    )

    return {
        "labor_cents": labor_cents,
        "difficulty_cents": difficulty_cents,
        "discount_cents": discount_cents,
        "calculated_total_cents": calculated_total_cents,
    }

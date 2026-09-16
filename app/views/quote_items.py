from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)

from flask import (
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

from app.db import get_db
from app.services.pricing import percentage_of_cents
from app.utils.parsing import money_to_cents, parse_decimal
from app.web import main


@main.route("/orcamentos/<int:quote_id>/itens/novo", methods=("GET", "POST"))
def new_quote_item(quote_id):
    db = get_db()
    quote = db.execute(
        """
        SELECT quotes.id, quotes.status, clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] != "draft":
        abort(400)

    error = None

    if request.method == "POST":
        service_type = request.form.get("service_type", "").strip()
        description = request.form.get("description", "").strip()
        glass_type = request.form.get("glass_type", "").strip()
        glass_color = request.form.get("glass_color", "").strip()
        finish = request.form.get("finish", "").strip()

        try:
            quantity = int(request.form.get("quantity", ""))
            width_mm = int(request.form.get("width_mm", ""))
            height_mm = int(request.form.get("height_mm", ""))
            thickness_mm = parse_decimal(
                request.form.get("thickness_mm", "")
            )
            glass_price_per_m2_cents = money_to_cents(
                request.form.get("glass_price_per_m2", "")
            )
        except (ValueError, InvalidOperation):
            error = "Preencha corretamente as medidas, quantidades e valores."

        if error is None and not service_type:
            error = "Informe o tipo de serviço."
        elif error is None and not glass_type:
            error = "Informe o tipo de vidro."
        elif error is None and quantity <= 0:
            error = "A quantidade deve ser maior que zero."
        elif error is None and (width_mm <= 0 or height_mm <= 0):
            error = "A largura e a altura devem ser maiores que zero."
        elif error is None and thickness_mm <= 0:
            error = "A espessura deve ser maior que zero."
        elif error is None and glass_price_per_m2_cents <= 0:
            error = "O preço do vidro deve ser maior que zero."

        if error is None:
            exact_area_m2 = (
                Decimal(width_mm)
                * Decimal(height_mm)
                / Decimal("1000000")
            ).quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP,
            )
            charged_area_m2 = exact_area_m2

            db.execute(
                """
                INSERT INTO quote_items (
                    quote_id,
                    service_type,
                    description,
                    quantity,
                    width_mm,
                    height_mm,
                    exact_area_m2,
                    charged_area_m2,
                    glass_type,
                    thickness_mm,
                    glass_color,
                    finish,
                    glass_price_per_m2_cents
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quote_id,
                    service_type,
                    description,
                    quantity,
                    width_mm,
                    height_mm,
                    float(exact_area_m2),
                    float(charged_area_m2),
                    glass_type,
                    float(thickness_mm),
                    glass_color,
                    finish,
                    glass_price_per_m2_cents,
                ),
            )
            db.commit()

            return redirect(
                url_for("main.quote_detail", quote_id=quote_id, _anchor="quote-items")
            )

    return render_template(
        "new_quote_item.html",
        quote=quote,
        error=error,
    )


@main.route(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/componentes/novo",
    methods=("GET", "POST"),
)
def new_quote_item_component(quote_id, item_id):
    db = get_db()

    item = db.execute(
        """
        SELECT
            quote_items.id,
            quote_items.service_type,
            quote_items.quantity AS item_quantity,
            quote_items.width_mm,
            quotes.id AS quote_id,
            quotes.status,
            clients.name AS client_name
        FROM quote_items
        JOIN quotes ON quotes.id = quote_items.quote_id
        JOIN clients ON clients.id = quotes.client_id
        WHERE quote_items.id = ? AND quotes.id = ?
        """,
        (item_id, quote_id),
    ).fetchone()

    if item is None:
        abort(404)

    if item["status"] != "draft":
        abort(400)

    available_components = db.execute(
        """
        SELECT id, name, unit_price_cents
        FROM components
        WHERE active = 1
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    existing_components = db.execute(
        """
        SELECT id, description, quantity, unit_price_cents
        FROM quote_item_components
        WHERE quote_item_id = ?
        ORDER BY id
        """,
        (item_id,),
    ).fetchall()

    error = None
    component_rows = []

    if request.method == "POST":
        descriptions = request.form.getlist("description")
        quantities = request.form.getlist("quantity")
        unit_prices = request.form.getlist("unit_price")

        if not (
            len(descriptions)
            == len(quantities)
            == len(unit_prices)
        ):
            error = "Os dados dos componentes estao incompletos."

        if error is None:
            for description, quantity_raw, unit_price_raw in zip(
                descriptions,
                quantities,
                unit_prices,
            ):
                description = description.strip()

                component_rows.append(
                    {
                        "description": description,
                        "quantity": quantity_raw,
                        "unit_price": unit_price_raw,
                    }
                )

                try:
                    quantity = int(quantity_raw)
                    unit_price_cents = money_to_cents(unit_price_raw)
                except (ValueError, InvalidOperation):
                    error = "Preencha corretamente quantidade e valor."
                    break

                if not description:
                    error = "Selecione um componente."
                    break

                if quantity <= 0:
                    error = "A quantidade deve ser maior que zero."
                    break

                if unit_price_cents <= 0:
                    error = "O valor unitario deve ser maior que zero."
                    break

        if error is None and not component_rows:
            error = "Adicione pelo menos um componente."

        if error is None:
            rows_to_save = []

            for row in component_rows:
                rows_to_save.append(
                    (
                        item_id,
                        "other",
                        row["description"],
                        int(row["quantity"]),
                        money_to_cents(row["unit_price"]),
                    )
                )

            db.execute(
                """
                DELETE FROM quote_item_components
                WHERE quote_item_id = ?
                """,
                (item_id,),
            )

            db.executemany(
                """
                INSERT INTO quote_item_components (
                    quote_item_id,
                    category,
                    description,
                    quantity,
                    unit_price_cents
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                rows_to_save,
            )

            db.commit()

            return redirect(
                url_for(
                    "main.quote_detail",
                    quote_id=quote_id,
                    _anchor="quote-items",
                )
            )

    else:
        for component in existing_components:
            component_rows.append(
                {
                    "description": component["description"],
                    "quantity": str(component["quantity"]),
                    "unit_price": (
                        f"{component['unit_price_cents'] / 100:.2f}"
                        .replace(".", ",")
                    ),
                }
            )

    if not component_rows:
        component_rows = [
            {
                "description": "",
                "quantity": "1",
                "unit_price": "",
            }
        ]

    return render_template(
        "new_quote_item_component.html",
        item=item,
        available_components=available_components,
        component_rows=component_rows,
        error=error,
    )


@main.route(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/mao-de-obra",
    methods=("GET", "POST"),
)
def edit_quote_item_labor(quote_id, item_id):
    db = get_db()

    quote = db.execute(
        """
        SELECT
            quotes.id,
            quotes.status,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    item = db.execute(
        """
        SELECT
            quote_items.*,
            CAST(
                ROUND(
                    charged_area_m2
                    * quantity
                    * glass_price_per_m2_cents
                )
                AS INTEGER
            ) AS glass_total_cents
        FROM quote_items
        WHERE id = ? AND quote_id = ?
        """,
        (item_id, quote_id),
    ).fetchone()

    if quote is None or item is None:
        abort(404)

    if quote["status"] != "draft":
        abort(400)

    components_total_cents = db.execute(
        """
        SELECT COALESCE(
            SUM(quantity * unit_price_cents),
            0
        )
        FROM quote_item_components
        WHERE quote_item_id = ?
        """,
        (item_id,),
    ).fetchone()[0]

    materials_total_cents = (
        item["glass_total_cents"]
        + components_total_cents
    )
    automatic_labor_cents = percentage_of_cents(
        materials_total_cents,
        50,
    )
    current_labor_cents = (
        item["manual_labor_cents"]
        if item["manual_labor_cents"] is not None
        else automatic_labor_cents
    )

    error = None

    if request.method == "POST":
        labor_mode = request.form.get("labor_mode", "manual")

        if labor_mode == "automatic":
            manual_labor_cents = None
        else:
            try:
                manual_labor_cents = money_to_cents(
                    request.form.get("labor_value", "")
                )
            except InvalidOperation:
                error = "Informe corretamente o valor da mão de obra."
                manual_labor_cents = None

            if error is None and manual_labor_cents < 0:
                error = "A mão de obra não pode ser negativa."

        if error is None:
            db.execute(
                """
                UPDATE quote_items
                SET
                    manual_labor_cents = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND quote_id = ?
                """,
                (
                    manual_labor_cents,
                    item_id,
                    quote_id,
                ),
            )
            db.execute(
                """
                UPDATE quotes
                SET
                    manual_total_cents = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (quote_id,),
            )
            db.commit()

            return redirect(
                url_for(
                    "main.quote_detail",
                    quote_id=quote_id,
                    _anchor=f"quote-item-{item_id}",
                )
            )

    return render_template(
        "edit_quote_item_labor.html",
        quote=quote,
        item=item,
        components_total_cents=components_total_cents,
        materials_total_cents=materials_total_cents,
        automatic_labor_cents=automatic_labor_cents,
        current_labor_cents=current_labor_cents,
        error=error,
    )


@main.route(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/editar",
    methods=("GET", "POST"),
)
def edit_quote_item(quote_id, item_id):
    db = get_db()
    quote = db.execute(
        """
        SELECT
            quotes.id,
            quotes.status,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    item = db.execute(
        """
        SELECT *
        FROM quote_items
        WHERE id = ? AND quote_id = ?
        """,
        (item_id, quote_id),
    ).fetchone()

    if quote is None or item is None:
        abort(404)

    if quote["status"] != "draft":
        abort(400)

    error = None

    if request.method == "POST":
        service_type = request.form.get("service_type", "").strip()
        description = request.form.get("description", "").strip()
        glass_type = request.form.get("glass_type", "").strip()
        glass_color = request.form.get("glass_color", "").strip()
        finish = request.form.get("finish", "").strip()

        try:
            quantity = int(request.form.get("quantity", ""))
            width_mm = int(request.form.get("width_mm", ""))
            height_mm = int(request.form.get("height_mm", ""))
            thickness_mm = parse_decimal(
                request.form.get("thickness_mm", "")
            )
            glass_price_per_m2_cents = money_to_cents(
                request.form.get("glass_price_per_m2", "")
            )
        except (ValueError, InvalidOperation):
            error = "Preencha corretamente as medidas, quantidades e valores."

        if error is None and not service_type:
            error = "Informe o tipo de serviço."
        elif error is None and not glass_type:
            error = "Informe o tipo de vidro."
        elif error is None and quantity <= 0:
            error = "A quantidade deve ser maior que zero."
        elif error is None and (width_mm <= 0 or height_mm <= 0):
            error = "A largura e a altura devem ser maiores que zero."
        elif error is None and thickness_mm <= 0:
            error = "A espessura deve ser maior que zero."
        elif error is None and glass_price_per_m2_cents <= 0:
            error = "O preço do vidro deve ser maior que zero."

        if error is None:
            exact_area_m2 = (
                Decimal(width_mm)
                * Decimal(height_mm)
                / Decimal("1000000")
            ).quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP,
            )
            charged_area_m2 = exact_area_m2

            db.execute(
                """
                UPDATE quote_items
                SET
                    service_type = ?,
                    description = ?,
                    quantity = ?,
                    width_mm = ?,
                    height_mm = ?,
                    exact_area_m2 = ?,
                    charged_area_m2 = ?,
                    glass_type = ?,
                    thickness_mm = ?,
                    glass_color = ?,
                    finish = ?,
                    glass_price_per_m2_cents = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND quote_id = ?
                """,
                (
                    service_type,
                    description,
                    quantity,
                    width_mm,
                    height_mm,
                    float(exact_area_m2),
                    float(charged_area_m2),
                    glass_type,
                    float(thickness_mm),
                    glass_color,
                    finish,
                    glass_price_per_m2_cents,
                    item_id,
                    quote_id,
                ),
            )
            db.commit()

            return redirect(
                url_for("main.quote_detail", quote_id=quote_id, _anchor="quote-items")
            )

    charged_area_for_input = (
        f"{item['charged_area_m2']:.2f}"
        .replace(".", ",")
    )
    glass_price_for_input = (
        f"{item['glass_price_per_m2_cents'] / 100:.2f}"
        .replace(".", ",")
    )

    return render_template(
        "edit_quote_item.html",
        quote=quote,
        item=item,
        charged_area_for_input=charged_area_for_input,
        glass_price_for_input=glass_price_for_input,
        error=error,
    )


@main.route(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/componentes/<int:component_id>/editar",
    methods=("GET", "POST"),
)
def edit_quote_item_component(
    quote_id,
    item_id,
    component_id,
):
    db = get_db()
    component = db.execute(
        """
        SELECT
            quote_item_components.*,
            quote_items.service_type,
            quotes.id AS quote_id,
            quotes.status,
            clients.name AS client_name
        FROM quote_item_components
        JOIN quote_items
            ON quote_items.id = quote_item_components.quote_item_id
        JOIN quotes
            ON quotes.id = quote_items.quote_id
        JOIN clients
            ON clients.id = quotes.client_id
        WHERE
            quote_item_components.id = ?
            AND quote_items.id = ?
            AND quotes.id = ?
        """,
        (component_id, item_id, quote_id),
    ).fetchone()

    if component is None:
        abort(404)

    if component["status"] != "draft":
        abort(400)

    error = None

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        try:
            quantity = int(request.form.get("quantity", ""))
            unit_price_cents = money_to_cents(
                request.form.get("unit_price", "")
            )
        except (ValueError, InvalidOperation):
            error = "Preencha corretamente a quantidade e o valor."

        if error is None and category not in {"kit", "accessory", "other"}:
            error = "Selecione o tipo do componente."
        elif error is None and not description:
            error = "Informe a descrição do componente."
        elif error is None and quantity <= 0:
            error = "A quantidade deve ser maior que zero."
        elif error is None and unit_price_cents <= 0:
            error = "O valor unitário deve ser maior que zero."

        if error is None:
            db.execute(
                """
                UPDATE quote_item_components
                SET
                    category = ?,
                    description = ?,
                    quantity = ?,
                    unit_price_cents = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND quote_item_id = ?
                """,
                (
                    category,
                    description,
                    quantity,
                    unit_price_cents,
                    component_id,
                    item_id,
                ),
            )
            db.commit()

            return redirect(
                url_for("main.quote_detail", quote_id=quote_id, _anchor="quote-items")
            )

    unit_price_for_input = (
        f"{component['unit_price_cents'] / 100:.2f}"
        .replace(".", ",")
    )

    return render_template(
        "edit_quote_item_component.html",
        component=component,
        unit_price_for_input=unit_price_for_input,
        error=error,
    )


@main.post(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/remover"
)
def remove_quote_item(quote_id, item_id):
    db = get_db()
    result = db.execute(
        """
        DELETE FROM quote_items
        WHERE
            id = ?
            AND quote_id = ?
            AND EXISTS (
                SELECT 1
                FROM quotes
                WHERE
                    quotes.id = quote_items.quote_id
                    AND quotes.status = 'draft'
            )
        """,
        (item_id, quote_id),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(
        url_for("main.quote_detail", quote_id=quote_id, _anchor="quote-items")
    )


@main.post(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/componentes/<int:component_id>/remover"
)
def remove_quote_item_component(
    quote_id,
    item_id,
    component_id,
):
    db = get_db()
    result = db.execute(
        """
        DELETE FROM quote_item_components
        WHERE
            id = ?
            AND quote_item_id = ?
            AND EXISTS (
                SELECT 1
                FROM quote_items
                JOIN quotes
                    ON quotes.id = quote_items.quote_id
                WHERE
                    quote_items.id = quote_item_components.quote_item_id
                    AND quote_items.quote_id = ?
                    AND quotes.status = 'draft'
            )
        """,
        (component_id, item_id, quote_id),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(
        url_for("main.quote_detail", quote_id=quote_id, _anchor="quote-items")
    )

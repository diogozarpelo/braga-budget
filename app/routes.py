from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import abort, redirect, render_template, request, send_file, url_for




from app.db import get_db
from app.utils.pagination import get_pagination
from app.web import main
from app.views import clients as _clients_routes
from app.views import components as _components_routes
from app.views import home as _home_routes
from app.views import settings as _settings_routes
from app.services.quote_export import (
    build_quote_pdf,
    build_quote_png,
)
from app.services.pricing import (
    calculate_items_pricing,
    calculate_price_breakdown,
    distribute_final_total_between_items,
    percentage_of_cents,
)
from app.utils.parsing import money_to_cents, parse_decimal
from app.utils.text import (
    escape_like,
    normalize_comparison_text,
    phone_digits,
)



ISSUED_QUOTES_PER_PAGE = 15























@main.get("/orcamentos")
def quotes():
    db = get_db()

    drafts = db.execute(
        """
        SELECT
            quotes.id,
            quotes.created_at,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.status = 'draft'
        ORDER BY quotes.created_at DESC, quotes.id DESC
        """
    ).fetchall()

    issued_search = request.args.get("q", "").strip()
    issued_where_parts = ["quotes.status != 'draft'"]
    issued_query_params = []

    if issued_search:
        escaped_search = escape_like(issued_search)
        search_pattern = f"%{escaped_search}%"
        search_conditions = [
            "CAST(quotes.quote_number AS TEXT) LIKE ? ESCAPE '\\'",
            "clients.name LIKE ? ESCAPE '\\' COLLATE NOCASE",
        ]
        issued_query_params.extend((search_pattern, search_pattern))

        normalized_search_phone = phone_digits(issued_search)
        if normalized_search_phone:
            search_conditions.append(
                f"{CLIENT_PHONE_DIGITS_SQL} LIKE ? ESCAPE '\\'"
            )
            issued_query_params.append(f"%{normalized_search_phone}%")

        issued_where_parts.append(f"({' OR '.join(search_conditions)})")

    issued_where_clause = " AND ".join(issued_where_parts)
    issued_total_count = db.execute(
        f"""
        SELECT COUNT(*)
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE {issued_where_clause}
        """,
        issued_query_params,
    ).fetchone()[0]
    issued_page, issued_total_pages, issued_offset = get_pagination(
        issued_total_count,
        ISSUED_QUOTES_PER_PAGE,
    )
    issued_quotes = db.execute(
        f"""
        SELECT
            quotes.id,
            quotes.quote_number,
            quotes.status,
            quotes.issued_at,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE {issued_where_clause}
        ORDER BY quotes.issued_at DESC, quotes.id DESC
        LIMIT ? OFFSET ?
        """,
        (*issued_query_params, ISSUED_QUOTES_PER_PAGE, issued_offset),
    ).fetchall()

    return render_template(
        "quotes.html",
        drafts=drafts,
        issued_quotes=issued_quotes,
        issued_search=issued_search,
        issued_page=issued_page,
        issued_total_pages=issued_total_pages,
        issued_total_count=issued_total_count,
    )


@main.route("/orcamentos/novo", methods=("GET", "POST"))
def new_quote():
    db = get_db()
    error = None

    clients_list = db.execute(
        """
        SELECT id, name
        FROM clients
        WHERE active = 1
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)

        client = None

        if client_id is not None:
            client = db.execute(
                """
                SELECT id
                FROM clients
                WHERE id = ? AND active = 1
                """,
                (client_id,),
            ).fetchone()

        if client is None:
            error = "Selecione um cliente ativo."
        else:
            settings = db.execute(
                """
                SELECT
                    default_validity_days,
                    default_execution_days,
                    warranty_text
                FROM settings
                WHERE id = 1
                """
            ).fetchone()

            result = db.execute(
                """
                INSERT INTO quotes (
                    client_id,
                    validity_days,
                    execution_days,
                    warranty_text
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    client_id,
                    settings["default_validity_days"],
                    settings["default_execution_days"],
                    settings["warranty_text"],
                ),
            )
            db.commit()

            return redirect(
                url_for("main.quote_detail", quote_id=result.lastrowid)
            )

    return render_template(
        "new_quote.html",
        clients=clients_list,
        error=error,
    )


@main.get("/orcamentos/<int:quote_id>")
def quote_detail(quote_id):
    db = get_db()
    quote = db.execute(
        """
        SELECT
            quotes.*,
            clients.name AS client_name,
            clients.phone AS client_phone,
            clients.address AS client_address
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    items = db.execute(
        """
        SELECT
            id,
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
            glass_price_per_m2_cents,
            manual_labor_cents,
            CAST(
                ROUND(
                    charged_area_m2
                    * quantity
                    * glass_price_per_m2_cents
                )
                AS INTEGER
            ) AS glass_total_cents
        FROM quote_items
        WHERE quote_id = ?
        ORDER BY position, id
        """,
        (quote_id,),
    ).fetchall()

    components = db.execute(
        """
        SELECT
            quote_item_components.id,
            quote_item_components.quote_item_id,
            quote_item_components.category,
            quote_item_components.description,
            quote_item_components.quantity,
            quote_item_components.unit_price_cents,
            (
                quote_item_components.quantity
                * quote_item_components.unit_price_cents
            ) AS total_cents
        FROM quote_item_components
        JOIN quote_items
            ON quote_items.id = quote_item_components.quote_item_id
        WHERE quote_items.quote_id = ?
        ORDER BY
            quote_item_components.position,
            quote_item_components.id
        """,
        (quote_id,),
    ).fetchall()

    components_by_item = {
        item["id"]: []
        for item in items
    }

    for component in components:
        components_by_item[component["quote_item_id"]].append(component)

    items = calculate_items_pricing(
        items,
        components_by_item,
    )

    glass_subtotal_cents = sum(
        item["glass_total_cents"]
        for item in items
    )
    components_subtotal_cents = sum(
        item["components_total_cents"]
        for item in items
    )
    materials_subtotal_cents = sum(
        item["materials_total_cents"]
        for item in items
    )
    labor_cents = sum(
        item["labor_cents"]
        for item in items
    )

    price_breakdown = calculate_price_breakdown(
        materials_subtotal_cents,
        quote,
        labor_cents,
    )
    calculated_total_cents = price_breakdown[
        "calculated_total_cents"
    ]
    display_total_cents = (
        quote["manual_total_cents"]
        if quote["manual_total_cents"] is not None
        else calculated_total_cents
    )
    items = distribute_final_total_between_items(
        items,
        display_total_cents,
    )
    manual_adjustment_cents = (
        display_total_cents
        - calculated_total_cents
    )

    return render_template(
        "quote_detail.html",
        quote=quote,
        items=items,
        components_by_item=components_by_item,
        glass_subtotal_cents=glass_subtotal_cents,
        components_subtotal_cents=components_subtotal_cents,
        materials_subtotal_cents=materials_subtotal_cents,
        labor_cents=price_breakdown["labor_cents"],
        difficulty_cents=price_breakdown["difficulty_cents"],
        discount_cents=price_breakdown["discount_cents"],
        calculated_total_cents=calculated_total_cents,
        display_total_cents=display_total_cents,
        manual_adjustment_cents=manual_adjustment_cents,
        final_total_cents=display_total_cents,
    )






@main.get("/orcamentos/<int:quote_id>/exportar/pdf")
def export_quote_pdf(quote_id):
    db = get_db()

    quote = db.execute(
        """
        SELECT
            quotes.*,
            clients.name AS client_name,
            clients.phone AS client_phone,
            clients.address AS client_address
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] == "draft":
        abort(400)

    business = db.execute(
        """
        SELECT business_name, phone, cnpj, warranty_text
        FROM settings
        WHERE id = 1
        """
    ).fetchone()

    items = db.execute(
        """
        SELECT
            id,
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
            glass_price_per_m2_cents,
            manual_labor_cents,
            CAST(
                ROUND(
                    charged_area_m2
                    * quantity
                    * glass_price_per_m2_cents
                )
                AS INTEGER
            ) AS glass_total_cents
        FROM quote_items
        WHERE quote_id = ?
        ORDER BY position, id
        """,
        (quote_id,),
    ).fetchall()

    components = db.execute(
        """
        SELECT
            quote_item_components.quote_item_id,
            quote_item_components.description,
            quote_item_components.quantity,
            quote_item_components.unit_price_cents,
            (
                quote_item_components.quantity
                * quote_item_components.unit_price_cents
            ) AS total_cents
        FROM quote_item_components
        JOIN quote_items
            ON quote_items.id = quote_item_components.quote_item_id
        WHERE quote_items.quote_id = ?
        ORDER BY
            quote_item_components.position,
            quote_item_components.id
        """,
        (quote_id,),
    ).fetchall()

    components_by_item = {
        item["id"]: []
        for item in items
    }

    for component in components:
        components_by_item[component["quote_item_id"]].append(component)

    items = calculate_items_pricing(
        items,
        components_by_item,
    )

    glass_subtotal_cents = sum(
        item["glass_total_cents"]
        for item in items
    )
    components_subtotal_cents = sum(
        item["components_total_cents"]
        for item in items
    )
    materials_subtotal_cents = sum(
        item["materials_total_cents"]
        for item in items
    )
    labor_cents = sum(
        item["labor_cents"]
        for item in items
    )

    price_breakdown = calculate_price_breakdown(
        materials_subtotal_cents,
        quote,
        labor_cents,
    )

    calculated_total_cents = price_breakdown[
        "calculated_total_cents"
    ]

    display_total_cents = (
        quote["manual_total_cents"]
        if quote["manual_total_cents"] is not None
        else calculated_total_cents
    )
    items = distribute_final_total_between_items(
        items,
        display_total_cents,
    )

    buffer = build_quote_pdf(
        quote,
        business,
        items,
        display_total_cents,
    )

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=(
            f"orcamento-{quote['quote_number']}.pdf"
        ),
    )



@main.get("/orcamentos/<int:quote_id>/exportar/imagem")
def export_quote_image(quote_id):
    db = get_db()

    quote = db.execute(
        """
        SELECT id, quote_number, status
        FROM quotes
        WHERE id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] == "draft":
        abort(400)

    pdf_response = export_quote_pdf(quote_id)

    pdf_response.direct_passthrough = False
    pdf_bytes = pdf_response.get_data()

    try:
        output = build_quote_png(pdf_bytes)
    except RuntimeError:
        abort(500)

    return send_file(
        output,
        mimetype="image/png",
        as_attachment=True,
        download_name=(
            f"orcamento-{quote['quote_number']}.png"
        ),
    )



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



@main.app_template_filter("brl")
def format_brl(cents):
    value = cents / 100
    formatted = f"{value:,.2f}"

    return (
        "R$ "
        + formatted
        .replace(",", "#")
        .replace(".", ",")
        .replace("#", ".")
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
    "/orcamentos/<int:quote_id>/condicoes",
    methods=("GET", "POST"),
)
def edit_quote_conditions(quote_id):
    db = get_db()
    quote = db.execute(
        """
        SELECT
            quotes.*,
            clients.name AS client_name
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
        payment_terms = request.form.get("payment_terms", "").strip()
        notes = request.form.get("notes", "").strip()
        warranty_text = request.form.get("warranty_text", "").strip()

        try:
            validity_days = int(
                request.form.get("validity_days", "")
            )
            execution_days = int(
                request.form.get("execution_days", "")
            )
            difficulty_percentage = parse_decimal(
                request.form.get("difficulty_percentage", "")
            )
            discount_percentage = parse_decimal(
                request.form.get("discount_percentage", "")
            )
        except (ValueError, InvalidOperation):
            error = "Preencha corretamente os prazos e percentuais."

        if error is None and validity_days <= 0:
            error = "A validade deve ser maior que zero."
        elif error is None and execution_days <= 0:
            error = "O prazo de execução deve ser maior que zero."
        elif error is None and not 0 <= difficulty_percentage <= 100:
            error = "O adicional de dificuldade deve ficar entre 0% e 100%."
        elif error is None and not 0 <= discount_percentage <= 100:
            error = "O desconto deve ficar entre 0% e 100%."

        if error is None:
            db.execute(
                """
                UPDATE quotes
                SET
                    validity_days = ?,
                    execution_days = ?,
                    payment_terms = ?,
                    notes = ?,
                    warranty_text = ?,
                    difficulty_percentage = ?,
                    discount_percentage = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    validity_days,
                    execution_days,
                    payment_terms,
                    notes,
                    warranty_text,
                    float(difficulty_percentage),
                    float(discount_percentage),
                    quote_id,
                ),
            )
            db.commit()

            return redirect(
                url_for(
                    "main.quote_detail",
                    quote_id=quote_id,
                    _anchor="quote-conditions",
                )
            )

    return render_template(
        "edit_quote_conditions.html",
        quote=quote,
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





@main.post("/orcamentos/<int:quote_id>/remover-rascunho")
def delete_draft_quote(quote_id):
    db = get_db()

    quote = db.execute(
        """
        SELECT id, status
        FROM quotes
        WHERE id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] != "draft":
        abort(400)

    db.execute(
        """
        DELETE FROM quote_item_components
        WHERE quote_item_id IN (
            SELECT id
            FROM quote_items
            WHERE quote_id = ?
        )
        """,
        (quote_id,),
    )

    db.execute(
        """
        DELETE FROM quote_items
        WHERE quote_id = ?
        """,
        (quote_id,),
    )

    db.execute(
        """
        DELETE FROM quotes
        WHERE id = ?
        """,
        (quote_id,),
    )

    db.commit()

    return redirect(url_for("main.quotes"))


@main.post("/orcamentos/<int:quote_id>/status")
def update_quote_status(quote_id):
    db = get_db()

    quote = db.execute(
        """
        SELECT id, status
        FROM quotes
        WHERE id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] == "draft":
        abort(400)

    new_status = request.form.get("status", "").strip()

    if new_status not in {"issued", "approved", "rejected"}:
        abort(400)

    db.execute(
        """
        UPDATE quotes
        SET
            status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_status, quote_id),
    )

    db.commit()

    return redirect(
        url_for(
            "main.quotes",
        )
    )


@main.post("/orcamentos/<int:quote_id>/emitir")
def issue_quote(quote_id):
    db = get_db()

    try:
        db.execute("BEGIN IMMEDIATE")

        quote = db.execute(
            """
            SELECT id, status
            FROM quotes
            WHERE id = ?
            """,
            (quote_id,),
        ).fetchone()

        if quote is None:
            db.rollback()
            abort(404)

        if quote["status"] != "draft":
            db.rollback()
            abort(400)

        item_count = db.execute(
            """
            SELECT COUNT(*)
            FROM quote_items
            WHERE quote_id = ?
            """,
            (quote_id,),
        ).fetchone()[0]

        if item_count == 0:
            db.rollback()
            abort(400)

        settings = db.execute(
            """
            SELECT next_quote_number
            FROM settings
            WHERE id = 1
            """
        ).fetchone()

        if settings is None:
            db.rollback()
            abort(500)

        quote_number = settings["next_quote_number"]

        db.execute(
            """
            UPDATE quotes
            SET
                quote_number = ?,
                status = 'issued',
                issued_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (quote_number, quote_id),
        )

        db.execute(
            """
            UPDATE settings
            SET
                next_quote_number = next_quote_number + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return redirect(
        url_for(
            "main.quote_detail",
            quote_id=quote_id,
        )
    )


@main.route(
    "/orcamentos/<int:quote_id>/valor-final",
    methods=("GET", "POST"),
)
def edit_quote_final_total(quote_id):
    db = get_db()
    quote = db.execute(
        """
        SELECT
            quotes.*,
            clients.name AS client_name
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

    glass_total_cents = db.execute(
        """
        SELECT COALESCE(
            SUM(
                CAST(
                    ROUND(
                        charged_area_m2
                        * quantity
                        * glass_price_per_m2_cents
                    )
                    AS INTEGER
                )
            ),
            0
        )
        FROM quote_items
        WHERE quote_id = ?
        """,
        (quote_id,),
    ).fetchone()[0]

    components_total_cents = db.execute(
        """
        SELECT COALESCE(
            SUM(
                quote_item_components.quantity
                * quote_item_components.unit_price_cents
            ),
            0
        )
        FROM quote_item_components
        JOIN quote_items
            ON quote_items.id = quote_item_components.quote_item_id
        WHERE quote_items.quote_id = ?
        """,
        (quote_id,),
    ).fetchone()[0]

    labor_total_cents = db.execute(
        """
        SELECT COALESCE(
            SUM(
                COALESCE(
                    quote_items.manual_labor_cents,
                    CAST(
                        ROUND(
                            (
                                CAST(
                                    ROUND(
                                        quote_items.charged_area_m2
                                        * quote_items.quantity
                                        * quote_items.glass_price_per_m2_cents
                                    )
                                    AS INTEGER
                                )
                                + COALESCE(
                                    (
                                        SELECT SUM(
                                            component.quantity
                                            * component.unit_price_cents
                                        )
                                        FROM quote_item_components AS component
                                        WHERE component.quote_item_id = quote_items.id
                                    ),
                                    0
                                )
                            )
                            * 0.5
                        )
                        AS INTEGER
                    )
                )
            ),
            0
        )
        FROM quote_items
        WHERE quote_items.quote_id = ?
        """,
        (quote_id,),
    ).fetchone()[0]

    materials_subtotal_cents = (
        glass_total_cents
        + components_total_cents
    )
    price_breakdown = calculate_price_breakdown(
        materials_subtotal_cents,
        quote,
        labor_total_cents,
    )
    calculated_total_cents = price_breakdown[
        "calculated_total_cents"
    ]

    error = None

    if request.method == "POST":
        action = request.form.get("action", "save")

        if action == "use_calculated":
            manual_total_cents = None
        else:
            try:
                manual_total_cents = money_to_cents(
                    request.form.get("manual_total", "")
                )
            except InvalidOperation:
                error = "Informe corretamente o valor final."

            if error is None and manual_total_cents <= 0:
                error = "O valor final deve ser maior que zero."
            elif error is None and manual_total_cents % 100 != 0:
                error = "Informe um valor inteiro, sem centavos."

        if error is None:
            db.execute(
                """
                UPDATE quotes
                SET
                    manual_total_cents = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (manual_total_cents, quote_id),
            )
            db.commit()

            return redirect(
                url_for(
                    "main.quote_detail",
                    quote_id=quote_id,
                    _anchor="quote-total",
                )
            )

    current_total_cents = (
        quote["manual_total_cents"]
        if quote["manual_total_cents"] is not None
        else calculated_total_cents
    )
    current_total_for_input = (
        f"{current_total_cents / 100:.2f}"
        .replace(".", ",")
    )

    return render_template(
        "edit_quote_final_total.html",
        quote=quote,
        calculated_total_cents=calculated_total_cents,
        current_total_for_input=current_total_for_input,
        error=error,
    )

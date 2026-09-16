from flask import (
    abort,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from app.db import get_db
from app.services.quote_export import (
    build_quote_pdf,
    build_quote_png,
)
from app.services.pricing import (
    calculate_items_pricing,
    calculate_price_breakdown,
    distribute_final_total_between_items,
)
from app.utils.pagination import get_pagination
from app.utils.search import CLIENT_PHONE_DIGITS_SQL
from app.utils.text import (
    escape_like,
    phone_digits,
)
from app.web import main


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

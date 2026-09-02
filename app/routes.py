from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.db import get_db


main = Blueprint("main", __name__)

COMPONENTS_PER_PAGE = 15
CLIENTS_PER_PAGE = 15
ISSUED_QUOTES_PER_PAGE = 15

CLIENT_PHONE_DIGITS_SQL = """
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(clients.phone, '(', ''),
                        ')',
                        ''
                    ),
                    '-',
                    ''
                ),
                ' ',
                ''
            ),
            '.',
            ''
        ),
        '+',
        ''
    )
"""


def parse_decimal(value):
    text = value.strip()

    if not text:
        raise InvalidOperation

    if "," in text:
        text = text.replace(".", "").replace(",", ".")

    return Decimal(text)


def money_to_cents(value):
    amount = parse_decimal(value)

    return int(
        (amount * 100).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def escape_like(value):
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def normalize_comparison_text(value):
    return " ".join((value or "").split()).casefold()


def phone_digits(value):
    return "".join(
        character
        for character in (value or "")
        if character.isdigit()
    )


def get_pagination(total_count, per_page):
    page = request.args.get("page", default=1, type=int) or 1
    page = max(page, 1)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    return page, total_pages, offset


def find_duplicate_client(db, name, phone, address, exclude_client_id=None):
    query = """
        SELECT id, name, phone, address, active
        FROM clients
    """
    query_params = []

    if exclude_client_id is not None:
        query += " WHERE id != ?"
        query_params.append(exclude_client_id)

    query += " ORDER BY active DESC, id"

    normalized_name = normalize_comparison_text(name)
    normalized_phone = phone_digits(phone)
    normalized_address = normalize_comparison_text(address)

    for client in db.execute(query, query_params).fetchall():
        if normalize_comparison_text(client["name"]) != normalized_name:
            continue

        existing_phone = phone_digits(client["phone"])

        if normalized_phone and existing_phone == normalized_phone:
            return client

        if (
            not normalized_phone
            and not existing_phone
            and normalize_comparison_text(client["address"])
            == normalized_address
        ):
            return client

    return None


def duplicate_client_error(duplicate):
    if duplicate["active"]:
        return "Já existe um cliente ativo com esses mesmos dados."

    return (
        "Este cliente já existe na lista de desativados e pode ser "
        "reativado."
    )


def get_components_page(active):
    db = get_db()
    search = request.args.get("q", "").strip()

    where_parts = ["active = ?"]
    query_params = [active]

    if search:
        escaped_search = escape_like(search)
        where_parts.append("name LIKE ? ESCAPE '\\' COLLATE NOCASE")
        query_params.append(f"%{escaped_search}%")

    where_clause = " AND ".join(where_parts)
    total_count = db.execute(
        f"SELECT COUNT(*) FROM components WHERE {where_clause}",
        query_params,
    ).fetchone()[0]
    page, total_pages, offset = get_pagination(
        total_count,
        COMPONENTS_PER_PAGE,
    )

    components_list = db.execute(
        f"""
        SELECT id, name, unit_price_cents, active
        FROM components
        WHERE {where_clause}
        ORDER BY name COLLATE NOCASE
        LIMIT ? OFFSET ?
        """,
        (*query_params, COMPONENTS_PER_PAGE, offset),
    ).fetchall()

    return components_list, search, page, total_pages, total_count


@main.get("/")
def index():
    db = get_db()
    recent_quotes = db.execute(
        """
        SELECT
            quotes.id,
            quotes.quote_number,
            quotes.status,
            quotes.issued_at,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.status != 'draft'
        ORDER BY quotes.issued_at DESC, quotes.id DESC
        LIMIT 5
        """
    ).fetchall()

    return render_template(
        "index.html",
        recent_quotes=recent_quotes,
    )


@main.route("/clientes", methods=("GET", "POST"))
def clients():
    db = get_db()
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            error = "Informe o nome do cliente."
        else:
            duplicate = find_duplicate_client(
                db,
                name,
                phone,
                address,
            )

            if duplicate is not None:
                error = duplicate_client_error(duplicate)

        if error is None:
            db.execute(
                "INSERT INTO clients (name, phone, address) VALUES (?, ?, ?)",
                (name, phone, address),
            )
            db.commit()

            return redirect(url_for("main.clients"))

    search = request.args.get("q", "").strip()
    where_parts = ["clients.active = 1"]
    query_params = []

    if search:
        escaped_search = escape_like(search)
        search_pattern = f"%{escaped_search}%"
        search_conditions = [
            "clients.name LIKE ? ESCAPE '\\' COLLATE NOCASE",
            "clients.address LIKE ? ESCAPE '\\' COLLATE NOCASE",
        ]
        query_params.extend((search_pattern, search_pattern))

        normalized_search_phone = phone_digits(search)
        if normalized_search_phone:
            search_conditions.append(
                f"{CLIENT_PHONE_DIGITS_SQL} LIKE ? ESCAPE '\\'"
            )
            query_params.append(f"%{normalized_search_phone}%")

        where_parts.append(f"({' OR '.join(search_conditions)})")

    where_clause = " AND ".join(where_parts)
    total_count = db.execute(
        f"SELECT COUNT(*) FROM clients WHERE {where_clause}",
        query_params,
    ).fetchone()[0]
    page, total_pages, offset = get_pagination(
        total_count,
        CLIENTS_PER_PAGE,
    )
    clients_list = db.execute(
        f"""
        SELECT id, name, phone, address
        FROM clients
        WHERE {where_clause}
        ORDER BY name COLLATE NOCASE
        LIMIT ? OFFSET ?
        """,
        (*query_params, CLIENTS_PER_PAGE, offset),
    ).fetchall()

    return render_template(
        "clients.html",
        clients=clients_list,
        error=error,
        search=search,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )


@main.route("/clientes/<int:client_id>/editar", methods=("GET", "POST"))
def edit_client(client_id):
    db = get_db()
    client = db.execute(
        """
        SELECT id, name, phone, address
        FROM clients
        WHERE id = ? AND active = 1
        """,
        (client_id,),
    ).fetchone()

    if client is None:
        abort(404)

    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            error = "Informe o nome do cliente."
        else:
            duplicate = find_duplicate_client(
                db,
                name,
                phone,
                address,
                exclude_client_id=client_id,
            )

            if duplicate is not None:
                error = duplicate_client_error(duplicate)

        if error is None:
            db.execute(
                """
                UPDATE clients
                SET name = ?, phone = ?, address = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (name, phone, address, client_id),
            )
            db.commit()

            return redirect(url_for("main.clients"))

    return render_template(
        "client_edit.html",
        client=client,
        error=error,
    )


@main.post("/clientes/<int:client_id>/desativar")
def deactivate_client(client_id):
    db = get_db()
    result = db.execute(
        """
        UPDATE clients
        SET active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND active = 1
        """,
        (client_id,),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(url_for("main.clients"))


@main.get("/clientes/inativos")
def inactive_clients():
    db = get_db()
    clients_list = db.execute(
        """
        SELECT id, name, phone, address
        FROM clients
        WHERE active = 0
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    return render_template(
        "inactive_clients.html",
        clients=clients_list,
    )


@main.post("/clientes/<int:client_id>/reativar")
def reactivate_client(client_id):
    db = get_db()
    result = db.execute(
        """
        UPDATE clients
        SET active = 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND active = 0
        """,
        (client_id,),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(url_for("main.inactive_clients"))


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

    glass_subtotal_cents = sum(
        item["glass_total_cents"]
        for item in items
    )
    components_subtotal_cents = sum(
        component["total_cents"]
        for component in components
    )
    materials_subtotal_cents = (
        glass_subtotal_cents
        + components_subtotal_cents
    )
    price_breakdown = calculate_price_breakdown(
        materials_subtotal_cents,
        quote,
    )
    calculated_total_cents = price_breakdown[
        "calculated_total_cents"
    ]
    display_total_cents = (
        quote["manual_total_cents"]
        if quote["manual_total_cents"] is not None
        else calculated_total_cents
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
            labor_percentage = parse_decimal(
                request.form.get("labor_percentage", "")
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
        elif error is None and labor_percentage < 0:
            error = "A mão de obra não pode ser negativa."
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
                    labor_percentage = ?,
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
                    float(labor_percentage),
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



def calculate_price_breakdown(
    materials_subtotal_cents,
    quote,
):
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

    materials_subtotal_cents = (
        glass_total_cents
        + components_total_cents
    )
    price_breakdown = calculate_price_breakdown(
        materials_subtotal_cents,
        quote,
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



@main.route(
    "/configuracoes",
    methods=("GET", "POST"),
)
def settings():
    db = get_db()
    current_settings = db.execute(
        """
        SELECT *
        FROM settings
        WHERE id = 1
        """
    ).fetchone()

    if current_settings is None:
        abort(404)

    error = None

    if request.method == "POST":
        business_name = request.form.get(
            "business_name",
            "",
        ).strip()
        phone = request.form.get("phone", "").strip()
        cnpj = request.form.get("cnpj", "").strip()
        warranty_text = request.form.get(
            "warranty_text",
            "",
        ).strip()

        try:
            default_validity_days = int(
                request.form.get(
                    "default_validity_days",
                    "",
                )
            )
            default_execution_days = int(
                request.form.get(
                    "default_execution_days",
                    "",
                )
            )
        except ValueError:
            error = "Preencha corretamente os prazos padrão."

        if error is None and not business_name:
            error = "Informe o nome da vidraçaria."
        elif error is None and default_validity_days <= 0:
            error = "A validade padrão deve ser maior que zero."
        elif error is None and default_execution_days <= 0:
            error = "O prazo de execução padrão deve ser maior que zero."

        if error is None:
            db.execute(
                """
                UPDATE settings
                SET
                    business_name = ?,
                    phone = ?,
                    cnpj = ?,
                    default_validity_days = ?,
                    default_execution_days = ?,
                    warranty_text = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (
                    business_name,
                    phone,
                    cnpj,
                    default_validity_days,
                    default_execution_days,
                    warranty_text,
                ),
            )
            db.commit()

            return redirect(
                url_for("main.settings", saved=1)
            )

    return render_template(
        "settings.html",
        settings=current_settings,
        error=error,
    )


@main.route("/componentes", methods=("GET", "POST"))
def components():
    db = get_db()
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        unit_price = request.form.get("unit_price", "").strip()

        if not name:
            error = "Informe o nome do componente."

        if error is None:
            try:
                unit_price_cents = money_to_cents(unit_price)
            except (InvalidOperation, ValueError):
                error = "Informe corretamente o valor unitário."

        if error is None and unit_price_cents < 0:
            error = "O valor unitário não pode ser negativo."

        if error is None:
            existing_component = db.execute(
                """
                SELECT id
                FROM components
                WHERE name = ? COLLATE NOCASE
                """,
                (name,),
            ).fetchone()

            if existing_component is not None:
                error = "Já existe um componente com esse nome."

        if error is None:
            db.execute(
                """
                INSERT INTO components (name, unit_price_cents)
                VALUES (?, ?)
                """,
                (name, unit_price_cents),
            )
            db.commit()

            return redirect(url_for("main.components", saved=1))

    components_list, search, page, total_pages, total_count = (
        get_components_page(active=1)
    )

    return render_template(
        "components.html",
        components=components_list,
        error=error,
        search=search,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )


@main.route(
    "/componentes/<int:component_id>/editar",
    methods=("GET", "POST"),
)
def edit_component(component_id):
    db = get_db()
    component = db.execute(
        """
        SELECT id, name, unit_price_cents, active
        FROM components
        WHERE id = ? AND active = 1
        """,
        (component_id,),
    ).fetchone()

    if component is None:
        abort(404)

    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        unit_price = request.form.get("unit_price", "").strip()

        if not name:
            error = "Informe o nome do componente."

        if error is None:
            try:
                unit_price_cents = money_to_cents(unit_price)
            except (InvalidOperation, ValueError):
                error = "Informe corretamente o valor unitário."

        if error is None and unit_price_cents < 0:
            error = "O valor unitário não pode ser negativo."

        if error is None:
            duplicate = db.execute(
                """
                SELECT id
                FROM components
                WHERE name = ? COLLATE NOCASE
                    AND id != ?
                """,
                (name, component_id),
            ).fetchone()

            if duplicate is not None:
                error = "Já existe outro componente com esse nome."

        if error is None:
            db.execute(
                """
                UPDATE components
                SET
                    name = ?,
                    unit_price_cents = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (name, unit_price_cents, component_id),
            )
            db.commit()

            return redirect(url_for("main.components", updated=1))

    return render_template(
        "edit_component.html",
        component=component,
        error=error,
    )


@main.post("/componentes/<int:component_id>/desativar")
def deactivate_component(component_id):
    db = get_db()
    result = db.execute(
        """
        UPDATE components
        SET active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND active = 1
        """,
        (component_id,),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(url_for("main.components", deactivated=1))


@main.post("/componentes/<int:component_id>/reativar")
def reactivate_component(component_id):
    db = get_db()
    result = db.execute(
        """
        UPDATE components
        SET active = 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND active = 0
        """,
        (component_id,),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(url_for("main.inactive_components", reactivated=1))


@main.get("/componentes/desativados")
def inactive_components():
    components_list, search, page, total_pages, total_count = (
        get_components_page(active=0)
    )

    return render_template(
        "inactive_components.html",
        components=components_list,
        search=search,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )

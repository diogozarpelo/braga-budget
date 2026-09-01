from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.db import get_db


main = Blueprint("main", __name__)


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


@main.get("/")
def index():
    return render_template("index.html")


@main.route("/clientes", methods=("GET", "POST"))
def clients():
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            error = "Informe o nome do cliente."
        else:
            db = get_db()
            db.execute(
                "INSERT INTO clients (name, phone, address) VALUES (?, ?, ?)",
                (name, phone, address),
            )
            db.commit()

            return redirect(url_for("main.clients"))

    db = get_db()
    clients_list = db.execute(
        """
        SELECT id, name, phone, address
        FROM clients
        WHERE active = 1
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    return render_template(
        "clients.html",
        clients=clients_list,
        error=error,
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

    issued_quotes = db.execute(
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
        """
    ).fetchall()

    return render_template(
        "quotes.html",
        drafts=drafts,
        issued_quotes=issued_quotes,
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

    glass_subtotal_cents = sum(
        item["glass_total_cents"]
        for item in items
    )

    return render_template(
        "quote_detail.html",
        quote=quote,
        items=items,
        glass_subtotal_cents=glass_subtotal_cents,
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
            charged_area_m2 = parse_decimal(
                request.form.get("charged_area_m2", "")
            )
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
        elif error is None and charged_area_m2 <= 0:
            error = "A área cobrada deve ser maior que zero."
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
                url_for("main.quote_detail", quote_id=quote_id)
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

from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.db import get_db


main = Blueprint("main", __name__)


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

    return render_template(
        "quote_detail.html",
        quote=quote,
    )


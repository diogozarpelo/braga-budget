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

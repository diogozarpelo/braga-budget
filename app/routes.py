from flask import Blueprint, redirect, render_template, request, url_for

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

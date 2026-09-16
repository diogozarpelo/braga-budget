from flask import (
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

from app.db import get_db
from app.utils.pagination import get_pagination
from app.utils.text import (
    escape_like,
    normalize_comparison_text,
    phone_digits,
)
from app.web import main


CLIENTS_PER_PAGE = 15

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

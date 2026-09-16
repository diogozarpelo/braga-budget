from decimal import InvalidOperation

from flask import (
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

from app.db import get_db
from app.utils.pagination import get_pagination
from app.utils.parsing import money_to_cents
from app.utils.text import escape_like
from app.web import main


COMPONENTS_PER_PAGE = 15


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

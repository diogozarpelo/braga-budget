from decimal import InvalidOperation

from flask import (
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

from app.db import get_db
from app.services.pricing import calculate_price_breakdown
from app.utils.parsing import money_to_cents, parse_decimal
from app.web import main


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

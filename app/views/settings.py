from flask import (
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

from app.db import get_db
from app.web import main


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

from flask import render_template

from app.db import get_db
from app.web import main


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

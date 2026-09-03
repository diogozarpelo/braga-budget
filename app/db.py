import sqlite3

import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def migrate_db():
    db = get_db()

    quote_item_columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info(quote_items)"
        ).fetchall()
    }

    if (
        quote_item_columns
        and "manual_labor_cents" not in quote_item_columns
    ):
        db.execute(
            """
            ALTER TABLE quote_items
            ADD COLUMN manual_labor_cents INTEGER
                CHECK (
                    manual_labor_cents IS NULL
                    OR manual_labor_cents >= 0
                )
            """
        )

    db.commit()


def init_db():
    db = get_db()

    with current_app.open_resource("schema.sql") as schema_file:
        db.executescript(schema_file.read().decode("utf-8"))

    migrate_db()
    db.commit()


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Banco de dados inicializado com sucesso.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
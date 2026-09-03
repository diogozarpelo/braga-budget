import os
import threading
import time
import webbrowser

from app import create_app
from app.db import init_db, migrate_db


app = create_app()


def ensure_database():
    database_path = app.config["DATABASE"]

    with app.app_context():
        if not os.path.exists(database_path):
            init_db()
        else:
            migrate_db()


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    ensure_database()

    threading.Thread(
        target=open_browser,
        daemon=True,
    ).start()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
    )
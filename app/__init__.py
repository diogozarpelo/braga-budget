import os
import sys

from flask import Flask


def create_app():
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get(
            "LOCALAPPDATA",
            os.path.expanduser("~"),
        )
        instance_path = os.path.join(
            local_app_data,
            "BragaBudget",
        )

        app = Flask(
            __name__,
            instance_path=instance_path,
        )
    else:
        app = Flask(
            __name__,
            instance_relative_config=True,
        )

    app.config.from_mapping(
        DATABASE=os.path.join(
            app.instance_path,
            "braga_budget.sqlite",
        ),
    )

    os.makedirs(
        app.instance_path,
        exist_ok=True,
    )

    from app import db
    db.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    return app

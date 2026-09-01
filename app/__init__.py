import os

from flask import Flask


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "braga_budget.sqlite"),
    )

    os.makedirs(app.instance_path, exist_ok=True)

    from app import db
    db.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    return app

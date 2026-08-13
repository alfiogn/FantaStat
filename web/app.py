from __future__ import annotations

from flask import Flask

from routes import api_bp, pages_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

from __future__ import annotations

from flask import Flask

from routes import api_bp, pages_bp, notes_bp, export_bp



def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(export_bp)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=False)

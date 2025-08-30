# app/__init__.py

from flask import Flask

def create_app():
    app = Flask(__name__)

    # Blueprints oder einfache Routen importieren
    from .routes import routes
    app.register_blueprint(routes)

    return app
import pytest
from app import app as flask_app
from app import db as flask_db


@pytest.fixture()
def app():
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    flask_db.create_all()
    yield flask_app, flask_db
    flask_db.session.remove()
    flask_db.drop_all()


@pytest.fixture()
def client(app):
    app, _ = app
    return app.test_client()


@pytest.fixture()
def db(app):
    _, db = app
    return db

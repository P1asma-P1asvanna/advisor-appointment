import os
import pathlib
from urllib.parse import urlparse

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
os.environ.setdefault("APP_ENV", "dev")
if TEST_DB:
    os.environ["DATABASE_URL"] = TEST_DB

SQL_DIR = pathlib.Path(__file__).resolve().parent.parent / "sql"
DEMO_PASSWORD = "demo1234"


def pytest_collection_modifyitems(config, items):
    if TEST_DB:
        return
    skip = pytest.mark.skip(reason="set TEST_DATABASE_URL to run the API tests (database name must end with _test)")
    for item in items:
        if "needs_db" in item.keywords:
            item.add_marker(skip)


def _run_script(sql: str) -> None:
    import psycopg

    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        conn.execute(sql)


@pytest.fixture(scope="session")
def _schema():
    name = urlparse(TEST_DB).path.lstrip("/")
    assert name.endswith("_test"), f"refusing to wipe database {name!r}: its name must end with _test"
    _run_script("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    for f in ("schema.sql", "schema_v2.sql", "schema_v3.sql", "schema_v4.sql", "schema_v5.sql"):
        _run_script((SQL_DIR / f).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fresh_data(request):
    """Every API test starts from the demo data in sql/seed.sql."""
    if "needs_db" not in request.keywords or not TEST_DB:
        return
    request.getfixturevalue("_schema")
    _run_script((SQL_DIR / "seed.sql").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def client(_schema):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def _login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def thana(client):  # student, 1 active upcoming appointment
    return _login(client, "thana@example.edu")


@pytest.fixture
def pimlada(client):  # student, 2 active upcoming appointments (at the default limit)
    return _login(client, "pimlada@example.edu")


@pytest.fixture
def sureeporn(client):  # advisor, วิศวกรรมคอมพิวเตอร์
    return _login(client, "sureeporn@example.edu")


@pytest.fixture
def nattawut(client):  # advisor, คณิตศาสตร์
    return _login(client, "nattawut@example.edu")


@pytest.fixture
def mali(client):  # admin
    return _login(client, "mali@example.edu")

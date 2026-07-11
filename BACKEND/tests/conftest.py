"""
conftest.py
-----------
Shared pytest fixtures used by all test modules.

Root cause fix for :memory: isolation:
  SQLite's ':memory:' creates a brand-new empty database for every connection.
  That means init_db() + seed_db() run on connection A (inside create_app()),
  but the HTTP test-client opens connection B which is completely empty.

  Solution: use a named temp-file database for the test app.  Every connection
  to the same file shares the same data.  The file is created fresh for each
  test function and deleted afterwards.

Fixtures:
  app         — Flask app backed by a fresh temp-file SQLite DB
  client      — HTTP test client for that app
  db          — Raw DB connection for direct SQL inspection
  auth_client — Already-logged-in test client
"""

import os
import sys
import tempfile

import pytest

# Allow imports from BACKEND/ when running from BACKEND/tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from database import get_db


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """
    Create a Flask app backed by a temporary on-disk SQLite database.

    A named temp file is used instead of ':memory:' so that every database
    connection (including the ones opened by HTTP request handlers) sees the
    tables and seed data created during app startup.

    The temp file is deleted after the test completes.
    """
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)   # close the OS-level file descriptor; sqlite3 will reopen it

    flask_app = create_app(
        {
            "TESTING": True,
            "DATABASE": db_path,
            "SECRET_KEY": "test-secret-key",
        }
    )

    yield flask_app

    # Teardown — remove the temp database file
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture()
def client(app):
    """HTTP test client for the test app."""
    return app.test_client()


@pytest.fixture()
def db(app):
    """
    Direct database connection for tests that need to inspect or manipulate
    the database without going through HTTP.
    """
    with app.app_context():
        yield get_db()


@pytest.fixture()
def auth_client(client):
    """
    A test client that is already authenticated as the demo user.

    Performs a real POST /login so the session cookie is set in the
    client's cookie jar — every subsequent request from this client
    will be treated as authenticated.
    """
    client.post(
        "/login",
        data={"username": "demo", "password": "demo1234"},
        follow_redirects=False,
    )
    return client

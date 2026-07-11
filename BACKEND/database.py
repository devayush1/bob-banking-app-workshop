"""
database.py
-----------
Centralises every interaction with the SQLite database.

Responsibilities:
  - get_db()          : returns a per-request connection stored on Flask's g object
  - close_db()        : tears down the connection at the end of every request
  - init_db()         : creates the three tables (users, accounts, transactions) if they
                        do not already exist — idempotent, safe to run repeatedly
  - seed_db()         : inserts one demo user + account on a fresh database so the app
                        works immediately without manual data entry
  - get_balance()     : reads the current account balance for a given user_id
  - update_balance()  : atomically updates the balance and writes a transaction record

Design notes:
  - The database file path is read from app.config['DATABASE'] so it can be overridden
    in tests with ':memory:' (an in-process SQLite DB that vanishes after the test).
  - sqlite3.Row is used as the row factory so columns are accessible by name.
  - update_balance() wraps both the UPDATE and INSERT inside an explicit BEGIN / COMMIT
    so that a failure in either step rolls back the whole operation — the balance can
    never be partially updated.
"""

import sqlite3
from datetime import datetime, timezone

from flask import current_app, g


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_db():
    """
    Return the SQLite connection for the current request.

    The connection is created once per request and cached on Flask's 'g' object.
    Subsequent calls within the same request return the cached connection without
    opening a second one.

    sqlite3.Row is set as the row_factory so that every row returned by a query
    behaves like a dictionary — columns are accessible by name, e.g. row['balance'].
    """
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        # Enforce foreign-key constraints (SQLite disables them by default)
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


def close_db(exception=None):
    """
    Close the database connection at the end of the request.

    Registered as a teardown function in init_app() so Flask calls it
    automatically after every request, whether or not an error occurred.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """
    Register close_db as a teardown function on the given Flask app.

    Called from create_app() in app.py so that connections are always
    cleaned up without the caller needing to manage them manually.
    """
    app.teardown_appcontext(close_db)


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def init_db():
    """
    Create the three application tables if they do not already exist.

    Tables:
      users        — customer credentials (username + hashed password)
      accounts     — current balance, one row per user (1-to-1 with users)
      transactions — immutable audit log of every deposit and withdrawal

    Using 'CREATE TABLE IF NOT EXISTS' makes this function idempotent —
    it is safe to call on every application start-up.
    """
    db = get_db()

    # ── users ───────────────────────────────────────────────────────────────
    # id            : auto-incrementing primary key
    # username      : unique login name, cannot be NULL
    # password_hash : Werkzeug-generated hash, never the plaintext password
    # created_at    : ISO-8601 timestamp set at insert time
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    # ── accounts ────────────────────────────────────────────────────────────
    # id      : primary key
    # user_id : foreign key to users.id — deleting a user cascades to the account
    # balance : stored as REAL; application logic rounds to 2 d.p. before writing
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            balance REAL    NOT NULL DEFAULT 0.0,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
    )

    # ── transactions ────────────────────────────────────────────────────────
    # id               : primary key
    # user_id          : which customer performed the transaction
    # transaction_type : 'deposit' or 'withdrawal'
    # amount           : always stored as a positive value
    # timestamp        : UTC ISO-8601 string written at insert time
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            transaction_type TEXT    NOT NULL,
            amount           REAL    NOT NULL,
            timestamp        TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
    )

    db.commit()


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

def seed_db():
    """
    Insert one demo user + account so the application works on a fresh install.

    The function checks whether any rows already exist in the users table before
    inserting — calling it repeatedly on an existing database is safe.

    Demo credentials (printed to console on first run):
      username : demo
      password : demo1234
    """
    from werkzeug.security import generate_password_hash

    db = get_db()

    # Guard: do not insert if data already exists
    existing = db.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
    if existing["cnt"] > 0:
        return

    hashed = generate_password_hash("demo1234")

    cursor = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("demo", hashed),
    )
    user_id = cursor.lastrowid

    db.execute(
        "INSERT INTO accounts (user_id, balance) VALUES (?, ?)",
        (user_id, 1000.00),
    )

    db.commit()

    print(
        "\n"
        "  ✔  Demo account created\n"
        "     username : demo\n"
        "     password : demo1234\n"
        "     balance  : $1,000.00\n"
    )


# ---------------------------------------------------------------------------
# Balance helpers
# ---------------------------------------------------------------------------

def get_balance(user_id):
    """
    Return the current balance for the given user_id as a float.

    Called by:
      - dashboard route  — to display the balance on screen
      - withdrawal route — to check whether the requested amount is available

    Raises ValueError if no account row exists for the user (should not happen
    in normal operation because seed_db() and the login flow ensure every
    authenticated user has an account).
    """
    db = get_db()
    row = db.execute(
        "SELECT balance FROM accounts WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if row is None:
        raise ValueError(f"No account found for user_id={user_id}")

    return float(row["balance"])


def update_balance(user_id, delta, transaction_type):
    """
    Atomically update the account balance and record the transaction.

    Parameters
    ----------
    user_id          : int   — the authenticated customer's ID
    delta            : float — positive to add (deposit), negative to subtract (withdrawal)
    transaction_type : str   — 'deposit' or 'withdrawal'

    The function wraps both the UPDATE and the INSERT inside an explicit
    database transaction.  If either statement fails the whole operation is
    rolled back, so the balance can never be left in a partial or inconsistent
    state.

    The amount stored in the transactions table is always the absolute value of
    delta (a positive number) for easier auditing and reporting.
    """
    db = get_db()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Update the running balance
        db.execute(
            "UPDATE accounts SET balance = ROUND(balance + ?, 2) WHERE user_id = ?",
            (delta, user_id),
        )

        # Append an immutable audit record
        db.execute(
            """
            INSERT INTO transactions (user_id, transaction_type, amount, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, transaction_type, abs(delta), timestamp),
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

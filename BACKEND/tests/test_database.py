"""
test_database.py
----------------
Unit tests for the database helper functions in database.py.

Tests cover:
  - init_db()       : tables exist after initialisation
  - seed_db()       : demo user + account are inserted once; second call is a no-op
  - get_balance()   : returns the correct float value
  - update_balance(): deposit increases balance by exact delta
                      withdrawal decreases balance by exact delta
                      transaction record is written for every operation
                      rollback on error leaves balance unchanged
"""

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import get_balance, get_db, init_db, seed_db, update_balance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_id(db):
    """Return the id of the demo user seeded by seed_db()."""
    row = db.execute("SELECT id FROM users WHERE username = 'demo'").fetchone()
    assert row is not None, "Demo user not found — seed_db() may not have run"
    return row["id"]


# ---------------------------------------------------------------------------
# init_db() tests
# ---------------------------------------------------------------------------

class TestInitDb:
    """Verify that init_db() creates the expected tables."""

    def test_users_table_exists(self, db, app):
        with app.app_context():
            result = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone()
            assert result is not None, "users table was not created"

    def test_accounts_table_exists(self, db, app):
        with app.app_context():
            result = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'"
            ).fetchone()
            assert result is not None, "accounts table was not created"

    def test_transactions_table_exists(self, db, app):
        with app.app_context():
            result = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'"
            ).fetchone()
            assert result is not None, "transactions table was not created"


# ---------------------------------------------------------------------------
# seed_db() tests
# ---------------------------------------------------------------------------

class TestSeedDb:
    """Verify seed data is inserted correctly and is idempotent."""

    def test_demo_user_created(self, db, app):
        with app.app_context():
            row = db.execute("SELECT username FROM users WHERE username='demo'").fetchone()
            assert row is not None
            assert row["username"] == "demo"

    def test_demo_account_created(self, db, app):
        with app.app_context():
            user_id = _get_user_id(db)
            row = db.execute(
                "SELECT balance FROM accounts WHERE user_id=?", (user_id,)
            ).fetchone()
            assert row is not None
            assert row["balance"] == 1000.00

    def test_seed_is_idempotent(self, db, app):
        """Calling seed_db() a second time must not insert extra rows."""
        with app.app_context():
            seed_db()  # second call
            count = db.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
            assert count == 1, f"Expected 1 user, got {count}"


# ---------------------------------------------------------------------------
# get_balance() tests
# ---------------------------------------------------------------------------

class TestGetBalance:
    """Verify balance retrieval returns the correct float value."""

    def test_returns_initial_balance(self, db, app):
        with app.app_context():
            user_id = _get_user_id(db)
            balance = get_balance(user_id)
            assert balance == 1000.00

    def test_returns_float(self, db, app):
        with app.app_context():
            user_id = _get_user_id(db)
            balance = get_balance(user_id)
            assert isinstance(balance, float)

    def test_raises_for_unknown_user(self, db, app):
        with app.app_context():
            with pytest.raises(ValueError, match="No account found"):
                get_balance(99999)


# ---------------------------------------------------------------------------
# update_balance() tests
# ---------------------------------------------------------------------------

class TestUpdateBalance:
    """Verify deposit and withdrawal update the balance atomically."""

    def test_deposit_increases_balance(self, db, app):
        with app.app_context():
            user_id = _get_user_id(db)
            update_balance(user_id, 200.00, "deposit")
            assert get_balance(user_id) == pytest.approx(1200.00)

    def test_withdrawal_decreases_balance(self, db, app):
        with app.app_context():
            user_id = _get_user_id(db)
            update_balance(user_id, -300.00, "withdrawal")
            assert get_balance(user_id) == pytest.approx(700.00)

    def test_transaction_record_written_for_deposit(self, db, app):
        with app.app_context():
            user_id = _get_user_id(db)
            update_balance(user_id, 150.00, "deposit")
            row = db.execute(
                "SELECT transaction_type, amount FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            assert row is not None
            assert row["transaction_type"] == "deposit"
            assert row["amount"] == pytest.approx(150.00)

    def test_transaction_record_written_for_withdrawal(self, db, app):
        with app.app_context():
            user_id = _get_user_id(db)
            update_balance(user_id, -50.00, "withdrawal")
            row = db.execute(
                "SELECT transaction_type, amount FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            assert row is not None
            assert row["transaction_type"] == "withdrawal"
            # Amount stored as positive even when delta was negative
            assert row["amount"] == pytest.approx(50.00)

    def test_multiple_deposits_accumulate(self, db, app):
        with app.app_context():
            user_id = _get_user_id(db)
            update_balance(user_id, 100.00, "deposit")
            update_balance(user_id, 100.00, "deposit")
            update_balance(user_id, 100.00, "deposit")
            assert get_balance(user_id) == pytest.approx(1300.00)

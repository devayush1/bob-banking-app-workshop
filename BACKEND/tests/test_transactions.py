"""
test_transactions.py
--------------------
Unit-level tests for the deposit and withdrawal logic in transactions.py.

Tests cover:
  - _parse_amount()     : the shared validation helper
  - Deposit GET         : renders the form correctly
  - Deposit POST        : blank, zero, negative, non-numeric amounts rejected
  - Deposit POST        : valid amount increases balance and redirects
  - Withdrawal GET      : renders the form with current balance
  - Withdrawal POST     : blank, zero, negative, non-numeric amounts rejected
  - Withdrawal POST     : amount > balance is rejected ("Insufficient funds")
  - Withdrawal POST     : valid amount decreases balance and redirects
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from transactions import _parse_amount


# ---------------------------------------------------------------------------
# _parse_amount() — shared validation helper
# ---------------------------------------------------------------------------

class TestParseAmount:
    """Pure-function tests — no Flask context needed."""

    def test_valid_positive_float(self):
        amount, error = _parse_amount("100.50")
        assert amount == pytest.approx(100.50)
        assert error is None

    def test_valid_integer_string(self):
        amount, error = _parse_amount("200")
        assert amount == pytest.approx(200.00)
        assert error is None

    def test_rounds_to_two_decimal_places(self):
        amount, error = _parse_amount("99.999")
        assert amount == pytest.approx(100.00)
        assert error is None

    def test_empty_string_returns_error(self):
        amount, error = _parse_amount("")
        assert amount is None
        assert error is not None

    def test_whitespace_only_returns_error(self):
        amount, error = _parse_amount("   ")
        assert amount is None
        assert error is not None

    def test_non_numeric_returns_error(self):
        amount, error = _parse_amount("abc")
        assert amount is None
        assert "valid number" in error.lower()

    def test_zero_returns_error(self):
        amount, error = _parse_amount("0")
        assert amount is None
        assert "greater than zero" in error.lower()

    def test_negative_returns_error(self):
        amount, error = _parse_amount("-50")
        assert amount is None
        assert "greater than zero" in error.lower()

    def test_none_input_returns_error(self):
        amount, error = _parse_amount(None)
        assert amount is None
        assert error is not None


# ---------------------------------------------------------------------------
# Deposit — GET
# ---------------------------------------------------------------------------

class TestDepositGet:
    def test_renders_form(self, auth_client):
        response = auth_client.get("/deposit")
        assert response.status_code == 200
        assert b"Deposit" in response.data
        assert b'name="amount"' in response.data

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get("/deposit", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Deposit — POST validation
# ---------------------------------------------------------------------------

class TestDepositPostValidation:
    def test_blank_amount_shows_error(self, auth_client):
        response = auth_client.post(
            "/deposit", data={"amount": ""}, follow_redirects=True
        )
        assert response.status_code == 200
        assert b"required" in response.data.lower()

    def test_non_numeric_amount_shows_error(self, auth_client):
        response = auth_client.post(
            "/deposit", data={"amount": "abc"}, follow_redirects=True
        )
        assert b"valid number" in response.data.lower()

    def test_zero_amount_shows_error(self, auth_client):
        response = auth_client.post(
            "/deposit", data={"amount": "0"}, follow_redirects=True
        )
        assert b"greater than zero" in response.data.lower()

    def test_negative_amount_shows_error(self, auth_client):
        response = auth_client.post(
            "/deposit", data={"amount": "-100"}, follow_redirects=True
        )
        assert b"greater than zero" in response.data.lower()


# ---------------------------------------------------------------------------
# Deposit — POST success
# ---------------------------------------------------------------------------

class TestDepositPostSuccess:
    def test_valid_deposit_redirects_to_dashboard(self, auth_client):
        response = auth_client.post(
            "/deposit", data={"amount": "250"}, follow_redirects=False
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers["Location"]

    def test_valid_deposit_increases_balance(self, auth_client, app):
        auth_client.post("/deposit", data={"amount": "250"})
        response = auth_client.get("/dashboard")
        # Demo account started at 1000.00; after depositing 250 it should show 1250.00
        assert b"1,250.00" in response.data

    def test_success_flash_message_shown(self, auth_client):
        response = auth_client.post(
            "/deposit", data={"amount": "100"}, follow_redirects=True
        )
        assert b"deposited" in response.data.lower()


# ---------------------------------------------------------------------------
# Withdrawal — GET
# ---------------------------------------------------------------------------

class TestWithdrawGet:
    def test_renders_form_with_balance(self, auth_client):
        response = auth_client.get("/withdraw")
        assert response.status_code == 200
        assert b"Withdraw" in response.data
        assert b'name="amount"' in response.data
        # Current balance should appear somewhere on the form
        assert b"1,000.00" in response.data

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get("/withdraw", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Withdrawal — POST validation
# ---------------------------------------------------------------------------

class TestWithdrawPostValidation:
    def test_blank_amount_shows_error(self, auth_client):
        response = auth_client.post(
            "/withdraw", data={"amount": ""}, follow_redirects=True
        )
        assert b"required" in response.data.lower()

    def test_non_numeric_shows_error(self, auth_client):
        response = auth_client.post(
            "/withdraw", data={"amount": "xyz"}, follow_redirects=True
        )
        assert b"valid number" in response.data.lower()

    def test_zero_shows_error(self, auth_client):
        response = auth_client.post(
            "/withdraw", data={"amount": "0"}, follow_redirects=True
        )
        assert b"greater than zero" in response.data.lower()

    def test_negative_shows_error(self, auth_client):
        response = auth_client.post(
            "/withdraw", data={"amount": "-10"}, follow_redirects=True
        )
        assert b"greater than zero" in response.data.lower()

    def test_exceeds_balance_shows_insufficient_funds(self, auth_client):
        response = auth_client.post(
            "/withdraw", data={"amount": "9999"}, follow_redirects=True
        )
        assert b"insufficient funds" in response.data.lower()

    def test_exceeds_balance_does_not_change_balance(self, auth_client):
        auth_client.post("/withdraw", data={"amount": "9999"})
        response = auth_client.get("/dashboard")
        # Balance must still be the original 1000.00
        assert b"1,000.00" in response.data


# ---------------------------------------------------------------------------
# Withdrawal — POST success
# ---------------------------------------------------------------------------

class TestWithdrawPostSuccess:
    def test_valid_withdrawal_redirects_to_dashboard(self, auth_client):
        response = auth_client.post(
            "/withdraw", data={"amount": "200"}, follow_redirects=False
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers["Location"]

    def test_valid_withdrawal_decreases_balance(self, auth_client):
        auth_client.post("/withdraw", data={"amount": "200"})
        response = auth_client.get("/dashboard")
        # 1000.00 - 200.00 = 800.00
        assert b"800.00" in response.data

    def test_success_flash_message_shown(self, auth_client):
        response = auth_client.post(
            "/withdraw", data={"amount": "100"}, follow_redirects=True
        )
        assert b"withdrew" in response.data.lower()

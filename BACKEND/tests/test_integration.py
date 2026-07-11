"""
test_integration.py
-------------------
End-to-end integration tests that exercise the full request lifecycle:
  Browser → Flask router → Auth guard → Business logic → SQLite → Template → Response

These tests use Flask's test client to simulate a real browser without
starting a network server.  Each test gets a fresh in-memory database
(via the 'client' fixture in conftest.py) so they are fully independent.

Test scenarios mirror the integration-test table in STEP_BY_STEP_IMPLEMENTATION_GUIDE.md:

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ Scenario                              │ Expected result                     │
  ├───────────────────────────────────────┼─────────────────────────────────────┤
  │ GET /login as anonymous user          │ 200, login page                     │
  │ POST /login with valid credentials    │ 302 → /dashboard                    │
  │ POST /login with wrong password       │ 200, error flash                    │
  │ GET /dashboard without session        │ 302 → /login                        │
  │ GET /dashboard with valid session     │ 200, balance visible                │
  │ POST /deposit with valid amount       │ 302 → /dashboard; balance higher    │
  │ POST /deposit with negative amount    │ 200, error flash                    │
  │ POST /withdraw within balance         │ 302 → /dashboard; balance lower     │
  │ POST /withdraw exceeding balance      │ 200, insufficient-funds flash       │
  │ GET /logout                           │ 302 → /login; session cleared       │
  └─────────────────────────────────────────────────────────────────────────────┘
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def login(client, username="demo", password="demo1234"):
    """Helper to log in and return the response."""
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Unauthenticated access
# ---------------------------------------------------------------------------

class TestUnauthenticated:
    """All protected URLs redirect unauthenticated users to /login."""

    def test_root_redirects(self, client):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302

    def test_dashboard_redirects(self, client):
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_deposit_redirects(self, client):
        response = client.get("/deposit", follow_redirects=False)
        assert response.status_code == 302

    def test_withdraw_redirects(self, client):
        response = client.get("/withdraw", follow_redirects=False)
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# Full login → dashboard → deposit → withdraw → logout flow
# ---------------------------------------------------------------------------

class TestFullFlow:
    """Happy-path end-to-end walkthrough of every user action."""

    def test_step1_login_page_loads(self, client):
        """GET /login returns 200 with the login form."""
        response = client.get("/login")
        assert response.status_code == 200
        assert b"MyBank" in response.data

    def test_step2_valid_login_redirects_to_dashboard(self, client):
        """POST /login with valid credentials → 302 to /dashboard."""
        response = login(client)
        assert response.status_code == 302
        assert "/dashboard" in response.headers["Location"]

    def test_step3_dashboard_shows_balance(self, client):
        """Authenticated GET /dashboard returns 200 with the balance."""
        login(client)
        response = client.get("/dashboard")
        assert response.status_code == 200
        # Demo account starts at $1,000.00
        assert b"1,000.00" in response.data

    def test_step4_deposit_increases_balance(self, client):
        """POST /deposit with valid amount → balance on dashboard increases."""
        login(client)
        client.post("/deposit", data={"amount": "500"}, follow_redirects=False)
        response = client.get("/dashboard")
        assert b"1,500.00" in response.data

    def test_step5_withdraw_decreases_balance(self, client):
        """POST /withdraw with valid amount → balance on dashboard decreases."""
        login(client)
        client.post("/withdraw", data={"amount": "200"}, follow_redirects=False)
        response = client.get("/dashboard")
        assert b"800.00" in response.data

    def test_step6_logout_clears_session(self, client):
        """GET /logout → session cleared → /dashboard redirects to /login."""
        login(client)
        client.get("/logout")
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestErrorPaths:
    """All validation failures return to the form with a flash message."""

    def test_wrong_password_shows_error(self, client):
        # Wrong credentials re-render the login page (200), not a redirect
        response = client.post(
            "/login",
            data={"username": "demo", "password": "wrong"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Invalid username or password" in response.data

    def test_deposit_non_numeric_shows_error(self, client):
        login(client)
        response = client.post(
            "/deposit", data={"amount": "hello"}, follow_redirects=True
        )
        assert b"valid number" in response.data.lower()

    def test_deposit_zero_shows_error(self, client):
        login(client)
        response = client.post(
            "/deposit", data={"amount": "0"}, follow_redirects=True
        )
        assert b"greater than zero" in response.data.lower()

    def test_withdraw_over_balance_shows_error(self, client):
        login(client)
        response = client.post(
            "/withdraw", data={"amount": "5000"}, follow_redirects=True
        )
        assert b"insufficient funds" in response.data.lower()

    def test_withdraw_over_balance_leaves_balance_unchanged(self, client):
        login(client)
        client.post("/withdraw", data={"amount": "5000"})  # should fail
        response = client.get("/dashboard")
        assert b"1,000.00" in response.data

    def test_404_returns_custom_page(self, client):
        response = client.get("/this-route-does-not-exist")
        assert response.status_code == 404
        assert b"404" in response.data


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------

class TestTransactionHistory:
    """The dashboard recent-transactions table reflects completed operations."""

    def test_deposit_appears_in_history(self, client):
        login(client)
        client.post("/deposit", data={"amount": "123.45"})
        response = client.get("/dashboard")
        assert b"123.45" in response.data
        assert b"Deposit" in response.data

    def test_withdrawal_appears_in_history(self, client):
        login(client)
        client.post("/withdraw", data={"amount": "50.00"})
        response = client.get("/dashboard")
        assert b"50.00" in response.data
        assert b"Withdrawal" in response.data

    def test_multiple_transactions_all_visible(self, client):
        login(client)
        client.post("/deposit",  data={"amount": "100"})
        client.post("/withdraw", data={"amount": "25"})
        client.post("/deposit",  data={"amount": "200"})
        response = client.get("/dashboard")
        assert b"100.00" in response.data
        assert b"25.00"  in response.data
        assert b"200.00" in response.data

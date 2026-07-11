"""
test_auth.py
------------
Unit-level tests for authentication logic in auth.py.

Tests cover:
  - login_required decorator  : unauthenticated access is redirected to /login
  - Login GET                 : renders the login form
  - Login POST — blank fields : flash error, no session created
  - Login POST — wrong creds  : generic flash error, no session created
  - Login POST — valid creds  : session created, redirect to dashboard
  - Logout                    : session cleared, redirect to /login
  - Already-logged-in GET     : redirected straight to dashboard (skip form)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# login_required decorator
# ---------------------------------------------------------------------------

class TestLoginRequired:
    """All protected routes must redirect unauthenticated visitors to /login."""

    def test_dashboard_redirects_to_login(self, client):
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_deposit_redirects_to_login(self, client):
        response = client.get("/deposit", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_withdraw_redirects_to_login(self, client):
        response = client.get("/withdraw", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Login GET
# ---------------------------------------------------------------------------

class TestLoginGet:
    """GET /login should render the login form."""

    def test_returns_200(self, client):
        response = client.get("/login")
        assert response.status_code == 200

    def test_contains_login_form_elements(self, client):
        response = client.get("/login")
        body = response.data.decode()
        body_lower = body.lower()
        assert 'name="username"' in body
        assert 'name="password"' in body
        assert 'method="post"' in body_lower


# ---------------------------------------------------------------------------
# Login POST — validation failures
# ---------------------------------------------------------------------------

class TestLoginPostValidation:
    """Server-side validation on the login form."""

    def test_blank_username_flashes_error(self, client):
        response = client.post(
            "/login",
            data={"username": "", "password": "any"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Username is required" in response.data

    def test_blank_password_flashes_error(self, client):
        response = client.post(
            "/login",
            data={"username": "demo", "password": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Password is required" in response.data

    def test_wrong_password_shows_generic_error(self, client):
        response = client.post(
            "/login",
            data={"username": "demo", "password": "wrongpassword"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Invalid username or password" in response.data

    def test_nonexistent_user_shows_generic_error(self, client):
        """Same message whether the username or password is wrong (anti-enumeration)."""
        response = client.post(
            "/login",
            data={"username": "nobody", "password": "any"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Invalid username or password" in response.data


# ---------------------------------------------------------------------------
# Login POST — success
# ---------------------------------------------------------------------------

class TestLoginPostSuccess:
    """Valid credentials create a session and redirect to /dashboard."""

    def test_valid_credentials_redirect_to_dashboard(self, client):
        response = client.post(
            "/login",
            data={"username": "demo", "password": "demo1234"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers["Location"]

    def test_session_contains_user_id_after_login(self, client, app):
        with client.session_transaction() as sess:
            assert "user_id" not in sess  # not logged in yet

        client.post("/login", data={"username": "demo", "password": "demo1234"})

        with client.session_transaction() as sess:
            assert "user_id" in sess
            assert isinstance(sess["user_id"], int)

    def test_welcome_flash_shown_after_login(self, client):
        response = client.post(
            "/login",
            data={"username": "demo", "password": "demo1234"},
            follow_redirects=True,
        )
        assert b"Welcome back" in response.data


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

class TestLogout:
    """Logout clears the session and redirects to /login."""

    def test_logout_redirects_to_login(self, auth_client):
        response = auth_client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_session_cleared_after_logout(self, auth_client):
        with auth_client.session_transaction() as sess:
            assert "user_id" in sess  # logged in

        auth_client.get("/logout")

        with auth_client.session_transaction() as sess:
            assert "user_id" not in sess  # logged out

    def test_dashboard_inaccessible_after_logout(self, auth_client):
        auth_client.get("/logout")
        response = auth_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Already-authenticated user hitting GET /login
# ---------------------------------------------------------------------------

class TestAlreadyLoggedIn:
    """Visiting /login while already authenticated skips the form."""

    def test_redirects_to_dashboard(self, auth_client):
        response = auth_client.get("/login", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard" in response.headers["Location"]

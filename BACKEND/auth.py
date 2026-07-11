"""
auth.py
-------
Authentication blueprint — login, logout, and the login_required decorator.

Routes registered:
  GET  /login   → render the login form
  POST /login   → validate credentials and create a session
  GET  /logout  → clear the session and redirect to login

Decorator exported:
  login_required  → wraps any view that must be protected; redirects
                    unauthenticated visitors to /login

Security practices applied here:
  - Passwords are NEVER compared as plaintext.  werkzeug.security.check_password_hash
    is used exclusively.
  - The same generic error message is shown whether the username is wrong OR the
    password is wrong.  This prevents username enumeration attacks.
  - session.clear() on logout removes ALL session data, not just user_id.
  - Already-authenticated users hitting GET /login are redirected to the dashboard
    immediately so they do not see a stale login form.
"""

import functools

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database import get_db

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# login_required decorator
# ---------------------------------------------------------------------------

def login_required(view):
    """
    Decorator that protects a view from unauthenticated access.

    How it works:
      1. The wrapper runs before the wrapped view function.
      2. It checks whether 'user_id' is present in the Flask session.
      3. If absent → the user is not logged in → redirect to /login.
      4. If present → the user is authenticated → call the original view.

    Usage:
      @dashboard_bp.route('/dashboard')
      @login_required
      def dashboard():
          ...
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            # Preserve the originally-requested URL so we can redirect
            # back to it after a successful login (future enhancement).
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped_view


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    GET  /login  →  Render the login form.
                    If the user already has an active session, redirect to
                    the dashboard — they do not need to log in again.

    POST /login  →  Validate the submitted credentials.

                    Validation steps (server-side):
                      1. Neither username nor password may be blank.
                      2. A user row with the submitted username must exist.
                      3. The submitted password must match the stored hash.

                    On success  : write user_id to the session, redirect to /dashboard.
                    On failure  : flash a GENERIC error (same message for wrong
                                  username and wrong password), re-render the form.
    """

    # Already logged in — skip the form
    if session.get("user_id") is not None:
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        error = None

        # ── Step 1: blank-field validation ──────────────────────────────
        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."

        # ── Step 2 & 3: database lookup + hash comparison ───────────────
        if error is None:
            db = get_db()
            user = db.execute(
                "SELECT id, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            # Deliberate: same message for "user not found" and "wrong password"
            if user is None or not check_password_hash(user["password_hash"], password):
                error = "Invalid username or password. Please try again."

        # ── On failure: flash and re-render ─────────────────────────────
        if error is not None:
            flash(error, "danger")
            return render_template("login.html")

        # ── On success: create session and redirect ──────────────────────
        session.clear()                   # Drop any stale session data
        session["user_id"] = user["id"]   # type: ignore[index]  (user is not None here)
        session["username"] = username    # Stored for display in navbar/templates

        flash(f"Welcome back, {username}!", "success")
        return redirect(url_for("dashboard.dashboard"))

    # GET request — render empty form
    return render_template("login.html")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@auth_bp.route("/logout")
def logout():
    """
    Clear the session entirely and redirect to the login page.

    Using session.clear() (rather than deleting only user_id) ensures that
    no residual session data is left behind regardless of what other code
    may have stored in the session.
    """
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))

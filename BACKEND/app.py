"""
app.py
------
Flask application factory.

Responsibilities:
  - Build and return a fully configured Flask application object.
  - Point Flask at the correct template and static-file folders
    (which live in FRONTEND/, not next to app.py).
  - Load configuration (secret key, database path, session settings).
  - Register the three feature blueprints: auth, dashboard, transactions.
  - Register custom HTTP error handlers (404 and 500).
  - Initialise and seed the database on first run.

Usage:
  Development  →  python app.py          (runs with debug=True)
  Flask CLI    →  flask --app app run     (same effect)
  Tests        →  from app import create_app; app = create_app({'TESTING': True, ...})
"""

import os

from flask import Flask, render_template

from database import init_app, init_db, seed_db


def create_app(test_config=None):
    """
    Application factory.

    Parameters
    ----------
    test_config : dict, optional
        When provided (e.g. from a test suite), these values override the
        default configuration.  Typical overrides:
          TESTING  = True
          DATABASE = ':memory:'   ← in-process SQLite, discarded after the test

    Returns
    -------
    Flask
        A fully configured, ready-to-run Flask application instance.
    """

    # ------------------------------------------------------------------
    # 1. Instantiate Flask
    #    template_folder and static_folder are resolved relative to the
    #    directory that contains this file (BACKEND/).  Since FRONTEND/
    #    sits one level above BACKEND/, we climb up with '../'.
    # ------------------------------------------------------------------
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "FRONTEND", "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "FRONTEND", "static"),
        static_url_path="/static",
    )

    # ------------------------------------------------------------------
    # 2. Default configuration
    # ------------------------------------------------------------------
    app.config.from_mapping(
        # SECRET_KEY signs the session cookie.
        # In production, load this from an environment variable — never
        # hardcode a real secret here.
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production"),

        # Absolute path to the SQLite database file.
        # Stored in BACKEND/ alongside the Python source files.
        DATABASE=os.path.join(os.path.dirname(os.path.abspath(__file__)), "banking.db"),

        # Never expose tracebacks to the browser outside of development.
        DEBUG=False,

        # Security: session cookie is HTTP-only (not accessible from JS)
        SESSION_COOKIE_HTTPONLY=True,

        # Security: prevent the session cookie from being sent in
        # cross-site requests (CSRF mitigation)
        SESSION_COOKIE_SAMESITE="Lax",
    )

    # ------------------------------------------------------------------
    # 3. Override with test config when supplied by the test suite
    # ------------------------------------------------------------------
    if test_config is not None:
        app.config.from_mapping(test_config)

    # ------------------------------------------------------------------
    # 4. Register the database teardown hook
    #    close_db() will be called at the end of every request context.
    # ------------------------------------------------------------------
    init_app(app)

    # ------------------------------------------------------------------
    # 5. Register feature blueprints
    #    Order matters: auth must be first because dashboard and
    #    transactions import login_required from auth.
    # ------------------------------------------------------------------
    from auth import auth_bp
    from dashboard import dashboard_bp
    from transactions import transactions_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)

    # ------------------------------------------------------------------
    # 5b. Register a custom Jinja2 filter: currency
    #     Usage in templates: {{ balance | currency }}  →  "1,250.00"
    # ------------------------------------------------------------------
    @app.template_filter("currency")
    def currency_filter(value):
        """Format a float as a comma-separated 2-decimal-place string."""
        try:
            return "{:,.2f}".format(float(value))
        except (TypeError, ValueError):
            return "0.00"

    # ------------------------------------------------------------------
    # 6. Root redirect — send bare "/" to the login page
    # ------------------------------------------------------------------
    from flask import redirect, url_for

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    # ------------------------------------------------------------------
    # 7. Custom HTTP error handlers
    # ------------------------------------------------------------------

    @app.errorhandler(404)
    def page_not_found(error):
        """Friendly 404 page instead of Flask's default HTML."""
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        """Generic error page; the full traceback is logged server-side."""
        app.logger.error("Server error: %s", error)
        return render_template("500.html"), 500

    # ------------------------------------------------------------------
    # 8. Initialise and seed the database
    #    Must run inside an application context because get_db() relies
    #    on current_app.config and Flask's g object.
    # ------------------------------------------------------------------
    with app.app_context():
        init_db()
        seed_db()

    return app


# ----------------------------------------------------------------------
# Entry point for direct execution:  python app.py
# ----------------------------------------------------------------------
if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,   # Auto-reload on code changes; NEVER use in production
    )

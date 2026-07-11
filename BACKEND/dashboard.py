"""
dashboard.py
------------
Dashboard blueprint — the customer's home screen after login.

Routes registered:
  GET /dashboard  →  display customer name and current account balance

The route is protected with @login_required from auth.py.  Any request that
arrives without a valid session is redirected to /login before this view
function is even called.

Data passed to the template:
  username  : str   — the customer's login name, used for a personalised greeting
  balance   : float — current account balance, formatted to 2 d.p. in the template
  transactions : list[sqlite3.Row] — the 10 most recent transactions for the mini
                                     history panel on the dashboard
"""

from flask import Blueprint, render_template, session

from auth import login_required
from database import get_balance, get_db

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

dashboard_bp = Blueprint("dashboard", __name__)


# ---------------------------------------------------------------------------
# Dashboard route
# ---------------------------------------------------------------------------

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    """
    Render the customer dashboard.

    Logic:
      1. Read user_id and username from the session (set at login).
      2. Call get_balance(user_id) to fetch the up-to-date balance from the DB.
         The balance is NEVER stored in the session — always read fresh so that
         deposit/withdrawal updates are reflected immediately.
      3. Fetch the 10 most recent transaction rows for this user so the customer
         can see a short activity history without navigating away.
      4. Pass all data to dashboard.html via render_template keyword arguments.
    """
    user_id  = session["user_id"]
    username = session.get("username", "Customer")

    # Current balance — always fetched from the database, never from the session
    balance = get_balance(user_id)

    # Recent transaction history (newest first, capped at 10 rows)
    db = get_db()
    recent_transactions = db.execute(
        """
        SELECT transaction_type, amount, timestamp
        FROM   transactions
        WHERE  user_id = ?
        ORDER  BY id DESC
        LIMIT  10
        """,
        (user_id,),
    ).fetchall()

    return render_template(
        "dashboard.html",
        username=username,
        balance=balance,
        transactions=recent_transactions,
    )

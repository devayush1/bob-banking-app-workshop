"""
transactions.py
---------------
Transactions blueprint — deposit and withdrawal routes.

Routes registered:
  GET  /deposit   →  render the deposit form
  POST /deposit   →  validate and process a deposit
  GET  /withdraw  →  render the withdrawal form (includes current balance)
  POST /withdraw  →  validate and process a withdrawal

Both routes are protected with @login_required.

Validation sequence (server-side — not bypassed by browser constraints):
  Deposit:
    1. Amount field is not empty
    2. Amount is a valid number (float conversion succeeds)
    3. Amount is greater than 0

  Withdrawal (all deposit checks, plus):
    4. Amount does not exceed the current balance
       → balance is fetched BEFORE calling update_balance so it is never
         temporarily negative

On success the session balance is NOT updated — the dashboard re-reads from
the database on every load, so the customer always sees the authoritative value.
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from auth import login_required
from database import get_balance, update_balance

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

transactions_bp = Blueprint("transactions", __name__)


# ---------------------------------------------------------------------------
# Shared validation helper
# ---------------------------------------------------------------------------

def _parse_amount(raw):
    """
    Parse and validate a raw string amount from a form field.

    Returns
    -------
    (float, None)   if the value is valid (numeric and > 0)
    (None, str)     if invalid — the string is the error message to flash

    Rounding to 2 decimal places happens here so that the number stored
    in the database is always clean (e.g. 100.0, not 99.999999999).
    """
    if not raw or not raw.strip():
        return None, "Amount is required."

    try:
        amount = float(raw.strip())
    except ValueError:
        return None, "Amount must be a valid number."

    if amount <= 0:
        return None, "Amount must be greater than zero."

    # Round to 2 decimal places to prevent floating-point drift
    amount = round(amount, 2)
    return amount, None


# ---------------------------------------------------------------------------
# Deposit routes
# ---------------------------------------------------------------------------

@transactions_bp.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """
    GET  /deposit  →  Render the empty deposit form.

    POST /deposit  →  Validate and apply the deposit.
      1. Parse the submitted 'amount' field with _parse_amount().
      2. On validation error: flash the error message, re-render the form.
      3. On success: call update_balance() with a positive delta, flash a
         success message, redirect to /dashboard.
    """
    if request.method == "POST":
        raw    = request.form.get("amount", "")
        amount, error = _parse_amount(raw)

        if error:
            flash(error, "danger")
            return render_template("deposit.html")

        user_id = session["user_id"]
        update_balance(user_id, amount, "deposit")

        flash(f"Successfully deposited ${amount:,.2f} to your account.", "success")
        return redirect(url_for("dashboard.dashboard"))

    # GET — render the empty form
    return render_template("deposit.html")


# ---------------------------------------------------------------------------
# Withdrawal routes
# ---------------------------------------------------------------------------

@transactions_bp.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    """
    GET  /withdraw  →  Render the withdrawal form.
                       Current balance is passed to the template so the
                       customer can see their limit before submitting.

    POST /withdraw  →  Validate and apply the withdrawal.
      1. Parse the submitted 'amount' field with _parse_amount().
      2. Fetch the current balance from the database.
      3. If amount > balance: flash "Insufficient funds", re-render — do NOT
         call update_balance.
      4. On success: call update_balance() with a NEGATIVE delta (reduces the
         balance), flash a success message, redirect to /dashboard.
    """
    user_id = session["user_id"]
    balance = get_balance(user_id)   # Needed for both GET and POST (display + check)

    if request.method == "POST":
        raw    = request.form.get("amount", "")

        # Explicit validation checks
        if not raw or not raw.strip():
            flash("Amount is required", "danger")
            return render_template("withdraw.html", balance=balance)

        try:
            _amount_val = float(raw.strip())
        except ValueError:
            _amount_val = 0

        if _amount_val <= 0:
            flash("Amount must be greater than zero", "danger")
            return render_template("withdraw.html", balance=balance)

        if _amount_val > balance:
            flash("Insufficient funds", "danger")
            return render_template("withdraw.html", balance=balance)
        amount, error = _parse_amount(raw)

        if error:
            flash(error, "danger")
            return render_template("withdraw.html", balance=balance)

        # Insufficient funds check — must happen before update_balance
        if amount > balance:
            flash(
                f"Insufficient funds. Your current balance is ${balance:,.2f}.",
                "danger",
            )
            return render_template("withdraw.html", balance=balance)

        # All checks passed — apply the withdrawal (negative delta)
        update_balance(user_id, -amount, "withdrawal")

        flash(f"Successfully withdrew ${amount:,.2f} from your account.", "success")
        return redirect(url_for("dashboard.dashboard"))

    # GET — render the form with current balance shown as the limit
    return render_template("withdraw.html", balance=balance)

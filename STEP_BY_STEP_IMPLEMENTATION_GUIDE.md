# Banking Web Application — Step-by-Step Implementation Guide

> **Reference:** This guide follows the phases defined in `IMPLEMENTATION_PLAN.md`.
> All instructions are written in plain English — they describe *what to do* and *why*, not the literal code.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Backend Implementation](#2-backend-implementation)
3. [Frontend Implementation](#3-frontend-implementation)
4. [Integration Steps](#4-integration-steps)
5. [Validation Rules](#5-validation-rules)
6. [Testing](#6-testing)
7. [Deployment](#7-deployment)

---

## 1. Environment Setup

### 1.1 Prerequisites Check

Before writing a single line of code, confirm the following tools are available on your machine:

- **Python 3.9 or later** — Flask requires a reasonably modern Python. Run `python3 --version` in a terminal to verify.
- **pip** — Python's package manager, bundled with Python. Run `pip3 --version` to confirm.
- **A text editor or IDE** — VS Code, PyCharm, or any editor of your choice.

You do not need Node.js, Docker, or any other runtime. SQLite is built into Python's standard library, so no separate database installation is required.

---

### 1.2 Create the Project Directory Structure

Manually create the top-level folders exactly as described in the implementation plan:

```
project-root/
├── FRONTEND/
│   ├── templates/
│   └── static/
│       └── css/
└── BACKEND/
```

The `FRONTEND/templates/` folder is where Flask will look for HTML files.
The `FRONTEND/static/css/` folder will hold optional custom CSS.
The `BACKEND/` folder will hold all Python files and the SQLite database.

Creating the structure upfront prevents import errors and missing-template errors later.

---

### 1.3 Create a Python Virtual Environment

A virtual environment is an isolated Python installation that keeps your project's dependencies separate from every other project on your machine.

**How to think about it:** Imagine each project having its own private copy of Python and its packages. Installing Flask inside the virtual environment means it will not interfere with any other Python project and the versions are locked to exactly what your project needs.

Steps:
1. Open a terminal and navigate to the `BACKEND/` folder.
2. Ask Python to create a virtual environment folder (commonly named `venv`) inside `BACKEND/`.
3. Activate the virtual environment. On macOS/Linux you source an activation script; on Windows you run a `.bat` file. Once activated, your terminal prompt will show the environment name as a prefix.
4. From this point on, every `pip install` command will install packages only into this environment.

> **Important:** Always activate the virtual environment before running the Flask app or installing packages. If you open a new terminal window, you must activate it again.

---

### 1.4 Create `requirements.txt`

The `requirements.txt` file lists every Python package the project needs. This file serves two purposes: it documents your dependencies, and it lets anyone else set up the project with a single command.

For this application, you need:

| Package | Why |
|---|---|
| `flask` | The web framework that handles routing, sessions, and template rendering |
| `werkzeug` | Comes with Flask; provides the password hashing utilities you will use directly |

Write the package names (with pinned or minimum version numbers) into `BACKEND/requirements.txt`, one package per line.

---

### 1.5 Install Dependencies

With the virtual environment active, run pip to install everything listed in `requirements.txt`. Pip will resolve and download Flask, Werkzeug, and all of their own internal dependencies automatically.

Verify the installation by asking pip to list installed packages and confirming Flask appears in the output.

---

### 1.6 Verify Flask is Working

Create a temporary, minimal Python file that imports Flask and starts the development server on a port of your choosing (the default is 5000). Open a browser and navigate to `http://localhost:5000`. If you see any response (even a blank page or a 404), Flask is running correctly. Delete the temporary file before continuing.

---

## 2. Backend Implementation

All backend files live in the `BACKEND/` folder. The implementation follows a layered approach: database helpers first, then the Flask application factory, then individual feature modules (blueprints).

---

### 2.1 Database Layer (`database.py`)

**Purpose:** Centralise every interaction with SQLite so that route handlers never write raw database calls themselves.

#### 2.1.1 Understanding the Database Connection Pattern

SQLite works with a *connection object*. You open a connection, run queries through it, commit changes, and close it. Flask's request context is the right scope for a connection: open it at the start of a request, use it throughout, close it when the response is sent.

Flask provides a `g` object — a request-scoped storage bag. Store the open database connection on `g` at the start of a request so any function within that request can retrieve it without opening a second connection.

#### 2.1.2 `get_db()` — Connection Helper

Write a function called `get_db()`. Its logic:

1. Check whether a connection already exists on `g`. If yes, return it immediately (do not open a second one).
2. If no connection exists, open a new SQLite connection pointing at `BACKEND/banking.db` (use the database path from the Flask app config so it is easy to change later).
3. Tell SQLite to use `sqlite3.Row` as the row factory. This makes query results behave like dictionaries so you can access columns by name (e.g., `row['balance']`) rather than by index.
4. Store the connection on `g` and return it.

Then register a *teardown function* on the app that runs automatically at the end of every request. This function checks whether a connection is stored on `g` and, if so, closes it. This ensures connections are never leaked.

#### 2.1.3 `init_db()` — Schema Creation

Write a function called `init_db()`. Its logic:

1. Call `get_db()` to obtain a connection.
2. Execute SQL statements that create three tables *if they do not already exist* (idempotent — safe to run multiple times):
   - **users** — stores the customer's username and hashed password.
   - **accounts** — stores the current balance, linked to a user by a foreign key.
   - **transactions** — stores an immutable record of every deposit and withdrawal (amount, type, timestamp, foreign key to users).
3. Commit the connection to persist the schema.

Call `init_db()` from `app.py` during application startup so the tables are always ready before the first request arrives.

#### 2.1.4 `seed_db()` — Demo Data

Write a function called `seed_db()`. Its logic:

1. Check whether the users table already has rows. If it does, return immediately (do not insert duplicates).
2. Hash a known demo password using `werkzeug.security.generate_password_hash`.
3. Insert one demo user row with a username and the hashed password.
4. Insert one matching account row with a starting balance (e.g., 1000.00) linked to the new user.
5. Commit.

Call `seed_db()` right after `init_db()` in `app.py`. This guarantees that on a fresh install you can immediately log in with the demo credentials without manually fiddling with the database.

#### 2.1.5 `get_balance(user_id)` — Balance Read

Write a helper function that accepts a `user_id`, queries the accounts table for the matching row, and returns the balance as a float. This function is called by the dashboard route and by the withdrawal validation logic.

#### 2.1.6 `update_balance(user_id, delta, transaction_type)` — Balance Write

Write a helper function that accepts a `user_id`, a `delta` amount (positive for deposit, negative for withdrawal), and a `transaction_type` string (e.g. `"deposit"` or `"withdrawal"`). Its logic:

1. Get a database connection.
2. **Open an explicit transaction** (SQLite's default autocommit must be disabled for this operation — use a `BEGIN` or rely on the connection's transaction context).
3. Update the accounts table by adding `delta` to the existing balance for the given `user_id`.
4. Insert a new row into the transactions table recording the amount (store as positive), type, and the current timestamp.
5. Commit. If any step fails, roll back — this is what keeps the balance correct even on errors.

---

### 2.2 Flask Application Factory (`app.py`)

**Purpose:** Create and configure the Flask application object; register all blueprints; run startup tasks.

#### 2.2.1 What a Factory Pattern Means

Instead of creating the Flask app at the top level of a module (which can cause circular import issues), you define a function — often called `create_app()` — that builds and returns the configured app. This also makes testing easier because tests can call `create_app()` with test-specific settings.

#### 2.2.2 Configuration

Inside `create_app()`:

1. Instantiate the Flask class, telling it where to find templates (the `FRONTEND/templates/` directory) and static files (`FRONTEND/static/`). Flask's constructor accepts `template_folder` and `static_folder` keyword arguments for exactly this purpose.
2. Set a `SECRET_KEY` in the app config. Flask uses this key to cryptographically sign session cookies. Without it sessions cannot be trusted. For development, any long random string is fine. For production, this must be a strong random value loaded from an environment variable — never hardcoded.
3. Set a `DATABASE` config key pointing to the absolute path of `banking.db` inside the `BACKEND/` folder. Using an absolute path avoids ambiguity about the current working directory.

#### 2.2.3 Blueprint Registration

Import and register each feature blueprint (auth, dashboard, transactions). Blueprints are Flask's way of splitting routes across multiple files. Registering a blueprint means Flask learns all the routes defined in that module.

#### 2.2.4 Startup Tasks

After registering blueprints, call `init_db()` and `seed_db()` inside an `app.app_context()` block. Flask's application context must be pushed before any database or application-level work can happen outside of a request.

#### 2.2.5 Running the App

At the bottom of `app.py`, add the standard `if __name__ == '__main__':` guard that calls `app.run(debug=True)`. `debug=True` enables the auto-reloader (the server restarts when you save a file) and the interactive debugger. Never use `debug=True` in production.

---

### 2.3 Authentication Module (`auth.py`)

**Purpose:** Handle login, logout, and protect every other route from unauthenticated access.

#### 2.3.1 Create the Blueprint

A Flask Blueprint is a collection of routes that can be registered on the main app. Create a blueprint called `auth` with a URL prefix of `/` or no prefix, so `/login` and `/logout` are at the root level.

#### 2.3.2 `login_required` Decorator

Write a Python decorator called `login_required`. A decorator is a function that wraps another function to add behaviour before or after it runs.

Logic:
1. The decorator's inner wrapper function runs first.
2. It checks whether `user_id` exists in Flask's `session` dictionary.
3. If the key is absent (user is not logged in), redirect immediately to the login page and return — the original view function never runs.
4. If the key is present, call the original view function and return its result normally.

Any protected route simply adds `@login_required` above its function definition.

#### 2.3.3 Login Route — GET

When a browser navigates to `/login` with a GET request:
- If the user already has an active session (they are already logged in), redirect straight to the dashboard — no need to show the login form again.
- Otherwise, render the `login.html` template and return it.

#### 2.3.4 Login Route — POST

When the login form is submitted (POST to `/login`):

1. Extract the `username` and `password` fields from the submitted form data.
2. Validate that neither field is empty. If either is blank, flash an appropriate error message and re-render the login page.
3. Query the users table for a row matching the submitted username. If no row is found, flash a generic "invalid credentials" message (do not reveal whether the username or password was wrong — this is a security best practice) and re-render.
4. Use `werkzeug.security.check_password_hash` to compare the submitted password against the stored hash. If the check fails, flash the same generic error and re-render.
5. If authentication succeeds, store the user's `id` in `session['user_id']`. Redirect to the dashboard.

#### 2.3.5 Logout Route

When a GET or POST request hits `/logout`:

1. Call `session.clear()` to remove all session data, including `user_id`.
2. Flash a "You have been logged out" message.
3. Redirect to the login page.

---

### 2.4 Dashboard Module (`dashboard.py`)

**Purpose:** Show the customer a summary of their account after login.

#### 2.4.1 Create the Blueprint

Create a blueprint called `dashboard`. Register it in `app.py` with no URL prefix, so the dashboard lives at `/dashboard`.

#### 2.4.2 Dashboard Route — GET

This route is protected with `@login_required`.

Logic:
1. Read `session['user_id']` to know which customer is logged in.
2. Call `get_balance(user_id)` from `database.py` to retrieve the current balance.
3. Also query the users table to get the customer's display name (username or full name).
4. Pass both values into the `dashboard.html` template using the `render_template` function.
5. The template will display a personalised greeting and the formatted balance.

---

### 2.5 Transactions Module (`transactions.py`)

**Purpose:** Process deposit and withdrawal requests with proper validation and atomic database writes.

#### 2.5.1 Create the Blueprint

Create a blueprint called `transactions`. Both deposit and withdrawal routes will live here.

#### 2.5.2 Deposit Routes

**GET `/deposit`** — Protected by `@login_required`. Simply render the `deposit.html` template (the empty form).

**POST `/deposit`** — Protected by `@login_required`. Logic:

1. Extract the `amount` field from the submitted form data (it arrives as a string).
2. Attempt to convert it to a float. If the conversion fails (the user typed letters), flash an error and re-render the deposit form.
3. Check that the converted amount is greater than zero. A zero or negative deposit is not meaningful; flash an error and re-render.
4. Call `update_balance(user_id, amount, "deposit")` from `database.py`.
5. Flash a success message showing how much was deposited.
6. Redirect to the dashboard so the customer can see the updated balance immediately.

#### 2.5.3 Withdrawal Routes

**GET `/withdraw`** — Protected by `@login_required`. Render the `withdraw.html` template.

**POST `/withdraw`** — Protected by `@login_required`. Logic:

1. Extract and attempt to convert the `amount` field to a float. Flash an error and re-render on failure.
2. Check that the amount is greater than zero. Flash an error and re-render if not.
3. Call `get_balance(user_id)` to fetch the current balance.
4. Compare the requested amount against the current balance. If `amount > balance`, flash an "insufficient funds" error and re-render the withdrawal form — **do not call `update_balance`**.
5. If all checks pass, call `update_balance(user_id, -amount, "withdrawal")` (the negative sign reduces the balance).
6. Flash a success message and redirect to the dashboard.

---

### 2.6 Session Management — How It Works

Flask's session is a *signed cookie* stored in the browser. When you write `session['user_id'] = 123`, Flask serialises that dictionary, signs it with the `SECRET_KEY`, and sends it to the browser as a cookie named `session`. On the next request the browser sends the cookie back; Flask verifies the signature, and if it is valid, deserialises the dictionary back. No session data is stored server-side.

Key points for this application:
- The session persists until the browser is closed (by default) or until `session.clear()` is called.
- Because the session is signed, a user cannot tamper with it (they cannot change `user_id` to impersonate another user).
- The `SECRET_KEY` must remain secret — anyone who knows it can forge sessions.

---

### 2.7 Error Handling Strategy

Flask's error handling works at two levels:

**Flash messages (user-facing validation errors):**
Use Flask's `flash(message, category)` function for errors the user caused and can fix. Categories are typically `"success"`, `"danger"`, or `"warning"` (Bootstrap alert class names). The base template will loop over all pending flash messages and display them as Bootstrap alerts at the top of every page.

**HTTP error pages:**
Register custom error handlers on the app for common HTTP error codes:
- **404 Not Found** — When a URL does not match any route. Render a friendly "page not found" template.
- **500 Internal Server Error** — When an unhandled exception occurs. Render a generic error template. In production, also log the exception.

Unhandled exceptions in a route function will automatically trigger the 500 handler.

---

## 3. Frontend Implementation

All HTML templates live in `FRONTEND/templates/`. Flask's Jinja2 engine renders them server-side, injecting Python variables into the HTML before sending it to the browser.

---

### 3.1 Understanding Jinja2 Template Inheritance

Jinja2 supports a concept called *template inheritance*. One base template defines the overall page layout, and child templates *extend* it by filling in named content blocks.

- `{{ variable }}` — renders a Python variable as text.
- `{% block name %}{% endblock %}` — defines a replaceable region.
- `{% extends "base.html" %}` — declares that a template inherits from `base.html`.
- `{% for item in list %}` / `{% if condition %}` — control flow inside templates.

---

### 3.2 Base Layout (`base.html`)

**Purpose:** Define the HTML skeleton shared by every page. Every other template extends this file.

#### What to include:

1. **DOCTYPE and `<html>` tag** with language attribute.
2. **`<head>` block** containing:
   - Character set and viewport meta tags (the viewport tag is required for Bootstrap's responsive behaviour).
   - The Bootstrap 5 CSS CDN link.
   - A `{% block title %}` region so child templates can set a custom page title.
3. **`<body>`** containing:
   - A Bootstrap `<nav>` bar showing the application name ("My Bank") and, if the user is logged in, their username and a Logout link. Use Jinja2's `session` object (Flask makes it available in templates) to check whether a user is logged in.
   - A **flash messages block** — loop over the messages returned by `get_flashed_messages(with_categories=True)` and render each as a Bootstrap alert inside a container div. Flash messages are consumed once read, so they only appear on the next page load after being set.
   - A `{% block content %}{% endblock %}` region where each child template injects its main body.
4. **Bootstrap JS bundle** CDN link at the bottom of `<body>` (required for interactive components like dismissible alerts).

---

### 3.3 Login Page (`login.html`)

**Purpose:** Collect username and password and submit them to the backend.

#### Layout logic:

1. Extend `base.html` and set the title block to "Login".
2. In the content block, create a centred Bootstrap card (use the grid to centre it horizontally, e.g., `col-md-4 offset-md-4`).
3. Inside the card, place the application logo or name as a heading.
4. Create an HTML `<form>` with `method="POST"` and `action="/login"`.
5. Add a Bootstrap form group with a labelled text input for `username`.
6. Add a Bootstrap form group with a labelled password input for `password`.
7. Add a submit button styled as a Bootstrap primary button with the text "Login".

**No JavaScript needed.** The form submits normally and the server re-renders the page with flash messages if login fails.

---

### 3.4 Dashboard Page (`dashboard.html`)

**Purpose:** Welcome the customer and give them a clear view of their balance with navigation to actions.

#### Layout logic:

1. Extend `base.html` and set the title to "Dashboard".
2. In the content block, show a greeting: "Welcome, {{ username }}".
3. Display the account balance inside a Bootstrap card or `jumbotron`-style section. Format the balance to two decimal places using Jinja2's `round` filter or a custom filter. Add a currency symbol.
4. Add two Bootstrap buttons below the balance: one linking to `/deposit` and one linking to `/withdraw`. Style them distinctly (e.g., success green for deposit, warning yellow for withdraw).
5. The logout link is already in the navbar from `base.html`, so no extra logout button is required.

---

### 3.5 Deposit Form (`deposit.html`)

**Purpose:** Let the customer enter an amount to deposit.

#### Layout logic:

1. Extend `base.html`. Set the title to "Deposit Funds".
2. Centre a Bootstrap card. Include a heading "Deposit Funds".
3. Create a form with `method="POST"` and `action="/deposit"`.
4. Add a single Bootstrap form group: a labelled numeric input for `amount` with a helpful placeholder (e.g., "Enter amount to deposit"). Set `min="0.01"` and `step="0.01"` as HTML attributes so the browser provides basic numeric validation before submitting.
5. Add a submit button ("Deposit") and a secondary "Cancel" button or link that navigates back to `/dashboard`.

---

### 3.6 Withdrawal Form (`withdraw.html`)

**Purpose:** Let the customer enter an amount to withdraw.

#### Layout logic:

1. Same structure as the deposit form.
2. Change the heading to "Withdraw Funds", the action to `/withdraw`, the placeholder text, and the submit button label to "Withdraw".
3. Optionally display the current balance above the form field (pass it from the route) so the customer knows their limit before submitting.

---

### 3.7 Bootstrap Layout Principles Applied

Understand these Bootstrap concepts before writing any template HTML:

| Concept | How it is used here |
|---|---|
| **Container** | Wrap all page content in `<div class="container">` to give it a maximum width and centred margins. |
| **Grid** | Use `row` and `col-*` classes to control column widths. For forms, a column of width 4–6 centred with `offset-*` looks clean. |
| **Cards** | Use `card`, `card-body`, `card-title` for the login form and balance display blocks. |
| **Alerts** | Use `alert alert-{category}` for flash messages. Add the `alert-dismissible` and `fade show` classes plus a close button so users can dismiss them. |
| **Buttons** | Use `btn btn-primary` (login, deposit), `btn btn-warning` (withdraw), `btn btn-secondary` (cancel). |
| **Forms** | Use `mb-3`, `form-label`, `form-control` for consistent vertical spacing and styled inputs. |

---

## 4. Integration Steps

### 4.1 Connecting Flask to the Template Folder

By default Flask looks for templates in a folder named `templates/` next to `app.py`. Because your templates are in `FRONTEND/templates/`, you must override this by passing `template_folder='../FRONTEND/templates'` (a relative path from `BACKEND/`) to the Flask constructor in `app.py`. Similarly pass `static_folder='../FRONTEND/static'` for CSS files.

Verify this is working by navigating to any route after adding the first template — if Flask raises a `TemplateNotFound` error, the path is wrong.

---

### 4.2 Connecting HTML Forms to Flask Routes

Every HTML form needs exactly two attributes to work with Flask:

- `method="POST"` — tells the browser to send the data as a POST request body.
- `action="/route-path"` — tells the browser which URL to send the request to.

The `name` attribute on each `<input>` element is the key you will use to retrieve the value in Flask via `request.form['name']`. Make sure the names in your templates match the keys your Python code reads.

For links (navigation between pages), use Flask's `url_for('blueprint_name.function_name')` inside Jinja2 template expressions instead of hardcoding paths. This ensures links stay correct if you ever rename a route.

---

### 4.3 Connecting Flask to SQLite

The connection is made in `database.py` using Python's built-in `sqlite3` module — no extra installation required. The `get_db()` function (described in Section 2.1.2) handles opening and caching the connection. All route handlers call this function to get a connection; they never open their own.

The database file path is stored in `app.config['DATABASE']`. Use Python's `os.path` module to build an absolute path so SQLite always finds the file regardless of which directory you launch the app from.

---

### 4.4 Passing Data from Backend to Frontend

Flask's `render_template()` function accepts keyword arguments that become variables inside the Jinja2 template. For example, passing `balance=1250.00` makes `{{ balance }}` in the template render as `1250.0`.

The session object is automatically available in all templates — you do not need to pass it explicitly. Access it with `session.get('user_id')` inside a template condition.

Flash messages are accessed in templates via `get_flashed_messages(with_categories=True)`, which returns a list of `(category, message)` tuples. Loop over this in `base.html` to render alerts.

---

### 4.5 Blueprint Registration Order

Register blueprints in `app.py` in a specific order to avoid confusion:

1. `auth` blueprint first — it defines the `login_required` decorator that other blueprints import.
2. `dashboard` blueprint second.
3. `transactions` blueprint third.

If a blueprint imports from `auth.py`, and `auth.py` imports from `app.py`, you may encounter circular imports. Avoid this by keeping `login_required` in `auth.py` and having other blueprints import *from `auth`*, not from `app`.

---

## 5. Validation Rules

Validation happens at two levels: the browser (HTML attributes) and the server (Python logic). Browser validation is a convenience — never rely on it for security, because anyone can bypass it by crafting a direct HTTP request.

---

### 5.1 Login Validation

| Rule | Where enforced | What happens on failure |
|---|---|---|
| Username field must not be empty | Server | Flash error; re-render login page |
| Password field must not be empty | Server | Flash error; re-render login page |
| Username must exist in the database | Server | Flash generic "invalid credentials"; re-render |
| Password must match the stored hash | Server | Flash generic "invalid credentials"; re-render |

**Security note:** Always use the *same* error message for "username not found" and "password wrong". Different messages let an attacker enumerate valid usernames.

**Never** compare the submitted password as plaintext. Always use `check_password_hash(stored_hash, submitted_password)`.

---

### 5.2 Balance Validation

| Rule | Where enforced | What happens on failure |
|---|---|---|
| Balance must be read only for the authenticated user | Server (session check) | Redirect to login if session is invalid |
| Balance display must be formatted to 2 decimal places | Frontend (Jinja2 filter) | Cosmetic; no security impact |

The balance is never accepted from the user as input — it is always read from the database. This prevents tampering.

---

### 5.3 Deposit Validation

| Rule | Where enforced | What happens on failure |
|---|---|---|
| Amount field must not be empty | Browser (`required` attribute) + Server | Browser blocks submission; server flashes error |
| Amount must be a valid number | Browser (`type="number"`) + Server (try/except) | Browser blocks; server catches conversion error |
| Amount must be greater than zero | Server | Flash "Amount must be positive"; re-render deposit form |
| Amount must have at most 2 decimal places | Server (round to 2 dp before storing) | Silent correction or flash warning — choose one |

The server-side check is the authoritative one. The HTML `type="number"` and `min` attributes are UI helpers only.

---

### 5.4 Withdrawal Validation

All deposit rules apply, plus:

| Rule | Where enforced | What happens on failure |
|---|---|---|
| Amount must not exceed current balance | Server | Flash "Insufficient funds"; re-render withdraw form; **do not update balance** |

The sequence matters: fetch the balance *before* calling `update_balance`. Do not update and then check — that would allow the balance to temporarily go negative.

---

### 5.5 Session Validation

| Rule | Where enforced | What happens on failure |
|---|---|---|
| Every protected route must check for `session['user_id']` | `login_required` decorator | Redirect to `/login` |
| Session data must not be trusted for business-critical values | Server | Always re-read balance from DB; never store it in the session |

---

## 6. Testing

Testing is split into three categories: unit tests (isolated logic), integration tests (multiple components working together), and a manual testing checklist (human-verified UI journeys).

---

### 6.1 Unit Tests

Unit tests verify individual functions in isolation, without starting the Flask server or touching the real database.

#### What to use

Python's built-in `unittest` module is sufficient. You may also use `pytest` (installable via pip) for simpler test syntax.

#### What to unit-test

**`database.py` functions:**
- `get_balance` — Pass a mock user_id; verify the returned value matches the value in an in-memory test database.
- `update_balance` — After calling it with a positive delta, verify the balance increased by exactly that amount. After calling it with a negative delta, verify the balance decreased. After a failed call (simulate a DB error), verify the balance is unchanged (rollback test).

**`auth.py` validation logic:**
- Test the logic that checks for empty username/password fields — this can be extracted into a pure function and tested without HTTP.
- Test that `check_password_hash` behaves correctly with a known hash/password pair.

**`transactions.py` validation logic:**
- Test amount parsing (valid float string → float; non-numeric string → error).
- Test the "amount > 0" check.
- Test the "amount ≤ balance" check.

#### How to structure tests

Create a `BACKEND/tests/` folder. Each test file mirrors the module it tests:
- `test_database.py` — tests for `database.py`
- `test_auth.py` — tests for auth logic
- `test_transactions.py` — tests for transaction validation

Each test function's name starts with `test_` so the test runner discovers it automatically.

---

### 6.2 Integration Tests

Integration tests run actual HTTP requests against a test instance of the Flask app and verify the responses.

#### Flask's Built-in Test Client

Flask provides a test client that simulates a browser without opening a real network port. You create the app in test mode (set `TESTING=True` in config), get the test client, and call methods like `client.get('/login')` or `client.post('/deposit', data={'amount': '100'})`.

#### Test Setup

Before each test, create a fresh in-memory SQLite database (set `DATABASE=':memory:'` in test config), call `init_db()` and `seed_db()` to populate it with known data, then run the test.

After each test, drop everything and start fresh. This keeps tests independent.

#### What to integration-test

| Scenario | Expected result |
|---|---|
| GET `/login` as anonymous user | Returns 200, login page HTML |
| POST `/login` with valid credentials | Redirects (302) to `/dashboard`; session contains `user_id` |
| POST `/login` with wrong password | Returns 200, login page re-rendered, flash message present |
| GET `/dashboard` without session | Redirects (302) to `/login` |
| GET `/dashboard` with valid session | Returns 200, balance visible in response |
| POST `/deposit` with valid amount | Redirects to `/dashboard`; balance in next GET is higher |
| POST `/deposit` with negative amount | Returns 200, error flash in response |
| POST `/withdraw` within balance | Redirects to dashboard; balance lower |
| POST `/withdraw` exceeding balance | Returns 200 (re-render), "insufficient funds" flash |
| GET `/logout` | Session cleared; redirect to login |

---

### 6.3 Manual Testing Checklist

Run through this checklist in a real browser after completing development. Tick each item only when the observed behaviour matches the expected behaviour.

#### Authentication
- [ ] Navigating to `/dashboard` without being logged in redirects to `/login`.
- [ ] Submitting the login form with a blank username shows an error message.
- [ ] Submitting the login form with a blank password shows an error message.
- [ ] Submitting with a wrong username or wrong password shows a generic error (same message in both cases).
- [ ] Submitting with correct credentials lands on the dashboard.
- [ ] Clicking Logout clears the session and lands on the login page.
- [ ] After logout, pressing the browser Back button and then refreshing does not restore the session.

#### Dashboard
- [ ] The dashboard shows the correct customer name.
- [ ] The balance is displayed formatted to two decimal places with a currency symbol.
- [ ] Deposit and Withdraw navigation links are visible and clickable.

#### Deposit
- [ ] Navigating to `/deposit` without being logged in redirects to login.
- [ ] Submitting the deposit form with no amount shows an error.
- [ ] Submitting with a non-numeric value (e.g., "abc") shows an error.
- [ ] Submitting with a negative amount (e.g., "-50") shows an error.
- [ ] Submitting with zero shows an error.
- [ ] Submitting with a valid amount (e.g., "200") redirects to the dashboard with a success message and the balance has increased by exactly that amount.

#### Withdrawal
- [ ] Submitting the withdraw form with no amount shows an error.
- [ ] Submitting with a non-numeric value shows an error.
- [ ] Submitting with a negative amount shows an error.
- [ ] Submitting with zero shows an error.
- [ ] Submitting an amount greater than the current balance shows "Insufficient funds" and the balance is unchanged.
- [ ] Submitting a valid amount within the balance redirects to dashboard with a success message and the balance is reduced by exactly that amount.

#### UI / Responsiveness
- [ ] All pages render without horizontal scroll on a desktop viewport.
- [ ] Resize the browser to a narrow width (simulate mobile); the layout does not break.
- [ ] Flash messages appear at the top of the page and can be dismissed.
- [ ] All navigation links in the navbar work correctly.

---

## 7. Deployment

### 7.1 Running Locally (Development)

**Step-by-step:**

1. Open a terminal and navigate to the `BACKEND/` folder.
2. Activate the virtual environment (see Section 1.3).
3. Run the Flask application by executing `app.py` with Python, or by using the Flask CLI (`flask run`). If using the CLI, set the `FLASK_APP` environment variable to `app.py` first.
4. Flask will print the local URL it is serving on (usually `http://127.0.0.1:5000`).
5. Open that URL in your browser. The database is initialised and seeded automatically on first run.
6. To stop the server, press `Ctrl+C` in the terminal.

**Development tips:**
- `debug=True` is set in `app.run()`. This enables auto-reload — the server restarts automatically when you save any Python file, so you do not need to restart it manually after every change.
- Template changes do not require a restart; Jinja2 re-reads templates on every request in debug mode.
- If you corrupt the database, simply delete `banking.db` and restart the server — `init_db()` and `seed_db()` will recreate it.

---

### 7.2 Production Considerations

The development server built into Flask is **not suitable for production**. It handles only one request at a time and has known security limitations. The following changes are required before deploying to any environment accessed by real users.

#### Use a Production WSGI Server

Flask's development server is replaced by a production-grade WSGI server. Common choices are **Gunicorn** (Linux/macOS) or **Waitress** (Windows-compatible). Install one via pip and configure it to serve `app:create_app()`. A WSGI server handles multiple concurrent requests and is far more stable.

#### Set the Secret Key from an Environment Variable

Never hardcode the `SECRET_KEY` in `app.py`. In production, read it from an environment variable:

- Set an environment variable on the server (e.g., `export SECRET_KEY="some-long-random-string"`).
- In `app.py`, read it with `os.environ.get('SECRET_KEY')`.
- If the variable is missing, raise a clear error at startup — do not fall back to a default.

#### Use HTTPS

The session cookie must only travel over an encrypted connection. Configure your web server (Nginx, Apache, or a cloud load balancer) to terminate TLS and forward requests to Gunicorn over HTTP on localhost. Set Flask's `SESSION_COOKIE_SECURE = True` so the browser refuses to send the session cookie over plain HTTP.

#### Consider Upgrading the Database

SQLite handles one writer at a time. For a real banking application with multiple concurrent users, migrate to PostgreSQL or MySQL. Flask-SQLAlchemy makes this transition straightforward — only the database connection string changes.

#### Disable Debug Mode

Set `debug=False` in the Flask run configuration (or rely on the default, which is `False`). Debug mode exposes an interactive Python console in the browser on unhandled errors — this is a severe security vulnerability in production.

#### Configure Logging

In production, Flask's default console logging is insufficient. Configure Python's `logging` module to write errors to a file or a centralised log service. At minimum, log all 500 errors with full stack traces so you can diagnose problems.

#### Restrict CORS and Headers

If the app is ever extended with an API, add appropriate CORS headers. For a pure HTML/form application this is not needed. Set the `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff` HTTP response headers to defend against common browser-level attacks.

---

*End of Step-by-Step Implementation Guide*

# Banking Web Application — Implementation Plan

---

## 1. Solution Overview

### Objective
Build a simple, browser-based banking web application that allows customers to log in securely, view their account balance, and perform basic transactions (deposit and withdrawal), backed by a lightweight Python/Flask API and a SQLite database.

### Scope
| In Scope | Out of Scope |
|---|---|
| Customer login / logout | User registration / self-enrolment |
| View account balance | Multi-currency support |
| Deposit funds | Wire / inter-bank transfers |
| Withdraw funds | Admin portal |
| Session-based access control | Email / SMS notifications |
| Bootstrap-based responsive UI | Mobile native apps |

### Users
- **Customer** — an existing bank customer who logs in to manage their account.

### Functional Requirements
1. A customer can authenticate using a username and password.
2. Authenticated customers are redirected to a personalised dashboard.
3. The dashboard displays the current account balance.
4. A customer can deposit a positive amount; the balance increases accordingly.
5. A customer can withdraw a positive amount not exceeding the current balance.
6. A customer can log out, which invalidates their session.
7. Unauthenticated requests to protected pages redirect to the login page.

### Non-Functional Requirements
- **Security** — passwords must be stored hashed (never plaintext); sessions must be server-side.
- **Usability** — all pages must render correctly on common desktop browsers and basic mobile viewports via Bootstrap's responsive grid.
- **Reliability** — transactions must be atomic; a failed deposit or withdrawal must not corrupt the balance.
- **Simplicity** — no external message queues, caches, or micro-services; the system runs as a single Flask process.
- **Maintainability** — clear separation between frontend templates, backend routes, and data access code.

### Assumptions
- Customer accounts are pre-seeded in the database (no self-registration flow).
- A single account per customer is sufficient for this scope.
- SQLite is acceptable for development and light production loads; no connection-pool tuning required.
- Bootstrap is loaded via CDN; no local asset pipeline (webpack, etc.) is needed.
- The application runs on `localhost` during development; HTTPS/TLS is a deployment concern outside this scope.

---

## 2. High-Level Architecture

### Architecture Overview

```
┌─────────────────────────────────┐
│           BROWSER               │
│  HTML pages styled with         │
│  Bootstrap (served by Flask)    │
└────────────────┬────────────────┘
                 │  HTTP (form POST / GET)
                 ▼
┌─────────────────────────────────┐
│        FLASK APPLICATION        │
│  (BACKEND/app.py + blueprints)  │
│                                 │
│  • Session management           │
│  • Route handling               │
│  • Business logic               │
│  • Jinja2 template rendering    │
└────────────────┬────────────────┘
                 │  SQLite ORM / raw SQL
                 ▼
┌─────────────────────────────────┐
│         SQLITE DATABASE         │
│  (BACKEND/banking.db)           │
│                                 │
│  • users table                  │
│  • accounts table               │
│  • transactions table           │
└─────────────────────────────────┘
```

### Frontend → Backend → Database Interaction

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | HTML + Bootstrap + Jinja2 | Render UI, submit forms, display flash messages |
| Backend | Python Flask | Handle HTTP requests, enforce auth, execute business logic, render responses |
| Database | SQLite | Persist users, accounts, and transaction history |

### Request Lifecycle

1. **Browser** sends an HTTP request (GET page or POST form data).
2. **Flask router** matches the URL to a view function.
3. **Auth guard** checks the session; unauthenticated requests are redirected to `/login`.
4. **View function** calls the appropriate service / data-access layer.
5. **Data layer** reads from or writes to SQLite.
6. **View function** passes result data to a Jinja2 template.
7. **Flask** renders the template and returns an HTTP response to the browser.
8. **Bootstrap** applies styling; the browser presents the final page.

---

## 3. Component Design

### Frontend Responsibilities (`FRONTEND/`)
- Provide Jinja2 HTML templates for every page (login, dashboard, deposit, withdraw).
- Use Bootstrap grid and components (forms, cards, alerts, navbar) for layout and styling.
- Display server-generated flash messages (success, error, warning).
- Submit data to the backend exclusively through HTML `<form>` elements (no JavaScript fetch required for core features).
- A `base.html` layout template provides the shared navbar, Bootstrap CDN links, and flash-message block inherited by all other templates.

### Backend Responsibilities (`BACKEND/`)
- Define and register Flask routes for all application URLs.
- Manage user sessions (login token, customer identity) using Flask's built-in session mechanism.
- Implement an authentication guard (decorator or before-request hook) protecting all non-login routes.
- Contain business logic for deposit and withdrawal (amount validation, balance check).
- Interact with the SQLite database through a data-access layer (direct SQL via `sqlite3` module or Flask-SQLAlchemy ORM).
- Render Jinja2 templates located in `FRONTEND/templates/`.
- Return appropriate HTTP redirects and flash messages on success or failure.

### Database Responsibilities (`BACKEND/banking.db`)
- Persist all application state: customer credentials, account balances, and transaction history.
- Three logical entities: **User** (credentials), **Account** (balance linked to a user), **Transaction** (immutable record of each deposit or withdrawal).
- Enforce data integrity at the storage layer (foreign keys, NOT NULL constraints, positive-amount checks where supported).

---

## 4. Folder Structure

```
project-root/
│
├── IMPLEMENTATION_PLAN.md          ← This document
│
├── FRONTEND/
│   ├── templates/
│   │   ├── base.html               ← Shared layout: navbar, Bootstrap CDN, flash messages
│   │   ├── login.html              ← Login form
│   │   ├── dashboard.html          ← Balance summary + action buttons
│   │   ├── deposit.html            ← Deposit form
│   │   └── withdraw.html           ← Withdrawal form
│   └── static/
│       └── css/
│           └── custom.css          ← Minor overrides on top of Bootstrap (optional)
│
└── BACKEND/
    ├── app.py                      ← Flask application factory; registers blueprints, config
    ├── auth.py                     ← Login / logout routes; auth guard decorator
    ├── dashboard.py                ← Dashboard route (balance display)
    ├── transactions.py             ← Deposit and withdrawal routes + business logic
    ├── database.py                 ← DB connection helper; init_db() to seed schema
    ├── banking.db                  ← SQLite database file (auto-created on first run)
    └── requirements.txt            ← Python dependencies (flask, werkzeug, etc.)
```

### Responsibility of Each Entry

| Path | Responsibility |
|---|---|
| `FRONTEND/templates/base.html` | Master layout; all pages extend this |
| `FRONTEND/templates/login.html` | Username/password form |
| `FRONTEND/templates/dashboard.html` | Greeting, current balance, nav links to deposit / withdraw |
| `FRONTEND/templates/deposit.html` | Amount input form for depositing funds |
| `FRONTEND/templates/withdraw.html` | Amount input form for withdrawing funds |
| `FRONTEND/static/css/custom.css` | Optional CSS tweaks; not required for core function |
| `BACKEND/app.py` | Flask app creation, config (secret key, DB path), blueprint registration |
| `BACKEND/auth.py` | `/login` GET/POST, `/logout`, `login_required` decorator |
| `BACKEND/dashboard.py` | `/dashboard` GET — fetches and displays balance |
| `BACKEND/transactions.py` | `/deposit` and `/withdraw` POST handlers with validation |
| `BACKEND/database.py` | `get_db()` helper, `init_db()` schema creation, `seed_db()` for demo data |
| `BACKEND/banking.db` | SQLite file; created automatically; not committed to version control |
| `BACKEND/requirements.txt` | Pinned Python package list |

---

## 5. Module Breakdown

### 5.1 Authentication Module (`BACKEND/auth.py`)
**Purpose:** Verify customer identity and manage session lifecycle.

| Concern | Detail |
|---|---|
| Login page (GET) | Render `login.html` |
| Login submit (POST) | Look up user by username; compare submitted password against stored hash; on success write `user_id` to session and redirect to dashboard; on failure re-render login with error flash |
| Logout | Clear session; redirect to login page |
| Auth guard | `login_required` decorator — checks `session['user_id']` before any protected view; redirects to login if absent |
| Password handling | Passwords hashed with `werkzeug.security` (`generate_password_hash` / `check_password_hash`); plaintext never stored |

### 5.2 Dashboard Module (`BACKEND/dashboard.py`)
**Purpose:** Provide the customer's home screen after login.

| Concern | Detail |
|---|---|
| Dashboard page (GET) | Protected by `login_required`; query the account balance for the logged-in user; pass balance and customer name to `dashboard.html` |
| Navigation | Template renders links to Deposit, Withdraw, and Logout |

### 5.3 Account Management Module (`BACKEND/database.py` + data layer)
**Purpose:** Centralise all data-access logic so route handlers stay thin.

| Concern | Detail |
|---|---|
| DB connection | `get_db()` — returns a connection scoped to the current Flask request context; closed automatically on teardown |
| Schema initialisation | `init_db()` — creates tables if they do not exist (idempotent) |
| Demo seeding | `seed_db()` — inserts one or more sample users + accounts so the app works immediately after first run |
| Balance retrieval | Helper function `get_balance(user_id)` — returns current balance as a Decimal/float |
| Balance update | Helper function `update_balance(user_id, delta)` — adds `delta` (positive for deposit, negative for withdrawal) to the account balance within a transaction |

### 5.4 Transactions Module (`BACKEND/transactions.py`)
**Purpose:** Handle deposit and withdrawal business logic.

| Concern | Detail |
|---|---|
| Deposit (POST) | Protected by `login_required`; parse and validate amount (must be numeric, > 0); call `update_balance` with positive delta; flash success; redirect to dashboard |
| Withdraw (POST) | Protected by `login_required`; parse and validate amount (must be numeric, > 0, ≤ current balance); call `update_balance` with negative delta; flash success or insufficient-funds error; redirect to dashboard |
| Transaction record | Each successful deposit or withdrawal writes an immutable row to the transactions table (amount, type, timestamp) for audit purposes |
| Error handling | Invalid amounts or insufficient funds re-render the relevant form with a descriptive flash message; no balance change occurs |

---

## 6. Implementation Roadmap

### Phase 1 — Project Scaffold & Environment
**Goal:** Working Flask app with folder structure in place and dependencies installable.

- Create `FRONTEND/` and `BACKEND/` directory trees.
- Write `BACKEND/requirements.txt` with Flask and Werkzeug.
- Create `BACKEND/app.py` (minimal Flask factory, no routes yet).
- Create `FRONTEND/templates/base.html` with Bootstrap CDN and flash-message block.

**Depends on:** Nothing.
**Estimated effort:** Small.

---

### Phase 2 — Database Layer
**Goal:** SQLite database initialises cleanly; helper functions are testable in isolation.

- Implement `BACKEND/database.py` with `get_db()`, `init_db()`, and `seed_db()`.
- Wire `init_db()` call into `app.py` startup.
- Verify database file and tables are created on first run.

**Depends on:** Phase 1.
**Estimated effort:** Small.

---

### Phase 3 — Authentication
**Goal:** Login and logout flows work end-to-end; unauthenticated routes redirect correctly.

- Implement `BACKEND/auth.py` with login GET/POST, logout, and `login_required` decorator.
- Create `FRONTEND/templates/login.html`.
- Register auth blueprint in `app.py`.
- Test: correct credentials → session created → redirect to dashboard placeholder; wrong credentials → flash error; `/logout` → session cleared.

**Depends on:** Phase 2.
**Estimated effort:** Medium.

---

### Phase 4 — Dashboard
**Goal:** Logged-in customer sees their name and current balance.

- Implement `BACKEND/dashboard.py` with the `/dashboard` route.
- Create `FRONTEND/templates/dashboard.html` (balance card, action links, logout link).
- Register dashboard blueprint in `app.py`.

**Depends on:** Phase 3.
**Estimated effort:** Small.

---

### Phase 5 — Transactions (Deposit & Withdrawal)
**Goal:** Customer can deposit and withdraw funds; balance updates immediately; errors handled gracefully.

- Implement `BACKEND/transactions.py` with `/deposit` and `/withdraw` routes.
- Add `update_balance()` and transaction-record insert to `database.py`.
- Create `FRONTEND/templates/deposit.html` and `FRONTEND/templates/withdraw.html`.
- Register transactions blueprint in `app.py`.
- Test: valid deposit → balance increases; valid withdrawal → balance decreases; over-withdrawal → error flash, balance unchanged; non-numeric input → error flash.

**Depends on:** Phase 4.
**Estimated effort:** Medium.

---

### Phase 6 — UI Polish & Integration Testing
**Goal:** All pages are visually consistent and end-to-end flows are verified.

- Add `FRONTEND/static/css/custom.css` for any Bootstrap overrides.
- Walk through all user journeys (login → dashboard → deposit → withdraw → logout) manually.
- Verify flash messages appear correctly on all success and error paths.
- Confirm unauthenticated access to every protected URL redirects to login.

**Depends on:** Phase 5.
**Estimated effort:** Small.

---

### Dependency Summary

```
Phase 1 (Scaffold)
    └── Phase 2 (Database)
            └── Phase 3 (Auth)
                    └── Phase 4 (Dashboard)
                                └── Phase 5 (Transactions)
                                            └── Phase 6 (Polish & Testing)
```

---

*End of Implementation Plan*

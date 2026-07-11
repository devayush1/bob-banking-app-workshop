# MyBank — Startup Instructions

## Prerequisites
- Python 3.9 or later installed
- pip available

---

## First-Time Setup

```bash
# 1. Navigate to the BACKEND folder
cd BACKEND

# 2. Create a virtual environment
python3 -m venv venv

# 3. Activate the virtual environment
#    macOS / Linux:
source venv/bin/activate
#    Windows:
#    venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## Run the Application

```bash
# Make sure you are in BACKEND/ and the venv is active, then:
python3 app.py
```

Flask will print:
```
✔  Demo account created
   username : demo
   password : demo1234
   balance  : $1,000.00

 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

Open **http://127.0.0.1:5000** in your browser and log in with:

| Field    | Value      |
|----------|------------|
| Username | `demo`     |
| Password | `demo1234` |

---

## Run the Tests

```bash
# From BACKEND/ with venv active:
python3 -m pytest tests/ -v
```

Expected: **78 passed**

---

## Reset the Database

Delete `BACKEND/banking.db` and restart the server.
`init_db()` and `seed_db()` will recreate it automatically.

---

## Stop the Server

Press `Ctrl+C` in the terminal.

import sqlite3
import os
import calendar
import json
from datetime import datetime, timedelta
from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)

PLAYER_1 = "JC"
PLAYER_2 = "MG"
DB_PATH = os.path.join(os.path.dirname(__file__), "cleanings.db")

CHORES = [
    {"key": "litter",   "name": "Litter Box", "emoji": "🐱"},
    {"key": "dishes",   "name": "Dishes",     "emoji": "🍽"},
    {"key": "laundry",  "name": "Laundry",    "emoji": "👕"},
    {"key": "bathroom", "name": "Bathroom",   "emoji": "🚿"},
    {"key": "vacuum",   "name": "Vacuum",     "emoji": "🧹"},
    {"key": "trash",    "name": "Trash",      "emoji": "🗑"},
]
CHORE_NAMES = {c["name"] for c in CHORES}


# --- Database ---

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]

    if "cleanings" in tables:
        cols = [r[1] for r in db.execute("PRAGMA table_info(cleanings)").fetchall()]
        if "cleaned_date" not in cols:
            db.execute("ALTER TABLE cleanings ADD COLUMN cleaned_date TEXT")
            db.execute("UPDATE cleanings SET cleaned_date = date(cleaned_at)")
            db.commit()
        if "chore" not in cols:
            db.execute("ALTER TABLE cleanings ADD COLUMN chore TEXT NOT NULL DEFAULT 'Litter Box'")
            db.commit()
    else:
        db.execute("""
            CREATE TABLE cleanings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                person       TEXT    NOT NULL,
                chore        TEXT    NOT NULL DEFAULT 'Litter Box',
                cleaned_date TEXT    NOT NULL,
                cleaned_at   TEXT    NOT NULL
            )
        """)
        db.commit()
    db.close()


# --- Helpers ---

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def week_start_str():
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")

def calc_streak(db, person, chore):
    rows = db.execute(
        "SELECT cleaned_date FROM cleanings WHERE person = ? AND chore = ? ORDER BY cleaned_date DESC",
        (person, chore)
    ).fetchall()
    dates = {r["cleaned_date"] for r in rows}
    current = datetime.now().date()
    streak = 0
    while current.strftime("%Y-%m-%d") in dates:
        streak += 1
        current -= timedelta(days=1)
    return streak

def calc_monthly(db, person, chore):
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    row = db.execute(
        "SELECT COUNT(*) as n FROM cleanings WHERE person = ? AND chore = ? AND cleaned_date >= ?",
        (person, chore, month_start)
    ).fetchone()
    return row["n"]


# --- API ---

@app.route("/api/today", methods=["GET"])
def get_today():
    db = get_db()
    rows = db.execute(
        "SELECT person, chore FROM cleanings WHERE cleaned_date = ?",
        (today_str(),)
    ).fetchall()
    now = datetime.now()
    result = []
    for r in rows:
        result.append({
            "person": r["person"],
            "chore":  r["chore"],
            "streak": calc_streak(db, r["person"], r["chore"]),
            "monthly": calc_monthly(db, r["person"], r["chore"]),
            "days_in_month": calendar.monthrange(now.year, now.month)[1],
            "month_name": now.strftime("%B"),
        })
    return jsonify(result)

@app.route("/api/clean", methods=["POST"])
def record_clean():
    data = request.get_json()
    person = (data.get("person") or "").strip()
    chore  = (data.get("chore")  or "").strip()

    if person not in (PLAYER_1, PLAYER_2):
        return jsonify({"error": "Unknown person"}), 400
    if chore not in CHORE_NAMES:
        return jsonify({"error": "Unknown chore"}), 400

    db = get_db()
    today = today_str()
    existing = db.execute(
        "SELECT person FROM cleanings WHERE cleaned_date = ? AND chore = ?",
        (today, chore)
    ).fetchone()
    if existing:
        return jsonify({"error": "Already done today", "person": existing["person"]}), 409

    db.execute(
        "INSERT INTO cleanings (person, chore, cleaned_date, cleaned_at) VALUES (?, ?, ?, ?)",
        (person, chore, today, datetime.now().isoformat())
    )
    db.commit()

    now = datetime.now()
    return jsonify({
        "ok": True,
        "person": person,
        "chore":  chore,
        "streak": calc_streak(db, person, chore),
        "monthly": calc_monthly(db, person, chore),
        "days_in_month": calendar.monthrange(now.year, now.month)[1],
        "month_name": now.strftime("%B"),
    })

@app.route("/api/history", methods=["GET"])
def get_history():
    db = get_db()
    rows = db.execute(
        "SELECT id, person, chore, cleaned_date FROM cleanings ORDER BY cleaned_date DESC, cleaned_at DESC"
    ).fetchall()
    return jsonify([
        {"id": r["id"], "person": r["person"], "chore": r["chore"], "date": r["cleaned_date"]}
        for r in rows
    ])

@app.route("/api/weekly", methods=["GET"])
def get_weekly():
    db = get_db()
    ws = week_start_str()
    rows = db.execute(
        "SELECT person, chore, COUNT(*) as n FROM cleanings WHERE cleaned_date >= ? GROUP BY person, chore",
        (ws,)
    ).fetchall()

    players = {PLAYER_1: 0, PLAYER_2: 0}
    chores  = {c["name"]: 0 for c in CHORES}

    for r in rows:
        if r["person"] in players:
            players[r["person"]] += r["n"]
        if r["chore"] in chores:
            chores[r["chore"]] += r["n"]

    return jsonify({"players": players, "chores": chores})

@app.route("/api/clean/<int:entry_id>", methods=["DELETE"])
def delete_clean(entry_id):
    db = get_db()
    row = db.execute("SELECT id FROM cleanings WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM cleanings WHERE id = ?", (entry_id,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/reset", methods=["POST"])
def reset_all():
    db = get_db()
    db.execute("DELETE FROM cleanings")
    db.commit()
    return jsonify({"ok": True})

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html",
        player1=PLAYER_1,
        player2=PLAYER_2,
        chores=json.dumps(CHORES)
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5050, debug=False)

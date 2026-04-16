import sqlite3
import os
import calendar
from datetime import datetime, timedelta
from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)

PLAYER_1 = "JC"
PLAYER_2 = "MG"
DB_PATH = os.path.join(os.path.dirname(__file__), "cleanings.db")


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
            # Migrate old schema: add cleaned_date from cleaned_at
            db.execute("ALTER TABLE cleanings ADD COLUMN cleaned_date TEXT")
            db.execute("UPDATE cleanings SET cleaned_date = date(cleaned_at)")
            db.commit()
    else:
        db.execute("""
            CREATE TABLE cleanings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                person       TEXT    NOT NULL,
                cleaned_date TEXT    NOT NULL,
                cleaned_at   TEXT    NOT NULL
            )
        """)
        db.commit()
    db.close()


# --- Helpers ---

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def calc_streak(db, person):
    rows = db.execute(
        "SELECT cleaned_date FROM cleanings WHERE person = ? ORDER BY cleaned_date DESC",
        (person,)
    ).fetchall()
    dates = {r["cleaned_date"] for r in rows}
    current = datetime.now().date()
    streak = 0
    while current.strftime("%Y-%m-%d") in dates:
        streak += 1
        current -= timedelta(days=1)
    return streak

def calc_monthly(db, person):
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    row = db.execute(
        "SELECT COUNT(*) as n FROM cleanings WHERE person = ? AND cleaned_date >= ?",
        (person, month_start)
    ).fetchone()
    return row["n"]


# --- API ---

@app.route("/api/today", methods=["GET"])
def get_today():
    db = get_db()
    row = db.execute(
        "SELECT person FROM cleanings WHERE cleaned_date = ? LIMIT 1",
        (today_str(),)
    ).fetchone()

    if not row:
        return jsonify({"person": None})

    person = row["person"]
    now = datetime.now()
    return jsonify({
        "person": person,
        "streak": calc_streak(db, person),
        "monthly": calc_monthly(db, person),
        "days_in_month": calendar.monthrange(now.year, now.month)[1],
        "month_name": now.strftime("%B"),
    })

@app.route("/api/clean", methods=["POST"])
def record_clean():
    data = request.get_json()
    person = (data.get("person") or "").strip()
    if person not in (PLAYER_1, PLAYER_2):
        return jsonify({"error": "Unknown person"}), 400

    db = get_db()
    today = today_str()
    existing = db.execute(
        "SELECT person FROM cleanings WHERE cleaned_date = ?", (today,)
    ).fetchone()
    if existing:
        return jsonify({"error": "Already cleaned today", "person": existing["person"]}), 409

    db.execute(
        "INSERT INTO cleanings (person, cleaned_date, cleaned_at) VALUES (?, ?, ?)",
        (person, today, datetime.now().isoformat())
    )
    db.commit()

    now = datetime.now()
    return jsonify({
        "ok": True,
        "person": person,
        "streak": calc_streak(db, person),
        "monthly": calc_monthly(db, person),
        "days_in_month": calendar.monthrange(now.year, now.month)[1],
        "month_name": now.strftime("%B"),
    })

@app.route("/api/history", methods=["GET"])
def get_history():
    db = get_db()
    rows = db.execute(
        "SELECT id, person, cleaned_date FROM cleanings ORDER BY cleaned_date DESC"
    ).fetchall()
    return jsonify([
        {"id": r["id"], "person": r["person"], "date": r["cleaned_date"]}
        for r in rows
    ])

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
    return render_template("index.html", player1=PLAYER_1, player2=PLAYER_2)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5050, debug=False)

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
    {"key": "patio",    "name": "Patio",      "emoji": "🌿"},
    {"key": "cooking",  "name": "Cooking",    "emoji": "🍳"},
]
CHORE_NAMES = {c["name"] for c in CHORES}

# These chores can be logged multiple times per day
MULTI_PER_DAY_CHORES = {"Dishes", "Laundry", "Trash", "Cooking"}

# Days without cleaning before showing an attention indicator
CHORE_THRESHOLDS = {
    "Litter Box": 3,
    "Vacuum":     3,
    "Bathroom":   7,
}

HABITS = [
    {"key": "running",        "name": "Running",       "emoji": "🏃"},
    {"key": "yoga",           "name": "Yoga",          "emoji": "🧘"},
    {"key": "weights",        "name": "Weights",       "emoji": "🏋️"},
    {"key": "sports",         "name": "Sports",        "emoji": "⚽"},
    {"key": "reading",        "name": "Reading",       "emoji": "📚"},
    {"key": "no_alcohol",     "name": "No Alcohol",    "emoji": "🚫🍺"},
    {"key": "drinking_water", "name": "Drinking Water","emoji": "💧"},
    {"key": "no_junk_food",   "name": "No Junk Food",  "emoji": "🥗"},
]
HABIT_NAMES = {h["name"] for h in HABITS}


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

    db.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            person      TEXT NOT NULL,
            habit       TEXT NOT NULL,
            logged_date TEXT NOT NULL,
            logged_at   TEXT NOT NULL
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

def calc_habit_streak(db, person, habit):
    rows = db.execute(
        "SELECT logged_date FROM habits WHERE person = ? AND habit = ? ORDER BY logged_date DESC",
        (person, habit)
    ).fetchall()
    dates = {r["logged_date"] for r in rows}
    current = datetime.now().date()
    streak = 0
    while current.strftime("%Y-%m-%d") in dates:
        streak += 1
        current -= timedelta(days=1)
    return streak

def calc_habit_monthly(db, person, habit):
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    row = db.execute(
        "SELECT COUNT(*) as n FROM habits WHERE person = ? AND habit = ? AND logged_date >= ?",
        (person, habit, month_start)
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

    # Once-per-day chores: block if already logged today by anyone
    if chore not in MULTI_PER_DAY_CHORES:
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

@app.route("/api/chore-status", methods=["GET"])
def get_chore_status():
    db = get_db()
    today = today_str()

    first_row = db.execute(
        "SELECT MIN(cleaned_date) as first_date FROM cleanings"
    ).fetchone()
    first_record_date = first_row["first_date"] if first_row["first_date"] else None

    chores = {}
    for chore_name in CHORE_THRESHOLDS:
        row = db.execute(
            "SELECT MAX(cleaned_date) as last_date FROM cleanings WHERE chore = ?",
            (chore_name,)
        ).fetchone()
        last_date = row["last_date"] if row["last_date"] else None

        if last_date:
            d1 = datetime.strptime(today, "%Y-%m-%d")
            d2 = datetime.strptime(last_date, "%Y-%m-%d")
            days_since = (d1 - d2).days
        else:
            days_since = None

        chores[chore_name] = {"last_date": last_date, "days_since": days_since}

    return jsonify({"first_record_date": first_record_date, "chores": chores})

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

@app.route("/api/habits/today", methods=["GET"])
def get_habits_today():
    db = get_db()
    rows = db.execute(
        "SELECT person, habit FROM habits WHERE logged_date = ?",
        (today_str(),)
    ).fetchall()
    now = datetime.now()
    result = []
    for r in rows:
        result.append({
            "person":        r["person"],
            "habit":         r["habit"],
            "streak":        calc_habit_streak(db, r["person"], r["habit"]),
            "monthly":       calc_habit_monthly(db, r["person"], r["habit"]),
            "days_in_month": calendar.monthrange(now.year, now.month)[1],
            "month_name":    now.strftime("%B"),
        })
    return jsonify(result)

@app.route("/api/habits/log", methods=["POST"])
def log_habit():
    data   = request.get_json()
    person = (data.get("person") or "").strip()
    habit  = (data.get("habit")  or "").strip()
    if person not in (PLAYER_1, PLAYER_2):
        return jsonify({"error": "Unknown person"}), 400
    if habit not in HABIT_NAMES:
        return jsonify({"error": "Unknown habit"}), 400
    db    = get_db()
    today = today_str()
    db.execute(
        "INSERT INTO habits (person, habit, logged_date, logged_at) VALUES (?, ?, ?, ?)",
        (person, habit, today, datetime.now().isoformat())
    )
    db.commit()
    now = datetime.now()
    return jsonify({
        "ok":            True,
        "person":        person,
        "habit":         habit,
        "streak":        calc_habit_streak(db, person, habit),
        "monthly":       calc_habit_monthly(db, person, habit),
        "days_in_month": calendar.monthrange(now.year, now.month)[1],
        "month_name":    now.strftime("%B"),
    })

@app.route("/api/habits/weekly", methods=["GET"])
def get_habits_weekly():
    db = get_db()
    ws = week_start_str()
    rows = db.execute(
        "SELECT person, COUNT(*) as n FROM habits WHERE logged_date >= ? GROUP BY person",
        (ws,)
    ).fetchall()
    players = {PLAYER_1: 0, PLAYER_2: 0}
    for r in rows:
        if r["person"] in players:
            players[r["person"]] += r["n"]
    return jsonify({"players": players})

@app.route("/api/habits/history", methods=["GET"])
def get_habits_history():
    db = get_db()
    rows = db.execute(
        "SELECT id, person, habit, logged_date FROM habits ORDER BY logged_date DESC, logged_at DESC"
    ).fetchall()
    return jsonify([
        {"id": r["id"], "person": r["person"], "habit": r["habit"], "date": r["logged_date"]}
        for r in rows
    ])

@app.route("/api/habits/<int:entry_id>", methods=["DELETE"])
def delete_habit(entry_id):
    db = get_db()
    row = db.execute("SELECT id FROM habits WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM habits WHERE id = ?", (entry_id,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/habits/reset", methods=["POST"])
def reset_habits():
    db = get_db()
    db.execute("DELETE FROM habits")
    db.commit()
    return jsonify({"ok": True})

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html",
        player1=PLAYER_1,
        player2=PLAYER_2,
        chores=json.dumps(CHORES),
        habits=json.dumps(HABITS),
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5050, debug=False)

# Chore Attention Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a pulsing red glow ring + "Xd ago" chip on overdue chore buttons (Litter Box ≥3d, Vacuum ≥3d, Bathroom ≥7d) while the screen is active.

**Architecture:** New `GET /api/chore-status` endpoint returns days-since-last-done for the three threshold chores; frontend reads this on every `loadAll()` call and applies CSS classes in `renderChoreGrid()`. No DB changes.

**Tech Stack:** Python Flask, SQLite, vanilla JS, inline CSS in a single HTML file.

---

## Files

| File | Change |
|---|---|
| `app.py` | Add `CHORE_THRESHOLDS` dict + `GET /api/chore-status` route |
| `templates/index.html` | Add CSS (animation + two classes), JS constants, `choreStatus` state, `isOverdue()`/`overdueChipLabel()` helpers, update `loadAll()` and `renderChoreGrid()` |

---

### Task 1: Add `CHORE_THRESHOLDS` and `/api/chore-status` to `app.py`

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add the `CHORE_THRESHOLDS` constant directly below `MULTI_PER_DAY_CHORES`**

Open `app.py`. Find the line:
```python
# These chores can be logged multiple times per day
MULTI_PER_DAY_CHORES = {"Dishes", "Laundry", "Trash"}
```

Add immediately after it:
```python
# Days threshold before showing an attention indicator on the grid button
CHORE_THRESHOLDS = {
    "Litter Box": 3,
    "Vacuum":     3,
    "Bathroom":   7,
}
```

- [ ] **Step 2: Add the `/api/chore-status` route to `app.py`**

Add this route after the existing `get_weekly()` function (around line 190):

```python
@app.route("/api/chore-status", methods=["GET"])
def get_chore_status():
    db = get_db()
    today = today_str()

    # Earliest-ever record date — used as grace-period reference for never-logged chores
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

        chores[chore_name] = {
            "last_date":  last_date,
            "days_since": days_since,
        }

    return jsonify({
        "first_record_date": first_record_date,
        "chores":            chores,
    })
```

- [ ] **Step 3: Manually start Flask and verify the endpoint**

```bash
cd /Users/juanca/Projects_2026/ChoreWars
source .venv/bin/activate
python3 app.py &
sleep 2
curl -s http://localhost:5050/api/chore-status | python3 -m json.tool
```

Expected response shape (values will vary based on your DB):
```json
{
    "first_record_date": "2026-05-01",
    "chores": {
        "Bathroom": {
            "days_since": 8,
            "last_date": "2026-05-15"
        },
        "Litter Box": {
            "days_since": 1,
            "last_date": "2026-05-22"
        },
        "Vacuum": {
            "days_since": null,
            "last_date": null
        }
    }
}
```

If the DB is empty you'll get:
```json
{
    "first_record_date": null,
    "chores": {
        "Bathroom":   {"days_since": null, "last_date": null},
        "Litter Box": {"days_since": null, "last_date": null},
        "Vacuum":     {"days_since": null, "last_date": null}
    }
}
```

- [ ] **Step 4: Kill the dev server**

```bash
pkill -f "python3 app.py"
```

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add /api/chore-status endpoint with per-chore days-since"
```

---

### Task 2: Add CSS for the attention indicator

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Add the animation and two classes to the `<style>` block**

In `templates/index.html`, find the closing comment and brace of the last CSS block before `</style>`. It looks like:

```css
    @keyframes cfall {
      0%   { opacity: 1; transform: translateY(0) rotate(0deg); }
      100% { opacity: 0; transform: translateY(220px) rotate(720deg); }
    }
  </style>
```

Replace that closing block with:

```css
    @keyframes cfall {
      0%   { opacity: 1; transform: translateY(0) rotate(0deg); }
      100% { opacity: 0; transform: translateY(220px) rotate(720deg); }
    }

    /* ============================================================
       ATTENTION INDICATOR
    ============================================================ */
    @keyframes pulseGlow {
      0%, 100% { box-shadow: 0 0 0 2px rgba(239,68,68,0.6), 0 0 18px rgba(239,68,68,0.4); }
      50%       { box-shadow: 0 0 0 3px rgba(239,68,68,0.9), 0 0 30px rgba(239,68,68,0.65); }
    }
    .alert-glow {
      animation: pulseGlow 1.8s ease-in-out infinite;
      outline: 2px solid rgba(239,68,68,0.7);
    }
    .days-chip {
      position: absolute;
      top: 7px;
      right: 7px;
      background: rgba(239,68,68,0.92);
      color: #fff;
      font-size: 9px;
      font-weight: 900;
      border-radius: 8px;
      padding: 2px 6px;
      line-height: 1.4;
      pointer-events: none;
    }
  </style>
```

- [ ] **Step 2: Commit**

```bash
git add templates/index.html
git commit -m "feat: add pulseGlow animation, alert-glow, and days-chip CSS classes"
```

---

### Task 3: Add JS constants, state variable, and helper functions

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Add `CHORE_THRESHOLDS` JS constant**

In the `<script>` block, find the existing constants at the top:

```js
    // Chores that can be logged multiple times per day
    const MULTI_PER_DAY = new Set(["Dishes", "Laundry", "Trash"]);
```

Add immediately after:

```js
    // Days threshold before showing attention indicator (null = no threshold)
    const CHORE_THRESHOLDS = { "Litter Box": 3, "Vacuum": 3, "Bathroom": 7 };
```

- [ ] **Step 2: Add `choreStatus` state variable**

Find the existing state variables:

```js
    let currentDay   = localDateStr();
    let currentChore = null;
    let todayDone    = {};   // chore name → last logged entry (for once-per-day display)
    let todayCount   = {};   // chore name → number of times logged today
    let weeklyStats  = { players: {}, chores: {} };
```

Add `choreStatus` to that block:

```js
    let currentDay   = localDateStr();
    let currentChore = null;
    let todayDone    = {};   // chore name → last logged entry (for once-per-day display)
    let todayCount   = {};   // chore name → number of times logged today
    let weeklyStats  = { players: {}, chores: {} };
    let choreStatus  = { firstRecordDate: null, chores: {} };
```

- [ ] **Step 3: Add `isOverdue()` and `overdueChipLabel()` helper functions**

Find the `// ---- Date helpers ----` comment block. Add these two functions directly before the `// ---- Toast ----` comment:

```js
    // ---- Overdue helpers ----
    function isOverdue(choreName) {
      var threshold = CHORE_THRESHOLDS[choreName];
      if (!threshold) return false;

      var status = choreStatus.chores[choreName];
      if (!status) return false;

      // Chore has been logged before — compare days since last done
      if (status.daysSince !== null && status.daysSince !== undefined) {
        return status.daysSince >= threshold;
      }

      // Never logged — use first-ever DB record date as grace period reference
      if (!choreStatus.firstRecordDate) return false;
      var today = new Date();
      var first = new Date(choreStatus.firstRecordDate + 'T00:00:00');
      var daysSinceFirst = Math.floor((today - first) / 86400000);
      return daysSinceFirst >= threshold;
    }

    function overdueChipLabel(choreName) {
      var status = choreStatus.chores[choreName];
      if (!status) return '';
      if (status.daysSince !== null && status.daysSince !== undefined) {
        return status.daysSince + 'd ago';
      }
      return 'never';
    }
```

- [ ] **Step 4: Commit**

```bash
git add templates/index.html
git commit -m "feat: add choreStatus state and isOverdue/overdueChipLabel helpers"
```

---

### Task 4: Wire up `loadAll()` and `renderChoreGrid()`

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Update `loadAll()` to fetch `/api/chore-status`**

Find the existing `loadAll()` function:

```js
    async function loadAll() {
      var results = await Promise.all([fetch('/api/today'), fetch('/api/weekly')]);
      var todayItems = await results[0].json();
      weeklyStats = await results[1].json();

      todayDone  = {};
      todayCount = {};
      todayItems.forEach(function(item) {
        todayDone[item.chore] = item;
        todayCount[item.chore] = (todayCount[item.chore] || 0) + 1;
      });
    }
```

Replace it with:

```js
    async function loadAll() {
      var results = await Promise.all([
        fetch('/api/today'),
        fetch('/api/weekly'),
        fetch('/api/chore-status'),
      ]);
      var todayItems  = await results[0].json();
      weeklyStats     = await results[1].json();
      var statusData  = await results[2].json();

      todayDone  = {};
      todayCount = {};
      todayItems.forEach(function(item) {
        todayDone[item.chore] = item;
        todayCount[item.chore] = (todayCount[item.chore] || 0) + 1;
      });

      choreStatus = { firstRecordDate: statusData.first_record_date, chores: {} };
      Object.keys(statusData.chores).forEach(function(name) {
        choreStatus.chores[name] = { daysSince: statusData.chores[name].days_since };
      });
    }
```

- [ ] **Step 2: Update `renderChoreGrid()` to apply overdue classes and chip**

Find the existing `renderChoreGrid()` function:

```js
    function renderChoreGrid() {
      var grid = document.getElementById('chore-grid');
      grid.innerHTML = CHORES.map(function(c) {
        var done      = todayDone[c.name];
        var count     = todayCount[c.name] || 0;
        var isMulti   = MULTI_PER_DAY.has(c.name);
        var cssCls    = CHORE_CSS[c.name] || 'chore-litter';
        var weekCount = (weeklyStats.chores && weeklyStats.chores[c.name]) || 0;
        var weekLabel = weekCount > 0 ? (weekCount + 'x this week') : '';
        var topSlot;
        if (isMulti && count > 0) {
          topSlot = '<div class="chore-done-hero">&#10003; ' + count + 'x</div>';
        } else if (!isMulti && done) {
          topSlot = '<div class="chore-done-hero">&#10003; ' + done.person + '</div>';
        } else {
          topSlot = '<div class="chore-emoji">' + c.emoji + '</div>';
        }
        return '<button class="btn-chore ' + cssCls + '" onclick="selectChore(\'' + c.name + '\')">' +
          topSlot +
          '<div class="chore-name">' + c.name + '</div>' +
          '<div class="chore-week-count">' + weekLabel + '</div>' +
          '</button>';
      }).join('');
    }
```

Replace it with:

```js
    function renderChoreGrid() {
      var grid = document.getElementById('chore-grid');
      grid.innerHTML = CHORES.map(function(c) {
        var done      = todayDone[c.name];
        var count     = todayCount[c.name] || 0;
        var isMulti   = MULTI_PER_DAY.has(c.name);
        var cssCls    = CHORE_CSS[c.name] || 'chore-litter';
        var weekCount = (weeklyStats.chores && weeklyStats.chores[c.name]) || 0;
        var weekLabel = weekCount > 0 ? (weekCount + 'x this week') : '';
        var overdue   = isOverdue(c.name);
        var topSlot;
        if (isMulti && count > 0) {
          topSlot = '<div class="chore-done-hero">&#10003; ' + count + 'x</div>';
        } else if (!isMulti && done) {
          topSlot = '<div class="chore-done-hero">&#10003; ' + done.person + '</div>';
        } else {
          topSlot = '<div class="chore-emoji">' + c.emoji + '</div>';
        }
        var chip = overdue
          ? '<div class="days-chip">' + overdueChipLabel(c.name) + '</div>'
          : '';
        return '<button class="btn-chore ' + cssCls + (overdue ? ' alert-glow' : '') + '" onclick="selectChore(\'' + c.name + '\')">' +
          chip +
          topSlot +
          '<div class="chore-name">' + c.name + '</div>' +
          '<div class="chore-week-count">' + weekLabel + '</div>' +
          '</button>';
      }).join('');
    }
```

- [ ] **Step 3: Start the app and verify visually in your browser**

```bash
cd /Users/juanca/Projects_2026/ChoreWars
source .venv/bin/activate
python3 app.py
```

Open `http://localhost:5050` in your browser.

**What to check:**
- Any chore with `days_since >= threshold` should show a pulsing red ring + a small red chip ("Xd ago") in the top-right corner of its button
- Chores done today (days_since = 0) should NOT have the glow
- Dishes, Laundry, Trash should never have the glow regardless of when last done
- Tapping an overdue chore button should still open the player select screen normally

**Quick way to force an overdue state for testing** — run this in the DB directly to backdate a record:

```bash
sqlite3 /Users/juanca/Projects_2026/ChoreWars/cleanings.db \
  "UPDATE cleanings SET cleaned_date = date('now', '-5 days') WHERE chore = 'Litter Box' ORDER BY id DESC LIMIT 1;"
```

Then reload the page — Litter Box should show the glow + "5d ago" chip.

Restore after:
```bash
sqlite3 /Users/juanca/Projects_2026/ChoreWars/cleanings.db \
  "UPDATE cleanings SET cleaned_date = date('now') WHERE chore = 'Litter Box' ORDER BY id DESC LIMIT 1;"
```

- [ ] **Step 4: Commit**

```bash
git add templates/index.html
git commit -m "feat: show pulsing glow + days chip on overdue chore buttons"
```

---

### Task 5: Deploy to Pi

- [ ] **Step 1: Kill the local dev server if still running**

```bash
pkill -f "python3 app.py"
```

- [ ] **Step 2: Copy updated files to Pi**

```bash
scp /Users/juanca/Projects_2026/ChoreWars/app.py jc@10.0.0.3:~/ChoreWars/
scp /Users/juanca/Projects_2026/ChoreWars/templates/index.html jc@10.0.0.3:~/ChoreWars/templates/
```

- [ ] **Step 3: SSH into Pi and restart the app**

```bash
ssh jc@10.0.0.3
pkill chromium-browser; pkill python3; sleep 1
cd ~/ChoreWars && nohup python3 app.py > /tmp/app.log 2>&1 &
sleep 2 && DISPLAY=:0 nohup bash ~/ChoreWars/kiosk.sh > /tmp/kiosk.log 2>&1 &
```

- [ ] **Step 4: Verify on Pi**

The kiosk screen should load with any overdue chores glowing red. Confirm data is intact by checking the trophy overlay (★) — all previous records should still be there.

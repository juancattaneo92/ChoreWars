# Chore Attention Indicators — Design Spec
**Date:** 2026-05-23  
**Status:** Approved

---

## Problem

Three chores — Litter Box, Vacuum, and Bathroom — are easy to forget. When the kiosk screen is active, there's no visual signal that any of them are overdue. Users have to remember thresholds mentally.

## Goal

Show a passive visual alert on the chore grid button when a chore hasn't been done in too long. No tap required — the alert is always visible while the screen is active.

---

## Scope

**In scope:**
- Litter Box, Vacuum, Bathroom — the three once-per-day chores that tend to be forgotten

**Out of scope:**
- Dishes, Laundry, Trash — done frequently enough that thresholds aren't needed
- Per-person overdue tracking — the clock resets for either player doing the chore
- Push notifications or sounds — visual only

---

## Thresholds

| Chore | Alert triggers after |
|---|---|
| Litter Box | 3 calendar days |
| Vacuum | 3 calendar days |
| Bathroom | 7 calendar days |

**Calendar days** = `today_date - last_cleaned_date` in whole days (e.g., done Sunday, alert on Wednesday = 3 days).

**Never-logged grace period:** If a chore has never been recorded, treat the earliest-ever record in the database as the reference date. Only trigger the alert once `(today - first_ever_record_date) >= threshold`. If the database has no records at all, no alerts are shown.

---

## Visual Design (approved)

**Option C — Pulsing glow ring + days-ago chip**

When a chore is overdue:
1. **Pulsing red glow ring** — animated `box-shadow` on the button that pulses between 60% and 90% opacity red. Catches the eye without requiring interaction.
2. **"Xd ago" chip** — small red badge in the top-right corner of the button showing how many days since last done (e.g., `"3d ago"`). If never logged and past grace period, shows `"never"`.

Normal, done-today, and multi-per-day chore states are unchanged.

### CSS additions (to `index.html`)
```css
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
  top: 7px; right: 7px;
  background: rgba(239,68,68,0.92);
  color: #fff;
  font-size: 9px; font-weight: 900;
  border-radius: 8px;
  padding: 2px 6px;
  line-height: 1.4;
}
```

---

## Architecture

### New backend endpoint: `GET /api/chore-status`

Single focused query. Returns last `cleaned_date` for each threshold chore plus the earliest-ever record date for grace period calculation.

**Response shape:**
```json
{
  "first_record_date": "2026-01-15",
  "chores": {
    "Litter Box": { "last_date": "2026-05-20", "days_since": 3 },
    "Vacuum":     { "last_date": "2026-05-22", "days_since": 1 },
    "Bathroom":   { "last_date": null,          "days_since": null }
  }
}
```

- `first_record_date` — earliest `cleaned_date` across all records; `null` if DB is empty  
- `last_date` — most recent `cleaned_date` for that chore; `null` if never logged  
- `days_since` — integer calendar days since `last_date`; `null` if never logged  

**Backend implementation (`app.py`):**
- Add constant: `CHORE_THRESHOLDS = {"Litter Box": 3, "Vacuum": 3, "Bathroom": 7}`
- Add `GET /api/chore-status` route that:
  1. Queries `MIN(cleaned_date)` across all records → `first_record_date`
  2. For each key in `CHORE_THRESHOLDS`, queries `MAX(cleaned_date)` filtered by chore name
  3. Computes `days_since` = `(today - last_date).days` if `last_date` is not null
  4. Returns JSON as above

### Frontend changes (`index.html`)

**New constants:**
```js
const CHORE_THRESHOLDS = { "Litter Box": 3, "Vacuum": 3, "Bathroom": 7 };
```

**New state variable:**
```js
let choreStatus = {};  // populated by loadAll()
// shape: { firstRecordDate: "YYYY-MM-DD"|null, chores: { "Litter Box": { daysSince: 3 }, ... } }
```

**`loadAll()` update:**
- Add `fetch('/api/chore-status')` to the existing `Promise.all()`
- Populate `choreStatus` from response

**`renderChoreGrid()` update:**
- For each chore, check if it has a threshold
- Compute `overdue`:
  - If `daysSince !== null`: `overdue = daysSince >= threshold`
  - If `daysSince === null` (never logged): use `firstRecordDate` to compute `daysSinceFirstRecord`; `overdue = daysSinceFirstRecord >= threshold`
  - If `firstRecordDate === null` (empty DB): `overdue = false`
- If `overdue`:
  - Add `alert-glow` class to button (alongside existing color class)
  - Inject `.days-chip` element inside button with label `"Xd ago"` or `"never"`

**No changes to:**
- `selectChore()` — tapping still works the same regardless of overdue state
- `recordClean()` — after a successful log, call `loadAll()` (already happens via `goHome()`) to refresh `choreStatus`

---

## No Database Changes

All queries use the existing `cleanings` table. No migration required.

---

## Files Changed

| File | Change |
|---|---|
| `app.py` | Add `CHORE_THRESHOLDS` constant + `GET /api/chore-status` route |
| `templates/index.html` | Add CSS, constants, state variable, update `loadAll()` and `renderChoreGrid()` |

---

## Deploy

After implementation, copy to Pi:
```bash
scp /Users/juanca/Projects_2026/ChoreWars/app.py jc@10.0.0.3:~/ChoreWars/
scp /Users/juanca/Projects_2026/ChoreWars/templates/index.html jc@10.0.0.3:~/ChoreWars/templates/
```
Then restart Flask + kiosk on the Pi. No DB migration needed.

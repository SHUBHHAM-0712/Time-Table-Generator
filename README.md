# Timetable Generator (Group I)

## Requirements

- Python 3.11+
- PostgreSQL (e.g. Supabase) and `DATABASE_URL` in `.env`

## Setup

1. `.env`:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
```

If the password contains `@` or other reserved characters, percent-encode them (e.g. `@` → `%40`). The loader also accepts the typo key `DATABSE_URL`.

2. Dependencies:

```bash
pip install -r requirements.txt
```

Use **`python3`** to run the app if your system has no `python` command (common on Debian/Ubuntu unless `python-is-python3` is installed).

3. **Database** — run the SQL files in order in your client (or use `python3 -m py_timetable init-db`):

| Order | File |
|-------|------|
| 1 | `sql/001_schema.sql` — DDL |
| 2 | `sql/002_seed.sql` — config, time grid, academic catalog |
| 3 | `sql/003_rooms_actual.sql` — real room codes (clears `master_timetable` / runs if present) |

## Data flow (DB → schedule → output)

1. **Optional CSV import** — bulk load or refresh offerings (does not replace `time_matrix` unless you pass `--slots`):

```bash
python3 -m py_timetable load --csv /path/to/semester.csv
```

2. **Generate** — reads offerings from `batch_course_map`. Use `--term autumn` (semesters 1,3,5), `--term winter` (2,4,6), or `--term all` (default):

```bash
python3 -m py_timetable schedule --label "autumn-run" --term autumn --timeout 300
```

3. **Export**:

```bash
python3 -m py_timetable export --run-id 1 --out output
```

### Web UI

```bash
python3 -m py_timetable serve
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000): pick Autumn / Winter / All when generating; CSV upload is optional (to replace DB data), preview timetables, download Excel/PDF as a ZIP.

## Constraints (summary)

- **Hard:** no double-booking of room, faculty, or batch in a slot; room capacity ≥ batch size; at most one lecture of the same course per batch per calendar day.
- **Soft:** swaps that preserve hard constraints to reduce back-to-back faculty periods.
- **Note:** “max 3 subjects per faculty” is reported when violated in the dataset; it is not a hard constraint.

## Package layout

- `py_timetable/ingest.py` — CSV → relational model  
- `py_timetable/csp_schedule.py` — CSP + soft polishing  
- `py_timetable/export_views.py` — Excel / PDF  
- `py_timetable/db.py` — connection and `init-db`  
- `py_timetable/superblock.py` — Union–Find helper for extensions  
- `py_timetable/web/` — FastAPI UI (`serve` command)  

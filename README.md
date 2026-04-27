# 📚 Time Table Generator – Intelligent Academic Scheduling Platform

> **Enable seamless timetable generation for academic institutions with support for multiple semesters, secure data management, and standardized APIs.**

## 🚀 Problem Statement – _Academic Scheduling Challenge_

> "Enable automated timetable generation for educational institutions with support for multiple batches, secure constraint satisfaction, and standardized export formats."

## 🧩 Key Features

- ✅ Standardized Interface — Easily integrates with academic institutions and their existing systems.
- ✅ Multi-Semester Support — Built with Autumn (1,3,5) and Winter (2,4,6) semester scheduling.
- ✅ Secure Data Management — Manages course data, faculty availability, and room constraints securely.
- ✅ Intelligent Batch Merging — Automatically detects and merges lectures for multiple batches taught by the same faculty.
- ✅ Multi-Format Export — Clean Excel, PDF, and CSV outputs with customizable views.
- ✅ Web UI Interface — Interactive browser-based interface for scheduling, preview, and download.

## 📦 Tech Stack

- Python 3.11+
- FastAPI (Uvicorn)
- PostgreSQL Database
- Pandas (Data Processing)
- OpenPyXL (Excel)
- ReportLab (PDF)
- Psycopg2 (DB Driver)

## 🛠️ Installation & Setup Instructions

### 🔁 Clone the Repository

```bash
git clone https://github.com/SHUBHHAM-0712/Time-Table-Generator.git
cd Time-Table-Generator
```

### 📦 Install Dependencies

```bash
pip install -r requirements.txt
```

### 🏗️ Configure Environment

Create a `.env` file with your database URL:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
```

> If password contains `@` or special characters, percent-encode them (e.g., `@` → `%40`).

### 🗄️ Initialize Database

```bash
python3 -m py_timetable init-db
```

This will run SQL migrations in order:

1. `sql/001_schema.sql` — DDL (tables, constraints)
2. `sql/002_seed.sql` — Seed data (config, time grid)
3. `sql/003_rooms_actual.sql` — Room inventory

## 🧪 Quick Start

### Step 1: Load Course Data

```bash
python3 -m py_timetable load --csv /path/to/courses.csv
```

### Step 2: Generate Timetable

```bash
python3 -m py_timetable schedule --label "autumn-run" --term autumn --timeout 300
```

### Step 3: Export Results

```bash
python3 -m py_timetable export --run-id 1 --out output
```

Generates:

- `schedule_by_batch.xlsx` — Per-batch timetable
- `schedule_by_room.xlsx` — Per-room timetable
- `schedule.pdf` — Printable schedule
- `schedule.csv` — Raw data export

## 🌐 Web UI

Start the interactive web interface:

```bash
python3 -m py_timetable serve
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

**Features:**

- Generate timetable (pick Autumn / Winter / All)
- Upload CSV to refresh data (optional)
- Preview timetables in browser
- Download Excel/PDF as ZIP

## 🔐 Security Considerations

- Uses secure PostgreSQL database for data persistence.
- Enforces strict constraint validation for scheduling accuracy.
- Isolated backend architecture prevents data leaks.
- Session-aware database schema ensures data integrity.

## 🌱 Future Enhancements

- Add support for additional academic programs (e.g., Executive, Online).
- Implement AI-based conflict prediction and resolution.
- UI/UX improvements with theme customization.
- Real-time notification system for schedule changes.
- **Database Integration**: Enhanced NoSQL support for scalability and performance.
- Advanced analytics dashboard for resource utilization.
- Multi-language support for global institutions.

## 🧩 How It Works

The scheduler uses **Constraint Satisfaction Problem (CSP)** algorithms:

- Models courses, batches, faculty as variables
- Applies hard constraints (no double-booking, capacity limits)
- Optimizes soft constraints (minimize back-to-back faculty periods)
- Uses backtracking search with MRV heuristics
- Exports optimized schedule to multiple formats

For detailed algorithm explanation, see **[TIMETABLE_LOGIC.md](./TIMETABLE_LOGIC.md)**.

## 👨‍💻 Team: Core Contributors

- [Shubham](https://github.com/shubham) — Lead Developer
- [Pranshu](https://github.com/pranshu) — Core Contributor

## 📝 Project Structure

**Core Modules:**

- `py_timetable/__main__.py` — CLI entry point
- `py_timetable/csp_schedule.py` — CSP solver & constraint engine
- `py_timetable/ingest.py` — CSV ingestion & normalization
- `py_timetable/db.py` — Database operations
- `py_timetable/export_views.py` — Excel / PDF / CSV export
- `py_timetable/web/` — FastAPI UI

**SQL Migrations:**

- `sql/001_schema.sql` — DDL
- `sql/002_seed.sql` — Seed data
- `sql/003_rooms_actual.sql` — Room inventory

**Tests:**

- `tests/` — Pytest suite (scheduler, ingestion, export, merge logic)

## 📚 Documentation

- **[TIMETABLE_LOGIC.md](./TIMETABLE_LOGIC.md)** — Algorithm deep-dive
- **[SQL Schema](./sql/)** — Database documentation
- **[API Docs](http://localhost:8000/docs)** — Interactive Swagger UI

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit changes (`git commit -m "feat: Add feature"`)
4. Push to branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

<div align="center">

**Made with ❤️ for educational institutions**

</div>

-- Timetable Generator — 3NF schema (PostgreSQL)

-- ---------------------------------------------------------------------------
-- Core entities
-- ---------------------------------------------------------------------------

CREATE TABLE faculty (
    faculty_id       BIGSERIAL PRIMARY KEY,
    short_name       TEXT NOT NULL UNIQUE,
    full_name        TEXT,
    department       TEXT,
    email            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE course (
    course_id        BIGSERIAL PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    lecture_hours    INT NOT NULL CHECK (lecture_hours >= 0),
    tutorial_hours   INT NOT NULL DEFAULT 0 CHECK (tutorial_hours >= 0),
    practical_hours  INT NOT NULL DEFAULT 0 CHECK (practical_hours >= 0),
    credits          NUMERIC(5,2) NOT NULL CHECK (credits > 0),
    course_type      TEXT NOT NULL,
    elective_slot    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE student_batch (
    batch_id         BIGSERIAL PRIMARY KEY,
    batch_code       TEXT NOT NULL UNIQUE,
    program          TEXT NOT NULL,
    semester         INT NOT NULL CHECK (semester > 0),
    section_label    TEXT,
    sub_batch        TEXT,
    batch_size       INT NOT NULL CHECK (batch_size > 0),
    academic_year    INT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE room (
    room_id          BIGSERIAL PRIMARY KEY,
    room_code        TEXT NOT NULL UNIQUE,
    capacity         INT NOT NULL CHECK (capacity > 0),
    room_type        TEXT NOT NULL DEFAULT 'Lecture Hall',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE time_matrix (
    slot_id          BIGSERIAL PRIMARY KEY,
    day_of_week      TEXT NOT NULL,
    start_time       TIME NOT NULL,
    end_time         TIME NOT NULL,
    slot_group       TEXT NOT NULL DEFAULT 'TEACHING',
    is_blackout      BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_time_matrix_day_start UNIQUE (day_of_week, start_time)
);

-- ---------------------------------------------------------------------------
-- Junction: authorized teacher ↔ course (surrogate assignment_id)
-- ---------------------------------------------------------------------------

CREATE TABLE faculty_course_map (
    assignment_id    BIGSERIAL PRIMARY KEY,
    faculty_id       BIGINT NOT NULL REFERENCES faculty (faculty_id) ON DELETE CASCADE,
    course_id        BIGINT NOT NULL REFERENCES course (course_id) ON DELETE CASCADE,
    UNIQUE (faculty_id, course_id)
);

-- Enrollment: which batch takes which course; faculty for that offering (CSV row)
CREATE TABLE batch_course_map (
    batch_id         BIGINT NOT NULL REFERENCES student_batch (batch_id) ON DELETE CASCADE,
    course_id        BIGINT NOT NULL REFERENCES course (course_id) ON DELETE CASCADE,
    faculty_id       BIGINT NOT NULL REFERENCES faculty (faculty_id) ON DELETE CASCADE,
    PRIMARY KEY (batch_id, course_id)
);

-- ---------------------------------------------------------------------------
-- Config & schedule run
-- ---------------------------------------------------------------------------

CREATE TABLE constraint_config (
    config_id        BIGSERIAL PRIMARY KEY,
    key              TEXT NOT NULL UNIQUE,
    value_json       JSONB NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE schedule_run (
    run_id           BIGSERIAL PRIMARY KEY,
    label            TEXT NOT NULL,
    source_csv       TEXT,
    status           TEXT NOT NULL DEFAULT 'draft',
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Final timetable: inherits course+faculty via assignment_id
CREATE TABLE master_timetable (
    timetable_id     BIGSERIAL PRIMARY KEY,
    run_id           BIGINT NOT NULL REFERENCES schedule_run (run_id) ON DELETE CASCADE,
    assignment_id    BIGINT NOT NULL REFERENCES faculty_course_map (assignment_id) ON DELETE CASCADE,
    batch_id         BIGINT NOT NULL REFERENCES student_batch (batch_id) ON DELETE CASCADE,
    room_id          BIGINT NOT NULL REFERENCES room (room_id) ON DELETE RESTRICT,
    slot_id          BIGINT NOT NULL REFERENCES time_matrix (slot_id) ON DELETE RESTRICT,
    lecture_index    INT NOT NULL CHECK (lecture_index >= 1),
    UNIQUE (run_id, batch_id, slot_id),
    UNIQUE (run_id, room_id, slot_id),
    UNIQUE (run_id, assignment_id, slot_id),
    UNIQUE (run_id, assignment_id, batch_id, lecture_index)
);

CREATE INDEX idx_master_timetable_run ON master_timetable (run_id);
CREATE INDEX idx_master_timetable_assignment ON master_timetable (assignment_id);
CREATE INDEX idx_master_timetable_slot ON master_timetable (slot_id);

-- ---------------------------------------------------------------------------
-- Conflict audit (when solver fails or partial)
-- ---------------------------------------------------------------------------

CREATE TABLE conflict_report (
    report_id        BIGSERIAL PRIMARY KEY,
    run_id           BIGINT NOT NULL REFERENCES schedule_run (run_id) ON DELETE CASCADE,
    severity         TEXT NOT NULL,
    category         TEXT NOT NULL,
    detail           TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

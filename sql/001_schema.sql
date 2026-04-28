-- Time-Table Generator — PostgreSQL DDL matching project ERD (PlantUML).

CREATE TABLE faculty (
    faculty_id       BIGSERIAL PRIMARY KEY,
    short_name       TEXT NOT NULL UNIQUE,
    full_name        TEXT,
    created_at       TIMESTAMPTZ
);

CREATE TABLE course (
    course_id        BIGSERIAL PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    lecture_hours    INT,
    tutorial_hours   INT,
    practical_hours  INT,
    credits          NUMERIC(5, 2),
    course_type      TEXT,
    created_at       TIMESTAMPTZ
);

CREATE TABLE student_batch (
    batch_id         BIGSERIAL PRIMARY KEY,
    batch_code       TEXT NOT NULL UNIQUE,
    program          TEXT NOT NULL,
    semester         INT NOT NULL,
    batch_size       INT NOT NULL,
    created_at       TIMESTAMPTZ
);

CREATE TABLE room (
    room_id          BIGSERIAL PRIMARY KEY,
    room_code        TEXT NOT NULL UNIQUE,
    capacity         INT NOT NULL,
    room_type        TEXT,
    created_at       TIMESTAMPTZ
);

CREATE TABLE time_matrix (
    slot_id          BIGSERIAL PRIMARY KEY,
    day_of_week      TEXT NOT NULL,
    start_time       TIME NOT NULL,
    end_time         TIME NOT NULL,
    slot_group       TEXT,
    is_blackout      BOOLEAN,
    CONSTRAINT uq_time_matrix_day_start UNIQUE (day_of_week, start_time)
);

CREATE TABLE faculty_course_map (
    assignment_id    BIGSERIAL PRIMARY KEY,
    faculty_id       BIGINT NOT NULL REFERENCES faculty (faculty_id) ON DELETE CASCADE,
    course_id        BIGINT NOT NULL REFERENCES course (course_id) ON DELETE CASCADE
);

CREATE TABLE batch_course_map (
    batch_id         BIGINT NOT NULL REFERENCES student_batch (batch_id) ON DELETE CASCADE,
    course_id        BIGINT NOT NULL REFERENCES course (course_id) ON DELETE CASCADE,
    faculty_id       BIGINT NOT NULL REFERENCES faculty (faculty_id) ON DELETE CASCADE,
    PRIMARY KEY (batch_id, course_id)
);

CREATE TABLE constraint_config (
    config_id        BIGSERIAL PRIMARY KEY,
    key              TEXT NOT NULL UNIQUE,
    value_json       JSONB NOT NULL,
    updated_at       TIMESTAMPTZ
);

CREATE TABLE schedule_run (
    run_id           BIGSERIAL PRIMARY KEY,
    label            TEXT NOT NULL,
    source_csv       TEXT,
    status           TEXT,
    notes            TEXT,
    created_at       TIMESTAMPTZ
);

CREATE TABLE master_timetable (
    timetable_id     BIGSERIAL PRIMARY KEY,
    run_id           BIGINT NOT NULL REFERENCES schedule_run (run_id) ON DELETE CASCADE,
    assignment_id    BIGINT NOT NULL REFERENCES faculty_course_map (assignment_id) ON DELETE CASCADE,
    batch_id         BIGINT NOT NULL REFERENCES student_batch (batch_id) ON DELETE CASCADE,
    room_id          BIGINT NOT NULL REFERENCES room (room_id) ON DELETE RESTRICT,
    slot_id          BIGINT NOT NULL REFERENCES time_matrix (slot_id) ON DELETE RESTRICT,
    lecture_index    INT
);

CREATE TABLE timetable_session (
    session_id       BIGSERIAL PRIMARY KEY,
    run_id           BIGINT NOT NULL REFERENCES schedule_run (run_id) ON DELETE CASCADE,
    assignment_id    BIGINT NOT NULL REFERENCES faculty_course_map (assignment_id) ON DELETE CASCADE,
    room_id          BIGINT NOT NULL REFERENCES room (room_id) ON DELETE RESTRICT,
    slot_id          BIGINT NOT NULL REFERENCES time_matrix (slot_id) ON DELETE RESTRICT,
    course_id        BIGINT NOT NULL REFERENCES course (course_id) ON DELETE CASCADE,
    faculty_id       BIGINT NOT NULL REFERENCES faculty (faculty_id) ON DELETE CASCADE,
    lecture_index    INT,
    faculty_label    TEXT,
    course_code      TEXT,
    course_title     TEXT,
    group_signature  TEXT,
    total_students   INT,
    batch_count      INT,
    merged           BOOLEAN,
    created_at       TIMESTAMPTZ,
    CONSTRAINT uq_timetable_session_run_assignment_slot UNIQUE (run_id, assignment_id, slot_id)
);

CREATE TABLE timetable_session_batch (
    session_id       BIGINT NOT NULL REFERENCES timetable_session (session_id) ON DELETE CASCADE,
    batch_id         BIGINT NOT NULL REFERENCES student_batch (batch_id) ON DELETE CASCADE,
    PRIMARY KEY (session_id, batch_id)
);

CREATE TABLE conflict_report (
    report_id        BIGSERIAL PRIMARY KEY,
    run_id           BIGINT NOT NULL REFERENCES schedule_run (run_id) ON DELETE CASCADE,
    severity         TEXT,
    category         TEXT,
    detail           TEXT,
    created_at       TIMESTAMPTZ
);

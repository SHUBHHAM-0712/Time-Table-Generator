-- Actual campus rooms (replaces placeholder inventory from earlier seeds).
-- Clears any generated timetables because they reference room_id.
-- Run after 002_seed.sql.

DELETE FROM timetable_session_batch;
DELETE FROM timetable_session;
DELETE FROM master_timetable;
DELETE FROM conflict_report;
DELETE FROM schedule_run;

DELETE FROM room;

INSERT INTO room (room_code, capacity, room_type) VALUES
    ('CEP-102', 150, 'Classroom'),
    ('CEP-003', 150, 'Classroom'),
    ('CEP-103', 150, 'Classroom'),
    ('CEP-104', 150, 'Classroom'),
    ('CEP-105', 150, 'Classroom'),
    ('CEP-106', 150, 'Classroom'),
    ('CEP-107', 150, 'Classroom'),
    ('CEP-108', 150, 'Classroom'),
    ('CEP-109', 150, 'Classroom'),
    ('CEP-110', 150, 'Classroom'),
    ('CEP-202', 90, 'Classroom'),
    ('CEP-203', 90, 'Classroom'),
    ('CEP-204', 90, 'Classroom'),
    ('CEP-205', 90, 'Classroom'),
    ('CEP-206', 90, 'Classroom'),
    ('CEP-207', 90, 'Classroom'),
    ('CEP-209', 90, 'Classroom'),
    ('CEP-210', 90, 'Classroom'),
    ('CEP-211', 90, 'Classroom'),
    ('CEP-212', 90, 'Classroom'),
    ('LT-01', 180, 'Lecture Theatre'),
    ('LT-02', 250, 'Lecture Theatre'),
    ('LT-03', 250, 'Lecture Theatre');

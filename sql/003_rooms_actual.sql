-- Actual campus rooms (replaces placeholder inventory from earlier seeds).
-- Clears any generated timetables because they reference room_id.
-- Run after 002_seed.sql.

DELETE FROM master_timetable;
DELETE FROM conflict_report;
DELETE FROM schedule_run;

DELETE FROM room;

INSERT INTO room (room_code, capacity, room_type) VALUES
    ('CEP-102', 90, 'Classroom'),
    ('CEP-003', 90, 'Classroom'),
    ('CEP-103', 90, 'Classroom'),
    ('CEP-104', 90, 'Classroom'),
    ('CEP-105', 90, 'Classroom'),
    ('CEP-106', 90, 'Classroom'),
    ('CEP-107', 90, 'Classroom'),
    ('CEP-108', 90, 'Classroom'),
    ('CEP-109', 90, 'Classroom'),
    ('CEP-110', 90, 'Classroom'),
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
    ('LT-02', 180, 'Lecture Theatre'),
    ('LT-03', 180, 'Lecture Theatre');

#!/usr/bin/env python3
"""Test script to verify batch merging logic."""

from py_timetable.csp_schedule import merge_batches_by_course_and_faculty

# Test data: HM106 offered to ICTB, MNC, CS, EVD (all semester 1)
test_rows = [
    {
        "assignment_id": 1,
        "faculty_id": 10,
        "faculty_short": "Prof. A",
        "course_id": 101,
        "course_code": "HM106",
        "lecture_hours": 2,
        "course_type": "Core",
        "elective_slot": None,
        "batch_id": 1,
        "batch_code": "ICTB-S1",
        "batch_size": 50,
        "program": "ICTB",
        "semester": 1,
    },
    {
        "assignment_id": 2,
        "faculty_id": 10,
        "faculty_short": "Prof. A",
        "course_id": 101,
        "course_code": "HM106",
        "lecture_hours": 2,
        "course_type": "Core",
        "elective_slot": None,
        "batch_id": 2,
        "batch_code": "MNC-S1",
        "batch_size": 45,
        "program": "MNC",
        "semester": 1,
    },
    {
        "assignment_id": 3,
        "faculty_id": 10,
        "faculty_short": "Prof. A",
        "course_id": 101,
        "course_code": "HM106",
        "lecture_hours": 2,
        "course_type": "Core",
        "elective_slot": None,
        "batch_id": 3,
        "batch_code": "CS-S1",
        "batch_size": 55,
        "program": "CS",
        "semester": 1,
    },
    {
        "assignment_id": 4,
        "faculty_id": 10,
        "faculty_short": "Prof. A",
        "course_id": 101,
        "course_code": "HM106",
        "lecture_hours": 2,
        "course_type": "Core",
        "elective_slot": None,
        "batch_id": 4,
        "batch_code": "EVD-S1",
        "batch_size": 40,
        "program": "EVD",
        "semester": 1,
    },
    # Different course, should not merge
    {
        "assignment_id": 5,
        "faculty_id": 11,
        "faculty_short": "Prof. B",
        "course_id": 102,
        "course_code": "MATH101",
        "lecture_hours": 3,
        "course_type": "Core",
        "elective_slot": None,
        "batch_id": 5,
        "batch_code": "ICTB-S2",
        "batch_size": 50,
        "program": "ICTB",
        "semester": 2,
    },
]

print("Input rows:", len(test_rows))
for r in test_rows:
    print(f"  - {r['course_code']} ({r['batch_code']}) with Prof. {r['faculty_short']}")

merged = merge_batches_by_course_and_faculty(test_rows)

print(f"\nAfter merging: {len(merged)} groups")
for r in merged:
    if r.get("is_merged"):
        batch_codes = ", ".join([f"Batch{bid}" for bid in r.get("merged_batch_ids", [])])
        total_size = r.get("total_batch_size", 0)
        print(f"  ✓ MERGED: {r['course_code']} - {batch_codes} (total size: {total_size})")
    else:
        print(f"  - Single: {r['course_code']} - {r['batch_code']}")

# Verify the merged HM106 has all 4 batches
hm106_merged = [r for r in merged if r["course_code"] == "HM106"][0]
assert hm106_merged["is_merged"] == True, "HM106 should be merged"
assert len(hm106_merged["merged_batch_ids"]) == 4, f"HM106 should have 4 batches, got {len(hm106_merged['merged_batch_ids'])}"
assert hm106_merged["total_batch_size"] == 190, f"Total size should be 190, got {hm106_merged['total_batch_size']}"
print("\n✓ Test passed: HM106 correctly merged 4 batches with total size 190")

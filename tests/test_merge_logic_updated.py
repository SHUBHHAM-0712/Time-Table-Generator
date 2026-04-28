#!/usr/bin/env python3
"""Test script to verify batch merging logic with batch restrictions."""

from py_timetable.csp_schedule import merge_batches_by_course_and_faculty, MERGEABLE_BATCH_PROGRAMS

print("="*70)
print(f"MERGEABLE BATCH PROGRAMS: {MERGEABLE_BATCH_PROGRAMS}")
print("="*70)

# Test 1: Merging allowed batches (ICTB, MNC, CS, EVD)
print("\n\nTest 1: Merging allowed batches (ICTB, MNC, CS, EVD)")
print("="*70)

test_rows_1 = [
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
]

print("Input rows:", len(test_rows_1))
for r in test_rows_1:
    print(f"  - {r['course_code']} ({r['batch_code']}) with Prof. {r['faculty_short']}")

merged_1 = merge_batches_by_course_and_faculty(test_rows_1)

print(f"\nAfter merging: {len(merged_1)} group(s)")
for r in merged_1:
    if r.get("is_merged"):
        batch_codes = ", ".join([f"B{bid}" for bid in r.get("merged_batch_ids", [])])
        total_size = r.get("total_batch_size", 0)
        print(f"  ✓ MERGED: {r['course_code']} - {batch_codes} (total size: {total_size})")
    else:
        print(f"  - SINGLE: {r['course_code']} ({r['batch_code']}) - {r['batch_size']} students")

# Verify the merged HM106 has all 4 batches
hm106_merged = [r for r in merged_1 if r["course_code"] == "HM106"]
assert len(hm106_merged) == 1, f"HM106 should have 1 entry, got {len(hm106_merged)}"
assert hm106_merged[0]["is_merged"] == True, "HM106 should be merged"
assert len(hm106_merged[0]["merged_batch_ids"]) == 4, f"HM106 should have 4 batches"
assert hm106_merged[0]["total_batch_size"] == 190, f"Total size should be 190"
print("\n✓ Test 1 PASSED: HM106 correctly merged 4 allowed batches (total size: 190)")


# Test 2: ICTA is kept separate (NOT merged)
print("\n\nTest 2: ICTA is kept SEPARATE (NOT merged)")
print("="*70)

test_rows_2 = [
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
        "assignment_id": 5,
        "faculty_id": 10,
        "faculty_short": "Prof. A",
        "course_id": 101,
        "course_code": "HM106",
        "lecture_hours": 2,
        "course_type": "Core",
        "elective_slot": None,
        "batch_id": 5,
        "batch_code": "ICTA-S1",
        "batch_size": 60,
        "program": "ICTA",
        "semester": 1,
    },
]

print("Input rows:")
for r in test_rows_2:
    print(f"  - {r['course_code']} ({r['batch_code']}) - Prof. {r['faculty_short']}")

merged_2 = merge_batches_by_course_and_faculty(test_rows_2)

print(f"\nAfter merging: {len(merged_2)} entry/entries")
for r in merged_2:
    if r.get("is_merged"):
        batch_codes = ", ".join([f"B{bid}" for bid in r.get("merged_batch_ids", [])])
        print(f"  ✓ MERGED: {r['course_code']} - {batch_codes}")
    else:
        print(f"  - SEPARATE: {r['course_code']} ({r['batch_code']}) - {r['batch_size']} students")

# Verify results
merged_entries = [r for r in merged_2 if r.get("is_merged")]
separate_entries = [r for r in merged_2 if not r.get("is_merged")]

print(f"\n  - Merged entries: {len(merged_entries)} (ICTB+MNC should be together)")
print(f"  - Separate entries: {len(separate_entries)} (ICTA should be alone)")

# Check that ICTB and MNC are merged
assert len(merged_entries) == 1, f"Should have 1 merged entry, got {len(merged_entries)}"
assert len(merged_entries[0]["merged_batch_ids"]) == 2, "Merged entry should have 2 batches (ICTB+MNC)"

# Check that ICTA is separate
icta_entries = [r for r in separate_entries if "ICTA" in str(r.get("batch_code", ""))]
assert len(icta_entries) == 1, f"ICTA should be separate, got {len(icta_entries)} entries"
assert icta_entries[0]["is_merged"] == False, "ICTA should NOT be marked as merged"
assert icta_entries[0]["total_batch_size"] == 60, "ICTA size should be 60"

print("\n✓ Test 2 PASSED: ICTA correctly kept SEPARATE while ICTB+MNC are merged")


# Test 3: All mergeable batches together
print("\n\nTest 3: All 4 mergeable batches (ICTB, MNC, CS, EVD) with ICTA mixed in")
print("="*70)

test_rows_3 = [
    {
        "assignment_id": 1,
        "faculty_id": 10,
        "faculty_short": "Prof. A",
        "course_id": 101,
        "course_code": "CS101",
        "lecture_hours": 1,
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
        "course_code": "CS101",
        "lecture_hours": 1,
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
        "course_code": "CS101",
        "lecture_hours": 1,
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
        "course_code": "CS101",
        "lecture_hours": 1,
        "course_type": "Core",
        "elective_slot": None,
        "batch_id": 4,
        "batch_code": "EVD-S1",
        "batch_size": 40,
        "program": "EVD",
        "semester": 1,
    },
    {
        "assignment_id": 5,
        "faculty_id": 10,
        "faculty_short": "Prof. A",
        "course_id": 101,
        "course_code": "CS101",
        "lecture_hours": 1,
        "course_type": "Core",
        "elective_slot": None,
        "batch_id": 5,
        "batch_code": "ICTA-S1",
        "batch_size": 60,
        "program": "ICTA",
        "semester": 1,
    },
]

print("Input rows:")
for r in test_rows_3:
    print(f"  - {r['course_code']} ({r['batch_code']})")

merged_3 = merge_batches_by_course_and_faculty(test_rows_3)

print(f"\nAfter merging: {len(merged_3)} entry/entries")
for r in merged_3:
    if r.get("is_merged"):
        batch_codes = ", ".join([str(bc) for bc in r.get("merged_batch_ids", [])])
        print(f"  ✓ MERGED: {r['course_code']} - BatchIDs {batch_codes}")
    else:
        print(f"  - SEPARATE: {r['course_code']} ({r['batch_code']}) - Size {r['batch_size']}")

# Verify we have 2 entries: one merged (4 batches) and one separate (ICTA)
assert len(merged_3) == 2, f"Should have 2 entries (1 merged + 1 separate), got {len(merged_3)}"

merged_count = sum(1 for r in merged_3 if r.get("is_merged"))
separate_count = sum(1 for r in merged_3 if not r.get("is_merged"))

assert merged_count == 1, f"Should have 1 merged entry, got {merged_count}"
assert separate_count == 1, f"Should have 1 separate entry, got {separate_count}"

merged_batch_count = merged_3[0]["merged_batch_ids"] if merged_3[0].get("is_merged") else merged_3[1]["merged_batch_ids"]
assert len(merged_batch_count) == 4, f"Merged entry should have 4 batches"

print("\n✓ Test 3 PASSED: ICTA correctly excluded from merge while 4 allowed batches merged")

print("\n" + "="*70)
print("✅ ALL TESTS PASSED!")
print("="*70)
print("\nSummary:")
print("  ✓ Batches ICTB, MNC, CS, EVD are merged when same course+faculty")
print("  ✓ Batch ICTA is ALWAYS kept separate")
print("  ✓ Cannot merge if ANY batch is outside allowed programs")

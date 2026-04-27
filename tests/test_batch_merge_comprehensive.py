#!/usr/bin/env python3
"""
Comprehensive test demonstrating the batch merging feature.

This test shows how lectures for different batches (ICTB, MNC, EVD, CS) 
are merged when they have the same course code and faculty, allowing 
efficient scheduling with a single timetable slot for all batches.
"""

from py_timetable.csp_schedule import merge_batches_by_course_and_faculty, build_vars

def test_batch_merging_example():
    """
    Scenario: HM106 (Approaches to Indian Society) is offered to 4 batches
    by the same faculty member. The algorithm should:
    
    1. Detect that all 4 batches have the same course code and faculty
    2. Merge them into a single lecture entry
    3. Create a single timetable slot that all 4 batches attend
    4. Calculate combined room capacity requirement (50+45+55+40=190)
    """
    print("\n" + "="*70)
    print("BATCH MERGING FEATURE TEST: HM106 Merged Lecture")
    print("="*70)
    
    # Input: 4 batches, same course, same faculty, semester 1
    input_rows = [
        {
            "assignment_id": 1,
            "faculty_id": 10,
            "faculty_short": "Dr. Smith",
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
            "faculty_short": "Dr. Smith",
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
            "faculty_short": "Dr. Smith",
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
            "faculty_short": "Dr. Smith",
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
    
    print("\n📋 INPUT: 4 separate offerings (one per batch)")
    for i, row in enumerate(input_rows, 1):
        print(f"   {i}. {row['course_code']} ({row['batch_code']}) - {row['batch_size']} students - Prof. {row['faculty_short']}")
    
    # Step 1: Merge batches
    print("\n🔄 MERGING PHASE: Grouping by (course_code, faculty_id, semester)...")
    merged_rows = merge_batches_by_course_and_faculty(input_rows)
    
    print(f"\n✓ AFTER MERGING: {len(merged_rows)} lecture(s)")
    
    # Verify merge results
    assert len(merged_rows) == 1, "Should have exactly 1 merged lecture"
    merged = merged_rows[0]
    
    print(f"\n📊 MERGED LECTURE DETAILS:")
    print(f"   Course Code: {merged['course_code']}")
    print(f"   Faculty: {merged['faculty_short']}")
    print(f"   Is Merged: {merged['is_merged']}")
    print(f"   Merged Batch IDs: {merged['merged_batch_ids']}")
    print(f"   Batch Sizes: {merged['merged_batch_sizes']}")
    print(f"   Total Student Count: {merged['total_batch_size']}")
    print(f"   Combined Batch Codes:")
    for bid, size in zip(merged['merged_batch_ids'], merged['merged_batch_sizes']):
        batch_info = next(r for r in input_rows if r['batch_id'] == bid)
        print(f"      - {batch_info['batch_code']}: {size} students")
    
    # Verify merge correctness
    assert merged["is_merged"] == True, "Should be marked as merged"
    assert merged["merged_batch_ids"] == [1, 2, 3, 4], "Should include all 4 batches"
    assert merged["merged_batch_sizes"] == [50, 45, 55, 40], "Should include all batch sizes"
    assert merged["total_batch_size"] == 190, "Total should be sum of all sizes"
    
    # Step 2: Build lecture variables
    print("\n\n🎯 SCHEDULING PHASE: Building lecture variables...")
    print(f"   Lecture hours: {merged['lecture_hours']}")
    print(f"   Generating {merged['lecture_hours']} lecture variable(s)...")
    
    vars_ = build_vars(merged_rows)
    
    print(f"\n✓ LECTURE VARIABLES CREATED: {len(vars_)}")
    for v in vars_:
        print(f"   Var {v.var_index}: Lecture #{v.lecture_index}")
        print(f"      - Primary batch ID: {v.batch_id}")
        print(f"      - Room capacity needed: {v.batch_size}")
        print(f"      - Is merged: {v.is_merged}")
        if v.is_merged:
            print(f"      - Merged batches: {v.merged_batches}")
    
    # Verify variable creation
    assert len(vars_) == 2, "Should have 2 lecture variables (one per lecture hour)"
    for v in vars_:
        assert v.is_merged == True, "All variables should be marked as merged"
        assert len(v.merged_batches) == 4, "Each variable should track all 4 batches"
        assert v.batch_size == 190, "Batch size should be total combined size"
    
    print("\n" + "="*70)
    print("✅ BATCH MERGING TEST PASSED")
    print("="*70)
    print("\n📌 EXPECTED SCHEDULING OUTCOME:")
    print("   - ONE time slot will be allocated (e.g., Monday 10-11)")
    print("   - ONE room with capacity ≥ 190 will be assigned")
    print("   - ALL 4 batches (ICTB, MNC, CS, EVD) will attend together")
    print("   - Faculty (Dr. Smith) has ONE slot, not 4")
    print("\n")

def test_no_merge_different_faculty():
    """Test that batches with different faculty are NOT merged."""
    print("\n" + "="*70)
    print("TEST: No merge when faculty differs")
    print("="*70)
    
    rows = [
        {
            "assignment_id": 1,
            "faculty_id": 10,
            "faculty_short": "Dr. A",
            "course_id": 101,
            "course_code": "HM106",
            "lecture_hours": 1,
            "course_type": "Core",
            "batch_id": 1,
            "batch_code": "ICTB-S1",
            "batch_size": 50,
            "semester": 1,
        },
        {
            "assignment_id": 2,
            "faculty_id": 11,  # Different faculty!
            "faculty_short": "Dr. B",
            "course_id": 101,
            "course_code": "HM106",
            "lecture_hours": 1,
            "course_type": "Core",
            "batch_id": 2,
            "batch_code": "MNC-S1",
            "batch_size": 45,
            "semester": 1,
        },
    ]
    
    merged = merge_batches_by_course_and_faculty(rows)
    
    print(f"\n✓ Result: {len(merged)} separate lectures (no merge)")
    assert len(merged) == 2, "Should NOT merge when faculty differs"
    assert merged[0]["is_merged"] == False
    assert merged[1]["is_merged"] == False
    print("✅ Test passed: Different faculty prevents merging\n")

if __name__ == "__main__":
    test_batch_merging_example()
    test_no_merge_different_faculty()
    print("\n🎉 All batch merging tests passed!")

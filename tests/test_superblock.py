from __future__ import annotations

from py_timetable.superblock import DisjointSet


def _groups_from_dsu(n: int, dsu: DisjointSet) -> list[list[int]]:
    groups: dict[int, list[int]] = {}
    for idx in range(n):
        groups.setdefault(dsu.find(idx), []).append(idx)
    return list(groups.values())


def test_disjoint_set_unions_elements() -> None:
    dsu = DisjointSet(6)
    dsu.union(0, 1)
    dsu.union(1, 2)
    dsu.union(3, 4)

    assert dsu.find(0) == dsu.find(2)
    assert dsu.find(3) == dsu.find(4)
    assert dsu.find(0) != dsu.find(5)


def test_superblocks_have_no_empty_groups() -> None:
    total_courses = 5
    dsu = DisjointSet(total_courses)
    dsu.union(0, 1)
    dsu.union(2, 3)

    groups = _groups_from_dsu(total_courses, dsu)

    assert groups
    assert all(len(group) > 0 for group in groups)
    flattened = {item for group in groups for item in group}
    assert flattened == set(range(total_courses))

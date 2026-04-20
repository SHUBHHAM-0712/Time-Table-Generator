"""Disjoint-set (Union–Find) for grouping scheduling units into superblocks.

The SRS describes merging related offerings that must occur in the same time
block. The CSP in ``csp_schedule`` schedules individual lecture variables; you
can extend this module to union-merge variables before search when your data
contains explicit “same instant” links (e.g. shared lab sections).
"""


class DisjointSet:
    def __init__(self, n: int) -> None:
        self._p = list(range(n))
        self._r = [0] * n

    def find(self, x: int) -> int:
        if self._p[x] != x:
            self._p[x] = self.find(self._p[x])
        return self._p[x]

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._r[ra] < self._r[rb]:
            ra, rb = rb, ra
        self._p[rb] = ra
        if self._r[ra] == self._r[rb]:
            self._r[ra] += 1

from __future__ import annotations

import random


class WumpusWorld:
    def __init__(self, rows: int, cols: int, pits: int):
        self.rows = rows
        self.cols = cols
        self.pits = pits

        self._pit = [[False for _ in range(cols)] for _ in range(rows)]
        self._wumpus = [[False for _ in range(cols)] for _ in range(rows)]

    def randomize(self) -> None:
        self._pit = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        self._wumpus = [[False for _ in range(self.cols)] for _ in range(self.rows)]

        cells = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) != (0, 0)]
        random.shuffle(cells)

        # place 1 wumpus
        wr, wc = cells[0]
        self._wumpus[wr][wc] = True

        # place pits
        max_pits = max(0, len(cells) - 1)
        to_place = max(0, min(self.pits, max_pits))
        for i in range(1, 1 + to_place):
            pr, pc = cells[i]
            self._pit[pr][pc] = True

    def is_pit(self, r: int, c: int) -> bool:
        return self._pit[r][c]

    def is_wumpus(self, r: int, c: int) -> bool:
        return self._wumpus[r][c]

    def _neighbors(self, r: int, c: int) -> list[tuple[int, int]]:
        n: list[tuple[int, int]] = []
        if r - 1 >= 0:
            n.append((r - 1, c))
        if r + 1 < self.rows:
            n.append((r + 1, c))
        if c - 1 >= 0:
            n.append((r, c - 1))
        if c + 1 < self.cols:
            n.append((r, c + 1))
        return n

    def percepts_at(self, r: int, c: int) -> dict[str, bool]:
        breeze = False
        stench = False
        for nr, nc in self._neighbors(r, c):
            if self._pit[nr][nc]:
                breeze = True
            if self._wumpus[nr][nc]:
                stench = True
        return {"breeze": breeze, "stench": stench}

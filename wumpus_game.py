from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wumpus_world import WumpusWorld
from kb_logic import KnowledgeBase


@dataclass(frozen=True)
class GameConfig:
    rows: int
    cols: int
    pits: int


class WumpusGame:
    def __init__(self, config: GameConfig):
        self.config = config
        self.world = WumpusWorld(config.rows, config.cols, config.pits)
        self.kb = KnowledgeBase()

        self.agent_r = 0
        self.agent_c = 0
        self.moves = 0
        self.game_over = False
        self.status = "Idle"

        self.visited = [[False for _ in range(config.cols)] for _ in range(config.rows)]
        self.safe = [[False for _ in range(config.cols)] for _ in range(config.rows)]

        # danger codes: 0 none, 1 pit confirmed, 2 wumpus confirmed
        self.danger = [[0 for _ in range(config.cols)] for _ in range(config.rows)]

        self.percepts = {"breeze": False, "stench": False}

        # Decision log for dashboard
        self.decision_log: list[dict[str, Any]] = []
        self.current_query: str = ""
        self.last_decision: str = ""

        # Resolution trace
        self._last_trace: dict[str, Any] = {"trace": [], "query": ""}

    def start_new_episode(self) -> None:
        self.world.randomize()
        self.kb.reset()

        self.agent_r = 0
        self.agent_c = 0
        self.moves = 0
        self.game_over = False
        self.status = "Exploring"

        self.visited = [[False for _ in range(self.config.cols)] for _ in range(self.config.rows)]
        self.safe = [[False for _ in range(self.config.cols)] for _ in range(self.config.rows)]
        self.danger = [[0 for _ in range(self.config.cols)] for _ in range(self.config.rows)]

        self.decision_log = []
        self.current_query = ""
        self.last_decision = ""
        self._last_trace = {"trace": [], "query": ""}

        self._visit(0, 0)

    def to_public_state(self) -> dict[str, Any]:
        percepts_list: list[str] = []
        if self.percepts.get("breeze"):
            percepts_list.append("Breeze")
        if self.percepts.get("stench"):
            percepts_list.append("Stench")

        # Build percept map for visualization
        percept_map = [[{"breeze": False, "stench": False} for _ in range(self.config.cols)] for _ in range(self.config.rows)]
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                if self.visited[r][c]:
                    p = self.world.percepts_at(r, c)
                    percept_map[r][c] = p

        return {
            "rows": self.config.rows,
            "cols": self.config.cols,
            "agent": {"r": self.agent_r, "c": self.agent_c},
            "visited": self.visited,
            "safe": self.safe,
            "danger": self.danger,
            "percepts": self.percepts,
            "percepts_list": percepts_list,
            "percept_map": percept_map,
            "metrics": {
                "moves": self.moves,
                "inference_steps": self.kb.inference_steps,
                "kb_clauses": self.kb.num_clauses,
                "status": "Game Over" if self.game_over else self.status,
                "can_step": (not self.game_over and self.status == "Exploring"),
            },
            "decision": {
                "current_query": self.current_query,
                "last_decision": self.last_decision,
                "log": self.decision_log[-20:],  # last 20 decisions
            },
        }

    def get_kb_clauses(self) -> list[str]:
        """Return human-readable representation of all KB clauses."""
        clauses = []
        for cl in self.kb._clauses:
            literals = sorted(cl)
            readable = " ∨ ".join(
                f"¬{lit[1:]}" if lit.startswith("!") else lit
                for lit in literals
            )
            clauses.append(f"({readable})")
        return clauses

    def get_resolution_trace(self) -> dict[str, Any]:
        return self._last_trace

    def _neighbors(self, r: int, c: int) -> list[tuple[int, int]]:
        n: list[tuple[int, int]] = []
        if r - 1 >= 0:
            n.append((r - 1, c))
        if r + 1 < self.config.rows:
            n.append((r + 1, c))
        if c - 1 >= 0:
            n.append((r, c - 1))
        if c + 1 < self.config.cols:
            n.append((r, c + 1))
        return n

    def _visit(self, r: int, c: int) -> None:
        self.agent_r, self.agent_c = r, c
        self.moves += 1

        # If revisiting, just refresh percepts
        if self.visited[r][c]:
            self.percepts = self.world.percepts_at(r, c)
            return

        # If the agent steps into a hazard -> game over
        if self.world.is_pit(r, c):
            self.visited[r][c] = True
            self.danger[r][c] = 1
            self.game_over = True
            self.status = "Fell into pit"
            self.last_decision = f"DEATH: Fell into pit at ({r},{c})"
            self.decision_log.append({"step": self.moves, "msg": self.last_decision})
            return
        if self.world.is_wumpus(r, c):
            self.visited[r][c] = True
            self.danger[r][c] = 2
            self.game_over = True
            self.status = "Eaten by wumpus"
            self.last_decision = f"DEATH: Eaten by wumpus at ({r},{c})"
            self.decision_log.append({"step": self.moves, "msg": self.last_decision})
            return

        # Safe
        self.visited[r][c] = True
        self.safe[r][c] = True

        self.percepts = self.world.percepts_at(r, c)

        # TELL KB
        adj = self._neighbors(r, c)
        self.kb.tell_percepts(r, c, adj, self.percepts["breeze"], self.percepts["stench"])

        # Infer only frontier cells
        self._infer_frontier()

    def _infer_frontier(self) -> None:
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                if self.visited[r][c]:
                    continue
                if self.danger[r][c] != 0:
                    continue

                # frontier: adjacent to visited
                if not any(self.visited[nr][nc] for nr, nc in self._neighbors(r, c)):
                    continue

                if not self.safe[r][c] and self.kb.is_safe(r, c):
                    self.safe[r][c] = True
                    continue

                if self.safe[r][c]:
                    continue

                # confirmed dangers
                if self.kb.is_pit(r, c):
                    self.danger[r][c] = 1
                elif self.kb.is_wumpus(r, c):
                    self.danger[r][c] = 2

    def _bfs_next_step_to_safe_unvisited(self) -> tuple[int, int] | None:
        start = (self.agent_r, self.agent_c)
        queue = [start]
        seen = {start}
        parent: dict[tuple[int, int], tuple[int, int]] = {}

        def passable(r: int, c: int) -> bool:
            if self.danger[r][c] != 0:
                return False
            return self.visited[r][c] or self.safe[r][c]

        while queue:
            cr, cc = queue.pop(0)

            # found target
            if (cr, cc) != start and self.safe[cr][cc] and not self.visited[cr][cc] and self.danger[cr][cc] == 0:
                path = [(cr, cc)]
                cur = (cr, cc)
                while cur in parent:
                    cur = parent[cur]
                    path.append(cur)
                path.reverse()
                return path[1] if len(path) >= 2 else None

            for nr, nc in self._neighbors(cr, cc):
                if (nr, nc) in seen:
                    continue
                if not passable(nr, nc):
                    continue
                seen.add((nr, nc))
                parent[(nr, nc)] = (cr, cc)
                queue.append((nr, nc))

        return None

    def step(self) -> None:
        if self.game_over:
            return

        r, c = self.agent_r, self.agent_c
        adj = self._neighbors(r, c)

        # Prefer safe unvisited neighbor
        for nr, nc in adj:
            if self.visited[nr][nc] or self.danger[nr][nc] != 0:
                continue

            self.current_query = f"ASK: is ({nr},{nc}) safe? → !P_{nr}_{nc} ∧ !W_{nr}_{nc}"

            if self.safe[nr][nc] or self.kb.is_safe(nr, nc):
                self.safe[nr][nc] = True
                self.last_decision = f"MOVE to ({nr},{nc}) — proven safe by KB"
                self.decision_log.append({"step": self.moves + 1, "msg": self.last_decision})
                self._visit(nr, nc)
                return

        # Otherwise BFS to a safe unvisited
        nxt = self._bfs_next_step_to_safe_unvisited()
        if nxt is not None:
            self.last_decision = f"BFS backtrack to ({nxt[0]},{nxt[1]}) toward safe unvisited cell"
            self.decision_log.append({"step": self.moves + 1, "msg": self.last_decision})
            self._visit(nxt[0], nxt[1])
            return

        # Stop if no safe moves
        self.status = "Exploration complete (no safe moves)"
        self.last_decision = "STOP — no more safe moves available"
        self.decision_log.append({"step": self.moves, "msg": self.last_decision})
        self.game_over = True

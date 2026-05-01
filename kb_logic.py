from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def negate(lit: str) -> str:
    return lit[1:] if lit.startswith("!") else "!" + lit


def normalize_clause(literals: Iterable[str]) -> frozenset[str] | None:
    s: set[str] = set()
    for raw in literals:
        lit = str(raw).strip()
        if not lit or lit == "!":
            continue
        comp = negate(lit)
        if comp in s:
            return None  # tautology
        s.add(lit)
    return frozenset(s)


# ─────────────────────────────────────────────────────────────
# Formula AST + CNF conversion (small, purpose-built)
# ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Not:
    arg: object


@dataclass(frozen=True)
class And:
    args: tuple[object, ...]


@dataclass(frozen=True)
class Or:
    args: tuple[object, ...]


@dataclass(frozen=True)
class Implies:
    left: object
    right: object


@dataclass(frozen=True)
class Iff:
    left: object
    right: object


def to_nnf(expr: object, neg: bool = False) -> object:
    if isinstance(expr, Var):
        lit = "!" + expr.name if neg else expr.name
        return ("lit", lit)

    if isinstance(expr, Not):
        return to_nnf(expr.arg, not neg)

    if isinstance(expr, And):
        if neg:
            return ("or", tuple(to_nnf(a, True) for a in expr.args))
        return ("and", tuple(to_nnf(a, False) for a in expr.args))

    if isinstance(expr, Or):
        if neg:
            return ("and", tuple(to_nnf(a, True) for a in expr.args))
        return ("or", tuple(to_nnf(a, False) for a in expr.args))

    if isinstance(expr, Implies):
        # A -> B  ===  ¬A ∨ B
        return to_nnf(Or((Not(expr.left), expr.right)), neg)

    if isinstance(expr, Iff):
        # A <-> B  === (A -> B) ∧ (B -> A)
        return to_nnf(And((Implies(expr.left, expr.right), Implies(expr.right, expr.left))), neg)

    raise TypeError(f"Unknown expression: {expr!r}")


def _distribute(cnf_a: list[list[str]], cnf_b: list[list[str]]) -> list[list[str]]:
    out: list[list[str]] = []
    for a in cnf_a:
        for b in cnf_b:
            merged = normalize_clause([*a, *b])
            if merged is None:
                continue
            out.append(sorted(merged))
    return out


def nnf_to_cnf_clauses(nnf: object) -> list[list[str]]:
    t = nnf[0]

    if t == "lit":
        return [[nnf[1]]]

    if t == "and":
        clauses: list[list[str]] = []
        for part in nnf[1]:
            clauses.extend(nnf_to_cnf_clauses(part))
        return clauses

    if t == "or":
        args = list(nnf[1])
        if not args:
            return []
        cnf = nnf_to_cnf_clauses(args[0])
        for part in args[1:]:
            cnf = _distribute(cnf, nnf_to_cnf_clauses(part))
        return cnf

    raise ValueError(f"Unknown NNF node: {nnf!r}")


# ─────────────────────────────────────────────────────────────
# Resolution Refutation (Set-of-Support)
# ─────────────────────────────────────────────────────────────


class KnowledgeBase:
    def __init__(self) -> None:
        self._clauses: list[frozenset[str]] = []
        self._keys: set[tuple[str, ...]] = set()
        self.inference_steps: int = 0
        self._version: int = 0
        self._cache: dict[tuple[int, str], bool] = {}

    def reset(self) -> None:
        self._clauses = []
        self._keys = set()
        self.inference_steps = 0
        self._version = 0
        self._cache = {}

    @property
    def num_clauses(self) -> int:
        return len(self._clauses)

    def tell_clause(self, clause: Iterable[str]) -> None:
        normalized = normalize_clause(clause)
        if normalized is None:
            return

        key = tuple(sorted(normalized))
        if key in self._keys:
            return

        self._clauses.append(normalized)
        self._keys.add(key)
        self._version += 1
        self._cache.clear()

    def tell_formula(self, formula: object) -> None:
        nnf = to_nnf(formula, False)
        clauses = nnf_to_cnf_clauses(nnf)
        for clause in clauses:
            self.tell_clause(clause)

    def tell_percepts(self, r: int, c: int, adj: list[tuple[int, int]], breeze: bool, stench: bool) -> None:
        # Current cell is safe
        self.tell_clause([f"!P_{r}_{c}"])
        self.tell_clause([f"!W_{r}_{c}"])

        b = f"B_{r}_{c}"
        s = f"S_{r}_{c}"

        pit_vars = [Var(f"P_{ar}_{ac}") for ar, ac in adj]
        w_vars = [Var(f"W_{ar}_{ac}") for ar, ac in adj]

        # Biconditionals (auto CNF conversion)
        if pit_vars:
            self.tell_formula(Iff(Var(b), Or(tuple(pit_vars))))
        if w_vars:
            self.tell_formula(Iff(Var(s), Or(tuple(w_vars))))

        # Observations
        self.tell_clause([b if breeze else f"!{b}"])
        self.tell_clause([s if stench else f"!{s}"])

    def entails(self, goal_lit: str, *, max_steps: int = 20000) -> bool:
        goal_lit = str(goal_lit).strip()
        if not goal_lit:
            return False

        cache_key = (self._version, goal_lit)
        if cache_key in self._cache:
            return self._cache[cache_key]

        entailed, steps = self._resolution_refutation(goal_lit, max_steps=max_steps)
        self.inference_steps += steps
        self._cache[cache_key] = entailed
        return entailed

    def _resolution_refutation(self, goal_lit: str, *, max_steps: int) -> tuple[bool, int]:
        # KB |= goal  iff  KB ∧ ¬goal is UNSAT  iff  derive empty clause.
        base = list(self._clauses)

        # all clauses (for indexing) and set-of-support queue
        all_clauses: list[frozenset[str]] = []
        all_keys: set[tuple[str, ...]] = set()
        idx: dict[str, set[int]] = {}

        def add_clause(cl: frozenset[str]) -> int | None:
            key = tuple(sorted(cl))
            if key in all_keys:
                return None
            ci = len(all_clauses)
            all_clauses.append(cl)
            all_keys.add(key)
            for lit in cl:
                idx.setdefault(lit, set()).add(ci)
            return ci

        for cl in base:
            add_clause(cl)

        start = normalize_clause([negate(goal_lit)])
        if start is None:
            return (False, 0)

        q: list[int] = []
        si = add_clause(start)
        if si is not None:
            q.append(si)

        steps = 0

        while q and steps < max_steps:
            sc_i = q.pop(0)
            sc = all_clauses[sc_i]

            for lit in sc:
                comp = negate(lit)
                for other_i in list(idx.get(comp, set())):
                    if other_i == sc_i:
                        continue
                    other = all_clauses[other_i]

                    # resolvent = (sc - {lit}) U (other - {comp})
                    resolvent = set(sc)
                    resolvent.discard(lit)
                    resolvent.update(other)
                    resolvent.discard(comp)

                    steps += 1

                    norm = normalize_clause(resolvent)
                    if norm is None:
                        continue
                    if len(norm) == 0:
                        return (True, steps)

                    new_i = add_clause(norm)
                    if new_i is not None:
                        q.append(new_i)

        return (False, steps)

    # Domain helpers
    def is_safe(self, r: int, c: int) -> bool:
        return self.entails(f"!P_{r}_{c}") and self.entails(f"!W_{r}_{c}")

    def is_pit(self, r: int, c: int) -> bool:
        return self.entails(f"P_{r}_{c}")

    def is_wumpus(self, r: int, c: int) -> bool:
        return self.entails(f"W_{r}_{c}")

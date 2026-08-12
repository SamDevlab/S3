"""Finite powerset prototype for logical-value residence knowledge.

This is deliberately a research model, not the production S3 representation.
The concrete states below are intentionally tiny so lattice laws can be checked
exhaustively before richer compiler facts are added.
"""

from __future__ import annotations

from enum import Enum, auto
from itertools import combinations
from typing import Iterable, Iterator


class ConcreteResidence(Enum):
    DEAD = auto()
    REGISTER_ONLY = auto()
    MEMORY_ONLY = auto()
    BOTH = auto()


ALL_CONCRETE = frozenset(ConcreteResidence)


class ResidenceFact(frozenset[ConcreteResidence]):
    """Abstract value as a set of possible concrete residence states.

    Information order is subset inclusion: fewer possible concrete states means
    more precise information.  Join is set union and meet is set intersection.
    This yields a finite distributive lattice automatically.
    """

    def __new__(cls, states: Iterable[ConcreteResidence] = ()) -> "ResidenceFact":
        return super().__new__(cls, states)

    def leq(self, other: "ResidenceFact") -> bool:
        return self.issubset(other)

    def join(self, other: "ResidenceFact") -> "ResidenceFact":
        return ResidenceFact(self | other)

    def meet(self, other: "ResidenceFact") -> "ResidenceFact":
        return ResidenceFact(self & other)


BOTTOM = ResidenceFact()
TOP = ResidenceFact(ALL_CONCRETE)
DEAD = ResidenceFact({ConcreteResidence.DEAD})
REGISTER_ONLY = ResidenceFact({ConcreteResidence.REGISTER_ONLY})
MEMORY_ONLY = ResidenceFact({ConcreteResidence.MEMORY_ONLY})
BOTH = ResidenceFact({ConcreteResidence.BOTH})


def _map_fact(
    fact: ResidenceFact,
    transform: dict[ConcreteResidence, ConcreteResidence],
) -> ResidenceFact:
    return ResidenceFact(transform[state] for state in fact)


def compute_value(_: ResidenceFact = TOP) -> ResidenceFact:
    """A fresh scalar computation creates a register/location-flexible value."""

    return REGISTER_ONLY


def materialize(fact: ResidenceFact) -> ResidenceFact:
    """Write the current value to canonical memory when such a value exists."""

    return _map_fact(
        fact,
        {
            ConcreteResidence.DEAD: ConcreteResidence.DEAD,
            ConcreteResidence.REGISTER_ONLY: ConcreteResidence.BOTH,
            ConcreteResidence.MEMORY_ONLY: ConcreteResidence.MEMORY_ONLY,
            ConcreteResidence.BOTH: ConcreteResidence.BOTH,
        },
    )


def clobber_register(fact: ResidenceFact) -> ResidenceFact:
    """Invalidate register-side availability, preserving memory when valid."""

    return _map_fact(
        fact,
        {
            ConcreteResidence.DEAD: ConcreteResidence.DEAD,
            ConcreteResidence.REGISTER_ONLY: ConcreteResidence.DEAD,
            ConcreteResidence.MEMORY_ONLY: ConcreteResidence.MEMORY_ONLY,
            ConcreteResidence.BOTH: ConcreteResidence.MEMORY_ONLY,
        },
    )


def recover_from_memory(fact: ResidenceFact) -> ResidenceFact:
    """Load a valid canonical memory value into a register-like location.

    DEAD/REGISTER_ONLY remain unchanged because this prototype intentionally
    avoids inventing memory validity that is not known.
    """

    return _map_fact(
        fact,
        {
            ConcreteResidence.DEAD: ConcreteResidence.DEAD,
            ConcreteResidence.REGISTER_ONLY: ConcreteResidence.REGISTER_ONLY,
            ConcreteResidence.MEMORY_ONLY: ConcreteResidence.BOTH,
            ConcreteResidence.BOTH: ConcreteResidence.BOTH,
        },
    )


def all_facts() -> Iterator[ResidenceFact]:
    states = tuple(ConcreteResidence)
    for size in range(len(states) + 1):
        for subset in combinations(states, size):
            yield ResidenceFact(subset)


def validate_lattice_laws() -> None:
    """Exhaustively check elementary finite-lattice laws for the prototype."""

    facts = tuple(all_facts())
    assert BOTTOM.leq(TOP)

    for a in facts:
        assert a.join(a) == a
        assert a.meet(a) == a
        assert a.join(BOTTOM) == a
        assert a.meet(TOP) == a
        for b in facts:
            assert a.join(b) == b.join(a)
            assert a.meet(b) == b.meet(a)
            assert a.meet(a.join(b)) == a
            assert a.join(a.meet(b)) == a
            for c in facts:
                assert a.join(b.join(c)) == a.join(b).join(c)
                assert a.meet(b.meet(c)) == a.meet(b).meet(c)
                # Powerset lattices are distributive.
                assert a.meet(b.join(c)) == a.meet(b).join(a.meet(c))
                assert a.join(b.meet(c)) == a.join(b).meet(a.join(c))


def validate_transfer_monotonicity() -> None:
    """Check that the current transfer functions are monotone in subset order."""

    facts = tuple(all_facts())
    transforms = (materialize, clobber_register, recover_from_memory)
    for transform in transforms:
        for a in facts:
            for b in facts:
                if a.leq(b):
                    assert transform(a).leq(transform(b)), (transform.__name__, a, b)

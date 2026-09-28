"""The factory decision enum and its total projection onto ``QualificationStatus``.

The factory recognises six decision states. ``ornix-tts`` recognises four. The
two extras, ``PENDING`` and ``REVIEW``, are factory-only: they describe work that
has not been decided, and a multi-stage run needs to say so rather than force a
refusal.

``to_ornix_status`` is the single conversion point between the two vocabularies.
It is total over the four admissible states and raises
:class:`DecisionMappingError` for the other two. It never guesses, never
defaults to ``ACCEPTED``, and never degrades a refusal into a pass.

See ADR 0003. A conforming implementation is forced by the runtime check in
:func:`assert_projection_is_total`, which :func:`to_ornix_status` calls.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from ornix.data.qualification import QualificationStatus

from .errors import DecisionMappingError

__all__ = [
    "ADMISSIBLE_STATES",
    "FACTORY_ONLY_STATES",
    "DecisionState",
    "assert_projection_is_total",
    "is_admissible",
    "to_ornix_status",
]


class DecisionState(StrEnum):
    """Canonical decision vocabulary of the data factory.

    ``ACCEPT`` is the only state that may enter a training release.
    """

    PENDING = "PENDING"
    ACCEPT = "ACCEPT"
    REVIEW = "REVIEW"
    REJECT = "REJECT"
    BLOCKED = "BLOCKED"
    DUPLICATE = "DUPLICATE"


FACTORY_ONLY_STATES: Final[frozenset[DecisionState]] = frozenset(
    {DecisionState.PENDING, DecisionState.REVIEW}
)
"""States with no ``QualificationStatus`` representation."""

ADMISSIBLE_STATES: Final[frozenset[DecisionState]] = frozenset(DecisionState) - FACTORY_ONLY_STATES
"""States that can be projected onto the downstream contract."""


_PROJECTION: Final[dict[DecisionState, QualificationStatus]] = {
    DecisionState.ACCEPT: QualificationStatus.ACCEPTED,
    DecisionState.REJECT: QualificationStatus.REJECTED,
    DecisionState.BLOCKED: QualificationStatus.BLOCKED,
    DecisionState.DUPLICATE: QualificationStatus.DUPLICATE,
}

_REASONS: Final[dict[DecisionState, str]] = {
    DecisionState.PENDING: "not yet evaluated at this stage",
    DecisionState.REVIEW: "evidence missing, unavailable, or borderline",
}


def is_admissible(state: DecisionState) -> bool:
    """Return whether a state can cross the Ornix-TTS boundary."""
    return state in ADMISSIBLE_STATES


def to_ornix_status(state: DecisionState) -> QualificationStatus:
    """Project a factory decision onto the downstream qualification status.

    Raises:
        DecisionMappingError: if ``state`` is ``PENDING`` or ``REVIEW``. These
            describe a decision the factory has not made, and a downstream
            contract has no lane for them. Passing them off as ``ACCEPTED`` is
            the "missing evidence becomes PASS" failure this exists to prevent.
        TypeError: if ``state`` is not a :class:`DecisionState`.

    """
    if isinstance(state, str) and not isinstance(state, DecisionState):
        raise TypeError(f"state must be DecisionState; received {type(state).__name__}")
    assert_projection_is_total()
    projected = _PROJECTION.get(state)
    if projected is None:
        raise DecisionMappingError(
            f"decision state {state.value!r} has no QualificationStatus representation: "
            f"{_REASONS[state]}"
        )
    return projected


def assert_projection_is_total() -> None:
    """Verify the projection covers every admissible state exactly once.

    Called on each :func:`to_ornix_status` invocation so that adding a member to
    ``DecisionState`` without extending the projection fails loudly, at the call
    site, instead of silently producing a ``REVIEW`` in a release.
    """
    if frozenset(_PROJECTION) != ADMISSIBLE_STATES:
        missing = sorted(state.value for state in ADMISSIBLE_STATES - frozenset(_PROJECTION))
        extra = sorted(state.value for state in frozenset(_PROJECTION) - ADMISSIBLE_STATES)
        raise DecisionMappingError(
            f"projection is not total over the admissible states; missing={missing} extra={extra}"
        )

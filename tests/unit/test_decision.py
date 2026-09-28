"""Decision-state projection tests (ADR 0003).

These are the tests that prove the factory cannot quietly convert missing
evidence into a downstream pass.
"""

from __future__ import annotations

import pytest
from ornix.data.qualification import QualificationStatus

from ornix_data.contracts.decision import (
    ADMISSIBLE_STATES,
    FACTORY_ONLY_STATES,
    DecisionState,
    assert_projection_is_total,
    is_admissible,
    to_ornix_status,
)
from ornix_data.contracts.errors import DecisionMappingError

_EXPECTED_PROJECTION = {
    DecisionState.ACCEPT: QualificationStatus.ACCEPTED,
    DecisionState.REJECT: QualificationStatus.REJECTED,
    DecisionState.BLOCKED: QualificationStatus.BLOCKED,
    DecisionState.DUPLICATE: QualificationStatus.DUPLICATE,
}


def test_enum_has_exactly_the_six_specified_states() -> None:
    assert {state.value for state in DecisionState} == {
        "PENDING",
        "ACCEPT",
        "REVIEW",
        "REJECT",
        "BLOCKED",
        "DUPLICATE",
    }


def test_factory_only_states_are_exactly_pending_and_review() -> None:
    expected = {DecisionState.PENDING, DecisionState.REVIEW}
    assert set(FACTORY_ONLY_STATES) == expected


def test_admissible_states_are_the_complement() -> None:
    expected = set(DecisionState) - set(FACTORY_ONLY_STATES)
    assert set(ADMISSIBLE_STATES) == expected
    assert not set(ADMISSIBLE_STATES) & set(FACTORY_ONLY_STATES)


@pytest.mark.parametrize(
    ("state", "expected"),
    sorted(_EXPECTED_PROJECTION.items(), key=lambda item: item[0].value),
)
def test_projection_matches_the_adr_table(
    state: DecisionState, expected: QualificationStatus
) -> None:
    assert to_ornix_status(state) is expected


@pytest.mark.parametrize("state", sorted(FACTORY_ONLY_STATES, key=lambda item: item.value))
def test_factory_only_states_raise(state: DecisionState) -> None:
    with pytest.raises(DecisionMappingError) as caught:
        to_ornix_status(state)
    assert state.value in str(caught.value)


@pytest.mark.parametrize("state", sorted(FACTORY_ONLY_STATES, key=lambda item: item.value))
def test_factory_only_states_never_reach_the_boundary(state: DecisionState) -> None:
    with pytest.raises(DecisionMappingError):
        to_ornix_status(state)
    assert not is_admissible(state)


def test_projection_is_total_over_admissible_states() -> None:
    assert_projection_is_total()
    for state in sorted(ADMISSIBLE_STATES, key=lambda item: item.value):
        assert isinstance(to_ornix_status(state), QualificationStatus)


def test_missing_evidence_states_never_map_to_accepted() -> None:
    for state in FACTORY_ONLY_STATES:
        with pytest.raises(DecisionMappingError):
            to_ornix_status(state)


def test_plain_string_is_rejected() -> None:
    with pytest.raises(TypeError):
        to_ornix_status("ACCEPT")  # type: ignore[arg-type]


def test_only_accept_enters_a_release() -> None:
    release_states = {
        state
        for state in DecisionState
        if is_admissible(state) and state is not DecisionState.ACCEPT
    }
    assert release_states == {
        DecisionState.REJECT,
        DecisionState.BLOCKED,
        DecisionState.DUPLICATE,
    }

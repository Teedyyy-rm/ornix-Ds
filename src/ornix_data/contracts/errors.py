"""Structured error hierarchy for the data factory.

The factory has its own error tree because it has its own failure modes. It does
not subclass ``ornix.data.errors`` types: those belong to the downstream
contract, and raising them here would blur which layer refused the work.

The one exception is :class:`ContractIncompatibleError`, which is raised only
when the installed ``ornix-tts`` cannot satisfy the boundary this repository
depends on. It is a build-stopping condition, never a recoverable one.
"""

from __future__ import annotations

__all__ = [
    "AcquisitionError",
    "ConfigurationError",
    "ContractIncompatibleError",
    "DataFactoryError",
    "DecisionMappingError",
    "EvidenceUnavailableError",
    "PipelineError",
    "PolicyError",
    "ProvenanceError",
    "ReleaseError",
    "RightsBlockedError",
    "StateError",
]


class DataFactoryError(Exception):
    """Base class for every error raised by ``ornix_data``."""


class ConfigurationError(DataFactoryError):
    """A versioned configuration is missing, malformed, or rejects a field."""


class ContractIncompatibleError(DataFactoryError):
    """The installed ``ornix-tts`` cannot satisfy the boundary this build needs.

    This is a build-stopping condition. The factory has no local fallback schema
    (``ARCHITECTURE.md`` section 25, ADR 0008 section 8.5), so a release cannot be
    produced when the downstream contract is unavailable or has diverged.
    """


class DecisionMappingError(DataFactoryError):
    """A factory decision state has no ``QualificationStatus`` representation.

    Raised for :attr:`DecisionState.PENDING` and :attr:`DecisionState.REVIEW`,
    which are factory-only and must never cross the boundary (ADR 0003).
    """


class PolicyError(DataFactoryError):
    """A quality or rights policy refused a record."""


class RightsBlockedError(PolicyError):
    """Rights or provenance prevent use of a source. Fail-closed."""


class EvidenceUnavailableError(DataFactoryError):
    """A required evidence provider could not produce a measurement.

    Callers translate this into ``DecisionState.REVIEW``. It must never be
    translated into an ``ACCEPT`` or into a zero-valued metric
    (ADR 0005, ADR 0008 section 8.1).
    """


class ProvenanceError(DataFactoryError):
    """A transformation lacks the lineage required to be auditable."""


class AcquisitionError(DataFactoryError):
    """A source could not be inventoried, downloaded, or staged immutably."""


class StateError(DataFactoryError):
    """The transactional run state is missing, inconsistent, or unwritable."""


class PipelineError(DataFactoryError):
    """A pipeline phase failed in a way that is not attributable to one record."""


class ReleaseError(DataFactoryError):
    """A release is incomplete, unverifiable, or must not be labelled READY."""

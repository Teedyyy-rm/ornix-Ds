"""Factory-owned contracts: decisions, evidence, provenance and artifacts.

Nothing in this package redefines a contract owned by ``ornix-tts``. The
downstream ``ManifestRecord``, ``Provenance``, ``QualityVector``,
``DedupFingerprint``, ``SplitPolicy`` and ``VADProvider`` are imported from
there and used as-is (ADR 0008 section 8.5).
"""

from __future__ import annotations

from .decision import (
    ADMISSIBLE_STATES,
    FACTORY_ONLY_STATES,
    DecisionState,
    assert_projection_is_total,
    is_admissible,
    to_ornix_status,
)
from .errors import (
    AcquisitionError,
    ConfigurationError,
    ContractIncompatibleError,
    DataFactoryError,
    DecisionMappingError,
    EvidenceUnavailableError,
    PipelineError,
    PolicyError,
    ProvenanceError,
    ReleaseError,
    RightsBlockedError,
    StateError,
)

__all__ = [
    "ADMISSIBLE_STATES",
    "FACTORY_ONLY_STATES",
    "AcquisitionError",
    "ConfigurationError",
    "ContractIncompatibleError",
    "DataFactoryError",
    "DecisionMappingError",
    "DecisionState",
    "EvidenceUnavailableError",
    "PipelineError",
    "PolicyError",
    "ProvenanceError",
    "ReleaseError",
    "RightsBlockedError",
    "StateError",
    "assert_projection_is_total",
    "is_admissible",
    "to_ornix_status",
]

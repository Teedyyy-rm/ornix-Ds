"""The data admission and evidence layer for Ornix-TTS.

Every record this package produces is built through ``ornix.data.ManifestRecord``
and ``ornix.data.Provenance`` from the installed ``ornix-tts`` package. This
package never defines a look-alike of a contract it does not own
(``ARCHITECTURE.md`` section 25, ADR 0008 section 8.5).
"""

from __future__ import annotations

__version__ = "0.0.0"

__all__ = ["__version__"]

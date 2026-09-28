# Architecture Decision Records

Normative. An ADR is **accepted** when it appears in the index table below with status
`Accepted`. Changing an accepted decision requires a new ADR that supersedes it, plus a
reconciliation entry in `MEMORY.md`.

| ADR | Title | Status | Blocks |
|---|---|---|---|
| [0001](0001-release-audio-at-48khz.md) | Release audio at 48 kHz, enforced by the factory | Accepted | Phase Q |
| [0002](0002-single-resampler.md) | One resampler: call `ornix.audio`, never reimplement | Accepted | Phase F |
| [0003](0003-decision-state-mapping.md) | The factory owns `PENDING` and `REVIEW` | Accepted | Phase A |
| [0004](0004-text-normalization-ownership.md) | Comparison normalization is not canonical text | Accepted | Phase M |
| [0005](0005-accept-requires-evidence.md) | `ACCEPT` requires computed evidence, not merely "no error" | Accepted | Phase L |
| [0006](0006-segmentation-ownership.md) | Factory owns boundaries; `Ornix-TTS` owns windows | Accepted | Phase K |
| [0007](0007-transactional-state-in-sqlite.md) | SQLite is the only authoritative run state | Accepted | Phase B |
| [0008](0008-no-repair-no-fabrication.md) | No repair, no fabrication, no hidden defaults | Accepted | All |

## Format

Every ADR states: **Context** (evidence, with citations), **Decision**, **Consequences**
(positive, negative, and what becomes impossible), **Alternatives rejected** with the
specific reason, and **Verification** (the test that proves the decision was honoured).

An ADR without a verification clause is a preference, not a decision.

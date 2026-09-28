# ADR 0003 — The factory owns `PENDING` and `REVIEW`

- **Status:** Accepted
- **Date:** 2026-09-29
- **Blocks:** Phase A (contracts), Phase L (policy)
- **Evidence:** `docs/ANALYSIS.md` §3

## Context

The seed architecture §22 mandates six decision states:

```text
PENDING  ACCEPT  REVIEW  REJECT  BLOCKED  DUPLICATE
```

`Ornix-TTS` has four — `qualification.py:43-47`:

```python
class QualificationStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    DUPLICATE = "DUPLICATE"
```

`PENDING` and `REVIEW` do not exist anywhere in `ornix.data` — not in the enum, not in the
82-name `__all__`, not in the module. `qualify_records` is synchronous and total: every input
record ends in one of the four. There is no queued lane and no human-in-the-loop lane.

The only affordance resembling escalation is
`QualificationConfig.require_known_rights=False` (`:105`) — and it resolves to `ACCEPTED`,
**not** to a review state. It is a trust-boundary escape hatch, not a review queue.

This collides with the spec's acceptance criterion *"Unavailable required detectors lead to
REVIEW."* That is a correct safety property with **no downstream home**.

## Decision

1. `ornix_data.contracts.decision.DecisionState` is the factory's canonical enum, with exactly
   the six states above. It is a **superset** of the downstream enum.
2. **`PENDING` and `REVIEW` are factory-only.** They never cross the boundary. They exist
   because a run is multi-stage and evidence is often unavailable; both mean *"not admissible
   on the evidence available"*.
3. A projection function `to_ornix_status(state: DecisionState) -> QualificationStatus` maps
   the four admissible states and **raises `DecisionMappingError` on `PENDING` and `REVIEW`**.
   It never guesses, never defaults to `ACCEPTED`, and never degrades a refusal into a pass.
4. **Only `ACCEPT` enters a training release.** `REJECT`, `BLOCKED`, `DUPLICATE` are recorded
   in the release reports and excluded from `manifest.jsonl`. `PENDING` and `REVIEW` are
   likewise excluded, and are additionally reported with the reason evidence was missing.
5. `REVIEW` is a **queue**, not a decision. A run that ends with a non-empty `REVIEW` queue is
   a **successful run with pending work**, not a failed run. It does not block the release of
   the `ACCEPT` set, but the release metadata must record the outstanding count and the
   `REVIEW` report ships alongside the manifest.
6. `REVIEW` is entered when, and only when, evidence is **missing, unavailable, or borderline**
   — never when evidence positively shows failure. Positive failure is `REJECT`. This
   distinction is the whole point of the state and must be preserved through refactors.

### Mapping table (normative)

| Factory state | `QualificationStatus` | Meaning | In release? |
|---|---|---|---|
| `PENDING` | *raises* | not yet evaluated at this stage | no |
| `ACCEPT` | `ACCEPTED` | every mandatory gate passed **with evidence** | **yes** |
| `REVIEW` | *raises* | evidence missing / unavailable / borderline | no (reported) |
| `REJECT` | `REJECTED` | available evidence proves failure | no (reported) |
| `BLOCKED` | `BLOCKED` | rights / provenance / contract prevents use | no (reported) |
| `DUPLICATE` | `DUPLICATE` | usable but removed by dedup policy | no (reported) |

## Consequences

**Positive**

- The spec's "unavailable required detector → `REVIEW`" rule is expressible and safe.
- Downstream never sees a state it cannot represent.
- `REVIEW` becomes a visible work queue with an owner, instead of a silent acceptance.
- `BLOCKED` for rights is preserved exactly: upstream `BLOCKED` has exactly one cause
  (`RIGHTS_BLOCKED:`, `qualification.py:470`), and the factory never invents others into that
  lane.

**Negative**

- Two enums must be kept in sync manually. Mitigated by making the projection the **only**
  conversion point, total, exhaustive, and unit-tested over all six inputs.
- A `REVIEW` queue needs a triage mechanism (CLI export, adjudication policy) that does not
  exist yet. That is Phase L scope.
- A release with a large `REVIEW` count is technically valid but operationally weak. The
  release metadata must surface it, and CI should be able to set a review-rate ceiling.

**Becomes impossible**

- Converting missing evidence into `ACCEPT` at the boundary.
- A record entering `manifest.jsonl` in any state other than `ACCEPT`.

## Alternatives rejected

1. **Collapse to the four downstream states; map `REVIEW` → `ACCEPTED`.** Rejected: this is
   precisely the "missing evidence becomes PASS" failure the spec forbids at §0.
2. **Collapse `REVIEW` → `REJECT`.** Rejected: it destroys the distinction between *"we could
   not tell"* and *"we know it is bad"*, biases the corpus toward whatever the available
   detectors happen to cover, and makes detector outages look like quality failures.
3. **Push `REVIEW` upstream as a new `QualificationStatus` member.** Rejected for now: it
   would modify a contract `ornix-Ds` must not redefine, and `Ornix-TTS` has no
   human-in-the-loop concept to hang it on. Revisit if `ornix-tts` grows an adjudication lane;
   the projection function is the seam where that would land.
4. **Keep `PENDING` in the downstream enum.** Rejected: absence from the result already means
   "not processed", and adding an enum member changes a contract we do not own.

## Verification

```python
@pytest.mark.parametrize("state", [DecisionState.PENDING, DecisionState.REVIEW])
def test_unmappable_states_raise(state):
    with pytest.raises(DecisionMappingError):
        to_ornix_status(state)

def test_projection_is_total_over_admissible_states():
    for state in (ACCEPT, REJECT, BLOCKED, DUPLICATE):
        assert isinstance(to_ornix_status(state), QualificationStatus)

def test_release_contains_only_accept_records(release):
    assert {r.decision for r in release.rows} == {DecisionState.ACCEPT}
```

Plus a manifest test asserting that a `REVIEW` record never appears in `manifest.jsonl`, and
a review-queue test asserting a detector outage produces `REVIEW` (not `REJECT`, not
`ACCEPT`).

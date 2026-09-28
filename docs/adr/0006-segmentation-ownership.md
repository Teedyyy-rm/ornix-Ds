# ADR 0006 — Factory owns boundaries; `Ornix-TTS` owns windows

- **Status:** Accepted
- **Date:** 2026-09-29
- **Blocks:** Phase H (VAD), Phase K (segmentation)
- **Evidence:** `docs/ANALYSIS.md` §10

## Context

Segmentation appears in both repositories, at two different levels, and the seed
architecture only names the factory side.

**`Ornix-TTS` owns window segmentation**, and it is wired in:

- `WindowSegmentationPolicy` — `data/segmentation.py:155-181`; `window_s=10.0`,
  `stride_s=None`, `max_segments=None`, `jitter_s=0.0`,
  `revision="ornix-window-segmentation-v1"`.
- `seeded_window_segments(...)` — `:204-270`. Fully deterministic:
  `_seed_fraction = sha256(canonical_json({...}))[:8]` big-endian over `2**64`. No RNG object,
  no global state.
- `segment_id_for(...)` — `:51-76` → `"seg-" + sha256(canonical_json(payload))` over
  `{source_record_id, start_s, end_s, segmentation_revision, seed}`. Purely metadata-derived.
- `SEGMENTATION_REVISION = "ornix-window-segmentation-v1"` — `:14`.
- `qualify_records` calls it as **stage 3 of every accepted record**
  (`qualification.py:497-526`, with `channel=0`). Not optional configuration — it always runs.
- The policy `revision` is hashed into `QualificationConfig.identity()` (`:139-146`), so
  changing it changes `QualificationReport.content_hash()`; and `segment_id` is
  content-addressed, so a different policy breaks downstream joins.

**`Ornix-TTS` does not own speech-boundary detection.** `VADProvider`
(`segmentation.py:184-189`) is `@runtime_checkable` with one method,

```python
def regions(self, source_record_id: str, *, duration_s: float
            ) -> Sequence[tuple[float, float]]: ...
```

`search_code` over `^src/` returns only the declaration — **no implementation exists**, and
`seeded_window_segments` neither accepts nor calls it. Forced alignment is likewise
spec-only (`docs/specs/data_pipeline_spec.md:235`).

The seed architecture §15 is right that boundary integrity is mandatory for TTS and belongs
here. It is wrong to read §20's `curation/segmentation.py` as "reimplement window
segmentation".

The legacy repo solved only half of it: `curation/segmentation.py:25-46` `low_energy_points`
finds local RMS minima as cut candidates, and `plan_segments` (`:74-121`) snaps arithmetic
cuts to the nearest trough, marking `uncertain_indices` when none is within
`snap_tol_s=0.35`. The `uncertain_indices → re-verify transcript` idea is worth keeping. The
energy heuristic is not a boundary model: no onset/offset reasoning, no learned detector, no
alignment.

## Decision

Two levels, two owners, no overlap:

| Level | Question | Owner | Revision identity |
|---|---|---|---|
| **Utterance boundary** | *Where does this utterance actually start and end, and is it cut mid-phoneme?* | **`ornix-Ds`** | `ornix-ds-boundary-v1` |
| **Training window** | *Which 10 s windows of this record should the model see?* | **`Ornix-TTS`** | `ornix-window-segmentation-v1` |

1. The factory implements a real `VADProvider` conformant to the upstream Protocol, plus the
   project-owned `quality/boundaries.py` detector required by §15.
2. The factory **calls** `seeded_window_segments` for window planning and **does not**
   reimplement it. Its `segment_id` values are what downstream joins on.
3. The factory's boundary output is **evidence attached to the canonical master record**, not
   a competing `Segment` set. A record that already has clean boundaries is not re-cut.
4. Factory boundaries use **sample indices on the master**, so the release's
   `segment start sample` / `segment end sample` are exact and feed sample identity
   deterministically (spec §27). The factory's own segment key is a separate namespaced hash
   and never collides with `"seg-..."`.
5. Boundary evidence is mandatory for TTS, per §15. A record whose boundaries are unknown or
   indeterminate is `REVIEW`, not `ACCEPT`.
6. The provider-protocol shape (`provider_id`, `model_id`, `model_revision`, `weights_sha256`,
   `runtime`, `device`, `status`) is uniform across every factory provider, including VAD,
   ASR, speaker and events.

## Consequences

**Positive**

- No duplicated windowing logic; downstream joins keep working because `segment_id` and
  `SEGMENTATION_REVISION` stay upstream-owned.
- Boundary integrity — the failure mode generic MOS metrics miss entirely (missing initial
  consonants, cut vowels, cut final syllables) — is a first-class, mandatory gate.
- Sample-index boundaries give deterministic sample identity, independent of float rounding.
- One provider protocol across all detectors, satisfying §3 and §32 uniformly.

**Negative**

- The factory must run two segmentation concepts, and the distinction between
  "utterance extent" and "training window" has to be explained to every new reader.
- Exact sample indices require the factory to hold the decoded master, not just a
  resampled view.
- The VAD provider is on the critical path, so its unavailability is a `REVIEW` generator
  (correct, but it costs yield).

**Becomes impossible**

- Reimplementing `seeded_window_segments` and diverging `segment_id` values.
- A `REVIEW`-free release that contains a record with indeterminate boundaries.

## Alternatives rejected

1. **Factory owns all segmentation; upstream windows are removed.** Rejected: it changes
  `qualify_records` behaviour, which `ornix-Ds` must not do, and invalidates
  `QualificationReport.content_hash()` for every existing consumer.
2. **Factory defines its own `VADProvider` with a different signature.** Rejected: the
   Protocol is a declared extension point upstream; conforming to it is the whole point of
   its existence.
3. **Keep the energy-trough heuristic from the legacy repo.** Rejected: an RMS-minimum
   heuristic cannot detect a cut vowel, which is the primary failure this ADR exists to catch.
4. **Make boundary checks advisory.** Rejected: §15 — *"A clean TTS corpus MUST not rely only
   on generic MOS/noise metrics."*

## Verification

```python
def test_window_segmentation_is_delegated(...):
    # factory calls seeded_window_segments; factory source contains no windowing implementation
    ...

def test_boundary_fixture_detects_cut_vowel():
    r = run_on_fixture("cut_vowel_48k.wav")
    assert r.decision == DecisionState.REJECT
    assert r.evidence["boundary_status"] != "OK"

def test_missing_initial_consonant_is_detected():
    r = run_on_fixture("missing_initial_consonant.wav")
    assert r.evidence["head_clip_probability"] > POLICY.head_clip_max

def test_factory_vad_provider_satisfies_upstream_protocol():
    assert isinstance(SileroVadProvider(...), VADProvider)

def test_segment_id_namespace_does_not_collide(run):
    assert all(not s.segment_id.startswith("seg-") for s in run.factory_segments)
```

Compatibility suite: records produced by the factory yield the same `segment_id` values
under upstream `seeded_window_segments` with the same policy and seed.

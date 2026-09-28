# ADR 0005 — `ACCEPT` requires computed evidence, not merely "no error"

- **Status:** Accepted
- **Date:** 2026-09-29
- **Blocks:** Phase L (quality policy), Phase Q (release builder)
- **Evidence:** `docs/ANALYSIS.md` §6

## Context

The seed architecture is built on one sentence: **"Missing evidence is never converted into
PASS."** Two facts in the downstream contract put that sentence under pressure.

### 1. `ACCEPTED` does not imply a quality vector exists

`qualify_records` skips the quality stage entirely when no `AudioTensor` is supplied
(`qualification.py:531-556`): it records `quality.applied = False,
reason="audio_unavailable"`, leaves `QualifiedRecord.quality = None`, and the record is still
**`ACCEPTED`**. No warning, no status change.

Consequence: a dataset shipped with no decodable audio qualifies **clean** at the
`ornix-tts` level. The downstream contract cannot distinguish "measured and good" from
"never measured".

### 2. `QualityVector` has no slot for most of what the factory must measure

Confirmed absent by `search_code` over `^src/ornix/data/`:

```text
asr_cer  asr_wer  wer  cer  vad_speech_ratio  boundary  clip_evidence
```

`compute_quality_vector` (`quality.py:156-199`) populates only the 8 required scalars; all
**six** optional fields — `speech_probability`, `snr_db`, `reverb_score`, `music_probability`,
`asr_match`, `speaker_consistency` — are left `None`, and nothing anywhere in `ornix-tts`
ever assigns them. They are declared-but-unpopulated slots, evidently reserved for exactly
this producer.

`QualityVector.from_dict` (`:130-153`) reads only its 16 known keys and **silently drops
unknown ones**. Extending it requires a `QUALITY_VECTOR_REVISION` bump, which is hashed into
feature cache keys (`tests/unit/test_m1_3_semantic_infrastructure.py:177`).

The one legal home is `ManifestRecord.quality` — a free-form `Mapping[str, object]` with no
allow-list, validated only for JSON-compatibility and finite floats
(`manifest.py:198-199`, `_validate_json_value:57-76`).

But `qualification._report_for` (`:351-407`) only summarises `peak_abs`, `rms`, `dc_offset`,
`clip_fraction`, `low_energy_fraction` and `available_records` — so anything extra is
**invisible** in `QualificationReport`. The factory owns its own reporting surface.

## Decision

1. **`ACCEPT` requires a computed quality vector.** A record without one is `REVIEW`
   (evidence missing), never `ACCEPT`. Enforced in the factory, before the handoff, because
   the handoff will not enforce it.
2. The quality block written into `ManifestRecord.quality` has a **fixed, versioned shape**:

   ```json
   {
     "schema_version": 1,
     "revision": "ornix-quality-vector-v1",
     "duration_s": 4.713125,
     "peak_abs": 0.8123,
     "rms": 0.1402,
     "dc_offset": 0.0007,
     "clip_fraction": 0.0,
     "low_energy_fraction": 0.031,
     "channel_count": 1,
     "sample_rate": 48000,
     "speech_probability": 0.97,
     "snr_db": 31.4,
     "reverb_score": 0.08,
     "music_probability": 0.01,
     "asr_match": 0.98,
     "speaker_consistency": null,

     "ornix_ds_evidence": {
       "evidence_schema_version": 1,
       "evidence_revision": "ornix-ds-evidence-v1",
       "asr_cer": 0.02,
       "asr_wer": 0.06,
       "vad_speech_ratio": 0.97,
       "vad_leading_silence_s": 0.12,
       "vad_trailing_silence_s": 0.09,
       "effective_bandwidth_hz": 7800.0,
       "boundary_status": "OK",
       "head_clip_probability": 0.01,
       "tail_clip_probability": 0.02,
       "providers": {
         "vad":  {"provider_id": "silero", "model_id": "...", "model_revision": "...",
                  "weights_sha256": "...", "runtime": "onnxruntime-cpu",
                  "device": "cpu", "status": "OK"},
         "asr":  {"...": "...", "status": "OK"},
         "speaker": {"status": "UNAVAILABLE"}
       }
     }
   }
   ```

   The top level is exactly `QualityVector.to_dict()` — so an `ornix-tts` consumer can
   reconstruct a `QualityVector` with `QualityVector.from_dict()` unchanged. All
   factory-specific evidence lives under `ornix_ds_evidence`, versioned separately.
3. **The six `QualityVector` optional slots are the factory's to fill.** They are declared and
   never populated upstream; populating them is not schema drift, it is the intended contract
   use.
4. **A metric that could not be measured is `null`, and its provider carries
   `status: UNAVAILABLE`.** It is never `0.0`, never omitted, never the mean of the
   population. The legacy repo already proves this property is worth keeping —
   `tests/unit/test_detectors.py:25-28` `test_dnsmos_returns_unknown_not_zero`.
5. **Every gate declares its evidence producer and is unreachable-when-unprovisioned = a
   defect.** A gate whose provider is stubbed out fails the build; it does not report `PASS`.
   (See ADR 0004 §6, the `transcript_match_status` dead-code pattern.)
6. Acceptance is **vector-based**. Forbidden:

   ```json
   { "quality": 0.91 }
   ```

   A single scalar cannot represent *"clean speech, clean transcript, but 40 % music"*.
7. The factory emits its **own** quality report (`reports/quality.json`) because
   `QualificationReport` will not surface `ornix_ds_evidence`.

## Consequences

**Positive**

- "Measured and good" becomes distinguishable from "never measured", at last.
- An `ornix-tts` consumer can `QualityVector.from_dict(record.quality)` today, and the extra
  block is additive and ignorable — forward-compatible on both sides.
- Detector outages degrade yield into `REVIEW` and are visible in the release metadata,
  instead of silently shrinking the corpus.
- The `null` vs `0.0` distinction is machine-checkable.

**Negative**

- A stricter `ACCEPT` definition means lower yield, and early campaigns will produce large
  `REVIEW` queues. This is the intended trade.
- Every evidence block carries provider metadata, so manifest rows grow. Budget accordingly
  and keep `ornix_ds_evidence` out of the `content_hash` inputs where it would cause
  instability — see below.
- The factory needs a second reporting surface, duplicating some `QualificationReport` work.

**Becomes impossible**

- A release where a detector outage is indistinguishable from a clean result.
- A scalar "quality score" as an acceptance criterion.

## Alternatives rejected

1. **Extend `QualityVector` with new fields.** Rejected: requires a `QUALITY_VECTOR_REVISION`
   bump, invalidates feature cache keys, and redefines a contract `ornix-Ds` must not own.
2. **Add evidence to `Provenance.transformations`.** Rejected: it is a `tuple[str, ...]` of
   human-readable operation names, not structured data.
3. **Accept `ACCEPTED`-with-`quality=None` from downstream as sufficient.** Rejected: it is
   exactly the "missing evidence becomes PASS" failure the spec forbids.
4. **Store evidence in a sidecar file keyed by record id.** Rejected: it breaks the
   single-record self-containment of `manifest.jsonl`, and requires a join at consumption
   time — reintroducing the normalization project the spec forbids.

## Verification

```python
def test_accept_requires_quality_vector(run):
    for row in run.accepted_rows:
        assert row.quality is not None
        assert row.quality["ornix_ds_evidence"] is not None

def test_unmeasured_metric_is_null_never_zero(run):
    e = run.accepted_rows[0].quality["ornix_ds_evidence"]
    for k, v in e.items():
        if v is None:
            assert run.provider_status_for(k) in {"UNAVAILABLE", "NOT_APPLICABLE", "ERROR"}

def test_quality_is_consumable_by_downstream(release):
    for r in release.records:
        QualityVector.from_dict(r.quality)   # must not raise

def test_detector_outage_yields_review_not_accept(...):
    ...
def test_no_scalar_quality_field_exists(release):
    assert "quality" not in r.quality      # the forbidden {"quality": 0.91} shape
```

Compatibility suite: `QualityVector.from_dict(record.quality)` must succeed for every released
record, and the factory's `ornix_ds_evidence` must survive a `ManifestRecord`
serialize/deserialize round-trip unchanged.

# ADR 0001 — Release audio at 48 kHz, enforced by the factory

- **Status:** Accepted
- **Date:** 2026-09-29
- **Blocks:** Phase Q (release builder), Phase F (views)
- **Supersedes:** nothing
- **Evidence:** `docs/ANALYSIS.md` §5

## Context

The seed architecture retires `canonical sample rate = 24 kHz` and names three views
(`master/native`, `48 kHz Audio-VAE`, `16 kHz SSL/VAD/ASR`). The downstream contract was
checked at source:

- 48 kHz is the Audio-VAE training rate: `Ornix-TTS/configs/train/audio_vae.yaml:3`
  `sample_rate: 48000`.
- 48 kHz is the serving output rate: `configs/serving/realtime.yaml:12`
  `output_sample_rate: 48000`; inputs accepted are `[16000, 48000]`.
- `ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ = 48_000` exists (`contracts/core.py:32`) but has
  **zero consumers** — `search_code` over `^src/` returns only the definition, the
  re-export, and the `__all__` entry.
- `ManifestRecord.__post_init__` calls `validate_sample_rate(self.sample_rate)` with **no
  `expected`** (`manifest.py:181` → `contracts/validation.py:170-183`). `AudioTensor` and
  `QualityVector` do the same.
- `24000` and `44100` appear **zero times** in `src/`, `tests/`, `configs/`, `data/`, `docs/`.
  Every `Ornix-TTS` data test fixture uses 16 kHz manifests and passes.

So the 24 kHz obsolescence claim is confirmed and total — but so is the fact that **no rate
is enforced anywhere in the downstream contract**.

## Decision

1. The release artifact is a **48 kHz** dataset. `ManifestRecord.sample_rate == 48000` for
   every released record, and the referenced `audio_uri` resolves to 48 kHz audio.
2. The factory **reads** `ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ`; it never hard-codes
   `48000` in Python. If upstream changes the constant, the factory follows automatically.
3. The factory **asserts** the rate itself, in its own acceptance tests, because upstream
   will not. `record.sample_rate == ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ`.
4. The native-rate **master** is a workspace artifact, not a release artifact. It is
   re-derivable from immutable raw bytes plus the resample config hash. Audio is stored once
   (§30 of the spec), so the release carries the 48 kHz view and nothing else.
5. The 16 kHz analysis view is **internal**. It is never shipped and never referenced by a
   `ManifestRecord`.
6. **Bandwidth is evidence, not a label.** A low-bandwidth source is never admitted
   *because its output would say 48,000 Hz*. `effective_bandwidth_hz` is measured on the
   master and travels in the quality vector. Where policy sets a floor, a source below it is
   `REJECT` on bandwidth evidence — not silently upsampled and relabelled.

## Consequences

**Positive**

- A release is directly trainable without a resample step, and cache keys computed from it
  are reusable.
- The release is small: one audio copy, one rate.
- The honest-admission principle already present in the legacy config
  (`configs/audio_profile.yaml:21-23`: *"a file is never admitted merely because its output
  would say 24,000 Hz"*) is preserved and generalised.

**Negative**

- Sources narrower than 24 kHz usable bandwidth cannot produce a legitimate 48 kHz release
  row. They are rejected or sent to `REVIEW` with the measurement attached. This is the
  intended behaviour, and it will reduce yield relative to the legacy pipeline.
- Storage of the native master is a workspace cost, not a release cost. A worker that deletes
  the workspace without having verified the release loses the ability to re-derive views —
  which is why cleanup is gated on remote verification (spec §31).

**Becomes impossible**

- Shipping a release that silently trains at the wrong rate. The mismatch would otherwise
  surface inside the model, far from its cause.

## Alternatives rejected

1. **Ship at native rate and let `ornix-tts` resample.** Rejected: `ornix-tts` will not
   resample inside the manifest — `validate_audio_metadata_consistency` requires
   `record.sample_rate == audio.sample_rate` (`validation.py:66`). Every consumer would need
   its own resample step, which is precisely the "second metadata-normalization project"
   the spec forbids.
2. **Ship 16 kHz, matching existing `ornix-tts` test fixtures.** Rejected: those fixtures
   test the manifest schema, not the training rate. 16 kHz is the SSL working rate;
   `configs/train/audio_vae.yaml:3` is the training rate.
3. **Ship both native and 48 kHz in the release.** Rejected: spec §30 — *"Audio is stored
   once."*
4. **Hard-code `48000` as a factory constant.** Rejected: it duplicates a decision upstream
   already expresses, and would drift silently.

## Verification

```python
# tests/acceptance/test_release_rate.py
def test_release_rate_matches_downstream_constant(release):
    for record in release.records:
        assert record.sample_rate == ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ
```

Plus: the compatibility suite runs `Ornix-TTS/tests/unit/test_m1_2_qualification.py`
unmodified against factory output, and a negative test asserts that a 44.1 kHz record is
rejected **by the factory** (proving the factory, not upstream, is the enforcement point).

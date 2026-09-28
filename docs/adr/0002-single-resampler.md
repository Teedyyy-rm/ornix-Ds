# ADR 0002 — One resampler: call `ornix.audio`, never reimplement

- **Status:** Accepted
- **Date:** 2026-09-29
- **Blocks:** Phase F (deterministic resampling)
- **Evidence:** `docs/ANALYSIS.md` §2

## Context

The seed architecture §6 says:

```text
Use scipy.signal.resample_poly
Project resampling must be versioned
Example identity: ornix-resample-polyphase-kaiser5-v1
```

`Ornix-TTS` already ships exactly this:

- `RESAMPLER_VERSION = "scipy-resample-poly-kaiser5-v1"` — `src/ornix/audio/resample.py:18`
- `DeterministicResampler` calls `scipy.signal.resample_poly` with `window=("kaiser", 5.0)`
  and an explicit integer half-up length rule — `audio/resample.py:40-44`:

  ```python
  def _target_length(input_length, input_rate, output_rate):
      return (input_length * output_rate + input_rate // 2) // input_rate
  ```

- `resample_audio(audio, target_sample_rate)` takes the rate as an argument; no default.
- The version string is **hashed into feature cache keys**
  (`tests/unit/test_m1_3_semantic_infrastructure.py:177`).

The legacy repo did the opposite and shows exactly how this goes wrong: it implements
`resample_poly_quality` at `dsp/resample.py:18-38` **and** copies it verbatim to
`detectors/music_noise.py:159-171`, with `detectors/vad.py:145` importing the *private*
function across modules. It also **silently degrades to `np.interp`** when scipy is absent,
returning `method="linear-degraded"`; the fail-closed gate only exists downstream in
`dsp/render.py:123-127`.

## Decision

1. **`ornix-Ds` implements no resampler.** Views are produced by
   `ornix.audio.resample_audio` / `DeterministicResampler`.
2. The factory's resampling identity in provenance is **`RESAMPLER_VERSION` read from
   `ornix.audio`** — never a locally invented string. The seed spec's
   `ornix-resample-polyphase-kaiser5-v1` is **rejected**.
3. Every resampled artifact records the full recipe: `source_sample_rate`,
   `target_sample_rate`, `up`, `down`, `window`, and
   `implementation_revision == ornix.audio.RESAMPLER_VERSION`.
4. **Resampling is a transformation, never part of decode.** A decoder that resamples
   implicitly is a contract violation.
5. If a future need appears for resampling that `ornix.audio` cannot serve, the addition goes
   **upstream into `ornix-tts`**, not into a parallel local implementation.
6. The "never silently degrade" property is preserved structurally: because the factory
   calls one versioned implementation, there is no second code path that can quietly fall back
   to linear interpolation.

## Consequences

**Positive**

- One algorithm, one version string, one cache-key namespace.
- The half-up length rule is inherited, not re-derived.
- Removes the legacy repo's most dangerous pattern (a resampler that silently degrades).
- The factory gains a `scipy` dependency it did not need to pin.

**Negative**

- `ornix-Ds` now has a hard runtime dependency on `ornix-tts`. This is already true for
  `ManifestRecord` and is accepted (ADR 0003's compatibility invariant), so it costs nothing
  new.
- If `ornix-tts` ever changes `RESAMPLER_VERSION`, previously built views are no longer
  byte-reproducible. This is **correct** — it is what version pinning is for — and the
  provenance records the version that produced each artifact.

**Becomes impossible**

- A factory artifact whose resample provenance names a version that no code implements.

## Alternatives rejected

1. **Implement a local `scipy.signal.resample_poly` wrapper under a new version id.**
   Rejected: two names for one algorithm, divergent cache keys, direct violation of the
   spec's own §0 rule against incompatible local contracts.
2. **Copy `DeterministicResampler` into the factory "to avoid a dependency".** Rejected: the
   dependency already exists for the manifest contract; the copy would be the exact drift
   this ADR exists to prevent.
3. **Use `np.interp`/linear interpolation for speed.** Rejected outright — no anti-aliasing,
   and it produced the legacy `linear-degraded` failure mode.

## Verification

```python
def test_view_provenance_names_the_downstream_resampler(artifact):
    assert artifact.resample["implementation_revision"] == ornix.audio.RESAMPLER_VERSION

def test_no_local_resample_poly_call_exists():
    # static check: audio/views.py must not import scipy.signal.resample_poly
    ...
```

Plus a determinism test: two independent runs of the same source at the same revision
produce byte-identical views, and `tests/compatibility/` asserts the factory's view length
matches `ornix.audio._target_length` for the full rate table.

# ADR 0008 — No repair, no fabrication, no hidden defaults

- **Status:** Accepted
- **Date:** 2026-09-29
- **Blocks:** every phase
- **Evidence:** `docs/ANALYSIS.md` throughout; spec §0, §14, §37

## Context

This ADR consolidates the project's core safety rules into one place, because they are
load-bearing, they are easy to erode under refactor pressure, and every one of them has a
documented precedent of being violated in the predecessor repository.

The rules are stated in spec §0 and §37, but §0 states them as principles and §37 as
prohibitions. Neither is executable. Violations do not raise — they produce a
reproducible-looking release that is silently wrong, which is the exact failure mode this
project exists to prevent.

Precedents from `~/projects/ornix-dataset`:

| Rule | How the legacy repo violated it |
|---|---|
| No silent degradation | `dsp/resample.py:18-38` returns `method="linear-degraded"` via `np.interp` when scipy is absent; the fail-closed gate exists only downstream at `dsp/render.py:123-127` |
| No unmeasured metric as zero | `curation/transcript.py:40-52` `transcript_match_status` has 0 callers, so `policy._transcript` can only return `PASS`/`UNKNOWN`, never a mismatch |
| Provider revisions must be real | `AdapterInfo.model_revision` is populated **only** by `EnergyVadAdapter` (`detectors/vad.py:44-46`, hardcoded `"0.1.0"`); no ML adapter ever sets it |
| No silent defaults on audio metadata | `dsp/decode.py:102` — `sr = info.get("sample_rate") or 24000` invents a 24 kHz rate when ffprobe omits one |
| No duplicated algorithm | `detectors/music_noise.py:159-171` duplicates `dsp/resample.py:18-38`; `detectors/vad.py:145` imports the *private* copy across modules |

And from `Ornix-TTS` itself, the reason the rules exist:

- `qualify_records` returns **`ACCEPTED` with `quality=None`** when no `AudioTensor` is
  supplied (`qualification.py:531-556`) — a downstream "measure nothing → pass" path.
- `DedupFingerprint.__post_init__` validates hashes but **discards the normalised value**
  (`dedup.py:30-35,53-60`), so uppercase hex silently fails to group.

## Decision

### 8.1 No fabrication

1. Missing evidence is `null` + a provider `status` of `UNAVAILABLE` / `ERROR` /
   `NOT_APPLICABLE`. **Never `0.0`.** Never the population mean. Never omitted.
2. A detector that cannot run **fails the gate**, it does not pass it. A required detector
   that is unavailable yields `REVIEW` (§11 of the spec), not `ACCEPT` and not `REJECT`.
3. **A gate that cannot fail is a defect.** Every policy gate names its evidence producer;
   a test proves the producer is reachable. (ADR 0004 §6.)
4. `PENDING` and `REVIEW` never cross the Ornix-TTS boundary (ADR 0003).

### 8.2 No guessing

5. Language is never inferred from a filename, a path, or a heuristic without recorded
   evidence. Unrecorded ⇒ unknown ⇒ not `ACCEPT`.
6. Rights are never inferred. Unknown license or consent ⇒ `BLOCKED` — unless an explicit,
   separately-recorded research-only policy says otherwise.
7. Speaker identity is never guessed from a name. `UNKNOWN` or a stable sample-local id
   (spec §28).
8. `sample_rate` is never defaulted. If ffprobe omits it, that is a decode failure — the
   legacy `or 24000` at `dsp/decode.py:102` is the canonical example of the anti-pattern.
9. Optional providers may not silently become required gates (spec §3). A gate's requirement
   is declared in policy, never inferred from provider availability.

### 8.3 No hidden repair

10. `text_raw` is byte-identical to the source. ASR verifies; it never authors.
11. No denoising, no dereverberation, no noise suppression, no spectral gating, no
    loudness normalisation, no peak normalisation, on any path. The legacy repo happens to
    have none of these — that property is preserved deliberately.
12. A low-bandwidth source is never upsampled and relabelled high quality. Bandwidth is
    measured and reported (ADR 0001 §6).
13. A decoder never implicitly resamples, downmixes, or trims. Every such operation is
    explicit, requested, and written to provenance.
14. Near-duplicate detection produces **evidence first**; it never silently deletes examples
    (spec §16).

### 8.4 No hidden defaults

15. Every versioned config is strict: `extra="forbid"`, unknown fields fail. Silent
    acceptance of a misspelled key is a class of bug this project cannot afford.
16. Source revisions are pinned. `revision: main` is **not** a reproducible source revision
    and is rejected for production campaigns (spec §8).
17. Model revisions are pinned in `configs/models.lock.yaml`. No runtime "download latest".
18. Operators never auto-pick a quality threshold. Thresholds are bound by calibration or
    left unset — preserved from `curation/policy.py:45-48` in the legacy repo, which is a
    strong safety property worth carrying over verbatim.
19. Every measurement states **which view it was measured on** (source / master / 16 k / 48 k
    / segment), per spec §13.

### 8.5 No schema drift

20. No second `ManifestRecord`. Every record is built through `ornix.data.ManifestRecord`
    and `ornix.data.Provenance` (spec §25).
21. No second resampler (ADR 0002). No second window segmenter (ADR 0006). No second
    `DedupFingerprint` construction path.
22. Release build **fails** when compatibility validation is unavailable. No silent fallback
    to a local look-alike.
23. Local artifacts are never deleted before remote verification (spec §31).

## Consequences

**Positive**

- Every release decision is traceable to recorded evidence, and every refusal is auditable.
- A detector outage is visible as reduced yield, not as a quietly better-looking corpus.
- Compatibility with `Ornix-TTS` is structural rather than aspirational.
- These become testable, and are enumerated as such in `docs/TESTING.md`.

**Negative**

- Yield will be lower than a permissive pipeline, and campaigns will be slower because
  unavailable evidence stops rows instead of passing them.
- Strict configs mean version bumps are required for any field addition — deliberate friction.
- Several rules are conventions enforced by lint and static tests rather than by the type
  system. That is a real maintenance cost, accepted.

**Becomes impossible**

- A release whose quality vector contains a `0.0` standing in for an unmeasured metric.
- A `REJECT` reason that cannot be reconstructed from stored evidence.
- Passing CI while claiming release compatibility that was never tested.

## Alternatives rejected

1. **Treat the rules as documentation only.** Rejected: the legacy repo shows the failure mode
   concretely — gates that look present, cannot fail, and are reported as passing.
2. **Enforce some rules only in CI.** Rejected: a rule that exists only in CI is not a
   contract; it is a suggestion that survives until someone disables a workflow.
3. **Allow a "permissive research" mode that guesses unknown fields.** Rejected: the escape
   hatch that exists (§23, research-only rights policy) must be explicit, configured and
   recorded — never a default.

## Verification

Each clause maps to a test in `docs/TESTING.md`. The blocking subset:

```python
def test_unavailable_detector_never_becomes_pass(...)
def test_missing_metric_is_null_never_zero(...)
def test_unknown_license_is_blocked(...)
def test_unknown_language_is_not_guessed(...)
def test_unknown_sample_rate_is_a_decode_failure(...)      # not `or 24000`
def test_text_raw_is_byte_identical_to_source(...)
def test_no_normalisation_or_denoise_on_any_path(...)      # static + signal-identity
def test_main_revision_is_rejected_for_production(...)
def test_unknown_config_field_is_rejected(...)
def test_release_build_fails_without_compatibility_check(...)
def test_cleanup_requires_remote_verification(...)
```

Static checks that back the structural claims:

```python
def test_no_local_manifest_record_definition(): ...        # no dataclass mirroring it
def test_no_local_resample_implementation(): ...           # ADR 0002
def test_no_local_window_segmentation(): ...               # ADR 0006
def test_no_sequential_id_allocation(): ...                # ADR 0007
def test_no_use_record_text_true(): ...                    # ADR 0004
```

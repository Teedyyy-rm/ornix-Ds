# Analysis — Ornix-Ds pre-implementation audit

> **Status:** normative. This document records the evidence that `docs/ARCHITECTURE.md`
> and `docs/ROADMAP.md` are built on. If the analysis and the architecture disagree,
> the analysis wins until an ADR is amended.
>
> **Audit date:** 2026-09-29
> **Evidence tier:** Auditor (full graph index of both repos + direct source reads)
> **Downstream:** `Teedyyy-rm/Ornix-TTS` @ `5da288c` (branch `main`)
> **Legacy predecessor:** `~/projects/ornix-dataset` @ `main` (95 files, ~11,421 LOC)

---

## 0. Why this document exists

The architecture specification that seeds this repository is internally consistent as a
*statement of intent*, but it was written before the downstream contract was read at
source. Reading `Ornix-TTS/src/ornix/data/**` and the legacy `ornix-dataset` implementation
surfaces **nine points where the specification is either wrong, unimplementable as written,
or in direct conflict with the code it must interoperate with**.

None of them are cosmetic. Six require a decision before the first line of pipeline code
is written. Those decisions are captured here and ratified in `docs/adr/`.

---

## 1. Downstream reality check — what `Ornix-TTS` actually guarantees

The spec's central claim — *"Ornix-TTS contracts are authoritative"* — is **correct and
load-bearing**. Confirmed at source:

| Guarantee | Evidence | Consequence for `ornix-Ds` |
|---|---|---|
| `ManifestRecord` is a frozen dataclass with 17 validated fields, `MANIFEST_SCHEMA_VERSION = 1` | `src/ornix/data/manifest.py:17,156-301` | Never redefine. Import it. |
| `Provenance` requires 4 text fields; `transformations` must be a `tuple` when constructed | `manifest.py:97-152` | Build `Provenance` with a tuple, not a list. |
| `canonical_json` = `sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False` | `data/hashing.py:16-28` | Vietnamese text is safe; `NaN` raises. |
| `ManifestRecord.quality` is a **free-form `Mapping[str, object]`** with no allow-list | `manifest.py:198-199` + `_validate_json_value:57-76` | Extra evidence (CER, boundary, VAD ratio) has a legal home. |
| `ManifestRecord.hashes` values must **all** be 64-char SHA-256 hex | `manifest.py:203-207` | No "other metadata" escape hatch — extra facts go in `quality`. |
| Rights fail-closed on exactly 5 unknown tokens per field | `data/validation.py:15-16` | `UNKNOWN_LICENSE_VALUES`, `UNKNOWN_CONSENT_VALUES`. |
| `validate_sample_rate(x)` is called **without** `expected` | `manifest.py:181` → `contracts/validation.py:170-183` | **No sample rate is enforced anywhere in `ornix.data`.** |
| `WAVEFORM_SAMPLE_RATE_HZ = 48_000` exists but has **zero consumers** | `contracts/core.py:32`; `search_code` → 3 hits, all definition/re-export | 48 kHz is policy, not contract. `ornix-Ds` must enforce it itself. |
| Canonical training rate is 48 kHz | `configs/train/audio_vae.yaml:3` `sample_rate: 48000`; `configs/serving/realtime.yaml:12` `output_sample_rate: 48000` | Release audio at 48 kHz. |
| `24000` / `44100` appear **zero times** in `src/`, `tests/`, `configs/`, `data/`, `docs/` | `search_code` `24000\|24_000\|22050\|22_050\|44100\|44_100` → 1 file, 2 hits (`22_050` test param) | The 24 kHz obsolescence claim in the spec is **confirmed** and total. |
| `ornix-tts` pip package, import name `ornix`, Python `>=3.11` (required by `StrEnum`) | `pyproject.toml:5-19` | Compatibility test env constraint. |

**Conclusion 1.** The spec's §0 obsolescence list is factually correct. 24 kHz, the
six-field schema, AudioFolder-as-contract and sequential `Ornix_<n>` identity are all dead
upstream — the last two never existed downstream at all, only in the legacy repo.

---

## 2. Conflict C-1 — the resampler would be implemented twice under two names

**Severity: high. Decision required before Phase F.**

The spec (§6) says:

```text
Use scipy.signal.resample_poly
Project resampling must be versioned
Example identity: ornix-resample-polyphase-kaiser5-v1
```

`Ornix-TTS` already ships exactly this, already versioned, already with the hard parts:

- `RESAMPLER_VERSION = "scipy-resample-poly-kaiser5-v1"` — `src/ornix/audio/resample.py:18`
- `DeterministicResampler` uses `scipy.signal.resample_poly` with `window=("kaiser", 5.0)`
  and explicit integer half-up length rounding — `audio/resample.py:40-44,52-113`:

  ```python
  def _target_length(input_length, input_rate, output_rate):
      return (input_length * output_rate + input_rate // 2) // input_rate
  ```

- The version string is **hashed into feature cache keys**
  (`tests/unit/test_m1_3_semantic_infrastructure.py:177`).

So the spec would create a second resampler, with a **different version string for the same
algorithm**. Consequences:

1. It violates the spec's own §0 rule (*"MUST NOT invent an incompatible contract"*).
2. Cache keys computed by `ornix-Ds` become non-reusable by `Ornix-TTS`.
3. The half-up rounding rule is a hard-won detail; reimplementing it invites drift.
4. `ornix-Ds` would silently acquire a `scipy` dependency that `ornix-tts` already pins.

**Resolution → `docs/adr/0002-single-resampler.md`.** The data factory **calls**
`ornix.audio.resample_audio` / `DeterministicResampler`. It implements no resampler.

---

## 3. Conflict C-2 — two decision enums, and the factory owns two states nobody else does

**Severity: high. Decision required before Phase A.**

The spec (§22) mandates six states:

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

`PENDING` and `REVIEW` **do not exist anywhere** in `ornix.data` — not in the enum, not in
`__init__.py`, not in the 82-name `__all__`. The full mapping:

| Factory state | `QualificationStatus` | Mechanism | Notes |
|---|---|---|---|
| `PENDING` | *none* | — | `qualify_records` is synchronous and total: every input ends in one of the four. A `PENDING` record is one that has not been run. Represent it as **absence from the result**, or as a factory-only state. |
| `ACCEPT` | `ACCEPTED` | default; survives all stages | Downstream attaches `split`. `quality` **may be `None`** if no audio was supplied — see §6. |
| `REVIEW` | *none* | — | No human-in-the-loop lane exists downstream. `QualificationConfig.require_known_rights=False` is the closest affordance and it resolves to `ACCEPTED`, **not** to a review state. **The factory must own this state entirely.** |
| `REJECT` | `REJECTED` | set at `qualification.py:455/482/506/525` | `failure_reasons` always populated, prefixed `NORMALIZATION_ERROR:` / `SEGMENTATION_ERROR:` / `QUALITY_ERROR:` / `HASH_ERROR:` + exception class name. |
| `BLOCKED` | `BLOCKED` | `qualification.py:470` | **Rights only.** `("RIGHTS_BLOCKED:{ExcType}",)`. |
| `DUPLICATE` | `DUPLICATE` | `qualification.py:653` | Applied only to records that were **already** `ACCEPTED` and are non-canonical. A `BLOCKED`/`REJECTED` record is never relabelled `DUPLICATE`. |

**Why this matters beyond bookkeeping.** The spec's acceptance criterion *"Unavailable
required detectors lead to REVIEW"* is **incompatible with shipping through
`qualify_records`**: there is no downstream lane for it, so a `REVIEW` record must never
reach a release. This strengthens — it does not weaken — the rule that only `ACCEPT`
enters a release.

**Resolution → `docs/adr/0003-decision-state-mapping.md`.** The factory enum is a superset;
`ACCEPT` is the only state that crosses the boundary; a documented projection function
`to_ornix_status()` maps the rest, and it must **raise** on `PENDING`/`REVIEW` rather than
guess.

---

## 4. Conflict C-3 — `protect_normalized_text` silently no-ops under the required text policy

**Severity: high. Silent failure. Decision required before Phase M.**

The spec (§24) correctly mandates that the factory ships `"text_normalized": null` because
spoken normalization belongs to `Ornix-TTS`. Verified as correct: `qualify_records` runs its
own `BaselineSpokenTextNormalizer` over `text_raw` and stores the result in
`QualifiedRecord.normalization` — it never mutates `record.text_normalized`
(`qualification.py:587-598`).

But `DedupFingerprint.from_record` defaults to `use_record_text=True`
(`dedup.py:71`), which selects `record.text_normalized` (`dedup.py:87`). With
`text_normalized=None`:

1. `normalized_text_hash` is `None` — `dedup.py:88`.
2. `_group_ids` skips `None` values — `dedup.py:214-224`, so the record joins **no text group**.
3. `assign_splits` guards on `is not None` — `split.py:213-215`:
   ```python
   if selected_policy.protect_normalized_text and fingerprint is not None:
       if fingerprint.normalized_text_hash is not None:
           grouped[f"text:{fingerprint.normalized_text_hash}"].append(record.id)
   ```
4. `validate_no_train_eval_leakage` does the same — `split.py:258-262`.

**Result: `protect_normalized_text=True` provides exactly zero protection, with no warning
and no error.** A dataset could ship thousands of text-duplicate segments leaking into both
train and test while reporting `LeakageReport.ok == True`.

Note `SplitPolicy.protect_normalized_text` defaults to `False` (`split.py:35`) and
`QualificationConfig.deduplicate_text` defaults to `False` (`qualification.py:106`) — the
upstream defaults are safe. The danger is entirely on the factory side, if the factory
passes `use_record_text=True` (the default) and forgets.

**Resolution → `docs/adr/0004-text-normalization-ownership.md`.** The factory must construct
every fingerprint as `from_record(record, audio=..., raw_audio_bytes=..., normalized_text=<comparison-normalized>, use_record_text=False)` — the same call shape `qualify_records` uses — and it must own a **comparison-normalization namespace** that is explicitly *not* canonical transcript storage (§10 spec).

---

## 5. Conflict C-4 — sample rate is unenforced upstream, and the spec offers no fallback

**Severity: medium. Policy gap, not a conflict.**

The spec retires 24 kHz and (§6) names three views: `master/native`, `48 kHz Audio-VAE`,
`16 kHz SSL/VAD/ASR`. That is **correct** and matches upstream exactly:

- 48 kHz is the Audio-VAE training rate — `configs/train/audio_vae.yaml:3`.
- 16 kHz is the SSL/manifest fixture rate — `tests/unit/test_m1_data_pipeline.py:44,197`,
  `tests/unit/test_m1_2_qualification.py:60,87`.
- Serving accepts `[16000, 48000]` in, emits `48000` — `configs/serving/realtime.yaml:11-12`.

But **nothing enforces any of it**: `ManifestRecord`, `AudioTensor` and `QualityVector` all
call `validate_sample_rate` without `expected`. Every existing `Ornix-TTS` data test fixture
uses 16 kHz manifests and passes. A factory that shipped 44.1 kHz manifests would be
accepted by every `ornix.data` API and would fail later, inside the model.

**Resolution → `docs/adr/0001-release-audio-at-48khz.md`.** The factory enforces the rate
itself, reads `ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ` rather than hard-coding `48000`, and
asserts it in its own acceptance tests.

---

## 6. Gap G-1 — `ACCEPTED` does not imply a quality vector exists

**Severity: high. Silent quality hole. Decision required before Phase L.**

`qualify_records` skips the quality stage when no `AudioTensor` is supplied
(`qualification.py:531-556`): it records `quality.applied = False, reason="audio_unavailable"`
and the record is still **`ACCEPTED`**.

This directly collides with the spec's core rule *"Missing evidence is never converted into
PASS"*. A dataset with no audio attached would qualify clean at `Ornix-TTS` level. The
factory's guarantee therefore has to be enforced **before** the handoff, not after: a
factory `ACCEPT` must require a computed quality vector, and the release builder must refuse
any record whose `quality` block is absent.

**Resolution → folded into `docs/adr/0005-accept-requires-evidence.md`.**

---

## 7. Gap G-2 — `validate_audio_metadata_consistency` compares against the longest item in the batch

**Severity: medium. API misuse trap.**

`validation.py:70-72`:

```python
lengths = cast(np.ndarray[Any, Any], audio.lengths)
expected_duration = float(np.max(lengths)) / float(audio.sample_rate)
if abs(record.duration_s - expected_duration) * audio.sample_rate > tolerance_samples:
    raise ManifestValidationError("manifest and decoded durations differ")
```

`np.max(lengths)`, not `lengths[item_index]`, and there is no `item_index` parameter (unlike
`compute_quality_vector` and `_audio_content_hash`, which both take `item_index: int = 0`).
With `B == 1` the behaviour is correct. With `B > 1` and unequal lengths, **every** record in
the batch is compared against the longest item. `tests/conftest.py:24` deliberately uses an
unequal-length batch (`lengths=[8, 5]` at 48 kHz), so this is a live convention, not a
theoretical concern.

The default tolerance is `tolerance_samples=0.5`, i.e. **half a sample** — a duration
mismatch of under ~10 µs at 48 kHz is accepted. Rounding the manifest duration to 6 decimal
places is safe at 48 kHz (1 µs resolution) but the factory must state the rounding rule
explicitly rather than discover it.

**Resolution → OPERATIONS.md runbook; the factory always calls this with `B == 1`.**

---

## 8. Gap G-3 — the release artifact cannot be read back without a project nobody planned

**Severity: high. Directly contradicts the §1 acceptance goal.**

The spec's goal is a release *"consumable by Ornix-TTS without another metadata-normalization
project"*. But `ornix.data` ships **no manifest file loader**: there is no `load_manifest`,
no JSONL reader, no `iter_*`. Verified by `search_code` over `^src/ornix/data/` for
`^def load_\|^def read_\|^def iter_\|jsonlines\|jsonl` → only `load_registry` and
`load_mixture`. `ManifestRecord.from_json` (`manifest.py:291-301`) is single-record, and
`from_json` additionally rejects bare `NaN`/`Infinity` literals via `parse_constant`.

So the factory must ship both sides: `manifest.jsonl` **and** a reader that yields
`ManifestRecord` objects, or the §1 goal fails on day one.

**Resolution → ROADMAP Phase Q; `ornix/loader.py` is a first-class deliverable, and its
round-trip test is a compatibility gate.**

---

## 9. Gap G-4 — the registry is not a required integration point (good news, bad timing)

**Severity: low today, medium later.**

`ornix.data.registry` looks like the registration hook but is not:

1. Nothing in `ornix.data` reads the registry — `registry.py` imports only `errors`,
   `hashing`, `validation`, `ornix.config`.
2. `load_registry` has exactly **one** in-repo caller, and it is a test
   (`tests/unit/test_m1_data_pipeline.py:327`).
3. Nothing outside `src/ornix/data/**` imports any `ornix.data` module except two test files.
   There is no trainer, sampler, dataloader or model in the repo.
4. `data/registry.yaml` ships `datasets: []` and `test_empty_registry_valid` **pins the
   empty state**.
5. The only link between registry and manifest is the opaque string `manifest_uri`, which
   nothing resolves or checksum-verifies.

**Resolution → the factory emits `release/dataset.json` shaped to be convertible into a
`DatasetEntry` (`id`, `version`, `status`, `source_url`, `manifest_uri`, `languages`,
`license`, `consent_scope`, `revision`, `checksum`) from day one, but does not block the
release on registration.**

---

## 10. Conflict C-5 — segmentation is specified in two places

**Severity: medium.**

The spec's repository layout puts `curation/segmentation.py` in the factory. `Ornix-TTS`
already owns a deterministic, seeded window segmenter and **wires it into
`qualify_records`** (`qualification.py:497-526`):

- `WindowSegmentationPolicy` — `window_s=10.0`, `stride_s=None`, `max_segments=None`,
  `jitter_s=0.0`, `revision="ornix-window-segmentation-v1"` — `segmentation.py:155-181`
- `seeded_window_segments(...)` — `segmentation.py:204-270`, deterministic via
  `sha256(canonical_json({...}))[:8] / 2**64`, no RNG object, no global state
- `segment_id_for(...)` — `seg-<sha256(canonical_json({source_record_id, start_s, end_s,
  segmentation_revision, seed}))>` — `segmentation.py:51-76`
- `SEGMENTATION_REVISION = "ornix-window-segmentation-v1"` — `segmentation.py:14`

Its `revision` is hashed into `QualificationConfig.identity()` (`qualification.py:139-146`),
so changing it changes `QualificationReport.content_hash()`, and `segment_id` is
content-addressed — a different policy produces different segment IDs and breaks downstream
joins.

**But** the one thing `Ornix-TTS` does **not** own is speech-boundary detection:
`VADProvider` (`segmentation.py:184-189`) is a declared-but-**unimplemented** protocol, and
`seeded_window_segments` neither accepts nor calls it. The spec's §15 boundary-integrity
detector is genuinely factory work.

**Resolution → `docs/adr/0006-segmentation-ownership.md`.** The factory owns
*utterance boundary detection* (VAD + edge + alignment evidence) and emits a canonical
master record. It does **not** reimplement `seeded_window_segments`; it calls it. Two levels,
two owners, no collision.

---

## 11. Gap G-5 — near-duplicate detection does not exist downstream

**Severity: high relative to the spec.**

`deduplicate_records` is exact-only, by docstring (`dedup.py:231`) and implementation — union
over `audio_content_hash`, `raw_audio_bytes_hash`, `source_item_hash`, and optionally
`normalized_text_hash` (`dedup.py:239-240`). No embedding, no perceptual hash. The spec
(§16) requires five levels including Chromaprint and embedding-assisted near-duplicate.

The spec is also correct that near-duplicate mechanisms *"MUST NOT silently delete examples"*
— they produce evidence. That is exactly right, and it is why this can be a factory
extension rather than a contract change: levels 1-2 feed `DedupFingerprint`; levels 3-5
produce factory-local evidence and **never** enter the downstream fingerprint.

One trap: `DedupFingerprint.__post_init__` validates hashes via `_optional_hash` but
**discards the return value** (`dedup.py:30-35, 53-60`), so a fingerprint built with an
uppercase hex hash keeps it uppercase and **will not group** with the lowercase form of the
same hash. Only `from_record` normalises by construction. The factory must never construct
`DedupFingerprint` directly — always `from_record`.

---

## 12. Legacy repo audit — `~/projects/ornix-dataset`

95 files / ~11,421 LOC / 324 tests across 46 files (unit 33 files/281 tests, integration
7/34, acceptance 2/9).

### 12.1 Audio stack — the spec's §5 is *not* what the legacy repo does

| Spec says | Legacy repo actually does |
|---|---|
| `torchcodec` | `soundfile` first, `ffmpeg` subprocess fallback — `dsp/decode.py:78-94`. **No `torchaudio`, no `torchcodec`, no `librosa`.** |
| FFmpeg system dependency | `ffprobe` for metadata, `ffmpeg` for decode — `dsp/decode.py:42-94` |
| `scipy.signal.resample_poly` | Correct, but **silently degrades to `np.interp` when scipy is absent** — `dsp/resample.py:18-38` returns `method="linear-degraded"`. Fail-closed at the render gate (`dsp/render.py:123-127`), fail-**open** at the adapter. |
| — | The resampler is **duplicated verbatim** at `detectors/music_noise.py:159-171`, and `detectors/vad.py:145` imports the *private* function across modules. |

`torch` appears only as an optional extra for gated `pyannote`/`panns`, never on the audio
path. `pyproject.toml:17-37` confirms: `dependencies = ["numpy>=1.24", "PyYAML>=6.0"]`,
extras `dsp = ["scipy>=1.10", "soundfile>=0.12"]`.

### 12.2 Where the obsolete assumptions actually live

| file:line | Code |
|---|---|
| `dsp/render.py:23` | `CANONICAL_SR = 24000` — the master constant |
| `dsp/decode.py:102` | `sr = info.get("sample_rate") or 24000` — silent 24 kHz default when ffprobe omits the rate |
| `canonical/verify.py:48` | `if wf.getframerate() != 24000:` → `SR_NOT_24K` |
| `exporters/verify.py:62` | same assertion, duplicated |
| `contracts/release.py:62` | `if self.sample_rate != 24000 or self.channels != 1 or self.encoding != "PCM_S16LE": raise` |
| `dsp/admission.py:65-66` | `canonical_sample_rate: int = 24000` / `native_min_sample_rate: int = 24000` |
| `pipeline.py:553` | `sample_rate=24000, channels=1, encoding="PCM_S16LE"` |
| `canonical/schema.py:24` | `CANONICAL_FIELDS = ("audio", "text", "file_name", "speaker", "duration", "language")` |
| `canonical/schema.py:103-106` | `if set(self.__dict__.keys()) != set(CANONICAL_FIELDS): raise SchemaError` |
| `canonical/schema.py:108-110` | `audio == file_name` load-bearing invariant, required *only* because HF `AudioFolder` treats them as a link column |
| `configs/audio_profile.yaml:3,16,26-28` | `24000`, `12000.0`, `24000`, `24000`, `22050` |

`canonical/loader.py:4-11` documents the old repo was **already fighting** AudioFolder:
*"Hugging Face `datasets`/`AudioFolder` builder instead casts the linked audio column to the
`Audio` feature ... so it cannot preserve `audio: str`/`file_name: str`"*. The new design
is free of a constraint the old code could not satisfy.

### 12.3 Things the legacy repo got right and MUST be preserved

These are not incidental — they are the hard parts, and rewriting them from scratch would be
a regression:

1. **Bounded downloader with real backpressure** — `ingestion/hf_downloader.py` (884 LOC):
   `_ByteBudget` backpressure, `_AdaptiveGate` circuit breaker, immutable staging, hard caps,
   durable journal, honest metrics. Proven by `tests/unit/test_hf_downloader.py` (27 tests),
   including `test_T1_files_download_truly_concurrently` (`:139-147`) which uses a
   `threading.Barrier` to *prove* overlap rather than assert it.
2. **Fail-closed rights** — `ingestion/permissions.py` (67 LOC).
3. **Immutable staging bound to content SHA** — `ingestion/hf.py`,
   `tests/unit/test_hf_materialize.py:30-96`.
4. **Union-find + LSH near-duplicate clustering, validated against brute force** —
   `curation/dedup.py:47-96`; `tests/unit/test_curation.py:71-81`
   (`test_lsh_dedup_matches_bruteforce_at_scale`) is the single best test in the repo.
5. **Release build + checksum verify** — `exporters/manifest.py:36-131`, with a load-bearing
   ordering comment at `:118-121`: *"a stale RELEASE_READY.json from a previous run must
   not be hashed and then overwritten"*.
6. **Remote verification as an exact set comparison** —
   `publishing/verification.py:31-88`; `EXTRA_REMOTE_FILE` is a failure, not a subset check.
7. **UNKNOWN is never zero** — `tests/unit/test_detectors.py:25-28`
   (`test_dnsmos_returns_unknown_not_zero`).
8. **The operator never auto-picks a quality threshold** —
   `curation/policy.py:45-48`: `min_quality_sig/bak/ovrl` default to `None` and must be
   bound by calibration. Keep this property.
9. **The honest-admission principle**, already written in
   `configs/audio_profile.yaml:21-23`: *"Upsampling a low-rate/narrowband source does NOT
   restore lost bandwidth: a file is never admitted merely because its output would say
   24,000 Hz."* Only the numbers change.

### 12.4 Things the legacy repo declared but never wired — and the spec correctly forbids

1. **ASR does not exist.** Repo-wide search for `whisper` / `transcribe` / `jiwer` /
   `word_error` → **0 matches**. `curation/transcript.py` implements a correct Levenshtein
   CER (`:26-37`) but `transcript_match_status` (`:40-52`) has **zero callers**, and its own
   docstring says *"We do NOT auto-generate the official transcript with ASR (out-of-scope
   v1)"*. Consequence: `policy._transcript` (`:195-205`) can only ever return `PASS` (via
   `NOT_APPLICABLE`) or `UNKNOWN` — **never a real transcript mismatch**. The spec's §10 is
   genuine new work, not a port.
2. **`model_revision` is dead.** `AdapterInfo.model_revision` exists
   (`detectors/base.py:31`) but is populated **only** by `EnergyVadAdapter`
   (`detectors/vad.py:44-46`, hardcoded `"0.1.0"`). No ML adapter ever sets it.
   `NoiseEvent.model_revision` (`contracts/quality.py:22`) is never written. The spec's §32
   model lock is a real fix, not a restatement.
3. **Speaker detection is permanently `UNAVAILABLE`.** `PyannoteAdapter._try_load`
   (`:33-45`) fails closed on missing `model_path` or `access_ack`; the model lock ships it
   commented out. So `policy._interfering` (`:170-178`) always returns `UNKNOWN` and the
   single-speaker gate is **never enforced**. Correct fail-closed design, zero capability.
4. **No SQLite.** `sqlite` / `sqlite3` / `CREATE TABLE` / `PRAGMA` / `cursor(` → **0 matches
   repo-wide**. State is atomic JSON + append-only JSONL (`campaign/store.py:1-16`), with
   durability from `util/io.py` (*"tmp + fsync + os.replace + dir fsync"*). There is no
   transaction layer, which is the root cause of three hand-rolled correctness mechanisms:
   reproducible `batch_id` (`campaign/models.py:48-54`), progress-preserving re-plan
   (`campaign/store.py:225-232`), and a single-writer `flock` (`canonical/identity.py:26-27`).
   The spec's §17 SQLite decision eliminates all three.
5. **Three competing CLI trees in 970 LOC** (`cli.py:713-954`): `{sources, ingest, qc, review,
   curate, calibrate, release, publish}`, `{campaign × 15 subcommands}`, `{canonical × 5}`,
   each with its own state model, build, publish and verify. The target 8-verb UX collapses
   this — which the SQLite layer is what makes possible.
6. **Silero v5 context-window contract** — `detectors/vad.py:127-142`: *"Silero v5 consumes
   576 samples per step: 64 context samples carried over from the previous window prepended
   to 512 new samples. Feeding only the 512-sample window (no context) makes the model emit
   ~0 on real speech."* `_CTX=64`, `_WIN=512`. **Do not lose this.**

### 12.5 Portability summary

| Verdict | Volume | Content |
|---|---|---|
| **Port** | ~4,000 LOC (35%) | downloader, backpressure, circuit breaker, immutable staging, fail-closed rights, resource reservation (`campaign/resources.py` — hysteresis watermark gate), dedup union-find + LSH, policy engine, split, checkpoint, cache, calibration, audit, util, remote verification, `canonical/bridge.py` + `canonical/verify.py` shapes |
| **Port the property, rewrite the code** | ~800 LOC | all detector adapters (keep the protocol, **wire `model_revision` for real**), segmentation, `contracts/enums.py`, ~100-120 of 324 tests |
| **Drop** | ~924 LOC | `canonical/{schema,identity,layout,loader,card,normalize,publish}.py`, `dsp/render.py`, `exporters/verify.py`, `curation/transcript.py` (dead CER, no ASR), `ops/{queue,retention}.py`, `ingestion/local.py`, `tests/unit/test_canonical_ids.py`, all AudioFolder assertions |

Full file-by-file matrix in `docs/MIGRATION.md`.

**Conclusion 2.** ~35% of the legacy repo is directly portable, and that 35% contains
genuinely hard engineering. The remaining 65% is the 24 kHz / six-field / `Ornix_<n>` contract
that must not survive, wrapped in orchestration that collapses once a transactional store
exists.

---

## 13. Summary of decisions required

| ID | Decision | Blocks | ADR |
|---|---|---|---|
| **C-1** | Do not reimplement the resampler; call `ornix.audio` | Phase F | `0002` |
| **C-2** | Factory owns `PENDING`+`REVIEW`; only `ACCEPT` crosses the boundary | Phase A | `0003` |
| **C-3** | Always build fingerprints with `use_record_text=False` + explicit comparison text | Phase M | `0004` |
| **C-4** | Enforce 48 kHz release rate from `ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ` | Phase Q | `0001` |
| **C-5** | Factory owns boundary detection; call `seeded_window_segments` for windows | Phase K | `0006` |
| **G-1** | `ACCEPT` requires a computed quality vector, not merely "no error" | Phase L | `0005` |
| **G-2** | Always call `validate_audio_metadata_consistency` with `B == 1` | Phase Q | — (runbook) |
| **G-3** | The factory ships the manifest reader it needs | Phase Q | — |
| **G-4** | Emit `DatasetEntry`-shaped metadata; do not block on registration | Phase Q | — |
| **G-5** | Never construct `DedupFingerprint` directly; always `from_record` | Phase M | — |

**No decision below is optional. Each one, if implemented the other way, produces a
reproducible-looking release that is silently wrong.**

# Architecture — Ornix-TTS Data Factory

> **Repository:** `Teedyyy-rm/ornix-Ds` (this repo)
> **Sole consumer:** `Teedyyy-rm/Ornix-TTS`
> **Status:** normative. Supersedes no prior document; refines the seed architecture against
> source-verified downstream contracts.
>
> **Reading order:** `docs/ANALYSIS.md` (why) → this document (what) → `docs/CONTRACTS.md`
> (the boundary, with citations) → `docs/adr/` (the decisions) → `docs/ROADMAP.md` (the order).
>
> **Rule:** where this document and an ADR appear to differ, the ADR wins until this document
> is amended. Where this document and `docs/CONTRACTS.md` differ, `Ornix-TTS` source wins.

---

## 0. Status and authority

This repository is not a generic speech-dataset toolkit.

Its only consumer is `Teedyyy-rm/Ornix-TTS`. Therefore:

- **Ornix-TTS contracts are authoritative.** This repository must not invent an incompatible
  training metadata schema, and must not redefine semantic, acoustic or training contracts.
- It produces auditable dataset artifacts that Ornix-TTS ingests directly.
- **Missing evidence is never converted into PASS.** (ADR 0008)
- **Unknown legal status is fail-closed.** → `BLOCKED`
- **Source audio is immutable.** A processed artifact never overwrites its source.

### 0.1 Obsolete assumptions — retired, permanently

```text
canonical sample rate            = 24 kHz
canonical public schema         = exactly six fields
                                   audio/text/file_name/speaker/duration/language
Hugging Face AudioFolder        defines the training contract
sequential Ornix_<number>       defines sample identity
```

Verified retired at source: `24000` and `44100` appear **zero times** in Ornix-TTS `src/`,
`tests/`, `configs/`, `data/`, `docs/`. The canonical training rate is 48 kHz
(`configs/train/audio_vae.yaml:3`). See ADR 0001.

### 0.2 Corrections applied to the seed architecture

The seed architecture was written before the downstream contract was read at source. Nine
corrections are incorporated here. Full evidence in `docs/ANALYSIS.md`.

| # | Seed said | This document says | ADR |
|---|---|---|---|
| C-1 | Implement a resampler, id `ornix-resample-polyphase-kaiser5-v1` | **Call `ornix.audio`.** No local resampler, ever. | `0002` |
| C-2 | Six decision states, all crossing the boundary | Six states, **two are factory-only**. Only `ACCEPT` crosses. | `0003` |
| C-3 | Ship `text_normalized: null` | Still true — **and** all fingerprints must use `use_record_text=False` with an explicit comparison text, or text dedup and text-leakage protection silently no-op. | `0004` |
| C-4 | Retire 24 kHz; name 48 k / 16 k views | Correct — **and the factory enforces the rate**, because upstream enforces nothing. | `0001` |
| C-5 | Factory owns `curation/segmentation.py` | Factory owns **boundaries**; `Ornix-TTS` owns **windows**. Call, do not reimplement. | `0006` |
| C-6 | "Missing evidence never becomes PASS" | Strengthened: `ACCEPT` **requires** a computed quality vector, because upstream `ACCEPTED` can mean `quality=None`. | `0005` |
| C-7 | Release consumable without another normalization project | The factory must **ship the manifest reader** — upstream has none. | §8.4 |
| C-8 | Registry not mentioned | Emit `DatasetEntry`-shaped metadata; do not block on registration (it is unwired upstream). | §8.5 |
| C-9 | Dedup level 3 = normalized transcript hash | Always via `use_record_text=False`; never construct `DedupFingerprint` directly. | `0004` |

---

## 0.3 Repository boundary — absolute

**Working directory: `/home/obito/projects/ornix-Ds/`. All work happens here.**

```text
/home/obito/projects/ornix-Ds      ← THIS repository. All writes.
    origin  https://github.com/Teedyyy-rm/ornix-Ds.git

/home/obito/projects/Ornix-TTS     ← DOWNSTREAM. READ-ONLY. NEVER WRITE.
```

`ornix-Ds` is a **separate project, split out of `Ornix-TTS`**. It is not a subdirectory, a
submodule, a workspace member, or a branch of it.

**Never, under any circumstance:**

- write, create, edit, delete or move any file under `/home/obito/projects/Ornix-TTS`;
- run any tool that writes there — `pytest`, `mypy --install-types`, `ruff --fix`, `build`,
  `pip install -e`, or any `uv sync` against that checkout;
- use a **path or editable dependency** on that checkout. `editable = true` writes
  `*.egg-info` into the source tree; a setuptools build writes `*.egg-info` and bytecode
  there. Both are forbidden;
- add `Ornix-TTS` to a uv workspace, or make either repo a member of the other.

**When reading it:**

- run any Python against that checkout with `python -B` or `PYTHONDONTWRITEBYTECODE=1`, so no
  `.pyc` is written into its tree;
- never `cd` into it to run anything;
- treat every read as a **snapshot**. Its branch is under active development and its HEAD
  moves — `cebd6d9` became `f9a3b1f` within one session. Cite a contract as
  *verified at `<sha>` on `<date>`*, never as permanent truth, and re-verify before relying
  on it.

**How the dependency is resolved.** `ornix-tts` is declared as a **normal dependency** in
`pyproject.toml`, for portability and so that CI resolves it from an index. For local
bootstrap, the source is **copied to a scratch directory outside both repositories**, built
into a wheel **there**, and that wheel is installed into this repository's `.venv`. The
`Ornix-TTS` checkout is read exactly once per build and never written.
Procedure: `docs/OPERATIONS.md` §1a.

This is a deliberate design constraint, not an inconvenience. The two repositories have
different lifecycles, different review gates and different rates of change. Coupling them at
the filesystem level would let a change to one silently become a change to the other.

---

## 1. Goal

Build a deterministic data factory:

```text
Dataset Sources → Inventory → Acquire → Immutable Raw Assets → Decode/Validate
  → Audio & Speech Analysis → Transcript Verification → Segmentation
  → Quality Qualification → Deduplication → Leakage-safe Split
  → Ornix-TTS ManifestRecord → Release Verification → Storage / Hugging Face
```

**The final release must be consumable by Ornix-TTS without another
metadata-normalization project.** Concretely, that means the release ships both the manifest
*and* a reader that reconstructs `ManifestRecord` objects from it, because
`ornix.data` provides no manifest file loader (`docs/CONTRACTS.md` §8).

---

## 2. Non-goals

This repository MUST NOT contain:

```text
TTS training                     Audio-VAE training
SSL representation training      semantic target extraction
Semantic Planner training        CFM/DiT training
TTS inference                    voice cloning inference
final spoken-form text frontend
denoising used to turn bad audio into "clean" audio
dereverberation used to fabricate clean samples
speaker gender inference         age inference
identity inference from voice
sequential id allocation         local ManifestRecord definition
local resampler                  local window segmenter
```

Feature extraction required specifically by training remains inside Ornix-TTS.

---

## 3. Dependency strategy

Dependencies are divided into extras:

```text
core  acquisition  audio  detectors  transcript  speaker  analytics  publishing  development
```

**No optional model may silently become a required gate.** A gate's requirement is declared
in policy, never inferred from provider availability.

Every model-backed provider exposes:

```python
provider_id  model_id  model_revision  weights_sha256  runtime  device  status
```

and every measurement carries a status:

```text
OK | UNAVAILABLE | ERROR | NOT_APPLICABLE
```

`UNAVAILABLE` MUST NOT become a fabricated clean result, and MUST NOT become `0.0`.
(ADR 0005, ADR 0008)

### 3.1 The provider contract

A single Protocol serves VAD, ASR, speaker and events. Uniform fields, uniform status
semantics, uniform fail-closed behaviour. A provider that cannot run returns
`status=UNAVAILABLE` with a reason — it does not raise through the policy layer, and it does
not return a value.

**Precedent to avoid.** The legacy repo declares `AdapterInfo.model_revision`
(`detectors/base.py:31`) but populates it **only** for `EnergyVadAdapter`
(`detectors/vad.py:44-46`, hardcoded `"0.1.0"`); no ML adapter ever sets it. A revision field
that is never written is worse than no revision field, because it looks like evidence.

---

## 4. Approved core libraries

### 4.1 Configuration and contracts

```text
pydantic >= 2
PyYAML
```

Pydantic is used for source configs, campaign configs, quality policies, detector outputs,
run metadata and release metadata. Strict validation at every external boundary:

```python
ConfigDict(strict=True, extra="forbid")
```

Unknown fields in versioned configuration **fail**, unless a specific extension map permits
them. A silently ignored misspelled key is a defect, not forward compatibility.

**Do not use Pydantic to redefine `ManifestRecord`.** Ornix-TTS is authoritative for the final
manifest contract. Load the reference constants from the installed package:

```python
from ornix.data import MANIFEST_SCHEMA_VERSION, ManifestRecord, Provenance
from ornix.contracts import WAVEFORM_SAMPLE_RATE_HZ
```

---

## 5. Audio I/O

**Primary library: `torchcodec`. System dependency: FFmpeg.**

Responsibilities: container decode, codec decode, audio stream metadata, canonical decode path.

**Do not build new code around deprecated TorchAudio media I/O APIs.** TorchAudio may be used
only where a specific maintained signal-processing primitive is demonstrably required.

Ornix-TTS already pins `torch==2.11.0` and `torchcodec==0.16.0`
(`pyproject.toml:25-28`, `audio/torchcodec.py:37-38`). The factory pins the same versions and
asserts compatibility at start-up.

### 5.1 Decode contract

```text
float32
[channel, samples]
finite values
explicit sample_rate
explicit sample count
```

No decoder may silently resample, normalise loudness, convert channels, or trim silence —
unless explicitly requested and written to provenance.

**A missing sample rate is a decode failure.** The legacy `sr = info.get("sample_rate") or
24000` (`dsp/decode.py:102`) is the canonical anti-pattern: it invents a rate and mislabels
the audio. (ADR 0008 §8.2)

### 5.2 AudioTensor interoperability

The decoded representation is constructed as `ornix.contracts.AudioTensor`
(`contracts/core.py:65-85`) via `ornix.audio.make_audio_tensor` — rank-3 `[B, C, T]`,
`float32`, finite, with explicit `int64` `lengths`. This is the same object
`compute_quality_vector` and `DedupFingerprint.from_record` consume, so no parallel tensor
contract is introduced. (ADR 0008 §8.5)

`lengths` must be **strictly `> 0`** (`audio/validation.py:45-55`) — zero-length audio is
rejected at the canonical boundary.

---

## 6. Resampling

**This repository implements no resampler.** All views are produced by
`ornix.audio.resample_audio` / `DeterministicResampler`, and the provenance
`implementation_revision` is `ornix.audio.RESAMPLER_VERSION`, read from the package — never a
locally invented string. (ADR 0002)

The seed architecture's proposed identity `ornix-resample-polyphase-kaiser5-v1` is
**rejected**: it duplicates `ornix.audio.RESAMPLER_VERSION =
"scipy-resample-poly-kaiser5-v1"` for the same algorithm, and would produce cache keys
Ornix-TTS cannot reuse.

Required recorded metadata per resampled artifact:

```text
source_sample_rate  target_sample_rate  up  down  window
implementation_revision  (= ornix.audio.RESAMPLER_VERSION)
```

**Resampling is a transformation, never part of decode.**

Required views:

| View | Rate | Role | Shipped? |
|---|---|---|---|
| master / native | source rate | analysis, bandwidth truth | no (workspace) |
| Audio-VAE view | `WAVEFORM_SAMPLE_RATE_HZ` (48 k) | training | **yes** |
| analysis view | 16 k | SSL / VAD / ASR | no (workspace) |

> Upsampling a low-bandwidth source does **not** restore lost bandwidth. A file is never
> admitted merely because its output would say 48,000 Hz. — principle preserved from the
> legacy `configs/audio_profile.yaml:21-23`, now generalised (ADR 0001 §6).

---

## 7. Master-audio policy

Immutable source bytes are preserved under `raw/`. Decoded and qualified representations are
created separately and never overwrite their source.

```text
source asset
    ├── immutable raw bytes            raw/
    ▼
decoded master                        master/       native rate
    ├── analysis view                 views/16k/
    └── Audio-VAE view                 views/48k/     ← the release
```

Every derived artifact records:

```text
parent hash  transformation  config hash  tool revision  output hash
```

The release ships **one** audio copy: the 48 kHz view. The native master is a workspace
artifact, re-derivable from raw bytes plus the resample recipe. (ADR 0001 §4)

---

## 8. Hugging Face integration

Use `huggingface_hub`: `hf_hub_download`, `snapshot_download`, upload APIs.

**Always pin source revision.** Production runs MUST NOT consume `revision: main` as a
reproducible source revision — it is resolved to an immutable commit SHA first, and that SHA
is what enters sample identity.

`datasets` is **optional** and may be used for source metadata inspection, dataset discovery,
Parquet inspection and interchange testing. It MUST NOT define Ornix canonical metadata.
Do not depend on AudioFolder behaviour for training correctness.

### 8.4 The reader obligation

`ornix.data` ships **no manifest file loader** — no `load_manifest`, no JSONL reader, no
`iter_*`; `ManifestRecord.from_json` is single-record and rejects bare `NaN`/`Infinity`
literals. Therefore the release ships, alongside `manifest.jsonl`, a reader that yields
`ManifestRecord` objects, and its round-trip is a compatibility gate. Without this, §1's
goal fails. (ADR 0005, `docs/CONTRACTS.md` §8)

### 8.5 Registry — emit, do not block

`ornix.data.registry` is not a required integration point today: `load_registry` has one
in-repo caller (a test), nothing in `src/` imports `ornix.data`, and `data/registry.yaml`
ships empty with that emptiness pinned by a test. The release therefore emits
`release/dataset.json` shaped to be convertible into a `DatasetEntry` (`id`, `version`,
`status`, `source_url`, `manifest_uri`, `languages`, `license`, `consent_scope`, `revision`,
`checksum`) from day one, but **does not block the release on registration**.

---

## 9. VAD

Default provider: **Silero VAD** on **ONNX Runtime CPU**. Analysis view: 16 kHz mono.

```python
VadEvidence:
    speech_intervals
    speech_ratio
    leading_silence
    trailing_silence
    provider  model_revision  status
```

VAD is a **segmentation/evidence signal**. It is NOT ground truth for turn-taking, speaker
identity, transcript boundaries, or conversation structure.

The factory's provider **conforms to the upstream `ornix.data.segmentation.VADProvider`
Protocol** (`segmentation.py:184-189`), which is declared but unimplemented upstream. That
Protocol is the extension point; conforming to it is the point of its existence. (ADR 0006)

> **Do not lose the Silero v5 context-window contract.** The legacy repo records it at
> `detectors/vad.py:127-142`: Silero v5 consumes **576 samples per step** — 64 context samples
> carried from the previous window, prepended to 512 new samples. Feeding only the 512-sample
> window makes the model emit ~0 on real speech.

---

## 10. Transcript verification

Default ASR provider: **faster-whisper**. Text-distance library: **jiwer**.

Minimum metrics: **WER** and **CER**. For Vietnamese, CER is retained alongside WER.

Comparison normalisation is isolated from canonical transcript storage:

```text
text_raw
   ├── preserved unchanged          → ManifestRecord.text_raw
   └── comparison normalization     → factory-local only
             ↓
          ASR match (WER/CER)
```

- `text_raw` is **never** replaced with ASR output.
- Datasets transcripts are **never** "corrected" with Whisper.
- **ASR verifies; it does not author the canonical transcript.**
- Model id, revision and decoding parameters are locked in `configs/models.lock.yaml`.

Because `text_normalized` is always `null` in the release, **every** fingerprint must be
built as `from_record(..., normalized_text=<comparison>, use_record_text=False)` — otherwise
`protect_normalized_text` silently protects nothing. (ADR 0004)

---

## 11. Speaker and overlap detection

```python
class SpeakerProvider(Protocol):
    def analyze(audio) -> SpeakerEvidence: ...
```

Optional high-quality provider: **pyannote.audio** — speaker count, speaker-change evidence,
overlap detection, and embeddings only when explicitly enabled.

It remains optional because of a large dependency footprint, credential requirements, and
unavailability on some workers.

**If policy requires the speaker gate and the provider is unavailable → `REVIEW`, not
`PASS`.**

Never infer gender, age, ethnicity or identity for dataset acceptance.

> **Precedent.** The legacy repo's `PyannoteAdapter._try_load` (`detectors/speaker.py:33-45`)
> fails closed on a missing model path or access ack, so it is **permanently `UNAVAILABLE`**;
> `policy._interfering` (`policy.py:170-178`) therefore always returns `UNKNOWN` and the
> single-speaker gate is **never enforced**. Correct fail-closed design, zero capability.
> The factory ships a real, credentialed provider — or declares the gate off. Not this middle
> state.

---

## 12. Music and acoustic-event detection

A generic `AudioEventProvider` interface. Initial candidate: **PANNs / AudioSet tagging**.

Target evidence: music probability, speech probability, interfering sound events, event
timeline.

**Never hardcode a PANNs-specific schema into core contracts.** Provider output normalises
into factory evidence:

```python
AudioEventEvidence(
    music_probability=...,
    events=...,
    provider="panns",
    model_revision="...",
)
```

This allows future replacement without dataset schema migration.

---

## 13. Objective signal analysis

Primarily **NumPy** and **SciPy**. No large DSP dependency where deterministic DSP suffices.

Required metrics: duration, sample rate, channel count, peak absolute value, RMS, DC offset,
clipping fraction, low-energy fraction, effective bandwidth, silence ratio, and the spectral
statistics required by policy.

**Every metric states which view it was measured on:**

```text
source | decoded master | 16k analysis view | 48k view | segment
```

Measurement is never mutation. (ADR 0008 §8.3)

---

## 14. Quality is a vector, not a score

MOS models (DNSMOS, NISQA) MUST NOT be the sole acceptance criterion. They are optional
diagnostic providers. NISQA pretrained weights MUST NOT enter the default commercial
production path unless licensing is explicitly reviewed.

**Forbidden:**

```json
{ "quality": 0.91 }
```

**Required:**

```json
{
  "speech_ratio": 0.97, "clip_fraction": 0.0, "snr_db": 31.4,
  "music_probability": 0.01, "reverb_score": 0.08, "asr_cer": 0.02,
  "speaker_overlap_probability": 0.0
}
```

Unavailable values remain `null` / `UNKNOWN` — **never zero**. (ADR 0005, ADR 0008 §8.1)

### 14.1 Where the vector lives

`ManifestRecord.quality` is a free-form `Mapping[str, object]` with **no allow-list**
(`manifest.py:198-199`), and `QualityVector` has no field for CER, WER, VAD ratio, bandwidth
or boundary evidence. Therefore the quality block has a fixed, versioned shape:

- **Top level is exactly `QualityVector.to_dict()`** — so an `ornix-tts` consumer can call
  `QualityVector.from_dict(record.quality)` unchanged, today.
- **All factory-specific evidence lives under `ornix_ds_evidence`**, versioned separately.

The six `QualityVector` optional slots (`speech_probability`, `snr_db`, `reverb_score`,
`music_probability`, `asr_match`, `speaker_consistency`) are declared upstream and **never
populated by any upstream code** — filling them is the intended contract use, not schema
drift.

**`ACCEPT` requires a computed quality vector.** A record without one is `REVIEW`. This is
enforced here because upstream `qualify_records` returns `ACCEPTED` with `quality=None` when
no `AudioTensor` is supplied (`qualification.py:531-556`). (ADR 0005)

---

## 15. Boundary integrity detector

**Mandatory for TTS.** Project-owned module `quality/boundaries.py`.

Combines evidence from VAD, edge energy, spectral activity, ASR timestamps when available, and
phonetic/word alignment when available.

```text
head_clip_probability   tail_clip_probability
leading_context_ms      trailing_context_ms
boundary_status
```

Detects: missing initial consonants, cut vowels, cut final syllables, bad segmentation around
speech.

**A clean TTS corpus MUST NOT rely only on generic MOS/noise metrics.**

A record with indeterminate boundaries is `REVIEW`, not `ACCEPT`. Factory boundaries are
recorded as **sample indices on the master**, which also makes sample identity exact
(§8.27). (ADR 0006)

---

## 16. Deduplication

| Level | Mechanism | Feeds `DedupFingerprint`? |
|---|---|---|
| 1 | `SHA-256` of raw source bytes | yes → `raw_audio_bytes_hash` |
| 2 | Hash of canonical float audio (`sample_rate`, `channels`, `length`, `float32-le`, shape prefix) | yes → `audio_content_hash` |
| 3 | Normalised transcript hash (comparison text) | yes → `normalized_text_hash`, via `use_record_text=False` |
| 4 | Perceptual fingerprint (Chromaprint) — optional provider | **no** — factory evidence only |
| 5 | Embedding-assisted near-duplicate — future optional | **no** — factory evidence only |

Levels 4-5 identify similar audio that differs at byte level. **Near-duplicate mechanisms MUST
NOT silently delete examples — they produce evidence first.**

Upstream `deduplicate_records` is exact-only by docstring and implementation (`dedup.py:231`),
so levels 4-5 are entirely factory work. (ADR 0004, `docs/CONTRACTS.md` §5.5)

> **Trap:** `DedupFingerprint.__post_init__` validates hashes but **discards the normalised
> value** (`dedup.py:30-35,53-60`), so a directly-constructed uppercase hex hash will not group
> with the lowercase form. `from_record` is the only safe construction path.

**Canonical selection rule** (upstream, `dedup.py:250-257`): the lexicographically smallest
`record_id` in a component wins. `DeduplicationResult.duplicate_ids` includes that canonical —
it is **not** "the ids to drop"; use `canonical_by_record`.

---

## 17. Runtime state

**SQLite** through the standard library is the authoritative mutable run state. **No JSON
files** as authoritative transactional state for multi-stage runs. **No DuckDB** for
transactional workflow state. (ADR 0007)

```text
runs  sources  assets  source_items  decoded_audio  segments  measurements
decisions  fingerprints  duplicate_groups  split_assignments  artifacts
releases  uploads  events
```

```text
SQLite  = transactional state
Parquet = release/analytics mirror
```

A phase commits its writes, measurements, decisions and artifact identities in **one
transaction**. A crash leaves the run in the last committed phase, never half-way through one.
Resume is state-driven: `ornix-data resume <run-id>` reads `(phase, status)` and re-executes
the first incomplete phase. There are no hand-rolled reconciliation paths and no `flock`.

---

## 18. Analytics

Optional: **Polars**, **PyArrow**, **DuckDB**.

```text
PyArrow  → Parquet interoperability
Polars   → large metadata transforms, report generation
DuckDB   → ad-hoc QA and release auditing
```

None is authoritative for pipeline state. For large releases, both `manifest.jsonl` and
`manifest.parquet` are produced:

```text
JSONL   = canonical interchange
Parquet = analytical mirror
```

Both hash back to the same logical records — a test asserts this by re-hashing the Parquet
rows into canonical JSON and comparing against the JSONL line hashes.

---

## 19. CLI

**Typer** + **Rich**.

```bash
ornix-data validate <campaign>
ornix-data run      <campaign>
ornix-data resume   <run-id>
ornix-data inspect  <run-id>
ornix-data qualify  <run-id>
ornix-data build    <run-id>
ornix-data verify   <release>
ornix-data push     <release>
```

`ornix-data run` executes the **complete allowed pipeline**. A worker MUST NOT stop after
preflight merely because intermediate checks passed. One state model, one verb per intent —
collapsing the legacy repo's three competing command trees over three incompatible state
models (`cli.py`, 970 LOC).

---

## 20. Repository layout

```text
ornix-Ds/
├── README.md  AGENTS.md  MEMORY.md  ARCHITECTURE.md
├── pyproject.toml  uv.lock
├── configs/{sources,campaigns,policies,audio}/  models.lock.yaml
├── src/ornix_data/
│   ├── cli.py  pipeline.py  version.py
│   ├── config/{models.py,loader.py}
│   ├── contracts/{source.py,evidence.py,decision.py,provenance.py,artifact.py,errors.py}
│   ├── sources/{base.py,huggingface.py,local.py}
│   ├── acquisition/{inventory.py,downloader.py,staging.py,hashing.py}
│   ├── audio/{decode.py,validate.py,views.py,channels.py,bandwidth.py}
│   ├── transcript/{mapping.py,verify.py,compare.py}
│   ├── providers/{base.py,vad/silero.py,asr/faster_whisper.py,
│   │              speaker/pyannote.py,events/panns.py,quality/dnsmos.py}
│   ├── quality/{signal.py,boundaries.py,aggregate.py,policy.py}
│   ├── curation/{dedup.py,grouping.py,qualify.py}
│   ├── ornix/{bridge.py,compatibility.py,loader.py,release.py,split.py}
│   ├── storage/{sqlite.py,parquet.py,filesystem.py}
│   ├── publishing/huggingface.py
│   └── ops/{checkpoint.py,cleanup.py,events.py,review.py}
├── tests/{unit,integration,compatibility,acceptance}/  fixtures/
└── scripts/validate_ornix_tts_compatibility.py
```

> **Deviations from the seed layout, and why.**
> `audio/resample.py` is **removed** (ADR 0002 — no local resampler).
> `curation/segmentation.py` is **removed as a windowing module**; boundary work lives in
> `quality/boundaries.py`, and window planning calls upstream (ADR 0006).
> `curation/segmentation.py` survives only as the utterance-boundary producer feeding
> `segments`; it contains no window arithmetic.
> `ornix/loader.py` is **added** (§8.4).
> `ornix/split.py` is **added** as the adapter that calls upstream `assign_splits` and owns
> the factory's duplicate-group union.
> `ops/review.py` is **added** because `REVIEW` is a work queue the factory owns (ADR 0003).
> `curation/transcript.py` is dropped; transcript work lives in `transcript/`.

---

## 21. Pipeline stages

```text
P0  CONFIG VALIDATION          P9  QUALITY POLICY
P1  SOURCE INVENTORY           P10 DEDUPLICATION
P2  ACQUISITION                P11 IDENTITY GROUPING
P3  IMMUTABLE STAGING          P12 SPLIT
P4  DECODE + AUDIO VALIDATION   P13 ORNIX-TTS MANIFEST
P5  ANALYSIS VIEW GENERATION   P14 RELEASE BUILD
P6  SPEECH/EVENT/SPEAKER       P15 RELEASE VERIFICATION
P7  TRANSCRIPT VERIFICATION    P16 OPTIONAL PUSH
P8  SEGMENTATION               P17 VERIFIED CLEANUP
```

Each phase produces an immutable artifact identity:

```text
input hashes  config identity  code revision  provider revisions  output hashes
```

---

## 22. Decision states

```text
PENDING  ACCEPT  REVIEW  REJECT  BLOCKED  DUPLICATE
```

```text
ACCEPT     all mandatory evidence passed, with a computed quality vector
REVIEW     evidence missing, unavailable or borderline
REJECT     available evidence proves quality failure
BLOCKED    rights / provenance / contract prevents use
DUPLICATE  technically usable but removed by dedup policy
```

**Only `ACCEPT` enters a training release.**

`PENDING` and `REVIEW` are **factory-only** and have no downstream equivalent; the projection
to `QualificationStatus` **raises** on them rather than guessing. (ADR 0003)

The `REVIEW` boundary is load-bearing and must survive refactors:

- unavailable / missing / borderline evidence → `REVIEW`
- evidence positively showing failure → `REJECT`
- `REVIEW` means *"we could not tell"*, `REJECT` means *"we know"*. Collapsing them biases the
  corpus toward whatever the available detectors happen to cover.

---

## 23. Rights and provenance

Every source declares:

```text
dataset id  upstream locator  revision  license  consent scope
commercial-training status  redistribution status
```

**Unknown values never inherit permissive defaults.**

```text
publicly downloadable ≠ commercially usable ≠ redistributable
```

Unknown rights → `BLOCKED`, unless an explicitly configured research-only policy says
otherwise. That policy must be recorded in the release metadata, not implied by absence of a
declaration.

> Upstream `ConsentScope` (`manifest.py:20-27`) is **documentation, not enforcement** — the
> field is a plain `str`, and only five tokens are fail-closed
> (`validation.py:15-16`). The real commercial-training policy is therefore enforced here.

---

## 24. Text ownership boundary

**This repository owns:** raw transcript preservation, encoding validation, language evidence,
audio-text verification, comparison-only normalisation.

**Ornix-TTS owns:** spoken normalisation, numbers, dates, currency, phonemisation, the
semantic-planner text frontend.

Release normally contains:

```json
{ "text_raw": "Có 12 người.", "text_normalized": null }
```

not:

```json
{ "text_raw": "Có mười hai người." }
```

unless the source transcript already was that string. Confirmed correct against source:
`qualify_records` runs its own `BaselineSpokenTextNormalizer` over `text_raw` and never mutates
`record.text_normalized` (`qualification.py:587-598`), and the upstream fixture
`test_m1_2_qualification.py:46-79` deliberately exercises the null path.

The comparison text is factory-local, versioned
(`text_compare_normalizer_revision`), and never written to either field. (ADR 0004)

---

## 25. Ornix-TTS compatibility boundary

**Critical invariant: do not create a second implementation of `ManifestRecord`.**

`ornix_data.ornix.bridge` builds every record through the actual Ornix-TTS contract:

```python
from ornix.data import ManifestRecord, Provenance
```

**Release build MUST fail if compatibility validation is unavailable.** No silent fallback to
a local look-alike schema.

Development setup:

```text
workspace/
├── Ornix-TTS/
└── ornix-Ds/
```

`pyproject.toml` declares `ornix-tts` as a real dependency (not an optional extra) so the
compatibility import is always available. The package name is `ornix-tts`; the import name is
`ornix`; Python `>=3.11` is required by `StrEnum`. (ADR 0008 §8.5)

---

## 26. Manifest output

Primary artifact: `manifest.jsonl`. Conceptual shape:

```json
{
  "schema_version": 1,
  "id": "…", "audio_uri": "…",
  "sample_rate": 48000, "channels": 1, "duration_s": 4.713125,
  "text_raw": "…", "text_normalized": null, "language": "vi",
  "speaker_id": "…", "conversation_id": null, "style_caption": null,
  "license": "…", "consent_scope": "…",
  "provenance": {}, "quality": {}, "hashes": {}
}
```

**The conceptual shape is not the authority.** Runtime validation against Ornix-TTS is.
Binding constraints, all from source:

- `schema_version == ornix.data.MANIFEST_SCHEMA_VERSION` (currently `1`).
- `Provenance.transformations` is a **`tuple`** when constructed.
- All 17 fields are present in serialized form, with **explicit `null`s** — `from_dict`
  requires them (`manifest.py:249-266`).
- Every `hashes` value is 64-char SHA-256 hex. There is no escape hatch.
- Every `quality` value is JSON-compatible with finite floats.
- `sample_rate == ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ`, **asserted here** because upstream
  asserts nothing. (ADR 0001)

`validate_audio_metadata_consistency` is always called with `B == 1`: it compares
`record.duration_s` against `np.max(lengths)`, the longest item in the batch, and has no
`item_index` parameter (`validation.py:70-72`). (`docs/CONTRACTS.md` §4.3)

---

## 27. Sample identity

Identity is **deterministic and content-derived**. Never:

```text
download order  worker order  wall-clock timestamp
global sequential counter  source filename alone
```

Identity input:

```text
dataset id
source revision
source item identity
segment start sample
segment end sample
```

then `SHA-256` over a canonical JSON payload yields a stable opaque sample key. A display
filename may use a truncated hash; the full identity is always stored internally.

Because boundaries are **sample indices on the master** (§15), identity is exact and
independent of float rounding. (ADR 0006 §4, ADR 0007 §8)

---

## 28. Speaker identity

Stable namespace:

```text
dataset id  source revision  source speaker reference
```

Speaker identifiers are **never merged across corpora by string equality**. If speaker
identity is unknown → `UNKNOWN`, or a stable sample-local identity per policy.

Identical names never imply identical speakers.

---

## 29. Splitting

Splits prevent leakage across:

```text
speaker identity     conversation identity
exact audio identity  raw-byte identity
configured normalized-text identity
known duplicate group
```

**Call the actual Ornix-TTS split implementation** — `assign_splits`, `SplitPolicy`,
`DedupFingerprint` — rather than duplicating it. The factory's own union-find contributes
**duplicate groups** as an extra group key; the rest of the grouping is upstream's.

Three upstream properties the factory must design around:

1. **Splits are not incrementally stable.** `group_key = canonical_json(sorted_members)`
   hashes the whole member list, so adding one utterance can re-hash and flip an entire
   speaker's component. A growing corpus must re-run `assign_splits` and re-publish
   `evaluation_split_identity()`. (`split.py:223-226`)
2. **Changing `seed`, `revision` or any fraction changes every assignment.**
3. **`protect_normalized_text` silently no-ops when `normalized_text_hash is None`.**
   (ADR 0004)

Published evaluation splits become immutable. A rerun with identical source revisions, policy,
seed and code revision reproduces identical split membership.

Validation↔test mixing is **not** flagged upstream (`split.py:273-278`); the factory adds that
dimension to its own leakage report.

---

## 30. Release layout

```text
release/
├── dataset.json          # DatasetEntry-shaped (§8.5)
├── manifest.jsonl        # canonical interchange
├── manifest.parquet      # analytical mirror
├── checksums.sha256
├── audio/{00,01,…}       # 48 kHz Audio-VAE view, stored once
├── splits/{train,validation,test}.ids
└── reports/
    ├── qualification.json  quality.json
    ├── dedup.json         leakage.json
    ├── rights.json        provenance.json
    └── review.json        # the REVIEW queue (§22)
```

**Audio is stored once.** Three physical copies are never made because an example belongs to
train, validation or test.

---

## 31. Publishing

Hugging Face is a publishing/storage target, **not** the source of truth.

```text
build → local verify → upload → remote inventory → remote checksum verify
      → mark VERIFIED → optional local cleanup
```

Never: upload → assume success → delete local source. **Cleanup requires remote
verification.** (ADR 0008 §8.5)

Remote verification compares the **exact file set**, not a subset — an extra remote file is a
failure. Preserved from the legacy `publishing/verification.py:31-88`.

---

## 32. Model lock

All ML providers are pinned in `configs/models.lock.yaml`:

```yaml
vad:      {provider: silero,       model: …, revision: …, sha256: …}
asr:      {provider: faster-whisper, model: …, revision: …, sha256: …}
speaker:  {provider: pyannote,     model: …, revision: …, sha256: …}
events:   {provider: panns,        model: …, revision: …, sha256: …}
```

**No runtime "download latest" behaviour** in reproducible campaigns.

Every provider's runtime report must populate `model_revision` and `weights_sha256` — the
legacy repo's declared-but-never-written revision field is the anti-pattern. (ADR 0008 §3.1)

---

## 33. Testing strategy

Four layers: `unit`, `integration`, `compatibility`, `acceptance`. Full matrix in
`docs/TESTING.md`.

Mandatory coverage includes: known-fixture decode, decode failure, NaN/Inf rejection,
sample-rate metadata validation, duration exactness, resampling determinism, resampling alias
rejection, channel policy, source immutability, hash determinism, VAD/ASR/speaker provider
unavailability, missing-metric-never-PASS, boundary clipping fixtures, transcript mismatch,
Vietnamese Unicode preservation, unknown language/license/consent, exact and decoded-content
duplicates, stable sample identity, speaker/conversation/audio leakage, split determinism
under input reorder, `ManifestRecord` compatibility, release checksum, remote-verify-before-
cleanup, and resume after crash at every phase.

---

## 34. CI gates

Before merge:

```text
ruff
mypy --strict
pytest unit
pytest integration
pytest compatibility
build
lockfile check
```

**The compatibility suite is mandatory.** This repository may be green internally and MUST NOT
claim release compatibility if the Ornix-TTS compatibility suite fails.

---

## 35. Migration

Port what is proven, rewrite what is idea-only, drop what is bound to the obsolete contract.
Full file-by-file matrix in `docs/MIGRATION.md`.

**Preserve:** HF downloader, bounded concurrency, backpressure, circuit breaker, source rights
logic, immutable staging, detector provider pattern, dedup union-find + LSH, policy engine,
upload verification with exact-set comparison, resume/checkpoint concepts, tests with valid
evidence, and the operator-never-auto-picks-a-threshold rule.

**Rewrite:** all detector adapters (protocol kept, `model_revision` actually wired),
segmentation, transcript verification (the legacy CER is dead code with no ASR), the CLI, and
the campaign orchestrator.

**Drop:** the six-field schema, sequential `Ornix_<n>` identity, AudioFolder layout, the 24 kHz
render path, and every test that encodes those assumptions.

**This is not a directory rename.** Each retained module is revalidated against this
architecture.

---

## 36. Implementation order

```text
A contracts/config   B SQLite state      C source registry     D acquisition
E TorchCodec decode  F views             G signal metrics     H VAD
I transcript         J speaker/events    K segmentation       L quality policy
M dedup              N identity grouping O compatibility bridge
P split              Q release builder   R release verifier   S publisher
T cleanup
```

**Do not start by building UI or publication automation.** Detail, dependencies, exit criteria
and risks in `docs/ROADMAP.md`.

---

## 37. Worker rules

**MUST:** inspect existing implementation before deleting reusable modules; preserve
evidence-first semantics; fail closed; write tests with every contract; pin model revisions;
pin source revisions; record hashes; preserve raw source; keep processing deterministic where
technically possible; avoid hidden repair; avoid hidden defaults; avoid schema drift from
Ornix-TTS.

**MUST NOT:** invent PASS; guess missing language; guess rights; guess speaker identity; change
`text_raw`; hide detector failure; replace a missing metric with zero; normalise every
waveform to peak 1; upsample low-bandwidth audio and label it HQ; denoise bad audio and label
it original clean audio; delete local artifacts before remote verification; copy the
Ornix-TTS contract into a divergent local schema.

These are codified as testable clauses in ADR 0008.

---

## 38. Acceptance criteria

A source dataset can be pinned and inventoried · downloaded reproducibly · raw bytes remain
immutable · audio decodes through the canonical decoder · audio metadata is verified against
decoded samples · derived views are reproducible · quality evidence is vectorised and
provider-aware · unavailable required detectors lead to `REVIEW` · known quality failures lead
to `REJECT` · unknown rights lead to `BLOCKED` · transcript mismatches cannot silently enter
`ACCEPT` · boundary clipping has explicit evidence · deduplication produces auditable reasons ·
split generation proves no configured train/eval leakage · every accepted release row is
instantiable through the actual `ManifestRecord` · release verification checks every referenced
audio artifact · manifest hashes are reproducible · a complete run resumes after interruption
without duplicating identity · upload is remotely verified before cleanup · no release is
labelled READY if any mandatory compatibility or integrity gate fails.

---

## 39. Final architectural invariant

```text
Source Dataset
      │
      ▼
Ornix Data Factory                    ornix-Ds, this repository
      │ produces evidence-backed, reproducible clean speech
      ▼
Ornix-TTS ManifestRecord              built through the real contract, never a look-alike
      │
      ▼
Ornix-TTS qualification
      │
      ▼
Training / Evaluation
```

This repository exists to make the boundary between raw internet speech data and Ornix-TTS
training data trustworthy.

It is not a generic downloader. It is not a generic audio cleaner. It is not a model-training
repository.

**It is the data admission and evidence layer of Ornix-TTS.**

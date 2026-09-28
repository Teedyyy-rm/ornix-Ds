# Contracts — the `Ornix-TTS` boundary

> **Status:** normative reference. Everything here is read from source at
> `Teedyyy-rm/Ornix-TTS@5da288c` (branch `main`) and is citable.
> If a line number drifts, the symbol name wins; re-verify before trusting a line.
>
> **Rule:** this file describes what `ornix-Ds` may *rely on*. It never re-declares a
> contract. If `ornix-Ds` needs something not listed here, that is a gap to close in
> `ornix-Tts` (upstream) or in `ornix-Ds` (locally) — never a local look-alike.

---

## 1. Package facts

| Item | Value | Source |
|---|---|---|
| Distribution name | `ornix-tts` | `pyproject.toml:6` |
| Import name | `ornix` | `[tool.setuptools] package-dir = {"" = "src"}` |
| Python | `>=3.11` (required by `StrEnum`) | `pyproject.toml:10` |
| Core deps | `numpy>=1.24,<3`, `PyYAML>=6.0,<7`, `scipy>=1.11,<2` | `pyproject.toml:11-15` |
| Media extras | `torch==2.11.0`, `torchcodec==0.16.0` | `pyproject.toml:25-28` |
| Canonical import path | `from ornix.data import ManifestRecord, Provenance` | `data/__init__.py` |
| Top-level re-export | **None** — `src/ornix/__init__.py` is 6 lines, exports only `__version__` | `src/ornix/__init__.py:1-6` |

`ornix.data`, `ornix.contracts` and `ornix.config` import with **numpy + PyYAML only**.
`torch` and `torchcodec` are lazily imported inside `ornix.audio`.

### 1.1 Version constants at a glance

| Constant | Value | Source |
|---|---|---|
| `MANIFEST_SCHEMA_VERSION` | `1` | `data/manifest.py:17` |
| `QUALITY_SCHEMA_VERSION` | `1` | `data/quality.py:17` |
| `QUALITY_VECTOR_REVISION` | `"ornix-quality-vector-v1"` | `data/quality.py:18` |
| `DEDUPLICATION_REVISION` | `"ornix-exact-dedup-v1"` | `data/dedup.py:18` |
| `SPLIT_POLICY_REVISION` | `"ornix-deterministic-split-v1"` | `data/split.py:17` |
| `SEGMENTATION_REVISION` | `"ornix-window-segmentation-v1"` | `data/segmentation.py:14` |
| `QUALIFICATION_SCHEMA_VERSION` | `1` | `data/qualification.py:39` |
| `QUALIFICATION_PIPELINE_REVISION` | `"ornix-m1.2-qualification-v1"` | `data/qualification.py:40` |
| `REGISTRY_SCHEMA_VERSION` | `1` | `data/registry.py:18` |
| `MIXTURE_SCHEMA_VERSION` | `1` | `data/registry.py:19` |
| `SUPPORTED_CONFIG_SCHEMA_VERSIONS` | `frozenset({1})` | `config/loader.py:18` |
| `WAVEFORM_SAMPLE_RATE_HZ` | `48_000` (**0 consumers**) | `contracts/core.py:32` |
| `SEMANTIC_RATE_HZ` | `25.0` | `contracts/core.py:28` |
| `SPECTRAL_FRAME_RATE_HZ` | `100.0` | `contracts/core.py:30` |
| `ACOUSTIC_LATENT_RATE_HZ` / `PROSODY_RATE_HZ` | `50.0` | `contracts/core.py:29,31` |
| `RESAMPLER_VERSION` | `"scipy-resample-poly-kaiser5-v1"` | `audio/resample.py:18` |
| `ORNIX_VERSION` | `"0.1.0"` | `src/ornix/__init__.py:3` |

---

## 2. `ManifestRecord` — the release contract

`data/manifest.py:156-301`, `frozen=True`, `MANIFEST_SCHEMA_VERSION = 1`.

| Field | Type | Required | Validation in `__post_init__` |
|---|---|---|---|
| `id` | `str` | yes | non-empty, no `\x00` |
| `audio_uri` | `str` | yes | non-empty text; opaque, no URI parse, no scheme check |
| `sample_rate` | `int` | yes | `validate_sample_rate(x)` **with no `expected`** → any positive int |
| `channels` | `int` | yes | positive int (`bool` rejected) |
| `duration_s` | `float` | yes | numeric, finite, `> 0` |
| `text_raw` | `str` | yes | `isinstance(str)` only — **may be empty** |
| `text_normalized` | `str \| None` | **explicit** | `str` or `None`; no default |
| `language` | `str` | yes | non-empty text |
| `speaker_id` | `str` | yes | non-empty text |
| `conversation_id` | `str \| None` | **explicit** | `str` or `None`; no default |
| `style_caption` | `str \| None` | **explicit** | `str` or `None`; no default |
| `license` | `str` | yes | non-empty text; **no SPDX validation** |
| `consent_scope` | `str` | yes | non-empty text; **not** `ConsentScope` |
| `provenance` | `Provenance` | yes | `isinstance(Provenance)` |
| `quality` | `Mapping[str, object]` | yes | `_validate_json_value` then `isinstance(Mapping)` |
| `hashes` | `Mapping[str, str]` | yes | non-blank `str` keys; **every value SHA-256 hex** |
| `schema_version` | `int = 1` | no | must `== 1` exactly, else `ManifestSerializationError` |

### 2.1 `Provenance` — `data/manifest.py:97-152`

| Field | Type | Default | Validation |
|---|---|---|---|
| `source` | `str` | — | non-empty text |
| `source_item_id` | `str` | — | non-empty text |
| `ingested_at` | `str` | — | non-empty text (**no ISO-8601 parse**) |
| `pipeline_version` | `str` | — | non-empty text |
| `source_checksum` | `str \| None` | `None` | SHA-256 hex if not `None` |
| `transformations` | `tuple[str, ...]` | `()` | **must be a `tuple`** when constructed; each element non-empty text |

`from_dict` (`:130-152`) accepts a list and converts to tuple. Constructing directly with a
list raises.

### 2.2 `ConsentScope` — `data/manifest.py:20-27`

```python
class ConsentScope(StrEnum):
    UNKNOWN = "UNKNOWN"; RESEARCH = "RESEARCH"; NON_COMMERCIAL = "NON_COMMERCIAL"
    COMMERCIAL = "COMMERCIAL"; EVAL_ONLY = "EVAL_ONLY"
```

**Documentation, not enforcement.** The dataclass field is typed `str` and validated only
with `_require_text`. Any non-empty string is accepted.

### 2.3 `canonical_json` — `data/hashing.py:16-28`

```python
json.dumps(value, ensure_ascii=False, sort_keys=True,
           separators=(",", ":"), allow_nan=False)
```

- `sort_keys=True` → hash is stable under dict insertion order.
- `ensure_ascii=False` → Vietnamese text is emitted raw and hashed as UTF-8 bytes. **Safe.**
- `allow_nan=False` → `NaN`/`Infinity` raise `HashingError`.
- `ManifestRecord.content_hash()` = `sha256_json(self.to_dict())` (`manifest.py:237-240`).
- `ManifestRecord.from_json` (`:291-301`) rejects bare `NaN`/`Infinity` JSON literals via
  `parse_constant`.

`ornix.config.loader._canonical_json` (`config/loader.py:21-27`) uses the **identical**
flags, so config hashes and manifest hashes are byte-compatible canonical forms.

### 2.4 Surprises that will bite an external producer

1. **`from_dict` requires all 17 fields, including the nullable ones** (`:249-266`). A
   manifest that omits `text_normalized` fails with `ManifestSerializationError`. Emit
   explicit `null`s.
2. **`hashes` has no escape hatch** — every value must be 64-char hex. Extra facts go in
   `quality`.
3. **`sample_rate` is unconstrained.** 16 k, 22.05 k, 44.1 k, 48 k all construct cleanly.
4. **`quality` is free-form.** `_validate_json_value` (`:57-76`) enforces structure only —
   no allow-list, no schema, no reserved keys. Arbitrary nested JSON round-trips verbatim
   and **does** affect `content_hash()`.
5. **`frozen=True` is shallow.** `quality` and `hashes` remain caller-owned live mappings;
   mutating a dict after construction silently changes `content_hash()`.
6. **Error classes differ by field.** `ManifestSerializationError` (schema version,
   missing fields, bad JSON) subclasses `ManifestValidationError`. Catch the parent.
7. **Empty `license`/`consent_scope` are rejected at construction**, so `"UNKNOWN"` is the
   smallest legal unknown token — and is exactly what the fail-closed lists catch.

---

## 3. `quality` — where factory evidence must live

### 3.1 `QualityVector` — `data/quality.py:33-153`

**Required (8):** `duration_s`, `peak_abs`, `rms`, `dc_offset`, `clip_fraction`,
`low_energy_fraction`, `channel_count`, `sample_rate`.

**Optional (6), all default `None`:** `speech_probability`, `snr_db`, `reverb_score`,
`music_probability`, `asr_match`, `speaker_consistency`.

Optional fields accept any finite numeric value — `speech_probability` and
`music_probability` are **not** range-checked to `[0,1]`.

### 3.2 `compute_quality_vector` — `data/quality.py:156-199`

```python
def compute_quality_vector(audio: AudioTensor, *, item_index: int = 0,
                           low_energy_threshold: float = 1e-4,
                           revision: str = QUALITY_VECTOR_REVISION) -> QualityVector
```

- **Requires an `AudioTensor`.** Calls `validate_audio_tensor` first.
- Computes over valid samples only: `waveform[item_index, :, :int(lengths[item_index])]`.
- `duration = lengths[item_index] / sample_rate` — **per item**, unlike
  `validate_audio_metadata_consistency` (see §4.3).
- **Populates only the 8 required scalars.** All six optional fields are left `None`, and
  `search_code` over `^src/` confirms **nothing in `ornix-tts` ever assigns them**.
  They are declared-but-unpopulated slots the factory is expected to fill.
- No waveform mutation (asserted by `tests/unit/test_m1_2_qualification.py:232-238`).

### 3.3 What is NOT in `QualityVector`

Confirmed absent by `search_code` over `^src/ornix/data/`:

```text
asr_cer  asr_wer  wer  cer  vad_speech_ratio  boundary  clip_evidence
```

`QualityVector.from_dict` (`:130-153`) reads only the 16 known keys and **silently drops
unknown keys**. Extending the vector requires a `QUALITY_VECTOR_REVISION` bump, which is
hashed into feature cache keys (`tests/unit/test_m1_3_semantic_infrastructure.py:177`).

**Therefore all factory-specific evidence (CER, WER, VAD intervals, boundary probabilities,
bandwidth, provider statuses) lives in `ManifestRecord.quality` under a namespaced key.**
See ADR `0005`.

### 3.4 `ManifestRecord.quality` accepts free-form JSON — confirmed

`manifest.py:198-199`. No allow-list, no schema, no reserved-key check. The only requirement
is JSON-compatibility with finite floats and non-blank string keys.

### 3.5 Aggregation blind spot

`qualification._report_for` (`:351-407`) only summarises `peak_abs`, `rms`, `dc_offset`,
`clip_fraction`, `low_energy_fraction` plus `available_records`. Anything extra the factory
puts in `ManifestRecord.quality` is **not** surfaced in `QualificationReport`. The factory
owns its own reporting surface.

---

## 4. Validation and rights — `data/validation.py`

### 4.1 Fail-closed lists — `:15-16`

```python
UNKNOWN_LICENSE_VALUES = frozenset({"", "UNKNOWN", "UNLICENSED", "NONE", "NULL"})
UNKNOWN_CONSENT_VALUES = frozenset({"", "UNKNOWN", "UNSPECIFIED", "NONE", "NULL"})
```

Asymmetric: `UNLICENSED` is license-only, `UNSPECIFIED` is consent-only. Matching is
`value.strip().upper()` (`:19-28`), so `"unknown"`, `" Unknown "`, `"NULL"` all fail closed.

### 4.2 API surface

```python
validate_manifest_record(record) -> ManifestRecord              # type guard only
require_known_rights(record) -> ManifestRecord                  # raises DatasetPolicyError
validate_audio_metadata_consistency(record, audio, *, tolerance_samples=0.5) -> ManifestRecord
```

`validate_manifest_record` performs **no field re-validation** — its docstring says so
(*"Validate one record's schema without changing its rights status"*). Field validation
happens in `ManifestRecord.__post_init__`.

### 4.3 The `np.max(lengths)` quirk — `:70-72`

```python
lengths = cast(np.ndarray[Any, Any], audio.lengths)
expected_duration = float(np.max(lengths)) / float(audio.sample_rate)
if abs(record.duration_s - expected_duration) * audio.sample_rate > tolerance_samples:
    raise ManifestValidationError("manifest and decoded durations differ")
```

- Compares against the **longest item in the batch**, not `lengths[item_index]`.
- There is **no `item_index` parameter**.
- `tolerance_samples=0.5` is **half a sample** (~10 µs at 48 kHz).
- `tests/conftest.py:24` uses a deliberately unequal-length batch (`lengths=[8, 5]`).

**`ornix-Ds` always calls this with `B == 1`.** Same convention in
`audio_duration_seconds` (`audio/validation.py:117-125`).

### 4.4 `AudioTensor` — `contracts/core.py:65-85`, `audio/validation.py:58-114`

```python
@dataclass(frozen=True)
class AudioTensor:
    waveform: TensorLike   # rank 3 [B, C, T], exactly float32, finite, dims > 0
    sample_rate: int       # positive int, no expected rate
    lengths: TensorLike    # rank 1 int64, one per batch item, 0 < lengths[i] <= T
```

Canonical constructor `make_audio_tensor(waveform, *, sample_rate, lengths)` is
**NumPy-only** at the CPU boundary. `lengths` is mandatory — *"padding semantics must be
explicit"* — and must be **strictly `> 0`** (`audio/validation.py:45-55`).
`validate_audio_tensor(audio, *, expected_sample_rate=None)` is the only place a rate can be
asserted, and it is optional.

---

## 5. Deduplication — `data/dedup.py`

### 5.1 `DedupFingerprint` — `:39-113`

| Field | Type | Default |
|---|---|---|
| `record_id` | `str` | required |
| `audio_content_hash` | `str \| None` | `None` |
| `raw_audio_bytes_hash` | `str \| None` | `None` |
| `normalized_text_hash` | `str \| None` | `None` |
| `source_item_hash` | `str \| None` | `None` |
| `manifest_hash` | `str \| None` | `None` |
| `revision` | `str` | `"ornix-exact-dedup-v1"` |

**Trap:** `__post_init__` calls `_optional_hash` but **discards its return value**
(`:30-35, 53-60`), so a directly-constructed fingerprint with an uppercase hex hash keeps
it uppercase and **will not group** with the lowercase form. Only `from_record` normalises.
**`ornix-Ds` never constructs `DedupFingerprint` directly.**

### 5.2 `DedupFingerprint.from_record` — `:65-102`

```python
from_record(record, *, audio=None, raw_audio_bytes=None, normalized_text=None,
            use_record_text=True, item_index=0) -> DedupFingerprint
```

- `audio_content_hash` = `_audio_content_hash(audio, item_index)` if `audio` given, else `None`.
- `raw_audio_bytes_hash` = `sha256_bytes(raw)` if given (must be `bytes`).
- `normalized_text_hash` = `sha256_text(record.text_normalized if use_record_text else normalized_text)`;
  `None` if the selected value is `None`.
- `source_item_hash` = `sha256_json({"source": ..., "source_item_id": ...})` — **always**.
- `manifest_hash` = `record.content_hash()` — **always**.

### 5.3 Audio content hash algorithm — `:116-137`

```python
length  = int(lengths[item_index])
values  = np.ascontiguousarray(waveform[item_index, :, :length], dtype="<f4")
prefix  = canonical_json({"sample_rate": ..., "channels": int(values.shape[0]),
                          "length": length, "dtype": "float32-le",
                          "shape": list(values.shape)}).encode("utf-8")
return sha256_bytes(prefix + b"\0" + values.tobytes(order="C"))
```

- dtype forced to little-endian float32, so float64/big-endian producers normalise.
- `item_index`/batch position is **not** in the prefix — same audio at slot 0 vs slot 1
  hashes identically. (Desired.)
- Valid samples only; padding never affects the hash.
- The `\0` separator prevents prefix/bytes boundary collisions.

### 5.4 `deduplicate_records` — `:227-285`

Unioned attributes (`:239-240`): `audio_content_hash`, `raw_audio_bytes_hash`,
`source_item_hash`, plus `normalized_text_hash` when `include_text=True`.
`_group_ids` (`:214-224`) skips `None`, so a missing hash means no grouping on that axis.
Union via `_UnionFind` (`:194-211`), **order-independent** (root = lexicographically
smaller id).

**Canonical selection** (`:250-257`): components iterated in sorted order, members sorted,
`canonical = members[0]` — the **lexicographically smallest `record_id`** wins.

`DuplicateReason` (`:21-27`): `EXACT_AUDIO_DUPLICATE` (audio **or** raw bytes),
`EXACT_TEXT_DUPLICATE` (normalized text), `SAME_SOURCE_ITEM` (source item), `NOT_DUPLICATE`.

`DeduplicationResult.duplicate_ids` (`:183-184`) returns **every** id in evidence where
`is_duplicate` — which **includes the canonical** of any multi-member group. Do not treat it
as "the ids to drop"; use `canonical_by_record`.

### 5.5 Near-duplicate: not supported

Docstring `:231` — *"Group only exact equalities; no learned near-duplicate heuristic is
used."* The only mention of near-duplicates upstream is in the **spec**
(`docs/specs/data_pipeline_spec.md:352-353`), not in code. Levels 3-5 of the factory's dedup
ladder are factory-local evidence and **never** enter `DedupFingerprint`.

---

## 6. Split — `data/split.py`

### 6.1 `SplitPolicy` — `:27-77`

| Field | Default |
|---|---|
| `seed` | `0` |
| `train_fraction` | `0.9` |
| `validation_fraction` | `0.05` |
| `test_fraction` | `0.05` |
| `protect_speaker` | `True` |
| `protect_conversation` | `True` |
| `protect_exact_audio` | `True` |
| `protect_normalized_text` | **`False`** |
| `revision` | `"ornix-deterministic-split-v1"` |

Fractions must sum to 1 within `abs_tol=1e-9` (`:50-52`).
`config_hash()` = `sha256(canonical_json(self.to_dict()))` (`:76-77`).

### 6.2 `assign_splits` — `:188-229`

```python
assign_splits(records, *, fingerprints=None, policy=None) -> SplitAssignment
```

Algorithm: sort by `record.id` → build namespaced group keys (`speaker:`, `conversation:`,
`audio:`, `text:`) → union members → collect components → for each component,
`group_key = canonical_json(sorted_members)` →
`_hash_bucket(policy, group_key)` = `sha256(canonical_json({seed, revision, group_key}))`
as a big-endian int over `2**256` → bucket into `train` / `validation` / `test`.

**Order-independent: yes, guaranteed.** Proven by
`tests/unit/test_m1_2_qualification.py:280-300` (forward vs reversed vs shuffled input).

**Three properties `ornix-Ds` must design around:**

1. **Splits are NOT incrementally stable.** `group_key` hashes the *entire* sorted member
   list of a component. Adding one utterance for speaker S re-hashes S's whole component
   and may flip its split. A growing corpus must re-run `assign_splits` and re-publish
   `evaluation_split_identity()`.
2. **Changing `seed`, `revision` or any fraction changes every assignment.**
3. **`protect_normalized_text` silently no-ops when `normalized_text_hash is None`** —
   see ADR `0004`.

### 6.3 Leakage checks — `:232-302`

| `dimension` | key | gated by |
|---|---|---|
| `"speaker"` | `record.speaker_id` | `policy.protect_speaker` |
| `"conversation"` | `record.conversation_id` | `policy.protect_conversation` (and not `None`) |
| `"audio"` | `audio_content_hash` or `raw_audio_bytes_hash` | `policy.protect_exact_audio` (and fingerprint present) |
| `"text"` | `normalized_text_hash` | `protect_normalized_text` (and fingerprint + hash present) |

A violation is recorded iff a key's records span **`TRAIN` together with `VALIDATION` or
`TEST`**. **Validation↔test mixing is not flagged.** `assert_no_train_eval_leakage` raises
`SplitLeakageError` (subclass of `SplitError`) with `canonical_json(report.to_dict())`.

### 6.4 `evaluation_split_identity` — `:99-108`

Hashes the **full policy dict** + the **sorted `(record_id, split_name)` list of
validation+test members only**. Training membership is deliberately excluded, so train
churn does not invalidate a published evaluation identity. Any eval reassignment or any
policy edit does.

### 6.5 Requirements to call it

`records`: a list/tuple of `ManifestRecord` with **unique `.id`**. Optional: a
`Mapping[str, DedupFingerprint]` and a `SplitPolicy`. There is **no bulk fingerprint helper**
and **no manifest file loader** — see §8.

---

## 7. Segmentation — `data/segmentation.py`

### 7.1 `VADProvider` — `:184-189` — declared, **never implemented**

```python
@runtime_checkable
class VADProvider(Protocol):
    def regions(self, source_record_id: str, *, duration_s: float
                ) -> Sequence[tuple[float, float]]: ...
```

`search_code` over `^src/` for `VADProvider` returns only the declaration.
`seeded_window_segments` neither accepts nor calls it. **This is factory work.**

### 7.2 `WindowSegmentationPolicy` — `:155-181`

`window_s=10.0`, `stride_s=None` (→ `window_s`), `max_segments=None`, `jitter_s=0.0`,
`revision="ornix-window-segmentation-v1"`. `jitter_s` must be `< window_s`.

### 7.3 `seeded_window_segments` — `:204-270`

```python
seeded_window_segments(source_record_id, *, duration_s, seed, policy=None,
                       speaker_id=None, conversation_id=None, channel=None) -> tuple[Segment, ...]
```

- **Takes no `VADProvider`.** Fixed-stride windows with seeded jitter.
- Fully deterministic: `_seed_fraction` = `sha256(canonical_json({...}))[:8]` big-endian
  over `2**64`. No RNG object, no global state.
- `max_segments` ranks windows by `_seed_fraction` ascending, truncates, re-sorts by
  `(start, index)`.
- `overlap_allowed` is derived: `effective_stride_s < window_s`.

`segment_id_for(source_record_id=, start_s=, end_s=, segmentation_revision=, seed=)` →
`"seg-" + sha256(canonical_json(payload))` (`:51-76`) — purely metadata-derived.

### 7.4 Ownership

`qualify_records` calls `seeded_window_segments` as **stage 3 of every accepted record**
(`qualification.py:497-526`). The `revision` is hashed into `QualificationConfig.identity()`,
so changing the policy changes `QualificationReport.content_hash()`, and `segment_id` is
content-addressed — a different policy breaks downstream joins.

**`ornix-Ds` calls it. It does not reimplement it.** See ADR `0006`.

---

## 8. What `ornix-tts` does NOT provide (factory obligations)

| Gap | Evidence | Severity |
|---|---|---|
| **No manifest file loader.** No `load_manifest`, no JSONL reader, no `iter_*` in `ornix.data`. `ManifestRecord.from_json` is single-record. | `data/manifest.py:291-301`; `search_code` for `^def load_\|^def read_\|^def iter_\|jsonlines\|jsonl` over `^src/ornix/data/` → only `load_registry`, `load_mixture` | **High** — blocks the §1 goal outright |
| **No bulk fingerprint helper.** `DedupFingerprint.from_record` is one-at-a-time; no batch variant. | `dedup.py:65-102` | Medium |
| **No near-duplicate detection.** Exact-only by docstring and implementation. | `dedup.py:231` vs `docs/specs/data_pipeline_spec.md:352-353` | **High** |
| **No `PENDING` / `REVIEW` state.** `QualificationStatus` has 4 members. | `qualification.py:43-47` | **High** |
| **`ACCEPTED` does not imply a quality vector exists.** Quality stage is skipped when no `AudioTensor` is supplied; `quality=None`, `applied=False, reason="audio_unavailable"`, status still `ACCEPTED`. | `qualification.py:531-556` | **High** — silent quality hole |
| **Registry is unwired.** `load_registry` has 1 caller (a test). Nothing in `src/` imports `ornix.data`. `data/registry.yaml` ships empty and the test pins the empty state. Only link to manifest is the opaque, unresolved string `manifest_uri`. | `trace_path` inbound; `IMPORTS` query | Medium |
| **48 kHz unenforced.** `WAVEFORM_SAMPLE_RATE_HZ` has 0 consumers; every data test fixture uses 16 kHz manifests. | `contracts/core.py:32`; `tests/unit/test_m1_data_pipeline.py:44,197` | Medium |
| **`quality` extras not aggregated.** `_report_for` summarises 5 scalars + `available_records` only. | `qualification.py:396-405` | Low |
| **Splits not incrementally stable.** Adding a record re-hashes whole speaker components. | `split.py:223-226` | Medium |
| **`CONSENT`/`LICENSE` are free-form strings.** Only 5 tokens each are fail-closed; a policy needing "commercial training permitted" has no upstream representation. | `manifest.py:170-171`; `validation.py:15-16` | Medium |
| **No ASR, no alignment, no boundary detection anywhere in `ornix.data`.** | `search_code` | High — factory work by design |

---

## 9. Qualification — `data/qualification.py` (the six operations)

`qualify_records(records, *, config=None, audio_by_id=None, raw_audio_bytes_by_id=None)`.
`run_qualification` (`:722-736`) is a verbatim alias with zero in-repo callers.

Per-record pipeline, sorted by `record.id` (duplicate ids raise `QualificationError`):

| Stage | Lines | Failure → | `failure_reasons` prefix |
|---|---|---|---|
| `text_normalize` | 444-462 | `REJECTED` | `NORMALIZATION_ERROR:` |
| `rights_validate` | 465-491 | `BLOCKED` | `RIGHTS_BLOCKED:` (rights is the **only** BLOCKED cause) |
| `segment` | 497-526 | `REJECTED` | `SEGMENTATION_ERROR:` |
| `quality` | 531-556 | `REJECTED`, **or skipped** when no `AudioTensor` | `QUALITY_ERROR:` |
| `exact_dedup` | 587-615 | `REJECTED` (retried audio-less) | `HASH_ERROR:` |
| batch `deduplicate_records` | 627 | `DUPLICATE` for non-canonical survivors | `DUPLICATE:{reason}` |
| `assign_splits` on accepted | 671 | — | — |
| `assert_no_train_eval_leakage` on accepted | 676 | **aborts the whole run** | — |

The transformation history always contains exactly these six operations, in this order,
whether or not they applied (`tests/unit/test_m1_2_qualification.py:366-390`):

```python
assert {e.operation for e in qualified.transformation_history} == {
    "text_normalize", "rights_validate", "segment", "quality", "exact_dedup", "split"
}
```

Non-application is recorded via `applied=False` + `reason`, never by omission.

**Two escape hatches `ornix-Ds` must know about:**

- `QualificationConfig.require_known_rights=False` (`:105`) turns `BLOCKED` into
  `ACCEPTED`. This flag is part of the trust boundary.
- Missing `AudioTensor` yields `ACCEPTED` with `quality=None` (see §8).

**Error classes are flattened.** `ornix.audio` errors root at `AudioPipelineError`, which does
**not** subclass `DataPipelineError`, so `qualify_records` catches them with bare
`except Exception` and converts them to `QUALITY_ERROR:{ExcType}` strings. **Downstream must
read `failure_reasons` strings, not exception types.**

---

## 10. Config schema versioning — `ornix.config`

```python
SUPPORTED_CONFIG_SCHEMA_VERSIONS = frozenset({1})   # config/loader.py:18
```

There is no single `CONFIG_SCHEMA_VERSION` integer and no canonical config constant. The
frozenset is the only alignable artefact.

`load_config(path, *, expected_schema_version=None) -> ConfigDocument` (`:95-142`):

1. Suffix must be `.json` / `.yaml` / `.yml`.
2. `yaml.safe_load` for YAML — deliberately, *"config files are data, never Python code"*.
3. Top level must be a `dict`.
4. `schema_version` must be a non-`bool` int `>= 1` and in the supported set.
5. `_validate_json_value` walk — finite floats, `str` keys, no arbitrary Python objects.
6. `content_hash = sha256(_canonical_json(data))`.

**Unknown fields are preserved, not rejected**
(`tests/unit/test_config_schema_version.py:39-58`). Forward-compatible.

Every YAML/JSON `ornix-Ds` ships to `ornix-tts` must carry top-level `schema_version: 1`.

---

## 11. Downstream test suites that constrain `ornix-Ds`

| File | Scope |
|---|---|
| `tests/unit/test_m1_2_qualification.py` (35 tests) | **The primary downstream contract suite.** Imports 21 names from `ornix.data` + `ornix.data.errors` + `ornix.text`. Covers segmentation determinism, quality round-trip, exact dedup, split determinism/order-independence, speaker & conversation isolation, exact-audio leakage rejection, report determinism, transformation history, unknown-rights blocking. |
| `tests/unit/test_m1_data_pipeline.py` (29 tests) | Manifest schema round-trip, **Vietnamese diacritics preserved** (`:241`), audio metadata consistency, unknown license/consent blocked, registry/mixture policy, hash determinism. |
| `tests/unit/test_audio_tensor_validation.py` | `AudioTensor` dtype/rank/length/rate negatives |
| `tests/unit/test_m0_negative_paths.py` | `SampleRateMismatchError`, `TensorContractError` paths |
| `tests/unit/test_config_schema_version.py` | Config schema version + safe-YAML |
| `tests/unit/test_package_import.py` | `ornix.__version__ == "0.1.0"` |
| `tests/integration/test_m0_public_surface.py` | `ornix.config` + `ornix.contracts` compose **without torch** (`:10`) |

Reference fixture (`:192-218`) uses `sample_rate=16_000`, `quality={"clipping": False,
"snr_db": 30.0}`, `hashes={"audio_sha256": source_hash}`. The qualification fixture
(`test_m1_2_qualification.py:46-79`) deliberately sets **`text_normalized=None`**, `quality={}`,
`hashes={}` — so the explicit-null path is the *tested* path.

**These tests run unchanged against `ornix-Ds` output. They are the compatibility gate.**

---

## 12. Compatibility obligations checklist

`ornix-Ds` may claim release compatibility only when every row is true:

- [ ] Every record is constructed through `ornix.data.ManifestRecord` and
      `ornix.data.Provenance` — never a local look-alike.
- [ ] `schema_version == MANIFEST_SCHEMA_VERSION`, read from the constant.
- [ ] `Provenance.transformations` is a `tuple`.
- [ ] All 17 fields are present in serialized form, with explicit `null`s.
- [ ] Every `hashes` value is a 64-char SHA-256 hex string.
- [ ] Every `quality` value is JSON-compatible with finite floats.
- [ ] `sample_rate == ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ`, asserted by the factory
      because upstream does not.
- [ ] `validate_audio_metadata_consistency` passes with `B == 1`.
- [ ] `require_known_rights` passes for every released record.
- [ ] `content_hash()` is stable across a serialize/deserialize round-trip.
- [ ] The release ships a reader that reconstructs `ManifestRecord` from `manifest.jsonl`.
- [ ] `tests/unit/test_m1_2_qualification.py` and `test_m1_data_pipeline.py` pass
      unmodified against factory output.
- [ ] The compatibility suite is wired into CI and is **mandatory**.

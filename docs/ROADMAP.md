# Roadmap — Ornix-Ds

> **Status:** normative execution plan. Phases execute in the order given.
> A phase is **done** only when its exit criteria are green in CI.
>
> **Authority:** `ARCHITECTURE.md` (what) · `docs/adr/` (decisions) ·
> `docs/CONTRACTS.md` (the boundary) · `docs/ANALYSIS.md` (why) ·
> `docs/MIGRATION.md` (what to port) · `docs/TESTING.md` (how it is proven).
>
> **Estimation unit:** engineer-days for a single competent engineer already briefed on the
> architecture. These are planning numbers, not commitments. They exclude model-download
> latency, credential acquisition, and legal review.

---

## 0. How to read this

Each phase states:

| Field | Meaning |
|---|---|
| **Objective** | The single sentence that, if true, closes the phase |
| **Deliverables** | Concrete files/modules created or ported |
| **Depends on** | Phases that must be `done` first |
| **Exit criteria** | Testable statements. Vague criteria are a bug in the plan |
| **Risks** | What is most likely to go wrong, and the response |
| **Port from** | Legacy module to reuse (`docs/MIGRATION.md`) |

**Do not start a phase whose dependency is not green.** The ordering is dependency order, not
preference. The single most common failure mode for this kind of project is building the
publishing layer before the quality policy exists, and then having nothing to publish.

---

## 1. Milestone map

```text
M0  FOUNDATION      A B            contracts, config, state          ~6 d
M1  ACQUISITION     C D            sources, download, staging        ~9 d
M2  SIGNALS         E F G          decode, views, metrics            ~8 d
M3  EVIDENCE        H I J K        VAD, transcript, speakers, cuts   ~13 d
M4  CURATION        L M N P        policy, dedup, grouping, split   ~10 d
M5  RELEASE         O Q R S T      bridge, build, verify, publish   ~12 d
                                          TOTAL                      ~58 d
```

```text
                          M0
      ┌────────────┬──────┴──────┬────────────┐
      A            B             C            D
 contracts       SQLite      registry    acquisition
      └────────────┴──────┬──────┴────────────┘
                          │
                    ┌─────┴─────┐
                    E           F
                  decode      views
                    └─────┬─────┘
                       G  │
                  metrics │
                    ┌─────┴─────┬────────────┐
                    H           I            J
                   VAD    transcript     speaker/events
                    └─────┬─────┴────────────┘
                          K
                   segmentation
                          │
                    ┌─────┴─────┬────────────┐
                    L           M            N
                  policy      dedup     grouping
                    └─────┬─────┴─────┬──────┘
                               P  split │
                    ┌──────────────────┴──┐
                    O                    │
              compatibility bridge       │
                    └─────────┬───────────┘
                              Q
                        release build
                    ┌─────────┴───────────┐
                    R                     S
                verifier              publisher
                    └─────────┬───────────┘
                              T
                           cleanup
```

---

## 2. Phase detail

### Phase A — Contracts and configuration

- **Estimate:** 3 d · **Milestone:** M0 · **Depends on:** — · **Blocks:** everything

**Objective.** Every external boundary validates strictly, and the decision enum is correct.

**Deliverables**

```text
src/ornix_data/version.py
src/ornix_data/contracts/errors.py        DataFactoryError hierarchy
src/ornix_data/contracts/decision.py      DecisionState + to_ornix_status()   [ADR 0003]
src/ornix_data/contracts/source.py        SourceSpec, RightsDeclaration
src/ornix_data/contracts/evidence.py      provider metadata + MeasurementStatus
src/ornix_data/contracts/provenance.py    ProvenanceRecipe
src/ornix_data/contracts/artifact.py      ArtifactIdentity
src/ornix_data/config/models.py           pydantic models, extra="forbid"
src/ornix_data/config/loader.py          YAML/JSON loader, safe_load only
configs/{sources,campaigns,policies,audio}/*.example.yaml
configs/models.lock.yaml
pyproject.toml   uv.lock
```

**Key constraints**

- `DecisionState` is the six-state enum. `to_ornix_status()` is **total over the four
  admissible states and raises `DecisionMappingError` on `PENDING`/`REVIEW`** (ADR 0003).
- Configs are `ConfigDict(strict=True, extra="forbid")`. Unknown fields **fail**.
- Reference constants are **imported from `ornix.data`**, never re-declared:
  `MANIFEST_SCHEMA_VERSION`, `QUALITY_VECTOR_REVISION`, `RESAMPLER_VERSION`,
  `WAVEFORM_SAMPLE_RATE_HZ`, `SEGMENTATION_REVISION`, `SPLIT_POLICY_REVISION`.
- `RightsDeclaration` has no permissive default: unknown license/consent is `BLOCKED`.
- `pyproject.toml` declares `ornix-tts` as a **non-optional** dependency.

**Exit criteria**

- [ ] `to_ornix_status` raises on `PENDING` and `REVIEW`; returns a `QualificationStatus` for
      the other four; a parametrised test covers all six.
- [ ] An unknown key in any config file is rejected, with the key named in the error.
- [ ] A config with a missing `license` loads as unknown-rights, not as permissive.
- [ ] `yaml.safe_load` semantics proven: `!!python/object/apply:` raises.
- [ ] `mypy --strict` and `ruff` clean.
- [ ] `pyproject.toml` imports `ornix.data` successfully in a bare environment.

**Risks**

- *Pydantic v2 strict mode rejects legitimate YAML coercions* (e.g. `16000` for a float).
  → Keep rate/count fields `int`; use explicit validators only where the coercion is intended
  and documented.

---

### Phase B — SQLite state

- **Estimate:** 3 d · **Milestone:** M0 · **Depends on:** A · **Blocks:** D, and all resume

**Objective.** One transactional store, one state model, resume by reading `runs`. (ADR 0007)

**Deliverables**

```text
src/ornix_data/storage/sqlite.py    connection, migrations, transactions
src/ornix_data/storage/filesystem.py  content-addressed paths
src/ornix_data/ops/events.py         append-only run event log
```

Tables: `runs sources assets source_items decoded_audio segments measurements decisions
fingerprints duplicate_groups split_assignments artifacts releases uploads events`.

**Key constraints**

- `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON` on open.
- One connection per worker; a run is single-writer. Parallelism is **within** a phase.
- A phase commits writes + measurements + decisions + artifact identities in **one**
  transaction.
- A `schema_version` column exists from day one; migrations are manual at v1.
- Filesystem is content-addressed; the DB records identity, not location history.

**Exit criteria**

- [ ] All 15 tables exist with foreign keys enforced; an orphan insert fails.
- [ ] A transaction rolled back mid-phase leaves no partial rows.
- [ ] `resume` is implemented against `(phase, status)` and needs no filesystem scan.
- [ ] Content-addressed lookup resolves an artifact by hash with no directory walk.

**Risks**

- *SQLite single-writer limits throughput.* Accepted (ADR 0007). The mitigation is
  intra-phase parallelism across source items, not multi-writer transactions.
- *Designing the schema for the current phase instead of the final one.* → Write all 15
  tables up front; unused ones stay empty. Schema churn mid-pipeline is the expensive path.

---

### Phase C — Source registry and rights

- **Estimate:** 2 d · **Milestone:** M0 · **Depends on:** A · **Blocks:** D

**Objective.** A source is declarable, pinnable and rights-gated before a byte is fetched.

**Deliverables**

```text
src/ornix_data/sources/base.py        SourceAdapter protocol
src/ornix_data/sources/huggingface.py
src/ornix_data/sources/local.py
```

**Port from:** `ingestion/permissions.py` (67 LOC) — the fail-closed rights model is correct
as written.

**Key constraints**

- Every source declares: `dataset_id`, `upstream_locator`, `revision`, `license`,
  `consent_scope`, `commercial_training`, `redistribution`.
- **`revision: main` is rejected for production campaigns.** Resolved to a commit SHA first,
  and that SHA enters sample identity.
- Unknown rights → `BLOCKED` at P0, before download.

**Exit criteria**

- [ ] A source with unknown license is `BLOCKED` before any network call.
- [ ] A source declaring `revision: main` in a production campaign is rejected with a message
      naming the pinning requirement.
- [ ] `commercially_usable`, `redistributable` and `downloadable` are independent fields and a
      test proves one cannot be derived from another.

---

### Phase D — Acquisition, inventory, immutable staging

- **Estimate:** 7 d · **Milestone:** M1 · **Depends on:** B, C · **Blocks:** E

**Objective.** Reproducible download with real backpressure, staged immutably, bound to a
content hash.

**Deliverables**

```text
src/ornix_data/acquisition/inventory.py    remote listing, pinned revision
src/ornix_data/acquisition/downloader.py   bounded concurrency + backpressure
src/ornix_data/acquisition/staging.py      immutable staging
src/ornix_data/acquisition/hashing.py      raw byte hashing
```

**Port from (high confidence, this is the hard part):**

| Legacy module | LOC | Note |
|---|---|---|
| `ingestion/hf_downloader.py` | 884 | `_ByteBudget` backpressure, `_AdaptiveGate` circuit breaker, durable journal, honest metrics, hard caps |
| `ingestion/hf.py` | 179 | pinned-SHA adapter, immutable staging, probe patching |
| `ops/cache.py` | 52 | content cache |
| `ops/env.py` | 86 | dotenv |
| `util/io.py` | — | atomic write (still needed for non-state files) |

Port `tests/unit/test_hf_downloader.py` (27 tests) and
`tests/unit/test_hf_materialize.py` — including `test_T1_files_download_truly_concurrently`
(`:139-147`), which uses a `threading.Barrier` to *prove* overlap rather than assert it.

**Key constraints**

- Raw bytes are written once and made read-only. Nothing downstream writes to `raw/`.
- Staging is bound to the upstream content SHA; a mismatch is a hard failure.
- Bounded concurrency with backpressure and a circuit breaker, as in the legacy module.

**Exit criteria**

- [ ] Download is genuinely concurrent (barrier test, not a timing assertion).
- [ ] A single worker reproduces the sequential result byte-for-byte.
- [ ] A content-SHA mismatch fails and leaves no partial asset marked acquired.
- [ ] Re-running acquisition on an unchanged source performs zero redundant writes.
- [ ] Two runs of the same pinned revision produce identical inventory.

**Risks**

- *The 884-line downloader is the single most valuable legacy file and also the most
  entangled.* Port it, then revalidate it against the new contracts rather than rewriting it
  from memory. Do not "clean it up" during the port.

---

### Phase E — TorchCodec decode

- **Estimate:** 4 d · **Milestone:** M2 · **Depends on:** D · **Blocks:** F, G

**Objective.** One decode path, no silent transformations, no invented metadata.

**Deliverables**

```text
src/ornix_data/audio/decode.py     canonical decode → AudioTensor
src/ornix_data/audio/validate.py   decode + metadata validation
src/ornix_data/audio/channels.py   explicit channel policy
```

**Key constraints**

- Internal representation: `float32`, `[channel, samples]`, finite, **explicit** sample rate
  and sample count — constructed as `ornix.contracts.AudioTensor` so no parallel tensor
  contract exists.
- Pin the same `torch==2.11.0` / `torchcodec==0.16.0` as Ornix-TTS; assert compatibility at
  start-up (`ornix.audio.torchcodec.TORCHCODEC_SUPPORTED_VERSION`).
- **A missing sample rate is a decode failure.** Never `or 24000`.
- No implicit resample / downmix / trim. Each is explicit, requested, and written to
  provenance.
- `lengths` must be strictly `> 0` (`audio/validation.py:45-55`).

**Exit criteria**

- [ ] Known fixtures decode at their declared rate; a fixture with no declared rate **fails**.
- [ ] NaN/Inf output is rejected.
- [ ] Channel policy is explicit: multi-channel is a policy decision, never an implicit
      downmix.
- [ ] `validate_audio_tensor` passes for every decoded item.
- [ ] Duration is exact to the sample, with the rounding rule stated in the runbook.

**Risks**

- *Torchaudio's deprecated media I/O leaking back in.* → A static test asserts the
  `torchaudio` media backends are never imported.

---

### Phase F — Views (48 kHz Audio-VAE, 16 kHz analysis)

- **Estimate:** 2 d · **Milestone:** M2 · **Depends on:** E · **Blocks:** H, I, G

**Objective.** Reproducible derived views, produced by the downstream resampler, with complete
provenance.

**Deliverables**

```text
src/ornix_data/audio/views.py       master/16k/48k view construction + ViewRecipe
src/ornix_data/audio/bandwidth.py   effective bandwidth measurement
```

**There is no `audio/resample.py`.** (ADR 0002)

**Key constraints**

- Views are produced by `ornix.audio.resample_audio` / `DeterministicResampler`.
- `implementation_revision` is `ornix.audio.RESAMPLER_VERSION`, read from the package.
- Every view records `source_sample_rate`, `target_sample_rate`, `up`, `down`, `window`,
  `implementation_revision`.
- **Bandwidth is measured on the master and reported.** A source is never admitted because its
  output would say 48 kHz.

**Exit criteria**

- [ ] Two independent runs produce byte-identical views.
- [ ] `implementation_revision == ornix.audio.RESAMPLER_VERSION` on every artifact.
- [ ] A static test proves no local `resample_poly` call exists in the factory.
- [ ] A narrowband source upsample to 48 kHz is rejected on **bandwidth evidence**, not
      silently labelled high quality.

---

### Phase G — Objective signal metrics

- **Estimate:** 2 d · **Milestone:** M2 · **Depends on:** E, F · **Blocks:** L

**Objective.** Deterministic scalar features, each tagged with the view it was measured on.

**Deliverables**

```text
src/ornix_data/quality/signal.py
```

Metrics: duration, sample rate, channel count, peak, RMS, DC offset, clip fraction,
low-energy fraction, effective bandwidth, silence ratio, policy-required spectral statistics.

**Port from:** `dsp/features.py` (114 LOC) and `dsp/technical.py` (237 LOC).

**Key constraints**

- NumPy/SciPy only. No large DSP dependency.
- Every metric records `measured_on: source|master|view16k|view48k|segment`.
- **Measurement is never mutation.** No normalisation, no denoise, no gating.
- Clip fraction and low-energy fraction must agree with `QualityVector` semantics
  (`quality.py:187-188` uses `|x| >= 1.0` and `|x| <= threshold`).

**Exit criteria**

- [ ] A fixture produces the exact expected metric vector, asserted numerically.
- [ ] Every metric carries `measured_on`.
- [ ] The factory's `QualityVector` fields match upstream `compute_quality_vector` exactly for
      the same audio (compatibility test).

---

### Phase H — VAD

- **Estimate:** 4 d · **Milestone:** M3 · **Depends on:** F, and the provider protocol in A
· **Blocks:** K, L

**Objective.** Speech-interval evidence from a real provider, conforming to the upstream
Protocol, failing closed.

**Deliverables**

```text
src/ornix_data/providers/base.py            Provider protocol (uniform metadata)
src/ornix_data/providers/vad/silero.py
```

**Key constraints**

- Conforms to `ornix.data.segmentation.VADProvider`
  (`regions(source_record_id, *, duration_s) -> Sequence[tuple[float, float]]`,
  `segmentation.py:184-189`) — `@runtime_checkable`, so conformance is testable.
- Runs on the 16 kHz mono analysis view; ONNX Runtime CPU.
- **Silero v5 context window: 576 samples per step = 64 context + 512 new.** The legacy repo
  documents at `detectors/vad.py:127-142` that feeding only 512 makes the model emit ~0 on
  real speech. This must be preserved and unit-tested with a fixture that would fail without
  it.
- `model_revision` and `weights_sha256` come from `configs/models.lock.yaml` and are actually
  written into every evidence record.
- Unavailable provider → `status=UNAVAILABLE` + `REVIEW`, never a fabricated clean result.

**Exit criteria**

- [ ] `isinstance(provider, VADProvider)` is true.
- [ ] The 576-sample context test passes, and fails if the context is removed.
- [ ] With the model absent, records land in `REVIEW` — not `ACCEPT`, not `REJECT`.
- [ ] Every `VadEvidence` carries provider id, model id, revision, weights sha, runtime,
      device, status.

---

### Phase I — Transcript verification

- **Estimate:** 5 d · **Milestone:** M3 · **Depends on:** F, H · **Blocks:** L

**Objective.** ASR measures the transcript; it never authors it. (ADR 0004)

**Deliverables**

```text
src/ornix_data/transcript/mapping.py    per-source text extraction + encoding validation
src/ornix_data/transcript/compare.py    comparison normalisation (versioned, factory-local)
src/ornix_data/transcript/verify.py     WER/CER via faster-whisper + jiwer
```

**This phase is entirely new work.** The legacy `curation/transcript.py` implements a correct
Levenshtein CER but `transcript_match_status` has **zero callers**, and there is no ASR in the
legacy repo at all (`whisper`/`jiwer`/`transcribe` → 0 matches). Its `_transcript` policy gate
could only ever return `PASS` or `UNKNOWN`.

**Key constraints**

- `text_raw` is byte-identical to the source. Never rewritten.
- `text_normalized` is always `null` in the release.
- The comparison text lives in a separately named, versioned field and **never** reaches
  `text_raw` or `text_normalized`.
- WER **and** CER are computed. For Vietnamese, CER is retained alongside WER.
- Model id, revision and decoding parameters are locked.
- A gate whose provider is unavailable is `REVIEW`. A gate that **cannot fail** is a defect —
  the legacy dead-code pattern is banned and a test enforces reachability.

**Exit criteria**

- [ ] Vietnamese diacritics survive extraction, comparison and serialization.
- [ ] A transcript-mismatch fixture produces a recorded mismatch; a matching fixture does not.
- [ ] `text_raw` is byte-identical to the source for every record, asserted against the source
      transcript store.
- [ ] The comparison normalizer's revision is recorded in provenance.
- [ ] With ASR disabled, records land in `REVIEW`.
- [ ] A deliberately mismatched transcript cannot reach `ACCEPT`.

---

### Phase J — Speaker and event providers (optional)

- **Estimate:** 4 d · **Milestone:** M3 · **Depends on:** H · **Blocks:** nothing (optional)

**Objective.** Overlap and music evidence, optional and honestly absent when unavailable.

**Deliverables**

```text
src/ornix_data/providers/speaker/pyannote.py
src/ornix_data/providers/events/panns.py
src/ornix_data/providers/quality/dnsmos.py     (diagnostic only)
```

**Key constraints**

- Never infer gender, age, ethnicity or identity. Not for any purpose in this repository.
- PANNs-specific schema never enters core contracts; output normalises into
  `AudioEventEvidence`.
- DNSMOS/NISQA are diagnostics. **NISQA pretrained weights do not enter the default commercial
  production path** without an explicit licensing review.
- If policy requires a gate whose provider is unavailable → `REVIEW`.
- The legacy repo's permanent-`UNAVAILABLE` pyannote adapter (declared gate, zero capability)
  is the failure mode to avoid: ship a working provider, or declare the gate off. Not the
  middle state.

**Exit criteria**

- [ ] Absent credentials → `REVIEW` on gated records, `ACCEPT` unaffected where the gate is off.
- [ ] A music-heavy fixture is detected; the evidence carries the provider revision.
- [ ] No code path in the repository references gender, age, or identity inference.

---

### Phase K — Segmentation and boundary integrity

- **Estimate:** 4 d · **Milestone:** M3 · **Depends on:** H, I · **Blocks:** N

**Objective.** Utterance boundaries detected with explicit evidence; windows delegated. (ADR 0006)

**Deliverables**

```text
src/ornix_data/quality/boundaries.py      head/tail clip, leading/trailing context
src/ornix_data/curation/segmentation.py   utterance extent → sample indices
```

**There is no window arithmetic in the factory.** `seeded_window_segments` is called.

**Key constraints**

- Boundary evidence combines VAD, edge energy, spectral activity, ASR timestamps when
  available, and alignment when available.
- Output: `head_clip_probability`, `tail_clip_probability`, `leading_context_ms`,
  `trailing_context_ms`, `boundary_status`.
- Detects missing initial consonants, cut vowels, cut final syllables, bad segmentation.
- **Factory boundaries are sample indices on the master** — exact, and they feed sample
  identity deterministically.
- The factory's segment key is a separate namespaced hash and never collides with upstream
  `"seg-..."`.
- Indeterminate boundaries → `REVIEW`.

**Exit criteria**

- [ ] `cut_vowel` fixture → `REJECT` with `boundary_status != OK`.
- [ ] `missing_initial_consonant` fixture → head clip probability above the policy floor.
- [ ] The energy-trough heuristic alone is **insufficient** — a test proves the fixture that
      the legacy heuristic passes is caught here.
- [ ] Factory segment ids never start with `seg-`.
- [ ] Records produced by the factory yield identical upstream `segment_id` values for the same
      policy and seed (compatibility test).

---

### Phase L — Quality policy

- **Estimate:** 4 d · **Milestone:** M4 · **Depends on:** G, H, I, J, K · **Blocks:** M, O

**Objective.** One deterministic decision function over the evidence vector. (ADR 0005)

**Deliverables**

```text
src/ornix_data/quality/aggregate.py     evidence → QualityVector + ornix_ds_evidence
src/ornix_data/quality/policy.py        vector → DecisionState
configs/policies/*.yaml
src/ornix_data/ops/review.py            the REVIEW queue
```

**Port from:** `curation/policy.py` (243 LOC) — a pure, deterministic, versioned decision
engine. Port it nearly as-is.

**Key constraints**

- **Vector-based, never scalar.** `{"quality": 0.91}` is forbidden.
- `ACCEPT` **requires** a computed quality vector, because upstream `qualify_records` returns
  `ACCEPTED` with `quality=None` when no `AudioTensor` is supplied
  (`qualification.py:531-556`).
- Unmeasured → `null` + a provider status. **Never `0.0`.**
- `REVIEW` = evidence missing/unavailable/borderline. `REJECT` = evidence proves failure. The
  distinction survives refactors.
- **The operator never auto-picks a threshold.** Unset thresholds stay unset and must be bound
  by calibration. Preserved verbatim from the legacy `curation/policy.py:45-48`.
- Rights is a separate, earlier gate: unknown → `BLOCKED`, independent of quality.

**Exit criteria**

- [ ] A missing metric never yields `ACCEPT`; it yields `REVIEW`.
- [ ] A detector outage yields `REVIEW`, not `REJECT` and not `ACCEPT`.
- [ ] A known-bad fixture yields `REJECT` with a reconstructable reason.
- [ ] Unset thresholds cause a policy error, not a silent pass.
- [ ] A `REVIEW` queue is produced and is not empty when a provider is absent.

---

### Phase M — Deduplication

- **Estimate:** 4 d · **Milestone:** M4 · **Depends on:** A, L · **Blocks:** N, P

**Objective.** Five levels; levels 1-3 feed `DedupFingerprint`, levels 4-5 produce evidence
only. (ADR 0004)

**Deliverables**

```text
src/ornix_data/curation/dedup.py        levels 1-3 (+ 4, 5 as evidence)
```

**Port from:** `curation/dedup.py` (96 LOC) — the union-find with path compression and the LSH
candidate generator are correct and proven. Port
`tests/unit/test_curation.py:71-81` `test_lsh_dedup_matches_bruteforce_at_scale` — the single
best test in the legacy repo.

**Key constraints**

- Fingerprints are **only** built through `DedupFingerprint.from_record`, always with
  `use_record_text=False` and an explicit comparison text.
- When the comparison text is unavailable: record `text_evidence_status=UNAVAILABLE`, and
  either send to `REVIEW` or **declare the text axis unprotected in the release metadata**.
  Silence is not an option.
- Near-duplicate mechanisms **never silently delete**; they emit evidence.
- Use `canonical_by_record`, not `duplicate_ids`, to decide what to drop — the latter includes
  the canonical of each group (`dedup.py:183-184`).

**Exit criteria**

- [ ] Exact-byte and decoded-content duplicates are detected with reasons.
- [ ] A text-duplicate pair with `text_normalized=null` **is** grouped (proving `0004`).
- [ ] A static test proves no `use_record_text=True` exists in the source tree.
- [ ] Near-duplicate evidence is produced without removing any record.
- [ ] Dedup is order-independent.

---

### Phase N — Identity grouping

- **Estimate:** 2 d · **Milestone:** M4 · **Depends on:** K, M · **Blocks:** P

**Objective.** Stable speaker, conversation and duplicate-group identities.

**Deliverables**

```text
src/ornix_data/curation/grouping.py
```

**Key constraints**

- Speaker namespace: `dataset_id + source_revision + source_speaker_reference`.
- **Never merge speaker identifiers across corpora by string equality.**
- Unknown speaker → `UNKNOWN` or a stable sample-local id per policy.
- Sample identity is the `SHA-256` of the canonical payload from `ARCHITECTURE.md` §27.
- **No counter, no sequential allocation, no filename-derived identity.** A static test
  enforces this.

**Exit criteria**

- [ ] Identity is stable across a re-run with identical inputs.
- [ ] Identity does not change when the source is re-downloaded in a different order.
- [ ] A speaker named "spk1" in two corpora produces two distinct identities.
- [ ] No sequential id allocation exists (static check).

---

### Phase O — Ornix-TTS compatibility bridge

- **Estimate:** 3 d · **Milestone:** M5 · **Depends on:** A, L, N · **Blocks:** Q

**Objective.** Every record is built through the real contract, and the build fails loudly
when compatibility cannot be checked.

**Deliverables**

```text
src/ornix_data/ornix/bridge.py           build Provenance + ManifestRecord
src/ornix_data/ornix/compatibility.py    contract probe + version assertions
src/ornix_data/ornix/loader.py           manifest.jsonl → ManifestRecord   [§8.4]
scripts/validate_ornix_tts_compatibility.py
tests/compatibility/
```

**Key constraints**

- **No second `ManifestRecord`.** Construction goes through
  `ornix.data.ManifestRecord` / `Provenance`.
- `Provenance.transformations` is a **`tuple`**.
- All 17 fields serialized with **explicit `null`s**.
- Every `hashes` value is 64-char SHA-256 hex.
- `sample_rate == ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ`, asserted **here** (ADR 0001).
- `validate_audio_metadata_consistency` is called with **`B == 1`**.
- `require_known_rights` passes for every released record.
- `QualityVector.from_dict(record.quality)` must succeed for every record.
- The release ships `ornix/loader.py`, because upstream has no manifest reader.
- **Release build fails when compatibility validation is unavailable.** No fallback.

**Exit criteria**

- [ ] The unmodified `Ornix-TTS/tests/unit/test_m1_2_qualification.py` and
      `test_m1_data_pipeline.py` pass against factory output.
- [ ] `ManifestRecord.from_json(factory.to_json())` round-trips, and `content_hash()` is
      stable.
- [ ] A deliberately invalid record (unknown rights / bad hash / missing null field) is
      **rejected**.
- [ ] With `ornix-tts` uninstalled, the build **fails** — it does not fall back.
- [ ] `loader.py` reconstructs every record from `manifest.jsonl`.

---

### Phase P — Split

- **Estimate:** 2 d · **Milestone:** M4 · **Depends on:** M, N, O · **Blocks:** Q

**Objective.** Leakage-safe, order-independent splits produced by the downstream
implementation.

**Deliverables**

```text
src/ornix_data/ornix/split.py
splits/{train,validation,test}.ids
```

**Key constraints**

- Call `ornix.data.assign_splits` / `validate_no_train_eval_leakage`. Do not reimplement.
- The factory's duplicate groups are contributed as an **extra group key** on top of upstream
  grouping.
- Because splits are **not incrementally stable** upstream (`split.py:223-226`), a corpus
  growth triggers a full re-run and a re-published `evaluation_split_identity()`.
- `protect_normalized_text` is only meaningful with ADR 0004 honoured.
- The factory's own leakage report adds the **validation↔test** dimension, which upstream does
  not check.

**Exit criteria**

- [ ] Identical split membership under forward, reversed and shuffled input order.
- [ ] Speaker leakage, conversation leakage, exact-audio leakage and text leakage are each
      detected by a fixture.
- [ ] Two runs with identical revisions, policy, seed and code produce identical membership.
- [ ] A duplicate group cannot span train and test.

---

### Phase Q — Release builder

- **Estimate:** 4 d · **Milestone:** M5 · **Depends on:** O, P · **Blocks:** R

**Objective.** A release that is complete, checksummed, reader-capable and honestly labelled.

**Deliverables**

```text
src/ornix_data/ornix/release.py
src/ornix_data/storage/parquet.py
release/{dataset.json,manifest.jsonl,manifest.parquet,checksums.sha256,audio/,splits/,reports/}
```

**Port from:** `exporters/manifest.py` (145 LOC) — including its load-bearing ordering comment
at `:118-121` (*"a stale `RELEASE_READY.json` from a previous run must not be hashed and then
overwritten"*). That ordering bug class is worth inheriting the fix for.

**Key constraints**

- Audio stored **once** (48 kHz view). Splits are id lists, not directories.
- `checksums.sha256` is written **after** the readiness marker.
- `manifest.parquet` is a mirror: re-hashing its canonical rows must reproduce the JSONL line
  hashes.
- `reports/review.json` ships the `REVIEW` queue — an empty review set is a fact worth
  recording, not an omission.
- `dataset.json` is `DatasetEntry`-shaped for future registry registration, which does **not**
  block the release.
- **The release is not labelled READY if any mandatory gate failed.**

**Exit criteria**

- [ ] `checksums.sha256` verifies every file, including audio.
- [ ] Rebuilding from the same inputs yields an identical release.
- [ ] Parquet and JSONL hash back to the same logical records.
- [ ] No `REVIEW`, `REJECT`, `BLOCKED` or `DUPLICATE` record appears in `manifest.jsonl`.
- [ ] A `REVIEW`-only run produces a release with zero manifest rows and a non-empty
      `review.json` — and is not labelled READY.

---

### Phase R — Release verifier

- **Estimate:** 3 d · **Milestone:** M5 · **Depends on:** Q · **Blocks:** S, T

**Objective.** Independent verification of a built release before anything is published or
deleted.

**Deliverables**

```text
src/ornix_data/ops/verify.py   (or ornix/release.py verification half)
```

**Key constraints**

- Every referenced audio artifact is checked, not sampled.
- Orphan files, dangling references and duplicate ids are all failures.
- Rights are re-checked from the release contents, not trusted from the build.
- Leakage is re-verified from the published split files.
- The verifier shares no state with the builder — a bug in the builder must not be able to
  certify its own output.

**Exit criteria**

- [ ] A tampered audio file fails verification.
- [ ] A dangling `audio_uri` fails.
- [ ] An extra unreferenced file in `audio/` fails.
- [ ] Re-verification is independent of the build process.

---

### Phase S — Publisher

- **Estimate:** 3 d · **Milestone:** M5 · **Depends on:** R · **Blocks:** T

**Objective.** Upload, then prove the remote matches, then and only then allow cleanup.

**Deliverables**

```text
src/ornix_data/publishing/huggingface.py
```

**Port from:** `publishing/` (638 LOC, all four modules) — `verification.py`, `approval.py`,
`hf.py`, `incremental.py`. The strongest package after `ingestion/`.

**Key constraints**

- The sequence is fixed: build → local verify → upload → remote inventory → remote checksum
  verify → mark VERIFIED → optional cleanup.
- Remote verification compares the **exact file set**. An extra remote file is a failure
  (`publishing/verification.py:63-68`).
- **Never: upload → assume success → delete local.**

**Exit criteria**

- [ ] A failed upload leaves local artifacts intact and the release un-VERIFIED.
- [ ] A remote checksum mismatch marks the release FAILED and blocks cleanup.
- [ ] An extra remote file is detected.

---

### Phase T — Verified cleanup

- **Estimate:** 1 d · **Milestone:** M5 · **Depends on:** S · **Blocks:** —

**Objective.** Reclaim workspace space without ever losing the ability to reproduce.

**Deliverables**

```text
src/ornix_data/ops/cleanup.py
```

**Key constraints**

- Cleanup is permitted **only** after remote verification recorded `VERIFIED`.
- The native master is re-derivable from raw + resample recipe; raw is **not** deleted by a
  default policy.
- Dry-run by default; `--execute` required.
- Every deletion is recorded in `uploads`/`events` before it happens.

**Exit criteria**

- [ ] Cleanup refuses to run on a non-VERIFIED release.
- [ ] Cleanup is idempotent and records what it removed.
- [ ] After cleanup, the release still verifies remotely.

---

## 3. Critical path and parallelisable work

**Critical path:** `A → B → D → E → F → H → I → L → M → N → O → P → Q → R → S → T`

Everything else (C, G, J) can proceed in parallel with its neighbour once its dependency is
green.

**Highest-risk items on the path**

| Phase | Risk | Why it is the risk |
|---|---|---|
| **O** | Compatibility surface changes | Ornix-TTS is a moving target; `MANIFEST_SCHEMA_VERSION`, `QUALITY_VECTOR_REVISION` and `WAVEFORM_SAMPLE_RATE_HZ` are all live. A bump breaks the release contract. |
| **K** | Boundary detector accuracy | A false-negative here ships clipped audio into training. This is the failure generic MOS metrics miss entirely. |
| **I** | ASR on Vietnamese | CER/WER behaviour on tonal, diacritic-heavy text is not a solved problem. Threshold policy must be conservative. |
| **J** | pyannote credentials | A gated provider that is permanently unavailable turns a declared gate into a permanent `REVIEW` — the legacy failure mode. |
| **D** | HF rate limits / gated datasets | Inventory and download can fail on authorisation, not just network. |

**Mitigation for O:** pin `ornix-tts` to an exact version in `uv.lock`, record the resolved
`ornix-tts` version and git SHA in every release's `dataset.json`, and make the compatibility
suite a **mandatory** CI job rather than a nightly one.

---

## 4. Cross-cutting requirements

These apply to every phase and are verified in every phase's CI:

| Requirement | Enforced by |
|---|---|
| `ruff` + `mypy --strict` | CI, every push |
| No local `ManifestRecord` | static test |
| No local resampler | static test (ADR 0002) |
| No local window segmentation | static test (ADR 0006) |
| No `use_record_text=True` | static test (ADR 0004) |
| No sequential id allocation | static test (ADR 0007) |
| No normalisation/denoise on any path | static + signal-identity test (ADR 0008) |
| Every gate names a reachable evidence producer | provider reachability test (ADR 0004) |
| Every provider writes `model_revision` | provider metadata test |
| Compatibility suite green | mandatory CI job (ARCHITECTURE §34) |

---

## 5. Definition of done for a phase

A phase is `done` when **all** of:

1. Every exit criterion above is green in CI.
2. `ruff`, `mypy --strict`, `pytest unit`, `pytest integration` pass.
3. `pytest compatibility` passes **or** the phase is explicitly marked as not-yet-compatible
   in `MEMORY.md` with a reason. It may never be silently skipped.
4. New behaviour has a test that would fail if the behaviour were removed.
5. `MEMORY.md` records: what completed, what did not, the verified commit SHA, the latest test
   evidence, and the next unblocked action.
6. No ADR was violated. If one was, a new ADR supersedes it — the violation is never left
   implicit.

---

## 6. What is deliberately not on the roadmap

| Not planned | Why |
|---|---|
| A UI or web dashboard | Spec §36: *"Do not start by building UI."* |
| Registry registration as a release gate | Upstream registry is unwired (ANALYSIS §9) |
| Near-duplicate **deletion** | Spec §16: evidence first, never silent removal |
| `text_normalized` population | Owned by Ornix-TTS (ADR 0004) |
| Any model training, inference, phonemisation | Non-goals (ARCHITECTURE §2) |
| A migration command for the legacy repo's releases | The old 24 kHz / six-field releases are not valid Ornix inputs; converting them would launder obsolete data |

---

## 7. Immediate next actions

The first three tasks, in order, for the next session:

1. **Phase A, task 1** — scaffold `pyproject.toml` with `ornix-tts` as a non-optional
   dependency, `src/ornix_data/`, and confirm `from ornix.data import ManifestRecord,
   Provenance` imports in a bare environment. If this fails, the whole compatibility strategy
   is at risk and that is the finding to report.
2. **Phase A, task 2** — `contracts/decision.py` with `DecisionState` and the total
   `to_ornix_status()` projection, plus its parametrised test. This is the smallest unit that
   proves ADR 0003 and it blocks the schema work.
3. **Phase A, task 3** — `config/models.py` + `loader.py` with `extra="forbid"`, and the
   reference-constant import block, so no constant is ever re-declared locally.

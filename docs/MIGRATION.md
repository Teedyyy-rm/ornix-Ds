# Migration — from `ornix-dataset`

> **Status:** normative execution plan for reusing proven code from the predecessor repository
> at `~/projects/ornix-dataset` (branch `main`, 95 files, ~11,421 LOC, 324 tests).
>
> **This is not a directory rename.** Each retained module is revalidated against
> `ARCHITECTURE.md`. Each dropped module is dropped for a stated reason, not by inertia.
>
> **On line references:** every `file:line` below was read from the legacy source through the
> code graph at branch `main` on 2026-09-29. If the legacy repo moves, treat the **symbol
> names** as authoritative and re-derive the line numbers.

---

## 1. Headline

| Verdict | Volume | Content |
|---|---|---|
| **Port** | ~4,000 LOC (35%) | downloader + backpressure + circuit breaker, immutable staging, fail-closed rights, resource reservation, dedup union-find + LSH, policy engine, split, checkpoint, cache, calibration, audit, util, remote verification, manifest build, `canonical/bridge.py` shape |
| **Port the property, rewrite the code** | ~800 LOC | all detector adapters, segmentation, `contracts/enums.py`, ~100-120 of 324 tests |
| **Drop** | ~924 LOC | the six-field schema, sequential `Ornix_<n>` identity, AudioFolder layout, the 24 kHz render path, the dead CER module, superseded ops modules, and every test encoding those assumptions |

**The 35% that ports contains the genuinely hard engineering** — bounded concurrency,
backpressure, circuit breaking, immutable staging, fail-closed rights, resource reservation,
dedup union-find, remote verification. Rewriting those from scratch would be a regression.

---

## 2. File-by-file matrix

### 2.1 `ingestion/` — **KEEP** (1 file dropped)

| File | LOC | Verdict | Notes |
|---|---|---|---|
| `ingestion/hf_downloader.py` | 884 | **PORT** | The single best-engineered file in the repo. `_ByteBudget` backpressure, `_AdaptiveGate` circuit breaker, immutable staging, hard caps, durable journal, honest metrics. Port + revalidate, do not "clean up" during the port. |
| `ingestion/hf.py` | 179 | **PORT** | Pinned-SHA adapter, immutable staging, probe provenance patching. |
| `ingestion/permissions.py` | 67 | **PORT** | Model of fail-closed rights logic. Correct as written. |
| `ingestion/base.py` | — | **PORT** | Adapter seam. |
| `ingestion/local.py` | 127 | **DROP** | Exists only to feed a `local` source type used by pilot configs. The new design is HF-centric. |

Target: `src/ornix_data/acquisition/{downloader,staging,hashing}.py`,
`src/ornix_data/sources/{base,huggingface}.py`.

**Behaviour tests to port unchanged** (they are about correctness, not about 24 kHz):

- `tests/unit/test_hf_downloader.py` (27 tests) — including
  `test_T1_files_download_truly_concurrently` (`:139-147`), which uses a `threading.Barrier`
  to *prove* overlap rather than assert it, and `test_T16_single_worker_reproduces_sequential`
  (`:587-594`).
- `tests/unit/test_hf_materialize.py:30-96` — immutable staging bound to content SHA, mismatch
  rejection, probe patching.

### 2.2 `ops/` — **KEEP** (2 files dropped)

| File | LOC | Verdict | Notes |
|---|---|---|---|
| `ops/checkpoint.py` | 50 | **PORT** | Small, correct, reusable. |
| `ops/cache.py` | 52 | **PORT** | Content cache. |
| `ops/env.py` | 86 | **PORT** | dotenv. |
| `ops/queue.py` | 29 | **DROP** | Superseded by the downloader's own pool; not called by the downloader path. |
| `ops/retention.py` | 39 | **DROP** | Job taken over by the new `ops/cleanup.py`, which has far stronger proof obligations. |

### 2.3 `contracts/` — **REWRITE**

| File | LOC | Verdict | Reason |
|---|---|---|---|
| `contracts/enums.py` | 115 | **PORT THE IDEA** | The `MeasurementStatus` / `DecisionState` distinction is excellent. Re-scope. The 12-state `RunState` machine (`:98-113`) is not used by the new pipeline. |
| `contracts/quality.py` | ~180 | **REWRITE** | `QualityEvidence` has 40+ fields (`:40-79`) that are now split across the master, the 16 k analysis view and the 48 k Audio-VAE view. |
| `contracts/source.py` | ~60 | **REWRITE** | Versioned typed source records survive; the schema does not. |
| `contracts/release.py` | ~60 | **REWRITE** | `validate()` hard-asserts 24 kHz (`:62`) and `PCM_S16LE`. Replaced by `ornix.data.ManifestRecord`. |

### 2.4 `detectors/` — **split verdict**

| File | Verdict | Notes |
|---|---|---|
| `detectors/base.py` (111) | **PORT** | Provider protocol + `_Registry`; already separates `is_heuristic` (`:35`) and derives availability from the adapter, never from config (`config.py:104-110`). This is the shape of `providers/base.py`. |
| `detectors/_providers.py` (66) | **PORT** | Solves per-model CPU fallback. |
| `detectors/model_server.py` (59) | **PORT** | Avoids re-paying ONNX load per chunk. |
| `detectors/vad.py` | **REWRITE** | Silero at 16 kHz survives, but `AdapterInfo.model_revision` is **never populated** (`:118-125`; only `energy` sets it at `:44-46`). Rebuilt to conform to `ornix.data.segmentation.VADProvider` and to actually write the revision. **Preserve the 576-sample context contract** (`:127-142`). |
| `detectors/quality.py` | **REWRITE** | DNSMOS adapter; keep the `UNKNOWN`-not-zero behaviour. |
| `detectors/music_noise.py` | **REWRITE** | **Delete the duplicated `_resample_to` (`:159-171`)** — it is a verbatim copy of `dsp/resample.py:18-38` and is imported privately across modules by `detectors/vad.py:145`. All resampling goes through `ornix.audio`. (ADR 0002) |
| `detectors/speaker.py` | **REWRITE** | The provider concept is right; the implementation is permanently `UNAVAILABLE` (`:33-45`). Ship a real credentialed provider or declare the gate off. |
| `detectors/windowing.py` | **DROP** | Superseded by upstream `seeded_window_segments`. (ADR 0006) |

### 2.5 `dsp/` — **REWRITE** (1 file dropped, resampling removed)

| File | LOC | Verdict | Notes |
|---|---|---|---|
| `dsp/features.py` | 114 | **PORT** | `signal_stats` is measurement, not mutation. `clip_ratio` at `>= 0.997` (`:31-45`) must be reconciled with upstream `QualityVector`'s `|x| >= 1.0` (`quality.py:187`). |
| `dsp/technical.py` | 237 | **PORT** | Technical gate. `canonical_nyquist_hz: float = 12000.0` (`:36`) is the 24 kHz Nyquist used as a **bandwidth reference**, not a rate — re-express against the measured bandwidth. |
| `dsp/admission.py` | 169 | **REWRITE** | The honest-admission logic is right and valuable; the 24 kHz/22.05 kHz constants (`:65-66`) are not. |
| `dsp/decode.py` | 129 | **REWRITE** | `soundfile` + `ffmpeg` subprocess → **TorchCodec**. **Delete the `or 24000` fallback (`:102`)** — inventing a rate is the anti-pattern (ADR 0008 §8.2). Keep the `except Exception: pass` + returned decoder-name pattern (`:90`) for provenance, but restructure so an unsupported container is distinguishable from a decoder error. |
| `dsp/resample.py` | 44 | **DELETE** | Replaced by `ornix.audio`. (ADR 0002) Also drops the silent `np.interp` → `"linear-degraded"` degradation path (`:18-38`). |
| `dsp/render.py` | 162 | **DROP** | Exists solely to emit a 24 kHz mono PCM16 artifact. Its fail-closed gate (`:123-127`) and its clip-counting quantiser (`:55-61`) are good patterns; the render target is not. |
| `dsp/audio.py` | — | **PORT** | `AudioBuffer` shape. Re-express as `ornix.contracts.AudioTensor`. |

### 2.6 `curation/` — mostly **KEEP**

| File | LOC | Verdict | Notes |
|---|---|---|---|
| `curation/dedup.py` | 96 | **PORT + EXTEND** | Union-find with path compression (`:73-96`) and LSH candidate generation (`:47-70`, `n_planes=16, n_tables=8`) are correct and proven. Add levels 4-5 as evidence. |
| `curation/policy.py` | 243 | **PORT** | Pure, deterministic, versioned decision engine. **Preserve the never-auto-pick-a-threshold rule (`:45-48`).** |
| `curation/split.py` | 48 | **REPLACE** | Superseded by upstream `assign_splits` (ADR — `split.py` there is 48 LOC of hash-bucketing). The factory calls upstream and adds duplicate groups. |
| `curation/segmentation.py` | 121 | **PORT THE IDEA, REWRITE** | Keep the `uncertain_indices → re-verify transcript` contract (`:74-121`). Replace the energy-trough heuristic (`:25-46`) with real boundary detection — an RMS-minimum heuristic cannot detect a cut vowel, which is the primary failure. |
| `curation/review.py` | 44 | **PORT** | Trivially reusable; becomes `ops/review.py`. |
| `curation/transcript.py` | 53 | **REWRITE ENTIRELY** | `transcript_match_status` (`:40-52`) has **zero callers**; no ASR exists anywhere in the repo. A gate that cannot fail is a defect. |

### 2.7 `publishing/` — **KEEP** (strongest after `ingestion/`)

| File | LOC | Verdict | Notes |
|---|---|---|---|
| `publishing/verification.py` | — | **PORT** | Exact **set** comparison, not a subset; `EXTRA_REMOTE_FILE` is a failure (`:63-68`). Keep this exactly. |
| `publishing/hf.py` | — | **PORT** | Staged publisher. |
| `publishing/approval.py` | — | **PORT** | Approval receipts. |
| `publishing/incremental.py` | — | **PORT** | Content-addressed push ledger (`:14-21`). |

### 2.8 `exporters/` — **mixed**

| File | LOC | Verdict | Notes |
|---|---|---|---|
| `exporters/manifest.py` | 145 | **PORT** | `build_release()` (`:36-131`) validates every row, re-hashes every file against `audio_sha256`, and writes the readiness marker **before** `MANIFEST.sha256` with the ordering comment at `:118-121`. That bug class is worth inheriting the fix for. |
| `exporters/verify.py` | 101 | **REWRITE** | Asserts `SR_NOT_24K` (`:62`), duplicated from `canonical/verify.py:48`. Re-verify structure, drop the rate assertion — the new verifier checks the **declared** rate against the policy. |
| `exporters/card.py`, `parquet.py` | — | **PORT** | Dataset card and Parquet mirror. Drop the AudioFolder loading instructions from the card. |

### 2.9 `canonical/` — **DROP the contract, KEEP the mechanics**

| File | LOC | Verdict | Reason |
|---|---|---|---|
| `canonical/bridge.py` | 122 | **KEEP THE SHAPE** | A clean adapter, and the natural seam for `ornix.data.ManifestRecord`. Becomes `ornix/bridge.py`. |
| `canonical/verify.py` | 126 | **KEEP THE SHAPE** | The verify structure (orphan / dangling / duplicate / speaker-leak / duration-mismatch, fail-closed) is right. Strip the 24 kHz assertion (`:48`). |
| `canonical/schema.py` | — | **DROP** | `CANONICAL_FIELDS` (`:24`) and the `audio == file_name` invariant (`:108-110`, required only for AudioFolder). Fully obsolete. |
| `canonical/identity.py` | — | **DROP** | Sequential `Ornix_<n>` allocation and the `flock` (`:26-27`) that guarded it. Both disappear with content-derived identity. (ADR 0007) |
| `canonical/layout.py` | — | **DROP** | AudioFolder layout. |
| `canonical/loader.py` | — | **REPLACE** | Its 6-field AudioFolder loader is obsolete — **but the underlying need survives** as `ornix/loader.py`, the manifest reader upstream does not provide. (ARCHITECTURE §8.4) |
| `canonical/normalize.py`, `card.py`, `publish.py` | — | **DROP / SPLIT** | Normalisation is owned by Ornix-TTS; card/publish split into `exporters/` and `publishing/`. |

### 2.10 `campaign/` — **REWRITE** (largest subsystem, 2,944 LOC)

`campaign/` is a genuine orchestration engine, not a toy. `campaign/resources.py` (301 LOC)
— a reservation ledger with a hysteresis watermark gate — is production-grade and must be
mined. Everything else is entangled with the 24 kHz / six-field release contract at every QC
boundary, and its state model is JSON-per-entity, which the SQLite layer replaces outright
(ADR 0007).

| File | Verdict |
|---|---|
| `campaign/resources.py` (301) | **MINE** — reservation ledger, hysteresis watermark gate |
| `campaign/store.py`, `models.py`, `planning.py`, `preflight.py`, `processing.py`, `downloading.py`, `publishing.py`, `cleanup.py`, `report.py`, `refs.py`, `parquet.py` | **REWRITE** against the SQLite state model |

### 2.11 `calibration/`, `audit/`, `testing/`, `util/` — **KEEP**

| File | LOC | Verdict | Notes |
|---|---|---|---|
| `calibration/` (4 files) | 252 | **PORT** | Gold-set FAR/FRR runner, leakage refusal, metrics. Directly useful for binding policy thresholds that the engine never auto-picks. |
| `audit/` (3 files) | 89 | **PORT** | Append-only JSONL event log, reports. |
| `util/` (5 files) | 196 | **PORT** | `hashing.py`, `io.py` (atomic write still needed for non-state files), `jsonl.py`, `timeutil.py`. |
| `testing/fakes.py` | 185 | **PORT MINUS ONE** | `FakeNet` / `FakeAnalyzer` / `FakeHub` doubles are valuable. Drop `accepted_row` (`:177` hardcodes `"sample_rate": 24000`). |
| `version.py` | 12 | **PORT** | `SCHEMA_VERSION` / `ANALYZER_VERSION` constant pattern. |

### 2.12 `cli.py`, `config.py`, `pipeline.py` — **REWRITE**

| File | LOC | Verdict | Notes |
|---|---|---|---|
| `cli.py` | 970 | **REWRITE** | 14 commands across 3 competing trees (`{sources,ingest,qc,review,curate,calibrate,release,publish}`, `{campaign × 15}`, `{canonical × 5}`), each with its own state model, build, publish and verify. Collapses to the 8-verb UX — which the SQLite layer is what makes possible. |
| `config.py` | 154 | **REWRITE (thin)** | Keep the `build_detectors` assembly shape and the "availability derived from the adapter, never from config" rule (`config.py:104-110`). |
| `pipeline.py` | 781 | **REWRITE** | `OrnixPipeline` against the P0-P17 stage model. Delete the `24000`/PCM16 release-row construction (`:553`). |

---

## 3. Test migration

46 files, 324 tests. **~100-120 portable; ~200 coupled to the obsolete contract.**

### 3.1 Port as-is (behaviour is rate- and schema-independent)

| Test | Why it survives |
|---|---|
| `test_hf_downloader.py` (27) | Concurrency, backpressure, caps, journal, reproducibility |
| `test_hf_materialize.py` | Immutable staging bound to content SHA |
| `test_curation.py:71-81` | `test_lsh_dedup_matches_bruteforce_at_scale` — **the single best test in the legacy repo** |
| `test_detectors.py:18-28` | `test_licensed_adapters_fail_closed`, `test_dnsmos_returns_unknown_not_zero` |
| `test_campaign_rights.py:74-92`, `test_release_rights.py:48-86` | Rights gates: train-only vs public target enforcement |
| `test_no_split.py` (3) | The `ORNIX_NO_SPLIT` invariant |
| `test_planner.py:50-66` | `test_streaming_admit_release_never_exceeds_caps` |
| `test_parquet_qc.py:130-178` | One shard resident at a time; resident shards bounded by verify workers |
| `test_release_rebuild.py:45-67` | `test_rebuild_release_still_verifies` |
| `tests/acceptance/*` (9) | CLI e2e, release publish |

### 3.2 Port the property, drop the assertion values

| Test | Property | Obsolete assertion |
|---|---|---|
| `test_canonical_ids.py:22-29` `test_sequential_allocation_in_order` | Retry re-uses identity, no gaps | `== "Ornix_0000001"` |
| `test_canonical_ids.py:32-36` `test_retry_reuses_id_without_advancing_counter` | Retry idempotence | counter arithmetic |
| `test_render_verify.py` (all) | Round-trip verifies | 24 kHz / mono / PCM16 |

Retry-idempotence is genuinely valuable and is fully preserved by content-derived identity
(ADR 0007 §8) — port the property, discard the values.

### 3.3 Drop

| Test | Reason |
|---|---|
| `test_canonical.py:57-70` `test_t1_metadata_exactly_six_fields_and_types` | Six-field schema is retired |
| `test_canonical.py:261-274` `test_t14_provenance_preserved_internally_and_not_public` | Six-field split |
| `test_canonical_e2e.py:327-357` `test_canonical_loader_vs_hf_audiofolder` | AudioFolder contract |
| `test_canonical_e2e.py:54-82`, `test_pipeline.py:29-38` | e2e at 24 kHz |
| `test_admission.py:29-96` | 24 kHz identity / fake-upsampled-container |
| `test_infra.py:58-80` | 24 kHz render roundtrip |

### 3.4 The fixture problem — do this first

`tests/fixtures/synth.py:19-33` (`speechlike`) and `tests/conftest.py:16-42` (`clean_wav`,
`pilot_corpus`) **all hardcode 24 kHz**, and `synth.py` is the base for ~54 test files.

**Porting tests means porting the fixture first**, parameterised by rate. Until the fixture is
parameterised, no ported test is meaningful, and a ported test that still assumes 24 kHz will
fail in a way that looks like a new bug.

The new fixture set must cover, at minimum: native, 48 k, 16 k, 8 k, 22.05 k, 44.1 k;
mono and stereo; clipped; low-bandwidth; cut vowel; missing initial consonant;
near-silent; NaN/Inf-bearing; oversized-file; multi-channel; and Vietnamese text with full
diacritics.

---

## 4. Migration order

Migration is folded into `docs/ROADMAP.md` phase by phase, but the sequence is:

1. **Fixture first** — parameterise the synth fixture by rate and add the new boundary/bandwidth
   fixtures. Nothing else can be ported honestly before this.
2. **Port the hard parts untouched** — `hf_downloader.py`, `permissions.py`, `hf.py`,
   `checkpoint.py`, `cache.py`, `util/`, `audit/`, `calibration/`. Do not modify during the
   port; modify after, in their own commit, with tests.
3. **Mine `campaign/resources.py`** and `canonical/{bridge,verify}.py` for shape only.
4. **Rewrite** detectors, dsp, curation/transcript, campaign, cli, config, pipeline against the
   new contracts.
5. **Drop** the obsolete modules, and delete the legacy tests that encode the retired contract
   in the same commit that removes the code they test.

---

## 5. What must not be migrated, under any circumstance

- Any `24000` literal, or any assertion that a release is 24 kHz.
- The six-field `CANONICAL_FIELDS` schema or the `audio == file_name` invariant.
- `AudioFolder` layout, loader, or dataset-card instructions.
- Sequential `Ornix_<n>` identity or the `flock` that guarded it.
- The silent `np.interp` → `"linear-degraded"` resample path.
- `sr = info.get("sample_rate") or 24000` — inventing a rate.
- Any second `_resample_to` (the legacy duplication at `detectors/music_noise.py:159-171`).
- The dead `transcript_match_status` call path.
- Any gate that cannot fail because its evidence producer is unreachable.

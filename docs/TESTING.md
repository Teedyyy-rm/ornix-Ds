# Testing — strategy and matrix

> **Status:** normative. Every acceptance criterion in `ARCHITECTURE.md` §38 and every clause
> in every ADR maps to a test here. A clause with no test is a preference, not a rule.
>
> **Layers:** `unit` · `integration` · `compatibility` · `acceptance`
>
> **CI gate (mandatory, `ARCHITECTURE.md` §34):** `ruff` · `mypy --strict` · `pytest unit` ·
> `pytest integration` · `pytest compatibility` · `build` · `lockfile check`.
>
> **This repository may be green internally and MUST NOT claim release compatibility if the
> compatibility suite fails.**

---

## 1. Layer definitions

| Layer | Runs on | Scope | May require |
|---|---|---|---|
| `unit` | every push | pure functions, contracts, policies, no I/O | nothing |
| `integration` | every push | real codecs, real files, real SQLite, real local HTTP | FFmpeg, a workspace |
| `compatibility` | every push | the actual `ornix.data` contract + upstream test suites | `ornix-tts` installed |
| `acceptance` | merge to main + nightly | full pipeline end to end, crash injection, remote verify | credentials, network, an HF repo |

`compatibility` is **not** optional and **not** nightly. It is the entire point of the
repository.

---

## 2. Static / structural tests

These encode the architectural invariants. They are cheap, deterministic, and catch the exact
regressions that produce a plausible-looking but wrong release.

| Test | Asserts | ADR |
|---|---|---|
| `test_no_local_manifest_record` | No dataclass in the factory mirrors `ManifestRecord` | 0008 §8.5 |
| `test_no_local_resample_implementation` | No `scipy.signal.resample_poly` call in the factory | 0002 |
| `test_no_local_window_segmentation` | No window arithmetic; `seeded_window_segments` is called | 0006 |
| `test_no_use_record_text_true` | No `use_record_text=True` anywhere in `src/` | 0004 |
| `test_no_sequential_id_allocation` | No counter/sequence in the identity path | 0007 |
| `test_no_torchaudio_media_io` | The deprecated media backends are never imported | §5 |
| `test_no_normalisation_or_denoise` | No peak-normalise, loudness, denoise, spectral-gate path | 0008 §8.3 |
| `test_every_gate_names_a_reachable_provider` | No gate whose evidence producer is dead code | 0004 §6 |
| `test_every_provider_writes_model_revision` | No declared-but-unwritten revision field | §3.1 |
| `test_no_reference_to_gender_age_identity` | No such code path exists | §11 |

---

## 3. Mandatory test matrix

### 3.1 Decode and audio integrity

| Test | Layer | Asserts |
|---|---|---|
| `test_decode_known_fixtures` | integration | Every fixture decodes at its declared rate |
| `test_decode_failure_on_missing_sample_rate` | integration | A file with no declared rate **fails**. Not `or 24000` |
| `test_decode_failure_on_corrupt_container` | integration | Corrupt input raises, does not yield zeros |
| `test_nan_inf_rejected` | unit | Non-finite output is rejected |
| `test_sample_rate_metadata_validation` | unit | Manifest rate matches the decoded rate |
| `test_duration_exactness` | unit | Duration is exact to the sample, with a stated rounding rule |
| `test_validate_audio_metadata_consistency_b1_only` | compatibility | The `np.max(lengths)` quirk is avoided by `B == 1` |
| `test_channel_policy_explicit` | unit | Multi-channel is a policy decision, never an implicit downmix |
| `test_source_immutability` | integration | Nothing downstream writes to `raw/` |
| `test_audio_tensor_validates` | compatibility | `ornix.audio.validate_audio_tensor` passes for every decoded item |

### 3.2 Views and resampling

| Test | Layer | Asserts |
|---|---|---|
| `test_resampling_determinism` | unit | Two runs → byte-identical views |
| `test_resampling_alias_rejected` | unit | Content above the anti-alias cutoff is attenuated, not folded |
| `test_resample_recipe_records_downstream_revision` | unit | `implementation_revision == ornix.audio.RESAMPLER_VERSION` |
| `test_view_length_matches_downstream_rounding` | compatibility | Matches `ornix.audio._target_length` across the full rate table |
| `test_low_bandwidth_source_not_labelled_hq` | acceptance | A narrowband source upsampled to 48 k is `REJECT` on bandwidth evidence |
| `test_views_are_reproducible` | integration | Same input + same revision → same view bytes |

### 3.3 Evidence and fail-closed semantics

| Test | Layer | Asserts |
|---|---|---|
| `test_vad_provider_unavailable_yields_review` | unit | `UNAVAILABLE` → `REVIEW`, not `PASS`/`ACCEPT` |
| `test_asr_provider_unavailable_yields_review` | unit | Same |
| `test_speaker_provider_unavailable_yields_review` | unit | Same, when the gate is on |
| `test_missing_metric_never_becomes_pass` | unit | An absent metric cannot produce `ACCEPT` |
| `test_unmeasured_metric_is_null_never_zero` | unit | `null` + provider status, never `0.0` |
| `test_detector_outage_is_not_rejected` | unit | An outage is `REVIEW`; only positive evidence is `REJECT` |
| `test_dnsmos_returns_unknown_not_zero` | unit | Ported from the legacy suite |
| `test_licensed_adapters_fail_closed` | unit | Ported from the legacy suite |
| `test_provider_status_enum_complete` | unit | Only `OK`/`UNAVAILABLE`/`ERROR`/`NOT_APPLICABLE` |
| `test_quality_is_vector_not_scalar` | unit | The forbidden `{"quality": 0.91}` shape cannot be produced |
| `test_quality_vector_consumable_by_downstream` | compatibility | `QualityVector.from_dict(record.quality)` succeeds |

### 3.4 Boundary integrity — mandatory for TTS

| Test | Layer | Asserts |
|---|---|---|
| `test_boundary_cut_vowel_detected` | unit | `REJECT`, `boundary_status != OK` |
| `test_boundary_missing_initial_consonant_detected` | unit | Head clip probability above the policy floor |
| `test_boundary_cut_final_syllable_detected` | unit | Tail clip probability above the floor |
| `test_energy_heuristic_alone_is_insufficient` | unit | The fixture the legacy trough heuristic passes is caught here |
| `test_indeterminate_boundaries_yield_review` | unit | Not `ACCEPT` |
| `test_boundaries_are_sample_indices_on_master` | unit | Exact, and identity-stable |
| `test_silero_v5_context_window` | unit | 576 samples/step (64 ctx + 512). **Fails if the context is removed** |

### 3.5 Transcript verification

| Test | Layer | Asserts |
|---|---|---|
| `test_text_raw_byte_identical_to_source` | integration | Every record's `text_raw` matches the source byte-for-byte |
| `test_text_normalized_is_always_null` | unit | The factory never populates it |
| `test_comparison_text_never_reaches_manifest` | unit | It stays in its own field |
| `test_transcript_mismatch_detected` | unit | A mismatched fixture produces a recorded mismatch |
| `test_transcript_mismatch_cannot_reach_accept` | unit | It cannot silently enter `ACCEPT` |
| `test_vietnamese_unicode_preserved` | unit | Diacritics survive extraction, comparison and serialization |
| `test_wer_and_cer_both_computed` | unit | Both present; CER retained for Vietnamese |
| `test_gate_without_producer_fails_build` | unit | The legacy dead-`transcript_match_status` pattern is banned |
| `test_asr_never_authors_text` | unit | No code path writes ASR output into `text_raw` |

### 3.6 Rights, language and provenance

| Test | Layer | Asserts |
|---|---|---|
| `test_unknown_license_is_blocked` | unit | `BLOCKED`, before any download |
| `test_unknown_consent_is_blocked` | unit | Same |
| `test_unknown_language_is_not_guessed` | unit | No inference from filename or path |
| `test_downloadable_ne_equals_commercially_usable` | unit | The three rights fields are independent |
| `test_research_only_policy_is_recorded` | unit | The escape hatch is explicit, never implied by absence |
| `test_provenance_transformations_is_tuple` | compatibility | Upstream requires a `tuple` on construction |
| `test_source_revision_pinned_not_main` | unit | `revision: main` is rejected for production campaigns |

### 3.7 Deduplication

| Test | Layer | Asserts |
|---|---|---|
| `test_exact_duplicate_detected` | unit | Level 1 |
| `test_decoded_content_duplicate_detected` | unit | Level 2 |
| `test_text_duplicate_grouped_with_null_text_normalized` | unit | **Proves ADR 0004** |
| `test_fingerprints_built_only_via_from_record` | static | No direct construction |
| `test_dedup_is_order_independent` | unit | Reversed and shuffled input give the same grouping |
| `test_near_duplicate_produces_evidence_not_deletion` | unit | Nothing is removed |
| `test_canonical_selection_uses_canonical_by_record` | unit | Not `duplicate_ids` (which includes the canonical) |
| `test_lsh_matches_bruteforce` | unit | Ported from the legacy suite |

### 3.8 Identity, grouping and split

| Test | Layer | Asserts |
|---|---|---|
| `test_stable_sample_identity` | unit | Same inputs → same key, across runs and orderings |
| `test_identity_independent_of_acquisition_order` | integration | Downloading in a different order changes nothing |
| `test_speaker_not_merged_across_corpora` | unit | `"spk1"` in two corpora → two identities |
| `test_speaker_leakage_rejected` | unit | A speaker spanning train and eval is a violation |
| `test_conversation_leakage_rejected` | unit | Same |
| `test_audio_leakage_rejected` | unit | Same, via both fingerprint axes |
| `test_text_leakage_rejected` | unit | Same, via the comparison text |
| `test_duplicate_group_cannot_span_splits` | unit | Factory duplicate groups feed the split |
| `test_split_deterministic_under_input_reorder` | unit | Forward / reversed / shuffled give identical membership |
| `test_split_evaluation_identity_reproducible` | unit | Same policy + seed + revisions → same identity |
| `test_validation_test_mixing_is_reported` | unit | Upstream does not check this; the factory does |

### 3.9 Manifest and compatibility

| Test | Layer | Asserts |
|---|---|---|
| `test_manifest_record_compatibility` | compatibility | Every record constructs through `ornix.data.ManifestRecord` |
| `test_manifest_schema_version_from_constant` | compatibility | Read from `MANIFEST_SCHEMA_VERSION`, never hard-coded |
| `test_all_seventeen_fields_serialized_with_explicit_nulls` | compatibility | `from_dict` requires them |
| `test_hashes_all_sha256_hex` | compatibility | No escape hatch |
| `test_quality_all_finite_json` | compatibility | `_validate_json_value` passes |
| `test_release_rate_matches_downstream_constant` | acceptance | `== ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ` |
| `test_require_known_rights_passes` | compatibility | Every released record |
| `test_content_hash_stable_across_roundtrip` | compatibility | `to_json` → `from_json` → `content_hash()` |
| `test_vietnamese_diacritics_survive_release` | compatibility | |
| `test_manifest_reader_roundtrips_release` | compatibility | The factory's `loader.py` (§8.4) |
| `test_upstream_test_m1_data_pipeline_passes` | compatibility | **Unmodified upstream suite** |
| `test_upstream_test_m1_2_qualification_passes` | compatibility | **Unmodified upstream suite** |
| `test_build_fails_without_ornix_tts_installed` | compatibility | No silent fallback to a look-alike |

### 3.10 Release, verification, publishing, cleanup

| Test | Layer | Asserts |
|---|---|---|
| `test_release_checksum_verifies` | integration | Every file, including audio |
| `test_parquet_and_jsonl_agree` | integration | Re-hashing the Parquet rows reproduces the JSONL line hashes |
| `test_release_contains_only_accept_records` | unit | No `REVIEW`/`REJECT`/`BLOCKED`/`DUPLICATE` row |
| `test_review_only_run_is_not_ready` | acceptance | Zero manifest rows, non-empty `review.json`, not READY |
| `test_tampered_audio_fails_verification` | integration | |
| `test_dangling_audio_uri_fails` | integration | |
| `test_extra_unreferenced_file_fails` | integration | |
| `test_verifier_independent_of_builder` | unit | No shared state |
| `test_release_rebuild_is_deterministic` | integration | Same inputs → identical release |
| `test_remote_checksum_mismatch_blocks_cleanup` | acceptance | |
| `test_extra_remote_file_detected` | acceptance | Exact set comparison |
| `test_cleanup_requires_verified_release` | acceptance | The `upload → assume success → delete` sequence is impossible |
| `test_cleanup_is_idempotent_and_logged` | integration | |

### 3.11 Resume and determinism

| Test | Layer | Asserts |
|---|---|---|
| `test_resume_after_crash_at_each_phase` | acceptance | Crash injection at P0..P17; identical output, including identity |
| `test_resume_does_not_duplicate_identity` | acceptance | Manifest ids are a set after resume |
| `test_state_is_authoritative_not_the_filesystem` | integration | Runs are not discoverable by directory scan |
| `test_rolls_back_leaves_no_partial_rows` | integration | |
| `test_release_hash_reproducible` | acceptance | Full pipeline → identical release |

---

## 4. Fixture requirements

The legacy `tests/fixtures/synth.py` hardcodes 24 kHz and is the base for ~54 test files.
**The fixture set must be ported first**, parameterised by rate.

| Fixture | Requirement |
|---|---|
| Rates | native, 48 000, 16 000, 8 000, 22 050, 44 100 |
| Channels | mono, stereo, multi-channel with a real channel difference |
| Codecs | PCM16, PCM24, FLAC, MP3, Ogg/Vorbis, a container with a mislabelled rate |
| Defects | clipped, low-bandwidth, near-silent, NaN/Inf-bearing, truncated, oversized |
| **Boundaries** | cut vowel, missing initial consonant, cut final syllable, speech onset at sample 0 |
| **Text** | Vietnamese with full diacritics, numbers, punctuation, mixed script, empty |
| Rights | known license, unknown license, unknown consent, research-only |
| Provenance | same audio at two different source revisions (must produce different identity) |

Every fixture ships a **reference measurement vector** so metric regressions are caught
numerically rather than by threshold.

---

## 5. Coverage expectations

| Area | Minimum |
|---|---|
| `contracts/` | 100% — it is the safety surface |
| `quality/policy.py`, `curation/dedup.py` | 100% — pure decision logic |
| `ornix/bridge.py`, `ornix/split.py` | 100% — the boundary |
| `audio/`, `transcript/`, `quality/` | 90% |
| `acquisition/`, `publishing/` | 85% (network paths covered by fakes + integration) |
| `storage/sqlite.py` | 95% (transaction and constraint logic) |

Branch coverage on `contracts/`, `ornix/` and `quality/policy.py` is a merge gate.

---

## 6. Anti-tests

Tests that exist specifically to catch a documented past failure. Each maps to a real,
specific regression:

| Anti-test | Prevents |
|---|---|
| `test_no_local_resample_implementation` | Re-creating a second resampler under a second version string |
| `test_text_duplicate_grouped_with_null_text_normalized` | Silent loss of text-leakage protection |
| `test_decode_failure_on_missing_sample_rate` | `sr = info.get("sample_rate") or 24000` |
| `test_silero_v5_context_window` | The ~0-on-real-speech VAD failure |
| `test_gate_without_producer_fails_build` | The dead `transcript_match_status` pattern |
| `test_energy_heuristic_alone_is_insufficient` | Shipping a cut vowel the trough heuristic passes |
| `test_no_sequential_id_allocation` | Reintroducing `Ornix_<n>` and its `flock` |
| `test_unmeasured_metric_is_null_never_zero` | `0.0` standing in for "not measured" |
| `test_low_bandwidth_source_not_labelled_hq` | Upsample-and-relabel |
| `test_review_only_run_is_not_ready` | A release labelled READY on zero accepted rows |
| `test_extra_remote_file_detected` | Subset-instead-of-set remote verification |
| `test_verifier_independent_of_builder` | A builder certifying its own output |
| `test_resume_does_not_duplicate_identity` | Identity allocation drifting on retry |
| `test_content_hash_stable_across_roundtrip` | Non-canonical serialization |

---

## 7. Test philosophy

1. **A gate that cannot fail is a defect.** A test that cannot fail is worse — it is a false
   assurance. Every gate names its evidence producer, and a test proves the producer is
   reachable.
2. **Prove, do not assert timing.** The legacy concurrency test uses a `threading.Barrier` to
   *prove* overlap (`:147`). Prefer proof over thresholds everywhere.
3. **Test the property, drop the value.** Legacy tests encode a valuable property in obsolete
   syntax (`test_retry_reuses_id_without_advancing_counter`). Port the property, discard the
   assertion values.
4. **Negative tests are the point.** For every safety rule there must be a test that
   *demonstrates the failure it prevents*, not merely a test that the happy path works.
5. **Fixtures first.** No test is ported honestly until its fixture is rate-parameterised.
6. **The upstream suites are the compatibility oracle.** They run **unmodified**. A fork or a
   patch to make them pass is a compatibility failure, not a fix.

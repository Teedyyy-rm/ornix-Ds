# Operations — runbook

> **Status:** normative operational procedure. Read with `docs/CONTRACTS.md` (the boundary)
> and `docs/adr/` (the rules).
>
> **Audience:** whoever operates a campaign, from a clean machine to a VERIFIED release.

---

## 1. Prerequisites

| Requirement | Version | Source of truth |
|---|---|---|
| Python | `>=3.11` | `ornix-tts` requires `StrEnum` |
| FFmpeg | any supported build | decode path |
| `torch` | `==2.11.0` | `ornix-tts` `pyproject.toml:25-28` |
| `torchcodec` | `==0.16.0` | `ornix.audio.torchcodec.TORCHCODEC_SUPPORTED_VERSION` |
| `ornix-tts` | pinned in `uv.lock` | **non-optional dependency** |

At start-up the factory asserts its `torch`/`torchcodec` versions against
`ornix.audio.torchcodec.TORCHCODEC_SUPPORTED_VERSION` /
`TORCHCODEC_SUPPORTED_TORCH_VERSION` and records the resolved `ornix-tts` version and git SHA
in every run's metadata.

**Extras** are opt-in and never become required gates:

```bash
uv sync --extra detectors     # VAD, ASR, speaker, events
uv sync --extra analytics     # pyarrow, polars, duckdb
uv sync --extra publishing    # huggingface_hub
```

---

## 1a. Resolving `ornix-tts` without writing to it

`ornix-tts` is not on PyPI and `Ornix-TTS` is a **read-only, never-written** checkout
(`ARCHITECTURE.md` §0.3). A path or editable dependency is prohibited because both write
`*.egg-info` and bytecode into the source tree.

### 1a.1 Local bootstrap — copy, build in scratch, install the wheel

```bash
# 1. Snapshot the checkout into scratch, OUTSIDE both repositories.
#    Read-only on the source; nothing is written back.
SCRATCH=/tmp/opencode/ornix-tts-build
rm -rf "$SCRATCH" && mkdir -p "$SCRATCH"
cp -a /home/obito/projects/Ornix-TTS/{src,pyproject.toml,README.md} "$SCRATCH"/
REV=$(git -C /home/obito/projects/Ornix-TTS rev-parse HEAD)
echo "snapshot of Ornix-TTS@$REV"

# 2. Build the wheel IN the scratch copy. Never in the source tree.
cd "$SCRATCH"
python3 -m build --wheel --outdir "$SCRATCH/dist" .

# 3. Install the wheel into THIS repository's environment.
cd /home/obito/projects/ornix-Ds
uv pip install "$SCRATCH"/dist/ornix_tts-*.whl
```

The build is deterministic given the same snapshot. **Record `$REV` in the release metadata**
— it is the contract revision the release was verified against (`ARCHITECTURE.md` §26,
`docs/ROADMAP.md` Phase O).

### 1a.2 Reading the checkout without writing to it

Any direct read must suppress bytecode:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -c "from ornix.data import ManifestRecord"
```

Never `cd` into `/home/obito/projects/Ornix-TTS` to run anything.

### 1a.3 Verifying the boundary holds

```bash
git -C /home/obito/projects/Ornix-TTS status --porcelain    # must be empty
```

Run this after any operation that touches `ornix-tts`. An empty result is the only acceptable
outcome. Note that `__pycache__` is usually gitignored, so a clean `git status` does **not**
prove nothing was written — when in doubt check filesystem mtimes, not git.

### 1a.4 CI

CI resolves `ornix-tts` from an index or an authenticated git source, never from a sibling
checkout. The compatibility suite pins the resolved revision so a contract change fails the
build rather than passing silently (`docs/ROADMAP.md` Phase O, "Mitigation for O").

---

## 2. Workspace layout

```text
workspace/
├── <run-id>/
│   ├── state.db              SQLite — the ONLY authoritative run state   (ADR 0007)
│   ├── raw/<dataset>/<sha256[0:2]>/<sha256>          immutable, read-only
│   ├── master/<sha256[0:2]>/<sha256>                 native-rate decoded
│   ├── views/16k/<sha256>                             analysis view
│   ├── views/48k/<sha256>                             Audio-VAE view (the release)
│   ├── release/                                        built release
│   └── logs/
```

**Rules**

- `raw/` is written once and made read-only. Nothing downstream writes there.
- Everything except `raw/` is content-addressed and re-derivable from `raw/` + recipes.
- The database records artifact **identity**, not location history. Finding an artifact is a
  hash lookup, never a directory walk.
- A run is single-writer. Parallelism is **within** a phase, across source items.

---

## 3. Standard campaign

```bash
# 1. Validate configuration, sources, rights, policies, model lock
ornix-data validate configs/campaigns/<campaign>.yaml

# 2. Run the complete allowed pipeline (P0-P15)
ornix-data run configs/campaigns/<campaign>.yaml

# 3. Inspect state, decisions, evidence
ornix-data inspect <run-id>

# 4. Review queue — adjudicate REVIEW rows
ornix-data qualify <run-id> --export-review

# 5. Build the release
ornix-data build <run-id>

# 6. Verify the release locally
ornix-data verify release/<release-id>

# 7. Publish, then prove the remote matches
ornix-data push release/<release-id>
```

`ornix-data run` executes the **complete allowed pipeline**. A worker MUST NOT stop after
preflight merely because intermediate checks passed (`ARCHITECTURE.md` §19).

### 3.1 Resume

```bash
ornix-data resume <run-id>
```

Resume reads `(phase, status)` from `runs` and re-executes the first incomplete phase. It is
transactionally safe at any point: a crash leaves the run in the last committed phase, never
half-way through one, and never duplicates identity.

---

## 4. Source declaration

```yaml
# configs/sources/<name>.yaml
schema_version: 1
sources:
  - dataset_id: <stable-id>
    type: huggingface
    repo_id: <org>/<name>
    revision: <40-hex-commit-sha>        # MUST NOT be "main" for production
    splits: [train]
    include_patterns: ["**/*.flac", "**/*.wav"]
    rights:
      license: CC-BY-4.0
      consent_scope: COMMERCIAL
      commercial_training: true
      redistribution: true
```

**`revision: main` is rejected for production campaigns.** Resolve it to an immutable commit
SHA first; the SHA is what enters sample identity (`ARCHITECTURE.md` §8, §27).

### 4.1 Rights gate

| Declaration | Result |
|---|---|
| Known license, consent permits the campaign target | proceeds |
| Unknown / missing license or consent | **`BLOCKED`** before any network call |
| Downloadable but not commercially usable | `BLOCKED` for a production campaign |
| `commercial_training: false` | `BLOCKED` unless a research-only policy is configured **and recorded** |

`publicly downloadable` ≠ `commercially usable` ≠ `redistributable`. The three fields are
independent and none is derived from another.

> Upstream `ConsentScope` is documentation, not enforcement — the field is a plain `str` and
> only five tokens are fail-closed (`ornix.data.validation:15-16`). The real policy is enforced
> here.

---

## 5. Model lock

```yaml
# configs/models.lock.yaml
schema_version: 1
vad:     {provider: silero,        model: ..., revision: ..., sha256: ..., runtime: onnxruntime-cpu}
asr:     {provider: faster-whisper, model: ..., revision: ..., sha256: ...}
speaker: {provider: pyannote,      model: ..., revision: ..., sha256: ...}
events:  {provider: panns,         model: ..., revision: ..., sha256: ...}
```

**No runtime "download latest" behaviour** in a reproducible campaign.

Every provider's runtime report must populate `provider_id`, `model_id`, `model_revision`,
`weights_sha256`, `runtime`, `device`, `status`. A revision field that is never written is
worse than no revision field, because it looks like evidence.

### 5.1 Provider status semantics

| Status | Meaning | Policy effect |
|---|---|---|
| `OK` | Measured successfully | evidence used |
| `UNAVAILABLE` | Model/credentials/runtime absent | gate → `REVIEW` |
| `ERROR` | Ran and failed | gate → `REVIEW`, with the error recorded |
| `NOT_APPLICABLE` | Gate not required by policy | ignored |

`UNAVAILABLE` MUST NOT become a fabricated clean result and MUST NOT become `0.0`
(`ARCHITECTURE.md` §3, §14).

---

## 6. Policy

```yaml
# configs/policies/<name>.yaml
schema_version: 1
policy_revision: ornix-ds-policy-v1
required_detectors: [vad, asr]        # explicit; never inferred from availability
thresholds:
  min_vad_speech_ratio: 0.60
  max_clip_fraction: 0.001
  min_snr_db: null                   # unset ⇒ policy error, never a silent pass
  max_asr_cer: 0.25
  max_music_probability: 0.20
  max_head_clip_probability: 0.10
  max_tail_clip_probability: 0.10
  min_effective_bandwidth_hz: 3400
```

**An unset threshold is a policy error, not a default.** The engine never auto-picks a
threshold; thresholds are bound by calibration (`ornix-data calibrate`) or explicitly declared.

---

## 7. Known operational traps

These are API behaviours in the downstream contract that will silently corrupt a release if
missed. Full detail in `docs/CONTRACTS.md`.

| Trap | Rule |
|---|---|
| `validate_audio_metadata_consistency` compares `record.duration_s` against **`np.max(lengths)`** — the longest item in the batch — and has no `item_index` parameter (`validation.py:70-72`) | **Always call it with `B == 1`.** |
| Default tolerance is `tolerance_samples=0.5`, i.e. **half a sample** (~10 µs at 48 kHz) | State the duration rounding rule explicitly. |
| `DedupFingerprint.from_record` defaults to `use_record_text=True`, which selects `record.text_normalized` — always `null` here — so `normalized_text_hash` is `None` and `protect_normalized_text` **silently no-ops** (`dedup.py:71,87`; `split.py:213-215,258-262`) | **Always pass `use_record_text=False` with an explicit comparison text.** (ADR 0004) |
| `DedupFingerprint.__post_init__` validates hashes but **discards the normalised value** (`dedup.py:30-35,53-60`) | Never construct directly; always `from_record`. |
| `DeduplicationResult.duplicate_ids` **includes the canonical** of each group (`dedup.py:183-184`) | Use `canonical_by_record` to decide what to drop. |
| `assign_splits` is order-independent but **not incrementally stable** — `group_key` hashes the whole member list, so one new utterance can flip a speaker's whole component (`split.py:223-226`) | Corpus growth ⇒ full re-run + re-publish `evaluation_split_identity()`. |
| `validate_no_train_eval_leakage` does **not** flag validation↔test mixing (`split.py:273-278`) | The factory adds that dimension. |
| `qualify_records` returns `ACCEPTED` with `quality=None` when no `AudioTensor` is supplied (`qualification.py:531-556`) | Enforce `ACCEPT requires a quality vector` **here**. (ADR 0005) |
| `QualificationConfig.require_known_rights=False` turns `BLOCKED` into `ACCEPTED` | This flag is part of the trust boundary; never set it in production. |
| `ornix-tts` audio errors do not subclass `DataPipelineError`, so `qualify_records` flattens them into `failure_reasons` strings | Read `failure_reasons` strings, never exception types. |
| No sample rate is enforced anywhere upstream | Enforce `== WAVEFORM_SAMPLE_RATE_HZ` here. (ADR 0001) |
| `ornix.data` has **no manifest file loader** | The factory ships `ornix/loader.py`. (ARCHITECTURE §8.4) |

---

## 8. Interpreting a run

```bash
ornix-data inspect <run-id> --phase P9
ornix-data inspect <run-id> --decision REVIEW --format jsonl
ornix-data inspect <run-id> --record <sample-id> --evidence
```

### 8.1 Decision semantics

| Decision | Meaning | In release? |
|---|---|---|
| `ACCEPT` | Every mandatory gate passed **with evidence** | **yes** |
| `REVIEW` | Evidence missing, unavailable or borderline | no (reported) |
| `REJECT` | Available evidence proves failure | no (reported) |
| `BLOCKED` | Rights / provenance / contract prevents use | no (reported) |
| `DUPLICATE` | Usable but removed by dedup policy | no (reported) |
| `PENDING` | Not yet evaluated at this stage | no |

**`REVIEW` means "we could not tell". `REJECT` means "we know."** Collapsing them biases the
corpus toward whatever the available detectors happen to cover.

### 8.2 Triage a `REVIEW` queue

```bash
ornix-data qualify <run-id> --export-review reports/review.json
```

Sort by `missing_evidence`. The usual causes and their responses:

| Cause | Response |
|---|---|
| Provider `UNAVAILABLE` (no credentials) | Provision credentials, or explicitly declare the gate off in policy |
| Provider `ERROR` | Inspect the recorded error; fix or disable the gate |
| Borderline threshold | Adjudicate, or adjust policy **with a version bump** — never per-record |
| Comparison text unavailable | Either send to `REVIEW` or declare the text axis unprotected **in the release metadata** (ADR 0004) |

A run that ends with a non-empty `REVIEW` queue is a **successful run with pending work**, not
a failed run. The release ships the accepted set plus the review report.

---

## 9. Publishing

```text
build → local verify → upload → remote inventory → remote checksum verify
      → mark VERIFIED → optional local cleanup
```

```bash
ornix-data push release/<release-id> --dry-run
ornix-data push release/<release-id> --execute
```

- **Never**: upload → assume success → delete local source.
- Remote verification compares the **exact file set**. An extra remote file is a failure.
- Only a `VERIFIED` release is eligible for cleanup.

---

## 10. Cleanup

```bash
ornix-data cleanup <run-id>                  # dry run
ornix-data cleanup <run-id> --execute --drop views --drop master
```

- Requires a `VERIFIED` release. Refuses otherwise.
- Raw bytes are **not** dropped by any default policy.
- Idempotent; every deletion is recorded in `uploads`/`events` before it happens.
- After cleanup, the release must still verify remotely.

---

## 11. Reproducibility checklist

A release is reproducible when the following are pinned and recorded:

- [ ] Source revisions (commit SHAs, never `main`)
- [ ] Policy revision + config hash
- [ ] `models.lock.yaml` contents (model ids, revisions, weights SHA-256)
- [ ] Code revision (git SHA)
- [ ] `ornix-tts` version + git SHA
- [ ] `ornix.audio.RESAMPLER_VERSION`
- [ ] Split seed + `SPLIT_POLICY_REVISION`
- [ ] `text_compare_normalizer_revision`
- [ ] Seed where randomness is involved (segmentation jitter)

Identical inputs on all of the above ⇒ byte-identical release. Anything else is a
`release_rebuild_is_deterministic` failure.

---

## 12. Incident playbook

| Symptom | First check | Likely cause |
|---|---|---|
| Every record is `REVIEW` | `reports/review.json` → `missing_evidence` | A required provider is `UNAVAILABLE` |
| Every record is `BLOCKED` | `reports/rights.json` | Unknown license/consent, or a production campaign on non-commercial rights |
| Mass decode failures | `events` table | Corrupt containers, or **a missing declared sample rate** (not defaulted) |
| Split membership changed unexpectedly | `evaluation_split_identity` | Corpus grew — splits are not incrementally stable by design |
| `mypy` or compatibility fails after an `ornix-tts` upgrade | `uv.lock` | A contract constant changed. Read `CONTRACTS.md`, amend the affected ADR, do **not** fork the upstream test |
| Release build fails with a compatibility error | `scripts/validate_ornix_tts_compatibility.py` | Expected behaviour. There is **no** fallback to a local schema |
| Zero manifest rows | `reports/review.json` | The run is not READY; the review queue is the deliverable |

---

## 13. Prohibited operations

Never, under any operational pressure:

```text
fabricate a PASS for a missing measurement
replace an unavailable metric with 0.0
default a missing sample rate
edit text_raw
relax a policy threshold for a single record without a policy version bump
label a release READY with a failed gate
delete local artifacts before remote verification
add a local fallback schema when ornix-tts is unavailable
set require_known_rights=False in a production campaign
reuse a legacy 24 kHz / six-field release as a migration source
```

Each is covered by a test in `docs/TESTING.md` and codified in `docs/adr/0008`.

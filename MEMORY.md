# MEMORY — cross-session execution state

> **This file is the single source of truth for cross-session execution state and the next
> autonomous action.** If it conflicts with git or test evidence, the evidence wins — fix this
> file.
>
> Last reconciled: 2026-09-29

---

## Goal

Build a deterministic, evidence-backed data factory that produces auditable datasets
consumable by `Teedyyy-rm/Ornix-TTS` without another metadata-normalization project.

---

## Repository boundary — absolute

```text
/home/obito/projects/ornix-Ds      ← THIS repository. All writes.
    origin  https://github.com/Teedyyy-rm/ornix-Ds.git

/home/obito/projects/Ornix-TTS     ← DOWNSTREAM. READ-ONLY. NEVER WRITE.
```

`ornix-Ds` is a **separate project, split out of `Ornix-TTS`**. Never a subdirectory, a
submodule, a workspace member, or a branch of it.

**Never** write, create, edit, delete or move any file under `Ornix-TTS`. Never run a tool
that writes there — `pytest`, `mypy --install-types`, `ruff --fix`, `build`,
`pip install -e`, `uv sync` against that checkout. Never use a **path or editable**
dependency on it: both write `*.egg-info` and bytecode into the source tree. Never put
`Ornix-TTS` in a uv workspace with this repository.

**When reading it:** always `python -B` or `PYTHONDONTWRITEBYTECODE=1`; never `cd` into it to
run anything. Local bootstrap copies the source to scratch, builds a wheel **there**, and
installs the wheel — procedure in `docs/OPERATIONS.md` §1a.

Verify after anything that touches `ornix-tts`:

```bash
git -C /home/obito/projects/Ornix-TTS status --porcelain    # must be empty
```

An empty result is necessary but **not sufficient** — `__pycache__` is gitignored, so a clean
`git status` does not prove nothing was written. Check filesystem mtimes when in doubt.

---

## Status

**Phase A in progress. A.1 and A.2 complete and green.**

| Milestone | State | Phases |
|---|---|---|
| M0 Foundation | `in_progress` | A.1 ✅ A.2 ✅ · A.3 ⬜ · B ⬜ · C ⬜ |
| M1 Acquisition | `pending` | D |
| M2 Signals | `pending` | E, F, G |
| M3 Evidence | `pending` | H, I, J, K |
| M4 Curation | `pending` | L, M, N, P |
| M5 Release | `pending` | O, Q, R, S, T |

Nothing is `blocked`.

---

## Completed

| What | Evidence |
|---|---|
| **A.1 — compatibility import proven** | `ornix-tts` installed as a wheel built in scratch. Every constant in `docs/CONTRACTS.md` verified against the installed package: `MANIFEST_SCHEMA_VERSION=1`, `WAVEFORM_SAMPLE_RATE_HZ=48000`, `RESAMPLER_VERSION=scipy-resample-poly-kaiser5-v1`, `QUALITY_VECTOR_REVISION=ornix-quality-vector-v1`, `DEDUPLICATION_REVISION=ornix-exact-dedup-v1`, `SPLIT_POLICY_REVISION=ornix-deterministic-split-v1`, `SEGMENTATION_REVISION=ornix-window-segmentation-v1`, `REGISTRY_SCHEMA_VERSION=MIXTURE_SCHEMA_VERSION=1`, `SUPPORTED_CONFIG_SCHEMA_VERSIONS=[1]`, `QualificationStatus` = 4 members (no `PENDING`/`REVIEW`), `TORCHCODEC_SUPPORTED_VERSION=0.16.0`, `TORCHCODEC_SUPPORTED_TORCH_VERSION=2.11.0`. **Zero discrepancies with the documentation.** |
| **A.2 — decision enum + projection** | `src/ornix_data/contracts/decision.py`, `errors.py`, `__init__.py`; 15 tests in `tests/unit/test_decision.py`. `ruff` clean, `mypy --strict` clean, 15/15 pass |
| **Repository boundary established and codified** | `AGENTS.md` §"Repository boundary — absolute", `ARCHITECTURE.md` §0.3, `docs/OPERATIONS.md` §1a, this file. Local bootstrap = copy to scratch → build wheel there → install wheel |
| Downstream contract audit of `Ornix-TTS` (read-only) | `docs/CONTRACTS.md` — 12 sections, all cited to `file:line`; coverage validated for 33 paths |
| Legacy repo audit of `ornix-dataset@main` (95 files, ~11,421 LOC, 324 tests) | `docs/MIGRATION.md` — file-by-file port/rewrite/drop matrix |
| Conflict analysis: 9 points where the seed architecture conflicts with reality | `docs/ANALYSIS.md` — 5 conflicts, 5 gaps, 10 decisions |
| 8 accepted ADRs | `docs/adr/0001`–`0008` |
| Normative architecture | `ARCHITECTURE.md` |
| Phased roadmap with testable exit criteria | `docs/ROADMAP.md` |
| Test matrix, anti-tests, fixture requirements | `docs/TESTING.md` |
| Operational runbook and downstream API traps | `docs/OPERATIONS.md` |
| Repository bootstrap | `README.md`, `AGENTS.md`, `MEMORY.md`, `pyproject.toml`, `.gitignore` |

---

## Not completed

- All implementation (phases A–T).
- No code, no tests, no configs, no `uv.lock` — `pyproject.toml` is a declared intent that has
  not been resolved or installed.
- Compatibility has **never been executed**. The compatibility import
  (`from ornix.data import ManifestRecord, Provenance`) is asserted from source reading, not
  from a running environment.
- No release has been built, verified, or published.

---

## Verified through

Implementation commit: **none**. The repository has documentation only.

Downstream reference: `Teedyyy-rm/Ornix-TTS` — **read-only, snapshot only**.

> **The downstream SHA is volatile.** Within a single session the checkout moved
> `5da288c` → `cebd6d9` → `f9a3b1f` on branch `codex/m1-3-semantic-extraction`, and
> `github.com/Teedyyy-rm/Ornix-TTS` returns HTTP 404 (private or unpublished).
> Every contract citation in `docs/CONTRACTS.md` is therefore stated as
> *"verified at `<sha>` on `<date>`"* and must be **re-verified before being relied on**.
> Do not treat any line number or constant in the docs as permanently true.

Test evidence: **none**. No test suite has been run, because none exists yet.

---

## Open blockers

None. Every phase is unblocked; A is simply not started.

Latent dependencies to confirm at the start of Phase A:

| Dependency | Why it matters | If it fails |
|---|---|---|
| `ornix-tts` imports in this repo's environment | The entire compatibility strategy rests on it | Stop and report. The architecture is not viable without it |
| Wheel build from a scratch copy succeeds without writing to the checkout | The only permitted resolution path (`docs/OPERATIONS.md` §1a) | Stop and report. Do **not** fall back to `pip install -e` |
| `torch==2.11.0` / `torchcodec==0.16.0` availability | The canonical decode path | Fall back is **not** permitted (ADR 0008); re-scope and report |
| FFmpeg present | Decode | Same |

**Resolved at A.1** (2026-09-29). `ornix-tts` is installed into `.venv` from a wheel built
in scratch from a snapshot of `Ornix-TTS@7ccf27f`. `from ornix.data import ManifestRecord,
Provenance` imports cleanly **inside this repository's environment**, and every constant
matches the documentation exactly.

**Install shape that works** — `uv pip install -e . --no-deps` plus a separate
`uv pip install <wheel>`. A plain `uv sync` fails because `ornix-tts` is unpublished and
`uv` tries to resolve it from an index. Recorded in `pyproject.toml` and `docs/OPERATIONS.md`
§1a.

Credentials are needed later, not now: HF token (Phase D), pyannote (Phase J, optional),
a writable HF repo (Phase S).

---

## Next actions

In order. Full detail in `docs/ROADMAP.md` §7.

1. **Phase A / task 3** — `config/models.py` and `config/loader.py` with
   `ConfigDict(strict=True, extra="forbid")`, importing every reference constant from
   `ornix.data` / `ornix.contracts` / `ornix.audio` so none is ever re-declared locally.
   Add `config/contract.py` as the single place those constants are read, with a test that
   the local values equal the installed `ornix-tts` values — that test is what catches a
   silent contract drift.
2. **Phase A / task 4** — `contracts/evidence.py` and `contracts/provenance.py`: the uniform
   provider metadata block (`provider_id`, `model_id`, `model_revision`, `weights_sha256`,
   `runtime`, `device`, `status`) and the `MeasurementStatus` enum, per `ARCHITECTURE.md` §3.
3. **Phase A / task 5** — `configs/sources/*.example.yaml`, `configs/policies/*.example.yaml`,
   `configs/models.lock.yaml` and their loader tests, including the `revision: main`
   rejection and the unknown-rights-`BLOCKED` path.

---

## Decisions in force

| ADR | Decision | Status |
|---|---|---|
| `0001` | Release audio at 48 kHz, read from `ornix.contracts.WAVEFORM_SAMPLE_RATE_HZ`, enforced by the factory | Accepted |
| `0002` | One resampler: call `ornix.audio`, never reimplement | Accepted |
| `0003` | The factory owns `PENDING` and `REVIEW`; only `ACCEPT` crosses the boundary | Accepted |
| `0004` | Comparison normalization is factory-local; all fingerprints use `use_record_text=False` | Accepted |
| `0005` | `ACCEPT` requires a computed quality vector, not merely "no error" | Accepted |
| `0006` | Factory owns utterance boundaries; `Ornix-TTS` owns training windows | Accepted |
| `0007` | SQLite is the only authoritative run state; identity is content-derived | Accepted |
| `0008` | No repair, no fabrication, no hidden defaults, no schema drift | Accepted |

None is superseded. Changing one requires a new ADR plus a reconciliation entry here.

---

## What the audit changed about the seed specification

Five conflicts, each resolved by an ADR, each of which would have produced a
reproducible-looking but silently wrong release:

1. **The resampler.** The seed spec proposed implementing one under
   `ornix-resample-polyphase-kaiser5-v1`. `ornix-tts` already ships the same algorithm as
   `RESAMPLER_VERSION = "scipy-resample-poly-kaiser5-v1"` with a hard-won half-up length
   rule, and the version is hashed into feature cache keys. A second name for one algorithm
   would have produced non-reusable cache keys and divergent results.

2. **The decision enum.** The seed spec mandates six states. `Ornix-TTS` has four;
   `PENDING` and `REVIEW` do not exist downstream. The spec's own acceptance criterion
   *"unavailable required detectors lead to REVIEW"* has no downstream home — so `REVIEW`
   must be factory-owned and must never cross the boundary.

3. **Text dedup silently doing nothing.** The spec correctly requires `text_normalized: null`.
   That makes `DedupFingerprint.from_record`'s default `use_record_text=True` yield
   `normalized_text_hash = None`, which makes `protect_normalized_text` a no-op with no
   warning — a dataset could ship text duplicates across train and test while reporting a
   clean leakage audit.

4. **`ACCEPTED` not implying quality.** `qualify_records` returns `ACCEPTED` with
   `quality=None` when no `AudioTensor` is supplied. A dataset shipped with no decodable audio
   qualifies clean downstream. "Missing evidence is never PASS" had to be enforced *before*
   the handoff, not after.

5. **Two segmenters.** `seeded_window_segments` is owned and wired upstream; the
   `VADProvider` Protocol is declared and never implemented. The factory owns boundaries,
   upstream owns windows, and neither reimplements the other.

Plus one gap that would have blocked the §1 goal outright: **`ornix.data` has no manifest
file loader**, so the factory must ship the reader its own release format requires.

---

## Reusable learnings

- `validate_audio_metadata_consistency` compares `record.duration_s` against
  `np.max(lengths)` — the longest item in the batch — and has no `item_index` parameter.
  Always call it with `B == 1`.
- `DedupFingerprint.__post_init__` validates hashes but discards the normalised value, so a
  directly-constructed uppercase hex hash will not group with the lowercase form.
  `from_record` is the only safe construction path.
- `DeduplicationResult.duplicate_ids` includes the canonical member of each group. Use
  `canonical_by_record` to decide what to drop.
- `assign_splits` is order-independent but **not** incrementally stable: adding one utterance
  re-hashes and can flip an entire speaker's component.
- `QualificationConfig.require_known_rights=False` turns `BLOCKED` into `ACCEPTED`. It is a
  trust-boundary escape hatch, not a convenience flag.
- `ornix-tts` audio errors do not subclass `DataPipelineError`, so `qualify_records`
  flattens them into `failure_reasons` strings. Read the strings, never the exception types.
- Silero v5 consumes **576 samples per step** (64 context + 512 new). Feeding only 512 makes
  the model emit ~0 on real speech. (Legacy `detectors/vad.py:127-142`)
- `ornix.data.registry` is unwired: `load_registry` has one in-repo caller (a test),
  `data/registry.yaml` ships empty and that emptiness is pinned by a test. Registration is a
  future obligation, not a release gate.

## Recorded incidents

| Date | Incident | Correction |
|---|---|---|
| 2026-09-29 | A contract-probe `python -c` was run using `Ornix-TTS`'s own venv **without** `PYTHONDONTWRITEBYTECODE=1`, which touched `__pycache__` directories under `Ornix-TTS/src/ornix/`. `git status` stayed clean because `__pycache__` is gitignored, so the write was invisible to the normal check. | Every subsequent read of `Ornix-TTS` uses `python -B` / `PYTHONDONTWRITEBYTECODE=1` and never `cd`s into it. Procedure codified in `docs/OPERATIONS.md` §1a.2. **Lesson: a clean `git status` does not prove nothing was written — check mtimes.** |

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

## Status

**Documentation complete. Implementation not started.**

| Milestone | State | Phases |
|---|---|---|
| M0 Foundation | `pending` | A, B, C |
| M1 Acquisition | `pending` | D |
| M2 Signals | `pending` | E, F, G |
| M3 Evidence | `pending` | H, I, J, K |
| M4 Curation | `pending` | L, M, N, P |
| M5 Release | `pending` | O, Q, R, S, T |

All 20 phases (A–T) are `pending`. Nothing is `in_progress`. Nothing is `blocked`.

---

## Completed

| What | Evidence |
|---|---|
| Downstream contract audit of `Ornix-TTS@5da288c` | `docs/CONTRACTS.md` — 12 sections, all cited to `file:line`; coverage validated for 33 paths |
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

Downstream reference: `Teedyyy-rm/Ornix-TTS@5da288c` (branch `main`).
Legacy reference: `ornix-dataset@main`, 95 files.

Test evidence: **none**. No test suite has been run, because none exists yet.

---

## Open blockers

None. Every phase is unblocked; A is simply not started.

Latent dependencies to confirm at the start of Phase A:

| Dependency | Why it matters | If it fails |
|---|---|---|
| `ornix-tts` installs and imports in a bare environment | The entire compatibility strategy rests on it | Stop and report. The architecture is not viable without it |
| `torch==2.11.0` / `torchcodec==0.16.0` availability | The canonical decode path | Fall back is **not** permitted (ADR 0008); re-scope and report |
| FFmpeg present | Decode | Same |

Credentials are needed later, not now: HF token (Phase D), pyannote (Phase J, optional),
a writable HF repo (Phase S).

---

## Next actions

In order. Full detail in `docs/ROADMAP.md` §7.

1. **Phase A / task 1** — scaffold `pyproject.toml` with `ornix-tts` as a **non-optional**
   dependency, create `src/ornix_data/`, and confirm
   `from ornix.data import ManifestRecord, Provenance` imports in a bare environment.
   **This is the highest-information first task**: it validates the repository's central
   assumption before any code is written.
2. **Phase A / task 2** — `src/ornix_data/contracts/decision.py`: `DecisionState` plus a
   total `to_ornix_status()` projection that raises on `PENDING` and `REVIEW` (ADR 0003),
   with a parametrised test over all six states.
3. **Phase A / task 3** — `config/models.py` and `config/loader.py` with
   `ConfigDict(strict=True, extra="forbid")`, importing every reference constant from
   `ornix.data` / `ornix.contracts` / `ornix.audio` so none is ever re-declared locally.

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

# ornix-Ds — the data admission and evidence layer of Ornix-TTS

> A deterministic, evidence-backed factory that turns raw internet speech data into
> auditable datasets that [`Teedyyy-rm/Ornix-TTS`](https://github.com/Teedyyy-rm/Ornix-TTS)
> can ingest **directly**, without another metadata-normalization project.

**This is not a generic downloader. It is not a generic audio cleaner. It is not a
model-training repository.**

---

## What this repository is

| | |
|---|---|
| **Purpose** | Dataset acquisition, validation, cleaning, qualification, provenance and release — exclusively for Ornix-TTS |
| **Sole consumer** | `Teedyyy-rm/Ornix-TTS` |
| **Contract authority** | Ornix-TTS. This repo must not invent an incompatible metadata schema |
| **Output** | `manifest.jsonl` built through the real `ornix.data.ManifestRecord` |

```text
Source Dataset
      │
      ▼
Ornix Data Factory                    ← this repository
      │ produces evidence-backed, reproducible clean speech
      ▼
Ornix-TTS ManifestRecord              built through the real contract
      │
      ▼
Ornix-TTS qualification
      │
      ▼
Training / Evaluation
```

---

## The rules that define it

```text
Missing evidence is never converted into PASS.      → REVIEW, not ACCEPT
Unknown legal status is fail-closed.                → BLOCKED
Source audio is immutable.                          → raw/ is read-only
A processed artifact never overwrites its source.
Ornix-TTS contracts are authoritative.              → no second ManifestRecord
Acceptance is vector-based, never a scalar score.   → {"quality": 0.91} is forbidden
```

Retired permanently, and verified absent from `Ornix-TTS` at source:

```text
canonical sample rate = 24 kHz
canonical schema      = exactly six fields
HuggingFace AudioFolder defines the training contract
sequential Ornix_<n>  defines sample identity
```

---

## Documentation

Read in this order.

| Document | What it answers |
|---|---|
| [`docs/ANALYSIS.md`](docs/ANALYSIS.md) | **Why.** The audit that found 9 places where the seed architecture conflicts with the real downstream contract or the legacy code, and the 10 decisions they forced. |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | **What.** The normative architecture — pipeline, contracts, layouts, decision states. |
| [`docs/CONTRACTS.md`](docs/CONTRACTS.md) | **The boundary.** The exact `ornix.data` surface, cited to `file:line` in Ornix-TTS, plus 11 things it does *not* provide. |
| [`docs/adr/`](docs/adr/) | **The decisions.** 8 accepted ADRs, each with consequences, rejected alternatives and a verification clause. |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | **The order.** Phases A–T with dependencies, testable exit criteria, a milestone map and a critical path. |
| [`docs/MIGRATION.md`](docs/MIGRATION.md) | **What to reuse.** File-by-file port/rewrite/drop matrix for the predecessor `ornix-dataset` repo (~35% directly portable). |
| [`docs/TESTING.md`](docs/TESTING.md) | **How it is proven.** The test matrix, anti-tests, and the fixtures that must be ported first. |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | **How to run it.** Runbook, known downstream API traps, reproducibility checklist, incident playbook. |

---

## Current status

**Documentation complete. Implementation not started.**

| Phase | State |
|---|---|
| A — contracts and configuration | `pending` |
| B — SQLite state | `pending` |
| C — source registry | `pending` |
| D — acquisition | `pending` |
| E — TorchCodec decode | `pending` |
| F — views | `pending` |
| G — signal metrics | `pending` |
| H — VAD | `pending` |
| I — transcript verification | `pending` |
| J — speaker/events (optional) | `pending` |
| K — segmentation and boundaries | `pending` |
| L — quality policy | `pending` |
| M — deduplication | `pending` |
| N — identity grouping | `pending` |
| O — Ornix-TTS compatibility bridge | `pending` |
| P — split | `pending` |
| Q — release builder | `pending` |
| R — release verifier | `pending` |
| S — publisher | `pending` |
| T — verified cleanup | `pending` |

Next actions are in [`MEMORY.md`](MEMORY.md) and in `docs/ROADMAP.md` §7.

---

## The pipeline

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

---

## CLI

```bash
ornix-data validate <campaign>    # config, sources, rights, policies, model lock
ornix-data run      <campaign>    # the complete allowed pipeline
ornix-data resume   <run-id>
ornix-data inspect  <run-id>
ornix-data qualify  <run-id>
ornix-data build    <run-id>
ornix-data verify   <release>
ornix-data push     <release>
```

---

## Quick orientation for a contributor

Five things that are non-obvious and that the code cannot tell you:

1. **Nothing is enforced upstream.** `ManifestRecord.sample_rate` accepts any positive int;
   `WAVEFORM_SAMPLE_RATE_HZ = 48_000` has zero consumers; `qualify_records` returns `ACCEPTED`
   with `quality=None` when no audio is supplied. This repository enforces all three.
2. **There is no manifest loader in `ornix.data`.** `ManifestRecord.from_json` is
   single-record. The factory ships its own reader, or the "consumable without another
   normalization project" goal fails on day one.
3. **`protect_normalized_text` silently no-ops** if the fingerprint was built with the default
   `use_record_text=True` and the record's `text_normalized` is `null` — which it always is
   here. Text dedup and text-leakage protection appear to work while doing nothing. (ADR 0004)
4. **There is one resampler and it is not ours.** Call `ornix.audio`. A second
   implementation under a second version string produces cache keys Ornix-TTS cannot reuse.
   (ADR 0002)
5. **The predecessor repo's hard parts are worth ~4,000 LOC** — bounded concurrency,
   backpressure, circuit breaking, immutable staging, fail-closed rights, dedup union-find,
   remote verification. Port them; do not rewrite them from memory. (`docs/MIGRATION.md`)

---

## License

To be determined. All sources must declare their own license; unknown license is `BLOCKED`.

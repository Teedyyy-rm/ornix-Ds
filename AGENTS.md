# AGENTS.md — Ornix-Ds autonomous engineering contract

This file is the bootstrap contract for coding/research agents working in this repository.
It is short on purpose. The detail lives in `docs/`.

## Mandatory reading order

Before implementing anything:

1. `README.md` — what this repository is
2. `docs/ANALYSIS.md` — the audit, and the 9 conflicts it found
3. `ARCHITECTURE.md` — the normative architecture
4. `docs/CONTRACTS.md` — the `ornix.data` boundary, cited to `file:line`
5. `docs/adr/` — the 8 accepted decisions
6. `docs/ROADMAP.md` — the phase you are in, and its exit criteria
7. `docs/TESTING.md` — the tests your change must satisfy
8. `MEMORY.md` — the current execution state and the next unblocked action

## Repository boundary — absolute

**Working directory: `/home/obito/projects/ornix-Ds/`. This is where all work happens.**

```text
/home/obito/projects/ornix-Ds      ← THIS repository. All writes.
    origin  https://github.com/Teedyyy-rm/ornix-Ds.git

/home/obito/projects/Ornix-TTS     ← DOWNSTREAM. READ-ONLY. NEVER WRITE.
```

`ornix-Ds` is a **separate project, split out of `Ornix-TTS`**. It is not a subdirectory, a
submodule, a workspace member, or a branch of it.

**Prohibited without exception:**

- Writing, creating, editing, deleting or moving any file under `/home/obito/projects/Ornix-TTS`.
- Running any tool that writes there — including `pytest`, `mypy --install-types`, `black`,
  `ruff --fix`, `build`, `pip install -e`, or any `uv sync` against that checkout.
- Using a **path or editable dependency** on that checkout. `editable = true` and setuptools
  builds both write `*.egg-info` and bytecode into the source tree. Both are forbidden.
- Adding `Ornix-TTS` to a uv workspace, or making either repo a member of the other.

**Required when reading it:**

- Run any Python against that checkout with `python -B` or `PYTHONDONTWRITEBYTECODE=1`, so no
  `.pyc` is written into its tree.
- Never `cd` into it to run anything.
- Treat every read as a **snapshot**: its branch is under active development and its HEAD moves.
  Cite a contract as *verified at `<sha>` on `<date>`*, never as permanent truth. Re-verify
  before relying on it.

**How the dependency is actually resolved** (see `docs/OPERATIONS.md` §1a): `ornix-tts` is
declared as a normal dependency in `pyproject.toml` for portability and CI. For local
bootstrap, the source is **copied to a scratch directory outside both repos**, built into a
wheel there, and the wheel is installed into this repository's `.venv`. `Ornix-TTS` is read
exactly once per build and never written.

## Non-negotiable rules

- Do not create a second `ManifestRecord`. Every record is built through
  `ornix.data.ManifestRecord` and `ornix.data.Provenance`.
- Do not create a second resampler. Call `ornix.audio.resample_audio`. (ADR 0002)
- Do not create a second window segmenter. Call `seeded_window_segments`. (ADR 0006)
- Do not invent PASS. Missing evidence is `REVIEW`, never `ACCEPT`. (ADR 0008)
- Do not replace an unmeasured metric with `0.0`, a mean, or an omission.
- Do not guess missing language, rights, or speaker identity.
- Do not edit `text_raw`. ASR verifies; it never authors.
- Do not add a gate whose evidence producer is unreachable. A gate that cannot fail is a
  defect. (ADR 0004)
- Do not use unknown-license or unknown-consent data.
- Do not normalise, denoise, or dereverberate. A processed artifact never overwrites its
  source, and clean audio is never fabricated.
- Do not relabel upsampled low-bandwidth audio as high quality.
- Do not pin a source at `revision: main` for a production campaign.
- Do not let an optional model become a required gate by accident.
- Do not delete local artifacts before remote verification.
- Do not add a local fallback schema when `ornix-tts` is unavailable. The build must fail.
- Do not add a sequential id allocator. Identity is content-derived. (ADR 0007)
- Do not mark a release READY if any mandatory gate failed.
- Do not claim release compatibility if the compatibility suite fails.

## Implementation order

```text
A contracts/config   B SQLite state      C source registry     D acquisition
E TorchCodec decode  F views             G signal metrics     H VAD
I transcript         J speaker/events    K segmentation       L quality policy
M dedup              N identity grouping O compatibility bridge
P split              Q release builder   R release verifier   S publisher
T cleanup
```

A phase is done only when its exit criteria in `docs/ROADMAP.md` are green in CI. Do not
start a phase whose dependency is not done.

## Definition of a valid change

A change is incomplete unless:

- every new contract has a test that would fail if the contract were removed;
- the four test layers that apply (`unit`, `integration`, `compatibility`, `acceptance`) pass;
- `ruff` and `mypy --strict` pass;
- new model or data dependencies carry an exact revision, license and provenance;
- any new provider populates `provider_id`, `model_id`, `model_revision`, `weights_sha256`,
  `runtime`, `device`, `status` — a revision field that is never written is worse than none;
- every transformation records input hashes, config identity, code revision, provider
  revisions and output hashes;
- `MEMORY.md` is updated: what completed, what did not, the verified commit SHA, the latest
  test evidence, and the next unblocked action;
- no ADR was violated. If one was, a new ADR supersedes it — never leave it implicit.

## Autonomous session bootstrap

On a new session:

1. Read `MEMORY.md`.
2. Read the 5–10 most recent commits.
3. Read the latest test/CI result; inspect failure logs if it failed.
4. Reconcile `MEMORY.md` against repository evidence. If they conflict, fix `MEMORY.md` —
   do not pretend the stale state is correct.
5. Execute the highest-priority unblocked task from `docs/ROADMAP.md` §7.
6. Run the required tests, commit, and close by updating `MEMORY.md`.

## Source-of-truth boundaries

- `MEMORY.md` is the single source of truth for cross-session execution state.
- `ARCHITECTURE.md`, `docs/adr/` and `docs/CONTRACTS.md` are normative for architecture,
  decisions and the downstream boundary.
- `Ornix-TTS` source is authoritative for every contract it owns. If this repository and
  Ornix-TTS disagree, Ornix-TTS is right and this repository is wrong.
- If a decision changes, amend or supersede its ADR **first**, then record the execution
  consequence in `MEMORY.md`.

## When uncertain

Choose the smallest independently testable implementation. If a decision is ambiguous, write
the test that would distinguish the options, then choose. Never resolve an ambiguity by
picking a default.

---

First-party skills follow the Ornix convention: skills translate specifications into
procedures, they do not override them. Specifications in `docs/` and accepted ADRs remain
normative.

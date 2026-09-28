# ADR 0007 — SQLite is the only authoritative run state

- **Status:** Accepted
- **Date:** 2026-09-29
- **Blocks:** Phase B (state), all resumable phases
- **Evidence:** `docs/ANALYSIS.md` §12.4

## Context

The seed architecture §17 requires SQLite via the standard library, and is unambiguous:
*"Do not use JSON files as the authoritative transactional state for multi-stage runs"* and
*"Do not replace SQLite with DuckDB for transactional workflow state."*

The legacy repository demonstrates exactly why. Repo-wide search for `sqlite`, `sqlite3`,
`CREATE TABLE`, `PRAGMA`, `cursor(`, `conn.` in `~/projects/ornix-dataset` returns **0
matches**. State is atomic JSON + append-only JSONL (`campaign/store.py:1-16`):

```text
campaign.json            # Campaign meta + ordered job_ids
jobs/<job_id>.json       # one DatasetJob per file
batches/<batch_id>.json  # one Batch per file
checkpoints/<job_id>/<batch_id>.jsonl
```

Durability comes from `util/io.py` — *"tmp + fsync + os.replace + dir fsync"*. That is a
correct write, but it is not a **transaction**. The absence of a transaction layer is the
direct cause of three hand-rolled correctness mechanisms:

1. **Reproducible `batch_id`** — `campaign/models.py:48-54` must derive a stable batch
   identity so a retry re-uses it instead of creating a gap.
2. **Progress-preserving re-plan** — `campaign/store.py:225-232` must reconstruct
   in-flight work before re-planning.
3. **Single-writer `flock`** — `canonical/identity.py:26-27` must serialise writers, because
   the sequential `Ornix_<n>` counter has no natural transaction. **Note this mechanism
   disappears entirely once identity is content-derived** (spec §27), because there is no
   counter left to protect.

The legacy repo also carries two parallel, incompatible state models — `pipeline.RunPaths`
(fan-in 18) and `CampaignStore` — plus a third in `canonical/CanonicalState`, and `cli.py`
(970 LOC) exposes three competing command trees on top of them.

## Decision

1. **SQLite is the sole authoritative mutable run state**, accessed through
   `sqlite3` from the standard library. No ORM, no migration framework at v1.
2. Schema is fixed at the tables named in spec §17:
   `runs, sources, assets, source_items, decoded_audio, segments, measurements, decisions,
   fingerprints, duplicate_groups, split_assignments, artifacts, releases, uploads, events`.
3. **Filesystem is content-addressed, not stateful.** Immutable raw bytes and derived
   artifacts live on disk addressed by hash; the database records their identity, not their
   location history. A `read` never needs a filesystem scan to find anything.
4. **Stage transitions are transactions.** A phase commits its writes, its measurement rows,
   its decisions and its artifact identities in one transaction. A crash leaves the run in the
   last committed phase — never half-way through one.
5. **Resume is state-driven, not path-driven.** `ornix-data resume <run-id>` reads
   `(phase, status)` from `runs` and re-executes the first incomplete phase. There are no
   hand-rolled reconciliation paths and no `flock`.
6. **Parquet/DuckDB/Polars are read-only analytical mirrors.** `manifest.parquet` is derived
   from `manifest.jsonl` and both hash back to the same logical records. Neither is ever
   written to by the pipeline.
7. `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` are set on open. Writes go through a
   single connection per worker; a run is single-writer by construction.
8. **Sample identity is content-derived** (spec §27), so identity is a pure function of
   `(dataset_id, source_revision, source_item_identity, start_sample, end_sample)`. There is
   no counter, no filename allocation, and no state to protect.

## Consequences

**Positive**

- Resume correctness becomes a database property rather than a hand-written invariant.
- Identity stability across resume is structural, not tested-into-existence.
- One state model collapses the legacy repo's three command trees and three state models into
  the single 8-verb UX of spec §19.
- Concurrent workers cannot corrupt a run; a duplicate insert is a constraint violation, not a
  silent overwrite.
- The `flock` and the sequential-id machinery both disappear, because the problem they solved
  no longer exists.

**Negative**

- SQLite is a single-writer store. Parallelism must be inside a phase (across source items),
  never across phases of one run. This is a real constraint on the scheduler design.
- Schema migrations are manual at v1. Acceptable while the schema is still moving fast; the
  `schema_version` column exists from day one so migrations are never guessed.
- The whole state must be a single file that is copied, backed up and (carefully) cleaned.

**Becomes impossible**

- Resuming a run from a directory layout.
- A run that is "half decoded" — decoding is one transaction.
- Silent identity duplication on retry.

## Alternatives rejected

1. **Keep the legacy atomic-JSON + JSONL model.** Rejected: it is the direct cause of the
   three hand-rolled mechanisms, and none of them survive this design.
2. **DuckDB as the store.** Rejected explicitly by spec §17, and correctly: DuckDB is an
   analytical engine, not a transactional one.
3. **Postgres.** Rejected: a single-worker pipeline on one machine does not justify a server
   dependency, and SQLite is already in the standard library.
4. **An ORM (SQLAlchemy).** Rejected: the schema is small, the queries are known, and an ORM
   adds a dependency and an abstraction layer over a store whose whole value is being boring
   and inspectable.
5. **Keep the sequential id allocator and the `flock`.** Rejected: content-derived identity
   (spec §27) makes both unnecessary, and the spec explicitly forbids global sequential
   counters as an identity source.

## Verification

```python
def test_resume_after_crash_at_each_phase(run, crash_injector):
    for phase in ALL_PHASES:
        crash_injector.fail_at(phase)
        resumed = resume(run.run_id)
        assert resumed.records == run.records            # identical, including identity
        assert len(resumed.manifest_ids) == len(set(resumed.manifest_ids))

def test_no_sequential_id_allocation_exists():
    # static check: no counter/sequence in the identity path
    ...

def test_state_is_authoritative_not_the_filesystem(tmp_path):
    shutil.rmtree(tmp_path / "state")
    # runs cannot be discovered by scanning the workspace
    ...

def test_wal_and_foreign_keys_enabled(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
```

Plus a crash-injection acceptance test that kills the worker at every phase boundary and
asserts byte-identical release output.

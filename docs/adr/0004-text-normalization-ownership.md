# ADR 0004 — Comparison normalization is not canonical text

- **Status:** Accepted
- **Date:** 2026-09-29
- **Blocks:** Phase I (transcript verification), Phase M (dedup), Phase P (split)
- **Evidence:** `docs/ANALYSIS.md` §4

## Context

The seed architecture §24 is **correct** and was verified against source. The factory owns:

```text
raw transcript preservation
encoding validation
language evidence
audio-text verification
comparison-only normalization
```

`Ornix-TTS` owns spoken normalization. And `qualify_records` confirms the division of labour:
it runs its own `BaselineSpokenTextNormalizer` over `text_raw` and stores the result in
`QualifiedRecord.normalization` — it never mutates `record.text_normalized`
(`qualification.py:587-598`). So the factory ships `"text_normalized": null`, and the
downstream `test_m1_2_qualification.py:46-79` fixture deliberately exercises exactly that path.

**But §24 interacts badly with dedup and split, and the interaction is silent.**

`DedupFingerprint.from_record` defaults to `use_record_text=True` (`dedup.py:71`), selecting
`record.text_normalized` (`:87`). With `text_normalized=None`:

1. `normalized_text_hash` is `None` — `dedup.py:88`.
2. `_group_ids` skips `None` — `dedup.py:214-224`. The record joins **no** text group.
3. `assign_splits` guards on `is not None` — `split.py:213-215`.
4. `validate_no_train_eval_leakage` does the same — `split.py:258-262`.

**`protect_normalized_text=True` therefore provides zero protection, with no warning and no
error**, and `LeakageReport.ok` still reads `True`. A dataset could ship thousands of
text-duplicate segments spanning train and test while reporting a clean leakage audit.

Upstream's own defaults are safe — `SplitPolicy.protect_normalized_text = False`
(`split.py:35`) and `QualificationConfig.deduplicate_text = False` (`qualification.py:106`) —
so the hazard is entirely on the factory side, from a default argument nobody reads.

The legacy repo has the same class of bug: `curation/transcript.py:40-52`
`transcript_match_status` has **zero callers**, so `policy._transcript` (`policy.py:195-205`)
can only ever return `PASS` (via `NOT_APPLICABLE`) or `UNKNOWN` — never a real transcript
mismatch. A gate that looks present but cannot fail is worse than an absent gate.

## Decision

1. The factory ships `text_raw` **byte-for-byte as the source provides it**, and
   `text_normalized = null`. It never rewrites `text_raw` and never uses ASR output as text.
2. The factory maintains a **comparison-normalized text**, in a separately named field, used
   only for: ASR distance computation (WER/CER), text-level dedup, and analysis grouping. It
   is **never** written to `text_raw` and **never** written to `text_normalized`.
3. **Every** `DedupFingerprint` is built as:

   ```python
   DedupFingerprint.from_record(
       record,
       audio=audio,
       raw_audio_bytes=raw,
       normalized_text=comparison_normalized,   # explicit
       use_record_text=False,                   # ALWAYS False
   )
   ```

   `use_record_text=False` is **mandatory and non-default**. A lint rule and a test forbid
   `use_record_text=True` anywhere in the codebase.
4. When the comparison text is unavailable, the factory must **not** silently pass `None` and
   call it done. It records `text_evidence_status = UNAVAILABLE`, and the dedup/split policy
   decides: either the run is `REVIEW` for those records, or the release declares the text
   axis unprotected — explicitly, in the release metadata and the leakage report. Silence is
   not an option.
5. A **gate that cannot fail is a defect.** Any policy gate whose evidence source has no live
   producer is a bug, not a pass. The legacy `transcript_match_status` dead-code pattern is
   banned; every gate declares its evidence producer and a test that proves the producer is
   reachable.
6. Comparison normalization rules are versioned (`text_compare_normalizer_revision`) and
   recorded in provenance, because a change to them changes dedup groups and therefore splits.

## Consequences

**Positive**

- Text-level dedup and `protect_normalized_text` actually work.
- Canonical transcript fidelity is absolute: the release's `text_raw` is exactly the source's.
- The comparison layer can evolve (numbers, punctuation, case) without touching the corpus
  text, and without invalidating the manifest's text identity.
- §24's ownership boundary is enforced rather than merely stated.

**Negative**

- A second text representation exists and must be versioned and audited.
- The factory must decide what to do when comparison normalization is unavailable. Two
  honest options (send to `REVIEW`, or declare the axis unprotected) — and the decision must
  be recorded, not defaulted.
- `use_record_text=False` at every call site is a discipline cost, paid back by a lint rule
  and a grep-based test.

**Becomes impossible**

- A release whose text-duplicate structure is unknown while its leakage report claims `ok`.
- A factory that "corrects" a dataset transcript using ASR.

## Alternatives rejected

1. **Set `text_normalized` to the comparison text so the downstream hash works.** Rejected:
   it puts non-canonical, factory-owned text into a field the downstream owns. Ornix would
   then see a "normalized" text that no normalizer produced, and its own normalizer would run
   over it anyway.
2. **Set `protect_normalized_text=False` and document that text leakage is not checked.**
   Rejected: the spec explicitly requires leakage protection on *"configured
   normalized-text identity"*, and leaving it off by default makes the corpus quietly
   vulnerable. It may be turned off, but only with an explicit, recorded declaration.
3. **Compute the text hash in the factory and inject it into a `DedupFingerprint`
   constructor call.** Rejected: `__post_init__` validates via `_optional_hash` but
   **discards its return value** (`dedup.py:30-35,53-60`), so an uppercase hex hash survives
   and **will not group** with the lowercase form of the same hash. `from_record` is the only
   safe construction path.

## Verification

```python
def test_no_call_site_uses_record_text():
    # static: no `use_record_text=True` anywhere in src/
    ...

def test_text_dedup_groups_records_with_null_text_normalized(release):
    fp = DedupFingerprint.from_record(
        record, audio=a, normalized_text=comp_text, use_record_text=False
    )
    assert fp.normalized_text_hash is not None

def test_comparison_text_never_reaches_manifest(release):
    for r in release.records:
        assert r.text_normalized is None
        assert r.text_raw == source_transcript[r.id]   # byte-identical to source

def test_protect_normalized_text_actually_protects(...):
    # two records with identical comparison text land in the same split
    ...
```

Plus a negative test: a policy gate whose provider is stubbed out must fail the build, not
report `PASS` (the legacy `transcript_match_status` failure mode).

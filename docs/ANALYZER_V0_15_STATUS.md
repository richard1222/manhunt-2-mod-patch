# Manhunt 2 Restoration Analyzer v0.15 — private test status (2026-10-26)

The private Analyzer v0.15.0 is a read-only ISO9660 inventory and SHA-256 comparison tool. The analyzer source and ZIP are **not** published in this public repository; the released PS2 patch scripts are separate.

## Reproduced and fixed with synthetic fixtures

1. **Path stat/open race:** v0.14 read `iso_bytes` from a pathname `stat` before opening the image. A replacement between those operations could produce a manifest reporting the old image's size while reading the new image. v0.15 obtains size from `fstat` on the opened descriptor.
2. **Undetected mid-scan source modification:** v0.14 could return a stale per-file SHA-256 after another writer changed source bytes during hashing. v0.15 compares the opened inode's device, inode, size, modification time and change time before/after scanning, rejecting detected changes.
3. **Undetected source-path replacement after opening:** v0.14 could return a manifest after the pathname was switched to another file while its original descriptor remained open. v0.15 checks that the pathname still resolves to the scanned inode at the end.

Regression tests: `test_replacement_between_path_stat_and_open_uses_opened_inode_size`, `test_mutation_during_hashing_is_rejected`, and `test_source_path_replaced_after_open_is_rejected` (the last skips on systems where replacing an open file is unsupported). **All three tests failed against v0.14 and passed with v0.15.**

**Verification:** v0.14 baseline 53/53 tests passed. v0.15 passed **56/56 tests** on Linux/Python 3, including after extracting the final ZIP. CLI reports `0.15.0`. All images used were synthetic. Private ZIP SHA-256: `8c54a7d5c4c33478be897398c69f1cac4dee2b7e99bf24229cfa81a3a5d0d3f1`.

## Remaining limitations

- These are **best-effort** source consistency checks, not an atomic filesystem snapshot. Undetected or reverted concurrent changes and changes after the final check remain possible. For reproducible reports, use immutable local copies and verify the full image SHA-256 before and after scanning.
- The four real Manhunt 2 ISOs still require read-only PC scans, independent file-hash checks, and internal platform/build identification; filenames do not establish identity.
- Unsupported ISO9660 layouts/extensions are rejected. Report publication is atomic per file, **not transactional across a report set** if disk publication fails.
- Do not publish copyrighted game images, extracted game assets, or private analyzer source in this repository.

The private v0.15 package and PC handoff belong in the user's private Google Drive.

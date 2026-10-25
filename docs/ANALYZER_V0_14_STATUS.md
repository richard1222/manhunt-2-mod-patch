# Manhunt 2 Restoration Analyzer v0.14 — private test status (2026-10-25)

The private Analyzer v0.14.0 is a read-only ISO9660 inventory and SHA-256 comparison tool. Its source and ZIP are **not** published in this repository; the public patch scripts here are separate.

## Reproduced and fixed using synthetic ISO fixtures

- **Missing required special directory records accepted:** v0.13 allowed a directory without its first `.` (ISO9660 `0x00`) or second `..` (ISO9660 `0x01`) entry and still returned a plausible one-file manifest. v0.14 requires both entries, in that order, for every directory.
- **Duplicate special directory entries accepted:** v0.13 allowed repeated `..` entries. v0.14 rejects additional special entries after the required first two.

Regressions: `test_missing_current_directory_entry_rejected`, `test_missing_parent_directory_entry_rejected`, `test_duplicate_special_directory_entry_rejected`.

**Verification:** v0.13 baseline 50/50 tests passed. v0.14 53/53 tests passed on Linux/Python 3, and 53/53 passed again after extracting the final ZIP. CLI version `0.14.0`. All fixtures were synthetic; no real game ISO was scanned or modified.

Private package SHA-256: `14af20154cbd59ddeffbcd0e78f90e4472db3bb661f6da8dc36b7965e11590f8`.

## Remaining limitations

- Four real Manhunt 2 images still require a read-only PC scan and independent file-hash verification. Filename alone does not establish platform/build identity.
- Unsupported ISO9660 layouts/extensions are deliberately rejected.
- Report publication is atomic per file, **not transactionally as a set** if disk publication fails partway through.
- No copyrighted game images, assets or private analyzer source belong in this public repository.

Keep the private ZIP and PC handoff in the user's private Google Drive.

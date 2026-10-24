# Manhunt 2 Restoration Analyzer v0.13 — private test status (2026-10-24)

The private Analyzer v0.13.0 is a read-only ISO9660 inventory and SHA-256 comparison tool. The analyzer source and ZIP are **not** published in this repository; the public patch scripts here are separate.

## Reproduced and fixed using synthetic ISO fixtures

- **Incorrect PVD root identifier accepted:** v0.12 accepted a primary volume descriptor root directory record named `R` rather than the required ISO9660 special root identifier `0x00`. v0.13 rejects the malformed root identifier. Regression: `test_reject_non_special_pvd_root_identifier`.
- **Incorrect `..` directory record accepted:** v0.12 skipped parent-directory extent/size validation, accepting a root `..` pointer beyond the declared volume and a nested `..` pointer to the wrong parent. v0.13 validates each present `..` entry against the expected parent directory's extent and size. Regressions: `test_reject_wrong_root_parent_extent_even_if_outside_volume`, `test_nested_parent_must_point_to_actual_parent` (also verifies valid nesting).

**Verification:** v0.12 baseline 47/47 tests passed. v0.13 50/50 tests passed on Linux/Python 3, and 50/50 passed again after extracting the final ZIP. The CLI reports version `0.13.0`. All fixtures were synthetic. No real game ISO was scanned or modified.

Private package SHA-256: `abdbe3c806363b7650c0053d66c26b3f28b364ed0fbcd86c6cb5b09fe8cc4e57`.

## Remaining limitations

- The four real Manhunt 2 images still require a read-only scan and independent hash verification by the PC counterpart. Filename alone does not establish platform/build identity.
- The parser deliberately rejects unsupported ISO9660 layouts/extensions.
- Output reports are atomically published per file, **not transactionally as a set** if disk publication fails partway through. The v0.12 scan-before-publish fix covers input parsing failures, not every disk failure.
- No copyrighted game assets, ISOs, or private analyzer source belong in this public repository.

The private v0.13 ZIP and PC handoff should be kept in the user's private Google Drive.

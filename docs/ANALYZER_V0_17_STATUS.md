# Manhunt 2 Restoration Analyzer v0.17 — private synthetic-test verification (2026-10-28)

**Scope:** Private read-only ISO9660 analyzer. This public repository contains status documentation only; no private analyzer source, copyrighted game images, or extracted assets.

## Reproduced v0.16 issues

1. **Direct test runner skipped 12 tests.** In v0.16, `test_analyzer.py` invoked `unittest.main()` before the v0.13–v0.16 test classes were defined. On Linux/Python 3, `python test_analyzer.py -q` ran **47 tests**, but `python -m unittest discover -q` ran **59**. This made a direct test run appear complete even though 12 later tests were omitted.
2. **Reserved ISO9660 file flags accepted.** Directory-record flag bits `0x20` and `0x40` are reserved by ISO9660. v0.16 silently parsed both as valid file records. A new synthetic regression test failed against the v0.16 parser for each bit, confirming the defect.

## v0.17 fixes and verification

- Move the `unittest.main()` entry point below all test classes. Add an AST-based regression test checking that the entry point follows every test class.
- Reject directory records with either reserved file-flag bit set (`flags & 0x60`), rather than silently accepting malformed metadata.
- Update the CLI version to `0.17.0`.

**Tests:** **61/61** passed with `python -m unittest discover -q` and **61/61** passed with `python test_analyzer.py -q`, including both commands repeated after extracting the final ZIP. All test images were synthetic. ZIP SHA-256: `ec82299f40d6eac2fceb1baa7c17e95e5457f713542541eb6a113aa53094a69d` (15,432 bytes).

## Limitations

No real Manhunt 2 ISO has been scanned for this verification, and no real-hardware compatibility is claimed. This change is ISO metadata validation and test coverage hardening, not a cut-content or uncensor patch. Source consistency checks are best-effort; staged multi-report publication is not crash-atomic and rollback can fail. Real-image scans, independent SHA-256 checks, and supported-format verification remain release gates. Do not commit copyrighted game images/assets or private analyzer source to this public repository.

**Distribution:** The v0.17 ZIP and PC handoff were uploaded to private Google Drive on 2026-10-28; Drive metadata readback confirmed both filenames and sizes and owner-only permissions. The ZIP remains private and is not committed to this repository.

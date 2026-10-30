# Manhunt 2 Restoration Analyzer v0.19 — synthetic-test verification (2026-10-30)

**Scope:** Private, read-only ISO9660 inventory and comparison tool. This public status report contains no copyrighted game images, extracted assets, or private analyzer source.

## Reproduced v0.18 defect

The CLI checked each input during its individual scan, but did not recheck **earlier inputs after later images were scanned** or after report rendering. If an earlier ISO changed or its pathname was replaced, the CLI could publish stale manifests and comparisons without warning.

Three deterministic synthetic regressions reproduce this defect against v0.18:

1. Modify the first ISO while scanning a second ISO.
2. Replace the first ISO's pathname while scanning a second ISO.
3. Modify an ISO during report rendering, after its scan finishes.

All three regressions failed against v0.18 (no exception raised) and passed with v0.19.

## v0.19 changes

- Capture a best-effort source fingerprint (device, inode, byte size, nanosecond mtime and ctime) before and after each scan.
- Use the resolved source paths that were checked for input/output collisions.
- After rendering all reports, recheck **every** scanned source immediately before publication; abort without publishing if any fingerprint changed.
- Add three synthetic regression tests for these cases.

**Verification:** 67/67 tests passed with `python -m unittest discover -q` and `python test_analyzer.py -q` on Linux, including after extracting the final private ZIP. `python analyzer.py --version` reports `0.19.0`. ZIP: 17,759 bytes; SHA-256 `d11cd0eb3747fb3ae296e7ec41f7367a388ec153069079776529cac051ffdb39`.

The private v0.19 ZIP and PC handoff were uploaded to the owner's Google Drive; filename, size, and owner-only permissions were verified.

## Limitations

- This is **not** an atomic filesystem snapshot. Concurrent changes after the final check, timestamp spoofing, and other races remain possible. Scan immutable copies and independently verify full-image SHA-256 hashes.
- Report publication is not crash-atomic across multiple files. The no-overwrite path still requires hard-link support.
- All tests used synthetic ISO images. The four real Manhunt 2 ISOs and PS3 hardware are **not tested with v0.19**. No real-game compatibility or cut-content restoration claim is made.
- Do not commit copyrighted game images, extracted assets, or private analyzer source.

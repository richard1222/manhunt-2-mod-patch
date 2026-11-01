# Manhunt 2 Restoration Analyzer v0.21 — synthetic verification (2026-11-01)

**Scope:** Private read-only ISO9660 inventory and comparison. No copyrighted game data or private analyzer source is included here.

## Reproduced v0.20 defect

Report publication attempts best-effort rollback if a later report fails. In v0.20, rollback did not verify that an earlier published report still belonged to the analyzer. If another writer replaced it before the later failure, no-overwrite rollback deleted the external replacement; overwrite rollback replaced it with an old backup. In-place edits to the published inode were also overwritten. All three data-loss cases were reproduced using deterministic synthetic files and injected publication errors.

## v0.21 changes

- Record each successfully published report's device/inode identity and observed size, nanosecond modification time, and change time.
- Before rollback, refuse to unlink or replace a report whose pathname now identifies a different or modified file. Preserve it and raise `Report publication failed; rollback INCOMPLETE` so callers know the output set must be inspected.
- Continue normal rollback of unchanged reports. Add three regressions for replacement in no-overwrite mode, replacement in overwrite mode, and in-place modification before rollback.

**Reproduction:** The three regressions fail against v0.20, which deletes or overwrites external data. They pass with v0.21.

**Verification:** 73/73 automated tests passed on Linux/Python 3.13 using both `python -m unittest discover -q` and `python test_analyzer.py -q`, including after extracting the final private ZIP. `python analyzer.py --version` reports `0.21.0`. ZIP SHA-256: `63fe5494a637a3ed062e9f8ee2065d2dcce75fb1513f3bd5dd68ce8e8062425d`.

## Limitations

- This is **best-effort detection**, not an atomic filesystem transaction. A concurrent change between verification and rollback, metadata spoofing, and crash interruption can still cause inconsistency. An `INCOMPLETE` rollback requires manual review.
- The no-overwrite publication path still requires hard-link support.
- **No real Manhunt 2 ISO or PS3 hardware was tested with v0.21.** No real-game compatibility or cut-content restoration is claimed.
- Do not publish copyrighted ISOs, extracted game assets, or private analyzer source.

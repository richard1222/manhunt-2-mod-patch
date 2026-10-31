# Manhunt 2 Restoration Analyzer v0.20 — synthetic verification (2026-10-31)

**Scope:** Private, read-only ISO9660 inventory and comparison. This public status contains no copyrighted game data or private analyzer source.

## Reproduced v0.19 defect

In `--overwrite` mode, the report publisher checked `target.is_symlink()` and later used `shutil.copy2(target, backup)`. A report pathname replaced by a symlink between these operations caused the backup to follow the link and read unrelated file contents. When a later report publication failed, rollback could restore those unrelated bytes as a report. A deterministic synthetic test reproduced this disclosure in v0.19.

## v0.20 changes

- Open each existing report for backup with `O_NOFOLLOW` where available and `O_NONBLOCK`; validate the opened file is regular and matches the pathname's `lstat` identity before copying.
- Copy the report through the verified open descriptor, check size and modification metadata after copying, and reject detected replacement or mutation.
- Preserve basic file mode and timestamps in the independent rollback copy; reject nonregular existing report targets such as FIFOs.
- Add three regression tests: symlink substitution between precheck and backup, symlink substitution followed by rollback, and FIFO report rejection.

**Reproduction:** All three new regressions failed against v0.19 (two failures and one exception). All passed with v0.20.

**Verification:** 70/70 automated tests passed on Linux/Python 3.13 using both `python -m unittest discover -q` and `python test_analyzer.py -q`. Both passed again after extracting the final private ZIP. `python analyzer.py --version` reports `0.20.0`. ZIP SHA-256: `a44f83b764cd00d9e569af32c0608f85326dd9fd39d588ca5372a25887a102ac`.

## Limitations

- Backup checks are best-effort. Platforms without `O_NOFOLLOW` rely on opened-file/path identity checks, not a race-free no-follow open.
- Concurrent changes after checks, timestamp spoofing, and multi-file crash-atomic report publication are not solved. The no-overwrite publication path still requires hard-link support.
- **No real Manhunt 2 ISO or PS3 hardware has been tested with v0.20.** No real-game compatibility or cut-content restoration is claimed.
- Do not publish copyrighted ISOs, extracted game assets, or private analyzer source.

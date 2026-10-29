# Manhunt 2 Restoration Analyzer v0.18 — private synthetic-test verification (2026-10-29)

**Scope:** Private, read-only ISO9660 inventory and comparison tool. This public status document contains no private analyzer source, copyrighted game images, or extracted assets.

## Reproduced v0.17 report-publication defects

1. **Rollback backup aliasing.** v0.17 created a hard link to each existing report as its rollback backup. Hard links point to the same inode; they are not independent snapshots. A synthetic regression holds an open file descriptor to an old report, modifies that inode after the first report is replaced, then injects a failure publishing the second report. v0.17 restores the modified bytes rather than the original report, violating the intended rollback behavior.
2. **Unnecessary hard-link dependency for overwrite.** v0.17 uses `os.link` both to back up existing reports and to stage new reports. Simulating `os.link` raising `EOPNOTSUPP` reproduces failures in the overwrite publication path and in a full CLI `--overwrite` run.

## v0.18 changes and verification

- Create **independent copies** of existing report bytes and metadata in the private staging directory before publication, rather than hard-linked aliases. This preserves the pre-publication report against later writes through a previously opened descriptor to the original inode.
- Stage generated reports with atomic replacement inside the private temporary staging directory, which has no preexisting generated report paths. This removes the hard-link dependency from the **overwrite** path.
- Add three deterministic synthetic regression tests: rollback after a writer modifies the old inode, direct overwrite backup with hard links unavailable, and full CLI overwrite with hard links unavailable. All three failed against v0.17 and passed against v0.18.

**Verification:** **64/64 tests passed** using `python -m unittest discover -q` and **64/64 passed** using `python test_analyzer.py -q` on Linux/Python 3.13. Both commands also passed after extracting the final ZIP. `python analyzer.py --version` reports `0.18.0`. The final private ZIP is 16,698 bytes, SHA-256 `8ad726019762a360a7dcedc25018f4be3e6b01458b367b1832d9b246bf8f637a`.

## Limitations

- The **no-overwrite** final publication path still uses exclusive hard-link creation and may fail on filesystems that do not support hard links. This is not fixed by v0.18.
- Backups are not filesystem snapshots: concurrent modification **during the copy**, power loss, process termination, and rollback I/O failure remain possible sources of mixed reports. The tool does not promise a crash-atomic multi-report transaction.
- All tests used synthetic ISO images. The four real Manhunt 2 ISOs and PS3 hardware have **not** been tested with v0.18. Real-image scans, independent hashes, and format compatibility checks remain release gates.
- Never commit copyrighted game images/assets or private analyzer source to this public repository.

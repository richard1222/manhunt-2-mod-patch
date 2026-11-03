# Manhunt 2 Restoration Analyzer v0.22 — synthetic verification (2026-11-03)

**Scope:** Private read-only ISO9660 inventory/comparison. No game assets or private analyzer source are published here.

## Reproduced v0.21 defect
In overwrite mode, after an existing report was copied to a rollback backup, a concurrent writer could replace, remove, or modify that report before the analyzer called `os.replace(staged, target)`. The analyzer then overwrote the concurrent change without detecting it. Three deterministic injected-mutation regression tests failed against the unmodified v0.21 package.

## v0.22 changes
The backup helper returns the source report's verified device/inode, size, modification time and change time fingerprint. Immediately before overwrite publication, the analyzer compares the current report against that fingerprint; if the target was absent at backup time, it also refuses a newly appeared target. A detected mismatch aborts publication and leaves the externally changed report intact. This is a **best-effort check, not an atomic compare-and-swap**: a writer racing between the final check and `os.replace` may still lose data.

## Verification
All 76 synthetic automated tests passed on Linux with `python -m unittest discover -q` and `python test_analyzer.py -q`. All 76 passed again after extracting the final v0.22 ZIP. The three new regression tests failed against the original v0.21 source and passed after the fix. ZIP SHA-256: `3eff5223d9b88acbeaa68af7bcf51d3c98f143ce54e2f4e8aabda0173e45bae8`.

## Limitations
No real Manhunt 2 ISO or console was tested. Multi-report publication remains non-atomic across crashes and concurrent writes. The package is private; no copyrighted game image or assets are included.

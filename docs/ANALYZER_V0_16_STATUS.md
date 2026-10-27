# Manhunt 2 Restoration Analyzer v0.16 — verification status (2026-10-27)

**Scope:** private read-only ISO9660 analyzer. Public repository contains status documentation only; no analyzer source, game images, or extracted assets.

## Reproduced v0.15 defect
v0.15 wrote each JSON/CSV report directly to the output directory. If a later report writer failed, an earlier report could already have replaced the old one, leaving mismatched files. A failure during publication could similarly leave a partially updated set. Three synthetic fault-injection regression tests reproduced these problems against v0.15 (3 failures).

## v0.16 fix and tests
v0.16 first renders the complete report set in a temporary directory under the output directory. It then publishes the staged files. For ordinary publication errors, it attempts rollback using hard-linked copies of existing reports. The three new tests cover:
1. Writer failure after a prior report was rendered, with `--overwrite`.
2. Failure replacing the second report, with existing reports restored.
3. Failure exclusively creating the second report, with newly created reports removed.

**Verification:** 59/59 Python unittest cases passed on Linux, and 59/59 passed again after extracting the packaged v0.16 ZIP (56 inherited + 3 new). All game-like inputs in the tests were synthetic. ZIP SHA-256: `b5d100e74e415b35756574ced09f6d86610bf3c7d48d4ea99f8fa95f9f4118f8`.

**Important limitations:** This is not a crash-atomic multi-file transaction. Power loss, SIGKILL, external concurrent modification, or rollback I/O failure can still leave inconsistent output. v0.15's source-change checks remain best-effort rather than a guaranteed filesystem snapshot. No real Manhunt 2 ISO has been scanned or independently hashed in this verification; no hardware compatibility or content-restoration claim is made.

**Distribution status:** The v0.16 ZIP and PC handoff were created locally, but the attempted Google Drive uploads failed with `container_session_expired`. Do not describe them as available in Drive until independently verified. The last confirmed private Drive package remains v0.15.

**Next:** Transfer v0.16 privately when upload access is restored, run on the four user-owned images, verify hashes independently, and upload only derived reports privately. Never commit copyrighted game images/assets or private analyzer source to this public repository.

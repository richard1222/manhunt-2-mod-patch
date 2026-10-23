# Manhunt 2 Restoration Analyzer v0.12 — private test status (2026-10-23)

The Analyzer is a **private, read-only** ISO9660 inventory and SHA-256 comparison tool. Its source and ZIP are not published in this repository. The public PS2 patch scripts in this repository are separate from the Analyzer.

## Verified against synthetic ISO9660 fixtures

- **47/47 Python unittest cases passed on Linux** with Python 3 and standard-library-only dependencies. No real Manhunt 2 image was scanned in this test run.
- **Fixed: partial report sets after a later input fails.** v0.11 wrote the first ISO's JSON/CSV manifests before scanning the second ISO. If the second image was invalid, the command failed but left the first pair of reports behind. Under `--overwrite`, the first pair could be replaced while older comparison reports remained. v0.12 scans every input successfully before publishing any reports. Regression tests cover a malformed second image and an unsuccessful overwrite rescan that must preserve the existing reports.
- **Fixed: indistinguishable comparison labels.** Two input images with the same basename (in different directories) produced identical JSON `builds` labels and duplicate CSV column headers. v0.12 prefixes comparison labels with `build_01:`, `build_02:`, etc., matching the manifest filenames without exposing full local paths. A regression test checks both output formats.

## Limits and next validation gate

- Report publication is atomic **per file**, not transactional across an entire set if disk writes fail mid-publication. The scan-before-write fix prevents incomplete sets caused by later **input parse failures**.
- v0.11 protections against symlink/hard-link report clobbering and unsupported extended-attribute/interleaved ISO9660 layouts remain in place.
- Real PS2/PSP game images have **not** been scanned or verified with this release. Do not infer game platform/build identity from filenames alone.
- The private package SHA-256 is `6d7a8df3f25b3e3dc1ff8832e581e23c0c50ad0b9a23ccf0e284ec6fab9e22d6`. Verify the archive before testing.
- Next: run `python -m unittest discover -v` (expect 47 tests), scan the four privately owned images, independently check sample file hashes with a second ISO9660 tool, and return non-copyrighted reports only. Never publish game ISOs or extracted assets.

This note documents only changes verified locally on synthetic fixtures; it does not claim real-hardware or real-image compatibility.

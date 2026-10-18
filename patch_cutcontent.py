"""Cut Content Patch for Manhunt 2 (PS2, USA) — separate layer

Removes cut weapons from spawning in levels and removes references to cut
environment executions. Applies to a patched or unpatched retail ISO as a separate
layer. Only modifies files in place with length-preserving edits where possible.

This is a work-in-progress; verify against your own copy before using.

Usage:
    py patch_cutcontent.py apply <iso>
    py patch_cutcontent.py verify <iso>
    py patch_cutcontent.py revert <iso>
"""
import struct
import sys

SECTOR = 2048
PVD_SECTOR = 16

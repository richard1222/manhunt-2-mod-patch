"""Create a separate 60fps patch layer.

The ELF has 10 occurrences of float 30.0. The task is to add a 60fps patch
*after* the cut-content work. This should be a new, separate script
(patch_60fps.py) — a layer, applied to the ISO just like the filter patch.

Also, changing 30.0→60.0 isn't always correct (some code uses 1.0/30.0, or
compares against timer units). But a common, simple 60fps patch for many games
is to double the framerate by replacing the delta/target 30.0 with 60.0. Let us
create a reversible, in-place patcher that patches only the 30.0 literals, can
revert, and verify. Since the binary changes, we need to track restore data like
the existing patch_iso.py does.
"""
import os
import struct
import sys

sys.path.insert(0, r"<repo>")
import ps2iso

ISO_PATH = r"Manhunt 2 (USA).iso"
RESTORE_EXT = ".60fps.orig"

BASE = 0xFF000  # vaddr = file_offset + BASE for this ELF

USAGE = """patch_60fps.py - 60fps patch layer for Manhunt 2 (USA SLUS_216.13)
Usage:
  py patch_60fps.py apply <iso>
  py patch_60fps.py revert <iso>
  py patch_60fps.py verify <iso>
"""


def locate_elf_lba(iso):
    # Find /SLUS_216.13
    def walk(entry, prefix):
        for e in iso.read_dir(entry):
            name = e.name.split(";")[0]
            if name in (".", ".."):
                continue
            p = prefix + "/" + name
            if e.is_dir:
                walk(e, p)
            elif name == "SLUS_216.13":
                return e.lba * 2048, e.size
        return None

    res = walk(iso.root, "")
    if not res:
        raise SystemExit("SLUS_216.13 not found")
    return res


def apply(iso_path):
    iso = ps2iso.PS2ISO(iso_path)
    off, size = locate_elf_lba(iso)
    with open(iso_path, "r+b") as f:
        f.seek(off)
        elf = f.read(size)
    f30 = struct.pack("<f", 30.0)
    f60 = struct.pack("<f", 60.0)
    locs = []
    s = 0
    while True:
        i = elf.find(f30, s)
        if i < 0:
            break
        locs.append(i)
        s = i + 4
    locs = sorted(set(locs))
    if not locs:
        print("No 30.0 literals found.")
        return
    restore = []
    patched = bytearray(elf)
    for i in locs:
        restore.append((i, patched[i:i + 4]))
        patched[i:i + 4] = f60
    restore_path = iso_path + RESTORE_EXT
    with open(restore_path, "wb") as rf:
        for i, b in restore:
            rf.write(struct.pack("<II", i, len(b)))
            rf.write(b)
    print("restore saved to %s (%d entries)" % (restore_path, len(restore)))
    with open(iso_path, "r+b") as f:
        f.seek(off)
        f.write(patched)
    print("patched %d 30.0->60.0 in SLUS_216.13 @ 0x%X" % (len(locs), off))
    print("virtual addrs: " + ", ".join("0x%08X" % (i + BASE) for i in locs))


def revert(iso_path):
    restore_path = iso_path + RESTORE_EXT
    if not os.path.exists(restore_path):
        print("no restore block: %s" % restore_path)
        return
    iso = ps2iso.PS2ISO(iso_path)
    off, size = locate_elf_lba(iso)
    with open(iso_path, "r+b") as f:
        f.seek(off)
        elf = bytearray(f.read(size))
    with open(restore_path, "rb") as rf:
        while True:
            hdr = rf.read(8)
            if not hdr:
                break
            i, n = struct.unpack("<II", hdr)
            b = rf.read(n)
            elf[i:i + n] = b
    with open(iso_path, "r+b") as f:
        f.seek(off)
        f.write(elf)
    os.remove(restore_path)
    print("reverted SLUS_216.13 from %s" % restore_path)


def verify(iso_path):
    iso = ps2iso.PS2ISO(iso_path)
    off, size = locate_elf_lba(iso)
    with open(iso_path, "rb") as f:
        f.seek(off)
        elf = f.read(size)
    f30 = struct.pack("<f", 30.0)
    f60 = struct.pack("<f", 60.0)
    c30 = elf.count(f30)
    c60 = elf.count(f60)
    print("30.0=%d 60.0=%d  (patched would be 30.0=0, 60.0=%d)" %
          (c30, c60, 10 + c60 - c30) if c30 == 10 else
          ("30.0=%d 60.0=%d" % (c30, c60)))
    print("looks %s" % ("PATCHED" if c30 == 0 else "UNPATCHED"))


def main(a):
    if len(a) < 2:
        print(USAGE)
        return 1
    cmd, iso_path = a[0], a[1]
    if cmd == "apply":
        apply(iso_path)
    elif cmd == "revert":
        revert(iso_path)
    elif cmd == "verify":
        verify(iso_path)
    else:
        print(USAGE)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""patch_60fps.py - frame-rate layer: WITHDRAWN, kept for evidence and revert.

This script no longer patches anything and never claims a framerate change.

Why the layer was withdrawn
---------------------------
An earlier revision replaced the ten ``30.0`` floats in ``SLUS_216.13`` with
``60.0``.  Those ten literals are gameplay tuning constants that live in the
float constant pool (``0x3F87xx``-``0x3FBFxx``), not a frame timer, so the swap
is not a 60fps patch.

The replacement target suggested later - the ``60.0f`` compare at virtual
address ``0x39BAA8`` - is also not a framerate limiter.  It is CRI ADX audio
library code:

*   the function containing it (entry ``0x39B990``) asserts with the string
    ``E02080815 adxt_GetTime: parameter error`` (referenced at ``0x39B9D4``);
*   the next assert in the same module is
    ``E06022201 adxt_Create: Work size is too short.`` (``0x47B120``);
*   the ``60.0f`` and its ``-60.0f`` twin are the two sides of a symmetric
    sanity window on an audio-time ratio: the code computes
    ``((A/B) - (*out/C)) * 10000.0`` and resyncs only when the result leaves
    ``[-60.0, 60.0]``.

Changing it alters ADX audio-time resync, not the display rate.  No safe
single-site framerate change was found, so the 60 fps layer is dropped rather
than shipped.

Address mapping: the boot ELF has a single ``PT_LOAD`` (``p_offset 0x1000``,
``p_vaddr 0x00100000``), so ``file_offset = vaddr - 0xFF000``; ``0x39BAA8`` is
file offset ``0x29CAA8``.

Usage
    py patch_60fps.py audit  "Manhunt 2 (USA).iso"   # evidence, no writes
    py patch_60fps.py status "Manhunt 2 (USA).iso"   # old swap applied?
    py patch_60fps.py revert "Manhunt 2 (USA).iso"   # undo the old swap
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps2iso

ISO_PATH = (os.environ.get("MH2_RETAIL")
            or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            os.pardir, "Manhunt 2 (USA).iso"))
RESTORE_EXT = ".60fps.orig"

BASE = 0xFF000  # vaddr = file_offset + BASE for this ELF
ADX_ASSERT_STR = 0x47B1F0
ADX_CREATE_STR = 0x47B120
PROPOSED_SITE = 0x39BAA8

USAGE = __doc__


def v2o(v):
    return v - BASE


def o2v(o):
    return o + BASE


def locate_elf(iso):
    """Return (file_offset, size) of the boot ELF inside the image."""
    hit = []

    def walk(entry):
        for e in iso.read_dir(entry):
            name = e.name.split(";")[0]
            if e.is_dir:
                walk(e)
            elif name == "SLUS_216.13":
                hit.append((e.lba * 2048, e.size))

    walk(iso.root)
    if not hit:
        raise SystemExit("SLUS_216.13 not found")
    return hit[0]


def read_elf(iso_path):
    iso = ps2iso.PS2ISO(iso_path)
    off, size = locate_elf(iso)
    with open(iso_path, "rb") as f:
        f.seek(off)
        return off, f.read(size)


def elf_info(elf):
    """Confirm the single-PT_LOAD mapping this tool relies on."""
    e_phoff = struct.unpack_from("<I", elf, 0x1C)[0]
    e_phnum = struct.unpack_from("<H", elf, 0x2C)[0]
    loads = []
    for i in range(e_phnum):
        p = elf[e_phoff + i * 32:e_phoff + i * 32 + 32]
        t, o, va, pa, fs, ms, fl, al = struct.unpack("<8I", p)
        if t == 1:
            loads.append((o, va, fs))
    if len(loads) != 1 or loads[0][1] - loads[0][0] != BASE:
        raise SystemExit("unexpected ELF load layout %r; update BASE" % (loads,))
    return loads[0]


def str_at(elf, vaddr):
    o = v2o(vaddr)
    end = elf.find(b"\x00", o)
    return elf[o:end].decode("latin1")


def float_sites(elf, value):
    pat = struct.pack("<f", value)
    out, s = [], 0
    while True:
        i = elf.find(pat, s)
        if i < 0:
            break
        out.append(i)
        s = i + 1
    return out


def audit(iso_path):
    off, elf = read_elf(iso_path)
    load = elf_info(elf)
    print("image             %s" % iso_path)
    print("boot ELF          file offset 0x%X, %d bytes" % (off, len(elf)))
    print("only PT_LOAD      off 0x%X vaddr 0x%X filesz 0x%X" % load)
    print("mapping           vaddr = file_offset + 0x%X" % BASE)

    v = PROPOSED_SITE
    raw = struct.unpack_from("<I", elf, v2o(v))[0]
    print("\nproposed 'limiter' site 0x%08X (file 0x%06X)" % (v, v2o(v)))
    print("  word 0x%08X  lui $at, 0x%04X -> 60.0f" % (raw, raw & 0xFFFF))
    print("  its function (entry 0x39B990) asserts with")
    print("    0x%08X  %r" % (ADX_ASSERT_STR, str_at(elf, ADX_ASSERT_STR)))
    print("  same module, next assert")
    print("    0x%08X  %r" % (ADX_CREATE_STR, str_at(elf, ADX_CREATE_STR)))

    print("\n30.0f literals (gameplay tuning constants; never touched)")
    for o in float_sites(elf, 30.0):
        print("  vaddr 0x%08X" % o2v(o))

    print("\nconclusion: 0x%08X is CRI ADX (adxt) audio time code," % v)
    print("not a display-rate limiter.  Layer withdrawn.")
    return 0


def status(iso_path):
    off, elf = read_elf(iso_path)
    c30 = len(float_sites(elf, 30.0))
    c60 = len(float_sites(elf, 60.0))
    print("30.0f=%d  60.0f=%d" % (c30, c60))
    print("old 30.0->60.0 swap: %s" % ("APPLIED" if c30 == 0 else "not applied"))
    return 0


def revert(iso_path):
    restore_path = iso_path + RESTORE_EXT
    if not os.path.exists(restore_path):
        print("no restore block: %s" % restore_path)
        return 1
    off, size = locate_elf(ps2iso.PS2ISO(iso_path))
    with open(iso_path, "r+b") as f:
        f.seek(off)
        elf = bytearray(f.read(size))
    with open(restore_path, "rb") as rf:
        while True:
            hdr = rf.read(8)
            if not hdr:
                break
            i, n = struct.unpack("<II", hdr)
            elf[i:i + n] = rf.read(n)
    with open(iso_path, "r+b") as f:
        f.seek(off)
        f.write(elf)
    os.remove(restore_path)
    print("reverted the boot ELF from %s" % restore_path)
    return 0


def main(a):
    if len(a) < 2:
        print(USAGE)
        return 2
    cmd, iso_path = a[0], a[1]
    if cmd == "audit":
        return audit(iso_path)
    if cmd == "status":
        return status(iso_path)
    if cmd == "revert":
        return revert(iso_path)
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

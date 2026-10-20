"""patch_60fps.py - frame-rate layer (AUDITED: deliberately not a framerate patch).

History
-------
An earlier revision replaced the ten ``30.0`` floats in SLUS_216.13 with
``60.0``.  That revision is wrong: those ten literals are gameplay tuning
constants, not a frame timer, and swapping them corrupts gameplay.  The swap is
gone.  ``revert`` still exists so an image patched by the old revision can be
restored.

The site that was proposed to replace it - the ``60.0f`` compare at virtual
address ``0x39BAA8`` - is **not** a framerate limiter either.  It lives in the
CRI ADX audio library:

*   the function containing it (entry ``0x39B990``) asserts with the string at
    ``0x47B1F0``: ``E02080815 adxt_GetTime: parameter error``;
*   the next assert in the same module, at ``0x47B120``, is
    ``E06022201 adxt_Create: Work size is too short.``;
*   the ``60.0f`` (and its ``-60.0f`` twin at ``0x39BADC``) are the two sides of
    a symmetric sanity window on an audio-time ratio: the code computes
    ``((A/B) - (*out/C)) * 10000.0`` and resyncs only when it leaves
    ``[-60.0, 60.0]``.

Changing it alters ADX audio-time resync, not the display rate.

Address mapping: the ELF has a single PT_LOAD (``p_offset 0x1000``,
``p_vaddr 0x00100000``), so ``file_offset = vaddr - 0xFF000``.  For ``0x39BAA8``
that is ``0x29CAA8`` (the value ``0x2FCAA8`` seen in an earlier report is off by
``0x60000``).

Usage
    py patch_60fps.py audit  <iso>     # evidence, no writes
    py patch_60fps.py status <iso>     # is the old 30.0->60.0 swap applied?
    py patch_60fps.py revert <iso>     # undo the old swap
    py patch_60fps.py xpatch <iso> <vaddr-hex> <value-hex>   # single word, saved
    py patch_60fps.py xrevert <iso>

``xpatch`` exists because a targeted one-word experiment is the safe way to
test a hypothesis on hardware; it always writes a restore block first.  It does
not claim to be a 60fps patch.
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
XPATCH_EXT = ".xpatch.orig"

BASE = 0xFF000  # vaddr = file_offset + BASE for this ELF
ADX_ASSERT_REF = 0x39B9D4       # lui $a0, 0x48 here ...
ADX_ASSERT_STR = 0x47B1F0       # ... -> "adxt_GetTime: parameter error"
PROPOSED_SITE = 0x39BAA8        # the 60.0f compare that was proposed as "the limiter"

USAGE = __doc__


def v2o(v):
    return v - BASE


def o2v(o):
    return o + BASE


def locate_elf(iso):
    """Return (file_offset, size) of SLUS_216.13 inside the image."""
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
    """Confirm the single-PT_LOAD mapping the tool assumes."""
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


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def audit(iso_path):
    off, elf = read_elf(iso_path)
    load = elf_info(elf)
    print("image            %s" % iso_path)
    print("ELF at file offset 0x%X, %d bytes" % (off, len(elf)))
    print("only PT_LOAD: off 0x%X vaddr 0x%X filesz 0x%X" % load)
    print("mapping          vaddr = file_offset + 0x%X" % BASE)

    print("\nproposed 'limiter' site")
    v = PROPOSED_SITE
    print("  vaddr 0x%08X -> file offset 0x%06X" % (v, v2o(v)))
    raw = struct.unpack_from("<I", elf, v2o(v))[0]
    print("  word 0x%08X  (lui $at, 0x%04X -> float %.4f)"
          % (raw, raw & 0xFFFF,
             struct.unpack("<f", struct.pack("<I", (raw & 0xFFFF) << 16))[0]))
    print("  containing function entry 0x39B990 asserts with the string at")
    print("    0x%08X  %r" % (ADX_ASSERT_STR, str_at(elf, ADX_ASSERT_STR)))
    print("  neighbours: 0x47B120 %r" % str_at(elf, 0x47B120))

    print("\n30.0f literals (NOT a frame timer; left alone)")
    for o in float_sites(elf, 30.0):
        print("  vaddr 0x%08X" % o2v(o))

    print("\nconclusion: 0x%08X is CRI ADX (adxt) audio time code." % v)
    print("It cannot be turned into a display-rate change.")
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
    print("reverted SLUS_216.13 from %s" % restore_path)
    return 0


def xpatch(iso_path, vaddr, value):
    """Experimental: write one 32-bit word, saving a restore block first."""
    v = int(vaddr, 16)
    val = int(value, 16) & 0xFFFFFFFF
    off, elf = read_elf(iso_path)
    elf_info(elf)
    o = v2o(v)
    if not (0 <= o <= len(elf) - 4):
        raise SystemExit("vaddr 0x%X is outside the ELF" % v)
    old = elf[o:o + 4]
    new = struct.pack("<I", val)
    with open(iso_path + XPATCH_EXT, "wb") as rf:
        rf.write(struct.pack("<II", o, 4))
        rf.write(old)
    with open(iso_path, "r+b") as f:
        f.seek(off + o)
        f.write(new)
    print("xpatch: 0x%08X (file 0x%X) %s -> %s"
          % (v, o, old.hex(" "), new.hex(" ")))
    print("restore block: %s" % (iso_path + XPATCH_EXT))
    return 0


def xrevert(iso_path):
    path = iso_path + XPATCH_EXT
    if not os.path.exists(path):
        print("no restore block: %s" % path)
        return 1
    off, size = locate_elf(ps2iso.PS2ISO(iso_path))
    with open(path, "rb") as rf:
        o, n = struct.unpack("<II", rf.read(8))
        old = rf.read(n)
    with open(iso_path, "r+b") as f:
        f.seek(off + o)
        f.write(old)
    os.remove(path)
    print("xrevert: restored 4 bytes at file offset 0x%X" % o)
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
    if cmd == "xpatch" and len(a) >= 4:
        return xpatch(iso_path, a[2], a[3])
    if cmd == "xrevert":
        return xrevert(iso_path)
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

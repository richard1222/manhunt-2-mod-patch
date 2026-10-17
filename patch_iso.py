"""Uncensor patch for the Manhunt 2 PS2 ISO (USA, SLUS_216.13).

The execution censorship is a "colour ramp" post-FX the engine applies while a
kill plays: the screen is tinted red and the gore hides behind the tint.  It is
configured entirely by three keys in GLOBAL/LVLSETUP.INI:

    EXECUTION_COLRAMP_TEXTURE      FE_execramps
    EXECUTION_COLRAMP_FLASH_TIMES  0.25, 0.6, 0.3   # fadein, hold, fadeout (sec)
    EXECUTION_COLRAMP_FADE_TIME    5.0

How the fix was established
---------------------------
Comparing the retail disc against the "MANHUNT 2 NOKILLFILTER" community release
(smitty.dmg, archive.org) -- a build verified to remove the red filter on real
PS2/PS3 hardware -- shows the two images are identical in all 587 of their files
except GLOBAL/LVLSETUP.INI, and there the mod *deletes this whole block*:

    # ----------------------------------------------------------------------
    #  [GK] execution colour ramp options: flash fadein, duration, fadeout
        EXECUTION_COLRAMP_TEXTURE      FE_execramps
        EXECUTION_COLRAMP_FLASH_TIMES  0.25, 0.6, 0.3
        EXECUTION_COLRAMP_FADE_TIME    5.0

With those keys absent the engine builds no execution ramp at all, so there is
no red filter.  The boot ELF is byte-identical -- this is purely a data change.

Shortening or zeroing the *timings* does not help: the ramp is still built, just
brief.  That is why the prototype/PSP-style timing tweak leaves a visible tint.

Variants
--------
    nofilter  (default) comment out the three keys, so the engine parses no
              execution ramp -- the same effect as the community release's
              deletion, but as an in-place edit.
    proto     restore the prototype's faint-flash timings (leaves a faint red
              filter; reference only).
    zero      zero the flash + fade durations (leaves the ramp built; reference
              only).

All variants are pure in-place byte swaps of exactly the same length: no
ISO9660 directory record, file size or sector layout changes.

Usage:
    py patch_iso.py apply  <iso> [variant]   patch in place, records a .orig block
    py patch_iso.py verify <iso>             report which state the image is in
    py patch_iso.py revert <iso>             restore the original bytes from .orig
"""
import sys
import struct

SECTOR = 2048
PVD_SECTOR = 16

# --- what we change ---------------------------------------------------------
# (old_bytes, new_bytes) -- every pair MUST be the same length.
VARIANTS = {
    # THE fix.  Commenting the keys out keeps the file exactly the same length
    # while making the parser see no execution-colour-ramp record at all --
    # identical in effect to the community release that deletes these lines.
    "nofilter": [
        (b"\tEXECUTION_COLRAMP_TEXTURE", b"#EXECUTION_COLRAMP_TEXTURE"),
        (b"\tEXECUTION_COLRAMP_FLASH_TIMES", b"#EXECUTION_COLRAMP_FLASH_TIMES"),
        (b"\tEXECUTION_COLRAMP_FADE_TIME", b"#EXECUTION_COLRAMP_FADE_TIME"),
    ],
    # Reference only: pre-release prototype timings (still a faint filter).
    "proto": [
        (b"EXECUTION_COLRAMP_FLASH_TIMES\t0.25, 0.6, 0.3",
         b"EXECUTION_COLRAMP_FLASH_TIMES\t0.05, 0.05,0.1"),
    ],
    # Reference only: zero durations (ramp still built).
    "zero": [
        (b"EXECUTION_COLRAMP_FLASH_TIMES\t0.25, 0.6, 0.3",
         b"EXECUTION_COLRAMP_FLASH_TIMES\t0.0,  0.0, 0.0"),
        (b"EXECUTION_COLRAMP_FADE_TIME\t\t5.0",
         b"EXECUTION_COLRAMP_FADE_TIME\t\t0.0"),
    ],
}
DEFAULT_VARIANT = "nofilter"


def both32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def walk(iso, lba, size, want):
    """Find `want` inside the directory at (lba, size). Returns entry or None.

    Skips the '.' (raw name 0x00) and '..' (0x01) records; a zero-length
    record means the directory extent is exhausted.
    """
    iso.seek(lba * SECTOR)
    data = iso.read(size)
    off = 0
    while off + 33 < len(data):
        rec_len = data[off]
        if rec_len == 0:
            break
        nlen = data[off + 32]
        rawname = data[off + 33: off + 33 + nlen]
        if not (nlen == 1 and rawname in (b"\x00", b"\x01")):
            flags = data[off + 25]
            lba_ = struct.unpack_from("<I", data, off + 2)[0]
            size_ = struct.unpack_from("<I", data, off + 10)[0]
            name = rawname.decode("ascii", "replace").split(";")[0]
            if name.upper() == want.upper():
                return {"lba": lba_, "size": size_,
                        "is_dir": bool(flags & 2), "name": name}
        off += rec_len
    return None


def locate(iso):
    """Return (lba, size) of GLOBAL/LVLSETUP.INI by walking the volume."""
    iso.seek(PVD_SECTOR * SECTOR)
    pvd = iso.read(SECTOR)
    if pvd[1:6] != b"CD001":
        raise SystemExit("not an ISO9660 volume")
    root_lba = both32(pvd, 158)
    root_size = both32(pvd, 166)
    g = walk(iso, root_lba, root_size, "GLOBAL")
    if g is None or not g["is_dir"]:
        raise SystemExit("GLOBAL/ not found")
    f = walk(iso, g["lba"], g["size"], "LVLSETUP.INI")
    if f is None:
        raise SystemExit("GLOBAL/LVLSETUP.INI not found")
    return f["lba"], f["size"]


def _state(data):
    """Classify the INI content: 'original' or the name of a patched variant."""
    for name, repl in VARIANTS.items():
        if all(new in data for _, new in repl):
            return name
    return "original"


def cmd_apply(path, variant):
    repl = VARIANTS[variant]
    with open(path, "r+b") as iso:
        lba, size = locate(iso)
        iso.seek(lba * SECTOR)
        data = bytearray(iso.read(size))

        missing = [old for old, _ in repl if old not in data]
        if missing:
            state = _state(data)
            if state != "original":
                print("already patched (%s)" % state)
                return 0
            raise SystemExit("censorship block not found -- different disc build?")

        # Save a restore block next to the ISO before touching anything.
        restore = path + ".orig"
        with open(restore, "wb") as rf:
            rf.write(struct.pack("<II", lba, size))
            for old, _ in repl:
                i = data.find(old)
                rf.write(struct.pack("<II", i, len(old)))
                rf.write(old)
            rf.write(struct.pack("<I", 0xFFFFFFFF))  # terminator
        print("restore block ->", restore)

        before = bytes(data)
        for old, new in repl:
            assert len(old) == len(new), "replacement length mismatch"
            i = data.find(old)
            data[i:i + len(old)] = new
            print("  0x%08X  %s -> %s" % (lba * SECTOR + i, old.decode(), new.decode()))

        iso.seek(lba * SECTOR)
        iso.write(data)
        iso.flush()

        # verify from disk
        iso.seek(lba * SECTOR)
        after = iso.read(size)
        changed = [i for i in range(size) if before[i] != after[i]]
        print("patched GLOBAL/LVLSETUP.INI (lba %d, %d bytes), %d bytes changed"
              % (lba, size, len(changed)))
        for _, new in repl:
            assert new in after
        print("OK -- variant '%s'" % variant)
    return 0


def cmd_verify(path):
    with open(path, "rb") as iso:
        lba, size = locate(iso)
        iso.seek(lba * SECTOR)
        data = iso.read(size)
    state = _state(data)
    print("lba %d  size %d" % (lba, size))
    print("state  :", state)
    return 0 if state != "original" else 1


def cmd_revert(path):
    restore = path + ".orig"
    try:
        rf = open(restore, "rb")
    except OSError:
        raise SystemExit("no restore block: %s" % restore)
    with rf:
        lba, size = struct.unpack("<II", rf.read(8))
        edits = []
        while True:
            raw = rf.read(8)
            if len(raw) < 8:
                break
            i, n = struct.unpack("<II", raw)
            if i == 0xFFFFFFFF:
                break
            edits.append((i, rf.read(n)))
    with open(path, "r+b") as iso:
        iso.seek(lba * SECTOR)
        data = bytearray(iso.read(size))
        for i, old in edits:
            data[i:i + len(old)] = old
        iso.seek(lba * SECTOR)
        iso.write(data)
        iso.flush()
    print("reverted %d edit(s)" % len(edits))
    return 0


def main(a):
    if not a or a[0] not in ("apply", "verify", "revert"):
        print(__doc__)
        return 2
    cmd = a[0]
    if cmd == "revert":
        if len(a) < 2:
            print(__doc__)
            return 2
        return cmd_revert(a[1])
    if len(a) < 2:
        print(__doc__)
        return 2
    variant = a[2] if len(a) > 2 else DEFAULT_VARIANT
    if variant not in VARIANTS:
        raise SystemExit("unknown variant %r (choose from %s)"
                         % (variant, ", ".join(VARIANTS)))
    if cmd == "apply":
        return cmd_apply(a[1], variant)
    return cmd_verify(a[1])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

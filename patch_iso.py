"""Remove the red execution "colour ramp" filter from Manhunt 2 (PS2, USA).

The filter
----------
While an execution plays, retail Manhunt 2 draws the whole screen through a
colour ramp: the picture is tinted red and the gore happens behind the tint.  It
is set up by three keys in GLOBAL/LVLSETUP.INI:

    EXECUTION_COLRAMP_TEXTURE       FE_execramps
    EXECUTION_COLRAMP_FLASH_TIMES   0.25, 0.6, 0.3
    EXECUTION_COLRAMP_FADE_TIME     5.0

The ramp is not a tint and it is not a scale factor -- it *replaces* colour.  The
engine builds a lookup from one row of the named texture (the `*_RAMP_ROW` key
picks the row) and draws the frame through it: a pixel comes out as the ramp's
entry for that pixel's luminance and nothing else.  Measured on hardware, overwriting FE_execramps with the grey
identity ramp -- output level i is (i,i,i) -- gives a full-screen black-and-white
execution at full detail: the picture's brightness survives, its colour does not.
Whatever the row holds *becomes* the picture, so a ramp can change the tint --
that is what FE_execramps is for -- but it can never leave the colour alone.
The texture sets the tint; it cannot remove it.

The lever that does work is the ramp's *name*: removing the filter means stopping
the engine resolving a ramp for the execution.

The fix
-------
Both execution ramp names are left present on their retail lines, but emptied:

    retail                                        patched
    EXECUTION_COLRAMP_TEXTURE  FE_execramps        EXECUTION_COLRAMP_TEXTURE  <spaces>
    BOOKEND_RAMP_TEXTURE       FE_genramps         BOOKEND_RAMP_TEXTURE       <spaces>

A name of only spaces is not a texture the game can find, so no execution ramp
resolves, nothing is drawn through a lookup, and the execution plays in full
colour.

Each name is replaced by the same number of spaces, so both edits keep the length
of the text they replace.  `FE_execramps` is 12 bytes, `FE_genramps` is 11, and
the key, its separators and the CR terminator are left exactly as retail wrote
them.  GLOBAL/LVLSETUP.INI is therefore patched in place: its size, its ISO9660
record and the disc layout do not move, and this is the only file written.
SLUS_216.13 and GLOBAL/PICS/GLOBAL.TXD are byte-identical to retail -- the patch
changes no code and rebuilds no container.

Why BOOKEND_RAMP_TEXTURE is emptied too
---------------------------------------
The execution ramp is not the only one retail arms.  Retail also defines

    BOOKEND_RAMP_TEXTURE   FE_genramps
    BOOKEND_RAMP_ROW       4

under "Ramp used for bookends" (LVLSETUP.INI line 16), a key set the pre-release
prototype disc does not have at all -- and the game's first execution is a
*bookend* execution (BOOKEND_EXECUTION_OBJECT A00_BookendB in the mission-1
script).  Emptying only the execution ramp leaves that first kill read through
FE_genramps.  Blanking both keys is what makes the first execution behave like
every later one.

Why the timing keys are left alone
----------------------------------
EXECUTION_COLRAMP_FLASH_TIMES and EXECUTION_COLRAMP_FADE_TIME stay at retail.
They have nothing to grade once no ramp resolves, and they are the wrong thing to
reach for:

*   EXECUTION_COLRAMP_FLASH_TIMES is not a fade-in.  0x3670D0, the arm the
    object-interaction flash handler calls, stores the numbers into the engine's
    ramp timer at 0x3FC9E8 as a *duration* (retail 0.25 + 0.6 = 0.85 s).  The
    community PS2 recipe stretches them to "200., 0.6, 0.3" to keep a missing ramp
    from flashing the screen black.  On hardware that value walks into the next
    freeze: the flash is fired by ordinary object interactions, not only by
    kills, so the 200 s timer outlives the execution and closing a door -- which
    runs the same call -- locks the console up.  Stock timing, with both names
    emptied, plays through.

*   EXECUTION_COLRAMP_FADE_TIME only shapes the tail of a grade that no longer
    happens.  Driven to 0.01 it goes sub-frame and sticks the engine at full,
    washing an execution white.

The retail values are also the safest possible: the patch leaves the timing
behaviour of the shipped game untouched.

The ramp slots, for reference
-----------------------------
The engine keeps a stack of five ramp slots in '.bss' at 0x6C1D58, eight bytes
an entry (a texture handle and a row), plus a top index at 0x3FC9F0.  The
renderer 0x3672D0 walks down from the top and applies the first entry that
resolves, and it *skips* a null entry (beqz $a0, 0x367328) -- so an empty name
leaves the engine in exactly the state ordinary, non-execution play runs in.  The
registration sites name the slots:

    slot 0   FE_genramps row 1                 0x319C24  (engine default)
    slot 1   BASE_RAMP_TEXTURE / _ROW          0x316298, 0x315A44
    slot 2   HIDE_RAMP_TEXTURE / _ROW          0x2E7778
    slot 3   EXECUTION_COLRAMP_TEXTURE         0x2E7864
    slot 4   BOOKEND_RAMP_TEXTURE / _ROW       0x3162AC, 0x315A58

Two traps, recorded so they are not re-tried
--------------------------------------------
*   The frame latch 0x3FC9B0 looks like an "is a ramp active" switch and is not
    one: the lookup the frame is drawn with is built *inside* the code the latch
    gates, so forcing it clear comes up to a black screen and stays there.

*   The colour flash does not go through the slot stack.  0x1D0034 builds a
    random row of the execution ramp and hands it straight to 0x3670D0, which
    writes the selection globals and calls the lookup builder itself; that path
    has no null check of its own.  It fires on ordinary object interactions, not
    only during a kill, so nop'ing it freezes the console in mission 1's office
    area.

    This patch cannot reach either trap, because it runs no code and changes no
    timing.  The engine's own behaviour with no ramp resolved is the state the
    game is in for the rest of the disc.

Tested on hardware
------------------
PS3 Slim 2001A on CFW 4.93 (Evilnat), through its PS2 emulator: every execution
plays in full colour, including the mission-1 bookend execution, and the game
runs through the 3-door gate sequence and the dumpster truck area with no freeze.
The boot ELF was confirmed byte-identical to retail on the same image.

Usage
-----
    py patch_iso.py apply  <iso>   patch in place; writes <iso>.orig first
    py patch_iso.py verify <iso>   report the current state
    py patch_iso.py revert <iso>   restore the original bytes from <iso>.orig

One region is written, GLOBAL/LVLSETUP.INI, at the size it already is.  The
restore block holds that region's original bytes, and a later apply merges into
it rather than replacing it.

Requires: nothing but the Python 3 standard library.
"""
import struct
import sys

SECTOR = 2048
PVD_SECTOR = 16
ELF_NAME = "SLUS_216.13"
INI_DIR = ["GLOBAL", "LVLSETUP.INI"]

# Each ramp line: the retail prefix (key plus separators) and the texture name it
# ends with.  The name is rewritten as one space per character, so the edit is
# length-preserving and nothing on the line moves but the name itself.
BLANK_RAMPS = [
    # retail: \tEXECUTION_COLRAMP_TEXTURE\t\tFE_execramps
    (b"\tEXECUTION_COLRAMP_TEXTURE\t\t", b"FE_execramps"),
    # retail: \tBOOKEND_RAMP_TEXTURE \tFE_genramps   (space before the tab)
    (b"\tBOOKEND_RAMP_TEXTURE \t", b"FE_genramps"),
]

INI_EDITS = [(prefix + name, prefix + b" " * len(name))
             for prefix, name in BLANK_RAMPS]


# --- ISO9660 ----------------------------------------------------------------
def walk(iso, lba, size, want):
    """Find `want` in the directory extent at (lba, size).  Returns entry or None.

    The '.' and '..' records (raw names 0x00 and 0x01) are skipped, and a
    zero-length record ends the extent.
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


def locate(iso, parts):
    """Return (lba, size) for a path such as ["GLOBAL", "LVLSETUP.INI"]."""
    iso.seek(PVD_SECTOR * SECTOR)
    pvd = iso.read(SECTOR)
    if pvd[1:6] != b"CD001":
        raise SystemExit("not an ISO9660 volume")
    lba = struct.unpack_from("<I", pvd, 158)[0]
    size = struct.unpack_from("<I", pvd, 166)[0]
    for want in parts:
        entry = walk(iso, lba, size, want)
        if entry is None:
            raise SystemExit("not on disc: %s" % want)
        lba, size = entry["lba"], entry["size"]
    return lba, size


def read_file_at(iso, lba, size):
    iso.seek(lba * SECTOR)
    return iso.read(size)


# --- the INI ----------------------------------------------------------------
def patch_ini(data, edits=INI_EDITS):
    """Apply `edits` to `data`.  Returns (patched, [(old, new), ...]).

    Every edit must match exactly once and keep its byte length, so the file size
    and its ISO9660 record never change.
    """
    out = data
    applied = []
    for old, new in edits:
        if len(old) != len(new):
            raise SystemExit("INI edit changes length: %r -> %r" % (old, new))
        found = out.count(old)
        if found != 1:
            raise SystemExit("expected exactly one %r, found %d" % (old, found))
        out = out.replace(old, new, 1)
        applied.append((old, new))
    return out, applied


def is_patched(ini):
    return all(new in ini and old not in ini for old, new in INI_EDITS)


# --- restore block ----------------------------------------------------------
def save_restore(path, regions):
    """Write <path>.orig holding each original region as (lba, bytes).

    An existing block is merged rather than replaced, so patching another region
    later does not lose the earlier region's original bytes.
    """
    try:
        keep = load_restore(path)
    except OSError:
        keep = []
    by_lba = {lba: data for lba, data in keep}
    for lba, data in regions:
        by_lba.setdefault(lba, data)
    with open(path + ".orig", "wb") as rf:
        rf.write(struct.pack("<I", len(by_lba)))
        for lba, data in by_lba.items():
            rf.write(struct.pack("<II", lba, len(data)))
            rf.write(data)


def load_restore(path):
    with open(path + ".orig", "rb") as rf:
        n = struct.unpack("<I", rf.read(4))[0]
        regions = []
        for _ in range(n):
            lba, size = struct.unpack("<II", rf.read(8))
            regions.append((lba, rf.read(size)))
        return regions


# --- commands ---------------------------------------------------------------
def cmd_apply(path):
    with open(path, "r+b") as iso:
        lba, size = locate(iso, INI_DIR)
        ini = read_file_at(iso, lba, size)
        if is_patched(ini):
            print("LVLSETUP.INI already carries both edits -- nothing to do")
            return 0
        ini_new, applied = patch_ini(ini)
        if len(ini_new) != size:
            raise SystemExit("INI size changed: %d -> %d" % (size, len(ini_new)))

        save_restore(path, [(lba, ini)])
        print("restore block ->", path + ".orig")

        iso.seek(lba * SECTOR)
        iso.write(ini_new)
        if read_file_at(iso, lba, size) != ini_new:
            raise SystemExit("INI write-back verification failed")
        iso.flush()

    print("LVLSETUP.INI (lba %d, %d bytes): %d edit(s), size unchanged"
          % (lba, size, len(applied)))
    for old, _new in applied:
        name = old.split(b"\t")[-1]
        print("  ramp name %-14s emptied in place" % name.decode())
    print("SLUS_216.13 and GLOBAL/PICS/GLOBAL.TXD untouched")
    return 0


def cmd_verify(path):
    with open(path, "rb") as iso:
        lba, size = locate(iso, INI_DIR)
        ini = read_file_at(iso, lba, size)

    print("LVLSETUP.INI  lba %d  size %d" % (lba, size))
    for old, new in INI_EDITS:
        state = ("emptied" if new in ini and old not in ini else
                 "retail" if old in ini else "unexpected")
        print("  %-26s %s" % (old.split(b"\t")[1].strip().decode(), state))
    print("  ramp lines:")
    for line in ini.split(b"\n"):
        if b"RAMP" in line:
            print("    %r" % line)
    print("  state: %s" % ("patched" if is_patched(ini) else "retail/original"))
    return 0 if is_patched(ini) else 1


def cmd_revert(path):
    try:
        regions = load_restore(path)
    except OSError:
        raise SystemExit("no restore block: %s" % (path + ".orig"))
    with open(path, "r+b") as iso:
        for lba, data in regions:
            iso.seek(lba * SECTOR)
            iso.write(data)
        iso.flush()
    print("reverted %d region(s)" % len(regions))
    return 0


def main(argv):
    if len(argv) < 2 or argv[0] not in ("apply", "verify", "revert"):
        print(__doc__)
        return 2
    return {"apply": cmd_apply, "verify": cmd_verify,
            "revert": cmd_revert}[argv[0]](argv[1])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Remove the red execution "colour ramp" filter from Manhunt 2 (PS2, USA).

What the filter is
------------------
While an execution plays, the engine puts a colour-ramp effect over the screen:
the picture is tinted red, so the gore happens behind the tint.  It is configured
by three keys in GLOBAL/LVLSETUP.INI:

    EXECUTION_COLRAMP_TEXTURE      FE_execramps
    EXECUTION_COLRAMP_FLASH_TIMES  0.25, 0.6, 0.3   # fade-in, hold, fade-out
    EXECUTION_COLRAMP_FADE_TIME    5.0

Tweaking the timings does not remove the tint: the ramp is still built and still
applies its colour for the whole execution; the timings only govern a flash and a
fade around it.  The red comes from the ramp *texture* named by the first key.

What the community does
-----------------------
The PC mod "Manhunt 2 No Execution Filter" (DeBuGWoLf) removes the effect by
pointing EXECUTION_COLRAMP_TEXTURE at a texture name that does not exist, and
restoring the pre-release flash timing.  The community PS2 release
"MANHUNT 2 NOKILLFILTER" deletes the three keys outright.

Neither is usable here.  A missing execution ramp makes the engine hard-freeze at
the first execution (the mission-1 bookend, BOOKEND_EXECUTION_OBJECT
A00_BookendB) on a PS3's PS2 emulator, and that is exactly what the community
release does.  The ramp therefore has to stay defined.

The fix
-------
Keep the ramp defined, and stop it replacing the picture.  The ramp texture
FE_execramps lives inside GLOBAL/PICS/GLOBAL.TXD:

    "Z2HM" | u32 uncompressed size | zlib stream  ->  "TCDT" texture dictionary

The TCDT is a linked list of 0x70-byte entries:

    +0x00  u32   offset of the next entry
    +0x08  char  NUL-terminated texture name
    +0x60  u32   offset of the texture pixels

Every texture here is 32 rows of 32 pixels, 4 bytes per pixel (pitch 0x80), and
each ramp row is a lookup across input level 0..255.  During an execution the
engine runs the picture through that lookup, and the lookup does not tint the
picture -- it replaces each pixel's colour with the ramp colour for that pixel's
level.  FE_execramps row 0 runs (5,0,0)..(215,5,5), so dark pixels come back
black and everything brighter comes back red.  That is the red.

Because the colour is replaced rather than scaled, no replacement texture can be
neutral, and that is confirmed on hardware.  A flat grey ramp of any level does
not leave the picture alone: it collapses the whole screen to that one flat tone
(flat 0 gives a black execution, flat 32 dark grey, flat 64 grey, flat 128
white).  And the grey identity ramp -- output level i is (i,i,i) -- does not come
back colourful either: it gives the execution a full-screen black-and-white
"noir" look at full detail.  That is the exact proof of the lookup: the picture's
brightness survives, its colour does not.  So there is no value to pick.

Two levers in the data remove the filter without taking the ramp away.

1.  Overwrite the ramp texture with the grey identity ramp: output level i is
    (i,i,i).  That takes the red out.  On its own it leaves the execution a
    black-and-white picture, because the lookup cannot return the original
    colour -- a grey lookup is the best any texture can do.

2.  Drive the ramp's timings down so the grade is up for only a few frames.
    The engine's ramp system is built from fade-in / hold / fade-out seconds
    plus a hold time, and EXECUTION_COLRAMP_FLASH_TIMES and
    EXECUTION_COLRAMP_FADE_TIME are those numbers.  Two measurements identified
    them on hardware: with FADE_TIME at 999 the grade stayed over sixteen
    minutes, and at 0.1 the execution went grey for only a fraction of a second,
    so the red wash over a kill is mostly this hold time.  Both are now 0.01 s,
    which leaves the ramp up for about a fortieth of a second -- under three
    frames -- so the execution plays in colour.

    These edits stay the same length by turning one of FADE_TIME's tabs into a
    space, so the INI's size, its ISO9660 record and the sector layout do not
    move.  The ramp itself stays defined, which matters: a missing ramp is what
    makes the console freeze at the first execution.

The texel alpha was tried and is not the effect's strength: with every ramp pixel
zeroed to alpha 0 the execution looked exactly as it did at alpha 255.  The engine
reads the ramp as colour and ignores the fourth byte, so this patch writes alpha 0
only as a leftover of that test.

The censored flash
------------------
Part of the censorship is in these same numbers.  Retail stretches the ramp's
fade-in / hold / fade-out to 0.25, 0.6, 0.3 (1.15 s all told) where the
pre-release prototype has 0.05, 0.05, 0.1 (0.2 s) -- a longer, stronger wash over
the kill.  This patch takes them below even the prototype, to 0.01, so the wash is
gone rather than merely shortened.  Nothing here moves in the file: both edits
keep their byte length, so the INI keeps its size, its ISO9660 record and its
sector layout.

Keeping the container byte-exact
--------------------------------
The retail TXD has no slack: its zlib stream is exactly 95263 bytes, filling the
file.  An edited dictionary will not compress to exactly that, so the stream is
rebuilt with zopfli and then padded *inside* the deflate stream -- inserted after
the 2-byte zlib header -- so that the stream is still exactly 95263 bytes and
nothing trails it.  The padding has to decode to nothing and leave the next block
byte aligned, and two units do that:

    00 00 00 FF FF       an empty stored block                        (5 bytes)
    02 00 00 00 FF FF    an empty fixed-Huffman block whose end-of-block code
                         ends mid-byte, followed by a stored block that
                         re-aligns the stream                        (6 bytes)

Both decode to zero bytes, and {5,6} can make any total length of 20 bytes or
more, so the stream fills to the byte whatever zopfli produced.  Because the
padding is whole bytes inserted, the dictionary itself never changes size: it
stays exactly 325024 bytes and the declared size does not move either.
GLOBAL.TXD keeps its exact size, so no ISO9660 record, file size or sector
layout changes.

Usage
-----
    py patch_iso.py apply  <iso>    patch in place; writes <iso>.orig first
    py patch_iso.py verify <iso>    report the current state
    py patch_iso.py revert <iso>    restore the original bytes from <iso>.orig

Requires:  pip install zopfli
"""
import struct
import sys
import zlib

try:
    import zopfli.zlib as _zopfli
except ImportError:                                     # pragma: no cover
    _zopfli = None

SECTOR = 2048
PVD_SECTOR = 16

TXD_DIR = ["GLOBAL", "PICS", "GLOBAL.TXD"]
RAMP_TEXTURE = "FE_execramps"

MAGIC = b"Z2HM"
TEXTURE_BYTES = 0x1000          # 32 rows * 0x80 pitch (32 pixels * 4 bytes)
GREY_ROW = b"".join(bytes((v, v, v, 0x00))
                    for v in (round(i * 255 / 31) for i in range(32)))
GREY_RAMP = GREY_ROW * 32       # every row: output level i is the grey (i,i,i),
                                # written with a zero alpha

# Same-length, in-place text edits to GLOBAL/LVLSETUP.INI.
INI_DIR = ["GLOBAL", "LVLSETUP.INI"]
INI_EDITS = [
    # the grade's fade-in / hold / fade-out window (retail 0.25, 0.6, 0.3)
    (b"EXECUTION_COLRAMP_FLASH_TIMES\t0.25, 0.6, 0.3",
     b"EXECUTION_COLRAMP_FLASH_TIMES\t0.01,0.01,0.01"),
    # how long the grade stays up (retail 5.0)
    (b"\tEXECUTION_COLRAMP_FADE_TIME\t\t5.0",
     b"\tEXECUTION_COLRAMP_FADE_TIME\t0.01"),
]

# Two padding units that inflate to nothing and leave the stream byte aligned:
#   EMPTY_STORED  BFINAL=0, BTYPE=00, LEN=0, NLEN=0xFFFF               5 bytes
#   FIXED_EMPTY   an empty fixed-Huffman block (10 bits: BTYPE=01 then the
#                 7-bit end-of-block code) followed by a stored block that
#                 re-aligns the stream                                   6 bytes
EMPTY_STORED = b"\x00\x00\x00\xff\xff"
FIXED_EMPTY = b"\x02\x00\x00\x00\xff\xff"
ZOPFLI_ITER = 15


def padding(pad):
    """Exactly `pad` bytes of blocks that decode to nothing.

    5- and 6-byte units between them can make any length of 20 or more (the
    largest number that is not a sum of 5s and 6s is 19), and the gap here is
    always around 11K, so this always covers it.
    """
    for six in range(0, 5):
        rest = pad - 6 * six
        if rest >= 0 and rest % 5 == 0:
            return EMPTY_STORED * (rest // 5) + FIXED_EMPTY * six
    raise SystemExit("cannot pad a %d-byte gap with 5- and 6-byte units" % pad)


# --- ISO9660 ---------------------------------------------------------------
def both32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def walk(iso, lba, size, want):
    """Find `want` inside the directory at (lba, size).  Returns entry or None.

    Skips the '.' (raw name 0x00) and '..' (0x01) records; a zero-length record
    means the directory extent is exhausted.
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
    """Return (lba, size) for a path such as ["GLOBAL", "PICS", "GLOBAL.TXD"]."""
    iso.seek(PVD_SECTOR * SECTOR)
    pvd = iso.read(SECTOR)
    if pvd[1:6] != b"CD001":
        raise SystemExit("not an ISO9660 volume")
    lba = both32(pvd, 158)
    size = both32(pvd, 166)
    for want in parts:
        entry = walk(iso, lba, size, want)
        if entry is None:
            raise SystemExit("not on disc: %s" % want)
        lba, size = entry["lba"], entry["size"]
    return lba, size


def read_file_at(iso, lba, size):
    iso.seek(lba * SECTOR)
    return iso.read(size)


# --- the texture dictionary ------------------------------------------------
def read_txd(iso):
    """Return (lba, file_size, dictionary_bytes) for GLOBAL/PICS/GLOBAL.TXD."""
    lba, size = locate(iso, TXD_DIR)
    data = read_file_at(iso, lba, size)
    if data[:4] != MAGIC:
        raise SystemExit("GLOBAL.TXD is not a Z2HM container")
    declared = struct.unpack_from("<I", data, 4)[0]
    raw = zlib.decompress(data[8:])
    if declared != len(raw):
        raise SystemExit("declared %d bytes, decompressed %d"
                         % (declared, len(raw)))
    return lba, size, raw


def ramp_offset(raw, name):
    """Pixel offset of `name` in the dictionary.

    Entries are 0x70 bytes with the NUL-terminated name at +0x08 and the pixel
    offset at +0x60, so the entry owning a name starts 8 bytes before it.
    """
    tag = name.encode("latin-1") + b"\x00"
    pos = 0
    while True:
        pos = raw.find(tag, pos)
        if pos < 0:
            break
        off = pos - 8
        if off >= 0x20:
            px = struct.unpack_from("<I", raw, off + 0x60)[0]
            if 0x100 <= px < len(raw) - TEXTURE_BYTES:
                return px
        pos += 1
    raise SystemExit("texture %r not found in GLOBAL.TXD" % name)


def build_container(raw, size):
    """Return (dictionary, 'Z2HM' container, padding) that fills `size` bytes.

    The container is MAGIC + u32(len(dictionary)) + a zlib stream of exactly
    size-8 bytes, so nothing trails the stream.  The stream is zopfli output with
    padding blocks inserted after its 2-byte header; they decode to nothing and
    keep the stream byte aligned, so the stream can be filled to the byte
    without touching the dictionary.
    """
    if _zopfli is None:
        raise SystemExit("zopfli is required: pip install zopfli")
    budget = size - 8                       # bytes the whole zlib stream may use
    stream = _zopfli.compress(raw, numiterations=ZOPFLI_ITER)
    pad = budget - len(stream)
    if pad < 0:
        raise SystemExit("compressed stream is %d bytes, %d over the %d-byte budget"
                         % (len(stream), -pad, budget))
    out = stream[:2] + padding(pad) + stream[2:]
    if len(out) != budget:
        raise SystemExit("internal error: stream is %d bytes" % len(out))
    if zlib.decompress(out) != raw:
        raise SystemExit("internal error: rebuilt stream does not inflate")
    return raw, MAGIC + struct.pack("<I", len(raw)) + out, pad


def row(raw, px, r):
    o = px + 0x80 * r
    return raw[o:o + 128]


def show_row(label, b):
    print("  %-8s %s" % (label, " ".join("%d,%d,%d" % (b[4 * i], b[4 * i + 1],
                                                       b[4 * i + 2])
                                          for i in (0, 1, 15, 31))))


# --- the INI ---------------------------------------------------------------
def patch_ini(data):
    """Apply INI_EDITS to `data`.  Returns (patched_bytes, n_applied).

    Every edit must match exactly once and keep the byte length, so the file
    size and the ISO9660 record are untouched.
    """
    out = bytearray(data)
    applied = 0
    for old, new in INI_EDITS:
        if len(old) != len(new):
            raise SystemExit("INI edit changes length: %r -> %r" % (old, new))
        n = out.count(old)
        if n != 1:
            raise SystemExit("expected exactly one %r, found %d" % (old, n))
        out[out.find(old):out.find(old) + len(old)] = new
        applied += 1
    return bytes(out), applied


# --- restore block ---------------------------------------------------------
def save_restore(path, regions):
    """Write <path>.orig holding every original region: (lba, bytes) pairs."""
    with open(path + ".orig", "wb") as rf:
        rf.write(struct.pack("<I", len(regions)))
        for lba, data in regions:
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


# --- commands --------------------------------------------------------------
def cmd_apply(path):
    regions = []
    with open(path, "r+b") as iso:
        # --- the ramp texture ---
        lba, size, raw = read_txd(iso)
        px = ramp_offset(raw, RAMP_TEXTURE)
        txd_done = raw[px:px + TEXTURE_BYTES] == GREY_RAMP

        if txd_done:
            print("%s already the zero-alpha grey identity ramp" % RAMP_TEXTURE)
        else:
            print("%s pixels at 0x%X (lba %d, %d bytes)" % (RAMP_TEXTURE, px, lba, size))
            show_row("before", row(raw, px, 0))
            patched = bytearray(raw)
            patched[px:px + TEXTURE_BYTES] = GREY_RAMP
            data, container, pad = build_container(bytes(patched), size)
            if len(container) != size:
                raise SystemExit("container is %d bytes, expected %d"
                                 % (len(container), size))
            print("rebuilt stream: zopfli(it=%d) + %d bytes of padding blocks; "
                  "dictionary %d bytes, declared size unchanged"
                  % (ZOPFLI_ITER, pad, len(data)))

        # --- the INI ---
        ini_lba, ini_size = locate(iso, INI_DIR)
        ini = read_file_at(iso, ini_lba, ini_size)
        ini_done = all(new in ini and old not in ini for old, new in INI_EDITS)
        if ini_done:
            print("LVLSETUP.INI already carries the edits")
        else:
            ini_new, n = patch_ini(ini)
            print("LVLSETUP.INI: %d/%d edit(s), %d bytes -> %d bytes"
                  % (n, len(INI_EDITS), len(ini), len(ini_new)))

        if txd_done and ini_done:
            print("nothing to do -- already patched")
            return 0

        # Save originals before touching anything.
        if not txd_done:
            regions.append((lba, read_file_at(iso, lba, size)))
        if not ini_done:
            regions.append((ini_lba, ini))
        save_restore(path, regions)
        print("restore block ->", path + ".orig")

        if not txd_done:
            iso.seek(lba * SECTOR)
            iso.write(container)
            if read_file_at(iso, lba, size) != container:
                raise SystemExit("write-back verification failed")
        if not ini_done:
            if len(ini_new) != ini_size:
                raise SystemExit("INI size changed: %d -> %d" % (ini_size, len(ini_new)))
            iso.seek(ini_lba * SECTOR)
            iso.write(ini_new)
            if read_file_at(iso, ini_lba, ini_size) != ini_new:
                raise SystemExit("INI write-back verification failed")
        iso.flush()

    print("OK -- execution ramp is the grey identity, up for 0.01s per timer "
          "instead of 5.0s; the red wash is gone")
    return 0


def cmd_verify(path):
    with open(path, "rb") as iso:
        lba, size, raw = read_txd(iso)
        px = ramp_offset(raw, RAMP_TEXTURE)
        iso.seek(lba * SECTOR)
        declared = struct.unpack_from("<I", iso.read(8), 4)[0]
        ini_lba, ini_size = locate(iso, INI_DIR)
        ini = read_file_at(iso, ini_lba, ini_size)

    neutral = sum(1 for r in range(32) if row(raw, px, r) == GREY_ROW)
    print("GLOBAL.TXD  lba %d  size %d  declared %d  (stream %d bytes)"
          % (lba, size, declared, size - 8))
    print("  %s at 0x%X" % (RAMP_TEXTURE, px))
    show_row("row 0", row(raw, px, 0))
    show_row("grey", GREY_ROW)
    print("  rows   : %d/32 grey identity ramp" % neutral)
    print("LVLSETUP.INI  lba %d  size %d" % (ini_lba, ini_size))
    for old, new in INI_EDITS:
        state = "patched" if new in ini and old not in ini else "original"
        print("  %-40s %s" % (new.replace(b"\t", b" ").strip().decode(), state))
    ok = neutral == 32 and all(new in ini for _, new in INI_EDITS)
    print("  state  :", "patched" if ok else "original")
    return 0 if ok else 1


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


def main(a):
    if not a or a[0] not in ("apply", "verify", "revert") or len(a) < 2:
        print(__doc__)
        return 2
    cmd = a[0]
    if cmd == "apply":
        return cmd_apply(a[1])
    if cmd == "verify":
        return cmd_verify(a[1])
    return cmd_revert(a[1])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

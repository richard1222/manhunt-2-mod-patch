"""Remove the red execution "colour ramp" filter from Manhunt 2 (PS2, USA).

What the filter is
------------------
While an execution plays, the engine puts a colour-ramp post effect over the
screen: the picture is tinted red, so the gore happens behind the tint.  It is
configured by exactly three keys in GLOBAL/LVLSETUP.INI:

    EXECUTION_COLRAMP_TEXTURE      FE_execramps
    EXECUTION_COLRAMP_FLASH_TIMES  0.25, 0.6, 0.3   # fade-in, hold, fade-out
    EXECUTION_COLRAMP_FADE_TIME    5.0

Tweaking those timings does not remove the tint -- the ramp is still built, just
briefer -- because the red comes from the ramp *texture*.

What does not work
------------------
Deleting or commenting out the three keys (which is what the community
"MANHUNT 2 NOKILLFILTER" release does) does remove the tint, but it leaves the
engine with no execution ramp at all, and the game then hard-freezes at the
mission-1 bookend execution (BOOKEND_EXECUTION_OBJECT A00_BookendB) when played
on a PS3's PS2 emulator.  The keys therefore have to stay defined.

The fix
-------
Keep the keys, and make the ramp itself a no-op.  The ramp texture FE_execramps
lives inside GLOBAL/PICS/GLOBAL.TXD:

    "Z2HM" | u32 uncompressed size | zlib stream  ->  "TCDT" texture dictionary

The TCDT is a linked list of 0x70-byte entries:

    +0x00  u32   offset of the next entry
    +0x08  char  NUL-terminated texture name
    +0x60  u32   offset of the texture pixels

Every ramp texture is 32x32 RGBA with a pitch of 0x80 (128 bytes = 32 pixels),
and each row is one colour ramp: for input level i the pixel holds (r,g,b), so
the row's channels ARE three per-channel lookup tables.  FE_execramps row 0 runs
(5,0,0)..(215,5,5) -- red passes through while green and blue are crushed.  That
is the red.

This patch overwrites the FE_execramps texture with the identity lookup
(i*255/31, i*255/31, i*255/31), a per-channel pass-through, so the engine still
builds and applies an execution ramp -- it simply has no effect.  All 32 rows are
replaced, so it is a no-op whichever row the engine picks.

The edited dictionary does not fit back into the retail file size with zlib, so
the stream is rebuilt with zopfli (still a plain zlib stream, same 78 DA header)
and zero-padded to the original byte length.  GLOBAL/PICS/GLOBAL.TXD keeps its
exact size, so no ISO9660 directory record, file size or sector layout changes.

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
TEXTURE_BYTES = 0x1000          # 32 rows * 0x80 pitch
IDENTITY = bytes(
    b for i in range(32)
    for b in (round(i * 255 / 31),) * 3 + (255,)
)
PATCHED_TEXTURE = IDENTITY * 32


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


# --- the texture dictionary ------------------------------------------------
def read_txd(iso):
    """Return (lba, file_size, dictionary_bytes) for GLOBAL/PICS/GLOBAL.TXD."""
    lba, size = locate(iso, TXD_DIR)
    iso.seek(lba * SECTOR)
    data = iso.read(size)
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


def compress(payload):
    """Rebuild the zlib stream, using zopfli when zlib cannot fit it."""
    stream = zlib.compress(payload, 9)
    if _zopfli is None:
        return stream
    better = _zopfli.compress(payload, numiterations=15)
    return better if len(better) < len(stream) else stream


def ramp_row(raw, px, row):
    o = px + 0x80 * row
    return raw[o:o + 128]


# --- commands --------------------------------------------------------------
def cmd_apply(path):
    with open(path, "r+b") as iso:
        lba, size, raw = read_txd(iso)
        px = ramp_offset(raw, RAMP_TEXTURE)

        if raw[px:px + TEXTURE_BYTES] == PATCHED_TEXTURE:
            print("already patched -- %s is the identity lookup" % RAMP_TEXTURE)
            return 0

        row = ramp_row(raw, px, 0)
        print("%s pixels @0x%X, row 0: %s .. %s"
              % (RAMP_TEXTURE, px,
                 ",".join(str(b) for b in row[0:3]),
                 ",".join(str(b) for b in row[124:127])))

        patched = bytearray(raw)
        patched[px:px + TEXTURE_BYTES] = PATCHED_TEXTURE
        stream = compress(bytes(patched))
        blob = MAGIC + struct.pack("<I", len(patched)) + stream
        if len(blob) > size:
            hint = ("" if _zopfli is not None
                    else " (install zopfli: pip install zopfli)")
            raise SystemExit("recompressed %d bytes > original file size %d%s"
                             % (len(blob), size, hint))
        blob = blob.ljust(size, b"\x00")

        # Restore block: the whole original file, so revert is self-contained.
        iso.seek(lba * SECTOR)
        original = iso.read(size)
        restore = path + ".orig"
        with open(restore, "wb") as rf:
            rf.write(struct.pack("<II", lba, size))
            rf.write(struct.pack("<II", 0, size))
            rf.write(original)
            rf.write(struct.pack("<I", 0xFFFFFFFF))
        print("restore block ->", restore)

        iso.seek(lba * SECTOR)
        iso.write(blob)
        iso.flush()

        iso.seek(lba * SECTOR)
        after = iso.read(size)
        if after[:len(blob)] != blob:
            raise SystemExit("write-back verification failed")

    print("patched GLOBAL/PICS/GLOBAL.TXD (lba %d, %d bytes; compressed %d)"
          % (lba, size, len(stream)))
    print("OK -- execution ramp is now the identity lookup")
    return 0


def cmd_verify(path):
    with open(path, "rb") as iso:
        lba, size, raw = read_txd(iso)
        px = ramp_offset(raw, RAMP_TEXTURE)
    row = ramp_row(raw, px, 0)
    patched = raw[px:px + TEXTURE_BYTES] == PATCHED_TEXTURE
    print("lba %d  size %d" % (lba, size))
    print("%s @0x%X row 0: %s" % (RAMP_TEXTURE, px,
                                  " ".join("%d,%d,%d" % (row[4 * k], row[4 * k + 1],
                                                         row[4 * k + 2])
                                           for k in range(4))))
    print("state  :", "patched" if patched else "original")
    return 0 if patched else 1


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
    print("reverted %d edit(s) in lba %d" % (len(edits), lba))
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

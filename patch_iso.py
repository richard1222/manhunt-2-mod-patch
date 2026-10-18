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

Every ramp texture is 32 rows of 32 pixels, 4 bytes per pixel (pitch 0x80), and
each row is one colour ramp: for input level i the pixel holds (r,g,b).  The
three channels are therefore three independent lookup tables, and FE_execramps
row 0 runs (5,0,0)..(215,5,5) -- red passes through while green and blue are
crushed.  That is the red.

This patch overwrites the FE_execramps texture with the linear identity lookup
(i*255/31, i*255/31, i*255/31) for all 32 rows, a per-channel pass-through: the
engine still builds and applies an execution ramp, it just has no effect.

Keeping the container byte-exact
--------------------------------
The retail file has no slack: its zlib stream is exactly 95263 bytes, filling
the file.  Any edited dictionary recompresses larger with zlib, so the stream is
rebuilt with zopfli and then padded *inside* the deflate stream -- with empty
stored blocks inserted after the 2-byte zlib header -- so that the stream is
still exactly 95263 bytes and nothing trails it.  An empty stored block is
00 00 00 FF FF, decodes to nothing, and keeps the following block byte aligned.
Because a stored block is 5 bytes, the padding is 5-byte granular, so the
zopfli iteration count is searched for a compression size that leaves a multiple
of 5 to pad.  GLOBAL.TXD keeps its exact size, so no ISO9660 record, file size or
sector layout changes.

Usage
-----
    py patch_iso.py apply  <iso>    patch in place; writes <iso>.orig first
    py patch_iso.py verify <iso>    report the current state
    py patch_iso.py revert <iso>    restore the original bytes from <iso>.orig

Requires:  pip install zopfli
"""
import hashlib
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
IDENTITY_ROW = bytes(
    b for i in range(32)
    for b in (round(i * 255 / 31),) * 3 + (255,)
)
IDENTITY = IDENTITY_ROW * 32

EMPTY_STORED = b"\x00\x00\x00\xff\xff"      # BFINAL=0, BTYPE=00, LEN=0, NLEN=FFFF


def filler(n):
    """n deterministic pseudo-random bytes, used only as unused trailing data."""
    out = bytearray()
    h = hashlib.sha256(b"manhunt2-uncensor").digest()
    while len(out) < n:
        out += h
        h = hashlib.sha256(h).digest()
    return bytes(out[:n])


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


def build_container(raw, size):
    """Return (dictionary, 'Z2HM' container) that exactly fills `size` bytes.

    The container is MAGIC + u32(len(dictionary)) + a zlib stream of exactly
    size-8 bytes, so nothing trails the stream.  The stream is zopfli output
    with empty stored blocks inserted after its 2-byte header; a stored block is
    5 bytes, so the zopfli iteration count is searched for a size that leaves a
    multiple of 5 to pad.
    """
    if _zopfli is None:
        raise SystemExit("zopfli is required: pip install zopfli")
    budget = size - 8                       # bytes the whole zlib stream may use
    for extra in range(0, 8):
        data = raw if extra == 0 else raw + filler(extra)
        for it in range(1, 41):
            stream = _zopfli.compress(data, numiterations=it)
            pad = budget - len(stream)
            if pad >= 0 and pad % len(EMPTY_STORED) == 0:
                out = stream[:2] + EMPTY_STORED * (pad // len(EMPTY_STORED)) \
                    + stream[2:]
                if len(out) != budget:
                    raise SystemExit("internal error: stream is %d bytes" % len(out))
                if zlib.decompress(out) != data:
                    raise SystemExit("internal error: rebuilt stream does not inflate")
                return data, MAGIC + struct.pack("<I", len(data)) + out, extra, it
    raise SystemExit("could not build a zlib stream of exactly %d bytes" % budget)


def row(raw, px, r):
    o = px + 0x80 * r
    return raw[o:o + 128]


def show_row(label, b):
    print("  %-8s %s" % (label, " ".join("%d,%d,%d" % (b[4 * i], b[4 * i + 1],
                                                       b[4 * i + 2])
                                          for i in (0, 1, 15, 31))))


# --- commands --------------------------------------------------------------
def cmd_apply(path):
    with open(path, "r+b") as iso:
        lba, size, raw = read_txd(iso)
        px = ramp_offset(raw, RAMP_TEXTURE)

        if raw[px:px + TEXTURE_BYTES] == IDENTITY:
            print("already patched -- %s is the identity lookup" % RAMP_TEXTURE)
            return 0

        print("%s pixels at 0x%X (file 95271-style: lba %d, %d bytes)"
              % (RAMP_TEXTURE, px, lba, size))
        show_row("before", row(raw, px, 0))

        patched = bytearray(raw)
        patched[px:px + TEXTURE_BYTES] = IDENTITY
        data, container, extra, it = build_container(bytes(patched), size)
        if len(container) != size:
            raise SystemExit("container is %d bytes, expected %d"
                             % (len(container), size))
        print("rebuilt stream: zopfli iterations=%d, 5-byte pad blocks=%d, "
              "dictionary %d bytes (+%d unused)"
              % (it, (size - 8 - len(_zopfli.compress(data, numiterations=it)))
                 // len(EMPTY_STORED), len(data), extra))

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
        iso.write(container)
        iso.flush()

        iso.seek(lba * SECTOR)
        if iso.read(size) != container:
            raise SystemExit("write-back verification failed")

    print("OK -- execution ramp is now the identity lookup")
    return 0


def cmd_verify(path):
    with open(path, "rb") as iso:
        lba, size, raw = read_txd(iso)
        px = ramp_offset(raw, RAMP_TEXTURE)
        iso.seek(lba * SECTOR)
        head = iso.read(8)
        declared = struct.unpack_from("<I", head, 4)[0]
    patched = raw[px:px + TEXTURE_BYTES] == IDENTITY
    print("lba %d  file size %d  declared size %d  (stream %d bytes)"
          % (lba, size, declared, size - 8))
    print("  %s at 0x%X" % (RAMP_TEXTURE, px))
    show_row("row 0", row(raw, px, 0))
    show_row("row 1", row(raw, px, 1))
    show_row("expect", IDENTITY_ROW)
    print("  state  :", "patched" if patched else "original")
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

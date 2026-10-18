"""Remove the red execution "colour ramp" filter from Manhunt 2 (PS2, USA).

What the filter is
------------------
While an execution plays, the engine puts a colour-ramp effect over the screen:
the picture is tinted red, so the gore happens behind the tint.  It is configured
by three keys in GLOBAL/LVLSETUP.INI:

    EXECUTION_COLRAMP_TEXTURE      FE_execramps
    EXECUTION_COLRAMP_FLASH_TIMES  0.25, 0.6, 0.3   # fade-in, hold, fade-out
    EXECUTION_COLRAMP_FADE_TIME    5.0

The red comes from the ramp *texture* named by the first key: the engine runs the
picture through a 256-entry lookup built from one of that texture's rows, and the
lookup replaces each pixel's colour.  It is a replacement, not a tint, and that is
what makes the effect impossible to cancel from the data side alone.  The other
two keys are timings: how long the ramp stays up, and its fade-in / hold /
fade-out.

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

The ramp stack
--------------
The engine does not apply one ramp.  It keeps a stack of five -- in '.bss' at
0x6C1D58, eight bytes an entry, a texture handle and a row -- plus a global top
index at 0x3FC9F0, and a renderer (0x3672D0) that walks down from the top and
applies the first entry that resolves.  The registration sites in SLUS_216.13
name the slots:

    slot 0   FE_genramps row 1                0x319C24  (engine default)
    slot 1   BASE_RAMP_TEXTURE / _ROW         0x316298, 0x315A44
    slot 2   HIDE_RAMP_TEXTURE / _ROW         0x2E7778
    slot 3   EXECUTION_COLRAMP_TEXTURE        0x2E7864
    slot 4   BOOKEND_RAMP_TEXTURE / _ROW      0x3162AC, 0x315A58

Slot 3 is filled every frame while an execution runs.  Slot 4 is filled once at
level load but stays inert until something raises the top index, and one small
function does exactly that, 0x2E3BB8(bool):

    on      0x2E3BCC  24040004  addiu $a0, $zero, 4    top = slot 4
    off     0x2E3BDC  24040003  addiu $a0, $zero, 3    top = slot 3

So the slot-4 ramp outranks the execution ramp in slot 3, and while a bookend
execution plays the whole picture is graded by it.  The execution ramp underneath
never gets a chance to show, which is why tuning its own timing changed nothing.

That is also how to tell the censor's work from the game's.  The prototype
SLES_548.19 has no BOOKEND_RAMP_TEXTURE or BOOKEND_RAMP_ROW string anywhere, its
INI goes straight from BASE_RAMP_* to HIDE_RAMP_*, and its level-init
(0x30FC18-0x30FC28) registers slot 1 and nothing else.  The slot-4 registration
and the "top = 4" branch are retail-only code.

The censorship
--------------
Retail differs from the pre-release prototype in three ways:

1.  Retail adds a whole second ramp, used for bookends only:

        BOOKEND_RAMP_TEXTURE   FE_genramps
        BOOKEND_RAMP_ROW       4

    The game's first execution is a bookend execution (the mission-1
    BOOKEND_EXECUTION_OBJECT A00_BookendB), so that first kill gets the second
    wash, and FE_genramps row 4 runs dark red to white.  That is the white on the
    first kill.

2.  Retail stretches the execution ramp's fade-in / hold / fade-out to
    0.25, 0.6, 0.3 (1.15 s all told) where the prototype has 0.05, 0.05, 0.1
    (0.2 s) -- a longer wash over the kill.

3.  Retail's FE_execramps rows are red and grey where the prototype's run red out
    to white and through other hues.

Why the data alone cannot fix it
--------------------------------
The keys look like levers, and three of them are not.

*   The ramp's pixels cannot be made neutral.  The lookup replaces the colour
    rather than scaling it, so a flat grey ramp at any level collapses the
    picture to that one tone -- flat 0 gives a black execution, flat 32 dark
    grey, flat 128 white -- and the grey identity ramp, output level i is
    (i,i,i), gives a full-screen black-and-white "noir" execution at full detail.
    Measured on hardware: the picture's brightness survives, its colour does not.

*   Deleting the keys hard-freezes.  A missing ramp is a real code path, and the
    console locks up at that first bookend execution.  That is what the community
    PS2 release "MANHUNT 2 NOKILLFILTER" does.  The keys have to stay defined.

*   The timings only reach the execution ramp, which is exactly what the censor's
    slot-4 ramp is covering.  EXECUTION_COLRAMP_FLASH_TIMES holds the ramp's
    fade-in, hold and fade-out -- the engine's generic ramp records call them
    COLORRAMP_SECONDS_IN, _ON and _OUT -- and EXECUTION_COLRAMP_FADE_TIME is how
    long the ramp stays up.  Measured on hardware: at 999 the execution stayed
    grey for over sixteen minutes, at the retail 5.0 the grade covered the whole
    kill, and at 0.1 it was a fraction of a second.

The fix
-------
Stop the engine selecting a ramp while an execution runs.  Two paths do the
selecting, and each call is a jal replaced by a nop, in place.

0x2E3BB8(bool) is the bookend switch.  It stores its flag at obj+0x620 -- which is
what the game logic reads -- and then arms the ramp stack in BOTH branches:

    0x2E3BC0  beqz  $a1, 0x2E3BD8
    0x2E3BC4  sb    $a1, 0x620($a0)     the flag
    0x2E3BC8  jal   0x367198            on  -> arm
    0x2E3BCC  addiu $a0, $zero, 4
    ...
    0x2E3BD8  jal   0x367198            off -> arm
    0x2E3BDC  addiu $a0, $zero, 3

0x2E77C0 is the execution registrar.  While an execution runs it re-registers the
execution ramp in slot 3 on each change of the execution's animation state:

    0x2E7860  lw    $a1, -0x3420($v0)   the ramp resolved from the INI
    0x2E7864  jal   0x3671C8            register slot 3
    0x2E7868  addiu $a0, $zero, 3

Both arms call 0x367198, which sets f12 = 0.05 and calls the renderer 0x3672D0; the
registrar's call rebuilds the lookup too.  Every arm therefore renews the grade,
which is why the INI timings only ever shaped the tail.  The three nops:

    0x2E3BC8  0C0D9C66  jal 0x367198    retail
    0x2E3BC8  00000000  nop             patched
    0x2E3BD8  0C0D9C66  jal 0x367198    retail
    0x2E3BD8  00000000  nop             patched
    0x2E7864  0C0D9C72  jal 0x3671C8    retail
    0x2E7864  00000000  nop             patched

The registrar's two "clear slot 3" calls are deliberately left alone: clearing
re-resolves the stack and drops back to the level's own ramp, which is the state
ordinary play runs in, so they are what ends the grade.  SLUS_216.13 is an ELF32
(ET_EXEC, MIPS R5900) whose '.text' is loaded at virtual 0x100000 from file offset
0x1000, so a virtual address maps to file offset vaddr - 0xFF000.  The shipped ELF
has no symbol table and a PS2 ELF is not checksummed.  Each instruction keeps its
size, so the file keeps its length, its ISO9660 record and the disc layout.

One nop was not enough on hardware, and that is how the third one turned up.
Dropping slot 4 exposes slot 3, and slot 3 is what the execution registrar
0x2E77C0 refills for as long as the execution runs, on each change of its
animation state:

    0x2E77D4  lbu  $v1, 0x44c8($v0)     execution active?
    0x2E77E4  lwc1 $f1, 0x12b8($s0)     and its timer still up?
    0x2E7860  lw   $a1, -0x3420($v0)    the ramp resolved from the INI
    0x2E7864  jal  0x3671c8             register slot 3 ...
    0x2E7868  addiu $a0, $zero, 3

Each registration rebuilds the lookup and re-arms the pass, so the grade covers
the whole kill however EXECUTION_COLRAMP_FADE_TIME is set; the INI only shapes the
tail after the ramp is dropped.  Nopping 0x2E7864 as well leaves the registrar
nothing to register, which is what makes the three nops above the whole fix.

It is also why painting the ramp grey was never going to remove anything: a
resolved ramp replaces colour rather than tinting it -- output level is the ramp
entry for the pixel's luminance, nothing else -- so every ramp that is actually
drawn is monochrome no matter what texture is put there.  Overwriting
FE_execramps with the grey identity turned the red filter into a grey one
instead of taking it away, which is exactly what the console showed.

The frame latch 0x3FC9B0 looks like the switch for "is a ramp active" and is a
trap.  The lookup the frame is drawn with is built *inside* the code the latch
gates:

    writers                0x366768  sb $v1, -0x3650($v0)   $v1 = 1
                           0x366F50  sb $v1, -0x3650($a3)   $v1 = 1
    reader                 0x366838  lbu $v0, -0x3650($a0)
                           0x36683C  beqz $v0, 0x366ed4

Forcing both writers to 0 was tried on hardware: the console came up to a black
screen and never produced a picture, because the table is never built at all when
the latch is clear and an empty table is what gets drawn.  That is why the fix sits
at the two registration paths above rather than at the latch.  The three writes
below are the record of the attempt, kept commented out:

    0x366768   A043C9B0  sb   $v1, -0x3650($v0)    retail
    0x366768   A000C9B0  sb   $zero, -0x3650($v0)  forced
    0x366F50   A0E3C9B0  sb   $v1, -0x3650($a3)    retail
    0x366F50   A0E0C9B0  sb   $zero, -0x3650($a3)  forced
    0x366838   9082C9B0  lbu  $v0, -0x3650($a0)    retail
    0x366838   24020000  addiu $v0, $zero, 0       forced

The ramp texture FE_execramps is a texture in GLOBAL/PICS/GLOBAL.TXD:

    "Z2HM" | u32 uncompressed size | zlib stream  ->  "TCDT" texture dictionary

The TCDT is a linked list of 0x70-byte entries:

    +0x00  u32   offset of the next entry
    +0x08  char  NUL-terminated texture name
    +0x60  u32   offset of the texture pixels

Two INI edits and two data edits stay as belt and braces, so that if a ramp is
ever exposed again it cannot wash the kill:

1.  EXECUTION_COLRAMP_FLASH_TIMES' fade-in is made enormous: the ramp is up for
    0.10 s (FADE_TIME, below) and in that time has ramped a thousandth of the way
    in, so it never replaces the picture.  999 keeps the line's byte length.
    Driven down as well, the ramp timer goes sub-frame and the engine sticks at
    full, washing the whole execution white.

2.  EXECUTION_COLRAMP_FADE_TIME, how long the ramp stays up, 5.0 -> 0.10.

3.  FE_execramps is overwritten with the grey identity ramp, all 32 rows: output
    level i is (i,i,i), so that if the execution ramp ever does come up it can
    only be grey, never red.  Every texture here is 32 rows of 32 pixels, 4 bytes
    a pixel (pitch 0x80), and each ramp row is a lookup across input level
    0..255.

4.  BOOKEND_RAMP_TEXTURE is repointed from FE_genramps at that same grey ramp.
    With the ELF patch slot 4 is never selected, so this is belt and braces; the
    key stays defined because a missing ramp is what freezes the console.

The texel alpha was tried and is not the effect's strength: with every ramp pixel
zeroed to alpha 0 the execution looked exactly as it did at alpha 255.  The engine
reads the ramp as colour and ignores the fourth byte, so this patch writes alpha 0
only as a leftover of that test.

Every edit keeps its byte length (the bookend line drops the space before its tab
and takes it back inside the texture name), so the INI keeps its size, its ISO9660
record and its sector layout.

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

Three regions are written: the game ELF SLUS_216.13 (three instructions), the ramp
texture inside GLOBAL/PICS/GLOBAL.TXD, and GLOBAL/LVLSETUP.INI.  Every one keeps
its length, so no file size, ISO9660 record or sector layout moves.  The restore
block holds the original bytes of every region patched so far, and a later apply
merges into it rather than replacing it.

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

# The game ELF, at the root of the disc.  Four words in it decide whether any
# colour ramp can grade the picture: the bookend filter's slot, and the latch that
# the ramp pass is gated on.
ELF_NAME = "SLUS_216.13"
ELF_PATCHES = [
    # The filter is a screen-wide lookup that *replaces* colour: the output is
    # the ramp's entry for the pixel's luminance, so no ramp texture can ever be
    # colour-neutral.  The only way to remove it is to stop the engine selecting
    # a ramp during an execution, and that is what these three words do.
    #
    # 0x2E3BB8(bool) is the bookend switch.  It stores its flag and then, in
    # *both* branches, arms the ramp stack -- index 4 (the censor's
    # BOOKEND_RAMP_* slot) when on, index 3 (the execution ramp) when off:
    #
    #   0x2E3BC0  beqz  $a1, 0x2E3BD8
    #   0x2E3BC4  sb    $a1, 0x620($a0)     keep the flag
    #   0x2E3BC8  jal   0x367198            on  -> arm
    #   0x2E3BCC  addiu $a0, $zero, 4
    #   ...
    #   0x2E3BD8  jal   0x367198            off -> arm
    #   0x2E3BDC  addiu $a0, $zero, 3
    #
    # Arming 0x367198 resolves a slot and rebuilds the lookup with a fresh fade
    # (0x367198 sets f12 = 0.05), so as long as either branch runs the grade is
    # renewed and the picture stays filtered.  Nop the two arms and the switch
    # only records its flag, which is what the game logic reads.
    (0x2E3BC8, 0x0C0D9C66, 0x00000000,
     "bookend switch: do not arm the ramp when turning on"),
    (0x2E3BD8, 0x0C0D9C66, 0x00000000,
     "bookend switch: do not arm the ramp when turning off"),

    # 0x2E77C0 is the execution registrar.  While an execution runs it
    # (re)registers the execution ramp in slot 3 on every animation state change,
    # which again resolves the slot and renews the fade:
    #
    #   0x2E7860  lw    $a1, -0x3420($v0)   the ramp resolved from the INI
    #   0x2E7864  jal   0x3671C8            register slot 3
    #   0x2E7868  addiu $a0, $zero, 3
    #
    # Its two "clear slot 3" calls further down are deliberately left alone:
    # clearing re-resolves the stack and drops back to the level's own ramp, which
    # is the state ordinary play runs in, so they are what ends the grade.
    (0x2E7864, 0x0C0D9C72, 0x00000000,
     "execution registrar: no longer registers the execution ramp"),

    # The frame latch 0x3FC9B0 is NOT a usable switch, and this is the record of
    # that.  It looked like the "is a ramp active" bit and clearing it does stop
    # 0x366774 rebuilding the lookup -- but the lookup is what the frame is drawn
    # with even so: with both writers forced to 0 the table never gets built at
    # all and the game comes up to a black screen and stays there.
    #
    # (0x366768, 0xA043C9B0, 0xA000C9B0,
    #  "ramp enable latch: never set (writer 1)"),
    # (0x366F50, 0xA0E3C9B0, 0xA0E0C9B0,
    #  "ramp enable latch: never set (writer 2)"),
    # (0x366838, 0x9082C9B0, 0x24020000,
    #  "ramp enable latch: force the read to 0"),
]

MAGIC = b"Z2HM"
TEXTURE_BYTES = 0x1000          # 32 rows * 0x80 pitch (32 pixels * 4 bytes)
GREY_ROW = b"".join(bytes((v, v, v, 0x00))
                    for v in (round(i * 255 / 31) for i in range(32)))
GREY_RAMP = GREY_ROW * 32       # every row: output level i is the grey (i,i,i),
                                # written with a zero alpha

# Same-length, in-place text edits to GLOBAL/LVLSETUP.INI.
INI_DIR = ["GLOBAL", "LVLSETUP.INI"]
INI_EDITS = [
    # the ramp's own fade-in / hold / fade-out (retail 0.25, 0.6, 0.3).  The
    # fade-in is made enormous so the ramp never ramps up during a kill: it is
    # up for 0.10 s (below) and in that time has only run a thousandth of the way
    # in, so it never replaces the picture.  999 keeps the line's byte length.
    (b"EXECUTION_COLRAMP_FLASH_TIMES\t0.25, 0.6, 0.3",
     b"EXECUTION_COLRAMP_FLASH_TIMES\t999, 0.60, 0.3"),
    # how long the ramp stays up (retail 5.0).  It has to stay a sane window:
    # driven to 0.01 the ramp timer goes sub-frame and the engine sticks at full,
    # washing the whole execution white.
    (b"\tEXECUTION_COLRAMP_FADE_TIME\t\t5.0",
     b"\tEXECUTION_COLRAMP_FADE_TIME\t0.10"),
    # the censor's bookend-only second ramp.  Retail points it at FE_genramps
    # row 4 (dark red to white) and the prototype has no bookend ramp at all.
    # The key stays defined -- a missing ramp is what freezes the first
    # execution -- but points at the grey identity ramp, so it cannot wash the
    # bookend red or white.  The space before the tab moves into the name.
    (b"\tBOOKEND_RAMP_TEXTURE \tFE_genramps",
     b"\tBOOKEND_RAMP_TEXTURE\tFE_execramps"),
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


# --- the game ELF ----------------------------------------------------------
def vaddr_to_off(elf, va):
    """File offset of a loaded virtual address in an ELF32 file.

    Walks the section headers for the loaded (PROGBITS, SHF_ALLOC) section that
    contains `va`, so the mapping never has to be hard-coded.
    """
    if elf[:4] != b"\x7fELF" or elf[4] != 1:
        raise SystemExit("SLUS_216.13 is not an ELF32 file")
    shoff = struct.unpack_from("<I", elf, 0x20)[0]
    shentsize = struct.unpack_from("<H", elf, 0x2E)[0]
    shnum = struct.unpack_from("<H", elf, 0x30)[0]
    for i in range(shnum):
        o = shoff + i * shentsize
        sh_type, sh_flags, sh_addr, sh_off, sh_size = struct.unpack_from(
            "<IIIII", elf, o + 4)
        if sh_type == 1 and sh_flags & 0x2 and sh_addr <= va < sh_addr + sh_size:
            return sh_off + (va - sh_addr)
    raise SystemExit("0x%X is not in a loaded section of the ELF" % va)


def patch_elf(data):
    """Apply ELF_PATCHES to `data`.  Returns (patched, [(va, note), ...]).

    Each patch must find the word it expects, and the replacement is the same
    size, so the file keeps its length exactly.
    """
    out = bytearray(data)
    applied = []
    for va, old, new, note in ELF_PATCHES:
        off = vaddr_to_off(out, va)
        cur = struct.unpack_from("<I", out, off)[0]
        if cur == new:
            continue
        if cur != old:
            raise SystemExit("ELF 0x%X: expected %08X, found %08X" % (va, old, cur))
        struct.pack_into("<I", out, off, new)
        applied.append((va, note))
    return bytes(out), applied


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
    """Write <path>.orig holding every original region: (lba, bytes) pairs.

    An existing restore block is merged rather than replaced, so patching another
    region of an image later on does not lose the earlier region's original
    bytes.
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

        # --- the game ELF ---
        elf_lba, elf_size = locate(iso, [ELF_NAME])
        elf = read_file_at(iso, elf_lba, elf_size)
        elf_new, elf_todo = patch_elf(elf)
        elf_done = not elf_todo
        if elf_done:
            print("%s already carries the ELF patch" % ELF_NAME)
        else:
            for va, note in elf_todo:
                print("%s 0x%X: %s" % (ELF_NAME, va, note))

        if txd_done and ini_done and elf_done:
            print("nothing to do -- already patched")
            return 0

        # Save originals before touching anything.
        if not txd_done:
            regions.append((lba, read_file_at(iso, lba, size)))
        if not ini_done:
            regions.append((ini_lba, ini))
        if not elf_done:
            regions.append((elf_lba, elf))
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
        if not elf_done:
            if len(elf_new) != elf_size:
                raise SystemExit("ELF size changed: %d -> %d"
                                 % (elf_size, len(elf_new)))
            iso.seek(elf_lba * SECTOR)
            iso.write(elf_new)
            if read_file_at(iso, elf_lba, elf_size) != elf_new:
                raise SystemExit("ELF write-back verification failed")
        iso.flush()

    print("OK -- the censor's bookend ramp can no longer be selected (the ELF keeps "
          "the ramp stack at the execution ramp), its own fade-in is 999s over a "
          "0.10s window so it never replaces the picture, and both ramp textures "
          "are the grey identity so nothing can wash red or white")
    return 0


def cmd_verify(path):
    with open(path, "rb") as iso:
        lba, size, raw = read_txd(iso)
        px = ramp_offset(raw, RAMP_TEXTURE)
        iso.seek(lba * SECTOR)
        declared = struct.unpack_from("<I", iso.read(8), 4)[0]
        ini_lba, ini_size = locate(iso, INI_DIR)
        ini = read_file_at(iso, ini_lba, ini_size)
        elf_lba, elf_size = locate(iso, [ELF_NAME])
        elf = read_file_at(iso, elf_lba, elf_size)

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
    print("%s  lba %d  size %d" % (ELF_NAME, elf_lba, elf_size))
    elf_ok = True
    for va, old, new, note in ELF_PATCHES:
        cur = struct.unpack_from("<I", elf, vaddr_to_off(elf, va))[0]
        if cur == new:
            state = "patched"
        elif cur == old:
            state = "original"
            elf_ok = False
        else:
            state = "unexpected 0x%08X" % cur
            elf_ok = False
        print("  0x%-9X %-34s %s" % (va, note, state))
    ok = neutral == 32 and elf_ok and all(new in ini for _, new in INI_EDITS)
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

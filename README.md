# Manhunt 2 (PS2) — execution red-filter removal

A minimal, **data-only** patch that takes the red "colour ramp" filter off the
screen during executions in the retail PS2 release of *Manhunt 2* (NTSC-U,
`SLUS_216.13`) — **without** the hard freeze the existing community patches cause
on a PS3.

This is a game-data patch — **not** a cheat code, and no cheat device or Action
Replay is required.

## The filter

Every execution paints the screen with a colour ramp, configured by three keys in
`GLOBAL/LVLSETUP.INI`:

```
EXECUTION_COLRAMP_TEXTURE		FE_execramps
EXECUTION_COLRAMP_FLASH_TIMES	0.25, 0.6, 0.3
EXECUTION_COLRAMP_FADE_TIME		5.0
```

## What the effect actually does

`EXECUTION_COLRAMP_TEXTURE` names the texture `FE_execramps`, which lives inside
`GLOBAL/PICS/GLOBAL.TXD`:

```
"Z2HM" | u32 uncompressed size | zlib stream   ->   "TCDT" texture dictionary
```

The dictionary is a linked list of `0x70`-byte entries:

| offset | meaning                        |
|--------|--------------------------------|
| `+0x00`| offset of the next entry       |
| `+0x08`| NUL-terminated texture name    |
| `+0x60`| offset of the texture pixels   |

Every texture here is 32×32 RGBA, pitch `0x80`. Each of the 32 rows is **one
colour table of 256 entries**, and during an execution the engine indexes it by
each pixel's brightness and paints the result:

```
output = table[brightness of the pixel]
```

The picture's own colour is **thrown away**. The table decides the colour, not the
scene, which is why the gore ends up behind a tint.

That is not a guess — it was pinned down on hardware:

| ramp written into `FE_execramps`          | what an execution looks like      |
|-------------------------------------------|-----------------------------------|
| flat level 0 (all black)                  | the whole screen is black         |
| flat level 32                             | dark grey                         |
| flat level 64                             | grey                              |
| flat level 128                            | white                             |
| **grey identity** — entry *i* = `(i,i,i)` | full-detail **black and white**   |
| the same, but every alpha forced to 0     | **no change at all**              |

A flat table collapses the picture to one flat tone. A table that maps brightness
to grey gives a full-detail monochrome picture: brightness survives, colour does
not. That is the signature of a lookup, so **there is no texture value that leaves
the picture alone**. The fourth byte of each texel is ignored as well — zeroing it
changed nothing — which fits a ramp that is read purely as a colour table.

An earlier version of this patch assumed the ramp was a *scale* (so that a flat
mid-grey would be 1:1). That is wrong, and the table above is why.

## The red is not the censor's filter

The red is the game's own stylisation rather than something the censor added: the
pre-release prototype has the **same** red `FE_execramps` and the **same**
`EXECUTION_COLRAMP_TEXTURE` key. What the retail release actually changed is
elsewhere:

- it **added** `BOOKEND_RAMP_TEXTURE FE_genramps` + `BOOKEND_RAMP_ROW 4`, which
  washes the intro bookend execution red;
- it **stretched** `EXECUTION_COLRAMP_FLASH_TIMES` from the prototype's
  `0.05, 0.05, 0.1` to `0.25, 0.6, 0.3`;
- it renamed and shifted `BOOKEND_CUTSCENE_OFFSET 0.0, 0.0, 0.35` to
  `BOOKEND_EXECUTION_OFFSET 0.0, 0.0, 0.4`;
- it **blanked `FE_execramps` rows 12–31 to black** in `GLOBAL.TXD`, where the
  prototype holds real colour curves.

## Why the community patches freeze

Both existing releases remove the effect by **taking the ramp away**:

- **No Execution Filter + extra** (DeBuGWoLf, PC) — edits `LevelSetup.ini` so
  `EXECUTION_COLRAMP_TEXTURE` names a texture that does not exist (it is left as
  `FE_`), which makes the lookup fail, and drops `EXECUTION_COLRAMP_FLASH_TIMES`
  to the pre-release value `0.05, 0.05, 0.1`.
- **MANHUNT 2 NOKILLFILTER** (smitty.dmg, PS2) — **deletes** the whole
  `EXECUTION_COLRAMP_*` block. Compared file by file against the retail disc, that
  release differs in exactly one file, `GLOBAL/LVLSETUP.INI`; the boot ELF and
  every other file are byte-identical.

Deleting the keys leaves the engine with **no execution ramp at all**, and on a
PS3's PS2 emulator the game then **hard-freezes** at the mission-1 bookend
execution (`BOOKEND_EXECUTION_OBJECT A00_BookendB`). So the keys *and* the ramp
have to stay defined. (The PC mod's other method — a name that does not resolve —
is a different edit, and has not been tested on this console.)

## The fix

Keep the key, keep the ramp defined and valid, and make the grade last no time.

1. `FE_execramps` is overwritten with the grey identity table (entry *i* =
   `(i,i,i)`). That takes the red out. It costs nothing, because it only shows if
   the grade is on screen long enough to see.
2. The timings are driven down so the table is up for a couple of frames instead
   of the whole kill:

   | key | retail | prototype | patched |
   |-----|--------|-----------|---------|
   | `EXECUTION_COLRAMP_FLASH_TIMES` | `0.25, 0.6, 0.3` | `0.05, 0.05,0.1` | `0.01,0.01,0.01` |
   | `EXECUTION_COLRAMP_FADE_TIME` | `5.0` | `5.0` | `0.01` |

The timings really are how long the grade is up, not just a flash around it: the
engine's generic ramp records call the same three numbers `COLORRAMP_SECONDS_IN`,
`COLORRAMP_SECONDS_ON` and `COLORRAMP_SECONDS_OUT`, and moving `FADE_TIME`
measurably changes the duration on hardware — at `999` the grade stayed for over
sixteen minutes, and at `0.1` an execution was grey for only a fraction of a
second, against a whole kill at the retail `5.0`.

Because the texture and all three keys stay defined, the engine never faces a
missing ramp — which is the part that matters for stability.

### Keeping the container byte-exact

The retail file has **no slack**: its zlib stream is exactly 95263 bytes and fills
the file, and the engine inflates it with zlib. Editing the dictionary
makes zlib recompress *larger* than the original, so the stream is rebuilt with
**zopfli** (still a plain zlib stream, same `78 DA` header) and then padded
**inside the deflate stream** — inserted right after the 2-byte zlib header — so
the stream is *still* exactly 95263 bytes and nothing trails it. Two units decode
to nothing and leave the next block byte-aligned:

```
00 00 00 FF FF       an empty stored block                          (5 bytes)
02 00 00 00 FF FF    an empty fixed-Huffman block whose end-of-block code ends
                     mid-byte, then a stored block that re-aligns     (6 bytes)
```

Five- and six-byte units between them reach any length of 20 bytes or more, so the
gap is always filled exactly, whatever zopfli produced. `GLOBAL/PICS/GLOBAL.TXD`
therefore keeps its exact byte size and its declared uncompressed size, so no
ISO9660 record, file size or sector layout changes.

The INI edits are equally contained. `GLOBAL/LVLSETUP.INI` is stored as plain
text, and both edits keep their byte length — the `EXECUTION_COLRAMP_FADE_TIME`
line keeps its length by turning one of its two tabs into a space — so the file
keeps its size, its directory record and its sector too.

## Requirements

- A retail **Manhunt 2 (USA)** PS2 ISO, `SLUS_216.13` — the unmodified image.
  Keep a backup of it.
- Python 3 with **zopfli**: `pip install zopfli`
- To run the patched copy: PCSX2, a softmodded PS2 (e.g. via OPL), or a CFW PS3.

## Usage

```
py patch_iso.py apply  "Manhunt 2 (USA).iso"     # patch in place
py patch_iso.py verify "Manhunt 2 (USA).iso"     # report the current state
py patch_iso.py revert "Manhunt 2 (USA).iso"     # restore from the .orig block
```

`apply` writes a `<iso>.orig` restore block next to the image before touching
anything, so `revert` can always put the disc back to stock. Patch a **copy** and
keep your original image somewhere safe.

## How this was checked

- Retail disc compared file by file against **MANHUNT 2 NOKILLFILTER**: 524 files,
  and the only difference is the `EXECUTION_COLRAMP_*` block in
  `GLOBAL/LVLSETUP.INI`.
- All 524 disc files scanned for ramp references: only the boot ELF and
  `GLOBAL/LVLSETUP.INI` mention the execution ramp, so there is no second place to
  patch.
- The boot ELF's string table searched for ramp keys. It contains the same three
  `EXECUTION_COLRAMP_*` keys and nothing else for executions, and the generic ramp
  system next to them (`COLORRAMP_NAME`, `_RAMP_ID`, `_SECONDS_IN`, `_ON`, `_OUT`,
  `_FREQUENCY`) is where the in/hold/out timings come from. There is no hidden
  enable/disable key.
- The retail `LVLSETUP.INI` was diffed against the pre-release prototype's, which
  is where the real censorship delta came from (bookend ramp, stretched flash
  timing, renamed offsets).
- The retail `GLOBAL.TXD` was decompressed and compared texture by texture against
  the prototype's: the ramps match except for the rows retail blanks, and every
  ramp texel's alpha is a constant 255.
- Every ramp variant was then played on hardware: flat levels, the grey identity,
  and the grey identity with the alpha zeroed.
- The patched image was diffed byte for byte against retail: 522 of 524 files are
  identical, and the only two that differ — `GLOBAL/PICS/GLOBAL.TXD` and
  `GLOBAL/LVLSETUP.INI` — are the *same size* as stock and sit at the same sectors.
  The container was checked to be byte-exact apart from the ramp: same `Z2HM`
  header, same declared uncompressed size, and a zlib stream of exactly the same
  95263 bytes with nothing trailing it.
- Run on real hardware — a **PS3 Slim 2001A on CFW 4.93 (Evilnat)**, through its
  PS2 emulator.

## References

- **DeBuGWoLf** — *No Execution Filter + extra*, PC (Dixmor Hospital / ModDB).
- **smitty.dmg** — *MANHUNT 2 NOKILLFILTER* PS2 release (used as the reference).
- **ermaccer** — PSP *Censorship Removal Patch*, which does the same job for the
  PSP release in code.
- The Manhunt community.

*Manhunt and Manhunt 2 are trademarks of Take-Two Interactive / Rockstar Games.
This repository contains no game data and is not affiliated with them.*

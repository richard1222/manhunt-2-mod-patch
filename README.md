# Manhunt 2 (PS2) — execution red-filter removal

A minimal, **data-only** patch that removes the red filter / "colour ramp" the
engine paints over the screen during executions in the retail PS2 release of
*Manhunt 2* (NTSC-U, `SLUS_216.13`).

This is a game-data patch — **not** a cheat code, and no cheat device or Action
Replay is required.

## The problem

Every execution tints the whole screen red, and the gore happens behind that
tint. The filter is a colour-ramp effect configured by three keys in
`GLOBAL/LVLSETUP.INI`:

```
EXECUTION_COLRAMP_TEXTURE		FE_execramps
EXECUTION_COLRAMP_FLASH_TIMES	0.25, 0.6, 0.3
EXECUTION_COLRAMP_FADE_TIME		5.0
```

Shortening or zeroing those timings does **not** remove the tint — the ramp is
still built and still applies for the whole execution; the timings only govern a
flash and a fade around it. The red comes from the ramp *texture* named in the
first key.

## What the community does

Two community releases remove the effect, and both do it by taking the ramp away:

- **No Execution Filter + extra** (DeBuGWoLf, PC) — edits `LevelSetup.ini` so
  `EXECUTION_COLRAMP_TEXTURE` names a texture that does not exist (it is left as
  `FE_`), which makes the lookup fail, and drops `EXECUTION_COLRAMP_FLASH_TIMES`
  to the pre-release value `0.05, 0.05, 0.1`.
- **MANHUNT 2 NOKILLFILTER** (smitty.dmg, PS2) — **deletes** the whole
  `EXECUTION_COLRAMP_*` block. Compared file by file against the retail disc, that
  release differs in exactly one file, `GLOBAL/LVLSETUP.INI`; the boot ELF and
  every other file are byte-identical.

Deleting — or failing to find — the ramp really does remove the tint. But it also
leaves the engine with **no execution ramp at all**, and the game then
**hard-freezes** at the mission-1 bookend execution
(`BOOKEND_EXECUTION_OBJECT A00_BookendB`) when played on a PS3's PS2 emulator. So
the keys *and* the ramp have to stay defined.

## The fix

Keep all three keys, and make the ramp itself a no-op.

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

Every texture here is 32×32 RGBA with a pitch of `0x80` (128 bytes = 32 pixels),
and **each ramp row is one lookup**: for input level *i* the pixel holds the
factor the picture is scaled by at that level. `FE_execramps` row 0 runs
`(5,0,0) … (215,5,5)` — red passes through while green and blue are crushed.
**That is the red.**

The ramp is a *scale*, not a flat overlay and not a lookup that replaces the
picture: an all-black ramp blacks the executing picture out, and flat 64 and flat
128 grey both turn it white, so the 1:1 point is **32**. This patch overwrites
`FE_execramps` with flat 32 grey — `(32,32,32,255)` at every level of all 32 rows
— so the ramp still exists and still applies, it just scales the picture by 1:1.

### The white flash

Retail also exaggerates the white flash that opens an execution: `0.25, 0.6, 0.3`
is 1.15 s all told, against the pre-release prototype's `0.05, 0.05, 0.1`
(0.2 s). `EXECUTION_COLRAMP_FLASH_TIMES` is restored to the prototype value. The
replacement is the same length as the original, so the INI is edited in place and
its size, ISO9660 record and sector layout do not move.

### Keeping the container byte-exact

The retail file has **no slack**: its zlib stream is exactly 95263 bytes and
fills the file, and the engine links zlib 1.1.4 to inflate it. Editing the
dictionary makes zlib recompress *larger* than the original, so the stream is
rebuilt with **zopfli** (still a plain zlib stream, same `78 DA` header) and then
padded **inside the deflate stream** — inserted right after the 2-byte zlib
header — so the stream is *still* exactly 95263 bytes and nothing trails it. Two
units decode to nothing and leave the next block byte-aligned:

```
00 00 00 FF FF       an empty stored block                          (5 bytes)
02 00 00 00 FF FF    an empty fixed-Huffman block whose end-of-block code ends
                     mid-byte, then a stored block that re-aligns     (6 bytes)
```

Five- and six-byte units between them reach any length of 20 bytes or more, so the
gap is always filled exactly, whatever zopfli produced.

`GLOBAL/PICS/GLOBAL.TXD` therefore keeps its exact byte size and the declared
uncompressed size is unchanged, so no ISO9660 record, file size or sector layout
changes — and nothing has to be rebuilt.

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
  `GLOBAL/LVLSETUP.INI` mention the execution ramp, so there is no second place
  to patch.
- The retail `GLOBAL/LVLSETUP.INI` was diffed against the pre-release prototype's:
  the whole censorship delta is the added `BOOKEND_RAMP_*` keys and the
  exaggerated `EXECUTION_COLRAMP_FLASH_TIMES`.
- The patched image was diffed byte for byte against retail: the only bytes that
  differ are inside `GLOBAL/PICS/GLOBAL.TXD` and on the one `LVLSETUP.INI` line,
  and the decompressed dictionary differs only inside `FE_execramps`.
- The patched container was checked to be byte-exact to retail everywhere except
  the ramp: same `Z2HM` header, same declared uncompressed size, and a zlib
  stream that is exactly the same 95263 bytes with nothing trailing it.
- Run on real hardware — a **PS3 Slim 2001A on CFW 4.93 (Evilnat)**, through its
  PS2 emulator.

## References

- **DeBuGWoLf** — *No Execution Filter + extra*, PC (Dixmor Hospital / ModDB).
- **smitty.dmg** — *MANHUNT 2 NOKILLFILTER* PS2 release (used as the reference).
- **ermaccer** — PSP *Censorship Removal Patch*.
- The Manhunt community.

*Manhunt and Manhunt 2 are trademarks of Take-Two Interactive / Rockstar Games.
This repository contains no game data and is not affiliated with them.*

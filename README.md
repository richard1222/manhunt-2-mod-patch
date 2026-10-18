# Manhunt 2 (PS2) — execution red-filter removal

A minimal, **data-only** patch that removes the red filter / "colour ramp" the
engine paints over the screen during executions in the retail PS2 release of
*Manhunt 2* (NTSC-U, `SLUS_216.13`).

This is a game-data patch — **not** a cheat code, and no cheat device or Action
Replay is required.

## The problem

Every execution tints the whole screen red, and the gore happens behind that
tint. The filter is a colour-ramp post effect configured by three keys in
`GLOBAL/LVLSETUP.INI`:

```
EXECUTION_COLRAMP_TEXTURE		FE_execramps
EXECUTION_COLRAMP_FLASH_TIMES	0.25, 0.6, 0.3
EXECUTION_COLRAMP_FADE_TIME		5.0
```

Shortening or zeroing those timings does **not** remove the tint — the ramp is
still built, just briefer. The red comes from the ramp *texture* named in the
first key.

## What does *not* work

The community release **MANHUNT 2 NOKILLFILTER** (smitty.dmg) solves it by
**deleting** that whole key block. Compared file by file against the retail disc,
that release differs in exactly one file, `GLOBAL/LVLSETUP.INI`, where those three
lines are gone; the boot ELF and every other file are byte-identical. So the whole
censorship lever is data.

Deleting — or commenting out — the keys really does remove the tint. But it also
leaves the engine with **no execution ramp at all**, and the game then
**hard-freezes** at the mission-1 bookend execution
(`BOOKEND_EXECUTION_OBJECT A00_BookendB`) when played on a PS3's PS2 emulator.
So the keys have to stay defined.

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

Every ramp texture is 32×32 RGBA with a pitch of `0x80` (128 bytes = 32 pixels),
and **each row is one colour ramp**: for input level *i* the pixel holds
`(r,g,b)`, so the row's three channels are three per-channel lookup tables.

`FE_execramps` row 0 runs `(5,0,0) … (215,5,5)` — red passes through while green
and blue are crushed. **That is the red.**

This patch overwrites the `FE_execramps` texture with the identity lookup
`(i*255/31, i*255/31, i*255/31)`, a per-channel pass-through. The engine still
builds and applies an execution ramp; it just has no effect. All 32 rows are
replaced, so the ramp is a no-op whichever row the engine picks.

The edited dictionary no longer fits back into the retail file size with zlib, so
the stream is rebuilt with **zopfli** (still a plain zlib stream, same `78 DA`
header) and zero-padded to the original length. `GLOBAL/PICS/GLOBAL.TXD` keeps its
exact byte size, so no ISO9660 directory record, file size or sector layout
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
- The patched image was diffed byte for byte against retail: the **only** bytes
  that differ are inside `GLOBAL/PICS/GLOBAL.TXD`, and the decompressed
  dictionary differs only inside `FE_execramps`.
- Run on real hardware — a **PS3 Slim 2001A on CFW 4.93 (Evilnat)**, through its
  PS2 emulator.

## References

- **smitty.dmg** — *MANHUNT 2 NOKILLFILTER* PS2 release (used as the reference).
- **ermaccer** — PSP *Censorship Removal Patch*.
- The Manhunt community.

*Manhunt and Manhunt 2 are trademarks of Take-Two Interactive / Rockstar Games.
This repository contains no game data and is not affiliated with them.*

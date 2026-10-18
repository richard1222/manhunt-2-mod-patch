# Manhunt 2 (PS2) — execution red-filter removal

A minimal, **data-only** patch that removes the red "colour ramp" the engine
paints over the screen during executions in the retail PS2 release of *Manhunt 2*
(NTSC-U, `SLUS_216.13`). **No code is changed; no game files are rebuilt.**

The patch is a single-line edit to **`GLOBAL/LVLSETUP.INI`** (two texture names
emptied, length-preserving). The boot ELF `SLUS_216.13` and `GLOBAL/PICS/GLOBAL.TXD`
stay byte-identical to retail. This is a game-data patch, not a cheat code.

## What it does

Retail grades every execution through a colour ramp: the picture is replaced by a
luminance lookup from the named texture.  The ramp's texture is the tint.  This
patch empties both ramp names on their retail lines:

```ini
EXECUTION_COLRAMP_TEXTURE       <empty>
BOOKEND_RAMP_TEXTURE            <empty>
```

With no ramp resolving, the execution plays in **full colour**. The other two ramp
keys (`EXECUTION_COLRAMP_FLASH_TIMES` and `EXECUTION_COLRAMP_FADE_TIME`) are
**left at stock retail values**. The edit keeps the INI the same size, so its
ISO9660 record and the disc layout never move.

Why both? Retail also defines `BOOKEND_RAMP_TEXTURE` (the censor's "bookend"
ramp). The very first execution in the game is a bookend execution; blanking only
the main execution ramp leaves that first kill graded. Blanking both gives full
colour from the first kill onward.

## Why this works (mechanism)

The ramp is a **luminance→colour lookup**.  The engine builds a table from one row
of the named texture and, during an execution, writes each pixel as
`ramp[luminance(pixel)]`.  There is no neutral texture: overwriting the ramp with
the grey identity ramp (`output = (i,i,i)`) gives a full-detail black-and-white
execution, not full colour.  So the fix is to stop any ramp from resolving.  The
engine's renderer skips a null ramp slot, and with no ramp in the execution slot
it falls back to normal drawing -- which is full colour.

## Why not delete the keys?

The community PS2 release "MANHUNT 2 NOKILLFILTER" deletes the entire
`EXECUTION_COLRAMP_*` block from `GLOBAL/LVLSETUP.INI`.  On a **PS3's PS2 emulator**
(CFW PS3, PS2 Classics mode) that causes a hard freeze at the mission-1 bookend
execution (`BOOKEND_EXECUTION_OBJECT A00_BookendB`).  Emptied, the keys stay
present and the game runs normally.

## Why not touch the flash times?

The community recipe (to avoid a black flash when the ramp is missing) stretches
`EXECUTION_COLRAMP_FLASH_TIMES` to `200., 0.6, 0.3`.  That number is not a fade
in; it is a **duration** written into the ramp timer and used by an
object-interaction flash path that fires during doors and other world
interactions.  With a 200-second timer still active, closing doors locks the
console up on PS3.  Leaving the stock retail timing (`0.25, 0.6, 0.3`) avoids
that, and once no ramp resolves the timing values do nothing.

## Tested on hardware

**PS3 Slim 2001A on CFW 4.93 (Evilnat)**, running via the PS3's PS2 emulator. With
this patch applied (two INI names emptied, everything else stock): every execution
plays in full colour, including the mission-1 bookend execution; grey appears
nowhere outside a kill; and the game runs through the 3-door gate sequence and
the dumpster truck area with no freeze. The boot ELF remained byte-identical to
retail.

## Usage

Python 3 (standard library only). No dependencies.

```bash
py patch_iso.py apply  "Manhunt 2 (USA).iso"     # patch in place; writes .orig
py patch_iso.py verify "Manhunt 2 (USA).iso"     # show ramp state
py patch_iso.py revert "Manhunt 2 (USA).iso"     # restore from .orig
```

Patch a **copy** of your retail ISO and keep the original safe. `apply` creates
`<iso>.orig` first (a restore block containing the original `GLOBAL/LVLSETUP.INI`
bytes). `revert` restores only the regions in that block.

## Notes

- Only `GLOBAL/LVLSETUP.INI` changes.
- Both edits are length-preserving: the text that replaces each texture name is
  exactly the same number of spaces as the retail texture name.
- Size, ISO9660 records and sector layout are unchanged.
- The engine's ramp stack skips null entries, so an empty ramp name is the normal
  "no execution ramp active" state.

*Manhunt and Manhunt 2 are trademarks of Take-Two Interactive / Rockstar Games.
This repository contains no game data and is not affiliated with them.*

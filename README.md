# Manhunt 2 (PS2) — execution red-filter removal

A **data-only** patch that removes the red "colour ramp" the game paints over the
screen during executions in the retail PS2 release of *Manhunt 2* (NTSC-U,
`SLUS_216.13`).

Two texture names in `GLOBAL/LVLSETUP.INI` are emptied, in place, and that is the
whole patch: **no code is changed and no game files are rebuilt.** The boot ELF
`SLUS_216.13` and `GLOBAL/PICS/GLOBAL.TXD` stay byte-identical to retail. It is a
game-data patch — no cheat code, cheat device or Action Replay is involved, and
the keys, textures and code paths all stay defined, so the engine never faces a
missing ramp.

## The filter

Every execution paints the screen with a colour ramp, configured by three keys in
`GLOBAL/LVLSETUP.INI`:

```
EXECUTION_COLRAMP_TEXTURE		FE_execramps
EXECUTION_COLRAMP_FLASH_TIMES	0.25, 0.6, 0.3
EXECUTION_COLRAMP_FADE_TIME		5.0
```

`FE_execramps` lives inside `GLOBAL/PICS/GLOBAL.TXD`, a `"Z2HM"` zlib container
holding a `"TCDT"` dictionary of `0x70`-byte entries (next-entry offset at `+0x00`,
name at `+0x08`, pixel offset at `+0x60`). Every texture there is 32×32 RGBA with
pitch `0x80`. Each of the 32 rows is one colour table, and during an execution the
engine indexes it by each pixel's brightness:

```
output = table[brightness of the pixel]
```

The picture's own colour is **thrown away** — the table decides the colour, not the
scene. This is a lookup, not a scale, so **no texture value leaves the picture
alone**: a flat table collapses the frame to one flat tone, and a table mapping
brightness to `(i,i,i)` gives a full-detail black-and-white picture (confirmed on
hardware). The fourth byte of each texel is ignored (zeroing it changes nothing).

That is why the filter cannot be removed by editing the texture. Colour can only
come back by stopping the engine *selecting* a ramp while an execution runs.

## The ramp stack

The engine keeps a **stack of five** ramps — in `.bss` at `0x6C1D58`, eight bytes
an entry (a texture handle and a row) — plus a **global top index** at `0x3FC9F0`.
The renderer (`0x3672D0`) walks down from the top and applies the first entry that
resolves, so the highest slot wins. It *skips* a null entry
(`beqz $a0, 0x367328`), which is why an unresolved ramp simply draws normally.

| slot | filled from | at | when |
|------|-------------|----|------|
| 0 | `FE_genramps` row 1 | `0x319C24` | engine default |
| 1 | `BASE_RAMP_TEXTURE` / `_ROW` | `0x316298`, `0x315A44` | level load |
| 2 | `HIDE_RAMP_TEXTURE` / `_ROW` | `0x2E7778` | while the player is hidden |
| 3 | `EXECUTION_COLRAMP_TEXTURE` | `0x2E7864` | while an execution runs |
| 4 | `BOOKEND_RAMP_TEXTURE` / `_ROW` | `0x3162AC`, `0x315A58` | level load |

Slot 4 is filled once at level load but stays inert until something raises the top
index. `0x2E3BB8(bool)` does exactly that, and it arms the stack on **both**
transitions:

```
on    0x2E3BCC   24040004   addiu $a0, $zero, 4    top = slot 4
off   0x2E3BDC   24040003   addiu $a0, $zero, 3    top = slot 3
```

So the bookend ramp **outranks the execution ramp**. The game's first execution is
a bookend execution (`BOOKEND_EXECUTION_OBJECT A00_BookendB`), which is why editing
the execution ramp's own texture or timing had no effect on the first kill.

## The fix

Empty both ramp names on their retail lines, keeping every other byte:

| key | retail | patched |
|-----|--------|---------|
| `EXECUTION_COLRAMP_TEXTURE` | `FE_execramps` | 12 spaces |
| `BOOKEND_RAMP_TEXTURE` | `FE_genramps` | 11 spaces |

An empty name is not a texture the game can find, so no ramp resolves. The
registrar (`0x3671C8`) opens with `beqz $s1, 0x367268`: handed a null ramp it
*clears* the slot instead of registering it, and the renderer skips that slot — so
the engine lands in exactly the state ordinary, non-execution play runs in. The
execution is drawn with no ramp and plays in full colour.

Both keys have to be emptied because both are armed: the bookend ramp outranks the
execution ramp at the first kill (above). Emptying only `EXECUTION_COLRAMP_TEXTURE`
leaves the mission-1 bookend execution graded.

Each name is replaced by the same number of spaces, so both edits keep the byte
length of the text they replace, and every other byte of the line (the tab and
space separators, the CR) is left exactly as retail wrote it.

**Nothing else changes.** A byte-for-byte comparison of the patched image against
the pristine retail image finds **23 differing bytes, all inside
`GLOBAL/LVLSETUP.INI`**: the two names, and nothing else on the disc. The ELF is
identical to retail, `GLOBAL/PICS/GLOBAL.TXD` is identical to retail, and the INI
keeps its size, its ISO9660 record and its sector, so no offset anywhere on the
disc moves.

### Why not delete the keys?

The community PS2 release *MANHUNT 2 NOKILLFILTER* deletes the whole
`EXECUTION_COLRAMP_*` block instead. Emptied rather than deleted, the file keeps
its size and its key set: there is nothing for a parser, a script or an offset to
be sensitive to, and the engine's own "no ramp" path is the one that runs.

### Why not touch the timing keys?

`EXECUTION_COLRAMP_FLASH_TIMES` and `EXECUTION_COLRAMP_FADE_TIME` are left at stock
retail values. They do nothing once no ramp resolves, and they are the wrong lever:

- The retail comment names the three numbers *flash fadein (sec), flash duration
  (sec), flash fadeout time (sec)*. The object-interaction flash path
  (`0x1D0370` → `0x3670D0`) **adds the first two into the engine's ramp timer**, so
  they are also the window for which a ramp stays armed — retail 0.25 + 0.6 =
  0.85 s. The community recipe stretches them to `200, 0.6, 0.3` to stop a missing
  ramp flashing the screen black. Measured on hardware, that value walks straight
  into the next freeze: the timer outlives the kill, that same flash path fires on
  ordinary world interactions such as closing a door, and the console locks up.
  Stock timing, with both names emptied, plays through.
- `EXECUTION_COLRAMP_FADE_TIME` is the window for the grade itself. Driven to
  `0.01` the ramp timer goes sub-frame and the engine sticks at full, washing the
  execution white.

## Requirements

- A retail **Manhunt 2 (USA)** PS2 ISO, `SLUS_216.13` — the unmodified image. Keep
  a backup of it.
- Python 3. Nothing else; there is no zopfli or container work any more.
- To run the patched copy: a CFW PS3, a softmodded PS2 (e.g. OPL), or PCSX2.

## Usage

```
py patch_iso.py apply  "Manhunt 2 (USA).iso"     # patch in place
py patch_iso.py verify "Manhunt 2 (USA).iso"     # report the current state
py patch_iso.py revert "Manhunt 2 (USA).iso"     # restore from the .orig block
```

One region is written, `GLOBAL/LVLSETUP.INI`, at the size it already is. `apply`
writes a `<iso>.orig` restore block next to the image before touching anything (and
merges into an existing block rather than replacing it), so `revert` can always put
the disc back to stock. Patch a **copy** and keep your original image safe.

## Current status

**Full colour, confirmed on hardware** — a PS3 Slim 2001A on CFW 4.93 (Evilnat).
Every execution plays ungraded, including the mission-1 bookend execution, and the
game runs through the 3-door gate sequence and the dumpster truck area with no
freeze.

Video of the execution on hardware:

[Watch the video](https://drive.google.com/uc?export=download&id=125l2ifjRok7r7L5QsDsFroVwTUCBvndY)

## How this was checked

- Retail disc compared file by file against the reference *MANHUNT 2 NOKILLFILTER*
  release: its only change to `GLOBAL/LVLSETUP.INI` is deleting the whole
  `EXECUTION_COLRAMP_*` block (13642 → 13330 bytes, one hunk, nothing else in the
  file), and every other disc file is byte-identical.
- All 652 disc files scanned for ramp references: only the boot ELF and
  `GLOBAL/LVLSETUP.INI` mention a colour ramp, so there is no second place to
  patch.
- Retail `GLOBAL/LVLSETUP.INI` diffed against the earlier prototype build
  (`SLES_548.19`): the whole censorship delta is the added `BOOKEND_RAMP_*` keys
  and the exaggerated `EXECUTION_COLRAMP_FLASH_TIMES` (the prototype uses the
  pre-release `0.05, 0.05, 0.1`).
- The patched image compared byte for byte against retail: 23 differing bytes,
  all in `GLOBAL/LVLSETUP.INI`; the ELF and `GLOBAL.TXD` are identical.
- Run on real hardware, three builds, to separate what matters from what does not:
  a grey-ramp texture with stock code (kills grey, doors fine), the community
  recipe's `200` flash timing (full colour, froze closing a door), and the shipped
  INI-only patch (full colour, doors and truck fine).

## Traps for anyone extending this

- The frame latch `0x3FC9B0` looks like the obvious "is a ramp active" switch and
  is a trap: the lookup the frame is drawn with is built *inside* the code the latch
  gates, so forcing it clear never builds the table and the console comes up to a
  black screen. The frame lookup is at `0x366774`, the renderer `0x3672D0`, the
  registrar `0x3671C8`, the arm `0x367198`.
- The colour flash does not go through the slot stack: `0x1D0034` builds a random
  row of the execution ramp and hands it straight to `0x3670D0`, which writes the
  selection globals and calls the lookup builder itself, with no null check of its
  own. It fires on ordinary object interactions, not only during kills, so
  interfering with it freezes the console in mission 1's office area.
- Replacing the `jal`s at `0x2E3BC8`, `0x2E3BD8` and `0x2E7864` with nops, or
  nulling the handler arguments at `0x2F99F0`, `0x2FA670` and `0x2FAD48`, does
  remove the grade — but those builds freeze on hardware. None of them are needed:
  the working patch touches no code at all.
- Displacement-based searches have to be read carefully: the R5900's `lui` sets the
  high half of a base register, so `lw $v1, -0x3634($v0)` only means `0x3FC9CC`
  when `$v0` holds `0x400000` — several plausible-looking hits resolve to unrelated
  globals.

Disassembly and tracing used `elf_tool.py` (capstone, MIPS32 with a MIPS64 fallback
for the R5900's 64-bit `daddu`/`sd`/`ld`); disc work used `ps2iso.py` and
`iso_diff.py`. Neither ships here.

## References

- **DeBuGWoLf** — *No Execution Filter + extra*, PC (Dixmor Hospital / ModDB). Names
  a non-existent texture (`FE_`) and restores the pre-release flash timing.
- **smitty.dmg** — *MANHUNT 2 NOKILLFILTER* PS2 release (used as the reference).
- **ermaccer** — PSP *Censorship Removal Patch*, which does the same job for the
  PSP release in code.
- The Manhunt community.

*Manhunt and Manhunt 2 are trademarks of Take-Two Interactive / Rockstar Games.
This repository contains no game data and is not affiliated with them.*

# Manhunt 2 (PS2) — execution red-filter removal

A minimal, **data-only** patch that removes the red filter / "colour ramp" the
engine paints over the screen during executions in the retail PS2 release of
*Manhunt 2* (NTSC-U, `SLUS_216.13`).

This is a game-data patch — **not** a cheat code, and no cheat device or Action
Replay is required.

## The problem

Every execution has the whole screen tinted red, and the actual gore happens
behind that tint. Tweaking the flash *timings* does not remove it: the filter is
a "colour ramp" post-effect that is built whenever the relevant keys exist, and
shortening the timings only makes the red flash briefer.

## The fix

The filter is configured by exactly three keys in `GLOBAL/LVLSETUP.INI`:

```
EXECUTION_COLRAMP_TEXTURE		FE_execramps
EXECUTION_COLRAMP_FLASH_TIMES	0.25, 0.6, 0.3
EXECUTION_COLRAMP_FADE_TIME		5.0
```

Remove — or comment out — those keys and the engine never builds the ramp, so
there is no red filter at all. This patch comments the three lines out in place:

```
#EXECUTION_COLRAMP_TEXTURE		FE_execramps
#EXECUTION_COLRAMP_FLASH_TIMES	0.25, 0.6, 0.3
#EXECUTION_COLRAMP_FADE_TIME		5.0
```

That is the entire change: **3 bytes, in one file.** The file keeps its exact
length, so the ISO9660 layout, directory records and boot image are untouched —
nothing has to be rebuilt.

## How this was confirmed

- The retail disc was compared, file by file, against the known-good community
  release **MANHUNT 2 NOKILLFILTER** (smitty.dmg). Across all 524 files, the
  boot ELF (`SLUS_216.13`) and every other file are byte-identical; the **only**
  difference is `GLOBAL/LVLSETUP.INI`, where that release **deletes** this exact
  block. (That release also *rebuilt* the image; this patch reproduces the same
  result without rebuilding.)
- The in-place comment-out was then verified on real hardware: the red filter is
  gone.

## Requirements

- A retail **Manhunt 2 (USA)** PS2 ISO, `SLUS_216.13`, disc version 1.03 — the
  unmodified image. Keep a backup of it.
- To run the patched copy: PCSX2, a softmodded PS2 (e.g. via OPL), or a CFW PS3.

## Usage

```
py patch_iso.py apply  "Manhunt 2 (USA).iso"     # patch in place (nofilter)
py patch_iso.py verify "Manhunt 2 (USA).iso"     # report the current state
py patch_iso.py revert "Manhunt 2 (USA).iso"     # restore from the .orig block
```

`apply` writes a `<iso>.orig` restore block next to the image the first time it
runs, so `revert` can always put the disc back to stock. Patch a **copy** and
keep your original image somewhere safe.

Variants (documented in the script header):

| variant    | what it does                                            | status   |
|------------|---------------------------------------------------------|----------|
| `nofilter` | comments out the three keys — the filter is gone        | default  |
| `proto`    | restores the pre-release prototype timings               | reference |
| `zero`     | zeroes the flash and fade durations                      | reference |

`proto` and `zero` leave the ramp built, so a (faint) tint remains; they are
kept only to document what does *not* work.

## References

- **smitty.dmg** — *MANHUNT 2 NOKILLFILTER* PS2 release (used as the reference).
- **ermaccer** — PSP *Censorship Removal Patch*.
- The Manhunt community.

*Manhunt and Manhunt 2 are trademarks of Take-Two Interactive / Rockstar Games.
This repository contains no game data and is not affiliated with them.*

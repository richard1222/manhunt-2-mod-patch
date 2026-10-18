# Manhunt 2 (PS2) — execution red-filter removal

Removes the red "colour ramp" filter the game paints over the screen during
executions in the retail PS2 release of *Manhunt 2* (NTSC-U, `SLUS_216.13`).

It is a game-data patch **plus instructions changed in the boot ELF** (each a
`jal` replaced by a nop). No cheat code, cheat device or Action Replay is
involved. The keys, textures and code paths all stay defined, so the engine never
faces a missing ramp — which is what makes it stable where other patches freeze.

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
brightness to `(i,i,i)` gives a full-detail black-and-white picture. The fourth
byte of each texel is ignored (zeroing it changes nothing).

That is why the filter cannot be removed by editing the texture. Colour can only
come back by stopping the engine *selecting* a ramp while an execution runs.

## The ramp stack

The engine keeps a **stack of five** ramps — in `.bss` at `0x6C1D58`, eight bytes
an entry (a texture handle and a row) — plus a **global top index** at `0x3FC9F0`.
The renderer (`0x3672D0`) walks down from the top and applies the first entry that
resolves, so the highest slot wins.

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

### 1. Stop the engine selecting a ramp during an execution

Each `jal` is replaced by a nop, in place:

| at | retail | patched | what it did |
|----|--------|---------|-------------|
| `0x2E3BC8` | `0C0D9C66` `jal 0x367198` | `00000000` | bookend switch **on** → arm, top index = 4 |
| `0x2E3BD8` | `0C0D9C66` `jal 0x367198` | `00000000` | bookend switch **off** → arm, top index = 3 |
| `0x2E7864` | `0C0D9C72` `jal 0x3671C8` | `00000000` | execution registrar → register slot 3 |

`0x2E3BB8` still writes its flag at `obj+0x620` — that is what the game logic reads
— it just no longer arms the ramp in either branch. Both branches have to go:
leaving the "off" one alone re-selects the execution ramp the moment the bookend
state clears.

`0x2E77C0`, the execution registrar, still runs, and its two **"clear slot 3"** calls
are deliberately kept — clearing re-resolves the stack back to the level's own
ramp, which is the state ordinary play runs in, so they are what *ends* the grade.

The frame latch `0x3FC9B0` looks like the obvious switch and is a trap: the lookup
the frame is drawn with is built *inside* the code the latch gates, so forcing it
clear never builds the table and the console comes up to a permanent black screen.
That experiment is recorded commented-out in `patch_iso.py`.

`SLUS_216.13` is an ELF32 (`ET_EXEC`, MIPS R5900) whose `.text` loads at virtual
`0x100000` from file offset `0x1000`, so **file offset = vaddr − `0xFF000`**. The
shipped ELF is stripped and a PS2 ELF is not checksummed. Every edit keeps its
instruction size, so the file keeps its length, its ISO9660 record and its sector.

### 2. Take the red out of the table

`FE_execramps` is overwritten with the grey identity table (entry *i* = `(i,i,i)`).
It cannot put colour back — nothing can — but it keeps full picture detail, so a
ramp that does get armed reads as monochrome rather than red.

### 3. Keep an exposed ramp from ramping up

| key | retail | patched | why |
|-----|--------|---------|-----|
| `EXECUTION_COLRAMP_FADE_TIME` | `5.0` | `0.10` | how long an armed ramp is applied; the clear calls arm the level's ramp with this, so `5.0` would close every execution with a five-second grade |
| `EXECUTION_COLRAMP_FLASH_TIMES` | `0.25, 0.6, 0.3` | `999, 0.60, 0.3` | fade-in made enormous, so a ramp that does get armed never reaches full |
| `BOOKEND_RAMP_TEXTURE` | `FE_genramps` | `FE_execramps` | the bookend ramp points at the grey table instead of the red-to-white one |

`FLASH_TIMES` is the ramp's **fade-in, hold and fade-out** — the engine's generic
ramp records name the same three numbers `COLORRAMP_SECONDS_IN`, `_ON` and `_OUT`.
`FADE_TIME` must stay a real window: driven to `0.01` the ramp timer goes sub-frame
and the engine sticks at full, washing the whole execution white.

`BOOKEND_RAMP_*` has no timing keys of its own, which is the other reason the change
has to be in code rather than data.

## Requirements

- A retail **Manhunt 2 (USA)** PS2 ISO, `SLUS_216.13`, unmodified. Keep a backup.
- Python 3 with **zopfli**: `pip install zopfli`
- To run the patched copy: a CFW PS3, a softmodded PS2 (e.g. OPL), or PCSX2.

## Usage

```
py patch_iso.py apply  "Manhunt 2 (USA).iso"     # patch in place
py patch_iso.py verify "Manhunt 2 (USA).iso"     # report the current state
py patch_iso.py revert "Manhunt 2 (USA).iso"     # restore from the .orig block
```

Three regions are written: the boot ELF `SLUS_216.13`, the ramp texture inside
`GLOBAL/PICS/GLOBAL.TXD`, and `GLOBAL/LVLSETUP.INI`. Every one keeps its length, so
no file size, ISO9660 record or sector moves.

`apply` writes a `<iso>.orig` restore block next to the image before touching
anything, holding the original bytes of every region patched so far, so `revert`
can always put the disc back to stock. Patch a **copy**.

## Keeping the container byte-exact

The retail `GLOBAL.TXD` has no slack: its zlib stream is exactly 95263 bytes and
fills the file. An edited dictionary will not recompress to that size, so the stream
is rebuilt with **zopfli** (still a plain zlib stream, same `78 DA` header) and then
padded **inside** the deflate stream, right after the 2-byte zlib header, so the
stream is still exactly 95263 bytes with nothing trailing it. Two units decode to
nothing and leave the next block byte-aligned:

```
00 00 00 FF FF       an empty stored block                          (5 bytes)
02 00 00 00 FF FF    an empty fixed-Huffman block whose end-of-block code ends
                     mid-byte, then a stored block that re-aligns     (6 bytes)
```

Five- and six-byte units between them reach any length of 20 bytes or more, so the
gap always fills exactly. The dictionary itself stays 325024 bytes, so `GLOBAL.TXD`
keeps its exact size, its declared uncompressed size and its sector.

The INI edits likewise keep their byte length, so `GLOBAL/LVLSETUP.INI` keeps its
size, directory record and sector.

## Notes for anyone extending this

The frame lookup is at `0x366774`, gated by the latch byte `0x3FC9B0`. The renderer
is `0x3672D0`, the ramp registrar `0x3671C8`, the arm `0x367198`. Displacement-based
searches have to be read carefully: the R5900's `lui` sets the high half of a base
register, so `lw $v1, -0x3634($v0)` only means `0x3FC9CC` when `$v0` holds
`0x400000` — several plausible-looking hits resolve to unrelated globals.

Disassembly and tracing used `elf_tool.py` (capstone, MIPS32 with a MIPS64 fallback
for the R5900's 64-bit `daddu`/`sd`/`ld`); disc work used `ps2iso.py` and
`iso_diff.py`. Neither ships here.

## Current status

Tested on a **PS3 Slim 2001A on CFW 4.93 (Evilnat)**. The three nops above stop the
bookend ramp, so the first kill now opens in full colour — but a ramp is still
registered partway through the kill and the picture goes monochrome for the rest of
it. Three further call sites load the execution ramp pointer (`0x5BCCBE0`) into the
registrar, at `0x2F99F8`, `0x2FA67C` and `0x2FAD50`, reached from the execution-type
dispatcher at `0x2EDDBC`. Until those are handled the fix is **partial**; this README
will be updated once a full-colour kill is confirmed on hardware.

## References

- **DeBuGWoLf** — *No Execution Filter + extra*, PC (Dixmor Hospital / ModDB).
- **smitty.dmg** — *MANHUNT 2 NOKILLFILTER* PS2 release (used as the reference).
- **ermaccer** — PSP *Censorship Removal Patch*, which does the same job for the
  PSP release in code.
- The Manhunt community.

*Manhunt and Manhunt 2 are trademarks of Take-Two Interactive / Rockstar Games.
This repository contains no game data and is not affiliated with them.*

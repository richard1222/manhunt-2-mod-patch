# Manhunt 2 (PS2) — execution red-filter removal

A minimal patch that takes the red "colour ramp" filter off the screen during
executions in the retail PS2 release of *Manhunt 2* (NTSC-U, `SLUS_216.13`) —
**without** the hard freeze the existing community patches cause on a PS3.

It is a game-data patch **plus one instruction changed in the boot ELF**. No cheat
code, no cheat device and no Action Replay are involved.

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
colour table**, and during an execution the engine indexes it by each pixel's
brightness and paints the result:

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
| the same, but every alpha forced to 0     | exactly as it did at alpha 255    |

A flat table collapses the picture to one flat tone. A table that maps brightness
to grey gives a full-detail monochrome picture: brightness survives, colour does
not. That is the signature of a lookup, so **there is no texture value that leaves
the picture alone**. The fourth byte of each texel is ignored as well — zeroing it
changed nothing — which fits a ramp that is read purely as a colour table.

An earlier version of this patch assumed the ramp was a *scale* (so that a flat
mid-grey would be 1:1). That is wrong, and the table above is why.

## The ramp stack: which ramp wins

The engine does not apply a single ramp. It keeps a **stack of five** — in `.bss`
at `0x6C1D58`, eight bytes an entry, a texture handle and a row — plus a **global
top index** (`0x3FC9F0`) and a renderer (`0x3672D0`) that walks down from the top
and applies the first entry that resolves. The registration sites in `SLUS_216.13`
name the slots:

| slot | filled from | at | when |
|------|-------------|----|------|
| 0 | `FE_genramps` row 1 | `0x319C24` | engine default |
| 1 | `BASE_RAMP_TEXTURE` / `_ROW` | `0x316298`, `0x315A44` | level load |
| 2 | `HIDE_RAMP_TEXTURE` / `_ROW` | `0x2E7778` | while the player is hidden |
| 3 | `EXECUTION_COLRAMP_TEXTURE` | `0x2E7864` | every frame an execution runs |
| 4 | `BOOKEND_RAMP_TEXTURE` / `_ROW` | `0x3162AC`, `0x315A58` | level load |

Slot 3 is filled every frame while an execution runs. Slot 4 is filled once at
level load but stays **inert** until something raises the top index, and one small
function does exactly that, `0x2E3BB8(bool)`:

```
on    0x2E3BCC   24040004   addiu $a0, $zero, 4    top = slot 4
off   0x2E3BDC   24040003   addiu $a0, $zero, 3    top = slot 3
```

So the slot-4 ramp **outranks the execution ramp** in slot 3. While a bookend
execution plays, the whole picture is graded by the bookend ramp and the execution
ramp underneath never gets a chance to show — which is why changing the execution
ramp's own timing, texture or length had no effect on the first kill at all.

## What retail changed

The ramp effect itself is the game's — the pre-release prototype carries the same
`EXECUTION_COLRAMP_TEXTURE` key and tints its executions too. What retail changed:

- **it added a fifth slot.** Retail's INI gains `BOOKEND_RAMP_TEXTURE FE_genramps`
  + `BOOKEND_RAMP_ROW 4`, and the matching code gains the slot-4 registration and
  the `top = 4` branch above. Neither is in the prototype: `SLES_548.19` carries no
  `BOOKEND_RAMP_TEXTURE` or `BOOKEND_RAMP_ROW` string anywhere, its INI goes
  straight from `BASE_RAMP_*` to `HIDE_RAMP_*`, and its level-init (`0x30FC18` to
  `0x30FC28`) registers slot 1 and nothing else. The game's first execution is a
  bookend execution (`BOOKEND_EXECUTION_OBJECT A00_BookendB`), so the first kill is
  exactly the one that gets the extra ramp, and `FE_genramps` row 4 runs dark red
  to white. **That is the white on the first kill** — and, once the red was taken
  out of the table, the whole-kill monochrome that pointed at it.
- **it reworked `FE_execramps`** in `GLOBAL.TXD`. The prototype's ramps run red out
  to white and carry other hues as well — yellow, green, pink; retail's stay red
  and grey. Both versions tint the kill, but retail's table is the redder,
  colour-drained one, and that is where the red on screen comes from.
- **it stretched `EXECUTION_COLRAMP_FLASH_TIMES`** from the prototype's
  `0.05, 0.05, 0.1` to `0.25, 0.6, 0.3` — a longer wash over the kill.
- it nudged `BOOKEND_CUTSCENE_OFFSET` from `0.0, 0.0, 0.35` to `0.0, 0.0, 0.4`.

(Several UI textures in `GLOBAL.TXD` differ between the two discs as well —
`slider`, `font2`, `t16plus`, `FE_static_bottom` — but they are not part of the
ramp system.)

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

### 1. Patch the boot ELF: the censor's ramp can never be selected

`SLUS_216.13` is an ELF32 (`ET_EXEC`, MIPS R5900) whose `.text` is loaded at
virtual `0x100000` from file offset `0x1000`, so a virtual address maps to file
offset `vaddr - 0xFF000`. The shipped ELF has no symbol table, and a PS2 ELF is not
checksummed, so the repair is one word swapped in place:

```
0x2E3BCC   24040004   addiu $a0, $zero, 4     retail
0x2E3BCC   24040003   addiu $a0, $zero, 3     patched
```

Turning the bookend filter on now leaves the top index at 3, where the prototype
leaves it the rest of the time. Slot 4 still holds the censor's ramp, and the keys
still define it, but nothing ever selects it — so a bookend execution gets the
execution ramp, the game's own. The instruction is the same size, so the ELF keeps
its length, its ISO9660 record and its sector on disc.

### 2. Take the red out of the table

`FE_execramps` is overwritten with the grey identity table (entry *i* = `(i,i,i)`).
A grey table cannot put the colour back — no table can — but it is the one table
that keeps the full picture detail, so if the grade is ever on screen it reads as
monochrome, not red.

### 3. Keep the exposed ramp from ramping up

Three `LVLSETUP.INI` keys are changed:

| key | retail | patched | why |
|-----|--------|---------|-----|
| `EXECUTION_COLRAMP_FLASH_TIMES` | `0.25, 0.6, 0.3` | `999, 0.60, 0.3` | the ramp's fade-in is made enormous, so it never reaches full during a kill |
| `EXECUTION_COLRAMP_FADE_TIME` | `5.0` | `0.10` | how long the ramp is applied — a tenth of a second |
| `BOOKEND_RAMP_TEXTURE` | `FE_genramps` | `FE_execramps` | the censor's bookend ramp points at the grey table instead of the red-to-white one |

The two timing keys do different jobs, and both were pinned down on hardware:

- `EXECUTION_COLRAMP_FADE_TIME` is **how long the ramp is applied**. At `999` the
  execution stayed grey for over sixteen minutes; at the retail `5.0` it covered
  the whole kill; at `0.1` it was gone in a fraction of a second. It has to stay a
  real window: driven down to `0.01` the ramp timer goes sub-frame and the engine
  sticks at full, washing the whole execution white.
- `EXECUTION_COLRAMP_FLASH_TIMES` is the ramp's **fade-in, hold and fade-out** —
  the engine's generic ramp records call the same three numbers
  `COLORRAMP_SECONDS_IN`, `_ON` and `_OUT`. The first number is a fade-in *to full
  strength*, and that is the lever this patch uses: set to `999` seconds, the ramp
  is still at roughly a thousandth of full when the `0.10 s` window ends, so it
  never replaces more than a trace of the picture.

The `BOOKEND_RAMP_*` block has no timing keys of its own, which is why it is the
key that has to come out of the code rather than out of the data: it is either off
or at full strength, for the whole bookend.

Because the ELF, the texture and every key all stay defined and valid, the engine
never faces a missing ramp — which is the part that matters for stability.

## Tooling

The patch itself needs only `patch_iso.py` and Python 3 with **zopfli**. The
analysis behind it was done with a handful of small local scripts, none of which
ship here:

| tool | what it does |
|------|--------------|
| `ps2iso.py` | random-access ISO9660 reader — PVD, both-endian directory records, and `SYSTEM.CNF` to the boot ELF, so a 2.5 GB disc can be browsed without downloading it |
| `elf_tool.py` | ELF32 reader and MIPS disassembler (capstone, MIPS32 with a MIPS64 fallback for the R5900's 64-bit `daddu`/`sd`/`ld`), with `sections`, `strings`, `xref`, `callers`, `dis`, `dumpfunc`, `find`, `hexdump` and an in-place `nop` |
| `dump_ramps.py` | prints every ramp row out of `GLOBAL/PICS/GLOBAL.TXD` as RGB triples |
| `iso_diff.py` | compares two images file by file by hash, and reports each differing file's size and sector — the byte-exactness proof below |
| `patch_iso.py` | this patch: the ELF word swap, the rebuilt texture container, the INI edits and the `.orig` restore block |

The shipped ELF is stripped, so the analysis ran from its string table and the
shape of the code around it rather than from symbols — walking back from
`DEFAULT_SETTINGS` and the ramp keys to the parsers, from the parsers to the
structures they fill, and from there to the five registration sites and the one
switch that selects between them.

## Keeping the container byte-exact

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
text, and all three edits keep their byte length — the `FADE_TIME` line turns one
of its two tabs into a space, and the `BOOKEND_RAMP_TEXTURE` line drops the space
before its tab and takes it back inside the texture name — so the file keeps its
size, its directory record and its sector too.

The ELF edit is one word in place, so it needs no tricks at all: the file keeps
its size and its sector, and the disc layout is untouched.

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

Three regions are written: the boot ELF `SLUS_216.13` (one instruction), the ramp
texture inside `GLOBAL/PICS/GLOBAL.TXD`, and `GLOBAL/LVLSETUP.INI`. Every one keeps
its length, so no file size, ISO9660 record or sector moves.

`apply` writes a `<iso>.orig` restore block next to the image before touching
anything, holding the original bytes of every region patched so far, so `revert`
can always put the disc back to stock. Patch a **copy** and keep your original
image somewhere safe.

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
  `_FREQUENCY`) is where the in/hold/out timings come from. It also carries
  `BOOKEND_RAMP_TEXTURE` and `BOOKEND_RAMP_ROW`, so the bookend ramp is live code
  and not leftover data.
- The same string search over the pre-release prototype's ELF found **none** of the
  `BOOKEND_RAMP_*` strings, and the prototype's INI has no such block — so the
  fifth slot is retail-only, added by the censor.
- `SLUS_216.13` disassembled and traced: the five ramp registrations, the renderer
  that walks the stack from the top, and the `0x2E3BB8` switch that raises the top
  index to the bookend slot. That is what identified the bookend ramp as the
  constant, whole-kill wash, and the execution ramp underneath as the part that
  was never being reached.
- The retail `LVLSETUP.INI` was diffed against the pre-release prototype's, which
  is where the censorship delta came from, and the retail `GLOBAL.TXD` was
  decompressed and compared texture by texture against the prototype's. Both ramp
  textures differ: `FE_execramps`, whose ramps retail keeps red and grey where the
  prototype runs through other hues and out to white, and `FE_genramps`, the
  texture the added bookend ramp points at. Every ramp texel's alpha is a constant
  255.
- Every ramp variant was played on hardware: flat levels, the grey identity, the
  grey identity with the alpha zeroed, and the ramp with each timing value moved on
  its own — which is how the ramp's application time and its in/hold/out numbers
  were told apart. The game's first execution is a bookend execution, so it is the
  one kill that also gets the censor's second ramp.
- The patched image was diffed byte for byte against retail: **524 files, 521
  identical**. The three that differ are `SLUS_216.13`, which differs in **exactly
  one byte** — the instruction above — and `GLOBAL/PICS/GLOBAL.TXD` and
  `GLOBAL/LVLSETUP.INI`, the same size as stock and at the same sectors. The
  container was checked to be byte-exact apart from the ramp: same `Z2HM` header,
  same declared uncompressed size, and a zlib stream of exactly the same 95263
  bytes with nothing trailing it.
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

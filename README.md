# Manhunt 2 (PS2) — execution red-filter removal

A minimal patch that takes the red "colour ramp" filter off the screen during
executions in the retail PS2 release of *Manhunt 2* (NTSC-U, `SLUS_216.13`) —
**without** the hard freeze the existing community patches cause on a PS3.

It is a game-data patch **plus three instructions changed in the boot ELF** (each a
`jal` replaced by a nop). No cheat code, no cheat device and no Action Replay are
involved.

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
| 3 | `EXECUTION_COLRAMP_TEXTURE` | `0x2E7864` | while an execution runs |
| 4 | `BOOKEND_RAMP_TEXTURE` / `_ROW` | `0x3162AC`, `0x315A58` | level load |

Slot 3 is refilled while an execution runs — on each change of the execution's
animation state, which is often enough to hold the grade for the whole kill. Slot 4
is filled once at level load but stays **inert** until something raises the top
index, and one small function does exactly that, `0x2E3BB8(bool)`:

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

### 1. Patch the boot ELF: nothing selects a ramp during an execution

The grade is a lookup, so **no texture value can leave the picture alone** — a ramp
that maps brightness to colour cannot give colour back. The only way to take the
filter off is to stop the engine *selecting* a ramp while an execution runs.

Two small functions do the selecting. Each `jal` is replaced by a nop, in place:

| at | retail | patched | what it did |
|----|--------|---------|-------------|
| `0x2E3BC8` | `0C0D9C66` `jal 0x367198` | `00000000` | bookend switch **on** → arm, top index = 4 (the censor's slot) |
| `0x2E3BD8` | `0C0D9C66` `jal 0x367198` | `00000000` | bookend switch **off** → arm, top index = 3 |
| `0x2E7864` | `0C0D9C72` `jal 0x3671C8` | `00000000` | execution registrar → register slot 3 |

`0x2E3BB8(bool)` still writes its flag at `obj+0x620` — that is what the game logic
reads — it just no longer arms the ramp in *either* branch. And this matters: the
switch arms the stack on **both** transitions, so leaving the "off" branch alone
would re-select the execution ramp the moment the bookend state cleared.

`0x2E77C0`, the execution registrar, still runs. Its two **"clear slot 3"** calls
are deliberately kept: clearing re-resolves the stack and drops back to the level's
own ramp, which is the state ordinary play runs in, so they are what *ends* the
grade rather than what starts it. Only the registration of slot 3 is removed.

Every arm would otherwise rebuild the lookup with a fresh fade — `0x367198` sets
`f12 = 0.05` before it calls the renderer, and the registrar's registration carries
the `FLASH_TIMES` value — so while either ran every frame the grade was renewed and
the picture stayed filtered, no matter what `EXECUTION_COLRAMP_FADE_TIME` said.

`SLUS_216.13` is an ELF32 (`ET_EXEC`, MIPS R5900) whose `.text` is loaded at virtual
`0x100000` from file offset `0x1000`, so a virtual address maps to file offset
`vaddr - 0xFF000`. The shipped ELF has no symbol table and a PS2 ELF is not
checksummed. Each instruction keeps its size, so the file keeps its length, its
ISO9660 record and its sector on disc.

The frame latch `0x3FC9B0` looks like the obvious switch and is a trap. Clearing it
does stop `0x366774` rebuilding the lookup — but the lookup **is** what the frame is
drawn with even then: with both writers forced to zero the table is never built at
all and the console comes up to a black screen and stays there. That experiment is
recorded in `patch_iso.py` (commented out) so it does not get tried again.

The three words above and their addresses are the whole repair; everything below is
belt and braces, and none of it can put colour back on its own.

### 2. Take the red out of the table

`FE_execramps` is overwritten with the grey identity table (entry *i* = `(i,i,i)`).
A grey table cannot put the colour back — no table can — but it is the one table
that keeps the full picture detail, so if the grade is ever on screen it reads as
monochrome, not red.

### 3. Keep the exposed ramp from ramping up

Three `LVLSETUP.INI` keys are changed. With the code patch in place these are belt
and braces, but `FADE_TIME` still earns its keep — and the timings were all pinned
down on hardware, so they are recorded here:

| key | retail | patched | why |
|-----|--------|---------|-----|
| `EXECUTION_COLRAMP_FADE_TIME` | `5.0` | `0.10` | how long an armed ramp is applied — a tenth of a second, so the tail when the stack re-resolves is imperceptible |
| `EXECUTION_COLRAMP_FLASH_TIMES` | `0.25, 0.6, 0.3` | `999, 0.60, 0.3` | the ramp's fade-in is made enormous, so a ramp that does get armed never reaches full |
| `BOOKEND_RAMP_TEXTURE` | `FE_genramps` | `FE_execramps` | the censor's bookend ramp points at the grey table instead of the red-to-white one |

`EXECUTION_COLRAMP_FADE_TIME` is **how long the ramp is applied**, and it is still
doing work after the code patch: the registrar's "clear slot 3" calls resolve back
to the level's own ramp and arm it with this value, so at the retail `5.0` every
execution would close with a five-second grade of that ramp. The hardware runs:
at `999` the execution stayed grey for over sixteen minutes; at the retail `5.0` it
covered the whole kill; at `0.1` it was gone in a fraction of a second. It has to
stay a real window — driven down to `0.01` the ramp timer goes sub-frame and the
engine sticks at full, washing the whole execution white.

`EXECUTION_COLRAMP_FLASH_TIMES` is the ramp's **fade-in, hold and fade-out** — the
engine's generic ramp records call the same three numbers `COLORRAMP_SECONDS_IN`,
`_ON` and `_OUT`. The first number is a fade-in *to full strength*.

The `BOOKEND_RAMP_*` block has no timing keys of its own, which is the other reason
the change has to be in code rather than data: a ramp the bookend arm selects is
either off or at full strength, for the whole bookend.

Because the ELF, the texture and every key all stay defined and valid, the engine
never faces a missing ramp — which is the part that matters for stability.

## Tooling

The patch itself is `patch_iso.py` — Python 3 with **zopfli** (`pip install zopfli`) —
and that is the only thing this repository needs. Everything below was used to work
the mechanism out and to prove the build, and none of it ships here.

### Reading the discs

| tool | what it does |
|------|--------------|
| `ps2iso.py` | random-access ISO9660 reader: primary volume descriptor, both-endian directory records, and `SYSTEM.CNF` down to the boot ELF, so a 2.5 GB image can be browsed without copying it |
| `list_files.py` | prints every file on an image as `<size> <path>` — the file census the comparison scripts below work from |
| `elfinfo.py` | ELF inspector for R5900 binaries: headers, program and section headers, where `.text` is loaded |
| `elf_tool.py` | the ELF reader **and MIPS disassembler** the tracing was done with (capstone — MIPS32 first, with a MIPS64 fallback for the R5900's 64-bit `daddu`/`sd`/`ld`). Sub-commands: `sections`, `strings`, `stringva`, `xref`, `ptr`, `dis`, `func`, `dumpfunc`, `calls`, `callers`, `find`, `hexdump`, `nop` |
| `dump_ramps.py` | every texture in `GLOBAL/PICS/GLOBAL.TXD`: name, pixel offset, first and last texel of rows 0 and 1, and whether a row is the identity table |
| `dump_exec.py` | the execution, bookend and base ramp rows as R, G and B level lists, flagging the grey ones — the dump that showed the ramps are colour curves, not scales |
| `pcglg.py` | opens the **PC** community mod's `resource1.glg`, which is the same `Z2HM` container, so its INI and textures could be read next to the PS2 discs' |

### Comparing discs and builds

| tool | what it does |
|------|--------------|
| `iso_diff.py` | compares two images file by file by hash and reports each differing file's size and sector |
| `cmp_trees.py` | compares the whole file tree *and* boot ELF of two images |
| `cmp_content.py` | hashes every file in two images — catches content changes the size-based tree walk would miss |
| `cmp_ramps.py` | compares the colour-ramp textures between two images, texture by texture |
| `cmp_ref.py` | compares `GLOBAL/LVLSETUP.INI` between the retail disc and the reference build |
| `diff_ini.py` | diffs the PC mod's INIs against each other and against the PS2 retail INI |
| `scan_ini.py` | sweeps every `.INI`/`.TXT` on an image for censor, gore and maturity keys |
| `scan_censorship.py` | walks the whole tree, reads every `LVLSETUP.INI`, and reports the execution ramp settings |
| a small word-differ | prints each word that differs between the retail `SLUS_216.13` and the build's, by virtual address — how the ELF change was proved to be exactly three words |

### Getting it onto the console, and checking it landed

| tool | what it does |
|------|--------------|
| `upload_iso.py` | uploads the build to the console's PS2ISO folder over FTP, with progress and a size check |
| `remote_check.py` | pulls a few kilobytes of the patched regions back off the console with an FTP `REST` range read and compares them to the local build |
| `remote_md5.py` | streams the whole remote image over FTP, hashing as it goes, and compares it to the local file |
| `hash_remote_iso.py` | hashes the patched image locally and on the console, to rule out a corrupt upload |

The shipped ELF is stripped, so the analysis ran from its string table and the
shape of the code around it rather than from symbols — walking back from
`DEFAULT_SETTINGS` and the ramp keys to the parsers, from the parsers to the
structures they fill, and from there to the five registration sites, the two
functions that select between them, and the lookup the frame is finally drawn with.

Displacement-based searches have to be read carefully: the R5900's `lui` sets the
high half of a base register, so `lw $v1, -0x3634($v0)` only means `0x3FC9CC` when
`$v0` was loaded with `0x400000`. Several plausible-looking hits turned out to be
different globals — a scratch area at `0x66C9xx`, string tables at `0x4BEDxx` —
and the base register has to be checked at each one before a hit is believed.

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

Three regions are written: the boot ELF `SLUS_216.13` (three instructions), the ramp
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
  that walks the stack from the top, and the frame lookup `0x366774` that turns the
  selected ramp into the table the picture is drawn with. That is what showed the
  bookend ramp as the constant, whole-kill wash and the execution ramp underneath
  as the part that was never being reached — and, with the registration sites, what
  the fix had to turn off.
- The frame latch `0x3FC9B0` was forced clear on hardware and the console came up to
  a **black screen** that never produced a picture. The lookup is built *inside* the
  code the latch gates, so with the latch clear the table is never filled at all and
  the empty table is what gets drawn. That is why the fix is at the registration
  sites and not at the latch.
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
  twelve bytes — three words**, each a `jal` turned into a nop, and
  `GLOBAL/PICS/GLOBAL.TXD` and `GLOBAL/LVLSETUP.INI`, the same size as stock and at
  the same sectors. The container was checked to be byte-exact apart from the ramp:
  same `Z2HM` header, same declared uncompressed size, and a zlib stream of exactly
  the same 95263 bytes with nothing trailing it.
- Built and run on real hardware — a **PS3 Slim 2001A on CFW 4.93 (Evilnat)**,
  through its PS2 emulator. The data-only build reached the first kill and showed a
  full-detail **monochrome** picture; the three-word build is the one that stops the
  ramp being selected at all, and it is the build this repository ships.

## References

- **DeBuGWoLf** — *No Execution Filter + extra*, PC (Dixmor Hospital / ModDB).
- **smitty.dmg** — *MANHUNT 2 NOKILLFILTER* PS2 release (used as the reference).
- **ermaccer** — PSP *Censorship Removal Patch*, which does the same job for the
  PSP release in code.
- The Manhunt community.

*Manhunt and Manhunt 2 are trademarks of Take-Two Interactive / Rockstar Games.
This repository contains no game data and is not affiliated with them.*

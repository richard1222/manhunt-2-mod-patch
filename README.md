![Platform](https://img.shields.io/badge/Platform-PS2-blue)
![Region](https://img.shields.io/badge/Region-USA-green)
![Serial](https://img.shields.io/badge/Serial-SLUS__216.13-orange)
![Status](https://img.shields.io/badge/Status-Released-green)
# Manhunt 2 (PS2) — data-only patches

**Private analyzer status (2026-10-25):** [v0.14 synthetic-fixture verification and limitations](docs/ANALYZER_V0_14_STATUS.md). This is separate from the released PS2 patch scripts; no real game ISO scan has been verified for v0.14.

A small collection of **data-only** patch layers for the retail PS2 release of
*Manhunt 2* (NTSC-U, `SLUS_216.13`). They are independent and can be applied in
any combination:

| layer | what it does | script |
|-------|--------------|--------|
| red-filter removal | stops the execution colour ramp resolving, so kills play in full colour | `patch_iso.py` |
| 60 fps | **withdrawn** — both candidate targets are audio/gameplay constants, not a frame limiter (see below) | `patch_60fps.py` (audit/revert only) |
| level list | makes the front-end level list reachable — a two-line text edit, no cheat code; confirmed on hardware | recipe below |
| cut-content research | inventories what retail deleted and studies a prototype-asset graft (in progress, local-only) | `patch_cutcontent.py` |

The red-filter layer is released and hardware-confirmed; see
[Current status](#current-status).


---

## Table of Contents

- [Red-Filter Removal](#red-filter-removal)
- [The Filter](#the-filter)
- [The Ramp Stack](#the-ramp-stack)
- [The Fix](#the-fix)
- [Requirements](#requirements)
- [Usage](#usage)
- [Current Status](#current-status)
- [How This Was Checked](#how-this-was-checked)
- [Traps for Anyone Extending This](#traps-for-anyone-extending-this)
- [The Level List](#the-level-list-that-ships-but-is-not-linked)
- [Cut Content Restoration](#cut-content-restoration-in-progress)
- [60 FPS Layer (Withdrawn)](#60-fps-layer-withdrawn)
- [Tools](#tools)
- [References](#references)

---

## Red-filter removal

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
Every execution plays ungraded, including the mission-1 bookend execution — the
hardest case, since the bookend ramp outranks the execution ramp — and the game
runs through the 3-door gate sequence and the dumpster truck area with no freeze.

The shipped patch is the smallest form of what was tested: both names emptied with
the timing keys left at retail. It was then re-confirmed on hardware on its own,
with the development-only texture and timing edits removed.

Video of the execution on hardware:

[Watch the video](https://drive.google.com/uc?export=download&id=125l2ifjRok7r7L5QsDsFroVwTUCBvndY)

The **level list is confirmed on hardware** — the two-line `NEOMENU.TXT` edit puts
the shipped-but-unlinked level list one START-press from the title screen. The
whole path was played: list opens, Safe House loads from it with spawn and doors
intact, and the red-light level runs past the point that a naive routing once
froze. A file-level diff against the uncensored base shows exactly one changed
file. Recipe and the routing trap are below.

The **cut-content layer is research-only so far, and its two structural questions
are settled on hardware.** The model graft and the entity appends are verified and
the images boot; the engine **finds a model by name, not by index**, and **entity
positions read and write correctly**. What remains is composition rather than
discovery: building the actual restored content (dildo, vending machine) on top of
these now-confirmed mechanisms. Details, including the decoded container formats
and one practical limit on growing a level's entity file, are in
[Cut content restoration](#cut-content-restoration-in-progress) below.

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
- Run on real hardware across three builds, to separate what matters from what does
  not: a grey ramp texture with stock code (kills grey, doors fine), the community
  recipe's `200` flash timing (full colour, froze closing a door), and both names
  emptied with stock timing (full colour, doors and truck fine). The shipped patch
  is that last change and nothing else, and its first kill — the bookend execution —
  was re-confirmed in full colour on hardware afterwards.

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

## The level list that ships but is not linked

*Status: **confirmed on hardware.*** The edit below has been played on real
hardware end-to-end — the list opens in one press, the Safe House loads from it
with its spawn intact and its doors working, and it plays through the red-light
level past the point that previously froze. No front-end code is changed.

There is a level list in the game data already. `GLOBAL/INITSCR/NEOMENU.TXT`
declares page `scene selection` (`SCENESELECTION_PAGE`), and that page is filled
by an unconditional block of `ADDTOSELECTIONLIST` rows — one per level, each
carrying its own `load level(...)` command. Nothing about the list is gated. It is
only *unreachable*: the title path links to the profile page, and the list hangs
off the dev-only `scene select test` row on `main`.

So a level list needs no code, no cheat device and no rebuild — two text edits in
that one file:

| edit | from | to |
|------|------|----|
| `START_PAGE`'s `STARTLINK` target | `"loadsave"` | `"scene select test"` |
| the row you want | its shipped position | the head of the list |

With the first edit, pressing START on the title screen takes you through the
confirm page and into the list. The second is only for convenience, since the list
is longer than the page and the Safe House sits 6th as shipped (`LVL_7B` →
`load level(A07_2Tolerance_Zone)`).

**Point it at `"scene select test"`, not at `"scene selection"`.** The short
version — aiming `STARTLINK` straight at the list page — looks like it works: the
list appears, levels start, everything seems fine. It is wrong, and it is wrong in
a way that costs you an evening. A page reached by `STARTLINK`/`LINKTOPAGE` is
entered through the plain page transition; the list is entered in the shipped game
through the **`COMMAND`** dispatcher (the dev-only `scene select test` row on
`main`), and the dispatcher runs the level-transition setup. Skip it and levels
are entered half-initialised, which first shows up much later as a **hard freeze
mid-level** — on hardware it died at the fence in the red-light level, while the
same level played from the normal path did not, and the file diff stayed a
hundred harmless bytes of menu text the whole time.

The general rule, if you extend this: reach a page the same way the dev menu
reaches it. `COMMAND` and `LINKTOPAGE` are not interchangeable.

The edit is otherwise free of consequence for the rest of the disc: it adds about
a hundred bytes (39,849 → 39,954) to a file that already owns a 40,960-byte
(20-sector) extent, so the file keeps its extent and no offset anywhere moves. A
file-level diff of a built image against the uncensored base shows exactly one
changed file — `NEOMENU.TXT` — which is what "text-only, no code" looks like when
you check rather than assume.

**Level names are not directory names, and that is fine.** The rows carry the long
level name (`A07_2Tolerance_Zone`) while the disc directory is 8.3 (`A07_2T`).
Every retail level directory is the first six characters of its long name,
uppercased — all sixteen of them match:

```
A01_Escape_Asylum -> A01_ES    A04_SM_Nightclub -> A04_SM    A16_TV_Studio -> A16_TV
A02_The_Old_House -> A02_TH    A07_2Tolerance_Zone -> A07_2T A17_Creepy_Farm -> A17_CR
A03_Neighbourhood -> A03_NE    A14_SugarFactory -> A14_SU    A18_Manor -> A18_MA
```

and the levels' own compiled scripts reference levels the same long way
(`A01_ES.MLS` names `A02_The_Old_House`), so the shipped rows already name the
right thing.

### The PS2 "level select" button code does not exist

The commonly posted PS2 code — Up, Up, Down, Down, Left, Right, Left, Right — is
**not in the USA build**. Entering it does nothing, and the disc says why: the boot
ELF contains no cheat table, no direction-mask array, and no `cheat`/`DOWN`
strings. The only `CHEAT_LEFT` / `CHEAT_RIGHT` strings present are *sound names*
(ids 9 and 10 of `AUDIO/PS2/SFX/FRONTEND.INI`), and their only cross-references are
inside the front-end sound dispatcher. The sequence is a Wii/PSP code; the row
above is what the PS2 disc actually ships.

## Cut content restoration (in progress)

The uncensor patch above removes the *filters*. A separate effort is now
underway to restore content that was *cut* (not just filtered) to get the
M rating. Research across TCRF, the Manhunt Wiki, Dixmor Hospital, and
other community sources has mapped what's restorable.

### Verified against the disc

Independent of the community notes below, the model data has been examined
directly, and one result changes the plan: **the cut models really were deleted,
not just unwired.**

- `MODELS.DFF` is a `PMLC` container — a header, a doubly-linked list of 16-byte
  chunk nodes, the chunk payloads, a string table, and a trailing relocation
  table listing the offset of every pointer field. Every relocation value is an
  object-region offset, so an insert-and-rebase edit is mechanical.
- A local writer parses and rebuilds both the retail and prototype
  `A07_2T/MODELS.DFF` byte-identically. That round-trip is the gate the graft
  must pass before it can be trusted.
- Aligning the two builds by record-name set gives 1:1 chunk correspondence. The
  prototype-only chunks are the deleted content: the dildo, vending machine,
  Desert Eagle and others. Retail's string table has **no** `dildo`,
  `vendingmachine` or `Desert_Eagle` entry at all.
- **A whole-file swap was tested on hardware and fails.** Dropping the
  prototype's model and texture banks into retail crashes the Safe House load at
  the same point every time. The blunt port is out; a surgical, chunk-level graft
  from the prototype is the path being built.
- Because the relocation table lists every pointer field, a new chunk can be
  appended at the end of the object region — leaving every existing chunk
  position untouched — with its outgoing references remapped. That graft is
  implemented (local-only workbench script) and validates structurally before it
  writes an image: reparse, node-list cycle, pointer range, and a byte-identity
  rebuild check. The dildo is first, then the vending machine.
- The trap in that graft is that a chunk's own tail is **not** its data. The last
  `0x20` bytes of a payload are the *next* chunk's descriptor chain, and a chunk
  is preceded by N `0x20`-byte descriptor blocks that live in the previous
  chunk's tail (`payload+0x14` → first, `payload+0x18` → last). The dildo has one
  block, the vending machine thirteen. A graft has to carry the chain, copy any
  string literals the payload references out of the prototype string table, and
  rewrite the final chunk's tail as a self-referential terminator.
- **The entity side is a second, separate format, and it is decoded.**
  `ENTINST.BIN` is `u32 count`, then `count` × `u32 size` that tile the record
  region exactly, then the records; a record is `type\0objectname\0` padded to 4,
  then position (three floats), a quaternion, a `Base_Inst` name and a class blob.
  There are **no absolute offsets anywhere in the file**, so appending is safe:
  bump the count, add one size word, append the record — every existing record's
  position shifts by four bytes and nothing notices. An instance only exists if
  its type string equals a `RECORD` name in the sibling `ENTTDATA.INI`, which is
  plain text.
- `GLOBAL/GAME.GXT` (the front-end text table) is decoded as well, which is how
  the level list's row labels (`LVL_1` … `LVL_18`) were identified: a `TKEY`
  version-2 header, then 16-byte entries from `0x0C` — `name[8]`, a u32 hash and a
  u32 **byte offset** into the UTF-16LE text block (`TDAT`, 783 entries).

### Where it stands

All three open questions have been **answered on hardware**:

- **A model binds to its entity by name, not by index.** Exchanging the payload
  pointers of two existing chunks left the level visually unchanged — nothing
  moved to the other location — so the engine resolves a chunk by the name it
  looks up, not by position in the file. The append-at-end graft is therefore the
  right shape: a new chunk can sit at the end of the object region and still be
  found.
- **Multiple instances per type are supported**, so nothing about the retail data
  limits a type to one placement. Retail `A07_2T` holds 359 instances across 97
  distinct types, and several types repeat (33 `EmptyLight_(L)`, 6
  `broken_chair`, 5 `Leather_Sofa_Rotten`, …). The blocker is not a per-type cap.
- **The entity layer reads and writes positions correctly.** Moving one existing
  record's position — no appending, no size change, no relocation — moves that
  prop on hardware exactly as written. The record layout, the position field and
  its offset (which varies per record with the name length: `0x20`, `0x24`,
  `0x28` … and must always be computed, never hard-coded) are all confirmed.

One practical limit came out of the same work, and it is worth knowing before
extending any level's entity data:

- **Keep `ENTINST.BIN` inside its existing extent.** A07_2T's file is 62,524
  bytes in a 63,488-byte (31-sector) extent, so it has room for 7 more 124-byte
  records. Stay within that and the file keeps its LBA and appended records take
  effect. Grow past it and the writer has to **relocate** the file to a new
  sector; an image built that way booted and played normally but no appended
  record appeared. If a level genuinely needs more room, the extent has to be
  extended deliberately — do not rely on the relocation path.

The "only one of N clones appears" result was **co-located clones**, not a dropped
record: N copies at one identical coordinate overlap into a single visible
object, which is exactly the expected outcome. Placements that are meant to be
counted have to be given distinct coordinates.

**What is left is composition, and one dependency that is not obvious.** A cut
weapon needs its model, its entity record, its placement — *and* its animations.
Moving the dildo's placement to the player's own spawn and still seeing nothing
established that: the object is created, its animation block fails to resolve,
and nothing renders. `ENTTDATA` records name their animation set, so restoring a
weapon whose animations were deleted means grafting those too, not just the mesh.
See [Dildo / newspaper weapons](#dildo--newspaper-weapons--the-beta-is-needed).

Ruled out along the way, so nobody repeats it: retail's `dildo02` string in
`MAT.BIN` is a stale material name with no mesh behind it; `DILDO_MELEE_COLLISION`
is absent from every level's `WEAPONS.INI`; and `CT_DILDO` /
`BAT_DAMAGE_EXECUTE_DILDO_2_ANIM` exist only as names in the boot ELF. `Base_Inst`
is a shared class name — its following word is identical in all 237 records that
carry it (a relocated pointer into the ELF), so it is **not** a per-instance
parent and instances are not parented to one another.

Graft output carries prototype data, so it stays **local-only**: it is never
committed here, attached to a release, or distributed.

### Environmental executions — vending machine + dumpster

Two environmental executions were scrapped but are **fully functional in
the final game** (TCRF). Both were cut from the Red Light level. Their
animations are unfinished/buggy, but the code, animations, and audio are
all present. The Manhunt Wiki lists **20 cut environmental executions
total** with surviving audio in the final build: Vending Machine, Dumpster,
Picket, Aztec Altar, Harvester, Prop, Barrier, Broken Window, Door, Wooden
Plank, Fence Pole, Chair, Sink, Bathtub, Agent Prime, Tombstone, Television,
Window Throw, Hangman Pole, Guillotine.

Restoration = re-enabling triggers via level scripting (MLS bytecode).
sor3nt's **manhunt-toolkit** (open source, PHP) can recompile MLS and is
the tool for this job. Note that the vending machine *model* is
prototype-only (see above), so its execution also needs the asset graft,
not just the trigger.

### Dildo / newspaper weapons — the beta is needed

Community notes claimed `dildo_(CT)` was still present in the Safe House level.
Checking the disc directly settles it: retail's string table has no `dildo`
entry, the `dildo` chunk exists only in the prototype, and a blind model-bank
swap crashes the level. So this is a model port, not a script edit.

**What retail actually kept, measured per file.** The weapon and camera records
live in `/GLOBAL/INIS`, the rest in `/LEVELS/A07_2T`:

| piece | where | retail | prototype |
|---|---|---|---|
| `WEAPTD.INI` `RECORD dildo` | `/GLOBAL/INIS` | present | present |
| `TVP.INI` `EXECUTE_DILDO2/3/4` camera records | `/GLOBAL/INIS` | present | present |
| `MAT.BIN` texture name `dildo02` | level | present (stale — no mesh) | present |
| `MODELS.DFF` dildo clump | level | **absent** | present |
| `STRMANIM.BIN` dildo animations | level | **absent** (0 of 11) | 11 blocks |
| `ENTTDATA.INI` `dildo(CT)` record | level | **absent** | present |
| `ENTINST.BIN` placement | level | **absent** | present |

So animations do **not** survive in this level — they were deleted with the mesh,
not left behind. That matters because the entity record *names* them:

```
ANIMATION_BLOCK     EntityAnims
MODEL_DISPLAY_ANIM  Dildo_Spin_W
EXECUTE_TVP         EXECUTE_DILDO2 / 3 / 4
```

**Result of building the first half and booting it.** Grafting the dildo clump
into `MODELS.DFF` and appending the prototype's `dildo(CT)` RECORD plus one
placement verifies cleanly on the image — the model library gains the clump, the
entity gains its record and instance at the right coordinates, and every file
stays inside its extent. On hardware the level boots and plays, and **nothing
renders**. With the position no longer in question (the placement was moved to
the player's own spawn point, one step in front, and still showed nothing), the
cause is the missing animation set: the entity is created, its animation block
fails to resolve, and no object appears.

The lesson generalises: **for this engine, an entity's animations are load-bearing,
not decoration.** A cut weapon cannot be restored by its model and placement
alone.

**One gotcha for anyone else attempting it.** Retail's `WEAPONS.INI` is not just
missing the dildo row, it is **renumbered**. `NUM_SOUNDS` drops 52 → 48, the
`DILDO_MELEE_COLLISION` row is gone, and rows after it shift down — the
prototype's `BASEBALL_BAT_BLADES_MELEE_COLLISION 41` ships as
`WOOD_BAT_MELEE_COLLISION 37`. So the prototype's index 30 is **not** the same
sound as retail's index 30, and mapping one build's index straight onto the other
silently picks the wrong audio.

`STRMANIM.BIN` is the file that carries the animations. Its format is decoded:
a 2048-byte header holding a *flattened* stream of `(offset, size)` chunk
entries (some followed by group sub-count dwords), then 2048-aligned `ANPK`
chunks, each beginning `u32 group_count` and then per-animation
`NAME`/length/name/tag/compressed-size/uncompressed-size records. Because chunk
offsets are absolute and every chunk is self-contained compressed bone data,
appending a chunk at the end of the file moves nothing — the same append-at-end
shape as the model graft.

### End-of-level rating system

Deliberately removed during the AO→M edits — former Rockstar VP Jeronimo
Barrera (MTV, 2007): *"The scoring was a holdover from the first game, and
when we had the opportunity to make edits because of the rating, we decided
to remove it."* The PC build ships it working. Whether the PS2 code is
merely disabled or compiled out is under investigation.

### "bananahammer" fun mode

The first cheat ever found for MH2 PC (Dixmor Hospital): type
`bananahammer` at the main menu. All melee weapons become flower bouquets,
blood becomes colorful flowers, firearms become candy canes/rubber ducks.
It's entity-swap based (`OneHandBouquet_(CT)` / `TwoHandBouquet_(CT)`).
Worth checking if the code path exists in the PS2 build.

### PS2 debug displays (pnach-ready)

From TCRF, exact USA RAM addresses — usable directly as PCSX2 pnach cheats:

| Display | USA address |
|---|---|
| Execution Information | `005B26D0 00000001` |
| Memory Usage | `0066CBBC 00000001` |
| Active Shadow Cameras | `0066CBF0 00000001` |
| Timer Values | `0066CBB8 00000000` + `0066CDE8 00000001` |
| Overscan Boundaries | `0066C9C8 00000001` |
| Textbox Boundaries | `0066C9E4 00000001` |

### Button cheats (PS2)

- **Level select:** Up, Up, Down, Down, Left, Right, Left, Right — **not in the
  USA build.** Verify for yourself: none of it is in the disc, and entering it
  does nothing. See
  [the level list](#the-level-list-that-ships-but-is-not-linked) for what the PS2
  release actually ships instead.
- **Infinite ammo:** Up, Down, Left, Right, Up, Down, Left, Right — reported, not
  checked here. Expect the same caveat: no cheat table was found in the boot ELF,
  so treat PS2 button codes as unconfirmed until someone finds the handler.

(Cheats disable autosave.)

## 60 fps layer (withdrawn)

There is no 60 fps layer. Two candidate targets were investigated and both are
wrong:

- The ten `30.0` floats in the boot ELF are **gameplay tuning constants**, not a
  frame timer. They live in the float constant pool (`0x3F87xx`–`0x3FBFxx`)
  alongside `60.0` values. Replacing them with `60.0` corrupts gameplay tuning.
- The `60.0f` compare at `0x39BAA8` is not a limiter either. It is inside the
  CRI ADX audio library: the function containing it (entry `0x39B990`) asserts
  `E02080815 adxt_GetTime: parameter error`, and the `60.0f` / `-60.0f` pair is
  a symmetric sanity window on an audio-time ratio, `((A/B) - (*out/C)) * 10000.0`.
  Its sibling assert is `E06022201 adxt_Create: Work size is too short.`

No safe single-site framerate change was found, so the layer is dropped rather
than shipped. `patch_60fps.py` is now read-only evidence plus a `revert` for
anyone who applied the older revision:

```
py patch_60fps.py audit  "Manhunt 2 (USA).iso"   # prints both findings
py patch_60fps.py status "Manhunt 2 (USA).iso"   # is the old swap applied?
py patch_60fps.py revert "Manhunt 2 (USA).iso"   # undo the old swap
```

Address mapping for anyone re-deriving the offsets: the boot ELF has a single
`PT_LOAD` (`p_offset 0x1000`, `p_vaddr 0x00100000`), so
`file_offset = vaddr - 0xFF000`; `0x39BAA8` is file offset `0x29CAA8`.

Background from the research that still stands:

- The PS2 build is vsync-paced: probing `SLUS_216.13` found no CP0 Count reads
  and no integer timestep, so the limiter is not a discrete timer value.
- ermaccer's PC 60fps patch
  (`Manhunt2.PluginMH2`, `dllmain.cpp`) changes a 2-byte frame timer from
  ~33.3ms to ~16.7ms (`Patch<short>(0x40D2A3, 0x412B)`); the PS2 build has no
  equivalent timer to retarget.
- **Caution:** ThirteenAG's Manhunt 1 fixer caps framerate at 60fps because the
  RenderWare-era AI breaks above that — the engine ties AI timing to framerate.
  A PS2 rate change would carry the same risk.
- No public PS2 60fps patch exists.



---

## Progress Chart

`
Task Progress
─────────────────────────────────────────────────────

Red-Filter Removal     ████████████████████ 100% ✅ (hardware confirmed)
Level List             ████████████████████ 100% ✅ (hardware confirmed)
Cut Content Research   ████████████░░░░░░░░  60% 🔄 (in progress)
60 FPS Patch           ░░░░░░░░░░░░░░░░░░░░   0% ❌ (withdrawn)
Model Graft            ████████████░░░░░░░░  60% 🔄 (local only)
Entity Layer           ████████████████████ 100% ✅ (decoded)

Legend: ✅ Done  🔄 In Progress  ⏳ Pending  ❌ Withdrawn
`

## Tools

Python 3, zero dependencies:

- **`patch_iso.py`** — the red-filter patch: `apply` / `verify` / `revert` on
  `GLOBAL/LVLSETUP.INI`, writing a `<iso>.orig` restore block.
- **`patch_60fps.py`** — withdrawn-layer tooling: `audit` / `status` / `revert`
  on the boot ELF. It no longer writes anything on its own; `revert` undoes the
  old `<iso>.60fps.orig` swap.
- **`patch_cutcontent.py`** — read-only cut-content audit. Walks the disc and
  reports what is present, what is a name stub, and what was deleted. It does
  not write to the image.

The cut-content workbench itself — the `PMLC` graft, the entity layer, the
level-list edit — is **not** shipped here: it either writes prototype bytes into
an image or is still being confirmed on hardware. The container formats it needs
are documented above, so the work can be reproduced from a retail disc plus a
prototype build.

Field notes live in `CUTCONTENT_FINDINGS.md`, `CUTCONTENT_NOTES.md` and
`CUTCONTENT_COMMUNITY_NOTES.md`.


---

## Resources

- [TCRF - Manhunt 2](https://tcrf.net/Manhunt_2) - Cut content documentation
- [Manhunt Wiki](https://manhunt.fandom.com/) - Community wiki
- [sor3nt/manhunt-toolkit](https://github.com/Sor3nt/manhunt-toolkit) - MLS recompiler
- [ermaccer/Manhunt2.PluginMH2](https://github.com/ermaccer/Manhunt2.PluginMH2) - PC 60fps patch
- [Manhunt 2 NOKILLFILTER](https://www.moddb.com/) - Community PS2 release (reference)

## References

- **DeBuGWoLf** — *No Execution Filter + extra*, PC (Dixmor Hospital / ModDB). Names
  a non-existent texture (`FE_`) and restores the pre-release flash timing.
- **smitty.dmg** — *MANHUNT 2 NOKILLFILTER* PS2 release (used as the reference).
- **ermaccer** — PSP *Censorship Removal Patch*, which does the same job for the
  PSP release in code.
- The Manhunt community.

- **TCRF** — [Manhunt 2](https://tcrf.net/Manhunt_2): debug addresses,
  cut executions, prototype info
- **Manhunt Wiki** — [Cut content list](https://manhunt.fandom.com/wiki/List_of_Cut_Manhunt_2_Content),
  [Cheats](https://manhuntgame.fandom.com/wiki/Cheats_in_Manhunt_2)
- **Dixmor Hospital** — [dixmor-hospital.com](https://www.dixmor-hospital.com/):
  bananahammer video, vending machine restoration video, grenade mod
- **sor3nt/manhunt-toolkit** — [GitHub](https://github.com/Sor3nt/manhunt-toolkit):
  MLS recompiler, GLG/INST/SCC handler
- **ermaccer/Manhunt2.PluginMH2** — [GitHub](https://github.com/ermaccer/Manhunt2.PluginMH2):
  PC 60fps patch source (`Patch<short>(0x40D2A3, 0x412B)`)
- **ThirteenAG** — Manhunt 1 framerate/AI findings (Steam guide)

*Manhunt and Manhunt 2 are trademarks of Take-Two Interactive / Rockstar Games.
This repository contains no game data and is not affiliated with them.*
---

## License

Research documentation only. No game data distributed. Legitimate copy required.
No console IDs, LAN IPs, or local paths committed.


---

## Restoration Analyzer v0.3 (research utility)

The separate **read-only** Manhunt 2 Restoration Analyzer inventories ISO9660 files, computes SHA-256 hashes, and compares file manifests across privately held PS2/PSP reference images. It does not modify game data or create an ISO.

**v0.3 hardening:** rejects directory loops, invalid paths, malformed records crossing ISO sector boundaries, and unsafe oversized directory data; CSV report output is protected against spreadsheet formula injection. Ten synthetic automated tests passed. **The analyzer has not yet been tested against the project's actual game ISOs.**

The packaged v0.3 tool is stored privately in the project's Google Drive handoff; no copyrighted ISOs or extracted assets are published here. Next steps: validate real-image parsing, compare build manifests, and identify one authentic cut-content candidate for isolated restoration and PS3 testing.


### Analyzer v0.4 update (2026-10-21)

Read-only analyzer v0.4 now searches the ISO9660 descriptor sequence for the primary descriptor (boot records can precede it), validates 2048-byte logical block sizes, rejects malformed/truncated directory records, and sanitizes CSV column headings. **13 synthetic unit tests pass.** The ZIP is available in the private Google Drive handoff. Actual Manhunt 2 ISOs have **not** yet been scanned with v0.4; these are parser hardening fixes, not verified cut-content discoveries.


### Analyzer v0.5.0 (pre-release)

Read-only analyzer v0.5 validates the declared ISO9660 volume size (including dual-endian agreement), rejects filenames with control characters and invalid version suffixes, protects CSV values with formula operators after leading whitespace, and adds `--version`. **17 synthetic tests passed.** The ZIP was uploaded to the private Google Drive handoff. **Not v1.0:** real game-image compatibility, manifest cross-checking, and release packaging still need verification. No ISOs or game assets were committed.


### Analyzer v0.6.0 — private pre-release

Parser safety update: rejects empty ISO identifiers, nonempty files with zero extent, and unsupported multi-extent root directories; comparison equality checks both size and SHA-256; report output collision detection prevents overwriting input images. **22 synthetic tests passed**, including an independent SHA-256 check. Private ZIP is held in the owner's Google Drive; **source and tool ZIP are not published to GitHub**. Still awaiting real-game ISO compatibility and report verification before v1.0.


### Analyzer v0.7.0 — private pre-release

Additional ISO9660 safety checks validate directory-record length/padding, volume-sequence number and endianness, and `.`/`..` directory metadata. Root zero-extents are rejected and descriptor scanning now handles up to 256 descriptors. **28 synthetic tests passed.** Private ZIP stored in the owner's Google Drive; **tool source and ZIP are not public**. Still pending: scan real owned images, independently verify hashes/manifests, and confirm PS2/PSP compatibility before v1.0.


### Analyzer v0.8.0 — private pre-release

Parser hardening now rejects unknown ISO9660 descriptor types, validates root-directory bounds before reading, and prevents report-output overwrites via hard links. Added independent SHA-256 checks against direct ISO byte slices, controlled changed-file comparison, and end-to-end JSON/CSV report verification. **33 synthetic tests passed.** Private ZIP is stored in the owner's Google Drive and is not publicly distributed. **v1.0 blocker:** run against the four real Manhunt 2 images and independently inspect the resulting manifests; those images have not been scanned in this environment.


### Analyzer v0.9.0 — private pre-release

Safety update: existing report files are protected by default, with an explicit `--overwrite` option for intentional replacement. Parser rejects ISO9660 directory names with file-version suffixes and invalid `;0` file versions. **37 automated synthetic tests passed** (four added). Private tool ZIP is retained in the owner's Google Drive; no analyzer source or binaries are published here. **Still not v1.0:** real Manhunt 2 ISO compatibility and independent external-parser validation remain pending.


### Analyzer v0.10.0 — private pre-release

Additional ISO9660 hardening rejects nonzero directory-sector padding and duplicate input images referenced through different hard-linked filenames. **39 synthetic regression tests passed.** The updated ZIP is stored privately in the owner's Google Drive, not on this public repository. **Real Manhunt 2 images have not been scanned**; independent verification of real-build manifests remains a requirement before v1.0.


### Analyzer v0.12.0 — private pre-release (2026-10-23)

The latest **locally verified** read-only Analyzer fixes incomplete/mixed report sets when a later ISO scan fails and disambiguates same-named input builds in JSON/CSV comparisons. **47/47 synthetic tests passed on Linux.** Real Manhunt 2 ISO scanning remains unverified. See [the v0.12 verification notes](docs/ANALYZER_V0_12_STATUS.md). The v0.12 package is private; no game images or assets are published.

### PS3 HEN conversion — 2026-10-21

**Proven:** the owner's supplied USA uncensored ISO (`SLUS_216.13`) was converted to PS2 Classics `ISO.BIN.ENC`. Decrypting the result reproduced all **2,657,058,816 bytes** with the exact original SHA-256. The matching encrypted emulator CONFIG and launcher installer were prepared locally. **HEN hardware compatibility is still unverified**; earlier CFW hardware results do not establish it. The conversion preserves the supplied ISO; it does not independently verify its uncensor changes or restore content.

See [PS3 HEN conversion: evidence, hashes, setup, and next hardware test](docs/PS3-HEN-CONVERSION.md). Game images and conversion binaries remain local.

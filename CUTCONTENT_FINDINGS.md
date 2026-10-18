# Manhunt 2 cut content — what retail actually ships

Field notes for the cut-content layer. Everything below was measured against the
USA retail ISO (`/SLUS_216.13`, 3,703,880 bytes) and, where noted, against the
prototype build kept locally as `build/prototype.iso`. Reproduce with
`patch_cutcontent.py audit <iso>`.

## Bottom line

The famously "cut" content — the vending machine, guillotine, tombstone, Aztec
altar, picket, harvester, agent prime, wooden blank, broken window, fence pole
executions, and the dildo weapon — **cannot be restored from the retail disc
alone.** Their assets were *deleted*, not merely unwired.

Earlier thinking (ours and the community's phrasing) said the data "ships but is
not wired up". That is true for some objects. It is not true for the cut items:
for those, the engine still knows the *name*, but the level no longer contains
the model, texture, animation or sound to back it.

Restoring them needs assets from a beta/prototype build. That is exactly what
the community PS2 mods do — e.g. "Uncensored Execution Animations PS2 version"
(ramonjones/givemeanumber) and "Dildo in PS2 Retail" (Semen123) ship replacement
`STRMANIM.BIN` / `AUD_PS2.AFS` files taken from a beta, not a retail-derived edit.

That is also why the earlier assumption — "the meshes ship, only the placement
is missing" — is wrong. The mesh files are zlib-wrapped RenderWare clump
libraries and they were rewritten; see "Graft feasibility" below.

## Method

1. Read the 33 environment-execution type names out of the engine. The boot ELF
   holds exactly 33 `BAT_<DAMAGE|USE|DIE>_EXECUTE_ENVIRONMENTAL_<TYPE>`
   triples.
2. For every level, search the files that carry execution animation names
   (`STRMANIM.BIN`, `ALLANIMS.IFP`, the level `.MLS`) for those exact strings.
   That is the ground truth for which executions a level can actually run.
   Bare type-name substring searches are unreliable — object names such as
   `CJ_Dumpster` collide with `DUMPSTER`.
3. Scan every file on the disc for each cut item's name, to separate "asset
   present" from "name stub only".

## Result 1 — which environment executions retail can actually run

Only these types have animation data somewhere in retail:

| type | level(s) with the animation |
|---|---|
| DENTIST_CHAIR | A04_SM |
| DUMPSTER | A07_2T |
| FIREEXT | A10_BR, A11_ME, A16_TV |
| FUSE_BOX | A09_BU, A10_BR, A14_SU, A16_TV |
| IRON_MAIDEN | A04_SM |
| LIQUID_NITROGEN | A11_ME |
| MANGLER | A14_SU |
| MANHOLE | A03_NE, A07_2T, A07_TO |
| MEATHOOK | A04_SM, A09_BU, A17_CR |
| OILBARREL | A06_CI, A17_CR, A18_MA |
| TELEPHONE | A10_BR |
| TOILET | A04_SM, A10_BR |

The other types have **no animation data anywhere on the disc**. For ten of them
the name survives only in the engine's type table and in `GLOBAL/INIS/TVP.INI`:

    VENDING  PICKET  GUILLOTINE  TOMBSTONE  AZTEC_ALTAR
    HARVESTER  AGENTPRIME  WOODENBLANK  BROKENWINDOW  FENCE_POLE

Full-disc name scan, retail:

```
VENDING      TVP.INI, SLUS_216.13 only
PICKET       TVP.INI, SLUS_216.13
GUILLOTINE   TVP.INI, SLUS_216.13
TOMBSTONE    TVP.INI, SLUS_216.13
AZTEC        TVP.INI, SLUS_216.13
HARVESTER    TVP.INI, SLUS_216.13
AGENTPRIME   SLUS_216.13
WOODENBLANK  TVP.INI, SLUS_216.13
BROKENWINDOW TVP.INI, SLUS_216.13
FENCE_POLE   TVP.INI, SLUS_216.13
```

No model, no texture, no animation, no sound, no placement, anywhere.

The stereo type name for the animation is `STRMANIM.BIN`'s job: it holds named
animation blocks. Retail registers a subset of what the prototype did. Diffing
the two builds' `STRMANIM.BIN` name tables, retail is missing exactly three
registrations the prototype had:

* **A07_2T: `VENDING`** — the vending machine (A07 is the mission the community
  calls the Safe House)
* **A03_NE: `PICKET`**
* **A02_TH: `MANHOLE`**

and adds none. So even against a build that had them, retail *removed* them.

## Result 2 — the dildo is not restorable from retail either

The dildo is the most promising cut weapon, and the community placed it in the
Safe House on PS2 retail. Retail does ship parts of it:

| piece | retail | prototype |
|---|---|---|
| `WEAPTD.INI` weapon record | present | present |
| `TVP.INI` `EXECUTE_DILDO2/3/4`, `EXEC_DILDO_JUMP_ANIM` | present | present |
| engine `dildo(CT)` / `CT_DILDO` names | present (ELF) | present (ELF) |
| `MAT.BIN` texture `dildo02` (A07_2T, A07_TO) | present | present |
| `STRMANIM.BIN` dildo animations (A07_2T) | **absent** | 11 blocks |
| `AUD_PS2.AFS` dildo sounds (A07_2T) | **absent** | 4 entries |
| `ENTTDATA.INI` `dildo(CT)` entity record | **absent** | present |
| `ENTINST.BIN` `dildo(CT)` placements | **absent** | present |

The prototype's A07_2T `STRMANIM.BIN` carries the dildo execution animation set:

```
BAT_USE_EXECUTE_DILDO2      BAT_DAMAGE_EXECUTE_DILDO2   BAT_DIE_EXECUTE_DILDO2
BAT_USE_EXECUTE_DILDO3      BAT_DAMAGE_EXECUTE_DILDO3   BAT_DIE_EXECUTE_DILDO3
BAT_USE_EXECUTE_DILDO4      BAT_DAMAGE_EXECUTE_DILDO4   BAT_DIE_EXECUTE_DILDO4
```

Retail A07_2T `STRMANIM.BIN` contains none of them, and retail `AUD_PS2.AFS`
contains none of the dildo sounds. So a retail-only patch can add the entity
record and the spawn, but the weapon would have no attack/execution animation
and no audio — a broken or crashing object, not a restoration.

## What this means

* The 10 listed environment executions are **not restorable from retail**.
* The dildo is **not restorable from retail**.
* `CUT_THROAT_RAZOR` is worse: it has a `WEAPTD.INI` definition but no dedicated
  model, texture, animation or sound anywhere on retail. Not restorable.
* The "already live" weapons (syringe, shard, sickle, katana, pliers, hacksaw)
  need nothing.

The community's "restore cut content" mods work because they *import beta
assets*. A pure in-place patch on the retail image cannot do that.

## If we want to actually restore something

The prototype build kept locally has the missing pieces for at least the Safe
House dildo (animation blocks, sounds, entity data). A real restoration would be
an **asset graft**:

1. extract the dildo animation blocks from the prototype's `STRMANIM.BIN`,
2. insert them into retail A07_2T `STRMANIM.BIN` (format + size work),
3. graft the dildo sounds into retail `AUD_PS2.AFS`,
4. add the `dildo(CT)` entity record to `ENTTDATA.INI` and a placement,

and it would depend on the prototype image being present at patch time. It could
not be published as a self-contained patch, because the grafted bytes are beta
game data. Steps 1–3 are a substantial binary-format project on their own.

## Graft feasibility — the formats, measured

The earlier "the containers are opaque" worry was wrong. Decompressing the
level's archives shows ordinary, parseable data:

| file | container | notes |
|---|---|---|
| `MODELS.DFF` | `Z2HM` magic, u32 uncompressed size, then zlib | decompresses to a `PMLC` RenderWare clump library with plaintext mesh names (`Small_Shell`, `6Shooter_(CT)`, `6Shooter_MasterBone`, …) |
| `TEXPS2.TXD` | same `Z2HM` + zlib | texture library |
| `STRMANIM.BIN` | custom | 2048-byte header table of `(offset, size)` pairs; 2048-aligned chunks, each starting `ANPK`, then `NAME` + u32 length + name, then a zlib payload |
| `ALLANIMS.IFP` | RenderWare `IFP` animation stream | documented format |
| `AUD_PS2.AFS` | standard AFS | `AFS\0`, u32 count, count × `(offset, size)` u32 pairs, data from 0x800 |
| `ENTINST.BIN` | custom | u32 count (359 retail / 358 prototype in A07_2T) + fixed records |
| `ENTTDATA.INI` | plain text | `RECORD …` / `END` entity definitions |

Measured, level A07_2T:

```
                        retail      prototype
MODELS.DFF  (unpacked)  2331672       2972784
TEXPS2.TXD  (packed)    2774509       2925125
STRMANIM.BIN (packed)   1667072       1374208
AUD_PS2.AFS             34134016      60448768
ENTINST.BIN              62524         62736
ENTTDATA.INI             49318         50675
```

Decompressing every `.DFF` on the retail disc and scanning for the cut names
(`vending`, `dildo`, `picket`, `guillotine`, `tombstone`, `harvest`) finds
**nothing, in any level.** The prototype's `A07_2T/MODELS.DFF` has `vending` ×1
and `dildo` ×4. So the meshes were deleted, not unwired — the `dildo02` string
left in `MAT.BIN` is a stale material name, not a mesh.

`STRMANIM.BIN` name-set diff for `A07_2T` (retail 99 names, prototype 101):

* prototype-only (26): 11 dildo, 12 pliers, 3 `BAT_*_EXECUTE_ENVIRONMENTAL_VENDING`
* retail-only (24): 12 crowbar, 12 flashlight

So development swapped the Safe House's execution animations — dildo/pliers/
vending out, crowbar/flashlight in. A graft must *add* the 26 prototype chunks,
not replace the file, or it loses the retail-only animations.

A working graft therefore has to carry, at minimum:

* `MODELS.DFF` — append the `vendingmachine` (or dildo) clump, rebuild the
  `PMLC` index, re-zlib the archive
* `TEXPS2.TXD` — append the matching textures, same treatment
* `MAT.BIN` — material records
* `COL.COL` — the `vendingmachine` collision entry
* `STRMANIM.BIN` — the 3 vending / 11 dildo animation chunks plus the header table
* `AUD_PS2.AFS` — the matching sounds
* `ENTTDATA.INI` — the entity `RECORD`
* `ENTINST.BIN` — a placement

Anything that grows must move to free space and have its ISO9660 directory
record rewritten: retail has 21 MB free at the tail and 517 KB of per-file
slack, but no large contiguous hole.

That is the project. None of it needs an emulator, but it is several binary
formats deep and every stage needs a hardware smoke test.

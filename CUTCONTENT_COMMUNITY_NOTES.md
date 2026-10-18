# Manhunt 2 cut content — community research notes

Field notes gathered from the Manhunt modding community while scoping the
cut-content patch layer. Sources are cited inline. Nothing here is a claim about
our own disc until it has been checked against the USA ISO locally.

## Headline correction: "cut" often means "not wired up"

The engine's environment-execution type table (33 entries, read from the ELF)
lists types that no level places an object for. My first read of that assumed the
absence of a placed object meant the content was deleted. The community says
otherwise, and the community is right:

> Two environmental executions known as Vending Machine and Dumpster were
> scrapped. They are fully functional even in the final game and can be
> [enabled].
> — TCRF, "Manhunt 2"

So for environment executions the animation and support data ship on the retail
disc, intact. What was removed is the *placement* — the object in the level that
arms it. That is a different, much smaller edit than restoring deleted assets,
and it is the same shape of problem as the weapon findings (see below).

## The cut environment executions, and who restored what

| execution | where it belonged | status in retail | community restoration |
|---|---|---|---|
| Vending Machine | Safe House | cut, fully functional | Sor3nt + MAJESTIC_R3, "Lost Environmental Executions - The Vending Machine", 2019, 9,016 downloads |
| Dumpster | Safe House | cut, fully functional | MAJESTIC_R3 |
| Guillotine | — | cut | confirmed present in beta builds |
| Tombstone | — | cut | confirmed present in beta builds |
| Aztec Altar | cut museum level | cut | level itself was cut |
| Picket | — | cut | namefulll |
| Wooden spike | Domestic Disturbance | cut, bugged | implemented by Extended Executions |
| Meat hook | — | unused in retail | present in beta |
| Liquid nitrogen | — | unused in retail | present in beta |

The beta 0.01 PSP build showcase (18,335 views, 2024) confirms the full retail
environmental set that *is* wired: Toilet, Barrel, Dentist Chair, Guillotine,
Iron Maiden, Meat Hook, Electrical Box, Fire Extinguisher, Gasoline Puddle,
Grinder, Liquid Nitrogen, Phone, Sewer Grate. Several of those (Guillotine, Meat
Hook, Liquid Nitrogen) are present in the beta but absent from retail level
placement — consistent with the type-table scan.

## The mod that does exactly what we are attempting

**Manhunt 2 Extended Executions** (ModDB, 2012, updated 2015, 139,645 visits) is
the reference implementation. Its published file recipe is the important part —
it lists which files must change to add/restore executions and weapon spawns:

- `A**.mls` — level script / spawns
- `strmanim.bin` — available execution animations, **interchangeable between
  levels**
- `allanims_pc.ifp` — other animations, execution object animations
- `entity_pc.inst` — entity placements
- `resource3.glg` — main ini of each level, many variables
- `resource13.glg` — execution camera vectors
- `resource21.glg` — victim decal data
- `resource28.glg` — interactive controls
- `resource11.glg` — weapon hit effects
- `Executions.fsb` — remastered PS2 execution audio

Two things follow for us.

1. **`strmanim.bin` is the gate, and it is shared between levels.** The PS2
   disc carries `STRMANIM.BIN` per level (e.g. A14_SU ships 1,464,320 bytes).
   The mod treats it as interchangeable, which means an animation can be made
   available to a level by giving that level the right STRMANIM, rather than by
   editing the ELF. That is a strong candidate mechanism for our patch layer and
   it is data-only.

2. **Weapon "restoration" is mostly respawning, not asset recovery.** The mod's
   per-level change list is almost entirely `Replaced X with Y` and
   `Added Z at start` — e.g. Ghosts 1 "Replaced Bottles with Sickle & Shard",
   Broadcast 2 "Working Katana, Circular Saw, Bat", Safehouse 1 "Replaced Crowbar
   with Dildo". This confirms the earlier finding that the cut weapons are fully
   defined in retail `WEAPTD.INI` and only their level placement is missing. It
   also confirms the practical technique: **swap an existing spawn slot for a cut
   weapon**, which is length-preserving if the record sizes match.

## Weapon findings, corroborated

The community's cut-weapon list matches the disc scan: dildo, sickle, shard,
syringe, katana, razor (CUT_THROAT_RAZOR), hacksaw, plus newspaper, mace,
flashlight, plastic bag and circular saw as version-specific entries. Note that
several of these are already spawnable in retail — the Extended Executions notes
show syringe, shard and sickle actively placed in retail levels, which agrees
with the ENTTDATA/ENTINST analysis rather than the older "only spawning was
removed" assumption.

"Dildo in PS2 Retail" (Semen123, 2024, 1,399 downloads) is the direct PS2
precedent for the dildo weapon: "added weapons for the safe house level along
with sounds". So the weapon is placeable on PS2 retail with sound support intact.

## Active community venues

- **dixmor-hospital.com** — the main Manhunt modding forum, 58 pages of Manhunt 2
  mods, has explicit PS2 platform filtering and a Discord. This is where PS2 work
  is happening now (most recent PS2 release 22.09.2026).
- **ModDB** — long-term home of Extended Executions and Razormoon.
- **r/Manhunt, r/ManhuntGames** — beta cut-content discussion.
- Notable PS2 modders: RAMONJONES, Semen123, Max Payne, Sor3nt, MAJESTIC_R3,
  chorpthon (Razormoon), Megahoff (execution animation author).

## What this means for our patch layer

The blocker identified for weapons — that restoring cut content needs new bytes
and the ISO files are packed at exact size — applies with less force to
environment executions, because the assets already ship. The open question is
whether the per-level STRMANIM/ENTINST can be edited in place. That is the next
thing to check against the USA ISO, and it should be checked before promising
any specific execution as restorable.

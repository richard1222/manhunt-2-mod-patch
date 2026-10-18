"""Cut-content audit for Manhunt 2 (PS2, USA).

There is no cut-content *patch* here, and this file deliberately does not
pretend otherwise.  The audit below establishes why, from the disc itself.

Summary of the finding (see CUTCONTENT_FINDINGS.md for the evidence):

  * The "cut" environment executions -- vending machine, guillotine, tombstone,
    Aztec altar, picket, harvester, agent prime, wooden blank, broken window,
    fence pole -- ship on retail as a *name only*.  The name survives in the
    engine's type table and in GLOBAL/INIS/TVP.INI; there is no model, texture,
    animation, sound or placement anywhere on the disc.

  * The dildo weapon ships its data record, its global execution camera records
    and its texture, but not its level animations or sounds -- those were
    deleted from the Safe House (A07_2T) STRMANIM.BIN and AUD_PS2.AFS.

  * CUT_THROAT_RAZOR ships a weapon record and nothing else.

So none of the cut content can be restored by an in-place edit of the retail
image.  Restoring it means importing assets from a beta/prototype build, which
is a different (and non-publishable) kind of patch.

What this tool does: it reads the boot ELF and every file on the disc and
reports, per cut item, whether the files a restoration would need are actually
present.  It is read-only; it never writes to the image.

Usage:
    py patch_cutcontent.py audit  <iso>
    py patch_cutcontent.py verify <iso>

Requires: ps2iso.py, alongside this file.
"""
import re
import sys

import ps2iso

ELF_NAME = "SLUS_216.13"

# Environment-execution types that retail cannot run: the engine still names
# them, but no level carries the animation.
CUT_EXEC_TYPES = [
    "VENDING", "GUILLOTINE", "TOMBSTONE", "AZTEC_ALTAR", "PICKET",
    "HARVESTER", "AGENTPRIME", "WOODENBLANK", "BROKENWINDOW", "FENCE_POLE",
]

# Cut items worth auditing.  The token is the spelling the game data uses.
CUT_ITEMS = [
    ("vending machine", "VENDING"),
    ("guillotine", "GUILLOTINE"),
    ("tombstone", "TOMBSTONE"),
    ("Aztec altar", "AZTEC"),
    ("picket", "PICKET"),
    ("harvester", "HARVESTER"),
    ("agent prime", "AGENTPRIME"),
    ("wooden blank", "WOODENBLANK"),
    ("broken window", "BROKENWINDOW"),
    ("fence pole", "FENCE_POLE"),
    ("dildo (weapon)", "DILDO"),
    ("throat razor", "CUT_THROAT_RAZOR"),
]

# Files a restoration needs: animation banks, audio bank, placement data.
CONTENT = (".MLS", "STRMANIM.BIN", "ALLANIMS.IFP", "AUD_PS2.AFS",
           "ENTINST.BIN", "ENTTDATA.INI")

# Model/texture banks: art only -- says nothing about placement or animation.
BANK = (".TXD", ".DFF", "MAT.BIN", ".BNK")

# Name lists (engine, level type list, UI text): a hit is not content.
NAME_LIST = ("SLUS_216.13", "TVP.INI", "GAME.GXT")


def walk_tree(iso, entry, prefix, out):
    for x in iso.read_dir(entry):
        name = x.name.split(";")[0]
        if name in (".", ".."):
            continue
        path = prefix + "/" + name
        if x.is_dir:
            walk_tree(iso, x, path, out)
        else:
            out.append((x.size, path))


def engine_knows_type(elf, type_name):
    """How many BAT_<mode>_EXECUTE_ENVIRONMENTAL_<type> names the ELF has."""
    pat = rb"BAT_[A-Z0-9]+_EXECUTE_ENVIRONMENTAL_" + type_name.encode() + rb"\b"
    return len(re.findall(pat, elf))


def classify(hits):
    """Split file paths carrying a name into content / bank / name-list."""
    content, bank, names = [], [], []
    for p in hits:
        base = p.rsplit("/", 1)[-1]
        if any(base == s for s in ("SLUS_216.13", "TVP.INI", "GAME.GXT")):
            names.append(p)
        elif any(p.endswith(s) for s in CONTENT):
            content.append(p)
        elif any(p.endswith(s) for s in BANK):
            bank.append(p)
    return content, bank, names


def scan(iso, files, token):
    # Case-insensitive: the data spells some names lower case (the dildo
    # texture is "dildo02"), and no cut name collides with an unrelated asset
    # when folded, so this only makes the classification more accurate.
    tb = token.upper().encode()
    hits = []
    for size, path in files:
        if size == 0:
            continue
        try:
            if tb in iso.read_path(path).upper():
                hits.append(path)
        except Exception:
            continue
    return classify(hits)


def short(paths):
    return ", ".join(p.split("/", 2)[-1] for p in paths[:6])


def run(iso_path):
    iso = ps2iso.PS2ISO(iso_path)
    elf = iso.read_path("/" + ELF_NAME)
    files = []
    walk_tree(iso, iso.root, "", files)

    print("image : %s" % iso.iso.name)
    print("files : %d" % len(files))
    print()
    print("=" * 92)
    print("cut environment executions: does the engine still know the type?")
    print("=" * 92)
    for t in CUT_EXEC_TYPES:
        print("  %-16s %s" % (t, "yes" if engine_knows_type(elf, t) else "no"))
    print()
    print("=" * 92)
    print("does the disc ship the files a restoration needs?")
    print("=" * 92)
    print("  content = %s" % ", ".join(CONTENT))
    print("  bank    = %s  (art only; no placement/animation)" % ", ".join(BANK))
    print()

    name_only = []
    art_only = []
    for label, token in CUT_ITEMS:
        content, bank, names = scan(iso, files, token)
        if content:
            print("  %-18s CONTENT PRESENT  %s" % (label, short(content)))
        elif bank:
            art_only.append(label)
            print("  %-18s ART ONLY         %s" % (label, short(bank)))
        else:
            name_only.append(label)
            files_txt = short(names) if names else "(engine only)"
            print("  %-18s NAME ONLY        %s" % (label, files_txt))
    print()
    broken = art_only + name_only
    if broken:
        if name_only:
            print("NAME ONLY  : %s" % ", ".join(name_only))
        if art_only:
            print("ART ONLY   : %s" % ", ".join(art_only))
        print()
        print("VERDICT: none of these can be restored by an in-place edit of this")
        print("         image.  NAME ONLY items have no assets at all; ART ONLY")
        print("         items have art but no animation or placement.  Both need")
        print("         assets imported from a beta/prototype build.")
        return 1
    print("VERDICT: every audited item has content on this image.")
    return 0


def main(argv):
    if len(argv) < 2 or argv[0] not in ("audit", "verify"):
        print(__doc__)
        return 2
    return run(argv[1])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

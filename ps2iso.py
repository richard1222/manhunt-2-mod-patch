"""PS2 DVD image reader with random access.

Reads the ISO9660 filesystem on a PlayStation 2 DVD.  Works against a local
file OR against an image served over HTTP, fetched a few kilobytes at a time
with Range requests -- so a 2.5 GB disc can be browsed without ever
downloading it in full.

PS2 disc notes
    * sectors are 2048 bytes
    * the Primary Volume Descriptor lives at sector 16 (offset 0x8000)
    * PS2/PSF directory records are BOTH-ENDIAN: every 32-bit field is stored
      little-endian first, then big-endian.  Getting that backwards is the
      classic way to make a parser "work" on nothing.
    * the boot file is named in SYSTEM.CNF as  BOOT2 = cdrom0:\\SLUS_XXX.XX;1

Usage
    py ps2iso.py ls   <iso>
    py ps2iso.py tree <iso> [path]
    py ps2iso.py cat  <iso> <path> > out.bin
    py ps2iso.py info <iso>
    py ps2iso.py extract <iso> <path> <outfile>
    py ps2iso.py md5   <iso> <path>

<iso> may be a local path or an http:// URL, e.g.
    http://example.local/MOUNT_PATH/PS2ISO/Manhunt%202%20(USA).iso
"""
import os
import re
import sys
import struct
import hashlib
import urllib.request
import urllib.parse

SECTOR = 2048


# ---------------------------------------------------------------------------
# backends
# ---------------------------------------------------------------------------
class LocalISO:
    """Random access into a local image file."""

    def __init__(self, path):
        self.name = path
        self.f = open(path, "rb")
        self.size = os.path.getsize(path)

    def read(self, offset, length):
        self.f.seek(offset)
        return self.f.read(length)


class HttpISO:
    """Random access into an ISO served over HTTP, via Range requests.

    NOTE: not every HTTP file server honours Range -- some answer 200 with the
    whole file regardless.  This backend is kept for servers that do; otherwise
    fetch the image locally first.  Requests are retried a few times, because
    some servers are single-threaded and flaky.
    """

    def __init__(self, url, retries=5):
        self.url = url
        self.retries = retries
        self.name = url
        # HEAD gives us the size; fall back to a 1-byte probe
        req = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                self.size = int(r.headers.get("Content-Length", 0))
        except Exception:
            self.size = self._probe_size()

    def _probe_size(self):
        req = urllib.request.Request(
            self.url, headers={"Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            cr = r.headers.get("Content-Range", "")
            m = re.match(r"bytes \d+-\d+/(\d+)", cr)
            return int(m.group(1)) if m else 0

    def read(self, offset, length):
        if length <= 0:
            return b""
        last = min(offset + length, self.size) - 1
        if last < offset:
            return b""
        hdr = {"Range": "bytes=%d-%d" % (offset, last)}
        last_err = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(self.url, headers=hdr)
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                if data:
                    return data
                last_err = IOError("empty body for range %d-%d" % (offset, last))
            except Exception as e:                       # noqa: BLE001
                last_err = e
            import time
            time.sleep(0.4 * (attempt + 1))
        raise IOError("range read failed @%d: %s" % (offset, last_err))


def open_iso(spec):
    if re.match(r"^https?://", spec, re.I):
        return HttpISO(spec)
    if not os.path.exists(spec):
        raise SystemExit("no such image: %s" % spec)
    return LocalISO(spec)


# ---------------------------------------------------------------------------
# ISO9660
# ---------------------------------------------------------------------------
def both(buf, off):
    """Read a PS2 both-endian 32-bit field: LE at off, BE at off+4."""
    return struct.unpack_from("<I", buf, off)[0]


def both16(buf, off):
    return struct.unpack_from("<H", buf, off)[0]


def _strip_ver(name):
    """Drop the ISO9660 ';1' version suffix from a directory record name."""
    i = name.find(";")
    return name[:i] if i > 0 else name


class DirectoryEntry:
    __slots__ = ("name", "lba", "size", "is_dir", "flags", "raw")

    def __init__(self, name, lba, size, is_dir, flags, raw):
        self.name = name
        self.lba = lba
        self.size = size
        self.is_dir = is_dir
        self.flags = flags
        self.raw = raw

    def __repr__(self):
        kind = "DIR " if self.is_dir else "FILE"
        return "<%s %-40s lba=%-8d size=%d>" % (
            kind, self.name, self.lba, self.size)


class PS2ISO:
    def __init__(self, spec):
        self.iso = open_iso(spec)
        if self.iso.size and self.iso.size < SECTOR * 17:
            raise SystemExit("image is too small to hold a volume descriptor")
        self.pvd = self._find_pvd()
        self.volume_id = self.pvd[40:72].decode("ascii", "replace").strip()
        self.sector_size = both16(self.pvd, 128) or SECTOR
        self.volume_space = both(self.pvd, 80)
        self.root = self._parse_dir_record(self.pvd[156:190], "")

    # -- volume ------------------------------------------------------------
    def _find_pvd(self):
        """Scan volume descriptors from sector 16 until we hit the terminator."""
        off = 16 * SECTOR
        for _ in range(32):
            sec = self.iso.read(off, SECTOR)
            if len(sec) < SECTOR or sec[1:6] != b"CD001":
                break
            vdtype = sec[0]
            if vdtype == 1:                       # Primary Volume Descriptor
                return sec
            if vdtype == 255:                     # Volume Descriptor Set Terminator
                break
            off += SECTOR
        raise SystemExit("no ISO9660 Primary Volume Descriptor found")

    def _parse_dir_record(self, rec, name):
        if len(rec) < 34 or rec[0] < 34:
            return None
        lba = both(rec, 2)
        size = both(rec, 10)
        flags = rec[25]
        namelen = rec[32]
        rawname = rec[33:33 + namelen]
        if namelen == 1 and rawname in (b"\x00", b"\x01"):
            shown = "." if rawname == b"\x00" else ".."
        else:
            shown = rawname.decode("ascii", "replace")
        return DirectoryEntry(shown, lba, size, bool(flags & 0x02), flags, rec)

    # -- directory walking -------------------------------------------------
    def read_dir(self, entry):
        """Return the entries inside a directory entry."""
        data = self.iso.read(entry.lba * SECTOR, entry.size)
        out = []
        pos = 0
        while pos < len(data):
            reclen = data[pos]
            if reclen == 0:                       # pad to next sector
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            rec = data[pos:pos + reclen]
            e = self._parse_dir_record(rec, entry.name)
            if e and e.name not in (".", ".."):
                out.append(e)
            pos += reclen
        return out

    def resolve(self, path):
        """Walk a path like '/SLUS_216.13' to a DirectoryEntry.

        ISO9660 stores the file version as a ';N' suffix in the directory
        record name, so accept the path with or without it.
        """
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        cur = self.root
        for part in parts:
            if not cur.is_dir:
                raise SystemExit("not a directory: %s" % cur.name)
            want = _strip_ver(part)
            found = None
            for e in self.read_dir(cur):
                if _strip_ver(e.name).upper() == want.upper():
                    found = e
                    break
            if found is None:
                raise SystemExit("not on disc: %s" % path)
            cur = found
        return cur

    def read_file(self, entry):
        return self.iso.read(entry.lba * SECTOR, entry.size)

    def read_path(self, path):
        return self.read_file(self.resolve(path))

    # -- convenience -------------------------------------------------------
    def system_cnf(self):
        try:
            raw = self.read_path("/SYSTEM.CNF;1")
        except SystemExit:
            raw = self.read_path("/SYSTEM.CNF")
        return raw.decode("ascii", "replace")

    def boot_elf(self):
        """Return the boot ELF path named in SYSTEM.CNF, e.g. 'SLUS_216.13'.

        SYSTEM.CNF writes it as  cdrom0:\\SLUS_216.13;1  -- the trailing ;1 is
        the ISO9660 file version, not part of the name, so strip it before
        looking the entry up on disc.
        """
        cnf = self.system_cnf()
        m = re.search(r"BOOT2\s*=\s*cdrom0:\\?([^\s;]+)", cnf, re.I)
        return m.group(1) if m else None


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f TB" % n


def cmd_info(iso, args):
    print("image    : %s" % iso.iso.name)
    if iso.iso.size:
        print("size     : %s (%d bytes)" % (human(iso.iso.size), iso.iso.size))
    print("volume id: %s" % iso.volume_id)
    print("sectors  : %d (sector size %d)" % (iso.volume_space, iso.sector_size))
    print("root LBA : %d  size %d" % (iso.root.lba, iso.root.size))
    print()
    try:
        print("--- SYSTEM.CNF ---")
        print(iso.system_cnf())
    except SystemExit as e:
        print("(no SYSTEM.CNF: %s)" % e)
    boot = iso.boot_elf()
    if boot:
        print("boot ELF : %s" % boot)
        try:
            e = iso.resolve("/" + boot)
            print("           LBA %d  size %s" % (e.lba, human(e.size)))
            head = iso.read_file(e)[:4]
            print("           magic %r  %s" % (
                head, "OK (ELF)" if head == b"\x7fELF" else "NOT an ELF"))
        except SystemExit as ex:
            print("           (not found: %s)" % ex)


def cmd_ls(iso, args):
    path = args[0] if args else "/"
    e = iso.resolve(path)
    if not e.is_dir:
        print("%-42s %10s  lba %d" % (e.name, human(e.size), e.lba))
        return
    entries = iso.read_dir(e)
    entries.sort(key=lambda x: (not x.is_dir, x.name.upper()))
    for x in entries:
        print("%-42s %10s  lba %d" % (
            x.name if x.is_dir else x.name, human(x.size), x.lba))
    print("-- %d entries --" % len(entries))


def cmd_tree(iso, args):
    path = args[0] if args else "/"

    def walk(entry, prefix, depth):
        for x in sorted(iso.read_dir(entry),
                        key=lambda y: (not y.is_dir, y.name.upper())):
            if x.is_dir:
                print("%s%s/" % (prefix, x.name))
                if depth < 6:
                    walk(x, prefix + "  ", depth + 1)
            else:
                print("%s%-40s %10s" % (prefix, x.name, human(x.size)))

    e = iso.resolve(path)
    print("%s/" % path)
    if e.is_dir:
        walk(e, "  ", 0)


def cmd_cat(iso, args):
    sys.stdout.buffer.write(iso.read_path(args[0]))


def cmd_extract(iso, args):
    data = iso.read_path(args[0])
    with open(args[1], "wb") as f:
        f.write(data)
    print("wrote %s (%s)" % (args[1], human(len(data))))


def cmd_md5(iso, args):
    data = iso.read_path(args[0])
    print("%s  %s" % (hashlib.md5(data).hexdigest(), args[0]))


CMDS = {"info": cmd_info, "ls": cmd_ls, "tree": cmd_tree,
        "cat": cmd_cat, "extract": cmd_extract, "md5": cmd_md5}


def main(argv):
    if len(argv) < 2 or argv[0] not in CMDS:
        print(__doc__)
        return 2
    iso = PS2ISO(argv[1])
    CMDS[argv[0]](iso, argv[2:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

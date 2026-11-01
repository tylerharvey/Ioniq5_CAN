#!/usr/bin/env python3
"""pii_strip.py — remove PII-bearing frames from CAN logs, format-preserving.

Line-based filter: every retained line is written back byte-for-byte; only
frames whose arbitration id is in the strip set are dropped. Handles both
SavvyCAN exports (`Time Stamp,ID,...`, hex id, padded or not) and panda
logs (`Bus,MessageID,...`, `0x`-prefixed hex id) by sniffing the header.

Default strip set (see .artifacts/pii_findings.md for evidence):

  11-bit (Ioniq5):
    0x7E8 / 0x7EA   UDS physical request/response (carries VIN via 22 F1 90)
    0x6E7           AVN nav-text ISO-TP (street names, destinations)
    0x3CC           vehicle-static ASCII id '6140341'
  11-bit (Ioniq6 — 0x6E7 analogue, same text channel, still 11-bit there):
    0x6D6           AVN media-title ISO-TP
  29-bit (Ioniq6 — 0x3CC analogues, vehicle-static ASCII):
    0xD435503 'P66FED5E', 0xD435504 '8BE9132\\r', 0xF03CA02 '0000206\\x00'
  29-bit (GV60 — 0x3CC analogue):
    0x1004A03 '8774N2'

Usage:
  python pii_strip.py PATH... -o OUTDIR          # PATH = file or dir (recursive)
  python pii_strip.py PATH... --in-place         # overwrite originals
  python pii_strip.py --list                     # show the strip set

Output mirrors the input tree under OUTDIR (relative to the first dir arg).
"""
import argparse, pathlib, shutil, sys

STRIP_IDS = {
    0x7E8, 0x7EA, 0x6E7, 0x3CC,              # Ioniq5
    0x6D6,                                    # Ioniq6 text channel (11-bit)
    0xD435503, 0xD435504, 0xF03CA02,          # Ioniq6 29-bit static ids
    0x1004A03,                                # GV60 29-bit static id
}

def sniff(header_line):
    """Return id column index for the format, or None if unrecognized."""
    cols = [c.strip().lower() for c in header_line.split(',')]
    if 'id' in cols:
        return cols.index('id')          # SavvyCAN
    if 'messageid' in cols:
        return cols.index('messageid')   # panda
    return None

def strip_file(src, dst, strip=STRIP_IDS):
    """Filter src -> file object dst; return (kept, dropped, unparsed)."""
    with open(src, 'r', newline='') as f:
        header = f.readline()
        idcol = sniff(header)
        if idcol is None:
            sys.stderr.write(f'  !! unrecognized format: {src}\n')
            dst.write(header)
            shutil.copyfileobj(f, dst)
            return 0, 0, 0
        kept, dropped, unparsed = 1, 0, 0
        dst.write(header)
        for line in f:
            cols = line.split(',')
            try:
                # SavvyCAN ids are unprefixed hex; panda ids are 0x-prefixed hex.
                fid = int(cols[idcol].strip(), 16)
            except (ValueError, IndexError):
                unparsed += 1
                dst.write(line)
                continue
            if fid in strip:
                dropped += 1
            else:
                kept += 1
                dst.write(line)
        return kept, dropped, unparsed

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('paths', nargs='*', type=pathlib.Path)
    ap.add_argument('-o', '--out', type=pathlib.Path,
                    help='output root mirroring the input tree')
    ap.add_argument('--in-place', action='store_true',
                    help='overwrite input files instead of copying')
    ap.add_argument('--list', action='store_true', help='print strip set and exit')
    a = ap.parse_args()
    if a.list:
        for i in sorted(STRIP_IDS):
            print(f'0x{i:X}')
        return
    if not a.paths or (not a.out and not a.in_place):
        ap.error('need PATH(s) and exactly one of -o OUTDIR / --in-place')
    if a.out and a.in_place:
        ap.error('-o and --in-place are mutually exclusive')

    files = []
    roots = []
    for p in a.paths:
        if p.is_dir():
            roots.append(p)
            files.extend(sorted(p.rglob('*.csv')))
        elif p.suffix.lower() == '.csv':
            files.append(p)
        else:
            ap.error(f'{p}: not a csv or directory')

    base = roots[0] if roots else (a.out or files[0].parent)
    total_dropped = 0
    for src in files:
        if a.in_place:
            tmp = src.with_suffix('.csv.tmp')
            with open(tmp, 'w', newline='') as fo:
                kept, dropped, unparsed = strip_file(src, fo)
            tmp.replace(src)
        else:
            rel = src.relative_to(base) if any(
                src == r or r in src.parents for r in roots) else pathlib.Path(src.name)
            dst = a.out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, 'w', newline='') as fo:
                kept, dropped, unparsed = strip_file(src, fo)
        total_dropped += dropped
        flag = '' if dropped else '  (no match)'
        note = f' !! {unparsed} unparsed line(s)' if unparsed else ''
        print(f'{src}: kept={kept} dropped={dropped}{flag}{note}')
    print(f'TOTAL dropped frames: {total_dropped}')

if __name__ == '__main__':
    main()

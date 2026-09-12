#!/usr/bin/env python
"""
highlight_bits.py

Bit-level reverse engineering of CAN frames that are not in a DBC.  This is the
command line for the two tools ported from the panda examples in
``~/Packages/archive/animatronic_panda/examples/``; see ``panda_port.md`` for
the full write-up.

``observed``
    Compare a capture containing a stimulus against one or more background
    captures: report the bits that are set somewhere in the first capture and
    never set in any background, and the bits that are clear here and never
    clear there.  This is ``can_unique.py``.

``invariant``
    Compare two stretches of one log, one where a signal is known low and one
    where it is known high: report the bits that are clear in *every* sample of
    one window and set in *every* sample of the other.  The signal really must
    be constant across each window, so pick the windows from a video marker or
    a plot -- the original write-up suggests 10 seconds.  This is
    ``can_bit_transition.py``.

Both modes print one line per bit, with the frame id in hex, the bits named
rather than left as a bare mask, and the direction in words::

    id 0x820  byte 2  bit 1  mask 0x02  new one

Examples
--------
    python highlight_bits.py observed door.csv background-1.csv background-2.csv --bus 0
    python highlight_bits.py invariant drive.csv 50.0-65.0 69.0-79.0 --bus 0
    python highlight_bits.py invariant drive.csv 50.0-65.0 69.0-79.0 --id 0x1be
"""

import argparse
import os
import sys

import canlib


def _basename(path):
    return os.path.basename(path)


def _count(number, noun):
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _describe_bus(bus):
    return "every bus" if bus is None else f"bus {bus}"


def parse_range(text):
    """Parse a ``START-END`` seconds range, the form the originals took."""
    parts = text.split("-")
    if len(parts) != 2:
        raise SystemExit(f"expected a START-END range in seconds, got {text!r}")
    try:
        start, end = (float(part) for part in parts)
    except ValueError:
        raise SystemExit(f"expected a START-END range in seconds, got {text!r}") from None
    if start > end:
        raise SystemExit(f"range starts after it ends: {text!r}")
    return start, end


def load_log(path):
    """Load a log, turning the usual failures into a one-line message."""
    try:
        return canlib.load_log(path)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    modes = parser.add_subparsers(dest="mode", required=True,
                                  metavar="{observed,invariant}")

    observed = modes.add_parser(
        "observed",
        help="bits a capture shows that background captures never show")
    observed.add_argument("interesting",
                          help="the capture that contains the stimulus")
    observed.add_argument("background", nargs="+",
                          help="one or more background captures")

    invariant = modes.add_parser(
        "invariant",
        help="bits that are constant and opposite across two time windows")
    invariant.add_argument("log", help="the log both windows come from")
    invariant.add_argument("low", help="START-END seconds where the signal is low")
    invariant.add_argument("high", help="START-END seconds where the signal is high")
    invariant.add_argument("--id", action="append", default=[], metavar="ID",
                           help="only compare this frame id, in hex. Repeatable.")
    invariant.add_argument("--min-rows", type=int, default=1, metavar="N",
                           help="skip frames seen fewer than N times in a window "
                                "(default 1, which only skips frames absent from it)")

    for sub in (observed, invariant):
        sub.add_argument("--bus", type=int,
                         help="restrict to one bus (default: every bus)")
    return parser.parse_args(argv)


def run_observed(args):
    """The can_unique.py workflow: interesting capture vs background captures."""
    interesting = load_log(args.interesting)
    background = [load_log(path) for path in args.background]
    scan = canlib.bits_only_in(interesting, background, bus=args.bus)

    print(f"observed: {_basename(args.interesting)} vs "
          f"{_count(len(background), 'background log')}  [{_describe_bus(args.bus)}]")
    print(f"  {_count(len(scan), 'frame')} with differing bits, "
          f"{_count(len(scan.new_frames), 'frame id')} not in the background")
    print()
    print(scan)
    return 0


def run_invariant(args):
    """The can_bit_transition.py workflow: two windows of a single log."""
    log = load_log(args.log)
    low_window = parse_range(args.low)
    high_window = parse_range(args.high)
    wanted = {int(frame_id, 16) for frame_id in args.id} if args.id else None

    present = [frame_id for frame_id, indices in canlib.iter_frames(log, args.bus)
               if indices.size]
    if wanted is None:
        frame_ids = present
    else:
        frame_ids = sorted(wanted)
        for missing in sorted(wanted - set(present)):
            where = "" if args.bus is None else f" on bus {args.bus}"
            print(f"WARN: 0x{missing:X} is not in {_basename(args.log)}{where}",
                  file=sys.stderr)

    changes = {}
    compared = skipped = 0
    for frame_id in frame_ids:
        low = canlib.frame_bit_masks(log, frame_id, bus=args.bus,
                                     window=low_window, mode=canlib.INVARIANT)
        high = canlib.frame_bit_masks(log, frame_id, bus=args.bus,
                                      window=high_window, mode=canlib.INVARIANT)
        if low.count < args.min_rows or high.count < args.min_rows:
            skipped += 1
            continue
        compared += 1
        differing = canlib.bit_differences(high, low)
        if differing:
            changes[frame_id] = differing

    scan = canlib.BitScan(changes, mode=canlib.INVARIANT)
    print(f"invariant: {_basename(args.log)}  "
          f"low={low_window[0]:.3f}-{low_window[1]:.3f}s  "
          f"high={high_window[0]:.3f}-{high_window[1]:.3f}s  "
          f"[{_describe_bus(args.bus)}]")
    print(f"  {_count(compared, 'frame')} compared, {_count(len(scan), 'frame')} with "
          f"differing bits, {_count(skipped, 'frame')} skipped "
          f"(too few rows in a window)")
    print()
    print(scan)
    return 0


def main(argv=None):
    args = parse_args(argv)
    if args.mode == "observed":
        return run_observed(args)
    return run_invariant(args)


if __name__ == "__main__":
    sys.exit(main())

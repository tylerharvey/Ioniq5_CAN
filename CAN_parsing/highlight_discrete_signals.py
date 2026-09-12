#!/usr/bin/env python
"""
highlight_discrete_signals.py

Decode CAN logs using cantools DBC files and highlight *discrete* changes in
signals: signals that take a small set of distinct values and jump between them
at a handful of timestamps.  This is the signal-level analogue of the
whole-message "control signal" search the notebooks (parsing_*.ipynb) do with
payload ids.

Loading, frame indexing, the payload searches and the DBC decoding all live in
the ``canlib`` package next to this script; this file is the command line and
the report.

Two tiers are reported per log:

  * DBC signal tier   - for frames that exist in the DBC, each decoded signal
                        is checked for a small distinct-value count. Signals
                        that change between few states are printed with their
                        transition timestamps and (when available) VAL_ names.
  * muid fallback tier- frames *not* in the DBC are reported at whole-message
                        granularity (limited unique payloads).

This distinction isn't all that meaningful and will be de-emphasized.

The file title is used as metadata: a keyword->expected-frame map is consulted
and each log's report is annotated PASS/INFO based on whether the expected
frames actually show discrete changes.

Examples
--------
    python highlight_discrete_signals.py --dbc ~/Packages/egmpdbc/ioniq5-2022.dbc \
        --logs ../CAN_logs/
    python highlight_discrete_signals.py --logs ../CAN_logs/panda/M-CAN_nav_start_to_bank_0.5mi.csv
"""

import argparse
import glob
import json
import os
import sys

import canlib
from canlib import dbc as dbc_lib


DEFAULT_DBC = os.path.expanduser('~/Packages/egmpdbc/ioniq5-2022.dbc')
DEFAULT_LOGS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             '..', 'CAN_logs'))
DEFAULT_DBCS = [os.path.join(os.path.dirname(DEFAULT_DBC), f)
                for f in ('ioniq5-2022.dbc', 'ev6-2024.dbc', 'ioniq6-2023-2025.dbc')]


# ---------------------------------------------------------------------------
# Title -> metadata mapping used for verification
# ---------------------------------------------------------------------------
# keyword substring -> frames we EXPECT to show discrete changes (hex strings)
TITLE_EXPECTATIONS = {
    'preconditioning': ['0x2ad', '0x0c7', '0x4ed', '0x4cc', '0x4e8'],
    'preconditioned': ['0x2ad', '0x0c7', '0x4ed', '0x4cc', '0x4e8'],
    'no_preconditioning': ['0x4e8', '0x4ed'],          # 0x2ad should NOT go On
    'nav_start_to': ['0x4e8', '0x4ed'],
    'nav_to_school': ['0x4e8', '0x4ed'],
    'driving_with_nav': ['0x4e8', '0x4ed'],
    'climate_start': ['0x380', '0x4f1', '0x4a2', '0x4cc'],
    'climate_stop': ['0x380', '0x4f1', '0x4a2', '0x4cc'],
    'warmers': ['0x380', '0x4f1', '0x4a2'],
    'remote_lock': ['0x411', '0x405'],
    'remote_unlock': ['0x411', '0x405'],
    'car_in_d': ['0x38', '0x31b'],
    'car_in_ready': ['0x38', '0x31b'],
    'nothing_happening': [],          # expect no discrete changes
    'nothing_on': [],                 # expect no discrete changes
    'already_preconditioning': ['0x4cc', '0x4e8'],     # state stays On; no toggle
    'gv60': ['0xa82aa03'],  # GV60: extended BMS_Precond id (replaces standard ids)
    'head_unit_only': [],             # depends on the rest of the title
}


def title_keywords(filename):
    """Return list of keyword groups present in a log's file title.

    Longer/more-specific keywords are matched first so that, e.g.,
    'no_preconditioning' is not also matched by the substring 'preconditioning'.
    """
    base = os.path.basename(filename).lower().replace('_cleaned', '').replace('.csv', '')
    hits = []
    for kw in sorted(TITLE_EXPECTATIONS, key=len, reverse=True):
        if kw in base:
            hits.append(kw)
            if kw.startswith('no_'):
                base = base.replace(kw, '')
    return hits


# ---------------------------------------------------------------------------
# Log loading
# ---------------------------------------------------------------------------
def load_log(path, clean=False):
    """Load a log with canlib, optionally dropping the pre-reset fragment.

    `--clean-timestamps` is off by default because these logs restart their
    capture mid-file, and truncating at the first reset loses whatever the
    event of interest was in that first segment.
    """
    log = canlib.load_log(path)
    if not clean:
        return log
    drops, jumps = canlib.timestamp_discontinuities(log)
    print(f"Identified {drops} drops in timestamp and {jumps} total timestamp jumps.")
    truncated, _dropped = log.after_timestamp_reset()
    return truncated


# ---------------------------------------------------------------------------
# Muid fallback tier (frames not in the DBC)
# ---------------------------------------------------------------------------
def analyze_log_muid_fallback(log, threshold, exclude_ids=()):
    """Frames with a limited set of distinct payloads that are not in the DBC."""
    fallback = []
    for frame_id, n_unique in canlib.limited_unique_frames(log, threshold):
        if frame_id in exclude_ids:
            continue  # already reported at signal level
        timestamps, payloads = canlib.frame_series(log, frame_id)
        _, change_times, _, _ = canlib.value_transitions(
            timestamps, canlib.pack_muids(payloads))
        fallback.append({
            'frame_id': int(frame_id),
            'n_unique_payloads': int(n_unique),
            'change_times_s': [float(t) for t in change_times],
        })
    return fallback


# ---------------------------------------------------------------------------
# Reporting + verification
# ---------------------------------------------------------------------------
def format_report(log_path, db_path, dbc_results, muid_results, title_hits):
    lines = []
    lines.append("=" * 78)
    lines.append(f"LOG: {os.path.basename(log_path)}")
    lines.append(f"  dbc : {os.path.basename(db_path)}")
    kw = ' | '.join(title_hits) if title_hits else '(none matched)'
    lines.append(f"  title metadata keywords: {kw}")
    lines.append("=" * 78)

    if dbc_results:
        lines.append("\nDBC signal-level discrete changes (decoded via cantools):")
        for res in dbc_results:
            lines.append(f"\n  * 0x{res['frame_id']:03X} {res['frame_name']}")
            for sig in res['signals']:
                lines.append(f"      {sig['signal']}  [{sig['n_distinct']} distinct "
                             f"{sig['values']}; {sig['n_changes']} change(s)]")
                for tr in sig['transitions'][:12]:
                    lines.append(f"          t={tr['time_s']:10.2f}s  {tr['from']} -> {tr['to']}")
                if len(sig['transitions']) > 12:
                    lines.append(f"          ... +{len(sig['transitions']) - 12} more")
    else:
        lines.append("\n  (no DBC-decoded signals with discrete changes)")

    if muid_results:
        lines.append("\nmuid fallback frames (limited distinct payloads, not in DBC):")
        for fr in muid_results:
            times = ", ".join(f"{t:.1f}s" for t in fr['change_times_s'][:8])
            if len(fr['change_times_s']) > 8:
                times += ", ..."
            lines.append(f"  * 0x{fr['frame_id']:03X}  {fr['n_unique_payloads']} payload(s)  "
                         f"changes at: {times}")
    else:
        lines.append("\n  (no muid-fallback frames)")

    return "\n".join(lines)


def verify_log(log_path, dbc_results, muid_results):
    """Return list of (frame_hex, ok_bool, note) using title as metadata."""
    keywords = title_keywords(log_path)
    expected = set()
    for kw in keywords:
        expected.update(TITLE_EXPECTATIONS[kw])
    if 'gv60' in keywords:
        # GV60 logs carry the extended BMS_Precond id (0x0A82AA03); the
        # standard M-CAN preconditioning ids are not present on that platform.
        expected = set(TITLE_EXPECTATIONS['gv60'])
    if not expected:
        return [], 'no metadata match'
    # compare by numeric id, not zero-padded hex strings, so 0x38 == 0x038
    seen_ids = {int(res['frame_id']) for res in dbc_results}
    seen_ids.update(int(fr['frame_id']) for fr in muid_results)

    checks = []
    for exp in sorted(expected, key=lambda s: int(s, 16)):
        ok = int(exp, 16) in seen_ids
        note = 'found' if ok else 'MISSING'
        if exp in ('0x2ad', '0x4ed', '0x4cc') and not ok and any(kw == 'no_preconditioning'
                                                                 for kw in keywords):
            ok, note = True, 'expected ABSENT (no preconditioning)'
        checks.append((exp, ok, note))
    return checks, 'verified'


def print_metadata(checks, state):
    print(f"\n  METADATA {state.upper()}:")
    for exp, ok, note in checks:
        mark = 'OK ' if ok else '!! '
        print(f"    [{mark}] expected {exp}: {note}")


def print_summary(summary):
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    for entry in summary:
        meta = ",".join(f"{c['frame']}:{'OK' if c['ok'] else 'X'}"
                        for c in entry['metadata_checks'])
        print(f"  {entry['file']:<70} disc={entry['n_discrete_signals']:<3} "
              f"muid={entry['n_muid_frames']:<3} {meta}")


# ---------------------------------------------------------------------------
# Optional interactive output
# ---------------------------------------------------------------------------
def plot_results(log, frame_ids):
    """Plot each frame's payload state, normalised, against time."""
    import matplotlib.pyplot as plt

    for i, frame_id in enumerate(frame_ids):
        indices = canlib.frame_indices(log, frame_id)
        if len(indices):
            norm_vals = log.muids[indices].astype(float)
            if norm_vals.min() != norm_vals.max():
                norm_vals -= norm_vals.min()
            norm_vals += 1e-6
            norm_vals /= norm_vals.max()
            norm_vals *= 1+(0.05*frame_id/1000)
            plt.plot(log.time_s[indices], norm_vals, label=f'frame {hex(frame_id)}',
                     alpha=0.5, marker='.', linestyle=None)
        if i % 5 == 4:
            plt.xlabel('Timestamp (s)')
            plt.legend()
            plt.show()

    plt.xlabel('Timestamp (s)')
    plt.legend()
    plt.show()


def print_frame_series(log, frame_id):
    """Print every payload of one frame id with the gap to the previous one."""
    times, payloads = canlib.frame_series(log, frame_id, hex=True)
    for index in range(times.size):
        last_timestamp = times[index-1] if index else times[0]
        print(f"Message: {payloads[index]}; "
              f"Time Spacing: {times[index]-last_timestamp:.6f}s")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def collect_logs(paths):
    files = []
    for p in paths:
        if os.path.isfile(p):
            files.append(p)
        elif os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, '**', '*.csv'), recursive=True)))
        else:
            print(f"WARN: not a file or dir: {p}", file=sys.stderr)
    # de-dup
    return sorted(set(os.path.abspath(f) for f in files))


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dbc', action='append', default=[], metavar='DBC',
                    help='DBC file(s) to decode with. Repeatable. '
                         'Defaults to all E-GMP dbc files under ~/Packages/egmpdbc/.')
    ap.add_argument('--logs', nargs='+', default=[DEFAULT_LOGS],
                    help='Log files or directories (default ../CAN_logs).')
    ap.add_argument('--threshold', type=int, default=10,
                    help='Max distinct values for a signal to count as discrete (default 10).')
    ap.add_argument('--min-changes', type=int, default=1,
                    help='Min transitions for a signal to be reported (default 1).')
    ap.add_argument('--clean-timestamps', action='store_true',
                    help='Truncate logs at a timestamp reset (SavvyCAN restart). '
                         'Off by default so mid-log events are not lost.')
    ap.add_argument('--json', dest='json_out', metavar='FILE',
                    help='Also dump machine-readable results to FILE.')
    ap.add_argument('--plot', action='store_true', help='Enable plotting of all signal differences.')
    ap.add_argument('--id', type=str, help='Select a frame ID to output all messages for.')
    return ap.parse_args(argv)


def dbc_label(dbc_paths):
    """Name of the first DBC file, as shown in the report header."""
    return os.path.basename(dbc_paths[0]) if dbc_paths else 'merged'


def analyze_log(log, path, db, args, db_label, excluded_ids):
    """Report one log and return its ``(dbc_results, muid_results, summary, json)``."""
    dbc_results = dbc_lib.discrete_signals_for_log(log, db, args.threshold, args.min_changes)
    muid_results = analyze_log_muid_fallback(log, args.threshold, excluded_ids)
    checks, state = verify_log(path, dbc_results, muid_results)

    print(format_report(path, db_label, dbc_results, muid_results, title_keywords(path)))
    if checks:
        print_metadata(checks, state)
    print()

    metadata = [{'frame': c[0], 'ok': c[1], 'note': c[2]} for c in checks]
    summary = {
        'file': os.path.basename(path),
        'format': log.fmt,
        'n_discrete_signals': sum(len(r['signals']) for r in dbc_results),
        'n_muid_frames': len(muid_results),
        'metadata_checks': metadata,
    }
    record = {
        'file': path,
        'format': log.fmt,
        'dbc': db_label,
        'dbc_signal_results': dbc_results,
        'muid_fallback': muid_results,
        'metadata': metadata,
    }
    return dbc_results, muid_results, summary, record


def main(argv=None):
    args = parse_args(argv)

    dbc_paths = args.dbc if args.dbc else DEFAULT_DBCS
    db = dbc_lib.load_dbc(dbc_paths)
    if db is None:
        print("ERROR: no usable DBC.", file=sys.stderr)
        return 1

    logs = collect_logs(args.logs)
    if not logs:
        print("ERROR: no log files found.", file=sys.stderr)
        return 1

    db_label = dbc_label(dbc_paths)
    excluded_ids = dbc_lib.frame_ids(db)
    summary = []
    records = []
    for path in logs:
        try:
            log = load_log(path, clean=args.clean_timestamps)
        except Exception as e:
            print(f"WARN: skipping {path}: {e}", file=sys.stderr)
            continue
        dbc_results, muid_results, entry, record = analyze_log(
            log, path, db, args, db_label, excluded_ids)
        summary.append(entry)
        records.append(record)

        if args.plot:
            plot_results(log, [r['frame_id'] for r in dbc_results]
                              + [f['frame_id'] for f in muid_results])

        if args.id:
            print_frame_series(log, int(args.id, 16))

    print_summary(summary)

    if args.json_out:
        with open(args.json_out, 'w') as fh:
            json.dump(records, fh, indent=2)
        print(f"\nWrote JSON results to {args.json_out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

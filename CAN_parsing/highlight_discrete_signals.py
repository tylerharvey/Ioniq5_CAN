#!/usr/bin/env python
"""
highlight_discrete_signals.py

Decode CAN logs using cantools DBC files (via parsing_lib for loading) and
highlight *discrete* changes in signals: signals that take a small set of
distinct values and jump between them at a handful of timestamps. This is the
signal-level analogue of the whole-message "control signal" search that the
notebooks (parsing_*.ipynb) do with messages_unique_ids.

Two tiers are reported per log:

  * DBC signal tier   - for frames that exist in the DBC, each decoded signal
                        is checked for a small distinct-value count. Signals
                        that change between few states are printed with their
                        transition timestamps and (when available) VAL_ names.
  * muid fallback tier- frames *not* in the DBC are reported at whole-message
                        granularity via parsing_lib (limited unique payloads).

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
import contextlib
import glob
import io
import json
import os
import re
import sys

import numpy as np

import cantools
from parsing_lib import (populate_dict, populate_dict_panda,
                         calculate_unique_message_id, clean_bad_timestamps,
                         return_frame_series, return_value_transitions,
                         return_frame_IDs_with_limited_message_changes)

DEFAULT_DBC = os.path.expanduser('~/Packages/egmpdbc/ioniq5-2022.dbc')
DEFAULT_LOGS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             '..', 'CAN_logs'))
DEFAULT_DBCS = [os.path.join(os.path.dirname(DEFAULT_DBC), f)
                for f in ('ioniq5-2022.dbc', 'ev6-2024.dbc', 'ioniq6-2023-2025.dbc')]


# ---------------------------------------------------------------------------
# DBC loading (robust to cantools VFrameFormat bug on extended IDs)
# ---------------------------------------------------------------------------
def _extract_message_blocks(text):
    """Yield (frame_id, block_lines) for each BO_ block in stripped DBC text.

    A block runs from a `BO_ <id>` line through any following SG_ lines until
    the next top-level keyword. Original byte order is preserved verbatim.
    VAL_ lines are handled separately (see `_extract_val_tables`): in these
    DBCs they live in a trailing section rather than inside the BO_ block.
    """
    block = None
    block_id = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('BO_ '):
            if block is not None:
                yield block_id, block
            parts = line.split()
            block_id = int(parts[1])
            block = [raw]
        elif block is not None and line.startswith('SG_'):
            block.append(raw)
        elif block is not None:
            yield block_id, block
            block = None
    if block is not None:
        yield block_id, block


def _extract_val_tables(text):
    """Group VAL_ value-table lines by the message id they define."""
    tables = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith('VAL_ '):
            continue
        parts = line.split()
        try:
            fid = int(parts[1])
        except (IndexError, ValueError):
            continue
        tables.setdefault(fid, []).append(raw)
    return tables


def load_dbc(dbc_paths):
    """Load and merge one or more DBC files.

    cantools fails on `BA_ "VFrameFormat" BO_ <id> 1;` lines (extended-ID
    messages). The extended bit is already encoded in the frame id (bit
    0x80000000), so those attribute lines are stripped before parsing.
    The first DBC that defines a frame wins; later files only fill gaps.
    """
    merged = cantools.database.can.database.Database()
    seen = set()
    loaded = 0
    for path in dbc_paths:
        try:
            with open(path, 'r', errors='replace') as fh:
                text = fh.read()
        except OSError as e:
            print(f"WARN: cannot read DBC {path}: {e}", file=sys.stderr)
            continue
        lines = [ln for ln in text.splitlines() if 'VFrameFormat' not in ln]
        stripped = '\n'.join(lines)
        # sanity check the file parses standalone before merging
        try:
            cantools.database.load_string(stripped)
        except Exception as e:
            print(f"WARN: could not parse DBC {path}: {e}", file=sys.stderr)
            continue
        val_tables = _extract_val_tables(stripped)
        for fid, block in _extract_message_blocks(stripped):
            if fid in seen:
                continue
            seen.add(fid)
            # VAL_ lines define signal value names; without them choices are
            # lost (the raw text would attach them to the wrong BO_ block).
            block = list(block) + val_tables.get(fid, [])
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    merged.add_dbc_string('\n'.join(block))
            except Exception as e:
                print(f"WARN: skip {hex(fid)} in {path}: {e}", file=sys.stderr)
        loaded += 1
        print(f"Loaded DBC: {path}")
    return merged if loaded else None


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
def sniff_format(path):
    """Return 'panda' or 'savvycan' based on the CSV header."""
    with open(path, 'r') as fh:
        header = fh.readline()
    if header.lower().startswith('bus'):
        return 'panda'
    if header.lower().startswith('time stamp'):
        return 'savvycan'
    raise ValueError(f"Unrecognized log header in {path}: {header!r}")


def load_log(path, clean=False):
    """Load a log via parsing_lib, auto-detecting the format."""
    fmt = sniff_format(path)
    d = {}
    if fmt == 'panda':
        populate_dict_panda(d, path)
    else:
        populate_dict(d, path)
    if clean and d['timestamps'].dtype.kind in 'iu':
        clean_bad_timestamps(d)
    calculate_unique_message_id(d)
    d['_format'] = fmt
    return d


def timestamps_to_seconds(ts, fmt):
    """SavvyCAN ints are microseconds, panda floats are seconds."""
    if fmt == 'savvycan' and ts.dtype.kind in 'iu':
        return ts.astype(float) / 1e6
    return ts.astype(float)


# ---------------------------------------------------------------------------
# DBC signal-level discrete change detection
# ---------------------------------------------------------------------------
def is_excluded_frame(db, frame_id):
    try:
        msg = db.get_message_by_frame_id(frame_id)
    except KeyError:
        return False
    return msg.name.startswith('ISOTP') or msg.name.startswith('VIN')


def signal_display_name(signal, value):
    """Return value as a string, using VAL_ names when available."""
    if signal.choices:
        try:
            raw = int(value)
        except (TypeError, ValueError):
            return str(value)
        if raw in signal.choices:
            return f"{signal.choices[raw]} ({raw})"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def analyze_frame_signals(d, frame_id, db, threshold, min_changes):
    """Return list of (signal_name, n_distinct, transitions) for a DBC frame."""
    ts_raw, msgs = return_frame_series(d, frame_id)
    if len(msgs) == 0:
        return []
    ts = timestamps_to_seconds(ts_raw, d['_format'])
    msg = db.get_message_by_frame_id(frame_id)
    report = []
    for signal in msg.signals:
        values = []
        ok = True
        for m in msgs:
            try:
                dec = db.decode_message(frame_id, m.astype(np.uint8).tobytes(),
                                        decode_choices=False)
                values.append(dec[signal.name])
            except Exception:
                ok = False
                break
        if not ok or len(values) != len(ts):
            continue
        values = np.asarray(values)
        distinct = np.unique(values)
        if not (1 < len(distinct) <= threshold):
            continue
        indices, change_ts, from_v, to_v = return_value_transitions(ts, values)
        if len(indices) < min_changes:
            continue
        transitions = []
        for t, f, t_ in zip(change_ts, from_v, to_v):
            transitions.append({
                'time_s': float(t),
                'from': signal_display_name(signal, f),
                'to': signal_display_name(signal, t_),
            })
        report.append({
            'signal': signal.name,
            'n_distinct': int(len(distinct)),
            'values': [signal_display_name(signal, v) for v in distinct],
            'n_changes': int(len(indices)),
            'transitions': transitions,
        })
    return report


def analyze_log_dbc(d, db, threshold, min_changes):
    """Iterate DBC frames present in the log and return discrete signals."""
    results = []
    for frame_id in np.unique(d['ids']):
        frame_id = int(frame_id)
        try:
            msg = db.get_message_by_frame_id(frame_id)
        except KeyError:
            continue
        if is_excluded_frame(db, frame_id):
            continue
        signals = analyze_frame_signals(d, frame_id, db, threshold, min_changes)
        if signals:
            results.append({'frame_id': frame_id, 'frame_name': msg.name, 'signals': signals})
    return results


# ---------------------------------------------------------------------------
# Muid fallback tier (frames not in the DBC)
# ---------------------------------------------------------------------------
def analyze_log_muid_fallback(d, threshold, db=None):
    """Frames with a limited set of distinct payloads, using parsing_lib."""
    frames = return_frame_IDs_with_limited_message_changes(d, threshold)
    out = []
    for frame_id, n_unique in frames:
        if db is not None:
            try:
                db.get_message_by_frame_id(int(frame_id))
                continue  # handled at signal level
            except KeyError:
                pass
        indices = np.argwhere(d['ids'] == frame_id)[:,0]
        ts_raw = d['timestamps'][indices]
        ts = timestamps_to_seconds(ts_raw, d['_format'])
        order = np.argsort(ts, kind='stable')
        ts, muids = ts[order], d['messages_unique_ids'][indices][order]
        _, change_ts, _, _ = return_value_transitions(ts, muids)
        out.append({
            'frame_id': frame_id,
            'n_unique_payloads': n_unique,
            'change_times_s': [float(t) for t in change_ts],
        })
    return out


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
    seen_ids = set()
    for res in dbc_results:
        seen_ids.add(int(res['frame_id']))
    for fr in muid_results:
        seen_ids.add(int(fr['frame_id']))

    checks = []
    for exp in sorted(expected, key=lambda s: int(s, 16)):
        ok = int(exp, 16) in seen_ids
        note = 'found' if ok else 'MISSING'
        if exp in ('0x2ad', '0x4ed', '0x4cc') and not ok and any(kw == 'no_preconditioning'
                                                                 for kw in keywords):
            ok, note = True, 'expected ABSENT (no preconditioning)'
        checks.append((exp, ok, note))
    return checks, 'verified'


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


def main(argv=None):
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
    args = ap.parse_args(argv)

    dbc_paths = args.dbc if args.dbc else DEFAULT_DBCS
    db = load_dbc(dbc_paths)
    if db is None:
        print("ERROR: no usable DBC.", file=sys.stderr)
        return 1

    dbc_label = os.path.basename(dbc_paths[0]) if dbc_paths else 'merged'
    logs = collect_logs(args.logs)
    if not logs:
        print("ERROR: no log files found.", file=sys.stderr)
        return 1

    all_json = []
    summary = []
    for lp in logs:
        try:
            d = load_log(lp, clean=args.clean_timestamps)
        except Exception as e:
            print(f"WARN: skipping {lp}: {e}", file=sys.stderr)
            continue
        dbc_results = analyze_log_dbc(d, db, args.threshold, args.min_changes)
        muid_results = analyze_log_muid_fallback(d, args.threshold, db=db)
        keywords = title_keywords(lp)
        checks, state = verify_log(lp, dbc_results, muid_results)

        print(format_report(lp, dbc_label, dbc_results, muid_results, keywords))

        if checks:
            print(f"\n  METADATA {state.upper()}:")
            for exp, ok, note in checks:
                mark = 'OK ' if ok else '!! '
                print(f"    [{mark}] expected {exp}: {note}")
        print()

        # one-line summary for easy verification
        n_sig = sum(len(r['signals']) for r in dbc_results)
        summary.append({
            'file': os.path.basename(lp),
            'format': d['_format'],
            'n_discrete_signals': n_sig,
            'n_muid_frames': len(muid_results),
            'metadata_checks': [{'frame': c[0], 'ok': c[1], 'note': c[2]} for c in checks],
        })
        all_json.append({
            'file': lp,
            'format': d['_format'],
            'dbc': dbc_label,
            'dbc_signal_results': dbc_results,
            'muid_fallback': muid_results,
            'metadata': [{'frame': c[0], 'ok': c[1], 'note': c[2]} for c in checks],
        })

    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    for s in summary:
        meta = ",".join(f"{c['frame']}:{'OK' if c['ok'] else 'X'}" for c in s['metadata_checks'])
        print(f"  {s['file']:<70} disc={s['n_discrete_signals']:<3} "
              f"muid={s['n_muid_frames']:<3} {meta}")

    if args.json_out:
        with open(args.json_out, 'w') as fh:
            json.dump(all_json, fh, indent=2)
        print(f"\nWrote JSON results to {args.json_out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

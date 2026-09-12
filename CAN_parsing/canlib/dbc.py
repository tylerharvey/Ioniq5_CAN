"""Decode frames with cantools DBC files and report discrete signals.

A *discrete* signal is one that takes a small set of distinct values and jumps
between them at a handful of timestamps -- the signal-level analogue of the
whole-payload search in :mod:`canlib.discrete`.

cantools is imported by this module rather than by ``canlib/__init__`` so that
``import canlib`` only needs numpy; import :mod:`canlib.dbc` explicitly when
you want DBC decoding.
"""

from __future__ import annotations

import contextlib
import io
import sys

import numpy as np

import cantools

from .frames import frame_series, value_transitions
from .log import CanLog

__all__ = [
    "load_dbc",
    "frame_ids",
    "is_excluded_frame",
    "signal_display_name",
    "decode_signal_transitions",
    "discrete_signals_for_log",
]

# Protocol / broadcast frames, not control signals.
_EXCLUDED_PREFIXES = ("ISOTP", "VIN")


def _extract_message_blocks(text):
    """Yield ``(frame_id, block_lines)`` for each ``BO_`` block in DBC text.

    A block runs from a ``BO_ <id>`` line through any following ``SG_`` lines
    until the next top-level keyword.  Original byte order is preserved
    verbatim.  ``VAL_`` lines are handled separately (see
    :func:`_extract_val_tables`): in these DBCs they live in a trailing
    section rather than inside the ``BO_`` block.
    """
    block = None
    block_id = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("BO_ "):
            if block is not None:
                yield block_id, block
            parts = line.split()
            block_id = int(parts[1])
            block = [raw]
        elif block is not None and line.startswith("SG_"):
            block.append(raw)
        elif block is not None:
            yield block_id, block
            block = None
    if block is not None:
        yield block_id, block


def _extract_val_tables(text):
    """Group ``VAL_`` value-table lines by the message id they define."""
    tables = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("VAL_ "):
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

    cantools fails on ``BA_ "VFrameFormat" BO_ <id> 1;`` lines (extended-ID
    messages).  The extended bit is already encoded in the frame id (bit
    0x80000000), so those attribute lines are stripped before parsing.  The
    first DBC that defines a frame wins; later files only fill gaps.

    Returns ``None`` when no file could be read.
    """
    merged = cantools.database.can.database.Database()
    seen = set()
    loaded = 0
    for path in dbc_paths:
        try:
            with open(path, "r", errors="replace") as handle:
                text = handle.read()
        except OSError as exc:
            print(f"WARN: cannot read DBC {path}: {exc}", file=sys.stderr)
            continue
        stripped = "\n".join(
            line for line in text.splitlines() if "VFrameFormat" not in line
        )
        # Sanity check that the file parses standalone before merging.
        try:
            cantools.database.load_string(stripped)
        except Exception as exc:
            print(f"WARN: could not parse DBC {path}: {exc}", file=sys.stderr)
            continue
        val_tables = _extract_val_tables(stripped)
        for fid, block in _extract_message_blocks(stripped):
            if fid in seen:
                continue
            seen.add(fid)
            # VAL_ lines define signal value names; without them the choices
            # are lost, because the raw text would attach them to the wrong
            # BO_ block.
            block = list(block) + val_tables.get(fid, [])
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    merged.add_dbc_string("\n".join(block))
            except Exception as exc:
                print(f"WARN: skip {hex(fid)} in {path}: {exc}", file=sys.stderr)
        loaded += 1
        print(f"Loaded DBC: {path}")
    return merged if loaded else None


def frame_ids(db) -> set[int]:
    """Every frame id a DBC database defines."""
    return {int(message.frame_id) for message in db.messages}


def is_excluded_frame(message) -> bool:
    """True for protocol/broadcast frames that are not control signals."""
    return message.name.startswith(_EXCLUDED_PREFIXES)


def signal_display_name(signal, value) -> str:
    """Render a decoded value, using its ``VAL_`` name when one exists."""
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


def decode_signal_transitions(
    log: CanLog, frame_id: int, db, threshold: int, min_changes: int
) -> list[dict]:
    """Discrete signals of one DBC frame, as plain dicts.

    Each message is decoded once.  A signal is skipped when it is absent from
    any decoded sample -- cantools omits the inactive branches of a multiplexed
    signal -- or when the message fails to decode at all, which skips every
    signal of that frame.  A frame that `db` does not define, or that the log
    does not contain, yields no signals.
    """
    try:
        message = db.get_message_by_frame_id(frame_id)
    except KeyError:
        return []
    timestamps, payloads = frame_series(log, frame_id)
    if payloads.shape[0] == 0:
        return []
    decoded = []
    for payload in payloads:
        try:
            decoded.append(
                db.decode_message(
                    frame_id, payload.astype(np.uint8).tobytes(), decode_choices=False
                )
            )
        except Exception:
            return []
    report = []
    for signal in message.signals:
        if any(signal.name not in sample for sample in decoded):
            continue
        values = np.asarray([sample[signal.name] for sample in decoded])
        distinct = np.unique(values)
        if not (1 < distinct.size <= threshold):
            continue
        indices, change_times, from_values, to_values = value_transitions(
            timestamps, values
        )
        if indices.size < min_changes:
            continue
        report.append(
            {
                "signal": signal.name,
                "n_distinct": int(distinct.size),
                "values": [signal_display_name(signal, value) for value in distinct],
                "n_changes": int(indices.size),
                "transitions": [
                    {
                        "time_s": float(time),
                        "from": signal_display_name(signal, before),
                        "to": signal_display_name(signal, after),
                    }
                    for time, before, after in zip(change_times, from_values, to_values)
                ],
            }
        )
    return report


def discrete_signals_for_log(
    log: CanLog, db, threshold: int, min_changes: int
) -> list[dict]:
    """Discrete signals for every DBC frame present in `log`.

    Returns ``[{'frame_id', 'frame_name', 'signals'}]``, each frame appearing
    once, in ascending frame-id order.
    """
    results = []
    for frame_id in np.unique(log.ids):
        frame_id = int(frame_id)
        try:
            message = db.get_message_by_frame_id(frame_id)
        except KeyError:
            continue
        if is_excluded_frame(message):
            continue
        signals = decode_signal_transitions(log, frame_id, db, threshold, min_changes)
        if signals:
            results.append(
                {"frame_id": frame_id, "frame_name": message.name, "signals": signals}
            )
    return results

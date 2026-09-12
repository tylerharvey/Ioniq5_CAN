"""Whole-payload state analysis: which frames look like control signals.

A frame that adopts a payload state only while some stimulus is active is
evidence that it reacts to that stimulus.  These helpers turn a stimulus's
timestamps into bursts, then look for frames whose states are confined to those
bursts.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from .encoding import pack_muids
from .frames import frame_series, unique_payload_counts
from .log import CanLog

__all__ = [
    "cluster_times",
    "payloads_only_in_windows",
    "frames_with_window_only_payloads",
]


def cluster_times(times, gap) -> list[tuple]:
    """Split event timestamps into bursts.

    Events separated by more than `gap` from the previous event start a new
    burst; `gap` is in the same unit as `times`.  Returns the first and last
    timestamp of each burst, which is the natural input for
    :func:`payloads_only_in_windows` -- for example the repeated transmissions
    of an injected frame become the "active" windows of that frame.

    The input dtype is preserved, so integer microsecond timestamps stay
    integers and float seconds stay floats.
    """
    ordered = np.sort(np.asarray(times).ravel())
    if ordered.size == 0:
        return []
    clusters = []
    start = previous = ordered[0]
    for current in ordered[1:]:
        if current - previous > gap:
            clusters.append((start.item(), previous.item()))
            start = current
        previous = current
    clusters.append((start.item(), previous.item()))
    return clusters


def payloads_only_in_windows(
    log: CanLog,
    frame_id: int,
    windows: Sequence[tuple[float, float]],
    bus: Optional[int] = None,
) -> np.ndarray:
    """Payload states of `frame_id` seen inside `windows` but nowhere else.

    `windows` is a sequence of ``(start, end)`` pairs in **seconds**; pair it
    with ``cluster_times(log.time_s, gap_seconds)``.  A state a control frame
    adopts only while a stimulus is active shows up here, while states that
    also occur in normal traffic are excluded.  Returns an empty array when the
    frame is absent or never confined to the windows.

    Caveats: a one-off transition that happens to fall inside a window is also
    reported, and a state held between repeated bursts is excluded unless the
    windows span the whole time it is held.
    """
    times, payloads = frame_series(log, frame_id, bus=bus)
    if times.size == 0:
        return np.array([], dtype=np.uint64)
    muids = pack_muids(payloads)
    inside = np.zeros(times.shape, dtype=bool)
    for start, end in windows:
        inside |= (times >= start) & (times <= end)
    confined = [
        muid
        for muid in np.unique(muids)
        if np.any((muids == muid) & inside) and not np.any((muids == muid) & ~inside)
    ]
    return np.array(confined, dtype=np.uint64)


def frames_with_window_only_payloads(
    log: CanLog,
    windows: Sequence[tuple[float, float]],
    threshold: int = 10,
    bus: Optional[int] = None,
) -> list[tuple[int, int, int]]:
    """Frames that adopt a payload state only inside `windows`.

    Frames are restricted to `threshold` distinct payloads so sensor-like
    frames are skipped.  Returns ``(frame_id, n_window_only_payloads,
    n_distinct_payloads)`` triples; see :func:`payloads_only_in_windows` for
    the caveats about one-off transitions inside a window.
    """
    results = []
    for frame_id, _indices, count in unique_payload_counts(log, bus):
        if not (1 < count <= threshold):
            continue
        confined = payloads_only_in_windows(log, frame_id, windows, bus=bus)
        if confined.size:
            results.append((frame_id, int(confined.size), count))
    return results

"""Whole-payload state analysis: which frames look like control signals.

A frame that adopts a payload state only while some stimulus is active is
evidence that it reacts to that stimulus.  These helpers turn a frame's
emissions into bursts, then look for frames whose states are confined to those
bursts.

:func:`payload_bursts` is the window generator to use when the stimulus is a
CAN frame: it splits on a payload change as well as on silence, so two
different commands sent back to back stay in separate windows.
"""

from __future__ import annotations

from typing import NamedTuple, Optional, Sequence

import numpy as np

from .encoding import pack_muids
from .frames import frame_series, unique_payload_counts
from .log import CanLog

__all__ = [
    "Burst",
    "cluster_times",
    "payload_bursts",
    "payloads_only_in_windows",
    "frames_with_window_only_payloads",
]


class Burst(NamedTuple):
    """A run of identical payloads from one frame.

    ``payload`` is a tuple of the eight byte values rather than a numpy array,
    so bursts compare and hash by value; ``np.array(burst.payload)`` gets the
    array row back.  ``start_s`` and ``end_s`` bound the first and last message
    of the run and are in seconds.
    """

    muid: int
    payload: tuple[int, ...]
    start_s: float
    end_s: float
    count: int


def cluster_times(times, gap) -> list[tuple]:
    """Split event timestamps into bursts.

    Events separated by more than `gap` from the previous event start a new
    burst; `gap` is in the same unit as `times`.  Returns the first and last
    timestamp of each burst.

    Use this when all you have is a list of timestamps.  When the events come
    from a CAN frame, prefer :func:`payload_bursts`, which also splits when the
    payload changes and so keeps distinct commands apart.

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


def _make_burst(times, payloads, muids, first: int, last: int) -> Burst:
    return Burst(
        muid=int(muids[first]),
        payload=tuple(int(value) for value in payloads[first]),
        start_s=float(times[first]),
        end_s=float(times[last]),
        count=last - first + 1,
    )


def payload_bursts(
    log: CanLog,
    frame_id: int,
    gap: float,
    bus: Optional[int] = None,
) -> list[Burst]:
    """Group one frame's messages into runs of identical payload.

    A new burst starts when the payload changes or when the frame goes quiet
    for more than `gap` seconds.  `gap`, ``start_s`` and ``end_s`` are all in
    seconds.  Returns the bursts in chronological order; an absent frame gives
    an empty list.

    This is the window generator to pair with
    :func:`payloads_only_in_windows`, which wants
    ``[(burst.start_s, burst.end_s) for burst in payload_bursts(...)]``.  It
    differs from :func:`cluster_times` in the one way that matters for that
    job: an injected 0x0C7 ENABLE immediately followed by a 0x0C7 hold is two
    windows here and one window there, so a car-side state can be attributed
    to the ENABLE rather than to "0x0C7 was doing something".
    """
    times, payloads = frame_series(log, frame_id, bus=bus)
    if times.size == 0:
        return []
    muids = pack_muids(payloads)
    bursts = []
    first = 0
    for index in range(1, times.size):
        if times[index] - times[index - 1] > gap or muids[index] != muids[index - 1]:
            bursts.append(_make_burst(times, payloads, muids, first, index - 1))
            first = index
    bursts.append(_make_burst(times, payloads, muids, first, times.size - 1))
    return bursts


def payloads_only_in_windows(
    log: CanLog,
    frame_id: int,
    windows: Sequence[tuple[float, float]],
    bus: Optional[int] = None,
    min_hits: int = 1,
) -> np.ndarray:
    """Payload states of `frame_id` seen inside `windows` but nowhere else.

    `windows` is a sequence of ``(start, end)`` pairs in **seconds**.  Build
    them with :func:`payload_bursts` when the stimulus is a CAN frame, or with
    :func:`cluster_times` when you only have bare timestamps.  A state a
    control frame adopts only while a stimulus is active shows up here, while
    states that also occur in normal traffic are excluded.  Returns an empty
    array when the frame is absent or never confined to the windows.

    A state must be seen at least `min_hits` times inside the windows.  The
    default of 1 still reports a one-off transition that merely happened to
    land inside a window; raise it to require the state to be sustained.

    Caveat: a state held between repeated bursts is excluded unless the windows
    span the whole time it is held.
    """
    if min_hits < 1:
        raise ValueError(f"min_hits must be at least 1, got {min_hits}")
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
        if not np.any((muids == muid) & ~inside)
        and np.count_nonzero((muids == muid) & inside) >= min_hits
    ]
    return np.array(confined, dtype=np.uint64)


def frames_with_window_only_payloads(
    log: CanLog,
    windows: Sequence[tuple[float, float]],
    threshold: int = 10,
    bus: Optional[int] = None,
    min_hits: int = 1,
) -> list[tuple[int, int, int]]:
    """Frames that adopt a payload state only inside `windows`.

    Frames are restricted to `threshold` distinct payloads so sensor-like
    frames are skipped.  Returns ``(frame_id, n_window_only_payloads,
    n_distinct_payloads)`` triples; `min_hits` is passed through to
    :func:`payloads_only_in_windows`, which also documents the caveats.
    """
    results = []
    for frame_id, _indices, count in unique_payload_counts(log, bus):
        if not (1 < count <= threshold):
            continue
        confined = payloads_only_in_windows(
            log, frame_id, windows, bus=bus, min_hits=min_hits)
        if confined.size:
            results.append((frame_id, int(confined.size), count))
    return results

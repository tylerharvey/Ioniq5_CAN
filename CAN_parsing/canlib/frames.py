"""Index a :class:`~canlib.log.CanLog` by frame id and analyse state changes.

Everything that needs to walk "every frame id in the log" goes through
:func:`unique_payload_counts`, so the bus filtering, the payload-id packing and
the distinct-state counting have exactly one implementation.  The searches that
used to duplicate that loop (``return_frame_IDs_with_message_changes``,
``return_frame_IDs_muids_with_message_changes_in_timestamp_range`` and
``return_frame_IDs_with_limited_message_changes``) are all thin filters over it.
"""

from __future__ import annotations

from typing import Iterable, NamedTuple, Optional, Sequence

import numpy as np

from .log import CanLog

__all__ = [
    "UNIT_SECONDS",
    "UNIT_RAW",
    "FrameMuid",
    "frame_indices",
    "iter_frames",
    "frame_series",
    "all_messages_for_frame",
    "unique_messages_for_frame",
    "value_transitions",
    "unique_payload_counts",
    "frame_ids_with_message_changes",
    "limited_unique_frames",
    "frames_with_muids",
    "frames_with_muids_in_range",
    "interesting_timestamps",
    "intersect_all",
]

UNIT_SECONDS = "s"
UNIT_RAW = "raw"
_UNITS = (UNIT_SECONDS, UNIT_RAW)


class FrameMuid(NamedTuple):
    """A frame id paired with one packed payload id.

    A named tuple rather than a hand-written class so that ordering and
    hashing follow the obvious ``(frame_id, muid)`` tuple order.
    """

    frame_id: int
    muid: int

    def __str__(self) -> str:
        return f"Frame ID: {self.frame_id}; MUID: {self.muid}"


def frame_indices(log: CanLog, frame_id: int, bus: Optional[int] = None) -> np.ndarray:
    """Row indices holding `frame_id`, optionally restricted to one bus."""
    return np.flatnonzero(log.mask(frame_id, bus))


def iter_frames(log: CanLog, bus: Optional[int] = None):
    """Yield ``(frame_id, row_indices)`` for each frame id in ascending order."""
    for frame_id in np.unique(log.ids):
        yield int(frame_id), frame_indices(log, frame_id, bus)


def frame_series(
    log: CanLog,
    frame_id: int,
    bus: Optional[int] = None,
    unit: str = UNIT_SECONDS,
    hex: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """``(timestamps, payloads)`` for one frame id in chronological order.

    `unit` selects seconds (the default) or the log's raw timestamp unit; see
    :attr:`CanLog.timestamps`.  With ``hex=True`` the payloads are the
    ``(n, 8)`` uppercase hex columns rather than ``uint8`` bytes.  Returns
    empty arrays when the frame is absent.
    """
    if unit not in _UNITS:
        raise ValueError(f"unit must be one of {_UNITS}, got {unit!r}")
    indices = frame_indices(log, frame_id, bus)
    if indices.size == 0:
        return np.array([]), np.empty((0, 8), dtype=log.messages.dtype)
    indices = indices[np.argsort(log.timestamps[indices], kind="stable")]
    timestamps = log.time_s[indices] if unit == UNIT_SECONDS else log.timestamps[indices]
    payloads = log.hex_messages[indices] if hex else log.messages[indices]
    return timestamps, payloads


def all_messages_for_frame(log: CanLog, frame_id: int, hex: bool = False) -> np.ndarray:
    """Every payload of `frame_id`, in log order."""
    indices = frame_indices(log, frame_id)
    return log.hex_messages[indices] if hex else log.messages[indices]


def unique_messages_for_frame(log: CanLog, frame_id: int, hex: bool = False) -> list:
    """One payload per distinct state of `frame_id`, in ascending state order."""
    indices = frame_indices(log, frame_id)
    muids = log.muids[indices]
    messages = []
    for muid in np.unique(muids):
        first = int(np.flatnonzero(muids == muid)[0])
        messages.append(log.hex_messages[indices[first]] if hex else log.messages[indices[first]])
    return messages


def value_transitions(timestamps, values):
    """Where a series changes value between consecutive samples.

    Returns ``(indices, times, from_values, to_values)``, all parallel.  The
    index of each entry is the position of the *new* value, so ``index - 1``
    holds the old one.
    """
    values = np.asarray(values)
    timestamps = np.asarray(timestamps)
    if values.size < 2:
        return (
            np.array([], dtype=int),
            np.array([], dtype=timestamps.dtype),
            np.array([]),
            np.array([]),
        )
    changed = np.flatnonzero(values[1:] != values[:-1]) + 1
    return changed, timestamps[changed], values[changed - 1], values[changed]


def unique_payload_counts(log: CanLog, bus: Optional[int] = None):
    """``[(frame_id, row_indices, n_distinct_payloads)]`` for every frame id.

    Frames with no rows on the selected bus are skipped.
    """
    counts = []
    for frame_id, indices in iter_frames(log, bus):
        if indices.size == 0:
            continue
        counts.append((frame_id, indices, int(np.unique(log.muids[indices]).size)))
    return counts


def frame_ids_with_message_changes(log: CanLog) -> list[list[int]]:
    """``[[frame_id, n_distinct_payloads]]`` for frames that ever change state."""
    return [
        [frame_id, count]
        for frame_id, _indices, count in unique_payload_counts(log)
        if count > 1
    ]


def limited_unique_frames(
    log: CanLog, threshold: int = 10, bus: Optional[int] = None
) -> list[tuple[int, int]]:
    """Frames whose payload takes more than one but at most `threshold` states.

    Control signals toggle between a handful of states and show up here;
    physical sensors take a near-continuous range of values and do not.
    """
    return [
        (frame_id, count)
        for frame_id, _indices, count in unique_payload_counts(log, bus)
        if 1 < count <= threshold
    ]


def frames_with_muids(
    log: CanLog, reject_muids: Iterable[int] = (), bus: Optional[int] = None
) -> list[FrameMuid]:
    """Every ``(frame_id, payload state)`` pair seen in the log.

    `reject_muids` drops states by payload id, which is how the notebooks
    filter out payloads already known to be irrelevant.
    """
    rejected = {int(muid) for muid in reject_muids}
    frames = []
    for frame_id, indices, _count in unique_payload_counts(log, bus):
        for muid in np.unique(log.muids[indices]):
            if int(muid) not in rejected:
                frames.append(FrameMuid(frame_id, int(muid)))
    return frames


def frames_with_muids_in_range(
    log: CanLog,
    timestamp_range: Sequence[int],
    reject_muids: Iterable[int] = (),
    threshold: int = 10,
    only_within_range: bool = True,
) -> list[FrameMuid]:
    """Frames whose individual payload states sit inside a time window.

    `timestamp_range` is a ``(start, end)`` pair **in the log's raw timestamp
    unit** (see :attr:`CanLog.timestamps`), matching the notebook arithmetic
    that builds these ranges.  Only frames with fewer than `threshold` distinct
    payloads are considered, since a sensor's states are never confined.

    With `only_within_range` (the default) a state must be seen *entirely*
    inside the range; otherwise it only has to occur inside the range at least
    once while the frame also shows at least one other state.
    """
    rejected = {int(muid) for muid in reject_muids}
    start, end = timestamp_range
    frames = []
    for frame_id, indices, count in unique_payload_counts(log):
        if count >= threshold:
            continue
        timestamps = log.timestamps[indices]
        muids = log.muids[indices]
        for muid in np.unique(muids):
            if int(muid) in rejected:
                continue
            selected = muids == muid
            state_times = timestamps[selected]
            if only_within_range:
                if state_times[0] > start and state_times[-1] < end:
                    frames.append(FrameMuid(frame_id, int(muid)))
            elif np.any((state_times > start) & (state_times < end)) and np.any(~selected):
                frames.append(FrameMuid(frame_id, int(muid)))
    return frames


def interesting_timestamps(log: CanLog, frame_ids: Iterable[int]) -> list:
    """The timestamp of the largest payload change of each frame id.

    Returned in the log's raw timestamp unit, and -- matching the helper this
    replaced -- the time of the sample *before* the change rather than of the
    change itself.

    Payload ids are compared as signed 64-bit values.  As unsigned values an
    earlier-to-later state change wraps around to roughly 2**64, which made
    every backwards change look like the largest one.  The magnitude of a muid
    difference is only a heuristic for "interesting" in any case.

    Frames absent from the log are skipped.
    """
    timestamps = []
    for frame_id in frame_ids:
        indices = frame_indices(log, frame_id)
        if indices.size:
            changes = np.diff(log.muids[indices].astype(np.int64))
            biggest = int(np.argmax(np.abs(changes)))
            timestamps.append(log.timestamps[indices][biggest])
    return timestamps


def intersect_all(arrays: Sequence[np.ndarray]) -> np.ndarray:
    """Intersection of one or more arrays, value by value."""
    if len(arrays) == 0:
        raise ValueError("intersect_all needs at least one array")
    result = np.asarray(arrays[0])
    for other in arrays[1:]:
        result = np.intersect1d(result, other)
    return result

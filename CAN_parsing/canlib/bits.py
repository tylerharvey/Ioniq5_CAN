"""Bit-level analysis: which individual bits are set, cleared or invariant.

The whole-payload searches in :mod:`canlib.discrete` and the DBC decoding in
:mod:`canlib.dbc` both work at coarser granularity than "this bit means the
driver's door is open".  These helpers reduce a frame's payloads to two
per-byte bitmasks and compare them between two selections, which is how you
name a bit in a frame you have not decoded.

Two modes, ported from the two tools in
``~/Packages/archive/animatronic_panda/examples/`` (see ``panda_port.md``):

``observed``
    ``ones[b]`` has a bit set if it was **ever** 1 in the selection, and
    ``zeros[b]`` if it was **ever** 0.  Comparing a capture that contains a
    stimulus against background captures reports the bits the stimulus
    introduces.  This is ``can_unique.py``.
``invariant``
    ``ones[b]`` has a bit set if it was 1 in **every** sample of the selection,
    and ``zeros[b]`` if it was 0 in every sample.  Comparing a time range where
    a signal is known high against one where it is known low reports the bits
    that follow that signal.  This is ``can_bit_transition.py``.

Both are numpy reductions, so a selection costs one pass over its payloads
rather than the per-row Python loop the originals used.

Frame ids are **not** namespaced by bus, unlike the original tools, which keyed
on ``bus:id``.  `bus` is a filter here, as everywhere else in ``canlib``.  Pass
``bus=`` when one id appears on several buses and you want them kept apart;
otherwise their payloads are pooled, which is well defined because both
reductions are order-independent.

Results render themselves for reading.  A :class:`BitScan` prints as one line
per bit, with the frame id in hex, the bits named rather than left as a bare
mask, and the direction spelled out in the mode's own words::

    new frame 0x150
    id 0x820  byte 2  bit 1  mask 0x02  new one
    id 0x520  byte 3  bits 0-2  mask 0x07  new one
    id 0x520  byte 3  bit 3  mask 0x08  new zero

Nothing here is Hyundai/Kia specific, and nothing here depends on cantools.
"""

from __future__ import annotations

from typing import Iterable, NamedTuple, Optional

import numpy as np

from .frames import frame_indices, iter_frames
from .log import CanLog

__all__ = [
    "OBSERVED",
    "INVARIANT",
    "MODES",
    "BitChange",
    "BitMasks",
    "BitScan",
    "bit_masks",
    "frame_bit_masks",
    "merge_bit_masks",
    "bit_differences",
    "format_bit_scan",
    "frames_only_in",
    "bits_only_in",
]

OBSERVED = "observed"
INVARIANT = "invariant"
MODES = (OBSERVED, INVARIANT)

_N_BYTES = 8
_BYTE_BITS = 8

# mode -> (reduction over a selection's rows for `ones`, dual reduction whose
# complement is `zeros`).  De Morgan makes the two reductions duals: the bits
# that were ever 0 are exactly the complement of the bits that were always 1.
_REDUCTIONS = {
    OBSERVED: (np.bitwise_or, np.bitwise_and),
    INVARIANT: (np.bitwise_and, np.bitwise_or),
}


class BitChange(NamedTuple):
    """One bit that differs between a test and a reference selection.

    `value` is the value the bit takes in the *test* selection, and which the
    reference never showed: 1 for a bit that appears (or goes high), 0 for one
    that disappears (or goes low).  How to read that depends on the mode --
    "new in this capture" for ``observed``, "0 -> 1" for ``invariant``.
    """

    byte: int
    mask: int
    value: int

    def __str__(self) -> str:
        return f"{_geometry(self)}  -> {self.value}"


def _bits_phrase(mask: int) -> str:
    """Name the bits in a byte mask: ``bit 3``, ``bits 4-6``, ``bits 0,6``."""
    positions = [bit for bit in range(_BYTE_BITS) if mask >> bit & 1]
    if not positions:
        return "no bits"
    runs = []
    for bit in positions:
        if runs and bit == runs[-1][1] + 1:
            runs[-1][1] = bit
        else:
            runs.append([bit, bit])
    named = ",".join(f"{first}" if first == last else f"{first}-{last}"
                     for first, last in runs)
    return f"bit {named}" if len(positions) == 1 else f"bits {named}"


def _geometry(change: BitChange) -> str:
    """The frame-less, direction-less part of a change."""
    return (f"byte {change.byte}  {_bits_phrase(change.mask)}  "
            f"mask 0x{change.mask:02X}")


def _direction(change: BitChange, mode: str) -> str:
    """How a change reads in `mode`, in that mode's own words."""
    if mode == OBSERVED:
        return "new one" if change.value else "new zero"
    return "0 -> 1" if change.value else "1 -> 0"


def format_bit_scan(results, mode: str = OBSERVED, new_frames=()) -> str:
    """Render a scan as readable lines, one per differing bit.

    `results` is the ``{frame_id: [BitChange, ...]}`` mapping that
    :func:`bits_only_in` returns.  `new_frames` are frame ids the reference
    never contained; they are listed first, the way the original tool did.
    Returns an empty string when there is nothing to report.

    Example line::

        id 0x1AB  byte 4  bits 4-6  mask 0x70  new one
    """
    lines = [f"new frame 0x{int(frame_id):03X}" for frame_id in new_frames]
    for frame_id, changes in results.items():
        for change in changes:
            lines.append(f"id 0x{int(frame_id):03X}  {_geometry(change)}  "
                         f"{_direction(change, mode)}")
    return "\n".join(lines)


class BitScan(dict):
    """The result of :func:`bits_only_in`: frame id -> differing bit changes.

    A plain ``dict``, so ``scan[0x1AB]``, ``len(scan)`` and ``== {...}`` all
    behave as usual, but it renders a readable table when printed -- and
    because a notebook displays ``repr()`` rather than ``str()``, both are the
    table.
    """

    def __init__(self, results=(), mode: str = OBSERVED, new_frames=()):
        super().__init__(results)
        self.mode = mode
        self.new_frames = tuple(int(frame_id) for frame_id in new_frames)

    def __str__(self) -> str:
        return format_bit_scan(self, self.mode, self.new_frames) or "(no differing bits)"

    __repr__ = __str__


class BitMasks(NamedTuple):
    """Per-byte bit masks for one selection, and how many rows it saw.

    `ones` and `zeros` are ``(8,)`` ``uint8`` arrays; `count` is the number of
    messages in the selection.  A selection with ``count == 0`` observed
    nothing, so its masks carry no information -- :func:`bit_differences`
    refuses it rather than reporting a vacuously invariant result (an AND
    reduction over no rows is all ones).
    """

    mode: str
    ones: np.ndarray
    zeros: np.ndarray
    count: int


def _empty_masks(mode: str) -> BitMasks:
    return BitMasks(
        mode=mode,
        ones=np.zeros(_N_BYTES, dtype=np.uint8),
        zeros=np.zeros(_N_BYTES, dtype=np.uint8),
        count=0,
    )


def bit_masks(messages, mode: str = OBSERVED) -> BitMasks:
    """Reduce an ``(n, 8)`` byte array to per-byte bit masks.

    A single ``(8,)`` payload is treated as one row.  See the module docstring
    for what `mode` means.
    """
    if mode not in _REDUCTIONS:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    payloads = np.asarray(messages)
    if payloads.ndim == 1:
        payloads = payloads[np.newaxis, :]
    if payloads.ndim != 2 or payloads.shape[1] != _N_BYTES:
        raise ValueError(
            f"expected an (n, {_N_BYTES}) byte array, got shape {payloads.shape}"
        )
    count = int(payloads.shape[0])
    if count == 0:
        return _empty_masks(mode)
    ones_reduction, zeros_reduction = _REDUCTIONS[mode]
    return BitMasks(
        mode=mode,
        ones=ones_reduction.reduce(payloads, axis=0).astype(np.uint8),
        zeros=(~zeros_reduction.reduce(payloads, axis=0)).astype(np.uint8),
        count=count,
    )


def frame_bit_masks(
    log: CanLog,
    frame_id: int,
    bus: Optional[int] = None,
    window: Optional[tuple[float, float]] = None,
    mode: str = OBSERVED,
) -> BitMasks:
    """Masks for one frame id, optionally limited to one bus and time window.

    `window` is an inclusive ``(start, end)`` pair in **seconds**, which is how
    the ``invariant`` workflow compares two stretches of a single log.  Masks
    are order-independent, so unlike :func:`canlib.frame_series` nothing is
    sorted here.
    """
    indices = frame_indices(log, frame_id, bus)
    if window is not None:
        start, end = window
        times = log.time_s[indices]
        indices = indices[(times >= start) & (times <= end)]
    return bit_masks(log.messages[indices], mode=mode)


def merge_bit_masks(masks: Iterable[BitMasks]) -> BitMasks:
    """Combine masks built from several selections of the same frame.

    ``observed`` masks are OR-ed and ``invariant`` masks are AND-ed -- the same
    reduction lifted one level, since both ``ones`` and ``zeros`` are already
    positive masks.  Selections that observed nothing are skipped, so an empty
    background log cannot erase a result.
    """
    masks = list(masks)
    if not masks:
        raise ValueError("merge_bit_masks needs at least one selection")
    modes = {mask.mode for mask in masks}
    if len(modes) > 1:
        raise ValueError(f"cannot merge masks from different modes: {sorted(modes)}")
    mode = masks[0].mode
    observed = [mask for mask in masks if mask.count]
    if not observed:
        return _empty_masks(mode)
    combine = _REDUCTIONS[mode][0]
    return BitMasks(
        mode=mode,
        ones=combine.reduce(np.stack([m.ones for m in observed]), axis=0).astype(np.uint8),
        zeros=combine.reduce(np.stack([m.zeros for m in observed]), axis=0).astype(np.uint8),
        count=sum(mask.count for mask in masks),
    )


def bit_differences(test: BitMasks, reference: BitMasks) -> list[BitChange]:
    """Bits that `test` shows and `reference` never shows.

    In ``observed`` mode that is "this capture sets the bit and the background
    never does".  In ``invariant`` mode it is "the bit is always high here and
    always low there".  Results are ordered by byte, with the value-1 change
    before the value-0 change within a byte.

    Raises ``ValueError`` if the two selections were built with different
    modes, or if either observed nothing.
    """
    if test.mode != reference.mode:
        raise ValueError(
            f"cannot compare a {test.mode!r} selection with a {reference.mode!r} one"
        )
    if test.count == 0 or reference.count == 0:
        raise ValueError(
            "bit_differences needs two non-empty selections "
            f"(test={test.count} rows, reference={reference.count} rows); an "
            "empty selection usually means the frame is not on that bus, or a "
            "time window that misses the log"
        )
    if test.mode == OBSERVED:
        appeared = test.ones & ~reference.ones
        vanished = test.zeros & ~reference.zeros
    else:
        appeared = test.ones & reference.zeros
        vanished = test.zeros & reference.ones
    changes = []
    for byte in range(_N_BYTES):
        if appeared[byte]:
            changes.append(BitChange(byte, int(appeared[byte]), 1))
        if vanished[byte]:
            changes.append(BitChange(byte, int(vanished[byte]), 0))
    return changes


def _frame_ids(log: CanLog, bus: Optional[int]) -> list[int]:
    return [frame_id for frame_id, indices in iter_frames(log, bus) if indices.size]


def _as_logs(reference) -> list[CanLog]:
    if isinstance(reference, CanLog):
        return [reference]
    return list(reference)


def _masks_by_frame(log: CanLog, bus: Optional[int], mode: str) -> dict[int, BitMasks]:
    return {
        frame_id: bit_masks(log.messages[frame_indices(log, frame_id, bus)], mode=mode)
        for frame_id in _frame_ids(log, bus)
    }


def frames_only_in(log: CanLog, reference, bus: Optional[int] = None) -> list[int]:
    """Frame ids present in `log` but in none of the `reference` logs.

    `reference` is one :class:`~canlib.log.CanLog` or a sequence of them.  This
    is the "New message_id" line of the original tool.
    """
    seen = set()
    for other in _as_logs(reference):
        seen.update(_frame_ids(other, bus))
    return [frame_id for frame_id in _frame_ids(log, bus) if frame_id not in seen]


def bits_only_in(
    log: CanLog,
    reference,
    bus: Optional[int] = None,
    mode: str = OBSERVED,
) -> BitScan:
    """Per frame id, the bits `log` shows that the reference logs never show.

    This is the whole-log scan of the original tools: `reference` is one
    :class:`~canlib.log.CanLog` or a sequence of them, and their masks are
    merged before comparing.  Frames with no differing bit are left out of the
    mapping; frame ids absent from the reference are not compared but are
    listed in ``scan.new_frames``.

    Returns a :class:`BitScan` -- a dict ordered by ascending frame id that
    prints as a readable table (see :func:`format_bit_scan`).
    """
    reference_masks: dict[int, BitMasks] = {}
    for other in _as_logs(reference):
        for frame_id, masks in _masks_by_frame(other, bus, mode).items():
            if frame_id in reference_masks:
                masks = merge_bit_masks([reference_masks[frame_id], masks])
            reference_masks[frame_id] = masks
    test_masks = _masks_by_frame(log, bus, mode)
    results = {}
    for frame_id, masks in test_masks.items():
        if frame_id not in reference_masks:
            continue
        changes = bit_differences(masks, reference_masks[frame_id])
        if changes:
            results[frame_id] = changes
    new_frames = [frame_id for frame_id in test_masks if frame_id not in reference_masks]
    return BitScan(results, mode=mode, new_frames=new_frames)

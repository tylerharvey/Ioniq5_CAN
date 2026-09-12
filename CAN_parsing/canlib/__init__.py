"""CAN log parsing tools for the Ioniq 5 / E-GMP preconditioning analysis.

Quick start::

    import canlib

    log = canlib.load_log("CAN_logs/panda/I-CAN_car_in_D.csv")
    log.time_s                 # timestamps in seconds
    log.timestamps             # raw, as recorded (see the CanLog docstring)
    log.messages               # (n, 8) uint8 payloads
    log.muids                  # packed payload id per row

    times, payloads = canlib.frame_series(log, 0x2AD)
    canlib.limited_unique_frames(log, threshold=10)

Layout:

``canlib.encoding``
    Hex-text normalisation and the packed payload id (muid).  numpy only.
``canlib.log``
    :class:`CanLog` and the SavvyCAN / panda CSV loaders.  numpy only.
``canlib.frames``
    Indexing a log by frame id, plus every "which frames change state" search.
``canlib.discrete``
    Burst clustering and the window-confined-payload searches.
``canlib.dbc``
    cantools DBC loading and discrete-signal decoding.  Imports cantools, so it
    is deliberately not re-exported here: ``import canlib`` needs only numpy.
"""

from .discrete import (
    Burst,
    cluster_times,
    frames_with_window_only_payloads,
    payload_bursts,
    payloads_only_in_windows,
)
from .encoding import format_hex_bytes, format_hex_ids, pack_muids, unpack_payload_words
from .frames import (
    UNIT_RAW,
    UNIT_SECONDS,
    FrameMuid,
    all_messages_for_frame,
    frame_ids_with_message_changes,
    frame_indices,
    frame_series,
    frames_with_muids,
    frames_with_muids_in_range,
    interesting_timestamps,
    intersect_all,
    iter_frames,
    limited_unique_frames,
    unique_messages_for_frame,
    unique_payload_counts,
    value_transitions,
)
from .log import (
    FORMATS,
    PANDA,
    SAVVYCAN,
    CanLog,
    load_log,
    sniff_format,
    timestamp_discontinuities,
)

__all__ = [
    # encoding
    "format_hex_bytes",
    "format_hex_ids",
    "pack_muids",
    "unpack_payload_words",
    # log
    "SAVVYCAN",
    "PANDA",
    "FORMATS",
    "CanLog",
    "sniff_format",
    "load_log",
    "timestamp_discontinuities",
    # frames
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
    # discrete
    "Burst",
    "cluster_times",
    "payload_bursts",
    "payloads_only_in_windows",
    "frames_with_window_only_payloads",
]

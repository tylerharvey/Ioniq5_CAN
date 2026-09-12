"""Load CAN logs into a :class:`CanLog`.

Two text formats are recognised by their header row:

``savvycan``
    ``Time Stamp,ID,Extended,Dir,Bus,LEN,D1..D8``.  Timestamps are integer
    microseconds and the eight payload bytes are separate hex columns.  Files
    usually end each row with a trailing comma, and some write byte values
    below 0x10 as a single character (``"F"`` rather than ``"0F"``).
``panda``
    ``Bus,MessageID,Message,MessageLength,Time``.  Timestamps are float
    seconds and the payload is one ``0x``-prefixed 16-character hex word.

Both are read with a structured ``np.loadtxt`` dtype whose fields are the
columns we want, so the data is parsed in one pass and each column is converted
by numpy rather than by a Python callback.  Both formats then yield the same
dtypes: payloads ``uint8`` ``(n, 8)``, ids ``uint32``, bus ``uint8``, and the
hex payload columns are uppercase two-character strings.

The raw ``timestamps`` are deliberately *not* converted.  SavvyCAN logs keep
their integer microseconds, which is what the notebook arithmetic and the
log-internal range arguments expect; :attr:`CanLog.time_s` converts to seconds
when that is what you want.  Nothing else should assume a unit.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

import numpy as np

from .encoding import format_hex_bytes, format_hex_ids, pack_muids, unpack_payload_words

__all__ = [
    "SAVVYCAN",
    "PANDA",
    "FORMATS",
    "CanLog",
    "sniff_format",
    "load_log",
    "timestamp_discontinuities",
]

SAVVYCAN = "savvycan"
PANDA = "panda"
FORMATS = (SAVVYCAN, PANDA)

# Divide a log's raw timestamps by this to get seconds.
_TIME_DIVISOR = {SAVVYCAN: 1e6, PANDA: 1.0}

_HEADER_PREFIXES = {PANDA: "bus", SAVVYCAN: "time stamp"}

_DATA_FIELDS = [f"d{i}" for i in range(1, 9)]


def _format_from_header(header: str, path: str) -> str:
    lowered = header.lower().lstrip()
    for fmt, prefix in _HEADER_PREFIXES.items():
        if lowered.startswith(prefix):
            return fmt
    raise ValueError(f"unrecognised log header in {path}: {header.strip()!r}")


def sniff_format(path: str) -> str:
    """Return the log format implied by the file's header row."""
    with open(path, "r", errors="replace") as handle:
        header = handle.readline()
    return _format_from_header(header, path)


@dataclasses.dataclass(eq=False)
class CanLog:
    """One CAN log, with every column a plain numpy array.

    Attributes
    ----------
    source:
        Path the log was read from.
    fmt:
        ``"savvycan"`` or ``"panda"``.
    timestamps:
        Raw timestamps **in the file's own unit** (microseconds for SavvyCAN,
        seconds for panda).  Use :attr:`time_s` instead of assuming.
    ids:
        ``uint32`` frame ids, as written in the file (no implicit
        extended-frame bit).
    messages:
        ``(n, 8)`` ``uint8`` payload bytes.
    bus:
        ``uint8`` bus number for each row (``0`` when the file has no bus
        column).
    hex_ids:
        ``(n,)`` uppercase zero-padded hex frame ids, for display.
    hex_messages:
        ``(n, 8)`` uppercase two-character hex payload bytes, for display.
    """

    source: str
    fmt: str
    timestamps: np.ndarray
    ids: np.ndarray
    messages: np.ndarray
    bus: np.ndarray
    hex_ids: np.ndarray
    hex_messages: np.ndarray
    _muids: Optional[np.ndarray] = dataclasses.field(default=None, repr=False)

    def __len__(self) -> int:
        return int(self.timestamps.shape[0])

    @property
    def time_s(self) -> np.ndarray:
        """Timestamps in seconds as ``float64``."""
        return self.timestamps / _TIME_DIVISOR[self.fmt]

    @property
    def muids(self) -> np.ndarray:
        """Packed big-endian payload id for every row.

        Computed on first use and cached; see
        :func:`canlib.encoding.pack_muids`.
        """
        if self._muids is None:
            self._muids = pack_muids(self.messages)
        return self._muids

    def mask(self, frame_id: int, bus: Optional[int] = None) -> np.ndarray:
        """Boolean mask selecting `frame_id`, optionally restricted to one bus."""
        mask = self.ids == frame_id
        if bus is not None:
            mask &= self.bus == bus
        return mask

    def truncated(self, index: int) -> "CanLog":
        """A copy holding only the rows from `index` onwards."""
        return dataclasses.replace(
            self,
            timestamps=self.timestamps[index:],
            ids=self.ids[index:],
            messages=self.messages[index:],
            bus=self.bus[index:],
            hex_ids=self.hex_ids[index:],
            hex_messages=self.hex_messages[index:],
            _muids=None,
        )

    def timestamp_reset_index(self) -> Optional[int]:
        """Row index just after the first backwards timestamp jump, if any.

        WiCAN/SavvyCAN restarts a capture part-way through a file, so the
        timestamps jump back to zero and everything before the jump belongs to
        a previous session.
        """
        drops = np.flatnonzero(np.diff(self.timestamps) < 0)
        return None if drops.size == 0 else int(drops[0]) + 1

    def after_timestamp_reset(self) -> tuple["CanLog", int]:
        """Drop everything before the first timestamp reset.

        Returns the truncated log and the number of dropped rows, which is
        ``0`` when the log contains no reset.  Use
        :func:`timestamp_discontinuities` if you also want the jump count.
        """
        index = self.timestamp_reset_index()
        if index is None:
            return self, 0
        return self.truncated(index), index


def timestamp_discontinuities(log: CanLog) -> tuple[int, int]:
    """Count ``(backwards jumps, jumps larger than twice the mean spacing)``."""
    diffs = np.diff(log.timestamps)
    if diffs.size == 0:
        return 0, 0
    mean = diffs.mean()
    jumps = int(np.count_nonzero(np.abs((diffs - mean) / mean) > 2)) if mean else 0
    return int(np.count_nonzero(diffs < 0)), jumps


def _header_columns(header: str) -> list[str]:
    return [name.strip().lower() for name in header.split(",")]


def _require(columns: list[str], name: str, path: str) -> int:
    try:
        return columns.index(name)
    except ValueError:
        raise ValueError(f"{path}: expected a {name!r} column, found {columns}") from None


def _hex_converter(text: str) -> int:
    return int(text, 16)


def _parse_table(path: str, fields, usecols, converters) -> np.ndarray:
    """Read the selected columns in one pass into a structured array."""
    record = np.loadtxt(
        path,
        delimiter=",",
        dtype=np.dtype(fields),
        skiprows=1,
        usecols=usecols,
        converters=converters,
    )
    # A single data row comes back 0-d rather than 1-d.
    return np.atleast_1d(record)


def _read_savvycan(path: str, columns: list[str]):
    data_columns = [_require(columns, f"d{i}", path) for i in range(1, 9)]
    time_column = _require(columns, "time stamp", path)
    id_column = _require(columns, "id", path)
    converters = {column: _hex_converter for column in [id_column, *data_columns]}
    data_fields = [(name, np.uint8) for name in _DATA_FIELDS]
    if "bus" in columns:
        fields = [("time", np.int64), ("id", np.uint32), ("bus", np.uint8), *data_fields]
        usecols = [time_column, id_column, columns.index("bus"), *data_columns]
    else:
        # Older SavvyCAN exports have no Bus column; default every row to bus 0.
        fields = [("time", np.int64), ("id", np.uint32), *data_fields]
        usecols = [time_column, id_column, *data_columns]
    record = _parse_table(path, fields, usecols, converters)
    messages = np.stack([record[name] for name in _DATA_FIELDS], axis=1)
    if "bus" in record.dtype.names:
        bus = record["bus"]
    else:
        bus = np.zeros(len(record), dtype=np.uint8)
    return record["time"], record["id"], bus, messages


def _read_panda(path: str, columns: list[str]):
    usecols = [
        _require(columns, "bus", path),
        _require(columns, "messageid", path),
        _require(columns, "message", path),
        _require(columns, "time", path),
    ]
    fields = [
        ("bus", np.uint8),
        ("id", np.uint32),
        ("message", np.uint64),
        ("time", np.float64),
    ]
    converters = {usecols[1]: _hex_converter, usecols[2]: _hex_converter}
    record = _parse_table(path, fields, usecols, converters)
    return (
        record["time"],
        record["id"],
        record["bus"],
        unpack_payload_words(record["message"]),
    )


def load_log(path: str) -> CanLog:
    """Read one CSV log into a :class:`CanLog`."""
    with open(path, "r", errors="replace") as handle:
        header = handle.readline()
    fmt = _format_from_header(header, path)
    columns = _header_columns(header)
    if fmt == SAVVYCAN:
        timestamps, ids, bus, messages = _read_savvycan(path, columns)
    else:
        timestamps, ids, bus, messages = _read_panda(path, columns)
    return CanLog(
        source=path,
        fmt=fmt,
        timestamps=timestamps,
        ids=ids,
        messages=messages,
        bus=bus,
        hex_ids=format_hex_ids(ids),
        hex_messages=format_hex_bytes(messages),
    )

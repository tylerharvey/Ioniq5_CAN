"""Packed payload ids and hex formatting.

A CAN payload is identified throughout this package by its *muid*: the eight
data bytes packed big-endian into a single ``uint64``, so data byte 1 (column
0) is the most significant.  Log files store those same bytes as hex text; the
loader hands the text to numpy's own integer converters, so the only direction
this module has to handle is *numbers to hex*, for display.

This module depends only on numpy.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "format_hex_bytes",
    "format_hex_ids",
    "pack_muids",
    "unpack_payload_words",
]

_N_BYTES = 8

# Lookup table: formatting 8 bytes per row with an f-string is an order of
# magnitude slower than indexing a 256-entry table, and payload text is built
# for every row of every log.
_HEX_BYTES = np.array([f"{value:02X}" for value in range(256)], dtype="U2")


def format_hex_bytes(messages) -> np.ndarray:
    """Return an ``(n, 8)`` array of uppercase two-character hex bytes."""
    return _HEX_BYTES[np.asarray(messages)]


def format_hex_ids(ids) -> np.ndarray:
    """Return an ``(n,)`` array of uppercase zero-padded 8-digit hex frame ids."""
    return np.array([f"{int(value):08X}" for value in ids], dtype="U8")


def unpack_payload_words(words) -> np.ndarray:
    """Split ``(n,)`` big-endian 64-bit payload words into an ``(n, 8)`` uint8 array.

    Used for the panda format, which stores a whole payload as one hex word.
    The byte-order conversion is deliberate: viewing native-order words as
    bytes would put data byte 8 first on a little-endian machine.
    """
    return np.asarray(words, dtype=np.uint64).astype(">u8").view(np.uint8).reshape(-1, _N_BYTES)


def pack_muids(messages) -> np.ndarray:
    """Pack each row of an ``(n, 8)`` byte array into a big-endian ``uint64``.

    Data byte 1 (column 0) ends up as the most significant byte.  A single
    ``(8,)`` payload is treated as one row.  This is the single definition of
    the payload id: the loader, the frame searches and the window helpers all
    call it, so a state comparison never depends on which code path produced
    the bytes.
    """
    payloads = np.asarray(messages)
    if payloads.ndim == 1:
        payloads = payloads[np.newaxis, :]
    if payloads.ndim != 2 or payloads.shape[1] != _N_BYTES:
        raise ValueError(
            f"expected an (n, {_N_BYTES}) byte array, got shape {payloads.shape}"
        )
    muids = np.zeros(payloads.shape[0], dtype=np.uint64)
    for column in range(_N_BYTES):
        muids = (muids << np.uint64(8)) | payloads[:, column].astype(np.uint64)
    return muids

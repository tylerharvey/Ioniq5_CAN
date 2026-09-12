"""Packed payload ids and hex formatting."""

import numpy as np
import pytest

from canlib import encoding


def test_pack_muids_is_big_endian():
    payload = np.array([[0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08]])
    assert encoding.pack_muids(payload)[0] == 0x0102030405060708


def test_pack_muids_accepts_a_single_row():
    payload = np.array([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    assert list(encoding.pack_muids(payload)) == [0x0102030405060708]


def test_pack_muids_matches_manual_shifting():
    rng = np.random.default_rng(0)
    payloads = rng.integers(0, 256, size=(50, 8), dtype=np.uint8)
    expected = [
        sum(int(byte) << (8 * (7 - column)) for column, byte in enumerate(row))
        for row in payloads
    ]
    assert list(encoding.pack_muids(payloads)) == expected


def test_pack_muids_wraps_at_64_bits():
    # All-ones payloads must saturate the uint64 rather than overflow into
    # Python ints or raise.
    payload = np.full((1, 8), 0xFF, dtype=np.uint8)
    assert encoding.pack_muids(payload)[0] == np.uint64(0xFFFFFFFFFFFFFFFF)


def test_pack_muids_empty():
    assert encoding.pack_muids(np.empty((0, 8), dtype=np.uint8)).shape == (0,)


def test_pack_muids_rejects_wrong_width():
    with pytest.raises(ValueError, match=r"\(n, 8\)"):
        encoding.pack_muids(np.zeros((4, 7), dtype=np.uint8))


def test_format_hex_bytes_is_uppercase_and_padded():
    messages = np.array([[0x01, 0xAB, 0x00, 0xFF, 0x09, 0x10, 0x80, 0x0F]], dtype=np.uint8)
    assert list(encoding.format_hex_bytes(messages)[0]) == [
        "01", "AB", "00", "FF", "09", "10", "80", "0F"]


def test_format_hex_ids_is_eight_digits():
    assert list(encoding.format_hex_ids(np.array([0x7B, 0x0A82AA03], dtype=np.uint32))) == [
        "0000007B", "0A82AA03"]


def test_unpack_payload_words_round_trips_with_pack_muids():
    words = np.array([0x0102030405060708, 0xFFFFFFFFFFFFFFFF, 0x00000000000000FF],
                     dtype=np.uint64)
    payloads = encoding.unpack_payload_words(words)
    assert payloads.shape == (3, 8)
    assert list(payloads[0]) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert list(encoding.pack_muids(payloads)) == list(words)


def test_unpack_payload_words_empty():
    assert encoding.unpack_payload_words(np.empty((0,), dtype=np.uint64)).shape == (0, 8)

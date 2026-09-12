"""Loading SavvyCAN and panda logs, and the CanLog value semantics."""

import numpy as np
import pytest

import canlib
from conftest import LOG_DIR, fixture_log


# --------------------------------------------------------------------------
# Formats and dtypes
# --------------------------------------------------------------------------
def test_savvycan_dtypes_and_shape(savvycan_log):
    assert savvycan_log.fmt == canlib.SAVVYCAN
    assert len(savvycan_log) == 7
    assert savvycan_log.timestamps.dtype == np.dtype(np.int64)
    assert savvycan_log.ids.dtype == np.dtype(np.uint32)
    assert savvycan_log.messages.dtype == np.dtype(np.uint8)
    assert savvycan_log.bus.dtype == np.dtype(np.uint8)
    assert savvycan_log.messages.shape == (7, 8)


def test_panda_dtypes_and_shape(panda_log):
    assert panda_log.fmt == canlib.PANDA
    assert len(panda_log) == 4
    assert panda_log.timestamps.dtype == np.dtype(np.float64)
    assert panda_log.ids.dtype == np.dtype(np.uint32)
    assert panda_log.messages.dtype == np.dtype(np.uint8)
    assert panda_log.bus.dtype == np.dtype(np.uint8)


def test_savvycan_timestamps_stay_in_microseconds(savvycan_log):
    # The raw column is what the notebooks and the range searches expect; a
    # SavvyCAN log must not be silently converted to seconds.
    assert list(savvycan_log.timestamps) == [1000, 2000, 3000, 4000, 5000, 6000, 500]
    assert savvycan_log.time_s.dtype == np.dtype(np.float64)
    assert savvycan_log.time_s == pytest.approx([0.001, 0.002, 0.003, 0.004,
                                                 0.005, 0.006, 0.0005])


def test_panda_timestamps_are_already_seconds(panda_log):
    assert list(panda_log.timestamps) == pytest.approx([0.001, 0.002, 0.003, 0.004])
    assert np.array_equal(panda_log.time_s, panda_log.timestamps)


def test_payloads_decode_identically_for_both_formats(panda_log):
    # 0x0102030405060708 in the panda fixture is the same payload the SavvyCAN
    # fixture spells across D1..D8.
    assert list(panda_log.messages[0]) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert list(panda_log.messages[2]) == [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22]


# --------------------------------------------------------------------------
# Hex columns: one normalised representation for both formats
# --------------------------------------------------------------------------
def test_hex_columns_are_padded_and_uppercase(savvycan_log):
    # The fixture writes the byte 0x01 as a single character "1".
    assert savvycan_log.hex_messages.dtype == np.dtype("U2")
    assert savvycan_log.hex_messages[0, 0] == "01"
    assert savvycan_log.hex_messages[3, 0] == "AA"


def test_hex_ids_are_zero_padded(savvycan_log):
    assert list(savvycan_log.hex_ids) == ["00000123"] * 3 + ["00000200"] * 3 + ["00000123"]


def test_panda_hex_columns_are_uppercase_strings(panda_log):
    assert panda_log.hex_messages.dtype == np.dtype("U2")
    assert list(panda_log.hex_messages[2]) == ["AA", "BB", "CC", "DD", "EE", "FF", "11", "22"]


@pytest.mark.skipif(not LOG_DIR.exists(), reason="CAN_logs corpus is not present")
def test_real_log_with_short_hex_bytes_is_padded():
    # This log writes some payload bytes as a single character.
    log = canlib.load_log(str(LOG_DIR / "car_buttons/M-CAN_tuner_down_up_down_up_6-24.csv"))
    assert set(map(len, log.hex_messages.ravel().tolist())) == {2}


# --------------------------------------------------------------------------
# Bus handling
# --------------------------------------------------------------------------
def test_mask_filters_by_bus(savvycan_log):
    assert list(savvycan_log.mask(0x200)) == [False, False, False, True, True, True, False]
    assert list(savvycan_log.mask(0x200, bus=0)) == [False, False, False, False, True, True, False]


def test_missing_bus_column_defaults_to_zero():
    log = canlib.load_log(fixture_log("savvycan_no_bus.csv"))
    assert len(log) == 2
    assert list(log.bus) == [0, 0]


# --------------------------------------------------------------------------
# Timestamp resets
# --------------------------------------------------------------------------
def test_timestamp_reset_index_and_truncation(savvycan_log):
    assert savvycan_log.timestamp_reset_index() == 6
    truncated, dropped = savvycan_log.after_timestamp_reset()
    assert dropped == 6
    assert len(truncated) == 1
    assert list(truncated.timestamps) == [500]
    # truncation returns a copy and leaves the source alone
    assert len(savvycan_log) == 7


def test_log_without_a_reset_is_unchanged(panda_log):
    assert panda_log.timestamp_reset_index() is None
    same, dropped = panda_log.after_timestamp_reset()
    assert dropped == 0
    assert len(same) == len(panda_log)


def test_truncated_recomputes_the_muid_cache(savvycan_log):
    before = list(savvycan_log.muids)          # populate the cache first
    truncated = savvycan_log.truncated(3)
    assert len(truncated.muids) == 4
    assert list(truncated.muids) == before[3:]


def test_timestamp_discontinuities_counts_the_backwards_jump(savvycan_log):
    drops, jumps = canlib.timestamp_discontinuities(savvycan_log)
    assert drops == 1
    assert jumps > 0


# --------------------------------------------------------------------------
# Malformed input
# --------------------------------------------------------------------------
def test_sniff_format_recognises_both_headers():
    assert canlib.sniff_format(fixture_log("savvycan_small.csv")) == canlib.SAVVYCAN
    assert canlib.sniff_format(fixture_log("panda_small.csv")) == canlib.PANDA


def test_unknown_header_is_rejected(tmp_path):
    path = tmp_path / "weird.csv"
    path.write_text("alpha,beta\n1,2\n")
    with pytest.raises(ValueError, match="unrecognised log header"):
        canlib.sniff_format(str(path))
    with pytest.raises(ValueError):
        canlib.load_log(str(path))


def test_missing_data_column_is_reported(tmp_path):
    path = tmp_path / "short.csv"
    path.write_text(
        "Time Stamp,ID,Extended,Dir,Bus,LEN,D1,D2,D3,D4,D5,D6,D7\n"
        "1000,00000123,false,Rx,0,7,1,2,3,4,5,6,7,\n"
    )
    with pytest.raises(ValueError, match="d8"):
        canlib.load_log(str(path))


def test_single_row_log_is_still_two_dimensional(tmp_path):
    path = tmp_path / "one.csv"
    path.write_text(
        "Time Stamp,ID,Extended,Dir,Bus,LEN,D1,D2,D3,D4,D5,D6,D7,D8\n"
        "1000,00000123,false,Rx,0,8,1,2,3,4,5,6,7,8,\n"
    )
    log = canlib.load_log(str(path))
    assert len(log) == 1
    assert log.messages.shape == (1, 8)
    assert log.hex_messages.shape == (1, 8)

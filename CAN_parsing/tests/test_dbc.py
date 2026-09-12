"""DBC loading, signal rendering and discrete-signal decoding."""

import pytest

from canlib import dbc as dbc_lib
from conftest import DBC_DIR, REAL_DBCS

TINY_DBC = '''VERSION ""

NS_ :

BS_:

BU_: ECU

BO_ 291 Fixture_123: 8 ECU
 SG_ Counter : 0|8@1+ (1,0) [0|255] "" ECU
 SG_ Tail : 56|8@1+ (1,0) [0|255] "" ECU

BO_ 292 Fixture_Float: 8 ECU
 SG_ Temp : 0|16@1+ (0.5,0) [0|100] "C" ECU

BO_ 100 ISOTP_Fixture: 8 ECU
 SG_ A : 0|8@1+ (1,0) [0|255] "" ECU

BO_ 101 VIN_Fixture: 8 ECU
 SG_ B : 0|8@1+ (1,0) [0|255] "" ECU

BA_ "VFrameFormat" BO_ 291 1;

VAL_ 291 Tail 8 "eight" 9 "nine";
'''

REDEFINED_DBC = '''VERSION ""

NS_ :

BS_:

BU_: ECU

BO_ 291 Second_123: 8 ECU
 SG_ Other : 0|8@1+ (1,0) [0|255] "" ECU
'''


def _load_db(tmp_path):
    path = tmp_path / "tiny.dbc"
    path.write_text(TINY_DBC)
    return dbc_lib.load_dbc([str(path)])


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def test_load_dbc_parses_the_tiny_database(tmp_path, capsys):
    db = _load_db(tmp_path)
    assert db is not None
    assert dbc_lib.frame_ids(db) == {291, 292, 100, 101}
    assert "Loaded DBC" in capsys.readouterr().out


def test_load_dbc_returns_none_when_nothing_can_be_read(tmp_path, capsys):
    assert dbc_lib.load_dbc([str(tmp_path / "missing.dbc")]) is None
    assert "cannot read DBC" in capsys.readouterr().err


def test_load_dbc_warns_and_skips_an_unparsable_file(tmp_path, capsys):
    path = tmp_path / "broken.dbc"
    path.write_text("this is not a dbc\n")
    assert dbc_lib.load_dbc([str(path)]) is None
    assert "could not parse DBC" in capsys.readouterr().err


def test_load_dbc_merges_first_wins(tmp_path):
    first = tmp_path / "first.dbc"
    first.write_text(TINY_DBC)
    second = tmp_path / "second.dbc"
    second.write_text(REDEFINED_DBC)
    db = dbc_lib.load_dbc([str(first), str(second)])
    # the first definition of 291 wins; the second only fills gaps (none here)
    assert db.get_message_by_frame_id(291).name == "Fixture_123"


@pytest.mark.skipif(not DBC_DIR.exists(), reason="~/Packages/egmpdbc is not present")
def test_load_real_egmp_dbcs_and_merge():
    db = dbc_lib.load_dbc([str(DBC_DIR / name) for name in REAL_DBCS])
    assert db is not None
    # 0x2AD is the preconditioning status frame in the M-CAN DBCs.
    assert 0x2AD in dbc_lib.frame_ids(db)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def test_is_excluded_frame(tmp_path):
    db = _load_db(tmp_path)
    assert dbc_lib.is_excluded_frame(db.get_message_by_frame_id(100))
    assert dbc_lib.is_excluded_frame(db.get_message_by_frame_id(101))
    assert not dbc_lib.is_excluded_frame(db.get_message_by_frame_id(291))


def test_signal_display_name_prefers_choices(tmp_path):
    db = _load_db(tmp_path)
    message = db.get_message_by_frame_id(291)
    tail = message.get_signal_by_name("Tail")
    assert dbc_lib.signal_display_name(tail, 8) == "eight (8)"
    # a value with no VAL_ entry falls back to its number
    assert dbc_lib.signal_display_name(tail, 200) == "200"


def test_signal_display_name_formats_floats(tmp_path):
    db = _load_db(tmp_path)
    temp = db.get_message_by_frame_id(292).get_signal_by_name("Temp")
    assert dbc_lib.signal_display_name(temp, 2.5) == "2.500"


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------
def test_decode_signal_transitions_finds_the_changing_signal(savvycan_log, tmp_path):
    db = _load_db(tmp_path)
    signals = dbc_lib.decode_signal_transitions(
        savvycan_log, 0x123, db, threshold=10, min_changes=1)
    assert [signal["signal"] for signal in signals] == ["Tail"]
    tail = signals[0]
    assert tail["n_distinct"] == 2
    assert tail["values"] == ["eight (8)", "nine (9)"]
    assert tail["n_changes"] == 1
    assert tail["transitions"] == [
        {"time_s": pytest.approx(0.003), "from": "eight (8)", "to": "nine (9)"}]


def test_decode_signal_transitions_respects_min_changes(savvycan_log, tmp_path):
    db = _load_db(tmp_path)
    assert dbc_lib.decode_signal_transitions(
        savvycan_log, 0x123, db, threshold=10, min_changes=2) == []


def test_decode_signal_transitions_ignores_constant_signals(savvycan_log, tmp_path):
    # Counter (byte 0) is constant in the fixture, so it is not reported even
    # though it is a valid signal.
    db = _load_db(tmp_path)
    names = [signal["signal"] for signal in dbc_lib.decode_signal_transitions(
        savvycan_log, 0x123, db, threshold=10, min_changes=1)]
    assert "Counter" not in names


def test_discrete_signals_for_log_skips_frames_absent_from_the_dbc(savvycan_log, tmp_path):
    db = _load_db(tmp_path)
    results = dbc_lib.discrete_signals_for_log(savvycan_log, db, threshold=10, min_changes=1)
    # frame 0x200 is not in the tiny DBC
    assert [result["frame_id"] for result in results] == [0x123]
    assert results[0]["frame_name"] == "Fixture_123"


def test_decode_signal_transitions_for_an_absent_frame(savvycan_log, tmp_path):
    db = _load_db(tmp_path)
    assert dbc_lib.decode_signal_transitions(
        savvycan_log, 0x200, db, threshold=10, min_changes=1) == []

"""The highlight_bits.py command line."""

import pytest

import highlight_bits
from conftest import fixture_log

BITS = "savvycan_bits.csv"
BACKGROUND = "savvycan_bits_background.csv"
LOW = "0.0005-0.0015"
HIGH = "0.0015-0.0035"


def test_parse_range():
    assert highlight_bits.parse_range("1.5-2.5") == (1.5, 2.5)
    assert highlight_bits.parse_range("0-10") == (0.0, 10.0)


# --------------------------------------------------------------------------
# observed
# --------------------------------------------------------------------------
def test_observed_prints_a_readable_table(capsys):
    code = highlight_bits.main(["observed", fixture_log(BITS), fixture_log(BACKGROUND)])
    assert code == 0
    assert capsys.readouterr().out == (
        "observed: savvycan_bits.csv vs 1 background log  [every bus]\n"
        "  1 frame with differing bits, 1 frame id not in the background\n"
        "\n"
        "new frame 0x150\n"
        "id 0x100  byte 0  bit 0  mask 0x01  new one\n"
        "id 0x100  byte 1  bits 0-3  mask 0x0F  new one\n")


def test_observed_accepts_several_backgrounds(capsys):
    code = highlight_bits.main(["observed", fixture_log(BITS),
                                fixture_log(BACKGROUND), fixture_log(BACKGROUND)])
    assert code == 0
    assert "vs 2 background logs" in capsys.readouterr().out


def test_observed_bus_filter(capsys):
    code = highlight_bits.main(["observed", fixture_log(BITS), fixture_log(BACKGROUND),
                                "--bus", "1"])
    assert code == 0
    out = capsys.readouterr().out
    assert "0 frames with differing bits, 0 frame ids not in the background" in out
    assert out.endswith("(no differing bits)\n")


# --------------------------------------------------------------------------
# invariant
# --------------------------------------------------------------------------
def test_invariant_prints_a_readable_table(capsys):
    code = highlight_bits.main(["invariant", fixture_log(BITS), LOW, HIGH])
    assert code == 0
    assert capsys.readouterr().out == (
        "invariant: savvycan_bits.csv  low=0.001-0.002s  high=0.002-0.004s  "
        "[every bus]\n"
        "  1 frame compared, 1 frame with differing bits, 1 frame skipped "
        "(too few rows in a window)\n"
        "\n"
        "id 0x100  byte 0  bit 0  mask 0x01  0 -> 1\n"
        "id 0x100  byte 1  bits 0-3  mask 0x0F  1 -> 0\n")


def test_invariant_can_restrict_to_one_frame(capsys):
    code = highlight_bits.main(["invariant", fixture_log(BITS), LOW, HIGH,
                                "--id", "0x100"])
    assert code == 0
    out = capsys.readouterr().out
    assert "1 frame compared, 1 frame with differing bits, 0 frames skipped" in out


def test_invariant_warns_about_an_id_the_log_does_not_have(capsys):
    code = highlight_bits.main(["invariant", fixture_log(BITS), LOW, HIGH,
                                "--id", "0x999"])
    captured = capsys.readouterr()
    assert code == 0
    assert "WARN: 0x999 is not in savvycan_bits.csv" in captured.err
    assert captured.out.endswith("(no differing bits)\n")


def test_invariant_min_rows_skips_short_windows(capsys):
    code = highlight_bits.main(["invariant", fixture_log(BITS), LOW, HIGH,
                                "--id", "0x100", "--min-rows", "2"])
    assert code == 0
    out = capsys.readouterr().out
    assert "0 frames compared" in out
    assert out.endswith("(no differing bits)\n")


def test_invariant_bus_filter(capsys):
    code = highlight_bits.main(["invariant", fixture_log(BITS), LOW, HIGH,
                                "--bus", "1"])
    assert code == 0
    out = capsys.readouterr().out
    assert "[bus 1]" in out
    assert out.endswith("(no differing bits)\n")


# --------------------------------------------------------------------------
# Bad input
# --------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["50", "50-", "a-b", "65-50"])
def test_a_bad_range_is_rejected(bad):
    with pytest.raises(SystemExit) as exit_info:
        highlight_bits.main(["invariant", fixture_log(BITS), bad, HIGH])
    assert "START-END" in str(exit_info.value) or "starts after" in str(exit_info.value)


def test_a_missing_log_is_reported(tmp_path):
    missing = str(tmp_path / "nope.csv")
    with pytest.raises(SystemExit) as exit_info:
        highlight_bits.main(["observed", missing, fixture_log(BACKGROUND)])
    assert "cannot read" in str(exit_info.value)


def test_an_unknown_mode_is_rejected():
    with pytest.raises(SystemExit):
        highlight_bits.main(["sometimes", fixture_log(BITS)])

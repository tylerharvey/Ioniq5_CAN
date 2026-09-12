"""Bit-level masks and the observed/invariant bit comparisons."""

import numpy as np
import pytest

import canlib

# Two rows chosen so that byte 0 has a bit that is always 1 and byte 1 has one
# that is always 0, while both bytes have mixed bits.
PAYLOADS = np.array([
    [0x01, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    [0x05, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
], dtype=np.uint8)

LOW_WINDOW = (0.0005, 0.0015)
HIGH_WINDOW = (0.0015, 0.0035)


# --------------------------------------------------------------------------
# bit_masks
# --------------------------------------------------------------------------
def test_bit_masks_observed_mode():
    observed = canlib.bit_masks(PAYLOADS)
    assert observed.mode == canlib.OBSERVED
    assert observed.count == 2
    # byte 0 saw 0x01 and 0x05: bit 2 appeared, bit 0 never cleared
    assert observed.ones[0] == 0x05
    assert observed.zeros[0] == 0xFE
    # byte 1 saw 0x03 and 0x01: bit 1 appeared and cleared
    assert observed.ones[1] == 0x03
    assert observed.zeros[1] == 0xFE
    # a byte held at zero is never-1 and always-0
    assert observed.ones[2] == 0x00
    assert observed.zeros[2] == 0xFF


def test_bit_masks_invariant_mode():
    invariant = canlib.bit_masks(PAYLOADS, mode=canlib.INVARIANT)
    assert invariant.mode == canlib.INVARIANT
    assert invariant.count == 2
    # byte 0: bit 0 is set in both rows, bit 2 only in one
    assert invariant.ones[0] == 0x01
    assert invariant.zeros[0] == 0xFA
    assert invariant.ones[1] == 0x01
    assert invariant.zeros[1] == 0xFC


def test_the_two_modes_are_not_the_same():
    # This is why both were ported: "never seen set" and "never always set" are
    # different questions.
    observed = canlib.bit_masks(PAYLOADS)
    invariant = canlib.bit_masks(PAYLOADS, mode=canlib.INVARIANT)
    assert observed.ones[0] != invariant.ones[0]
    assert observed.zeros[0] != invariant.zeros[0]


def test_invariant_mode_reports_a_mixed_bit_as_neither():
    payloads = np.zeros((2, 8), dtype=np.uint8)
    payloads[1, 0] = 0x01
    invariant = canlib.bit_masks(payloads, mode=canlib.INVARIANT)
    assert invariant.ones[0] == 0x00
    # bit 0 is mixed, so it is in neither mask; bits 1-7 were always zero
    assert invariant.zeros[0] == 0xFE


def test_bit_masks_accepts_a_single_row():
    masks = canlib.bit_masks(np.array([0x01] + [0] * 7, dtype=np.uint8))
    assert masks.count == 1
    assert masks.ones[0] == 0x01
    assert masks.zeros[0] == 0xFE


def test_bit_masks_of_an_empty_selection_does_not_claim_invariance():
    # An AND reduction over no rows is all ones, which would read as "always
    # high"; the empty selection must not be allowed to say that.
    empty = np.empty((0, 8), dtype=np.uint8)
    for mode in canlib.MODES:
        masks = canlib.bit_masks(empty, mode=mode)
        assert masks.count == 0
        assert not masks.ones.any()
        assert not masks.zeros.any()


def test_bit_masks_rejects_a_wrong_shape():
    with pytest.raises(ValueError, match=r"\(n, 8\)"):
        canlib.bit_masks(np.zeros((3, 7), dtype=np.uint8))


def test_bit_masks_rejects_an_unknown_mode():
    with pytest.raises(ValueError, match="mode must be one of"):
        canlib.bit_masks(np.zeros((1, 8), dtype=np.uint8), mode="sometimes")


# --------------------------------------------------------------------------
# frame_bit_masks
# --------------------------------------------------------------------------
def test_frame_bit_masks_matches_the_frame_payloads(bits_log):
    masks = canlib.frame_bit_masks(bits_log, 0x100)
    assert masks.count == 3
    assert list(masks.ones[:2]) == [0x01, 0x0F]
    assert list(masks.zeros[:2]) == [0xFF, 0xFF]


def test_frame_bit_masks_window_limits_the_selection(bits_log):
    low = canlib.frame_bit_masks(bits_log, 0x100, window=LOW_WINDOW,
                                 mode=canlib.INVARIANT)
    high = canlib.frame_bit_masks(bits_log, 0x100, window=HIGH_WINDOW,
                                  mode=canlib.INVARIANT)
    assert (low.count, high.count) == (1, 2)
    assert list(low.ones[:2]) == [0x00, 0x0F]
    assert list(high.ones[:2]) == [0x01, 0x00]


def test_frame_bit_masks_for_an_absent_frame(bits_log):
    assert canlib.frame_bit_masks(bits_log, 0x999).count == 0


def test_frame_bit_masks_respects_bus(bits_log):
    assert canlib.frame_bit_masks(bits_log, 0x100, bus=0).count == 3
    assert canlib.frame_bit_masks(bits_log, 0x100, bus=1).count == 0


# --------------------------------------------------------------------------
# merge_bit_masks
# --------------------------------------------------------------------------
def test_merge_bit_masks_ors_observed_selections(bits_background):
    # frame 0x100 in the background is all zero; add a selection that sets a bit
    held_zero = canlib.frame_bit_masks(bits_background, 0x100)
    bit_set = canlib.bit_masks(
        np.array([[0, 0, 0, 0, 0, 0, 0, 0x01]], dtype=np.uint8))
    merged = canlib.merge_bit_masks([held_zero, bit_set])
    assert merged.mode == canlib.OBSERVED
    assert merged.count == 3
    assert merged.ones[0] == 0x00
    assert merged.ones[7] == 0x01


def test_merge_bit_masks_ands_invariant_selections():
    def row(first):
        return canlib.bit_masks(np.array([[first] + [0] * 7], dtype=np.uint8),
                                mode=canlib.INVARIANT)
    merged = canlib.merge_bit_masks([row(0x0F), row(0x03)])
    assert merged.ones[0] == 0x03
    assert merged.count == 2


def test_merge_bit_masks_skips_selections_that_observed_nothing():
    empty = canlib.bit_masks(np.empty((0, 8), dtype=np.uint8), mode=canlib.INVARIANT)
    full = canlib.bit_masks(np.array([[0x0F] + [0] * 7], dtype=np.uint8),
                            mode=canlib.INVARIANT)
    merged = canlib.merge_bit_masks([empty, full])
    # the AND identity of the empty selection must not erase the real result
    assert merged.ones[0] == 0x0F
    assert merged.count == 1
    assert canlib.merge_bit_masks([empty, empty]).count == 0


def test_merge_bit_masks_rejects_mixed_modes(bits_log):
    observed = canlib.frame_bit_masks(bits_log, 0x100)
    invariant = canlib.frame_bit_masks(bits_log, 0x100, mode=canlib.INVARIANT)
    with pytest.raises(ValueError, match="different modes"):
        canlib.merge_bit_masks([observed, invariant])


def test_merge_bit_masks_needs_a_selection():
    with pytest.raises(ValueError, match="at least one"):
        canlib.merge_bit_masks([])


# --------------------------------------------------------------------------
# bit_differences
# --------------------------------------------------------------------------
def test_bit_differences_observed_mode(bits_log, bits_background):
    # The background holds frame 0x100 at all-zero, so every bit the test
    # capture sets is new to it.
    changes = canlib.bit_differences(
        canlib.frame_bit_masks(bits_log, 0x100),
        canlib.frame_bit_masks(bits_background, 0x100))
    assert changes == [canlib.BitChange(0, 0x01, 1), canlib.BitChange(1, 0x0F, 1)]


def test_bit_differences_invariant_mode(bits_log):
    # Byte 0 goes 0 -> 1 between the windows and byte 1 goes 1 -> 0.
    low = canlib.frame_bit_masks(bits_log, 0x100, window=LOW_WINDOW,
                                 mode=canlib.INVARIANT)
    high = canlib.frame_bit_masks(bits_log, 0x100, window=HIGH_WINDOW,
                                  mode=canlib.INVARIANT)
    assert canlib.bit_differences(high, low) == [
        canlib.BitChange(0, 0x01, 1), canlib.BitChange(1, 0x0F, 0)]


def test_bit_differences_is_empty_for_identical_selections(bits_log):
    assert canlib.bit_differences(canlib.frame_bit_masks(bits_log, 0x100),
                                  canlib.frame_bit_masks(bits_log, 0x100)) == []


def test_bit_differences_rejects_mismatched_modes(bits_log):
    observed = canlib.frame_bit_masks(bits_log, 0x100)
    invariant = canlib.frame_bit_masks(bits_log, 0x100, mode=canlib.INVARIANT)
    with pytest.raises(ValueError, match="cannot compare"):
        canlib.bit_differences(observed, invariant)


def test_bit_differences_rejects_an_empty_selection(bits_log):
    empty = canlib.frame_bit_masks(bits_log, 0x999)
    full = canlib.frame_bit_masks(bits_log, 0x100)
    with pytest.raises(ValueError, match="non-empty"):
        canlib.bit_differences(empty, full)
    with pytest.raises(ValueError, match="non-empty"):
        canlib.bit_differences(full, empty)


# --------------------------------------------------------------------------
# Whole-log scans
# --------------------------------------------------------------------------
def test_frames_only_in(bits_log, bits_background):
    assert canlib.frames_only_in(bits_log, bits_background) == [0x150]
    assert canlib.frames_only_in(bits_background, bits_log) == [0x200]
    assert canlib.frames_only_in(bits_log, bits_log) == []


def test_frames_only_in_respects_bus(bits_log, bits_background):
    assert canlib.frames_only_in(bits_log, bits_background, bus=1) == []


def test_bits_only_in_scans_every_frame(bits_log, bits_background):
    assert canlib.bits_only_in(bits_log, bits_background) == {
        0x100: [canlib.BitChange(0, 0x01, 1), canlib.BitChange(1, 0x0F, 1)]}


def test_bits_only_in_accepts_several_reference_logs(bits_log, bits_background):
    assert (canlib.bits_only_in(bits_log, [bits_background, bits_background])
            == canlib.bits_only_in(bits_log, bits_background))


def test_bits_only_in_invariant_mode_asks_a_different_question(bits_log, bits_background):
    # No bit is always high in the test capture and always low in the
    # background, even though the observed comparison finds several bits.
    assert canlib.bits_only_in(bits_log, bits_background, mode=canlib.INVARIANT) == {}
    assert canlib.bits_only_in(bits_log, bits_background) != {}


# --------------------------------------------------------------------------
# Readable output
# --------------------------------------------------------------------------
def test_bit_change_str_names_the_bits():
    # A mask is hard to read; the individual bits are not.
    assert str(canlib.BitChange(4, 0x70, 1)) == "byte 4  bits 4-6  mask 0x70  -> 1"
    assert str(canlib.BitChange(1, 0x08, 0)) == "byte 1  bit 3  mask 0x08  -> 0"
    assert str(canlib.BitChange(0, 0x41, 1)) == "byte 0  bits 0,6  mask 0x41  -> 1"
    assert str(canlib.BitChange(7, 0xFF, 1)) == "byte 7  bits 0-7  mask 0xFF  -> 1"


def test_format_bit_scan_observed(bits_log, bits_background):
    scan = canlib.bits_only_in(bits_log, bits_background)
    assert canlib.format_bit_scan(scan, canlib.OBSERVED, scan.new_frames) == (
        "new frame 0x150\n"
        "id 0x100  byte 0  bit 0  mask 0x01  new one\n"
        "id 0x100  byte 1  bits 0-3  mask 0x0F  new one")


def test_format_bit_scan_invariant(bits_log):
    low = canlib.frame_bit_masks(bits_log, 0x100, window=LOW_WINDOW,
                                 mode=canlib.INVARIANT)
    high = canlib.frame_bit_masks(bits_log, 0x100, window=HIGH_WINDOW,
                                  mode=canlib.INVARIANT)
    changes = canlib.bit_differences(high, low)
    assert canlib.format_bit_scan({0x100: changes}, canlib.INVARIANT) == (
        "id 0x100  byte 0  bit 0  mask 0x01  0 -> 1\n"
        "id 0x100  byte 1  bits 0-3  mask 0x0F  1 -> 0")


def test_format_bit_scan_of_nothing_is_empty():
    assert canlib.format_bit_scan({}, canlib.OBSERVED) == ""


def test_bit_scan_prints_as_a_table(bits_log, bits_background):
    scan = canlib.bits_only_in(bits_log, bits_background)
    assert str(scan) == (
        "new frame 0x150\n"
        "id 0x100  byte 0  bit 0  mask 0x01  new one\n"
        "id 0x100  byte 1  bits 0-3  mask 0x0F  new one")


def test_bit_scan_repr_is_the_table_because_a_notebook_shows_repr(bits_log, bits_background):
    scan = canlib.bits_only_in(bits_log, bits_background)
    assert repr(scan) == str(scan)


def test_bit_scan_says_so_when_nothing_differs(bits_log):
    assert str(canlib.bits_only_in(bits_log, bits_log)) == "(no differing bits)"


def test_bit_scan_still_behaves_like_a_dict(bits_log, bits_background):
    scan = canlib.bits_only_in(bits_log, bits_background)
    assert scan == {0x100: [canlib.BitChange(0, 0x01, 1), canlib.BitChange(1, 0x0F, 1)]}
    assert list(scan) == [0x100]
    assert scan[0x100] == [canlib.BitChange(0, 0x01, 1), canlib.BitChange(1, 0x0F, 1)]
    assert scan.new_frames == (0x150,)
    assert scan.mode == canlib.OBSERVED

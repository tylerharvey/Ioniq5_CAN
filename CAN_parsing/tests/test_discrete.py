"""Burst clustering and the window-confined-payload searches."""

import numpy as np
import pytest

import canlib

FRAME_B = 0x200
FRAME_300 = 0x300
MU_D = 0xAABBCCDDEEFF1123
# Splits the two CC transmissions (0.7 ms apart) but not the AA or BB runs.
GAP = 0.0005


def _muid(first_byte: int) -> int:
    """Packed payload id of ``(first_byte, 0, 0, 0, 0, 0, 0, 0)``."""
    return int(canlib.pack_muids(np.array([[first_byte] + [0] * 7], dtype=np.uint8))[0])


# --------------------------------------------------------------------------
# cluster_times
# --------------------------------------------------------------------------
def test_cluster_times_splits_on_gaps():
    assert canlib.cluster_times([1, 2, 3, 10, 11, 40], gap=2) == [(1, 3), (10, 11), (40, 40)]


def test_cluster_times_accepts_unsorted_input():
    assert canlib.cluster_times([5, 1, 2], gap=1) == [(1, 2), (5, 5)]


def test_cluster_times_is_empty_for_no_events():
    assert canlib.cluster_times([], gap=1) == []


def test_cluster_times_preserves_float_seconds():
    assert canlib.cluster_times([0.1, 0.2, 0.9], gap=0.5) == [(0.1, 0.2), (0.9, 0.9)]


# --------------------------------------------------------------------------
# payload_bursts
# --------------------------------------------------------------------------
def test_payload_bursts_splits_on_a_payload_change(bursts_log):
    bursts = canlib.payload_bursts(bursts_log, FRAME_300, gap=GAP, bus=0)
    assert [(b.payload[0], b.count) for b in bursts] == [
        (0xAA, 3), (0xBB, 2), (0xCC, 1), (0xCC, 1)]


def test_payload_bursts_reports_both_ends_in_seconds(bursts_log):
    first, second = canlib.payload_bursts(bursts_log, FRAME_300, gap=GAP, bus=0)[:2]
    assert (first.start_s, first.end_s) == pytest.approx((0.0010, 0.0012))
    assert (second.start_s, second.end_s) == pytest.approx((0.0013, 0.0014))
    assert first.muid == _muid(0xAA)
    assert first.payload == (0xAA, 0, 0, 0, 0, 0, 0, 0)


def test_payload_bursts_splits_on_a_gap(bursts_log):
    # A 1 ms gap joins the two CC transmissions, which are 0.7 ms apart.
    bursts = canlib.payload_bursts(bursts_log, FRAME_300, gap=0.001, bus=0)
    assert [(b.payload[0], b.count) for b in bursts] == [(0xAA, 3), (0xBB, 2), (0xCC, 2)]


def test_payload_bursts_keeps_commands_that_cluster_times_would_merge(bursts_log):
    # The AA and BB runs are only 0.1 ms apart, so a gap-only clustering
    # reports them as one window and the command change is lost.
    bursts = canlib.payload_bursts(bursts_log, FRAME_300, gap=GAP, bus=0)
    times = bursts_log.time_s[canlib.frame_indices(bursts_log, FRAME_300, bus=0)]
    first_window = canlib.cluster_times(times, GAP)[0]
    merged = [b for b in bursts
              if first_window[0] - 1e-12 <= b.start_s <= first_window[1] + 1e-12]
    assert {b.payload[0] for b in merged} == {0xAA, 0xBB}


def test_payload_bursts_respects_bus(bursts_log):
    bursts = canlib.payload_bursts(bursts_log, FRAME_300, gap=GAP, bus=1)
    assert [(b.payload[0], b.count) for b in bursts] == [(0xDD, 1)]


def test_payload_bursts_without_a_bus_filter_includes_every_bus(bursts_log):
    bursts = canlib.payload_bursts(bursts_log, FRAME_300, gap=GAP)
    assert [b.payload[0] for b in bursts] == [0xAA, 0xBB, 0xCC, 0xCC, 0xDD]


def test_payload_bursts_for_an_absent_frame(bursts_log):
    assert canlib.payload_bursts(bursts_log, 0x999, gap=GAP) == []


def test_burst_compares_and_hashes_by_value(bursts_log):
    first = canlib.payload_bursts(bursts_log, FRAME_300, gap=GAP, bus=0)[0]
    again = canlib.payload_bursts(bursts_log, FRAME_300, gap=GAP, bus=0)[0]
    assert first == again
    assert len({first, again}) == 1


# --------------------------------------------------------------------------
# payloads_only_in_windows
# --------------------------------------------------------------------------
def test_payloads_only_in_windows_finds_a_confined_state(savvycan_log):
    # Frame B holds MU_C at 4 ms and 5 ms and MU_D at 6 ms.
    only = canlib.payloads_only_in_windows(savvycan_log, FRAME_B, [(0.0059, 0.0061)])
    assert list(only) == [MU_D]


def test_payloads_only_in_windows_excludes_a_state_also_seen_outside(savvycan_log):
    # A window covering MU_C's second occurrence only: MU_C still appears at
    # 4 ms outside the window, so it is not window-only.
    only = canlib.payloads_only_in_windows(savvycan_log, FRAME_B, [(0.0045, 0.0061)])
    assert list(only) == [MU_D]


def test_payloads_only_in_windows_for_an_absent_frame(savvycan_log):
    assert canlib.payloads_only_in_windows(savvycan_log, 0x999, [(0.0, 1.0)]).size == 0


def test_payloads_only_in_windows_with_no_windows(savvycan_log):
    assert canlib.payloads_only_in_windows(savvycan_log, FRAME_B, []).size == 0


def test_payloads_only_in_windows_min_hits_requires_a_sustained_state(bursts_log):
    # Only the AA run falls inside this window, and it is three messages long.
    window = [(0.00095, 0.00125)]
    assert list(canlib.payloads_only_in_windows(
        bursts_log, FRAME_300, window)) == [_muid(0xAA)]
    assert list(canlib.payloads_only_in_windows(
        bursts_log, FRAME_300, window, min_hits=3)) == [_muid(0xAA)]
    assert canlib.payloads_only_in_windows(
        bursts_log, FRAME_300, window, min_hits=4).size == 0


def test_payloads_only_in_windows_rejects_min_hits_below_one(bursts_log):
    with pytest.raises(ValueError, match="min_hits"):
        canlib.payloads_only_in_windows(bursts_log, FRAME_300, [(0.0, 1.0)], min_hits=0)


# --------------------------------------------------------------------------
# frames_with_window_only_payloads
# --------------------------------------------------------------------------
def test_frames_with_window_only_payloads(savvycan_log):
    results = canlib.frames_with_window_only_payloads(
        savvycan_log, [(0.0059, 0.0061)], threshold=10)
    assert results == [(FRAME_B, 1, 2)]


def test_frames_with_window_only_payloads_respects_the_threshold(savvycan_log):
    assert canlib.frames_with_window_only_payloads(
        savvycan_log, [(0.0059, 0.0061)], threshold=1) == []


def test_frames_with_window_only_payloads_needs_an_overlap(savvycan_log):
    assert canlib.frames_with_window_only_payloads(
        savvycan_log, [(10.0, 11.0)], threshold=10) == []


def test_frames_with_window_only_payloads_threads_min_hits(bursts_log):
    window = [(0.00095, 0.00125)]
    assert canlib.frames_with_window_only_payloads(
        bursts_log, window, threshold=10, min_hits=3) == [(FRAME_300, 1, 4)]
    assert canlib.frames_with_window_only_payloads(
        bursts_log, window, threshold=10, min_hits=4) == []

"""Burst clustering and the window-confined-payload searches."""

import numpy as np

import canlib

FRAME_A = 0x123
FRAME_B = 0x200
MU_D = 0xAABBCCDDEEFF1123


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

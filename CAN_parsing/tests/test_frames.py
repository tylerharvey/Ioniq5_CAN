"""Frame indexing, series extraction and the payload-state searches."""

import numpy as np
import pytest

import canlib

FRAME_A = 0x123
FRAME_B = 0x200
# The three distinct payloads in the SavvyCAN fixture.
MU_A = 0x0102030405060708
MU_B = 0x0102030405060709
MU_C = 0xAABBCCDDEEFF1122
MU_D = 0xAABBCCDDEEFF1123


# --------------------------------------------------------------------------
# Indexing
# --------------------------------------------------------------------------
def test_frame_indices(savvycan_log):
    assert list(canlib.frame_indices(savvycan_log, FRAME_A)) == [0, 1, 2, 6]
    assert list(canlib.frame_indices(savvycan_log, FRAME_B)) == [3, 4, 5]
    assert list(canlib.frame_indices(savvycan_log, FRAME_B, bus=0)) == [4, 5]
    assert list(canlib.frame_indices(savvycan_log, 0x999)) == []


def test_iter_frames_is_sorted_by_id(savvycan_log):
    assert [frame_id for frame_id, _indices in canlib.iter_frames(savvycan_log)] == [
        FRAME_A, FRAME_B]


def test_frame_series_is_sorted_by_time(savvycan_log):
    times, payloads = canlib.frame_series(savvycan_log, FRAME_A)
    assert times == pytest.approx([0.0005, 0.001, 0.002, 0.003])
    assert payloads.shape == (4, 8)
    assert list(canlib.pack_muids(payloads)) == [MU_A, MU_A, MU_A, MU_B]


def test_frame_series_can_return_raw_timestamps_and_hex(savvycan_log):
    raw_times, hex_payloads = canlib.frame_series(
        savvycan_log, FRAME_A, unit=canlib.UNIT_RAW, hex=True)
    assert list(raw_times) == [500, 1000, 2000, 3000]
    assert hex_payloads.dtype == np.dtype("U2")
    assert list(hex_payloads[0]) == ["01", "02", "03", "04", "05", "06", "07", "08"]


def test_frame_series_rejects_an_unknown_unit(savvycan_log):
    with pytest.raises(ValueError, match="unit"):
        canlib.frame_series(savvycan_log, FRAME_A, unit="minutes")


def test_frame_series_of_an_absent_frame(savvycan_log):
    times, payloads = canlib.frame_series(savvycan_log, 0x999)
    assert times.size == 0
    assert payloads.shape == (0, 8)


def test_all_and_unique_messages_for_frame(savvycan_log):
    assert canlib.all_messages_for_frame(savvycan_log, FRAME_B).shape == (3, 8)
    unique = canlib.unique_messages_for_frame(savvycan_log, FRAME_A)
    assert list(canlib.pack_muids(unique)) == [MU_A, MU_B]
    unique_hex = canlib.unique_messages_for_frame(savvycan_log, FRAME_A, hex=True)
    assert list(unique_hex[1]) == ["01", "02", "03", "04", "05", "06", "07", "09"]


# --------------------------------------------------------------------------
# Transitions
# --------------------------------------------------------------------------
def test_value_transitions_reports_the_new_value_position():
    indices, times, before, after = canlib.value_transitions(
        np.array([0.0, 1.0, 2.0, 3.0]), np.array([7, 7, 9, 9]))
    assert list(indices) == [2]
    assert list(times) == [2.0]
    assert list(before) == [7]
    assert list(after) == [9]


def test_value_transitions_handles_short_input():
    indices, times, before, after = canlib.value_transitions(np.array([1.0]), np.array([5]))
    assert indices.size == times.size == before.size == after.size == 0


# --------------------------------------------------------------------------
# Payload-state searches
# --------------------------------------------------------------------------
def test_unique_payload_counts(savvycan_log):
    counts = {frame_id: count
              for frame_id, _indices, count in canlib.unique_payload_counts(savvycan_log)}
    assert counts == {FRAME_A: 2, FRAME_B: 2}


def test_unique_payload_counts_skips_frames_absent_from_the_bus(savvycan_log):
    counts = {frame_id: count
              for frame_id, _indices, count in canlib.unique_payload_counts(savvycan_log, bus=1)}
    assert counts == {FRAME_B: 1}


def test_frame_ids_with_message_changes(savvycan_log):
    assert canlib.frame_ids_with_message_changes(savvycan_log) == [[FRAME_A, 2], [FRAME_B, 2]]


def test_limited_unique_frames_respects_the_threshold(savvycan_log):
    assert canlib.limited_unique_frames(savvycan_log, threshold=2) == [(FRAME_A, 2), (FRAME_B, 2)]
    assert canlib.limited_unique_frames(savvycan_log, threshold=1) == []


def test_frames_with_muids_lists_every_state(savvycan_log):
    frames = canlib.frames_with_muids(savvycan_log)
    assert frames == [canlib.FrameMuid(FRAME_A, MU_A), canlib.FrameMuid(FRAME_A, MU_B),
                      canlib.FrameMuid(FRAME_B, MU_C), canlib.FrameMuid(FRAME_B, MU_D)]


def test_frames_with_muids_rejects_by_payload_id(savvycan_log):
    frames = canlib.frames_with_muids(savvycan_log, reject_muids=[MU_A, MU_D])
    assert frames == [canlib.FrameMuid(FRAME_A, MU_B), canlib.FrameMuid(FRAME_B, MU_C)]


def test_frames_with_muids_in_range_requires_a_confined_state(savvycan_log):
    # Ranges here are in the log's raw timestamp unit (microseconds).
    # State MU_A occurs at 1000, 2000 and 500 us, so it is not confined to
    # (1500, 3500); MU_B occurs only at 3000 us and is.
    frames = canlib.frames_with_muids_in_range(savvycan_log, [1500, 3500])
    assert frames == [canlib.FrameMuid(FRAME_A, MU_B)]


def test_frames_with_muids_in_range_can_require_only_one_occurrence(savvycan_log):
    # With only_within_range=False a state just has to appear inside the range
    # while the frame shows at least one other state, so both of frame A's
    # states qualify here (MU_A at 2000 us, MU_B at 3000 us).
    inside = canlib.frames_with_muids_in_range(savvycan_log, [1500, 3500],
                                               only_within_range=False)
    assert inside == [canlib.FrameMuid(FRAME_A, MU_A), canlib.FrameMuid(FRAME_A, MU_B)]
    outside = canlib.frames_with_muids_in_range(savvycan_log, [10, 20],
                                                only_within_range=False)
    assert outside == []


def test_frames_with_muids_in_range_respects_reject_and_threshold(savvycan_log):
    assert canlib.frames_with_muids_in_range(savvycan_log, [1500, 3500],
                                             reject_muids=[MU_B]) == []
    # threshold=2 skips any frame with 2 or more distinct payloads
    assert canlib.frames_with_muids_in_range(savvycan_log, [1500, 3500],
                                             threshold=2) == []


def test_interesting_timestamps_uses_the_raw_unit(savvycan_log):
    # The largest payload jump of frame A is at 2000 us (A -> B at 3000, but
    # the biggest |diff| lands on the first change).
    assert list(canlib.interesting_timestamps(savvycan_log, [FRAME_A])) == [2000]
    # frames absent from the log are skipped
    assert list(canlib.interesting_timestamps(savvycan_log, [0x999])) == []


def test_intersect_all():
    assert list(canlib.intersect_all([[1, 2, 3], [2, 3, 4], [3, 4, 5]])) == [3]
    assert list(canlib.intersect_all([[1, 2]])) == [1, 2]
    with pytest.raises(ValueError):
        canlib.intersect_all([])


# --------------------------------------------------------------------------
# FrameMuid
# --------------------------------------------------------------------------
def test_frame_muid_orders_and_hashes_like_a_tuple():
    first = canlib.FrameMuid(1, 5)
    second = canlib.FrameMuid(1, 6)
    third = canlib.FrameMuid(2, 0)
    assert first < second < third
    assert sorted([third, first, second]) == [first, second, third]
    assert len({first, canlib.FrameMuid(1, 5)}) == 1
    assert str(first) == "Frame ID: 1; MUID: 5"

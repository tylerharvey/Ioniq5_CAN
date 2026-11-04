"""Report-side helpers of ``highlight_discrete_signals``.

The report names the bus beside every frame id: the muid tier already knows its
bus (it is split per bus), while the DBC tier decodes one frame across all of
its buses and has to look them up.
"""

import highlight_discrete_signals as highlight


def test_frame_buses_lists_the_buses_a_frame_appears_on(panda_log):
    # panda fixture: 0x123 on bus 0, 0x200 on bus 2
    assert highlight.frame_buses(panda_log, 0x123) == [0]
    assert highlight.frame_buses(panda_log, 0x200) == [2]


def test_frame_buses_is_empty_for_an_absent_frame(panda_log):
    assert highlight.frame_buses(panda_log, 0x999) == []


def test_bus_label_names_one_or_several_buses():
    assert highlight.bus_label([1]) == "bus 1"
    assert highlight.bus_label([0, 2]) == "bus 0,2"

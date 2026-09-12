"""Shared paths and log fixtures for the canlib tests."""

from pathlib import Path

import pytest

import canlib

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = TESTS_DIR.parent
REPO_DIR = PACKAGE_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
GOLDEN_DIR = TESTS_DIR / "golden"
LOG_DIR = REPO_DIR / "CAN_logs"
DBC_DIR = Path.home() / "Packages" / "egmpdbc"
REAL_DBCS = ("ioniq5-2022.dbc", "ev6-2024.dbc", "ioniq6-2023-2025.dbc")


def fixture_log(name: str) -> str:
    return str(FIXTURES_DIR / name)


@pytest.fixture
def savvycan_log() -> canlib.CanLog:
    """The seven-row SavvyCAN fixture (two buses, a reset, short hex bytes)."""
    return canlib.load_log(fixture_log("savvycan_small.csv"))


@pytest.fixture
def panda_log() -> canlib.CanLog:
    """The four-row panda fixture (buses 0 and 2)."""
    return canlib.load_log(fixture_log("panda_small.csv"))


@pytest.fixture
def bursts_log() -> canlib.CanLog:
    """Frame 0x300 as three payload runs: AA x3, BB x2, then CC, CC, and a DD
    on bus 1.  Used by the burst and window helpers."""
    return canlib.load_log(fixture_log("savvycan_bursts.csv"))


@pytest.fixture
def bits_log() -> canlib.CanLog:
    """Frame 0x100, whose byte 0 goes 00 -> 01 -> 01 and byte 1 goes
    0F -> 00 -> 00, plus a frame 0x150 absent from the background fixture."""
    return canlib.load_log(fixture_log("savvycan_bits.csv"))


@pytest.fixture
def bits_background() -> canlib.CanLog:
    """Frame 0x100 held at all-zero, plus an unrelated frame 0x200."""
    return canlib.load_log(fixture_log("savvycan_bits_background.csv"))

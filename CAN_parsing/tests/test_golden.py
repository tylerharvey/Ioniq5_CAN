"""Golden-output tests.

The goldens in ``tests/golden`` were captured from the pre-refactor
``parsing_lib``-based scripts (see ``MIGRATION.md``), so these tests pin the
report byte-for-byte: any refactor that changes what a log reports has to be a
deliberate, visible change.

The subset test runs in a few seconds.  The whole-corpus test is marked
``slow`` and is deselected by default; run it with ``pytest -m slow``.
"""

import contextlib
import gzip
import io

import pytest

import condition_mode_analysis as condition_mode
import highlight_discrete_signals as highlight
from conftest import GOLDEN_DIR, LOG_DIR, PACKAGE_DIR, REPO_DIR

missing_corpus = pytest.mark.skipif(
    not LOG_DIR.exists(), reason="CAN_logs corpus is not present")


def _capture(func, *args):
    """Run `func` capturing stdout, returning ``(output, return_value)``."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = func(*args)
    return buffer.getvalue(), result


def _golden(name: str) -> str:
    return (GOLDEN_DIR / name).read_text()


def _subset_logs():
    lines = (GOLDEN_DIR / "subset_logs.txt").read_text().split()
    return [str(REPO_DIR / line) for line in lines]


@missing_corpus
def test_highlight_subset_matches_golden():
    output, return_code = _capture(highlight.main, ["--logs", *_subset_logs()])
    assert return_code == 0
    assert output == _golden("highlight_subset.txt")


@missing_corpus
@pytest.mark.slow
def test_highlight_all_logs_matches_golden():
    output, return_code = _capture(highlight.main, ["--logs", str(LOG_DIR)])
    assert return_code == 0
    with gzip.open(GOLDEN_DIR / "highlight_all_logs.txt.gz", "rt") as handle:
        expected = handle.read()
    assert output == expected


@missing_corpus
def test_condition_mode_matches_golden(monkeypatch):
    # The script's LOGS entries are relative to this package directory.
    monkeypatch.chdir(PACKAGE_DIR)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        for path in condition_mode.LOGS:
            condition_mode.report(path)
    assert buffer.getvalue() == _golden("condition_mode.txt")

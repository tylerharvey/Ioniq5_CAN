# CAN_parsing

Offline analysis of the CAN logs captured for the Ioniq 5 / E-GMP
preconditioning work: load SavvyCAN and panda CSV logs, find control signals,
decode them against a DBC, and name individual bits in frames that have no DBC
entry yet.

This is the notebook work (`parsing_*.ipynb`) extracted into a library and two
command line tools. The rest of the notebooks were **not** migrated: they sit in
`archived_notebooks/` and still import the removed `parsing_lib`. One has been
ported back as a worked example — `parsing_utility_mode.ipynb`, the "utility
mode" session — and reproduces its archived results cell for cell. See
[MIGRATION.md](MIGRATION.md) for the name map and the deliberate behaviour
changes, and `archived_notebooks/README.md` for why the rest are frozen.

## Install and run

Nothing needs installing to run the tools from this directory:

```sh
cd ~/Packages/Ioniq5_CAN/CAN_parsing
~/main_venv/bin/python highlight_discrete_signals.py --logs ../CAN_logs/
~/main_venv/bin/python highlight_bits.py observed door.csv background*.csv --bus 0
```

Installing adds console scripts and makes `import canlib` work from anywhere:

```sh
pip install -e .
highlight-discrete-signals --logs ../CAN_logs/
highlight-bits invariant drive.csv 50.0-65.0 69.0-79.0
```

`numpy` is the only hard dependency. `cantools` is needed for `canlib.dbc` and
so for `highlight_discrete_signals.py`; `matplotlib` for `--plot`; `pytest` for
the tests. All are already in `~/main_venv`. `import canlib` deliberately does
not import cantools, so the core package stays numpy-only.

```sh
~/main_venv/bin/python -m pytest          # unit + subset golden, ~40 s
~/main_venv/bin/python -m pytest -m slow  # also all 45 logs, ~70 s
```

## Layout

| path | contents |
|---|---|
| `canlib/encoding.py` | packed payload ids (muids) and hex formatting |
| `canlib/log.py` | `CanLog`, and the SavvyCAN / panda CSV loaders |
| `canlib/frames.py` | index a log by frame id; the payload-state searches |
| `canlib/discrete.py` | payload bursts and the window-confined-payload searches |
| `canlib/bits.py` | per-byte bit masks and the `observed` / `invariant` comparisons |
| `canlib/dbc.py` | cantools DBC loading, merging and discrete-signal decoding |
| `highlight_discrete_signals.py` | the DBC signal + payload-state report |
| `highlight_bits.py` | the bit-level CLI (`observed`, `invariant`) |
| `condition_mode_analysis.py` | the one-off 0x0C7 conditioning-mode study |
| `parsing_utility_mode.ipynb` | the "utility mode" reverse-engineering session, ported to `canlib` |
| `archived_notebooks/` | the pre-refactor notebooks, kept for reference; they do not run |
| `tests/` | pytest suite, fixtures, and the golden outputs |

## Quick start

```python
import canlib

log = canlib.load_log("../CAN_logs/panda/I-CAN_car_in_D.csv")
len(log)              # 12386
log.fmt               # 'panda'
log.messages          # (12386, 8) uint8 payloads
log.bus               # uint8; only bus 0 in this log
log.time_s            # float64 seconds
log.muids             # packed payload id per row, computed on first use

times, payloads = canlib.frame_series(log, 0x38)        # one frame, chronological
canlib.limited_unique_frames(log, threshold=10)         # control-signal candidates
canlib.frame_ids_with_message_changes(log)
canlib.payload_bursts(log, 0x4C5, gap=0.2)              # runs of identical payload
canlib.bits_only_in(log, other_log, bus=0)              # bits with no DBC entry
```

Every "search" helper takes `bus=` and keys on frame id, so the same id on two
buses is pooled unless you say otherwise.

### Timestamps are not always seconds

`log.timestamps` keeps the file's own unit — integer **microseconds** for
SavvyCAN logs, float **seconds** for panda logs. The notebooks' arithmetic
(`±500000`, `5e6` buffers) and the raw-unit range argument of
`frames_with_muids_in_range` rely on that, so it was left alone. Everything
else wants `log.time_s`, which is seconds either way. Helpers that take or
return times (the `unit=` and `window=` arguments, `payloads_only_in_windows`,
`payload_bursts`) document which they use; nothing else should assume one.

## `highlight_discrete_signals.py`

Finds *discrete* signals: signals that take a small set of distinct values and
jump between them at a handful of timestamps. Physical sensors vary too
continuously to qualify, so this filters them out — it is the signal-level
analogue of the whole-payload "control signal" search the notebooks do.

```sh
# every log under ../CAN_logs, merged DBCs from ~/Packages/egmpdbc
~/main_venv/bin/python highlight_discrete_signals.py --logs ../CAN_logs/

# one log, one DBC, machine-readable results as well
~/main_venv/bin/python highlight_discrete_signals.py \
    --dbc ~/Packages/egmpdbc/ioniq5-2022.dbc \
    --logs ../CAN_logs/panda/M-CAN_panda_nothing_on_remote_lock.csv \
    --json /tmp/results.json
```

| flag | meaning |
|---|---|
| `--dbc DBC` | DBC to decode with; repeatable. Defaults to the three E-GMP DBCs (`ioniq5-2022`, `ev6-2024`, `ioniq6-2023-2025`) merged first-wins |
| `--logs PATH...` | files or directories; directories are searched recursively for `*.csv`. Default `../CAN_logs` |
| `--threshold N` | max distinct values for a signal to count as discrete (default 10) |
| `--min-changes N` | min transitions before a signal is reported (default 1) |
| `--clean-timestamps` | truncate each log at its first timestamp reset. Off by default: these logs restart their capture mid-file and truncating loses the first segment |
| `--json FILE` | also write the full results (including every transition) as JSON |
| `--plot` | plot each interesting frame's payload state over time (needs a display) |
| `--id ID` | print every payload of one frame id, with the gap to the previous one |

Two tiers are reported per log. Frames that are in the DBC get their signals
decoded and each signal is checked for a small distinct-value count; frames that
are **not** in the DBC fall back to whole-payload granularity, where a limited
number of distinct payloads is the same signal of interest. ISO-TP and VIN
frames are excluded as protocol noise.

```
==============================================================================
LOG: M-CAN_panda_nothing_on_remote_lock.csv
  dbc : ioniq5-2022.dbc
  title metadata keywords: remote_lock | nothing_on
==============================================================================

DBC signal-level discrete changes (decoded via cantools):

  * 0x151 BMS_10_100ms_1
      DATA  [8 distinct [...]; 7 change(s)]
          t=      0.04s  731835801130390344 -> 731835801130538237
          ...

muid fallback frames (limited distinct payloads, not in DBC):
  * 0x405  3 payload(s)  changes at: 0.1s, 0.2s
  ...
  * 0x4F1  2 payload(s)  changes at: 0.1s

  METADATA VERIFIED:
    [OK ] expected 0x405: found
    [OK ] expected 0x411: found

==============================================================================
SUMMARY
==============================================================================
  M-CAN_panda_nothing_on_remote_lock.csv                                 disc=31  muid=10  0x405:OK,0x411:OK
```

The log's **file name is used as metadata**. A keyword → expected-frame table
(`TITLE_EXPECTATIONS` in the script) says which frames a log named
`..._remote_lock...` ought to show, and each is annotated `OK`/`!!` so a whole
corpus can be checked at a glance. Frames that should be *absent* are
special-cased: a `no_preconditioning` log is not expected to show `0x2AD`, and
the GV60 logs carry an extended preconditioning id that the standard M-CAN ids
are replaced by.

## `highlight_bits.py`

Names individual bits in frames that have no DBC entry, which is the step
before writing a DBC entry for them. Ported from the panda examples in
`~/Packages/archive/animatronic_panda/examples/`; see
[panda_port.md](panda_port.md) for the full write-up and worked examples.

```sh
# bits the door capture shows that the background captures never do
~/main_venv/bin/python highlight_bits.py observed door.csv background-1.csv background-2.csv --bus 0

# bits that are constant and opposite across two stretches of one drive
~/main_venv/bin/python highlight_bits.py invariant drive.csv 50.0-65.0 69.0-79.0 --bus 0
```

| mode | what it compares | when |
|---|---|---|
| `observed` | a capture containing a stimulus against one or more background captures | you can record "with the thing" and "without the thing" |
| `invariant` | two time windows of a single log | you only have one drive, and can point at a stretch where a signal is known low and another where it is known high |

`observed` reports bits that are set somewhere in the interesting capture and
never set in any background, plus the reverse; `invariant` reports bits that
are clear in *every* sample of one window and set in *every* sample of the
other. They are genuinely different questions — a bit that is sometimes set is
in neither `invariant` mask — so a bit that only appears when the stimulus
starts will show up in `observed` but not in `invariant` unless it is held.

`invariant` needs the signal to be constant across each window, so the windows
have to be chosen honestly (the original write-up suggests a 10 second stretch,
identified from a video marker). `--min-rows N` skips frames seen fewer than N
times in a window; the default of 1 only skips frames absent from it.

```sh
~/main_venv/bin/python highlight_bits.py observed \
    tests/fixtures/savvycan_bits.csv tests/fixtures/savvycan_bits_background.csv --bus 0
```

```
observed: savvycan_bits.csv vs 1 background log  [bus 0]
  1 frame with differing bits, 1 frame id not in the background

new frame 0x150
id 0x100  byte 0  bit 0  mask 0x01  new one
id 0x100  byte 1  bits 0-3  mask 0x0F  new one
```

A door-bit run instead reads `id 0x820  byte 2  bit 1  mask 0x02  new one` —
the `observed` equivalent of the original tool's
`id 820 new one at byte 2 bitmask 2`.

Each line names the byte, the individual bits, the raw mask to search for in
Cabana, and the direction in words (`new one`/`new zero` for `observed`,
`0 -> 1`/`1 -> 0` for `invariant`). Extra flags: `--bus N` on both modes, and
`--id 0x1BE` (repeatable) to restrict `invariant` to particular frames.

## `condition_mode_analysis.py`

A one-off study rather than a general tool: it finds bus-0 (car-side) responses
to the 0x0C7 conditioning-mode requests in
`../CAN_logs/WiCAN_MITM/M-CAN_MITM_condition_mode_*.csv`, by aligning bus-0 byte
transitions to the request bursts and checking which payload states appear only
while preconditioning is enabled or only while it is disabled. Run it with no
arguments.

## Tests

```sh
~/main_venv/bin/python -m pytest          # 137 tests, ~40 s
~/main_venv/bin/python -m pytest -m slow  # + the 45-log golden, ~70 s
```

The golden outputs in `tests/golden/` were captured from the **pre-refactor**
scripts, so they pin the reports byte-for-byte: a refactor that changes what a
log reports has to be a deliberate, visible change. `tests/golden/highlight_all_logs.txt.gz`
covers every log in `../CAN_logs` and is behind the `slow` marker.

## Further reading

| document | contents |
|---|---|
| [MIGRATION.md](MIGRATION.md) | `parsing_lib` → `canlib` name map, how to migrate a notebook, and every deliberate behaviour change |
| [panda_port.md](panda_port.md) | the bit-level tools: what was ported, the two modes with worked examples, and what changed |
| `status_update_untracked.md` | running log of how the discrete-signal search was built and verified |

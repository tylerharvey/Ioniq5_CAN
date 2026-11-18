# What is this?

These are drawings of wiring harnesses manufactured for and sold by our shop. At the moment, all drawings are copies **as sent to the manufacturer** and not **as-manufactured**, except [the two-CAN ICU-H harness](./ICU-H_dongle_separable_2CAN_001-2.yml). This one has **as-manufactured** connector part numbers in places where the drawing allowed for choice by the manufacturer. We will eventually include both copies of each drawing, but need to find the least confusing way to organize this.

# Pinouts

These wiring harnesses use the Hyundai service manual connector pinout numbering scheme. In the case of the OBD port, this is backwards from the most commonly used numbering scheme, including the numbering scheme we use for labeling WiCAN pins, which we adopted from the WiCAN designer. Please keep this in mind and translate pin numbers appropriately.

The two schemes describe the same 16 physical pins:

- **WiCAN plug numbering** is standard J1962. On the WiCAN's male plug face, the top row is 8 7 6 5 4 3 2 1 (left to right) and the bottom row is 16 15 14 13 12 11 10 9. This is the numbering used by the stock WiCAN-OBD-C3 [reference graphic](https://user-images.githubusercontent.com/94690098/182854687-911bae04-9bdd-4947-8363-e088e278b3b8.png) and by the firmware comments.
- **Harness socket numbering** is the Hyundai service-manual numbering used in the harness drawings. It runs the other way around the same face: harness socket pin 1 is the pin that mates WiCAN plug pin 8, harness socket pin 9 is the pin that mates WiCAN plug pin 16, and so on.

## Converting between the two schemes

Use this table when reading a harness drawing and comparing it with a WiCAN pin number. The top row sums to 9 (`harness N + plug N = 9`); the bottom row sums to 25 (`harness N + plug N = 25`).

| WiCAN plug | Harness socket |
|---:|---:|
| 1 | 8 |
| 2 | 7 |
| 3 | 6 |
| 4 | 5 |
| 5 | 4 |
| 6 | 3 |
| 7 | 2 |
| 8 | 1 |
| 9 | 16 |
| 10 | 15 |
| 11 | 14 |
| 12 | 13 |
| 13 | 12 |
| 14 | 11 |
| 15 | 10 |
| 16 | 9 |

For example, the stock WiCAN-OBD-C3 labels CAN-H on plug 6 and CAN-L on plug 14. On a harness socket, those are pins 3 and 11. The stock graphic's +V on plug 16 is harness socket pin 9.

### Why the connector pictures look different

The harness drawings use two different OBD pictures:

- `M-CAN_dongle_009` uses a **rear (wire-in side)** view of the female socket, numbered 1–8 across the top and 9–16 across the bottom. That picture matches the harness numbering used in its pin table.
- `ICU-H_dongle_separable_2CAN_001-2` uses a **front (mating side)** view, numbered 8–1 across the top and 16–9 across the bottom. That picture matches the WiCAN/standard plug numbering, not the harness numbering used in its pin table.

In both cases the pin table beside the connector is the authoritative harness numbering. Do not read numbers off the picture unless you know which view it is.

## WiCAN-EB-FD-S3 pinout

![WiCAN-EB-FD-S3 OBD-II plug pinout](./WiCAN-EB-FD-S3_pinout.png)

[Open the SVG](./WiCAN-EB-FD-S3_pinout.svg) if you want to edit the drawing.

The EB-FD-S3 uses both OBD-II rows. Its complete pinout is:

| Function | WiCAN plug | Harness socket | Notes |
|---|---:|---:|---|
| CAN 0 H | 6 | 3 | M-CAN, rest-of-car side |
| CAN 0 L | 14 | 11 | |
| CAN 1 H | 12 | 13 | M-CAN, head-unit side |
| CAN 1 L | 13 | 12 | |
| +12 V main | 16 | 9 | `PWR_12V_1`; main supply |
| +12 V car-on | 8 | 1 | `PWR_12V_7`; hot in ON/START; also the car-on sense input |
| GND | 4, 5 | 4, 5 | both pins are ground |
| Not connected | 1, 2, 3, 7, 9, 10, 11, 15 | — | |

Points that are easy to get wrong:

- **There are two +12 V pins.** Plug 16 (harness 9, `PWR_12V_1`) is the main supply. Plug 8 (harness 1, `PWR_12V_7`) is a second, hot-when-car-on feed; the firmware reads it through a divider as the car-on sense. The stock WiCAN-OBD-C3 graphic only shows +V on plug 16, so it does not show plug 8 at all.
- **There are two CAN interfaces.** CAN 0 is on the standard 6/14 pair. CAN 1 is on 12/13 (harness 13/12), not on 3/11. The two interfaces are independent: CAN 0 connects to the rest of the M-CAN, CAN 1 connects only to the head unit.
- **Both 4 and 5 are ground.** The stock WiCAN graphic labels only pin 5 as ground. The EB-FD-S3 harnesses ground both.
- **Pins 12 and 13 are NOT CAN 0.** On the stock WiCAN-OBD-C3 they are unused; on the EB-FD-S3 they are CAN 1.

## Which harness supplies what

### Head-unit harness (`M-CAN_dongle_*`)

This is the harness whose OBD2 pinout matches the EB-FD-S3 exactly. It connects at the AVN M05-B connector, breaks the M-CAN, and brings both sides back to the OBD socket:

| EB-FD-S3 function | WiCAN plug | Harness socket | Source in `M-CAN_dongle_009.yml` |
|---|---:|---:|---|
| CAN 0 H/L | 6/14 | 3/11 | M-CAN rest-of-car side |
| CAN 1 H/L | 12/13 | 13/12 | M-CAN head-unit side |
| +12 V main | 16 | 9 | `PWR_12V_1` |
| +12 V car-on | 8 | 1 | `PWR_12V_7` |
| GND | 4/5 | 4/5 | `SGND` |

Both +12 V pins are fed from the AVN connector: socket 9 is the OBD2 `PWR_12V_1` main feed, and socket 1 is the `PWR_12V_7` car-on feed (AVN pin 33). The harness also contains the shunt/termination network for the M-CAN.

### Selectable-CAN harness -- ICU (`ICU-H_dongle_separable_2CAN_001-2`)

This harness connects at the ICU-H connector. Its OBD2 pinout is **not** the same as the EB-FD-S3's:

| ICU-H drawing label | Harness socket | WiCAN plug | Wired in 001-2? | EB-FD-S3 function |
|---|---:|---:|---|---|
| CAN (H/L) | 3/11 | 6/14 | yes | CAN 0 H/L |
| CAN2 (H/L) | 13/12 | 12/13 | yes | CAN 1 H/L |
| `PWR_12V_1` | 9 | 16 | yes | +12 V main |
| GND | 4/5 | 4/5 | yes | GND |
| — | 1 | 8 | no | +12 V car-on (unconnected) |

### Stock WiCAN-OBD-C3 comparison

| Function | Stock WiCAN-OBD-C3 | EB-FD-S3 |
|---|---|---|
| CAN H/L | plug 6/14 (harness 3/11) | CAN 0 plug 6/14 (harness 3/11) |
| +12 V | plug 16 (harness 9) | plug 16 main + plug 8 car-on (harness 9 and 1) |
| GND | plug 5 (harness 5) | plugs 4 and 5 (harness 4/5) |

## Firmware and drawing references

- `main/can.h` and `main/hw_config.h` in the EB-FD firmware (`eb-fd-combined`) document the plug-side bus assignments: CAN 0 = 6/14, CAN 1 = 12/13. The comments also state the harness socket is the mirror image (harness 1 ↔ plug 8, harness 9 ↔ plug 16).
- `M-CAN_dongle_009.yml` is the head-unit harness; `ICU-H_dongle_separable_2CAN_001-2.yml` is the selectable-CAN harness. Both use the Hyundai service-manual numbering on the OBD2 connector.
- The stock WiCAN-OBD-C3 graphic is linked in the Pinouts section above; it shows the first CAN pair and the main power pin, not the EB-FD-S3's second pair.

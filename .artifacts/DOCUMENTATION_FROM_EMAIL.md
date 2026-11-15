# Documentation notes extracted from project email

Compiled from outgoing project replies and quoted thread material, April–November 2026.  
Sanitized: personal names, email addresses, shipping/billing addresses, order numbers, payment-card digits, tax IDs, credentials, and private/unlisted store links have been removed. Public GitHub links are retained.

Technical statements are reported as stated in the correspondence. Where the email hedged (“likely”, “presumably”, “almost certainly”), the hedge is preserved. These notes are not independently verified.

## 1. Hardware and CAN interface capabilities

- **Stock hardware:** the original WiCAN, referred to in store correspondence as **WiCAN-OBD-C3**.
- **Custom hardware names:** **WiCAN-EB-S3** was used in earlier correspondence for the custom board; the production/shipping custom board is **WiCAN-EB-FD-S3**.
- **WiCAN Pro architecture:** three CAN interfaces are connected to the OBD chip and are multiplexed, usable only one at a time; a fourth CAN interface is connected directly to the ESP32 on pins **14** and **6**. Forwarding between interfaces is possible. This supports one-at-a-time addressing of multiple buses, not two buses simultaneously.
- **Custom WiCAN architecture:** two fully independent CAN interfaces. The first prototype sample had two CAN 2.0 interfaces for man-in-the-middle operation; the planned production version had one **CAN-FD** interface and one CAN 2.0 interface.
- **Custom interface requirements:** two interfaces capable of **ISO 15765-4**, **500 kbps**, with **29-bit headers**.
- **Controller details:** an early custom board used MCP2515 CAN controllers on pins **12/13**; later revisions moved to **MCP2518FD** for CAN-FD support. GPIO mapping/schematic documentation was requested from the vendor.
- **Flash/memory:** the original WiCAN has a small amount of flash storage and limits feature growth. The **WiCAN-EB-FD-S3** has flash capacity equivalent to the WiCAN Pro and is described as the future platform.
- **CAN-FD:** the new custom board can do CAN-FD. At an earlier point in the project, no CAN-FD-capable microcontroller was supplied, and CAN-FD WiCAN availability was months away. By November 2026 the **WiCAN-EB-FD-S3** was shipping.
- **Wireless/LTE path considered:** the ESPNetLink was expected in principle to talk to the WiCAN-EB-S3 over BLE. For LTE-based triggering, the payload is very small: a handful of distinct booleans plus one low-precision temperature value.
- **Power draw (reported):**
  - WiCAN original under normal use: about **30 mA**.
  - First prototype custom WiCAN in parallel mode: about **35 mA**.
  - Custom WiCAN in MITM mode: about **40 mA**.
  - Sleep mode: below **1 mA**.
  - Car off and locked after 5 minutes: about **750 mA**.
  - A known HV-battery power-draw issue exists when using the WiCAN in the normal OBD port; a community fix was referenced as PR 782 in the WiCAN firmware repository.

## 2. Harness modes and bus access

- **MITM / serial mode:** the head unit is isolated from the rest of the car and lives on the microcontroller’s network. The microcontroller forwards/decides messages. If the WiCAN fails while in serial mode, the car loses:
  - backup camera / parking-sensor display, including the reverse cross-traffic alert display (described as probably the most safety-critical loss);
  - SOC reading on the center screen;
  - the normal method of activating preconditioning.
  The car remains drivable, but this state should not be left for long.
- **Parallel mode:** the harness sits on the CAN bus like another ECU. If the WiCAN fails, the car continues normally; only the WiCAN’s functionality is lost. The beta configuration’s dash messages are flickery because the microcontroller must compete with the head unit.
- **Switching modes:** the harness can be switched between MITM and parallel in a few minutes; instructions are in `guides/harnesses/head_unit_MITM/MITM_harness_modes.pdf`.
- **Default mode:** the new **WiCAN-EB-FD-S3** defaults to MITM. MITM gives clearer dash messages and allows button reuse via double-press without triggering the standard button behavior.
- **Parallel trade-off:** in parallel mode the WiCAN can be put to sleep without blocking remote app requests to the car. In serial mode it must stay on if Bluelink requests are to work.
- **Harness families:**
  - **ICU-H** is for first-generation Ioniq 5 / EV6 only.
  - **CCU** hardware applies to the Ioniq 6 and GV60 starting in 2023, and is also shared with 2025+ Ioniq 5.
  - The **selectable CAN harness** gives physical access to all buses. It can be used for preconditioning with a WiCAN on M-CAN, but that is not the recommended setup; the dedicated head-unit harness is cleaner for MITM, though it requires more trim removal.
  - A standard EV6 has substantial hardware behind the ICU and requires removal for installation.
- **Bus roles mentioned:**
  - Preconditioning kit: **M-CAN**.
  - Door lock / remote lock commands: **B-CAN**.
  - i-Pedal: normally controlled from **B-CAN**.
  - Other features such as lane assist are likely on **E-CAN**, which is a CAN-FD bus.
  - Normal OBD port: **D-CAN**.
  - GV60 also involves **I-CAN** and **G-CAN** in the preconditioning path discussion.
- **Access limits:** with the original WiCAN, only M, B and I buses were accessible. The FD buses were deliberately avoided because they were considered risky. A Lilygo T2CAN-FD attached to a male OBD port (roughly $30) was suggested as a way to experiment with all buses.
- **Normal OBD port remains available:** the kit adds another OBD-like port with access to similar information; the car’s normal OBD port is still present.

## 3. Manual preconditioning behavior and diagnostics

- **Activation:** the preconditioning request can be mapped to several buttons. The star button should work immediately once the WiCAN is powered up.
- **Button reuse:** in MITM mode it is possible to reuse buttons with a double-press that does not activate the standard button-press behavior.
- **Battery-temperature gate:** if the battery’s minimum temperature is above **21 °C**, the BMU determines that preconditioning is not needed, and the request does not activate. This was described as the exact cause of a “nothing happens” symptom.
- **Temperature lag:** battery temperature lags outside temperature because the pack is heavy and somewhat insulated from the cabin. It can be below 21 °C even when the cabin is warm, and it takes a long time to cool at night.
- **Reported countdown symptom:** a user reported a countdown from “69–60 yds” and then three cycles of 69–60 km before shutdown. The response treated this as consistent with the high-battery-temperature case.
- **Status/error reporting:** the beta release `v4.20_eb-0.1.2-beta` added temperature monitoring in the HTTP interface. A definitive error message for the high-temperature case was planned.
- **WiCAN as an OBD dongle:** to use the WiCAN as an OBD dongle, switch its protocol to `elm327` or `autopid`, then switch back to `savvycan` for preconditioning. Documentation for this process was noted as a manual TODO.
- **Implemented telemetry:** SOC, battery minimum/maximum temperature, and car power status (reduced to “ready” / “not ready”) were implemented from broadcast ECU messages. Odometer was considered possible but not implemented and described as tricky.
- **Remote functions:** remote lock commands succeeded. The HV-battery wakeup request appears to have some security protection and had not yet been cracked. Controlling climate from an already-awake car was described as straightforward.
- **Flicker:** in the beta parallel configuration the dash messages flicker; MITM is the non-flickery configuration.

## 4. CAN reverse-engineering notes

- **Preconditioning bus:** the kit’s preconditioning traffic is on **M-CAN**.
- **GV60 architecture:** the head unit has only **I-CAN**, and the BMU is not on I-CAN. During preconditioning start, most familiar frames were not seen on M-CAN. The working hypothesis is that messages go head unit → I-CAN → G-CAN → BMU, or are structured differently and passed to M-CAN. GV60 M-CAN was observed to use **29-bit frame IDs**. GV60 CAN was described as a “Frankenstein” layout.
- **Ioniq 6 result:** with the **2AD checks disabled**, preconditioning worked on an Ioniq 6 test car. The 2AD bytes were described as almost certainly **blue coolant EWP status indicators**. For the EV6, the equivalent likely requires the correct **pink coolant flow checks**.
- **Ioniq 6 DBC work:** the Ioniq 6 is harder because fewer cars are available; checking whether a message ID differs on that car is the slow part of integrating a new signal. A community owner was sought to “own” the Ioniq 6 DBC file and validate frames from other cars.
- **DBC resources:** community DBC files are maintained at `github.com/dragz/egmpdbc/tree/testing`; the README is at `github.com/dragz/egmpdbc/blob/testing/README.md`. Ioniq 5 steering-wheel heating and seat heating had already been reverse-engineered in `ioniq5-2022.dbc` around lines 58 and 89.
- **OBD/UDS limits:** OBD requests with the kit are “kind of” supported and may be limited to ECUs on M-CAN. UDS is limited to ECUs on each bus unless using D-CAN, the normal OBD port. SOC can in principle be read on M-CAN but not on B-CAN.
- **BMS reflash:** the BMS measures SOC; communication with the CMU is analog within the battery assembly. MITM on that communication was considered possible but hacky. Reflashing BMU/BMS firmware was described as the easy path; Infineon secure boot is a barrier. UDS over CAN may be possible as dealerships do, but it may be encrypted.
- **Head-unit modification:** modifying head-unit firmware through the WiCAN was described as a roundabout alternative to Nemesis. Jacob’s fork implements turn-by-turn directions from Google Maps: `github.com/JacobPantuso/wicant-i-precondition`.

## 5. Firmware and integration notes

- The main firmware branch supports both the original WiCAN and the custom WiCAN automatically; the firmware is functionally identical between them.
- The firmware flashed onto the first custom boards was from the `eb-fd-clean-sent` branch. The latest work was in `eb-fd-combined`.
- The custom board changed after Jacob’s fork, so his fork must catch up to the new board before it can flash the new WiCAN. New board support had not yet been merged back into main.
- BLE flashing was considered convenient; PRs from community forks were welcomed.
- Numen support was not present in the firmware on the new WiCAN at the time of the swap.
- Firmware update guidance: `meatpihq.github.io/wican-fw/config/firmware-update`.
- Home Assistant integration fork for the project’s data method: `github.com/adman234/ha-wican`. On the WiCAN Pro with the selectable harness, the stock HA integration would not work out of the box.
- Code pointers mentioned for temperature monitoring: `precondition_can_rx_hook()` in `main/precondition.c#L357`, and `main/homepage_full.html`, `main/config_server.c`, `main/precondition.c`; a collaborator’s `ironiq.py#L49` also had relevant parsing.

## 6. Open questions / documentation gaps

- GV60 preconditioning path is still a hypothesis (I-CAN/G-CAN/M-CAN routing), not confirmed.
- Ioniq 6 and EV6 coolant/EWP checks need validation (2AD bytes, pink coolant flow).
- CAN-FD support and safe access to E-CAN were still being developed; FD buses were considered risky.
- Remote HV-battery wakeup security had not been cracked.
- Numen support, odometer readout, clearer preconditioning error messages, and manual documentation for the OBD-dongle protocol switch were outstanding.
- Install documentation for EV6 trim removal and OBD mounting was still being simplified.

## 7. Useful public references retained from the correspondence

- Preconditioning manual: `github.com/tylerharvey/Ioniq5_CAN/blob/main/guides/manuals/preconditioning_manual.pdf`
- MITM harness modes: `github.com/tylerharvey/Ioniq5_CAN/blob/main/guides/harnesses/head_unit_MITM/MITM_harness_modes.pdf`
- Project guides: `github.com/tylerharvey/Ioniq5_CAN/tree/main/guides`
- Firmware: `github.com/L1Z3/wicant-i-precondition`
- Firmware releases: `github.com/L1Z3/wicant-i-precondition/releases`
- Beta release: `github.com/L1Z3/wicant-i-precondition/releases/tag/v4.20_eb-0.1.2-beta`
- Firmware branches: `github.com/L1Z3/wicant-i-precondition/tree/eb-fd-clean-sent`, `github.com/L1Z3/wicant-i-precondition/tree/eb-fd-combined`
- DBC database: `github.com/dragz/egmpdbc/tree/testing`
- WiCAN firmware issue/PR context: `github.com/meatpiHQ/wican-fw/issues/708`, `github.com/meatpiHQ/wican-fw/pull/782`
- Firmware update guide: `meatpihq.github.io/wican-fw/config/firmware-update`
- Community HA integration: `github.com/adman234/ha-wican`

## 8. Verbatim excerpts from the correspondence (sanitized)

These are direct quotations. Bracketed redactions replace personal names, addresses, email addresses, order details, payment data, and unlisted store links. Ellipses mark omitted non-technical passages. Source IDs are Gmail message IDs.

### 8.1 Hardware and CAN interfaces

Source 9264:
> WiCAN PRO has 3 CAN interfaces connected to the OBD chip, these 3
> interfaces are muxed and can be used only one at a time. An additional CAN
> interface connected to main CAN (pin 14, pin 6). So you can switch the OBD
> chip to a different CAN bus and use the main bus directly in WiCAN.

Source 9264/9266:
> Yes, we just need 2 interfaces capable of ISO
> 15765-4, with 500kpbs with 29-bit headers.

Source 9915:
> The CAN pins of the MCP2515 are on pins 12 and 13 just like in your
> harness.
> We cannot swap them, we'll need to make a new prototype with the
> MCP2518FD. The good news is that you don't need to pay for it, since it's
> included as 2nd round of prototyping.

Source 9637:
> The first sample had 2 CAN 2.0 interfaces for man-in-the-middle with the
> head unit. I can't guarantee it until the next samples come out, but we're
> planning on one CAN-FD interface and one CAN 2.0 interface, which will
> allow forwarding and will also allow reverse engineering on busses besides
> M and B.

Source 10063:
> The harness with two CAN interfaces can be used with both, but it's a pain
> (and not fast) to address the second interface with the Pro through the
> multiplexer. That's why we ordered this custom WiCAN, with two fully
> independent interfaces. The Pro can be used for one-at-a-time addressing of
> multiple interfaces, e.g., auto iPedal (B-CAN) at startup and then
> preconditioning (M-CAN) while driving, but not two at once.

Source 9960:
> The new microcontroller has 2 CAN interfaces, one of which can do CAN-FD.

Source 10043:
> Why do the swap? Even if you want to operate in parallel mode, the new
> WiCAN has larger flash memory equivalent to the WiCAN Pro, so the number of
> features we can eventually fit is much higher on this one. For
> man-in-the-middle operation, messages on the dash don't flicker, and a lot
> of other nice-to-haves work better. Plus, the new WiCAN can do CAN-FD!

Source 10079:
> The only hardware update is the availability of the new WiCAN-EB-FD-S3,
> which enables MITM and has much more flash space for new features.

### 8.2 Harness modes, failure behavior, and power

Source 9504:
> In the parallel configuration, it can be configured to shut off when the
> car is off. In serial, it has to stay on if you want Bluelink requests to
> work. The WiCAN firmware has existing sleep functionality and we have plans
> to improve that (i.e. allow sleep that turns off WiFi but preserves head
> unit communication).

Source 9504:
> If the harness is in parallel mode and the WiCAN fails, nothing bad happens other than
> losing the functionality of the WiCAN. If you have the harness in serial
> mode and the WiCAN isn't forwarding, you lose a few things you're probably
> used to, a few of which are safety-related.

Source 9504:
> -backup camera/parking sensor display (including reverse cross-traffic
> alert display on head unit, probably the most safety-critical feature)
> -SOC reading on center screen
> -the normal method of activating preconditioning
> And probably a few more features. In short, your car is drivable but you
> wouldn't want to leave it like this for long at all.

Source 9504:
> There is a known HV battery power draw issue using the WiCAN for its usual purpose in the OBD port, but
> another Ioniq 5 owner has a fix out for that (
> https://github.com/meatpiHQ/wican-fw/pull/782) that should get merged soon.

Source 9608:
> It's about 30mA for the WiCAN original under normal use, 35 mA for the
> first prototype customized WiCAN in parallel mode, and 40 mA for customized
> in MITM. Sleep mode drops that under 1 mA. My car off and locked after 5
> minutes uses 750mA.

Source 9554:
> There might be a hacky way to get auto-lock by repurposing remote commands,
> but the preconditioning kit sits on a different bus (M) than door lock
> commands (B). ...
> The other things you're asking about are likely on E-CAN, which is a CAN-FD
> bus. The biggest barrier there is that we don't currently supply a
> microcontroller with CAN-FD support, but we're working hard on that.
> ... With a Lilygo T2CAN-FD attached to a male OBD port (~$30 USD), you
> can play with all of the busses--or you could wait until we can provide a
> prebuilt solution for roughly the same cost (still working out lead time on
> that).

Source 9556:
> Yeah, to be honest I felt pretty comfortable with no access to the FD
> busses because they're the ones where things could go terribly wrong. M and
> B are pretty safe to mess with and are accessible with a WiCAN original.

Source 9658:
> Unfortunately we won't have a CAN-FD WiCAN for a few months. Only M, B and I are accessible with the current one.

Source 10079:
> The default with the new WiCAN-EB-FD-S3 is MITM. The
> upside of MITM is primarily clearer user interface: the messages on the
> dash show up very nicely, and it'll be possible to re-use buttons with
> double-press that don't activate the standard button press behavior. The
> upside of parallel is that you can put the WiCAN to sleep without blocking
> remote app requests to the car.

Source 10037:
> -for quite a bit less than a WiCAN Pro, you can get our custom WiCAN with 2
> independent CAN interfaces instead of 1, as well as CAN-FD if you ever want
> that (it'll be available starting this weekend)
> -HA integration based on CAN isn't fully cooked yet in either case; one
> person has built something to bridge the gap (
> https://github.com/adman234/ha-wican) and I'd like to fork his effort and
> officially support this eventually
> -do you want fully remote (i.e. from car off) control? If so, this isn't
> fully built yet but I have a prototype working using the harness you
> ordered and our new WiCAN (strictly necessary as you need to be on both
> M-CAN and I-CAN)

Source 9966:
> It can be used for preconditioning with a WiCAN on M-CAN, but that's not the recommended setup for several reasons.
> The proper kit uses a dedicated head unit harness that allows for MITM
> (which mostly means better messages on the dash right now). It is more trim
> removal to install but overall cleaner.

Source 10013:
> I learned yesterday that the standard EV6 has a
> ton of stuff behind the ICU and absolutely requires removal for
> installation.

### 8.3 Manual preconditioning and diagnostics

Source 9726:
> That's expected with the firmware version shipped with a high battery
> temperature (>21C) such that the BMU determines you don't need
> preconditioning. I know that's not very clear, and we're working hard on
> making it better!
>
> The current beta release (
> https://github.com/L1Z3/wicant-i-precondition/releases/tag/v4.20_eb-0.1.2-beta)
> includes temperature monitoring in the HTTP interface. In a week or so we
> should have a definitive error message built for this case.

Source 9726:
> Yes! Your normal OBD port is still there. This kit adds another OBD-like
> port with access to similar information. We plan to build in a battery
> temperature display with the kit as well, but we're still working on
> that--I think we'll have that in an update available sometime in the next
> month.

Source 9727:
> This guide (point 1) has you covered.
> https://meatpihq.github.io/wican-fw/config/firmware-update
> It's remarkably easy!

Source 9654:
> Note that to use the WiCAN as an OBD dongle, you'll have to switch the protocol to 'elm327' or 'autopid', and go back to 'savvycan' for preconditioning. (I'll put on my list to add docs on this process into the manual.)
>
> Generally, the battery temp lags outside temp since it's ~1000lbs in a
> smal-ish form factor.

Source 9653:
> Was your battery minimum temperature above 21°C when you tried it? That's exactly what
> happens in that case. We're working on better messages and a battery status
> display in the http interface to make that situation less confusing.

Source 10042:
> It should immediately work on the star button once the WiCAN is powered up.

Source 9959:
> The answer is a hard "kind of" (i.e. no guarantees). I believe normal OBD
> requests are possible with the kit but I haven't poked at them much, and
> it's likely you'd be limited only to ECUs on M-CAN. Instead, we just grab
> what we need directly from the ECU messages that are constantly broadcast
> on M-CAN. Currently, we have SOC, battery min/max temperature and car power
> status (currently reduced to "ready" and "not ready") implemented. Odometer
> is probably possible, but not implemented (this one is actually very tricky
> as an OBD parameter and there have been several attempts to fix it in the
> main WiCAN repo, including by me).

Source 9959:
> while we've successfully sent remote lock commands, the HV
> battery wakeup request seems to have some amount of security on it. I think
> we will crack it, but we haven't yet. Controlling climate from an
> already-awake car is straightforward, though.

Source 10064:
> Home Assistant integration in the Pro will not work
> out of the box if you leave it on the selectable CAN harness. UDS is
> limited to ECUs on each bus unless you're on D-CAN (the normal OBD port).

### 8.4 CAN reverse engineering

Source 9375:
> boy, GV60 CAN is a
> Frankenstein. The head unit only has I-CAN, which the BMU is not on, and
> most frames we're familiar with were not on M-CAN during preconditioning
> start. So presumably on this car, preconditioning messages go head
> unit->I-CAN->G-CAN->BMU, or they're structured totally differently and
> passed to M-CAN.

Source 9375:
> [contributor] identified that GV60 M-CAN has 29-bit frame IDs.

Source 9375:
> With 2AD checks disabled, preconditioning worked on [owner redacted]'s Ioniq 6. So
> presumably it should work on the EV6 if we can do the correct pink coolant
> flow checks, and the 2AD bytes are almost certainly blue coolant EWP status
> indicators.

Source 9731:
> We really need someone to
> 'own' the Ioniq 6 DBC file (
> https://github.com/dragz/egmpdbc/blob/testing/ioniq6-2023-2025.dbc), i.e.
> check frames that work for other cars on your cars and approve them to be
> included in the Ioniq 6 profile.

Source 9732:
> it looks like at least on the Ioniq 5, steering wheel
> heating has been reverse-engineered:
> https://github.com/dragz/egmpdbc/blob/291d77152a5cb7d83bb2a6c513b38223f2a32ef3/ioniq5-2022.dbc#L58
> And seat heating:
> https://github.com/dragz/egmpdbc/blob/291d77152a5cb7d83bb2a6c513b38223f2a32ef3/ioniq5-2022.dbc#L89

Source 9732:
> i-Pedal would likely require the selectable CAN harness or a B-CAN-specific
> harness, as it's normally controlled from there.

Source 9971:
> The BMS is the ECU that measures the SOC! There is some communication with
> the CMU, but it looks like it's analog and that's all within the battery
> assembly. So, it's possible if you go MITM on that communication, but
> that's getting very hacky with it. The "easy" way is to reverse engineer
> and reflash the BMU/BMS firmware. ...
> The Infineon chips have secure boot.

Source 9976:
> In principle it's possible via CAN (UDS over CAN), as that's exactly how
> dealerships do it. But it may be transmitted encrypted, which would
> probably make it a very hacky update process.

### 8.5 Firmware, integration, and community

Source 9637:
> At the moment, we have a main firmware branch that supports both the WiCAN
> original and customized WiCAN automatically, and we expect that to
> continue. So the firmware is functionally identical between both WiCANs.

Source 10047:
> This is what's flashed:
> https://github.com/L1Z3/wicant-i-precondition/tree/eb-fd-clean-sent
> And this is the latest work on this:
> https://github.com/L1Z3/wicant-i-precondition/tree/eb-fd-combined

Source 10060:
> For that you would definitely need Nemesis! You could modify your head unit
> firmware using the WiCAN, but that's just a roundabout way to do similar
> things as Nemesis. The closest thing is [contributor]'s fork, which implements
> turn-by-turn directions from google maps (I believe):
> https://github.com/JacobPantuso/wicant-i-precondition

Source 10024:
> In principle, the ESPNetLink should be able to talk to our WiCAN-EB-S3 over
> BLE, right? ...
> The bandwidth can be
> super low as it's just a handful of distinct booleans with one temperature
> as the only low-precision number that needs to be sent.

Source 10037:
> HA integration based on CAN isn't fully cooked yet in either case; one
> person has built something to bridge the gap (
> https://github.com/adman234/ha-wican) and I'd like to fork his effort and
> officially support this eventually

### 8.6 Commercial and installation notes (sanitized)

Source 10079:
> The complete manual preconditioning kit comes with a WiCAN customized
> for our application (currently still listed as a WiCAN-OBD-C3 on Etsy as
> we're changing over next week). The head unit harness alone is
> bring-your-own-firmware-and-microcontroller.

Source 10039:
> Our custom WiCAN, the WiCAN-EB-FD-S3, is shipping from Australia and will be available
> to ship to you shortly.

Source 10037:
> -for quite a bit less than a WiCAN Pro, you can get our custom WiCAN with 2
> independent CAN interfaces instead of 1, as well as CAN-FD if you ever want
> that (it'll be available starting this weekend)

Source 9966:
> It can be used for preconditioning with a WiCAN on M-CAN, but that's not the recommended setup for several reasons.
> The proper kit uses a dedicated head unit harness that allows for MITM
> (which mostly means better messages on the dash right now). It is more trim
> removal to install but overall cleaner.

Source 10013:
> I learned yesterday that the standard EV6 has a
> ton of stuff behind the ICU and absolutely requires removal for
> installation.

### 8.7 Excluded material

> A childcare/pink-eye message and routine order/refund logistics were excluded as unrelated to the technical documentation.

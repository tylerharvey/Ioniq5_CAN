> Car, give me the grace to accept with serenity the things that cannot be changed, courage to build the buttons that Hyundai will never offer as an update, and the wisdom to distinguish the one from the other. 

# Purpose 
We have begun shipping a fully open-source Ioniq 5/6/EV6 preconditioning button that can be implemented with a hardware retrofit kit. With the kit, preconditioning is [activatable](https://youtu.be/37fBu63kVeo?si=eVobnYavg8i2hmdD) and cancelable by an [existing button](guides/manuals/preconditioning_manual.pdf) in your car. Other activation options are in development. For a brief background on battery preconditioning, see ["What is preconditioning?"](what_is_preconditioning.md). For a brief technical overview of the kit, see the [basic preconditioning kit explanation](basic_explanation.md). This repository serves to document progresss on Ioniq 5 CAN reverse-engineering and status updates on the hardware and software for the kit.
Major contributors to date:
- [Liz](https://github.com/L1Z3): firmware, CAN reverse-engineering
- [Roy](https://github.com/dragz): CAN reverse-engineering, prototyping
- [Corbin](https://www.theioniqguy.com): testing, strategy, marketing, retail, 3D printing
- [Tyler](https://github.com/tylerharvey): glue guy/productizing
- [Michaël](https://github.com/Tichael): technical review, EV6 testing

Other contributors:
- people who have contributed to install guides are specifically noted in those guides      
- [Kenny](https://www.reddit.com/user/KennyBS167/submitted/): technical review
- [Thomas](https://www.ioniqforum.com/members/thomas212.6422/): CAN reverse-engineering

Other repositories for this project: 
- [manual preconditioning firmware repository](https://github.com/L1Z3/wicant-i-precondition)
- [known CAN messages in DBC format](https://github.com/dragz/egmpdbc)
- [ESP-based DIY build](https://github.com/dragz/ironiq)

# How to Buy
We have begun shipping orders to customers. To purchase in the US, visit [ElectroniqButtons.com](https://www.electroniqbuttons.com). To purchase outside the US, buy on [Etsy](https://www.etsy.com/listing/4498059167/ioniq-56ev6gv60-manual-preconditioning). Etsy does not support HTML, so the product pages are much clearer at [ElectroniqButtons.com](https://www.electroniqbuttons.com). It's advisable to browse there first. If you have any questions not answered on the product pages, please ask us at [info@electroniqbuttons.com](mailto:info@electroniqbuttons.com). If you do make a purchase, please fill out [this email form](https://docs.google.com/forms/d/e/1FAIpQLSd8GtjELMu9Nn59Qep1Qt1Ey02MGxPplVcpOBm7KX2CQ7S9JQ/viewform?usp=header) so we know which car(s) you have.

# Structure
This kit has a few moving parts:
- CAN messages (talking to the car)
- microcontroller to inject CAN messsages (box that talks to the car)
- firmware for that microcontroller (programming for the box)
- wiring harnesss to adapt microcontroller to car (how to plug the box into the car)
- user interface (the button that triggers preconditioning)

The [CAN messages for preconditioning](preconditioning_messages/) have been documented since March 2026. We are shipping a first version of the microcontroller now, and you will have the option of a free trade-in or discounted purchase of the non-flickery customized WiCAN when it is available. The current firmware works well, and we are rapidly developing new features in firmware. The wiring harness has been extensively tested and is in bulk production, and may only slightly change in length to accommodate new installation methods. The current user interface allows for a choice of existing buttons on the car to trigger preconditioning, and we are working hard on physical buttons.

Videos of the button in action:
- [dragz triggering preconditioning from a laptop](https://youtu.be/vaBQV_6DW-M?si=8POdBs7m_WmN-vUu)
- [triggering preconditioning with star button on a panda](https://youtu.be/1I849mg2cQ4?si=igR4gxgVAqW1klbn)
- [Liz showing first UI](https://youtu.be/VzLoRYCNTqQ?si=Sd3lELZRXEixEHiz)
- [demonstration of beta kit](https://youtu.be/37fBu63kVeo?si=eVobnYavg8i2hmdD)

# Current Status
Kits have shipped to about 40 people. Liz and Tyler have had the first prototype custom WiCAN installed in their cars for over a month, and [wicant-i-precondition](https://github.com/L1Z3/wicant-i-precondition) automatically supports both wiCANs in a single main branch. We will test the second prototype shortly. Shipping of the custom WiCANs will occur in the fall. We are rapidly releasing firmware updates, so if you've purchased the kit, check [releases](https://github.com/L1Z3/wicant-i-precondition/releases/) for the latest and follow [these instructions](https://meatpihq.github.io/wican-fw/config/firmware-update/) to update your WiCAN.

We are shipping a [fork of WiCAN firmware lead by Liz](https://github.com/L1Z3/wicant-i-precondition) on stock WiCAN-OBD-C3s for the beta run. 

Roy is gathering known E-GMP CAN bus information in [DBC files](https://github.com/dragz/egmpdbc) and has [prototyped a UI](https://github.com/dragz/ironiq) based on a Lilygo T-Display S3.

# History
1. CAN messages:
   - The necessary CAN messages to initiate preconditioning on 2021-2024 E-GMP cars were isolated by Roy and I in early March 2026. 
2. microcontroller: 
   - We are using a low-cost prepackaged microcontroller to piggyback on existing work and open-source code
   - Beta test units will use a stock WiCAN-OBD-C3 initially, and receive a customized WiCAN (WiCAN-EB-S3) later
   - The customized WiCAN has been designed and is in testing now
3. firmware:
   - Liz and I (mostly Liz) have [working firmware](https://youtu.be/1I849mg2cQ4?si=igR4gxgVAqW1klbn) for one prototype microcontroller [here](https://github.com/tylerharvey/animatronic_panda)
   - Liz ported that logic to [WiCAN firmware](https://github.com/L1Z3/wicant-i-precondition)
4. wiring harness: 
   - First inventory has been ordered from one wiring harness vendor
   - We have a sample from a separate vendor as a backup in case of problems
5. user interface:
   - Liz designed logic to [activate and deactivate](https://youtu.be/3RfnEo8Xc0o?si=r9ix7-klKYVObkZd) preconditioning on star button press; a choice of mapping onto other buttons is now also possible
   - We are actively exploring physical button add-ons

# Business Info
In the spirit of keeping things open, here's some basic info about the structure of the business to date. Electroniq Buttons Boutique LLC is a US sole-member LLC fully owned by Tyler. Handshake agreements are in place to pay significant contributors from the net margin (and more of these are possible if you want to make a significant and sustained contribution). This structure was chosen for a few reasons:
- Tyler was most interested in professionally-made wiring harnesses and prebuilt microcontrollers, which are the two largest costs, and had the available capital to do this
- US LLCs are relatively easy to start; nonprofits and other structures require a lot more work on guiding documents and potentially a board of directors
- None of us expect to make big bucks; this structure is subject to change if we're very wrong about this

As of early June, the business has incurred roughly the following costs:
- at least $1150 in prototype/test expenses (e.g. WiCANs, pandas, wiring harness samples, handmade wiring harnesses, etc.)
- $7400 for inventory, including WiCAN originals (the largest cost), two wiring harnesses at the minimum order quantity, installation tools, and packaging materials; this includes the cost of development of the customized WiCAN, bundled to protect others' business details, but does not include the cost to produce or ship the customized WiCAN yet
- $500 in miscellaneous business expenses 
- $500 in various shipping costs

Roy, Liz and Tyler have committed several hundred hours in labor to date, and Michaël has also put in a lot of work on a related project that may be merged in. If all current inventory sold at currently listed prices on the Shopify or Etsy shops, after platform fees but before any taxes, the business would see about $14,500 in revenue. As we still will order customized WiCANs (expected to cost about $4000 for all beta test kits), this leaves about $1000 available to pay people for labor on the first inventory and break even. We hope to eventually make minimum wage on this project, but it may take some time! The business is cash-flow positive, so we will get there.

# Contents
Structure of this repository:
## 1. minimal working CAN messages
Two logs (in SavvyCAN format, with timestamps in microseconds) of CAN messages filtered/edited down from logs recorded using [SavvyCAN](https://github.com/collin80/SavvyCAN) and a [WiCAN Pro](https://github.com/meatpihq/wican-fw) that can be sent back to Ioniq 5s with a battery PTC heater equipped and battery preconditioning mode enabled to [initiate](preconditioning_messages/MWE_preconditioning.csv) or [cancel](preconditioning_messages/MWE_cancel_preconditioning.csv) preconditioning manually. These messages were reverse-engineered by [dragz](https://github.com/dragz) and I. See dragz's [articles](https://github.com/dragz/explorationsincarhacking/tree/main/articles) or our [Ioniqforum notes](https://www.ioniqforum.com/posts/666540/) for more documentation. 
## 2. best real logs and parsing script
I am including two real recorded logs [1](CAN_logs/M-CAN_driving_with_nav_preconditioning_at_end_cleaned.csv) and [2](CAN_logs/M-CAN_start_nav_to_EA_parked_in_D_preconditioning_cleaned.csv) that included activation of preconditioning; two real recorded logs designed as control experments using the built-in navigation but not navigating to a nearby charger [1](CAN_logs/M-CAN_driving_with_nav_to_school_no_preconditioning_including_reroute.csv) and [2](CAN_logs/M-CAN_start_nav_to_school_parked_in_D.csv); and a parsing [script](CAN_parsing/parsing_MWE.ipynb) that I retroactively edited to show the most valuable parsing steps I took to identify the minimal working examples (MWEs)
## 3. harness designs
This harness design is shipping:
![drawing 007](wiring_harness/M-CAN_dongle_shunt_caps_007-1_stamped.pdf)

I am also including the [source file](wiring_harness/M-CAN_dongle_shunt_caps_007-1.yml) used to render the drawings with [wireviz](https://github.com/wireviz/WireViz/). Wireviz was easy to learn and good for a reasonably straightforward harness, but has some limitations: 
- no built-in way to draw resistors or any other basic circuit component besides wires
- no way to directly connect a wire to a wire besides an invisible splice, which confused some vendors
## 4. guides
Written guides are available for:
- [basic use of the kit](guides/manuals/preconditioning_manual.pdf)
- [harness mode switching](guides/harnesses/head_unit_MITM/MITM_harness_modes.pdf)
- [Ioniq 5 install](guides/cars/E-GMP_gen1/Ioniq5/head_unit_preconditioning_kit_Ioniq5_install.pdf)
- [Ioniq 6 install](guides/cars/E-GMP_gen1/Ioniq5/head_unit_preconditioning_kit_Ioniq6_install.pdf)
- [EV6 install](guides/cars/E-GMP_gen1/Ioniq5/head_unit_preconditioning_kit_EV6_install.pdf)

# CAN Reverse Engineering Tips/Resources
One or two good logs is far more valuable than 10 questionable logs. I had much better success after identifying my best logs and cleaning them (e.g. out-of-range timestamps from buffered data). Think of log acqusition as a scientific experiment: you want a test and a control condition. In the case of preconditioning, that meant setting the nav to a charger nearby vs. to a school nearby. You can also tag logs with known messages, such as the star button. If all else fails, plotting temporal changes in a large range of messages can offer a lot of insight and help identify interesting frame IDs.

General CAN resources:
- [CSS electronics](https://www.csselectronics.com/pages/can-bus-simple-intro-tutorial): many helpful introductory articles on CAN
- [canbus tools](https://github.com/iDoka/awesome-canbus): a better/longer list of resources
- [SavvyLens](https://github.com/SuperSuave/SavvyLens): a fork of SavvyCAN by a member of our community, with support for signal tagging and LLM integration for help parsing
- [OVMS DBC file documentation](https://docs.openvehicles.com/en/latest/components/vehicle_dbc/docs/dbc-primer.html): basic explanation of the structure of a DBC file
- [cantools](https://github.com/cantools/cantools): python library that can easily plot CAN-based signals using DBC files
- [standalone Cabana](https://github.com/deanlee/openpilot-cabana): fork of openpilot Cabana for general-purpose CAN reverse-engineering
- [kvaser.com](https://kvaser.com/): login needed but various CAN resources available free

Related projects:
- [manual preconditioning firmware repository](https://github.com/L1Z3/wicant-i-precondition)
- [known CAN messages in DBC format](https://github.com/dragz/egmpdbc)
- [ESP-based DIY build](https://github.com/dragz/ironiq)
- [another Ioniq 5 CAN reverse engineering project](https://github.com/Sterlingarcher2525/ioniq5-can)
- [OBD reverse engineering tools built for WiCAN](https://github.com/philipkocanda/canair)
- [original Ioniq CAN reverse engineering](https://github.com/philipkocanda/ioniq-can) 
- [Hyundai Kona VESS reverse engineering](https://github.com/ereuter/vess)

# Contributing
Feel free to join the conversation on [our Fluxer community](https://fluxer.gg/w0OpDJjG) or the [Discord mirror](https://discord.gg/zKyNAfmtU). PRs are welcome for install guide changes, harness requests, or CAN parsing tools. Since CAN reverse engineering is new to most of us, many people in this community utilize large language models in various ways depending on their initial skill level. Pull requests should clearly designate the level of human and LLM authorship. 

## Rebatable Contributions from Customers
The following contributions are welcome and potentially eligible for a rebate:
- Offer suggestions or photos to improve the [manual](./guides/manuals/) or [install guides](./guides/cars/) or product descriptions:
  - Document alternate EV6 OBD mount locations
- Review automated translations of technical documentation in your language, particularly for German, Korean, Spanish and French
- Accepted pull request to [firmware repository](https://github.com/L1Z3/wicant-i-precondition) or [DBC repository](https://github.com/dragz/egmpdbc)
- Prototype physical button (note: Michaël is currently working on this; get in touch with us to avoid duplication of effort; this probably goes beyond a rebate)

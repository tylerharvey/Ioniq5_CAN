# Purpose 
I am working to take to market a fully open-source design for an Ioniq 5 preconditioning button and similar features that can be implemented with a hardware retrofit (e.g. remote climate). This repository serves to document progresss on Ioniq 5 CAN reverse-engineering and progress towards a sellable kit.

# Contents
At the moment, this repository contains:
## 1. minimal working CAN messages
two logs (in SavvyCAN format, with timestamps in microseconds) of CAN messages filtered/edited down from logs recorded using SavvyCAN that can be sent back to Ioniq 5s with a battery PTC heater equipped and battery preconditioning mode enabled to [initiate](preconditioning_messages/MWE_preconditioning.csv) or [cancel](preconditioning_messages/MWE_cancel_preconditioning.csv) preconditioning manually. These messages were reverse-engineered by [dragz](https://github.com/dragz) and I. See dragz's [articles](https://github.com/dragz/explorationsincarhacking/tree/main/articles) or our [Ioniqforum notes](https://www.ioniqforum.com/posts/666540/) for more documentation. 
## 2. best CAN message logs and parsing script used to generate the MWEs
I am including two real recorded logs [1](CAN_logs/M-CAN_driving_with_nav_preconditioning_at_end_cleaned.csv) and [2](CAN_logs/M-CAN_start_nav_to_EA_parked_in_D_preconditioning_cleaned.csv) that included activation of preconditioning; two real recorded logs designed as control experments using the built-in navigation but not navigating to a nearby charger [1](CAN_logs/M-CAN_driving_with_nav_to_school_no_preconditioning_including_reroute.csv) and [2](CAN_logs/M-CAN_start_nav_to_school_parked_in_D.csv); and a parsing [script](CAN_parsing/parsing_MWE.ipynb) that I retroactively edited to show the most valuable parsing steps I took to identify the minimal working examples (MWEs)

## 3. harness designs
I have drawings for harness designs including CAN lines:
![drawing 001 without shielded twisted pairs](wiring_harness/M-CAN_dongle_001.pdf)
![drawing 001 with shielded twisted pairs](wiring_harness/M-CAN_dongle_003.pdf)
The latter drawing explicitly includes twisted pairs for the CAN lines, which may be important for the wire lengths used here. 

I am also including the source files [1](wiring_harness/M-CAN_dongle_001.yml) and [2](wiring_harness/M-CAN_dongle_003.yml) used to render the drawings with [wireviz](https://github.com/wireviz/WireViz/).

# Tips
One or two good logs is far more valuable than 10 questionable logs. I had much better success after identifying my best logs and cleaning them (e.g. out-of-range timestamps from extra acquisitions). Think of log acqusition as a scientific experiment: you want a test and a control condition. In the case of preconditioning, that meant setting the nav to a charger nearby vs. to a school nearby. You can also tag logs with known messages. I plan to use the star buttons for this purpose.

# Parsing
One approach to [parsing](CAN_parsing/parsing_MWE.ipynb) depends at least in part on interesting timestamp tagging to limit the noise. In our case, this was made possible by dragz's manual discoveries of preconditioning indicator messages.


# More coming soon
I expect that both dragz and I and other new contributors will make a lot more documentation available soon. Quite a few people were working on this in parallel and we're starting to find each other: Thomas has found that preconditioning messages are not forwarded to B-CAN, and Liz has found that preconditoning messages are not forwarded to A- or E-CAN.

# Contributing
Feel free to join the conversation on Ioniqforum or the [E-GMP discord](https://discord.gg/HmwyXv73Br). PRs are welcome if my repo becomes big enough to be worth using as a central repo.

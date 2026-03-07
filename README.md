# Purpose 
I plan to use this repository to document Ioniq 5 CAN reverse-engineering.

# Contents
At the moment, this repository contains two logs of CAN messages filtered/edited down from logs recorded using SavvyCAN that can be sent back to Ioniq 5s with a battery PTC heater equipped and battery preconditioning mode enabled to initiate or cancel preconditioning manually. These messages were reverse-engineered by [dragz](https://github.com/dragz) and I. See dragz's [articles](https://github.com/dragz/explorationsincarhacking/tree/main/articles) or our [Ioniqforum notes](https://www.ioniqforum.com/posts/666540/) for more documentation. 

# Parsing
The repository also contains a python notebook that I trimmed down into a usable parsing tool. The parsing depends at least in part on interesting timestamp tagging to limit the noise. In our case, this was made possible by dragz's manual discoveries of preconditioning indicator messages.

# Tips
One or two good logs is far more valuable than 10 questionable logs. I had much better success after identifying my best logs and cleaning them (e.g. out-of-range timestamps from extra acquisitions). Think of log acqusition as a scientific experiment: you want a test and a control condition. In the case of preconditioning, that meant setting the nav to a charger nearby vs. to a school nearby. You can also tag logs with known messages. I plan to use the star buttons for this purpose.

# 
I expect that we'll both make a lot more documentation available soon. 

# Contributing
Feel free to join the conversation on Ioniqforum or the [E-GMP discord](https://discord.gg/HmwyXv73Br). PRs are welcome if my repo becomes big enough to be worth using as a central repo.

---
layout: about
title: about
permalink: /
subtitle: Closing the gap between physical intelligence and its fundamental limits.

profile:
  align: right
  image: profile/prof_pic.webp # made with bin/cloak_photo.sh --no-cloak (see the README's "Profile photo")
  image_circular: false # crops the image to make it circular
  more_info: # optional lines under the photo, e.g. <p>Office 123</p><p>City, State</p>

selected_papers: false # off: all publications, then the working papers, are listed at the end of the text below instead
social: true # shows the icons configured in _data/socials.yml

latest_posts:
  enabled: false # turn on once you write posts in _posts/ (and set nav: true in _pages/blog.md)
  scrollable: true
  limit: 3
---

I'm an M.S. student in [Electrical and Computer Engineering](https://ece.illinois.edu) at the [University of Illinois Urbana-Champaign](https://illinois.edu), where I'm part of the [Reliable Autonomy Group](https://mitras.ece.illinois.edu/group.html) and a teaching assistant for ECE 486, Control Systems.

Robots are learning remarkable skills, but there are limits no robot can learn its way past. Some are physical: a robot's **dynamics** decide what is feasible, from a high-level plan down to a single motor command. Others are about complexity: how much a robot must sense, compute, and represent to succeed. I want to understand these **fundamental limits**, and build **physical intelligence** that reasons about them and learns to reach them. Right now, that means studying how little information a controller needs to keep a system safe, and deploying resource-efficient learned policies on nano-drones.

### Research Interests

- **How much intelligence does a physical task require?** Making effective decisions can require a minimum amount of information and computation. I'm interested in characterizing these fundamental limits on decision-making, to scope the intelligence a robot needs for a task.
- **How should a robot's dynamics and environment inform its decisions?** The limits that matter include underactuated or hard-to-model dynamics, limited communication, and environments that change while the robot acts. I'm interested in robots that know their limits and can act flexibly within them.
- **How can a robot learn compact representations for physical tasks?** I'm interested in new learning problems where the limits of the task, the robot, and its environment shape the model's architecture, and in analyzing how the resulting policies are trained and how they perform.

### Background

- **M.S. in Electrical and Computer Engineering**, UIUC, Reliable Autonomy Group (2025–now)
- **B.S. in Computer Engineering**, UIUC (2021–2025)
- **Robotics Institute Summer Scholar**, [Drive Lab](https://drive-lab-cmu.github.io/), Carnegie Mellon University (2022 and 2024)
- **Undergraduate Researcher**, Intelligent Motion Laboratory, UIUC (2021–2022)

<h2 style="clear: both">
  <a href="/publications/" style="color: inherit">Publications</a>
</h2>
<div class="publications">
{% bibliography --group_by none --query @unpublished,@article,@inproceedings %}
</div>

<h2>
  <a href="/publications/#working-papers" style="color: inherit">Working Papers</a>
</h2>
<div class="publications">
{% bibliography --group_by none --query @techreport %}
</div>

<h2>Honors</h2>

- **ABP Scholarship**, [Association of Bulgarian Professionals](https://bgprofessionals.org/3rd-annual-scholarship-award-ceremony-networking-event/) (2023)
- **Third place, Public Outreach**, [NASA Lunabotics](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/college-teams-earn-top-honors-during-lunabotics-2023-competition/#:~:text=of%20Nebraska%20%E2%80%93%20Lincoln-,Public%20Outreach%20Project%20Report,-First%20Place%20%E2%80%93%20University), with [Illinois Robotics in Space](/projects/illinois_robotics_in_space/) (2023)

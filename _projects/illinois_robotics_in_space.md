---
layout: page
title: Illinois Robotics in Space
description: Autonomy for a student-built lunar mining rover
importance: 5
---

{% comment %}TODO: add a photo of the rover or the team (see "Images and videos" in README.md).{% endcomment %}

[Illinois Robotics in Space](https://iris.ae.illinois.edu/members) is a student robotics team at the University of Illinois Urbana-Champaign; I was a member from 2021 to 2024. I started on the autonomous team as a programmer, led it from 2022 to 2023, and was president of the team from 2023 to 2024. At NASA's Lunabotics 2023 competition, the team won [third place in the Public Outreach Project Report category](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/college-teams-earn-top-honors-during-lunabotics-2023-competition/#:~:text=of%20Nebraska%20%E2%80%93%20Lincoln-,Public%20Outreach%20Project%20Report,-First%20Place%20%E2%80%93%20University).

- **Autonomy stack.** I led the design and development of a ROS 2 autonomy stack for localization and mapping on a Jetson Nano, for a mining rover designed around lunar-environment constraints, and coordinated actuator selection and sensor integration with the mechanical and electrical teams.
- **Perception and simulation.** I guided the integration of AprilTags and RTAB-Map simultaneous localization and mapping (SLAM), and set up a ROS 2 Gazebo simulation of the differential-drive robot with a depth camera so the team could test on a simulated robot.
- **Motor control.** I led development of an Arduino-based motor-control and sensor hub with PID controllers, a custom serial message protocol, interrupt-driven sensor reading, and a host-side Python driver over USB.
- **Leadership.** As president, I directed funding, sponsorships, and coordination across teams, expanding outreach to 200+ students and increasing active membership by 25% through recruitment.

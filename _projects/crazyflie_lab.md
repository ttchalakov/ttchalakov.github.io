---
layout: page
title: Crazyflie-Lab
description: An open-source research SDK for Crazyflie nano drones with the AI-deck
importance: 1
github: https://github.com/IllinoisReliableAutonomyGroup/Crazyflie-Lab
---

{% comment %}TODO: add a photo or flight video (see "Images and videos" in README.md).{% endcomment %}

Built in the [Reliable Autonomy Group](https://mitras.ece.illinois.edu/group.html) at the University of Illinois Urbana-Champaign, 2025 to present. Code: [IllinoisReliableAutonomyGroup/Crazyflie-Lab](https://github.com/IllinoisReliableAutonomyGroup/Crazyflie-Lab) (GPL-3.0).

Crazyflie-Lab is a software development kit for research on the Crazyflie 2.1 Brushless nano drone with the AI-deck. It packages the control architecture I developed to streamline deploying state- and vision-based reinforcement learning (RL) policies, so that one versioned repository provides:

- shared C libraries for the drone's GAP8 and STM32 processors, covering radio transport, camera streaming, JPEG encoding, and quantized neural-network kernels;
- a `cf-lab` command that builds and flashes the STM32 controller, the GAP8 app, and the ESP32 firmware, and runs the NEMO and DORY neural-network pipeline;
- a Python package for the host computer, with radio backends, motion-capture streaming, experiment runners, preflight checks, and telemetry recording;
- example apps, each split into controller, GAP8, and host code.

Work done with it:

- **Onboard inference.** I optimized concurrent policy inference and video streaming on the GAP8 to run in real time, including priority-based scheduling of the shared SPI bus. Compared with the original sequential implementation, policy throughput doubled and policy latency dropped by 30%.
- **Inner-loop characterization.** Through controlled flight experiments run with a custom Python harness, I characterized the command responses of the PID and INDI inner loops and tuned the PID gains. These measurements support dynamics modeling for RL simulation.
- **Flight data.** A configurable framework brings together OptiTrack motion capture, STM32 and GAP8 telemetry, and camera streams for hardware debugging and flight analysis, with adjustable sampling rates and post-processing time-stamp alignment.

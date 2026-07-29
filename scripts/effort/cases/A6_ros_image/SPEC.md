---
id: A6_ros_image
title: ROS image topic acquisition
---

## Goal

Consume frames from a ROS image topic via the same camera contract.

## Stack assumptions

ROS Image subscription vs ImageHandler source=ros

## Success condition

Frames available to a callback / read loop.

## Non-goals

Not measuring transport latency.

## Counting

Application fixtures only. Nectar package internals are never counted.
Regions use `# @loc:boilerplate` / `# @loc:core` markers.

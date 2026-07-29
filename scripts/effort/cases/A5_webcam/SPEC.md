---
id: A5_webcam
title: Webcam acquisition
---

## Goal

Open a USB webcam and read frames via the camera contract.

## Stack assumptions

OpenCV VideoCapture vs ImageHandler source=usb/opencv

## Success condition

Frames available to a callback / read loop.

## Non-goals

Not measuring FPS or image quality.

## Counting

Application fixtures only. Nectar package internals are never counted.
Regions use `# @loc:boilerplate` / `# @loc:core` markers.

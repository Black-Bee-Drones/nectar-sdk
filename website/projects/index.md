# Projects

Nectar SDK is the shared foundation Black Bee Drones uses for competition missions. These are
the real codebases behind those runs — what the SDK looks like in a full autonomous mission,
end to end.

!!! note "SDK lineage"

    The SDK evolved over three generations: `tadinisdk` (ROS 1) → `mirela_sdk` (ROS 2) →
    **`nectar`**. Older projects reference the earlier names; each page below states which one it
    used. The competition repositories are being progressively open-sourced under the
    [Black Bee Drones organization](https://github.com/Black-Bee-Drones).

<div class="grid cards" markdown>

-   **IMAV 2025 — Indoor Search & Rescue**

    3rd place. Gate entry and autonomous landing on a moving, smoke-obscured platform, on a
    Jetson Orin Nano with Isaac VSLAM. Uses `mirela_sdk` (Nectar v0.1.0).

    [IMAV 2025](imav-2025.md)

-   **CBR 2025 — Flying Robot League**

    A four-phase indoor mission: mapping, gripper package delivery, gesture control, and maze
    navigation. Uses `mirela_sdk` (Nectar v0.1.0).

    [CBR 2025](cbr-2025.md)

-   **IMAV 2023**

    3rd place; the only team to complete the course fully autonomously. Line following + ArUco
    landing. ROS 1 on the first-generation `tadinisdk` — predates Nectar.

    [IMAV 2023](imav-2023.md)

-   **SAE 2026 — EletroQuad**

    In progress on the current `nectar` package: hook-and-place, gauge reading, and more.

    [SAE 2026](sae-2026.md)

</div>

# Brand logos (Built on)

The Home page "Built on" chips render a brand logo when a matching file is present here, and
fall back to a plain text label otherwise (`onerror` on the `<img>`, or `alt` text for the
logo-only chips). Filenames must match exactly.

Wordmark logos (the logo already spells the name) are shown on their own, with the name in
`alt`/`aria-label` only, to avoid repeating the text: ArduPilot, Ultralytics, and Parrot
(shown as the Parrot mark followed by the "Bebop" qualifier). Symbol marks keep their text
label: PX4, Luxonis, MAVLink, Bitcraze.

## Included

| File | Brand | Source | License / note |
|------|-------|--------|----------------|
| `px4.svg` | PX4 | PX4-Devguide `assets/px4-logo.svg` (<https://github.com/PX4/PX4-graphics>) | Dronecode trademark; use unaltered, black/white only |
| `ardupilot.svg` | ArduPilot | Wikimedia Commons (<https://commons.wikimedia.org/wiki/File:ArduPilot_logo.svg>) | CC BY-SA 3.0 (ArduPilot dev team) |
| `luxonis.svg` | Luxonis (symbol) | Luxonis brand assets (<https://www.luxonis.com/marketing>) | Luxonis trademark |
| `parrot.svg` | Parrot (Bebop) | Wikimedia Commons (<https://commons.wikimedia.org/wiki/File:Parrot-logo.svg>) | Parrot SA trademark |
| `ultralytics.svg` | Ultralytics (logotype) | ultralytics/assets `logo/Ultralytics_Logotype_Original.svg` (<https://github.com/ultralytics/assets>) | Ultralytics trademark; nominative use |
| `mavlink.png` | MAVLink | MAVLink GitHub org avatar (<https://github.com/mavlink>) | Dronecode trademark; nominative use. No official SVG published |
| `bitcraze.png` | Bitcraze (Crazyflie) | Bitcraze GitHub org avatar (<https://github.com/bitcraze>) | Bitcraze AB trademark; nominative use. No public SVG for redistribution |

Notes:

- Prefer an SVG/PNG that reads on a dark background (the site's dark scheme uses a near-black
  surface). The Parrot wordmark is dark, so it appears faint; swap for a light variant if wanted.
- MAVLink and Bitcraze are PNGs (the orgs publish no SVG); they are the orgs' own avatars.
- Keep them small; they render at ~1em height in the chip.
- Use each project's marks per its brand/trademark guidelines (nominative "built on" use).

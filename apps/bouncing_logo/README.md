# Bouncing Logo

Bouncing Logo drifts @ashleywolf around the screen like the classic DVD screensaver.

## Use

Open **bouncing_logo** in the Universe 2026 launcher. A big, slanted
@ashleywolf name glides diagonally across a black
screen at a steady 71 pixels per second. Every time it touches a wall, it
bounces and switches to a new bright color.

Now and then, it hits a corner exactly. Then the logo flashes through every
color, three rings ripple out from that corner, and the case lights pulse.
After about 1.4 seconds, it settles on a new color and keeps going.
The first corner comes 8 to 16 seconds after the app opens, then one every
20.8 seconds. That's about 11 wall bounces between corners, so they still feel
like a treat.

Tilt the badge to steer. The logo turns toward the low side, like a marble,
but its speed never changes. Let go, and after half a second it eases back to
a 45-degree path that lines up for the next corner hit. The steering adapts to
how you're holding the badge, so a held tilt slowly fades. This doesn't track
spinning the badge flat on a table, because gravity doesn't change.

| Control | Action |
| --- | --- |
| Tilt | Steer the logo; speed stays the same |
| BACK | Return to the launcher |
| HOME | Firmware-owned return to the launcher |

You don't need Wi-Fi, credentials, saved state, extra hardware, or extra
libraries. The app targets **GitHub Universe 2026 firmware**, not the older
e-paper Badger or the Universe 2025 runtime.

## How corners stay possible

The logo is 190x32 pixels, so it travels 130 pixels across and 208 down.
Both numbers are multiples of 26. On a 45-degree path, the logo hits a corner
exactly when its distances to the next two walls differ by a multiple of 26.
Bounces never change that difference. After you steer, the app gently nudges
the path back onto this 26-pixel grid, at most 6 pixels per second, so the
next corner still arrives within 20.8 seconds. A corner counts when both walls
are reached within 0.75 pixels of each other in the same frame.

## Preview without installing

From the repository root:

```sh
python3 tools/bouncing_logo.py build
python3 tools/bouncing_logo.py serve
```

Open http://127.0.0.1:8777/. The preview uses this repository's Badge
Simulator page and the official MicroPython WebAssembly runtime at the revision
pinned in `.github/extensions/badge-simulator/web/BUILD_INFO.json`. It runs
these app files, not a JavaScript copy. The first run needs internet access to
cache the runtime. The preview can't deploy anything. Stop it with Ctrl-C.

Use **Rotate** to test the upside-down badge. Computers without motion input
report a still IMU, so the checks inject tilt readings instead.

With the preview open in a visible browser tab:

```sh
python3 tools/bouncing_logo.py verify
```

This writes screenshots and `verification.json` to `dist/bouncing_logo`. It
checks constant speed, a new color on every wall bounce, an exact corner hit
and its celebration, name readability, live tilt steering, corner timing with
steady and jittery frames, zero, extreme, and upside-down IMU readings, case
lights turning off, heap use, rotation, and BACK/HOME. The in-app part is
`tools/bouncing_logo_e2e.py`.

## Build and install

```sh
python3 tools/bouncing_logo.py build
```

This draws the original 24x24 `icon.png` and creates
`dist/bouncing_logo/bouncing_logo.zip`. The zip holds
`bouncing_logo/__init__.py`, `icon.png`, and this README.

**Don't flash firmware or copy anything to the RP2350 bootloader drive.**

1. Follow [`hardware/USB_SERIAL.md`](../../../hardware/USB_SERIAL.md).
   Open the badge's **Mass Storage** app, or use its documented USB Disk Mode.
   The **BADGER** drive appears.
2. Unzip the archive. Copy the whole `bouncing_logo` folder into the BADGER
   drive's `apps` folder (`system/apps` on some firmware). It installs at
   `/system/apps/bouncing_logo`.
3. Check that the menu shows custom icons, as described in the USB guide.
   Older event menus need the documented menu icon patch. That's a separate
   system change, not part of this app.
4. Eject BADGER safely, then reset the badge so it starts at the launcher.
   Open **Bouncing Logo** and test it both ways up.

## Rendering and limits

The badge has a 320x240 color LCD. The app runs in `HIRES | VSYNC`. It draws
the slanted name into one off-screen image, and only redraws that
image when the color changes. Each frame clears the screen and copies the
image once, so there are no file reads, network calls, or sleeps in the frame
loop. Movement uses `badge.ticks_delta`, and long pauses are capped at
0.1 seconds per frame, so the logo never jumps. Text uses the firmware's
Mona Sans font. All graphics are original; no DVD Forum logo or artwork is
included.

**Physical checks still needed:** frame smoothness on the RP2350, tilt
direction (the low side should pull the logo) upright and upside down, case
light pulses on a corner hit, the menu icon, and HOME/BACK returning to the
launcher and reopening. The simulator can't measure badge speed, real memory
use, battery life, or sensor calibration.

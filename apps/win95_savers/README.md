A Windows 95 screensaver pack with Solitaire, Flying Octocats and Mystify, each with a GitHub twist.

The app opens on a Windows 95 **Display Properties** dialog. After a moment it
"clicks" **Preview** and starts the selected screensaver. It is a companion to
the Windows 3D Pipes app.

## The savers

| Saver | Classic look | GitHub twist |
| --- | --- | --- |
| **Solitaire** | The famous win cascade: cards bounce off the bottom of the green felt and leave trails. | Card backs and face cards carry the GitHub mark. The win box says "All 52 checks have passed" and offers a green **Merge** button. |
| **Flying Octocats** | The Flying Windows starfield. | Four-colour Octocat marks fly at you instead of Windows flags. |
| **Mystify** | Two bouncing polygons with colour-shifting echo trails. | The colours drift around GitHub green and Copilot purple. |

## Controls

| Button | In the dialog | While a saver runs |
| --- | --- | --- |
| **Left / Right** | Pick a saver | Pick a saver and return to the dialog |
| **Up** | Toggle **Cycle all three savers** | Toggle cycling and return to the dialog |
| **Select** | Start the saver now | Restart the saver |
| **Back** | Leave the app | Return to the dialog |

With cycling on, the badge moves to the next saver every 45 seconds. Solitaire
moves on after its win box. With cycling off, Solitaire deals again. The app
remembers your saver and cycle choice.

The app needs no network, sensors, or extra hardware. It runs in HIRES mode
(320x240). Everything is drawn in code, so `__init__.py` has no asset files to
load.

## Preview in a simulator

Open <https://badger.github.io/simulator>, create an app named
`win95_savers`, and paste in `__init__.py`.

## Install on a badge

1. Put the badge in USB Disk Mode so the `BADGER` drive appears.
2. Copy the `win95_savers` folder (with `__init__.py`, `icon.png` and
   `README.md`) into `BADGER/apps/`.
3. Eject the drive and reset the badge. Pick **win95_savers** from the menu.

To rebuild the icon and a ready-to-copy zip, run
`python3 tools/win95_savers.py build --output <dir>`.

## Credits

The GitHub mark comes from [Primer Octicons](https://github.com/primer/octicons)
(MIT License). Windows 95, Solitaire, Flying Windows and Mystify belong to
Microsoft; this app is a fan tribute.

# Badge apps

These are my apps for the GitHub Universe 2026 badge (Badger 2350). Each folder
under `apps/` is one app.

![Space Pinball running on the badge](screenshots/space_pinball.png)

## Apps

| App | What it does |
| --- | --- |
| [Space Pinball](apps/space_pinball) | Lean the badge to roll the ball around a space pinball table, inspired by 3D Pinball: Space Cadet. |
| [3D Maze](apps/maze3d) | Walk through a red brick labyrinth by tilting and turning the badge. |
| [Ski Tilt](apps/ski_tilt) | Tilt the badge to steer a skier downhill, SkiFree-style. |
| [Bouncing Logo](apps/bouncing_logo) | A handle bounces around the screen like the classic DVD screensaver. |

Each app's README lists its controls.

## Install an app

1. Plug the badge into your computer with USB.
2. Put the badge in USB disk mode. A drive named `BADGER` appears.
3. Copy an app folder, for example `apps/space_pinball`, into the `apps/`
   folder on the `BADGER` drive.
4. Eject the drive and reset the badge. The app shows up in the menu.

These apps need the October 2026 badge firmware. They use the badge's built-in
`badge`, `screen`, and button globals, so they don't run on the 2025 badge.

## Credits

I wrote all the code and drew all the art in code. The apps borrow ideas from
classic games and screensavers, but they include no graphics, sounds, or code
from them.

Made for the [GitHub Universe badge](https://github.com/badger/home).

# 3D Maze

3D Maze walks you through a red brick labyrinth, steered by tilting and turning the badge.

It's a tribute to the classic Windows 3D Maze screensaver. Each run builds a
new random maze. Find the green EXIT sign in the far corner to escape.

## Controls

| Input | Action |
| --- | --- |
| Tilt top away / toward you | Walk forward / back |
| Tilt left / right | Turn left / right |
| Turn your body with the badge | Look around (gyroscope) |
| D-pad | Walk and turn without tilting |
| SELECT | Re-centre tilt (hold the badge how you like, then press) |
| MENU | Show or hide the map of places you've seen |
| BACK | Autopilot on or off |
| HOME | Back to the menu |

After a minute with no input, autopilot takes over and wanders the maze like
the original screensaver. Your best escape time is saved. Autopilot escapes
don't count.

## Hardware

Uses the badge's motion sensor (`badge.imu()`). Without it, the D-pad still
works. If a tilt or turn direction feels backwards, flip `STEER_SIGN`,
`WALK_SIGN` or `GYRO_SIGN` at the top of `__init__.py`.

No network is needed.

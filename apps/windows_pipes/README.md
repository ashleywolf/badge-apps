# Windows Pipes

Windows Pipes grows glossy 3D pipes behind a floating @ashleywolf name, inspired
by the classic Windows 3D Pipes screensaver.

## How it works

Six pipes grow at different speeds through a 3D grid, turning at random 90-degree
corners. Green, purple, magenta, and cyan tubes have metallic highlights and
rounded elbows on a black background. When the scene fills up, it clears and
starts a new maze.

The name stays readable on top of the pipes. Tilt the badge and the name slides
and bobs, then springs back when you hold still.

| Control | Action |
| --- | --- |
| Tilt | Move the floating name |
| SELECT | Start a new maze |
| BACK | Return to the menu |

## Requirements

Windows Pipes needs the October 2026 badge firmware. It uses the built-in
`pico3d` module for fast 3D drawing on the badge's 320x240 color screen. It
needs no Wi-Fi, saved data, or extra libraries.

All graphics are drawn in code. The app includes no Microsoft code, art, or
fonts.

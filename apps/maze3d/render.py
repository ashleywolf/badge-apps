"""Textured raycaster for the 3D Maze app.

The heavy lifting runs in a Viper function that writes straight into an
offscreen image's 32-bit pixels, so each frame touches every pixel once.
All maths is integer fixed point: positions and distances in Q16 (1 cell =
65536), view vectors in Q14.
"""

import math
import random
import struct
from array import array

import micropython

TEX = micropython.const(64)
TEX_SHIFT = micropython.const(6)
BIAS = micropython.const(1 << 24)
FOV = 0.66

BRICK = 1
EXIT = 2
START = 3

_probe = image(1, 1)


def native(r, g, b):
    """Return the firmware's 32-bit pixel value for an opaque colour."""
    _probe.pen = color.rgb(r, g, b)
    _probe.clear()
    return struct.unpack("<I", bytes(_probe.raw[:4]))[0]


def _channel_offsets():
    offsets = []
    for rgb in ((255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0)):
        _probe.pen = color.rgb(*rgb)
        _probe.clear()
        raw = bytes(_probe.raw[:4])
        offsets.append(raw.index(255))
    return offsets


def _brick(raw, top, offsets, rng):
    ro, go, bo, ao = offsets
    mortar = (168, 160, 150)
    for course in range(8):
        shift = 8 if course & 1 else 0
        tones = [(150 + rng.randrange(-22, 22), 44 + rng.randrange(-10, 12), 30 + rng.randrange(-8, 8))
                 for _ in range(5)]
        for row in range(8):
            y = course * 8 + row
            base = ((top + y) * TEX) * 4
            for x in range(TEX):
                column = (x + shift) & 15
                if row == 7 or column == 15:
                    r, g, b = mortar
                    n = rng.randrange(-14, 10)
                else:
                    r, g, b = tones[((x + shift) >> 4) % 5]
                    n = rng.randrange(-12, 12)
                    if row == 0 or column == 0:
                        n += 22
                    elif row == 6 or column == 14:
                        n -= 26
                i = base + x * 4
                raw[i + ro] = max(0, min(255, r + n))
                raw[i + go] = max(0, min(255, g + n))
                raw[i + bo] = max(0, min(255, b + n))
                raw[i + ao] = 255


def _sign(tex, top, label, fill, text_pen):
    tex.pen = color.rgb(20, 20, 20)
    tex.rectangle(6, top + 18, TEX - 12, 26)
    tex.pen = fill
    tex.rectangle(8, top + 20, TEX - 16, 22)
    tex.font = font.nope
    width, height = tex.measure_text(label)
    tex.pen = text_pen
    tex.text(label, (TEX - width) // 2, top + 20 + (22 - height) // 2)


def build_textures(seed=2026):
    """Brick, EXIT and START wall textures stacked vertically (64x192)."""
    random.seed(seed)
    tex = image(TEX, TEX * 3)
    offsets = _channel_offsets()
    raw = tex.raw
    for slot in range(3):
        _brick(raw, slot * TEX, offsets, random)
    _sign(tex, TEX * (EXIT - 1), "EXIT", color.rgb(30, 160, 70), color.rgb(255, 255, 255))
    _sign(tex, TEX * (START - 1), "START", color.rgb(240, 236, 220), color.rgb(170, 30, 30))
    return tex


def build_rows(height):
    """One colour per screen row: ceiling fading into the dark, then the floor."""
    rows = image(1, height)
    horizon = height // 2
    for y in range(height):
        if y < horizon:
            t = y / horizon
            r, g, b = 92 - 70 * t, 92 - 70 * t, 104 - 76 * t
        else:
            t = (y - horizon) / (height - horizon)
            r, g, b = 26 + 96 * t, 24 + 88 * t, 22 + 74 * t
        rows.pen = color.rgb(int(r), int(g), int(b))
        rows.rectangle(0, y, 1, 1)
    return rows


class Renderer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.frame = image(width, height)
        self.textures = build_textures()
        self.rows = build_rows(height)
        alpha = native(0, 0, 0)
        # Distance (Q16) per 1/16th of darkening.
        self.cfg = array("I", [width, height, 0, BIAS, 0, 0, 0, 0, 0, 0, alpha, 40000])

    def draw(self, grid, grid_width, x, y, angle):
        cfg = self.cfg
        dx = math.cos(angle)
        dy = math.sin(angle)
        cfg[2] = grid_width
        cfg[4] = BIAS + int(x * 65536)
        cfg[5] = BIAS + int(y * 65536)
        cfg[6] = BIAS + int(dx * 16384)
        cfg[7] = BIAS + int(dy * 16384)
        cfg[8] = BIAS + int(-dy * FOV * 16384)
        cfg[9] = BIAS + int(dx * FOV * 16384)
        cast(self.frame.raw, self.textures.raw, grid, self.rows.raw, cfg)
        return self.frame


@micropython.viper
def cast(frame, textures, grid, rows, cfg):
    out = ptr32(frame)
    tex = ptr32(textures)
    cells = ptr8(grid)
    row = ptr32(rows)
    c = ptr32(cfg)
    w = int(c[0])
    h = int(c[1])
    gw = int(c[2])
    bias = int(c[3])
    px = int(c[4]) - bias
    py = int(c[5]) - bias
    dir_x = int(c[6]) - bias
    dir_y = int(c[7]) - bias
    plane_x = int(c[8]) - bias
    plane_y = int(c[9]) - bias
    alpha = int(c[10])
    fog = int(c[11])
    cell_x = px >> 16
    cell_y = py >> 16
    frac_x = px & 0xFFFF
    frac_y = py & 0xFFFF
    # 1 << 30 would fold to a big-int object; build it as a machine int.
    one = 0x8000
    one = one << 15
    x = 0
    while x < w:
        cam = ((((x << 1) + 1) << 14) // w) - 16384
        ray_x = dir_x + ((plane_x * cam) >> 14)
        ray_y = dir_y + ((plane_y * cam) >> 14)
        abs_x = ray_x
        if abs_x < 0:
            abs_x = 0 - abs_x
        abs_y = ray_y
        if abs_y < 0:
            abs_y = 0 - abs_y
        delta_x = 1 << 24
        if abs_x >= 64:
            delta_x = one // abs_x
        delta_y = 1 << 24
        if abs_y >= 64:
            delta_y = one // abs_y
        if ray_x < 0:
            step_x = -1
            side_x = (frac_x >> 8) * (delta_x >> 8)
        else:
            step_x = 1
            side_x = ((0x10000 - frac_x) >> 8) * (delta_x >> 8)
        if ray_y < 0:
            step_y = -1
            side_y = (frac_y >> 8) * (delta_y >> 8)
        else:
            step_y = 1
            side_y = ((0x10000 - frac_y) >> 8) * (delta_y >> 8)
        mx = cell_x
        my = cell_y
        side = 0
        hit = 1
        steps = 0
        while steps < 96:
            if side_x < side_y:
                side_x += delta_x
                mx += step_x
                side = 0
            else:
                side_y += delta_y
                my += step_y
                side = 1
            hit = int(cells[my * gw + mx])
            if hit:
                break
            steps += 1
        if hit == 0:
            hit = 1
        if side == 0:
            perp = side_x - delta_x
            wall = py + (((perp >> 7) * ray_y) >> 7)
        else:
            perp = side_y - delta_y
            wall = px + (((perp >> 7) * ray_x) >> 7)
        if perp < 256:
            perp = 256
        u = (wall & 0xFFFF) >> 10
        # Map y points down, so west- and south-facing hits read backwards.
        if side == 0 and ray_x < 0:
            u = 63 - u
        if side == 1 and ray_y > 0:
            u = 63 - u
        line = (h << 16) // perp
        step = (64 << 16) // line
        top = (h - line) >> 1
        y0 = top
        if y0 < 0:
            y0 = 0
        y1 = top + line
        if y1 > h:
            y1 = h
        shade = 16 - perp // fog
        if side == 1:
            shade -= 3
        if shade < 3:
            shade = 3
        pos = (y0 - top) * step
        base = ((hit - 1) << 12) + u
        o = x
        y = 0
        while y < y0:
            out[o] = row[y]
            o += w
            y += 1
        if shade >= 16:
            while y < y1:
                out[o] = tex[base + (((pos >> 16) & 63) << 6)]
                pos += step
                o += w
                y += 1
        else:
            while y < y1:
                p = int(tex[base + (((pos >> 16) & 63) << 6)])
                lo = (((p & 0xFF00FF) * shade) >> 4) & 0xFF00FF
                hi = ((((p >> 8) & 0xFF00FF) * shade) >> 4) & 0xFF00FF
                out[o] = lo | (hi << 8) | alpha
                pos += step
                o += w
                y += 1
        while y < h:
            out[o] = row[y]
            o += w
            y += 1
        x += 1

"""Draws the static Space Pinball artwork once, so each frame is one blit."""

import math
import random

import table as T

W = 320
H = 240
PANEL_X = 200

SPACE_TOP = color.rgb(8, 10, 38)
SPACE_BOTTOM = color.rgb(36, 10, 58)
WALL_GLOW = color.rgb(40, 140, 255, 70)
WALL = color.rgb(150, 210, 255)
WALL_SHADOW = color.rgb(20, 40, 90)
LANE_FLOOR = color.rgb(6, 6, 20)
SLING_FILL = color.rgb(150, 24, 60)
SLING_EDGE = color.rgb(255, 120, 150)
PANEL_TOP = color.rgb(46, 58, 104)
PANEL_BOTTOM = color.rgb(14, 16, 40)
BEVEL_LIGHT = color.rgb(150, 170, 230)
BEVEL_DARK = color.rgb(4, 6, 16)
LCD_BG = color.rgb(4, 4, 8)
LABEL = color.rgb(170, 190, 255)
TITLE_GOLD = color.rgb(255, 200, 60)
TITLE_RED = color.rgb(230, 60, 40)
DIM_LIGHT = color.rgb(60, 50, 40)

SCORE_BOX = (208, 76, 104, 22)
BALL_BOX = (208, 116, 34, 18)
MULT_BOX = (248, 116, 64, 18)
RANK_BOX = (208, 150, 104, 16)
MISSION_BOX = (208, 182, 104, 34)


def screen_like_image(width, height):
    pixel_bytes = len(screen.raw) // (screen.width * screen.height)
    if pixel_bytes == 2:
        return image(width, height, bytearray(width * height * 2), image.RGB565)
    return image(width, height)


def chevron(cx, cy, size):
    return [
        vec2(cx - size, cy + size * 0.6),
        vec2(cx, cy - size * 0.4),
        vec2(cx + size, cy + size * 0.6),
        vec2(cx + size, cy + size * 1.1),
        vec2(cx, cy + size * 0.1),
        vec2(cx - size, cy + size * 1.1),
    ]


def bevel(img, x, y, w, h, sunken=False):
    light, dark = (BEVEL_DARK, BEVEL_LIGHT) if sunken else (BEVEL_LIGHT, BEVEL_DARK)
    img.pen = light
    img.rectangle(x, y, w, 1)
    img.rectangle(x, y, 1, h)
    img.pen = dark
    img.rectangle(x, y + h - 1, w, 1)
    img.rectangle(x + w - 1, y, 1, h)


def lcd(img, box, label, label_font):
    x, y, w, h = box
    img.pen = LCD_BG
    img.rectangle(x, y, w, h)
    bevel(img, x - 1, y - 1, w + 2, h + 2, True)
    if label:
        img.font = label_font
        img.pen = LABEL
        img.text(label, x, y - 11)


def scaled_text(img, text, x, y, scale, pen):
    img.pen = pen
    img.text(text, vec2(0, 0), transform=mat3().translate(x, y).scale(scale, scale))


def draw_table(img):
    random.seed(1987)
    rand = random.random

    img.pen = brush.gradient(brush.LINEAR, 0.0, 0.0, 0.0, 1.0,
                             [(0.0, SPACE_TOP), (1.0, SPACE_BOTTOM)],
                             mat3().scale(PANEL_X, H))
    img.rectangle(0, 0, PANEL_X, H)

    # Nebula clouds and stars.
    for cx, cy, r, tint in ((40, 60, 46, (120, 30, 140, 40)), (150, 150, 54, (30, 90, 170, 38)),
                            (70, 190, 40, (170, 40, 90, 30)), (120, 40, 30, (60, 120, 200, 30))):
        for k in range(4):
            img.pen = color.rgb(*tint)
            img.shape(shape.circle(cx + k * 3, cy - k * 2, r - k * 9))
    for _ in range(170):
        x = int(rand() * PANEL_X)
        y = int(rand() * H)
        b = 90 + int(rand() * 165)
        img.pen = color.rgb(b, b, min(255, b + 30))
        img.rectangle(x, y, 1, 1)
    for _ in range(14):
        x = 6 + rand() * (PANEL_X - 12)
        y = 6 + rand() * (H - 12)
        img.pen = color.rgb(255, 255, 255, 110)
        img.shape(shape.star(x, y, 4, 0.6, 2.4))

    # Ringed planet behind the lower playfield.
    px, py, pr = 93, 150, 26
    planet = brush.gradient(brush.RADIAL, 0.3, 0.3, 1.0, 1.0,
                            [(0.0, color.rgb(120, 220, 230)), (0.5, color.rgb(40, 110, 170)), (1.0, color.rgb(12, 20, 60))],
                            mat3().translate(px - pr, py - pr).scale(pr * 2, pr * 2))
    img.pen = planet
    img.shape(shape.circle(px, py, pr))
    ring = shape.ellipse(0, 0, pr * 1.7, pr * 0.42).stroke(2)
    ring.transform = mat3().translate(px, py).rotate(-14)
    img.pen = color.rgb(255, 210, 140, 150)
    img.shape(ring)

    # Plunger lane floor and lettering.
    img.pen = LANE_FLOOR
    img.rectangle(T.LANE, 70, T.RIGHT - T.LANE, T.FLOOR - 70)
    img.font = font.nope
    img.pen = color.rgb(255, 200, 60, 170)
    for i, ch in enumerate("LAUNCH"):
        w, _ = img.measure_text(ch)
        img.text(ch, int(T.LAUNCH_X - w / 2), 112 + i * 14)

    # Up arrows (mission progress lights are drawn on top of these).
    img.pen = DIM_LIGHT
    for i in range(3):
        img.shape(shape.custom(chevron(93, 196 - i * 11, 6)))

    # Outlane kickback arrow (dim).
    img.shape(shape.custom(chevron(15, 228, 4)))

    # Slingshots.
    for a, c, b in T.SLINGS:
        img.pen = SLING_FILL
        img.shape(shape.custom([vec2(*a), vec2(*c), vec2(*b)]))
        img.pen = SLING_EDGE
        img.shape(shape.line(a[0], a[1], c[0], c[1], 2))

    # Walls with a soft neon glow.
    for line in T.wall_polylines():
        points = [vec2(x, y) for x, y in line]
        img.pen = WALL_GLOW
        img.shape(shape.custom(points).stroke(6, shape.ALIGN_CENTER | shape.PATH_OPEN | shape.JOIN_ROUND))
        img.pen = WALL
        img.shape(shape.custom(points).stroke(2, shape.ALIGN_CENTER | shape.PATH_OPEN | shape.JOIN_ROUND))

    # Posts, bumper rings, wormhole rim, lane light sockets, drop target slots.
    for x, y in T.POSTS:
        img.pen = WALL
        img.shape(shape.circle(x, y, T.POST_R))
    for x, y in T.BUMPERS:
        img.pen = color.rgb(30, 30, 60)
        img.shape(shape.circle(x, y, T.BUMPER_R + 2))
        img.pen = color.rgb(200, 200, 230)
        img.shape(shape.circle(x, y, T.BUMPER_R + 2).stroke(1.5))
    wx, wy = T.WORMHOLE
    img.pen = color.rgb(0, 0, 0)
    img.shape(shape.circle(wx, wy, T.WORMHOLE_R + 4))
    img.pen = color.rgb(170, 90, 255, 160)
    img.shape(shape.circle(wx, wy, T.WORMHOLE_PULL_R - 2).stroke(1))
    for x, y in T.LANE_LIGHTS:
        img.pen = DIM_LIGHT
        img.shape(shape.circle(x, y, 4))
    img.pen = color.rgb(30, 30, 50)
    for y in T.DROP_TARGETS:
        img.rectangle(T.LEFT + 1, y - 6, 3, 12)


def draw_panel(img):
    img.pen = brush.gradient(brush.LINEAR, 0.0, 0.0, 0.0, 1.0,
                             [(0.0, PANEL_TOP), (1.0, PANEL_BOTTOM)],
                             mat3().translate(PANEL_X, 0).scale(W - PANEL_X, H))
    img.rectangle(PANEL_X, 0, W - PANEL_X, H)
    bevel(img, PANEL_X, 0, W - PANEL_X, H)
    bevel(img, PANEL_X + 1, 1, W - PANEL_X - 2, H - 2)

    # Logo: planet, orbiting rocket and title.
    img.pen = color.rgb(0, 0, 0, 120)
    img.rectangle(PANEL_X + 6, 6, W - PANEL_X - 12, 52)
    bevel(img, PANEL_X + 6, 6, W - PANEL_X - 12, 52, True)
    cx, cy = 300, 22
    img.pen = brush.gradient(brush.RADIAL, 0.3, 0.3, 1.0, 1.0,
                             [(0.0, color.rgb(255, 220, 140)), (1.0, color.rgb(170, 60, 30))],
                             mat3().translate(cx - 9, cy - 9).scale(18, 18))
    img.shape(shape.circle(cx, cy, 9))
    orbit = shape.ellipse(0, 0, 15, 4).stroke(1)
    orbit.transform = mat3().translate(cx, cy).rotate(-20)
    img.pen = color.rgb(255, 255, 255, 160)
    img.shape(orbit)
    img.font = font.ziplock
    scaled_text(img, "SPACE", 213, 13, 1.0, TITLE_RED)
    scaled_text(img, "SPACE", 212, 12, 1.0, TITLE_GOLD)
    img.font = font.sins
    img.pen = color.rgb(150, 210, 255)
    img.text("PINBALL", 213, 38)

    label_font = font.nope
    lcd(img, SCORE_BOX, "SCORE", label_font)
    lcd(img, BALL_BOX, "BALL", label_font)
    lcd(img, MULT_BOX, "BONUS", label_font)
    lcd(img, RANK_BOX, "RANK", label_font)
    lcd(img, MISSION_BOX, "MISSION", label_font)

    img.font = label_font
    img.pen = color.rgb(110, 120, 170)
    img.text("BEST", 208, 222)


def build():
    img = screen_like_image(W, H)
    img.antialias = image.X4
    img.fill_rule = image.EVEN_ODD
    draw_table(img)
    draw_panel(img)
    return img

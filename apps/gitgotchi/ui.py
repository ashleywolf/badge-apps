import math

import pets

WHITE = color.rgb(255, 255, 255)
INK = color.rgb(36, 32, 56)
SHADOW = color.rgb(0, 0, 0, 50)

FLOOR_Y = 70
GROUND_Y = 96
BAR_Y = 104

ACTIONS = ("feed", "play", "clean", "heal", "lights", "stats")
LABELS = {
    "feed": "Feed",
    "play": "Play",
    "clean": "Clean",
    "heal": "Patch",
    "lights": "Lights",
    "stats": "Stats",
}
METER_COLOURS = {
    "feed": color.rgb(240, 150, 60),
    "heart": color.rgb(250, 90, 140),
    "bolt": color.rgb(240, 200, 40),
}


def text(message, x, y, pen=INK, face=None, centre=False, right=False):
    screen.font = face or font.ark
    if centre or right:
        w, _ = screen.measure_text(message)
        x -= w if right else w / 2
    screen.pen = pen
    screen.text(message, int(x), int(y))


def pill(x, y, w, h, pen):
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(x, y, w, h, min(4, h / 2)))


def room(kind, dark):
    wall = pets.INFO[kind][3]
    if dark:
        screen.pen = color.rgb(26, 26, 54)
        screen.rectangle(0, 0, screen.width, FLOOR_Y)
        screen.pen = color.rgb(18, 18, 40)
        screen.rectangle(0, FLOOR_Y, screen.width, screen.height - FLOOR_Y)
    else:
        screen.pen = color.rgb(*wall)
        screen.rectangle(0, 0, screen.width, FLOOR_Y)
        r, g, b = wall
        screen.pen = color.rgb(r * 7 // 10, g * 7 // 10, b * 7 // 10)
        screen.rectangle(0, FLOOR_Y, screen.width, screen.height - FLOOR_Y)
        screen.pen = color.rgb(r * 6 // 10, g * 6 // 10, b * 6 // 10)
        screen.rectangle(0, FLOOR_Y, screen.width, 2)
    # window
    screen.pen = color.rgb(255, 255, 255, 70 if dark else 200)
    screen.shape(shape.rounded_rectangle(116, 22, 34, 28, 3))
    screen.pen = color.rgb(12, 14, 40) if dark else color.rgb(150, 205, 255)
    screen.shape(shape.rounded_rectangle(119, 25, 28, 22, 2))
    if dark:
        screen.pen = color.rgb(255, 240, 180)
        screen.shape(shape.circle(139, 32, 4))
        screen.pen = color.rgb(12, 14, 40)
        screen.shape(shape.circle(137, 31, 4))
        screen.pen = color.rgb(255, 255, 255)
        screen.shape(shape.circle(125, 40, 0.8))
        screen.shape(shape.circle(131, 29, 0.8))
    else:
        screen.pen = color.rgb(255, 255, 255, 220)
        screen.shape(shape.circle(126, 39, 3))
        screen.shape(shape.circle(130, 38, 4))
        screen.shape(shape.circle(134, 40, 3))
    # rug
    screen.pen = color.rgb(255, 255, 255, 25 if dark else 60)
    screen.shape(shape.ellipse(80, GROUND_Y - 2, 56, 8))


def shadow(x, w, y=GROUND_Y):
    screen.pen = SHADOW
    screen.shape(shape.ellipse(x, y, w / 2.6, 2.5))


def meter(name, x, value):
    screen.blit(pets.icon(name), vec2(x, 2))
    pill(x + 14, 5, 34, 6, color.rgb(0, 0, 0, 60))
    low = value < 25 and int(badge.ticks / 300) % 2
    pill(x + 14, 5, max(3, 34 * value / 100), 6, color.rgb(230, 40, 50) if low else METER_COLOURS[name])


def meters(hunger, happy, energy):
    pill(0, 0, screen.width, 16, color.rgb(255, 255, 255, 120))
    meter("feed", 3, hunger)
    meter("heart", 56, happy)
    meter("bolt", 109, energy)


def action_bar(selected):
    screen.pen = color.rgb(30, 26, 50, 210)
    screen.rectangle(0, BAR_Y, screen.width, screen.height - BAR_Y)
    for i, name in enumerate(ACTIONS):
        cx = 13 + i * 27
        if i == selected:
            pill(cx - 10, BAR_Y + 2, 20, 14, color.rgb(255, 255, 255, 230))
        screen.blit(pets.icon(name), vec2(cx - 6, BAR_Y + 3))


def toast(message):
    screen.font = font.ark
    w, h = screen.measure_text(message)
    x = 80 - w / 2
    pill(x - 5, 19, w + 10, h + 4, color.rgb(255, 255, 255, 235))
    text(message, x, 21)


def bubble(x, y, mark, pen):
    pill(x - 5, y - 13, 11, 12, WHITE)
    screen.pen = WHITE
    screen.shape(shape.regular_polygon(x - 2, y - 1, 3, 3))
    text(mark, x, y - 12, pen, centre=True)


def bug(x, y, t):
    wiggle = 1 if int(t / 180) % 2 else -1
    screen.pen = INK
    for dy in (-2, 0, 2):
        screen.shape(shape.line(x - 5, y + dy + wiggle * (dy == 0), x + 5, y + dy - wiggle * (dy == 0), 1))
    screen.pen = color.rgb(220, 60, 70)
    screen.shape(shape.ellipse(x, y, 4, 3.5))
    screen.pen = INK
    screen.shape(shape.circle(x + 4, y - 1, 2))
    screen.shape(shape.line(x, y - 3, x, y + 3, 1))
    screen.pen = WHITE
    screen.shape(shape.circle(x - 2, y - 1, 0.8))


def star(x, y, r, pen):
    screen.pen = pen
    screen.shape(shape.star(x, y, 5, r * 0.5, r))


def egg(x, y, spots, crack, wobble):
    x += math.sin(badge.ticks / 70) * wobble
    screen.pen = SHADOW
    screen.shape(shape.ellipse(x, y + 1, 14, 3))
    screen.pen = color.rgb(250, 248, 240)
    screen.shape(shape.ellipse(x, y - 18, 14, 18))
    screen.pen = color.rgb(*spots)
    screen.shape(shape.circle(x - 6, y - 24, 3))
    screen.shape(shape.circle(x + 5, y - 12, 4))
    screen.shape(shape.circle(x + 6, y - 28, 2))
    screen.shape(shape.circle(x - 4, y - 8, 2))
    if crack:
        screen.pen = INK
        points = ((-12, -20), (-6, -16), (-2, -22), (3, -15), (8, -21), (12, -18))
        for i in range(min(len(points) - 1, int(crack * 5))):
            ax, ay = points[i]
            bx, by = points[i + 1]
            screen.shape(shape.line(x + ax, y + ay, x + bx, y + by, 1.2))


def food(kind, x, y, left):
    """Draw a meal or snack with `left` (0..1) of it still uneaten."""
    if left <= 0:
        return
    s = 0.4 + 0.6 * left
    if kind == "meal":
        w = int(12 * 1.4 * s)
        screen.blit(pets.icon("feed"), rect(int(x - w / 2), int(y - w), w, w))
    else:
        screen.pen = color.rgb(205, 140, 70)
        screen.shape(shape.circle(x, y - 6 * s, 6 * s))
        screen.pen = color.rgb(90, 50, 30)
        screen.shape(shape.circle(x - 2 * s, y - 7 * s, 1.2))
        screen.shape(shape.circle(x + 2 * s, y - 4 * s, 1.2))
        screen.shape(shape.circle(x + 1 * s, y - 9 * s, 1))


def panel(x, y, w, h):
    pill(x + 2, y + 2, w, h, color.rgb(0, 0, 0, 60))
    pill(x, y, w, h, color.rgb(255, 255, 255, 245))

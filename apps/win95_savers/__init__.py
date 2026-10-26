# Win95 Savers: three classic Windows screensavers with a GitHub twist.
#
# LEFT/RIGHT pick a saver, SELECT starts or restarts it, UP toggles
# auto-cycling and BACK returns to the Display Properties dialog (BACK again
# exits). The GitHub mark outline comes from Primer Octicons (MIT licence).

import math
import random

from badgeware import State

NAME = "@ashleywolf"
STATE_KEY = "win95_savers"
SAVERS = ("Solitaire", "Flying Octocats", "Mystify")
DIALOG_MS = 2600
CYCLE_MS = 45000
WIN_BOX_MS = 5000

badge.mode(HIRES | VSYNC)
W, H = screen.width, screen.height
FULL = rect(0, 0, W, H)

BLACK = color.rgb(0, 0, 0)
WHITE = color.rgb(255, 255, 255)
SILVER = color.rgb(192, 192, 192)
LIGHT = color.rgb(223, 223, 223)
GREY = color.rgb(128, 128, 128)
NAVY = color.rgb(0, 0, 128)
TEAL = color.rgb(0, 128, 128)
FELT = color.rgb(0, 128, 0)
FELT_LINE = color.rgb(0, 88, 0)
RED = color.rgb(220, 0, 0)
MERGE = color.rgb(31, 136, 61)
CLEAR = color.rgb(0, 0, 0, 0)
FLAG = (
    color.rgb(237, 28, 36),
    color.rgb(34, 177, 76),
    color.rgb(0, 120, 215),
    color.rgb(255, 201, 14),
)

UI_FONT = font.corset
TITLE_FONT = font.holotype
HINT_FONT = font.winds
CARD_FONT = font.salty

MARK = (
    (-0.154, 0.448), (-0.276, 0.420), (-0.383, 0.369), (-0.471, 0.298),
    (-0.537, 0.210), (-0.579, 0.106), (-0.594, -0.009), (-0.591, -0.058),
    (-0.582, -0.107), (-0.569, -0.156), (-0.550, -0.202), (-0.527, -0.244),
    (-0.500, -0.282), (-0.516, -0.365), (-0.517, -0.414), (-0.513, -0.462),
    (-0.505, -0.506), (-0.451, -0.541), (-0.408, -0.534), (-0.363, -0.521),
    (-0.320, -0.502), (-0.281, -0.479), (-0.246, -0.452), (-0.170, -0.472),
    (-0.088, -0.483), (-0.044, -0.486), (0.002, -0.487), (0.048, -0.486),
    (0.092, -0.483), (0.173, -0.472), (0.246, -0.454), (0.319, -0.503),
    (0.363, -0.521), (0.407, -0.534), (0.451, -0.541), (0.504, -0.507),
    (0.515, -0.417), (0.514, -0.368), (0.508, -0.322), (0.527, -0.245),
    (0.551, -0.202), (0.569, -0.157), (0.583, -0.109), (0.591, -0.059),
    (0.594, -0.009), (0.579, 0.106), (0.537, 0.209), (0.470, 0.296),
    (0.382, 0.367), (0.274, 0.418), (0.150, 0.446), (0.209, 0.505),
    (0.231, 0.544), (0.248, 0.589), (0.258, 0.638), (0.262, 0.690),
    (0.262, 0.894), (0.277, 0.943), (0.315, 0.968), (0.369, 0.962),
    (0.539, 0.877), (0.690, 0.759), (0.817, 0.613), (0.915, 0.441),
    (0.978, 0.247), (1.000, 0.036), (0.964, -0.230), (0.863, -0.470),
    (0.706, -0.673), (0.503, -0.830), (0.264, -0.932), (-0.002, -0.968),
    (-0.268, -0.932), (-0.506, -0.830), (-0.708, -0.673), (-0.864, -0.470),
    (-0.964, -0.230), (-1.000, 0.036), (-0.978, 0.246), (-0.915, 0.440),
    (-0.816, 0.612), (-0.686, 0.760), (-0.530, 0.879), (-0.353, 0.964),
    (-0.303, 0.967), (-0.265, 0.941), (-0.250, 0.896), (-0.250, 0.739),
    (-0.296, 0.753), (-0.344, 0.759), (-0.404, 0.753), (-0.456, 0.736),
    (-0.501, 0.707), (-0.541, 0.668), (-0.574, 0.618), (-0.603, 0.558),
    (-0.626, 0.512), (-0.673, 0.473), (-0.718, 0.460), (-0.700, 0.415),
    (-0.647, 0.403), (-0.592, 0.415), (-0.541, 0.451), (-0.490, 0.511),
    (-0.450, 0.557), (-0.408, 0.584), (-0.361, 0.593), (-0.317, 0.587),
    (-0.278, 0.566), (-0.236, 0.530), (-0.206, 0.499),
)
MARK_SHAPE = shape.custom([vec2(x, y) for x, y in MARK])


def draw_mark(img, cx, cy, r):
    MARK_SHAPE.transform = mat3().translate(cx, cy).scale(r, r)
    img.shape(MARK_SHAPE)


# ---- Win95 chrome --------------------------------------------------------------

def box(img, x, y, w, h, tl, br, inner_tl, inner_br, fill=SILVER):
    if fill is not None:
        img.pen = fill
        img.rectangle(x, y, w, h)
    img.pen = br
    img.rectangle(x, y + h - 1, w, 1)
    img.rectangle(x + w - 1, y, 1, h)
    img.pen = tl
    img.rectangle(x, y, w - 1, 1)
    img.rectangle(x, y, 1, h - 1)
    img.pen = inner_br
    img.rectangle(x + 1, y + h - 2, w - 2, 1)
    img.rectangle(x + w - 2, y + 1, 1, h - 2)
    img.pen = inner_tl
    img.rectangle(x + 1, y + 1, w - 3, 1)
    img.rectangle(x + 1, y + 1, 1, h - 3)


def raised(x, y, w, h, fill=SILVER):
    box(screen, x, y, w, h, WHITE, BLACK, LIGHT, GREY, fill)


def pressed_in(x, y, w, h, fill=SILVER):
    box(screen, x, y, w, h, BLACK, WHITE, GREY, LIGHT, fill)


def sunken(x, y, w, h, fill=WHITE):
    box(screen, x, y, w, h, GREY, WHITE, BLACK, LIGHT, fill)


def window(x, y, w, h, title):
    box(screen, x, y, w, h, LIGHT, BLACK, WHITE, GREY)
    screen.pen = NAVY
    screen.rectangle(x + 3, y + 3, w - 6, 14)
    screen.font = TITLE_FONT
    screen.pen = WHITE
    screen.text(title, x + 6, y + 2)
    raised(x + w - 19, y + 5, 14, 11)
    screen.pen = BLACK
    screen.shape(shape.line(x + w - 15, y + 7, x + w - 9, y + 13, 1.5))
    screen.shape(shape.line(x + w - 9, y + 7, x + w - 15, y + 13, 1.5))


def label(text, x, y, pen=BLACK):
    screen.font = UI_FONT
    screen.pen = pen
    screen.text(text, x, y)


def button(text, x, y, w, h=18, down=False, fill=SILVER, pen=BLACK):
    (pressed_in if down else raised)(x, y, w, h, fill)
    tw, th = screen.measure_text(text)
    off = 1 if down else 0
    label(text, x + (w - tw) // 2 + off, y + (h - th) // 2 + off, pen)


def etched(x, y, w, h):
    screen.pen = GREY
    screen.rectangle(x, y, w - 1, 1)
    screen.rectangle(x, y, 1, h - 1)
    screen.rectangle(x, y + h - 2, w - 1, 1)
    screen.rectangle(x + w - 2, y, 1, h - 1)
    screen.pen = WHITE
    screen.rectangle(x + 1, y + 1, w - 3, 1)
    screen.rectangle(x + 1, y + 1, 1, h - 3)
    screen.rectangle(x, y + h - 1, w, 1)
    screen.rectangle(x + w - 1, y, 1, h)


def taskbar():
    screen.pen = SILVER
    screen.rectangle(0, H - 20, W, 20)
    screen.pen = WHITE
    screen.rectangle(0, H - 19, W, 1)
    raised(2, H - 17, 54, 15)
    screen.antialias = image.X4
    for i, pen in enumerate(FLAG):
        screen.pen = pen
        screen.rectangle(6 + (i % 2) * 6, H - 15 + (i // 2) * 6, 5, 5)
    screen.font = TITLE_FONT
    screen.pen = BLACK
    screen.text("Start", 20, H - 17)
    screen.font = UI_FONT
    tw, _ = screen.measure_text(NAME)
    sunken(W - tw - 14, H - 17, tw + 12, 15, SILVER)
    label(NAME, W - tw - 8, H - 17)
    screen.font = HINT_FONT
    screen.pen = GREY
    screen.text("L/R pick  SELECT preview  UP cycle", 62, H - 16)


# ---- cards ---------------------------------------------------------------------

CW, CH = 38, 52
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
# Spades, hearts, clubs, diamonds: alternating colours like Windows.
SUIT_RED = (False, True, False, True)
PIPS = (
    (),
    ((1, 0), (1, 4)),
    ((1, 0), (1, 2), (1, 4)),
    ((0, 0), (2, 0), (0, 4), (2, 4)),
    ((0, 0), (2, 0), (1, 2), (0, 4), (2, 4)),
    ((0, 0), (2, 0), (0, 2), (2, 2), (0, 4), (2, 4)),
    ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2), (0, 4), (2, 4)),
    ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2), (1, 3), (0, 4), (2, 4)),
    ((0, 0), (2, 0), (0, 1.33), (2, 1.33), (1, 2), (0, 2.67), (2, 2.67),
     (0, 4), (2, 4)),
    ((0, 0), (2, 0), (1, 0.67), (0, 1.33), (2, 1.33), (0, 2.67), (2, 2.67),
     (1, 3.33), (0, 4), (2, 4)),
)


def poly(img, *points):
    img.shape(shape.custom([vec2(x, y) for x, y in points]))


def suit(img, kind, cx, cy, s):
    h = s / 2
    if kind == 0 or kind == 2:
        if kind == 0:
            img.shape(shape.circle(cx - h, cy + s * 0.2, h))
            img.shape(shape.circle(cx + h, cy + s * 0.2, h))
            poly(img, (cx - s, cy + s * 0.15), (cx, cy - s), (cx + s, cy + s * 0.15))
        else:
            r = s * 0.42
            img.shape(shape.circle(cx, cy - s * 0.45, r))
            img.shape(shape.circle(cx - s * 0.5, cy + s * 0.15, r))
            img.shape(shape.circle(cx + s * 0.5, cy + s * 0.15, r))
        poly(img, (cx, cy), (cx - h, cy + s), (cx + h, cy + s))
    elif kind == 1:
        img.shape(shape.circle(cx - h, cy - s * 0.3, h))
        img.shape(shape.circle(cx + h, cy - s * 0.3, h))
        poly(img, (cx - s, cy - s * 0.2), (cx + s, cy - s * 0.2), (cx, cy + s))
    else:
        poly(img, (cx, cy - s), (cx + s * 0.72, cy), (cx, cy + s), (cx - s * 0.72, cy))


def card_blank(img):
    img.pen = CLEAR
    img.clear()
    img.antialias = image.X4
    img.pen = BLACK
    img.shape(shape.rounded_rectangle(0, 0, CW, CH, 3))
    img.pen = WHITE
    img.shape(shape.rounded_rectangle(1, 1, CW - 2, CH - 2, 2))


def render_card(img, rank, kind):
    card_blank(img)
    ink = RED if SUIT_RED[kind] else BLACK
    img.pen = ink
    img.font = CARD_FONT
    text = RANKS[rank]
    img.text(text, 3, 1)
    tw, th = img.measure_text(text)
    img.text(text, CW - tw - 3, CH - th - 1)
    suit(img, kind, 6, 18, 2.6)
    suit(img, kind, CW - 7, CH - 19, 2.6)
    if rank == 0:
        suit(img, kind, CW / 2, CH / 2, 8)
    elif rank >= 10:
        # Face cards are GitHub cards: the mark sits in a gold frame.
        img.pen = color.rgb(255, 214, 102)
        img.rectangle(9, 10, CW - 18, CH - 20)
        img.pen = ink
        img.rectangle(9, 10, CW - 18, 1)
        img.rectangle(9, CH - 11, CW - 18, 1)
        img.rectangle(9, 10, 1, CH - 20)
        img.rectangle(CW - 10, 10, 1, CH - 20)
        draw_mark(img, CW / 2, CH / 2, 9)
    else:
        for col, row in PIPS[rank]:
            suit(img, kind, CW / 2 + (col - 1) * 6, 15 + row * 6, 3)


def render_back(img):
    card_blank(img)
    img.pen = NAVY
    img.shape(shape.rounded_rectangle(3, 3, CW - 6, CH - 6, 2))
    img.pen = color.rgb(40, 80, 200)
    for i in range(-CH, CW, 5):
        img.shape(shape.line(3 + i, 3, 3 + i + CH, 3 + CH, 1))
    img.pen = WHITE
    draw_mark(img, CW / 2, CH / 2, 11)


# ---- savers --------------------------------------------------------------------

CARD = image(CW, CH)
FOUND_X = tuple(W - 4 * (CW + 6) + i * (CW + 6) for i in range(4))
STEP_MS = 16


def empty_slot(x, y):
    screen.antialias = image.X4
    screen.pen = FELT_LINE
    screen.shape(shape.rounded_rectangle(x, y, CW, CH, 3))
    screen.pen = FELT
    screen.shape(shape.rounded_rectangle(x + 1, y + 1, CW - 2, CH - 2, 2))


class Solitaire:
    name = "Solitaire"

    def start(self):
        self.order = [(r, s) for r in range(12, -1, -1) for s in range(4)]
        self.index = 0
        self.card = None
        self.delay = 700
        self.acc = 0
        self.won = None
        screen.pen = FELT
        screen.clear()
        render_back(CARD)
        screen.blit(CARD, vec2(6, 6))
        empty_slot(6 + CW + 6, 6)
        for kind, x in enumerate(FOUND_X):
            render_card(CARD, 12, kind)
            screen.blit(CARD, vec2(x, 6))

    def launch(self):
        rank, kind = self.order[self.index]
        x = FOUND_X[kind]
        if rank:
            render_card(CARD, rank - 1, kind)
            screen.blit(CARD, vec2(x, 6))
        else:
            empty_slot(x, 6)
        render_card(CARD, rank, kind)
        vx = random.uniform(1.8, 4.6) * random.choice((-1, 1))
        self.card = [x, 6.0, vx, -random.uniform(0.0, 4.0)]

    def update(self, dt):
        if self.won is not None:
            self.won += dt
            return
        if self.card is None:
            self.delay -= dt
            if self.delay > 0:
                return
            if self.index >= len(self.order):
                self.won = 0
                win_box()
                return
            self.launch()
        self.acc = min(self.acc + dt, STEP_MS * 6)
        card = self.card
        while self.acc >= STEP_MS and card is not None:
            self.acc -= STEP_MS
            card[0] += card[2]
            card[3] += 0.32
            card[1] += card[3]
            if card[1] > H - CH:
                card[1] = H - CH
                card[3] = -card[3] * random.uniform(0.7, 0.85)
            screen.blit(CARD, vec2(int(card[0]), int(card[1])))
            if card[0] < -CW or card[0] > W:
                self.index += 1
                self.card = card = None
                self.delay = 0

    def done(self):
        return self.won is not None and self.won > WIN_BOX_MS

    def restart_when_done(self):
        if self.done():
            self.start()


def win_box():
    x, y, w, h = 50, 72, 220, 96
    window(x, y, w, h, "Solitaire")
    screen.antialias = image.X4
    screen.pen = MERGE
    screen.shape(shape.circle(x + 26, y + 40, 12))
    screen.pen = WHITE
    screen.shape(shape.line(x + 20, y + 40, x + 24, y + 45, 3))
    screen.shape(shape.line(x + 24, y + 45, x + 33, y + 34, 3))
    label("Congratulations, you won!", x + 46, y + 26)
    label("All 52 checks have passed.", x + 46, y + 40)
    button("Merge", x + 50, y + h - 28, 60, fill=MERGE, pen=WHITE)
    button("Deal Again", x + 120, y + h - 28, 80)


class Flying:
    name = "Flying Octocats"
    COUNT = 16
    STARS = 40

    def __init__(self):
        self.sprite = None

    def make_sprite(self):
        size = 64
        img = image(size, size)
        img.pen = CLEAR
        img.clear()
        img.antialias = image.X4
        half = size // 2
        img.pen = WHITE
        img.shape(shape.circle(half, half, half - 3))
        for i, pen in enumerate(FLAG):
            img.clip = rect((i % 2) * half, (i // 2) * half, half, half)
            img.pen = pen
            draw_mark(img, half, half, half - 1)
        img.clip = rect(0, 0, size, size)
        return img

    def spawn(self, z):
        while True:
            x, y = random.uniform(-1, 1), random.uniform(-1, 1)
            if abs(x) > 0.18 or abs(y) > 0.18:
                return [x, y, z]

    def start(self):
        if self.sprite is None:
            self.sprite = self.make_sprite()
        self.logos = [self.spawn(random.uniform(0.15, 1.0)) for _ in range(self.COUNT)]
        self.stars = [self.spawn(random.uniform(0.1, 1.0)) for _ in range(self.STARS)]

    def update(self, dt):
        screen.pen = BLACK
        screen.clear()
        cx, cy = W / 2, H / 2
        step = dt * 0.00028
        for star in self.stars:
            star[2] -= step * 1.6
            if star[2] < 0.05:
                star[:] = self.spawn(1.0)
            z = star[2]
            v = int(90 + 165 * min(1.0, 1.0 - z))
            screen.pen = color.rgb(v, v, v)
            s = 1 if z > 0.4 else 2
            screen.rectangle(int(cx + star[0] * 160 / z), int(cy + star[1] * 120 / z), s, s)
        for logo in self.logos:
            logo[2] -= step
            if logo[2] < 0.09:
                logo[:] = self.spawn(1.0)
        self.logos.sort(key=lambda logo: -logo[2])
        sprite = self.sprite
        for x, y, z in self.logos:
            size = int(15 / z)
            px = int(cx + x * 110 / z - size / 2)
            py = int(cy + y * 85 / z - size / 2)
            if px > W or py > H or px + size < 0 or py + size < 0:
                continue
            sprite.alpha = int(255 * min(1.0, 1.15 - z))
            screen.blit(sprite, rect(px, py, size, size))

    def done(self):
        return False


class Mystify:
    name = "Mystify"
    ECHOES = 7
    STEP = 35

    def start(self):
        screen.pen = BLACK
        screen.clear()
        self.acc = 0
        self.t = 0
        self.polys = []
        for hue in (95, 215):
            points = [[random.uniform(10, W - 10), random.uniform(10, H - 10),
                       random.uniform(3.0, 6.5) * random.choice((-1, 1)),
                       random.uniform(3.0, 6.5) * random.choice((-1, 1))]
                      for _ in range(4)]
            self.polys.append([points, [], hue])

    def draw(self, coords):
        for i in range(4):
            j = (i + 1) % 4
            screen.line(coords[i * 2], coords[i * 2 + 1], coords[j * 2], coords[j * 2 + 1])

    def update(self, dt):
        self.acc = min(self.acc + dt, self.STEP * 4)
        screen.antialias = image.OFF
        while self.acc >= self.STEP:
            self.acc -= self.STEP
            self.t += 1
            for points, echoes, hue in self.polys:
                coords = []
                for p in points:
                    p[0] += p[2]
                    p[1] += p[3]
                    if p[0] < 0 or p[0] > W - 1:
                        p[2] = -p[2]
                        p[0] = min(max(p[0], 0), W - 1)
                    if p[1] < 0 or p[1] > H - 1:
                        p[3] = -p[3]
                        p[1] = min(max(p[1], 0), H - 1)
                    coords.append(int(p[0]))
                    coords.append(int(p[1]))
                # GitHub greens on one, Copilot purples and pinks on the other.
                h = hue + 28 * math.sin(self.t / 40 + hue)
                echoes.append((coords, color.hsv(int(h) % 256, 200, 255)))
                if len(echoes) > self.ECHOES:
                    old, _ = echoes.pop(0)
                    screen.pen = BLACK
                    self.draw(old)
            for _, echoes, _ in self.polys:
                for coords, pen in echoes:
                    screen.pen = pen
                    self.draw(coords)

    def done(self):
        return False


# ---- thumbnails for the dialog monitor -----------------------------------------

def thumb(kind, x, y, w, h, flying):
    screen.clip = rect(x, y, w, h)
    screen.antialias = image.X4
    if kind == 0:
        screen.pen = FELT
        screen.rectangle(x, y, w, h)
        for i in range(9):
            t = i / 8
            cx = x + 6 + t * (w - 18)
            cy = y + 4 + abs(math.cos(t * 5.5)) * (h - 18) * (0.4 + t * 0.6)
            screen.pen = BLACK
            screen.rectangle(int(cx), int(cy), 10, 14)
            screen.pen = WHITE
            screen.rectangle(int(cx) + 1, int(cy) + 1, 8, 12)
            screen.pen = RED if i % 2 else BLACK
            suit(screen, (i % 4), cx + 5, cy + 7, 2.5)
    else:
        screen.pen = BLACK
        screen.rectangle(x, y, w, h)
        if kind == 1:
            sprite = flying.sprite or flying.make_sprite()
            flying.sprite = sprite
            for sx, sy, s in ((0.2, 0.25, 10), (0.7, 0.2, 14), (0.45, 0.55, 24),
                              (0.82, 0.7, 12), (0.12, 0.72, 8)):
                sprite.alpha = 255
                screen.blit(sprite, rect(int(x + sx * w - s / 2), int(y + sy * h - s / 2), s, s))
        else:
            for k, (hue, pts) in enumerate(((95, (0.1, 0.2, 0.6, 0.1, 0.8, 0.6, 0.3, 0.8)),
                                            (205, (0.5, 0.3, 0.9, 0.4, 0.7, 0.9, 0.2, 0.55)))):
                for e in range(4):
                    screen.pen = color.hsv(hue + e * 6, 230, 255 - e * 30)
                    c = [int((x if i % 2 == 0 else y) + v * (w if i % 2 == 0 else h)) + e * 3
                         for i, v in enumerate(pts)]
                    for i in range(4):
                        j = (i + 1) % 4
                        screen.line(c[i * 2], c[i * 2 + 1], c[j * 2], c[j * 2 + 1])
    screen.clip = FULL


# ---- app -----------------------------------------------------------------------

class App:
    def __init__(self):
        self.data = {"saver": 0, "cycle": True}
        State.load(STATE_KEY, self.data)
        self.data["saver"] = int(self.data.get("saver", 0)) % len(SAVERS)
        self.savers = (Solitaire(), Flying(), Mystify())
        self.show_dialog()

    @property
    def saver(self):
        return self.savers[self.data["saver"]]

    def save(self):
        State.save(STATE_KEY, self.data)

    def show_dialog(self):
        self.mode = "dialog"
        self.timer = 0
        self.preview_down = False
        self.draw_dialog()

    def start_saver(self):
        self.mode = "saver"
        self.timer = 0
        self.saver.start()

    def pick(self, delta):
        self.data["saver"] = (self.data["saver"] + delta) % len(SAVERS)
        self.save()

    def draw_dialog(self):
        screen.fill_rule = image.EVEN_ODD
        screen.antialias = image.X4
        screen.pen = TEAL
        screen.clear()
        taskbar()
        x, y, w, h = 22, 4, 276, 212
        window(x, y, w, h, "Display Properties")
        px, py, pw, ph = x + 6, y + 37, w - 12, h - 65
        box(screen, px, py, pw, ph, WHITE, BLACK, LIGHT, GREY)
        screen.font = UI_FONT
        tabs = []
        tx = px
        for name in ("Background", "Screen Saver", "Appearance"):
            tw = screen.measure_text(name)[0] + 12
            tabs.append((name, tx, tw))
            tx += tw
        for name, tx, tw in tabs:
            if name != "Screen Saver":
                raised(tx, y + 23, tw, py - y - 21)
                label(name, tx + 6, y + 24)
        screen.pen = WHITE
        screen.rectangle(px, py, pw - 1, 1)
        screen.pen = LIGHT
        screen.rectangle(px + 1, py + 1, pw - 3, 1)
        name, tx, tw = tabs[1]
        raised(tx - 2, y + 20, tw + 4, py - y - 17)
        screen.pen = SILVER
        screen.rectangle(tx, py - 1, tw, 4)
        label(name, tx + 4, y + 21)

        # The classic monitor that previews the saver.
        mx = x + w // 2 - 50
        my = py + 6
        raised(mx, my, 100, 70)
        sunken(mx + 7, my + 6, 86, 58, BLACK)
        thumb(self.data["saver"], mx + 9, my + 8, 82, 54, self.savers[1])
        raised(mx + 30, my + 70, 40, 6)
        raised(mx + 18, my + 76, 64, 5)

        gx, gy = px + 6, py + 90
        etched(gx, gy, pw - 12, 52)
        screen.pen = SILVER
        screen.rectangle(gx + 6, gy - 2, 66, 6)
        label("Screen Saver", gx + 8, gy - 5)
        sunken(gx + 8, gy + 10, 150, 18)
        label(SAVERS[self.data["saver"]], gx + 13, gy + 13)
        raised(gx + 142, gy + 12, 14, 14)
        screen.pen = BLACK
        poly(screen, (gx + 145, gy + 17), (gx + 153, gy + 17), (gx + 149, gy + 21))
        button("Preview", gx + 166, gy + 10, 70, down=self.preview_down)
        sunken(gx + 8, gy + 33, 12, 12)
        if self.data["cycle"]:
            screen.pen = BLACK
            screen.shape(shape.line(gx + 11, gy + 39, gx + 13, gy + 42, 2))
            screen.shape(shape.line(gx + 13, gy + 42, gx + 18, gy + 36, 2))
        label("Cycle all three savers", gx + 26, gy + 33)

        by = y + h - 24
        button("OK", x + w - 196, by, 58)
        button("Cancel", x + w - 132, by, 58)
        button("Apply", x + w - 68, by, 58)

    def update(self):
        dt = min(badge.ticks_delta, 100)
        if self.mode == "dialog":
            self.update_dialog(dt)
        else:
            self.update_saver(dt)

    def update_dialog(self, dt):
        if badge.pressed(BUTTON_BACK):
            reset()
            return
        changed = False
        if badge.pressed(BUTTON_LEFT):
            self.pick(-1)
            changed = True
        if badge.pressed(BUTTON_RIGHT):
            self.pick(1)
            changed = True
        if badge.pressed(BUTTON_UP):
            self.data["cycle"] = not self.data["cycle"]
            self.save()
            changed = True
        if changed:
            self.timer = 0
            self.preview_down = False
            self.draw_dialog()
            return
        if badge.pressed(BUTTON_SELECT):
            self.timer = DIALOG_MS
        self.timer += dt
        if not self.preview_down and self.timer >= DIALOG_MS - 250:
            self.preview_down = True
            self.draw_dialog()
        if self.timer >= DIALOG_MS:
            self.start_saver()

    def update_saver(self, dt):
        if badge.pressed(BUTTON_BACK):
            self.show_dialog()
            return
        if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            self.pick(1 if badge.pressed(BUTTON_RIGHT) else -1)
            self.show_dialog()
            return
        if badge.pressed(BUTTON_UP):
            self.data["cycle"] = not self.data["cycle"]
            self.save()
            self.show_dialog()
            return
        if badge.pressed(BUTTON_SELECT):
            self.start_saver()
            return
        self.timer += dt
        saver = self.saver
        saver.update(dt)
        if self.data["cycle"]:
            if saver.done() or (isinstance(saver, Solitaire) is False and self.timer > CYCLE_MS):
                self.pick(1)
                self.show_dialog()
        elif isinstance(saver, Solitaire):
            saver.restart_when_done()


_previous_clear = badge.default_clear
badge.default_clear = None
app = App()


def update():
    app.update()


def on_exit():
    badge.default_clear = _previous_clear


run(update)

"""@ashleywolf bounces like the classic DVD screensaver on the 2026 badge."""

import gc
import math
import os
import random
import sys

APP_DIR = "/system/apps/bouncing_logo"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)
WIDTH, HEIGHT = screen.width, screen.height
BLACK = color.rgb(0, 0, 0)
badge.default_clear = BLACK

USERNAME = "@ashleywolf"
FONT = font.load("/system/assets/fonts/MonaSans-Medium.af")
FONT_SIZE = 35
SLANT = 0.2
LOGO_W, LOGO_H = 190, 32

# Travel ranges share a 26 px lattice. Holding the diagonal path on that
# lattice makes exactly one corner hit every lcm(130, 208) px of travel.
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


RANGE_X, RANGE_Y = WIDTH - LOGO_W, HEIGHT - LOGO_H
LATTICE = gcd(RANGE_X, RANGE_Y)
AXIS_SPEED = 50.0
SPEED = AXIS_SPEED * math.sqrt(2)
CORNER_PERIOD = RANGE_X * RANGE_Y / LATTICE / AXIS_SPEED
CORNER_TOLERANCE = 0.75
NUDGE_SPEED = 6.0

IMU_GRAVITY = 16384.0
TILT_DEAD = 0.15
TILT_FULL = 0.45
TILT_SMOOTH = 0.2
TILT_RECENTRE = 3.0
TURN_RATE = 3.0
RETURN_RATE = 1.4
STEER_HOLD = 0.5

CELEBRATION = 1.4
FLASH_STEP = 0.09
PALETTE = (
    (40, 140, 255), (255, 70, 170), (255, 210, 20), (60, 225, 100),
    (175, 100, 255), (255, 130, 40), (20, 220, 235), (255, 75, 75),
)
CASE_LIGHTS = hasattr(badge, "caselights")
DIAGONALS = (math.pi / 4, 3 * math.pi / 4, -3 * math.pi / 4, -math.pi / 4)


def clamp(value, low, high):
    return min(high, max(low, value))


def wrap(angle):
    return (angle + math.pi) % math.tau - math.pi


class Logo:
    """Pre-renders the slanted name; repaints only when color changes.

    Images are cleared to opaque black because a transparent pen does not
    erase existing pixels, and the screen behind the logo is black anyway.
    """

    def __init__(self):
        probe = image(LOGO_W + 40, FONT_SIZE * 2)
        probe.font = FONT
        probe.antialias = image.X4
        probe.fill_rule = image.EVEN_ODD
        self.text = probe
        self.art = image(LOGO_W, LOGO_H)
        self.art.antialias = image.X4
        self.art.fill_rule = image.EVEN_ODD
        self.draw_text(color.rgb(255, 255, 255), 8, 8)
        top, bottom, left, right = self.ink_bounds()
        self.rows = bottom - top + 1
        self.shift = int(self.rows * SLANT + 0.5)
        width = right - left + 1 + self.shift
        self.text_x = 8 - left
        self.text_y = 8 - top
        self.dest_x = (LOGO_W - width) // 2
        self.dest_y = (LOGO_H - self.rows) // 2
        self.text_width = right - left + 1
        self.rgb = None
        self.paint(PALETTE[0])

    def draw_text(self, pen, x, y):
        self.text.pen = BLACK
        self.text.clear()
        self.text.pen = pen
        for dx in (0, 0.6, 1.2, 1.8):
            self.text.text(USERNAME, x + dx, y, font_size=FONT_SIZE)

    def ink_bounds(self):
        get = self.text.get
        w, h = self.text.width, self.text.height
        rows = [y for y in range(h) if any(get(x, y).r > 64 for x in range(w))]
        cols = [x for x in range(w) if any(get(x, y).r > 64 for y in rows)]
        return rows[0], rows[-1], cols[0], cols[-1]

    def paint(self, rgb):
        self.rgb = rgb
        pen = color.rgb(*rgb)
        self.draw_text(pen, self.text_x, self.text_y)
        art = self.art
        art.pen = BLACK
        art.clear()
        for row in range(self.rows):
            offset = int((self.rows - 1 - row) * SLANT + 0.5)
            art.blit(self.text, rect(0, row, self.text_width, 1),
                     rect(self.dest_x + offset, self.dest_y + row, self.text_width, 1))


class Tilt:
    """Turns raw accelerometer gravity into a filtered on-screen 'downhill' lean."""

    def __init__(self):
        self.rest = None
        self.inverted = None
        self.x = self.y = 0.0
        self.strength = 0.0

    def update(self, dt):
        reading = badge.imu()
        inverted = badge.upside_down()
        if not (reading[0] or reading[1] or reading[2]):
            self.x = self.y = self.strength = 0.0
            return 0.0
        sign = -1 if inverted else 1
        lx = sign * reading[0] / IMU_GRAVITY
        ly = sign * reading[1] / IMU_GRAVITY
        if self.rest is None or inverted != self.inverted:
            self.rest = [lx, ly]
            self.inverted = inverted
            self.x = self.y = 0.0
        recentre = 1 - math.exp(-dt / TILT_RECENTRE)
        self.rest[0] += (lx - self.rest[0]) * recentre
        self.rest[1] += (ly - self.rest[1]) * recentre
        smooth = 1 - math.exp(-dt / TILT_SMOOTH)
        self.x += (clamp(lx - self.rest[0], -1, 1) - self.x) * smooth
        self.y += (clamp(ly - self.rest[1], -1, 1) - self.y) * smooth
        lean = math.sqrt(self.x * self.x + self.y * self.y)
        self.strength = clamp((lean - TILT_DEAD) / (TILT_FULL - TILT_DEAD), 0, 1)
        return self.strength


class Bouncer:
    """Constant-speed motion with exact wall and corner hit detection."""

    def __init__(self, first_corner=None):
        self.hold = 0.0
        self.residual = None
        self.bounces = 0
        self.corners = 0
        corner = random.randrange(4)
        self.x = RANGE_X if corner & 1 else 0
        self.y = RANGE_Y if corner & 2 else 0
        self.vx = -AXIS_SPEED if corner & 1 else AXIS_SPEED
        self.vy = -AXIS_SPEED if corner & 2 else AXIS_SPEED
        self.diagonal = True
        if first_corner is None:
            first_corner = random.uniform(8, 16)
        # Start on a corner, then fast-forward so the next corner is first_corner away.
        remaining = CORNER_PERIOD - first_corner
        while remaining > 0:
            step = min(0.05, remaining)
            self.move(step)
            remaining -= step
        self.bounces = self.corners = 0

    def heading(self):
        return math.atan2(self.vy, self.vx)

    def set_heading(self, angle):
        self.vx = SPEED * math.cos(angle)
        self.vy = SPEED * math.sin(angle)
        self.diagonal = False

    def lattice_error(self):
        dx = RANGE_X - self.x if self.vx > 0 else self.x
        dy = RANGE_Y - self.y if self.vy > 0 else self.y
        error = (dx - dy) % LATTICE
        return error - LATTICE if error > LATTICE / 2 else error

    def steer(self, lean_x, lean_y, strength, dt):
        if strength > 0:
            self.hold = STEER_HOLD
            heading = self.heading()
            turn = clamp(wrap(math.atan2(lean_y, lean_x) - heading),
                         -TURN_RATE * strength * dt, TURN_RATE * strength * dt)
            if turn:
                self.set_heading(heading + turn)
            return
        if self.hold > 0:
            self.hold -= dt
            return
        if not self.diagonal:
            heading = self.heading()
            target = min(DIAGONALS, key=lambda d: abs(wrap(d - heading)))
            difference = wrap(target - heading)
            if abs(difference) <= RETURN_RATE * dt:
                self.vx = AXIS_SPEED if self.vx > 0 else -AXIS_SPEED
                self.vy = AXIS_SPEED if self.vy > 0 else -AXIS_SPEED
                self.diagonal = True
            else:
                self.set_heading(heading + (RETURN_RATE * dt if difference > 0 else -RETURN_RATE * dt))
            return
        error = self.lattice_error()
        if error:
            half = clamp(error, -NUDGE_SPEED * dt, NUDGE_SPEED * dt) / 2
            self.x = clamp(self.x + (half if self.vx > 0 else -half), 0, RANGE_X)
            self.y = clamp(self.y + (-half if self.vy > 0 else half), 0, RANGE_Y)
            if abs(self.lattice_error()) < 1e-6:
                self.x = round(self.x * 1e6) / 1e6
                self.y = round(self.y * 1e6) / 1e6

    def move(self, dt):
        """Advance; return None, ("wall", None) or ("corner", (x, y))."""
        hit_x = hit_y = None
        x = self.x + self.vx * dt
        y = self.y + self.vy * dt
        if self.vx > 0 and x >= RANGE_X:
            hit_x = (RANGE_X - self.x) / self.vx
            x = 2 * RANGE_X - x
            self.vx = -self.vx
        elif self.vx < 0 and x <= 0:
            hit_x = self.x / -self.vx
            x = -x
            self.vx = -self.vx
        if self.vy > 0 and y >= RANGE_Y:
            hit_y = (RANGE_Y - self.y) / self.vy
            y = 2 * RANGE_Y - y
            self.vy = -self.vy
        elif self.vy < 0 and y <= 0:
            hit_y = self.y / -self.vy
            y = -y
            self.vy = -self.vy
        self.x = clamp(x, 0, RANGE_X)
        self.y = clamp(y, 0, RANGE_Y)
        if hit_x is None and hit_y is None:
            return None
        self.bounces += 1
        if hit_x is not None and hit_y is not None and \
                abs(hit_x - hit_y) * SPEED <= CORNER_TOLERANCE:
            self.corners += 1
            self.residual = abs(hit_x - hit_y) * SPEED
            return ("corner", (WIDTH if self.vx < 0 else 0, HEIGHT if self.vy < 0 else 0))
        return ("wall", None)


class Celebration:
    def __init__(self):
        self.t = CELEBRATION
        self.origin = (0, 0)
        self.flash = -1

    def active(self):
        return self.t < CELEBRATION

    def start(self, origin):
        self.t = 0.0
        self.origin = origin
        self.flash = -1

    def update(self, dt):
        if not self.active():
            return
        self.t += dt
        if self.t >= CELEBRATION:
            logo.paint(new_color(logo.rgb))
            lights(0)
            return
        flash = int(self.t / FLASH_STEP)
        if flash != self.flash:
            self.flash = flash
            start = PALETTE.index(logo.rgb) if logo.rgb in PALETTE else 0
            logo.paint(PALETTE[(start + 1) % len(PALETTE)])
        fade = 1 - self.t / CELEBRATION
        lights(fade if flash % 2 == 0 else fade * 0.25)

    def draw(self):
        if not self.active():
            return
        fade = 1 - self.t / CELEBRATION
        r, g, b = logo.rgb
        for ring in range(3):
            radius = (self.t - ring * 0.16) * 260
            if radius > 4:
                screen.pen = color.rgb(r, g, b, int(255 * fade))
                screen.shape(shape.circle(self.origin[0], self.origin[1], radius).stroke(4))


def lights(level):
    if CASE_LIGHTS:
        badge.caselights(clamp(level, 0, 1))


def new_color(current):
    return random.choice([rgb for rgb in PALETTE if rgb != current])


logo = Logo()
logo.paint(random.choice(PALETTE))
tilt = Tilt()
bouncer = Bouncer()
party = Celebration()
gc.collect()


def advance(dt):
    bouncer.steer(tilt.x, tilt.y, tilt.update(dt), dt)
    hit = bouncer.move(dt)
    if hit:
        if hit[0] == "corner":
            print("corner hit", bouncer.corners, hit[1])
            party.start(hit[1])
        elif not party.active():
            logo.paint(new_color(logo.rgb))
    party.update(dt)


def update():
    if badge.pressed(BUTTON_BACK):
        reset()
    advance(clamp(badge.ticks_delta / 1000, 0, 0.1))
    screen.pen = BLACK
    screen.clear()
    screen.blit(logo.art, vec2(int(bouncer.x + 0.5), int(bouncer.y + 0.5)))
    party.draw()


def on_exit():
    lights(0)


run(update)

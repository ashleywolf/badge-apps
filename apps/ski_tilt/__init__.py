import math
import os
import sys

APP_DIR = "/system/apps/ski_tilt"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State

STATE_KEY = "ski_tilt"
saved = {"best": 0, "flip": False}
State.load(STATE_KEY, saved)

# World units are screen pixels; the skier stays fixed on screen and the
# slope scrolls past. Downhill is +y.
M_PER_PX = 0.5
SKIER_X = 80
SKIER_Y = 42
CELL = 32
CRUISE = 46.0
BOOST = 1.6
MAX_HEADING = math.radians(80)
FULL_TILT = math.radians(30)
DEAD_ZONE = math.radians(3)
MAX_LEAN = 35.0
GRAVITY = 220.0
SPIN_TIME = 0.4
YETI_AT_M = 2000

SNOW = color.rgb(246, 249, 255)
SPECK = color.rgb(222, 232, 246)
TRACK = color.rgb(200, 212, 230)
SHADOW = color.rgb(200, 210, 228)
INK = color.rgb(30, 34, 48)
SKI = color.rgb(36, 41, 61)
PANTS = color.rgb(40, 52, 110)
JACKET = color.rgb(130, 80, 223)
SCARF = color.rgb(255, 170, 40)
SKIN = color.rgb(246, 196, 160)
HAT = color.rgb(232, 52, 74)
POM = color.rgb(255, 255, 255)
POLE = color.rgb(90, 96, 112)
PINE_DARK = color.rgb(22, 110, 64)
PINE = color.rgb(38, 150, 80)
TRUNK = color.rgb(120, 76, 42)
STUMP_TOP = color.rgb(214, 170, 110)
ROCK = color.rgb(128, 134, 148)
ROCK_LIGHT = color.rgb(172, 178, 192)
MOGUL = color.rgb(214, 226, 244)
MOGUL_EDGE = color.rgb(176, 192, 218)
RAMP = color.rgb(250, 196, 40)
RAMP_EDGE = color.rgb(214, 134, 20)
YETI = color.rgb(250, 252, 255)
YETI_EDGE = color.rgb(150, 170, 200)
YETI_FACE = color.rgb(70, 86, 120)
MOUTH = color.rgb(150, 20, 40)
WHITE = color.rgb(255, 255, 255)
PANEL = color.rgb(255, 255, 255, 225)
PANEL_EDGE = color.rgb(140, 150, 170)
TEXT = color.rgb(30, 34, 48)
ALERT = color.rgb(220, 40, 60)
STAR = color.rgb(255, 200, 40)

TREE, SMALL_TREE, DEAD_TREE, ROCK_KIND, STUMP, MOGUL_KIND, RAMP_KIND = range(7)
# radius used for collisions, height you must be above to clear it
HIT = {
    TREE: (3.0, 11.0),
    SMALL_TREE: (2.5, 7.0),
    DEAD_TREE: (2.5, 8.0),
    ROCK_KIND: (4.0, 4.0),
    STUMP: (3.0, 4.0),
    MOGUL_KIND: (5.0, 1.0),
    RAMP_KIND: (6.0, 1.0),
}
KIND_WEIGHTS = (
    (TREE, 34), (SMALL_TREE, 16), (DEAD_TREE, 4), (ROCK_KIND, 11),
    (STUMP, 9), (MOGUL_KIND, 18), (RAMP_KIND, 8),
)
KIND_TOTAL = sum(w for _, w in KIND_WEIGHTS)


def poly(*points):
    return shape.custom([vec2(x, y) for x, y in points])


def part(pen, shp):
    return (pen, shp)


# Skier art: feet at the origin, body pointing up (-y). Skis point down (+y).
SKIS = (
    part(SKI, poly((-3.0, -5), (-1.2, -5), (-1.2, 7), (-2.1, 8.5), (-3.0, 7))),
    part(SKI, poly((1.2, -5), (3.0, -5), (3.0, 7), (2.1, 8.5), (1.2, 7))),
)
BODY = (
    part(POLE, shape.line(-4.6, -6.5, -6.5, 1.0, 0.8)),
    part(POLE, shape.line(4.6, -6.5, 6.5, 1.0, 0.8)),
    part(PANTS, poly((-2.6, 0), (-0.4, 0), (-0.3, -6), (-2.4, -6))),
    part(PANTS, poly((0.4, 0), (2.6, 0), (2.4, -6), (0.3, -6))),
    part(JACKET, poly((-3.2, -5.5), (3.2, -5.5), (3.4, -10.5), (2.4, -11.5), (-2.4, -11.5), (-3.4, -10.5))),
    part(JACKET, shape.line(-3.0, -10.5, -4.8, -6.5, 1.6)),
    part(JACKET, shape.line(3.0, -10.5, 4.8, -6.5, 1.6)),
    part(SCARF, poly((-2.4, -11.8), (2.4, -11.8), (2.4, -10.6), (-2.4, -10.6))),
    part(SCARF, poly((1.4, -11.0), (3.0, -11.0), (4.2, -8.4), (3.0, -8.2))),
    part(SKIN, shape.circle(vec2(0, -14.0), 2.5)),
    part(HAT, poly((-2.7, -14.4), (2.7, -14.4), (2.2, -16.4), (0, -17.3), (-2.2, -16.4))),
    part(POM, shape.circle(vec2(0, -17.6), 1.2)),
    part(INK, shape.circle(vec2(-0.9, -13.6), 0.45)),
    part(INK, shape.circle(vec2(0.9, -13.6), 0.45)),
)
SKIER_SHADOW = shape.ellipse(0, 0, 6, 2)

TREE_PARTS = (
    part(TRUNK, poly((-1.2, 0), (1.2, 0), (1.2, -3.5), (-1.2, -3.5))),
    part(PINE_DARK, poly((-7, -3), (7, -3), (0, -12))),
    part(PINE, poly((-5.5, -8), (5.5, -8), (0, -16))),
    part(PINE_DARK, poly((-4, -12.5), (4, -12.5), (0, -20))),
    part(WHITE, poly((-1.6, -17.5), (1.6, -17.5), (0, -20))),
)
DEAD_TREE_PARTS = (
    part(TRUNK, poly((-1.2, 0), (1.2, 0), (0.6, -16), (-0.6, -16))),
    part(TRUNK, shape.line(0, -7, -5, -12, 1.0)),
    part(TRUNK, shape.line(0, -10, 4.5, -14, 1.0)),
    part(TRUNK, shape.line(0, -4.5, 3.5, -7.5, 1.0)),
)
ROCK_PARTS = (
    part(ROCK, poly((-5, 0.5), (-4.5, -2.5), (-1.5, -4.5), (2.5, -4), (5, -1), (4.5, 0.5))),
    part(ROCK_LIGHT, poly((-3, -2.5), (-1.2, -3.8), (1.5, -3.4), (0, -2.2))),
)
STUMP_PARTS = (
    part(TRUNK, poly((-3.2, 0.5), (3.2, 0.5), (3, -3.5), (-3, -3.5))),
    part(STUMP_TOP, shape.ellipse(0, -3.5, 3, 1.2)),
)
MOGUL_PARTS = (
    part(MOGUL_EDGE, poly((-7, 1), (-4, -2.2), (-1, -1), (2, -2.6), (7, 1))),
    part(MOGUL, poly((-6, 0.3), (-4, -1.4), (-1, -0.3), (2, -1.8), (6, 0.3))),
)
RAMP_PARTS = (
    part(RAMP_EDGE, poly((-7, 1), (7, 1), (6, -4), (-6, -4))),
    part(RAMP, poly((-6.3, -0.2), (6.3, -0.2), (5.5, -4), (-5.5, -4))),
    part(RAMP_EDGE, shape.line(-4.5, -2, 4.5, -2, 0.6)),
)
ART = {
    TREE: TREE_PARTS, SMALL_TREE: TREE_PARTS, DEAD_TREE: DEAD_TREE_PARTS,
    ROCK_KIND: ROCK_PARTS, STUMP: STUMP_PARTS, MOGUL_KIND: MOGUL_PARTS,
    RAMP_KIND: RAMP_PARTS,
}
SCALE = {SMALL_TREE: 0.65}


def draw_parts(parts, transform):
    for pen, shp in parts:
        shp.transform = transform
        screen.pen = pen
        screen.shape(shp)


def clamp(value, low, high):
    return low if value < low else high if value > high else value


def ease(dt, ms):
    return 1 - math.exp(-dt * 1000 / ms)


class Tilt:
    """Side-to-side roll of the badge as -1..1 (positive = tipped to the right)."""

    def __init__(self):
        self.roll = 0.0
        self.available = False

    def update(self, dt):
        ax, ay, az = badge.imu()[:3]
        magnitude = math.sqrt(ax * ax + ay * ay + az * az)
        if magnitude < 4000:
            self.available = False
            target = 0.0
        else:
            self.available = True
            target = math.asin(clamp(-ax / magnitude, -1.0, 1.0))
            if badge.upside_down():
                target = -target
            if saved["flip"]:
                target = -target
        self.roll += (target - self.roll) * ease(dt, 90)

    def amount(self):
        roll = self.roll
        if abs(roll) < DEAD_ZONE:
            return 0.0
        roll -= DEAD_ZONE if roll > 0 else -DEAD_ZONE
        return clamp(roll / (FULL_TILT - DEAD_ZONE), -1.0, 1.0)


def cell_random(cx, cy, seed):
    state = (cx * 374761393 + cy * 668265263 + seed * 2246822519) & 0x7FFFFFFF
    state = ((state ^ (state >> 13)) * 1274126177) & 0x7FFFFFFF
    state ^= state >> 16
    state = state or 1

    def next_value(limit):
        nonlocal state
        state ^= (state << 13) & 0x7FFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0x7FFFFFFF
        return state % limit

    return next_value


class Slope:
    """An endless slope: each grid cell is generated from a hash, so the
    same spot always holds the same obstacles."""

    def __init__(self, seed):
        self.seed = seed
        self.cells = {}

    def cell(self, cx, cy):
        key = (cx, cy)
        objects = self.cells.get(key)
        if objects is None:
            objects = self.make(cx, cy)
            self.cells[key] = objects
        return objects

    def make(self, cx, cy):
        objects = []
        top = cy * CELL
        if top < 70 and -100 < cx * CELL < 100:
            return objects
        rand = cell_random(cx, cy, self.seed)
        metres = max(0, top) * M_PER_PX
        density = min(48, 26 + int(metres / 150))
        for _ in range(2):
            if rand(100) >= density:
                continue
            pick = rand(KIND_TOTAL)
            for kind, weight in KIND_WEIGHTS:
                if pick < weight:
                    break
                pick -= weight
            x = cx * CELL + 4 + rand(CELL - 8)
            y = top + 4 + rand(CELL - 8)
            objects.append([kind, x, y, False])
        return objects

    def prune(self, px, py):
        pcx, pcy = int(px // CELL), int(py // CELL)
        for key in list(self.cells):
            if key[1] < pcy - 3 or abs(key[0] - pcx) > 7:
                del self.cells[key]

    def around(self, x0, y0, x1, y1):
        for cy in range(int(y0 // CELL), int(y1 // CELL) + 1):
            for cx in range(int(x0 // CELL), int(x1 // CELL) + 1):
                for obj in self.cell(cx, cy):
                    yield obj


TITLE, PLAY, CRASH, EATEN, OVER = range(5)


class Game:
    def __init__(self):
        self.reset(title=True)

    def reset(self, title=False):
        self.state = TITLE if title else PLAY
        self.slope = Slope((badge.ticks * 2654435761) & 0xFFFFF)
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.vz = 0.0
        self.heading = 0.0
        self.speed = 0.0
        self.lean = 0.0
        self.spin = -1.0
        self.time = 0.0
        self.style = 0
        self.timer = 0.0
        self.safe = 0.0
        self.paused = False
        self.trail = []
        self.trail_step = 0.0
        self.yeti = None
        self.yeti_speed = 0.0
        self.new_best = False
        self.prune_at = 0.0

    @property
    def metres(self):
        return int(max(0.0, self.y) * M_PER_PX)

    def steer(self):
        target = tilt.amount()
        if badge.held(BUTTON_LEFT):
            target = -1.0
        elif badge.held(BUTTON_RIGHT):
            target = 1.0
        return target

    def update(self, dt):
        if self.state == TITLE:
            self.lean += (self.steer() * MAX_LEAN - self.lean) * ease(dt, 80)
            self.heading = self.steer() * MAX_HEADING
            if badge.pressed(BUTTON_SELECT):
                self.reset()
            return
        if self.state == OVER:
            if badge.pressed(BUTTON_SELECT):
                self.reset()
            return
        if self.state in (PLAY, CRASH) and badge.pressed(BUTTON_BACK):
            self.paused = not self.paused
        if self.paused:
            return
        self.time += dt
        if self.state == PLAY:
            self.ski(dt)
        elif self.state == CRASH:
            self.timer -= dt
            if self.timer <= 0:
                self.state = PLAY
                self.safe = 0.8
                self.lean = 0.0
        elif self.state == EATEN:
            self.timer -= dt
            if self.timer <= 0:
                self.finish()
            return
        self.chase(dt)
        self.prune_at -= dt
        if self.prune_at <= 0:
            self.slope.prune(self.x, self.y)
            self.prune_at = 1.0

    def ski(self, dt):
        steer = self.steer()
        self.heading += (steer * MAX_HEADING - self.heading) * ease(dt, 90)
        self.lean += (steer * MAX_LEAN - self.lean) * ease(dt, 70)
        target = CRUISE * (1 + min(self.metres, 4000) / 20000)
        target *= 0.22 + 0.78 * math.cos(self.heading)
        rate = 600
        if badge.held(BUTTON_DOWN):
            target *= BOOST
        if badge.held(BUTTON_UP):
            target, rate = 0.0, 220
        self.speed += (target - self.speed) * ease(dt, rate)

        if badge.pressed(BUTTON_SELECT):
            if self.z <= 0:
                self.vz = 55.0
                self.z = 0.01
            elif self.spin < 0:
                self.spin = 0.0

        step = self.speed * dt
        self.x += math.sin(self.heading) * step
        self.y += math.cos(self.heading) * step
        self.safe = max(0.0, self.safe - dt)

        if self.z > 0:
            self.vz -= GRAVITY * dt
            self.z += self.vz * dt
            if self.spin >= 0:
                self.spin += dt / SPIN_TIME
                if self.spin >= 1:
                    self.spin = -1.0
                    self.style += 100
            if self.z <= 0:
                self.z = 0.0
                self.vz = 0.0
                if self.spin >= 0:
                    self.spin = -1.0
                    self.crash()
                    return
        self.lay_track(step)
        self.collide()

    def lay_track(self, step):
        self.trail_step += step
        if self.trail_step < 3:
            return
        self.trail_step = 0.0
        self.trail.append((self.x, self.y, self.heading) if self.z <= 0 else None)
        if len(self.trail) > 40:
            self.trail.pop(0)

    def collide(self):
        for obj in self.slope.around(self.x - 8, self.y - 8, self.x + 8, self.y + 8):
            kind, ox, oy, used = obj
            radius, clear = HIT[kind]
            dx, dy = ox - self.x, oy - self.y
            if dx * dx + dy * dy > (radius + 2) ** 2 or self.z >= clear:
                continue
            if kind == RAMP_KIND:
                if not used:
                    obj[3] = True
                    self.vz = 85 + self.speed * 0.6
                    self.z = max(self.z, 0.01)
                    self.style += 10
            elif kind == MOGUL_KIND:
                if not used and self.z <= 0:
                    obj[3] = True
                    self.speed *= 0.7
                    self.vz = 28.0
                    self.z = 0.01
                    self.style += 5
            elif self.safe <= 0:
                obj[3] = True
                self.crash()
                return

    def crash(self):
        self.state = CRASH
        self.timer = 1.0
        self.speed = 0.0
        self.z = 0.0
        self.vz = 0.0
        self.spin = -1.0
        self.trail.append(None)

    def chase(self, dt):
        if self.yeti is None:
            if self.metres >= YETI_AT_M:
                side = -1 if (int(self.time * 10) & 1) else 1
                self.yeti = [self.x + side * 70, self.y - 110]
                self.yeti_speed = CRUISE * 1.12
            return
        self.yeti_speed += 1.2 * dt
        dx, dy = self.x - self.yeti[0], self.y - self.yeti[1]
        gap = math.sqrt(dx * dx + dy * dy) or 1.0
        step = min(gap, self.yeti_speed * dt)
        self.yeti[0] += dx / gap * step
        self.yeti[1] += dy / gap * step
        if gap < 7 and self.z < 10:
            self.state = EATEN
            self.timer = 2.4
            self.speed = 0.0
            self.z = 0.0

    def finish(self):
        self.state = OVER
        if self.metres > saved["best"]:
            saved["best"] = self.metres
            self.new_best = True
            State.save(STATE_KEY, saved)


def to_screen(wx, wy):
    return wx - game.x + SKIER_X, wy - game.y + SKIER_Y


def draw_snow():
    screen.pen = SNOW
    screen.rectangle(0, 0, screen.width, screen.height)
    # Faint specks that scroll with the slope so speed is visible on open snow.
    screen.pen = SPECK
    ox = int(game.x) % 23
    oy = int(game.y) % 19
    for row in range(-1, 8):
        for col in range(-1, 9):
            sx = col * 23 - ox + (row * 11) % 23
            sy = row * 19 - oy
            screen.rectangle(sx, sy, 2, 1)


def draw_trail():
    screen.pen = TRACK
    previous = None
    for point in game.trail:
        if point is None:
            previous = None
            continue
        wx, wy, heading = point
        sx, sy = to_screen(wx, wy)
        if previous is not None:
            px, py, ph = previous
            cos_h, sin_h = math.cos(heading) * 2, math.sin(heading) * 2
            screen.shape(shape.line(px - cos_h, py + sin_h, sx - cos_h, sy + sin_h, 1))
            screen.shape(shape.line(px + cos_h, py - sin_h, sx + cos_h, sy - sin_h, 1))
        previous = (sx, sy, heading)


def draw_object(kind, sx, sy):
    scale = SCALE.get(kind, 1.0)
    transform = mat3().translate(sx, sy)
    if scale != 1.0:
        transform = transform.scale(scale, scale)
    draw_parts(ART[kind], transform)


def draw_skier(sx, sy, z, heading, lean, spin=-1.0, shadow=True):
    if shadow:
        SKIER_SHADOW.transform = mat3().translate(sx, sy + 1).scale(1 - min(z, 20) / 40)
        screen.pen = SHADOW
        screen.shape(SKIER_SHADOW)
    turn = 360.0 * spin if spin >= 0 else 0.0
    feet = mat3().translate(sx, sy - z)
    draw_parts(SKIS, feet.rotate(-math.degrees(heading) + turn))
    draw_parts(BODY, mat3().translate(sx, sy - z).rotate(lean + turn))


def draw_crashed(sx, sy):
    draw_parts(SKIS, mat3().translate(sx - 2, sy).rotate(35))
    draw_parts(SKIS, mat3().translate(sx + 2, sy).rotate(-50))
    draw_parts(BODY, mat3().translate(sx - 6, sy + 2).rotate(80))
    screen.pen = STAR
    for i in range(3):
        angle = badge.ticks / 160 + i * 2.094
        screen.shape(shape.star(sx - 6 + math.cos(angle) * 7, sy - 6 + math.sin(angle) * 2.5, 4, 1.8, 0.8))


def draw_yeti(sx, sy, holding=False):
    hop = 0
    step = (badge.ticks // 140) & 1
    if holding:
        hop = 3 if (badge.ticks // 180) & 1 else 0
    sy -= hop
    screen.pen = SHADOW
    screen.shape(shape.ellipse(sx, sy + 1 + hop, 9, 2.5))
    # feet
    screen.pen = YETI_EDGE
    screen.shape(shape.ellipse(sx - 4, sy - (1 if step else 0), 3.5, 1.8))
    screen.shape(shape.ellipse(sx + 4, sy - (0 if step else 1), 3.5, 1.8))
    # arms up, waving
    raise_l = -26 if step or holding else -20
    raise_r = -20 if step and not holding else -26
    screen.shape(shape.line(sx - 6, sy - 15, sx - 11, sy + raise_l + 4, 3.4))
    screen.shape(shape.line(sx + 6, sy - 15, sx + 11, sy + raise_r + 4, 3.4))
    screen.pen = YETI
    screen.shape(shape.line(sx - 6, sy - 15, sx - 11, sy + raise_l + 4, 2.2))
    screen.shape(shape.line(sx + 6, sy - 15, sx + 11, sy + raise_r + 4, 2.2))
    # body
    screen.pen = YETI_EDGE
    screen.shape(shape.ellipse(sx, sy - 10, 7.5, 10))
    screen.pen = YETI
    screen.shape(shape.ellipse(sx, sy - 10, 6.5, 9))
    # face
    screen.pen = YETI_FACE
    screen.shape(shape.ellipse(sx, sy - 14, 4, 3.4))
    screen.pen = WHITE
    screen.shape(shape.circle(vec2(sx - 1.6, sy - 15), 1.0))
    screen.shape(shape.circle(vec2(sx + 1.6, sy - 15), 1.0))
    screen.pen = INK
    screen.shape(shape.circle(vec2(sx - 1.4, sy - 14.8), 0.5))
    screen.shape(shape.circle(vec2(sx + 1.8, sy - 14.8), 0.5))
    screen.pen = MOUTH
    screen.shape(shape.ellipse(sx, sy - 12, 2.2, 1.1 + (1.0 if holding and hop else 0.4)))
    screen.pen = WHITE
    screen.shape(poly((sx - 1.6, sy - 12.8), (sx - 0.8, sy - 12.8), (sx - 1.2, sy - 11.8)))
    screen.shape(poly((sx + 0.8, sy - 12.8), (sx + 1.6, sy - 12.8), (sx + 1.2, sy - 11.8)))
    if holding:
        kick = 20 if (badge.ticks // 120) & 1 else -20
        draw_skier(sx, sy - 22, 0, math.radians(kick), 180 + kick, shadow=False)


def draw_start_banner():
    lx, ly = to_screen(-30, -6)
    rx, ry = to_screen(30, -6)
    if ly < -20 or ly > screen.height + 20:
        return
    screen.pen = POLE
    screen.shape(shape.line(lx, ly, lx, ly - 22, 1.2))
    screen.shape(shape.line(rx, ry, rx, ry - 22, 1.2))
    screen.pen = HAT
    screen.rectangle(int(lx), int(ly - 22), int(rx - lx), 8)
    screen.pen = WHITE
    screen.font = font.sins
    w, _ = screen.measure_text("SKI TILT")
    screen.text("SKI TILT", int((lx + rx - w) / 2), int(ly - 22))


def draw_world():
    draw_snow()
    draw_trail()
    draw_start_banner()
    x0 = game.x - SKIER_X - 10
    y0 = game.y - SKIER_Y - 6
    x1 = x0 + screen.width + 20
    y1 = y0 + screen.height + 30
    visible = [obj for obj in game.slope.around(x0, y0, x1, y1)]
    visible.sort(key=lambda obj: obj[2])
    flat = [obj for obj in visible if obj[0] in (MOGUL_KIND, RAMP_KIND)]
    upright = [obj for obj in visible if obj[0] not in (MOGUL_KIND, RAMP_KIND)]
    for kind, wx, wy, _ in flat:
        sx, sy = to_screen(wx, wy)
        draw_object(kind, sx, sy)
    skier_drawn = False
    yeti_drawn = game.yeti is None or game.state == EATEN
    for kind, wx, wy, _ in upright:
        if not yeti_drawn and wy > game.yeti[1]:
            draw_yeti(*to_screen(*game.yeti))
            yeti_drawn = True
        if not skier_drawn and wy > game.y:
            draw_player()
            skier_drawn = True
        sx, sy = to_screen(wx, wy)
        draw_object(kind, sx, sy)
    if not skier_drawn:
        draw_player()
    if not yeti_drawn:
        draw_yeti(*to_screen(*game.yeti))


def draw_player():
    if game.state == CRASH:
        draw_crashed(SKIER_X, SKIER_Y)
    elif game.state == EATEN:
        draw_yeti(SKIER_X, SKIER_Y + 4, holding=True)
    elif game.state in (PLAY, OVER, TITLE):
        if game.state == OVER and game.yeti is not None:
            return
        blink = game.safe > 0 and (badge.ticks // 90) & 1
        if not blink:
            draw_skier(SKIER_X, SKIER_Y, game.z, game.heading, game.lean, game.spin)


def draw_yeti_warning():
    if game.yeti is None or game.state not in (PLAY, CRASH):
        return
    sx, sy = to_screen(*game.yeti)
    if -12 < sx < screen.width + 12 and -4 < sy < screen.height + 24:
        return
    ex = clamp(sx, 6, screen.width - 6)
    ey = clamp(sy, 6, screen.height - 6)
    if (badge.ticks // 200) & 1:
        screen.pen = ALERT
        screen.shape(shape.circle(vec2(ex, ey), 5))
        screen.pen = WHITE
        screen.font = font.sins
        screen.text("!", int(ex - 1), int(ey - 5))


def panel(x, y, w, h):
    screen.pen = PANEL_EDGE
    screen.shape(shape.rounded_rectangle(x - 1, y - 1, w + 2, h + 2, 3))
    screen.pen = PANEL
    screen.shape(shape.rounded_rectangle(x, y, w, h, 3))


def centre(text, y, pen=TEXT):
    w, _ = screen.measure_text(text)
    screen.pen = pen
    screen.text(text, int((screen.width - w) / 2), y)


def clock(seconds):
    seconds = int(seconds)
    return "%d:%02d" % (seconds // 60, seconds % 60)


def draw_hud():
    screen.font = font.sins
    panel(screen.width - 52, 2, 50, 31)
    screen.pen = TEXT
    lines = ("%dm" % game.metres, clock(game.time), "%d km/h" % int(game.speed * M_PER_PX * 3.6))
    for i, line in enumerate(lines):
        w, _ = screen.measure_text(line)
        screen.text(line, screen.width - 5 - w, 1 + i * 10)
    if game.style:
        screen.pen = JACKET
        screen.text("+%d" % game.style, 3, 2)
    if game.paused:
        panel(46, 52, 68, 18)
        centre("PAUSED", 56)
    if toast["until"] > badge.ticks:
        panel(30, 104, 100, 13)
        centre(toast["text"], 105)


def draw_title():
    draw_snow()
    for kind, x, y in ((TREE, 9, 112), (SMALL_TREE, 26, 118), (TREE, 151, 110),
                       (ROCK_KIND, 132, 116), (MOGUL_KIND, 60, 116)):
        draw_object(kind, x, y)
    screen.font = font.ziplock
    centre("SKI TILT", 6, JACKET)
    screen.font = font.sins
    centre("a SkiFree-style run", 24)
    draw_skier(80, 66, 0, game.heading, game.lean)
    centre("Tilt the badge to steer", 76)
    centre("SELECT to start", 88, ALERT if (badge.ticks // 500) & 1 else TEXT)
    if saved["best"]:
        centre("Best %dm" % saved["best"], 100)
    if not tilt.available:
        centre("(no tilt: use < >)", 34, PANEL_EDGE)
    if toast["until"] > badge.ticks:
        panel(30, 40, 100, 13)
        centre(toast["text"], 41)


def draw_over():
    panel(22, 26, 116, 70)
    screen.font = font.sins
    if game.yeti is not None:
        centre("The yeti got you!", 30, ALERT)
    else:
        centre("Run over", 30, ALERT)
    centre("Distance %dm" % game.metres, 44)
    centre("Time %s  Style %d" % (clock(game.time), game.style), 54)
    centre(("New best!" if game.new_best else "Best %dm" % saved["best"]), 64, JACKET)
    centre("SELECT to ski again", 80, ALERT if (badge.ticks // 500) & 1 else TEXT)


toast = {"text": "", "until": 0}


def show_toast(text):
    toast["text"] = text
    toast["until"] = badge.ticks + 1400


tilt = Tilt()
game = Game()


def update():
    dt = min(badge.ticks_delta, 100) / 1000
    tilt.update(dt)
    if badge.pressed(BUTTON_MENU):
        saved["flip"] = not saved["flip"]
        State.save(STATE_KEY, saved)
        show_toast("Tilt flipped" if saved["flip"] else "Tilt normal")
    game.update(dt)
    if game.state == TITLE:
        draw_title()
        return
    draw_world()
    draw_yeti_warning()
    draw_hud()
    if game.state == OVER:
        draw_over()


run(update)

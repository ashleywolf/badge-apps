"""Space Pinball table layout and ball physics.

All coordinates are in HIRES screen pixels (the table fills x 0..200).
"""

import math

BALL_R = 4.0
GRAVITY = 430.0          # table slope pulling the ball down, px/s^2
TILT_GRAVITY = 560.0     # extra sideways pull for a 1 g lean
MAX_SPEED = 780.0
STEP = 2.4               # max ball travel per physics sub-step, px
MAX_STEPS = 18

LEFT = 8
LANE = 178
RIGHT = 196
ARC_CX = (LEFT + RIGHT) / 2
ARC_CY = 100
ARC_R = (RIGHT - LEFT) / 2
FLOOR = 238
DRAIN_Y = 246
LAUNCH_X = (LANE + RIGHT) / 2
LAUNCH_Y = FLOOR - BALL_R

# Segment kinds
WALL = 0
SLING = 1
DROP = 2

FLIPPER_LEN = 27.0
FLIPPER_R = 3.6
FLIPPER_REST = 28.0
FLIPPER_UP = -28.0
FLIPPER_UP_SPEED = 1500.0    # degrees per second
FLIPPER_DOWN_SPEED = 900.0

BUMPERS = ((78, 80), (120, 80), (99, 113))
BUMPER_R = 9.0
BUMPER_KICK = 300.0
SLING_KICK = 250.0

POSTS = ((90, 40), (114, 40))
POST_R = 3.0
LANE_LIGHTS = ((78, 36), (102, 32), (126, 36))

DROP_TARGETS = (104, 118, 132)
DROP_X = 12

WORMHOLE = (34, 70)
WORMHOLE_R = 6.0
WORMHOLE_PULL_R = 15.0

LEFT_PIVOT = (61.0, 206.0)
RIGHT_PIVOT = (125.0, 206.0)

SLINGS = (
    ((22, 138), (46, 178), (22, 170)),
    ((164, 138), (140, 178), (164, 170)),
)

# Events reported by Table.step()
EV_BUMPER = 1
EV_SLING = 2
EV_DROP = 3
EV_LANE = 4
EV_WORMHOLE = 5
EV_DRAIN = 6
EV_FLIPPER = 7
EV_KICKBACK = 8

KICKBACK_X = 22
KICKBACK_Y = 222


def arc_points(steps=20):
    points = []
    for i in range(steps + 1):
        a = math.pi + math.pi * i / steps
        points.append((ARC_CX + ARC_R * math.cos(a), ARC_CY + ARC_R * math.sin(a)))
    return points


def wall_polylines():
    """Static walls as polylines, shared by the physics and the artwork."""
    return (
        [(LEFT, 252), (LEFT, ARC_CY)] + arc_points()[1:] + [(RIGHT, FLOOR)],
        [(22, 170), (22, 180), (57, 201)],
        [(LANE, 74), (LANE, FLOOR)],
        [(164, 170), (164, 180), (129, 201)],
        [(LANE, FLOOR), (RIGHT, FLOOR)],
    )


class Flipper:
    def __init__(self, pivot, left):
        self.px, self.py = pivot
        self.left = left
        self.angle = FLIPPER_REST
        self.omega = 0.0          # radians per second, screen coordinates
        self.active = False

    def world_angle(self, angle):
        return angle if self.left else 180.0 - angle

    def tip(self):
        a = math.radians(self.world_angle(self.angle))
        return self.px + FLIPPER_LEN * math.cos(a), self.py + FLIPPER_LEN * math.sin(a)

    def advance(self, dt):
        target = FLIPPER_UP if self.active else FLIPPER_REST
        speed = FLIPPER_UP_SPEED if self.active else FLIPPER_DOWN_SPEED
        before = self.angle
        if self.angle > target:
            self.angle = max(target, self.angle - speed * dt)
        elif self.angle < target:
            self.angle = min(target, self.angle + speed * dt)
        change = self.angle - before
        if not self.left:
            change = -change
        self.omega = math.radians(change) / dt if dt else 0.0


class Table:
    def __init__(self):
        self.segments = []
        for line in wall_polylines():
            for i in range(len(line) - 1):
                self.add_segment(line[i], line[i + 1], WALL, 0.45)
        for a, c, b in SLINGS:
            self.add_segment(a, c, SLING, 0.6)
            self.add_segment(a, b, WALL, 0.4)
            self.add_segment(b, c, WALL, 0.4)
        for i, y in enumerate(DROP_TARGETS):
            self.add_segment((DROP_X, y - 6), (DROP_X, y + 6), DROP, 0.3, i)

        self.circles = []
        for x, y in BUMPERS:
            self.circles.append((x, y, BUMPER_R, True))
        for x, y in POSTS:
            self.circles.append((x, y, POST_R, False))

        self.cell = 16
        self.cols = 13
        self.rows = 17
        self.grid = [[] for _ in range(self.cols * self.rows)]
        reach = BALL_R + 2
        for index, seg in enumerate(self.segments):
            x1, y1, dx, dy = seg[0], seg[1], seg[2], seg[3]
            self.add_to_grid(("s", index), min(x1, x1 + dx) - reach, min(y1, y1 + dy) - reach,
                             max(x1, x1 + dx) + reach, max(y1, y1 + dy) + reach)
        for index, (x, y, r, _bumper) in enumerate(self.circles):
            self.add_to_grid(("c", index), x - r - reach, y - r - reach, x + r + reach, y + r + reach)

        self.flippers = (Flipper(LEFT_PIVOT, True), Flipper(RIGHT_PIVOT, False))
        self.drops = [True, True, True]
        self.lanes = [False, False, False]
        self.lane_inside = [False, False, False]
        self.tilt_x = 0.0
        self.kickback = True
        self.ball_live = False
        self.captured = False
        self.reset_ball()

    def add_segment(self, a, b, kind, restitution, tag=0):
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        self.segments.append((a[0], a[1], dx, dy, 1.0 / (dx * dx + dy * dy), kind, restitution, tag))

    def add_to_grid(self, item, x0, y0, x1, y1):
        c0 = max(0, int(x0 // self.cell))
        c1 = min(self.cols - 1, int(x1 // self.cell))
        r0 = max(0, int(y0 // self.cell))
        r1 = min(self.rows - 1, int(y1 // self.cell))
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                self.grid[row * self.cols + col].append(item)

    def reset_ball(self):
        self.x = LAUNCH_X
        self.y = LAUNCH_Y
        self.vx = 0.0
        self.vy = 0.0
        self.ball_live = True
        self.captured = False

    def in_launch_lane(self):
        return self.x > LANE + 2 and self.y > 150

    def resting_on_plunger(self):
        return self.in_launch_lane() and self.y > LAUNCH_Y - 3 and abs(self.vy) < 40

    def launch(self, power):
        if self.resting_on_plunger():
            self.vy = -power
            self.vx = 0.0

    def nudge(self, push_x, push_y):
        if self.ball_live and not self.captured:
            self.vx += push_x
            self.vy += push_y

    def step(self, dt, events):
        flippers = self.flippers
        if not self.ball_live or self.captured:
            for flipper in flippers:
                flipper.advance(dt)
            return

        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        travel = speed * dt
        if self.y > 170:
            for flipper in flippers:
                if flipper.angle != (FLIPPER_UP if flipper.active else FLIPPER_REST):
                    travel = max(travel, FLIPPER_LEN * math.radians(FLIPPER_UP_SPEED) * dt)
        steps = min(MAX_STEPS, int(travel / STEP) + 1)
        h = dt / steps
        ax = self.tilt_x * TILT_GRAVITY
        if self.in_launch_lane():
            ax = 0.0
        for _ in range(steps):
            for flipper in flippers:
                flipper.advance(h)
            self.vx += ax * h
            self.vy += GRAVITY * h
            self.x += self.vx * h
            self.y += self.vy * h
            self.collide(events, h)
            if self.captured or not self.ball_live:
                return

        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        if speed > MAX_SPEED:
            scale = MAX_SPEED / speed
            self.vx *= scale
            self.vy *= scale
        damping = 1.0 - 0.12 * dt
        self.vx *= damping
        self.vy *= damping

    def collide(self, events, h):
        R = BALL_R
        bx, by = self.x, self.y

        if by > DRAIN_Y:
            self.ball_live = False
            events.append((EV_DRAIN, 0))
            return

        if self.kickback and bx < KICKBACK_X and by > KICKBACK_Y:
            self.kickback = False
            self.vx = 0.0
            self.vy = -760.0
            events.append((EV_KICKBACK, 0))

        wx, wy = WORMHOLE
        dx = bx - wx
        dy = by - wy
        d2 = dx * dx + dy * dy
        if d2 < WORMHOLE_PULL_R * WORMHOLE_PULL_R:
            if d2 < WORMHOLE_R * WORMHOLE_R:
                self.captured = True
                self.x, self.y, self.vx, self.vy = wx, wy, 0.0, 0.0
                events.append((EV_WORMHOLE, 0))
                return
            d = math.sqrt(d2) or 1.0
            self.vx -= dx / d * 1100.0 * h
            self.vy -= dy / d * 1100.0 * h

        for i, (lx, ly) in enumerate(LANE_LIGHTS):
            inside = abs(bx - lx) < 7 and abs(by - ly) < 7
            if inside and not self.lane_inside[i]:
                events.append((EV_LANE, i))
            self.lane_inside[i] = inside

        col = int(bx // self.cell)
        row = int(by // self.cell)
        if 0 <= col < self.cols and 0 <= row < self.rows:
            segments = self.segments
            circles = self.circles
            for kind, index in self.grid[row * self.cols + col]:
                if kind == "s":
                    seg = segments[index]
                    if seg[5] == DROP and not self.drops[seg[7]]:
                        continue
                    self.hit_segment(seg, events)
                else:
                    self.hit_circle(circles[index], index, events)

        if by > 180:
            for flipper in self.flippers:
                self.hit_flipper(flipper, events)

    def hit_segment(self, seg, events):
        x1, y1, sdx, sdy, inv, kind, rest, tag = seg
        bx, by = self.x, self.y
        t = ((bx - x1) * sdx + (by - y1) * sdy) * inv
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        px = x1 + sdx * t
        py = y1 + sdy * t
        dx = bx - px
        dy = by - py
        d2 = dx * dx + dy * dy
        if d2 >= BALL_R * BALL_R:
            return
        d = math.sqrt(d2)
        if d < 0.0001:
            nx, ny = -sdy, sdx
            length = math.sqrt(nx * nx + ny * ny)
            nx /= length
            ny /= length
        else:
            nx = dx / d
            ny = dy / d
        self.x = px + nx * BALL_R
        self.y = py + ny * BALL_R
        vn = self.vx * nx + self.vy * ny
        if vn < 0.0:
            self.vx -= (1.0 + rest) * vn * nx
            self.vy -= (1.0 + rest) * vn * ny
            if kind == SLING and vn < -40.0:
                self.vx += nx * SLING_KICK
                self.vy += ny * SLING_KICK
                events.append((EV_SLING, 0))
            elif kind == DROP and vn < -25.0:
                self.drops[tag] = False
                events.append((EV_DROP, tag))

    def hit_circle(self, circle, index, events):
        cx, cy, r, bumper = circle
        dx = self.x - cx
        dy = self.y - cy
        reach = r + BALL_R
        d2 = dx * dx + dy * dy
        if d2 >= reach * reach:
            return
        d = math.sqrt(d2) or 0.0001
        nx = dx / d
        ny = dy / d
        self.x = cx + nx * reach
        self.y = cy + ny * reach
        vn = self.vx * nx + self.vy * ny
        if vn < 0.0:
            self.vx -= 1.5 * vn * nx
            self.vy -= 1.5 * vn * ny
        if bumper:
            vn = self.vx * nx + self.vy * ny
            if vn < BUMPER_KICK:
                self.vx += nx * (BUMPER_KICK - vn)
                self.vy += ny * (BUMPER_KICK - vn)
            events.append((EV_BUMPER, index))

    def hit_flipper(self, flipper, events):
        px, py = flipper.px, flipper.py
        tx, ty = flipper.tip()
        sdx = tx - px
        sdy = ty - py
        bx, by = self.x, self.y
        t = ((bx - px) * sdx + (by - py) * sdy) / (FLIPPER_LEN * FLIPPER_LEN)
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        cx = px + sdx * t
        cy = py + sdy * t
        radius = FLIPPER_R + 1.2 * (1.0 - t)
        reach = radius + BALL_R
        dx = bx - cx
        dy = by - cy
        d2 = dx * dx + dy * dy
        if d2 >= reach * reach:
            return
        d = math.sqrt(d2) or 0.0001
        nx = dx / d
        ny = dy / d
        self.x = cx + nx * reach
        self.y = cy + ny * reach
        omega = flipper.omega
        svx = -omega * (cy - py)
        svy = omega * (cx - px)
        rvx = self.vx - svx
        rvy = self.vy - svy
        vn = rvx * nx + rvy * ny
        if vn < 0.0:
            rvx -= 1.3 * vn * nx
            rvy -= 1.3 * vn * ny
            self.vx = rvx + svx
            self.vy = rvy + svy
            if abs(omega) > 1.0:
                events.append((EV_FLIPPER, 0))

    def release_wormhole(self):
        self.captured = False
        self.x = WORMHOLE[0] + 2
        self.y = WORMHOLE[1] + WORMHOLE_PULL_R + 2
        self.vx = 70.0
        self.vy = 160.0

"""3D Maze: a first-person walk through a red brick labyrinth.

A homage to the classic Windows 3D Maze screensaver. Tilt the badge to walk
and steer, physically turn around to look around (gyroscope), or let the
autopilot wander like the old screensaver.
"""

import math
import os
import random
import sys

APP_DIR = "/system/apps/maze3d"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State  # noqa: E402

import render  # noqa: E402

ROOMS = 8
RADIUS = 0.22
WALK_SPEED = 1.9          # cells per second at full tilt
BACK_SPEED = 0.6          # fraction of WALK_SPEED when walking backwards
TURN_SPEED = 2.4          # radians per second at full tilt or D-pad
AUTO_SPEED = 1.5
AUTO_TURN = 2.6
WIN_MS = 4000
INTRO_MS = 5000
IDLE_AUTOPILOT_MS = 60000

# IMU tuning. Readings are ~16384 per g and ~14.3 per degree/second
# (see badger.github.io src/lib/badge-motion.ts). Flip a sign here if a
# direction feels backwards on your badge.
GRAVITY = 16384.0
GYRO_PER_DPS = 14.29
STEER_SIGN = 1
WALK_SIGN = 1
GYRO_SIGN = 1
TILT_DEAD = 0.10          # ~6 degrees of free play
TILT_FULL = 0.45          # ~27 degrees for full speed
GYRO_DEAD = 4.0           # degrees per second treated as stillness
TILT_SMOOTH_MS = 90

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))  # east, south, west, north

BG = color.rgb(0, 0, 0)
WHITE = color.rgb(255, 255, 255)
SHADOW = color.rgb(0, 0, 0, 170)
YELLOW = color.rgb(255, 214, 64)
GREEN = color.rgb(60, 200, 90)
MAP_WALL = color.rgb(150, 50, 36)
MAP_FLOOR = color.rgb(40, 40, 48)
MAP_UNSEEN = color.rgb(0, 0, 0, 150)

previous_clear = badge.default_clear
badge.default_clear = None

state = {"best_ms": 0, "escapes": 0}
State.load("maze3d", state)

renderer = render.Renderer(screen.width, screen.height)
imu_source = badge.imu


def rotated():
    flip = getattr(badge, "rotate_180", None)
    return bool(flip()) if flip else False


class Motion:
    """Turns raw IMU readings into steer, walk and yaw-rate inputs."""

    def __init__(self):
        self.ax = None
        self.az = 0.0
        self.ref = None
        self.bias = 0.0
        self.flipped = rotated()
        self.steer = 0.0
        self.walk = 0.0
        self.yaw = 0.0

    def recentre(self):
        self.ref = None

    @staticmethod
    def shape(value):
        size = abs(value)
        if size <= TILT_DEAD:
            return 0.0
        size = min(1.0, (size - TILT_DEAD) / (TILT_FULL - TILT_DEAD))
        return size if value > 0 else -size

    def update(self, dt):
        reading = imu_source()
        if not reading or not any(reading[:3]):
            self.steer = self.walk = self.yaw = 0.0
            return
        ax, az, gy = reading[0], reading[2], reading[4]
        flipped = rotated()
        if flipped != self.flipped:
            self.flipped = flipped
            self.ax = None
            self.ref = None
        if flipped:
            # Turning the badge 180 degrees about the screen reverses x and y.
            ax, gy = -ax, -gy
        if self.ax is None:
            self.ax, self.az = float(ax), float(az)
        else:
            k = 1 - math.exp(-dt * 1000 / TILT_SMOOTH_MS)
            self.ax += (ax - self.ax) * k
            self.az += (az - self.az) * k
        if self.ref is None:
            self.ref = (self.ax, self.az)
        # Right side down reads negative x; top tipped away reads negative z.
        self.steer = self.shape(-(self.ax - self.ref[0]) / GRAVITY) * STEER_SIGN
        self.walk = self.shape(-(self.az - self.ref[1]) / GRAVITY) * WALK_SIGN
        rate = (gy - self.bias) / GYRO_PER_DPS
        if abs(rate) < GYRO_DEAD:
            self.bias += (gy - self.bias) * min(1.0, dt * 2)
            rate = 0.0
        # Positive gy is a right turn about the badge's vertical axis.
        self.yaw = math.radians(rate) * GYRO_SIGN


class Maze:
    def __init__(self, rooms):
        self.width = rooms * 2 + 1
        self.height = rooms * 2 + 1
        w = self.width
        grid = bytearray(b"\x01" * (w * self.height))
        grid[w + 1] = 0
        stack = [(1, 1)]
        while stack:
            x, y = stack[-1]
            options = []
            for dx, dy in DIRS:
                nx, ny = x + dx * 2, y + dy * 2
                if 0 < nx < w - 1 and 0 < ny < self.height - 1 and grid[ny * w + nx]:
                    options.append((nx, ny, dx, dy))
            if not options:
                stack.pop()
                continue
            nx, ny, dx, dy = options[random.getrandbits(8) % len(options)]
            grid[(y + dy) * w + x + dx] = 0
            grid[ny * w + nx] = 0
            stack.append((nx, ny))
        self.grid = grid
        self.goal = (w - 2, self.height - 2)
        gx, gy = self.goal
        grid[gy * w + gx + 1] = render.EXIT
        grid[(gy + 1) * w + gx] = render.EXIT
        grid[w] = render.START
        grid[1] = render.START
        self.seen = bytearray(w * self.height)

    def solid(self, x, y):
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return True
        return self.grid[int(y) * self.width + int(x)] != 0

    def open_cell(self, cx, cy):
        return not self.solid(cx, cy)

    def free(self, x, y):
        r = RADIUS
        return not (self.solid(x - r, y - r) or self.solid(x + r, y - r)
                    or self.solid(x - r, y + r) or self.solid(x + r, y + r))


class Minimap:
    SCALE = 4

    def __init__(self, maze):
        self.maze = maze
        s = self.SCALE
        self.image = image(maze.width * s, maze.height * s)
        self.image.pen = MAP_UNSEEN
        self.image.clear()

    def reveal(self, cx, cy):
        maze = self.maze
        s = self.SCALE
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                x, y = cx + ox, cy + oy
                if not (0 <= x < maze.width and 0 <= y < maze.height):
                    continue
                i = y * maze.width + x
                if maze.seen[i]:
                    continue
                maze.seen[i] = 1
                cell = maze.grid[i]
                if cell == render.EXIT:
                    self.image.pen = GREEN
                elif cell:
                    self.image.pen = MAP_WALL
                else:
                    self.image.pen = MAP_FLOOR
                self.image.rectangle(x * s, y * s, s, s)

    def draw(self, px, py, angle):
        s = self.SCALE
        ox, oy = screen.width - self.image.width - 3, 3
        screen.blit(self.image, vec2(ox, oy))
        x = ox + px * s
        y = oy + py * s
        screen.pen = YELLOW
        screen.rectangle(int(x) - 1, int(y) - 1, 3, 3)
        screen.line(int(x), int(y), int(x + math.cos(angle) * 4), int(y + math.sin(angle) * 4))


def wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


class Game:
    def __init__(self):
        self.motion = Motion()
        self.autopilot = False
        self.show_map = False
        self.last_input = badge.ticks
        self.intro_until = badge.ticks + INTRO_MS
        self.new_maze()

    def new_maze(self):
        random.seed(badge.ticks ^ random.getrandbits(16))
        self.maze = Maze(ROOMS)
        self.map = Minimap(self.maze)
        self.x = 1.5
        self.y = 1.5
        heading = 0 if self.maze.open_cell(2, 1) else 1
        self.angle = heading * math.pi / 2
        self.auto_heading = heading
        self.auto_target = (1, 1)
        self.started = badge.ticks
        self.won_at = None
        self.elapsed = 0
        self.new_best = False
        self.map.reveal(1, 1)

    def toggle_autopilot(self):
        self.autopilot = not self.autopilot
        self.last_input = badge.ticks
        if self.autopilot:
            self.auto_target = (int(self.x), int(self.y))
            self.auto_heading = round(wrap(self.angle) / (math.pi / 2)) % 4

    def move(self, distance):
        dx = math.cos(self.angle) * distance
        dy = math.sin(self.angle) * distance
        if self.maze.free(self.x + dx, self.y):
            self.x += dx
        if self.maze.free(self.x, self.y + dy):
            self.y += dy

    def steer_manually(self, dt):
        turn = 0
        walk = 0
        if badge.held(BUTTON_LEFT):
            turn -= 1
        if badge.held(BUTTON_RIGHT):
            turn += 1
        if badge.held(BUTTON_UP):
            walk += 1
        if badge.held(BUTTON_DOWN):
            walk -= 1
        if turn or walk:
            self.autopilot = False
            self.last_input = badge.ticks
        m = self.motion
        if not self.autopilot:
            if m.steer or m.walk or m.yaw:
                self.last_input = badge.ticks
            self.angle += (turn + m.steer) * TURN_SPEED * dt + m.yaw * dt
            walk = max(-1.0, min(1.0, walk + m.walk))
            if walk < 0:
                walk *= BACK_SPEED
            if walk:
                self.move(walk * WALK_SPEED * dt)

    def drive_autopilot(self, dt):
        """Right-hand wall following, like the old screensaver."""
        tx, ty = self.auto_target
        cx, cy = tx + 0.5, ty + 0.5
        dist = math.sqrt((cx - self.x) ** 2 + (cy - self.y) ** 2)
        want = self.auto_heading * math.pi / 2
        diff = wrap(want - self.angle)
        if abs(diff) > 0.01:
            turn = AUTO_TURN * dt
            self.angle += max(-turn, min(turn, diff))
            if dist > 0.05:
                return
        step = AUTO_SPEED * dt
        if dist > step:
            self.x += (cx - self.x) / dist * step
            self.y += (cy - self.y) / dist * step
            return
        self.x, self.y = cx, cy
        for turn in (1, 0, 3, 2):
            heading = (self.auto_heading + turn) % 4
            dx, dy = DIRS[heading]
            if self.maze.open_cell(tx + dx, ty + dy):
                self.auto_heading = heading
                self.auto_target = (tx + dx, ty + dy)
                break

    def check_goal(self):
        cell = (int(self.x), int(self.y))
        self.map.reveal(*cell)
        if cell == self.maze.goal and self.won_at is None:
            self.won_at = badge.ticks
            self.elapsed = badge.ticks - self.started
            if not self.autopilot:
                state["escapes"] += 1
                if not state["best_ms"] or self.elapsed < state["best_ms"]:
                    state["best_ms"] = self.elapsed
                    self.new_best = True
                State.save("maze3d", state)

    def update(self):
        dt = min(badge.ticks_delta, 100) / 1000
        if badge.pressed(BUTTON_SELECT):
            self.motion.recentre()
            self.intro_until = 0
            if self.won_at is not None:
                self.new_maze()
        if badge.pressed(BUTTON_MENU):
            self.show_map = not self.show_map
        if badge.pressed(BUTTON_BACK):
            self.toggle_autopilot()
            self.intro_until = 0
        self.motion.update(dt)
        if self.won_at is None:
            self.steer_manually(dt)
            if not self.autopilot and badge.ticks - self.last_input > IDLE_AUTOPILOT_MS:
                self.toggle_autopilot()
            if self.autopilot:
                self.drive_autopilot(dt)
            self.angle = wrap(self.angle)
            self.check_goal()
        elif badge.ticks - self.won_at > WIN_MS:
            self.new_maze()
        self.draw()

    def draw(self):
        frame = renderer.draw(self.maze.grid, self.maze.width, self.x, self.y, self.angle)
        screen.blit(frame, vec2(0, 0))
        screen.font = font.nope
        self.draw_hud()
        if self.show_map:
            self.map.draw(self.x, self.y, self.angle)
        if self.won_at is not None:
            self.draw_win()
        elif badge.ticks < self.intro_until:
            self.draw_intro()

    def draw_hud(self):
        seconds = (badge.ticks - self.started) // 1000
        label = "AUTO" if self.autopilot else "%d:%02d" % (seconds // 60, seconds % 60)
        text_shadowed(label, 3, 2, YELLOW if self.autopilot else WHITE)
        m = self.motion
        if m.steer or m.walk:
            cx, cy = screen.width - 9, screen.height - 9
            screen.pen = SHADOW
            screen.shape(shape.circle(cx, cy, 7))
            screen.pen = YELLOW
            screen.shape(shape.circle(cx + m.steer * 5, cy - m.walk * 5, 2))

    def draw_intro(self):
        panel(14, 20, screen.width - 28, 80)
        centred("3D MAZE", 25, YELLOW)
        centred("tilt to walk + steer", 42, WHITE)
        centred("turn around to look", 54, WHITE)
        centred("SELECT recentre", 70, WHITE)
        centred("MENU map  BACK auto", 82, WHITE)

    def draw_win(self):
        panel(18, 30, screen.width - 36, 60)
        seconds = self.elapsed // 1000
        centred("YOU ESCAPED!", 36, GREEN)
        centred("%d:%02d" % (seconds // 60, seconds % 60), 52, WHITE)
        best = state["best_ms"] // 1000
        if self.new_best:
            centred("new best!", 68, YELLOW)
        elif best:
            centred("best %d:%02d" % (best // 60, best % 60), 68, WHITE)


def text_shadowed(text, x, y, pen):
    screen.pen = BG
    screen.text(text, x + 1, y + 1)
    screen.pen = pen
    screen.text(text, x, y)


def centred(text, y, pen):
    width, _ = screen.measure_text(text)
    text_shadowed(text, (screen.width - width) // 2, y, pen)


def panel(x, y, w, h):
    screen.pen = SHADOW
    screen.shape(shape.rounded_rectangle(x, y, w, h, 4))


game = Game()


def update():
    game.update()


def on_exit():
    badge.default_clear = previous_clear


run(update)

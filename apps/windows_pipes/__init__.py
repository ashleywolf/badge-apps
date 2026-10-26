"""Original, growing 3D pipes for the Universe 2026 badge."""

import gc
import math
import os
import random
import sys
from array import array

try:
    import pico3d
except ImportError:
    pico3d = None
    print("Windows Pipes: pico3d unavailable; using software preview renderer.")

APP_DIR = "/system/apps/windows_pipes"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2
screen.fill_rule = image.EVEN_ODD
BLACK = color.rgb(0, 0, 0)
WHITE = color.rgb(255, 255, 255)
badge.default_clear = BLACK
WIDTH, HEIGHT = screen.width, screen.height
USERNAME = "@ashleywolf"
PREVIOUS_GC_THRESHOLD = gc.threshold()

MAX_STEPS = 144
PIPE_COUNT = 6
SIDES = 8
RADIUS = 0.23
ELBOW = 0.40
SPACING = 1.65
DIRECTIONS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0),
              (0, -1, 0), (0, 0, 1), (0, 0, -1))
SPEEDS = (1.2, 1.5, 1.8, 2.1, 1.35, 1.65)
MATERIALS = ((35, 235, 70), (139, 55, 242), (242, 35, 184), (15, 216, 242))
RING = []
for i in range(SIDES):
    RING.append((math.cos(i * math.tau / SIDES), math.sin(i * math.tau / SIDES)))
PALETTES = []
for material in MATERIALS:
    shades = []
    for i in range(32):
        diffuse = 0.15 + 0.85 * i / 31
        shine = max(0, (i / 31 - 0.65) / 0.35) ** 3 * 0.85
        factor = diffuse * (1 - shine)
        highlight = 255 * shine
        shades.append(color.rgb(int(material[0] * factor + highlight),
                                int(material[1] * factor + highlight),
                                int(material[2] * factor + highlight)))
    PALETTES.append(shades)


def add(a, b, scale=1):
    return (a[0] + b[0] * scale, a[1] + b[1] * scale, a[2] + b[2] * scale)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def unit(a):
    length = math.sqrt(dot(a, a))
    return (a[0] / length, a[1] / length, a[2] / length)


def clamp(value, low, high):
    return min(high, max(low, value))


def camera(point, normal=False):
    x, y, z = point
    rx = x * 0.8660254 + z * 0.5
    rz = z * 0.8660254 - x * 0.5
    return (rx, y * 0.9396926 - rz * 0.3420201,
            y * 0.3420201 + rz * 0.9396926 + (0 if normal else 17))


def project(point):
    x, y, z = point
    scale = WIDTH * 0.91 / z
    return vec2(WIDTH / 2 + x * scale, HEIGHT / 2 + y * scale)


def mesh(samples, material, binormal, cap=False):
    """Cache projected, lit faces; completed pipe geometry never changes."""
    if pico3d is not None:
        return NativePart(samples, material, binormal, cap)
    rings = []
    for point, tangent in samples:
        side = cross(tangent, binormal)
        vertices, normals = [], []
        for c, s in RING:
            normal = (side[0] * c + binormal[0] * s,
                      side[1] * c + binormal[1] * s,
                      side[2] * c + binormal[2] * s)
            vertices.append(camera(add(point, normal, RADIUS)))
            normals.append(camera(normal, True))
        rings.append((vertices, normals))
    faces = []
    for index in range(len(rings) - 1):
        a, na = rings[index]
        b, nb = rings[index + 1]
        for j in range(SIDES):
            k = (j + 1) % SIDES
            normal = unit(add(add(na[j], na[k]), add(nb[j], nb[k])))
            middle = ((a[j][0] + b[k][0]) / 2, (a[j][1] + b[k][1]) / 2,
                      (a[j][2] + b[k][2]) / 2)
            if dot(normal, middle) >= 0:
                continue
            light = clamp(-normal[0] * 0.43 - normal[1] * 0.62
                          - normal[2] * 0.65, 0, 1)
            shade = int(light * 31)
            polygon = (project(a[j]), project(a[k]), project(b[k]), project(b[j]))
            faces.append((middle[2], PALETTES[material][shade], polygon))
    if cap:
        vertices, _ = rings[-1]
        points = [project(p) for p in vertices]
        for index in range(1, SIDES - 1):
            faces.append((sum(p[2] for p in vertices) / SIDES,
                          PALETTES[material][14],
                          (points[0], points[index], points[index + 1])))
    faces.sort(key=lambda face: -face[0])
    return faces


class NativePart:
    def __init__(self, samples, material, binormal, cap):
        positions, normals, indices = array("f"), array("f"), array("H")
        colors = bytearray()
        for point, tangent in samples:
            side = cross(tangent, binormal)
            for c, s in RING:
                normal = (side[0] * c + binormal[0] * s,
                          side[1] * c + binormal[1] * s,
                          side[2] * c + binormal[2] * s)
                x, y, z = camera(add(point, normal, RADIUS))
                nx, ny, nz = camera(normal, True)
                positions.extend((x, -y, -z))
                normals.extend((nx, -ny, -nz))
                light = clamp(-nx * 0.43 - ny * 0.62 - nz * 0.65, 0, 1)
                diffuse = 0.15 + 0.85 * light
                shine = max(0, (light - 0.65) / 0.35) ** 3 * 0.85
                rgb = MATERIALS[material]
                colors.extend((int(rgb[0] * diffuse * (1 - shine) + 255 * shine),
                               int(rgb[1] * diffuse * (1 - shine) + 255 * shine),
                               int(rgb[2] * diffuse * (1 - shine) + 255 * shine), 255))
        for ring in range(len(samples) - 1):
            base, following = ring * SIDES, (ring + 1) * SIDES
            for j in range(SIDES):
                k = (j + 1) % SIDES
                indices.extend((base + j, following + k, base + k,
                                base + j, following + j, following + k))
        if cap:
            base = (len(samples) - 1) * SIDES
            for j in range(1, SIDES - 1):
                indices.extend((base, base + j, base + j + 1))
        self.vertices = len(positions) // 3
        self.triangles = len(indices) // 3
        self.geometry = pico3d.mesh(positions=positions, normals=normals,
                                    indices=indices, colors=colors, quantise=True)


class NativeRenderer:
    def __init__(self):
        self.surface = pico3d.surface(screen)
        capacity = MAX_STEPS + PIPE_COUNT
        self.scene = pico3d.scene(self.surface, meshes=capacity,
                                 vertices=capacity * SIDES * 5,
                                 triangles=capacity * (SIDES * 8 + SIDES - 2))
        fov = math.atan(HEIGHT / (WIDTH * 1.82)) * 360 / math.pi
        self.projection = pico3d.mat4.perspective(fov, WIDTH / HEIGHT, 1, 32)
        self.identity = pico3d.mat4()
        self.material = pico3d.material(color=WHITE, shading=pico3d.material.UNLIT)
        self.light = pico3d.light(color=BLACK, ambient=WHITE)
        self.drawn = 0
        pico3d.engine.cores(2)
        pico3d.engine.work_bands(6)
        display.set_async(True)

    def draw(self, parts):
        self.scene.reset()
        for part in parts:
            self.scene.add(part.geometry, self.identity, self.projection,
                           self.material, self.light)
        self.drawn = self.surface.draw(self.scene)


native_renderer = NativeRenderer() if pico3d is not None else None


class Step:
    def __init__(self, cell, incoming, outgoing, binormal):
        self.corner = (cell[0] * SPACING, cell[1] * SPACING, cell[2] * SPACING)
        self.incoming = incoming
        self.outgoing = outgoing
        self.turn = incoming != outgoing
        self.binormal = cross(incoming, outgoing) if self.turn else binormal
        self.arc = ELBOW * math.pi / 2 if self.turn else 0
        self.length = SPACING - (2 * ELBOW if self.turn else 0) + self.arc
        self.samples = []
        if self.turn:
            for i in range(4):
                self.samples.append(self.sample(self.arc * i / 3))
        else:
            self.samples.append(self.sample(0))
        self.samples.append(self.sample(self.length))

    def sample(self, distance):
        if self.turn and distance < self.arc:
            angle = distance / ELBOW
            centre = add(add(self.corner, self.incoming, -ELBOW),
                         self.outgoing, ELBOW)
            point = add(add(centre, self.outgoing, -ELBOW * math.cos(angle)),
                        self.incoming, ELBOW * math.sin(angle))
            c, s = math.cos(angle), math.sin(angle)
            tangent = (self.incoming[0] * c + self.outgoing[0] * s,
                       self.incoming[1] * c + self.outgoing[1] * s,
                       self.incoming[2] * c + self.outgoing[2] * s)
            return point, tangent
        if self.turn:
            distance = distance - self.arc + ELBOW
        else:
            distance -= ELBOW
        return add(self.corner, self.outgoing, distance), self.outgoing

    def partial(self, distance):
        samples = [self.samples[0]]
        if self.turn:
            for i in range(1, 4):
                if self.arc * i / 3 < distance:
                    samples.append(self.samples[i])
        samples.append(self.sample(distance))
        return samples


class Pipe:
    def __init__(self, material, cell, direction, slot):
        self.material = material
        self.speed = SPEEDS[slot]
        self.cell = cell
        self.direction = direction
        reference = (0, 1, 0) if direction[2] else (0, 0, 1)
        self.binormal = unit(cross(direction, reference))
        self.step = None
        self.distance = 0
        self.completed = 0
        self.faces = []
        self.alive = True


class Scene:
    def __init__(self):
        self.cycles = -1
        self.restart()

    def restart(self):
        self.cycles += 1
        self.age = 0
        self.head_age = 0
        self.wipe = -1
        self.completed = []
        self.occupied = bytearray(9 * 7 * 7)
        self.pipes = []
        self.steps = 0
        for slot in range(PIPE_COUNT):
            pipe = self.spawn(slot % len(MATERIALS), slot)
            if pipe is not None:
                self.pipes.append(pipe)
        gc.collect()

    def available(self, cell):
        x, y, z = cell
        return (-4 <= x <= 4 and -3 <= y <= 3 and -3 <= z <= 3
                and not self.occupied[(x + 4) * 49 + (y + 3) * 7 + z + 3])

    def reserve(self, cell):
        x, y, z = cell
        self.occupied[(x + 4) * 49 + (y + 3) * 7 + z + 3] = 1

    def spawn(self, material, slot):
        for _ in range(32):
            cell = (random.randrange(-4, 5), random.randrange(-3, 4),
                    random.randrange(-3, 4))
            if self.available(cell):
                self.reserve(cell)
                pipe = Pipe(material, cell, random.choice(DIRECTIONS), slot)
                self.choose_step(pipe)
                if pipe.alive:
                    return pipe
        return None

    def choose_step(self, pipe):
        choices = []
        for direction in DIRECTIONS:
            target = add(pipe.cell, direction)
            if dot(direction, pipe.direction) != -1 and self.available(target):
                choices.append(direction)
        if not choices:
            pipe.alive = False
            return
        if pipe.direction in choices and random.random() < 0.42:
            outgoing = pipe.direction
        else:
            outgoing = random.choice(choices)
        self.reserve(add(pipe.cell, outgoing))
        pipe.step = Step(pipe.cell, pipe.direction, outgoing, pipe.binormal)
        pipe.distance = 0

    def advance(self, dt):
        self.age += dt
        if self.wipe >= 0:
            self.wipe += dt
            if self.wipe >= 1.8:
                self.restart()
            return
        self.head_age += dt
        refresh = self.head_age >= 1 / 30
        if refresh:
            self.head_age %= 1 / 30
        for slot, pipe in enumerate(self.pipes):
            if not pipe.alive:
                replacement = self.spawn(pipe.material, slot)
                if replacement is None:
                    continue
                self.pipes[slot] = pipe = replacement
            pipe.distance += pipe.speed * SPACING * dt
            if pipe.distance >= pipe.step.length:
                remaining = pipe.distance - pipe.step.length
                previous_step = pipe.step
                faces = mesh(pipe.step.samples, pipe.material, pipe.step.binormal)
                self.completed.append(faces)
                self.steps += 1
                pipe.completed += 1
                pipe.binormal = pipe.step.binormal
                pipe.cell = add(pipe.cell, pipe.step.outgoing)
                pipe.direction = pipe.step.outgoing
                self.choose_step(pipe)
                if pipe.alive and refresh:
                    pipe.distance = remaining
                else:
                    self.completed[-1] = mesh(previous_step.samples, pipe.material,
                                              previous_step.binormal, True)
                    pipe.faces = []
                if self.steps >= MAX_STEPS:
                    self.wipe = 0
                    break
            if pipe.alive:
                pipe.faces = mesh(pipe.step.partial(pipe.distance), pipe.material,
                                  pipe.step.binormal, True)
        if self.age >= 35 or not any(pipe.alive for pipe in self.pipes):
            self.wipe = 0

    def draw(self):
        start = int(len(self.completed) * self.wipe / 1.8) if self.wipe >= 0 else 0
        if native_renderer is not None:
            parts = self.completed[start:]
            parts.extend(pipe.faces for pipe in self.pipes if pipe.faces)
            native_renderer.draw(parts)
            return
        faces = []
        for part in self.completed[start:]:
            faces.extend(part)
        for pipe in self.pipes:
            faces.extend(pipe.faces)
        faces.sort(key=lambda face: -face[0])
        for _, pen, polygon in faces:
            screen.pen = pen
            screen.triangle(polygon[0], polygon[1], polygon[2])
            if len(polygon) == 4:
                screen.triangle(polygon[0], polygon[2], polygon[3])


class Name:
    GLYPHS = {
        "@": ("01110", "10001", "10111", "10101", "10111", "10000", "01110", "00000"),
        "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111", "00000"),
        "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110", "00000"),
        "h": ("10000", "10000", "10110", "11001", "10001", "10001", "10001", "00000"),
        "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110", "00000"),
        "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01110", "00000"),
        "y": ("00000", "00000", "10001", "10001", "10001", "01111", "00001", "01110"),
        "w": ("00000", "00000", "10001", "10001", "10101", "10101", "01010", "00000"),
        "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110", "00000"),
        "f": ("00110", "01001", "01000", "11100", "01000", "01000", "01000", "00000"),
    }

    def __init__(self):
        self.scale = max(1, int((WIDTH - 48) / (len(USERNAME) * 6 - 1)))
        self.width = (len(USERNAME) * 6 - 1) * self.scale
        self.height = 8 * self.scale
        self.limit_x = max(0, min(24, (WIDTH - self.width) / 2 - 7))
        self.limit_y = max(0, min(38, (HEIGHT - self.height) / 2 - 7))
        self.x = self.y = 0
        self.vx = self.vy = 0
        self.rest_x = self.rest_y = 0
        self.rest_z = None
        self.inverted = badge.upside_down()
        self.phase = 0
        pixels = []
        for index, char in enumerate(USERNAME):
            for row, line in enumerate(self.GLYPHS[char]):
                for column, bit in enumerate(line):
                    if bit == "1":
                        x = (index * 6 + column) * self.scale
                        y = row * self.scale
                        pixels.append((x + 4, y + 4))
        self.bitmap = image(self.width + 8, self.height + 8)
        self.bitmap.pen = color.rgb(0, 0, 0, 0)
        self.bitmap.clear()
        self.bitmap.pen = BLACK
        for x, y in pixels:
            self.bitmap.rectangle(x - 2, y - 2, self.scale + 4, self.scale + 4)
            self.bitmap.rectangle(x + 1, y + 2, self.scale + 3, self.scale + 3)
        self.bitmap.pen = WHITE
        for x, y in pixels:
            self.bitmap.rectangle(x, y, self.scale, self.scale)

    def advance(self, dt):
        reading = badge.imu()[:3]
        ax, ay, az = reading
        inverted = badge.upside_down()
        magnitude = math.sqrt(ax * ax + ay * ay + az * az)
        nx, ny, nz = (ax / magnitude, ay / magnitude, az / magnitude) if magnitude else (0, 0, 0)
        if magnitude and (self.rest_z is None or inverted != self.inverted):
            self.rest_x = nx
            vertical = math.sqrt(ny * ny + nz * nz)
            self.rest_y = ny / vertical if vertical else 0
            self.rest_z = nz / vertical if vertical else -1
            self.inverted = inverted
            self.x = self.y = 0
            self.vx = self.vy = 0
        sign = -1 if inverted else 1
        target_x = target_y = 0
        if magnitude:
            target_x = clamp(-(nx - self.rest_x) * sign * 120, -self.limit_x, self.limit_x)
            # Project onto the rest pose's vertical tangent: pitch stays sensitive
            # both when worn upright and when the screen starts face-up.
            pitch = -self.rest_z * ny + self.rest_y * nz
            target_y = clamp(pitch * sign * 140, -self.limit_y, self.limit_y)
        # Exact damped spring, stable even at the real badge's uneven frame rate.
        decay = math.exp(-6 * dt)
        cosine, sine = math.cos(8 * dt), math.sin(8 * dt)
        a = decay * (cosine + 0.75 * sine)
        b = decay * sine / 8
        c = -12.5 * decay * sine
        d = decay * (cosine - 0.75 * sine)
        dx, dy = self.x - target_x, self.y - target_y
        self.x = target_x + dx * a + self.vx * b
        self.y = target_y + dy * a + self.vy * b
        self.vx = dx * c + self.vx * d
        self.vy = dy * c + self.vy * d
        if abs(self.x) > self.limit_x:
            self.x = clamp(self.x, -self.limit_x, self.limit_x)
            self.vx = 0
        if abs(self.y) > self.limit_y:
            self.y = clamp(self.y, -self.limit_y, self.limit_y)
            self.vy = 0
        self.phase = (self.phase + dt * 0.65) % math.tau

    def position(self):
        x = (WIDTH - self.width) / 2 + self.x + math.sin(self.phase) * 1.25
        y = (HEIGHT - self.height) / 2 + self.y + math.cos(self.phase)
        return (clamp(x, 5, WIDTH - self.width - 5),
                clamp(y, 5, HEIGHT - self.height - 5))

    def draw(self):
        x, y = self.position()
        screen.blit(self.bitmap, vec2(int(x) - 4, int(y) - 4))


scene = Scene()
name = Name()


def update():
    if badge.pressed(BUTTON_BACK):
        reset()
    if badge.pressed(BUTTON_SELECT):
        scene.restart()
    dt = clamp(badge.ticks_delta / 1000, 0, 0.25)
    scene.advance(dt)
    name.advance(dt)
    scene.draw()
    name.draw()


def on_exit():
    if native_renderer is not None:
        display.set_async(False)
    gc.threshold(PREVIOUS_GC_THRESHOLD)


gc.threshold(32 * 1024)
run(update)

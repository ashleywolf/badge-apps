import random

import pets
import ui

LENGTH_MS = 20000
SPEED = 95
GROUND = 100


class Catch:
    """Move your pet left and right to catch falling stars. Dodge the bugs."""

    def __init__(self, kind):
        self.kind = kind
        self.x = 80
        self.flip = False
        self.items = []
        self.spawn_in = 400
        self.left = LENGTH_MS
        self.score = 0
        self.flash = 0
        self.done = False

    def update(self):
        dt = badge.ticks_delta
        if self.done:
            return
        self.left -= dt
        if self.left <= 0:
            self.left = 0
            self.done = True
            return

        move = 0
        if badge.held(BUTTON_LEFT):
            move -= 1
        if badge.held(BUTTON_RIGHT):
            move += 1
        if move:
            half = pets.size(self.kind, 0.5)[0] / 2 + 1
            self.x = min(screen.width - half, max(half, self.x + move * SPEED * dt / 1000))
            self.flip = move < 0

        self.spawn_in -= dt
        if self.spawn_in <= 0:
            self.spawn_in = random.randint(450, 800)
            elapsed = LENGTH_MS - self.left
            is_bug = elapsed > 4000 and random.random() < 0.22
            self.items.append([random.randint(10, 150), 14.0, random.randint(35, 60), is_bug])

        w, h = pets.size(self.kind, 0.5)
        keep = []
        for item in self.items:
            item[1] += item[2] * dt / 1000
            if GROUND - h - 4 < item[1] < GROUND and abs(item[0] - self.x) < w / 2 + 4:
                if item[3]:
                    self.score = max(0, self.score - 1)
                    self.flash = 300
                else:
                    self.score += 1
                continue
            if item[1] < GROUND + 6:
                keep.append(item)
        self.items = keep
        self.flash = max(0, self.flash - dt)

    def draw(self):
        screen.pen = color.rgb(24, 22, 52)
        screen.clear()
        screen.pen = color.rgb(255, 255, 255, 60)
        for i in range(12):
            screen.shape(shape.circle((i * 37) % 160, (i * 53) % 90 + 14, 0.8))
        screen.pen = color.rgb(60, 52, 110)
        screen.rectangle(0, GROUND, screen.width, screen.height - GROUND)

        t = badge.ticks
        for x, y, _, is_bug in self.items:
            if is_bug:
                ui.bug(x, y, t)
            else:
                ui.star(x, y, 5, color.rgb(255, 214, 60))

        row = "happy" if self.done else "idle"
        flip = self.flip if self.kind in ("duck", "squirrel") else False
        pets.draw(self.kind, row, self.x, GROUND, 0.5, flip=flip, alpha=140 if self.flash else 255)

        ui.pill(0, 0, screen.width, 13, color.rgb(0, 0, 0, 120))
        ui.star(8, 6, 5, color.rgb(255, 214, 60))
        ui.text("%d" % self.score, 16, 2, ui.WHITE)
        ui.text("%ds" % ((self.left + 999) // 1000), screen.width - 3, 2, ui.WHITE, right=True)
        ui.text("Catch the stars!", 80, 2, ui.WHITE, centre=True)

        if self.done:
            ui.panel(28, 36, 104, 40)
            ui.text("You caught %d!" % self.score, 80, 42, centre=True)
            ui.text("Press SELECT", 80, 60, color.rgb(110, 100, 150), centre=True)

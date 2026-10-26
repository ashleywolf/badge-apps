import math
import random

import pets
import ui

ARRIVE_MS = 1000
LAND_MS = 450
ACT_MS = 2600
# If both badges pick a move within this window, the leader's pick wins.
CLASH_MS = 1000
BYE_WAVE_MS = 1500
BYE_JUMP_MS = 900
AUTO_MS = (2500, 5000)
SCALE = 0.85
HOST_X = 50
GUEST_X = 110
EDGE_X = 196
JUMP_H = 36
MIDDLE = 80

TOASTS = {
    "wave": "Hi!",
    "high5": "High five!",
    "dance": "Dance party!",
    "snack": "Snack time!",
    "chase": "Tag, you're it!",
}
HINTS = ("SELECT high five  UP dance", "DOWN snack  < > wave  BACK bye")


def scale(stage):
    return SCALE * (0.75 if stage == 0 else 1.0)


def flips(kind):
    # only the duck and squirrel face a direction; Mona and Copilot face you
    return kind in ("duck", "squirrel")


def arc(start, end, p):
    """Position on a jump from x `start` to `end` at progress `p`."""
    return start + (end - start) * p, ui.GROUND_Y - 4 * JUMP_H * p * (1 - p)


class Party:
    """Two pets hanging out on one screen while their badges are linked."""

    def __init__(self, host, host_stage, guest, guest_stage, owner, now, leader, host_from=HOST_X):
        self.host = host
        self.guest = guest
        self.host_scale = scale(host_stage)
        self.guest_scale = scale(guest_stage)
        self.owner = owner
        self.leader = leader
        self.host_from = host_from
        self.phase = "arrive"
        self.phase_at = now
        self.together_at = None
        self.activity = None
        self.activity_at = 0
        self.mine = False
        self.seed = 0
        self.next_auto = now + ARRIVE_MS + LAND_MS + ACT_MS + random.randint(*AUTO_MS)
        self.toast = ""
        self.toast_until = 0
        self.done = False

    @property
    def label(self):
        return "%s's %s" % (self.owner, pets.INFO[self.guest][0])

    def busy(self, now):
        return self.activity is not None and now - self.activity_at < ACT_MS

    def ready(self, now):
        """True when the pets can start a new activity."""
        return self.phase == "together" and not self.busy(now)

    def start(self, activity, seed, now, mine=True):
        if self.phase != "together":
            return False
        if (not mine and self.leader and self.mine and self.activity is not None
                and now - self.activity_at < CLASH_MS):
            return False
        self.mine = mine
        self.activity = activity
        self.activity_at = now
        self.seed = seed
        self.say(TOASTS[activity], now)
        self.next_auto = now + ACT_MS + random.randint(*AUTO_MS)
        return True

    def say(self, text, now, ms=1600):
        self.toast = text
        self.toast_until = now + ms

    def leave(self, now):
        if self.phase != "bye":
            self.phase = "bye"
            self.phase_at = now
            self.activity = None
            self.say("Bye bye!", now, BYE_WAVE_MS)

    def auto(self, now):
        """The leader's next activity once it's due, else None."""
        if self.leader and self.ready(now) and now >= self.next_auto:
            return random.choice(("high5", "dance", "snack", "chase", "wave"))
        return None

    def update(self, now):
        t = now - self.phase_at
        if self.phase == "arrive" and t >= ARRIVE_MS + LAND_MS:
            self.phase = "together"
            self.phase_at = now
            self.together_at = now
            self.activity = "wave"
            self.activity_at = now
            self.say("%s came to visit!" % self.label, now, 2400)
        elif self.phase == "bye" and t >= BYE_WAVE_MS + BYE_JUMP_MS:
            self.done = True

    # ---------------------------------------------------------------- drawing

    def positions(self, now):
        """(host_x, host_y, guest_x, guest_y, host_row, guest_row, waving)."""
        t = now - self.phase_at
        hx, gx, hy, gy = HOST_X, GUEST_X, ui.GROUND_Y, ui.GROUND_Y
        hrow = grow = "idle"
        waving = False
        if self.phase == "arrive":
            p = min(1.0, t / ARRIVE_MS)
            hx = self.host_from + (HOST_X - self.host_from) * p
            gx, gy = arc(EDGE_X, GUEST_X, p)
            grow = "happy" if p >= 1 else "idle"
            hrow = "happy" if p >= 1 else "idle"
        elif self.phase == "bye":
            waving = t < BYE_WAVE_MS
            if not waving:
                gx, gy = arc(GUEST_X, EDGE_X, min(1.0, (t - BYE_WAVE_MS) / BYE_JUMP_MS))
        elif self.busy(now):
            p = (now - self.activity_at) / ACT_MS
            act = self.activity
            if act == "wave":
                waving = True
            elif act == "high5":
                d = 18 * math.sin(math.pi * min(1.0, p / 0.9))
                hx += d
                gx -= d
                if 0.35 < p < 0.6:
                    hop = math.sin(math.pi * (p - 0.35) / 0.25) * 10
                    hy -= hop
                    gy -= hop
                hrow = grow = "happy" if p > 0.45 else "idle"
            elif act == "dance":
                hrow = grow = "happy"
            elif act == "snack":
                d = 10 * min(1.0, p * 4)
                hx += d
                gx -= d
                hrow = grow = "eat"
            elif act == "chase":
                a = 2 * math.pi * p
                gx = MIDDLE + 30 * math.cos(a)
                hx = MIDDLE - 30 * math.cos(a)
                hop = abs(math.sin(a * 3)) * 4
                hy -= hop
                gy -= hop
        return hx, hy, gx, gy, hrow, grow, waving

    def draw_pet(self, kind, row, x, y, size, facing_left, alpha):
        w, h = pets.size(kind, size)
        ui.shadow(x, w * max(0.4, 1 - (ui.GROUND_Y - y) / 60))
        top = pets.draw(kind, row, x, y, size, flip=facing_left and flips(kind), alpha=alpha)
        return w, h, top

    def draw(self, now, dark=False):
        hx, hy, gx, gy, hrow, grow, waving = self.positions(now)
        alpha = 170 if dark else 255
        act = self.activity if self.busy(now) else None

        host_left = False
        guest_left = True
        if act == "chase":
            a = 2 * math.pi * (now - self.activity_at) / ACT_MS
            guest_left = math.sin(a) > 0
            host_left = not guest_left
        elif act == "dance":
            host_left = guest_left = int(now / 400) % 2 == 0
        if self.phase == "bye" and now - self.phase_at >= BYE_WAVE_MS:
            guest_left = False

        if act == "snack":
            p = (now - self.activity_at) / ACT_MS
            ui.food("snack" if self.seed % 2 else "meal", MIDDLE, ui.GROUND_Y - 1, 1 - int(p * 4) / 3)

        order = [("host", hx), ("guest", gx)]
        if act == "chase" and math.sin(2 * math.pi * (now - self.activity_at) / ACT_MS) < 0:
            order.reverse()
        tops = {}
        for who, _ in order:
            if who == "host":
                tops[who] = self.draw_pet(self.host, hrow, hx, hy, self.host_scale, host_left, alpha)
            else:
                tops[who] = self.draw_pet(self.guest, grow, gx, gy, self.guest_scale, guest_left, alpha)

        hw, hh, htop = tops["host"]
        gw, gh, gtop = tops["guest"]
        if waving:
            ui.wave(hx + hw * 0.3, htop + hh * 0.5, 1, now)
            ui.wave(gx - gw * 0.3, gtop + gh * 0.5, -1, now + 200)
        if self.phase == "arrive":
            ui.puff(GUEST_X, ui.GROUND_Y, (now - self.phase_at - ARRIVE_MS) / LAND_MS)
        if act == "high5":
            p = (now - self.activity_at) / ACT_MS
            ui.burst(MIDDLE, min(htop, gtop) + 10, (p - 0.45) / 0.4)
        elif act == "dance":
            for i in range(4):
                phase = ((now + i * 350) % 1400) / 1400
                x = (hx, gx)[i % 2] + (i - 1.5) * 6
                ui.note(x, min(htop, gtop) + 6 - phase * 18,
                        color.rgb(110, 80, 200, int(255 * (1 - phase))))
        if act in ("high5", "snack") and (now - self.activity_at) > ACT_MS * 0.6:
            for i, (x, top) in enumerate(((hx, htop), (gx, gtop))):
                phase = ((now + i * 300) % 800) / 800
                screen.blit(pets.icon("heart"), vec2(int(x - 6), int(top + 4 - phase * 14)))

    def draw_bar(self, now):
        screen.pen = color.rgb(30, 26, 50, 210)
        screen.rectangle(0, ui.BAR_Y, screen.width, screen.height - ui.BAR_Y)
        if self.phase == "together" and int(now / 3500) % 2:
            text = HINTS[int(now / 7000) % 2]
        else:
            text = "With %s" % self.label
        ui.text(text, 80, ui.BAR_Y + 4, ui.WHITE, centre=True)

    def draw_toast(self, now):
        if now < self.toast_until:
            ui.toast(self.toast)

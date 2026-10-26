import os
import sys

APP_DIR = "/system/apps/space_pinball"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import math
import random

from badgeware import State

badge.mode(HIRES | VSYNC)

import art
import table as T

STATE_KEY = "space_pinball"
saved = {"best": 0, "best_rank": 0}
State.load(STATE_KEY, saved)
if not isinstance(saved.get("best"), int) or saved["best"] < 0:
    saved["best"] = 0
if not isinstance(saved.get("best_rank"), int) or not 0 <= saved["best_rank"] < 9:
    saved["best_rank"] = 0

BALLS_PER_GAME = 3
BALL_SAVE_MS = 6000
MIN_LAUNCH = 540.0
MAX_LAUNCH = 920.0
PULL_MS = 900.0

IMU_G = 16384.0
GYRO_PER_DPS = 114.3        # LSM6DS3 at +/-250 dps
LEAN_DEADZONE = 0.04
LEAN_LIMIT = 0.7
JOLT_G = 0.6
FLICK_DPS = 240.0
NUDGE_COOLDOWN_MS = 400
WARNING_DECAY = 0.35        # nudge warnings forgiven per second
DANGER_AT = 2.0
TILT_AT = 3.2

RANKS = ("CADET", "ENSIGN", "LIEUTENANT", "CAPTAIN", "LT COMMANDER",
         "COMMANDER", "COMMODORE", "ADMIRAL", "FLEET ADMIRAL")

# name, goal text, event that counts, target count
MISSIONS = (
    ("TARGET PRACTICE", "Hits", T.EV_DROP, 3),
    ("LAUNCH TRAINING", "Bumps", T.EV_BUMPER, 8),
    ("RE-ENTRY", "Lanes", T.EV_LANE, 3),
    ("HYPERSPACE", "Wormhole", T.EV_WORMHOLE, 1),
)

TITLE = 0
PLAY = 1
OVER = 2

AMBER = color.rgb(255, 176, 40)
AMBER_DIM = color.rgb(90, 60, 20)
CYAN = color.rgb(120, 230, 255)
WHITE = color.rgb(255, 255, 255)
RED = color.rgb(255, 70, 60)
YELLOW = color.rgb(255, 230, 80)
GREEN = color.rgb(120, 255, 140)
VEIL = color.rgb(0, 0, 10, 180)
BUMPER_COLORS = (color.rgb(255, 80, 80), color.rgb(80, 160, 255), color.rgb(255, 200, 40))
FLIPPER_RUBBER = color.rgb(220, 40, 50)
FLIPPER_BODY = color.rgb(235, 235, 245)
BALL_DARK = color.rgb(110, 115, 130)
BALL_MID = color.rgb(200, 205, 215)

background = art.build()
badge.default_clear = None


def commas(n):
    s = str(n)
    out = ""
    while len(s) > 3:
        out = "," + s[-3:] + out
        s = s[:-3]
    return s + out


class Motion:
    """Turns the IMU into a table lean and spots bumps."""

    def __init__(self):
        self.smooth = None
        self.level_x = 0.0
        self.gyro_bias = [0.0, 0.0, 0.0]
        self.lean = 0.0
        self.next_nudge = 0
        self.upside_down = badge.upside_down()

    def calibrate(self):
        if self.smooth:
            self.level_x = self.smooth[0] / IMU_G
        self.upside_down = badge.upside_down()

    def update(self, dt_ms):
        reading = badge.imu()
        ax, ay, az = reading[0], reading[1], reading[2]
        if self.smooth is None:
            self.smooth = [ax, ay, az]
            self.gyro_bias = [reading[3], reading[4], reading[5]]
            self.calibrate()
        smooth = self.smooth
        jx = ax - smooth[0]
        jy = ay - smooth[1]
        jz = az - smooth[2]
        jolt = math.sqrt(jx * jx + jy * jy + jz * jz) / IMU_G
        k = min(1.0, dt_ms / 90.0)
        smooth[0] += jx * k
        smooth[1] += jy * k
        smooth[2] += jz * k

        bias = self.gyro_bias
        spin = 0.0
        for axis in range(3):
            delta = reading[3 + axis] - bias[axis]
            spin += delta * delta
            bias[axis] += delta * min(1.0, dt_ms / 3000.0)
        spin = math.sqrt(spin) / GYRO_PER_DPS

        if badge.upside_down() != self.upside_down:
            self.calibrate()
        lean = smooth[0] / IMU_G - self.level_x
        if self.upside_down:
            lean = -lean
        if abs(lean) < LEAN_DEADZONE:
            lean = 0.0
        else:
            lean -= LEAN_DEADZONE if lean > 0 else -LEAN_DEADZONE
        self.lean = max(-LEAN_LIMIT, min(LEAN_LIMIT, lean))

        if (jolt > JOLT_G or spin > FLICK_DPS) and badge.ticks >= self.next_nudge:
            self.next_nudge = badge.ticks + NUDGE_COOLDOWN_MS
            return True
        return False


class Game:
    def __init__(self, motion=None):
        self.table = T.Table()
        self.motion = motion or Motion()
        self.mode = TITLE
        self.score = 0
        self.ball = 1
        self.rank = 0
        self.mission = 0
        self.progress = 0
        self.multiplier = 1
        self.warnings = 0.0
        self.tilted = False
        self.message = ""
        self.message_until = 0
        self.flash = 0.0
        self.lights = -1.0
        self.bumper_flash = [0, 0, 0]
        self.pull_start = None
        self.pull = 0.0
        self.launched_at = None
        self.ball_saved = False
        self.drop_reset_at = 0
        self.lane_reset_at = 0
        self.wormhole_release_at = 0
        self.next_ball_at = 0
        self.over_at = 0
        self.paused = False
        self.new_best = False
        self.await_release = True

    # ----- game flow -------------------------------------------------
    def start(self):
        self.__init__(self.motion)
        self.mode = PLAY
        self.serve()
        self.say("WELCOME CADET", 2500)

    def serve(self):
        t = self.table
        t.reset_ball()
        t.kickback = True
        for flipper in t.flippers:
            flipper.active = False
        self.tilted = False
        self.warnings = 0.0
        self.launched_at = None
        self.pull_start = None
        self.pull = 0.0
        if self.message == "TILT":
            self.message_until = 0
        self.motion.calibrate()

    def say(self, text, ms=1800):
        self.message = text
        self.message_until = badge.ticks + ms

    def add(self, points):
        if not self.tilted:
            self.score += points * self.multiplier

    def advance_mission(self, kind):
        name, _goal, wanted, target = MISSIONS[self.mission]
        if kind != wanted or self.tilted:
            return
        self.progress += 1
        if self.progress >= target:
            self.add(25000 * (self.rank + 1))
            if self.rank < len(RANKS) - 1:
                self.rank += 1
                self.say("PROMOTED!", 2600)
            else:
                self.say("MISSION DONE", 2600)
            self.mission = (self.mission + 1) % len(MISSIONS)
            self.progress = 0
            self.flash = 1.0

    def handle(self, events):
        t = self.table
        for kind, index in events:
            if kind == T.EV_BUMPER:
                self.add(500)
                self.bumper_flash[index] = badge.ticks + 120
                self.flash = max(self.flash, 0.7)
                self.advance_mission(kind)
            elif kind == T.EV_SLING:
                self.add(100)
            elif kind == T.EV_DROP:
                self.add(1500)
                self.advance_mission(kind)
                if not any(t.drops) and not self.drop_reset_at:
                    self.add(10000)
                    t.kickback = True
                    self.say("KICKBACK LIT")
                    self.drop_reset_at = badge.ticks + 1500
            elif kind == T.EV_LANE:
                if not t.lanes[index]:
                    t.lanes[index] = True
                    self.add(1000)
                    self.advance_mission(kind)
                    if all(t.lanes):
                        self.add(5000)
                        self.multiplier = min(5, self.multiplier + 1)
                        self.say("BONUS x%d" % self.multiplier)
                        self.lane_reset_at = badge.ticks + 1200
            elif kind == T.EV_WORMHOLE:
                self.add(7500)
                self.say("HYPERSPACE!", 1600)
                self.flash = 1.0
                self.wormhole_release_at = badge.ticks + 1300
                self.advance_mission(kind)
            elif kind == T.EV_KICKBACK:
                self.add(2000)
                self.say("KICKBACK!")
            elif kind == T.EV_DRAIN:
                self.drained()

    def drained(self):
        if (self.launched_at is not None and not self.ball_saved and not self.tilted
                and badge.ticks - self.launched_at < BALL_SAVE_MS):
            self.say("BALL SAVED")
            self.ball_saved = True
            self.serve()
            return
        self.ball_saved = False
        if self.ball >= BALLS_PER_GAME:
            self.game_over()
        else:
            self.ball += 1
            self.say("BALL %d" % self.ball, 1500)
            self.next_ball_at = badge.ticks + 1200

    def game_over(self):
        self.mode = OVER
        self.over_at = badge.ticks
        self.new_best = self.score > saved["best"]
        changed = False
        if self.new_best:
            saved["best"] = self.score
            changed = True
        if self.rank > saved["best_rank"]:
            saved["best_rank"] = self.rank
            changed = True
        if changed:
            try:
                State.save(STATE_KEY, saved)
            except OSError:
                pass

    def bump(self):
        t = self.table
        if self.tilted or not t.ball_live or t.captured:
            return
        side = self.motion.lean
        if side == 0.0:
            side = random.choice((-0.5, 0.5))
        t.nudge(side * 120.0, -150.0)
        self.warnings += 1.0
        if self.warnings > TILT_AT:
            self.tilted = True
            for flipper in t.flippers:
                flipper.active = False
            self.say("TILT", 60000)
        elif self.warnings > DANGER_AT:
            self.say("DANGER", 900)

    # ----- per frame -------------------------------------------------
    def update(self):
        dt_ms = min(40, max(1, badge.ticks_delta))
        now = badge.ticks
        bumped = self.motion.update(dt_ms)

        if self.mode == TITLE:
            if badge.pressed(BUTTON_SELECT):
                self.start()
            return
        if self.mode == OVER:
            if now - self.over_at > 1200 and badge.pressed(BUTTON_SELECT):
                self.start()
            return

        if badge.pressed(BUTTON_BACK):
            self.paused = not self.paused
        if self.paused:
            return
        if badge.pressed(BUTTON_MENU):
            self.motion.calibrate()
            self.say("TABLE LEVELED", 1200)

        t = self.table
        if self.next_ball_at:
            if now >= self.next_ball_at:
                self.next_ball_at = 0
                self.serve()
            return

        if bumped or badge.pressed(BUTTON_UP):
            self.bump()

        t.flippers[0].active = badge.held(BUTTON_LEFT) and not self.tilted
        t.flippers[1].active = badge.held(BUTTON_RIGHT) and not self.tilted

        # Plunger: hold SELECT (or DOWN), let go to launch.
        on_plunger = t.resting_on_plunger()
        holding = badge.held(BUTTON_SELECT) or badge.held(BUTTON_DOWN)
        if self.await_release:
            # The SELECT press that started the game must not fire the ball.
            self.await_release = holding
            holding = False
        if on_plunger and holding:
            if self.pull_start is None:
                self.pull_start = now
            self.pull = min(1.0, (now - self.pull_start) / PULL_MS)
        elif self.pull_start is not None:
            if on_plunger:
                t.launch(MIN_LAUNCH + (MAX_LAUNCH - MIN_LAUNCH) * self.pull)
                if self.launched_at is None:
                    self.launched_at = now
            self.pull_start = None
            self.pull = 0.0

        t.tilt_x = 0.0 if self.tilted else self.motion.lean
        events = []
        t.step(dt_ms / 1000.0, events)
        self.handle(events)

        if t.captured and now >= self.wormhole_release_at:
            t.release_wormhole()
        if self.drop_reset_at and now >= self.drop_reset_at:
            self.drop_reset_at = 0
            t.drops = [True, True, True]
        if self.lane_reset_at and now >= self.lane_reset_at:
            self.lane_reset_at = 0
            t.lanes = [False, False, False]

        self.warnings = max(0.0, self.warnings - WARNING_DECAY * dt_ms / 1000.0)
        self.flash = max(0.0, self.flash - 3.0 * dt_ms / 1000.0)

    # ----- drawing ---------------------------------------------------
    def draw(self):
        screen.blit(background, vec2(0, 0))
        screen.antialias = image.X2
        screen.fill_rule = image.EVEN_ODD
        self.draw_table()
        self.draw_panel()
        if self.mode == TITLE:
            self.draw_title()
        elif self.mode == OVER:
            self.draw_over()
        elif self.paused:
            self.draw_paused()
        elif self.tilted:
            self.draw_tilt()
        self.update_caselights()

    def draw_table(self):
        t = self.table
        now = badge.ticks
        blink = (now // 250) % 2

        for i, (x, y) in enumerate(T.LANE_LIGHTS):
            if t.lanes[i]:
                screen.pen = YELLOW
                screen.shape(shape.circle(x, y, 3.5))
        screen.pen = color.rgb(255, 120, 60)
        for i, y in enumerate(T.DROP_TARGETS):
            if t.drops[i]:
                screen.rectangle(T.LEFT + 1, y - 6, 4, 12)

        target = MISSIONS[self.mission][3]
        lit = int(3 * self.progress / target)
        for i in range(3):
            if i < lit or (i == lit and blink and self.mode == PLAY):
                screen.pen = AMBER if i < lit else AMBER_DIM
                screen.shape(shape.custom(art.chevron(93, 196 - i * 11, 6)))
        if t.kickback and blink:
            screen.pen = GREEN
            screen.shape(shape.custom(art.chevron(15, 228, 4)))

        for i, (x, y) in enumerate(T.BUMPERS):
            if now < self.bumper_flash[i]:
                screen.pen = WHITE
                screen.shape(shape.circle(x, y, T.BUMPER_R + 1))
            else:
                screen.pen = BUMPER_COLORS[i]
                screen.shape(shape.circle(x, y, T.BUMPER_R - 1))
                screen.pen = color.rgb(255, 255, 255, 120)
                screen.shape(shape.circle(x - 2, y - 2, 3))

        wx, wy = T.WORMHOLE
        spin = now / 4.0
        screen.pen = color.rgb(190, 120, 255, 200)
        for arm in range(3):
            a = math.radians(spin + arm * 120)
            screen.shape(shape.line(wx, wy, wx + math.cos(a) * 8, wy + math.sin(a) * 8, 1.5))

        plunger_y = T.FLOOR + 1 + self.pull * 10
        screen.pen = color.rgb(200, 200, 210)
        screen.rectangle(T.LANE + 4, int(plunger_y - 1), 10, 3)
        if self.pull > 0:
            screen.pen = color.rgb(255, 120, 60)
            bar = int(self.pull * 30)
            screen.rectangle(T.LANE + 2, T.FLOOR - 2 - bar, 2, bar)

        for flipper in t.flippers:
            self.draw_flipper(flipper)

        if t.ball_live or t.captured:
            x, y = t.x, t.y
            r = T.BALL_R
            if t.captured:
                left = max(0.0, (self.wormhole_release_at - now) / 1300.0)
                r = T.BALL_R * (0.3 + 0.7 * (1.0 - left))
                x += math.cos(now / 60.0) * 3 * left
                y += math.sin(now / 60.0) * 3 * left
            screen.pen = color.rgb(0, 0, 0, 90)
            screen.shape(shape.circle(x + 1.5, y + 1.5, r))
            screen.pen = BALL_DARK
            screen.shape(shape.circle(x, y, r))
            screen.pen = BALL_MID
            screen.shape(shape.circle(x - 0.6, y - 0.6, r * 0.75))
            screen.pen = WHITE
            screen.shape(shape.circle(x - 1.4, y - 1.4, r * 0.3))

    def draw_flipper(self, flipper):
        px, py = flipper.px, flipper.py
        tx, ty = flipper.tip()
        dx = (tx - px) / T.FLIPPER_LEN
        dy = (ty - py) / T.FLIPPER_LEN
        nx, ny = -dy, dx
        for grow, pen in ((1.0, FLIPPER_RUBBER), (0.0, FLIPPER_BODY)):
            rb = T.FLIPPER_R + 0.8 + grow
            rt = T.FLIPPER_R - 1.0 + grow
            screen.pen = pen
            screen.shape(shape.custom([
                vec2(px + nx * rb, py + ny * rb), vec2(tx + nx * rt, ty + ny * rt),
                vec2(tx - nx * rt, ty - ny * rt), vec2(px - nx * rb, py - ny * rb),
            ]))
            screen.shape(shape.circle(px, py, rb))
            screen.shape(shape.circle(tx, ty, rt))
        screen.pen = color.rgb(120, 120, 140)
        screen.shape(shape.circle(px, py, 1.5))

    def text_in(self, box, text, pen, typeface, right=False):
        x, y, w, h = box
        screen.font = typeface
        tw, th = screen.measure_text(text)
        tx = x + w - tw - 4 if right else x + (w - tw) // 2
        screen.pen = pen
        screen.text(text, int(tx), int(y + (h - th) // 2))

    def draw_panel(self):
        now = badge.ticks
        self.text_in(art.SCORE_BOX, commas(self.score), AMBER, font.ziplock, True)
        self.text_in(art.BALL_BOX, str(self.ball), AMBER, font.sins)
        self.text_in(art.MULT_BOX, "x%d" % self.multiplier, AMBER, font.sins)
        self.text_in(art.RANK_BOX, RANKS[self.rank], CYAN, font.nope)

        x, y, w, h = art.MISSION_BOX
        showing = self.message and now < self.message_until
        if showing and (self.message != "TILT" or (now // 300) % 2):
            pen = RED if self.message in ("TILT", "DANGER") else YELLOW
            self.text_in(art.MISSION_BOX, self.message, pen, font.nope)
        elif showing:
            pass
        elif self.mode == PLAY:
            name, goal, _kind, target = MISSIONS[self.mission]
            self.text_in((x, y + 1, w, 16), name, CYAN, font.nope)
            self.text_in((x, y + 17, w, 16), "%s %d/%d" % (goal, min(self.progress, target), target),
                         AMBER, font.nope)
        else:
            pen = YELLOW if (now // 400) % 2 else AMBER_DIM
            self.text_in(art.MISSION_BOX, "PRESS SELECT", pen, font.nope)

        screen.font = font.nope
        screen.pen = color.rgb(200, 200, 230)
        best = commas(saved["best"])
        tw, _ = screen.measure_text(best)
        screen.text(best, 312 - tw, 222)

    def veil(self, y, h):
        screen.pen = VEIL
        screen.rectangle(0, y, art.PANEL_X, h)

    def centred(self, text, y, pen, typeface):
        screen.font = typeface
        tw, _ = screen.measure_text(text)
        screen.pen = pen
        screen.text(text, int((art.PANEL_X - tw) / 2), int(y))

    def draw_title(self):
        self.veil(60, 120)
        self.centred("SPACE PINBALL", 68, YELLOW, font.ziplock)
        self.centred("Lean the badge to roll", 96, CYAN, font.nope)
        self.centred("Flick it to bump. Gently!", 110, CYAN, font.nope)
        self.centred("LEFT / RIGHT flippers", 128, WHITE, font.nope)
        self.centred("Hold SELECT, let go to launch", 142, WHITE, font.nope)
        if (badge.ticks // 400) % 2:
            self.centred("PRESS SELECT", 160, AMBER, font.nope)

    def draw_over(self):
        self.veil(70, 100)
        self.centred("GAME OVER", 78, RED, font.ziplock)
        self.centred("RANK: " + RANKS[self.rank], 106, CYAN, font.nope)
        if self.new_best:
            self.centred("NEW HIGH SCORE!", 122, YELLOW, font.nope)
        else:
            self.centred("BEST " + commas(saved["best"]), 122, WHITE, font.nope)
        if badge.ticks - self.over_at > 1200 and (badge.ticks // 400) % 2:
            self.centred("SELECT TO PLAY AGAIN", 146, AMBER, font.nope)

    def draw_paused(self):
        self.veil(80, 76)
        self.centred("PAUSED", 88, YELLOW, font.ziplock)
        self.centred("BACK to resume", 116, WHITE, font.nope)
        self.centred("MENU levels the table", 132, CYAN, font.nope)

    def draw_tilt(self):
        if (badge.ticks // 300) % 2:
            self.veil(92, 30)
            self.centred("TILT", 96, RED, font.ziplock)

    def update_caselights(self):
        level = round(self.flash * 0.8, 2)
        if level != self.lights:
            self.lights = level
            badge.caselights(level)


game = Game()


def update():
    game.update()
    game.draw()


def on_exit():
    badge.caselights(0)


run(update)

import math
import os
import random
import sys
import time

APP_DIRS = ("/remote/apps/gitgotchi", "/system/apps/gitgotchi", "/apps/gitgotchi", "/gitgotchi")
APP_DIR = next(path for path in APP_DIRS if is_dir(path))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State

import pets
import ui
import visit
from catch import Catch
from party import Party, HOST_X

try:
    from badgeware import link as badgelink
except ImportError:
    badgelink = None

try:
    import secrets
except ImportError:
    secrets = None

SAVE_KEY = "gitgotchi"
FRIENDS_KEY = "gitgotchi_friends"
GAME = "gitgotchi"
FRIENDS_MAX = 20
VISIT_MS = 5 * 60 * 1000            # a visit lasts while the badges stay linked, up to 5 minutes
VISIT_FUN = 20
ACT_FUN = 3
ACT_FUN_CAP = 15
PRETEND_SYNC_MS = 1500

# How fast things change, per second of real time.
HUNGER_RATE = 100 / (3 * 3600)      # full to empty in about 3 hours
HAPPY_RATE = 100 / (2.5 * 3600)
ENERGY_RATE = 100 / (6 * 3600)      # awake for about 6 hours
SLEEP_DARK = 100 / (40 * 60)        # a full recharge in 40 minutes with the lights off
SLEEP_LIGHT = SLEEP_DARK / 2
BUG_EVERY = 25 * 60                 # a new bug about every 25 minutes
SICK_CHANCE = 0.08 / 60
NEGLECT_LIMIT = 90 * 60             # empty meters this long and your pet wanders off
OFFLINE_RATE = 0.25                 # time passes slower while the app is closed
OFFLINE_CAP = 12 * 3600
MAX_BUGS = 4
BUG_SPOTS = (24, 136, 44, 116)

FRESH = {
    "pet": "",
    "hunger": 60.0,
    "happy": 60.0,
    "energy": 80.0,
    "bugs": 0,
    "sick": False,
    "asleep": False,
    "lights": True,
    "age": 0.0,
    "weight": 5,
    "neglect": 0.0,
    "next_bug": 0.0,
    "gone": False,
    "t": 0,
}

screen.antialias = image.X2

pet = dict(FRESH)
mode = "choose"
choose_index = 0
selected = 0
label_until = 0
message = ""
message_until = 0
anim = ""
anim_until = 0
anim_length = 1
food_kind = ""
clean_progress = -1.0
feed_choice = 0
pet_x = 80.0
target_x = 80.0
move_at = 0
facing_left = False
game = None
hatch_start = 0
save_at = 0
lights_level = -1
party = None
party_fun = 0
party_wish = None
friends = []


def now():
    try:
        if time.gmtime()[0] >= 2025:
            return int(time.time())
    except (OSError, OverflowError):
        pass
    return 0


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def save():
    global save_at
    pet["t"] = now()
    State.save(SAVE_KEY, pet)
    save_at = badge.ticks + 20000


def load():
    global mode
    saved = dict(FRESH)
    try:
        State.load(SAVE_KEY, saved)
    except (OSError, ValueError):
        pass
    for key, default in FRESH.items():
        value = saved.get(key, default)
        if isinstance(default, bool):
            pet[key] = bool(value)
        elif isinstance(default, (int, float)) and not isinstance(value, bool) and isinstance(value, (int, float)):
            pet[key] = type(default)(value)
        elif isinstance(default, str) and isinstance(value, str):
            pet[key] = value
        else:
            pet[key] = default
    for key in ("hunger", "happy", "energy"):
        pet[key] = clamp(pet[key])
    pet["bugs"] = int(clamp(pet["bugs"], 0, MAX_BUGS))

    if pet["pet"] not in pets.INFO:
        mode = "choose"
        return
    pets.keep_only(pet["pet"])
    if pet["gone"]:
        mode = "gone"
        return
    current = now()
    if current and pet["t"] and current > pet["t"]:
        simulate(min(current - pet["t"], OFFLINE_CAP), offline=True)
    mode = "home"


def name():
    return pets.INFO[pet["pet"]][0]


def say(text, ms=1800):
    global message, message_until
    message = text
    message_until = badge.ticks + ms


def play_anim(row, ms):
    global anim, anim_until, anim_length
    anim = row
    anim_until = badge.ticks + ms
    anim_length = ms


def busy():
    return badge.ticks < anim_until or clean_progress >= 0


def add_bug():
    pet["bugs"] = min(MAX_BUGS, pet["bugs"] + 1)


def fall_asleep(text):
    pet["asleep"] = True
    say(text)


def wake(text):
    pet["asleep"] = False
    pet["lights"] = True
    say(text)


def simulate(sec, offline=False):
    """Advance the pet's needs by `sec` seconds."""
    global mode
    pet["age"] += sec
    rate = OFFLINE_RATE if offline else 1.0
    drain = sec * rate * (0.35 if pet["asleep"] else 1.0)
    pet["hunger"] = clamp(pet["hunger"] - HUNGER_RATE * drain)
    sad = HAPPY_RATE * drain * (1 + 0.25 * pet["bugs"]) * (2 if pet["sick"] else 1)
    pet["happy"] = clamp(pet["happy"] - sad)
    if pet["asleep"]:
        pet["energy"] = clamp(pet["energy"] + sec * (SLEEP_LIGHT if pet["lights"] else SLEEP_DARK))
        if pet["energy"] >= 100:
            wake("Good morning!")
    else:
        pet["energy"] = clamp(pet["energy"] - ENERGY_RATE * sec * rate)

    if offline:
        # closing the app never makes your pet run away
        pet["hunger"] = max(pet["hunger"], 10)
        pet["happy"] = max(pet["happy"], 10)
        pet["bugs"] = min(MAX_BUGS, pet["bugs"] + int(sec * rate / BUG_EVERY))
        return

    if not pet["asleep"]:
        if pet["next_bug"] > 0:
            pet["next_bug"] -= sec
            if pet["next_bug"] <= 0:
                add_bug()
        elif random.random() < sec / BUG_EVERY:
            add_bug()

    if not pet["sick"] and (pet["bugs"] >= 3 or pet["hunger"] < 10 or pet["happy"] < 10):
        if random.random() < sec * SICK_CHANCE:
            pet["sick"] = True
            say("%s feels sick!" % name())

    if pet["hunger"] <= 0 or pet["happy"] <= 0:
        pet["neglect"] += sec
    else:
        pet["neglect"] = max(0, pet["neglect"] - sec)
    if pet["neglect"] > NEGLECT_LIMIT:
        pet["gone"] = True
        mode = "gone"
        save()
        return

    if not pet["asleep"] and pet["energy"] <= 0:
        fall_asleep("Too tired... Zzz")


def needs_help():
    if pet["asleep"]:
        return pet["sick"] or pet["hunger"] < 15
    return (pet["sick"] or pet["bugs"] >= 2 or pet["hunger"] < 25
            or pet["happy"] < 25 or pet["energy"] < 20)


def stage():
    if pet["age"] < 20 * 60:
        return 0
    return 1 if pet["age"] < 4 * 3600 else 2


# -------------------------------------------------------------------- visits

def own_login():
    login = str(getattr(secrets, "GITHUB_USERNAME", "") or "").strip().lstrip("@")
    return login if visit.valid_login(login) else ""


def badge_id(value):
    if isinstance(value, (bytes, bytearray)):
        return "".join("%02x" % b for b in value)
    return str(value)


def clean_name(value):
    value = str(value or "")
    return "".join(ch for ch in value if " " <= ch <= "~").strip()[:16]


class Radio:
    """Bluetooth badge-to-badge link with a PetLink meeting on top.

    In the simulator, which can't pair badges, UP on the home screen brings a
    pretend friend over instead.
    """

    def __init__(self):
        self.link = None
        self.proximity = None
        self.simulator = badgelink is not None and not hasattr(badgelink, "NEAR_RSSI")
        if badgelink is not None and not self.simulator:
            try:
                self.link = badgelink.Link(GAME)
                self.proximity = badgelink.Proximity(self.link)
            except Exception as error:
                print("gitgotchi: no badge link:", error)
                self.link = None
        self.was_linked = False
        self.meeting = None
        self.partner_id = ""
        self.partner_name = ""
        self.pretend_at = None
        self.events = []

    @property
    def central(self):
        return bool(getattr(self.link, "central", True)) if self.link else True

    def pretend(self, now):
        if self.simulator and self.pretend_at is None and self.meeting is None:
            self.pretend_at = now

    def update(self, now, listening):
        if self.pretend_at is not None:
            if self.meeting is None and now - self.pretend_at >= PRETEND_SYNC_MS:
                self.meeting = True
                self.partner_id = ""
                self.partner_name = "Pretend pal"
                kind = random.choice([k for k in pets.ORDER if k != pet["pet"]])
                self.events.append(("hello", {"kind": kind, "stage": 2, "flags": 0, "login": ""}))
            return
        if self.link is None:
            return
        link = self.link
        link.pump()
        linked = link.linked
        if linked and not self.was_linked:
            partner = link.partner
            if listening and partner is not None:
                self.partner_id = badge_id(partner.id)
                self.partner_name = clean_name(getattr(partner, "name", ""))
                hello = visit.encode_hello(pet["pet"], stage(), visit.SICK if pet["sick"] else 0, own_login())
                self.meeting = visit.Meeting(hello, now, random.getrandbits(8))
            else:
                link.leave()
                linked = False
        elif self.was_linked and not linked:
            if self.meeting is not None:
                self.meeting = None
                self.events.append(("lost",))
            self.proximity.clear()
        self.was_linked = linked

        meeting = self.meeting
        if linked and meeting is not None:
            for message in link.receive():
                self.events.extend(meeting.receive(message, link.send))
            meeting.pump(link.send, now, link.capacity())
            if meeting.expired(now):
                self.leave(now)
                self.events.append(("lost",))
        elif listening and not linked:
            self.proximity.update(now)
        link.update()

    def take_events(self):
        events = self.events
        self.events = []
        return events

    def act(self, activity, seed):
        if isinstance(self.meeting, visit.Meeting):
            self.meeting.act(self.link.send, activity, seed)

    def bye(self):
        if isinstance(self.meeting, visit.Meeting):
            self.meeting.say_bye(self.link.send)
            self.meeting.pump(self.link.send, badge.ticks, self.link.capacity())

    def leave(self, now):
        self.meeting = None
        self.pretend_at = None
        if self.link is not None and self.link.linked:
            partner = self.link.partner
            self.proximity.rest(partner.id if partner else None, now)
            self.link.leave()
        self.was_linked = False

    def status(self, now):
        """("syncing", progress), ("hello", 0) or (None, 0)."""
        if self.pretend_at is not None and self.meeting is None:
            return "syncing", min(1.0, (now - self.pretend_at) / PRETEND_SYNC_MS)
        if self.meeting is not None:
            return "hello", 0.0
        if self.proximity is not None and self.proximity.syncing() is not None:
            return "syncing", self.proximity.progress(now)
        return None, 0.0

    def lights(self, now):
        if self.proximity is None or self.meeting is not None:
            return None
        return self.proximity.lights(now)

    def close(self):
        if self.link is not None:
            try:
                self.link.close()
            except Exception:
                pass


def load_friends():
    saved = {"friends": []}
    try:
        State.load(FRIENDS_KEY, saved)
    except (OSError, ValueError):
        pass
    found = saved.get("friends")
    if not isinstance(found, list):
        return
    for item in found[-FRIENDS_MAX:]:
        if (isinstance(item, list) and len(item) == 4 and isinstance(item[0], str)
                and item[1] in pets.INFO and isinstance(item[2], str) and isinstance(item[3], int)):
            friends.append(item)


def remember_friend(friend_id, kind, owner):
    for item in friends:
        if item[0] == friend_id:
            item[1] = kind
            item[2] = owner
            item[3] += 1
            friends.remove(item)
            friends.append(item)
            break
    else:
        friends.append([friend_id, kind, owner, 1])
        del friends[:-FRIENDS_MAX]
    State.save(FRIENDS_KEY, {"friends": friends})


def start_visit(friend):
    """The other badge said hello: their pet jumps over."""
    global mode, party, party_fun, party_wish
    if mode not in ("home", "feed", "stats") or pet["asleep"] or pet["pet"] not in pets.INFO:
        radio.leave(badge.ticks)
        return
    if friend["login"]:
        owner = "@" + friend["login"]
    else:
        owner = radio.partner_name or "A friend"
    pets.keep_only(pet["pet"], friend["kind"])
    party = Party(pet["pet"], stage(), friend["kind"], friend["stage"], owner,
                  badge.ticks, radio.central, pet_x)
    party_fun = 0
    party_wish = None
    mode = "visit"
    pet["happy"] = clamp(pet["happy"] + VISIT_FUN)
    pet["energy"] = clamp(pet["energy"] - 5)
    if radio.partner_id:
        remember_friend(radio.partner_id, friend["kind"], owner)
    save()


def do_activity(activity, seed=None, send=True):
    global party_fun
    if seed is None:
        seed = random.getrandbits(8)
    if party.start(activity, seed, badge.ticks, send):
        if send:
            radio.act(activity, seed)
        if party_fun < ACT_FUN_CAP:
            party_fun += ACT_FUN
            pet["happy"] = clamp(pet["happy"] + ACT_FUN)


def end_visit(said_bye=False):
    if party is not None and party.phase != "bye":
        if said_bye:
            radio.bye()
        party.leave(badge.ticks)


def radio_update():
    listening = mode == "home" and not pet["asleep"] and pet["pet"] in pets.INFO
    radio.update(badge.ticks, listening)
    for event in radio.take_events():
        if event[0] == "hello":
            start_visit(event[1])
        elif party is None:
            if event[0] == "lost" and mode == "home":
                say("They wandered off")
        elif event[0] == "act":
            do_activity(event[1], event[2], send=False)
        else:
            end_visit()


def visit_update():
    global mode, party, pet_x, target_x, party_wish
    now = badge.ticks
    simulate(badge.ticks_delta / 1000)
    if mode == "gone":
        radio.leave(now)
        party = None
        return
    if party.phase == "together":
        if badge.pressed(BUTTON_BACK) or pet["asleep"] or now - party.together_at >= VISIT_MS:
            end_visit(said_bye=True)
        else:
            # Remember a press made mid-activity so it runs next.
            if badge.pressed(BUTTON_SELECT):
                party_wish = "high5"
            elif badge.pressed(BUTTON_UP):
                party_wish = "dance"
            elif badge.pressed(BUTTON_DOWN):
                party_wish = "snack"
            elif badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
                party_wish = "wave"
            if party.ready(now):
                choice = party_wish or party.auto(now)
                party_wish = None
                if choice:
                    do_activity(choice)
    party.update(now)
    if party.done:
        label = party.label
        party = None
        radio.leave(now)
        pets.keep_only(pet["pet"])
        pet_x = target_x = HOST_X
        mode = "home"
        say("Bye, %s!" % label, 2200)
        save()
        draw_home()
        return

    ui.room(pet["pet"], not pet["lights"])
    party.draw(now, not pet["lights"])
    ui.meters(pet["hunger"], pet["happy"], pet["energy"])
    party.draw_bar(now)
    party.draw_toast(now)
    if badge.ticks > save_at:
        save()


# ------------------------------------------------------------------ actions

def do_action(action):
    global mode, feed_choice, game, clean_progress
    if action == "stats":
        mode = "stats"
        return
    if action == "lights":
        if pet["lights"]:
            pet["lights"] = False
            if not pet["asleep"]:
                fall_asleep("Night night!")
        else:
            grumpy = pet["asleep"] and pet["energy"] < 60
            pet["lights"] = True
            pet["asleep"] = False
            if grumpy:
                pet["happy"] = clamp(pet["happy"] - 10)
                say("Grumpy... still sleepy")
            else:
                say("Good morning!")
        save()
        return
    if pet["asleep"]:
        say("Shh... %s is asleep" % name())
        return
    if busy():
        return
    if action == "feed":
        feed_choice = 0
        mode = "feed"
    elif action == "play":
        if pet["sick"]:
            say("Too sick to play")
        elif pet["energy"] < 15:
            say("Too sleepy to play")
        else:
            game = Catch(pet["pet"])
            mode = "game"
    elif action == "clean":
        if pet["bugs"]:
            clean_progress = 0.0
        else:
            say("No bugs here!")
    elif action == "heal":
        if pet["sick"]:
            pet["sick"] = False
            pet["happy"] = clamp(pet["happy"] - 5)
            play_anim("happy", 1500)
            say("All patched up!")
            save()
        else:
            say("%s isn't sick" % name())


def eat(kind):
    global food_kind
    if kind == "meal":
        if pet["hunger"] >= 95:
            say("I'm full!")
            return
        pet["hunger"] = clamp(pet["hunger"] + 35)
        pet["weight"] += 1
        if pet["next_bug"] <= 0:
            pet["next_bug"] = random.randint(120, 300)
    else:
        pet["hunger"] = clamp(pet["hunger"] + 10)
        pet["happy"] = clamp(pet["happy"] + 15)
        pet["weight"] += 2
    food_kind = kind
    play_anim("eat", 2400)
    say("Yum!", 2400)
    save()


def adopt(kind):
    global mode, hatch_start, pet_x, target_x, selected
    pet.clear()
    pet.update(FRESH)
    pet["pet"] = kind
    pets.keep_only(kind)
    pet_x = target_x = 80.0
    selected = 0
    hatch_start = badge.ticks
    mode = "hatch"
    save()


# ------------------------------------------------------------------- screens

def choose_update():
    global choose_index
    if badge.pressed(BUTTON_LEFT):
        choose_index = (choose_index - 1) % len(pets.ORDER)
    if badge.pressed(BUTTON_RIGHT):
        choose_index = (choose_index + 1) % len(pets.ORDER)
    if badge.pressed(BUTTON_SELECT):
        adopt(pets.ORDER[choose_index])
        return

    kind = pets.ORDER[choose_index]
    title, blurb, _, wall = pets.INFO[kind]
    screen.pen = color.rgb(*wall)
    screen.clear()
    screen.pen = color.rgb(wall[0] * 7 // 10, wall[1] * 7 // 10, wall[2] * 7 // 10)
    screen.rectangle(0, 78, screen.width, 42)
    ui.text("Pick your pet!", 80, 4, face=font.sins, centre=True)
    w, _ = pets.size(kind)
    ui.shadow(80, w, 79)
    pets.draw(kind, "idle", 80, 80)
    nudge = int(badge.ticks / 300) % 2
    ui.text("<", 10 - nudge, 46, face=font.sins)
    ui.text(">", 144 + nudge, 46, face=font.sins)
    ui.text(title, 80, 84, face=font.sins, centre=True)
    ui.text(blurb, 80, 98, ui.INK, centre=True)
    for i in range(len(pets.ORDER)):
        screen.pen = ui.INK if i == choose_index else color.rgb(36, 32, 56, 70)
        screen.shape(shape.circle(65 + i * 10, 114, 2))


def hatch_update():
    global mode
    t = badge.ticks - hatch_start
    kind = pet["pet"]
    if badge.pressed(BUTTON_SELECT) or t > 4800:
        mode = "home"
        play_anim("happy", 1200)
        return
    ui.room(kind, False)
    if t < 2600:
        ui.egg(80, ui.GROUND_Y, pets.INFO[kind][2], max(0, (t - 1000) / 1600), 1 + t / 900)
        ui.toast("Your egg is hatching...")
    else:
        w, _ = pets.size(kind)
        ui.shadow(80, w)
        pets.draw(kind, "happy", 80, ui.GROUND_Y)
        ui.toast("Hi! I'm %s!" % name())
        if t < 2900:
            screen.pen = color.rgb(255, 255, 255, int(255 * (2900 - t) / 300))
            screen.rectangle(0, 0, screen.width, screen.height)


def move_pet():
    global pet_x, target_x, move_at, facing_left
    if pet["asleep"] or busy():
        return
    if badge.ticks > move_at:
        target_x = random.randint(36, 124)
        move_at = badge.ticks + random.randint(3000, 7000)
    speed = 9 if pet["sick"] else 18
    step = speed * badge.ticks_delta / 1000
    if abs(target_x - pet_x) <= step:
        pet_x = target_x
    else:
        facing_left = target_x < pet_x
        pet_x += step if target_x > pet_x else -step


def home_update():
    global mode, selected, label_until, clean_progress
    if badge.pressed(BUTTON_LEFT):
        selected = (selected - 1) % len(ui.ACTIONS)
        label_until = badge.ticks + 1200
    if badge.pressed(BUTTON_RIGHT):
        selected = (selected + 1) % len(ui.ACTIONS)
        label_until = badge.ticks + 1200
    if badge.pressed(BUTTON_SELECT):
        do_action(ui.ACTIONS[selected])
        if mode != "home":
            return
    if badge.pressed(BUTTON_MENU):
        mode = "confirm"
        return
    if badge.pressed(BUTTON_UP) and radio.simulator:
        radio.pretend(badge.ticks)

    simulate(badge.ticks_delta / 1000)
    if mode != "home":
        return
    move_pet()

    if clean_progress >= 0:
        clean_progress += badge.ticks_delta / 1400
        if clean_progress >= 1:
            clean_progress = -1.0
            pet["bugs"] = 0
            play_anim("happy", 1200)
            say("Bugs squashed!")
            save()
    if badge.ticks > save_at:
        save()
    draw_home()


def draw_home():
    kind = pet["pet"]
    t = badge.ticks
    dark = not pet["lights"]
    ui.room(kind, dark)

    sweep = clean_progress * 200 - 20 if clean_progress >= 0 else -999
    for i in range(pet["bugs"]):
        bx = BUG_SPOTS[i]
        if bx > sweep:
            ui.bug(bx, ui.GROUND_Y + 3 - (i % 2) * 6, t + i * 90)

    if pet["age"] < 20 * 60:
        scale = 0.75
    else:
        scale = 1.0
    if pet["asleep"]:
        row = "sleep"
    elif t < anim_until:
        row = anim
    else:
        row = "idle"
    w, h = pets.size(kind, scale)
    ui.shadow(pet_x, w)
    flip = facing_left and kind in ("duck", "squirrel")
    top = pets.draw(kind, row, pet_x, ui.GROUND_Y, scale, flip=flip, alpha=170 if dark else 255)

    if row == "eat":
        progress = 1 - (anim_until - t) / anim_length
        side = -1 if flip else 1
        ui.food(food_kind, pet_x + side * (w / 2 + 6), ui.GROUND_Y - 2, 1 - int(progress * 4) / 3)
    if row == "happy":
        for i in range(2):
            phase = ((t + i * 400) % 800) / 800
            hx = pet_x + (i * 2 - 1) * (w / 2 + 2)
            screen.blit(pets.icon("heart"), vec2(int(hx - 6), int(top + 8 - phase * 16)))
    if pet["asleep"]:
        for i in range(3):
            phase = ((t / 1000 + i * 0.6) % 1.8) / 1.8
            ui.text("z", pet_x + w / 3 + phase * 14, top + 4 - phase * 18,
                    color.rgb(180, 190, 255, int(255 * (1 - phase))))
    elif pet["sick"]:
        ui.bubble(pet_x + w / 2, top + 6, "+", color.rgb(220, 50, 60))
    elif needs_help() and int(t / 500) % 2 and row == "idle":
        ui.bubble(pet_x + w / 2, top + 6, "!", color.rgb(220, 50, 60))

    if clean_progress >= 0:
        for i in range(6):
            by = 24 + i * 14 + math.sin(t / 90 + i) * 3
            screen.pen = color.rgb(170, 225, 255, 200)
            screen.shape(shape.circle(sweep + (i % 2) * 6, by, 5 + (i % 3)))
            screen.pen = ui.WHITE
            screen.shape(shape.circle(sweep + (i % 2) * 6 - 2, by - 2, 1.2))

    ui.meters(pet["hunger"], pet["happy"], pet["energy"])
    ui.action_bar(selected)
    if mode in ("stats", "confirm", "feed"):
        return
    state, progress = radio.status(t) if mode == "home" else (None, 0)
    if state == "syncing":
        ui.toast("Someone's nearby...")
        ui.pill(50, 33, 60, 4, color.rgb(0, 0, 0, 60))
        ui.pill(50, 33, max(4, 60 * progress), 4, color.rgb(250, 90, 140))
    elif state == "hello":
        ui.toast("Saying hi...")
    elif t < message_until:
        ui.toast(message)
    elif t < label_until:
        ui.toast(ui.LABELS[ui.ACTIONS[selected]])


def feed_update():
    global mode, feed_choice
    if badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_LEFT):
        feed_choice = 0
    if badge.pressed(BUTTON_DOWN) or badge.pressed(BUTTON_RIGHT):
        feed_choice = 1
    if badge.pressed(BUTTON_BACK):
        mode = "home"
    elif badge.pressed(BUTTON_SELECT):
        mode = "home"
        eat(("meal", "snack")[feed_choice])
    draw_home()
    ui.panel(40, 30, 80, 50)
    ui.text("Feed %s" % name(), 80, 34, centre=True)
    for i, (label, kind) in enumerate((("Meal", "meal"), ("Snack", "snack"))):
        y = 48 + i * 14
        if i == feed_choice:
            ui.pill(46, y - 1, 68, 13, color.rgb(214, 204, 255))
        ui.food(kind, 56, y + 11, 1)
        ui.text(label, 68, y + 1)


def hearts(label, value, y):
    ui.text(label, 26, y)
    full = math.ceil(value / 25)
    sprite = pets.icon("heart")
    for i in range(4):
        screen.alpha = 255 if i < full else 50
        screen.blit(sprite, vec2(82 + i * 13, y - 1))
    screen.alpha = 255


def age_text():
    age = int(pet["age"])
    if age < 3600:
        return "%d min" % (age // 60)
    if age < 86400:
        return "%d h" % (age // 3600)
    return "%d days" % (age // 86400)


def stats_update():
    global mode
    if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_SELECT):
        mode = "home"
    simulate(badge.ticks_delta / 1000)
    draw_home()
    ui.panel(16, 14, 128, 92)
    grown = ("Baby", "Kid", "Grown-up")[stage()]
    ui.text(name(), 80, 17, face=font.sins, centre=True)
    ui.text("%s, %s" % (grown, age_text()), 80, 32, color.rgb(110, 100, 150), centre=True)
    hearts("Food", pet["hunger"], 46)
    hearts("Fun", pet["happy"], 58)
    hearts("Energy", pet["energy"], 70)
    health = "Sick" if pet["sick"] else "Healthy"
    ui.text("Weight %d  %s" % (pet["weight"], health), 80, 83,
            color.rgb(110, 100, 150), centre=True)
    ui.text("Friends met: %d" % len(friends), 80, 94, color.rgb(110, 100, 150), centre=True)


def confirm_update():
    global mode
    if badge.pressed(BUTTON_BACK):
        mode = "home"
    elif badge.pressed(BUTTON_SELECT):
        pets.keep_only(None)
        mode = "choose"
        return
    draw_home()
    ui.panel(16, 34, 128, 46)
    ui.text("Start over with", 80, 38, centre=True)
    ui.text("a new pet?", 80, 49, centre=True)
    ui.text("SELECT yes", 22, 65, color.rgb(110, 100, 150))
    ui.text("BACK no", 138, 65, color.rgb(110, 100, 150), right=True)


def game_update():
    global mode, game
    if badge.pressed(BUTTON_BACK) and not game.done:
        game.done = True
    elif game.done and badge.pressed(BUTTON_SELECT):
        score = game.score
        pet["happy"] = clamp(pet["happy"] + min(45, 5 + score * 3))
        pet["energy"] = clamp(pet["energy"] - 10)
        pet["hunger"] = clamp(pet["hunger"] - 5)
        pet["weight"] = max(3, pet["weight"] - 1)
        game = None
        mode = "home"
        play_anim("happy", 1500)
        say("That was fun!" if score else "Nice try!")
        save()
        return
    game.update()
    game.draw()


def gone_update():
    if badge.pressed(BUTTON_SELECT):
        pets.keep_only(None)
        globals()["mode"] = "choose"
        return
    kind = pet["pet"]
    ui.room(kind, True)
    float_y = ui.GROUND_Y - 4 - math.sin(badge.ticks / 400) * 3
    pets.draw(kind, "gone", 80, float_y, alpha=170, speed=200)
    ui.panel(20, 3, 120, 36)
    ui.text("%s went to" % name(), 80, 6, centre=True)
    ui.text("touch grass.", 80, 17, centre=True)
    ui.text("SELECT: new pet", 80, 28, color.rgb(110, 100, 150), centre=True)


SCREENS = {
    "choose": choose_update,
    "hatch": hatch_update,
    "home": home_update,
    "feed": feed_update,
    "stats": stats_update,
    "confirm": confirm_update,
    "game": game_update,
    "gone": gone_update,
    "visit": visit_update,
}


def caselights():
    global lights_level
    level = 0
    lights = radio.lights(badge.ticks) if mode == "home" else None
    if lights is not None:
        lights_level = -1
        try:
            badge.caselights(*lights)
        except (AttributeError, OSError, TypeError):
            pass
        return
    if mode == "visit":
        level = round(0.15 + 0.1 * (math.sin(badge.ticks / 250) + 1), 2)
    elif mode == "home" and needs_help():
        level = round(0.1 + 0.25 * (math.sin(badge.ticks / 300) + 1), 2)
    if level != lights_level:
        lights_level = level
        try:
            badge.caselights(level)
        except (AttributeError, OSError, TypeError):
            pass


def update():
    radio_update()
    SCREENS[mode]()
    caselights()


def on_exit():
    if party is not None:
        radio.bye()
    radio.leave(badge.ticks)
    radio.close()
    if pet["pet"] in pets.INFO:
        save()
    try:
        badge.caselights(0)
    except (AttributeError, OSError, TypeError):
        pass


radio = Radio()
load_friends()
load()
run(update)

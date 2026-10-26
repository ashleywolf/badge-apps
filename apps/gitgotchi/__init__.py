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
from catch import Catch

SAVE_KEY = "gitgotchi"

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
    if t < message_until:
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
    ui.panel(16, 18, 128, 84)
    stage = "Baby" if pet["age"] < 20 * 60 else "Kid" if pet["age"] < 4 * 3600 else "Grown-up"
    ui.text(name(), 80, 21, face=font.sins, centre=True)
    ui.text("%s, %s" % (stage, age_text()), 80, 36, color.rgb(110, 100, 150), centre=True)
    hearts("Food", pet["hunger"], 50)
    hearts("Fun", pet["happy"], 62)
    hearts("Energy", pet["energy"], 74)
    health = "Sick" if pet["sick"] else "Healthy"
    ui.text("Weight %d  %s" % (pet["weight"], health), 80, 88,
            color.rgb(110, 100, 150), centre=True)


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
}


def caselights():
    global lights_level
    level = 0
    if mode == "home" and needs_help():
        level = round(0.1 + 0.25 * (math.sin(badge.ticks / 300) + 1), 2)
    if level != lights_level:
        lights_level = level
        try:
            badge.caselights(level)
        except (AttributeError, OSError, TypeError):
            pass


def update():
    SCREENS[mode]()
    caselights()


def on_exit():
    if pet["pet"] in pets.INFO:
        save()
    try:
        badge.caselights(0)
    except (AttributeError, OSError, TypeError):
        pass


load()
run(update)

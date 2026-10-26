import gc
import math

from petdata import ICONS, PETS, ROWS

ORDER = ("mona", "duck", "squirrel", "copilot")

# name, one-line blurb, egg spot colour, room wall colour
INFO = {
    "mona": ("Mona", "A curious octocat", (60, 90, 200), (214, 224, 250)),
    "duck": ("Ducky", "Listens to your bugs", (255, 190, 40), (206, 236, 250)),
    "squirrel": ("Shipit", "Ships it. Fast.", (160, 90, 50), (222, 238, 208)),
    "copilot": ("Copilot", "Loves to help you build", (130, 110, 250), (232, 224, 255)),
}

icons = image.load("assets/icons.png").spritesheet(len(ICONS), 1)
_sheets = {}


def icon(name):
    return icons.sprite(ICONS.index(name), 0)


def sheet(kind):
    if kind not in _sheets:
        data = PETS[kind]
        _sheets[kind] = image.load("assets/%s.png" % kind).spritesheet(data["columns"], len(ROWS))
    return _sheets[kind]


def keep_only(kind):
    for name in list(_sheets):
        if name != kind:
            del _sheets[name]
    gc.collect()


def size(kind, scale=1.0):
    data = PETS[kind]
    s = data["scale"] * scale
    return data["cell"][0] * s, data["cell"][1] * s


def draw(kind, row, x, y, scale=1.0, flip=False, alpha=255, speed=150, ms=None):
    """Draw one frame of a pet with its feet centred on (x, y).

    Returns the y of the top of the sprite so callers can place bubbles.
    """
    data = PETS[kind]
    r = ROWS.index(row)
    t = badge.ticks if ms is None else ms
    sprite = sheet(kind).sprite(int(t / speed) % data["frames"][r], r)
    w, h = size(kind, scale)
    if row == "happy":
        y -= abs(math.sin(t / 160)) * 6 * scale
    elif data["bob"] and row == "idle":
        y -= (math.sin(t / 260) + 1) * scale
    w = int(w)
    h = int(h)
    top = int(y) - h
    screen.alpha = alpha
    screen.blit(sprite, rect(int(x - w / 2), top, -w if flip else w, h))
    screen.alpha = 255
    return top

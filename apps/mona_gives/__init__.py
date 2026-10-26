import math
import os
import random
import sys

APP_DIRS = ("/remote/apps/mona_gives", "/system/apps/mona_gives", "/apps/mona_gives", "/mona_gives")
APP_DIR = next((path for path in APP_DIRS if is_dir(path)), APP_DIRS[1])
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import json

import depscan
import heartlink
from badgeware import State
from maintainers import CURATED

try:
    from badgeware import link as badgelink
except ImportError:
    badgelink = None

try:
    import fetch
    import wifi
    if hasattr(fetch, "AsyncFetch"):
        fetch.AsyncFetch.MAX_HEADER_BYTES = max(8192, fetch.AsyncFetch.MAX_HEADER_BYTES)
except ImportError:
    fetch = wifi = None

try:
    import secrets
except ImportError:
    secrets = None

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

GAME = "mona_gives"
STATE_KEY = "mona_gives"
# Data synced by tools/mona_gives_sync.py. Copy it to /state with mpremote, or
# drop personal.json into this app's folder in USB Disk Mode.
PERSONAL_FILE = "/state/mona_gives_personal.json"
PERSONAL_FALLBACK = APP_DIR + "/personal.json"
# Results of the on-badge public scan (depscan.py) of the GitHub user, org or
# owner/repo named by MONA_GIVES_SOURCE or GITHUB_USERNAME in secrets.
STATE_DIR = "/state"
SCAN_FILE = STATE_DIR + "/mona_gives_scan.json"
MET_FILE = STATE_DIR + "/mona_gives_met.json"
# Optional GitHub Sponsors attribution tag, for example "universe26". When set,
# QR codes add ?metadata_campaign=<value>, which GitHub shares with the
# maintainer in their sponsorship export. Leave empty for plain links.
CAMPAIGN = ""

W = screen.width
H = screen.height
ATTRACT_MS = 25000
SEEK_MS = 10000
SEEK_GRACE_MS = 3000
ATTRACT_SHOW_MS = 7800
ATTRACT_QR_MS = 9000
TOSS_MS = 900
CATCH_MS = 1900
PASSED_MS = 3500
CELEBRATE_MS = 7000
LINGER_MS = 700
FOUND_LIMIT = 200
MET_LIMIT = 50

BG = color.rgb(13, 17, 23)
PANEL = color.rgb(22, 27, 34)
RAISED = color.rgb(33, 38, 45)
BORDER = color.rgb(48, 54, 61)
FG = color.rgb(230, 237, 243)
MUTED = color.rgb(139, 148, 158)
GREEN = color.rgb(63, 185, 80)
GREEN_BTN = color.rgb(35, 134, 54)
GREEN_DARK = color.rgb(26, 127, 55)
LIGHT_GREEN = color.rgb(170, 240, 180)
BLUE = color.rgb(88, 166, 255)
PINK = color.rgb(219, 97, 162)
WHITE = color.rgb(255, 255, 255)
BLACK = color.rgb(0, 0, 0)
GLOWS = [color.rgb(63, 185, 80, alpha) for alpha in (26, 44, 70)]

try:
    body_font = font.load("/system/assets/fonts/MonaSans-Medium.af")
except Exception:
    body_font = font.ark
title_font = font.ignore

mona_idle = image.load("assets/mona/mona-default.png").spritesheet(11, 1)
mona_dance = image.load("assets/mona/mona-dance.png").spritesheet(6, 1)
MONA_W = 28
MONA_H = 24


def heart_points(steps=36):
    points = []
    for i in range(steps):
        t = i / steps * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        points.append(vec2(x / 16, -y / 16 + 0.1))
    return points


HEART = shape.custom(heart_points())


# ---------------------------------------------------------------- drawing ---

def wave(period, phase=0.0):
    return math.sin((badge.ticks / period + phase) * 2 * math.pi)


def ease_out(t):
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) * (1 - t)


def draw_heart(x, y, r, pen=GREEN, glow=False, shine=True):
    if r <= 0.5:
        return
    if glow:
        for index, glow_pen in enumerate(GLOWS):
            screen.pen = glow_pen
            HEART.transform = mat3().translate(x, y).scale(r * (1.9 - index * 0.28), r * (1.9 - index * 0.28))
            screen.shape(HEART)
    screen.pen = pen
    HEART.transform = mat3().translate(x, y).scale(r, r)
    screen.shape(HEART)
    if shine and r >= 6:
        screen.pen = color.rgb(255, 255, 255, 150)
        screen.shape(shape.circle(x - r * 0.42, y - r * 0.38, r * 0.17))


def draw_mona(x, y, scale, dancing=False, flip=False, speed=1.0):
    if dancing:
        sprite = mona_dance.sprite(int(badge.ticks * speed / 110) % 6, 0)
    else:
        sprite = mona_idle.sprite(int(badge.ticks * speed / 150) % 11, 0)
    w = MONA_W * scale
    h = MONA_H * scale
    if flip:
        screen.blit(sprite, rect(x, y, -w, h))
    else:
        screen.blit(sprite, rect(x, y, w, h))


def measure(text, size=None, typeface=None):
    screen.font = typeface or body_font
    return screen.measure_text(text, size) if size else screen.measure_text(text)


def write(text, x, y, size=15, pen=FG, typeface=None):
    screen.font = typeface or body_font
    screen.pen = pen
    if size:
        screen.text(text, x, y, size)
    else:
        screen.text(text, x, y)


def fit(text, width, size=15, typeface=None):
    if measure(text, size, typeface)[0] <= width:
        return text
    while text and measure(text + "...", size, typeface)[0] > width:
        text = text[:-1]
    return text + "..."


def centred(text, y, size=15, pen=FG, typeface=None, x=0, width=None):
    width = W if width is None else width
    text = fit(text, width - 8, size, typeface)
    tw = measure(text, size, typeface)[0]
    write(text, x + (width - tw) / 2, y, size, pen, typeface)


def headline(text, y, pen=FG, width=W, x=0):
    """Big pixel-font text, falling back to Mona Sans when it is too wide."""
    if measure(text, None, title_font)[0] <= width - 12:
        centred(text, y, None, pen, title_font, x, width)
    else:
        centred(text, y + 2, 20, pen, body_font, x, width)


def paragraph(text, x, y, width, height, size=15, pen=FG):
    screen.font = body_font
    screen.pen = pen
    screen.text(text, rect(x, y, width, height), size)


def panel(x, y, w, h, fill=PANEL, outline=BORDER, radius=8, thickness=1):
    if outline is not None:
        screen.pen = outline
        screen.shape(shape.rounded_rectangle(x, y, w, h, radius))
        screen.pen = fill
        screen.shape(shape.rounded_rectangle(x + thickness, y + thickness, w - thickness * 2, h - thickness * 2, max(1, radius - thickness)))
    else:
        screen.pen = fill
        screen.shape(shape.rounded_rectangle(x, y, w, h, radius))


def footer(text):
    screen.pen = BORDER
    screen.rectangle(0, H - 22, W, 1)
    centred(text, H - 18, 12, MUTED)


def identicon(login, x, y, size):
    value = 2166136261
    for ch in login.lower():
        value = ((value ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    hue = (value >> 16) & 3
    ink = (GREEN, BLUE, PINK, color.rgb(210, 153, 34))[hue]
    screen.pen = RAISED
    screen.shape(shape.circle(x + size / 2, y + size / 2, size / 2))
    cell = size * 0.7 / 5
    left = x + size * 0.15
    top = y + size * 0.15
    screen.pen = ink
    for row in range(5):
        for col in range(3):
            if value & (1 << (row * 3 + col)):
                for mirrored in {col, 4 - col}:
                    screen.rectangle(left + mirrored * cell, top + row * cell, cell + 0.5, cell + 0.5)


_avatars = {}


def avatar(login):
    key = login.lower()
    if key not in _avatars:
        if len(_avatars) > 6:
            _avatars.clear()
        _avatars[key] = None
        for path in ("assets/avatars/%s.png" % key, depscan.avatar_path(STATE_DIR, key)):
            if file_exists(path):
                try:
                    _avatars[key] = image.load(path)
                    break
                except Exception:
                    pass
    return _avatars[key]


def draw_avatar(login, x, y, size, ring=None):
    if ring is not None:
        screen.pen = ring
        screen.shape(shape.circle(x + size / 2, y + size / 2, size / 2 + 3))
        screen.pen = BG
        screen.shape(shape.circle(x + size / 2, y + size / 2, size / 2 + 1))
    img = avatar(login)
    if img is None:
        identicon(login, x, y, size)
    else:
        screen.blit(img, rect(x, y, size, size))


_qr_cache = {}


QR_BORDER = 1
QR_LEVEL = image.QR_HIGH
QR_MARGIN = 6
QR_DOTS = color.rgb(26, 127, 55)
QR_EYES = color.rgb(17, 99, 41)


def qr_for(url):
    if url not in _qr_cache:
        _qr_cache.clear()
        # High error correction leaves room for the heart in the middle.
        code = image.qr(url, QR_LEVEL, QR_BORDER)
        try:
            code.palette[1] = QR_DOTS
        except (AttributeError, IndexError, TypeError):
            pass
        _qr_cache[url] = code
    return _qr_cache[url]


def draw_qr(url, x, y, size):
    code = qr_for(url)
    modules = max(1, code.width)
    scale = max(1, int((size - QR_MARGIN) // modules))
    drawn = modules * scale
    pad = (size - drawn) // 2
    panel(x, y, size, size, WHITE, None, 8)
    ox, oy = x + pad, y + pad
    screen.blit(code, rect(0, 0, code.width, code.height), rect(ox, oy, drawn, drawn))
    far = modules - QR_BORDER - 7
    if far <= QR_BORDER:
        return
    for mx, my in ((QR_BORDER, QR_BORDER), (far, QR_BORDER), (QR_BORDER, far)):
        ex, ey = ox + mx * scale, oy + my * scale
        screen.pen = QR_EYES
        screen.rectangle(ex, ey, 7 * scale, 7 * scale)
        screen.pen = WHITE
        screen.rectangle(ex + scale, ey + scale, 5 * scale, 5 * scale)
        screen.pen = QR_EYES
        screen.rectangle(ex + 2 * scale, ey + 2 * scale, 3 * scale, 3 * scale)
    inner = modules - 2 * QR_BORDER
    logo = max(5, (inner * 2 // 9) | 1)
    box = logo * scale
    lx = ox + (modules - logo) * scale // 2
    ly = oy + (modules - logo) * scale // 2
    screen.pen = WHITE
    screen.rectangle(lx, ly, box, box)
    draw_heart(lx + box / 2, ly + box / 2 + scale / 2, box * 0.36, GREEN_BTN, shine=False)


class Particles:
    def __init__(self):
        self.items = []

    def burst(self, x, y, count=14, speed=120.0, size=5.0):
        for _ in range(count):
            angle = random.random() * 2 * math.pi
            velocity = speed * (0.4 + random.random() * 0.8)
            self.items.append([x, y, math.cos(angle) * velocity, math.sin(angle) * velocity - 40,
                               0, 700 + random.randint(0, 600), size * (0.6 + random.random() * 0.7)])
        if len(self.items) > 90:
            self.items = self.items[-90:]

    def rain(self, count=1):
        for _ in range(count):
            self.items.append([random.randint(0, W), -10, random.uniform(-20, 20), random.uniform(60, 130),
                               0, 3500, random.uniform(3, 7)])

    def update(self, dt):
        alive = []
        for p in self.items:
            p[4] += dt * 1000
            if p[4] < p[5] and p[1] < H + 20:
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[3] += 90 * dt
                alive.append(p)
        self.items = alive

    def draw(self):
        for x, y, _, _, age, life, size in self.items:
            fade = 1 - age / life
            pen = color.rgb(63, 185, 80, int(255 * fade)) if size > 4.5 else color.rgb(170, 240, 180, int(230 * fade))
            draw_heart(x, y, size, pen, shine=False)


# ------------------------------------------------------------------- data ---

def curated_card(entry):
    ident, login, name, project, blurb = entry
    return {"id": ident, "login": login, "name": name, "project": project, "blurb": blurb, "verified": True}


CURATED_BY_LOGIN = {}
CURATED_BY_ID = {}
for _entry in CURATED:
    _card = curated_card(_entry)
    CURATED_BY_LOGIN[_card["login"].lower()] = _card
    CURATED_BY_ID[_card["id"]] = _card


def clean_card(raw, verified):
    if not isinstance(raw, dict) or not heartlink.valid_login(raw.get("login")):
        return None
    login = raw["login"]
    known = CURATED_BY_LOGIN.get(login.lower())
    card = {
        "login": login,
        "name": heartlink.clean_text(raw.get("name"), 40) or (known["name"] if known else login),
        "project": heartlink.clean_text(raw.get("project"), 80) or (known["project"] if known else ""),
        "blurb": heartlink.clean_text(raw.get("blurb"), 60) or (known["blurb"] if known else ""),
        "verified": verified or bool(known),
    }
    via = heartlink.clean_text(raw.get("via"), 80)
    if via:
        card["via"] = via
    if raw.get("how") == "npm" and not card["verified"]:
        card["how"] = "npm"
    if known:
        card["id"] = known["id"]
    return card


def personal_path():
    return PERSONAL_FILE if file_exists(PERSONAL_FILE) else PERSONAL_FALLBACK


def load_personal(path):
    """Read data synced by tools/mona_gives_sync.py. Missing parts stay None."""
    try:
        with open(path) as handle:
            data = json.loads(handle.read())
    except (OSError, ValueError):
        return {"dependencies": None, "sponsoring": None, "confirmed": []}
    if not isinstance(data, dict):
        data = {}

    def cards(key):
        items = data.get(key)
        if not isinstance(items, list):
            return None
        out = []
        for item in items[:60]:
            card = clean_card(item, True)
            if card is not None:
                out.append(card)
        return out

    confirmed = data.get("confirmed")
    confirmed = [login for login in confirmed if heartlink.valid_login(login)] if isinstance(confirmed, list) else []
    return {"dependencies": cards("dependencies"), "sponsoring": cards("sponsoring"), "confirmed": confirmed[:20]}


def setting(key):
    return str(getattr(secrets, key, "") or "").strip()


def own_login():
    login = setting("GITHUB_USERNAME").lstrip("@")
    return login if heartlink.valid_login(login) else ""


def load_met(path):
    """People whose hearts you caught, oldest first, for the laptop follow tool."""
    try:
        with open(path) as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    met = data.get("met") if isinstance(data, dict) else None
    return [login for login in met if heartlink.valid_login(login)][-MET_LIMIT:] if isinstance(met, list) else []


def scan_source():
    """The public GitHub user, org or owner/repo the badge may scan, or ""."""
    for key in ("MONA_GIVES_SOURCE", "GITHUB_USERNAME"):
        value = setting(key)
        if value and depscan.parse_source(value):
            return value
    return ""


def load_scan(source):
    """Cached public scan for ``source``, or None if missing or for someone else."""
    if not source:
        return None
    try:
        with open(SCAN_FILE) as handle:
            data = json.loads(handle.read())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or str(data.get("source", "")).lower() != source.lower():
        return None
    items = data.get("dependencies")
    cards = []
    for item in items[:depscan.MAX_CARDS] if isinstance(items, list) else []:
        card = clean_card(item, False)
        if card is not None:
            cards.append(card)
    repos = [r for r in data.get("repos", []) if isinstance(r, str)][:depscan.MAX_REPOS] if isinstance(data.get("repos"), list) else []
    packages = data.get("packages") if isinstance(data.get("packages"), int) else 0
    return {"source": source, "repos": repos, "packages": packages, "dependencies": cards}


# ------------------------------------------------------------------ radio ---

class Radio:
    """Bluetooth badge-to-badge link, with HeartLink on top."""

    def __init__(self):
        self.link = None
        self.proximity = None
        self.error = None
        if badgelink is not None and not hasattr(badgelink, "NEAR_RSSI"):
            # The simulator ships a stub Link that never pairs.
            self.error = "simulator"
        elif badgelink is not None:
            try:
                self.link = badgelink.Link(GAME)
                self.proximity = badgelink.Proximity(self.link)
            except Exception as error:
                self.link = None
                self.error = str(error)
        self.was_linked = False
        self.exchange = None
        self.partner_name = ""
        self.done_at = None
        self.seen = []
        self.events = []

    @property
    def available(self):
        return self.link is not None

    def update(self, now, listening, outgoing):
        if self.link is None:
            return
        link = self.link
        link.pump()
        linked = link.linked
        if linked and not self.was_linked:
            partner = link.partner
            if listening and partner is not None:
                self.partner_name = heartlink.clean_text(getattr(partner, "name", ""), 32) or "a friend"
                peer = partner.id
                if not isinstance(peer, bytes):
                    peer = str(peer).encode()
                self.exchange = heartlink.Exchange(outgoing, now, random.getrandbits(8), peer, self.seen)
                self.done_at = None
            else:
                link.leave()
                linked = False
        elif self.was_linked and not linked:
            if self.exchange is not None:
                self.finish(False)
            self.proximity.clear()
        self.was_linked = linked

        if linked and self.exchange is not None:
            exchange = self.exchange
            for message in link.receive():
                exchange.receive(message, link.send, now)
            exchange.pump(link.send, now, link.capacity())
            if exchange.done and self.done_at is None:
                self.done_at = now
            if (self.done_at is not None and now - self.done_at >= LINGER_MS) or exchange.expired(now):
                self.finish(True, now)
        elif listening and not linked:
            self.proximity.update(now)
        link.update()

    def finish(self, leave, now=0):
        exchange = self.exchange
        self.exchange = None
        self.done_at = None
        if exchange.outgoing is not None:
            self.events.append(("sent" if exchange.acked else "failed", self.partner_name, None))
        if exchange.incoming is not None:
            self.events.append(("caught", self.partner_name, exchange.incoming))
        if leave and self.link.linked:
            partner = self.link.partner
            if partner is not None:
                self.proximity.rest(partner.id, now)
            self.link.leave()
            self.was_linked = False

    def status(self, now):
        if self.link is None:
            return "unavailable", 0.0
        if self.exchange is not None:
            return "passing", 1.0
        peer = self.proximity.syncing()
        if peer is not None:
            return "syncing", self.proximity.progress(now)
        if self.proximity.cooling(now) is not None:
            return "cooling", 0.0
        return "seeking", 0.0

    def lights(self, now):
        if self.proximity is None:
            return None
        return self.proximity.lights(now)

    def take_events(self):
        events = self.events
        self.events = []
        return events

    def close(self):
        if self.link is not None:
            try:
                self.link.close()
            except Exception:
                pass


# -------------------------------------------------------------------- app ---

WELCOME = "welcome"
ATTRACT = "attract"
DISCOVER = "discover"
INFO = "info"
CARD = "card"
QR = "qr"
PASS = "pass"
PASSED = "passed"
FALLBACK = "fallback"
CATCH = "catch"
FOLLOW = "follow"
COLLECTION = "collection"
CELEBRATE = "celebrate"
SCAN = "scan"

LISTENING = (WELCOME, ATTRACT, DISCOVER, CARD, COLLECTION, PASS)

MENU_ITEMS = (
    ("deps", "My Dependencies", "Maintainers behind code you use"),
    ("new", "Discover Someone New", "Curated, verified Sponsors listings"),
    ("sponsors", "My Sponsors", "People you already support"),
)

SLOGANS = ("PASS THE HEART", "DISCOVER. SPONSOR. PASS IT ON.", "GITHUB GIVES")
STEPS = ("Find a maintainer", "Scan to sponsor", "Pass to a badge")


class App:
    def __init__(self):
        self.data = {"found": {}, "cards": {}, "passed": 0, "caught": 0, "longest": 1, "celebrated": []}
        State.load(STATE_KEY, self.data)
        for key, default in (("found", {}), ("cards", {}), ("celebrated", [])):
            if not isinstance(self.data.get(key), type(default)):
                self.data[key] = default
        for key in ("passed", "caught", "longest"):
            if not isinstance(self.data.get(key), int):
                self.data[key] = 0 if key != "longest" else 1
        self.radio = Radio()
        self.particles = Particles()
        self.personal = load_personal(personal_path())
        self.screen = WELCOME
        self.at = badge.ticks
        self.idle_at = badge.ticks
        self.menu = 1
        self.cards = []
        self.index = 0
        self.source = "new"
        self.card_back = WELCOME
        self.seek_until = 0
        self.info = None
        self.pass_card = None
        self.met = load_met(MET_FILE)
        self.pass_badges = 1
        self.pass_packet = None
        self.pass_result = None
        self.pending_catch = None
        self.catch = None
        self.collection_cursor = 0
        self.celebrations = []
        self.fallback_reason = ""
        self.return_to = WELCOME
        self.source_name = scan_source()
        self.scan = load_scan(self.source_name)
        self.scanner = None
        self.scan_steps = None
        self.scan_error = None
        self.queue_celebrations()
        if self.celebrations:
            self.go(CELEBRATE)

    # ---- state ----
    def save(self):
        State.save(STATE_KEY, self.data)

    def refresh_personal(self):
        self.personal = load_personal(personal_path())
        self.queue_celebrations()

    def queue_celebrations(self):
        done = self.data["celebrated"]
        self.celebrations = [login for login in self.personal["confirmed"] if login.lower() not in done]

    def discover(self, card, via, badges=1):
        login = card["login"]
        key = login.lower()
        found = self.data["found"]
        entry = found.get(key)
        changed = False
        if entry is None:
            if len(found) >= FOUND_LIMIT:
                return
            entry = {"l": login, "v": via, "b": badges}
            found[key] = entry
            changed = True
        elif badges > entry.get("b", 1):
            entry["b"] = badges
            changed = True
        if key not in CURATED_BY_LOGIN and key not in self.data["cards"]:
            self.data["cards"][key] = [card.get("name", login), card.get("project", ""), card.get("blurb", "")]
            changed = True
        if badges > self.data["longest"]:
            self.data["longest"] = badges
            changed = True
        if changed:
            self.save()

    def card_for(self, key):
        if key in CURATED_BY_LOGIN:
            return dict(CURATED_BY_LOGIN[key])
        entry = self.data["found"].get(key, {})
        extra = self.data["cards"].get(key)
        login = entry.get("l", key)
        if extra and len(extra) == 3:
            return {"login": login, "name": extra[0], "project": extra[1], "blurb": extra[2], "verified": False}
        return {"login": login, "name": login, "project": "", "blurb": "", "verified": False}

    def curated_order(self):
        found = self.data["found"]
        fresh = [curated_card(e) for e in CURATED if e[1].lower() not in found]
        seen = [curated_card(e) for e in CURATED if e[1].lower() in found]
        for group in (fresh, seen):
            for i in range(len(group) - 1, 0, -1):
                j = random.randint(0, i)
                group[i], group[j] = group[j], group[i]
        return fresh + seen

    # ---- navigation ----
    def go(self, screen_name):
        self.screen = screen_name
        self.at = badge.ticks

    def open_collection(self):
        self.return_to = self.screen if self.screen in (WELCOME, DISCOVER, CARD) else WELCOME
        self.collection_cursor = 0
        self.go(COLLECTION)

    def open_cards(self, cards, source, index=0):
        self.card_back = WELCOME if self.screen == WELCOME else DISCOVER
        self.cards = cards
        self.source = source
        self.index = index
        self.go(CARD)
        self.mark_current()

    def mark_current(self):
        card = self.current
        if card is not None:
            via = {"new": "c", "deps": "d", "public": "d", "sponsors": "s", "caught": "h", "collection": card.get("via_code", "c")}.get(self.source, "c")
            self.discover(card, via, card.get("badges", 1))

    @property
    def current(self):
        if not self.cards:
            return None
        return self.cards[self.index % len(self.cards)]

    def choose_menu(self):
        kind = MENU_ITEMS[self.menu][0]
        if kind == "new":
            self.open_cards(self.curated_order(), "new")
            return
        self.refresh_personal()
        key = "dependencies" if kind == "deps" else "sponsoring"
        cards = self.personal[key]
        if cards:
            self.open_cards(cards, kind)
            return
        reason = "none" if cards is not None else "nosync"
        if kind == "deps" and cards is None:
            reason = self.public_deps()
            if reason is None:
                return
        self.show_info(kind, reason)

    def show_info(self, kind, reason):
        self.info = (kind, reason)
        self.go(INFO)

    def public_deps(self, rescan=False):
        """Open, or start scanning for, public dependency maintainers.
        Returns an info reason when there is nothing to show."""
        self.source_name = scan_source()
        if not self.source_name:
            return "setup"
        if not rescan:
            self.scan = self.scan or load_scan(self.source_name)
            if self.scan is not None and self.scan["source"].lower() == self.source_name.lower():
                if self.scan["dependencies"]:
                    self.open_cards(self.scan["dependencies"], "public")
                    return None
                return "public-none"
        if fetch is None or wifi is None:
            return "nonet"
        if not setting("WIFI_SSID"):
            return "wifi"
        self.start_scan()
        return None

    def start_scan(self):
        self.stop_scan()

        def start(url, path, headers):
            return fetch.url(url, headers=headers).to(path)

        try:
            os.mkdir(STATE_DIR)
        except OSError:
            pass
        self.scanner = depscan.Scanner(self.source_name, start, wifi.connect, lambda: badge.ticks,
                                       CURATED_BY_LOGIN, STATE_DIR, setting("GITHUB_TOKEN"))
        self.scan_steps = self.scanner.steps()
        self.scan_error = None
        self.go(SCAN)

    def stop_scan(self):
        if self.scan_steps is not None:
            try:
                self.scan_steps.close()
            except Exception:
                pass
        self.scan_steps = None

    def finish_scan(self):
        result = self.scanner.result()
        self.scan_steps = None
        try:
            with open(SCAN_FILE, "w") as handle:
                handle.write(json.dumps(result))
        except OSError:
            pass
        self.scan = load_scan(self.source_name) or {
            "source": self.source_name, "repos": result["repos"], "packages": result["packages"],
            "dependencies": [c for c in (clean_card(item, False) for item in result["dependencies"]) if c]}
        if self.scan["dependencies"]:
            self.particles.burst(W / 2, 110, 16)
            self.open_cards(self.scan["dependencies"], "public")
        else:
            self.show_info("deps", "public-none")

    def start_pass(self, card):
        badges = max(1, card.get("badges", 1))
        self.pass_card = card
        self.pass_badges = badges
        self.pass_packet = heartlink.encode_heart(card, badges, own_login() or None)
        self.pass_result = None
        self.go(PASS)
        self.seek_until = self.at + TOSS_MS + SEEK_MS

    def remember_met(self, login):
        key = login.lower()
        self.met = [m for m in self.met if m.lower() != key] + [login]
        self.met = self.met[-MET_LIMIT:]
        try:
            try:
                os.mkdir(STATE_DIR)
            except OSError:
                pass
            with open(MET_FILE, "w") as handle:
                json.dump({"version": 1, "met": self.met}, handle)
        except OSError:
            pass

    def start_catch(self, payload, partner):
        card, badges = payload
        card = dict(card)
        sender = card.pop("sender", None)
        badges = min(9999, badges + 1)
        known = CURATED_BY_LOGIN.get(card["login"].lower())
        if known:
            merged = dict(known)
        else:
            merged = dict(card)
            merged["verified"] = False
        merged["badges"] = badges
        merged["from"] = partner
        me = own_login()
        if sender and sender.lower() != me.lower():
            merged["from_login"] = sender
            merged["from"] = "@" + sender
            self.remember_met(sender)
        self.data["caught"] += 1
        self.save()
        self.catch = merged
        self.particles.items = []
        self.go(CATCH)

    # ---- frame ----
    def update(self):
        now = badge.ticks
        dt = min(badge.ticks_delta, 100) / 1000
        if badge.pressed():
            self.idle_at = now

        listening = self.screen in LISTENING
        if self.screen == PASS and now - self.at < TOSS_MS:
            listening = False
        outgoing = self.pass_packet if self.screen == PASS else None
        self.radio.update(now, listening, outgoing)
        for kind, partner, payload in self.radio.take_events():
            self.handle_event(kind, partner, payload)

        handler = getattr(self, "frame_" + self.screen)
        handler(now)
        self.particles.update(dt)
        self.draw(now)
        self.lights(now)

    def handle_event(self, kind, partner, payload):
        if kind == "sent" and self.screen == PASS:
            self.data["passed"] += 1
            self.pass_result = partner
            reached = self.pass_badges + 1
            if reached > self.data["longest"]:
                self.data["longest"] = reached
            self.save()
            self.particles.burst(W - 40, 120, 18)
            self.go(PASSED)
        elif kind == "failed" and self.screen == PASS:
            self.fallback_reason = "The heart didn't land. Try again, or share it by QR."
            self.go(FALLBACK)
        elif kind == "caught":
            if self.screen in (PASS, PASSED):
                self.pending_catch = (payload, partner)
            else:
                self.start_catch(payload, partner)

    def lights(self, now):
        if self.screen == PASS:
            lights = self.radio.lights(now)
            if lights:
                badge.caselights(*lights)
            else:
                badge.caselights(0.25 + 0.15 * wave(1200))
        elif self.screen in (CATCH, PASSED, CELEBRATE):
            badge.caselights(0.2 + 0.3 * abs(wave(500)))
        else:
            badge.caselights(0)

    # ---- per-screen input ----
    def frame_welcome(self, now):
        if badge.pressed(BUTTON_SELECT):
            self.open_cards(self.curated_order(), "new")
        elif badge.pressed(BUTTON_UP):
            self.go(DISCOVER)
        elif badge.pressed(BUTTON_MENU):
            self.open_collection()
        elif badge.pressed(BUTTON_BACK):
            reset()
        elif now - self.idle_at > ATTRACT_MS:
            self.go(ATTRACT)

    def frame_attract(self, now):
        if badge.pressed():
            self.idle_at = now
            self.go(WELCOME)

    def frame_discover(self, now):
        if badge.pressed(BUTTON_UP):
            self.menu = (self.menu - 1) % len(MENU_ITEMS)
        elif badge.pressed(BUTTON_DOWN):
            self.menu = (self.menu + 1) % len(MENU_ITEMS)
        elif badge.pressed(BUTTON_RIGHT) and self.can_rescan():
            self.rescan()
        elif badge.pressed(BUTTON_SELECT) or badge.pressed(BUTTON_RIGHT):
            self.choose_menu()
        elif badge.pressed(BUTTON_MENU):
            self.open_collection()
        elif badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_LEFT):
            self.go(WELCOME)
        elif now - self.idle_at > ATTRACT_MS * 2:
            self.go(ATTRACT)

    def can_rescan(self):
        """RIGHT rescans on the My Dependencies row once a public scan is cached."""
        return (MENU_ITEMS[self.menu][0] == "deps" and self.personal["dependencies"] is None
                and self.scan is not None)

    def rescan(self):
        reason = self.public_deps(rescan=True)
        if reason is not None:
            self.show_info("deps", reason)

    def frame_info(self, now):
        if badge.pressed(BUTTON_SELECT):
            self.open_cards(self.curated_order(), "new")
        elif badge.pressed(BUTTON_RIGHT) and self.info[1] == "public-none":
            self.rescan()
        elif badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_LEFT):
            self.go(DISCOVER)

    def frame_scan(self, now):
        if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_LEFT):
            self.stop_scan()
            self.go(DISCOVER)
            return
        if self.scan_error:
            if badge.pressed(BUTTON_SELECT):
                self.open_cards(self.curated_order(), "new")
            elif badge.pressed(BUTTON_RIGHT):
                self.start_scan()
            return
        if self.scan_steps is None:
            return
        try:
            next(self.scan_steps)
        except StopIteration:
            self.finish_scan()
        except depscan.ScanError as error:
            self.scan_steps = None
            self.scan_error = heartlink.clean_text(str(error), 90) or "Scan failed"
        except (OSError, ValueError, KeyError, MemoryError) as error:
            self.scan_steps = None
            self.scan_error = heartlink.clean_text("Scan failed: %s" % error, 90)

    def frame_card(self, now):
        count = len(self.cards)
        if badge.pressed(BUTTON_DOWN) and count > 1:
            self.index = (self.index + 1) % count
            self.mark_current()
        elif badge.pressed(BUTTON_UP) and count > 1:
            self.index = (self.index - 1) % count
            self.mark_current()
        elif badge.pressed(BUTTON_DOWN) and self.follow_login():
            self.go(FOLLOW)
        elif badge.pressed(BUTTON_SELECT):
            self.go(QR)
        elif badge.pressed(BUTTON_RIGHT):
            self.start_pass(self.current)
        elif badge.pressed(BUTTON_MENU):
            self.open_collection()
        elif badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_LEFT):
            if self.source == "collection":
                self.go(COLLECTION)
            elif self.source == "caught" or self.card_back == WELCOME:
                self.go(WELCOME)
            else:
                self.go(DISCOVER)

    def follow_login(self):
        card = self.current
        if self.source != "caught" or card is None:
            return ""
        login = card.get("from_login") or ""
        return login if heartlink.valid_login(login) else ""

    def frame_follow(self, now):
        if (badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_SELECT)
                or badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN)):
            self.go(CARD)

    def frame_qr(self, now):
        if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_SELECT):
            self.go(CARD)
        elif badge.pressed(BUTTON_RIGHT):
            self.start_pass(self.current)

    def frame_pass(self, now):
        if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_LEFT):
            self.pass_packet = None
            self.go(CARD)
            return
        if now - self.at < TOSS_MS:
            return
        if not self.radio.available:
            if self.radio.error == "simulator":
                self.fallback_reason = "The simulator can't pair badges, so share it by QR."
            else:
                self.fallback_reason = "Bluetooth isn't available here, so share it by QR."
            self.go(FALLBACK)
        elif badge.pressed(BUTTON_SELECT):
            self.fallback_reason = "Sharing by QR instead. Passing is always free."
            self.go(FALLBACK)
        elif self.radio.status(now)[0] in ("syncing", "passing"):
            # someone is in range: keep going rather than giving up mid-handshake
            self.seek_until = max(self.seek_until, now + SEEK_GRACE_MS)
        elif now > self.seek_until and self.radio.exchange is None:
            self.fallback_reason = "No badge caught the heart this time."
            self.go(FALLBACK)

    def frame_passed(self, now):
        if now - self.at > PASSED_MS or badge.pressed(BUTTON_SELECT) or badge.pressed(BUTTON_BACK):
            self.pass_packet = None
            if self.pending_catch is not None:
                payload, partner = self.pending_catch
                self.pending_catch = None
                self.start_catch(payload, partner)
            else:
                self.go(CARD)
        elif int((now - self.at) / 400) != int((now - self.at - badge.ticks_delta) / 400):
            self.particles.burst(random.randint(40, W - 40), random.randint(40, 120), 6, 80, 4)

    def frame_fallback(self, now):
        if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_SELECT):
            self.pass_packet = None
            self.go(CARD)
        elif badge.pressed(BUTTON_RIGHT):
            self.start_pass(self.pass_card)

    def frame_catch(self, now):
        age = now - self.at
        if age >= 800 and age - badge.ticks_delta < 800:
            self.particles.burst(W / 2, 128, 22, 150, 6)
        if age > CATCH_MS or (age > 300 and badge.pressed(BUTTON_SELECT)):
            card = self.catch
            self.catch = None
            self.open_cards([card], "caught")

    def frame_collection(self, now):
        keys = self.collection_keys()
        count = len(keys)
        if count:
            if badge.pressed(BUTTON_RIGHT):
                self.collection_cursor = (self.collection_cursor + 1) % count
            elif badge.pressed(BUTTON_LEFT):
                self.collection_cursor = (self.collection_cursor - 1) % count
            elif badge.pressed(BUTTON_DOWN):
                self.collection_cursor = min(count - 1, self.collection_cursor + 10)
            elif badge.pressed(BUTTON_UP):
                self.collection_cursor = max(0, self.collection_cursor - 10)
            elif badge.pressed(BUTTON_SELECT):
                cards = []
                for key in keys:
                    card = self.card_for(key)
                    entry = self.data["found"][key]
                    card["badges"] = entry.get("b", 1)
                    card["via_code"] = entry.get("v", "c")
                    cards.append(card)
                if self.return_to == CARD:
                    self.return_to = DISCOVER
                self.open_cards(cards, "collection", self.collection_cursor)
                return
        if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_MENU):
            self.go(self.return_to)

    def frame_celebrate(self, now):
        if int(now / 120) != int((now - badge.ticks_delta) / 120):
            self.particles.rain(2)
        if (now - self.at > 600 and (badge.pressed(BUTTON_SELECT) or badge.pressed(BUTTON_BACK))) or now - self.at > CELEBRATE_MS:
            if self.celebrations:
                login = self.celebrations.pop(0)
                self.data["celebrated"].append(login.lower())
                self.data["celebrated"] = self.data["celebrated"][-50:]
                self.save()
            if self.celebrations:
                self.go(CELEBRATE)
            else:
                self.particles.items = []
                self.go(WELCOME)

    def collection_keys(self):
        return sorted(self.data["found"].keys())

    # ---- drawing ----
    def draw(self, now):
        screen.fill_rule = image.EVEN_ODD
        screen.pen = BG
        screen.clear()
        getattr(self, "draw_" + self.screen)(now)
        self.particles.draw()
        if self.screen == CELEBRATE:
            screen.pen = color.rgb(13, 17, 23, 210)
            screen.rectangle(0, 8, W, 32)
            centred("You helped sustain open source!", 14, 19, GREEN)

    def draw_welcome(self, now):
        bob = wave(1600) * 3
        pulse = 1 + 0.12 * max(0.0, wave(900))
        mx = 14
        screen.pen = color.rgb(63, 185, 80, 18)
        screen.shape(shape.circle(mx + 56, 100, 62 + 4 * wave(1800)))
        headline("MONA GIVES", 14, FG)
        draw_mona(mx, 50 + bob, 4)
        draw_heart(mx + 58, 130 + bob, 15 * pulse, GREEN, glow=True)
        lit = int(now / 900) % 3
        for step, text in enumerate(STEPS):
            y = 58 + step * 32
            screen.pen = GREEN_BTN if step == lit else RAISED
            screen.shape(shape.circle(150, y + 10, 11))
            centred(str(step + 1), y + 2, 14, WHITE if step == lit else MUTED, None, 139, 22)
            write(fit(text, W - 176, 15), 168, y + 1, 15, FG if step == lit else MUTED)
        centred("Good code deserves good people.", 158, 16, FG)
        panel(W / 2 - 74, 184, 148, 30, GREEN_BTN, GREEN, 8)
        centred("Start Giving", 190, 16, WHITE)
        count = len(self.data["found"])
        if count:
            draw_heart(16, 20, 6, GREEN, shine=False)
            write("%d found" % count, 26, 13, 13, MUTED)
        footer("SELECT start   UP more ways   MENU collection")

    def draw_attract(self, now):
        age = now - self.at
        loop = ATTRACT_SHOW_MS + ATTRACT_QR_MS
        if age % loop >= ATTRACT_SHOW_MS:
            self.draw_attract_qr(int(age / loop))
            return
        cycle = 1500
        t = (now % (cycle * 2)) / cycle
        rightward = t < 1
        p = t if rightward else t - 1
        left_x, right_x = 64, W - 64
        start, end = (left_x, right_x) if rightward else (right_x, left_x)
        hx = start + (end - start) * p
        hy = 168 - math.sin(p * math.pi) * 104
        left_dancing = (not rightward and p > 0.85) or (rightward and p < 0.12)
        right_dancing = (rightward and p > 0.85) or (not rightward and p < 0.12)
        draw_mona(left_x - 42, 140, 3, dancing=left_dancing)
        draw_mona(right_x - 42, 140, 3, dancing=right_dancing, flip=True)
        for trail in range(1, 5):
            q = p - trail * 0.04
            if q > 0:
                tx = start + (end - start) * q
                ty = 168 - math.sin(q * math.pi) * 104
                draw_heart(tx, ty, 8 - trail, color.rgb(63, 185, 80, 160 - trail * 35), shine=False)
        draw_heart(hx, hy, 12 + 2 * wave(400), GREEN, glow=True)
        slogan = SLOGANS[int((age % loop) / 2600) % len(SLOGANS)]
        headline(slogan, 16, FG)
        centred("Mona Gives  -  press any button", H - 18, 12, MUTED)

    def draw_attract_qr(self, turn):
        card = curated_card(CURATED[turn % len(CURATED)])
        login = card["login"]
        centred("Scan to meet a maintainer", 8, 16, FG)
        draw_qr(heartlink.sponsors_url(login, CAMPAIGN), 10, 32, 182)
        col_x = 200
        col_w = W - col_x - 8
        draw_avatar(login, col_x + (col_w - 48) / 2, 36, 48, PINK)
        centred(fit("@" + login, col_w, 14), 92, 14, FG, None, col_x, col_w)
        paragraph(card.get("project") or "", col_x, 112, col_w, 34, 12, BLUE)
        paragraph("Opens their GitHub Sponsors page.", col_x, 150, col_w, 40, 11, MUTED)
        footer("Mona Gives  -  press any button")

    def draw_discover(self, now):
        centred("Discover a maintainer", 10, 20, FG)
        top = 42
        for index, (kind, label, sub) in enumerate(MENU_ITEMS):
            y = top + index * 58
            selected = index == self.menu
            panel(12, y, W - 24, 50, RAISED if selected else PANEL, GREEN if selected else BORDER, 8, 2 if selected else 1)
            cx, cy = 40, y + 25
            if kind == "deps":
                screen.pen = BLUE
                screen.shape(shape.rounded_rectangle(cx - 11, cy - 11, 22, 22, 4))
                screen.pen = PANEL
                screen.rectangle(cx - 11, cy - 3, 22, 2)
                screen.rectangle(cx - 1, cy - 11, 2, 8)
            elif kind == "new":
                screen.pen = GREEN
                screen.shape(shape.star(cx, cy, 5, 6, 13))
            else:
                draw_heart(cx, cy, 11, PINK)
            sub_text = sub
            if kind == "sponsors":
                cards = self.personal["sponsoring"]
                sub_text = "Needs a sync from your laptop" if cards is None else "%d synced from GitHub" % len(cards)
            elif kind == "deps":
                cards = self.personal["dependencies"]
                if cards is not None:
                    sub_text = "%d synced from GitHub" % len(cards)
                elif self.scan is not None:
                    sub_text = "%d in @%s's public repos" % (len(self.scan["dependencies"]), self.scan["source"])
                elif self.source_name:
                    sub_text = "Scan @%s's public repos" % self.source_name
                else:
                    sub_text = "Add your GitHub name in Settings"
            write(label, 64, y + 7, 16, FG)
            write(fit(sub_text, W - 90, 12), 64, y + 28, 12, MUTED)
        footer("UP/DOWN  SELECT open  RIGHT rescan  BACK" if self.can_rescan() else "UP/DOWN choose   SELECT open   BACK home")

    INFO_TEXT = {
        ("deps", "setup"): ("Scan your public repos",
                            "Add your GitHub username or org in Settings and Mona reads the public "
                            "dependency graph, no sign-in needed. For private repos, run "
                            "tools/mona_gives_sync.py on your laptop."),
        ("deps", "wifi"): ("Wi-Fi needed",
                           "Add Wi-Fi details in Settings so Mona can read your public repos. "
                           "Or sync from your laptop with tools/mona_gives_sync.py."),
        ("deps", "nonet"): ("No network here",
                            "This firmware can't reach GitHub. Sync from your laptop with "
                            "tools/mona_gives_sync.py instead."),
        ("deps", "public-none"): ("None found yet",
                                  "Mona read the public dependency graphs but found no maintainers she "
                                  "can confirm are sponsorable. Private repos need a laptop sync."),
        ("deps", "nosync"): ("No synced dependencies yet",
                             "Run tools/mona_gives_sync.py on your laptop to load your real "
                             "dependencies. Until then, try a curated maintainer."),
        ("deps", "none"): ("No sponsorable dependencies",
                           "Your dependency graph had no maintainers with a GitHub Sponsors listing. "
                           "Try a curated maintainer instead."),
        ("sponsors", "nosync"): ("No synced sponsorships yet",
                                 "The badge can't sign in to GitHub. Run tools/mona_gives_sync.py on your "
                                 "laptop to load your real sponsorships. Until then, try a curated maintainer."),
        ("sponsors", "none"): ("No public sponsorships",
                               "Your sync found no public sponsorships. Private ones are only shown "
                               "if you opt in. Try a curated maintainer instead."),
    }

    def draw_info(self, now):
        kind, reason = self.info
        title, body = self.INFO_TEXT.get((kind, reason), self.INFO_TEXT[(kind, "nosync")])
        draw_mona(20, 24, 3)
        write(fit(title, W - 120), 112, 34, 17, FG)
        paragraph(body, 112, 62, W - 124, 120, 14, MUTED)
        panel(W / 2 - 92, 184, 184, 28, GREEN_BTN, GREEN, 8)
        centred("SELECT  Discover Someone New", 190, 13, WHITE)
        footer("RIGHT scan again   BACK choose again" if reason == "public-none" else "BACK choose again")

    def draw_scan(self, now):
        bob = wave(1400) * 3
        draw_mona(18, 70 + bob, 3, dancing=self.scan_error is None and (now // 1400) % 2 == 1)
        if self.scan_error:
            write("Scan didn't finish", 112, 40, 18, FG)
            paragraph(self.scan_error, 112, 70, W - 124, 70, 14, MUTED)
            panel(W / 2 - 92, 184, 184, 28, GREEN_BTN, GREEN, 8)
            centred("SELECT  Discover Someone New", 190, 13, WHITE)
            footer("RIGHT try again   BACK choose again")
            return
        # a magnifying glass sweeping over a stack of package boxes
        for row in range(3):
            panel(118 + row * 8, 132 - row * 18, 64, 14, PANEL, BLUE if row == (now // 400) % 3 else BORDER, 3)
        gx = 150 + 40 * wave(1800)
        gy = 112 + 8 * wave(900, 0.3)
        screen.pen = FG
        screen.shape(shape.circle(gx, gy, 15))
        screen.pen = BG
        screen.shape(shape.circle(gx, gy, 12))
        screen.pen = color.rgb(88, 166, 255, 50)
        screen.shape(shape.circle(gx, gy, 12))
        screen.pen = FG
        screen.shape(shape.line(gx + 10, gy + 10, gx + 22, gy + 22, 4))
        write(fit("Reading @%s" % self.source_name, W - 20), 10, 10, 18, FG)
        status = self.scanner.status if self.scanner else ""
        write(fit(status, W - 20, 14), 10, 160, 14, GREEN)
        dots = "." * (1 + (now // 350) % 3)
        write("Public repos only, no sign-in" + dots, 10, 182, 12, MUTED)
        footer("BACK cancel")

    def draw_card(self, now):
        card = self.current
        if card is None:
            return
        follow = self.follow_login()
        labels = {"new": "MEET A MAINTAINER", "deps": "FROM YOUR DEPENDENCIES", "public": "FROM YOUR PUBLIC REPOS",
                  "sponsors": "YOU SPONSOR",
                  "caught": "CAUGHT FROM %s" % card.get("from", "A FRIEND").upper(), "collection": "HEART COLLECTION"}
        write(fit(labels.get(self.source, ""), 200 if follow else 220, 11), 14, 8, 11, GREEN if self.source == "caught" else MUTED)
        if follow:
            hint = "DOWN: follow"
            tw = measure(hint, 11)[0]
            write(hint, W - 14 - tw, 8, 11, BLUE)
        elif len(self.cards) > 1:
            pos = "%d/%d" % (self.index % len(self.cards) + 1, len(self.cards))
            tw = measure(pos, 11)[0]
            write(pos, W - 30 - tw, 8, 11, MUTED)
            screen.pen = MUTED
            screen.shape(shape.custom([vec2(W - 20, 8), vec2(W - 14, 14), vec2(W - 26, 14)]))
            screen.shape(shape.custom([vec2(W - 20, 22), vec2(W - 14, 16), vec2(W - 26, 16)]))
        login = card["login"]
        draw_avatar(login, 18, 34, 60, PINK if card.get("verified") else BORDER)
        write(fit(card.get("name") or login, W - 104, 19), 92, 32, 19, FG)
        write(fit("@" + login, W - 104, 14), 92, 56, 14, MUTED)
        if card.get("verified"):
            panel(92, 78, 146, 20, BG, PINK, 10)
            draw_heart(104, 88, 5, PINK, shine=False)
            write("On GitHub Sponsors", 114, 81, 12, PINK)
        elif card.get("how") == "npm":
            panel(92, 78, 150, 20, BG, PINK, 10)
            draw_heart(104, 88, 5, PINK, shine=False)
            write("Sponsor link in npm", 114, 81, 12, PINK)
        else:
            panel(92, 78, 128, 20, BG, BORDER, 10)
            write("Check on GitHub", 102, 81, 12, MUTED)
        project = card.get("project") or ""
        if project:
            screen.pen = BLUE
            screen.shape(shape.rounded_rectangle(18, 110, 12, 14, 2))
            screen.pen = BG
            screen.rectangle(21, 113, 6, 2)
            write(fit(project, W - 50, 15), 36, 108, 15, BLUE)
        if card.get("blurb"):
            paragraph(card["blurb"], 18, 130, W - 36, 36, 14, FG)
        badges = card.get("badges", 1)
        if badges > 1:
            draw_heart(24, 176, 6, GREEN, shine=False)
            write(fit("This heart has traveled through %d badges!" % badges, W - 50, 13), 36, 169, 13, GREEN)
        elif card.get("via"):
            write(fit("Used by " + card["via"], W - 36, 12), 18, 170, 12, MUTED)
        half = (W - 36) // 2
        panel(12, 192, half, 40, RAISED, PINK, 8)
        draw_heart(30, 206, 7, PINK, shine=False)
        write("Sponsor", 42, 198, 15, FG)
        write("SELECT: show QR", 42, 216, 10, MUTED)
        panel(24 + half, 192, half, 40, GREEN_BTN, GREEN, 8)
        draw_heart(42 + half, 206, 7, LIGHT_GREEN, shine=False)
        write("Pass it on", 54 + half, 198, 15, WHITE)
        write(fit("RIGHT: to a badge", half - 46, 10), 54 + half, 216, 10, LIGHT_GREEN)

    def draw_qr(self, now):
        card = self.current
        login = card["login"]
        url = heartlink.sponsors_url(login, CAMPAIGN)
        centred("Support the people behind the code.", 8, 16, FG)
        draw_qr(url, 10, 32, 182)
        col_x = 200
        col_w = W - col_x - 8
        draw_avatar(login, col_x + (col_w - 48) / 2, 40, 48, PINK)
        centred("@" + login, 98, 14, FG, None, col_x, col_w)
        centred("Scan to open", 124, 12, MUTED, None, col_x, col_w)
        draw_heart(col_x + 10, 147, 6, PINK, shine=False)
        write("GitHub Sponsors", col_x + 19, 140, 13, PINK)
        paragraph("Checkout happens on GitHub. Scanning is free.", col_x, 166, col_w, 40, 11, MUTED)
        footer("BACK card   RIGHT pass it on")

    def draw_follow(self, now):
        login = self.follow_login()
        if not login:
            return
        centred("Follow the person who passed it.", 8, 16, FG)
        draw_qr(heartlink.profile_url(login), 10, 32, 182)
        col_x = 200
        col_w = W - col_x - 8
        draw_avatar(login, col_x + (col_w - 48) / 2, 40, 48, BLUE)
        centred(fit("@" + login, col_w, 14), 98, 14, FG, None, col_x, col_w)
        centred("Scan, then tap", 124, 12, MUTED, None, col_x, col_w)
        centred("Follow", 140, 14, BLUE, None, col_x, col_w)
        paragraph("Also saved, so your laptop can follow later.", col_x, 166, col_w, 40, 11, MUTED)
        footer("BACK card")

    def draw_pass(self, now):
        age = now - self.at
        card = self.pass_card
        if age < TOSS_MS:
            p = ease_out(age / TOSS_MS)
            sx, sy = 92, 150
            ex, ey = W + 30, 110
            hx = sx + (ex - sx) * p
            hy = sy + (ey - sy) * p - math.sin(p * math.pi) * 90
            draw_mona(36, 110, 3, dancing=True, speed=1.6)
            for trail in range(1, 6):
                q = max(0.0, p - trail * 0.05)
                tx = sx + (ex - sx) * q
                ty = sy + (ey - sy) * q - math.sin(q * math.pi) * 90
                draw_heart(tx, ty, 9 - trail, color.rgb(63, 185, 80, 170 - trail * 28), shine=False)
            draw_heart(hx, hy, 12 + 6 * p, GREEN, glow=True)
            headline("PASS THE HEART", 16, FG)
            return
        status, progress = self.radio.status(now)
        pulse = 1 + 0.15 * wave(700)
        draw_mona(20, 120, 3, speed=1.0)
        draw_heart(W - 4, 150, 24 * pulse, GREEN, glow=True)
        headline("PASS THE HEART", 16, FG)
        write(fit("@" + card["login"], 200, 15), 120, 48, 15, GREEN)
        write("Hold badges close", 120, 72, 17, FG)
        paragraph("Your friend needs Mona Gives open too.", 120, 98, W - 150, 44, 13, MUTED)
        if status == "syncing":
            text = "Connecting..."
        elif status == "passing":
            text = "Passing to %s..." % self.radio.partner_name
        elif status == "cooling":
            text = "Pull apart, then try again"
        else:
            text = "Looking for a badge"
            left = max(0, self.seek_until - now)
            progress = min(1.0, left / SEEK_MS)
            write("%ds" % int((left + 999) / 1000), W - 34, 166, 13, GREEN)
        write(fit(text, W - 150, 13), 120, 150, 13, MUTED)
        screen.pen = BORDER
        screen.rectangle(120, 172, W - 160, 6)
        screen.pen = GREEN
        screen.rectangle(120, 172, int((W - 160) * progress), 6)
        footer("SELECT share by QR   BACK cancel")

    def draw_passed(self, now):
        draw_mona(W / 2 - 56, 80 + abs(wave(700)) * -10, 4, dancing=True)
        headline("CAUGHT!", 14, GREEN)
        centred(fit("%s caught your heart." % self.pass_result, W - 20, 16), 42, 16, FG)
        reached = self.pass_badges + 1
        centred("Your heart has traveled through %d badges!" % reached, 188, 14, GREEN)
        centred("Passed: %d   Caught: %d" % (self.data["passed"], self.data["caught"]), 210, 12, MUTED)

    def draw_fallback(self, now):
        card = self.pass_card
        url = heartlink.sponsors_url(card["login"], CAMPAIGN)
        centred("Share by QR", 8, 17, FG)
        draw_qr(url, 10, 32, 182)
        col_x = 200
        col_w = W - col_x - 8
        draw_avatar(card["login"], col_x + (col_w - 40) / 2, 36, 40, PINK)
        centred("@" + card["login"], 82, 14, FG, None, col_x, col_w)
        paragraph(self.fallback_reason, col_x, 104, col_w, 52, 12, MUTED)
        paragraph("A friend can scan this to visit their Sponsors page.", col_x, 156, col_w, 50, 12, FG)
        footer("BACK card   RIGHT try passing again")

    def draw_catch(self, now):
        age = now - self.at
        mx = W / 2 - 56
        if age < 800:
            p = ease_out(age / 800)
            hx = -30 + (W / 2 + 30) * p
            hy = 70 + 58 * p - math.sin(p * math.pi) * 40
            draw_mona(mx, 70, 4)
            draw_heart(hx, hy, 16, GREEN, glow=True)
            headline("A HEART IS COMING!", 14, FG)
        else:
            draw_mona(mx, 70 - abs(wave(600)) * 8, 4, dancing=True)
            draw_heart(W / 2 + 2, 150, 16 * (1 + 0.1 * wave(500)), GREEN, glow=True)
            headline("CAUGHT IT!", 14, GREEN)
            card = self.catch
            centred("from %s" % card.get("from", "a friend"), 182, 15, FG)
            centred("This heart has traveled through %d badges!" % card["badges"], 204, 13, GREEN)

    def draw_collection(self, now):
        keys = self.collection_keys()
        centred("Mona's Heart Collection", 8, 18, FG)
        stats = "%d discovered   %d passed   %d caught   longest chain %d" % (
            len(keys), self.data["passed"], self.data["caught"], self.data["longest"])
        centred(stats, 32, 11, MUTED)
        if not keys:
            draw_mona(W / 2 - 42, 70, 3)
            centred("No hearts yet.", 150, 16, FG)
            centred("Each maintainer you discover adds one.", 172, 13, MUTED)
            footer("BACK home")
            return
        cursor = self.collection_cursor % len(keys)
        first_row = max(0, cursor // 10 - 2)
        for i in range(first_row * 10, min(len(keys), first_row * 10 + 40)):
            row = i // 10 - first_row
            col = i % 10
            x = 26 + col * 30
            y = 64 + row * 30
            entry = self.data["found"][keys[i]]
            pen = GREEN if entry.get("v") != "h" else LIGHT_GREEN
            if i == cursor:
                draw_heart(x, y, 12 + wave(800), pen, glow=True)
            else:
                draw_heart(x, y, 9, pen, shine=False)
        key = keys[cursor]
        entry = self.data["found"][key]
        card = self.card_for(key)
        how = {"c": "Discovered: curated pick", "d": "Discovered: your dependencies",
               "s": "You sponsor them", "h": "Caught from another badge"}.get(entry.get("v"), "")
        badges = entry.get("b", 1)
        if badges > 1:
            how += "  -  chain of %d" % badges
        line = "@" + card["login"] + ("  " + card["project"] if card.get("project") else "")
        centred(line, 182, 14, FG)
        centred(how, 202, 12, MUTED)
        footer("ARROWS move   SELECT open   BACK")

    def draw_celebrate(self, now):
        login = self.celebrations[0] if self.celebrations else ""
        jump = abs(wave(700)) * 22
        draw_mona(W / 2 - 56, 74 - jump, 4, dancing=True, speed=1.4)
        draw_heart(W / 2 + 2, 152 - jump, 14, GREEN, glow=True)
        if login:
            centred("Thank you for sponsoring @%s" % login, 184, 15, FG)
        centred("Confirmed by GitHub Sponsors", 206, 12, MUTED)


app = App()


def update():
    app.update()


def on_exit():
    badge.caselights(0)
    app.radio.close()


run(update)

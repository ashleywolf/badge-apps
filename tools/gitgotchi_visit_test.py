#!/usr/bin/env python3
"""End-to-end test for GitGotchi visits, run on a laptop with no badge.

It loads two full copies of apps/gitgotchi, each with its own fake badge
runtime, and joins them with a fake Bluetooth link that can drop packets and
lose the signal. Then it plays out real visits frame by frame: badges held
close, pets jumping over, waving, button presses on one badge showing up on
the other, saying bye, walking away, and the 5-minute limit. A third copy runs
as the browser simulator, which has no Bluetooth, to check the pretend friend.

Every check lands in a JSON transcript, so a run can be compared with another:
    python3 tools/gitgotchi_visit_test.py --out gitgotchi-visit-report.json

Exits with status 1 if any check fails.
"""

import argparse
import builtins
import copy
import json
import os
import random
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "apps", "gitgotchi")
APP_MODULES = ("pets", "petdata", "ui", "catch", "visit", "party")
FRAME_MS = 33
SYNC_MS = 1200          # how long the fake badges must stay close before they link
REST_MS = 15000         # how long a badge ignores a partner after leaving it
QUEUE_MAX = 6           # messages a fake link holds before send() returns False
BUTTONS = ("BACK", "DOWN", "LEFT", "MENU", "RIGHT", "SELECT", "UP")


# ---------------------------------------------------------------- fake runtime

class Blob:
    """Stands in for images, shapes, fonts and vectors: every call works."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return self

    def __call__(self, *args, **kwargs):
        return self


class Screen(Blob):
    def __init__(self):
        self.width = 160
        self.height = 120
        self.texts = []

    def text(self, message, *args):
        self.texts.append(str(message))

    def measure_text(self, message):
        return len(str(message)) * 6, 8

    def clear(self, *args):
        self.texts = []


class Color:
    @staticmethod
    def rgb(r, g, b, a=255):
        return (r, g, b, a)


class Badge:
    def __init__(self):
        self.ticks = 0
        self.ticks_delta = 0
        self.down = set()
        self.lights = []

    def pressed(self, button):
        return button in self.down

    def held(self, button):
        return button in self.down

    def caselights(self, *values):
        self.lights.append(values)


class Store:
    """The badge's State: each fake badge has its own."""

    def __init__(self):
        self.data = {}

    def make(self):
        data = self.data

        class State:
            @staticmethod
            def load(key, target):
                if key not in data:
                    return False
                target.update(copy.deepcopy(data[key]))
                return True

            @staticmethod
            def save(key, value):
                data[key] = json.loads(json.dumps(value))

        return State


# ---------------------------------------------------------------- fake Bluetooth

class Partner:
    def __init__(self, ident, name):
        self.id = ident
        self.name = name


class Air:
    """The space between two badges: are they close, and do packets get through?"""

    def __init__(self, seed):
        self.links = []
        self.near = False
        self.loss = 0.0
        self.rng = random.Random(seed)
        self.sync_since = None
        self.log = []

    def add(self, link):
        self.links.append(link)

    def listening(self, now):
        return all(link.proximity and now - link.proximity.heard <= 2 * FRAME_MS for link in self.links)

    def tick(self, now):
        a, b = self.links
        if a.linked or b.linked:
            self.sync_since = None
            return
        cooling = a.proximity.cooling(now, b.id) or b.proximity.cooling(now, a.id)
        if self.near and not cooling and self.listening(now):
            if self.sync_since is None:
                self.sync_since = now
            elif now - self.sync_since >= SYNC_MS:
                self.join()
        else:
            self.sync_since = None

    def join(self):
        a, b = self.links
        a.connect(b, central=True)
        b.connect(a, central=False)
        self.sync_since = None
        self.log.append("linked")

    def cut(self):
        for link in self.links:
            link.drop()
        self.log.append("cut")

    def carry(self, message, to):
        if self.rng.random() < self.loss:
            return
        to.inbox.append(bytes(message))


class FakeLink:
    def __init__(self, air, ident, name):
        self.air = air
        self.id = ident
        self.name = name
        self.linked = False
        self.partner = None
        self.peer = None
        self.central = False
        self.inbox = []
        self.queue = []
        self.proximity = None
        self.sent = 0
        self.left = 0
        air.add(self)

    def connect(self, peer, central):
        self.linked = True
        self.peer = peer
        self.partner = Partner(peer.id, peer.name)
        self.central = central
        self.inbox = []
        self.queue = []

    def drop(self):
        self.linked = False
        self.peer = None
        self.partner = None
        self.inbox = []
        self.queue = []

    def pump(self):
        pass

    def update(self):
        if self.linked:
            for message in self.queue:
                self.air.carry(message, self.peer)
        self.queue = []

    def send(self, message):
        if not self.linked or len(self.queue) >= QUEUE_MAX:
            return False
        self.queue.append(bytes(message))
        self.sent += 1
        return True

    def capacity(self):
        return 20

    def receive(self):
        messages = self.inbox
        self.inbox = []
        return messages

    def leave(self):
        self.left += 1
        if self.linked:
            peer = self.peer
            self.drop()
            peer.drop()
            self.air.log.append("left")

    def close(self):
        self.drop()


class FakeProximity:
    def __init__(self, link):
        self.link = link
        link.proximity = self
        self.heard = -10 ** 9
        self.resting = {}

    def update(self, now):
        self.heard = now

    def syncing(self):
        air = self.link.air
        return 1 if air.sync_since is not None and not self.link.linked else None

    def progress(self, now):
        since = self.link.air.sync_since
        return 0.0 if since is None else min(1.0, (now - since) / SYNC_MS)

    def cooling(self, now, partner=None):
        until = [t for p, t in self.resting.items() if partner is None or p == partner]
        return any(now < t for t in until)

    def lights(self, now):
        return (0.4, 0.4, 0.4, 0.4) if self.syncing() else None

    def rest(self, partner, now):
        self.resting[partner] = now + REST_MS

    def clear(self):
        pass


# ---------------------------------------------------------------- one badge

class Gotchi:
    """One running copy of the GitGotchi app with its own fake badge."""

    def __init__(self, name, kind, login, air=None, simulator=False, seed=0):
        self.name = name
        self.badge = Badge()
        self.screen = Screen()
        self.store = Store()
        self.rng_seed = seed
        self.update = None
        self.on_exit = None
        self.texts = []
        self.link = None
        if kind:
            self.store.data["gitgotchi"] = {
                "pet": kind, "hunger": 80.0, "happy": 50.0, "energy": 90.0,
                "age": 5 * 3600.0, "asleep": False, "lights": True, "t": 0,
            }
        link_module = types.ModuleType("badgeware.link")
        if simulator:
            def no_link(game):
                raise AssertionError("the simulator should never open a badge link")
            link_module.Link = no_link
            link_module.Proximity = FakeProximity
        else:
            link_module.NEAR_RSSI = -45
            self.link = FakeLink(air, bytes([ord(name[0])]) * 6, "%s's badge" % name)
            link_module.Link = lambda game, link=self.link: link
            link_module.Proximity = FakeProximity
        badgeware = types.ModuleType("badgeware")
        badgeware.State = self.store.make()
        badgeware.link = link_module
        secrets = types.ModuleType("secrets")
        secrets.GITHUB_USERNAME = login
        self.fakes = {"badgeware": badgeware, "badgeware.link": link_module, "secrets": secrets}
        self.builtins = {
            "badge": self.badge, "screen": self.screen, "color": Color, "image": Blob(),
            "shape": Blob(), "font": Blob(), "vec2": Blob(), "rect": Blob(), "mat3": Blob(),
            "io": Blob(), "is_dir": lambda path: path == "/system/apps/gitgotchi",
            "run": self._run,
        }
        for button in BUTTONS:
            self.builtins["BUTTON_" + button] = button
        self._boot()

    def _run(self, update):
        self.update = update

    def _enter(self):
        for key, value in self.builtins.items():
            setattr(builtins, key, value)
        random.seed(self.rng_seed)

    def _boot(self):
        self._enter()
        saved = {name: sys.modules.get(name) for name in APP_MODULES + tuple(self.fakes)}
        for name in APP_MODULES:
            sys.modules.pop(name, None)
        sys.modules.update(self.fakes)
        chdir = os.chdir
        os.chdir = lambda path: None
        sys.path.insert(0, APP)
        try:
            with open(os.path.join(APP, "__init__.py")) as source:
                code = compile(source.read(), os.path.join(APP, "__init__.py"), "exec")
            self.app = {"__name__": "gitgotchi_" + self.name, "__file__": os.path.join(APP, "__init__.py")}
            exec(code, self.app)
            self.on_exit = self.app.get("on_exit")
        finally:
            os.chdir = chdir
            sys.path.remove(APP)
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
        self.rng_seed = random.random()

    def frame(self, ticks, buttons=()):
        self._enter()
        self.badge.ticks_delta = ticks - self.badge.ticks
        self.badge.ticks = ticks
        self.badge.down = set(buttons)
        self.screen.texts = []
        self.update()
        self.texts = list(self.screen.texts)
        self.rng_seed = random.random()

    def exit(self):
        self._enter()
        self.on_exit()

    # handy views of the app's state
    @property
    def mode(self):
        return self.app["mode"]

    @property
    def party(self):
        return self.app["party"]

    @property
    def pet(self):
        return self.app["pet"]

    def friends(self):
        return self.store.data.get("gitgotchi_friends", {}).get("friends", [])


class World:
    def __init__(self, seed):
        self.air = Air(seed)
        self.ticks = 1000
        self.a = Gotchi("ada", "mona", "ada-codes", self.air, seed=seed + 1)
        self.b = Gotchi("bo", "duck", "@bo-ships", self.air, seed=seed + 2)
        self.seen = {"ada": set(), "bo": set()}

    def run(self, ms, a=(), b=(), until=None):
        """Advance both badges `ms` milliseconds. Buttons are pressed on the first frame."""
        end = self.ticks + ms
        first = True
        while self.ticks < end:
            self.ticks += FRAME_MS
            self.a.frame(self.ticks, a if first else ())
            self.b.frame(self.ticks, b if first else ())
            self.air.tick(self.ticks)
            self.seen["ada"].update(self.a.texts)
            self.seen["bo"].update(self.b.texts)
            first = False
            if until is not None and until(self):
                return True
        return until is None

    def saw(self, who, fragment):
        return any(fragment in text for text in self.seen[who])

    def clear_seen(self):
        self.seen = {"ada": set(), "bo": set()}


# ---------------------------------------------------------------- scenarios

class Report:
    def __init__(self):
        self.scenarios = []
        self.current = None

    def scenario(self, name):
        self.current = {"name": name, "checks": []}
        self.scenarios.append(self.current)

    def check(self, label, ok, detail=None):
        entry = {"check": label, "ok": bool(ok)}
        if detail is not None:
            entry["detail"] = detail
        self.current["checks"].append(entry)
        print("  %s %s%s" % ("PASS" if ok else "FAIL", label, "" if ok else "  (%s)" % (detail,)))

    @property
    def failed(self):
        return [c for s in self.scenarios for c in s["checks"] if not c["ok"]]


def both_visiting(world):
    return world.a.mode == "visit" and world.b.mode == "visit"


def both_together(world):
    return (both_visiting(world) and world.a.party.phase == "together"
            and world.b.party.phase == "together")


def both_home(world):
    return world.a.mode == "home" and world.b.mode == "home"


def meet(world, report, loss=0.0):
    world.air.near = True
    world.air.loss = loss
    linked = world.run(12000, until=both_visiting)
    report.check("badges link and both pets start a visit", linked,
                 {"ada": world.a.mode, "bo": world.b.mode, "air": world.air.log[-3:]})
    together = linked and world.run(6000, until=both_together)
    report.check("guest pets land and both screens reach 'together'", together)
    return together


def scenario_hello(report, seed):
    report.scenario("hold badges close, pets jump over and wave")
    world = World(seed)
    world.run(2000)
    report.check("both pets start on the home screen", both_home(world),
                 {"ada": world.a.mode, "bo": world.b.mode})
    report.check("far apart: no link, no visit", world.air.log == [] and both_home(world))

    world.air.near = True
    world.run(600)
    report.check("a 'Someone's nearby...' toast shows while syncing",
                 world.saw("ada", "Someone's nearby") and world.saw("bo", "Someone's nearby"))
    report.check("case lights flash while syncing", any(len(v) == 4 for v in world.a.badge.lights))

    happy_before = world.a.pet["happy"]
    world.air.near = True
    if not world.run(12000, until=both_visiting):
        report.check("badges link and both pets start a visit", False, world.air.log)
        return
    report.check("badges link and both pets start a visit", True)
    pa, pb = world.a.party, world.b.party
    report.check("Ada's badge hosts Bo's Ducky", pa.host == "mona" and pa.guest == "duck",
                 {"host": pa.host, "guest": pa.guest})
    report.check("Bo's badge hosts Ada's Mona", pb.host == "duck" and pb.guest == "mona",
                 {"host": pb.host, "guest": pb.guest})
    report.check("guests are named by GitHub username", pa.owner == "@bo-ships" and pb.owner == "@ada-codes",
                 {"ada sees": pa.owner, "bo sees": pb.owner})
    report.check("guest starts in the 'arrive' (jumping in) phase", pa.phase == "arrive" and pb.phase == "arrive")
    report.check("a visit makes the pet happier", world.a.pet["happy"] >= happy_before + 15,
                 {"before": happy_before, "after": world.a.pet["happy"]})

    world.run(6000, until=both_together)
    report.check("both reach 'together' after the jump", both_together(world))
    report.check("they wave hello first", pa.activity == "wave" and pb.activity == "wave",
                 {"ada": pa.activity, "bo": pb.activity})
    world.run(2600)
    report.check("'came to visit!' toast names the friend's pet",
                 world.saw("ada", "@bo-ships's Ducky came to visit!")
                 and world.saw("bo", "@ada-codes's Mona came to visit!"))

    friends = world.a.friends()
    report.check("Ada's badge remembers Bo's badge", len(friends) == 1 and friends[0][1] == "duck"
                 and friends[0][2] == "@bo-ships" and friends[0][3] == 1, friends)
    report.check("only the central badge picks surprise activities", pa.leader and not pb.leader)

    # The leader picks something on its own; the other badge plays it too.
    world.clear_seen()
    world.run(9000, until=lambda w: w.a.party.activity not in (None, "wave"))
    world.run(200)
    report.check("leader's surprise activity plays on both badges",
                 pa.activity == pb.activity and pa.activity not in (None, "wave"),
                 {"ada": pa.activity, "bo": pb.activity})
    report.check("both badges start it within 250 ms of each other",
                 abs(pa.activity_at - pb.activity_at) <= 250, pa.activity_at - pb.activity_at)

    # Bo presses buttons; Ada's screen follows.
    for button, activity in (("UP", "dance"), ("SELECT", "high5"), ("DOWN", "snack"), ("LEFT", "wave")):
        world.run(3000, until=lambda w: w.b.party.ready(w.ticks) and w.a.party.ready(w.ticks))
        world.b.party.next_auto = world.ticks + 60000
        world.a.party.next_auto = world.ticks + 60000
        world.run(300, b=(button,))
        report.check("Bo presses %s: both pets %s" % (button, activity),
                     pa.activity == activity and pb.activity == activity,
                     {"ada": pa.activity, "bo": pb.activity})
    # A press made while a move is still playing isn't lost; it plays next.
    world.run(3000, until=lambda w: w.b.party.ready(w.ticks) and w.a.party.ready(w.ticks))
    world.run(300, b=("SELECT",))
    busy = not world.b.party.ready(world.ticks)
    world.run(300, b=("UP",))
    report.check("a press during a move is remembered", busy and world.b.app["party_wish"] == "dance",
                 {"busy": busy, "wish": world.b.app["party_wish"]})
    world.run(4000, until=lambda w: w.b.party.activity == "dance" and w.a.party.activity == "dance")
    report.check("the remembered move plays next on both badges",
                 pa.activity == "dance" and pb.activity == "dance" and world.b.app["party_wish"] is None,
                 {"ada": pa.activity, "bo": pb.activity})
    report.check("visit fun is capped per visit", world.a.app["party_fun"] <= 15, world.a.app["party_fun"])

    # Walking away ends the visit on both badges.
    world.air.near = False
    world.air.cut()
    world.clear_seen()
    world.run(6000, until=both_home)
    report.check("walking away: guests wave bye and jump home", both_home(world),
                 {"ada": world.a.mode, "bo": world.b.mode})
    report.check("a 'Bye, ...' toast shows", world.saw("ada", "Bye, @bo-ships's Ducky")
                 and world.saw("bo", "Bye, @ada-codes's Mona"))
    report.check("only the host's sprite sheet stays loaded",
                 set(world.a.app["pets"]._sheets) <= {"mona"}, list(world.a.app["pets"]._sheets))


def scenario_back(report, seed):
    report.scenario("press BACK to say bye, then a cool-down before the next visit")
    world = World(seed)
    world.run(500)
    if not meet(world, report):
        return
    world.clear_seen()
    world.run(300, a=("BACK",))
    report.check("Ada's pet says bye", world.a.party is not None and world.a.party.phase == "bye")
    report.check("Bo's badge hears the bye", world.b.party is not None and world.b.party.phase == "bye",
                 world.b.party and world.b.party.phase)
    world.run(6000, until=both_home)
    report.check("both back home", both_home(world))
    report.check("Ada's badge left the link", world.a.link.left >= 1 and not world.a.link.linked)
    world.run(5000)
    report.check("still close, but no instant second visit", both_home(world) and world.air.log.count("linked") == 1,
                 world.air.log)
    world.run(REST_MS + 5000, until=both_visiting)
    report.check("after the cool-down they can visit again", both_visiting(world), world.air.log)
    friends = world.b.friends()
    report.check("Bo's badge counts 2 visits from Ada", friends and friends[0][3] == 2, friends)


def scenario_lossy(report, seed):
    report.scenario("noisy room: 35% of packets lost")
    world = World(seed)
    world.run(500)
    if not meet(world, report, loss=0.35):
        return
    pa, pb = world.a.party, world.b.party
    pa.next_auto = pb.next_auto = world.ticks + 10 ** 6
    matched = 0
    for button, activity in (("UP", "dance"), ("SELECT", "high5"), ("DOWN", "snack")):
        world.run(3000, until=lambda w: w.a.party.ready(w.ticks) and w.b.party.ready(w.ticks))
        world.run(300, a=(button,))
        matched += pb.activity == activity
    report.check("button presses still reach the other badge sometimes", matched >= 1, matched)
    report.check("lost packets never crash or end the visit", both_together(world))
    world.air.loss = 0.0
    world.air.cut()
    world.run(6000, until=both_home)
    report.check("both back home after the signal goes", both_home(world))


def scenario_duplicates(report, seed):
    report.scenario("repeated packets are only acted on once")
    world = World(seed)
    world.run(500)
    if not meet(world, report):
        return
    pa, pb = world.a.party, world.b.party
    pa.next_auto = pb.next_auto = world.ticks + 10 ** 6
    world.run(3000, until=lambda w: w.a.party.ready(w.ticks) and w.b.party.ready(w.ticks))
    world.run(100, a=("UP",))
    started = pb.activity_at
    world.run(3000, until=lambda w: w.b.party.ready(w.ticks))
    # replay Ada's last activity packet to Bo three times
    seq = world.a.app["radio"].meeting.seq
    for _ in range(3):
        world.b.link.inbox.append(bytes((ord("A"), seq, 2, 7)))
    world.run(200)
    report.check("replayed activity is ignored", pb.activity_at == started, pb.activity_at - started)
    report.check("hello isn't repeated", world.b.app["friends"][0][3] == 1, world.b.app["friends"])
    # Mismatched hello chunks (same id, different totals) must not crash.
    hello, version = ord("V"), world.b.app["visit"].VERSION
    world.b.link.inbox.append(bytes((hello, version, 9, 5, 6, 0)))
    world.b.link.inbox.append(bytes((hello, version, 9, 0, 2, 0)))
    crashed = None
    try:
        world.run(200)
    except Exception as e:  # noqa: BLE001
        crashed = repr(e)
    report.check("mismatched hello chunks are ignored, no crash",
                 crashed is None and world.b.mode == "visit", crashed or world.b.mode)
    world.air.cut()
    world.run(6000, until=both_home)


def scenario_clash(report, seed):
    report.scenario("both people press at the same moment: the pets still match")
    world = World(seed)
    world.run(500)
    if not meet(world, report):
        return
    pa, pb = world.a.party, world.b.party
    report.check("Ada's badge is the leader", pa.leader and not pb.leader)
    for a_button, b_button, want in (("SELECT", "UP", "high5"), ("DOWN", "LEFT", "snack")):
        pa.next_auto = pb.next_auto = world.ticks + 10 ** 6
        world.run(4000, until=lambda w: w.a.party.ready(w.ticks) and w.b.party.ready(w.ticks))
        world.run(800, a=(a_button,), b=(b_button,))
        report.check("Ada %s + Bo %s at once: both pets do the leader's %s" % (a_button, b_button, want),
                     pa.activity == want and pb.activity == want,
                     {"ada": pa.activity, "bo": pb.activity})
    world.air.cut()
    world.run(6000, until=both_home)


def scenario_cap(report, seed):
    report.scenario("a visit ends by itself after 5 minutes")
    world = World(seed)
    world.run(500)
    if not meet(world, report):
        return
    together_at = world.a.party.together_at
    world.run(4 * 60 * 1000)
    report.check("still visiting after 4 minutes", both_visiting(world))
    world.run(90 * 1000, until=lambda w: w.a.party is None or w.a.party.phase == "bye")
    elapsed = world.ticks - together_at
    report.check("bye starts at about 5 minutes", 5 * 60 * 1000 <= elapsed <= 5 * 60 * 1000 + 1000, elapsed)
    world.run(6000, until=both_home)
    report.check("both back home", both_home(world))


def scenario_not_listening(report, seed):
    report.scenario("busy or sleeping pets don't start visits")
    world = World(seed)
    world.run(500)
    world.b.pet["asleep"] = True
    world.air.near = True
    world.run(5000)
    report.check("a sleeping pet's badge doesn't link", world.air.log == [] and both_home(world), world.air.log)
    world.b.pet["asleep"] = False
    world.b.pet["lights"] = True
    world.b.app["mode"] = "stats"
    world.air.join()  # the firmware links anyway; the busy badge must leave
    world.run(1500)
    report.check("a badge in another screen leaves the link", not world.b.link.linked and world.b.mode == "stats",
                 {"b mode": world.b.mode, "air": world.air.log})
    report.check("the other badge goes back to normal", world.a.mode == "home" and world.a.party is None)


def scenario_exit(report, seed):
    report.scenario("closing the app mid-visit says bye")
    world = World(seed)
    world.run(500)
    if not meet(world, report):
        return
    world.a.exit()
    report.check("closing leaves the link", not world.a.link.linked)
    world.run(6000, until=lambda w: w.b.mode == "home")
    report.check("the friend's badge sends its guest home", world.b.mode == "home")


def scenario_simulator(report, seed):
    report.scenario("browser simulator: UP brings a pretend friend")
    sim = Gotchi("sim", "copilot", "", simulator=True, seed=seed)
    ticks = 1000
    texts = set()

    def step(ms, buttons=()):
        nonlocal ticks
        end = ticks + ms
        first = True
        while ticks < end:
            ticks += FRAME_MS
            sim.frame(ticks, buttons if first else ())
            texts.update(sim.texts)
            first = False

    step(1000)
    report.check("no badge link in the simulator", sim.app["radio"].link is None)
    step(500, ("UP",))
    report.check("syncing toast shows", "Someone's nearby..." in texts)
    step(2000)
    report.check("pretend friend visits", sim.mode == "visit" and sim.party.owner == "Pretend pal")
    report.check("the pretend pet is a different kind", sim.party.guest != "copilot", sim.party and sim.party.guest)
    step(4000)
    report.check("they hang out", sim.party.phase == "together")
    step(9000)
    report.check("the pretend friend plays on its own", sim.party.activity not in (None, "wave"), sim.party.activity)
    step(3000)
    step(300, ("BACK",))
    step(5000)
    report.check("BACK sends the pretend friend home", sim.mode == "home")
    report.check("pretend friends aren't saved", sim.friends() == [])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="gitgotchi-visit-report.json")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    report = Report()
    for scenario in (scenario_hello, scenario_back, scenario_lossy, scenario_duplicates, scenario_clash,
                     scenario_cap, scenario_not_listening, scenario_exit, scenario_simulator):
        print(scenario.__name__)
        scenario(report, args.seed)

    total = sum(len(s["checks"]) for s in report.scenarios)
    result = {"seed": args.seed, "checks": total, "failed": len(report.failed), "scenarios": report.scenarios}
    with open(args.out, "w") as out:
        json.dump(result, out, indent=2)
    print("\n%d/%d checks passed. Transcript: %s" % (total - len(report.failed), total, args.out))
    sys.exit(1 if report.failed else 0)


if __name__ == "__main__":
    main()

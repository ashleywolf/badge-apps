"""PetLink: let two GitGotchi pets visit each other over a badge link.

The protocol runs on top of any message link that can send and receive short
byte strings (the badge uses the firmware's Bluetooth ``badgeware.link``). It
has no badge dependencies, so it also runs on a laptop for tests.

Messages (first byte is the kind):

- ``V version sid index total chunk``: one chunk of a hello. The joined chunks
  are ``kind stage flags login_length login`` plus a CRC-8 of those bytes.
- ``O sid``: "your hello ``sid`` arrived intact".
- ``A seq activity seed``: both pets do ``activity`` now.
- ``B``: "bye", the visit is over.

Each side resends its hello every ``RESEND_MS`` until it is acknowledged. A
visit starts once both hellos have arrived. Activities and bye are sent once,
queued if the link is busy, and ``seq`` stops a repeat from playing twice.
"""

VERSION = 1
RESEND_MS = 700
HELLO_TIMEOUT_MS = 8000
LOGIN_MAX = 39

HELLO = 0x56  # "V"
OK = 0x4F  # "O"
ACT = 0x41  # "A"
BYE = 0x42  # "B"

KINDS = ("mona", "duck", "squirrel", "copilot")
ACTIVITIES = ("wave", "high5", "dance", "snack", "chase")
SICK = 1
SLEEPY = 2


def crc8(data, crc=0):
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def valid_login(login):
    """GitHub usernames: 1-39 letters, digits or single hyphens, no edge hyphens."""
    if not isinstance(login, str) or not 0 < len(login) <= LOGIN_MAX:
        return False
    if login[0] == "-" or login[-1] == "-" or "--" in login:
        return False
    for ch in login:
        if not ("a" <= ch <= "z" or "A" <= ch <= "Z" or "0" <= ch <= "9" or ch == "-"):
            return False
    return True


def encode_hello(kind, stage=0, flags=0, login=""):
    if kind not in KINDS:
        raise ValueError("unknown pet")
    login = login if valid_login(login) else ""
    body = bytes((KINDS.index(kind), max(0, min(2, stage)), flags & 0xFF, len(login))) + login.encode()
    return body + bytes((crc8(body),))


def decode_hello(payload):
    """Return ``{"kind", "stage", "flags", "login"}`` or None if it's damaged."""
    if len(payload) < 5 or crc8(payload[:-1]) != payload[-1]:
        return None
    kind, stage, flags, size = payload[0], payload[1], payload[2], payload[3]
    if kind >= len(KINDS) or stage > 2 or len(payload) != 5 + size:
        return None
    try:
        login = payload[4:4 + size].decode()
    except (UnicodeError, ValueError):
        return None
    if size and not valid_login(login):
        return None
    return {"kind": KINDS[kind], "stage": stage, "flags": flags, "login": login}


def frames(payload, sid, capacity):
    """Split a hello into messages no longer than ``capacity`` bytes."""
    size = max(1, capacity - 5)
    total = (len(payload) + size - 1) // size
    if total > 255:
        raise ValueError("hello too long")
    return [bytes((HELLO, VERSION, sid, i, total)) + payload[i * size:(i + 1) * size]
            for i in range(total)]


class Meeting:
    """One visit between this badge and a partner badge."""

    def __init__(self, hello, now, sid):
        self.hello = hello
        self.sid = sid & 0xFF
        self.started = now
        self.frames = None
        self.next = 0
        self.round_at = now - RESEND_MS
        self.acked = False
        self.friend = None
        self.parts = {}
        self.part_sid = None
        self.part_total = 0
        self.queue = []
        self.seq = 0
        self.last_seq = None
        self.bye = False

    @property
    def ready(self):
        return self.acked and self.friend is not None

    def expired(self, now):
        return not self.ready and now - self.started > HELLO_TIMEOUT_MS

    def pump(self, send, now, capacity=20):
        """Send queued messages and (re)send the hello until it's acknowledged.

        ``send`` returns ``False`` when the link's queue is full.
        """
        while self.queue:
            if send(self.queue[0]) is False:
                return
            self.queue.pop(0)
        if self.acked:
            return
        if self.frames is None:
            self.frames = frames(self.hello, self.sid, max(8, capacity))
        if self.next >= len(self.frames):
            if now - self.round_at < RESEND_MS:
                return
            self.next = 0
        if self.next == 0:
            self.round_at = now
        while self.next < len(self.frames):
            if send(self.frames[self.next]) is False:
                return
            self.next += 1

    def _send(self, send, message):
        if self.queue or send(message) is False:
            self.queue.append(message)

    def act(self, send, activity, seed=0):
        """Ask the partner's pet to do ``activity`` too."""
        self.seq = (self.seq + 1) & 0xFF
        self._send(send, bytes((ACT, self.seq, ACTIVITIES.index(activity), seed & 0xFF)))

    def say_bye(self, send):
        self._send(send, bytes((BYE,)))

    def receive(self, message, send):
        """Handle one message. Returns a list of events:

        ``("hello", friend)``, ``("act", activity, seed)`` or ``("bye",)``.
        """
        if not message:
            return []
        kind = message[0]
        if kind == HELLO and len(message) > 5 and message[1] == VERSION:
            return self._chunk(message, send)
        if kind == OK and len(message) == 2 and message[1] == self.sid:
            self.acked = True
        elif kind == ACT and len(message) == 4 and self.friend is not None:
            seq, activity, seed = message[1], message[2], message[3]
            if seq != self.last_seq and activity < len(ACTIVITIES):
                self.last_seq = seq
                return [("act", ACTIVITIES[activity], seed)]
        elif kind == BYE and not self.bye:
            self.bye = True
            return [("bye",)]
        return []

    def _chunk(self, message, send):
        sid, index, total = message[2], message[3], message[4]
        if not 0 < total or index >= total:
            return []
        if sid != self.part_sid or total != self.part_total:
            self.part_sid = sid
            self.part_total = total
            self.parts = {}
        self.parts[index] = message[5:]
        for i in range(total):
            if i not in self.parts:
                return []
        payload = b"".join(self.parts[i] for i in range(total))
        self.parts = {}
        friend = decode_hello(payload)
        if friend is None:
            return []
        self._send(send, bytes((OK, sid)))
        if self.friend is not None:
            return []
        self.friend = friend
        return [("hello", friend)]

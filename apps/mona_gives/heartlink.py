"""HeartLink: pass a maintainer recommendation from one badge to another.

The protocol runs on top of any message link that can send and receive short
byte strings (the badge uses the firmware's Bluetooth ``badgeware.link``). It
has no badge dependencies, so it also runs on a laptop for tests.

Messages (first byte is the kind):

- ``H sid idx total chunk``: one chunk of a heart. The last byte of the joined
  chunks is a CRC-8 of the JSON payload before it.
- ``K sid crc``: acknowledgment that the heart ``sid``/``crc`` arrived intact.
- ``N version``: "I have no heart to pass you", so the exchange can finish.

A sender repeats its whole heart every ``RESEND_MS`` until it is acknowledged
or ``TIMEOUT_MS`` passes. A receiver acknowledges every copy it gets but only
catches a heart once (``seen`` remembers recent hearts across exchanges).
"""

import json

VERSION = 1
RESEND_MS = 1200
TIMEOUT_MS = 9000
SEEN_LIMIT = 16
MAX_PAYLOAD = 400
LOGIN_MAX = 39
TEXT_LIMITS = {"n": 40, "p": 80, "d": 60}

HEART = 0x48  # "H"
ACK = 0x4B  # "K"
NONE = 0x4E  # "N"


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


def sponsors_url(login, campaign=None):
    if not valid_login(login):
        raise ValueError("invalid GitHub login")
    url = "https://github.com/sponsors/" + login
    if campaign:
        if len(campaign) > 100 or not all(ch.isalpha() or ch.isdigit() or ch in "-_" for ch in campaign):
            raise ValueError("invalid campaign")
        url += "?metadata_campaign=" + campaign
    return url


def profile_url(login):
    if not valid_login(login):
        raise ValueError("invalid GitHub login")
    return "https://github.com/" + login


def clean_text(value, limit):
    if not isinstance(value, str):
        return ""
    out = "".join(ch for ch in value if 32 <= ord(ch) < 127)
    return out.strip()[:limit]


def encode_heart(card, badges, sender=None):
    """Serialise a maintainer card for passing. ``badges`` counts badges so far.
    ``sender`` is the passer's own GitHub login, so the catcher can follow them."""
    if not valid_login(card.get("login")):
        raise ValueError("invalid GitHub login")
    body = {"v": VERSION, "l": card["login"], "b": max(1, min(int(badges), 9999))}
    for key, field in (("n", "name"), ("p", "project"), ("d", "blurb")):
        text = clean_text(card.get(field), TEXT_LIMITS[key])
        if text:
            body[key] = text
    if card.get("id"):
        body["i"] = int(card["id"])
    if valid_login(sender):
        body["s"] = sender
    payload = json.dumps(body).encode()
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("heart too large")
    return payload + bytes((crc8(payload),))


def decode_heart(packet):
    """Return ``(card, badges)`` from a CRC-checked packet, or ``None``."""
    if len(packet) < 3 or len(packet) > MAX_PAYLOAD + 1:
        return None
    payload, crc = packet[:-1], packet[-1]
    if crc8(payload) != crc:
        return None
    try:
        body = json.loads(payload)
    except ValueError:
        return None
    if not isinstance(body, dict) or body.get("v") != VERSION:
        return None
    login = body.get("l")
    badges = body.get("b")
    if not valid_login(login) or not isinstance(badges, int) or not 0 < badges < 10000:
        return None
    card = {"login": login, "name": clean_text(body.get("n"), TEXT_LIMITS["n"]) or login,
            "project": clean_text(body.get("p"), TEXT_LIMITS["p"]),
            "blurb": clean_text(body.get("d"), TEXT_LIMITS["d"])}
    curated = body.get("i")
    if isinstance(curated, int) and 0 < curated < 1000:
        card["id"] = curated
    sender = body.get("s")
    if valid_login(sender):
        card["sender"] = sender
    return card, badges


class Exchange:
    """One back-to-back meeting between two badges.

    ``outgoing`` is a packet from ``encode_heart`` or ``None``. ``seen`` is a
    list shared across exchanges so a resent heart is never caught twice.
    """

    def __init__(self, outgoing, now, session, peer=b"", seen=None):
        self.started = now
        self.round_at = now
        self.peer = bytes(peer)
        self.seen = seen if seen is not None else []
        self.session = session & 0xFF or 1
        self.outgoing = outgoing
        if outgoing is None:
            self.frames = [bytes((NONE, VERSION))]
            self.crc = None
        else:
            self.crc = outgoing[-1]
            self.frames = None
        self.next = 0
        self.acked = outgoing is None
        self.peer_done = False
        self.incoming = None
        self.duplicate = False
        self.in_session = None
        self.in_total = 0
        self.parts = {}

    def _split(self, capacity):
        size = max(1, capacity - 4)
        chunks = [self.outgoing[i:i + size] for i in range(0, len(self.outgoing), size)]
        if len(chunks) > 255:
            raise ValueError("heart too large for link")
        return [bytes((HEART, self.session, i, len(chunks))) + chunk for i, chunk in enumerate(chunks)]

    @property
    def done(self):
        return self.acked and self.peer_done

    def expired(self, now):
        return now - self.started >= TIMEOUT_MS

    def pump(self, send, now, capacity=20):
        """Send the next frames. ``send`` returns ``False`` when its queue is full."""
        if self.done:
            return
        if self.frames is None:
            self.frames = self._split(capacity)
        if self.next >= len(self.frames) and now - self.round_at >= RESEND_MS:
            self.next = 0
        while self.next < len(self.frames):
            if not send(self.frames[self.next]):
                return
            self.next += 1
            if self.next == len(self.frames):
                self.round_at = now

    def receive(self, message, send, now):
        if not message:
            return
        kind = message[0]
        if kind == ACK and len(message) >= 3:
            if self.outgoing is not None and message[1] == self.session and message[2] == self.crc:
                self.acked = True
        elif kind == NONE:
            if self.incoming is None:
                self.peer_done = True
        elif kind == HEART and len(message) >= 5:
            self._chunk(message, send)

    def _key(self, session, crc):
        return self.peer + bytes((session, crc))

    def _chunk(self, message, send):
        session, index, total = message[1], message[2], message[3]
        if total == 0 or index >= total:
            return
        if session != self.in_session or total != self.in_total:
            self.in_session = session
            self.in_total = total
            self.parts = {}
        self.parts[index] = bytes(message[4:])
        if len(self.parts) < total:
            return
        packet = b"".join(self.parts[i] for i in range(total))
        self.parts = {}
        key = self._key(session, packet[-1])
        if key in self.seen:
            send(bytes((ACK, session, packet[-1])))
            self.peer_done = True
            if self.incoming is None:
                self.duplicate = True
            return
        result = decode_heart(packet)
        if result is None:
            return
        self.seen.append(key)
        while len(self.seen) > SEEN_LIMIT:
            self.seen.pop(0)
        self.incoming = result
        self.duplicate = False
        self.peer_done = True
        send(bytes((ACK, session, packet[-1])))

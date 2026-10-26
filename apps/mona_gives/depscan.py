"""Find sponsorable maintainers behind a GitHub account's public dependencies.

No sign-in needed: GitHub serves the dependency graph (an SBOM) of any public
repository to anyone, and many npm packages name their own GitHub Sponsors
page in a "funding" field. Private repositories need tools/mona_gives_sync.py.

The scan is a generator so the app can step it once a frame and keep
animating while downloads run. Big JSON files are read in small chunks.
"""

import json
import os

import heartlink
from packages import PACKAGES

API = "https://api.github.com"
REPOS_URL = API + "/users/%s/repos?sort=pushed&per_page=15&type=owner"
SBOM_URL = API + "/repos/%s/dependency-graph/sbom"
NPM_URL = "https://registry.npmjs.org/%s/latest"
AVATAR_URL = "https://wsrv.nl/?url=https://github.com/%s.png&w=64&h=64&output=png"
HEADERS = {"User-Agent": "GitHub Universe Badge 2026 Mona Gives", "Accept": "application/vnd.github+json"}

MAX_REPOS = 3
MAX_TRIES = 6
MAX_NPM = 20
MAX_AVATARS = 8
MAX_CARDS = 30
MAX_PACKAGES = 400
WIFI_MS = 30000
REQUEST_MS = 25000
CHUNK = 2048
MARGIN = 256

ECOSYSTEMS = ("npm", "pypi", "cargo", "composer")
SPONSORS = "github.com/sponsors/"


class ScanError(Exception):
    pass


# ---------------------------------------------------------------- parsing ---

def _name_ok(text, extra):
    if not 0 < len(text) <= 100:
        return False
    for ch in text:
        if not ("a" <= ch <= "z" or "A" <= ch <= "Z" or "0" <= ch <= "9" or ch in extra):
            return False
    return True


def parse_source(text):
    """Turn "octocat", "@octocat", "owner/repo" or a github.com URL into
    ("owner", name) or ("repo", "owner/name"). Returns None when invalid."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    for prefix in ("https://", "http://", "github.com/", "www.github.com/", "@"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
    text = text.strip("/")
    if text.lower().startswith("github.com/"):
        text = text[11:]
    parts = text.split("/")
    if len(parts) == 1 and heartlink.valid_login(parts[0]):
        return ("owner", parts[0])
    if len(parts) == 2 and heartlink.valid_login(parts[0]) and _name_ok(parts[1], "-_."):
        return ("repo", parts[0] + "/" + parts[1])
    return None


def scan_pairs(path, keys, limit=MAX_PACKAGES):
    """Find "key":value pairs in a JSON file without loading all of it.

    ``keys`` are byte strings such as b'"fork":'. Values run to the next
    quote, comma or closing brace. Returns [(key, value_str), ...] in file
    order. Reads CHUNK bytes at a time and keeps MARGIN bytes of overlap so
    a pair split across two reads is still found exactly once.
    """
    out = []
    tail = b""
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(CHUNK)
            buf = tail + chunk
            safe = len(buf) if not chunk else max(0, len(buf) - MARGIN)
            pos = 0
            while True:
                best = -1
                found = None
                for key in keys:
                    at = buf.find(key, pos)
                    if at != -1 and at < safe and (best == -1 or at < best):
                        best = at
                        found = key
                if found is None:
                    break
                start = best + len(found)
                while start < len(buf) and buf[start:start + 1] in (b" ", b"\t", b"\r", b"\n"):
                    start += 1
                if start < len(buf) and buf[start:start + 1] == b'"':
                    start += 1
                end = start
                while end < len(buf) and buf[end:end + 1] not in (b'"', b",", b"}"):
                    end += 1
                try:
                    value = buf[start:end].decode()
                except UnicodeError:
                    value = ""
                out.append((found, value.strip()))
                pos = end
                if len(out) >= limit:
                    return out
            if not chunk:
                return out
            tail = buf[max(pos, safe):]


def parse_repos(path):
    """Public, non-fork, non-archived repos from a /users/<x>/repos listing."""
    repos = []
    current = None
    skip = False
    for key, value in scan_pairs(path, (b'"full_name":', b'"fork":', b'"archived":')):
        if key == b'"full_name":':
            if current and not skip:
                repos.append(current)
            current = value
            skip = False
        elif value == "true":
            skip = True
    if current and not skip:
        repos.append(current)
    return [repo for repo in repos if parse_source(repo) and parse_source(repo)[0] == "repo"]


def _unquote(text):
    return text.replace("%40", "@").replace("%2F", "/").replace("%2f", "/")


def purl_package(purl):
    """"pkg:npm/%40vue/shared@^3" -> ("npm", "@vue/shared"). None if unsupported."""
    if not purl.startswith("pkg:"):
        return None
    body = purl[4:]
    slash = body.find("/")
    if slash < 1:
        return None
    eco = body[:slash].lower()
    if eco not in ECOSYSTEMS:
        return None
    name = _unquote(body[slash + 1:])
    for stop in ("?", "#"):
        if stop in name:
            name = name[:name.find(stop)]
    version = name.rfind("@")
    if version > 0:
        name = name[:version]
    name = name.strip()
    if eco == "pypi":
        name = name.lower().replace("_", "-").replace(".", "-")
    elif eco == "composer":
        name = name.lower()
    if not _name_ok(name, "-_.@/"):
        return None
    return (eco, name)


def parse_packages(path):
    packages = []
    seen = set()
    for _, value in scan_pairs(path, (b'"referenceLocator":',)):
        package = purl_package(_unquote(value) if value.startswith("pkg:") else value)
        if package and package not in seen:
            seen.add(package)
            packages.append(package)
    return packages


def funding_login(funding):
    """The GitHub Sponsors login a package.json "funding" field names, if any.

    Only github.com/sponsors/<login> counts. Repository links such as
    github.com/owner/repo?sponsor=1 point at a repo, not a person.
    """
    if isinstance(funding, list):
        for item in funding:
            login = funding_login(item)
            if login:
                return login
        return None
    if isinstance(funding, dict):
        funding = funding.get("url")
    if not isinstance(funding, str):
        return None
    at = funding.lower().find(SPONSORS)
    if at == -1:
        return None
    login = funding[at + len(SPONSORS):]
    for stop in ("/", "?", "#"):
        if stop in login:
            login = login[:login.find(stop)]
    return login if heartlink.valid_login(login) else None


def build_cards(matches, curated):
    """``matches`` maps login -> {"packages": [...], "via": repo, "how": ...}."""
    cards = []
    for login, info in matches.items():
        known = curated.get(login.lower())
        names = info["packages"]
        more = len(names) - 1
        blurb = "Maintains %s%s you use." % (names[0], " and %d more" % more if more else "")
        card = {
            "login": known["login"] if known else login,
            "name": known["name"] if known else login,
            "project": known["project"] if known else names[0],
            "blurb": blurb,
            "via": info["via"],
            "verified": bool(known),
            "how": "curated" if known else info["how"],
        }
        cards.append((0 if known else 1, -len(names), card["login"].lower(), card))
    cards.sort(key=lambda item: item[:3])
    return [item[3] for item in cards[:MAX_CARDS]]


# ------------------------------------------------------------------- scan ---

class Scanner:
    """Steps through a scan. ``start(url, path, headers)`` must return a
    request that is truthy once the file is written and exposes ``.error``;
    ``online()`` drives Wi-Fi and returns True once connected; ``clock()``
    returns milliseconds."""

    def __init__(self, source, start, online, clock, curated, workdir="/state", token=""):
        self.source = parse_source(source)
        self.label = source
        self.start = start
        self.online = online
        self.clock = clock
        self.curated = curated
        self.workdir = workdir
        self.token = token
        self.repos = []
        self.package_count = 0
        self.cards = None
        self.error = None
        self.status = "Starting..."

    def headers(self, url):
        if self.token and url.startswith(API):
            headers = dict(HEADERS)
            headers["Authorization"] = "Bearer " + self.token
            return headers
        return HEADERS

    def tmp(self, name):
        return "%s/mona_gives_%s.tmp" % (self.workdir, name)

    def download(self, url, path, status):
        self.status = status
        request = self.start(url, path, self.headers(url))
        began = self.clock()
        while not request:
            if getattr(request, "error", None):
                raise ScanError(str(request.error))
            if self.clock() - began > REQUEST_MS:
                raise ScanError("timed out")
            yield status
        return path

    def steps(self):
        if self.source is None:
            raise ScanError("Not a GitHub user, org or owner/repo")
        self.status = "Joining Wi-Fi..."
        began = self.clock()
        while not self.online():
            if self.clock() - began > WIFI_MS:
                raise ScanError("Couldn't join Wi-Fi")
            yield self.status

        kind, name = self.source
        if kind == "repo":
            candidates = [name]
        else:
            path = self.tmp("repos")
            try:
                yield from self.download(REPOS_URL % name, path, "Finding @%s's public repos" % name)
            except ScanError as error:
                raise ScanError("Couldn't list @%s's repos (%s)" % (name, error))
            candidates = parse_repos(path)[:MAX_TRIES]
            _remove(path)
            if not candidates:
                raise ScanError("@%s has no public repos to scan" % name)

        packages = []
        via = {}
        errors = []
        for repo in candidates:
            if len(self.repos) >= MAX_REPOS or len(packages) >= MAX_PACKAGES:
                break
            path = self.tmp("sbom")
            try:
                yield from self.download(SBOM_URL % repo, path, "Reading %s" % repo)
                found = parse_packages(path)
            except (ScanError, OSError, ValueError) as error:
                errors.append(str(error))
                _remove(path)
                continue
            _remove(path)
            self.repos.append(repo)
            for package in found:
                if package not in via:
                    via[package] = repo
                    packages.append(package)
                    if len(packages) >= MAX_PACKAGES:
                        break
        self.package_count = len(packages)
        if not self.repos:
            where = name if kind == "repo" else "@%s's recent public repos" % name
            if all("404" in error for error in errors):
                raise ScanError("No dependency graph in %s" % where)
            raise ScanError("Couldn't read %s (%s)" % (where, errors[-1]))

        matches = {}
        me = name.split("/")[0].lower()

        def add(login, package, how):
            key = login.lower()
            if key == me:
                return
            entry = matches.get(key)
            if entry is None:
                entry = {"packages": [], "via": via[package], "how": how}
                matches[key] = entry
                entry["login"] = login
            if package[1] not in entry["packages"]:
                entry["packages"].append(package[1])

        npm = []
        for package in packages:
            login = PACKAGES.get("%s:%s" % package)
            if login:
                add(login, package, "curated")
            elif package[0] == "npm":
                npm.append(package)

        for index, package in enumerate(npm[:MAX_NPM]):
            path = self.tmp("npm")
            status = "Checking npm %d/%d" % (index + 1, min(len(npm), MAX_NPM))
            try:
                yield from self.download(NPM_URL % package[1], path, status)
                with open(path) as handle:
                    funding = json.load(handle).get("funding")
                login = funding_login(funding)
            except (ScanError, OSError, ValueError, AttributeError):
                login = None
            _remove(path)
            if login:
                add(login, package, "npm")

        keyed = {}
        for entry in matches.values():
            keyed[entry["login"]] = entry
        self.cards = build_cards(keyed, self.curated)

        avatars = [card["login"] for card in self.cards if not card["verified"]][:MAX_AVATARS]
        for index, login in enumerate(avatars):
            path = avatar_path(self.workdir, login)
            if _exists(path):
                continue
            try:
                yield from self.download(AVATAR_URL % login, path + ".tmp", "Fetching faces %d/%d" % (index + 1, len(avatars)))
                os.rename(path + ".tmp", path)
            except (ScanError, OSError):
                _remove(path + ".tmp")
        self.status = "Done"

    def result(self):
        return {"source": self.label, "repos": self.repos, "packages": self.package_count,
                "dependencies": self.cards or []}


def avatar_path(workdir, login):
    return "%s/mona_gives_av_%s.png" % (workdir, login.lower())


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass

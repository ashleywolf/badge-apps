#!/usr/bin/env python3
"""Sync your real GitHub data for the Mona Gives badge app.

Runs on your laptop with the GitHub CLI (`gh auth login`), so the badge never
holds a token. It reads, never writes, GitHub data:

* Dependencies: the dependency graph of repositories you name with --repo,
  keeping only owners with a GitHub Sponsors listing. Nothing is guessed: if
  GitHub doesn't link a package to a repository, it is skipped.
* Sponsoring: your active sponsorships. Private ones are left out unless you
  pass --include-private.
* Confirmed: sponsorships you started in the last --since days. The badge
  celebrates each one once. No amounts are ever read or stored.

Examples:
    python3 tools/mona_gives_sync.py --repo octocat/hello-world
    python3 tools/mona_gives_sync.py --repo me/app --out personal.json

Copy the output to the badge either by dropping it into
/system/apps/mona_gives/personal.json in USB Disk Mode, or with:
    mpremote connect <port> fs cp personal.json :/state/mona_gives_personal.json

Follow the people whose hearts you caught (the only thing this tool writes,
and it asks about each person first):
    mpremote connect <port> fs cp :/state/mona_gives_met.json met.json
    python3 tools/mona_gives_sync.py --follow met.json
Following needs the user:follow scope: gh auth refresh -s user:follow
"""

import argparse
import datetime
import json
import re
import subprocess
import sys

LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
LIMITS = {"name": 40, "project": 80, "blurb": 60, "via": 80}

DEPENDENCIES = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    dependencyGraphManifests(first: 20, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        dependencies(first: 100) {
          nodes {
            packageName
            repository {
              nameWithOwner
              description
              isArchived
              owner {
                login
                ... on User { name hasSponsorsListing }
                ... on Organization { name hasSponsorsListing }
              }
            }
          }
        }
      }
    }
  }
}
"""

SPONSORING = """
query($cursor: String) {
  viewer {
    sponsorshipsAsSponsor(first: 100, after: $cursor, activeOnly: true) {
      pageInfo { hasNextPage endCursor }
      nodes {
        createdAt
        privacyLevel
        sponsorable {
          ... on User { login name hasSponsorsListing pinnedItems(first: 1, types: REPOSITORY) { nodes { ... on Repository { nameWithOwner description } } } }
          ... on Organization { login name hasSponsorsListing pinnedItems(first: 1, types: REPOSITORY) { nodes { ... on Repository { nameWithOwner description } } } }
        }
      }
    }
  }
}
"""


def graphql(query, **variables):
    command = ["gh", "api", "graphql", "-f", "query=" + query]
    for key, value in variables.items():
        if value is not None:
            command += ["-F", "%s=%s" % (key, value)]
    result = subprocess.run(command, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
    except ValueError:
        raise SystemExit("gh api graphql failed: " + (result.stderr.strip() or result.stdout.strip()))
    if data.get("errors"):
        messages = sorted({e.get("message", "") for e in data["errors"]})
        if not data.get("data"):
            raise SystemExit("GitHub returned errors: " + "; ".join(messages))
        # Partial results, for example SAML-protected orgs: those entries come back null.
        print("warning: skipped some entries: " + "; ".join(messages), file=sys.stderr)
    return data["data"]


def clean(value, limit):
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value if 32 <= ord(ch) < 127).strip()[:limit]


def card(login, name, project, blurb, via=None):
    out = {
        "login": login,
        "name": clean(name, LIMITS["name"]) or login,
        "project": clean(project, LIMITS["project"]),
        "blurb": clean(blurb, LIMITS["blurb"]),
    }
    if via:
        out["via"] = clean(via, LIMITS["via"])
    return out


def dependencies(repos):
    found = {}
    for full in repos:
        if full.count("/") != 1:
            raise SystemExit("--repo must look like owner/name, got %r" % full)
        owner, name = full.split("/")
        cursor = None
        while True:
            data = graphql(DEPENDENCIES, owner=owner, name=name, cursor=cursor)["repository"]
            if data is None:
                raise SystemExit("Repository %s not found or not visible to gh" % full)
            manifests = data["dependencyGraphManifests"]
            for manifest in manifests["nodes"] or []:
                for dep in ((manifest or {}).get("dependencies") or {}).get("nodes") or []:
                    repo = (dep or {}).get("repository")
                    if not repo or repo.get("isArchived"):
                        continue
                    owner_info = repo["owner"]
                    login = owner_info.get("login", "")
                    if not owner_info.get("hasSponsorsListing") or not LOGIN.match(login):
                        continue
                    if login.lower() not in found:
                        found[login.lower()] = card(login, owner_info.get("name"), repo["nameWithOwner"],
                                                    repo.get("description"), data["nameWithOwner"])
            if not manifests["pageInfo"]["hasNextPage"]:
                break
            cursor = manifests["pageInfo"]["endCursor"]
    return sorted(found.values(), key=lambda c: c["login"].lower())


def sponsorships(include_private, since):
    sponsoring = []
    confirmed = []
    cursor = None
    while True:
        data = graphql(SPONSORING, cursor=cursor)["viewer"]["sponsorshipsAsSponsor"]
        for node in data["nodes"] or []:
            if not node:
                continue
            who = node.get("sponsorable") or {}
            login = who.get("login", "")
            if not LOGIN.match(login):
                continue
            if node.get("privacyLevel") == "PRIVATE" and not include_private:
                continue
            pinned = (who.get("pinnedItems") or {}).get("nodes") or [{}]
            sponsoring.append(card(login, who.get("name"), pinned[0].get("nameWithOwner"), pinned[0].get("description")))
            created = datetime.datetime.fromisoformat(node["createdAt"].replace("Z", "+00:00"))
            if created >= since:
                confirmed.append(login)
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return sponsoring, confirmed


def gh_ok(args, run=subprocess.run):
    return run(["gh", "api"] + args + ["--silent"], capture_output=True, text=True).returncode == 0


def follow_people(path, ask=input, run=subprocess.run, out=print):
    """Ask about each person in a badge's met list and follow the ones you approve."""
    try:
        with open(path) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        raise SystemExit("Couldn't read %s: %s" % (path, error))
    met = data.get("met") if isinstance(data, dict) else None
    if not isinstance(met, list):
        raise SystemExit("%s has no 'met' list. Copy it from :/state/mona_gives_met.json" % path)
    logins = []
    for login in met:
        if isinstance(login, str) and LOGIN.match(login) and login.lower() not in {l.lower() for l in logins}:
            logins.append(login)
    followed = failed = 0
    for login in logins:
        if gh_ok(["/user/following/" + login], run):
            out("Already following @%s" % login)
            continue
        answer = ask("Follow @%s (https://github.com/%s)? [y/N] " % (login, login))
        if answer.strip().lower() not in ("y", "yes"):
            continue
        if gh_ok(["-X", "PUT", "/user/following/" + login], run):
            followed += 1
            out("Followed @%s" % login)
        else:
            failed += 1
            out("Couldn't follow @%s" % login)
    if failed:
        out("If following failed, add the scope with: gh auth refresh -s user:follow")
    out("Followed %d of %d people" % (followed, len(logins)))
    return followed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", action="append", default=[], help="owner/name whose dependencies to scan (repeatable)")
    parser.add_argument("--no-sponsorships", action="store_true", help="skip reading your sponsorships")
    parser.add_argument("--include-private", action="store_true", help="also include your private sponsorships")
    parser.add_argument("--since", type=int, default=7, help="celebrate sponsorships started in the last N days")
    parser.add_argument("--out", default="personal.json", help="output file (default personal.json)")
    parser.add_argument("--follow", metavar="MET_JSON", help="follow people from a badge's met list (asks first)")
    args = parser.parse_args(argv)
    if args.follow:
        follow_people(args.follow)
        return 0

    output = {"version": 1}
    if args.repo:
        output["dependencies"] = dependencies(args.repo)
    if not args.no_sponsorships:
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=args.since)
        output["sponsoring"], output["confirmed"] = sponsorships(args.include_private, since)

    with open(args.out, "w") as handle:
        json.dump(output, handle, separators=(",", ":"))
    print("Wrote %s: %d dependency maintainers, %d sponsorships, %d to celebrate" % (
        args.out, len(output.get("dependencies", [])), len(output.get("sponsoring", [])),
        len(output.get("confirmed", []))))


if __name__ == "__main__":
    sys.exit(main())

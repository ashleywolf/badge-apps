Mona Gives helps you discover open source maintainers, open their GitHub Sponsors page by QR code, and pass them on to another badge.

![Mona holding a green heart](icon.png)

## Pass the Heart

1. Press **Start Giving** on the welcome screen to jump straight to a
   maintainer card. Press **UP** instead for more ways to find one:
   **Discover Someone New**, **My Dependencies** or **My Sponsors**.
2. On a maintainer card, press **SELECT** to show a QR code for their GitHub
   Sponsors page, or **RIGHT** to pass the heart.
3. To pass, hold your badge back to back with a friend's badge that is also
   running Mona Gives. Mona tosses the heart, and their Mona catches it with
   the same maintainer card. Their badge shows how many badges the heart has
   traveled through. Your badge looks for a catcher for about 10 seconds,
   with a countdown, and keeps going while another badge is connecting. If
   nobody catches it, you get a QR code to share instead.
4. If you set your GitHub username in the badge Settings, the heart carries
   it too. The catcher sees "Caught from @you" and can press **DOWN** for a QR
   code to your GitHub profile, then tap **Follow** on their phone. Their
   badge also saves your name so they can follow you later from a laptop.

Passing is always free. Nothing on the badge asks for or handles money.

## Follow the people you met

The badge can't follow anyone by itself, because it holds no GitHub login.
To follow everyone whose heart you caught, copy the saved list to your laptop
and approve each person:

```sh
gh auth refresh -s user:follow
mpremote connect <port> fs cp :/state/mona_gives_met.json met.json
python3 tools/mona_gives_sync.py --follow met.json
```

The tool skips people you already follow and asks before following anyone
else.

## Controls

| Screen | Buttons |
| --- | --- |
| Welcome | SELECT start (opens a maintainer card), UP more ways to discover, MENU heart collection, BACK exit |
| Discover | UP/DOWN choose, SELECT open, RIGHT on My Dependencies scans again, BACK home |
| Scanning | BACK cancel; after an error SELECT curated picks, RIGHT try again |
| Maintainer card | UP/DOWN browse, SELECT sponsor QR, RIGHT pass it on, MENU collection, BACK; on a caught card, DOWN follows the passer |
| Follow QR | BACK card |
| Sponsor QR | RIGHT pass it on, BACK card |
| Passing | SELECT share by QR instead, BACK cancel |
| Heart collection | ARROWS move, SELECT open card, BACK |

After 25 seconds on the welcome screen, attract mode starts. Two Monas toss a
heart back and forth under "PASS THE HEART", "DISCOVER. SPONSOR. PASS IT ON."
and "GITHUB GIVES". Then a big "Scan to meet a maintainer" QR code shows a
different curated maintainer's Sponsors page, so passers-by can try it from
their phone. The two views take turns. Any button returns to the welcome
screen.

## What works today

| Feature | Status |
| --- | --- |
| Animated Mona welcome screen | Done |
| Discover Someone New: 28 curated maintainers, each checked with the GitHub GraphQL API for a live Sponsors listing and a real, active repository | Done, labeled "Meet a maintainer" |
| Maintainer cards with avatar, name, login, project, description and Sponsors status | Done |
| QR code to `https://github.com/sponsors/<login>`, made on the badge by the firmware in GitHub green with a heart in the middle | Done |
| Pass-the-Heart toss and catch animations | Done |
| Badge-to-badge passing over the firmware's Bluetooth link, with chunking, CRC checks, acknowledgments, resends, timeouts and duplicate detection | Done, tested with a simulated link; needs real-badge testing |
| QR fallback when no badge catches the heart or Bluetooth is missing | Done |
| Giving chain ("This heart has traveled through N badges!") | Done, counted per pass |
| Mona's Heart Collection, one heart per unique maintainer | Done |
| "Caught from @you", a follow QR for the passer, and a saved list for following from your laptop | Done, needs real-badge testing |
| Attract mode, with a scannable maintainer QR code | Done |
| My Dependencies from your public repos, scanned on the badge over Wi-Fi with no sign-in | Done |
| My Dependencies from private repos | Done through the laptop sync tool |
| My Sponsors, public sponsorships only unless you opt in | Done through the laptop sync tool |
| Celebration for a new sponsorship confirmed by the GitHub API | Done through the laptop sync tool |
| Optional campaign attribution (`metadata_campaign`) | Off by default; set `CAMPAIGN` in `__init__.py` |
| Signing in to GitHub on the badge | Planned, needs a backend |
| A shared, conference-wide giving chain and aggregate metrics | Planned, needs a backend |
| Instant celebration right after someone scans and sponsors | Planned, needs a webhook backend |

## Install

1. Put the badge in USB Disk Mode (double-press RESET, or run
   `mpremote connect <port> exec "import powman; powman.reset_into_msc()"`).
2. Copy this whole `mona_gives` folder to `BADGER/apps/mona_gives`.
3. Eject the drive and reset the badge. Mona Gives appears in the menu.

## Scan your public repos (no sign-in)

**My Dependencies** works with just your GitHub name and Wi-Fi:

1. In the badge **Settings** app, set your GitHub username and Wi-Fi.
2. Open Mona Gives, choose **My Dependencies**, and wait about 10 seconds.

The badge reads the dependency graph of up to 3 of your most recently pushed
public repos (skipping forks, archived repos and repos with no package files).
It then shows maintainers you depend on:

- **Curated maintainers** whose packages appear in your graph (see
  `packages.py`).
- **npm maintainers** whose package names a `github.com/sponsors/<login>`
  page in its `funding` field. These cards say "Sponsor link in npm".

Results are saved, so the list opens instantly and works offline next time.
Press **RIGHT** on **My Dependencies** to scan again.

To scan an organization or one repo instead of your own account, add a line
like `MONA_GIVES_SOURCE = "your-org"` or `MONA_GIVES_SOURCE = "owner/repo"`
to `secrets.py` on the USB drive.

GitHub allows 60 unsigned requests an hour per network, and a scan uses up to
7. On busy conference Wi-Fi, an optional read-only `GITHUB_TOKEN` in
`secrets.py` raises that limit. It's only sent to `api.github.com`.

Private repos can't be read without signing in, so use the laptop sync below.

## Load private dependencies and sponsorships (optional)

For private repos and your sponsorships, run the sync tool on your laptop,
where the GitHub CLI is already signed in. Synced dependencies replace the
public scan:

```sh
gh auth login
python3 tools/mona_gives_sync.py --repo your-name/your-app --out personal.json
```

Then copy `personal.json` to the badge in either of these ways:

- In USB Disk Mode, drop it into `BADGER/apps/mona_gives/personal.json`.
- Or run `mpremote connect <port> fs cp personal.json :/state/mona_gives_personal.json`.

The tool only lists maintainers that GitHub's dependency graph links to a
repository whose owner has a GitHub Sponsors listing. It never guesses. It
leaves out private sponsorships unless you pass `--include-private`, and it
never reads amounts. Sponsorships you started in the last 7 days (`--since`)
get one celebration each.

## Permissions and services

| What | Why |
| --- | --- |
| Bluetooth link (firmware `badgeware.link`) | Passing hearts between badges held back to back |
| Wi-Fi from the badge Settings | Public dependency scan |
| `api.github.com` repo list and dependency graph (SBOM), no sign-in | Public dependency scan |
| `registry.npmjs.org` package metadata | Finding `funding` Sponsors links |
| `wsrv.nl` image proxy for `github.com/<login>.png` | Small PNG avatars for npm maintainers |
| GitHub CLI on your laptop, read-only GraphQL | Optional sync of private dependencies and sponsorships |
| GitHub CLI on your laptop with `user:follow` | Optional `--follow`, only for people you approve |
| `GITHUB_USERNAME` from the badge Settings | Sent with each heart you pass so the catcher can follow you. Leave it empty to share nothing |
| github.com, opened on the scanner's own phone | Viewing a Sponsors page and checking out on GitHub |

There is no backend and no OAuth app, and no token is needed. The badge
stores discovered logins, pass counts and the chain length in
`/state/mona_gives.json`, the last public scan in
`/state/mona_gives_scan.json`, and up to 50 people whose hearts you caught
in `/state/mona_gives_met.json`.

## Hardware limits and tradeoffs

- **Bluetooth, not infrared.** The badge has an IR receiver and transmitter,
  but the firmware's Bluetooth link already handles "hold badges back to back"
  pairing for Contacts and Pong. Mona Gives reuses it, so passing works the
  same way people already know.
- **Small messages.** The link sends short packets, so a heart is split into
  chunks, each checked with a CRC and acknowledged. Lost chunks are resent,
  and the same heart is never caught twice.
- **No live verification on the badge.** A QR scan doesn't prove anyone
  sponsored. The celebration only appears after the sync tool confirms a
  sponsorship through the GitHub API.
- **Local giving chain.** Each badge counts the passes it has seen. A shared,
  conference-wide count would need a backend.
- **Public scan, not sign-in.** Signing in on a badge needs a backend and an
  OAuth app. Public dependency graphs need neither, so the badge reads those
  and leaves private repos to the laptop sync.
- **Small scan.** To stay within memory and the unsigned API limit, the scan
  reads 3 repos, up to 400 packages and 20 npm lookups. Big JSON files are
  read in 2 KB chunks.
- **Memory.** Avatars are 56x56 paletted PNGs (about 1 KB each), loaded a few
  at a time. QR codes are made once per maintainer and cached.
- **Green QR codes.** QR codes use GitHub green with a heart in the middle,
  inspired by [OctoQR](https://www.woodwardweb.com/ghqr/). They use the
  highest error correction so the heart doesn't stop phones from reading
  them. The GitHub logo isn't used, because that needs brand approval.

## Credits

The Mona sprites come from [badger/home](https://github.com/badger/home),
Copyright (c) Pimoroni & GitHub, used under the MIT License. See
[`assets/mona/LICENSE-badger-home`](assets/mona/LICENSE-badger-home).
Maintainer avatars are their public GitHub profile pictures. GitHub, Mona and
GitHub Sponsors are trademarks of GitHub, Inc.

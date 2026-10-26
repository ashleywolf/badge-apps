# GitGotchi

A Tamagotchi-style virtual pet where you hatch and raise Mona, a rubber duck, the ship-it squirrel or Copilot.

## Usage

1. Press LEFT and RIGHT to pick a pet, then SELECT to hatch its egg.
2. Press LEFT and RIGHT to choose an action at the bottom of the screen, and SELECT to do it:
   - **Feed**: give a Meal (fills the food meter) or a Snack (a little food, lots of fun).
   - **Play**: a 20-second mini-game. Hold LEFT and RIGHT to catch falling stars and dodge bugs.
   - **Clean**: wash away the bugs your pet leaves around the room.
   - **Patch**: give medicine when your pet shows a red **+** because it is sick.
   - **Lights**: turn the lights off so your pet can sleep, and back on to wake it up.
   - **Stats**: see age, weight, food, fun, energy, health, and how many friends you've met. Press BACK to close.
3. A red **!** above your pet (and glowing case lights) means it needs something.
4. Press MENU to start over with a new pet.
5. Hold your badge back to back with a friend's badge to visit. See
   [Visit a friend](#visit-a-friend).

The meters at the top show food, fun and energy. They go down over time, slower
while the pet sleeps and much slower while the app is closed. If food or fun
stays empty for a long time with the app open, your pet wanders off to touch
grass, and you can hatch a new one.

Your pet is saved on the badge. If the badge clock has been set (for example by
connecting to Wi-Fi), time away from the app counts too. No extra hardware or
network access is required.

## Visit a friend

When two people both have GitGotchi open, their pets can hang out.

1. Open GitGotchi and stay on the home screen with your pet awake.
2. Hold your badge back to back with a friend's badge. The case lights flash
   and the screen says **Someone's nearby...** while the badges pair.
3. Each pet jumps over to the other badge. Your screen shows your pet plus
   your friend's pet, named by their GitHub username, for example
   "@octocat's Ducky came to visit!"
4. The pets wave hello, then play on their own. You can pick what they do,
   and both badges show the same thing:

   | Button | What the pets do |
   | --- | --- |
   | SELECT | High five |
   | UP | Dance party |
   | DOWN | Share a snack |
   | LEFT or RIGHT | Wave |
   | BACK | Say bye |

5. A visit lasts up to 5 minutes. It also ends when someone presses BACK,
   walks away, closes the app, or their pet falls asleep. The guest waves bye
   and jumps home.

Visits make your pet happier and use a little energy. Your badge remembers up
to 20 friends, and **Stats** shows how many you've met.

Visits use the firmware's Bluetooth badge link, the same one Contacts and Pong
use, so they work offline at a venue with no Wi-Fi. After a visit, the same two
badges wait a short cool-down before they pair again.

### Try it without a second badge

- **Simulator:** in the [badge simulator](https://badger.github.io/simulator/),
  press UP on the home screen. A pretend friend visits so you can see the whole
  flow. In the simulator, the K key is BACK.
- **Two pets on your laptop:** run the end-to-end test. It loads two copies of
  GitGotchi, connects them through a fake radio (including dropped and repeated
  messages), and plays through full visits:

  ```bash
  python3 tools/gitgotchi_visit_test.py
  ```

  It prints each check and writes a JSON report to
  `gitgotchi-visit-report.json`.

## Credits

The Mona and squirrel sprites come from [badger/home](https://github.com/badger/home),
Copyright (c) Pimoroni & GitHub, used under the MIT License. See
[`assets/LICENSE-badger-home`](assets/LICENSE-badger-home). I drew the rubber
duck, Copilot, and icon art in code.

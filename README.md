# Theme Park (EA) Revival

EA's **Theme Park** for Android (2012, by Progressive Media) stopped working when
EA shut down its servers. Your whole park lived on those servers, so the game
could not even start.

This project brings it back:

- a **server emulator** that replaces EA's servers and saves your park, and
- a **64-bit port** of the game, so it runs on modern phones (tested on Android 16
  and Android 13; the app supports Android 2.3 and newer).

No game files are in this repository. You need your own copy of the game
(version 4.4.92, the APK and its OBB data file).

## What works

- Login, new game, the full tutorial
- Building, upgrading, selling and moving rides, shops and decorations
- Saving: your park, money, tickets, level, quests, staff, land and statues are
  stored on the server, and ride timers keep running while the game is closed
- Sound effects and music
- Daily bonus (the game's own 28-day calendar)
- Friends: add friends with a friend code, visit their parks in **Neighbor Parks**,
  empty their trash and mop up puke for daily rewards, hire friends as staff
- The Advisor's park in Neighbor Parks
- Promo codes (for example `REVIVAL`: $10,000 and 5 super tickets, once per player)

Not included on purpose: the real-money shop. Nothing can be bought for real
money. Super tickets come from playing, levelling up, the daily bonus and codes.

## Friends and codes

Tap the blue **Friends & Codes** button at the top of the screen.

1. **My friend code** shows your 6-letter code. Send it to a friend.
2. Your friend taps **Add a friend** and types your code. You are now friends.
3. Restart the game. Your friend is in **Neighbor Parks** (the people button at
   the bottom right). Tap **Visit**.

The same menu has **Enter a promo code** and **Change my name**.

## Build the app

You need Linux (or WSL) with:

- Python 3.9+
- Java 17+ (`javac`, `keytool`)
- Android build tools: `d8`, `zipalign`, `apksigner`
- [apktool 2.11.1](https://github.com/iBotPeaches/Apktool/releases) saved as `tools/apktool.jar`

Steps:

1. Unzip the game's OBB file (`main.4004092.com.eamobile.themepark_row.obb` is a
   zip file) into a folder, for example `obb/`.
2. Build, with the address of the server you want to play on:

   ```bash
   python3 tools/build_port.py ThemePark-4.4.92.apk obb/ ThemePark-revival.apk http://YOUR-SERVER:8086
   ```

3. Install `ThemePark-revival.apk` on your phone. If the original EA game is
   installed, uninstall it first (the new app is signed with your own key).

The first build creates your signing key in `tools/themepark.keystore`. Keep it:
later builds must use the same key to install as an update without losing data.

What the build does: it replaces the game's 32-bit native libraries with Java
code (graphics, sound, login), puts the OBB data inside the APK, points the game
at your server and adds the Friends & Codes menu. See `tools/build_port.py`.

## Host a server

The server is plain Python 3 with no extra packages. Anything that runs Python
works: your PC, a Raspberry Pi, or a free cloud VM.

### On your own PC (Linux, macOS or Windows)

Download this repository, then in the project folder:

Linux / macOS:

```bash
TP_PORT=8086 TP_PUBLIC=http://YOUR-IP:8086 python3 server/server.py
```

Windows (PowerShell, with Python from python.org):

```powershell
$env:TP_PORT="8086"; $env:TP_PUBLIC="http://YOUR-IP:8086"; python server\server.py
```

- `TP_PUBLIC` is the address phones use to reach the server. Build the app
  with the same address.
- Allow TCP port 8086 in your firewall.

- `YOUR-IP` is your PC's address on your Wi-Fi (for players at home) or your
  public IP (for players elsewhere; then forward port 8086 in your router).
- The server keeps running while the window is open.

### On a VPS or cloud VM (any Ubuntu/Debian server, e.g. Oracle Cloud free tier)

The deploy script sets everything up from your PC over SSH.

1. Create the server and allow incoming TCP port 8086 in your provider's
   firewall (on Oracle: the subnet's Security List, Ingress rule, source
   `0.0.0.0/0`).
2. Copy `deploy/deploy.env.example` to `deploy/deploy.env` and fill in your VM's
   address and SSH key.
3. Run:

   ```bash
   bash deploy/deploy_oracle.sh
   ```

   This needs SSH access with sudo. It copies the server, installs it as a `systemd` service called
   `themepark` (it starts again after a reboot) and opens port 8086 in the VM's
   own firewall. Run it again to update; saved parks are kept.

### Settings

`server/settings.json`:

| Setting | Meaning |
|---|---|
| `promoCodes` | Codes and their rewards, e.g. `"REVIVAL": {"cash": 10000, "tickets": 5}` |
| `timezone` | When a new day starts for the daily bonus (default `Europe/Prague`) |
| `startCash`, `startTickets` | Money and super tickets a new park starts with (default 10,000 and 10) |
| `upgradeCostMultiplier` | Multiplies every upgrade price (default 5; the game's own prices are very low) |
| `upgradeCostFixed` | Fixed upgrade prices by item id, e.g. the tutorial's Bouncy Castle (`3000`) and French Friend Fries (`4002`) at $50 |
| `easyMode` | `true` gives ticket-only items a cash price and every park 500,000 cash and 100 tickets once |

Restart the server after changing it.

### Data and backups

Everything is in `server/data/`:

- `parks/<player>.json`: one file per player, the whole park
- `state.json`: which device owns which player
- `requests.log`: request log (rotated at 20 MB)

Back up the `data` folder. To give a player a fresh start, rename their park file.

## Security

- The app contains only the server address. No passwords or keys.
- A player's login key is only given to the device that owns that player, and
  every park request must carry it. Nobody can change someone else's park.
- Other players' parks can only be viewed by their friends.
- Request size is limited, and login keys are not written to the log.
- The server runs as a normal user, not root. Protect your VM's SSH with key
  login only.

## Project layout

| Path | What it is |
|---|---|
| `server/server.py` | HTTP server: EA "Synergy" login, Mayhem users and sessions |
| `server/game.py` | Theme Park game requests, saving, friends, daily bonus, codes |
| `server/catalog.json` | Ride/shop/decoration stats, rebuilt from the game's own tables |
| `port/src/` | Java replacements for the native libraries, plus the revival menu |
| `port/stubs/` | Minimal Android/game classes to compile against (not shipped) |
| `tools/build_port.py` | Builds the 64-bit app |
| `tools/bfc.py`, `tools/catalog.py` | Read the game's data archive, rebuild `catalog.json` |
| `deploy/` | Cloud VM deploy script |

## Credits

- The game: Theme Park by EA and Progressive Media. This project is not affiliated
  with or endorsed by EA. It contains no game files; you need your own copy.
- Revival: AriCuteGirl. Built with the help of Claude (AI) for reverse
  engineering and code.

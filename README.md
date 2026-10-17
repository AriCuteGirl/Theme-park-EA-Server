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

Not included on purpose: the real-money shop. The GET MORE! button is removed
and nothing can be bought for real money. Super tickets come from playing, levelling up, the daily bonus and codes.

## Friends and codes

Tap the blue **Friends & Codes** button at the top of the screen.

1. **My friend code** shows your 6-letter code. Send it to a friend.
2. Your friend taps **Add a friend** and types your code. You are now friends.
3. Restart the game. Your friend is in **Neighbor Parks** (the people button at
   the bottom right). Tap **Visit**.

The same menu has **Enter a promo code** and **Change my name**.

## How it fits together

To play you need two things:

1. **A server.** It keeps everyone's parks. One person hosts it (on a PC, a
   VPS or a free cloud VM) and everyone plays on it together.
2. **The app, built for that server.** The original EA app does not work any
   more: it tries to reach EA's dead servers and needs 32-bit parts that new
   phones don't have. `tools/build_port.py` turns your copy of the game into a
   working app with the server's address built in. An app built for one server
   always connects to that server.

So the order is: start a server, build the app with its address, install the
app on the phones.

## Build the app

You do this once on a PC. The result is one APK file you can install on any
Android phone (Android 2.3 or newer, 32-bit or 64-bit).

### 1. Get the game files

You need **version 4.4.92** of Theme Park, two files:

- the APK, for example `ThemePark-4.4.92.apk`
- its OBB data file: `main.4004092.com.eamobile.themepark_row.obb`
  (some sites call it "SD cache" or "data"; it can be inside a zip or rar, unpack
  that first). If the game is still on a phone, the OBB is in
  `Android/obb/com.eamobile.themepark_row/`.

Other versions (like 4.5.88 or 4.2.1) do not work: the build stops with
`pattern not found`.

### 2. Install the tools

The build runs on Linux. On Windows, use WSL (install it with `wsl --install`
in PowerShell, then use the Ubuntu window). On Ubuntu / Debian / WSL:

```bash
sudo apt install python3 openjdk-17-jdk-headless unzip wget git
```

Download this project and the two extra tools into it:

```bash
git clone https://github.com/AriCuteGirl/Theme-park-EA-Server.git
cd Theme-park-EA-Server
wget -O tools/apktool.jar https://github.com/iBotPeaches/Apktool/releases/download/v2.11.1/apktool_2.11.1.jar
wget https://dl.google.com/android/repository/build-tools_r34-linux.zip
unzip build-tools_r34-linux.zip -d ~/android-build-tools
export PATH="$HOME/android-build-tools/android-14:$PATH"
```

The last line makes `d8`, `zipalign` and `apksigner` available. It only lasts
for this terminal window; run it again in a new window (or add it to
`~/.bashrc`).

### 3. Unzip the OBB

An OBB file is a zip file. Unzip it into a folder of its own:

```bash
unzip main.4004092.com.eamobile.themepark_row.obb -d obb
```

The `obb` folder now has files like `0.bfc`, `head_large.bfc`, `wv0000`,
`audio_large.pac` and the music `.mp3` files.

### 4. Build

Run this in the project folder:

```bash
python3 tools/build_port.py ThemePark-4.4.92.apk obb ThemePark-revival.apk http://SERVER-ADDRESS:8086
```

The four parts, in this order:

| Part | What to put there |
|---|---|
| `ThemePark-4.4.92.apk` | Path to the original game APK |
| `obb` | Path to the **folder** with the unzipped OBB files (not the `.obb` file) |
| `ThemePark-revival.apk` | Name of the new app file to create |
| `http://SERVER-ADDRESS:8086` | The server the app will connect to (see "Host a server") |

The files can be anywhere. Use full paths and quotes if a path has spaces, for
example `"/home/me/Downloads/Theme Park.apk"`. The build takes a few minutes and
ends with `wrote ThemePark-revival.apk`.

The first build creates your own signing key in `tools/themepark.keystore`.
Keep that file: an update only installs over the old app (keeping its data) if
it is signed with the same key.

### 5. Install on the phone

- Copy `ThemePark-revival.apk` to the phone and open it. Android asks you to
  allow "Install unknown apps" for the app you opened it with (Files, Chrome...).
- Or with a USB cable and adb: `adb install -r ThemePark-revival.apk`.
- The app is about 250 MB, because the game data is inside it. The phone does
  not need the OBB file.
- If the original EA Theme Park is installed, uninstall it first.

What the build changes: it replaces the game's 32-bit native libraries with
Java code (graphics, sound, login), puts the game data inside the APK, writes
the server address into the app and adds the Friends & Codes menu. See
`tools/build_port.py`.

## Host a server

The server is plain Python 3 with no extra packages. Anything that runs Python
works: your PC, a Raspberry Pi, a VPS or a free cloud VM.

### On your own PC (Linux, macOS or Windows)

Download this project, then in the project folder:

Linux / macOS:

```bash
TP_PORT=8086 TP_PUBLIC=http://YOUR-IP:8086 python3 server/server.py
```

Windows (PowerShell, with Python from python.org):

```powershell
$env:TP_PORT="8086"; $env:TP_PUBLIC="http://YOUR-IP:8086"; python server\server.py
```

- `YOUR-IP` is the address phones use to reach your PC:
  - players on your Wi-Fi: your PC's local address (Linux: `ip addr`,
    Windows: `ipconfig`, it looks like `192.168.1.20`);
  - players anywhere: your public IP (search "what is my IP"), and forward the
    port to your PC in your router.
- Allow the port in your PC's firewall.
- Build the app with exactly the same address: `http://YOUR-IP:8086`.
- The server runs while the window is open.

### On a VPS or cloud VM (any Ubuntu/Debian server, e.g. Oracle Cloud free tier)

The deploy script sets everything up from your PC over SSH.

1. Create the server and allow incoming TCP port 8086 in your provider's
   firewall (on Oracle: the subnet's Security List, Ingress rule, source
   `0.0.0.0/0`).
2. Copy `deploy/deploy.env.example` to `deploy/deploy.env` and fill in your
   server's address and SSH key.
3. Run:

   ```bash
   bash deploy/deploy_oracle.sh
   ```

   This needs SSH access with sudo. It copies the server, installs it as a
   `systemd` service called `themepark` (it starts again after a reboot) and
   opens port 8086 in the server's own firewall. Run it again to update; saved
   parks are kept.
4. Build the app with `http://YOUR-SERVER-IP:8086`.

### Ports

8086 is only the default; any port from 1024 to 65535 works. The same number
must be used in three places: the server (`TP_PORT` and `TP_PUBLIC`), the
address you build the app with, and the firewall. An app built for one port
cannot connect to a server on another port; build it again. The VPS deploy
script always uses 8086.

### Problems

| Problem | Fix |
|---|---|
| Build stops with `pattern not found` | Wrong game version. You need 4.4.92 (OBB `main.4004092...`). |
| Build says `d8`, `zipalign` or `apksigner` not found | Run the `export PATH=...` line from step 2 again. |
| Phone says "App not installed" | Uninstall the original EA Theme Park (or an app built with another key) first. |
| Game says it can't reach the server | The address in the app is wrong, the server is not running, or the port is blocked by a firewall/router. On the phone, open `http://SERVER-ADDRESS:8086/director/api/android/getDirectionByPackage` in the browser: it should show some text, not an error. |
| "Failed to download player save data" when visiting | The server is older than the app. Update the server. |

### Settings

`server/settings.json`:

| Setting | Meaning |
|---|---|
| `promoCodes` | Codes and their rewards, e.g. `"REVIVAL": {"cash": 10000, "tickets": 5}` |
| `timezone` | When a new day starts for the daily bonus (default `Europe/Prague`) |
| `startCash`, `startTickets` | Money and super tickets a new park starts with (default 20,000 and 10) |
| `upgradeCostMultiplier` | Multiplies every upgrade price (default 5; the game's own prices are very low) |
| `ticketPriceMultiplier` | Multiplies the super ticket price of premium (purple) items, at least 1 ticket (default 0.25) |
| `upgradeCostFixed` | Fixed upgrade prices by item id, e.g. the tutorial's Bouncy Castle (`3000`) and French Friend Fries (`4002`) at $50 |
| `easyMode` | `true` gives ticket-only items a cash price and every park 500,000 cash and 100 tickets once |

Restart the server after changing it.

### Data and backups

Everything is in `server/data/`:

- `parks/<player>.json`: one file per player, the whole park
- `state.json`: which phone owns which player (needed, or players get new
  empty parks)
- `requests.log`: request log (rotated at 20 MB, not included in backups)

To give a player a fresh start, rename their park file.

**Back up and move a server.** A backup is one `.tar.gz` file with both parts.
It works in every direction (VM to PC, PC to VM, old VM to new VM):

| Where the server runs | Save a backup | Load a backup |
|---|---|---|
| VPS / cloud VM | `bash deploy/backup.sh` | `bash deploy/restore.sh backups/<file>.tar.gz` |
| Your PC | `python3 tools/data.py export` | `python3 tools/data.py import backups/<file>.tar.gz` |

- Backups are saved in `backups/`. `python3 tools/data.py info <file>` shows
  which players are inside.
- Loading keeps the old data next to it (`data.before-restore-...` /
  `data.before-import-...`), so nothing is lost by mistake.
- On a PC, stop the server before `import`. On a new VM, run
  `deploy_oracle.sh` once before `restore.sh`.

**If the server's address changes** (new VM, new IP, new port), the apps still
point at the old address. Build the app again with the new address and install
it over the old one. Use the **same signing key** (`tools/themepark.keystore`):
then the update installs without losing anything, and every phone gets its own
player and park back. Keep a copy of that key file somewhere safe, and never
share it.

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
| `deploy/` | VPS deploy, backup and restore scripts |
| `tools/data.py` | Backup / restore for a server on a PC |

## Credits

- The game: Theme Park by EA and Progressive Media. This project is not affiliated
  with or endorsed by EA. It contains no game files; you need your own copy.
- Revival: AriCuteGirl. Built with the help of Claude (AI) for reverse
  engineering and code.

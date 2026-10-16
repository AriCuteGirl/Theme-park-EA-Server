# Theme Park (EA, Android) — revival research

APK: `com.eamobile.themepark_row` v4.5.88 (versionCode 4005088), built Sept 2014.
Developer code: Progressive Media (`dk.progressivemedia.*`), mostly Java, plus small native
libs `librflib.so` (graphics) and `libAudioLib.so`.

## 1. Game data is NOT in the APK
- The APK holds only code and wallpaper images. Art and data come from a Google Play
  expansion file: `Android/obb/com.eamobile.themepark_row/main.4005088.com.eamobile.themepark_row.obb`.
- `PMActivity.TryOpenZipResources()` first checks whether `assets/0.bfc` exists inside the APK.
  If it does, the game skips the OBB and loads everything from the APK. So the OBB contents can be
  baked into a patched APK.
- Without the OBB, the game opens `PMAADActivity`, which tries Google Play's downloader. That
  can't work any more because the app is delisted.
- **Blocker:** we need `main.4005088...obb`. An OBB from a different version (e.g. 4.4.92) may
  not match the code.

## 2. Server dependencies
| Service | URL / source | Purpose |
|---|---|---|
| Nimble Synergy director | `https://syn-dir.sn.eamobile.com` | EA account bootstrap, service URLs |
| Mayhem game server | `PMiPSP.GetMayhemURL()` (from director) | **stores the whole park**, server-authoritative |
| SKUM CDN | `http://cdn.skum.eamobile.com/skumasset/gameasset/themepark/mtx/timestamp.txt` | store catalogue cache |
| Facebook, PlayHaven, Google Analytics, Crashlytics | — | optional, can be stubbed |

The Mayhem client lives in `dk/progressivemedia/skeleton/h/by.java` (log tag `ThemeParkSoap`).
Every request sends `mayhemUserId`, `sessionKey`, `deviceID`, `userVersion`, `accounttype`
(`udid`/origin) and `themeuserid`. Responses are XML, and errors come back as `<error code= field= type=>`.

REST paths seen (89 request classes in `skeleton/h/`):
`themeuser/ create/ fullpark/ update/ cash/ xpprogress/ unlock/ slotlicense/ themeslot/
sell/ swap/ remove/ moveto/ setstate/ setbroke/ setparkoffice/ timers/ start/
incrementgametime/ userwentoffline/ hire/ hireahandyman/ removehiredhandyman/
alluserhiredhandymans/ switchhandymantorestingstate/ supertickets/ redeem/ onetimepurchase/
qaward/ eaward/ scriptvariables/ gesture/ locale/ musicvolume/ migratefrom/ checkversionandroid/`

The manifest also has an `enable_offline` meta-data flag (`skeleton/d/e.java:162`). It's worth
testing whether it makes the server unnecessary.

## 3. Plan
1. Get the matching OBB. Unzip it into `assets/` and rebuild and sign the APK. Test it in Waydroid
   (installed on this machine).
2. Try `enable_offline=true` in the manifest. If the game runs without the server, we're done.
3. Otherwise: point the director/Mayhem/CDN URLs at a local server (patch the strings in smali,
   http instead of https), then write a small Python server that implements the director plus
   the Mayhem endpoints above, saving each park to a local file.
4. Stub out IAP, Facebook and ads.

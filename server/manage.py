#!/usr/bin/env python3
"""Command-line admin tool for the Theme Park server (used by Server Manager).

Every command prints one JSON object. Errors: {"ok": false, "error": "..."}, exit code 1.
Works while the server runs or not. Files are written atomically (temp file + rename).

usage: manage.py [--root DIR] <command> [args]

  info                         game, version, number of players
  players                      all players (no session keys, no device ids)
  player <id>                  one player record (park shown as a summary)
  set <id> <field> <value>     change cash, superTickets or xpLevel (keeps <id>.json.bak)
  reset <id>                   fresh park; old save kept as <id>.json.old, friends kept
  settings                     read settings.json
  settings set <key> <json>    change one setting (restart the server afterwards)
  codes                        list promo codes
  codes add <CODE> <json>      add or change a code, e.g. '{"cash": 5000, "tickets": 2}'
  codes remove <CODE>          remove a code
  backup [file]                save data/ into a .tar.gz (same format as deploy/backup.sh)
  backups                      list the backups in backups/
  restore <file>               replace data/ with a backup; old data kept aside
  logs [lines]                 last lines of data/requests.log

--root is the folder with server.py (default: the folder of this file). Server Manager
passes it because it runs this script through "python3 -" over SSH.
"""
import json
import os
import shutil
import sys
import tarfile
import time

VERSION = "1.0.0"
GAME = "theme-park"

# Fields an admin may change with "set" (also listed in manager/game.json "currencies").
CURRENCIES = {
    "cash": (0, 2_000_000_000),
    "superTickets": (0, 1_000_000),
    "xpLevel": (1, 99),
}

# settings.json keys "settings set" accepts (manager/game.json "settings.fields").
SETTINGS_FIELDS = {
    "startCash": ("int", 0, 2_000_000_000),
    "startTickets": ("int", 0, 1_000_000),
    "upgradeCostMultiplier": ("float", 0.1, 100),
    "ticketPriceMultiplier": ("float", 0.05, 100),
    "easyMode": ("bool",),
    "easyStartCash": ("int", 0, 2_000_000_000),
    "easyStartTickets": ("int", 0, 1_000_000),
    "timezone": ("string",),
}

# Never shown: logins, sessions, phone ids.
SECRET_KEYS = {"deviceId", "eadeviceid", "sessions", "sessions2", "mayhem", "devices", "token"}


class Fail(Exception):
    pass


def out(obj, code=0):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.exit(code)


def write_json(path, obj, indent=1):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=indent)
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        if default is not None:
            return default
        raise Fail("file not found: %s" % os.path.basename(path))
    except ValueError:
        raise Fail("broken JSON in %s" % os.path.basename(path))


class Server:
    def __init__(self, root):
        self.root = os.path.abspath(os.path.expanduser(root))
        self.data = os.path.join(self.root, "data")
        self.parks = os.path.join(self.data, "parks")
        self.settings_file = os.path.join(self.root, "settings.json")
        self.backup_dir = os.path.join(self.root, "backups")

    # ---- players -------------------------------------------------------------
    def park_path(self, pid):
        if not pid.isdigit() or len(pid) > 20:
            raise Fail("player id must be a number")
        path = os.path.join(self.parks, pid + ".json")
        if not os.path.isfile(path):
            raise Fail("no player %s" % pid)
        return path

    def player_files(self):
        if not os.path.isdir(self.parks):
            return []
        return sorted(n for n in os.listdir(self.parks) if n.endswith(".json") and n[:-5].isdigit())

    @staticmethod
    def summary(u, pid):
        return {
            "id": str(u.get("userId") or pid),
            "name": u.get("name") or "Player %s" % pid[-4:],
            "level": u.get("xpLevel", 0),
            "cash": u.get("cash", 0),
            "superTickets": u.get("superTickets", 0),
            "lastLogin": u.get("userLastLogin", 0),
            "friends": len(u.get("friends", [])),
            "friendCode": u.get("friendCode"),
        }

    def players(self):
        result = []
        for name in self.player_files():
            pid = name[:-5]
            try:
                u = read_json(os.path.join(self.parks, name))
            except Fail:
                result.append({"id": pid, "name": "(unreadable save)", "broken": True})
                continue
            result.append(self.summary(u, pid))
        result.sort(key=lambda p: p.get("lastLogin") or 0, reverse=True)
        return result

    def player(self, pid):
        u = read_json(self.park_path(pid))
        rec = {k: v for k, v in u.items() if k not in SECRET_KEYS and k != "park"}
        park = u.get("park") or {}
        rec["park"] = {k: len(v) for k, v in park.items() if isinstance(v, (dict, list))}
        rec.update(self.summary(u, pid))
        return rec

    def set(self, pid, field, value):
        if field not in CURRENCIES:
            raise Fail("unknown field %r, allowed: %s" % (field, ", ".join(CURRENCIES)))
        try:
            value = int(value)
        except ValueError:
            raise Fail("value must be a whole number")
        lo, hi = CURRENCIES[field]
        if not lo <= value <= hi:
            raise Fail("%s must be between %d and %d" % (field, lo, hi))
        path = self.park_path(pid)
        u = read_json(path)
        if u.get("xpLevel", 0) < 1:
            raise Fail("this player has not started a park yet")
        old = u.get(field)
        shutil.copy2(path, path + ".bak")
        u[field] = value
        write_json(path, u)
        return {"old": old, "new": value, "backup": os.path.basename(path) + ".bak"}

    def reset(self, pid):
        path = self.park_path(pid)
        sys.path.insert(0, self.root)
        import game  # NEW_USER / PERSISTENT / empty_park, so the reset matches the server
        u = read_json(path)
        keep = {k: u[k] for k in game.PERSISTENT if k in u}
        fresh = dict(game.NEW_USER, **keep)
        fresh.update(themeUserId=pid, userId=pid, park=game.empty_park())
        os.replace(path, path + ".old")
        write_json(path, fresh)
        return {"kept": os.path.basename(path) + ".old", "keptFields": sorted(keep)}

    # ---- settings / codes ----------------------------------------------------
    def settings(self):
        return read_json(self.settings_file, {})

    def settings_set(self, key, raw):
        if key not in SETTINGS_FIELDS:
            raise Fail("unknown setting %r, allowed: %s" % (key, ", ".join(SETTINGS_FIELDS)))
        try:
            value = json.loads(raw)
        except ValueError:
            raise Fail("value must be JSON, e.g. 100, 0.5, true or \"Europe/Prague\"")
        spec = SETTINGS_FIELDS[key]
        kind = spec[0]
        if kind == "bool":
            if not isinstance(value, bool):
                raise Fail("%s must be true or false" % key)
        elif kind == "string":
            if not isinstance(value, str) or not value or len(value) > 64:
                raise Fail("%s must be a short text" % key)
            if key == "timezone":
                try:
                    from zoneinfo import ZoneInfo
                    ZoneInfo(value)
                except ImportError:
                    pass
                except Exception:
                    raise Fail("unknown time zone %r (example: Europe/Prague)" % value)
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise Fail("%s must be a number" % key)
            if kind == "int":
                if value != int(value):
                    raise Fail("%s must be a whole number" % key)
                value = int(value)
            else:
                value = float(value)
            if not spec[1] <= value <= spec[2]:
                raise Fail("%s must be between %s and %s" % (key, spec[1], spec[2]))
        s = self.settings()
        old = s.get(key)
        s[key] = value
        write_json(self.settings_file, s)
        return {"key": key, "old": old, "new": value, "restart": True}

    def codes(self):
        return self.settings().get("promoCodes", {})

    def codes_add(self, code, raw):
        code = code.strip().upper()
        if not code.isalnum() or len(code) > 20:
            raise Fail("a code is 1-20 letters or digits")
        try:
            reward = json.loads(raw)
        except ValueError:
            raise Fail('reward must be JSON, e.g. {"cash": 5000, "tickets": 2}')
        if not isinstance(reward, dict) or set(reward) - {"cash", "tickets"}:
            raise Fail("reward can only have cash and tickets")
        for k, v in reward.items():
            if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 2_000_000_000:
                raise Fail("%s must be a whole number, 0 or more" % k)
        reward = {"cash": reward.get("cash", 0), "tickets": reward.get("tickets", 0)}
        s = self.settings()
        s.setdefault("promoCodes", {})[code] = reward
        write_json(self.settings_file, s)
        return {"code": code, "reward": reward, "restart": True}

    def codes_remove(self, code):
        s = self.settings()
        codes = s.get("promoCodes", {})
        match = [k for k in codes if k.upper() == code.strip().upper()]
        if not match:
            raise Fail("no code %s" % code)
        for k in match:
            del codes[k]
        write_json(self.settings_file, s)
        return {"removed": match[0], "restart": True}

    # ---- backups ---------------------------------------------------------------
    def backup(self, dest=None):
        if not os.path.isfile(os.path.join(self.data, "state.json")):
            raise Fail("no server data in %s" % self.data)
        if dest:
            dest = os.path.abspath(os.path.expanduser(dest))
        else:
            dest = os.path.join(self.backup_dir, "themepark-data-%s.tar.gz" % time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        def skip_logs(t):
            return None if os.path.basename(t.name).startswith("requests.log") else t
        tmp = dest + ".part"
        with tarfile.open(tmp, "w:gz") as tar:
            tar.add(self.data, arcname="data", filter=skip_logs)
        os.chmod(tmp, 0o600)
        os.replace(tmp, dest)
        info = backup_info(dest)
        info.update(file=dest, size=os.path.getsize(dest))
        return info

    def backups(self):
        if not os.path.isdir(self.backup_dir):
            return []
        items = []
        for n in os.listdir(self.backup_dir):
            if n.endswith(".tar.gz"):
                p = os.path.join(self.backup_dir, n)
                st = os.stat(p)
                items.append({"file": p, "name": n, "size": st.st_size, "time": int(st.st_mtime)})
        items.sort(key=lambda b: b["time"], reverse=True)
        return items

    def restore(self, src):
        src = os.path.abspath(os.path.expanduser(src))
        info = backup_info(src)
        kept = None
        with tarfile.open(src) as tar:
            members = safe_members(tar)
            if os.path.exists(self.data):
                kept = self.data + ".before-restore-" + time.strftime("%Y%m%d-%H%M%S")
                shutil.move(self.data, kept)
            tar.extractall(self.root, members=members)
        return {"kept": kept, "players": info["players"]}

    def logs(self, lines):
        path = os.path.join(self.data, "requests.log")
        if not os.path.isfile(path):
            return []
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 200 * lines))
            text = f.read().decode("utf-8", "replace")
        return text.splitlines()[-lines:]

    def info(self):
        return {"game": GAME, "version": VERSION, "players": len(self.player_files()),
                "data_dir": self.data, "settings": os.path.isfile(self.settings_file),
                "python": "%d.%d.%d" % sys.version_info[:3]}


def safe_members(tar):
    members = tar.getmembers()
    for m in members:
        if (m.name != "data" and not m.name.startswith("data/")) or ".." in m.name.split("/") \
                or m.name.startswith("/") or not (m.isfile() or m.isdir()):
            raise Fail("unexpected entry in backup: %s" % m.name)
    return members


def backup_info(path):
    if not os.path.isfile(path):
        raise Fail("backup not found: %s" % path)
    try:
        with tarfile.open(path) as tar:
            names = tar.getnames()
            if "data/state.json" not in names:
                raise Fail("not a Theme Park backup (no data/state.json)")
            safe_members(tar)
            parks = [n for n in names if n.startswith("data/parks/") and n.endswith(".json")]
    except tarfile.TarError as e:
        raise Fail("cannot read backup: %s" % e)
    return {"players": len(parks)}


def main(argv):
    me = globals().get("__file__") or ""
    root = os.path.dirname(os.path.abspath(me)) if os.path.isfile(me) else None
    if len(argv) >= 2 and argv[0] == "--root":
        root, argv = argv[1], argv[2:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        out({"ok": True, "help": __doc__})
    if not root or not os.path.isdir(os.path.expanduser(root)):
        raise Fail("server folder not found (use --root DIR): %s" % (root or "not given"))
    srv = Server(root)
    cmd, args = argv[0], argv[1:]

    def need(n, usage):
        if len(args) < n:
            raise Fail("usage: manage.py " + usage)

    if cmd == "info":
        return srv.info()
    if cmd == "players":
        return {"players": srv.players()}
    if cmd == "player":
        need(1, "player <id>")
        return {"player": srv.player(args[0])}
    if cmd == "set":
        need(3, "set <id> <field> <value>")
        return srv.set(*args[:3])
    if cmd == "reset":
        need(1, "reset <id>")
        return srv.reset(args[0])
    if cmd == "settings":
        if args and args[0] == "set":
            need(3, "settings set <key> <json-value>")
            return srv.settings_set(args[1], args[2])
        return {"settings": srv.settings()}
    if cmd == "codes":
        if args and args[0] == "add":
            need(3, "codes add <CODE> <json-reward>")
            return srv.codes_add(args[1], args[2])
        if args and args[0] == "remove":
            need(2, "codes remove <CODE>")
            return srv.codes_remove(args[1])
        return {"codes": srv.codes()}
    if cmd == "backup":
        return srv.backup(args[0] if args else None)
    if cmd == "backups":
        return {"backups": srv.backups()}
    if cmd == "restore":
        need(1, "restore <file>")
        return srv.restore(args[0])
    if cmd == "logs":
        n = int(args[0]) if args and args[0].isdigit() else 100
        return {"lines": srv.logs(min(max(n, 1), 2000))}
    raise Fail("unknown command %r (try: manage.py help)" % cmd)


if __name__ == "__main__":
    try:
        result = main(sys.argv[1:])
    except Fail as e:
        out({"ok": False, "error": str(e)}, 1)
    except Exception as e:  # never print a traceback with paths/secrets to the GUI
        out({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, 1)
    result = dict(ok=True, **result)
    out(result)

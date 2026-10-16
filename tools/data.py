#!/usr/bin/env python3
"""Back up and move a Theme Park server's data (parks, logins, friends).

usage: data.py export [backup.tar.gz]   save server/data into one file
       data.py import <backup.tar.gz>   replace server/data with a backup
       data.py info <backup.tar.gz>     show what a backup contains

A backup holds data/parks/*.json (one park per player) and data/state.json
(which phone owns which player). Both are needed, or players get new empty
parks. Stop the server before importing. The same files work with
deploy/backup.sh and deploy/restore.sh (VM).
"""
import json
import os
import shutil
import sys
import tarfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "server")
DATA = os.path.join(SERVER, "data")


def info(path):
    with tarfile.open(path) as tar:
        names = tar.getnames()
        parks = [n for n in names if n.startswith("data/parks/") and n.endswith(".json")]
        if "data/state.json" not in names:
            sys.exit("not a Theme Park backup (no data/state.json): %s" % path)
        state = json.load(tar.extractfile("data/state.json"))
        players = []
        for n in parks:
            try:
                u = json.load(tar.extractfile(n))
                players.append("%s (%s, level %s, $%s)" % (
                    u.get("userId", "?"), u.get("name") or "no name", u.get("xpLevel"), u.get("cash")))
            except ValueError:
                players.append(n + " (unreadable)")
    print("%s: %d player(s), %d device(s)" % (path, len(parks), len(state.get("devices", {}))))
    for p in players:
        print("  " + p)


def export(out):
    if not os.path.exists(os.path.join(DATA, "state.json")):
        sys.exit("no server data in %s" % DATA)
    out = out or os.path.join(ROOT, "backups", "themepark-data-%s.tar.gz" % time.strftime("%Y%m%d-%H%M"))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    def skip_logs(t):
        return None if os.path.basename(t.name).startswith("requests.log") else t
    with tarfile.open(out, "w:gz") as tar:
        tar.add(DATA, arcname="data", filter=skip_logs)
    print("saved", out)
    info(out)


def safe_members(tar):
    for m in tar.getmembers():
        if (m.name != "data" and not m.name.startswith("data/")) or ".." in m.name.split("/") \
                or not (m.isfile() or m.isdir()):
            sys.exit("refusing unexpected entry in backup: %s" % m.name)
        yield m


def import_(path):
    info(path)
    answer = input("Replace %s with this backup? Stop the server first. [y/N] " % DATA)
    if answer.strip().lower() != "y":
        sys.exit("cancelled")
    if os.path.exists(DATA):
        keep = DATA + ".before-import-" + time.strftime("%Y%m%d-%H%M%S")
        shutil.move(DATA, keep)
        print("old data kept in", keep)
    with tarfile.open(path) as tar:
        tar.extractall(SERVER, members=list(safe_members(tar)))
    print("imported into", DATA)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("export", "import", "info"):
        sys.exit(__doc__)
    cmd, arg = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    if cmd == "export":
        export(arg)
    elif arg is None:
        sys.exit(__doc__)
    elif cmd == "import":
        import_(arg)
    else:
        info(arg)


if __name__ == "__main__":
    main()

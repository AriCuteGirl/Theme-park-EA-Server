#!/usr/bin/env python3
"""Local replacement for the EA servers used by Theme Park (Android, 4.4.92).

Implements the Synergy director/user endpoints and the Mayhem login, and logs
every request it sees so the remaining game endpoints can be filled in.
"""
import json
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game  # noqa: E402

HOST = os.environ.get("TP_HOST", "0.0.0.0")
PORT = int(os.environ.get("TP_PORT", "8086"))
# Address the game uses to reach us (the waydroid0 bridge by default).
PUBLIC = os.environ.get("TP_PUBLIC", "http://192.168.240.1:%d" % PORT)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOG_FILE = os.path.join(DATA_DIR, "requests.log")

os.makedirs(DATA_DIR, exist_ok=True)
STATE_FILE = os.path.join(DATA_DIR, "state.json")


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"next_uid": 1000000001, "devices": {}, "mayhem": {}}


def save_state():
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(STATE, f, indent=1)
    os.replace(tmp, STATE_FILE)


STATE = load_state()
# Sessions from before device-checked logins (v1) are no longer accepted.
STATE.pop("sessions", None)
STATE.setdefault("sessions2", {})

MAX_BODY = 512 * 1024
MAX_LOG = 20 * 1024 * 1024
# One request at a time touches the park files.
GAME_LOCK = threading.Lock()
# Game paths that are fine without a login.
PUBLIC_GAME = ("serverload/", "checkversionandroid/", "locale/")


def director():
    return {
        "resultCode": 0,
        "serverApiVersion": "1.0.0",
        "DMGId": 0,
        "hwId": 1,
        "sellId": 1,
        "productId": 1,
        "packageId": "com.eamobile.themepark_row",
        "mayhemGameCode": "themepark",
        "facebookAppId": "0",
        "appUpgrade": 0,
        "telemetryFreq": 0,
        "pollIntervals": [{"key": "badgePollInterval", "value": "300"}],
        "serverData": [
            {"key": "synergy.user", "value": PUBLIC},
            {"key": "synergy.product", "value": PUBLIC},
            {"key": "synergy.drm", "value": PUBLIC},
            {"key": "synergy.tracking", "value": PUBLIC},
            {"key": "synergy.m2u", "value": PUBLIC},
            {"key": "synergy.s2s", "value": PUBLIC},
            {"key": "synergy.cipgl", "value": PUBLIC},
            {"key": "mayhem.url", "value": PUBLIC},
            {"key": "origincasualapp.url", "value": PUBLIC},
            {"key": "origincasualserver.url", "value": PUBLIC},
            {"key": "friends.url", "value": PUBLIC},
            {"key": "avatars.url", "value": PUBLIC},
            {"key": "akamai.url", "value": PUBLIC},
            {"key": "dmg.url", "value": PUBLIC},
        ],
    }


def new_uid():
    uid = STATE["next_uid"]
    STATE["next_uid"] += 1
    return uid


def known_uid(app_uid):
    """True if app_uid was handed out by getAnonUid to some device."""
    return any(str(d.get("uid")) == str(app_uid) for d in STATE["devices"].values())


def session_ok(headers):
    mid = headers.get("mh_uid") or ""
    sess = STATE["sessions2"].get(headers.get("mh_session_key") or "")
    return bool(mid) and sess is not None and sess.get("mid") == mid


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 30

    def log_message(self, fmt, *args):
        pass

    def _log(self, body):
        line = "%s %s %s %s" % (time.strftime("%H:%M:%S"), self.command, self.path,
                                body[:2000].decode("utf-8", "replace") if body else "")
        if "/mh/" in self.path:
            hdr = {k: v for k, v in self.headers.items()
                   if k.lower() in ("mh_uid", "tp_cash", "tp_tickets", "tp_level", "tp_xp", "user-agent")}
            line += "\n   headers: " + repr(hdr)
        print(line, flush=True)
        try:
            if os.path.getsize(LOG_FILE) > MAX_LOG:
                os.replace(LOG_FILE, LOG_FILE + ".1")
        except OSError:
            pass
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")

    def _send(self, code, payload, ctype):
        data = payload if isinstance(payload, bytes) else payload.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        print("   -> %d %s" % (code, data[:300].decode("utf-8", "replace")), flush=True)

    def json(self, obj, code=200):
        self._send(code, json.dumps(obj), "application/json")

    def xml(self, text, code=200):
        self._send(code, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + text,
                   "application/xml")

    def handle_any(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self.close_connection = True
            return self.xml("<error code=\"413\" type=\"TOO_LARGE\" field=\"body\"/>", 413)
        body = self.rfile.read(length) if length else b""
        self._log(body)
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        path = url.path

        if path.startswith(game.BASE):
            if not path[len(game.BASE):].startswith(PUBLIC_GAME) and not session_ok(self.headers):
                return self.xml("<error code=\"401\" type=\"BAD_SESSION\" field=\"mh_session_key\"/>", 401)
            with GAME_LOCK:
                res = game.handle(self.command, path, q, self.headers, body)
            return self.xml(res[1], res[0])

        if path.endswith("/director/api/android/getDirectionByPackage"):
            return self.json(director())

        if path.endswith("/user/api/android/getDeviceID"):
            dev = q.get("androidId") or q.get("deviceId") or "dev"
            if dev not in STATE["devices"]:
                STATE["devices"][dev] = {"deviceId": uuid.uuid4().hex, "uid": None}
                save_state()
            return self.json({"resultCode": 0, "serverApiVersion": "1.0.0",
                              "deviceId": STATE["devices"][dev]["deviceId"]})

        if path.endswith("/user/api/android/validateDeviceID"):
            return self.json({"resultCode": 0, "serverApiVersion": "1.0.0",
                              "deviceId": q.get("eadeviceid") or q.get("deviceId", "")})

        if path.endswith("/user/api/android/getAnonUid"):
            key = q.get("eadeviceid") or q.get("deviceId") or q.get("androidId") or "anon"
            rec = STATE["devices"].setdefault(key, {"deviceId": key, "uid": None})
            if not rec.get("uid"):
                rec["uid"] = new_uid()
                save_state()
            return self.json({"resultCode": 0, "serverApiVersion": "1.0.0", "uid": rec["uid"]})

        if path.endswith("/user/api/android/getAlrId"):
            return self.json({"resultCode": 0, "serverApiVersion": "1.0.0", "alrId": 0})

        if path.endswith("/user/api/core/isFacebookEnabled"):
            return self.json({"resultCode": 0, "serverApiVersion": "1.0.0", "enabled": False})

        if path.startswith("/m2u/") or path.startswith("/user/api/core/") or "/tracking" in path:
            return self.json({"resultCode": 0, "serverApiVersion": "1.0.0"})

        # Mayhem login: create/lookup a Mayhem user for an application user id.
        if path.rstrip("/").endswith("/mh/users"):
            app_uid = q.get("applicationUserId", "anon")
            if not known_uid(app_uid):
                return self.xml("<error code=\"404\" type=\"NO_SUCH_USER\" field=\"applicationUserId\"/>", 404)
            mid = STATE["mayhem"].get(app_uid)
            if not mid:
                mid = str(new_uid())
                STATE["mayhem"][app_uid] = mid
                save_state()
            return self.xml("<Resources><URI>/users/%s</URI></Resources>" % mid)

        # Map application (Synergy) user ids to Mayhem user ids.
        if path.rstrip("/").endswith("/mh/userlist"):
            # The client fires this before it has finished storing the login
            # result; answering instantly makes it fail, so reply a bit later.
            time.sleep(float(os.environ.get("TP_USERLIST_DELAY", "1.0")))
            form = {k: v[0] for k, v in parse_qs(body.decode("utf-8", "replace")).items()}
            app = form.get("application", "synergy")
            ids = [i for i in (form.get("applicationUserIds") or q.get("applicationUserIds", "")).split(",") if i]
            out = []
            for app_uid in ids:
                if not known_uid(app_uid):
                    continue
                mid = STATE["mayhem"].get(app_uid)
                if not mid:
                    mid = str(new_uid())
                    STATE["mayhem"][app_uid] = mid
                    save_state()
                out.append("<User><mayhemUserId>%s</mayhemUserId><applicationUserId>%s"
                           "</applicationUserId><application>%s</application></User>"
                           % (mid, app_uid, app))
            return self.xml("<Resources><Users>%s</Users></Resources>" % "".join(out))

        if "/mh/users/" in path and path.rstrip("/").endswith("/token"):
            mid = path.rstrip("/").split("/")[-2]
            # Only the device that owns this player gets a session: the client
            # proves it with the eadeviceid getDeviceID gave it.
            dev = STATE["devices"].get(q.get("eadeviceid") or "")
            if not dev or STATE["mayhem"].get(str(dev.get("uid"))) != mid:
                return self.xml("<error code=\"403\" type=\"NOT_YOUR_USER\" field=\"token\"/>", 403)
            key = uuid.uuid4().hex
            sessions = STATE["sessions2"]
            for old in [k for k, v in sessions.items() if v.get("mid") == mid]:
                del sessions[old]
            sessions[key] = {"mid": mid, "t": int(time.time())}
            save_state()
            # expirationDate is a duration, "days:hours:minutes:seconds".
            return self.xml("<Token><sessionKey>%s</sessionKey>"
                            "<expirationDate>365:00:00:00</expirationDate></Token>" % key)

        return self.xml("<error code=\"404\" type=\"NOT_IMPLEMENTED\" field=\"%s\"/>" % path, 404)

    do_GET = do_POST = do_PUT = do_DELETE = handle_any


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Theme Park server on %s:%d (public %s)" % (HOST, PORT, PUBLIC), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()

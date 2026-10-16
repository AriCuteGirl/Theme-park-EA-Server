"""Theme Park game endpoints (Mayhem paths under /mh/games/themepark/).

The client (dk.progressivemedia.skeleton.h.*) sends the player's Mayhem id in the
mh_uid header and parses XML replies; <error code= type= field=> means failure.

The park is saved per player in data/parks/<mayhemId>.json. Actions update it and
fullpark/ rebuilds the XML the client loads (dk.progressivemedia.skeleton.h.ak).
Cash/tickets/level/xp are not recomputed here: the patched client reports its own
values in tp_* headers on every request (com.tprevival.State).
"""
import json
import os
import time
from urllib.parse import parse_qs, unquote

BASE = "/mh/games/themepark/"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "parks")
os.makedirs(DATA_DIR, exist_ok=True)

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog.json")) as _f:
    CATALOG = json.load(_f)
ENTITIES = {e["entityId"]: e for e in CATALOG}

# server/settings.json: easy mode switch (edit it, then redeploy).
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")) as _f:
        SETTINGS = json.load(_f)
except (OSError, ValueError):
    SETTINGS = {}
EASY = bool(SETTINGS.get("easyMode"))
EASY_CASH = int(SETTINGS.get("easyStartCash", 500000))
EASY_TICKETS = int(SETTINGS.get("easyStartTickets", 100))


def _easy_entity(e):
    """Easy mode: ticket-only items (price 0) get a cash price instead.

    The client treats an item as ticket-only when its cash price is 0
    (dk.progressivemedia.skeleton.c.a.b.e()). Cash items sell for about 1/5 of
    their price, so sellPrice * easyTicketToCash gives a matching cash price.
    """
    if not EASY or e.get("price", 0) > 0 or e.get("priceSuperTickets", 0) <= 0:
        return e
    e = dict(e)
    e["price"] = max(100, int(e.get("sellPrice", 0)) * int(SETTINGS.get("easyTicketToCash", 5)))
    e["priceSuperTickets"] = 0
    return e


def _xml_obj(tag, obj):
    return "<%s>%s</%s>" % (tag, "".join("<%s>%s</%s>" % (k, v, k) for k, v in obj.items()), tag)


# Ride/shop/decoration definitions rebuilt from the client's own tables
# (tools/catalog.py); EA's server sent these with every full park.
CATALOG_XML = "".join(_xml_obj("Entity", {k: v for k, v in _easy_entity(e).items()
                                          if not k.startswith("_")})
                      for e in CATALOG)

NEW_USER = {
    "xpLevel": 0,
    "xpProgress": 0,
    "cash": 0,
    "superTickets": 0,
    "userLastLogin": 0,
    "dailyBonusCash": 0,
    "dailyBonusSuperTickets": 0,
    "dailyBonusVoucher": -1,
    "userDaysInARow": 0,
    "remainingFriendInvites": 0,
}

# A freshly wiped park (after destroydata). xpLevel -1 tells the client the save
# hasn't been started; it then calls startgame and sets up the tutorial itself.
# Values follow the client's built-in defaults (StartingGrindCurrency,
# TutorialTickets) since EA's originals are gone.
NEW_PARK_USER = dict(NEW_USER, xpLevel=-1, cash=100000, superTickets=10,
                     unlockStates=0, musicVolume=100, sfxVolume=100,
                     parkOfficeString="-2,-2,-1,-2,-2,", scriptVariables="", userLastLvlUp=0,
                     friendInteractionDataString="")

THEMEUSER_FIELDS = ["themeUserId", "userId", "xpLevel", "xpProgress", "cash", "superTickets",
                    "userLastLogin", "userLastLvlUp", "dailyBonusCash", "dailyBonusSuperTickets",
                    "dailyBonusVoucher", "userDaysInARow", "remainingFriendInvites",
                    "unlockStates", "musicVolume", "sfxVolume", "parkOfficeString",
                    "scriptVariables", "friendInteractionDataString"]

# unlockStates bits as read by the client (ak.java / d.d): unlock/<name> -> bit
UNLOCK_BITS = {"microactions": 1, "upgrades": 2, "parkoffice": 4, "sell": 8}

# Tutorial scripts lock/unlock the build menus by plot size:
# unlock/<l|u><ridemenu|shopmenu><all|small|medium|large>/themeuser/ ("l" locks).
# Bits as set by script ops 62/63 (skeleton.g.a) and read back in ak.java.
MENU_BITS = {
    "ridemenu": {"small": 512, "medium": 4194304, "large": 16777216},
    "shopmenu": {"small": 256, "medium": 2097152, "large": 8388608},
}
for _sizes in MENU_BITS.values():
    _sizes["all"] = sum(_sizes.values())


def menu_lock_bits(name):
    """'lshopmenuall' -> (True, 10486016); None if not a menu lock name."""
    if len(name) < 2 or name[0] not in "lu":
        return None
    for menu, sizes in MENU_BITS.items():
        if name[1:].startswith(menu) and name[1 + len(menu):] in sizes:
            return name[0] == "l", sizes[name[1 + len(menu):]]
    return None


# Actions whose effect lives only in the client (cash/tickets/xp arrive via the
# tp_* headers anyway), so a plain OK is the whole reply.
STATELESS = {"gesture", "emptytrash", "cleanuppuke", "incrementgametime", "xpprogress",
             "cash", "supertickets", "sentinvite", "tapjoy", "getallfreepurchases"}

# Territory 25 is the starting area (the only one with no unlock condition in
# the client's themeSlots table).
START_TERRITORY = 25


def _path(mid):
    return os.path.join(DATA_DIR, "%s.json" % "".join(c for c in mid if c.isalnum()))


def empty_park():
    return {"WorldInstance": {}, "Quest": {}, "EntityLicense": {}, "SavedScript": [],
            "StaffMember": {}, "ThemeStatue": {}, "SlotLicense": {}, "OneTimePurchase": {},
            "AttractionVoucher": []}


def load_user(mid):
    try:
        with open(_path(mid)) as f:
            user = json.load(f)
    except (OSError, ValueError):
        user = dict(NEW_USER)
        user["themeUserId"] = mid
        user["userId"] = mid
        user["park"] = empty_park()
        return user
    if user.get("xpLevel", 0) != 0:
        for k, v in NEW_PARK_USER.items():
            user.setdefault(k, v)
        if not user.get("parkOfficeString"):
            user["parkOfficeString"] = NEW_PARK_USER["parkOfficeString"]
    park = user.get("park")
    if not isinstance(park, dict) or not isinstance(park.get("WorldInstance"), dict):
        old = park if isinstance(park, dict) else {}
        park = empty_park()
        for lic in old.get("SlotLicense", []):
            park["SlotLicense"]["%s:%s" % (lic["isThemeSlot"], lic["localSlotId"])] = lic
        user["park"] = park
    for k, v in empty_park().items():
        park.setdefault(k, v)
    return user


def save_user(mid, user):
    tmp = _path(mid) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(user, f, indent=1)
    os.replace(tmp, _path(mid))


def give_easy_bonus(user):
    """Easy mode: raise a park's cash/tickets once to the easy starting amounts.

    The client takes cash and tickets from the ThemeUser reply when it loads
    the park (dk.progressivemedia.skeleton.d.d.a(ak)), so this reaches new and
    existing parks alike.
    """
    if not EASY or user.get("easyBonus") or user.get("xpLevel", 0) < 1:
        return False
    user["cash"] = max(user.get("cash", 0), EASY_CASH)
    user["superTickets"] = max(user.get("superTickets", 0), EASY_TICKETS)
    user["easyBonus"] = 1
    return True


def themeuser_xml(user):
    return "<ThemeUser>%s</ThemeUser>" % "".join(
        "<%s>%s</%s>" % (k, user.get(k, ""), k) for k in THEMEUSER_FIELDS if k in user)


# ---- world instances (rides, shops, decorations) -------------------------------
# objectState: 1 building, 2 built (waiting to open), 3 upgrading, 4 open.
# Timers are stored as absolute end times and sent as seconds remaining, so
# they keep running while the game is closed.

def _entity_secs(entity_id, key):
    try:
        return int(ENTITIES.get(str(entity_id), {}).get(key, 0))
    except (TypeError, ValueError):
        return 0


def worldinstance_xml(wi, now):
    state = wi.get("objectState", 4)
    out = {"localId": wi["localId"], "slotId": wi.get("slotId", -1),
           "instanceType": wi.get("instanceType", 0), "entityId": wi.get("entityId", ""),
           "nurtureClicks": wi.get("nurtureClicks", 0), "upgradeLevel": wi.get("upgradeLevel", 0),
           "buildTime": 0, "nurtureTime": 0, "upgradeTime": 0,
           "nurturePauseTime": 0, "upgradePauseTime": 0, "buildPauseTime": 0}
    if state == 1:
        left = int(wi.get("buildEnd", 0) - now)
        if left <= 0:
            # the client turns state 1 with a negative build time into "built"
            out["buildTime"] = -1
        else:
            out["buildTime"] = left
    elif state == 2:
        out["buildTime"] = -1
    elif state == 3:
        out["upgradeTime"] = max(0, int(wi.get("upgradeEnd", 0) - now))
    elif state == 4:
        if wi.get("pausedNurture") is not None:
            out["nurturePauseTime"] = max(1, int(wi["pausedNurture"]))
        else:
            out["nurtureTime"] = max(0, int(wi.get("nurtureEnd", 0) - now))
    out["objectState"] = state
    return _xml_obj("WorldInstance", out)


def fullpark_xml(user):
    now = time.time()
    park = user["park"]
    parts = [CATALOG_XML]
    for wi in park["WorldInstance"].values():
        parts.append(worldinstance_xml(wi, now))
    for q in park["Quest"].values():
        parts.append(_xml_obj("Quest", q))
    for lic in park["EntityLicense"].values():
        parts.append(_xml_obj("EntityLicense", lic))
    for sc in park["SavedScript"]:
        parts.append(_xml_obj("SavedScript", sc))
    for st in park["StaffMember"].values():
        parts.append(_xml_obj("StaffMember", st))
    for ts in park["ThemeStatue"].values():
        parts.append(_xml_obj("ThemeStatue", ts))
    for sl in park["SlotLicense"].values():
        parts.append(_xml_obj("SlotLicense", sl))
    for otp in park["OneTimePurchase"].values():
        parts.append(_xml_obj("OneTimePurchase", otp))
    for idx in park["AttractionVoucher"]:
        parts.append(_xml_obj("AttractionVoucher", {"attractionIndex": idx}))
    return "<Resources>%s</Resources>" % "".join(parts)


def parse_scripts(body):
    """SaveScriptState body: per script 'data;offset;paused;pauseType;pauseData;time;param#'."""
    scripts = []
    for chunk in body.split("#"):
        f = chunk.strip().split(";")
        if len(f) < 7:
            continue
        scripts.append({"scriptData": f[0], "offset": f[1], "paused": f[2], "pauseType": f[3],
                        "pauseData": f[4], "time": f[5], "param": f[6]})
    return scripts


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def apply_reported_state(user, headers):
    """Store the client's own cash/tickets/level/xp (tp_* headers)."""
    level = _int(headers.get("tp_level"), -1)
    cash = _int(headers.get("tp_cash"), -1)
    if level < 1 or cash < 0 or user.get("xpLevel", 0) < 1:
        return False
    if level > user.get("xpLevel", 0):
        user["userLastLvlUp"] = int(time.time())
    user["xpLevel"] = level
    user["cash"] = cash
    user["superTickets"] = max(0, _int(headers.get("tp_tickets"), user.get("superTickets", 0)))
    user["xpProgress"] = max(0, _int(headers.get("tp_xp"), user.get("xpProgress", 0)))
    return True


def handle(method, path, query, headers, body):
    """Return (status, xml_without_declaration) or None if not a game path."""
    if not path.startswith(BASE):
        return None
    rest = path[len(BASE):]
    seg = [unquote(s) for s in rest.strip("/").split("/")]
    mid = headers.get("mh_uid") or "anon"
    user = load_user(mid)
    park = user["park"]
    text = body.decode("utf-8", "replace") if body else ""
    form = {k: v[0] for k, v in parse_qs(text.replace("\n", "")).items()} if "=" in text else {}
    now = time.time()
    ok = (200, "<Resources></Resources>")

    dirty = apply_reported_state(user, headers)

    def done():
        save_user(mid, user)
        return ok

    if seg[0] == "serverload":
        return 200, "<Resources><serverLoad>0</serverLoad></Resources>"

    if seg[0] == "checkversionandroid":
        return 200, "<Resources><version>ok</version></Resources>"

    # themeuser/<mayhemId>: does a park exist? themeuser/: the logged-in user.
    if seg[0] == "themeuser":
        arg = seg[1] if len(seg) > 1 else ""
        if arg:
            other = load_user(arg)
            if other.get("xpLevel", 0) > 0:
                return 200, "<Resources>%s</Resources>" % themeuser_xml(other)
            return 200, "<Resources></Resources>"
        user["userLastLogin"] = int(now)
        give_easy_bonus(user)
        if user.get("xpLevel", 0) != 0:
            save_user(mid, user)
        return 200, themeuser_xml(user)

    # Wipes the player's park before a new game starts.
    if seg[0] == "destroydata":
        user = dict(NEW_PARK_USER)
        user["themeUserId"] = mid
        user["userId"] = mid
        user["userLastLogin"] = int(now)
        user["park"] = empty_park()
        user["park"]["SlotLicense"]["1:%d" % START_TERRITORY] = {
            "isThemeSlot": 1, "isTaken": 0, "localSlotId": START_TERRITORY}
        save_user(mid, user)
        return ok

    if seg[0] == "startgame":
        user["xpLevel"] = 1
        return done()

    # Dynamic images (loading screen etc.): the client has none cached (-1) and only
    # downloads when our version is newer, so -2 keeps the built-in artwork.
    if "imagedata" in seg:
        return 200, "<ImageData><imageName>%s</imageName><version>-2</version></ImageData>" % seg[-1]

    if seg[0] == "fullpark":
        if dirty:
            save_user(mid, user)
        return 200, fullpark_xml(user)

    # ---- profile ----------------------------------------------------------------
    if seg[0] == "setparkoffice" and len(seg) > 1:
        user["parkOfficeString"] = seg[1]
        return done()
    if seg[0] == "scriptvariables" and len(seg) > 1:
        user["scriptVariables"] = seg[1]
        return done()
    if seg[0] == "musicvolume" and len(seg) > 3:
        user["musicVolume"], user["sfxVolume"] = _int(seg[1], 100), _int(seg[3], 100)
        return done()
    if seg[0] == "unlock" and len(seg) > 1 and seg[1] in UNLOCK_BITS:
        user["unlockStates"] = user.get("unlockStates", 0) | UNLOCK_BITS[seg[1]]
        return done()
    if seg[0] == "unlock" and len(seg) > 1 and menu_lock_bits(seg[1]):
        lock, bits = menu_lock_bits(seg[1])
        states = user.get("unlockStates", 0)
        user["unlockStates"] = states | bits if lock else states & ~bits
        return done()
    if seg[0] in STATELESS:
        if dirty:
            save_user(mid, user)
        return ok
    if seg[0] == "setfriendinteraction":
        user["friendInteractionDataString"] = text
        return done()

    # ---- scripts and quests -------------------------------------------------------
    if seg[0] == "savedscript":
        park["SavedScript"] = parse_scripts(text)
        return done()
    if len(seg) >= 3 and seg[0] == "start" and seg[-1] == "quest":
        for qid in seg[1].split(","):
            if qid:
                park["Quest"].setdefault(qid, {"localQuestID": qid, "questState": 0,
                                               "param1": 0, "param2": 0, "param3": 0})
        return done()
    if len(seg) >= 5 and seg[0] == "setstate" and seg[-1] == "quest":
        for qid, st in zip(seg[1].split(","), seg[3].split(",")):
            q = park["Quest"].setdefault(qid, {"localQuestID": qid, "param1": 0, "param2": 0, "param3": 0})
            q["questState"] = _int(st)
        return done()
    if len(seg) >= 9 and seg[0] == "update" and seg[-1] == "quest":
        q = park["Quest"].setdefault(seg[1], {"localQuestID": seg[1], "questState": 0})
        q["param1"], q["param2"], q["param3"] = _int(seg[3]), _int(seg[5]), _int(seg[7])
        return done()

    # ---- licences, plots, purchases -------------------------------------------------
    if seg[0] in ("qaward", "eaward") and len(seg) >= 4:
        for eid, itype in zip(seg[1].split(","), seg[3].split(",")):
            if eid and eid != "0":
                park["EntityLicense"][eid] = {"entityId": eid, "instanceType": _int(itype)}
        return done()
    if seg[0] == "themeslot" and len(seg) > 1:
        park["SlotLicense"]["1:%s" % seg[1]] = {"isThemeSlot": 1, "isTaken": 0, "localSlotId": seg[1]}
        return done()
    if seg[0] == "slotlicense" and len(seg) > 1:
        for sid in seg[1].split(","):
            if sid:
                park["SlotLicense"]["0:%s" % sid] = {"isThemeSlot": 0, "isTaken": 0, "localSlotId": sid}
        return done()
    if seg[0] == "onetimepurchase" and len(seg) > 1:
        park["OneTimePurchase"][seg[1]] = {"oneTimePurchaseId": seg[1], "entityId": seg[1]}
        return done()

    # ---- staff ------------------------------------------------------------------------
    if seg[0] == "hire" and len(seg) >= 3:
        park["StaffMember"][seg[1]] = {"positionId": seg[1],
                                       "employeeId": seg[3] if len(seg) > 3 else "-1"}
        return done()
    if seg[0] == "remove" and len(seg) >= 3 and seg[2] == "staffmember":
        park["StaffMember"].pop(seg[1], None)
        return done()

    # ---- theme statues ------------------------------------------------------------------
    if seg[0] == "create" and len(seg) >= 5 and seg[3] == "themestatue":
        park["ThemeStatue"][seg[1]] = {"localId": seg[1], "slotId": seg[2], "entityId": seg[4]}
        return done()
    if seg[0] == "swap" and len(seg) >= 4 and seg[2] == "themestatue":
        ts = park["ThemeStatue"].get(seg[1])
        if ts:
            ts["entityId"] = seg[3]
        return done()

    # ---- world instances ----------------------------------------------------------------
    wis = park["WorldInstance"]
    if len(seg) >= 4 and seg[0] == "build" and seg[2] == "worldinstance":
        lid = seg[3]
        if seg[1] == "start":
            eid = form.get("entityID", "")
            wis[lid] = {"localId": _int(lid), "slotId": _int(form.get("slotID"), -1),
                        "instanceType": _int(form.get("instanceType")), "entityId": eid,
                        "objectState": 1, "upgradeLevel": 0, "nurtureClicks": 0,
                        "buildEnd": now + _entity_secs(eid, "buildTimeInSeconds")}
            # building with a voucher uses up one voucher for that attraction
            idx = ENTITIES.get(eid, {}).get("index")
            if form.get("usingvoucher") == "true" and idx in park["AttractionVoucher"]:
                park["AttractionVoucher"].remove(idx)
        elif lid in wis and seg[1] == "finish":       # skipped with tickets
            wis[lid]["buildEnd"] = now
            wis[lid]["objectState"] = 2
        elif lid in wis and seg[1] == "complete":     # opened
            wi = wis[lid]
            wi["objectState"] = 4
            wi["nurtureEnd"] = now + _entity_secs(wi["entityId"], "timeTillPayoutInSeconds")
        return done()
    if len(seg) >= 4 and seg[0] == "upgrade" and seg[2] == "worldinstance":
        wi = wis.get(seg[3])
        if wi:
            if seg[1] == "start":
                # the client decrements upgradeLevel when loading an upgrading ride
                wi["upgradeLevel"] = wi.get("upgradeLevel", 0) + 1
                wi["objectState"] = 3
                wi["upgradeEnd"] = now + _entity_secs(wi["entityId"], "buildTimeInSeconds") // 3
            elif seg[1] == "finish":
                wi["upgradeEnd"] = now
            elif seg[1] == "complete":
                wi["objectState"] = 4
                wi["nurtureEnd"] = now + _entity_secs(wi["entityId"], "timeTillPayoutInSeconds")
        return done()
    if len(seg) >= 4 and seg[0] == "nurture" and seg[2] == "worldinstance":
        wi = wis.get(seg[3])
        if wi:
            if seg[1] == "complete":                 # earnings collected
                wi["nurtureEnd"] = now + _entity_secs(wi["entityId"], "timeTillPayoutInSeconds")
                wi["nurtureClicks"] = 0
            elif seg[1] == "finish":                 # payout timer skipped
                wi["nurtureEnd"] = now
            wi.pop("pausedNurture", None)
        return done()
    if seg[0] == "sell" and len(seg) >= 3:
        wis.pop(seg[1], None)
        return done()
    if seg[0] == "moveto" and len(seg) >= 4:
        wi = wis.get(seg[3])
        if wi:
            wi["slotId"] = _int(seg[1], wi.get("slotId", -1))
        return done()
    if seg[0] == "timers" and len(seg) >= 4:
        wi = wis.get(seg[3])
        if wi:
            if seg[1] == "pause" and wi.get("pausedNurture") is None:
                wi["pausedNurture"] = max(0, wi.get("nurtureEnd", now) - now)
            elif seg[1] == "resume" and wi.get("pausedNurture") is not None:
                wi["nurtureEnd"] = now + wi.pop("pausedNurture")
        return done()
    if seg[0] == "setbroke" and len(seg) >= 4:
        wi = wis.get(seg[3])
        if wi:
            wi["broken"] = seg[1] == "true"
        return done()

    # Anything else (gestures, trash, vouchers, game time, ...) needs only an
    # error-free reply; log it so it can be modelled later.
    log_action(mid, method, rest, body)
    if dirty:
        save_user(mid, user)
    return ok


def log_action(mid, method, rest, body):
    with open(os.path.join(DATA_DIR, "%s.actions.log" % "".join(c for c in mid if c.isalnum())), "a") as f:
        f.write("%s %s %s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), method, rest,
                                   body.decode("utf-8", "replace").replace("\n", "\\n") if body else ""))

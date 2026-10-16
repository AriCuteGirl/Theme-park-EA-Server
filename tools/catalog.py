#!/usr/bin/env python3
"""Rebuild the server-side Entity catalogue from the client's built-in tables.

usage: catalog.py <dir with extracted OBB> <out.json>

The client loads default stats for every ride/shop/decoration from resource
86406097 (see dk.progressivemedia.skeleton.d.c.d.a()), and the EA server sent the
same items again as <Entity> records with an entityId. This walks that table in
the client's read order and emits Entity records with the XML field names parsed
by dk.progressivemedia.skeleton.h.f.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bfc  # noqa: E402

TABLE_ID = 86406097


class Reader:
    def __init__(self, ints):
        self.v = ints
        self.p = 0

    def i(self):
        x = self.v[self.p]
        self.p += 1
        return x

    def n(self, k):
        return [self.i() for _ in range(k)]


def read_attraction(r, shop=False, extra=False):
    """Rides (class c.a.e), shops (c.a.f) and type-14 items (c.a.g) share a prefix."""
    o = {}
    for k in ("t", "w", "x", "y", "price", "st", "B", "n", "C", "D", "E", "F", "G", "H", "I", "J"):
        o[k] = r.i()
    r.i()  # skipped (p++)
    o["R"] = r.i()
    o["ax"], o["ay"] = r.i(), r.i()
    o["b"] = r.i()
    o["c"], o["d"], o["e"] = r.n(4), r.n(4), r.n(4)
    o["j"], o["k"], o["l"], o["m"] = r.i(), r.i(), r.i(), r.i()
    r.n(3), r.n(3), r.i()  # q, p vectors and r (render offsets)
    o["f"] = r.n(r.i())
    o["g"] = r.n(r.i())
    r.n(2 * r.i())  # h/i float pairs
    if extra:  # c.a.g
        for k in ("N", "u", "v", "S", "T", "L", "M", "o", "K", "U", "V", "W", "X", "Y"):
            o[k] = r.i()
    elif shop:  # c.a.f
        for k in ("N", "u", "v", "L", "M", "o", "K", "T", "U"):
            o[k] = r.i()
        r.n(2 * r.i())  # V/W pairs
    else:  # c.a.e
        for k in ("N", "u", "v", "L", "M", "o", "K", "S", "T", "ad", "V", "U", "W", "X", "Y",
                  "Z", "ab", "aa", "ac"):
            o[k] = r.i()
    return o


def csv(a):
    return ",".join(str(x) for x in a)


def main():
    root, out = sys.argv[1], sys.argv[2]
    entries = bfc.read_index(root)
    r = Reader(bfc.ints(bfc.read_resource(root, entries, TABLE_ID)))

    rides = [read_attraction(r) for _ in range(r.i())]
    shops = [read_attraction(r, shop=True) for _ in range(r.i())]
    # c.a.c (paths/scenery placed locally, no server Entity)
    for _ in range(r.i()):
        r.n(13)
    # c.a.h -> entityType 27
    typ27 = []
    for _ in range(r.i()):
        v = r.n(19)
        typ27.append(dict(zip(("t", "u", "v", "w", "x", "G", "H", "price", "st", "b", "L", "M", "c",
                               "d", "K", "a", "y", "I", "C"), v)))
    # c.a.d -> entityType 9
    typ9 = []
    for _ in range(r.i()):
        v = r.n(11)
        typ9.append(dict(zip(("t", "u", "v", "price", "st", "I", "C", "a", "L", "M", "K"), v)))
    typ14 = [read_attraction(r, extra=True) for _ in range(r.i())]
    assert r.p == len(r.v), "table not fully consumed: %d of %d" % (r.p, len(r.v))

    ents = []

    def base(etype, o):
        return {"entityType": etype, "entityId": str(etype * 1000 + o["t"]), "index": o["t"],
                "price": o["price"], "priceSuperTickets": o["st"]}

    for o in rides:
        e = base(3, o)
        e.update(theme=o["y"], sellPrice=o["B"], upgradeCost=o["n"], unlockCost=o["C"],
                 buildSkipCost=o["D"], upgradeSkipCost=o["E"], profiteeringSkipCost=o["F"],
                 buildTimeInSeconds=o["G"], buildHeight=o["H"], unlockLevel=o["I"],
                 type=o["S"], capacity=o["T"], entrance="%d,%d" % (o["ax"], o["ay"]),
                 entranceDirection=o["b"], entranceWaitTime=o["aa"],
                 earningsPerCollect=csv(o["c"]), parkRankPerCollect=csv(o["d"]),
                 visitorsServed=o["j"], visitorsServedUpgradeEffect=o["k"],
                 timeTillPayoutInSeconds=o["m"], perfectGestureReward=o["ad"],
                 isHidden=0 if o["R"] == 1 else 1, sortOrder=o["N"], gesture=o["ac"],
                 _name=o["u"], _desc=o["v"], _instanceType=o["K"])
        ents.append(e)
    for o in shops:
        e = base(4, o)
        e.update(theme=o["y"], acceptableGoodsPrice=o["S"] if "S" in o else 0,
                 unlockCost=o["C"], buildSkipCost=o["D"], upgradeSkipCost=o["E"],
                 upgradeCost=o["n"], profiteeringSkipCost=o["F"], buildTimeInSeconds=o["G"],
                 buildHeight=o["H"], earningsPerCollect=csv(o["c"]),
                 parkRankPerCollect=csv(o["d"]), visitorsServed=o["j"],
                 visitorsServedUpgradeEffect=o["k"], nurtureClicks=o["l"],
                 timeTillPayoutInSeconds=o["m"], entranceDirection=o["b"], type=o["T"],
                 entrance="%d,%d" % (o["ax"], o["ay"]), sellPrice=o["B"], unlockLevel=o["I"],
                 isHidden=0 if o["R"] == 1 else 1, sortOrder=o["N"],
                 _name=o["u"], _desc=o["v"], _instanceType=o["K"])
        ents.append(e)
    for o in typ9:
        e = base(9, o)
        e.update(unlockCost=o["C"], _name=o["u"], _desc=o["v"], _instanceType=o["K"])
        ents.append(e)
    for o in typ27:
        e = base(27, o)
        e.update(unlockCost=o["C"], isHidden=0 if o["b"] == 1 else 1, _name=o["u"],
                 _desc=o["v"], _instanceType=o["K"])
        ents.append(e)
    for o in typ14:
        e = base(14, o)
        e.update(buildHeight=o["H"], buildSkipCost=o["D"], buildTimeInSeconds=o["G"],
                 entrance="%d,%d" % (o["ax"], o["ay"]), entranceDirection=o["b"],
                 profiteeringSkipCost=o["S"], nurtureClicks=o["T"],
                 timeTillPayoutInSeconds=o["m"], earningsPerCollect=csv(o["c"]),
                 upgradeSkipCost=o["Y"], sellPrice=o["B"], isHidden=0 if o["R"] == 1 else 1,
                 unlockLevel=o["I"], unlockCost=o["C"], sortOrder=o["N"],
                 _name=o["u"], _desc=o["v"], _instanceType=o["K"])
        ents.append(e)

    with open(out, "w") as f:
        json.dump(ents, f, indent=1)
    print("rides %d, shops %d, type9 %d, type27 %d, type14 %d -> %d entities"
          % (len(rides), len(shops), len(typ9), len(typ27), len(typ14), len(ents)))


if __name__ == "__main__":
    main()

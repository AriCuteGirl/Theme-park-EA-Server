#!/usr/bin/env python3
"""Build a pure-Java Theme Park APK that runs on 64-bit-only phones.

usage: build_port.py <original 4.4.92 apk> <extracted obb dir> <out.apk> <server url>
       (needs: apktool.jar via $APKTOOL, javac, d8, zipalign, apksigner)

Steps:
  1. apktool-decode the original APK
  2. compile port/src (Java replacements for librflib, libAudioLib and EA's
     libEASPFullExample) against port/stubs, convert to smali, drop them in
  3. remove System.loadLibrary calls and EA SDK start-up from the game
  4. delete lib/ (no native code left) and bundle the OBB data in assets/
  5. point the login code at <server url>, raise targetSdk to 24 so Android 15+
     installs it, rebuild, align and sign (tools/themepark.keystore)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APKTOOL = os.environ.get("APKTOOL", os.path.join(HERE, "apktool.jar"))
KEYSTORE = os.path.join(HERE, "themepark.keystore")
NATIVE_LIBS = ("EASPFullExample", "rflib", "AudioLib")
REPLACED = ["dk/progressivemedia/android/PMGraphics", "dk/progressivemedia/android/PMAudioAPI",
            "dk/progressivemedia/android/ipsp/PMiPSP", "com/tprevival/Safe", "com/tprevival/State",
            "com/tprevival/Brand", "com/tprevival/Net", "com/tprevival/Friends"]


def run(*cmd, **kw):
    print("+", " ".join(cmd[:4]), "...")
    subprocess.check_call(list(cmd), **kw)


def sub_once(text, pattern, repl, what):
    new, n = re.subn(pattern, repl, text, flags=re.M)
    if n == 0:
        sys.exit("build_port: pattern not found: " + what)
    return new


def main():
    src_apk, obb_dir, out_apk, server = sys.argv[1:5]
    work = tempfile.mkdtemp(prefix="tpport_")
    dec = os.path.join(work, "dec")
    run("java", "-jar", APKTOOL, "d", "-f", "-o", dec, src_apk)

    # 2. compile replacements -> dex -> smali
    classes = os.path.join(work, "classes")
    os.makedirs(classes)
    srcs = []
    for d, _, files in os.walk(os.path.join(ROOT, "port", "src")):
        srcs += [os.path.join(d, f) for f in files if f.endswith(".java")]
    run("javac", "--release", "8", "-nowarn", "-cp", os.path.join(ROOT, "port", "stubs"),
        "-sourcepath", os.path.join(ROOT, "port", "stubs"), "-d", classes, *srcs)
    # keep only our classes (not the stubs javac compiled alongside)
    keep = []
    for d, _, files in os.walk(classes):
        for f in files:
            rel = os.path.relpath(os.path.join(d, f), classes)[:-len(".class")].split("$")[0]
            if rel in REPLACED:
                keep.append(os.path.join(d, f))
    dexdir = os.path.join(work, "dex")
    os.makedirs(dexdir)
    run("d8", "--release", "--min-api", "14", "--no-desugaring", "--output", dexdir, *keep)
    smali_out = os.path.join(work, "smali")
    # apktool's bundled baksmali has no CLI entry point; let apktool decode a
    # minimal zip holding just our classes.dex instead.
    import zipfile
    tiny = os.path.join(work, "port.apk")
    with zipfile.ZipFile(tiny, "w") as z:
        z.write(os.path.join(dexdir, "classes.dex"), "classes.dex")
    tinydec = os.path.join(work, "portdec")
    run("java", "-jar", APKTOOL, "d", "-r", "-f", "-o", tinydec, tiny)
    shutil.move(os.path.join(tinydec, "smali"), smali_out)
    for d, _, files in os.walk(smali_out):
        for f in files:
            rel = os.path.relpath(os.path.join(d, f), smali_out)
            dst = os.path.join(dec, "smali", rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(os.path.join(d, f), dst)

    # 3. no native libraries, no EA SDK start-up
    smali = os.path.join(dec, "smali")
    for d, _, files in os.walk(smali):
        for f in files:
            if not f.endswith(".smali"):
                continue
            p = os.path.join(d, f)
            s = open(p, encoding="utf-8").read()
            if "loadLibrary" not in s:
                continue
            for lib in NATIVE_LIBS:
                s = re.sub(r'\n\s*const-string (v\d+), "%s"\n\s*invoke-static \{\1\}, '
                           r'Ljava/lang/System;->loadLibrary\(Ljava/lang/String;\)V\n' % lib, "\n", s)
            open(p, "w", encoding="utf-8").write(s)
    # implicit service intents throw on Android 5+: route through com.tprevival.Safe
    svc = [(r"bindService\(Landroid/content/Intent;Landroid/content/ServiceConnection;I\)Z",
            "bindService(Landroid/content/Context;Landroid/content/Intent;Landroid/content/ServiceConnection;I)Z"),
           (r"startService\(Landroid/content/Intent;\)Landroid/content/ComponentName;",
            "startService(Landroid/content/Context;Landroid/content/Intent;)Landroid/content/ComponentName;"),
           # device identifiers throw SecurityException on Android 10+
           (r"getDeviceId\(\)Ljava/lang/String;",
            "getDeviceId(Landroid/telephony/TelephonyManager;)Ljava/lang/String;"),
           (r"getSubscriberId\(\)Ljava/lang/String;",
            "getSubscriberId(Landroid/telephony/TelephonyManager;)Ljava/lang/String;"),
           (r"getNetworkType\(\)I", "getNetworkType(Landroid/telephony/TelephonyManager;)I")]
    for d, _, files in os.walk(smali):
        for f in files:
            p = os.path.join(d, f)
            if not f.endswith(".smali") or "tprevival" in p:
                continue
            s = open(p, encoding="utf-8").read()
            if "Service(" not in s and "TelephonyManager" not in s:
                continue
            n = s
            for pat, sig in svc:
                owner = r"Landroid/telephony/TelephonyManager;" if "Telephony" in sig else r"L[^;]+;"
                n = re.sub(r"invoke-virtual \{([^}]*)\}, " + owner + "->" + pat,
                           r"invoke-static {\1}, Lcom/tprevival/Safe;->" + sig, n)
            if n != s:
                open(p, "w", encoding="utf-8").write(n)

    # Ride plots start open instead of covered in rocks. Originally every plot
    # in a new territory had to be cleared one by one (and EA's server granted
    # the free ones); now buying a territory with tickets is enough.
    p = os.path.join(smali, "dk", "progressivemedia", "skeleton", "d", "b", "n.smali")
    s = open(p, encoding="utf-8").read()
    s = sub_once(s, r"(:cond_0\n\s*)const/4 v0, 0x0(\n\s*iput-boolean v0, p0, "
                    r"Ldk/progressivemedia/skeleton/d/b/n;->k:Z)", r"\1const/4 v0, 0x1\2", "open ride plots")
    open(p, "w", encoding="utf-8").write(s)

    # friends come from the revival server (com.tprevival.Friends) instead of
    # the made-up "Friend 1..n" list this build's GetFriends() produced
    p = os.path.join(smali, "dk", "progressivemedia", "skeleton", "ipsp", "PMiPSP.smali")
    s = open(p, encoding="utf-8").read()
    s = sub_once(s, r"(\.method public static GetFriends\(\)V\n)(?:.*\n)*?(\.end method)",
                 r"\1    .locals 0\n\n    invoke-static {}, Lcom/tprevival/Friends;->fetch()V\n\n    return-void\n\2",
                 "GetFriends")
    open(p, "w", encoding="utf-8").write(s)

    # friend screens think this is an Origin account (com.tprevival.Friends.accountState)
    state_call = "invoke-static {}, Ldk/progressivemedia/skeleton/d/f;->r()I"
    for name in ("s", "b"):  # Neighbor Parks, hire a friend
        p = os.path.join(smali, "dk", "progressivemedia", "skeleton", "d", "c", "b", name + ".smali")
        s = open(p, encoding="utf-8").read()
        if state_call not in s:
            sys.exit("build_port: no account state check in d/c/b/%s.smali" % name)
        s = s.replace(state_call, "invoke-static {}, Lcom/tprevival/Friends;->accountState()I")
        open(p, "w", encoding="utf-8").write(s)
    p = os.path.join(smali, "dk", "progressivemedia", "skeleton", "d", "f.smali")
    s = open(p, encoding="utf-8").read()
    s = sub_once(s, r"(\.method public static i\(\)I\n(?:(?!\.end method).*\n)*?\s*)"
                    r"invoke-static \{\}, Ldk/progressivemedia/skeleton/ipsp/PMiPSP;->getAccountState\(\)I",
                 r"\1invoke-static {}, Lcom/tprevival/Friends;->accountState()I", "friend count")
    open(p, "w", encoding="utf-8").write(s)

    # mark when our own park's cash/tickets are loaded (com.tprevival.State.parkLoaded)
    p = os.path.join(smali, "dk", "progressivemedia", "skeleton", "d", "d.smali")
    s = open(p, encoding="utf-8").read()
    s = sub_once(s, r"(\.method public static a\(Ldk/progressivemedia/skeleton/h/ak;\)V\n(?:(?!\.end method).*\n)*?"
                    r"\s*sput v0, Ldk/progressivemedia/skeleton/d/d;->z:I\n)",
                 r"\1\n    invoke-static {}, Lcom/tprevival/State;->parkLoaded()V\n", "park loaded")
    open(p, "w", encoding="utf-8").write(s)

    # tell the server when the daily bonus popup was collected (com.tprevival.Net)
    p = os.path.join(smali, "dk", "progressivemedia", "skeleton", "d", "c", "e.smali")
    s = open(p, encoding="utf-8").read()
    s = sub_once(s, r"(sput-boolean v4, Ldk/progressivemedia/skeleton/f;->P:Z\n)",
                 r"\1\n    invoke-static {}, Lcom/tprevival/Net;->bonusCollected()V\n", "daily bonus collect")
    open(p, "w", encoding="utf-8").write(s)

    # every park request reports the player's cash/tickets/level/xp (com.tprevival.State)
    p = os.path.join(smali, "dk", "progressivemedia", "a", "n", "b.smali")
    s = open(p, encoding="utf-8").read()
    s, n = re.subn(r"(invoke-virtual \{(v\d+), v\d+\}, Ljava/net/HttpURLConnection;->setRequestMethod\(Ljava/lang/String;\)V\n)",
                   r"\1\n    invoke-static {\2}, Lcom/tprevival/State;->addHeaders(Ljava/net/HttpURLConnection;)V\n", s)
    if n < 2:
        sys.exit("build_port: expected 2 setRequestMethod calls in a/n/b.smali, found %d" % n)
    open(p, "w", encoding="utf-8").write(s)

    p = os.path.join(smali, "dk", "progressivemedia", "android", "PMActivity.smali")
    s = open(p, encoding="utf-8").read()
    for call in ("Lcom/ea/EAThread/EAThread;->Init()V",
                 "Lcom/ea/EAIO/EAIO;->Startup(Landroid/app/Activity;)V",
                 "Lcom/ea/EAMIO/StorageDirectory;->Startup(Landroid/app/Activity;)V"):
        s = sub_once(s, r"^\s*invoke-static \{[^}]*\}, %s\n" % re.escape(call), "", call)
    s = sub_once(s, r"^\s*new-instance (v\d+), Lcom/ea/easp/EASPHandler;\n(?:.*\n)*?"
                    r"\s*invoke-virtual \{\1, v\d+\}, Lcom/ea/easp/EASPHandler;->onCreate\(Landroid/os/Bundle;\)V\n",
                 "", "EASPHandler start-up")
    # "Private Server" label over the game view (com.tprevival.Brand)
    s = sub_once(s, r"(invoke-virtual \{p0, (v\d+)\}, Ldk/progressivemedia/android/PMActivity;->setContentView\(Landroid/view/View;\)V\n)",
                 r"\1\n    invoke-static {p0}, Lcom/tprevival/Brand;->attach(Landroid/app/Activity;)V\n", "setContentView")
    open(p, "w", encoding="utf-8").write(s)

    # 4. no lib/, game data inside the APK (PMActivity prefers assets/0.bfc over the OBB)
    shutil.rmtree(os.path.join(dec, "lib"), ignore_errors=True)
    assets = os.path.join(dec, "assets")
    for f in os.listdir(obb_dir):
        shutil.copy(os.path.join(obb_dir, f), os.path.join(assets, f))
    yml = os.path.join(dec, "apktool.yml")
    y = open(yml, encoding="utf-8").read()
    y = re.sub(r"doNotCompress:\n(  - .*\n)*", "", y)
    y += "doNotCompress:\n- bfc\n- pac\n- mp3\n- wav\n- png\n"
    y = re.sub(r"targetSdkVersion: '?\d+'?", "targetSdkVersion: 24", y)
    open(yml, "w", encoding="utf-8").write(y)
    man = os.path.join(dec, "AndroidManifest.xml")
    m = open(man, encoding="utf-8").read()
    m = re.sub(r'android:targetSdkVersion="\d+"', 'android:targetSdkVersion="24"', m)
    open(man, "w", encoding="utf-8").write(m)

    # 5. server address
    p = os.path.join(smali, "dk", "progressivemedia", "android", "ipsp", "PMiPSP.smali")
    s = open(p, encoding="utf-8").read()
    s = sub_once(s, r'(SERVER:Ljava/lang/String; = )"http://[^"]*"', r'\1"%s"' % server, "SERVER")
    open(p, "w", encoding="utf-8").write(s)

    unsigned = os.path.join(work, "unsigned.apk")
    aligned = os.path.join(work, "aligned.apk")
    run("java", "-jar", APKTOOL, "b", "-o", unsigned, dec)
    run("zipalign", "-f", "-p", "4", unsigned, aligned)
    run("apksigner", "sign", "--ks", KEYSTORE, "--ks-pass", "pass:themepark", "--out", out_apk, aligned)
    shutil.rmtree(work)
    print("wrote", out_apk)


if __name__ == "__main__":
    main()

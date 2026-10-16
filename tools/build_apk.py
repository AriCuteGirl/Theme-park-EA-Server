#!/usr/bin/env python3
"""Patch the Theme Park 4.4.92 APK so it talks to the local server.

usage: build_apk.py <original.apk> <out.apk> <server url, e.g. http://192.168.240.1:8086>

Rewrites the Synergy production URL inside libEASPFullExample.so (the new URL must
not be longer than the original), drops the old EA signature and re-signs with a
local key (tools/themepark.keystore, created on first run).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

LIB = "lib/armeabi-v7a/libEASPFullExample.so"
ORIG = b"https://synergy.eamobile.com\x00"
HERE = os.path.dirname(os.path.abspath(__file__))
KEYSTORE = os.path.join(HERE, "themepark.keystore")


def patch_lib(data, url):
    new = url.encode()
    if len(new) >= len(ORIG):
        sys.exit("server url too long (max %d chars)" % (len(ORIG) - 1))
    idx = data.find(ORIG)
    if idx < 0:
        sys.exit("synergy url not found in " + LIB)
    return data[:idx] + new.ljust(len(ORIG), b"\x00") + data[idx + len(ORIG):]


def main():
    src, out, url = sys.argv[1:4]
    tmpdir = tempfile.mkdtemp()
    unsigned = os.path.join(tmpdir, "unsigned.apk")
    aligned = os.path.join(tmpdir, "aligned.apk")
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(unsigned, "w") as zout:
        for info in zin.infolist():
            if info.filename.startswith("META-INF/"):
                continue
            data = zin.read(info.filename)
            if info.filename == LIB:
                data = patch_lib(data, url)
            zout.writestr(info, data, compress_type=info.compress_type)
    subprocess.check_call(["zipalign", "-f", "-p", "4", unsigned, aligned])
    if not os.path.exists(KEYSTORE):
        subprocess.check_call(["keytool", "-genkeypair", "-keystore", KEYSTORE, "-alias", "tp",
                               "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
                               "-storepass", "themepark", "-keypass", "themepark",
                               "-dname", "CN=Theme Park Revival"])
    subprocess.check_call(["apksigner", "sign", "--ks", KEYSTORE, "--ks-pass", "pass:themepark",
                           "--out", out, aligned])
    shutil.rmtree(tmpdir)
    print("wrote", out)


if __name__ == "__main__":
    main()

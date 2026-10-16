package dk.progressivemedia.android;

import android.util.Log;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;

/**
 * Replacement for libAudioLib.so (32-bit ARM only). The native library was a
 * software mixer for sound effects; for now effects are silent and report as
 * finished. Music is unaffected: it plays through Android's MediaPlayer (PMMusic).
 */
public class PMAudioAPI {
    private static int masterVolume = 100;

    public static boolean Begin() { return true; }
    public static void Destroy() { }
    public static void End() { }
    public static short GetLoadCount(int i) { return 0; }
    public static int GetMasterVolume() { return masterVolume; }
    public static int GetPlayableCount() { return 0; }
    public static int GetState(int i) { return 0; }
    public static boolean Initialize(String str, int i) { return true; }
    public static boolean IsPlayingAnyOf(int i) { return false; }
    public static boolean Load(int i) { return true; }
    public static int Play(int i) { return -1; }
    public static int Play(int i, int i2) { return -1; }
    public static boolean SetLoadCount(int i, short s) { return true; }
    public static void SetMasterVolume(int i) { masterVolume = i; }
    public static boolean SetVolume(int i, int i2) { return true; }
    public static boolean Stop(int i) { return true; }
    public static void StopAll() { }
    public static boolean StopAllOf(int i) { return true; }
    public static void Suspend() { }
    public static boolean Unload(int i) { return true; }
    public static void Update() { }

    public static void UpdateAsync(short[] buffer) {
        java.util.Arrays.fill(buffer, (short) 0);
    }

    public static void Wakeup() { }

    public static byte[] readFile(String str) {
        try {
            byte[] bArr = new byte[65536];
            ByteArrayOutputStream out = new ByteArrayOutputStream(65536);
            InputStream in = PMActivity.instance.openReadAsset(str);
            while (true) {
                int n = in.read(bArr, 0, 65536);
                if (n <= 0) {
                    in.close();
                    return out.toByteArray();
                }
                out.write(bArr, 0, n);
            }
        } catch (Exception e) {
            Log.e("RFLib", "Failed to load file: " + str + " - " + e);
            return null;
        }
    }
}

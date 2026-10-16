package dk.progressivemedia.android;

import android.util.Log;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;

/**
 * Replacement for libAudioLib.so (32-bit ARM only): a small software mixer for
 * the sound effects. Music is separate: it plays through Android's MediaPlayer.
 *
 * The game owns the AudioTrack (dk.progressivemedia.a.b.a: 22050 Hz, stereo,
 * 16-bit) and asks us to fill its buffer in UpdateAsync() from its audio thread.
 *
 * Sound bank (audio_*.pac, little-endian ints):
 *   magic 0x13370226, version, 0, recordCount, soundCount
 *   recordCount x {type, fileId, flag, byteSize}   -> data file "wv%04x" (16-bit mono PCM)
 *   soundCount  x {type, id, n, flag, n x {recordIndex, sampleRate}}
 * The game plays sounds by their index in the second table. All three banks
 * point at the same wv files; audio_large.pac has their real rate (11025 Hz),
 * audio_xlarge.pac lists rates up to 96000 Hz, so rates always come from
 * audio_large.pac.
 */
public class PMAudioAPI {
    private static final String TAG = "TPRevivalAudio";
    private static final int OUT_RATE = 22050;
    private static final int MAX_VOICES = 16;

    // game-visible voice states (skeleton.b.a treats 0, 3 and 4 as "still busy")
    private static final int STATE_PLAYING = 3;
    private static final int STATE_DONE = 1;

    private static int masterVolume = 100;
    private static int[] soundFile = new int[0];   // sound index -> wv file id, -1 = none
    private static int[] soundRate = new int[0];
    private static short[][] samples = new short[0][];
    private static final Voice[] voices = new Voice[MAX_VOICES];
    private static int nextHandle = 1;
    private static boolean suspended = false;

    private static final class Voice {
        int handle;
        int sound;
        short[] data;
        long pos;      // 16.16 fixed point position in data
        long step;     // 16.16 fixed point step per output frame
        int volume;    // 0..100
    }

    private static int le32(byte[] b, int i) {
        int p = i * 4;
        return (b[p] & 255) | (b[p + 1] & 255) << 8 | (b[p + 2] & 255) << 16 | (b[p + 3] & 255) << 24;
    }

    public static synchronized boolean Initialize(String str, int bufferBytes) {
        try {
            byte[] b = readFile("audio_large.pac");
            if (b == null) {
                b = readFile(str);
            }
            if (b == null || le32(b, 0) != 0x13370226) {
                Log.e(TAG, "bad sound bank " + str);
                return true;
            }
            int nrec = le32(b, 3);
            int nsnd = le32(b, 4);
            int[] recFile = new int[nrec];
            int p = 5;
            for (int i = 0; i < nrec; i++) {
                recFile[i] = le32(b, p + 1);
                p += 4;
            }
            soundFile = new int[nsnd];
            soundRate = new int[nsnd];
            samples = new short[nsnd][];
            for (int i = 0; i < nsnd; i++) {
                int n = le32(b, p + 2);
                p += 4;
                soundFile[i] = -1;
                soundRate[i] = 11025;
                if (n > 0) {
                    int rec = le32(b, p);
                    soundRate[i] = le32(b, p + 1);
                    soundFile[i] = rec >= 0 && rec < nrec ? recFile[rec] : -1;
                }
                p += 2 * n;
            }
            Log.i(TAG, "sound bank: " + nsnd + " sounds");
        } catch (Throwable t) {
            Log.e(TAG, "sound bank failed: " + t);
        }
        return true;
    }

    public static synchronized boolean Load(int i) {
        if (i < 0 || i >= samples.length || soundFile[i] < 0) {
            return true;
        }
        if (samples[i] == null) {
            byte[] b = readFile(String.format("wv%04x", soundFile[i]));
            if (b == null) {
                return false;
            }
            short[] s = new short[b.length / 2];
            for (int k = 0; k < s.length; k++) {
                s[k] = (short) ((b[2 * k] & 255) | (b[2 * k + 1] << 8));
            }
            samples[i] = s;
        }
        return true;
    }

    public static synchronized boolean Unload(int i) {
        // keep the samples: they are small and sounds are reloaded constantly
        return true;
    }

    public static int Play(int i) {
        return Play(i, 100);
    }

    public static synchronized int Play(int i, int volume) {
        if (i < 0 || i >= samples.length || soundFile[i] < 0) {
            return -1;
        }
        if (samples[i] == null && !Load(i)) {
            return -1;
        }
        int slot = -1;
        for (int k = 0; k < MAX_VOICES; k++) {
            if (voices[k] == null) {
                slot = k;
                break;
            }
        }
        if (slot < 0) {
            // all busy: replace the voice closest to its end
            long best = Long.MAX_VALUE;
            for (int k = 0; k < MAX_VOICES; k++) {
                long left = ((long) voices[k].data.length << 16) - voices[k].pos;
                if (left < best) {
                    best = left;
                    slot = k;
                }
            }
        }
        Voice v = new Voice();
        v.handle = nextHandle++;
        if (nextHandle <= 0) {
            nextHandle = 1;
        }
        v.sound = i;
        v.data = samples[i];
        v.step = ((long) soundRate[i] << 16) / OUT_RATE;
        v.volume = clamp(volume);
        voices[slot] = v;
        if (v.handle <= 5) {
            Log.i(TAG, "play sound " + i + " (wv" + Integer.toHexString(soundFile[i]) + ") volume " + volume);
        }
        return v.handle;
    }

    private static int clamp(int volume) {
        return volume < 0 ? 0 : (volume > 100 ? 100 : volume);
    }

    private static Voice find(int handle) {
        for (Voice v : voices) {
            if (v != null && v.handle == handle) {
                return v;
            }
        }
        return null;
    }

    public static synchronized int GetState(int handle) {
        return find(handle) != null ? STATE_PLAYING : STATE_DONE;
    }

    public static synchronized boolean SetVolume(int handle, int volume) {
        Voice v = find(handle);
        if (v != null) {
            v.volume = clamp(volume);
        }
        return true;
    }

    public static synchronized boolean Stop(int handle) {
        for (int k = 0; k < MAX_VOICES; k++) {
            if (voices[k] != null && voices[k].handle == handle) {
                voices[k] = null;
            }
        }
        return true;
    }

    public static synchronized void StopAll() {
        for (int k = 0; k < MAX_VOICES; k++) {
            voices[k] = null;
        }
    }

    public static synchronized boolean StopAllOf(int i) {
        for (int k = 0; k < MAX_VOICES; k++) {
            if (voices[k] != null && voices[k].sound == i) {
                voices[k] = null;
            }
        }
        return true;
    }

    public static synchronized boolean IsPlayingAnyOf(int i) {
        for (Voice v : voices) {
            if (v != null && v.sound == i) {
                return true;
            }
        }
        return false;
    }

    public static synchronized int GetPlayableCount() {
        int n = 0;
        for (Voice v : voices) {
            if (v == null) {
                n++;
            }
        }
        return n;
    }

    public static boolean Begin() { return true; }
    public static void End() { }
    public static void Update() { }
    public static void Destroy() { StopAll(); }
    public static short GetLoadCount(int i) { return 0; }
    public static boolean SetLoadCount(int i, short s) { return true; }
    public static int GetMasterVolume() { return masterVolume; }
    public static void SetMasterVolume(int i) { masterVolume = clamp(i); }
    public static synchronized void Suspend() { suspended = true; }
    public static synchronized void Wakeup() { suspended = false; }

    /** Fill the game's stereo buffer (interleaved L/R) with the mixed voices. */
    public static synchronized void UpdateAsync(short[] buffer) {
        int frames = buffer.length / 2;
        java.util.Arrays.fill(buffer, (short) 0);
        if (suspended) {
            return;
        }
        int[] mix = null;
        for (int k = 0; k < MAX_VOICES; k++) {
            Voice v = voices[k];
            if (v == null) {
                continue;
            }
            if (mix == null) {
                mix = new int[frames];
            }
            int gain = v.volume * masterVolume; // 0..10000
            long end = (long) v.data.length << 16;
            short[] d = v.data;
            for (int f = 0; f < frames; f++) {
                if (v.pos >= end) {
                    break;
                }
                int idx = (int) (v.pos >> 16);
                int frac = (int) (v.pos & 0xFFFF);
                int a = d[idx];
                int b = idx + 1 < d.length ? d[idx + 1] : a;
                int s = a + (((b - a) * frac) >> 16);
                mix[f] += s * gain / 10000;
                v.pos += v.step;
            }
            if (v.pos >= end) {
                voices[k] = null;
            }
        }
        if (mix == null) {
            return;
        }
        for (int f = 0; f < frames; f++) {
            int s = mix[f];
            short out = (short) (s > 32767 ? 32767 : (s < -32768 ? -32768 : s));
            buffer[2 * f] = out;
            buffer[2 * f + 1] = out;
        }
    }

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

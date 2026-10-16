package dk.progressivemedia.android.ipsp;

import android.provider.Settings;
import android.util.Log;

import dk.progressivemedia.android.PMActivity;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Replacement for libEASPFullExample.so (EA's 32-bit ARM SDK). Logs in to the
 * revival server with the same Synergy/Mayhem calls the SDK made, then reports
 * SPEvent_GetMayhemIdsDone (60) to the game on its update tick. Store/MTX calls
 * answer "no items"; purchases fail.
 */
public class PMiPSP {
    /** Replaced at build time by tools/build_port.py. */
    public static String SERVER = "http://192.168.0.130:8086";

    private static final String TAG = "TPRevival";
    private static final int EV_GET_ITEMS_DONE = 13;
    private static final int EV_PURCHASE_ERROR = 24;
    private static final int EV_SERVER_UNAVAILABLE = 52;
    private static final int EV_MAYHEM_IDS_DONE = 60;

    private static final ArrayList<int[]> events = new ArrayList<int[]>();
    private static final ArrayList<Runnable> gameTasks = new ArrayList<Runnable>();
    private static volatile boolean loggedIn = false;
    private static volatile boolean loggingIn = false;
    private static volatile String mayhemUserId = null;
    private static volatile String sessionKey = null;
    private static int nextRequest = 1;

    private static void post(int id, int request, int value) {
        synchronized (events) {
            events.add(new int[]{id, request, value});
        }
    }

    /** Run r on the game thread (next onUpdate tick). */
    public static void runOnGame(Runnable r) {
        synchronized (gameTasks) {
            gameTasks.add(r);
        }
    }

    private static synchronized int newRequest() {
        return nextRequest++;
    }

    private static String get(String path) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(SERVER + path).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(15000);
        try {
            InputStream in = c.getResponseCode() < 400 ? c.getInputStream() : c.getErrorStream();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while (in != null && (n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
            }
            if (c.getResponseCode() >= 400) {
                throw new Exception("HTTP " + c.getResponseCode() + " for " + path);
            }
            return out.toString("UTF-8");
        } finally {
            c.disconnect();
        }
    }

    private static String find(String text, String regex) throws Exception {
        Matcher m = Pattern.compile(regex).matcher(text);
        if (!m.find()) {
            throw new Exception("unexpected reply: " + text);
        }
        return m.group(1);
    }

    private static String enc(String s) throws Exception {
        return URLEncoder.encode(s, "UTF-8");
    }

    private static void startLogin() {
        if (loggingIn) {
            return;
        }
        loggingIn = true;
        new Thread(new Runnable() {
            public void run() {
                try {
                    String androidId = null;
                    try {
                        androidId = Settings.Secure.getString(PMActivity.instance.getContentResolver(), "android_id");
                    } catch (Throwable t) {
                    }
                    if (androidId == null || androidId.length() == 0) {
                        androidId = "themepark";
                    }
                    String pkg = "com.eamobile.themepark_row";
                    get("/director/api/android/getDirectionByPackage?packageId=" + pkg);
                    String dev = find(get("/user/api/android/getDeviceID?androidId=" + enc(androidId)),
                            "\"deviceId\"\\s*:\\s*\"([^\"]+)\"");
                    String uid = find(get("/user/api/android/getAnonUid?eadeviceid=" + enc(dev)),
                            "\"uid\"\\s*:\\s*\"?(\\d+)");
                    String mid = find(get("/mh/users?application=synergy&applicationUserId=" + uid),
                            "/users/(\\d+)");
                    // the device id proves to the server that this player is ours
                    String key = find(get("/mh/users/" + mid + "/token?game=themepark&eadeviceid=" + enc(dev)),
                            "<sessionKey>([^<]+)</sessionKey>");
                    mayhemUserId = mid;
                    sessionKey = key;
                    loggedIn = true;
                    com.tprevival.Brand.loggedIn();
                    Log.i(TAG, "logged in: mayhemUserId=" + mid);
                    post(EV_MAYHEM_IDS_DONE, 0, 0);
                } catch (Throwable e) {
                    Log.e(TAG, "login failed: " + e);
                    post(EV_SERVER_UNAVAILABLE, 0, 0);
                } finally {
                    loggingIn = false;
                }
            }
        }, "TPRevivalLogin").start();
    }

    public static int CancelRequest(int i) { return 0; }

    public static int DownloadMTXItem(int i) {
        int r = newRequest();
        post(EV_PURCHASE_ERROR, r, -1);
        return r;
    }

    public static int GetAllMTXItems() {
        int r = newRequest();
        post(EV_GET_ITEMS_DONE, r, 0);
        return r;
    }

    public static int GetIAMessage() { return -1; }

    public static int GetMTXStoreBadgesCount() { return -1; }

    public static String GetMayhemSessionKey() { return sessionKey; }

    public static String GetMayhemURL() { return SERVER; }

    public static String GetMayhemUserId() { return mayhemUserId; }

    public static int GetPurchasedMTXItems() {
        int r = newRequest();
        post(EV_GET_ITEMS_DONE, r, 0);
        return r;
    }

    public static int GetTickers(int i) { return -1; }

    public static void IAMCancelPressed() { }

    public static void IAMOKPressed() { }

    public static boolean IsLoggedIn() { return loggedIn; }

    public static boolean IsLoggingIn() { return loggingIn; }

    public static void LogEAServer(int i, int i2, String str, int i3, String str2) { }

    public static int PurchaseMTXItem(int i) {
        int r = newRequest();
        post(EV_PURCHASE_ERROR, r, -1);
        return r;
    }

    public static void RetryAutoLogin() {
        if (!loggedIn) {
            startLogin();
        }
    }

    public static boolean SetAgeGate(int i, int i2) { return true; }

    public static void enableTelemetry(boolean z) { }

    public static int onPauseJNI() { return 0; }

    public static int onResumeJNI() { return 0; }

    public static int onStopJNI() { return 0; }

    /** Called every frame by the game: deliver queued SDK events on its thread. */
    public static void onUpdate() {
        Runnable[] tasks = null;
        synchronized (gameTasks) {
            if (!gameTasks.isEmpty()) {
                tasks = gameTasks.toArray(new Runnable[gameTasks.size()]);
                gameTasks.clear();
            }
        }
        if (tasks != null) {
            for (Runnable r : tasks) {
                try {
                    r.run();
                } catch (Throwable t) {
                    Log.e(TAG, "game task failed: " + t);
                }
            }
        }
        int[][] pending;
        synchronized (events) {
            if (events.isEmpty()) {
                return;
            }
            pending = events.toArray(new int[events.size()][]);
            events.clear();
        }
        for (int[] e : pending) {
            dk.progressivemedia.skeleton.ipsp.PMiPSP.HandleSPEvent(e[0], e[1], e[2]);
        }
    }

    public static int onWindowFocusChangedJNI(boolean z) { return 0; }

    public static void registerHandler(String a, String b, String c, boolean d, String e, String f, boolean g) {
        startLogin();
    }

    public static void registerHandler1(String a, String b, String c, boolean d, String e, String f, boolean g,
                                        int year, int month) {
        startLogin();
    }

    public static int shutdownJNI() { return 0; }

    public static boolean telemetryEnabled() { return false; }
}

package com.tprevival;

import dk.progressivemedia.android.ipsp.PMiPSP;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Requests to the revival server's own endpoints (/mh/games/themepark/tp/...). */
public class Net {
    public interface Done {
        void done(String reply); // null on failure
    }

    public static String request(String path) throws Exception {
        String uid = PMiPSP.GetMayhemUserId();
        String key = PMiPSP.GetMayhemSessionKey();
        if (uid == null || key == null) {
            throw new Exception("not logged in");
        }
        HttpURLConnection c = (HttpURLConnection) new URL(
                PMiPSP.GetMayhemURL() + "/mh/games/themepark/" + path).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(15000);
        c.setRequestMethod("POST");
        c.setRequestProperty("mh_uid", uid);
        c.setRequestProperty("mh_session_key", key);
        State.addHeaders(c);
        c.setDoOutput(true);
        c.getOutputStream().close();
        try {
            int code = c.getResponseCode();
            InputStream in = code < 400 ? c.getInputStream() : c.getErrorStream();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while (in != null && (n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
            }
            if (code >= 400) {
                throw new Exception("HTTP " + code);
            }
            return out.toString("UTF-8");
        } finally {
            c.disconnect();
        }
    }

    public static void async(final String path, final Done done) {
        new Thread(new Runnable() {
            public void run() {
                String reply = null;
                try {
                    reply = request(path);
                } catch (Throwable t) {
                    android.util.Log.e("TPRevival", "request " + path + " failed: " + t);
                }
                if (done != null) {
                    done.done(reply);
                }
            }
        }, "TPRevivalNet").start();
    }

    public static String enc(String s) {
        try {
            return URLEncoder.encode(s, "UTF-8").replace("+", "%20");
        } catch (Exception e) {
            return s;
        }
    }

    /** First <tag>value</tag> in xml, unescaped, or "" */
    public static String field(String xml, String tag) {
        if (xml == null) {
            return "";
        }
        Matcher m = Pattern.compile("<" + tag + ">([^<]*)</" + tag + ">").matcher(xml);
        return m.find() ? unescape(m.group(1)) : "";
    }

    public static ArrayList<String> blocks(String xml, String tag) {
        ArrayList<String> out = new ArrayList<String>();
        if (xml != null) {
            Matcher m = Pattern.compile("<" + tag + ">(.*?)</" + tag + ">").matcher(xml);
            while (m.find()) {
                out.add(m.group(1));
            }
        }
        return out;
    }

    static String unescape(String s) {
        return s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&");
    }

    /** Called by the game (skeleton.d.c.e.b()) after the daily bonus was collected. */
    public static void bonusCollected() {
        async("tp/bonuscollected/", null);
    }
}

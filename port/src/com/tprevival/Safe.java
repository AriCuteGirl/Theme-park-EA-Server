package com.tprevival;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.telephony.TelephonyManager;

/**
 * Android 5+ throws for implicit service intents; the 2013-era SDKs bundled in
 * the game (Google Analytics, Play billing/licensing) still use them. Every
 * bindService/startService call is rerouted here and simply fails quietly.
 * Likewise device identifiers (IMEI etc.), which throw SecurityException on
 * Android 10+ for apps like this one (the bundled ad SDK reads them).
 */
public class Safe {
    public static boolean bindService(Context c, Intent i, ServiceConnection s, int flags) {
        try {
            return c.bindService(i, s, flags);
        } catch (Throwable t) {
            return false;
        }
    }

    public static ComponentName startService(Context c, Intent i) {
        try {
            return c.startService(i);
        } catch (Throwable t) {
            return null;
        }
    }

    public static String getDeviceId(TelephonyManager t) {
        try {
            return t.getDeviceId();
        } catch (Throwable e) {
            return null;
        }
    }

    public static String getSubscriberId(TelephonyManager t) {
        try {
            return t.getSubscriberId();
        } catch (Throwable e) {
            return null;
        }
    }

    public static int getNetworkType(TelephonyManager t) {
        try {
            return t.getNetworkType();
        } catch (Throwable e) {
            return 0;
        }
    }
}

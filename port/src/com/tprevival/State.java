package com.tprevival;

import java.net.HttpURLConnection;

/**
 * EA's server computed cash, tickets and XP itself from every action. Instead,
 * every park request carries the client's own current values so the revival
 * server can store what the player actually has.
 */
public class State {
    /**
     * True from the start of a friend visit until our own park has loaded
     * again: in between, the game's cash/tickets are the friend's (and stay so
     * for a moment after the visit flag is cleared on the way home).
     */
    private static volatile boolean foreign = false;

    /** Called by the game when a park's cash/tickets are set (skeleton.d.d.a(ak)). */
    public static void parkLoaded() {
        if (!dk.progressivemedia.skeleton.i.c.i) {
            foreign = false;
        }
    }

    public static void addHeaders(HttpURLConnection c) {
        try {
            if (dk.progressivemedia.skeleton.i.c.i) {
                foreign = true;
            }
            if (foreign) {
                return;
            }
            c.setRequestProperty("tp_cash", String.valueOf(dk.progressivemedia.skeleton.d.d.a(false)));
            c.setRequestProperty("tp_tickets", String.valueOf(dk.progressivemedia.skeleton.d.d.c(false)));
            c.setRequestProperty("tp_level", String.valueOf(dk.progressivemedia.skeleton.d.d.e()));
            c.setRequestProperty("tp_xp", String.valueOf(dk.progressivemedia.skeleton.d.d.b(false)));
        } catch (Throwable t) {
            // player state not initialised yet
        }
    }
}

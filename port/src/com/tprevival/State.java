package com.tprevival;

import java.net.HttpURLConnection;

/**
 * EA's server computed cash, tickets and XP itself from every action. Instead,
 * every park request carries the client's own current values so the revival
 * server can store what the player actually has.
 */
public class State {
    public static void addHeaders(HttpURLConnection c) {
        try {
            c.setRequestProperty("tp_cash", String.valueOf(dk.progressivemedia.skeleton.d.d.a(false)));
            c.setRequestProperty("tp_tickets", String.valueOf(dk.progressivemedia.skeleton.d.d.c(false)));
            c.setRequestProperty("tp_level", String.valueOf(dk.progressivemedia.skeleton.d.d.e()));
            c.setRequestProperty("tp_xp", String.valueOf(dk.progressivemedia.skeleton.d.d.b(false)));
        } catch (Throwable t) {
            // player state not initialised yet
        }
    }
}

package com.tprevival;

import dk.progressivemedia.android.ipsp.PMiPSP;
import dk.progressivemedia.skeleton.ipsp.EASocialUser;

import java.util.ArrayList;

/**
 * Replaces skeleton.ipsp.PMiPSP.GetFriends(), which in this build only made up
 * test friends. Loads the player's friends from the server and hands them to
 * the game like EA's SDK did (iPSPReceiver.GotFriendsList -> skeleton.d.f.a).
 */
public class Friends {
    /**
     * The friend screens (Neighbor Parks, hire a friend, friend count) only work
     * for Origin accounts (account state 4). build_port.py points their state
     * check here; everything else still sees the real anonymous account.
     */
    public static int accountState() {
        return 4;
    }

    public static void fetch() {
        Net.async("tp/friends/", new Net.Done() {
            public void done(String reply) {
                ArrayList<String> rows = Net.blocks(reply, "Friend");
                final EASocialUser[] users = new EASocialUser[rows.size()];
                for (int i = 0; i < users.length; i++) {
                    String row = rows.get(i);
                    EASocialUser u = new EASocialUser();
                    u.mayhemId = Net.field(row, "mayhemId");
                    u.username = "tp" + u.mayhemId;
                    u.nucleusId = u.mayhemId;
                    u.eamobileUserId = u.mayhemId;
                    u.displayname = Net.field(row, "name");
                    u.isFriend = true;
                    u.is_app_user = true;
                    u.avatar = 0;
                    users[i] = u;
                }
                PMiPSP.runOnGame(new Runnable() {
                    public void run() {
                        dk.progressivemedia.skeleton.d.f.a(users);
                    }
                });
            }
        });
    }
}

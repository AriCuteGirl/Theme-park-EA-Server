package com.tprevival;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.view.View;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

import dk.progressivemedia.android.ipsp.PMiPSP;

import java.util.ArrayList;

/**
 * "Private Server" label at the top centre, drawn over the game view. Tapping
 * it opens the revival menu: friend code, add friends, promo codes, name.
 */
public class Brand {
    public static final String TEXT = "Theme Park Revival · Private Server ▾";

    private static Activity activity;

    public static void attach(Activity a) {
        try {
            activity = a;
            TextView t = new TextView(a);
            t.setText(TEXT);
            t.setTextSize(11f);
            t.setTextColor(0xFFFFFFFF);
            t.setShadowLayer(3f, 1f, 1f, 0xFF000000);
            t.setBackgroundColor(0x66000000);
            t.setPadding(24, 4, 24, 8);
            t.setClickable(true);
            t.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    openMenu();
                }
            });
            // WRAP_CONTENT x2, Gravity.TOP | Gravity.CENTER_HORIZONTAL
            a.addContentView(t, new FrameLayout.LayoutParams(-2, -2, 48 | 1));
        } catch (Throwable e) {
            // never let the label break start-up
        }
    }

    private static void ui(Runnable r) {
        activity.runOnUiThread(r);
    }

    private static void toast(final String msg) {
        ui(new Runnable() {
            public void run() {
                Toast.makeText(activity, msg, 1).show();
            }
        });
    }

    static void openMenu() {
        if (PMiPSP.GetMayhemSessionKey() == null) {
            toast("Not connected to the server yet.");
            return;
        }
        Net.async("tp/me/", new Net.Done() {
            public void done(final String reply) {
                if (reply == null) {
                    toast("Could not reach the server.");
                    return;
                }
                ui(new Runnable() {
                    public void run() {
                        showMenu(Net.field(reply, "name"), Net.field(reply, "code"));
                    }
                });
            }
        });
    }

    static void showMenu(final String name, final String code) {
        String[] items = {"Enter a promo code", "Add a friend", "My friends", "Change my name"};
        new AlertDialog.Builder(activity)
                .setTitle(name + "  ·  Friend code: " + code)
                .setItems(items, new DialogInterface.OnClickListener() {
                    public void onClick(DialogInterface d, int which) {
                        if (which == 0) {
                            ask("Promo code", "Type the code", "Redeem", "tp/redeem/");
                        } else if (which == 1) {
                            ask("Add a friend", "Your friend's code (theirs, not " + code + ")",
                                    "Add", "tp/addfriend/");
                        } else if (which == 2) {
                            showFriends();
                        } else {
                            ask("Change my name", name, "Save", "tp/name/");
                        }
                    }
                })
                .setNegativeButton("Close", null)
                .show();
    }

    static void ask(String title, String hint, String button, final String path) {
        final EditText input = new EditText(activity);
        input.setHint(hint);
        input.setSingleLine();
        new AlertDialog.Builder(activity)
                .setTitle(title)
                .setView(input)
                .setPositiveButton(button, new DialogInterface.OnClickListener() {
                    public void onClick(DialogInterface d, int which) {
                        String text = String.valueOf(input.getText()).trim();
                        if (text.length() > 0) {
                            send(path + Net.enc(text) + "/");
                        }
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    static void send(String path) {
        Net.async(path, new Net.Done() {
            public void done(String reply) {
                if (reply == null) {
                    toast("Could not reach the server.");
                    return;
                }
                toast(Net.field(reply, "message"));
                final int cash = parse(Net.field(reply, "cash"));
                final int tickets = parse(Net.field(reply, "tickets"));
                if (cash > 0 || tickets > 0) {
                    PMiPSP.runOnGame(new Runnable() {
                        public void run() {
                            if (cash > 0) {
                                dk.progressivemedia.skeleton.d.d.a(cash, false);
                            }
                            if (tickets > 0) {
                                dk.progressivemedia.skeleton.d.d.a(tickets);
                            }
                        }
                    });
                }
                if (Net.field(reply, "ok").equals("1")) {
                    Friends.fetch(); // refresh the game's friend list
                }
            }
        });
    }

    static void showFriends() {
        Net.async("tp/friends/", new Net.Done() {
            public void done(String reply) {
                if (reply == null) {
                    toast("Could not reach the server.");
                    return;
                }
                final ArrayList<String> rows = Net.blocks(reply, "Friend");
                ui(new Runnable() {
                    public void run() {
                        if (rows.isEmpty()) {
                            new AlertDialog.Builder(activity).setTitle("My friends")
                                    .setMessage("No friends yet. Share your friend code, or add a friend's code.")
                                    .setNegativeButton("Close", null).show();
                            return;
                        }
                        final String[] names = new String[rows.size()];
                        for (int i = 0; i < names.length; i++) {
                            names[i] = Net.field(rows.get(i), "name") + "  (level "
                                    + Net.field(rows.get(i), "level") + ")";
                        }
                        new AlertDialog.Builder(activity)
                                .setTitle("My friends · visit them from Neighbor Parks")
                                .setItems(names, new DialogInterface.OnClickListener() {
                                    public void onClick(DialogInterface d, int which) {
                                        confirmRemove(names[which], Net.field(rows.get(which), "mayhemId"));
                                    }
                                })
                                .setNegativeButton("Close", null)
                                .show();
                    }
                });
            }
        });
    }

    static void confirmRemove(String name, final String id) {
        new AlertDialog.Builder(activity)
                .setTitle("Remove " + name + " from your friends?")
                .setPositiveButton("Remove", new DialogInterface.OnClickListener() {
                    public void onClick(DialogInterface d, int which) {
                        send("tp/removefriend/" + id + "/");
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    static int parse(String s) {
        try {
            return Integer.parseInt(s);
        } catch (Exception e) {
            return 0;
        }
    }
}

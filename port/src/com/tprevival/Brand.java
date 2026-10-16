package com.tprevival;

import android.app.Activity;
import android.widget.FrameLayout;
import android.widget.TextView;

/** Small "Private Server" label at the top centre, drawn over the game view. */
public class Brand {
    public static final String TEXT = "Theme Park Revival · Private Server";

    public static void attach(Activity a) {
        try {
            TextView t = new TextView(a);
            t.setText(TEXT);
            t.setTextSize(11f);
            t.setTextColor(0xFFFFFFFF);
            t.setShadowLayer(3f, 1f, 1f, 0xFF000000);
            t.setBackgroundColor(0x66000000);
            t.setPadding(16, 2, 16, 4);
            t.setClickable(false); // taps go through to the game
            // WRAP_CONTENT x2, Gravity.TOP | Gravity.CENTER_HORIZONTAL
            a.addContentView(t, new FrameLayout.LayoutParams(-2, -2, 48 | 1));
        } catch (Throwable e) {
            // never let the label break start-up
        }
    }
}

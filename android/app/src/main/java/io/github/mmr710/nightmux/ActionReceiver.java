package io.github.mmr710.nightmux;

import android.app.NotificationManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.widget.Toast;

/** Notification buttons, and bringing alerts back after a reboot. */
public class ActionReceiver extends BroadcastReceiver {
    static final String ANSWER = "io.github.mmr710.nightmux.ANSWER", STOP = "io.github.mmr710.nightmux.STOP";

    @Override public void onReceive(Context c, Intent i) {
        String a = String.valueOf(i.getAction());
        if (a.equals(Intent.ACTION_BOOT_COMPLETED) || a.equals(Intent.ACTION_MY_PACKAGE_REPLACED)) {
            AlertService.sync(c);
        } else if (a.equals(STOP)) {
            c.getSharedPreferences("nightmux", Context.MODE_PRIVATE).edit().putBoolean("alerts", false).apply();
            AlertService.sync(c);
        } else if (a.equals(ANSWER)) {
            PendingResult pr = goAsync();
            new Thread(() -> {
                boolean ok = Office.send(i.getStringExtra("base"), i.getStringExtra("topic"), i.getStringExtra("text"));
                c.getSystemService(NotificationManager.class).cancel(i.getIntExtra("id", 0));
                new android.os.Handler(c.getMainLooper()).post(() ->
                        Toast.makeText(c, ok ? "sent ✓" : "couldn't reach nightmux", Toast.LENGTH_SHORT).show());
                pr.finish();
            }).start();
        }
    }
}

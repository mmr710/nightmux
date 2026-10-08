package io.github.mmr710.nightmux;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.DateFormat;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

/**
 * Watches /api/office while alerts are on and notifies on the moments that
 * matter: an agent finished, needs an answer, or hit its usage limit.
 * Polling, not push: the daemon lives on a tailnet with no route in from FCM.
 */
public class AlertService extends Service {
    static final String LIVE = "live", NEWS = "news", ASK = "ask";
    static final int ONGOING = 1;
    static final long EVERY_MS = 15000;

    volatile boolean running;
    final Map<String, String> last = new HashMap<>();
    boolean primed;
    String watching = "";

    static void sync(Context c) {
        SharedPreferences p = c.getSharedPreferences("nightmux", MODE_PRIVATE);
        Intent i = new Intent(c, AlertService.class);
        if (p.getBoolean("alerts", false) && !p.getString("url", "").isEmpty()) c.startForegroundService(i);
        else c.stopService(i);
    }

    static void channels(Context c) {
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(LIVE, "Live status", NotificationManager.IMPORTANCE_MIN));
        nm.createNotificationChannel(new NotificationChannel(NEWS, "Finished and limits", NotificationManager.IMPORTANCE_DEFAULT));
        nm.createNotificationChannel(new NotificationChannel(ASK, "Agent needs you", NotificationManager.IMPORTANCE_HIGH));
    }

    static PendingIntent openApp(Context c) {
        return PendingIntent.getActivity(c, 0, new Intent(c, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE);
    }

    @Override public IBinder onBind(Intent i) { return null; }

    @Override public int onStartCommand(Intent intent, int flags, int id) {
        channels(this);
        Notification n = ongoing("connecting…");
        if (Build.VERSION.SDK_INT >= 34) startForeground(ONGOING, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(ONGOING, n);
        if (!running) {
            running = true;
            new Thread(this::loop, "nightmux-alerts").start();
        }
        return START_STICKY;
    }

    @Override public void onDestroy() { running = false; super.onDestroy(); }

    Notification ongoing(String text) {
        Intent stop = new Intent(this, ActionReceiver.class).setAction(ActionReceiver.STOP);
        return new Notification.Builder(this, LIVE)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("nightmux")
                .setContentText(text)
                .setOngoing(true)
                .setContentIntent(openApp(this))
                .addAction(new Notification.Action.Builder(null, "Stop alerts",
                        PendingIntent.getBroadcast(this, 0, stop, PendingIntent.FLAG_IMMUTABLE)).build())
                .build();
    }

    void loop() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        while (running) {
            String base = getSharedPreferences("nightmux", MODE_PRIVATE).getString("url", "");
            if (!base.equals(watching)) { watching = base; last.clear(); primed = false; }   // switched servers
            try {
                JSONObject o = Office.fetch(base);
                nm.notify(ONGOING, ongoing(Office.summary(o)));
                OfficeWidget.push(this, o);
                diff(nm, base, o);
            } catch (Exception e) {
                nm.notify(ONGOING, ongoing("can't reach " + base));
            }
            try { Thread.sleep(EVERY_MS); } catch (InterruptedException e) { return; }
        }
    }

    /** The first poll only learns the current states; alerts are for changes after that. */
    void diff(NotificationManager nm, String base, JSONObject o) {
        JSONArray rooms = o.optJSONArray("rooms");
        for (int i = 0; rooms != null && i < rooms.length(); i++) {
            JSONObject r = rooms.optJSONObject(i);
            JSONArray desks = r.optJSONArray("desks");
            for (int j = 0; desks != null && j < desks.length(); j++) {
                JSONObject d = desks.optJSONObject(j);
                String sess = d.optString("session"), now = d.optString("state"), was = last.put(sess, now);
                if (!primed || now.equals(was)) continue;
                String who = r.optString("name") + " · " + d.optString("agent");
                if (now.equals("waiting")) ask(nm, base, r.optString("topic"), sess, who, d);
                else if (now.equals("limit")) news(nm, sess, "🛑 " + who + " hit its limit",
                        d.isNull("until") ? "" : "back at " + DateFormat.getTimeInstance(DateFormat.SHORT)
                                .format(new Date((long) (d.optDouble("until") * 1000))));
                else if (now.equals("idle") && ("busy".equals(was) || "waiting".equals(was)))
                    news(nm, sess, "✅ " + who + " is done", "Tap to see what it did.");
                else if ("waiting".equals(was)) nm.cancel(sess.hashCode());
            }
        }
        primed = true;
    }

    void news(NotificationManager nm, String sess, String title, String text) {
        nm.notify(sess.hashCode(), new Notification.Builder(this, NEWS)
                .setSmallIcon(R.drawable.ic_stat).setContentTitle(title).setContentText(text)
                .setAutoCancel(true).setContentIntent(openApp(this)).build());
    }

    /** An approval or menu: its first three choices become buttons on the notification. */
    void ask(NotificationManager nm, String base, String topic, String sess, String who, JSONObject d) {
        Notification.Builder b = new Notification.Builder(this, ASK)
                .setSmallIcon(R.drawable.ic_stat).setContentTitle("⏸ " + who + " needs you")
                .setContentText("Answer here or open the office.")
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setAutoCancel(true).setContentIntent(openApp(this));
        JSONArray opts = d.optJSONArray("options");
        for (int k = 0; opts != null && k < Math.min(3, opts.length()); k++) {
            JSONObject op = opts.optJSONObject(k);
            Intent act = new Intent(this, ActionReceiver.class).setAction(ActionReceiver.ANSWER)
                    .putExtra("base", base).putExtra("topic", topic)
                    .putExtra("text", op.optString("send")).putExtra("id", sess.hashCode());
            PendingIntent pi = PendingIntent.getBroadcast(this, sess.hashCode() * 4 + k, act,
                    PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            Notification.Action.Builder ab = new Notification.Action.Builder(null, op.optString("text"), pi);
            // Answering an agent can run commands: never from a locked phone.
            if (Build.VERSION.SDK_INT >= 31) ab.setAuthenticationRequired(true);
            b.addAction(ab.build());
        }
        nm.notify(sess.hashCode(), b.build());
    }
}

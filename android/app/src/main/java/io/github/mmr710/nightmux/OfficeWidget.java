package io.github.mmr710.nightmux;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.widget.RemoteViews;

import org.json.JSONObject;

/** The office in miniature on the home screen: a tile per agent, colored by state. */
public class OfficeWidget extends AppWidgetProvider {
    @Override public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        String base = c.getSharedPreferences("nightmux", Context.MODE_PRIVATE).getString("url", "");
        PendingResult pr = goAsync();
        new Thread(() -> {
            try { push(c, Office.fetch(base)); }
            catch (Exception e) { show(c, null, base.isEmpty() ? "open the app to connect" : "can't reach nightmux"); }
            pr.finish();
        }).start();
    }

    static void push(Context c, JSONObject o) { show(c, o, Office.summary(o)); }

    static void show(Context c, JSONObject o, String line) {
        AppWidgetManager m = AppWidgetManager.getInstance(c);
        int[] ids = m.getAppWidgetIds(new ComponentName(c, OfficeWidget.class));
        if (ids.length == 0) return;
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget);
        v.setTextViewText(R.id.line, line);
        if (o != null) v.setImageViewBitmap(R.id.office, Office.render(o, c.getResources().getDisplayMetrics().density));
        v.setOnClickPendingIntent(R.id.root, AlertService.openApp(c));
        m.updateAppWidget(ids, v);
    }
}

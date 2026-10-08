package io.github.mmr710.nightmux;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/** Talking to the daemon, and drawing the office small enough for a widget. */
final class Office {
    private Office() { }

    static JSONObject fetch(String base) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(base + "/api/office").openConnection();
        c.setConnectTimeout(5000);
        c.setReadTimeout(8000);
        try (InputStream in = c.getInputStream()) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            for (int n; (n = in.read(buf)) > 0; ) out.write(buf, 0, n);
            return new JSONObject(out.toString("UTF-8"));
        } finally {
            c.disconnect();
        }
    }

    /** Same request the office page makes when a button is tapped. */
    static boolean send(String base, String topic, String text) {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(base + "/topic/" + topic).openConnection();
            c.setConnectTimeout(5000);
            c.setReadTimeout(8000);
            c.setRequestMethod("POST");
            c.setRequestProperty("X-Nightmux", "1");
            c.setDoOutput(true);
            try (OutputStream o = c.getOutputStream()) { o.write(text.getBytes(StandardCharsets.UTF_8)); }
            int code = c.getResponseCode();
            c.disconnect();
            return code / 100 == 2;
        } catch (Exception e) {
            return false;
        }
    }

    static int color(String state) {
        switch (state) {
            case "busy": return Color.parseColor("#9ece6a");
            case "waiting": return Color.parseColor("#f5c542");
            case "limit": return Color.parseColor("#f7768e");
            case "idle": return Color.parseColor("#565f89");
            default: return Color.parseColor("#2a2f3d");
        }
    }

    /** "2 working · 1 needs you · 1 at limit" */
    static String summary(JSONObject o) {
        int busy = 0, wait = 0, lim = 0, idle = 0;
        JSONArray rooms = o.optJSONArray("rooms");
        for (int i = 0; rooms != null && i < rooms.length(); i++) {
            JSONArray desks = rooms.optJSONObject(i).optJSONArray("desks");
            for (int j = 0; desks != null && j < desks.length(); j++) {
                switch (desks.optJSONObject(j).optString("state")) {
                    case "busy": busy++; break;
                    case "waiting": wait++; break;
                    case "limit": lim++; break;
                    case "idle": idle++; break;
                    default: break;
                }
            }
        }
        StringBuilder b = new StringBuilder();
        if (busy > 0) b.append(busy).append(" working");
        if (wait > 0) b.append(b.length() > 0 ? " · " : "").append(wait).append(" need you");
        if (lim > 0) b.append(b.length() > 0 ? " · " : "").append(lim).append(" at limit");
        if (b.length() == 0) b.append(idle > 0 ? "all quiet · " + idle + " idle" : "no agents");
        return b.toString();
    }

    /** One row per room: its name, then a tile per agent colored by what it is doing. */
    static Bitmap render(JSONObject o, float density) {
        JSONArray rooms = o.optJSONArray("rooms");
        int n = rooms == null ? 0 : Math.min(rooms.length(), 8);
        float u = density, row = 26 * u, tile = 18 * u, nameW = 110 * u, w = 320 * u;
        Bitmap bm = Bitmap.createBitmap((int) w, (int) Math.max(row, n * row), Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bm);
        Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
        text.setColor(Color.parseColor("#c0caf5"));
        text.setTextSize(12 * u);
        Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
        Paint letter = new Paint(Paint.ANTI_ALIAS_FLAG);
        letter.setColor(Color.parseColor("#0b0e14"));
        letter.setTextSize(11 * u);
        letter.setFakeBoldText(true);
        letter.setTextAlign(Paint.Align.CENTER);
        if (n == 0) cv.drawText("no rooms yet", 0, 16 * u, text);
        for (int i = 0; i < n; i++) {
            JSONObject r = rooms.optJSONObject(i);
            float y = i * row;
            String name = r.optString("name");
            if (name.length() > 14) name = name.substring(0, 13) + "…";
            cv.drawText(name, 0, y + 17 * u, text);
            JSONArray desks = r.optJSONArray("desks");
            for (int j = 0; desks != null && j < desks.length() && nameW + (j + 1) * (tile + 4 * u) < w; j++) {
                JSONObject d = desks.optJSONObject(j);
                float x = nameW + j * (tile + 4 * u);
                fill.setColor(color(d.optString("state")));
                cv.drawRoundRect(new RectF(x, y + 3 * u, x + tile, y + 3 * u + tile), 4 * u, 4 * u, fill);
                String a = d.optString("agent");
                if (!a.isEmpty()) cv.drawText(a.substring(0, 1).toUpperCase(java.util.Locale.ROOT), x + tile / 2, y + 16 * u, letter);
            }
        }
        return bm;
    }
}

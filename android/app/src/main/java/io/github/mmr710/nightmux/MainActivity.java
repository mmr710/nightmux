package io.github.mmr710.nightmux;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;

/** A thin native shell around the daemon's own pages: office, chat, dashboard. */
public class MainActivity extends Activity {
    static final String[][] TABS = {{"Office", "/office"}, {"Chat", "/chat"}, {"Dashboard", "/"}};
    static final int FILES = 1, MIC = 2, NOTIFY = 3;

    SharedPreferences prefs;
    WebView web;
    LinearLayout bar;
    boolean ambient;
    ValueCallback<Uri[]> pendingFiles;
    PermissionRequest pendingMic;

    @Override protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        prefs = getSharedPreferences("nightmux", MODE_PRIVATE);
        getWindow().setStatusBarColor(Color.parseColor("#0b0e14"));
        getWindow().setNavigationBarColor(Color.parseColor("#0b0e14"));

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#0b0e14"));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setUserAgentString(s.getUserAgentString() + " NightmuxApp/" + BuildConfig.VERSION_NAME);
        web.setWebViewClient(new Client());
        web.setWebChromeClient(new Chrome());
        web.setDownloadListener((url, ua, cd, mime, len) -> open(url));

        bar = new LinearLayout(this);
        bar.setBackgroundColor(Color.parseColor("#11151f"));
        for (String[] t : TABS) bar.addView(button(t[0], v -> go(t[1])));
        bar.addView(button("☾", v -> setAmbient(true)));
        bar.addView(button("⚙", v -> askServer(base())));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.addView(web, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        root.addView(bar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        root.setOnApplyWindowInsetsListener((v, in) -> {
            if (!ambient) v.setPadding(0, in.getSystemWindowInsetTop(), 0, in.getSystemWindowInsetBottom());
            else v.setPadding(0, 0, 0, 0);
            return in;
        });
        setContentView(root);

        if (saved != null && web.restoreState(saved) != null) return;
        if (handleLink(getIntent())) return;
        if (base().isEmpty()) askServer("");
        else go(prefs.getString("tab", "/office"));
    }

    Button button(String label, View.OnClickListener l) {
        Button b = new Button(this, null, android.R.attr.borderlessButtonStyle);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextColor(Color.parseColor("#c0caf5"));
        b.setOnClickListener(l);
        b.setLayoutParams(new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT,
                label.length() > 1 ? 3 : 1));
        return b;
    }

    String base() { return prefs.getString("url", ""); }

    void go(String path) {
        prefs.edit().putString("tab", path).apply();
        web.loadUrl(base() + path);
    }

    static String clean(String u) {
        u = u.trim();
        while (u.endsWith("/")) u = u.substring(0, u.length() - 1);
        if (!u.isEmpty() && !u.startsWith("http://") && !u.startsWith("https://")) u = "http://" + u;
        return u;
    }

    void askServer(String current) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(48, 8, 48, 0);
        EditText e = new EditText(this);
        e.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        e.setHint("https://box.tailnet.ts.net  or  100.64.0.1:9090");
        e.setText(current);
        CheckBox alerts = new CheckBox(this);
        alerts.setText("Alerts: done, needs you, limits (also feeds the widget live)");
        alerts.setChecked(prefs.getBoolean("alerts", false));
        box.addView(e);
        box.addView(alerts);
        new AlertDialog.Builder(this)
                .setTitle("nightmux server")
                .setMessage("The address of your dashboard. Reach it over Tailscale or your LAN; "
                        + "nightmux has no login of its own, so never expose it to the open internet.")
                .setView(box)
                .setCancelable(!base().isEmpty())
                .setPositiveButton("Connect", (d, w) -> {
                    prefs.edit().putBoolean("alerts", alerts.isChecked()).apply();
                    if (alerts.isChecked() && android.os.Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                            != PackageManager.PERMISSION_GRANTED)
                        requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, NOTIFY);
                    save(clean(e.getText().toString()));
                })
                .show();
    }

    void save(String url) {
        if (url.isEmpty()) { askServer(""); return; }
        prefs.edit().putString("url", url).apply();
        AlertService.sync(this);
        web.clearHistory();
        go(prefs.getString("tab", "/office"));
    }

    /** nightmux://connect?url=… from /app. A link can come from anywhere, so ask first. */
    boolean handleLink(Intent i) {
        Uri u = i == null ? null : i.getData();
        if (u == null || !"nightmux".equals(u.getScheme())) return false;
        String q = u.getQueryParameter("url");
        String url = clean(q == null ? "" : q);
        if (url.isEmpty()) return false;
        new AlertDialog.Builder(this)
                .setTitle("Connect to this server?")
                .setMessage(url + "\n\nOnly say yes if this is your own nightmux.")
                .setPositiveButton("Connect", (d, w) -> save(url))
                .setNegativeButton("Cancel", (d, w) -> { if (base().isEmpty()) askServer(""); })
                .show();
        return true;
    }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        if (!handleLink(i) && ambient) setAmbient(false);
    }

    void open(String url) {
        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) { }
    }

    /** Ambient: the office as a night-light on a spare phone. Full screen, screen stays on. */
    void setAmbient(boolean on) {
        ambient = on;
        bar.setVisibility(on ? View.GONE : View.VISIBLE);
        WindowInsetsController c = getWindow().getInsetsController();
        if (on) {
            go("/office");
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
            if (c != null) {
                c.hide(WindowInsets.Type.systemBars());
                c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
            if (c != null) c.show(WindowInsets.Type.systemBars());
        }
        getWindow().getDecorView().requestApplyInsets();
    }

    @Override public void onBackPressed() {
        if (ambient) setAmbient(false);
        else if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    boolean ours(Uri u) {
        Uri b = Uri.parse(base());
        return u.getHost() != null && u.getHost().equals(b.getHost()) && u.getPort() == b.getPort();
    }

    class Client extends WebViewClient {
        @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
            if (ours(r.getUrl())) return false;
            open(r.getUrl().toString());     // GitHub, tweet intents, Telegram: the real apps
            return true;
        }

        @Override public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
            if (!r.isForMainFrame() || isFinishing()) return;
            new AlertDialog.Builder(MainActivity.this)
                    .setTitle("Can't reach nightmux")
                    .setMessage(base() + "\n\n" + e.getDescription()
                            + "\n\nIs the daemon running, and is this phone on the same tailnet?")
                    .setPositiveButton("Retry", (d, w) -> web.reload())
                    .setNegativeButton("Change server", (d, w) -> askServer(base()))
                    .show();
        }
    }

    class Chrome extends WebChromeClient {
        @Override public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
            if (pendingFiles != null) pendingFiles.onReceiveValue(null);
            pendingFiles = cb;
            try { startActivityForResult(p.createIntent(), FILES); }
            catch (Exception ex) { pendingFiles = null; cb.onReceiveValue(null); }
            return true;
        }

        /** Voice notes: the microphone, and only for the configured server. */
        @Override public void onPermissionRequest(PermissionRequest r) {
            boolean micOnly = true;
            for (String res : r.getResources())
                if (!PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(res)) micOnly = false;
            if (!micOnly || !ours(r.getOrigin())) { r.deny(); return; }
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                r.grant(r.getResources());
            } else {
                pendingMic = r;
                requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, MIC);
            }
        }
    }

    @Override public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
        if (code == NOTIFY) { AlertService.sync(this); return; }
        if (code != MIC || pendingMic == null) return;
        if (res.length > 0 && res[0] == PackageManager.PERMISSION_GRANTED) pendingMic.grant(pendingMic.getResources());
        else pendingMic.deny();
        pendingMic = null;
    }

    @Override protected void onActivityResult(int code, int result, Intent data) {
        if (code != FILES || pendingFiles == null) { super.onActivityResult(code, result, data); return; }
        pendingFiles.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result, data));
        pendingFiles = null;
    }
}

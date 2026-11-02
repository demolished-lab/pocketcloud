package org.pocketcloud.supervisor;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int REQ_NOTIFICATIONS = 31;
    private static final String TERMUX_PERMISSION = "com.termux.permission.RUN_COMMAND";
    private final ExecutorService pairingExecutor = Executors.newSingleThreadExecutor();
    private LinearLayout root;
    private TextView pairedText;
    private PairInvite pendingInvite;
    private String pendingAction;
    private boolean checkingTermuxSettings;
    private static final String HOME = "/data/data/com.termux/files/home";
    private static final String SCRIPT_PATH = HOME + "/pocketcloud/scripts/termux/supervisor.sh";

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        buildUi();
        if (!isSafeFixedScriptPath(SCRIPT_PATH)) throw new IllegalStateException("Invalid built-in Termux script path");
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setPadding(dp(20), dp(22), dp(20), dp(26));
        scroll.addView(root);
        TextView title = text("PocketCloud Supervisor", 25, true); root.addView(title);
        TextView intro = text("Controls the PocketCloud runtime installed in Termux. Nothing starts automatically; use the visible controls below.", 15, false); intro.setPadding(0, dp(8), 0, dp(18)); root.addView(intro);
        Button start = button("Start local supervisor"); root.addView(start); start.setOnClickListener(v -> requestStart());
        Button stop = button("Stop local supervisor"); root.addView(stop); stop.setOnClickListener(v -> requestTermuxPermission("stop"));
        Button scan = button("Scan laptop pairing QR"); root.addView(scan); scan.setOnClickListener(v -> new IntentIntegrator(this).setDesiredBarcodeFormats(IntentIntegrator.QR_CODE).setPrompt("Scan the PocketCloud laptop invitation").setBeepEnabled(false).setOrientationLocked(false).initiateScan());
        TextView setupTitle = text("One-time Termux setup", 18, true); setupTitle.setPadding(0, dp(18), 0, dp(4)); root.addView(setupTitle);
        TextView setup = text("1. Install Termux 0.109 or later and the repository checkout/dependencies there.\n2. Ensure this fixed script exists and is executable:\n" + SCRIPT_PATH + "\n3. In Termux, enable external apps by adding `allow-external-apps=true` to ~/.termux/termux.properties, then run `termux-reload-settings`.\n4. In Android Settings, manually grant PocketCloud the “Run commands in Termux” permission under Apps → PocketCloud → Permissions → Additional permissions.\n\nOnly this fixed script and the start/stop/status verbs are sent. QR/network input is never used as a command. Termux completion must be returned for status/stop confirmation. Android may stop services according to its background and battery policies.", 14, false); setup.setPadding(0, dp(4), 0, dp(14)); root.addView(setup);
        TextView pairTitle = text("Pairing", 18, true); root.addView(pairTitle);
        pairedText = text("No paired laptop is stored.", 14, false); pairedText.setPadding(0, dp(5), 0, 0); root.addView(pairedText);
        setContentView(scroll);
        refreshPairedText();
    }

    private TextView text(String value, int size, boolean bold) {
        TextView t = new TextView(this); t.setText(value); t.setTextSize(size); t.setTextColor(0xff202124); t.setGravity(Gravity.START);
        if (bold) t.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return t;
    }
    private Button button(String value) { Button b = new Button(this); b.setText(value); return b; }
    private int dp(int value) { return (int) (value * getResources().getDisplayMetrics().density + 0.5f); }

    private void requestStart() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            new AlertDialog.Builder(this).setTitle("Notifications are required")
                    .setMessage("The supervisor must show an ongoing notification with a Stop action. Allow notifications to start it; otherwise start is blocked.")
                    .setNegativeButton("Cancel", null).setPositiveButton("Continue", (d, w) -> requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFICATIONS)).show();
            return;
        }
        requestTermuxPermission("start");
    }

    private void requestTermuxPermission(String action) {
        if (!isSafeFixedScriptPath(SCRIPT_PATH)) { showTermuxSetup("The built-in script path failed safety validation."); return; }
        try { getPackageManager().getPackageInfo("com.termux", 0); }
        catch (PackageManager.NameNotFoundException e) { showTermuxSetup("Termux is not installed or its package is not visible. Install the supported Termux app, configure the script, and retry."); return; }
        if (checkSelfPermission(TERMUX_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            pendingAction = action;
            new AlertDialog.Builder(this).setTitle("Allow Termux commands")
                    .setMessage("Termux requires this permission to be granted manually in Android Settings. Open PocketCloud's app settings, then enable ‘Run commands in Termux’ under Permissions → Additional permissions. Return here to continue.")
                    .setNegativeButton("Cancel", (d, w) -> pendingAction = null)
                    .setPositiveButton("Open PocketCloud settings", (d, w) -> {
                        checkingTermuxSettings = true;
                        Intent settings = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName()));
                        startActivity(settings);
                    }).show();
            return;
        }
        launchSupervisor(action);
    }

    private void launchSupervisor(String action) {
        Intent intent = new Intent(this, SupervisorService.class).setAction(SupervisorService.actionFor(action));
        try {
            if ("start".equals(action)) {
                if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent); else startService(intent);
                Toast.makeText(this, "Starting Termux supervisor. See the ongoing notification for status.", Toast.LENGTH_LONG).show();
            } else {
                if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent); else startService(intent);
                Toast.makeText(this, "Sending the fixed Termux " + action + " action.", Toast.LENGTH_SHORT).show();
            }
        } catch (SecurityException | IllegalStateException e) { showTermuxSetup("Android or Termux rejected the request: " + e.getClass().getSimpleName()); }
    }

    private static boolean isSafeFixedScriptPath(String path) {
        if (path == null || !path.startsWith(HOME + "/") || path.contains("..") || !path.matches("/data/data/com\\.termux/files/home/[A-Za-z0-9._/-]+")) return false;
        for (String part : path.substring((HOME + "/").length()).split("/")) if (part.isEmpty() || part.equals(".") || part.equals("..")) return false;
        return path.endsWith("/supervisor.sh");
    }

    private void showTermuxSetup(String why) {
        new AlertDialog.Builder(this).setTitle("Termux setup required")
                .setMessage(why + "\n\nIn Termux enable `allow-external-apps=true` in ~/.termux/termux.properties and run `termux-reload-settings`. Manually grant `com.termux.permission.RUN_COMMAND` in PocketCloud's Android app settings. Check that " + SCRIPT_PATH + " exists and is executable. No command was run.")
                .setNegativeButton("Close", null)
                .setPositiveButton("Open PocketCloud settings", (d, w) -> startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName())))).show();
    }

    @Override protected void onResume() {
        super.onResume();
        if (checkingTermuxSettings) {
            checkingTermuxSettings = false;
            String action = pendingAction;
            pendingAction = null;
            if (action != null && checkSelfPermission(TERMUX_PERMISSION) == PackageManager.PERMISSION_GRANTED) launchSupervisor(action);
            else if (action != null) showTermuxSetup("The Termux RUN_COMMAND permission is still not granted.");
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        if (requestCode == REQ_NOTIFICATIONS) {
            if (granted) requestTermuxPermission("start");
            else new AlertDialog.Builder(this).setTitle("Start blocked").setMessage("Notifications are denied. The app blocks supervisor start because it cannot guarantee the required visible ongoing notification and Stop action. Enable notifications in Android app settings, then retry.").setPositiveButton("OK", null).show();
        }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, android.content.Intent data) {
        IntentResult result = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (result != null) {
            if (result.getContents() == null) Toast.makeText(this, "QR scan cancelled.", Toast.LENGTH_SHORT).show();
            else handleInvite(result.getContents());
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    private void handleInvite(String raw) {
        final PairInvite invite;
        try { invite = PairInvite.parse(raw); }
        catch (IllegalArgumentException e) { new AlertDialog.Builder(this).setTitle("Invalid invitation").setMessage(e.getMessage()).setPositiveButton("OK", null).show(); return; }
        pendingInvite = invite;
        String address = invite.host.contains(":") ? "[" + invite.host + "]" : invite.host;
        String fingerprint;
        try { fingerprint = PairingProtocol.colonHex(android.util.Base64.decode(invite.spkiSha256, android.util.Base64.URL_SAFE | android.util.Base64.NO_PADDING | android.util.Base64.NO_WRAP)); }
        catch (RuntimeException e) { Toast.makeText(this, "Invalid invitation fingerprint.", Toast.LENGTH_LONG).show(); return; }
        EditText name = new EditText(this); name.setSingleLine(true); name.setText("Android phone"); name.setSelection(name.length()); name.setHint("Phone name (1–64 printable characters)");
        LinearLayout content = new LinearLayout(this); content.setOrientation(LinearLayout.VERTICAL); content.setPadding(dp(24), dp(4), dp(24), 0);
        TextView review = text("Laptop: " + invite.laptopName + "\nAddress: " + address + ":" + invite.port + "\nSPKI SHA-256: " + fingerprint + "\n\nNo network request will be made unless you approve. Verify this laptop and fingerprint out of band.", 14, false);
        content.addView(review); content.addView(name);
        new AlertDialog.Builder(this).setTitle("Review laptop pairing").setView(content).setNegativeButton("Cancel", (d, w) -> pendingInvite = null)
                .setPositiveButton("Approve and pair", (d, w) -> {
                    PairInvite selected = pendingInvite; pendingInvite = null;
                    if (selected != null) submitPairing(selected, name.getText().toString());
                }).show();
    }

    private void submitPairing(PairInvite invite, String phoneName) {
        try { PairingClient.validatePhoneName(phoneName); }
        catch (IllegalArgumentException e) { new AlertDialog.Builder(this).setTitle("Invalid phone name").setMessage(e.getMessage()).setPositiveButton("OK", null).show(); return; }
        final AlertDialog progress = new AlertDialog.Builder(this).setTitle("Pairing").setMessage("Connecting to the pinned laptop. Waiting for the laptop operator's approval…").setCancelable(false).create();
        progress.show();
        pairingExecutor.execute(() -> {
            Exception failure = null;
            try { PairingClient.pair(getApplicationContext(), invite, phoneName); }
            catch (Exception e) { failure = e; }
            final Exception result = failure;
            runOnUiThread(() -> {
                progress.dismiss();
                if (result == null) { refreshPairedText(); new AlertDialog.Builder(this).setTitle("Paired").setMessage("Laptop pairing was accepted. The server's approval response and identity were verified.").setPositiveButton("OK", null).show(); }
                else new AlertDialog.Builder(this).setTitle("Pairing failed").setMessage("Pairing was not saved. Check the invitation expiry, LAN reachability, certificate pin, and laptop approval, then scan a fresh QR.").setPositiveButton("OK", null).show();
            });
        });
    }

    private void refreshPairedText() {
        if (pairedText == null) return;
        android.content.SharedPreferences p = getSharedPreferences("paired_peers", MODE_PRIVATE);
        String laptop = p.getString("laptop_id", null), phone = p.getString("phone_id", null), pin = p.getString("laptop_spki_sha256", null);
        pairedText.setText(laptop == null ? "No paired laptop is stored." : "Laptop ID: " + laptop + "\nPhone ID: " + phone + "\nPublic laptop SPKI pin (base64url): " + pin);
    }
}

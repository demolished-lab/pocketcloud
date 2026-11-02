package org.pocketcloud.supervisor;

import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class SupervisorService extends Service {
    private static final String CHANNEL = "pocketcloud_supervisor";
    private static final int NOTIFICATION_ID = 4101;
    private static final String TERMUX_PACKAGE = "com.termux";
    private static final String BASH = "/data/data/com.termux/files/usr/bin/bash";
    private static final String TERMUX_HOME = "/data/data/com.termux/files/home";
    private static final String SCRIPT = TERMUX_HOME + "/pocketcloud/scripts/termux/supervisor.sh";
    private static final String ACTION_TERMUX_RESULT = "org.pocketcloud.supervisor.TERMUX_RESULT";
    private static final String TERMUX_PENDING_INTENT = "com.termux.RUN_COMMAND_PENDING_INTENT";
    private static final String TERMUX_RESULT_BUNDLE = "result";
    private static final String TERMUX_RESULT_EXIT_CODE = "exitCode";
    private static final String TERMUX_RESULT_ERROR = "err";
    private static final int TERMUX_RESULT_TIMEOUT_MS = 30_000;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final ConcurrentHashMap<String, String> pendingCommands = new ConcurrentHashMap<>();

    public static String actionFor(String verb) {
        return "org.pocketcloud.supervisor." + verb.toUpperCase(java.util.Locale.ROOT);
    }

    @Override public void onCreate() {
        super.onCreate();
        createChannel();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_TERMUX_RESULT.equals(intent.getAction())) {
            handleTermuxResult(intent);
            return START_NOT_STICKY;
        }
        String action = intent == null ? null : intent.getAction();
        String verb = action == null ? "" : action.substring(action.lastIndexOf('.') + 1).toLowerCase(java.util.Locale.ROOT);
        if (!verb.equals("start") && !verb.equals("stop") && !verb.equals("status")) {
            stopSelf(startId);
            return START_NOT_STICKY;
        }
        try {
            startOngoing("Preparing Termux " + verb + "…");
        } catch (RuntimeException e) {
            stopSelf(startId);
            return START_NOT_STICKY;
        }
        executor.execute(() -> runTermux(verb));
        return START_NOT_STICKY;
    }

    private void startOngoing(String text) {
        Notification n = notification(text);
        if (Build.VERSION.SDK_INT >= 34) startForeground(NOTIFICATION_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(NOTIFICATION_ID, n);
    }

    private Notification notification(String text) {
        Intent stopIntent = new Intent(this, SupervisorService.class).setAction(actionFor("stop"));
        PendingIntent stop = PendingIntent.getService(this, 2, stopIntent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        return builder
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle("PocketCloud local supervisor")
                .setContentText(text)
                .setOngoing(true)
                .setCategory(Notification.CATEGORY_SERVICE)
                .addAction(new Notification.Action.Builder(android.R.drawable.ic_media_pause, "Stop", stop).build())
                .build();
    }

    private void runTermux(String verb) {
        String requestId = UUID.randomUUID().toString();
        try {
            if (!safeScriptPath(SCRIPT)) throw new SecurityException("Unsafe built-in script path");
            Intent callbackIntent = new Intent(this, SupervisorService.class)
                    .setAction(ACTION_TERMUX_RESULT)
                    .setData(Uri.parse("pocketcloud://termux-result/" + requestId));
            int callbackFlags = PendingIntent.FLAG_ONE_SHOT;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) callbackFlags |= PendingIntent.FLAG_MUTABLE;
            PendingIntent callback = PendingIntent.getService(this, 0, callbackIntent, callbackFlags);

            Intent run = new Intent("com.termux.RUN_COMMAND");
            run.setComponent(new ComponentName(TERMUX_PACKAGE, "com.termux.app.RunCommandService"));
            run.putExtra("com.termux.RUN_COMMAND_PATH", BASH);
            run.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{SCRIPT, verb});
            run.putExtra("com.termux.RUN_COMMAND_WORKDIR", TERMUX_HOME);
            run.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
            run.putExtra(TERMUX_PENDING_INTENT, callback);
            pendingCommands.put(requestId, verb);
            startService(run);

            Handler main = new Handler(getMainLooper());
            main.postDelayed(() -> {
                if (pendingCommands.remove(requestId) != null) {
                    notifyOngoing("No result from Termux; command outcome is not confirmed. Check Termux version (0.109+) and permissions.");
                }
            }, TERMUX_RESULT_TIMEOUT_MS);
        } catch (SecurityException e) {
            pendingCommands.remove(requestId);
            notifyOngoing("Termux permission/settings required; see PocketCloud setup");
        } catch (Exception e) {
            pendingCommands.remove(requestId);
            notifyOngoing("Termux unavailable; command outcome is not confirmed. Check setup and fixed script path");
        }
    }

    private void handleTermuxResult(Intent intent) {
        Uri data = intent.getData();
        String requestId = data == null ? null : data.getLastPathSegment();
        String verb = requestId == null ? null : pendingCommands.remove(requestId);
        if (verb == null) return;

        Bundle result = intent.getBundleExtra(TERMUX_RESULT_BUNDLE);
        if (result == null) {
            notifyOngoing("Termux returned no command result; outcome is not confirmed");
            return;
        }
        int internalError = result.getInt(TERMUX_RESULT_ERROR, Activity.RESULT_OK);
        int exitCode = result.getInt(TERMUX_RESULT_EXIT_CODE, Integer.MIN_VALUE);
        if (internalError != Activity.RESULT_OK || exitCode == Integer.MIN_VALUE) {
            notifyOngoing("Termux could not confirm the " + verb + " command; check Termux notifications and permissions");
            return;
        }
        if (verb.equals("stop") && exitCode == 0) {
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
            return;
        }
        if (exitCode == 0) {
            String message = verb.equals("start") ? "PocketCloud runtime is ready on loopback"
                    : verb.equals("status") ? "PocketCloud runtime is ready on loopback"
                    : "Termux command completed";
            notifyOngoing(message);
        } else if (verb.equals("status") && exitCode == 3) {
            notifyOngoing("PocketCloud runtime is not running; use Start in the app");
        } else {
            notifyOngoing("Termux " + verb + " failed (exit " + exitCode + "); outcome is not confirmed");
        }
    }

    private void notifyOngoing(String text) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        nm.notify(NOTIFICATION_ID, notification(text));
    }

    private static boolean safeScriptPath(String path) {
        if (path == null || !path.startsWith(TERMUX_HOME + "/") || path.contains("..") || !path.matches("/data/data/com\\.termux/files/home/[A-Za-z0-9._/-]+")) return false;
        for (String part : path.substring((TERMUX_HOME + "/").length()).split("/")) if (part.isEmpty() || part.equals(".") || part.equals("..")) return false;
        return path.endsWith("/supervisor.sh");
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(CHANNEL, "PocketCloud supervisor", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Ongoing user-started local Termux supervisor status and Stop action");
            ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(channel);
        }
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    @Override public void onDestroy() {
        executor.shutdownNow();
        pendingCommands.clear();
        super.onDestroy();
    }
}

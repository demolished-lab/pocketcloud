package org.pocketcloud.supervisor;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

@RunWith(AndroidJUnit4.class)
public final class SupervisorAvdTest {
    @Test
    public void launcherRendersPrimaryControlsOnAndroid() {
        Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
        Context context = instrumentation.getTargetContext();
        Intent launchIntent = context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
        assertNotNull("PocketCloud must have a launcher activity", launchIntent);
        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);

        Activity activity = instrumentation.startActivitySync(launchIntent);
        try {
            assertTrue("Launcher must open MainActivity", activity instanceof MainActivity);
            Set<String> visibleText = new HashSet<>();
            instrumentation.runOnMainSync(() -> collectVisibleText(
                    activity.findViewById(android.R.id.content), visibleText));
            assertTrue("Supervisor title is missing", visibleText.contains("PocketCloud Supervisor"));
            assertTrue("Start control is missing", visibleText.contains("Start local supervisor"));
            assertTrue("Stop control is missing", visibleText.contains("Stop local supervisor"));
            assertTrue("Pairing control is missing", visibleText.contains("Scan laptop pairing QR"));
        } finally {
            instrumentation.runOnMainSync(activity::finish);
        }
    }

    @Test
    public void supervisorServiceIsPrivateAndDeclaresRequiredForegroundContract() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        PackageManager packageManager = context.getPackageManager();
        ComponentName serviceName = new ComponentName(context, SupervisorService.class);
        ServiceInfo service = packageManager.getServiceInfo(serviceName, PackageManager.GET_META_DATA);

        assertFalse("Supervisor service must not be externally exported", service.exported);
        if (Build.VERSION.SDK_INT >= 34) {
            assertTrue("Android 14+ must see the specialUse foreground service type",
                    (service.foregroundServiceType & ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE) != 0);
        }

        PackageInfo packageInfo = packageManager.getPackageInfo(context.getPackageName(), PackageManager.GET_PERMISSIONS);
        assertNotNull("Requested-permission metadata is missing", packageInfo.requestedPermissions);
        Set<String> requested = new HashSet<>(Arrays.asList(packageInfo.requestedPermissions));
        assertTrue("Foreground-service permission is missing", requested.contains("android.permission.FOREGROUND_SERVICE"));
        assertTrue("specialUse foreground-service permission is missing",
                requested.contains("android.permission.FOREGROUND_SERVICE_SPECIAL_USE"));
        assertTrue("Notification permission is missing", requested.contains("android.permission.POST_NOTIFICATIONS"));
    }

    private static void collectVisibleText(View view, Set<String> output) {
        if (view instanceof TextView) {
            output.add(((TextView) view).getText().toString());
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int index = 0; index < group.getChildCount(); index++) {
                collectVisibleText(group.getChildAt(index), output);
            }
        }
    }
}

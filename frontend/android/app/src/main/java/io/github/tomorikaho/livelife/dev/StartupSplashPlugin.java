package io.github.tomorikaho.livelife.dev;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/** Lets the web entry dismiss the native startup splash once the first screen is ready. */
@CapacitorPlugin(name = "StartupSplash")
public class StartupSplashPlugin extends Plugin {
    private static StartupSplashView view;
    private static boolean pendingDismiss;
    private static boolean pendingFail;

    public static void attach(StartupSplashView splash) {
        view = splash;
        if (pendingFail) {
            pendingFail = false;
            splash.showError();
        } else if (pendingDismiss) {
            pendingDismiss = false;
            splash.dismiss();
        }
    }

    static void onDismissed(StartupSplashView splash) {
        if (view == splash) view = null;
    }

    @PluginMethod
    public void dismiss(PluginCall call) {
        run(call, false);
    }

    @PluginMethod
    public void fail(PluginCall call) {
        run(call, true);
    }

    private void run(PluginCall call, boolean failed) {
        if (getActivity() == null) {
            if (failed) pendingFail = true;
            else pendingDismiss = true;
            call.resolve();
            return;
        }
        getActivity().runOnUiThread(() -> {
            if (view == null) {
                if (failed) pendingFail = true;
                else pendingDismiss = true;
            } else if (failed) {
                view.showError();
            } else {
                view.dismiss();
            }
            call.resolve();
        });
    }
}

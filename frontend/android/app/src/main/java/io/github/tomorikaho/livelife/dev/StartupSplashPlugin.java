package io.github.tomorikaho.livelife.dev;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/** Lets the web entry dismiss the native startup splash once the first screen is ready. */
@CapacitorPlugin(name = "StartupSplash")
public class StartupSplashPlugin extends Plugin {
    @PluginMethod
    public void dismiss(PluginCall call) {
        run(call, false);
    }

    @PluginMethod
    public void fail(PluginCall call) {
        run(call, true);
    }

    private void run(PluginCall call, boolean failed) {
        if (!(getActivity() instanceof MainActivity)) {
            call.resolve();
            return;
        }
        MainActivity activity = (MainActivity) getActivity();
        // Web calls are queued after onCreate attaches the overlay. Never retain
        // commands globally or let an old bridge act on a replacement Activity.
        activity.runOnUiThread(() -> {
            if (!activity.isFinishing() && !activity.isDestroyed()) {
                StartupSplashView view = activity.getStartupSplash();
                if (view != null) {
                    if (failed) view.showError();
                    else view.dismiss();
                }
            }
            call.resolve();
        });
    }
}

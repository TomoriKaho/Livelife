package io.github.tomorikaho.livelife.dev;

import android.os.Bundle;
import android.view.ViewGroup;
import androidx.core.splashscreen.SplashScreen;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private boolean releaseSystemSplash;
    private StartupSplashView startupSplash;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        SplashScreen splash = SplashScreen.installSplashScreen(this);
        splash.setKeepOnScreenCondition(() -> !releaseSystemSplash);
        splash.setOnExitAnimationListener(provider -> provider.remove());
        registerPlugin(DeviceHeadingPlugin.class);
        registerPlugin(DeviceLocationPlugin.class);
        registerPlugin(StartupSplashPlugin.class);
        super.onCreate(savedInstanceState);
        if (getBridge() != null && getBridge().getWebView() != null) {
            getBridge().getWebView().setBackgroundColor(0xFFFDE554);
        }
        showStartupSplash();
        startupSplash.post(() -> releaseSystemSplash = true);
    }

    void showStartupSplash() {
        clearStartupSplash();
        startupSplash = new StartupSplashView(this);
        ((ViewGroup) getWindow().getDecorView()).addView(startupSplash, new ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));
    }

    StartupSplashView getStartupSplash() {
        return startupSplash;
    }

    void onStartupSplashDismissed(StartupSplashView splash) {
        if (startupSplash == splash) startupSplash = null;
    }

    private void clearStartupSplash() {
        StartupSplashView previous = startupSplash;
        startupSplash = null;
        if (previous != null) {
            previous.animate().setListener(null);
            previous.animate().cancel();
            ViewGroup parent = (ViewGroup) previous.getParent();
            if (parent != null) parent.removeView(previous);
        }
    }

    @Override
    public void onDestroy() {
        clearStartupSplash();
        super.onDestroy();
    }
}

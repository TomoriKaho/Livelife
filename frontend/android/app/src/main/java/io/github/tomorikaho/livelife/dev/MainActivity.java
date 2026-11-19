package io.github.tomorikaho.livelife.dev;

import android.os.Bundle;
import android.view.ViewGroup;
import androidx.core.splashscreen.SplashScreen;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private boolean releaseSystemSplash;

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
        StartupSplashView splashView = new StartupSplashView(this);
        ((ViewGroup) getWindow().getDecorView()).addView(splashView, new ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));
        StartupSplashPlugin.attach(splashView);
        splashView.post(() -> releaseSystemSplash = true);
    }
}

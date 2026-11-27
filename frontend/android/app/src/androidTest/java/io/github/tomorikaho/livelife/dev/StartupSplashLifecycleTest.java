package io.github.tomorikaho.livelife.dev;

import static org.junit.Assert.*;

import androidx.appcompat.app.AppCompatActivity;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class StartupSplashLifecycleTest {
    private PluginCall call(AtomicInteger resolved) {
        return new PluginCall(null, "StartupSplash", "test", "dismiss", new JSObject()) {
            @Override public void resolve() { resolved.incrementAndGet(); }
        };
    }

    private StartupSplashPlugin plugin(MainActivity owner) {
        return new StartupSplashPlugin() {
            @Override public AppCompatActivity getActivity() { return owner; }
        };
    }

    @Test
    public void destroyedOwnerReleasesViewAndCannotAffectReplacement() {
        AtomicReference<MainActivity> oldOwner = new AtomicReference<>();
        AtomicReference<StartupSplashView> oldView = new AtomicReference<>();
        try (ActivityScenario<MainActivity> old = ActivityScenario.launch(MainActivity.class)) {
            old.onActivity(activity -> {
                activity.showStartupSplash();
                oldOwner.set(activity);
                oldView.set(activity.getStartupSplash());
            });
        }
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            assertTrue(oldOwner.get().isDestroyed());
            assertNull(oldOwner.get().getStartupSplash());
            assertNull(oldView.get().getParent());
        });
        try (ActivityScenario<MainActivity> replacement = ActivityScenario.launch(MainActivity.class)) {
            replacement.onActivity(activity -> {
                activity.showStartupSplash();
                StartupSplashView current = activity.getStartupSplash();
                AtomicInteger resolved = new AtomicInteger();
                plugin(oldOwner.get()).dismiss(call(resolved));
                plugin(oldOwner.get()).fail(call(resolved));
                plugin(null).dismiss(call(resolved));
                assertEquals(3, resolved.get());
                assertSame(current, activity.getStartupSplash());
                assertNotNull(current.getParent());
                assertEquals(1f, current.getAlpha(), 0f);
            });
        }
    }

    @Test
    public void staleDismissCallbackDoesNotClearNewViewOnSameOwner() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                activity.showStartupSplash();
                StartupSplashView previous = activity.getStartupSplash();
                previous.dismiss();
                activity.showStartupSplash();
                StartupSplashView current = activity.getStartupSplash();
                activity.onStartupSplashDismissed(previous);
                assertNull(previous.getParent());
                assertSame(current, activity.getStartupSplash());
                assertNotNull(current.getParent());
            });
        }
    }

    @Test
    public void currentBridgeCanDismissAndClearItsOwnView() throws Exception {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            AtomicReference<MainActivity> owner = new AtomicReference<>();
            AtomicInteger resolved = new AtomicInteger();
            scenario.onActivity(activity -> {
                activity.showStartupSplash();
                owner.set(activity);
                plugin(activity).dismiss(call(resolved));
                assertEquals(1, resolved.get());
            });
            long deadline = android.os.SystemClock.uptimeMillis() + 5000;
            AtomicReference<StartupSplashView> remaining = new AtomicReference<>();
            do {
                scenario.onActivity(activity -> remaining.set(activity.getStartupSplash()));
                if (remaining.get() == null) break;
                Thread.sleep(20);
            } while (android.os.SystemClock.uptimeMillis() < deadline);
            assertNull("Dismissed splash must release the owner reference", remaining.get());
        }
    }
}

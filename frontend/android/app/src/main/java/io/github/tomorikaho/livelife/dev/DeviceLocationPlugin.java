package io.github.tomorikaho.livelife.dev;

import android.Manifest;
import android.content.Context;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import com.getcapacitor.*;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;

/** Foreground GPS + OEM network location. No Google service/settings dependency. */
@CapacitorPlugin(name = "DeviceLocation", permissions = {
    @Permission(alias = "location", strings = {Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION}),
    @Permission(alias = "coarseLocation", strings = {Manifest.permission.ACCESS_COARSE_LOCATION})
})
public class DeviceLocationPlugin extends Plugin {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, Request> requests = new HashMap<>();
    private LocationManager manager;
    private boolean paused;

    @Override public void load() {
        manager = (LocationManager) getContext().getSystemService(Context.LOCATION_SERVICE);
    }

    @PluginMethod public void getCurrentPosition(PluginCall call) { begin(call, false); }
    @PluginMethod(returnType = PluginMethod.RETURN_CALLBACK)
    public void watchPosition(PluginCall call) { begin(call, true); }

    private void begin(PluginCall call, boolean watch) {
        handler.post(() -> {
            Request request = new Request(call, watch);
            if (watch) call.setKeepAlive(true);
            requests.put(call.getCallbackId(), request);
            if (paused) { request.error("unavailable"); request.close(); }
            else request.start();
        });
    }

    @PluginMethod public void clearWatch(PluginCall call) {
        handler.post(() -> {
            Request request = requests.get(call.getString("id", ""));
            if (request != null) request.close();
            call.resolve();
        });
    }

    private boolean allowed() {
        return getPermissionState("location") == PermissionState.GRANTED
            || getPermissionState("coarseLocation") == PermissionState.GRANTED;
    }

    // Capacitor getLong does not accept JSON Integer values (e.g. timeout:5000).
    private long number(PluginCall call, String key, long fallback) {
        Object value = call.getData().opt(key);
        return value instanceof Number ? ((Number) value).longValue() : fallback;
    }

    private final class Request implements LocationListener {
        final PluginCall call;
        final boolean watch;
        final Runnable deadline = () -> error("timeout");
        boolean closed;
        long newest = -1;
        Request(PluginCall call, boolean watch) { this.call = call; this.watch = watch; }

        @SuppressWarnings("MissingPermission")
        void start() {
            if (closed) return;
            if (!allowed()) { error("permission-denied"); close(); return; }
            if (manager == null) { error("unavailable"); close(); return; }
            long timeout = Math.max(1000, number(call, "timeout", 20000L));
            long interval = Math.max(1000, Math.max(number(call, "minimumUpdateInterval", 1000L), number(call, "interval", 1000L)));
            long maximumAge = Math.max(0, number(call, "maximumAge", 15000L));
            int subscribed = 0;
            Location cached = null;
            try {
                for (String provider : new String[]{LocationManager.NETWORK_PROVIDER, LocationManager.GPS_PROVIDER}) {
                    if (!manager.getAllProviders().contains(provider)) continue;
                    if (provider.equals(LocationManager.GPS_PROVIDER) &&
                        (!call.getBoolean("enableHighAccuracy", true) || getPermissionState("location") != PermissionState.GRANTED)) continue;
                    if (!manager.isProviderEnabled(provider)) continue;
                    manager.requestLocationUpdates(provider, interval, 0f, this, Looper.getMainLooper());
                    subscribed++;
                    Location candidate = manager.getLastKnownLocation(provider);
                    if (candidate != null && maximumAge > 0) {
                        long age = (SystemClock.elapsedRealtimeNanos() - candidate.getElapsedRealtimeNanos()) / 1000000;
                        if (age >= 0 && age <= maximumAge && (cached == null || candidate.getElapsedRealtimeNanos() > cached.getElapsedRealtimeNanos())) cached = candidate;
                    }
                }
                if (subscribed == 0) { error("unavailable"); close(); return; }
                handler.postDelayed(deadline, timeout);
                if (cached != null) onLocationChanged(cached);
            } catch (SecurityException error) { error("permission-denied"); close(); }
              catch (RuntimeException error) { error("unavailable"); close(); }
        }

        @Override public void onLocationChanged(Location location) {
            if (closed || paused || location.getElapsedRealtimeNanos() <= newest) return;
            if (!allowed()) { error("permission-denied"); close(); return; }
            if (!location.hasAccuracy() || !Double.isFinite(location.getLatitude()) || !Double.isFinite(location.getLongitude())) return;
            newest = location.getElapsedRealtimeNanos();
            handler.removeCallbacks(deadline);
            JSObject coords = new JSObject();
            coords.put("latitude", location.getLatitude());
            coords.put("longitude", location.getLongitude());
            coords.put("accuracy", location.getAccuracy());
            if (location.hasBearing()) coords.put("heading", location.getBearing());
            JSObject result = new JSObject();
            result.put("coords", coords);
            result.put("timestamp", location.getTime());
            call.resolve(result);
            if (!watch) close();
        }

        void error(String code) {
            if (closed) return;
            if (watch) { JSObject result = new JSObject(); result.put("error", code); call.resolve(result); }
            else { call.reject(code, code); close(); }
        }
        void suspend() {
            handler.removeCallbacks(deadline);
            if (manager != null) manager.removeUpdates(this);
        }
        void close() {
            if (closed) return;
            closed = true;
            suspend();
            requests.remove(call.getCallbackId());
            if (watch) call.release(bridge);
        }
        @Override public void onProviderDisabled(String provider) {
            if (!manager.isProviderEnabled(LocationManager.GPS_PROVIDER) && !manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) error("unavailable");
        }
        @Override public void onProviderEnabled(String provider) { }
        @Override public void onStatusChanged(String provider, int status, Bundle extras) { }
    }

    @Override protected void handleOnPause() {
        paused = true;
        for (Request request : new ArrayList<>(requests.values())) {
            request.suspend();
            if (!request.watch) request.error("unavailable");
        }
    }
    @Override protected void handleOnResume() {
        if (!paused) return;
        paused = false;
        for (Request request : new ArrayList<>(requests.values())) request.start();
    }
    @Override protected void handleOnDestroy() {
        for (Request request : new ArrayList<>(requests.values())) request.close();
        handler.removeCallbacksAndMessages(null);
    }
}

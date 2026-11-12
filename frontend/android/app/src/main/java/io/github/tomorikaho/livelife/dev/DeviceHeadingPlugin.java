package io.github.tomorikaho.livelife.dev;

import android.content.Context;
import android.content.res.Configuration;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.view.Surface;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/** Streams the display-relative magnetic heading from Android's rotation-vector sensor. */
@CapacitorPlugin(name = "DeviceHeading")
public class DeviceHeadingPlugin extends Plugin implements SensorEventListener {
    private SensorManager sensorManager;
    private Sensor rotationVector;
    private boolean requested;
    private boolean registered;
    private final float[] rotationMatrix = new float[9];
    private final float[] screenRotationMatrix = new float[9];
    private final float[] orientation = new float[3];
    private float[] latestRotationVector;

    @Override
    public void load() {
        sensorManager = (SensorManager) getContext().getSystemService(Context.SENSOR_SERVICE);
        rotationVector = sensorManager == null ? null : sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR);
    }

    @PluginMethod
    public void start(PluginCall call) {
        requested = true;
        boolean available = registerSensor();
        JSObject result = new JSObject();
        result.put("available", available);
        if (!available) requested = false;
        call.resolve(result);
    }

    @PluginMethod
    public void stop(PluginCall call) {
        requested = false;
        unregisterSensor();
        call.resolve();
    }

    @Override
    protected void handleOnPause() {
        unregisterSensor();
    }

    @Override
    protected void handleOnResume() {
        if (requested) registerSensor();
    }

    @Override
    protected void handleOnConfigurationChanged(Configuration newConfig) {
        if (latestRotationVector != null) emitHeading(latestRotationVector);
    }

    @Override
    protected void handleOnDestroy() {
        requested = false;
        unregisterSensor();
    }

    private boolean registerSensor() {
        if (registered) return true;
        if (sensorManager == null || rotationVector == null) return false;
        registered = sensorManager.registerListener(this, rotationVector, SensorManager.SENSOR_DELAY_GAME);
        return registered;
    }

    private void unregisterSensor() {
        if (!registered || sensorManager == null) return;
        sensorManager.unregisterListener(this, rotationVector);
        registered = false;
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (event.sensor.getType() != Sensor.TYPE_ROTATION_VECTOR) return;
        latestRotationVector = event.values.clone();
        emitHeading(latestRotationVector);
    }

    private void emitHeading(float[] vector) {
        SensorManager.getRotationMatrixFromVector(rotationMatrix, vector);
        int rotation = getActivity().getWindowManager().getDefaultDisplay().getRotation();
        int xAxis = SensorManager.AXIS_X;
        int yAxis = SensorManager.AXIS_Y;
        if (rotation == Surface.ROTATION_90) {
            xAxis = SensorManager.AXIS_Y;
            yAxis = SensorManager.AXIS_MINUS_X;
        } else if (rotation == Surface.ROTATION_180) {
            xAxis = SensorManager.AXIS_MINUS_X;
            yAxis = SensorManager.AXIS_MINUS_Y;
        } else if (rotation == Surface.ROTATION_270) {
            xAxis = SensorManager.AXIS_MINUS_Y;
            yAxis = SensorManager.AXIS_X;
        }
        if (!SensorManager.remapCoordinateSystem(rotationMatrix, xAxis, yAxis, screenRotationMatrix)) return;
        SensorManager.getOrientation(screenRotationMatrix, orientation);
        double heading = (Math.toDegrees(orientation[0]) + 360d) % 360d;
        JSObject payload = new JSObject();
        payload.put("heading", heading);
        notifyListeners("heading", payload);
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
        // The continuous stream is still useful while Android calibrates the compass.
    }
}

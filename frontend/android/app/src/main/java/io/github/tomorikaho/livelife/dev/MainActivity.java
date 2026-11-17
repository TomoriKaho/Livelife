package io.github.tomorikaho.livelife.dev;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(DeviceHeadingPlugin.class);
        registerPlugin(DeviceLocationPlugin.class);
        super.onCreate(savedInstanceState);
    }
}

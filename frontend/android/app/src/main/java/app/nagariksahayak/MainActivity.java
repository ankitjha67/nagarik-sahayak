package app.nagariksahayak;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Bundle;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.getcapacitor.BridgeActivity;

/**
 * Voice intake needs the microphone. Capacitor's WebChromeClient grants the
 * WebView's audio-capture request only once the app itself holds RECORD_AUDIO,
 * so this requests the runtime permission on first launch. Everything else is
 * the standard Capacitor bridge.
 */
public class MainActivity extends BridgeActivity {

    private static final int REQ_MIC = 4201;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(
                    this, new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
        }
    }
}

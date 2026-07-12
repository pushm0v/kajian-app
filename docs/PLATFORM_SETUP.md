# Platform setup

After running `flutter create --platforms=android,ios .` to generate the native
projects, apply the microphone / speech permissions below. Without these the app
will crash or silently fail to record on a real device.

---

## iOS — `ios/Runner/Info.plist`

Add these keys inside the top-level `<dict>`:

```xml
<key>NSMicrophoneUsageDescription</key>
<string>Kajian Notes uses the microphone to record lectures for transcription.</string>

<key>NSSpeechRecognitionUsageDescription</key>
<string>Kajian Notes uses speech recognition to caption kajian live as you record.</string>
```

To keep recording while the screen is locked or the app is backgrounded, add
background audio mode:

```xml
<key>UIBackgroundModes</key>
<array>
  <string>audio</string>
</array>
```

Minimum iOS deployment target for `speech_to_text` / `record` is **iOS 13**.
In `ios/Podfile` ensure: `platform :ios, '13.0'`.

---

## Android — `android/app/src/main/AndroidManifest.xml`

Add these permissions above the `<application>` tag:

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
<uses-permission android:name="android.permission.INTERNET"/>
<!-- For continuous recording while backgrounded: -->
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE"/>
```

Android 11+ requires a `<queries>` entry so `speech_to_text` can find the
recognizer service. Add inside `<manifest>`:

```xml
<queries>
  <intent>
    <action android:name="android.speech.RecognitionService" />
  </intent>
</queries>
```

Set `minSdkVersion 23` (or higher) in `android/app/build.gradle`.

---

## Background recording (optional, recommended for long kajian)

For recordings that continue when the app is backgrounded on Android, add a
foreground-service package such as `flutter_foreground_task` and start a
notification-backed service when recording begins. The current scaffold records
reliably while the app is in the foreground; wire the foreground service in
`RecordingController.start()` when you need lock-screen resilience.

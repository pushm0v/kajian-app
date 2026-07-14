// Generated from android/app/google-services.json and
// ios/Runner/GoogleService-Info.plist for the "aplikasi-raya" Firebase
// project. Re-run `flutterfire configure` if those files ever change.
//
// ignore_for_file: type=lint
import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      throw UnsupportedError(
        'DefaultFirebaseOptions have not been configured for web — run '
        '`flutterfire configure`.',
      );
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      default:
        throw UnsupportedError(
          'DefaultFirebaseOptions are not supported for this platform.',
        );
    }
  }

  static const android = FirebaseOptions(
    apiKey: 'AIzaSyC9R3Y_k_oVRRcT6XAKBAqK1735Ac5C6uw',
    appId: '1:106021924289:android:d5410f66e2930a7d9f1340',
    messagingSenderId: '106021924289',
    projectId: 'aplikasi-raya',
    storageBucket: 'aplikasi-raya.firebasestorage.app',
  );

  static const ios = FirebaseOptions(
    apiKey: 'AIzaSyCsrYLDrG8niQBbK6xvnBV59ZfnYtY-irM',
    appId: '1:106021924289:ios:b05377f3320601129f1340',
    messagingSenderId: '106021924289',
    projectId: 'aplikasi-raya',
    storageBucket: 'aplikasi-raya.firebasestorage.app',
    iosBundleId: 'app.kajian.id.kajianApp',
  );
}

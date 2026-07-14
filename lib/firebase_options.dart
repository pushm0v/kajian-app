// TODO(setup): This file is a placeholder. Generate the real one with the
// FlutterFire CLI once your Firebase project exists:
//
//   dart pub global activate flutterfire_cli
//   flutterfire configure
//
// That command overwrites this file with real `FirebaseOptions` for each
// platform (reading the same Firebase project you registered the Android
// package `app.kajian.id.kajian_app` and iOS bundle id `app.kajian.id.kajianApp`
// under) and updates android/app/google-services.json +
// ios/Runner/GoogleService-Info.plist for you automatically — you can then
// delete the .template files next to those two.
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

  // Placeholder values — replace by running `flutterfire configure`.
  static const android = FirebaseOptions(
    apiKey: 'REPLACE_ME',
    appId: 'REPLACE_ME',
    messagingSenderId: 'REPLACE_ME',
    projectId: 'REPLACE_ME',
  );

  static const ios = FirebaseOptions(
    apiKey: 'REPLACE_ME',
    appId: 'REPLACE_ME',
    messagingSenderId: 'REPLACE_ME',
    projectId: 'REPLACE_ME',
    iosBundleId: 'app.kajian.id.kajianApp',
  );
}

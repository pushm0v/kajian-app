import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app.dart';
import 'firebase_options.dart';
import 'providers/auth_provider.dart';
import 'providers/session_provider.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        // load() is triggered by _AuthGate once the user is confirmed
        // signed in (see app.dart) — every backend-core request needs a
        // Firebase ID token, so there's nothing useful to sync before then,
        // and the sign-in screen never shows session data anyway.
        ChangeNotifierProvider(create: (_) => SessionProvider()),
      ],
      child: const KajianApp(),
    ),
  );
}

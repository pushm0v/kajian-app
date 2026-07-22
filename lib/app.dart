import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/config/app_config.dart';
import 'core/constants/app_constants.dart';
import 'core/theme/app_theme.dart';
import 'providers/auth_provider.dart';
import 'providers/session_provider.dart';
import 'screens/auth/sign_in_screen.dart';
import 'screens/home/home_screen.dart';

class KajianApp extends StatelessWidget {
  const KajianApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: AppConstants.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      home: const _AuthGate(),
    );
  }
}

/// Shows the sign-in screen until a Firebase user is present, then the app.
///
/// The user is always signed in by the time [HomeScreen] renders, so this
/// is also where [SessionProvider] learns it's safe to sync with
/// backend-core (every request needs a Firebase ID token — see
/// CoreApiClient) rather than staying local-cache-only. This is the single
/// place that decides [SessionProvider.syncEnabled] — it, not
/// [SessionProvider] itself, is responsible for checking
/// [AppConfig.backendBaseUrl] is actually configured before turning sync on.
class _AuthGate extends StatefulWidget {
  const _AuthGate();

  @override
  State<_AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<_AuthGate> {
  bool _syncStarted = false;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    final canSync =
        auth.status == AuthStatus.signedIn && AppConfig.backendBaseUrl.isNotEmpty;
    if (canSync && !_syncStarted) {
      _syncStarted = true;
      final sessions = context.read<SessionProvider>();
      sessions.syncEnabled = true;
      sessions.load();
    } else if (!canSync && _syncStarted) {
      // Signed out (e.g. user tapped "Keluar") — stop treating local data
      // as sync-eligible so a subsequent sign-in (possibly as a different
      // user) doesn't push the previous user's cached sessions to their
      // account.
      _syncStarted = false;
      context.read<SessionProvider>().syncEnabled = false;
    }

    return switch (auth.status) {
      AuthStatus.unknown => const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
      AuthStatus.signedOut => const SignInScreen(),
      AuthStatus.signedIn => const HomeScreen(),
    };
  }
}

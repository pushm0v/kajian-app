import 'package:firebase_auth/firebase_auth.dart' hide AuthProvider;
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:kajian_app/app.dart';
import 'package:kajian_app/providers/auth_provider.dart';
import 'package:kajian_app/providers/session_provider.dart';
import 'package:kajian_app/services/auth_service.dart';

/// Fake auth backend so widget tests never touch Firebase. Always reports
/// signed-out, since a real `User` can't be constructed without Firebase.
class _FakeSignedOutAuthService implements AuthServiceBase {
  @override
  Stream<User?> get authStateChanges => const Stream.empty();
  @override
  User? get currentUser => null;
  @override
  Future<UserCredential> signInWithGoogle() => throw UnimplementedError();
  @override
  Future<UserCredential> signInWithApple() => throw UnimplementedError();
  @override
  Future<void> signOut() async {}
}

void main() {
  testWidgets('Signed-out app shows the sign-in screen', (tester) async {
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(
            create: (_) => AuthProvider(service: _FakeSignedOutAuthService()),
          ),
          // path_provider has no platform implementation in widget tests, so
          // StorageService.loadAll() catches the error and yields an empty
          // library — harmless since HomeScreen is never reached here.
          ChangeNotifierProvider(create: (_) => SessionProvider()..load()),
        ],
        child: const KajianApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Kajian App'), findsWidgets);
    expect(find.text('Continue with Google'), findsOneWidget);
  });
}

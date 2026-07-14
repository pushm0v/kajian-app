import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';

import '../services/auth_service.dart';

enum AuthStatus { unknown, signedOut, signedIn }

/// Exposes the current Firebase auth state to the widget tree.
///
/// Depends on the small [AuthService] interface rather than `FirebaseAuth`
/// directly, so widget tests can inject a fake without initializing
/// Firebase.
class AuthProvider extends ChangeNotifier {
  final AuthServiceBase _service;
  late final StreamSubscription<User?> _sub;

  AuthProvider({AuthServiceBase? service}) : _service = service ?? AuthService() {
    _user = _service.currentUser;
    _status = _user == null ? AuthStatus.signedOut : AuthStatus.signedIn;
    _sub = _service.authStateChanges.listen((user) {
      _user = user;
      _status = user == null ? AuthStatus.signedOut : AuthStatus.signedIn;
      notifyListeners();
    });
  }

  User? _user;
  AuthStatus _status = AuthStatus.unknown;
  String? _error;
  bool _busy = false;

  User? get user => _user;
  AuthStatus get status => _status;
  String? get error => _error;
  bool get busy => _busy;

  Future<void> signInWithGoogle() => _runSignIn(_service.signInWithGoogle);

  Future<void> signInWithApple() => _runSignIn(_service.signInWithApple);

  Future<void> _runSignIn(Future<UserCredential> Function() action) async {
    _busy = true;
    _error = null;
    notifyListeners();
    try {
      await action();
    } catch (e) {
      _error = _friendlyError(e);
    } finally {
      _busy = false;
      notifyListeners();
    }
  }

  Future<void> signOut() => _service.signOut();

  String _friendlyError(Object e) {
    if (e is FirebaseAuthException) {
      return e.message ?? 'Sign-in failed (${e.code}).';
    }
    return 'Sign-in failed: $e';
  }

  @override
  void dispose() {
    _sub.cancel();
    super.dispose();
  }
}

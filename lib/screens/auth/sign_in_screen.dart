import 'dart:io';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import '../../core/constants/app_constants.dart';
import '../../providers/auth_provider.dart';

/// Shown when there is no signed-in Firebase user. Kajian Notes requires an
/// account (Google or Apple) before recording/browsing sessions.
class SignInScreen extends StatelessWidget {
  const SignInScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.menu_book_rounded,
                size: 80,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(height: 20),
              Text(
                AppConstants.appName,
                style: Theme.of(context)
                    .textTheme
                    .headlineMedium
                    ?.copyWith(fontWeight: FontWeight.bold),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                'Sign in to record, transcribe, and keep your kajian notes.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 48),
              if (auth.error != null) ...[
                Text(
                  auth.error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
              ],
              _GoogleSignInButton(busy: auth.busy),
              if (Platform.isIOS) ...[
                const SizedBox(height: 12),
                _AppleSignInButton(busy: auth.busy),
              ],
              if (auth.busy) ...[
                const SizedBox(height: 24),
                const CircularProgressIndicator(),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _GoogleSignInButton extends StatelessWidget {
  final bool busy;
  const _GoogleSignInButton({required this.busy});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: OutlinedButton.icon(
        onPressed: busy
            ? null
            : () => context.read<AuthProvider>().signInWithGoogle(),
        icon: const Icon(Icons.g_mobiledata, size: 28),
        label: const Text('Continue with Google'),
      ),
    );
  }
}

class _AppleSignInButton extends StatelessWidget {
  final bool busy;
  const _AppleSignInButton({required this.busy});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: SignInWithAppleButton(
        onPressed: busy
            ? () {}
            : () => context.read<AuthProvider>().signInWithApple(),
      ),
    );
  }
}

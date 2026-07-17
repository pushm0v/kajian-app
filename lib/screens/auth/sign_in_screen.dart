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
    final theme = Theme.of(context);

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 28),
          child: Column(
            children: [
              const Spacer(flex: 3),
              const _Logo(),
              const SizedBox(height: 28),
              Text(
                AppConstants.appName,
                style: theme.textTheme.displaySmall,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                'Record a kajian, transcribe it, and keep\nbeautiful notes — automatically.',
                style: theme.textTheme.bodyLarge
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textAlign: TextAlign.center,
              ),
              const Spacer(flex: 4),
              if (auth.error != null) ...[
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Text(
                    auth.error!,
                    style: TextStyle(
                        color: theme.colorScheme.onErrorContainer),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 16),
              ],
              _GoogleSignInButton(busy: auth.busy),
              if (Platform.isIOS) ...[
                const SizedBox(height: 12),
                _AppleSignInButton(busy: auth.busy),
              ],
              SizedBox(height: auth.busy ? 20 : 0),
              if (auth.busy)
                const SizedBox(
                  height: 22,
                  width: 22,
                  child: CircularProgressIndicator(strokeWidth: 2.4),
                ),
              const SizedBox(height: 20),
              Text(
                'By continuing you agree to our Terms & Privacy Policy.',
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
    );
  }
}

class _Logo extends StatelessWidget {
  const _Logo();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.12),
            blurRadius: 24,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(28),
        child: Image.asset(
          'assets/icon/app_icon.png',
          width: 108,
          height: 108,
          fit: BoxFit.cover,
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
      child: OutlinedButton.icon(
        onPressed: busy
            ? null
            : () => context.read<AuthProvider>().signInWithGoogle(),
        icon: const _GoogleGlyph(),
        label: const Text('Continue with Google'),
      ),
    );
  }
}

/// Simple "G" mark so we don't depend on a bundled Google asset.
class _GoogleGlyph extends StatelessWidget {
  const _GoogleGlyph();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 22,
      height: 22,
      alignment: Alignment.center,
      decoration: const BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
      ),
      child: const Text(
        'G',
        style: TextStyle(
          fontWeight: FontWeight.w700,
          fontSize: 15,
          color: Color(0xFF4285F4),
        ),
      ),
    );
  }
}

class _AppleSignInButton extends StatelessWidget {
  final bool busy;
  const _AppleSignInButton({required this.busy});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return SizedBox(
      width: double.infinity,
      child: SignInWithAppleButton(
        height: 52,
        style: dark
            ? SignInWithAppleButtonStyle.white
            : SignInWithAppleButtonStyle.black,
        borderRadius: BorderRadius.circular(16),
        onPressed: busy
            ? () {}
            : () => context.read<AuthProvider>().signInWithApple(),
      ),
    );
  }
}

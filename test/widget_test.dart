import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:kajian_app/app.dart';
import 'package:kajian_app/providers/session_provider.dart';

void main() {
  testWidgets('App boots to the empty library with a record action',
      (tester) async {
    // In a widget test path_provider has no platform implementation, so
    // StorageService.loadAll() catches the error and yields an empty library.
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => SessionProvider()..load()),
        ],
        child: const KajianApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Kajian Notes'), findsWidgets);
    expect(find.text('Record Kajian'), findsOneWidget);
    expect(find.text('No kajian yet'), findsOneWidget);
  });
}

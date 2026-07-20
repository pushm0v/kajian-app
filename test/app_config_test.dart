import 'package:flutter_test/flutter_test.dart';
import 'package:kajian_app/core/config/app_config.dart';

void main() {
  group('AppConfig.httpToWsUrl', () {
    test('returns empty for empty input', () {
      expect(AppConfig.httpToWsUrl(''), '');
    });

    test('swaps http -> ws', () {
      expect(
        AppConfig.httpToWsUrl('http://192.168.1.50:8080'),
        'ws://192.168.1.50:8080',
      );
    });

    test('swaps https -> wss', () {
      expect(
        AppConfig.httpToWsUrl('https://api.mykajianapp.com'),
        'wss://api.mykajianapp.com',
      );
    });

    test('preserves path if present', () {
      expect(
        AppConfig.httpToWsUrl('https://api.mykajianapp.com/v1'),
        'wss://api.mykajianapp.com/v1',
      );
    });
  });
}

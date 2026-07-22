import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../core/config/app_config.dart';
import '../models/transcript_segment.dart';

/// High-accuracy transcription of the recorded audio file via a cloud model
/// (Whisper) behind your backend proxy.
///
/// This is the "accurate" half of the hybrid strategy: run after recording to
/// replace the rough live captions with a clean, timestamped transcript that
/// handles Indonesian + Arabic and long audio well.
///
/// When no backend is configured ([AppConfig.isMockMode]) it returns a
/// realistic mock so the whole flow is testable offline.
class CloudTranscriptionService {
  final http.Client _client;
  CloudTranscriptionService({http.Client? client})
      : _client = client ?? http.Client();

  /// Transcribe [audioFilePath]. [localeId] hints the spoken language.
  ///
  /// [baseUrl] selects which backend to hit (e.g. the Qwen or Whisper server);
  /// when null/empty it falls back to [AppConfig.backendBaseUrl]. If the
  /// resolved URL is empty and no dev key is set, returns mock data.
  Future<List<TranscriptSegment>> transcribe({
    required String audioFilePath,
    required String localeId,
    String? baseUrl,
  }) async {
    final resolved =
        (baseUrl == null || baseUrl.isEmpty) ? AppConfig.backendBaseUrl : baseUrl;
    if (resolved.isEmpty && AppConfig.devDirectProviderKey.isEmpty) {
      return _mockTranscript();
    }

    final uri = Uri.parse('$resolved/transcribe');
    final request = http.MultipartRequest('POST', uri)
      ..fields['locale'] = localeId
      ..fields['model'] = AppConfig.cloudTranscriptionModel
      ..files.add(await http.MultipartFile.fromPath('audio', audioFilePath));
    if (AppConfig.backendAuthToken.isNotEmpty) {
      request.headers['Authorization'] = 'Bearer ${AppConfig.backendAuthToken}';
    }

    final streamed = await _client.send(request);
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode != 200) {
      throw HttpException(
        'Transcription failed (${response.statusCode}): ${response.body}',
      );
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final segments = (body['segments'] as List?) ?? const [];
    return segments
        .map((e) => TranscriptSegment.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Realistic placeholder transcript used in mock mode.
  Future<List<TranscriptSegment>> _mockTranscript() async {
    await Future<void>.delayed(const Duration(seconds: 2));
    const lines = [
      'Alhamdulillah, segala puji bagi Allah subhanahu wa ta\'ala.',
      'Pada kajian kali ini kita akan membahas tentang keutamaan sabar.',
      'Allah berfirman: "Innallaha ma\'as-sabirin" — sesungguhnya Allah beserta orang-orang yang sabar.',
      'Sabar terbagi menjadi tiga: sabar dalam ketaatan, sabar menjauhi maksiat, dan sabar atas takdir.',
      'Rasulullah shallallahu \'alaihi wa sallam bersabda bahwa sabar itu cahaya.',
      'Semoga kita semua dimudahkan untuk mengamalkan kesabaran dalam kehidupan sehari-hari.',
    ];
    var t = 0;
    return [
      for (var i = 0; i < lines.length; i++)
        TranscriptSegment(
          id: 'mock_$i',
          text: lines[i],
          startMs: t,
          endMs: t += 8000,
          isFinal: true,
        ),
    ];
  }

  void dispose() => _client.close();
}

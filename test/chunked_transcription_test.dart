import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:kajian_app/services/chunked_transcription_service.dart';

void main() {
  // The overlap window makes Whisper transcribe the same ~2s of audio in
  // two consecutive chunks. Without stitching, that speech appears twice in
  // the captions.
  group('stitch (overlap dedup)', () {
    test('drops a repeated tail from the next chunk', () {
      expect(
        ChunkedTranscriptionService.stitch(
          'bismillah alhamdulillah kita mulai kajian',
          'kita mulai kajian hari ini tentang sabar',
        ),
        'hari ini tentang sabar',
      );
    });

    test('matches across differing punctuation and casing', () {
      // Whisper does not transcribe the overlapped audio identically twice,
      // so a literal string compare would miss this.
      expect(
        ChunkedTranscriptionService.stitch(
          'kita mulai kajian hari ini',
          'Kajian, hari ini tentang sabar',
        ),
        'tentang sabar',
      );
    });

    test('returns the next chunk unchanged when nothing repeats', () {
      expect(
        ChunkedTranscriptionService.stitch(
          'bismillah kita mulai',
          'topik berikutnya adalah zakat',
        ),
        'topik berikutnya adalah zakat',
      );
    });

    test('returns the next chunk when there is no previous text', () {
      expect(
        ChunkedTranscriptionService.stitch('', 'bismillah'),
        'bismillah',
      );
    });

    test('does not dedup on a single shared word', () {
      // One common word ("dan", "yang") repeating across a boundary is
      // coincidence, not overlap — stripping it would delete real speech.
      expect(
        ChunkedTranscriptionService.stitch(
          'kajian tentang sabar dan',
          'dan syukur itu penting',
        ),
        'dan syukur itu penting',
      );
    });

    test('handles full repetition of the previous chunk', () {
      expect(
        ChunkedTranscriptionService.stitch('satu dua tiga', 'satu dua tiga'),
        '',
      );
    });
  });

  group('wrapInWav', () {
    // ffmpeg/PyAV need a container to know sample rate and channel count;
    // raw PCM would be misinterpreted.
    Uint8List pcm(int samples) =>
        Uint8List.fromList(List.filled(samples * 2, 0));

    test('prepends a 44-byte header and preserves the payload', () {
      final data = pcm(1000);
      final wav = ChunkedTranscriptionService.wrapInWav(data);
      expect(wav.length, 44 + data.length);
    });

    test('writes a RIFF/WAVE header', () {
      final wav = ChunkedTranscriptionService.wrapInWav(pcm(10));
      expect(String.fromCharCodes(wav.sublist(0, 4)), 'RIFF');
      expect(String.fromCharCodes(wav.sublist(8, 12)), 'WAVE');
      expect(String.fromCharCodes(wav.sublist(12, 16)), 'fmt ');
      expect(String.fromCharCodes(wav.sublist(36, 40)), 'data');
    });

    test('declares mono 16kHz PCM16 — what the model expects', () {
      final wav = ChunkedTranscriptionService.wrapInWav(pcm(10));
      final view = ByteData.sublistView(wav);
      expect(view.getUint16(20, Endian.little), 1, reason: 'format = PCM');
      expect(view.getUint16(22, Endian.little), 1, reason: 'mono');
      expect(view.getUint32(24, Endian.little), 16000, reason: 'sample rate');
      expect(view.getUint32(28, Endian.little), 32000, reason: 'byte rate');
      expect(view.getUint16(34, Endian.little), 16, reason: 'bits per sample');
    });

    test('sets chunk sizes consistently with the payload', () {
      final data = pcm(500);
      final wav = ChunkedTranscriptionService.wrapInWav(data);
      final view = ByteData.sublistView(wav);
      expect(view.getUint32(4, Endian.little), 36 + data.length);
      expect(view.getUint32(40, Endian.little), data.length);
    });
  });

  group('chunk geometry', () {
    test('20s chunks with 2s overlap at 16kHz PCM16', () {
      expect(ChunkedTranscriptionService.chunkDuration.inSeconds, 20);
      expect(ChunkedTranscriptionService.overlapDuration.inSeconds, 2);
    });
  });
}

import 'dart:math' as math;

import 'package:flutter/material.dart';

/// A lightweight animated level meter that reacts to the live mic amplitude.
/// Keeps a short rolling history so it reads like a scrolling waveform.
class WaveformBar extends StatefulWidget {
  final double amplitude; // 0..1
  final bool active;
  const WaveformBar({super.key, required this.amplitude, required this.active});

  @override
  State<WaveformBar> createState() => _WaveformBarState();
}

class _WaveformBarState extends State<WaveformBar> {
  static const _barCount = 40;
  final List<double> _levels = List.filled(_barCount, 0.05, growable: true);

  @override
  void didUpdateWidget(covariant WaveformBar old) {
    super.didUpdateWidget(old);
    if (widget.active) {
      _levels.removeAt(0);
      _levels.add(widget.amplitude.clamp(0.05, 1.0));
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = widget.active
        ? Theme.of(context).colorScheme.primary
        : Theme.of(context).colorScheme.outlineVariant;
    return LayoutBuilder(
      builder: (context, constraints) {
        const gap = 3.0;
        final barW =
            (constraints.maxWidth - gap * (_barCount - 1)) / _barCount;
        return Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            for (var i = 0; i < _barCount; i++) ...[
              _Bar(
                width: math.max(2, barW),
                heightFactor: _levels[i],
                color: color,
              ),
              if (i != _barCount - 1) SizedBox(width: gap),
            ],
          ],
        );
      },
    );
  }
}

class _Bar extends StatelessWidget {
  final double width;
  final double heightFactor;
  final Color color;
  const _Bar({
    required this.width,
    required this.heightFactor,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 150),
      width: width,
      height: 48 * heightFactor,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(4),
      ),
    );
  }
}

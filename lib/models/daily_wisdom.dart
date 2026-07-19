/// A single Quran verse or Hadith, shown with its Indonesian meaning in the
/// homepage's rotating "wisdom" card.
class DailyWisdom {
  /// "quran" or "hadith".
  final String type;

  /// Original Arabic text.
  final String arabic;

  /// Indonesian translation / meaning.
  final String meaningId;

  /// e.g. "QS. Al-Baqarah: 153" or "HR. Muslim no. 2699".
  final String source;

  const DailyWisdom({
    required this.type,
    required this.arabic,
    required this.meaningId,
    required this.source,
  });
}

/// A small curated rotation of verses and hadiths about seeking knowledge,
/// patience, and gathering to remember Allah — themes that fit a kajian app.
/// Static and offline so the homepage always has something to show.
const List<DailyWisdom> kDailyWisdoms = [
  DailyWisdom(
    type: 'hadith',
    arabic:
        'مَنْ سَلَكَ طَرِيقًا يَلْتَمِسُ فِيهِ عِلْمًا سَهَّلَ اللَّهُ لَهُ بِهِ طَرِيقًا إِلَى الْجَنَّةِ',
    meaningId:
        'Barang siapa menempuh jalan untuk mencari ilmu, Allah akan mudahkan '
        'baginya jalan menuju surga.',
    source: 'HR. Muslim no. 2699',
  ),
  DailyWisdom(
    type: 'quran',
    arabic:
        'يَرْفَعِ اللَّهُ الَّذِينَ آمَنُوا مِنْكُمْ وَالَّذِينَ أُوتُوا الْعِلْمَ دَرَجَاتٍ',
    meaningId:
        'Allah akan meninggikan derajat orang-orang beriman di antara kalian '
        'dan orang-orang yang berilmu, beberapa derajat.',
    source: 'QS. Al-Mujadilah: 11',
  ),
  DailyWisdom(
    type: 'hadith',
    arabic:
        'مَا اجْتَمَعَ قَوْمٌ فِي بَيْتٍ مِنْ بُيُوتِ اللَّهِ يَتْلُونَ كِتَابَ اللَّهِ وَيَتَدَارَسُونَهُ بَيْنَهُمْ '
        'إِلَّا نَزَلَتْ عَلَيْهِمُ السَّكِينَةُ',
    meaningId:
        'Tidaklah suatu kaum berkumpul di salah satu rumah Allah, membaca '
        'Kitabullah dan saling mempelajarinya, kecuali ketenangan akan turun '
        'kepada mereka.',
    source: 'HR. Muslim no. 2699',
  ),
  DailyWisdom(
    type: 'quran',
    arabic: 'إِنَّ اللَّهَ مَعَ الصَّابِرِينَ',
    meaningId: 'Sesungguhnya Allah beserta orang-orang yang sabar.',
    source: 'QS. Al-Baqarah: 153',
  ),
  DailyWisdom(
    type: 'hadith',
    arabic: 'خَيْرُكُمْ مَنْ تَعَلَّمَ الْقُرْآنَ وَعَلَّمَهُ',
    meaningId:
        'Sebaik-baik kalian adalah orang yang belajar Al-Qur\'an dan '
        'mengajarkannya.',
    source: 'HR. Bukhari no. 5027',
  ),
  DailyWisdom(
    type: 'quran',
    arabic: 'وَذَكِّرْ فَإِنَّ الذِّكْرَىٰ تَنفَعُ الْمُؤْمِنِينَ',
    meaningId:
        'Dan tetaplah memberi peringatan, karena sesungguhnya peringatan itu '
        'bermanfaat bagi orang-orang yang beriman.',
    source: 'QS. Adz-Dzariyat: 55',
  ),
  DailyWisdom(
    type: 'hadith',
    arabic: 'الدَّالُّ عَلَى الْخَيْرِ كَفَاعِلِهِ',
    meaningId:
        'Orang yang menunjukkan kepada kebaikan, pahalanya seperti orang yang '
        'mengerjakannya.',
    source: 'HR. Muslim no. 1893',
  ),
];

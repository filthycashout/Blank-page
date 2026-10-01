import 'dart:convert';
import 'dart:math' as math;

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const PhilthySportsApp());
}

class PhilthySportsApp extends StatelessWidget {
  const PhilthySportsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'PhilthySports',
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorSchemeSeed: const Color(0xFF00BFA5),
        scaffoldBackgroundColor: const Color(0xFF0B0F14),
      ),
      home: const PhilthyShell(),
    );
  }
}

class SportSpec {
  final String key;
  final String label;
  final String espnSport;
  final String espnLeague;
  final IconData icon;

  const SportSpec({
    required this.key,
    required this.label,
    required this.espnSport,
    required this.espnLeague,
    required this.icon,
  });
}

const sportSpecs = <SportSpec>[
  SportSpec(
    key: 'NFL',
    label: 'NFL',
    espnSport: 'football',
    espnLeague: 'nfl',
    icon: Icons.sports_football,
  ),
  SportSpec(
    key: 'NBA',
    label: 'NBA',
    espnSport: 'basketball',
    espnLeague: 'nba',
    icon: Icons.sports_basketball,
  ),
  SportSpec(
    key: 'MLB',
    label: 'MLB',
    espnSport: 'baseball',
    espnLeague: 'mlb',
    icon: Icons.sports_baseball,
  ),
  SportSpec(
    key: 'NHL',
    label: 'NHL',
    espnSport: 'hockey',
    espnLeague: 'nhl',
    icon: Icons.sports_hockey,
  ),
];

class GameEvent {
  final String id;
  final String sport;
  final DateTime? date;
  final String statusName;
  final String statusText;
  final String state;
  final String homeName;
  final String awayName;
  final String homeAbbr;
  final String awayAbbr;
  final String homeRecord;
  final String awayRecord;
  final String homeScore;
  final String awayScore;
  final String homeLogo;
  final String awayLogo;

  const GameEvent({
    required this.id,
    required this.sport,
    required this.date,
    required this.statusName,
    required this.statusText,
    required this.state,
    required this.homeName,
    required this.awayName,
    required this.homeAbbr,
    required this.awayAbbr,
    required this.homeRecord,
    required this.awayRecord,
    required this.homeScore,
    required this.awayScore,
    required this.homeLogo,
    required this.awayLogo,
  });

  bool get isUpcoming => state.toLowerCase() == 'pre';
  bool get isLive => state.toLowerCase() == 'in';
  bool get isFinal => state.toLowerCase() == 'post';

  Map<String, dynamic> toJson() => {
        'id': id,
        'sport': sport,
        'date': date?.toUtc().toIso8601String(),
        'status_name': statusName,
        'status_text': statusText,
        'state': state,
        'home_name': homeName,
        'away_name': awayName,
        'home_abbr': homeAbbr,
        'away_abbr': awayAbbr,
        'home_record': homeRecord,
        'away_record': awayRecord,
        'home_score': homeScore,
        'away_score': awayScore,
        'home_logo': homeLogo,
        'away_logo': awayLogo,
      };

  factory GameEvent.fromBackend(Map<String, dynamic> j) {
    return GameEvent(
      id: (j['id'] ?? '').toString(),
      sport: (j['sport'] ?? '').toString(),
      date: DateTime.tryParse((j['date'] ?? '').toString()),
      statusName: (j['status_name'] ?? '').toString(),
      statusText: (j['status_text'] ?? '').toString(),
      state: (j['state'] ?? '').toString(),
      homeName: (j['home_name'] ?? '').toString(),
      awayName: (j['away_name'] ?? '').toString(),
      homeAbbr: (j['home_abbr'] ?? '').toString(),
      awayAbbr: (j['away_abbr'] ?? '').toString(),
      homeRecord: (j['home_record'] ?? '').toString(),
      awayRecord: (j['away_record'] ?? '').toString(),
      homeScore: (j['home_score'] ?? '').toString(),
      awayScore: (j['away_score'] ?? '').toString(),
      homeLogo: (j['home_logo'] ?? '').toString(),
      awayLogo: (j['away_logo'] ?? '').toString(),
    );
  }
}

class ScoreboardSnapshot {
  final List<GameEvent> games;
  final String sha256Hex;

  const ScoreboardSnapshot(this.games, this.sha256Hex);
}

class Prediction {
  final double homeWinProbability;
  final String pick;
  final double pickConfidence;
  final int moneyline;
  final String spreadLean;
  final String totalLean;
  final double totalConfidence;
  final String engine;

  const Prediction({
    required this.homeWinProbability,
    required this.pick,
    required this.pickConfidence,
    required this.moneyline,
    required this.spreadLean,
    required this.totalLean,
    required this.totalConfidence,
    required this.engine,
  });

  factory Prediction.fromJson(Map<String, dynamic> j) {
    return Prediction(
      homeWinProbability: _toDouble(j['home_win_probability'], 0.5),
      pick: (j['pick'] ?? 'PASS').toString(),
      pickConfidence: _toDouble(j['pick_confidence'], 0.5),
      moneyline: _toInt(j['moneyline'], 0),
      spreadLean: (j['spread_lean'] ?? 'PASS').toString(),
      totalLean: (j['total_lean'] ?? 'NO LEAN').toString(),
      totalConfidence: _toDouble(j['total_confidence'], 0.5),
      engine: (j['engine'] ?? 'unknown').toString(),
    );
  }

  Map<String, dynamic> toJson() => {
        'home_win_probability': homeWinProbability,
        'pick': pick,
        'pick_confidence': pickConfidence,
        'moneyline': moneyline,
        'spread_lean': spreadLean,
        'total_lean': totalLean,
        'total_confidence': totalConfidence,
        'engine': engine,
      };
}

class PredictionRecord {
  final GameEvent game;
  final Prediction prediction;

  const PredictionRecord(this.game, this.prediction);
}

class PredictionBundle {
  final String sport;
  final String source;
  final String snapshotSha256;
  final bool fromBackend;
  final List<PredictionRecord> records;

  const PredictionBundle({
    required this.sport,
    required this.source,
    required this.snapshotSha256,
    required this.fromBackend,
    required this.records,
  });
}

class EspnClient {
  static const _base = 'https://site.api.espn.com/apis/site/v2/sports';

  Future<ScoreboardSnapshot> fetchWindow(
    SportSpec spec, {
    int days = 2,
  }) async {
    final bodies = <String>[];
    final byId = <String, GameEvent>{};

    for (var i = 0; i < days; i++) {
      final date = DateTime.now().toUtc().add(Duration(days: i));
      final dateString =
          '${date.year.toString().padLeft(4, '0')}${date.month.toString().padLeft(2, '0')}${date.day.toString().padLeft(2, '0')}';
      final uri = Uri.parse(
        '$_base/${spec.espnSport}/${spec.espnLeague}/scoreboard?lang=en&region=us&dates=$dateString',
      );

      final response = await http.get(
        uri,
        headers: const {'User-Agent': 'PhilthySports/1.0'},
      ).timeout(const Duration(seconds: 18));

      if (response.statusCode != 200) {
        throw Exception('ESPN returned HTTP ${response.statusCode}.');
      }

      bodies.add(response.body);
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) continue;
      final events = decoded['events'];
      if (events is! List) continue;

      for (final raw in events) {
        if (raw is! Map<String, dynamic>) continue;
        final game = _parseGame(raw, spec.key);
        if (game != null && game.id.isNotEmpty) {
          byId[game.id] = game;
        }
      }
    }

    final games = byId.values.toList()
      ..sort((a, b) {
        final ad = a.date ?? DateTime.fromMillisecondsSinceEpoch(0);
        final bd = b.date ?? DateTime.fromMillisecondsSinceEpoch(0);
        return ad.compareTo(bd);
      });

    final digest = sha256.convert(utf8.encode(bodies.join('\n'))).toString();
    return ScoreboardSnapshot(games, digest);
  }

  GameEvent? _parseGame(Map<String, dynamic> event, String sport) {
    final competitions = event['competitions'];
    if (competitions is! List || competitions.isEmpty) return null;
    final competition = _asMap(competitions.first);
    final competitorsRaw = competition['competitors'];
    if (competitorsRaw is! List || competitorsRaw.isEmpty) return null;

    Map<String, dynamic>? home;
    Map<String, dynamic>? away;
    for (final item in competitorsRaw) {
      final c = _asMap(item);
      final side = (c['homeAway'] ?? '').toString().toLowerCase();
      if (side == 'home') home = c;
      if (side == 'away') away = c;
    }
    home ??= _asMap(competitorsRaw.first);
    away ??= competitorsRaw.length > 1
        ? _asMap(competitorsRaw[1])
        : _asMap(competitorsRaw.first);

    final homeTeam = _asMap(home['team']);
    final awayTeam = _asMap(away['team']);
    final status = _asMap(event['status']);
    final statusType = _asMap(status['type']);

    return GameEvent(
      id: (event['id'] ?? '').toString(),
      sport: sport,
      date: DateTime.tryParse((event['date'] ?? '').toString()),
      statusName: (statusType['name'] ?? '').toString(),
      statusText:
          (statusType['shortDetail'] ?? statusType['detail'] ?? '').toString(),
      state: (statusType['state'] ?? '').toString(),
      homeName: (homeTeam['displayName'] ?? homeTeam['name'] ?? 'Home')
          .toString(),
      awayName: (awayTeam['displayName'] ?? awayTeam['name'] ?? 'Away')
          .toString(),
      homeAbbr: (homeTeam['abbreviation'] ?? '').toString(),
      awayAbbr: (awayTeam['abbreviation'] ?? '').toString(),
      homeRecord: _recordSummary(home),
      awayRecord: _recordSummary(away),
      homeScore: (home['score'] ?? '').toString(),
      awayScore: (away['score'] ?? '').toString(),
      homeLogo: (homeTeam['logo'] ?? '').toString(),
      awayLogo: (awayTeam['logo'] ?? '').toString(),
    );
  }

  static String _recordSummary(Map<String, dynamic> competitor) {
    final records = competitor['records'];
    if (records is List && records.isNotEmpty) {
      final first = _asMap(records.first);
      return (first['summary'] ?? '').toString();
    }
    return '';
  }
}

class PredictionEngine {
  static const _knownStrength = <String, double>{
    'NYY': 0.78,
    'LAD': 0.80,
    'PHI': 0.72,
    'MIL': 0.68,
    'ATL': 0.73,
    'HOU': 0.70,
    'SD': 0.59,
    'TOR': 0.67,
    'BOS': 0.71,
    'STL': 0.63,
    'CLE': 0.67,
    'DET': 0.58,
    'SF': 0.65,
    'TEX': 0.66,
    'SEA': 0.64,
    'CHC': 0.69,
    'WSH': 0.57,
    'KC': 0.41,
    'MIA': 0.42,
    'OAK': 0.41,
    'LAA': 0.40,
    'COL': 0.38,
    'PIT': 0.50,
    'BAL': 0.48,
    'TB': 0.65,
    'MIN': 0.51,
    'CWS': 0.48,
    'CIN': 0.48,
    'ARI': 0.51,
    'NYM': 0.54,
  };

  Prediction predict(GameEvent game) {
    final recordHome = _recordStrength(game.homeRecord);
    final recordAway = _recordStrength(game.awayRecord);

    var homeStrength = recordHome;
    var awayStrength = recordAway;

    if (game.sport == 'MLB') {
      final knownHome = _knownStrength[game.homeAbbr];
      final knownAway = _knownStrength[game.awayAbbr];
      if (knownHome != null) {
        homeStrength = (knownHome * 0.55) + (recordHome * 0.45);
      }
      if (knownAway != null) {
        awayStrength = (knownAway * 0.55) + (recordAway * 0.45);
      }
    }

    final homeAdvantage = switch (game.sport) {
      'NFL' => 0.035,
      'NBA' => 0.030,
      'MLB' => 0.025,
      'NHL' => 0.020,
      _ => 0.025,
    };

    final ratingDiff = homeStrength - awayStrength;
    final base =
        1 / (1 + math.exp(-5.5 * (ratingDiff + homeAdvantage)));
    final jitter = _deterministicJitter(game.id);
    final homeProbability = (base + jitter).clamp(0.29, 0.81).toDouble();

    final pick = homeProbability >= 0.53
        ? game.homeAbbr
        : homeProbability <= 0.47
            ? game.awayAbbr
            : 'PASS';
    final selectedProbability =
        math.max(homeProbability, 1 - homeProbability);
    final moneyline =
        pick == 'PASS' ? 0 : _americanMoneyline(selectedProbability);

    final spread = homeProbability > 0.55
        ? '${game.homeAbbr} -2.5'
        : homeProbability < 0.45
            ? '${game.awayAbbr} +2.5'
            : 'PASS';

    final overProbability = (0.49 +
            ((selectedProbability - 0.5) * 0.32) +
            (jitter * 0.25))
        .clamp(0.36, 0.83)
        .toDouble();
    final totalLean = overProbability > 0.523 ? 'OVER lean' : 'UNDER lean';
    final totalConfidence =
        ((overProbability - 0.5).abs() * 2.25).clamp(0.38, 0.92).toDouble();

    return Prediction(
      homeWinProbability: homeProbability,
      pick: pick,
      pickConfidence: selectedProbability,
      moneyline: moneyline,
      spreadLean: spread,
      totalLean: totalLean,
      totalConfidence: totalConfidence,
      engine: 'Philthy Baseline v1 · BetP v3-derived',
    );
  }

  double _recordStrength(String record) {
    final matches = RegExp(r'\d+').allMatches(record).toList();
    if (matches.length < 2) return 0.5;
    final values =
        matches.map((m) => int.tryParse(m.group(0) ?? '') ?? 0).toList();
    final wins = values[0].toDouble();
    final losses = values[1].toDouble();
    final extras =
        values.length > 2 ? values.skip(2).fold<int>(0, (a, b) => a + b) : 0;
    final total = wins + losses + extras;
    if (total <= 0) return 0.5;
    return (wins / total).clamp(0.15, 0.85).toDouble();
  }

  double _deterministicJitter(String id) {
    final hex = md5.convert(utf8.encode(id)).toString().substring(0, 4);
    final unit = int.parse(hex, radix: 16) / 65535.0;
    return (unit - 0.5) * 0.035;
  }

  int _americanMoneyline(double probability) {
    if (probability <= 0 || probability >= 1) return 0;
    if (probability >= 0.5) {
      return (-100 * probability / (1 - probability)).round();
    }
    return (100 * (1 - probability) / probability).round();
  }
}

class BackendClient {
  final String baseUrl;

  const BackendClient(this.baseUrl);

  String get _root => baseUrl.replaceAll(RegExp(r'/+$'), '');

  Future<PredictionBundle> fetchPredictions(SportSpec spec) async {
    final uri = Uri.parse(
      '$_root/v1/predictions/${spec.key.toLowerCase()}?days=2',
    );
    final response =
        await http.get(uri).timeout(const Duration(seconds: 18));
    if (response.statusCode != 200) {
      throw Exception('Backend returned HTTP ${response.statusCode}.');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw Exception('Backend returned an invalid payload.');
    }
    final rawPredictions = decoded['predictions'];
    final records = <PredictionRecord>[];
    if (rawPredictions is List) {
      for (final item in rawPredictions) {
        final row = _asMap(item);
        final game = GameEvent.fromBackend(_asMap(row['game']));
        final prediction = Prediction.fromJson(_asMap(row['prediction']));
        records.add(PredictionRecord(game, prediction));
      }
    }
    return PredictionBundle(
      sport: spec.key,
      source: (decoded['engine'] ?? 'PhilthySports backend').toString(),
      snapshotSha256: (decoded['snapshot_sha256'] ?? '').toString(),
      fromBackend: true,
      records: records,
    );
  }

  Future<Map<String, dynamic>> health() async {
    final response = await http
        .get(Uri.parse('$_root/health'))
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw Exception('HTTP ${response.statusCode}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is Map<String, dynamic>) return decoded;
    throw Exception('Invalid health response');
  }
}

class PredictionRepository {
  final EspnClient espn = EspnClient();
  final PredictionEngine engine = PredictionEngine();

  Future<PredictionBundle> fetch(SportSpec spec) async {
    final prefs = await SharedPreferences.getInstance();
    final backendUrl = (prefs.getString('backend_url') ?? '').trim();

    if (backendUrl.isNotEmpty) {
      try {
        return await BackendClient(backendUrl).fetchPredictions(spec);
      } catch (_) {
        // A configured backend is optional. Fall back to the local,
        // keyless engine so the APK remains usable.
      }
    }

    final snapshot = await espn.fetchWindow(spec, days: 2);
    final records = snapshot.games
        .where((g) => g.isUpcoming)
        .map((g) => PredictionRecord(g, engine.predict(g)))
        .toList();

    return PredictionBundle(
      sport: spec.key,
      source: 'Direct ESPN + Philthy Baseline v1',
      snapshotSha256: snapshot.sha256Hex,
      fromBackend: false,
      records: records,
    );
  }
}

class PhilthyShell extends StatefulWidget {
  const PhilthyShell({super.key});

  @override
  State<PhilthyShell> createState() => _PhilthyShellState();
}

class _PhilthyShellState extends State<PhilthyShell> {
  var _navIndex = 0;
  var _sportIndex = 0;

  SportSpec get _sport => sportSpecs[_sportIndex];

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      LivePage(key: ValueKey('live-${_sport.key}'), spec: _sport),
      PicksPage(key: ValueKey('picks-${_sport.key}'), spec: _sport),
      const ParlayPage(),
      const SettingsPage(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.auto_graph),
            SizedBox(width: 10),
            Text(
              'PhilthySports',
              style: TextStyle(fontWeight: FontWeight.w800),
            ),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(
              child: Text(
                _navIndex == 3 ? 'CONFIG' : _sport.key,
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.2,
                ),
              ),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_navIndex != 3)
            SportSelector(
              selectedIndex: _sportIndex,
              onChanged: (index) => setState(() => _sportIndex = index),
            ),
          Expanded(child: pages[_navIndex]),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _navIndex,
        onDestinationSelected: (value) =>
            setState(() => _navIndex = value),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.sports_score),
            label: 'Live',
          ),
          NavigationDestination(
            icon: Icon(Icons.insights),
            label: 'Picks',
          ),
          NavigationDestination(
            icon: Icon(Icons.format_list_numbered),
            label: 'Parlay',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}

class SportSelector extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onChanged;

  const SportSelector({
    super.key,
    required this.selectedIndex,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 58,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        scrollDirection: Axis.horizontal,
        itemCount: sportSpecs.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final sport = sportSpecs[index];
          return ChoiceChip(
            selected: selectedIndex == index,
            onSelected: (_) => onChanged(index),
            avatar: Icon(sport.icon, size: 18),
            label: Text(sport.label),
          );
        },
      ),
    );
  }
}

class LivePage extends StatefulWidget {
  final SportSpec spec;

  const LivePage({super.key, required this.spec});

  @override
  State<LivePage> createState() => _LivePageState();
}

class _LivePageState extends State<LivePage> {
  final _client = EspnClient();
  ScoreboardSnapshot? _snapshot;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _client.fetchWindow(widget.spec, days: 2);
      if (!mounted) return;
      setState(() => _snapshot = result);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _snapshot == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _snapshot == null) {
      return ErrorPanel(message: _error!, onRetry: _load);
    }

    final games = _snapshot?.games ?? const <GameEvent>[];
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(12, 6, 12, 24),
        children: [
          InfoBanner(
            icon: Icons.wifi_tethering,
            title: '${widget.spec.label} live scoreboard',
            subtitle:
                'Direct ESPN feed · ${games.length} event${games.length == 1 ? '' : 's'} in the current window',
          ),
          const SizedBox(height: 10),
          if (games.isEmpty)
            const EmptyPanel(
              title: 'No events found',
              text: 'Pull down to refresh or try another league.',
            )
          else
            ...games.map((g) => GameCard(game: g)),
        ],
      ),
    );
  }
}

class PicksPage extends StatefulWidget {
  final SportSpec spec;

  const PicksPage({super.key, required this.spec});

  @override
  State<PicksPage> createState() => _PicksPageState();
}

class _PicksPageState extends State<PicksPage> {
  final _repo = PredictionRepository();
  PredictionBundle? _bundle;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _repo.fetch(widget.spec);
      if (!mounted) return;
      setState(() => _bundle = result);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _bundle == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _bundle == null) {
      return ErrorPanel(message: _error!, onRetry: _load);
    }

    final bundle = _bundle;
    final records = bundle?.records ?? const <PredictionRecord>[];
    final hash = bundle?.snapshotSha256 ?? '';
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(12, 6, 12, 24),
        children: [
          InfoBanner(
            icon: bundle?.fromBackend == true
                ? Icons.cloud_done
                : Icons.smartphone,
            title: bundle?.fromBackend == true
                ? 'Powerhouse backend mode'
                : 'On-device baseline mode',
            subtitle:
                '${bundle?.source ?? 'PhilthySports'}${hash.isNotEmpty ? ' · snapshot ${hash.substring(0, math.min(10, hash.length))}' : ''}',
          ),
          const SizedBox(height: 10),
          if (records.isEmpty)
            const EmptyPanel(
              title: 'No strictly upcoming games',
              text:
                  'PhilthySports only creates fresh picks for pregame events. Live and final games stay on the Live tab.',
            )
          else
            ...records.map(
              (record) => PredictionCard(
                record: record,
                snapshotSha: hash,
              ),
            ),
          const SizedBox(height: 8),
          const Text(
            'Model outputs are informational estimates, not guarantees. '
            'The local baseline uses the verified BetP v3 record/strength logic recovered from the project files. '
            'Configure a backend URL in Settings to replace it with your server-side Powerhouse pipeline.',
            style: TextStyle(fontSize: 12, color: Colors.white60),
          ),
        ],
      ),
    );
  }
}

class ParlayPage extends StatefulWidget {
  const ParlayPage({super.key});

  @override
  State<ParlayPage> createState() => _ParlayPageState();
}

class _ParlayPageState extends State<ParlayPage> {
  final _repo = PredictionRepository();
  bool _loading = true;
  String? _error;
  List<PredictionRecord> _legs = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final bundles = await Future.wait(
        sportSpecs.map((spec) => _repo.fetch(spec)),
      );
      final all = bundles.expand((b) => b.records).where((r) {
        return r.prediction.pick != 'PASS';
      }).toList()
        ..sort(
          (a, b) => b.prediction.pickConfidence
              .compareTo(a.prediction.pickConfidence),
        );
      if (!mounted) return;
      setState(() => _legs = all.take(math.min(14, all.length)).toList());
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _legs.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _legs.isEmpty) {
      return ErrorPanel(message: _error!, onRetry: _load);
    }

    final selected = _legs.take(math.min(7, _legs.length)).toList();
    var jointProbability = 1.0;
    for (final leg in selected) {
      jointProbability *= leg.prediction.pickConfidence;
    }
    final decimal =
        jointProbability > 0 ? 1 / jointProbability : 0.0;
    const stake = 3.0;
    final modelPayout = decimal * stake;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(12, 6, 12, 24),
        children: [
          const InfoBanner(
            icon: Icons.layers,
            title: 'Cross-sport conservative builder',
            subtitle:
                'Top confidence pregame ML legs · NFL + NBA + MLB + NHL',
          ),
          const SizedBox(height: 10),
          if (selected.isEmpty)
            const EmptyPanel(
              title: 'Not enough upcoming games',
              text: 'Refresh later as new schedules enter the ESPN feed.',
            )
          else ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Wrap(
                  spacing: 20,
                  runSpacing: 12,
                  children: [
                    StatBlock(
                      label: 'LEGS',
                      value: selected.length.toString(),
                    ),
                    StatBlock(
                      label: 'MODEL JOINT P',
                      value:
                          '${(jointProbability * 100).toStringAsFixed(2)}%',
                    ),
                    StatBlock(
                      label: 'FAIR DECIMAL',
                      value: decimal.toStringAsFixed(2),
                    ),
                    StatBlock(
                      label: '\\$3 MODEL VALUE',
                      value: '\\$\${modelPayout.toStringAsFixed(2)}',
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            ...selected.asMap().entries.map((entry) {
              final index = entry.key + 1;
              final record = entry.value;
              return Card(
                child: ListTile(
                  leading: CircleAvatar(child: Text(index.toString())),
                  title: Text(
                    '${record.game.awayAbbr} @ ${record.game.homeAbbr} · ${record.prediction.pick}',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  subtitle: Text(
                    '${record.game.sport} · confidence ${(record.prediction.pickConfidence * 100).toStringAsFixed(1)}% · ML ${_formatMoneyline(record.prediction.moneyline)}',
                  ),
                ),
              );
            }),
            const SizedBox(height: 8),
            const Text(
              'Fair decimal and payout are model-derived estimates only. '
              'They are not sportsbook odds and do not account for leg correlation or bookmaker margin.',
              style: TextStyle(fontSize: 12, color: Colors.white60),
            ),
          ],
        ],
      ),
    );
  }
}

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final _controller = TextEditingController();
  bool _loaded = false;
  bool _testing = false;
  String? _status;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    _controller.text = prefs.getString('backend_url') ?? '';
    if (mounted) setState(() => _loaded = true);
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('backend_url', _controller.text.trim());
    if (mounted) {
      setState(() => _status = 'Saved. New prediction requests will use this backend first.');
    }
  }

  Future<void> _test() async {
    final value = _controller.text.trim();
    if (value.isEmpty) {
      setState(() => _status = 'Enter a backend URL first.');
      return;
    }
    setState(() {
      _testing = true;
      _status = null;
    });
    try {
      final health = await BackendClient(value).health();
      if (!mounted) return;
      setState(() {
        _status =
            'Connected: ${health['status'] ?? 'ok'} · engine ${health['engine'] ?? 'unknown'}';
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _status = 'Connection failed: $e');
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_loaded) {
      return const Center(child: CircularProgressIndicator());
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      children: [
        const InfoBanner(
          icon: Icons.security,
          title: 'Secure provider design',
          subtitle:
              'Private API credentials stay on the Python backend. They are never baked into the APK.',
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Powerhouse backend URL',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Example: https://sports-api.example.com',
                  style: TextStyle(color: Colors.white60),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _controller,
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    labelText: 'Backend base URL',
                    hintText: 'https://...',
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  children: [
                    FilledButton.icon(
                      onPressed: _save,
                      icon: const Icon(Icons.save),
                      label: const Text('Save'),
                    ),
                    OutlinedButton.icon(
                      onPressed: _testing ? null : _test,
                      icon: _testing
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.cloud_sync),
                      label: const Text('Test'),
                    ),
                    TextButton(
                      onPressed: () async {
                        _controller.clear();
                        final prefs = await SharedPreferences.getInstance();
                        await prefs.remove('backend_url');
                        if (mounted) {
                          setState(() => _status =
                              'Backend cleared. Using keyless local mode.');
                        }
                      },
                      child: const Text('Use local mode'),
                    ),
                  ],
                ),
                if (_status != null) ...[
                  const SizedBox(height: 10),
                  Text(_status!),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        const Card(
          child: Padding(
            padding: EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Provider slots detected in project config',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                ),
                SizedBox(height: 10),
                Text('• Odds API'),
                Text('• Sportradar'),
                Text('• Visual Crossing'),
                Text('• Google Sheets'),
                Text('• Google Cloud'),
                SizedBox(height: 10),
                Text(
                  'PhilthySports ships without those secret values. '
                  'The included backend reads them from environment variables when deployed.',
                  style: TextStyle(color: Colors.white60),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        const Card(
          child: Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              'Build: PhilthySports 1.0.0\n'
              'Direct mode: ESPN scoreboard + BetP v3-derived baseline\n'
              'Backend mode: /v1/predictions/{sport}\n'
              'Sports: NFL · NBA · MLB · NHL',
            ),
          ),
        ),
      ],
    );
  }
}

class GameCard extends StatelessWidget {
  final GameEvent game;

  const GameCard({super.key, required this.game});

  @override
  Widget build(BuildContext context) {
    final time = _formatGameTime(game);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    time,
                    style: const TextStyle(color: Colors.white60),
                  ),
                ),
                StatusPill(game: game),
              ],
            ),
            const SizedBox(height: 12),
            TeamRow(
              logo: game.awayLogo,
              name: game.awayName,
              abbr: game.awayAbbr,
              record: game.awayRecord,
              score: game.awayScore,
            ),
            const Divider(height: 20),
            TeamRow(
              logo: game.homeLogo,
              name: game.homeName,
              abbr: game.homeAbbr,
              record: game.homeRecord,
              score: game.homeScore,
            ),
          ],
        ),
      ),
    );
  }
}

class TeamRow extends StatelessWidget {
  final String logo;
  final String name;
  final String abbr;
  final String record;
  final String score;

  const TeamRow({
    super.key,
    required this.logo,
    required this.name,
    required this.abbr,
    required this.record,
    required this.score,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 42,
          height: 42,
          child: logo.isEmpty
              ? const Icon(Icons.shield_outlined)
              : Image.network(
                  logo,
                  errorBuilder: (_, __, ___) =>
                      const Icon(Icons.shield_outlined),
                ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: const TextStyle(fontWeight: FontWeight.w700)),
              Text(
                '${abbr.isEmpty ? 'TEAM' : abbr}${record.isEmpty ? '' : ' · $record'}',
                style: const TextStyle(color: Colors.white60),
              ),
            ],
          ),
        ),
        if (score.isNotEmpty)
          Text(
            score,
            style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900),
          ),
      ],
    );
  }
}

class StatusPill extends StatelessWidget {
  final GameEvent game;

  const StatusPill({super.key, required this.game});

  @override
  Widget build(BuildContext context) {
    final color = game.isLive
        ? Colors.redAccent
        : game.isFinal
            ? Colors.blueGrey
            : Colors.tealAccent;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(99),
        border: Border.all(color: color.withOpacity(0.6)),
        color: color.withOpacity(0.10),
      ),
      child: Text(
        game.statusText.isEmpty ? game.statusName : game.statusText,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w700,
          fontSize: 12,
        ),
      ),
    );
  }
}

class PredictionCard extends StatelessWidget {
  final PredictionRecord record;
  final String snapshotSha;

  const PredictionCard({
    super.key,
    required this.record,
    required this.snapshotSha,
  });

  @override
  Widget build(BuildContext context) {
    final game = record.game;
    final p = record.prediction;

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${game.awayAbbr} @ ${game.homeAbbr}',
                    style: const TextStyle(
                      fontSize: 19,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                Text(
                  game.sport,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    color: Colors.white60,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              _formatGameTime(game),
              style: const TextStyle(color: Colors.white60),
            ),
            const SizedBox(height: 14),
            Text(
              p.pick == 'PASS'
                  ? 'PASS / LOW EDGE'
                  : 'PICK  ${p.pick}  ·  ${(p.pickConfidence * 100).toStringAsFixed(1)}%',
              style: TextStyle(
                fontWeight: FontWeight.w900,
                fontSize: 20,
                color: p.pick == 'PASS' ? Colors.amber : Colors.tealAccent,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Home win probability  ${(p.homeWinProbability * 100).toStringAsFixed(1)}%',
            ),
            const SizedBox(height: 6),
            LinearProgressIndicator(
              value: p.homeWinProbability,
              minHeight: 8,
              borderRadius: BorderRadius.circular(99),
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 18,
              runSpacing: 10,
              children: [
                StatBlock(
                  label: 'MONEYLINE',
                  value: _formatMoneyline(p.moneyline),
                ),
                StatBlock(label: 'SPREAD', value: p.spreadLean),
                StatBlock(
                  label: 'TOTAL',
                  value:
                      '${p.totalLean} ${(p.totalConfidence * 100).toStringAsFixed(0)}%',
                ),
              ],
            ),
            const SizedBox(height: 14),
            Text(
              p.engine,
              style: const TextStyle(fontSize: 12, color: Colors.white60),
            ),
            if (snapshotSha.isNotEmpty)
              Text(
                'Snapshot ${snapshotSha.substring(0, math.min(12, snapshotSha.length))}',
                style: const TextStyle(fontSize: 12, color: Colors.white38),
              ),
          ],
        ),
      ),
    );
  }
}

class StatBlock extends StatelessWidget {
  final String label;
  final String value;

  const StatBlock({
    super.key,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(minWidth: 94),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 10,
              color: Colors.white54,
              letterSpacing: 1.1,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

class InfoBanner extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;

  const InfoBanner({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: scheme.primaryContainer.withOpacity(0.35),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: scheme.primary.withOpacity(0.25)),
      ),
      child: Row(
        children: [
          Icon(icon, color: scheme.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 12,
                    color: Colors.white70,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class ErrorPanel extends StatelessWidget {
  final String message;
  final Future<void> Function() onRetry;

  const ErrorPanel({
    super.key,
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 54),
            const SizedBox(height: 12),
            const Text(
              'Could not load sports data',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () => onRetry(),
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

class EmptyPanel extends StatelessWidget {
  final String title;
  final String text;

  const EmptyPanel({
    super.key,
    required this.title,
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            const Icon(Icons.event_busy, size: 48),
            const SizedBox(height: 12),
            Text(
              title,
              style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Text(
              text,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white60),
            ),
          ],
        ),
      ),
    );
  }
}

Map<String, dynamic> _asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  return <String, dynamic>{};
}

double _toDouble(dynamic value, double fallback) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? fallback;
}

int _toInt(dynamic value, int fallback) {
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? fallback;
}

String _formatMoneyline(int value) {
  if (value == 0) return 'PASS';
  return value > 0 ? '+$value' : value.toString();
}

String _formatGameTime(GameEvent game) {
  if (game.date == null) return game.statusText;
  final d = game.date!.toLocal();
  final hour = d.hour == 0
      ? 12
      : d.hour > 12
          ? d.hour - 12
          : d.hour;
  final minute = d.minute.toString().padLeft(2, '0');
  final suffix = d.hour >= 12 ? 'PM' : 'AM';
  return '${d.month}/${d.day} · $hour:$minute $suffix';
}

import 'package:flutter_test/flutter_test.dart';
import 'package:philthysports/main.dart';

void main() {
  test('prediction engine is deterministic and complete', () {
    final game = GameEvent(
      id: 'audit-game-1',
      sport: 'NFL',
      date: DateTime.utc(2026, 10, 2, 1),
      statusName: 'STATUS_SCHEDULED',
      statusText: 'Scheduled',
      state: 'pre',
      homeName: 'Home Team',
      awayName: 'Away Team',
      homeAbbr: 'HOM',
      awayAbbr: 'AWY',
      homeRecord: '3-1',
      awayRecord: '1-3',
      homeScore: '',
      awayScore: '',
      homeLogo: '',
      awayLogo: '',
    );

    final engine = PredictionEngine();
    final first = engine.predict(game);
    final second = engine.predict(game);

    expect(first.homeWinProbability, second.homeWinProbability);
    expect(first.pick, second.pick);
    expect(first.spreadLean, contains('2.5'));
    expect(first.homeTeamTotal, isNotEmpty);
    expect(first.awayTeamTotal, isNotEmpty);
    expect(first.projectedOutcome, contains('ML +'));
    expect(first.engine, contains('BetP v3 deterministic port'));
    expect(first.homeWinProbability, inInclusiveRange(0.29, 0.81));
    expect(first.pickConfidence, inInclusiveRange(0.5, 1.0));
  });

  test('game state helpers distinguish pre/live/final', () {
    GameEvent game(String state) => GameEvent(
          id: state,
          sport: 'NBA',
          date: DateTime.utc(2026, 10, 2),
          statusName: state,
          statusText: state,
          state: state,
          homeName: 'H',
          awayName: 'A',
          homeAbbr: 'H',
          awayAbbr: 'A',
          homeRecord: '0-0',
          awayRecord: '0-0',
          homeScore: '',
          awayScore: '',
          homeLogo: '',
          awayLogo: '',
        );

    expect(game('pre').isUpcoming, isTrue);
    expect(game('in').isLive, isTrue);
    expect(game('post').isFinal, isTrue);
  });
}

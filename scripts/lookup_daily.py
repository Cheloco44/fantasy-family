"""Manual read-only ESPN daily aggregate lookup for November 11, 2026 (Phoenix)."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math
import unicodedata
import json
import os
import sys
from urllib.request import Request, build_opener

from collect_current import NoRedirect, SafeArgumentParser, atomic_write

BASE = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2027'
METADATA_URL = BASE + '?view=proTeamSchedules_wl&scoringPeriodId=44'
LEAGUE_URL = (BASE + '/segments/0/leagues/1399646897?view=mSettings&view=mTeam'
              '&view=mMatchupScore&view=mScoreboard&scoringPeriodId=44')
MAX_BYTES = 8 * 1024 * 1024

DATE = '2026-11-11'
TIME_ZONE = 'America/Phoenix'
PERIOD = 44
LEAGUE_ID = 1399646897
SEASON_ID = 2027


def integer(value):
    if type(value) is not int or value < 1:
        raise ValueError('INVALID_DATA')
    return value


def period_evidence(data):
    """Verify the fixed date/period from deduplicated provider game evidence."""
    try:
        games = {}
        for team in data['settings']['proTeams']:
            for key, group in team['proGamesByScoringPeriod'].items():
                if type(group) is not list:
                    raise ValueError
                for game in group:
                    game_id = integer(game['id'])
                    period = integer(game['scoringPeriodId'])
                    if key != str(period) or type(game['statsOfficial']) is not bool:
                        raise ValueError
                    timestamp = integer(game['date'])
                    day = datetime.fromtimestamp(timestamp / 1000, timezone.utc).astimezone(
                        ZoneInfo(TIME_ZONE)).date().isoformat()
                    evidence = (timestamp, period, game['statsOfficial'], day)
                    if game_id in games and games[game_id] != evidence:
                        raise ValueError
                    games[game_id] = evidence
        target = [g for g in games.values() if g[3] == DATE]
        if (not target or {g[1] for g in target} != {PERIOD}
                or any(g[1] == PERIOD and g[3] != DATE for g in games.values())):
            raise ValueError
        return dict(gameCount=len(target), allGamesStatsOfficial=all(g[2] for g in target))
    except (KeyError, TypeError, AttributeError, OverflowError, OSError, ValueError):
        raise ValueError('INVALID_DATA') from None


def normalize(data, metadata, *, now=None):
    """Allowlist daily aggregates only; never infer them from weekly totals or players."""
    try:
        return _normalize(data, metadata, now=now)
    except (KeyError, TypeError, AttributeError, OverflowError, ValueError):
        raise ValueError('INVALID_DATA') from None


def _normalize(data, metadata, *, now):
    evidence = period_evidence(metadata)
    if (integer(data['id']) != LEAGUE_ID or integer(data['seasonId']) != SEASON_ID
            or integer(data['scoringPeriodId']) != PERIOD
            or data['settings']['scoringSettings']['scoringType'] != 'H2H_POINTS'):
        raise ValueError
    now = datetime.now(timezone.utc) if now is None else now
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError
    if type(data['teams']) is not list or len(data['teams']) != 8:
        raise ValueError
    names = {}
    for team in data['teams']:
        team_id = integer(team['id'])
        name = team['name'] if 'name' in team else team['location'] + ' ' + team['nickname']
        if (team_id in names or not isinstance(name, str) or name in names.values()
                or not 1 <= len(name) <= 120
                or not name.strip() or any(unicodedata.category(c).startswith('C') for c in name)):
            raise ValueError
        names[team_id] = name
    if type(data['schedule']) is not list:
        raise ValueError
    candidates = set()
    for match in data['schedule']:
        period = integer(match['matchupPeriodId'])
        for side in (match.get('home'), match.get('away')):
            if side is None:
                continue
            points = side.get('pointsByScoringPeriod', {})
            if type(points) is not dict:
                raise ValueError
            if '44' in points:
                candidates.add(period)
    mapping = data['settings'].get('scheduleSettings', {}).get('matchupPeriods')
    if mapping is not None:
        mapped = set()
        for key, periods in mapping.items():
            period = integer(int(key))
            if str(period) != key or type(periods) is not list:
                raise ValueError
            for value in periods:
                integer(value)
            if PERIOD in periods:
                mapped.add(period)
        if len(mapped) != 1 or (candidates and candidates != mapped):
            raise ValueError
        candidates = mapped
    if len(candidates) != 1:
        raise ValueError
    period = candidates.pop()
    sides = {}
    for match in data['schedule']:
        if match['matchupPeriodId'] != period:
            continue
        for side in (match['home'], match['away']):
            team_id = integer(side['teamId'])
            if team_id not in names or team_id in sides:
                raise ValueError
            points = side.get('pointsByScoringPeriod', {})
            available = '44' in points
            value = points['44'] if available else None
            if available and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError
            sides[team_id] = dict(id=team_id, name=names[team_id], dailyPoints=value,
                                 available=available,
                                 pointSource="pointsByScoringPeriod['44']" if available else None)
    if set(sides) != set(names):
        raise ValueError
    return dict(schemaVersion=1, source='ESPN', dataKind='daily-team-points', date=DATE,
                timeZone=TIME_ZONE, fetchedAt=now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
                leagueId=LEAGUE_ID, seasonId=SEASON_ID, scoringType='H2H_POINTS',
                scoringPeriodId=PERIOD, matchupPeriodId=period, periodEvidence=evidence,
                teams=[sides[team_id] for team_id in sorted(sides)])


def main(argv=None, *, environ=None, opener_factory=build_opener, now=None):
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument('--network', action='store_true')
    parser.add_argument('--output', default='artifacts/daily-lookup/nov-11.json')
    args = parser.parse_args(argv)
    if not args.network:
        print('ERROR network disabled; pass --network.', file=sys.stderr)
        return 2
    try:
        environ = os.environ if environ is None else environ
        cookies = [environ.get('ESPN_S2'), environ.get('ESPN_SWID')]
        if any(not isinstance(value, str) or not value or any(
                ord(c) < 33 or ord(c) > 126 or c in ';,"\\' for c in value)
               for value in cookies):
            raise ValueError
        payloads = []
        for url in (METADATA_URL, LEAGUE_URL):
            headers = {} if url == METADATA_URL else {'Cookie': f'espn_s2={cookies[0]}; SWID={cookies[1]}'}
            # Default stdlib TLS certificate and hostname checks stay enabled.
            with opener_factory(NoRedirect()).open(Request(url, method='GET', headers=headers), timeout=20) as response:
                if response.status != 200:
                    raise ValueError
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError
                payloads.append(json.loads(body))
            if url == METADATA_URL:
                period_evidence(payloads[0])  # No authenticated GET until date evidence is valid.
        result = normalize(payloads[1], payloads[0], now=now)
        text = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n'
        if any(cookie in text for cookie in cookies):
            raise ValueError
        atomic_write(args.output, text)
    except Exception:
        # Never echo bodies, headers, paths, cookies, or provider exception details.
        print('ERROR lookup failed.', file=sys.stderr)
        return 1
    print(f"OK teams={len(result['teams'])} available={sum(t['available'] for t in result['teams'])} scoringPeriodId=44")
    return 0


if __name__ == '__main__':
    sys.exit(main())

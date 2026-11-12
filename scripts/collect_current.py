"""Read-only, opt-in current ESPN matchup snapshot; never persists raw responses."""
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, build_opener

from probe_espn import NoRedirect

import math
import unicodedata

LEAGUE_ID = 1399646897
SEASON_ID = 2027
URL = ('https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2027/'
       'segments/0/leagues/1399646897?view=mSettings&view=mTeam&view=mMatchupScore'
       '&view=mScoreboard&view=mStandings')
MAX_BYTES = 8 * 1024 * 1024


def atomic_write(output, text):
    """Only normalized, secret-checked JSON may reach this same-directory temp file."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                         prefix='.current-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'ERROR invalid arguments.\n')


def main(argv=None, *, environ=None, opener_factory=build_opener, now=None):
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument('--network', action='store_true')
    parser.add_argument('--output', default='artifacts/current-export/current.json')
    args = parser.parse_args(argv)
    if not args.network:
        print('ERROR network disabled; pass --network.', file=sys.stderr)
        return 2
    try:
        environ = os.environ if environ is None else environ
        cookies = [environ.get('ESPN_S2'), environ.get('ESPN_SWID')]
        if any(not isinstance(value, str) or not value or any(
                ord(c) < 33 or ord(c) > 126 or c in ';,"\\\\' for c in value)
               for value in cookies):
            raise ValueError
        request = Request(URL, method='GET', headers={
            'Cookie': f'espn_s2={cookies[0]}; SWID={cookies[1]}'})
        # Standard-library opener keeps default certificate/hostname verification.
        with opener_factory(NoRedirect()).open(request, timeout=20) as response:
            if response.status != 200:
                raise ValueError
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError
            data = json.loads(body)
        result = normalize(data, now=now)
        text = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n'
        if any(cookie in text for cookie in cookies):
            raise ValueError
        atomic_write(args.output, text)
    except Exception:
        # Never echo exception details, bodies, headers, cookie values or paths.
        print('ERROR collection failed.', file=sys.stderr)
        return 1
    print(f"OK teams={len(result['teams'])} matchups={len(result['matchups'])} scoringType={result['scoringType']}")
    return 0


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('INVALID_DATA')
    return value


def record(value):
    return {key: integer(value[key]) for key in ('wins', 'losses', 'ties')}


def normalize(data, *, now=None, expected_team_count=8):
    """Build only the public contract; reject partial snapshots without raw errors."""
    try:
        return _normalize(data, now=now, expected_team_count=expected_team_count)
    except (KeyError, TypeError, AttributeError, OverflowError, ValueError):
        raise ValueError('INVALID_DATA') from None


def _normalize(data, *, now, expected_team_count):
    now = datetime.now(timezone.utc) if now is None else now
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError
    if integer(data['id']) != LEAGUE_ID or integer(data['seasonId']) != SEASON_ID:
        raise ValueError
    period = integer(data['status']['currentMatchupPeriod'], 1)
    scoring_period = integer(data['scoringPeriodId'], 1)
    scoring_type = data['settings']['scoringSettings']['scoringType']
    if scoring_type not in ('H2H_POINTS', 'H2H_CATEGORY'):
        raise ValueError
    if type(data['teams']) is not list or len(data['teams']) != integer(expected_team_count, 1):
        raise ValueError
    teams, team_ids = [], set()
    for team in data['teams']:
        team_id = integer(team['id'], 1)
        if team_id in team_ids:
            raise ValueError
        team_ids.add(team_id)
        name = team['name'] if 'name' in team else team['location'] + ' ' + team['nickname']
        if (not isinstance(name, str) or not 1 <= len(name) <= 120 or not name.strip()
                or any(unicodedata.category(c).startswith('C') for c in name)):
            raise ValueError
        seed = team.get('playoffSeed')
        standing = seed if type(seed) is int and seed > 0 else None
        teams.append(dict(id=team_id, name=name, standing=standing, **record(team['record']['overall'])))
    participants, matchup_ids = set(), set()

    def side(value):
        team_id = integer(value['teamId'], 1)
        if team_id not in team_ids or team_id in participants:
            raise ValueError
        participants.add(team_id)
        result = dict(teamId=team_id, points=None, pointSource=None,
                      categoryRecord=None, available=False)
        if scoring_type == 'H2H_CATEGORY':
            score = value.get('cumulativeScore')
            if score is not None:
                category_record = record(score)
                # ESPN nests per-stat evidence under cumulativeScore, not the side.
                evidence = score.get('scoreByStat')
                if evidence is not None and type(evidence) is not dict:
                    raise ValueError
                if any(category_record.values()) or bool(evidence):
                    result.update(categoryRecord=category_record, available=True)
        else:
            source = ('totalPointsLive' if 'totalPointsLive' in value else
                      'totalPoints' if 'totalPoints' in value else None)
            if source is not None:
                points = value[source]
                if type(points) not in (int, float) or not math.isfinite(points):
                    raise ValueError
                result.update(points=points, pointSource=source, available=True)
        return result

    if type(data['schedule']) is not list:
        raise ValueError
    matchups = []
    for matchup in data['schedule']:
        if integer(matchup['matchupPeriodId'], 1) != period:
            continue
        matchup_id = integer(matchup['id'])
        if matchup_id in matchup_ids:
            raise ValueError
        matchup_ids.add(matchup_id)
        matchups.append(dict(id=matchup_id, home=side(matchup['home']),
                             away=None if matchup.get('away') is None else side(matchup['away'])))
    if participants != team_ids:
        raise ValueError
    return dict(schemaVersion=1, mode='live', source='ESPN', dataKind='current-matchup-snapshot',
                fetchedAt=now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
                leagueId=LEAGUE_ID, seasonId=SEASON_ID, scoringType=scoring_type,
                matchupPeriodId=period, scoringPeriodId=scoring_period, teams=teams, matchups=matchups)


if __name__ == '__main__':
    sys.exit(main())

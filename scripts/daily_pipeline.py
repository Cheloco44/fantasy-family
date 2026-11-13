"""Bounded ESPN daily collection and offline, archive-driven clubhouse publishing.

No historical lineup inference. Only explicit date-keyed aggregate points count.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
import json
import math
import os
import re
import tempfile
from pathlib import Path
import sys
import unicodedata
from urllib.request import Request, build_opener

import collect_current as current_collector
from collect_current import NoRedirect, SafeArgumentParser
from lookup_daily import BASE, LEAGUE_ID, SEASON_ID, MAX_BYTES

TIME_ZONE = 'America/Phoenix'
ROOT = Path(__file__).resolve().parents[1]
METADATA_URL = BASE + '?view=proTeamSchedules_wl'
LEAGUE_BASE = BASE + '/segments/0/leagues/1399646897'


def require(condition):
    if not condition:
        raise ValueError('INVALID_DATA')


def integer(value, minimum=1):
    require(type(value) is int and value >= minimum)
    return value


def instant(value):
    require(type(value) is str)
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None and result.utcoffset() is not None)
    return result


def timestamp(now=None):
    now = datetime.now(timezone.utc) if now is None else now
    require(now.tzinfo is not None and now.utcoffset() is not None)
    return now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def target_date(value=None, now=None):
    now = instant(timestamp(now)).astimezone(ZoneInfo(TIME_ZONE))
    result = now.date() - timedelta(days=1) if value is None else date.fromisoformat(value)
    require(result.isoformat() == (result.isoformat() if value is None else value))
    require(date(2026, 9, 1) <= result < min(now.date(), date(2027, 7, 2)))
    return result.isoformat()


def text(value):
    require(type(value) is str and 1 <= len(value) <= 120 and value.strip()
            and not any(unicodedata.category(c).startswith('C') for c in value))
    return value


def number(value):
    require(type(value) in (int, float) and math.isfinite(value))
    return value


def derive_period(metadata, day):
    """Deduplicate both NHL sides; reject ambiguous or date-spanning periods."""
    games = {}
    teams = metadata['settings']['proTeams']
    require(type(teams) is list and bool(teams))
    for team in teams:
        mapping = team['proGamesByScoringPeriod']
        require(type(mapping) is dict)
        for key, group in mapping.items():
            require(type(group) is list)
            for game in group:
                gid, period = integer(game['id']), integer(game['scoringPeriodId'])
                require(str(period) == key and type(game['statsOfficial']) is bool)
                millis = integer(game['date'])
                game_day = datetime.fromtimestamp(millis / 1000, timezone.utc).astimezone(ZoneInfo(TIME_ZONE)).date().isoformat()
                evidence = (millis, period, game['statsOfficial'], game_day)
                require(gid not in games or games[gid] == evidence)
                games[gid] = evidence
    target = [g for g in games.values() if g[3] == day]
    if not target:
        # Empty/truncated metadata is never evidence of a hockey off-day.
        ids = [integer(t['id']) for t in teams]
        require(len(set(ids)) >= 32 and len(ids) == len(set(ids)) and bool(games))
        days = [g[3] for g in games.values()]
        require(min(days) < day < max(days))
        return None, dict(gameCount=0, allGamesStatsOfficial=False)
    periods = {g[1] for g in target}
    require(len(periods) == 1)
    period = periods.pop()
    require(not any(g[1] == period and g[3] != day for g in games.values()))
    return period, dict(gameCount=len(target), allGamesStatsOfficial=all(g[2] for g in target))


def normalize_daily(data, metadata, day, *, now=None):
    """Normalize daily points, keeping weekly totals out of the daily result."""
    day = target_date(day, now)
    period, evidence = derive_period(metadata, day)
    require(integer(data['id']) == LEAGUE_ID and integer(data['seasonId']) == SEASON_ID)
    require(period is None or integer(data['scoringPeriodId']) == period)
    require(data['settings']['scoringSettings']['scoringType'] == 'H2H_POINTS')
    require(type(data['teams']) is list and len(data['teams']) == 8)
    names = {}
    for team in data['teams']:
        tid = integer(team['id'])
        name = text(team['name'] if 'name' in team else team['location'] + ' ' + team['nickname'])
        require(tid not in names and name not in names.values())
        names[tid] = name
    if period is None:
        return dict(schemaVersion=1, source='ESPN', dataKind='daily-team-points', date=day,
                    timeZone=TIME_ZONE, fetchedAt=timestamp(now), leagueId=LEAGUE_ID,
                    seasonId=SEASON_ID, scoringType='H2H_POINTS', scoringPeriodId=None,
                    matchupPeriodId=None, periodEvidence=evidence, status='off-day', sourceRunUrl=None, matchups=[],
                    teams=[dict(id=tid, name=names[tid], dailyPoints=None, available=False,
                                pointSource=None) for tid in sorted(names)])
    schedule = data['schedule']
    require(type(schedule) is list)
    candidates = set()
    for match in schedule:
        mp = integer(match['matchupPeriodId'])
        for side in (match.get('home'), match.get('away')):
            if side is not None:
                points = side.get('pointsByScoringPeriod')
                require(points is None or type(points) is dict)
                if points is not None and str(period) in points:
                    candidates.add(mp)
    if not candidates:
        mapping = data['settings'].get('scheduleSettings', {}).get('matchupPeriods', {})
        require(type(mapping) is dict)
        for key, periods in mapping.items():
            mp = integer(int(key))
            require(str(mp) == key and type(periods) is list)
            for value in periods:
                integer(value)
            if period in periods:
                candidates.add(mp)
    require(len(candidates) == 1)
    mp = candidates.pop()
    teams, matchups, mids = {}, [], set()
    for match in schedule:
        if match['matchupPeriodId'] != mp:
            continue
        mid = integer(match['id'], 0)
        require(mid not in mids)
        mids.add(mid)
        pair = []
        for side in (match['home'], match['away']):
            tid = integer(side['teamId'])
            require(tid in names and tid not in teams)
            points = side.get('pointsByScoringPeriod')
            points = {} if points is None else points
            require(type(points) is dict)
            available = str(period) in points
            value = number(points[str(period)]) if available else None
            teams[tid] = dict(id=tid, name=names[tid], dailyPoints=value, available=available,
                              pointSource=f"pointsByScoringPeriod['{period}']" if available else None)
            pair.append(tid)
        matchups.append(dict(id=mid, homeId=pair[0], awayId=pair[1]))
    require(set(teams) == set(names))
    status = 'verified-aggregate' if evidence['allGamesStatsOfficial'] and all(t['available'] for t in teams.values()) else 'incomplete'
    return dict(schemaVersion=1, source='ESPN', dataKind='daily-team-points', date=day,
                timeZone=TIME_ZONE, fetchedAt=timestamp(now), leagueId=LEAGUE_ID, seasonId=SEASON_ID,
                scoringType='H2H_POINTS', scoringPeriodId=period, matchupPeriodId=mp,
                periodEvidence=evidence, teams=[teams[k] for k in sorted(teams)],
                status=status, sourceRunUrl=None, matchups=sorted(matchups, key=lambda m: m['id']))


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected.split()))


def validate_identity(value, kind):
    require(type(value['schemaVersion']) is int and value['schemaVersion'] == 1)
    require(value['source'] == 'ESPN' and value['dataKind'] == kind)
    require(integer(value['leagueId']) == LEAGUE_ID and integer(value['seasonId']) == SEASON_ID)
    require(value['scoringType'] == 'H2H_POINTS')
    instant(value['fetchedAt'])


def validate_teams(teams, daily=False):
    require(type(teams) is list and len(teams) == 8)
    ids, names = set(), set()
    for team in teams:
        keys(team, 'id name dailyPoints available pointSource' if daily else 'id name standing wins losses ties')
        tid, name = integer(team['id']), text(team['name'])
        require(tid not in ids and name not in names)
        ids.add(tid); names.add(name)
        if not daily:
            if team['standing'] is not None:
                require(integer(team['standing']) <= 8)
            for field in ('wins', 'losses', 'ties'):
                integer(team[field], 0)
    require(ids == set(range(1, 9)))
    return ids


def validate_current(value):
    keys(value, 'schemaVersion mode source dataKind fetchedAt leagueId seasonId scoringType matchupPeriodId scoringPeriodId teams matchups')
    validate_identity(value, 'current-matchup-snapshot')
    require(value['mode'] == 'live')
    integer(value['matchupPeriodId']); integer(value['scoringPeriodId'])
    ids = validate_teams(value['teams'])
    require(type(value['matchups']) is list)
    seen, mids = set(), set()
    for match in value['matchups']:
        keys(match, 'id home away')
        mid = integer(match['id'], 0)
        require(mid not in mids); mids.add(mid)
        require(match['home'] is not None)
        for side in (match['home'], match['away']):
            if side is None:
                continue
            keys(side, 'teamId points pointSource categoryRecord available')
            tid = integer(side['teamId'])
            require(tid in ids and tid not in seen); seen.add(tid)
            require(type(side['available']) is bool and side['categoryRecord'] is None)
            if side['available']:
                number(side['points'])
                require(side['pointSource'] in ('totalPointsLive', 'totalPoints'))
            else:
                require(side['points'] is None and side['pointSource'] is None)
    require(seen == ids)
    return value


def validate_bundle(value, *, now=None):
    keys(value, 'daily current')
    daily, current = value['daily'], value['current']
    keys(daily, 'schemaVersion source dataKind date timeZone fetchedAt leagueId seasonId scoringType scoringPeriodId matchupPeriodId periodEvidence teams status sourceRunUrl matchups')
    validate_identity(daily, 'daily-team-points')
    require(daily['timeZone'] == TIME_ZONE)
    target_date(daily['date'], now)
    target_date(daily['date'], instant(daily['fetchedAt']))
    require(daily['sourceRunUrl'] is None or (type(daily['sourceRunUrl']) is str and re.fullmatch(
        r'https://github\.com/Cheloco44/fantasy-family/actions/runs/[1-9][0-9]{0,19}', daily['sourceRunUrl']) is not None))
    ids = validate_teams(daily['teams'], daily=True)
    evidence = daily['periodEvidence']
    keys(evidence, 'gameCount allGamesStatsOfficial')
    integer(evidence['gameCount'], 0)
    require(type(evidence['allGamesStatsOfficial']) is bool)
    require(daily['status'] in ('verified-aggregate', 'incomplete', 'off-day'))
    require(type(daily['matchups']) is list)
    if daily['status'] == 'off-day':
        require(daily['scoringPeriodId'] is None and daily['matchupPeriodId'] is None
                and daily['matchups'] == [] and evidence == dict(gameCount=0, allGamesStatsOfficial=False))
    else:
        integer(daily['scoringPeriodId']); integer(daily['matchupPeriodId'])
        require(evidence['gameCount'] > 0)
    for team in daily['teams']:
        require(type(team['available']) is bool)
        if team['available']:
            require(daily['status'] != 'off-day')
            number(team['dailyPoints'])
            require(team['pointSource'] == f"pointsByScoringPeriod['{daily['scoringPeriodId']}']")
        else:
            require(team['dailyPoints'] is None and team['pointSource'] is None)
    if daily['status'] != 'off-day':
        verified = evidence['allGamesStatsOfficial'] and all(t['available'] for t in daily['teams'])
        require((daily['status'] == 'verified-aggregate') == verified)
    seen, mids = set(), set()
    for match in daily['matchups']:
        keys(match, 'id homeId awayId')
        mid = integer(match['id'], 0)
        require(mid not in mids); mids.add(mid)
        for field in ('homeId', 'awayId'):
            tid = integer(match[field])
            require(tid in ids and tid not in seen); seen.add(tid)
    require(daily['status'] == 'off-day' or seen == ids)
    validate_current(current)
    return value


def parse_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    def reject_constant(_):
        raise ValueError('INVALID_DATA')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=reject_constant)


def safe_path(path):
    path = Path(os.path.abspath(path))
    require(path.resolve() == path)
    return path


def read_json(path):
    path = safe_path(path)
    with path.open('rb') as handle:
        body = handle.read(MAX_BYTES + 1)
    require(len(body) <= MAX_BYTES)
    return parse_json(body)


def serialize(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')) + '\n'


def promote(outputs):
    """Stage every validated output first; atomic files, rollback on handled I/O failure.

    Multi-file crash atomicity is not possible with these separate contract paths.
    The workflow never commits/publishes a failed import.
    """
    staged, backups, applied = {}, {}, []
    try:
        for destination, content in outputs.items():
            destination = safe_path(destination)
            require(not destination.exists() or destination.is_file())
            if destination.exists() and destination.read_text(encoding='utf-8') == content:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                backups[destination] = destination.read_bytes()
            else:
                backups[destination] = None
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent,
                                             prefix='.daily-', suffix='.tmp', delete=False) as handle:
                staged[destination] = Path(handle.name)
                handle.write(content); handle.flush(); os.fsync(handle.fileno())
        for destination, temporary in staged.items():
            os.replace(temporary, destination)
            applied.append(destination)
    except Exception:
        for destination in reversed(applied):
            backup = backups[destination]
            if backup is None:
                destination.unlink(missing_ok=True)
            else:
                # Same-directory atomic rollback using the existing reviewed writer.
                current_collector.atomic_write(destination, backup.decode('utf-8'))
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def fetch(url, cookies, opener_factory):
    headers = {} if cookies is None else {'Cookie': f'espn_s2={cookies[0]}; SWID={cookies[1]}'}
    with opener_factory(NoRedirect()).open(Request(url, method='GET', headers=headers), timeout=20) as response:
        require(response.status == 200)
        body = response.read(MAX_BYTES + 1)
        require(len(body) <= MAX_BYTES)
        return parse_json(body)


def collect(output_dir, day, *, environ, opener_factory=build_opener, now=None):
    cookies = [environ.get('ESPN_S2'), environ.get('ESPN_SWID')]
    require(all(type(v) is str and v and len(v) <= 16384 and not any(
        ord(c) < 33 or ord(c) > 126 or c in ';,"\\\\' for c in v) for v in cookies))
    day = target_date(day, now)
    output_dir = safe_path(output_dir)
    require(not output_dir.is_relative_to(ROOT) or output_dir.is_relative_to(ROOT / 'artifacts'))
    require(not output_dir.exists() or (output_dir.is_dir() and
            {p.name for p in output_dir.iterdir()} <= {'daily.json', 'current.json'}))
    metadata = fetch(METADATA_URL, None, opener_factory)
    period, _ = derive_period(metadata, day)  # Fail before sending any cookie.
    if period is not None:
        url = LEAGUE_BASE + '?view=mSettings&view=mTeam&view=mMatchupScore&view=mScoreboard&scoringPeriodId=' + str(integer(period))
        data = fetch(url, cookies, opener_factory)
        daily = normalize_daily(data, metadata, day, now=now)
    data = fetch(current_collector.URL, cookies, opener_factory)
    if period is None:
        daily = normalize_daily(data, metadata, day, now=now)
    run_id = environ.get('GITHUB_RUN_ID', '')
    if environ.get('GITHUB_REPOSITORY') == 'Cheloco44/fantasy-family' and type(run_id) is str and re.fullmatch(r'[1-9][0-9]{0,19}', run_id):
        daily['sourceRunUrl'] = 'https://github.com/Cheloco44/fantasy-family/actions/runs/' + run_id
    current = current_collector.normalize(data, now=now)
    validate_bundle(dict(daily=daily, current=current), now=now)
    outputs = {output_dir / 'daily.json': serialize(daily), output_dir / 'current.json': serialize(current)}
    require(not any(cookie in content for cookie in cookies for content in outputs.values()))
    promote(outputs)


def asset_path(image, root):
    require(type(image) is str and re.fullmatch(r'(avatars|memes)/[A-Za-z0-9_/-]+\.(webp|jpg|jpeg|png|gif)', image) is not None)
    require(all(part not in ('', '.', '..') for part in image.split('/')))
    path = safe_path(Path(root) / 'public' / image)
    require(path.is_file() and path.is_relative_to(safe_path(Path(root) / 'public')))
    return image


def validate_catalog(catalog, profiles, root):
    keys(catalog, 'schemaVersion timezone publishTarget closeMargin smokedMargin cast approvedMemes')
    require(type(catalog['schemaVersion']) is int and catalog['schemaVersion'] == 1)
    require(catalog['timezone'] == TIME_ZONE and catalog['publishTarget'] == '07:00')
    require(type(catalog['closeMargin']) is int and 0 <= catalog['closeMargin'] <= 1000)
    require(type(catalog['smokedMargin']) is int and catalog['closeMargin'] < catalog['smokedMargin'] <= 10000)
    cast = catalog['cast']
    require(type(cast) is dict and set(cast) == {str(i) for i in range(1, 9)})
    slugs, names = set(), set()
    for person in cast.values():
        require(type(person) is dict and set(person) in ({'slug', 'displayName'}, {'slug', 'displayName', 'teamName'}))
        if 'teamName' in person:
            text(person['teamName'])
        require(type(person['slug']) is str and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', person['slug']) is not None)
        name = text(person['displayName'])
        require(person['slug'] not in slugs and name not in names)
        slugs.add(person['slug']); names.add(name)
    require(type(catalog['approvedMemes']) is list)
    ids = set()
    for meme in catalog['approvedMemes']:
        fields = set('id image caption date managers tags approvalStatus contextType'.split())
        require(type(meme) is dict and set(meme) in (fields, fields | {'scoreContext'}))
        if 'scoreContext' in meme:
            context = meme['scoreContext']
            require(type(context) is dict and bool(context) and set(context) <= set(cast))
            for value in context.values():
                number(value)
        mid = text(meme['id'])
        require(mid not in ids); ids.add(mid)
        require(meme['approvalStatus'] == 'approved' and meme['contextType'] in ('dated', 'evergreen'))
        require(type(meme['caption']) is str and 1 <= len(meme['caption']) <= 1000)
        if meme['contextType'] == 'dated' or meme['date'] is not None:
            require(type(meme['date']) is str and date.fromisoformat(meme['date']).isoformat() == meme['date'])
        for key in ('managers', 'tags'):
            require(type(meme[key]) is list and all(type(v) is str for v in meme[key]) and len(meme[key]) == len(set(meme[key])))
        require(set(meme['managers']) <= slugs)
        asset_path(meme['image'], root)
    require(type(profiles['managers']) is list)
    avatars = {}
    for person in profiles['managers']:
        if person['slug'] in slugs:
            require(person['slug'] not in avatars and person['approved'] is True)
            avatars[person['slug']] = asset_path(person['image'], root)
    require(set(avatars) == slugs)
    return avatars


def choose_meme(catalog, avatars, day, home_slug, away_slug, points=None):
    pair = {home_slug, away_slug}
    candidates = [m for m in catalog['approvedMemes'] if set(m['managers']) <= pair and
                  (m['contextType'] == 'evergreen' or m['date'] == day) and
                  ('scoreContext' not in m or (points is not None and
                   all(points.get(int(tid)) == score for tid, score in m['scoreContext'].items())))]
    candidates.sort(key=lambda m: (m['contextType'] != 'dated', -len(m['managers']), m['id']))
    if candidates:
        meme = candidates[0]
        return dict(id=meme['id'], image=meme['image'], caption=meme['caption'],
                    sourceDate=meme['date'] if meme['contextType'] == 'dated' else None,
                    isArchive=False, approvalStatus='approved')
    return dict(id='avatar-' + home_slug, image=avatars[home_slug],
                caption='Approved portrait fallback — no new image approved for this date.',
                sourceDate=None, isArchive=False, approvalStatus='approved')


def rolling_note(bundles, day, tid, alias, *, brief=False):
    start = (date.fromisoformat(day) - timedelta(days=6)).isoformat()
    wins = losses = ties = 0
    for value in bundles:
        daily = value['daily']
        if daily['status'] != 'verified-aggregate' or not start <= daily['date'] <= day:
            continue
        points = {t['id']: t['dailyPoints'] for t in daily['teams']}
        match = next(m for m in daily['matchups'] if tid in (m['homeId'], m['awayId']))
        opponent = match['awayId'] if match['homeId'] == tid else match['homeId']
        wins += points[tid] > points[opponent]
        losses += points[tid] < points[opponent]
        ties += points[tid] == points[opponent]
    count = wins + losses + ties
    if brief:
        if losses >= 3:
            return f'{alias} is starting to look like a bye week with Wi-Fi: {losses} daily-round losses in the last seven days.'
        if wins >= 3 and wins > losses:
            return f'{alias} has stacked {wins} daily-round wins in the last seven days. The group chat is running out of excuses.'
        return ''
    note = (f'{alias}: {wins}-{losses}-{ties} across {count} verified DAILY ROUNDS in the seven-calendar-day '
            f'window {start}–{day}; coverage {count}/7 calendar dates. Missing dates and off-days '
            'are not losses; not official ESPN weekly W–L.')
    if losses >= 3:
        note += f' {alias} is starting to look like a bye week with Wi-Fi: {losses} recorded DAILY ROUND losses in this window, not a continuous losing streak.'
    return note


def character_chirp(slug, won):
    """Owner-approved fictional cast beats, never real quotes or biographical evidence."""
    beats = {
        'marcelo': ('The Commissioner keeps the throne and graciously cancels the recount he would have demanded if he lost.', 'The Commissioner fell off his throne. Apparently the constitution forgot to award points for being in charge.'),
        'rich': ('The Juice turns cartoon supplement horsepower into bragging rights. The imaginary blender has a better agent than the manager.', 'All that cartoon roid horsepower and The Juice still needs a jump-start. The comeback movie went straight to the bargain bin.'),
        'zach': ('June Bug, the polite assassin, sends a thank-you card with the daily receipt. Somehow the manners make it worse.', 'June Bug met the bug zapper. Impeccable manners; absolutely no refund on the result.'),
        'ben': ('Ben won and still needs something to complain about. Somebody get this man a refund for the inconvenience of winning.', 'Ben has filed a complaint against arithmetic. The threat to quit is ready; the unsubscribe button remains untouched.'),
        'jake': ('UGG. BONK. The Caveman drags the receipt back to the Stone Age. Neanderthal customer service: every complaint gets an extinction event.', 'GRONK. The Caveman brought a rock to a Wi-Fi problem. Neanderthal tech support has tried BONK and is all out of ideas.'),
        'robert': ('IR BOB and the imaginary team-mom group chat are running the Anti-Commish victory parade. Even the fictional carpool has an opposition whip.', 'IR BOB has called an emergency imaginary team-mom meeting. Team Anti-Commish needs a game plan, not a bigger carpool.'),
        'erik': ('SYSTEM: Skynet online. STATUS: DAILY VICTORY. Auto Erik prints the receipt; opponent requests a factory reset on the whole damn day. REQUEST DENIED.', 'SYSTEM: Skynet malfunction. STATUS: DAILY ERROR. Auto Erik demoted to a toaster. Reboot complete; excuses still incompatible with the scoreboard.'),
        'kyle': ('Jive Turkey gets the daily bragging rights; AI remains the designated scapegoat. Even a win cannot uninstall the excuses.', 'The Young Monkey ordered banter and got return fire with free shipping. Blaming AI will not cover the postage.')}
    return beats.get(slug, ('', ''))[0 if won else 1]


def build_recaps(bundles, catalog, profiles, *, root=ROOT, now=None):
    avatars = validate_catalog(catalog, profiles, root)
    dates = set()
    for value in bundles:
        validate_bundle(value, now=now)
        require(value['daily']['date'] not in dates)
        dates.add(value['daily']['date'])
    editions = []
    for value in sorted(bundles, key=lambda b: b['daily']['date'], reverse=True):
        daily, current = value['daily'], value['current']
        day, status = daily['date'], daily['status']
        points = {t['id']: t['dailyPoints'] for t in daily['teams']}
        matches = []
        for match in daily['matchups']:
            hid, aid = match['homeId'], match['awayId']
            home, away = catalog['cast'][str(hid)], catalog['cast'][str(aid)]
            hp, ap = points[hid], points[aid]
            margin = None if hp is None or ap is None else number(float(abs(Decimal(str(hp)) - Decimal(str(ap)))))
            classification = 'unavailable'
            title = f"{home['displayName']} vs {away['displayName']} — DAILY ROUND incomplete"
            story = 'DAILY ROUND incomplete: missing or provisional aggregate evidence. No daily win or loss is awarded.'
            if status == 'verified-aggregate':
                if margin == 0:
                    classification = 'tie'
                    title = f"{home['displayName']} and {away['displayName']} — DAILY ROUND tied"
                    story = f"DAILY ROUND tied at {hp:g} points each. Both brought the same receipt; neither gets a victory lap."
                else:
                    winner, loser = (home['displayName'], away['displayName']) if hp > ap else (away['displayName'], home['displayName'])
                    classification = 'close' if margin <= catalog['closeMargin'] else 'smoked' if margin >= catalog['smokedMargin'] else 'standard'
                    if classification == 'close':
                        title = f'{winner} escapes {loser} — DAILY ROUND by {margin:g}'
                        story = (f'DAILY ROUND: {winner} edges {loser} by {margin:g}. '
                                 'Close enough to call the victory parade a bit much. '
                                 'One daily edge, not the weekly verdict.')
                    elif classification == 'smoked':
                        title = f'{winner} puts {loser} in the DAILY ROUND body bag'
                        story = (f'DAILY ROUND: {winner} smokes {loser} by {margin:g}. '
                                 f'{loser} brought a participation trophy to a demolition derby. '
                                 'Daily bragging rights only, not a completed weekly win.')
                    else:
                        title = f'{winner} hands {loser} the DAILY ROUND receipt'
                        story = (f'DAILY ROUND: {winner} takes the day over {loser} by {margin:g}. '
                                 f"{loser}’s excuse department is open; the scoreboard is not taking returns. "
                                 'Daily bragging rights, not a completed weekly win.')
                    story += ' ' + ' '.join(filter(None, (character_chirp(home['slug'], hp > ap), character_chirp(away['slug'], ap > hp))))
            weekly = None
            if current['matchupPeriodId'] == daily['matchupPeriodId']:
                for cm in current['matchups']:
                    if cm['away'] is None or {cm['home']['teamId'], cm['away']['teamId']} != {hid, aid}:
                        continue
                    sides = {s['teamId']: s for s in (cm['home'], cm['away'])}
                    if sides[hid]['available'] and sides[aid]['available']:
                        weekly = (f"Current weekly snapshot at {current['fetchedAt']}: {home['displayName']} "
                                  f"{sides[hid]['points']:g}, {away['displayName']} {sides[aid]['points']:g}; "
                                  'separate from the DAILY ROUND, not end-of-day and not a final weekly result.')
            if status == 'verified-aggregate':
                chirps = [rolling_note(bundles, day, tid, person['displayName'], brief=True)
                          for tid, person in ((hid, home), (aid, away))]
                story = ' '.join([story.strip(), *filter(None, chirps)])
            matches.append(dict(id=match['id'], homeId=hid, awayId=aid, homeAlias=home['displayName'],
                awayAlias=away['displayName'], homePoints=hp, awayPoints=ap, margin=margin,
                classification=classification, title=title, story=story,
                trendNotes=[rolling_note(bundles, day, tid, person['displayName']) for tid, person in ((hid, home), (aid, away))],
                weeklySummary=weekly, meme=choose_meme(catalog, avatars, day, home['slug'], away['slug'], points)))
        coverage = ('No scheduled NHL games in complete public schedule evidence; no daily points or W/L awarded.' if status == 'off-day' else
                    f"{daily['periodEvidence']['gameCount']} scheduled NHL games; statsOfficial={str(daily['periodEvidence']['allGamesStatsOfficial']).lower()}; "
                    f"{sum(t['available'] for t in daily['teams'])}/8 team daily aggregates available. "
                    'Provider aggregate evidence only; no player/lineup attribution or correction-finality claim.')
        headline = ('Hockey takes the night off' if status == 'off-day' else 'DAILY ROUND on hold — incomplete evidence' if status == 'incomplete' else 'DAILY ROUND — the receipts are in')
        if status == 'verified-aggregate':
            decided = [m for m in matches if m['classification'] in ('close', 'standard', 'smoked')]
            if decided:
                # Largest actual daily margin leads, never the highest individual total.
                # Equal margins use the lowest matchup ID, independent of source ordering.
                lead = max(decided, key=lambda m: (m['margin'], -m['id']))
                winner, loser = ((lead['homeAlias'], lead['awayAlias'])
                                 if lead['homePoints'] > lead['awayPoints'] else
                                 (lead['awayAlias'], lead['homeAlias']))
                if lead['classification'] == 'smoked':
                    headline = (f"DAILY ROUND: {winner} cooks {loser} by {lead['margin']:g} — "
                                'somebody unplug the damn oven.')
                elif lead['classification'] == 'close':
                    headline = f"DAILY ROUND: {winner} escapes {loser} by {lead['margin']:g} — save the parade."
                else:
                    headline = (f"DAILY ROUND: {winner} sends {loser}’s excuses to voicemail — "
                                f"{lead['margin']:g} points.")
            else:
                headline = 'DAILY ROUND tied — No daily winner. Nobody gets the victory lap.'
        editions.append(dict(date=day, sourceFetchedAt=daily['fetchedAt'], sourceRunUrl=daily['sourceRunUrl'],
            scoringPeriodId=daily['scoringPeriodId'], matchupPeriodId=daily['matchupPeriodId'], status=status,
            headline=headline, dek='Yesterday’s points. Today’s grudges. Daily rounds—not a final weekly verdict.',
            coverageNote=coverage, weeklyContextAt=current['fetchedAt'] if any(m['weeklySummary'] is not None for m in matches) else None,
            matchups=matches))
    result = dict(schemaVersion=1, timezone=TIME_ZONE, publishTarget='07:00', editions=editions)
    serialize(result)  # Reject any nonfinite derived value before a write is staged.
    return result


def load_archive(root, *, now=None):
    directory = safe_path(Path(root) / 'src/data/daily')
    archived = {}
    if directory.exists():
        require(directory.is_dir())
        for path in sorted(directory.iterdir()):
            require(path.is_file() and re.fullmatch(r'202[67]-[0-9]{2}-[0-9]{2}\.json', path.name) is not None)
            value = validate_bundle(read_json(path), now=now)
            day = value['daily']['date']
            require(path.name == day + '.json' and day not in archived)
            archived[day] = value
    return archived


def report_for(archived, root, *, now=None):
    data = Path(root) / 'src/data'
    return build_recaps(list(archived.values()), read_json(data / 'editorial.json'),
                        read_json(data / 'clubhouse.json'), root=root, now=now)


def rebuild(*, root=ROOT, now=None):
    root = safe_path(root)
    archived = load_archive(root, now=now)
    require(bool(archived))  # Never erase the last report because history disappeared.
    report = report_for(archived, root, now=now)
    promote({root / 'src/data/recaps.json': serialize(report)})


def import_batch(input_dir, *, root=ROOT, now=None):
    root, input_dir = safe_path(root), safe_path(input_dir)
    require(input_dir.is_dir() and {p.name for p in input_dir.iterdir()} == {'daily.json', 'current.json'})
    value = validate_bundle(dict(daily=read_json(input_dir / 'daily.json'),
                                 current=read_json(input_dir / 'current.json')), now=now)
    archived = load_archive(root, now=now)
    day = value['daily']['date']
    archived[day] = value
    report = report_for(archived, root, now=now)
    data = root / 'src/data'
    outputs = {data / 'daily' / (day + '.json'): serialize(value), data / 'recaps.json': serialize(report)}
    latest_current = value['current']
    current_path = safe_path(data / 'current.json')
    write_current = True
    if current_path.exists():
        previous = validate_current(read_json(current_path))
        if instant(latest_current['fetchedAt']) <= instant(previous['fetchedAt']):
            write_current = False
    if write_current:
        outputs[current_path] = serialize(latest_current)
    # Validate *all* destination paths and serialized outputs before staging any write.
    for path, content in outputs.items():
        safe_path(path)
        require(len(content.encode('utf-8')) <= MAX_BYTES)
    promote(outputs)


def main(argv=None, *, environ=None, opener_factory=build_opener, now=None, root=ROOT):
    parser = SafeArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True, parser_class=SafeArgumentParser)
    collector = commands.add_parser('collect')
    collector.add_argument('--network', action='store_true')
    collector.add_argument('--date')
    collector.add_argument('--output-dir', default='artifacts/daily-batch')
    importer = commands.add_parser('import')
    importer.add_argument('--input-dir', default='artifacts/daily-batch')
    commands.add_parser('rebuild')
    args = parser.parse_args(argv)
    if args.command == 'collect' and not args.network:
        print('ERROR network disabled; pass --network.', file=sys.stderr)
        return 2
    environ = (os.environ if environ is None else environ) if args.command == 'collect' else {}
    try:
        if args.command == 'collect':
            collect(args.output_dir, args.date, environ=environ, opener_factory=opener_factory, now=now)
        elif args.command == 'import':
            import_batch(args.input_dir, root=root, now=now)
        else:
            rebuild(root=root, now=now)
    except Exception:
        # No traceback, provider text, source paths, dates or credential-derived diagnostics.
        message = 'ERROR daily pipeline failed.'
        if not any(type(environ.get(k)) is str and environ[k] and environ[k] in message for k in ('ESPN_S2', 'ESPN_SWID')):
            print(message, file=sys.stderr)
        return 1
    message = 'OK daily pipeline complete.'
    if not any(type(environ.get(k)) is str and environ[k] and environ[k] in message for k in ('ESPN_S2', 'ESPN_SWID')):
        print(message)
    return 0


if __name__ == '__main__':
    sys.exit(main())


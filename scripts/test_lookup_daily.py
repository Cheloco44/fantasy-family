"""Offline contract tests; all provider data and credentials are synthetic."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr
import io
import tempfile

try:
    import lookup_daily as lookup
except ModuleNotFoundError:
    lookup = None


def metadata():
    game = dict(id=101, date=int(datetime(2026, 11, 12, 2, tzinfo=timezone.utc).timestamp() * 1000),
                scoringPeriodId=44, statsOfficial=True)
    tomorrow = dict(id=102, date=game['date'] + 86400000, scoringPeriodId=45, statsOfficial=True)
    return {'settings': {'proTeams': [
        {'proGamesByScoringPeriod': {'44': [game], '45': [tomorrow]}},
        {'proGamesByScoringPeriod': {'44': [copy.deepcopy(game)]}}]}}


def league():
    return dict(id=1399646897, seasonId=2027, scoringPeriodId=44,
                settings={'scoringSettings': {'scoringType': 'H2H_POINTS'},
                          'scheduleSettings': {'matchupPeriods': {'6': [43, 44, 45]}}},
                members=[{'email': 'private@example.invalid'}],
                teams=[dict(id=i, name=f'Canonical {i}', owners=['private-owner']) for i in range(1, 9)],
                schedule=[dict(id=i, matchupPeriodId=6,
                               home=dict(teamId=i, pointsByScoringPeriod={'44': 10}, totalPointsLive=100),
                               away=dict(teamId=i+1, pointsByScoringPeriod={'44': 10}, totalPoints=100))
                          for i in range(1, 9, 2)])


NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)


class NormalizeTests(unittest.TestCase):
    def test_daily_not_weekly_and_only_allowlist(self):
        self.assertTrue(callable(getattr(lookup, 'normalize', None)))
        result = lookup.normalize(league(), metadata(), now=NOW)
        self.assertEqual(set(result), {'schemaVersion', 'source', 'dataKind', 'date', 'timeZone',
                         'fetchedAt', 'leagueId', 'seasonId', 'scoringType', 'scoringPeriodId',
                         'matchupPeriodId', 'periodEvidence', 'teams'})
        self.assertEqual(result['date'], '2026-11-11')
        self.assertEqual(result['timeZone'], 'America/Phoenix')
        self.assertEqual(result['scoringPeriodId'], 44)
        self.assertEqual(result['matchupPeriodId'], 6)
        self.assertEqual(len(result['teams']), 8)
        self.assertEqual(result['teams'][0], dict(id=1, name='Canonical 1', dailyPoints=10,
                         available=True, pointSource="pointsByScoringPeriod['44']"))
        text = json.dumps(result)
        for private in ('email', 'owner', 'members', 'totalPoints', 'private@', 'player'):
            self.assertNotIn(private, text)

    def test_zero_negative_and_missing_remain_distinct(self):
        data = league()
        data['schedule'][0]['home']['pointsByScoringPeriod']['44'] = 0
        data['schedule'][0]['away']['pointsByScoringPeriod']['44'] = -2.5
        del data['schedule'][1]['home']['pointsByScoringPeriod']
        data['schedule'][1]['away']['pointsByScoringPeriod'] = {'43': 900, 'providerPrivate': 'secret'}
        result = lookup.normalize(data, metadata(), now=NOW)['teams']
        self.assertEqual([t['dailyPoints'] for t in result[:4]], [0, -2.5, None, None])
        self.assertEqual([t['available'] for t in result[:4]], [True, True, False, False])
        self.assertIsNone(result[2]['pointSource'])
        self.assertNotIn('providerPrivate', json.dumps(result))

    def test_unscored_other_matchups_do_not_block_verified_daily_points(self):
        data = league()
        data['schedule'].append(dict(id=999, matchupPeriodId=20,
                                     home=dict(teamId=1, pointsByScoringPeriod=None),
                                     away=dict(teamId=2, pointsByScoringPeriod=None)))
        result = lookup.normalize(data, metadata(), now=NOW)
        self.assertEqual(len(result['teams']), 8)
        self.assertTrue(all(t['dailyPoints'] == 10 for t in result['teams']))
        data['schedule'][0]['home']['pointsByScoringPeriod'] = None
        result = lookup.normalize(data, metadata(), now=NOW)
        self.assertIsNone(result['teams'][0]['dailyPoints'])
        self.assertFalse(result['teams'][0]['available'])

    def test_duplicate_canonical_names_are_rejected(self):
        data = league(); data['teams'][1]['name'] = data['teams'][0]['name']
        with self.assertRaises(ValueError):
            lookup.normalize(data, metadata(), now=NOW)

    def test_invalid_daily_points_fail_closed(self):
        for value in (True, False, float('nan'), float('inf'), -float('inf'), '10', None):
            data = league(); data['schedule'][0]['home']['pointsByScoringPeriod']['44'] = value
            with self.subTest(value=str(value)), self.assertRaises(ValueError):
                lookup.normalize(data, metadata(), now=NOW)

    def test_invalid_identity_names_period_and_coverage(self):
        variants = []
        for field, value in [('id', 1), ('id', True), ('seasonId', 2026), ('scoringPeriodId', 45),
                             ('scoringPeriodId', True)]:
            data = league(); data[field] = value; variants.append(data)
        data = league(); data['settings']['scoringSettings']['scoringType'] = 'H2H_CATEGORY'; variants.append(data)
        for name in ('', '  ', 'bad\nname', 'x' * 121, 42):
            data = league(); data['teams'][0]['name'] = name; variants.append(data)
        data = league(); data['teams'].pop(); variants.append(data)
        data = league(); data['teams'][1]['id'] = 1; variants.append(data)
        data = league(); data['schedule'][0]['away']['teamId'] = 1; variants.append(data)
        data = league(); data['schedule'][0]['away']['teamId'] = 99; variants.append(data)
        data = league(); data['schedule'].pop(); variants.append(data)
        data = league(); data['schedule'][0]['away'] = None; variants.append(data)
        data = league(); data['schedule'].append(copy.deepcopy(data['schedule'][0])); variants.append(data)
        data = league(); data['settings']['scheduleSettings']['matchupPeriods']['7'] = [44]; variants.append(data)
        data = league(); data['settings']['scheduleSettings']['matchupPeriods'] = {'7': [45]}; variants.append(data)
        data = league(); data['schedule'].append(dict(matchupPeriodId=7, home=dict(teamId=1, pointsByScoringPeriod={'44': 2}), away=dict(teamId=2)))
        variants.append(data)
        for index, data in enumerate(variants):
            with self.subTest(case=index), self.assertRaises(ValueError):
                lookup.normalize(data, metadata(), now=NOW)
        with self.assertRaises(ValueError):
            lookup.normalize(league(), metadata(), now=datetime(2026, 11, 12))

    def test_schedule_daily_keys_can_establish_period_without_settings_mapping(self):
        data = league(); del data['settings']['scheduleSettings']['matchupPeriods']
        data['teams'][0]['name'] = 'Équipe — Original'
        self.assertEqual(lookup.normalize(data, metadata(), now=NOW)['teams'][0]['name'], 'Équipe — Original')
        data['schedule'][0]['home'].pop('pointsByScoringPeriod')
        self.assertEqual(lookup.normalize(data, metadata(), now=NOW)['matchupPeriodId'], 6)


class Response:
    def __init__(self, data, status=200):
        self.body = json.dumps(data).encode()
        self.status = status
        self.bounds = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, bound):
        self.bounds.append(bound)
        return self.body[:bound]


class TransportTests(unittest.TestCase):
    cookies = {'ESPN_S2': 'synthetic-s2-token', 'ESPN_SWID': '{synthetic-swid}'}

    def invoke(self, args, responses, *, environ=None):
        self.assertTrue(callable(getattr(lookup, 'main', None)))
        calls, handlers = [], []
        class Opener:
            def open(inner, request, timeout):
                calls.append((request, timeout))
                response = responses[len(calls)-1]
                if isinstance(response, Exception):
                    raise response
                return response
        def factory(handler):
            handlers.append(handler)
            return Opener()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = lookup.main(args, environ=self.cookies if environ is None else environ,
                               opener_factory=factory, now=NOW)
        return code, out.getvalue(), err.getvalue(), calls, handlers

    def test_safe_optin_diagnostics_expose_only_types_counts_and_stage(self):
        data = league(); data['scoringPeriodId'] = 45
        data['schedule'][0]['home']['pointsByScoringPeriod'] = None
        data['members'] = [{'email': 'private-person@example.invalid'}]
        code, out, err, _, _ = self.invoke(['--network', '--diagnostic'], [Response(metadata()), Response(data)])
        self.assertEqual((code, out), (1, ''))
        prefix = 'SAFE_LOOKUP_DIAGNOSTIC '
        diagnostic = json.loads(next(line[len(prefix):] for line in err.splitlines() if line.startswith(prefix)))
        self.assertEqual(diagnostic['stage'], 'league-normalization')
        self.assertTrue(diagnostic['sourceLines'])
        self.assertTrue(all(type(line) is int and 0 < line < 10000 for line in diagnostic['sourceLines']))
        self.assertEqual(diagnostic['summary']['responseScoringPeriod'], 45)
        self.assertEqual(diagnostic['summary']['nullDailyMapCount'], 1)
        self.assertEqual(diagnostic['summary']['targetDailySideCount'], 7)
        self.assertEqual(set(diagnostic['summary']), {'responseScoringPeriod', 'teamCount', 'leagueMatches', 'seasonMatches', 'pointsScoring', 'nullDailyMapCount', 'targetDailySideCount', 'targetDailyValueTypes'})
        for private in ('private-person', 'Canonical', 'members', 'email', 'synthetic-s2-token', '{synthetic-swid}'):
            self.assertNotIn(private, err)
        code, _, err, _, _ = self.invoke(['--network', '--diagnostic'], [Response(metadata()), Response(data)], environ=dict(self.cookies, ESPN_S2='45'))
        self.assertEqual(code, 1)
        self.assertNotIn(prefix, err)

    def test_fixed_gets_metadata_never_authenticated_and_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            responses = [Response(metadata()), Response(league())]
            code, out, err, calls, handlers = self.invoke(['--network', '--output', str(path)], responses)
            self.assertEqual((code, err), (0, ''))
            self.assertEqual(out, 'OK teams=8 available=8 scoringPeriodId=44\n')
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][0].full_url, 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2027?view=proTeamSchedules_wl&scoringPeriodId=44')
            self.assertEqual(calls[1][0].full_url, 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2027/segments/0/leagues/1399646897?view=mSettings&view=mTeam&view=mMatchupScore&view=mScoreboard&scoringPeriodId=44')
            self.assertIsNone(calls[0][0].get_header('Cookie'))
            self.assertEqual(calls[1][0].get_header('Cookie'), 'espn_s2=synthetic-s2-token; SWID={synthetic-swid}')
            for request, timeout in calls:
                self.assertEqual(request.get_method(), 'GET')
                self.assertEqual(timeout, 20)
            self.assertTrue(all(isinstance(h, lookup.NoRedirect) for h in handlers))
            self.assertTrue(all(r.bounds == [8 * 1024 * 1024 + 1] for r in responses))
            result = json.loads(path.read_text())
            self.assertEqual(result['teams'][0]['dailyPoints'], 10)
            for cookie in self.cookies.values():
                self.assertNotIn(cookie, path.read_text() + out + err)

    def test_no_network_and_invalid_credentials_never_open_or_write(self):
        cases = [([], self.cookies, 2), (['--network'], {}, 1)]
        for value in ('', 'bad\nvalue', 'bad;value', 'bad,value', 'bad"value', 'bad\\value', 'é', 'a b', 1):
            cases.append((['--network'], dict(self.cookies, ESPN_S2=value), 1))
        cases.append((['--network'], {'ESPN_S2': 'only-one'}, 1))
        for index, (args, environ, expected) in enumerate(cases):
            with self.subTest(case=index), patch.object(lookup, 'atomic_write') as write:
                code, out, err, calls, _ = self.invoke(args, [], environ=environ)
                self.assertEqual(code, expected)
                self.assertEqual(out, '')
                self.assertTrue(err.startswith('ERROR '))
                self.assertEqual(calls, [])
                write.assert_not_called()

    def test_failures_preserve_last_good_and_sanitize_logs(self):
        bad_json = Response({}); bad_json.body = b'private body not json'
        oversized = Response({}); oversized.body = b'x' * (8 * 1024 * 1024 + 1)
        invalid_meta = metadata(); invalid_meta['settings']['proTeams'] = []
        invalid_league = league(); invalid_league['id'] = 1
        failures = [[RuntimeError('private body synthetic-s2-token /private/path')],
                    [Response({}, status=302)], [Response({}, status=500)], [bad_json], [oversized],
                    [Response(invalid_meta)], [Response(metadata()), Response({}, status=302)],
                    [Response(metadata()), Response(invalid_league)]]
        for index, responses in enumerate(failures):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'last-good.json'; path.write_text('last-good')
                code, out, err, calls, _ = self.invoke(['--network', '--output', str(path)], responses)
                self.assertEqual((code, out, err), (1, '', 'ERROR lookup failed.\n'))
                self.assertEqual(path.read_text(), 'last-good')
                self.assertEqual(list(Path(directory).iterdir()), [path])
                if index == 5:
                    self.assertEqual(len(calls), 1)

    def test_cookie_collision_rejected_before_atomic_write(self):
        for collision in ('synthetic-s2-token', '{synthetic-swid}', '2026-11-11'):
            data = league(); data['teams'][0]['name'] = collision
            environ = self.cookies if collision != '2026-11-11' else dict(self.cookies, ESPN_S2=collision)
            with self.subTest(collision=collision), patch.object(lookup, 'atomic_write') as write:
                code, out, err, _, _ = self.invoke(['--network'], [Response(metadata()), Response(data)], environ=environ)
                self.assertEqual((code, out, err), (1, '', 'ERROR lookup failed.\n'))
                write.assert_not_called()

    def test_write_failure_is_sanitized_and_missing_scores_reported(self):
        data = league()
        for match in data['schedule']:
            for side in (match['home'], match['away']):
                side.pop('pointsByScoringPeriod')
        with patch.object(lookup, 'atomic_write') as write:
            code, out, err, _, _ = self.invoke(['--network'], [Response(metadata()), Response(data)])
            self.assertEqual((code, out, err), (0, 'OK teams=8 available=0 scoringPeriodId=44\n', ''))
            self.assertEqual(write.call_args.args[0], 'artifacts/daily-lookup/nov-11.json')
            self.assertTrue(all(t['dailyPoints'] is None for t in json.loads(write.call_args.args[1])['teams']))
        with patch.object(lookup, 'atomic_write', side_effect=OSError('private path synthetic-s2-token')):
            code, out, err, _, _ = self.invoke(['--network'], [Response(metadata()), Response(data)])
            self.assertEqual((code, out, err), (1, '', 'ERROR lookup failed.\n'))

    def test_no_redirect_handler_and_argument_errors_are_safe(self):
        self.assertIsNone(lookup.NoRedirect().redirect_request(None, None, 302, 'private', {}, 'https://evil.invalid'))
        out = io.StringIO()
        with redirect_stderr(out), self.assertRaises(SystemExit) as caught:
            lookup.main(['--date=private-token'])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(out.getvalue(), 'ERROR invalid arguments.\n')


class WorkflowTests(unittest.TestCase):
    def test_manual_main_only_readonly_and_step_scoped_secrets(self):
        path = Path(__file__).resolve().parents[1] / '.github/workflows/lookup-daily.yml'
        self.assertTrue(path.is_file(), 'manual workflow is missing')
        text = path.read_text()
        self.assertIn('on:\n  workflow_dispatch:\n', text)
        self.assertIn('permissions:\n  contents: read\n', text)
        self.assertIn("if: github.repository == 'Cheloco44/fantasy-family' && github.ref == 'refs/heads/main'", text)
        self.assertIn('timeout-minutes: 3', text)
        self.assertIn('actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', text)
        self.assertIn('persist-credentials: false', text)
        self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02', text)
        self.assertIn('name: nov-11-daily-scores\n', text)
        self.assertIn('path: artifacts/daily-lookup/nov-11.json\n', text)
        self.assertIn('retention-days: 1\n', text)
        self.assertIn('if-no-files-found: error\n', text)
        self.assertIn("python -m unittest discover -s scripts -p 'test_*.py'", text)
        self.assertIn('python scripts/lookup_daily.py --network --diagnostic', text)
        self.assertIn('set +x\n          ulimit -c 0\n', text)
        self.assertEqual(text.count('secrets.'), 2)
        self.assertIn('ESPN_S2: ${{ secrets.ESPN_S2 }}', text)
        self.assertIn('ESPN_SWID: ${{ secrets.ESPN_SWID }}', text)
        steps = text.split('      - ')
        secret_steps = [step for step in steps if 'secrets.' in step]
        self.assertEqual(len(secret_steps), 1)
        self.assertIn('python scripts/lookup_daily.py --network', secret_steps[0])
        self.assertLess(text.index('python -m unittest'), text.index('secrets.'))
        self.assertLess(text.index('python scripts/lookup_daily.py'), text.index('actions/upload-artifact'))
        self.assertEqual(text.count('uses:'), 2)
        for forbidden in ('schedule:', 'inputs:', 'pull_request', 'push:', 'write', 'deploy',
                          'git commit', 'pip install', 'always()', 'continue-on-error'):
            self.assertNotIn(forbidden, text)


class EvidenceTests(unittest.TestCase):
    def test_phoenix_date_dedup_and_next_day_exclusion(self):
        self.assertTrue(callable(getattr(lookup, 'period_evidence', None)))
        self.assertEqual(lookup.period_evidence(metadata()),
                         {'gameCount': 1, 'allGamesStatsOfficial': True})

    def test_rejects_missing_ambiguous_conflicting_and_spanning_evidence(self):
        variants = []
        empty = metadata(); empty['settings']['proTeams'] = []; variants.append(empty)
        for field, value in [('id', True), ('date', True), ('statsOfficial', 1),
                             ('scoringPeriodId', 45)]:
            data = metadata()
            for team in data['settings']['proTeams']:
                team['proGamesByScoringPeriod']['44'][0][field] = value
            variants.append(data)
        data = metadata(); data['settings']['proTeams'][1]['proGamesByScoringPeriod']['44'][0]['statsOfficial'] = False
        variants.append(data)
        data = metadata(); data['settings']['proTeams'][0]['proGamesByScoringPeriod']['45'][0]['scoringPeriodId'] = 44
        variants.append(data)
        data = metadata(); other = copy.deepcopy(data['settings']['proTeams'][0]['proGamesByScoringPeriod']['44'][0])
        other.update(id=103, scoringPeriodId=45)
        data['settings']['proTeams'][0]['proGamesByScoringPeriod']['45'].append(other); variants.append(data)
        for data in variants:
            with self.subTest(data=data), self.assertRaises(ValueError):
                lookup.period_evidence(data)

    def test_official_false_is_disclosed_not_called_final(self):
        data = metadata()
        for team in data['settings']['proTeams']:
            team['proGamesByScoringPeriod']['44'][0]['statsOfficial'] = False
        self.assertEqual(lookup.period_evidence(data), {'gameCount': 1, 'allGamesStatsOfficial': False})


if __name__ == '__main__':
    unittest.main()

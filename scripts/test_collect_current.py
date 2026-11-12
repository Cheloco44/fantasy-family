"""Synthetic-only current collector tests; no credentials or network needed."""
import contextlib
import copy
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('collect_current', Path(__file__).with_name('collect_current.py'))
collector = None
if Path(SPEC.origin).exists():
    collector = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(collector)
NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)


def fixture():
    return {
        'id': 1399646897, 'seasonId': 2027, 'scoringPeriodId': 42,
        'status': {'currentMatchupPeriod': 7},
        'settings': {'scoringSettings': {'scoringType': 'H2H_POINTS'}},
        'members': [{'displayName': 'PRIVATE_MEMBER_SENTINEL'}],
        'teams': [dict(id=i, name=f'ESPN Team {i}', playoffSeed=i,
                       record={'overall': {'wins': 2, 'losses': 1, 'ties': 0}},
                       owners=['PRIVATE_OWNER_SENTINEL'], logo='PRIVATE_LOGO_SENTINEL')
                  for i in (1, 2)],
        'schedule': [dict(id=10, matchupPeriodId=7,
                          home={'teamId': 1, 'totalPointsLive': 0, 'totalPoints': 99},
                          away={'teamId': 2, 'totalPoints': 12.5}),
                     dict(id=11, matchupPeriodId=42, home={'teamId': 1}, away={'teamId': 2})],
    }


class NormalizeTests(unittest.TestCase):
    def test_points_allowlist_and_matchup_not_daily_period(self):
        self.assertIsNotNone(collector, 'current collector implementation missing')
        result = collector.normalize(fixture(), now=NOW, expected_team_count=2)
        self.assertEqual(result, {
            'schemaVersion': 1, 'mode': 'live', 'source': 'ESPN',
            'dataKind': 'current-matchup-snapshot', 'fetchedAt': '2026-11-12T12:00:00Z',
            'leagueId': 1399646897, 'seasonId': 2027, 'scoringType': 'H2H_POINTS',
            'matchupPeriodId': 7, 'scoringPeriodId': 42,
            'teams': [dict(id=i, name=f'ESPN Team {i}', standing=i, wins=2, losses=1, ties=0) for i in (1, 2)],
            'matchups': [dict(id=10,
                home=dict(teamId=1, points=0, pointSource='totalPointsLive', categoryRecord=None, available=True),
                away=dict(teamId=2, points=12.5, pointSource='totalPoints', categoryRecord=None, available=True))],
        })
        self.assertNotIn('PRIVATE_', json.dumps(result))

    def test_category_records_never_use_points_and_unknown_zero_unavailable(self):
        data = fixture()
        data['settings']['scoringSettings']['scoringType'] = 'H2H_CATEGORY'
        home, away = data['schedule'][0]['home'], data['schedule'][0]['away']
        home['cumulativeScore'] = dict(wins=3, losses=2, ties=1, private='PRIVATE_STAT')
        away['cumulativeScore'] = dict(wins=0, losses=0, ties=0)
        result = collector.normalize(data, now=NOW, expected_team_count=2)['matchups'][0]
        self.assertEqual(result['home'], dict(teamId=1, points=None, pointSource=None,
            categoryRecord=dict(wins=3, losses=2, ties=1), available=True))
        self.assertEqual(result['away'], dict(teamId=2, points=None, pointSource=None,
            categoryRecord=None, available=False))
        away['cumulativeScore']['scoreByStat'] = {'0': {'score': 0, 'result': 'TIE'}}
        self.assertTrue(collector.normalize(data, now=NOW, expected_team_count=2)['matchups'][0]['away']['available'])
        home.pop('cumulativeScore')
        self.assertFalse(collector.normalize(data, now=NOW, expected_team_count=2)['matchups'][0]['home']['available'])

    def test_missing_points_is_not_zero_and_bye_is_explicit(self):
        data = fixture()
        data['schedule'][0]['home'] = {'teamId': 1}
        result = collector.normalize(data, now=NOW, expected_team_count=2)
        self.assertEqual(result['matchups'][0]['home'], dict(teamId=1, points=None,
            pointSource=None, categoryRecord=None, available=False))
        data['schedule'] = [dict(id=i, matchupPeriodId=7, home={'teamId': i}, away=None) for i in (1, 2)]
        self.assertTrue(all(m['away'] is None for m in collector.normalize(data, now=NOW, expected_team_count=2)['matchups']))

    def test_strict_validation_rejects_partial_unsafe_and_unknown_data(self):
        cases = []
        def change(path, value):
            data = fixture()
            target = data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            cases.append(data)
        for path, values in [
            (['id'], [True, 1, None]), (['seasonId'], [True, 2026]),
            (['status', 'currentMatchupPeriod'], [True, None, -1, '7']),
            (['scoringPeriodId'], [False, None, -1]),
            (['settings', 'scoringSettings', 'scoringType'], ['UNKNOWN', None, []]),
            (['teams', 0, 'id'], [True, 2, -1]),
            (['teams', 0, 'name'], ['', 'x' * 121, 'bad\nname', 'bad\x7fname', 'bad\x85name', 23]),
            (['teams', 0, 'record', 'overall'], [None, {}, {'wins': True, 'losses': 0, 'ties': 0}, {'wins': -1, 'losses': 0, 'ties': 0}]),
            (['schedule', 0, 'home', 'teamId'], [True, 999, 2]),
            (['schedule', 0, 'home', 'totalPointsLive'], [True, None, '1', float('nan'), float('inf')]),
            (['schedule', 0, 'matchupPeriodId'], [True, None, '7']),
            (['schedule', 0, 'id'], [True, None, -1]),
            (['schedule', 0, 'home'], [None, {}]),
        ]:
            for value in values:
                change(path, value)
        change(['teams'], fixture()['teams'][:1])
        change(['schedule'], [])
        change(['schedule'], [fixture()['schedule'][0]] * 2)
        missing = fixture()
        del missing['status']['currentMatchupPeriod']
        cases.append(missing)
        missing = fixture()
        del missing['schedule'][0]['away']
        cases.append(missing)
        for data in cases:
            with self.subTest(case=cases.index(data)):
                with self.assertRaises(ValueError):
                    collector.normalize(data, now=NOW, expected_team_count=2)
        with self.assertRaises(ValueError):
            collector.normalize(fixture(), now=NOW)  # production requires exactly eight
        with self.assertRaises(ValueError):
            collector.normalize(fixture(), now=NOW.replace(tzinfo=None), expected_team_count=2)

    def test_missing_away_byes_and_empty_nested_category_evidence(self):
        data = fixture()
        data['schedule'] = [dict(id=i, matchupPeriodId=7, home={'teamId': i}) for i in (1, 2)]
        result = collector.normalize(data, now=NOW, expected_team_count=2)
        self.assertTrue(all(m['away'] is None for m in result['matchups']))
        data = fixture()
        data['settings']['scoringSettings']['scoringType'] = 'H2H_CATEGORY'
        data['schedule'][0]['home']['cumulativeScore'] = dict(wins=0, losses=0, ties=0, scoreByStat={})
        result = collector.normalize(data, now=NOW, expected_team_count=2)
        self.assertFalse(result['matchups'][0]['home']['available'])

    def test_legacy_name_and_optional_positive_standing(self):
        for seed in (None, 0, -1, True, '1', 1.5):
            data = fixture()
            del data['teams'][0]['name']
            data['teams'][0].update(location='Legacy', nickname='Team', playoffSeed=seed)
            team = collector.normalize(data, now=NOW, expected_team_count=2)['teams'][0]
            self.assertEqual(team['name'], 'Legacy Team')
            self.assertIsNone(team['standing'])

    def test_invalid_category_record_fails_closed(self):
        for record in ({}, {'wins': True, 'losses': 0, 'ties': 0}, {'wins': 0, 'losses': -1, 'ties': 0}):
            data = fixture()
            data['settings']['scoringSettings']['scoringType'] = 'H2H_CATEGORY'
            data['schedule'][0]['home']['cumulativeScore'] = record
            with self.assertRaises(ValueError):
                collector.normalize(data, now=NOW, expected_team_count=2)


def full_fixture():
    data = fixture()
    data['teams'] = [dict(copy.deepcopy(data['teams'][0]), id=i, name=f'ESPN Team {i}') for i in range(1, 9)]
    data['schedule'] = [dict(id=i, matchupPeriodId=7, home={'teamId': i, 'totalPointsLive': 0},
                             away={'teamId': i + 1, 'totalPoints': 1}) for i in (1, 3, 5, 7)]
    return data


class CollectionTests(unittest.TestCase):
    def invoke(self, payload=None, *, env=None, status=200, network=True, prior=True):
        self.calls, self.handlers, self.read_sizes = [], [], []
        payload = json.dumps(full_fixture()).encode() if payload is None else payload
        owner = self
        class Response(io.BytesIO):
            def read(self, size=-1):
                owner.read_sizes.append(size)
                return super().read(size)
        class Opener:
            def open(self, request, timeout):
                owner.calls.append((request, timeout))
                if isinstance(payload, Exception):
                    raise payload
                response = Response(payload)
                response.status = status
                return response
        def factory(*handlers):
            self.handlers.extend(handlers)
            return Opener()
        env = {'ESPN_S2': 'COOKIE_S2_SENTINEL', 'ESPN_SWID': 'COOKIE_SWID_SENTINEL'} if env is None else env
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'nested' / 'current.json'
            if prior:
                output.parent.mkdir()
                output.write_text('LAST_GOOD_SENTINEL')
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                code = collector.main((['--network'] if network else []) + ['--output', str(output)],
                                      environ=env, opener_factory=factory, now=NOW)
            self.output_exists = output.exists()
            self.files_left = [p.name for p in output.parent.glob('*')]
            return code, stream.getvalue(), output.read_text() if output.exists() else None

    def test_opt_in_auth_fixed_get_cap_and_allowlist_output(self):
        self.assertTrue(hasattr(collector, 'main'), 'opt-in collection CLI missing')
        code, log, text = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(log, 'OK teams=8 matchups=4 scoringType=H2H_POINTS\n')
        self.assertEqual(len(self.calls), 1)
        request, timeout = self.calls[0]
        self.assertEqual(request.full_url, 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2027/segments/0/leagues/1399646897?view=mSettings&view=mTeam&view=mMatchupScore&view=mScoreboard&view=mStandings')
        self.assertEqual((request.get_method(), request.data, timeout), ('GET', None, 20))
        self.assertEqual(request.get_header('Cookie'), 'espn_s2=COOKIE_S2_SENTINEL; SWID=COOKIE_SWID_SENTINEL')
        self.assertEqual(self.read_sizes, [8 * 1024 * 1024 + 1])
        for handler in self.handlers:
            if hasattr(handler, 'redirect_request'):
                for status in (301, 302, 303, 307, 308):
                    self.assertIsNone(handler.redirect_request(None, None, status, '', {}, 'https://example.invalid'))
        self.assertEqual(json.loads(text)['fetchedAt'], '2026-11-12T12:00:00Z')
        self.assertNotIn('PRIVATE_', text)
        self.assertNotIn('COOKIE_', text + log)
        self.assertEqual(self.files_left, ['current.json'])

    def test_missing_or_unsafe_cookies_and_no_optin_never_open(self):
        for env in ({}, {'ESPN_S2': 'FAKE'}, {'ESPN_SWID': 'FAKE'},
                    *({'ESPN_S2': bad, 'ESPN_SWID': 'FAKE'} for bad in ('', 'a b', 'a;b', 'a,b', 'a"b', 'a\\b', 'a\nb', 'a☃'))):
            code, log, text = self.invoke(env=env)
            self.assertNotEqual(code, 0)
            self.assertEqual(self.calls, [])
            self.assertEqual(log, 'ERROR collection failed.\n')
            self.assertEqual(text, 'LAST_GOOD_SENTINEL')
        code, log, text = self.invoke(network=False, prior=False)
        self.assertEqual(code, 2)
        self.assertEqual(log, 'ERROR network disabled; pass --network.\n')
        self.assertIsNone(text)
        self.assertEqual(self.calls, [])

    def test_failures_preserve_existing_output_and_never_log_payload(self):
        from urllib.error import HTTPError, URLError
        sentinel = 'PRIVATE_RESPONSE_COOKIE_SENTINEL'
        cases = [HTTPError('https://example.invalid/' + sentinel, 401, sentinel, {}, None),
                 HTTPError('https://example.invalid', 302, sentinel, {}, None),
                 URLError(sentinel), TimeoutError(sentinel), RuntimeError(sentinel),
                 sentinel.encode(), b'{}', b'[]', b' ' * (8 * 1024 * 1024 + 1)]
        invalid = full_fixture()
        invalid['teams'][0]['record'] = {}
        cases.append(json.dumps(invalid).encode())
        for payload in cases:
            with self.subTest(kind=type(payload).__name__):
                code, log, text = self.invoke(payload)
                self.assertEqual(code, 1)
                self.assertEqual(log, 'ERROR collection failed.\n')
                self.assertEqual(text, 'LAST_GOOD_SENTINEL')
                self.assertLessEqual(len(self.calls), 1)
                self.assertEqual(self.files_left, ['current.json'])
        for status in (301, 302, 303, 307, 308, 401, 403, 500):
            code, log, text = self.invoke(status=status, prior=False)
            self.assertEqual(code, 1)
            self.assertEqual(log, 'ERROR collection failed.\n')
            self.assertIsNone(text)

    def test_cookie_collision_in_allowlisted_name_preserves_output(self):
        for cookie in ('COOKIE_S2_SENTINEL', 'COOKIE_SWID_SENTINEL'):
            data = full_fixture()
            data['teams'][0]['name'] = f'prefix {cookie} suffix'
            code, log, text = self.invoke(json.dumps(data).encode())
            self.assertEqual(code, 1)
            self.assertEqual(log, 'ERROR collection failed.\n')
            self.assertEqual(text, 'LAST_GOOD_SENTINEL')

    def test_cli_entrypoint_refuses_network_without_trace_or_argument_echo(self):
        import subprocess
        import sys
        for argv, message in [([], 'ERROR network disabled; pass --network.\n'),
                              (['--PRIVATE_ARGUMENT_SENTINEL'], 'ERROR invalid arguments.\n')]:
            result = subprocess.run([sys.executable, '-B', str(Path(SPEC.origin)), *argv],
                                    env={}, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr, message)

    def test_real_default_opener_keeps_tls_verification_and_refuses_redirects(self):
        import ssl
        from urllib.request import HTTPRedirectHandler, HTTPSHandler, build_opener
        opener = build_opener(collector.NoRedirect())
        redirects = [handler for handler in opener.handlers if isinstance(handler, HTTPRedirectHandler)]
        self.assertEqual(len(redirects), 1)
        self.assertIsInstance(redirects[0], collector.NoRedirect)
        https = [handler for handler in opener.handlers if isinstance(handler, HTTPSHandler)]
        self.assertEqual(len(https), 1)
        context = https[0]._context
        # None means urllib constructs its verified default context on connection.
        if context is not None:
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)

    def test_category_invalid_score_evidence_does_not_verify_zero(self):
        data = fixture()
        data['settings']['scoringSettings']['scoringType'] = 'H2H_CATEGORY'
        data['schedule'][0]['home']['cumulativeScore'] = dict(wins=0, losses=0, ties=0, scoreByStat='PRIVATE_NOT_STATS')
        with self.assertRaises(ValueError):
            collector.normalize(data, now=NOW, expected_team_count=2)

    def test_default_output_path_and_atomic_replace_failure(self):
        from unittest.mock import patch
        data = json.dumps(full_fixture()).encode()
        # A real replace failure exercises cleanup after writing normalized temp data.
        with patch.object(collector.os, 'replace', side_effect=OSError('PRIVATE_IO_SENTINEL')):
            code, log, text = self.invoke(data)
        self.assertEqual((code, log, text), (1, 'ERROR collection failed.\n', 'LAST_GOOD_SENTINEL'))
        self.assertEqual(self.files_left, ['current.json'])
        class Response(io.BytesIO):
            status = 200
        class Opener:
            def open(self, request, timeout):
                return Response(data)
        stream = io.StringIO()
        with patch.object(collector, 'atomic_write') as write, contextlib.redirect_stdout(stream):
            code = collector.main(['--network'], environ={'ESPN_S2': 'S2_SENTINEL', 'ESPN_SWID': 'SWID_SENTINEL'},
                                  opener_factory=lambda *handlers: Opener(), now=NOW)
        self.assertEqual(code, 0)
        self.assertEqual(write.call_args.args[0], 'artifacts/current-export/current.json')


class WorkflowTests(unittest.TestCase):
    def test_manual_refresh_security_contract(self):
        path = Path(__file__).resolve().parents[1] / '.github/workflows/refresh-current.yml'
        self.assertTrue(path.exists(), 'manual current workflow missing')
        text = path.read_text()
        for required in ('workflow_dispatch:', 'contents: read', 'persist-credentials: false',
                         "github.repository == 'Cheloco44/fantasy-family'", "github.ref == 'refs/heads/main'",
                         'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
                         "python3 -m unittest discover -s scripts -p 'test_*.py' -v",
                         'python3 scripts/collect_current.py --network', 'set +x', 'ulimit -c 0',
                         'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02',
                         'path: artifacts/current-export/current.json', 'name: current-league-data',
                         'retention-days: 1', 'if-no-files-found: error'):
            self.assertIn(required, text)
        for forbidden in ('schedule:', 'push:', 'pull_request:', 'pull_request_target:',
                          'contents: write', 'deploy-pages', 'git commit', 'git push', 'set -x',
                          'if: always()', 'if: failure()'):
            self.assertNotIn(forbidden, text)
        self.assertEqual(text.count('env:'), 1)
        self.assertEqual(text.count('${{ secrets.'), 2)
        steps = text.split('      - name:')[1:]
        self.assertEqual(len(steps), 4)
        self.assertNotIn('env:', steps[0] + steps[1] + steps[3])
        self.assertIn('${{ secrets.ESPN_S2 }}', steps[2])
        self.assertIn('${{ secrets.ESPN_SWID }}', steps[2])


if __name__ == '__main__':
    unittest.main()

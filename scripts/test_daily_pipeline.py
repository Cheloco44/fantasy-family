"""Offline daily pipeline contracts. Fixtures and credentials are synthetic only."""
import copy
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_lookup_daily import league, metadata, NOW
from test_collect_current import full_fixture
try:
    import daily_pipeline as pipeline
except ModuleNotFoundError:
    pipeline = None


class DailyTests(unittest.TestCase):
    def test_generic_prior_arizona_date_and_period(self):
        self.assertTrue(callable(getattr(pipeline, 'normalize_daily', None)), 'generic daily collector missing')
        self.assertEqual(pipeline.target_date(None, datetime(2026, 11, 12, 6, 59, tzinfo=timezone.utc)), '2026-11-10')
        self.assertEqual(pipeline.target_date(None, datetime(2026, 11, 12, 7, tzinfo=timezone.utc)), '2026-11-11')
        result = pipeline.normalize_daily(league(), metadata(), '2026-11-11', now=NOW)
        self.assertEqual(result['status'], 'verified-aggregate')
        self.assertEqual(result['matchups'][0], {'id': 1, 'homeId': 1, 'awayId': 2})
        self.assertEqual(result['teams'][0]['dailyPoints'], 10)
        data = league(); data['scoringPeriodId'] = 45
        for match in data['schedule']:
            for side in (match['home'], match['away']):
                side['pointsByScoringPeriod'] = {'45': -2.5}
        result = pipeline.normalize_daily(data, metadata(), '2026-11-12', now=datetime(2026, 11, 13, 12, tzinfo=timezone.utc))
        self.assertEqual(result['scoringPeriodId'], 45)
        self.assertEqual(result['teams'][0]['dailyPoints'], -2.5)

    def test_offday_requires_complete_nonempty_season_schedule(self):
        meta = metadata()
        base = copy.deepcopy(meta['settings']['proTeams'][0])
        meta['settings']['proTeams'] = [dict(copy.deepcopy(base), id=i) for i in range(1, 33)]
        # A date between evidenced scheduled dates, with no games of its own.
        for team in meta['settings']['proTeams']:
            team['proGamesByScoringPeriod']['45'][0]['date'] += 86400000
        result = pipeline.normalize_daily(league(), meta, '2026-11-12', now=datetime(2026, 11, 14, tzinfo=timezone.utc))
        self.assertEqual(result['status'], 'off-day')
        self.assertIsNone(result['scoringPeriodId'])
        self.assertEqual(result['matchups'], [])
        self.assertTrue(all(t['dailyPoints'] is None and not t['available'] for t in result['teams']))
        for teams in ([], meta['settings']['proTeams'][:2], [dict(id=i, proGamesByScoringPeriod={}) for i in range(1, 33)]):
            invalid = {'settings': {'proTeams': teams}}
            with self.subTest(count=len(teams)), self.assertRaises(ValueError):
                pipeline.normalize_daily(league(), invalid, '2026-11-12', now=datetime(2026, 11, 14, tzinfo=timezone.utc))

    def test_incomplete_missing_zero_negative_and_explicit_week_authority(self):
        data = league()
        data['settings']['scheduleSettings']['matchupPeriods'] = {'7': [44], '8': [44]}
        data['schedule'].append(dict(id=999, matchupPeriodId=20, home=dict(teamId=1, pointsByScoringPeriod=None), away=None))
        data['schedule'][0]['home']['pointsByScoringPeriod']['44'] = 0
        data['schedule'][0]['away']['pointsByScoringPeriod']['44'] = -2
        data['schedule'][1]['home']['pointsByScoringPeriod'] = None
        result = pipeline.normalize_daily(data, metadata(), '2026-11-11', now=NOW)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['matchupPeriodId'], 6)
        self.assertEqual([t['dailyPoints'] for t in result['teams'][:3]], [0, -2, None])
        meta = metadata()
        for team in meta['settings']['proTeams']:
            team['proGamesByScoringPeriod']['44'][0]['statsOfficial'] = False
        self.assertEqual(pipeline.normalize_daily(league(), meta, '2026-11-11', now=NOW)['status'], 'incomplete')

    def test_metadata_date_ambiguity_and_identity_fail_closed(self):
        for day in ('2026-11-12', '2026-11-11x', '2026-2-01', '../2026-11-11', '2025-11-11'):
            with self.subTest(day=day), self.assertRaises(ValueError):
                pipeline.target_date(day, NOW)
        variants = []
        data = metadata(); data['settings']['proTeams'] = []; variants.append(data)
        data = metadata(); data['settings']['proTeams'][1]['proGamesByScoringPeriod']['44'][0]['statsOfficial'] = False; variants.append(data)
        data = metadata(); game = copy.deepcopy(data['settings']['proTeams'][0]['proGamesByScoringPeriod']['44'][0]); game.update(id=222, scoringPeriodId=45)
        data['settings']['proTeams'][0]['proGamesByScoringPeriod']['45'].append(game); variants.append(data)
        for meta in variants:
            with self.assertRaises(ValueError):
                pipeline.normalize_daily(league(), meta, '2026-11-11', now=NOW)
        for field, value in [('id', 1), ('id', True), ('seasonId', 2026), ('scoringPeriodId', 45)]:
            data = league(); data[field] = value
            with self.assertRaises(ValueError):
                pipeline.normalize_daily(data, metadata(), '2026-11-11', now=NOW)
        for value in (True, None, '3', float('nan'), float('inf')):
            data = league(); data['schedule'][0]['home']['pointsByScoringPeriod']['44'] = value
            with self.assertRaises(ValueError):
                pipeline.normalize_daily(data, metadata(), '2026-11-11', now=NOW)


def bundle():
    return dict(daily=pipeline.normalize_daily(league(), metadata(), '2026-11-11', now=NOW),
                current=pipeline.current_collector.normalize(full_fixture(), now=NOW))


class ValidationTests(unittest.TestCase):
    def test_strict_revalidation_of_entire_bundle(self):
        self.assertTrue(callable(getattr(pipeline, 'validate_bundle', None)), 'import validator missing')
        self.assertEqual(pipeline.validate_bundle(bundle(), now=NOW), bundle())
        variants = []
        def change(path, value):
            data = bundle(); target = data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value; variants.append(data)
        for path, values in [
            (['daily', 'schemaVersion'], [True, 2]),
            (['daily', 'leagueId'], [3, True]),
            (['daily', 'seasonId'], [2026]),
            (['daily', 'source'], ['OTHER']),
            (['daily', 'timeZone'], ['UTC']),
            (['daily', 'date'], ['2026-11-12', '../../evil', '2026-11-11x']),
            (['daily', 'fetchedAt'], ['not-a-date', '2026-11-10T10:00:00Z', '2026-11-12T12:00:00']),
            (['daily', 'teams', 0, 'dailyPoints'], [True, float('nan'), float('inf'), '10', None]),
            (['daily', 'teams', 0, 'available'], [1, False]),
            (['daily', 'teams', 0, 'id'], [2, 99, True]),
            (['daily', 'teams', 0, 'pointSource'], ['totalPointsLive', None]),
            (['daily', 'periodEvidence', 'allGamesStatsOfficial'], [1, False]),
            (['daily', 'matchups', 0, 'awayId'], [1, 99]),
            (['daily', 'matchups', 0, 'id'], [True, -1]),
            (['current', 'mode'], ['demo']),
            (['current', 'teams', 0, 'wins'], [-1, True]),
            (['current', 'teams', 0, 'standing'], [0, True]),
            (['current', 'matchups', 0, 'home', 'points'], [float('nan'), None, True]),
            (['current', 'matchups', 0, 'home', 'available'], [1, False]),
            (['current', 'matchups', 0, 'home', 'pointSource'], ["pointsByScoringPeriod['44']", None]),
            (['current', 'matchups', 0, 'home', 'categoryRecord'], [dict(wins=1, losses=0, ties=0)]),
        ]:
            for value in values:
                change(path, value)
        for root, key in [('daily', 'raw'), ('current', 'members')]:
            data = bundle(); data[root][key] = 'PRIVATE'; variants.append(data)
        data = bundle(); data['daily']['teams'].pop(); variants.append(data)
        data = bundle(); data['daily']['matchups'].pop(); variants.append(data)
        data = bundle(); data['current']['matchups'].append(copy.deepcopy(data['current']['matchups'][0])); variants.append(data)
        data = bundle(); data['current']['teams'][0]['private'] = 'secret'; variants.append(data)
        for index, data in enumerate(variants):
            with self.subTest(case=index), self.assertRaises(ValueError):
                pipeline.validate_bundle(data, now=NOW)

    def test_json_reader_refuses_duplicate_keys_oversize_and_symlinks(self):
        self.assertTrue(callable(getattr(pipeline, 'read_json', None)), 'bounded strict JSON reader missing')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            for body in ('{"id":1,"id":2}', '{"points":NaN}', 'x' * (pipeline.MAX_BYTES + 1)):
                path.write_text(body)
                with self.assertRaises(ValueError):
                    pipeline.read_json(path)
            path.write_text('{}')
            link = Path(directory) / 'link.json'; link.symlink_to(path)
            with self.assertRaises(ValueError):
                pipeline.read_json(link)


class CollectionTests(unittest.TestCase):
    cookies = dict(ESPN_S2='S2_SYNTHETIC_TOKEN', ESPN_SWID='SWID_SYNTHETIC_TOKEN')

    def invoke(self, directory, responses, *, args=None, environ=None):
        calls, handlers, bounds = [], [], []
        class Response(io.BytesIO):
            status = 200
            def read(inner, size=-1):
                bounds.append(size)
                return super().read(size)
        class Opener:
            def open(inner, request, timeout):
                calls.append((request, timeout))
                value = responses[len(calls) - 1]
                if isinstance(value, Exception):
                    raise value
                response = Response(value if isinstance(value, bytes) else json.dumps(value).encode())
                return response
        def factory(handler):
            handlers.append(handler)
            return Opener()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = pipeline.main(['collect', '--output-dir', str(directory)] + (['--network'] if args is None else args),
                                   environ=self.cookies if environ is None else environ,
                                   opener_factory=factory, now=NOW)
        return result, out.getvalue(), err.getvalue(), calls, handlers, bounds

    def test_collect_exact_sanitized_artifacts_metadata_first_and_no_source_writes(self):
        self.assertTrue(callable(getattr(pipeline, 'main', None)), 'daily CLI missing')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'batch'
            env = dict(self.cookies, GITHUB_REPOSITORY='Cheloco44/fantasy-family', GITHUB_RUN_ID='12345')
            code, out, err, calls, handlers, bounds = self.invoke(output, [metadata(), league(), full_fixture()], environ=env)
            self.assertEqual((code, err), (0, ''))
            self.assertEqual({p.name for p in output.iterdir()}, {'daily.json', 'current.json'})
            daily, current = pipeline.read_json(output / 'daily.json'), pipeline.read_json(output / 'current.json')
            self.assertEqual(daily['sourceRunUrl'], 'https://github.com/Cheloco44/fantasy-family/actions/runs/12345')
            self.assertEqual(daily['teams'][0]['dailyPoints'], 10)
            self.assertEqual(current['teams'][0]['wins'], 2)
            self.assertEqual(calls[0][0].full_url, pipeline.BASE + '?view=proTeamSchedules_wl')
            self.assertIsNone(calls[0][0].get_header('Cookie'))
            self.assertEqual(calls[1][0].full_url, pipeline.LEAGUE_BASE + '?view=mSettings&view=mTeam&view=mMatchupScore&view=mScoreboard&scoringPeriodId=44')
            self.assertEqual(calls[2][0].full_url, pipeline.current_collector.URL)
            for request, timeout in calls:
                self.assertEqual((request.get_method(), timeout), ('GET', 20))
            self.assertEqual(bounds, [pipeline.MAX_BYTES + 1] * 3)
            self.assertTrue(all(isinstance(h, pipeline.NoRedirect) for h in handlers))
            joined = (output / 'daily.json').read_text() + (output / 'current.json').read_text() + out + err
            for private in ('members', 'owners', 'PRIVATE_', 'private-owner', 'private@example', *self.cookies.values()):
                self.assertNotIn(private, joined)

    def test_no_optin_invalid_credentials_transport_and_collision_preserve_batch(self):
        self.assertTrue(callable(getattr(pipeline, 'main', None)), 'daily CLI missing')
        for env in ({}, {'ESPN_S2': 'one'}, *(dict(self.cookies, ESPN_S2=v) for v in ('', 'bad;value', 'a b', 'a\\b', 'bad\nvalue', 1))):
            with tempfile.TemporaryDirectory() as directory:
                result = self.invoke(directory, [], environ=env)
                self.assertEqual(result[0], 1); self.assertEqual(result[3], [])
        with tempfile.TemporaryDirectory() as directory:
            result = self.invoke(directory, [], args=[])
            self.assertEqual(result[0], 2); self.assertEqual(result[3], [])
        collision = league(); collision['teams'][0]['name'] = self.cookies['ESPN_S2']
        from urllib.error import HTTPError, URLError
        failures = [[HTTPError('https://evil.invalid', 302, 'PRIVATE', {}, None)],
                    [URLError('PRIVATE')], [TimeoutError('PRIVATE')], [b'raw PRIVATE'],
                    [b'x' * (pipeline.MAX_BYTES + 1)], [{'settings': {'proTeams': []}}],
                    [metadata(), collision, full_fixture()]]
        for responses in failures:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                for name in ('daily.json', 'current.json'):
                    (output / name).write_text('LAST_GOOD')
                code, out, err, *_ = self.invoke(output, responses)
                self.assertEqual((code, out), (1, ''))
                self.assertNotIn('PRIVATE', err)
                self.assertTrue(all((output / name).read_text() == 'LAST_GOOD' for name in ('daily.json', 'current.json')))
                self.assertEqual(len(list(output.iterdir())), 2)

    def test_verified_tls_and_all_redirects_rejected(self):
        import ssl
        from urllib.request import HTTPSHandler, HTTPRedirectHandler
        opener = pipeline.build_opener(pipeline.NoRedirect())
        redirects = [h for h in opener.handlers if isinstance(h, HTTPRedirectHandler)]
        self.assertEqual(len(redirects), 1)
        for status in (301, 302, 303, 307, 308):
            self.assertIsNone(redirects[0].redirect_request(None, None, status, '', {}, 'https://evil.invalid'))
        https = next(h for h in opener.handlers if isinstance(h, HTTPSHandler))
        if https._context is not None:
            self.assertEqual(https._context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(https._context.check_hostname)


def editorial():
    return dict(schemaVersion=1, timezone='America/Phoenix', publishTarget='07:00', closeMargin=5, smokedMargin=20,
                cast={str(i): dict(slug=f'person-{i}', displayName=f'Alias {i}') for i in range(1, 9)},
                approvedMemes=[dict(id='dated', image='memes/approved.jpg', caption='Approved daily cartoon',
                    date='2026-11-11', managers=['person-1', 'person-2'], tags=['daily-round'],
                    approvalStatus='approved', contextType='dated')])


def setup_content(root):
    root = Path(root)
    (root / 'src/data').mkdir(parents=True)
    (root / 'public/memes').mkdir(parents=True)
    (root / 'public/memes/approved.jpg').write_bytes(b'synthetic-image-not-for-publication')
    (root / 'public/avatars').mkdir()
    managers = []
    for i in range(1, 9):
        image = f'avatars/person-{i}.webp'
        (root / 'public' / image).write_bytes(b'synthetic-image-not-for-publication')
        managers.append(dict(slug=f'person-{i}', approved=True, image=image))
    (root / 'src/data/clubhouse.json').write_text(json.dumps(dict(managers=managers)))
    (root / 'src/data/editorial.json').write_text(json.dumps(editorial()))
    return root


class EditorialTests(unittest.TestCase):
    def report(self, bundles, *, catalog=None):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory)
            return pipeline.build_recaps(bundles, editorial() if catalog is None else catalog,
                                         pipeline.read_json(root / 'src/data/clubhouse.json'), root=root, now=NOW)

    def test_contract_exact_fields_thresholds_and_aliases(self):
        self.assertTrue(callable(getattr(pipeline, 'build_recaps', None)), 'editorial builder missing')
        data = bundle()
        values = [10, 5, 0, 20, 3, 3, -1, 6]
        for team, points in zip(data['daily']['teams'], values):
            team['dailyPoints'] = points
        result = self.report([data])
        self.assertEqual(set(result), {'schemaVersion', 'timezone', 'publishTarget', 'editions'})
        edition = result['editions'][0]
        self.assertEqual(set(edition), set('date sourceFetchedAt sourceRunUrl scoringPeriodId matchupPeriodId status headline dek coverageNote weeklyContextAt matchups'.split()))
        self.assertEqual([m['classification'] for m in edition['matchups']], ['close', 'smoked', 'tie', 'standard'])
        self.assertEqual([m['margin'] for m in edition['matchups']], [5, 20, 0, 7])
        match = edition['matchups'][0]
        self.assertEqual(set(match), set('id homeId awayId homeAlias awayAlias homePoints awayPoints margin classification title story trendNotes weeklySummary meme'.split()))
        self.assertEqual(set(match['meme']), set('id image caption sourceDate isArchive approvalStatus'.split()))
        self.assertIn('DAILY ROUND', match['story'])
        self.assertNotIn('Canonical', json.dumps(result))
        self.assertNotIn('ESPN Team', json.dumps(result))
        self.assertEqual(match['homeAlias'], 'Alias 1')

    def test_approved_dated_only_for_its_date_and_avatar_fallback(self):
        self.assertTrue(callable(getattr(pipeline, 'build_recaps', None)), 'editorial builder missing')
        result = self.report([bundle()])['editions'][0]['matchups']
        self.assertEqual(result[0]['meme']['id'], 'dated')
        self.assertEqual(result[1]['meme']['id'], 'avatar-person-3')
        catalog = editorial(); catalog['approvedMemes'][0]['date'] = '2026-11-10'
        result = self.report([bundle()], catalog=catalog)['editions'][0]['matchups'][0]
        self.assertEqual(result['meme']['id'], 'avatar-person-1')
        catalog['approvedMemes'][0].update(contextType='evergreen', date=None)
        result = self.report([bundle()], catalog=catalog)['editions'][0]['matchups'][0]
        self.assertEqual(result['meme']['id'], 'dated')
        self.assertIsNone(result['meme']['sourceDate'])
        catalog['approvedMemes'][0]['approvalStatus'] = 'draft'
        with self.assertRaises(ValueError):
            self.report([bundle()], catalog=catalog)

    def test_catalog_thresholds_are_real_reviewable_controls(self):
        catalog = editorial(); catalog.update(closeMargin=7, smokedMargin=25)
        data = bundle(); data['daily']['teams'][0]['dailyPoints'] = 16
        edition = self.report([data], catalog=catalog)['editions'][0]
        self.assertEqual(edition['matchups'][0]['classification'], 'close')
        data['daily']['teams'][0]['dailyPoints'] = 30
        self.assertEqual(self.report([data], catalog=catalog)['editions'][0]['matchups'][0]['classification'], 'standard')
        catalog['closeMargin'] = True
        with self.assertRaises(ValueError):
            self.report([data], catalog=catalog)

    def test_personalized_headlines_and_character_chirps_keep_fiction_in_the_editorial(self):
        self.assertTrue(callable(getattr(pipeline, 'character_chirp', None)))
        self.assertIn('AI', pipeline.character_chirp('kyle', False))
        self.assertIn('complain', pipeline.character_chirp('ben', True))
        self.assertIn('throne', pipeline.character_chirp('marcelo', False))
        self.assertEqual(pipeline.character_chirp('unknown', True), '')
        data = bundle(); data['daily']['teams'][0]['dailyPoints'] = 61
        edition = self.report([data])['editions'][0]
        self.assertIn('Alias 1', edition['headline'])
        self.assertNotIn('Deterministic rules', edition['dek'])

    def test_corrected_daily_points_do_not_reuse_old_baked_score_art(self):
        catalog = editorial()
        catalog['approvedMemes'][0]['scoreContext'] = {'1': 10, '2': 10}
        data = bundle()
        self.assertEqual(self.report([data], catalog=catalog)['editions'][0]['matchups'][0]['meme']['id'], 'dated')
        data['daily']['teams'][0]['dailyPoints'] = 11
        self.assertEqual(self.report([data], catalog=catalog)['editions'][0]['matchups'][0]['meme']['id'], 'avatar-person-1')
        catalog['approvedMemes'][0]['scoreContext']['1'] = float('nan')
        with self.assertRaises(ValueError):
            self.report([data], catalog=catalog)

    def test_invalid_asset_paths_missing_and_unapproved_avatars_fail_closed(self):
        self.assertTrue(callable(getattr(pipeline, 'build_recaps', None)), 'editorial builder missing')
        for image in ('../private.jpg', 'https://evil.invalid/image.jpg', '/etc/passwd', 'memes/../private.jpg', 'memes/draft.svg', 'memes/missing.jpg'):
            catalog = editorial(); catalog['approvedMemes'][0]['image'] = image
            with self.subTest(image=image), self.assertRaises(ValueError):
                self.report([bundle()], catalog=catalog)
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory)
            profiles = pipeline.read_json(root / 'src/data/clubhouse.json')
            profiles['managers'][2]['approved'] = False
            with self.assertRaises(ValueError):
                pipeline.build_recaps([bundle()], editorial(), profiles, root=root, now=NOW)

    def test_weekly_context_is_separate_same_period_pair_and_fetch_time(self):
        self.assertTrue(callable(getattr(pipeline, 'build_recaps', None)), 'editorial builder missing')
        data = bundle()
        data['current']['matchupPeriodId'] = 6
        data['current']['fetchedAt'] = '2026-11-12T11:00:00Z'
        edition = self.report([data])['editions'][0]
        self.assertEqual(edition['sourceFetchedAt'], '2026-11-12T12:00:00Z')
        self.assertEqual(edition['weeklyContextAt'], '2026-11-12T11:00:00Z')
        self.assertIn('snapshot', edition['matchups'][0]['weeklySummary'])
        self.assertIn('not end-of-day', edition['matchups'][0]['weeklySummary'])
        data['current']['matchupPeriodId'] = 7
        edition = self.report([data])['editions'][0]
        self.assertIsNone(edition['weeklyContextAt'])
        self.assertTrue(all(m['weeklySummary'] is None for m in edition['matchups']))
        data['current']['matchupPeriodId'] = 6
        a, b = data['current']['matchups'][:2]
        a['away'], b['away'] = b['away'], a['away']
        self.assertIsNone(self.report([data])['editions'][0]['matchups'][0]['weeklySummary'])

    def test_rolling_records_are_real_daily_rounds_not_weekly_or_missing_streaks(self):
        self.assertTrue(callable(getattr(pipeline, 'build_recaps', None)), 'editorial builder missing')
        history = []
        for day in ('2026-11-04', '2026-11-06', '2026-11-08', '2026-11-11'):
            data = bundle(); data['daily']['date'] = day
            data['daily']['teams'][0]['dailyPoints'] = -1
            history.append(data)
        latest = self.report(history)['editions'][0]['matchups'][0]
        notes = ' '.join(latest['trendNotes'])
        self.assertIn('0-3-0', notes)
        self.assertIn('3/7', notes)
        self.assertIn('2026-11-05', notes)
        self.assertIn('bye week', notes)
        self.assertIn('not official ESPN', notes)
        self.assertNotIn('streak', latest['story'])
        history[1]['daily']['teams'][0].update(available=False, dailyPoints=None, pointSource=None)
        history[1]['daily']['status'] = 'incomplete'
        notes = ' '.join(self.report(history)['editions'][0]['matchups'][0]['trendNotes'])
        self.assertIn('0-2-0', notes)
        self.assertNotIn('bye week', notes)


class ImportTests(unittest.TestCase):
    def invoke(self, root, args):
        out, err = io.StringIO(), io.StringIO()
        def no_network(*_):
            self.fail('offline command attempted network')
        with redirect_stdout(out), redirect_stderr(err):
            code = pipeline.main(args, root=root, now=NOW, environ={}, opener_factory=no_network)
        return code, out.getvalue(), err.getvalue()

    def artifact(self, root, value=None):
        path = root / 'artifacts/batch'; path.mkdir(parents=True, exist_ok=True)
        value = bundle() if value is None else value
        for key in ('daily', 'current'):
            (path / (key + '.json')).write_text(json.dumps(value[key]))
        return path

    def test_import_rebuild_idempotency_and_exact_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory); artifact = self.artifact(root)
            self.assertTrue(callable(getattr(pipeline, 'import_batch', None)), 'offline importer missing')
            code, _, err = self.invoke(root, ['import', '--input-dir', str(artifact)])
            self.assertEqual((code, err), (0, ''))
            data = root / 'src/data'
            self.assertEqual(pipeline.read_json(data / 'daily/2026-11-11.json'), bundle())
            self.assertEqual(pipeline.read_json(data / 'current.json'), bundle()['current'])
            paths = [data / 'daily/2026-11-11.json', data / 'current.json', data / 'recaps.json']
            before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
            self.assertEqual(self.invoke(root, ['import', '--input-dir', str(artifact)])[0], 0)
            self.assertEqual(self.invoke(root, ['rebuild'])[0], 0)
            self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths])
            self.assertEqual({p.name for p in (data / 'daily').iterdir()}, {'2026-11-11.json'})

    def test_invalid_input_and_editorial_preserve_all_last_good_outputs(self):
        self.assertTrue(callable(getattr(pipeline, 'import_batch', None)), 'offline importer missing')
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory); artifact = self.artifact(root)
            self.assertEqual(self.invoke(root, ['import', '--input-dir', str(artifact)])[0], 0)
            paths = [root / 'src/data/daily/2026-11-11.json', root / 'src/data/current.json', root / 'src/data/recaps.json']
            before = [p.read_bytes() for p in paths]
            data = bundle(); data['daily']['teams'][0]['dailyPoints'] = 99
            self.artifact(root, data)
            catalog = editorial(); catalog['approvedMemes'][0]['image'] = '../secret.jpg'
            (root / 'src/data/editorial.json').write_text(json.dumps(catalog))
            self.assertEqual(self.invoke(root, ['import', '--input-dir', str(artifact)])[0], 1)
            self.assertEqual(before, [p.read_bytes() for p in paths])
            (root / 'src/data/editorial.json').write_text(json.dumps(editorial()))
            for extra in ('raw.json', 'members.json'):
                (artifact / extra).write_text('PRIVATE')
                self.assertEqual(self.invoke(root, ['import', '--input-dir', str(artifact)])[0], 1)
                (artifact / extra).unlink()
            data['current']['members'] = []
            self.artifact(root, data)
            self.assertEqual(self.invoke(root, ['import', '--input-dir', str(artifact)])[0], 1)
            self.assertEqual(before, [p.read_bytes() for p in paths])

    def test_correction_recomputes_history_without_regressing_current_snapshot(self):
        self.assertTrue(callable(getattr(pipeline, 'import_batch', None)), 'offline importer missing')
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory)
            for day in ('2026-11-08', '2026-11-10', '2026-11-11'):
                value = bundle(); value['daily']['date'] = day; value['daily']['teams'][0]['dailyPoints'] = -1
                artifact = self.artifact(root, value)
                self.assertEqual(self.invoke(root, ['import', '--input-dir', str(artifact)])[0], 0)
            path = root / 'src/data/recaps.json'
            notes = pipeline.read_json(path)['editions'][0]['matchups'][0]['trendNotes']
            self.assertIn('bye week', ' '.join(notes))
            good_current = (root / 'src/data/current.json').read_bytes()
            value = bundle(); value['daily']['date'] = '2026-11-08'; value['daily']['teams'][0]['dailyPoints'] = 15
            value['current']['fetchedAt'] = '2026-11-11T12:00:00Z'
            self.artifact(root, value)
            self.assertEqual(self.invoke(root, ['import', '--input-dir', str(artifact)])[0], 0)
            notes = pipeline.read_json(path)['editions'][0]['matchups'][0]['trendNotes']
            self.assertIn('1-2-0', ' '.join(notes)); self.assertNotIn('bye week', ' '.join(notes))
            self.assertEqual((root / 'src/data/current.json').read_bytes(), good_current)
            self.assertEqual(len(pipeline.read_json(path)['editions']), 3)

    def test_partial_replace_failure_rolls_back_all_outputs(self):
        self.assertTrue(callable(getattr(pipeline, 'import_batch', None)), 'offline importer missing')
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory); artifact = self.artifact(root)
            self.assertEqual(self.invoke(root, ['import', '--input-dir', str(artifact)])[0], 0)
            paths = [root / 'src/data/daily/2026-11-11.json', root / 'src/data/current.json', root / 'src/data/recaps.json']
            before = [p.read_bytes() for p in paths]
            value = bundle(); value['daily']['teams'][0]['dailyPoints'] = 99
            value['current']['fetchedAt'] = '2026-11-12T12:01:00Z'
            self.artifact(root, value)
            real_replace = pipeline.os.replace; calls = []
            def replace(source, destination):
                calls.append(str(destination))
                if len(calls) == 2:
                    raise OSError('PRIVATE_WRITE_ERROR')
                return real_replace(source, destination)
            with patch.object(pipeline.os, 'replace', side_effect=replace):
                code, out, err = self.invoke(root, ['import', '--input-dir', str(artifact)])
            self.assertEqual(code, 1); self.assertNotIn('PRIVATE', out + err)
            self.assertEqual(before, [p.read_bytes() for p in paths])
            self.assertEqual(list(root.rglob('*.tmp')), [])

    def test_archive_filename_and_symlink_validation_preserves_last_good(self):
        self.assertTrue(callable(getattr(pipeline, 'import_batch', None)), 'offline importer missing')
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory); artifact = self.artifact(root)
            self.assertEqual(self.invoke(root, ['import', '--input-dir', str(artifact)])[0], 0)
            report = root / 'src/data/recaps.json'; before = report.read_bytes()
            archive = root / 'src/data/daily'
            (archive / '2026-11-10.json').write_text(json.dumps(bundle()))
            self.assertEqual(self.invoke(root, ['rebuild'])[0], 1)
            self.assertEqual(report.read_bytes(), before)
            (archive / '2026-11-10.json').unlink()
            (artifact / 'daily.json').unlink(); (artifact / 'daily.json').symlink_to(archive / '2026-11-11.json')
            self.assertEqual(self.invoke(root, ['import', '--input-dir', str(artifact)])[0], 1)
            self.assertEqual(report.read_bytes(), before)


class RegressionTests(unittest.TestCase):
    def test_decimal_margin_does_not_export_binary_float_noise(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory); data = bundle()
            data['daily']['teams'][0]['dailyPoints'] = 40.55
            data['daily']['teams'][1]['dailyPoints'] = 26.75
            report = pipeline.build_recaps([data], editorial(), pipeline.read_json(root / 'src/data/clubhouse.json'), root=root, now=NOW)
            self.assertEqual(report['editions'][0]['matchups'][0]['margin'], 13.8)

    def test_offline_cli_does_not_read_credential_environment(self):
        class ForbiddenEnvironment(dict):
            def get(self, *_):
                raise AssertionError('offline path read credentials')
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory)
            archive = root / 'src/data/daily'; archive.mkdir()
            (archive / '2026-11-11.json').write_text(json.dumps(bundle()))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(pipeline.main(['rebuild'], root=root, now=NOW, environ=ForbiddenEnvironment()), 0)

    def test_cast_accepts_optional_owner_team_name_not_arbitrary_extras(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory); catalog = editorial()
            catalog['cast']['1']['teamName'] = "America's FUPA"
            profiles = pipeline.read_json(root / 'src/data/clubhouse.json')
            report = pipeline.build_recaps([bundle()], catalog, profiles, root=root, now=NOW)
            self.assertEqual(report['editions'][0]['matchups'][0]['homeAlias'], 'Alias 1')
            catalog['cast']['1']['ownerEmail'] = 'PRIVATE'
            with self.assertRaises(ValueError):
                pipeline.build_recaps([bundle()], catalog, profiles, root=root, now=NOW)

    def test_thresholds_are_exact_not_rounded_into_close_or_tie(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory); data = bundle()
            for team, points in zip(data['daily']['teams'], [5.0000000001, 0, 0.0000000001, 0, 19.9999999999, 0, 0, 0]):
                team['dailyPoints'] = points
            result = pipeline.build_recaps([data], editorial(), pipeline.read_json(root / 'src/data/clubhouse.json'), root=root, now=NOW)
            self.assertEqual([m['classification'] for m in result['editions'][0]['matchups']], ['standard', 'close', 'standard', 'tie'])

    def test_source_run_url_only_fixed_repository_numeric_run(self):
        for url in ('https://evil.invalid/actions/runs/123', 'https://github.com/Other/repo/actions/runs/123',
                    'https://github.com/Cheloco44/fantasy-family/actions/runs/123?token=secret',
                    'https://github.com/Cheloco44/fantasy-family/actions/runs/01', 123):
            data = bundle(); data['daily']['sourceRunUrl'] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                pipeline.validate_bundle(data, now=NOW)

    def test_incomplete_does_not_roast_or_award_daily_round_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory); data = bundle()
            data['daily']['periodEvidence']['allGamesStatsOfficial'] = False
            data['daily']['status'] = 'incomplete'
            data['daily']['teams'][0]['dailyPoints'] = 100
            result = pipeline.build_recaps([data], editorial(), pipeline.read_json(root / 'src/data/clubhouse.json'), root=root, now=NOW)
            match = result['editions'][0]['matchups'][0]
            self.assertEqual(match['classification'], 'unavailable')
            self.assertIn('0-0-0', match['trendNotes'][0])
            self.assertNotIn('smokes', match['story'])

    def test_old_snapshot_import_preserves_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_content(directory)
            previous = bundle()['current']; previous['fetchedAt'] = '2026-11-12T12:01:00Z'
            current_path = root / 'src/data/current.json'; current_path.write_text(json.dumps(previous, indent=2))
            before = current_path.read_bytes()
            artifact = root / 'artifacts/batch'; artifact.mkdir(parents=True)
            data = bundle()
            for key in ('daily', 'current'):
                (artifact / (key + '.json')).write_text(json.dumps(data[key]))
            pipeline.import_batch(artifact, root=root, now=NOW)
            self.assertEqual(before, current_path.read_bytes())


if __name__ == '__main__':
    unittest.main()

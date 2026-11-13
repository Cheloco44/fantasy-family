"""Private review packets: offline transports, real validation and local rendering."""
import copy
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

try:
    import review_packet as packet
except ModuleNotFoundError:
    packet = None

import daily_pipeline as pipeline
from test_daily_pipeline import bundle, editorial

NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
SHA = 'a' * 40
URL = 'https://github.com/Cheloco44/fantasy-family/actions/runs/123'


def run_info(**changes):
    value = dict(databaseId=123, headSha=SHA, headBranch='main', event='schedule',
                 status='completed', conclusion='success', createdAt='2026-11-12T11:30:00Z', url=URL)
    value.update(changes)
    return value


class SourceTests(unittest.TestCase):
    def test_arizona_date_and_newest_successful_today_run(self):
        self.assertTrue(callable(getattr(packet, 'select_run', None)), 'run selection missing')
        self.assertEqual(packet.dates(datetime(2026, 11, 12, 6, 59, tzinfo=timezone.utc)), ('2026-11-11', '2026-11-10'))
        self.assertEqual(packet.dates(NOW), ('2026-11-12', '2026-11-11'))
        runs = [run_info(createdAt='2026-11-12T06:59:00Z'),
                run_info(conclusion='failure'), run_info(headBranch='feature'),
                run_info(event='push'), run_info(),
                run_info(databaseId=124, event='workflow_dispatch', createdAt='2026-11-12T11:45:00Z', url=URL[:-3]+'124')]
        self.assertEqual(packet.select_run(runs, NOW)['databaseId'], 124)
        for bad in [[], [run_info(headSha='../private')], [run_info(url='https://evil.invalid')],
                    [run_info(createdAt='2026-11-13T12:00:00Z')]]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                packet.select_run(bad, NOW)


class ArtifactTests(unittest.TestCase):
    def test_exact_run_download_strict_bundle_and_transport_bounds(self):
        self.assertTrue(callable(getattr(packet, 'prepare_input', None)), 'artifact transport missing')
        calls = []
        def transport(args, *, cwd, limit):
            calls.append(args)
            if args[:3] == ['gh', 'run', 'list']:
                return json.dumps([run_info()]).encode()
            self.assertIn('--name', args)
            self.assertEqual(args[3], '123')
            self.assertEqual(args[args.index('--name')+1], 'daily-review-input')
            target = Path(args[args.index('--dir')+1])
            for key, value in bundle().items():
                (target / (key+'.json')).write_text(json.dumps(value))
            return b''
        with tempfile.TemporaryDirectory() as directory:
            value, run = packet.prepare_input(Path(directory), NOW, transport)
            expected = bundle(); expected['daily']['sourceRunUrl'] = URL
            self.assertEqual(value, expected)
            self.assertEqual(run['headSha'], SHA)
        self.assertEqual(len(calls), 3)  # schedule and dispatch, then exact run
        with patch.object(packet.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as mocked:
            self.assertEqual(packet.command(['gh', '--version'], cwd=Path('.'), limit=12), b'')
            self.assertEqual(mocked.call_args.kwargs['timeout'], 20)
            self.assertEqual(mocked.call_args.kwargs['stderr'], subprocess.DEVNULL)

    def test_artifact_refuses_extra_symlink_oversize_duplicate_stale_and_schema(self):
        self.assertTrue(callable(getattr(packet, 'read_artifact', None)), 'artifact validation missing')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for case in ('extra', 'symlink', 'large', 'duplicate', 'stale', 'schema'):
                for p in root.iterdir():
                    p.unlink()
                data = bundle()
                if case == 'stale':
                    data['daily']['date'] = '2026-11-10'
                if case == 'schema':
                    data['current']['owners'] = ['PRIVATE']
                for key in data:
                    (root / (key+'.json')).write_text(json.dumps(data[key]))
                if case == 'extra':
                    (root / 'raw.json').write_text('PRIVATE')
                if case == 'symlink':
                    (root / 'daily.json').unlink(); (root / 'daily.json').symlink_to(root / 'current.json')
                if case == 'large':
                    (root / 'daily.json').write_bytes(b' '*(pipeline.MAX_BYTES+1))
                if case == 'duplicate':
                    (root / 'daily.json').write_text('{"daily":1,"daily":2}')
                with self.subTest(case=case), self.assertRaises(ValueError):
                    packet.read_artifact(root, NOW)


class SnapshotTests(unittest.TestCase):
    def test_snapshot_uses_exact_git_objects_real_history_and_approved_assets(self):
        self.assertTrue(callable(getattr(packet, 'snapshot', None)), 'immutable snapshot missing')
        catalog = editorial()
        profiles = dict(managers=[dict(slug=f'person-{i}', approved=True, image=f'avatars/person-{i}.webp') for i in range(1,9)])
        history = bundle(); history['daily']['date'] = '2026-11-10'
        objects = {'src/data/editorial.json': json.dumps(catalog).encode(),
                   'src/data/clubhouse.json': json.dumps(profiles).encode(),
                   'src/data/daily/2026-11-10.json': json.dumps(history).encode()}
        for image in [m['image'] for m in profiles['managers']] + [catalog['approvedMemes'][0]['image']]:
            objects['public/'+image] = b'approved fixture bytes'
        calls = []
        def transport(args, *, cwd, limit):
            calls.append(args)
            if args[1] in ('fetch', 'merge-base'):
                return b''
            if args[1] == 'ls-tree':
                path = args[-1]
                paths = [p for p in objects if p.startswith(path)]
                return ''.join(f'100644 blob {SHA} {len(objects[p])}\t{p}\n' for p in paths).encode()
            self.assertEqual(args[1], 'show')
            self.assertTrue(args[2].startswith(SHA+':'))
            return objects[args[2].split(':',1)[1]]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'snapshot'
            report, actual, avatars = packet.snapshot(Path(directory), SHA, bundle(), root, NOW, transport)
            self.assertEqual(actual, catalog)
            self.assertEqual([e['date'] for e in report['editions']], ['2026-11-11','2026-11-10'])
            self.assertEqual(len(avatars), 8)
            self.assertEqual({str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}, set(objects)-{'src/data/daily/2026-11-10.json'})
        self.assertEqual(calls[0], ['git','fetch','origin','main'])
        self.assertIn(['git','merge-base','--is-ancestor',SHA,'FETCH_HEAD'], calls)
        for path in ('../secret', 'private/portraits.png', 'public/avatars/../secret.png', 'src/data/current.json'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                packet.object_file(Path('.'), SHA, path, transport)
        with self.assertRaises(ValueError):
            packet.object_file(Path('.'), 'main', 'src/data/editorial.json', transport)


class RenderTests(unittest.TestCase):
    def test_four_private_real_composites_pending_manifest_and_idempotency(self):
        self.assertTrue(callable(getattr(packet, 'write_packet', None)), 'private renderer missing')
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow unavailable; image rendering explicitly skipped')
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            root = repo / 'snapshot'
            (root / 'public/avatars').mkdir(parents=True)
            catalog = editorial(); catalog['approvedMemes'] = []
            profiles = dict(managers=[])
            for i in range(1,9):
                image = f'avatars/person-{i}.webp'
                pic = Image.new('RGB', (80,100), (i*25,10,100))
                exif = Image.Exif(); exif[270] = 'PRIVATE EXIF'
                pic.save(root / 'public' / image, exif=exif)
                profiles['managers'].append(dict(slug=f'person-{i}', approved=True, image=image))
            report = pipeline.build_recaps([bundle()], catalog, profiles, root=root, now=NOW)
            avatars = pipeline.validate_catalog(catalog, profiles, root)
            from PIL import ImageDraw
            rendered_text = []
            real_text = ImageDraw.ImageDraw.text
            def record_text(canvas, xy, text, *args, **kwargs):
                rendered_text.append(text)
                return real_text(canvas, xy, text, *args, **kwargs)
            with patch.object(ImageDraw.ImageDraw, 'text', new=record_text):
                result = packet.write_packet(repo, bundle(), run_info(), root, report, catalog, avatars, NOW)
            self.assertIn('Unpublished DRAFT', result)
            self.assertIn('mention Neo', result)
            self.assertIn('Redlands Possum Busters', rendered_text)
            self.assertFalse(any('DRAFT' in str(text) or 'approval needed' in str(text) for text in rendered_text),
                             'Keep approval administration in message/manifest, not final-ready approved image bytes')
            output = repo / 'private/review-packets/2026-11-11'
            manifest = pipeline.read_json(output / 'manifest.json')
            self.assertEqual(manifest['approvalStatus'], 'pending')
            self.assertEqual(manifest['sourceSha'], SHA)
            self.assertEqual(manifest['sourceRunId'], 123)
            self.assertEqual(manifest['coverageDate'], '2026-11-11')
            self.assertEqual(manifest['reviewDate'], '2026-11-12')
            self.assertEqual(manifest['scoreContext'], {str(t['id']):t['dailyPoints'] for t in bundle()['daily']['teams']})
            self.assertEqual(len(manifest['files']), 4)
            self.assertEqual([item['caption'] for item in manifest['files']],
                             [match['title'] for match in report['editions'][0]['matchups']],
                             'draft images inherit individual editorial punchlines, not a generic repeated score sentence')
            self.assertEqual(len(list(output.glob('*.png'))), 4)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            before = {}
            for item in manifest['files']:
                path = output / item['file']
                self.assertEqual(item['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(item['approvalStatus'], 'pending')
                with Image.open(path) as image:
                    self.assertEqual(image.size, (1280,1280))
                    self.assertFalse(image.getexif())
                    self.assertFalse(image.info)
                    self.assertGreater(len(image.getcolors(2000000)), 10)
                before[path.name] = path.read_bytes()
            self.assertIn('MEDIA:'+str(output), result)
            self.assertIn('Alias 1', result)
            self.assertIn('06:00',result)
            self.assertIn('06:30',result)
            self.assertIn('06:40',result)
            self.assertIn('07:00',result)
            packet.write_packet(repo, bundle(), run_info(), root, report, catalog, avatars, NOW)
            self.assertEqual(before, {p.name:p.read_bytes() for p in output.glob('*.png')})
            self.assertFalse((repo / 'public').exists())
            # Provisional and late are visible, never an unqualified winning caption.
            data = bundle(); data['daily']['periodEvidence']['allGamesStatsOfficial'] = False
            data['daily']['status'] = 'incomplete'; data['daily']['teams'][0].update(available=False, dailyPoints=None, pointSource=None)
            report = pipeline.build_recaps([data], catalog, profiles, root=root, now=NOW)
            late = datetime(2026,11,12,13,1,tzinfo=timezone.utc)
            message = packet.write_packet(repo, data, run_info(), root, report, catalog, avatars, late)
            self.assertIn('LATE / SETUP', message)
            manifest = pipeline.read_json(output / 'manifest.json')
            self.assertTrue(manifest['late'])
            self.assertTrue(all('PROVISIONAL' in item['caption'] and 'wins' not in item['caption'] for item in manifest['files']))
            # Off-day creates no invented score art; old same-date images are removed.
            data['daily'].update(status='off-day', scoringPeriodId=None, matchupPeriodId=None,
                                 periodEvidence=dict(gameCount=0, allGamesStatsOfficial=False), matchups=[])
            for team in data['daily']['teams']:
                team.update(dailyPoints=None, available=False, pointSource=None)
            report = pipeline.build_recaps([data], catalog, profiles, root=root, now=NOW)
            message = packet.write_packet(repo, data, run_info(), root, report, catalog, avatars, NOW)
            self.assertNotIn('MEDIA:',message)
            self.assertEqual(list(output.glob('*.png')), [])
            self.assertEqual(pipeline.read_json(output/'manifest.json')['files'], [])

    def test_output_symlinks_and_oversize_images_refused(self):
        self.assertTrue(callable(getattr(packet, 'output_dir', None)), 'safe private output missing')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'public').mkdir(); (root/'private').symlink_to(root/'public', target_is_directory=True)
            with self.assertRaises(ValueError):
                packet.output_dir(root, '2026-11-11')
            with self.assertRaises(ValueError):
                packet.output_dir(root, '../public')
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow unavailable; image bounds explicitly skipped')
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/'large.png'
            Image.new('RGB', (4097,1)).save(image)
            with self.assertRaises(ValueError):
                packet.portrait(image)


class NotificationTests(unittest.TestCase):
    def fixture(self, repo):
        output = repo/'private/review-packets/2026-11-11'; output.mkdir(parents=True)
        image = b'private candidate bytes'
        candidate = dict(id='review-2026-11-11-1', file='review-2026-11-11-1.png',
                         sha256=hashlib.sha256(image).hexdigest(), approvalStatus='pending',
                         caption='Daily tie', scoreContext={'1':10,'2':10}, managers=['person-1','person-2'])
        (output/candidate['file']).write_bytes(image)
        manifest = dict(schemaVersion=1, coverageDate='2026-11-11', reviewDate='2026-11-12',
                        sourceRunId=123, sourceRunUrl=URL, sourceSha=SHA,
                        scoreContext={str(i):10 for i in range(1,9)}, dataStatus='verified-aggregate',
                        files=[candidate], approvalStatus='pending', deadlines=packet.DEADLINES, late=False)
        (output/'manifest.json').write_text(json.dumps(manifest))
        return manifest, candidate, image

    def test_reminder_cutoff_only_remote_catalog_id_and_actual_image_hash_count(self):
        self.assertTrue(callable(getattr(packet, 'notify', None)), 'catalog-backed notification missing')
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            manifest, candidate, image = self.fixture(repo)
            catalog = editorial(); item = catalog['approvedMemes'][0]
            item.update(id=candidate['id'], scoreContext=candidate['scoreContext'])
            calls = []
            published = image
            def transport(args, *, cwd, limit):
                calls.append(args)
                if args[1] == 'fetch': return b''
                if args[1] == 'rev-parse': return (SHA+'\n').encode()
                path = args[-1].split(':')[-1]
                body = json.dumps(catalog).encode() if path == 'src/data/editorial.json' else published
                if args[1] == 'ls-tree':
                    return f'100644 blob {SHA} {len(body)}\t{path}\n'.encode()
                return body
            message = packet.notify(repo, 'reminder', NOW, transport)
            self.assertIn('In approved publishing catalog: '+candidate['id'],message)
            self.assertIn('06:00',message)
            self.assertEqual(calls[0], ['git','fetch','origin','main'])
            item['managers'] = list(reversed(candidate['managers']))
            self.assertIn('In approved publishing catalog: '+candidate['id'],
                          packet.notify(repo, 'cutoff', NOW, transport))
            item['managers'] = candidate['managers']
            published = b'different approved bytes'
            message = packet.notify(repo, 'cutoff', NOW, transport)
            self.assertIn('No new packet artwork is in the publishing catalog',message)
            self.assertIn('06:40',message)
            self.assertIn('approved art/portraits',message)
            for key, bad in [('approvalStatus','pending'), ('date','2026-11-10'), ('id','old-approved')]:
                previous = item[key]; item[key] = bad; published = image
                self.assertIn('No new packet artwork',packet.notify(repo,'reminder',NOW,transport))
                item[key] = previous
            self.assertEqual(pipeline.read_json(repo/'private/review-packets/2026-11-11/manifest.json'),manifest)
            self.assertTrue(all(a[1] in ('fetch','rev-parse','show','ls-tree') for a in calls))

    def test_missing_corrupt_stale_and_tampered_packet_never_imply_approval(self):
        self.assertTrue(callable(getattr(packet, 'main', None)), 'no-agent CLI missing')
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            def forbidden(*args, **kwargs): self.fail('invalid packet attempted network')
            for mode in ('reminder','cutoff'):
                out = io.StringIO()
                with redirect_stdout(out):
                    code = packet.main([mode,'--repo-dir',str(repo)], now=NOW, transport=forbidden)
                self.assertEqual(code,1)
                self.assertIn('approval',out.getvalue())
                self.assertNotIn('MEDIA:',out.getvalue())
            manifest, candidate, _ = self.fixture(repo)
            path = repo/'private/review-packets/2026-11-11/manifest.json'
            for key, bad in [('reviewDate','2026-11-11'),('coverageDate','2026-11-10'),
                             ('sourceSha','main'),('approvalStatus','approved'),('files',[dict(candidate,file='../secret.png')])]:
                invalid = copy.deepcopy(manifest); invalid[key] = bad
                path.write_text(json.dumps(invalid))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    packet.notify(repo,'reminder',NOW,forbidden)
            path.write_text(json.dumps(manifest))
            (path.parent/candidate['file']).write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                packet.notify(repo,'cutoff',NOW,forbidden)

    def test_remote_catalog_invalid_fields_cannot_be_called_publishing_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            manifest, candidate, image = self.fixture(repo)
            catalog = editorial()
            catalog['approvedMemes'][0].update(id=candidate['id'],scoreContext=candidate['scoreContext'],
                                               owners=['PRIVATE'])
            def transport(args, *, cwd, limit):
                if args[1] == 'fetch': return b''
                if args[1] == 'rev-parse': return (SHA+'\n').encode()
                path = args[-1].split(':')[-1]
                body = json.dumps(catalog).encode() if path == 'src/data/editorial.json' else image
                if args[1] == 'ls-tree': return f'100644 blob {SHA} {len(body)}\t{path}\n'.encode()
                return body
            with self.assertRaises(ValueError):
                packet.notify(repo,'reminder',NOW,transport)

    def test_failure_notice_is_stdout_sanitized_actionable_and_late(self):
        self.assertTrue(callable(getattr(packet, 'main', None)), 'no-agent CLI missing')
        def failed(*args, **kwargs):
            raise subprocess.CalledProcessError(1, 'gh', output=b'SECRET', stderr=b'PRIVATE COOKIE')
        with tempfile.TemporaryDirectory() as directory:
            out = io.StringIO()
            with redirect_stdout(out):
                code = packet.main(['--repo-dir',directory], now=datetime(2026,11,12,14,tzinfo=timezone.utc), transport=failed)
            message = out.getvalue()
            self.assertEqual(code,1)
            self.assertIn('LATE / SETUP',message)
            self.assertIn('prepare-review.yml',message)
            self.assertIn('approved art/portraits',message)
            self.assertIn('06:40',message)
            for hidden in ('SECRET','PRIVATE','COOKIE','Traceback','MEDIA:'):
                self.assertNotIn(hidden,message)
            self.assertFalse((Path(directory)/'private').exists())


class MemePromptTests(unittest.TestCase):
    """ChatGPT-style meme prompts delivered with the reviewed 05:00 packet."""

    def edition(self, matchups):
        return dict(date='2026-11-11', status='verified-aggregate', headline='The receipts are in',
                    dek='', coverageNote='', matchups=matchups)

    def matchup(self, mid, home, away, hp, ap, classification, margin):
        return dict(id=mid, homeId=home, awayId=away,
                    homeAlias=f"Person {home}", awayAlias=f"Person {away}",
                    homePoints=hp, awayPoints=ap, margin=margin,
                    classification=classification, title='some editorial title', story='some story')

    def decided(self):
        # Four decided matchups; margins descending: 90(smoked), 20(smoked), 8(standard), 5(close).
        return [
            self.matchup(1, 1, 2, 100, 10, 'smoked', 90),
            self.matchup(2, 3, 4, 60, 40, 'smoked', 20),
            self.matchup(3, 5, 6, 30, 22, 'standard', 8),
            self.matchup(4, 7, 8, 15, 10, 'close', 5),
        ]

    def test_no_decided_matchups_return_single_evergreen_fallback(self):
        self.assertTrue(callable(getattr(packet, 'meme_prompts', None)), 'meme prompt builder missing')
        for classification in ('tie', 'unavailable'):
            with self.subTest(classification=classification):
                edition = self.edition([self.matchup(1, 1, 2, 10, 10, classification, 0)])
                prompts = packet.meme_prompts(edition, editorial())
                self.assertEqual(len(prompts), 1)
        # An empty edition (off-day / incomplete) also falls back.
        self.assertEqual(len(packet.meme_prompts(self.edition([]), editorial())), 1)

    def test_evergreen_fallback_names_cast_display_names_and_styles_scene(self):
        prompt = packet.meme_prompts(self.edition([]), editorial())[0]
        self.assertIn('Alias 6', prompt)          # exact catalog displayNames, not slugs
        self.assertIn('Alias 7', prompt)
        self.assertIn('one full scene', prompt.lower())
        self.assertIn('not a collage', prompt.lower())
        self.assertIn('caption', prompt.lower())
        self.assertNotIn('person-6', prompt)      # slugs never leak into prompt text

    def test_decided_matchups_take_largest_margins_first_up_to_three(self):
        prompts = packet.meme_prompts(self.edition(self.decided()), editorial())
        self.assertEqual(len(prompts), 3)          # cap: 90, 20, 8 (8-margin standard before 5 close)
        joined = '\n'.join(prompts)
        self.assertLess(joined.index('Alias 1'), joined.index('Alias 3'))
        self.assertLess(joined.index('Alias 3'), joined.index('Alias 5'))

    def test_cap_at_three_ignores_extra_decided(self):
        extra = [self.matchup(5, 1, 2, 70, 5, 'smoked', 65),
                 self.matchup(6, 3, 4, 50, 10, 'smoked', 40)]
        edition = self.edition(self.decided() + extra)
        self.assertEqual(len(packet.meme_prompts(edition, editorial())), 3)

    def test_deterministic_across_matchup_order(self):
        forward = self.decided()
        reversed_edition = self.edition(list(reversed(forward)))
        self.assertEqual(packet.meme_prompts(self.edition(forward), editorial()),
                         packet.meme_prompts(reversed_edition, editorial()))

    def test_prompts_name_real_pairing_no_invented_numbers_no_embedded_caption(self):
        for match, prompt in zip(self.decided(), packet.meme_prompts(self.edition(self.decided()), editorial())):
            cast = editorial()['cast']
            home, away = cast[str(match['homeId'])]['displayName'], cast[str(match['awayId'])]['displayName']
            with self.subTest(mid=match['id']):
                self.assertTrue(any(n in prompt for n in (home, away)), f'acts in prompt: {prompt}')
                residue = prompt.replace(home, '').replace(away, '')   # digits only from fixture displayNames
                self.assertFalse(any(c.isdigit() for c in residue), 'no invented numbers in prompt')
                self.assertNotIn(match['title'], prompt)    # caption/title not embedded in the image prompt
                self.assertIn('not a collage', prompt.lower())
                self.assertIn('bottom', prompt.lower())     # caption space left on the rendered scene

    def test_classification_variants_share_style_but_differ(self):
        smoked = self.matchup(1, 1, 2, 100, 10, 'smoked', 90)
        close = self.matchup(2, 3, 4, 15, 10, 'close', 5)
        standard = self.matchup(3, 5, 6, 30, 22, 'standard', 8)
        prompts = {m['id']: p for m, p in zip(
            [smoked, close, standard],
            packet.meme_prompts(self.edition([smoked, close, standard]), editorial()))}
        self.assertNotEqual(prompts[1], prompts[2])
        self.assertNotEqual(prompts[2], prompts[3])
        for p in prompts.values():
            self.assertIn('one full scene', p.lower())
            self.assertIn('minimal', p.lower())

    def test_same_classification_prompts_have_distinct_character_scenes(self):
        catalog = json.loads((Path(__file__).resolve().parents[1] / 'src/data/editorial.json').read_text())
        matches = [self.matchup(1, 5, 2, 76, 32.15, 'smoked', 43.85),
                   self.matchup(2, 6, 7, 99.9, 60.75, 'smoked', 39.15)]
        prompts = packet.meme_prompts(self.edition(matches), catalog)
        normalized = []
        for prompt in prompts:
            for person in catalog['cast'].values():
                prompt = prompt.replace(person['displayName'], 'CHARACTER')
            normalized.append(prompt)
        self.assertNotEqual(normalized[0], normalized[1], 'changing names is not a different scene')
        self.assertIn('Neanderthal', prompts[0])
        self.assertIn('blue Dodgers cap', prompts[1])
        self.assertIn('chrome', prompts[1])
        self.assertIn('reference', prompts[0].lower())
        self.assertIn('reference', prompts[1].lower())

    def test_unverified_edition_cannot_promote_stale_decided_classifications(self):
        for status in ('incomplete', 'off-day'):
            edition = self.edition(self.decided())
            edition['status'] = status
            prompts = packet.meme_prompts(edition, editorial())
            self.assertEqual(len(prompts), 1)
            self.assertIn('evergreen', prompts[0].lower())
            self.assertIn('no game result implied', prompts[0])

    def test_away_team_win_is_picked_and_named_without_error(self):
        # Regression: the pickup ternary must bind both winner and loser. A nested
        # tuple as loser_id previously caused KeyError on any away-team decided win.
        away_wins = self.matchup(1, 1, 2, 10, 99, 'smoked', 89)
        passed = self.matchup(2, 1, 2, 99, 10, 'smoked', 89)
        prompts = packet.meme_prompts(self.edition([away_wins]), editorial())
        self.assertEqual(len(prompts), 1)
        cast = editorial()['cast']
        self.assertIn(cast['2']['displayName'], prompts[0])  # away Alias 2 = winner
        self.assertIn(cast['1']['displayName'], prompts[0])  # home Alias 1 = loser
        # Sanity: symmetric home-wins still works identically.
        home_prompts = packet.meme_prompts(self.edition([passed]), editorial())
        self.assertIn(cast['1']['displayName'], home_prompts[0])
        self.assertIn(cast['2']['displayName'], home_prompts[0])

    def test_write_packet_includes_delimited_prompt_block_when_decided(self):
        self.assertTrue(callable(getattr(packet, 'write_packet', None)))
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow unavailable; image rendering explicitly skipped')
        # Make team points decided so build_recaps produces classified (decided) matchups.
        data = bundle()
        for team, pts in zip(data['daily']['teams'], [100, 10, 60, 40, 30, 22, 15, 10]):
            team['dailyPoints'] = pts
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory); root = repo / 'snapshot'
            (root / 'public/avatars').mkdir(parents=True)
            catalog = editorial(); catalog['approvedMemes'] = []
            profiles = dict(managers=[])
            for i in range(1, 9):
                image = f'avatars/person-{i}.webp'
                Image.new('RGB', (80, 100), (i * 25, 10, 100)).save(root / 'public' / image)
                profiles['managers'].append(dict(slug=f'person-{i}', approved=True, image=image))
            report = pipeline.build_recaps([data], catalog, profiles, root=root, now=NOW)
            avatars = pipeline.validate_catalog(catalog, profiles, root)
            block = '/'.join('CHATGPT MEME PROMPTS'.lower().split())
            message = packet.write_packet(repo, data, run_info(), root, report, catalog, avatars, NOW)
            self.assertIn('CHATGPT MEME PROMPTS', message)
            self.assertGreaterEqual(message.count('<---'), 2)   # clearly delimited block
            self.assertIn('Alias 1', message)                    # exact cast displayNames in block

    def test_write_packet_uses_evergreen_fallback_when_nothing_decided(self):
        # bundle() is an all-tie verified edition; no decided matchups -> evergreen fallback prompt.
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow unavailable; image rendering explicitly skipped')
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory); root = repo / 'snapshot'
            (root / 'public/avatars').mkdir(parents=True)
            catalog = editorial(); catalog['approvedMemes'] = []
            profiles = dict(managers=[])
            for i in range(1, 9):
                image = f'avatars/person-{i}.webp'
                Image.new('RGB', (80, 100), (i * 25, 10, 100)).save(root / 'public' / image)
                profiles['managers'].append(dict(slug=f'person-{i}', approved=True, image=image))
            report = pipeline.build_recaps([bundle()], catalog, profiles, root=root, now=NOW)
            avatars = pipeline.validate_catalog(catalog, profiles, root)
            message = packet.write_packet(repo, bundle(), run_info(), root, report, catalog, avatars, NOW)
            self.assertIn('CHATGPT MEME PROMPTS', message)
            self.assertIn('evergreen', message.lower())


class EndToEndTests(unittest.TestCase):
    def test_no_agent_packet_cli_with_git_and_github_only_at_transport_seam(self):
        self.assertTrue(callable(getattr(packet, 'main', None)), 'packet CLI missing')
        data = bundle()
        data['daily'].update(status='off-day', scoringPeriodId=None, matchupPeriodId=None,
                             periodEvidence=dict(gameCount=0, allGamesStatsOfficial=False), matchups=[])
        for team in data['daily']['teams']:
            team.update(dailyPoints=None, available=False, pointSource=None)
        catalog = editorial(); catalog['approvedMemes'] = []
        profiles = dict(managers=[dict(slug=f'person-{i}', approved=True, image=f'avatars/person-{i}.webp') for i in range(1,9)])
        objects = {'src/data/editorial.json':json.dumps(catalog).encode(),
                   'src/data/clubhouse.json':json.dumps(profiles).encode()}
        objects.update({'public/'+p['image']:b'approved fixture' for p in profiles['managers']})
        calls = []
        def transport(args, *, cwd, limit):
            calls.append(args)
            if args[:3] == ['gh','run','list']: return json.dumps([run_info()]).encode()
            if args[:3] == ['gh','run','download']:
                target = Path(args[args.index('--dir')+1])
                for key in data:
                    (target/(key+'.json')).write_text(json.dumps(data[key]))
                return b''
            if args[1] in ('fetch','merge-base'): return b''
            if args[1] == 'ls-tree':
                paths = [p for p in objects if p.startswith(args[-1])]
                return ''.join(f'100644 blob {SHA} {len(objects[p])}\t{p}\n' for p in paths).encode()
            return objects[args[-1].split(':',1)[1]]
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo/'src/data').mkdir(parents=True)
            # Unreviewed working-tree config must not be consumed or overwritten.
            source = repo/'src/data/editorial.json'; source.write_text('UNREVIEWED PRIVATE')
            out = io.StringIO()
            with redirect_stdout(out):
                code = packet.main(['packet','--repo-dir',directory],now=NOW,transport=transport)
            self.assertEqual(code,0)
            self.assertIn('Off-day: text review only',out.getvalue())
            self.assertNotIn('MEDIA:',out.getvalue())
            self.assertNotIn('UNREVIEWED',out.getvalue())
            self.assertEqual(source.read_text(),'UNREVIEWED PRIVATE')
            manifest = packet.load_packet(repo,NOW)
            self.assertEqual(manifest['files'],[])
            self.assertEqual(manifest['sourceRunUrl'],URL)
        self.assertTrue(all(a[0] in ('git','gh') for a in calls))

    def test_transport_timeout_failure_and_bounded_output_never_return_raw_text(self):
        self.assertTrue(callable(getattr(packet, 'command', None)), 'bounded transport missing')
        for error in (subprocess.TimeoutExpired('gh',20,output=b'PRIVATE'), OSError('PRIVATE')):
            with patch.object(packet.subprocess,'run',side_effect=error), self.assertRaises(type(error)):
                packet.command(['gh','run','list'],cwd=Path('.'),limit=8)
        def huge(args, **kwargs):
            kwargs['stdout'].write(b'PRIVATE TOO LARGE')
            return subprocess.CompletedProcess(args,0)
        with patch.object(packet.subprocess,'run',side_effect=huge), self.assertRaises(ValueError):
            packet.command(['gh','run','list'],cwd=Path('.'),limit=8)


if __name__ == '__main__':
    unittest.main()

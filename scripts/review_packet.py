"""Private, no-agent early review packets. Never approves or publishes artwork."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re
import os
import hashlib
import textwrap
from pathlib import Path
import subprocess
import tempfile

import daily_pipeline as pipeline

REPO = 'Cheloco44/fantasy-family'
DEFAULT_REPO = '/home/marcelo/projects/possum-busters'
AZ = ZoneInfo('America/Phoenix')
require = pipeline.require


def dates(now):
    require(now.tzinfo is not None)
    today = now.astimezone(AZ).date()
    return today.isoformat(), (today - timedelta(days=1)).isoformat()


def select_run(runs, now):
    require(type(runs) is list and len(runs) <= 100)
    candidates = []
    for run in runs:
        if not isinstance(run, dict) or (run.get('headBranch'), run.get('status'), run.get('conclusion')) != ('main', 'completed', 'success'):
            continue
        if run.get('event') not in ('schedule', 'workflow_dispatch'):
            continue
        created = pipeline.instant(run['createdAt'])
        if created.astimezone(AZ).date().isoformat() != dates(now)[0] or created > now:
            continue
        require(type(run['databaseId']) is int and 0 < run['databaseId'] < 10**20)
        require(type(run['headSha']) is str and re.fullmatch('[0-9a-f]{40}', run['headSha']))
        require(run['url'] == f'https://github.com/{REPO}/actions/runs/{run["databaseId"]}')
        candidates.append(run)
    require(bool(candidates))
    return max(candidates, key=lambda r: (pipeline.instant(r['createdAt']), r['databaseId']))


def command(args, *, cwd, limit=pipeline.MAX_BYTES):
    """Explicit transport seam; no shell, logs, credentials or unbounded waits."""
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(args, cwd=cwd, stdout=output, stderr=subprocess.DEVNULL,
                                timeout=20, check=False, stdin=subprocess.DEVNULL)
        require(result.returncode == 0)
        require(output.tell() <= limit)
        output.seek(0)
        body = output.read(limit + 1)
        require(len(body) <= limit)
        return body


def read_artifact(directory, now):
    directory = pipeline.safe_path(directory)
    require(directory.is_dir() and {p.name for p in directory.iterdir()} == {'daily.json', 'current.json'})
    require(all(pipeline.safe_path(p).is_file() for p in directory.iterdir()))
    value = pipeline.validate_bundle({key: pipeline.read_json(directory / (key + '.json'))
                                      for key in ('daily', 'current')}, now=now)
    require(value['daily']['date'] == dates(now)[1])
    return value


def prepare_input(repo, now, transport=command):
    runs = []
    for event in ('schedule', 'workflow_dispatch'):
        body = transport(['gh', 'run', 'list', '--repo', REPO, '--workflow', 'prepare-review.yml',
                          '--branch', 'main', '--event', event, '--limit', '50', '--json',
                          'databaseId,headSha,headBranch,event,status,conclusion,createdAt,url'],
                         cwd=repo, limit=pipeline.MAX_BYTES)
        found = pipeline.parse_json(body)
        require(type(found) is list and len(found) <= 50)
        runs.extend(found)
    run = select_run(runs, now)
    with tempfile.TemporaryDirectory(prefix='review-input-') as temporary:
        transport(['gh', 'run', 'download', str(run['databaseId']), '--repo', REPO,
                   '--name', 'daily-review-input', '--dir', temporary], cwd=repo, limit=1024)
        value = read_artifact(Path(temporary), now)
    require(value['daily']['sourceRunUrl'] in (None, run['url']))
    value['daily']['sourceRunUrl'] = run['url']
    return value, run


def object_file(repo, sha, path, transport=command):
    require(type(sha) is str and re.fullmatch('[0-9a-f]{40}', sha))
    require(type(path) is str and (path in ('src/data/editorial.json', 'src/data/clubhouse.json')
            or re.fullmatch(r'src/data/daily/202[67]-[0-9]{2}-[0-9]{2}\.json', path)
            or re.fullmatch(r'public/(avatars|memes)/[A-Za-z0-9_/-]+\.(webp|jpg|jpeg|png|gif)', path)))
    require(all(p not in ('', '.', '..') for p in path.split('/')))
    limit = 8 * 1024 * 1024 if path.startswith('public/') else pipeline.MAX_BYTES
    entry = transport(['git', 'ls-tree', '-l', sha, '--', path], cwd=repo, limit=2048).decode()
    metadata, name = entry.rstrip('\n').split('\t')
    mode, kind, oid, size = metadata.split()
    require(name == path and mode in ('100644', '100755') and kind == 'blob'
            and re.fullmatch('[0-9a-f]{40}', oid) and 0 < int(size) <= limit)
    body = transport(['git', 'show', sha + ':' + path], cwd=repo, limit=limit)
    require(len(body) == int(size))
    return body


def snapshot(repo, sha, value, root, now, transport=command):
    require(type(sha) is str and re.fullmatch('[0-9a-f]{40}', sha))
    transport(['git', 'fetch', 'origin', 'main'], cwd=repo, limit=1024)
    transport(['git', 'merge-base', '--is-ancestor', sha, 'FETCH_HEAD'], cwd=repo, limit=1024)
    root = pipeline.safe_path(root)
    configs = {}
    for name in ('editorial', 'clubhouse'):
        path = 'src/data/' + name + '.json'
        body = object_file(repo, sha, path, transport)
        configs[name] = pipeline.parse_json(body)
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    catalog, profiles = configs['editorial'], configs['clubhouse']
    # Never copy reference folders or unapproved portraits into the report root.
    assets = []
    for person in profiles['managers']:
        if person.get('approved') is True:
            require(re.fullmatch(r'avatars/[A-Za-z0-9_-]+\.(webp|jpg|jpeg|png)', person['image']))
            assets.append(person['image'])
    assets.extend(m['image'] for m in catalog['approvedMemes'] if m.get('approvalStatus') == 'approved')
    require(len(assets) <= 108)
    for image in sorted(set(assets)):
        path = 'public/' + image
        body = object_file(repo, sha, path, transport)
        target = pipeline.safe_path(root / path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    avatars = pipeline.validate_catalog(catalog, profiles, root)
    entries = transport(['git', 'ls-tree', '-r', '-l', sha, '--', 'src/data/daily/'],
                        cwd=repo, limit=128 * 1024).decode().splitlines()
    require(len(entries) <= 366)
    history = {}
    day = value['daily']['date']
    start = (datetime.fromisoformat(day).date() - timedelta(days=6)).isoformat()
    for entry in entries:
        metadata, path = entry.split('\t')
        require(re.fullmatch(r'src/data/daily/202[67]-[0-9]{2}-[0-9]{2}\.json', path))
        archived_day = path.rsplit('/', 1)[1][:-5]
        if start <= archived_day < day:
            archived = pipeline.validate_bundle(pipeline.parse_json(object_file(repo, sha, path, transport)), now=now)
            require(archived['daily']['date'] == archived_day and archived_day not in history)
            history[archived_day] = archived
    history[day] = value
    report = pipeline.build_recaps(list(history.values()), catalog, profiles, root=root, now=now)
    return report, catalog, avatars


DEADLINES = dict(review='06:00', corrections='06:30', freeze='06:40', target='07:00', timezone='America/Phoenix')
TIMING = ('Review by 06:00 Arizona; corrections/review/merge until 06:30. '
          'Publishing source snapshot 06:40; target 07:00 AZ (best effort).')
FALLBACK = ('No response is not approval. Existing approved art/portraits remain the fallback; '
            'this script never approves, changes public source, or deploys.')


def output_dir(repo, day):
    require(type(day) is str and re.fullmatch(r'202[67]-[0-9]{2}-[0-9]{2}', day))
    require(datetime.fromisoformat(day).date().isoformat() == day)
    repo = pipeline.safe_path(repo)
    output = pipeline.safe_path(repo / 'private/review-packets' / day)
    require(not output.is_relative_to(repo / 'public'))
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output, 0o700)
    return output


def portrait(path):
    from PIL import Image, ImageOps
    path = pipeline.safe_path(path)
    require(path.is_file() and 0 < path.stat().st_size <= 8 * 1024 * 1024)
    with Image.open(path) as source:
        require(0 < source.width <= 4096 and 0 < source.height <= 4096
                and source.width * source.height <= 16_000_000 and getattr(source, 'n_frames', 1) == 1)
        return ImageOps.fit(source.convert('RGB'), (560, 650))


def write_packet(repo, value, run, root, report, catalog, avatars, now):
    pipeline.validate_bundle(value, now=now)
    review, day = dates(now)
    require(value['daily']['date'] == day)
    edition = next(e for e in report['editions'] if e['date'] == day)
    output = output_dir(repo, day)
    late = now.astimezone(AZ).strftime('%H:%M:%S') >= '06:00:00'
    scores = {str(t['id']): t['dailyPoints'] for t in value['daily']['teams']}
    entries, staged = [], []
    message = [f'{"LATE / SETUP — " if late else ""}Unpublished DRAFT / DAILY review — {day}',
               edition['headline'], edition['coverageNote'],
               'New local captioned composites of approved character portraits; not new AI scenes/poses.']
    try:
        if edition['matchups']:
            from PIL import Image, ImageDraw, ImageFont
            font = ImageFont.load_default(size=34)
            large = ImageFont.load_default(size=46)
        for match in edition['matchups']:
            hid, aid = match['homeId'], match['awayId']
            home, away = catalog['cast'][str(hid)], catalog['cast'][str(aid)]
            provisional = value['daily']['status'] != 'verified-aggregate'
            if provisional:
                caption = 'PROVISIONAL — incomplete daily evidence; no daily win/loss awarded.'
            else:
                caption = match['title']
            image = Image.new('RGB', (1280,1280), '#101927')
            image.paste(portrait(root/'public'/avatars[home['slug']]), (50,210))
            image.paste(portrait(root/'public'/avatars[away['slug']]), (670,210))
            draw = ImageDraw.Draw(image)
            draw.text((50,35), 'Redlands Possum Busters', font=large, fill='#ffce68')
            draw.text((50,105), f'{day} / DAILY, not weekly'+(' / PROVISIONAL' if provisional else ''), font=font, fill='white')
            if late:
                draw.text((50,155), 'LATE / SETUP — review window missed', font=font, fill='#ffce68')
            for x, person, tid in ((50,home,hid),(670,away,aid)):
                label = textwrap.fill(person['displayName'], width=23)
                draw.multiline_text((x,875), label, font=font, fill='white', spacing=5)
                points = 'unavailable' if scores[str(tid)] is None else str(scores[str(tid)])
                draw.text((x,975), f'{points} daily points', font=font, fill='#86e1cf')
            draw.multiline_text((50,1060), textwrap.fill(caption, width=55), font=font, fill='white', spacing=8)
            candidate = f'review-{day}-{match["id"]}'
            filename = candidate + '.png'
            destination = pipeline.safe_path(output / filename)
            require(not destination.exists() or destination.is_file())
            with tempfile.NamedTemporaryFile(dir=output, prefix='.draft-', suffix='.tmp', delete=False) as temporary:
                temporary_path = Path(temporary.name)
            staged.append((temporary_path, destination))
            image.save(temporary_path, format='PNG')  # Fresh RGB canvas: no source EXIF/metadata.
            require(temporary_path.stat().st_size <= 8 * 1024 * 1024)
            digest = hashlib.sha256(temporary_path.read_bytes()).hexdigest()
            entries.append(dict(id=candidate, file=filename, sha256=digest, approvalStatus='pending',
                                caption=caption, scoreContext={str(t):scores[str(t)] for t in (hid,aid)},
                                managers=[home['slug'], away['slug']]))
            message.extend([f'{candidate}: {home["displayName"]} {scores[str(hid)]} / {away["displayName"]} {scores[str(aid)]} DAILY.',
                            match['story'], 'MEDIA:'+str(destination)])
        manifest = dict(schemaVersion=1, coverageDate=day, reviewDate=review, sourceRunId=run['databaseId'],
                        sourceRunUrl=run['url'], sourceSha=run['headSha'], scoreContext=scores,
                        dataStatus=value['daily']['status'], files=entries, approvalStatus='pending',
                        deadlines=DEADLINES, late=late)
        # Validate all final paths before replacing any output. Manifest is the commit marker.
        manifest_path = pipeline.safe_path(output / 'manifest.json')
        obsolete = [p for p in output.glob('review-*.png') if p.name not in {e['file'] for e in entries}]
        for path in obsolete:
            require(pipeline.safe_path(path).is_file())
        for temporary, destination in staged:
            os.replace(temporary, destination)
        for path in obsolete:
            path.unlink()
        pipeline.promote({manifest_path:pipeline.serialize(manifest)})
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    if value['daily']['status'] == 'off-day':
        message.append('Off-day: text review only; no scores or draft images invented.')
    message.extend([TIMING, 'Reply here and mention Neo with candidate IDs to approve or with edits. Owner approval plus reviewed catalog merge is required.', FALLBACK])
    return '\n'.join(message)


def load_packet(repo, now):
    review, day = dates(now)
    directory = pipeline.safe_path(repo / 'private/review-packets' / day)
    value = pipeline.read_json(directory / 'manifest.json')
    pipeline.keys(value, 'schemaVersion coverageDate reviewDate sourceRunId sourceRunUrl sourceSha scoreContext dataStatus files approvalStatus deadlines late')
    require(type(value['schemaVersion']) is int and value['schemaVersion'] == 1)
    require(value['coverageDate'] == day and value['reviewDate'] == review)
    require(value['approvalStatus'] == 'pending' and value['deadlines'] == DEADLINES and type(value['late']) is bool)
    require(type(value['sourceRunId']) is int and 0 < value['sourceRunId'] < 10**20)
    require(value['sourceRunUrl'] == f'https://github.com/{REPO}/actions/runs/{value["sourceRunId"]}')
    require(type(value['sourceSha']) is str and re.fullmatch('[0-9a-f]{40}', value['sourceSha']))
    require(value['dataStatus'] in ('verified-aggregate', 'incomplete', 'off-day'))
    require(type(value['scoreContext']) is dict and set(value['scoreContext']) == {str(i) for i in range(1,9)})
    for score in value['scoreContext'].values():
        if score is not None:
            pipeline.number(score)
    require(type(value['files']) is list and len(value['files']) <= 4)
    ids, files = set(), set()
    for item in value['files']:
        pipeline.keys(item, 'id file sha256 approvalStatus caption scoreContext managers')
        require(type(item['id']) is str and re.fullmatch('review-'+day+r'-[0-9]+', item['id']))
        require(item['file'] == item['id']+'.png' and item['id'] not in ids and item['file'] not in files)
        ids.add(item['id']); files.add(item['file'])
        require(item['approvalStatus'] == 'pending')
        require(type(item['caption']) is str and 1 <= len(item['caption']) <= 1000)
        require(type(item['sha256']) is str and re.fullmatch('[0-9a-f]{64}', item['sha256']))
        require(type(item['scoreContext']) is dict and len(item['scoreContext']) == 2
                and set(item['scoreContext']) <= set(value['scoreContext']))
        require(all(value['scoreContext'][tid] == score for tid,score in item['scoreContext'].items()))
        require(type(item['managers']) is list and len(item['managers']) == 2 and
                all(type(m) is str and re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', m) for m in item['managers'])
                and len(set(item['managers'])) == 2)
        path = pipeline.safe_path(directory / item['file'])
        require(path.is_file() and 0 < path.stat().st_size <= 8 * 1024 * 1024)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'])
    return value


def notify(repo, mode, now, transport=command):
    value = load_packet(repo, now)  # Validate before any remote request; pending is not approval.
    transport(['git', 'fetch', 'origin', 'main'], cwd=repo, limit=1024)
    sha = transport(['git', 'rev-parse', 'FETCH_HEAD'], cwd=repo, limit=128).decode().strip()
    catalog = pipeline.parse_json(object_file(repo, sha, 'src/data/editorial.json', transport))
    pipeline.keys(catalog, 'schemaVersion timezone publishTarget closeMargin smokedMargin cast approvedMemes')
    require(catalog['schemaVersion'] == 1 and catalog['timezone'] == 'America/Phoenix'
            and catalog['publishTarget'] == '07:00' and type(catalog['approvedMemes']) is list
            and len(catalog['approvedMemes']) <= 100)
    approved = []
    for candidate in value['files']:
        matches = [m for m in catalog['approvedMemes'] if isinstance(m, dict) and m.get('id') == candidate['id']]
        require(len(matches) <= 1)
        if not matches:
            continue
        item = matches[0]
        expected = set('id image caption date managers tags approvalStatus contextType'.split())
        require(set(item) in (expected, expected | {'scoreContext'}))
        require(type(item['caption']) is str and 1 <= len(item['caption']) <= 1000)
        for field in ('managers', 'tags'):
            require(type(item[field]) is list and all(type(v) is str for v in item[field])
                    and len(item[field]) == len(set(item[field])))
        if 'scoreContext' in item:
            require(type(item['scoreContext']) is dict and bool(item['scoreContext'])
                    and set(item['scoreContext']) <= {str(i) for i in range(1,9)})
            for score in item['scoreContext'].values():
                pipeline.number(score)
        if (item.get('approvalStatus') != 'approved' or item.get('contextType') != 'dated'
                or item.get('date') != value['coverageDate'] or item.get('scoreContext') != candidate['scoreContext']
                or set(item.get('managers', [])) != set(candidate['managers'])):
            continue
        image = object_file(repo, sha, 'public/' + item['image'], transport)
        if hashlib.sha256(image).hexdigest() == candidate['sha256']:
            approved.append(candidate['id'])
    title = '05:45 review reminder' if mode == 'reminder' else '06:30 correction cutoff'
    message = [title+' — '+value['coverageDate'],
               'In approved publishing catalog: '+', '.join(approved) if approved else
               'No new packet artwork is in the publishing catalog; existing approved art/portraits will be used.']
    remaining = [c['id'] for c in value['files'] if c['id'] not in approved]
    if remaining:
        message.append('Not in approved publishing catalog (fallback remains): '+', '.join(remaining))
    message.extend(['Please send feedback by 06:00 AZ.' if mode == 'reminder' else
                    'Correction cutoff reached. Remaining candidates stay private; no automatic approval. Source freeze 06:40 AZ.',
                    TIMING, FALLBACK])
    return '\n'.join(message)


def main(argv=None, *, now=None, transport=command):
    parser = pipeline.SafeArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=('packet','reminder','cutoff'), default='packet')
    parser.add_argument('--repo-dir', default=DEFAULT_REPO)
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc) if now is None else now
    try:
        repo = pipeline.safe_path(args.repo_dir)
        if args.mode == 'packet':
            value, run = prepare_input(repo, now, transport)
            with tempfile.TemporaryDirectory(prefix='review-snapshot-') as temporary:
                root = Path(temporary)
                report, catalog, avatars = snapshot(repo, run['headSha'], value, root, now, transport)
                message = write_packet(repo, value, run, root, report, catalog, avatars, now)
        else:
            message = notify(repo, args.mode, now, transport)
    except Exception:
        late = now.astimezone(AZ).strftime('%H:%M:%S') >= '06:00:00'
        print(('LATE / SETUP — ' if late else '') + 'Clubhouse review '+args.mode+' unavailable. '
              'No fresh packet or publishing approval can be confirmed. '
              'Check today’s successful prepare-review.yml run and its daily-review-input artifact; '
              'retry after validation, or request owner review. '+TIMING+' '+FALLBACK)
        return 1
    print(message)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

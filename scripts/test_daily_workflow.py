"""Offline security contract tests for the automatic clubhouse workflow (stdlib only)."""
from pathlib import Path
import re
import subprocess
import textwrap
import unittest
from unittest.mock import patch

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/daily-clubhouse.yml'


def workflow_text():
    return WORKFLOW.read_text() if WORKFLOW.exists() else ''


def job(text, name):
    match = re.search(rf'^  {name}:\n(.*?)(?=^  [a-z]+:\n|\Z)', text, re.M | re.S)
    return match.group(1) if match else ''


class DailyWorkflowTests(unittest.TestCase):
    def test_collect_is_read_only_and_credentials_are_step_scoped(self):
        text = workflow_text()
        self.assertIn("cron: '40 13 * * *'", text)
        self.assertIn('workflow_dispatch:', text)
        self.assertNotIn('inputs:', text)
        self.assertIn('group: pages\n  cancel-in-progress: false', text)
        collect = job(text, 'collect')
        self.assertIn('contents: read', collect)
        self.assertIn("github.repository == 'Cheloco44/fantasy-family' && github.ref == 'refs/heads/main'", collect)
        self.assertLess(collect.index('python -m unittest discover'), collect.index('secrets.ESPN'))
        self.assertIn('python scripts/daily_pipeline.py collect --network --output-dir artifacts/daily-batch', collect)
        self.assertEqual(text.count('${{ secrets.'), 2)
        self.assertRegex(collect, r'- name: Collect sanitized daily batch\n        env:\n          ESPN_S2: \$\{\{ secrets.ESPN_S2 \}\}\n          ESPN_SWID: \$\{\{ secrets.ESPN_SWID \}\}')
        self.assertIn('path: |\n            artifacts/daily-batch/daily.json\n            artifacts/daily-batch/current.json', collect)
        self.assertIn('retention-days: 1', collect)
        self.assertIn('if-no-files-found: error', collect)

    def test_publish_revalidates_offline_stages_only_json_and_fails_closed_on_races(self):
        text = workflow_text()
        publish = job(text, 'publish')
        self.assertIn('needs: collect', publish)
        self.assertIn('contents: write', publish)
        self.assertNotIn('secrets.', publish)
        self.assertIn('name: daily-clubhouse-batch', publish)
        self.assertIn('path: artifacts/daily-batch', publish)
        self.assertIn('python scripts/daily_pipeline.py import --input-dir artifacts/daily-batch', publish)
        self.assertNotIn('--network', publish)
        self.assertLess(publish.index('daily_pipeline.py import'), publish.index('git add --'))
        self.assertIn("git add -- ':(glob)src/data/daily/*.json' src/data/current.json src/data/recaps.json", publish)
        self.assertIn('re.fullmatch(r"src/data/daily/\\d{4}-\\d{2}-\\d{2}\\.json", path)', publish)
        self.assertIn('git diff --cached --name-only -z', publish)
        self.assertIn('test "$base" = "$(git rev-parse refs/remotes/origin/main)"', publish)
        self.assertIn('git merge-base --is-ancestor "$base" HEAD', publish)
        self.assertIn('push origin HEAD:refs/heads/main', publish)
        self.assertIn('published_sha: ${{ steps.push.outputs.sha }}', publish)
        self.assertIn('echo "sha=$(git rev-parse HEAD)" >> "$GITHUB_OUTPUT"', publish)
        self.assertEqual(publish.count('GH_TOKEN:'), 1)
        self.assertRegex(publish, r'- name: Push validated source\n        id: push\n        env:\n          GH_TOKEN: \$\{\{ github.token \}\}')
        for forbidden in ('git pull', '--force', 'git rebase', 'workflow_dispatch', 'https://x-access-token', 'git add -A', 'git add .'):
            self.assertNotIn(forbidden, publish)

    def test_build_checks_out_published_sha_without_collector_secrets(self):
        build = job(workflow_text(), 'build')
        self.assertIn('needs: publish', build)
        self.assertIn('contents: read', build)
        self.assertIn('ref: ${{ needs.publish.outputs.published_sha }}', build)
        self.assertIn("node-version: '26'", build)
        for command in ('npm ci --ignore-scripts', 'npm run build', 'npm test'):
            self.assertIn(command, build)
        self.assertIn('path: dist', build)
        self.assertNotIn('secrets.', build)
        self.assertNotIn('GH_TOKEN', build)
        self.assertNotIn('contents: write', build)

    def test_deploy_only_has_pages_permissions_and_scheduled_bounded_wait(self):
        text = workflow_text()
        deploy = job(text, 'deploy')
        self.assertIn('needs: build', deploy)
        self.assertIn('pages: write\n      id-token: write', deploy)
        self.assertIn('name: github-pages', deploy)
        self.assertIn("if: github.event_name == 'schedule'", deploy)
        self.assertLess(deploy.index('name: Scheduled not-before gate'), deploy.index('uses: actions/deploy-pages@'))
        self.assertIn('timeout-minutes: 30', deploy)
        self.assertIn('14:00:00', deploy)
        self.assertIn('delay <= 1200', deploy)
        self.assertNotIn('secrets.', deploy)
        self.assertNotIn('contents:', deploy)
        for name in ('collect', 'publish', 'build', 'deploy'):
            section = job(text, name)
            self.assertIn("if: github.repository == 'Cheloco44/fantasy-family' && github.ref == 'refs/heads/main'", section)
            self.assertRegex(section, r'timeout-minutes: [1-9][0-9]?\n')
            if name != 'deploy':
                self.assertNotIn('pages: write', section)
                self.assertNotIn('id-token: write', section)
        self.assertEqual(text.count('contents: write'), 1)
        self.assertEqual(text.count('persist-credentials: false'), text.count('uses: actions/checkout@'))
        self.assertIn('permissions: {}', text)
        self.assertIn('best effort', text)
        self.assertNotIn('always()', text)
        self.assertNotIn('continue-on-error', text)
        pins = {
            'actions/checkout': 'd23441a48e516b6c34aea4fa41551a30e30af803',
            'actions/setup-node': '249970729cb0ef3589644e2896645e5dc5ba9c38',
            'actions/upload-artifact': 'ea165f8d65b6e75b540449e92b4886f43607fa02',
            'actions/download-artifact': 'd3f86a106a0bac45b974a628896c90dbdf5c8093',
            'actions/upload-pages-artifact': '7b1f4a764d45c48632c6b24a0339c27f5614fb0b',
            'actions/deploy-pages': 'd6db90164ac5ed86f2b6aed7e0febac5b3c0c03e',
        }
        actions = re.findall(r'uses: (\S+)@(\S+)', text)
        self.assertEqual(set(name for name, _ in actions), set(pins))
        for name, pin in actions:
            self.assertEqual(pin, pins[name])

    def test_actual_wait_script_handles_early_ontime_late_and_excessive_delay(self):
        deploy = job(workflow_text(), 'deploy')
        match = re.search(r'        run: \|\n((?:          .*\n|\n)+)', deploy)
        self.assertIsNotNone(match, 'Scheduled wait script is required')
        script = textwrap.dedent(match.group(1))
        for delay, expected, sleep in ((1200, 0, True), (1, 0, True), (0, 0, False), (-900, 0, False), (1201, 1, False)):
            with self.subTest(delay=delay):
                # Shell functions provide a deterministic clock; no real sleeping or network.
                clock = f'''date() {{
                  case "$*" in
                    '-u +%s') printf '0\\n';;
                    '-u +%F') printf '2026-11-12\\n';;
                    *) printf '%s\\n' '{delay}';;
                  esac
                }}
                sleep() {{ printf 'SLEEP:%s\\n' "$1"; }}
                '''
                result = subprocess.run(['bash'], input=clock + script, text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual('SLEEP:' in result.stdout, sleep)
                if sleep:
                    self.assertIn(f'SLEEP:{delay}', result.stdout)

    def test_import_refuses_extra_artifact_entries_or_symlinks(self):
        publish = job(workflow_text(), 'publish')
        self.assertIn("expected = {'daily.json', 'current.json'}", publish)
        self.assertIn('set(p.name for p in batch.iterdir()) != expected', publish)
        self.assertIn('p.is_symlink() or not p.is_file()', publish)
        self.assertLess(publish.index('batch.iterdir()'), publish.index('daily_pipeline.py import'))

    def test_all_real_shell_blocks_are_strict_and_parse(self):
        scripts = re.findall(r'        run: \|\n((?:          .*\n|\n)+)', workflow_text())
        self.assertEqual(len(scripts), 7)
        for script in scripts:
            script = textwrap.dedent(script)
            self.assertTrue(script.startswith('set -euo pipefail\n'))
            result = subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            for source in re.findall(r"python - <<'PY'\n(.*?)\nPY", script, re.S):
                compile(source, '<workflow-python>', 'exec')

    def test_actual_stage_validator_rejects_outside_paths(self):
        publish = job(workflow_text(), 'publish')
        sources = re.findall(r"          python - <<'PY'\n(.*?)          PY", publish, re.S)
        self.assertEqual(len(sources), 2)
        source = textwrap.dedent(sources[1])
        allowed = ['src/data/daily/2026-11-11.json', 'src/data/current.json', 'src/data/recaps.json']
        rejected = ['src/data/daily/raw.json', 'src/data/daily/nested/2026-11-11.json', 'src/data/current.json.bak', 'src/pages/index.astro', '.github/workflows/deploy-pages.yml', 'src/data/daily/../current.json']
        for paths, accepted in (([], True), (allowed, True), *(([path], False) for path in rejected)):
            with self.subTest(paths=paths), patch('subprocess.check_output', return_value=('\0'.join(paths) + '\0').encode()):
                if accepted:
                    exec(compile(source, '<workflow-stage-validator>', 'exec'), {})
                else:
                    with self.assertRaises(SystemExit):
                        exec(compile(source, '<workflow-stage-validator>', 'exec'), {})

    def test_published_sha_is_verified_against_remote_before_build_output(self):
        publish = job(workflow_text(), 'publish')
        self.assertEqual(publish.count('fetch --no-tags origin refs/heads/main:refs/remotes/origin/main'), 2)
        self.assertIn('test "$(git rev-parse HEAD)" = "$(git rev-parse refs/remotes/origin/main)"', publish)
        self.assertLess(publish.index('test "$(git rev-parse HEAD)"'), publish.index('echo "sha='))


if __name__ == '__main__':
    unittest.main()

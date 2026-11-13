"""Stdlib-only offline security contract for read-only review preparation.

Exact structural/command allowlists deliberately fail closed on added permissions,
triggers, jobs, steps or artifact paths. No YAML dependency, credentials or network.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/prepare-review.yml'


def workflow_text():
    return WORKFLOW.read_text() if WORKFLOW.exists() else ''


def steps():
    return re.findall(r'^      - name: .*?(?=^      - name: |\Z)',
                      workflow_text(), re.M | re.S)


class PrepareReviewWorkflowTests(unittest.TestCase):
    def test_schedule_permissions_fixed_main_gate_and_checkout_are_allowlisted(self):
        text = workflow_text()
        # Ignore only full-line comments and blank lines; all executable YAML
        # before steps is allowlisted, including the single job and its gate.
        header = text.split('    steps:\n', 1)[0]
        meaningful = '\n'.join(line for line in header.splitlines()
                               if line.strip() and not line.lstrip().startswith('#'))
        self.assertEqual(meaningful, textwrap.dedent('''\
            name: Prepare daily review input
            on:
              schedule:
                - cron: '30 11 * * *'
              workflow_dispatch:
            permissions: {}
            jobs:
              prepare:
                if: github.repository == 'Cheloco44/fantasy-family' && github.ref == 'refs/heads/main'
                runs-on: ubuntu-24.04
                timeout-minutes: 10
                permissions:
                  contents: read
        ''').rstrip())
        self.assertEqual(text.count('    steps:\n'), 1)
        self.assertTrue(steps(), 'Pinned checkout step is required')
        self.assertEqual(textwrap.dedent(steps()[0]).strip(), textwrap.dedent('''\
            - name: Check out reviewed source
              uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
              with:
                ref: ${{ github.sha }}
                persist-credentials: false
        ''').strip())

    def test_all_offline_python_tests_run_before_any_credentials(self):
        self.assertGreaterEqual(len(steps()), 2, 'Offline test step is required')
        self.assertEqual(textwrap.dedent(steps()[1]).strip(), textwrap.dedent('''\
            - name: Offline Python tests before credentials
              run: |
                set -euo pipefail
                PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s scripts -p 'test_*.py' -v
        ''').strip())
        before_collect = workflow_text().split('      - name: Collect sanitized review input', 1)[0]
        self.assertNotIn('env:', before_collect)
        self.assertNotIn('secrets.', before_collect)
        self.assertNotIn('token:', before_collect)

    def test_collection_uses_only_step_scoped_provider_cookies_and_fixed_command(self):
        self.assertGreaterEqual(len(steps()), 3, 'Collection step is required')
        self.assertEqual(textwrap.dedent(steps()[2]).strip(), textwrap.dedent('''\
            - name: Collect sanitized review input
              env:
                ESPN_S2: ${{ secrets.ESPN_S2 }}
                ESPN_SWID: ${{ secrets.ESPN_SWID }}
              run: |
                set -euo pipefail
                set +x
                ulimit -c 0
                if ! python scripts/daily_pipeline.py collect --network --output-dir artifacts/review-input >/dev/null 2>&1; then
                  echo 'Review input collection failed; no artifact prepared.' >&2
                  exit 1
                fi
        ''').strip())
        self.assertEqual(workflow_text().count('env:'), 1)
        self.assertEqual(workflow_text().count('${{ secrets.'), 2)

    def test_actual_collection_shell_swallows_both_streams_on_success_and_failure(self):
        self.assertGreaterEqual(len(steps()), 3, 'Collection step is required')
        block = steps()[2].split('        run: |\n', 1)
        self.assertEqual(len(block), 2, 'Collection must use a literal shell block')
        script = textwrap.dedent(block[1])
        for status in (0, 1, 2, 137):
            with self.subTest(status=status):
                # Replace only the external Python command at the shell seam.
                # This executes the real YAML shell without ESPN/network/files.
                fake = '''python() {
                  test "$*" = 'scripts/daily_pipeline.py collect --network --output-dir artifacts/review-input' || return 96
                  test "$ESPN_S2" = 'synthetic-cookie-s2' || return 95
                  test "$ESPN_SWID" = 'synthetic-cookie-swid' || return 95
                  printf 'RAW-RESPONSE:%s\\n' "$ESPN_S2"
                  printf 'RAW-ERROR:%s\\n' "$ESPN_SWID" >&2
                  return STATUS
                }
                '''.replace('STATUS', str(status))
                result = subprocess.run(
                    ['bash', '--noprofile', '--norc', '-e', '-o', 'pipefail'],
                    input=fake + script, text=True, capture_output=True, timeout=5,
                    env={'PATH': '/usr/bin:/bin', 'ESPN_S2': 'synthetic-cookie-s2',
                         'ESPN_SWID': 'synthetic-cookie-swid'})
                self.assertEqual(result.returncode, 0 if status == 0 else 1)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr, '' if status == 0 else
                                 'Review input collection failed; no artifact prepared.\n')

    def test_required_artifact_files_are_checked_before_upload(self):
        self.assertEqual(len(steps()), 5, 'Exact artifact validation step is required')
        self.assertEqual(textwrap.dedent(steps()[3]).strip(), textwrap.dedent('''\
            - name: Validate exact artifact files without credentials
              run: |
                set -euo pipefail
                python - <<'PY'
                from pathlib import Path
                batch = Path('artifacts/review-input')
                expected = {'daily.json', 'current.json'}
                if (batch.is_symlink() or not batch.is_dir()
                        or set(p.name for p in batch.iterdir()) != expected
                        or any(p.is_symlink() or not p.is_file() for p in batch.iterdir())):
                    raise SystemExit('Invalid review input files; no artifact prepared.')
                PY
        ''').strip())
        script = textwrap.dedent(steps()[3].split('        run: |\n', 1)[1])
        sources = re.findall(r"python - <<'PY'\n(.*?)\nPY", script, re.S)
        self.assertEqual(len(sources), 1)
        source = sources[0]
        for case in ('valid', 'missing-daily', 'missing-current', 'empty', 'extra',
                     'symlink', 'directory', 'symlink-batch'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                batch = root / 'artifacts/review-input'
                batch.mkdir(parents=True)
                if case != 'empty':
                    for name in ('daily.json', 'current.json'):
                        if case != 'missing-' + name.split('.')[0]:
                            (batch / name).write_text('{}')
                if case == 'extra':
                    (batch / 'private-cookie.txt').write_text('synthetic-private-data')
                elif case == 'symlink':
                    (batch / 'daily.json').unlink()
                    (batch / 'daily.json').symlink_to(batch / 'current.json')
                elif case == 'directory':
                    (batch / 'daily.json').unlink()
                    (batch / 'daily.json').mkdir()
                elif case == 'symlink-batch':
                    batch.rename(root / 'elsewhere')
                    batch.symlink_to(root / 'elsewhere', target_is_directory=True)
                result = subprocess.run([sys.executable, '-c', source], cwd=root,
                                        text=True, capture_output=True, timeout=5,
                                        env={'PATH': '/usr/bin:/bin'})
                self.assertEqual(result.returncode, 0 if case == 'valid' else 1)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr, '' if case == 'valid' else
                                 'Invalid review input files; no artifact prepared.\n')

    def test_upload_is_required_exact_two_files_one_day_and_pinned(self):
        self.assertEqual(len(steps()), 5, 'Only reviewed preparation steps are allowed')
        self.assertEqual(textwrap.dedent(steps()[4]).strip(), textwrap.dedent('''\
            - name: Upload exact sanitized review input
              uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
              with:
                name: daily-review-input
                path: |
                  artifacts/review-input/daily.json
                  artifacts/review-input/current.json
                retention-days: 1
                if-no-files-found: error
        ''').strip())
        # No hidden extra keys/jobs/steps between the allowlisted blocks.
        self.assertEqual(workflow_text().split('    steps:\n', 1)[1], ''.join(steps()))
        self.assertEqual(re.findall(r'uses: (\S+)@(\S+)', workflow_text()), [
            ('actions/checkout', 'd23441a48e516b6c34aea4fa41551a30e30af803'),
            ('actions/upload-artifact', 'ea165f8d65b6e75b540449e92b4886f43607fa02'),
        ])

    def test_real_shell_blocks_are_strict_parseable_and_embedded_python_compiles(self):
        scripts = re.findall(r'        run: \|\n((?:          .*\n|\n)+)', workflow_text())
        self.assertEqual(len(scripts), 3)
        for block in scripts:
            script = textwrap.dedent(block)
            self.assertTrue(script.startswith('set -euo pipefail\n'))
            result = subprocess.run(['bash', '-n'], input=script, text=True,
                                    capture_output=True, timeout=5,
                                    env={'PATH': '/usr/bin:/bin'})
            self.assertEqual(result.returncode, 0, result.stderr)
            for source in re.findall(r"python - <<'PY'\n(.*?)\nPY", script, re.S):
                compile(source, '<prepare-review-python>', 'exec')
        # The command allowlists above also forbid hidden alternate interpreters,
        # source import/write/commit/deploy, installers, and broad asset uploads.
        for forbidden in ('always()', 'continue-on-error', 'write-all', 'contents: write',
                          'pages:', 'id-token:', 'git push', 'git commit', 'npm ',
                          'pip install', 'daily_pipeline.py import', 'set -x'):
            self.assertNotIn(forbidden, workflow_text())


if __name__ == '__main__':
    unittest.main()
